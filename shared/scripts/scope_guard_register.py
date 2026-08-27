#!/usr/bin/env python3
"""Register the mrcall-ai-kit scope guard without disturbing foreign hooks."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile


IDENTITY = "mrcall-ai-kit.scope-guard.v1"


def home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home()))).expanduser()


def kit_dir() -> Path:
    return home() / ".config" / "mrcall-ai-kit"


def adapter(runtime: str) -> Path:
    suffix = "ts" if runtime == "opencode" else "py"
    return kit_dir() / "scope-guard" / runtime / f"scope-guard.{suffix}"


def command(runtime: str) -> str:
    return f'python3 "{adapter(runtime)}"'


def settings_path(runtime: str) -> Path:
    if runtime == "claude":
        return home() / ".claude" / "settings.json"
    if runtime == "codex":
        return home() / ".codex" / "hooks.json"
    raise ValueError(runtime)


def hook_spec(runtime: str) -> list[tuple[str, dict[str, object]]]:
    hook = {"type": "command", "command": command(runtime), "timeout": 10}
    if runtime == "claude":
        return [
            ("PreToolUse", {"matcher": "Edit|Write", "hooks": [hook]}),
            ("MessageDisplay", {"hooks": [hook]}),
            ("SessionEnd", {"hooks": [hook]}),
        ]
    return [("PreToolUse", {"matcher": "Edit|Write", "hooks": [hook]})]


def is_owned_group(value: object, runtime: str) -> bool:
    if not isinstance(value, dict):
        return False
    hooks = value.get("hooks")
    if not isinstance(hooks, list):
        return False
    expected = command(runtime)
    return any(isinstance(item, dict) and item.get("command") == expected for item in hooks)


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


def atomic_json(path: Path, value: dict[str, object], dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".scope-guard.bak"))
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def json_enabled(runtime: str) -> bool:
    value = read_json(settings_path(runtime))
    hooks = value.get("hooks", {})
    if not isinstance(hooks, dict):
        return False
    for event, _ in hook_spec(runtime):
        groups = hooks.get(event)
        if not isinstance(groups, list) or not any(is_owned_group(group, runtime) for group in groups):
            return False
    return True


def mutate_json(runtime: str, enable: bool, dry_run: bool) -> bool:
    path = settings_path(runtime)
    value = read_json(path)
    hooks = value.get("hooks")
    if hooks is None and not enable:
        return False
    if hooks is None:
        hooks = {}
        value["hooks"] = hooks
    if not isinstance(hooks, dict):
        raise RuntimeError(f"{path}: `hooks` must be a JSON object")
    changed = False
    for event, spec in hook_spec(runtime):
        groups = hooks.get(event)
        if groups is None and not enable:
            continue
        if groups is None:
            groups = []
            hooks[event] = groups
        if not isinstance(groups, list):
            raise RuntimeError(f"{path}: `hooks.{event}` must be a JSON array")
        kept = [group for group in groups if not is_owned_group(group, runtime)]
        if enable:
            kept.append(spec)
        if kept != groups:
            hooks[event] = kept
            changed = True
        if not kept:
            hooks.pop(event, None)
            changed = True
    if not hooks:
        value.pop("hooks", None)
    if changed:
        atomic_json(path, value, dry_run)
    return changed


def opencode_plugin() -> Path:
    return home() / ".config" / "opencode" / "plugins" / "mrcall-scope-guard.ts"


def opencode_enabled() -> bool:
    active = opencode_plugin()
    source = adapter("opencode")
    return active.is_symlink() and active.resolve(strict=False) == source.resolve(strict=False)


def mutate_opencode(enable: bool, dry_run: bool) -> bool:
    active = opencode_plugin()
    source = adapter("opencode")
    if enable:
        if not source.exists():
            raise RuntimeError(f"scope guard adapter is not installed: {source}")
        if active.exists() or active.is_symlink():
            if opencode_enabled():
                return False
            raise RuntimeError(f"refusing to replace foreign OpenCode plugin: {active}")
        if not dry_run:
            active.parent.mkdir(parents=True, exist_ok=True)
            active.symlink_to(source)
        return True
    if opencode_enabled():
        if not dry_run:
            active.unlink()
        return True
    return False


def installed(runtime: str) -> bool:
    return adapter(runtime).exists()


def remove_state(runtime: str, dry_run: bool) -> None:
    state = kit_dir() / "scope-guard" / "state" / runtime
    if state.exists() and not dry_run:
        shutil.rmtree(state)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", choices=("claude", "codex", "opencode"))
    parser.add_argument("action", choices=("on", "off", "status", "unregister"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        enabled = opencode_enabled() if args.runtime == "opencode" else json_enabled(args.runtime)
        if args.action == "status":
            if enabled:
                if args.runtime == "codex":
                    print(f"scope guard for codex: registered; trust unverified (confirm in /hooks) ({IDENTITY})")
                else:
                    print(f"scope guard for {args.runtime}: enabled ({IDENTITY})")
            elif installed(args.runtime):
                print(f"scope guard for {args.runtime}: installed, dormant")
            else:
                print(f"scope guard for {args.runtime}: not installed")
            return 0
        if args.action == "on" and not installed(args.runtime):
            raise RuntimeError(f"scope guard for {args.runtime} is not installed")
        enable = args.action == "on"
        changed = (
            mutate_opencode(enable, args.dry_run)
            if args.runtime == "opencode"
            else mutate_json(args.runtime, enable, args.dry_run)
        )
        if not enable:
            remove_state(args.runtime, args.dry_run)
        verb = "would enable" if args.dry_run and enable else "would disable" if args.dry_run else "enabled" if enable else "disabled"
        if args.runtime == "codex" and enable and not args.dry_run:
            verb = "registered; trust unverified (confirm in /hooks)"
        suffix = "" if changed else " (already in requested state)"
        print(f"scope guard for {args.runtime}: {verb}{suffix}")
        return 0
    except RuntimeError as exc:
        print(f"scope-guard: {exc}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
