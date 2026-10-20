# Restrict runtime completion review to declared work

The operator's ordinary clarification and status answers are blocked and emitted
again because the adapter treats every Stop as work delivery. Moving the same
mandatory review earlier would retain unnecessary bureaucracy for conversation.
The operator explicitly requests correction, not another diagnosis.

Restrict mandatory runtime review to an explicit delivery declaration for the
current task/turn (`bind --delivery`), or an explicit checked-exec invocation.
Merely tracking an open task/binding never declares delivery and must not impose
review on its clarification/status turns. Delivery never propagates to another
turn. An unbound conversational turn must end normally, with
no review command, continuation prompt or duplicate final answer. Never classify
free-text intent with regex or pretend the runtime knows semantic task scope.
Existing whole-assignment instructions remain in place; unbound work is not
promoted to independently enforced completion. State that coverage boundary.

Preserve the existing strict validator for declared work: no second-pass auto
allowance, stale/foreign/mismatched receipts refused, explicit task check required,
legitimate limited stops and bounded failure. Do not claim an unbound answer is
certified complete. Re-enable only the corrected scoped registration after
validation, preserving foreign hooks and native trust ownership.

Scope: ai-kit and owned installed adapter only. No Octopus/engine/cron/downstream
changes, restarts or publication. Use an isolated worktree because installed
symlinks otherwise expose unreviewed edits. The broken blanket registration has
been removed as immediate containment; containment alone is not delivery.

Acceptance: deterministic tests and actual installed Codex prove an unbound plain
exec and actual TUI produce one answer/one Stop with zero review/continuation;
checked exec and an explicitly bound plain exec still refuse omitted review.
Retain existing valid-receipt and real bound-harness regression coverage. Cover
clarification with an open tracked binding, followed by explicit current-turn
delivery that refuses missing review. Four
native processes maximum, 60 seconds/2 MB each, deterministic loopback and no
credentials/paid inference. Follow fresh reviews, doc-end, critic, final review,
checked commit and safe fast-forward integration/owned installed update.
