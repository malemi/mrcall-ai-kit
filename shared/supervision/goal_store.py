import contextlib
import datetime
import json
import sqlite3
import time
import uuid


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class AdmissionDenied(ValueError):
    """The current generation refused an action before its process was launched."""


class GoalStore:
    def __init__(self, path):
        self.path = str(path)
        with self.transaction() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("unsupported goal database schema")
            db.execute("CREATE TABLE IF NOT EXISTS goals (id TEXT PRIMARY KEY, document TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS audit (sequence INTEGER PRIMARY KEY AUTOINCREMENT, goal_id TEXT NOT NULL, timestamp TEXT NOT NULL, event TEXT NOT NULL, payload TEXT NOT NULL)")
            for table in ("attempts", "outbox", "receipts"):
                db.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, goal_id TEXT NOT NULL, generation INTEGER NOT NULL, document TEXT NOT NULL)")
            db.execute("PRAGMA user_version=1")

    @contextlib.contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _read(self, db, goal_id):
        row = db.execute("SELECT document FROM goals WHERE id=?", (goal_id,)).fetchone()
        if row is None:
            raise ValueError("unknown goal")
        return json.loads(row[0])

    def _write(self, db, goal, event, payload):
        goal["updated_at"] = now()
        db.execute("UPDATE goals SET document=? WHERE id=?", (encode(goal), goal["id"]))
        db.execute("INSERT INTO audit(goal_id,timestamp,event,payload) VALUES(?,?,?,?)", (goal["id"], now(), event, encode(payload)))

    def get(self, goal_id):
        with self.transaction() as db:
            goal = self._read(db, goal_id)
            goal['outbox'] = [json.loads(r[0]) for r in db.execute('SELECT document FROM outbox WHERE goal_id=? ORDER BY rowid', (goal_id,))]
            return goal

    def create(self, contract):
        goal = dict(contract)
        goal.update(status="open", generation=1, created_at=now(), updated_at=now(), wakeups_reserved=0, next_due_at=None, reports=[], check_requested=False, pending_obligation="Acceptance has not been verified")
        with self.transaction() as db:
            sessions = {goal['target']['lead_id'], goal['target']['supervisor_id']}
            if len(sessions) != 2:
                raise ValueError('lead and supervisor must be distinct sessions')
            for session in sessions:
                if str(uuid.UUID(session)) != session:
                    raise ValueError('canonical native session UUID required')
            for row in db.execute('SELECT document FROM goals'):
                other = json.loads(row[0])
                if other['status'] == 'open' and sessions.intersection((other['target']['lead_id'], other['target']['supervisor_id'])):
                    raise ValueError('a native session already belongs to an open goal')
            db.execute("INSERT INTO goals VALUES (?,?)", (goal["id"], encode(goal)))
            self._write(db, goal, "created", contract)
        return goal

    def apply(self, goal_id, generation, operation, payload=None):
        with self.transaction() as db:
            goal = self._read(db, goal_id)
            if goal["generation"] != generation:
                raise ValueError("stale generation")
            if operation == "report":
                if goal['status'] != 'open':
                    raise ValueError('goal is not open')
                goal["reports"].append({"timestamp": now(), "report": payload})
                goal["pending_obligation"] = "Review latest agent report; acceptance remains unverified"
            elif operation == "check_request":
                if goal['status'] != 'open':
                    raise ValueError('goal is not open')
                goal["check_requested"] = True
            elif operation in ("stop", "resume", "set_limits"):
                goal["generation"] += 1
                if operation == "set_limits":
                    goal["limits"] = payload
                else:
                    if operation == 'resume' and goal['status'] == 'completed':
                        raise ValueError('verified completion is immutable; create a new goal')
                    if operation == 'resume':
                        sessions = {goal['target']['lead_id'], goal['target']['supervisor_id']}
                        for row in db.execute('SELECT document FROM goals WHERE id!=?', (goal_id,)):
                            other = json.loads(row[0])
                            if other['status'] == 'open' and sessions.intersection((other['target']['lead_id'], other['target']['supervisor_id'])):
                                raise ValueError('native session already belongs to another open goal')
                    goal["status"] = "stopped" if operation == "stop" else "open"
            else:
                raise ValueError("unsupported store operation")
            self._write(db, goal, operation, payload)
            return goal

    def fence(self, goal_id, generation):
        with self.transaction() as db:
            goal = self._read(db, goal_id)
            return goal["generation"] == generation and goal["status"] == "open"

    def open_goals(self):
        with self.transaction() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT document FROM goals') if json.loads(r[0])['status'] == 'open']

    @staticmethod
    def deadline_reached(goal):
        value = goal['limits'].get('deadline_at')
        return value is not None and datetime.datetime.now(datetime.timezone.utc) >= datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))

    def _eligible(self, db, goal_id, generation):
        goal = self._read(db, goal_id)
        if goal['generation'] != generation or goal['status'] != 'open' or self.deadline_reached(goal):
            raise AdmissionDenied('stale, stopped or deadline-limited goal admission')
        return goal

    @contextlib.contextmanager
    def admission(self, goal_id, generation):
        # Lock only through the actual launch, never through a long child wait.
        with self.transaction() as db:
            self._eligible(db, goal_id, generation)
            yield

    def observe(self, goal_id, generation, observation, cadence):
        with self.transaction() as db:
            goal = self._read(db, goal_id)
            if goal['generation'] != generation or goal['status'] != 'open':
                return
            goal['last_observation'] = observation
            goal['next_due_at'] = time.time() + cadence
            if self.deadline_reached(goal):
                goal['status'] = 'limited'
                goal['pending_obligation'] = 'Operator deadline reached; unfinished acceptance retained'
                goal['generation'] += 1
            self._write(db, goal, 'observation', observation)

    def reserve_wake(self, goal_id, generation, session_id, role, message, intervention=None):
        with self.transaction() as db:
            goal = self._eligible(db, goal_id, generation)
            # Outstanding sends survive stop/resume and generation changes.
            for row in db.execute('SELECT document FROM outbox WHERE goal_id=?', (goal_id,)):
                event = json.loads(row[0])
                if event['session_id'] == session_id and event['status'] not in ('consumed', 'not-delivered'):
                    return None
            cap = goal['limits'].get('max_wakeups')
            if cap is not None and goal['wakeups_reserved'] >= cap:
                goal['last_observation'] = {'limit': 'max_wakeups', 'remaining': goal['pending_obligation']}
                self._write(db, goal, 'wake-limit', goal['last_observation'])
                return None
            event_id = str(uuid.uuid4())
            event = {'id': event_id, 'goal_id': goal_id, 'generation': generation, 'session_id': session_id, 'role': role, 'status': 'sending', 'message': message, 'created_at': now()}
            if goal.get('last_receipt', {}).get('passed') is False:
                event['failed_attempt_id'] = goal['last_receipt']['attempt_id']
            if intervention is not None:
                event['intervention'] = intervention
            db.execute('INSERT INTO outbox VALUES (?,?,?,?)', (event_id, goal_id, generation, encode(event)))
            goal['wakeups_reserved'] += 1
            self._write(db, goal, 'wake-reserved', {'event_id': event_id, 'session_id': session_id})
            return event

    def record_delivery(self, event_id, status, observation):
        if status not in ('delivered', 'uncertain', 'not-delivered', 'consumed'):
            raise ValueError('invalid delivery state')
        with self.transaction() as db:
            row = db.execute('SELECT document FROM outbox WHERE id=?', (event_id,)).fetchone()
            if row is None:
                raise ValueError('unknown dispatch')
            event = json.loads(row[0])
            if event['status'] == 'consumed' and status != 'consumed':
                return
            event.update(status=status, observation=observation, updated_at=now())
            db.execute('UPDATE outbox SET document=? WHERE id=?', (encode(event), event_id))
            # Delivery observations remain useful after an operator fence.
            db.execute('INSERT INTO audit(goal_id,timestamp,event,payload) VALUES(?,?,?,?)', (event['goal_id'], now(), 'delivery', encode(event)))

    def begin_check(self, goal_id, generation):
        with self.transaction() as db:
            goal = self._eligible(db, goal_id, generation)
            attempt = {'id': str(uuid.uuid4()), 'generation': generation, 'status': 'running', 'started_at': now()}
            db.execute('INSERT INTO attempts VALUES (?,?,?,?)', (attempt['id'], goal_id, generation, encode(attempt)))
            goal['last_attempt'] = attempt
            goal['check_requested'] = False
            self._write(db, goal, 'check-started', attempt)
            return attempt

    def finish_check(self, goal_id, generation, attempt, result):
        with self.transaction() as db:
            goal = self._read(db, goal_id)
            valid = goal['generation'] == generation and goal['status'] == 'open' and not self.deadline_reached(goal)
            receipt = dict(result.get('receipt') or {})
            receipt.setdefault('id', attempt['id'])
            receipt.update(attempt_id=attempt['id'], passed=result.get('passed') is True, generation=generation, accepted=valid, diagnostic=result.get('diagnostic', ''))
            attempt = dict(attempt, status='passed' if receipt['passed'] else 'failed', finished_at=now(), accepted=valid)
            db.execute('UPDATE attempts SET document=? WHERE id=?', (encode(attempt), attempt['id']))
            db.execute('INSERT INTO receipts VALUES (?,?,?,?)', (attempt['id'], goal_id, generation, encode(receipt)))
            if valid:
                goal['last_attempt'] = attempt
                goal['last_receipt'] = receipt
                goal['pending_obligation'] = result.get('diagnostic') or 'Acceptance failed; investigate and continue'
                if receipt['passed']:
                    goal['status'] = 'completed'
                    goal['pending_obligation'] = None
            self._write(db, goal, 'check-result', receipt)

    def mark_exhausted(self, goal_id, generation):
        with self.transaction() as db:
            goal = self._read(db, goal_id)
            if goal['status'] != 'open' or goal['generation'] != generation:
                return
            cap = goal['limits'].get('max_wakeups')
            if cap is None or goal['wakeups_reserved'] < cap:
                return
            pending = [json.loads(r[0]) for r in db.execute('SELECT document FROM outbox WHERE goal_id=?', (goal_id,))]
            if any(e['status'] not in ('consumed', 'not-delivered') for e in pending):
                return
            goal['status'] = 'limited'
            goal['generation'] += 1
            goal['pending_obligation'] = 'Operator wakeup allowance exhausted; unfinished acceptance retained'
            self._write(db, goal, 'wake-limit-reached', {'max_wakeups': cap})
