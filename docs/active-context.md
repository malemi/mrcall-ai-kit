---
doc_baseline_commit: 4d04b3c01c2873d9567b9bbf58baf84fd8c5760e
doc_baseline_date: 2026-08-25
---

# Active Context

Living snapshot of current repository state. Replace stale information instead
of appending session history; Git and completed briefs retain that history.

## State now

Harness v3 is in force across Claude Code, Codex, and OpenCode. The contract is
[`documentation-harness.md`](documentation-harness.md); the router half of it
was split out to [`model-router.md`](model-router.md) on 2026-08-25, when the
first document grew a second subject and the gate named it.

**The context-economics workstream is finished** (work trace:
[`briefs/2026-08-24-harness-context-economics.md`](briefs/2026-08-24-harness-context-economics.md)
/ [`execution-plans/2026-08-24-harness-context-economics.md`](execution-plans/2026-08-24-harness-context-economics.md),
`status: completed`). What the harness now does that it did not:

- The gate prints bytes and an estimated token count beside every line count,
  and `doc-end` must record a `split` or `keep whole` verdict in
  `harness-backlog.md` for each oversized document it names.
- **`split` means deletion, never relocation** — stated at length in
  `doc-end.md`, as contract in `documentation-harness.md`, and pinned by a test
  so an edit cannot quietly drop it. Cutting a document that has grown a second
  subject into a new document that stands alone is allowed; moving text into an
  *existing* document to shrink a line count is not, nor is writing into a
  generated file, and an as-built document is never an append target.
- In `meta` mode the gate names every sub-repo index with no orientation head
  (`<!-- orientation ends -->`), and `doc-start` carries the matching routing
  rule: the ownership map answers by itself, so a sub-repo index is opened when
  work enters that repository's code, never to decide whether it belongs there.
- Every `worker-*` agent carries a `## Report budget` — twenty lines, no diff,
  no file listing, no stack trace — with `Unverified:` and `Evidence:` in the
  `## Done` block and long evidence going to `$TMPDIR/mrcall-ai-kit/<task-id>/`.
- The caller's own reading budget, about a hundred lines per request, rides in
  the router's injected directive, alongside the rule that a worker's report is
  relayed in your own words and never pasted verbatim.
- Session rotation has a `## Hand-off` contract (constraints first, because
  compaction destroys those first) and a resume rule: the successor reads the
  hand-off plus `active-context.md` and does **not** run `/doc-start`.

**One standing constraint came out of it: this kit installs no hooks on the
people who install it.** That rejected the `PreToolUse` read guard, the
automatic rotation trigger, `SubagentStop` budget enforcement, and the
per-session read meter. The consequence is not softened anywhere: on Claude
Code nothing deterministic enforces any of the budgets above — they are prose
addressed to a model. OpenCode does enforce the report budget, in
`post_task_gate.py`, which rejects an over-budget report, a pasted diff, a
stack trace, or a missing `Unverified:` line. The one existing hook, the
router, keeps its licence because nothing happens until someone runs
`/router on`.

**The link checker no longer reads code as links.** `MD_LINK` is `[...](...)`,
which ordinary source matches — `Array.fill[Byte](packetSize)` was reported as
a link to `packetSize`. Fenced blocks and inline backtick spans are blanked
before the scan. Measured on starchat: 20 findings became 1 real one.

**The router is in live use across several concurrent sessions**, not just
installed. The `docs/sessions/` directories in `hb`, `mrcall-cs` and `starchat`
all hold real session-memory files, two of them already `closed` by `/doc-end`. A
routed session on 2026-08-25 answered trivial turns directly and delegated
substantial ones to pinned-model workers whose returned edits landed in this
repository, in `cs-kernel` and in `starchat`.

Mechanically verified: 53 `doc-check.py` pytest cases plus
`test_router_install.sh`, `test_codex_install.sh` and
`test_orchestration_install.sh` all pass, and the gate is clean on this repo.

## Unresolved

- **A routed session can run all day and never create its session-memory file.**
  One did on 2026-08-25: the injected directive names `docs/sessions/<id>.md`
  every turn and says to create it if missing, and nothing did, while other
  sessions the same day wrote theirs normally. The mechanism works — the gap is
  that the instruction is ignorable, not that the code is broken.
- Rotation has no invocation. The hand-off contract says what a rotation
  contains; an operator gets one by asking in words. A `/router rotate` verb
  was floated and dropped as never having been part of the proposal.
- Whether `/router on`'s "restart the session" guidance is necessary: one
  session activated the router and the hook fired on the very next prompt with
  no restart. A single data point, not confirmed either way.
- Whether a session can be relied on to know its own active model: `/model
  haiku` reported success and `~/.claude/settings.json` persisted it, but the
  visible indicator kept showing Sonnet 5 and the session had no way to
  self-verify which model was executing.

## Next

- Make the session-memory file harder to skip, since a routed session ran a
  whole day without writing one while other sessions wrote theirs.
- Exercise `doc-create`'s v1→v3 migration path against a real v1 repository
  (not just `doc-critic`'s repair in isolation, which is already verified) to
  confirm the migration note produces the same archive-and-trim result when
  entered through the version-mismatch flow rather than invoked directly.
- On the next protocol change, bump the embedded command/checker version and
  add its explicit repository migration before releasing it.
