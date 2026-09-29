---
status: completed
---

# Agent re-read rules

Brief: [Apply the sc checklist to every kit agent report](../briefs/2026-09-28-agent-reread-rules.md), reviewer `APPROVED` on 2026-09-28.

## M1 — Compose and prove the rule (lead owns)

Add one generated re-read block built from the shipped six-item checklist.
Include it in Claude Code's preloaded role skill, every OpenCode agent body
(including leads), and each Codex TOML `developer_instructions`. Preserve the
existing report schema and verdict location. Regenerate. Extend the generator
gate to assert the checklist is present for every agent. Verify the generated
files, full content, and deterministic regeneration. Review the integrated
milestone before installation.

Result: generator composed the shipped checklist into the Claude role skill,
all OpenCode agent bodies, and all four Codex TOML profiles. The fixed-report
opening rule is explicit. Generation and the strengthened agent gate pass;
the M1 reviewer returned `APPROVED`.

## M2 — Install and probe (lead owns)

Install the changed artifacts in a temporary home and the active local home.
Check that installed files match generated sources. Run a fresh Codex reviewer
probe with a report-format challenge; run focused real-client probes for
Claude Code and OpenCode if the clients are available. Distinguish static
instruction loading from observed compliance. Update the agent-layer and
active-context documentation, run the mechanical documentation gate, and
obtain the M2 integration reviewer verdict. After both milestone verdicts
pass, run a separate final end-to-end reviewer pass.

Result: a temporary-home install placed the checklist in all 11
instruction carriers. The active Claude and OpenCode installs use symlinked
generated sources, and the four copied Codex TOML profiles were reinstalled.
Codex 0.158.0 spawned the installed reviewer and produced a format-conforming
`REVISE` finding against an overclaim in this brief. The brief now says an
internal pass is unobservable; the brief re-review returned `APPROVED`. OpenCode 1.18.32
resolved the reviewer profile and delegated to it from `build` in a disposable
directory; the child returned a correct `No` verdict in the first required
field. Claude Code 2.1.280 returned HTTP 429 for the weekly usage limit before
the agent ran. Installed files and the generator, documentation and installer
help gates pass. The M2 reviewer returned `APPROVED`; it confirmed the
OpenCode child report, Codex verdict format, the installed carriers, and the
Claude 429 limit. A separate final review returned `APPROVED` with no blocking
finding. The internal re-read and Claude runtime behavior remain unverified.

## Risks and rollback

The answer-first checklist item can conflict with fixed report headers; the
generated instruction must tell agents to put the answer or verdict in the
first required report field. Generated profiles capture the shipped checklist
at build time. Rolling back this change means removing the generated block,
regenerating, and reinstalling the previous profiles. No persistent data or
external service is changed.
