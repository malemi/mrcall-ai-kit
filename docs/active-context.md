---
doc_baseline_commit: c30a36e1af2511cdca8d344223e0fc9a1688116c
doc_baseline_date: 2026-08-21
---

# Active Context

Living snapshot of current repository state. Replace stale information instead
of appending session history; Git and completed briefs retain that history.

## State now

Harness v3 is in force across Claude Code, Codex, and OpenCode; the full
contract is [`documentation-harness.md`](documentation-harness.md).

An opt-in Claude Code model router has been added (work trace:
[`docs/briefs/2026-08-21-cc-model-router.md`](briefs/2026-08-21-cc-model-router.md) /
[`docs/execution-plans/2026-08-21-cc-model-router.md`](execution-plans/2026-08-21-cc-model-router.md)):
a dormant `UserPromptSubmit` hook (`claude/scripts/router-hook.py`) that, once
`/router on` creates a flag file, turns the session model into a classifier —
answer trivial prompts directly, delegate the rest to a pinned-model worker
(`worker-sonnet` / `worker-opus` / the new `worker-fable`). Delegated workers
share continuity via a per-session memory file, `docs/sessions/<id>.md` — the
short-lived sibling of `active-context.md`, same living-snapshot discipline,
written by whoever answers a turn, promoted into `active-context.md` and
closed by `/doc-end`. The full contract (shape, write protocol, promotion,
`/router sweep`'s liveness heuristic) is in `documentation-harness.md` §
Session memory. `doc-check.py` validates `docs/sessions/*.md` status
(open/closed) and reports an advisory count of open files; `doc-start` never
reads that directory, the same rule as `docs/projects/**`. `/ai-help` was
added alongside it: introspects whatever commands/skills/agents are actually
installed (frontmatter descriptions), rather than a written list that goes
stale.

Mechanically verified: 39 `doc-check.py` pytest cases (up from 36) and a new
`tests/test_router_install.sh` (5 assertions — sandbox install alone, dropped
without Claude Code selected, no duplicate `worker-fable` manifest entry when
combined with doc-harness, uninstall removes exactly the router artifacts,
hook dormancy/injection) all pass; the mechanical gate is clean on this repo.
**Not yet verified live** — no real session has run `/router on`, restarted,
switched to Haiku, and exercised actual trivial-vs-delegated routing or the
session-memory write/read/promote cycle end to end.

All of the above is currently uncommitted in the working tree.

## Unresolved

- None.

## Next

- Run the router's live smoke test: `/router on`, restart the session,
  `/model haiku`, then confirm trivial prompts are answered directly and hard
  ones are delegated, and that a delegated worker's session-memory write is
  read back and promoted correctly by `/doc-end`.
- Commit this session's changes once the live smoke test above passes (or
  sooner, if the router feature is committed unverified — that's a call for
  whoever runs the smoke test to make explicitly, not a default).
- Exercise `doc-create`'s v1→v2 migration path against a real v1 repository
  (not just `doc-critic`'s repair in isolation, which is already verified) to
  confirm the migration note produces the same archive-and-trim result when
  entered through the version-mismatch flow rather than invoked directly.
- On the next protocol change, bump the embedded command/checker version and
  add its explicit repository migration before releasing it.
- Rewrite `opencode/skills/orchestrator/REVIEW.md` in English, or supersede
  and archive it (logged in `harness-backlog.md`).
