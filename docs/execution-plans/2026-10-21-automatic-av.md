---
status: completed
---

# Automatic av implementation

## Approved intent

The [approved brief](../briefs/2026-10-21-automatic-av.md) requires semantic
selection if and only if the outgoing response reports analysis/results, followed
by canonical av in the same answering context. No completion self-certificate.

## Capability evidence and architecture

Read-only discovery is retained at `/tmp/mrcall-ai-kit/av-runtime-capabilities/`.
Official Codex hook documentation and installed 0.163.0 expose command/MCP Stop
continuations, not a native semantic matcher. Claude 2.1.296 supports Stop
continuations and native prompt selection. OpenCode 2.0.32 has native plugins:
`session.execution.succeeded`, `session.context`, `session.generate` and
`session.prompt`. These are actual pinned upstream contracts, not native tests.
All three may expose the first draft before continuation; report that limit.

Use one installed canonical av body and one semantic selection policy. Selection
returns only APPLY or SKIP (or a native boolean equivalent); it does not ask the
answering agent to certify completion. Classify the actual full draft and relevant
request context as data, not instructions. No keywords, size thresholds or task
bindings. Missing/empty non-user-facing text is quiet without classification.
Negative selection neither sends av nor advances the original conversation.

For Codex use a bounded ephemeral read-only native classifier invocation, tools
and recursion disabled, inheriting the configured session model where available.
For Claude use native semantic selection if its returned reason can preserve the
canonical av body exactly; otherwise a tools-disabled bounded native classifier
and command adapter construct that body mechanically. Use the installed verify
role model from the operator budget, never a cheaper model chosen by the session.
OpenCode 2 resolves the operator-installed verify agent with native
`ctx.agent.get({agentID:"verify"})`, requires its explicit model reference and
uses native stateless `ctx.generate.text({model: role.model, prompt})`. The prompt
contains only the selection policy and full request/draft as untrusted JSON.
The native request has no session history or tools; never omit the model and
accidentally select the base default. Its native credential resolver uses the
selected provider's configured authentication. Missing role/model/credentials
is an explicit unavailable diagnostic, never restoration of tools or a retry on
another model. A free native provider fixture must prove the actual tools-empty
request and selected role model, not merely a test double of this API. Positive
selection alone steers canonical av into the same original answering session.
A legacy OpenCode 1 adapter must use its actual SDK, never load the v2 module as
an old-style plugin. Installation selects the discovered runtime API explicitly.

Canonical av is shared with manual entries. An automatic task wrapper supplies
the outgoing report and the existing assignment; the manual bare-invocation
restatement is not the automatic action. Adequate content stays unchanged. The
parent performs real feasible work when warranted, with all original authority
and lifecycle boundaries. No extra av acknowledgment or report of a review.

Recursion state is owned by the adapter and scoped to native session/user-turn
identity (or documented native execution identity plus the adapter's own synthetic
continuation). Foreign hook-active flags alone do not count as our application.
At most one av continuation for an original user turn; a genuine later user turn
must get its own first selection. Concurrent sessions and negative callbacks
cannot consume each other's state. Preserve operator pauses/cancellation and
clean up owned state. No global toggle pretending a turn was reviewed.

Production selection limits apply separately to each transport: one adapter
invocation, 30-second wall-clock deadline including transport, at most 2 KiB of
selector output (the full draft is never truncated), no adapter retry. Native
CLI provider-internal retries are inherited and remain inside that deadline;
a single forwarded-generation production cap is not established. The M2
admission relay independently counts and caps every forwarded generation. Codex
and CLI-based Claude run their own process group, killed and reaped on timeout,
output overflow, tool emission or operator cancellation. Native Claude prompt
selection uses its configured 30-second hook timeout and bounded output schema;
if canonical-reason/output/cancellation constraints cannot be established, use
the CLI transport instead. OpenCode selection must propagate native cancellation
through its request API; a bare Promise.race that leaves inference running is
not cancellation. If that API cannot cancel, use an isolated bounded native
process transport rather than launching uncancellable background classification.
Suppress completions after cancellation and never enqueue av from a timed-out
or obsolete selector. Report budget exhaustion without retrying.

Classifier timeout, invalid output or missing capability produces an explicit
availability diagnostic/status, never a successful-review claim or blanket av.
Classifiers see no credentials beyond their own native configured provider,
receive no tools and cannot mutate repositories. Native generation costs apply
to negative as well as positive selection: normally one classifier call per
nonempty outgoing response. Record this cost rather than claiming free selection.

## Ordered milestones and ownership

### M1 — Shared behavior and native adapters

Lead owns canonical policy/body wiring, shared Python protocol/registration,
Codex/Claude adapters, installer/uninstaller integration and retirement of the
old runtime completion certificate. A bounded execute worker may own only
OpenCode v1/v2 adapters and adapter tests after this plan is approved; it is not
alone in the codebase and must preserve others' edits. All handoffs specify files
and 180-second deliverable checkpoints. No service/engine changes.

Implement the smallest complete selection-to-parent path with isolated native
provider fixtures and tools-disabled classifier transports. Free tests cover
short/mixed/status/analysis positives, acknowledgments/clarifications/quotes/
empty/internal negatives, invalid output, timeout, replay, foreign continuations,
concurrency, same-turn suppression and next-user-turn activation. Verify exact
canonical body delivery and adequate-content preservation. Keep old audit logs
as historical data; retire only owned executable paths/registrations, preserving
foreign hooks and modified foreign files. Preserve the separate doc-evidence API.

Run real installer/adapter CLI paths in isolated homes, copy and symlink, and
actual native clients against deterministic local providers. This proves protocol
execution, not model semantics. Fresh M1 review before behavioral acceptance.

### M2 — Behavioral acceptance

The initial matrix, started only after free checks pass, allows six real-model
native conversations: one positive and one negative for each installed client.
The separately reviewed recovery decision below supersedes its overall ceiling
with seven conversations and 27 forwarded generations, including failed work.
At most six
generation requests per positive conversation and two per negative conversation,
24 total, 90 seconds/conversation, 2 MB
output; stop the matrix on first failure. The positive allowance includes the
initial report, classifier, resumed parent tool request and final response after
tool results; tool requests count as generations, not just final messages. No parallel paid matrices, no silent
retry or model switching. Count classifier and parent calls together; retain
usage, exact invocations, transcripts and actual resulting filesystem/CLI checks.
No paid acceptance for deterministic installation/protocol facts.

Positive cases reproduce a reported result with an uninvestigated failed probe,
requiring the same parent to investigate and verify the actual fixture cause.
Negative cases must leave av and parent continuation counts at zero. The full
semantic category corpus is also independently reviewed; six native examples
establish measured behavior, not universal classification accuracy. Refresh
only affected free evidence after a justified repair; further paid trials require
a new explicit bounded decision. Fresh M2 reviewer checks actual runtime results.

### M3 — Documentation, integration and delivery

Lead reconciles current docs and unchanged affected contracts, preserves displaced
active-context text verbatim in its archive and explicitly invokes doc-critic.
Document per-runtime version/entry point, activation boundary, classifier cost,
display order, failure behavior and measured limits. Complete configured checks,
focused real-user evidence, separate final review and checker finalization.
Install only the reviewed owned adapters after source acceptance, preserving all
other hooks and native trust stores. Verify installed callback paths. No runtime
restarts, operational clone edits, commit of foreign work or public release.

## Rollback and feasibility refusals

Rollback only this task's source and installed owned registrations; leave the
rejected old completion adapter disabled. Keep historical evidence and foreign
configuration. An unsupported native integration, failed semantic routing, or
missing genuine parent continuation blocks the cross-system acceptance; do not
substitute an instruction-only pass, blanket second turn, or Codex-only delivery.
The lead continues independent useful work and records the concrete unmet
acceptance rather than pretending a partial implementation meets the brief.

## Completion transition

Keep status active until the checker finalizes the reviewed transition.

## M1 measured implementation

Shared command routing and native OpenCode2 plugins are implemented. Actual
Codex0.163.0 and Claude2.1.296 loopback cases each pass APPLY/SKIP with zero
selector tools, same-parent identity, retained assignment/report, and exact
canonical stance. OpenCode2.0.32 passes positive/negative dispatch and a delayed
provider cancellation at30seconds; production npm installation of pinned effect
dependency passes. Protocol tests cover routing, isolation, current-turn replay,
later user turns, cancellation and stale results. Actual copy/symlink install
and uninstall tests pass for all3current runtimes, preserving foreign content
and old audit bytes while retiring only owned legacy assets. Full Python
regression reports253passed; the focused native path was refreshed after fixing
an ephemeral Codex transcript-path assumption. All 18 shell checks pass after repairing the managed-template diagnostic-order
regression and refreshing its focused installer evidence. These facts establish mechanics, not semantic quality.

M2 uses a pre-dispatch test-only admission guard bounding actual forwarded
requests, including classifier/parent traffic and native retries. Its measured
checkpoint below records the current results and remaining acceptance. OpenCode1 lacks the new pluginAPI and
receives an explicit unavailability diagnostic; no v2 plugin is loaded as v1.

M1 review requested repairs to command-selector request context, cached legacy
hook retirement and real canonical OpenCode evidence. All three are repaired:
24 core tests pass, copy/symlink migration and inert cached-hook tests pass, all
four actual command-native fixtures retain the current request in selector input,
and a refreshed OpenCode native positive case compares the actual canonical
source assets and delivered stance exactly. These are free loopback checks;
M2 real-model acceptance has not started.

The production retry boundary above was clarified after native source inspection:
one CLI process is enforced, while provider-internal retries cannot be described
as a proven single forwarded request. This changes the stated limit, not the
selection boundary or automatic av behavior; an updated plan review is required.

## M2 measured checkpoint

The first four real-model conversations pass: Codex positive/negative use six
and two forwarded generations; Claude positive/negative use five and two.
Both positives receive one exact canonical av in the same parent, repair the
broken configuration, run the probe and leave matching output. Both negatives
produce one acknowledgment, one successful classifier and zero av continuations.

The fifth conversation (OpenCode positive) stops the matrix. The response
observer failed to decode compressed upstream bytes, and retained native logs
also show the isolated selector rejected by the configured free provider with
an authentication/admission diagnostic. Read-only recovery from that isolated
trial database preserves its actual session messages; no av was delivered and
the broken fixture remains unchanged. Native source and a free builtin-provider
fixture show matching primary/selector client identity headers, so a missing
client header is not established as the cause. The remote admission predicate
is unavailable. Do not restore tools or fabricate a client identity.

Nineteen generations were forwarded against the original shared limit of 24;
OpenCode negative was not started. No further real-model trial is authorized by
an automatic retry. Test-observer encoding repairs and investigation of the
operator-configured verification transport are independent free work. Any
transport/acceptance amendment needs explicit bounded review before further
inference. M2 and cross-system acceptance remain open.

## Reviewed recovery decision for OpenCode

The configured free answering provider rejects the tools-empty selector, while
its native client identity is unchanged. Classification now follows the operator's
installed verify-role model instead of requiring the answering model to support
this isolated request. Native stateless generation provides that explicit model
and zero tools/history. The installed OpenCode verify role currently resolves to
OpenRouter; no model is chosen by this session. Read-only metadata establishes an
existing native legacy OpenRouter API credential. An isolated native client may
import it through a temporary auth.json symlink using its standard migration;
never print secret values, copy credential files or share the live SQLite DB.
This establishes a native credential source, not a successful authentication claim.

The generic generate API bypasses session HTTP hooks. The free/real trial config
therefore routes its explicit verify provider baseURL through the same admission
relay, while the answering provider retains the existing native HTTP hook guard.
Free tests must prove both routes count against one budget, zero selector tools,
actual request/draft isolation and provider cancellation at 30 seconds. The API
exposes no per-call token limit: 2 KiB validates the returned label after native
completion; its 30-second interrupt bounds ongoing inference. Do not claim
streaming byte cancellation or an exact production provider-request cap.

After these free repairs and fresh applicable reviews, permit exactly two
additional real-model OpenCode conversations, positive then negative, six/two
forwarded generations respectively, 90 seconds/2 MB each, stop on first failure.
Include all 19 previously forwarded generations: the amended global ceiling is
27 generations across at most seven original/recovery conversations. No other
repeat, model switch, provider/tool spoofing or parallel paid matrix is authorized.
Keep original failed evidence and all four passing Codex/Claude conversations.
A fresh M2 review must assess the complete record and amended limit honestly.

## Credential preflight correction and final bounded trial decision

The first recovery positive stops after two forwarded requests: the initial
report succeeds and the verify provider returns 401, "No cookie auth credentials
found". Its isolated native database contains no credentials. Total forwarding
is 21/27; the recovery negative never starts. Retained evidence is
`/tmp/mrcall-ai-kit/automatic-av-20261021/semantic-opencode-2oi1hrzy/`.

The assumed fresh-database legacy import was incorrect: pinned OpenCode 2
bootstraps the schema and marks migrations complete without running their up
functions, so the legacy-auth import runs only during an existing-database
upgrade. Do not fake migration metadata or share the production database.
Use the supported native private-server provider connect API with the existing
legacy key held only in memory. Prove fake-key header forwarding locally before
any further inference. Native storage inside the isolated client is allowed;
no secret values enter logs or copied credential files. This repairs test setup,
not the unchanged production selector, and does not change global authentication.

Following free authentication proof and review, the final allowance is exactly
two additional isolated OpenCode trials: positive at most four forwarded requests,
negative at most two, 90 seconds/2 MB each, stopping on the first failure. The
positive's original assignment explicitly permits one batched shell call after
av to inspect the fixture, repair the configuration and run its actual verifier.
This preserves actual parent execution evidence within the remaining resource
limit. Count all 21 prior requests: global ceiling remains 27, at most eight
original/recovery conversations. No further retry, provider/model change,
global credential mutation, service restart or budget increase is authorized.

## Current stop condition

The final positive conversation authenticates successfully and emits its exact
initial report. The configured native verify provider then returns HTTP 200 with
`finish_reason: content_filter`, `native_finish_reason: refusal` and empty text.
This is neither SKIP nor a completed av application. No av is delivered, the
fixture remains broken, and the negative conversation does not start. Evidence:
`/tmp/mrcall-ai-kit/automatic-av-20261021/semantic-opencode-_053d32h/`.

The matrix has forwarded 23 requests across seven attempts; four Codex/Claude
conversations are accepted. The unused four requests are not authorization to
ignore the stop-on-first-failure rule. No further inference, model/provider
switch, global credential mutation or service restart is authorized by this plan.
The remote refusal predicate is unestablished; do not describe it as classifier
misclassification or invent a local repair for an external provider decision.

Cross-system acceptance is blocked on an operator-configured verification
provider returning a valid label for this tools-empty request. Remaining work:
real OpenCode positive/negative acceptance, M2 approval, final documentation and
integration review, current completion check/finalization and reviewed owned
adapter installation. Independent source checks and truthful documentation
reconciliation continue; no global new adapter activation, commit/release or
baseline advancement claims are permitted while required acceptance remains open.

## Operator-authorized release decision — 2026-10-23

The current operator authorizes production deployment and release as-is, with
the disclosed OpenCode provider refusal. This decision supersedes the previous
release prohibition and the requirement for successful OpenCode real-model
acceptance before delivery. The missing positive/negative OpenCode cases are
waived for this release, never relabeled as passed; no further inference or
model/provider change is authorized or necessary.

Retain all failed trial evidence and four passing Codex/Claude conversations.
M2 review now checks this qualified acceptance and disclosure against the exact
operator waiver. Reuse unchanged M1 and failed-plan-status approvals. Reconcile
docs, invoke doc-critic, refresh scoped mechanical/focused checks and obtain a
separate final review. Finalize the existing completion task and its plan status,
commit only the known task changes, then publish v9.5.0 using the documented
release workflow and required deterministic release checks. Install doc-harness
for all three runtimes with backups and ownership preservation; verify actual
installed assets, hook registrations and quiet legacy/empty callbacks. Native
reload/trust remains explicit; do not restart engines or edit trust stores.
The release includes the reviewed failed-plan-status addition.

The failed-state workflow update changes the original task's immutable workflow
fingerprint. The checker requires a new release task bound to current workflows;
retain the original blocked record and import actual reviewed artifacts instead
of resetting it or manufacturing fresh evidence. This is the completion task
used for the authorized release and the same reviewed plan transition.
