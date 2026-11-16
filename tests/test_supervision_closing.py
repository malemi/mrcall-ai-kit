"""M1 property tests for closing an assessment, through the real CLI and the `Native` fixture.

Each test proves exactly one row of the Verification table in
docs/execution-plans/2026-11-14-supervision-controller-repair.md, reading the
observation the table names from where it names it.
"""
import json
import sys
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervision_fixture import Native, isolate

MANDATE = 'Deliver the report. Spend at most 50000 tokens.'


class SelectivelyUnreadableNative(Native):
    """`Native.fail` makes a whole method fail for every session; this scenario needs exactly one
    session's `thread/read` to fail while the supervisor's own reads keep succeeding, so a wake can
    still be dispatched. `unreadable_sessions` names which session ids get the failure."""

    def __init__(self, root, *session_ids):
        super().__init__(root, *session_ids)
        self.unreadable_sessions = set()

    def respond(self, method, params):
        if method == 'thread/read' and params.get('threadId') in self.unreadable_sessions:
            return {'error': {'code': -32000, 'message': 'native read failed'}}
        return super().respond(method, params)


class ClosingTests(unittest.TestCase):
    def env(self, n_targets=1, native_cls=Native):
        root = isolate(self)
        state_dir = root / 'state'
        supervisor = str(uuid.uuid4())
        targets = [str(uuid.uuid4()) for _ in range(n_targets)]
        native = native_cls(root, supervisor, *targets)
        ctx = native.serving()
        ctx.__enter__()
        self.addCleanup(lambda: ctx.__exit__(None, None, None))
        native.cli(state_dir, 'bind', {'id': 'team', 'session_id': supervisor, 'target_ids': targets})
        native.cli(state_dir, 'registry-scan', {'supervisor_id': 'team'})
        native[supervisor].say(MANDATE)
        scan = native.cli(state_dir, 'registry-scan', {'supervisor_id': 'team'})
        ref = scan['registry'][-1]['ref']
        return state_dir, native, supervisor, targets, ref

    def task_data(self, supervisor, targets, ref, **overrides):
        data = {'id': 'task', 'supervisor_id': 'team', 'target_ids': list(targets), 'mode': 'completion',
                'operator_session_id': supervisor, 'instruction': 'Deliver the report', 'scope': 'fixture',
                'acceptance': [{'text': f'report {number} exists', 'owner': target} for number, target in enumerate(targets, 1)],
                'interval_seconds': 1,
                'limits': {'spend': {'unit': 'tokens', 'target': 40000, 'ceiling': 50000, 'cites': [ref]}}}
        limits = overrides.pop('limits', None)
        data.update(overrides)
        if limits is not None:
            data['limits'] = {**data['limits'], **limits}
        return data

    def new_step(self, root, target, artifact=None, estimate=600):
        return {'session_id': target, 'description': 'write the report',
                'artifact': str(artifact or (root / 'artifact.txt')), 'estimate_seconds': estimate}

    def ref_step(self, step_id, target):
        return {'id': step_id, 'session_id': target}

    def tick_take_wake(self, native, state_dir, supervisor):
        native.cli(state_dir, 'tick')
        if native[supervisor].queue:
            native[supervisor].consume()
            native[supervisor].finish()
        return native.cli(state_dir, 'status')['executions'][-1]

    def advance(self, native, state_dir, supervisor, task_id='task', wait=1.2, changes=None):
        time.sleep(wait)
        revision = native.cli(state_dir, 'status', identifier=task_id)['revision']
        native.cli(state_dir, 'task-update', {'id': task_id, 'revision': revision,
                                              'changes': changes or {'scope': 'fixture-' + str(revision)}})
        return self.tick_take_wake(native, state_dir, supervisor)

    # ---- the four closings ----

    def test_the_four_closings(self):
        state_dir, native, supervisor, targets, ref = self.env(1)
        target = targets[0]
        root = state_dir.parent
        native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
        execution = self.tick_take_wake(native, state_dir, supervisor)
        error = native.cli(state_dir, 'execution-result', {
            'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
            'steps': [self.new_step(root, target)], 'closing': []}, ok=False)
        for phrase in ('an intervention sent in this assessment', 'a wait on a time, a file or a process exit',
                       'a park (outcome blocked with a park)', 'task-state complete or fail'):
            self.assertIn(phrase, error)
        event_id = str(uuid.uuid4())
        delivered = native.cli(state_dir, 'intervene', {
            'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': target,
            'event_id': event_id, 'instruction': 'Write the report now', 'reason': 'unmet acceptance'})
        self.assertEqual(delivered['status'], 'delivered')
        result = native.cli(state_dir, 'execution-result', {
            'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
            'steps': [self.new_step(root, target)],
            'closing': [{'session_id': target, 'kind': 'intervention', 'event_id': event_id}]})
        self.assertEqual(result['no_closure_count'], 1)

    # ---- a target that is not working is bounded ----

    def _bounded_scenario(self, prepare, native_cls=Native):
        state_dir, native, supervisor, targets, ref = self.env(1, native_cls=native_cls)
        target = targets[0]
        root = state_dir.parent
        native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
        prepare(native, target)
        native.cli(state_dir, 'tick')
        execution = native.cli(state_dir, 'status')['executions'][-1]
        return state_dir, native, supervisor, target, root, execution

    def test_a_target_that_is_not_working_is_bounded(self):
        def waiting(native, target):
            native[target].status = 'active'
            native[target].flags = ['waitingOnApproval']

        def unreachable(native, target):
            native[target].status = 'notLoaded'

        def unreadable(native, target):
            native.unreadable_sessions.add(target)

        # A waiting or unreachable target is in the closing set and accepts only a wait: a result without one is
        # refused, and the wait that is accepted raises the count when it expires unmet.
        for label, prepare in (('waiting', waiting), ('unreachable', unreachable)):
            with self.subTest(state=label):
                state_dir, native, supervisor, target, root, execution = self._bounded_scenario(prepare)
                base = {'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
                        'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
                        'steps': [self.new_step(root, target)]}
                error = native.cli(state_dir, 'execution-result', base | {'closing': []}, ok=False)
                self.assertIn('owns an open acceptance item', error)
                self.assertIn('an intervention does not close it', error)
                result = native.cli(state_dir, 'execution-result', base | {'closing': [
                    {'session_id': target, 'kind': 'wait', 'condition': {'kind': 'file', 'path': str(root / 'never.txt')},
                     'latest_at': time.time() + 1}]})
                self.assertEqual(result['no_closure_count'], 0)
                time.sleep(1.2)
                native.cli(state_dir, 'tick')
                measured = native.cli(state_dir, 'status', identifier='task')['measured']
                self.assertEqual(measured['counts']['no_closure'], 1)

        # An unreadable target is outside the closing set; a result without closure or wait raises the count.
        with self.subTest(state='unreadable'):
            state_dir, native, supervisor, target, root, execution = self._bounded_scenario(unreadable, SelectivelyUnreadableNative)
            result = native.cli(state_dir, 'execution-result', {
                'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
                'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
                'steps': [self.new_step(root, target)], 'closing': []})
            self.assertEqual(result['no_closure_count'], 1)

        for label, prepare in (('waiting', waiting), ('unreachable', unreachable)):
            with self.subTest(intervene=label):
                state_dir, native, supervisor, target, root, execution = self._bounded_scenario(prepare)
                error = native.cli(state_dir, 'intervene', {
                    'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': target,
                    'event_id': str(uuid.uuid4()), 'instruction': 'Write now', 'reason': 'unmet acceptance'}, ok=False)
                self.assertIn('a message cannot reach it now', error)

        with self.subTest(result='every item closed'):
            state_dir, native, supervisor, target, root, execution = self._bounded_scenario(lambda n, t: None)
            error = native.cli(state_dir, 'execution-result', {
                'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
                'summary': 'assessment', 'evidence': ['note'],
                'items': [{'id': 'A1', 'status': 'closed', 'evidence': ['done']}], 'closing': []}, ok=False)
            self.assertIn('task-state complete', error)

    # ---- a result names items and steps ----

    def test_a_result_names_items_and_steps(self):
        state_dir, native, supervisor, targets, ref = self.env(1)
        target = targets[0]
        native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
        execution = self.tick_take_wake(native, state_dir, supervisor)
        error = native.cli(state_dir, 'execution-result', {
            'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'], 'items': [], 'steps': [], 'closing': []}, ok=False)
        self.assertIn('items missing from the result: A1', error)
        self.assertIn('steps must name the step target', error)

    # ---- a wait on the operator is refused ----

    def test_a_wait_on_the_operator_is_refused(self):
        state_dir, native, supervisor, targets, ref = self.env(1)
        target = targets[0]
        root = state_dir.parent
        native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
        execution = self.tick_take_wake(native, state_dir, supervisor)
        error = native.cli(state_dir, 'execution-result', {
            'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
            'steps': [self.new_step(root, target)],
            'closing': [{'session_id': target, 'kind': 'wait', 'condition': {'kind': 'operator'},
                         'latest_at': time.time() + 100}]}, ok=False)
        self.assertIn('a wait on the operator is a park', error)

    # ---- blocked stops the clock ----

    def test_blocked_stops_the_clock(self):
        state_dir, native, supervisor, targets, ref = self.env(1)
        target = targets[0]
        root = state_dir.parent
        native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
        execution = self.tick_take_wake(native, state_dir, supervisor)
        park = {'reason': 'operator-input',
                'questions': [{'matter': 'Scope is unclear', 'options': ['Proceed as-is', 'Stop'],
                               'recommendation': 'Proceed as-is'}],
                'completed': 'Nothing yet.'}
        result = native.cli(state_dir, 'execution-result', {
            'id': execution['id'], 'generation': execution['generation'], 'outcome': 'blocked',
            'summary': 'assessment', 'evidence': [], 'items': [{'id': 'A1', 'status': 'open'}],
            'steps': [self.new_step(root, target)], 'park': park})
        self.assertTrue(result['task_state_changed'])
        status = native.cli(state_dir, 'status', identifier='task')
        self.assertEqual(status['status'], 'blocked')
        before = len(native.cli(state_dir, 'status')['executions'])
        native.cli(state_dir, 'tick')
        after = len(native.cli(state_dir, 'status')['executions'])
        self.assertEqual(before, after)

    # ---- an old artifact closes nothing ----

    def test_an_old_artifact_closes_nothing(self):
        # A step gets its identifier from the result that declares it, so only a later assessment can close it.
        with self.subTest(case='declared in the same assessment'):
            state_dir, native, supervisor, targets, ref = self.env(1)
            target = targets[0]
            root = state_dir.parent
            native[target].status = 'active'
            native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
            execution = self.tick_take_wake(native, state_dir, supervisor)
            artifact = root / 'same-assessment.txt'
            artifact.write_text('placeholder')
            error = native.cli(state_dir, 'execution-result', {
                'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
                'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
                'steps': [{'session_id': target, 'description': 'write', 'artifact': str(artifact), 'estimate_seconds': 600}],
                'steps_closed': ['S1'], 'closing': []}, ok=False)
            self.assertIn('step S1 is not an open step', error)
            measured = native.cli(state_dir, 'status', identifier='task')['measured']
            self.assertEqual(measured['steps'], [])

        with self.subTest(case='artifact age'):
            state_dir, native, supervisor, targets, ref = self.env(2)
            old_target, fresh_target = targets
            root = state_dir.parent
            native[old_target].status = 'active'
            native[fresh_target].status = 'active'
            old_artifact = root / 'old.txt'
            old_artifact.write_text('already here before the step is declared')
            fresh_artifact = root / 'fresh.txt'
            native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
            execution = self.tick_take_wake(native, state_dir, supervisor)
            result = native.cli(state_dir, 'execution-result', {
                'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
                'summary': 'assessment', 'evidence': ['note'],
                'items': [{'id': 'A1', 'status': 'open'}, {'id': 'A2', 'status': 'open'}],
                'steps': [{'session_id': old_target, 'description': 'old', 'artifact': str(old_artifact), 'estimate_seconds': 600},
                          {'session_id': fresh_target, 'description': 'fresh', 'artifact': str(fresh_artifact), 'estimate_seconds': 600}],
                'closing': []})
            old_id, fresh_id = result['steps_declared']
            time.sleep(1.2)
            fresh_artifact.write_text('written after the step was declared')
            execution2 = self.advance(native, state_dir, supervisor)
            result2 = native.cli(state_dir, 'execution-result', {
                'id': execution2['id'], 'generation': execution2['generation'], 'outcome': 'completed',
                'summary': 'assessment', 'evidence': ['note'],
                'items': [{'id': 'A1', 'status': 'open'}, {'id': 'A2', 'status': 'open'}],
                'steps': [self.ref_step(old_id, old_target), self.ref_step(fresh_id, fresh_target)],
                'steps_closed': [old_id, fresh_id], 'closing': []})
            kept = {entry['id']: entry['why'] for entry in result2['steps_kept_open']}
            self.assertEqual(kept.get(old_id), 'its artifact is older than the declaration')
            self.assertEqual(result2['closures'], 1)
            measured = native.cli(state_dir, 'status', identifier='task')['measured']
            statuses = {step['id']: step['status'] for step in measured['steps']}
            self.assertEqual(statuses[old_id], 'open')
            self.assertEqual(statuses[fresh_id], 'closed')

    # ---- a step declared again in the same words ----

    def test_a_step_declared_again_in_the_same_words_keeps_its_clock(self):
        state_dir, native, supervisor, targets, ref = self.env(1)
        target = targets[0]
        root = state_dir.parent
        native[target].status = 'active'
        native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
        fields = {'outcome': 'completed', 'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}], 'closing': []}
        steps = lambda: native.cli(state_dir, 'status', identifier='task')['measured']['steps']
        execution = self.tick_take_wake(native, state_dir, supervisor)
        first = native.cli(state_dir, 'execution-result', fields | {
            'id': execution['id'], 'generation': execution['generation'], 'steps': [self.new_step(root, target)]})
        self.assertEqual((first['steps_declared'], first['steps_continued']), (['S1'], []))
        declared_at = steps()[0]['declared_at']

        execution = self.advance(native, state_dir, supervisor)
        again = native.cli(state_dir, 'execution-result', fields | {
            'id': execution['id'], 'generation': execution['generation'], 'steps': [self.new_step(root, target, estimate=9000)]})
        self.assertEqual((again['steps_declared'], again['steps_continued']), ([], ['S1']))
        self.assertEqual([(step['id'], step['status'], step['declared_at'], step['estimate_seconds']) for step in steps()],
                         [('S1', 'open', declared_at, 600)])

        # Other words are another step: the open one is superseded and the new one starts its own clock.
        execution = self.advance(native, state_dir, supervisor)
        summary = self.new_step(root, target) | {'description': 'write the summary'}
        other = native.cli(state_dir, 'execution-result', fields | {
            'id': execution['id'], 'generation': execution['generation'], 'steps': [summary]})
        self.assertEqual((other['steps_declared'], other['steps_continued']), (['S2'], []))
        self.assertEqual({step['id']: step['status'] for step in steps()}, {'S1': 'superseded', 'S2': 'open'})

        # A step closed and declared again in the same result is a new step.
        (root / 'artifact.txt').write_text('done')
        execution = self.advance(native, state_dir, supervisor)
        repeated = native.cli(state_dir, 'execution-result', fields | {
            'id': execution['id'], 'generation': execution['generation'], 'steps': [summary], 'steps_closed': ['S2']})
        self.assertEqual((repeated['closures'], repeated['steps_declared'], repeated['steps_continued']), (1, ['S3'], []))

    # ---- a closure counts once ----

    def test_a_closure_counts_once(self):
        state_dir, native, supervisor, targets, ref = self.env(2)
        target1, target2 = targets
        root = state_dir.parent
        native[target1].status = 'active'
        native[target2].status = 'active'
        native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
        execution = self.tick_take_wake(native, state_dir, supervisor)
        result1 = native.cli(state_dir, 'execution-result', {
            'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'],
            'items': [{'id': 'A1', 'status': 'closed', 'evidence': ['done']}, {'id': 'A2', 'status': 'open'}],
            'steps': [self.new_step(root, target2, artifact=root / 'a2.txt')], 'closing': []})
        self.assertEqual(result1['closures'], 1)
        step_id = result1['steps_declared'][0]

        execution2 = self.advance(native, state_dir, supervisor)
        result2 = native.cli(state_dir, 'execution-result', {
            'id': execution2['id'], 'generation': execution2['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'],
            'items': [{'id': 'A1', 'status': 'open'}, {'id': 'A2', 'status': 'open'}],
            'steps': [self.ref_step(step_id, target2), self.new_step(root, target1, artifact=root / 'a1.txt')],
            'closing': []})
        self.assertEqual(result2['closures'], 0)

        execution3 = self.advance(native, state_dir, supervisor)
        result3 = native.cli(state_dir, 'execution-result', {
            'id': execution3['id'], 'generation': execution3['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'],
            'items': [{'id': 'A1', 'status': 'closed', 'evidence': ['done again']}, {'id': 'A2', 'status': 'open'}],
            'steps': [self.ref_step(step_id, target2)], 'closing': []})
        self.assertEqual(result3['closures'], 0)
        measured = native.cli(state_dir, 'status', identifier='task')['measured']
        item1 = next(item for item in measured['items'] if item['id'] == 'A1')
        self.assertEqual(item1['status'], 'closed')
        self.assertIsNotNone(item1['closed_at'])

    # ---- two idle results without closure ----

    def test_two_idle_results_without_closure(self):
        with self.subTest(target='idle'):
            state_dir, native, supervisor, targets, ref = self.env(1)
            target = targets[0]
            root = state_dir.parent
            native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
            execution = self.tick_take_wake(native, state_dir, supervisor)
            counted = 0
            for round_number in range(1, 4):
                event_id = str(uuid.uuid4())
                if round_number > 1:
                    time.sleep(1.2)
                    execution = self.tick_take_wake(native, state_dir, supervisor)
                delivered = native.cli(state_dir, 'intervene', {
                    'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': target,
                    'event_id': event_id, 'instruction': 'Write now', 'reason': 'unmet acceptance'})
                self.assertEqual(delivered['status'], 'delivered')
                fields = {'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
                          'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
                          'closing': [{'session_id': target, 'kind': 'intervention', 'event_id': event_id}]}
                fields['steps'] = [self.new_step(root, target)] if round_number == 1 else [self.ref_step('S1', target)]
                if round_number < 3:
                    result = native.cli(state_dir, 'execution-result', fields)
                    counted = result['no_closure_count']
                    native[target].consume()
                    native[target].finish()
                else:
                    error = native.cli(state_dir, 'execution-result', fields, ok=False)
                    self.assertIn('two assessments in a row closed nothing', error)
            self.assertEqual(counted, 2)

        with self.subTest(target='working'):
            state_dir, native, supervisor, targets, ref = self.env(1)
            target = targets[0]
            root = state_dir.parent
            native[target].status = 'active'
            native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
            execution = self.tick_take_wake(native, state_dir, supervisor)
            for round_number in range(1, 4):
                if round_number > 1:
                    execution = self.advance(native, state_dir, supervisor)
                fields = {'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
                          'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
                          'closing': []}
                fields['steps'] = [self.new_step(root, target)] if round_number == 1 else [self.ref_step('S1', target)]
                result = native.cli(state_dir, 'execution-result', fields)
                self.assertEqual(result['no_closure_count'], 0)

    # ---- an unmet wait counts ----

    def test_an_unmet_wait_counts(self):
        with self.subTest(outcome='expired'):
            state_dir, native, supervisor, targets, ref = self.env(1)
            target = targets[0]
            root = state_dir.parent
            native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
            execution = self.tick_take_wake(native, state_dir, supervisor)
            missing = root / 'never-appears.txt'
            result = native.cli(state_dir, 'execution-result', {
                'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
                'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
                'steps': [self.new_step(root, target)],
                'closing': [{'session_id': target, 'kind': 'wait', 'condition': {'kind': 'file', 'path': str(missing)},
                             'latest_at': time.time() + 1}]})
            self.assertEqual(result['no_closure_count'], 0)
            time.sleep(1.3)
            native.cli(state_dir, 'tick')
            measured = native.cli(state_dir, 'status', identifier='task')['measured']
            self.assertEqual(measured['counts']['no_closure'], 1)
            latest = native.cli(state_dir, 'status')['executions'][-1]
            self.assertIn('wait-expired', [entry['kind'] for entry in json.loads(latest['triggers'] or '[]')])

        with self.subTest(outcome='met'):
            state_dir, native, supervisor, targets, ref = self.env(1)
            target = targets[0]
            root = state_dir.parent
            native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
            execution = self.tick_take_wake(native, state_dir, supervisor)
            appears = root / 'appears.txt'
            result = native.cli(state_dir, 'execution-result', {
                'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
                'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
                'steps': [self.new_step(root, target)],
                'closing': [{'session_id': target, 'kind': 'wait', 'condition': {'kind': 'file', 'path': str(appears)},
                             'latest_at': time.time() + 100}]})
            self.assertEqual(result['no_closure_count'], 0)
            appears.write_text('here now')
            time.sleep(1.2)
            native.cli(state_dir, 'tick')
            measured = native.cli(state_dir, 'status', identifier='task')['measured']
            self.assertEqual(measured['counts']['no_closure'], 0)
            latest = native.cli(state_dir, 'status')['executions'][-1]
            self.assertIn('wait-met', [entry['kind'] for entry in json.loads(latest['triggers'] or '[]')])

    def test_at_the_bound_a_wait_is_refused(self):
        """Two unmet waits bring the count to two; a third result that offers another wait is refused."""
        state_dir, native, supervisor, targets, ref = self.env(1)
        target = targets[0]
        root = state_dir.parent
        native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
        execution = self.tick_take_wake(native, state_dir, supervisor)
        steps = [self.new_step(root, target)]
        for number in (1, 2, 3):
            data = {'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed', 'summary': 'assessment',
                    'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}], 'steps': steps,
                    'closing': [{'session_id': target, 'kind': 'wait', 'condition': {'kind': 'file', 'path': str(root / 'never.txt')},
                                 'latest_at': time.time() + 1}]}
            if number == 3:
                error = native.cli(state_dir, 'execution-result', data, ok=False)
                self.assertIn('two assessments in a row closed nothing', error)
                break
            native.cli(state_dir, 'execution-result', data)
            steps = [self.ref_step('S1', target)]
            time.sleep(1.2)
            execution = self.tick_take_wake(native, state_dir, supervisor)
            self.assertEqual(native.cli(state_dir, 'status', identifier='task')['measured']['counts']['no_closure'], number)

    # ---- an operator message resets counts ----

    def test_an_operator_message_resets_counts(self):
        state_dir, native, supervisor, targets, ref = self.env(1)
        target = targets[0]
        root = state_dir.parent
        native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
        execution = self.tick_take_wake(native, state_dir, supervisor)
        artifact = root / 'step.txt'
        event1 = str(uuid.uuid4())
        delivered1 = native.cli(state_dir, 'intervene', {
            'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': target,
            'event_id': event1, 'instruction': 'Write now', 'reason': 'unmet acceptance'})
        self.assertEqual(delivered1['status'], 'delivered')
        result1 = native.cli(state_dir, 'execution-result', {
            'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
            'steps': [self.new_step(root, target, artifact=artifact)],
            'closing': [{'session_id': target, 'kind': 'intervention', 'event_id': event1}]})
        self.assertEqual(result1['no_closure_count'], 1)
        step_id = result1['steps_declared'][0]
        native[target].consume()
        native[target].finish()

        time.sleep(1.2)
        artifact.write_text('done')
        execution2 = self.tick_take_wake(native, state_dir, supervisor)
        event2 = str(uuid.uuid4())
        delivered2 = native.cli(state_dir, 'intervene', {
            'execution_id': execution2['id'], 'generation': execution2['generation'], 'session_id': target,
            'event_id': event2, 'instruction': 'Write now', 'reason': 'unmet acceptance'})
        self.assertEqual(delivered2['status'], 'delivered')
        result2 = native.cli(state_dir, 'execution-result', {
            'id': execution2['id'], 'generation': execution2['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
            'steps': [self.ref_step(step_id, target)], 'steps_closed': [step_id],
            'closing': [{'session_id': target, 'kind': 'intervention', 'event_id': event2}]})
        self.assertEqual(result2['step_closures'], 1)
        self.assertEqual(result2['no_closure_count'], 0)
        native[target].consume()
        native[target].finish()

        time.sleep(1.2)
        execution3 = self.tick_take_wake(native, state_dir, supervisor)
        event3 = str(uuid.uuid4())
        delivered3 = native.cli(state_dir, 'intervene', {
            'execution_id': execution3['id'], 'generation': execution3['generation'], 'session_id': target,
            'event_id': event3, 'instruction': 'Write now', 'reason': 'unmet acceptance'})
        self.assertEqual(delivered3['status'], 'delivered')
        result3 = native.cli(state_dir, 'execution-result', {
            'id': execution3['id'], 'generation': execution3['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
            'steps': [self.new_step(root, target, artifact=root / 'other.txt')],
            'closing': [{'session_id': target, 'kind': 'intervention', 'event_id': event3}]})
        self.assertEqual(result3['no_closure_count'], 1)
        measured = native.cli(state_dir, 'status', identifier='task')['measured']
        self.assertEqual(measured['counts']['no_closure'], 1)
        self.assertEqual(measured['counts']['step_closures'], 1)

        native[supervisor].say('New instructions from the operator')
        native.cli(state_dir, 'tick')
        measured_after = native.cli(state_dir, 'status', identifier='task')['measured']
        self.assertEqual(measured_after['counts']['no_closure'], 0)
        self.assertEqual(measured_after['counts']['step_closures'], 0)

    # ---- step bound ----

    def test_step_bound(self):
        state_dir, native, supervisor, targets, ref = self.env(1)
        target = targets[0]
        root = state_dir.parent
        native[target].status = 'active'
        native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref, limits={'step_bound': 1}))
        execution = self.tick_take_wake(native, state_dir, supervisor)
        artifact_a = root / 'a.txt'
        result1 = native.cli(state_dir, 'execution-result', {
            'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
            'steps': [self.new_step(root, target, artifact=artifact_a)], 'closing': []})
        step_a = result1['steps_declared'][0]

        time.sleep(1.2)
        artifact_a.write_text('a done')
        execution2 = self.advance(native, state_dir, supervisor)
        artifact_b = root / 'b.txt'
        result2 = native.cli(state_dir, 'execution-result', {
            'id': execution2['id'], 'generation': execution2['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
            'steps': [self.new_step(root, target, artifact=artifact_b)], 'steps_closed': [step_a], 'closing': []})
        self.assertEqual(result2['convergence_review'], 'step-bound')
        step_b = result2['steps_declared'][0]
        measured = native.cli(state_dir, 'status', identifier='task')['measured']
        self.assertTrue(any(review['kind'] == 'convergence' and review['reason'] == 'step-bound' for review in measured['reviews']))

        time.sleep(1.2)
        artifact_b.write_text('b done')
        execution3 = self.advance(native, state_dir, supervisor)
        result3 = native.cli(state_dir, 'execution-result', {
            'id': execution3['id'], 'generation': execution3['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
            'steps': [self.ref_step(step_b, target)], 'steps_closed': [step_b], 'closing': []})
        self.assertTrue(result3['task_state_changed'])
        self.assertIn('park_id', result3)
        status = native.cli(state_dir, 'status', identifier='task')
        self.assertEqual(status['status'], 'blocked')
        park = next(p for p in status['measured']['parks'] if p['id'] == result3['park_id'])
        self.assertEqual(park['reason'], 'closure-bounds')

    # ---- queue rule ----

    def test_queue_rule(self):
        state_dir, native, supervisor, targets, ref = self.env(1)
        target = targets[0]
        native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
        execution = self.tick_take_wake(native, state_dir, supervisor)

        with self.subTest(case='queue holds a message'):
            before = len(native.accepted)
            native[target].queue.append({'id': 'x', 'client_id': str(uuid.uuid4()), 'text': 'someone else wrote this'})
            error = native.cli(state_dir, 'intervene', {
                'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': target,
                'event_id': str(uuid.uuid4()), 'instruction': 'Write now', 'reason': 'unmet acceptance'}, ok=False)
            self.assertIn('already holds a message', error)
            self.assertEqual(len(native.accepted), before)
            native[target].queue.clear()

        with self.subTest(case='thread/queue/list fails'):
            before = len(native.accepted)
            native.fail['thread/queue/list'] = {'code': -32000, 'message': 'queue unavailable'}
            error = native.cli(state_dir, 'intervene', {
                'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': target,
                'event_id': str(uuid.uuid4()), 'instruction': 'Write now', 'reason': 'unmet acceptance'}, ok=False)
            self.assertIn('could not be read', error)
            self.assertEqual(len(native.accepted), before)

    # ---- no message because time passed ----

    def test_no_message_because_time_passed(self):
        state_dir, native, supervisor, targets, ref = self.env(1)
        target = targets[0]
        root = state_dir.parent
        native[target].status = 'active'
        native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref, limits={'heartbeat_seconds': 1}))
        execution = self.tick_take_wake(native, state_dir, supervisor)
        native.cli(state_dir, 'execution-result', {
            'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
            'steps': [self.new_step(root, target)], 'closing': []})

        time.sleep(1.3)
        native.cli(state_dir, 'tick')
        latest = native.cli(state_dir, 'status')['executions'][-1]
        triggers = json.loads(latest['triggers'] or '[]')
        self.assertTrue(triggers and all(entry['kind'] == 'heartbeat' for entry in triggers))
        error = native.cli(state_dir, 'intervene', {
            'execution_id': latest['id'], 'generation': latest['generation'], 'session_id': target,
            'event_id': str(uuid.uuid4()), 'instruction': 'Write now', 'reason': 'unmet acceptance'}, ok=False)
        self.assertIn('long active work receives no message because time passed', error)

        native.cli(state_dir, 'execution-result', {
            'id': latest['id'], 'generation': latest['generation'], 'outcome': 'completed',
            'summary': 'assessment', 'evidence': ['note'], 'items': [{'id': 'A1', 'status': 'open'}],
            'steps': [self.ref_step('S1', target)], 'closing': []})
        next_execution = self.advance(native, state_dir, supervisor)
        next_triggers = json.loads(next_execution['triggers'] or '[]')
        self.assertFalse(all(entry['kind'] == 'heartbeat' for entry in next_triggers))
        delivered = native.cli(state_dir, 'intervene', {
            'execution_id': next_execution['id'], 'generation': next_execution['generation'], 'session_id': target,
            'event_id': str(uuid.uuid4()), 'instruction': 'Write now', 'reason': 'unmet acceptance'})
        self.assertEqual(delivered['status'], 'delivered')

    # ---- observation mode ----

    def test_observation_mode(self):
        state_dir, native, supervisor, targets, ref = self.env(1)
        target = targets[0]
        native.cli(state_dir, 'task-create', {
            'id': 'task', 'supervisor_id': 'team', 'target_ids': targets, 'mode': 'observation',
            'operator_session_id': supervisor, 'instruction': 'Watch and report', 'scope': 'fixture',
            'acceptance': ['evidence'], 'interval_seconds': 1, 'limits': {}})
        execution = self.tick_take_wake(native, state_dir, supervisor)
        error = native.cli(state_dir, 'intervene', {
            'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': target,
            'event_id': str(uuid.uuid4()), 'instruction': 'Write now', 'reason': 'curiosity'}, ok=False)
        self.assertIn('an observation task reads and reports', error)
        result = native.cli(state_dir, 'execution-result', {
            'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
            'summary': 'observed', 'evidence': ['note']})
        self.assertEqual(result['outcome'], 'completed')
        self.assertNotIn('items', result)
        self.assertNotIn('steps', result)
        self.assertNotIn('closing', result)

    # ---- park reasons ----

    def test_park_reasons(self):
        state_dir, native, supervisor, targets, ref = self.env(1)
        target = targets[0]
        root = state_dir.parent
        native.cli(state_dir, 'task-create', self.task_data(supervisor, targets, ref))
        execution = self.tick_take_wake(native, state_dir, supervisor)

        def attempt(park, ok=False):
            return native.cli(state_dir, 'execution-result', {
                'id': execution['id'], 'generation': execution['generation'], 'outcome': 'blocked',
                'summary': 'assessment', 'evidence': [], 'items': [{'id': 'A1', 'status': 'open'}],
                'steps': [self.new_step(root, target)], 'park': park}, ok=ok)

        with self.subTest(reason='unknown'):
            error = attempt({'reason': 'made-up-reason',
                              'questions': [{'matter': 'x', 'options': ['a', 'b'], 'recommendation': 'a'}],
                              'completed': 'nothing'})
            self.assertIn('is not a reason to park', error)
            self.assertIn('decide', error)
            self.assertIn('proceed', error)

        for reason in ('limit-reached', 'closure-bounds', 'delivery-unresolved'):
            with self.subTest(reason=reason):
                error = attempt({'reason': reason,
                                  'questions': [{'matter': 'x', 'options': ['a', 'b'], 'recommendation': 'a'}],
                                  'completed': 'nothing'})
                self.assertIn('the records do not show ' + reason, error)

        with self.subTest(reason='operator-restriction without citation'):
            error = attempt({'reason': 'operator-restriction',
                              'questions': [{'matter': 'x', 'options': ['a', 'b'], 'recommendation': 'a'}],
                              'completed': 'nothing', 'cites': []})
            self.assertIn('must cite the operator', error)

        with self.subTest(reason='ask-first without item'):
            error = attempt({'reason': 'ask-first',
                              'questions': [{'matter': 'x', 'options': ['a', 'b'], 'recommendation': 'a'}],
                              'completed': 'nothing'})
            self.assertIn('park.item must name the ask-first entry', error)

        with self.subTest(reason='ask-first valid'):
            result = attempt({'reason': 'ask-first',
                               'questions': [{'matter': 'Should we email the customer now?',
                                              'options': ['Send it', 'Wait'], 'recommendation': 'Wait'}],
                               'completed': 'Draft ready.', 'item': 'sending anything to customers'}, ok=True)
            self.assertTrue(result['task_state_changed'])
            status = native.cli(state_dir, 'status', identifier='task')
            self.assertEqual(status['status'], 'blocked')


if __name__ == '__main__':
    unittest.main()
