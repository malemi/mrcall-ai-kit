# Make migration prerequisites obtainable without scope escalation

## Intent

An explicitly requested v9 upgrade must have a documented, executable path to
its compatibility prerequisite. A downstream agent encountering a refusal must
stop the blocked operation, preserve the repository, and report the missing
prerequisite. It must not investigate or modify the AI-kit installation,
symlink targets, helper implementation, or compatibility policy to complete a
different repository's task. Explicit kit maintenance, as requested here, is
a separate authorized scope.

## Verified problem

The installed clients report OpenCode 1.18.34 and Codex 0.160.1. The migration
helper accepts only OpenCode 1.18.32/run-explicit-dir and Codex
0.160.0/native-app-server. It additionally requires a repository-bound schema-1
report with current instruction hashes and readable measured artifacts.
`doc-create` describes consuming this report but supplies no executable way to
obtain it. Missing artifacts and unsupported exact versions are independent
blockers. A version-number edit or a fabricated compatibility attestation
cannot repair either.

The baseline mechanical command passed before source changes. Relevant
contracts are `docs/harness-runtime-support.md`, the migration section of
`docs/documentation-harness.md`, and `shared/commands/doc-create.md`.

## Scope and constraints

- Make the failure boundary explicit in doc-create and shared role/lead
  instructions. A missing prerequisite/refusal is a stop, not permission for
  external source archaeology or repair. Recovery steps already documented
  and authorized inside the target repository remain allowed.
- Correct the compatibility acquisition path using actual current-client
  measurements. Reuse an existing reproducible probe when suitable; otherwise
  implement the smallest bounded probe/report path necessary. Reports remain
  bound to the target repository, instruction observations, exact runtime mode,
  configuration and measured scopes. Preserve complete raw results.
- New client-version support requires fresh evidence. Do not infer patch-version
  compatibility, disable guards, change model selection, or extend OpenCode's
  development/fastpath support without measuring those paths.
- Missing, failed or ambiguous measurements still refuse without target writes.
  Provide structured, actionable diagnostics so an agent can stop without
  reading the kit's source. Keep customized CLAUDE protection, ownership,
  mechanical staging, atomic publication and rollback intact.
- No real downstream migration, commits, pushes, release, global activation or
  client configuration changes are authorized by this task. Disposable native
  trials and local source/test/documentation edits are in scope. Refreshing
  affected kit-owned installed workflows/agents is in scope, preserving foreign
  files and existing configuration/activation; running sessions need restart.

## Evidence acquisition authority

The documented compatibility preflight is part of an explicitly requested
migration, not permission for arbitrary troubleshooting. A downstream agent may
invoke the installed bounded collector/report commands on disposable shadow
fixtures and retained external evidence. It may not open kit implementation or
change policy when that preflight refuses. Native trials never write the real
target. A fresh trial/report binds one target's observed instruction inventory
and exact client configuration; it is not portable to arbitrary repositories.
The shadow fixture must preserve the target's relevant ancestor/user instruction
environment, and mismatches refuse. Measurements establish only the exercised
startup/documentation paths; application behavior and universal compliance are
not implied. Semantic judgment remains explicit, not inferred from exit status.

## Acceptance

1. A downstream migration refusal exposes the missing prerequisite and the
   bounded next action through its CLI/workflow, not through source inspection.
   Stop/no-kit-modification instructions reach generated agents and both
   doc-create workflow copies.
2. A reproducible route creates valid compatibility evidence for at least one
   currently installed client using real startup and documentation-closure
   trials. The other client is measured or remains explicitly unsupported with
   the actual refusal reason. No result is represented as measured when it is
   only a fixture, a canary, or an inferred patch match.
3. Using the installed helper path, a disposable recognized v8 repository can
   dry-run, apply, pass the v9 mechanical checker, and roll back exactly with
   valid current evidence. No-evidence, stale/changed artifact, wrong repository,
   unsupported mode/scope/version, and failed-measurement cases leave target
   bytes and transaction state untouched.
4. Relevant tests pass; workflow copies and generated agents stay synchronized.
   Durable runtime docs distinguish new measurements from historical evidence
   and retain limits. Documentation closure precedes a fresh final review.

## Assumptions and exclusions

Native trials may encounter provider quotas, authentication failures or guard
denials. Those are measured failures, not permission to bypass prerequisites.
Probe implementation and exact enrollment mechanics are determined by the
reviewed plan after bounded investigation of existing measurement tooling.
The task does not promise universal runtime compatibility or interception of
an agent that ignores its instructions.
