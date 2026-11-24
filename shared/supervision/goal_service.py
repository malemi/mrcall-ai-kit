import argparse
import datetime
import fcntl
import hashlib
import json
import math
import os
import pathlib
import socket
import socketserver
import stat
import struct
import sys
import threading


def bootstrap():
    if not sys.flags.isolated:
        raise ValueError("goal service requires Python isolated mode (-I)")
    writable_mask = 0o022 if os.geteuid() == 0 else 0o002
    source = pathlib.Path(__file__).absolute()
    for item in (source, *source.parents):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid not in (0, os.geteuid()):
            raise ValueError(f"untrusted runtime path: {item}")
        if info.st_mode & writable_mask and not (item not in (source, source.parent) and stat.S_ISDIR(info.st_mode) and info.st_mode & stat.S_ISVTX):
            raise ValueError(f"writable runtime path: {item}")
    for item in source.parent.iterdir():
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid not in (0, os.geteuid()) or info.st_mode & writable_mask:
            raise ValueError(f"untrusted runtime member: {item}")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(source.parent))


def object_fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise ValueError("missing or unknown fields")


def text_field(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 16384 or "\0" in value:
        raise ValueError(f"invalid {label}")


def limits(value):
    object_fields(value, ["process_timeout_seconds"], ["max_wakeups", "deadline_at"])
    timeout = value["process_timeout_seconds"]
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise ValueError("invalid process_timeout_seconds")
    if "max_wakeups" in value and (type(value["max_wakeups"]) is not int or value["max_wakeups"] < 0):
        raise ValueError("invalid max_wakeups")
    if "deadline_at" in value:
        if not isinstance(value["deadline_at"], str):
            raise ValueError("deadline_at must be an ISO timestamp")
        stamp = datetime.datetime.fromisoformat(value["deadline_at"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("deadline_at requires timezone")
    return value


def contract(value):
    object_fields(value, ["id", "intent", "scope", "target", "acceptance", "limits"])
    for key in ("id", "intent", "scope"):
        text_field(value[key], key)
    if len(value["id"]) > 128 or not all(c.isascii() and (c.isalnum() or c in "-_.") for c in value["id"]):
        raise ValueError("invalid goal id")
    object_fields(value["target"], ["runtime", "lead_id", "supervisor_id"])
    for key, entry in value["target"].items():
        text_field(entry, key)
    if value["target"]["runtime"] != "codex":
        raise ValueError("unsupported native runtime")
    if not isinstance(value["acceptance"], dict) or not value["acceptance"]:
        raise ValueError("acceptance must be a nonempty immutable object")
    limits(value["limits"])
    result = dict(value)
    result["acceptance_digest"] = hashlib.sha256(json.dumps(value["acceptance"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return result


def configuration(path, protected_path):
    path = protected_path(path, directory=False)
    config = json.loads(path.read_text())
    object_fields(config, ["version", "root", "agent_uid", "agent_gid", "verifier_uid", "verifier_gid", "agent_home", "verifier_home", "native_paths", "cadence_seconds", "native_socket", "codex_path"], ["mode", "ledger_path"])
    mode = config.get("mode", "protected")
    if mode not in ("local", "protected"):
        raise ValueError("unsupported goal mode")
    if mode == "protected" and os.geteuid() != 0:
        raise ValueError("protected service requires root")
    if mode == "local" and os.geteuid() == 0:
        raise ValueError("local service requires a non-root account")
    if config["version"] != 1:
        raise ValueError("unsupported configuration version")
    for key in ("agent_uid", "agent_gid", "verifier_uid", "verifier_gid"):
        if type(config[key]) is not int or not (0 < config[key] < 2**31 or mode == "local" and key.endswith("gid") and config[key] == 0):
            raise ValueError(f"invalid restricted principal: {key}")
    if mode == "protected" and (config["agent_uid"] == config["verifier_uid"] or config["agent_gid"] == config["verifier_gid"]):
        raise ValueError("agent and verifier must have distinct non-root principals and groups")
    if mode == "local" and any(config[f"{principal}_{field}"] != value for principal in ("agent", "verifier") for field, value in (("uid", os.geteuid()), ("gid", os.getegid()))):
        raise ValueError("local identities must match the service account")
    root = protected_path(config["root"], directory=True)
    if path != root / "config.json" or pathlib.Path(__file__).absolute().parent != root / "code":
        raise ValueError("configuration and runtime must belong to the same protected installation")
    for directory in ("state", "acceptance", "evidence"):
        item = protected_path(root / directory, directory=True)
        if item.stat().st_mode & 0o077:
            raise ValueError(f"private directory permits other principals: {item}")
    for key, uid_key in (("agent_home", "agent_uid"), ("verifier_home", "verifier_uid")):
        home = pathlib.Path(config[key])
        if not home.is_absolute() or ".." in home.parts or not home.is_dir() or home.is_symlink() or home.stat().st_uid != config[uid_key]:
            raise ValueError(f"invalid {key}")
    if not isinstance(config["native_paths"], list) or not all(isinstance(p, str) and os.path.isabs(p) and "\0" not in p for p in config["native_paths"]):
        raise ValueError("native_paths must be absolute paths")
    cadence = config["cadence_seconds"]
    if type(cadence) not in (int, float) or not math.isfinite(cadence) or not 0.05 <= cadence <= 86400:
        raise ValueError("cadence_seconds must be between 0.05 and 86400")
    if config["native_socket"] is not None and (not isinstance(config["native_socket"], str) or not os.path.isabs(config["native_socket"])):
        raise ValueError("native_socket must be an absolute path")
    if "ledger_path" in config and (not isinstance(config["ledger_path"], str) or not os.path.isabs(config["ledger_path"])):
        raise ValueError("ledger_path must be an absolute path")
    if not isinstance(config["codex_path"], str) or not config["codex_path"] or "\0" in config["codex_path"]:
        raise ValueError("invalid codex_path")
    for directory in ("runs", "deps"):
        protected_path(root / directory, directory=True)
    for item in (root / "deps").rglob("*"):
        protected_path(item)
    return config


def dispatch(store, config, peer_uid, request, acceptance, driver):
    if peer_uid not in (0, config["agent_uid"]):
        raise PermissionError("peer principal is not authorized")
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    operation = request.get("op")
    if operation not in ("create", "inspect", "report", "check_request", "stop", "resume", "set_limits", "tick"):
        raise ValueError("unknown operation")
    operator_uid = os.geteuid() if config.get("mode", "protected") == "local" else 0
    if operation in ("create", "stop", "resume", "set_limits", "tick") and peer_uid not in (0, operator_uid):
        raise PermissionError("operator operation requires controller-owner peer credentials")
    if operation == "create":
        object_fields(request, ["op", "goal"])
        value = contract(request["goal"])
        value["acceptance"] = acceptance.bind(value["acceptance"])
        value["acceptance_digest"] = hashlib.sha256(json.dumps(value["acceptance"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        return store.create(value)
    if operation == "tick":
        object_fields(request, ["op"])
        return driver.tick(force=True)
    required = ["op", "id"] + ([] if operation == "inspect" else ["generation"])
    if operation == "report":
        required.append("report")
    if operation == "set_limits":
        required.append("limits")
    object_fields(request, required)
    text_field(request["id"], "id")
    if operation == "inspect":
        return store.get(request["id"])
    if type(request["generation"]) is not int or request["generation"] < 1:
        raise ValueError("invalid generation")
    payload = None
    if operation == "report":
        if not isinstance(request["report"], dict):
            raise ValueError("report must be an object")
        payload = request["report"]
    if operation == "set_limits":
        payload = limits(request["limits"])
    return store.apply(request["id"], request["generation"], operation, payload)


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(5)
        try:
            unused_pid, uid, unused_gid = struct.unpack("3i", self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
            line = self.rfile.readline(65537)
            if len(line) > 65536 or not line.endswith(b"\n"):
                raise ValueError("request exceeds limit or lacks newline")
            def reject_constant(value):
                raise ValueError("nonfinite JSON value")
            request = json.loads(line, parse_constant=reject_constant)
            result = dispatch(self.server.store, self.server.config, uid, request, self.server.acceptance, self.server.driver)
            response = {"ok": True, "result": result}
        except Exception as error:
            response = {"ok": False, "error": str(error)}
        try:
            self.wfile.write(json.dumps(response, allow_nan=False).encode() + b"\n")
        except OSError:
            pass


class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    request_queue_size = 32


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    bootstrap()
    from goal_child import protected_path
    from goal_store import GoalStore
    from goal_acceptance import Acceptance
    from goal_driver import Driver
    config = configuration(args.config, protected_path)
    os.umask(0o077)
    root = pathlib.Path(config["root"])
    lock_path = root / "state" / "service.lock"
    if lock_path.exists() or lock_path.is_symlink():
        protected_path(lock_path, directory=False)
    lock = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    database = root / "state" / "goals.sqlite3"
    for item in (root / "state").iterdir():
        protected_path(item, directory=False)
    store = GoalStore(database)
    acceptance = Acceptance(config)
    driver = Driver(config, store, acceptance)
    stopping = threading.Event()

    def advance():
        while not stopping.wait(config["cadence_seconds"]):
            try:
                driver.tick()
            except Exception as error:
                print(json.dumps({"driver_error": str(error)}), file=sys.stderr, flush=True)
    address = root / "control.sock"
    if address.exists() or address.is_symlink():
        info = address.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid():
            raise ValueError("unsafe existing control socket")
        address.unlink()
    try:
        with Server(str(address), Handler) as server:
            server.store = store
            server.config = config
            server.acceptance = acceptance
            server.driver = driver
            threading.Thread(target=advance, daemon=True).start()
            os.chmod(address, 0o600 if config.get("mode", "protected") == "local" else 0o666)
            print(json.dumps({"ready": True, "socket": str(address)}), flush=True)
            server.serve_forever(poll_interval=0.2)
    finally:
        stopping.set()
        address.unlink(missing_ok=True)
        os.close(lock)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        sys.exit(1)
