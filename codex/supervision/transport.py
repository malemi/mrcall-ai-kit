"""Codex local control socket adapter; no native database reads or writes."""
import ast
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import shlex
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


def bookkeeping_command(command):
    try:
        words = command if isinstance(command, list) else shlex.split(command)
        if len(words) == 3 and Path(words[0]).name in ('bash', 'sh') and words[1] in ('-lc', '-c'):
            command = words[2]
        elif isinstance(command, list):
            command = shlex.join(command)
        words = shlex.split(command) if isinstance(command, str) else words
        cli = list(words)
        if cli and Path(cli[0]).name in ('python', 'python3'):
            cli.pop(0)
            if cli and cli[0] == '-I':
                cli.pop(0)
            if cli and Path(cli.pop(0)).name == 'goal_client.py' and not any(char in command for char in ('$', '`', '\n', ';', '&', '|', '>', '<')):
                if len(cli) == 4 and cli[0] == '--socket' and cli[2] == 'request':
                    payload = json.loads(cli[3])
                    return isinstance(payload, dict) and payload.get('op') in ('inspect', 'report', 'check_request')
        lines = command.strip().splitlines()
        header = shlex.split(lines[0])
        if len(header) != 3 or Path(header[0]).name not in ('python', 'python3') or header[1] != '-' or not header[2].startswith('<<'):
            return False
        raw_header = lines[0].strip()
        if '$' in raw_header or '`' in raw_header:
            return False
        marker = raw_header.find('<<')
        if marker < 0 or raw_header[marker + 2:marker + 3] not in ("'", '"'):
            return False
        delimiter = header[2][2:]
        if raw_header[marker + 2:] not in ("'" + delimiter + "'", '"' + delimiter + '"'):
            return False
        if not delimiter or lines[-1] != delimiter:
            return False
        tree = ast.parse('\n'.join(lines[1:-1]))
        names = set()
        imported = set()
        requests = []
        types = {'list', 'dict', 'tuple', 'str', 'int', 'float', 'bool'}
        reserved = types | {'sys', 'json', 'request', 'print', 'isinstance'}

        def type_reference(node):
            return (isinstance(node, ast.Name) and node.id in types or
                    isinstance(node, ast.Tuple) and all(type_reference(item) for item in node.elts))

        def pure(node, bound=frozenset()):
            if isinstance(node, ast.Constant):
                return True
            if isinstance(node, ast.Name):
                return node.id in names or node.id in bound
            if isinstance(node, (ast.List, ast.Tuple)):
                return all(pure(item, bound) for item in node.elts)
            if isinstance(node, ast.Dict):
                return all(key is not None and pure(key, bound) and pure(item, bound) for key, item in zip(node.keys, node.values))
            if isinstance(node, ast.Subscript):
                return pure(node.value, bound) and pure(node.slice, bound)
            if isinstance(node, ast.Slice):
                return all(item is None or pure(item, bound) for item in (node.lower, node.upper, node.step))
            if isinstance(node, ast.IfExp):
                return pure(node.test, bound) and pure(node.body, bound) and pure(node.orelse, bound)
            if isinstance(node, ast.Compare):
                return (all(isinstance(op, (ast.Eq, ast.NotEq, ast.Is, ast.IsNot, ast.In, ast.NotIn, ast.Lt, ast.LtE, ast.Gt, ast.GtE)) for op in node.ops)
                        and pure(node.left, bound) and all(pure(item, bound) for item in node.comparators))
            if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
                return all(pure(item, bound) for item in node.values)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Not, ast.USub, ast.UAdd)):
                return pure(node.operand, bound)
            if isinstance(node, ast.Call) and not node.keywords and isinstance(node.func, ast.Name):
                if node.func.id == 'list':
                    return len(node.args) == 1 and pure(node.args[0], bound)
                if node.func.id == 'isinstance':
                    return len(node.args) == 2 and pure(node.args[0], bound) and type_reference(node.args[1])
            if isinstance(node, ast.Call) and not node.keywords and isinstance(node.func, ast.Attribute) and node.func.attr == 'get':
                return (isinstance(node.func.value, ast.Name) and pure(node.func.value, bound)
                        and 1 <= len(node.args) <= 2 and all(pure(arg, bound) for arg in node.args))
            if isinstance(node, ast.DictComp) and len(node.generators) == 1:
                generator = node.generators[0]
                if (generator.is_async or not isinstance(generator.target, ast.Name)
                        or generator.target.id in reserved
                        or not isinstance(generator.iter, (ast.List, ast.Tuple))
                        or not all(isinstance(item, ast.Constant) for item in generator.iter.elts)):
                    return False
                scope = bound | {generator.target.id}
                return pure(node.key, scope) and pure(node.value, scope) and all(pure(test, scope) for test in generator.ifs)
            return False

        def literal(node):
            return (isinstance(node, ast.Constant) or isinstance(node, (ast.Tuple, ast.List))
                    and all(literal(item) for item in node.elts))

        def value(node):
            if pure(node):
                return True
            if isinstance(node, ast.Constant):
                return True
            if isinstance(node, ast.Name):
                return node.id in names
            if isinstance(node, (ast.List, ast.Tuple)):
                return all(value(item) for item in node.elts)
            if isinstance(node, ast.Dict):
                return all(key is not None and value(key) and value(item) for key, item in zip(node.keys, node.values))
            if isinstance(node, ast.Subscript):
                return value(node.value) and value(node.slice)
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == 'json'
                    and 'json' in imported and node.func.attr in ('dumps', 'loads')):
                if node.keywords and (node.func.attr != 'dumps' or not all(
                        item.arg in ('sort_keys', 'indent', 'separators', 'ensure_ascii') and literal(item.value) for item in node.keywords)):
                    return False
                return all(value(arg) for arg in node.args)
            if isinstance(node, ast.Call) and not node.keywords:
                if isinstance(node.func, ast.Name) and node.func.id == 'request' and 'request' in imported:
                    if len(node.args) != 2 or not all(value(arg) for arg in node.args) or not isinstance(node.args[1], ast.Dict):
                        return False
                    payload = node.args[1]
                    if not all(isinstance(key, ast.Constant) and isinstance(key.value, str) for key in payload.keys):
                        return False
                    operations = [v for k, v in zip(payload.keys, payload.values) if k.value == 'op']
                    if len(operations) != 1 or not isinstance(operations[0], ast.Constant) or operations[0].value not in ('inspect', 'report', 'check_request'):
                        return False
                    requests.append(operations[0].value)
                    return True
                if isinstance(node.func, ast.Name) and node.func.id == 'print':
                    return all(value(arg) for arg in node.args)
            return False

        def statements(nodes):
            for node in nodes:
                if isinstance(node, ast.Import) and all(item.name in ('sys', 'json') and item.asname is None for item in node.names):
                    imported.update(item.name for item in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module == 'goal_client' and node.level == 0 and len(node.names) == 1 and node.names[0].name == 'request' and node.names[0].asname is None:
                    imported.add('request')
                elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id not in reserved and value(node.value):
                    names.add(node.targets[0].id)
                elif isinstance(node, ast.Expr):
                    call = node.value
                    if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                            and isinstance(call.func.value, ast.Attribute) and isinstance(call.func.value.value, ast.Name)
                            and call.func.value.value.id == 'sys' and 'sys' in imported and call.func.value.attr == 'path'
                            and call.func.attr in ('insert', 'append') and not call.keywords
                            and all(isinstance(arg, ast.Constant) for arg in call.args)):
                        continue
                    if not value(call):
                        return False
                elif isinstance(node, ast.For):
                    if (not isinstance(node.target, ast.Name) or node.target.id in reserved
                            or not isinstance(node.iter, (ast.List, ast.Tuple))
                            or not all(isinstance(item, ast.Constant) for item in node.iter.elts)):
                        return False
                    previous_names, previous_imported = set(names), set(imported)
                    names.add(node.target.id)
                    if not statements(node.body) or not statements(node.orelse):
                        return False
                    names.intersection_update(previous_names)
                    imported.intersection_update(previous_imported)
                elif isinstance(node, ast.If):
                    if not pure(node.test):
                        return False
                    previous_names, previous_imported = set(names), set(imported)
                    if not statements(node.body):
                        return False
                    body_names, body_imported = set(names), set(imported)
                    names.intersection_update(previous_names)
                    imported.intersection_update(previous_imported)
                    if not statements(node.orelse):
                        return False
                    names.intersection_update(body_names)
                    imported.intersection_update(body_imported)
                else:
                    return False
            return True

        if not statements(tree.body):
            return False
        return bool(requests)
    except (ValueError, TypeError, IndexError, SyntaxError, AttributeError):
        return False


def public_activity(turns):
    evidence = {}
    states = set()
    for turn in turns:
        status = turn.get('status')
        if status in ('inProgress', 'active', 'running'):
            states.add('active')
        elif status != 'completed':
            states.add('unknown')
        items = turn.get('items')
        if not isinstance(items, list) or not isinstance(turn.get('id'), str):
            states.add('unknown')
            continue
        for item in items:
            if not isinstance(item, dict):
                states.add('unknown')
                continue
            kind = item.get('type')
            state = 'no_work'
            if item.get('status') in ('inProgress', 'active', 'running'):
                state = 'active'
            elif kind == 'commandExecution':
                command = item.get('command')
                valid = isinstance(command, str) and bool(command.strip()) or isinstance(command, list) and bool(command) and all(isinstance(word, str) for word in command)
                state = 'unknown' if not valid else ('no_work' if bookkeeping_command(command) else 'execution')
            elif kind in ('fileChange', 'mcpToolCall', 'dynamicToolCall', 'collabAgentToolCall', 'subAgentActivity', 'webSearch', 'imageGeneration'):
                state = 'execution'
            elif kind not in ('userMessage', 'agentMessage', 'reasoning', 'plan', 'sleep'):
                state = 'unknown'
            states.add(state)
            if kind != 'reasoning':
                key = str(kind) + ':' + state
                evidence[key] = evidence.get(key, 0) + 1
    classification = next((state for state in ('active', 'execution', 'unknown') if state in states), 'no_work')
    return {'classification': classification, 'turn_ids': [turn.get('id') for turn in turns], 'evidence': evidence,
            'execution_is_not_progress': True, 'private_reasoning_included': False}


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

    def reconcile(self, thread_id, event_id, include_activity=False):
        self._identity(event_id)
        ws, deadline = self._session()
        try:
            self._metadata(ws, deadline, thread_id)
            rpc = lambda method, params: self._rpc(ws, deadline, method, params)
            for page in self._pages(rpc, 'thread/queue/list', {'threadId': thread_id}):
                for entry in page:
                    if entry.get('clientUserMessageId') == event_id:
                        return {'status': 'delivered', 'location': 'queue', 'native_submission_id': entry.get('id'), 'event_id': event_id}
            observed = []
            params = {'threadId': thread_id, 'itemsView': 'full'}
            if include_activity:
                params['sortDirection'] = 'desc'
            for page in self._pages(rpc, 'thread/turns/list', params):
                for turn in page:
                    if not isinstance(turn, dict) or not isinstance(turn.get('items'), list):
                        raise DeliveryError('invalid native turn; activity unknown', uncertain=True)
                    observed.append(turn)
                    for item in turn['items']:
                        if isinstance(item, dict) and item.get('type') == 'userMessage' and item.get('clientId') == event_id:
                            result = {'status': 'delivered', 'location': 'history', 'turn_id': turn['id'], 'event_id': event_id,
                                      'turn_status': turn.get('status')}
                            if include_activity:
                                result['activity'] = public_activity(observed)
                            return result
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

    def interrupt(self, thread_id, turn_id):
        self._identity(thread_id)
        self._identity(turn_id)
        ws, deadline = self._session()
        try:
            self._rpc(ws, deadline, 'turn/interrupt', {'threadId': thread_id, 'turnId': turn_id}, mutation=True)
            return {'status': 'interrupted', 'thread_id': thread_id, 'turn_id': turn_id}
        finally:
            ws.close()

    def observe(self, thread_id, cursor=None, workers_since=None, history_turns=30):
        self._identity(thread_id)
        cursor = cursor or {}
        closed_turn_in = cursor.get('closed_turn')
        open_in = dict(cursor.get('open') or {})
        rollout_in = dict(cursor.get('rollout') or {})
        workers_cursor_in = cursor.get('workers') or {'dirs': {}, 'found': {}}

        unknown = []
        ws, deadline = self._session()
        try:
            rpc = lambda method, params: self._rpc(ws, deadline, method, params)
            data = self._rpc(ws, deadline, 'thread/read', {'threadId': thread_id, 'includeTurns': False})
            thread = data.get('thread', {})
            if thread.get('id') != thread_id or not isinstance(thread.get('status'), dict):
                raise DeliveryError('native thread identity/status mismatch')
            status = thread['status']
            path = thread.get('path')

            result = {
                'id': thread_id,
                'status': status.get('type'),
                'flags': list(status.get('activeFlags') or []),
                'can_accept_input': thread.get('canAcceptDirectInput'),
                'parent_id': thread.get('parentThreadId'),
            }

            try:
                queue = []
                for page in self._pages(rpc, 'thread/queue/list', {'threadId': thread_id}):
                    for entry in page:
                        queue.append({'id': entry.get('id'), 'client_id': entry.get('clientUserMessageId')})
                result['queue'] = queue
            except Exception:
                result['queue'] = None
                unknown.append('queue')

            collected = []
            try:
                collected, new_closed_turn, history_reset = self._scan_turns(rpc, thread_id, closed_turn_in, history_turns)
                result['turns'] = [{'id': turn.get('id'), 'status': turn.get('status'),
                                     'started_at': turn.get('startedAt'), 'completed_at': turn.get('completedAt')}
                                    for turn in reversed(collected)]
                result['history_reset'] = history_reset
            except Exception:
                result['turns'] = []
                result['history_reset'] = False
                new_closed_turn = closed_turn_in
                unknown.append('turns')

            turn_status = {turn.get('id'): turn.get('status') for turn in collected}
            try:
                messages, new_open = self._scan_messages(rpc, thread_id, collected, open_in, turn_status)
                result['messages'] = messages
            except Exception:
                # Turns and their messages advance together: a turn whose messages were not read is listed again next time.
                result['messages'] = []
                result['turns'] = []
                result['history_reset'] = False
                new_open = open_in
                new_closed_turn = closed_turn_in
                unknown.append('messages')
                if 'turns' not in unknown:
                    unknown.append('turns')

            usage, allowance, new_rollout, rollout_ok = self._scan_rollout(path, rollout_in)
            if rollout_ok:
                result['usage'] = usage
                result['allowance'] = allowance
            else:
                result['usage'] = None
                result['allowance'] = None
                unknown.append('usage')
                unknown.append('allowance')
                new_rollout = rollout_in

            if workers_since is not None:
                workers_out, new_workers, workers_ok = self._scan_workers(path, thread_id, workers_since, workers_cursor_in)
                if workers_ok:
                    result['workers'] = workers_out
                else:
                    result['workers'] = []
                    unknown.append('workers')
                    new_workers = workers_cursor_in
            else:
                result['workers'] = []
                new_workers = workers_cursor_in

            result['cursor'] = {'closed_turn': new_closed_turn, 'open': new_open,
                                 'rollout': new_rollout, 'workers': new_workers}
            result['unknown'] = unknown
            return result
        finally:
            ws.close()

    def _scan_turns(self, rpc, thread_id, closed_turn_in, history_turns):
        collected = []
        found_closed = False
        params = {'threadId': thread_id, 'limit': 20, 'sortDirection': 'desc', 'itemsView': 'notLoaded'}
        for page in self._pages(rpc, 'thread/turns/list', params):
            stop = False
            for turn in page:
                if closed_turn_in is not None and turn.get('id') == closed_turn_in:
                    found_closed = True
                    stop = True
                    break
                collected.append(turn)
                if closed_turn_in is None and len(collected) >= history_turns:
                    stop = True
                    break
            if stop:
                break

        history_reset = False
        if closed_turn_in is not None and not found_closed:
            collected = collected[:history_turns]
            history_reset = True

        new_closed = closed_turn_in
        for turn in collected:
            if turn.get('status') != 'inProgress':
                new_closed = turn.get('id')
                break
        if history_reset and not any(turn.get('status') != 'inProgress' for turn in collected):
            new_closed = None

        return collected, new_closed, history_reset

    def _scan_messages(self, rpc, thread_id, collected, open_in, turn_status):
        turn_started = {turn.get('id'): turn.get('startedAt') for turn in collected}
        ordered = [turn.get('id') for turn in reversed(collected)]
        for turn_id in open_in:
            if turn_id not in ordered:
                ordered.append(turn_id)

        messages = []
        new_open = {}
        for turn_id in ordered:
            anchor = open_in.get(turn_id)
            entries, last_item_id = self._fetch_items(rpc, thread_id, turn_id, anchor, turn_started.get(turn_id))
            messages.extend(entries)
            status = turn_status.get(turn_id)
            if status is None and turn_id in open_in:
                status = 'inProgress'
            if status == 'inProgress' and (last_item_id or anchor) is not None:
                # No new item keeps the previous anchor, so a quiet running turn is not read again from its start.
                new_open[turn_id] = last_item_id or anchor
        return messages, new_open

    def _fetch_items(self, rpc, thread_id, turn_id, anchor, turn_started_at):
        def pull(use_anchor):
            messages = []
            last_item_id = None
            base = {'threadId': thread_id, 'turnId': turn_id, 'limit': 200,
                    'deferOutput': {'commandExecution': True, 'mcpToolCall': True}}
            params = dict(base, cursor={'type': 'item', 'itemId': anchor}) if use_anchor else dict(base)
            while True:
                page = rpc('thread/items/list', params)
                data = page.get('data')
                if not isinstance(data, list):
                    raise DeliveryError('invalid native items page; absence not established', uncertain=True)
                for entry in data:
                    item = entry.get('item') or {}
                    item_id = item.get('id')
                    if item_id is not None:
                        last_item_id = item_id
                    if item.get('type') != 'userMessage':
                        continue
                    at_ms = entry.get('startedAtMs')
                    if at_ms is None:
                        at_ms = item.get('startedAtMs')
                    at = at_ms / 1000 if isinstance(at_ms, (int, float)) else turn_started_at
                    parts = item.get('content') or []
                    text = '\n'.join(part.get('text', '') for part in parts
                                      if isinstance(part, dict) and part.get('type') == 'text')
                    messages.append({'id': item_id, 'turn_id': entry.get('turnId', turn_id),
                                      'client_id': item.get('clientId'), 'at': at, 'text': text,
                                      'inter_agent': False})
                next_cursor = page.get('nextCursor')
                if next_cursor is None:
                    break
                if not isinstance(next_cursor, str):
                    raise DeliveryError('native items pagination did not advance', uncertain=True)
                params = dict(base, cursor=next_cursor)
            return messages, last_item_id

        try:
            return pull(bool(anchor))
        except DeliveryError as exc:
            if anchor and '-32602' in str(exc):
                return pull(False)
            raise

    def _scan_rollout(self, path, cursor_rollout):
        try:
            if not isinstance(path, str) or not os.path.isabs(path):
                raise OSError('rollout path missing or not absolute')
            info = os.stat(path)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise OSError('rollout path not a regular file owned by the current user')
        except OSError:
            return None, None, cursor_rollout, False

        usage = cursor_rollout.get('usage')
        allowance = cursor_rollout.get('allowance')
        inode, size = info.st_ino, info.st_size
        try:
            with open(path, 'rb') as handle:
                stored_inode = cursor_rollout.get('inode')
                stored_offset = cursor_rollout.get('offset')
                # The same file, grown: read what was appended. A rotated rollout has another path and is read afresh.
                if cursor_rollout.get('path') == path and stored_inode == inode and isinstance(stored_offset, int) and size >= stored_offset:
                    lines, new_offset = self._complete_lines(handle, stored_offset)
                else:
                    window_start = max(0, size - 8 * 1024 * 1024)
                    lines, new_offset = self._complete_lines(handle, window_start)
                    if not any(self._relevant_line(line) for line in lines):
                        lines, new_offset = self._complete_lines(handle, 0)
                for line in lines:
                    if not self._relevant_line(line):
                        continue
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    if not isinstance(record, dict):
                        continue
                    if record.get('type') == 'token_usage_record':
                        thread_usage = (record.get('payload') or {}).get('thread_token_usage')
                        if isinstance(thread_usage, dict):
                            usage = {'total': thread_usage.get('total_tokens'), 'input': thread_usage.get('input_tokens'),
                                      'cached_input': thread_usage.get('cached_input_tokens'),
                                      'output': thread_usage.get('output_tokens'),
                                      'at': self._parse_timestamp(record.get('timestamp'))}
                    elif record.get('type') == 'event_msg':
                        payload = record.get('payload') or {}
                        if payload.get('type') == 'token_count':
                            rate_limits = payload.get('rate_limits') or {}
                            primary = rate_limits.get('primary') or {}
                            allowance = {'used_percent': primary.get('used_percent'),
                                          'window_minutes': primary.get('window_minutes'),
                                          'resets_at': primary.get('resets_at'),
                                          'plan_type': rate_limits.get('plan_type'),
                                          'at': self._parse_timestamp(record.get('timestamp'))}
        except OSError:
            return None, None, cursor_rollout, False

        new_cursor = {'path': path, 'inode': inode, 'offset': new_offset, 'usage': usage, 'allowance': allowance}
        return usage, allowance, new_cursor, True

    def _scan_workers(self, path, thread_id, workers_since, workers_cursor):
        dirs_state = {key: list(value) for key, value in (workers_cursor.get('dirs') or {}).items()}
        found_state = {key: dict(value) for key, value in (workers_cursor.get('found') or {}).items()}
        try:
            if not isinstance(path, str) or not os.path.isabs(path):
                raise OSError('rollout path unavailable; cannot locate sessions root')
            sessions_root = Path(path).parents[3]
        except (OSError, IndexError):
            return [], {'dirs': workers_cursor.get('dirs') or {}, 'found': workers_cursor.get('found') or {}}, False

        start_day = datetime.fromtimestamp(workers_since, tz=timezone.utc).date() - timedelta(days=1)
        end_day = datetime.now(timezone.utc).date()
        day = start_day
        while day <= end_day:
            directory = sessions_root / f'{day.year:04d}' / f'{day.month:02d}' / f'{day.day:02d}'
            key = str(directory)
            inspected = set(dirs_state.get(key, []))
            try:
                names = sorted(entry.name for entry in directory.glob('rollout-*.jsonl'))
            except OSError:
                names = []
            for name in names:
                if name in inspected:
                    continue
                file_path = directory / name
                try:
                    with open(file_path, 'rb') as handle:
                        first_line = handle.readline()
                    record = json.loads(first_line.decode('utf-8', 'replace'))
                except (OSError, ValueError):
                    inspected.add(name)
                    continue
                if isinstance(record, dict) and record.get('type') == 'session_meta':
                    payload = record.get('payload') or {}
                    worker_id = payload.get('id')
                    if payload.get('session_id') == thread_id and worker_id and worker_id != thread_id:
                        found_state[worker_id] = {'path': str(file_path), 'inode': None, 'offset': 0,
                                                   'usage': None, 'created_at': self._parse_timestamp(payload.get('timestamp'))}
                inspected.add(name)
            dirs_state[key] = sorted(inspected)
            day += timedelta(days=1)

        workers_out = []
        for worker_id, info in found_state.items():
            usage, _allowance, new_rollout, ok = self._scan_rollout(info.get('path'), info)
            if ok:
                info = dict(info, inode=new_rollout['inode'], offset=new_rollout['offset'], usage=usage)
                found_state[worker_id] = info
            workers_out.append({'id': worker_id, 'created_at': info.get('created_at'), 'usage': info.get('usage')})
        return workers_out, {'dirs': dirs_state, 'found': found_state}, True

    @staticmethod
    def _complete_lines(handle, start):
        handle.seek(start)
        data = handle.read()
        parts = data.rsplit(b'\n', 1)
        if len(parts) == 1:
            return [], start
        body = parts[0]
        offset = start + len(body) + 1
        if not body:
            return [], offset
        return [line.decode('utf-8', 'replace') for line in body.split(b'\n')], offset

    @staticmethod
    def _relevant_line(line):
        return 'token_usage_record' in line or 'token_count' in line

    @staticmethod
    def _parse_timestamp(value):
        if not isinstance(value, str):
            return None
        text = value[:-1] + '+00:00' if value.endswith('Z') else value
        try:
            return datetime.fromisoformat(text).timestamp()
        except ValueError:
            return None
