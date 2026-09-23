#!/usr/bin/env python3
"""
reread-hook.py — dormant Stop hook that hands a finished answer back once.

Registered in `~/.claude/settings.json` once, inert by default: the first thing
it does is look for one of two flag files, and if neither is there it exits with
no output and no stdin read.

Two flags, because there are two ways to want this. `/sc <question>` arms it for
the next answer only and the hook clears the flag itself — that is the common
case, and it costs nothing when unused. `/sc on` sets a flag that stays until
`/sc off`, for a stretch of work where every answer should get the pass.

What it is for. The rules about how to answer — run the check you just named,
say what a thing is before naming it, one idea per sentence — already exist, in
the managed `CLAUDE.md` and in this kit's own docs. They are good rules and they
are forgotten, because by the end of a long turn they sit twenty thousand tokens
back. Nothing is wrong with the rule; it is simply out of sight at the moment it
applies. So this hook does not judge the answer and does not classify anything.
It puts the list back in front of the model once, at the only moment it can act
on it: after the answer exists and before the user sees it.

That is why there is no model call here and no pattern matching on the text. A
classifier reading every message would cost money on every turn of every session
and would have to decide, from prose, whether a rule was broken — which is the
kind of judgement this kit does not make with string matching. Re-presenting the
list costs one extra pass of the model already in the session, and the model
does the judging with the answer in front of it.

Firing once is the whole trick. A Stop hook that blocks unconditionally loops:
the session finishes, gets pushed back, finishes again, forever. The payload
carries `stop_hook_active`, which is true on the second pass, and returning
nothing then lets the turn end. Measured: hook fires twice, session exits 0.

Failing open is deliberate. This improves answers; it does not protect anything.
A missing checklist, a malformed payload, an unreadable file — every one of them
ends in "let the turn finish". A quality aid that can wedge a session is worse
than no quality aid.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

KIT_STATE = Path.home() / ".config" / "mrcall-ai-kit"
FLAG = KIT_STATE / "reread.on"        # `/sc on` — stays until `/sc off`
ONCE = KIT_STATE / "reread.once"      # `/sc <question>` — armed for one answer
CHECKLIST = KIT_STATE / "reread-checklist.md"

# Short answers are skipped, because the second pass costs a full model turn and
# a two-line answer rarely earns one. This is a cost dial, not a safety boundary:
# a short answer can still name a check nobody ran. Raise it if the hook feels
# expensive, lower it to 0 to check everything.
MIN_CHARS = int(os.environ.get("SC_MIN_CHARS", "500"))

PREAMBLE = """Before this answer reaches the reader, read it back against the list below.

This is not a request for commentary about the list. Either the answer already
satisfies every line — in which case send it unchanged — or it does not, in
which case fix what fails and send the corrected answer. Do not explain what you
changed, do not mention this list, and do not add a note saying you reviewed it.
The reader sees only the answer.
"""


def disarm() -> None:
    """Spend the one-shot arming, whatever happens next.

    It is cleared before the decision to block, not after, so a turn that is
    skipped for being short — or that fails for any other reason — does not
    leave the guard armed for whatever the user asks next. A one-shot that
    outlives its turn is a toggle nobody switched on.
    """
    try:
        ONCE.unlink()
    except OSError:
        pass


def main() -> int:
    armed_once = ONCE.exists()
    if not (FLAG.exists() or armed_once):
        return 0  # dormant: no stdin read, no output

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0

    # Second pass: the list has already been delivered. Let the turn end, or the
    # session blocks itself forever.
    if payload.get("stop_hook_active"):
        disarm()
        return 0

    answer = payload.get("last_assistant_message")
    if not isinstance(answer, str) or len(answer.strip()) < MIN_CHARS:
        disarm()
        return 0

    try:
        checklist = CHECKLIST.read_text(encoding="utf-8").strip()
    except OSError:
        disarm()
        return 0  # nothing to say: fail open rather than block on a missing file
    if not checklist:
        disarm()
        return 0

    # Spend the arming before blocking, not on the second pass. If the session
    # dies between the two, a flag left behind would silently re-arm whatever
    # the user asks next.
    disarm()
    print(json.dumps({
        "decision": "block",
        "reason": f"{PREAMBLE}\n{checklist}",
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
