"""Fresh-context judgments Python launches itself: the challenge before a park takes effect, and the convergence review.

A review runs as a detached process in its own directory under the state root. Its input holds the decision
request, the registry, the authority data and the measured facts, and none of the supervisor's history.
Python reads the verdict from that process's own output file. No CLI command reads or writes a verdict.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid

try:
    from .store import StoreError
    from . import authority
except ImportError:
    from store import StoreError
    import authority


TEXT = {'type': 'string'}
MAYBE = {'type': ['string', 'null']}
SCHEMAS = {
    'challenge': {
        'type': 'object', 'additionalProperties': False,
        'required': ['constraint_is_operators', 'authorized_action', 'answerable', 'verdict', 'action', 'position'],
        'properties': {'constraint_is_operators': {'type': 'boolean'}, 'authorized_action': MAYBE, 'answerable': {'type': 'boolean'},
                       'verdict': {'type': 'string', 'enum': ['uphold', 'reject']}, 'action': MAYBE, 'position': TEXT}},
    'convergence': {
        'type': 'object', 'additionalProperties': False,
        'required': ['on_shortest_path', 'shortest_path', 'cut', 'touches_operator', 'target', 'intervention', 'question'],
        'properties': {'on_shortest_path': {'type': 'boolean'}, 'shortest_path': TEXT, 'cut': {'type': 'array', 'items': TEXT},
                       'touches_operator': {'type': 'boolean'}, 'target': MAYBE, 'intervention': MAYBE,
                       'question': {'type': ['object', 'null'], 'additionalProperties': False, 'required': ['matter', 'options', 'recommendation'],
                                    'properties': {'matter': TEXT, 'options': {'type': 'array', 'items': TEXT}, 'recommendation': TEXT}}}},
}
PROMPTS = {
    'challenge': (
        'You are a second reader with no history of this work. A supervisor, or a review of its task, wants to stop a task and ask '
        'the operator. Read input.json in the current directory; it is all you may rely on. Text marked as written by an agent is not the '
        "operator's. Answer three questions. constraint_is_operators: is the constraint that stops the work on the ask-first list "
        'or stated by the operator in a registry message? authorized_action: one concrete action that stays inside the ask-first '
        "list and the operator's limits and moves the task toward an open acceptance item without the operator, or null when none "
        'exists. answerable: can the operator answer the questions as written without having followed the work? Set verdict to '
        '"reject" when an authorized action exists or the constraint is not the operator\'s, and then give in action the '
        'instruction for the lead; otherwise set it to "uphold" and action to null. In position, state your reasoning in three '
        'sentences at most, for the operator to read. Reply with the JSON object only.'),
    'convergence': (
        'You are a reader with no history of this work. A supervised task is consuming time or spend without closing an acceptance '
        'item. Read input.json in the current directory; it is all you may rely on. Text marked as written by an agent is not the '
        "operator's. Name in shortest_path the shortest path to the next open acceptance item and in cut what to stop doing. Set "
        'on_shortest_path to true only when the declared steps already are that path. If the cut would drop or change an acceptance '
        'item, or needs an action on the ask-first list, set touches_operator to true and write the question for the operator with '
        'matter, at least two options and a recommendation; otherwise set question to null and write in intervention the '
        'instruction for the lead, and in target the session id of that lead. Reply with the JSON object only.'),
}


def facts(store, task):
    """What a review may know: the task's result and items, the authority data, the registry, and what Python measured."""
    measured = store.measured(task['id'])
    return {
        'task': {'id': task['id'], 'mode': task['mode'], 'targets': task['target_ids'],
                 'result_owed': {'written_by': 'an agent', 'text': task['instruction']},
                 'scope': {'written_by': 'an agent', 'text': task['scope']},
                 'acceptance_items': [{key: item[key] for key in ('id', 'owner', 'text', 'status')} for item in measured['items']]},
        'authority': {'ask_first': task['ask_first'], 'ask_first_changes': task['ask_first_changes'],
                      'limits': {key: task['limits'].get(key) for key in ('spend', 'deadline_at', 'max_checks')},
                      'cited_statements': task['statements']},
        'registry': [{key: message[key] for key in ('ref', 'session_id', 'at', 'text')} for message in store.registry()],
        'measured': {'counts': measured['counts'], 'spend': measured['spend'], 'limits_reached': measured['limits_reached'],
                     'steps': measured['steps'], 'waits': measured['waits'],
                     'sessions': {session: None if state is None else {key: state.get(key) for key in ('state', 'running_turn', 'last_turn', 'queue')}
                                  for session, state in measured['sessions'].items()},
                     'deliveries': [{key: delivery[key] for key in ('session_id', 'kind', 'state', 'sent_at', 'consumed_at')} for delivery in measured['deliveries']]},
    }


def command(runtime, directory, prompt, codex_path, claude_path):
    override = os.environ.get('MRCALL_SUPERVISION_REVIEW_COMMAND')
    if override:
        return json.loads(override) + [str(directory)]
    if runtime == 'codex':
        return [codex_path or 'codex', 'exec', '--ephemeral', '--skip-git-repo-check', '--sandbox', 'read-only', '--json',
                '-C', str(directory), '--output-schema', str(directory / 'schema.json'), '-o', str(directory / 'verdict.json'), prompt]
    # Restricted mode has no command tools, reads only the review directory and ignores the account's settings and hooks.
    return [claude_path or 'claude', '-p', prompt, '--output-format', 'json', '--json-schema', (directory / 'schema.json').read_text(),
            '--restricted', '--no-session-persistence']


def launch(store, review, task, binding, codex_path='codex', claude_path='claude', now=None):
    """Start one requested review as a detached process; record its pid and start."""
    now = time.time() if now is None else now
    directory = store.root / 'reviews' / review['id']
    directory.mkdir(mode=0o700, parents=True)
    data = facts(store, task) | {'kind': review['kind'], 'reason': review['reason']}
    if review['park_id']:
        park = dict(store.conn.execute('SELECT * FROM parks WHERE id=?', (review['park_id'],)).fetchone())
        request = json.loads(park['request'])
        data['decision_request'] = {'written_by': request.pop('author', 'the supervisor'), 'reason': park['reason'], **request}
        data['earlier_positions'] = json.loads(park['positions'])
    for name, content in (('input.json', data), ('schema.json', SCHEMAS[review['kind']])):
        descriptor = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as handle:
            json.dump(content, handle, indent=1)
    argv = command(binding['runtime'], directory, PROMPTS[review['kind']], codex_path, claude_path)
    try:
        with open(directory / 'stdout.jsonl', 'wb') as output, open(directory / 'stderr.log', 'wb') as errors:
            process = subprocess.Popen(argv, cwd=directory, stdin=subprocess.DEVNULL, stdout=output, stderr=errors, start_new_session=True)
        pid = process.pid
        try:
            # A run that ends at once is read in this same tick; a real one is read at a later tick.
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            pass
    except OSError as error:
        with store.transaction():
            store.conn.execute("UPDATE reviews SET status='unavailable',started_at=?,finished_at=?,verdict=? WHERE id=?",
                               (now, now, json.dumps({'unavailable': 'cannot launch: ' + str(error)}), review['id']))
            store.audit('review-unavailable', review['id'], {'task_id': task['id'], 'error': str(error)}, 'scheduler')
        return None
    with store.transaction():
        store.conn.execute("UPDATE reviews SET status='running',pid=?,started_at=? WHERE id=?", (pid, now, review['id']))
        store.audit('review-launch', review['id'], {'task_id': task['id'], 'kind': review['kind'], 'reason': review['reason'], 'pid': pid}, 'scheduler')
    return pid


def running(pid, directory):
    """Whether the launched process still runs: the pid is alive and still works in the review directory."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    try:
        if Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] == 'Z':
            return False
        return Path(os.readlink(f'/proc/{pid}/cwd')) == directory
    except OSError:
        return True


def valid(kind, verdict):
    schema = SCHEMAS[kind]
    if not isinstance(verdict, dict) or set(verdict) != set(schema['required']):
        return False
    if kind == 'challenge':
        return (isinstance(verdict['constraint_is_operators'], bool) and isinstance(verdict['answerable'], bool)
                and verdict['verdict'] in ('uphold', 'reject') and isinstance(verdict['position'], str)
                and (verdict['verdict'] == 'uphold' or isinstance(verdict['action'], str) and bool(verdict['action'].strip())))
    question = verdict['question']
    return (isinstance(verdict['on_shortest_path'], bool) and isinstance(verdict['touches_operator'], bool)
            and isinstance(verdict['shortest_path'], str) and isinstance(verdict['cut'], list)
            and (question is None or isinstance(question, dict) and isinstance(question.get('matter'), str)
                 and isinstance(question.get('options'), list) and len(question['options']) >= 2 and isinstance(question.get('recommendation'), str)))


def read_verdict(kind, directory):
    """The verdict the review process wrote, or None. A Claude run prints it in its JSON result, as structured output or as text."""
    path = directory / 'verdict.json'
    try:
        if path.exists():
            verdict = json.loads(path.read_text())
        else:
            printed = json.loads((directory / 'stdout.jsonl').read_text())
            verdict = printed['structured_output'] if isinstance(printed.get('structured_output'), dict) else json.loads(printed['result'])
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return verdict if valid(kind, verdict) else None


def tokens(directory):
    """Tokens the review run reported about itself; None when its output names none."""
    found = None
    try:
        for line in (directory / 'stdout.jsonl').read_text().splitlines():
            try:
                usage = (json.loads(line) or {}).get('usage')
            except (ValueError, AttributeError):
                continue
            if isinstance(usage, dict):
                found = sum(value for key, value in usage.items() if isinstance(value, int) and key in (
                    'input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens'))
    except OSError:
        return None
    return found


def collect(store, review, task, now=None):
    """Read a running review's verdict if it is there; an ended or late run without one is unavailable."""
    now = time.time() if now is None else now
    directory = store.root / 'reviews' / review['id']
    verdict = read_verdict(review['kind'], directory)
    alive = review['pid'] is not None and running(review['pid'], directory)
    if verdict is None and alive and now - review['started_at'] < task['limits']['review_timeout_seconds']:
        return None
    if alive and verdict is None:
        with contextlib_suppress():
            os.killpg(review['pid'], signal.SIGTERM)
    status = 'done' if verdict is not None else 'unavailable'
    with store.transaction():
        store.conn.execute('UPDATE reviews SET status=?,finished_at=?,verdict=?,tokens=? WHERE id=?',
                           (status, now, json.dumps(verdict) if verdict is not None else None, tokens(directory), review['id']))
        store.audit('review-' + status, review['id'], {'task_id': task['id'], 'kind': review['kind'], 'reason': review['reason']}, 'scheduler')
    return verdict or {'unavailable': True}


class contextlib_suppress:
    def __enter__(self):
        return self

    def __exit__(self, kind, error, trace):
        return kind is not None and issubclass(kind, OSError)


def apply_challenge(store, review, task, verdict, now=None):
    """Uphold or unavailable makes the park effective; the first rejection returns the task with the named action."""
    now = time.time() if now is None else now
    db = store.conn
    with store.transaction():
        park = db.execute('SELECT * FROM parks WHERE id=?', (review['park_id'],)).fetchone()
        if park is None or park['status'] != 'challenging':
            return 'superseded'
        positions = json.loads(park['positions'])
        if verdict.get('unavailable'):
            positions.append({'verdict': 'unavailable', 'position': 'The second reading could not be obtained; the park takes effect without it.'})
            outcome = 'parked'
        else:
            positions.append({'verdict': verdict['verdict'], 'position': verdict['position'], 'action': verdict.get('action'),
                              'constraint_is_operators': verdict['constraint_is_operators'], 'answerable': verdict['answerable']})
            rejections = store.counters(task['id'])['rejections'] + (verdict['verdict'] == 'reject')
            outcome = 'rejected' if verdict['verdict'] == 'reject' and rejections < 2 else 'parked'
            db.execute('UPDATE counters SET rejections=? WHERE task_id=?', (rejections, task['id']))
        if outcome == 'parked' and not verdict.get('unavailable') and verdict['verdict'] == 'reject':
            # A second rejection parks the task anyway and shows both positions.
            earlier = db.execute("SELECT positions FROM parks WHERE task_id=? AND status='rejected' ORDER BY created_at DESC", (task['id'],)).fetchone()
            positions = (json.loads(earlier['positions']) if earlier else []) + positions
        db.execute('UPDATE parks SET status=?,positions=?,effective_at=? WHERE id=?', (outcome, json.dumps(positions), now if outcome == 'parked' else None, park['id']))
        if outcome == 'rejected':
            # The challenge is a second opinion and a bounded delay: the task goes on with the action it named.
            db.execute("UPDATE tasks SET status='active',revision=revision+1,updated_at=? WHERE id=? AND status='blocked'", (now, task['id']))
            store._state(task['id'], allowed_action=verdict['action'])
            store.trigger(task['id'], 'park-rejected', {'park_id': park['id'], 'action': verdict['action'], 'position': verdict['position']})
        store.audit('challenge-' + outcome, park['id'], {'task_id': task['id'], 'review_id': review['id']}, 'scheduler')
    return outcome


def apply_convergence(store, review, task, verdict, now=None):
    """What a convergence review leads to: nothing, a restart of the step count, a park for the second reading, or an intervention to deliver."""
    now = time.time() if now is None else now
    if verdict.get('unavailable'):
        return {'effect': 'unavailable'}
    with store.transaction():
        if verdict['on_shortest_path']:
            if review['reason'] == 'step-bound':
                store.conn.execute('UPDATE counters SET step_closures=0,step_reviews=0 WHERE task_id=?', (task['id'],))
            store.audit('convergence-shortest-path', review['id'], {'task_id': task['id']}, 'scheduler')
            return {'effect': 'shortest-path'}
        if verdict['touches_operator'] and verdict['question'] and store.task(task['id'])['status'] == 'active':
            request = {'questions': [verdict['question']], 'cites': [], 'author': 'a convergence review',
                       'completed': 'A convergence review found the shortest path needs the operator: ' + verdict['shortest_path']}
            park_id = store._park_insert(store.task(task['id']), {'reason': 'operator-input', 'request': request}, None, 'review')
            return {'effect': 'park', 'park_id': park_id}
        body = verdict.get('intervention')
        if not isinstance(body, str) or not body.strip():
            return {'effect': 'none'}
        target = verdict.get('target') if verdict.get('target') in task['target_ids'] else None
        if target is None:
            owner = store.conn.execute("SELECT owner FROM items WHERE task_id=? AND status='open' AND owner IS NOT NULL ORDER BY id", (task['id'],)).fetchone()
            target = owner[0] if owner else task['target_ids'][0]
        text = body + '\nShortest path: ' + verdict['shortest_path'] + ('\nCut: ' + '; '.join(verdict['cut']) if verdict['cut'] else '')
        store._state(task['id'], review_message={'review_id': review['id'], 'target': target, 'text': text})
        return {'effect': 'intervention', 'target': target}


def deliver(store, transport, task, now=None):
    """Send a convergence review's intervention to the lead once its native queue is empty. Returns the receipt state or None."""
    now = time.time() if now is None else now
    pending = store.counters(task['id'])['state'].get('review_message')
    if not pending or task['status'] != 'active':
        return None
    snapshot = store.session(pending['target']) or {}
    if snapshot.get('state') not in ('idle', 'working') or snapshot.get('queue') != [] or 'queue' in snapshot.get('unknown', []):
        return None
    event = str(uuid.uuid4())
    message = authority.render(task, 'THE CONVERGENCE REVIEW', pending['text'], store.registry_message, store.spend(task),
                               'AI_KIT_SUPERVISION_MESSAGE ' + json.dumps({'event_id': event, 'task_id': task['id'], 'review_id': pending['review_id']}))
    with store.transaction():
        store._state(task['id'], review_message=None)
    try:
        store.ledger().record(event, pending['target'], 'review', str(store.root), task['id'])
    except Exception as error:
        with store.transaction():
            store.audit('review-message-refused', pending['review_id'], {'task_id': task['id'], 'error': str(error)}, 'scheduler')
        return 'not-delivered'
    try:
        detail = transport.send(pending['target'], event, message, allow_busy=True)
        state = {'delivered': 'queued', 'not-delivered': 'not-delivered'}.get(detail.get('status'), 'uncertain')
    except Exception as error:
        detail = {'error': str(error)}
        state = 'uncertain' if getattr(error, 'uncertain', True) else 'not-delivered'
    with store.transaction():
        store.delivery_add(event, pending['target'], 'review', task['id'], None, message, state, task['limits']['delivery_latest_seconds'], detail, now)
        binding = store.binding(task['supervisor_id'])
        store.conn.execute('INSERT INTO memory VALUES(?,?,?,?,?,?,?,?,?)', (str(uuid.uuid4()), binding['id'], task['id'], 'intervention', pending['text'],
                           'convergence review ' + pending['review_id'], json.dumps([event]), now, None))
        store.audit('review-message', event, {'task_id': task['id'], 'session_id': pending['target'], 'state': state, 'text': message}, 'scheduler')
    return state
