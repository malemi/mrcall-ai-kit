---
description: Bootstrap or explicitly migrate a repository to the AGENTS-only v9 documentation harness.
allowed-tools: Bash(git *) Bash(ls *) Bash(mkdir *) Bash(cat *) Bash(python3 *) Write Edit
---

An explicit bootstrap or upgrade request authorizes the managed migration and
routine local documentation repairs needed to complete it. Complete that work
without asking the operator to approve each mechanical correction. Write in
English; preserve knowledge and operating rules. Ordinary startup, closure or
a version mismatch does not authorize migration.

## Preflight

This workflow implements harness_version = 9. Read an existing docs/.doc-profile
completely. v6/v7/v8 require a requested upgrade; v9 may be reapplied idempotently.
Newer profiles require newer installed tooling. Earlier or ambiguous layouts
are unsupported; preserve them rather than guess ownership. Require Git with
an existing commit; do not create a commit without authorization. Preserve an
existing profile's mode/settings; choose leaf or meta for fresh bootstrap.

Resolve doc-migrate.py, doc-check.py, AGENTS.block.md and legacy/ under
${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}. The helper owns managed layout
changes. Do not reproduce managed prose or manually delete CLAUDE files. A
source-tree run may use shared/scripts/doc-migrate.py with the absolute
shared/templates/AGENTS.block.md as MRCALL_DOC_HARNESS_TEMPLATE.

Stop on missing external setup or unresolved ownership. Installation symlinks
do not authorize reading/editing AI-kit implementation, relaxing policy,
changing client configuration or inventing evidence during a downstream task.
Use documented preflight/recovery; kit maintenance needs a separate kit task.
Preserve foreign/customized managed files, ambiguous markers, symlinked managed
paths and obsolete sidecars. Automatic CLAUDE retirement requires known template
bytes; customized files follow the explicit adoption-consent path below.
Escalate only unresolved meaning, ownership or authority.

A helper refusal is diagnostic input, never by itself a reason to finish the
session. For any unresolved decision, explain the concrete issue, prepare the
smallest reviewable resolution and ask the specific authorization question.
Remain pending for the answer and continue afterward; do not report a terminal
refused upgrade with an unspecified "decision pending".

Runtime compatibility reports and client experiments are not prerequisites for
this deterministic file operation. Without a report, compatibility is
not-evaluated; no measured client support is claimed. Do not ask for an escape
flag or launch probes to unblock an ordinary upgrade. If evidence validation
is separately requested, use --compatibility "$compatibility_report"
consistently on inspect, dry-run and apply. Supplied reports must validate and
must not silently fall back. Optional installed doc-compat.py --help describes
acquisition for that separate task. Legacy explicit --allow-unverified remains
supported; do not combine it with a report.

Run inspection with the absolute repository root:

```sh
python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-migrate.py" inspect --repo "$repo_root" --json
```

Inspect writes neither target content nor a transaction. A valid staged layout
returns ready: true. Staging references application/child trees instead of
copying them. Ancestor/user instructions are observations, never edit targets.

## Resolve target documentation in one pass

Read structured next_action and all mechanical_validation.violations together.
repair-target-documentation is actionable preflight, not an external
prerequisite or another approval request. Correct routine local defects
according to their meaning, then retry inspect. Do not stop merely because
the helper returns nonzero.

### Customized CLAUDE.md: propose, ask, resume

When next_action.operation is request-claude-adoption, the helper returns
state: awaiting-authorization and the exact source sha256. Read CLAUDE.md and
AGENTS.md completely. Prepare a concrete preservation mapping or diff: project
rules move outside the managed AGENTS block; obsolete harness prose is retired;
unresolved conflicting rules receive a specific question. Do not copy the old
harness protocol into the project rules. Keep the current files unchanged
while presenting the proposal.

Ask: "May I preserve these project instructions in AGENTS.md and retire this
specific CLAUDE.md through the migration helper, retaining its original content
for rollback?" Include the actual proposed changes, not merely this template.
The upgrade request alone does not authorize customized-file adoption. Reuse
explicit consent already given for this exact proposal/file; do not ask twice.
Do not end the task as refused while waiting for this answer.

After consent, reconcile the approved project content and invoke inspect,
dry-run and apply with --adopt-claude-sha256 "$approved_claude_sha256". Use the
helper-returned hash, never a newly computed replacement to bypass a stale
consent. A changed source requires a renewed proposal. The helper validates the
hash and saves original CLAUDE bytes/mode in the transaction before retirement.
Never manually delete or replace the customized file to make it recognizable.
This option cannot authorize symlinks, other instruction collisions or invalid
layouts. Project-prose reconciliation remains outside managed rollback; retain
its preimages separately. Explicitly verify the preservation mapping with
doc-critic along with the affected documentation before declaring completion.

- Update obsolete documentation links to the current instruction entry. A link
  to removed managed CLAUDE is a local repair; do not recreate that file.
  Preserve historical accounts; correct link targets without rewriting history.
- Read invalid plan/session metadata with its content and choose the actual
  lifecycle state. Plans allow planned|active|blocked|completed|superseded;
  session memories allow open|closed. Never mark unfinished work completed.
- Reconcile inventory with actual ownership. A temporary worktree may belong
  in inventory_ignore; an owned service belongs in the index. Decide from
  evidence, never hide unknown repositories merely to pass.
- Resolve index overflow by removing duplication or routing durable detail to
  its proper doc while preserving every operating rule. Never raise limits or
  discard guidance merely to silence the checker.

Keep project-prose repairs separate from the managed transaction. Record their
changes and recovery boundary: the helper rolls back only AGENTS, CLAUDE and
profile. If evidence cannot determine a repair, ask the concrete unresolved
question. Do not ask the operator to repeat an authorized upgrade.

## Prepare only missing project content

For fresh bootstrap prepare scoped AGENTS.md, docs/README.md and
docs/active-context.md. Preserve existing bytes; add only verified facts. Root
AGENTS owns inventory; docs/README routes transversal docs. Active context needs
a real ancestor baseline and only State now, Unresolved and Next. Never invent
verification. Create docs/execution-plans/ and docs/briefs/, with .gitkeep when
empty. Add docs/sessions/ to .gitignore; do not create that runtime directory.

Each required routing doc has exactly one inline declaration:

```markdown
<!-- doc-scope:start -->
Scope: <verified purpose and ownership boundary>
<!-- doc-scope:end -->
```

The helper publishes the managed block/profile. Fresh profiles use version 9,
schema 1, explicit mode and index_file = AGENTS.md, without harness_file.
Add build/smoke settings only from verified knowledge. Substantial work keeps
its dated brief/plan pair and valid lifecycle status.

For existing docs reconcile affected routing and references to retired CLAUDE,
then explicitly invoke doc-critic over affected changed and unchanged docs.
Use doc-end's lead-owned current/history decision for active-context repair;
preserve historical passages verbatim in the archive. Helper success does not
establish semantic review. Prose edits remain outside its managed transaction.

## Apply and verify

After inspect is ready, run dry-run:

```sh
python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-migrate.py" dry-run --repo "$repo_root" --mode "$repo_mode" --json
```

Require ready: true. Choose a new absolute transaction directory outside
repository content or below its worktree Git directory, with an existing parent.
Preserve it for recovery, then run:

```sh
python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-migrate.py" apply --repo "$repo_root" --mode "$repo_mode" --transaction "$transaction_dir" --json
python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-check.py" --repo "$repo_root" --startup --json
```

The helper validates before mutation, publishes the profile last and removes
recognized managed CLAUDE or an exact custom file explicitly approved through
the adoption-consent path. For interrupted migration inspect the saved
manifest and invoke rollback when recovery is required:

```sh
python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-migrate.py" rollback --repo "$repo_root" --transaction "$transaction_dir" --json
```

Rollback restores managed bytes/modes and refuses unrelated later edits.
Hooks, global config, commits and release remain outside bootstrap authority.

## Output

Report Doc-harness v9: applied|unchanged|refused, target/mode, actual changes,
mechanical result, compatibility status and transaction path. Distinguish
managed rollback from prose recovery. After verified layout continue the
original task when pending; otherwise Next: doc-start. Report unresolved
blockers without turning routine repairs into permission requests.
An unanswered authorization question is a pending task, not a completed
refusal. Name the concrete proposed action and resume when the answer arrives.
