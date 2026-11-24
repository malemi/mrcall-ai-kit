# Brief — supervision completion failure and controller audit

## Requested outcome

Produce an evidence-backed diagnosis and implementation brief for the supervisor's failure to drive the entrusted sessions to verified completion. The operator had to take over. Preserve the complete available incident logs so a subsequent investigator can reconstruct decisions, messages, receipts, authority and state transitions without relying on the supervisor's retrospective account.

This deliverable is a brief and local evidence package. Implementation, resumption of supervision, product changes, deployment and release require their own subsequent task. Supervision was explicitly interrupted on 2026-11-13. All four discovered related legacy bindings were detached, their tasks paused, and their cron entries removed. Collection uses existing local records without contacting or waking the entrusted sessions.

## Evidence package and access

The local evidence root is `/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/`.

- [Complete available logs archive](/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/logs.tar.gz)
- [Supplemental state-root observations and collection tooling](/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/supplemental-logs.tar.gz)
- [Supplemental manifest](/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/supplemental-manifest.json)
- [Supplemental verification](/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/supplemental-verification.json)
- [Per-file source path, archive member, byte length and SHA-256 manifest](/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/manifest.json)
- [Archive checksum](/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/logs.tar.gz.sha256)
- [Archive verification result](/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/verification.json)
- [Collection changes and missing paths](/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/collection-changes.json)
- [Collection metadata and scope](/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/exports/collection-metadata.json)
- [Chronological execution export, JSON](/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/exports/executions-chronological.json)
- [Chronological execution export, TSV](/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/exports/executions-chronological.tsv)
- [Decision and intervention audit timeline](/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/audit-decision-timeline.json)
- [Intervention intents and delivery results](/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/interventions.json)

The principal archive preserves the available contents of the incident evidence trees, four consistent SQLite backups and complete table exports, selected native root and descendant rollouts including rotated files, and current installed/repository supervision source snapshots. The supplemental archive retains all four state roots' non-database files, including the observer's observation JSON records, the collection script and derived decision/intervention timelines. Historical artifacts retain original failures and later corrections. Full raw native logs can contain private reasoning, prompts, tool output and sensitive local material. Keep the evidence local and private. External publication requires a separately prepared redacted derivative.

The archive member name is the absolute source path with the leading `/` removed. For example, `tmp/m6-local-controls-20261107/invocation-binding/clock-allocation-provenance654.md` is the retained allocation-provenance record. The manifest is the authoritative inventory. Missing native paths are recorded in `exports/missing-native-paths.json`; available logs must not be described as a complete history of unavailable sessions. Each archive's verification reads every member and compares its length and digest with the corresponding manifest. The SQLite backups are internally consistent snapshots; the wider filesystem collection is a sequence of per-file captures, not one atomic incident-wide snapshot. Active native rollouts may gain subsequent entries. The collection-change check is advisory and does not prove that every source stayed unchanged throughout collection.

## Exact identities and incident boundary

| Responsibility | Native root UUID |
| --- | --- |
| Supervisor | `01a181e1-f7cd-7a50-8111-c25e0bfd044d` |
| REMOTE | `01a13069-ea38-7fe3-af86-57883ec8d4fd` |
| PROBLEMI5 | `01a1ab51-13f9-7ab2-92df-fcedeb2b53bb` |
| MEMORY | `01a14013-28db-7b71-be70-c2aff5456a6e` |
| Observer of the supervisor | `01a17d1d-9986-77d2-b4ca-6aee6acc90a3` |

The principal state directory was `/home/mal/.local/state/mrcall-ai-kit/supervision-three-session-20261110`. Its binding was `remote-problemi5-memory-coordination`; its task was `three-session-coordination-20261110`. The mandate covered exact-root coordination, preserving stopped MEMORY work, required roles, necessary tests and verified completion within existing scope and spending limits.

Three related historical state roots are also preserved: `supervision-problemi5-20261105`, `supervision-remote-problemi5-20261105` and `supervision-observe-prob3`. Their complete exports support investigation of overlapping supervision and stale messages. Their existence alone does not establish that every message or delay came from them.

## Work labels and accountable sessions

- **M6** is the acceptance stage of the interactive-reply draft/consent work. It covers the native interactive lifecycle and the ordinary dual-clone FULL acceptance run. Local controls support admission, budgets, containment and deadlines. PROBLEMI5, also called ROOT in these work records, owns kernel/integration/consumer work; REMOTE owns the Desktop engine/controller. M6 is not the MEMORY session.
- **CLOCK** is the checkpoint protocol joining original driver clock/deadline observations to a durable parent event and acknowledgment before protected work proceeds. ROOT owns the shared contract and parent side; REMOTE owns the Desktop consumer. `ACKED` is the acknowledged state whose relationship to the actual parent cleanup latch remained unverified in the examined test-only scope.
- **B2** is the startup-parent integration step named “Integrate the frozen private graph and adopt the original account.” It wires the parent to the original byte ledger/account while preserving identity, charges and clock. Its scope stops before actual driver/runtime launch, so B2 acceptance alone cannot establish a successful live launch.

Definition evidence: `/home/mal/hb/docs/briefs/2026-11-07-interactive-reply-m6-controls.md`, `/home/mal/.local/share/mrcall-operational-evidence/2026-11-05/interactive-reply-development/m6-acceptance-planning/revised-approved/plan.md`, and the `d0-clock-ack-contract-plan509.md` and `startup-owner-plan633.md` records under `/tmp/m6-local-controls-20261107/invocation-binding/`. These documents are retained in the principal or supplemental archive with their original path names.

## What the records establish

The principal database contains 269 executions, 269 outbox entries, 5,132 audit entries and 271 memory entries at collection. Execution outcomes total 133 `completed` and 136 `blocked`. An assessment marked completed can still concern an incomplete operational assignment; those 133 rows do not establish 133 completed deliverables.

Two contiguous runs account for all 136 blocked execution outcomes:

| Assessment labels | Count | First result UTC | Last result UTC | Demonstrated condition |
| --- | --- | --- | --- | --- |
| 124–150 | 27 | 2026-11-10 23:54:32.000432 | 2026-11-11 01:33:24.605891 | Worker estimates treated as insufficient authority to continue |
| 161–269 | 109 | 2026-11-11 02:13:36.329155 | 2026-11-11 08:47:30.925312 | Repeated pending product-scope decision and archive uncertainty |

The first interval spans 1 hour 38 minutes 52.605459 seconds. The second spans 6 hours 33 minutes 54.596157 seconds. These are intervals between recorded assessment results, not measured exclusive worker time or billed usage. No verified monetary total is available.

The principal audit has ten intervention intents, ten recorded outgoing intervention messages and ten delivery results. Delivery is a receipt of submission to the intended root. Subsequent native history is required to establish compliance or useful progress.

## Reconstructable chronology

1. **2026-11-10 16:11:12 UTC — three-session task created.** The task retained a 180-second assessment cadence, unlimited check count and no added spending/release authority. MEMORY had been started accidentally and was to remain stopped pending a scoped decision about its preserved changes. The task payload and native operator messages carry the authority boundary.
2. **Test-selection corrections required repeated intervention.** Audit sequences 290–292, 307–309 and 319–321 retain the successive instructions to keep only necessary tests and rewrite defective designs before advancing integration. Later test-prune approval 575 establishes a scoped result; it does not establish completion of all M6 obligations.
3. **CLOCK source review 653 returned REVISE.** Two continuity tests required correction. Two cleanup properties were then described as unobservable through the approved public interface. The candidate had compile-only evidence; runtime acceptance remained open.
4. **Assessment 123 attempted resumption.** Intervention `5dcae7c2-b3ba-4185-a043-0587d31dbafe` asked PROBLEMI5 to resume the current CLOCK revision and avoid reopening historical work. Its wording preserved limits but did not resolve their actual provenance.
5. **Assessments 124–150 accepted the allocation blocker.** PROBLEMI5 reported that generations 652 and 653 were terminal and their limits had expired. The supervisor repeatedly accepted that as sufficient to stop authorized work. It did not establish an operator deadline or exhausted resource.
6. **Assessment 151 corrected that premise.** Intervention `ecd82dd5-d32f-4c7f-97a6-58c39bfd3cba` required allocation-provenance verification. PROBLEMI5's record `clock-allocation-provenance654.md` states that the eight-minute and five-minute estimates came from its own plan and slot records and cited no explicit operator deadline. It reports no demonstrated exhausted monetary limit. The corrections resumed and source review 655 approved them.
7. **Assessments 152–160 produced further local work.** The supervisor directed the fresh runner, its three failure controls, the user invocation, and a causal assessment of the remaining cleanup gaps. Runner controls 658 passed. Invocation 659 exited 1 after five passing cases; cleanup was UNVERIFIABLE and two later cases were NOT_RUN. Evidence review 660 returned REVISE.
8. **Proposal 662 identified feasible test-only work.** Read-only snapshots of existing accepted fields could establish refusal atomicity. A fixed diagnostic runner mode could execute the modified cleanup plus continuity-loss and canonicality without replaying five valid cases. The combined actual parent-latch/ACKED transition required a product-boundary change outside the declared test-only rewrite scope. Plan/source reviews 663 and 665 approved the test-only delta.
9. **Diagnostic 666 and final review 668 established a limited result.** Eight accepted-state comparisons passed; continuity-loss and canonicality passed; an altered receipt was rejected before child launch; process groups and staging were cleaned. Aggregate exit remained 1 because the combined parent-latch/ACKED property was still UNVERIFIABLE. Prior archive byte preservation and broader lifecycle closure also remained unverified.
10. **Assessments 161–269 repeated the pending decision.** The supervisor did not produce a new operational result during this run. It repeatedly reported the same product-scope decision and archive uncertainty. Audit sequence 2110 records a task-level block only at 2026-11-11 08:47:31.030625 UTC.
11. **2026-11-13 11:08:12 UTC — operator-requested interruption executed.** Principal audit sequences 5131 and 5132 record pause and detach. The three other discovered related roots were deactivated in the same stop operation. Collection found no remaining supervision cron entry. The final shutdown exports preserve the resulting paused/detached state.

For exact wording, use the complete native rollouts and the audit exports. The records `clock-cases-source-review653.md`, `clock-allocation-provenance654.md`, `clock-local-evidence-review660.md`, `clock-cleanup-correction-proposal662.md`, `clock-test-final-review668.md` and `clock-diagnostics666/verification666.json` are included under their original absolute-path members in the archive.

## Causal findings and confidence

### F1 — an invented authority blocker prolonged inactivity

**Established.** The lead's own estimate was treated as an operator restriction. Assessment 151 requested the missing provenance check; the lead acknowledged the mistake and resumed work. The causal chain is supported by the blocked execution run, intervention delivery, native response, allocation record 654 and subsequent source approval 655.

The supervisor should have reconciled the authority source at the first reported stop. A lack of a successor slot record establishes the absence of that record. It does not establish exhausted operator authority.

### F2 — execution results and task lifecycle permitted an unchanged loop

**Established for the legacy path.** `Store.execution_result` in `shared/supervision/store.py` validates types, outcome, generation, task/binding eligibility and running status, then updates the execution and audits the result. It returns `task_state_changed: False`. It does not derive a task-level transition or verify the semantic truth of a blocker.

`Scheduler._claim` in `shared/supervision/scheduler.py` considers active due tasks, binding status, in-flight executions and the configured count cap. Finished executions with outcome `blocked` do not remain in its in-flight set. With `max_checks: null`, another due assessment remains eligible. The incident demonstrates that this transition repeated for both blocked runs.

`Store.task_state` provides a separate explicit block operation requiring remaining obligations and a resumption-condition string. It does not authenticate those assertions. The audit labels task-block as actor `operator` because the API defaults that field; the supervisor actually issued this call in assessment269. Audit actor text must not be treated as authenticated human provenance.

### F3 — current instructions describe the required behavior, but historical loading is unverified

**Established at collection; historical availability unresolved.** The captured current policy tells the supervisor to wake an idle unfinished lead when feasible, treat supervisor estimates as reassessment points, avoid repeating unchanged blockers, and distinguish delivery from useful progress. These collection-time bytes do not prove which policy version was loaded at each incident assessment. A subsequent investigator must establish that from contemporaneous native context and source history before attributing the incident to noncompliance with that exact policy. Regardless of policy loading, the retained execution sequence demonstrates that bookkeeping accepted repeated blocked results without stopping the legacy task. More prose alone would not change that executable transition.

### F4 — local approvals obscured unresolved end-to-end obligations

**Established as a supervisory management failure.** Final review668 explicitly approves a scoped test/harness delta and lists unresolved full CLOCK and broader lifecycle claims. The supervisor's memory also retains B2, capacity and real launch as open. Repeated reports did not translate those obligations into a verified continuation or a concise operator decision. The existence of legitimate scope limits does not prove that every independent path was blocked; that must be investigated against the original mandate.

### F5 — tests were implemented before observability was resolved

**Established for the recorded CLOCK sequence.** Source review653 identified that some required observations could not be made through the chosen seam. Proposal662 later separated test-only state observation from a missing public integration path. Requirements-to-test mapping must include whether an observation is actually reachable, alongside test necessity and independent expected results.

### F6 — the asserted failure of all symbolic controls is broader than the evidence

**Established boundary.** These incidents use `AI_KIT_SUPERVISOR_EVENT`, the legacy SQLite scheduler and model-submitted results. The repository separately documents Python-owned persistent goals and their executable acceptance. The available incident records do not establish that this three-session task was bound to that goal controller. Audit configuration before attributing these 269 legacy events to persistent-goal enforcement.

The measured gap is that the active legacy controls admitted correct bookkeeping while semantic supervision stalled. Whether the persistent-goal path would resolve, repeat or misclassify this exact scenario remains unverified and needs its own replay.

## Proposed investigation and repair scope

The subsequent implementation task should establish which controller was expected to own continuation, what was installed, and which acceptance contract was actually bound. It should then design controller-owned handling for repeated unchanged blockers, exact authority provenance and missing progress, while preserving legitimate waits and operator constraints.

Required design questions include:

- What machine-readable obligation identifies the unfinished result across assessments, reviews and compaction?
- Which evidence establishes operator-supplied deadlines, spending limits and scope decisions, and how is it distinguished from agent-authored estimates or an unauthenticated actor field?
- What observable delta justifies another paid assessment or lead wake after an unchanged blocker?
- What controller action follows repeated blocked reports, and which operator notification contains the concrete requested decision, proposed change and resumption condition?
- How does the system continue independent authorized work while a narrower branch requires a product-scope decision?
- How do assessment completion, component acceptance, full task acceptance and supervisory shutdown remain separately verifiable?
- If persistent goals are the intended solution, what migration and explicit acceptance binding is required for these exact sessions? Do not silently retrofit a legacy task and claim its history was protected.

## Acceptance requirements for a future repair

1. Reproduce the legacy loop from retained state/results in an isolated environment. Identify the first transition at which intervention or escalation should have occurred. No live sessions or paid model calls are needed for deterministic reproduction.
2. Demonstrate that worker-estimate expiry alone cannot be recorded as exhausted operator authority. An actual operator deadline must still stop admission according to its contract.
3. Replay both the 27-result and 109-result runs. The repaired policy must produce a bounded, documented reaction with useful evidence or an actionable operator decision. Repeating a message or recording another successful API call does not satisfy progress acceptance.
4. Preserve uncertain-delivery handling, exact-session identity, pause/detach fences, observation-only scope and legitimate long-running work. A corrective send must not duplicate a pending instruction.
5. Require test observability and distinct-risk justification before implementation. Keep only necessary tests; discard defective test designs and rewrite them from the required behavior and independent expected results. Existing tests have no preservation privilege merely because they already exist. Preserve valid evidence, failed attempts, non-PASS cleanup obligations and scope restrictions.
6. Verify the actual final user entry point and an independent acceptance oracle. Correct receipt hashes establish integrity; they do not establish arbitrary task success.
7. Give each claimed enforcement property a real failure-path test. Cover malformed/unsubstantiated blockers, stale evidence, restart, compaction/history loss, exhausted true limits and successful continuation after a false blocker is corrected.
8. Verify the chosen mode in one bounded native scenario after deterministic checks. Explicitly report remaining semantic/model-judgment uncertainty and actual spending information when available.

## Constraints and unresolved facts

- The operator has stopped supervision. This brief grants no resumption, new spend, provider effects, product scope extension, installation or release authority.
- Existing worktree changes predate this brief. Source snapshots in the package are collection-time bytes. Matching installed and repository supervision files at collection does not independently establish their bytes at every incident timestamp.
- Current installed and repository `store.py`, `scheduler.py`, `control.py`, `POLICY.md` and `COMMANDS.md` match byte-for-byte at collection. Their digests are in the manifest.
- Native metadata identifies descendants, but some recorded rollout paths are absent. The manifest and missing-path report define what was actually retained.
- Raw native rollouts may repeat or rotate history. Do not sum duplicate messages or token counters as unique work or billed consumption.
- No numeric cost estimate should be invented from the unknown billing data.
- The operator reports completing work manually after the supervisor failed. The subsequent completion and exact human changes are outside this brief's verified acceptance record.
- Prior archive byte preservation is an evidence gap. Lack of an independent before-image is not proof that the archive was corrupted.

## Delivery verification

The deliverable must include this brief, the log archive, per-file digests, all-table exports, complete available native root/worker logs and an explicit missing-evidence inventory. Verify every archived member against the manifest and retain the verification result. Independently review the brief's framing, numerical claims and evidence references. Any incomplete archive verification or missing artifact must be disclosed before delivery.

Collection retained 30,948 principal archive members (12,976,373,976 uncompressed bytes; 7,712,682,964 compressed bytes). The metadata identifies 689 native threads. There are 314 missing historical native paths, listed individually; rotated files may retain some related history. One REMOTE rollout changed during capture, identified in `collection-changes.json`. Its archived bytes are a collection-time capture, not a claim that the live file was frozen.

Verification completed successfully: all 30,948 principal and 83 supplemental archive members match their recorded byte lengths and SHA-256 digests. All four SQLite backups were independently checked against their complete table exports. The fresh brief review is retained in [brief-review.md](/home/mal/.local/share/mrcall-operational-evidence/2026-11-13/supervision-failure/brief-review.md). No implementation or baseline advancement was performed.
