# Automatic av for analysis and result reports

## Intent

Before concluding a response that reports an analysis or a result, the answering
agent receives and applies the canonical av engineering-lead stance to the
current assignment. It must do useful authorized, feasible work rather than
merely report that a branch failed without investigating it. The operator's
manual av invocation is the behavioral reference. This replaces the earlier
completion self-certification mechanism, not the repository review lifecycle.

## Exact activation boundary

Activate av if and only if the outgoing user-facing response reports an analysis
or result. A short result is still a result. Mixed responses activate whenever
they contain a report. A progress/status answer reporting findings is included.
A technical explanation that develops an analysis is included even when the
operator asked a question; question wording alone is not an exemption.

Pure acknowledgment, greeting, clarification request with no findings, pause or
cancellation acknowledgment, bare stance restatement, quoted-only material with
no agent finding, empty/missing answer and internal coordination without a
user-facing report must not activate av. A bound task, terminal event, character
count, keyword, explicit delivery declaration or receipt is not the selector.

Selection is semantic. Native model-backed selection or a bounded semantic
classifier may route the callback, but cannot be replaced with prose pattern
matching or a self-declared completion certificate. Negative selection produces
no av prompt, forced continuation, revised answer or successful-completion claim.
The classifier's routing data is not an assignment review from the answering
agent. Any per-response classification cost must be stated and bounded.

## Required behavior

The same canonical stance body serves manual and automatic application. An
automatic invocation explicitly carries the current draft and open assignment;
it must not trigger av's bare-invocation acknowledgment-and-stop behavior.
The original agent resumes in its own context and can use its normal authorized
tools. If the draft is adequate, it remains unchanged. Otherwise the agent
performs and checks remaining work, then reports the resulting state. The hook
never invents work, expands authority, bypasses reviews or performs forbidden
external actions. Pauses, cancellation, real missing authority/input and actual
resource limits remain legitimate stops.

## Scope

Implement and verify a shared behavior for Codex, Claude Code and OpenCode,
including actual currently installed runtime/version constraints. Each needs a
measured integration; an instruction-only fallback is not equivalent to a hook.
Capability investigation must establish selection, draft availability, parent
continuation and display ordering before adapters are selected. Record any
unsupported runtime explicitly; never silently ship Codex-only success as the
requested cross-system result.

Retire the old runtime completion JSON challenge/receipt, bind-to-arm and strict
exec certification paths and their owned registrations/assets. Preserve the
separate doc-check completion evidence API, av manual behavior, optional sc,
scope guard, verification warnings and unrelated operator hooks/configuration.
The prior adapter's registrations were already disabled during the interrupted
operator exchange; do not restore them. Preserve foreign WIP and historical logs.

Work is limited to ai-kit sources, isolated test installs and final owned adapter
installation. No engine, cron, operational clone changes or restarts. No release
is authorized by this task. Delegations require a concrete deliverable and a
120-180 second limit; no unattended loops or unbounded acceptance spending.

## Acceptance

- On each of the three systems, actual native callbacks select analysis/results
  and deliver the canonical av body into the original answering session.
- The reported deployment/probe example resumes authorized investigation and
  produces real verification evidence; mere apology or av acknowledgment fails.
- A completed analysis/result receives av but performs no invented work; adequate
  final content remains unchanged. Results with legitimate stops preserve scope.
- All negative categories above incur zero av activations and zero extra parent
  turns. Positive short/mixed/status cases and quoted-only negative cases are
  covered. Repeated callbacks, foreign hook continuations and concurrent sessions
  cannot multiply av passes or suppress an unrelated answer's first application.
- Native tests establish callback execution and observable behavior, not private
  reasoning. Deterministic fixtures establish protocol/registration facts; they
  do not establish semantic classifier accuracy or real-model behavior.
- First run free protocol/install checks. A later plan must bound any necessary
  real-model semantic trials by calls/time/output and stop on first failure;
  never repeat paid acceptance on a candidate with failing free checks.
- Demonstrate actual display ordering per client; do not claim prevention before
  display when an integration only resumes after a visible draft. No false
  certification or silent success on missing capabilities/classification failure.
- Tests, docs, explicit doc-critic, reviewed milestones, independent final review
  and checker finalization complete before claiming delivery. Public release
  remains separately authorized.

## Open implementation questions

Client APIs determine semantic selection transport and whether interception is
before or after draft display. These are engineering discovery obligations,
not permission to weaken the activation boundary. Cross-client capability facts
and cost/limit choices belong in the reviewed execution plan.

## Operator-authorized production scope — 2026-10-23

The operator explicitly requests production deployment and release of this
candidate as it stands, accepting the disclosed OpenCode provider refusal.
Release/install all three adapters without changing their implementation or
models. Successful real OpenCode positive/negative acceptance is waived for this
release, not claimed as passed. Retain the refusal and display/trust limitations.
No additional paid inference, service restart or credential change is needed.
The reviewed failed-plan-status addition is included in this release. Required
deterministic checks, documentation review and final integration review remain.
