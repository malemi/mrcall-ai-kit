import concurrent.futures
import json
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CLI = ROOT / 'shared/supervision/cli.py'
from supervision_fixture import isolate


class SupervisionStoreCLI(unittest.TestCase):
    def setUp(self):
        self.temp = isolate(self)
        self.state = self.temp / 'state'
        self.supervisor = str(uuid.uuid4())
        self.target = str(uuid.uuid4())

    def cli(self, command, data=None, ok=True, extra=()):
        run = subprocess.run([sys.executable, str(CLI), '--state-dir', str(self.state), command, *extra],
                             input=json.dumps(data) if data is not None else '', capture_output=True, text=True)
        result = json.loads(run.stdout)
        self.assertEqual(run.returncode, 0 if ok else 1, run.stdout + run.stderr)
        self.assertEqual(result['ok'], ok)
        return result.get('result') if ok else result['error']

    def bind(self):
        return self.cli('bind', {'id': 'lead', 'session_id': self.supervisor, 'target_ids': [self.target]})

    def create(self, task_id='work', mode='observation', **changes):
        data = {'id': task_id, 'supervisor_id': 'lead', 'mode': mode, 'operator_session_id': self.supervisor,
                'instruction': 'Verify delivery evidence', 'acceptance': ['Actual result verified'],
                'scope': 'Test repository only'}
        data.update(changes)
        return self.cli('task-create', data)

    def test_real_cli_task_lifecycle_and_restart(self):
        self.bind()
        task = self.create()
        self.assertEqual(task['interval_seconds'], 600)
        self.assertIsNone(task['limits']['max_checks'])
        self.assertEqual(task['limits']['parameter_provenance']['heartbeat_seconds'], 'supervisor-default')
        paused = self.cli('task-state', {'id': 'work', 'revision': 1, 'action': 'pause', 'reason': 'Operator pause'})
        self.assertEqual(paused['status'], 'paused')
        resumed = self.cli('task-state', {'id': 'work', 'revision': 2, 'action': 'resume', 'reason': 'Operator resume'})
        self.assertEqual(resumed['generation'], 3)
        self.assertIn('requires evidence', self.cli('task-state', {'id': 'work', 'revision': 3, 'action': 'complete', 'reason': 'Done'}, ok=False))
        done = self.cli('task-state', {'id': 'work', 'revision': 3, 'action': 'complete', 'reason': 'Verified', 'evidence': ['receipt.json'], 'remaining': []})
        self.assertEqual(done['status'], 'completed')
        self.assertEqual(self.cli('status', extra=('--id', 'work'))['evidence'], ['receipt.json'])
        self.assertIn('terminal', self.cli('task-state', {'id': 'work', 'revision': 4, 'action': 'resume', 'reason': 'Retry'}, ok=False))

    def test_concurrent_updates_allow_one_revision_winner(self):
        self.bind()
        self.create()
        def update(index):
            return subprocess.run([sys.executable, str(CLI), '--state-dir', str(self.state), 'task-update'],
                                  input=json.dumps({'id': 'work', 'revision': 1, 'changes': {'instruction': f'Check {index}'}}), text=True, capture_output=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, [1, 2]))
        self.assertEqual(sorted(r.returncode for r in results), [0, 1])
        self.assertEqual(self.cli('status', extra=('--id', 'work'))['revision'], 2)
        self.assertTrue(any('revision conflict' in r.stdout for r in results))

    def test_memory_supersession_survives_process_restart(self):
        self.bind()
        self.create()
        self.cli('memory-add', {'id': 'old', 'supervisor_id': 'lead', 'task_id': 'work', 'kind': 'hypothesis', 'content': 'Provider timeout suspected', 'source': 'trace:1'})
        self.cli('memory-supersede', {'id': 'new', 'supersedes': 'old', 'supervisor_id': 'lead', 'task_id': 'work', 'kind': 'correction', 'content': 'Operation never attempted', 'source': 'trace:2', 'evidence': ['receipt.json']})
        current = self.cli('memory-query', {'supervisor_id': 'lead', 'task_id': 'work'})
        self.assertEqual([m['id'] for m in current], ['new'])
        history = self.cli('memory-query', {'supervisor_id': 'lead', 'task_id': 'work', 'include_history': True})
        self.assertEqual([m['id'] for m in history], ['old', 'new'])
        self.assertEqual(self.cli('memory-query', {'supervisor_id': 'lead'}), [])
        with sqlite3.connect(self.state / 'state.sqlite3') as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("DELETE FROM memory WHERE id='old'")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute('DELETE FROM audit')

    def test_decision_memory_requires_undo(self):
        self.bind()
        self.create()
        self.assertIn('undo', self.cli('memory-add', {'id': 'd1', 'supervisor_id': 'lead', 'task_id': 'work', 'kind': 'decision',
                                                       'content': 'ignored', 'source': 'test', 'what': 'skipped a step', 'why': 'redundant'}, ok=False))
        self.cli('memory-add', {'id': 'd2', 'supervisor_id': 'lead', 'task_id': 'work', 'kind': 'decision', 'content': 'ignored',
                                'source': 'test', 'what': 'skipped a step', 'why': 'redundant', 'undo': 're-run the step'})

    def test_exact_bindings_and_private_files(self):
        first = self.bind()
        self.assertEqual(self.bind(), first)
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o700)
        for file in self.state.iterdir():
            self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600)
        self.assertIn('exact UUID', self.cli('bind', {'id': 'other', 'session_id': 'newest'}, ok=False))
        task = {'id': 'bad', 'supervisor_id': 'lead', 'mode': 'observation', 'operator_session_id': self.supervisor,
                'target_ids': [str(uuid.uuid4())], 'instruction': 'Check', 'acceptance': ['Done'], 'scope': 'Only target'}
        self.assertIn('outside', self.cli('task-create', task, ok=False))
        self.state.chmod(0o755)
        self.assertIn('unsafe', self.cli('status', ok=False))

    def test_symlink_and_newer_schema_refused(self):
        self.cli('init')
        db = self.state / 'state.sqlite3'
        with sqlite3.connect(db) as conn:
            conn.execute('PRAGMA user_version=99')
        before = db.read_bytes()
        self.assertIn('newer schema', self.cli('status', ok=False))
        self.assertEqual(before, db.read_bytes())
        db.unlink()
        external = self.temp / 'foreign'
        external.write_text('untouched')
        db.symlink_to(external)
        self.assertIn('unsafe', self.cli('init', ok=False))
        self.assertEqual(external.read_text(), 'untouched')

    def test_block_detach_and_stale_execution_results(self):
        self.bind()
        self.create()
        park = {'reason': 'operator-input', 'questions': [{'matter': 'External wait', 'options': ['Wait', 'Stop'], 'recommendation': 'Wait'}],
                'completed': 'Nothing else can proceed', 'cites': []}
        paused = self.cli('task-state', {'id': 'work', 'revision': 1, 'action': 'pause', 'reason': 'External wait'})
        self.assertEqual(paused['status'], 'paused')
        self.cli('task-state', {'id': 'work', 'revision': 2, 'action': 'resume', 'reason': 'Result arrived'})
        self.cli('tick')
        with sqlite3.connect(self.state / 'state.sqlite3') as conn:
            running = conn.execute("SELECT id,generation FROM executions WHERE task_id='work'").fetchone()
        detached = self.cli('detach', {'id': 'lead', 'reason': 'Operator detached'})
        self.assertEqual(detached['status'], 'detached')
        self.assertEqual(self.cli('status', extra=('--id', 'work'))['status'], 'paused')
        attached = self.bind()
        self.assertEqual(attached['status'], 'active')
        self.assertEqual(self.cli('status', extra=('--id', 'work'))['status'], 'paused')
        self.assertIn('stale execution', self.cli('execution-result', {'id': running[0], 'generation': running[1], 'outcome': 'completed', 'summary': 'Late result', 'evidence': ['late']}, ok=False))
        with sqlite3.connect(self.state / 'state.sqlite3') as conn:
            self.assertEqual(conn.execute("SELECT status FROM outbox WHERE execution_id=?", (running[0],)).fetchone()[0], 'cancelled')
            self.assertFalse(json.loads(conn.execute("SELECT details FROM audit WHERE action='detach'").fetchone()[0])['underlying_sessions_cancelled'])

    def test_blocked_metadata_survives_instruction_update_and_restart(self):
        self.bind()
        self.create()
        park = {'reason': 'operator-input', 'questions': [{'matter': 'Awaiting external receipt', 'options': ['Wait', 'Stop'], 'recommendation': 'Wait'}],
                'completed': 'Nothing else can proceed', 'cites': []}
        self.cli('task-state', {'id': 'work', 'revision': 1, 'action': 'block', 'reason': 'Awaiting external receipt',
                                'remaining': ['Verify delivered artifact'], 'evidence': ['failed-check.json'], 'park': park})
        updated = self.cli('task-update', {'id': 'work', 'revision': 2, 'changes': {'instruction': 'Inspect the receipt when available'}})
        self.assertEqual(updated['revision'], 3)
        restored = self.cli('status', extra=('--id', 'work'))
        self.assertEqual(restored['status'], 'blocked')
        self.assertEqual(restored['reason'], 'Awaiting external receipt')
        self.assertEqual(restored['remaining'], ['Verify delivered artifact'])
        self.assertEqual(restored['evidence'], ['failed-check.json'])
        self.assertEqual(restored['instruction'], 'Inspect the receipt when available')
        # A park ends with the operator's words, not with a bare resume.
        refused = self.cli('task-state', {'id': 'work', 'revision': 3, 'action': 'resume', 'reason': 'Receipt arrived'}, ok=False)
        self.assertIn('waits for the operator', refused)
        self.assertEqual(self.cli('status', extra=('--id', 'work'))['status'], 'blocked')


if __name__ == '__main__':
    unittest.main()
