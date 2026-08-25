# Active Context Archive

Pruned session narrative from [`active-context.md`](active-context.md), dated,
newest first, preserved verbatim. Cold storage: never read by `/doc-start`,
queried on demand to answer "when did we do X" without reconstructing it from
`git log -p`.

## 2026-08-25 — the router's pre-live verification record

Superseded by live use on 2026-08-25, when the router drove a full working
session. Kept because it is the record of what had and had not been proved
before that.

`/router`'s `on`/`off`/`status`/`unregister` output was rewritten (commit
`4918e1a`): it had been printing internals (flag file, symlink, settings.json
registration) on every call; it now prints state plus the next command only,
and expands only when something is actually broken (flag set but hook not
registered).

Mechanically verified: 45 `doc-check.py` pytest cases and
`tests/test_router_install.sh` (8 assertions — sandbox install alone, dropped
without Claude Code selected, no duplicate `worker-fable` manifest entry when
combined with doc-harness, uninstall removes exactly the router artifacts, hook
dormancy/injection, the session path held across a cd, an existing session file
adopted rather than duplicated, the start directory recovered from the
transcript path) all pass; the mechanical gate is clean on this repo. **Not yet
verified live** — the router has been switched on for real on this machine
(hook registered in `~/.claude/settings.json`, flag present), but no session has
cleanly exercised actual trivial-vs-delegated routing or the session-memory
write/read/promote cycle end to end.

Every live attempt up to that point had had a more specific override in play:
Plan Mode superseding routing for one task, `doc-end`'s own non-delegable
phases for a consolidation.

## 2026-08-21 — Router feature confirmed committed; status-output UX fix

Earlier `active-context.md` stated the router feature (hook, `/router`
command, session-memory contract, `/ai-help`) was "currently uncommitted in
the working tree," pending a live smoke test before committing. That
sentence became stale: the feature was committed (`19cfc61`) before this
correction was made, without the smoke test having passed — a deliberate
call left open by the prior wording ("or sooner, if the router feature is
committed unverified — that's a call for whoever runs the smoke test to
make explicitly, not a default").

## 2026-08-15 — Harness v3 in force; work-trace rule with four enforcement points (as recorded)

Harness v3 is implemented and committed across Claude Code, Codex, and
OpenCode. The full contract lives in
[`documentation-harness.md`](documentation-harness.md); enforcement of the
living-context shape is three-layered, with the heading half mechanical in
`doc-check.py`. `doc-end` delegates to pinned-model workers (`worker-sonnet`
mechanical, `worker-opus` verification) where the environment provides them;
gathering the session signal and deciding what is current stay non-delegable.
All `doc-*` workflows require an exact `harness_version` match before doing
work.

The work-trace rule is in force (2026-08-14): orchestrated or multi-session
work creates `docs/briefs/YYYY-MM-DD-<slug>.md` +
`docs/execution-plans/YYYY-MM-DD-<slug>.md` before execution, with lifecycle
only in the plan's `status` frontmatter. Four enforcement points: `doc-create`
ships the briefs directory and writes the one-line pointer into the configured
index (the trigger binding — it fires exactly in harness repos); `doc-end`
Phase 3 creates a missing pair in-session and must fill a mandatory *work
trace* output slot; a delegated `doc-critic` reports a `TRACE:` finding
instead of inventing content; `doc-check.py` reports undated trace filenames
as an advisory. The OpenCode orchestrator persists this pair natively (its
private `docs/plans/execution.md` schema is gone) and its question templates
are in English.

The gate emits two advisory families, never affecting the exit code:
`doc_max_lines` (default 400, archive exempt) and undated work-trace
filenames. 36 checker tests pass. The root `README.md` is human-facing (82
lines: value proposition plus two-minute install; protocol internals live
only in the contract). This machine installs the kit in symlink mode, so the
installed commands and checker track the working tree with no reinstall.

## 2026-08-04 — Harness v3: shape enforcement, workers, version handshake (as recorded)

Harness version 3 is implemented across Claude Code, Codex, and OpenCode.
Pruned `active-context.md` narrative now moves to `active-context-archive.md`
(dated, newest first, verbatim, never read by `doc-start`) instead of being
discarded: `doc-end` Phase 3 archives it proactively every session, and
`doc-critic` independently checks the file's shape — the backstop for the exact
failure the plain instruction alone did not prevent (a real downstream repo's
`active-context.md` grew from ~120 to ~1500 lines over two months of sessions
that each said "consolidate"). Whether that check repairs or only reports
follows the delegation boundary: in-session it repairs, delegated it reports a
blocking finding, because sorting current from historical needs the transcript
a subagent does not have. The repair was verified against a real scratch
fixture, byte-for-byte zero information loss.

Since v3 the heading half of that shape is **mechanical**: `doc-check.py`
fails on any `##` section in `active-context.md` outside the canonical three
(code fences excluded; the archive exempt). The two LLM layers above it each
failed in practice — one repo drifted to ~1500 lines over two months of
consolidations, then lost 1436 lines and four durable invariants to a session
that never invoked `doc-end` at all, which no instruction to an agent can
prevent. Replayed against that repo's real pre-trim file, the check reports 27
violations. The durable contract is in
[`documentation-harness.md`](documentation-harness.md); 21 checker tests + the
Codex install layout test pass.

`doc-end` delegates its delegable work to pinned-model workers where the
environment has them: `worker-sonnet` for mechanical execution, `worker-opus`
for independent verification. Claude Code gets them from `claude/agents/`,
installed to `~/.claude/agents/` with `doc-harness`; OpenCode already had
`worker-sonnet` in its own roster. Because each worker declares `model:`, the
tier follows the task rather than the session — verified live in both
directions. Gathering the session signal and deciding what is current are
declared non-delegable: only the session holding the transcript can do either.

All `doc-*` workflows now require an exact `harness_version` match before doing
work. Directional failures distinguish a stale installed kit from repository
docs that need an explicitly authorized migration.

Codex receives native user-level skills under `$HOME/.agents/skills`; install
and uninstall were verified in disposable HOME directories in both copy and
symlink modes.

## 2026-07-25 — OpenRouter Auto Router experiment

The OpenRouter Auto Router experiment is complete. The working OpenCode agent
model ID is `openrouter/openrouter/auto`, and delegation was verified
end-to-end. Retained evidence and superseded hypotheses live in
[`briefs/2026-08-01-test-worker-auto.md`](briefs/2026-08-01-test-worker-auto.md), not in this volatile
snapshot.
