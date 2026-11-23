"""What the operator reserves, what the operator limited, and how every kit message says so."""
import datetime
import json
import os
from pathlib import Path

try:
    from .store import StoreError, strings, text
except ImportError:
    from store import StoreError, strings, text


ASK_FIRST = (
    'using a credential that only the operator holds',
    'making a payment',
)
MARKERS = ('AI_KIT_SUPERVISOR_EVENT ', 'AI_KIT_GOAL_EVENT ', 'AI_KIT_OPERATOR_QUESTION ',
           'AI_KIT_SUPERVISION_NOTICE ', 'AI_KIT_SUPERVISION_MESSAGE ', 'AI_KIT_SUPERVISION_EVENT ')
PARK_REASONS = ('ask-first', 'operator-restriction', 'operator-input',
                'limit-reached', 'closure-bounds', 'delivery-unresolved')
OPERATOR_REASONS = PARK_REASONS[:3]
CHALLENGED = OPERATOR_REASONS + ('closure-bounds',)
UNITS = ('tokens', 'allowance_percent', 'currency')
# The operator's standing request of 2026-10-27, carried by every kit message to an entrusted session.
TOKEN_REMINDER = ('Conserve tokens: reuse existing evidence, avoid repeated checks and unnecessary delegation, and keep '
                  'context and reports concise. Prefer deterministic checks when sufficient. Pass this requirement to '
                  "workers and respect the operator's spending limits.")
PRICE_KEYS = ('input', 'cached_input', 'output')


def kit_home():
    return Path(os.environ.get('MRCALL_KIT_HOME', Path.home() / '.config/mrcall-ai-kit')).absolute()


def config():
    """Operator-written kit configuration. No command writes this file."""
    path = kit_home() / 'supervision.json'
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as error:
        raise StoreError(f'kit configuration {path} is unreadable: {error}') from None
    if not isinstance(data, dict):
        raise StoreError(f'kit configuration {path} must be a JSON object')
    return data


def positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not value > 0 or value != value or value in (float('inf'),):
        raise StoreError(f'{name} must be a positive number')
    return value


def cites(value, name, registered, required=True):
    """Every citation is an operator message of this state root or an entry of the kit configuration."""
    value = strings([] if value is None else value, name)
    if required and not value:
        raise StoreError(f'{name} must cite the operator: a registry reference (see registry) or config:<key>')
    settings = None
    for entry in value:
        if entry.startswith('config:'):
            settings = config() if settings is None else settings
            if entry[7:] not in settings:
                raise StoreError(f'{name}: {entry} is not an entry of the kit configuration')
        elif not registered(entry):
            raise StoreError(f'{name}: {entry} is not an operator message in the registry; text an agent wrote cannot be cited')
    return value


def prices(value, name):
    if not isinstance(value, dict) or set(value) != set(PRICE_KEYS):
        raise StoreError(f'{name} must give input, cached_input and output prices per million tokens')
    return {key: positive(value[key], f'{name}.{key}') for key in PRICE_KEYS}


def spend_limit(value, registered, required):
    """A spend limit is data the operator supplied: unit, target, ceiling, citations."""
    cited = None
    if value is None:
        if not required:
            # The configured default is for the tasks that must have a limit; an observation task has one only when given one.
            return None
        default = config().get('default_spend_limit')
        if default is None:
            raise StoreError('a completion task needs limits.spend with a target, a ceiling and the operator message it '
                             'cites: ask the operator for a spend limit, or have the operator write default_spend_limit '
                             'in the kit configuration')
        value, cited = default, ['config:default_spend_limit']
    if not isinstance(value, dict):
        raise StoreError('limits.spend must be an object')
    unit = value.get('unit')
    if unit not in UNITS:
        raise StoreError('limits.spend.unit must be tokens, allowance_percent or currency')
    target = positive(value.get('target'), 'limits.spend.target')
    ceiling = positive(value.get('ceiling'), 'limits.spend.ceiling')
    if ceiling < target:
        raise StoreError('limits.spend.ceiling must not be below its target')
    limit = {'unit': unit, 'target': target, 'ceiling': ceiling,
             'cites': cited or cites(value.get('cites'), 'limits.spend.cites', registered)}
    if unit == 'currency':
        table = value.get('prices')
        if table is None:
            table = config().get('prices')
            if table is None:
                raise StoreError('a currency spend limit needs prices per million tokens from the operator, in '
                                 'limits.spend.prices or in the kit configuration; no price is assumed')
            limit['prices_from'] = 'config:prices'
        limit['prices'] = prices(table, 'limits.spend.prices')
    return limit


def ask_first(changes, registered):
    """The list is fixed in code. A task changes it only by citing the operator."""
    items = list(ASK_FIRST)
    record = {'add': [], 'remove': []}
    if changes is None:
        return items, record
    if not isinstance(changes, dict) or set(changes) - {'add', 'remove'}:
        raise StoreError('ask_first accepts only add and remove')
    for kind in ('remove', 'add'):
        for entry in changes.get(kind, []):
            if not isinstance(entry, dict):
                raise StoreError('each ask_first change is an object with item and cites')
            item = text(entry.get('item'), 'ask_first.item')
            cited = cites(entry.get('cites'), 'ask_first.cites', registered)
            if kind == 'remove':
                if item not in items:
                    raise StoreError(f'ask_first.remove: {item!r} is not on the list')
                items.remove(item)
            elif item not in items:
                items.append(item)
            record[kind].append({'item': item, 'cites': cited})
    return items, record


def stamp(value):
    if value is None:
        return 'time unknown'
    return datetime.datetime.fromtimestamp(value, datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')


def amount(value, unit):
    if value is None:
        return 'unknown'
    if unit == 'tokens':
        return f'{int(value):,} tokens'
    if unit == 'allowance_percent':
        return f'{value:g}% of the allowance window'
    return f'{value:,.2f} in currency'


def limit_lines(task, spend):
    limits = task['limits']
    lines = []
    limit = limits.get('spend')
    if limit:
        measured = amount(None if spend is None or spend.get('unknown') else spend.get('value'), limit['unit'])
        lines.append(f"- Spend: target {amount(limit['target'], limit['unit'])}, ceiling {amount(limit['ceiling'], limit['unit'])}; "
                     f"measured so far: {measured} [cites {', '.join(limit['cites'])}]")
    if limits.get('deadline_at'):
        lines.append(f"- Deadline: {stamp(limits['deadline_at']['value'])} [cites {', '.join(limits['deadline_at']['cites'])}]")
    if limits.get('max_checks'):
        lines.append(f"- Assessments: at most {limits['max_checks']['value']} [cites {', '.join(limits['max_checks']['cites'])}]")
    return lines or ['- None recorded.']


def cited_references(task):
    found = list(task.get('statements', []))
    for key in ('spend', 'deadline_at', 'max_checks'):
        found += (task['limits'].get(key) or {}).get('cites', [])
    for kind in ('add', 'remove'):
        for change in task.get('ask_first_changes', {}).get(kind, []):
            found += change['cites']
    return list(dict.fromkeys(found))


def render(task, sender, body, registry, spend=None, envelope=None, reminder=True):
    """Every kit message in labeled parts. `registry` maps a reference to its stored operator message."""
    statements = []
    for reference in cited_references(task):
        if reference.startswith('config:'):
            statements.append(f'[{reference}] kit configuration entry written by the operator')
            continue
        message = registry(reference)
        statements.append(f"[{reference}, session {message['session_id']}, {stamp(message['at'])}]\n{message['text']}")
    parts = [
        ('RESULT OWED', task['instruction']),
        ('ASK FIRST — the operator decides these, nobody else', '\n'.join('- ' + item for item in task['ask_first'])),
        ('OPERATOR LIMITS — data, each cited', '\n'.join(limit_lines(task, spend))),
        ('OPERATOR STATEMENTS — verbatim from the registry', '\n\n'.join(statements) or 'None cited.'),
        ('EVERYTHING ELSE', 'Anything not listed above is yours to decide. Decide it, do it, and record the decision '
                            'with what, why and how to undo it.'),
    ]
    if reminder:
        parts.append(('TOKEN DISCIPLINE — the operator\'s standing request', TOKEN_REMINDER))
    parts.append((f'FROM {sender} — NOT THE OPERATOR\'S WORDS', body))
    rendered = '\n\n'.join(f'== {label} ==\n{content}' for label, content in parts)
    return (envelope + '\n' if envelope else '') + rendered


def question_text(park):
    request = park['request']
    lines = []
    for number, question in enumerate(request['questions'], 1):
        lines.append(f"Question {number}: {question['matter']}")
        lines += [f'  Option {chr(96 + index)}: {option}' for index, option in enumerate(question['options'], 1)]
        lines.append(f"  Recommended: {question['recommendation']}")
    lines.append('Completed meanwhile, or why nothing else can proceed: ' + request['completed'])
    if request.get('cites'):
        lines.append('Cites: ' + ', '.join(request['cites']))
    for position in park.get('positions', []):
        lines.append(f"Second reading ({position['verdict']}): {position['position']}")
    return '\n'.join(lines)


def question(task, park, registry, spend=None):
    body = (f"Supervision of task {task['id']} stopped and waits for the operator (reason: {park['reason']}).\n"
            + question_text(park) +
            '\nPresent this to the operator exactly, then wait. Do not answer it yourself and do not act on it. '
            'The task resumes when the operator writes in an observed session.')
    envelope = 'AI_KIT_OPERATOR_QUESTION ' + json.dumps({'task_id': task['id'], 'park_id': park['id']})
    # The question is for the operator to read, not an instruction to a working session: it carries no reminder.
    return render(task, 'THE SUPERVISION CONTROLLER', body, registry, spend, envelope, reminder=False)
