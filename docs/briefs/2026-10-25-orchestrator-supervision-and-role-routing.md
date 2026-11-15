# Development brief: supervised orchestration and specialist delegation

Date: 2026-10-25 Status: proposal for review; no implementation authorized by this artifact. Classification: substantial development if adopted; this deliverable is brief-only.

## Intent

Let the operator entrust a bounded engineering task to the lead without repeatedly requesting five-minute checks or correcting arbitrary worker selection. The solution must supervise the lead and its workers independently of the lead's memory. It must distinguish a quiet but productive task from inactivity, and distinguish both from active work that has departed from the authorized objective.

Success means evidence-based, bounded intervention that improves delivery while preserving operator control, existing lifecycle gates, role ownership and model budgets. A skill alone can express policy but cannot establish independent execution or enforcement.

## Current state established from this checkout

- The existing orchestration command selects the OpenCode `orchestrator` primary.
  Its skill already specifies bounded delegation, normally at most three workers,
  appropriate specialist roles, proportionate verification and reviewed delivery.
  Sources: `opencode/commands/orchestrator.md:3`,
  `opencode/skills/orchestrator/SKILL.md`, and its `ARCHITECTURE.md`.
- The shared lead role prescribes `execute`, `verify` and `reviewer` selection.
  It does not prescribe a five-minute independent supervisor or persist task state.
  Source: `shared/roles/orchestrate.md:15` and `:30`.
- The role manifest and shipped/installed Codex TOML inventory contain `execute`,
  `plan`, `reviewer`, and `verify`. No kit `architect` profile exists in that inventory.
  Sources: `shared/roles/agents.json:35`, `codex/agents/`, `~/.codex/agents/`.
- Codex profiles have no model pin. Shared role documentation assigns their model
  to session inheritance; Claude/OpenCode choices follow the operator's budget.
  Sources: parsed TOML inventory and `shared/roles/README.md:95`.
- Generated profiles come from role sources and stubs through the existing builder.
  Editing a shipped TOML directly would violate that source-of-truth contract.
  Source: `shared/roles/README.md:3` and `shared/roles/agents/`.
- The OpenCode watchdog discovers children through `parentID` and SQL requiring
  `parent_id IS NOT NULL`. It does not register an ordinary root lead.
  Its violations are total elapsed time or accumulated cost, not lack of progress.
  Source: `opencode/skills/orchestrator/scripts/watchdog.py:200`, `:315`, `:100`.
- Its task configuration loader reads and logs timeout/budget values without
  applying them to registered workers. Its in-memory registry has no durable
  task objective, phase, authorization or progress assessment.
  Source: `opencode/skills/orchestrator/scripts/watchdog.py:607` and `:55`.
- A failed abort is still logged and permanently added to the killed-session set.
  That suppresses another attempt without establishing that the session stopped.
  Source: `opencode/skills/orchestrator/scripts/watchdog.py:512` and `:482`.
- Its client associates a task with the newest child created after registration.
  That is a timing heuristic, not an exact task/session binding.
  Source: `opencode/skills/orchestrator/scripts/watchdog_client.py:219`.
- The installer copies the OpenCode skill directory and installs role agents.
  Scoped searches found no daemon/client/gate invocation outside their scripts
  in the inspected OpenCode/shared/Codex surfaces or installer.
  Copying these scripts does not demonstrate a running watchdog.
  Sources: `install.sh:503` and scoped reference search.
- The post-task gate checks report structure and optional files/commands.
  It does not establish ongoing semantic progress or correct role dispatch.
  Source: `opencode/skills/orchestrator/scripts/post_task_gate.py`.
- Automatic av is retired; manual av remains available. Existing completion and
  reread rules are model instructions, with documented native enforcement limits.
  Sources: `docs/runtime-completion.md:3`, `docs/reread-guard.md:16`.

These are source observations, not proof of native runtime behavior. The operator's reported recurring drift supplies the problem statement; this brief does not claim to measure its frequency or attribute every case to one cause.

## Options and recommended direction

1. Strengthen the existing skill only. This is the smallest change and improves
   handoffs and role guidance, but repeats the dependency on model obedience.
   It cannot meet the independent-timer requirement and is insufficient alone.
2. Extend the existing OpenCode watchdog into a common supervisor. Its session
   observation and abort concepts are useful, but its OpenCode coupling, child-only
   discovery, weak binding and incomplete configuration handling require changes.
   Reusing the file unchanged would preserve the central failure modes.
3. Combine a shared orchestration policy with runtime-specific supervision.
   Reuse role generation and lifecycle contracts, and evaluate existing watchdog
   components against the common contract before extending or replacing them.
   This adds integration work but fits the Codex-first need without pretending
   OpenCode's APIs or an instruction skill are portable enforcement.
4. Adopt an upstream orchestrator. This might supply durable state or dispatch
   machinery, but introduces dependencies, security/maintenance obligations and
   possible conflicts with model policy. It remains a candidate, not a decision.

Recommend option 3. Reuse the existing policy, specialist profiles and generator.
Do not reuse the OpenCode daemon as the Codex supervisor: its runtime coupling
and child-only discovery do not cover the lead. Build the required Codex adapter
against a common supervision contract; this does not choose a new orchestration engine.
Keep the existing OpenCode daemon outside the initial Codex control path.
If later reused for OpenCode, repair exact task binding, effective configurations
and abort acknowledgement before claiming support. Those repairs are conditional
integration requirements, not unrelated cleanup in the initial Codex delivery.

The supplied external project leads are preliminary comparison candidates only:
[external watchdog loop](https://github.com/hyw007726/multi-agent-orchestrator-skill),
[phase-based dispatcher](https://github.com/ramil-zakirov-dev/superpowers-multiagents/blob/main/scripts/orchestrator.py),
and [architect skill](https://github.com/DanMcInerney/architect-loop/blob/main/skills/architect/SKILL.md).
Their source was not independently reviewed for this brief; no feature, license,
compatibility or dependency suitability conclusion is established here.

## Required behavior

### Independent supervision

- Establish a supervisor outside the lead's reasoning loop, bound to the actual
  native lead session and every authorized worker. The lead cannot be its only timer.
- Default to a five-minute assessment cadence for active work. Distinguish cadence
  from per-task deadlines; five minutes of useful work is not a failure condition.
- Record timer ownership and health. If supervision is unavailable, say so once
  and do not label the session supervised. Supervisor failure must be detectable.
- Observe only explicitly bound sessions. Never infer ownership from recency,
  terminate unrelated sessions, or treat an absent observation as completion.

### Progress and intervention

- Keep liveness observations separate from useful-progress assessments.
  Heartbeats, log growth, token usage and tool activity establish activity only.
- Assess progress against the current objective, scope, acceptance conditions,
  last useful result, next authorized action, and elapsed/resource allowance.
- Recognize valid waits, approvals, long-running tools and unchanged-source
  investigation. Do not require arbitrary file changes to demonstrate usefulness.
- Flag repeated failures without new evidence, expanding scope, irrelevant work,
  unsupported completion, and unowned blocked work, including when the lead does them.
- Use deterministic evidence where available and bounded semantic assessment for
  relevance. Record uncertainty; do not turn a semantic judgment into a guarantee.
- Support a proportionate intervention sequence: inspect, redirect, interrupt,
  and at most the configured recovery allowance. Preserve work before restart.
  A lead failure needs an independent recovery or explicit bounded handoff path.
- Verify an interrupt/abort outcome. Failed control requests remain failed actions,
  never successful-stop records or permission for unlimited retry.

### Specialist delegation

- Define an explicit phase-to-role policy using established roles: `plan` for
  read-only planning from an approved brief, `execute` for decided work,
  `verify` for consequential truth checks, `reviewer` for lifecycle gates.
  Preserve direct work where repository rules permit it.
- Use actual installed profiles, not a generic agent prompted to impersonate one.
  Missing profiles produce a diagnostic; inventing an `architect` is not a fallback.
- Retain fresh-review requirements, leaf-role boundaries and scoped handoffs.
  The lead owns synthesis and cannot treat dispatch as completion evidence.
- Document separately the policy expressed in prompts and any dispatch denial
  actually enforced by an adapter. Test native `spawn_agent` and alternate CLI
  paths: a wrapper-only role check is bypassable when those paths remain available.
- Either mediate all delegation within the claimed managed mode or label remaining
  bypasses explicitly. Detection after dispatch is not prevention of dispatch.

### State, authority and resources

- Persist objective, task/session identities, phase, scope, role assignments,
  owned surfaces, pending obligations, evidence references, timer deadlines,
  assessments, interventions and remaining limits in recoverable versioned state.
- Reconnect after compaction or supervisor restart without resetting budgets,
  duplicating workers, losing cancellation or replaying completed side effects.
- Require explicit bounded wall-time, concurrency, semantic-check and recovery
  allowances. Include supervision's own resource consumption in the task allowance.
  Preserve the operator's model/budget policy; Codex inherits the session model.
- Preserve pause, cancel and pending approval as distinct states. A timer never
  grants authority, resumes paused work, bypasses approval or buys more attempts.
- Keep routine healthy checks quiet. Surface meaningful drift, failed recovery,
  exhausted limits or decisions requiring the operator; offer an inspectable status.

## Skill creation and integration

Create the skill as the policy and operating entry point for this contract.
Start from the existing OpenCode orchestration skill rather than parallel prose.
Separate reusable policy from adapter procedures, installation and capability claims.
Provide a Codex-discoverable entry that starts or attaches to independently owned
supervision, binds real session identities, and reports the available control mode.
A skill that merely tells the lead to wake itself every five minutes is insufficient.

Keep phase/role definitions in one maintained source and compose runtime entries
through established generation conventions where applicable. Change role sources
and the builder path when role instructions change; regenerate shipped profiles.
Do not add a specialist merely to match an upstream vocabulary.

Kit maintainers own shared policy, state and generation; each runtime adapter owns
its native observation, dispatch/control and version-specific acceptance evidence.
Codex is the initial supported target. Claude/OpenCode should reuse the policy
without a compatibility claim until their actual client paths are exercised.
Installation and removal must preserve foreign registrations, existing work and
manual av. Disablement stops supervision cleanly and leaves a recoverable handoff.
Do not reactivate automatic av, per-answer hooks or completion certificates.

## Acceptance scenarios for the eventual implementation

- In a real managed Codex task, the lead forgets supervision instructions; an
  independent five-minute assessment still covers the lead and registered workers.
- A worker becomes inactive, while another emits frequent irrelevant activity.
  Both receive the appropriate assessment; heartbeat activity cannot clear drift.
- Useful research and a declared long-running command survive a routine check
  without forced edits, premature killing or repeated operator notifications.
- The lead researches outside scope or repeats a failed attempt without new
  evidence; independent intervention preserves the authorized objective and WIP.
- Each lifecycle phase selects its installed specialist. A generic/native spawn
  or alternate CLI bypass is denied in enforced mode, or exposed as unsupported
  in the capability report; the test cannot pass by exercising only the wrapper.
- Pause, cancel and approval waits survive timer ticks and restart without new
  work, extra spending, duplicate delegation or unauthorized side effects.
- A supervisor crash/reconnect and simulated compaction preserve exact task
  bindings, pending work and consumed retry/budget allowances.
- An abort failure remains visibly unresolved; bounded recovery ends at its limit.
  Concurrent unrelated sessions are never selected or interrupted.
- Install, repeated install, disable and removal preserve manual av and foreign
  assets; generated role checks detect source/rendering divergence.
- Long-session real-user trials include both genuine drift and productive controls.
  Report detection delay, missed drift, false intervention and supervisory cost.
  Passing plumbing tests alone cannot establish reduced operator intervention.

## Scope, assumptions and unresolved decisions

In scope: Codex-first supervised orchestration, role selection, recoverable state,
resource bounds, quiet operation, installation ownership and measured capabilities.
Out of scope: a new model router, hardcoded upstream models, unlimited autonomous
retries, replacing lifecycle reviews, broad repository cleanup or a release.

Adapter feasibility is open: native identity, observation, independent scheduling,
interruption and dispatch interception must be established in the intended Codex
interactive environment. CLI evidence cannot silently stand in for that environment.
Runtime coverage may require an explicitly managed launch path; an unsupervised
pre-existing session cannot acquire enforcement merely by reading a skill.

Exact recovery limits and acceptable false-intervention/cost targets remain
operator-configurable product choices. No paid acceptance budget is implied here.
The final design must state its trust boundary and residual native/CLI bypasses.
This brief establishes development intent and source-grounded gaps; it does not
establish native support, semantic-drift detection accuracy or behavioral improvement.
