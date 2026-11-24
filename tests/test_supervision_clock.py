"""Proves the clock properties of the plan's Verification table: dispatch, spacing, heartbeat,
delivery lifecycle, abandonment, limits parks, ceiling interrupts, the operator's question,
reactivation and measured spend. Everything goes through the real CLI and the `Native` fixture,
as `m1-spec-tests.md` requires; nothing here touches the real account ledger or real Codex state.
"""
import json
from pathlib import Path
import sys
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervision_fixture import MANDATE, Native, isolate

SLEEP = 1.3


def make_native(case):
    """A fresh isolated account/kit home and a Native fixture with a supervisor and one lead."""
    root = isolate(case)
    supervisor, lead = str(uuid.uuid4()), str(uuid.uuid4())
    native = Native(root, supervisor, lead)
    return native, root / 'state', supervisor, lead


def setup_task(native, state_dir, supervisor, lead, mode='completion', interval_seconds=1, limits=None, **extra):
    """bind; registry-scan once (baseline); the operator's mandate; registry-scan again for its ref; task-create."""
    native.cli(state_dir, 'bind', {'id': 'supervisor', 'session_id': supervisor, 'target_ids': [lead]})
    native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})
    native[supervisor].say(MANDATE)
    scanned = native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})
    ref = scanned['registry'][-1]['ref']
    base_limits = {'spend': {'unit': 'tokens', 'target': 40000, 'ceiling': 50000, 'cites': [ref]}}
    if limits:
        base_limits.update(limits)
    data = {'id': 'task', 'supervisor_id': 'supervisor', 'target_ids': [lead], 'mode': mode,
            'operator_session_id': supervisor, 'instruction': 'Deliver the report', 'scope': 'fixture',
            'acceptance': [{'text': 'the report exists', 'owner': lead}] if mode == 'completion' else ['evidence'],
            'interval_seconds': interval_seconds, 'limits': base_limits}
    data.update(extra)
    task = native.cli(state_dir, 'task-create', data)
    return ref, task


def executions(native, state_dir):
    return native.cli(state_dir, 'status')['executions']


def latest_execution(native, state_dir):
    return executions(native, state_dir)[-1]


def measured(native, state_dir, task_id='task'):
    return native.cli(state_dir, 'status', identifier=task_id)['measured']


def task_status(native, state_dir, task_id='task'):
    return native.cli(state_dir, 'status', identifier=task_id)['status']


def trigger_kinds(execution):
    return [entry['kind'] for entry in json.loads(execution['triggers'] or '[]')]


def wake_text(native):
    return native.accepted[-1]['input'][0]['text']


def close_with_wait(native, state_dir, execution, lead, artifact, condition=None, latest_at=None, outcome='completed', items=None):
    """Close an assessment leaving the acceptance item open: declare a step for `lead` and a far-future wait."""
    now = time.time()
    condition = condition or {'kind': 'time', 'at': now + 100000}
    data = {'id': execution['id'], 'generation': execution['generation'], 'outcome': outcome,
            'summary': 'progress', 'evidence': ['fixture'],
            'items': items if items is not None else [{'id': 'A1', 'status': 'open'}],
            'steps': [{'session_id': lead, 'description': 'write the report', 'artifact': str(artifact), 'estimate_seconds': 600}],
            'closing': [{'session_id': lead, 'kind': 'wait', 'condition': condition, 'latest_at': latest_at or now + 200000}]}
    return native.cli(state_dir, 'execution-result', data)


class NoDispatchWithoutTriggerTests(unittest.TestCase):
    def test_closed_assessment_with_far_wait_produces_no_further_dispatch(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            ref, task = setup_task(native, state_dir, supervisor, lead)
            native.cli(state_dir, 'tick')
            execution = latest_execution(native, state_dir)
            close_with_wait(native, state_dir, execution, lead, state_dir.parent / 'report.txt')
            self.assertEqual(len(executions(native, state_dir)), 1)
            accepted_before = len(native.accepted)
            for _ in range(3):
                time.sleep(SLEEP)
                native.cli(state_dir, 'tick')
            self.assertEqual(len(executions(native, state_dir)), 1)
            self.assertEqual(len(native.accepted), accepted_before)


class TriggerOnceTests(unittest.TestCase):
    """For each trigger kind: one execution whose stored triggers and wake text list it, and ticking
    again (with no new event) dispatches no second execution."""

    def _assert_once(self, native, state_dir, kind):
        execution = latest_execution(native, state_dir)
        self.assertIn(kind, trigger_kinds(execution))
        self.assertIn(f'"kind": "{kind}"', wake_text(native))
        count = len(executions(native, state_dir))
        native.cli(state_dir, 'tick')
        self.assertEqual(len(executions(native, state_dir)), count)

    def test_activated(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native.cli(state_dir, 'tick')
            self._assert_once(native, state_dir, 'activated')

    def test_task_updated(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native.cli(state_dir, 'task-update', {'id': 'task', 'revision': 1, 'changes': {'scope': 'fixture-updated'}})
            native.cli(state_dir, 'tick')
            self._assert_once(native, state_dir, 'task-updated')

    def test_turn_ended(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native[lead].say('status update from the lead')
            native.cli(state_dir, 'tick')
            self._assert_once(native, state_dir, 'turn-ended')

    def test_target_waiting(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native[lead].status = 'active'
            native[lead].flags = ['waitingOnUserInput']
            native.cli(state_dir, 'tick')
            self._assert_once(native, state_dir, 'target-waiting')

    def test_target_unreachable(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native[lead].status = 'notLoaded'
            native.cli(state_dir, 'tick')
            self._assert_once(native, state_dir, 'target-unreachable')

    def test_operator_message(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native[supervisor].say('a fresh operator instruction')
            native.cli(state_dir, 'tick')
            self._assert_once(native, state_dir, 'operator-message')

    def test_unknown_message(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native[lead].say('an ancient message', at=0)
            native.cli(state_dir, 'tick')
            self._assert_once(native, state_dir, 'unknown-message')

    def test_step_overrun_short_estimate(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native.cli(state_dir, 'tick')
            execution = latest_execution(native, state_dir)
            now = time.time()
            native.cli(state_dir, 'execution-result', {
                'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
                'summary': 'progress', 'evidence': ['fixture'],
                'items': [{'id': 'A1', 'status': 'open'}],
                'steps': [{'session_id': lead, 'description': 'write the report',
                           'artifact': str(state_dir.parent / 'report.txt'), 'estimate_seconds': 1}],
                'closing': [{'session_id': lead, 'kind': 'wait', 'condition': {'kind': 'time', 'at': now + 100000},
                             'latest_at': now + 200000}]})
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')
            self._assert_once(native, state_dir, 'step-overrun')

    def test_spend_threshold_crossed(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            native.cli(state_dir, 'bind', {'id': 'supervisor', 'session_id': supervisor, 'target_ids': [lead]})
            native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})
            native[supervisor].say(MANDATE)
            ref = native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})['registry'][-1]['ref']
            native.cli(state_dir, 'task-create', {
                'id': 'task', 'supervisor_id': 'supervisor', 'target_ids': [lead], 'mode': 'completion',
                'operator_session_id': supervisor, 'instruction': 'Deliver the report', 'scope': 'fixture',
                'acceptance': [{'text': 'the report exists', 'owner': lead}], 'interval_seconds': 1,
                'limits': {'spend': {'unit': 'tokens', 'target': 100, 'ceiling': 100000, 'cites': [ref]}}})
            native[lead].spend(60)
            native.cli(state_dir, 'tick')
            self._assert_once(native, state_dir, 'spend-threshold')

    def test_spend_unknown(self):
        native, state_dir, supervisor, lead = make_native(self)

        class BrokenRollout(Native):
            broken = False

            def respond(self, method, params):
                answer = super().respond(method, params)
                if self.broken and method == 'thread/read' and params['threadId'] == lead:
                    answer['thread']['path'] = str(self.root / 'no-such-rollout.jsonl')
                return answer

        broken = BrokenRollout(native.root, supervisor, lead)
        with broken.serving():
            ref, task = setup_task(broken, state_dir, supervisor, lead)
            broken.broken = True
            broken.cli(state_dir, 'tick')
            self._assert_once(broken, state_dir, 'spend-unknown')

    def test_wait_met(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native.cli(state_dir, 'tick')
            execution = latest_execution(native, state_dir)
            now = time.time()
            close_with_wait(native, state_dir, execution, lead, state_dir.parent / 'report.txt',
                             condition={'kind': 'time', 'at': now + 1}, latest_at=now + 1000)
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')
            self._assert_once(native, state_dir, 'wait-met')

    def test_wait_expired(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native.cli(state_dir, 'tick')
            execution = latest_execution(native, state_dir)
            now = time.time()
            close_with_wait(native, state_dir, execution, lead, state_dir.parent / 'report.txt',
                             condition={'kind': 'file', 'path': '/nonexistent-supervision-clock-test-file'},
                             latest_at=now + 1)
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')
            self._assert_once(native, state_dir, 'wait-expired')

    def test_delivery_unresolved(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead, limits={'delivery_latest_seconds': 1})
            native.cli(state_dir, 'tick')
            execution = latest_execution(native, state_dir)
            event_id = str(uuid.uuid4())
            native.cli(state_dir, 'intervene', {'execution_id': execution['id'], 'generation': execution['generation'],
                                                 'session_id': lead, 'event_id': event_id,
                                                 'instruction': 'please proceed', 'reason': 'unmet acceptance'})
            close_with_wait(native, state_dir, execution, lead, state_dir.parent / 'report.txt',
                             condition={'kind': 'file', 'path': '/nonexistent-supervision-clock-delivery'})
            native[lead].queue.clear()
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')
            self._assert_once(native, state_dir, 'delivery-unresolved')

    def test_assessment_abandoned(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead,
                       limits={'assessment_timeout_seconds': 1, 'heartbeat_seconds': 1})
            native.cli(state_dir, 'tick')
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')  # delivered -> unhealthy
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')  # unhealthy -> abandoned, re-wake
            self._assert_once(native, state_dir, 'assessment-abandoned')

    def test_heartbeat(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            ref, task = setup_task(native, state_dir, supervisor, lead, mode='observation',
                                    limits={'heartbeat_seconds': 1})
            native.cli(state_dir, 'tick')
            execution = latest_execution(native, state_dir)
            native[supervisor].consume()
            native[supervisor].finish()  # the wake's delivery must be consumed: a queued delivery blocks heartbeat
            native.cli(state_dir, 'execution-result', {'id': execution['id'], 'generation': execution['generation'],
                                                        'outcome': 'completed', 'summary': 'ok', 'evidence': ['fixture']})
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')
            self._assert_once(native, state_dir, 'heartbeat')


class SpacingTests(unittest.TestCase):
    def test_spacing_postpones_a_trigger(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead, interval_seconds=3)
            native.cli(state_dir, 'tick')
            execution = latest_execution(native, state_dir)
            close_with_wait(native, state_dir, execution, lead, state_dir.parent / 'report.txt')
            native[lead].status = 'active'
            native[lead].flags = ['waitingOnUserInput']
            native.cli(state_dir, 'tick')
            self.assertEqual(len(executions(native, state_dir)), 1)
            time.sleep(3.2)
            native.cli(state_dir, 'tick')
            after = executions(native, state_dir)
            self.assertEqual(len(after), 2)
            self.assertIn('target-waiting', trigger_kinds(after[-1]))


class HeartbeatTests(unittest.TestCase):
    def test_no_heartbeat_while_wait_pending(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead, limits={'heartbeat_seconds': 1})
            native.cli(state_dir, 'tick')
            execution = latest_execution(native, state_dir)
            native[supervisor].consume()
            native[supervisor].finish()  # isolate the wait as the sole blocker: the wake itself must not be queued
            now = time.time()
            close_with_wait(native, state_dir, execution, lead, state_dir.parent / 'report.txt',
                             condition={'kind': 'time', 'at': now + 100000}, latest_at=now + 200000)
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')
            self.assertEqual(len(executions(native, state_dir)), 1)

    def test_no_heartbeat_while_delivery_queued(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead,
                       limits={'heartbeat_seconds': 1, 'delivery_latest_seconds': 100000})
            native.cli(state_dir, 'tick')
            execution = latest_execution(native, state_dir)
            native[supervisor].consume()
            native[supervisor].finish()  # isolate the intervention as the sole blocker
            event_id = str(uuid.uuid4())
            native.cli(state_dir, 'intervene', {'execution_id': execution['id'], 'generation': execution['generation'],
                                                 'session_id': lead, 'event_id': event_id,
                                                 'instruction': 'please proceed', 'reason': 'unmet acceptance'})
            close_with_wait(native, state_dir, execution, lead, state_dir.parent / 'report.txt')
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')
            self.assertEqual(len(executions(native, state_dir)), 1)
            self.assertEqual(measured(native, state_dir)['deliveries'][-1]['state'], 'queued')

    def test_one_heartbeat_over_a_working_target_with_nothing_pending(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead, limits={'heartbeat_seconds': 1})
            native[lead].status = 'active'  # working: active status, no waiting flags, no message sent
            native.cli(state_dir, 'tick')
            execution = latest_execution(native, state_dir)
            native[supervisor].consume()
            native[supervisor].finish()  # the wake's delivery must be consumed: a queued delivery blocks heartbeat
            native.cli(state_dir, 'execution-result', {
                'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed',
                'summary': 'progress', 'evidence': ['fixture'],
                'items': [{'id': 'A1', 'status': 'open'}],
                'steps': [{'session_id': lead, 'description': 'write the report',
                           'artifact': str(state_dir.parent / 'report.txt'), 'estimate_seconds': 600}],
                'closing': []})
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')
            execution2 = latest_execution(native, state_dir)
            self.assertIn('heartbeat', trigger_kinds(execution2))
            count = len(executions(native, state_dir))
            native.cli(state_dir, 'tick')
            self.assertEqual(len(executions(native, state_dir)), count)


class DeliveryLifecycleTests(unittest.TestCase):
    def test_queued_then_consumed_with_its_turn(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead)
            native.cli(state_dir, 'tick')
            execution = latest_execution(native, state_dir)
            event_id = str(uuid.uuid4())
            native.cli(state_dir, 'intervene', {'execution_id': execution['id'], 'generation': execution['generation'],
                                                 'session_id': lead, 'event_id': event_id,
                                                 'instruction': 'please proceed', 'reason': 'unmet acceptance'})
            delivery = next(d for d in measured(native, state_dir)['deliveries'] if d['client_id'] == event_id)
            self.assertEqual(delivery['state'], 'queued')
            native[lead].consume()
            native.cli(state_dir, 'observe', identifier='task')
            delivery = next(d for d in measured(native, state_dir)['deliveries'] if d['client_id'] == event_id)
            self.assertEqual(delivery['state'], 'consumed')
            self.assertEqual(delivery['turn_id'], native[lead].turns[-1]['id'])

    def test_unresolved_variants_and_accepted_park(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead, limits={'delivery_latest_seconds': 1})
            native.cli(state_dir, 'tick')
            execution = latest_execution(native, state_dir)

            native[lead].say('working', running=True)
            event1 = str(uuid.uuid4())
            native.cli(state_dir, 'intervene', {'execution_id': execution['id'], 'generation': execution['generation'],
                                                 'session_id': lead, 'event_id': event1,
                                                 'instruction': 'keep going', 'reason': 'unmet acceptance'})
            time.sleep(SLEEP)
            native.cli(state_dir, 'observe', identifier='task')
            delivery1 = next(d for d in measured(native, state_dir)['deliveries'] if d['client_id'] == event1)
            self.assertEqual(delivery1['state'], 'queued')  # behind a working target, past latest, still queued

            native[lead].finish()
            native[lead].queue = [entry for entry in native[lead].queue if entry['client_id'] != event1]
            native.cli(state_dir, 'observe', identifier='task')
            delivery1 = next(d for d in measured(native, state_dir)['deliveries'] if d['client_id'] == event1)
            self.assertEqual(delivery1['state'], 'unresolved')  # vanished from both queue and history

            event2 = str(uuid.uuid4())
            native.cli(state_dir, 'intervene', {'execution_id': execution['id'], 'generation': execution['generation'],
                                                 'session_id': lead, 'event_id': event2,
                                                 'instruction': 'and again', 'reason': 'unmet acceptance'})
            time.sleep(SLEEP)
            native.cli(state_dir, 'observe', identifier='task')
            delivery2 = next(d for d in measured(native, state_dir)['deliveries'] if d['client_id'] == event2)
            self.assertEqual(delivery2['state'], 'unresolved')  # queued on an idle target, past latest

            triggers = [t['kind'] for t in measured(native, state_dir)['triggers']]
            self.assertIn('delivery-unresolved', triggers)

            result = native.cli(state_dir, 'execution-result', {
                'id': execution['id'], 'generation': execution['generation'], 'outcome': 'blocked',
                'summary': 'stuck', 'evidence': ['fixture'],
                'items': [{'id': 'A1', 'status': 'open'}],
                'steps': [{'session_id': lead, 'description': 'write the report',
                           'artifact': str(state_dir.parent / 'report.txt'), 'estimate_seconds': 600}],
                'park': {'reason': 'delivery-unresolved',
                         'questions': [{'matter': 'Two interventions went unresolved.',
                                        'options': ['Check the supervisor session and write there to resume', 'Stop the task'],
                                        'recommendation': 'Open the supervisor session.'}],
                         'completed': 'nothing else can proceed', 'cites': []}})
            self.assertTrue(result['task_state_changed'])
            self.assertEqual(task_status(native, state_dir), 'blocked')


class AbandonedAssessmentTests(unittest.TestCase):
    def test_abandoned_rewakes_then_parks_on_second(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead,
                       limits={'assessment_timeout_seconds': 1, 'heartbeat_seconds': 1})
            native.cli(state_dir, 'tick')
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')  # delivered -> unhealthy
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')  # unhealthy -> abandoned (1st), re-wake
            execution2 = latest_execution(native, state_dir)
            self.assertIn('assessment-abandoned', trigger_kinds(execution2))
            self.assertEqual(measured(native, state_dir)['counts']['abandoned'], 1)
            self.assertEqual(task_status(native, state_dir), 'active')

            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')  # 2nd execution: delivered -> unhealthy
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')  # 2nd abandoned: parks
            self.assertEqual(task_status(native, state_dir), 'blocked')
            parks = measured(native, state_dir)['parks']
            self.assertEqual(parks[-1]['reason'], 'delivery-unresolved')

    def test_lost_wake_in_idle_supervisor_queue_parks(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            setup_task(native, state_dir, supervisor, lead, limits={'delivery_latest_seconds': 1})
            native.cli(state_dir, 'tick')  # wake delivered to supervisor's queue, never consumed
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')  # observe marks the wake delivery unresolved
            time.sleep(SLEEP)
            native.cli(state_dir, 'tick')  # abandon sees the unresolved wake and parks
            self.assertEqual(task_status(native, state_dir), 'blocked')
            parks = measured(native, state_dir)['parks']
            self.assertEqual(parks[-1]['reason'], 'delivery-unresolved')
            count = len(executions(native, state_dir))
            native.cli(state_dir, 'tick')
            self.assertEqual(len(executions(native, state_dir)), count)


class LimitsParkTests(unittest.TestCase):
    def test_deadline_parks_and_stops_the_clock(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            native.cli(state_dir, 'bind', {'id': 'supervisor', 'session_id': supervisor, 'target_ids': [lead]})
            native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})
            native[supervisor].say(MANDATE)
            ref = native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})['registry'][-1]['ref']
            native.cli(state_dir, 'task-create', {
                'id': 'task', 'supervisor_id': 'supervisor', 'target_ids': [lead], 'mode': 'completion',
                'operator_session_id': supervisor, 'instruction': 'Deliver the report', 'scope': 'fixture',
                'acceptance': [{'text': 'the report exists', 'owner': lead}], 'interval_seconds': 1,
                'limits': {'spend': {'unit': 'tokens', 'target': 40000, 'ceiling': 50000, 'cites': [ref]},
                           'deadline_at': {'value': time.time() - 10, 'cites': [ref]}}})
            native.cli(state_dir, 'tick')
            self.assertEqual(task_status(native, state_dir), 'blocked')
            parks = measured(native, state_dir)['parks']
            self.assertEqual(parks[-1]['reason'], 'limit-reached')
            count = len(executions(native, state_dir))
            native.cli(state_dir, 'tick')
            self.assertEqual(len(executions(native, state_dir)), count)

    def test_max_checks_parks_and_stops_the_clock(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            ref, task = setup_task(native, state_dir, supervisor, lead)
            native.cli(state_dir, 'task-update', {'id': 'task', 'revision': task['revision'],
                                                   'changes': {'limits': task['limits'] | {'max_checks': {'value': 1, 'cites': [ref]}}}})
            native.cli(state_dir, 'tick')  # dispatches the one assessment the operator allowed
            native.cli(state_dir, 'tick')
            self.assertEqual(task_status(native, state_dir), 'active')  # the last allowed assessment is not cut off while it runs
            close_with_wait(native, state_dir, latest_execution(native, state_dir), lead, state_dir.parent / 'report.txt')
            native.cli(state_dir, 'tick')  # one assessment ended: the count is reached and the task parks
            self.assertEqual(task_status(native, state_dir), 'blocked')
            self.assertEqual(measured(native, state_dir)['parks'][-1]['reason'], 'limit-reached')
            count = len(executions(native, state_dir))
            native.cli(state_dir, 'tick')
            self.assertEqual(len(executions(native, state_dir)), count)

    def test_spend_ceiling_parks_and_stops_the_clock(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            native.cli(state_dir, 'bind', {'id': 'supervisor', 'session_id': supervisor, 'target_ids': [lead]})
            native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})
            native[supervisor].say(MANDATE)
            ref = native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})['registry'][-1]['ref']
            native.cli(state_dir, 'task-create', {
                'id': 'task', 'supervisor_id': 'supervisor', 'target_ids': [lead], 'mode': 'completion',
                'operator_session_id': supervisor, 'instruction': 'Deliver the report', 'scope': 'fixture',
                'acceptance': [{'text': 'the report exists', 'owner': lead}], 'interval_seconds': 1,
                'limits': {'spend': {'unit': 'tokens', 'target': 100, 'ceiling': 200, 'cites': [ref]}}})
            native[lead].spend(500)
            native.cli(state_dir, 'tick')
            self.assertEqual(task_status(native, state_dir), 'blocked')
            self.assertEqual(measured(native, state_dir)['parks'][-1]['reason'], 'limit-reached')
            count = len(executions(native, state_dir))
            native.cli(state_dir, 'tick')
            self.assertEqual(len(executions(native, state_dir)), count)


class CeilingInterruptTests(unittest.TestCase):
    def test_running_turn_interrupted_at_ceiling(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            native.cli(state_dir, 'bind', {'id': 'supervisor', 'session_id': supervisor, 'target_ids': [lead]})
            native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})
            native[supervisor].say(MANDATE)
            ref = native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})['registry'][-1]['ref']
            native.cli(state_dir, 'task-create', {
                'id': 'task', 'supervisor_id': 'supervisor', 'target_ids': [lead], 'mode': 'completion',
                'operator_session_id': supervisor, 'instruction': 'Deliver the report', 'scope': 'fixture',
                'acceptance': [{'text': 'the report exists', 'owner': lead}], 'interval_seconds': 1,
                'limits': {'spend': {'unit': 'tokens', 'target': 100, 'ceiling': 200, 'cites': [ref]}}})
            native[lead].say('working', running=True)
            native[lead].spend(500)
            native.cli(state_dir, 'tick')
            self.assertEqual(len(native.interrupts), 1)
            self.assertEqual(native.interrupts[0]['threadId'], lead)
            self.assertEqual(native.interrupts[0]['turnId'], native[lead].turns[-1]['id'])
            self.assertEqual(measured(native, state_dir)['interrupts'][-1]['status'], 'interrupted')

    def test_failed_interrupt_reports_turn_continuing(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            native.cli(state_dir, 'bind', {'id': 'supervisor', 'session_id': supervisor, 'target_ids': [lead]})
            native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})
            native[supervisor].say(MANDATE)
            ref = native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})['registry'][-1]['ref']
            native.cli(state_dir, 'task-create', {
                'id': 'task', 'supervisor_id': 'supervisor', 'target_ids': [lead], 'mode': 'completion',
                'operator_session_id': supervisor, 'instruction': 'Deliver the report', 'scope': 'fixture',
                'acceptance': [{'text': 'the report exists', 'owner': lead}], 'interval_seconds': 1,
                'limits': {'spend': {'unit': 'tokens', 'target': 100, 'ceiling': 200, 'cites': [ref]}}})
            native[lead].say('working', running=True)
            running_turn_id = native[lead].turns[-1]['id']
            native[lead].spend(500)
            native.fail['turn/interrupt'] = {'code': -32000, 'message': 'refused'}
            native.cli(state_dir, 'tick')
            measurement = measured(native, state_dir)
            self.assertTrue(any(entry['status'] == 'continues' for entry in measurement['interrupts']))
            self.assertTrue(any(entry['turn_id'] == running_turn_id for entry in measurement['turns_continuing']),
                             measurement['turns_continuing'])
            self.assertEqual(measurement['sessions'][lead]['running_turn']['id'], running_turn_id)


class QuestionNoTimerTests(unittest.TestCase):
    def test_one_question_sent_then_no_more(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            native.cli(state_dir, 'bind', {'id': 'supervisor', 'session_id': supervisor, 'target_ids': [lead]})
            native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})
            native[supervisor].say(MANDATE)
            ref = native.cli(state_dir, 'registry-scan', {'supervisor_id': 'supervisor'})['registry'][-1]['ref']
            native.cli(state_dir, 'task-create', {
                'id': 'task', 'supervisor_id': 'supervisor', 'target_ids': [lead], 'mode': 'completion',
                'operator_session_id': supervisor, 'instruction': 'Deliver the report', 'scope': 'fixture',
                'acceptance': [{'text': 'the report exists', 'owner': lead}], 'interval_seconds': 1,
                'limits': {'spend': {'unit': 'tokens', 'target': 40000, 'ceiling': 50000, 'cites': [ref]},
                           'deadline_at': {'value': time.time() - 10, 'cites': [ref]}}})
            native.cli(state_dir, 'tick')
            self.assertEqual(task_status(native, state_dir), 'blocked')
            to_supervisor = [p for p in native.accepted if p['threadId'] == supervisor]
            self.assertEqual(len(to_supervisor), 1)
            park = measured(native, state_dir)['parks'][-1]
            self.assertIn(park['request']['questions'][0]['matter'], to_supervisor[0]['input'][0]['text'])
            for option in park['request']['questions'][0]['options']:
                self.assertIn(option, to_supervisor[0]['input'][0]['text'])
            self.assertIn('wait', to_supervisor[0]['input'][0]['text'].lower())
            count_before = len(native.accepted)
            for _ in range(2):
                time.sleep(SLEEP)
                native.cli(state_dir, 'tick')
            self.assertEqual(len(native.accepted), count_before)
            self.assertEqual(len(executions(native, state_dir)), 0)


class OperatorReactivationTests(unittest.TestCase):
    def _park_on_limit(self, native, state_dir, supervisor, lead):
        ref, task = setup_task(native, state_dir, supervisor, lead)
        native.cli(state_dir, 'task-update', {'id': 'task', 'revision': task['revision'],
                                               'changes': {'limits': task['limits'] | {'max_checks': {'value': 1, 'cites': [ref]}}}})
        native.cli(state_dir, 'tick')
        execution = latest_execution(native, state_dir)
        close_with_wait(native, state_dir, execution, lead, state_dir.parent / 'report.txt')
        native.cli(state_dir, 'tick')  # count=1 >= max_checks=1: parks, question sent
        self.assertEqual(task_status(native, state_dir), 'blocked')
        return ref

    def test_operator_message_reactivates_and_repeated_park_is_silent(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            self._park_on_limit(native, state_dir, supervisor, lead)
            sent_before = len(native.accepted)
            native[supervisor].say('please raise the limit, we need more checks')
            time.sleep(SLEEP)  # interval_seconds spacing since the previous execution's scheduled_at
            native.cli(state_dir, 'tick')
            self.assertEqual(task_status(native, state_dir), 'active')
            execution2 = latest_execution(native, state_dir)
            self.assertEqual(trigger_kinds(execution2), ['operator-message'])
            self.assertEqual(len(executions(native, state_dir)), 2)

            park = measured(native, state_dir)['parks'][-1]
            questions = park['request']['questions']
            result = native.cli(state_dir, 'execution-result', {
                'id': execution2['id'], 'generation': execution2['generation'], 'outcome': 'blocked',
                'summary': 'still blocked', 'evidence': ['fixture'],
                'items': [{'id': 'A1', 'status': 'open'}],
                'steps': [{'session_id': lead, 'id': 'S1'}],
                'park': {'reason': park['reason'], 'questions': questions, 'completed': 'still nothing new', 'cites': []}})
            self.assertTrue(result['task_state_changed'])
            self.assertEqual(task_status(native, state_dir), 'blocked')
            self.assertEqual(len(native.accepted), sent_before + 1)  # only the operator-message wake, no new question

    def test_raised_limit_after_reactivation_keeps_task_active(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            self._park_on_limit(native, state_dir, supervisor, lead)
            native[supervisor].say('please raise the limit, we need more checks')
            time.sleep(SLEEP)  # interval_seconds spacing since the previous execution's scheduled_at
            native.cli(state_dir, 'tick')
            self.assertEqual(task_status(native, state_dir), 'active')

            new_ref = native.cli(state_dir, 'registry', identifier=supervisor)[-1]['ref']
            current = native.cli(state_dir, 'status', identifier='task')
            updated = native.cli(state_dir, 'task-update', {
                'id': 'task', 'revision': current['revision'],
                'changes': {'limits': current['limits'] | {'max_checks': {'value': 5, 'cites': [new_ref]}}}})
            self.assertEqual(updated['limits']['max_checks']['cites'], [new_ref])
            self.assertEqual(task_status(native, state_dir), 'active')
            time.sleep(1.2)
            native.cli(state_dir, 'tick')
            self.assertEqual(task_status(native, state_dir), 'active')


class SpendMeasuredTests(unittest.TestCase):
    def test_spend_sums_supervisor_target_and_new_worker_deltas(self):
        native, state_dir, supervisor, lead = make_native(self)
        with native.serving():
            before_worker = str(uuid.uuid4())
            native[lead].workers[before_worker] = {'usage': {'total': 500, 'input': 450, 'cached_input': 100, 'output': 50},
                                                     'created_at': time.time() - 100}
            setup_task(native, state_dir, supervisor, lead)

            after_worker = str(uuid.uuid4())
            native[lead].workers[after_worker] = {'usage': {'total': 0, 'input': 0, 'cached_input': 0, 'output': 0},
                                                   'created_at': time.time()}
            native.cli(state_dir, 'observe', identifier='task')  # establishes the new worker's zero baseline

            supervisor_delta, lead_delta, worker_delta = 37, 53, 211
            native[supervisor].spend(supervisor_delta)
            native[lead].spend(lead_delta)
            native[lead].workers[after_worker]['usage']['total'] += worker_delta
            native[lead].workers[after_worker]['usage']['input'] += worker_delta

            native.cli(state_dir, 'observe', identifier='task')
            spend = measured(native, state_dir)['spend']
            self.assertEqual(spend['unknown'], [])
            self.assertEqual(spend['value'], supervisor_delta + lead_delta + worker_delta)


if __name__ == '__main__':
    unittest.main()
