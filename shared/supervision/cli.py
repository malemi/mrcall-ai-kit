import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time

sys.dont_write_bytecode = True

if __package__:
    from .store import Store, StoreError, default_state_dir, identity, number, text
    from .scheduler import Scheduler, native_transport, execution_read, transport_read, reconcile_execution
    from .cron import activate, deactivate, deactivate_owned
    from .harness import inspect as harness_inspect
    from .control import intervene, intervention_status, session_read, reconcile_intervention, current_execution, notice
    from . import authority, ledger as ledger_module, observe
else:
    from store import Store, StoreError, default_state_dir, identity, number, text
    from scheduler import Scheduler, native_transport, execution_read, transport_read, reconcile_execution
    from cron import activate, deactivate, deactivate_owned
    from harness import inspect as harness_inspect
    from control import intervene, intervention_status, session_read, reconcile_intervention, current_execution, notice
    import authority
    import ledger as ledger_module
    import observe

COMMANDS = ['init', 'bind', 'task-create', 'task-update', 'task-state', 'list', 'status', 'memory-add', 'memory-supersede', 'memory-query',
            'detach', 'execution-result', 'tick', 'execution-read', 'execution-reconcile', 'intervention-reconcile', 'transport-read',
            'activate', 'deactivate', 'deactivate-owned', 'harness-inspect', 'intervene', 'intervention-status', 'session-read',
            'observe', 'registry-scan', 'registry', 'notice', 'ledger-backfill']


def shown(store, task):
    """The authority exactly as Python renders it in every message, for the operator to see before and after creation."""
    return authority.render(task, 'THE SUPERVISOR', "(the supervisor's own text appears here)", store.registry_message, None)


def create_task(store, transport_for, data, dry_run=False):
    """Create a task after one observation of its sessions: the spend baseline and the registry come from it."""
    store.current()
    binding = store.binding(text(data.get('supervisor_id'), 'supervisor_id'))
    transport = transport_for(binding)
    operator = data.get('operator_session_id')
    if isinstance(operator, str) and operator not in [binding['session_id'], *binding['target_ids']]:
        try:
            metadata = transport.metadata(identity(operator, 'operator_session_id'))
        except StoreError:
            raise
        except Exception as error:
            raise StoreError('operator_session_id could not be verified through the runtime: ' + str(error)) from None
        if metadata.get('id') != operator or metadata.get('parentThreadId'):
            raise StoreError('operator_session_id must be a root session of the same runtime')
    baseline = observe.baseline(store, transport, binding, data, time.time())
    if dry_run:
        task = store.preview_task(data)
        unread = [s for s in [binding['session_id'], *task['target_ids']] if not baseline.get(s)] if task['mode'] == 'completion' else []
        return {'dry_run': True, 'task': task, 'authority': shown(store, task), 'operator_session_id': task['operator_session_id'],
                'unreadable_counters': unread}
    task = store.create_task(data, baseline=baseline)
    return task | {'authority': shown(store, task)}


def registry_scan(store, transport_for, data):
    """Read the binding's sessions, and optionally an operator session, so operator messages can be cited."""
    store.current()
    binding = store.binding(text(data.get('supervisor_id'), 'supervisor_id'))
    if binding['status'] != 'active':
        raise StoreError('binding is detached; native reads refused')
    transport = transport_for(binding)
    sessions = [binding['session_id'], *binding['target_ids']]
    operator = data.get('operator_session_id')
    if operator is not None and identity(operator, 'operator_session_id') not in sessions:
        sessions.append(operator)
    now = time.time()
    seen = observe.refresh(store, lambda _binding: transport, sessions, now, extra_runtime=(binding['runtime'], transport, None))
    added = {}
    if data.get('history_turns') is not None:
        turns = number(data['history_turns'], 'history_turns')
        for session_id in sessions:
            added[session_id] = len(observe.scan_history(store, transport, session_id, turns, now))
    return {'sessions': {session_id: {'state': result['state'], 'failed': result.get('failed'), 'unknown': result['snapshot'].get('unknown', [])}
                         for session_id, result in seen.items()},
            'older_messages_added': added, 'registry': store.registry(), 'ledger': store.ledger_path}


def refresh_task(store, transport_for, task_id):
    task = store.task(text(task_id, 'id'))
    if task.get('contract') != 2:
        return store.status(task_id)
    binding, sessions = observe.task_sessions(store, task)
    if binding['status'] == 'active' and task['status'] in ('active', 'blocked'):
        observe.refresh(store, transport_for, sessions, time.time())
    return store.status(task_id)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Persistent ai-kit supervision tasks and memory')
    parser.add_argument('--state-dir')
    parser.add_argument('command', choices=COMMANDS)
    parser.add_argument('--id')
    parser.add_argument('--codex-path')
    parser.add_argument('--claude-path')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    store = None
    try:
        if args.codex_path and not Path(args.codex_path).is_absolute():
            raise StoreError('codex-path must be absolute')
        if args.command == 'deactivate-owned':
            result = deactivate_owned(dry_run=args.dry_run)
            print(json.dumps({'ok': True, 'result': result}, allow_nan=False))
            return 0
        if args.claude_path and not Path(args.claude_path).is_absolute():
            raise StoreError('claude-path must be absolute')
        if args.command == 'ledger-backfill':
            # One ledger for the account: earlier kit sends of every state root classify as kit from now on.
            account = ledger_module.Ledger(ledger_module.default_path())
            try:
                result = account.backfill(Path(args.state_dir).absolute() if args.state_dir else default_state_dir().parent) | {'ledger': str(account.path)}
            finally:
                account.close()
            print(json.dumps({'ok': True, 'result': result}, allow_nan=False))
            return 0
        store = Store(args.state_dir)
        def transport_for(binding):
            return native_transport(args.codex_path or 'codex', runtime=binding.get('runtime', 'codex'), claude_path=args.claude_path or 'claude')
        if args.command in ('init', 'list', 'status'):
            result = store.status(args.id)
        elif args.command == 'tick':
            scheduler = Scheduler(store, codex_path=args.codex_path or 'codex', claude_path=args.claude_path or 'claude')
            result = scheduler.tick()
        elif args.command == 'execution-read':
            result = execution_read(store, args.id)
        elif args.command == 'execution-reconcile':
            execution = execution_read(store, args.id)
            result = reconcile_execution(store, args.id, transport_for(execution['binding']))
        elif args.command == 'intervention-reconcile':
            receipt = intervention_status(store, args.id)
            _, _, binding = current_execution(store, receipt['intent'])
            result = reconcile_intervention(store, transport_for(binding), args.id)
        elif args.command == 'harness-inspect':
            result = harness_inspect(store, args.id)
        elif args.command == 'intervention-status':
            result = intervention_status(store, args.id)
        elif args.command == 'deactivate':
            result = deactivate(store, dry_run=args.dry_run)
        elif args.command == 'observe':
            result = refresh_task(store, transport_for, args.id)
        elif args.command == 'registry':
            store.current()
            result = store.registry(args.id)
        else:
            data = json.load(sys.stdin)
            if not isinstance(data, dict):
                raise StoreError('input must be a JSON object')
            if args.command == 'memory-supersede' and not data.get('supersedes'):
                raise StoreError('memory-supersede requires supersedes')
            if args.command == 'activate':
                result = activate(store, transport_for(data), data, dry_run=args.dry_run, codex_path=args.codex_path, claude_path=args.claude_path)
            elif args.command == 'transport-read':
                result = transport_read(store, transport_for(store.binding(data['supervisor_id'])), data)
            elif args.command in ('intervene', 'session-read'):
                method = intervene if args.command == 'intervene' else session_read
                _, _, binding = current_execution(store, data)
                result = method(store, transport_for(binding), data)
            elif args.command == 'task-create':
                result = create_task(store, transport_for, data, dry_run=args.dry_run)
            elif args.command == 'registry-scan':
                result = registry_scan(store, transport_for, data)
            elif args.command == 'notice':
                task = store.task(text(data.get('task_id'), 'task_id'))
                result = notice(store, transport_for(store.binding(task['supervisor_id'])), data)
            else:
                method = {'bind': 'bind', 'task-update': 'update_task', 'task-state': 'task_state', 'memory-add': 'add_memory', 'memory-supersede': 'add_memory', 'memory-query': 'memory', 'detach': 'detach', 'execution-result': 'execution_result'}[args.command]
                result = getattr(store, method)(data)
        print(json.dumps({'ok': True, 'result': result}, allow_nan=False))
        return 0
    except (StoreError, sqlite3.Error, OSError, ValueError, TypeError, RuntimeError, KeyError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == '__main__':
    raise SystemExit(main())
