<!-- mrcall-ai-kit:codex-agents:start -->
If you are the lead Codex session in a repository with `docs/.doc-profile`,
follow the managed lifecycle block in that repository's `AGENTS.md`. Before
source investigation for any repository request, personally run the applicable
`doc-start` orientation and read relevant durable docs, reusing valid context.
Respect the request-kind limits: brief-only and review-only requests return only
the requested artifact or verdict; documentation-only changes run `doc-end`;
fast-path changes state documentation impact. Substantial development follows
brief, fresh reviewer, plan, fresh reviewer, reviewed milestones, documentation
closure, then separate final review before baseline advancement. Release needs
separate task authorization. Never load a legacy `CLAUDE.md` as the v9 protocol.

The kit installs Codex custom agents `reviewer`, `verify`, `execute`, and
`plan` in `~/.codex/agents/`. As lead, for a lifecycle gate, spawn `reviewer` by name
and give it the artifact, gate kind, and approved brief or plan as applicable.
Its role rules load as the child's developer instructions. Use `verify` for
consequential truth checks, `plan` for read-only planning from an approved
brief, and `execute` for decided work. Do not treat `docs/.doc-profile` as an
agent profile. If the custom agents are absent, report that limitation rather
than claim a kit review occurred.
<!-- mrcall-ai-kit:codex-agents:end -->
