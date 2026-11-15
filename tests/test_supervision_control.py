import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from shared.supervision.control import intervene, intervention_status, session_read
from shared.supervision.store import StoreError
from supervision_fixture import isolate, World, Native, MANDATE


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.world = World(self)
        self.world.create(interval_seconds=1)
        self.execution = self.world.wake()
        self.data = {'execution_id': self.execution['id'], 'generation': self.execution['generation'], 'session_id': self.world.target,
                     'event_id': str(uuid.uuid4()), 'instruction': 'Return to the requested result', 'reason': 'Unmet acceptance'}

    def test_uncertain_delivery_reconciles_once_never_resends(self):
        self.world.fake.refuse_send = OSError('lost acknowledgement')
        self.world.fake.reconciled = 'absent'
        before = len(self.world.fake.calls)
        self.assertEqual(intervene(self.world.store, self.world.fake, self.data)['status'], 'uncertain')
        self.world.reopen()
        self.assertEqual(intervene(self.world.store, self.world.fake, self.data)['status'], 'uncertain')
        self.assertTrue(intervene(self.world.store, self.world.fake, self.data)['replayed'])
        self.assertEqual([call[0] for call in self.world.fake.calls[before:] if call[0] in ('send', 'reconcile')], ['send', 'reconcile'])

    def test_crashed_intent_is_reconciled_without_send(self):
        intent = {key: self.data[key] for key in ('execution_id', 'generation', 'session_id', 'instruction', 'reason')}
        with self.world.store.transaction():
            self.world.store.audit('intervention-intent', self.data['event_id'], intent, 'supervisor')
        self.assertEqual(intervention_status(self.world.store, self.data['event_id'])['result']['status'], 'uncertain')
        before = len(self.world.fake.calls)
        self.assertEqual(intervene(self.world.store, self.world.fake, self.data)['status'], 'delivered')
        self.assertEqual([call[0] for call in self.world.fake.calls[before:]], ['reconcile'])

    def test_descendant_read_and_pagination(self):
        worker = self.world.fake.add()
        self.world.fake[worker].parent = self.world.target
        result = session_read(self.world.store, self.world.fake, self.data | {'session_id': worker, 'cursor': 'anchor', 'sort_direction': 'asc'})
        self.assertEqual(result['authorized_root'], self.world.target)
        self.assertEqual(result['reverse_cursor'], 'newer')
        self.assertEqual(self.world.fake.calls[-1], ('read', worker, {'cursor': 'anchor', 'sort_direction': 'asc'}))
        with self.assertRaises(StoreError):
            intervene(self.world.store, self.world.fake, self.data | {'session_id': worker})
        orphan = self.world.fake.add()
        with self.assertRaises(StoreError):
            session_read(self.world.store, self.world.fake, self.data | {'session_id': orphan})

    def test_real_cli_status_retains_uncertainty_after_detach(self):
        self.world.fake.refuse_send = OSError('accepted but acknowledgement lost')
        intervene(self.world.store, self.world.fake, self.data)
        sent = next(call for call in self.world.fake.calls if call[0] == 'send' and call[2] == self.data['event_id'])
        self.world.store.detach({'id': 'supervisor', 'reason': 'operator detached'})
        process = subprocess.run([sys.executable, os.environ.get('AI_KIT_SUPERVISION_TEST_CLI', str(ROOT / 'shared/supervision/cli.py')),
                                  '--state-dir', str(self.world.store.root), 'intervention-status', '--id', self.data['event_id']],
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        result = json.loads(process.stdout)['result']
        self.assertEqual(result['result']['status'], 'uncertain')
        self.assertEqual(len(result['history']), 3)
        text = result['history'][1]['details']['text']
        self.assertEqual(text, sent[3])
        self.assertIn(self.data['instruction'], text)
        self.assertIn("NOT THE OPERATOR'S WORDS", text)
        self.assertEqual(result['intent']['instruction'], self.data['instruction'])
        self.assertEqual(len([call for call in self.world.fake.calls if call[0] == 'send' and call[2] == self.data['event_id']]), 1)

    def test_real_cli_rejects_stale_execution_without_native_access(self):
        self.world.store.task_state({'id': 'task', 'revision': 1, 'action': 'pause', 'reason': 'operator pause'})
        for lifecycle in ('paused', 'detached'):
            if lifecycle == 'detached':
                self.world.store.task_state({'id': 'task', 'revision': 2, 'action': 'resume', 'reason': 'new assessment'})
                self.world.fake[self.world.supervisor].finish()
                execution = self.world.wake(now=time.time() + 5)
                self.data.update(execution_id=execution['id'], generation=execution['generation'])
                # Establish valid authority before detach; pause must not mask it.
                session_read(self.world.store, self.world.fake, self.data)
                self.world.store.detach({'id': 'supervisor', 'reason': 'operator detached'})
            for command in ('intervene', 'session-read'):
                with self.subTest(lifecycle=lifecycle, command=command):
                    result = subprocess.run([sys.executable, os.environ.get('AI_KIT_SUPERVISION_TEST_CLI', str(ROOT / 'shared/supervision/cli.py')),
                                             '--state-dir', str(self.world.store.root), '--codex-path', '/definitely/missing/codex', command],
                                            input=json.dumps(self.data), capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn('stale or inactive', json.loads(result.stdout)['error'])

    def test_real_cli_intervention_and_read_through_native_protocol(self):
        root = isolate(self)
        supervisor, target = str(uuid.uuid4()), str(uuid.uuid4())
        native = Native(root, supervisor, target)
        state = root / 'state'

        def cli(command, data=None, ident=None, ok=True):
            argv = [sys.executable, str(ROOT / 'shared/supervision/cli.py'), '--state-dir', str(state), '--codex-path', str(native.codex), command]
            if ident is not None:
                argv += ['--id', ident]
            process = subprocess.run(argv, input=None if data is None else json.dumps(data), capture_output=True, text=True)
            self.assertEqual(process.returncode, 0 if ok else 1, process.stdout + process.stderr)
            payload = json.loads(process.stdout)
            return payload['result'] if ok else payload['error']

        with native.serving():
            cli('bind', {'id': 'team', 'session_id': supervisor, 'target_ids': [target]})
            cli('registry-scan', {'supervisor_id': 'team'})
            native[supervisor].say(MANDATE)
            ref = cli('registry-scan', {'supervisor_id': 'team'})['registry'][-1]['ref']
            cli('task-create', {'id': 'task', 'supervisor_id': 'team', 'mode': 'completion', 'operator_session_id': supervisor,
                                'target_ids': [target], 'instruction': 'Verify delivery', 'scope': 'fixture',
                                'acceptance': [{'text': 'done', 'owner': target}], 'interval_seconds': 1,
                                'limits': {'spend': {'unit': 'tokens', 'target': 40000, 'ceiling': 50000, 'cites': [ref]}}})
            cli('tick')
            execution = cli('status')['executions'][0]
            self.assertEqual(execution['status'], 'delivered')
            data = {'execution_id': execution['id'], 'generation': execution['generation'], 'session_id': target,
                    'event_id': str(uuid.uuid4()), 'instruction': 'Continue authorized work', 'reason': 'Acceptance incomplete'}
            delivered = cli('intervene', data)
            self.assertEqual(delivered['status'], 'delivered')
            self.assertTrue(cli('intervene', data)['replayed'])
            self.assertIn('different intervention', cli('intervene', data | {'instruction': 'Different command'}, ok=False))
            intervention_call = next(call for call in native.accepted if call['threadId'] == target)
            text = intervention_call['input'][0]['text']
            self.assertIn(data['instruction'], text)
            self.assertIn("NOT THE OPERATOR'S WORDS", text)
            receipt = cli('intervention-status', ident=data['event_id'])
            self.assertEqual(receipt['intent']['instruction'], data['instruction'])
            self.assertEqual(receipt['history'][1]['details']['text'], text)
            native[target].consume()
            native[target].finish()
            second = data | {'event_id': str(uuid.uuid4()), 'instruction': 'Verify the next result'}
            cli('intervene', second)
            self.assertTrue(cli('intervene', second)['replayed'])
            read = cli('session-read', data)
            self.assertEqual(read['authorized_root'], target)
            self.assertEqual(read['thread']['id'], target)


if __name__ == '__main__':
    unittest.main()
