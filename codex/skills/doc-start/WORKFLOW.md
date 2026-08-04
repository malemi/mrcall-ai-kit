---
description: Start a work session — load the smallest high-signal context and surface doc drift.
allowed-tools: Bash(git *) Bash(ls *) Bash(python3 *) Bash(cat *) Bash(make *) Bash(npm *) Bash(sbt *) Bash(pytest *) Agent
---

Load project knowledge: durable layer on demand, volatile state up front. Pull the smallest high-signal set into context — not everything.

## Harness version preflight — run before every other step
This command implements `harness_version = 3`. Read `docs/.doc-profile` and compare its `harness_version` before loading project context or running the gate.

- Equal to `3` ⇒ continue.
- Missing/lower ⇒ stop: `Harness version mismatch: repo docs are older than the installed commands (docs: <version|legacy>, commands: 3). Run doc-create and explicitly choose the docs/ upgrade, or leave the repo unchanged.`
- Greater ⇒ stop: `Harness version mismatch: installed commands are older than the repo docs (commands: 3, docs: <version>). Upgrade mrcall-ai-kit and reinstall its commands; do not downgrade docs/.`
- Missing profile ⇒ this repo is not bootstrapped; suggest `doc-create` and stop.

Never repair or bypass a mismatch inside `doc-start`.

## Delegation — trim the plumbing, never the payload

Where the environment provides a pinned-model worker (Claude Code: `Agent` with `subagent_type: "worker-sonnet"`; OpenCode: `task` with the same name), delegate the mechanical checks of Phase 2 — validating the baseline and counting content-drift commits, and scanning plan frontmatter — and take back only their results. Both are git and file plumbing whose answer is a few lines; neither needs to pass through this session's context on the way, and the frontmatter scan grows with the number of plans.

Never delegate reading the index, `docs/README.md`, or `docs/active-context.md`. Loading those into *this* session is the whole purpose of the command, and a worker's summary of them defeats it.

Be honest about the gain: this trims the plumbing, not the payload. A `doc-start` that costs a lot of context is telling you `active-context.md` has drifted into a changelog and needs consolidating — the worker is not the fix for that.

Without a worker, run the checks inline. Never skip one because you could not delegate it.

## Profile
After the version preflight succeeds, read the remaining profile keys: schema version, mode, index file, optional build/smoke command, and routing. It is machine-readable `key = value` data; comments never carry values. Mode is exactly `meta` or `leaf`; `build`/`smoke`, when present, must be non-empty. If invalid, report the violation and stop.
!`cat docs/.doc-profile 2>/dev/null || echo "NO PROFILE — run /doc-create to bootstrap this repo's docs/."`

## Canonical index
Resolve `index_file` from the profile. Do not assume a configured index was auto-loaded: skip reading it only when it is exactly the session's confirmed auto-loaded root instruction file; otherwise read it explicitly. Verify it is still a THIN index — pointers, roles, ownership, not prose. Read nested indexes when work enters their subtree.

## Index integrity (run first)
The gate below fails on dead doc links and, in meta mode, on repo-inventory drift or a duplicated repo-index. Surface any failure in the output line's *violations* slot and fix it before other work.
!`python3 "$HOME/.config/mrcall-ai-kit/doc-check.py" --repo . 2>&1 || true`

## Phase 1 — Durable layer (read on demand)
Run `ls ./docs/` to map the knowledge base and read `docs/README.md` (the index of transversal docs) to know what exists. "N docs indexed" is the number of distinct existing Markdown files in the mechanical gate's index set: `README.md`, configured `index_file`, and recursive `docs/**/*.md`, de-duplicated by path. It is not the number read into context. Open a durable doc only when the task enters its area. Absolute constraints are the exception.

## Phase 2 — Volatile layer (read now)
1. Read `docs/active-context.md` — last done / in progress / next. Its frontmatter carries `doc_baseline_commit`.
2. Validate that `doc_baseline_commit` resolves and is an ancestor of `HEAD`. Count later commits touching any path outside `docs/**` and configured `index_file`; these are content-drift commits. Docs-only commits are ignored, preventing a consolidation commit from creating false drift. Report working-tree changes separately, not in the count. Absent/invalid means no established baseline.
3. Read plan YAML frontmatter. Valid statuses are `planned`, `active`, `blocked`, `completed`, and `superseded`; missing/invalid status is a mechanical violation. Report planned, active, and blocked plans as open. Never infer lifecycle from headings, emoji, prose, or checkboxes.

Working tree + recent commits (pre-injected):
!`git status --short`
!`git log --oneline -n 8`

## Phase 3 — Constraint smoke check (conditional)
The build/smoke command (see profile) guards code work — it is NOT a session-start blocker. Skip it when only orienting or on a clean, in-sync tree. Run it before modifying code and surface any pre-existing breakage.

## Output
No summaries or greetings. Keep mechanical integrity distinct from semantic confidence; no semantic critic runs here. One line:
`Context loaded. [N] docs indexed. Baseline <sha> (<N> content commits behind HEAD; working tree clean|dirty). [mechanical gate: clean | violations]. [semantic review: not run]. [open plans]. Ready to work.`
