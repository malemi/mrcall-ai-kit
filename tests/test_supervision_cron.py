from pathlib import Path
from types import SimpleNamespace
import tempfile
import json
import os
import subprocess
from unittest.mock import patch
import unittest
import uuid
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.supervision.cron import Cron, activate, deactivate, deactivate_owned
from shared.supervision.store import Store, StoreError


class CrontabFixture:
    def __init__(self):
        self.content = 'MAILTO=owner@example.org\n5 * * * * /foreign/job\n'
        self.writes = 0

    def __call__(self, args, **kwargs):
        if args == ['crontab', '-l']:
            return SimpleNamespace(returncode=0, stdout=self.content, stderr='')
        self.content = kwargs['input']
        self.writes += 1
        return SimpleNamespace(returncode=0, stdout='', stderr='')


class NativeFixture:
    def metadata(self, session):
        return {'id': session, 'canAcceptDirectInput': True, 'parentThreadId': None}


class CronTests(unittest.TestCase):
    def test_deactivate_owned_custom_roots_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = CrontabFixture()
            original = fixture.content
            cli = Path(__file__).resolve().parents[1] / 'shared/supervision/cli.py'
            roots = [Path(tmp) / 'custom state%one', Path(tmp) / 'second']
            for root in roots:
                store = Store(root)
                store.bind({'id': 'bound', 'session_id': str(uuid.uuid4())})
                store.add_memory({'supervisor_id': 'bound', 'kind': 'fact', 'content': 'retained', 'source': 'test'})
                store.close()
                Cron(root, cli_path=cli, runner=fixture).apply(True)
            foreign_cli = Path(tmp) / 'foreign.py'
            foreign_cli.write_text('raise SystemExit("must never execute")')
            foreign = Cron(Path(tmp) / 'foreign', cli_path=foreign_cli)
            foreign_block = foreign.render('', True)
            malformed = '# mrcall-ai-kit:supervision:aaaaaaaaaaaaaaaa:start\n# foreign malformed retained\n'
            fixture.content += foreign_block + malformed
            preview = deactivate_owned(cli, fixture, dry_run=True)
            self.assertEqual(len(preview['state_dirs']), 2)
            result = deactivate_owned(cli, fixture)
            self.assertEqual(result['state_dirs'], [str(root) for root in roots])
            self.assertEqual(fixture.content, original + foreign_block + malformed)
            for root in roots:
                store = Store(root)
                self.assertEqual(store.binding('bound')['status'], 'detached')
                self.assertEqual(store.memory({'supervisor_id': 'bound'})[0]['content'], 'retained')
                store.close()

    def test_deactivate_owned_real_cli_and_failure_preserves_cron(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'custom%state'
            store = Store(root)
            store.bind({'id': 'bound', 'session_id': str(uuid.uuid4())})
            store.close()
            cli = Path(__file__).resolve().parents[1] / 'shared/supervision/cli.py'
            fixture = Path(tmp) / 'crontab-data'
            fixture.write_text(Cron(root, cli_path=cli).render('5 * * * * /foreign/job\n', True))
            binary = Path(tmp) / 'crontab'
            binary.write_text('#!' + sys.executable + '\nimport pathlib,sys\np=pathlib.Path(' + repr(str(fixture)) + ')\nif sys.argv[1]=="-l": print(p.read_text(),end="")\nelse: p.write_text(sys.stdin.read())\n')
            binary.chmod(0o700)
            result = subprocess.run([sys.executable, str(cli), 'deactivate-owned'], env={**os.environ, 'PATH': tmp + os.pathsep + os.environ['PATH']}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)['result']['changed'])
            self.assertEqual(fixture.read_text(), '5 * * * * /foreign/job\n')
            store = Store(root)
            self.assertEqual(store.binding('bound')['status'], 'detached')
            store.close()
            bad = CrontabFixture()
            bad.content = Cron(Path(tmp) / 'missing', cli_path=cli).render('', True)
            before = bad.content
            with self.assertRaisesRegex(StoreError, 'missing'):
                deactivate_owned(cli, bad)
            self.assertEqual(bad.content, before)
            self.assertEqual(bad.writes, 0)

    def test_deactivate_owned_absent_cron_and_refused_write(self):
        def absent(*args, **kwargs):
            raise FileNotFoundError('crontab')
        self.assertTrue(deactivate_owned(runner=absent)['cron_unavailable'])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'state'
            store = Store(root)
            store.bind({'id': 's', 'session_id': str(uuid.uuid4())})
            store.close()
            fixture = CrontabFixture()
            fixture.content = Cron(root).render('', True)
            original = fixture.content
            def refused(args, **kwargs):
                if args == ['crontab', '-']:
                    return SimpleNamespace(returncode=1, stdout='', stderr='write refused')
                return fixture(args, **kwargs)
            with self.assertRaisesRegex(StoreError, 'retain helpers'):
                deactivate_owned(runner=refused)
            self.assertEqual(fixture.content, original)
            store = Store(root)
            self.assertEqual(store.binding('s')['status'], 'detached')
            store.close()

    def test_cron_large_environment_uses_short_path_and_absolute_codex(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex = Path(tmp) / 'codex'
            codex.write_text('must not execute')
            codex.chmod(0o700)
            enormous = tmp + os.pathsep + os.pathsep.join('/long/unused/path/' + str(i) for i in range(1000))
            self.assertGreater(len(enormous), 5000)
            with patch.dict(os.environ, {'PATH': enormous}):
                command = Cron(Path(tmp) / 'state').command()
                self.assertLess(len(command), 1000)
                self.assertIn('PATH=' + os.defpath, command)
                self.assertIn('--codex-path ' + str(codex), command)
                explicit = Cron(Path(tmp) / 'state').command('/explicit/codex')
                self.assertIn('--codex-path /explicit/codex', explicit)
                self.assertNotIn('--codex-path ' + str(codex), explicit)

    def test_malformed_and_newline_rejected(self):
        cron = Cron('/tmp/state')
        with self.assertRaises(StoreError):
            cron.render(cron.start + '\n', True)
        with self.assertRaises(StoreError):
            Cron('/tmp/state\n* * * * * evil').command()
        with self.assertRaises(StoreError):
            cron.command('relative-codex')

    def test_activation_detachment_no_native_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'state')
            try:
                fixture = CrontabFixture()
                cron = Cron(store.root, runner=fixture)
                binding = {'id': 's', 'session_id': str(uuid.uuid4())}
                activate(store, NativeFixture(), binding, cron, dry_run=True)
                self.assertEqual(store.status()['bindings'], [])
                activate(store, NativeFixture(), binding, cron, codex_path='/custom/codex')
                activate(store, NativeFixture(), binding, cron)
                self.assertEqual(fixture.writes, 1)
                claude = {'id': 'claude', 'runtime': 'claude', 'session_id': str(uuid.uuid4())}
                activate(store, NativeFixture(), claude, cron, claude_path='/custom/claude')
                activate(store, NativeFixture(), binding, cron)
                self.assertIn('--codex-path /custom/codex', fixture.content)
                self.assertIn('--claude-path /custom/claude', fixture.content)
                self.assertEqual(fixture.content.count(cron.start), 1)
                deactivate(store, cron)
                self.assertEqual(store.binding('s')['status'], 'detached')
                self.assertNotIn(cron.start, fixture.content)
            finally:
                store.close()


if __name__ == '__main__':
    unittest.main()
