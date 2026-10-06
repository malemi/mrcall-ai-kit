---
description: End a work session — reconsolidate the docs to reality, verify against code, advance the baseline.
allowed-tools: Bash(git *) Bash(python3 *) Bash(cat *) Read Write Edit Glob Grep Skill(doc-critic) Agent
---

Consolidate session knowledge — Dream pattern: Orient → Gather → Consolidate → Prune. Ground truth is git plus the session transcript, never half-remembered context. Read `docs/.doc-profile` for mode, index file, and routing. This is the v9 closure workflow. An explicit read-only, brief-only, or review-only request does not authorize consolidation. A fast-path change with a justified no-documentation-impact decision needs only its focused real check and explicit completion decision.

## Delegation — what this session must do itself, and what it must not

Two phases below are **yours alone and can never be delegated**: gathering the session signal (Phase 2) and deciding what is current versus historical (Phase 3). Only this session holds the transcript — the decisions, rejected approaches, and user corrections that git cannot show — and no subagent can reconstruct it. A worker that "summarizes the session" is inventing.

Other phases may be delegated when independent verification or measured context/execution benefit justifies the overhead; mechanical work is inline by default. Claude Code exposes both roles named below through the `Agent` tool (`subagent_type: "execute"` / `"verify"`); OpenCode exposes the same names through `task`; Codex uses `spawn_agent` with the installed `execute` or `verify` role. Check what your environment actually provides rather than assuming a name exists; where it does not, do the work inline — never skip a step because you could not delegate it.

- **`execute` — mechanical execution.** Summarizing the code diff between the baseline and `HEAD` (Phase 1); applying an archive-and-trim once *you* have decided what is current (Phase 3); running the gate and reporting its output (Phase 4.1). Give it exact instructions; it must not decide what should change.
- **`verify` — independent verification.** The semantic review (Phase 4.2). Delegating this is not only about cost: a fresh context has not been persuaded by the reasoning that produced the docs, so it reads the claim and the code rather than the story behind them. Pass it the affected-document list, including unchanged documents and missing coverage identified by the lead, and have it invoke the `doc-critic` skill; require UNVERIFIABLE over a guessed confirmation. Require the living-context shape check on `docs/active-context.md` **whether or not that file changed** — a skipped Phase 3 leaves it untouched, so it would be absent from a changed-files list precisely in the case the check exists to catch. Tell it explicitly that it is running delegated from Phase 4, so that if it finds `active-context.md` still mis-shaped it reports that instead of repairing it: a violation surviving to Phase 4 means Phase 3's decision was skipped or botched, and redoing it needs the transcript, which the worker does not have.

A worker returns `## Done` or `## Blocked`. Anything else, or a `## Done` whose "Verified" line quotes no real command output, is a failure: re-delegate with a corrected prompt or do it yourself. Never report a worker's claim as a verified fact without its evidence.

## Harness version preflight — run before every other step
This command implements `harness_version = 9`. Read `docs/.doc-profile` and compare its `harness_version` before checking whether consolidation is needed.

- Equal to `9` ⇒ continue.
- 6, 7, or 8 ⇒ stop: `Harness version mismatch: repo docs are older than the installed commands (docs: <version>, commands: 9). Run doc-create and explicitly choose the docs/ upgrade before consolidating.`
- Missing or 1–5 ⇒ stop: `Harness version mismatch: repo docs use an unsupported legacy harness (docs: <version|legacy>, commands: 9). doc-create migrates only v6–v8; convert outside the kit before consolidating.`
- Greater ⇒ stop: `Harness version mismatch: installed commands are older than the repo docs (commands: 9, docs: <version>). Upgrade mrcall-ai-kit and reinstall its commands; do not downgrade docs/.`
- Missing profile ⇒ suggest `doc-create` and stop.

Never edit session docs, add scope declarations, advance the baseline, or run partial consolidation across a mismatch.

## Gate check — is consolidation needed?
At least one must hold, else output `No consolidation needed.` and stop:
- Change gate: `git status` / `git diff` shows uncommitted or recently committed work.
- Context gate: `docs/active-context.md` no longer matches reality.
- **Shape gate**: `docs/active-context.md` violates the living-context shape — a `##` section beyond `State now` / `Unresolved` / `Next`, chronological narrative, or well over the ~120-line target. Read the file and check this every time, even when the other gates are plainly shut and nothing was committed. Drift here is not a consequence of this session's work and will not show up in `git status`: a file can be mis-shaped for months, or have been rewritten by something that never ran this command at all, and every run that only asks "was there new work?" answers `No consolidation needed` and leaves it. If this gate is the only one that fires, limit reconciliation to the archive-and-trim of Phase 3, then perform Phase 4 verification and completion checks.
- Plan gate: work completed **in this session** has left an execution plan's steps unchecked or its `status` stale. A plan that was already `completed` with unticked boxes before this session is not this gate: `status` is the lifecycle, checkboxes are a reading aid, and their disagreement is untidiness rather than a defect. Do not investigate or "fix" it here — a checkbox says nothing authoritative, and deciding whether a May step really ran needs May's transcript. Mention it once in the output if you like; never block on it.

## Phase 1 — Orient (ground truth, pre-injected)
!`git status --short`
!`git log --oneline -n 15`
1. Read `doc_baseline_commit` and validate that it resolves and is an ancestor of `HEAD`. The complete change set is the union of `git diff <baseline>..HEAD`, `git diff --cached`, and `git diff`. Include untracked paths from `git status --short` and read relevant new files. Never guess a `HEAD~N` range. If absent/invalid, inspect available history and working tree, state that a baseline is being established, and do not attribute uncertain work to this session.
2. If unsure what landed this session vs. earlier, ask rather than guess.
3. Before deciding edits, identify documentation affected by the changed behavior and its documented dependencies. Include unchanged contracts, routing entries, and missing capability coverage. Read those docs and state the impact decision; changed Markdown alone is insufficient. Keep the audit within task scope.

## Phase 2 — Gather signal
Two kinds. The second is the one git CANNOT show you and is most often lost:
- From the diff (code / structure): new modules, resources, endpoints; changed boundaries; new deps; completed plan steps; tests added or broken; tech debt; harness gaps.
- From the session, NOT the diff: decisions made and why; approaches tried and rejected and why; user corrections and preferences stated this session; constraints and gotchas discovered.
- **From this session's own memory file, if the opt-in model router named one.** When routing is active, its hook injects `docs/sessions/<session-id>.md` into this very turn's context — read it if that path is present; it holds whatever the role agents this session delegated to chose to record. If no such path was injected this turn (router off, or never touched this session), there is nothing to gather here — do not glob `docs/sessions/*.md` guessing which file might be yours; a file with no confirmed owner is `/router sweep`'s business, not this command's.

## Phase 3 — Consolidate (reconsolidate, don't append)
Merge into existing content — no changelogs (git log is the changelog). Living docs are declarative and present-tense, **in English** (chat may be another language; artifacts are English).
- Verify-before-done: record a feature as built / working ONLY if it was verified end-to-end this session the way the user runs it (CLI / API / browser / REPL) — not because code was written or unit tests passed. Coded-but-unverified ⇒ in progress / needs verification.
- `docs/active-context.md`: overwrite to current reality — built & verified, unresolved/failing, and immediate next steps. It is not a changelog: obsolete theories, session narration, and completed detail without operational value do not stay here. Keep only `State now`, `Unresolved`, and `Next` plus baseline frontmatter; target at most 120 lines. Never delete this material outright — move it: prepend it, as dated `## <date> — <title>` section(s) preserved verbatim (wrap undated prose under the best-known date; if genuinely unknown, say so rather than inventing one), to the top of `docs/active-context-archive.md` (create it, with a one-paragraph English header explaining its purpose, if it doesn't exist yet; if creating it for the first time, add one routing line for it to `docs/README.md`). Durable facts (architecture, conventions) route to the appropriate durable doc instead of the archive.
- Durable docs (architecture / conventions): update ONLY on real structural change; delete descriptions of things that no longer exist.
- Execution plans: prepare the completed steps and decisions for review. YAML frontmatter status must be one of `planned | active | blocked | completed | superseded`. Declare an intended `active` → `completed` transition for checker finalization after approval; leave the current status unchanged until then. All other plan edits belong before the applicable review. Prose and emoji are not authoritative.
- Work traces: if this session ran orchestrated work (a multi-agent/worker fan-out) or opened a workstream that will outlive the session, and no `docs/briefs/YYYY-MM-DD-<slug>.md` + `docs/execution-plans/YYYY-MM-DD-<slug>.md` pair exists for it, create the pair now — you hold the transcript that says what the work was and why. The brief records the what/why (decision, approach, rejected alternatives; no status frontmatter); the plan's frontmatter records where reality is (`active`, `completed`, `blocked` — work merely conceived is `planned`). A small single-session fix needs no pair, but that is a decision to state in the output's *work trace* slot, never an omission.
- Quality / harness docs: update if coverage / debt / quality moved; log enforcement gaps to the backlog.
- Maintain the **single source of truth**: if a sub-repo was added / removed / renamed or its role changed, update the index file's inventory tables — the ONLY place the inventory lives. Never re-add a repo table to `README.md` / `docs/README.md`.
- Session memory: if Phase 2 read a `docs/sessions/<session-id>.md`, this is where it gets promoted — fold whatever is durable into `docs/active-context.md` exactly as you would any other session signal, then flip that file's frontmatter `status` from `open` to `closed`. The flip can ride along with the archive-and-trim edit when you delegate that to `execute`. Nothing else about the session file changes — it stays on disk, closed, as the record that it was reconciled.

## Completion record — bind actual evidence to this mutating task

Use the existing checker completion API for documentation-only work, substantial
development, and fast-path changes with documentation impact. A justified
fast-path no-impact change needs only its focused real check and explicit impact
and completion decision; do not manufacture a critic or baseline operation.
Read-only, brief-only, review-only, and startup-only requests create no record.

Use one explicit task ID and an absolute repository root. Retain input JSON and
raw result artifacts outside reviewed source content. The checker stores small
hashes and references under this worktree's Git directory, not transcript bodies.
Resolve the installed checker through `${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}`.
All commands below use that same `doc-check.py`, `--repo "$repo_root"`, and
`--task "$task_id"`. The live `context_id` is an honest caller token for the
lead knowledge currently available, not proof the checker can inspect context.

Initialize once with `--completion init --input "$task_input" --json`. The JSON
contains `kind` (`documentation`, `development`, or `fastpath`), explicit relative
`scope` paths, real ancestor `base`, and absolute current workflow paths under
`workflows`: `doc_start`, `doc_end`, `doc_critic`. An unborn repository has no
valid base: report the refusal; never invent a baseline or create an unauthorized
commit. If completing an active plan,
declare `plan_transition: {"path": "<relative plan>", "from": "active", "to": "completed"}`.
For development, also declare `reviews` mapping live source paths:
`{"brief": "<relative brief>", "plan": "<relative plan>", "milestones": {"M1": "<relative reviewed milestone source>"}}`.
Declare at least one milestone. Initialization may precede artifact creation;
record each verdict only after the actual artifact and review exist. Capture
an immutable approved artifact version outside reviewed source content at that
review, alongside the real raw verdict; do not reconstruct an approved version
from later edited prose. Submit each prior verdict with `--completion result`:
`schema_version`, task/repository/Git-directory binding, real `producer`,
`gate_kind` (`brief-review`, `plan-review`, or `milestone-review`), `gate_id`
(`brief`, `plan`, or its declared milestone ID), checker-issued `scope_digest`,
`source` matching the declared relative path, `artifact: {"path": "<absolute retained version>", "sha256": "<actual hash>"}`,
actual `outcome`, `deferrals`, and absolute raw `report` path. The checker retains
references and hashes, not another copy of artifact bodies. Preserve these
versions and reports across delegation; later progress notes do not rewrite
prior approval. Substantive scope changes require a fresh applicable review and
new approved version. Existing prior review references can be recorded after
initialization; never invent missing reviews at closure. Record or replace
these prior references before final impact/reconciliation and critic snapshots:
changing an approved-version reference changes the closure fingerprint.

The baseline commit/date keys must already exist before review; finalization
cannot hide new structure inside a metadata exemption. Use existing task
recovery instead of resetting evidence to evade a refusal.

The lead writes truthful obligation JSON and submits each with
`--completion attest --input "$attestation" --json`:

- Startup: `obligation: "startup"`, `producer: "lead"`, the actual personally
  available `documents` (at least `AGENTS.md`, `docs/.doc-profile`,
  `docs/README.md`, and `docs/active-context.md`), `context_id`, and
  `available: true`. Never assert this
  from a worker summary or a previous receipt after context loss.
- Impact: `obligation: "impact"`, `producer: "lead"`, explicit `affected_docs`
  including unchanged affected contracts, `doc_impact`, the factual `reason`,
  and the explicit `work_trace` decision. Missing capability coverage must be
  resolved or reported, never hidden by listing only edited Markdown.
- Reconciliation: `obligation: "reconciliation"`, `producer: "lead"`, and
  `reason` recording the current/historical decision made from session signal.

On resumption, run `--completion recover --context-id "$context_id" --json`
for this exact task only. Read its current/pending obligations. After compaction
or lost knowledge, use a new live context token, personally reload the missing
required docs, then reattest startup; do not reset the task or repeat unchanged
checks. Ordinary source edits invalidate affected closure results, not valid
same-scope orientation. Instruction, repository, and worktree changes require
the appropriate reload. A persisted result never makes absent knowledge present.

## Phase 4 — Critic + gate (verify against code before advancing the baseline)
1. **Mechanical gate** — must pass:
   `python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-check.py" --repo "$repo_root" --completion mechanical --task "$task_id" --json`
   This runs the real mechanical checker and records its actual exit status and
   current content digest. A hand-written success field is not a substitute.
   The gate may also print `advisory` blocks — docs past `doc_max_lines`, work-trace files named without their `YYYY-MM-DD-` date prefix, and session-memory files (`docs/sessions/*.md`) still `open`. They are **not** part of "must pass" and never block the baseline. Report those lines and stop there: a long document or a legacy filename is the operator's call, and this command's licence to edit docs covers what *this session* changed, not a file that merely happens to be big or old. In particular, never let an advisory pull `docs/projects/**` into a trim — those folders are outside every automatic pass. The one case where it is already in scope: if the oversized file is `docs/active-context.md` itself, that is the Phase 3 shape gate firing, and Phase 3 owns it.

   **One obligation attaches to the oversized list, and only this one.** Every document it names must carry a recorded verdict in the `## Oversized docs — reviewed` section of `docs/harness-backlog.md`. Read that section, compare it with the gate's list, and append a row for each named document not already there. Create the section — and the backlog file, titled, if the repository has none — the first time this fires. This is the whole of the obligation: without it the size advisory is a sensor with a display and no actuator, which is how a document reaches 71 KB while being reported at every session for two months.

   | doc | lines at review | verdict | date |
   |---|---|---|---|
   | docs/known-issues-and-solutions.md | 1186 | split into docs/known-issues/ | 2026-08-24 |
   | docs/dependency-map.md | 684 | keep whole — read by section | 2026-08-24 |

   Two verdicts exist. `split` says the document should be cut up; that is work, so log it as an ordinary `OPEN` backlog entry too, and do not start it here. `keep whole` carries its reason on the same line — "read by section", "one argument that would cost three reads if split" — and is a decision, not a deferral. The rule that decides between them: **split logs, never split indexes.** A log is retrieved by search, so cutting it into one file per entry makes the search return a small file and the read small. An index is retrieved by traversal, so cutting it up buys more reads rather than fewer.

   **`split` means deletion, never relocation.** Four rules follow from that, and none of them is optional.

   **One. Splitting is a decision about what deserves to exist.** Start by deciding what in the document is still worth keeping, and delete the rest. Moving text is not a substitute for that decision: a relocation leaves the same words sitting in the repository, so one file's line count went down and the total cost to a reader went up.

   There is one legitimate move, and it is narrow. A document that has grown a **second subject** may be cut along that seam into a new document of its own — new file, its own title, its own routing line in `docs/README.md`, and a pointer left behind. Both halves must be coherent on their own, and a reader who wants one must not have to open the other. That is a split by subject, and it is what `docs/known-issues-and-solutions.md` → `docs/known-issues/` was.

   Everything else is an attic. Moving text into an **existing** document because it needed somewhere to go is forbidden, however plausible the destination sounds: the receiving document did not ask for it, nobody weighed whether it should still exist, and its own size advisory fires a few sessions later.

   **Two. Establish where text belongs before you move it, and check whether it is already there.** Text that duplicates what the destination already says is deleted. It is not moved.

   **Three. Never move text into a generated file.** A file rendered from a template — anything whose header says "regenerated by", "stamped from", "do not hand-edit", or the equivalent — is destroyed and rebuilt at its next render, and everything written into it by hand dies with it. If the content genuinely belongs there, it belongs in the template that produces the file. That is a change to the template's own repository, not to the rendered file.

   **Four. A durable document is never an append target.** An as-built or architecture document describes what the system *is*. Rationale, history, and why something changed are a different kind of writing, and they belong in a CHANGELOG or a dated brief. A document that accumulates entries over time has become a log, whatever its title says.

   When in doubt, delete rather than relocate. Git already holds the history.

   This step licenses one line in the backlog and nothing else: recording a verdict never edits the oversized document, including when the verdict is `split`. The split itself is ordinary work with an ordinary backlog entry, done deliberately later — not something this phase starts. A document already listed is never asked about again however far past the limit it has since grown, so the steady state of this step is zero work. `docs/projects/**` is out of scope here as everywhere above, and `docs/active-context.md` needs no row — an oversized living context is Phase 3's, not the ledger's.
    1b. **Keyword coverage check** — run `python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-keywords.py" --repo . --json`. This installed script reads commit subjects (baseline..HEAD from `docs/active-context.md`, falling back to the latest ten commits when the baseline is missing or unsuitable), extracts keywords, and checks whether those keywords appear in `README.md` and every `docs/**/*.md` file. For each keyword not found anywhere, ask: is the omission justified, or is documentation missing? Uncovered keywords are reported in the output's *keyword coverage* slot and never block the baseline on their own — but a keyword that describes a shipped capability and appears in no doc is a finding this command must surface, not silently pass. The script's own stop words and noise list keep the check focused on capability keywords rather than common English.
   If advisory-ledger or keyword repairs changed content after the recorded
   mechanical check, finish those edits, refresh the truthful lead impact and
   reconciliation attestations, and rerun the mechanical check. Reattest startup
   only for affected orientation content the lead actually holds. Do not force
   another full startup for ordinary source edits.

   For development and affected fast-path work, run its final focused real-user
   check through `--completion focused --input "$focused_check" --json`, with
   `{"argv": ["<executable>", "<argument>"]}` naming the actual command. It records
   the true exit/output digests and refuses a check that changes reviewed
   content. Documentation-only work does not acquire this extra obligation.

    2. **Semantic review** — first run `--completion snapshot --json` for the same repository/task and retain its exact digest. Then load and explicitly invoke the current `doc-critic/SKILL.md` (the complete entry; no sibling `WORKFLOW.md`) over every affected document: changed Markdown across committed, staged, unstaged, and untracked changes, affected unchanged docs, and missing documentation coverage. Always check active-context shape, including narrative inside valid headings. Generic reviewer approval does not replace this skill or establish semantic closure. Keep it separate from the mechanical gate. Repair STALE findings and rerun to zero STALE; preserve UNVERIFIABLE findings in output and never call them clean.

   Pass the explicit affected-document read scope to a delegated critic. Extra
   document reads require a concrete dependency on changed behavior; unrelated
   project/session histories and other work traces are not ambient audit input.
   Recursive metadata/link coverage remains the mechanical checker's job.

   Retain the actual critic output outside repository content. The lead submits
   a structured envelope with `--completion result --input "$critic_result" --json`:
   `schema_version: 1`, `task_id`, exact `repo` and `git_dir`, the checker-issued
   `snapshot`, real `producer`, `gate_kind: "critic"`, `skill: "doc-critic"`, actual `outcome`, complete
   `reviewed_docs`, `shape: "pass"|"fail"`, `deferrals`, and absolute `report`
   pointing to the retained raw result. The checker hashes both envelope and
   report. A delegated read-only critic returns its report; the parent records
   it without pretending the child wrote an artifact. Never write a desired
   verdict, invent provenance, or attach an old report to a fresh snapshot.
   `STALE`, `REVISE`, or an `UNVERIFIABLE`-only result refuses completion.
   `APPROVED` with explicit nonblocking `{claim, reason}` deferrals may pass only
   as qualified evidence (each deferral also requires `nonblocking: true`); it is not semantic-clean and cannot waive unmet
   acceptance criteria. Repaired content needs fresh affected evidence.
3. **Completion check before final review** — run:

   `python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-check.py" --repo "$repo_root" --completion check --task "$task_id" --context-id "$context_id" --phase pre-review --json`

   It must pass with current startup availability, impact, reconciliation,
   mechanical, critic, shape, work-trace, and applicable prior-review evidence.
   Missing or stale required results block completion. Repair the actual issue
   and rerun affected checks; do not refresh hashes around unchanged old reports.
   This explicit CLI check also governs documentation-only and affected fast-path
   work without a development reviewer.

   For substantial development, give a separate fresh final reviewer the
   approved brief/plan, actual prior verdict references, final-user results,
   this task/context ID, and completion evidence. The reviewer independently
   checks pre-review readiness and returns `REVISE` for missing/stale obligations.
   The final reviewer compares every current declared brief/plan/milestone
   source with its actual immutable approved version. Its final envelope must
   include `approved_versions`, one entry per earlier gate:
   `gate_key` (`brief-review`, `plan-review`, or `milestone-review:M1`), `source`,
   actual `approved_sha256` and `current_sha256`, `scope_preserved: true`,
   `substantive_changes: false`, and an evidence-based `comparison_reason`.
   This is a semantic attestation, not mechanical proof of equivalence. Progress
   notes alone do not force reapproval; substantive scope changes do. Never
   normalize or discard prose differences to make a comparison pass.
   Obtain a current `snapshot` and its `evidence_digest` immediately before
   that review. The final result must echo both; replacing supporting evidence
   invalidates final approval even when source bytes are unchanged. After an actual
   APPROVED verdict, the parent records a `gate_kind: "final-review"` result
   envelope with that snapshot, `evidence_digest`, and the actual raw report,
   as for the critic.
   A final approval covers only that content; later relevant edits reopen checks.

4. **Complete and finalize** — after all applicable reviews, run the full
   `--completion check --context-id "$context_id" --json` without `--phase`.
   Only after it passes run:

   `python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-check.py" --repo "$repo_root" --completion finalize --task "$task_id" --context-id "$context_id" --json`

   The checker rechecks freshness and performs only the reviewed baseline
   commit/date update and predeclared plan status transition. Do not edit those
   values by hand to bypass refusal. All prose changes, including active-context
   body changes, require affected verification again. Report the real result.
   The baseline means last reviewed real repository commit; dirty content remains
   separately represented and is never described as contained in that commit.
   A critic shape violation returns control to the lead's Phase 3 reconciliation
   and blocks finalization until repaired and reviewed.

These commands verify recorded coverage and freshness when invoked. The record
is an attestation plus hash-bound results, not authentication of a model's
judgment or proof the host blocks an agent that skips the entire workflow.

## Phase 5 — Release (only when authorized)
Runs only when release is authorized by the current task, after Phase 4 completion/final review and baseline advancement. Otherwise report `release: none, outside authorized scope` and stop this phase without edits. A configured release key alone does not authorize publication, commits, or pushes. The repository opts in through `release = <command>` in `docs/.doc-profile`: a command that takes one argument, `vX.Y.Z`, and refuses on its own preconditions (the kit's is `shared/scripts/release.sh`). Setting the key also opts the repository into the changelog format this phase reads: a root `CHANGELOG.md` with `## Unreleased` on top and one `## vX.Y.Z — YYYY-MM-DD` section per version, newest first.

Four skips, evaluated in this order and **before any edit**; each is the whole of the phase and goes in the output's *release* slot:
1. No `release` key ⇒ `release: not configured`.
2. `Unreleased` is empty — no line with a non-whitespace character between `## Unreleased` and the next version heading ⇒ `release: none, Unreleased empty`.
3. Not on the release branch — `main` unless the repository's own rule names another ⇒ `release: none, not on main`.
4. Tracked files carry changes that are not this run's consolidation edits ⇒ `release: none, uncommitted work in <paths>`. Someone else's half-done work is never released or committed by this phase.

Otherwise, cut it:
- **Choose the version** by semver from the `Unreleased` content, applied to the newest `## vX.Y.Z` heading: patch for fixes and documentation, minor for a new capability or a behavior change, major when the repository's rule says its protocol moved. A repository may state its own rule in its docs (the kit's is "Releasing" in `docs/documentation-harness.md`); the default above applies where none is stated.
- **Rewrite the changelog**: the `Unreleased` section becomes `## vX.Y.Z — <today>` with its content unchanged, and a fresh empty `## Unreleased` goes above it.
- **Commit and push, in this order**: first commit `CHANGELOG.md` alone, staged by path. After that commit, initialize a **new explicit documentation completion task**, with its own task ID, the new real HEAD as base, and the affected documentation scope. Perform fresh impact/reconciliation, mechanical, critic, and shape checks using the completion procedure above, then run full completion check and checker finalization for the baseline metadata. Do not reopen the finalized development task, hand-edit its baseline, or reuse its pre-commit closure snapshot. Prior code approval may be referenced but is not fresh documentation evidence. Commit the resulting consolidation edits, staged by explicit path, as a second commit; push both. The changelog commit is outside `docs/**`, so finalizing the baseline after it avoids false content drift; the subsequent docs-only consolidation commit is ignored by startup drift accounting. The release command requires a clean tracked tree at the remote tip, so neither commit is optional.
- **Run the command** exactly as the profile states it, from the repository root, with `vX.Y.Z` appended — a `bash …` or `./…` spelling may not match the repository's permission rule.

A refusal is yours to fix within these bounds: pick another version, push, commit edits this run made, repair a test this session broke. Never delete or move a tag, edit a protocol version constant to make the major fit, force-push, or commit tracked changes you did not make. When a refusal cannot be fixed inside those bounds, put the version section back under `Unreleased` and commit that revert alone. Initialize another new explicit documentation task bound to the revert HEAD, obtain fresh applicable closure evidence, and use checker finalization for baseline metadata before the docs-only follow-up commit. Push both and report `release: not cut — <the refusal's own reason>`. A failing completion check remains blocking; never hand-edit baseline values to finish this recovery. Success reports `release: vX.Y.Z cut`. The release is never handed to the operator as a next step.

## Output
`Session state consolidated. Baseline advanced to <sha>. [docs touched]. [mechanical gate: clean]. [completion: passed|qualified, <record reference>]. [oversized docs: N]. [undated traces: N]. [open sessions: N]. [keyword coverage: N covered / N total, N uncovered]. [semantic review: N confirmed, N repaired, N unverifiable]. [work trace: created|updated <slug> | not needed]. [release: vX.Y.Z cut | none, <reason> | not cut — <reason> | not configured]. [N plan steps completed. N harness gaps logged.]`

Report a qualified completion as qualified and retain every nonblocking
UNVERIFIABLE claim/reason; never relabel it semantic-clean. Keep only the small
record/reference in the final summary, not the stored evidence bodies.

The *oversized docs*, *undated traces*, and *open sessions* slots carry counts only, and each is omitted entirely when the gate reported none of its kind; reproduce the gate's advisory lines verbatim beneath the summary, adding nothing of your own. They never affect whether the baseline advances. The *work trace* slot is always present in one of its three forms — it is the explicit record of the Phase 3 trace decision, and `not needed` said out loud is the whole point. The *release* slot is likewise always present: Phase 5 either cut a version, skipped for a stated reason, could not cut and says why, or is not configured for this repository.

When a blocking condition survives the run, say so instead — never emit the advanced-baseline line for a baseline you did not advance: `Session state consolidated, BASELINE NOT ADVANCED — <blocking condition>. [docs touched]. [what remains to be done].`

When no gate fires, the whole output is the line `No consolidation needed.`, optionally followed by one short sentence naming the single fact that decided it. Do not narrate the gate-by-gate evaluation: this is the cheapest path through the command and it should read that way. You still had to open `docs/active-context.md` for the shape gate, so say `shape OK` — a silent no-op is indistinguishable from a check that was skipped.
