"""Real install/uninstall checks with isolated homes; no inference calls."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(tempfile.gettempdir()) / 'mrcall-ai-kit/automatic-av/install-tests'


def digest(path):
    mode = path.lstat().st_mode
    entries = [['.', stat.S_IFMT(mode), stat.S_IMODE(mode), hashlib.sha256(path.read_bytes()).hexdigest()]]
    return hashlib.sha256(json.dumps(entries, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()


def snapshot(root):
    result = {}
    for base, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            path = Path(base) / name
            result[str(path.relative_to(root))] = (os.readlink(path) if path.is_symlink() else
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else 'directory')
    return result


class AutoAvInstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='auto-av-install-')
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.kit = self.home / '.config/mrcall-ai-kit'
        self.kit.mkdir(parents=True)
        self.env = dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.home / '.codex'),
                        XDG_CONFIG_HOME=str(self.home / '.config'),
                        MRCALL_KIT_HOME=str(self.kit),
                        npm_config_cache=str(self.home / '.npm'),
                        npm_config_registry='https://registry.npmjs.org')
        self.log = EVIDENCE / (self.id().split('.')[-1] + '.log')
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self.log.write_text('')
        self.old = self.kit / 'completion-check/completion_check.py'
        self.old.parent.mkdir()
        self.audit = self.old.parent / 'audit.jsonl'
        self.audit.write_bytes(b'{"historical":"retain exactly"}\n')
        self.registries = [self.home / '.codex/hooks.json', self.home / '.claude/settings.json']
        self.foreign = {'foreign': {'preserve': True}, 'hooks': {
            'Stop': [{'matcher': '*', 'hooks': [{'type': 'command', 'command': 'foreign-hook --keep'}]}],
            'ForeignEvent': [{'hooks': [{'type': 'command', 'command': 'other-hook'}]}]}}
        old_command = shlex.join([sys.executable, str(self.old), 'hook', '--owner', 'mrcall-completion-v1'])
        for path in self.registries:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = json.loads(json.dumps(self.foreign))
            if path.name == 'hooks.json':
                data['hooks']['Stop'][0]['hooks'].append({'type': 'command', 'command': old_command})
            path.write_text(json.dumps(data))
        self.foreign_plugin = self.home / '.config/opencode/plugins/foreign.js'
        self.foreign_plugin.parent.mkdir(parents=True)
        self.foreign_plugin.write_text('export default {};\n')

    def run_cli(self, argv, timeout=60):
        process = subprocess.Popen(argv, cwd=ROOT, env=self.env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)
        capped = False
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            capped = True
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate(timeout=5)
        with self.log.open('a') as handle:
            handle.write(json.dumps({'argv': list(map(str, argv)), 'exit': process.returncode,
                                     'timeout': capped}) + '\n')
            handle.write(stdout + stderr + '\n')
        self.assertFalse(capped, f'60-second command limit: see {self.log}')
        self.assertEqual(process.returncode, 0, f'{argv}: see {self.log}\n{stderr}')
        return stdout

    def seed_legacy(self, kind):
        if kind == 'symlink':
            source = self.home / 'removed-checkout/completion_check.py'
            self.old.symlink_to(source)
            fields = ['fixture', 'symlink', str(self.old), str(source), '', '']
        else:
            self.old.write_text('old owned executable\n')
            fields = ['fixture', 'copy', str(self.old), str(ROOT / 'shared/scripts/completion_check.py'), '', digest(self.old)]
            if kind == 'modified':
                self.old.write_text('operator modified executable\n')
        (self.kit / 'installed.tsv').write_text('\t'.join(fields) + '\n')

    def installation(self, mode, kind):
        self.seed_legacy(kind)
        argv = ['bash', str(ROOT / 'install.sh'), '--environment', 'all', '--features', 'doc-harness',
                '--mode', mode, '--on-exist', 'overwrite', '--yes']
        before = snapshot(self.home)
        self.run_cli(argv + ['--dry-run'])
        self.assertEqual(snapshot(self.home), before)
        self.run_cli(argv)
        helper = self.kit / 'auto-av/auto_av.py'
        self.assertEqual(helper.is_symlink(), mode == 'symlink')
        for asset in ('av.md', 'selector.md'):
            self.assertEqual((helper.parent / asset).read_bytes(), (ROOT / 'shared/shortcuts' / asset).read_bytes())
        for runtime in ('claude', 'codex'):
            status = json.loads(self.run_cli([sys.executable, str(helper), 'status', '--runtime', runtime]))
            self.assertEqual(status['registered_events'], ['UserPromptSubmit', 'Stop', 'SessionEnd'])
            self.assertFalse(status['completion_certification'])
        for registry in self.registries:
            data = json.loads(registry.read_text())
            self.assertEqual(data['foreign'], self.foreign['foreign'])
            self.assertEqual(data['hooks']['ForeignEvent'], self.foreign['hooks']['ForeignEvent'])
            commands = [hook['command'] for entry in data['hooks']['Stop'] for hook in entry['hooks']]
            self.assertIn('foreign-hook --keep', commands)
            self.assertFalse(any('completion_check.py' in command for command in commands))
        self.assertTrue(self.old.is_file())
        if kind != 'modified':
            cached = subprocess.run([sys.executable, str(self.old), 'hook', '--owner', 'mrcall-completion-v1'],
                                    input='{}', capture_output=True, text=True, env=self.env, timeout=5)
            self.assertEqual(cached.returncode, 0, cached.stderr)
            self.assertEqual(json.loads(cached.stdout), {})
            self.assertFalse(self.old.is_symlink())
            for action in ('review', 'bind', 'exec', 'on'):
                retired = subprocess.run([sys.executable, str(self.old), action], capture_output=True,
                                         text=True, env=self.env, timeout=5)
                self.assertEqual(retired.returncode, 2)
                self.assertIn('retired', retired.stderr)
        self.assertTrue((helper.parent / 'retired_completion.py').is_file())
        self.assertEqual(self.audit.read_bytes(), b'{"historical":"retain exactly"}\n')
        bundle = helper.parent / 'opencode-v2'
        verify_role = self.home / '.config/opencode/agents/verify.md'
        self.assertEqual(verify_role.read_bytes(), (ROOT / 'opencode/agents/medium/verify.md').read_bytes())
        self.assertTrue(bundle.is_dir())
        self.assertFalse(bundle.is_symlink())
        self.assertTrue((bundle / 'node_modules').is_dir())
        dependencies = json.loads(self.run_cli(['npm', 'ls', '--prefix', str(bundle), '--omit=dev', '--json']))
        self.assertEqual(dependencies['dependencies']['effect']['version'], '4.0.0-beta.83')
        status = json.loads(self.run_cli([sys.executable, str(helper), 'status', '--runtime', 'opencode']))
        self.assertTrue(status['registered'])
        plugin = self.home / '.config/opencode/plugins/mrcall-auto-av'
        self.assertTrue(plugin.is_symlink())
        self.assertEqual(plugin.resolve(), bundle.resolve())
        before = snapshot(self.home)
        self.run_cli(['bash', str(ROOT / 'uninstall.sh'), '--yes', '--dry-run'])
        self.assertEqual(snapshot(self.home), before)
        self.run_cli(['bash', str(ROOT / 'uninstall.sh'), '--yes'])
        self.assertFalse(helper.exists() or helper.is_symlink())
        self.assertFalse(bundle.exists())
        self.assertFalse(plugin.exists() or plugin.is_symlink())
        for registry in self.registries:
            self.assertEqual(json.loads(registry.read_text()), self.foreign)
        self.assertEqual(self.audit.read_bytes(), b'{"historical":"retain exactly"}\n')
        self.assertEqual(self.foreign_plugin.read_text(), 'export default {};\n')
        if kind == 'modified':
            self.assertEqual(self.old.read_text(), 'operator modified executable\n')
        else:
            self.assertFalse(self.old.exists() or self.old.is_symlink())

    def install_skip(self, environment):
        binary_dir = self.home / 'bin'
        binary_dir.mkdir()
        marker = self.home / 'npm-executed'
        for name, body in {
            'opencode': '#!/bin/sh\nprintf "2.0.32\\n"\n',
            'npm': '#!/bin/sh\ntouch ' + shlex.quote(str(marker)) + '\nexit 99\n',
        }.items():
            executable = binary_dir / name
            executable.write_text(body)
            executable.chmod(0o755)
        self.env['PATH'] = str(binary_dir) + os.pathsep + self.env['PATH']
        output = self.run_cli(['bash', str(ROOT / 'install.sh'), '--environment', environment,
                               '--features', 'doc-harness', '--mode', 'copy',
                               '--on-exist', 'skip', '--yes'])
        self.assertFalse(marker.exists())
        return output

    def assert_not_owned(self, destination):
        records = [line.split('\t') for line in (self.kit / 'installed.tsv').read_text().splitlines()]
        self.assertFalse(any(len(record) >= 3 and record[2] == str(destination) for record in records))

    def test_skip_preserves_foreign_bundle_without_npm_or_registration(self):
        bundle = self.kit / 'auto-av/opencode-v2'
        bundle.mkdir(parents=True)
        package = b'{"name":"foreign-preserved-bundle","dependencies":{}}\n'
        plugin = b'export default { foreign: true };\n'
        (bundle / 'package.json').write_bytes(package)
        (bundle / 'index.js').write_bytes(plugin)
        before = snapshot(bundle)
        output = self.install_skip('opencode')
        self.assertEqual(snapshot(bundle), before)
        self.assertEqual((bundle / 'package.json').read_bytes(), package)
        self.assertEqual((bundle / 'index.js').read_bytes(), plugin)
        self.assertFalse((bundle / 'node_modules').exists())
        self.assertFalse((bundle / 'package-lock.json').exists())
        self.assert_not_owned(bundle)
        registration = self.home / '.config/opencode/plugins/mrcall-auto-av'
        self.assertFalse(registration.exists() or registration.is_symlink())
        self.assertEqual(self.foreign_plugin.read_bytes(), b'export default {};\n')
        self.assertIn('Automatic av unavailable for OpenCode: preserved plugin bundle is foreign or modified.', output)

    def test_skip_preserves_foreign_helper_without_execution_or_registration(self):
        helper = self.kit / 'auto-av/auto_av.py'
        helper.parent.mkdir()
        marker = self.home / 'foreign-helper-executed'
        contents = ('from pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("executed")\n').encode()
        helper.write_bytes(contents)
        registries = {path: path.read_bytes() for path in self.registries}
        output = self.install_skip('all')
        self.assertEqual(helper.read_bytes(), contents)
        self.assertFalse(marker.exists())
        self.assert_not_owned(helper)
        for path, original in registries.items():
            self.assertEqual(path.read_bytes(), original)
        registration = self.home / '.config/opencode/plugins/mrcall-auto-av'
        self.assertFalse(registration.exists() or registration.is_symlink())
        bundle = helper.parent / 'opencode-v2'
        self.assertFalse((bundle / 'node_modules').exists())
        self.assertFalse((bundle / 'package-lock.json').exists())
        self.assertIn('Automatic av unavailable: preserved helper or shared asset is foreign or modified; no registration performed.', output)

    def test_skip_preserves_foreign_shared_assets_without_registration(self):
        original_env = self.env.copy()
        for asset in ('av.md', 'selector.md', 'retired_completion.py'):
            with self.subTest(asset=asset):
                case_home = self.home / asset
                kit = case_home / '.config/mrcall-ai-kit'
                destination = kit / 'auto-av' / asset
                destination.parent.mkdir(parents=True)
                contents = ('Foreign shared asset: ' + asset + '\n').encode()
                destination.write_bytes(contents)
                registries = [case_home / '.claude/settings.json', case_home / '.codex/hooks.json']
                originals = {}
                for registry in registries:
                    registry.parent.mkdir(parents=True)
                    registry.write_text(json.dumps(self.foreign))
                    originals[registry] = registry.read_bytes()
                self.env = dict(original_env, HOME=str(case_home), CODEX_HOME=str(case_home / '.codex'),
                                XDG_CONFIG_HOME=str(case_home / '.config'), MRCALL_KIT_HOME=str(kit),
                                npm_config_cache=str(case_home / '.npm'))
                output = self.run_cli(['bash', str(ROOT / 'install.sh'), '--environment', 'claude',
                                       '--features', 'doc-harness', '--mode', 'copy',
                                       '--on-exist', 'skip', '--yes'])
                self.assertEqual(destination.read_bytes(), contents)
                for registry, before in originals.items():
                    self.assertEqual(registry.read_bytes(), before)
                registration = case_home / '.config/opencode/plugins/mrcall-auto-av'
                self.assertFalse(registration.exists() or registration.is_symlink())
                records = [line.split('\t') for line in (kit / 'installed.tsv').read_text().splitlines()]
                self.assertFalse(any(len(record) >= 3 and record[2] == str(destination) for record in records))
                self.assertIn('Automatic av unavailable: preserved helper or shared asset is foreign or modified; no registration performed.', output)
        self.env = original_env

    def test_copy_retires_owned_dangling_legacy_and_preserves_foreign(self):
        self.installation('copy', 'symlink')

    def test_symlink_uses_physical_bundle_and_preserves_modified_legacy(self):
        self.installation('symlink', 'modified')


if __name__ == '__main__':
    unittest.main()
