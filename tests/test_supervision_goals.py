import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid


SOURCE = Path(__file__).resolve().parents[1] / 'shared/supervision'
EVIDENCE = Path('/tmp/mrcall-ai-kit/persistent-goal-20261030/goal-acceptance')
AGENT_UID = 60001
VERIFIER_UID = 60002
WEBSOCKETS_SOURCE = Path(os.environ.get('AI_KIT_TEST_WEBSOCKETS_SOURCE', str(
    Path(pwd.getpwuid(int(os.environ.get('SUDO_UID', os.getuid()))).pw_dir) /
    f'.local/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages/websockets')))


class NativeGoalFixture:
    def __init__(self, path, lead, supervisor, package_parent, socket_uid=AGENT_UID):
        sys.path.insert(0, str(package_parent))
        from websockets.sync.server import unix_serve
        self.path = path
        self.identities = {lead: 'idle', supervisor: 'idle'}
        self.accepted = []
        self.completed = set()
        self.history_items = {}
        self.newer_turns = []
        self.calls = []
        self.drop_ack = False
        self.hide_pending = False
        self.metadata_barrier = None
        self.lock = threading.RLock()
        self.server = unix_serve(self.handle, str(path))
        if socket_uid != os.getuid():
            os.chown(path, socket_uid, socket_uid)
        path.chmod(0o600)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def handle(self, connection):
        try:
            for raw in connection:
                message = json.loads(raw)
                if 'id' not in message:
                    continue
                with self.lock:
                    method, params = message['method'], message.get('params', {})
                    self.calls.append((method, params))
                    if method == 'initialize':
                        result = {'userAgent': 'independent-goal-fixture'}
                    elif method == 'thread/read':
                        identity = params['threadId']
                        if self.metadata_barrier is not None and self.metadata_barrier[0] == identity:
                            self.metadata_barrier[1].set()
                            self.metadata_barrier[2].wait(timeout=5)
                        result = {'thread': {'id': identity, 'cwd': str(self.path.parent),
                                             'status': {'type': self.identities[identity]},
                                             'parentThreadId': None, 'canAcceptDirectInput': True}}
                    elif method == 'thread/queue/add':
                        self.accepted.append(params)
                        if self.drop_ack:
                            self.drop_ack = False
                            connection.close()
                            return
                        result = {'queuedSubmission': {'id': str(uuid.uuid4()),
                                                       'clientUserMessageId': params['clientUserMessageId']}}
                    elif method == 'thread/queue/list':
                        result = {'data': [] if self.hide_pending else [
                            {'id': item['clientUserMessageId'], 'clientUserMessageId': item['clientUserMessageId']}
                            for item in self.accepted if item['threadId'] == params['threadId']
                            and item['clientUserMessageId'] not in self.completed], 'nextCursor': None}
                    elif method == 'thread/turns/list':
                        turns = [
                            {'id': 'turn-' + item['clientUserMessageId'], 'status': 'completed',
                             'items': [{'type': 'userMessage', 'clientId': item['clientUserMessageId'], 'content': []},
                                       {'type': 'agentMessage', 'text': 'Fixture finished its bounded action'},
                                       *self.history_items.get(item['clientUserMessageId'], [])]}
                            for item in self.accepted if item['threadId'] == params['threadId']
                            and item['clientUserMessageId'] in self.completed]
                        if params.get('sortDirection') == 'desc':
                            turns.reverse()
                        result = {'data': self.newer_turns + turns, 'nextCursor': None}
                    else:
                        raise AssertionError(method)
                connection.send(json.dumps({'id': message['id'], 'result': result}))
        except Exception:
            return

    def finish_all(self):
        with self.lock:
            self.completed.update(item['clientUserMessageId'] for item in self.accepted)

    def close(self):
        self.server.shutdown()
        self.thread.join(timeout=3)


@unittest.skipUnless(os.geteuid() == 0, 'Real principal acceptance requires an explicitly authorized isolated root test process')
class ProtectedGoalTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix='ai-kit-protected-goal-'))
        self.base.chmod(0o755)
        self.root = self.base / 'installed'
        self.agent_home = self.base / 'agent'
        self.verifier_home = self.base / 'verifier'
        for directory, uid in ((self.agent_home, AGENT_UID), (self.verifier_home, VERIFIER_UID)):
            directory.mkdir(mode=0o700)
            os.chown(directory, uid, uid)
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        self.log_path = EVIDENCE / (self._testMethodName + '.log')
        self.log = self.log_path.open('w')
        self.process = None
        self.addCleanup(self.cleanup)
        self.setup_command = [sys.executable, '-I', str(SOURCE / 'goal_setup.py'), '--mode', 'protected', '--root', str(self.root),
                              '--agent-uid', str(AGENT_UID), '--agent-gid', str(AGENT_UID),
                              '--verifier-uid', str(VERIFIER_UID), '--verifier-gid', str(VERIFIER_UID),
                              '--agent-home', str(self.agent_home), '--verifier-home', str(self.verifier_home),
                              '--websockets-source', str(WEBSOCKETS_SOURCE),
                              '--native-socket', str(self.agent_home / 'native.sock')]
        if self._testMethodName == 'test_service_cadence_resumes_idle_work_without_operator_tick':
            self.setup_command += ['--cadence-seconds', '0.1']
        self.run_command(self.setup_command)
        self.assertFalse((self.root / 'control.sock').exists())
        self.start_service()

    def cleanup(self):
        self.stop_service()
        self.log.close()
        shutil.rmtree(self.base)

    def run_command(self, command, expected=0, timeout=15):
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        self.log.write(json.dumps({'argv': command, 'exit': completed.returncode}) + '\n')
        self.log.write(completed.stdout + completed.stderr)
        self.log.flush()
        if expected is not None:
            self.assertEqual(completed.returncode, expected, str(self.log_path) + '\n' + completed.stdout + completed.stderr)
        return completed

    def restricted(self, uid, command, expected=0):
        return self.run_command(['setpriv', '--reuid', str(uid), '--regid', str(uid), '--clear-groups',
                                 '--bounding-set=-all', '--inh-caps=-all', '--ambient-caps=-all',
                                 '--no-new-privs', *command], expected=expected)

    def request(self, data, uid=0, expected=0):
        command = [sys.executable, '-I', str(self.root / 'code/goal_client.py'),
                   '--socket', str(self.root / 'control.sock'), 'request', json.dumps(data)]
        completed = self.restricted(uid, command, expected) if uid else self.run_command(command, expected)
        response = json.loads(completed.stdout)
        self.assertEqual(response['ok'], expected == 0, response)
        return response.get('result') if expected == 0 else response['error']

    def start_service(self, cwd=None, env=None):
        self.process = subprocess.Popen([sys.executable, '-I', str(self.root / 'code/goal_service.py'),
                                         '--config', str(self.root / 'config.json')], stdout=self.log, stderr=self.log,
                                        cwd=cwd, env=env)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail('Service exited during startup; evidence: ' + str(self.log_path))
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.settimeout(0.2)
                    client.connect(str(self.root / 'control.sock'))
                    client.sendall(b'{"op":"inspect","id":"readiness-probe"}\n')
                    with client.makefile('rb') as response:
                        if isinstance(json.loads(response.readline()), dict):
                            return
            except (OSError, ValueError):
                pass
            time.sleep(0.02)
        self.fail('Service did not create its socket; evidence: ' + str(self.log_path))

    def stop_service(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def create_goal(self):
        if not hasattr(self, 'candidate'):
            self.candidate = self.agent_home / 'candidate'
            self.candidate.mkdir(mode=0o755)
            os.chown(self.candidate, AGENT_UID, AGENT_UID)
            self.write_candidate('import json\nprint(json.dumps({"value":41}))\n')
            self.checker = self.base / 'reviewed-checker'
            self.checker.mkdir(mode=0o755)
            self.checker.joinpath('check.py').write_text('import json,os,pathlib,sys\nassert os.getuid()==60002\nr=json.loads(pathlib.Path(sys.argv[1]).read_text())\ntry:\n    passed=r["exit_code"]==0 and r["termination"] is None and json.loads(r["stdout"])=={"value":42}\nexcept Exception:\n    passed=False\nprint(json.dumps({"passed":passed}))\n')
            self.checker.joinpath('check.py').chmod(0o644)
        acceptance = {'version': 1, 'candidate_root': str(self.candidate),
                      'candidate_argv': ['/usr/bin/python3', '-I', '{candidate}/main.py'],
                      'checker_root': str(self.checker),
                      'checker_manifest': {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                           for path in self.checker.iterdir()},
                      'checker_argv': ['/usr/bin/python3', '-I', '{checker}/check.py', '{result}', '{candidate}'],
                      'env': {}, 'timeout_seconds': 3}
        goal = {'id': 'independent-goal', 'intent': 'Produce the exact fixture result', 'scope': 'isolated fixture only',
                'target': {'runtime': 'codex', 'lead_id': str(uuid.uuid4()), 'supervisor_id': str(uuid.uuid4())},
                'acceptance': acceptance,
                'limits': {'max_wakeups': 4, 'process_timeout_seconds': 3}}
        self.request({'op': 'create', 'goal': goal})
        return goal, self.request({'op': 'inspect', 'id': goal['id']}, uid=AGENT_UID)

    def write_candidate(self, source):
        path = self.candidate / 'main.py'
        path.write_text(source)
        path.chmod(0o644)
        os.chown(path, AGENT_UID, AGENT_UID)

    def native_fixture(self, goal):
        fixture = NativeGoalFixture(self.agent_home / 'native.sock', goal['target']['lead_id'],
                                    goal['target']['supervisor_id'], self.root / 'deps')
        self.addCleanup(fixture.close)
        return fixture

    def tick(self):
        return self.request({'op': 'tick'})

    def check_candidate(self, goal):
        state = self.request({'op': 'inspect', 'id': goal['id']})
        self.request({'op': 'check_request', 'id': goal['id'], 'generation': state['generation']}, uid=AGENT_UID)
        self.tick()
        return self.request({'op': 'inspect', 'id': goal['id']})

    def test_failed_real_check_wakes_both_idle_roles_then_exact_candidate_passes(self):
        goal, state = self.create_goal()
        native = self.native_fixture(goal)
        failed = self.check_candidate(goal)
        self.assertEqual(failed['status'], 'open')
        self.assertIsNotNone(failed['last_attempt'])
        self.assertFalse(failed['last_receipt']['passed'])
        self.assertEqual(json.loads(failed['last_receipt']['candidate_result']['stdout']), {'value': 41})
        self.tick()
        self.assertEqual({item['threadId'] for item in native.accepted}, set(native.identities))
        self.assertEqual(len(native.accepted), 2)
        self.assertTrue(all('41' in json.dumps(item) or 'fail' in json.dumps(item).lower() for item in native.accepted))
        self.tick()
        self.assertEqual(len(native.accepted), 2)
        native.finish_all()
        self.write_candidate('import json\nprint(json.dumps({"value":42}))\n')
        passed = self.check_candidate(goal)
        self.assertEqual(passed['status'], 'completed', passed)
        receipt = passed['last_receipt']
        self.assertTrue(receipt['passed'])
        self.assertEqual(receipt['candidate_result']['uid'], AGENT_UID)
        self.assertEqual(receipt['verifier_result']['uid'], VERIFIER_UID)
        self.assertEqual(receipt['candidate_manifest'], {'main.py': hashlib.sha256((self.candidate / 'main.py').read_bytes()).hexdigest()})
        self.assertEqual(Path(receipt['run_path']).joinpath('candidate/main.py').read_bytes(), (self.candidate / 'main.py').read_bytes())
        evidence = json.loads((self.root / 'evidence' / (receipt['id'] + '.json')).read_text())
        self.assertEqual({key: receipt[key] for key in evidence}, evidence)
        self.assertTrue(receipt['accepted'])
        before = passed
        self.stop_service()
        self.start_service()
        self.assertEqual(self.request({'op': 'inspect', 'id': goal['id']}), before)

    def test_busy_unknown_and_premature_agent_reports_do_not_duplicate_or_close(self):
        goal, state = self.create_goal()
        native = self.native_fixture(goal)
        native.identities[goal['target']['lead_id']] = 'active'
        native.identities[goal['target']['supervisor_id']] = 'unknown'
        for outcome in ('blocked', 'failed', 'completed'):
            self.request({'op': 'report', 'id': goal['id'], 'generation': state['generation'],
                          'report': {'outcome': outcome, 'acceptance_passed': True}}, uid=AGENT_UID)
            self.tick()
        self.assertEqual(native.accepted, [])
        self.assertEqual(self.request({'op': 'inspect', 'id': goal['id']})['status'], 'open')
        native.identities.update({identity: 'idle' for identity in native.identities})
        self.tick()
        self.assertEqual(len(native.accepted), 2)

    def test_idle_supervisor_wakes_independently_of_busy_lead(self):
        goal, state = self.create_goal()
        native = self.native_fixture(goal)
        native.identities[goal['target']['lead_id']] = 'active'
        self.tick()
        self.assertEqual([item['threadId'] for item in native.accepted], [goal['target']['supervisor_id']])
        self.tick()
        self.assertEqual(len(native.accepted), 1)
        native.identities[goal['target']['lead_id']] = 'idle'
        self.tick()
        self.assertEqual({item['threadId'] for item in native.accepted}, set(native.identities))
        self.assertEqual(len(native.accepted), 2)

    def test_lost_ack_restart_and_ambiguous_absence_never_resend(self):
        goal, state = self.create_goal()
        native = self.native_fixture(goal)
        native.identities[goal['target']['supervisor_id']] = 'active'
        native.drop_ack = True
        native.hide_pending = True
        self.tick()
        self.assertEqual(len(native.accepted), 1)
        event = native.accepted[0]['clientUserMessageId']
        self.stop_service()
        self.start_service()
        for unused in range(3):
            self.tick()
        self.assertEqual(len(native.accepted), 1)
        self.assertEqual(native.accepted[0]['clientUserMessageId'], event)
        self.assertTrue(any(method == 'thread/turns/list' for method, params in native.calls))
        native.hide_pending = False
        self.tick()
        self.assertEqual(len(native.accepted), 1)

    def test_operator_stop_during_native_observation_prevents_later_send(self):
        goal, state = self.create_goal()
        native = self.native_fixture(goal)
        entered, release = threading.Event(), threading.Event()
        native.metadata_barrier = (goal['target']['lead_id'], entered, release)
        command = [sys.executable, '-I', str(self.root / 'code/goal_client.py'), '--socket',
                   str(self.root / 'control.sock'), 'request', json.dumps({'op': 'tick'})]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(entered.wait(timeout=3), 'Native metadata did not reach admission barrier')
            self.request({'op': 'stop', 'id': goal['id'], 'generation': state['generation']})
            release.set()
            output, errors = process.communicate(timeout=10)
            self.log.write(output + errors)
            self.assertEqual(process.returncode, 0, output + errors)
            self.assertEqual(native.accepted, [])
            self.assertEqual(self.request({'op': 'inspect', 'id': goal['id']})['status'], 'stopped')
        finally:
            release.set()
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)

    def test_stop_after_reservation_before_process_admission_records_known_non_delivery(self):
        goal, state = self.create_goal()
        native = self.native_fixture(goal)
        self.stop_service()
        runner = '''import contextlib,json,pathlib,sys
sys.path.insert(0,sys.argv[1])
from goal_acceptance import Acceptance
from goal_driver import Driver
from goal_store import GoalStore
config=json.loads(pathlib.Path(sys.argv[2]).read_text())
store=GoalStore(pathlib.Path(config['root'])/'state/goals.sqlite3')
original=store.admission
intercepted=[]
@contextlib.contextmanager
def admission(goal_id,generation):
    state=store.get(goal_id)
    sending=[event for event in state['outbox'] if event['status']=='sending']
    if sending and not intercepted:
        intercepted.append(sending[0]['id'])
        store.apply(goal_id,generation,'stop')
    with original(goal_id,generation):
        yield
store.admission=admission
result=Driver(config,store,Acceptance(config)).tick(force=True)
print(json.dumps({'boundary_events':intercepted,'result':result,'goal':store.get(sys.argv[3])}))
'''
        completed = self.run_command([sys.executable, '-I', '-c', runner, str(self.root / 'code'),
                                      str(self.root / 'config.json'), goal['id']])
        result = json.loads(completed.stdout)
        stopped = result['goal']
        self.assertEqual(stopped['status'], 'stopped')
        self.assertEqual(len(result['boundary_events']), 1)
        self.assertEqual(stopped['wakeups_reserved'], 1)
        self.assertEqual(len(stopped['outbox']), 1)
        event = stopped['outbox'][0]
        self.assertEqual(event['id'], result['boundary_events'][0])
        self.assertEqual(event['status'], 'not-delivered')
        self.assertEqual(native.accepted, [])
        self.assertFalse(any(method == 'thread/queue/add' for method, params in native.calls))
        self.start_service()
        self.assertEqual(self.request({'op': 'inspect', 'id': goal['id']}), stopped)
        self.request({'op': 'resume', 'id': goal['id'], 'generation': stopped['generation']})
        self.tick()
        resumed = self.request({'op': 'inspect', 'id': goal['id']})
        self.assertEqual(len(native.accepted), 2)
        self.assertEqual(resumed['wakeups_reserved'], 3)
        self.assertEqual(resumed['outbox'][0], event)
        self.assertTrue(all(item['clientUserMessageId'] != event['id'] for item in native.accepted))

    def test_controller_death_kills_candidate_descendants_and_restart_preserves_goal(self):
        goal, state = self.create_goal()
        self.native_fixture(goal)
        marker = self.agent_home / 'controller-death-barrier'
        self.write_candidate('import pathlib,time\npathlib.Path(' + repr(str(marker)) + ').write_text("started")\ntime.sleep(30)\n')
        token = os.fsencode(str(self.root / 'runs') + '/')

        def running(clean=False):
            found = []
            for directory in Path('/proc').iterdir():
                if not directory.name.isdigit():
                    continue
                descriptor = None
                try:
                    descriptor = os.pidfd_open(int(directory.name))
                    if directory.stat().st_uid not in (0, AGENT_UID, VERIFIER_UID):
                        continue
                    if not any(token in argument for argument in (directory / 'cmdline').read_bytes().split(b'\0')):
                        continue
                    if (directory / 'stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z':
                        continue
                    found.append(int(directory.name))
                    if clean:
                        signal.pidfd_send_signal(descriptor, signal.SIGKILL)
                except (FileNotFoundError, ProcessLookupError, PermissionError):
                    pass
                finally:
                    if descriptor is not None:
                        os.close(descriptor)
            return found

        command = [sys.executable, '-I', str(self.root / 'code/goal_client.py'), '--socket',
                   str(self.root / 'control.sock'), 'request', json.dumps({'op': 'tick'})]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        survivors = []
        try:
            deadline = time.monotonic() + 3
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(marker.exists(), 'Candidate never reached controller-death barrier')
            before = self.request({'op': 'inspect', 'id': goal['id']})
            self.assertTrue(running(), 'Fixture could not identify its executing OS processes')
            self.process.kill()
            self.process.wait(timeout=3)
            process.communicate(timeout=3)
            deadline = time.monotonic() + 1
            while running() and time.monotonic() < deadline:
                time.sleep(0.02)
            survivors = running()
        finally:
            remaining = running(clean=True)
            deadline = time.monotonic() + 2
            while remaining and time.monotonic() < deadline:
                time.sleep(0.02)
                remaining = running(clean=True)
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=3)
            self.assertEqual(remaining, [], 'Fixture could not remove its exact surviving subprocesses')
        self.start_service()
        recovered = self.request({'op': 'inspect', 'id': goal['id']})
        self.assertEqual(recovered['status'], 'open')
        self.assertEqual(recovered['last_attempt'], before['last_attempt'])
        self.assertEqual(recovered['acceptance'], before['acceptance'])
        self.assertEqual(survivors, [], 'Candidate or wrapper survived controller SIGKILL')
        self.write_candidate('print(\'{"value":42}\')\n')
        self.assertEqual(self.check_candidate(goal)['status'], 'completed')

    def test_service_cadence_resumes_idle_work_without_operator_tick(self):
        goal, state = self.create_goal()
        native = self.native_fixture(goal)
        deadline = time.monotonic() + 6
        while len(native.accepted) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertEqual({item['threadId'] for item in native.accepted}, set(native.identities))
        time.sleep(0.3)
        self.assertEqual(len(native.accepted), 2)

    def test_concurrent_ticks_do_not_duplicate_acceptance_or_wakeups(self):
        goal, state = self.create_goal()
        native = self.native_fixture(goal)
        command = [sys.executable, '-I', str(self.root / 'code/goal_client.py'), '--socket',
                   str(self.root / 'control.sock'), 'request', json.dumps({'op': 'tick'})]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                     for unused in range(4)]
        try:
            for process in processes:
                output, errors = process.communicate(timeout=15)
                self.log.write(output + errors)
                self.assertEqual(process.returncode, 0, output + errors)
            self.assertEqual(len(native.accepted), 2)
            self.assertEqual(len(list((self.root / 'evidence').glob('*.json'))), 1)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=3)

    def test_repeated_failure_remains_open_without_operator_failure_cap(self):
        goal, state = self.create_goal()
        native = self.native_fixture(goal)
        self.request({'op': 'set_limits', 'id': goal['id'], 'generation': state['generation'],
                      'limits': {'process_timeout_seconds': 3}})
        for unused in range(6):
            native.finish_all()
            checked = self.check_candidate(goal)
            self.assertEqual(checked['status'], 'open')
            self.assertFalse(checked['last_receipt']['passed'])
        self.assertEqual(len(list((self.root / 'evidence').glob('*.json'))), 6)
        self.assertEqual(len(native.accepted), 12)

    def test_wakeup_budget_and_deadline_prevent_admission(self):
        goal, state = self.create_goal()
        native = self.native_fixture(goal)
        self.request({'op': 'set_limits', 'id': goal['id'], 'generation': state['generation'],
                      'limits': {'max_wakeups': 1, 'process_timeout_seconds': 3}})
        self.tick()
        self.assertEqual(len(native.accepted), 1)
        native.finish_all()
        self.tick()
        self.assertEqual(len(native.accepted), 1)
        current = self.request({'op': 'inspect', 'id': goal['id']})
        self.assertEqual(current['wakeups_reserved'], 1)
        self.request({'op': 'set_limits', 'id': goal['id'], 'generation': current['generation'],
                      'limits': {'max_wakeups': 10, 'process_timeout_seconds': 3,
                                 'deadline_at': '2000-01-01T00:00:00+00:00'}})
        self.tick()
        self.assertEqual(len(native.accepted), 1)

    def test_changed_checker_source_never_replaces_pinned_acceptance(self):
        goal, state = self.create_goal()
        native = self.native_fixture(goal)
        self.checker.joinpath('check.py').write_text('print(\'{"passed":true}\')\n')
        checked = self.check_candidate(goal)
        self.assertEqual(checked['status'], 'open')
        self.assertIsNotNone(checked['last_attempt'])
        self.assertFalse(checked['last_receipt']['passed'])

    def test_tampered_pinned_checker_and_symlink_candidate_cannot_succeed(self):
        goal, state = self.create_goal()
        native = self.native_fixture(goal)
        bundle = Path(state['acceptance']['bundle_path'])
        bundle.joinpath('check.py').write_text('print(\'{"passed":true}\')\n')
        self.write_candidate('print(\'{"value":42}\')\n')
        checked = self.check_candidate(goal)
        self.assertEqual(checked['status'], 'open')
        self.assertFalse(checked['last_receipt']['passed'])
        self.assertNotIn('candidate_result', checked['last_receipt'])
        bundle.joinpath('check.py').write_bytes(self.checker.joinpath('check.py').read_bytes())
        native.finish_all()
        (self.candidate / 'main.py').unlink()
        (self.candidate / 'main.py').symlink_to(self.checker / 'check.py')
        checked = self.check_candidate(goal)
        self.assertEqual(checked['status'], 'open')
        self.assertFalse(checked['last_receipt']['passed'])
        self.assertNotIn('candidate_result', checked['last_receipt'])

    def test_malformed_checker_result_cannot_close_goal(self):
        goal, state = self.create_goal()
        self.native_fixture(goal)
        invalid = self.base / 'malformed-checker'
        invalid.mkdir(mode=0o755)
        invalid.joinpath('check.py').write_text('print(\'{"passed":true,"spoofed":true}\')\n')
        invalid.joinpath('check.py').chmod(0o644)
        other = dict(goal, id='malformed-result-goal')
        other['acceptance'] = dict(goal['acceptance'], checker_root=str(invalid),
                                   checker_manifest={'check.py': hashlib.sha256(invalid.joinpath('check.py').read_bytes()).hexdigest()})
        self.request({'op': 'stop', 'id': goal['id'], 'generation': state['generation']})
        self.request({'op': 'create', 'goal': other})
        self.write_candidate('print(\'{"value":42}\')\n')
        checked = self.check_candidate(other)
        self.assertEqual(checked['status'], 'open')
        self.assertFalse(checked['last_receipt']['passed'])

    def test_candidate_executes_only_as_agent_and_cannot_modify_protected_state(self):
        goal, state = self.create_goal()
        self.native_fixture(goal)
        protected = str(self.root / 'config.json')
        self.write_candidate('import json,os\nassert os.getuid()==60001\ntry:\n    open(' + repr(protected) + ',"wb")\nexcept PermissionError:\n    pass\nelse:\n    raise RuntimeError("candidate received controller privileges")\nprint(json.dumps({"value":42}))\n')
        self.assertEqual(self.check_candidate(goal)['status'], 'completed')

    def test_operator_stop_while_candidate_runs_fences_late_success(self):
        self.check_control_race('stop')

    def test_operator_limit_change_while_candidate_runs_fences_late_success(self):
        self.check_control_race('set_limits')

    def test_mutable_candidate_change_does_not_replace_executing_snapshot(self):
        self.check_control_race('candidate_edit')

    def check_control_race(self, operation):
        goal, state = self.create_goal()
        native = self.native_fixture(goal)
        started = self.agent_home / 'candidate-started'
        release = self.agent_home / 'candidate-release'
        result_value = 42
        self.write_candidate('import json,pathlib,time\npathlib.Path(' + repr(str(started)) + ').write_text("started")\nwhile not pathlib.Path(' + repr(str(release)) + ').exists():\n    time.sleep(0.02)\nprint(json.dumps({"value":' + str(result_value) + '}))\n')
        self.request({'op': 'check_request', 'id': goal['id'], 'generation': state['generation']}, uid=AGENT_UID)
        command = [sys.executable, '-I', str(self.root / 'code/goal_client.py'), '--socket',
                   str(self.root / 'control.sock'), 'request', json.dumps({'op': 'tick'})]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 3
            while not started.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(started.exists(), 'Real candidate never reached stop-race barrier')
            began = time.monotonic()
            control = {'op': operation, 'id': goal['id'], 'generation': state['generation']}
            if operation == 'set_limits':
                control['limits'] = {'max_wakeups': 0, 'process_timeout_seconds': 3,
                                     'deadline_at': '2000-01-01T00:00:00+00:00'}
            if operation == 'candidate_edit':
                self.write_candidate('print(\'{"value":41}\')\n')
            else:
                self.request(control)
            self.assertLess(time.monotonic() - began, 1, 'Operator stop waited for executing candidate')
            release.write_text('release')
            output, errors = process.communicate(timeout=10)
            self.log.write(output + errors)
            self.assertEqual(process.returncode, 0, output + errors)
            self.assertEqual(self.request({'op': 'inspect', 'id': goal['id']})['status'],
                             'stopped' if operation == 'stop' else 'open')
            if operation == 'candidate_edit':
                checked = self.request({'op': 'inspect', 'id': goal['id']})
                self.assertEqual(json.loads(checked['last_receipt']['candidate_result']['stdout']), {'value': 42})
                self.assertFalse(checked['last_receipt']['passed'])
                self.assertNotEqual(checked['last_receipt']['candidate_manifest']['main.py'],
                                    hashlib.sha256((self.candidate / 'main.py').read_bytes()).hexdigest())
                return
            self.tick()
            self.assertEqual(native.accepted, [])
        finally:
            release.write_text('release')
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)

    def test_installed_restart_retains_contract_and_nonterminal_reports(self):
        original, state = self.create_goal()
        for outcome in ('failed', 'blocked', 'completed', 'paused', 'stopped'):
            self.request({'op': 'report', 'id': original['id'], 'generation': state['generation'],
                          'report': {'outcome': outcome, 'summary': 'Agent assertion only',
                                     'acceptance_passed': True, 'receipt': {'verified': True}}}, uid=AGENT_UID)
            current = self.request({'op': 'inspect', 'id': original['id']})
            self.assertEqual(current['status'], 'open')
            self.assertEqual(current['generation'], state['generation'])
        before = self.request({'op': 'inspect', 'id': original['id']})
        self.stop_service()
        config_path = self.root / 'config.json'
        config = json.loads(config_path.read_text())
        self.assertEqual(config.pop('mode'), 'protected')
        config_path.write_text(json.dumps(config))
        self.start_service()
        after = self.request({'op': 'inspect', 'id': original['id']}, uid=AGENT_UID)
        self.assertEqual(after, before)
        for key in ('intent', 'scope', 'target', 'acceptance', 'limits'):
            if key == 'acceptance':
                self.assertEqual({name: after[key][name] for name in original[key]}, original[key])
            else:
                self.assertEqual(after[key], original[key])
        self.assertEqual(len(after['reports']), 5)

    def test_peer_authentication_blocks_operator_impersonation_and_lifecycle(self):
        original, before = self.create_goal()
        for operation in ('stop', 'resume', 'set_limits', 'pause', 'detach', 'deactivate', 'complete', 'delete'):
            payload = {'op': operation, 'id': original['id'], 'generation': before['generation']}
            if operation == 'set_limits':
                payload['limits'] = {'max_wakeups': 99, 'process_timeout_seconds': 3}
            self.request(payload, uid=AGENT_UID, expected=1)
        self.request({'op': 'stop', 'id': original['id'], 'generation': before['generation'], 'actor': 'operator'},
                     uid=AGENT_UID, expected=1)
        self.request({'op': 'create', 'goal': original}, uid=AGENT_UID, expected=1)
        self.request({'op': 'inspect', 'id': original['id']}, uid=VERIFIER_UID, expected=1)
        self.request({'op': 'unknown_operation', 'id': original['id']}, expected=1)
        self.assertEqual(self.request({'op': 'inspect', 'id': original['id']}), before)

    def test_setup_refuses_shared_principals_root_agent_and_agent_writable_ancestor(self):
        cases = [('same-principal', '--verifier-uid', str(AGENT_UID)),
                 ('root-agent', '--agent-uid', '0'),
                 ('unsafe-ancestor', '--root', str(self.agent_home / 'protected'))]
        for name, option, value in cases:
            with self.subTest(case=name):
                command = list(self.setup_command)
                destination = self.base / name
                command[command.index('--root') + 1] = str(destination)
                command[command.index(option) + 1] = value
                destination = Path(command[command.index('--root') + 1])
                self.run_command(command, expected=1)
                self.assertFalse((destination / 'config.json').exists())

    def test_operator_stop_resume_and_generation_fence(self):
        original, before = self.create_goal()
        self.request({'op': 'stop', 'id': original['id'], 'generation': before['generation']})
        stopped = self.request({'op': 'inspect', 'id': original['id']}, uid=AGENT_UID)
        self.assertEqual(stopped['status'], 'stopped')
        self.assertGreater(stopped['generation'], before['generation'])
        for operation in ('report', 'check_request'):
            payload = {'op': operation, 'id': original['id'], 'generation': before['generation']}
            if operation == 'report':
                payload['report'] = {'outcome': 'completed'}
            self.request(payload, uid=AGENT_UID, expected=1)
        self.request({'op': 'resume', 'id': original['id'], 'generation': before['generation']}, expected=1)
        self.request({'op': 'resume', 'id': original['id'], 'generation': stopped['generation']})
        resumed = self.request({'op': 'inspect', 'id': original['id']})
        self.assertEqual(resumed['status'], 'open')
        self.assertGreater(resumed['generation'], stopped['generation'])
        self.request({'op': 'report', 'id': original['id'], 'generation': stopped['generation'],
                      'report': {'outcome': 'completed'}}, uid=AGENT_UID, expected=1)
        limits = {'max_wakeups': 2, 'process_timeout_seconds': 3}
        self.request({'op': 'set_limits', 'id': original['id'], 'generation': resumed['generation'], 'limits': limits})
        updated = self.request({'op': 'inspect', 'id': original['id']})
        self.assertEqual(updated['limits'], limits)
        self.assertGreater(updated['generation'], resumed['generation'])
        self.request({'op': 'check_request', 'id': original['id'], 'generation': resumed['generation']},
                     uid=AGENT_UID, expected=1)

    def test_untrusted_working_directory_and_python_environment_do_not_supply_controller_code(self):
        original, before = self.create_goal()
        self.stop_service()
        marker = self.agent_home / 'controller-import-compromised'
        poison = 'from pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("executed")\nraise RuntimeError("untrusted import")\n'
        for filename in ('sitecustomize.py', 'goal_store.py', 'json.py', 'socket.py', 'sqlite3.py'):
            path = self.agent_home / filename
            path.write_text(poison)
            os.chown(path, AGENT_UID, AGENT_UID)
        environment = dict(os.environ, PYTHONPATH=str(self.agent_home), PYTHONSTARTUP=str(self.agent_home / 'sitecustomize.py'))
        self.start_service(cwd=self.agent_home, env=environment)
        self.assertEqual(self.request({'op': 'inspect', 'id': original['id']}), before)
        self.assertFalse(marker.exists())

    def test_installed_child_launcher_drops_authority_and_inherited_descriptors(self):
        probe = '''import json,os,pathlib,sys
assert os.getuid()==int(sys.argv[1])
assert os.getgid()==int(sys.argv[1])
assert os.getgroups()==[]
status=pathlib.Path('/proc/self/status').read_text()
assert 'NoNewPrivs:\\t1' in status
assert 'CapEff:\\t0000000000000000' in status
assert 'CapInh:\\t0000000000000000' in status
assert 'CapAmb:\\t0000000000000000' in status
assert 'GOAL_TEST_PARENT_SECRET' not in os.environ
try:
    os.fstat(int(sys.argv[2]))
except OSError:
    pass
else:
    raise SystemExit('Inherited protected descriptor')
try:
    open(sys.argv[3],'wb')
except PermissionError:
    pass
else:
    raise SystemExit('Protected configuration writable')
print(json.dumps({'uid':os.getuid(),'groups':os.getgroups(),'isolated':True}))
'''
        runner = '''import json,os,sys
sys.path.insert(0,sys.argv[1])
from goal_child import run_child
os.environ['GOAL_TEST_PARENT_SECRET']='must not reach children'
descriptor=os.open(sys.argv[2],os.O_RDONLY)
os.set_inheritable(descriptor,True)
uid=int(sys.argv[3])
result=run_child([sys.executable,'-I','-c',sys.argv[5],str(uid),str(descriptor),sys.argv[2]],
                 uid=uid,gid=uid,home=sys.argv[4],cwd=sys.argv[4],timeout=3)
print(json.dumps(result))
'''
        for uid, home in ((AGENT_UID, self.agent_home), (VERIFIER_UID, self.verifier_home)):
            process = self.run_command([sys.executable, '-I', '-c', runner, str(self.root / 'code'),
                                        str(self.root / 'config.json'), str(uid), str(home), probe])
            result = json.loads(process.stdout)
            self.assertEqual(result['exit_code'], 0, result)
            self.assertIsNone(result['termination'])
            self.assertEqual(json.loads(result['stdout']), {'uid': uid, 'groups': [], 'isolated': True})

    def test_child_timeout_contains_detached_descendant_with_closed_stdio(self):
        marker = self.agent_home / ('escaped-' + uuid.uuid4().hex)
        probe = '''import os,pathlib,sys,time
marker=pathlib.Path(sys.argv[1])
if os.fork()==0:
    os.setsid()
    for descriptor in (0,1,2):
        os.close(descriptor)
    marker.write_text('detached child reached')
    time.sleep(30)
    os._exit(0)
while not marker.exists():
    time.sleep(0.01)
time.sleep(30)
'''
        runner = '''import json,sys
sys.path.insert(0,sys.argv[1])
from goal_child import run_child
result=run_child([sys.executable,'-I','-c',sys.argv[4],sys.argv[5]],
                 uid=int(sys.argv[2]),gid=int(sys.argv[2]),home=sys.argv[3],cwd=sys.argv[3],timeout=1)
print(json.dumps(result))
'''

        def descendants(clean=False):
            active = []
            for directory in Path('/proc').iterdir():
                if not directory.name.isdigit():
                    continue
                descriptor = None
                try:
                    descriptor = os.pidfd_open(int(directory.name))
                    if directory.stat().st_uid != AGENT_UID:
                        continue
                    if os.fsencode(marker) not in (directory / 'cmdline').read_bytes().split(b'\0'):
                        continue
                    state = (directory / 'stat').read_text().rsplit(')', 1)[1].split()[0]
                    if state == 'Z':
                        continue
                    active.append(int(directory.name))
                    if clean:
                        signal.pidfd_send_signal(descriptor, signal.SIGKILL)
                except (FileNotFoundError, ProcessLookupError, PermissionError):
                    pass
                finally:
                    if descriptor is not None:
                        os.close(descriptor)
            return active

        try:
            process = self.run_command([sys.executable, '-I', '-c', runner, str(self.root / 'code'),
                                        str(AGENT_UID), str(self.agent_home), probe, str(marker)])
            result = json.loads(process.stdout)
            self.assertTrue(marker.exists(), result)
            self.assertEqual(result['termination'], 'timeout', result)
            self.assertEqual(descendants(), [], 'Detached child survived the declared execution timeout')
        finally:
            remaining = descendants(clean=True)
            deadline = time.monotonic() + 2
            while remaining and time.monotonic() < deadline:
                time.sleep(0.02)
                remaining = descendants(clean=True)
            self.assertEqual(remaining, [], 'Fixture failed to clean up detached descendants')

    def test_restricted_principals_cannot_write_replace_or_signal_controller(self):
        original, before = self.create_goal()
        self.assertFalse((self.root / 'code/goal_service.py').is_symlink())
        self.assertEqual((self.root / 'code/goal_service.py').read_bytes(), (SOURCE / 'goal_service.py').read_bytes())
        files = [self.root / 'config.json', *(self.root / 'code').glob('*.py'),
                 *(self.root / 'state').rglob('*.sqlite*')]
        self.assertTrue(any('sqlite' in path.name for path in files))
        initial = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
        attack = '''import json,os,pathlib,signal,sys
paths=json.loads(sys.argv[1])
denied=[]
for name in paths:
    try:
        fd=os.open(name,os.O_WRONLY)
    except PermissionError:
        denied.append(name)
    else:
        os.close(fd)
        raise SystemExit('Protected file writable: '+name)
for name in json.loads(sys.argv[2]):
    try:
        os.rename(name,name+'.replaced')
    except PermissionError:
        denied.append(name)
    else:
        raise SystemExit('Protected ancestor replaceable: '+name)
try:
    os.symlink('/tmp',sys.argv[3])
except PermissionError:
    denied.append('symlink')
else:
    raise SystemExit('Protected symlink creation permitted')
try:
    os.kill(int(sys.argv[4]),signal.SIGTERM)
except PermissionError:
    denied.append('signal')
else:
    raise SystemExit('Controller signal permitted')
status=pathlib.Path('/proc/self/status').read_text()
assert 'NoNewPrivs:\\t1' in status
assert 'CapEff:\\t0000000000000000' in status
assert os.getgroups()==[]
print(json.dumps({'uid':os.getuid(),'denied':denied}))
'''
        for uid in (AGENT_UID, VERIFIER_UID):
            self.restricted(uid, [sys.executable, '-I', '-c', attack, json.dumps(list(initial)),
                                  json.dumps([str(self.root), str(self.root / 'code'), str(self.root / 'state'),
                                              str(self.root / 'acceptance'), str(self.root / 'evidence')]),
                                  str(self.root / 'replacement-link'), str(self.process.pid)])
        self.assertIsNone(self.process.poll())
        self.assertEqual({str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}, initial)
        self.assertEqual(self.request({'op': 'inspect', 'id': original['id']}), before)


if __name__ == '__main__':
    unittest.main()
