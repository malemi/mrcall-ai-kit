"""Explicit setup and execution of supervision's private dependency environment."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

sys.dont_write_bytecode = True
try:
    from .store import Store, StoreError, default_state_dir
except ImportError:
    from store import Store, StoreError, default_state_dir


def location():
    return Path(os.environ.get('MRCALL_SUPERVISION_RUNTIME', default_state_dir() / 'runtime')).absolute()


def validate(root, creating=False):
    for part in [root, *root.parents]:
        if part.is_symlink():
            raise StoreError('symlink runtime directory refused: ' + str(part))
    if root.exists():
        Store._private(root, directory=True)
        marker = root / '.ai-kit-owned'
        if not marker.is_file() or marker.is_symlink() or marker.read_text() != 'supervision-runtime-v1\n':
            raise StoreError('foreign runtime directory refused: ' + str(root))
        Store._private(marker)
    elif creating:
        root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        root.mkdir(mode=0o700, parents=True)
        marker = root / '.ai-kit-owned'
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write('supervision-runtime-v1\n')
    else:
        raise StoreError('supervision runtime is not prepared; run runtime.py setup')


def ready(root):
    python = root / 'bin/python'
    if not python.exists():
        return False
    result = subprocess.run([str(python), '-I', '-c',
                             "import importlib.metadata; from websockets.sync.client import unix_connect; "
                             "assert importlib.metadata.version('websockets') == '16.1'"],
                            capture_output=True, timeout=15)
    return result.returncode == 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['setup', 'run'])
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    root = location()
    try:
        validate(root, creating=args.action == 'setup')
        if args.action == 'setup':
            if args.arguments:
                raise StoreError('setup takes no CLI arguments; use MRCALL_SUPERVISION_RUNTIME for an isolated environment')
            lock = root / '.setup.lock'
            fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                Store._private(lock)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if not ready(root):
                    venv.EnvBuilder(with_pip=True).create(root)
                    subprocess.run([str(root / 'bin/python'), '-I', '-m', 'pip', 'install',
                                    '--disable-pip-version-check', '-r', str(Path(__file__).with_name('requirements.txt'))],
                                   check=True, timeout=180, stdout=sys.stderr)
                if not ready(root):
                    raise StoreError('supervision dependency verification failed')
            finally:
                os.close(fd)
            print(json.dumps({'ok': True, 'runtime': str(root), 'dependency': 'websockets==16.1', 'cron_enabled': False}))
            return 0
        if not ready(root):
            raise StoreError('supervision dependencies missing or changed; rerun runtime.py setup')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        os.execve(str(root / 'bin/python'), [str(root / 'bin/python'), '-B',
                  str(Path(__file__).with_name('cli.py')), *args.arguments], env)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
