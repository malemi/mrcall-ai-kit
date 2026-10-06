# Tie the enforced protocol version to the release tags

**Date**: 2026-10-06 · **Plan**:
[`2026-10-06-protocol-release-invariant.md`](../execution-plans/2026-10-06-protocol-release-invariant.md).
Evidence verified 2026-10-06 against `main` @ edc784b, `git tag --list`,
`git ls-remote origin`, `gh auth status`, and the installed tree
`~/.config/mrcall-ai-kit`. Revised twice the same day after the brief gate
returned REVISE (lifecycle deadlocks, then merge/retry/branch-drift gaps).

## Problem

The 2026-10-01 release-versioning delivery tied release majors to the harness
protocol in one direction: `shared/scripts/release.sh` refuses to cut `vX.Y.Z`
unless `X` equals `HARNESS_VERSION` in `shared/scripts/doc-check.py`, and tags
are created only by releases. Nothing ties the third side — the protocol the
kit actually enforces — back to the tags. Commit edc784b raised
`HARNESS_VERSION` from 8 to 9 and was pushed to `main` with no v9 release.
Because this machine's installation is symlinks into the checkout
(`~/.config/mrcall-ai-kit/doc-check.py` and every `/doc-*` workflow resolve to
this checkout's working-tree files), every session on every repository here
immediately began enforcing unreleased protocol v9 while the newest tag
remained `v8.2.0`.

Observed damage (2026-10-06):

- Sessions in downstream repositories whose `docs/.doc-profile` says
  `harness_version = 8` are refused by design — "docs harness version 8 is
  older than installed version 9; explicitly migrate docs/ with doc-create" —
  pointing at a release that does not exist.
- The prescribed remedy is inoperable: the installation predates v9, so
  `~/.config/mrcall-ai-kit` has no `doc-migrate.py`, `doc-evidence.py`,
  `AGENTS.block.md`, or `legacy/`, and the installed `doc-create` cannot
  migrate (recorded in `docs/active-context.md`, Unresolved and Next).
- The operator's invariant is violated: protocol N is enforced iff a tag
  `vN.x.y` exists. Today commands enforce 9 with no v9 tag.

Root cause: the tag⟺release binding is checked only at cut time. No mechanical
check refuses a protocol bump that reached `main` without its release; the
rule exists in prose (`docs/documentation-harness.md`, "Releasing") and prose
is what the 2026-10-01 brief itself calls insufficient.

## Decision

The invariant: **in the checkout this machine actually runs, `HARNESS_VERSION`
equals the major of the newest release tag.** Enforced protocol N ⟺ tag
`vN.x.y` exists. The judgment surface is the working tree, not `origin/main`,
because the symlinked installation enforces whatever this checkout's files say
the moment they change — pushed or not, whichever branch is checked out.

1. **Repair now.** The operator authorized, in this task on 2026-10-06,
   cutting `v9.0.0` at the current HEAD through the documented `doc-end`
   Phase 5 flow (changelog rewrite, commits, push, `release.sh`, tag, GitHub
   Release), then re-running `./install.sh` so the installed kit gains the v9
   migration assets. After repair: newest tag major 9 == `HARNESS_VERSION` 9,
   and downstream refusals name a real release whose `doc-create` migration
   path is installed and operable. The repair runs before the check exists,
   so it cannot deadlock against it.
2. **Bump-and-release are one authorized act.** A `HARNESS_VERSION` bump may
   reach `main` only inside a task that is also authorized to cut its release;
   an unauthorized bump is forbidden and the gate treats it as a blocking
   violation until repaired (authorized release, or revert of the bump).
   Protocol development happens in a **linked worktree or separate clone**,
   never by checking a protocol branch out in the installed checkout itself;
   non-protocol work keeps landing on `main` directly, as before.
3. **Enforce mechanically.** `doc-check.py` gains an invariant check that
   activates only when the repository under check is the kit itself (it
   contains `shared/scripts/doc-check.py` with a `HARNESS_VERSION = N` line;
   no downstream repository has that path). Scope of enforcement:
   - **Installed checkout** — the resolved
     `${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-check.py` path lies
     inside the repository root, i.e. this checkout is what the machine
     enforces: the invariant applies on **every branch and detached HEAD**,
     because any state here leaks machine-wide through the symlinks.
   - **Any other checkout** (linked worktree, clone, copy-mode install):
     the invariant applies only on branch `main` (the release source);
     other branches and detached HEAD are silent, so development worktrees
     legitimately precede a release.

   `N` is compared with the major of the highest semver tag matching `vX.Y.Z`
   visible locally (highest by version sort, not newest by creation).
   Outcomes:
   - `N` equals that major → clean.
   - `N` ahead → **blocking violation** ("unreleased protocol: cut the
     authorized release via doc-end Phase 5, or revert the bump"), except
     when `CHANGELOG.md` carries a version heading matching
     `^## vN\.\d+\.\d+` — the state Phase 5 creates before invoking
     `release.sh` — which downgrades the finding to a **named advisory**
     ("release pending: vN section present, tag absent"). The advisory keeps
     Phase 4/5 completion checks and `release.sh`'s own gate step green
     without hiding the state.
   - `N` behind → **blocking violation** (`main` downgraded under its own
     release). The repair is an ordinary commit restoring the released
     protocol (revert of the downgrade); Phase 5's ban on editing
     `HARNESS_VERSION` to make a release major fit is untouched.
   - No matching tag visible → **advisory**, not violation (a fresh or shallow
     clone cannot know; the message suggests `git fetch --tags`, since the
     gate never fetches by itself).
4. **Amend Phase 5 for the protocol lifecycle** (edits to
   `shared/commands/doc-end.md` and its byte copy
   `codex/skills/doc-end/WORKFLOW.md`; `tests/test_codex_install.sh` compares
   them):
   - **Merge entry.** When the authorized release is a protocol major whose
     work sits on a branch, the phase — running on the release branch —
     proceeds in this order: (1) verify no tracked file carries uncommitted
     changes, the skip that must precede any merge; (2) merge the branch
     **fast-forward only** — it must already contain the release branch's
     tip, so the post-merge HEAD is exactly the HEAD Phase 4 reviewed and no
     conflict state can strand the checkout ahead-without-section; a branch
     that cannot fast-forward is refused, brought up to date with the release
     branch in its own worktree, and runs Phase 4 again; (3) evaluate the
     remaining skips and the version choice, which read the merged (branch)
     changelog; (4) perform the changelog rewrite; (5) only then permit any
     gate invocation. The skips are not gate runs, so the first gate the
     phase triggers already sees the version section and never observes the
     ahead-without-section state. Phase 4 completion/final review evidence,
     produced on the branch at its HEAD, carries over exactly because that
     HEAD is now the release HEAD; the phase's existing "new explicit
     documentation completion task" rule still rebinds fresh documentation
     evidence to the post-merge, post-changelog HEAD.
   - **Retry exit.** Before the four skips are evaluated: when the newest
     `## vX.Y.Z` heading in `CHANGELOG.md` has no tag of the same name and
     the current task authorizes that release, the phase re-runs the release
     command for that version (its preconditions are already staged) and the
     "Unreleased empty" skip does not apply. A retry triggered from a
     non-release branch or a dirty tree is harmless: the release command's
     own checks refuse both. While the newest version heading
     is untagged, `Unreleased` is never rewritten into a newer version, so a
     pending `vN.0.0` cannot be leapfrogged by a `vN.1.0`. This gives the
     retained-section state of a failed major release a documented exit; the
     rule is runtime-agnostic and serves any repository that keeps the
     changelog format, not only the kit.
   - **Major recovery.** When an unfixable `release.sh` refusal concerns a
     version whose major exceeds the newest tag's major, the version section
     stays committed and pushed — it is the pending-release marker and keeps
     the gate green as an advisory — and the phase reports
     `release: not cut — <reason>; version section retained`. Minor/patch
     releases keep the existing revert-into-Unreleased recovery.
5. **Document the rule** in `docs/documentation-harness.md` "Releasing": the
   invariant, the bump-and-release act, the worktree discipline, the gate
   outcomes and advisory semantics, the Phase 5 merge/retry/recovery rules,
   and the recorded limits below.

Recorded limits (the invariant is enforced at session start, closure, and
release time — not at the wire):

- A raw `git push` is not intercepted. A bump pushed from this checkout is
  caught here at the next gate run; a bump pushed from another clone does not
  change what this machine enforces until this checkout pulls it, and is
  caught then.
- A committed `## vN.` section whose release run died (e.g., between the
  changelog push and `release.sh`) rests in the advisory state — loud but
  non-blocking — until an authorized session completes the retry exit above.
- The gate reads local tags only; a stale local tag list can mask or fake a
  mismatch until `git fetch --tags`. The advisory message says so.

## Rejected alternatives

- **Pin installations to the newest tag** instead of symlinking HEAD: also
  satisfies the invariant, but it breaks the documented symlink development
  workflow ("edit kit = edit config"), contradicts `install.sh`'s stated
  modes, and would make the kit repository refuse itself between a bump and
  its release (v9 profile vs v8 commands). Bump-and-release atomicity gives
  the same guarantee without redesigning installation.
- **Judge `origin/main` instead of the working tree**: misses the actual
  enforcement surface — the symlinks expose the working tree on whatever
  branch is checked out, so even an uncommitted or unpushed bump already
  leaks machine-wide.
- **Silence non-`main` branches everywhere**: a protocol branch checked out
  in the installed checkout itself would enforce an unreleased protocol
  machine-wide with no finding — the same damage this brief exists to stop.
  Hence the installed-checkout tier, which needs no branch detection at all.
- **CI enforcement (GitHub Actions)**: the repository has no CI at all;
  standing one up is a larger infrastructure decision than this fix. The gate
  covers every session start in the kit repository and every release attempt.
- **A git hook that auto-releases on bump**: publication requires task
  authorization by design ("a configured release command never authorizes
  release"); a hook would release without it.
- **Soften the downstream refusal until v9 is released** (an unreleased
  checker tolerates older profiles): hides the true state, complicates the
  compatibility matrix, and rewards exactly the drift being fixed.
- **A separate "release pending" marker file** as the exemption: new
  machinery for a state the changelog version heading already expresses, and
  one more artifact to keep honest.
- **Prose-only rule**: rejected by the 2026-10-01 precedent — "the mismatch
  has to be refused mechanically".

## Acceptance

- `git ls-remote --tags origin` lists `v9.0.0` on the release commit;
  `gh release view v9.0.0` carries the `## v9.0.0` CHANGELOG section as body;
  tag message and release title are exactly `mrcall-ai-kit v9.0.0`;
  `release.sh` printed PASS for every check (its log is the record).
- `CHANGELOG.md`: `## v9.0.0 — 2026-10-06` holds the former Unreleased
  content verbatim; a fresh `## Unreleased` above it holds the enforcement
  entry.
- After the install re-run, `~/.config/mrcall-ai-kit` contains
  `doc-migrate.py`, `doc-evidence.py`, `AGENTS.block.md`, and `legacy/`;
  installed checker and workflows remain symlinks into the checkout; no
  operator-owned file was clobbered (installer's own listing is the record).
- The invariant check is proven by tests: equal → clean; ahead without a
  changelog section → violation; ahead with a `## vN.x.y` heading → advisory
  and gate exit 0; behind → violation; non-kit repository → silent; no tags →
  advisory; highest-semver tag chosen over newest-created; non-installed
  checkout on a non-`main` branch or detached HEAD → silent; installed
  checkout (fixture: `MRCALL_KIT_HOME` whose `doc-check.py` resolves into the
  fixture repository) → enforced on a non-`main` branch. Full suite
  (`tests/test_*.sh`, `pytest tests shared/scripts/tests`) and the gate pass
  at the delivery commit.
- The three Phase 5 amendments (merge entry, retry exit, major recovery)
  appear identically in both workflow copies and
  `tests/test_codex_install.sh` still passes.
- `docs/documentation-harness.md` "Releasing" states the invariant, the
  bump-and-release act, the worktree discipline, and the limits; doc-start in
  the kit repository reports a clean mechanical gate, valid baseline, and
  0 content commits behind after closure; doc-critic is clean over affected
  docs.
- A throwaway fixture repository with a v8 profile, checked with the installed
  checker after repair, is refused with the migrate-with-doc-create message,
  and the installed `doc-migrate.py` exists and runs (final-user path of the
  downstream story; actually migrating downstream repositories stays out of
  scope).

## Assumptions

- The 2026-10-06 authorization covers publishing `v9.0.0`: the work-trace
  commits of this brief and its plan on top of edc784b, the Phase 5 changelog
  and consolidation commits built on those, the push of `main`, the tag push,
  and the GitHub Release. The released content is the v9 adoption as committed
  at edc784b. No other version is published without new authorization; the
  enforcement work (items 3–5) lands on `main` after `v9.0.0` as ordinary
  commits and waits in `Unreleased` for a future authorized release.
- Downstream migrations (including `/home/mal/hb`) remain separate tasks,
  already listed in `docs/active-context.md` Next.
- No CI is introduced; no install mode changes.
- `docs/active-context.md`'s claim "The v9 adoption is uncommitted in the
  working tree" is stale (edc784b committed and pushed it) and is reconciled
  by this work's doc-end runs.
