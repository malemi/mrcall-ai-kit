---
status: completed
---

# Debugger agent delivery

Brief: [debugger agent](../briefs/2026-10-30-debugger-agent.md).

## Approved framing

Brief review: `/root/debugger_brief_review`, APPROVED on 2026-10-30.
The diagnostic role follows real data to the first demonstrated divergence;
it does not implement fixes or replace lifecycle review.

## Ownership and sequence

1. Lead: startup and brief review, then plan review before implementation.
2. One bounded `execute` worker: canonical debugger role/stubs, generator,
   equivalent verify model policy/snapshot, installation/help/budget/routing
   wiring and focused integration regressions. Preserve unrelated changes.
   Deliver within 10 minutes with exact commands, results and remaining gaps.
3. Lead: milestone review before native acceptance. Correct review findings
   before dependent work; reuse the same reviewer for corrections.
4. Lead: one deterministic, isolated native Codex diagnostic acceptance using
   the actually installed debugger profile. Maximum two native conversations
   total, 180 seconds each, no external business calls or paid catalogue refresh.
   Use a misleading wrapper exception around a deterministic inner data failure;
   require actual reproduction and source-backed function trace with evidence
   limits. Inspect actual tool events and report; never grade by keywords alone.
5. Lead: reconcile affected durable docs and living context; invoke doc-end,
   mechanical and doc-critic including active-context shape; completion check;
   fresh final reviewer with real native evidence; finalize only after approval.

## Verification

- Baseline configured build: `python3 shared/scripts/doc-check.py --repo .`
  passed before source changes; pre-existing advisory documents remain unchanged.
- Focused checks: generated parity, role profiles, Codex roles installation,
  Claude router and OpenCode workers installation, help/budget and model resolver
  tests affected by inventory changes. Expand only for relevant failures.
- Verify copy/symlink install and uninstall ownership without touching real user
  configuration; native acceptance uses an isolated installation and retained
  logs under `/tmp/mrcall-ai-kit/debugger-agent/`.
- Claude/OpenCode profile/install checks do not prove native model adherence;
  document that boundary. A sample cannot prove every debugger follows policy.

## Documentation scope

Canonical role README, top-level README, installation/help descriptions, Codex
lead template, relevant lead routing, docs/documentation-harness.md delegation
contract, active-context snapshot and this brief/plan. Review unchanged
model-router and reread contracts for impact, without rewriting unrelated work.

## Rollback

Remove only debugger-owned manifest/stub/policy entries and regenerate. Restore
only task-owned edits; preserve pre-existing supervision work. Native scratch
install is disposable. No release or commit is authorized.

## Results and pending obligations

- Plan review: `/root/debugger_plan_review`, APPROVED.
- Implementation: `/root/debugger_implementation`; 37 resolver cases and ten
  focused shell suites pass. Generator parity covers 40 files. Copy/symlink
  install, help discovery, budget switch and uninstall pass for the new role.
- M1 review: `/root/debugger_milestone_review`, initially REVISE for invalid
  YAML descriptions, then APPROVED after canonical quoting and actual six-profile
  YAML parsing. The shipped regression uses only the standard library; no new
  test dependency is required. Routing guidance includes debugger handoffs.
- Native attempt 1: isolated Codex `--ephemeral` failed before child startup with
  `no rollout found for thread id`; no diagnostic success is claimed for it.
- Native attempt 2: persistent isolated session, 43.703 seconds, installed role
  discovered and spawned as `debugger`. Four child shell calls read exact input
  and source, reproduce the real CLI failure, execute the intermediate functions
  and test an explicitly labeled in-memory counterfactual. String quantity
  `"4"` causes repetition `"4444444"`; local validation is mislabeled as a remote
  timeout. Fixture hashes are unchanged; the report claims no applied fix.
- Evidence: `/tmp/mrcall-ai-kit/debugger-agent/`, including immutable approved
  versions under `reviews/`, free test logs, `native/` failed attempt and
  `native-persistent/` invocation, installed profile, events, final report,
  result and native rollouts. Authentication copies are removed after each run.
- Runtime boundary: profile/install checks cover Claude/OpenCode; no new native
  behavioral claim for those clients. Codex's one synthetic sample does not
  establish production reliability. Actual user configuration is unchanged;
  installation refresh and a fresh session are needed to deploy the new role.
- Documentation reconciliation and closure reviews are the remaining gates.
  After their actual approval, the checker may transition this plan to completed.
  Existing supervision changes are outside this task and are not certified here.
