# Re-read guard on OpenCode and Codex: the same checklist, an honest guarantee per runtime

**Date**: 2026-09-27 · **Plan**:
[`2026-09-27-reread-guard-cross-runtime.md`](../execution-plans/2026-09-27-reread-guard-cross-runtime.md).
Evidence verified 2026-09-27 against `install.sh` @ d9da954, OpenCode 1.18.32,
`opencode-claude-hooks` 0.1.0 (the copy cached at
`~/.cache/opencode/packages/opencode-claude-hooks@latest/`).

## Problem

`/sc` gives a finished answer one enforced re-read pass against
`reread-checklist.md` before the user sees it. It exists only on Claude Code.
The operator asked for it on OpenCode and Codex too (2026-09-27, session
`ses_f1c30ea70ffebPw9jiwhRbBWfI`), and the
checklist is exactly the kind of rule that decays with context length on those
runtimes no less than on Claude Code. A first attempt that day shipped
prompt-only stubs, misgated installer wiring, a Claude-dependent checklist
path, and a completion report claiming commands that do not exist; it was
reviewed, found unusable, and discarded from the working tree (findings in
`docs/sessions/ses_f1bfb5f77fferiY4VG5CqO4fRL.md`). The demand stands; the
port has to be redone from the mechanism up.

## The guarantee that exists today (Claude Code)

`claude/commands/sc.md` arms a flag (`reread.once` one-shot, `reread.on`
persistent); the Stop hook `claude/scripts/reread-hook.py`, registered in
`~/.claude/settings.json`, intercepts the finished answer, spends the flag, and
returns `decision: block` with the checklist — the session fixes what fails,
the second pass (`stop_hook_active`) is let through, answers under
`SC_MIN_CHARS` (500) skip the pass. These paths are tested by the eight
numbered checks in `tests/test_reread_guard.sh`: opt-in, fires once, never
loops, fails open when the checklist is missing, and spends the arming even
when a short answer is skipped. A malformed JSON payload also fails open, but
that early return does not spend `reread.once`.
The guarantee is **runtime-enforced and pre-delivery**: the pass happens
whether or not the model remembers to, and before the answer is shown.

## Verified mechanism landscape

**OpenCode — no verified Stop-equivalent control in the inspected version.**
- The kit's `opencode/plugins/scope-guard.ts` uses `tool.execute.before/after`
  and `event`. Its comments record that the inspected stable v1 API provides
  no supported way to block a completed answer and hand it back to the model
  for another pass. This file is evidence about this adapter, not an inventory
  of every OpenCode hook. The installed `@opencode-ai/plugin` 1.17.17 type
  declaration also exposes `experimental.text.complete`, which can mutate a
  completed text part. Its declared input has session, message, and part IDs;
  its output has text. It does not declare the Claude Stop payload, a block
  decision, or a model re-entry contract. A text transformation is therefore
  not evidence of a Claude-style re-read control.
- Third-party `opencode-claude-hooks` 0.1.0 (already enabled in the operator's
  `opencode.json`): its README maps Claude `Stop` to `session.idle` as
  "Partial", but the shipped `dist/index.js` never calls its own `handleStop` —
  `Stop` support is dead code. Even wired, `session.idle` fires after the
  answer has reached the user, and the plugin's `StopInput` carries neither
  `last_assistant_message` nor `stop_hook_active`, so `reread-hook.py` would
  fail open on every answer.

**Codex — hooks exist, but none at answer completion.**
The kit already registers Codex hooks for scope-guard: `~/.codex/hooks.json`
with a `PreToolUse` entry (`shared/scripts/scope_guard_register.py`,
adapter `codex/scripts/scope-guard-hook.py`, itself titled "degraded …
enforcement"). No Stop-equivalent event is used or documented, and Codex has
no operator-typed command form — the shortcut convention is a model-invoked
skill triggered by a literal `$token` or explicit request, never
self-triggering (`codex/skills/nr/SKILL.md`, `codex/skills/av/`).

**Conclusion.** The inspected integrations provide no verified way to
replicate the Claude-Code enforced pre-delivery pass on either runtime. What can be delivered is the same
checklist, the same one-shot ergonomics, and an **instruction-based in-turn
pass**: the answering session performs the re-read before it finishes the
answer. Weaker, and the docs must say so in the support-matrix style
`docs/scope-guard.md` already established (capability per runtime, with
verification status), not in prose that lets a reader infer parity.

## Requirements

1. **OpenCode**: a typed `/sc <question>` command (command sources install to
   `~/.config/opencode/commands/`), one-shot by contract: answer, re-read
   against the installed checklist, fix, present only the corrected answer,
   say nothing about the machinery. Ship no `on`/`off`/`status` mode on this
   runtime: without a hook consumer, a persistent flag would be a dead toggle.
2. **Codex**: a `$sc` model-invoked skill following the `nr`/`av` convention
   (trigger only on the literal token or explicit request, never self-trigger),
   same one-shot in-turn pass, same silence rule.
   The OpenCode and Codex one-shot paths perform the pass even on answers under
   500 characters: `SC_MIN_CHARS` is a Claude Stop-hook cost dial, not a
   cross-runtime skip rule. State and test this difference explicitly.
3. **Checklist availability decoupled from Claude Code.** Today
   `--features reread` is forced off unless Claude Code is selected
   (`install.sh`, the `reread is Claude Code-only` gate) and only then installs
   `shared/roles/reread-checklist.md` to `~/.config/mrcall-ai-kit/`. The
   checklist is runtime-neutral: any selected runtime with `reread` must get
   it. The discarded stubs' broken dependency — a skill reading a
   Claude-gated file — is the exact failure this prevents.
4. **One source, rendered per platform.** The checklist stays a single file;
   the instruction texts follow the shortcut pattern (shared source,
   per-runtime renderings), not three hand-maintained near-copies. The
   Claude-side `/sc` and hook are untouched except where the feature model
   forces rewording.
5. **Feature model honesty.** `reread` stops being "[Claude Code only]":
   help text, the `--features` lists, the tutorial capability block
   (`shared/tutorial.md`, enforced by `tests/test_tutorial_covers_features.sh`),
   the install summary line, and `README.md` all change together or not at
   all. The installer shape follows the `DO_SCOPE` precedent — shared core to
   the kit-global home, then per-runtime branches under `WANT_CC` / `WANT_OC` /
   `WANT_CODEX` inside the feature's own gate; nothing rides in another
   feature's loop (the discarded attempt wired Codex into `doc-harness`).
6. **Lifecycle.** Every new installed destination must be in the install
   manifest and removable by `uninstall.sh` in copy and symlink modes. Check
   that `doc-harness,reread` creates no duplicate destination. If a future
   artifact replaces a previously shipped name, follow
   `shared/roles/retired.txt`; the discarded, unshipped stubs require no
   retirement entry. The new in-turn paths do not create session-memory files
   or bypass the router's `docs/sessions/` updates.

## Rejected, and why it deserves recording

- **The 2026-09-27 stubs** (three duplicate prompt-only `SKILL.md`, one
  installer line in the wrong feature gate, checklist path that cannot exist
  on the target runtimes): rejected in full — no mechanism analysis behind
  them, dead code for OpenCode, and they advertised enforcement they did not
  have.
- **Depending on `opencode-claude-hooks` Stop**: dead code in v0.1.0; a
  third-party package would become a runtime dependency of a kit feature (the
  kit ships only first-party adapters today); and the mapped event is
  post-delivery regardless.
- **Porting `reread-hook.py` to OpenCode as-is**: the inspected hooks provide
  no compatible Stop event with its block-and-re-enter contract; the payload
  differs; it would fail open silently —
  the worst outcome, because it looks installed.
- **Pretending parity in the docs**: the support matrix states per runtime
  what is enforced and what is instructed. A reader who infers more than was
  verified is a defect this brief is explicitly trying to stop shipping.

## Verification

- Hook behavior on Claude Code: `tests/test_reread_guard.sh` unchanged and
  passing (the port must not regress it).
- Install: a test per new destination in the style of
  `tests/test_shortcuts_install.sh` / `test_scope_guard_install.sh` —
  OpenCode-only and Codex-only temporary-HOME installs must produce the
  command/skill **and** the checklist. Test copy and symlink installs, their
  manifest-driven uninstallation, no cross-runtime leakage, and no duplicate
  destination when combined with `doc-harness`; `test_help_is_complete.sh`
  and `test_tutorial_covers_features.sh` must pass with the reworded feature.
- Real-runtime QA, the way the operator runs it (global rule — unit tests
  don't count): invoke `/sc <question>` in a live OpenCode session and `$sc
  <question>` in a live Codex session with a temporary, harmless checklist
  item whose effect is unambiguous in the final answer. Capture the invocation
  and final answer, check that the item took effect without commentary about
  the machinery, then restore the checklist. Exercise a short answer too: it
  must receive the in-turn pass on those runtimes. This checks observable
  checklist use, not an unseen draft or proof that a correction occurred.
  Re-check `/sc` in a live Claude Code session for the existing Stop behavior,
  including its under-500 skip. Record runtime versions and evidence.

## What this is, and what it is not

On Claude Code the guard is a control: the runtime hands the answer back
whether the model wants to or not. On OpenCode and Codex this ships a
mitigation: the instruction is in context at the moment of answering, and a
session under context pressure can still under-apply it — the same failure
mode the checklist exists for, narrowed but not eliminated. The test of
success on those runtimes is not "answers always get the pass"; it is "one
token gets the pass into the turn, silently, with the checklist present, and
the docs never claim more than that."

## Open questions for the plan / first milestone

1. Where the shared source of the instruction texts lives
   (`shared/shortcuts/` beside `nr`/`av` vs a `shared/commands/` + rendering
   step), and whether the Codex rendering must be byte-identical (doc-*
   convention) or adapted (shortcut convention).

The baseline ships one-shot only on OpenCode and Codex. Always-on mode or a
first-party plugin needs a separate, evidenced design; neither is a milestone
or a promised toggle in this port.
