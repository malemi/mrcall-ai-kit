"""Deterministic routing and real CLI checks; no semantic model claims."""
import concurrent.futures
import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'shared/scripts/auto_av.py'
REQUEST = 'Offline fixture assignment: investigate the probe and report findings.'
LONG_REPORT = 'The fixture probe failed; investigate the observed cause and verify the resulting configuration. ' * 4
LOGGING_REPLY = ('È un’indicazione forte: un fallimento del supervisor con reason=unknown è poco diagnostico.\n\n'
                 'Dovrebbe registrare quale controllo fallisce, perché e con quali eventi collegati. '
                 'Così il worker può ricostruire la causa senza doverla indovinare.')
spec = importlib.util.spec_from_file_location('auto_av_under_test', SCRIPT)
av = importlib.util.module_from_spec(spec)
spec.loader.exec_module(av)


class AutoAvTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.env = mock.patch.dict(os.environ, {'HOME': str(self.base), 'CODEX_HOME': str(self.base / '.codex'), 'MRCALL_KIT_HOME': str(self.base / '.config/mrcall-ai-kit')})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.bin = self.base / 'bin'
        self.bin.mkdir()

    def payload(self, event='Stop', session='one', turn='turn-one', answer=LONG_REPORT):
        return {'hook_event_name': event, 'session_id': session, 'turn_id': turn,
                'last_assistant_message': answer, 'prompt': REQUEST}

    def cli(self, *args, payload=None):
        result = subprocess.run([sys.executable, str(SCRIPT), *args],
                                input=json.dumps(payload), capture_output=True, text=True,
                                env=os.environ.copy(), timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def native(self, name, body):
        path = self.bin / name
        path.write_text('#!' + sys.executable + '\n' + body)
        path.chmod(0o700)
        os.environ['PATH'] = str(self.bin) + os.pathsep + os.environ['PATH']

    def test_canonical_stance_is_preserved_exactly(self):
        manual = (ROOT / 'shared/shortcuts/av.md').read_text().split('\n---\n', 1)[1].lstrip()
        prefix, suffix = manual.split('$ARGUMENTS')
        actual = av.av_prompt()
        self.assertTrue(actual.startswith(prefix))
        self.assertTrue(actual.endswith(suffix))
        self.assertNotIn('$ARGUMENTS', actual)
        self.assertIn('WHOLE current assignment', actual)
        self.assertIn('send it unchanged', actual)
        self.assertIn('not a bare invocation', actual)

    def test_installed_assets_are_used_by_real_prompt_cli(self):
        installed = self.base / 'installed'
        installed.mkdir()
        shutil.copy2(SCRIPT, installed / 'auto_av.py')
        for asset in ('av.md', 'selector.md'):
            shutil.copy2(ROOT / 'shared/shortcuts' / asset, installed / asset)
        result = subprocess.run([sys.executable, str(installed / 'auto_av.py'), 'prompt'],
                                capture_output=True, text=True, env=os.environ.copy(), timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, av.av_prompt() + '\n')

    def test_routing_category_fixtures_do_not_replace_semantic_classification(self):
        cases = [('result', '42.', 'APPLY'),
                 ('mixed', 'Hello. The probe failed with exit 2.', 'APPLY'),
                 ('status', 'Still investigating; the endpoint rejects the token.', 'APPLY'),
                 ('analysis', 'The branch cannot execute because its predicate is false.', 'APPLY'),
                 ('acknowledgment', 'Understood.', 'SKIP'),
                 ('greeting', 'Hello!', 'SKIP'),
                 ('clarification', 'Which repository should I use?', 'SKIP'),
                 ('pause', 'Paused.', 'SKIP'),
                 ('stance', 'The engineering-lead stance is restated.', 'SKIP'),
                 ('quoted-only', '> The endpoint failed.', 'SKIP'),
                 ('internal', 'Worker: inspect the assigned file.', 'SKIP')]
        for session, answer, label in cases:
            answer = (answer + '\n') * (301 // (len(answer) + 1) + 1)
            with self.subTest(session=session):
                with mock.patch.object(av, 'selection', return_value=label) as select:
                    result = av.hook(self.payload(session=session, answer=answer), 'codex')
                    self.assertEqual(bool(result), label == 'APPLY')
                    self.assertEqual(select.call_args.args, ('codex', answer))
                    if result:
                        self.assertEqual(result['reason'], av.av_prompt())

    def test_empty_missing_and_null_are_quiet_without_selector(self):
        with mock.patch.object(av, 'selection') as select:
            for answer in (None, '', ' \n', [], {}):
                self.assertEqual(av.hook(self.payload(answer=answer), 'codex'), {})
            select.assert_not_called()

    def test_short_answers_never_select_even_without_turn_context(self):
        self.assertLessEqual(len(LOGGING_REPLY), 300)
        with mock.patch.object(av, 'selection') as select:
            for runtime in ('codex', 'claude'):
                for answer in (LOGGING_REPLY, '42.', 'x' * 300, '🙂' * 300, 'line\n' * 60):
                    for session in ('one', None):
                        payload = self.payload(session=session, turn=None, answer=answer)
                        payload.pop('prompt')
                        self.assertEqual(av.hook(payload, runtime), {})
            select.assert_not_called()

    def test_301_code_points_still_select_in_both_runtimes(self):
        with mock.patch.object(av, 'selection', return_value='APPLY') as select:
            for runtime in ('codex', 'claude'):
                for number, answer in enumerate(('x' * 301, '🙂' * 301, 'a' * 150 + '\n' + 'b' * 150)):
                    payload = self.payload(session=f'{runtime}-{number}', answer=answer)
                    av.hook(dict(payload, hook_event_name='UserPromptSubmit'), runtime)
                    self.assertEqual(av.hook(payload, runtime)['decision'], 'block')
            self.assertEqual(select.call_count, 6)

    def test_operator_short_example_is_quiet_in_actual_hook_cli_without_context(self):
        for runtime in ('codex', 'claude'):
            payload = self.payload(session=None, turn=None, answer=LOGGING_REPLY)
            payload.pop('prompt')
            self.assertEqual(self.cli('hook', '--runtime', runtime, payload=payload), {})

    def test_short_skip_preserves_later_same_turn_application(self):
        with mock.patch.object(av, 'selection', return_value='APPLY') as select:
            for runtime in ('codex', 'claude'):
                payload = self.payload(session=runtime)
                av.hook(dict(payload, hook_event_name='UserPromptSubmit'), runtime)
                self.assertEqual(av.hook(dict(payload, last_assistant_message=LOGGING_REPLY), runtime), {})
                self.assertEqual(av.hook(payload, runtime)['decision'], 'block')
                self.assertEqual(av.hook(dict(payload, last_assistant_message=LOGGING_REPLY), runtime), {})
                self.assertEqual(av.hook(payload, runtime), {})
            self.assertEqual(select.call_count, 2)

    def test_semantic_result_is_authoritative_without_keyword_routing(self):
        with mock.patch.object(av, 'selection', side_effect=['SKIP', 'APPLY']) as select:
            self.assertEqual(av.hook(self.payload(answer='Analysis result complete verified. ' * 10), 'codex'), {})
            result = av.hook(self.payload(answer='Hello. ' * 60), 'codex')
        self.assertEqual(select.call_count, 2)
        self.assertEqual(result, {'decision': 'block', 'reason': av.av_prompt()})
        self.assertNotIn('completion', result)

    def test_repeat_next_turn_cross_session_and_foreign_hook_flag(self):
        with mock.patch.object(av, 'selection', return_value='APPLY') as select:
            payload = self.payload()
            payload['stop_hook_active'] = True
            self.assertEqual(av.hook(payload, 'codex')['decision'], 'block')
            self.assertEqual(av.hook(payload, 'codex'), {})
            self.assertEqual(av.hook(self.payload(answer='Follow-up result.'), 'codex'), {})
            self.assertEqual(av.hook(self.payload(turn='turn-two'), 'codex')['decision'], 'block')
            self.assertEqual(av.hook(self.payload(session='two'), 'codex')['decision'], 'block')
            self.assertEqual(select.call_count, 3)

    def test_skip_replay_is_quiet_but_changed_draft_is_selected(self):
        with mock.patch.object(av, 'selection', return_value='SKIP') as select:
            self.assertEqual(av.hook(self.payload(), 'codex'), {})
            self.assertEqual(av.hook(self.payload(), 'codex'), {})
            self.assertEqual(av.hook(self.payload(answer='Changed. ' + LONG_REPORT), 'codex'), {})
            self.assertEqual(select.call_count, 2)

    def test_claude_requires_observed_user_turn_and_cleans_session(self):
        with self.assertRaisesRegex(ValueError, 'user-turn'):
            av.hook(self.payload(), 'claude')
        with mock.patch.object(av, 'selection', return_value='APPLY') as select:
            self.assertEqual(av.hook(self.payload('UserPromptSubmit'), 'claude'), {})
            self.assertEqual(av.hook(self.payload(), 'claude')['decision'], 'block')
            av.hook(self.payload('UserPromptSubmit'), 'claude')
            self.assertEqual(av.hook(self.payload(), 'claude'), {})
            av.hook(self.payload('UserPromptSubmit', turn='new'), 'claude')
            self.assertEqual(av.hook(self.payload(), 'claude')['decision'], 'block')
            av.hook(self.payload('SessionEnd'), 'claude')
            self.assertEqual(list((av.home() / 'state').glob('*.json')), [])
            self.assertEqual(select.call_count, 2)

    def test_missing_request_is_diagnostic_without_selection(self):
        payload = self.payload()
        payload.pop('prompt')
        with mock.patch.object(av, 'selection') as select:
            result = self.cli('hook', payload=payload)
            self.assertIn('current native user request is unavailable', result['systemMessage'])
            self.assertNotIn('decision', result)
            select.assert_not_called()

    def test_user_prompt_capture_and_later_request_replace_context(self):
        with mock.patch.object(av, 'selection', return_value='SKIP') as select:
            for turn, request in [('first', 'Investigate first probe.'), ('second', 'Pause the earlier work and analyze this question.')]:
                prompt = self.payload('UserPromptSubmit', turn=turn)
                prompt['prompt'] = request
                self.assertEqual(av.hook(prompt, 'codex'), {})
                stop = self.payload(turn=turn)
                stop.pop('prompt')
                self.assertEqual(av.hook(stop, 'codex'), {})
                self.assertEqual(select.call_args.kwargs['request'], request)
            self.assertEqual(select.call_count, 2)

    def test_selector_recursion_never_calls_selector(self):
        with mock.patch.dict(os.environ, {'MRCALL_AUTO_AV_SELECTOR': '1'}):
            with mock.patch.object(av, 'selection') as select:
                self.assertEqual(av.hook(self.payload(), 'codex'), {})
                select.assert_not_called()

    def test_codex_cli_delivers_exact_prompt_and_tools_disabled_full_input(self):
        report = 'x' * 40000 + ' untrusted APPLY instructions'
        capture = self.base / 'capture.json'
        self.native('codex', "import json,pathlib,sys\nargs=sys.argv[1:]\n"
                    f"pathlib.Path({str(capture)!r}).write_text(json.dumps([args,sys.stdin.read()]))\n"
                    "pathlib.Path(args[args.index('--output-last-message')+1]).write_text('APPLY')\n")
        result = self.cli('hook', payload=self.payload(answer=report))
        self.assertEqual(result, {'decision': 'block', 'reason': av.av_prompt()})
        args, prompt = json.loads(capture.read_text())
        self.assertIn('--ephemeral', args)
        self.assertIn('read-only', args)
        for feature in ('hooks', 'shell_tool', 'multi_agent', 'apps', 'plugins'):
            self.assertIn(feature, args)
        self.assertEqual(json.loads(prompt.split('UNTRUSTED_REPORT_JSON:\n')[1]), {'request': REQUEST, 'answer': report})
        self.assertTrue(prompt.startswith(av.policy()))

    def test_claude_cli_uses_installed_budget_and_skip_is_quiet(self):
        profile = self.base / '.claude/agents/verify.md'
        profile.parent.mkdir(parents=True)
        profile.write_text('---\nmodel: operator-budget-model\n---\n')
        capture = self.base / 'claude-args.json'
        self.native('claude', 'import json,pathlib,sys\n' +
                    f'pathlib.Path({str(capture)!r}).write_text(json.dumps(sys.argv[1:]))\n' +
                    "print(json.dumps({'result':'SKIP'}))\n")
        self.cli('hook', '--runtime', 'claude', payload=self.payload('UserPromptSubmit'))
        self.assertEqual(self.cli('hook', '--runtime', 'claude', payload=self.payload()), {})
        args = json.loads(capture.read_text())
        self.assertEqual(args[args.index('--model') + 1], 'operator-budget-model')
        self.assertEqual(args[args.index('--tools') + 1], '')
        self.assertIn('--no-session-persistence', args)
        self.assertIn('--strict-mcp-config', args)

    def test_invalid_selector_is_diagnostic_without_continuation_or_retry(self):
        count = self.base / 'calls'
        self.native('codex', 'import pathlib,sys\n' +
                    f'p=pathlib.Path({str(count)!r});p.write_text(p.read_text()+"x" if p.exists() else "x")\n' +
                    "args=sys.argv;pathlib.Path(args[args.index('--output-last-message')+1]).write_text('APPLY because done')\n")
        result = self.cli('hook', payload=self.payload())
        self.assertEqual(set(result), {'systemMessage'})
        self.assertIn('exactly APPLY or SKIP', result['systemMessage'])
        self.assertEqual(self.cli('hook', payload=self.payload()), {})
        self.assertEqual(count.read_text(), 'x')

    def test_oversized_selector_output_is_refused(self):
        self.native('codex', "import pathlib,sys\na=sys.argv;pathlib.Path(a[a.index('--output-last-message')+1]).write_text('A'*2049)\n")
        result = self.cli('hook', payload=self.payload())
        self.assertIn('oversized', result['systemMessage'])
        self.assertNotIn('decision', result)

    def test_bounded_timeout_kills_child_and_does_not_retry(self):
        count = self.base / 'attempts'
        pid = self.base / 'pid'
        program = f"from pathlib import Path;import os,time;Path({str(count)!r}).write_text('one');Path({str(pid)!r}).write_text(str(os.getpid()));time.sleep(5)"
        started = time.monotonic()
        with self.assertRaisesRegex(ValueError, 'deadline'):
            av.bounded([sys.executable, '-c', program], '', os.environ.copy(), str(self.base), timeout=.75)
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(count.read_text(), 'one')
        self.assertFalse(Path('/proc', pid.read_text()).exists())

    def test_selector_tool_item_is_refused(self):
        event = json.dumps({'type': 'item.started', 'item': {'type': 'command_execution', 'command': 'forbidden'}})
        with self.assertRaisesRegex(ValueError, 'tool item'):
            av.bounded([sys.executable, '-c', f'print({event!r}, flush=True)'], '',
                       os.environ.copy(), str(self.base), timeout=2, native_json=True)

    def test_selector_stdout_is_closed_on_success_timeout_and_early_cancellation(self):
        original = subprocess.Popen
        processes = []
        def launch(*args, **kwargs):
            process = original(*args, **kwargs)
            processes.append(process)
            return process
        def cancelled(process):
            raise InterruptedError('obsolete fixture')
        with mock.patch.object(av.subprocess, 'Popen', side_effect=launch):
            self.assertEqual(av.bounded([sys.executable, '-c', "print('ok')"], '',
                                       os.environ.copy(), str(self.base)), 'ok\n')
            with self.assertRaisesRegex(ValueError, 'deadline'):
                av.bounded([sys.executable, '-c', 'import time;time.sleep(5)'], '',
                           os.environ.copy(), str(self.base), timeout=.2)
            with self.assertRaisesRegex(InterruptedError, 'obsolete'):
                av.bounded([sys.executable, '-c', 'import time;time.sleep(5)'], '',
                           os.environ.copy(), str(self.base), started=cancelled)
        self.assertEqual(len(processes), 3)
        for process in processes:
            self.assertTrue(process.stdout.closed)
            self.assertIsNotNone(process.poll())

    def test_exact_legacy_release_copy_with_stale_symlink_record_becomes_inert(self):
        old = self.base / '.config/mrcall-ai-kit/completion-check/completion_check.py'
        old.parent.mkdir(parents=True)
        historical = subprocess.check_output(['git', '-C', str(ROOT), 'show',
                                              'v9.4.1:shared/scripts/completion_check.py'])
        old.write_bytes(historical)
        manifest = old.parent.parent / 'installed.tsv'
        manifest.write_text('fixture\tsymlink\t' + str(old) + '\t/missing/old-checkout.py\t\t\n')
        audit = old.parent / 'audit.jsonl'
        audit.write_bytes(b'historical audit bytes\n')
        result = self.cli('retire')
        self.assertTrue(result['owned_path_inert'])
        cached = subprocess.run([sys.executable, str(old), 'hook', '--owner', 'mrcall-completion-v1'],
                                input='{}', capture_output=True, text=True, env=os.environ.copy(), timeout=5)
        self.assertEqual(cached.returncode, 0, cached.stderr)
        self.assertEqual(json.loads(cached.stdout), {})
        self.assertEqual(audit.read_bytes(), b'historical audit bytes\n')
        self.assertEqual(manifest.read_text().splitlines()[-1].split('\t')[1], 'copy')

    def test_bounded_transport_overflow_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'transport output'):
            av.bounded([sys.executable, '-c', "print('x'*300000)"], '', os.environ.copy(), str(self.base), timeout=2)

    def registration_snapshot(self):
        return {str(path.relative_to(self.base)): (os.readlink(path) if path.is_symlink() else
                path.read_bytes() if path.is_file() else None)
                for path in self.base.rglob('*')}

    def test_registration_absent_status_dry_runs_and_off_do_not_write(self):
        self.native('opencode', "print('opencode v2.0.32')\n")
        for runtime in ('claude', 'codex', 'opencode'):
            for action, extra in (('status', []), ('on', ['--dry-run']),
                                  ('off', ['--dry-run']), ('off', [])):
                with self.subTest(runtime=runtime, action=action, extra=extra):
                    before = self.registration_snapshot()
                    result = self.cli(action, '--runtime', runtime, *extra)
                    self.assertEqual(self.registration_snapshot(), before)
                    if runtime != 'opencode':
                        self.assertEqual(result['registered_events'], list(av.EVENTS) if action == 'on' else [])
                    else:
                        self.assertEqual(result['registered'], action == 'on')

    def test_registration_foreign_registry_bytes_and_tree_are_preserved(self):
        for runtime, registry in (('claude', self.base / '.claude/settings.json'),
                                  ('codex', self.base / '.codex/hooks.json')):
            registry.parent.mkdir(parents=True, exist_ok=True)
            for body in ('{ "foreign": true }\n',
                         '{"hooks":{"Stop":[{"matcher":"*","hooks":[]}]}, "foreign": 42}\n'):
                registry.write_text(body)
                for action, extra in (('status', []), ('on', ['--dry-run']), ('off', []), ('off', ['--dry-run'])):
                    before = self.registration_snapshot()
                    self.cli(action, '--runtime', runtime, *extra)
                    self.assertEqual(self.registration_snapshot(), before)
                    self.assertEqual(registry.read_text(), body)

    def test_registration_preserves_foreign_hooks_and_is_idempotent(self):
        for runtime, registry in (('codex', self.base / '.codex/hooks.json'),
                                  ('claude', self.base / '.claude/settings.json')):
            registry.parent.mkdir(parents=True, exist_ok=True)
            foreign = {'hooks': {'Stop': [{'matcher': '*', 'hooks': [{'type': 'command', 'command': 'foreign hook'}]}, {'matcher': 'empty', 'hooks': []}, {'matcher': 'metadata-only'}],
                                 'Unrelated': [{'hooks': [{'command': 'keep'}]}]}, 'foreign': {'enabled': True}}
            registry.write_text(json.dumps(foreign))
            before = registry.read_bytes()
            self.cli('on', '--runtime', runtime, '--dry-run')
            self.assertEqual(registry.read_bytes(), before)
            self.cli('on', '--runtime', runtime)
            registered = registry.read_bytes()
            installed_metadata = (registry.stat().st_ino, registry.stat().st_mtime_ns)
            self.cli('on', '--runtime', runtime)
            self.assertEqual(registry.read_bytes(), registered)
            self.assertEqual((registry.stat().st_ino, registry.stat().st_mtime_ns), installed_metadata)
            status = self.cli('status', '--runtime', runtime)
            self.assertEqual(status['registered_events'], list(av.EVENTS))
            self.assertFalse(status['completion_certification'])
            self.cli('off', '--runtime', runtime)
            self.assertEqual(json.loads(registry.read_text()), foreign)

    def test_real_selector_process_is_cancelled_and_reaped_without_stale_av(self):
        pidfile = self.base / 'selector-pid'
        self.native('codex', 'import os,pathlib,time\n' +
                    f'pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()))\n' +
                    'time.sleep(10)\n')
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            stop = pool.submit(av.hook, self.payload(), 'codex')
            deadline = time.monotonic() + 2
            while not pidfile.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(pidfile.exists(), 'selector process did not start')
            self.assertEqual(av.hook(self.payload('SessionEnd'), 'codex'), {})
            self.assertEqual(stop.result(timeout=2), {})
        self.assertFalse(Path('/proc', pidfile.read_text()).exists())

    def test_concurrent_repeated_callbacks_only_select_once(self):
        with mock.patch.object(av, 'selection', return_value='APPLY') as select:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: av.hook(self.payload(), 'codex'), range(2)))
        self.assertEqual(sum(bool(item) for item in results), 1)
        self.assertEqual(select.call_count, 1)

    def stale_selection(self, event, answer=LONG_REPORT, turn='new-turn'):
        entered, release = threading.Event(), threading.Event()
        def pending(*args, **kwargs):
            entered.set()
            if not release.wait(3):
                raise RuntimeError('fixture selector was not released')
            return 'APPLY'
        with mock.patch.object(av, 'selection', side_effect=pending):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                stop = pool.submit(av.hook, self.payload(), 'codex')
                self.assertTrue(entered.wait(1))
                interrupt = pool.submit(av.hook, self.payload(event, turn=turn, answer=answer), 'codex')
                try:
                    self.assertEqual(interrupt.result(timeout=.5), {})
                finally:
                    release.set()
                self.assertEqual(stop.result(timeout=2), {})

    def test_session_end_during_selection_suppresses_stale_continuation(self):
        self.stale_selection('SessionEnd')

    def test_new_user_turn_during_selection_suppresses_stale_continuation(self):
        self.stale_selection('UserPromptSubmit')

    def test_short_draft_during_selection_suppresses_stale_continuation(self):
        for answer in (LOGGING_REPLY, '', ' ', '\n' * 301):
            with self.subTest(answer=answer):
                self.stale_selection('Stop', answer=answer, turn='turn-one')

    def test_short_draft_cancels_real_pending_selector_process(self):
        for number, answer in enumerate((LOGGING_REPLY, '', ' ', '\n' * 301)):
            pidfile = self.base / f'short-selector-pid-{number}'
            self.native('codex', 'import os,pathlib,time\n' +
                        f'pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()))\n' +
                        'time.sleep(10)\n')
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                stop = pool.submit(av.hook, self.payload(), 'codex')
                deadline = time.monotonic() + 2
                while not pidfile.exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(pidfile.exists(), 'selector process did not start')
                self.assertEqual(av.hook(self.payload(answer=answer), 'codex'), {})
                self.assertEqual(stop.result(timeout=2), {})
            self.assertFalse(Path('/proc', pidfile.read_text()).exists())


if __name__ == '__main__':
    unittest.main()
