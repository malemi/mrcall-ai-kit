# Active Context Archive

Pruned session narrative from [`active-context.md`](active-context.md), dated,
newest first, preserved verbatim. Cold storage: never read by `/doc-start`,
queried on demand to answer "when did we do X" without reconstructing it from
`git log -p`.

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
