#!/usr/bin/env python3
"""Bounded, zero-inference acceptance of installed completion hooks in Codex."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time
import tempfile

spec = importlib.util.spec_from_file_location('transport', Path(__file__).with_name('completion_stop_native.py'))
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)
ROOT = Path(__file__).resolve().parents[1]


def run(out, case, scoped=False):
    out.mkdir(parents=True, exist_ok=True)
    require = lambda ok, message: None if ok else (_ for _ in ()).throw(AssertionError(message))
    prefix = 'scope' if scoped else 'M2'
    allowance = 4 if scoped else 7
    attempts = list(out.glob(prefix + '-attempt-*.json'))
    started = list(out.glob(prefix + '-case-*/invocation.json'))
    require(len(started) < allowance, f'{allowance}-process production acceptance allowance exhausted')
    require(len(attempts) < allowance * 2, 'bounded preflight attempt allowance exhausted')
    directory = out / f'{prefix}-case-{len(attempts)+1}-{case}'
    directory.mkdir()
    (out / f'{prefix}-attempt-{len(attempts)+1}.json').write_text(json.dumps({'case': case, 'paid': False, 'started': time.time()}))
    home = directory / 'home'
    codex = home / '.codex'
    codex.mkdir(parents=True)
    workspace = directory / 'workspace'
    workspace.mkdir()
    env = dict(os.environ, HOME=str(home), CODEX_HOME=str(codex), XDG_CONFIG_HOME=str(home / '.config'))
    if case == 'tui-skip':
        # Legacy strict TUI fixture explicitly declares a review-required run.
        env['MRCALL_COMPLETION_REQUIRE_REVIEW'] = '1'
    for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENROUTER_API_KEY'):
        env.pop(key, None)
    subprocess.run([str(ROOT / 'install.sh'), '--environment', 'codex', '--features', 'doc-harness',
                    '--mode', 'copy', '--on-exist', 'overwrite', '--yes'], env=env, check=True,
                   stdout=(directory / 'install.log').open('w'), stderr=subprocess.STDOUT)
    script = home / '.config/mrcall-ai-kit/completion-check/completion_check.py'
    # Independently observe native callbacks; leave every shipped hook intact.
    logger = directory / 'observe.py'
    logger.write_text("import json,sys\nfrom pathlib import Path\np=json.load(sys.stdin)\nwith Path(__file__).with_name('hook-events.jsonl').open('a') as f: f.write(json.dumps(p)+'\\n')\nprint('{}')\n")
    if case == 'bound-skip':
        with logger.open('a') as handle:
            handle.write("import subprocess\nif p['hook_event_name']=='UserPromptSubmit':\n subprocess.run([sys.executable," + repr(str(script)) + ", 'bind', '--delivery', '--session', p['session_id'], '--turn', p['turn_id'], '--repo', p['cwd'], '--task', 'explicit-fixture-delivery', '--context', 'fixture'],check=True,stdout=subprocess.DEVNULL)\n")
    registry = codex / 'hooks.json'
    hooks = json.loads(registry.read_text())
    for event in ('UserPromptSubmit', 'Stop', 'SessionEnd'):
        hooks['hooks'][event].append({'hooks': [{'type': 'command', 'command': shlex.join([sys.executable, str(logger)]), 'timeout': 5}]})
    registry.write_text(json.dumps(hooks))
    final = 'REVIEWED_FINAL'
    calls = []

    def responder(request, count):
        # Fixture reads its own structured request state. Production never
        # selects a task or infers semantic intent from this test machinery.
        states = list((script.parent / 'runtime/state').glob('*.json'))
        challenge = None
        for path in states:
            state = json.loads(path.read_text())
            challenge = state.get('challenge') or challenge
        if case in ('complete', 'limited', 'changed') and challenge:
            nonce = challenge['nonce']
            if nonce not in calls:
                calls.append(nonce)
                review = dict(assignment='Return the deterministic fixture answer.', acceptance=['Answer delivered.'],
                              evidence=[], remaining=[], decision='complete', rationale='Fixture answer is ready.', answer=final)
                if case == 'limited':
                    review.update(decision='limited', remaining=['Operator publication authority.'], stop_condition='authority')
                if case == 'changed' and len(calls) == 1:
                    review['answer'] = 'STALE_DIFFERENT_ANSWER'
                req = Path(tempfile.gettempdir()) / f'mrcall-completion-{os.getuid()}' / (nonce + '.request.json')
                command = shlex.join([sys.executable, str(script), 'review', '--request', str(req)])
                command += " <<'COMPLETION_REVIEW'\n" + json.dumps(review) + '\nCOMPLETION_REVIEW'
                return {'id': f'fc_{count}', 'type': 'function_call', 'call_id': f'call_{count}',
                        'name': 'exec_command', 'arguments': json.dumps({'cmd': command, 'login': False, 'max_output_tokens': 1000}), 'status': 'completed'}
        return {'id': f'msg_{count}', 'type': 'message', 'role': 'assistant', 'status': 'completed',
                'content': [{'type': 'output_text', 'text': final, 'annotations': []}]}

    server = transport.serve(directory, responder=responder)
    (codex / 'config.toml').write_text(
        'model="offline-fixture"\nmodel_provider="fixture"\napproval_policy="never"\n'
        '[model_providers.fixture]\nname="Offline fixture"\n'
        f'base_url="http://127.0.0.1:{server.server_port}/v1"\nwire_api="responses"\nrequires_openai_auth=false\n'
        '[features]\napps=false\nmulti_agent=false\nenable_request_compression=false\n')
    prompt = '$nr Answer the fixture question.' if case == 'nr' else 'Offline fixture; follow the deterministic protocol.'
    args = ['--ephemeral', '--skip-git-repo-check', '--sandbox', 'workspace-write', '--cd', str(workspace)]
    if case != 'untrusted':
        args.append('--dangerously-bypass-hook-trust')
    args.append(prompt)
    argv = [sys.executable, str(script), 'exec', *args]
    if case in ('conversation', 'tui-conversation', 'bound-skip'):
        argv = ['codex', 'exec', '--json', *args]
    tui = case in ('tui-skip', 'tui-conversation')
    if tui:
        with (codex / 'config.toml').open('a') as handle:
            handle.write(f'\n[projects.{json.dumps(str(workspace))}]\ntrust_level="trusted"\n')
        argv = ['codex', '--no-daemon', '--no-alt-screen', '--sandbox', 'workspace-write', '--ask-for-approval', 'never',
                '--dangerously-bypass-hook-trust', '--cd', str(workspace), prompt]
    (directory / 'invocation.json').write_text(json.dumps({'argv': argv, 'paid': False, 'trust_bypass': case != 'untrusted'}, indent=2))
    started = time.monotonic()
    reason = None
    if tui:
        code, reason = transport.capture_tui(argv, env, workspace, directory, stop_count=1 if case == 'tui-conversation' else 3)
    else:
        with (directory / 'events.jsonl').open('w') as stdout, (directory / 'stderr.log').open('w') as stderr:
            process = subprocess.Popen(argv, env=env, cwd=workspace, stdout=stdout, stderr=stderr, start_new_session=True)
            while process.poll() is None:
                if time.monotonic()-started >= 60 or stdout.tell()+stderr.tell() > 2_000_000:
                    reason = 'native acceptance time/output cap'
                    os.killpg(process.pid, signal.SIGKILL)
                    break
                time.sleep(.05)
            code = process.wait(timeout=5)
    server.shutdown()
    observed_path = script.parent / 'runtime/last-observed.json'
    audit = json.loads(observed_path.read_text()) if observed_path.exists() else None
    events_path = directory / 'hook-events.jsonl'
    events = [json.loads(x) for x in events_path.read_text().splitlines()] if events_path.exists() else []
    result = {'case': case, 'exit': code, 'stop_reason': reason, 'paid': False,
              'elapsed': round(time.monotonic()-started, 3), 'audit': audit,
              'events': events, 'submitted_reviews': len(calls)}
    (directory / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({'case': case, 'exit': code, 'outcome': audit and audit['outcome'], 'reviews': len(calls), 'events': [e['hook_event_name'] for e in events]}))
    if scoped:
        verify_scoped_case(directory, result)
        return result
    if case in ('complete', 'limited', 'nr', 'changed'):
        require(code == 0 and audit is not None, 'valid native completion was refused; inspect retained evidence')
        require(audit['outcome'] == ('limited' if case == 'limited' else 'exempt' if case == 'nr' else 'complete'), 'unexpected accepted outcome')
    elif case == 'untrusted':
        require(code == 3 and audit is None and not events, 'missing/untrusted audit was silently accepted')
    elif case == 'skip':
        require(code == 3 and audit['outcome'] == 'failed', 'deliberate bypass silently passed')
        require(len([e for e in events if e['hook_event_name'] == 'Stop']) == 3, 'retry bound differs')
    else:
        require(reason == 'fixture observation complete after three Stop callbacks' and audit['outcome'] == 'failed', 'TUI failure not observed')
    return result


def verify_scoped_case(directory, result):
    import re
    case = result['case']
    stops = [e for e in result['events'] if e['hook_event_name'] == 'Stop']
    assert stops and stops[0]['stop_hook_active'] is False
    if case in ('conversation', 'tui-conversation'):
        assert len(stops) == 1 and result['audit'] is None and result['submitted_reviews'] == 0
        if case == 'conversation':
            assert result['exit'] == 0
            events = [json.loads(x) for x in (directory / 'events.jsonl').read_text().splitlines()]
            finals = [e for e in events if e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'agent_message']
            assert len(finals) == 1 and not any(e.get('item', {}).get('type') == 'command_execution' for e in events)
        else:
            assert result['exit'] == -9 and result['stop_reason'] == 'fixture observation complete after 1 Stop callback'
            terminal = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', (directory / 'terminal.log').read_text(errors='replace'))
            assert 'REVIEWED_FINAL' in terminal and 'Blocked by hook' not in terminal and 'Completion check required' not in terminal
    else:
        assert len(stops) == 3 and all(e['stop_hook_active'] is True for e in stops[1:])
        assert result['audit']['outcome'] == 'failed' and result['submitted_reviews'] == 0
        assert result['exit'] == (3 if case == 'skip' else 0)


def verify_scope(out):
    cases = []
    for directory in sorted(out.glob('scope-case-*')):
        if (directory / 'preflight-failure.json').exists():
            failure = json.loads((directory / 'preflight-failure.json').read_text())
            assert failure['native_started'] is False and not (directory / 'invocation.json').exists()
            continue
        result = json.loads((directory / 'result.json').read_text())
        assert result['paid'] is False
        verify_scoped_case(directory, result)
        cases.append(result['case'])
    assert sorted(cases) == sorted(['conversation', 'tui-conversation', 'skip', 'bound-skip'])
    print(json.dumps({'verified_scoped_native_cases': cases, 'paid_calls': 0}))


def verify(out):
    """Recheck retained actual-client results without starting any client/model."""
    import re
    cases = {}
    for directory in sorted(out.glob('M2-case-*')):
        result = json.loads((directory / 'result.json').read_text())
        case = result['case']
        assert case not in cases, 'duplicate production case'
        assert result['paid'] is False
        stops = [e for e in result['events'] if e['hook_event_name'] == 'Stop']
        if case == 'untrusted':
            assert result['exit'] == 3 and result['audit'] is None and not result['events']
        else:
            assert stops and len({(e['session_id'], e['turn_id']) for e in stops}) == 1
            assert stops[0]['stop_hook_active'] is False
            assert all(e['stop_hook_active'] is True for e in stops[1:])
            audit = result['audit']
            assert audit['session_id'] == stops[-1]['session_id'] and audit['turn_id'] == stops[-1]['turn_id']
            if case in ('skip', 'tui-skip'):
                assert len(stops) == 3 and audit['outcome'] == 'failed'
                if case == 'skip':
                    assert result['exit'] == 3
                else:
                    assert result['exit'] == -9 and result['stop_reason'] == 'fixture observation complete after three Stop callbacks'
                    terminal = (directory / 'terminal.log').read_text(errors='replace')
                    # ANSI is a structured terminal protocol, not task prose.
                    terminal = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', terminal)
                    assert 'Completion check FAILED' in terminal and 'Hook stopped' in terminal
            else:
                assert result['exit'] == 0
                assert audit['outcome'] == ('limited' if case == 'limited' else 'exempt' if case == 'nr' else 'complete')
                assert len(stops) == (1 if case == 'nr' else 3 if case == 'changed' else 2)
                if case != 'nr':
                    events = [json.loads(x) for x in (directory / 'events.jsonl').read_text().splitlines()]
                    commands = [e['item'] for e in events if e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'command_execution']
                    assert len(commands) == (2 if case == 'changed' else 1)
                    assert all(c['exit_code'] == 0 and json.loads(c['aggregated_output'])['submitted'] is True for c in commands)
        cases[case] = result['exit']
    assert set(cases) == {'complete', 'limited', 'skip', 'untrusted', 'nr', 'changed', 'tui-skip'}
    print(json.dumps({'verified_native_cases': cases, 'paid_calls': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--run', type=Path)
    modes.add_argument('--verify', type=Path)
    parser.add_argument('--scoped', action='store_true')
    parser.add_argument('--case', choices=('complete', 'limited', 'skip', 'untrusted', 'nr', 'changed', 'tui-skip', 'conversation', 'tui-conversation', 'bound-skip'))
    args = parser.parse_args()
    if args.verify:
        (verify_scope if args.scoped else verify)(args.verify.resolve())
    else:
        parser.error('--case is required with --run') if args.case is None else None
        run(args.run.resolve(), args.case, scoped=args.scoped)
