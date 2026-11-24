---
status: completed
---

# Local goal controller plan

Approved brief: [local controller](../briefs/2026-10-30-local-goal-controller.md).
Brief reviewer local_goal_brief_review APPROVED, SHA256
112304cde010b079f84e345159c7f68a4fe4f548e55ad73fc037ab21e14d5281.

## M1 — Same-account runtime

Execute owns goal_setup.py, goal_service.py and goal_child.py. Add mode local as
setup default, current UID/GID/home defaults, owner-or-root path validation and
same-account socket control. Preserve explicit mode protected and previous
configuration compatibility (missing mode means protected). Protected mode keeps
its root/separate UID/namespaces requirements. Local service runs non-root with
-I; its children use the same UID and normal process groups, bounded runtime,
output and parent-death handling. Local does not claim descendant containment
across setsid or authentication of the operator against an agent. No root access,
user creation or privilege migration for local setup/service.

Do not change store/driver lifecycle, acceptance predicates, generation fences,
limits or uncertain delivery. Acceptance inputs stay immutable snapshots; local
ownership checks permit root-owned executables and current-user-owned bundles.
The same UID control endpoint permits administrative commands; document that
agent restrictions here are instructions, rather than a security boundary.

Verify owns a new local CLI/service/native fixture test, run as normal user:
failed candidate, idle wakes, restart with original event reconciliation,
corrected candidate and actual acceptance completion. Test bounded timeout/output
without privileged namespaces. Existing root suite explicitly selects protected
mode; retain its distinct security coverage. Fresh milestone review precedes
installation and activation.

## M2 — Installation, documentation and activation

After the install refresh, rerun the independent local lifecycle scenario against
the actual refreshed installed CLI/service under the normal account and isolated
state: failed acceptance, both idle wakes, restart reconciliation, corrected
acceptance and completion. This post-install check must pass before real activation.

Lead refreshes the installed supervision feature, both supervisor skills,
COMMANDS/POLICY and docs/supervision.md. Local is the normal deployment and the
existing protected mode is optional. Reconcile active context; preserve displaced
historical prose verbatim. Run mechanical gate, scoped doc-critic and separate
fresh final review, then finalize the active-to-completed plan transition.

Activation restores PROBLEMI3 current mandate, exact lead/supervisor IDs, existing
reviewed executable acceptance and spending constraints. Bind only actual
reviewed inputs; no invented fixture acceptance, paid retries or money-accounting
claims. Default cadence180s, no invented finite wake cap. A genuine missing
acceptance/authority remains an explicit activation prerequisite. Preserve legacy
end state until new activation is verified; no parallel legacy clock.

## Rollback

Stop the local controller using operator control, retain database/evidence and
pending delivery, and restore copied installed files if necessary. Do not replay
uncertain messages or reset reserved allowance. Live application sessions remain
under their existing account throughout.


## Verified implementation

M1 is APPROVED. Independent actual installed tests pass as the normal account:
local lifecycle and process bounds (2 cases), optional protected lifecycle and
old-mode compatibility (26 cases), and protected installation (4 cases).
Store, driver and acceptance semantics remain unchanged. Runtime evidence and
approved source versions are retained under
`/tmp/mrcall-ai-kit/local-goal-20261030/` and the independent verification logs
under `/tmp/mrcall-ai-kit/local-goal-controller-20261030/`.
Post-refresh installed verification and completion closure are tracked by task
`local-goal-controller-20261030`; real PROBLEMI3 activation requires its reviewed
read-only completion checker and preserves all prior paid-admission restrictions.
