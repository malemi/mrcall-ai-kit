---
status: completed
---
# Deliver test-prune with documentation memory

Brief: ../briefs/2026-10-27-test-prune-skill.md
Evidence: `/tmp/test-prune-skill-20261027/` (retain all work artifacts).

## M1 — Skill and delivery

Lead owns one self-contained `shared/skills/test-prune/SKILL.md`, the explicit
Codex entry in `install.sh`, and discovery/documentation changes in README.md
and docs/documentation-harness.md. Claude/OpenCode use the existing shared-skill
sweep; manifest uninstall needs no new mechanism. No generated boilerplate,
new feature switch, custom test framework or separate pruning command.

Skill workflow: resolve scope and applicable lifecycle; read scoped testing
memory and existing evidence; evaluate concrete risks; record remove/consolidate
reasons and consciously lost coverage before editing; preserve WIP and before
copies; validate meaningful functional scenarios and inspect full logs; close
through the existing harness. A transferred assertion must exercise its own
precondition, not pass because an earlier action already invalidated the state.
Keep failures and causes visible after later success. Never remove a failing
regression just to make a suite pass. No paid trial when deterministic evidence
suffices. Preserve all task-created temporary evidence.

Memory uses dated docs/test-audits records and a docs-index link on first use;
existing matching audit and brief/plan references are reused. Without a profile,
use a named scratch file. Audit-only requests return findings without edits.
Current durable testing facts and unresolved work go through doc-end; logs and
rationales stay in the audit/evidence rather than bloating active context.

Extend existing tests/test_codex_install.sh lifecycle loops to check the shared
skill bytes in all three install destinations, Codex directory discovery, owned
uninstall and foreign-copy preservation. Do not create standalone wording tests.
Fresh milestone review checks implementation and memory boundaries before local
installation. Retain immutable approved artifacts and raw reports.

## Verification and closure

Validate skill frontmatter with skill-creator quick_validate.py. Run the actual
existing installation test script once with a retained trace, covering copy and
symlink modes, shared-runtime delivery, ownership and removal. Re-run only affected
checks if findings require edits. No native model trial; directory availability
and content do not prove invocation or pruning judgment.

Install locally with the existing Codex doc-harness installer using skip for
existing assets, after checking role compatibility. Verify new skill content and
manifest ownership; preserve other assets and every existing session. A conflicting
foreign skill is preserved and diagnosed. Source availability is not described as
native discovery in an already-running client.

Apply doc-end over skill, README, harness contract, this brief/plan and unchanged
active-context shape. No unrelated history audit or archive edits expected. Record
mechanical, focused and explicit critic evidence, obtain separate final review,
then let checker transition active to completed. No commit or release.

## Rollback

Before-state manifest and original owned files are retained in the evidence root.
Restore only this task's edits if needed; remove only new task-owned assets. Never
reset the whole WIP tree or delete evidence. Installation records identify ownership.
