---
status: completed
---

# Goal stasis intervention

Approved intent: [brief](../briefs/2026-11-01-goal-stasis-intervention.md).
Prior work in this dirty checkout is preserved. Evidence and approved versions
live under `/tmp/mrcall-ai-kit/goal-stasis-20261101/`.

## M1 — Observation and automatic corrective delivery

Owner: execute agent for implementation/tests; lead integrates and verifies.
Dependencies: approved brief and plan, existing native transport/outbox.

- Extend exact-event native reconciliation to return a compact public activity
  classification for the matched completed lead turn and any newer turns.
  Consume complete native pages up to the event anchor; missing/malformed data
  means unknown. Never infer activity from prose, reports or private reasoning.
- Recognize structured work tools as execution signals. Recognize direct goal
  control calls and narrowly parsed, side-effect-free Python goal-client report
  wrappers as bookkeeping. A mixed wrapper must not be discarded as bookkeeping.
  Other commands count as observed execution, not useful progress. Unknown event
  shapes remain unknown. Active work defers correction.
- Attach the observation to the durable consumed event. When acceptance remains
  failed and the latest consumed lead event has no work, inject a corrective
  prompt through the existing reserved outbox instead of a generic lead wake.
  Include observation evidence in the event/inspection state. Reports cannot
  satisfy the detector. Missing observations use the existing generic path,
  explicitly marked unknown, rather than falsely claiming stasis.
- Use existing pending-delivery reconciliation and generation admission for
  corrective events. A consumed correction with continued inactivity is visible
  and yields a subsequent correction on the next eligible cycle; never an
  in-flight duplicate, a new authority grant or an automatic terminal state.
- Tests exercise report-only, mixed command, actual work, active, unknown,
  pagination, restart/lost ACK, stop/resume and wake allowances. Existing goal
  acceptance behavior remains intact. No checker edits or lifecycle bypass.
- Fresh milestone reviewer checks integrated source and actual test evidence
  before installation or dependent operational work.

## M2 — Installed checks, documentation and activation

Owner: lead. Dependencies: approved M1.

- Install dormant kit assets using the existing installer. Exercise installed
  setup/service/client through a free native socket fixture: failed acceptance,
  report-only lead turn, corrective delivery, pending deduplication/restart,
  actual work and corrected-candidate success.
- Reconcile `docs/supervision.md`, shared policy/command reference where needed,
  active context and work trace. Keep measured mechanics separate from semantic
  model judgment; legacy supervision has no new detector. Preserve displaced
  living text verbatim in the archive.
- Run doc-end, mechanical/focused checks and explicit doc-critic including
  unchanged affected contracts and living-context shape. Obtain separate final
  review before baseline finalization. No public release or unrelated commits.
- With existing goal stopped, back up changed installed runtime assets; refresh
  only reviewed runtime files and restart the owned user goal service. Preserve
  config, database, checker bundles, candidate, receipts and counters.
- Resume exact goal `problemi3-restoration-20261030`, exact lead
  `01a17ded-ec54-7fc2-a660-887f43dccbee`, supervisor
  `01a181e1-f7cd-7a50-8111-c25e0bfd044d`. Retain cap60/target8/hard13.25,
  no new paid admission, no consumed FULL retry, pending private installation
  authority. Verify first actual observation/delivery; report remaining product
  acceptance honestly. Activation is an operational follow-up, not proof of FULL.

## Rollback

Stop the goal using its current generation, stop the owned user service, restore
backed-up code files and restart with the same durable state. Do not reset outbox,
reservations, failures or checker. Additional JSON observation fields must remain
backward-compatible and ignored by old code. Resume only within operator mandate.

## Progress

- Brief and plan approved; immutable artifacts and verdicts retained.
- M1 implementation, installed socket checks and independent milestone review
  cover the original report-only case and active/unknown/work boundaries.
- Initial live activation exposed two false negatives: conditional summaries and
  finite reporting loops were counted as execution. Both actual captures are
  retained in the evidence directory. The pure-report grammar repair and mixed
  work regressions passed independent M1 re-review; original failure/review
  evidence remains retained.
- Reviewed runtime is installed in the existing local service. Exact PROBLEMI3
  goal resumed as generation 7 with unchanged checker, scope and accounting.
  Its first corrected live tick classified the lead turn `no_work` and delivered
  `stasis_correction` event `00fd45c8-e223-4e1f-9cb1-37f7a9e21f74` to the exact
  lead. `live-final-activation.json` and `live-final-first-tick.json` retain
  the real observation, prompt and delivery receipt.
- Documentation reconciliation and the first critic pass are recorded. The
  final combined focused check, refreshed critic and separate final review
  qualify the repaired version before checker finalization transitions this
  plan to completed. Product restoration and semantic lead compliance remain
  outside this implementation's demonstrated result.
