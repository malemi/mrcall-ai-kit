---
status: completed
---

# Codex role agents

Brief: [Codex must run the kit's reviewer profile](../briefs/2026-09-28-codex-role-agents.md), independently reviewed `APPROVED` on 2026-09-28.

## M1 — Compose the four Codex profiles

Extend the shared agent generator to write TOML profiles for `reviewer`,
`verify`, `execute`, and `plan`. Compose their instructions from the existing
role files and common blocks. Make `--check` detect drift. Validate TOML
parsing, role content, read-only review, and deterministic regeneration.
Review the integrated generator and artifacts before M2.

Result: `build-agents.py --check` reported 32 files in sync; the generated
agent test passed. An independent M1 review found an unintended change to
OpenCode's plan agent and missing stray-TOML detection. Both were fixed and
the re-review returned `APPROVED`.

## M2 — Install and discover

Install profiles under `~/.codex/agents/` with `doc-harness`. Install a
delimited global `AGENTS.md` block that tells a Codex lead to use the roles
and delivery gates in repositories with a harness profile. Preserve foreign
content, existing operator agents, copy/symlink semantics, and manifest-based
removal. Make `ai-help` enumerate installed profiles, and `ai-budget` state
that Codex roles inherit the session model. Verify temporary-HOME installs,
uninstalls, and coexistence with foreign files; review before M3.

Result: the focused install test passed in copy and symlink modes. An
independent M2 review found that `skip` could leave a foreign reviewer while
the global block claimed a kit reviewer, and repeated `backup` could replace
the foreign original. The installer now refuses a differing role under
`skip` before writing and retains the first backup on repeat installs. The
re-review returned `APPROVED`.

## M3 — Real Codex proof and docs

Install on this machine without touching foreign content. Run a fresh Codex
session to prove global instruction injection and a spawned named reviewer
whose response follows a distinctive profile-only rule and the review format.
Use a harmless review fixture. Update documentation to the measured behavior
and limitations. Run a separate final review of the diff, install path, and
real-client evidence. Keep this plan active if either runtime proof fails.

Result on Codex CLI 0.158.0: the first named-reviewer spawn failed with
`agent type is currently not available` while its profile was symlinked.
The installer now copies Codex TOML profiles in either mode. A fresh CLI
session with no file reads named the four agents and the gate order from the
injected global block. Another fresh session requested a named `reviewer`
spawn for a deliberately misframed brief. The reviewer returned `## Done`,
`- Verdict: REVISE`, a frame-mismatch finding, and `Verified`/`Unverified`
fields from its installed profile. The actual `ai-help` and `ai-budget`
commands listed the roles and the inherited-model limitation. Focused
generator, Codex install, budget, tutorial, help, and mechanical doc gates
passed. The separate installed-Codex final reviewer returned `REVISE` for two
integration defects: `resolve-models.py` rejected the new inherited-model
Codex manifest entries, and a repeat `--on-exist skip` install could accept
a byte-identical symlinked profile that Codex cannot load. The resolver now
excludes Codex entries from model selection, while still validating the
pinned runtimes; the installer refuses any symlinked Codex profile under
`skip` before writing. The resolver CLI fixture check and copy/symlink
install checks pass.
The next final reviewer verified both fixes and returned `REVISE` for a
repeat-`backup` case that discarded edits to an installed physical role
profile. The installer now compares the installed item with its source and
moves a changed item to a free numbered backup, preserving the first backup.
The temporary-HOME install test reproduces the edit, repeat install, and
uninstall restoration sequence. The installed Codex `reviewer` returned
`APPROVED` on the final re-review after independently confirming that repeat
installs preserve successive edits and older backups, and that uninstall
restores the latest edit. No blocker remains for this brief.

## Risks and rollback

Codex custom-agent discovery may differ from documentation on the installed
0.158.0 client. Probe it rather than infer from static files. A changed global
`AGENTS.md` block must not alter user-owned text. `uninstall.sh` removes the
kit block and manifest-owned profiles; the backup option restores any existing
profile it moved. No model pin is added, so the runtime's session model still
determines quality; `ai-budget` must report that limitation clearly.
