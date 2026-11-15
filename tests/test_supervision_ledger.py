import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import tempfile
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'shared/supervision/ledger.py'

spec = importlib.util.spec_from_file_location('ledger', SOURCE)
ledger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ledger)
Ledger, LedgerError, default_path, KINDS = ledger.Ledger, ledger.LedgerError, ledger.default_path, ledger.KINDS

sys.path.insert(0, str(ROOT))
import shared.supervision.ledger as packaged_ledger
assert packaged_ledger.Ledger is not None and packaged_ledger.LedgerError is not None


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.previous_env = os.environ.get('MRCALL_SUPERVISION_LEDGER')
        os.environ['MRCALL_SUPERVISION_LEDGER'] = str(self.root / 'ledger.sqlite3')

    def tearDown(self):
        if self.previous_env is None:
            os.environ.pop('MRCALL_SUPERVISION_LEDGER', None)
        else:
            os.environ['MRCALL_SUPERVISION_LEDGER'] = self.previous_env
        self.temp.cleanup()

    def test_default_path_follows_environment(self):
        self.assertEqual(default_path(), (self.root / 'ledger.sqlite3').absolute())

    def test_creation_writes_epoch_once_and_reopen_keeps_it(self):
        path = self.root / 'account/ledger.sqlite3'
        first = Ledger(path)
        epoch_one = first.epoch()
        first.close()
        time.sleep(0.01)
        second = Ledger(path)
        self.assertEqual(second.epoch(), epoch_one)
        second.close()

    def test_unsafe_permissions_and_symlink_refused(self):
        path = self.root / 'account/ledger.sqlite3'
        made = Ledger(path)
        made.close()
        os.chmod(path, 0o666)
        with self.assertRaisesRegex(LedgerError, 'unsafe'):
            Ledger(path)
        os.chmod(path, 0o600)

        external = self.root / 'foreign-file'
        external.write_text('untouched')
        path.unlink()
        for suffix in ('-wal', '-shm', '-journal'):
            Path(str(path) + suffix).unlink(missing_ok=True)
        path.symlink_to(external)
        with self.assertRaisesRegex(LedgerError, 'unsafe'):
            Ledger(path)
        self.assertEqual(external.read_text(), 'untouched')

        path.unlink()
        parent_link_target = self.root / 'real-parent'
        parent_link_target.mkdir()
        symlinked_parent = self.root / 'account2'
        symlinked_parent.symlink_to(parent_link_target)
        with self.assertRaisesRegex(LedgerError, 'symlink'):
            Ledger(symlinked_parent / 'ledger.sqlite3')

    def test_record_is_idempotent_and_refuses_second_session(self):
        store = Ledger(self.root / 'ledger.sqlite3')
        client_id = str(uuid.uuid4())
        session = str(uuid.uuid4())
        store.record(client_id, session, 'wake', '/state/root-a', task_id='task-1')
        store.record(client_id, session, 'wake', '/state/root-a', task_id='task-1')
        self.assertEqual(store.known([client_id]), {client_id})
        with self.assertRaises(LedgerError):
            store.record(client_id, str(uuid.uuid4()), 'wake', '/state/root-a', task_id='task-1')
        with self.assertRaises(LedgerError):
            store.record(client_id, session, 'not-a-kind', '/state/root-a')
        store.close()

    def test_known_returns_exactly_recorded_subset(self):
        store = Ledger(self.root / 'ledger.sqlite3')
        recorded = str(uuid.uuid4())
        unrecorded = str(uuid.uuid4())
        store.record(recorded, str(uuid.uuid4()), 'question', '/state/root-a')
        self.assertEqual(store.known([recorded, unrecorded]), {recorded})
        self.assertEqual(store.known([]), set())
        store.close()

    def test_claim_refuses_live_holder_replaces_dead_one_noop_for_same_task(self):
        store = Ledger(self.root / 'ledger.sqlite3')
        session = str(uuid.uuid4())
        store.claim(session, '/state/root-a', 'task-1', alive=lambda sr, tid: True)
        store.claim(session, '/state/root-a', 'task-1', alive=lambda sr, tid: (_ for _ in ()).throw(AssertionError('alive must not be called for a same-task claim')))
        with self.assertRaises(LedgerError):
            store.claim(session, '/state/root-b', 'task-2', alive=lambda sr, tid: True)
        self.assertEqual(store.holder(session)['state_root'], '/state/root-a')
        store.claim(session, '/state/root-b', 'task-2', alive=lambda sr, tid: False)
        holder = store.holder(session)
        self.assertEqual(holder['state_root'], '/state/root-b')
        self.assertEqual(holder['task_id'], 'task-2')
        store.close()

    def test_release_frees_the_target(self):
        store = Ledger(self.root / 'ledger.sqlite3')
        session = str(uuid.uuid4())
        store.claim(session, '/state/root-a', 'task-1', alive=lambda sr, tid: True)
        store.release('/state/root-x', 'task-x')
        self.assertIsNotNone(store.holder(session))
        store.release('/state/root-a', 'task-1')
        self.assertIsNone(store.holder(session))
        store.close()

    def _write_state_root(self, directory, outbox_session, outbox_client_id, intervention_session, intervention_client_id):
        directory.mkdir(parents=True, exist_ok=True)
        db = directory / 'state.sqlite3'
        conn = sqlite3.connect(db)
        conn.execute('CREATE TABLE bindings (id TEXT PRIMARY KEY, session_id TEXT NOT NULL)')
        conn.execute('CREATE TABLE executions (id TEXT PRIMARY KEY, supervisor_id TEXT NOT NULL)')
        conn.execute('CREATE TABLE outbox (id TEXT PRIMARY KEY, execution_id TEXT NOT NULL, client_message_id TEXT NOT NULL, created_at REAL NOT NULL)')
        conn.execute('CREATE TABLE audit (sequence INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, action TEXT NOT NULL, entity_id TEXT NOT NULL, details TEXT NOT NULL)')
        conn.execute("INSERT INTO bindings VALUES ('lead', ?)", (outbox_session,))
        conn.execute("INSERT INTO executions VALUES ('ex1', 'lead')")
        conn.execute("INSERT INTO outbox VALUES ('msg1', 'ex1', ?, ?)", (outbox_client_id, 1700000000.0))
        conn.execute("INSERT INTO audit(at, action, entity_id, details) VALUES (?, 'intervention-intent', ?, ?)",
                     (1700000100.0, intervention_client_id, json.dumps({'session_id': intervention_session})))
        conn.commit()
        conn.close()

    def _write_goals(self, directory, goal_session, goal_client_id):
        directory.mkdir(parents=True, exist_ok=True)
        db = directory / 'goals.sqlite3'
        conn = sqlite3.connect(db)
        conn.execute('CREATE TABLE outbox (id TEXT PRIMARY KEY, document TEXT NOT NULL)')
        conn.execute('INSERT INTO outbox VALUES (?, ?)', (goal_client_id, json.dumps({'session_id': goal_session})))
        conn.commit()
        conn.close()

    def test_backfill_inserts_reports_unreadable_idempotent_and_untouched(self):
        base = self.root / 'state-base'
        base.mkdir()
        wake_session, wake_client = str(uuid.uuid4()), str(uuid.uuid4())
        intervention_session, intervention_client = str(uuid.uuid4()), str(uuid.uuid4())
        self._write_state_root(base / 'root1', wake_session, wake_client, intervention_session, intervention_client)
        (base / 'root2').mkdir()
        (base / 'root2' / 'state.sqlite3').write_bytes(b'not a sqlite database')
        goal_session, goal_client = str(uuid.uuid4()), str(uuid.uuid4())
        self._write_goals(base / 'goals/state', goal_session, goal_client)

        hash_root1 = sha256(base / 'root1/state.sqlite3')
        hash_root2 = sha256(base / 'root2/state.sqlite3')
        hash_goals = sha256(base / 'goals/state/goals.sqlite3')

        store = Ledger(self.root / 'ledger.sqlite3')
        first = store.backfill(base)
        self.assertEqual(first['roots'], 2)
        self.assertEqual(first['inserted'], 3)
        self.assertEqual(first['present'], 0)
        self.assertEqual(first['unreadable'], [str(base / 'root2/state.sqlite3')])
        self.assertEqual(store.known([wake_client, intervention_client, goal_client]), {wake_client, intervention_client, goal_client})

        rows = {r['client_id']: r for r in store.conn.execute('SELECT client_id, session_id, kind, state_root, at FROM messages')}
        self.assertEqual(rows[wake_client]['session_id'], wake_session)
        self.assertEqual(rows[wake_client]['kind'], 'backfill')
        self.assertEqual(rows[wake_client]['state_root'], str(base / 'root1'))
        self.assertEqual(rows[wake_client]['at'], 1700000000.0)
        self.assertEqual(rows[intervention_client]['session_id'], intervention_session)
        self.assertEqual(rows[intervention_client]['at'], 1700000100.0)
        self.assertEqual(rows[goal_client]['session_id'], goal_session)
        self.assertEqual(rows[goal_client]['state_root'], str(base / 'goals'))

        second = store.backfill(base)
        self.assertEqual(second['roots'], 2)
        self.assertEqual(second['inserted'], 0)
        self.assertEqual(second['present'], 3)
        self.assertEqual(second['unreadable'], [str(base / 'root2/state.sqlite3')])
        store.close()

        self.assertEqual(sha256(base / 'root1/state.sqlite3'), hash_root1)
        self.assertEqual(sha256(base / 'root2/state.sqlite3'), hash_root2)
        self.assertEqual(sha256(base / 'goals/state/goals.sqlite3'), hash_goals)


if __name__ == '__main__':
    unittest.main()
