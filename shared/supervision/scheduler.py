import fcntl
import importlib.util
import json
import os
from pathlib import Path
import time
import uuid

try:
    from .store import LEGACY, OPEN_EXECUTIONS, StoreError
    from . import authority, observe, review
except ImportError:
    from store import LEGACY, OPEN_EXECUTIONS, StoreError
    import authority
    import observe
    import review


OPEN = ('pending', 'sending', 'delivered', 'uncertain', 'unhealthy', 'not-delivered')
WAKE = ('Assess this supervision event now. Read it with execution-read: it holds the triggers below, the closing set and what '
        'Python measured. Close the assessment with execution-result as COMMANDS.md describes; a result the records do not '
        'support is refused and names what is missing.')


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
    if result['task'].get('contract') == 2:
        # The observation that triggered the assessment travels with it; no session history is needed to read it.
        result['triggers'] = json.loads(result['triggers'] or '[]')
        result['closing_set'] = json.loads(result['closing_set'] or '[]')
        result['measured'] = store.measured(row['task_id'])
        result['registry'] = store.registry()
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

    def _bound(self, binding, task):
        transport = self._transport(binding['runtime'])
        if hasattr(transport, 'timeout'):
            transport.timeout = min(30, task['limits']['transport_timeout_seconds'])
        return transport

    def _valid(self, execution):
        task = self.store.task(execution['task_id'])
        binding = self.store.binding(execution['supervisor_id'])
        return task['status'] == 'active' and binding['status'] == 'active' and task['generation'] == execution['generation'] and binding['generation'] == execution['binding_generation']

    def _tasks(self, statuses):
        marks = ','.join('?' * len(statuses))
        rows = self.store.conn.execute(
            f"SELECT t.id FROM tasks t JOIN bindings b ON b.id=t.supervisor_id WHERE t.status IN ({marks}) AND b.status='active' ORDER BY t.next_run_at,t.id", statuses).fetchall()
        return [task for task in (self.store.task(row[0]) for row in rows) if task.get('contract') == 2]

    # ---- observation ----

    def _observe(self):
        """Observe the sessions of every task that is active or parked, each session once per tick."""
        seen = {}
        for task in self._tasks(('active', 'blocked')):
            binding, sessions = observe.task_sessions(self.store, task)
            try:
                transport = self._bound(binding, task)
            except Exception as error:
                with self.store.transaction():
                    self.store.audit('observation-unavailable', task['id'], {'error': str(error)}, 'scheduler')
                continue
            for session_id in sessions:
                if session_id not in seen:
                    spends = session_id == binding['session_id'] or session_id in task['target_ids']
                    seen[session_id] = observe.observe_session(self.store, transport, session_id, binding['runtime'], self.now,
                                                               workers_since=task['created_at'] if spends else None)
            observe.raise_triggers(self.store, task, seen, self.now)

    # ---- limits, abandonment, parks ----

    def _limits(self):
        """A deadline, a count or a spend ceiling reached parks the task and stops admission."""
        for task in self._tasks(('active',)):
            if self.store.counters(task['id'])['state'].get('limit_grace'):
                continue
            reached = self.store.limits_reached(task, self.now)
            if not reached:
                continue
            questions, measured = [], []
            for limit in reached:
                if limit['limit'] == 'deadline':
                    matter = f"The deadline the operator set for task {task['id']} ({authority.stamp(limit['value'])}) has passed and the task is not finished."
                    options = ['Set a later deadline', 'Stop the task']
                elif limit['limit'] == 'count':
                    matter = f"Task {task['id']} used the {limit['value']} assessments the operator allowed and is not finished."
                    options = ['Allow more assessments', 'Stop the task']
                    measured.append(f"{limit['measured']} assessments ran")
                else:
                    matter = f"Task {task['id']} reached the spend ceiling the operator set ({authority.amount(limit['value'], limit['unit'])})."
                    options = ['Raise the ceiling', 'Stop the task']
                    measured.append('measured spend ' + authority.amount(limit['measured'], limit['unit']))
                questions.append({'matter': matter, 'options': options, 'recommendation': 'Decide from the open items below; nothing proceeds until you write.'})
            still = [row[0] for row in self.store.conn.execute("SELECT id FROM items WHERE task_id=? AND status='open' ORDER BY id", (task['id'],))]
            with self.store.transaction():
                self.store.park(task['id'], 'limit-reached', questions,
                                'Open acceptance items: ' + (', '.join(still) or 'none') + '. ' + '; '.join(measured))
            if any(limit['limit'] == 'spend' for limit in reached):
                self._interrupt(task)

    def _interrupt(self, task):
        """A spend ceiling stops the targets' running turns where the runtime can; status says when a turn continues."""
        binding = self.store.binding(task['supervisor_id'])
        for target in task['target_ids']:
            turn = (self.store.session(target) or {}).get('running_turn')
            if not turn:
                continue
            try:
                self._bound(binding, task).interrupt(target, turn['id'])
                outcome = {'status': 'interrupted'}
            except AttributeError:
                outcome = {'status': 'continues', 'reason': 'this runtime adapter cannot interrupt a turn'}
            except Exception as error:
                outcome = {'status': 'continues', 'reason': str(error)}
            with self.store.transaction():
                observe.log(self.store, target, 'interrupt', {'task_id': task['id'], 'turn_id': turn['id'], **outcome}, self.now)
                self.store.audit('turn-interrupt', target, {'task_id': task['id'], 'turn_id': turn['id'], **outcome}, 'scheduler')

    def _abandon(self):
        """An assessment the supervisor never closes is closed by Python; two in a row, or a lost wake, park the task."""
        db = self.store.conn
        unresolved = "The supervisor session does not complete its assessments of task {task}."
        request = lambda task_id: ([{'matter': unresolved.format(task=task_id), 'options': ['Check the supervisor session and write there to resume', 'Stop the task'],
                                     'recommendation': 'Open the supervisor session; supervision resumes when you write in an observed session.'}],
                                   'Nothing else can proceed: no assessment is being recorded.')
        for row in db.execute("SELECT * FROM executions WHERE status='unhealthy'").fetchall():
            task = self.store.task(row['task_id'])
            since = json.loads(row['result'] or '{}').get('unhealthy_at')
            if task.get('contract') != 2 or since is None or self.now - since < task['limits']['heartbeat_seconds']:
                continue
            with self.store.transaction():
                db.execute("UPDATE executions SET status='abandoned',finished_at=? WHERE id=? AND status='unhealthy'", (self.now, row['id']))
                db.execute('UPDATE triggers SET execution_id=NULL WHERE execution_id=?', (row['id'],))
                db.execute('UPDATE counters SET abandoned=abandoned+1 WHERE task_id=?', (task['id'],))
                self.store._state(task['id'], limit_grace=None)
                self.store.audit('assessment-abandoned', row['id'], {'task_id': task['id']}, 'scheduler')
                if self.store.counters(task['id'])['abandoned'] >= 2:
                    self.store.park(task['id'], 'delivery-unresolved', *request(task['id']))
                else:
                    self.store.trigger(task['id'], 'assessment-abandoned', {'execution_id': row['id']})
        for row in db.execute("SELECT * FROM executions WHERE status='pending'").fetchall():
            # A wake that cannot be sent because the supervisor is not there to take it: waiting for a working supervisor is not a failure.
            task = self.store.task(row['task_id'])
            if task.get('contract') != 2 or task['status'] != 'active' or self.now - row['scheduled_at'] < task['limits']['heartbeat_seconds']:
                continue
            state = (self.store.session(self.store.binding(task['supervisor_id'])['session_id']) or {}).get('state', 'unknown')
            if state not in ('unreachable', 'waiting'):
                continue
            with self.store.transaction():
                db.execute("UPDATE executions SET status='abandoned',finished_at=? WHERE id=? AND status='pending'", (self.now, row['id']))
                db.execute("UPDATE outbox SET status='cancelled',updated_at=? WHERE execution_id=? AND status='pending'", (self.now, row['id']))
                db.execute('UPDATE triggers SET execution_id=NULL WHERE execution_id=?', (row['id'],))
                db.execute('UPDATE counters SET abandoned=abandoned+2 WHERE task_id=?', (task['id'],))
                self.store.audit('wake-undeliverable', row['id'], {'task_id': task['id'], 'supervisor_state': state}, 'scheduler')
                self.store.park(task['id'], 'delivery-unresolved', *request(task['id']))
        for row in db.execute("SELECT * FROM deliveries WHERE kind='wake' AND state='unresolved'").fetchall():
            with self.store.transaction():
                db.execute("UPDATE deliveries SET state='lost' WHERE client_id=?", (row['client_id'],))
                db.execute("UPDATE executions SET status='abandoned',finished_at=? WHERE id=? AND status IN ('delivered','uncertain','unhealthy')", (self.now, row['execution_id']))
                db.execute('UPDATE triggers SET execution_id=NULL WHERE execution_id=?', (row['execution_id'],))
                self.store.audit('wake-unresolved', row['client_id'], {'task_id': row['task_id']}, 'scheduler')
                db.execute('UPDATE counters SET abandoned=abandoned+2 WHERE task_id=?', (row['task_id'],))
                self.store.park(row['task_id'], 'delivery-unresolved', *request(row['task_id']))

    def _reviews(self):
        """Launch the fresh-context reviews that were requested, read the verdicts that arrived, and act on them."""
        db = self.store.conn
        with self.store.transaction():
            # A park that waits for its second reading gets one challenge.
            for park in db.execute("SELECT p.id,p.task_id FROM parks p WHERE p.status='challenging' AND NOT EXISTS(SELECT 1 FROM reviews r WHERE r.park_id=p.id)").fetchall():
                self.store.review_request(park['task_id'], 'challenge', 'park', park['id'])
        for row in db.execute("SELECT * FROM reviews WHERE status IN ('requested','running') ORDER BY started_at,id").fetchall():
            entry = dict(row)
            task = self.store.task(entry['task_id'])
            binding = self.store.binding(task['supervisor_id'])
            if entry['status'] == 'requested':
                # An injected transport is a fixture: the native reviewer is launched only by the real tick, or by a stub.
                if self.transport is not None and not os.environ.get('MRCALL_SUPERVISION_REVIEW_COMMAND'):
                    with self.store.transaction():
                        db.execute("UPDATE reviews SET status='unavailable',finished_at=? WHERE id=?", (self.now, entry['id']))
                    verdict = {'unavailable': True}
                elif review.launch(self.store, entry, task, binding, self.codex_path, self.claude_path, self.now) is None:
                    verdict = {'unavailable': True}
                else:
                    verdict = review.collect(self.store, dict(db.execute('SELECT * FROM reviews WHERE id=?', (entry['id'],)).fetchone()), task, self.now)
            else:
                verdict = review.collect(self.store, entry, task, self.now)
            if verdict is None:
                continue
            if entry['kind'] == 'challenge':
                review.apply_challenge(self.store, entry, task, verdict, self.now)
            else:
                review.apply_convergence(self.store, entry, task, verdict, self.now)
        for task in self._tasks(('active',)):
            if self.store.counters(task['id'])['state'].get('review_message'):
                try:
                    review.deliver(self.store, self._bound(self.store.binding(task['supervisor_id']), task), task, self.now)
                except Exception as error:
                    with self.store.transaction():
                        self.store.audit('review-message-unavailable', task['id'], {'error': str(error)}, 'scheduler')

    def _parks(self):
        """The question of a park that took effect goes once to the operator session."""
        db = self.store.conn
        for park in db.execute("SELECT p.* FROM parks p JOIN tasks t ON t.id=p.task_id JOIN bindings b ON b.id=t.supervisor_id WHERE p.status='parked' AND p.question_id IS NULL AND t.status='blocked' AND b.status='active'").fetchall():
            self._question(dict(park))

    def _question(self, park):
        db = self.store.conn
        task = self.store.task(park['task_id'])
        binding = self.store.binding(task['supervisor_id'])
        target = task['operator_session_id']
        retry = self.store.counters(task['id'])['state'].get('question_retry_at')
        if retry and self.now < retry:
            return
        park['request'], park['positions'] = json.loads(park['request']), json.loads(park['positions'])
        event = str(uuid.uuid4())
        body = authority.question(task, park, self.store.registry_message, self.store.spend(task))
        with self.store.transaction():
            if not db.execute('UPDATE parks SET question_id=? WHERE id=? AND question_id IS NULL', (event, park['id'])).rowcount:
                return
        state, detail = 'not-delivered', None
        try:
            # A send that the account ledger cannot record is not made.
            self.store.ledger().record(event, target, 'question', str(self.store.root), task['id'])
            transport = self._bound(binding, task)
        except Exception as error:
            detail = {'error': 'not sent: ' + str(error)}
        else:
            try:
                detail = transport.send(target, event, body, allow_busy=True)
                state = {'delivered': 'queued', 'not-delivered': 'not-delivered'}.get(detail.get('status'), 'uncertain')
            except Exception as error:
                state = 'uncertain' if getattr(error, 'uncertain', True) else 'not-delivered'
                detail = {'error': str(error)}
        with self.store.transaction():
            self.store.delivery_add(event, target, 'question', task['id'], None, body, state, task['limits']['delivery_latest_seconds'], detail, self.now)
            if state == 'not-delivered':
                # A question that was definitely not delivered is offered again later; an uncertain one never is.
                db.execute('UPDATE parks SET question_id=NULL WHERE id=?', (park['id'],))
                self.store._state(task['id'], question_retry_at=self.now + 600)
            else:
                self.store._state(task['id'], question_retry_at=None)
            self.store.audit('question-' + state, park['id'], {'task_id': task['id'], 'session_id': target, 'event_id': event, 'detail': detail}, 'scheduler')

    # ---- clock ----

    def _closing_set(self, task):
        """Targets that own an open item and are not working, and whether any such target was working."""
        owners = {row[0] for row in self.store.conn.execute("SELECT DISTINCT owner FROM items WHERE task_id=? AND status='open'", (task['id'],))}
        members, working = [], False
        for target in task['target_ids']:
            if target not in owners:
                continue
            snapshot = self.store.session(target) or {}
            state = snapshot.get('state', 'unknown')
            if state == 'working':
                working = True
            elif state == 'idle' and snapshot.get('queue') == [] and 'queue' not in snapshot.get('unknown', []):
                members.append({'session_id': target, 'state': 'idle'})
            elif state in ('waiting', 'unreachable'):
                members.append({'session_id': target, 'state': state})
        return members, working

    def _claim(self):
        """An assessment is dispatched only when an observation calls for judgment; the interval is the minimum spacing."""
        db = self.store.conn
        with self.store.transaction():
            count = 0
            for task in self._tasks(('active',)):
                if count >= self.max_dispatch:
                    break
                if task['next_run_at'] > self.now:
                    continue
                if db.execute(f"SELECT 1 FROM executions WHERE supervisor_id=? AND status IN ({','.join('?' * len(OPEN))})", (task['supervisor_id'], *OPEN)).fetchone():
                    continue
                triggers = self.store.pending_triggers(task['id'])
                if not triggers:
                    continue
                last = db.execute('SELECT max(scheduled_at) FROM executions WHERE task_id=?', (task['id'],)).fetchone()[0]
                if last is not None and (task['interval_seconds'] is None or self.now < last + task['interval_seconds']):
                    continue
                binding = self.store.binding(task['supervisor_id'])
                members, working = self._closing_set(task) if task['mode'] == 'completion' else ([], False)
                eid = str(uuid.uuid4())
                event = str(uuid.uuid4())
                carried = [{key: value for key, value in trigger.items() if key != 'sequence'} for trigger in triggers]
                payload = {'execution_id': eid, 'generation': task['generation'], 'cli': self.cli_path, 'state_dir': str(self.store.root),
                           'triggers': [trigger['kind'] for trigger in carried]}
                db.execute('INSERT INTO executions(id,task_id,supervisor_id,generation,binding_generation,status,scheduled_at,lease_until,triggers,closing_set,working) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                           (eid, task['id'], task['supervisor_id'], task['generation'], binding['generation'], 'pending', self.now,
                            self.now + task['limits']['assessment_timeout_seconds'], json.dumps(carried), json.dumps(members), int(working)))
                db.execute('INSERT INTO outbox(id,execution_id,status,payload,client_message_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?)', (event, eid, 'pending', json.dumps(payload), event, self.now, self.now))
                db.execute('UPDATE triggers SET execution_id=? WHERE task_id=? AND execution_id IS NULL', (eid, task['id']))
                db.execute('UPDATE tasks SET updated_at=? WHERE id=?', (self.now, task['id']))
                self.store.audit('execution-claim', eid, payload | {'closing_set': members, 'working': working}, 'scheduler')
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

    def _wake(self, outbox, execution, task, binding):
        """The wake in labeled parts: what is owed, what the operator reserved and limited, then the controller's words."""
        triggers = json.loads(execution['triggers'] or '[]')
        lines = [WAKE, 'Triggers: ' + json.dumps(triggers, sort_keys=True)]
        return authority.render(task, 'THE SUPERVISION CONTROLLER', '\n'.join(lines), self.store.registry_message, self.store.spend(task),
                                'AI_KIT_SUPERVISOR_EVENT ' + outbox['payload'])

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
                    message = self._wake(outbox, execution, task, binding)
                    # A send that the account ledger cannot record is not made.
                    self.store.ledger().record(outbox['client_message_id'], binding['session_id'], 'wake', str(self.store.root), task['id'])
                except Exception as error:
                    self._outcome(outbox, execution, 'not-delivered', 'not sent: ' + str(error))
                    continue
                try:
                    result = transport.send(binding['session_id'], outbox['client_message_id'], message)
                    status = result.get('status', 'uncertain')
                    if status not in ('delivered', 'not-delivered'):
                        status = 'uncertain'
                    self._outcome(outbox, execution, status, result, result.get('native_submission_id'))
                except Exception as error:
                    status = 'uncertain' if getattr(error, 'uncertain', True) else 'not-delivered'
                    self._outcome(outbox, execution, status, str(error))
                if status != 'not-delivered':
                    self.store.delivery_add(outbox['client_message_id'], binding['session_id'], 'wake', task['id'], execution['id'], message,
                                            'queued' if status == 'delivered' else 'uncertain', task['limits']['delivery_latest_seconds'], None, self.now)

    def tick(self):
        if self.store.legacy:
            return {'locked': False, 'legacy': True, 'remedy': LEGACY}
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
                    self.store.conn.execute("UPDATE executions SET status='unhealthy',result=? WHERE id=?", (json.dumps({'assessment_checkpoint_overdue': True, 'unhealthy_at': self.now, 'observation': 'assessment checkpoint exceeded; assess progress; execution authority and task remain active', 'previous_result': json.loads(row['result']) if row['result'] else None}), row['id']))
                    self.store.audit('assessment-overdue', row['id'], {'checkpoint_at': self.now, 'authority_retained': True, 'previous_result': json.loads(row['result']) if row['result'] else None}, 'scheduler')
            self._abandon()
            self._observe()
            self._limits()
            self._reviews()
            self._parks()
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
