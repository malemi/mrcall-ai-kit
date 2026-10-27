import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.dont_write_bytecode = True

if __package__:
    from .store import Store, StoreError
    from .scheduler import Scheduler, native_transport, execution_read, transport_read, reconcile_execution
    from .cron import activate, deactivate, deactivate_owned
    from .harness import inspect as harness_inspect
    from .control import intervene, intervention_status, session_read, reconcile_intervention, current_execution
else:
    from store import Store, StoreError
    from scheduler import Scheduler, native_transport, execution_read, transport_read, reconcile_execution
    from cron import activate, deactivate, deactivate_owned
    from harness import inspect as harness_inspect
    from control import intervene, intervention_status, session_read, reconcile_intervention, current_execution


def main(argv=None):
    parser = argparse.ArgumentParser(description='Persistent ai-kit supervision tasks and memory')
    parser.add_argument('--state-dir')
    parser.add_argument('command', choices=['init', 'bind', 'task-create', 'task-update', 'task-state', 'list', 'status', 'memory-add', 'memory-supersede', 'memory-query', 'detach', 'execution-result', 'tick', 'execution-read', 'execution-reconcile', 'intervention-reconcile', 'transport-read', 'activate', 'deactivate', 'deactivate-owned', 'harness-inspect', 'intervene', 'intervention-status', 'session-read'])
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
            else:
                method = {'bind': 'bind', 'task-create': 'create_task', 'task-update': 'update_task', 'task-state': 'task_state', 'memory-add': 'add_memory', 'memory-supersede': 'add_memory', 'memory-query': 'memory', 'detach': 'detach', 'execution-result': 'execution_result'}[args.command]
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
