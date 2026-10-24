---
status: completed
---

# Automatic av short-answer exemption

## Approved intent

Implement the [brief](../briefs/2026-10-24-av-short-answers.md): up to 300 raw
Unicode code points skips classification and automatic av on all three systems;
301 and above keeps semantic selection. Manual av and existing authority remain.

## M1 — Implementation and deterministic native proof

Lead owns the Python hook, selector policy, Python tests and Codex/Claude native
fixture. A bounded execute worker may own only OpenCode protocol.js, its Node
tests and native fixture; preserve others' edits and deliver within 180 seconds.

1. Add the early length exemption before selection/context diagnostics, using
   matching code-point counting. Exempt drafts must never call a selector or
   consume a later eligible same-turn application.
2. Cancel/invalidate pending old selection when a current short draft supersedes
   it; suppress stale av delivery. Keep normal prompt/session-end cancellation,
   canonical body, replay, once-per-turn and above-limit negative selection.
3. Update selection-intended fixtures to explicit above-limit reports. Add the
   operator example, 300/301, Unicode, multiline, short-to-long and stale cases.
   Native local-provider runs prove zero selectors/continuations at 300 and the
   existing path at 301 on Codex, Claude and OpenCode. No paid model acceptance.
4. Run affected Python/Node suites, actual native fixtures and installer checks
   as needed for changed assets; obtain fresh M1 integration review.

## Documentation and closure

Lead reconciles current automatic-av contract, README, runtime/reread support,
selector cost and historical evidence. Historical dated briefs/plans retain
their original boundary; current docs explicitly supersede it. Active context
remains a current snapshot; archive only displaced narrative verbatim if any.
Invoke doc-end/doc-critic, current checker receipts and separate final review.
Declare active-to-completed transition for checker finalization only after review.

## Integration and installation

Work only in the detached isolated worktree until verified approval, so installed
main-checkout Python symlinks cannot expose a partial change. Commit the reviewed
candidate, fast-forward the clean main checkout, then refresh only kit-owned
installed assets through the installer with backups. Verify installed hashes and
short-callback CLI behavior; native reload/trust limits remain explicit.
No push/public release, model/credential changes, operational clones or restarts.

## Rollback

Before integration, discard only this isolated task's changes. After integration,
restore only its owned assets/registrations from recorded backups; preserve
foreign WIP and other hooks. Do not restore the retired completion certificate.

## Completion

Keep status active until reviewed checker finalization. Remaining required
evidence: M1, native boundary/no-selector proofs, docs critic, final approval,
main integration and installed verification. Public release is outside scope.
