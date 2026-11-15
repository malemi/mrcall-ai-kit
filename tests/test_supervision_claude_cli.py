import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

from test_supervision_claude_transport import ClaudeFixture

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.supervision.store import Store
from shared.supervision.scheduler import Scheduler
from supervision_fixture import isolate


class ClaudeCLITests(unittest.TestCase):
    def setUp(self):
        isolate(self)
        self.fixture = ClaudeFixture()
        self.addCleanup(self.fixture.close)
        self.state = self.fixture.root / 'state'
        self.cron = self.fixture.root / 'crontab-data'
        self.cron.write_text('5 * * * * /foreign/job\n')
        binary = self.fixture.root / 'crontab'
        binary.write_text('#!' + sys.executable + '\nimport pathlib,sys\np=pathlib.Path(' + repr(str(self.cron)) + ')\nif sys.argv[1]=="-l": print(p.read_text(),end="")\nelse: p.write_text(sys.stdin.read())\n')
        binary.chmod(0o700)
        self.env = dict(os.environ, CLAUDE_CONFIG_DIR=str(self.fixture.config_root),
                        PATH=str(self.fixture.root) + os.pathsep + os.environ['PATH'])
        self.log = self.fixture.root / 'cli.log'

    def cli(self, command, data=None, ident=None, ok=True):
        argv = [sys.executable, os.environ.get('AI_KIT_SUPERVISION_TEST_CLI', str(ROOT / 'shared/supervision/cli.py')), '--state-dir', str(self.state),
                '--claude-path', str(self.fixture.executable), '--codex-path', '/missing/codex', command]
        if ident:
            argv += ['--id', ident]
        result = subprocess.run(argv, input=json.dumps(data) if data is not None else None,
                                env=self.env, capture_output=True, text=True)
        with self.log.open('a') as stream:
            stream.write(json.dumps({'argv': argv, 'exit': result.returncode}) + '\n' + result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0 if ok else 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        return payload['result'] if ok else payload['error']

    def task(self, binding='s', operator=None, targets=None, mode='observation'):
        return self.cli('task-create', {'id': 'task-' + binding, 'supervisor_id': binding, 'mode': mode, 'operator_session_id': operator,
                        'target_ids': targets or [], 'instruction': 'Verify delivery', 'scope': 'fixture',
                        'acceptance': ['actual result']})

    def test_activation_mixed_runtime_dispatch_and_late_reconciliation_without_resend(self):
        fixture = self.fixture
        self.cli('activate', {'id': 's', 'runtime': 'claude', 'session_id': fixture.thread_id})
        self.assertIn('--claude-path', self.cron.read_text())
        self.assertIn('CLAUDE_CONFIG_DIR=', self.cron.read_text())
        self.assertTrue(self.cron.read_text().startswith('5 * * * * /foreign/job\n'))
        self.task(operator=fixture.thread_id)
        other_session = str(uuid.uuid4())
        self.cli('bind', {'id': 'other', 'runtime': 'codex', 'session_id': other_session})
        self.task('other', operator=other_session)
        self.cli('tick')
        self.assertTrue(fixture.received.wait(2))
        status = self.cli('status')
        execution = next(x for x in status['executions'] if x['supervisor_id'] == 's')
        self.assertEqual(execution['status'], 'uncertain')
        self.assertEqual(next(x for x in status['executions'] if x['supervisor_id'] == 'other')['status'], 'not-delivered')
        self.assertEqual(self.cli('execution-reconcile', ident=execution['id'])['status'], 'uncertain')
        fixture.receipt(fixture.frames[0])
        confirmed = self.cli('execution-reconcile', ident=execution['id'])
        self.assertEqual(confirmed['status'], 'delivered')
        self.cli('execution-result', {'id': execution['id'], 'generation': execution['generation'],
                                     'outcome': 'completed', 'summary': 'Assessment complete',
                                     'evidence': ['fixture history'], 'remaining': ['Underlying task']})
        self.assertEqual(len(fixture.frames), 1)
        self.assertEqual(self.cli('status', ident='task-s')['status'], 'active')
        store = Store(self.state)
        try:
            actions = [r[0] for r in store.conn.execute('SELECT action FROM audit WHERE entity_id=?', (execution['id'],))]
            self.assertIn('delivery-uncertain', actions)
            self.assertIn('delivery-delivered', actions)
        finally:
            store.close()
        self.assertIn('identity cannot change', self.cli('bind', {'id': 's', 'runtime': 'codex', 'session_id': fixture.thread_id}, ok=False))
        self.cli('detach', {'id': 's', 'reason': 'operator detached'})
        self.assertIn('inactive', self.cli('execution-reconcile', ident=execution['id'], ok=False))
        self.cli('deactivate')
        self.assertEqual(self.cron.read_text(), '5 * * * * /foreign/job\n')

    def test_late_scheduler_observation_cannot_undo_cli_completion(self):
        fixture = self.fixture
        self.cli('bind', {'id': 's', 'runtime': 'claude', 'session_id': fixture.thread_id})
        self.task(operator=fixture.thread_id)
        self.cli('tick')
        self.assertTrue(fixture.received.wait(2))
        execution = self.cli('status')['executions'][0]
        fixture.receipt(fixture.frames[0])
        case = self
        class RacingRead:
            def reconcile(self, session, event, **_):
                case.cli('execution-reconcile', ident=execution['id'])
                case.cli('execution-result', {'id': execution['id'], 'generation': execution['generation'],
                         'outcome': 'completed', 'summary': 'Finished during scheduler read',
                         'evidence': ['peer history'], 'remaining': []})
                return {'status': 'delivered'}
        store = Store(self.state)
        try:
            Scheduler(store, RacingRead()).tick()
        finally:
            store.close()
        after = self.cli('execution-read', ident=execution['id'])
        self.assertEqual(after['status'], 'completed')
        self.assertEqual(after['result']['summary'], 'Finished during scheduler read')
        self.assertEqual(len(fixture.frames), 1)

    @unittest.skip('the Claude adapter does not observe sessions yet')
    def test_intervention_late_history_recheck_and_pause_fence(self):
        # intervene requires a completion-mode task, and a completion task needs a readable spend
        # baseline for every binding and target session; the Claude adapter has no observe() yet,
        # so a Claude-runtime completion task cannot be created in this milestone.
        pass


if __name__ == '__main__':
    unittest.main()
