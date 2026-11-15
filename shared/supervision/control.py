import json
import time
import uuid

try:
    from .store import LEGACY, StoreError, identity, number, text
    from . import authority, observe
except ImportError:
    from store import LEGACY, StoreError, identity, number, text
    import authority
    import observe


def current_execution(store, data):
    execution_id = text(data.get('execution_id'), 'execution_id')
    generation = number(data.get('generation'), 'generation')
    row = store.conn.execute('SELECT * FROM executions WHERE id=?', (execution_id,)).fetchone()
    if row is None:
        raise StoreError('unknown execution')
    task = store.task(row['task_id'])
    binding = store.binding(row['supervisor_id'])
    if (binding['status'] != 'active' or task['status'] != 'active' or
            row['generation'] != generation or task['generation'] != generation or
            row['binding_generation'] != binding['generation'] or
            row['status'] not in ('running', 'delivered', 'unhealthy')):
        raise StoreError('stale or inactive execution authority')
    return row, task, binding


def session_read(store, transport, data):
    target = identity(data.get('session_id'), 'session_id')
    direction = data.get('sort_direction', 'desc')
    if direction not in ('asc', 'desc'):
        raise StoreError('sort_direction must be asc or desc')
    with store.transaction():
        _, task, _ = current_execution(store, data)
        deadline = time.monotonic() + min(30, task['limits']['transport_timeout_seconds'])
        selected = target
        seen = set()
        while selected not in task['target_ids']:
            if selected in seen:
                raise StoreError('native parent ancestry contains a cycle')
            seen.add(selected)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise StoreError('native parent ancestry deadline exceeded; membership unverified')
            if hasattr(transport, 'timeout'):
                transport.timeout = remaining
            metadata = transport.metadata(selected)
            if metadata.get('id') != selected:
                raise StoreError('native ancestry identity mismatch')
            selected = metadata.get('parentThreadId')
            if not selected:
                raise StoreError('session is outside the task target ancestry')
            selected = identity(selected, 'parentThreadId')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise StoreError('session read deadline exceeded')
        if hasattr(transport, 'timeout'):
            transport.timeout = remaining
        result = transport.read(target, cursor=data.get('cursor'), sort_direction=direction)
        return {'authorized_root': selected, **result}


def intervention_result(store, event_id):
    row = store.conn.execute("SELECT details FROM audit WHERE action='intervention-result' AND entity_id=? ORDER BY sequence DESC LIMIT 1", (event_id,)).fetchone()
    return json.loads(row['details']) if row else None


def intervention_status(store, event_id):
    event_id = identity(event_id, 'event_id')
    rows = store.conn.execute("SELECT sequence,at,action,details FROM audit WHERE entity_id=? AND action IN ('intervention-intent','intervention-message','intervention-result') ORDER BY sequence", (event_id,)).fetchall()
    if not rows:
        raise StoreError('unknown intervention event')
    history = [dict(row) | {'details': json.loads(row['details'])} for row in rows]
    result = intervention_result(store, event_id) or {'status': 'uncertain', 'reconciled': False, 'action_completed': False}
    delivery = None if store.legacy else store.delivery(event_id)
    if delivery:
        # The receipt Python keeps: queued until the message is found in the target's history, then consumed.
        result = result | {'receipt': {key: delivery[key] for key in ('state', 'sent_at', 'latest_at', 'consumed_at', 'turn_id')}}
    return {'event_id': event_id, 'intent': history[0]['details'], 'result': result, 'history': history, 'read_only': True}


def admit(store, transport, row, task, binding, target):
    """Whether a new message may go to this target now, judged from a fresh observation of it."""
    if task['mode'] == 'observation':
        raise StoreError('an observation task reads and reports: intervene is refused')
    seen = observe.refresh(store, lambda _binding: transport, [target], time.time())
    fresh = seen.get(target) or {}
    snapshot = fresh.get('snapshot') or {}
    if fresh.get('failed') or 'queue' in snapshot.get('unknown', []) or snapshot.get('queue') is None:
        raise StoreError('the native queue of the target could not be read, so nothing was sent: retry when the session is readable')
    if snapshot['queue']:
        raise StoreError("the target's native queue already holds a message, so nothing was sent: wait until it is consumed (status shows "
                         'each delivery) before sending another')
    if fresh['state'] in ('waiting', 'unreachable', 'unknown'):
        raise StoreError(f"the target is {fresh['state']}, so a message cannot reach it now and nothing was sent: close the assessment "
                         'for it with a wait, a park or a conclusion')
    triggers = json.loads(row['triggers'] or '[]')
    if fresh['state'] == 'working' and triggers and all(trigger['kind'] == 'heartbeat' for trigger in triggers):
        raise StoreError('long active work receives no message because time passed: this assessment was raised by the heartbeat alone '
                         'and the target is working, so nothing was sent')


def intervene(store, transport, data, reconcile_again=False):
    event_id = identity(data.get('event_id'), 'event_id')
    target = identity(data.get('session_id'), 'session_id')
    instruction = text(data.get('instruction'), 'instruction')
    reason = text(data.get('reason'), 'reason')
    intent = {'execution_id': data.get('execution_id'), 'generation': data.get('generation'),
              'session_id': target, 'instruction': instruction, 'reason': reason}
    with store.transaction():
        row, task, binding = current_execution(store, data)
        if target not in task['target_ids'] or target not in binding['target_ids']:
            raise StoreError('intervention target is outside exact task targets; workers are read-only')
        prior = store.conn.execute("SELECT details FROM audit WHERE action='intervention-intent' AND entity_id=?", (event_id,)).fetchone()
        if prior and json.loads(prior['details']) != intent:
            raise StoreError('event identity already belongs to a different intervention')
    current = task.get('contract') == 2
    message = instruction
    if not current and not prior:
        # A root of the earlier schema has no ledger and no queue rule: nothing new is sent from it.
        raise StoreError(LEGACY)
    if current and not prior:
        # Refusals come before the intent is recorded: a refused send leaves nothing to reconcile.
        admit(store, transport, row, task, binding, target)
        message = authority.render(task, 'THE SUPERVISOR', instruction, store.registry_message, store.spend(task),
                                   'AI_KIT_SUPERVISION_MESSAGE ' + json.dumps({'event_id': event_id, 'task_id': task['id']}))
        try:
            store.ledger().record(event_id, target, 'intervention', str(store.root), task['id'])
        except Exception as error:
            raise StoreError('the account ledger could not record the message, so it was not sent: ' + str(error)) from None
    with store.transaction():
        _, task, _ = current_execution(store, data)
        if not prior and not store.conn.execute("SELECT 1 FROM audit WHERE action='intervention-intent' AND entity_id=?", (event_id,)).fetchone():
            store.audit('intervention-intent', event_id, intent, 'supervisor')
        result = intervention_result(store, event_id)
        if result and (result['status'] != 'uncertain' or (result.get('reconciled') and not reconcile_again)):
            return result | {'replayed': True}
        if hasattr(transport, 'timeout'):
            transport.timeout = min(30, task['limits']['transport_timeout_seconds'])
        reconcile = bool(prior or result)
        try:
            if reconcile:
                delivery = transport.reconcile(target, event_id)
                status = 'delivered' if delivery.get('status') == 'delivered' else 'uncertain'
            else:
                store.audit('intervention-message', event_id, {'text': message}, 'supervisor')
                delivery = transport.send(target, event_id, message, allow_busy=True)
                status = delivery.get('status', 'uncertain')
                if status not in ('delivered', 'not-delivered'):
                    status = 'uncertain'
        except Exception as error:
            delivery = {'error': str(error)}
            status = 'uncertain' if reconcile or getattr(error, 'uncertain', True) else 'not-delivered'
        result = {'event_id': event_id, 'session_id': target, 'status': status,
                  'delivery': delivery, 'reconciled': reconcile,
                  'action_completed': False, 'task_state_changed': False}
        store.audit('intervention-result', event_id, result, 'supervisor')
        if current:
            state = {'delivered': 'queued', 'not-delivered': 'not-delivered'}.get(status, 'uncertain')
            if not reconcile:
                store.delivery_add(event_id, target, 'intervention', task['id'], data['execution_id'], message, state,
                                   task['limits']['delivery_latest_seconds'], delivery)
            elif status == 'delivered':
                store.conn.execute("UPDATE deliveries SET state='queued' WHERE client_id=? AND state='uncertain'", (event_id,))
            result['receipt'] = (store.delivery(event_id) or {}).get('state')
        return result


def reconcile_intervention(store, transport, event_id):
    receipt = intervention_status(store, event_id)
    return intervene(store, transport, receipt['intent'] | {'event_id': event_id}, reconcile_again=True)


def notice(store, transport, data):
    """One rendered notice to a session of the binding. It replaces every contact outside the CLI, the end notice included."""
    store.current()
    task = store.task(text(data.get('task_id'), 'task_id'))
    if task.get('contract') != 2:
        raise StoreError('notice needs a task of this state root')
    binding = store.binding(task['supervisor_id'])
    target = identity(data.get('session_id'), 'session_id')
    if binding['status'] != 'active' or target not in [binding['session_id'], *binding['target_ids'], task['operator_session_id']]:
        raise StoreError('a notice goes to a session of the active binding or to the operator session of its task')
    body = text(data.get('text'), 'text')
    event_id = identity(data.get('event_id', str(uuid.uuid4())), 'event_id')
    existing = store.delivery(event_id)
    if existing:
        return {'event_id': event_id, 'session_id': existing['session_id'], 'receipt': existing['state'], 'replayed': True}
    if task['mode'] == 'observation' and target in task['target_ids']:
        raise StoreError('an observation task reads and reports: its targets receive nothing, a notice included')
    if store.conn.execute("SELECT 1 FROM deliveries WHERE task_id=? AND session_id=? AND kind='notice' AND state!='not-delivered'", (task['id'], target)).fetchone():
        raise StoreError('this session already received the notice of this task; a notice is sent once and is not a way to instruct a session')
    message = authority.render(task, 'THE SUPERVISOR', body, store.registry_message, store.spend(task),
                               'AI_KIT_SUPERVISION_NOTICE ' + json.dumps({'event_id': event_id, 'task_id': task['id']}))
    try:
        store.ledger().record(event_id, target, 'notice', str(store.root), task['id'])
    except Exception as error:
        raise StoreError('the account ledger could not record the notice, so it was not sent: ' + str(error)) from None
    if hasattr(transport, 'timeout'):
        transport.timeout = min(30, task['limits']['transport_timeout_seconds'])
    try:
        delivery = transport.send(target, event_id, message, allow_busy=True)
        state = {'delivered': 'queued', 'not-delivered': 'not-delivered'}.get(delivery.get('status'), 'uncertain')
    except Exception as error:
        delivery = {'error': str(error)}
        state = 'uncertain' if getattr(error, 'uncertain', True) else 'not-delivered'
    with store.transaction():
        store.delivery_add(event_id, target, 'notice', task['id'], None, message, state, task['limits']['delivery_latest_seconds'], delivery)
        store.audit('notice', event_id, {'task_id': task['id'], 'session_id': target, 'text': message, 'state': state}, data.get('actor', 'supervisor'))
    return {'event_id': event_id, 'session_id': target, 'receipt': state, 'delivery': delivery, 'action_completed': False}
