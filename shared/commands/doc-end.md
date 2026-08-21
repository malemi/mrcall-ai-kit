---
description: End a work session — reconsolidate the docs to reality, verify against code, advance the baseline.
allowed-tools: Bash(git *) Bash(python3 *) Bash(cat *) Read Write Edit Glob Grep Skill(doc-critic) Agent
---

Consolidate session knowledge — Dream pattern: Orient → Gather → Consolidate → Prune. Ground truth is git plus the session transcript, never half-remembered context. Read `docs/.doc-profile` for mode, index file, and routing.

## Delegation — what this session must do itself, and what it must not

Two phases below are **yours alone and can never be delegated**: gathering the session signal (Phase 2) and deciding what is current versus historical (Phase 3). Only this session holds the transcript — the decisions, rejected approaches, and user corrections that git cannot show — and no subagent can reconstruct it. A worker that "summarizes the session" is inventing.

Everything else is delegable when your environment provides a pinned-model worker, and should be: it is cheaper, and it keeps this session's context free for the judgment that actually needs it. Claude Code exposes both workers named below through the `Agent` tool (`subagent_type: "worker-sonnet"` / `"worker-opus"`). OpenCode uses `task`, and ships `worker-sonnet` but no `worker-opus` — pick the strongest worker its roster offers for the verification role, or do that step inline. Check what your environment actually provides rather than assuming a name exists; where it does not, do the work inline — never skip a step because you could not delegate it.

- **`worker-sonnet` — mechanical execution.** Summarizing the code diff between the baseline and `HEAD` (Phase 1); applying an archive-and-trim once *you* have decided what is current (Phase 3); running the gate and reporting its output (Phase 4.1). Give it exact instructions; it must not decide what should change.
- **`worker-opus` — independent verification.** The semantic review (Phase 4.2). Delegating this is not only about cost: a fresh context has not been persuaded by the reasoning that produced the docs, so it reads the claim and the code rather than the story behind them. Pass it the list of changed docs and have it invoke the `doc-critic` skill; require UNVERIFIABLE over a guessed confirmation. Require the living-context shape check on `docs/active-context.md` **whether or not that file changed** — a skipped Phase 3 leaves it untouched, so it would be absent from a changed-files list precisely in the case the check exists to catch. Tell it explicitly that it is running delegated from Phase 4, so that if it finds `active-context.md` still mis-shaped it reports that instead of repairing it: a violation surviving to Phase 4 means Phase 3's decision was skipped or botched, and redoing it needs the transcript, which the worker does not have.

A worker returns `## Done` or `## Blocked`. Anything else, or a `## Done` whose "Verified" line quotes no real command output, is a failure: re-delegate with a corrected prompt or do it yourself. Never report a worker's claim as a verified fact without its evidence.

## Harness version preflight — run before every other step
This command implements `harness_version = 3`. Read `docs/.doc-profile` and compare its `harness_version` before checking whether consolidation is needed.

- Equal to `3` ⇒ continue.
- Missing/lower ⇒ stop: `Harness version mismatch: repo docs are older than the installed commands (docs: <version|legacy>, commands: 3). Run doc-create and explicitly choose the docs/ upgrade before consolidating.`
- Greater ⇒ stop: `Harness version mismatch: installed commands are older than the repo docs (commands: 3, docs: <version>). Upgrade mrcall-ai-kit and reinstall its commands; do not downgrade docs/.`
- Missing profile ⇒ suggest `doc-create` and stop.

Never edit session docs, advance the baseline, or run partial consolidation across a mismatch.

## Gate check — is consolidation needed?
At least one must hold, else output `No consolidation needed.` and stop:
- Change gate: `git status` / `git diff` shows uncommitted or recently committed work.
- Context gate: `docs/active-context.md` no longer matches reality.
- **Shape gate**: `docs/active-context.md` violates the living-context shape — a `##` section beyond `State now` / `Unresolved` / `Next`, chronological narrative, or well over the ~120-line target. Read the file and check this every time, even when the other gates are plainly shut and nothing was committed. Drift here is not a consequence of this session's work and will not show up in `git status`: a file can be mis-shaped for months, or have been rewritten by something that never ran this command at all, and every run that only asks "was there new work?" answers `No consolidation needed` and leaves it. If this gate is the only one that fires, the work is the archive-and-trim of Phase 3 and nothing else — do that, then stop.
- Plan gate: work completed **in this session** has left an execution plan's steps unchecked or its `status` stale. A plan that was already `completed` with unticked boxes before this session is not this gate: `status` is the lifecycle, checkboxes are a reading aid, and their disagreement is untidiness rather than a defect. Do not investigate or "fix" it here — a checkbox says nothing authoritative, and deciding whether a May step really ran needs May's transcript. Mention it once in the output if you like; never block on it.

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
- **From this session's own memory file, if the opt-in model router named one.** When routing is active, its hook injects `docs/sessions/<session-id>.md` into this very turn's context — read it if that path is present; it holds whatever pinned-model workers this session delegated to chose to record. If no such path was injected this turn (router off, or never touched this session), there is nothing to gather here — do not glob `docs/sessions/*.md` guessing which file might be yours; a file with no confirmed owner is `/router sweep`'s business, not this command's.

## Phase 3 — Consolidate (reconsolidate, don't append)
Merge into existing content — no changelogs (git log is the changelog). Living docs are declarative and present-tense, **in English** (chat may be another language; artifacts are English).
- Verify-before-done: record a feature as built / working ONLY if it was verified end-to-end this session the way the user runs it (CLI / API / browser / REPL) — not because code was written or unit tests passed. Coded-but-unverified ⇒ in progress / needs verification.
- `docs/active-context.md`: overwrite to current reality — built & verified, unresolved/failing, and immediate next steps. It is not a changelog: obsolete theories, session narration, and completed detail without operational value do not stay here. Keep only `State now`, `Unresolved`, and `Next` plus baseline frontmatter; target at most 120 lines. Never delete this material outright — move it: prepend it, as dated `## <date> — <title>` section(s) preserved verbatim (wrap undated prose under the best-known date; if genuinely unknown, say so rather than inventing one), to the top of `docs/active-context-archive.md` (create it, with a one-paragraph English header explaining its purpose, if it doesn't exist yet; if creating it for the first time, add one routing line for it to `docs/README.md`). Durable facts (architecture, conventions) route to the appropriate durable doc instead of the archive.
- Durable docs (architecture / conventions): update ONLY on real structural change; delete descriptions of things that no longer exist.
- Execution plans: check off completed steps and record decisions. YAML frontmatter status must be one of `planned | active | blocked | completed | superseded`; set `status: completed` when done. Prose and emoji are not authoritative.
- Work traces: if this session ran orchestrated work (a multi-agent/worker fan-out) or opened a workstream that will outlive the session, and no `docs/briefs/YYYY-MM-DD-<slug>.md` + `docs/execution-plans/YYYY-MM-DD-<slug>.md` pair exists for it, create the pair now — you hold the transcript that says what the work was and why. The brief records the what/why (decision, approach, rejected alternatives; no status frontmatter); the plan's frontmatter records where reality is (`active`, `completed`, `blocked` — work merely conceived is `planned`). A small single-session fix needs no pair, but that is a decision to state in the output's *work trace* slot, never an omission.
- Quality / harness docs: update if coverage / debt / quality moved; log enforcement gaps to the backlog.
- Maintain the **single source of truth**: if a sub-repo was added / removed / renamed or its role changed, update the index file's inventory tables — the ONLY place the inventory lives. Never re-add a repo table to `README.md` / `docs/README.md`.
- Session memory: if Phase 2 read a `docs/sessions/<session-id>.md`, this is where it gets promoted — fold whatever is durable into `docs/active-context.md` exactly as you would any other session signal, then flip that file's frontmatter `status` from `open` to `closed`. The flip can ride along with the archive-and-trim edit when you delegate that to `worker-sonnet`. Nothing else about the session file changes — it stays on disk, closed, as the record that it was reconciled.

## Phase 4 — Critic + gate (verify against code before advancing the baseline)
1. **Mechanical gate** — must pass:
   !`python3 "$HOME/.config/mrcall-ai-kit/doc-check.py" --repo . 2>&1 || true`
   The gate may also print `advisory` blocks — docs past `doc_max_lines`, work-trace files named without their `YYYY-MM-DD-` date prefix, and session-memory files (`docs/sessions/*.md`) still `open`. They are **not** part of "must pass" and never block the baseline. Report those lines and stop there: a long document or a legacy filename is the operator's call, and this command's licence to edit docs covers what *this session* changed, not a file that merely happens to be big or old. In particular, never let an advisory pull `docs/projects/**` into a trim — those folders are outside every automatic pass. The one case where it is already in scope: if the oversized file is `docs/active-context.md` itself, that is the Phase 3 shape gate firing, and Phase 3 owns it.
2. **Semantic review** — explicitly invoke the installed `doc-critic` skill over every Markdown doc touched across committed, staged, unstaged, and untracked changes. Keep it separate from the mechanical gate. Repair STALE findings and rerun to zero STALE; preserve UNVERIFIABLE findings in output and never call them clean.
3. Only when the mechanical gate passes, semantic review has zero STALE findings, and no unresolved living-context shape violation remains, set the baseline to current `git rev-parse HEAD` and update its date. A delegated critic reports a shape violation instead of repairing it (it lacks the transcript); that report is blocking, not advisory — it means Phase 3 was skipped or botched, so return to Phase 3, redo it yourself, and re-run the review. Never advance the baseline over a mis-shaped `active-context.md`. It means "last reviewed repository commit", not "commit containing docs edits". A later commit touching only `docs/**` and configured `index_file` is ignored by `/doc-start`, so committing the consolidation creates no false drift. Never use an uncommitted or hypothetical SHA.

## Output
`Session state consolidated. Baseline advanced to <sha>. [docs touched]. [mechanical gate: clean]. [oversized docs: N]. [undated traces: N]. [open sessions: N]. [semantic review: N confirmed, N repaired, N unverifiable]. [work trace: created|updated <slug> | not needed]. [N plan steps completed. N harness gaps logged.]`

The *oversized docs*, *undated traces*, and *open sessions* slots carry counts only, and each is omitted entirely when the gate reported none of its kind; reproduce the gate's advisory lines verbatim beneath the summary, adding nothing of your own. They never affect whether the baseline advances. The *work trace* slot is always present in one of its three forms — it is the explicit record of the Phase 3 trace decision, and `not needed` said out loud is the whole point.

When a blocking condition survives the run, say so instead — never emit the advanced-baseline line for a baseline you did not advance: `Session state consolidated, BASELINE NOT ADVANCED — <blocking condition>. [docs touched]. [what remains to be done].`

When no gate fires, the whole output is the line `No consolidation needed.`, optionally followed by one short sentence naming the single fact that decided it. Do not narrate the gate-by-gate evaluation: this is the cheapest path through the command and it should read that way. You still had to open `docs/active-context.md` for the shape gate, so say `shape OK` — a silent no-op is indistinguishable from a check that was skipped.
