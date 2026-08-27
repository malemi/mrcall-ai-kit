#!/usr/bin/env python3
"""Codex PreToolUse adapter for degraded scope-guard enforcement."""
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


def _response(action: str, message: str = "", context: str = "") -> dict[str, object]:
    if action == "ignore":
        return {}
    specific: dict[str, object] = {
        "hookEventName": "PreToolUse",
        "permissionDecision": action,
    }
    if message:
        specific["permissionDecisionReason"] = message
    if context:
        specific["additionalContext"] = context
    result: dict[str, object] = {"hookSpecificOutput": specific}
    if message:
        result["systemMessage"] = f"Scope guard (degraded mode): {message}"
    return result


def handle(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("hook payload must be an object")
    core = _load_core()
    event = payload.get("hook_event_name")
    session = payload.get("session_id")
    if not isinstance(session, str):
        raise core.ScopeGuardError("hook payload has no session_id")
    if event == "SessionEnd":
        core.close_session("codex", session)
        return {}
    if event != "PreToolUse":
        return {}
    tool = payload.get("tool_name")
    if tool not in {"apply_patch", "apply_patch_tool", "Edit", "Write"}:
        return {}
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return _response("deny", "Scope guard could not validate this mutation: tool_input is not an object")
    patch = tool_input.get("patch")
    if not isinstance(patch, str):
        patch = tool_input.get("patchText")
    if not isinstance(patch, str):
        patch = tool_input.get("command")
    if not isinstance(patch, str):
        return _response("deny", "Scope guard could not validate this mutation: apply_patch payload has no patch text")
    cwd = Path(payload.get("cwd")) if isinstance(payload.get("cwd"), str) else Path.cwd()
    try:
        mutations = core.parse_apply_patch(patch, cwd)
        turn = payload.get("turn_id", payload.get("message_id", ""))
        turn_id = turn if isinstance(turn, str) else ""
        decisions = [
            core.decide("codex", session, mutation, full_attestation=False, turn_id=turn_id)
            for mutation in mutations
        ]
    except (core.ScopeGuardError, OSError, UnicodeDecodeError) as exc:
        return _response("deny", f"Scope guard could not validate this mutation: {exc}")
    protected = [decision for decision in decisions if decision.action != "ignore"]
    if not protected:
        return {}
    denied = [decision for decision in protected if decision.action == "deny"]
    selected = denied if denied else protected
    message = "\n\n".join(decision.message for decision in selected if decision.message)
    context = "\n\n".join(dict.fromkeys(decision.context for decision in protected if decision.context))
    return _response("deny" if denied else "allow", message, context)


def main() -> int:
    try:
        result = handle(json.load(sys.stdin))
    except Exception as exc:
        result = _response("deny", f"Scope guard adapter failed closed: {exc}")
    if result:
        print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
