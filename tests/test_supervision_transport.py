"""Actual Unix WebSocket protocol tests without model or business calls."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import uuid
from websockets.sync.server import unix_serve

spec = importlib.util.spec_from_file_location('codex_supervision_transport', Path(__file__).resolve().parents[1] / 'codex/supervision/transport.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NativeTransport, DeliveryError = module.NativeTransport, module.DeliveryError


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.thread_id = str(uuid.uuid4())
        self.event = str(uuid.uuid4())
        self.calls = []
        self.mode = 'idle'
        self.accepted = []

    def tearDown(self):
        self.temp.cleanup()

    def respond(self, method, params):
        if method == 'initialize':
            return {'userAgent': 'fixture'}
        if method == 'thread/read':
            return {'thread': {'id': self.thread_id, 'cwd': str(self.root), 'status': {'type': self.mode},
                               'parentThreadId': None, 'canAcceptDirectInput': True}}
        if method == 'thread/queue/add':
            self.accepted.append(params)
            return {'queuedSubmission': {'id': str(uuid.uuid4()), 'clientUserMessageId': params['clientUserMessageId']}}
        if method == 'thread/queue/list':
            return {'data': [], 'nextCursor': None}
        if method == 'thread/turns/list':
            return {'data': [{'id': 'turn', 'status': 'completed', 'items': [
                {'type': 'reasoning', 'content': 'private'},
                {'type': 'userMessage', 'clientId': self.event, 'content': []},
                {'type': 'agentMessage', 'text': 'ACK'}]}], 'nextCursor': None}
        raise AssertionError(method)

    @contextlib.contextmanager
    def server(self, override=None):
        path = self.root / 'control.sock'
        def handler(ws):
            try:
                for raw in ws:
                    request = json.loads(raw)
                    if 'id' not in request:
                        continue
                    method, params = request['method'], request['params']
                    self.calls.append((method, params))
                    result = override(method, params) if override else self.respond(method, params)
                    if result == 'CLOSE':
                        ws.close()
                        return
                    ws.send(json.dumps({'method': 'notification', 'params': {}}))
                    ws.send(json.dumps({'id': request['id'], 'result': result}))
            except Exception:
                return
        with unix_serve(handler, str(path)) as server:
            path.chmod(0o600)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                yield NativeTransport(socket_path=str(path), timeout=2)
            finally:
                server.shutdown()
                thread.join(3)

    def test_busy_and_wrong_identity_do_not_submit(self):
        with self.server() as transport:
            self.mode = 'active'
            with self.assertRaises(DeliveryError) as caught:
                transport.send(self.thread_id, self.event, 'event')
            self.assertFalse(caught.exception.uncertain)
            with self.assertRaises(DeliveryError):
                transport.send(str(uuid.uuid4()), self.event, 'event')
            self.assertEqual(self.accepted, [])

    def test_explicit_intervention_can_queue_busy_and_delta_preserves_anchor(self):
        def delta(method, params):
            if method == 'thread/turns/list':
                self.assertEqual(params['sortDirection'], 'asc')
                self.assertEqual(params['cursor'], 'anchor')
                return {'data': [], 'nextCursor': 'newer-page', 'backwardsCursor': 'reverse'}
            return self.respond(method, params)
        with self.server(delta) as transport:
            self.mode = 'active'
            result = transport.send(self.thread_id, self.event, 'bounded intervention', allow_busy=True)
            self.assertEqual(result['status'], 'delivered')
            view = transport.read(self.thread_id, cursor='anchor', sort_direction='asc')
            self.assertEqual(view['next_cursor'], 'newer-page')
            self.assertEqual(view['reverse_cursor'], 'reverse')

    def test_lost_ack_is_uncertain_and_reconciles_from_history(self):
        def lost(method, params):
            if method == 'thread/queue/add':
                self.accepted.append(params)
                return 'CLOSE'
            return self.respond(method, params)
        with self.server(lost) as transport:
            with self.assertRaises(DeliveryError) as caught:
                transport.send(self.thread_id, self.event, 'event')
            self.assertTrue(caught.exception.uncertain)
            self.assertEqual(transport.reconcile(self.thread_id, self.event)['status'], 'delivered')
            self.assertEqual(len(self.accepted), 1)
            self.assertFalse(any(method == 'thread/queue/start' for method, _ in self.calls))

    def test_pagination_complete_before_absence_and_no_private_reasoning(self):
        def pages(method, params):
            if method == 'thread/queue/list' and 'cursor' not in params:
                return {'data': [], 'nextCursor': 'page2'}
            return self.respond(method, params)
        with self.server(pages) as transport:
            result = transport.reconcile(self.thread_id, str(uuid.uuid4()))
            self.assertEqual(result['status'], 'absent')
            self.assertTrue(result['absence_is_not_permission_to_resend'])
            self.assertTrue(any(p.get('cursor') == 'page2' for m, p in self.calls if m == 'thread/queue/list'))
            view = transport.read(self.thread_id)
            self.assertEqual([i['type'] for i in view['turns'][0]['items']], ['userMessage', 'agentMessage'])

    def test_stuck_cursor_never_claims_absence(self):
        def stuck(method, params):
            if method == 'thread/queue/list':
                return {'data': [], 'nextCursor': 'same'}
            return self.respond(method, params)
        with self.server(stuck) as transport:
            with self.assertRaises(DeliveryError) as caught:
                transport.reconcile(self.thread_id, self.event)
            self.assertTrue(caught.exception.uncertain)

    def test_large_history_read_and_reconciliation_preserve_complete_output(self):
        output = 'x' * (2 * 1024 * 1024)
        def large(method, params):
            if method == 'thread/turns/list':
                return {'data': [{'id': 'large-turn', 'status': 'completed', 'items': [
                    {'type': 'commandExecution', 'aggregatedOutput': output},
                    {'type': 'reasoning', 'content': 'private'},
                    {'type': 'userMessage', 'clientId': self.event, 'content': []}]}],
                    'nextCursor': None, 'backwardsCursor': 'large-anchor'}
            return self.respond(method, params)
        with self.server(large) as transport:
            transport.timeout = 10
            view = transport.read(self.thread_id)
            self.assertEqual(view['turns'][0]['items'][0]['aggregatedOutput'], output)
            self.assertEqual([i['type'] for i in view['turns'][0]['items']],
                             ['commandExecution', 'userMessage'])
            self.assertEqual(view['reverse_cursor'], 'large-anchor')
            self.assertIsNone(view['next_cursor'])
            result = transport.reconcile(self.thread_id, self.event)
            self.assertEqual(result['status'], 'delivered')
            self.assertEqual(result['turn_id'], 'large-turn')
            self.assertEqual(self.accepted, [])

    def test_history_above_finite_receive_ceiling_is_incomplete_not_absent(self):
        def oversized(method, params):
            if method == 'thread/turns/list':
                return {'data': [], 'padding': 'x' * (module.MAX_MESSAGE_BYTES + 1),
                        'nextCursor': None}
            return self.respond(method, params)
        with self.server(oversized) as transport:
            transport.timeout = 10
            for operation in (lambda: transport.read(self.thread_id),
                              lambda: transport.reconcile(self.thread_id, self.event)):
                with self.assertRaises(DeliveryError) as caught:
                    operation()
                self.assertIn('1009', str(caught.exception))
                self.assertEqual(self.accepted, [])

    def test_offline_or_public_socket_refuses_before_send(self):
        with self.assertRaises(DeliveryError) as caught:
            NativeTransport(socket_path=str(self.root / 'absent')).send(self.thread_id, self.event, 'event')
        self.assertFalse(caught.exception.uncertain)
        with self.server() as transport:
            (self.root / 'control.sock').chmod(0o666)
            with self.assertRaises(DeliveryError):
                transport.send(self.thread_id, self.event, 'event')
            self.assertEqual(self.calls, [])

    def test_discovery_preserves_permission_diagnostic(self):
        executable = self.root / 'codex-denied'
        executable.write_text('#!/bin/sh\necho "control socket: Operation not permitted" >&2\nexit 1\n')
        executable.chmod(0o700)
        with self.assertRaises(DeliveryError) as caught:
            NativeTransport(codex_path=str(executable)).metadata(self.thread_id)
        self.assertIn('Operation not permitted', str(caught.exception))
        self.assertFalse(caught.exception.uncertain)


if __name__ == '__main__':
    unittest.main()
