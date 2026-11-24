---
status: active
created: 2026-11-06
brief: ../briefs/2026-11-06-migration-sibling-links.md
---

# Migration staging sibling links

Brief APPROVED by `/root/migration_sibling_brief_review`, SHA256
ab9d5bb778b0a1e11fd6ffea8941e6cc832cc91ee8fc747a29b7be6502bc1e1b.

One lead implementation, at most15minutes plus10minutes focused checks. Ownership:
`shared/scripts/doc-migrate.py:validate_stage`, `tests/test_doc_upgrade_cli.py`,
and the migration staging paragraph in `docs/documentation-harness.md`.
Retain exact source/test preimages and original failing consumer dry-run.

Create the private temporary stage directly in `root.parent`, as a sibling root,
instead of nesting `repo` under a system temporary directory. Keep every existing
copy/reference, checker invocation, consent, preimage, publication and rollback
check. Parent creation failures return an explicit refusal; do not retry elsewhere
with false relative-link topology. Temporary tree cleanup owns only that stage.
No content or permission changes to parent/sibling repositories.

A sibling stage alone can resolve `../<original-repo>/CLAUDE.md` against the
live preimage. Add a migration-local postimage check using the unchanged checker's
same indexed Markdown/link parser. Resolve each link relative to its original
document location; when its resolved target is inside the target repository,
require the corresponding staged postimage to exist. Apply the same rule to
absolute and symlink-mediated references back into the target. Retain the normal
checker as well, merging additional dead-link findings; do not ignore any existing
violation. External sibling references still use the actual workspace context.

Tests use the actual CLI with two relative sibling references at different depths:
inspect and dry-run succeed without mutation; apply succeeds; actual checker stays
clean; rollback restores exact original bytes/modes; sibling bytes and temporary
cleanup remain unchanged. Missing external target still fails inspect/apply with
no transaction or source mutation. Parent-qualified, absolute and symlink-mediated
references to retired CLAUDE must refuse, while parent-qualified retained AGENTS
remains valid. Retain the existing retired-CLAUDE alias
negative and the complete existing migration CLI suite. Add a deterministic
permission-denial control for stage allocation without granting permissions.

Run configured kit pre-edit mechanical check and original migration suite, then
new focused tests, full migration CLI suite and kit mechanical check. Require
fresh integration review before the actual consumer helper invocation. The repaired
installed helper (source symlink) must then report only exact CLAUDE deletion and
ready=true on the real authorized consumer. Apply through helper with an external
transaction, verify startup clean and preserved AGENTS/profile/aliases. This is
real CLI acceptance, not a fabricated compatibility report.

Lead reconciles affected docs and living context, invokes doc-critic, then obtains
separate final assessment. No public release or baseline completion claim while
parent acceptance/checker obligations remain open. If the helper changes beyond
staging topology, stop and revise this scope. On failed consumer publication use
only helper transaction rollback; no manual deletion. Preserve dirty files and
all original failed receipts.

## Verified result

Revised plan APPROVED after adding staged-postimage protection. All11 migration
CLI tests pass, including actual apply/rollback and parent/absolute/symlink return
references. Independent integration review approves source and the supported
consumer action. Actual mrcall-cs dry-run/apply exit0; only CLAUDE is removed,
AGENTS/profile/aliases remain equal, original bytes/mode are journaled externally,
and consumer startup is clean. The original failing dry-run remains unchanged.
Scoped documentation semantic review is APPROVED; separate final assessment and
parent FULL/checker obligations remain open.

Final assessment verifies the applied consumer result and unchanged approved
implementation hashes, but returns REVISE for formal closure: completion binding,
current snapshot/evidence digest and parent acceptance remain unmet. This result
does not undo the applied retirement or source approvals. No baseline is advanced.
