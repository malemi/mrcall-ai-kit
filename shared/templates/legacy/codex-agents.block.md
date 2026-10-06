<!-- mrcall-ai-kit:codex-agents:start -->
If you are the lead Codex session in a repository with `docs/.doc-profile`,
load that repository's `CLAUDE.md` before substantial work and follow its reviewed delivery flow. The short order
is brief, fresh `reviewer` verdict, plan, fresh `reviewer` verdict, reviewed
milestones, then a separate final review. Use the direct fast path only when
the conditions in `CLAUDE.md` all hold.

The kit installs Codex custom agents `reviewer`, `verify`, `execute`, and
`plan` in `~/.codex/agents/`. As lead, for a lifecycle gate, spawn `reviewer` by name
and give it the artifact, gate kind, and approved brief or plan as applicable.
Its role rules load as the child's developer instructions. Use `verify` for
consequential truth checks, `plan` for read-only planning from an approved
brief, and `execute` for decided work. Do not treat `docs/.doc-profile` as an
agent profile. If the custom agents are absent, report that limitation rather
than claim a kit review occurred.
<!-- mrcall-ai-kit:codex-agents:end -->
