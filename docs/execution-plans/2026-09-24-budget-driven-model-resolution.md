---
status: active
---

# Execution plan: roles, then a budget that resolves their models

Brief: [`docs/briefs/2026-09-24-budget-driven-model-resolution.md`](../briefs/2026-09-24-budget-driven-model-resolution.md),
approved at round 4. This plan builds what it describes, in six milestones.
It also closes the rename half of item 1 in
[`2026-09-22-kit-agent-layer-and-issue-visibility.md`](2026-09-22-kit-agent-layer-and-issue-visibility.md).

## How the work is carried

**Everything happens in a git worktree, not in the main checkout.** On this
machine `~/.claude/agents/worker-*.md` and `~/.claude/skills/kit-role-rules` are
symlinks into the main checkout. Editing the checkout edits the operator's live
agents in every running session. The work therefore happens in a worktree under
this session's scratchpad, on a branch `budget-roles` taken from `main`, and
nothing reaches the live agents until the branch is merged. The scratchpad is
under `/tmp`, which this machine empties at boot. A commit survives a reboot,
because it lives in the main repository's object store. Uncommitted work does
not, so no milestone stays uncommitted longer than it takes to finish it.

**One commit per milestone, on the branch**, staged by explicit path (`git rm`
for deletions). The brief and this plan land first, as a docs-only commit on
`main`: `docs/` is never installed, so that commit reaches nothing live.
Nothing is pushed.

**Every milestone ends in an integration review** by a fresh reviewer, before
the next one starts. Until the merge, the reviewer is the live `worker-opus`.
Each reviewer reads the session file first
(`hb/docs/sessions/bf41db18-1d84-4ad8-b358-2fb5491ec60b.md`) and appends its
verdict there.

**The full gate runs at the end of every milestone,** and its output goes in
the milestone report. It has four parts:

1. Every `tests/test_*.sh` passes. From M1 on this includes
   `tests/test_retired_names.sh`, the name sweep described in M1, so the naming
   rule of AC8 is checked on every tree up to the final one.
2. `python3 -m unittest discover -s tests -p 'test_*.py'` passes, and so does
   the same command with `-s shared/scripts/tests`.
3. `python3 shared/scripts/build-agents.py --check` reports the tree in sync.
4. `python3 shared/scripts/doc-check.py` prints `MECHANICAL GATE CLEAN`.

At the base commit `579ee98` all four pass: ten shell tests, both unittest runs,
the generator check, and the doc gate.

**The merge is the operator's call on timing.** When M2 is reviewed, the roles
and the migration are complete and mergeable on their own. The operator is then
asked whether to merge them at once or to hold everything for one merge after
M6. Every merge follows the procedure in M6: snapshot, merge, reinstall, and
live checks, with the snapshot as the rollback. A merge without a reinstall
would leave this machine's `worker-*` symlinks dangling.

## M1 — Roles replace the model-named agents

Depends on: nothing. Owner: the lead.

- **Stubs.** New stubs `claude--execute`, `claude--verify`, `claude--reviewer`,
  `opencode--execute` and `opencode--verify` are added. `opencode--reviewer`,
  `--plan`, `--build` and `--orchestrator` keep their names. Their descriptions
  stop naming a vendor, and their task permissions change from `worker-*: allow`
  to `execute: allow` and `verify: allow`. The nineteen `*--worker-*` stubs are
  deleted. Each stub carries the interim model from the brief's rename table.
- **Role text is written once.** `shared/roles/agents.json` gains a `role`
  field. `build-agents.py` then composes each agent from its stub, its role
  text (`execute.md`, `verify.md` or `review.md`), the non-negotiable rules in
  `common.md`, the three shared blocks, and the report format. OpenCode gets
  all of this inline. Claude Code gets the shared parts through
  `kit-role-rules`, whose body grows to hold them.
- **Each text lives once.** Where `common.md` and `worker-report.md` repeat a
  block, the shipped block wins and the copy goes. The copies differ by a clause
  or two, and the block is what agents carry today. `plan.md` and
  `orchestrate.md` stay unwired, since the OpenCode leads keep their own bodies.
  `orchestrate.md`'s model section is still rewritten, as the brief requires.
- **Generated files.** The three `claude/agents/worker-*.md` and the sixteen
  `opencode/agents/worker-*.md` are deleted. The role files and the skill are
  regenerated.
- **Model choice becomes role choice** in the five texts the brief names:
  `shared/roles/orchestrate.md:30-35`, `shared/tutorial.md:129-131`,
  `docs/model-router.md:20-25`, `opencode/skills/orchestrator/SKILL.md:102-104`
  and `AGENTS.md:41-42`.
- **Commands.** `shared/commands/doc-start.md:20` and `doc-end.md:12-15`, plus
  both Codex `WORKFLOW.md` mirrors, name `execute` and `verify`.
- **Installer.**
  - `workers` keeps its flag name, which is public, and installs OpenCode's
    `execute` and `verify`.
  - `router` without `doc-harness` installs Claude's three roles and the skill
    in place of `worker-fable`.
  - `router` installs `claude/commands/router.md` alone. Today it copies every
    file in `claude/commands` (`install.sh:335`). That includes `/sc`, whose
    first step registers a hook script that only `--features reread` installs.
    A router-only reinstall on this machine would therefore let `/sc` register
    a hook pointing at a missing file. `test_router_install.sh` gains the
    assertion that a router-only install ships no `sc.md`.
  - `orchestration` stops shipping `llms.md`.
  - Help and prompt texts change to match.
  - Nothing installed is retired yet. That is M2.
- **Retired from the repository.** `llms.md`, and every reference to it.
- **The retired names get one home.** `shared/roles/retired.txt` lists every
  file this change retires, one per line. Each line holds two tab-separated
  fields: the repository path and the install destination under `$HOME`. It
  covers the nineteen worker files and `llms.md`, whose destination is
  `.config/opencode/llms.md`. It is the only live file allowed to name them.
  M2's migration, its test, and M1's own `llms.md` assertion in
  `test_orchestration_install.sh` all read the names from it.
- **Docs.** `README.md`, `AGENTS.md` (layout lines),
  `docs/documentation-harness.md`, `docs/model-router.md`,
  `docs/harness-backlog.md` (the `worker-fable` item), the tutorial's workers
  section and its proof path, and `shared/roles/README.md` (the taxonomy is now
  wired) all describe roles. Incident records in
  `docs/known-issues-and-solutions.md` keep their names.
- **Tests follow the names.** `test_agent_profiles.sh:10-11,38-41,140-150`,
  `test_router_install.sh:18-28,47-58,69`, `test_orchestration_install.sh`
  (which now asserts that `llms.md` is not shipped), `test_agents_generated.sh`
  and `test_tutorial_covers_features.sh`, through the proof path at
  `shared/tutorial.md:117`. A new install assertion checks that every installed
  Claude agent's `skills:` names an installed skill. That is the gap behind
  today's live fix.

**Verification**, beyond the full gate:

1. **Name sweep.** A new `tests/test_retired_names.sh` derives the old names
   from `retired.txt`: each basename without `.md`, plus the literal `worker-*`
   and `llms.md`. It runs `git grep -n -F` with every name as a fixed-string
   pattern, excluding `docs/briefs/`, `docs/execution-plans/`,
   `docs/active-context-archive.md`, `docs/known-issues-and-solutions.md` and
   `retired.txt` itself. It fails on any hit. Because the patterns are fixed
   strings, `worker-*` matches the literal permission pattern, not every
   occurrence of "worker". The test belongs to the full gate from M1 on.
2. **Content sweep.** Every rule line in the nineteen old worker stubs at
   `579ee98` is traced to a line in the new generated files. Each line that is
   not traced is listed as model-specific and dropped, and the reviewer judges
   the list. This is the standard the deduplication met: zero lines lost,
   checked line by line.
3. **Source sweep.** Every bolded rule and every bullet rule in the new files is
   found, as a phrase, in an agent file at `579ee98`, or is listed as an
   intended change. This is the check that caught absorbed text last time.
4. **OpenCode, real binary.** In a temporary home, a copy install and a symlink
   install each run `opencode debug agent` for `execute`, `verify`, `reviewer`,
   `build`, `plan` and `orchestrator`. Each resolves with its interim model
   string, its permissions, and a prompt that carries the rules.
5. **Claude Code, real binary.** A personal skill shadows a project skill of the
   same name. This was measured today: a project `kit-role-rules` carrying a
   codeword did not reach a subagent that preloads that name, while the live
   personal copy did. So the test copies the generated agents into a temporary
   project's `.claude/agents/`, with their `skills:` line renamed to
   `kit-role-rules-candidate`. It copies the generated skill into
   `.claude/skills/kit-role-rules-candidate/`, under that name. `claude -p` on
   Haiku then delegates to `execute`, `verify` and `reviewer`. Each subagent's
   transcript must show its interim model. Each must quote a sentence that
   exists only in the grown skill: a rule from `common.md`, which neither the
   old skill nor any new agent body contains. The real name is checked live, at
   merge time, with the same sentence.

**Rollback.** Nothing is live until the merge, and the branch holds everything.

## M2 — Installed machines migrate

Depends on: M1. Owner: the lead.

- `install.sh` retires the files named in `shared/roles/retired.txt`, as the
  brief says.
  - A file under a retired name is the kit's if the manifest records it, or if
    its bytes equal a blob the kit shipped at that path:
    `git -C <checkout> log --all --find-object=<blob> -- <path>`.
  - Retiring follows `--on-exist`. `overwrite` deletes the file, `backup` backs
    it up, and `skip` only reports it.
  - Anything else under a retired name stays, and the installer reports it.
  - `--dry-run` lists what would be retired.
- **Backups of directories move out of the runtimes' scan paths.** OpenCode
  loads a skill from a directory renamed `<name>.bak`. This was measured today:
  a lone `skills/foo.bak/SKILL.md` loaded as the skill `foo`. So a directory
  that `backup` replaces moves to
  `~/.config/mrcall-ai-kit/backups/<path under $HOME>`, recorded in the
  manifest's backup column, which `uninstall.sh --restore-backups` already reads.
  Files keep `<file>.bak`. `opencode debug agent` ignores a `.md.bak` agent.
  `--help` says so.
- `tests/test_role_migration.sh` seeds a temporary home with this machine's
  shape. The retired names come from `retired.txt`:
  - old files the manifest records;
  - unrecorded old files, byte-identical to shipped blobs;
  - one unrecorded old file that has been modified;
  - an old-name `llms.md` that matches no shipped blob;
  - the orchestrator skill as a directory;
  - four foreign agents.

  It installs under each `--on-exist` value and asserts each outcome. In the
  backup case, `opencode debug skill` lists exactly one `orchestrator`: the new
  one. That assertion is skipped, with a message, when `opencode` is not on the
  PATH, so the full gate still runs on a machine without OpenCode.

**Verification.** The full gate, including the new test. Then a `--dry-run` in
a temporary home seeded with copies of this machine's
`~/.claude/agents/`, `~/.config/opencode/agents/`, `~/.config/opencode/llms.md`
and `installed.tsv`, with the manifest's paths rewritten to that home. Its
output must list the retirements the brief predicts:
- the three Claude workers, found through the manifest;
- the sixteen OpenCode workers, found by their bytes;
- `llms.md`, reported and kept.

**Checkpoint.** The merge question goes to the operator here.

## M3 — The resolver, its requirements, and the first refresh

Depends on: M1, because the requirements name roles. Owner: the lead.

- `shared/roles/requirements.json` holds each role's rule, index and floor per
  runtime, and each runtime's ceilings per budget. The values are the
  operator's: $5/$20/none for OpenCode, $10/$20/none for Claude Code, and a
  coding floor of 73. It also holds the common requirements: tools, 200k
  context, no `:batch` or `:free` variants, and an intelligence score.
- `shared/scripts/resolve-models.py` does the following.
  - **Reads** the catalogue, and the benchmarks with `OPENROUTER_API_KEY`. If it
    cannot read either one, it exits non-zero and writes nothing.
  - **Joins** on `canonical_slug`.
  - **Resolves** every runtime, budget and role by the brief's rules, including
    the raised ceiling and the below-floor flag.
  - **Maps ids.** A Claude id has its dots replaced with dashes. An OpenCode id
    becomes `openrouter/<id>`, filtered through `opencode models` when OpenCode
    is on the PATH.
  - **Prints the diff.** The old side is the model in each current generated
    agent file, which is what the agents run now; the new side is the
    resolution. `--apply` writes `models.json`, holding the selection with its
    scores, prices and `as_of`.
  - **Runs offline.** `--fixture <dir>` runs the same code from saved payloads.
- `tests/test_resolver.py` (unittest), on fixtures, covers:
  - each rule: maximise, satisfice, below-floor and the raised ceiling;
  - both tie-breaks;
  - each exclusion: no tools, short context, a variant, a missing role index and
    a missing intelligence score;
  - an unreadable endpoint, and a role with no candidate at any price;
  - the id mapping and the reachability filter;
  - AC3: a run without `--apply` leaves `models.json` byte-identical;
  - AC7: on every budget and runtime, on the fixtures and on the committed
    `models.json`.
- **The first applied refresh**, run with the key the operator authorized for
  this session, commits `models.json`. Its diff against the interim models goes
  in the milestone report.

M3 changes no agent file, and `models.json` stays inert until M4.

**Verification.** The full gate. The refresh output reproduces the brief's
decided-values tables, or the report names each price or score that moved since
2026-09-24.

## M4 — One rendering per budget, all installed

Depends on: M2 and M3. Owner: the lead.

- **Rendering.** Stubs lose `model:`. `build-agents.py` renders every agent once
  per budget into `<runtime>/agents/<budget>/<name>.md`, taking the model from
  `models.json`. The flat `<runtime>/agents/<name>.md` files go away.
- **The readers of the flat paths move with them:**
  - `install.sh`: the `--list` inventory, the doc-harness `claude/agents` sweep,
    the router add, and the OpenCode role and worker adds;
  - `test_agents_generated.sh:24,38,59`;
  - `test_agent_profiles.sh:10,38-41`;
  - `test_router_install.sh`;
  - the tutorial's proof paths, which `test_tutorial_covers_features.sh:30`
    resolves against `<base>/agents/`;
  - `shared/scripts/ai-help.sh`, which lists installed agents, not repository
    paths, and is re-checked.
- **The gate.** `test_agents_generated.sh` checks every rendering against its
  sources. It also checks that regenerating is a no-op, that no stub names a
  model (AC2), and that every rendered model equals `models.json`.
- **Installing.** `install.sh` installs all three renderings of each kit agent
  under `~/.config/mrcall-ai-kit/agents/<runtime>/<budget>/`.
  - It places the rendering for the machine's budget at the runtime's own path.
    The budget comes from `~/.config/mrcall-ai-kit/budget`, and is medium when
    that file is absent.
  - Both placements follow the install mode, and both are recorded in the
    manifest, so `uninstall.sh` needs no new logic.

**Verification.** The full gate, then these, in temporary homes:

- Copy and symlink installs put the medium renderings at the runtime paths and
  all three renderings under the kit's home.
- With a budget file set to low, the low renderings are placed instead.
- `opencode debug agent verify` shows the medium model string after the default
  install and the low one after the low install.

## M5 — `/ai-budget`

Depends on: M4. Owner: the lead.

- `shared/scripts/ai-budget.py` is installed to the kit's home, and the
  `shared/commands/ai-budget.md` command calls it on both runtimes, the way
  `/ai-help` calls its script.
- With a level, the script:
  - records the level;
  - moves each runtime agent file in the manifest to that level's installed
    rendering, re-pointing it in symlink mode and re-copying it in copy mode;
  - updates the manifest and prints each role's model;
  - says the switch applies to sessions started after it (AC1).

  With no level, it prints the budget and each role's model. An unknown level
  changes nothing.
- The tutorial gains the section its gate requires, and `install.sh --help`
  lists the command.
- `tests/test_ai_budget.sh` covers four cases:
  - in copy mode, a switch reads nothing from the checkout, because the test
    moves the checkout away before switching (AC9);
  - in symlink mode, a switch re-points;
  - an invalid level changes nothing;
  - the status output.

**Verification.** The full gate, then these:

- In a temporary home, `ai-budget low` followed by `opencode debug agent verify`
  shows the low model string, and `ai-budget high` shows the high one.
- A temporary project's `.claude/agents/` holds copies of the temporary home's
  switched Claude agents, with the skill name renamed as in M1. For each level,
  `claude -p` delegates to `verify` and `execute`, and each subagent's
  transcript shows that level's model.

## M6 — Docs, final review, merge

Depends on: M5. Owner: the lead. The operator decides when to merge.

- **Docs.** Reconcile `README.md`, the `AGENTS.md` index, `docs/README.md`,
  `docs/model-router.md`, `docs/documentation-harness.md` and
  `docs/active-context.md` to the system as built. Then:
  - Add an incident to `docs/known-issues-and-solutions.md`: the role skill was
    never installed on this machine, so from `33c3b18` until today's live fix
    the Claude workers ran without the shared blocks.
  - Put in `docs/harness-backlog.md` whatever part of that gap M1's install
    assertion does not close.
  - Mark the 2026-09-22 plan's rename as done here.
  - Set this plan to `completed` after the merge.
- **Final review.** A separate reviewer judges the final-user path, after the
  full gate. Two of the checks need what a reviewer is not given: the refresh
  needs the OpenRouter key, and the Claude probes need the operator's login.
  The lead runs those two, and the reviewer judges their saved output. The
  checks are:
  - installs into temporary homes, in copy mode and in symlink mode;
  - migration from a replica of this machine's layout;
  - `ai-budget` at each level, with `opencode debug agent` and the Claude
    project probe at each;
  - a fresh refresh without `--apply`, whose diff shows how far prices moved
    since M3.
- **Merge and reinstall, when the operator says.**
  1. **Snapshot.** Run each install command below with `--dry-run` first. Put
     every destination it lists, including retirements, together with
     `~/.config/mrcall-ai-kit/installed.tsv`, into
     `~/.config/mrcall-ai-kit/pre-roles-<date>.tgz`, with symlinks kept as
     symlinks. Record the manifest's line count.
  2. **Merge.** Record `main`'s SHA. If `main` has moved, rebase the branch
     and run the full gate again. Then fast-forward `main` in the main
     checkout.
  3. **Reinstall**, in this machine's recorded modes, from the main checkout:

     ```
     ./install.sh --environment claude   --features doc-harness,router        --mode symlink --on-exist overwrite --yes
     ./install.sh --environment opencode --features doc-harness               --mode symlink --on-exist overwrite --yes
     ./install.sh --environment opencode --features orchestration,workers     --mode copy    --on-exist overwrite --yes
     ```

     The mode per feature follows the manifest. On OpenCode, the doc-harness
     commands, `doc-critic` and the kit-home scripts are symlinks, while the
     role agents and the orchestrator command and skill are copies. The Codex
     skills are directory symlinks into the checkout, so the merge updates them
     with no reinstall.
     `overwrite` rather than `backup` is chosen for two reasons: the snapshot is
     the rollback, and a backup keeps one generation only (`install.sh:80-81`).
     What gets overwritten is safe to lose. Every July OpenCode copy it replaces
     is byte-identical to a version the kit shipped (`2cf0206`, and `890464f`
     for the skill), so no local edit is lost.
     The reinstall also brings this machine's install up to date beyond this
     change. `doc-harness` adds `/ai-tutorial` and its script, which the
     manifest does not record. That is expected, and the snapshot covers its
     rollback. With M1's router fix, `/sc` is not added.
  4. **Live checks.**
     - A real `execute` quotes the grown skill's `common.md` sentence under the
       real skill name.
     - `opencode debug agent build`, `execute` and `verify` resolve.
     - `opencode debug skill` lists one `orchestrator`.
     - `/ai-budget` with no argument reports medium. This check applies only
       to a merge that includes M5. A merge at M2 checks the three roles and
       the retirements instead.
     - One real OpenCode delegation, `build` handing a trivial task to
       `execute`, costs a small model call on the operator's providers. It runs
       only if he agrees.
  5. **Rollback**, if any check fails:
     - `git -C <checkout> reset --keep <recorded SHA>`.
     - Delete every destination in the manifest lines appended after the
       recorded count.
     - Restore the snapshot.

     Anything written to those paths after the snapshot is lost. The window is
     the minutes between steps 1 and 5.

## What this plan does not establish

- **Output quality.** No milestone measures whether a resolved model does a
  role's job better than the hand-chosen one.
- **That a model exists.** `opencode debug agent` exits 0 for a model that does
  not exist, as the plan reviewer found. The checks that use it prove the model
  string in the frontmatter, not that the model can be called. Callability is
  checked once, by M3's `opencode models` filter, on this machine.
- **OpenCode delegation with a model call.** It happens only at merge time, with
  the operator's agreement.
- **Claude Code in a user-level install before the merge.** Pre-merge checks use
  project-level agents under a renamed skill, because a personal skill of the
  same name wins. The real names are checked live after the merge.
- **Other machines.** Their install state and providers are not checked.
- **A session already running** was measured in M5, not assumed: Claude Code
  applies an edit to a project agent from its next delegation, and OpenCode a
  switch from its next start, as `docs/known-issues-and-solutions.md` records.
  That Claude Code does the same for a user-level agent, which is what
  `/ai-budget` edits, is inferred, and that entry says so.
- **Codex** is out of scope: the kit ships no Codex agents.
