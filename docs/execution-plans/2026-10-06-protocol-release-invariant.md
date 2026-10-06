---
status: active
brief: docs/briefs/2026-10-06-protocol-release-invariant.md
---

# Execution plan — protocol/release invariant: repair by releasing v9.0.0, then enforce

<!-- doc-scope:start -->
Scope: Ordered milestones to close the pending v9 state, cut the authorized
v9.0.0 release, refresh the installation, and mechanically enforce that the
checkout this machine runs never enforces a protocol without its release tag.
<!-- doc-scope:end -->

Brief: [`2026-10-06-protocol-release-invariant.md`](../briefs/2026-10-06-protocol-release-invariant.md),
`APPROVED` at its gate on 2026-10-06 after four REVISE rounds with the same
reviewer (B1/B2 lifecycle deadlocks; R1–R3 merge/retry/branch-drift gaps;
N1 unreviewed-merge content; O1 skip-ordering contradiction).

## Authority and classification

- Substantial development: brief and plan gates, milestone integration
  reviews, separate final review, doc-end closure with explicit completion
  tasks (T1/T2/T3 below).
- Operator authorization (in-task, 2026-10-06): publish `v9.0.0` — the
  closure and work-trace commits leading to it, the Phase 5 changelog and
  consolidation commits, the pushes of `main` those steps require, the tag
  push, and the GitHub Release — and re-run `./install.sh`. No other version
  is authorized. Landing the enforcement work on `main` (M2/M3 commits and
  their pushes, after their reviews) is the task the operator assigned.
- Complete push accounting (every `git push` this plan performs): M1a
  docs-only consolidation; M1b work trace; M1c Phase 5 changelog +
  consolidation pair; M2 delivery commit **after** its integration review;
  M3 closure consolidation. External publication happens only in M1c step 7
  (`release.sh`: tag push + GitHub Release) and its step-8 recovery.
- Evidence retention (for the final envelope's `approved_versions` and raw
  verdicts): `/tmp/opencode/protocol-release-invariant/` holds `approved/`
  (immutable approved bytes + `sha256` per gate: brief, plan, M1 source, M2
  source), `reports/` (raw reviewer verdicts as returned, including the
  brief-gate rounds and the plan-review log copied from
  `/tmp/mrcall-ai-kit/plan-review/reviewer.log`), and `logs/` (release.sh
  PASS log, installer output, probe script output). Captured at each gate,
  never reconstructed later.

## Established planning facts (verified 2026-10-06)

- `main` @ edc784b == `origin/main`; tree clean except this task's untracked
  brief/plan; `HARNESS_VERSION = 9` (shared/scripts/doc-check.py:21); tags
  v8.0.0/v8.1.0/v8.2.0 only; `gh` authenticated (malemi, `repo` scope);
  origin reachable; baseline c88b024 valid, 1 content commit behind (edc784b
  landed without closure — the reason M1a exists).
- `CHANGELOG.md` `## Unreleased` holds the v9 notes (non-empty).
- `~/.config/mrcall-ai-kit/doc-check.py` and `~/.agents/skills/doc-*` are
  symlinks into this checkout; the installed tree lacks `doc-migrate.py`,
  `doc-evidence.py`, `AGENTS.block.md`, `legacy/`.
- Phase 5 text: `shared/commands/doc-end.md` ≡ `codex/skills/doc-end/WORKFLOW.md`
  (byte copies; `tests/test_codex_install.sh` compares). `release.sh` checks
  1–9; its tag push can succeed while `gh release create` fails, and a
  re-run then refuses on "tag already exists" (lines 185–193) — M1c step 8
  carries the recovery. `tests/test_release.sh` stubs the checker, so M2's
  new check cannot affect it. No CI exists. Suite state at plan review:
  pytest 184 passed; 17/17 shell tests passed.

## M1 — Repair: close the pending v9 state, cut v9.0.0, refresh the installation

### M1a — Pre-release closure of edc784b (Phase 4 before Phase 5)

Phase 5 runs only after Phase 4 and baseline advancement, and edc784b has
had neither: it is the follow-up commit the 2026-10-05 delivery ended with
(its plan's Gate results record reviews through M6 adoption; edc784b's exact
bytes carry no recorded final-review coverage, and the baseline stopped at
c88b024). Completion task **T1** (`--completion init`, kind `documentation`,
base edc784b, scope `docs/active-context.md`): impact/reconciliation limited
to the stale claims — "v9 adoption is uncommitted in the working tree; no
release is cut" becomes the current truth (committed and pushed; release
v9.0.0 authorized in-task 2026-10-06, pending Phase 5 of this run). Critic
scope, stated in T1's impact attestation with this reason: the edited doc
(`docs/active-context.md`) plus the startup-critical docs edc784b changed
behavior in — `AGENTS.md` (managed block), `README.md` (index),
`shared/commands/doc-start.md` and `shared/commands/doc-end.md` (read once
per byte-copy pair) — and the shape check; the remainder of edc784b's
markdown is the 2026-10-05 delivery content covered by that plan's recorded
gates, and its generated/copied files are covered by the suite
(`test_agents_generated.sh`, `test_codex_install.sh`) which the mechanical
gate run executes. Then: mechanical; `--completion check`;
`--completion finalize` → baseline advances to edc784b. Commit the docs-only
consolidation by explicit paths; push. Between T1's init and its finalize,
the untracked brief and plan are part of T1's snapshot and are not edited.

### M1b — Work trace

Flip this plan's frontmatter to `status: active` (the `completed` transition
is declared to T3 and executed by its finalize, never hand-edited); commit
brief + plan by explicit paths; push.

### M1c — Phase 5, verbatim from the shipped workflow

1. Evaluate the four skips in order, before any edit: `release` key present;
   `Unreleased` non-empty; branch `main`; tracked tree clean. Any skip ends
   the release as `release: none, <reason>`; remaining steps drop.
2. Choose `v9.0.0` — major, per the repository rule ("Releasing": major is
   the protocol; the protocol moved 8→9).
3. Rewrite `CHANGELOG.md`: Unreleased content becomes `## v9.0.0 — 2026-10-06`
   verbatim; fresh empty `## Unreleased` above. Commit `CHANGELOG.md` alone,
   staged by path.
4. Initialize completion task **T2** (kind `documentation`) on the
   changelog-commit HEAD per the Phase 5 text: fresh impact/reconciliation
   (active-context records the release as authorized and in-flight in this
   run; M3 states the final past-tense truth), mechanical, critic, shape;
   `--completion check`; `--completion finalize` (baseline onto the
   changelog commit). Do not reopen T1 or hand-edit baseline metadata.
5. Commit the consolidation edits by explicit paths (docs only); push both
   commits. `HEAD == origin/main`, tracked tree clean.
6. Dry-run guard: `shared/scripts/release.sh v9.0.0 --dry-run` must print
   PASS for all nine checks (log to `logs/`). Any FAIL: repair within Phase
   5's bounds, or run its refusal recovery (section back under `Unreleased`,
   revert committed alone, fresh completion task bound to the revert HEAD,
   finalize, docs-only follow-up, push both, report `release: not cut —
   <reason>`).
7. **External, authorized**: run `shared/scripts/release.sh v9.0.0` exactly
   as the profile states it, from the repository root. Keep the full PASS
   log in `logs/` as the release record.
8. Half-release recovery (tag pushed, `gh release create` failed): a re-run
   refuses on "tag already exists" and Phase 5 forbids deleting or moving
   tags; complete the publication directly, inside the same authorization —
   `gh release create v9.0.0 --title "mrcall-ai-kit v9.0.0" --notes-file
   <the v9.0.0 section extracted to a temp file>` — then verify with
   `gh release view` and report the recovery in the release record.
9. Verify release: `git ls-remote --tags origin` lists `v9.0.0` at the
   pushed HEAD; `gh release view v9.0.0 --json name,body` shows title
   `mrcall-ai-kit v9.0.0` and body equal to the section; `git describe
   --tags` is `v9.0.0`.

### M1d — Installation refresh (guarded by a snapshot)

1. Snapshot before touching anything: `tar -czf
   /tmp/opencode/protocol-release-invariant/logs/installed-backup-2026-10-06.tgz`
   over the paths `installed.tsv` records (plus `~/.config/mrcall-ai-kit`,
   excluding `sessions/` and `__pycache__`). `--on-exist overwrite` makes no
   backups of its own; this tarball is the rollback.
2. `./install.sh --environment all --features all --mode symlink
   --on-exist overwrite --yes --dry-run`; diff the planned writes against
   `installed.tsv` and the installed tree; adjust flags if the dry-run shows
   clobbering of operator-owned files or changes any activation state (no
   `--activate-scope-guard`: existing activation stays as-is); then the real
   run, output to `logs/`.
3. Verify: `~/.config/mrcall-ai-kit` now holds `doc-migrate.py`,
   `doc-evidence.py`, `AGENTS.block.md`, `legacy/`; installed checker and
   workflows remain symlinks into the checkout; installer listed no
   operator-owned file as replaced.

### M1e — Downstream fixture probe (no real downstream repository touched)

Build a throwaway repo in `/tmp/opencode` with `docs/.doc-profile`
`harness_version = 8` and a minimal v8 docs layout; run the *installed*
checker on it — expect the migrate-with-doc-create refusal; run the installed
`doc-migrate.py` in help/dry mode — expect it to exist and operate.

- M1 Verify: M1a–M1e step-level verifications; `doc-check.py --repo .
  --startup --json` after M1c reports gate clean, baseline valid, 0 content
  commits behind (docs-only consolidation excepted per drift accounting).
- Integration review (fresh reviewer) after M1, before M2: retain the
  reviewed source snapshot (`CHANGELOG.md` bytes + sha256 → `approved/`,
  verdict → `reports/`).

## M2 — Enforce: the invariant check, its tests, the Phase 5 amendments, the rule text

1. `shared/scripts/doc-check.py`: the protocol/release invariant check per
   the brief's Decision 3 — kit-self detection (repo contains
   `shared/scripts/doc-check.py` with a `HARNESS_VERSION = N` line); tiers
   (installed checkout = realpath of
   `${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-check.py` inside the
   repo root → enforce on every branch and detached HEAD; otherwise enforce
   only on branch `main`); reference = highest semver among local tags
   matching `^v\d+\.\d+\.\d+$` (version-tuple sort; no fetch); outcomes:
   equal → silent; ahead → violation, downgraded to a named advisory when
   `CHANGELOG.md` has a heading matching `^## vN\.\d+\.\d+`; behind →
   violation; no visible tag → advisory. Messages name the repair and the
   `git fetch --tags` staleness caveat. Wiring: violations join the gate's
   blocking list (plain and `--startup`); the advisory joins the startup
   advisory payload under its own key.
2. `shared/scripts/tests/test_doc_check.py`: cases per the brief's
   Acceptance list — equal; ahead-without-section; ahead-with-section
   (advisory, exit 0); behind; non-kit repo silent; no tags advisory;
   highest-semver beats newest-created; non-installed checkout silent on
   non-`main` branch and detached HEAD; installed-checkout tier enforced on
   a non-`main` branch (fixture: `MRCALL_KIT_HOME` whose `doc-check.py`
   symlinks into the fixture repo).
3. Phase 5 amendments, byte-identical in `shared/commands/doc-end.md` and
   `codex/skills/doc-end/WORKFLOW.md` (merge entry with the fast-forward-only
   order and its undo — a skip firing after the merge resets the release
   branch to its pre-merge tip, safe because nothing was pushed; retry exit;
   major recovery retaining the section), exactly as specified in the
   approved brief's Decision item 4.
4. `docs/documentation-harness.md` "Releasing": the invariant, the
   bump-and-release act, the worktree discipline, gate outcomes, recorded
   limits.
5. `CHANGELOG.md`: entry under `## Unreleased` describing the enforcement.
   This is additive: the `## v9.0.0` section (M1's reviewed source) keeps
   its exact bytes — the justification the final reviewer's M1
   `substantive_changes: false` attestation rests on.
6. Local suite: `python3 -m pytest -q tests shared/scripts/tests`;
   `bash tests/test_codex_install.sh`; `bash tests/test_release.sh`; full
   `tests/test_*.sh` sweep; `doc-check.py --repo .` exit 0 here (9 == major
   of v9.0.0).
7. Commit M2 by explicit paths — **before** the probe, because the probe
   clones and a clone only sees committed code.
8. Live end-user probe as one script
   (`/tmp/opencode/protocol-release-invariant/logs/probe-invariant.sh`,
   output retained; re-invoked through `--completion focused` in M3):
   scratch clone of this local repository in /tmp (post-commit, so its
   checker carries the new check); in the clone bump **both**
   `HARNESS_VERSION` → 10 and `docs/.doc-profile` `harness_version` → 10
   (keeping the profile check equal, so only the invariant fires); then,
   running the clone's checker:
   (a) on the clone's `main` → expect the blocking violation; (b) with a
   `MRCALL_KIT_HOME` fixture resolving into the clone, on a new branch →
   expect enforcement off `main` (installed tier); (c) fixture removed, same
   branch → expect silence (non-installed tier, off `main`); (d) back on
   `main`, add a `## v10.0.0` heading → expect the advisory and exit 0;
   (e) `git tag v10.0.0` → expect clean. Discard the clone. The script
   exits 0 only when every expectation (a)–(e) holds (`--completion
   focused` requires exit 0) and runs with `MRCALL_KIT_HOME` unset except
   in step (b).
9. Initialize completion task **T3** — after the last M2 source edit and
   commit, because init hashes the checker and workflow files and any later
   edit to them is refused as "workflow versions changed" (`--completion
   init`, kind `development`, base = the post-M1 HEAD, scope = the M2/M3
   paths, workflows paths, `plan_transition: {path: this plan, from: active,
   to: completed}`, `reviews: {brief: <brief path>, plan: <this path>,
   milestones: {M1: CHANGELOG.md, M2: shared/scripts/doc-check.py}}`);
   record the already-held brief/plan/M1 verdicts with `--completion result`
   (approved bytes + sha256 from `approved/`, raw reports from `reports/`).
10. **Integration review (fresh reviewer) before the push**: retain the
    reviewed source snapshot (`shared/scripts/doc-check.py` bytes + sha256 →
    `approved/`, verdict → `reports/`); record with `--completion result`
    (gate_kind `milestone-review`, gate_id `M2`). Then push `main`. If this
    review returns REVISE and the repair edits `doc-check.py` or the
    workflow copies, T3 is permanently refused ("workflow versions
    changed"): the way out is a fresh T3 task ID with the earlier verdicts
    re-recorded against it.

## M3 — Close: final review, doc-end closure, baseline

1. Reconcile `docs/active-context.md` to the final truth **before any T3
   Phase 4 record** (every later record is snapshot-bound; editing after
   them would stale them all): v9.0.0 cut 2026-10-06 (tag sha, release
   published); installation refreshed with migration assets; invariant
   enforced; drop the resolved Unresolved/Next entries (missing migration
   assets, install re-run); downstream migrations remain Next. The plan's
   `active → completed` transition was declared in T3's input and is
   executed by its finalize, never by hand.
2. T3 Phase 4 in shipped order: refresh startup/impact/reconciliation
   attestations (impact covers: CHANGELOG.md, documentation-harness.md,
   active-context.md, both doc-end workflow copies, AGENTS.md unchanged but
   affected-contract, doc-start workflow unchanged); mechanical
   (`--completion mechanical`); focused (`--completion focused` re-invoking
   the probe script — it runs in /tmp and changes no reviewed content);
   `--completion snapshot`; doc-critic over the affected set incl. shape;
   critic result envelope; `--completion check --phase pre-review` — must
   pass.
3. Fresh final review: obtain a current `snapshot` + `evidence_digest`
   immediately before; hand the reviewer the approved brief/plan bytes with
   hashes, prior verdict references (brief ×5 rounds, plan rounds, M1, M2),
   final-user results (M1c/M1e/M2 step-8 logs), task/context IDs, and the
   completion evidence; the reviewer checks pre-review readiness and returns
   the `approved_versions` comparison (gate_key, source, approved_sha256,
   current_sha256, scope_preserved, substantive_changes, comparison_reason —
   for M1, `substantive_changes: false` rests on the step-5 note: only an
   additive Unreleased entry, the reviewed v9.0.0 section's bytes untouched)
   echoing snapshot and evidence_digest. Record the `final-review` result
   envelope. Later substantive edits reopen the review.
4. Full `--completion check` (no --phase), then `--completion finalize`
   (baseline lands on the HEAD at finalize time — the M2 delivery commit —
   plus the declared plan status transition). Commit the consolidation by
   explicit paths (docs-only, ignored by startup drift accounting); push.
5. Phase 5 evaluation for this closure: `Unreleased` is non-empty (M2's
   entry) but no release beyond v9.0.0 is authorized in this task → report
   `release: none, outside authorized scope`. The enforcement entry waits for
   a future authorized release (next minor, v9.1.0).
6. Final-user sanity: `doc-check.py --repo . --startup --json` shows gate
   clean, baseline valid, 0 content commits behind;
   `shared/scripts/release.sh v9.1.0 --dry-run` shows exactly one FAIL (no
   `## v9.1.0` section) and PASS elsewhere, gate and suites included.
7. Report to the operator: release record, enforcement evidence, residual
   limits (raw push; retained-section advisory; local-tag staleness), and
   the pending v9.1.0 authorization decision. Emit the doc-end output line.

## Dependencies and ownership

- M1a → M1b → M1c → M1d → M1e → M1 review → M2 → M2 review → M3, strictly
  sequential; one working tree, judgment-heavy, all in-session by the lead.
  Reviewers are fresh agents at each gate (the brief and plan gates reuse
  their own reviewer across REVISE rounds, per protocol).
- T1 closes edc784b; T2 is Phase 5's own task; T3 is this delivery's
  development task and carries the brief/plan/milestone/final review
  evidence and the plan transition.

## What this plan does not establish

- No CI and no wire-level push interception: enforcement fires at session
  start, closure, and release time in the checkout this machine runs.
- Downstream repositories are not migrated here (separate tasks, already in
  active-context Next).
- Runtime behavior of the amended Phase 5 text inside Claude/Codex/OpenCode
  sessions is instruction-level; only the byte copies and their comparison
  test are verified mechanically.

## Gate results

- Brief gate: REVISE ×4 → APPROVED (same reviewer, 2026-10-06). Rounds:
  (1) B1 bump-deadlock before Phase 5, B2 recovery deadlock + silent lasting
  exemption; (2) R1 no merge step to main, R2 no retry exit, R3 branch drift
  in the installed checkout; (3) N1 non-fast-forward merge would release
  unreviewed content; (4) O1 rewrite-before-skips ordering contradiction.
  APPROVED with one non-blocking note (merge undo), folded into M2 step 4.
  Raw verdicts retained in `reports/`.
- Plan gate: round 1 REVISE (same reviewer to re-judge): B1 Phase 5 without
  Phase 4 over edc784b → M1a added; B2 half-release stranding → M1c step 8
  recovery; B3 overwrite has no backup → M1d snapshot; B4 probe
  self-contradictory (profile vs constant, silent post-tag branch) → M2
  step 8 rewritten; B5 final-review ordering, pre-review phase, approved
  versions retention, plan-status via finalize → M3 rewritten, retention
  directory added, T3 declared; B6 push accounting → Authority section, M2
  push moved after its review.
- Plan gate round 2: REVISE, round-1 findings all closed. R2-1 T3 init
  hashed the checker/workflow files before M2 edited them ("workflow
  versions changed" refusal) → T3 init moved to M2 step 9, after the last
  source edit and commit, base = post-M1 HEAD. R2-2 probe cloned before the
  M2 commit, testing old code → commit moved ahead of the probe (steps 7–8).
  R2-3 M3 reconciled active-context after the snapshot-bound records →
  reconciliation is now M3 step 1, before every Phase 4 record.
  Non-blocking folded: baseline lands on the M2 delivery commit (M3 step 4
  wording); M1 approved-version justification for the later additive
  CHANGELOG entry written into M2 step 5 and M3 step 3; T1 critic scope
  bounded and reasoned in M1a (edc784b is the 2026-10-05 delivery's
  follow-up commit; startup-critical docs re-criticized, delivery content
  rests on that plan's recorded gates, generated copies on the suite).
- Plan gate round 3: **APPROVED** (same reviewer, 2026-10-06; approved bytes
  retained, sha256 76d43151d093a8393d5a426546ac1229122ca108aae0c8f577b1c6ae970b2bd8).
  Its three non-blocking notes were folded in as progress notes after
  retention: M2 step 10 (a REVISE repair touching hashed files needs a
  fresh T3 ID), M1a (brief/plan frozen between T1 init and finalize),
  M2 step 8 (probe exits 0 only on all-pass; `MRCALL_KIT_HOME` unset except
  in (b)).

## State

- 2026-10-06: plan APPROVED at round 3. M1a done: T1 finalized (completion
  qualified — two nonblocking UNVERIFIABLE deferrals in the critic report),
  baseline advanced to edc784b, consolidation commit c7eee0d pushed. M1b
  committing the work trace; M1c (Phase 5, v9.0.0) next.
