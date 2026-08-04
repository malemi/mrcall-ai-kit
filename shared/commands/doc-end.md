---
description: End a work session — reconsolidate the docs to reality, verify against code, advance the baseline.
allowed-tools: Bash(git *) Bash(python3 *) Bash(cat *) Read Write Edit Glob Grep Skill(doc-critic)
---

Consolidate session knowledge — Dream pattern: Orient → Gather → Consolidate → Prune. Ground truth is git plus the session transcript, never half-remembered context. Read `docs/.doc-profile` for mode, index file, and routing.

## Harness version preflight — run before every other step
This command implements `harness_version = 2`. Read `docs/.doc-profile` and compare its `harness_version` before checking whether consolidation is needed.

- Equal to `2` ⇒ continue.
- Missing/lower ⇒ stop: `Harness version mismatch: repo docs are older than the installed commands (docs: <version|legacy>, commands: 2). Run doc-create and explicitly choose the docs/ upgrade before consolidating.`
- Greater ⇒ stop: `Harness version mismatch: installed commands are older than the repo docs (commands: 2, docs: <version>). Upgrade mrcall-ai-kit and reinstall its commands; do not downgrade docs/.`
- Missing profile ⇒ suggest `doc-create` and stop.

Never edit session docs, advance the baseline, or run partial consolidation across a mismatch.

## Gate check — is consolidation needed?
At least one must hold, else output `No consolidation needed.` and stop:
- Change gate: `git status` / `git diff` shows uncommitted or recently committed work.
- Context gate: `docs/active-context.md` no longer matches reality.
- Plan gate: an execution plan has completed-but-unchecked steps.

## Phase 1 — Orient (ground truth, pre-injected)
!`git status --short`
!`git log --oneline -n 15`
1. Read `doc_baseline_commit` and validate that it resolves and is an ancestor of `HEAD`. The complete change set is the union of `git diff <baseline>..HEAD`, `git diff --cached`, and `git diff`. Include untracked paths from `git status --short` and read relevant new files. Never guess a `HEAD~N` range. If absent/invalid, inspect available history and working tree, state that a baseline is being established, and do not attribute uncertain work to this session.
2. If unsure what landed this session vs. earlier, ask rather than guess.
3. Read the docs you will edit.

## Phase 2 — Gather signal
Two kinds. The second is the one git CANNOT show you and is most often lost:
- From the diff (code / structure): new modules, resources, endpoints; changed boundaries; new deps; completed plan steps; tests added or broken; tech debt; harness gaps.
- From the session, NOT the diff: decisions made and why; approaches tried and rejected and why; user corrections and preferences stated this session; constraints and gotchas discovered.

## Phase 3 — Consolidate (reconsolidate, don't append)
Merge into existing content — no changelogs (git log is the changelog). Living docs are declarative and present-tense, **in English** (chat may be another language; artifacts are English).
- Verify-before-done: record a feature as built / working ONLY if it was verified end-to-end this session the way the user runs it (CLI / API / browser / REPL) — not because code was written or unit tests passed. Coded-but-unverified ⇒ in progress / needs verification.
- `docs/active-context.md`: overwrite to current reality — built & verified, unresolved/failing, and immediate next steps. It is not a changelog: obsolete theories, session narration, and completed detail without operational value do not stay here. Keep only `State now`, `Unresolved`, and `Next` plus baseline frontmatter; target at most 120 lines. Never delete this material outright — move it: prepend it, as dated `## <date> — <title>` section(s) preserved verbatim (wrap undated prose under the best-known date; if genuinely unknown, say so rather than inventing one), to the top of `docs/active-context-archive.md` (create it, with a one-paragraph English header explaining its purpose, if it doesn't exist yet; if creating it for the first time, add one routing line for it to `docs/README.md`). Durable facts (architecture, conventions) route to the appropriate durable doc instead of the archive.
- Durable docs (architecture / conventions): update ONLY on real structural change; delete descriptions of things that no longer exist.
- Execution plans: check off completed steps and record decisions. YAML frontmatter status must be one of `planned | active | blocked | completed | superseded`; set `status: completed` when done. Prose and emoji are not authoritative.
- Quality / harness docs: update if coverage / debt / quality moved; log enforcement gaps to the backlog.
- Maintain the **single source of truth**: if a sub-repo was added / removed / renamed or its role changed, update the index file's inventory tables — the ONLY place the inventory lives. Never re-add a repo table to `README.md` / `docs/README.md`.

## Phase 4 — Critic + gate (verify against code before advancing the baseline)
1. **Mechanical gate** — must pass:
   !`python3 "$HOME/.config/mrcall-ai-kit/doc-check.py" --repo . 2>&1 || true`
2. **Semantic review** — explicitly invoke the installed `doc-critic` skill over every Markdown doc touched across committed, staged, unstaged, and untracked changes. Keep it separate from the mechanical gate. Repair STALE findings and rerun to zero STALE; preserve UNVERIFIABLE findings in output and never call them clean.
3. Only when the mechanical gate passes and semantic review has zero STALE findings, set the baseline to current `git rev-parse HEAD` and update its date. It means "last reviewed repository commit", not "commit containing docs edits". A later commit touching only `docs/**` and configured `index_file` is ignored by `/doc-start`, so committing the consolidation creates no false drift. Never use an uncommitted or hypothetical SHA.

## Output
`Session state consolidated. Baseline advanced to <sha>. [docs touched]. [mechanical gate: clean]. [semantic review: N confirmed, N repaired, N unverifiable]. [N plan steps completed. N harness gaps logged.]`
