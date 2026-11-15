import contextlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import time


KINDS = ('wake', 'intervention', 'question', 'notice', 'review', 'interrupt', 'goal', 'backfill')


class LedgerError(ValueError):
    pass


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise LedgerError(f'{name} must be a nonempty string')
    return value


def default_path():
    env = os.environ.get('MRCALL_SUPERVISION_LEDGER')
    if env:
        return Path(env).absolute()
    base = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))
    # Its own private directory: the account's state directory is shared with other kit state and need not be private.
    return (base / 'mrcall-ai-kit/ledger/ledger.sqlite3').absolute()


class Ledger:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.is_absolute():
            raise LedgerError('ledger path must be absolute; pass an absolute path')
        parent = self.path.parent
        for part in [parent, *parent.parents]:
            if part.is_symlink():
                raise LedgerError(f'symlink ledger path refused: {part}')
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._private(parent, directory=True)
        for suffix in ('', '-wal', '-shm', '-journal'):
            p = Path(str(self.path) + suffix)
            if p.exists() or p.is_symlink():
                self._private(p)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        self._private(self.path)
        self.conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA busy_timeout=10000')
        try:
            with self._transaction():
                self._schema()
        except BaseException:
            self.conn.close()
            raise

    @staticmethod
    def _private(path, directory=False):
        info = path.lstat()
        wanted = stat.S_ISDIR if directory else stat.S_ISREG
        if not wanted(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise LedgerError(f'unsafe ownership, type or permissions: {path}')
        if not directory and info.st_nlink != 1:
            raise LedgerError(f'hard-linked ledger file refused: {path}')

    def _schema(self):
        self.conn.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        self.conn.execute('CREATE TABLE IF NOT EXISTS messages (client_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, '
                           'kind TEXT NOT NULL, state_root TEXT NOT NULL, task_id TEXT, at REAL NOT NULL)')
        self.conn.execute('CREATE TABLE IF NOT EXISTS claims (session_id TEXT PRIMARY KEY, state_root TEXT NOT NULL, '
                           'task_id TEXT NOT NULL, at REAL NOT NULL)')
        self.conn.execute('INSERT OR IGNORE INTO meta(key,value) VALUES(?,?)', ('epoch', json.dumps(time.time(), allow_nan=False)))

    @contextlib.contextmanager
    def _transaction(self):
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            yield self.conn
            self.conn.execute('COMMIT')
        except BaseException:
            self.conn.execute('ROLLBACK')
            raise

    def epoch(self):
        row = self.conn.execute("SELECT value FROM meta WHERE key='epoch'").fetchone()
        return json.loads(row['value'])

    def record(self, client_id, session_id, kind, state_root, task_id=None, at=None):
        client_id = _text(client_id, 'client_id')
        session_id = _text(session_id, 'session_id')
        if kind not in KINDS:
            raise LedgerError(f'kind must be one of {KINDS}; got {kind!r}')
        state_root = _text(state_root, 'state_root')
        if task_id is not None:
            _text(task_id, 'task_id')
        at = time.time() if at is None else float(at)
        with self._transaction():
            row = self.conn.execute('SELECT session_id FROM messages WHERE client_id=?', (client_id,)).fetchone()
            if row is not None:
                if row['session_id'] != session_id:
                    raise LedgerError(f'client id {client_id} is already recorded for session {row["session_id"]}; use a distinct client id')
                return
            self.conn.execute('INSERT INTO messages VALUES(?,?,?,?,?,?)', (client_id, session_id, kind, state_root, task_id, at))

    def known(self, client_ids):
        ids = list(client_ids)
        if not ids:
            return set()
        placeholders = ','.join('?' * len(ids))
        rows = self.conn.execute(f'SELECT client_id FROM messages WHERE client_id IN ({placeholders})', ids).fetchall()
        return {row['client_id'] for row in rows}

    def claim(self, session_id, state_root, task_id, alive):
        session_id = _text(session_id, 'session_id')
        state_root = _text(state_root, 'state_root')
        task_id = _text(task_id, 'task_id')
        with self._transaction():
            row = self.conn.execute('SELECT state_root, task_id FROM claims WHERE session_id=?', (session_id,)).fetchone()
            if row is None:
                self.conn.execute('INSERT INTO claims VALUES(?,?,?,?)', (session_id, state_root, task_id, time.time()))
                return
            if row['state_root'] == state_root and row['task_id'] == task_id:
                return
            if alive(row['state_root'], row['task_id']):
                raise LedgerError(f'session {session_id} is held by task {row["task_id"]} of state root {row["state_root"]}; release it first')
            self.conn.execute('UPDATE claims SET state_root=?,task_id=?,at=? WHERE session_id=?', (state_root, task_id, time.time(), session_id))

    def release(self, state_root, task_id):
        state_root = _text(state_root, 'state_root')
        task_id = _text(task_id, 'task_id')
        with self._transaction():
            self.conn.execute('DELETE FROM claims WHERE state_root=? AND task_id=?', (state_root, task_id))

    def holder(self, session_id):
        session_id = _text(session_id, 'session_id')
        row = self.conn.execute('SELECT session_id, state_root, task_id, at FROM claims WHERE session_id=?', (session_id,)).fetchone()
        return dict(row) if row is not None else None

    def _read_state_root(self, db_path):
        rows = []
        conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True, timeout=10)
        try:
            for client_id, created_at, session_id in conn.execute(
                    'SELECT o.client_message_id, o.created_at, b.session_id FROM outbox o '
                    'JOIN executions e ON o.execution_id = e.id JOIN bindings b ON e.supervisor_id = b.id'):
                rows.append((client_id, session_id, created_at))
            for entity_id, at, details in conn.execute(
                    "SELECT entity_id, at, details FROM audit WHERE action='intervention-intent'"):
                session_id = json.loads(details)['session_id']
                rows.append((entity_id, session_id, at))
        finally:
            conn.close()
        return rows

    def _read_goals(self, db_path):
        rows = []
        conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True, timeout=10)
        try:
            for client_id, document in conn.execute('SELECT id, document FROM outbox'):
                session_id = json.loads(document)['session_id']
                rows.append((client_id, session_id, None))
        finally:
            conn.close()
        return rows

    def _apply_backfill(self, rows, state_root, result):
        if not rows:
            return
        known = self.known([row[0] for row in rows])
        for client_id, session_id, at in rows:
            if client_id in known:
                result['present'] += 1
            else:
                result['inserted'] += 1
            self.record(client_id, session_id, 'backfill', state_root, at=at)

    def backfill(self, state_base):
        state_base = Path(state_base)
        result = {'roots': 0, 'inserted': 0, 'present': 0, 'unreadable': []}
        if state_base.is_dir():
            for child in sorted(p for p in state_base.iterdir() if p.is_dir()):
                db_path = child / 'state.sqlite3'
                if not db_path.exists():
                    continue
                result['roots'] += 1
                try:
                    rows = self._read_state_root(db_path)
                except sqlite3.Error:
                    result['unreadable'].append(str(db_path))
                    continue
                self._apply_backfill(rows, str(child), result)
        goals_path = state_base / 'goals/state/goals.sqlite3'
        if goals_path.exists():
            try:
                rows = self._read_goals(goals_path)
            except sqlite3.Error:
                result['unreadable'].append(str(goals_path))
            else:
                self._apply_backfill(rows, str(state_base / 'goals'), result)
        return result

    def close(self):
        self.conn.close()
