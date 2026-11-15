import argparse
import json
import math
import os
import pathlib
import shutil
import stat
import sys


ASSETS = ("goal_service.py", "goal_store.py", "goal_client.py", "goal_setup.py", "goal_child.py", "goal_acceptance.py", "goal_driver.py", "goal_native.py", "goal.service", "ledger.py")


def parent_safe(path, owner):
    writable_mask = 0o022 if owner == 0 else 0o002
    for item in (path, *path.parents):
        info = item.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid not in (0, owner) or (info.st_mode & writable_mask and not info.st_mode & stat.S_ISVTX):
            raise ValueError(f"unsafe installation ancestor: {item}")


def setup(args):
    if not sys.flags.isolated:
        raise ValueError("setup requires Python isolated mode (-I)")
    if args.mode == "protected" and os.geteuid() != 0:
        raise ValueError("protected setup requires root")
    if args.mode == "local" and os.geteuid() == 0:
        raise ValueError("local setup requires a non-root account; use --mode protected for root provisioning")
    if args.mode == "local":
        for principal in ("agent", "verifier"):
            values = {"uid": os.geteuid(), "gid": os.getegid(), "home": str(pathlib.Path.home())}
            for field, default in values.items():
                key = f"{principal}_{field}"
                if getattr(args, key) is None:
                    setattr(args, key, default)
            if getattr(args, f"{principal}_uid") != os.geteuid() or getattr(args, f"{principal}_gid") != os.getegid():
                raise ValueError("local identities must match the current account")
    elif any(getattr(args, f"{principal}_{field}") is None for principal in ("agent", "verifier") for field in ("uid", "gid", "home")):
        raise ValueError("protected setup requires explicit agent and verifier UID, GID and home")
    root = pathlib.Path(args.root)
    if not root.is_absolute() or ".." in root.parts or root.exists() or root.is_symlink():
        raise ValueError("installation root must be a new absolute path")
    parent_safe(root.parent, os.geteuid())
    for value in (args.agent_uid, args.agent_gid, args.verifier_uid, args.verifier_gid):
        if not (0 < value < 2**31 or args.mode == "local" and value == 0):
            raise ValueError("agent and verifier identities must be non-root")
    if args.mode == "protected" and (args.agent_uid == args.verifier_uid or args.agent_gid == args.verifier_gid):
        raise ValueError("agent and verifier principals and groups must differ")
    for home, uid in ((args.agent_home, args.agent_uid), (args.verifier_home, args.verifier_uid)):
        path = pathlib.Path(home)
        if not path.is_absolute() or ".." in path.parts or path.is_symlink() or not path.is_dir() or path.stat().st_uid != uid:
            raise ValueError("restricted home must be an existing directory owned by its principal")
    if any(not os.path.isabs(path) or "\0" in path for path in args.native_path):
        raise ValueError("native paths must be absolute")
    if not math.isfinite(args.cadence_seconds) or not 0.05 <= args.cadence_seconds <= 86400:
        raise ValueError("cadence_seconds must be between 0.05 and 86400")
    if args.native_socket is not None and not os.path.isabs(args.native_socket):
        raise ValueError("native_socket must be absolute")
    if args.codex_path != "codex" and not os.path.isabs(args.codex_path):
        raise ValueError("codex_path must be absolute")
    source = pathlib.Path(__file__).absolute().parent
    transport = source / "codex_transport.py"
    if not transport.exists():
        transport = source.parent.parent / "codex" / "supervision" / "transport.py"
    if transport.is_symlink() or not transport.is_file():
        raise ValueError("missing trusted Codex transport asset")
    dependency = pathlib.Path(args.websockets_source) if args.websockets_source else None
    if dependency is not None:
        if not dependency.is_absolute() or dependency.is_symlink() or not dependency.is_dir() or not (dependency / "__init__.py").is_file():
            raise ValueError("websockets-source must name an absolute package directory")
        for item in dependency.rglob("*"):
            if item.is_symlink() or not (item.is_file() or item.is_dir()):
                raise ValueError("websockets source contains unsupported files")
    for name in ASSETS:
        item = source / name
        if item.is_symlink() or not item.is_file():
            raise ValueError(f"missing or symlinked trusted source asset: {name}")
    os.umask(0o077)
    root.mkdir(mode=0o755)
    os.chmod(root, 0o755)
    try:
        (root / "code").mkdir(mode=0o755)
        os.chmod(root / "code", 0o755)
        for name in ASSETS:
            shutil.copyfile(source / name, root / "code" / name)
            os.chmod(root / "code" / name, 0o644)
        shutil.copyfile(transport, root / "code" / "codex_transport.py")
        os.chmod(root / "code" / "codex_transport.py", 0o644)
        for name in ("runs", "deps"):
            (root / name).mkdir(mode=0o755)
            os.chmod(root / name, 0o755)
        if dependency is not None:
            shutil.copytree(dependency, root / "deps" / "websockets")
            for item in (root / "deps").rglob("*"):
                os.chmod(item, 0o755 if item.is_dir() else 0o644)
        for name in ("state", "acceptance", "evidence"):
            (root / name).mkdir(mode=0o700)
        config = {"version": 1, "mode": args.mode, "root": str(root), "agent_uid": args.agent_uid, "agent_gid": args.agent_gid, "verifier_uid": args.verifier_uid, "verifier_gid": args.verifier_gid, "agent_home": args.agent_home, "verifier_home": args.verifier_home, "native_paths": args.native_path, "cadence_seconds": args.cadence_seconds, "native_socket": args.native_socket, "codex_path": args.codex_path}
        if args.mode == "local":
            sys.path.insert(0, str(source))
            from ledger import default_path
            config["ledger_path"] = str(default_path())
        (root / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
        os.chmod(root / "config.json", 0o600)
    except BaseException:
        shutil.rmtree(root)
        raise
    return {"ok": True, "root": str(root), "config": str(root / "config.json"), "socket": str(root / "control.sock")}


def main():
    parser = argparse.ArgumentParser(description="Prepare dormant local or protected goal assets; never activates a service")
    parser.add_argument("--root", required=True)
    parser.add_argument("--mode", choices=("local", "protected"), default="local")
    for principal in ("agent", "verifier"):
        parser.add_argument(f"--{principal}-uid", type=int)
        parser.add_argument(f"--{principal}-gid", type=int)
        parser.add_argument(f"--{principal}-home")
    parser.add_argument("--native-path", action="append", default=[])
    parser.add_argument("--cadence-seconds", type=float, default=180)
    parser.add_argument("--native-socket")
    parser.add_argument("--codex-path", default="codex")
    parser.add_argument("--websockets-source")
    args = parser.parse_args()
    try:
        result = setup(args)
    except (ValueError, OSError) as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
