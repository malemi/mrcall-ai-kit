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
`plan`, plus `debugger` in `~/.codex/agents/`. As lead, for a lifecycle gate, spawn `reviewer` by name
and give it the artifact, gate kind, and approved brief or plan as applicable.
Its role rules load as the child's developer instructions. Use `verify` for
consequential truth checks, `plan` for read-only planning from an approved
brief, `debugger` for causal diagnosis from actual failing data, and `execute`
for decided work. Do not treat `docs/.doc-profile` as an
agent profile. If the custom agents are absent, report that limitation rather
than claim a kit review occurred.
{{MANDATE_COMPLETION}}
<!-- mrcall-ai-kit:codex-agents:end -->
