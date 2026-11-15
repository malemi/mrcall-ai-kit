# Automatic intervention after stalled failure

## Intent

The persistent goal controller repeatedly woke a lead and supervisor after failed
acceptance while both merely reported the same blocker. Implement a symbolic
activity check that automatically injects a corrective prompt into the exact
lead session after observed inactivity following failure. An agent's report
alone must not establish concrete work or suppress this intervention.

## Scope and constraints

- Extend the Python-owned Codex persistent-goal path, native observation and its
  durable outbox/state; preserve legacy supervision behavior.
- Observe structured public native events, excluding private reasoning. Treat
  incomplete observation as unknown, never as absence of activity.
- Distinguish completed report/control-only turns from actual tool activity;
  activity is evidence of execution, not proof of useful progress or success.
- Respect active sessions/work, pending/uncertain delivery, generation fences,
  operator stop, deadlines, wake allowances and all existing authority limits.
- Persist intervention identity and result across restarts; prevent duplicate
  injection while delivery or recipient execution remains pending.
- Corrective text requires a new authorized step or a precise indispensable
  operator decision; it grants no new spending, release or failed-FULL retry.
- Install reviewed changes locally and resume the existing PROBLEMI3 goal only
  after checks. Preserve its checker, candidate evidence, counters and failures.
  Public release and unrelated cleanup are outside scope.

## Acceptance

1. An observed completed lead turn after failed acceptance with no concrete
   activity automatically produces a corrective lead event, without requiring
   a supervisor's discretionary intervention or parsing prose.
2. Report-only activity reproducing the incident cannot defeat the detector.
   Concrete execution, active work, missing history, and pending delivery are
   distinguished and recorded accurately.
3. Restart, lost acknowledgement, stop/resume and allowance boundaries preserve
   deduplication and fencing. A corrected candidate can still pass normally.
4. Installed CLI/socket execution proves detection and actual injected content;
   checks include negative cases and unchanged failure, using free fixtures.
5. Required reviews/documentation closure complete, then the exact operational
   goal is resumed and its first observation/delivery is verified. This proves
   activation and mechanics, not restoration or guaranteed model ingenuity.

## Assumptions

The native public history exposes tool/turn identities sufficient for conservative
classification. Where it cannot distinguish control-only execution reliably,
record unknown rather than claim no work. Existing operator constraints persist.
