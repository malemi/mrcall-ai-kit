import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_supervision_install as legacy_install


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(tempfile.gettempdir()) / 'mrcall-ai-kit/persistent-goal-20261030/m4-install'
GOAL_ASSETS = ('goal_acceptance.py', 'goal_child.py', 'goal_client.py', 'goal_driver.py',
               'goal_native.py', 'goal_service.py', 'goal_setup.py', 'goal_store.py', 'goal.service')


class GoalInstallTests(unittest.TestCase):
    def setUp(self):
        self.fixture = legacy_install.InstallTests(methodName='runTest')
        self.fixture.setUp()
        self.addCleanup(shutil.rmtree, self.fixture.home.parent)
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        self.fixture.log = EVIDENCE / (self.id().split('.')[-1] + '.log')
        self.fixture.log.write_text('')

    def shipping(self, mode):
        self.fixture.install(mode, extra=('--dry-run',))
        self.assertFalse(self.fixture.kit.exists())
        output = self.fixture.install(mode)
        installed = self.fixture.kit / 'supervision'
        for name in GOAL_ASSETS:
            target = installed / name
            self.assertTrue(target.is_file(), name)
            self.assertFalse(target.is_symlink(), name)
            self.assertEqual(target.read_bytes(), (ROOT / 'shared/supervision' / name).read_bytes())
        native = installed / 'codex_transport.py'
        self.assertFalse(native.is_symlink())
        self.assertEqual(native.read_bytes(), (ROOT / 'codex/supervision/transport.py').read_bytes())
        self.assertEqual((installed / 'cli.py').is_symlink(), mode == 'symlink')
        self.assertEqual(self.fixture.crontab.read_text(), self.fixture.foreign_cron)
        self.assertFalse(self.fixture.state.exists())
        self.assertFalse((self.fixture.home / '.local/state').exists())
        self.assertFalse((self.fixture.home / '.config/systemd').exists())
        self.assertFalse((installed / 'config.json').exists())
        self.assertFalse((installed / 'control.sock').exists())
        self.assertIn('no goal service was activated', output)
        manifest = (self.fixture.kit / 'installed.tsv').read_text().splitlines()
        modes = {row.split('\t')[2]: row.split('\t')[1] for row in manifest}
        for name in (*GOAL_ASSETS, 'codex_transport.py'):
            self.assertEqual(modes[str(installed / name)], 'copy')
        return installed

    def test_copy_ships_dormant_assets(self):
        self.shipping('copy')

    def test_symlink_ships_usable_protected_setup_copies(self):
        self.shipping('symlink')

    def protected_setup(self, mode):
        installed = self.shipping(mode)
        base = self.fixture.home.parent
        base.chmod(0o755)
        agent = base / 'agent'
        verifier = base / 'verifier'
        agent.mkdir(mode=0o700)
        verifier.mkdir(mode=0o700)
        os.chown(agent, 60011, 60011)
        os.chown(verifier, 60012, 60012)
        protected = base / 'protected-goals'
        output = self.fixture.run_cli([
            '/usr/bin/python3', '-I', installed / 'goal_setup.py', '--mode', 'protected', '--root', protected,
            '--agent-uid', '60011', '--agent-gid', '60011', '--agent-home', agent,
            '--verifier-uid', '60012', '--verifier-gid', '60012', '--verifier-home', verifier,
        ])
        self.assertTrue(json.loads(output)['ok'])
        self.assertFalse((protected / 'control.sock').exists())
        self.assertFalse((protected / 'state/goals.sqlite3').exists())
        self.assertEqual(self.fixture.crontab.read_text(), self.fixture.foreign_cron)
        for name in (*GOAL_ASSETS, 'codex_transport.py'):
            target = protected / 'code' / name
            self.assertEqual(target.read_bytes(), (installed / name).read_bytes())
            self.assertFalse(target.is_symlink())
            self.assertEqual(target.stat().st_uid, 0)
            self.assertEqual(target.stat().st_mode & 0o022, 0)
        process = subprocess.Popen([
            '/usr/bin/python3', '-I', str(protected / 'code/goal_service.py'),
            '--config', str(protected / 'config.json'),
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=base, env=self.fixture.env)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(5), 'installed protected service did not become ready')
                ready = process.stdout.readline()
            self.assertTrue(json.loads(ready)['ready'])
            response = self.fixture.run_cli([
                '/usr/bin/python3', '-I', protected / 'code/goal_client.py',
                '--socket', protected / 'control.sock', 'request',
                json.dumps({'op': 'inspect', 'id': 'absent'}),
            ], expected=1)
            self.assertEqual(json.loads(response)['error'], 'unknown goal')
            self.assertTrue((protected / 'state/goals.sqlite3').is_file())
            self.assertEqual(self.fixture.crontab.read_text(), self.fixture.foreign_cron)
        finally:
            process.terminate()
            process.wait(timeout=5)
            errors = process.stderr.read()
            process.stdout.close()
            process.stderr.close()
            with self.fixture.log.open('a') as log:
                log.write(errors)
            self.assertEqual(errors, '')

    @unittest.skipUnless(os.geteuid() == 0, 'isolated protected setup requires root')
    def test_copy_install_supports_isolated_root_setup(self):
        self.protected_setup('copy')

    @unittest.skipUnless(os.geteuid() == 0, 'isolated protected setup requires root')
    def test_symlink_install_supports_isolated_root_setup(self):
        self.protected_setup('symlink')


if __name__ == '__main__':
    unittest.main()
