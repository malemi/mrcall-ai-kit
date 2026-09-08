# Brief — directives on demand, not on every turn

## Intent

Stop pushing standing instructions into every routed prompt, and give the
operator two commands that pull the instruction he actually wants for the turn
he wants it in. One suspends the harness machinery for a quick question; the
other restates the engineering-lead stance when the session has drifted from it.

## Problem

The router hook prints a forty-six-line `DIRECTIVE` on every prompt of every
routed session. It restates content the session already holds: the managed
`CLAUDE.md` carries the engineering-lead stance, the reviewed delivery flow and
the verdict vocabulary (`shared/templates/CLAUDE.md:21,23,32,42,46,53,56`), and
the three `claude/agents/worker-*.md` `description` fields carry the routing
table, which Claude Code surfaces in every session's agent listing. Repetition
of already-present instructions is not free: it costs a block of context on
every turn, and the CTO's direct observation is that compliance does not follow
from it.

The opposite failure is also real. A quick factual question runs through tools,
subagents, and lifecycle gates and costs minutes. That latency comes from tool
calls, subagent launches, and gates — not from the length of model reasoning,
which is a client-side effort setting that prompt text cannot change.

## Scope

1. `claude/scripts/router-hook.py` stops printing `DIRECTIVE`, and prints
   nothing at all when it has nothing to say — with the directive gone and no
   `docs/` tree in reach, `print()` would emit a blank line as context.
2. `MEMORY_NOTE` is reduced to what is genuinely about the session file: the
   resolved path, the create-if-missing and living-snapshot rules, and the
   instruction to have a delegated worker read that file first and append
   durable findings back before reporting. The rest of its second paragraph is
   standing delegation doctrine, and it moves (see 3). The note keeps its
   literal opening `Session memory:`, which `tests/test_router_install.sh:91`
   asserts.
3. Four named edits to `shared/templates/CLAUDE.md`, and nothing else in that
   file:
   - Add the caller-side rules that currently exist **only** inside the hook —
     relay a reviewer's verdict and evidence in your own words rather than
     pasting its report, and continue the same reviewer for a revision at the
     same gate while using a fresh reviewer for each new gate. Verified absent
     elsewhere on the Claude side; only OpenCode carries its own copies
     (`opencode/agents/orchestrator.md:105`,
     `opencode/skills/orchestrator/SKILL.md:100`).
   - `:46` becomes "Do not delegate or implement until it returns `APPROVED`".
     The hook barred delegating implementation before the plan gate; the
     template as written bars only implementing, so retargeting without this
     repair would drop a guarantee rather than move it.
   - State that a review returns exactly one of `APPROVED`, `REVISE`,
     `FAST_PATH`, or `BLOCKED`. The template names all four but never says the
     set is exhaustive, and the only boundedness statement,
     `claude/agents/worker-opus.md:71`, loads inside the worker where the
     caller cannot see it. The sentence stays agent-facing and free of worker
     vocabulary — the hook scoped boundedness to worker-opus verdicts, but the
     template addresses any reviewer, including a human one, and reads best
     next to `:57-58`, which already covers a runtime with no delegation
     capability.
   - `:21-23` counts "coordination and waiting" as the cost of delegating; the
     hook also counted review. Add it, so the delegation test keeps weighing
     what it used to weigh. This raises the bar for delegating, which is the
     direction of travel here and restores parity with the deleted text.

   Wording stays tool-agnostic, because the template ships to all three
   runtimes.
4. Regenerate every managed `CLAUDE.md` that the template edit invalidates.
   `shared/scripts/doc-check.py:409-431` requires a managed repository's harness
   file to match the installed template byte-for-byte, and
   `find_harness_template()` resolves to this working tree — the installed
   template is a symlink into it. Three repositories on this machine currently
   hold a byte-identical copy: this one, the meta-repository `/home/mal/hb`, and
   `/home/mal/hb/cs-kernel`. All three fail their own gate the moment the
   template changes. `harness_version` stays at `8`: the profile version is
   compared against an installed constant and governs contract shape, while the
   byte comparison is what carries a content change; bumping it would force a
   `doc-create` migration that this edit does not require. Regenerating the file
   in the other two repositories is mechanical and restores their gate to clean,
   but committing there is an act in a repository this workstream does not own:
   those two commits are batched for the CTO rather than taken silently.
5. A new command `nr` — the fast-answer override.
6. A new command `av` — on-demand injection of the engineering-lead stance.
7. Both commands delivered to Claude Code, Codex, and OpenCode, wired into
   `install.sh` under a new cross-tool `--features` value, with `uninstall.sh`
   coverage through the existing manifest, and one install test.
8. Reconciliation of the tests and live docs that describe the removed
   injection, enumerated below.

Out of scope: the worker agent definitions, the OpenCode orchestration agents,
and every part of the managed template other than item 3.

Repositories installed in `copy` mode elsewhere are not newly broken:
`doc-check.py:399-406` prefers `$MRCALL_DOC_HARNESS_TEMPLATE`, then the source
tree, then the installed copy, so a frozen snapshot keeps comparing against
itself until its owner re-runs the installer, which is the harness's normal
migration path.

## What the removal costs

With the managed `CLAUDE.md` installed, nothing is lost: the stance, the
lifecycle, the verdict vocabulary and — through the agent listing — the routing
table are all still in context, and the hook was repeating them.

Without it, a routed session loses all three, and `av` restores none of them:
`av` injects stance only, by design. Widening it into a second lifecycle dump
would rebuild precisely the artifact whose decay this change exists to fix. The
answer for such a repository is to install the managed template, which is the
harness's actual delivery mechanism for the contract. This brief states that
rather than pretending `av` covers it.

## Behavior contract — `nr`

For that turn only:

- Answer from context and existing knowledge.
- No tool calls, no subagents, no brief or execution plan, no review gates, no
  session-memory write.
- Short answer, no preamble, no restating the question.
- When the answer is not already known, say so in one line and name what would
  have to be checked. Never guess.
- When the argument asks for an action or a change rather than a question,
  decline in one line and state that the normal path applies. The command
  suspends investigation, never the gates that govern doing work.

The last two clauses are load-bearing. Without the first, the command is a
licence to fabricate, against `AGENTS.md`: never claim something works until it
has been run the way the final user runs it. Without the second, "no review
gates" plus an action request reads as permission to change things ungated.

The name `nr` is the operator's and stays. The shipped `description` states the
effect — the harness machinery is suspended for one turn — rather than the
name's original expansion, which named the wrong cost.

## Behavior contract — `av`

Injects the engineering-lead stance: the assistant's time is worth less than the
CTO's; the CTO codes less than the assistant does, so deeply technical questions
are misplaced; problems are solved rather than handed back; value comes from
deciding, implementing and finishing, and interrupting to display diligence
destroys it.

With an argument, the stance applies to that task; with none, it is a bare
restatement and the session continues. The payload stays short and stays about
stance. It does not restate the delivery flow — a long procedural payload would
decay the same way the hook's did — it grants no permission to skip a gate, and
it authorises no irreversible or external action. A command payload cannot
guarantee that a stance persists for the rest of a session, and the brief does
not claim it does.

## Constraints

- All shipped artifacts are in English, including both command payloads.
- `install.sh:269,278` sweeps **every** entry of `shared/commands/` into Claude
  Code and OpenCode under the `doc-harness` feature. A file placed there would
  ship with `doc-harness` whatever the new flag says, and a second explicit add
  would create a duplicate destination — under `--on-exist backup` the second
  pass moves the file the first pass just installed to `.bak`. The two shortcut
  sources therefore live **outside** the swept directory, in
  `shared/shortcuts/`, and reach Claude Code and OpenCode through explicit
  `add_one` entries under the new feature. This avoids the collision by
  construction rather than by a `$DO_DOC ||` guard of the kind `install.sh:286`
  uses for `worker-fable`.
- Codex is wired differently again: the kit installs model-invoked skills to
  `~/.agents/skills/<name>/`.
- Symlink installs create one link per entry, not a directory link, so new files
  do not appear until the installer runs again.
- `nr` must override whatever the router hook still injects, without disabling
  the router.

## Reconciliation surface

Tests. `tests/test_agent_profiles.sh:85-100` runs the hook with the flag on and
asserts eight substrings of `DIRECTIVE`. Those eight guarantees are not deleted;
their carrier changes, and the assertions retarget from hook stdout to the
installed managed template, which that test already installs and greps at
`:103-109`. Five retarget cleanly, with a verified home:
keep-narrow-work-local and positive-value delegation at `:21,23`, the strict
fast path at `:32`, the brief gate at `:42`, and the separate final end-to-end
review in step 6.

Three do not retarget as they stand, which is why scope item 3 repairs the
template rather than only adding to it. The plan gate at `:46` bars implementing
but not delegating, so it is repaired before the assertion moves. The verdict
list defended boundedness, which the template does not state, so boundedness is
added. The negative guard asserted the absence of `DIRECTIVE`'s own former
wording; against a template that never contained that phrase it could never
fail, and a tautology that reads as protection is worse than no assertion. It is
replaced by a positive assertion that can fail — the template must still say
`never delegate a trivial local edit` — which is the rule the negative guard
existed to defend.

Exact assertion strings change with the carrier's wording; after the repairs,
the guarantee each one defends does not. That test's
own hook payload at `:83` has no `docs/` tree in reach, so what it asserts about
the hook becomes a single check that the output is empty; it cannot assert that
the session file is named.

`tests/test_router_install.sh:80-85` is six assertions, not one. Five are
`DIRECTIVE` substrings — `Router mode is ON`, both `until its verdict is
APPROVED` gates, `separate final end-to-end review`, and the bounded verdict
list — and the sixth asserts that a flag-on session with no `docs/` tree prints
*no* memory note. After scope item 1 that payload prints nothing at all, so five
fail and the sixth passes vacuously. The whole block is replaced by the
no-output assertion that acceptance criterion 1 describes. The docs-tree case at
`:91-92` stays valid and is where the session file's naming remains covered,
which is why scope item 2 preserves the literal `Session memory:`.

Every `shared/templates/CLAUDE.md` line number cited in this brief is pre-edit.
Scope item 3 shifts them, so the implementer re-resolves each one against the
edited file rather than trusting the numbers here.

Live docs to correct: `docs/model-router.md:54,150`, plus a re-read of `:21-25`
which describes the intended shape; `docs/documentation-harness.md:286`;
the hook's own module docstring at `claude/scripts/router-hook.py:9-10,22`;
`README.md`; and `install.sh`'s help text for the router feature.

Not touched: closed briefs and completed execution plans that describe the
injection as it was — `docs/briefs/2026-08-24-harness-context-economics.md`,
`docs/execution-plans/2026-08-24-harness-context-economics.md`,
`docs/execution-plans/2026-09-01-reviewed-delivery-flow.md`. They are the
historical record, and this repository does not rewrite it.

Verified still true, no edit: `shared/commands/doc-end.md:47` and
`codex/skills/doc-end/WORKFLOW.md:47`, which rely on the injected session path.

## Open technical question, resolved by experiment

Codex 0.150.1 appears to have no operator-typed prompt directory:
`~/.codex/prompts` does not exist and the binary carries no `$CODEX_HOME/prompts`
string. The implementer confirms this against the running client — the slash
list in the TUI — before falling back to skills under the existing
`~/.agents/skills/` destination. If the fallback is taken, `README.md` records
the asymmetry: on Codex the shortcuts are model-invoked rather than
operator-typed, which is a weaker guarantee, documented as such rather than
described as equivalent.

## Acceptance criteria

1. With the router on, a real Claude Code session shows the hook printing the
   session-memory note and no lifecycle directive, and the session still
   resolves and uses its memory file. A routed session with no `docs/` tree in
   reach produces no output at all rather than a blank line.
2. A real Claude Code session with the router **on** — the operator's actual
   configuration — answers an `nr` question with no tool call and no delegation.
   The same is observed in real OpenCode and Codex sessions, through whichever
   invocation mechanism each supports.
3. `nr`'s unknown-answer path states what would have to be checked instead of
   guessing, and an action request passed to `nr` is declined rather than
   executed.
4. `av` expands to the stance text in each runtime that supports operator
   invocation, both with an argument and without one. The criterion is
   expansion, not measured compliance.
5. A real install under a sandboxed `HOME`, in the manner of
   `tests/test_codex_install.sh`, shows both commands landing in each runtime's
   correct destination and `uninstall.sh` removing exactly those entries.
   `--dry-run` writes no manifest lines, so it cannot prove the uninstall half.
6. `tests/test_agent_profiles.sh` and `tests/test_router_install.sh` pass with
   retargeted assertions, each of which can still fail against a template that
   dropped the rule it defends, and the remaining tests pass unchanged.
7. No live document describes the router as injecting the lifecycle directive:
   the files enumerated in the reconciliation surface, and no others.
8. `python3 shared/scripts/doc-check.py --repo .` is clean in this repository
   after its managed `CLAUDE.md` is regenerated, and the same check is clean in
   `/home/mal/hb` and `/home/mal/hb/cs-kernel` once theirs are regenerated too.
   The regenerated file is a byte copy of the edited template, never a hand
   edit.

## Assumptions

- Both commands are invoked at the start of the input, with any question or task
  as the argument. Pasting a directive at the end of a line is not supported by
  any of the three runtimes.
- The command names are `nr` and `av`.
- Removing the per-turn injection is the CTO's explicit decision, taken with the
  cost above stated.
