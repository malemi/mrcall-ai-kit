#!/usr/bin/env python3
"""
router-hook.py — dormant UserPromptSubmit hook for the opt-in model router.

Registered once by `/router on` in `~/.claude/settings.json`, but inert by
default: the first thing it does is check for the flag file `/router`
toggles, and if that is absent it exits with no output and no stdin read —
one `Path.exists()` call, on every prompt of every session, whether or not the
router is in use. When the flag is present, it prints the routing directive
(classify the prompt, delegate to the pinned-model worker that fits) and, if
the working directory has a docs/ tree, names this session's shared-memory
file so delegated workers have continuity across turns.

Plain stdout on exit 0 is treated by Claude Code as additional context for the
model — no JSON envelope needed for that. This script never calls another
model and never touches the network; the session's own model is the
classifier.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FLAG = Path.home() / ".config" / "mrcall-ai-kit" / "router.on"

DIRECTIVE = """\
Router mode is ON. Before acting, classify this request:
- trivial (greetings, acknowledgements, quick factual answers) -> answer directly, one short reply, no tools;
- normal implementation or lookup work -> delegate to worker-sonnet;
- hard analysis, debugging, design -> delegate to worker-opus;
- explicitly requests Fable, or is genuinely frontier-hard / long-horizon -> delegate to worker-fable."""

MEMORY_NOTE = """
Session memory: `{path}`. Create it if missing (frontmatter: status open, session_id, started, repo; then a one-line description). Whoever answers the turn updates it at their own discretion -- a living snapshot of goal, decisions, and open threads; replace stale content, never append a log.

When delegating: tell the worker to read the session file first, give it the question plus any context not yet recorded there, and have it append durable findings back before it reports. Relay the worker's report faithfully. For follow-ups on the same thread, continue the same worker via SendMessage rather than spawning a new one."""


def main() -> int:
    if not FLAG.exists():
        return 0  # dormant: no stdin read, no output

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # malformed input -- fail silent rather than break the prompt

    session_id = payload.get("session_id", "")
    cwd_raw = payload.get("cwd")
    cwd = Path(cwd_raw) if cwd_raw else Path.cwd()
    docs_dir = cwd / "docs"

    directive = DIRECTIVE
    if session_id and docs_dir.is_dir():
        session_file = docs_dir / "sessions" / f"{session_id}.md"
        directive += "\n" + MEMORY_NOTE.format(path=session_file)

    print(directive)
    return 0


if __name__ == "__main__":
    sys.exit(main())
