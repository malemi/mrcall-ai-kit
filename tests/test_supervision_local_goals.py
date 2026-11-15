import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import tempfile
import time
import unittest
import uuid

import test_supervision_goals as goals
import test_supervision_install as installation


EVIDENCE = Path(tempfile.gettempdir()) / 'mrcall-ai-kit/local-goal-controller-20261030'
LEDGER_SOURCE = Path(__file__).resolve().parents[1] / 'shared/supervision/ledger.py'


def ledger_module():
    spec = importlib.util.spec_from_file_location('ledger', LEDGER_SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ledger_rows(path):
    store = ledger_module().Ledger(path)
    try:
        return {row['client_id']: dict(row) for row in
                store.conn.execute('SELECT client_id, session_id, kind, state_root, task_id FROM messages')}
    finally:
        store.close()


@unittest.skipIf(os.geteuid() == 0, 'Local acceptance must execute as an ordinary account')
class LocalGoalTests(unittest.TestCase):
    run_command = goals.ProtectedGoalTests.run_command
    start_service = goals.ProtectedGoalTests.start_service
    stop_service = goals.ProtectedGoalTests.stop_service
    tick = goals.ProtectedGoalTests.tick

    def setUp(self):
        self.fixture = installation.InstallTests(methodName='runTest')
        self.fixture.setUp()
        self.base = self.fixture.home.parent
        self.base.chmod(0o775)
        self.root = self.base / 'local-goals'
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        self.log_path = EVIDENCE / (self._testMethodName + '.log')
        self.log = self.log_path.open('w')
        self.process = None
        self.addCleanup(self.cleanup)
        self.fixture.log = EVIDENCE / (self._testMethodName + '-install.log')
        self.fixture.install()
        self.setup_command = [sys.executable, '-I', str(self.fixture.kit / 'supervision/goal_setup.py'),
                              '--root', str(self.root), '--websockets-source', str(goals.WEBSOCKETS_SOURCE),
                              '--native-socket', str(self.base / 'native.sock')]
        self.fixture.run_cli(self.setup_command)
        config = json.loads((self.root / 'config.json').read_text())
        self.assertEqual(config['mode'], 'local')
        for role in ('agent', 'verifier'):
            self.assertEqual(config[role + '_uid'], os.getuid())
            self.assertEqual(config[role + '_gid'], os.getgid())
            self.assertEqual(config[role + '_home'], str(self.fixture.home))
        self.assertFalse((self.root / 'control.sock').exists())
        self.assertEqual(self.fixture.crontab.read_text(), self.fixture.foreign_cron)
        self.start_service()

    def cleanup(self):
        self.stop_service()
        self.log.close()
        for directory in self.base.rglob('*'):
            if directory.is_dir():
                directory.chmod(0o700)
        shutil.rmtree(self.base)

    def request(self, data, uid=None, expected=0):
        self.assertIn(uid, (None, os.getuid()))
        result = self.run_command([sys.executable, '-I', str(self.root / 'code/goal_client.py'),
                                   '--socket', str(self.root / 'control.sock'), 'request', json.dumps(data)],
                                  expected=expected)
        response = json.loads(result.stdout)
        self.assertEqual(response['ok'], expected == 0, response)
        return response['result'] if expected == 0 else response['error']

    def check_candidate(self, goal):
        state = self.request({'op': 'inspect', 'id': goal['id']})
        self.request({'op': 'check_request', 'id': goal['id'], 'generation': state['generation']})
        self.tick()
        return self.request({'op': 'inspect', 'id': goal['id']})

    def write_candidate(self, source):
        (self.candidate / 'main.py').write_text(source)

    def create_goal(self):
        self.candidate = self.base / 'candidate'
        self.candidate.mkdir()
        self.write_candidate('import json,os\nassert os.getuid()==' + str(os.getuid()) + '\nprint(json.dumps({"value":41}))\n')
        checker = self.base / 'checker'
        checker.mkdir()
        checker.joinpath('check.py').write_text('import json,os,pathlib,sys\nassert os.getuid()==' + str(os.getuid()) + '\nr=json.loads(pathlib.Path(sys.argv[1]).read_text())\nprint(json.dumps({"passed":r["exit_code"]==0 and r["termination"] is None and json.loads(r["stdout"])=={"value":42}}))\n')
        acceptance = {'version': 1, 'candidate_root': str(self.candidate),
                      'candidate_argv': ['/usr/bin/python3', '-I', '{candidate}/main.py'],
                      'checker_root': str(checker),
                      'checker_manifest': {'check.py': hashlib.sha256(checker.joinpath('check.py').read_bytes()).hexdigest()},
                      'checker_argv': ['/usr/bin/python3', '-I', '{checker}/check.py', '{result}'],
                      'timeout_seconds': 3}
        goal = {'id': 'local-fixture', 'intent': 'Produce exact fixture output', 'scope': 'isolated fixture',
                'target': {'runtime': 'codex', 'lead_id': str(uuid.uuid4()), 'supervisor_id': str(uuid.uuid4())},
                'acceptance': acceptance, 'limits': {'max_wakeups': 4, 'process_timeout_seconds': 3}}
        self.request({'op': 'create', 'goal': goal})
        native = goals.NativeGoalFixture(self.base / 'native.sock', goal['target']['lead_id'],
                                         goal['target']['supervisor_id'], self.root / 'deps', socket_uid=os.getuid())
        self.addCleanup(native.close)
        return goal, native

    def test_installed_local_failure_wakes_restart_reconciles_and_corrected_acceptance_completes(self):
        goal, native = self.create_goal()
        native.drop_ack = True
        failed = self.check_candidate(goal)
        self.assertEqual(failed['status'], 'open')
        receipt = failed['last_receipt']
        self.assertFalse(receipt['passed'])
        self.assertEqual(json.loads(receipt['candidate_result']['stdout']), {'value': 41})
        self.assertEqual({item['threadId'] for item in native.accepted}, set(native.identities))
        self.assertEqual(len(native.accepted), 2)
        original_events = [item['clientUserMessageId'] for item in native.accepted]
        self.assertTrue(any(event['status'] == 'uncertain' for event in failed['outbox']))
        self.assertEqual(failed['wakeups_reserved'], 2)
        self.stop_service()
        self.start_service()
        self.assertEqual(self.request({'op': 'inspect', 'id': goal['id']}), failed)
        self.tick()
        reconciled = self.request({'op': 'inspect', 'id': goal['id']})
        self.assertEqual([event['id'] for event in reconciled['outbox']], original_events)
        self.assertTrue(all(event['status'] == 'delivered' for event in reconciled['outbox']))
        self.assertEqual(reconciled['wakeups_reserved'], 2)
        self.assertEqual(len(native.accepted), 2)
        self.assertTrue(any(method == 'thread/queue/list' for method, params in native.calls))
        native.finish_all()
        self.write_candidate('import json\nprint(json.dumps({"value":42}))\n')
        passed = self.check_candidate(goal)
        self.assertEqual(passed['status'], 'completed', passed)
        receipt = passed['last_receipt']
        self.assertTrue(receipt['passed'])
        self.assertTrue(receipt['accepted'])
        for key in ('candidate_result', 'verifier_result'):
            self.assertEqual(receipt[key]['uid'], os.getuid())
            self.assertEqual(receipt[key]['exit_code'], 0)
            self.assertIsNone(receipt[key]['termination'])
        self.assertEqual(receipt['candidate_manifest'], {'main.py': hashlib.sha256((self.candidate / 'main.py').read_bytes()).hexdigest()})
        self.assertEqual(Path(receipt['run_path']).joinpath('candidate/main.py').read_bytes(), (self.candidate / 'main.py').read_bytes())
        evidence = json.loads((self.root / 'evidence' / (receipt['id'] + '.json')).read_text())
        self.assertEqual({key: receipt[key] for key in evidence}, evidence)
        self.stop_service()
        self.start_service()
        self.assertEqual(self.request({'op': 'inspect', 'id': goal['id']}), passed)

    def test_installed_local_child_bounds_output_and_cleans_timed_out_process_group(self):
        marker = self.base / 'child-pid'
        probe = '''import os,pathlib,sys,time
child=os.fork()
if child==0:
    pathlib.Path(sys.argv[1]).write_text(str(os.getpid()))
    time.sleep(30)
    os._exit(0)
while not pathlib.Path(sys.argv[1]).exists():
    time.sleep(0.01)
time.sleep(30)
'''
        runner = '''import json,os,sys
sys.path.insert(0,sys.argv[1])
from goal_child import run_child
result=run_child([sys.executable,'-I','-c',sys.argv[3],sys.argv[4]],uid=os.getuid(),gid=os.getgid(),home=sys.argv[2],cwd=sys.argv[2],timeout=0.5,max_output=4096)
print(json.dumps(result))
'''
        def run_probe(source):
            return json.loads(self.run_command([sys.executable, '-I', '-c', runner, str(self.root / 'code'),
                                                str(self.base), source, str(marker)]).stdout)
        try:
            result = run_probe(probe)
            self.assertEqual(result['termination'], 'timeout', result)
            self.assertLess(result['elapsed_seconds'], 3)
            self.assertTrue(marker.exists(), result)
            child = int(marker.read_text())
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                status = Path('/proc') / str(child) / 'stat'
                if not status.exists() or status.read_text().rsplit(')', 1)[1].split()[0] == 'Z':
                    break
                time.sleep(0.02)
            else:
                self.fail('Same-group descendant survived local timeout')
        finally:
            if marker.exists():
                try:
                    os.kill(int(marker.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass
        result = run_probe('import os\nwhile True:\n    os.write(1,b"x"*65536)\n')
        self.assertEqual(result['termination'], 'output_limit', result)
        self.assertEqual(len(result['stdout'].encode()) + len(result['stderr'].encode()), 4096)
        self.assertLess(result['elapsed_seconds'], 3)

    def test_installed_ledger_asset_is_copied_and_importable_from_the_code_directory(self):
        installed = self.root / 'code/ledger.py'
        self.assertTrue(installed.is_file())
        self.assertFalse(installed.is_symlink())
        self.assertEqual(installed.read_bytes(), LEDGER_SOURCE.read_bytes())
        probe = ("import sys,json\nsys.path.insert(0,sys.argv[1])\nimport ledger\n"
                 "print(json.dumps({'file': ledger.__file__, 'has_record': callable(ledger.Ledger.record)}))")
        result = self.run_command([sys.executable, '-I', '-c', probe, str(self.root / 'code')])
        payload = json.loads(result.stdout)
        self.assertEqual(Path(payload['file']).resolve(), installed.resolve())
        self.assertTrue(payload['has_record'])


@unittest.skipIf(os.geteuid() == 0, 'Local acceptance must execute as an ordinary account')
class LedgerGoalTests(unittest.TestCase):
    run_command = goals.ProtectedGoalTests.run_command
    start_service = goals.ProtectedGoalTests.start_service
    stop_service = goals.ProtectedGoalTests.stop_service
    tick = goals.ProtectedGoalTests.tick
    cleanup = LocalGoalTests.cleanup
    request = LocalGoalTests.request
    check_candidate = LocalGoalTests.check_candidate
    write_candidate = LocalGoalTests.write_candidate
    create_goal = LocalGoalTests.create_goal

    def setUp(self):
        self.ledger_temp = tempfile.TemporaryDirectory(prefix='goal-ledger-')
        self.addCleanup(self.ledger_temp.cleanup)
        self.previous_ledger_env = os.environ.get('MRCALL_SUPERVISION_LEDGER')
        self.addCleanup(self.restore_ledger_env)
        self.configured_ledger_path = str(Path(self.ledger_temp.name) / 'ledger.sqlite3')
        os.environ['MRCALL_SUPERVISION_LEDGER'] = self.configured_ledger_path
        LocalGoalTests.setUp(self)
        config = json.loads((self.root / 'config.json').read_text())
        self.assertEqual(config['ledger_path'], self.configured_ledger_path)

    def restore_ledger_env(self):
        if self.previous_ledger_env is None:
            os.environ.pop('MRCALL_SUPERVISION_LEDGER', None)
        else:
            os.environ['MRCALL_SUPERVISION_LEDGER'] = self.previous_ledger_env

    def test_installed_ledger_records_each_sent_wake_before_an_uncertain_native_send(self):
        goal, native = self.create_goal()
        native.drop_ack = True
        failed = self.check_candidate(goal)
        self.assertEqual(failed['status'], 'open')
        self.assertTrue(any(event['status'] == 'uncertain' for event in failed['outbox']))
        self.assertEqual(len(native.accepted), 2)
        sent_ids = [item['clientUserMessageId'] for item in native.accepted]
        rows = ledger_rows(self.configured_ledger_path)
        self.assertEqual(set(sent_ids), set(rows))
        for client_id in sent_ids:
            self.assertEqual(rows[client_id]['kind'], 'goal')
            self.assertEqual(rows[client_id]['state_root'], str(self.root))
            self.assertEqual(rows[client_id]['task_id'], goal['id'])

    def test_installed_unusable_ledger_path_refuses_every_wake_and_sends_nothing(self):
        blocker = Path(self.ledger_temp.name) / 'blocker'
        blocker.write_text('a file, not a directory')
        unusable = blocker / 'sub/ledger.sqlite3'
        os.environ['MRCALL_SUPERVISION_LEDGER'] = str(unusable)
        self.stop_service()
        config_path = self.root / 'config.json'
        config = json.loads(config_path.read_text())
        config['ledger_path'] = str(unusable)
        config_path.write_text(json.dumps(config))
        self.start_service()
        goal, native = self.create_goal()
        failed = self.check_candidate(goal)
        self.assertEqual(failed['status'], 'open')
        self.assertEqual(native.accepted, [])
        self.assertTrue(failed['outbox'])
        for event in failed['outbox']:
            self.assertEqual(event['status'], 'not-delivered')
            self.assertIn('ledger', event['observation']['error'])
        self.assertFalse(unusable.exists())

    def test_installed_absent_ledger_path_sends_as_before_and_creates_no_file(self):
        config_path = self.root / 'config.json'
        config = json.loads(config_path.read_text())
        ledger_path = config.pop('ledger_path')
        config_path.write_text(json.dumps(config))
        self.stop_service()
        self.start_service()
        goal, native = self.create_goal()
        failed = self.check_candidate(goal)
        self.assertEqual(failed['status'], 'open')
        self.assertEqual(len(native.accepted), 2)
        self.assertTrue(all(event['status'] in ('delivered', 'uncertain') for event in failed['outbox']))
        self.assertFalse(Path(ledger_path).exists())


if __name__ == '__main__':
    unittest.main()
