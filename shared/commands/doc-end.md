---
description: End a work session — reconsolidate the docs to reality, verify against code, advance the baseline.
disable-model-invocation: true
allowed-tools: Bash(git *) Bash(python3 *) Bash(cat *)
---

Consolidate session knowledge — Dream pattern: Orient → Gather → Consolidate → Prune. Ground truth is git plus the session transcript, never half-remembered context. Read `docs/.doc-profile` for mode, index file, and routing.

## Gate check — is consolidation needed?
At least one must hold, else output `No consolidation needed.` and stop:
- Change gate: `git status` / `git diff` shows uncommitted or recently committed work.
- Context gate: `docs/active-context.md` no longer matches reality.
- Plan gate: an execution plan has completed-but-unchecked steps.

## Phase 1 — Orient (ground truth, pre-injected)
!`git status --short`
!`git log --oneline -n 15`
1. Read `doc_baseline_commit` from `docs/active-context.md` frontmatter. The change set is everything in `git diff <doc_baseline_commit>..HEAD` — precise; do not guess a `HEAD~N` range. If absent, fall back to `git diff HEAD~5..HEAD` and note you are establishing the baseline now.
2. If unsure what landed this session vs. earlier, ask rather than guess.
3. Read the docs you will edit.

## Phase 2 — Gather signal
Two kinds. The second is the one git CANNOT show you and is most often lost:
- From the diff (code / structure): new modules, resources, endpoints; changed boundaries; new deps; completed plan steps; tests added or broken; tech debt; harness gaps.
- From the session, NOT the diff: decisions made and why; approaches tried and rejected and why; user corrections and preferences stated this session; constraints and gotchas discovered.

## Phase 3 — Consolidate (reconsolidate, don't append)
Merge into existing content — no changelogs (git log is the changelog). Living docs are declarative and present-tense, **in English** (chat may be another language; artifacts are English).
- Verify-before-done: record a feature as built / working ONLY if it was verified end-to-end this session the way the user runs it (CLI / API / browser / REPL) — not because code was written or unit tests passed. Coded-but-unverified ⇒ in progress / needs verification.
- `docs/active-context.md`: overwrite to the state right now — built & verified, completed, unresolved / failing, immediate next steps. Route per the profile.
- Durable docs (architecture / conventions): update ONLY on real structural change; delete descriptions of things that no longer exist.
- Execution plans: check off completed steps, record decisions, set `status: completed` when done.
- Quality / harness docs: update if coverage / debt / quality moved; log enforcement gaps to the backlog.
- Maintain the **single source of truth**: if a sub-repo was added / removed / renamed or its role changed, update the index file's inventory tables — the ONLY place the inventory lives. Never re-add a repo table to `README.md` / `docs/README.md`.

## Phase 4 — Critic + gate (verify against code before advancing the baseline)
1. **Mechanical gate** — must pass:
   !`python3 "$HOME/.config/mrcall-ai-kit/doc-check.py" --repo . 2>&1 || true`
2. **Semantic critic** — run the `doc-critic` skill over the docs you touched this session (scoped to the diff): does any doc claim a feature / endpoint / file / flag that does not exist or is not wired? Is any described capability actually dead code? Is any artifact written in a non-English language that should be English? Flag → repair → re-check (reflexion) until the critic is clean.
3. Only when BOTH pass, advance the baseline: set `doc_baseline_commit` to `git rev-parse HEAD` and update `doc_baseline_date` in `docs/active-context.md` frontmatter.

## Output
`Session state consolidated. Baseline advanced to <sha>. [docs touched]. [gate: clean]. [critic: N claims verified/repaired]. [N plan steps completed. N harness gaps logged.]`
