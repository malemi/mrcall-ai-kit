"""Codex local control socket adapter; no native database reads or writes."""
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import time
import uuid


# Native history pages can include large tool outputs. Keep a finite receive
# ceiling while allowing real sessions beyond websockets' 1 MiB default.
MAX_MESSAGE_BYTES = 64 * 1024 * 1024


class DeliveryError(RuntimeError):
    def __init__(self, message, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


class NativeTransport:
    def __init__(self, codex_path='codex', timeout=10, socket_path=None):
        self.codex_path = shutil.which(codex_path) if not os.path.isabs(codex_path) else codex_path
        self.timeout = float(timeout)
        if not 0 < self.timeout <= 120:
            raise DeliveryError('transport timeout must be in (0, 120]')
        self.socket_path = socket_path

    @staticmethod
    def _identity(value):
        try:
            if str(uuid.UUID(value)) != value:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise DeliveryError('exact canonical session/event UUID required') from None
        return value

    def _socket(self, deadline):
        if self.socket_path is not None:
            path = Path(self.socket_path)
        else:
            if not self.codex_path:
                raise DeliveryError('codex executable unavailable')
            try:
                result = subprocess.run([self.codex_path, 'app-server', 'daemon', 'version'],
                                        capture_output=True, text=True, timeout=self._left(deadline), check=True)
                data = json.loads(result.stdout)
                if data.get('status') != 'running':
                    raise DeliveryError('Codex daemon unavailable; no daemon was started')
                path = Path(data['socketPath'])
            except subprocess.CalledProcessError as exc:
                detail = (exc.stderr or '').strip()
                raise DeliveryError('cannot discover running Codex daemon: ' + (detail or str(exc))) from exc
            except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
                raise DeliveryError('cannot discover running Codex daemon: ' + str(exc)) from exc
        try:
            # Codex itself publishes an owned symlink to a private runtime socket.
            if not path.is_absolute():
                raise DeliveryError('Codex socket path must be absolute')
            link = path.lstat()
            actual = path.stat()
            if link.st_uid != os.getuid() or actual.st_uid != os.getuid() or not stat.S_ISSOCK(actual.st_mode) or stat.S_IMODE(actual.st_mode) & 0o077:
                raise DeliveryError('Codex socket ownership/type/permissions refused')
        except OSError as exc:
            raise DeliveryError('Codex socket unavailable: ' + str(exc)) from exc
        return path

    @staticmethod
    def _left(deadline):
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError('native transport deadline exceeded')
        return left

    def _session(self):
        try:
            from websockets.sync.client import unix_connect
        except ImportError as exc:
            raise DeliveryError('missing websockets dependency; install the supervision requirements in its owned environment') from exc
        deadline = time.monotonic() + self.timeout
        path = self._socket(deadline)
        try:
            ws = unix_connect(str(path), uri='ws://localhost', open_timeout=self._left(deadline), close_timeout=1,
                              max_size=MAX_MESSAGE_BYTES)
            self._rpc(ws, deadline, 'initialize', {'clientInfo': {'name': 'mrcall_ai_kit_supervisor', 'version': '1'},
                                                  'capabilities': {'experimentalApi': True}})
            ws.send(json.dumps({'method': 'initialized', 'params': {}}))
            return ws, deadline
        except Exception as exc:
            if 'ws' in locals():
                ws.close()
            if isinstance(exc, DeliveryError):
                raise
            raise DeliveryError('native initialization failed: ' + str(exc)) from exc

    def _rpc(self, ws, deadline, method, params, mutation=False):
        ident = str(uuid.uuid4())
        try:
            self._left(deadline)
            ws.send(json.dumps({'id': ident, 'method': method, 'params': params}))
            while True:
                message = json.loads(ws.recv(timeout=self._left(deadline)))
                if message.get('id') != ident:
                    continue
                if 'error' in message:
                    raise DeliveryError('native request refused: ' + json.dumps(message['error']), uncertain=False)
                if 'result' not in message:
                    raise DeliveryError('malformed native acknowledgement', uncertain=mutation)
                return message['result']
        except DeliveryError:
            raise
        except Exception as exc:
            raise DeliveryError('native request outcome unavailable: ' + str(exc), uncertain=mutation) from exc

    def _metadata(self, ws, deadline, thread_id):
        data = self._rpc(ws, deadline, 'thread/read', {'threadId': self._identity(thread_id), 'includeTurns': False})
        thread = data.get('thread', {})
        if thread.get('id') != thread_id or not isinstance(thread.get('status'), dict):
            raise DeliveryError('native thread identity/status mismatch')
        return {key: thread.get(key) for key in ('id', 'cwd', 'status', 'parentThreadId', 'canAcceptDirectInput', 'cliVersion', 'model', 'reasoningEffort')}

    def metadata(self, thread_id):
        ws, deadline = self._session()
        try:
            return self._metadata(ws, deadline, thread_id)
        finally:
            ws.close()

    def send(self, thread_id, event_id, text, allow_busy=False):
        self._identity(event_id)
        if not isinstance(text, str) or not text.strip():
            raise DeliveryError('nonempty event text required')
        ws, deadline = self._session()
        try:
            meta = self._metadata(ws, deadline, thread_id)
            if meta.get('canAcceptDirectInput') is not True or meta.get('parentThreadId'):
                raise DeliveryError('target does not support direct input; subagents are observation-only')
            if not allow_busy and meta['status'].get('type') != 'idle':
                raise DeliveryError('supervisor is busy; event was not submitted')
            result = self._rpc(ws, deadline, 'thread/queue/add', {'threadId': thread_id, 'clientUserMessageId': event_id,
                                'input': [{'type': 'text', 'text': text}]}, mutation=True)
            submission = result.get('queuedSubmission', {})
            if submission.get('clientUserMessageId') != event_id or not isinstance(submission.get('id'), str):
                raise DeliveryError('native queue acknowledgement identity mismatch', uncertain=True)
            # queue/add auto-starts on the measured native runtime. A second start races.
            return {'status': 'delivered', 'event_id': event_id, 'native_submission_id': submission['id'],
                    'thread_id': thread_id, 'assessment_completed': False}
        finally:
            ws.close()

    @staticmethod
    def _pages(rpc, method, params):
        seen = set()
        while True:
            page = rpc(method, params)
            if not isinstance(page.get('data'), list):
                raise DeliveryError('invalid native page; absence not established', uncertain=True)
            yield page['data']
            cursor = page.get('nextCursor')
            if cursor is None:
                break
            if not isinstance(cursor, str) or cursor in seen:
                raise DeliveryError('native pagination did not advance', uncertain=True)
            seen.add(cursor)
            params = dict(params, cursor=cursor)

    def reconcile(self, thread_id, event_id):
        self._identity(event_id)
        ws, deadline = self._session()
        try:
            self._metadata(ws, deadline, thread_id)
            rpc = lambda method, params: self._rpc(ws, deadline, method, params)
            for page in self._pages(rpc, 'thread/queue/list', {'threadId': thread_id}):
                for entry in page:
                    if entry.get('clientUserMessageId') == event_id:
                        return {'status': 'delivered', 'location': 'queue', 'native_submission_id': entry.get('id'), 'event_id': event_id}
            for page in self._pages(rpc, 'thread/turns/list', {'threadId': thread_id, 'itemsView': 'full'}):
                for turn in page:
                    for item in turn.get('items', []):
                        if item.get('type') == 'userMessage' and item.get('clientId') == event_id:
                            return {'status': 'delivered', 'location': 'history', 'turn_id': turn['id'], 'event_id': event_id,
                                    'turn_status': turn.get('status')}
            return {'status': 'absent', 'event_id': event_id, 'absence_is_not_permission_to_resend': True}
        except DeliveryError as exc:
            # Incomplete inspection must never clear an uncertain prior send.
            raise DeliveryError(str(exc), uncertain=True) from exc
        finally:
            ws.close()

    def read(self, thread_id, cursor=None, sort_direction='desc'):
        if sort_direction not in ('asc', 'desc'):
            raise DeliveryError('sort_direction must be asc or desc')
        ws, deadline = self._session()
        try:
            meta = self._metadata(ws, deadline, thread_id)
            params = {'threadId': thread_id, 'itemsView': 'full', 'sortDirection': sort_direction}
            if cursor is not None:
                params['cursor'] = cursor
            page = self._rpc(ws, deadline, 'thread/turns/list', params)
            if not isinstance(page.get('data'), list):
                raise DeliveryError('invalid native history page')
            turns = []
            for turn in page['data']:
                public = []
                for item in turn.get('items', []):
                    if item.get('type') in ('userMessage', 'agentMessage', 'commandExecution', 'mcpToolCall', 'subAgentActivity',
                                             'collabAgentToolCall', 'functionCallOutput', 'dynamicToolCall', 'plan', 'fileChange', 'sleep'):
                        public.append(item)
                turns.append({key: turn.get(key) for key in ('id', 'status', 'startedAt', 'completedAt')} | {'items': public})
            return {'thread': meta, 'turns': turns, 'next_cursor': page.get('nextCursor'),
                    'newer_cursor': page.get('backwardsCursor'), 'reverse_cursor': page.get('backwardsCursor'),
                    'sort_direction': sort_direction, 'private_reasoning_included': False}
        finally:
            ws.close()
