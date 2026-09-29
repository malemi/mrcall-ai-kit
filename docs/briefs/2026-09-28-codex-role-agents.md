# Codex must run the kit's reviewer profile

Date: 2026-09-28

## Intent

When a Codex lead delegates a lifecycle review, the child must receive the
same role, common rules, delivery contract, and report format that the kit
already gives Claude Code and OpenCode reviewers. The kit must install usable
Codex roles, and its installed Codex instructions must tell a lead to use them
for substantial work. A repository's `docs/.doc-profile` configures the
documentation harness; it is not an agent profile.

## Evidence and cause

`shared/roles/README.md` says Codex receives nothing from the agent layer.
`install.sh` puts only skills under `~/.agents/skills/` for Codex. The Codex
`doc-start` workflow reads `CLAUDE.md`, but this gives the lead file content,
not a custom reviewer definition for a child. An observed Codex review was
launched with a task prompt and no kit role profile. Current official Codex
documentation says standalone custom agents under `~/.codex/agents/*.toml`
carry `developer_instructions` into spawned sessions. Codex 0.158.0 is installed
on this machine.

## Scope

- Generate Codex `reviewer`, `verify`, `execute`, and `plan` custom-agent TOML
  definitions from the existing single-owned role text and shared rules.
- Install them with the Codex documentation harness in copy and symlink modes;
  include them in the install manifest and uninstall path, preserving foreign
  files under `--on-exist`.
- Install a delimited kit block in the global Codex `AGENTS.md` so fresh leads
  know when to use the roles and the reviewed delivery gates. Preserve all
  foreign content, and remove only the kit block on uninstall. If global
  injection does not work in a real client, find a working carrier before
  claiming this criterion.
- Show the actual Codex roles in `ai-help`. State in `ai-budget` that Codex
  roles inherit the session model until budget resolution for Codex is
  supported; never imply the existing Claude/OpenCode budget switches them.
- Update the relevant docs and focused installer/generated-artifact checks.

Out of scope: Codex model score/price resolution, hook enforcement, and
attestation gates from the broader draft
`2026-09-27-enforceable-delivery-gates.md`. They are separate work. This change
must not present them as complete.

## Constraints

- One source for each role and shared rule; no hand-maintained duplicate body.
- No pinned Codex model or cheaper-role choice. A Codex role inherits the
  session's model, and the reporting says so.
- Preserve `~/.codex/AGENTS.md` and any existing custom-agent file that the
  operator owns. Installation never silently overwrites foreign content.
- Every generated artifact is in English. Run the real Codex client, not just
  static tests, before claiming the profile loads.

## Acceptance criteria

1. After installation, a fresh Codex session names the four installed kit
   custom agents without opening their files, and knows that substantial
   brief, plan, milestone, and final reviews use `reviewer`.
2. In a fresh real Codex session, spawning `reviewer` gives the child the
   generated `developer_instructions`. A targeted probe demonstrates a
   distinctive rule present only in that profile, and the child follows the
   gate-specific verdict/report format. Record the transcript or output.
3. Generated Codex agent definitions contain the role, common rules, selected
   shared blocks, and report format from `shared/roles/`; `--check` detects
   drift. The Codex reviewer is read-only.
4. Copy and symlink installs, repeat installs, `--on-exist` handling, and
   uninstall preserve foreign content and leave no kit block or agent residue.
5. `ai-help` lists installed Codex agents; `ai-budget` explicitly reports the
   Codex model limitation. Documentation states the measured real-client
   coverage and what remains unverified.

## Material assumptions

- Codex 0.158.0 discovers `~/.codex/agents/*.toml` at session start and uses
  `developer_instructions` for a named spawned agent. Official documentation
  describes this; the real-client probe must establish it here.
- Codex loads `~/.codex/AGENTS.md` into fresh sessions. Official docs describe
  this; the real-client probe must establish it here.
