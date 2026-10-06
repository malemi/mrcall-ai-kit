---
doc_baseline_commit: edc784b4767883f1972e81db6b454d64b2d27f42
doc_baseline_date: 2026-10-06
---

# Active Context

<!-- doc-scope:start -->
Scope: Volatile snapshot of current verified state, unresolved work, and immediate next actions; never session history or durable design.
<!-- doc-scope:end -->

## State now

This repository runs harness v9: one managed protocol block in root AGENTS.md,
no repository CLAUDE.md, compact startup checks, deterministic migration
(`doc-migrate.py`), and task-bound completion evidence (`doc-check.py
--completion`). The checker can refuse stale or missing results when invoked.
It cannot force a client to invoke the lifecycle or authenticate an agent's
judgment.

The installed commands, skills, and checker on this machine are symlinks into
this checkout, so doc-start, doc-end, and the checker run v9 for every
repository here. The installation predates v9: `~/.config/mrcall-ai-kit` lacks
`doc-migrate.py`, `doc-evidence.py`, `AGENTS.block.md`, and `legacy/`, so the
installed `doc-create` cannot migrate until `./install.sh` runs again. Every
other repository on this machine carries an older profile (mostly v8; some v3,
v2, or none); its doc gates refuse until it is migrated, and only v6–v8 can
migrate through `doc-create`.

The prototype passed 20 ordinary/boundary Codex app-server trials. Its startup
median incremental input fell from 19,611 to 7,875 bytes; this is not a measure
of actual context occupancy. Measured client/configuration boundaries belong in
the runtime support table.

Codex custom roles inherit the session model; Claude and OpenCode roles follow
`/ai-budget`. Generated agents carry the shipped final-answer re-read checklist;
private reasoning is not observable. Installed-client verification and its
limits remain in the corresponding durable contracts.

Release requires task authorization in addition to the profile command.
The v9 adoption is committed and pushed (edc784b); release v9.0.0 is
authorized in-task on 2026-10-06 and is being cut through doc-end Phase 5
in this run.

## Unresolved

- Claude Code 2.1.280 with default settings does not load this repository's
  AGENTS.md: the ancestor `/home/mal/hb/CLAUDE.md` takes precedence (probe in
  this checkout, 2026-10-05). Claude sessions here load that ancestor's v8
  protocol and the meta-repository AGENTS.md instead of this repository's v9
  block and project rules, until the ancestor file is removed or the
  `agents-md` combined-instruction option is set.
- The critic's documentation read boundary in the shipped build has no native
  trial evidence; native evidence covers the M2 prototype and the pre-repair
  integrated-v2 build. The operator waived a further native matrix.
- Migrating `/home/mal/hb` is refused as it stands: its AGENTS.md has 185 lines
  and the 61-line managed block plus its blank separator take it to 247, over
  its `index_max_lines` of 200.
- Whole-lifecycle bypass remains possible. The deliberate native bypass still
  completed without evidence creation or an independent runtime denial.
- The tested Claude 2.1.280 print configuration fails startup/documentation
  migration requirements: router-created files exceed limited task scope, and
  documentation edits encounter the scope guard. Instruction loading also
  depends on coexistence settings; do not infer support from the version alone.
- OpenCode's measured explicit-directory paths do not establish substantial
  development, interactive behavior, or its `orchestrator` role.
- Scope-guard capabilities beyond the documented real-client paths remain
  unverified; incidental guard observations do not establish full support.
- A routed session can skip its instructed session-memory file. A model can
  also misuse an installed model-invocable `nr`; both boundaries still rely on
  instructions rather than deterministic interception.
- Claude `execute` at low/medium remains below its recorded coding floor in
  the existing model selection. Role quality on real tasks, other machines'
  installations, and other OpenCode providers are not established.

## Next

- Rerun `./install.sh` so the installed `doc-create` finds the v9 migration
  assets.
- Migrate downstream repositories one at a time with `doc-create`, starting
  with the `/home/mal/hb` meta-repository (after trimming its AGENTS.md to at
  most 138 lines) so its CLAUDE.md stops shadowing sub-repository AGENTS.md files.
- Complete the remaining scope-guard plan with installed-client evidence.
- Refresh resolved models when their evidence changes, using the documented
  resolver and generation workflow.
