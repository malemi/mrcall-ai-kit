---
doc_baseline_commit: 4918e1aeb7db09a8c0528fe262f9b97ad40a4e4f
doc_baseline_date: 2026-08-21
---

# Active Context

Living snapshot of current repository state. Replace stale information instead
of appending session history; Git and completed briefs retain that history.

## State now

Harness v3 is in force across Claude Code, Codex, and OpenCode; the full
contract is [`documentation-harness.md`](documentation-harness.md).

An opt-in Claude Code model router is committed and installed (work trace:
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

`/router`'s `on`/`off`/`status`/`unregister` output was rewritten (commit
`4918e1a`): it had been printing internals (flag file, symlink, settings.json
registration) on every call; it now prints state plus the next command only,
and expands only when something is actually broken (flag set but hook not
registered).

Mechanically verified: 39 `doc-check.py` pytest cases and `tests/test_router_install.sh`
(5 assertions — sandbox install alone, dropped without Claude Code selected,
no duplicate `worker-fable` manifest entry when combined with doc-harness,
uninstall removes exactly the router artifacts, hook dormancy/injection) all
pass; the mechanical gate is clean on this repo. **Not yet verified live** —
the router has been switched on for real on this machine (hook registered in
`~/.claude/settings.json`, flag present), but no session has cleanly exercised
actual trivial-vs-delegated routing or the session-memory write/read/promote
cycle end to end; see Unresolved and Next.

## Unresolved

- Whether `/router on`'s "restart the session" guidance is actually
  necessary: one session activated the router and the hook fired on the very
  next prompt with no process restart. A single data point, not confirmed
  either way.
- Whether a session can be relied on to know its own active model:
  `/model haiku` reported success and `~/.claude/settings.json` correctly
  persisted `"model": "haiku"` (no project or env override found), and
  Claude Code's own docs say `/model` switches the running session
  immediately, not just new ones — but the visible model indicator kept
  showing Sonnet 5 in the same session, and the session had no way to
  self-verify which model was actually executing. Matters directly for the
  smoke test below.

## Next

- Run the router's live smoke test properly: every attempt so far has had a
  more specific override in play (Plan Mode superseding routing for one
  task, `doc-end`'s own non-delegable phases for a consolidation), so
  trivial-vs-delegated routing has never actually been exercised. Needs a
  plain turn with no such override, plus a way to confirm the acting model
  that doesn't depend on the visible indicator (see Unresolved).
- Exercise `doc-create`'s v1→v2 migration path against a real v1 repository
  (not just `doc-critic`'s repair in isolation, which is already verified) to
  confirm the migration note produces the same archive-and-trim result when
  entered through the version-mismatch flow rather than invoked directly.
- On the next protocol change, bump the embedded command/checker version and
  add its explicit repository migration before releasing it.
- Rewrite `opencode/skills/orchestrator/REVIEW.md` in English, or supersede
  and archive it (logged in `harness-backlog.md`).
