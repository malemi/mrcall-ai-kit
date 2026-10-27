import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'claude/supervision/transport.py'
spec = importlib.util.spec_from_file_location('claude_transport', SOURCE)
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


class ClaudeFixture:
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
        self.stopped = threading.Event()
        self.received = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()
        self.record = {'pid': os.getpid(), 'sessionId': self.thread_id, 'cwd': str(self.root),
                       'status': 'idle', 'version': '2.1.296', 'peerProtocol': 1,
                       'procStart': transport.NativeTransport._proc_start(os.getpid()),
                       'messagingSocketPath': str(self.socket_path)}
        self.registry = self.sessions / f'{os.getpid()}.json'
        self.write_registry()
        self.executable = self.root / 'claude'
        self.discovery = self.root / 'agents.json'
        self.discovery.write_text(json.dumps([self.record]))
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
                if data:
                    self.frames.append(json.loads(data))
                    self.received.set()

    def write_registry(self):
        self.registry.write_text(json.dumps(self.record))
        self.registry.chmod(0o664)

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
        self.assertEqual((frame['msgV'], frame['msg_id'], frame['priority']), (1, event, 'next'))
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
        self.assertIn(output, first['turns'][-1]['items'][0]['message']['content'][0]['content'])
        self.assertNotIn('PRIVATE', serialized)
        self.assertEqual(first['workers'][0]['parentThreadId'], fixture.thread_id)
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
        with self.assertRaisesRegex(transport.DeliveryError, 'identity mismatch'):
            self.client.read(fixture.thread_id)
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
        fixture.record['version'] = '0.0.0'
        fixture.write_registry()
        with self.assertRaisesRegex(transport.DeliveryError, 'unsupported'):
            self.client.send(fixture.thread_id, str(uuid.uuid4()), 'Continue')
        fixture.record['version'] = '2.1.296'
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


if __name__ == '__main__':
    unittest.main()
