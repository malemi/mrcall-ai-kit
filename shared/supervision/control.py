import json
import time

try:
    from .store import StoreError, identity, number, text
except ImportError:
    from store import StoreError, identity, number, text


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
    rows = store.conn.execute("SELECT sequence,at,action,details FROM audit WHERE entity_id=? AND action IN ('intervention-intent','intervention-result') ORDER BY sequence", (event_id,)).fetchall()
    if not rows:
        raise StoreError('unknown intervention event')
    history = [dict(row) | {'details': json.loads(row['details'])} for row in rows]
    return {'event_id': event_id, 'intent': history[0]['details'],
            'result': intervention_result(store, event_id) or {'status': 'uncertain', 'reconciled': False, 'action_completed': False},
            'history': history, 'read_only': True}


def intervene(store, transport, data, reconcile_again=False):
    event_id = identity(data.get('event_id'), 'event_id')
    target = identity(data.get('session_id'), 'session_id')
    instruction = text(data.get('instruction'), 'instruction')
    reason = text(data.get('reason'), 'reason')
    with store.transaction():
        _, task, binding = current_execution(store, data)
        if target not in task['target_ids'] or target not in binding['target_ids']:
            raise StoreError('intervention target is outside exact task targets; workers are read-only')
        intent = {'execution_id': data['execution_id'], 'generation': data['generation'],
                  'session_id': target, 'instruction': instruction, 'reason': reason}
        prior = store.conn.execute("SELECT details FROM audit WHERE action='intervention-intent' AND entity_id=?", (event_id,)).fetchone()
        if prior and json.loads(prior['details']) != intent:
            raise StoreError('event identity already belongs to a different intervention')
        if not prior:
            store.audit('intervention-intent', event_id, intent, 'supervisor')
    with store.transaction():
        _, task, _ = current_execution(store, data)
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
                delivery = transport.send(target, event_id, instruction, allow_busy=True)
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
        return result


def reconcile_intervention(store, transport, event_id):
    receipt = intervention_status(store, event_id)
    return intervene(store, transport, receipt['intent'] | {'event_id': event_id}, reconcile_again=True)
