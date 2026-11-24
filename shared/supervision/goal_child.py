import contextlib
import ctypes
import json
import os
import pathlib
import selectors
import signal
import stat
import subprocess
import sys
import time


def protected_path(path, directory=None):
    writable_mask = 0o022 if os.geteuid() == 0 else 0o002
    path = pathlib.Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("protected path must be absolute without parent traversal")
    for item in reversed((path, *path.parents)):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid not in (0, os.geteuid()):
            raise ValueError(f"untrusted owner or symlink: {item}")
        writable = info.st_mode & writable_mask
        sticky_ancestor = item != path and stat.S_ISDIR(info.st_mode) and info.st_mode & stat.S_ISVTX
        if writable and not sticky_ancestor:
            raise ValueError(f"unprotected path: {item}")
    if directory is True and not path.is_dir():
        raise ValueError("expected protected directory")
    if directory is False and not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("expected protected regular file")
    return path


def run_child(argv, *, uid, gid, home, cwd, timeout, env=None, max_output=1048576, admission=None):
    local = os.geteuid() != 0
    if type(uid) is not int or uid <= 0 or type(gid) is not int or gid < 0 or not local and gid == 0:
        raise ValueError("child requires a non-root identity")
    if local and (uid != os.geteuid() or gid != os.getegid()):
        raise ValueError("local child identities must match the current account")
    if not isinstance(argv, list) or not argv or not all(isinstance(arg, str) and "\0" not in arg for arg in argv) or not os.path.isabs(argv[0]):
        raise ValueError("child argv must start with an absolute executable")
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 3600:
        raise ValueError("child timeout must be between zero and 3600 seconds")
    if type(max_output) is not int or not 0 < max_output <= 16777216:
        raise ValueError("invalid output bound")
    environment = {"PATH": "/usr/bin:/bin", "HOME": str(home), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    if env:
        if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) and "=" not in k and "\0" not in k + v for k, v in env.items()):
            raise ValueError("invalid child environment")
        environment.update(env)
    launcher_env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    if local:
        command = argv
        launcher_env = environment
        launch_directory = cwd
    else:
        unshare = "/usr/bin/unshare"
        if not pathlib.Path(unshare).is_file():
            raise ValueError("child isolation requires util-linux /usr/bin/unshare and permission to create PID/mount namespaces")
        namespace = [unshare, "--pid", "--fork", "--kill-child=KILL", "--mount-proc", "--"]
        probe = subprocess.run(namespace + ["/usr/bin/true"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=launcher_env, close_fds=True, timeout=5)
        if probe.returncode:
            raise ValueError("child PID/mount namespace prerequisite failed: " + probe.stderr.decode("utf-8", "replace").strip())
        payload = json.dumps({"argv": argv, "uid": uid, "gid": gid, "cwd": str(cwd), "env": environment}, allow_nan=False)
        command = namespace + ["/usr/bin/python3", "-I", str(pathlib.Path(__file__).absolute()), "--restricted-child", payload]
        launch_directory = "/"
    libc = ctypes.CDLL(None, use_errno=True)
    parent_pid = os.getpid()

    def parent_death():
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "cannot bind child to controller lifetime")
        if os.getppid() != parent_pid:
            os.kill(os.getpid(), signal.SIGKILL)

    started = time.monotonic()
    with admission() if admission is not None else contextlib.nullcontext():
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=launch_directory, env=launcher_env, close_fds=True, start_new_session=True, preexec_fn=parent_death)
    output = {"stdout": bytearray(), "stderr": bytearray()}
    reason = None
    selector = selectors.DefaultSelector()
    for name in output:
        selector.register(getattr(process, name), selectors.EVENT_READ, name)
    try:
        while selector.get_map():
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                reason = "timeout"
                break
            for key, unused in selector.select(min(remaining, 0.1)):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                available = max_output - sum(len(value) for value in output.values())
                output[key.data].extend(chunk[:available])
                if len(chunk) > available:
                    reason = "output_limit"
                    break
            if reason:
                break
        if not reason:
            try:
                process.wait(timeout=max(0.001, timeout - (time.monotonic() - started)))
            except subprocess.TimeoutExpired:
                reason = "timeout"
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        selector.close()
        process.stdout.close()
        process.stderr.close()
    return {"argv": argv, "uid": uid, "gid": gid, "exit_code": process.returncode, "termination": reason, "stdout": output["stdout"].decode("utf-8", "replace"), "stderr": output["stderr"].decode("utf-8", "replace"), "elapsed_seconds": time.monotonic() - started}


def restricted_child(payload):
    if os.geteuid() != 0 or os.getpid() != 1 or not sys.flags.isolated:
        raise ValueError("restricted child must start as root PID 1 in an isolated namespace")
    request = json.loads(payload)
    child = os.fork()
    if child:
        unused_pid, status = os.waitpid(child, 0)
        code = os.waitstatus_to_exitcode(status)
        raise SystemExit(code if code >= 0 else 128 - code)
    libc = ctypes.CDLL(None, use_errno=True)
    os.setgroups([])
    os.setgid(request["gid"])
    os.setuid(request["uid"])
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "cannot set no_new_privs")
    os.chdir(request["cwd"])
    os.execve(request["argv"][0], request["argv"], request["env"])


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--restricted-child":
        raise SystemExit("goal_child is an internal isolated-process launcher")
    restricted_child(sys.argv[2])
