import contextlib
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import time
import uuid

SCHEMA_VERSION = 2
TERMINAL = {'completed', 'failed', 'cancelled'}
LEGACY = ('this state root uses the earlier schema and is kept as it is: use a new state root (--state-dir) '
          'and create the task there with the required fields')
TECHNICAL = {'assessment_timeout_seconds': 180, 'transport_timeout_seconds': 10, 'recovery_attempts': 1,
             'heartbeat_seconds': 1800, 'delivery_latest_seconds': 1800, 'step_bound': 5, 'review_timeout_seconds': 600}
OPEN_EXECUTIONS = ('pending', 'claimed', 'running', 'delivered', 'sending', 'uncertain', 'not-delivered', 'unhealthy')
USAGE = ('total', 'input', 'cached_input', 'output')
FOUR = ('target {session} is {state} and owns an open acceptance item: close the assessment for it with an intervention '
        'sent in this assessment and accepted by the transport, a wait on a time, a file or a process exit with a latest '
        'time, a park (outcome blocked with a park), or a conclusion (task-state complete or fail)')


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


def timestamp(value, name='next_run_at'):
    if isinstance(value, str):
        try:
            parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                raise ValueError()
            value = parsed.timestamp()
        except ValueError:
            raise StoreError(f'{name} must be an epoch or timezone-aware ISO timestamp') from None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise StoreError(f'{name} must be a finite nonnegative timestamp')
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


def modules():
    try:
        from . import authority, ledger
    except ImportError:
        import authority
        import ledger
    return authority, ledger


def session_state(snapshot):
    """working, idle, waiting, unreachable or unknown: only `working` means the session is doing work."""
    if not snapshot or snapshot.get('stale_since'):
        return 'unknown'
    status = snapshot.get('status')
    if status == 'idle':
        return 'idle'
    if status == 'active':
        return 'waiting' if snapshot.get('flags') else 'working'
    if status in ('notLoaded', 'systemError'):
        return 'unreachable'
    return 'unknown'


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
        self.legacy = False
        self._ledger = None
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
                elif version < SCHEMA_VERSION:
                    # An earlier root is never migrated: it stays readable and stoppable.
                    self.legacy = True
            self.ledger_path = None if self.legacy else self.meta('ledger_path')
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
        _, ledger = modules()
        statements = [
            'CREATE TABLE bindings (id TEXT PRIMARY KEY, runtime TEXT NOT NULL, session_id TEXT NOT NULL UNIQUE, target_ids TEXT NOT NULL, status TEXT NOT NULL, generation INTEGER NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)',
            'CREATE TABLE tasks (id TEXT PRIMARY KEY, supervisor_id TEXT NOT NULL REFERENCES bindings(id), status TEXT NOT NULL, revision INTEGER NOT NULL, generation INTEGER NOT NULL, next_run_at REAL NOT NULL, interval_seconds INTEGER, payload TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)',
            'CREATE TABLE executions (id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), supervisor_id TEXT NOT NULL REFERENCES bindings(id), generation INTEGER NOT NULL, binding_generation INTEGER NOT NULL, status TEXT NOT NULL, scheduled_at REAL NOT NULL, started_at REAL, finished_at REAL, lease_until REAL, result TEXT, triggers TEXT, closing_set TEXT, working INTEGER, UNIQUE(task_id, scheduled_at, generation))',
            'CREATE TABLE outbox (id TEXT PRIMARY KEY, execution_id TEXT NOT NULL REFERENCES executions(id), status TEXT NOT NULL, payload TEXT NOT NULL, client_message_id TEXT NOT NULL UNIQUE, native_submission_id TEXT, attempts INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, updated_at REAL NOT NULL)',
            'CREATE TABLE audit (sequence INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, entity_id TEXT NOT NULL, details TEXT NOT NULL)',
            'CREATE TABLE memory (id TEXT PRIMARY KEY, supervisor_id TEXT NOT NULL REFERENCES bindings(id), task_id TEXT REFERENCES tasks(id), kind TEXT NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL, evidence TEXT NOT NULL, created_at REAL NOT NULL, supersedes TEXT UNIQUE REFERENCES memory(id))',
            'CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)',
            'CREATE TABLE sessions (session_id TEXT PRIMARY KEY, runtime TEXT NOT NULL, snapshot TEXT NOT NULL, cursor TEXT, observed_at REAL NOT NULL, stale_since REAL)',
            'CREATE TABLE observations (sequence INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, session_id TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL)',
            'CREATE TABLE messages (session_id TEXT NOT NULL, id TEXT NOT NULL, turn_id TEXT, client_id TEXT, at REAL, origin TEXT NOT NULL, ref TEXT UNIQUE, text TEXT NOT NULL, observed_at REAL NOT NULL, PRIMARY KEY(session_id, id))',
            'CREATE TABLE deliveries (client_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, kind TEXT NOT NULL, task_id TEXT, execution_id TEXT, state TEXT NOT NULL, text TEXT NOT NULL, sent_at REAL NOT NULL, latest_at REAL NOT NULL, consumed_at REAL, turn_id TEXT, detail TEXT)',
            'CREATE TABLE items (task_id TEXT NOT NULL REFERENCES tasks(id), id TEXT NOT NULL, owner TEXT, text TEXT NOT NULL, status TEXT NOT NULL, evidence TEXT NOT NULL, closed_at REAL, PRIMARY KEY(task_id, id))',
            'CREATE TABLE steps (task_id TEXT NOT NULL REFERENCES tasks(id), id TEXT NOT NULL, session_id TEXT NOT NULL, description TEXT NOT NULL, artifact TEXT NOT NULL, estimate_seconds INTEGER NOT NULL, declared_at REAL NOT NULL, declared_execution TEXT NOT NULL, status TEXT NOT NULL, closed_at REAL, flags TEXT NOT NULL, PRIMARY KEY(task_id, id))',
            'CREATE TABLE closures (task_id TEXT NOT NULL, kind TEXT NOT NULL, ref TEXT NOT NULL, execution_id TEXT, at REAL NOT NULL, PRIMARY KEY(task_id, kind, ref))',
            'CREATE TABLE waits (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, session_id TEXT NOT NULL, execution_id TEXT NOT NULL, condition TEXT NOT NULL, latest_at REAL NOT NULL, status TEXT NOT NULL, created_at REAL NOT NULL, resolved_at REAL)',
            'CREATE TABLE parks (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, execution_id TEXT, reason TEXT NOT NULL, request TEXT NOT NULL, status TEXT NOT NULL, positions TEXT NOT NULL, question_id TEXT, created_at REAL NOT NULL, effective_at REAL)',
            'CREATE TABLE triggers (sequence INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL, at REAL NOT NULL, execution_id TEXT)',
            'CREATE TABLE reviews (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, kind TEXT NOT NULL, park_id TEXT, reason TEXT NOT NULL, status TEXT NOT NULL, pid INTEGER, started_at REAL NOT NULL, finished_at REAL, verdict TEXT, tokens INTEGER)',
            'CREATE TABLE counters (task_id TEXT PRIMARY KEY, no_closure INTEGER NOT NULL, step_closures INTEGER NOT NULL, step_reviews INTEGER NOT NULL, rejections INTEGER NOT NULL, abandoned INTEGER NOT NULL, state TEXT NOT NULL)',
            'CREATE TABLE baselines (task_id TEXT NOT NULL, session_id TEXT NOT NULL, usage TEXT NOT NULL, PRIMARY KEY(task_id, session_id))',
            'CREATE INDEX task_due ON tasks(status, next_run_at)',
            'CREATE INDEX execution_state ON executions(supervisor_id, status)',
            'CREATE INDEX memory_scope ON memory(supervisor_id, task_id)',
            'CREATE INDEX trigger_pending ON triggers(task_id, execution_id)',
            'CREATE INDEX message_client ON messages(session_id, client_id)',
        ]
        for statement in statements:
            self.conn.execute(statement)
        for table in ('audit', 'memory', 'observations', 'messages'):
            for action in ('UPDATE', 'DELETE'):
                self.conn.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only table'); END")
        self.conn.execute('INSERT INTO meta VALUES(?,?)', ('ledger_path', str(ledger.default_path())))
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
        if self._ledger is not None:
            self._ledger.close()
        self.conn.close()

    def meta(self, key):
        row = self.conn.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return row[0] if row else None

    def ledger(self):
        """The account ledger this root recorded at creation; the environment cannot redirect it later."""
        if self.legacy:
            raise StoreError(LEGACY)
        if self._ledger is None:
            self._ledger = modules()[1].Ledger(self.ledger_path)
        return self._ledger

    def current(self):
        if self.legacy:
            raise StoreError(LEGACY)

    def audit(self, action, entity_id, details, actor='operator'):
        self.conn.execute('INSERT INTO audit(at, actor, action, entity_id, details) VALUES(?,?,?,?,?)',
                          (time.time(), text(actor, 'actor'), action, entity_id, json.dumps(details, allow_nan=False)))

    # ---- bindings ----

    def binding(self, binding_id):
        row = self.conn.execute('SELECT * FROM bindings WHERE id=?', (binding_id,)).fetchone()
        if row is None:
            raise StoreError(f'unknown binding: {binding_id}')
        result = dict(row)
        result['target_ids'] = json.loads(result['target_ids'])
        return result

    def bind(self, data):
        self.current()
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

    # ---- registry ----

    def registered(self, reference):
        return self.conn.execute("SELECT 1 FROM messages WHERE ref=? AND origin='operator'", (reference,)).fetchone() is not None

    def registry_message(self, reference):
        row = self.conn.execute("SELECT * FROM messages WHERE ref=? AND origin='operator'", (reference,)).fetchone()
        if row is None:
            raise StoreError(f'{reference} is not in the registry')
        return dict(row)

    def registry(self, session_id=None):
        query = "SELECT ref,session_id,turn_id,at,text FROM messages WHERE origin='operator'"
        rows = self.conn.execute(query + (' AND session_id=?' if session_id else '') + ' ORDER BY at,ref',
                                 ((session_id,) if session_id else ())).fetchall()
        return [dict(row) for row in rows]

    # ---- tasks ----

    def task(self, task_id):
        row = self.conn.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
        if row is None:
            raise StoreError(f'unknown task: {task_id}')
        result = dict(row)
        result.update(json.loads(result.pop('payload')))
        return result

    def _limits(self, value, mode):
        authority, _ = modules()
        limits = dict(object_value({} if value is None else value, 'limits'))
        extra = set(limits) - set(TECHNICAL) - {'provenance', 'parameter_provenance', 'spend', 'deadline_at', 'max_checks'}
        if extra:
            raise StoreError('unknown limits: ' + ', '.join(sorted(extra)) + '; an operator limit is a deadline, an assessment '
                             'count or a spend limit, and an estimate or a time slot an agent wrote is not a limit')
        provenance = limits.get('provenance')
        if provenance is not None:
            text(provenance, 'limits.provenance')
        sources = dict(object_value(limits.get('parameter_provenance', {}), 'limits.parameter_provenance'))
        for key, default in TECHNICAL.items():
            if key not in limits:
                limits[key] = default
                sources[key] = 'supervisor-default'
            else:
                sources.setdefault(key, provenance or 'supervisor')
            text(sources[key], 'limits.parameter_provenance.' + key)
            number(limits[key], 'limits.' + key, minimum=0 if key == 'recovery_attempts' else 1)
        limits['parameter_provenance'] = {key: sources[key] for key in TECHNICAL}
        limits['spend'] = authority.spend_limit(limits.get('spend'), self.registered, required=mode == 'completion')
        for key in ('deadline_at', 'max_checks'):
            entry = limits.get(key)
            if entry is None:
                limits[key] = None
                continue
            if not isinstance(entry, dict) or set(entry) != {'value', 'cites'}:
                raise StoreError(f'limits.{key} must be an object with value and cites; text an agent wrote is not an operator limit')
            checked = timestamp(entry['value'], 'limits.deadline_at.value') if key == 'deadline_at' else number(entry['value'], 'limits.max_checks.value')
            limits[key] = {'value': checked, 'cites': authority.cites(entry['cites'], f'limits.{key}.cites', self.registered)}
        return limits

    def _acceptance(self, value, targets, mode, task_id=None):
        if not isinstance(value, list) or not value:
            raise StoreError('acceptance must be a nonempty list')
        entries = []
        for entry in value:
            if isinstance(entry, str):
                entry = {'text': entry}
            if not isinstance(entry, dict) or set(entry) - {'id', 'text', 'owner'}:
                raise StoreError('each acceptance item is an object with text, owner and optionally id')
            owner = entry.get('owner')
            if owner is not None:
                owner = identity(owner, 'acceptance.owner')
                if owner not in targets:
                    raise StoreError('each acceptance item is owned by one of the task targets')
            elif mode == 'completion':
                raise StoreError('each acceptance item of a completion task names its owner among the targets')
            entries.append({'id': entry.get('id'), 'text': text(entry.get('text'), 'acceptance.text'), 'owner': owner})
        known = {row[0] for row in self.conn.execute('SELECT id FROM items WHERE task_id=?', (task_id,))} if task_id else set()
        used = [entry['id'] for entry in entries if entry['id'] is not None]
        if len(set(used)) != len(used) or any(ident not in known for ident in used):
            raise StoreError('an acceptance id is one Python already assigned to this task, used once')
        highest = max([int(ident[1:]) for ident in known] or [0])
        for entry in entries:
            if entry['id'] is None:
                highest += 1
                entry['id'] = f'A{highest}'
        return entries

    def _task_payload(self, data, binding, task_id=None):
        authority, _ = modules()
        instruction = text(data.get('instruction'), 'instruction')
        mode = data.get('mode')
        if mode not in ('completion', 'observation'):
            raise StoreError('mode must be completion or observation')
        targets = [identity(x, 'target_id') for x in strings(data.get('target_ids', []), 'target_ids', nonempty=mode == 'completion')]
        if not set(targets).issubset(binding['target_ids']):
            raise StoreError('task target is outside the exact binding')
        if data.get('operator_session_id') is None:
            raise StoreError('operator_session_id is required: the session where the operator gave the mandate, unless the operator names another')
        operator = identity(data.get('operator_session_id'), 'operator_session_id')
        acceptance = self._acceptance(data.get('acceptance'), targets, mode, task_id)
        scope = text(data.get('scope'), 'scope')
        limits = self._limits(data.get('limits'), mode)
        changes = data.get('ask_first')
        asks, record = authority.ask_first(changes, self.registered)
        statements = authority.cites(data.get('statements'), 'statements', self.registered, required=False)
        harness = data.get('harness')
        if harness is not None:
            object_value(harness, 'harness')
            for key in ('repo', 'git_dir', 'task_id'):
                text(harness.get(key), f'harness.{key}')
            if not Path(harness['repo']).is_absolute() or not Path(harness['git_dir']).is_absolute():
                raise StoreError('harness repo and git_dir must be absolute')
        return {'contract': 2, 'mode': mode, 'operator_session_id': operator, 'instruction': instruction,
                'target_ids': targets, 'acceptance': acceptance, 'scope': scope, 'limits': limits,
                'ask_first': asks, 'ask_first_changes': record, 'statements': statements, 'harness': harness,
                'evidence': strings(data.get('evidence', []), 'evidence'),
                'remaining': strings(data.get('remaining', []), 'remaining')}

    def _claim_alive(self, state_root, task_id):
        """Whether another root's claim on a target still holds: its task is active or parked under an active binding."""
        query = "SELECT t.status,b.status FROM tasks t JOIN bindings b ON b.id=t.supervisor_id WHERE t.id=?"
        if Path(state_root) == self.root:
            row = self.conn.execute(query, (task_id,)).fetchone()
        else:
            path = Path(state_root) / 'state.sqlite3'
            if not path.is_file():
                return False
            try:
                other = sqlite3.connect(f'file:{path}?mode=ro', uri=True, timeout=5)
                try:
                    row = other.execute(query, (task_id,)).fetchone()
                finally:
                    other.close()
            except sqlite3.Error:
                return True
        return bool(row) and row[0] in ('active', 'blocked') and row[1] == 'active'

    def _claim(self, task_id, payload):
        if payload['mode'] != 'completion':
            return
        ledger = self.ledger()
        try:
            for target in payload['target_ids']:
                ledger.claim(target, str(self.root), task_id, self._claim_alive)
        except Exception as error:
            ledger.release(str(self.root), task_id)
            raise StoreError('one completion task per target: ' + str(error)) from None

    def _release(self, task_id):
        if not self.legacy:
            self.ledger().release(str(self.root), task_id)

    def _sync_items(self, task_id, acceptance):
        kept = {entry['id'] for entry in acceptance}
        for entry in acceptance:
            row = self.conn.execute('SELECT status FROM items WHERE task_id=? AND id=?', (task_id, entry['id'])).fetchone()
            if row is None:
                self.conn.execute('INSERT INTO items VALUES(?,?,?,?,?,?,?)', (task_id, entry['id'], entry['owner'], entry['text'], 'open', '[]', None))
            else:
                self.conn.execute("UPDATE items SET owner=?,text=?,status=CASE status WHEN 'dropped' THEN 'open' ELSE status END WHERE task_id=? AND id=?",
                                  (entry['owner'], entry['text'], task_id, entry['id']))
        for row in self.conn.execute('SELECT id FROM items WHERE task_id=?', (task_id,)).fetchall():
            if row[0] not in kept:
                self.conn.execute("UPDATE items SET status='dropped' WHERE task_id=? AND id=?", (task_id, row[0]))

    def _measurable(self, payload, binding):
        """A spend limit as a share of the allowance window needs a session that reports its window."""
        limit = payload['limits'].get('spend')
        if payload['mode'] != 'completion' or not limit or limit['unit'] != 'allowance_percent':
            return
        if not any((self.session(session) or {}).get('allowance') for session in [binding['session_id'], *payload['target_ids']]):
            raise StoreError('no session of this task reports an allowance window, so a spend limit in allowance_percent could not '
                             'be measured: refused; give the spend limit in tokens')

    def preview_task(self, data):
        """Validate a task without creating it: what Python would record, for the display before activation."""
        self.current()
        binding = self.binding(text(data.get('supervisor_id'), 'supervisor_id'))
        if binding['status'] != 'active':
            raise StoreError('binding is detached')
        return {'id': text(data.get('id'), 'id'), 'supervisor_id': binding['id'], **self._task_payload(data, binding)}

    def create_task(self, data, baseline=None):
        self.current()
        task_id = text(data.get('id'), 'id')
        binding_id = text(data.get('supervisor_id'), 'supervisor_id')
        interval = data.get('interval_seconds', 600)
        if interval is not None:
            number(interval, 'interval_seconds')
        now = time.time()
        due = timestamp(data.get('next_run_at', now))
        baseline = baseline or {}
        with self.transaction():
            binding = self.binding(binding_id)
            if binding['status'] != 'active':
                raise StoreError('binding is detached')
            payload = self._task_payload(data, binding)
            if payload['mode'] == 'completion':
                unread = [s for s in [binding['session_id'], *payload['target_ids']] if not baseline.get(s)]
                if unread:
                    raise StoreError('the token counter of ' + ', '.join(unread) + ' could not be read, so the spend limit could not be '
                                     'measured: creation refused; run registry-scan, check each session is readable, and retry')
                self._measurable(payload, binding)
            self.conn.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)',
                              (task_id, binding_id, 'active', 1, 1, due, interval, json.dumps(payload), now, now))
            self._sync_items(task_id, payload['acceptance'])
            self.conn.execute('INSERT INTO counters VALUES(?,?,?,?,?,?,?)', (task_id, 0, 0, 0, 0, 0, '{}'))
            for session, usage in baseline.items():
                if usage:
                    self.conn.execute('INSERT INTO baselines VALUES(?,?,?)', (task_id, session, json.dumps(usage)))
            self.trigger(task_id, 'activated', {})
            self.audit('task-create', task_id, payload, data.get('actor', 'operator'))
            self._claim(task_id, payload)
        return self.task(task_id)

    def _fence(self, task_id):
        self.conn.execute("UPDATE outbox SET status='uncertain', updated_at=? WHERE execution_id IN (SELECT id FROM executions WHERE task_id=?) AND status='sending'", (time.time(), task_id))
        self.conn.execute("UPDATE outbox SET status='cancelled', updated_at=? WHERE execution_id IN (SELECT id FROM executions WHERE task_id=?) AND status IN ('pending','claimed','not-delivered')", (time.time(), task_id))
        if not self.legacy:
            # Triggers a fenced assessment held go back to pending: the observation is still owed a judgment.
            self.conn.execute("UPDATE triggers SET execution_id=NULL WHERE task_id=? AND execution_id IN (SELECT id FROM executions WHERE task_id=? AND status IN ('pending','claimed','running','delivered','sending','uncertain','not-delivered','unhealthy'))", (task_id, task_id))
            self._state(task_id, limit_grace=None)
        self.conn.execute("UPDATE executions SET status='invalidated', finished_at=? WHERE task_id=? AND status IN ('pending','claimed','running','delivered','sending','uncertain','not-delivered','unhealthy')", (time.time(), task_id))

    def update_task(self, data):
        self.current()
        task_id = text(data.get('id'), 'id')
        revision = number(data.get('revision'), 'revision')
        changes = object_value(data.get('changes'), 'changes')
        allowed = {'instruction', 'target_ids', 'acceptance', 'scope', 'limits', 'harness', 'interval_seconds', 'next_run_at',
                   'operator_session_id', 'ask_first', 'statements'}
        if not changes or set(changes) - allowed:
            raise StoreError('unknown or empty task changes')
        with self.transaction():
            old = self.task(task_id)
            if old['revision'] != revision:
                raise StoreError('revision conflict')
            if old['status'] in TERMINAL:
                raise StoreError('terminal task cannot be updated')
            if old.get('contract') != 2:
                raise StoreError(LEGACY)
            merged = old | {'ask_first': old['ask_first_changes']} | changes
            binding = self.binding(old['supervisor_id'])
            if binding['status'] != 'active':
                raise StoreError('binding is detached')
            payload = json.loads(self.conn.execute('SELECT payload FROM tasks WHERE id=?', (task_id,)).fetchone()[0])
            payload.update(self._task_payload(merged, binding, task_id))
            self._measurable(payload, binding)
            interval = merged['interval_seconds']
            if interval is not None:
                number(interval, 'interval_seconds')
            due = timestamp(merged['next_run_at'])
            self._fence(task_id)
            self.conn.execute('UPDATE tasks SET revision=revision+1,generation=generation+1,next_run_at=?,interval_seconds=?,payload=?,updated_at=? WHERE id=?',
                              (due, interval, json.dumps(payload), time.time(), task_id))
            self._sync_items(task_id, payload['acceptance'])
            if old['status'] in ('active', 'blocked'):
                self._claim(task_id, payload)
                self.trigger(task_id, 'task-updated', {'changes': sorted(changes)})
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
        with self.transaction():
            old = self.task(task_id)
            if old['revision'] != revision:
                raise StoreError('revision conflict')
            if old['status'] in TERMINAL:
                raise StoreError('terminal task cannot transition')
            current = old.get('contract') == 2
            if not current and action in ('resume', 'block'):
                raise StoreError(LEGACY)
            if action == 'resume' and old['status'] not in ('paused', 'blocked'):
                raise StoreError('only paused or blocked tasks can resume')
            if self.binding(old['supervisor_id'])['status'] != 'active' and action == 'resume':
                raise StoreError('cannot resume detached binding')
            payload = json.loads(self.conn.execute('SELECT payload FROM tasks WHERE id=?', (task_id,)).fetchone()[0])
            payload.update(reason=reason, evidence=evidence, remaining=remaining)
            park = None
            parked = self.conn.execute("SELECT id,created_at FROM parks WHERE task_id=? AND status IN ('challenging','parked') ORDER BY created_at DESC", (task_id,)).fetchone() if current else None
            if parked and action == 'resume':
                # A park ends with the operator's words: an operator message newer than the park, read by the tick or cited here.
                authority, _ = modules()
                cited = authority.cites(data.get('cites'), 'cites', self.registered, required=False)
                if not any(not ref.startswith('config:') and (self.registry_message(ref)['at'] or 0) > parked['created_at'] for ref in cited):
                    raise StoreError('the task is parked and waits for the operator: it resumes when the operator writes in an observed '
                                     'session, or with a resume that cites an operator message newer than the park')
            if current and action == 'block':
                problems = []
                park = self._park_checked(data.get('park'), old, problems)
                if problems:
                    raise StoreError('; '.join(problems))
            if current and action == 'complete' and old['mode'] == 'completion':
                problems = []
                marks = self._marks(task_id, data.get('items'), problems, required=False)
                if problems:
                    raise StoreError('; '.join(problems))
                self._close_items(task_id, marks, None)
                still = [row[0] for row in self.conn.execute("SELECT id FROM items WHERE task_id=? AND status='open' ORDER BY id", (task_id,))]
                if still:
                    raise StoreError('completion requires every acceptance item closed with evidence; still open: ' + ', '.join(still))
            self._fence(task_id)
            self.conn.execute('UPDATE tasks SET status=?,revision=revision+1,generation=generation+1,payload=?,updated_at=? WHERE id=?',
                              (states[action], json.dumps(payload), time.time(), task_id))
            if current:
                if action == 'block':
                    self._park_insert(self.task(task_id), park, None, data.get('actor', 'operator'), blocked=True)
                elif action == 'resume':
                    if parked:
                        self.conn.execute("UPDATE parks SET status='resumed' WHERE task_id=? AND status IN ('challenging','parked')", (task_id,))
                        self.operator_spoke(task_id)
                        self.conn.execute('UPDATE counters SET abandoned=0 WHERE task_id=?', (task_id,))
                        self._state(task_id, reactivated_park=parked['id'], limit_grace=True, reactivation_results=0)
                    self._claim(task_id, payload)
                    self.trigger(task_id, 'activated', {'resumed': True})
                else:
                    self._release(task_id)
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
                self._release(row['id'])
            self.audit('detach', binding_id, {'reason': reason, 'underlying_sessions_cancelled': False}, data.get('actor', 'operator'))
        return self.binding(binding_id)

    # ---- memory ----

    def add_memory(self, data):
        memory_id = data.get('id', str(uuid.uuid4()))
        text(memory_id, 'id')
        binding_id = text(data.get('supervisor_id'), 'supervisor_id')
        task_id = data.get('task_id')
        kind = data.get('kind')
        if kind not in ('fact', 'hypothesis', 'decision', 'correction', 'authorization', 'failure', 'intervention', 'next-action'):
            raise StoreError('invalid memory kind')
        if kind == 'decision' and not self.legacy:
            parts = {key: data.get(key) for key in ('what', 'why', 'undo')}
            if any(not isinstance(value, str) or not value.strip() for value in parts.values()):
                raise StoreError('a decision taken without the operator is recorded with what, why and undo')
            data = data | {'content': json.dumps(parts)}
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

    # ---- observation records ----

    def session(self, session_id):
        row = self.conn.execute('SELECT * FROM sessions WHERE session_id=?', (session_id,)).fetchone()
        if row is None:
            return None
        snapshot = json.loads(row['snapshot']) | {'session_id': session_id, 'runtime': row['runtime'],
                                                  'observed_at': row['observed_at'], 'stale_since': row['stale_since']}
        snapshot['state'] = session_state(snapshot)
        return snapshot

    def trigger(self, task_id, kind, data):
        """One pending trigger per kind and content; a trigger is pending until an execution carries it."""
        encoded = json.dumps(data, sort_keys=True, allow_nan=False)
        if self.conn.execute('SELECT 1 FROM triggers WHERE task_id=? AND kind=? AND data=? AND execution_id IS NULL', (task_id, kind, encoded)).fetchone():
            return False
        self.conn.execute('INSERT INTO triggers(task_id,kind,data,at) VALUES(?,?,?,?)', (task_id, kind, encoded, time.time()))
        return True

    def pending_triggers(self, task_id):
        rows = self.conn.execute('SELECT sequence,kind,data,at FROM triggers WHERE task_id=? AND execution_id IS NULL ORDER BY sequence', (task_id,)).fetchall()
        return [{'sequence': row['sequence'], 'kind': row['kind'], 'at': row['at'], **json.loads(row['data'])} for row in rows]

    def counters(self, task_id):
        row = self.conn.execute('SELECT * FROM counters WHERE task_id=?', (task_id,)).fetchone()
        result = dict(row)
        result['state'] = json.loads(result['state'])
        return result

    def _state(self, task_id, **changes):
        row = self.conn.execute('SELECT state FROM counters WHERE task_id=?', (task_id,)).fetchone()
        if row is None:
            return
        state = json.loads(row[0])
        for key, value in changes.items():
            if value is None:
                state.pop(key, None)
            else:
                state[key] = value
        self.conn.execute('UPDATE counters SET state=? WHERE task_id=?', (json.dumps(state), task_id))

    def delivery_add(self, client_id, session_id, kind, task_id, execution_id, body, state, latest_seconds, detail=None, now=None):
        now = time.time() if now is None else now
        self.conn.execute('INSERT OR REPLACE INTO deliveries VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                          (client_id, session_id, kind, task_id, execution_id, state, body, now, now + latest_seconds, None, None,
                           json.dumps(detail) if detail is not None else None))

    def delivery(self, client_id):
        row = self.conn.execute('SELECT * FROM deliveries WHERE client_id=?', (client_id,)).fetchone()
        return dict(row) if row else None

    # ---- spend and limits ----

    def spend(self, task):
        """Change in each cumulative counter since its baseline, over the supervisor, the targets and their workers."""
        limit = task['limits'].get('spend')
        unit = limit['unit'] if limit else 'tokens'
        binding = self.binding(task['supervisor_id'])
        bases = {row['session_id']: json.loads(row['usage']) for row in self.conn.execute('SELECT * FROM baselines WHERE task_id=?', (task['id'],))}
        total = dict.fromkeys(USAGE, 0)
        by_session, unknown = {}, []

        def add(ident, usage, unreadable):
            base = bases.get(ident)
            if unreadable or not usage or base is None:
                unknown.append(ident)
            if not usage or base is None:
                return
            delta = {key: max(0, usage[key] - base[key]) for key in USAGE}
            by_session[ident] = delta['total']
            for key in USAGE:
                total[key] += delta[key]

        for session_id in dict.fromkeys([binding['session_id'], *task['target_ids']]):
            snapshot = self.session(session_id) or {}
            unreadable = bool(snapshot.get('stale_since')) or 'usage' in snapshot.get('unknown', [])
            add(session_id, snapshot.get('usage'), unreadable)
            for worker, record in (snapshot.get('workers') or {}).items():
                add(worker, record.get('usage'), unreadable or 'workers' in snapshot.get('unknown', []))
        value = None
        if not unknown:
            if unit == 'tokens':
                value = total['total']
            elif unit == 'currency':
                table = limit['prices']
                value = ((total['input'] - total['cached_input']) * table['input'] + total['cached_input'] * table['cached_input']
                         + total['output'] * table['output']) / 1_000_000
        if unit == 'allowance_percent':
            tracker = self.counters(task['id'])['state'].get('allowance')
            value = None if not tracker else tracker['carried'] + tracker['last'] - tracker['base']
        # What could be read is a lower bound: a counter never falls, so a ceiling the bound has reached is reached.
        bound = total['total'] if unit == 'tokens' else value
        if unit == 'currency':
            table = limit['prices']
            bound = ((total['input'] - total['cached_input']) * table['input'] + total['cached_input'] * table['cached_input']
                     + total['output'] * table['output']) / 1_000_000
        if unknown and unit != 'allowance_percent':
            value = None
        result = {'unit': unit, 'value': value, 'lower_bound': bound, 'tokens': None if unknown else total['total'], 'unknown': unknown,
                  'last_read_tokens': total['total'], 'by_session': by_session}
        if limit:
            result.update(target=limit['target'], ceiling=limit['ceiling'], cites=limit['cites'],
                          fraction=None if value is None else value / limit['ceiling'])
        return result

    def limits_reached(self, task, now=None):
        """Operator limits the records show as reached: deadline, count, spend ceiling."""
        now = time.time() if now is None else now
        limits = task['limits']
        reached = []
        if limits.get('deadline_at') and now >= limits['deadline_at']['value']:
            reached.append({'limit': 'deadline', 'value': limits['deadline_at']['value'], 'cites': limits['deadline_at']['cites']})
        # An assessment counts when it has ended: the last one allowed is not cut off while it runs.
        checks = self.conn.execute(f"SELECT count(*) FROM executions WHERE task_id=? AND status NOT IN ({','.join('?' * len(OPEN_EXECUTIONS))})",
                                   (task['id'], *OPEN_EXECUTIONS)).fetchone()[0]
        if limits.get('max_checks') and checks >= limits['max_checks']['value']:
            reached.append({'limit': 'count', 'value': limits['max_checks']['value'], 'measured': checks, 'cites': limits['max_checks']['cites']})
        spend = self.spend(task)
        if limits.get('spend') and spend['lower_bound'] is not None and spend['lower_bound'] >= limits['spend']['ceiling']:
            reached.append({'limit': 'spend', 'value': limits['spend']['ceiling'], 'measured': spend['lower_bound'],
                            'at_least': bool(spend['unknown']), 'unit': spend['unit'], 'cites': limits['spend']['cites']})
        return reached

    # ---- parks ----

    def _park_checked(self, park, task, problems):
        authority, _ = modules()
        if not isinstance(park, dict):
            problems.append('outcome blocked is a park: give a park object with reason, questions, completed and cites')
            return None
        reason = park.get('reason')
        if reason not in authority.PARK_REASONS:
            problems.append(f'{reason!r} is not a reason to park ({", ".join(authority.PARK_REASONS)}): decide, proceed, '
                            'and record the decision with its undo')
            return None
        request = {'questions': []}
        try:
            questions = park.get('questions')
            if not isinstance(questions, list) or not questions:
                raise StoreError('park.questions must list at least one question')
            for question in questions:
                object_value(question, 'park.questions entry')
                options = strings(question.get('options'), 'park.questions.options')
                if len(options) < 2:
                    raise StoreError('each question offers at least two options')
                request['questions'].append({'matter': text(question.get('matter'), 'park.questions.matter'), 'options': options,
                                             'recommendation': text(question.get('recommendation'), 'park.questions.recommendation')})
            request['completed'] = text(park.get('completed'), 'park.completed')
            request['cites'] = authority.cites(park.get('cites'), 'park.cites', self.registered, required=reason == 'operator-restriction')
            if reason == 'ask-first':
                if park.get('item') not in task['ask_first']:
                    raise StoreError('park.item must name the ask-first entry the action falls under: ' + '; '.join(task['ask_first']))
                request['item'] = park['item']
        except StoreError as error:
            problems.append(str(error))
            return None
        counts = self.counters(task['id'])
        shown = {
            'limit-reached': lambda: bool(self.limits_reached(task)),
            'closure-bounds': lambda: counts['no_closure'] >= 2 or counts['step_reviews'] >= 1 and counts['step_closures'] >= task['limits']['step_bound'],
            'delivery-unresolved': lambda: counts['abandoned'] >= 2 or self.conn.execute(
                "SELECT 1 FROM deliveries WHERE task_id=? AND state='unresolved'", (task['id'],)).fetchone() is not None,
        }
        if reason in shown and not shown[reason]():
            problems.append(f'the records do not show {reason}: Python measures this reason itself and it is not true now')
            return None
        return {'reason': reason, 'request': request}

    def _park_insert(self, task, park, execution_id, actor, blocked=False):
        """Record the park and stop the clock in the caller's transaction."""
        authority, _ = modules()
        now = time.time()
        state = self.counters(task['id'])['state']
        previous = self.conn.execute('SELECT * FROM parks WHERE id=?', (state.get('reactivated_park'),)).fetchone() if state.get('reactivated_park') else None
        matters = lambda request: [question['matter'] for question in request['questions']]
        repeated = bool(previous) and previous['reason'] == park['reason'] and matters(json.loads(previous['request'])) == matters(park['request'])
        challenged = park['reason'] in authority.CHALLENGED and not repeated and actor != 'review'
        park_id = str(uuid.uuid4())
        self.conn.execute('INSERT INTO parks VALUES(?,?,?,?,?,?,?,?,?,?)',
                          (park_id, task['id'], execution_id, park['reason'], json.dumps(park['request']),
                           'challenging' if challenged else 'parked', previous['positions'] if repeated else '[]',
                           previous['question_id'] if repeated else None, now, None if challenged else now))
        if not blocked:
            self._fence(task['id'])
            self.conn.execute("UPDATE tasks SET status='blocked',revision=revision+1,generation=generation+1,updated_at=? WHERE id=?", (now, task['id']))
        self._state(task['id'], reactivated_park=None, limit_grace=None)
        self.audit('park', park_id, {'task_id': task['id'], 'reason': park['reason'], 'repeated': repeated, 'challenged': challenged}, actor)
        return park_id

    def park(self, task_id, reason, questions, completed, actor='scheduler', execution_id=None):
        """A park Python decides from its own measurements."""
        task = self.task(task_id)
        if task['status'] != 'active':
            return None
        return self._park_insert(task, {'reason': reason, 'request': {'questions': questions, 'completed': completed, 'cites': []}}, execution_id, actor)

    def reactivate(self, task_id, reference):
        """An operator message makes a parked task active again, for one assessment that receives it."""
        park = self.conn.execute("SELECT id FROM parks WHERE task_id=? AND status IN ('challenging','parked') ORDER BY created_at DESC", (task_id,)).fetchone()
        self.conn.execute("UPDATE parks SET status='reactivated' WHERE task_id=? AND status IN ('challenging','parked')", (task_id,))
        self.conn.execute("UPDATE tasks SET status='active',revision=revision+1,updated_at=? WHERE id=? AND status='blocked'", (time.time(), task_id))
        self._state(task_id, reactivated_park=park['id'] if park else None, limit_grace=True, reactivation_results=0)
        self.audit('task-reactivate', task_id, {'operator_message': reference, 'park': park['id'] if park else None}, 'scheduler')

    def operator_spoke(self, task_id):
        self.conn.execute('UPDATE counters SET no_closure=0,step_closures=0,step_reviews=0,rejections=0 WHERE task_id=?', (task_id,))

    # ---- assessment results ----

    def _marks(self, task_id, marks, problems, required=True):
        """Item marks of a result: {id: (status, evidence)}; every item is required in an assessment result."""
        items = {row['id']: dict(row) for row in self.conn.execute("SELECT * FROM items WHERE task_id=? AND status!='dropped'", (task_id,))}
        found = {}
        if marks is None and not required:
            return found
        if not isinstance(marks, list):
            problems.append('items must mark every acceptance item open or closed: ' + ', '.join(sorted(items)))
            return found
        for mark in marks:
            if not isinstance(mark, dict) or mark.get('id') not in items or mark.get('status') not in ('open', 'closed'):
                problems.append('each items entry needs an id of this task and status open or closed')
                continue
            evidence = mark.get('evidence', [])
            if mark['status'] == 'closed' and (not isinstance(evidence, list) or not evidence or any(not isinstance(x, str) or not x.strip() for x in evidence)):
                problems.append(f"item {mark['id']} is closed without evidence")
                continue
            found[mark['id']] = (mark['status'], evidence if mark['status'] == 'closed' else [])
        missing = sorted(set(items) - set(found))
        if required and missing:
            problems.append('items missing from the result: ' + ', '.join(missing))
        return found

    def _close_items(self, task_id, marks, execution_id):
        """Apply item marks; return how many closures are new. A closure counts once."""
        now = time.time()
        new = 0
        for ident, (status, evidence) in marks.items():
            if status == 'closed':
                self.conn.execute("UPDATE items SET status='closed',evidence=?,closed_at=? WHERE task_id=? AND id=?", (json.dumps(evidence), now, task_id, ident))
                new += self.conn.execute('INSERT OR IGNORE INTO closures VALUES(?,?,?,?,?)', (task_id, 'item', ident, execution_id, now)).rowcount
            else:
                self.conn.execute("UPDATE items SET status='open',closed_at=NULL WHERE task_id=? AND id=?", (task_id, ident))
        return new

    def _wait_checked(self, entry, targets, problems, now):
        condition = entry.get('condition')
        kind = condition.get('kind') if isinstance(condition, dict) else None
        if kind == 'operator':
            problems.append('a wait on the operator is a park: use outcome blocked with a park')
            return None
        try:
            if entry.get('session_id') not in targets:
                raise StoreError('a wait names one of the task targets')
            if kind == 'time':
                condition = {'kind': 'time', 'at': timestamp(condition.get('at'), 'wait.condition.at')}
            elif kind == 'file':
                path = text(condition.get('path'), 'wait.condition.path')
                if not Path(path).is_absolute():
                    raise StoreError('wait.condition.path must be absolute')
                condition = {'kind': 'file', 'path': path}
            elif kind == 'process':
                condition = {'kind': 'process', 'pid': number(condition.get('pid'), 'wait.condition.pid')}
            else:
                raise StoreError('a wait condition is a time, a file or a process exit that Python can observe')
            latest = timestamp(entry.get('latest_at'), 'wait.latest_at')
            if latest <= now or kind == 'time' and latest < condition['at']:
                raise StoreError('wait.latest_at must lie in the future and not before the awaited time')
        except StoreError as error:
            problems.append(str(error))
            return None
        return {'session_id': entry['session_id'], 'condition': condition, 'latest_at': latest}

    def _close_assessment(self, row, task, data):
        """Validate and apply a completion result. Every reason for refusal is reported together."""
        now = time.time()
        task_id = task['id']
        problems = []
        outcome = data['outcome']
        marks = self._marks(task_id, data.get('items'), problems)
        items = {r['id']: dict(r) for r in self.conn.execute("SELECT * FROM items WHERE task_id=? AND status!='dropped'", (task_id,))}
        after = {ident: marks.get(ident, (item['status'],))[0] for ident, item in items.items()}
        open_owners = {items[ident]['owner'] for ident, status in after.items() if status == 'open'}
        if items and not open_owners and not problems:
            problems.append('every acceptance item is closed: conclude the task with task-state complete, passing the same items, '
                            'instead of recording another assessment')
        known = {r['id']: dict(r) for r in self.conn.execute('SELECT * FROM steps WHERE task_id=?', (task_id,))}
        declared, named = [], set()
        entries = data.get('steps', [])
        if not isinstance(entries, list):
            problems.append('steps must be a list')
            entries = []
        for entry in entries:
            try:
                object_value(entry, 'steps entry')
                session = identity(entry.get('session_id'), 'steps.session_id')
                if session not in task['target_ids']:
                    raise StoreError('a step belongs to one of the task targets')
                if entry.get('id') is not None:
                    step = known.get(entry['id'])
                    if not step or step['status'] != 'open' or step['session_id'] != session:
                        raise StoreError(f"step {entry['id']} is not an open step of that target")
                else:
                    artifact = text(entry.get('artifact'), 'steps.artifact')
                    if not Path(artifact).is_absolute():
                        raise StoreError('steps.artifact must be the absolute path of the file that will show the step done')
                    declared.append({'session_id': session, 'description': text(entry.get('description'), 'steps.description'),
                                     'artifact': artifact, 'estimate_seconds': number(entry.get('estimate_seconds'), 'steps.estimate_seconds')})
                named.add(session)
            except StoreError as error:
                problems.append(str(error))
        for owner in sorted(open_owners - named - {None}):
            problems.append(f'steps must name the step target {owner} is on, the artifact that will show it done, and its estimate')
        closed_steps, kept_open = [], []
        requested = data.get('steps_closed', [])
        if not isinstance(requested, list):
            problems.append('steps_closed must be a list of step ids')
            requested = []
        for ident in requested:
            step = known.get(ident)
            if not step or step['status'] != 'open':
                problems.append(f'step {ident} is not an open step')
                continue
            try:
                modified = os.stat(step['artifact']).st_mtime
            except OSError:
                modified = None
            if modified is None:
                kept_open.append({'id': ident, 'why': 'its artifact does not exist'})
            elif modified <= step['declared_at']:
                kept_open.append({'id': ident, 'why': 'its artifact is older than the declaration'})
            else:
                closed_steps.append(ident)
        park, waits = None, []
        closing_set = json.loads(row['closing_set'] or '[]')
        if outcome == 'blocked':
            park = self._park_checked(data.get('park'), task, problems)
        else:
            closing = data.get('closing', [])
            if not isinstance(closing, list) or any(not isinstance(entry, dict) for entry in closing):
                problems.append('closing must be a list of objects')
                closing = []
            by_session = {}
            for entry in closing:
                by_session[entry.get('session_id')] = entry
                if entry.get('kind') == 'wait':
                    wait = self._wait_checked(entry, task['target_ids'], problems, now)
                    if wait:
                        waits.append(wait)
            waiting_for = {wait['session_id'] for wait in waits}
            for member in closing_set:
                session = member['session_id']
                if session not in open_owners:
                    continue
                entry = by_session.get(session) or {}
                accepted = session in waiting_for
                if entry.get('kind') == 'intervention' and member['state'] == 'idle':
                    delivery = self.delivery(entry.get('event_id')) or {}
                    accepted = (delivery.get('execution_id') == row['id'] and delivery.get('session_id') == session
                                and delivery.get('state') in ('queued', 'consumed'))
                if not accepted and not (entry.get('kind') == 'wait' and session not in waiting_for):
                    problems.append(FOUR.format(session=session, state=member['state'])
                                    + ('' if member['state'] == 'idle' else '; a message cannot reach it now, so an intervention does not close it'))
        new_item_marks = sum(1 for ident, (status, _) in marks.items() if status == 'closed'
                             and not self.conn.execute("SELECT 1 FROM closures WHERE task_id=? AND kind='item' AND ref=?", (task_id, ident)).fetchone())
        closes = new_item_marks + len(closed_steps)
        counts = self.counters(task_id)
        raises = outcome != 'blocked' and not row['working'] and not closes and not waits
        allowed = counts['state'].get('allowed_action') and any(entry.get('kind') == 'intervention' for entry in data.get('closing', []) if isinstance(entry, dict))
        # At the bound a wait is no way on: only a park or a conclusion follows two results that closed nothing.
        if outcome != 'blocked' and not row['working'] and not closes and counts['no_closure'] >= 2 and not allowed:
            problems.append('two assessments in a row closed nothing while no target was working: this one is accepted only as a park '
                            '(outcome blocked with reason closure-bounds) or the task is concluded')
        if problems:
            raise StoreError('; '.join(dict.fromkeys(problems)))
        closed_items = self._close_items(task_id, marks, row['id'])
        number_of = len(known)
        declared_ids = []
        for step in declared:
            self.conn.execute("UPDATE steps SET status='superseded' WHERE task_id=? AND session_id=? AND status='open'", (task_id, step['session_id']))
            number_of += 1
            declared_ids.append(f'S{number_of}')
            self.conn.execute('INSERT INTO steps VALUES(?,?,?,?,?,?,?,?,?,?,?)', (task_id, declared_ids[-1], step['session_id'], step['description'],
                              step['artifact'], step['estimate_seconds'], now, row['id'], 'open', None, '{}'))
        for ident in closed_steps:
            self.conn.execute("UPDATE steps SET status='closed',closed_at=? WHERE task_id=? AND id=?", (now, task_id, ident))
            self.conn.execute('INSERT OR IGNORE INTO closures VALUES(?,?,?,?,?)', (task_id, 'step', ident, row['id'], now))
        for wait in waits:
            self.conn.execute('INSERT INTO waits VALUES(?,?,?,?,?,?,?,?,?)', (str(uuid.uuid4()), task_id, wait['session_id'], row['id'],
                              json.dumps(wait['condition']), wait['latest_at'], 'pending', now, None))
        if closed_items:
            self.conn.execute('UPDATE counters SET no_closure=0,step_closures=0,step_reviews=0,rejections=0 WHERE task_id=?', (task_id,))
        elif closed_steps:
            self.conn.execute('UPDATE counters SET no_closure=0,rejections=0,step_closures=step_closures+? WHERE task_id=?', (len(closed_steps), task_id))
        elif raises:
            self.conn.execute('UPDATE counters SET no_closure=no_closure+1 WHERE task_id=?', (task_id,))
        self.conn.execute('UPDATE counters SET abandoned=0 WHERE task_id=?', (task_id,))
        results = counts['state'].get('reactivation_results')
        self._state(task_id, allowed_action=None, limit_grace=None,
                    reactivation_results=None if results is None else results + 1,
                    reactivated_park=None if closes or results else counts['state'].get('reactivated_park'))
        counts = self.counters(task_id)
        effect = {'closures': closed_items + len(closed_steps), 'steps_declared': declared_ids, 'steps_kept_open': kept_open,
                  'no_closure_count': counts['no_closure'], 'step_closures': counts['step_closures']}
        if park:
            effect['park'] = park
        elif counts['step_closures'] >= task['limits']['step_bound']:
            # Steps close and no acceptance item does: a convergence review first, a park the second time.
            if counts['step_reviews'] == 0:
                self.conn.execute('UPDATE counters SET step_reviews=1,step_closures=0 WHERE task_id=?', (task_id,))
                self.review_request(task_id, 'convergence', 'step-bound')
                effect['convergence_review'] = 'step-bound'
            else:
                effect['park'] = {'reason': 'closure-bounds', 'request': {'cites': [], 'questions': [{
                    'matter': f"Steps keep closing on task {task_id} and no acceptance item closes, after a convergence review already ran.",
                    'options': ['Continue with a new instruction on what to cut', 'Stop the task'],
                    'recommendation': 'Say what to cut or which acceptance item to drop.'}],
                    'completed': f"{counts['step_closures']} more steps closed since that review; no acceptance item closed."}}
                effect['python_park'] = True
        return effect

    def review_request(self, task_id, kind, reason, park_id=None):
        """One open review per task, kind and reason; the tick launches it."""
        if self.conn.execute("SELECT 1 FROM reviews WHERE task_id=? AND kind=? AND reason=? AND IFNULL(park_id,'')=IFNULL(?,'') AND status IN ('requested','running')",
                             (task_id, kind, reason, park_id)).fetchone():
            return None
        review_id = str(uuid.uuid4())
        self.conn.execute('INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?,?,?)', (review_id, task_id, kind, park_id, reason, 'requested', None, time.time(), None, None, None))
        return review_id

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
            effect = {}
            if task.get('contract') == 2:
                if task['mode'] == 'completion':
                    effect = self._close_assessment(row, task, data)
                elif outcome == 'blocked':
                    problems = []
                    effect = {'park': self._park_checked(data.get('park'), task, problems)}
                    if problems:
                        raise StoreError('; '.join(problems))
                self.conn.execute('UPDATE counters SET abandoned=0 WHERE task_id=?', (task['id'],))
                self._state(task['id'], limit_grace=None)
            self.conn.execute('UPDATE executions SET status=?,finished_at=?,result=? WHERE id=?',
                              (outcome, time.time(), json.dumps(result), execution_id))
            park = effect.pop('park', None)
            python = effect.pop('python_park', False)
            changed = False
            if park:
                effect['park_id'] = self._park_insert(task, park, execution_id, 'scheduler' if python else data.get('actor', 'supervisor'))
                changed = True
            self.audit('execution-result', execution_id, result | effect, data.get('actor', 'supervisor'))
        return {'id': execution_id, **result, **effect, 'task_state_changed': changed}

    # ---- status ----

    def measured(self, task_id):
        """What Python recorded about a task, readable without any session's history."""
        task = self.task(task_id)
        binding = self.binding(task['supervisor_id'])
        sessions = {}
        for session_id in dict.fromkeys([binding['session_id'], *task['target_ids'], task['operator_session_id']]):
            snapshot = self.session(session_id)
            sessions[session_id] = None if snapshot is None else {key: snapshot.get(key) for key in (
                'state', 'status', 'flags', 'running_turn', 'last_turn', 'queue', 'unknown', 'observed_at', 'stale_since')}
        rows = lambda query, *args: [dict(row) for row in self.conn.execute(query, args)]
        counts = self.counters(task_id)
        parks = rows('SELECT id,reason,status,request,positions,question_id,created_at,effective_at FROM parks WHERE task_id=? ORDER BY created_at', task_id)
        for park in parks:
            park['request'], park['positions'] = json.loads(park['request']), json.loads(park['positions'])
        decisions = [dict(row) for row in self.conn.execute("SELECT id,content,source,created_at FROM memory m WHERE task_id=? AND kind='decision' AND NOT EXISTS(SELECT 1 FROM memory n WHERE n.supersedes=m.id) ORDER BY created_at", (task_id,))]
        items = rows('SELECT id,owner,text,status,evidence,closed_at FROM items WHERE task_id=? ORDER BY id', task_id)
        waits = rows("SELECT id,session_id,condition,latest_at,status FROM waits WHERE task_id=? AND status='pending' ORDER BY created_at", task_id)
        reviews = rows('SELECT id,kind,reason,status,started_at,finished_at,verdict,tokens FROM reviews WHERE task_id=? ORDER BY started_at', task_id)
        for row, key in [(row, 'evidence') for row in items] + [(row, 'condition') for row in waits] + [(row, 'verdict') for row in reviews]:
            row[key] = json.loads(row[key]) if row[key] else None
        interrupts = [json.loads(row['data']) | {'session_id': row['session_id'], 'at': row['at']}
                      for row in self.conn.execute("SELECT * FROM observations WHERE kind='interrupt' ORDER BY sequence")]
        interrupts = [entry for entry in interrupts if entry.get('task_id') == task_id]
        # A limit stops admission; where the runtime could not interrupt a running turn, that turn continues and status says so.
        continuing = [entry for entry in interrupts if entry['status'] in ('continues', 'requested') and entry.get('turn_id') is not None
                      and ((sessions.get(entry['session_id']) or {}).get('running_turn') or {}).get('id') == entry['turn_id']]
        return {
            'items': items,
            'steps': rows('SELECT id,session_id,description,artifact,estimate_seconds,declared_at,status,closed_at FROM steps WHERE task_id=? ORDER BY declared_at,id', task_id),
            'counts': {key: counts[key] for key in ('no_closure', 'step_closures', 'step_reviews', 'rejections', 'abandoned')},
            'sessions': sessions,
            'deliveries': rows('SELECT client_id,session_id,kind,state,sent_at,latest_at,consumed_at,turn_id,execution_id FROM deliveries WHERE task_id=? ORDER BY sent_at', task_id),
            'spend': self.spend(task),
            'limits_reached': self.limits_reached(task),
            'interrupts': interrupts,
            'turns_continuing': continuing,
            'parks': parks,
            'open_questions': [park for park in parks if park['status'] in ('challenging', 'parked')],
            'triggers': self.pending_triggers(task_id),
            'waits': waits,
            'reviews': reviews,
            'decisions': decisions,
            'ledger': self.ledger_path,
        }

    def status(self, task_id=None):
        if task_id is not None:
            task = self.task(task_id)
            if task.get('contract') == 2:
                return task | {'measured': self.measured(task_id)}
            return task | {'legacy_contract': True, 'remedy': LEGACY}
        tick = self.conn.execute("SELECT details FROM audit WHERE action='tick' AND actor='scheduler' ORDER BY sequence DESC LIMIT 1").fetchone()
        last_tick = json.loads(tick['details'])['at'] if tick else None
        age = max(0, time.time() - last_tick) if last_tick is not None else None
        activation = self.conn.execute("SELECT max(updated_at) FROM bindings WHERE status='active'").fetchone()[0]
        active = activation is not None
        scheduler_state = 'dormant' if not active else ('active' if age is not None and age <= 180 else 'overdue')
        if active and last_tick is None and max(0, time.time() - activation) <= 180:
            scheduler_state = 'waiting-first-tick'
        tasks = [self.task(row[0]) for row in self.conn.execute('SELECT id FROM tasks ORDER BY id')]
        for task in tasks:
            if task.get('contract') != 2:
                task.update(legacy_contract=True, remedy=LEGACY)
        return {'schema_version': 1 if self.legacy else SCHEMA_VERSION,
                'bindings': [self.binding(row[0]) for row in self.conn.execute('SELECT id FROM bindings ORDER BY id')],
                'tasks': tasks,
                'executions': [dict(row) for row in self.conn.execute('SELECT * FROM executions ORDER BY scheduled_at,id')],
                'outbox': [dict(row) for row in self.conn.execute('SELECT * FROM outbox ORDER BY created_at,id')],
                'health': {'scheduler': {'state': scheduler_state, 'last_tick_at': last_tick, 'age_seconds': age, 'grace_seconds': 180},
                           'attention': [dict(row) for row in self.conn.execute("SELECT id,task_id,status,result FROM executions WHERE status IN ('unhealthy','uncertain','not-delivered') OR (status='pending' AND json_extract(result,'$.dispatch_wait_overdue')=1)")]}}
