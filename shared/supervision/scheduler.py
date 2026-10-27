import fcntl
import importlib.util
import json
import os
from pathlib import Path
import time
import uuid

try:
    from .store import StoreError
except ImportError:
    from store import StoreError


OPEN = ('pending', 'sending', 'delivered', 'uncertain', 'unhealthy', 'not-delivered')


def native_transport(codex_path='codex', runtime='codex', claude_path='claude'):
    if runtime not in ('codex', 'claude'):
        raise StoreError('unsupported supervision runtime: ' + str(runtime))
    source = Path(__file__).with_name(runtime + '_transport.py')
    if not source.exists():
        source = Path(__file__).resolve().parents[2] / runtime / 'supervision/transport.py'
    spec = importlib.util.spec_from_file_location('supervision_' + runtime + '_transport', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.NativeTransport(**{runtime + '_path': codex_path if runtime == 'codex' else claude_path})


def execution_read(store, execution_id):
    row = store.conn.execute('SELECT * FROM executions WHERE id=?', (execution_id,)).fetchone()
    if row is None:
        raise StoreError('unknown execution')
    result = dict(row)
    result['result'] = json.loads(result['result']) if result['result'] else None
    result['task'] = store.task(row['task_id'])
    result['binding'] = store.binding(row['supervisor_id'])
    result['memory'] = store.memory({'supervisor_id': row['supervisor_id'], 'task_id': row['task_id']})
    result['supervisor_memory'] = store.memory({'supervisor_id': row['supervisor_id']})
    return result


def transport_read(store, transport, data):
    with store.transaction():
        binding = store.binding(data['supervisor_id'])
        if binding['status'] != 'active':
            raise StoreError('binding is detached; native reads refused')
        target = data['session_id']
        if target not in [binding['session_id'], *binding['target_ids']]:
            raise StoreError('session is outside the exact binding')
        return transport.read(target, cursor=data.get('cursor'))


class Scheduler:
    def __init__(self, store, transport=None, now=None, cli_path=None, max_dispatch=10, codex_path='codex', claude_path='claude'):
        self.store = store
        self.transport = transport
        self.codex_path = codex_path
        self.claude_path = claude_path
        self.transports = {}
        self.now = time.time() if now is None else now
        self.cli_path = str(Path(cli_path or Path(__file__).with_name('cli.py')).absolute())
        self.max_dispatch = max_dispatch

    def _transport(self, runtime='codex'):
        if self.transport is not None:
            return self.transport
        if runtime not in self.transports:
            self.transports[runtime] = native_transport(self.codex_path, runtime=runtime, claude_path=self.claude_path)
        return self.transports[runtime]

    def _valid(self, execution):
        task = self.store.task(execution['task_id'])
        binding = self.store.binding(execution['supervisor_id'])
        return task['status'] == 'active' and binding['status'] == 'active' and task['generation'] == execution['generation'] and binding['generation'] == execution['binding_generation']

    def _claim(self):
        db = self.store.conn
        with self.store.transaction():
            rows = db.execute("SELECT t.* FROM tasks t JOIN bindings b ON b.id=t.supervisor_id WHERE t.status='active' AND b.status='active' AND t.next_run_at<=? ORDER BY t.next_run_at,t.id", (self.now,)).fetchall()
            count = 0
            for row in rows:
                if count >= self.max_dispatch:
                    break
                task = self.store.task(row['id'])
                existing = db.execute("SELECT 1 FROM executions WHERE supervisor_id=? AND status IN ('pending','sending','delivered','uncertain','unhealthy','not-delivered')", (task['supervisor_id'],)).fetchone()
                if existing:
                    continue
                checks = db.execute('SELECT count(*) FROM executions WHERE task_id=?', (task['id'],)).fetchone()[0]
                cap = task['limits']['max_checks']
                if cap is not None and checks >= cap:
                    payload = json.loads(row['payload'])
                    payload.update(reason='max_checks reached; explicit reassessment required', resume_condition='Review limits and explicitly resume', remaining=['Supervision allowance requires reassessment'])
                    db.execute("UPDATE tasks SET status='blocked',revision=revision+1,payload=? WHERE id=?", (json.dumps(payload), task['id']))
                    self.store.audit('check-limit', task['id'], {'checks': checks}, 'scheduler')
                    continue
                if task['interval_seconds'] is None and checks:
                    continue
                binding = self.store.binding(task['supervisor_id'])
                eid = str(uuid.uuid4())
                event = str(uuid.uuid4())
                payload = {'execution_id': eid, 'generation': task['generation'], 'cli': self.cli_path, 'state_dir': str(self.store.root)}
                db.execute('INSERT INTO executions(id,task_id,supervisor_id,generation,binding_generation,status,scheduled_at,lease_until) VALUES(?,?,?,?,?,?,?,?)', (eid, task['id'], task['supervisor_id'], task['generation'], binding['generation'], 'pending', task['next_run_at'], self.now + task['limits']['assessment_timeout_seconds']))
                db.execute('INSERT INTO outbox(id,execution_id,status,payload,client_message_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)', (event, eid, 'pending', json.dumps(payload), event, self.now, self.now))
                interval = task['interval_seconds']
                if interval:
                    due = (int(self.now // interval) + 1) * interval if task.get('schedule_mode') == 'utc-aligned' else self.now + interval
                    db.execute('UPDATE tasks SET next_run_at=?,updated_at=? WHERE id=?', (due, self.now, task['id']))
                self.store.audit('execution-claim', eid, payload, 'scheduler')
                count += 1

    def _outcome(self, outbox, execution, status, detail=None, native_id=None):
        db = self.store.conn
        if not self._valid(execution):
            return
        db.execute('UPDATE outbox SET status=?,native_submission_id=COALESCE(?,native_submission_id),updated_at=? WHERE id=?', (status, native_id, self.now, outbox['id']))
        task = self.store.task(execution['task_id'])
        lease = self.now + task['limits']['assessment_timeout_seconds'] if status == 'delivered' else None
        db.execute('UPDATE executions SET status=?,lease_until=?,result=? WHERE id=?', (status, lease, json.dumps({'delivery': detail}) if detail else None, execution['id']))
        self.store.audit('delivery-' + status, execution['id'], {'detail': detail}, 'scheduler')

    def _dispatch(self):
        db = self.store.conn
        rows = db.execute("SELECT o.* FROM outbox o JOIN executions e ON e.id=o.execution_id JOIN tasks t ON t.id=e.task_id JOIN bindings b ON b.id=e.supervisor_id WHERE t.status='active' AND b.status='active' AND t.generation=e.generation AND b.generation=e.binding_generation AND (o.status IN ('pending','sending') OR (o.status='uncertain' AND json_extract(o.payload,'$.reconciled') IS NULL) OR (o.status='not-delivered' AND o.attempts<1+min(1,json_extract(t.payload,'$.limits.recovery_attempts')) AND o.updated_at+60<=?)) ORDER BY o.created_at,o.id LIMIT ?", (self.now, self.max_dispatch)).fetchall()
        for outbox in rows:
            execution = db.execute('SELECT * FROM executions WHERE id=?', (outbox['execution_id'],)).fetchone()
            if not self._valid(execution):
                continue
            task = self.store.task(execution['task_id'])
            binding = self.store.binding(execution['supervisor_id'])
            try:
                transport = self._transport(binding['runtime'])
            except Exception as error:
                if outbox['status'] in ('pending', 'not-delivered') and outbox['attempts'] < 1 + min(1, task['limits']['recovery_attempts']) and (not outbox['attempts'] or self.now >= outbox['updated_at'] + 60):
                    with self.store.transaction():
                        db.execute('UPDATE outbox SET attempts=attempts+1 WHERE id=?', (outbox['id'],))
                        self._outcome(outbox, execution, 'not-delivered', str(error))
                continue
            if hasattr(transport, 'timeout'):
                transport.timeout = min(30, task['limits']['transport_timeout_seconds'])
            if outbox['status'] in ('sending', 'uncertain'):
                if outbox['status'] == 'uncertain' and json.loads(outbox['payload']).get('reconciled'):
                    continue
                try:
                    result = transport.reconcile(binding['session_id'], outbox['client_message_id'])
                except Exception as error:
                    result = {'status': 'uncertain', 'error': str(error)}
                status = 'delivered' if result.get('status') == 'delivered' else 'uncertain'
                with self.store.transaction():
                    current_execution = db.execute('SELECT * FROM executions WHERE id=?', (execution['id'],)).fetchone()
                    current_outbox = db.execute('SELECT * FROM outbox WHERE id=?', (outbox['id'],)).fetchone()
                    if (current_execution is None or current_outbox is None
                            or dict(current_execution) != dict(execution) or dict(current_outbox) != dict(outbox)):
                        self.store.audit('delivery-observation-superseded', execution['id'], {'observation': result}, 'scheduler')
                        continue
                    self._outcome(outbox, execution, status, result, result.get('native_submission_id'))
                    payload = json.loads(outbox['payload'])
                    payload['reconciled'] = True
                    db.execute('UPDATE outbox SET payload=? WHERE id=?', (json.dumps(payload), outbox['id']))
                continue
            if outbox['status'] == 'not-delivered':
                if outbox['attempts'] >= 1 + min(1, task['limits']['recovery_attempts']) or self.now < outbox['updated_at'] + 60:
                    continue
            try:
                metadata = transport.metadata(binding['session_id'])
                status = metadata.get('status')
                if isinstance(status, dict):
                    status = status.get('type')
                if status != 'idle':
                    continue
            except Exception as error:
                with self.store.transaction():
                    db.execute('UPDATE outbox SET attempts=attempts+1 WHERE id=?', (outbox['id'],))
                    self._outcome(outbox, execution, 'not-delivered', str(error))
                continue
            with self.store.transaction():
                if not self._valid(execution):
                    continue
                db.execute("UPDATE outbox SET status='sending',attempts=attempts+1,updated_at=? WHERE id=?", (self.now, outbox['id']))
                db.execute("UPDATE executions SET status='sending',started_at=?,lease_until=? WHERE id=?", (self.now, self.now + task['limits']['transport_timeout_seconds'], execution['id']))
            with self.store.transaction():
                if not self._valid(execution):
                    continue
                try:
                    message = 'AI_KIT_SUPERVISOR_EVENT ' + outbox['payload'] + '\nRead this execution using execution-read, restore its memory, and apply the supervisor skill within the recorded scope and limits. Record the assessment using execution-result.'
                    result = transport.send(binding['session_id'], outbox['client_message_id'], message)
                    status = result.get('status', 'uncertain')
                    if status not in ('delivered', 'not-delivered'):
                        status = 'uncertain'
                    self._outcome(outbox, execution, status, result, result.get('native_submission_id'))
                except Exception as error:
                    self._outcome(outbox, execution, 'uncertain' if getattr(error, 'uncertain', True) else 'not-delivered', str(error))

    def tick(self):
        path = self.store.root / 'tick.lock'
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            self.store._private(path)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {'locked': True}
            with self.store.transaction():
                waiting = self.store.conn.execute("SELECT id,lease_until FROM executions WHERE status='pending' AND lease_until<=? AND COALESCE(json_extract(result,'$.dispatch_wait_overdue'),0)=0", (self.now,)).fetchall()
                for row in waiting:
                    detail = {'dispatch_wait_overdue': True, 'dispatch_deadline': row['lease_until'], 'observation': 'dispatch wait exceeded; delivery remains pending until supervisor is idle; activity is not classified as failure'}
                    self.store.conn.execute('UPDATE executions SET result=? WHERE id=?', (json.dumps(detail), row['id']))
                    self.store.audit('dispatch-wait-overdue', row['id'], detail, 'scheduler')
                expired = self.store.conn.execute("SELECT id,result FROM executions WHERE status='delivered' AND lease_until<=?", (self.now,)).fetchall()
                for row in expired:
                    self.store.conn.execute("UPDATE executions SET status='unhealthy',result=? WHERE id=?", (json.dumps({'assessment_checkpoint_overdue': True, 'observation': 'assessment checkpoint exceeded; assess progress; execution authority and task remain active', 'previous_result': json.loads(row['result']) if row['result'] else None}), row['id']))
                    self.store.audit('assessment-overdue', row['id'], {'checkpoint_at': self.now, 'authority_retained': True, 'previous_result': json.loads(row['result']) if row['result'] else None}, 'scheduler')
            self._claim()
            self._dispatch()
            with self.store.transaction():
                self.store.audit('tick', 'scheduler', {'at': self.now}, 'scheduler')
            return {'locked': False, 'health': self.store.status()['health']}
        finally:
            os.close(fd)


def reconcile_execution(store, execution_id, transport):
    scheduler = Scheduler(store, transport)
    with store.transaction():
        execution = store.conn.execute('SELECT * FROM executions WHERE id=?', (execution_id,)).fetchone()
        if execution is None or not scheduler._valid(execution):
            raise StoreError('stale or inactive execution authority')
        if execution['status'] in ('delivered', 'unhealthy'):
            return execution_read(store, execution_id)
        if execution['status'] not in ('sending', 'uncertain'):
            raise StoreError('execution has no uncertain delivery to reconcile')
        outbox = store.conn.execute('SELECT * FROM outbox WHERE execution_id=?', (execution_id,)).fetchone()
        binding = store.binding(execution['supervisor_id'])
        if hasattr(transport, 'timeout'):
            transport.timeout = min(30, store.task(execution['task_id'])['limits']['transport_timeout_seconds'])
        try:
            result = transport.reconcile(binding['session_id'], outbox['client_message_id'])
        except Exception as error:
            result = {'status': 'uncertain', 'error': str(error)}
        status = 'delivered' if result.get('status') == 'delivered' else 'uncertain'
        scheduler._outcome(outbox, execution, status, result, result.get('native_submission_id'))
        payload = json.loads(outbox['payload'])
        payload['reconciled'] = True
        store.conn.execute('UPDATE outbox SET payload=? WHERE id=?', (json.dumps(payload), outbox['id']))
        store.audit('execution-reconcile', execution_id, result, 'supervisor')
        return execution_read(store, execution_id)
