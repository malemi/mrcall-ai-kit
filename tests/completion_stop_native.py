#!/usr/bin/env python3
"""Observe real Codex Stop events using a deterministic loopback provider."""
import argparse
import gzip
import http.server
import json
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import sys
import threading
import time


HOOK = '''import json,sys
from pathlib import Path
p=json.load(sys.stdin)
f=Path(__file__).with_name('hook-events.jsonl')
with f.open('a') as h: h.write(json.dumps(p)+'\\n')
n=sum(1 for line in f.read_text().splitlines() if json.loads(line).get('hook_event_name')=='Stop')
if p.get('hook_event_name')=='Stop':
 if n<=2: print(json.dumps({'decision':'block','reason':'FIXTURE_COMPLETION_REQUIRED: The required completion check has not been performed. Continue and perform it.'}))
 else: print(json.dumps({'continue':False,'stopReason':'FIXTURE_RETRY_CAP: required check missing','systemMessage':'FIXTURE_RETRY_CAP: required check missing; this is not successful completion.'}))
'''


def serve(directory, responder=None):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            if self.headers.get('Content-Encoding') == 'gzip':
                body = gzip.decompress(body)
            request = json.loads(body)
            with (directory / 'requests.jsonl').open('a') as handle:
                handle.write(json.dumps({'path': self.path, 'body': request}) + '\n')
            count = sum(1 for _ in (directory / 'requests.jsonl').open())
            item = {'id': f'msg_{count}', 'type': 'message', 'role': 'assistant',
                    'status': 'completed', 'content': [{'type': 'output_text',
                    'text': f'FINAL_WITHOUT_CHECK_{count}', 'annotations': []}]}
            if responder is not None:
                item = responder(request, count)
            response = {'id': f'resp_{count}', 'object': 'response', 'created_at': int(time.time()),
                        'status': 'completed', 'model': 'offline-fixture', 'output': [item],
                        'usage': {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0}}
            events = [
                ('response.created', {'response': dict(response, status='in_progress', output=[])}),
                ('response.output_item.added', {'output_index': 0, 'item': dict(item, status='in_progress', content=[])}),
                ('response.content_part.added', {'item_id': item['id'], 'output_index': 0, 'content_index': 0,
                                                'part': {'type': 'output_text', 'text': '', 'annotations': []}}),
                ('response.output_text.delta', {'item_id': item['id'], 'output_index': 0, 'content_index': 0,
                                               'delta': item['content'][0]['text']}),
                ('response.output_text.done', {'item_id': item['id'], 'output_index': 0, 'content_index': 0,
                                              'text': item['content'][0]['text']}),
                ('response.content_part.done', {'item_id': item['id'], 'output_index': 0, 'content_index': 0,
                                               'part': item['content'][0]}),
                ('response.output_item.done', {'output_index': 0, 'item': item}),
                ('response.completed', {'response': response}),
            ] if item['type'] == 'message' else []
            if item['type'] == 'function_call':
                events = [
                    ('response.created', {'response': dict(response, status='in_progress', output=[])}),
                    ('response.output_item.added', {'output_index': 0, 'item': dict(item, status='in_progress')}),
                    ('response.function_call_arguments.done', {'item_id': item['id'], 'output_index': 0, 'arguments': item['arguments']}),
                    ('response.output_item.done', {'output_index': 0, 'item': item}),
                    ('response.completed', {'response': response}),
                ]
            data = ''.join('event: ' + name + '\ndata: ' + json.dumps(dict(type=name, **payload)) + '\n\n'
                           for name, payload in events).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def capture_tui(argv, env, workspace, directory):
    import fcntl
    import termios
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 120, 0, 0))
    process = subprocess.Popen(argv, env=dict(env, TERM='xterm-256color'), cwd=workspace,
                               stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    started = time.monotonic()
    settled = None
    reason = None
    with (directory / 'terminal.log').open('wb') as log:
        while process.poll() is None:
            if select.select([master], [], [], 0.05)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                log.write(chunk)
                log.flush()
                if b'\x1b[6n' in chunk:
                    os.write(master, b'\x1b[1;1R')
            hooks = directory / 'hook-events.jsonl'
            if hooks.exists() and sum(json.loads(line).get('hook_event_name') == 'Stop' for line in hooks.read_text().splitlines()) >= 3:
                settled = settled or time.monotonic()
            if settled and time.monotonic()-settled >= 2:
                reason = 'fixture observation complete after three Stop callbacks'
                break
            if time.monotonic()-started >= 60:
                reason = '60-second native transport cap'
                break
            if log.tell() > 2_000_000:
                reason = '2MB output cap'
                break
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGKILL)
    code = process.wait(timeout=5)
    os.close(master)
    return code, reason


def probe(out, trusted=True, cap_error=False, tui=False):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    attempts = list(out.glob('attempt-*.json'))
    if len(attempts) >= 6:
        raise RuntimeError('initial six-process capability allowance exhausted')
    directory = out / f'case-{len(attempts)+1}'
    directory.mkdir()
    (out / f'attempt-{len(attempts)+1}.json').write_text(json.dumps({'case': directory.name, 'started': time.time(), 'paid': False}))
    home = directory / 'home'
    workspace = directory / 'workspace'
    codex_home = home / '.codex'
    codex_home.mkdir(parents=True)
    workspace.mkdir()
    hook = directory / 'hook.py'
    hook_source = HOOK
    if cap_error:
        hook_source = hook_source.replace("else: print(json.dumps({'continue':False,'stopReason':'FIXTURE_RETRY_CAP: required check missing','systemMessage':'FIXTURE_RETRY_CAP: required check missing; this is not successful completion.'}))",
            "else:\n  print('FIXTURE_RETRY_CAP: required completion check missing; task is not complete.',file=sys.stderr)\n  raise SystemExit(1)")
    hook.write_text(hook_source)
    (codex_home / 'hooks.json').write_text(json.dumps({'hooks': {'Stop': [{'hooks': [
        {'type': 'command', 'command': f'{sys.executable} "{hook}"', 'timeout': 5}]}]}}))
    server = serve(directory)
    (codex_home / 'config.toml').write_text(
        'model = "offline-fixture"\nmodel_provider = "fixture"\napproval_policy = "never"\n'
        '[model_providers.fixture]\nname = "Offline fixture"\n'
        f'base_url = "http://127.0.0.1:{server.server_port}/v1"\nwire_api = "responses"\nrequires_openai_auth = false\n'
        '[features]\napps = false\nmulti_agent = false\nenable_request_compression = false\n')
    if tui:
        with (codex_home / 'config.toml').open('a') as handle:
            handle.write(f'\n[projects.{json.dumps(str(workspace))}]\ntrust_level = "trusted"\n')
    env = dict(os.environ, HOME=str(home), CODEX_HOME=str(codex_home), XDG_CONFIG_HOME=str(home / '.config'))
    for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENROUTER_API_KEY'):
        env.pop(key, None)
    argv = ['codex', 'exec', '--json', '--ephemeral', '--skip-git-repo-check', '--sandbox', 'read-only']
    if trusted:
        argv.append('--dangerously-bypass-hook-trust')
    argv += ['--cd', str(workspace), 'This is an offline native transport fixture. Reply briefly.']
    if tui:
        argv = ['codex', '--no-daemon', '--no-alt-screen', '--sandbox', 'read-only', '--ask-for-approval', 'never']
        if trusted:
            argv.append('--dangerously-bypass-hook-trust')
        argv += ['--cd', str(workspace), 'This is an offline native transport fixture. Reply briefly.']
    (directory / 'invocation.json').write_text(json.dumps({'argv': argv, 'runtime': subprocess.check_output(['codex', '--version'], text=True).strip(),
                                                        'paid': False, 'trusted_fixture_only': trusted}, indent=2))
    started = time.monotonic()
    reason = None
    if tui:
        code, reason = capture_tui(argv, env, workspace, directory)
    else:
      with (directory / 'events.jsonl').open('wb') as stdout, (directory / 'stderr.log').open('wb') as stderr:
        process = subprocess.Popen(argv, env=env, cwd=workspace, stdout=stdout, stderr=stderr, start_new_session=True)
        while process.poll() is None:
            if time.monotonic() - started > 60:
                reason = '60-second native transport cap'
            elif stdout.tell() + stderr.tell() > 2_000_000:
                reason = '2MB output cap'
            if reason:
                os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(0.05)
        code = process.wait(timeout=5)
    server.shutdown()
    hooks = [json.loads(line) for line in (directory / 'hook-events.jsonl').read_text().splitlines()] if (directory / 'hook-events.jsonl').exists() else []
    requests = [json.loads(line) for line in (directory / 'requests.jsonl').read_text().splitlines()] if (directory / 'requests.jsonl').exists() else []
    result = {'exit': code, 'stop_reason': reason, 'elapsed_seconds': round(time.monotonic()-started, 3),
              'hook_events': hooks, 'provider_requests': len(requests), 'paid': False, 'trusted_fixture': trusted, 'cap_error': cap_error, 'tui': tui}
    (directory / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--untrusted', action='store_true')
    parser.add_argument('--cap-error', action='store_true')
    parser.add_argument('--tui', action='store_true')
    args = parser.parse_args()
    sys.exit(probe(args.probe, not args.untrusted, args.cap_error, args.tui))
