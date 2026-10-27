import hashlib
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

try:
    from .store import StoreError
except ImportError:
    from store import StoreError


class Cron:
    def __init__(self, state_dir, cli_path=None, interpreter=None, runner=None):
        self.state_dir = str(Path(state_dir).absolute())
        self.cli_path = str(Path(cli_path or Path(__file__).with_name('cli.py')).absolute())
        self.interpreter = str(Path(interpreter or sys.executable).absolute())
        self.runner = runner or subprocess.run
        self.key = hashlib.sha256(self.state_dir.encode()).hexdigest()[:16]
        self.start = '# mrcall-ai-kit:supervision:' + self.key + ':start'
        self.end = '# mrcall-ai-kit:supervision:' + self.key + ':end'

    def command(self, codex_path=None, claude_path=None, claude_config_dir=None):
        home = str(Path.home().absolute())
        codex_home = str(Path(os.environ.get('CODEX_HOME', Path(home) / '.codex')).absolute())
        path = os.defpath
        if codex_path is None:
            discovered = shutil.which('codex')
            if discovered is not None:
                codex_path = str(Path(discovered).absolute())
        if any(c in home + codex_home + path + self.cli_path + self.state_dir + self.interpreter + (codex_path or '') for c in '\n\r'):
            raise StoreError('cron environment and paths must not contain newlines')
        if not Path(self.interpreter).is_file() or not Path(self.cli_path).is_file():
            raise StoreError('cron requires existing absolute interpreter and CLI')
        args = ['/usr/bin/env', '-i', 'HOME=' + home, 'CODEX_HOME=' + codex_home, 'PATH=' + path, self.interpreter, self.cli_path, '--state-dir', self.state_dir]
        if codex_path:
            if not Path(codex_path).is_absolute():
                raise StoreError('codex-path must be absolute')
            args += ['--codex-path', codex_path]
        if claude_path:
            config = str(Path(claude_config_dir or os.environ.get('CLAUDE_CONFIG_DIR', Path(home) / '.claude')).absolute())
            if not Path(claude_path).is_absolute() or any(c in claude_path + config for c in '\n\r'):
                raise StoreError('Claude executable/config must be absolute paths without newlines')
            args.insert(5, 'CLAUDE_CONFIG_DIR=' + config)
            args += ['--claude-path', claude_path]
        args += ['tick']
        return '* * * * * ' + shlex.join(args).replace('%', '\\%') + ' >/dev/null 2>&1'

    def render(self, existing, enabled, codex_path=None, claude_path=None):
        lines = existing.splitlines(keepends=True)
        kept = []
        inside = False
        found = False
        previous = []
        for line in lines:
            marker = line.rstrip('\r\n')
            if marker == self.start:
                if inside or found:
                    raise StoreError('duplicate or nested owned cron block')
                inside = True
                found = True
            elif marker == self.end:
                if not inside:
                    raise StoreError('malformed owned cron block')
                inside = False
            elif not inside:
                kept.append(line)
            else:
                previous.append(line.rstrip('\r\n'))
        if inside:
            raise StoreError('unterminated owned cron block')
        result = ''.join(kept)
        if enabled:
            config = None
            if previous:
                if len(previous) != 1 or _owned_state(previous[0], self.cli_path, self.key) != self.state_dir:
                    raise StoreError('unrecognized owned cron command; preserve and diagnose')
                tokens = shlex.split(previous[0][len('* * * * * '):].replace('\\%', '%'))
                if codex_path is None and '--codex-path' in tokens:
                    codex_path = tokens[tokens.index('--codex-path') + 1]
                if claude_path is None and '--claude-path' in tokens:
                    claude_path = tokens[tokens.index('--claude-path') + 1]
                    config = next((x.split('=', 1)[1] for x in tokens if x.startswith('CLAUDE_CONFIG_DIR=')), None)
            if result and not result.endswith('\n'):
                result += '\n'
            result += self.start + '\n' + self.command(codex_path, claude_path, config) + '\n' + self.end + '\n'
        return result

    def apply(self, enabled, dry_run=False, codex_path=None, claude_path=None):
        read = self.runner(['crontab', '-l'], text=True, capture_output=True, timeout=10, env={**os.environ, 'LC_ALL': 'C'})
        if read.returncode and not (read.returncode == 1 and 'no crontab for' in read.stderr.lower()):
            raise StoreError('cannot read crontab: ' + read.stderr.strip())
        existing = read.stdout if read.returncode == 0 else ''
        rendered = self.render(existing, enabled, codex_path, claude_path)
        if not dry_run and rendered != existing:
            result = self.runner(['crontab', '-'], input=rendered, text=True, capture_output=True, timeout=10)
            if result.returncode:
                raise StoreError('cannot install crontab: ' + result.stderr.strip())
        return {'enabled': enabled, 'changed': rendered != existing, 'dry_run': dry_run, 'crontab': rendered}


def activate(store, transport, data, cron=None, dry_run=False, codex_path=None, claude_path=None):
    session_ids = [data['session_id'], *data.get('target_ids', [])]
    for session in session_ids:
        metadata = transport.metadata(session)
        if metadata.get('id') != session or metadata.get('canAcceptDirectInput') is not True or metadata.get('parentThreadId'):
            raise StoreError('activation requires exact root sessions accepting direct input: ' + session)
    cron = cron or Cron(store.root)
    paths = {'codex_path': codex_path}
    if data.get('runtime', 'codex') == 'claude' or claude_path is not None:
        executable = claude_path or shutil.which('claude')
        if executable is None:
            raise StoreError('Claude executable unavailable for cron')
        paths['claude_path'] = str(Path(executable).absolute())
    preview = cron.apply(True, dry_run=True, **paths)
    if dry_run:
        return preview
    binding = store.bind(data)
    try:
        installed = cron.apply(True, **paths)
    except Exception:
        store.detach({'id': binding['id'], 'reason': 'cron activation failed'})
        raise
    return {'binding': binding, 'cron': installed}


def deactivate(store, cron=None, dry_run=False):
    cron = cron or Cron(store.root)
    if dry_run:
        return cron.apply(False, dry_run=True)
    for binding in store.status()['bindings']:
        if binding['status'] == 'active':
            store.detach({'id': binding['id'], 'reason': 'supervision deactivated'})
    return cron.apply(False)


def _owned_state(command, cli_path, key):
    if not command.startswith('* * * * * '):
        return None
    try:
        tokens = shlex.split(command[len('* * * * * '):].replace('\\%', '%'))
    except ValueError:
        return None
    if tokens[:2] != ['/usr/bin/env', '-i'] or tokens[-3:] != ['tick', '>/dev/null', '2>&1']:
        return None
    i = 2
    environment = {}
    while i < len(tokens) and '=' in tokens[i] and not tokens[i].startswith('/'):
        name, value = tokens[i].split('=', 1)
        if name not in ('HOME', 'CODEX_HOME', 'PATH', 'CLAUDE_CONFIG_DIR') or name in environment:
            return None
        environment[name] = value
        i += 1
    if not {'HOME', 'CODEX_HOME', 'PATH'}.issubset(environment):
        return None
    if len(tokens) < i + 7 or not Path(tokens[i]).is_absolute() or tokens[i + 1:i + 3] != [cli_path, '--state-dir']:
        return None
    state = tokens[i + 3]
    flags = tokens[i + 4:-3]
    seen = set()
    if len(flags) % 2:
        return None
    for flag, value in zip(flags[::2], flags[1::2]):
        if flag not in ('--codex-path', '--claude-path') or flag in seen or not Path(value).is_absolute():
            return None
        seen.add(flag)
    if not Path(state).is_absolute() or hashlib.sha256(state.encode()).hexdigest()[:16] != key:
        return None
    return state


def deactivate_owned(cli_path=None, runner=None, dry_run=False):
    try:
        from .store import Store
    except ImportError:
        from store import Store
    cli_path = str(Path(cli_path or Path(__file__).with_name('cli.py')).absolute())
    runner = runner or subprocess.run
    try:
        read = runner(['crontab', '-l'], text=True, capture_output=True, timeout=10, env={**os.environ, 'LC_ALL': 'C'})
    except FileNotFoundError:
        return {'state_dirs': [], 'changed': False, 'dry_run': dry_run, 'cron_unavailable': True}
    if read.returncode and not (read.returncode == 1 and 'no crontab for' in read.stderr.lower()):
        raise StoreError('cannot read crontab: ' + read.stderr.strip())
    existing = read.stdout if read.returncode == 0 else ''
    lines = existing.splitlines(keepends=True)
    remove = set()
    states = []
    prefix = '# mrcall-ai-kit:supervision:'
    malformed = []
    for i, line in enumerate(lines):
        marker = line.rstrip('\r\n')
        if not marker.startswith(prefix) or not marker.endswith(':start'):
            continue
        key = marker[len(prefix):-len(':start')]
        valid = len(key) == 16 and all(c in '0123456789abcdef' for c in key)
        end = prefix + key + ':end'
        if not valid or i + 2 >= len(lines) or lines[i + 2].rstrip('\r\n') != end:
            malformed.append(i + 1)
            continue
        state = _owned_state(lines[i + 1].rstrip('\r\n'), cli_path, key)
        if state is not None:
            states.append(state)
            remove.update((i, i + 1, i + 2))
    for index, line in enumerate(lines):
        if index not in remove and cli_path in line and not line.lstrip().startswith('#'):
            raise StoreError('unrecognized cron command references this CLI; preserved all entries; manual reconciliation required at line ' + str(index + 1))
    states = list(dict.fromkeys(states))
    result = {'state_dirs': states, 'changed': bool(remove), 'dry_run': dry_run, 'preserved_malformed_blocks': malformed}
    if dry_run:
        return result
    detached = []
    for state in states:
        if not (Path(state) / 'state.sqlite3').is_file():
            raise StoreError('owned cron state is missing; cron preserved; already detached states=' + repr(detached) + ': ' + state)
        try:
            store = Store(state)
        except Exception as error:
            raise StoreError('cannot open owned state; cron preserved; already detached states=' + repr(detached) + ': ' + str(error)) from error
        try:
            for binding in store.status()['bindings']:
                if binding['status'] == 'active':
                    store.detach({'id': binding['id'], 'reason': 'installed supervision CLI deactivated'})
            detached.append(state)
        except Exception as error:
            raise StoreError('deactivation failed; cron preserved; already detached states=' + repr(detached) + ': ' + str(error)) from error
        finally:
            store.close()
    if remove:
        rendered = ''.join(line for i, line in enumerate(lines) if i not in remove)
        write = runner(['crontab', '-'], input=rendered, text=True, capture_output=True, timeout=10)
        if write.returncode:
            raise StoreError('bindings detached but owned cron removal failed; retain helpers: ' + write.stderr.strip())
    return result
