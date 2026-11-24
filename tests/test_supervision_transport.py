"""Actual Unix WebSocket protocol tests without model or business calls."""
import contextlib
import datetime
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import uuid
from websockets.sync.server import unix_serve

spec = importlib.util.spec_from_file_location('codex_supervision_transport', Path(__file__).resolve().parents[1] / 'codex/supervision/transport.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NativeTransport, DeliveryError = module.NativeTransport, module.DeliveryError


class RpcErrorResult:
    """Sentinel an override returns to make the fixture answer with a JSON-RPC error object."""

    def __init__(self, error):
        self.error = error


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.thread_id = str(uuid.uuid4())
        self.event = str(uuid.uuid4())
        self.calls = []
        self.mode = 'idle'
        self.accepted = []
        self.rollout_dir = self.root / 'sessions' / '2026' / '11' / '13'
        self.rollout_dir.mkdir(parents=True)
        self.rollout_path = self.rollout_dir / f'rollout-{self.thread_id}.jsonl'
        self.rollout_path.write_text('')

    def tearDown(self):
        self.temp.cleanup()

    def respond(self, method, params):
        if method == 'initialize':
            return {'userAgent': 'fixture'}
        if method == 'thread/read':
            return {'thread': {'id': self.thread_id, 'cwd': str(self.root), 'status': {'type': self.mode},
                               'parentThreadId': None, 'canAcceptDirectInput': True, 'path': str(self.rollout_path)}}
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
        if method == 'thread/items/list':
            return {'data': [
                {'turnId': params.get('turnId'), 'item': {'type': 'reasoning', 'id': 'r0', 'content': 'private'},
                 'startedAtMs': None},
                {'turnId': params.get('turnId'),
                 'item': {'type': 'userMessage', 'id': 'u0', 'clientId': self.event,
                          'content': [{'type': 'text', 'text': 'hi'}]}, 'startedAtMs': 1000}],
                    'nextCursor': None}
        if method == 'turn/interrupt':
            return {}
        raise AssertionError(method)

    @contextlib.contextmanager
    def server(self, override=None):
        path = self.root / 'control.sock'
        path.unlink(missing_ok=True)
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
                    if isinstance(result, RpcErrorResult):
                        ws.send(json.dumps({'id': request['id'], 'error': result.error}))
                    else:
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

    def test_observe_calls_only_read_methods(self):
        with self.server() as transport:
            transport.observe(self.thread_id)
            methods = {method for method, _ in self.calls}
            self.assertNotIn('thread/queue/add', methods)
            self.assertNotIn('turn/interrupt', methods)
            self.assertTrue(methods.issubset(
                {'initialize', 'thread/read', 'thread/queue/list', 'thread/turns/list', 'thread/items/list'}))

    def test_second_and_third_user_messages_returned_despite_summary(self):
        ids = [str(uuid.uuid4()) for _ in range(3)]
        def three_messages(method, params):
            if method == 'thread/turns/list':
                return {'data': [{'id': 'turn', 'status': 'completed', 'startedAt': 100, 'completedAt': 200}],
                        'nextCursor': None}
            if method == 'thread/items/list':
                return {'data': [
                    {'turnId': 'turn', 'item': {'type': 'userMessage', 'id': ids[0], 'clientId': ids[0],
                                                 'content': [{'type': 'text', 'text': 'first'}]}, 'startedAtMs': 100000},
                    {'turnId': 'turn', 'item': {'type': 'userMessage', 'id': ids[1], 'clientId': ids[1],
                                                 'content': [{'type': 'text', 'text': 'second'}]}, 'startedAtMs': 150000},
                    {'turnId': 'turn', 'item': {'type': 'userMessage', 'id': ids[2], 'clientId': ids[2],
                                                 'content': [{'type': 'text', 'text': 'third'}]}, 'startedAtMs': 180000},
                ], 'nextCursor': None}
            return self.respond(method, params)
        with self.server(three_messages) as transport:
            result = transport.observe(self.thread_id)
            self.assertEqual([m['text'] for m in result['messages']], ['first', 'second', 'third'])

    def test_anchor_sent_on_second_call_returns_only_newer_items(self):
        first_id, second_id = str(uuid.uuid4()), str(uuid.uuid4())
        state = {'phase': 1}
        def paged(method, params):
            if method == 'thread/turns/list':
                return {'data': [{'id': 'turn', 'status': 'inProgress', 'startedAt': 100, 'completedAt': None}],
                        'nextCursor': None}
            if method == 'thread/items/list':
                if state['phase'] == 1:
                    self.assertNotIn('cursor', params)
                    return {'data': [{'turnId': 'turn',
                                       'item': {'type': 'userMessage', 'id': first_id, 'clientId': first_id,
                                                'content': [{'type': 'text', 'text': 'one'}]},
                                       'startedAtMs': 1000}], 'nextCursor': None}
                self.assertEqual(params.get('cursor'), {'type': 'item', 'itemId': first_id})
                return {'data': [{'turnId': 'turn',
                                   'item': {'type': 'userMessage', 'id': second_id, 'clientId': second_id,
                                            'content': [{'type': 'text', 'text': 'two'}]},
                                   'startedAtMs': 2000}], 'nextCursor': None}
            return self.respond(method, params)
        with self.server(paged) as transport:
            first = transport.observe(self.thread_id)
            self.assertEqual([m['id'] for m in first['messages']], [first_id])
            state['phase'] = 2
            second = transport.observe(self.thread_id, cursor=first['cursor'])
            self.assertEqual([m['id'] for m in second['messages']], [second_id])

    def test_anchor_refusal_falls_back_to_full_read(self):
        anchor_id, full_id = str(uuid.uuid4()), str(uuid.uuid4())
        def refusing(method, params):
            if method == 'thread/turns/list':
                return {'data': [{'id': 'turn', 'status': 'inProgress', 'startedAt': 100, 'completedAt': None}],
                        'nextCursor': None}
            if method == 'thread/items/list':
                if 'cursor' in params:
                    return RpcErrorResult({'code': -32602,
                                            'message': 'cursor.itemId does not identify an item in the requested history scope'})
                return {'data': [{'turnId': 'turn',
                                   'item': {'type': 'userMessage', 'id': full_id, 'clientId': full_id,
                                            'content': [{'type': 'text', 'text': 'full'}]},
                                   'startedAtMs': 500}], 'nextCursor': None}
            return self.respond(method, params)
        with self.server(refusing) as transport:
            result = transport.observe(self.thread_id,
                                        cursor={'closed_turn': None, 'open': {'turn': anchor_id},
                                                'rollout': {}, 'workers': {}})
            self.assertEqual([m['id'] for m in result['messages']], [full_id])

    def test_open_turn_then_completed_advances_closed_turn(self):
        state = {'status': 'inProgress'}
        def turning(method, params):
            if method == 'thread/turns/list':
                return {'data': [{'id': 'turn', 'status': state['status'], 'startedAt': 100,
                                   'completedAt': None if state['status'] == 'inProgress' else 200}],
                        'nextCursor': None}
            if method == 'thread/items/list':
                return {'data': [], 'nextCursor': None}
            return self.respond(method, params)
        with self.server(turning) as transport:
            first = transport.observe(self.thread_id)
            self.assertEqual(first['turns'][0]['status'], 'inProgress')
            self.assertIsNone(first['cursor']['closed_turn'])
            state['status'] = 'completed'
            second = transport.observe(self.thread_id, cursor=first['cursor'])
            self.assertEqual(second['turns'][0]['status'], 'completed')
            self.assertEqual(second['cursor']['closed_turn'], 'turn')

    def test_queue_entry_reported(self):
        client_id = str(uuid.uuid4())
        def queued(method, params):
            if method == 'thread/queue/list':
                return {'data': [{'id': 'q1', 'clientUserMessageId': client_id}], 'nextCursor': None}
            return self.respond(method, params)
        with self.server(queued) as transport:
            result = transport.observe(self.thread_id)
            self.assertEqual(result['queue'], [{'id': 'q1', 'client_id': client_id}])

    def test_failing_queue_list_marks_unknown_without_losing_other_values(self):
        def failing(method, params):
            if method == 'thread/queue/list':
                return RpcErrorResult({'code': -32000, 'message': 'queue unavailable'})
            return self.respond(method, params)
        with self.server(failing) as transport:
            result = transport.observe(self.thread_id)
            self.assertIsNone(result['queue'])
            self.assertIn('queue', result['unknown'])
            self.assertEqual(result['turns'][0]['status'], 'completed')
            self.assertTrue(any(m['text'] for m in result['messages']))

    def test_usage_and_allowance_read_then_only_appended_part(self):
        lines = [
            '{"timestamp":"2026-11-13T12:57:22.264Z","type":"session_meta","payload":'
            '{"session_id":"%(id)s","id":"%(id)s","timestamp":"2026-11-13T12:57:22.141Z",'
            '"cli_version":"0.169.0","source":"vscode","thread_source":"user"}}' % {'id': self.thread_id},
            '{"timestamp":"2026-11-13T15:34:59.046Z","type":"token_usage_record","payload":'
            '{"thread_id":"%(id)s","turn_id":"T","usage":{"input_tokens":10,"cached_input_tokens":4,'
            '"cache_write_input_tokens":0,"output_tokens":2,"reasoning_output_tokens":1,"total_tokens":12},'
            '"thread_token_usage":{"input_tokens":1000,"cached_input_tokens":400,"cache_write_input_tokens":0,'
            '"output_tokens":200,"reasoning_output_tokens":50,"total_tokens":1200}}}' % {'id': self.thread_id},
            '{"timestamp":"2026-11-13T15:34:59.052Z","type":"event_msg","payload":{"type":"token_count",'
            '"info":{"total_token_usage":{"total_tokens":1200}},"rate_limits":{"limit_id":"codex",'
            '"primary":{"used_percent":60.0,"window_minutes":10080,"resets_at":1794909929},"secondary":null,'
            '"plan_type":"pro"}}}',
        ]
        self.rollout_path.write_text('\n'.join(lines) + '\n')
        with self.server() as transport:
            first = transport.observe(self.thread_id)
            self.assertEqual(first['usage']['total'], 1200)
            self.assertEqual(first['allowance']['used_percent'], 60.0)
            offset_after_first = first['cursor']['rollout']['offset']
            self.assertEqual(offset_after_first, self.rollout_path.stat().st_size)

            extra = ('{"timestamp":"2026-11-13T16:00:00.000Z","type":"token_usage_record","payload":'
                     '{"thread_id":"%(id)s","turn_id":"T2","usage":{"input_tokens":1,"cached_input_tokens":0,'
                     '"cache_write_input_tokens":0,"output_tokens":1,"reasoning_output_tokens":0,"total_tokens":2},'
                     '"thread_token_usage":{"input_tokens":1500,"cached_input_tokens":400,"cache_write_input_tokens":0,'
                     '"output_tokens":300,"reasoning_output_tokens":50,"total_tokens":1800}}}\n') % {'id': self.thread_id}
            with open(self.rollout_path, 'a') as handle:
                handle.write(extra)
            second = transport.observe(self.thread_id, cursor=first['cursor'])
            self.assertEqual(second['usage']['total'], 1800)
            self.assertEqual(second['cursor']['rollout']['offset'], offset_after_first + len(extra.encode('utf-8')))

    def test_missing_rollout_path_gives_unknown_usage_never_zero(self):
        missing_path = str(self.rollout_dir / 'rollout-missing.jsonl')
        def missing(method, params):
            if method == 'thread/read':
                return {'thread': {'id': self.thread_id, 'cwd': str(self.root), 'status': {'type': self.mode},
                                   'parentThreadId': None, 'canAcceptDirectInput': True, 'path': missing_path}}
            return self.respond(method, params)
        with self.server(missing) as transport:
            result = transport.observe(self.thread_id)
            self.assertIsNone(result['usage'])
            self.assertIn('usage', result['unknown'])
            self.assertNotEqual(result['usage'], 0)

    def test_worker_rollout_discovered_and_foreign_root_excluded(self):
        worker_id, other_root = str(uuid.uuid4()), str(uuid.uuid4())
        worker_path = self.rollout_dir / f'rollout-{worker_id}.jsonl'
        other_path = self.rollout_dir / f'rollout-{other_root}.jsonl'
        worker_path.write_text(json.dumps({
            'timestamp': '2026-11-13T13:20:00.000Z', 'type': 'session_meta',
            'payload': {'session_id': self.thread_id, 'id': worker_id, 'parent_thread_id': self.thread_id,
                        'timestamp': '2026-11-13T13:20:00.000Z',
                        'source': {'subagent': {'thread_spawn': {'parent_thread_id': self.thread_id, 'depth': 1}}},
                        'thread_source': 'subagent'}}) + '\n')
        other_path.write_text(json.dumps({
            'timestamp': '2026-11-13T13:20:00.000Z', 'type': 'session_meta',
            'payload': {'session_id': other_root, 'id': worker_id, 'timestamp': '2026-11-13T13:20:00.000Z'}}) + '\n')
        with self.server() as transport:
            since = datetime.datetime(2026, 11, 13, 13, 0, tzinfo=datetime.timezone.utc).timestamp()
            result = transport.observe(self.thread_id, workers_since=since)
            self.assertEqual([w['id'] for w in result['workers']], [worker_id])

    def test_no_reasoning_item_text_in_result(self):
        def with_reasoning(method, params):
            if method == 'thread/items/list':
                return {'data': [
                    {'turnId': 'turn', 'item': {'type': 'reasoning', 'id': 'r1', 'content': 'SECRET REASONING'},
                     'startedAtMs': 100},
                    {'turnId': 'turn', 'item': {'type': 'userMessage', 'id': self.event, 'clientId': self.event,
                                                 'content': [{'type': 'text', 'text': 'public'}]},
                     'startedAtMs': 200}], 'nextCursor': None}
            return self.respond(method, params)
        with self.server(with_reasoning) as transport:
            result = transport.observe(self.thread_id)
            dumped = json.dumps(result, default=str)
            self.assertNotIn('SECRET REASONING', dumped)
            self.assertEqual([m['text'] for m in result['messages']], ['public'])

    def test_interrupt_sends_exact_ids_and_uncertain_ack_raises(self):
        turn_id = str(uuid.uuid4())
        with self.server() as transport:
            result = transport.interrupt(self.thread_id, turn_id)
            self.assertEqual(result, {'status': 'interrupted', 'thread_id': self.thread_id, 'turn_id': turn_id})
            self.assertEqual([p for m, p in self.calls if m == 'turn/interrupt'],
                              [{'threadId': self.thread_id, 'turnId': turn_id}])

        def lost(method, params):
            if method == 'turn/interrupt':
                return 'CLOSE'
            return self.respond(method, params)
        with self.server(lost) as transport:
            with self.assertRaises(DeliveryError) as caught:
                transport.interrupt(self.thread_id, turn_id)
            self.assertTrue(caught.exception.uncertain)


if __name__ == '__main__':
    unittest.main()
