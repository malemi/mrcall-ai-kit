---
status: completed
---
# Completion-driven supervision without a default check cap

Brief: ../briefs/2026-10-27-optional-supervision-cap.md
Prior brief/plan approval covered the earlier finite-cap change, but its instruction
to restore TEST-SUPERVISOR2 is superseded by the current operator correction.
Completion task: `optional-supervision-cap-20261027`.

## Ownership and dependencies

Lead owns runtime, tests, documentation, installation and evidence. Preserve all
existing WIP. Fresh reviewers own corrected brief, plan, milestone and final gates.
Review check-ins assess evidence; elapsed time alone is not failure evidence.
No invented reviewer or worker termination deadline. Reviews have a concrete gate
and artifact, with progress reassessment when needed.

## M1 — Implement and verify

After corrected brief and plan approval, inspect the existing cap implementation,
previous suite log and checkpoint/timeout handling. Fix root causes within scope.
Use actual CLI and deterministic transport fixtures to cover uncapped execution
beyond 100, explicit/legacy caps, invalid values, history/fences, one-shot behavior,
checkpoint expiry, idle-lead intervention contract and retained failures.
Update skill, policy, commands and durable docs. Record failures even if repaired.
Obtain a fresh milestone review before installation.

## M2 — Install and verify the user path

Install supervision through the normal installer, preserving unrelated installation
assets. Verify installed bytes and actual CLI in isolated state. Use deterministic
protocol fixtures wherever sufficient; do not launch paid acceptance merely to
repeat deterministic claims. Inspect native session creation capability read-only.
The operator will create TEST-SUPERVISOR3; deliver its startup prompt with exact
PROBLEMI2 intent and cadence only. The installed skill must supply progress,
cap/failure/timeout rules and preactivation disclosure of effective configuration;
the prompt must not restate the skill or disclose observation. Do not
create or activate a native session in this implementation task. The operator
authorizes this lead to observe TEST-SUPERVISOR3 once its exact identity exists;
the parent resolves identity externally from its new registered binding. The
startup prompt must not disclose that observation or request a callback. Never reuse or modify TEST-SUPERVISOR2.
If missing target authority or paid behavior testing is indispensable, retain the
specific remaining acceptance and ask only for that missing input.

## Closure and rollback

Reconcile affected docs and living context, preserve displaced historical text,
run doc-end mechanical and semantic checks, then a separate final review before
baseline advancement. No commit or release. Installation rollback restores owned
backups only. Do not reset execution history, alter old trial state, or claim model
behavior from passing Python tests or native message acceptance.

## Evidence and remaining work

Inherited evidence: `/tmp/optional-cap-evidence/`; inherited suite log
`tests.log` has not yet been accepted. Earlier review references remain historical.
Corrected brief and plan APPROVED by fresh reviewers `/root/corrected_brief` and
`/root/corrected_plan`; immutable versions and raw verdicts retained in the evidence
directory. Operator clarification: deliver a prompt for TEST-SUPERVISOR3 rather
than creating it now. This narrows M2 preparation, preserving the approved scope.
Inherited suite: 60 tests pass (42.535s); resumed suite: 60 pass (51.606s).
Corrected full suite: 62 pass (44.454s), including CLI reads/interventions after
checkpoint expiry through a Unix socket fixture and audit/failure retention.
The first expanded suite failed due to fixture execution/outbox inconsistency;
its cause and raw failure remain in `checkpoint-fixture-failure.txt` and
`corrected-suite.log`. No paid model acceptance or native session activation.
M1 APPROVED by `/root/cap_milestone`; immutable store/scheduler and raw verdict
retained in the evidence directory. Normal local copy installation completed with
owned backups (`local-install.log`). Installed bytes match sources and skill;
installed CLI smoke verifies 102 uncapped executions, finite caps, invalid inputs,
null update/resume, checkpoint late-result authority and retained failure memory.
All existing binding/task/execution/outbox records match their before snapshot;
TEST-SUPERVISOR2 remains untouched. Evidence: `installed-smoke.py` and
`installed-smoke.log`, no native model calls.

Final human-written-style prompt (delivered to the operator): `/tmp/optional-cap-evidence/TEST-SUPERVISOR3-prompt.txt`, SHA-256
`f355332a0bf8c10141449957819258a54299eebc5aa636ca6b4eada3d4bdebe2`.
PROBLEMI2 exact root `01a1698a-21b3-7c53-8424-ae71e372339a` metadata confirms
root/idle/direct input. New-session setup is intentionally left to the operator's
prompt launch; no session was created. This lead's future observation requires
TEST-SUPERVISOR3's exact native ID, resolved externally from its registered binding.
The operator explicitly requires uninformed observation: no reference to this
parent, observation or a callback appears in the final startup prompt. Parent
observation is strictly read-only: no messages or interventions to TEST3 or
PROBLEMI2, and no recursive expansion. The earlier callback section is superseded
and retained only as evidence outside the repository.
The operator rejected the technical startup payload in favor of a short natural
language mandate. The final prompt supplies only target, verified-completion intent, minute cadence
and session name. Preactivation mandate/configuration disclosure is now explicit
in the skill/policy; exact identity remains independently established by the skill.
General rules must work without the operator repeating them in the startup prompt.
The installed default configuration supports assessment cadence60s when requested,
with optional UTC alignment,
max_checks null, checkpoint180s, transport10s and one recovery; observer cadence120s
with the same defaults, configured separately from the target startup prompt.
Checkpoints never terminate useful reviewer/worker work.
Existing business spending/release restrictions remain binding. Actual native
supervisory judgment, minimal-prompt compliance and future observer activation are not certified by these
checks. Doc-end and separate final review remain due before finalization.
