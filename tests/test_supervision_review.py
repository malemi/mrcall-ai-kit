"""Fresh-context reviews through the real CLI: the challenge before a park takes effect and the convergence review.

The reviewer is a stub command: it logs each launch and writes the verdict a test planned. No model is called.
"""
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from supervision_fixture import Native, isolate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.supervision import cli as cli_module

MANDATE = 'Deliver the report. Spend at most 50000 tokens.'
STUB = '''import json, pathlib, sys
plan, log, directory = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
kind = json.loads((directory / 'input.json').read_text())['kind']
with open(log, 'a') as handle:
    handle.write(kind + ' ' + str(directory) + '\\n')
verdict = json.loads(plan.read_text()).get(kind)
if verdict is not None:
    (directory / 'verdict.json').write_text(json.dumps(verdict))
'''
UPHOLD = {'constraint_is_operators': True, 'authorized_action': None, 'answerable': True, 'verdict': 'uphold', 'action': None,
          'position': 'The operator alone can decide this.'}
REJECT = {'constraint_is_operators': False, 'authorized_action': 'Write the outline first', 'answerable': True, 'verdict': 'reject',
          'action': 'Write the outline first', 'position': 'An authorized action exists.'}
PATH = {'on_shortest_path': True, 'shortest_path': 'The declared steps', 'cut': [], 'touches_operator': False, 'target': None,
        'intervention': None, 'question': None}
CUT = {'on_shortest_path': False, 'shortest_path': 'Write the report directly', 'cut': ['the extra survey'], 'touches_operator': False,
       'target': None, 'intervention': 'Stop the survey and write the report.', 'question': None}
ASK = {'on_shortest_path': False, 'shortest_path': 'Drop the second report', 'cut': ['report two'], 'touches_operator': True, 'target': None,
       'intervention': None, 'question': {'matter': 'Report two costs more than it returns', 'options': ['Drop it', 'Keep it'], 'recommendation': 'Drop it'}}


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.root = isolate(self)
        self.state = self.root / 'state'
        self.supervisor, self.lead = str(uuid.uuid4()), str(uuid.uuid4())
        self.native = Native(self.root, self.supervisor, self.lead)
        self.plan, self.log = self.root / 'plan.json', self.root / 'launches.log'
        stub = self.root / 'reviewer.py'
        stub.write_text(STUB)
        self.plan.write_text('{}')
        self.log.write_text('')
        os.environ['MRCALL_SUPERVISION_REVIEW_COMMAND'] = json.dumps([sys.executable, str(stub), str(self.plan), str(self.log)])
        serving = self.native.serving()
        serving.__enter__()
        self.addCleanup(lambda: serving.__exit__(None, None, None))
        self.cli('bind', {'id': 'team', 'session_id': self.supervisor, 'target_ids': [self.lead]})
        self.cli('registry-scan', {'supervisor_id': 'team'})
        self.native[self.supervisor].say(MANDATE)
        self.ref = self.cli('registry-scan', {'supervisor_id': 'team'})['registry'][-1]['ref']

    def cli(self, command, data=None, identifier=None, ok=True):
        return self.native.cli(self.state, command, data, identifier, ok)

    def create(self, **limits):
        return self.cli('task-create', {
            'id': 'task', 'supervisor_id': 'team', 'target_ids': [self.lead], 'mode': 'completion', 'operator_session_id': self.supervisor,
            'instruction': 'Deliver the report', 'scope': 'fixture', 'acceptance': [{'text': 'the report exists', 'owner': self.lead}],
            'interval_seconds': 1, 'limits': {'spend': {'unit': 'tokens', 'target': 40000, 'ceiling': 50000, 'cites': [self.ref]}} | limits})

    def wake(self):
        """Tick, let the supervisor take and finish the wake, and return the newest execution."""
        self.cli('tick')
        if self.native[self.supervisor].queue:
            self.native[self.supervisor].consume()
            self.native[self.supervisor].finish()
        return self.cli('status')['executions'][-1]

    def next_wake(self):
        time.sleep(1.2)
        return self.wake()

    def result(self, execution, ok=True, **fields):
        base = {'id': execution['id'], 'generation': execution['generation'], 'outcome': 'completed', 'summary': 'assessment', 'evidence': ['note'],
                'items': [{'id': 'A1', 'status': 'open'}], 'steps': [self.step()]}
        return self.cli('execution-result', base | fields, ok=ok)

    def step(self, artifact='report.txt', estimate=600, ident=None):
        if ident:
            return {'id': ident, 'session_id': self.lead}
        return {'session_id': self.lead, 'description': 'write the report', 'artifact': str(self.root / artifact), 'estimate_seconds': estimate}

    def park(self, execution, matter='May the lead buy the dataset?'):
        return self.result(execution, outcome='blocked', evidence=[], park={
            'reason': 'operator-input', 'completed': 'The outline is written.',
            'questions': [{'matter': matter, 'options': ['Buy it', 'Do without it'], 'recommendation': 'Do without it'}]})

    def measured(self):
        return self.cli('status', identifier='task')['measured']

    def launches(self, kind=None):
        lines = [line.split(' ', 1) for line in self.log.read_text().splitlines()]
        return [Path(directory) for name, directory in lines if kind is None or name == kind]

    def to_operator(self):
        return [entry for entry in self.native.accepted if entry['threadId'] == self.supervisor and 'AI_KIT_OPERATOR_QUESTION' in entry['input'][0]['text']]

    # ---- the challenge ----

    def test_upheld_park_takes_effect_with_the_second_reading(self):
        self.plan.write_text(json.dumps({'challenge': UPHOLD}))
        self.create()
        self.park(self.wake())
        self.assertEqual(self.measured()['parks'][-1]['status'], 'challenging')
        self.assertEqual(self.to_operator(), [])
        self.cli('tick')
        park = self.measured()['parks'][-1]
        self.assertEqual((park['status'], park['positions'][0]['verdict']), ('parked', 'uphold'))
        self.assertEqual(len(self.launches('challenge')), 1)
        question = self.to_operator()
        self.assertEqual(len(question), 1)
        self.assertIn('May the lead buy the dataset?', question[0]['input'][0]['text'])
        self.assertIn('The operator alone can decide this.', question[0]['input'][0]['text'])

    def test_rejected_park_returns_the_action_and_the_second_rejection_parks_with_both_positions(self):
        self.plan.write_text(json.dumps({'challenge': REJECT}))
        self.create()
        self.park(self.wake())
        self.cli('tick')
        status = self.cli('status', identifier='task')
        self.assertEqual(status['status'], 'active')
        self.assertEqual(status['measured']['parks'][-1]['status'], 'rejected')
        self.assertEqual(self.to_operator(), [])
        execution = self.next_wake()
        carried = [trigger for trigger in json.loads(execution['triggers']) if trigger['kind'] == 'park-rejected']
        self.assertEqual(carried[0]['action'], 'Write the outline first')
        # A second park while nothing closed and the operator said nothing: the challenge rejects again and the park stands.
        self.park(execution, matter='May the lead buy the dataset after all?')
        self.cli('tick')
        status = self.cli('status', identifier='task')
        park = status['measured']['parks'][-1]
        self.assertEqual((status['status'], park['status']), ('blocked', 'parked'))
        self.assertEqual([position['verdict'] for position in park['positions']], ['reject', 'reject'])
        self.assertEqual(len(self.launches('challenge')), 2)
        self.assertEqual(len(self.to_operator()), 1)

    def test_the_rejected_action_is_accepted_whatever_the_count(self):
        self.create()
        first = self.wake()
        for execution in (first, None):
            execution = execution or self.next_wake_after_turn()
            event = str(uuid.uuid4())
            self.cli('intervene', {'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': self.lead,
                                   'event_id': event, 'instruction': 'Write the report', 'reason': 'idle'})
            self.result(execution, closing=[{'session_id': self.lead, 'kind': 'intervention', 'event_id': event}],
                        steps=[self.step()] if execution is first else [self.step(ident='S1')])
        self.assertEqual(self.measured()['counts']['no_closure'], 2)
        self.plan.write_text(json.dumps({'challenge': REJECT}))
        third = self.next_wake_after_turn()
        self.result(third, outcome='blocked', evidence=[], steps=[self.step(ident='S1')], park={
            'reason': 'closure-bounds', 'completed': 'Two instructions, nothing closed.',
            'questions': [{'matter': 'The lead closes nothing', 'options': ['Continue', 'Stop'], 'recommendation': 'Stop'}]})
        self.cli('tick')
        fourth = self.next_wake()
        event = str(uuid.uuid4())
        self.cli('intervene', {'execution_id': fourth['id'], 'generation': fourth['generation'], 'session_id': self.lead,
                               'event_id': event, 'instruction': 'Write the outline first', 'reason': 'the second reading named it'})
        accepted = self.result(fourth, steps=[self.step(ident='S1')], closing=[{'session_id': self.lead, 'kind': 'intervention', 'event_id': event}])
        self.assertEqual(accepted['no_closure_count'], 3)

    def next_wake_after_turn(self):
        """The lead takes its queued message and ends the turn; the next assessment follows the spacing."""
        self.native[self.lead].consume()
        self.native[self.lead].finish()
        return self.next_wake()

    def test_unavailable_review_lets_the_park_take_effect(self):
        self.create()
        self.park(self.wake())
        self.cli('tick')
        park = self.measured()['parks'][-1]
        self.assertEqual((park['status'], park['positions'][0]['verdict']), ('parked', 'unavailable'))
        self.assertEqual(self.measured()['reviews'][-1]['status'], 'unavailable')
        self.assertEqual(len(self.to_operator()), 1)

    def test_no_command_takes_a_verdict_and_the_input_holds_no_history(self):
        self.assertEqual([name for name in cli_module.COMMANDS if any(word in name for word in ('verdict', 'review', 'challenge'))], [])
        self.plan.write_text(json.dumps({'challenge': UPHOLD}))
        self.create()
        execution = self.wake()
        self.cli('memory-add', {'supervisor_id': 'team', 'task_id': 'task', 'kind': 'fact', 'content': 'MEMORY-MARKER-7731', 'source': 'supervisor'})
        self.result(execution, outcome='blocked', evidence=[], summary='SUMMARY-MARKER-4419', park={
            'reason': 'operator-input', 'completed': 'The outline is written.',
            'questions': [{'matter': 'MATTER-MARKER-2206', 'options': ['Yes', 'No'], 'recommendation': 'No'}]})
        self.cli('tick')
        directory = self.launches('challenge')[0]
        text = (directory / 'input.json').read_text()
        for absent in ('MEMORY-MARKER-7731', 'SUMMARY-MARKER-4419', 'AI_KIT_SUPERVISOR_EVENT'):
            self.assertNotIn(absent, text)
        for present in ('MATTER-MARKER-2206', MANDATE, 'spending money or paid resources'):
            self.assertIn(present, text)
        self.assertEqual(sorted(json.loads(text)), ['authority', 'decision_request', 'earlier_positions', 'kind', 'measured', 'reason', 'registry', 'task'])

    def test_a_park_with_the_same_matters_after_an_operator_message_is_not_challenged_again(self):
        self.plan.write_text(json.dumps({'challenge': UPHOLD}))
        self.create()
        self.park(self.wake())
        self.cli('tick')
        self.native[self.supervisor].say('I am still thinking about it.')
        execution = self.next_wake()
        self.assertEqual(self.cli('status', identifier='task')['status'], 'active')
        self.park(execution)
        self.cli('tick')
        self.assertEqual(self.measured()['parks'][-1]['status'], 'parked')
        self.assertEqual(len(self.launches('challenge')), 1)
        self.assertEqual(len(self.to_operator()), 1)

    # ---- the convergence review ----

    def close_steps(self, verdict, count, challenge=None):
        """Declare a step, then close `count` steps one assessment after another, with `step_bound` 1."""
        self.plan.write_text(json.dumps({'convergence': verdict} | ({'challenge': challenge} if challenge else {})))
        self.create(step_bound=1)
        self.native[self.lead].status = 'active'
        execution = self.wake()
        self.result(execution, closing=[], steps=[self.step('one.txt')])
        results = []
        for number in range(1, count + 1):
            time.sleep(1.2)
            (self.root / ('one.txt' if number == 1 else f'step{number}.txt')).write_text('done')
            revision = self.cli('status', identifier='task')['revision']
            self.cli('task-update', {'id': 'task', 'revision': revision, 'changes': {'scope': f'fixture {number}'}})
            execution = self.wake()
            results.append(self.result(execution, closing=[], steps=[self.step(f'step{number + 1}.txt')], steps_closed=[f'S{number}']))
            self.cli('tick')
        return results

    def test_step_bound_launches_a_review_and_shortest_path_restarts_the_count(self):
        results = self.close_steps(PATH, 2)
        self.assertEqual(results[0]['convergence_review'], 'step-bound')
        self.assertEqual(len(self.launches('convergence')), 2)
        self.assertEqual(self.cli('status', identifier='task')['status'], 'active')
        self.assertEqual(self.measured()['counts']['step_reviews'], 0)

    def test_step_bound_parks_the_second_time_when_the_review_did_not_find_the_shortest_path(self):
        self.close_steps(CUT, 2)
        status = self.cli('status', identifier='task')
        self.assertEqual((status['status'], status['measured']['parks'][-1]['reason']), ('blocked', 'closure-bounds'))

    def test_review_intervention_reaches_the_lead_under_its_label_once_the_queue_is_empty(self):
        self.close_steps(CUT, 1)
        sent = [entry for entry in self.native.accepted if entry['threadId'] == self.lead]
        self.assertEqual(len(sent), 1)
        text = sent[0]['input'][0]['text']
        self.assertIn('FROM THE CONVERGENCE REVIEW — NOT THE OPERATOR\'S WORDS', text)
        self.assertIn('Stop the survey and write the report.', text)
        ledger = sqlite3.connect(os.environ['MRCALL_SUPERVISION_LEDGER'])
        self.assertEqual(ledger.execute("SELECT kind,session_id FROM messages WHERE client_id=?", (sent[0]['clientUserMessageId'],)).fetchone(), ('review', self.lead))
        memory = self.cli('memory-query', {'supervisor_id': 'team', 'task_id': 'task'})
        self.assertIn('Stop the survey and write the report.', [entry['content'].splitlines()[0] for entry in memory if entry['kind'] == 'intervention'])

    def test_a_cut_that_touches_the_operator_parks_only_after_the_second_reading(self):
        self.close_steps(ASK, 1, UPHOLD)
        status = self.cli('status', identifier='task')
        park = status['measured']['parks'][-1]
        self.assertEqual((status['status'], park['status'], park['reason']), ('blocked', 'challenging', 'operator-input'))
        self.assertEqual((self.launches('challenge'), self.to_operator()), ([], []))
        self.cli('tick')
        park = self.measured()['parks'][-1]
        self.assertEqual((park['status'], park['positions'][0]['verdict']), ('parked', 'uphold'))
        challenge = self.launches('challenge')
        self.assertEqual(len(challenge), 1)
        self.assertEqual(json.loads((challenge[0] / 'input.json').read_text())['decision_request']['written_by'], 'a convergence review')
        question = self.to_operator()
        self.assertEqual(len(question), 1)
        self.assertIn('Report two costs more than it returns', question[0]['input'][0]['text'])
        self.assertIn('The operator alone can decide this.', question[0]['input'][0]['text'])

    def test_a_review_park_the_second_reading_rejects_returns_the_task_with_the_action(self):
        self.close_steps(ASK, 1, REJECT)
        self.cli('tick')
        status = self.cli('status', identifier='task')
        self.assertEqual((status['status'], status['measured']['parks'][-1]['status']), ('active', 'rejected'))
        self.assertEqual(self.to_operator(), [])
        carried = [trigger for trigger in json.loads(self.next_wake()['triggers']) if trigger['kind'] == 'park-rejected']
        self.assertEqual(carried[0]['action'], 'Write the outline first')

    def test_each_measure_launches_one_convergence_review(self):
        spend = lambda: {'spend': {'unit': 'tokens', 'target': 1000, 'ceiling': 100000, 'cites': [self.ref]}}
        cases = {
            'step-overrun': (dict, lambda: None, 2.4),
            'spend-target': (spend, lambda: self.native[self.lead].spend(1500), 0),
            'spend-since-closure': (spend, lambda: self.native[self.lead].spend(600), 0),
            'time-since-closure': (lambda: {'deadline_at': {'value': time.time() + 4, 'cites': [self.ref]}}, lambda: None, 2.4),
        }
        for reason, (limits, act, pause) in cases.items():
            with self.subTest(reason=reason):
                # Each case needs its own account and task; the limits cite the mandate of that account.
                self.setUp()
                self.plan.write_text(json.dumps({'convergence': PATH}))
                self.create(**limits())
                self.native[self.lead].status = 'active'
                self.result(self.wake(), closing=[], steps=[self.step(estimate=1)])
                act()
                time.sleep(pause)
                self.cli('tick')
                self.cli('tick')
                reasons = [review['reason'].split(':')[0] for review in self.measured()['reviews'] if review['kind'] == 'convergence']
                self.assertEqual(reasons.count(reason), 1, reasons)


    # ---- a stop cannot be lifted, or a message forced, around the rules ----

    def test_a_rejected_park_then_a_closure_continues(self):
        self.plan.write_text(json.dumps({'challenge': REJECT}))
        self.create()
        self.native[self.lead].status = 'active'
        self.result(self.wake(), closing=[])
        time.sleep(1.2)
        (self.root / 'report.txt').write_text('done')
        revision = self.cli('status', identifier='task')['revision']
        self.cli('task-update', {'id': 'task', 'revision': revision, 'changes': {'scope': 'fixture again'}})
        self.result(self.wake(), outcome='blocked', evidence=[], steps=[self.step(ident='S1')], park={
            'reason': 'operator-input', 'completed': 'The outline is written.',
            'questions': [{'matter': 'May the lead buy the dataset?', 'options': ['Buy it', 'Do without it'], 'recommendation': 'Do without it'}]})
        self.cli('tick')
        closed = self.result(self.next_wake(), closing=[], steps=[self.step('next.txt')], steps_closed=['S1'])
        status = self.cli('status', identifier='task')
        self.assertEqual((status['status'], closed['closures']), ('active', 1))
        self.assertEqual((status['measured']['counts']['no_closure'], status['measured']['counts']['rejections']), (0, 0))

    def test_a_parked_task_resumes_only_with_the_operators_newer_words(self):
        self.create()
        self.park(self.wake())
        self.cli('tick')
        task = self.cli('status', identifier='task')
        resume = {'id': 'task', 'revision': task['revision'], 'action': 'resume', 'reason': 'continue'}
        self.assertIn('waits for the operator', self.cli('task-state', resume, ok=False))
        self.assertIn('newer than the park', self.cli('task-state', resume | {'cites': [self.ref]}, ok=False))
        paused = self.cli('task-state', resume | {'action': 'pause'})
        self.assertIn('waits for the operator', self.cli('task-state', resume | {'revision': paused['revision']}, ok=False))
        self.assertEqual(self.measured()['parks'][-1]['status'], 'parked')
        time.sleep(1.1)
        self.native[self.supervisor].say('Do without the dataset.')
        newer = self.cli('registry-scan', {'supervisor_id': 'team'})['registry'][-1]['ref']
        resumed = self.cli('task-state', resume | {'revision': paused['revision'], 'cites': [newer]})
        self.assertEqual(resumed['status'], 'active')

    def test_pause_and_resume_do_not_reset_the_no_closure_count(self):
        self.create()
        execution = self.wake()
        event = str(uuid.uuid4())
        self.cli('intervene', {'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': self.lead,
                               'event_id': event, 'instruction': 'Write the report', 'reason': 'idle'})
        self.result(execution, closing=[{'session_id': self.lead, 'kind': 'intervention', 'event_id': event}])
        task = self.cli('status', identifier='task')
        paused = self.cli('task-state', {'id': 'task', 'revision': task['revision'], 'action': 'pause', 'reason': 'pause'})
        self.cli('task-state', {'id': 'task', 'revision': paused['revision'], 'action': 'resume', 'reason': 'resume'})
        self.assertEqual(self.measured()['counts']['no_closure'], 1)

    def test_a_notice_is_sent_once_per_session_and_never_to_an_observation_target(self):
        self.create()
        first = self.cli('notice', {'task_id': 'task', 'session_id': self.lead, 'text': 'Supervision has ended.'})
        self.assertEqual(first['receipt'], 'queued')
        self.assertIn('already received the notice', self.cli('notice', {'task_id': 'task', 'session_id': self.lead, 'text': 'Do this now.'}, ok=False))
        self.assertEqual(len([entry for entry in self.native.accepted if entry['threadId'] == self.lead]), 1)
        self.cli('task-create', {'id': 'watch', 'supervisor_id': 'team', 'target_ids': [self.lead], 'mode': 'observation',
                                 'operator_session_id': self.supervisor, 'instruction': 'Watch', 'scope': 'fixture', 'acceptance': ['evidence']})
        self.assertIn('an observation task', self.cli('notice', {'task_id': 'watch', 'session_id': self.lead, 'text': 'x'}, ok=False))

    def test_the_ceiling_parks_on_what_was_read_when_a_worker_counter_is_missing(self):
        self.create()
        self.native[self.lead].workers[str(uuid.uuid4())] = {'usage': None, 'created_at': time.time()}
        self.native[self.lead].spend(60000)
        self.cli('tick')
        status = self.cli('status', identifier='task')
        spend = status['measured']['spend']
        self.assertEqual((status['status'], spend['value'], spend['lower_bound']), ('blocked', None, 60000))
        self.assertEqual(len(spend['unknown']), 1)


if __name__ == '__main__':
    unittest.main()
