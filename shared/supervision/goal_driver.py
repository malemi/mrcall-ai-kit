"""Python owns continuation; native reports never own goal termination."""
import fcntl
import json
import os
from pathlib import Path
import time

from goal_child import run_child
from goal_store import AdmissionDenied
from ledger import Ledger


class NativeError(RuntimeError):
    def __init__(self, message, uncertain=True):
        super().__init__(message)
        self.uncertain = uncertain


class Driver:
    def __init__(self, config, store, acceptance):
        self.config = config
        self.store = store
        self.acceptance = acceptance
        self.root = Path(config['root'])
        self.cadence = config.get('cadence_seconds', 180)

    def native(self, goal, operation, session_id, **arguments):
        timeout = min(12, goal['limits']['process_timeout_seconds'])
        data = {'operation': operation, 'session_id': session_id, 'timeout': max(0.001, timeout - 0.1),
                'codex_path': self.config.get('codex_path'), 'socket_path': self.config.get('native_socket'), **arguments}
        try:
            result = run_child(['/usr/bin/python3', '-I', str(self.root / 'code' / 'goal_native.py'), json.dumps(data)],
                               uid=self.config['agent_uid'], gid=self.config['agent_gid'], home=self.config['agent_home'],
                               cwd=self.config['agent_home'], timeout=timeout,
                               admission=lambda: self.store.admission(goal['id'], goal['generation']))
        except AdmissionDenied as error:
            raise NativeError(str(error), uncertain=False) from error
        try:
            response = json.loads(result['stdout'])
        except (ValueError, TypeError):
            raise NativeError('Native bridge returned no valid result: ' + result.get('stderr', '')) from None
        if result['termination'] or response.get('ok') is not True or result['exit_code'] != 0:
            raise NativeError(response.get('error', 'Native bridge failed'), uncertain=response.get('uncertain', True))
        return response['result']

    def record_in_ledger(self, event_id, session_id, goal_id):
        path = self.config.get('ledger_path')
        if not path:
            return None
        try:
            ledger = Ledger(path)
        except Exception as error:
            return f'ledger unavailable: {error}'
        try:
            ledger.record(event_id, session_id, 'goal', str(self.root), task_id=goal_id)
        except Exception as error:
            return f'ledger record failed: {error}'
        finally:
            ledger.close()
        return None

    def tick(self, force=False):
        descriptor = os.open(self.root / 'state' / 'driver.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {'locked': True}
            observations = []
            for goal in self.store.open_goals():
                if not force and not goal.get('check_requested') and (goal.get('next_due_at') or 0) > time.time():
                    continue
                try:
                    observation = self.advance_goal(goal)
                except Exception as error:
                    observation = {'error': str(error), 'remaining': 'Goal remains pending; no success inferred'}
                self.store.observe(goal['id'], goal['generation'], observation, self.cadence)
                observations.append({'id': goal['id'], **observation})
            return {'locked': False, 'observations': observations}
        finally:
            os.close(descriptor)

    @staticmethod
    def outstanding(event):
        return event['status'] not in ('consumed', 'not-delivered')

    def advance_goal(self, goal):
        if self.store.deadline_reached(goal):
            return {'limit': 'deadline_at'}
        consumed_lead = False
        outbox = self.store.get(goal['id'])['outbox']
        latest_lead = next((event['id'] for event in reversed(outbox) if event['role'] == 'lead' and event['status'] != 'not-delivered'), None)
        for event in outbox:
            if not self.outstanding(event) and event['id'] != latest_lead:
                continue
            try:
                receipt = self.native(goal, 'reconcile', event['session_id'], event_id=event['id'], include_activity=event['role'] == 'lead')
                if (receipt.get('status') == 'delivered' and receipt.get('location') == 'history'
                        and receipt.get('turn_status') in ('completed', 'failed', 'interrupted')
                        and receipt.get('event_id') == event['id']):
                    self.store.record_delivery(event['id'], 'consumed', receipt)
                    consumed_lead |= event['role'] == 'lead' and event['status'] != 'consumed'
                elif event['status'] == 'consumed':
                    self.store.record_delivery(event['id'], 'consumed', {**event.get('observation', {}), 'activity': {'classification': 'unknown'}})
                elif receipt.get('status') == 'delivered':
                    self.store.record_delivery(event['id'], 'delivered', receipt)
                else:
                    self.store.record_delivery(event['id'], 'uncertain', receipt)
            except NativeError as error:
                if event['status'] == 'consumed':
                    self.store.record_delivery(event['id'], 'consumed', {**event.get('observation', {}), 'activity': {'classification': 'unknown', 'diagnostic': str(error)}})
                else:
                    self.store.record_delivery(event['id'], 'uncertain', {'error': str(error)})

        current = self.store.get(goal['id'])
        if current['generation'] != goal['generation'] or current['status'] != 'open':
            return {'fenced': True}
        pending = {e['session_id'] for e in current['outbox'] if self.outstanding(e)}
        activity = {}
        for role in ('lead', 'supervisor'):
            session_id = goal['target'][role + '_id']
            try:
                metadata = self.native(goal, 'metadata', session_id)
                valid = metadata.get('id') == session_id and metadata.get('canAcceptDirectInput') is True and not metadata.get('parentThreadId')
                status = metadata.get('status')
                activity[role] = (status.get('type') if isinstance(status, dict) else status) if valid else 'unknown'
            except NativeError:
                activity[role] = 'unknown'

        lead_event = next((event for event in reversed(current['outbox']) if event['role'] == 'lead' and event['status'] != 'not-delivered'), None)
        lead_activity = {'classification': 'unknown'}
        if lead_event and lead_event['status'] == 'consumed':
            lead_activity = lead_event.get('observation', {}).get('activity', lead_activity)
        # Only inspect a stable idle candidate, never race useful in-flight work.
        if not pending and lead_activity.get('classification') != 'active' and all(value == 'idle' for value in activity.values()) and (
                current.get('check_requested') or current.get('last_receipt') is None or consumed_lead):
            attempt = self.store.begin_check(goal['id'], goal['generation'])
            try:
                result = self.acceptance.run(current, admission=lambda: self.store.admission(goal['id'], goal['generation']))
            except Exception as error:
                result = {'passed': False, 'receipt': {}, 'diagnostic': str(error)}
            self.store.finish_check(goal['id'], goal['generation'], attempt, result)
            current = self.store.get(goal['id'])
            if current['status'] != 'open' or current['generation'] != goal['generation']:
                return {'acceptance': current['status'], 'attempt_id': attempt['id']}

        correction = bool(lead_event and lead_event.get('failed_attempt_id') and
                          current.get('last_receipt', {}).get('passed') is False and
                          lead_activity.get('classification') == 'no_work')
        dispatched = []
        for role in ('lead', 'supervisor'):
            session_id = goal['target'][role + '_id']
            if activity[role] != 'idle' or session_id in pending or (role == 'lead' and lead_activity.get('classification') == 'active'):
                continue
            intervention = {'kind': 'stasis_correction', 'source_event_id': lead_event['id'], 'activity': lead_activity} if role == 'lead' and correction else None
            message = self.message(current, role, intervention)
            event = self.store.reserve_wake(goal['id'], goal['generation'], session_id, role, message, intervention=intervention)
            if event is None:
                continue
            ledger_error = self.record_in_ledger(event['id'], session_id, goal['id'])
            if ledger_error is not None:
                self.store.record_delivery(event['id'], 'not-delivered', {'error': ledger_error})
            else:
                try:
                    receipt = self.native(goal, 'send', session_id, event_id=event['id'], message=message)
                    status = 'delivered' if receipt.get('status') == 'delivered' else 'uncertain'
                    self.store.record_delivery(event['id'], status, receipt)
                except NativeError as error:
                    self.store.record_delivery(event['id'], 'uncertain' if error.uncertain else 'not-delivered', {'error': str(error)})
            dispatched.append(event['id'])
        if not dispatched and not pending and lead_activity.get('classification') != 'active' and all(v == 'idle' for v in activity.values()):
            self.store.mark_exhausted(goal['id'], goal['generation'])
        return {'activity': activity, 'lead_activity': lead_activity, 'pending_sessions': sorted(pending), 'dispatched': dispatched}

    def message(self, goal, role, intervention=None):
        data = {'goal_id': goal['id'], 'generation': goal['generation'], 'role': role,
                'socket': str(self.root / 'control.sock'), 'client': str(self.root / 'code' / 'goal_client.py')}
        action = ('Continue the unfinished authorized assignment. Use the recorded failure to choose the next concrete action; '
                  'do not repeat an unchanged failed operation. Use plan, execute, verify, reviewer, or debugger as the actual work requires.')
        if intervention:
            data['intervention'] = {'kind': intervention['kind'], 'source_event_id': intervention['source_event_id']}
            action = ('Automatic correction: the completed lead wake and all observed newer turns contained no concrete execution after failed acceptance. '
                      'Reports and goal bookkeeping do not satisfy this obligation. Take a new authorized concrete step now, using the failure evidence. '
                      'If every remaining step requires indispensable operator input, state the precise decision or authority needed and advance any independent authorized work. '
                      'Do not repeat an unchanged failed operation or retry an operation whose authorized allowance has been consumed. This grants no new spending, paid admission, release or installation authority. '
                      'Conserve tokens, reuse valid evidence, and remain within all operator limits.')
        if role == 'supervisor':
            action = ('Check the lead progress and drive the next authorized action toward acceptance. '
                      'An idle unfinished lead requires correction, not merely a blocked report. '
                      'Respect pending messages and do not duplicate a wake already sent by this controller.')
        return ('AI_KIT_GOAL_EVENT ' + json.dumps(data) + '\n'
                'This is an automated continuation of the recorded mandate, not new operator authorization.\n'
                'Goal: ' + goal['intent'] + '\nAuthorized scope: ' + goal['scope'] + '\n'
                'Remaining: ' + str(goal.get('pending_obligation')) + '\n' + action + '\n'
                'Read the goal through the protected client inspect operation; report progress and request acceptance with check_request. '
                'Agent reports never stop or complete this goal. Missing indispensable authority stays an obligation; advance independent authorized work. '
                'Conserve tokens, reuse valid evidence, propagate that discipline to workers and respect operator limits.')
