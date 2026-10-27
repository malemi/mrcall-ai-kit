import fcntl
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.supervision.store import Store, StoreError
from shared.supervision.scheduler import Scheduler, execution_read, transport_read


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.busy = False
        self.offline = False
        self.uncertain = False
        self.reconciled = 'absent'

    def metadata(self, thread_id):
        self.calls.append(('metadata', thread_id))
        if self.offline:
            raise OSError('offline')
        return {'id': thread_id, 'status': {'type': 'active' if self.busy else 'idle'}, 'canAcceptDirectInput': True}

    def send(self, thread_id, event_id, text):
        self.calls.append(('send', event_id))
        if self.uncertain:
            raise OSError('lost acknowledgement')
        return {'status': 'delivered', 'native_submission_id': 'native'}

    def reconcile(self, thread_id, event_id):
        self.calls.append(('reconcile', event_id))
        return {'status': self.reconciled}

    def read(self, thread_id, cursor=None):
        self.calls.append(('read', thread_id))
        return {'thread_id': thread_id, 'cursor': cursor}


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'state')
        self.native = FakeTransport()
        self.session = str(uuid.uuid4())
        self.store.bind({'id': 's', 'session_id': self.session})

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def task(self, name='t', **kwargs):
        return self.store.create_task({'id': name, 'supervisor_id': 's', 'instruction': 'inspect', 'scope': 'none', 'acceptance': ['evidence'], 'limits': {'provenance': 'test'}, 'next_run_at': 100, 'interval_seconds': 600, **kwargs})

    def tick(self, now=100):
        return Scheduler(self.store, self.native, now=now).tick()

    def result(self):
        row = self.store.conn.execute('SELECT * FROM executions ORDER BY started_at DESC').fetchone()
        return self.store.execution_result({'id': row['id'], 'generation': row['generation'], 'outcome': 'completed', 'summary': 'checked', 'evidence': ['fixture']})

    def test_empty_real_cli_and_lock(self):
        cli = Path(__file__).resolve().parents[1] / 'shared/supervision/cli.py'
        result = subprocess.run([sys.executable, str(cli), '--state-dir', str(self.store.root), 'tick'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(json.loads(result.stdout)['result']['locked'])
        with open(self.store.root / 'tick.lock', 'r') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertTrue(self.tick()['locked'])
        self.assertEqual(self.native.calls, [])

    def test_real_cli_tick_through_native_rpc_fixture(self):
        from test_supervision_transport import TransportTests
        fixture = TransportTests()
        fixture.setUp()
        try:
            fixture.thread_id = self.session
            self.task()
            cli = Path(__file__).resolve().parents[1] / 'shared/supervision/cli.py'
            with fixture.server():
                executable = Path(self.tmp.name) / 'codex-fixture'
                executable.write_text('#!' + sys.executable + '\nimport json\nprint(json.dumps(' + repr({'status': 'running', 'socketPath': str(fixture.root / 'control.sock')}) + '))\n')
                executable.chmod(0o700)
                result = subprocess.run([sys.executable, str(cli), '--state-dir', str(self.store.root), '--codex-path', str(executable), 'tick'], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(len(fixture.accepted), 1)
                event = self.store.status()['outbox'][0]
                self.assertEqual(event['status'], 'delivered')
                execution = self.store.status()['executions'][0]
                self.assertFalse(json.loads(execution['result'])['delivery']['assessment_completed'])
                self.assertEqual(fixture.accepted[0]['clientUserMessageId'], event['id'])
        finally:
            fixture.tearDown()

    def test_coalesce_clock_changes_and_callback(self):
        self.task()
        self.tick(10000)
        self.assertEqual(self.store.task('t')['next_run_at'], 10600)
        self.tick(50)
        self.assertEqual(len([x for x in self.native.calls if x[0] == 'send']), 1)
        self.result()
        with self.assertRaises(StoreError):
            self.result()
        self.tick(10600)
        self.assertEqual(len([x for x in self.native.calls if x[0] == 'send']), 2)
        self.assertEqual(self.store.task('t')['status'], 'active')

    def test_busy_dispatch_deadline_survives_restart_then_idle(self):
        self.task()
        self.task('second')
        self.native.busy = True
        self.tick(100)
        original = self.store.status()['executions'][0]
        self.assertEqual(len(self.store.status()['executions']), 1)
        self.assertEqual(original['lease_until'], 280)
        self.assertEqual(self.store.status()['health']['attention'], [])
        root = self.store.root
        self.store.close()
        self.store = Store(root)
        self.tick(281)
        attention = self.store.status()['health']['attention']
        self.assertEqual(len(attention), 1)
        self.assertEqual(attention[0]['status'], 'pending')
        self.assertTrue(json.loads(attention[0]['result'])['dispatch_wait_overdue'])
        self.tick(10000)
        self.assertEqual(self.store.conn.execute("SELECT count(*) FROM audit WHERE action='dispatch-wait-overdue'").fetchone()[0], 1)
        self.assertFalse(any(call[0] == 'send' for call in self.native.calls))
        self.native.busy = False
        self.tick(10001)
        execution = self.store.status()['executions'][0]
        self.assertEqual(execution['id'], original['id'])
        self.assertEqual(execution['status'], 'delivered')
        self.assertEqual(execution['lease_until'], 10181)
        self.assertEqual(self.store.status()['health']['attention'], [])
        self.assertEqual(len([call for call in self.native.calls if call[0] == 'send']), 1)
        self.assertEqual(len(self.store.status()['executions']), 1)
        self.result()
        self.tick(10002)
        executions = self.store.status()['executions']
        self.assertEqual(len(executions), 2)
        self.assertEqual({row['task_id'] for row in executions}, {'t', 'second'})

    def test_detached_transport_read_makes_no_native_call(self):
        self.store.detach({'id': 's', 'reason': 'operator detached'})
        with self.assertRaisesRegex(StoreError, 'detached'):
            transport_read(self.store, self.native, {'supervisor_id': 's', 'session_id': self.session})
        self.assertEqual(self.native.calls, [])

    def test_status_reports_scheduler_liveness_separately(self):
        health = self.store.status()['health']['scheduler']
        self.assertEqual(health['state'], 'waiting-first-tick')
        self.assertIsNone(health['last_tick_at'])
        activated = self.store.binding('s')['updated_at']
        with patch('shared.supervision.store.time.time', return_value=activated + 600):
            self.assertEqual(self.store.status()['health']['scheduler']['state'], 'overdue')
        self.tick(100)
        with patch('shared.supervision.store.time.time', return_value=150):
            health = self.store.status()['health']['scheduler']
            self.assertEqual(health['state'], 'active')
            self.assertEqual(health['last_tick_at'], 100)
        with patch('shared.supervision.store.time.time', return_value=281):
            self.assertEqual(self.store.status()['health']['scheduler']['state'], 'overdue')
        self.store.detach({'id': 's', 'reason': 'done'})
        self.assertEqual(self.store.status()['health']['scheduler']['state'], 'dormant')

    def test_retry_bound_and_recovery(self):
        self.task()
        self.native.offline = True
        self.tick()
        self.tick(159)
        self.assertEqual(len(self.native.calls), 1)
        self.tick(160)
        self.tick(220)
        self.assertEqual(len(self.native.calls), 2)
        self.assertEqual(self.store.status()['outbox'][0]['attempts'], 2)

    def test_crash_sending_reconciles_never_resends(self):
        self.task()
        Scheduler(self.store, self.native, now=100)._claim()
        self.store.conn.execute("UPDATE outbox SET status='sending'")
        self.store.conn.execute("UPDATE executions SET status='sending',lease_until=101")
        self.tick(110)
        self.tick(1000)
        self.assertEqual([x[0] for x in self.native.calls], ['reconcile'])
        self.assertEqual(self.store.status()['outbox'][0]['status'], 'uncertain')

    def test_uncertain_and_pause_fences(self):
        self.task()
        self.native.uncertain = True
        self.tick()
        self.tick(1000)
        self.assertEqual(len([x for x in self.native.calls if x[0] == 'send']), 1)
        self.store.task_state({'id': 't', 'revision': 1, 'action': 'pause', 'reason': 'test'})
        self.tick(2000)
        with self.assertRaises(StoreError):
            self.result()
        self.assertEqual(self.store.status()['outbox'][0]['status'], 'uncertain')

    def test_uncapped_continues_beyond_old_default(self):
        self.task()
        for index in range(102):
            self.tick(100 + index * 600)
            self.result()
        self.assertEqual(len(self.store.status()['executions']), 102)
        self.assertEqual(self.store.task('t')['status'], 'active')
        self.assertFalse(self.store.conn.execute("SELECT 1 FROM audit WHERE action='check-limit'").fetchone())

    def test_persisted_cap_removal_preserves_history_and_fences(self):
        self.task(limits={'provenance': 'legacy operator', 'max_checks': 1})
        self.tick()
        self.result()
        original = self.store.status()['executions'][0]
        root = self.store.root
        self.store.close()
        self.store = Store(root)
        self.tick(700)
        task = self.store.task('t')
        self.assertEqual(task['status'], 'blocked')
        self.assertEqual(task['limits']['max_checks'], 1)
        updated = self.store.update_task({'id': 't', 'revision': task['revision'], 'changes': {'limits': dict(task['limits'], max_checks=None)}})
        self.assertEqual(updated['status'], 'blocked')
        self.store.task_state({'id': 't', 'revision': updated['revision'], 'action': 'resume', 'reason': 'Operator removed cap'})
        self.tick(1300)
        self.assertEqual(self.store.status()['executions'][0], original)
        self.assertEqual(len(self.store.status()['executions']), 2)
        running = self.store.status()['executions'][1]
        task = self.store.task('t')
        self.store.update_task({'id': 't', 'revision': task['revision'], 'changes': {'limits': dict(task['limits'], max_checks=None)}})
        with self.assertRaisesRegex(StoreError, 'stale execution'):
            self.store.execution_result({'id': running['id'], 'generation': running['generation'], 'outcome': 'completed', 'summary': 'Late', 'evidence': ['fixture']})
        self.assertEqual(self.store.status()['executions'][1]['status'], 'invalidated')

    def test_failure_survives_recovery_checkpoint_and_success(self):
        self.task()
        self.native.offline = True
        self.tick(100)
        failure = self.store.conn.execute("SELECT * FROM audit WHERE action='delivery-not-delivered'").fetchone()
        event = self.store.status()['outbox'][0]['id']
        self.store.add_memory({'id': 'failure', 'supervisor_id': 's', 'task_id': 't', 'kind': 'failure',
                               'content': 'Native delivery offline; cause unresolved', 'source': 'failed-delivery'})
        self.native.offline = False
        self.tick(160)
        self.assertIn(('send', event), self.native.calls)
        delivery = json.loads(self.store.status()['executions'][0]['result'])
        self.tick(341)
        execution = self.store.status()['executions'][0]
        checkpoint = json.loads(execution['result'])
        self.assertTrue(checkpoint['assessment_checkpoint_overdue'])
        self.assertEqual(checkpoint['previous_result'], delivery)
        self.tick(10000)
        self.assertEqual(len(self.store.status()['executions']), 1)
        self.result()
        self.assertEqual(dict(self.store.conn.execute('SELECT * FROM audit WHERE sequence=?', (failure['sequence'],)).fetchone()), dict(failure))
        checkpoint_audit = self.store.conn.execute("SELECT details FROM audit WHERE action='assessment-overdue'").fetchone()
        self.assertTrue(json.loads(checkpoint_audit[0])['authority_retained'])
        self.store.add_memory({'id': 'success', 'supervisor_id': 's', 'task_id': 't', 'kind': 'fact',
                               'content': 'Later assessment completed', 'source': 'assessment-result'})
        root = self.store.root
        self.store.close()
        self.store = Store(root)
        self.tick(10001)
        executions = self.store.status()['executions']
        self.assertEqual(len(executions), 2)
        restored = execution_read(self.store, executions[-1]['id'])
        self.assertEqual([entry['id'] for entry in restored['memory']], ['failure', 'success'])
        self.assertEqual(restored['memory'][0]['content'], 'Native delivery offline; cause unresolved')

    def test_max_checks_oneshot_alignment_and_scope(self):
        self.task(interval_seconds=None)
        self.tick()
        self.result()
        self.tick(10000)
        self.assertEqual(len(self.store.status()['executions']), 1)
        self.task('aligned', schedule_mode='utc-aligned', limits={'provenance': 'test', 'max_checks': 1})
        self.tick(10001)
        self.assertEqual(self.store.task('aligned')['next_run_at'], 10200)
        row = self.store.conn.execute("SELECT * FROM executions WHERE task_id='aligned'").fetchone()
        restored = execution_read(self.store, row['id'])
        self.assertEqual(restored['task']['id'], 'aligned')
        self.result()
        self.tick(10200)
        self.assertEqual(self.store.task('aligned')['status'], 'blocked')
        with self.assertRaises(StoreError):
            transport_read(self.store, self.native, {'supervisor_id': 's', 'session_id': str(uuid.uuid4())})


if __name__ == '__main__':
    unittest.main()
