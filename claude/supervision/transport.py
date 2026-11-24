import base64
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import struct
import subprocess
import sys
import time
import uuid


PROTOCOL = 1
MEASURED = ('2.1.296', '2.1.323')
SENDER = 'ai-kit-supervisor'
MARKER = 'AI_KIT_SUPERVISION_EVENT '
MARKED = re.compile(re.escape(MARKER) + '([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})')
USAGE = ('total', 'input', 'cached_input', 'output')
# What the registry names as the reason a session waits, as the flags the controller knows.
WAITING = {'permission prompt': 'waitingOnApproval', 'sandbox request': 'waitingOnApproval', 'worker request': 'waitingOnApproval',
           'goal proposal': 'waitingOnApproval', 'input needed': 'waitingOnUserInput', 'dialog open': 'waitingOnUserInput'}
PAGE_BYTES = 20000
CLIP = 3000
WORKERS = 8
STOP = ('Stop the work in progress now. Start no new work and launch no agents. Supervision of this task is parked and the '
        'operator has been asked how to proceed: wait for the operator.')


class DeliveryError(RuntimeError):
    def __init__(self, message, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


class NativeTransport:
    # Claude Code has no call that stops a turn: the stop travels as a message, rendered and recorded like every other.
    interrupt_is_message = True

    def __init__(self, claude_path='claude', timeout=10):
        self.claude_path = shutil.which(claude_path) if not os.path.isabs(claude_path) else claude_path
        self.timeout = float(timeout)
        if not 0 < self.timeout <= 120:
            raise DeliveryError('transport timeout must be in (0, 120]')
        self.config_dir = Path(os.environ.get('CLAUDE_CONFIG_DIR', str(Path.home() / '.claude'))).absolute()

    @staticmethod
    def _identity(value):
        try:
            if str(uuid.UUID(value)) != value:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise DeliveryError('exact canonical session/event UUID required') from None
        return value

    @staticmethod
    def _left(deadline):
        left = deadline - time.monotonic()
        if left <= 0:
            raise DeliveryError('Claude transport technical timeout exceeded')
        return left

    @staticmethod
    def _path(path, kind='file', private=False):
        if not path.is_absolute():
            raise DeliveryError('Claude path must be absolute')
        for component in (path, *path.parents):
            if stat.S_ISLNK(component.lstat().st_mode):
                raise DeliveryError('Claude path contains a symlink: ' + str(component))
        info = path.stat()
        checker = {'file': stat.S_ISREG, 'directory': stat.S_ISDIR, 'socket': stat.S_ISSOCK}[kind]
        if info.st_uid != os.getuid() or not checker(info.st_mode):
            raise DeliveryError('Claude path ownership/type/permissions refused: ' + str(path))
        if private and info.st_mode & 0o077:
            raise DeliveryError('Claude socket or parent is not private: ' + str(path))
        return info

    @staticmethod
    def _proc_start(pid):
        return Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19]

    def _live(self, thread_id, deadline):
        """The registry record of the live root session with this identity, or None when no live session has it."""
        self._identity(thread_id)
        if sys.platform != 'linux':
            raise DeliveryError('Claude supervision supports Linux only')
        if not self.claude_path:
            raise DeliveryError('claude executable unavailable')
        result = subprocess.run([self.claude_path, 'agents', '--json'], capture_output=True,
                                text=True, timeout=self._left(deadline), check=True)
        agents = json.loads(result.stdout)
        if not isinstance(agents, list):
            raise DeliveryError('unsupported Claude agents discovery shape')
        matches = [entry for entry in agents if isinstance(entry, dict) and entry.get('sessionId') == thread_id]
        if not matches:
            return None
        if len(matches) != 1:
            raise DeliveryError('Claude root session is unavailable or ambiguous')
        pid = matches[0].get('pid')
        if type(pid) is not int or pid <= 0:
            raise DeliveryError('Claude registry PID unavailable')
        self._path(self.config_dir, 'directory')
        directory = self.config_dir / 'sessions'
        self._path(directory, 'directory', private=True)
        path = directory / f'{pid}.json'
        self._path(path)
        record = json.loads(path.read_text())
        if (not isinstance(record, dict) or record.get('pid') != pid
                or record.get('sessionId') != thread_id or record.get('cwd') != matches[0].get('cwd')):
            raise DeliveryError('Claude discovery/registry identity mismatch')
        # The peer protocol number is the client's own compatibility signal; every shape read below is checked where it is used.
        if record.get('peerProtocol') != PROTOCOL or not isinstance(record.get('version'), str):
            raise DeliveryError(f'unsupported Claude peer protocol; expected {PROTOCOL}')
        if record.get('procStart') != self._proc_start(pid):
            raise DeliveryError('Claude PID start identity mismatch')
        if not isinstance(record.get('cwd'), str) or not isinstance(record.get('status'), str):
            raise DeliveryError('Claude registry lacks cwd/status')
        self._left(deadline)
        return record

    def _record(self, thread_id, deadline):
        record = self._live(thread_id, deadline)
        if record is None:
            raise DeliveryError('Claude root session is unavailable or ambiguous')
        return record

    @staticmethod
    def _rests(record):
        """No turn runs: `shell` is an idle session whose background command still runs."""
        return record['status'] in ('idle', 'shell')

    @classmethod
    def _meta(cls, record):
        return {'id': record['sessionId'], 'cwd': record['cwd'],
                'status': {'type': 'idle' if cls._rests(record) else 'busy'},
                'native_status': record['status'], 'parentThreadId': None,
                'canAcceptDirectInput': bool(record.get('messagingSocketPath')),
                'cliVersion': record['version'], 'versionMeasured': record['version'] in MEASURED, 'runtime': 'claude'}

    def metadata(self, thread_id):
        try:
            return self._meta(self._record(thread_id, time.monotonic() + self.timeout))
        except DeliveryError:
            raise
        except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as exc:
            raise DeliveryError('Claude discovery failed: ' + str(exc)) from exc

    @staticmethod
    def _envelope(event_id, text):
        escaped = text.replace('<cross-session-message', '&lt;cross-session-message').replace('</cross-session-message', '&lt;/cross-session-message')
        return f'<cross-session-message from-name="{SENDER}">\n{MARKER}{event_id}\n{escaped}\n</cross-session-message>'

    def _token(self, record):
        """The inbox key the session published for its peers, or None. The auth line is optional on Linux."""
        try:
            found = list((self.config_dir / 'sessions').glob(f"{record['pid']}.*.key"))
            if len(found) != 1:
                return None
            self._path(found[0], private=True)
            token = json.loads(found[0].read_text()).get('peerToken')
            return token if isinstance(token, str) and token else None
        except (OSError, ValueError, AttributeError, DeliveryError):
            return None

    def send(self, thread_id, event_id, text, allow_busy=False, priority='next'):
        self._identity(event_id)
        if not isinstance(text, str) or not text.strip():
            raise DeliveryError('nonempty event text required')
        if priority not in ('now', 'next', 'later'):
            raise DeliveryError('priority must be now, next or later')
        writing = False
        try:
            deadline = time.monotonic() + self.timeout
            record = self._record(thread_id, deadline)
            if not allow_busy and not self._rests(record):
                raise DeliveryError('supervisor is busy; event was not submitted')
            if not record.get('messagingSocketPath'):
                raise DeliveryError('Claude root has no live inbox')
            path = Path(record['messagingSocketPath'])
            self._path(path.parent, 'directory', private=True)
            self._path(path, 'socket', private=True)
            # The session drops a frame that names another session, so a recycled socket cannot receive it.
            frame = {'msgV': 1, 'msg_id': event_id, 'type': 'user', 'priority': priority, 'session_id': thread_id,
                     'message': {'role': 'user', 'content': self._envelope(event_id, text)}}
            token = self._token(record)
            lines = ([json.dumps({'type': 'auth', 'token': token})] if token else []) + [json.dumps(frame)]
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(self._left(deadline))
                connection.connect(str(path))
                pid, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if pid != record['pid'] or uid != os.getuid() or self._proc_start(pid) != record['procStart']:
                    raise DeliveryError('Claude connected inbox process identity mismatch')
                connection.settimeout(self._left(deadline))
                writing = True
                connection.sendall(('\n'.join(lines) + '\n').encode())
                connection.shutdown(socket.SHUT_WR)
            return {'status': 'uncertain', 'event_id': event_id, 'native_submission_id': event_id,
                    'thread_id': thread_id, 'assessment_completed': False, 'priority': priority,
                    'reason': 'Native socket has no delivery acknowledgement; reconcile recipient history'}
        except DeliveryError as exc:
            if writing:
                exc.uncertain = True
            raise
        except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as exc:
            raise DeliveryError('Claude inbox submission failed: ' + str(exc), uncertain=writing) from exc

    def interrupt(self, thread_id, turn_id, event_id=None, text=None):
        """A message with priority `now` ends the running turn at its next tool boundary and starts a turn of its own.

        A tool call in flight runs to its end first, and nothing acknowledges the message: the history shows what happened.
        """
        sent = self.send(thread_id, event_id or str(uuid.uuid4()), text or STOP, allow_busy=True, priority='now')
        return {'status': 'interrupted', 'thread_id': thread_id, 'turn_id': turn_id, 'event_id': sent['event_id'], 'acknowledged': False}

    def _root_path(self, thread_id):
        directory = self.config_dir / 'projects'
        self._path(directory, 'directory')
        matches = list(directory.glob(f'*/{thread_id}.jsonl'))
        if len(matches) != 1:
            raise DeliveryError('Claude root history unavailable or ambiguous; absence not established', uncertain=True)
        self._path(matches[0].parent, 'directory')
        return matches[0]

    def _history(self, path, thread_id, deadline):
        info = self._path(path, private=True)
        with path.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            if (info.st_dev, info.st_ino) != (opened.st_dev, opened.st_ino):
                raise DeliveryError('Claude history identity changed while opening')
            data = stream.read()
        self._left(deadline)
        if not data or not data.endswith(b'\n'):
            raise DeliveryError('Claude history empty or partial; absence not established', uncertain=True)
        records = []
        for line in data.splitlines():
            self._left(deadline)
            item = json.loads(line)
            if not isinstance(item, dict):
                raise DeliveryError('Claude history record is not an object')
            if item.get('sessionId', thread_id) != thread_id:
                raise DeliveryError('Claude history session identity mismatch')
            if item.get('type') in ('user', 'assistant') and item.get('sessionId') != thread_id:
                raise DeliveryError('Claude message lacks verified root session identity')
            records.append(item)
        if not any(item.get('sessionId') == thread_id for item in records):
            raise DeliveryError('Claude history has no verified root session identity')
        return data, records, info

    @classmethod
    def _public(cls, value):
        if isinstance(value, dict):
            if value.get('type') in ('thinking', 'redacted_thinking'):
                return None
            return {key: cls._public(item) for key, item in value.items()
                    if key not in ('thinking', 'redacted_thinking')}
        if isinstance(value, list):
            return [cls._public(item) for item in value
                    if not isinstance(item, dict) or item.get('type') not in ('thinking', 'redacted_thinking')]
        return value

    @classmethod
    def _clip(cls, value, limit):
        """Long text keeps its start and its end; what is left out is counted in its place."""
        if isinstance(value, str):
            if len(value) <= limit:
                return value
            half = limit // 2
            return value[:half] + f'\n[session-read left out {len(value) - 2 * half} characters here; the history file holds them]\n' + value[-half:]
        if isinstance(value, dict):
            return {key: cls._clip(item, limit) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._clip(item, limit) for item in value]
        return value

    @classmethod
    def _turn(cls, item, limit=CLIP):
        """One history record as session-read shows it, or None for a record it does not show."""
        if item.get('type') == 'attachment' and isinstance(item.get('attachment'), dict) and item['attachment'].get('type') == 'prompt_snapshot':
            return None
        if item.get('type') not in ('user', 'assistant', 'system', 'progress', 'attachment', 'queue-operation'):
            return None
        public = {key: item[key] for key in ('type', 'message', 'subtype', 'data', 'isSidechain', 'agentId', 'toolUseResult', 'content', 'attachment', 'operation', 'deliveryId') if key in item}
        return {'id': item.get('uuid'), 'status': 'recorded', 'startedAt': item.get('timestamp'),
                'completedAt': None, 'items': [cls._clip(cls._public(public), limit)]}

    def _worker(self, directory, file, thread_id):
        """One subagent of the session as session-read lists it: where its history is, how long, and the last thing it said."""
        entry = {'id': str(file.relative_to(directory))[:-len('.jsonl')], 'parentThreadId': thread_id, 'path': str(file)}
        try:
            info = os.stat(file)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise DeliveryError('ownership or type refused')
            said, count = None, 0
            with open(file, 'rb') as stream:
                for line in stream:
                    try:
                        item = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(item, dict):
                        continue
                    if item.get('sessionId', thread_id) != thread_id:
                        raise DeliveryError('it holds records of another session')
                    count += 1
                    words = self._text((item.get('message') if isinstance(item.get('message'), dict) else {}).get('content'))
                    if item.get('type') == 'assistant' and words.strip():
                        said = {'at': item.get('timestamp'), 'text': self._clip(words, 400)}
            return entry | {'records': count, 'last_said': said}
        except (OSError, DeliveryError) as error:
            # A file that is not this session's own is named and not shown.
            return entry | {'refused': str(error)}

    def _anchor(self, thread_id, identity, data, offset, before=False):
        anchor = {'session': thread_id, 'identity': identity, 'offset': offset, 'digest': hashlib.sha256(data[:offset]).hexdigest()}
        return base64.b64encode(json.dumps(anchor | ({'before': True} if before else {})).encode()).decode()

    def read(self, thread_id, cursor=None, sort_direction='desc'):
        if sort_direction not in ('asc', 'desc'):
            raise DeliveryError('sort_direction must be asc or desc')
        try:
            deadline = time.monotonic() + self.timeout
            record = self._record(thread_id, deadline)
            path = self._root_path(thread_id)
            data, records, info = self._history(path, thread_id, deadline)
            identity = [str(path), info.st_dev, info.st_ino]
            offsets, position = [], 0
            for line in data.splitlines(keepends=True):
                offsets.append(position)
                position += len(line)
            start, stop, older = 0, len(records), cursor is None
            if cursor is not None:
                anchor = json.loads(base64.b64decode(cursor, validate=True))
                offset = anchor['offset']
                if (anchor['session'] != thread_id or anchor['identity'] != identity or type(offset) is not int
                        or offset < 0 or offset > len(data) or offset and data[offset - 1:offset] != b'\n'
                        or anchor['digest'] != hashlib.sha256(data[:offset]).hexdigest()):
                    raise DeliveryError('Claude cursor identity/prefix changed; full reread required')
                index = len(records) if offset == len(data) else offsets.index(offset)
                older = anchor.get('before') is True
                start, stop = (0, index) if older else (index, len(records))
            # One page holds what a reader can take in: the newest records before a point, or the oldest after one.
            page, size, edge = [], 0, stop if older else start
            for index in (range(stop - 1, start - 1, -1) if older else range(start, stop)):
                turn = self._turn(records[index])
                cost = len(json.dumps(turn)) if turn else 0
                if page and size + cost > PAGE_BYTES:
                    break
                edge = index if older else index + 1
                if turn:
                    page.append(turn)
                    size += cost
            if older:
                page.reverse()
            next_cursor = self._anchor(thread_id, identity, data, offsets[edge], before=True) if older and edge > 0 else None
            after = len(data) if older or edge >= len(records) else offsets[edge]
            newer = self._anchor(thread_id, identity, data, offsets[stop] if older and stop < len(records) else after)
            workers, files = [], []
            directory = path.parent / thread_id
            if directory.exists():
                self._path(directory, 'directory')
                directory = directory / 'subagents'
                if directory.exists():
                    self._path(directory, 'directory')
                    files = sorted(directory.rglob('agent-*.jsonl'), key=lambda file: file.stat().st_mtime, reverse=True)
                    workers = [self._worker(directory, worker, thread_id) for worker in files[:WORKERS]]
            return {'thread': self._meta(record) | {'history_path': str(path)},
                    'turns': page if sort_direction == 'asc' else list(reversed(page)),
                    'has_more_newer': not older and edge < len(records), 'has_more_older': next_cursor is not None,
                    'workers': workers, 'workers_omitted': max(0, len(files) - WORKERS), 'workers_are_full_snapshots': False,
                    'next_cursor': next_cursor, 'newer_cursor': newer, 'reverse_cursor': newer,
                    'sort_direction': sort_direction, 'private_reasoning_included': False}
        except DeliveryError:
            raise
        except (OSError, ValueError, KeyError, TypeError, IndexError, subprocess.SubprocessError) as exc:
            raise DeliveryError('Claude history unavailable/corrupt: ' + str(exc), uncertain=True) from exc

    def reconcile(self, thread_id, event_id):
        self._identity(event_id)
        try:
            deadline = time.monotonic() + self.timeout
            self._record(thread_id, deadline)
            _, records, _ = self._history(self._root_path(thread_id), thread_id, deadline)
            marker = f'{MARKER}{event_id}\n'
            for record in records:
                # A message that starts a turn is a user record; one read while a turn runs is a queued-command attachment.
                attachment = record.get('attachment') if record.get('type') == 'attachment' else None
                if isinstance(attachment, dict) and attachment.get('type') == 'queued_command':
                    origin, content, turn = attachment.get('origin'), attachment.get('prompt'), attachment.get('source_uuid') or record.get('uuid')
                elif record.get('type') == 'user' and isinstance(record.get('message'), dict) and record['message'].get('role') == 'user':
                    origin, content, turn = record.get('origin'), record['message'].get('content'), record.get('uuid')
                else:
                    continue
                if not isinstance(origin, dict) or origin.get('kind') != 'peer' or origin.get('msg_id') != event_id:
                    continue
                if marker in self._text(content):
                    return {'status': 'delivered', 'location': 'history', 'event_id': event_id,
                            'native_submission_id': event_id, 'turn_id': turn}
            return {'status': 'absent', 'event_id': event_id, 'absence_is_not_permission_to_resend': True}
        except (DeliveryError, OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as exc:
            raise DeliveryError('Claude reconciliation incomplete: ' + str(exc), uncertain=True) from exc

    # ---- observation: the registry for the live state, the session's own files for everything it recorded ----

    @staticmethod
    def _stamp(value):
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value[:-1] + '+00:00' if value.endswith('Z') else value).timestamp()
        except ValueError:
            return None

    @staticmethod
    def _text(content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return '\n'.join(block.get('text', '') for block in content
                             if isinstance(block, dict) and block.get('type') == 'text' and isinstance(block.get('text'), str))
        return ''

    @staticmethod
    def _close(turn, status):
        evidence = turn.get('evidence')
        return {'id': turn['id'], 'status': evidence[0] if evidence else status, 'started_at': turn.get('started_at'),
                'completed_at': evidence[1] if evidence and evidence[1] is not None else turn.get('last_at')}

    @staticmethod
    def _count(state, item, at, keep):
        """Add one model message's tokens to the cumulative counter; its records repeat the same usage."""
        message = item.get('message') if isinstance(item.get('message'), dict) else {}
        usage = message.get('usage') if isinstance(message.get('usage'), dict) else None
        if usage is None:
            return
        number = lambda key: usage[key] if type(usage.get(key)) is int and usage[key] > 0 else 0
        read = [number('input_tokens'), number('cache_creation_input_tokens'), number('cache_read_input_tokens'), number('output_tokens')]
        ident = message.get('id') if isinstance(message.get('id'), str) else item.get('uuid')
        counted = state['recent'].get(ident) or [0, 0, 0, 0]
        fresh, creation, cached, output = (max(0, new - old) for new, old in zip(read, counted))
        state['recent'].pop(ident, None)
        state['recent'][ident] = [max(new, old) for new, old in zip(read, counted)]
        while len(state['recent']) > keep:
            state['recent'].pop(next(iter(state['recent'])))
        total = state['usage']
        total['input'] += fresh + creation + cached
        total['cached_input'] += cached
        total['output'] += output
        total['total'] += fresh + creation + cached + output
        if at is not None:
            total['at'] = at

    def _scan(self, path, state, light=False):
        """Read what one session file gained since `state`. Returns the new state, the turns that ended and the messages found."""
        info = os.stat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise DeliveryError('Claude history ownership/type refused: ' + str(path))
        grown = (isinstance(state, dict) and state.get('path') == str(path) and state.get('inode') == info.st_ino
                 and isinstance(state.get('offset'), int) and 0 <= state['offset'] <= info.st_size)
        if grown:
            state = json.loads(json.dumps(state))
        else:
            state = {'path': str(path), 'inode': info.st_ino, 'offset': 0, 'usage': dict.fromkeys(USAGE, 0) | {'at': None},
                     'recent': {}, 'turn': None, 'queue': [], 'dequeued': 0, 'created_at': None, 'clock': None}
        with open(path, 'rb') as stream:
            stream.seek(state['offset'])
            data = stream.read()
        end = data.rfind(b'\n')
        lines = data[:end].split(b'\n') if end >= 0 else []
        state['offset'] += end + 1
        ended, messages = [], []
        for line in lines:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if not isinstance(item, dict):
                continue
            at = self._stamp(item.get('timestamp'))
            if at is not None and state['created_at'] is None:
                state['created_at'] = at
            kind = item.get('type')
            # A queued message is recorded when it is read and carries the time it was queued: the file's own clock says when it was read.
            read_at = state.get('clock')
            if at is not None and kind != 'attachment':
                state['clock'] = at if read_at is None else max(read_at, at)
            if kind == 'assistant':
                self._count(state, item, at, 4 if light else 32)
            if light or item.get('isSidechain'):
                continue
            turn = state['turn']
            if kind == 'user':
                origin = item.get('origin') if isinstance(item.get('origin'), dict) else {}
                text = self._text((item.get('message') if isinstance(item.get('message'), dict) else {}).get('content'))
                if origin.get('kind') and not item.get('toolUseResult'):
                    position = item.get('turnPosition') if isinstance(item.get('turnPosition'), dict) else {}
                    index = position.get('turnIndex')
                    # A client that records no turn origin starts a turn at each message that follows an ended one.
                    starts = (turn is None or index is None or index != turn.get('index')) if item.get('turnOrigin') else (turn is None or bool(turn.get('evidence')))
                    if starts:
                        if turn is not None:
                            ended.append(self._close(turn, 'completed'))
                        turn = state['turn'] = {'id': item.get('uuid'), 'index': index, 'started_at': at, 'last_at': at, 'evidence': None}
                    sent = origin.get('msg_id') if origin.get('kind') == 'peer' else None
                    if state.get('dequeued'):
                        own = origin.get('kind') != 'human' and (origin.get('kind') != 'peer' or origin.get('handback') or origin.get('senderTaskId'))
                        self._unqueue(state['queue'], self._digest(text), sent, 'internal' if own else 'prompt' if origin.get('kind') == 'human' else 'peer')
                        state['dequeued'] = 0
                    elif sent:
                        self._unqueue(state['queue'], event=sent)
                    messages.append(self._message(item.get('uuid'), turn, origin, at, text))
                elif turn is not None:
                    turn['last_at'] = at if at is not None else turn['last_at']
                    stopped = bool(item.get('interruptedMessageId')) or text.startswith('[Request interrupted by user')
                    turn['evidence'] = ['interrupted', at] if stopped else None
            elif kind == 'assistant':
                if turn is None:
                    # Model activity outside a known turn, as when a hook makes an ended turn go on.
                    turn = state['turn'] = {'id': item.get('uuid'), 'index': None, 'started_at': at, 'last_at': at, 'evidence': None}
                turn['last_at'] = at if at is not None else turn['last_at']
                reason = (item.get('message') if isinstance(item.get('message'), dict) else {}).get('stop_reason')
                turn['evidence'] = ['completed', at] if reason in ('end_turn', 'stop_sequence') else None
            elif kind == 'system' and item.get('subtype') == 'turn_duration' and turn is not None:
                turn['evidence'] = ['completed', at]
            elif kind == 'attachment':
                attachment = item.get('attachment') if isinstance(item.get('attachment'), dict) else {}
                origin = attachment.get('origin') if isinstance(attachment.get('origin'), dict) else {}
                if attachment.get('type') == 'queued_command' and origin.get('kind'):
                    if turn is not None:
                        turn['last_at'] = at if at is not None else turn['last_at']
                        turn['evidence'] = None
                    if origin.get('kind') == 'peer' and origin.get('msg_id'):
                        self._unqueue(state['queue'], event=origin['msg_id'])
                    queued_at = self._stamp(attachment.get('timestamp')) or at
                    messages.append(self._message(attachment.get('source_uuid') or item.get('uuid'), turn, origin,
                                                  max(filter(None, (queued_at, read_at)), default=None), self._text(attachment.get('prompt'))))
            elif kind == 'queue-operation':
                content = item.get('content')
                found = MARKED.search(content) if isinstance(content, str) else None
                event = found.group(1) if found else None
                if item.get('operation') == 'enqueue':
                    state['queue'].append({'id': self._digest(content), 'client_id': event, 'at': at, 'kind': self._queued_kind(content)})
                elif item.get('operation') == 'dequeue':
                    # The record names no entry: the message that starts the next turn says which one left.
                    if state.get('dequeued'):
                        self._unqueue(state['queue'])
                    state['dequeued'] = 1
                elif item.get('operation') == 'remove':
                    self._unqueue(state['queue'], self._digest(content), event, self._queued_kind(content))
                elif item.get('operation') in ('popAll', 'clear'):
                    state['queue'], state['dequeued'] = [], 0
        return state, ended, messages

    @staticmethod
    def _digest(content):
        return hashlib.sha256(content.encode()).hexdigest()[:16] if isinstance(content, str) else None

    @staticmethod
    def _queued_kind(content):
        """What a queued entry is, from the envelope the client gives it.

        `internal` is the session's own event, a task notification or a subagent's report: the client can hold one
        while the session rests and it delays no message. `peer` is another session's message, `prompt` typed text.
        """
        head = content.lstrip()[:40] if isinstance(content, str) else ''
        if head.startswith(('<task-notification', '<agent-message')):
            return 'internal'
        return 'peer' if head.startswith('<cross-session-message') else 'prompt'

    @staticmethod
    def _unqueue(queue, digest=None, event=None, kind=None):
        """Drop the entry a record refers to: the same text, else the same kit event, else the oldest of its kind.

        With nothing to match, the oldest entry leaves. A kit entry leaves only by its text or its event.
        """
        position = next((i for i, entry in enumerate(queue) if digest and entry['id'] == digest), None)
        if position is None and event:
            position = next((i for i, entry in enumerate(queue) if entry['client_id'] == event), None)
        if position is None and kind:
            position = next((i for i, entry in enumerate(queue) if entry.get('kind') == kind and entry['client_id'] is None), None)
        if position is None and not (digest or event or kind) and queue:
            position = 0
        if position is not None:
            del queue[position]

    @staticmethod
    def _message(ident, turn, origin, at, text):
        """A message a session received. Only what a human typed is not inter-agent."""
        if origin.get('kind') == 'peer':
            # The client wraps a peer message in its own words; the registry keeps what the sender wrote.
            body = origin.get('body')
            start = text.find('<cross-session-message')
            text = body if isinstance(body, str) and body.strip() else text[start:] if start > 0 else text
        return {'id': ident, 'turn_id': turn['id'] if turn else None,
                'client_id': origin.get('msg_id') if origin.get('kind') == 'peer' and isinstance(origin.get('msg_id'), str) else None,
                'at': at, 'text': text, 'inter_agent': origin.get('kind') != 'human'}

    def observe(self, thread_id, cursor=None, workers_since=None, history_turns=30):
        """One read of a session with no model call: its live state, queue, turns, messages and cumulative token counter."""
        self._identity(thread_id)
        cursor = cursor or {}
        unknown = []
        try:
            record = self._live(thread_id, time.monotonic() + self.timeout)
        except DeliveryError:
            raise
        except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as exc:
            raise DeliveryError('Claude discovery failed: ' + str(exc)) from exc
        native = record['status'] if record else None
        if record is None:
            status, flags = 'notLoaded', []
        elif native == 'busy':
            status, flags = 'active', []
        elif native == 'waiting':
            status, flags = 'active', [WAITING.get(record.get('waitingFor'), 'waitingOnUserInput')]
        elif native == 'shell':
            status, flags = 'idle', ['backgroundShell']
        elif native == 'idle':
            status, flags = 'idle', []
        else:
            status, flags = None, []
            unknown.append('status')
        result = {'id': thread_id, 'status': status, 'flags': flags, 'native_status': native, 'parent_id': None,
                  'can_accept_input': bool(record and record.get('messagingSocketPath')),
                  'cli_version': record.get('version') if record else None, 'allowance': None, 'workers': [], 'history_reset': False}
        try:
            found = list((self.config_dir / 'projects').glob(f'*/{thread_id}.jsonl'))
        except OSError:
            found = [None, None]
        state_in = cursor.get('log') if isinstance(cursor.get('log'), dict) else None
        state, ended, messages = state_in, [], []
        if len(found) == 1:
            try:
                state, ended, messages = self._scan(found[0], state_in)
                result['history_reset'] = bool(state_in and state_in.get('inode') is not None and state.get('inode') != state_in['inode'])
            except (OSError, ValueError, DeliveryError):
                unknown += ['turns', 'messages', 'usage', 'queue']
        elif not found and record is not None:
            # A live session that has recorded nothing yet: an empty history and a counter at zero.
            state = {'path': None, 'inode': None, 'offset': 0, 'usage': dict.fromkeys(USAGE, 0) | {'at': None},
                     'recent': {}, 'turn': None, 'queue': [], 'dequeued': 0, 'created_at': None, 'clock': None}
        elif not found:
            raise DeliveryError('Claude session is neither live nor recorded on this machine')
        else:
            unknown += ['turns', 'messages', 'usage', 'queue']
        readable = 'usage' not in unknown and state is not None
        turns = []
        if readable:
            turns = list(ended)
            turn = state.get('turn')
            if turn is not None:
                running = {'id': turn['id'], 'status': 'inProgress', 'started_at': turn.get('started_at'), 'completed_at': None}
                if native in ('busy', 'waiting'):
                    turns.append(running)
                else:
                    # The registry is written after the history: a turn with no end on record is over once the registry says so later.
                    settled = record is None or turn.get('evidence') or (record.get('statusUpdatedAt') or 0) / 1000 >= (turn.get('last_at') or 0)
                    if settled:
                        turns.append(self._close(turn, 'interrupted' if record is None else 'completed'))
                        state['turn'] = None
                    else:
                        turns.append(running)
            if state_in is None and len(turns) > history_turns:
                turns = turns[-history_turns:]
                kept = {entry['id'] for entry in turns}
                messages = [message for message in messages if message['turn_id'] in kept]
            if record is None:
                # The queue lives in the process: a process that is gone holds nothing.
                state['queue'], state['dequeued'] = [], 0
            else:
                started = (record.get('startedAt') or 0) / 1000
                state['queue'] = [entry for entry in state['queue'] if entry.get('at') is None or entry['at'] >= started]
                if native in ('idle', 'shell'):
                    # A session at rest reads a queued message at once: one on record from before it came to rest is not waiting.
                    rested = (record.get('statusUpdatedAt') or 0) / 1000
                    state['queue'] = [entry for entry in state['queue'] if entry.get('kind') == 'internal' or (entry.get('at') or 0) > rested]
            # What is reported is what a new message would wait behind: the session's own held events are not.
            result['queue'] = [{'id': entry['id'], 'client_id': entry['client_id']} for entry in state['queue'] if entry.get('kind') != 'internal']
            result['usage'] = dict(state['usage'])
        else:
            result['queue'] = None
            result['usage'] = None
        result['turns'] = turns
        result['messages'] = messages if readable else []
        workers = dict(cursor.get('workers') or {})
        if workers_since is not None and len(found) == 1:
            base = found[0].parent / thread_id / 'subagents'
            try:
                files = sorted(base.rglob('*.jsonl')) if base.is_dir() else []
            except OSError:
                files = []
                unknown.append('workers')
            for file in files:
                key = str(file.relative_to(base))[:-len('.jsonl')]
                try:
                    # A worker file untouched since before the task spent nothing in it.
                    if key not in workers and file.stat().st_mtime < workers_since:
                        continue
                    workers[key], _, _ = self._scan(file, workers.get(key), light=True)
                except (OSError, ValueError, DeliveryError):
                    if 'workers' not in unknown:
                        unknown.append('workers')
            result['workers'] = [{'id': thread_id + '/' + key, 'created_at': entry.get('created_at'), 'usage': dict(entry['usage'])}
                                 for key, entry in workers.items()]
        result['cursor'] = {'log': state if readable else state_in, 'workers': workers}
        result['unknown'] = unknown
        return result
