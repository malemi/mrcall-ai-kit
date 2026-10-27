import contextlib
import datetime
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import time
import uuid

SCHEMA_VERSION = 1
TERMINAL = {'completed', 'failed', 'cancelled'}


class StoreError(ValueError):
    pass


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise StoreError(f'{name} must be a nonempty string')
    return value


def strings(value, name, nonempty=False):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise StoreError(f'{name} must be a string list')
    if nonempty and not value:
        raise StoreError(f'{name} must not be empty')
    return value


def identity(value, name):
    try:
        return str(uuid.UUID(text(value, name)))
    except (ValueError, AttributeError):
        raise StoreError(f'{name} must be an exact UUID') from None


def timestamp(value):
    if isinstance(value, str):
        try:
            parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                raise ValueError()
            value = parsed.timestamp()
        except ValueError:
            raise StoreError('next_run_at must be an epoch or timezone-aware ISO timestamp') from None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise StoreError('next_run_at must be a finite nonnegative timestamp')
    return float(value)


def number(value, name, minimum=1):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise StoreError(f'{name} must be an integer >= {minimum}')
    return value


def object_value(value, name):
    if not isinstance(value, dict):
        raise StoreError(f'{name} must be an object')
    return value


def default_state_dir():
    base = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state'))
    return base / 'mrcall-ai-kit/supervision'


class Store:
    def __init__(self, state_dir=None):
        self.root = Path(state_dir or default_state_dir()).absolute()
        for part in [self.root, *self.root.parents]:
            if part.is_symlink():
                raise StoreError(f'symlink state path refused: {part}')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._private(self.root, directory=True)
        self.path = self.root / 'state.sqlite3'
        for suffix in ('', '-wal', '-shm', '-journal'):
            p = Path(str(self.path) + suffix)
            if p.exists() or p.is_symlink():
                self._private(p)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        self._private(self.path)
        self.conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.execute('PRAGMA busy_timeout=10000')
        try:
            with self.transaction():
                version = self.conn.execute('PRAGMA user_version').fetchone()[0]
                if version > SCHEMA_VERSION:
                    raise StoreError(f'newer schema {version}; supported {SCHEMA_VERSION}; writes refused')
                if version == 0:
                    tables = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                    if tables:
                        raise StoreError('unversioned populated database refused; no automatic migration')
                    if self.path.stat().st_size:
                        backup = self.root / 'state.sqlite3.v0.backup'
                        if backup.exists() or backup.is_symlink():
                            self._private(backup)
                        else:
                            fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                            with os.fdopen(fd, 'wb') as output:
                                output.write(self.path.read_bytes())
                                output.flush()
                                os.fsync(output.fileno())
                    self._schema()
        except BaseException:
            self.conn.close()
            raise

    @staticmethod
    def _private(path, directory=False):
        info = path.lstat()
        wanted = stat.S_ISDIR if directory else stat.S_ISREG
        if not wanted(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise StoreError(f'unsafe ownership, type or permissions: {path}')
        if not directory and info.st_nlink != 1:
            raise StoreError(f'hard-linked state file refused: {path}')

    def _schema(self):
        statements = [
            'CREATE TABLE bindings (id TEXT PRIMARY KEY, runtime TEXT NOT NULL, session_id TEXT NOT NULL UNIQUE, target_ids TEXT NOT NULL, status TEXT NOT NULL, generation INTEGER NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)',
            'CREATE TABLE tasks (id TEXT PRIMARY KEY, supervisor_id TEXT NOT NULL REFERENCES bindings(id), status TEXT NOT NULL, revision INTEGER NOT NULL, generation INTEGER NOT NULL, next_run_at REAL NOT NULL, interval_seconds INTEGER, payload TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)',
            'CREATE TABLE executions (id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), supervisor_id TEXT NOT NULL REFERENCES bindings(id), generation INTEGER NOT NULL, binding_generation INTEGER NOT NULL, status TEXT NOT NULL, scheduled_at REAL NOT NULL, started_at REAL, finished_at REAL, lease_until REAL, result TEXT, UNIQUE(task_id, scheduled_at, generation))',
            'CREATE TABLE outbox (id TEXT PRIMARY KEY, execution_id TEXT NOT NULL REFERENCES executions(id), status TEXT NOT NULL, payload TEXT NOT NULL, client_message_id TEXT NOT NULL UNIQUE, native_submission_id TEXT, attempts INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, updated_at REAL NOT NULL)',
            'CREATE TABLE audit (sequence INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, entity_id TEXT NOT NULL, details TEXT NOT NULL)',
            'CREATE TABLE memory (id TEXT PRIMARY KEY, supervisor_id TEXT NOT NULL REFERENCES bindings(id), task_id TEXT REFERENCES tasks(id), kind TEXT NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL, evidence TEXT NOT NULL, created_at REAL NOT NULL, supersedes TEXT UNIQUE REFERENCES memory(id))',
            'CREATE INDEX task_due ON tasks(status, next_run_at)',
            'CREATE INDEX execution_state ON executions(supervisor_id, status)',
            'CREATE INDEX memory_scope ON memory(supervisor_id, task_id)',
        ]
        for statement in statements:
            self.conn.execute(statement)
        for table in ('audit', 'memory'):
            for action in ('UPDATE', 'DELETE'):
                self.conn.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only table'); END")
        self.conn.execute(f'PRAGMA user_version={SCHEMA_VERSION}')

    @contextlib.contextmanager
    def transaction(self):
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            yield self.conn
            self.conn.execute('COMMIT')
        except BaseException:
            self.conn.execute('ROLLBACK')
            raise

    def close(self):
        self.conn.close()

    def audit(self, action, entity_id, details, actor='operator'):
        self.conn.execute('INSERT INTO audit(at, actor, action, entity_id, details) VALUES(?,?,?,?,?)',
                          (time.time(), text(actor, 'actor'), action, entity_id, json.dumps(details, allow_nan=False)))

    def binding(self, binding_id):
        row = self.conn.execute('SELECT * FROM bindings WHERE id=?', (binding_id,)).fetchone()
        if row is None:
            raise StoreError(f'unknown binding: {binding_id}')
        result = dict(row)
        result['target_ids'] = json.loads(result['target_ids'])
        return result

    def bind(self, data):
        binding_id = text(data.get('id'), 'id')
        runtime = data.get('runtime', 'codex')
        if runtime not in ('codex', 'claude'):
            raise StoreError('runtime must be codex or claude')
        session = identity(data.get('session_id'), 'session_id')
        targets = [identity(x, 'target_id') for x in strings(data.get('target_ids', []), 'target_ids')]
        if len(set(targets)) != len(targets) or session in targets:
            raise StoreError('target IDs must be distinct from one another and supervisor')
        now = time.time()
        with self.transaction():
            old = self.conn.execute('SELECT * FROM bindings WHERE id=?', (binding_id,)).fetchone()
            if old:
                current = self.binding(binding_id)
                if current['runtime'] == runtime and current['session_id'] == session and current['target_ids'] == targets:
                    if current['status'] == 'active':
                        return current
                    self.conn.execute("UPDATE bindings SET status='active',generation=generation+1,updated_at=? WHERE id=?", (now, binding_id))
                    self.audit('reattach', binding_id, {'session_id': session, 'target_ids': targets, 'tasks_remain_paused': True}, data.get('actor', 'operator'))
                    return self.binding(binding_id)
                raise StoreError('binding identity cannot change; register a distinct session separately')
            self.conn.execute('INSERT INTO bindings VALUES(?,?,?,?,?,?,?,?)', (binding_id, runtime, session, json.dumps(targets), 'active', 1, now, now))
            self.audit('bind', binding_id, {'session_id': session, 'target_ids': targets}, data.get('actor', 'operator'))
        return self.binding(binding_id)

    def task(self, task_id):
        row = self.conn.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        if row is None:
            raise StoreError(f'unknown task: {task_id}')
        result = dict(row)
        result.update(json.loads(result.pop('payload')))
        return result

    def _task_payload(self, data, binding):
        instruction = text(data.get('instruction'), 'instruction')
        targets = [identity(x, 'target_id') for x in strings(data.get('target_ids', []), 'target_ids')]
        if not set(targets).issubset(binding['target_ids']):
            raise StoreError('task target is outside the exact binding')
        acceptance = strings(data.get('acceptance'), 'acceptance', True)
        scope = text(data.get('scope'), 'scope')
        limits = dict(object_value(data.get('limits'), 'limits'))
        text(limits.get('provenance'), 'limits.provenance')
        sources = dict(object_value(limits.get('parameter_provenance', {}), 'limits.parameter_provenance'))
        for key, default in {'max_checks': None, 'assessment_timeout_seconds': 180, 'transport_timeout_seconds': 10, 'recovery_attempts': 1}.items():
            if key not in limits:
                limits[key] = default
                sources[key] = 'supervisor-default'
            else:
                sources.setdefault(key, limits['provenance'])
            text(sources[key], 'limits.parameter_provenance.' + key)
            if key != 'max_checks' or limits[key] is not None:
                number(limits[key], 'limits.' + key, minimum=0 if key == 'recovery_attempts' else 1)
        limits['parameter_provenance'] = sources
        harness = data.get('harness')
        if harness is not None:
            object_value(harness, 'harness')
            for key in ('repo', 'git_dir', 'task_id'):
                text(harness.get(key), f'harness.{key}')
            if not Path(harness['repo']).is_absolute() or not Path(harness['git_dir']).is_absolute():
                raise StoreError('harness repo and git_dir must be absolute')
        mode = data.get('schedule_mode', 'interval')
        if mode not in ('interval', 'utc-aligned'):
            raise StoreError('schedule_mode must be interval or utc-aligned')
        return {'schedule_mode': mode, 'instruction': instruction, 'target_ids': targets, 'acceptance': acceptance,
                'scope': scope, 'limits': limits, 'harness': harness,
                'evidence': strings(data.get('evidence', []), 'evidence'),
                'remaining': strings(data.get('remaining', []), 'remaining')}

    def create_task(self, data):
        task_id = text(data.get('id'), 'id')
        binding_id = text(data.get('supervisor_id'), 'supervisor_id')
        interval = data.get('interval_seconds', 600)
        if interval is not None:
            number(interval, 'interval_seconds')
        elif 'next_run_at' not in data:
            raise StoreError('one-shot task requires next_run_at')
        now = time.time()
        due = timestamp(data.get('next_run_at', now + interval if interval else now))
        with self.transaction():
            binding = self.binding(binding_id)
            if binding['status'] != 'active':
                raise StoreError('binding is detached')
            payload = self._task_payload(data, binding)
            self.conn.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)',
                              (task_id, binding_id, 'active', 1, 1, due, interval, json.dumps(payload), now, now))
            self.audit('task-create', task_id, payload, data.get('actor', 'operator'))
        return self.task(task_id)

    def _fence(self, task_id):
        self.conn.execute("UPDATE outbox SET status='uncertain', updated_at=? WHERE execution_id IN (SELECT id FROM executions WHERE task_id=?) AND status='sending'", (time.time(), task_id))
        self.conn.execute("UPDATE outbox SET status='cancelled', updated_at=? WHERE execution_id IN (SELECT id FROM executions WHERE task_id=?) AND status IN ('pending','claimed','not-delivered')", (time.time(), task_id))
        self.conn.execute("UPDATE executions SET status='invalidated', finished_at=? WHERE task_id=? AND status IN ('pending','claimed','running','delivered','sending','uncertain','not-delivered','unhealthy')", (time.time(), task_id))

    def update_task(self, data):
        task_id = text(data.get('id'), 'id')
        revision = number(data.get('revision'), 'revision')
        changes = object_value(data.get('changes'), 'changes')
        allowed = {'instruction', 'target_ids', 'acceptance', 'scope', 'limits', 'harness', 'interval_seconds', 'next_run_at', 'schedule_mode'}
        if not changes or set(changes) - allowed:
            raise StoreError('unknown or empty task changes')
        with self.transaction():
            old = self.task(task_id)
            if old['revision'] != revision:
                raise StoreError('revision conflict')
            if old['status'] in TERMINAL:
                raise StoreError('terminal task cannot be updated')
            merged = old | changes
            binding = self.binding(old['supervisor_id'])
            if binding['status'] != 'active':
                raise StoreError('binding is detached')
            payload = json.loads(self.conn.execute('SELECT payload FROM tasks WHERE id=?', (task_id,)).fetchone()[0])
            payload.update(self._task_payload(merged, binding))
            interval = merged['interval_seconds']
            if interval is not None:
                number(interval, 'interval_seconds')
            due = timestamp(merged['next_run_at'])
            self._fence(task_id)
            self.conn.execute('UPDATE tasks SET revision=revision+1,generation=generation+1,next_run_at=?,interval_seconds=?,payload=?,updated_at=? WHERE id=?',
                              (due, interval, json.dumps(payload), time.time(), task_id))
            self.audit('task-update', task_id, changes, data.get('actor', 'operator'))
        return self.task(task_id)

    def task_state(self, data):
        task_id = text(data.get('id'), 'id')
        revision = number(data.get('revision'), 'revision')
        action = text(data.get('action'), 'action')
        states = {'pause': 'paused', 'resume': 'active', 'complete': 'completed', 'fail': 'failed', 'cancel': 'cancelled', 'block': 'blocked'}
        if action not in states:
            raise StoreError('invalid task state action')
        reason = text(data.get('reason'), 'reason')
        evidence = strings(data.get('evidence', []), 'evidence')
        remaining = strings(data.get('remaining', []), 'remaining')
        if action == 'complete' and (not evidence or remaining):
            raise StoreError('completion requires evidence and no remaining obligations')
        if action in ('fail', 'block') and not remaining:
            raise StoreError('failed or blocked task requires remaining obligations')
        if action == 'block':
            text(data.get('resume_condition'), 'resume_condition')
        with self.transaction():
            old = self.task(task_id)
            if old['revision'] != revision:
                raise StoreError('revision conflict')
            if old['status'] in TERMINAL:
                raise StoreError('terminal task cannot transition')
            if action == 'resume' and old['status'] not in ('paused', 'blocked'):
                raise StoreError('only paused or blocked tasks can resume')
            if self.binding(old['supervisor_id'])['status'] != 'active' and action == 'resume':
                raise StoreError('cannot resume detached binding')
            payload = json.loads(self.conn.execute('SELECT payload FROM tasks WHERE id=?', (task_id,)).fetchone()[0])
            payload.update(reason=reason, evidence=evidence, remaining=remaining)
            if action == 'block':
                payload['resume_condition'] = data['resume_condition']
            elif action == 'resume':
                payload.pop('resume_condition', None)
            self._fence(task_id)
            self.conn.execute('UPDATE tasks SET status=?,revision=revision+1,generation=generation+1,payload=?,updated_at=? WHERE id=?',
                              (states[action], json.dumps(payload), time.time(), task_id))
            self.audit('task-' + action, task_id, payload, data.get('actor', 'operator'))
        return self.task(task_id)

    def detach(self, data):
        binding_id = text(data.get('id'), 'id')
        reason = text(data.get('reason'), 'reason')
        with self.transaction():
            binding = self.binding(binding_id)
            if binding['status'] == 'detached':
                return binding
            self.conn.execute("UPDATE bindings SET status='detached',generation=generation+1,updated_at=? WHERE id=?", (time.time(), binding_id))
            ids = self.conn.execute("SELECT id FROM tasks WHERE supervisor_id=? AND status NOT IN ('completed','failed','cancelled')", (binding_id,)).fetchall()
            for row in ids:
                self._fence(row['id'])
                self.conn.execute("UPDATE tasks SET status='paused',revision=revision+1,generation=generation+1,updated_at=? WHERE id=?", (time.time(), row['id']))
            self.audit('detach', binding_id, {'reason': reason, 'underlying_sessions_cancelled': False}, data.get('actor', 'operator'))
        return self.binding(binding_id)

    def add_memory(self, data):
        memory_id = data.get('id', str(uuid.uuid4()))
        text(memory_id, 'id')
        binding_id = text(data.get('supervisor_id'), 'supervisor_id')
        task_id = data.get('task_id')
        kind = data.get('kind')
        if kind not in ('fact', 'hypothesis', 'decision', 'correction', 'authorization', 'failure', 'intervention', 'next-action'):
            raise StoreError('invalid memory kind')
        content = text(data.get('content'), 'content')
        source = text(data.get('source'), 'source')
        evidence = strings(data.get('evidence', []), 'evidence')
        supersedes = data.get('supersedes')
        with self.transaction():
            self.binding(binding_id)
            if task_id is not None and self.task(task_id)['supervisor_id'] != binding_id:
                raise StoreError('memory task belongs to another supervisor')
            if supersedes:
                old = self.conn.execute('SELECT * FROM memory WHERE id=?', (supersedes,)).fetchone()
                if not old or old['supervisor_id'] != binding_id or old['task_id'] != task_id:
                    raise StoreError('superseded memory must exist in the same exact scope')
            self.conn.execute('INSERT INTO memory VALUES(?,?,?,?,?,?,?,?,?)',
                              (memory_id, binding_id, task_id, kind, content, source, json.dumps(evidence), time.time(), supersedes))
            self.audit('memory-add', memory_id, {'supervisor_id': binding_id, 'task_id': task_id, 'supersedes': supersedes}, data.get('actor', 'operator'))
        return {'id': memory_id, 'supersedes': supersedes}

    def memory(self, data):
        binding_id = text(data.get('supervisor_id'), 'supervisor_id')
        self.binding(binding_id)
        task_id = data.get('task_id')
        query = 'SELECT m.* FROM memory m WHERE m.supervisor_id=? AND m.task_id IS ?'
        if not data.get('include_history', False):
            query += ' AND NOT EXISTS(SELECT 1 FROM memory n WHERE n.supersedes=m.id)'
        rows = self.conn.execute(query + ' ORDER BY created_at,id', (binding_id, task_id)).fetchall()
        return [dict(row) | {'evidence': json.loads(row['evidence'])} for row in rows]

    def execution_result(self, data):
        execution_id = text(data.get('id'), 'id')
        generation = number(data.get('generation'), 'generation')
        outcome = data.get('outcome')
        if outcome not in ('completed', 'failed', 'blocked'):
            raise StoreError('invalid execution outcome')
        result = {'outcome': outcome, 'evidence': strings(data.get('evidence', []), 'evidence'),
                  'remaining': strings(data.get('remaining', []), 'remaining'), 'summary': text(data.get('summary'), 'summary')}
        if outcome == 'completed' and not result['evidence']:
            raise StoreError('completed execution requires evidence')
        with self.transaction():
            row = self.conn.execute('SELECT * FROM executions WHERE id=?', (execution_id,)).fetchone()
            if row is None:
                raise StoreError('unknown execution')
            task = self.task(row['task_id'])
            binding = self.binding(row['supervisor_id'])
            if row['generation'] != generation or task['generation'] != generation or binding['generation'] != row['binding_generation'] or binding['status'] != 'active' or task['status'] != 'active':
                raise StoreError('stale execution fence')
            if row['status'] not in ('running', 'delivered', 'unhealthy'):
                raise StoreError('execution is not running or delivered')
            self.conn.execute('UPDATE executions SET status=?,finished_at=?,result=? WHERE id=?',
                              (outcome, time.time(), json.dumps(result), execution_id))
            self.audit('execution-result', execution_id, result, data.get('actor', 'supervisor'))
        return {'id': execution_id, **result, 'task_state_changed': False}

    def status(self, task_id=None):
        if task_id is not None:
            return self.task(task_id)
        tick = self.conn.execute("SELECT details FROM audit WHERE action='tick' AND actor='scheduler' ORDER BY sequence DESC LIMIT 1").fetchone()
        last_tick = json.loads(tick['details'])['at'] if tick else None
        age = max(0, time.time() - last_tick) if last_tick is not None else None
        activation = self.conn.execute("SELECT max(updated_at) FROM bindings WHERE status='active'").fetchone()[0]
        active = activation is not None
        scheduler_state = 'dormant' if not active else ('active' if age is not None and age <= 180 else 'overdue')
        if active and last_tick is None and max(0, time.time() - activation) <= 180:
            scheduler_state = 'waiting-first-tick'
        return {'schema_version': SCHEMA_VERSION,
                'bindings': [self.binding(row[0]) for row in self.conn.execute('SELECT id FROM bindings ORDER BY id')],
                'tasks': [self.task(row[0]) for row in self.conn.execute('SELECT id FROM tasks ORDER BY id')],
                'executions': [dict(row) for row in self.conn.execute('SELECT * FROM executions ORDER BY scheduled_at,id')],
                'outbox': [dict(row) for row in self.conn.execute('SELECT * FROM outbox ORDER BY created_at,id')],
                'health': {'scheduler': {'state': scheduler_state, 'last_tick_at': last_tick, 'age_seconds': age, 'grace_seconds': 180},
                           'attention': [dict(row) for row in self.conn.execute("SELECT id,task_id,status,result FROM executions WHERE status IN ('unhealthy','uncertain','not-delivered') OR (status='pending' AND json_extract(result,'$.dispatch_wait_overdue')=1)")]}}
