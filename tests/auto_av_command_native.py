#!/usr/bin/env python3
"""Free native callback transport fixtures, with no model-semantic claims."""
import argparse
import gzip
import http.server
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stop_fixture', ROOT / 'tests/completion_stop_native.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def selector(request):
    return any('UNTRUSTED_REPORT_JSON:' in text for text in strings(request))


def claude_server(directory, label):
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
            text = label if selector(request) else 'FIXTURE_RESULT'
            message = {'id': 'msg_fixture', 'type': 'message', 'role': 'assistant',
                       'model': request.get('model', 'fixture'), 'content': [],
                       'stop_reason': None, 'stop_sequence': None,
                       'usage': {'input_tokens': 1, 'output_tokens': 0}}
            events = [('message_start', {'type': 'message_start', 'message': message}),
                      ('content_block_start', {'type': 'content_block_start', 'index': 0,
                                               'content_block': {'type': 'text', 'text': ''}}),
                      ('content_block_delta', {'type': 'content_block_delta', 'index': 0,
                                               'delta': {'type': 'text_delta', 'text': text}}),
                      ('content_block_stop', {'type': 'content_block_stop', 'index': 0}),
                      ('message_delta', {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn',
                                         'stop_sequence': None}, 'usage': {'output_tokens': 1}}),
                      ('message_stop', {'type': 'message_stop'})]
            if request.get('stream'):
                data = ''.join('event: ' + event + '\ndata: ' + json.dumps(payload) + '\n\n'
                               for event, payload in events).encode()
                content_type = 'text/event-stream'
            else:
                message.update(content=[{'type': 'text', 'text': text}], stop_reason='end_turn')
                data = json.dumps(message).encode()
                content_type = 'application/json'
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def run_case(out, runtime, label):
    directory = out / (runtime + '-' + label.lower())
    directory.mkdir(parents=True)
    home = directory / 'home'
    workspace = directory / 'workspace'
    workspace.mkdir()
    installed = home / '.config/mrcall-ai-kit/auto-av'
    installed.mkdir(parents=True)
    shutil.copy2(ROOT / 'shared/scripts/auto_av.py', installed / 'auto_av.py')
    for name in ('av.md', 'selector.md'):
        shutil.copy2(ROOT / 'shared/shortcuts' / name, installed / name)
    env = dict(os.environ, HOME=str(home), CODEX_HOME=str(home / '.codex'),
               XDG_CONFIG_HOME=str(home / '.config'), CLAUDE_CONFIG_DIR=str(home / '.claude'),
               MRCALL_KIT_HOME=str(home / '.config/mrcall-ai-kit'))
    for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENROUTER_API_KEY', 'ANTHROPIC_AUTH_TOKEN',
                'CLAUDECODE', 'ANTHROPIC_BASE_URL', 'ANTHROPIC_API_KEY'):
        env.pop(key, None)
    helper = [sys.executable, str(installed / 'auto_av.py')]
    subprocess.run(helper + ['on', '--runtime', runtime], env=env, check=True, capture_output=True)
    canonical = subprocess.check_output(helper + ['prompt'], env=env, text=True).rstrip('\n')
    if runtime == 'codex':
        def responder(request, count):
            text = label if selector(request) else 'FIXTURE_RESULT'
            return {'id': f'msg_{count}', 'type': 'message', 'role': 'assistant', 'status': 'completed',
                    'content': [{'type': 'output_text', 'text': text, 'annotations': []}]}
        server = fixture.serve(directory, responder)
        config = home / '.codex/config.toml'
        config.write_text('model="offline-fixture"\nmodel_provider="fixture"\napproval_policy="never"\n'
                          '[model_providers.fixture]\nname="Fixture"\n'
                          f'base_url="http://127.0.0.1:{server.server_port}/v1"\n'
                          'wire_api="responses"\nrequires_openai_auth=false\n'
                          '[features]\napps=false\nmulti_agent=false\nenable_request_compression=false\n')
        argv = ['codex', 'exec', '--json', '--ephemeral', '--skip-git-repo-check', '--sandbox',
                'read-only', '--dangerously-bypass-hook-trust', '--cd', str(workspace),
                'Offline fixture: report the result briefly.']
    else:
        server = claude_server(directory, label)
        profile = home / '.claude/agents/verify.md'
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text('---\nname: verify\ndescription: Offline fixture\nmodel: claude-sonnet-4-6\n---\nFixture.\n')
        env.update(ANTHROPIC_API_KEY='fake-loopback-only',
                   ANTHROPIC_BASE_URL=f'http://127.0.0.1:{server.server_port}',
                   CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',
                   CLAUDE_CODE_DISABLE_1M_CONTEXT='1')
        argv = ['claude', '--print', '--model', 'claude-sonnet-4-6', '--tools', '',
                '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                '--no-session-persistence', 'Offline fixture: report the result briefly.']
    (directory / 'invocation.json').write_text(json.dumps({'argv': argv, 'paid': False,
        'runtime': subprocess.check_output([runtime, '--version'], env=env, text=True).strip()}, indent=2))
    started = time.monotonic()
    reason = None
    with (directory / 'stdout.log').open('wb') as stdout, (directory / 'stderr.log').open('wb') as stderr:
        process = subprocess.Popen(argv, env=env, cwd=workspace, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        while process.poll() is None:
            if time.monotonic() - started > 60:
                reason = '60-second deadline'
            if stdout.tell() + stderr.tell() > 2_000_000:
                reason = '2MB output cap'
            if reason:
                os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(.05)
        code = process.wait(timeout=5)
    server.shutdown()
    path = directory / 'requests.jsonl'
    requests = [json.loads(line)['body'] for line in path.read_text().splitlines()] if path.exists() else []
    selections = [request for request in requests if selector(request)]
    parents = [request for request in requests if not selector(request)]
    selector_context = all(any('Offline fixture: report the result briefly.' in text
                               for text in strings(request)) for request in selections)
    canonical_count = sum(any(canonical in text for text in strings(request)) for request in parents)
    if runtime == 'codex':
        identities = [request.get('prompt_cache_key') for request in parents]
    else:
        identities = [json.loads(request.get('metadata', {}).get('user_id', '{}')).get('session_id')
                      for request in parents]
    same_parent = bool(identities) and all(identity == identities[0] and identity for identity in identities)
    prior_report_retained = label == 'SKIP' or (len(parents) == 2 and
        any('FIXTURE_RESULT' in text for text in strings(parents[-1])) and
        any('Offline fixture: report the result briefly.' in text for text in strings(parents[-1])))
    result = {'runtime': runtime, 'label': label, 'exit': code, 'stop_reason': reason,
              'parent_requests': len(parents), 'selector_requests': len(selections),
              'selector_tools': [request.get('tools', []) for request in selections],
              'selector_native_assignment_retained': selector_context,
              'canonical_parent_requests': canonical_count, 'parent_session_ids': identities,
              'same_parent_session': same_parent, 'prior_report_and_assignment_retained': prior_report_retained,
              'paid': False,
              'elapsed_seconds': round(time.monotonic() - started, 3)}
    result['passed'] = (code == 0 and reason is None and same_parent and prior_report_retained
                        and len(selections) == 1 and selector_context
                        and all(not request.get('tools') for request in selections)
                        and len(parents) == (2 if label == 'APPLY' else 1)
                        and canonical_count == (1 if label == 'APPLY' else 0))
    (directory / 'result.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)
    return result['passed']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--runtime', choices=('codex', 'claude', 'all'), default='all')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for runtime in ('codex', 'claude') if args.runtime == 'all' else (args.runtime,):
        for label in ('APPLY', 'SKIP'):
            if not run_case(args.out.resolve(), runtime, label):
                return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
