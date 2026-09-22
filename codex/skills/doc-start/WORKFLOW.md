---
description: Start a work session — load the smallest high-signal context and surface doc drift.
allowed-tools: Bash(git *) Bash(ls *) Bash(python3 *) Bash(cat *) Bash(make *) Bash(npm *) Bash(sbt *) Bash(pytest *) Agent
---

Load project knowledge: durable layer on demand, volatile state up front. Pull the smallest high-signal set into context — not everything.

## Harness version preflight — run before every other step
This command implements `harness_version = 8`. Read `docs/.doc-profile` and compare its `harness_version` before loading project context or running the gate.

- Equal to `8` ⇒ continue.
- Missing/lower ⇒ stop: `Harness version mismatch: repo docs are older than the installed commands (docs: <version|legacy>, commands: 8). Run doc-create and explicitly choose the docs/ upgrade, or leave the repo unchanged.`
- Greater ⇒ stop: `Harness version mismatch: installed commands are older than the repo docs (commands: 8, docs: <version>). Upgrade mrcall-ai-kit and reinstall its commands; do not downgrade docs/.`
- Missing profile ⇒ this repo is not bootstrapped; suggest `doc-create` and stop.

Never repair, add scope declarations, or bypass a mismatch inside `doc-start`.

## Delegation — trim the plumbing, never the payload

Where the environment provides a pinned-model worker (Claude Code: `Agent` with `subagent_type: "worker-sonnet"`; OpenCode: `task` with the same name), delegate the mechanical checks of Phase 2 — validating the baseline and counting content-drift commits, and scanning plan frontmatter — and take back only their results. Both are git and file plumbing whose answer is a few lines; neither needs to pass through this session's context on the way, and the frontmatter scan grows with the number of plans.

Never delegate reading the index, `docs/README.md`, or `docs/active-context.md`. Loading those into *this* session is the whole purpose of the command, and a worker's summary of them defeats it.

Be honest about the gain: this trims the plumbing, not the payload. A `doc-start` that costs a lot of context is telling you `active-context.md` has drifted into a changelog and needs consolidating — the worker is not the fix for that.

Without a worker, run the checks inline. Never skip one because you could not delegate it.

## Read scope — `docs/projects/**` is never opened here

Do not read, `grep`, or frontmatter-scan anything under `docs/projects/**` — the per-customer / per-engagement working folders — and do not hand that job to a worker either. Delegating it does not make it allowed; it only moves the same mistake into a context you cannot see. Those folders are loaded deliberately, one at a time, by whatever command owns customer work, never as ambient session start-up. Twenty project folders must not cost twenty times what one costs — the number of customers a repo tracks is not allowed to drive the price of starting a session.

Counting them is fine; reading them is not. They belong to the gate's index set, so they are included in "N docs indexed" and the gate may name an oversized one by path, line count, bytes, and estimated tokens. A path and its size are the entire budget this command may spend on a project folder — that is what keeps start-up cost flat as project folders accumulate, whether there are two of them or twenty. When work later turns to a specific project, open that folder then, on purpose.

`docs/sessions/**` — the opt-in model router's per-session shared memory, when that feature is installed — follows the identical rule and for the identical reason: it is loaded by a running session that needs it, never as ambient start-up context. The gate counts and advises on it (an `open session file(s)` line, same shape as the other advisories); this command never opens one.

## Routing in a meta-repo — a sub-repo index is never opened to decide where work belongs
In `meta` mode the index's ownership map already answers the routing question by itself: it says which repository owns which concern, and that is the whole answer. Reading a sub-repo's own index to work out whether a change belongs there inverts the cost — the map is one table, the indexes are ten files, and the answer was in the table the entire time.

So: open a sub-repo index when work has entered that repository's **code**, never to decide whether it should. If the map cannot answer, the defect is in the map — say so, and fix the map — rather than paying ten reads to route one change.

The gate helps in the other direction. Each sub-repo index should open with an orientation head — stack, entry points, build and test command, the rules that must not be broken — closed by an `<!-- orientation ends -->` marker, so that a session which *does* need to enter that repository can orient on a dozen lines instead of the whole file. In `meta` mode the gate prints an advisory naming each index that has no such head. Like every advisory it never blocks, and this command does nothing with it beyond carrying it through to the output.

## Profile
After the version preflight succeeds, read the remaining profile keys: schema version, mode, index file, harness file, optional build/smoke command, and routing. It is machine-readable `key = value` data; comments never carry values. Mode is exactly `meta` or `leaf`; v6 requires `index_file = AGENTS.md` and `harness_file = CLAUDE.md`; `build`/`smoke`, when present, must be non-empty. If invalid, report the violation and stop.
!`cat docs/.doc-profile 2>/dev/null || echo "NO PROFILE — run /doc-create to bootstrap this repo's docs/."`

## Harness instructions and canonical index
Resolve `harness_file` and `index_file` from the profile. Read managed
`CLAUDE.md` first unless this session confirms that exact path was auto-loaded;
then read project-owned `AGENTS.md` unless the runtime confirms it was loaded.
Claude Code reaches the project file through `@AGENTS.md`; Codex and OpenCode
load it natively, but this workflow never guesses what the current session has
actually received. Verify that `CLAUDE.md` matches the installed canonical
template byte-for-byte and contains no project guidance. Verify that `AGENTS.md`
is still thin — routing, roles, ownership, conventions, and pointers rather
than durable prose. Read nested `AGENTS.md` files only when work enters their
subtree.

## Index integrity (run first)
The gate below fails on dead doc links and, in meta mode, on repo-inventory drift or a duplicated repo-index. Surface any failure in the output line's *violations* slot and fix it before other work.

The gate also prints `advisory` blocks — docs past `doc_max_lines`, work-trace files (briefs, execution plans) named without their `YYYY-MM-DD-` date prefix, and in meta mode any sub-repo index with no orientation head. They are not failures and never block: carry those lines through to the output unchanged (the Output section says where they go) and leave them alone. Do not open a named file to assess it, do not trim or rename it, do not propose a restructuring unasked — reporting is the whole job, and the operator decides what to do about it.
!`python3 "$HOME/.config/mrcall-ai-kit/doc-check.py" --repo . 2>&1 || true`

## Phase 1 — Durable layer (read on demand)
Run `ls ./docs/` to map the knowledge base and read `docs/README.md` (the index of transversal docs) to know what exists. "N docs indexed" is the number of distinct existing Markdown files in the mechanical gate's index set: `README.md`, configured `index_file`, configured `harness_file`, and recursive `docs/**/*.md`, de-duplicated by path. It is not the number read into context. Open a durable doc only when the task enters its area. Absolute constraints are the exception.

## Phase 2 — Volatile layer (read now)
1. Read `docs/active-context.md` — last done / in progress / next. Its frontmatter carries `doc_baseline_commit`.
2. Validate that `doc_baseline_commit` resolves and is an ancestor of `HEAD`. Count later commits touching any path outside `docs/**`, configured `index_file`, and configured `harness_file`; these are content-drift commits. Harness-only commits are ignored, preventing a consolidation or protocol-migration commit from creating false drift. Report working-tree changes separately, not in the count. Absent/invalid means no established baseline.
3. Read plan YAML frontmatter — **`docs/execution-plans/**/*.md` and nothing else**, which is exactly the set the gate enforces. A `plan.md` sitting inside `docs/projects/**` is that project's own business and is out of scope here; widening the scan to catch it is the read-scope violation above, not diligence. Valid statuses are `planned`, `active`, `blocked`, `completed`, and `superseded`; missing/invalid status is a mechanical violation. Report planned, active, and blocked plans as open. Never infer lifecycle from headings, emoji, prose, or checkboxes.
4. Read known-issue YAML frontmatter — **`docs/known-issues/*.md` and nothing else**, excluding that directory's own `README.md`, which is the index. Valid statuses are `open`, `fixed`, and `unknown`. Unlike a plan, a file with **no** frontmatter counts as `unknown` rather than as a violation: the directory predates this scan in every repository, and a missing status is a gap to report, not a reason to stop. Report `open` and `unknown` together as open issues. Never open an issue body — the log runs to tens of kilobytes and the count is the entire budget this command spends on it. When work later enters an issue's area, grep the index and open exactly that one file.

Working tree + recent commits (pre-injected):
!`git status --short`
!`git log --oneline -n 8`

## Phase 3 — Constraint smoke check (conditional)
The build/smoke command (see profile) guards code work — it is NOT a session-start blocker. Skip it when only orienting or on a clean, in-sync tree. Run it before modifying code and surface any pre-existing breakage.

## Output
No summaries or greetings. Keep mechanical integrity distinct from semantic confidence; no semantic critic runs here. One line:
`Context loaded. [N] docs indexed. Baseline <sha> (<N> content commits behind HEAD; working tree clean|dirty). [mechanical gate: clean | violations]. [oversized docs: N]. [undated traces: N]. [open sessions: N]. [open issues: N]. [unoriented indexes: N]. [semantic review: not run]. [open plans]. Ready to work.`

The *oversized docs*, *undated traces*, *open sessions*, and *unoriented indexes* slots carry counts only; omit each slot entirely when the gate reported none of its kind. When one is non-zero, reproduce the gate's advisory lines verbatim underneath the summary, one per line — a repo can have ten of them and they do not belong inside a one-line summary. Add no commentary of your own to them.
