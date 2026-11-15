"""Fixed native adapter bridge, executed only as the restricted session owner."""
import json
import os
from pathlib import Path
import sys


def main():
    if os.geteuid() == 0 or not sys.flags.isolated:
        raise ValueError('native bridge requires an isolated non-root child')
    root = Path(__file__).absolute().parent.parent
    sys.path.insert(0, str(root / 'deps'))
    sys.path.insert(0, str(root / 'code'))
    import websockets
    if websockets.__version__ != '16.1':
        raise ValueError('protected native bridge requires websockets==16.1')
    from codex_transport import NativeTransport
    data = json.loads(sys.argv[1])
    transport = NativeTransport(codex_path=data.get('codex_path') or 'codex', timeout=data['timeout'], socket_path=data.get('socket_path'))
    operation = data['operation']
    if operation == 'metadata':
        result = transport.metadata(data['session_id'])
    elif operation == 'reconcile':
        result = transport.reconcile(data['session_id'], data['event_id'], include_activity=data.get('include_activity', False))
    elif operation == 'send':
        result = transport.send(data['session_id'], data['event_id'], data['message'], allow_busy=False)
    else:
        raise ValueError('unsupported native operation')
    print(json.dumps({'ok': True, 'result': result}, allow_nan=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'ok': False, 'error': str(error), 'uncertain': getattr(error, 'uncertain', True)}))
        sys.exit(1)
