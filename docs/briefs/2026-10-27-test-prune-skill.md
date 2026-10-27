# Reusable test-prune skill

## Intent

Provide a callable kit skill for pruning tests that add no distinct confidence,
retaining concrete failure coverage and repository memory of each decision.
The operator wants this workflow reusable without restating its rules.

## Scope

Ship one shared `test-prune` skill through doc-harness on Codex, Claude and
OpenCode. Reuse existing installation ownership and documentation lifecycle.
Add concise discovery and memory guidance to existing documentation. Preserve
all current WIP and previous pruning evidence. No release or paid native trial.

The skill works from user scope, actual functional risks and existing evidence.
It distinguishes redundant assertions from valuable regressions, preserves unique
checks when consolidating, and explicitly records deliberately lost coverage.
It does not prune solely by test type, line count or an arbitrary reduction goal.
A failing test is evidence to diagnose, not permission to delete it.

## Memory and acceptance

- With a compatible documentation harness, retain dated audits under
  `docs/test-audits/`, linked from the docs index when first used. Reuse existing
  scoped audits and applicable brief/plan records; no second lifecycle.
- Audit records identify decisions, concrete reasons, surviving coverage or lost
  checks, command/log references and remaining uncertainty. Relevant current
  testing guidance belongs in durable docs; active context stays a snapshot.
- Without a harness, use a named repository scratch audit without installing or
  migrating documentation implicitly. Read-only requests remain read-only.
- Preserve before bytes, work artifacts and failed logs; inspect actual output.
  Reuse valid evidence and run only meaningful affected checks. Deterministic
  validation does not establish an agent's judgment on real user tasks.
- Validate skill format and actual copy/symlink installation, discovery and
  removal using isolated homes, preserving foreign files. Add assertions to
  existing installation coverage where useful; no wording-matching test suite.
- Make the skill available locally through the kit installer. Keep unrelated
  installation assets and sessions unchanged; document native invocation as
  unverified until observed.
