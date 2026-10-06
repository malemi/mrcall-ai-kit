---
description: Orient from repository documentation before source work; report compact mechanical facts.
allowed-tools: Bash(git *) Bash(ls *) Bash(python3 *) Bash(cat *) Bash(make *) Bash(npm *) Bash(sbt *) Bash(pytest *) Agent
---

The lead runs this once per valid repository/task scope before source investigation, including
questions, small fixes, briefs, and reviews. Reuse exact files confirmed present
in the lead's context; do not reread equivalent installed/source copies. Reload
affected knowledge after repository/worktree/instruction changes or context loss.

1. Read `docs/.doc-profile` in full. This workflow is v9: absent profile stops
   with `No profile — run doc-create`; v6–v8 stops with `Harness version
   mismatch: docs <version>, commands 9; explicitly upgrade with doc-create`;
   missing version or v1–v5 stops with `Harness version mismatch: docs
   <version|legacy>, commands 9; unsupported by doc-create, convert outside the
   kit`. Newer version stops with `Harness version mismatch: docs
   <version>, commands 9; upgrade installed commands`. Never repair or migrate
   during startup. v9 requires `index_file = AGENTS.md` and no `harness_file`.
2. Run `python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-check.py" --repo . --startup --json`.
   This single command supplies all mechanical violations/advisories, indexed
   count, baseline validity/content drift, staged/unstaged/untracked state,
   open plans and open/unknown issues. Committed drift and working-tree counts
   remain separate; no raw recent-commit or dirty-path payload is needed. Do not duplicate its
   scans or dump raw inventories/frontmatter. Report every finding; violations
   block source work until addressed within scope. Advisories never block and
   authorize no edits, renames, trimming, or extra reads. Mechanical success
   establishes no semantic confidence. A missing checker is a setup failure.
3. The lead reads the complete `AGENTS.md`, `docs/README.md`, and
   `docs/active-context.md` unless those exact documents are already in context.
   List the top-level `docs/` names to map the knowledge base. Read relevant
   durable documentation and absolute constraints before any source work.
   Nested indexes are read only when entering their subtree. In meta mode route
   through the root ownership table; never open child indexes to decide routing.
   If the map cannot answer, report/fix that map within scope.
4. Never load `docs/projects/**`, `docs/sessions/**`, archive/history bodies, or
   issue bodies as ambient startup context, including through workers. The
   checker may inspect them for integrity and report paths/sizes/statuses;
   its output is not permission to open them. Plans and issues are status-only
   here; open a body later only when the task specifically enters its area.
5. Before code modification, run the configured build/smoke command and report
   pre-existing breakage, even when the initial tree is clean and in sync. Skip
   it during orientation-only work. Keep working-tree changes separate from committed content drift.

Run mechanical work inline by default. Delegate only with measured benefit;
count worker overhead separately. Never delegate required lead orientation.

Output one concise summary: `Context loaded. N docs indexed. Baseline <sha or
invalid> (<N content commits behind HEAD>; working tree clean|dirty).
Mechanical gate: clean|violations. Open plans: <all paths/statuses or none>.
Open issues: <all open/unknown paths/statuses or none>. Semantic review: not run.`
Reproduce every violation and advisory beneath it unchanged; do not open their
named files merely to assess them. No greeting or narrative. Startup alone
never authorizes edits, baseline advancement, release, or a semantic audit.
Startup and limited read-only, brief-only, or review-only requests create no
persisted completion task. A receipt never substitutes for missing lead context.
