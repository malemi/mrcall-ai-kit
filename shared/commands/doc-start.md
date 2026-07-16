---
description: Start a work session — load the smallest high-signal context and surface doc drift.
allowed-tools: Bash(git *) Bash(ls *) Bash(python3 *) Bash(cat *) Bash(make *) Bash(npm *) Bash(sbt *) Bash(pytest *)
---

Load project knowledge: durable layer on demand, volatile state up front. Pull the smallest high-signal set into context — not everything.

## Profile
Read `docs/.doc-profile` for this repo's mode, index file, build/smoke command, and routing (pre-injected below). If it is absent, this repo has no doc-harness yet — suggest `/doc-create`, then stop.
!`cat docs/.doc-profile 2>/dev/null || echo "NO PROFILE — run /doc-create to bootstrap this repo's docs/."`

## Already in context — do NOT re-read
The index file (`CLAUDE.md` by default) is auto-loaded at session start; re-reading wastes context. Verify it is still a THIN index — pointers, roles, ownership, not prose — and flag it if it has grown into a full document. In a monorepo, nested index files off the root path are NOT auto-loaded; read those.

## Index integrity (run first)
The gate below fails on dead doc links and, in meta mode, on repo-inventory drift or a duplicated repo-index. Surface any failure in the output line's *violations* slot and fix it before other work.
!`python3 "$HOME/.config/mrcall-ai-kit/doc-check.py" --repo . 2>&1 || true`

## Phase 1 — Durable layer (read on demand)
Run `ls ./docs/` to map the knowledge base and read `docs/README.md` (the index of transversal docs) to know what exists. Open a durable doc only when the task enters its area. Absolute constraints (system-rules / core rules) are the exception — know them before touching code.

## Phase 2 — Volatile layer (read now)
1. Read `docs/active-context.md` — last done / in progress / next. Its frontmatter carries `doc_baseline_commit`.
2. Doc drift: `git rev-list --count <doc_baseline_commit>..HEAD` = commits landed since the docs were last synced. (Absent ⇒ baseline not established yet; note it.)
3. List active plans under `docs/execution-plans/` whose `status` is not `completed`.

Working tree + recent commits (pre-injected):
!`git status --short`
!`git log --oneline -n 8`

## Phase 3 — Constraint smoke check (conditional)
The build/smoke command (see profile) guards code work — it is NOT a session-start blocker. Skip it when only orienting or on a clean, in-sync tree. Run it before modifying code and surface any pre-existing breakage.

## Output
No summaries or greetings. One line:
`Context loaded. [N] docs indexed. Baseline <sha> (<N> commits behind HEAD). [gate: clean | violations]. [active plans]. Ready to work.`
