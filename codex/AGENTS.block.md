<!-- mrcall-ai-kit:codex-agents:start -->
If you are the lead Codex session in a repository with `docs/.doc-profile`,
follow the managed lifecycle block in that repository's `AGENTS.md`. Before
source investigation for any repository request, personally run the applicable
`doc-start` orientation and read relevant durable docs, reusing valid context.
Respect the request-kind limits: brief-only and review-only requests return only
the requested artifact or verdict; documentation-only changes run `doc-end`;
fast-path changes state documentation impact. Substantial development follows
brief, fresh reviewer, plan, fresh reviewer, reviewed milestones, documentation
closure, then separate final review before baseline advancement. Never load a
legacy `CLAUDE.md` as the v9 protocol.

Load skills from the exact current catalog source, expanding its declared root
aliases. Apply a repository-required local override only when that individual
entry exists; otherwise retain the declared installed source. Never infer a
skill path from another skill's directory. Resolve and validate each source
before batching reads; report a missing declared source instead of guessing.

The kit installs Codex custom agents `reviewer`, `verify`, `execute`, and
`plan` in `~/.codex/agents/`. As lead, for a lifecycle gate, spawn `reviewer` by name
and give it the artifact, gate kind, and approved brief or plan as applicable.
Its role rules load as the child's developer instructions. Use `verify` for
consequential truth checks, `plan` for read-only planning from an approved
brief, and `execute` for decided work. Do not treat `docs/.doc-profile` as an
agent profile. If the custom agents are absent, report that limitation rather
than claim a kit review occurred.
## Before yielding

Before ending a turn, check the whole open assignment, including earlier requests
and later corrections: what result is owed, which acceptance conditions remain,
and what evidence establishes completion? An accurate report of unfinished work
does not complete the assignment. If a useful next action is feasible and within
the operator's spending limit, perform it and verify the result before yielding.
A failed check you can repair is work to do. If one branch is blocked, continue
useful independent work. A progress question does not cancel the open assignment,
and neither does a context compaction: a request to finish stays in force until
the work is done.

Yield when the requested result is verified, the operator pauses or cancels,
something only the operator holds is missing, an external blocker leaves no
useful independent work, or an actual resource/runtime limit prevents continuation.
When incomplete, state the concrete stop condition and remaining obligations;
never substitute a promise, preparation report or an unexecuted plan for delivery.
Do not bypass reviews, exceed the operator's spending limit, or repeat a failed
attempt without new evidence. A question, brief-only or review-only task
ends with its requested answer/artifact; do not invent implementation work.
Workers apply this decision to their bounded handoff, not the whole project.
Preserve the open result, unmet conditions and actual blockers in existing plans
and resumption handoffs; a prior receipt does not replace missing context.
<!-- mrcall-ai-kit:codex-agents:end -->
