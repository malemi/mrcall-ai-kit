import datetime
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'claude/supervision/transport.py'
spec = importlib.util.spec_from_file_location('claude_transport', SOURCE)
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


def stamp(at=None):
    moment = datetime.datetime.fromtimestamp(time.time() if at is None else at, datetime.timezone.utc)
    return moment.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'


PEER = '''
import os, socket, sys
path, out = sys.argv[1], sys.argv[2]
server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(path)
os.chmod(path, 0o600)
server.listen()
print('ready', flush=True)
while True:
    client, _ = server.accept()
    with client:
        data = b''
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            data += chunk
    with open(out, 'ab') as stream:
        stream.write(data)
'''


class Shapes:
    """Records as Claude Code 2.1.323 writes them, for a session that has `history`, `thread_id` and `record`."""

    def write(self, record):
        self.history.parent.mkdir(parents=True, exist_ok=True)
        with self.history.open('a') as stream:
            stream.write(json.dumps({'sessionId': self.thread_id, 'uuid': str(uuid.uuid4()), 'timestamp': stamp(), **record}) + '\n')
        self.history.chmod(0o600)

    def human(self, text, index, at=None):
        ident = str(uuid.uuid4())
        self.write({'type': 'user', 'uuid': ident, 'timestamp': stamp(at), 'message': {'role': 'user', 'content': text},
                    'origin': {'kind': 'human'}, 'promptSource': 'typed', 'turnOrigin': 'human',
                    'turnPosition': {'promptIndex': index, 'turnIndex': index}, 'permissionMode': 'auto'})
        return ident

    def model(self, message_id, tokens, stop='tool_use', at=None, records=1):
        fresh, creation, cached, output = tokens
        for _ in range(records):
            self.write({'type': 'assistant', 'timestamp': stamp(at),
                        'message': {'id': message_id, 'role': 'assistant', 'stop_reason': stop, 'content': [{'type': 'text', 'text': 'working'}],
                                    'usage': {'input_tokens': fresh, 'cache_creation_input_tokens': creation,
                                              'cache_read_input_tokens': cached, 'output_tokens': output}}})

    def tool(self, at=None):
        self.write({'type': 'user', 'timestamp': stamp(at), 'toolUseResult': {'ok': True},
                    'message': {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'toolu_1', 'content': 'done'}]}})

    def queue(self, operation, content=None, at=None, **fields):
        self.write({'type': 'queue-operation', 'operation': operation, 'timestamp': stamp(at),
                    **({'content': content} if content is not None else {}), **fields})

    def arrive(self, frame, index=None, at=None):
        """A kit frame as the session records it: starting a turn when `index` is given, read inside the running turn otherwise."""
        content = frame['message']['content']
        origin = {'kind': 'peer', 'from': 'unknown', 'msg_id': frame['msg_id'], 'name': 'ai-kit-supervisor',
                  'body': content.split('\n', 1)[1].rsplit('\n', 1)[0]}
        self.queue('enqueue', content, at)
        if index is None:
            self.queue('remove', content, at, reason='absorbed_mid_turn')
            self.write({'type': 'attachment', 'timestamp': stamp(at),
                        'attachment': {'type': 'queued_command', 'prompt': content, 'source_uuid': str(uuid.uuid4()),
                                       'commandMode': 'prompt', 'origin': origin, 'timestamp': stamp(at), 'isMeta': True}})
        else:
            self.queue('dequeue', at=at)
            self.write({'type': 'user', 'timestamp': stamp(at), 'isMeta': True, 'message': {'role': 'user', 'content': content},
                        'origin': origin, 'promptSource': 'system', 'turnOrigin': 'peer',
                        'turnPosition': {'promptIndex': index, 'turnIndex': index}})

    def status(self, native, waiting_for=None):
        self.record.update(status=native, statusUpdatedAt=int(time.time() * 1000) + 1000)
        self.record.pop('waitingFor', None)
        if waiting_for:
            self.record['waitingFor'] = waiting_for
        self.write_registry()


class ClaudePeer(Shapes):
    """A second live session of the same account: its inbox is served by its own process."""

    def __init__(self, fixture):
        self.fixture = fixture
        self.thread_id = str(uuid.uuid4())
        self.history = fixture.project / f'{self.thread_id}.jsonl'
        self.socket_path = fixture.root / f'peer-{self.thread_id[:8]}.sock'
        self.inbox = fixture.root / f'peer-{self.thread_id[:8]}.frames'
        self.process = subprocess.Popen([sys.executable, '-c', PEER, str(self.socket_path), str(self.inbox)],
                                        stdout=subprocess.PIPE, text=True)
        assert self.process.stdout.readline().strip() == 'ready'
        pid = self.process.pid
        self.record = {'pid': pid, 'sessionId': self.thread_id, 'cwd': str(fixture.root), 'status': 'idle',
                       'version': '2.1.323', 'peerProtocol': 1, 'startedAt': int(time.time() * 1000) - 60000,
                       'procStart': transport.NativeTransport._proc_start(pid), 'messagingSocketPath': str(self.socket_path)}
        self.registry = fixture.sessions / f'{pid}.json'
        fixture.records.append(self.record)
        self.write_registry()

    def write_registry(self):
        self.registry.write_text(json.dumps(self.record))
        self.fixture.write_discovery()

    def frames(self):
        if not self.inbox.exists():
            return []
        return [json.loads(line) for line in self.inbox.read_text().splitlines() if line.strip()]

    def close(self):
        self.process.kill()
        self.process.wait(timeout=5)
        self.process.stdout.close()


class ClaudeFixture(Shapes):
    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix='ai-kit-claude-'))
        self.config_root = self.root / 'config'
        self.config_root.mkdir(mode=0o775)
        self.sessions = self.config_root / 'sessions'
        self.sessions.mkdir(mode=0o700)
        self.project = self.config_root / 'projects' / 'fixture'
        self.project.mkdir(parents=True)
        self.thread_id = str(uuid.uuid4())
        self.history = self.project / f'{self.thread_id}.jsonl'
        self.socket_path = self.root / 'inbox.sock'
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(self.socket_path))
        self.socket_path.chmod(0o600)
        self.server.listen()
        self.server.settimeout(0.1)
        self.frames = []
        self.auths = []
        self.peers = []
        self.stopped = threading.Event()
        self.received = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        self.record = {'pid': os.getpid(), 'sessionId': self.thread_id, 'cwd': str(self.root),
                       'status': 'idle', 'version': '2.1.296', 'peerProtocol': 1,
                       'startedAt': int(time.time() * 1000) - 60000,
                       'procStart': transport.NativeTransport._proc_start(os.getpid()),
                       'messagingSocketPath': str(self.socket_path)}
        self.records = [self.record]
        self.registry = self.sessions / f'{os.getpid()}.json'
        self.executable = self.root / 'claude'
        self.discovery = self.root / 'agents.json'
        self.write_registry()
        self.executable.write_text('#!/usr/bin/env python3\nimport pathlib,sys\n'
                                   'assert sys.argv[1:] == ["agents", "--json"]\n'
                                   f'print(pathlib.Path({str(self.discovery)!r}).read_text())\n')
        self.executable.chmod(0o700)
        self.append('user', 'Initial authorized task')

    def _serve(self):
        while not self.stopped.is_set():
            try:
                client, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with client:
                data = b''
                while True:
                    chunk = client.recv(65536)
                    if not chunk:
                        break
                    data += chunk
                for line in data.splitlines():
                    frame = json.loads(line)
                    (self.auths if frame.get('type') == 'auth' else self.frames).append(frame)
                if data:
                    self.received.set()

    def write_registry(self):
        self.registry.write_text(json.dumps(self.record))
        self.registry.chmod(0o664)
        self.write_discovery()

    def write_discovery(self):
        self.discovery.write_text(json.dumps(self.records))

    def peer(self):
        self.peers.append(ClaudePeer(self))
        return self.peers[-1]

    def append(self, role, content, path=None, **fields):
        path = path or self.history
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {'type': role, 'sessionId': self.thread_id, 'uuid': str(uuid.uuid4()),
                  'timestamp': '2026-10-27T00:00:00Z', 'message': {'role': role, 'content': content}, **fields}
        with path.open('a') as stream:
            stream.write(json.dumps(record) + '\n')
        path.chmod(0o600)
        return record

    def receipt(self, frame):
        content = frame['message']['content']
        body = content.split('\n', 1)[1].rsplit('\n', 1)[0]
        return self.append('user', 'Another Claude session sent a message:\n' + content
                           + "\n\nThis came from another Claude session — not typed by your user.",
                           origin={'kind': 'peer', 'msg_id': frame['msg_id'],
                                   'name': 'ai-kit-supervisor', 'body': body})

    def client(self):
        with patch.dict(os.environ, {'CLAUDE_CONFIG_DIR': str(self.config_root)}):
            return transport.NativeTransport(str(self.executable), timeout=5)

    def close(self):
        for peer in self.peers:
            peer.close()
        self.stopped.set()
        self.server.close()
        self.thread.join(timeout=2)


class ClaudeTransportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ClaudeFixture()
        self.addCleanup(self.fixture.close)
        self.client = self.fixture.client()

    def test_socket_submission_requires_recipient_history_not_quotes_or_tool_results(self):
        fixture = self.fixture
        event = str(uuid.uuid4())
        self.assertEqual(self.client.metadata(fixture.thread_id)['status']['type'], 'idle')
        result = self.client.send(fixture.thread_id, event, 'Continue the authorized next step')
        self.assertEqual(result['status'], 'uncertain')
        self.assertTrue(fixture.received.wait(2))
        frame = fixture.frames[0]
        self.assertEqual((frame['msgV'], frame['msg_id'], frame['priority'], frame['session_id']), (1, event, 'next', fixture.thread_id))
        self.assertEqual(fixture.auths, [])
        self.assertNotIn('from', frame)
        content = frame['message']['content']
        self.assertNotIn('from-mode', content)
        origin = {'kind': 'peer', 'msg_id': event, 'name': 'ai-kit-supervisor',
                  'body': content.split('\n', 1)[1].rsplit('\n', 1)[0]}
        fixture.append('assistant', content, origin=origin)
        fixture.append('user', [{'type': 'tool_result', 'tool_use_id': 'x', 'content': content}], origin=origin)
        self.assertEqual(self.client.reconcile(fixture.thread_id, event)['status'], 'absent')
        fixture.append('user', [{'type': 'text', 'text': content}])
        self.assertEqual(self.client.reconcile(fixture.thread_id, event)['status'], 'absent')
        fixture.receipt(frame)
        self.assertEqual(self.client.reconcile(fixture.thread_id, event)['status'], 'delivered')
        self.assertEqual(len(fixture.frames), 1)

    def test_public_large_output_workers_and_append_cursor_preserve_failure(self):
        fixture = self.fixture
        output = 'failure: command exited 17\n' + 'x' * (2 * 1024 * 1024)
        fixture.append('user', [{'type': 'tool_result', 'content': output, 'is_error': True},
                                {'type': 'thinking', 'thinking': 'PRIVATE'}])
        worker = fixture.project / fixture.thread_id / 'subagents' / 'agent-worker.jsonl'
        fixture.append('assistant', [{'type': 'text', 'text': 'Worker unresolved cause'},
                                     {'type': 'redacted_thinking', 'data': 'PRIVATE'}], path=worker,
                       agentId='worker', isSidechain=True)
        fixture.append('attachment', '', attachment={'type': 'prompt_snapshot',
                                                     'systemPrompt': ['PRIVATE_PROMPT_SNAPSHOT']})
        first = self.client.read(fixture.thread_id, sort_direction='asc')
        serialized = json.dumps(first)
        # A long output keeps its start, where the failure is named, and its end; the middle is counted, not shown.
        shown = first['turns'][-1]['items'][0]['message']['content'][0]['content']
        self.assertTrue(shown.startswith('failure: command exited 17\n'))
        self.assertIn(f'left out {len(output) - transport.CLIP} characters', shown)
        self.assertLess(len(serialized), 2 * transport.PAGE_BYTES)
        self.assertNotIn('PRIVATE', serialized)
        self.assertEqual((first['workers'][0]['parentThreadId'], first['workers'][0]['id'], first['workers'][0]['records']),
                         (fixture.thread_id, 'agent-worker', 1))
        self.assertEqual(first['workers'][0]['last_said']['text'], 'Worker unresolved cause')
        self.assertEqual((first['workers_are_full_snapshots'], first['thread']['history_path']), (False, str(fixture.history)))
        fixture.append('assistant', 'Later success does not resolve the prior cause')
        delta = self.client.read(fixture.thread_id, cursor=first['newer_cursor'])
        self.assertEqual(len(delta['turns']), 1)
        self.assertEqual(len(delta['workers']), 1)
        full = self.client.read(fixture.thread_id)
        self.assertIn('failure: command exited 17', json.dumps(full))
        original = fixture.history.read_bytes()
        fixture.history.write_bytes(original.replace(b'Initial authorized task', b'Changed authorized task'))
        with self.assertRaisesRegex(transport.DeliveryError, 'prefix changed'):
            self.client.read(fixture.thread_id, cursor=first['newer_cursor'])

    def test_a_long_history_is_read_in_bounded_pages_in_both_directions(self):
        fixture = self.fixture
        for index in range(120):
            fixture.append('assistant', f'step {index} ' + 'y' * 900)
        newest = self.client.read(fixture.thread_id)
        self.assertLess(len(json.dumps(newest['turns'])), transport.PAGE_BYTES + 2000)
        self.assertEqual(newest['turns'][0]['items'][0]['message']['content'][:9], 'step 119 ')
        self.assertTrue(newest['has_more_older'])
        # Walking back reaches the first record with no gap and no repeat.
        seen, cursor = [turn['id'] for turn in newest['turns']], newest['next_cursor']
        while cursor:
            page = self.client.read(fixture.thread_id, cursor=cursor)
            seen += [turn['id'] for turn in page['turns']]
            cursor = page['next_cursor']
        self.assertEqual((len(seen), len(set(seen))), (121, 121))
        # Reading on from the newest point returns only what was added, oldest first, a page at a time.
        self.assertEqual(self.client.read(fixture.thread_id, cursor=newest['newer_cursor'])['turns'], [])
        for index in range(60):
            fixture.append('assistant', f'later {index} ' + 'z' * 900)
        added, cursor, rounds = [], newest['newer_cursor'], 0
        while True:
            page = self.client.read(fixture.thread_id, cursor=cursor, sort_direction='asc')
            added += [turn['items'][0]['message']['content'].split(' y')[0].split(' z')[0] for turn in page['turns']]
            cursor, rounds = page['newer_cursor'], rounds + 1
            if not page['has_more_newer']:
                break
        self.assertEqual(added, [f'later {index}' for index in range(60)])
        self.assertGreater(rounds, 1)

    def test_incomplete_ambiguous_and_wrong_root_history_never_establish_absence(self):
        fixture = self.fixture
        event = str(uuid.uuid4())
        original = fixture.history.read_bytes()
        fixture.history.write_bytes(original + b'{"type":')
        with self.assertRaises(transport.DeliveryError) as error:
            self.client.reconcile(fixture.thread_id, event)
        self.assertTrue(error.exception.uncertain)
        fixture.history.write_bytes(original + b'broken\n')
        with self.assertRaises(transport.DeliveryError):
            self.client.read(fixture.thread_id)
        fixture.history.write_bytes(original)
        duplicate = fixture.project.parent / 'other' / fixture.history.name
        duplicate.parent.mkdir()
        duplicate.write_bytes(original)
        duplicate.chmod(0o600)
        with self.assertRaisesRegex(transport.DeliveryError, 'ambiguous'):
            self.client.reconcile(fixture.thread_id, event)
        duplicate.rename(duplicate.with_suffix('.saved'))
        worker = fixture.project / fixture.thread_id / 'subagents' / 'agent-foreign.jsonl'
        fixture.append('assistant', 'Wrong root', path=worker, sessionId=str(uuid.uuid4()))
        listed = self.client.read(fixture.thread_id)['workers']
        self.assertEqual([(entry['id'], 'another session' in entry['refused']) for entry in listed], [('agent-foreign', True)])
        self.assertNotIn('Wrong root', json.dumps(listed))
        fixture.history.rename(fixture.history.with_suffix('.saved'))
        with self.assertRaises(transport.DeliveryError) as error:
            self.client.reconcile(fixture.thread_id, event)
        self.assertTrue(error.exception.uncertain)

    def test_stale_identity_unsupported_runtime_and_socket_symlink_refuse_before_write(self):
        fixture = self.fixture
        fixture.record['procStart'] = '0'
        fixture.write_registry()
        with self.assertRaisesRegex(transport.DeliveryError, 'start identity') as error:
            self.client.send(fixture.thread_id, str(uuid.uuid4()), 'Continue')
        self.assertFalse(error.exception.uncertain)
        fixture.record['procStart'] = transport.NativeTransport._proc_start(os.getpid())
        fixture.record['version'] = '9.9.9'
        fixture.write_registry()
        self.assertFalse(self.client.metadata(fixture.thread_id)['versionMeasured'])
        fixture.record['peerProtocol'] = 2
        fixture.write_registry()
        with self.assertRaisesRegex(transport.DeliveryError, 'unsupported Claude peer protocol'):
            self.client.send(fixture.thread_id, str(uuid.uuid4()), 'Continue')
        fixture.record.update(version='2.1.296', peerProtocol=1)
        alias = fixture.root / 'alias.sock'
        alias.symlink_to(fixture.socket_path)
        fixture.record['messagingSocketPath'] = str(alias)
        fixture.write_registry()
        with self.assertRaisesRegex(transport.DeliveryError, 'symlink'):
            self.client.send(fixture.thread_id, str(uuid.uuid4()), 'Continue')
        self.assertEqual(fixture.frames, [])
        other_socket = fixture.root / 'other.sock'
        code = ('import socket,sys,os; s=socket.socket(socket.AF_UNIX); '
                's.bind(sys.argv[1]); os.chmod(sys.argv[1],0o600); s.listen(); '
                'print("ready",flush=True); sys.stdin.read()')
        process = subprocess.Popen([sys.executable, '-c', code, str(other_socket)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'ready')
            fixture.record['messagingSocketPath'] = str(other_socket)
            fixture.write_registry()
            with self.assertRaisesRegex(transport.DeliveryError, 'connected inbox process identity') as error:
                self.client.send(fixture.thread_id, str(uuid.uuid4()), 'Continue')
            self.assertFalse(error.exception.uncertain)
        finally:
            process.communicate(timeout=5)


class ClaudeObservationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ClaudeFixture()
        self.addCleanup(self.fixture.close)
        self.client = self.fixture.client()

    def test_state_turns_messages_and_queue_come_from_the_registry_and_the_history(self):
        fixture, thread = self.fixture, self.fixture.thread_id
        first = fixture.human('Write the report', 1)
        fixture.model('msg_1', (2, 100, 1000, 50))
        fixture.tool()
        fixture.status('busy')
        seen = self.client.observe(thread)
        self.assertEqual((seen['status'], seen['flags'], seen['queue'], seen['unknown']), ('active', [], [], []))
        self.assertEqual([(turn['id'], turn['status']) for turn in seen['turns']], [(first, 'inProgress')])
        self.assertEqual([(m['id'], m['turn_id'], m['text'], m['inter_agent'], m['client_id']) for m in seen['messages']],
                         [(first, first, 'Write the report', False, None)])
        # A kit message sent while the turn runs is queued, then read inside the turn as an attachment.
        event = str(uuid.uuid4())
        self.client.send(thread, event, 'Report the state', allow_busy=True)
        self.assertTrue(fixture.received.wait(2))
        frame = fixture.frames[0]
        fixture.queue('enqueue', frame['message']['content'])
        queued = self.client.observe(thread, cursor=seen['cursor'])
        self.assertEqual([entry['client_id'] for entry in queued['queue']], [event])
        self.assertEqual((queued['turns'], queued['messages']), ([{'id': first, 'status': 'inProgress', 'started_at': queued['turns'][0]['started_at'], 'completed_at': None}], []))
        fixture.queue('remove', frame['message']['content'], reason='absorbed_mid_turn')
        fixture.write({'type': 'attachment', 'attachment': {'type': 'queued_command', 'prompt': frame['message']['content'], 'source_uuid': 'cmd-1',
                                                             'origin': {'kind': 'peer', 'from': 'unknown', 'msg_id': event, 'name': 'ai-kit-supervisor'}}})
        read = self.client.observe(thread, cursor=queued['cursor'])
        self.assertEqual(read['queue'], [])
        self.assertEqual([(m['id'], m['client_id'], m['turn_id'], m['inter_agent']) for m in read['messages']], [('cmd-1', event, first, True)])
        self.assertEqual(self.client.reconcile(thread, event)['status'], 'delivered')
        # The turn ends in the history; the registry then says the session rests.
        fixture.model('msg_2', (1, 0, 2000, 20), stop='end_turn')
        fixture.status('idle')
        done = self.client.observe(thread, cursor=read['cursor'])
        self.assertEqual((done['status'], [(turn['id'], turn['status']) for turn in done['turns']]), ('idle', [(first, 'completed')]))
        self.assertEqual(self.client.observe(thread, cursor=done['cursor'])['turns'], [])
        # A task notification starts a turn of its own and is not the operator's message.
        fixture.write({'type': 'user', 'uuid': 'note-1', 'message': {'role': 'user', 'content': 'background task finished'},
                       'origin': {'kind': 'task-notification'}, 'turnOrigin': 'task_notification', 'turnPosition': {'promptIndex': 1, 'turnIndex': 2}})
        fixture.status('waiting', 'permission prompt')
        waiting = self.client.observe(thread, cursor=done['cursor'])
        self.assertEqual((waiting['status'], waiting['flags']), ('active', ['waitingOnApproval']))
        self.assertEqual([(m['id'], m['inter_agent']) for m in waiting['messages']], [('note-1', True)])
        self.assertEqual([(turn['id'], turn['status']) for turn in waiting['turns']], [('note-1', 'inProgress')])
        fixture.write({'type': 'user', 'interruptedMessageId': 'msg_3', 'message': {'role': 'user', 'content': [{'type': 'text', 'text': '[Request interrupted by user]'}]}})
        fixture.status('shell')
        resting = self.client.observe(thread, cursor=waiting['cursor'])
        self.assertEqual((resting['status'], resting['flags']), ('idle', ['backgroundShell']))
        self.assertEqual([(turn['id'], turn['status']) for turn in resting['turns']], [('note-1', 'interrupted')])
        self.assertEqual(self.client.metadata(thread)['status']['type'], 'idle')

    def test_a_removal_recorded_with_another_text_still_empties_the_queue_and_keeps_the_kit_entry(self):
        fixture, thread = self.fixture, self.fixture.thread_id
        event = str(uuid.uuid4())
        fixture.human('Write the report', 1)
        fixture.status('busy')
        fixture.queue('enqueue', '<cross-session-message from="uds:/run/x.sock" from-name="peer">\nhello\n</cross-session-message>')
        fixture.queue('enqueue', transport.NativeTransport._envelope(event, 'Report the state'))
        fixture.queue('enqueue', 'a task notification')
        seen = self.client.observe(thread)
        self.assertEqual([entry['client_id'] for entry in seen['queue']], [None, event, None])
        # The client records the removal of the peer message with a rewritten text, and of the notification with its own.
        fixture.queue('remove', '<cross-session-message from-name="peer">\nhello\n</cross-session-message>', reason='absorbed_mid_turn')
        fixture.queue('remove', 'a task notification', reason='delivered_to_agent')
        left = self.client.observe(thread, cursor=seen['cursor'])
        self.assertEqual([entry['client_id'] for entry in left['queue']], [event])
        fixture.queue('remove', 'the kit message, rewritten: ' + transport.MARKER + event, reason='absorbed_mid_turn')
        self.assertEqual(self.client.observe(thread, cursor=left['cursor'])['queue'], [])
        self.assertEqual(self.client.observe(thread)['queue'], [])

    def test_the_sessions_own_held_events_are_not_a_queue_and_a_dequeue_removes_what_the_next_turn_reads(self):
        fixture, thread = self.fixture, self.fixture.thread_id
        note = '<task-notification>\n<task-id>t1</task-id>\n<status>completed</status>\n</task-notification>'
        fixture.human('Write the report', 1)
        fixture.model('msg_1', (1, 0, 10, 1), stop='end_turn')
        # The client holds a notification of the session's own task while the session rests: it delays no message.
        fixture.queue('enqueue', note)
        fixture.queue('enqueue', '<agent-message from="worker">report</agent-message>')
        fixture.status('idle')
        resting = self.client.observe(thread)
        self.assertEqual((resting['status'], resting['queue'], resting['unknown']), ('idle', [], []))
        # A kit message arrives at rest: queued, dequeued, and read as the start of a turn. It is not left in the queue.
        event = str(uuid.uuid4())
        envelope = transport.NativeTransport._envelope(event, 'Report the state')
        fixture.queue('enqueue', envelope)
        fixture.queue('dequeue')
        fixture.write({'type': 'user', 'isMeta': True, 'message': {'role': 'user', 'content': 'Another Claude session sent a message:\n' + envelope},
                       'origin': {'kind': 'peer', 'from': 'unknown', 'msg_id': event, 'name': 'ai-kit-supervisor'},
                       'turnOrigin': 'peer', 'turnPosition': {'promptIndex': 1, 'turnIndex': 2}})
        fixture.status('busy')
        working = self.client.observe(thread, cursor=resting['cursor'])
        self.assertEqual((working['queue'], [message['client_id'] for message in working['messages']]), ([], [event]))
        self.assertEqual(self.client.observe(thread)['queue'], [])
        # The held events are folded into the turn; a message a human types meanwhile is a queue entry until it is read.
        fixture.queue('enqueue', 'and also update the index')
        fixture.queue('remove', note, reason='absorbed_mid_turn')
        typed = self.client.observe(thread, cursor=working['cursor'])
        self.assertEqual([entry['client_id'] for entry in typed['queue']], [None])
        # A record that never shows the entry leaving cannot block a session that came to rest after it was queued.
        fixture.model('msg_2', (1, 0, 10, 1), stop='end_turn')
        fixture.status('idle')
        rested = self.client.observe(thread, cursor=typed['cursor'])
        self.assertEqual(rested['queue'], [])
        # An entry queued after the registry was last written is kept: the registry may not have caught up yet.
        fixture.record['statusUpdatedAt'] = int(time.time() * 1000) - 60000
        fixture.write_registry()
        fixture.queue('enqueue', 'typed after the registry was last written')
        self.assertEqual(len(self.client.observe(thread, cursor=rested['cursor'])['queue']), 1)

    def test_the_counter_counts_each_model_message_once_and_follows_the_file(self):
        fixture, thread = self.fixture, self.fixture.thread_id
        fixture.human('Write the report', 1)
        fixture.model('msg_1', (2, 100, 1000, 50), records=3)
        seen = self.client.observe(thread)
        self.assertEqual({key: seen['usage'][key] for key in transport.USAGE}, {'total': 1152, 'input': 1102, 'cached_input': 1000, 'output': 50})
        fixture.model('msg_1', (2, 100, 1000, 50))
        fixture.model('msg_2', (0, 0, 3000, 10))
        later = self.client.observe(thread, cursor=seen['cursor'])
        self.assertEqual((later['usage']['total'], later['usage']['cached_input']), (1152 + 3010, 4000))
        self.assertEqual(self.client.observe(thread)['usage']['total'], later['usage']['total'])
        self.assertIsNone(later['allowance'])
        # Workers are the session's subagent files; one that ended before the task spent nothing in it.
        directory = fixture.project / thread / 'subagents'
        old = directory / 'agent-old.jsonl'
        new = directory / 'workflows' / 'wf_1' / 'agent-new.jsonl'
        for path, tokens in ((old, (0, 0, 500, 5)), (new, (0, 10, 700, 7))):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'type': 'assistant', 'isSidechain': True, 'timestamp': stamp(), 'message': {'id': 'w', 'usage': {
                'input_tokens': tokens[0], 'cache_creation_input_tokens': tokens[1], 'cache_read_input_tokens': tokens[2], 'output_tokens': tokens[3]}}}) + '\n')
        os.utime(old, (time.time() - 7200, time.time() - 7200))
        self.assertEqual(self.client.observe(thread)['workers'], [])
        workers = self.client.observe(thread, workers_since=time.time() - 3600)['workers']
        self.assertEqual([(worker['id'], worker['usage']['total']) for worker in workers], [(thread + '/workflows/wf_1/agent-new', 717)])
        self.assertIsNotNone(workers[0]['created_at'])

    def test_first_reading_keeps_the_recent_turns_and_an_older_message_needs_a_longer_scan(self):
        fixture, thread = self.fixture, self.fixture.thread_id
        idents = []
        for index in range(1, 6):
            idents.append(fixture.human(f'request {index}', index))
            fixture.model(f'msg_{index}', (1, 0, 10, 1), stop='end_turn')
        seen = self.client.observe(thread, history_turns=2)
        self.assertEqual([turn['id'] for turn in seen['turns']], idents[-2:])
        self.assertEqual([message['text'] for message in seen['messages']], ['request 4', 'request 5'])
        self.assertEqual(len(self.client.observe(thread, history_turns=30)['messages']), 5)
        self.assertEqual(seen['usage']['total'], 60)

    def test_a_session_that_is_gone_is_not_loaded_and_one_with_no_history_reads_zero(self):
        fixture, thread = self.fixture, self.fixture.thread_id
        fixture.human('Write the report', 1)
        fixture.model('msg_1', (1, 0, 10, 1))
        fixture.queue('enqueue', 'still queued when the process went away')
        fixture.records.clear()
        fixture.write_discovery()
        gone = self.client.observe(thread)
        self.assertEqual((gone['status'], gone['queue'], gone['can_accept_input']), ('notLoaded', [], False))
        self.assertEqual((gone['turns'][-1]['status'], gone['usage']['total']), ('interrupted', 12))
        with self.assertRaisesRegex(transport.DeliveryError, 'unavailable'):
            self.client.metadata(thread)
        with self.assertRaisesRegex(transport.DeliveryError, 'neither live nor recorded'):
            self.client.observe(str(uuid.uuid4()))
        fixture.records.append(fixture.record)
        fixture.write_discovery()
        fixture.history.unlink()
        empty = self.client.observe(thread)
        self.assertEqual((empty['status'], empty['turns'], empty['messages'], empty['queue'], empty['usage']['total'], empty['unknown']),
                         ('idle', [], [], [], 0, []))

    def test_the_stop_is_a_message_with_priority_now_and_the_inbox_key_opens_the_connection(self):
        fixture, thread = self.fixture, self.fixture.thread_id
        key = fixture.sessions / f'{os.getpid()}.0123abcd.key'
        key.write_text(json.dumps({'peerToken': 'secret-token', 'procStart': fixture.record['procStart']}))
        key.chmod(0o600)
        fixture.status('busy')
        event = str(uuid.uuid4())
        self.assertTrue(self.client.interrupt_is_message)
        result = self.client.interrupt(thread, 'turn-1', event, 'Stop: the ceiling is reached')
        self.assertEqual((result['status'], result['event_id'], result['acknowledged']), ('interrupted', event, False))
        self.assertTrue(fixture.received.wait(2))
        self.assertEqual(fixture.auths, [{'type': 'auth', 'token': 'secret-token'}])
        frame = fixture.frames[0]
        self.assertEqual((frame['priority'], frame['msg_id'], frame['session_id']), ('now', event, thread))
        self.assertIn('Stop: the ceiling is reached', frame['message']['content'])
        with self.assertRaisesRegex(transport.DeliveryError, 'busy'):
            self.client.send(thread, str(uuid.uuid4()), 'A wake waits for a resting supervisor')
        fixture.status('shell')
        self.assertEqual(self.client.send(thread, str(uuid.uuid4()), 'A wake reaches a supervisor whose shell still runs')['status'], 'uncertain')


if __name__ == '__main__':
    unittest.main()
