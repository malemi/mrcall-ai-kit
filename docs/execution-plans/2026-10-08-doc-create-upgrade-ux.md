---
status: completed
brief: docs/briefs/2026-10-08-doc-create-upgrade-ux.md
---

# Direct documentation upgrade delivery

## Ownership and dependencies

Lead owns migration helper, doc-create workflow/copy, focused acceptance runner,
affected durable documentation, installed workflow refresh and closure evidence.
Unrelated completion-boundary edits remain untouched. Brief review is retained
at `/tmp/mrcall-upgrade-ux/brief-review.md`; approved bytes are retained beside it.
This plan requires a fresh approval before implementation.

## M1 — Correct the default and recovery contract

1. No report returns `compatibility.status: not-evaluated`; explicit deferral
   retains its existing status. A supplied report still takes the strict path.
   Do not infer supported clients or run probes automatically.
2. Route supplied-report failures to evidence correction, mechanical failures
   to target-documentation repair, and ownership/setup failures to bounded
   layout/setup resolution. Never send every refusal to a runtime collector.
3. Make doc-create's default a direct inspect/repair/dry-run/apply/check path.
   Explain optional strict reports and legacy deferral without requiring either.
   Routine metadata/link/inventory fixes within the target require no new
   approval; preserve semantic meaning, history and managed ownership.
4. Retain efficient staging and raw existing symlink targets. Add focused CLI
   coverage for no-report apply/rollback, strict supplied-report refusal,
   mechanical repair/retry, foreign ownership, and opaque child application data.
5. Fresh M1 integration review before dependent installed refresh.

## M2 — Installed delivery and documentation closure

1. Inventory only known installed doc-create workflow paths and ownership
   records. Back up preimages and refresh only symlinks or exact kit-owned
   copies, updating matching ownership metadata. Preserve foreign files,
   configuration, agent activation and unrelated installed artifacts.
2. Run the installed helper/checker CLI on disposable recognized v8 leaf/meta
   fixtures: inspect, dry-run, apply, check, exact rollback, and refusal/retry.
   Retain full commands/output, target hashes and transaction evidence externally.
   No downstream migration or native client trial is authorized.
3. Reconcile doc-create, documentation-harness, runtime support, changelog and
   active context. Preserve historical text. Record the supersession of the
   earlier mandatory compatibility-acquisition direction without asserting
   missing prior evidence. Update only this task's work trace.
4. Invoke doc-end and explicit doc-critic over affected documents plus living
   context shape. Initialize development completion bound to this brief/plan
   and milestone snapshots. Record actual reviews and focused CLI output;
   fresh final review precedes completion check/finalize. Native and broad
   suites remain deferred; no release is implicit.

## Rollback

Source edits are local and can be reverted independently. Installed copies have
external byte/mode backups. Disposable fixture transactions must roll back
exactly; target documentation repairs remain separate from the three-file
managed transaction. A supplied failing report never silently falls back.

## State

Brief and plan APPROVED; raw verdicts and immutable approved bytes are retained
under `/tmp/mrcall-upgrade-ux`. M1 APPROVED after independent source review and
CLI evidence. Five installed-helper CLI acceptance scenarios passed in 2.242s;
raw command/output records are in `m1-cli.jsonl`. Supplied malformed reports and
combined evidence/deferral flags were independently refused without writes.

All three installed doc-create entries resolve through recorded kit-owned
symlinks to current workflow source; no installed copy or configuration mutation
is needed. The shared workflow and Codex byte copy match. M2 also exercises
meta inspect/dry-run/apply/check/rollback with an opaque child FIFO; all five
expanded installed CLI scenarios passed in 2.938s (`m2-cli.jsonl`). M2's actual
review is retained as `M2-review.md`; final completion uses the task-bound
record `doc-create-upgrade-ux-2026-10-08`. Native/broad suites remain deferred;
no downstream migration or release is performed. Intended status transition
after final approval: completed.
