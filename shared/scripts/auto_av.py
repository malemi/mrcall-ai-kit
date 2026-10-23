#!/usr/bin/env python3
"""Semantically route analysis/result reports to canonical av in their session.

Routing state is not evidence that an assignment is complete. No answering-agent
review, receipt, task binding or completion certificate is accepted here.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import selectors
import shlex
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import tomllib

LIMIT_SECONDS = 30
LIMIT_OUTPUT = 2048
LIMIT_TRANSPORT = 262144
OWNER = 'mrcall-auto-av-v1'
EVENTS = ('UserPromptSubmit', 'Stop', 'SessionEnd')


def home():
    return Path(os.environ.get('MRCALL_KIT_HOME', str(Path.home() / '.config/mrcall-ai-kit'))) / 'auto-av'


def assets():
    return Path(__file__).resolve().parent


def asset(name):
    installed = Path(__file__).absolute().parent / name
    if installed.is_file():
        return installed.read_text()
    source = assets().parent / 'shortcuts' / name
    return source.read_text()


def av_prompt():
    source = asset('av.md')
    if source.startswith('---\n'):
        source = source.split('\n---\n', 1)[1].lstrip()
    task = (
        'Automatic av application, authorized by the operator for analysis/result reports. '
        'Apply the stance above to the analysis or result you just reported and the WHOLE '
        'current assignment, including earlier requests and later corrections. This is a '
        'concrete task, not a bare invocation: do not merely acknowledge av. If useful '
        'authorized work remains feasible, perform and verify it before concluding. '
        'Preserve question/brief/review-only scope, pauses, cancellation and real authority '
        'or resource limits. If the answer is already adequate, send it unchanged. '
        'Do not announce this pass, invent work or produce a completion certificate.'
    )
    if '$ARGUMENTS' not in source:
        raise ValueError('canonical av source has no task insertion point')
    return source.replace('$ARGUMENTS', task)


def policy():
    return asset('selector.md')


def key(runtime, session):
    return hashlib.sha256((runtime + '\0' + session).encode()).hexdigest()


def private(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    stat = path.lstat()
    if path.is_symlink() or not path.is_dir() or stat.st_uid != os.getuid() or stat.st_mode & 0o077:
        raise ValueError('unsafe auto-av state directory')
    return path


def write(path, data):
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(data, handle)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read(path):
    mode = path.lstat()
    if path.is_symlink() or not path.is_file() or mode.st_uid != os.getuid() or mode.st_mode & 0o077:
        raise ValueError('unsafe auto-av state file')
    return json.loads(path.read_text())


def kill(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()


def process_token(pid):
    # Linux start time distinguishes a live owned process from PID reuse.
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def cancel_pending(state):
    child = state.get('child', {})
    pid = child.get('pid')
    if isinstance(pid, int) and child.get('token') and process_token(pid) == child['token']:
        try:
            if os.getpgid(pid) == pid:
                os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def bounded(argv, prompt, env, cwd, timeout=LIMIT_SECONDS, started=None, native_json=False):
    """One process attempt, interruptible deadline, bounded transport, no retry."""
    # File-backed stdin cannot deadlock while a process has not begun reading.
    with tempfile.TemporaryFile() as stdin, tempfile.TemporaryFile() as stderr:
        stdin.write(prompt.encode())
        stdin.seek(0)
        process = subprocess.Popen(argv, stdin=stdin, stdout=subprocess.PIPE, stderr=stderr,
                                   env=env, cwd=cwd, start_new_session=True)
        old_handlers = {}
        if threading.current_thread() is threading.main_thread():
            def interrupted(signum, frame):
                raise InterruptedError('automatic-av selection cancelled')
            for signum in (signal.SIGTERM, signal.SIGINT):
                old_handlers[signum] = signal.signal(signum, interrupted)
        try:
            if started:
                started(process)
        except BaseException:
            kill(process)
            for signum, handler in old_handlers.items():
                signal.signal(signum, handler)
            raise
        deadline = time.monotonic() + timeout
        output = bytearray()
        pending_lines = bytearray()
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError('semantic selector exceeded 30-second deadline')
                for selected, _ in selector.select(min(remaining, .1)):
                    chunk = os.read(selected.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(selected.fileobj)
                    else:
                        output.extend(chunk)
                        if len(output) > LIMIT_TRANSPORT:
                            raise ValueError('semantic selector transport output exceeded limit')
                        if native_json:
                            pending_lines.extend(chunk)
                            while b'\n' in pending_lines:
                                line, _, rest = pending_lines.partition(b'\n')
                                pending_lines = bytearray(rest)
                                event = json.loads(line)
                                item = event.get('item', {})
                                if event.get('type') in ('item.started', 'item.completed') and item.get('type') not in ('reasoning', 'agent_message', 'error'):
                                    raise ValueError('semantic selector emitted a tool item')
                                if event.get('type') in ('error', 'turn.failed'):
                                    raise ValueError('semantic selector native request failed')
                if stderr.tell() > LIMIT_TRANSPORT:
                    raise ValueError('semantic selector diagnostic output exceeded limit')
            code = process.wait(timeout=max(.01, deadline - time.monotonic()))
            if code:
                raise ValueError(f'semantic selector exited {code}')
            return output.decode()
        finally:
            selector.close()
            kill(process)
            for signum, handler in old_handlers.items():
                signal.signal(signum, handler)


def selection(runtime, answer, *, request='', started=None, model=None):
    env = dict(os.environ, MRCALL_AUTO_AV_SELECTOR='1')
    # Claude refuses accidental nested interactive sessions; this is a dedicated
    # tools-disabled selector, with no access to the parent's conversation store.
    env.pop('CLAUDECODE', None)
    prompt = policy() + '\n\nUNTRUSTED_REPORT_JSON:\n' + json.dumps({'request': request, 'answer': answer}, ensure_ascii=False)
    with tempfile.TemporaryDirectory(prefix='mrcall-av-selector-') as directory:
        if runtime == 'codex':
            result = Path(directory) / 'selection.txt'
            argv = ['codex', 'exec', '--json', '--ephemeral', '--skip-git-repo-check', '--sandbox', 'read-only',
                    '--disable', 'hooks', '--disable', 'shell_tool', '--disable', 'multi_agent',
                    '--disable', 'apps', '--disable', 'plugins', '--disable', 'image_generation',
                    '--disable', 'view_image', '--disable', 'goals',
                    '-c', 'project_doc_max_bytes=0', '-c', 'web_search="disabled"',
                    '-c', 'tools.experimental_request_user_input.enabled=false',
                    '-c', 'tools.update_plan.enabled=false',
                    '--output-last-message', str(result), '-']
            config = Path(env.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml'
            if config.is_file():
                settings = tomllib.loads(config.read_text())
                for name in settings.get('mcp_servers', {}):
                    argv[2:2] = ['-c', 'mcp_servers.' + json.dumps(name) + '.enabled=false']
            if model:
                argv[2:2] = ['--model', model]
            bounded(argv, prompt, env, directory, started=started, native_json=True)
            text = result.read_text() if result.exists() else ''
        else:
            profile = Path.home() / '.claude/agents/verify.md'
            if not profile.is_file():
                raise ValueError('installed Claude verify role is missing; cannot resolve operator model budget')
            lines = profile.read_text().splitlines()
            if not lines or lines[0] != '---':
                raise ValueError('invalid Claude verify profile')
            fields = {}
            for line in lines[1:]:
                if line == '---':
                    break
                name, sep, value = line.partition(':')
                if sep:
                    fields[name] = value.strip().strip('"\'')
            model = fields.get('model')
            if not model:
                raise ValueError('Claude verify role declares no model')
            argv = ['claude', '--print', '--safe-mode', '--tools', '', '--strict-mcp-config',
                    '--mcp-config', '{"mcpServers":{}}', '--no-session-persistence',
                    '--model', model, '--system-prompt', policy(), '--output-format', 'json']
            data = json.loads(bounded(argv, prompt, env, directory, started=started))
            if data.get('is_error'):
                raise ValueError('Claude selector reported a native error')
            text = data.get('result', '')
        if not isinstance(text, str) or len(text.encode()) > LIMIT_OUTPUT:
            raise ValueError('invalid or oversized semantic selector output')
        label = text.strip()
        if label not in ('APPLY', 'SKIP'):
            raise ValueError('semantic selector must return exactly APPLY or SKIP')
        return label


def parent_model(payload):
    transcript = payload.get('transcript_path')
    if not transcript or not Path(transcript).is_file():
        return None
    selected = None
    with Path(transcript).open() as handle:
        for line in handle:
            record = json.loads(line)
            if record.get('type') == 'turn_context':
                context = record.get('payload', {})
                if context.get('turn_id') == payload.get('turn_id'):
                    model = context.get('model')
                    if isinstance(model, str) and model:
                        selected = model
    return selected


@contextlib.contextmanager
def state_lock(runtime, session):
    directory = private(home() / 'state')
    path = directory / (key(runtime, session) + '.json')
    lock = directory / (key(runtime, session) + '.lock')
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield path


def hook(payload, runtime):
    if os.environ.get('MRCALL_AUTO_AV_SELECTOR') == '1':
        return {}
    if not isinstance(payload, dict):
        raise ValueError('hook payload must be an object')
    event = payload.get('hook_event_name')
    if event not in EVENTS:
        return {}
    session = payload.get('session_id')
    if not isinstance(session, str) or not session:
        raise ValueError('missing native session identity')
    with state_lock(runtime, session) as path:
        state = read(path) if path.exists() else {}
        if event == 'SessionEnd':
            cancel_pending(state)
            path.unlink(missing_ok=True)
            return {}
        turn = payload.get('turn_id')
        if event == 'UserPromptSubmit':
            if turn and state.get('turn') == turn:
                return {}
            cancel_pending(state)
            state = {'turn': turn or secrets.token_hex(16), 'applied': False,
                     'request': payload.get('prompt')}
            write(path, state)
            return {}
        answer = payload.get('last_assistant_message')
        if not isinstance(answer, str) or not answer.strip():
            return {}
        if runtime == 'codex':
            if not isinstance(turn, str) or not turn:
                raise ValueError('missing native Codex turn identity')
            if state.get('turn') != turn:
                cancel_pending(state)
                state = {'turn': turn, 'applied': False}
        elif not state.get('turn'):
            raise ValueError('Claude user-turn callback was not observed')
        if state.get('applied'):
            return {}
        request = state.get('request', payload.get('prompt'))
        if not isinstance(request, str) or not request.strip():
            raise ValueError('current native user request is unavailable')
        digest = hashlib.sha256(answer.encode()).hexdigest()
        if state.get('selected_answer') == digest:
            return {}
        if state.get('pending'):
            return {}
        pending = secrets.token_hex(16)
        state['pending'] = pending
        write(path, state)

    def started(process):
        with state_lock(runtime, session) as path:
            current = read(path) if path.exists() else {}
            if current.get('pending') != pending:
                kill(process)
                raise InterruptedError('obsolete automatic-av selection')
            current['child'] = {'pid': process.pid, 'token': process_token(process.pid)}
            write(path, current)

    try:
        label = selection(runtime, answer, request=request, started=started,
                          model=parent_model(payload) if runtime == 'codex' else None)
    except Exception as exc:
        with state_lock(runtime, session) as path:
            current = read(path) if path.exists() else {}
            if current.get('pending') != pending:
                return {}
            current.pop('pending', None)
            current.pop('child', None)
            current['selected_answer'] = digest
            current['unavailable'] = str(exc)
            write(path, current)
        raise
    with state_lock(runtime, session) as path:
        state = read(path) if path.exists() else {}
        if state.get('pending') != pending:
            return {}
        state.pop('pending', None)
        state.pop('child', None)
        state['selected_answer'] = digest
        if label == 'SKIP':
            write(path, state)
            return {}
        instruction = av_prompt()
        state['applied'] = True
        write(path, state)
        return {'decision': 'block', 'reason': instruction}


def registration(runtime, action, dry_run=False):
    if runtime == 'opencode':
        target = home() / 'opencode-v2'
        plugin = Path.home() / '.config/opencode/plugins/mrcall-auto-av'
        owned = plugin.is_symlink() and plugin.resolve() == target.resolve()
        if action == 'status':
            return {'runtime': runtime, 'registered': owned, 'plugin': str(plugin),
                    'completion_certification': False}
        if action == 'off':
            if owned and not dry_run:
                plugin.unlink()
            return {'runtime': runtime, 'registered': False, 'foreign_preserved': not owned}
        version = subprocess.check_output(['opencode', '--version'], text=True).strip()
        # CLI version output is structured input, not a semantic text matcher.
        numbers = version.removeprefix('opencode ').removeprefix('v').split('.')
        if not numbers or numbers[0] != '2':
            return {'runtime': runtime, 'registered': False,
                    'unavailable': 'Automatic av requires the measured OpenCode 2 plugin API; found ' + version}
        if plugin.exists() or plugin.is_symlink():
            if not owned:
                raise ValueError('foreign OpenCode auto-av plugin path is occupied')
        elif not dry_run:
            if not (target / 'index.js').is_file():
                raise ValueError('OpenCode auto-av plugin is missing')
            plugin.parent.mkdir(parents=True, exist_ok=True)
            plugin.symlink_to(target, target_is_directory=True)
        return {'runtime': runtime, 'registered': True, 'plugin': str(plugin)}
    if runtime not in ('claude', 'codex'):
        raise ValueError('OpenCode activation uses its native plugin installer')
    registry = (Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'hooks.json'
                if runtime == 'codex' else Path.home() / '.claude/settings.json')
    if registry.is_symlink():
        raise ValueError('symlinked hook registry refused')
    command = shlex.join([sys.executable, str(home() / 'auto_av.py'), 'hook', '--runtime', runtime])

    def project(data):
        hooks = dict(data.get('hooks', {}))
        changed = False
        registered = []
        for event in EVENTS:
            entries = hooks.get(event, [])
            found = any(h.get('command') == command for entry in entries for h in entry.get('hooks', []))
            if action == 'off' and found:
                kept = []
                for entry in entries:
                    if not any(h.get('command') == command for h in entry.get('hooks', [])):
                        kept.append(entry)
                        continue
                    rest = [h for h in entry.get('hooks', []) if h.get('command') != command]
                    if rest:
                        kept.append(dict(entry, hooks=rest))
                if kept:
                    hooks[event] = kept
                else:
                    hooks.pop(event, None)
                changed = True
            elif action == 'on' and not found:
                hooks[event] = entries + [{'hooks': [{'type': 'command', 'command': command,
                                                    'timeout': 35 if event == 'Stop' else 3}]}]
                found = True
                changed = True
            if found and action != 'off':
                registered.append(event)
        updated = dict(data)
        if changed:
            updated['hooks'] = hooks
        return updated, changed, registered

    data = json.loads(registry.read_text()) if registry.exists() else {}
    updated, changed, registered = project(data)
    if changed and action != 'status' and not dry_run:
        registry.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(registry.with_name('.mrcall-auto-av.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            if registry.is_symlink():
                raise ValueError('symlinked hook registry refused')
            data = json.loads(registry.read_text()) if registry.exists() else {}
            updated, changed, registered = project(data)
            if changed:
                write(registry, updated)
    return {'runtime': runtime, 'registered_events': registered, 'registry': str(registry),
            'native_trust': 'not inferred', 'completion_certification': False}


def retire_legacy(dry_run=False):
    """Remove only the rejected adapter's exact owned Codex registrations."""
    registry = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'hooks.json'
    if registry.is_symlink():
        raise ValueError('symlinked hook registry refused')
    old = str(Path.home() / '.config/mrcall-ai-kit/completion-check/completion_check.py')
    fd = os.open(registry.with_name('.mrcall-auto-av.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600) if registry.exists() else None
    with os.fdopen(fd, 'w') if fd is not None else contextlib.nullcontext() as handle:
        if handle is not None:
            fcntl.flock(handle, fcntl.LOCK_EX)
        data = json.loads(registry.read_text()) if registry.exists() else {}
        for event in EVENTS:
            entries = []
            for entry in data.get('hooks', {}).get(event, []):
                kept = []
                for definition in entry.get('hooks', []):
                    try:
                        argv = shlex.split(definition.get('command', ''))
                    except ValueError:
                        argv = []
                    if not (len(argv) == 5 and argv[1:] == [old, 'hook', '--owner', 'mrcall-completion-v1']):
                        kept.append(definition)
                if kept:
                    entries.append(dict(entry, hooks=kept))
            if entries:
                data['hooks'][event] = entries
            else:
                data.get('hooks', {}).pop(event, None)
        if registry.exists() and not dry_run:
            write(registry, data)
    manifest = Path.home() / '.config/mrcall-ai-kit/installed.tsv'
    recorded = None
    if manifest.is_file():
        for line in manifest.read_text().splitlines():
            fields = line.split('\t')
            if len(fields) >= 4 and fields[2] == old:
                recorded = fields
    obsolete = Path(old)
    owned = False
    if recorded and obsolete.is_symlink():
        owned = recorded[1] == 'symlink' and os.readlink(obsolete) == recorded[3]
    elif recorded and obsolete.is_file() and recorded[1] == 'copy' and len(recorded) > 5 and recorded[5]:
        mode = obsolete.lstat().st_mode
        entries = [['.', stat.S_IFMT(mode), stat.S_IMODE(mode), hashlib.sha256(obsolete.read_bytes()).hexdigest()]]
        actual = hashlib.sha256(json.dumps(entries, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
        owned = actual == recorded[5]
    # A prior release can also be recognized exactly when an intervening copy
    # install changed the file type without updating an older manifest entry.
    if obsolete.is_file() and not obsolete.is_symlink():
        owned = owned or hashlib.sha256(obsolete.read_bytes()).hexdigest() == '7ab614136ae545734e62157b2c95b4332b3813941712597267162b67fe6e22af'
    if owned and not dry_run:
        compatibility = Path(__file__).absolute().parent / 'retired_completion.py'
        if not compatibility.is_file():
            compatibility = assets() / 'completion_check.py'
        body = compatibility.read_bytes()
        if not obsolete.is_file() or obsolete.read_bytes() != body:
            descriptor, temporary = tempfile.mkstemp(dir=obsolete.parent)
            try:
                with os.fdopen(descriptor, 'wb') as target:
                    target.write(body)
                os.chmod(temporary, 0o644)
                os.replace(temporary, obsolete)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            mode = obsolete.stat().st_mode
            entry = [['.', stat.S_IFMT(mode), stat.S_IMODE(mode), hashlib.sha256(body).hexdigest()]]
            content_hash = hashlib.sha256(json.dumps(entry, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            backup = recorded[4] if recorded and len(recorded) > 4 else ''
            with manifest.open('a') as log:
                log.write('\t'.join([timestamp, 'copy', old, str(compatibility), backup, content_hash]) + '\n')
    return {'retired': True, 'owned_path_inert': owned,
            'historical_audits_preserved': True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('hook', 'on', 'off', 'status', 'prompt', 'retire'))
    parser.add_argument('--runtime', choices=('codex', 'claude', 'opencode'), default='codex')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.action == 'prompt':
            print(av_prompt())
            return 0
        if args.action == 'retire':
            result = retire_legacy(args.dry_run)
        elif args.action == 'hook':
            try:
                result = hook(json.load(sys.stdin), args.runtime)
            except Exception as exc:
                # An unavailable selector must neither manufacture an av pass
                # nor interrupt every ordinary answer. This is an availability
                # diagnostic, not a completion claim.
                result = {'systemMessage': 'Automatic av unavailable: ' + str(exc)}
        else:
            result = registration(args.runtime, args.action, args.dry_run)
        print(json.dumps(result))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('automatic-av: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
