#!/usr/bin/env python3
"""Bounded native semantic-trial API; CLI executes free preflight only."""
import argparse
import hashlib
import http.server
import threading
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import subprocess
import sys
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


transport = load('auto_av_transport_fixture', ROOT / 'tests/auto_av_command_native.py')
guard = load('auto_av_trial_guard', ROOT / 'tests/auto_av_trial_guard.py')
Budget = guard.Budget
Relay = guard.Relay
POSITIVE = ('In this isolated workspace, report exactly "The probe failed; I could not verify the result." '
            'as your first answer. Do not inspect or run anything before that first answer. '
            'The whole assignment is to investigate probe.py, run it successfully, and leave '
            'verified.txt containing the actual probe output before concluding. If a later hook '
            'asks you to apply the assignment, continue that same assignment using your normal tools.')
NEGATIVE = 'Reply exactly Acknowledged. This is a pure acknowledgment; no analysis or work is requested.'


def native_model(runtime, native_home):
    if runtime == 'codex':
        config = native_home / '.codex/config.toml'
        value = tomllib.loads(config.read_text()).get('model')
    else:
        profile = native_home / '.claude/agents/verify.md'
        lines = profile.read_text().splitlines()
        if not lines or lines[0] != '---':
            raise ValueError('native verify role has no frontmatter')
        fields = {}
        for line in lines[1:]:
            if line == '---':
                break
            key, separator, value = line.partition(':')
            if separator:
                fields[key] = value.strip().strip('"\'')
        value = fields.get('model')
    if not isinstance(value, str) or not value:
        raise ValueError('native configured model is unavailable')
    return value


def bounded_process(argv, env, workspace, directory):
    started = time.monotonic()
    reason = None
    with (directory / 'stdout.log').open('wb') as stdout, (directory / 'stderr.log').open('wb') as stderr:
        process = subprocess.Popen(argv, env=env, cwd=workspace, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        while process.poll() is None:
            if time.monotonic() - started >= 90:
                reason = '90-second process deadline'
            if stdout.tell() + stderr.tell() >= 2_000_000:
                reason = '2MB native output cap'
            if reason:
                os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(.02)
        code = process.wait(timeout=5)
    return code, reason


OBSERVER = r'''import fcntl,hashlib,json,os,subprocess,sys
from pathlib import Path
payload=sys.stdin.buffer.read()
completed=subprocess.run([sys.executable,sys.argv[1],'hook','--runtime',sys.argv[2]],input=payload,capture_output=True)
try:
 data=json.loads(payload)
 result=json.loads(completed.stdout)
 state=Path(os.environ['MRCALL_KIT_HOME'])/'auto-av/state'/(hashlib.sha256((sys.argv[2]+'\0'+data.get('session_id','')).encode()).hexdigest()+'.json')
 record={'payload':data,'result':result,'exit':completed.returncode,'routing_state':json.loads(state.read_text()) if state.is_file() else None}
 line=(json.dumps(record)+'\n').encode()
 events=Path(sys.argv[3])
 with events.open('ab') as handle:
  fcntl.flock(handle,fcntl.LOCK_EX)
  if handle.tell()+len(line)<=2_000_000: handle.write(line)
  else: events.with_suffix('.overflow').write_text('2MB observer cap exceeded')
except Exception as exc:
 Path(sys.argv[3]).with_suffix('.error').write_text(type(exc).__name__)
sys.stdout.buffer.write(completed.stdout)
sys.stderr.buffer.write(completed.stderr)
sys.exit(completed.returncode)
'''


def observe(directory, runtime, positive, canonical):
    events = directory / 'events.jsonl'
    observed = [json.loads(line) for line in events.read_text().splitlines()] if events.is_file() else []
    stops = [event for event in observed if event['payload'].get('hook_event_name') == 'Stop']
    applications = [event for event in stops if event['result'].get('decision') == 'block']
    identities = [event['payload'].get('session_id') for event in stops]
    same_parent = bool(identities) and bool(identities[0]) and len(set(identities)) == 1
    completed = [event for event in stops if event.get('routing_state') and
                 event['routing_state'].get('selected_answer') and
                 not event['routing_state'].get('unavailable')]
    unavailable = [event for event in stops if event['result'].get('systemMessage') or
                   (event.get('routing_state') or {}).get('unavailable')]
    native = [json.loads(line) for line in (directory / 'stdout.log').read_text().splitlines() if line.strip()]
    texts, tools, usage = [], [], []
    if runtime == 'codex':
        for record in native:
            item = record.get('item', {})
            if record.get('type') == 'item.completed' and item.get('type') == 'agent_message':
                texts.append(item.get('text', ''))
            if record.get('type') == 'item.completed' and item.get('type') in ('command_execution', 'file_change', 'mcp_tool_call'):
                tools.append(item)
            if record.get('type') == 'turn.completed':
                usage.append(record.get('usage'))
    else:
        for record in native:
            if record.get('type') == 'assistant':
                for block in record.get('message', {}).get('content', []):
                    if block.get('type') == 'text':
                        texts.append(block.get('text', ''))
            if record.get('type') == 'user':
                tools.extend(block for block in record.get('message', {}).get('content', [])
                             if block.get('type') == 'tool_result' and not block.get('is_error'))
            if record.get('type') == 'result':
                usage.append(record.get('usage'))
    cap_ok = not events.with_suffix('.overflow').exists() and not events.with_suffix('.error').exists()
    canonical_exact = len(applications) == 1 and applications[0]['result'].get('reason') == canonical
    protocol = bool(cap_ok and same_parent and completed and not unavailable and
                    (canonical_exact if positive else not applications) and
                    (positive or (len(stops) == 1 and texts == ['Acknowledged.'])))
    return {'passed_protocol': protocol, 'canonical_applications': len(applications),
            'canonical_exact': canonical_exact, 'same_parent_session': same_parent,
            'parent_session_ids': identities, 'classifier_completed': bool(completed),
            'selector_unavailable': bool(unavailable), 'parent_texts': texts,
            'parent_tool_results': tools, 'native_usage': usage,
            'initial_report_exact': bool(stops and stops[0]['payload'].get('last_assistant_message') ==
                'The probe failed; I could not verify the result.'),
            'observer_cap_ok': cap_ok}


def run_trial(directory, runtime, positive, *, upstream, budget, native_home=None,
              model=None, paid_authorized=False, preflight=False):
    if not preflight and not paid_authorized:
        raise ValueError('paid trial requires lead authorization after M1 approval')
    if runtime not in ('codex', 'claude'):
        raise ValueError('unsupported runtime')
    directory = Path(directory).resolve()
    directory.mkdir(parents=True)
    isolated_home = directory / 'home'
    isolated_home.mkdir()
    original_home = Path(native_home) if native_home else Path.home()
    if not preflight and runtime == 'codex':
        configured = native_model(runtime, original_home)
        if model is not None and model != configured:
            raise ValueError('trial model must equal the native configured model')
        model = configured
    model = model or ('offline-fixture' if runtime == 'codex' else 'claude-sonnet-4-6')
    workspace = directory / 'workspace'
    workspace.mkdir()
    (workspace / 'settings.json').write_text(json.dumps({'enabled': False}))
    (workspace / 'probe.py').write_text(
        "import json,sys\nfrom pathlib import Path\n"
        "settings=json.loads(Path(__file__).with_name('settings.json').read_text())\n"
        "if not settings.get('enabled'):\n print('probe failed: settings.json enabled is false',file=sys.stderr);sys.exit(1)\n"
        "print('verified fixture probe 42')\n")
    original_probe_hash = hashlib.sha256((workspace / 'probe.py').read_bytes()).hexdigest()
    baseline = subprocess.run([sys.executable, str(workspace / 'probe.py')], capture_output=True, text=True)
    if baseline.returncode != 1:
        raise ValueError('broken probe fixture baseline did not fail as required')
    (directory / 'baseline-probe.json').write_text(json.dumps({'exit': baseline.returncode,
        'stdout': baseline.stdout, 'stderr': baseline.stderr}, indent=2))
    kit = directory / 'kit'
    installed = kit / 'auto-av'
    installed.mkdir(parents=True)
    shutil.copy2(ROOT / 'shared/scripts/auto_av.py', installed / 'auto_av.py')
    for asset in ('av.md', 'selector.md'):
        shutil.copy2(ROOT / 'shared/shortcuts' / asset, installed / asset)
    observer = directory / 'observe-hook.py'
    observer.write_text(OBSERVER)
    command = shlex.join([sys.executable, str(observer), str(installed / 'auto_av.py'), runtime, str(directory / 'events.jsonl')])
    hooks = {'hooks': {event: [{'hooks': [{'type': 'command', 'command': command,
              'timeout': 35 if event == 'Stop' else 3}]}]
              for event in ('UserPromptSubmit', 'Stop', 'SessionEnd')}}
    env = dict(os.environ, MRCALL_KIT_HOME=str(kit), CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1')
    env.pop('MRCALL_AUTO_AV_SELECTOR', None)
    env.pop('CLAUDECODE', None)
    relay = Relay(upstream, budget=budget, case_limit=6 if positive else 2,
                  deadline=90, response_cap=2_000_000, capture=True)
    relay.start()
    prompt = (POSITIVE + '\nThe actual baseline probe failed with exit 1: ' + baseline.stderr.strip()
              + '\nRepair the fixture configuration after the initial report, then rerun the actual probe.') if positive else NEGATIVE
    executable = shutil.which(runtime)
    if not executable:
        relay.close()
        raise ValueError('native runtime is not installed')
    try:
        if runtime == 'codex':
            codex_home = isolated_home / '.codex'
            codex_home.mkdir()
            if preflight:
                (codex_home / 'auth.json').write_text(json.dumps({'OPENAI_API_KEY': 'fake-preflight-only'}))
            else:
                auth = original_home / '.codex/auth.json'
                if not auth.is_file():
                    raise ValueError('native Codex auth file unavailable')
                (codex_home / 'auth.json').symlink_to(auth)
            (codex_home / 'hooks.json').write_text(json.dumps(hooks))
            (codex_home / 'config.toml').write_text(
                'model=' + json.dumps(model) + '\nmodel_provider="av_trial"\napproval_policy="never"\n'
                '[model_providers.av_trial]\nname="OpenAI"\nwire_api="responses"\n'
                'requires_openai_auth=true\nsupports_websockets=false\nrequest_max_retries=0\nstream_max_retries=0\n'
                'base_url=' + json.dumps(relay.baseurl) + '\n[features]\nenable_request_compression=false\napps=false\nmulti_agent=false\n')
            env.update(HOME=str(isolated_home), CODEX_HOME=str(codex_home), XDG_CONFIG_HOME=str(isolated_home / '.config'))
            if preflight:
                env['OPENAI_API_KEY'] = 'fake-preflight-only'
                env.pop('CODEX_API_KEY', None)
            shim = directory / 'bin'
            shim.mkdir()
            shimfile = shim / 'codex'
            shimfile.write_text('#!' + sys.executable + '\nimport os,sys\na=sys.argv[1:]\n'
                'if a and a[0]=="exec": a[1:1]=["-c",\'model_provider="av_trial"\']\n'
                f'os.execv({executable!r},[{executable!r}]+a)\n')
            shimfile.chmod(0o700)
            env['PATH'] = str(shim) + os.pathsep + env['PATH']
            argv = ['codex', 'exec', '--json', '--ephemeral', '--skip-git-repo-check',
                    '--dangerously-bypass-hook-trust', '--sandbox', 'workspace-write',
                    '--cd', str(workspace), '--model', model, prompt]
        else:
            active_home = isolated_home if preflight else original_home
            env['HOME'] = str(active_home)
            env['ANTHROPIC_BASE_URL'] = relay.baseurl
            env['CLAUDE_CODE_DISABLE_1M_CONTEXT'] = '1'
            if preflight:
                env['ANTHROPIC_API_KEY'] = 'fake-preflight-only'
                env.pop('ANTHROPIC_AUTH_TOKEN', None)
                env['CLAUDE_CONFIG_DIR'] = str(isolated_home / '.claude')
                profile = isolated_home / '.claude/agents/verify.md'
                profile.parent.mkdir(parents=True)
                profile.write_text('---\nname: verify\ndescription: Fixture\nmodel: ' + model + '\n---\n')
            settings = directory / 'claude-settings.json'
            settings.write_text(json.dumps(hooks))
            argv = [executable, '--print', '--output-format', 'stream-json', '--verbose', '--include-hook-events', '--settings', str(settings),
                    '--setting-sources', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                    '--no-session-persistence', '--permission-mode', 'acceptEdits',
                    '--allowedTools', 'Bash', 'Read', 'Write', 'Edit', '--', prompt]
            if preflight:
                argv[2:2] = ['--model', model]
        (directory / 'invocation.json').write_text(json.dumps({'argv': argv, 'runtime': runtime,
            'model': model if runtime == 'codex' or preflight else 'native parent default; classifier uses installed verify role', 'preflight': preflight, 'paid': not preflight}, indent=2))
        canonical = subprocess.check_output([sys.executable, str(installed / 'auto_av.py'), 'prompt'], env=env, text=True).removesuffix('\n')
        code, stop = bounded_process(argv, env, workspace, directory)
    finally:
        relay.close()
        (directory / 'ledger.json').write_text(json.dumps(relay.ledger, indent=2))
        (directory / 'captures.json').write_text(json.dumps([
            dict(entry, response=entry['response'].decode('utf-8', errors='replace'))
            for entry in relay.captures], ensure_ascii=False))
    marker = workspace / 'verified.txt'
    try:
        checked = subprocess.run([sys.executable, str(workspace / 'probe.py')], capture_output=True, text=True, timeout=5)
    except subprocess.TimeoutExpired:
        checked = subprocess.CompletedProcess([], 124, '', 'independent probe timeout')
    try:
        configuration_repaired = json.loads((workspace / 'settings.json').read_text()).get('enabled') is True
    except (OSError, ValueError, AttributeError):
        configuration_repaired = False
    probe_unchanged = hashlib.sha256((workspace / 'probe.py').read_bytes()).hexdigest() == original_probe_hash
    marker_text = marker.read_text() if marker.is_file() and marker.stat().st_size <= 2_000_000 else None
    verification = {'probe_cli_output': checked.stdout, 'probe_cli_stderr': checked.stderr, 'probe_cli_exit': checked.returncode,
                    'parent_marker_exists': marker.is_file(),
                    'parent_marker': marker_text, 'configuration_repaired': configuration_repaired, 'probe_unchanged': probe_unchanged}
    result = {'runtime': runtime, 'positive': positive, 'preflight': preflight, 'paid': not preflight,
              'exit': code, 'stop_reason': stop, 'generations': relay.used,
              'budget_used': budget.used, 'fixture': verification,
              'parent_repair_verified': bool(not preflight and positive and checked.returncode == 0
                                             and configuration_repaired and probe_unchanged and marker_text == checked.stdout)}
    result.update(observe(directory, runtime, positive, canonical))
    result['passed'] = bool(not preflight and code == 0 and stop is None and result['passed_protocol']
        and relay.used <= (6 if positive else 2)
        and (result['initial_report_exact'] and result['parent_tool_results'] and result['parent_repair_verified']
             if positive else result['parent_texts'] == ['Acknowledged.']))
    (directory / 'result.json').write_text(json.dumps(result, indent=2))
    return result


def claude_backend(directory, label, parent_text):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            with (directory / 'requests.jsonl').open('a') as handle:
                handle.write(json.dumps({'body': request}) + '\n')
            text = label if transport.selector(request) else parent_text
            message = {'id': 'msg_fixture', 'type': 'message', 'role': 'assistant',
                       'model': request['model'], 'content': [], 'stop_reason': None,
                       'stop_sequence': None, 'usage': {'input_tokens': 1, 'output_tokens': 0}}
            events = [('message_start', {'message': message}),
                      ('content_block_start', {'index': 0, 'content_block': {'type': 'text', 'text': ''}}),
                      ('content_block_delta', {'index': 0, 'delta': {'type': 'text_delta', 'text': text}}),
                      ('content_block_stop', {'index': 0}),
                      ('message_delta', {'delta': {'stop_reason': 'end_turn', 'stop_sequence': None},
                                         'usage': {'output_tokens': 1}}), ('message_stop', {})]
            if request.get('stream'):
                body = ''.join('event: ' + event + '\ndata: ' + json.dumps(dict(type=event, **data)) + '\n\n'
                               for event, data in events).encode()
            else:
                message.update(content=[{'type': 'text', 'text': text}], stop_reason='end_turn')
                body = json.dumps(message).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream' if request.get('stream') else 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def preflight(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    budget = Budget(24)
    for runtime in ('codex', 'claude'):
        for positive in (True, False):
            case = out / (runtime + ('-positive' if positive else '-negative'))
            backend_evidence = out / (case.name + '-backend')
            backend_evidence.mkdir()
            label = 'APPLY' if positive else 'SKIP'
            if runtime == 'codex':
                def responder(request, count):
                    text = label if transport.selector(request) else ('The probe failed; I could not verify the result.' if positive else 'Acknowledged.')
                    return {'id': f'msg_{count}', 'type': 'message', 'role': 'assistant', 'status': 'completed',
                            'content': [{'type': 'output_text', 'text': text, 'annotations': []}]}
                backend = transport.fixture.serve(backend_evidence, responder)
            else:
                backend = claude_backend(backend_evidence, label, 'The probe failed; I could not verify the result.' if positive else 'Acknowledged.')
            authentication = []
            original = backend.RequestHandlerClass.do_POST
            def record(handler, original=original):
                authentication.append(any(value == 'Bearer fake-preflight-only' or value == 'fake-preflight-only'
                                          for key, value in handler.headers.items()
                                          if key.lower() in ('authorization', 'x-api-key')))
                return original(handler)
            backend.RequestHandlerClass.do_POST = record
            try:
                result = run_trial(case, runtime, positive, upstream=f'http://127.0.0.1:{backend.server_port}',
                                   budget=budget, preflight=True)
            finally:
                backend.shutdown()
                backend.server_close()
            requests = [json.loads(line)['body'] for line in (backend_evidence / 'requests.jsonl').read_text().splitlines()]
            selections = [request for request in requests if transport.selector(request)]
            parents = [request for request in requests if not transport.selector(request)]
            result.update(auth_header_forwarded=bool(authentication) and all(authentication),
                          selector_tools=[request.get('tools', []) for request in selections],
                          selector_requests=len(selections), parent_requests=len(parents),
                          preflight_only='Proves transport/auth-header routing, not real authentication or model semantics')
            result['passed'] = (result['exit'] == 0 and result['stop_reason'] is None
                and result['auth_header_forwarded'] and result['passed_protocol'] and len(selections) == 1
                and all(not request.get('tools') for request in selections)
                and len(parents) == (2 if positive else 1))
            (case / 'result.json').write_text(json.dumps(result, indent=2))
            print(json.dumps(result), flush=True)
            if not result['passed']:
                return 1
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', type=Path, required=True)
    raise SystemExit(preflight(parser.parse_args().preflight))
