#!/usr/bin/env python3
"""
router-hook.py — dormant UserPromptSubmit hook for the opt-in model router.

Registered once by `/router on` in `~/.claude/settings.json`, but inert by
default: the first thing it does is check for the flag file `/router`
toggles, and if that is absent it exits with no output and no stdin read —
one `Path.exists()` call, on every prompt of every session, whether or not the
router is in use. When the flag is present, it prints exactly one thing: the
path of this session's shared-memory file, so delegated workers have continuity
across turns.

That path is the only thing this hook knows and no static file can carry. The
standing engineering-lead contract — the delivery lanes, the routing choices,
the review gates — lives in the managed `CLAUDE.md` a repository installs and in
the `description` field of each worker agent, both of which a session already
holds, so this hook does not restate them.

That file's directory is resolved once per session and then pinned, because the
payload's `cwd` is the shell's working directory and one `cd` into a sub-repo
would otherwise move the session's memory for every later turn — silently, since
a successor that follows the moved path finds nothing and starts from an empty
file while the real snapshot sits in another repository. The pin is a one-line
record under `~/.config/mrcall-ai-kit/sessions/`; it is written on the first
routed turn of a session and read on every turn after that, so the path is
decided by where the session began and not by where it currently is. A session
with no docs/ tree in reach at all gets no output at all — an empty line would
otherwise reach the model as context that says nothing.

Plain stdout on exit 0 is treated by Claude Code as additional context for the
model — no JSON envelope needed for that. This script never calls another
model and never touches the network; the session's own model is the
classifier.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

KIT_STATE = Path.home() / ".config" / "mrcall-ai-kit"
FLAG = KIT_STATE / "router.on"
PIN_DIR = KIT_STATE / "sessions"
PIN_MAX_AGE_S = 30 * 24 * 60 * 60
# A session id is a UUID; anything that is not a plain filename-safe token is
# refused, because it is interpolated into both a path and the printed note.
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

MEMORY_NOTE = """Session memory: `{path}`. Create it if missing (frontmatter: status open, session_id, started, repo; then a one-line description). Whoever answers the turn updates it at their own discretion -- a living snapshot of goal, decisions, and open threads; replace stale content, never append a log.

When delegating: tell the worker to read this file first, give it the question plus any context not yet recorded there, and have it append durable findings back before it reports."""


def session_rel(session_id: str) -> Path:
    """The session file's path relative to the repository root."""
    return Path("docs") / "sessions" / f"{session_id}.md"


def read_pin(session_id: str) -> Path | None:
    """The directory this session was pinned to, if the record is still usable."""
    try:
        recorded = (PIN_DIR / session_id).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not recorded:
        return None
    pinned = Path(recorded)
    return pinned if pinned.is_dir() else None


def write_pin(session_id: str, base: Path) -> None:
    """Record the pin, and drop records older than a session can plausibly live.

    A pin that cannot be stored is not an error worth breaking a prompt over:
    the note is still correct for this turn, and the next turn re-resolves.
    """
    try:
        PIN_DIR.mkdir(parents=True, exist_ok=True)
        cutoff = time.time() - PIN_MAX_AGE_S
        for stale in PIN_DIR.iterdir():
            try:
                if stale.is_file() and stale.stat().st_mtime < cutoff:
                    stale.unlink()
            except OSError:
                continue
        (PIN_DIR / session_id).write_text(f"{base}\n", encoding="utf-8")
    except OSError:
        return


def encode_project_dir(path: Path) -> str:
    """Claude Code's project-directory name for `path`: slashes and dots to dashes."""
    return str(path).replace("/", "-").replace(".", "-")


def start_dir(transcript_path: object, cwd: Path) -> Path | None:
    """The directory the session started in, when it is `cwd` or one of its parents.

    Claude Code keeps a session's transcript at
    `~/.claude/projects/<encoded-start-dir>/<session-id>.jsonl`, fixed when the
    session opens and unaffected by any later `cd`. The encoding is lossy — a
    directory whose own name contains a dash or a dot is indistinguishable from
    a deeper path — so this never decodes it. It encodes each candidate and
    compares, which cannot produce a directory that does not exist, and returns
    nothing when the session started outside the current chain.
    """
    if not isinstance(transcript_path, str) or not transcript_path:
        return None
    project_dir = Path(transcript_path).parent.name
    if not project_dir:
        return None
    for candidate in (cwd, *cwd.parents):
        if encode_project_dir(candidate) == project_dir:
            return candidate
    return None


def resolve_base(session_id: str, cwd: Path, transcript_path: object) -> tuple[Path | None, bool]:
    """Where this session's memory file lives, and whether that is a fresh decision.

    Order matters. An existing file wins over every rule, because two files for
    one session is the failure being prevented and a session already split by the
    old cwd-derived path is repaired by adopting the file it already has. Next is
    the directory the session started in. Only a session whose start cannot be
    established falls back to the working directory, and then only if a docs/
    tree is already there — this hook names a path, and never creates one.
    """
    pinned = read_pin(session_id)
    if pinned is not None:
        return pinned, False

    relative = session_rel(session_id)
    started = start_dir(transcript_path, cwd)
    existing = [d for d in (cwd, *cwd.parents) if (d / relative).is_file()]

    if existing:
        # Outermost wins a tie: a stray file left by the old rule is always
        # deeper than the session's own directory, never above it.
        return (started if started in existing else existing[-1]), True
    if started is not None and (started / "docs").is_dir():
        return started, True
    if (cwd / "docs").is_dir():
        return cwd, True
    return None, False


def main() -> int:
    if not FLAG.exists():
        return 0  # dormant: no stdin read, no output

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # malformed input -- fail silent rather than break the prompt
    if not isinstance(payload, dict):
        return 0

    session_id = payload.get("session_id")
    cwd_raw = payload.get("cwd")
    cwd = Path(cwd_raw) if isinstance(cwd_raw, str) and cwd_raw else Path.cwd()
    if not cwd.is_absolute():
        cwd = Path.cwd() / cwd

    if not (isinstance(session_id, str) and SAFE_ID.fullmatch(session_id)):
        return 0
    base, decided_now = resolve_base(session_id, cwd, payload.get("transcript_path"))
    if base is None:
        return 0  # no path to name, so nothing to say: not even a blank line

    if decided_now:
        write_pin(session_id, base)
    print(MEMORY_NOTE.format(path=base / session_rel(session_id)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
