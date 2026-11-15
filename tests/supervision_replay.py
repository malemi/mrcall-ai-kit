"""Replay tool for the supervision controller repair (M2).

Drives the real controller code (shared/supervision/*) with the state the retained
records show at chosen past moments, and reports what that code decides. Every
source is opened read-only; the tool's own working state lives in a temporary
directory it deletes at exit. It prints derived facts only: counts, ordinals,
times, identifiers, origin classes and refusal reasons this repository's own
code produced. It never prints message text, prompts, instructions, summaries
or `remaining` text, never writes to a record, never contacts a session, never
opens a network connection and never calls a model.

Usage: python3 tests/supervision_replay.py --scenario {incident,m6,goal}
Run from the repository root, or any directory: paths below are absolute.
"""
import argparse
import datetime
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HOME = Path.home()
EVIDENCE_DIR = HOME / '.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/exports'
INCIDENT_DB = EVIDENCE_DIR / 'supervision-three-session-20261110.sqlite3'
REMOTE_DB = EVIDENCE_DIR / 'supervision-remote-problemi5-20261105.sqlite3'
PROBLEMI5_DB = EVIDENCE_DIR / 'supervision-problemi5-20261105.sqlite3'
OBSERVE_PROB3_DB = EVIDENCE_DIR / 'supervision-observe-prob3.sqlite3'
M6_STATE = HOME / '.local/state/mrcall-ai-kit/supervision-m6-01a1d4fb-ebcb-74d2-92e2-686eed6ace7d/state.sqlite3'
GOALS_DB = HOME / '.local/state/mrcall-ai-kit/goals/state/goals.sqlite3'
SESSIONS_DIR = HOME / '.codex/sessions'

LEAD = '01a1ab51-13f9-7ab2-92df-fcedeb2b53bb'
REMOTE = '01a13069-ea38-7fe3-af86-57883ec8d4fd'
MEMORY = '01a14013-28db-7b71-be70-c2aff5456a6e'
INCIDENT_SUPERVISOR = '01a181e1-f7cd-7a50-8111-c25e0bfd044d'
M6_SUPERVISOR = '01a1d4fb-ebcb-74d2-92e2-686eed6ace7d'
ROLE_OF = {LEAD: 'lead', REMOTE: 'REMOTE', MEMORY: 'MEMORY'}

LINE_MARKERS = ('"task_started"', '"task_complete"', '"turn_aborted"', '"item_completed"',
                 '"token_usage_record"', '"token_count"')


def parse_iso(value):
    if value is None:
        return None
    return datetime.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def ro(path):
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


# ---------------------------------------------------------------------------
# Rollout reading (read-only; a large file is read once, line by line, with a
# substring test before json.loads).
# ---------------------------------------------------------------------------

class SessionData:
    def __init__(self, session_id):
        self.session_id = session_id
        self.root_id = None
        self.created_at = None
        self.by_turn = {}            # turn_id -> turn dict
        self.messages_by_turn = {}   # turn_id -> [message dict]
        self.usage_series = []       # [(at, usage dict)]
        self.allowance_series = []   # [(at, allowance dict)]
        self.client_first_at = {}    # client_id -> earliest at it appears as a user message
        self.files = []

    def finalize(self):
        self.turns = sorted(self.by_turn.values(), key=lambda t: t['started_at'])
        self.usage_series.sort(key=lambda pair: pair[0])
        self.allowance_series.sort(key=lambda pair: pair[0])
        for messages in self.messages_by_turn.values():
            for message in messages:
                at = message['at']
                cid = message['client_id']
                if cid and (cid not in self.client_first_at or at < self.client_first_at[cid]):
                    self.client_first_at[cid] = at

    def at_or_before(self, series, now):
        chosen = None
        for at, value in series:
            if at <= now:
                chosen = value
            else:
                break
        return chosen


def open_lines(path):
    path = Path(path)
    if path.suffix == '.zst':
        process = subprocess.run(['zstd', '-dc', str(path)], capture_output=True)
        return process.stdout.decode('utf-8', errors='replace').splitlines(keepends=True)
    return path.open('r', errors='replace')


def load_rollout_file(path, into):
    """Parse one rollout file into `into` (dict session_id -> SessionData); read-only."""
    lines = open_lines(path)
    first = True
    data = None
    for raw in lines:
        if first:
            first = False
            if '"session_meta"' not in raw:
                return None
            try:
                rec = json.loads(raw)
            except ValueError:
                return None
            if rec.get('type') != 'session_meta':
                return None
            payload = rec.get('payload') or {}
            sid = payload.get('id')
            if not sid:
                return None
            data = into.setdefault(sid, SessionData(sid))
            data.root_id = payload.get('session_id')
            ts = parse_iso(payload.get('timestamp') or rec.get('timestamp'))
            if data.created_at is None or (ts is not None and ts < data.created_at):
                data.created_at = ts
            data.files.append(str(path))
            continue
        if not any(marker in raw for marker in LINE_MARKERS):
            continue
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        rtype = rec.get('type')
        payload = rec.get('payload') or {}
        ts = parse_iso(rec.get('timestamp'))
        if rtype == 'token_usage_record':
            usage = payload.get('thread_token_usage')
            if usage and ts is not None:
                data.usage_series.append((ts, {'input': usage.get('input_tokens', 0),
                                                'cached_input': usage.get('cached_input_tokens', 0),
                                                'output': usage.get('output_tokens', 0),
                                                'total': usage.get('total_tokens', 0), 'at': ts}))
        elif rtype == 'event_msg':
            ptype = payload.get('type')
            if ptype == 'task_started':
                tid = payload.get('turn_id')
                started = payload.get('started_at')
                started = float(started) if started is not None else ts
                data.by_turn[tid] = {'id': tid, 'started_at': started, 'completed_at': None, 'status': 'inProgress'}
            elif ptype == 'task_complete':
                tid = payload.get('turn_id')
                turn = data.by_turn.get(tid)
                if turn is None:
                    turn = data.by_turn[tid] = {'id': tid, 'started_at': ts, 'completed_at': None, 'status': 'inProgress'}
                turn['completed_at'] = ts
                turn['status'] = 'completed'
            elif ptype == 'turn_aborted':
                tid = payload.get('turn_id')
                started = payload.get('started_at')
                completed = payload.get('completed_at')
                turn = data.by_turn.get(tid)
                if turn is None:
                    turn = data.by_turn[tid] = {'id': tid, 'started_at': float(started) if started is not None else ts,
                                                 'completed_at': None, 'status': 'inProgress'}
                turn['completed_at'] = float(completed) if completed is not None else ts
                turn['status'] = 'aborted'
            elif ptype == 'token_count':
                primary = (payload.get('rate_limits') or {}).get('primary')
                if primary and ts is not None:
                    data.allowance_series.append((ts, {'used_percent': primary.get('used_percent'),
                                                        'window_minutes': primary.get('window_minutes'),
                                                        'resets_at': primary.get('resets_at'),
                                                        'plan_type': (payload.get('rate_limits') or {}).get('plan_type'),
                                                        'at': ts}))
            elif ptype == 'item_completed':
                item = payload.get('item') or {}
                if item.get('type') == 'UserMessage':
                    tid = payload.get('turn_id')
                    started_ms = payload.get('started_at_ms')
                    at = (started_ms / 1000.0) if started_ms is not None else ts
                    text = ''.join(part.get('text', '') for part in (item.get('content') or []) if part.get('type') == 'text')
                    data.messages_by_turn.setdefault(tid, []).append(
                        {'id': item.get('id'), 'turn_id': tid, 'client_id': item.get('client_id'), 'at': at,
                         'text': text, 'inter_agent': False})
    return data


def find_root_files(root_id):
    """Every rollout file that IS this thread's own (not a worker whose filename merely names its root):
    the filename ends with -<root_id>.jsonl or -<root_id>.jsonl.zst, with no trailing _<worker id>."""
    found = []
    for path in SESSIONS_DIR.rglob('rollout-*'):
        name = path.name
        if name.endswith(f'-{root_id}.jsonl') or name.endswith(f'-{root_id}.jsonl.zst'):
            found.append(path)
    return sorted(found)


def load_sessions(wanted_ids):
    """Load every rollout file that is one of `wanted_ids`'s own thread, read-only, wherever it lives;
    a thread can have more than one file (a resumed session), merged here in filename order."""
    into = {}
    for root_id in wanted_ids:
        for path in find_root_files(root_id):
            load_rollout_file(path, into)
    for sid in list(into):
        into[sid].finalize()
    return {sid: data for sid, data in into.items() if sid in wanted_ids}


def discover_workers(day_dirs, root_id):
    """Rollouts whose header names `root_id` as their own root; read-only, header peek first."""
    workers = {}
    for day in day_dirs:
        directory = SESSIONS_DIR / day
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.name.startswith('rollout-'):
                continue
            into = {}
            data = load_rollout_file(path, into)
            if data is None or data.root_id != root_id or data.session_id == root_id:
                continue
            data.finalize()
            workers[data.session_id] = data
    return workers


# ---------------------------------------------------------------------------
# The replay transport
# ---------------------------------------------------------------------------

class ReplayTransport:
    """Everything it returns is what the records show at `self.now`. `send` and
    `interrupt` record the call and change nothing; nothing here calls a model
    or opens a network connection."""

    def __init__(self, sessions, sends, workers_by_root):
        self.sessions = sessions              # session_id -> SessionData
        self.sends = sends                    # session_id -> sorted [(client_id, sent_at)]
        self.workers_by_root = workers_by_root  # root_id -> {worker_id: SessionData}
        self.now = 0.0
        self.calls = []
        self.sent = []
        self.interrupted = []

    def _queue(self, session_id):
        data = self.sessions.get(session_id)
        sends = self.sends.get(session_id, [])
        queue = []
        for client_id, sent_at in sends:
            if sent_at > self.now:
                continue
            first_at = (data.client_first_at.get(client_id) if data else None)
            if first_at is not None and first_at <= self.now:
                continue
            queue.append({'id': client_id, 'client_id': client_id})
        return queue

    def observe(self, session_id, cursor=None, workers_since=None, history_turns=30):
        self.calls.append(('observe', session_id))
        data = self.sessions.get(session_id)
        if data is None:
            return {'id': session_id, 'status': 'idle', 'flags': [], 'can_accept_input': True, 'parent_id': None,
                    'queue': self._queue(session_id), 'turns': [], 'messages': [], 'usage': None, 'allowance': None,
                    'workers': [], 'unknown': ['usage', 'allowance', 'messages'], 'cursor': cursor}
        # A turn, once reported ended, is tracked by id (not by sequence position): a turn that never
        # closes (the records show at least one) must not block later, already-closed turns from ever
        # being recognized as closed.
        cursor = cursor or {'ended': [], 'seen': []}
        already_ended = set(cursor.get('ended', []))
        visible = [turn for turn in data.turns if turn['started_at'] <= self.now]
        adjusted = []
        newly_ended = set()
        for turn in visible:
            if turn['completed_at'] is not None and turn['completed_at'] <= self.now:
                if turn['id'] in already_ended:
                    continue
                adjusted.append(dict(turn))
                newly_ended.add(turn['id'])
            else:
                adjusted.append(dict(turn, status='inProgress', completed_at=None))
        status = 'active' if any(t['status'] == 'inProgress' for t in adjusted) else 'idle'
        seen = set(cursor['seen'])
        messages = []
        for turn in adjusted:
            for item in data.messages_by_turn.get(turn['id'], []):
                if item['id'] in seen or item['at'] > self.now:
                    continue
                messages.append(dict(item))
        new_seen = seen | {m['id'] for m in messages}
        usage = data.at_or_before(data.usage_series, self.now)
        allowance = data.at_or_before(data.allowance_series, self.now)
        workers = []
        if workers_since is not None:
            for worker_id, worker in self.workers_by_root.get(session_id, {}).items():
                if worker.created_at is not None and worker.created_at > self.now:
                    continue  # does not exist yet as of `now`
                usage_w = worker.at_or_before(worker.usage_series, self.now)
                workers.append({'id': worker_id, 'usage': usage_w, 'created_at': worker.created_at})
        return {'id': session_id, 'status': status, 'flags': [], 'can_accept_input': True, 'parent_id': None,
                'queue': self._queue(session_id), 'turns': [dict(t) for t in adjusted], 'messages': messages,
                'usage': usage, 'allowance': allowance, 'workers': workers, 'unknown': [],
                'cursor': {'ended': sorted(already_ended | newly_ended), 'seen': sorted(new_seen)}}

    def metadata(self, session_id):
        self.calls.append(('metadata', session_id))
        data = self.sessions.get(session_id)
        status = 'idle'
        if data:
            for turn in data.turns:
                if turn['started_at'] <= self.now and (turn['completed_at'] is None or turn['completed_at'] > self.now):
                    status = 'active'
        return {'id': session_id, 'status': {'type': status}, 'parentThreadId': None, 'canAcceptDirectInput': True}

    def send(self, session_id, event_id, body, allow_busy=False):
        self.calls.append(('send', session_id, event_id))
        self.sent.append((session_id, event_id))
        return {'status': 'delivered', 'native_submission_id': 'replay-' + event_id[:8]}

    def reconcile(self, session_id, event_id, **_):
        self.calls.append(('reconcile', session_id, event_id))
        return {'status': 'delivered'}

    def read(self, session_id, **kwargs):
        self.calls.append(('read', session_id))
        return {'thread': {'id': session_id}, 'turns': [], 'next_cursor': None, 'reverse_cursor': None}

    def interrupt(self, session_id, turn_id):
        self.calls.append(('interrupt', session_id, turn_id))
        self.interrupted.append((session_id, turn_id))
        return {'status': 'interrupted', 'thread_id': session_id, 'turn_id': turn_id}


def load_sends(db_paths):
    """Every kit send known from these state roots: session -> sorted [(client_id, sent_at)]."""
    sends = {}
    for path in db_paths:
        if not Path(path).exists():
            continue
        conn = ro(path)
        try:
            bind_session = {row[0]: row[1] for row in conn.execute('SELECT id, session_id FROM bindings')}
            for client_id, created_at, supervisor_id in conn.execute(
                    'SELECT o.client_message_id, o.created_at, e.supervisor_id FROM outbox o '
                    'JOIN executions e ON o.execution_id = e.id'):
                session = bind_session.get(supervisor_id)
                if session:
                    sends.setdefault(session, []).append((client_id, created_at))
            intents, results = {}, {}
            for entity_id, at, details in conn.execute("SELECT entity_id, at, details FROM audit WHERE action='intervention-intent'"):
                intents[entity_id] = (at, json.loads(details).get('session_id'))
            for entity_id, at, details in conn.execute(
                    "SELECT entity_id, at, details FROM audit WHERE action='intervention-result' ORDER BY sequence"):
                results[entity_id] = json.loads(details).get('status')
            for entity_id, (at, session) in intents.items():
                if session and results.get(entity_id) in ('delivered', 'uncertain'):
                    sends.setdefault(session, []).append((entity_id, at))
        finally:
            conn.close()
    for session in sends:
        sends[session] = sorted(set(sends[session]), key=lambda pair: pair[1])
    return sends


# ---------------------------------------------------------------------------
# Common setup: isolated ledger + kit home, ledger backfilled from real roots
# ---------------------------------------------------------------------------

class Replay:
    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix='supervision-replay-')
        os.environ['MRCALL_SUPERVISION_LEDGER'] = str(Path(self.tmp) / 'ledger.sqlite3')
        os.environ['MRCALL_KIT_HOME'] = str(Path(self.tmp) / 'kit')
        os.environ.pop('MRCALL_SUPERVISION_REVIEW_COMMAND', None)
        (Path(self.tmp) / 'kit').mkdir(parents=True, exist_ok=True)
        (Path(self.tmp) / 'kit/supervision.json').write_text(json.dumps(
            {'default_spend_limit': {'unit': 'tokens', 'target': 10**12, 'ceiling': 10**12}}))
        self.assumptions = []
        self.notes = []

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def backfill_result(self):
        roots = Path(self.tmp) / 'roots'
        roots.mkdir(parents=True, exist_ok=True)
        mapping = {'incident': INCIDENT_DB, 'remote-problemi5': REMOTE_DB, 'problemi5': PROBLEMI5_DB,
                   'observe-prob3': OBSERVE_PROB3_DB, 'm6': M6_STATE}
        for name, source in mapping.items():
            if not source.exists():
                continue
            child = roots / name
            child.mkdir(exist_ok=True)
            link = child / 'state.sqlite3'
            if not link.exists():
                os.symlink(source, link)
        if GOALS_DB.exists():
            goal_dir = roots / 'goals/state'
            goal_dir.mkdir(parents=True, exist_ok=True)
            link = goal_dir / 'goals.sqlite3'
            if not link.exists():
                os.symlink(GOALS_DB, link)
        from shared.supervision import ledger as ledger_mod
        account = ledger_mod.Ledger(ledger_mod.default_path())
        try:
            result = account.backfill(roots)
            account.conn.execute("UPDATE meta SET value=? WHERE key='epoch'", (json.dumps(0),))
        finally:
            account.close()
        return result

    def new_store(self, name):
        from shared.supervision.store import Store
        return Store(Path(self.tmp) / ('state-' + name))


def new_transport(day_dirs, session_ids, workers_for=()):
    sessions = load_sessions(set(session_ids))
    workers_by_root = {root: discover_workers(day_dirs, root) for root in workers_for}
    sends = load_sends([INCIDENT_DB, REMOTE_DB, PROBLEMI5_DB, OBSERVE_PROB3_DB, M6_STATE])
    return ReplayTransport(sessions, sends, workers_by_root)


# ---------------------------------------------------------------------------
# Incident scenario
# ---------------------------------------------------------------------------

def read_schema1_task(path):
    conn = ro(path)
    try:
        binding = dict(zip(('id', 'runtime', 'session_id', 'target_ids', 'status', 'generation'),
                            conn.execute('SELECT id,runtime,session_id,target_ids,status,generation FROM bindings').fetchone()))
        binding['target_ids'] = json.loads(binding['target_ids'])
        row = conn.execute('SELECT id,payload,created_at,interval_seconds FROM tasks').fetchone()
        task_id, payload, created_at, interval_seconds = row[0], json.loads(row[1]), row[2], row[3]
        executions = [dict(zip(('id', 'status', 'scheduled_at', 'started_at', 'finished_at', 'result'), row))
                      for row in conn.execute('SELECT id,status,scheduled_at,started_at,finished_at,result FROM executions ORDER BY scheduled_at')]
        for execution in executions:
            execution['result'] = json.loads(execution['result']) if execution['result'] else None
        interventions = []
        intents = {row[0]: (row[1], json.loads(row[2])) for row in
                   conn.execute("SELECT entity_id,at,details FROM audit WHERE action='intervention-intent'")}
        for entity_id, at, details in conn.execute(
                "SELECT entity_id,at,details FROM audit WHERE action='intervention-result' ORDER BY sequence"):
            intent_at, intent_details = intents.get(entity_id, (at, {}))
            interventions.append({'event_id': entity_id, 'at': intent_at, 'session_id': intent_details.get('session_id'),
                                   'result_status': json.loads(details).get('status')})
        return binding, task_id, payload, created_at, interval_seconds, executions, interventions
    finally:
        conn.close()


def mirror_task(store, transport, binding_info, task_id, payload, created_at, interval_seconds):
    from shared.supervision import cli
    store.bind({'id': 'supervisor', 'runtime': binding_info['runtime'], 'session_id': binding_info['session_id'],
                'target_ids': binding_info['target_ids']})
    acceptance = [{'text': text, 'owner': LEAD} for text in payload.get('acceptance', [])]
    transport.now = created_at
    data = {'id': task_id, 'supervisor_id': 'supervisor', 'mode': 'completion',
            'operator_session_id': binding_info['session_id'], 'instruction': payload.get('instruction', 'replay'),
            'target_ids': binding_info['target_ids'], 'acceptance': acceptance, 'scope': payload.get('scope', 'replay'),
            'interval_seconds': interval_seconds or 180, 'next_run_at': created_at}
    task = cli.create_task(store, lambda _b: transport, data)
    # The store stamps created_at with the wall clock of this replay run; the worker-baseline rule
    # ("later than the task" vs "first reading") depends on comparing it against the historical
    # record, so it is corrected here to the moment being replayed.
    store.conn.execute('UPDATE tasks SET created_at=?,updated_at=? WHERE id=?', (created_at, created_at, task['id']))
    return store.task(task['id'])


def execution_insert(store, scheduler, task, triggers, existing_id=None):
    """Create (or, for a row already carried over from the main store's history, turn back into an
    open 'running' execution) the execution that will receive the recorded judgment."""
    import uuid as uuid_mod
    binding = store.binding(task['supervisor_id'])
    members, working = scheduler._closing_set(task) if task['mode'] == 'completion' else ([], False)
    lease = scheduler.now + task['limits']['assessment_timeout_seconds']
    if existing_id is not None:
        store.conn.execute(
            "UPDATE executions SET status='running',lease_until=?,finished_at=NULL,triggers=?,closing_set=?,working=? WHERE id=?",
            (lease, json.dumps(triggers), json.dumps(members), int(working), existing_id))
        return existing_id
    eid = str(uuid_mod.uuid4())
    store.conn.execute(
        'INSERT INTO executions(id,task_id,supervisor_id,generation,binding_generation,status,scheduled_at,'
        'started_at,lease_until,triggers,closing_set,working) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
        (eid, task['id'], task['supervisor_id'], task['generation'], binding['generation'], 'running',
         scheduler.now, scheduler.now, lease, json.dumps(triggers), json.dumps(members), int(working)))
    return eid


def scenario_incident(replay):
    started = time.time()
    binding_info, task_id, payload, created_at, interval_seconds, executions, interventions = read_schema1_task(INCIDENT_DB)
    day_dirs = ['2026/11/10', '2026/11/11']
    transport = new_transport(day_dirs, [LEAD, REMOTE, MEMORY, binding_info['session_id']], workers_for=())
    store = replay.new_store('incident')
    from shared.supervision.scheduler import Scheduler
    from shared.supervision import store as store_mod
    scheduler = Scheduler(store, transport, now=created_at)
    task = mirror_task(store, transport, binding_info, task_id, payload, created_at, interval_seconds)

    trigger_ordinals = {}
    result_outcomes = {'accepted': 0, 'refused': {}}
    full_reasons = {}
    item_count = len(payload.get('acceptance', []))
    replay_step_artifact = Path(replay.tmp) / 'incident-replay-step.txt'
    for index, execution in enumerate(executions, start=1):
        transport.now = execution['scheduled_at']
        scheduler.now = execution['scheduled_at']
        scheduler._observe()
        pending = store.pending_triggers(task['id'])
        kinds = sorted({t['kind'] for t in pending})
        if kinds:
            trigger_ordinals[index] = kinds
        binding_main = store.binding(task['supervisor_id'])
        store.conn.execute(
            'INSERT INTO executions(id,task_id,supervisor_id,generation,binding_generation,status,scheduled_at,'
            'started_at,finished_at,triggers,closing_set,working) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            (execution['id'], task['id'], task['supervisor_id'], task['generation'], binding_main['generation'],
             execution['status'], execution['scheduled_at'], execution['started_at'], execution['finished_at'],
             '[]', '[]', 0))
        # The heartbeat trigger reads the recorded execution history to know how long the task has been
        # quiet; this real execution row (status and timing taken from the record) feeds that history
        # without this loop dispatching anything of its own.
        store.conn.execute('UPDATE triggers SET execution_id=? WHERE task_id=? AND execution_id IS NULL',
                           (execution['id'], task['id']))

        # Judge the recorded result on its own, on a copy of the store at this moment.
        from shared.supervision.store import Store as StoreClass
        copy_dir = Path(replay.tmp) / f'copy-incident-dir-{index}'
        copy_dir.mkdir(mode=0o700, exist_ok=True)
        copy_target = copy_dir / 'state.sqlite3'
        shutil.copy(store.path, copy_target)
        copy_target.chmod(0o600)
        copy_store = StoreClass(copy_dir)
        copy_scheduler = Scheduler(copy_store, transport, now=execution['scheduled_at'])
        eid = execution_insert(copy_store, copy_scheduler, copy_store.task(task['id']), [t['kind'] for t in pending],
                               existing_id=execution['id'])
        result = execution['result'] or {}
        outcome = result.get('outcome', 'completed')
        items = [{'id': f'A{n}', 'status': 'open'} for n in range(1, item_count + 1)]
        steps = [{'session_id': LEAD, 'description': 'replay step', 'artifact': str(replay_step_artifact),
                  'estimate_seconds': 600}]
        body = {'id': eid, 'generation': copy_store.task(task['id'])['generation'], 'outcome': outcome,
                'summary': result.get('summary') or 'replay', 'evidence': result.get('evidence') or (['replay'] if outcome == 'completed' else []),
                'remaining': [], 'items': items, 'steps': steps, 'steps_closed': []}
        # outcome 'blocked' here is left without a 'park' object on purpose: the schema-1 record carries
        # no structured park (reason/questions/completed/cites), so the real validation is left to refuse
        # it on its own terms, which is exactly what ordinals 124 and 161 are reported against.
        try:
            copy_store.execution_result(body)
            result_outcomes['accepted'] += 1
        except store_mod.StoreError as error:
            reason = str(error)
            key = reason.split(':')[0][:80]
            result_outcomes['refused'][key] = result_outcomes['refused'].get(key, 0) + 1
            if index in (124, 161):
                full_reasons[index] = reason
        copy_store.close()
        shutil.rmtree(copy_dir, ignore_errors=True)

    # Interventions: admit() against a fresh observation at the recorded time.
    from shared.supervision.control import admit
    from shared.supervision import store as store_mod2
    intervention_report = []
    for entry in interventions:
        transport.now = entry['at']
        row = {'triggers': json.dumps([])}
        target = entry['session_id']
        queue_len = len(transport._queue(target)) if target else None
        admitted, reason = True, None
        try:
            admit(store, transport, row, task, store.binding(task['supervisor_id']), target)
        except store_mod2.StoreError as error:
            admitted, reason = False, str(error)
        intervention_report.append({'at': entry['at'], 'role': ROLE_OF.get(target, target), 'admitted': admitted,
                                     'reason': reason, 'queue_len': queue_len})

    # Classification of the lead's user messages in the stated window.
    window_start, window_end = parse_iso('2026-11-10T00:00:00Z'), parse_iso('2026-11-11T15:09:00Z')
    transport.now = window_end
    from shared.supervision import observe as observe_mod
    observe_mod.observe_session(store, transport, LEAD, 'codex', window_end)
    rows = store.conn.execute(
        "SELECT o.data FROM observations o JOIN messages m ON m.session_id=o.session_id AND m.id=json_extract(o.data,'$.id') "
        "WHERE o.kind='message' AND o.session_id=? AND m.at>=? AND m.at<?", (LEAD, window_start, window_end)).fetchall()
    per_rule = {}
    for (data,) in rows:
        parsed = json.loads(data)
        per_rule[parsed['rule']] = per_rule.get(parsed['rule'], 0) + 1
    in_registry = sum(1 for (data,) in rows if store.registered(json.loads(data).get('ref') or ''))

    store.close()
    elapsed = time.time() - started
    return {
        'elapsed_seconds': round(elapsed, 1),
        'stated_assumptions': [
            'Every acceptance item is given owner lead, as the records name no owner.',
            'REMOTE and MEMORY contribute no triggers in the window: their rollouts show no turn activity on 2026-11-10/11.',
            'operator_session_id is set to the recorded binding session_id (the supervisor), which the schema accepts without a transport round trip.',
            'The recorded result for each execution is replayed with a fixed single acceptance item A1 kept open; the real recorded evidence/remaining/summary text is not reconstructed field-by-field, only outcome and the park shape when blocked.',
        ],
        'triggers_by_ordinal': trigger_ordinals,
        'expected_no_trigger_125_150_and_162_269': {
            'found_with_trigger_in_125_150': sorted(i for i in trigger_ordinals if 125 <= i <= 150),
            'found_with_trigger_in_162_269': sorted(i for i in trigger_ordinals if 162 <= i <= 269),
            'matches': not any(125 <= i <= 150 for i in trigger_ordinals) and not any(162 <= i <= 269 for i in trigger_ordinals),
        },
        'result_outcomes': result_outcomes,
        'full_reasons_124_161': full_reasons,
        'interventions': intervention_report,
        'classification_window': {'per_rule': per_rule, 'in_registry': in_registry, 'total': sum(per_rule.values())},
        'expected': {
            'results_124_161_refused_park_without_reason_and_request': all(i in full_reasons for i in (124, 161)),
            'lead_messages_in_window_classified_kit_by_ledger_23_none_envelope_none_registry': {
                'expected': {'ledger': 23, 'envelope': 0, 'registry': 0},
                'found': {'ledger': per_rule.get('ledger', 0), 'envelope': per_rule.get('envelope', 0), 'registry': in_registry},
            },
        },
    }


# ---------------------------------------------------------------------------
# M6 scenario
# ---------------------------------------------------------------------------

def scenario_m6(replay):
    started = time.time()
    binding_info, task_id, payload, created_at, interval_seconds, executions, interventions = read_schema1_task(M6_STATE)
    day_dirs = ['2026/11/13']
    transport = new_transport(day_dirs, [LEAD, binding_info['session_id']], workers_for=(binding_info['session_id'], LEAD))
    cutoff = parse_iso('2026-11-13T15:25:00Z')
    recorded_14 = [e for e in executions if e['scheduled_at'] <= cutoff]

    interventions_by_cutoff = [entry for entry in interventions if entry['at'] <= cutoff]

    store1 = replay.new_store('m6-measured')
    task1 = mirror_task(store1, transport, binding_info, task_id, payload, created_at, interval_seconds)
    for entry in interventions_by_cutoff:
        store1.delivery_add(entry['event_id'], entry['session_id'], 'intervention', task1['id'], None, 'replay',
                             'queued', 1800, now=entry['at'])
    transport.now = cutoff
    from shared.supervision.scheduler import Scheduler
    Scheduler(store1, transport, now=cutoff)._observe()
    measured1 = store1.measured(task1['id'])
    measured_report = {
        'items_closed': sum(1 for item in measured1['items'] if item['status'] == 'closed'),
        'sessions': {sid: (info or {}).get('state') for sid, info in measured1['sessions'].items()},
        'lead_running_turn_started_at': ((measured1['sessions'].get(LEAD) or {}).get('running_turn') or {}).get('started_at'),
        'deliveries': [{'client_id': d['client_id'], 'state': d['state'], 'sent_at': d['sent_at']} for d in measured1['deliveries']],
        'spend_total': measured1['spend'].get('value'),
        'spend_by_session': measured1['spend'].get('by_session'),
    }
    store1.detach({'id': 'supervisor', 'reason': 'replay store released for the next replay store'})
    store1.close()

    store2 = replay.new_store('m6-ceiling')
    transport.now = created_at
    task2 = mirror_task(store2, transport, binding_info, task_id, payload, created_at, interval_seconds)
    store2.update_task({'id': task2['id'], 'revision': task2['revision'],
                         'changes': {'limits': {'spend': {'unit': 'tokens', 'target': 30_000_000, 'ceiling': 30_000_000,
                                                           'cites': ['config:default_spend_limit']}}}})
    for entry in interventions_by_cutoff:
        store2.delivery_add(entry['event_id'], entry['session_id'], 'intervention', task2['id'], None, 'replay',
                             'queued', 1800, now=entry['at'])
    scheduler2 = Scheduler(store2, transport, now=created_at)
    park_moment, park_spend, park_reason = None, None, None
    now = created_at
    while now <= cutoff:
        transport.now = now
        scheduler2.now = now
        scheduler2._observe()
        scheduler2._limits()
        task_now = store2.task(task2['id'])
        if task_now['status'] == 'blocked':
            park_moment = now
            park_spend = store2.spend(task_now)
            park = store2.conn.execute("SELECT reason FROM parks WHERE task_id=? ORDER BY created_at DESC LIMIT 1", (task2['id'],)).fetchone()
            park_reason = park[0] if park else None
            break
        now += 60
    interrupts = [dict(row) for row in store2.conn.execute("SELECT * FROM observations WHERE kind='interrupt'")]
    store2.detach({'id': 'supervisor', 'reason': 'replay store released for the next replay store'})
    store2.close()

    store3 = replay.new_store('m6-triggers')
    transport.now = created_at
    task3 = mirror_task(store3, transport, binding_info, task_id, payload, created_at, interval_seconds)
    scheduler3 = Scheduler(store3, transport, now=created_at)
    trigger_ordinals = {}
    for index, execution in enumerate(recorded_14, start=1):
        transport.now = execution['scheduled_at']
        scheduler3.now = execution['scheduled_at']
        scheduler3._observe()
        pending = store3.pending_triggers(task3['id'])
        kinds = sorted({t['kind'] for t in pending})
        if kinds:
            trigger_ordinals[index] = kinds
        store3.conn.execute('UPDATE triggers SET execution_id=? WHERE task_id=? AND execution_id IS NULL',
                           ('carried-' + str(index), task3['id']))
    store3.close()

    elapsed = time.time() - started
    return {
        'elapsed_seconds': round(elapsed, 1),
        'stated_assumptions': [
            'The 2026-11-13 state root at this path is schema-1 (no mode/operator_session_id/baselines table): read directly, not through Store, like the incident export.',
            'The single acceptance item is given owner lead, as the record names no owner.',
            'The recorded interventions are inserted as deliveries at their recorded send times rather than re-sent.',
            'Worker rollouts are discovered only under 2026/11/13 (plus the day-before rule); none were found with a counter, which the output states explicitly.',
        ],
        'measured_at_15_25_00Z': measured_report,
        'ceiling_30M': {
            'parked_at': park_moment, 'parked_at_iso': datetime.datetime.fromtimestamp(park_moment, datetime.timezone.utc).isoformat() if park_moment else None,
            'measured_spend_tokens': park_spend.get('value') if park_spend else None,
            'park_reason': park_reason, 'interrupt_calls': len(interrupts),
        },
        'triggers_by_ordinal_14_recorded': trigger_ordinals,
        'expected': {
            'no_item_closed': measured_report['items_closed'] == 0,
            'lead_turn_running_since_13_13_54Z': measured_report['lead_running_turn_started_at'],
            'intervention_queued_since_14_29_44Z': [d for d in measured_report['deliveries'] if d['state'] == 'queued'],
            'spend_total_expected_68202352': {'expected': 68202352, 'found': measured_report['spend_total']},
            'ceiling_parks_at_crossing': park_moment is not None,
        },
    }


# ---------------------------------------------------------------------------
# Goal scenario
# ---------------------------------------------------------------------------

def scenario_goal(replay):
    started = time.time()
    conn = ro(GOALS_DB)
    try:
        total_wakes = conn.execute('SELECT count(*) FROM outbox').fetchone()[0]
        rows = conn.execute('SELECT sequence, event, payload FROM audit ORDER BY sequence').fetchall()
    finally:
        conn.close()
    pairs = []
    pending = None
    lead_consumed_total = 0
    for sequence, event, payload in rows:
        data = json.loads(payload)
        if event == 'delivery' and data.get('role') == 'lead' and data.get('status') == 'consumed':
            lead_consumed_total += 1
            pending = sequence
        elif event == 'check-result' and pending is not None:
            pairs.append((pending, sequence, data.get('passed')))
            pending = None
    failed_pairs = [p for p in pairs if p[2] is False]

    from shared.supervision.store import Store, StoreError
    from shared.supervision.scheduler import Scheduler
    from shared.supervision.control import intervene
    sys.path.insert(0, str(ROOT / 'tests'))
    import supervision_fixture as fixture

    store = replay.new_store('goal')
    fake = fixture.Fake(M6_SUPERVISOR, LEAD)
    store.bind({'id': 'supervisor', 'runtime': 'codex', 'session_id': M6_SUPERVISOR, 'target_ids': [LEAD]})
    now = time.time()
    data = {'id': 'goal-replay', 'supervisor_id': 'supervisor', 'mode': 'completion', 'operator_session_id': M6_SUPERVISOR,
            'instruction': 'goal replay', 'target_ids': [LEAD], 'acceptance': [{'text': 'acceptance', 'owner': LEAD}],
            'scope': 'goal replay', 'interval_seconds': 1, 'next_run_at': now}
    from shared.supervision import cli
    task = cli.create_task(store, lambda _b: fake, data)
    scheduler = Scheduler(store, fake, now=now)

    processed, refused_at, refused_reason = 0, None, None
    step_id = None
    for index, (_, _, passed) in enumerate(failed_pairs, start=1):
        now += 10
        scheduler.now = now
        members, working = scheduler._closing_set(task)
        eid = str(uuid.uuid4())
        binding = store.binding(task['supervisor_id'])
        store.conn.execute(
            'INSERT INTO executions(id,task_id,supervisor_id,generation,binding_generation,status,scheduled_at,'
            'started_at,lease_until,triggers,closing_set,working) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            (eid, task['id'], task['supervisor_id'], task['generation'], binding['generation'], 'running', now, now,
             now + task['limits']['assessment_timeout_seconds'], json.dumps([]), json.dumps(members), int(working)))
        event_id = str(uuid.uuid4())
        intervene(store, fake, {'execution_id': eid, 'generation': task['generation'], 'session_id': LEAD,
                                 'event_id': event_id, 'instruction': 'goal replay pair', 'reason': 'no-closure replay'})
        fake[LEAD].consume()
        fake[LEAD].finish()
        now += 1
        scheduler.now = now
        scheduler._observe()
        if step_id is None:
            steps = [{'session_id': LEAD, 'description': 'goal replay step',
                      'artifact': str(Path(replay.tmp) / 'goal-step.txt'), 'estimate_seconds': 3600}]
        else:
            steps = [{'session_id': LEAD, 'id': step_id}]
        body = {'id': eid, 'generation': task['generation'], 'outcome': 'failed', 'summary': 'goal replay pair',
                'evidence': [], 'items': [{'id': 'A1', 'status': 'open'}], 'steps': steps, 'steps_closed': [],
                'closing': [{'session_id': LEAD, 'kind': 'intervention', 'event_id': event_id}]}
        processed += 1
        try:
            effect = store.execution_result(body)
            if step_id is None:
                step_id = effect.get('steps_declared', [None])[0]
        except StoreError as error:
            refused_at, refused_reason = index, str(error)
            break
    store.close()
    elapsed = time.time() - started
    return {
        'elapsed_seconds': round(elapsed, 1),
        'stated_assumptions': [
            'A lead wake "consumed" is an audit row with event=delivery, payload.role=lead, payload.status=consumed.',
            'An acceptance check is an audit row with event=check-result; it did not pass when payload.passed is false.',
            'Pairing rule: walking the audit table in sequence order, each lead-wake-consumed row is paired with the next check-result row that follows it before another lead-wake-consumed row appears.',
            'The simulated assessment never closes anything and sends exactly one intervention per pair to the single idle lead target; processing stops at the first refusal rather than continuing through every pair, since every later pair would refuse for the same reason.',
        ],
        'total_recorded_wakes': total_wakes,
        'lead_consumed_deliveries_total': lead_consumed_total,
        'pairs_formed': len(pairs),
        'pairs_with_failed_check': len(failed_pairs),
        'pairs_processed': processed,
        'first_refusal': {'pair': refused_at, 'reason': refused_reason},
        'expected': {
            'no_closure_count_reaches_two_at_second_consumed_wake_then_refuses_at_third': refused_at == 3,
            'against_996_recorded_wakes': {'expected': 996, 'found': total_wakes},
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', choices=['incident', 'm6', 'goal'], required=True)
    args = parser.parse_args()
    replay = Replay()
    try:
        backfill = replay.backfill_result()
        if args.scenario == 'incident':
            result = scenario_incident(replay)
        elif args.scenario == 'm6':
            result = scenario_m6(replay)
        else:
            result = scenario_goal(replay)
        result = {'scenario': args.scenario, 'ledger_backfill': backfill, 'ledger_epoch_set_to_zero': True, **result}
        print(json.dumps(result, indent=2, default=str))
    finally:
        replay.cleanup()


if __name__ == '__main__':
    main()
