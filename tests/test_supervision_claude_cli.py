import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

from test_supervision_claude_transport import ClaudeFixture, stamp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from shared.supervision.store import Store
from shared.supervision.scheduler import Scheduler
from supervision_fixture import isolate


class ClaudeCLITests(unittest.TestCase):
    def setUp(self):
        isolate(self)
        self.fixture = ClaudeFixture()
        self.addCleanup(self.fixture.close)
        self.state = self.fixture.root / 'state'
        self.cron = self.fixture.root / 'crontab-data'
        self.cron.write_text('5 * * * * /foreign/job\n')
        binary = self.fixture.root / 'crontab'
        binary.write_text('#!' + sys.executable + '\nimport pathlib,sys\np=pathlib.Path(' + repr(str(self.cron)) + ')\nif sys.argv[1]=="-l": print(p.read_text(),end="")\nelse: p.write_text(sys.stdin.read())\n')
        binary.chmod(0o700)
        self.env = dict(os.environ, CLAUDE_CONFIG_DIR=str(self.fixture.config_root),
                        PATH=str(self.fixture.root) + os.pathsep + os.environ['PATH'])
        self.log = self.fixture.root / 'cli.log'

    def cli(self, command, data=None, ident=None, ok=True):
        argv = [sys.executable, os.environ.get('AI_KIT_SUPERVISION_TEST_CLI', str(ROOT / 'shared/supervision/cli.py')), '--state-dir', str(self.state),
                '--claude-path', str(self.fixture.executable), '--codex-path', '/missing/codex', command]
        if ident:
            argv += ['--id', ident]
        result = subprocess.run(argv, input=json.dumps(data) if data is not None else None,
                                env=self.env, capture_output=True, text=True)
        with self.log.open('a') as stream:
            stream.write(json.dumps({'argv': argv, 'exit': result.returncode}) + '\n' + result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0 if ok else 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        return payload['result'] if ok else payload['error']

    def task(self, binding='s', operator=None, targets=None, mode='observation'):
        return self.cli('task-create', {'id': 'task-' + binding, 'supervisor_id': binding, 'mode': mode, 'operator_session_id': operator,
                        'target_ids': targets or [], 'instruction': 'Verify delivery', 'scope': 'fixture',
                        'acceptance': ['actual result']})

    def test_activation_mixed_runtime_dispatch_and_late_reconciliation_without_resend(self):
        fixture = self.fixture
        self.cli('activate', {'id': 's', 'runtime': 'claude', 'session_id': fixture.thread_id})
        self.assertIn('--claude-path', self.cron.read_text())
        self.assertIn('CLAUDE_CONFIG_DIR=', self.cron.read_text())
        self.assertTrue(self.cron.read_text().startswith('5 * * * * /foreign/job\n'))
        self.task(operator=fixture.thread_id)
        other_session = str(uuid.uuid4())
        self.cli('bind', {'id': 'other', 'runtime': 'codex', 'session_id': other_session})
        self.task('other', operator=other_session)
        self.cli('tick')
        self.assertTrue(fixture.received.wait(2))
        status = self.cli('status')
        execution = next(x for x in status['executions'] if x['supervisor_id'] == 's')
        self.assertEqual(execution['status'], 'uncertain')
        self.assertEqual(next(x for x in status['executions'] if x['supervisor_id'] == 'other')['status'], 'not-delivered')
        self.assertEqual(self.cli('execution-reconcile', ident=execution['id'])['status'], 'uncertain')
        fixture.receipt(fixture.frames[0])
        confirmed = self.cli('execution-reconcile', ident=execution['id'])
        self.assertEqual(confirmed['status'], 'delivered')
        self.cli('execution-result', {'id': execution['id'], 'generation': execution['generation'],
                                     'outcome': 'completed', 'summary': 'Assessment complete',
                                     'evidence': ['fixture history'], 'remaining': ['Underlying task']})
        self.assertEqual(len(fixture.frames), 1)
        self.assertEqual(self.cli('status', ident='task-s')['status'], 'active')
        store = Store(self.state)
        try:
            actions = [r[0] for r in store.conn.execute('SELECT action FROM audit WHERE entity_id=?', (execution['id'],))]
            self.assertIn('delivery-uncertain', actions)
            self.assertIn('delivery-delivered', actions)
        finally:
            store.close()
        self.assertIn('identity cannot change', self.cli('bind', {'id': 's', 'runtime': 'codex', 'session_id': fixture.thread_id}, ok=False))
        self.cli('detach', {'id': 's', 'reason': 'operator detached'})
        self.assertIn('inactive', self.cli('execution-reconcile', ident=execution['id'], ok=False))
        self.cli('deactivate')
        self.assertEqual(self.cron.read_text(), '5 * * * * /foreign/job\n')

    def test_late_scheduler_observation_cannot_undo_cli_completion(self):
        fixture = self.fixture
        self.cli('bind', {'id': 's', 'runtime': 'claude', 'session_id': fixture.thread_id})
        self.task(operator=fixture.thread_id)
        self.cli('tick')
        self.assertTrue(fixture.received.wait(2))
        execution = self.cli('status')['executions'][0]
        fixture.receipt(fixture.frames[0])
        case = self
        class RacingRead:
            def reconcile(self, session, event, **_):
                case.cli('execution-reconcile', ident=execution['id'])
                case.cli('execution-result', {'id': execution['id'], 'generation': execution['generation'],
                         'outcome': 'completed', 'summary': 'Finished during scheduler read',
                         'evidence': ['peer history'], 'remaining': []})
                return {'status': 'delivered'}
        store = Store(self.state)
        try:
            Scheduler(store, RacingRead()).tick()
        finally:
            store.close()
        after = self.cli('execution-read', ident=execution['id'])
        self.assertEqual(after['status'], 'completed')
        self.assertEqual(after['result']['summary'], 'Finished during scheduler read')
        self.assertEqual(len(fixture.frames), 1)

    def test_completion_task_on_claude_sends_reads_receipts_and_stops_at_the_ceiling(self):
        fixture = self.fixture
        lead = fixture.peer()
        self.cli('bind', {'id': 's', 'runtime': 'claude', 'session_id': fixture.thread_id, 'target_ids': [lead.thread_id]})
        self.cli('registry-scan', {'supervisor_id': 's'})
        lead.human('Write the report. Spend at most 50000 tokens.', 1)
        lead.model('msg_0', (1, 0, 900, 99), stop='end_turn')
        scan = self.cli('registry-scan', {'supervisor_id': 's'})
        self.assertEqual({key: scan['sessions'][lead.thread_id][key] for key in ('state', 'unknown')}, {'state': 'idle', 'unknown': []})
        reference = scan['registry'][-1]['ref']
        data = {'id': 'task', 'supervisor_id': 's', 'mode': 'completion', 'operator_session_id': fixture.thread_id,
                'target_ids': [lead.thread_id], 'instruction': 'Deliver the report', 'scope': 'fixture',
                'acceptance': [{'text': 'the report exists', 'owner': lead.thread_id}],
                'limits': {'spend': {'unit': 'allowance_percent', 'target': 4, 'ceiling': 5, 'cites': [reference]}}}
        self.assertIn('allowance', self.cli('task-create', data, ok=False))
        data['limits']['spend'] = {'unit': 'tokens', 'target': 40000, 'ceiling': 50000, 'cites': [reference]}
        self.cli('task-create', data)
        # The lead's client holds a notification of its own task while it rests: the lead still counts as idle with nothing queued.
        lead.queue('enqueue', '<task-notification>\n<task-id>t1</task-id>\n<status>completed</status>\n</task-notification>')
        # The wake reaches the resting supervisor; nothing acknowledges it until its history shows it.
        self.cli('tick')
        self.assertTrue(fixture.received.wait(2))
        execution = self.cli('status')['executions'][0]
        self.assertEqual(execution['status'], 'uncertain')
        self.assertEqual(self.cli('execution-read', ident=execution['id'])['closing_set'], [{'session_id': lead.thread_id, 'state': 'idle'}])
        fixture.arrive(fixture.frames[0], index=1)
        fixture.status('busy')
        self.cli('tick')
        execution = self.cli('status')['executions'][0]
        self.assertEqual(execution['status'], 'delivered')
        # The supervisor reads the lead through the CLI: one bounded page, newest first.
        page = self.cli('session-read', {'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': lead.thread_id})
        self.assertEqual((page['authorized_root'], page['workers_are_full_snapshots']), (lead.thread_id, False))
        self.assertEqual(page['turns'][-1]['items'][0]['message']['content'], 'Write the report. Spend at most 50000 tokens.')
        self.assertLess(len(json.dumps(page)), 40000)
        # An intervention to the idle lead is uncertain when sent and consumed once the lead's history holds it.
        event = str(uuid.uuid4())
        sent = self.cli('intervene', {'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': lead.thread_id,
                                      'event_id': event, 'instruction': 'Write the report now', 'reason': 'unmet acceptance'})
        self.assertEqual(sent['receipt'], 'uncertain')
        frame = lead.frames()[-1]
        self.assertEqual((frame['msg_id'], frame['priority'], frame['session_id']), (event, 'next', lead.thread_id))
        self.assertIn('RESULT OWED', frame['message']['content'])
        lead.arrive(frame, index=2)
        lead.status('busy')
        measured = self.cli('observe', ident='task')['measured']
        receipt = next(entry for entry in measured['deliveries'] if entry['client_id'] == event)
        self.assertEqual((receipt['state'], measured['sessions'][lead.thread_id]['state']), ('consumed', 'working'))
        self.assertIn('queue already holds', self.queued_refusal(lead, execution))
        # The lead works past the ceiling: the task parks and the stop travels as a message that cuts the turn.
        lead.model('msg_1', (0, 0, 60000, 100))
        self.cli('tick')
        status = self.cli('status', ident='task')
        self.assertEqual(status['status'], 'blocked')
        stop = lead.frames()[-1]
        self.assertEqual(stop['priority'], 'now')
        self.assertIn('spend ceiling', stop['message']['content'])
        interrupts = status['measured']['interrupts']
        self.assertEqual([(entry['status'], entry['session_id']) for entry in interrupts], [('requested', lead.thread_id)])
        self.assertEqual(len(status['measured']['turns_continuing']), 1)
        self.assertEqual(status['measured']['spend']['lower_bound'], 60100)
        store = Store(self.state)
        try:
            kinds = [row[0] for row in store.ledger().conn.execute('SELECT kind FROM messages ORDER BY at')]
            sent = {row['kind']: row['state'] for row in store.conn.execute('SELECT kind,state FROM deliveries')}
        finally:
            store.close()
        self.assertEqual(sorted(kinds), ['interrupt', 'intervention', 'question', 'wake'])
        self.assertEqual(sent['interrupt'], 'uncertain')
        # The operator's question went once to the operator session, here the supervisor's.
        self.assertIn('AI_KIT_OPERATOR_QUESTION', fixture.frames[-1]['message']['content'])
        # The stop is read at the lead's next tool boundary and its turn ends: nothing continues.
        lead.arrive(stop, index=3)
        lead.model('msg_2', (0, 0, 10, 5), stop='end_turn')
        lead.status('idle')
        after = self.cli('observe', ident='task')['measured']
        self.assertEqual(after['turns_continuing'], [])
        self.assertEqual(next(entry for entry in after['deliveries'] if entry['kind'] == 'interrupt')['state'], 'consumed')

    def test_a_ceiling_reached_while_the_lead_rests_still_tells_it_to_stop(self):
        fixture = self.fixture
        lead = fixture.peer()
        self.cli('bind', {'id': 's', 'runtime': 'claude', 'session_id': fixture.thread_id, 'target_ids': [lead.thread_id]})
        self.cli('registry-scan', {'supervisor_id': 's'})
        lead.human('Write the report. Spend at most 50000 tokens.', 1)
        lead.model('msg_0', (1, 0, 900, 99), stop='end_turn')
        reference = self.cli('registry-scan', {'supervisor_id': 's'})['registry'][-1]['ref']
        self.cli('task-create', {'id': 'task', 'supervisor_id': 's', 'mode': 'completion', 'operator_session_id': fixture.thread_id,
                                 'target_ids': [lead.thread_id], 'instruction': 'Deliver the report', 'scope': 'fixture',
                                 'acceptance': [{'text': 'the report exists', 'owner': lead.thread_id}],
                                 'limits': {'spend': {'unit': 'tokens', 'target': 40000, 'ceiling': 50000, 'cites': [reference]}}})
        # A worker the lead started keeps spending while the lead itself rests.
        worker = fixture.project / lead.thread_id / 'subagents' / 'agent-busy.jsonl'
        worker.parent.mkdir(parents=True)
        worker.write_text(json.dumps({'type': 'assistant', 'isSidechain': True, 'sessionId': lead.thread_id, 'timestamp': stamp(),
                                      'message': {'id': 'w1', 'usage': {'input_tokens': 0, 'cache_creation_input_tokens': 0,
                                                                        'cache_read_input_tokens': 60000, 'output_tokens': 500}}}) + '\n')
        self.cli('tick')
        status = self.cli('status', ident='task')
        self.assertEqual((status['status'], status['measured']['spend']['lower_bound']), ('blocked', 60500))
        stop = lead.frames()[-1]
        self.assertEqual(stop['priority'], 'now')
        self.assertIn('spend ceiling', stop['message']['content'])
        self.assertEqual([(entry['status'], entry['turn_id']) for entry in status['measured']['interrupts']], [('requested', None)])
        self.assertEqual(status['measured']['turns_continuing'], [])
        self.assertEqual(self.cli('status')['executions'], [])

    def test_an_observation_task_at_its_ceiling_sends_nothing_to_its_targets(self):
        fixture = self.fixture
        watched = fixture.peer()
        self.cli('bind', {'id': 's', 'runtime': 'claude', 'session_id': fixture.thread_id, 'target_ids': [watched.thread_id]})
        self.cli('registry-scan', {'supervisor_id': 's'})
        watched.human('Watch this session and report. Spend at most 50000 tokens.', 1)
        watched.model('msg_0', (1, 0, 900, 99))
        watched.status('busy')
        reference = self.cli('registry-scan', {'supervisor_id': 's'})['registry'][-1]['ref']
        data = {'id': 'watch', 'supervisor_id': 's', 'mode': 'observation', 'operator_session_id': fixture.thread_id,
                'target_ids': [watched.thread_id], 'instruction': 'Report what the session does', 'scope': 'fixture', 'acceptance': ['a report']}
        # The configured default is for completion tasks: an observation task has a limit only when the operator gave one.
        (Path(os.environ['MRCALL_KIT_HOME']) / 'supervision.json').write_text(json.dumps(
            {'default_spend_limit': {'unit': 'tokens', 'target': 40000, 'ceiling': 50000}}))
        self.assertIsNone(self.cli('task-create', data, ok=True)['limits']['spend'])
        self.cli('task-state', {'id': 'watch', 'revision': 1, 'action': 'cancel', 'reason': 'replaced by a limited one'})
        limited = self.cli('task-create', data | {'id': 'limited', 'limits': {'spend': {'unit': 'tokens', 'target': 40000, 'ceiling': 50000, 'cites': [reference]}}})
        self.assertEqual(limited['limits']['spend']['ceiling'], 50000)
        watched.model('msg_1', (0, 0, 60000, 100))
        self.cli('tick')
        status = self.cli('status', ident='limited')
        self.assertEqual((status['status'], status['measured']['interrupts']), ('blocked', []))
        self.assertEqual(watched.frames(), [])

    def queued_refusal(self, lead, execution):
        """A second message while the first still sits in the lead's native queue is refused."""
        lead.queue('enqueue', 'a message the lead has not read yet')
        try:
            return self.cli('intervene', {'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': lead.thread_id,
                                          'event_id': str(uuid.uuid4()), 'instruction': 'Another message', 'reason': 'unmet acceptance'}, ok=False)
        finally:
            lead.queue('dequeue')


if __name__ == '__main__':
    unittest.main()
