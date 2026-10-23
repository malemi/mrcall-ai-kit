"""Test-only, bounded HTTP admission relay for native-client trials."""
import hashlib
import http.client
import json
import secrets
import select
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class Budget:
    def __init__(self, limit=24):
        if not 0 <= limit <= 27:
            raise ValueError('global limit must be between zero and the reviewed recovery ceiling of 27')
        self.limit = limit
        self.used = 0
        self.lock = threading.Lock()
        self.hashes = set()


class Relay:
    def __init__(self, upstream, budget=None, case_limit=6, deadline=90,
                 response_cap=2_000_000, evidence_cap=2_000_000, capture=False):
        if case_limit not in (2, 4, 6):
            raise ValueError('case_limit must be 2, 4 or 6')
        if not 0 < deadline <= 90 or not 0 < response_cap <= 2_000_000:
            raise ValueError('invalid trial bounds')
        if not 0 < evidence_cap <= 2_000_000:
            raise ValueError('invalid evidence cap')
        self.backends = dict(upstream) if isinstance(upstream, dict) else {'/': upstream}
        for prefix, target in self.backends.items():
            self._validate_target(target)
            if not prefix.startswith('/'):
                raise ValueError('backend prefixes must be absolute paths')
        self.budget = budget if budget is not None else Budget()
        self.case_limit = case_limit
        self.deadline = deadline
        self.response_cap = response_cap
        self.evidence_cap = evidence_cap
        self.used = 0
        self.ledger = []
        self.capture = capture
        self.captures = []
        self.evidence_bytes = 0
        self.output_bytes = 0
        self.output_exhausted = False
        self._private = {}
        self._connections = set()
        self._connections_lock = threading.Lock()
        self._server = None
        self._thread = None
        self._stop = threading.Event()
        self.baseurl = None

    @staticmethod
    def _validate_target(target, allow_query=False):
        parsed = urlsplit(target)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or (parsed.query and not allow_query) or parsed.fragment:
            raise ValueError('backend must be HTTP without credentials/fragments; construction URLs cannot contain query')

    def register_original(self, original_url):
        self._validate_target(original_url, allow_query=True)
        parsed = urlsplit(original_url)
        allowed = {(urlsplit(x).scheme, urlsplit(x).netloc) for x in self.backends.values()}
        if (parsed.scheme, parsed.netloc) not in allowed:
            raise ValueError('original URL origin was not registered at construction')
        path = '/_trial/' + secrets.token_urlsafe(32)
        self._private[path] = original_url
        return self.baseurl + path

    def _record(self, event):
        encoded = json.dumps(event, sort_keys=True).encode()
        with self.budget.lock:
            if self.evidence_bytes + len(encoded) <= self.evidence_cap:
                self.ledger.append(event)
                self.evidence_bytes += len(encoded)

    def start(self):
        if self._server is not None:
            return self.baseurl
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *args):
                pass

            def do_GET(self):
                self.run_request()

            def do_POST(self):
                self.run_request()

            def do_PUT(self):
                self.reject(403, 'unexpected-kind')

            do_DELETE = do_PUT
            do_PATCH = do_PUT
            do_CONNECT = do_PUT

            def reject(self, status, reason):
                owner._record({'kind': 'rejected', 'reason': reason})
                self.close_connection = True
                try:
                    self.send_response(status)
                    self.send_header('Content-Length', '0')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                except OSError:
                    pass

            def disconnected(self):
                try:
                    readable, _, _ = select.select([self.connection], [], [], 0)
                    return bool(readable) and self.connection.recv(1, socket.MSG_PEEK) == b''
                except OSError:
                    return True

            def run_request(self):
                conn = None
                response = None
                upstream_socket = None
                watcher = None
                finished = threading.Event()
                cancelled = threading.Event()
                capture = None
                normal_eof = False
                try:
                    if self.headers.get('Upgrade') or 'upgrade' in self.headers.get('Connection', '').lower():
                        return self.reject(403, 'websocket')
                    elapsed = time.monotonic() - owner.started
                    remaining = owner.deadline - elapsed
                    if remaining <= 0 or owner._stop.is_set():
                        return self.reject(408, 'deadline')
                    inbound = urlsplit(self.path)
                    path = inbound.path
                    target = owner._private.get(path)
                    if target is not None and inbound.query:
                        return self.reject(400, 'private-query')
                    if target is None:
                        for prefix in sorted(owner.backends, key=len, reverse=True):
                            if path.startswith(prefix):
                                target = owner.backends[prefix].rstrip('/') + '/' + path[len(prefix):].lstrip('/')
                                if inbound.query:
                                    target += '?' + inbound.query
                                break
                    if target is None:
                        return self.reject(403, 'backend')
                    target_parts = urlsplit(target)
                    if self.command != 'POST' or not target_parts.path.rstrip('/').endswith(('/responses', '/chat/completions', '/messages', '/complete', '/generate')):
                        return self.reject(403, 'unexpected-kind')
                    if self.headers.get('Content-Encoding', 'identity').strip().lower() != 'identity':
                        return self.reject(415, 'content-encoding')
                    if self.headers.get('Transfer-Encoding'):
                        return self.reject(400, 'transfer-encoding')
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= owner.response_cap:
                        return self.reject(413, 'request-size')
                    self.connection.settimeout(remaining)
                    body = self.rfile.read(length)
                    if len(body) != length:
                        return self.reject(400, 'body')
                    decoded = json.loads(body)
                    canonical = json.dumps(decoded, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
                    digest = hashlib.sha256(canonical).hexdigest()
                    capture_size = len(canonical) + 256
                    if self.disconnected():
                        return self.reject(400, 'disconnect')
                    reason = None
                    with owner.budget.lock:
                        if digest in owner.budget.hashes:
                            reason = 'duplicate'
                        elif owner.used >= owner.case_limit or owner.budget.used >= owner.budget.limit or owner.output_exhausted or owner.output_bytes >= owner.response_cap:
                            reason = 'budget'
                        elif owner.capture and owner.evidence_bytes + capture_size > owner.evidence_cap:
                            reason = 'capture-cap'
                        elif time.monotonic() - owner.started >= owner.deadline:
                            reason = 'deadline'
                        else:
                            owner.budget.hashes.add(digest)
                            owner.used += 1
                            owner.budget.used += 1
                            if owner.capture:
                                capture = {'hash': digest, 'request': decoded, 'response': b'',
                                           'status': None, 'finished': False, 'finalized': False,
                                           'content_encoding': 'identity'}
                                owner.captures.append(capture)
                                owner.evidence_bytes += capture_size
                    if reason:
                        return self.reject(429, reason)
                    owner._record({'kind': 'generation', 'hash': digest,
                                   'origin': target_parts.scheme + '://' + target_parts.netloc,
                                   'path': next(x for x in ('/chat/completions', '/responses', '/messages', '/complete', '/generate') if target_parts.path.rstrip('/').endswith(x))})
                    cls = http.client.HTTPSConnection if target_parts.scheme == 'https' else http.client.HTTPConnection
                    conn = cls(target_parts.hostname, target_parts.port, timeout=max(.001, owner.deadline - (time.monotonic() - owner.started)))
                    with owner._connections_lock:
                        owner._connections.add(conn)
                    excluded = {'host', 'connection', 'proxy-connection', 'transfer-encoding', 'content-length', 'upgrade'}
                    if owner.capture:
                        excluded.add('accept-encoding')
                    headers = {key: value for key, value in self.headers.items() if key.lower() not in excluded}
                    if owner.capture:
                        headers['Accept-Encoding'] = 'identity'
                    headers['Content-Length'] = str(len(body))
                    conn.connect()
                    upstream_socket = conn.sock

                    def watch():
                        while not finished.wait(.02):
                            reason = None
                            if owner._stop.is_set():
                                reason = 'shutdown'
                            elif self.disconnected():
                                reason = 'disconnect'
                            elif time.monotonic() - owner.started >= owner.deadline:
                                reason = 'deadline'
                            if reason:
                                cancelled.set()
                                owner._record({'kind': 'cancelled', 'reason': reason})
                                try:
                                    upstream_socket.shutdown(socket.SHUT_RDWR)
                                except OSError:
                                    pass
                                return

                    watcher = threading.Thread(target=watch, daemon=True)
                    watcher.start()
                    request_target = target_parts.path or '/'
                    if target_parts.query:
                        request_target += '?' + target_parts.query
                    conn.request('POST', request_target, body, headers)
                    response = conn.getresponse()
                    if capture is not None:
                        with owner.budget.lock:
                            capture['status'] = response.status
                            encoding = response.getheader('Content-Encoding', 'identity').strip().lower()
                            capture['content_encoding'] = encoding if encoding in ('identity', 'gzip', 'deflate', 'br', 'zstd') else 'unknown'
                    self.send_response(response.status)
                    for key, value in response.getheaders():
                        if key.lower() in ('content-type', 'content-encoding'):
                            self.send_header(key, value)
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.close_connection = True
                    total = 0
                    while not owner._stop.is_set():
                        if self.disconnected():
                            owner._record({'kind': 'cancelled', 'reason': 'disconnect'})
                            break
                        remaining = owner.deadline - (time.monotonic() - owner.started)
                        if remaining <= 0:
                            owner._record({'kind': 'cancelled', 'reason': 'deadline'})
                            break
                        chunk = response.read1(min(65536, owner.response_cap - total + 1))
                        if not chunk:
                            normal_eof = response.length in (None, 0)
                            break
                        total += len(chunk)
                        with owner.budget.lock:
                            overflow = owner.output_bytes + len(chunk) > owner.response_cap
                            if overflow:
                                owner.output_exhausted = True
                            else:
                                owner.output_bytes += len(chunk)
                                if capture is not None:
                                    capture['response'] += chunk
                        if overflow:
                            owner._record({'kind': 'cancelled', 'reason': 'response-cap'})
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (OSError, ValueError, http.client.HTTPException):
                    owner._record({'kind': 'cancelled', 'reason': 'deadline' if time.monotonic() - owner.started >= owner.deadline else 'transport'})
                    self.close_connection = True
                finally:
                    if upstream_socket is not None:
                        try:
                            upstream_socket.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                    if response is not None:
                        response.close()
                    finished.set()
                    if watcher is not None:
                        watcher.join(timeout=.2)
                    if conn is not None:
                        conn.close()
                        with owner._connections_lock:
                            owner._connections.discard(conn)
                    if capture is not None:
                        with owner.budget.lock:
                            capture['finished'] = normal_eof and not cancelled.is_set() and not owner._stop.is_set() and time.monotonic() - owner.started < owner.deadline
                            capture['finalized'] = True

        self.started = time.monotonic()
        self._server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self._server.daemon_threads = True
        self._server.block_on_close = False
        self.baseurl = 'http://127.0.0.1:' + str(self._server.server_port)
        self._thread = threading.Thread(target=self._server.serve_forever, kwargs={'poll_interval': .05}, daemon=True)
        self._thread.start()
        return self.baseurl

    def close(self):
        self._stop.set()
        with self._connections_lock:
            for conn in self._connections:
                if conn.sock:
                    try:
                        conn.sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                conn.close()
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=1)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.close()
