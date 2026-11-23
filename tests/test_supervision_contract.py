"""M1 property tests for the account ledger, observation origin, task-contract validation and
earlier-schema safety, through the real CLI and the `Native` fixture, as `m1-spec-tests.md`
requires. Each test proves exactly one row of the Verification table in
docs/execution-plans/2026-11-14-supervision-controller-repair.md, reading the observation the
table names from where it names it. Nothing here touches the real account ledger, the real kit
home, real Codex state or the network.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervision_fixture import MANDATE, Native, isolate
from shared.supervision.store import LEGACY


class BrokenRollout(Native):
    """`thread/read` reports a rollout path that does not exist for every session named in
    `broken`, so the real transport's counter read fails for exactly that session while every
    other session's read keeps succeeding. The fixture's rollout files are rewritten from the
    sessions' counters on every call, so breaking the file's content would not survive a second
    `cli()` call; redirecting the reported path does. Local to this file, as the handoff allows."""

    def __init__(self, root, *session_ids):
        super().__init__(root, *session_ids)
        self.broken = set()

    def respond(self, method, params):
        answer = super().respond(method, params)
        if method == 'thread/read' and params.get('threadId') in self.broken:
            answer['thread']['path'] = str(self.root / 'missing-rollout.jsonl')
        return answer


def make_native(case, native_cls=Native):
    """A fresh isolated account/kit home and a Native fixture with a supervisor and one lead."""
    root = isolate(case)
    supervisor, lead = str(uuid.uuid4()), str(uuid.uuid4())
    native = native_cls(root, supervisor, lead)
    return native, root / 'state', supervisor, lead


def bootstrap(native, state_dir, supervisor, lead, binding='supervisor'):
    """bind; registry-scan once (baseline); the operator's mandate; registry-scan again for its ref."""
    native.cli(state_dir, 'bind', {'id': binding, 'session_id': supervisor, 'target_ids': [lead]})
    native.cli(state_dir, 'registry-scan', {'supervisor_id': binding})
    native[supervisor].say(MANDATE)
    scanned = native.cli(state_dir, 'registry-scan', {'supervisor_id': binding})
    return scanned['registry'][-1]['ref']


def setup_task(native, state_dir, supervisor, lead, mode='completion', interval_seconds=1, limits=None,
                binding='supervisor', task_id='task', **extra):
    ref = bootstrap(native, state_dir, supervisor, lead, binding)
    base_limits = limits if limits is not None else {'spend': {'unit': 'tokens', 'target': 40000, 'ceiling': 50000, 'cites': [ref]}}
    data = {'id': task_id, 'supervisor_id': binding, 'target_ids': [lead], 'mode': mode,
            'operator_session_id': supervisor, 'instruction': 'Deliver the report', 'scope': 'fixture',
            'acceptance': [{'text': 'the report exists', 'owner': lead}] if mode == 'completion' else ['evidence'],
            'interval_seconds': interval_seconds, 'limits': base_limits}
    data.update(extra)
    task = native.cli(state_dir, 'task-create', data)
    return ref, task


def park_payload(reason='operator-input'):
    return {'reason': reason, 'questions': [{'matter': 'Which channel should carry the update?',
            'options': ['Email', 'Phone'], 'recommendation': 'Email'}],
            'completed': 'Nothing else can proceed without the operator.'}


def ledger_rows(path):
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute('SELECT client_id, kind FROM messages ORDER BY at').fetchall()
    finally:
        conn.close()


def ledger_claim(path, session_id):
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute('SELECT state_root, task_id FROM claims WHERE session_id=?', (session_id,)).fetchone()
        return {'state_root': row[0], 'task_id': row[1]} if row else None
    finally:
        conn.close()


def state_messages(state_dir, session_id):
    conn = sqlite3.connect(str(Path(state_dir) / 'state.sqlite3'))
    try:
        return conn.execute('SELECT origin, text, client_id, ref FROM messages WHERE session_id=? ORDER BY observed_at',
                            (session_id,)).fetchall()
    finally:
        conn.close()


RENDERED_HEADERS = ['== RESULT OWED ==', "== ASK FIRST — the operator decides these, nobody else ==",
                     '== OPERATOR LIMITS — data, each cited ==', '== OPERATOR STATEMENTS — verbatim from the registry ==',
                     '== EVERYTHING ELSE ==', "== TOKEN DISCIPLINE — the operator's standing request =="]


def assert_rendered(case, text, statement):
    """The labeled parts appear in order and the cited operator statement appears verbatim."""
    indices = [text.index(header) for header in RENDERED_HEADERS]
    case.assertEqual(indices, sorted(indices))
    last = text.index("NOT THE OPERATOR'S WORDS ==")
    case.assertGreater(last, indices[-1])
    case.assertIn(statement, text)


class ContractTests(unittest.TestCase):

    def test_observation_is_read_only(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native.cli(state_dir, 'tick')  # dispatches the 'activated' wake
            triggers = native.cli(state_dir, 'status', identifier='task')['measured']['triggers']
            self.assertEqual(triggers, [])
            native.methods.clear()
            native.accepted.clear()
            native.interrupts.clear()
            native.cli(state_dir, 'tick')  # no trigger pending; nothing changed
            self.assertEqual(native.accepted, [])
            self.assertEqual(native.interrupts, [])
            allowed = {'initialize', 'thread/read', 'thread/queue/list', 'thread/turns/list', 'thread/items/list'}
            self.assertTrue(set(native.methods) <= allowed, native.methods)
            self.assertNotIn('thread/queue/add', native.methods)
            self.assertNotIn('turn/interrupt', native.methods)

    def test_unreadable_counter_is_unknown(self):
        native, state_dir, supervisor, lead = make_native(self, native_cls=BrokenRollout)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native.cli(state_dir, 'tick')  # dispatches 'activated'; the wake stays undelivered/open
            native.broken.add(lead)
            native.cli(state_dir, 'tick')  # the open execution blocks a new claim: 'spend-unknown' stays pending
            status = native.cli(state_dir, 'status', identifier='task')
            spend = status['measured']['spend']
            self.assertIn(lead, spend['unknown'])
            self.assertIsNone(spend['value'])
            self.assertIn('spend-unknown', [t['kind'] for t in status['measured']['triggers']])

    def test_restart_or_lost_history_keeps_records(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native.cli(state_dir, 'tick')
            native.cli(state_dir, 'task-state', {'id': 'task', 'revision': 1, 'action': 'block',
                                                  'reason': 'needs a decision', 'remaining': ['pick a channel'],
                                                  'park': park_payload()})
            native.cli(state_dir, 'tick')  # the park takes effect and the question is sent
            before = native.cli(state_dir, 'status', identifier='task')['measured']
            before_registry = native.cli(state_dir, 'registry')
            self.assertTrue(before['parks'])
            self.assertEqual(sorted(d['kind'] for d in before['deliveries']), ['question', 'wake'])

            for session in native.sessions.values():
                session.turns = []
                session.items = {}

            native.cli(state_dir, 'tick')
            after = native.cli(state_dir, 'status', identifier='task')['measured']
            after_registry = native.cli(state_dir, 'registry')
            for key in ('parks', 'open_questions', 'deliveries', 'counts'):
                self.assertEqual(after[key], before[key], key)
            self.assertEqual(after_registry, before_registry)

    def test_every_kit_send_is_in_the_ledger(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native.cli(state_dir, 'tick')  # wake
            execution = native.cli(state_dir, 'status')['executions'][-1]
            native.cli(state_dir, 'intervene', {'execution_id': execution['id'], 'generation': execution['generation'],
                                                 'session_id': lead, 'event_id': str(uuid.uuid4()),
                                                 'instruction': 'Write the report now', 'reason': 'unmet acceptance'})
            native.cli(state_dir, 'notice', {'task_id': 'task', 'session_id': lead, 'text': 'Status check-in.',
                                              'event_id': str(uuid.uuid4())})
            native.cli(state_dir, 'task-state', {'id': 'task', 'revision': 1, 'action': 'block',
                                                  'reason': 'needs a decision', 'remaining': ['pick a channel'],
                                                  'park': park_payload()})
            native.cli(state_dir, 'tick')  # question
            ledger_path = native.cli(state_dir, 'status', identifier='task')['measured']['ledger']
            rows = ledger_rows(ledger_path)
            self.assertEqual(sorted(kind for _, kind in rows), ['intervention', 'notice', 'question', 'wake'])
            self.assertEqual(len(native.accepted), 4)

    def test_failed_ledger_write_refuses_the_send(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            ledger_path = native.root / 'ledger.sqlite3'
            self.assertTrue(ledger_path.exists())
            os.chmod(ledger_path, 0)
            self.addCleanup(lambda: ledger_path.exists() and os.chmod(ledger_path, 0o600))
            native.accepted.clear()
            error = native.cli(state_dir, 'notice', {'task_id': 'task', 'session_id': lead, 'text': 'status update'}, ok=False)
            self.assertIn('ledger', error)
            self.assertEqual(native.accepted, [])

    def test_recorded_ledger_path_wins(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            ledger_path = native.root / 'ledger.sqlite3'
            elsewhere = native.root / 'elsewhere.sqlite3'

            native.cli(state_dir, 'tick', env={'MRCALL_SUPERVISION_LEDGER': str(elsewhere)})
            recorded = native.cli(state_dir, 'status', identifier='task')['measured']['ledger']
            self.assertEqual(Path(recorded), ledger_path)
            self.assertFalse(elsewhere.exists())
            self.assertEqual(len(ledger_rows(ledger_path)), 1)

            native.cli(state_dir, 'task-update', {'id': 'task', 'revision': 1, 'changes': {'interval_seconds': 1}})
            time.sleep(1.2)
            saved = os.environ.pop('MRCALL_SUPERVISION_LEDGER')
            try:
                native.cli(state_dir, 'tick')
            finally:
                os.environ['MRCALL_SUPERVISION_LEDGER'] = saved
            self.assertEqual(len(ledger_rows(ledger_path)), 2)
            self.assertFalse(elsewhere.exists())

    def test_origin_classes(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native.cli(state_dir, 'tick')
            wake_client_id = native.cli(state_dir, 'status')['outbox'][0]['client_message_id']

            ledger_body = 'already sent by the kit, replayed here'
            envelope_body = 'AI_KIT_GOAL_EVENT ' + json.dumps({'task': 'goal-1'})
            old_body = 'a very old operator-looking message'
            native[lead].say(ledger_body, client_id=wake_client_id)
            native[lead].say(envelope_body)
            native[lead].say(old_body, at=0)

            native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})

            by_text = {text: origin for origin, text, client_id, ref in state_messages(state_dir, lead)}
            self.assertEqual(by_text[ledger_body], 'kit')
            self.assertEqual(by_text[envelope_body], 'kit')
            self.assertEqual(by_text[old_body], 'unknown')

            registry = native.cli(state_dir, 'registry')
            self.assertTrue(any(entry['text'] == MANDATE and entry['session_id'] == supervisor for entry in registry))

    def test_only_registry_entries_are_cited(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            ref = bootstrap(native, state_dir, supervisor, lead)
            bad = 'op-0000000000'
            (native.root / 'kit' / 'supervision.json').write_text(json.dumps({'operator_note': True}))

            def payload(**overrides):
                data = {'id': 'task', 'supervisor_id': 'supervisor', 'target_ids': [lead], 'mode': 'completion',
                        'operator_session_id': supervisor, 'instruction': 'Deliver the report', 'scope': 'fixture',
                        'acceptance': [{'text': 'the report exists', 'owner': lead}], 'interval_seconds': 1,
                        'limits': {'spend': {'unit': 'tokens', 'target': 100, 'ceiling': 200, 'cites': [ref]}}}
                data.update(overrides)
                return data

            # A spend limit citing a kit message's id or an unknown reference is refused.
            error = native.cli(state_dir, 'task-create', payload(
                limits={'spend': {'unit': 'tokens', 'target': 1, 'ceiling': 2, 'cites': [bad]}}), ok=False)
            self.assertIn('registry', error)

            # A spend limit citing nothing is refused.
            error = native.cli(state_dir, 'task-create', payload(
                limits={'spend': {'unit': 'tokens', 'target': 1, 'ceiling': 2, 'cites': []}}), ok=False)
            self.assertIn('must cite', error)

            # A deadline citing an unregistered reference is refused.
            error = native.cli(state_dir, 'task-create', payload(
                limits={'spend': {'unit': 'tokens', 'target': 1, 'ceiling': 2, 'cites': [ref]},
                        'deadline_at': {'value': time.time() + 1000, 'cites': [bad]}}), ok=False)
            self.assertIn('registry', error)

            # An ask_first change citing an unregistered reference is refused.
            error = native.cli(state_dir, 'task-create', payload(
                ask_first={'remove': [{'item': 'making a payment', 'cites': [bad]}]}), ok=False)
            self.assertIn('registry', error)

            # A top-level statement citing an unregistered reference is refused.
            error = native.cli(state_dir, 'task-create', payload(statements=[bad]), ok=False)
            self.assertIn('registry', error)

            # A config: citation of a key the kit configuration does not hold is refused.
            error = native.cli(state_dir, 'task-create', payload(
                limits={'spend': {'unit': 'tokens', 'target': 1, 'ceiling': 2, 'cites': [ref]},
                        'deadline_at': {'value': time.time() + 1000, 'cites': ['config:missing']}}), ok=False)
            self.assertIn('kit configuration', error)

            # A config: citation of a key the kit configuration does hold is accepted.
            task = native.cli(state_dir, 'task-create', payload(
                limits={'spend': {'unit': 'tokens', 'target': 1, 'ceiling': 2, 'cites': [ref]},
                        'deadline_at': {'value': time.time() + 1000, 'cites': ['config:operator_note']}}))
            self.assertEqual(task['limits']['deadline_at']['cites'], ['config:operator_note'])

    def test_one_completion_task_per_target(self):
        root = isolate(self)
        supervisor, lead = str(uuid.uuid4()), str(uuid.uuid4())
        native = Native(root, supervisor, lead)
        state_a, state_b = root / 'state-a', root / 'state-b'
        with native.serving():
            setup_task(native, state_a, supervisor, lead, binding='supervisor')
            ref_b = bootstrap(native, state_b, supervisor, lead, binding='supervisor2')

            def payload_b():
                return {'id': 'task2', 'supervisor_id': 'supervisor2', 'target_ids': [lead], 'mode': 'completion',
                        'operator_session_id': supervisor, 'instruction': 'Deliver another report', 'scope': 'fixture',
                        'acceptance': [{'text': 'another report exists', 'owner': lead}], 'interval_seconds': 1,
                        'limits': {'spend': {'unit': 'tokens', 'target': 10, 'ceiling': 20, 'cites': [ref_b]}}}

            error = native.cli(state_b, 'task-create', payload_b(), ok=False)
            self.assertIn('one completion task per target', error)
            self.assertIn('task', error)
            self.assertIn('state-a', error)

            ledger_path = native.root / 'ledger.sqlite3'
            holder = ledger_claim(ledger_path, lead)
            self.assertIn('state-a', holder['state_root'])
            self.assertEqual(holder['task_id'], 'task')

            shutil.rmtree(state_a)
            task2 = native.cli(state_b, 'task-create', payload_b())
            self.assertEqual(task2['id'], 'task2')
            holder = ledger_claim(ledger_path, lead)
            self.assertIn('state-b', holder['state_root'])
            self.assertEqual(holder['task_id'], 'task2')

    def test_required_fields(self):
        native, state_dir, supervisor, lead = make_native(self, native_cls=BrokenRollout)
        with native.serving():
            ref = bootstrap(native, state_dir, supervisor, lead)

            def payload(**overrides):
                data = {'id': 'task', 'supervisor_id': 'supervisor', 'target_ids': [lead], 'mode': 'completion',
                        'operator_session_id': supervisor, 'instruction': 'Deliver the report', 'scope': 'fixture',
                        'acceptance': [{'text': 'the report exists', 'owner': lead}], 'interval_seconds': 1,
                        'limits': {'spend': {'unit': 'tokens', 'target': 100, 'ceiling': 200, 'cites': [ref]}}}
                data.update(overrides)
                return {key: value for key, value in data.items() if value is not None}

            error = native.cli(state_dir, 'task-create', payload(mode=None), ok=False)
            self.assertIn('mode', error)

            error = native.cli(state_dir, 'task-create', payload(operator_session_id=None), ok=False)
            self.assertIn('operator_session_id', error)

            unknown_session = str(uuid.uuid4())
            error = native.cli(state_dir, 'task-create', payload(operator_session_id=unknown_session), ok=False)
            self.assertIn('operator_session_id', error)
            self.assertIn('runtime', error)

            error = native.cli(state_dir, 'task-create', payload(limits={}), ok=False)
            self.assertIn('limits.spend', error)

            native.broken.add(lead)
            error = native.cli(state_dir, 'task-create', payload(), ok=False)
            self.assertIn('could not be read', error)
            native.broken.discard(lead)

            error = native.cli(state_dir, 'task-create', payload(
                limits={'spend': {'unit': 'currency', 'target': 10, 'ceiling': 20, 'cites': [ref]}}), ok=False)
            self.assertIn('prices', error)

            task = native.cli(state_dir, 'task-create', payload(id='task-ok',
                limits={'spend': {'unit': 'currency', 'target': 10, 'ceiling': 20, 'cites': [ref],
                                  'prices': {'input': 1.0, 'cached_input': 0.5, 'output': 2.0}}}))
            self.assertEqual(task['limits']['spend']['unit'], 'currency')
            self.assertEqual(task['limits']['spend']['prices']['output'], 2.0)

    def test_rendered_parts(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native.cli(state_dir, 'tick')
            assert_rendered(self, native.accepted[-1]['input'][0]['text'], MANDATE)

            native.cli(state_dir, 'notice', {'task_id': 'task', 'session_id': lead, 'text': 'A status check-in.'})
            assert_rendered(self, native.accepted[-1]['input'][0]['text'], MANDATE)

    def test_decision_memory(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            error = native.cli(state_dir, 'memory-add', {'supervisor_id': 'supervisor', 'task_id': 'task',
                                                           'kind': 'decision', 'source': 'lead',
                                                           'what': 'Chose plan B', 'why': 'Plan A was blocked'}, ok=False)
            self.assertIn('undo', error)

            native.cli(state_dir, 'memory-add', {'supervisor_id': 'supervisor', 'task_id': 'task', 'kind': 'decision',
                                                  'source': 'lead', 'what': 'Chose plan B', 'why': 'Plan A was blocked',
                                                  'undo': 'Revert to plan A'})
            decisions = native.cli(state_dir, 'status', identifier='task')['measured']['decisions']
            contents = [json.loads(d['content']) for d in decisions]
            self.assertIn({'what': 'Chose plan B', 'why': 'Plan A was blocked', 'undo': 'Revert to plan A'}, contents)

    def test_earlier_root_untouched(self):
        root = isolate(self)
        native = Native(root)  # no sessions needed: every command here is refused before any transport use
        legacy_dir = root / 'legacy'
        legacy_dir.mkdir(mode=0o700)
        os.chmod(legacy_dir, 0o700)
        db_path = legacy_dir / 'state.sqlite3'
        binding_id, session_id, target_id, task_id = 'supervisor', str(uuid.uuid4()), str(uuid.uuid4()), 'legacy-task'
        now = time.time()
        conn = sqlite3.connect(db_path)
        try:
            # The first six CREATE TABLE statements of Store._schema, 'executions' without the
            # three columns (triggers, closing_set, working) schema 2 added.
            conn.execute('CREATE TABLE bindings (id TEXT PRIMARY KEY, runtime TEXT NOT NULL, session_id TEXT NOT NULL UNIQUE, '
                         'target_ids TEXT NOT NULL, status TEXT NOT NULL, generation INTEGER NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)')
            conn.execute('CREATE TABLE tasks (id TEXT PRIMARY KEY, supervisor_id TEXT NOT NULL REFERENCES bindings(id), status TEXT NOT NULL, '
                         'revision INTEGER NOT NULL, generation INTEGER NOT NULL, next_run_at REAL NOT NULL, interval_seconds INTEGER, '
                         'payload TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)')
            conn.execute('CREATE TABLE executions (id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), '
                         'supervisor_id TEXT NOT NULL REFERENCES bindings(id), generation INTEGER NOT NULL, binding_generation INTEGER NOT NULL, '
                         'status TEXT NOT NULL, scheduled_at REAL NOT NULL, started_at REAL, finished_at REAL, lease_until REAL, result TEXT, '
                         'UNIQUE(task_id, scheduled_at, generation))')
            conn.execute('CREATE TABLE outbox (id TEXT PRIMARY KEY, execution_id TEXT NOT NULL REFERENCES executions(id), status TEXT NOT NULL, '
                         'payload TEXT NOT NULL, client_message_id TEXT NOT NULL UNIQUE, native_submission_id TEXT, '
                         'attempts INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, updated_at REAL NOT NULL)')
            conn.execute('CREATE TABLE audit (sequence INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, actor TEXT NOT NULL, '
                         'action TEXT NOT NULL, entity_id TEXT NOT NULL, details TEXT NOT NULL)')
            conn.execute('CREATE TABLE memory (id TEXT PRIMARY KEY, supervisor_id TEXT NOT NULL REFERENCES bindings(id), '
                         'task_id TEXT REFERENCES tasks(id), kind TEXT NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL, '
                         'evidence TEXT NOT NULL, created_at REAL NOT NULL, supersedes TEXT UNIQUE REFERENCES memory(id))')
            conn.execute('INSERT INTO bindings VALUES(?,?,?,?,?,?,?,?)',
                        (binding_id, 'codex', session_id, json.dumps([target_id]), 'active', 1, now, now))
            legacy_payload = {'mode': 'completion', 'instruction': 'Legacy task', 'target_ids': [target_id], 'scope': 'legacy',
                              'limits': {'provenance': 'legacy'}, 'ask_first': [], 'evidence': [], 'remaining': []}
            conn.execute('INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (task_id, binding_id, 'active', 1, 1, now, 600, json.dumps(legacy_payload), now, now))
            execution_id = str(uuid.uuid4())
            conn.execute('INSERT INTO executions(id,task_id,supervisor_id,generation,binding_generation,status,scheduled_at) VALUES(?,?,?,?,?,?,?)',
                         (execution_id, task_id, binding_id, 1, 1, 'delivered', now))
            conn.execute('PRAGMA user_version=1')
            conn.commit()
        finally:
            conn.close()
        os.chmod(db_path, 0o600)

        digest = lambda: hashlib.sha256(db_path.read_bytes()).hexdigest()
        baseline = digest()

        status = native.cli(legacy_dir, 'status', identifier=task_id)
        self.assertTrue(status['legacy_contract'])
        self.assertEqual(status['remedy'], LEGACY)
        self.assertEqual(digest(), baseline)

        overview = native.cli(legacy_dir, 'status')
        self.assertEqual(overview['schema_version'], 1)
        self.assertEqual(digest(), baseline)

        error = native.cli(legacy_dir, 'task-create', {'id': 'new'}, ok=False)
        self.assertEqual(error, LEGACY)
        self.assertIn('new state root', error)
        self.assertEqual(digest(), baseline)

        error = native.cli(legacy_dir, 'task-update', {'id': task_id, 'revision': 1, 'changes': {'scope': 'z'}}, ok=False)
        self.assertEqual(error, LEGACY)
        self.assertEqual(digest(), baseline)

        error = native.cli(legacy_dir, 'task-state', {'id': task_id, 'revision': 1, 'action': 'resume',
                                                        'reason': 'operator asked'}, ok=False)
        self.assertEqual(error, LEGACY)
        self.assertEqual(digest(), baseline)

        # An assessment still open on an earlier root sends nothing: it has no ledger and no queue rule.
        error = native.cli(legacy_dir, 'intervene', {'execution_id': execution_id, 'generation': 1, 'session_id': target_id,
                                                      'event_id': str(uuid.uuid4()), 'instruction': 'Do it', 'reason': 'legacy'}, ok=False)
        self.assertEqual(error, LEGACY)
        self.assertEqual(native.accepted, [])
        self.assertFalse(Path(os.environ['MRCALL_SUPERVISION_LEDGER']).exists())
        self.assertEqual(digest(), baseline)

        paused = native.cli(legacy_dir, 'task-state', {'id': task_id, 'revision': 1, 'action': 'pause',
                                                         'reason': 'operator paused'})
        self.assertEqual(paused['status'], 'paused')
        self.assertEqual(paused['revision'], 2)


if __name__ == '__main__':
    unittest.main()
