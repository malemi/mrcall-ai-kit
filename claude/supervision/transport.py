import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import struct
import subprocess
import sys
import time
import uuid


class DeliveryError(RuntimeError):
    def __init__(self, message, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


class NativeTransport:
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

    def _record(self, thread_id, deadline):
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
        if record.get('version') != '2.1.296' or record.get('peerProtocol') != 1:
            raise DeliveryError('unsupported Claude version/protocol; expected 2.1.296 / 1')
        if record.get('procStart') != self._proc_start(pid):
            raise DeliveryError('Claude PID start identity mismatch')
        if not isinstance(record.get('cwd'), str) or not isinstance(record.get('status'), str):
            raise DeliveryError('Claude registry lacks cwd/status')
        self._left(deadline)
        return record

    @staticmethod
    def _meta(record):
        return {'id': record['sessionId'], 'cwd': record['cwd'],
                'status': {'type': 'idle' if record['status'] == 'idle' else 'busy'},
                'native_status': record['status'], 'parentThreadId': None,
                'canAcceptDirectInput': bool(record.get('messagingSocketPath')),
                'cliVersion': record['version'], 'runtime': 'claude'}

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
        return f'<cross-session-message from-name="ai-kit-supervisor">\nAI_KIT_SUPERVISION_EVENT {event_id}\n{escaped}\n</cross-session-message>'

    def send(self, thread_id, event_id, text, allow_busy=False):
        self._identity(event_id)
        if not isinstance(text, str) or not text.strip():
            raise DeliveryError('nonempty event text required')
        writing = False
        try:
            deadline = time.monotonic() + self.timeout
            record = self._record(thread_id, deadline)
            if not allow_busy and record['status'] != 'idle':
                raise DeliveryError('supervisor is busy; event was not submitted')
            if not record.get('messagingSocketPath'):
                raise DeliveryError('Claude root has no live inbox')
            path = Path(record['messagingSocketPath'])
            self._path(path.parent, 'directory', private=True)
            self._path(path, 'socket', private=True)
            frame = {'msgV': 1, 'msg_id': event_id, 'type': 'user', 'priority': 'next',
                     'message': {'role': 'user', 'content': self._envelope(event_id, text)}}
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(self._left(deadline))
                connection.connect(str(path))
                pid, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if pid != record['pid'] or uid != os.getuid() or self._proc_start(pid) != record['procStart']:
                    raise DeliveryError('Claude connected inbox process identity mismatch')
                connection.settimeout(self._left(deadline))
                writing = True
                connection.sendall((json.dumps(frame) + '\n').encode())
                connection.shutdown(socket.SHUT_WR)
            return {'status': 'uncertain', 'event_id': event_id, 'native_submission_id': event_id,
                    'thread_id': thread_id, 'assessment_completed': False,
                    'reason': 'Native socket has no delivery acknowledgement; reconcile recipient history'}
        except DeliveryError as exc:
            if writing:
                exc.uncertain = True
            raise
        except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as exc:
            raise DeliveryError('Claude inbox submission failed: ' + str(exc), uncertain=writing) from exc

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
    def _turns(cls, records, direction):
        turns = []
        for item in records:
            if item.get('type') == 'attachment' and isinstance(item.get('attachment'), dict) and item['attachment'].get('type') == 'prompt_snapshot':
                continue
            if item.get('type') not in ('user', 'assistant', 'system', 'progress', 'attachment', 'queue-operation'):
                continue
            public = {key: item[key] for key in ('type', 'message', 'subtype', 'data', 'isSidechain', 'agentId', 'toolUseResult', 'content', 'attachment', 'operation', 'deliveryId') if key in item}
            turns.append({'id': item.get('uuid'), 'status': 'recorded', 'startedAt': item.get('timestamp'),
                          'completedAt': None, 'items': [cls._public(public)]})
        return turns if direction == 'asc' else list(reversed(turns))

    def read(self, thread_id, cursor=None, sort_direction='desc'):
        if sort_direction not in ('asc', 'desc'):
            raise DeliveryError('sort_direction must be asc or desc')
        try:
            deadline = time.monotonic() + self.timeout
            record = self._record(thread_id, deadline)
            path = self._root_path(thread_id)
            data, records, info = self._history(path, thread_id, deadline)
            offset = 0
            identity = [str(path), info.st_dev, info.st_ino]
            if cursor is not None:
                anchor = json.loads(base64.b64decode(cursor, validate=True))
                offset = anchor['offset']
                if (anchor['session'] != thread_id or anchor['identity'] != identity or type(offset) is not int
                        or offset < 0 or offset > len(data) or offset and data[offset - 1:offset] != b'\n'
                        or anchor['digest'] != hashlib.sha256(data[:offset]).hexdigest()):
                    raise DeliveryError('Claude cursor identity/prefix changed; full reread required')
                records = [json.loads(line) for line in data[offset:].splitlines()]
            anchor = {'session': thread_id, 'identity': identity, 'offset': len(data),
                      'digest': hashlib.sha256(data).hexdigest()}
            newer = base64.b64encode(json.dumps(anchor).encode()).decode()
            workers = []
            directory = path.parent / thread_id
            if directory.exists():
                self._path(directory, 'directory')
                directory = directory / 'subagents'
                if directory.exists():
                    self._path(directory, 'directory')
                    for worker in sorted(directory.glob('*.jsonl')):
                        _, messages, _ = self._history(worker, thread_id, deadline)
                        workers.append({'id': worker.stem, 'parentThreadId': thread_id,
                                        'turns': self._turns(messages, sort_direction)})
            return {'thread': self._meta(record), 'turns': self._turns(records, sort_direction),
                    'workers': workers, 'workers_are_full_snapshots': True,
                    'next_cursor': None, 'newer_cursor': newer, 'reverse_cursor': newer,
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
            marker = f'AI_KIT_SUPERVISION_EVENT {event_id}\n'
            for record in records:
                message = record.get('message', {})
                origin = record.get('origin', {})
                if not isinstance(message, dict) or not isinstance(origin, dict):
                    raise DeliveryError('Claude user message/origin shape unsupported')
                body = origin.get('body')
                if (record.get('type') != 'user' or message.get('role') != 'user'
                        or origin.get('kind') != 'peer' or origin.get('msg_id') != event_id
                        or origin.get('name') != 'ai-kit-supervisor'
                        or not isinstance(body, str) or not body.startswith(marker)):
                    continue
                envelope = f'<cross-session-message from-name="ai-kit-supervisor">\n{body}\n</cross-session-message>'
                content = message.get('content')
                blocks = [{'type': 'text', 'text': content}] if isinstance(content, str) else content
                if not isinstance(blocks, list):
                    continue
                for block in blocks:
                    if not isinstance(block, dict) or block.get('type') != 'text':
                        continue
                    text = block.get('text')
                    if isinstance(text, str) and envelope in text:
                        return {'status': 'delivered', 'location': 'history', 'event_id': event_id,
                                'native_submission_id': event_id, 'turn_id': record.get('uuid')}
            return {'status': 'absent', 'event_id': event_id, 'absence_is_not_permission_to_resend': True}
        except (DeliveryError, OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as exc:
            raise DeliveryError('Claude reconciliation incomplete: ' + str(exc), uncertain=True) from exc
