"""Deterministic protocol, cross-turn and installed CLI regressions."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'shared/scripts/completion_check.py'
spec = importlib.util.spec_from_file_location('completion_check', SCRIPT)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class Completion(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name) / 'home'
        self.home.mkdir()
        self.env = patch.dict(os.environ, {'HOME': str(self.home), 'CODEX_HOME': str(self.home / '.codex'), 'MRCALL_COMPLETION_REQUIRE_REVIEW': '1'})
        self.env.start()
        self.handoff = patch.object(core, 'handoffs', lambda: core.private_dir(Path(self.temp.name) / 'handoffs'))
        self.handoff.start()
        self.payload = dict(hook_event_name='Stop', session_id='one', turn_id='first',
                            cwd=str(self.home), last_assistant_message='Done.')

    def tearDown(self):
        self.handoff.stop()
        self.env.stop()
        self.temp.cleanup()

    def challenge(self, payload=None):
        response = core.hook(payload or self.payload)
        self.assertEqual(response['decision'], 'block')
        states = list((core.root() / 'state').glob('*.json'))
        for path in states:
            state = core.read(path)
            if state.get('challenge', {}).get('session_id') == (payload or self.payload)['session_id']:
                return core.request_path(state['challenge']['nonce'])
        self.fail('no challenge')

    def review(self, **changes):
        return dict(assignment='Answer the bounded fixture question.', acceptance=['Answer supplied.'],
                    evidence=[], remaining=[], decision='complete', rationale='The requested answer is present.',
                    answer='Done.', **changes)

    def test_review_executes_and_exact_answer_allows(self):
        request = self.challenge()
        core.submit(request, self.review())
        self.assertEqual(core.hook(dict(self.payload, stop_hook_active=True)), {})
        audit = core.read(core.root() / 'last-observed.json')
        self.assertEqual(audit['outcome'], 'complete')
        self.assertFalse(request.exists())

    def test_bypass_never_passes_second_stop_or_cap(self):
        self.challenge()
        self.challenge(dict(self.payload, stop_hook_active=True))
        response = core.hook(self.payload)
        self.assertFalse(response['continue'])
        self.assertEqual(core.read(core.root() / 'last-observed.json')['outcome'], 'failed')

    def test_new_turn_and_foreign_receipt_cannot_reuse_review(self):
        request = self.challenge()
        core.submit(request, self.review())
        other = dict(self.payload, session_id='two')
        other_request = self.challenge(other)
        core.write(other_request.with_suffix('.receipt.json'), core.read(request.with_suffix('.receipt.json')))
        self.assertEqual(core.hook(other)['decision'], 'block')
        self.assertEqual(core.hook(self.payload), {})
        self.assertEqual(core.hook(dict(self.payload, turn_id='second'))['decision'], 'block')

    def test_changed_answer_and_expired_receipt_refuse(self):
        request = self.challenge()
        core.submit(request, self.review())
        self.assertEqual(core.hook(dict(self.payload, last_assistant_message='Changed.'))['decision'], 'block')
        request = self.challenge(dict(self.payload, turn_id='expiry'))
        with patch.object(core.time, 'time', return_value=time.time() + core.TTL + 1):
            with self.assertRaises(ValueError):
                core.submit(request, self.review())

    def test_legitimate_limited_and_continue(self):
        request = self.challenge()
        review = self.review()
        review.update(decision='limited', remaining=['Operator approval required.'], stop_condition='authority')
        core.submit(request, review)
        self.assertEqual(core.hook(self.payload), {})
        self.assertEqual(core.read(core.root() / 'last-observed.json')['outcome'], 'limited')
        review.update(decision='continue')
        request = self.challenge(dict(self.payload, turn_id='next'))
        core.submit(request, review)
        self.assertEqual(core.hook(dict(self.payload, turn_id='next'))['decision'], 'block')

    def test_literal_nr_exemption_is_turn_bound(self):
        core.hook(dict(self.payload, hook_event_name='UserPromptSubmit', prompt='$nr What is 2+2?'))
        self.assertEqual(core.hook(self.payload), {})
        self.assertEqual(core.read(core.root() / 'last-observed.json')['outcome'], 'exempt')
        self.assertEqual(core.hook(dict(self.payload, turn_id='another'))['decision'], 'block')

    def test_explicit_task_gate_executes_and_failure_refuses(self):
        request = self.challenge()
        path = core.root() / 'state' / (core.identity(self.payload) + '.json')
        state = core.read(path)
        state['binding'] = {'repo': str(self.home), 'task': 'explicit', 'context': 'now'}
        core.write(path, state)
        core.submit(request, self.review())
        with patch.object(core, 'gate', side_effect=ValueError('bound gate failed')) as gate:
            response = core.hook(self.payload)
        self.assertEqual(gate.call_count, 1)
        self.assertEqual(response['decision'], 'block')
        self.assertIn('bound gate failed', response['reason'])

    def test_malformed_and_symlink_handoff_fail_closed(self):
        with self.assertRaises(ValueError):
            core.hook(dict(self.payload, session_id=''))
        request = self.challenge()
        request.with_suffix('.receipt.json').symlink_to(request)
        self.assertEqual(core.hook(self.payload)['decision'], 'block')
        with self.assertRaises(ValueError):
            core.validate_review({'decision': 'complete'})

    def test_strict_audit_rejects_stale_foreign_mismatch_failure(self):
        now = time.time()
        value = dict(schema_version=1, run_id='run', session_id='session', turn_id='turn',
                     observed=now, outcome='complete', cwd=str(self.home), answer_sha256=core.answer_digest('Done.'))
        core.strict_audit(value, 'run', now-1, 'session', 'Done.', self.home)
        for change in ({}, {'observed': now-10}, {'run_id': 'old'}, {'session_id': 'other'},
                       {'answer_sha256': 'other'}, {'outcome': 'failed'}, {'cwd': '/other'}):
            candidate = dict(value, **change) if change else None
            with self.assertRaises(ValueError):
                core.strict_audit(candidate, 'run', now-1, 'session', 'Done.', self.home)

    def test_chat_and_tracked_question_need_no_review(self):
        with patch.dict(os.environ, {'MRCALL_COMPLETION_REQUIRE_REVIEW': ''}):
            self.assertEqual(core.hook(self.payload), {})
            path = core.private_dir(core.root() / 'state') / (core.identity(self.payload) + '.json')
            core.write(path, {'attempts': 0, 'binding': {'task': 'still-open'}})
            self.assertEqual(core.hook(self.payload), {})
            self.assertFalse((core.root() / 'last-observed.json').exists())
            self.assertFalse(list(core.handoffs().glob('*.request.json')))

    def test_explicit_delivery_is_turn_bound_and_tracking_cannot_clear_it(self):
        with patch.dict(os.environ, {'MRCALL_COMPLETION_REQUIRE_REVIEW': ''}):
            args = ['bind', '--session', 'one', '--turn', 'first', '--repo', str(self.home),
                    '--task', 'open-task', '--context', 'lead']
            self.assertEqual(core.main(args), 0)
            self.assertEqual(core.hook(self.payload), {})
            self.assertEqual(core.main(args + ['--delivery']), 0)
            self.assertEqual(core.main(args), 0)
            self.assertEqual(core.hook(self.payload)['decision'], 'block')
            self.assertEqual(core.hook(dict(self.payload, turn_id='question-next')), {})

    def test_missing_answer_admission_precedes_validation(self):
        variants = [{}, {'last_assistant_message': None},
                    {'last_assistant_message': []}, {'last_assistant_message': ''}]
        base = {k: v for k, v in self.payload.items() if k != 'last_assistant_message'}
        with patch.dict(os.environ, {'MRCALL_COMPLETION_REQUIRE_REVIEW': ''}):
            path = core.private_dir(core.root() / 'state') / (core.identity(base) + '.json')
            tracked = {'attempts': 0, 'binding': {'task': 'still-open'}}
            for state in (None, tracked):
                if state is not None:
                    core.write(path, state)
                for variant in variants:
                    for _ in range(2):
                        self.assertEqual(core.hook(dict(base, **variant)), {})
                if state is None:
                    self.assertFalse(path.exists())
                else:
                    self.assertEqual(core.read(path), tracked)
            self.assertFalse((core.root() / 'last-observed.json').exists())
            self.assertFalse(list(core.handoffs().glob('*.request.json')))
            core.hook(dict(base, hook_event_name='UserPromptSubmit', prompt='$nr question'))
            self.assertEqual(core.hook(base), {})
            self.assertFalse((core.root() / 'last-observed.json').exists())
            self.assertEqual(core.read(path)['attempts'], 0)

    def test_armed_missing_answer_still_refuses(self):
        base = {k: v for k, v in self.payload.items() if k != 'last_assistant_message'}
        for variant in ({}, {'last_assistant_message': None}, {'last_assistant_message': []}):
            with self.assertRaisesRegex(ValueError, 'missing final answer'):
                core.hook(dict(base, **variant))
        with patch.dict(os.environ, {'MRCALL_COMPLETION_REQUIRE_REVIEW': ''}):
            core.main(['bind', '--session', 'one', '--turn', 'first', '--repo', str(self.home),
                       '--task', 'open-task', '--context', 'lead', '--delivery'])
            with self.assertRaisesRegex(ValueError, 'missing final answer'):
                core.hook(base)
        self.assertEqual(core.hook(dict(base, last_assistant_message=''))['decision'], 'block')

    def test_session_end_cleans_only_own_pending_state(self):
        request = self.challenge()
        other_request = self.challenge(dict(self.payload, session_id='other'))
        core.hook({'hook_event_name': 'SessionEnd', 'session_id': 'one'})
        self.assertFalse(request.exists())
        self.assertTrue(other_request.exists())

    def test_real_bound_harness_gate_refuses_then_passes_and_refuses_drift(self):
        helper_spec = importlib.util.spec_from_file_location('evidence_fixture', ROOT / 'shared/scripts/tests/test_doc_evidence.py')
        helper = importlib.util.module_from_spec(helper_spec)
        helper_spec.loader.exec_module(helper)
        fixture = helper.CompletionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        installed = self.home / '.config/mrcall-ai-kit'
        installed.mkdir(parents=True)
        for name in ('doc-check.py', 'doc-evidence.py'):
            (installed / name).symlink_to(ROOT / 'shared/scripts' / name)
        fixture.initialize('fastpath')
        binding = {'repo': str(fixture.root), 'task': fixture.task, 'context': fixture.context}
        with self.assertRaisesRegex(ValueError, 'bound completion gate refused'):
            core.gate(binding)
        fixture.lead_closure(impact=False)
        fixture.call('focused', {'argv': ['python3', 'src/tool.py']})
        self.assertTrue(core.gate(binding)['passed'])
        (fixture.root / 'src/tool.py').write_text("print('changed after review')\n")
        with self.assertRaisesRegex(ValueError, 'bound completion gate refused'):
            core.gate(binding)

    def test_copy_symlink_registration_uninstall_preserve_foreign(self):
        # Installer executes with the isolated HOME/CODEX_HOME; no real profile.
        for mode in ('copy', 'symlink'):
            with self.subTest(mode=mode):
                registry = self.home / '.codex/hooks.json'
                registry.parent.mkdir(exist_ok=True)
                foreign = {'hooks': {'PreToolUse': [{'hooks': [{'type': 'command', 'command': 'echo foreign'}]}]}, 'operator': 'keep'}
                registry.write_text(json.dumps(foreign))
                subprocess.run([str(ROOT / 'install.sh'), '--environment', 'codex', '--features', 'doc-harness',
                                '--mode', mode, '--on-exist', 'overwrite', '--yes'], check=True, capture_output=True)
                script = core.installed_script()
                self.assertTrue(script.is_file())
                status = json.loads(subprocess.check_output(['python3', str(script), 'status']))
                self.assertEqual(set(status['registered_events']), set(core.EVENTS))
                self.assertIn('unknown', status['trust'])
                base = dict(hook_event_name='Stop', session_id='installed',
                            turn_id='no-answer', cwd=str(self.home))
                cli_env = dict(os.environ, MRCALL_COMPLETION_REQUIRE_REVIEW='')
                for variant in ({}, {'last_assistant_message': None},
                                {'last_assistant_message': []}, {'last_assistant_message': ''}):
                    response = subprocess.check_output(['python3', str(script), 'hook'],
                                                       input=json.dumps(dict(base, **variant)).encode(), env=cli_env)
                    self.assertEqual(json.loads(response), {})
                strict = subprocess.check_output(['python3', str(script), 'hook'],
                                                 input=json.dumps(base).encode())
                self.assertFalse(json.loads(strict)['continue'])
                self.assertIn('missing final answer', json.loads(strict)['stopReason'])
                before = registry.read_bytes()
                subprocess.run([str(ROOT / 'uninstall.sh'), '--yes', '--dry-run'], check=True, capture_output=True)
                self.assertEqual(registry.read_bytes(), before)
                subprocess.run([str(ROOT / 'uninstall.sh'), '--yes'], check=True, capture_output=True)
                self.assertEqual(json.loads(registry.read_text()), foreign)
                self.assertFalse(script.exists())


if __name__ == '__main__':
    unittest.main()
