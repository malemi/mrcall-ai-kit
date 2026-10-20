#!/usr/bin/env python3
"""Codex Stop completion reviews, registration and strict exec exit status.

Review contents are model attestations. Native trust and semantic truth are not
established by registration or by a successful receipt validation.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import stat
import subprocess
import sys
import tempfile
import time

EVENTS = ('UserPromptSubmit', 'Stop', 'SessionEnd')
TTL = 600
OWNER = 'mrcall-completion-v1'
LIMITED = {'pause', 'cancel', 'input', 'authority', 'external', 'resource'}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def answer_digest(answer):
    return digest(answer.replace('\r\n', '\n').strip())


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def private_dir(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    mode = path.lstat()
    require(stat.S_ISDIR(mode.st_mode) and mode.st_uid == os.getuid()
            and stat.S_IMODE(mode.st_mode) == 0o700, f'unsafe owned directory: {path}')
    return path


def root():
    return private_dir(Path.home() / '.config/mrcall-ai-kit/completion-check/runtime')


def handoffs():
    return private_dir(Path(tempfile.gettempdir()) / f'mrcall-completion-{os.getuid()}')


def read(path):
    mode = path.lstat()
    require(stat.S_ISREG(mode.st_mode) and mode.st_uid == os.getuid()
            and not mode.st_mode & 0o077 and mode.st_size <= 1_000_000,
            f'unsafe or oversized owned file: {path}')
    with path.open() as handle:
        return json.load(handle)


def write(path, value):
    fd, name = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, ensure_ascii=False)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextlib.contextmanager
def locked():
    path = root() / 'lock'
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def identity(payload):
    require(isinstance(payload, dict), 'hook payload must be an object')
    for name in ('session_id', 'turn_id', 'cwd'):
        require(isinstance(payload.get(name), str) and payload[name], f'missing {name}')
    return digest(payload['session_id'] + '\0' + payload['turn_id'])


def request_path(nonce):
    require(isinstance(nonce, str) and len(nonce) == 64
            and all(c in '0123456789abcdef' for c in nonce), 'invalid request nonce')
    return handoffs() / (nonce + '.request.json')


def validate_review(review):
    require(isinstance(review, dict), 'review must be an object')
    for name in ('assignment', 'answer', 'rationale'):
        require(isinstance(review.get(name), str) and review[name].strip(), f'review requires {name}')
    for name in ('acceptance', 'evidence', 'remaining'):
        require(isinstance(review.get(name), list)
                and all(isinstance(x, str) and x.strip() for x in review[name]), f'invalid {name}')
    require(review['acceptance'], 'review requires acceptance conditions')
    require(review.get('decision') in ('complete', 'continue', 'limited'), 'invalid decision')
    if review['decision'] == 'complete':
        require(not review['remaining'], 'complete review still has remaining obligations')
    elif review['decision'] == 'limited':
        require(review['remaining'] and review.get('stop_condition') in LIMITED,
                'limited review needs remaining obligations and a legitimate stop_condition')
    else:
        require(review['remaining'], 'continue review needs remaining obligations')


def submit(request, review):
    require(request.parent == handoffs() and request.name.endswith('.request.json'), 'foreign request path')
    challenge = read(request)
    require(request == request_path(challenge['nonce']), 'request identity mismatch')
    require(0 <= time.time() - challenge['created'] <= TTL, 'expired request')
    validate_review(review)
    receipt = dict(challenge=challenge, review=review, submitted=time.time())
    write(request.with_suffix('.receipt.json'), receipt)
    return {'submitted': True, 'decision': review['decision'], 'answer_sha256': answer_digest(review['answer'])}


def gate(binding):
    checker = Path.home() / '.config/mrcall-ai-kit/doc-check.py'
    require(checker.is_file(), 'bound completion checker is missing')
    result = subprocess.run([sys.executable, str(checker), '--repo', binding['repo'],
                             '--task', binding['task'], '--context-id', binding['context'],
                             '--completion', 'check', '--json'], capture_output=True, text=True, timeout=20)
    data = json.loads(result.stdout)
    require(result.returncode == 0 and data.get('passed') is True,
            'bound completion gate refused: ' + json.dumps(data.get('reasons', [])))
    return data


def audit(payload, outcome, reason, review=None):
    value = {'schema_version': 1, 'session_id': payload['session_id'], 'turn_id': payload['turn_id'],
             'cwd': str(Path(payload['cwd']).resolve()), 'answer_sha256': answer_digest(payload['last_assistant_message']),
             'outcome': outcome, 'reason': reason, 'review': review, 'observed': time.time(),
             'run_id': os.environ.get('MRCALL_COMPLETION_RUN_ID', '')}
    directory = private_dir(root() / 'audits')
    write(directory / (identity(payload) + '.json'), value)
    if value['run_id']:
        # Hash untrusted environment values; never use them as path components.
        runs = private_dir(root() / 'runs')
        write(runs / (digest(value['run_id']) + '.json'), value)
    write(root() / 'last-observed.json', value)


def fail(reason):
    message = 'Completion check FAILED; assignment is not certified complete: ' + reason
    return {'continue': False, 'stopReason': message, 'systemMessage': message}


def hook(payload):
    require(isinstance(payload, dict), 'hook payload must be an object')
    event = payload.get('hook_event_name')
    if event not in EVENTS:
        return {}
    if event == 'SessionEnd':
        require(isinstance(payload.get('session_id'), str) and payload['session_id'], 'missing session_id')
        # Retain audits for strict exec. Remove only this session's pending
        # challenges; crashed sessions remain bounded by nonce expiry.
        with locked():
            states = private_dir(root() / 'state')
            for path in states.glob('*.json'):
                state = read(path)
                if state.get('session_id') == payload['session_id']:
                    challenge = state.get('challenge')
                    if challenge:
                        request = request_path(challenge['nonce'])
                        request.unlink(missing_ok=True)
                        request.with_suffix('.receipt.json').unlink(missing_ok=True)
                    path.unlink()
        return {}
    key = identity(payload)
    with locked():
        states = private_dir(root() / 'state')
        path = states / (key + '.json')
        state = read(path) if path.exists() else {'attempts': 0}
        if event == 'UserPromptSubmit':
            prompt = payload.get('prompt', '')
            exempt = isinstance(prompt, str) and (prompt == '$nr' or prompt.startswith('$nr ') or prompt.startswith('$nr\n') or prompt.startswith('$nr\t'))
            # Hook continuations must not erase the previous challenge/attempts.
            state['nr'] = exempt or state.get('nr', False)
            state['session_id'] = payload['session_id']
            write(path, state)
            return {}
        require(isinstance(payload.get('last_assistant_message'), str), 'missing final answer')
        if state.get('nr'):
            audit(payload, 'exempt', 'explicit operator $nr')
            return {}
        reason = 'a current whole-assignment review is missing'
        challenge = state.get('challenge')
        if challenge:
            request = request_path(challenge['nonce'])
            receipt_file = request.with_suffix('.receipt.json')
            if receipt_file.exists():
                try:
                    receipt = read(receipt_file)
                    require(receipt['challenge'] == challenge, 'stale or foreign receipt')
                    require(challenge['cwd'] == str(Path(payload['cwd']).resolve())
                            and challenge['run_id'] == os.environ.get('MRCALL_COMPLETION_RUN_ID', ''),
                            'request belongs to another invocation or workspace')
                    require(0 <= time.time() - challenge['created'] <= TTL, 'expired challenge')
                    require(challenge['created'] <= receipt['submitted'] <= time.time(), 'invalid submission time')
                    review = receipt['review']
                    validate_review(review)
                    require(answer_digest(review['answer']) == answer_digest(payload['last_assistant_message']),
                            'the final answer differs from its reviewed answer')
                    require(review['decision'] != 'continue', 'review says useful work remains; continue it')
                    binding = state.get('binding')
                    if binding and review['decision'] == 'complete':
                        gate(binding)
                    audit(payload, review['decision'], review['rationale'], review)
                    receipt_file.unlink()
                    request.unlink(missing_ok=True)
                    state.pop('challenge', None)
                    write(path, state)
                    return {}
                except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as exc:
                    reason = str(exc)
                finally:
                    receipt_file.unlink(missing_ok=True)
            request.unlink(missing_ok=True)
        state['session_id'] = payload['session_id']
        state['attempts'] += 1
        if state['attempts'] >= 3:
            audit(payload, 'failed', reason)
            state.pop('challenge', None)
            write(path, state)
            return fail(reason + '; two automatic continuations exhausted')
        challenge = {'schema_version': 1, 'nonce': secrets.token_hex(32), 'session_id': payload['session_id'],
                     'turn_id': payload['turn_id'], 'cwd': str(Path(payload['cwd']).resolve()), 'created': time.time(),
                     'run_id': os.environ.get('MRCALL_COMPLETION_RUN_ID', '')}
        state['challenge'] = challenge
        write(path, state)
        request = request_path(challenge['nonce'])
        write(request, challenge)
        command = shlex.join([sys.executable, str(Path(__file__).absolute()), 'review', '--request', str(request)])
        instructions = (
            'Completion check required: ' + reason + '. Review the WHOLE open assignment, including earlier '
            'requests and later corrections. If useful authorized work remains feasible within resource limits, '
            'perform and verify it before yielding. A progress question does not cancel that assignment. '
            'Question/brief/review-only tasks retain their requested scope. Do not invent evidence or authority. '
            'Submit your actual review as JSON on stdin to: ' + command + '. Required fields: assignment (string), '
            'acceptance (nonempty string list), evidence (string list of actual result references), remaining '
            '(string list), decision (complete/continue/limited), rationale (string), answer (exact intended final '
            'text). complete requires no remaining obligations. limited requires remaining obligations and '
            'stop_condition (pause/cancel/input/authority/external/resource). Then deliver exactly the reviewed '
            'answer; changes require another review. This checks execution and binding, not semantic truth. '
            'At most two automatic continuations; skipping the review never becomes successful completion.\n'
            'COMPLETION_REQUEST_JSON=' + json.dumps({'request': str(request), 'command': command}))
        return {'decision': 'block', 'reason': instructions}


def installed_script():
    return Path.home() / '.config/mrcall-ai-kit/completion-check/completion_check.py'


def registration(action, dry_run=False):
    home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    registry = home / 'hooks.json'
    require(not registry.is_symlink(), 'hooks registry is symlinked; resolve ownership first')
    command = shlex.join([sys.executable, str(installed_script()), 'hook', '--owner', OWNER])
    # Lock next to hooks.json and merge the latest contents, not a stale copy.
    @contextlib.contextmanager
    def registry_lock():
        if dry_run or action == 'status':
            yield
            return
        home.mkdir(parents=True, exist_ok=True)
        fd = os.open(home / '.mrcall-completion.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield
    with registry_lock():
        data = json.loads(registry.read_text()) if registry.exists() else {}
        require(isinstance(data, dict), 'hooks registry must be an object')
        hooks = data.get('hooks', {})
        require(isinstance(hooks, dict), 'hooks registry hooks must be an object')
        registered = []
        for event in EVENTS:
            entries = hooks.get(event, [])
            require(isinstance(entries, list), f'invalid {event} hooks')
            kept = []
            found = False
            for entry in entries:
                require(isinstance(entry, dict) and isinstance(entry.get('hooks'), list), 'invalid hook entry')
                own = [x for x in entry['hooks'] if isinstance(x, dict) and x.get('command') == command]
                found = found or bool(own)
                if action == 'off' and own:
                    rest = [x for x in entry['hooks'] if x not in own]
                    if rest:
                        kept.append(dict(entry, hooks=rest))
                else:
                    kept.append(entry)
            if action == 'on' and not found:
                kept.append({'hooks': [{'type': 'command', 'command': command, 'timeout': 3 if event == 'SessionEnd' else 30}]})
            if action != 'status':
                if kept:
                    hooks[event] = kept
                else:
                    hooks.pop(event, None)
            if found:
                registered.append(event)
        if action != 'status' and not dry_run:
            data['hooks'] = hooks
            write(registry, data)
        observed_path = Path.home() / '.config/mrcall-ai-kit/completion-check/runtime/last-observed.json'
        observed = read(observed_path) if observed_path.exists() else None
        return {'installed': installed_script().is_file(), 'registered_events': list(EVENTS) if action == 'on' else [] if action == 'off' else registered,
                'trust': 'unknown: approve the current definition in native /hooks; never inferred from registration',
                'observed': observed, 'dry_run': dry_run, 'registry': str(registry)}


def strict_audit(value, run_id, started, session, answer, cwd):
    require(isinstance(value, dict) and value.get('schema_version') == 1, 'malformed terminal audit')
    require(value.get('run_id') == run_id and value.get('session_id') == session and bool(value.get('turn_id')),
            'foreign or mismatched terminal audit')
    require(isinstance(value.get('observed'), (int, float)) and started <= value['observed'] <= time.time(), 'stale terminal audit')
    require(value.get('answer_sha256') == answer_digest(answer) and value.get('cwd') == str(cwd.resolve()), 'terminal audit does not match this result')
    require(value.get('outcome') in ('complete', 'limited', 'exempt'), 'completion check failed')


def exec_checked(args):
    run_id = secrets.token_hex(32)
    started = time.time()
    env = dict(os.environ, MRCALL_COMPLETION_RUN_ID=run_id)
    # JSON is necessary to bind the native session and final result. Never parse
    # assistant prose or internal transcripts to discover the assignment.
    process = subprocess.Popen(['codex', 'exec', '--json', *args], env=env, stdout=subprocess.PIPE, text=True)
    session = ''
    answer = ''
    cwd = Path.cwd()
    for i, arg in enumerate(args):
        if arg in ('--cd', '-C') and i + 1 < len(args):
            cwd = Path(args[i + 1])
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end='', flush=True)
        try:
            event = json.loads(line)
            if event.get('type') == 'thread.started':
                session = event['thread_id']
            item = event.get('item', {})
            if event.get('type') == 'item.completed' and item.get('type') == 'agent_message':
                answer = item['text']
        except (ValueError, KeyError, TypeError):
            pass
    code = process.wait()
    if code:
        return code
    try:
        value = read(root() / 'runs' / (digest(run_id) + '.json'))
        require(session and answer, 'native result identity missing')
        strict_audit(value, run_id, started, session, answer, cwd)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('Completion check FAILED: missing or invalid terminal audit: ' + str(exc), file=sys.stderr)
        return 3
    print(json.dumps({'type': 'completion.result', 'outcome': value['outcome'],
                      'session_id': session, 'turn_id': value['turn_id'],
                      'reason': value['reason'],
                      'remaining': (value.get('review') or {}).get('remaining', [])}), flush=True)
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == 'exec':
        return exec_checked(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('hook', 'review', 'bind', 'on', 'off', 'status'))
    parser.add_argument('--owner', choices=(OWNER,))
    parser.add_argument('--request', type=Path)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--session')
    parser.add_argument('--turn')
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--task')
    parser.add_argument('--context')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.action == 'hook':
            try:
                result = hook(json.load(sys.stdin))
            except Exception as exc:
                result = fail('adapter error: ' + str(exc))
        elif args.action == 'review':
            require(args.request is not None, 'review needs --request')
            review = json.loads(args.input.read_text()) if args.input else json.load(sys.stdin)
            result = submit(args.request.absolute(), review)
        elif args.action == 'bind':
            require(all((args.session, args.turn, args.repo, args.task, args.context)),
                    'bind needs explicit --session --turn --repo --task --context')
            key = identity({'session_id': args.session, 'turn_id': args.turn, 'cwd': str(args.repo)})
            with locked():
                path = private_dir(root() / 'state') / (key + '.json')
                state = read(path) if path.exists() else {'attempts': 0}
                state['binding'] = {'repo': str(args.repo.resolve()), 'task': args.task, 'context': args.context}
                write(path, state)
            result = {'bound': state['binding']}
        else:
            result = registration(args.action, args.dry_run)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('completion-check: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
