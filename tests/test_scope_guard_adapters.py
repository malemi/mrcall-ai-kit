#!/usr/bin/env python3
"""End-to-end fixture tests for scope-guard runtime adapters."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / "claude" / "scripts" / "scope-guard-hook.py"
CODEX = ROOT / "codex" / "scripts" / "scope-guard-hook.py"
CORE = ROOT / "shared" / "scripts" / "scope_guard.py"
START = "<!-- doc-scope:start -->"
END = "<!-- doc-scope:end -->"


def scoped(scope: str = "Only maintain this fixture.", body: str = "old") -> str:
    return f"{START}\nScope: {scope}\n{END}\n\n{body}\n"


class AdapterFixtures(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.env = os.environ | {
            "SCOPE_GUARD_STATE": str(self.state),
            "MRCALL_SCOPE_GUARD_CORE": str(CORE),
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def call(self, script: Path, payload: dict[str, object]) -> dict[str, object]:
        run = subprocess.run(
            ["python3", str(script)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=self.env,
            check=True,
        )
        self.assertEqual("", run.stderr)
        return json.loads(run.stdout) if run.stdout else {}

    def claude(self, path: Path, content: str, **extra: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "hook_event_name": "PreToolUse",
            "session_id": "claude-session",
            "turn_id": "turn-1",
            "cwd": str(self.root),
            "tool_name": "Write",
            "tool_input": {"file_path": str(path), "content": content},
        }
        payload.update(extra)
        return self.call(CLAUDE, payload)

    def codex(self, patch: str, turn: str = "turn-1") -> dict[str, object]:
        return self.call(
            CODEX,
            {
                "hook_event_name": "PreToolUse",
                "session_id": "codex-session",
                "turn_id": turn,
                "cwd": str(self.root),
                "tool_name": "apply_patch",
                "tool_input": {"patch": patch},
            },
        )

    def test_claude_write_requires_visible_attestation(self) -> None:
        path = self.root / "routing.md"
        path.write_text(scoped(), encoding="utf-8")
        proposed = scoped(body="new")
        first = self.claude(path, proposed)
        hook = first["hookSpecificOutput"]
        self.assertEqual("deny", hook["permissionDecision"])
        self.assertIn("Scope: Only maintain this fixture.", hook["additionalContext"])
        nonce = re.search(r"Scope reason ([A-Za-z0-9_-]+):", hook["permissionDecisionReason"]).group(1)

        retry = self.claude(path, proposed, turn_id="turn-2")
        self.assertEqual("deny", retry["hookSpecificOutput"]["permissionDecision"])
        displayed = self.call(
            CLAUDE,
            {
                "hook_event_name": "MessageDisplay",
                "session_id": "claude-session",
                "message_id": "message-2",
                "role": "assistant",
                "message": f"Scope reason {nonce}: the body update remains inside the declared scope",
            },
        )
        self.assertEqual({}, displayed)
        allowed = self.claude(path, proposed, turn_id="turn-3")
        self.assertEqual("allow", allowed["hookSpecificOutput"]["permissionDecision"])

    def test_claude_edit_reconstructs_postimage_and_denies_malformed_marker(self) -> None:
        path = self.root / "routing.md"
        path.write_text(scoped(), encoding="utf-8")
        result = self.call(
            CLAUDE,
            {
                "hook_event_name": "PreToolUse",
                "session_id": "claude-edit",
                "turn_id": "turn-1",
                "cwd": str(self.root),
                "tool_name": "Edit",
                "tool_input": {"file_path": str(path), "old_string": END, "new_string": ""},
            },
        )
        hook = result["hookSpecificOutput"]
        self.assertEqual("deny", hook["permissionDecision"])
        self.assertIn("malformed scope block", hook["permissionDecisionReason"])

    def test_claude_unmarked_is_silent_and_bash_is_not_intercepted(self) -> None:
        path = self.root / "plain.md"
        path.write_text("plain\n", encoding="utf-8")
        self.assertEqual({}, self.claude(path, "changed\n"))
        self.assertEqual(
            {},
            self.call(
                CLAUDE,
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "claude-session",
                    "tool_name": "Bash",
                    "tool_input": {"command": "touch plain.md"},
                },
            ),
        )

    def test_codex_degraded_retry_requires_a_later_turn(self) -> None:
        path = self.root / "routing.md"
        path.write_text(scoped(), encoding="utf-8")
        patch = "*** Begin Patch\n*** Update File: routing.md\n@@\n-old\n+new\n*** End Patch"
        first = self.codex(patch)
        self.assertEqual("deny", first["hookSpecificOutput"]["permissionDecision"])
        self.assertIn("degraded mode", first["systemMessage"])
        same_turn = self.codex(patch)
        self.assertEqual("deny", same_turn["hookSpecificOutput"]["permissionDecision"])
        later = self.codex(patch, "turn-2")
        self.assertEqual("allow", later["hookSpecificOutput"]["permissionDecision"])
        self.assertIn("Scope: Only maintain this fixture.", later["hookSpecificOutput"]["additionalContext"])

    def test_codex_multi_target_denies_protected_target_in_last_position(self) -> None:
        plain = self.root / "plain.md"
        guarded = self.root / "guarded.md"
        plain.write_text("plain\n", encoding="utf-8")
        guarded.write_text(scoped(), encoding="utf-8")
        patch = (
            "*** Begin Patch\n"
            "*** Update File: plain.md\n@@\n-plain\n+changed\n"
            "*** Update File: guarded.md\n@@\n-old\n+new\n"
            "*** End Patch"
        )
        result = self.codex(patch)
        self.assertEqual("deny", result["hookSpecificOutput"]["permissionDecision"])
        self.assertIn("Only maintain this fixture", result["systemMessage"])

    def test_codex_marker_removal_never_becomes_normal_retry(self) -> None:
        path = self.root / "routing.md"
        path.write_text(scoped(), encoding="utf-8")
        patch = (
            "*** Begin Patch\n*** Update File: routing.md\n@@\n"
            f"-{START}\n-Scope: Only maintain this fixture.\n-{END}\n-\n old\n"
            "*** End Patch"
        )
        first = self.codex(patch)
        later = self.codex(patch, "turn-2")
        self.assertEqual("deny", first["hookSpecificOutput"]["permissionDecision"])
        self.assertEqual("deny", later["hookSpecificOutput"]["permissionDecision"])
        self.assertIn("scope-guard unmark", later["systemMessage"])

    def test_supported_adapter_outputs_never_emit_ask(self) -> None:
        path = self.root / "routing.md"
        path.write_text(scoped(), encoding="utf-8")
        claude = self.claude(path, scoped(body="changed"))
        patch = "*** Begin Patch\n*** Update File: routing.md\n@@\n-old\n+changed\n*** End Patch"
        codex = self.codex(patch)
        self.assertNotIn('"ask"', json.dumps(claude))
        self.assertNotIn('"ask"', json.dumps(codex))


if __name__ == "__main__":
    unittest.main()
