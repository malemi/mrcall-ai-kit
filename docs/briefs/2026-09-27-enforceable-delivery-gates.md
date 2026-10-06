---
status: draft
---

# Enforceable delivery gates on every runtime (Claude Code, Codex, OpenCode)

## Why — the measured incident

On 2026-09-27 a Codex session (KERNEL-CREDITS, cs-kernel, rollout `01a0e3ba`)
received a substantial cross-repo task and shipped code in two repositories
with zero reviews: brief and plan written in one patch at 16:50:00, first code
patch 51 seconds later, a production clone used for live RPC and a real
OpenRouter call, and a second repo's code patched before that repo's brief
existed. The audit (session memory
`docs/sessions/ses_f1bf8cc3effeknujoKf7KYkTeD.md`) proved four independent
structural causes:

1. **No instruction carrier.** On Codex the delivery-flow contract reaches a
   session only as `cat CLAUDE.md` tool output during doc-start — data, not
   instructions. Codex injects only the project `AGENTS.md` (cs-kernel's
   carries no gates), and no global `~/.codex/AGENTS.md` exists.
2. **No roster.** The kit ships no Codex role agents
   (`shared/roles/README.md`: "Codex receives nothing from here"). The
   contract's central mechanism — "have a fresh reviewer judge" — has no
   executor on that runtime. `/ai-budget` resolves models for Claude Code and
   OpenCode agent directories only.
3. **Spawn suppressed by default.** Codex 0.156 provides `spawn_agent` but
   injects a developer message forbidding sub-agent spawns "unless the user or
   applicable AGENTS.md/skill instructions explicitly ask". Nothing kit-side
   asks, so even the generic escape hatch stays closed.
4. **No mechanical brake, plus a dead one.** The machine runs
   `approval_policy = "never"` + `sandbox_mode = "danger-full-access"`. The
   kit's own Codex scope-guard registration
   (`shared/scripts/scope_guard_register.py` L50) installs a `PreToolUse`
   matcher `Edit|Write` — tool names Codex does not have; its edits are
   `apply_patch` inside `exec`. The shipped guard could never fire. A
   mechanism that cannot run, but is registered and reported as active, is
   worse than none: it manufactures false assurance.

The same compliance-only weakness exists on Claude Code and OpenCode in milder
form: the roster and instruction carriers are real there, but nothing checks
that a gate actually ran, OpenCode's orchestration has no real-client proof
(recorded in `docs/active-context.md`), and Claude Code's roster lacks the
planning role. This brief covers all three runtimes because the invariant is
one: **wherever kit-backed work starts, the lead is bound by the contract as
an instruction, knows the role roster with budget-resolved models, and the
gates leave checkable evidence — or the runtime's degradation is declared,
never silent.**

## Intent

Give the reviewed delivery flow, per runtime: an instruction carrier (C1), a
role roster with `/ai-budget` model resolution (C2), and enforcement that is
either demonstrated in a real client or honestly declared impossible (C3).
Role names map to the operator's vocabulary: architect ↔ `plan`, reviewer ↔
`reviewer`, coder ↔ `execute`, plus `verify` and the OpenCode leads.

### C1 — the contract arrives as an instruction

- **Claude Code**: already true (managed `CLAUDE.md` auto-loads). Regression-
  protect only.
- **OpenCode**: already true for lead agents (contract composed into
  `build`/`orchestrator`). Regression-protect only.
- **Codex (new)**: two managed, delimited blocks:
  - a global block in `~/.codex/AGENTS.md` (installed/uninstalled by
    `install.sh` like every other kit artifact) carrying the delivery-flow
    contract and the roster pointer, so even a general session with no
    doc-start is bound;
  - a per-repo block that `doc-create` adds to the project `AGENTS.md` (the
    existing `doc-scope` block is the precedent for a kit-managed delimited
    region inside a project-owned file), carrying the same contract plus the
    explicit sub-agent ask that lifts Codex's spawn suppression legitimately.

### C2 — the roster exists and the lead knows it, with budget-resolved models

- **Claude Code**: roster today is `execute`/`verify`/`reviewer` × 3 budgets.
  The `plan` (architect) role exists as role text but is not composed for
  Claude Code. Decide in the plan: render it, or declare the absence with a
  reason wherever the roster is listed. No silent gaps.
- **OpenCode**: roster complete (`build`/`orchestrator`/`plan`/`execute`/
  `verify`/`reviewer` × 3 budgets). Regression-protect.
- **Codex (new)**: the kit cannot register agent definitions Codex does not
  have, but Codex sub-agents take a task prompt. Ship the role texts as
  spawnable profiles: the C1 carrier names the roster and instructs the lead
  to spawn `reviewer`/`execute`/`verify`/`plan` sub-agents with the
  corresponding role file as their task charter. Model resolution per
  sub-agent is a probe (below): if Codex allows a model per spawn, wire
  `models.json` through it; if not, Codex roles run on the session's single
  configured model and `/ai-budget`, `ai-help`, and the docs must say so.
- **`/ai-budget` (all runtimes)**: the command's report covers every runtime
  that has a roster; a runtime whose models it cannot set gets an explicit
  degraded line. Silence is a failure.

### C3 — gates leave checkable evidence; brakes that exist must work

Mechanical "no edit before review" cannot encode the fast-path judgment
without blocking legitimate fast-path work, so the default enforcement is
attestation, not blocking:

- **Gate attestation (all runtimes)**: the lead records each gate outcome
  (verdict, reviewer, artifact path) in the session/work-trace file.
  `doc-start` surfaces substantial open work whose trace lacks verdicts;
  `doc-critic`/`doc-end` fail or flag it; OpenCode's existing
  `post_task_gate`/watchdog path is wired to check it and is proven in a real
  client (closing the recorded no-real-client-proof gap).
- **Fix or remove the Codex brake**: probe what `PreToolUse` actually receives
  on Codex 0.156/0.157 for `exec`-borne `apply_patch`. If the hook can see and
  deny it, correct the matcher/adapter and prove one real denial + retry (the
  Claude Code non-interactive proof is the template). If it cannot, remove the
  Codex guard from the installer, `hooks.json` registration, the scope-guard
  skill, and every doc that claims it. No middle state survives.
- **Optional strict mode (opt-in, scope-guard-style)**: where a runtime
  demonstrably can deny writes (Claude Code `PreToolUse` proven; OpenCode
  permission plugin probable; Codex per probe), an opt-in feature blocks code
  writes when the session's trace shows a plan without an `APPROVED` plan
  review. Default off; the fast path is never gated by it because it keys on
  the trace's own substantial-work declaration, not on every edit.

## Scope

In: `install.sh`/`uninstall.sh`; `shared/roles/` (agents.json, role texts,
build-agents renderings if the Claude Code `plan` agent is added);
`shared/scripts/` (`ai-budget.py`, `scope_guard_register.py`, doc-check
trace-attestation checks, `resolve-models.py` only if Codex model data is
added); `shared/commands/doc-create.md` + `doc-start.md` (+ their Codex skill
and OpenCode command renderings); `codex/` (new global-AGENTS block source,
hook adapter fix or removal); `claude/`, `opencode/` where parity or
attestation wiring touches them; docs (`documentation-harness.md`,
`model-router.md` if session-file semantics change, `scope-guard.md`,
`README.md`, kit `AGENTS.md` index); tests (static, generated-artifact, and a
real-client proof script/checklist per runtime).

Out: customer-repo residue cleanup (stale `active` traces and deleted-code
plans in cs-kernel/mrcall-desktop — separate housekeeping); the model router
feature's design; new runtimes; changing the machine's
`approval_policy`/`sandbox_mode` stance — the solution must hold under
`approval_policy = "never"` + full access, because that is how the machine
actually runs.

## Constraints

- **Fast path intact.** No mechanism may require a review verdict for
  fast-path-eligible work, and none may add startup cost that scales with
  project/session folder counts (existing doc-start economics stand).
- **Managed vs user-owned.** `~/.codex/AGENTS.md` and project `AGENTS.md` are
  user territory: delimited kit-managed blocks only, never overwrite foreign
  content, uninstall removes exactly the kit's blocks (the doc-scope and
  hooks-registration precedents).
- **Probe before build.** Every assumed runtime mechanism is verified on the
  installed real client before implementation relies on it: (a) Codex injects
  `~/.codex/AGENTS.md` into sessions; (b) `spawn_agent` accepts a role charter
  in its task and what it does about models; (c) Codex `PreToolUse` payload
  for `exec`/`apply_patch` and whether denial works; (d) OpenCode plugin
  denial path in a real client. A negative probe converts that scope item into
  an honest declaration or removal — never a shipped dead mechanism.
- **No dead mechanisms.** Anything shipped as enforcement is demonstrated in
  a real client (kit Q&A rule: unit tests don't count), or it does not ship
  and no doc claims it.
- **Generated-artifact discipline.** New or changed rendered agents go through
  `shared/roles/` sources + `build-agents.py`; `tests/test_agents_generated.sh`
  and the static/install tests stay green; installer stays idempotent.
- **Data hygiene.** No secrets in command arguments, logs, or artifacts; a
  session never names a model — budget data stays in `shared/roles`; all docs
  in English; kit `AGENTS.md` stays the thin single source of truth.
- **This work itself** follows the reviewed flow: brief → fresh reviewer
  `APPROVED` → milestone plan → fresh reviewer `APPROVED` → milestones with
  integration reviews → final end-to-end review.

## Acceptance criteria

1. **Codex, real client, fresh session, no doc-start**: asked which delivery
   gates bind it, the session answers from injected instructions (no file
   reads); given a scripted substantial task, its transcript shows a spawned
   reviewer sub-agent and a recorded verdict **before** the first code patch.
2. **Codex brake**: either one real denial of an `apply_patch` on a
   scope-marked file with visible reason and successful retry, or the Codex
   guard is absent from installer, `hooks.json`, skills, and docs — with a
   recorded probe showing why.
3. **`/ai-budget low|medium|high`**: Claude Code and OpenCode roster models
   switch as today (regression-proven); Codex either receives budget-resolved
   models per spawned role or the command prints an explicit degraded line.
4. **Roster parity declared**: `ai-help` and docs list, per runtime, the roles
   that exist with their budget source, and every missing role carries a
   stated reason (including Claude Code `plan`, whichever way the plan
   milestone decides).
5. **Attestation works end-to-end**: a substantial work item whose trace lacks
   the plan-review verdict is flagged by `doc-start` and rejected/flagged by
   `doc-end`/`doc-critic` on at least one real client per runtime where those
   commands run; OpenCode's watchdog/`post_task_gate` path has real-client
   proof recorded in `docs/active-context.md`.
6. **Strict mode (if shipped)**: opt-in per runtime, one real-client denial +
   retry proof per runtime that claims it, fast-path work demonstrably
   unaffected.
7. **No regression**: existing features (router, shortcuts, nr/av, migration,
   CC/OC scope guard, generated-artifact and install tests) pass; uninstall
   leaves no kit residue in `~/.codex/AGENTS.md`, project `AGENTS.md` blocks,
   or hook registries.

## Material assumptions

- Codex reads `~/.codex/AGENTS.md` as global instruction on 0.156.1+ (docs
  claim it; the audited session shows only project-level injection — probe
  a). If false, C1-Codex falls back to the per-repo doc-create block plus a
  doc-start-emitted instruction, and the global claim is dropped.
- `spawn_agent` sub-agents inherit the session model; per-spawn model override
  unknown (probe b). Either outcome is shippable; only the reporting differs.
- Codex hook events for unified `exec` may not expose patch-level granularity
  (probe c); removal is an acceptable, planned outcome.
- The operator keeps `approval_policy = "never"`; no acceptance criterion may
  depend on approvals being re-enabled.

## Risks

- **Platform drift**: Codex multi-agent and hook surfaces are young and move
  fast; every shipped claim is pinned to the verified version, and the probe
  scripts are re-runnable so a Codex upgrade can be re-attested cheaply.
- **Over-enforcement**: blocking by default would gate the fast path and
  recreate prompt fatigue; mitigated by attestation-default, strict-mode
  opt-in, and trace-keyed (not edit-keyed) blocking.
- **False assurance recurrence**: the dead Codex matcher shipped because
  registration was verified but firing never was; the "no dead mechanisms"
  constraint and real-client acceptance criteria exist to make that class
  unshippable.
