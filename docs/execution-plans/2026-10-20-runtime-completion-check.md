---
status: completed
---

# Runtime completion check

Intent and acceptance: [approved brief](../briefs/2026-10-20-runtime-completion-check.md).

## Ownership and budget

Lead owns implementation, session signal and documentation reconciliation.
Reviewers own bounded external verdicts only: 90 seconds per new gate, 60 seconds
per affected repair, with concrete findings instead of repeated investigation.
No implementation fan-out. Preserve other work by explicit-path staging.

Native transport evidence uses an isolated home/workspace and loopback provider
with deterministic responses; no credentials or remote model calls. Each process
has a 60-second timeout and 2 MB output cap. At most six native processes in the
same evidence directory during initial capability discovery. Stop a failing
attempt, explain its observed cause, then repair only with new evidence. A paid
conversation requires a documented remaining fact that deterministic transport
cannot establish; initially at most one, 180 seconds and eight tool calls.

## M1 — Prove the runtime boundary before designing enforcement

After brief and fresh plan approval:

- Build a deterministic loopback-provider harness that runs the real installed
  Codex client with a vetted isolated Stop hook. Capture actual provider requests,
  native event output, hook payloads/decisions, versions and command settings.
- Measure Stop invocation, continuation identity, stop_hook_active behavior,
  repeated final attempts, missing/untrusted registration and available explicit
  failure signaling. No assumption that the native client hides an emitted draft.
- Start with native exec. If the actual evidence shows it cannot service Stop
  continuation, measure the user-facing TUI/app-server path in isolation before
  making an interactive claim. Never change the engine to create a passing result.
- Decide the smallest supported mechanism: mandatory runtime invocation plus a
  current per-session completion-review receipt, and an existing completion check
  for explicitly bound harness tasks. A second-pass flag alone never substitutes
  for required receipt validation. Bind current requests/reviews and reject stale
  or foreign receipts without scanning unrelated histories or guessing a task.
- Keep semantic judgment explicit. The model supplies its decision and evidence;
  the hook checks invocation, identity and applicable mechanical gate results.
  Do not infer task scope or truth from regex over user/assistant prose.
- Obtain fresh M1 integration review of actual native evidence and the resulting
  enforcement contract before dependent installation/activation work. If native
  capability contradicts the intended contract, revise the concrete design and
  get affected plan approval rather than relabel a weaker mechanism successful.

## M2 — Integrate, verify and deliver the measured mechanism

After M1 approval:

- Implement the measured hook and owned receipt/decision CLI, bounded continuation
  and explicit incomplete-failure outcomes. Cover accepted completion, legitimate
  limited stops, repeated bypass, stale/cross-session identity, malformed input,
  cleanup/resume and explicit task bindings. Never consume a receipt from another
  assignment or automatically pass at a retry cap.
- Deliver registration/status/removal with copy/symlink install tests; preserve
  all foreign hooks, owner text and existing evidence. Keep trusted activation
  distinguishable from file installation. No silent writes to trust stores.
- Exercise the shipped adapter through the actual client using the deterministic
  provider, including an agent response that deliberately skips the check.
  Required negative evidence is an observed runtime refusal/continuation, not
  an instruction assertion or a unit test against a hand-built payload.
- Obtain fresh M2 integration review. Reconcile README, runtime/re-read/harness
  contracts and living context from observed facts; preserve displaced narrative.
- Invoke doc-end, explicit doc-critic and completion coverage using current
  workflows, then a separate fresh final review. Retain immutable approved
  artifacts and actual raw results outside source. Finalize only reviewed
  baseline/plan metadata. Commit this task's verified paths; no release here.
- Prepare the concrete trusted-activation result before any indispensable operator
  trust step. Complete all independent work first; report the exact native trust
  boundary and remaining action if that is the only blocker. Never claim the
  operator's existing session is protected from an isolated fixture alone.

## Rollback and known limits

Use normal commits/reverts for kit changes; uninstall only owned hook entries
and files, preserving foreign configuration. Do not edit downstream protocols,
engine sources or cron, restart other sessions, or reconstruct unavailable old
reviews. An agent can still lie about semantic completion; a trusted runtime
receipt proves an executed check, not the truth of private reasoning. Explicit
operator interruption and actual resource limits remain valid stopping paths.

## Verified delivery and remaining activation

M1 measured four native Codex 0.163.0 processes and obtained APPROVED design
review. Stop continuation is real; a second-pass flag is not an allowance.
Untrusted hooks do not run. Plain exec exit0 cannot attest completion failure.

M2 obtained APPROVED integration review after seven zero-inference native cases
and 12 deterministic protocol/install tests. Actual sandboxed CLI submissions
cover complete and limited decisions; skipped or mismatched reviews are refused,
and absent native trust yields wrapper3. The actual TUI displays bounded failure.
The core, installer and strict wrapper are reviewed; semantic truth is not proved.
Raw reports, approved versions and evidence remain under
`/tmp/mrcall-ai-kit/completion-stop-20261020/` on the acceptance host.

The production acceptance allowance was seven processes, each 60 seconds and
2 MB, with zero paid inference; all seven are retained, no extra retries bought.
The earlier capability allowance used four of six permitted processes. Tests
that recheck retained evidence start no client. Review-worker inference is
separate from those zero-inference acceptance processes.

Documentation closure and final integration review govern the final source
snapshot. Native trust/reload on the operator profile is an explicit remaining
activation obligation, not a claim of live protection. All independent delivery
work must precede that indispensable native approval. No current session or
engine is restarted; ordinary trust and subagents are not promoted from fixtures.
