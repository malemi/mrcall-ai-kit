import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
import websockets

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(tempfile.gettempdir()) / 'mrcall-ai-kit/supervisor-m4-install'


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix='supervision-install-')) / 'home'
        self.home.mkdir()
        self.kit = self.home / '.config/mrcall-ai-kit'
        self.state = self.home / 'state space%percent'
        self.crontab = self.home / 'crontab.fixture'
        self.foreign_cron = 'MAILTO=operator@example.org\n5 * * * * /foreign/job\n'
        self.crontab.write_text(self.foreign_cron)
        binary = self.home / 'bin'
        binary.mkdir()
        executable = binary / 'crontab'
        executable.write_text('#!' + sys.executable + '''
import os,sys
from pathlib import Path
path = Path(os.environ['CRONTAB_FIXTURE_FILE'])
if sys.argv[1:] == ['-l']:
    sys.stdout.write(path.read_text())
elif sys.argv[1:] == ['-']:
    path.write_text(sys.stdin.read())
else:
    raise SystemExit(9)
''')
        executable.chmod(0o700)
        self.env = {**os.environ, 'HOME': str(self.home), 'CODEX_HOME': str(self.home / '.codex'),
                    'XDG_STATE_HOME': str(self.home / '.local/state'), 'XDG_CONFIG_HOME': str(self.home / '.config'),
                    'MRCALL_KIT_HOME': str(self.kit), 'PYTHONDONTWRITEBYTECODE': '1',
                    'PYTHONPATH': str(Path(websockets.__file__).resolve().parent.parent),
                    'PATH': str(binary) + os.pathsep + os.environ['PATH'], 'CRONTAB_FIXTURE_FILE': str(self.crontab)}
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        self.log = EVIDENCE / (self.id().split('.')[-1] + '.log')
        self.log.write_text('')

    def run_cli(self, argv, data=None, expected=0):
        result = subprocess.run(list(map(str, argv)), cwd=ROOT, env=self.env, input=json.dumps(data) if data is not None else None,
                                text=True, capture_output=True, timeout=60)
        with self.log.open('a') as output:
            output.write(json.dumps({'argv': list(map(str, argv)), 'exit': result.returncode}) + '\n' + result.stdout + result.stderr)
        self.assertEqual(result.returncode, expected, str(self.log) + '\n' + result.stdout + result.stderr)
        return result.stdout + result.stderr

    def install(self, mode='copy', policy='overwrite', environment='codex', features='supervision', expected=0, extra=()):
        return self.run_cli(['bash', ROOT / 'install.sh', '--environment', environment, '--features', features,
                             '--mode', mode, '--on-exist', policy, '--yes', *extra], expected=expected)

    def cli(self, command, data=None, extra=()):
        return json.loads(self.run_cli([sys.executable, self.kit / 'supervision/cli.py', '--state-dir', self.state,
                                       command, *extra], data))['result']

    def installed_lifecycle(self, mode):
        self.install(mode, extra=('--dry-run',))
        self.assertFalse(self.kit.exists())
        self.install(mode)
        self.assertEqual(self.crontab.read_text(), self.foreign_cron)
        self.assertFalse(self.state.exists())
        self.assertFalse((self.home / '.local/state').exists())
        self.assertFalse((self.home / '.codex/hooks.json').exists())
        self.assertFalse((self.home / '.config/opencode').exists())
        cli = self.kit / 'supervision/cli.py'
        self.assertEqual(cli.is_symlink(), mode == 'symlink')
        self.assertFalse(cli.parent.is_symlink())
        self.assertTrue((self.home / '.agents/skills/supervisor/SKILL.md').is_file())
        self.assertTrue((self.kit / 'supervision/codex_transport.py').is_file())
        self.assertEqual(self.cli('status')['tasks'], [])
        self.run_cli([sys.executable, '-c', "import sys;sys.path.insert(0,sys.argv[1]);import harness;c,e,w=harness.modules();print(c.__file__,e.__file__,w.__file__)", str(cli.parent)])
        self.install(mode)
        self.assertEqual(self.crontab.read_text(), self.foreign_cron)
        from test_supervision_transport import TransportTests
        native = TransportTests()
        native.setUp()
        try:
            with native.server():
                discovery = self.home / 'bin/codex-fixture'
                discovery.write_text('#!' + sys.executable + '\nimport json\nprint(json.dumps(' + repr({'status': 'running', 'socketPath': str(native.root / 'control.sock')}) + '))\n')
                discovery.chmod(0o700)
                payload = {'id': 'team', 'session_id': native.thread_id}
                self.cli('activate', payload, ('--codex-path', str(discovery)))
                registered = self.crontab.read_text()
                self.cli('activate', payload, ('--codex-path', str(discovery)))
                self.assertEqual(self.crontab.read_text(), registered)
                self.assertEqual(registered.count(':start'), 1)
                self.assertTrue(registered.startswith(self.foreign_cron))
                self.assertEqual(native.accepted, [])
        finally:
            native.tearDown()
        self.cli('memory-add', {'supervisor_id': 'team', 'kind': 'fact', 'content': 'Retain after uninstall', 'source': 'fixture', 'evidence': []})
        policy = self.kit / 'supervision/POLICY.md'
        if mode == 'copy':
            policy.write_text(policy.read_text() + '\nOperator addition.\n')
        before = self.crontab.read_text()
        self.run_cli(['bash', ROOT / 'uninstall.sh', '--yes', '--dry-run'])
        self.assertEqual(self.crontab.read_text(), before)
        self.assertEqual(self.cli('status')['bindings'][0]['status'], 'active')
        self.run_cli(['bash', ROOT / 'uninstall.sh', '--yes'])
        self.assertEqual(self.crontab.read_text(), self.foreign_cron)
        self.assertFalse(cli.exists() or cli.is_symlink())
        self.assertFalse((self.home / '.agents/skills/supervisor').exists())
        self.assertTrue((self.state / 'state.sqlite3').is_file())
        import sqlite3
        with sqlite3.connect(self.state / 'state.sqlite3') as db:
            self.assertEqual(db.execute('SELECT status FROM bindings').fetchone()[0], 'detached')
            self.assertEqual(db.execute('SELECT content FROM memory').fetchone()[0], 'Retain after uninstall')
        if mode == 'copy':
            self.assertIn('Operator addition.', policy.read_text())

    def test_copy_lifecycle(self):
        self.installed_lifecycle('copy')

    def test_symlink_lifecycle(self):
        self.installed_lifecycle('symlink')

    def test_unsupported_and_foreign_skip(self):
        result = self.install(environment='opencode', expected=1)
        self.assertIn('Nothing to install', result)
        self.assertIn('supervision requires Claude Code or Codex', result)
        self.assertFalse(self.kit.exists())
        foreign = self.home / '.agents/skills/supervisor/SKILL.md'
        foreign.parent.mkdir(parents=True)
        foreign.write_text('Foreign skill\n')
        self.install(policy='skip')
        self.assertEqual(foreign.read_text(), 'Foreign skill\n')
        self.run_cli(['bash', ROOT / 'uninstall.sh', '--yes'])
        self.assertEqual(foreign.read_text(), 'Foreign skill\n')
        self.assertEqual(self.crontab.read_text(), self.foreign_cron)

    def test_claude_only_then_combined_installed_delivery(self):
        from test_supervision_claude_transport import ClaudeFixture
        native = ClaudeFixture()
        self.addCleanup(native.close)
        self.env['CLAUDE_CONFIG_DIR'] = str(native.config_root)
        self.install(environment='claude')
        skill = self.home / '.claude/skills/supervisor/SKILL.md'
        self.assertTrue(skill.is_file())
        self.assertFalse((self.home / '.agents/skills/supervisor').exists())
        self.assertFalse(self.state.exists())
        self.assertEqual(self.crontab.read_text(), self.foreign_cron)
        self.install(environment='all')
        self.assertTrue((self.home / '.agents/skills/supervisor/SKILL.md').is_file())
        self.assertTrue((self.kit / 'supervision/claude_transport.py').is_file())
        self.cli('activate', {'id': 'team', 'runtime': 'claude', 'session_id': native.thread_id},
                 ('--claude-path', str(native.executable)))
        self.cli('task-create', {'id': 't', 'supervisor_id': 'team', 'instruction': 'Verify fixture',
                               'scope': 'fixture', 'acceptance': ['actual result'], 'next_run_at': 0, 'limits': {'provenance': 'fixture'}})
        self.cli('tick', extra=('--claude-path', str(native.executable)))
        self.assertTrue(native.received.wait(2))
        execution = self.cli('status')['executions'][0]
        self.assertEqual(execution['status'], 'uncertain')
        native.receipt(native.frames[0])
        confirmed = self.cli('execution-reconcile', extra=('--id', execution['id'], '--claude-path', str(native.executable)))
        self.assertEqual(confirmed['status'], 'delivered')
        self.assertEqual(len(native.frames), 1)
        self.run_cli(['bash', ROOT / 'uninstall.sh', '--yes'])
        self.assertEqual(self.crontab.read_text(), self.foreign_cron)
        self.assertFalse(skill.exists())
        self.assertFalse((self.home / '.agents/skills/supervisor').exists())
        self.assertTrue((self.state / 'state.sqlite3').is_file())

    def test_missing_native_prerequisite_does_not_activate(self):
        self.install()
        result = subprocess.run([sys.executable, str(self.kit / 'supervision/cli.py'), '--state-dir', str(self.state),
                                 '--codex-path', str(self.home / 'absent-codex'), 'activate'],
                                input=json.dumps({'id': 'team', 'session_id': str(uuid.uuid4())}),
                                env=self.env, text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertIn('cannot discover running Codex daemon', json.loads(result.stdout)['error'])
        self.assertEqual(self.crontab.read_text(), self.foreign_cron)
        self.assertEqual(self.cli('status')['bindings'], [])

    def test_modified_executable_refuses_uninstall(self):
        self.install()
        module = self.kit / 'supervision/store.py'
        module.write_text(module.read_text() + '\nraise RuntimeError("foreign must not execute")\n')
        result = subprocess.run(['bash', str(ROOT / 'uninstall.sh'), '--yes'], env=self.env, cwd=ROOT,
                                text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Cannot disable supervision safely', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertTrue((self.kit / 'supervision/cli.py').exists())
        self.assertEqual(self.crontab.read_text(), self.foreign_cron)


if __name__ == '__main__':
    unittest.main()
