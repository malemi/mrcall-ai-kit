---
status: completed
brief: docs/briefs/2026-09-27-reread-guard-cross-runtime.md
---

# Execution plan — re-read pass on OpenCode and Codex

Brief: [`2026-09-27-reread-guard-cross-runtime.md`](../briefs/2026-09-27-reread-guard-cross-runtime.md), approved after the repairs recorded in
`docs/sessions/ses_f1bfb5f77fferiY4VG5CqO4fRL.md`. Independent plan review:
`APPROVED` on 2026-09-28. M1 and M2 are reviewed. On 2026-09-28 the operator
waived a repeat live Claude Code check because the existing `/sc` had worked
before this port. M3 and final integration review are approved against that
revised acceptance boundary.

## Decisions and boundary

- Claude Code retains its Stop-hook control, including `SC_MIN_CHARS=500`,
  one-shot arming, and its existing `on`/`off`/`status` behavior. OpenCode and
  Codex get an instruction-based one-shot pass on every answer length. They
  get no persistent flag, hook, plugin, or `on`/`off`/`status` mode.
- Keep `shared/roles/reread-checklist.md` as the single checklist. Put the
  common in-turn procedure in `shared/shortcuts/sc-core.md` and install it once
  at `~/.config/mrcall-ai-kit/sc-core.md`. Make
  `opencode/commands/sc.md` and `codex/skills/sc/SKILL.md` thin entry points:
  each gets the current question from its own runtime, loads that installed
  procedure and checklist, applies the pass, and returns only the answer.
  OpenCode injects the two files during command expansion, avoiding an
  external-directory read-tool denial observed in the real client. Codex
  reads them through its skill. The
  Codex skill description instructs invocation only for a literal `$sc` at
  message start or an explicit request, never on the model's own initiative.
  This shares the procedure without pretending that the two runtime entry
  formats are byte-identical.
- A missing question yields a one-line usage response. On OpenCode and Codex,
  `on`, `off`, `status`, and `unregister` as the entire argument yield a one-line
  unsupported mode response; they do not create state or get silently treated
  as questions. Normal repository work, tool use, review gates, and router session-memory
  updates continue when the question calls for them. The pass changes the
  answer, not the work contract.
- No change to `shared/roles/retired.txt` is needed: the discarded stubs were
  never shipped. A later rename of a shipped entry must use that registry.

## M1 — In-turn entry points

Create the common procedure and two thin entry points named above. The entry
point supplies the installed checklist at invocation time or reads it through
a tool, then drafts the answer,
checks it against each checklist item, repairs failures, and emits only the
final answer. If the common procedure or checklist cannot be read, report the
missing install artifact instead of claiming a pass. It makes no Claude Stop
hook or pre-delivery enforcement claim. Keep the normal work instructions in
force; `$sc` is not an `nr`-style suspension of tools or gates.

Verification: inspect both entry points for their argument and trigger
contracts, missing-artifact behavior, and lack of duplicate checklist text.
Check that the common procedure names the installed paths, that the Codex
skill metadata is discoverable, and that the OpenCode command uses
`$ARGUMENTS`. At this milestone the files are source artifacts only; no claim
of runtime behavior follows from inspection.

Ownership: implement as one bounded change. A fresh reviewer checks the
artifact contracts against the brief before M2.

Review: `APPROVED` by a fresh M1 reviewer on 2026-09-28. The initial source
artifacts met the entry-point contract. Live-client QA later exposed an
OpenCode external-directory read denial and a Codex progress announcement;
the entry points were corrected and re-reviewed with M3 evidence.

## M2 — Feature wiring, lifecycle, and user-facing truth

Change `install.sh` so `reread` is offered for any selected runtime. In its
own `DO_REREAD` block, install the checklist once; install the common procedure
once when OpenCode or Codex is selected; and add separate `WANT_CC`, `WANT_OC`,
and `WANT_CODEX` branches for the Claude script/command and the two new entry
points. Do not place `sc` under the `DO_DOC` directory sweeps. Preserve the
existing Claude command and hook except for wording forced by the feature
model. Update interactive prompts, `--help`, and the final summary so they
describe the distinct guarantees and do not suggest `/sc on` for an
OpenCode-only or Codex-only install.

Add focused temporary-HOME tests modeled on `tests/test_shortcuts_install.sh`.
Cover OpenCode-only, Codex-only, Claude-only, and combined installs in copy and
symlink modes. Assert each selected runtime gets its entry point and the
checklist, unselected runtimes get no entry point, each destination has one
manifest record, and `uninstall.sh --yes` removes all kit-owned new artifacts.
Exercise `doc-harness,reread` with `--on-exist backup` to catch duplicate
destinations; assert no unwanted `.bak` in runtime scan paths. No test may run
`install.sh` against the operator's real HOME.

Update `README.md` and the `sc` capability block in `shared/tutorial.md` with
the support distinction: Claude is hook-enforced before delivery above its
length threshold; OpenCode and Codex are instructed in-turn, including on
short answers. The tutorial must show the right syntax and only claim the
capability for a runtime with its entry point. Update the install summary to
match. Run `tests/test_help_is_complete.sh`,
`tests/test_tutorial_covers_features.sh`, the focused install/uninstall test,
`tests/test_reread_guard.sh`, and the repository documentation gate. These
checks establish package distribution and Claude hook regression, not
OpenCode/Codex behavior in a client.

Ownership: implement after M1 review. A fresh reviewer checks installer gates,
manifest cleanup, docs, and test evidence before M3.

Review: `APPROVED` by a fresh M2 reviewer on 2026-09-28. Temporary-HOME
copy/symlink install and uninstall, Claude hook regression, installer help,
tutorial coverage, and shell syntax tests passed. The reviewer advised
clarifying that 500 is the default threshold; the help was corrected.

## M3 — Installed-client acceptance and documentation reconciliation

Use disposable client configurations populated by temporary-HOME installs.
Confirm in each client that its effective command/skill and checklist paths
are those installed artifacts before interpreting the result. In a live
OpenCode session invoke `/sc <question>`; in a live Codex session invoke
`$sc <question>`. Temporarily append a harmless, distinctive formatting item
to the installed checklist, ask a short deterministic question, and capture
both the checklist read and the final answer showing that item without
commentary about the pass. Restore the checklist immediately. Repeat with a
substantial question to exercise normal work and a long answer. Probe a plain
question without `$sc` for accidental Codex self-triggering and the empty
argument and unsupported-mode paths. Temporarily hide the common procedure and
then the checklist, one at a time, and verify that the client reports the
missing artifact instead of claiming a pass; restore each file immediately.
These observations prove the installed entry point reached the checklist and
influenced a visible answer; they cannot
prove an unseen draft was corrected or that every future answer will comply.

Preserve the existing Claude hook test and the existing command and hook source.
The operator accepts the prior functioning of Claude Code `/sc` and waived a
repeat live check for this port on 2026-09-28. Record the attempted client
version and quota rejection, and do not present it as fresh runtime proof.
If OpenCode or Codex is unavailable or does not load an isolated config,
record that runtime as unverified and do not claim it works or complete the
plan. Resolve the config-loading cause before retrying; a synthetic prompt
test cannot replace client acceptance on either new runtime.

Add a short re-read support and verification matrix to
`docs/reread-guard.md`, indexed from `docs/README.md` and linked from
`README.md`. Use the capability/status/proof shape already established by
`docs/scope-guard.md`; do not mix unrelated features into its scope-guard
matrix. State the measured versions, exact proof, and limits. Reconcile
`docs/active-context.md` as a living snapshot, advance this plan's status only
when implementation and the required OpenCode/Codex client proof are complete,
and close the session memory through the normal
documentation workflow. Run the repository test suite, `git diff --check`,
and `python3 shared/scripts/doc-check.py --repo .`.

Ownership: the lead performs and records real-client QA. A fresh milestone
reviewer judges those observations and the documentation claims. After M3 is
approved, a separate final reviewer checks the integrated install, client
behavior, uninstall, and support claims. Only final approval closes the plan.

Evidence so far: OpenCode 1.18.32 and Codex CLI 0.157.1, using an isolated copy
install, each consumed a temporary checklist marker in short and long answers.
Their long answers read a three-line workspace fixture and correctly reported
three nonempty lines. Both reported missing installed files; OpenCode's empty
argument and all four unsupported modes and Codex's plain, empty, and four
unsupported prompts were exercised. The OpenCode command now injects the
installed files through shell expansion. Codex's skill description now
suppresses an observed progress announcement. `docs/reread-guard.md` records
the measured limits. Claude Code 2.1.280 returned a weekly usage-limit message
before `/sc` could run. The operator then waived the repeat live Claude check
because the existing `/sc` had worked before the port. No new Claude client
behavior is established by this work trace.

Independent M3 review on 2026-09-28 found no remaining source, installer, or
documentation defect. The reviewer returned `BLOCKED` under the former live
Claude requirement. After the operator waived that requirement, the reviewer
returned `APPROVED` against the revised boundary: new OpenCode/Codex client
checks passed, Claude command and hook source did not change, and the eight
hook regression checks passed. The reviewer inspected the disposable client
traces before their cleanup; they are no longer on disk.
An independent semantic documentation review found no blocking claim or
work-trace defect. The isolated checklist was restored byte for byte after QA.

## Risks and rollback

The two new entry points depend on installed global files; a missing common
procedure or checklist must be reported as an incomplete installation. The
Codex skill is model-invoked and may still self-trigger despite its
description, so documentation must describe this as an instruction boundary.
An isolated config may differ from the operator's actual client setup; record
the effective config path and test the installed client, not a standalone
template. Rollback is removal through the install manifest and restoration of
any backed-up destination with `uninstall.sh --restore-backups`; Claude's
dynamic `/sc` Stop registration needs its own `unregister` command because it
is not a manifest artifact.

## Plan review

Independent verdict: `APPROVED` on 2026-09-28. The reviewer found no blocking
issue. Its two advisories are incorporated above: live-client missing-artifact
probes in M3, and explicit rejection of Claude's `unregister` mode on OpenCode
and Codex. Source paths checked: `install.sh` and `claude/commands/sc.md`.

## Final integration review (2026-09-28)

Independent verdict: `APPROVED`, with no blocking findings. The reviewer read
the complete brief and plan, inspected the entry points, shared procedure,
installer, uninstaller, new install test, support matrix, and unchanged Claude
command and hook. Fresh runs of `tests/test_reread_install.sh`,
`tests/test_reread_guard.sh` (eight checks), `tests/test_help_is_complete.sh`,
`tests/test_tutorial_covers_features.sh`, `git diff --check`, and the
documentation gate passed. The reviewer checked the recorded OpenCode/Codex
client outcomes but did not rerun those clients; their disposable traces had
already been removed. The operator waived a repeat Claude client check, and
this plan claims no fresh Claude client proof.
