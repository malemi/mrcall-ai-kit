#!/usr/bin/env python3
"""Run one command under a real PTY, forwarding preloaded stdin and output."""
from __future__ import annotations

import errno
import os
import pty
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: pty_run.py COMMAND [ARG ...]", file=sys.stderr)
        return 2
    input_bytes = sys.stdin.buffer.read()
    pid, master = pty.fork()
    if pid == 0:
        os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
    try:
        if input_bytes:
            os.write(master, input_bytes)
        while True:
            try:
                chunk = os.read(master, 65536)
            except OSError as exc:
                if exc.errno == errno.EIO:
                    break
                raise
            if not chunk:
                break
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
    finally:
        os.close(master)
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


if __name__ == "__main__":
    raise SystemExit(main())
