---
status: completed
---

# Agent autonomy and proportional effort execution plan

Brief: [../briefs/2026-08-31-agent-autonomy.md](../briefs/2026-08-31-agent-autonomy.md)

## 1. Map behavior entry points

- [x] Inventory primary-agent, orchestrator, router, worker, command, and skill
  prompts across Claude Code, Codex, and OpenCode.
- [x] Identify which instructions are global, repository-scoped, task-scoped, or
  unavailable in each runtime.
- [x] Locate duplicated worker doctrine and existing timing, testing, delegation,
  and escalation rules that would conflict with proportional effort.

## 2. Define and route the contract

- [x] Write one concise engineering-lead contract for the user-facing agent.
- [x] Write the worker application of the same contract: bounded scope, fast useful
  progress, proportionate verification, and no unsolicited expansion.
- [x] Route each runtime to the smallest authoritative source it can load; document
  platform gaps instead of copying divergent prose without ownership.

## 3. Update profiles and enforcement

- [x] Update primary/orchestrator profiles and worker templates or profiles.
- [x] Change delegation prompts so trivial local work stays with the parent agent.
- [x] Add mechanical checks that prevent the contract or critical proportionality
  rules from silently disappearing from distributed mirrors.

## 4. Verify behavior

- [x] Run profile, installer, mirror, and documentation gates.
- [x] Exercise a tiny-change scenario and confirm it avoids worker delegation and
  broad test expansion while still performing a focused real check.
- [x] Exercise a substantial scenario or prompt inspection to confirm planning,
  delegation, and stronger verification remain available when justified.
- [x] Run semantic review, reconcile living docs, and complete this plan only after
  evidence supports the behavior claims.

## Verification

- `bash tests/test_agent_profiles.sh`: all nineteen workers carry the contract;
  primary profiles have no mandatory approval ceremony; the live router-hook
  directive keeps narrow work local; copy and symlink installs match.
- All repository shell suites, 86 shared-script tests, seven adapter tests,
  command mirrors, template equality, `git diff --check`, and the v7 mechanical
  documentation gate pass.
- Claude Code 2.0.24 performs and verifies a focused one-line change through
  the v7 template in a temporary repository without delegation or broad tests.
- OpenCode is not installed in the verification environment. Its install paths
  and prompt contracts pass mechanically; no real-client behavior is claimed.
