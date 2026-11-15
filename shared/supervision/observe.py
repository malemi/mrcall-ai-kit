"""Python observes the sessions: what it reads is stored, and what changed raises triggers."""
import hashlib
import json
import os
import time

try:
    from .store import OPEN_EXECUTIONS, StoreError, session_state
    from . import authority
except ImportError:
    from store import OPEN_EXECUTIONS, StoreError, session_state
    import authority


CLAUDE_ENVELOPE = '<cross-session-message from-name="ai-kit-supervisor">'
THRESHOLDS = (0.5, 1.0)


def classify(message, known, epoch):
    """Origin of a user message and the rule that decided it. Provenance for well-behaved runs, not authentication."""
    body = message['text'].lstrip()
    if message.get('client_id') in known:
        return 'kit', 'ledger'
    if body.startswith(authority.MARKERS) or body.startswith(CLAUDE_ENVELOPE):
        return 'kit', 'envelope'
    if message.get('inter_agent'):
        return 'inter-agent', 'runtime'
    if message.get('at') is None or message['at'] < epoch:
        return 'unknown', 'epoch'
    return 'operator', 'default'


def reference(session_id, message_id):
    return 'op-' + hashlib.sha256((session_id + ':' + message_id).encode()).hexdigest()[:10]


def log(store, session_id, kind, data, now):
    store.conn.execute('INSERT INTO observations(at,session_id,kind,data) VALUES(?,?,?,?)', (now, session_id, kind, json.dumps(data, allow_nan=False)))


def store_messages(store, session_id, messages, now):
    """Record user messages not yet stored, each with its origin; return the new ones."""
    ledger = store.ledger()
    known = ledger.known([message['client_id'] for message in messages if message.get('client_id')])
    epoch = ledger.epoch()
    fresh = []
    for message in messages:
        if store.conn.execute('SELECT 1 FROM messages WHERE session_id=? AND id=?', (session_id, message['id'])).fetchone():
            continue
        origin, rule = classify(message, known, epoch)
        ref = reference(session_id, message['id']) if origin == 'operator' else None
        store.conn.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?,?)',
                           (session_id, message['id'], message.get('turn_id'), message.get('client_id'), message.get('at'), origin, ref, message['text'], now))
        log(store, session_id, 'message', {'id': message['id'], 'origin': origin, 'rule': rule, 'ref': ref}, now)
        fresh.append({'id': message['id'], 'origin': origin, 'rule': rule, 'ref': ref, 'at': message.get('at'), 'turn_id': message.get('turn_id')})
    return fresh


def observe_session(store, transport, session_id, runtime, now, workers_since=None):
    """Read one session with no model call and store what was read.

    Returns what changed since the previous observation. The first observation of a session is its
    baseline: everything is stored and nothing is reported as a change.
    """
    db = store.conn
    row = db.execute('SELECT * FROM sessions WHERE session_id=?', (session_id,)).fetchone()
    previous = json.loads(row['snapshot']) if row else {}
    before = session_state(previous | {'stale_since': row['stale_since']}) if row else 'unknown'
    cursor = json.loads(row['cursor']) if row and row['cursor'] else None
    try:
        seen = transport.observe(session_id, cursor=cursor, workers_since=workers_since)
    except Exception as error:
        with store.transaction():
            if row is None:
                db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)', (session_id, runtime, json.dumps({'unknown': ['status']}), None, now, now))
            elif row['stale_since'] is None:
                db.execute('UPDATE sessions SET stale_since=? WHERE session_id=?', (now, session_id))
            if row is None or row['stale_since'] is None:
                log(store, session_id, 'read-failed', {'error': str(error)}, now)
        return {'session_id': session_id, 'failed': str(error), 'state': 'unknown', 'previous_state': before,
                'ended': [], 'messages': [], 'deliveries': [], 'snapshot': previous}
    unknown = list(seen.get('unknown') or [])
    snapshot = dict(previous)
    snapshot.update(status=seen.get('status'), flags=seen.get('flags') or [], can_accept_input=seen.get('can_accept_input'), unknown=unknown)
    if 'queue' not in unknown:
        snapshot['queue'] = seen.get('queue') or []
    turns = [] if 'turns' in unknown else (seen.get('turns') or [])
    running = [turn for turn in turns if turn['status'] == 'inProgress']
    ended = [turn for turn in turns if turn['status'] != 'inProgress']
    held = previous.get('running_turn')
    if running:
        snapshot['running_turn'] = {'id': running[-1]['id'], 'started_at': running[-1].get('started_at')}
    elif seen.get('status') != 'active' or held and any(turn['id'] == held['id'] for turn in ended):
        snapshot['running_turn'] = None
    if ended:
        snapshot['last_turn'] = {'id': ended[-1]['id'], 'status': ended[-1]['status'], 'completed_at': ended[-1].get('completed_at')}
    for key in ('usage', 'allowance'):
        if seen.get(key):
            snapshot[key] = seen[key]
    workers = dict(previous.get('workers') or {})
    for worker in seen.get('workers') or []:
        workers[worker['id']] = {'usage': worker.get('usage') or (workers.get(worker['id']) or {}).get('usage'), 'created_at': worker.get('created_at')}
    snapshot['workers'] = workers
    after = session_state(snapshot)
    changed = []
    with store.transaction():
        fresh = store_messages(store, session_id, [] if 'messages' in unknown else (seen.get('messages') or []), now)
        if row is not None:
            for turn in running:
                if not held or held['id'] != turn['id']:
                    log(store, session_id, 'turn-started', turn, now)
            for turn in ended:
                log(store, session_id, 'turn-ended', turn, now)
        if previous.get('status') != snapshot['status'] or (previous.get('flags') or []) != snapshot['flags']:
            log(store, session_id, 'status', {'status': snapshot['status'], 'flags': snapshot['flags']}, now)
        if 'queue' not in unknown and previous.get('queue') != snapshot['queue']:
            log(store, session_id, 'queue', {'client_ids': [entry.get('client_id') for entry in snapshot['queue']]}, now)
        if (previous.get('usage') or {}).get('total') != (snapshot.get('usage') or {}).get('total'):
            log(store, session_id, 'counter', snapshot.get('usage'), now)
        if (previous.get('allowance') or {}).get('used_percent') != (snapshot.get('allowance') or {}).get('used_percent'):
            log(store, session_id, 'allowance', snapshot.get('allowance'), now)
        db.execute('INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?,?)',
                   (session_id, runtime, json.dumps(snapshot, allow_nan=False), json.dumps(seen.get('cursor')), now, None))
        queued = None if 'queue' in unknown else {entry.get('client_id') for entry in snapshot.get('queue') or []}
        for delivery in db.execute("SELECT * FROM deliveries WHERE session_id=? AND state IN ('queued','uncertain')", (session_id,)).fetchall():
            hit = db.execute('SELECT turn_id,at FROM messages WHERE session_id=? AND client_id=?', (session_id, delivery['client_id'])).fetchone()
            if hit:
                db.execute("UPDATE deliveries SET state='consumed',consumed_at=?,turn_id=? WHERE client_id=?", (hit['at'] or now, hit['turn_id'], delivery['client_id']))
                changed.append(('consumed', dict(delivery)))
            elif queued is None:
                continue
            elif now >= delivery['latest_at'] and (delivery['client_id'] not in queued or after != 'working'):
                # In neither the native queue nor the history, or queued on a target that is not working.
                db.execute("UPDATE deliveries SET state='unresolved' WHERE client_id=?", (delivery['client_id'],))
                changed.append(('unresolved', dict(delivery)))
            elif delivery['state'] == 'uncertain' and delivery['client_id'] in queued:
                db.execute("UPDATE deliveries SET state='queued' WHERE client_id=?", (delivery['client_id'],))
    first = row is None
    return {'session_id': session_id, 'state': after, 'previous_state': before, 'first': first,
            'ended': [] if first else ended, 'messages': [] if first else fresh, 'deliveries': changed, 'snapshot': snapshot}


def task_sessions(store, task):
    binding = store.binding(task['supervisor_id'])
    return binding, list(dict.fromkeys([binding['session_id'], *task['target_ids'], task['operator_session_id']]))


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def track_allowance(store, task, now):
    """Carry the allowance spend across a window reset: spend is the change in used percent."""
    readings = [snapshot['allowance'] for snapshot in (store.session(s) for s in task_sessions(store, task)[1]) if snapshot and snapshot.get('allowance')]
    if not readings:
        return
    newest = max(readings, key=lambda reading: reading.get('at') or 0)
    tracker = store.counters(task['id'])['state'].get('allowance')
    if tracker is None:
        tracker = {'base': newest['used_percent'], 'last': newest['used_percent'], 'resets_at': newest.get('resets_at'), 'carried': 0}
    elif newest.get('resets_at') and tracker.get('resets_at') and newest['resets_at'] > tracker['resets_at'] + 60:
        tracker = {'base': 0, 'last': newest['used_percent'], 'resets_at': newest['resets_at'],
                   'carried': tracker['carried'] + tracker['last'] - tracker['base']}
    else:
        tracker = tracker | {'last': newest['used_percent']}
    store._state(task['id'], allowance=tracker)


def worker_baselines(store, task, seen):
    """A worker found after creation starts from zero when it was created after the task, else from its first reading."""
    binding = store.binding(task['supervisor_id'])
    for session_id in dict.fromkeys([binding['session_id'], *task['target_ids']]):
        snapshot = (seen.get(session_id) or {}).get('snapshot') or {}
        for worker, record in (snapshot.get('workers') or {}).items():
            if not record.get('usage') or store.conn.execute('SELECT 1 FROM baselines WHERE task_id=? AND session_id=?', (task['id'], worker)).fetchone():
                continue
            later = record.get('created_at') is not None and record['created_at'] >= task['created_at']
            usage = dict.fromkeys(record['usage'], 0) if later else record['usage']
            store.conn.execute('INSERT INTO baselines VALUES(?,?,?)', (task['id'], worker, json.dumps(usage)))


def raise_triggers(store, task, seen, now):
    """Turn what this observation read into triggers for one task. Nothing is raised while nothing changed."""
    db = store.conn
    task_id = task['id']
    binding, sessions = task_sessions(store, task)
    with store.transaction():
        spoke = None
        for session_id in sessions:
            for message in (seen.get(session_id) or {}).get('messages', []):
                if message['origin'] == 'operator':
                    spoke = message['ref']
                    store.trigger(task_id, 'operator-message', {'session_id': session_id, 'ref': message['ref']})
                elif message['origin'] == 'unknown':
                    store.trigger(task_id, 'unknown-message', {'session_id': session_id, 'message_id': message['id']})
        if spoke:
            store.operator_spoke(task_id)
            if task['status'] == 'blocked' and binding['status'] == 'active':
                store.reactivate(task_id, spoke)
                task = store.task(task_id)
        worker_baselines(store, task, seen)
        if task['status'] != 'active':
            return task
        open_items = db.execute("SELECT count(*) FROM items WHERE task_id=? AND status='open'", (task_id,)).fetchone()[0]
        for target in task['target_ids']:
            result = seen.get(target)
            if not result or result.get('failed'):
                continue
            for turn in result['ended']:
                if open_items or task['mode'] == 'observation':
                    store.trigger(task_id, 'turn-ended', {'session_id': target, 'turn_id': turn['id'], 'status': turn['status']})
            if result['state'] != result['previous_state'] and not result.get('first'):
                if result['state'] == 'waiting':
                    store.trigger(task_id, 'target-waiting', {'session_id': target, 'flags': result['snapshot'].get('flags')})
                elif result['state'] == 'unreachable':
                    store.trigger(task_id, 'target-unreachable', {'session_id': target, 'status': result['snapshot'].get('status')})
            for kind, delivery in result['deliveries']:
                if kind == 'unresolved' and delivery['task_id'] == task_id and delivery['kind'] != 'wake':
                    store.trigger(task_id, 'delivery-unresolved', {'session_id': target, 'client_id': delivery['client_id']})
        for step in db.execute("SELECT * FROM steps WHERE task_id=? AND status='open'", (task_id,)).fetchall():
            flags = json.loads(step['flags'])
            elapsed = now - step['declared_at']
            if elapsed >= step['estimate_seconds'] and not flags.get('overrun'):
                flags['overrun'] = now
                store.trigger(task_id, 'step-overrun', {'step': step['id'], 'session_id': step['session_id'],
                                                        'estimate_seconds': step['estimate_seconds'], 'elapsed_seconds': int(elapsed)})
            if elapsed >= 2 * step['estimate_seconds'] and not flags.get('review'):
                flags['review'] = now
                store.review_request(task_id, 'convergence', 'step-overrun:' + step['id'])
            db.execute('UPDATE steps SET flags=? WHERE task_id=? AND id=?', (json.dumps(flags), task_id, step['id']))
        for wait in db.execute("SELECT * FROM waits WHERE task_id=? AND status='pending'", (task_id,)).fetchall():
            condition = json.loads(wait['condition'])
            met = (condition['kind'] == 'time' and now >= condition['at'] or condition['kind'] == 'file' and os.path.exists(condition['path'])
                   or condition['kind'] == 'process' and not alive(condition['pid']))
            if met or now >= wait['latest_at']:
                db.execute('UPDATE waits SET status=?,resolved_at=? WHERE id=?', ('met' if met else 'expired', now, wait['id']))
                store.trigger(task_id, 'wait-met' if met else 'wait-expired', {'wait': wait['id'], 'session_id': wait['session_id']})
                if not met:
                    db.execute('UPDATE counters SET no_closure=no_closure+1 WHERE task_id=?', (task_id,))
        track_allowance(store, task, now)
        spend = store.spend(task)
        state = store.counters(task_id)['state']
        fired = dict(state.get('fired') or {})
        closures = db.execute("SELECT count(*) FROM closures WHERE task_id=? AND kind='item'", (task_id,)).fetchone()[0]
        if state.get('closures_seen') != closures:
            # An acceptance item closed: the measures taken since the last closure start again.
            fired.pop('spend-since-closure', None)
            fired.pop('time-since-closure', None)
            store._state(task_id, closures_seen=closures, closure_spend=spend['lower_bound'] or 0)
            state = store.counters(task_id)['state']
        readable = not spend['unknown']
        if state.get('spend_readable', True) and not readable:
            store.trigger(task_id, 'spend-unknown', {'sessions': spend['unknown']})
        limit = task['limits'].get('spend')
        measure = spend['lower_bound']
        if limit and measure is not None:
            for fraction in THRESHOLDS:
                if measure >= fraction * limit['target'] and not fired.get(f'spend-{fraction}'):
                    fired[f'spend-{fraction}'] = now
                    store.trigger(task_id, 'spend-threshold', {'fraction': fraction, 'value': measure, 'unit': spend['unit'], 'at_least': bool(spend['unknown'])})
                    if fraction == 1.0:
                        store.review_request(task_id, 'convergence', 'spend-target')
            if measure - (state.get('closure_spend') or 0) >= 0.5 * limit['target'] and not fired.get('spend-since-closure'):
                fired['spend-since-closure'] = now
                store.review_request(task_id, 'convergence', f'spend-since-closure:{closures}')
        deadline = task['limits'].get('deadline_at')
        if deadline and not fired.get('time-since-closure'):
            last = db.execute("SELECT max(at) FROM closures WHERE task_id=? AND kind='item'", (task_id,)).fetchone()[0] or task['created_at']
            if now - last >= 0.5 * (deadline['value'] - task['created_at']):
                fired['time-since-closure'] = now
                store.review_request(task_id, 'convergence', f'time-since-closure:{closures}')
        store._state(task_id, spend_readable=readable, fired=fired)
        if not store.pending_triggers(task_id):
            quiet = not db.execute("SELECT 1 FROM waits WHERE task_id=? AND status='pending'", (task_id,)).fetchone() and not db.execute(
                "SELECT 1 FROM deliveries WHERE task_id=? AND state IN ('queued','uncertain')", (task_id,)).fetchone() and not db.execute(
                f"SELECT 1 FROM executions WHERE task_id=? AND status IN ({','.join('?' * len(OPEN_EXECUTIONS))})", (task_id, *OPEN_EXECUTIONS)).fetchone()
            last = db.execute('SELECT max(COALESCE(finished_at,scheduled_at)) FROM executions WHERE task_id=?', (task_id,)).fetchone()[0] or task['created_at']
            if quiet and now - last >= task['limits']['heartbeat_seconds']:
                store.trigger(task_id, 'heartbeat', {})
    return task


def refresh(store, transport_for, session_ids, now, extra_runtime=None):
    """Observe sessions and raise the triggers of every active or parked task they belong to."""
    db = store.conn
    seen = {}
    wanted = set(session_ids)
    tasks = [store.task(row[0]) for row in db.execute(
        "SELECT t.id FROM tasks t JOIN bindings b ON b.id=t.supervisor_id WHERE t.status IN ('active','blocked') AND b.status='active' ORDER BY t.id")]
    involved = []
    for task in tasks:
        if task.get('contract') != 2:
            continue
        binding, sessions = task_sessions(store, task)
        if not wanted.intersection(sessions):
            continue
        involved.append(task)
        try:
            transport = transport_for(binding)
        except Exception:
            continue
        if hasattr(transport, 'timeout'):
            transport.timeout = min(30, task['limits']['transport_timeout_seconds'])
        for session_id in sessions:
            if session_id in wanted and session_id not in seen:
                spends = session_id == binding['session_id'] or session_id in task['target_ids']
                seen[session_id] = observe_session(store, transport, session_id, binding['runtime'], now, workers_since=task['created_at'] if spends else None)
    for session_id in wanted - set(seen):
        if extra_runtime is not None:
            runtime, transport, since = extra_runtime
            seen[session_id] = observe_session(store, transport, session_id, runtime, now, workers_since=since)
    for task in involved:
        raise_triggers(store, task, seen, now)
    return seen


def baseline(store, transport, binding, data, now):
    """Observe a new task's sessions once: its spend baseline, and its registry of operator messages."""
    targets = [target for target in data.get('target_ids', []) if isinstance(target, str)]
    spenders = list(dict.fromkeys([binding['session_id'], *targets]))
    sessions = spenders + [s for s in [data.get('operator_session_id')] if isinstance(s, str) and s not in spenders]
    seen = refresh(store, lambda _binding: transport, sessions, now, extra_runtime=(binding['runtime'], transport, now))
    usage = {}
    for session_id in spenders:
        snapshot = (seen.get(session_id) or {}).get('snapshot') or {}
        if seen.get(session_id, {}).get('failed') or 'usage' in snapshot.get('unknown', []):
            continue
        usage[session_id] = snapshot.get('usage')
        for worker, record in (snapshot.get('workers') or {}).items():
            usage[worker] = record.get('usage')
    return usage


def scan_history(store, transport, session_id, history_turns, now):
    """Read further back than the stored cursor, to bring an older operator message into the registry."""
    seen = transport.observe(session_id, cursor=None, history_turns=history_turns)
    if 'messages' in (seen.get('unknown') or []):
        raise StoreError('the history of ' + session_id + ' could not be read; nothing was added to the registry')
    with store.transaction():
        return store_messages(store, session_id, seen.get('messages') or [], now)
