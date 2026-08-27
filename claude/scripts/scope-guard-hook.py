#!/usr/bin/env python3
"""Claude Code hook adapter for the shared scope-guard engine."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType


def _load_core() -> ModuleType:
    configured = os.environ.get("MRCALL_SCOPE_GUARD_CORE")
    candidates = [
        Path(configured) if configured else None,
        Path(__file__).resolve().parents[1] / "scope_guard.py",
        Path(__file__).resolve().parents[2] / "shared" / "scripts" / "scope_guard.py",
        Path.home() / ".config" / "mrcall-ai-kit" / "scope-guard" / "scope_guard.py",
    ]
    for path in candidates:
        if path is not None and path.is_file():
            spec = importlib.util.spec_from_file_location("mrcall_scope_guard", path)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
    raise RuntimeError("scope-guard core was not found")


def _text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            str(item.get("text", "")) for item in value if isinstance(item, dict) and item.get("type") == "text"
        )
    if isinstance(value, dict):
        return _text(value.get("content", value.get("text", "")))
    return ""


def _mutation(core: ModuleType, tool: str, tool_input: dict[str, object], cwd: Path):
    raw_path = tool_input.get("file_path")
    if not isinstance(raw_path, str) or not raw_path:
        raise core.ScopeGuardError(f"{tool} payload has no file_path")
    path = core.canonical_path(raw_path, cwd)
    if tool == "Write":
        content = tool_input.get("content")
        if not isinstance(content, str):
            raise core.ScopeGuardError("Write payload has no string content")
        return core.Mutation(path, "write", content)
    try:
        preimage = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise core.ScopeGuardError(f"cannot reconstruct Edit target `{path}`: {exc}") from exc
    old = tool_input.get("old_string")
    new = tool_input.get("new_string")
    if not isinstance(old, str) or not isinstance(new, str):
        raise core.ScopeGuardError("Edit payload needs string old_string and new_string")
    postimage = core.apply_edit(preimage, old, new, tool_input.get("replace_all") is True)
    return core.Mutation(path, "edit", postimage)


def _decision(event: str, decision: object) -> dict[str, object]:
    if decision.action == "ignore":
        return {}
    output: dict[str, object] = {
        "hookEventName": event,
        "permissionDecision": decision.action,
    }
    if decision.message:
        output["permissionDecisionReason"] = decision.message
    if decision.context:
        output["additionalContext"] = decision.context
    return {"hookSpecificOutput": output}


def handle(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("hook payload must be an object")
    core = _load_core()
    event = payload.get("hook_event_name")
    session = payload.get("session_id")
    if not isinstance(session, str):
        raise core.ScopeGuardError("hook payload has no session_id")
    if event == "SessionEnd":
        core.close_session("claude", session)
        return {}
    if event == "MessageDisplay":
        # Only complete assistant messages from the main display event attest.
        if payload.get("role") not in (None, "assistant"):
            return {}
        core.attest("claude", session, _text(payload.get("message", payload.get("content", ""))))
        return {}
    if event != "PreToolUse":
        return {}
    tool = payload.get("tool_name")
    if tool not in {"Write", "Edit"}:
        return {}
    tool_input = payload.get("tool_input")
    cwd = Path(payload.get("cwd")) if isinstance(payload.get("cwd"), str) else Path.cwd()
    try:
        mutation = _mutation(core, tool, tool_input if isinstance(tool_input, dict) else {}, cwd)
        turn = payload.get("turn_id", payload.get("message_id", ""))
        return _decision(
            "PreToolUse",
            core.decide(
                "claude",
                session,
                mutation,
                full_attestation=True,
                turn_id=turn if isinstance(turn, str) else "",
            ),
        )
    except (core.ScopeGuardError, OSError, UnicodeDecodeError) as exc:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Scope guard could not validate this mutation: {exc}",
            }
        }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        result = handle(payload)
    except Exception as exc:
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Scope guard adapter failed closed: {exc}",
            }
        }
    if result:
        print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
