import concurrent.futures
import gzip
import http.client
import json
import select
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from auto_av_trial_guard import Budget, Relay


class GuardTests(unittest.TestCase):
    def test_reviewed_recovery_ceiling(self):
        self.assertEqual(Budget(27).limit, 27)
        with self.assertRaises(ValueError):
            Budget(28)

    def setUp(self):
        self.calls = []
        calls = self.calls
        self.paths = []
        paths = self.paths
        self.encodings = []
        encodings = self.encodings
        self.cancelled = threading.Event()
        cancelled = self.cancelled

        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                calls.append(json.loads(body))
                paths.append(self.path)
                encodings.append(self.headers.get('Accept-Encoding'))
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                if json.loads(body).get('gzip'):
                    self.send_header('Content-Encoding', 'gzip')
                self.end_headers()
                try:
                    if json.loads(body).get('gzip'):
                        self.wfile.write(gzip.compress(b'data: done\n\n', mtime=0))
                        self.wfile.flush()
                        return
                    if json.loads(body).get('slow'):
                        self.wfile.write(b'data: first\n\n')
                        self.wfile.flush()
                        end = time.monotonic() + .5
                        while time.monotonic() < end:
                            ready, _, _ = select.select([self.connection], [], [], .01)
                            if ready and self.connection.recv(1, socket.MSG_PEEK) == b'':
                                cancelled.set()
                                return
                    self.wfile.write(b'data: done\n\n')
                    self.wfile.flush()
                except OSError:
                    pass

        self.upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        self.upstream.daemon_threads = True
        self.thread = threading.Thread(target=self.upstream.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.upstream.server_port)

    def tearDown(self):
        self.upstream.shutdown()
        self.upstream.server_close()
        self.thread.join(1)

    def request(self, relay, body, path='/v1/responses', headers=None, method='POST'):
        conn = http.client.HTTPConnection('127.0.0.1', relay._server.server_port, timeout=2)
        conn.request(method, path, json.dumps(body), headers or {})
        response = conn.getresponse()
        result = (response.status, response.read())
        conn.close()
        return result

    def test_case_limit_and_sse(self):
        with Relay(self.url, case_limit=2) as relay:
            self.assertEqual(self.request(relay, {'n': 1}), (200, b'data: done\n\n'))
            self.assertEqual(self.request(relay, {'n': 2})[0], 200)
            self.assertEqual(self.request(relay, {'n': 3})[0], 429)
            self.assertEqual(len(self.calls), 2)

    def test_final_recovery_four_request_ceiling(self):
        budget = Budget(27)
        budget.used = 21
        with Relay(self.url, budget, case_limit=4) as relay:
            for n in range(4):
                self.assertEqual(self.request(relay, {'n': n})[0], 200)
            self.assertEqual(self.request(relay, {'n': 4})[0], 429)
            self.assertEqual(budget.used, 25)
            self.assertEqual(len(self.calls), 4)

    def test_duplicate_canonical_body(self):
        with Relay(self.url) as relay:
            self.assertEqual(self.request(relay, {'a': 1, 'b': 2})[0], 200)
            self.assertEqual(self.request(relay, {'b': 2, 'a': 1})[0], 429)
            self.assertEqual(len(self.calls), 1)

    def test_aux_and_websocket_never_forward(self):
        with Relay(self.url) as relay:
            self.assertEqual(self.request(relay, {}, '/v1/models')[0], 403)
            self.assertEqual(self.request(relay, {}, headers={'Upgrade': 'websocket', 'Connection': 'Upgrade'}, method='GET')[0], 403)
            self.assertEqual(self.calls, [])
            self.assertEqual(relay.used, 0)

    def test_atomic_global_budget(self):
        budget = Budget(3)
        with Relay(self.url, budget) as one, Relay(self.url, budget) as two:
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                statuses = list(pool.map(lambda n: self.request(one if n % 2 else two, {'n': n})[0], range(8)))
            self.assertEqual(statuses.count(200), 3)
            self.assertEqual(budget.used, 3)
            self.assertEqual(len(self.calls), 3)

    def test_deadline_cancels_stream(self):
        with Relay(self.url, deadline=.15) as relay:
            started = time.monotonic()
            self.assertEqual(self.request(relay, {'slow': True})[0], 200)
            self.assertLess(time.monotonic() - started, .45)
            self.assertTrue(any(x.get('reason') == 'deadline' for x in relay.ledger))
            self.assertTrue(self.cancelled.wait(.3))

    def test_disconnect_cancels_stream(self):
        with Relay(self.url) as relay:
            conn = http.client.HTTPConnection('127.0.0.1', relay._server.server_port)
            conn.request('POST', '/v1/responses', json.dumps({'slow': True}))
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            response.close()
            conn.close()
            end = time.monotonic() + .4
            while time.monotonic() < end and not any(x.get('reason') == 'disconnect' for x in relay.ledger):
                time.sleep(.01)
            self.assertTrue(any(x.get('reason') == 'disconnect' for x in relay.ledger))
            self.assertTrue(self.cancelled.wait(.3))

    def test_secret_absent_and_private_mapping(self):
        with Relay(self.url) as relay:
            private = relay.register_original(self.url + '/v1/messages')
            path = private[len(relay.baseurl):]
            self.assertEqual(self.request(relay, {'n': 1}, path, {'Authorization': 'Bearer PRIVATE_SECRET', 'x-api-key': 'PRIVATE_KEY'})[0], 200)
            evidence = json.dumps(relay.ledger)
            self.assertNotIn('PRIVATE', evidence)
            self.assertNotIn('Authorization', evidence)
            self.assertNotIn(path, evidence)
            with self.assertRaises(ValueError):
                relay.register_original('http://unregistered.invalid/v1/messages')

    def test_inbound_and_registered_queries_forward_without_evidence(self):
        with Relay(self.url) as relay:
            incoming = '/v1/responses?api-version=2026-10-01&secret=QUERY_SECRET%2Bencoded'
            self.assertEqual(self.request(relay, {'n': 1}, incoming)[0], 200)
            self.assertEqual(self.paths[-1], incoming)
            original = '/v1/messages?key=ORIGINAL_SECRET&api-version=2026-10-01'
            private = relay.register_original(self.url + original)
            private_path = private[len(relay.baseurl):]
            self.assertEqual(self.request(relay, {'n': 2}, private_path)[0], 200)
            self.assertEqual(self.paths[-1], original)
            self.assertEqual(self.request(relay, {'n': 3}, private_path + '?override=1')[0], 400)
            evidence = json.dumps(relay.ledger)
            for secret in ('QUERY_SECRET', 'ORIGINAL_SECRET', 'api-version', 'override', '?'):
                self.assertNotIn(secret, evidence)
            for invalid in (self.url + '/v1/messages#fragment', self.url.replace('http://', 'http://user:password@') + '/v1/messages'):
                with self.assertRaises(ValueError):
                    relay.register_original(invalid)

    def test_compressed_request_rejected_before_admission(self):
        with Relay(self.url) as relay:
            self.assertEqual(self.request(relay, {'n': 1}, headers={'Content-Encoding': 'gzip'})[0], 415)
            self.assertEqual(self.calls, [])
            self.assertEqual(relay.used, 0)
            self.assertEqual(relay.ledger[-1], {'kind': 'rejected', 'reason': 'content-encoding'})
            self.assertEqual(self.request(relay, {'n': 1}, headers={'Content-Encoding': 'identity'})[0], 200)

    def test_aggregate_output_and_evidence_cap(self):
        with Relay(self.url, response_cap=20, evidence_cap=100) as relay:
            self.assertEqual(self.request(relay, {'n': 1})[1], b'data: done\n\n')
            self.assertEqual(self.request(relay, {'n': 2})[1], b'')
            self.assertEqual(self.request(relay, {'n': 3})[0], 429)
            self.assertLessEqual(relay.output_bytes, 20)
            self.assertLessEqual(relay.evidence_bytes, 100)

    def test_capture_opt_in_completed_body_and_no_transport_secrets(self):
        with Relay(self.url) as relay:
            self.request(relay, {'n': 1})
            self.assertEqual(relay.captures, [])
        with Relay(self.url, capture=True) as relay:
            body = {'model': 'fixture', 'input': 'selector: APPLY', 'n': 2}
            status, response = self.request(relay, body, '/v1/responses?key=QUERY_SECRET',
                                            {'Authorization': 'HEADER_SECRET'})
            capture = relay.captures[0]
            self.assertEqual(capture['request'], body)
            self.assertEqual(capture['response'], response)
            self.assertEqual(capture['status'], status)
            self.assertTrue(capture['finished'])
            self.assertTrue(capture['finalized'])
            self.assertEqual(len(capture['hash']), 64)
            self.assertNotIn('QUERY_SECRET', repr(relay.captures))
            self.assertNotIn('HEADER_SECRET', repr(relay.captures))
            self.assertEqual(set(capture), {'hash', 'request', 'response', 'status', 'finished', 'finalized', 'content_encoding'})

    def test_capture_reserves_before_dispatch_and_bounds_requests(self):
        with Relay(self.url, capture=True, evidence_cap=10) as relay:
            self.assertEqual(self.request(relay, {'input': 'too long for evidence'})[0], 429)
            self.assertEqual(relay.used, 0)
            self.assertEqual(self.calls, [])
            self.assertEqual(relay.captures, [])
            self.assertLessEqual(relay.evidence_bytes, 10)
        with Relay(self.url, capture=True, deadline=.15) as relay:
            conn = http.client.HTTPConnection('127.0.0.1', relay._server.server_port)
            conn.request('POST', '/v1/responses', json.dumps({'slow': True}))
            response = conn.getresponse()
            self.assertEqual(len(relay.captures), 1)
            self.assertFalse(relay.captures[0]['finished'])
            self.assertFalse(relay.captures[0]['finalized'])
            response.read()
            conn.close()
            self.assertFalse(relay.captures[0]['finished'])
            self.assertTrue(relay.captures[0]['finalized'])
            self.assertLessEqual(sum(len(x['response']) for x in relay.captures), relay.response_cap)

    def test_capture_aggregate_evidence_reservation(self):
        with Relay(self.url, capture=True, evidence_cap=500) as relay:
            self.assertEqual(self.request(relay, {'input': 'x' * 80, 'n': 1})[0], 200)
            self.assertEqual(self.request(relay, {'input': 'x' * 80, 'n': 2})[0], 429)
            self.assertEqual(len(relay.captures), 1)
            self.assertEqual(len(self.calls), 1)
            self.assertLessEqual(relay.evidence_bytes, 500)

    def test_capture_overflow_stays_unfinished(self):
        with Relay(self.url, capture=True, response_cap=15) as relay:
            self.request(relay, {'slow': True})
            self.assertFalse(relay.captures[0]['finished'])
            self.assertTrue(relay.captures[0]['finalized'])
            self.assertLessEqual(len(relay.captures[0]['response']), 15)

    def test_default_gzip_forwarding_preserves_client_accept_encoding(self):
        with Relay(self.url) as relay:
            conn = http.client.HTTPConnection('127.0.0.1', relay._server.server_port)
            conn.request('POST', '/v1/responses', json.dumps({'gzip': True}),
                         {'Accept-Encoding': 'gzip'})
            response = conn.getresponse()
            self.assertEqual(response.getheader('Content-Encoding'), 'gzip')
            self.assertEqual(response.read(), gzip.compress(b'data: done\n\n', mtime=0))
            conn.close()
            self.assertEqual(self.encodings[-1], 'gzip')
            self.assertEqual(relay.captures, [])

    def test_capture_requests_identity_and_preserves_ignored_gzip_response(self):
        with Relay(self.url, capture=True) as relay:
            status, body = self.request(relay, {'gzip': True}, headers={'accept-encoding': 'gzip, br'})
            self.assertEqual(status, 200)
            self.assertEqual(self.encodings[-1], 'identity')
            self.assertEqual(body, gzip.compress(b'data: done\n\n', mtime=0))
            capture = relay.captures[0]
            self.assertEqual(capture['content_encoding'], 'gzip')
            self.assertEqual(capture['response'], body)
            self.assertTrue(capture['finished'])
            self.assertTrue(capture['finalized'])
            self.assertEqual(relay.output_bytes, len(body))
            self.assertLessEqual(sum(len(x['response']) for x in relay.captures), relay.response_cap)
            self.request(relay, {'plain': True}, headers={'Accept-Encoding': 'gzip'})
            self.assertEqual(self.encodings[-1], 'identity')
            self.assertEqual(relay.captures[-1]['content_encoding'], 'identity')

    def test_response_cap(self):
        with Relay(self.url, response_cap=15) as relay:
            status, body = self.request(relay, {'slow': True})
            self.assertEqual(status, 200)
            self.assertLessEqual(len(body), 15)
            self.assertTrue(any(x.get('reason') == 'response-cap' for x in relay.ledger))


if __name__ == '__main__':
    unittest.main()
