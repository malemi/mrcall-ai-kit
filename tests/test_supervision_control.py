import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.supervision.control import intervene, intervention_status, session_read
from shared.supervision.scheduler import Scheduler
from shared.supervision.store import Store, StoreError


class Native:
    def __init__(self):
        self.calls = []
        self.parents = {}
        self.uncertain = False
        self.reconciled = 'delivered'

    def metadata(self, session):
        self.calls.append(('metadata', session))
        return {'id': session, 'parentThreadId': self.parents.get(session)}

    def read(self, session, **kwargs):
        self.calls.append(('read', session, kwargs))
        return {'thread': {'id': session}, 'turns': [], 'next_cursor': 'older', 'reverse_cursor': 'newer', **kwargs}

    def send(self, session, event, instruction, allow_busy=False):
        self.calls.append(('send', session, event, instruction, allow_busy))
        if self.uncertain:
            raise OSError('accepted but acknowledgement lost')
        return {'status': 'delivered', 'native_submission_id': 'submission'}

    def reconcile(self, session, event):
        self.calls.append(('reconcile', session, event))
        return {'status': self.reconciled}


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'state')
        self.addCleanup(lambda: self.store.close())
        self.native = Native()
        self.target = str(uuid.uuid4())
        self.store.bind({'id': 'supervisor', 'session_id': str(uuid.uuid4()), 'target_ids': [self.target]})
        self.store.create_task({'id': 'task', 'supervisor_id': 'supervisor', 'target_ids': [self.target], 'instruction': 'check',
                               'scope': 'fixture', 'acceptance': ['evidence'], 'limits': {'provenance': 'fixture'}, 'next_run_at': 0})
        Scheduler(self.store, now=1)._claim()
        self.store.conn.execute("UPDATE executions SET status='delivered'")
        execution = self.store.status()['executions'][0]
        self.data = {'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': self.target,
                     'event_id': str(uuid.uuid4()), 'instruction': 'Return to the requested result', 'reason': 'Unmet acceptance'}

    def test_uncertain_delivery_reconciles_once_never_resends(self):
        self.native.uncertain = True
        self.native.reconciled = 'absent'
        self.assertEqual(intervene(self.store, self.native, self.data)['status'], 'uncertain')
        self.store.close()
        self.store = Store(Path(self.temp.name) / 'state')
        self.assertEqual(intervene(self.store, self.native, self.data)['status'], 'uncertain')
        self.assertTrue(intervene(self.store, self.native, self.data)['replayed'])
        self.assertEqual([call[0] for call in self.native.calls], ['send', 'reconcile'])

    def test_crashed_intent_is_reconciled_without_send(self):
        intent = {key: self.data[key] for key in ('execution_id', 'generation', 'session_id', 'instruction', 'reason')}
        with self.store.transaction():
            self.store.audit('intervention-intent', self.data['event_id'], intent, 'supervisor')
        self.assertEqual(intervention_status(self.store, self.data['event_id'])['result']['status'], 'uncertain')
        self.assertEqual(intervene(self.store, self.native, self.data)['status'], 'delivered')
        self.assertEqual([call[0] for call in self.native.calls], ['reconcile'])

    def test_descendant_read_and_pagination(self):
        worker = str(uuid.uuid4())
        self.native.parents[worker] = self.target
        result = session_read(self.store, self.native, self.data | {'session_id': worker, 'cursor': 'anchor', 'sort_direction': 'asc'})
        self.assertEqual(result['authorized_root'], self.target)
        self.assertEqual(result['reverse_cursor'], 'newer')
        self.assertEqual(self.native.calls[-1], ('read', worker, {'cursor': 'anchor', 'sort_direction': 'asc'}))
        with self.assertRaises(StoreError):
            intervene(self.store, self.native, self.data | {'session_id': worker})
        with self.assertRaises(StoreError):
            session_read(self.store, self.native, self.data | {'session_id': str(uuid.uuid4())})

    def test_real_cli_status_retains_uncertainty_after_detach(self):
        self.native.uncertain = True
        intervene(self.store, self.native, self.data)
        self.store.detach({'id': 'supervisor', 'reason': 'operator detached'})
        process = subprocess.run([sys.executable, str(ROOT / 'shared/supervision/cli.py'), '--state-dir', str(self.store.root),
                                  'intervention-status', '--id', self.data['event_id']], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        result = json.loads(process.stdout)['result']
        self.assertEqual(result['result']['status'], 'uncertain')
        self.assertEqual(len(result['history']), 2)
        self.assertEqual(result['intent']['instruction'], self.data['instruction'])
        self.assertEqual(len(self.native.calls), 1)

    def test_real_cli_rejects_stale_execution_without_native_access(self):
        self.store.task_state({'id': 'task', 'revision': 1, 'action': 'pause', 'reason': 'operator pause'})
        for lifecycle in ('paused', 'detached'):
            if lifecycle == 'detached':
                self.store.task_state({'id': 'task', 'revision': 2, 'action': 'resume', 'reason': 'new assessment'})
                Scheduler(self.store, now=1000)._claim()
                execution = self.store.status()['executions'][-1]
                self.store.conn.execute("UPDATE executions SET status='delivered' WHERE id=?", (execution['id'],))
                self.data.update(execution_id=execution['id'], generation=execution['generation'])
                # Establish valid authority before detach; pause must not mask it.
                session_read(self.store, self.native, self.data)
                self.store.detach({'id': 'supervisor', 'reason': 'operator detached'})
            for command in ('intervene', 'session-read'):
                with self.subTest(lifecycle=lifecycle, command=command):
                    result = subprocess.run([sys.executable, str(ROOT / 'shared/supervision/cli.py'), '--state-dir', str(self.store.root),
                                             '--codex-path', '/definitely/missing/codex', command], input=json.dumps(self.data), capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn('stale or inactive', json.loads(result.stdout)['error'])

    def test_real_cli_intervention_and_read_through_native_protocol(self):
        from test_supervision_transport import TransportTests
        fixture = TransportTests()
        fixture.setUp()
        try:
            fixture.thread_id = self.target
            fixture.mode = 'active'
            # Cross the health checkpoint before using the real CLI. This must
            # retain authority without waking a duplicate assessment.
            self.store.conn.execute("UPDATE executions SET lease_until=2")
            self.store.conn.execute("UPDATE outbox SET status='delivered'")
            Scheduler(self.store, self.native, now=1000).tick()
            execution = self.store.status()['executions'][0]
            self.assertEqual(execution['status'], 'unhealthy')
            self.assertEqual(self.store.task('task')['status'], 'active')
            self.assertEqual(self.native.calls, [])
            with fixture.server():
                executable = Path(self.temp.name) / 'codex-fixture'
                executable.write_text('#!' + sys.executable + '\nimport json\nprint(json.dumps(' + repr({'status': 'running', 'socketPath': str(fixture.root / 'control.sock')}) + '))\n')
                executable.chmod(0o700)
                def cli(command, data=None, ok=True):
                    process = subprocess.run([sys.executable, str(ROOT / 'shared/supervision/cli.py'), '--state-dir', str(self.store.root),
                                              '--codex-path', str(executable), command], input=json.dumps(self.data if data is None else data), capture_output=True, text=True)
                    self.assertEqual(process.returncode, 0 if ok else 1, process.stdout + process.stderr)
                    return json.loads(process.stdout)['result' if ok else 'error']
                delivered = cli('intervene')
                self.assertEqual(delivered['status'], 'delivered')
                self.assertFalse(delivered['action_completed'])
                self.assertTrue(cli('intervene')['replayed'])
                self.assertIn('different intervention', cli('intervene', self.data | {'instruction': 'Different command'}, ok=False))
                self.assertEqual(len(fixture.accepted), 1)
                self.assertEqual(fixture.accepted[0]['threadId'], self.target)
                read = cli('session-read')
                self.assertEqual(read['authorized_root'], self.target)
                self.assertEqual(read['thread']['id'], self.target)
                self.assertFalse(read['private_reasoning_included'])
                result = cli('execution-result', {'id': execution['id'], 'generation': execution['generation'],
                                                  'outcome': 'completed', 'summary': 'Late assessment verified',
                                                  'evidence': ['protocol fixture'], 'remaining': ['Underlying work']})
                self.assertFalse(result['task_state_changed'])
                self.assertEqual(cli('status')['tasks'][0]['status'], 'active')
                checkpoint = self.store.conn.execute("SELECT details FROM audit WHERE action='assessment-overdue'").fetchone()
                self.assertTrue(json.loads(checkpoint[0])['authority_retained'])
        finally:
            fixture.tearDown()


if __name__ == '__main__':
    unittest.main()
