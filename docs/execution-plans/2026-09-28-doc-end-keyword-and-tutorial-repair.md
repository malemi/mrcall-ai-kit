---
status: completed
brief: docs/briefs/2026-09-28-doc-end-keyword-and-tutorial-repair.md
---

# Execution plan — restore installed documentation checks

Brief: [`2026-09-28-doc-end-keyword-and-tutorial-repair.md`](../briefs/2026-09-28-doc-end-keyword-and-tutorial-repair.md).
This repair was discovered by semantic review during `doc-end` after the
cross-runtime re-read port was committed.

## M1 — Keyword check available to installed workflows

Install `shared/scripts/doc-keywords.py` to the kit-global home inside the
`doc-harness` gate. Update the shared `doc-end` command and its Codex workflow
mirror to invoke that installed path; preserve byte equality between them.
Update installer help. In the script, distinguish Git exit 1 from
`merge-base --is-ancestor` (normal non-ancestor fallback) from other Git
errors. Use the valid baseline range when possible, otherwise the latest ten
commits, including a repository with fewer than ten. Extract subjects without
their abbreviated hashes. Honor `--docs-only`.

Verify copy and symlink installs, manifest uniqueness, uninstall, and an
installed CLI invocation from outside the kit checkout. In temporary Git
repositories, check valid and invalid baselines, the short-history fallback,
an invalid explicit `--range` error, and absence of hash tokens. Run the
existing doc-harness install test and a
focused new CLI test. A fresh reviewer checks M1 before M2.

Review: `APPROVED` on 2026-09-28. The reviewer reran the three CLI tests, the
temporary-HOME install test, workflow mirror comparison, and whitespace check.
Two advisories are incorporated before final review: text output for
`--docs-only` must name only docs, and a valid non-ancestor baseline gets a
direct CLI test.

## M2 — Named tutorial coverage and semantic reconciliation

Make the named-capability branch of `ai-tutorial.sh` require the same installed
proof as the list branch. Distinguish a known but uninstalled capability from
an unknown name. Replace the tutorial test's source-tree copy with a disposable
HOME and test installed, absent, and unknown names through the CLI.

Repair the source-backed documentation findings from the `doc-end` critic:
the README's OpenCode command labels; the tutorial's OpenCode `/sc`, router
sweep, hook state, and scope-guard claims; the Claude `/sc` and router flag
claims; and the re-read brief's OpenCode hook attribution and enforced-pass
overclaim. Keep dated historical client evidence explicit where the disposable
traces have been removed. Run the repository shell/Python tests, generated
agent check, whitespace check, and documentation gate. A separate final
reviewer checks installed CLI behavior, source/docs agreement, and the test
evidence before the plan closes.

## Boundary

Do not install into the operator's real HOME. Do not modify the unrelated
concurrent delivery-gates brief. Claude Code client QA for the existing `/sc`
was waived by the operator in the re-read port; these corrections claim no new
Claude runtime proof. The session's `doc-end` baseline advances only after
the code repair is committed, the semantic critic reports zero STALE claims,
and the mechanical gate passes.

## Review outcome

M2 and final integration reviews: `APPROVED` on 2026-09-28. The tutorial's
`/ai-help` claim was narrowed to the router's persistent flag and registration
state, plus the re-read guard's persistent state when its hook script is
installed. The independent semantic critic found zero STALE claims; historical
client evidence whose temporary traces are gone remains UNVERIFIABLE. The
mechanical gate passed with six oversized-document and one unrelated
open-session advisory.
