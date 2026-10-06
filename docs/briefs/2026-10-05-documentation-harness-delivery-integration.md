# One AGENTS.md entry point and a verifiable documentation lifecycle

Review: **APPROVED** on 2026-10-05 by the independent `reviewer` agent
`brief_review`. No blocking findings remain. This consolidated brief includes
the lead's earlier `REVISE` findings, the AGENTS-only migration, and startup
cost requirements. Approval does not establish runtime behavior or savings.
The operator has authorized brief review,
planning, plan review, and implementation through the required delivery gates
without further routine approval requests. Downstream fleet migration remains
outside scope.

<!-- doc-scope:start -->
Scope: requirements and acceptance criteria for a single AGENTS.md instruction
entry point and documentation-first work with verified closure, including
migration, behavioral validation, and explicit runtime enforcement limits.
<!-- doc-scope:end -->

## Problem and intended outcome

The operator repeatedly observes agents investigating source before using the
repository's documented knowledge, and updating documentation without the kit's
reconciliation and verification workflow. The motivating Qonto integration
session in MrCall Desktop is a reported instance, not a measured failure rate.

The current kit splits project instructions into `AGENTS.md` and the managed
delivery protocol into `CLAUDE.md`. Its Codex entry instructions require the
lead to open `CLAUDE.md`. That protocol specifies development review gates but
does not explicitly bind ordinary task entry to `doc-start` or completion to
`doc-end`. The documentation workflows exist without being integrated into
the ordinary delivery path. This is an observed contract gap, not proof that
it is the only cause of noncompliance.

The intended outcome is one instruction entry point and a documentation
lifecycle agents follow on ordinary requests without operator reminders.
Required documentation must guide investigation. Documentation updates must
follow the kit's ownership, consolidation, and semantic verification rules.
Missing obligations must prevent a verified completion result wherever a
runtime control can establish that guarantee; remaining bypasses must be
reported and measured rather than renamed as success.

Removing `CLAUDE.md` simplifies instruction delivery. It does not by itself
establish that an agent follows the delivered instructions.

The operator also reports that adding an explicit context-saving reminder to
`doc-start` improves its context use. Efficient startup must be the default;
requiring that reminder is a separate usability failure. The reported UI
percentage is not yet an attributed measurement of startup overhead.

## Current evidence and related contracts

- [The current template](../../shared/templates/CLAUDE.md) and
  [Codex entry block](../../codex/AGENTS.block.md) carry the delivery flow.
- [The harness contract](../documentation-harness.md) defines ownership,
  versioning, work traces, baseline semantics, and living-context discipline.
- [doc-start](../../shared/commands/doc-start.md),
  [doc-end](../../shared/commands/doc-end.md), and
  [doc-critic](../../shared/skills/doc-critic/SKILL.md) define the existing
  documentation procedures. Their requirements must survive the integration.
- [Current state](../active-context.md) records installed Codex roles and
  distinguishes instruction guidance from mechanical enforcement.
- [Anthropic's memory documentation](https://code.claude.com/docs/en/memory#agents-md),
  checked on 2026-10-05, documents direct `AGENTS.md` loading from Claude Code
  2.1.277. The installed CLI reports 2.1.280. The documentation identifies
  additional limitations before 2.1.281, including some sessions with telemetry
  disabled or third-party providers. Default loading also depends on ancestor
  `CLAUDE.md` / `CLAUDE.local.md` files and the instruction-file setting.
  Version output and documentation are not a real-client loading test.
- [The earlier delivery-gates proposal](2026-09-27-enforceable-delivery-gates.md)
  contains historical runtime observations, some superseded by current kit
  state. This brief is the sole proposal for the instruction-entry and
  documentation-compliance work described here. Its overlapping requirements
  are consolidated here; unrelated role parity, budget resolution, and broader
  write-guard work are not prerequisites or additional scope.
- A read-only startup analysis on 2026-10-05 measured 10,868 bytes for the
  shared `doc-start` workflow and 614 for its Codex wrapper. The five profile
  and orientation files total 15,994 bytes: 27,476 bytes altogether, about
  6,869 tokens under the checker's bytes/4 convention. This is a static file
  inventory, not actual request occupancy or incremental startup cost:
  already-injected material must not be counted again as a new read. The
  canonical and Codex workflows are byte-identical; the installed skill
  resolves to the repository copy. Actual UI usage and reminder effects
  remain unmeasured.

## Required behavior

### 1. AGENTS.md is the sole repository instruction entry point

Supported clients must receive the minimum binding kit lifecycle instructions
through root `AGENTS.md`, without a discretionary read of `CLAUDE.md` first.
Keep a clearly delimited kit-managed section and preserve project-owned
instructions and routing outside it. Maintain one canonical kit source for the
managed content and regenerate its installed surfaces consistently.

Keep always-loaded instructions short: entry triggers, obligations by task
kind, completion conditions, and workflow pointers. Detailed procedures remain
in their canonical workflows. A pointer alone is not evidence that its
procedure was loaded or executed. Preserve the thin-index budget; do not copy
whole skills or the durable contract into `AGENTS.md`.

Migration retires the kit-managed repository `CLAUDE.md` only after its
required instructions have a verified replacement. It must preserve foreign or
customized content and stop before ambiguous deletion. User-level or ancestor
Claude instructions are not owned by this migration. Detect and report any
that change the tested loading behavior; do not silently modify them.

Declare supported client versions, settings, and execution modes from actual
loading tests. For an unsupported configuration, give an explicit compatibility
outcome before migration. Do not leave a repository silently without its
instructions or claim that a surviving compatibility file is the migrated
single-entry configuration.

### 2. Entry and closure obligations are defined for ordinary requests

The lead must load the routing index, docs index, and living context itself,
then read the relevant durable documentation before substantive source
diagnosis. Bounded profile, installation, and routing checks may precede those
reads. Do not scan the codebase to decide which documented subsystem owns the
request when the routing documents already answer it.

| Request | Required entry | Required completion |
|---|---|---|
| Repository explanation or read-only diagnosis | Minimum documentation orientation and relevant durable docs before source investigation | Answer with findings and uncertainty; no mandatory edits, work trace, baseline advancement, or release |
| Small reversible change eligible for the existing fast path | Same relevant orientation, reusable within scope | Explicit documentation-impact decision; proportionate reconciliation and applicable checks without requiring the full development review chain |
| Documentation-only update | Orientation and the existing document's purpose and ownership | Lead-owned reconciliation, mechanical gate, semantic verification, and living-context shape check even without a development reviewer |
| Substantial development | Valid startup before substantial investigation or delegation | Existing reviewed delivery flow plus applicable documentation closure before final approval |
| Brief-only or review-only request | Relevant orientation and requested artifacts | Deliver only the requested artifact or verdict; no automatic planning, implementation, migration, baseline advancement, or release |

A code change that affects documented behavior requires semantic verification
of the affected documentation, including documents left unedited. A fast-path
change with no documentation impact may record that justified outcome without
running unrelated consolidation. Purely editorial changes need proportionate
verification; they do not authorize a repository-wide audit.

Reuse valid startup within the same scope. Repository or worktree changes,
relevant instruction changes, and resumed sessions without the needed context
must reload the affected material. A persisted startup receipt cannot stand
in for documents no longer available to the lead after compaction. Ordinary
source edits must not restart the whole startup procedure.

### 3. Closure checks coverage as well as correctness

The lead owns reconciliation of session signal and current state. Preserve
English artifacts, document ownership, the thin routing index, and the living
snapshot rather than appending session history. A delegated critic reports
findings; it cannot silently reconstruct or rewrite the lead's session account.

Determine which documentation a behavior change affects before deciding what
to edit or audit. A review of changed Markdown alone is insufficient: an
unchanged document can become false, and a new capability can need a missing
documentation entry. Keep this impact analysis bounded to the task and its
documented dependencies rather than reading all historical material.

Applicable closure evidence includes the impact decision, reconciliation,
mechanical results, semantic results, and the always-required living-context
shape check during consolidation. Repair stale claims and repeat the affected
checks. Preserve `UNVERIFIABLE` findings and their limits; do not report them
as verified. Generic code review or a clean mechanical gate is insufficient.

The final reviewer must return `REVISE` for missing or stale required evidence.
Documentation-only and fast-path work must have an explicit completion check
without depending on a final development reviewer that those paths do not use.

Closure ordering must make documentation evidence available to final review
before baseline advancement and any applicable release. Avoid recursive
invalidation from recording evidence or advancing baseline metadata. Automatic
documentation closure must not expand a limited request into publication;
release remains subject to its scope, authorization, and prerequisites.

### 4. Evidence and enforcement have distinct guarantees

Recover the minimum completed and pending obligations across delegation and
resumption. Bind records to repository, worktree, task scope, workflow version,
and the content examined, including relevant staged, unstaged, and untracked
changes. Later relevant changes invalidate affected results. Another worktree
or task must not inherit approval by accident.

Record actual critic and reviewer result references, outcomes, and explicit
deferrals. Specify who creates each record and who checks its freshness. An
agent-written success flag is an attestation, not independent enforcement.
Prefer an existing compatible evidence mechanism over a parallel gate system.

For each supported client and tested mode, distinguish instruction delivery,
observable compliance, and demonstrated runtime blocking. Test the lead
skipping the entire lifecycle, including evidence creation and final review.
A check reached only through the skipped workflow cannot detect that bypass.

Classify each negative case as prevented, detected by a control outside the
skipped path, or still possible. If no independent control exists, say so.
An observable failure is useful evidence, but does not satisfy a claim that
noncompliant completion is prevented. Require a real denial and successful
compliant retry for every claimed blocking mechanism. Do not assume a universal
pre-tool or final-response hook, and do not change permissions or sandboxing.

### 5. Demonstrate improvement before building evidence infrastructure

Start validation with a bounded current-versus-candidate experiment on the
operator's actual Codex client and work mode. Use disposable repositories and
ordinary requests without naming `doc-start`, `doc-end`, the critic, or the
expected sequence. Exercise explanation, development, documentation updates,
and limited brief-only requests. Observe tool order, document quality,
completion claims, and operator interventions independently of agent receipts.

Repeat each ordinary Codex scenario in at least three fresh sessions per
configuration, preserving failures in the results. Pin client version,
instruction installation, settings, and model configuration; do not attribute
differences to the kit when other relevant conditions changed. Repeat the
applicable user paths on Claude Code and OpenCode before claiming support
there. A headless test does not establish interactive behavior automatically.

Require all candidate trials to satisfy the applicable obligations without
operator reminders. Report numerator and denominator, elapsed time, and
available context measurements; repeated passes are evidence for the tested
configuration, not a universal guarantee. If the baseline does not reproduce
the failure, report that limit rather than claim measured improvement.

The experiment must precede substantial evidence-store implementation. If the
candidate still skips the lifecycle, revise the approach or record that the
intended outcome remains unmet. A documented fallback alone must not turn that
failed outcome into completion of this workstream.

### 6. Efficient startup is the default, with attributable costs

Separate preloaded runtime instructions and skill metadata from workflow text,
new document reads, tool results, and delegated-agent context. Report parent
context growth separately from total agent usage. Distinguish measured tokens
from byte estimates; a UI percentage, collapsed output, or cached input does
not establish reduced context occupancy. User wording can guide subsequent
actions but cannot remove instructions already injected into that request.
Any runtime configuration experiment must be reported separately from a
workflow improvement; disabling unrelated capabilities is not an optimization
of `doc-start`.

Read one current workflow copy. Reuse instructions and documents confirmed
present in the lead's context without reopening equivalent installed or
generated copies. Preserve full required lead orientation; neither truncation
nor a worker's summary substitutes for it. Simplify the startup instructions
themselves while retaining their obligations and moving nonessential rationale
off the startup path. Do not attribute expensive startup to active-context
drift without measuring the other contributors.

Use a compact, deterministic result for mechanical startup checks, reusing or
extending the existing checker rather than duplicating its validations in
agent reasoning. Include drift, working-tree state, open-plan and issue
results, and every required violation and advisory without dumping raw file
inventories or frontmatter. Distinguish the bounded orientation payload from
diagnostic output that grows with actual findings; do not hide findings to
meet a size target.

Delegate mechanical work only when measured context or execution benefit
justifies the child instructions, task, and result. Use a bounded task without
full conversation inheritance when it needs no session history. Do not claim
that moving tokens from parent to child eliminates their cost.

Within the existing experiment, compare ordinary `doc-start` requests against
the same requests with a context-saving reminder, using equivalent fresh
sessions and identical preloaded configuration. Before evaluating a candidate,
record an incremental startup budget and comparison tolerance grounded in the
baseline measurements. Both prompts must retain all checks and required
knowledge; the ordinary request must meet the budget without the reminder.
Measure the candidate's reduction against current behavior and investigate
any material reminder advantage rather than accepting it as normal variance.

## Migration and scope constraints

- Change canonical instructions, installer/uninstaller behavior, profile and
  checker expectations, documentation workflows, generated surfaces, and
  their relevant tests consistently. Preserve project-owned content through
  installation, migration, repeated installation, and uninstall.
- Removing the required `harness_file = CLAUDE.md` contract requires a harness
  major migration under the current versioning rules. Version preflight must
  remain strict; older repositories must not be silently reinterpreted.
- No fleet-wide edits to downstream repositories. Migration is an explicit,
  separately authorized operation, tested on representative fixtures first.
- Keep startup bounded as project and session folders accumulate. Do not load
  `docs/projects/**`, `docs/sessions/**`, or historical evidence bodies as
  ambient context. Store small evidence references without credentials or
  customer payloads; validation transcripts belong in controlled test output.
- Preserve existing development gates, fast-path eligibility, and operator
  scope. Do not redesign model routing, role budgets, or unrelated guards.

## Acceptance criteria

1. Fresh supported-client sessions load the managed obligations from
   `AGENTS.md` without a repository `CLAUDE.md`. Real-client checks cover
   applicable ancestor-file precedence, settings, and compatibility limits.
2. Migration preserves project instructions and transfers the delivery
   protocol; the checker and workflows accept the migrated layout. Repeated
   migration is safe, and customized legacy files cannot be silently deleted.
3. Ordinary requests satisfy the entry/completion table without naming a skill
   or receiving operator reminders, with the repeated Codex results and other
   supported-client checks reported as specified above.
4. A code change leaving an affected document untouched is detected before
   verified closure, as is a false claim inside modified documentation.
5. A mechanically valid active context that narrates session history is
   detected even when untouched. Reconciliation preserves current knowledge
   and follows the existing archival and ownership rules.
6. Missing or stale critic evidence prevents the applicable completion check
   from passing. Skipping that check entirely is separately tested and its
   prevention, independent detection, or remaining bypass is stated accurately.
7. Relevant dirty and untracked changes invalidate evidence; another worktree
   cannot reuse it. Resumption recovers pending obligations and restores needed
   lead context without unnecessarily repeating valid checks.
8. Read-only, brief-only, and review-only requests remain limited. Fast-path
   and documentation-only requests receive their defined checks without being
   forced through the full development review chain.
9. Baseline advancement follows applicable reviews without self-invalidation;
   release cannot begin before its own authorization and prerequisites hold.
10. Mechanical/source tests and real-client behavioral results are reported
    separately. No runtime guarantee is accepted solely from generated text,
    registration, unit tests, or an agent's statement that it complied.
11. Ordinary startup meets the predefined incremental context budget while
    preserving its obligations. Paired reminder trials show no material
    advantage beyond the predefined tolerance. Results identify preload,
    workflow, document, tool-output, and delegation costs separately, stating
    any unavailable measurements instead of inferring them from UI percentages.

## Handoff

This is the consolidated brief for review. Planning may begin only after its
review returns `APPROVED`. Planning must resolve the concise managed block,
compatibility policy, staged migration, experiment fixtures and observation,
completion controls per client, and only then any needed evidence mechanism.
A failed feasibility experiment requires revising the approach, not lowering
the acceptance criteria after observing the results.
