"""Shared fixtures for the supervision suites: an isolated account, a programmable in-process
transport, and a programmable native app-server over a Unix WebSocket for real-CLI tests.

Nothing here touches the real account ledger, the real kit home or real Codex state.
"""
import contextlib
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CLI = os.environ.get('AI_KIT_SUPERVISION_TEST_CLI', str(ROOT / 'shared/supervision/cli.py'))
MANDATE = 'Supervise the lead until the report exists. Spend at most 50000 tokens.'


def isolate(case):
    """Give a test its own ledger and kit home; return the temporary directory."""
    temp = tempfile.TemporaryDirectory()
    case.addCleanup(temp.cleanup)
    root = Path(temp.name)
    saved = {key: os.environ.get(key) for key in ('MRCALL_SUPERVISION_LEDGER', 'MRCALL_KIT_HOME', 'MRCALL_SUPERVISION_REVIEW_COMMAND')}

    def restore():
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    case.addCleanup(restore)
    os.environ['MRCALL_SUPERVISION_LEDGER'] = str(root / 'ledger.sqlite3')
    os.environ['MRCALL_KIT_HOME'] = str(root / 'kit')
    # No test may launch the native reviewer: by default a review run ends at once with no verdict, which is
    # the unavailable outcome. A test that needs a verdict sets its own stub command.
    os.environ['MRCALL_SUPERVISION_REVIEW_COMMAND'] = json.dumps([sys.executable, '-c', 'pass'])
    (root / 'kit').mkdir()
    return root


class Session:
    """One native session as the fixtures model it."""

    def __init__(self, session_id):
        self.id = session_id
        self.status = 'idle'
        self.flags = []
        self.queue = []          # [{'id', 'client_id', 'text'}]
        self.turns = []          # [{'id', 'status', 'started_at', 'completed_at'}]
        self.items = {}          # turn id -> [{'id', 'client_id', 'text', 'at'}]
        self.usage = {'total': 1000, 'input': 900, 'cached_input': 500, 'output': 100}
        self.allowance = {'used_percent': 10.0, 'window_minutes': 10080, 'resets_at': 2_000_000_000, 'plan_type': 'pro'}
        self.workers = {}        # worker id -> {'usage', 'created_at'}
        self.parent = None
        self.accepts = True

    def say(self, body, client_id=None, at=None, running=False):
        """A user message that starts its own turn: what the operator typing in the session looks like."""
        now = time.time() if at is None else at
        turn = {'id': str(uuid.uuid4()), 'status': 'inProgress' if running else 'completed', 'started_at': now, 'completed_at': None if running else now}
        self.turns.append(turn)
        self.items[turn['id']] = [{'id': str(uuid.uuid4()), 'client_id': client_id or str(uuid.uuid4()), 'text': body, 'at': now}]
        if running:
            self.status = 'active'
        return self.items[turn['id']][0]

    def steer(self, body, client_id=None, at=None):
        """A user message entering the running turn; the summary view of a turn never shows it."""
        message = {'id': str(uuid.uuid4()), 'client_id': client_id or str(uuid.uuid4()), 'text': body, 'at': time.time() if at is None else at}
        self.items[self.turns[-1]['id']].append(message)
        return message

    def consume(self, running=True):
        """The session takes its first queued message into a new turn."""
        entry = self.queue.pop(0)
        return self.say(entry['text'], client_id=entry['client_id'], running=running)

    def finish(self, status='completed'):
        self.turns[-1].update(status=status, completed_at=time.time())
        self.status = 'idle'
        self.flags = []

    def spend(self, tokens):
        for key in ('total', 'input'):
            self.usage[key] += tokens


class Fake:
    """In-process transport with the contract of the native adapters, driven by Session objects."""

    def __init__(self, *session_ids):
        self.sessions = {session_id: Session(session_id) for session_id in session_ids}
        self.calls = []
        self.sent = []
        self.interrupted = []
        self.unreadable = set()          # session ids whose observation raises
        self.unknown = {}                # session id -> names of values that cannot be read
        self.refuse_send = None          # an exception to raise from send
        self.refuse_interrupt = None
        self.reconciled = 'delivered'

    def __getitem__(self, session_id):
        return self.sessions[session_id]

    def add(self, session_id=None):
        session_id = session_id or str(uuid.uuid4())
        self.sessions[session_id] = Session(session_id)
        return session_id

    def metadata(self, session_id):
        self.calls.append(('metadata', session_id))
        session = self.sessions[session_id]
        return {'id': session_id, 'status': {'type': session.status}, 'parentThreadId': session.parent, 'canAcceptDirectInput': session.accepts}

    def observe(self, session_id, cursor=None, workers_since=None, history_turns=30):
        self.calls.append(('observe', session_id))
        if session_id in self.unreadable:
            raise RuntimeError('native read failed')
        session = self.sessions[session_id]
        cursor = cursor or {'closed': 0, 'seen': []}
        unknown = list(self.unknown.get(session_id, []))
        turns = session.turns[cursor['closed']:]
        seen = set(cursor['seen'])
        messages = [{'id': item['id'], 'turn_id': turn['id'], 'client_id': item['client_id'], 'at': item['at'], 'text': item['text'], 'inter_agent': bool(item.get('inter_agent'))}
                    for turn in turns for item in session.items.get(turn['id'], []) if item['id'] not in seen]
        closed = cursor['closed']
        while closed < len(session.turns) and session.turns[closed]['status'] != 'inProgress':
            closed += 1
        usage = None if 'usage' in unknown else dict(session.usage, at=time.time())
        return {'id': session_id, 'status': session.status, 'flags': list(session.flags), 'can_accept_input': session.accepts, 'parent_id': session.parent,
                'queue': None if 'queue' in unknown else [{'id': entry['id'], 'client_id': entry['client_id']} for entry in session.queue],
                'turns': [dict(turn) for turn in turns], 'messages': [] if 'messages' in unknown else messages,
                'usage': usage, 'allowance': None if 'allowance' in unknown else dict(session.allowance, at=time.time()),
                'workers': [] if workers_since is None else [{'id': worker, **record} for worker, record in session.workers.items()],
                'history_reset': False, 'unknown': unknown,
                'cursor': {'closed': closed, 'seen': sorted(seen | {message['id'] for message in messages}) if closed < len(session.turns) else []}}

    def send(self, session_id, event_id, body, allow_busy=False):
        self.calls.append(('send', session_id, event_id, body, allow_busy))
        if self.refuse_send is not None:
            raise self.refuse_send
        session = self.sessions[session_id]
        if not allow_busy and session.status != 'idle':
            raise RuntimeError('supervisor is busy; event was not submitted')
        self.sent.append((session_id, event_id, body))
        session.queue.append({'id': 'queued-' + event_id[:8], 'client_id': event_id, 'text': body})
        return {'status': 'delivered', 'native_submission_id': 'queued-' + event_id[:8]}

    def reconcile(self, session_id, event_id, **_):
        self.calls.append(('reconcile', session_id, event_id))
        return {'status': self.reconciled}

    def read(self, session_id, **kwargs):
        self.calls.append(('read', session_id, kwargs))
        return {'thread': {'id': session_id}, 'turns': [], 'next_cursor': 'older', 'reverse_cursor': 'newer', **kwargs}

    def interrupt(self, session_id, turn_id):
        self.calls.append(('interrupt', session_id, turn_id))
        if self.refuse_interrupt is not None:
            raise self.refuse_interrupt
        self.interrupted.append((session_id, turn_id))
        self.sessions[session_id].finish('interrupted')
        return {'status': 'interrupted', 'thread_id': session_id, 'turn_id': turn_id}


class World:
    """A store with one supervisor, its targets and an operator mandate already in the registry."""

    def __init__(self, case, targets=1, runtime='codex'):
        from shared.supervision.store import Store
        from shared.supervision import cli
        self.case = case
        self.temp = isolate(case)
        self.store = Store(self.temp / 'state')
        case.addCleanup(lambda: self.store.close())
        self.supervisor = str(uuid.uuid4())
        self.targets = [str(uuid.uuid4()) for _ in range(targets)]
        self.target = self.targets[0] if self.targets else None
        self.fake = Fake(self.supervisor, *self.targets)
        self.store.bind({'id': 'supervisor', 'runtime': runtime, 'session_id': self.supervisor, 'target_ids': self.targets})
        # The first observation is the baseline; the mandate arrives after it, as an operator message.
        cli.registry_scan(self.store, lambda _binding: self.fake, {'supervisor_id': 'supervisor'})
        self.fake[self.supervisor].say(MANDATE)
        self.ref = cli.registry_scan(self.store, lambda _binding: self.fake, {'supervisor_id': 'supervisor'})['registry'][-1]['ref']

    def reopen(self):
        from shared.supervision.store import Store
        self.store.close()
        self.store = Store(self.temp / 'state')
        return self.store

    def data(self, mode='completion', **changes):
        """Input of task-create that the contract accepts; `changes` override or, with None, remove fields."""
        data = {'id': 'task', 'supervisor_id': 'supervisor', 'target_ids': list(self.targets), 'mode': mode,
                'operator_session_id': self.supervisor, 'instruction': 'Deliver the report', 'scope': 'fixture',
                'acceptance': [{'text': f'report {number} exists', 'owner': target} for number, target in enumerate(self.targets, 1)],
                'interval_seconds': 600,
                'limits': {'spend': {'unit': 'tokens', 'target': 40000, 'ceiling': 50000, 'cites': [self.ref]}}}
        if mode == 'observation':
            data['acceptance'] = ['evidence']
            data['limits'] = {}
        data.update(changes)
        return {key: value for key, value in data.items() if value is not None}

    def create(self, mode='completion', **changes):
        from shared.supervision import cli
        return cli.create_task(self.store, lambda _binding: self.fake, self.data(mode, **changes))

    def tick(self, now=None):
        from shared.supervision.scheduler import Scheduler
        return Scheduler(self.store, self.fake, now=time.time() if now is None else now).tick()

    def executions(self, task_id='task'):
        return [dict(row) for row in self.store.conn.execute('SELECT * FROM executions WHERE task_id=? ORDER BY scheduled_at,id', (task_id,))]

    def wake(self, now=None, task_id='task'):
        """Tick until an assessment is dispatched, let the supervisor take the wake, and return the execution."""
        self.tick(now)
        execution = self.executions(task_id)[-1]
        if self.fake[self.supervisor].queue:
            self.fake[self.supervisor].consume()
        return execution

    def result(self, execution, outcome='completed', **fields):
        base = {'id': execution['id'], 'generation': execution['generation'], 'outcome': outcome, 'summary': 'assessment', 'evidence': ['fixture']}
        return self.store.execution_result(base | fields)

    def step(self, target=None, artifact=None, estimate=600):
        return {'session_id': target or self.target, 'description': 'write the report', 'artifact': str(artifact or self.temp / 'report.txt'), 'estimate_seconds': estimate}

    def intervene(self, execution, target=None, instruction='Write the report now', event_id=None):
        from shared.supervision.control import intervene
        event_id = event_id or str(uuid.uuid4())
        result = intervene(self.store, self.fake, {'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': target or self.target,
                                                    'event_id': event_id, 'instruction': instruction, 'reason': 'unmet acceptance'})
        return event_id, result

    def measured(self, task_id='task'):
        return self.store.measured(task_id)


# ---- real CLI over a native app-server fixture ----

def iso(at):
    return datetime.datetime.fromtimestamp(at, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


class Native:
    """A fake Codex app-server on a Unix WebSocket, driven by the same Session objects as Fake.

    It serves thread/read, thread/queue/list, thread/queue/add, thread/turns/list, thread/items/list and
    turn/interrupt, and keeps a synthetic rollout per session for token counters. `methods` lists every call.
    """

    def __init__(self, root, *session_ids):
        self.root = Path(root)
        self.sessions = {session_id: Session(session_id) for session_id in session_ids}
        self.methods = []
        self.accepted = []           # thread/queue/add params
        self.interrupts = []
        self.fail = {}               # method -> JSON-RPC error object to answer with
        # Today's directory: workers are searched from the day before a task's creation.
        self.day = self.root / 'sessions' / datetime.datetime.now(datetime.timezone.utc).strftime('%Y/%m/%d')
        self.day.mkdir(parents=True, exist_ok=True)
        self.socket = self.root / 'control.sock'
        self.codex = self.root / 'codex-fixture'
        self.codex.write_text('#!' + sys.executable + '\nimport json\nprint(json.dumps(' + repr({'status': 'running', 'socketPath': str(self.socket)}) + '))\n')
        self.codex.chmod(0o700)

    def __getitem__(self, session_id):
        return self.sessions[session_id]

    def rollout(self, session_id, root_id=None):
        return self.day / f'rollout-{session_id}.jsonl'

    def write_rollouts(self):
        """Bring every rollout up to the sessions' counters. A rollout is append-only, as the native one is:
        the header once, then one cumulative usage record and one allowance record whenever a value changed."""
        written = self.__dict__.setdefault('_written', {})
        for session in self.sessions.values():
            records = [(session.id, session.id, session.usage, session.allowance, None)]
            records += [(session.id, worker, record['usage'], None, record.get('created_at')) for worker, record in session.workers.items()]
            for root_id, ident, usage, allowance, created in records:
                now = time.time()
                path = self.rollout(ident)
                lines = []
                if not path.exists():
                    written.pop(ident, None)
                    lines.append({'timestamp': iso(created or now), 'type': 'session_meta', 'payload': {'session_id': root_id, 'id': ident, 'timestamp': iso(created or now)}})
                state = (json.dumps(usage, sort_keys=True), json.dumps(allowance, sort_keys=True))
                if written.get(ident) == state:
                    continue
                if usage is not None:
                    lines.append({'timestamp': iso(now), 'type': 'token_usage_record', 'payload': {'thread_id': ident, 'thread_token_usage': {
                        'input_tokens': usage['input'], 'cached_input_tokens': usage['cached_input'], 'output_tokens': usage['output'], 'total_tokens': usage['total']}}})
                if allowance is not None:
                    lines.append({'timestamp': iso(now), 'type': 'event_msg', 'payload': {'type': 'token_count', 'rate_limits': {
                        'primary': {key: allowance[key] for key in ('used_percent', 'window_minutes', 'resets_at')}, 'plan_type': allowance['plan_type']}}})
                with path.open('a') as handle:
                    handle.write(''.join(json.dumps(line) + '\n' for line in lines))
                written[ident] = state

    def respond(self, method, params):
        if method == 'initialize':
            return {'userAgent': 'fixture'}
        session = self.sessions[params['threadId']]
        if method == 'thread/read':
            status = {'type': session.status}
            if session.status == 'active':
                status['activeFlags'] = list(session.flags)
            return {'thread': {'id': session.id, 'cwd': str(self.root), 'status': status, 'parentThreadId': session.parent,
                               'canAcceptDirectInput': session.accepts if session.status in ('idle', 'active') else None, 'path': str(self.rollout(session.id))}}
        if method == 'thread/queue/list':
            return {'data': [{'id': entry['id'], 'clientUserMessageId': entry['client_id'], 'input': []} for entry in session.queue], 'nextCursor': None}
        if method == 'thread/queue/add':
            self.accepted.append(params)
            body = '\n'.join(part.get('text', '') for part in params['input'])
            entry = {'id': str(uuid.uuid4()), 'client_id': params['clientUserMessageId'], 'text': body}
            session.queue.append(entry)
            return {'queuedSubmission': {'id': entry['id'], 'clientUserMessageId': entry['client_id']}}
        if method == 'thread/turns/list':
            turns = list(reversed(session.turns)) if params.get('sortDirection', 'desc') == 'desc' else list(session.turns)
            return {'data': [{'id': turn['id'], 'status': turn['status'], 'startedAt': int(turn['started_at']),
                              'completedAt': None if turn['completed_at'] is None else int(turn['completed_at']), 'items': []} for turn in turns],
                    'nextCursor': None, 'backwardsCursor': None}
        if method == 'thread/items/list':
            items = session.items.get(params['turnId'], [])
            anchor = (params.get('cursor') or {}).get('itemId') if isinstance(params.get('cursor'), dict) else None
            if anchor is not None:
                index = [item['id'] for item in items].index(anchor) if anchor in [item['id'] for item in items] else None
                if index is None:
                    return {'error': {'code': -32602, 'message': 'cursor.itemId does not identify an item in the requested history scope'}}
                items = items[index + 1:]
            return {'data': [{'turnId': params['turnId'], 'startedAtMs': int(item['at'] * 1000), 'completedAtMs': int(item['at'] * 1000),
                              'item': {'type': 'userMessage', 'id': item['id'], 'clientId': item['client_id'], 'content': [{'type': 'text', 'text': item['text']}]}}
                             for item in items], 'nextCursor': None}
        if method == 'turn/interrupt':
            self.interrupts.append(params)
            session.finish('interrupted')
            return {}
        raise AssertionError(method)

    @contextlib.contextmanager
    def serving(self):
        from websockets.sync.server import unix_serve

        def handler(ws):
            try:
                for raw in ws:
                    request = json.loads(raw)
                    if 'id' not in request:
                        continue
                    method, params = request['method'], request.get('params') or {}
                    self.methods.append(method)
                    answer = {'error': self.fail[method]} if method in self.fail else self.respond(method, params)
                    if isinstance(answer, dict) and set(answer) == {'error'}:
                        ws.send(json.dumps({'id': request['id'], 'error': answer['error']}))
                    else:
                        ws.send(json.dumps({'id': request['id'], 'result': answer}))
            except Exception:
                return
        self.write_rollouts()
        with unix_serve(handler, str(self.socket)) as server:
            self.socket.chmod(0o600)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield self
            finally:
                server.shutdown()
                thread.join(3)

    def cli(self, state_dir, command, data=None, identifier=None, ok=True, env=None):
        """Run the real CLI against this fixture; return its result, or its error text when `ok` is false."""
        self.write_rollouts()
        argv = [sys.executable, CLI, '--state-dir', str(state_dir), '--codex-path', str(self.codex), command]
        if identifier is not None:
            argv += ['--id', identifier]
        process = subprocess.run(argv, input=None if data is None else json.dumps(data), capture_output=True, text=True,
                                 env=dict(os.environ, **(env or {})))
        answer = json.loads(process.stdout) if process.stdout.strip() else {'ok': False, 'error': process.stderr}
        if answer.get('ok') is not ok:
            raise AssertionError(f'{command}: expected ok={ok}, got {process.stdout}{process.stderr}')
        return answer['result'] if ok else answer['error']
