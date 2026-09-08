---
status: completed
brief: docs/briefs/2026-09-08-on-demand-directives.md
started: 2026-09-08
completed: 2026-09-08
---

# Execution plan — directives on demand, not on every turn

Brief: [`2026-09-08-on-demand-directives.md`](../briefs/2026-09-08-on-demand-directives.md),
`APPROVED` at the fifth review pass. Milestone numbering follows the brief's
scope items; each milestone is independently reviewable and leaves the tree in a
state where the test suite passes.

## M1 — Template repairs and regeneration

Scope items 3 and 4. No dependency.

Edit `shared/templates/CLAUDE.md` exactly four times: add the two caller-side
sentences (relay a reviewer's verdict and evidence in your own words rather than
pasting the report; continue the same reviewer for a revision at the same gate
and use a fresh one for each new gate), change the plan gate to bar delegating
as well as implementing before `APPROVED`, state that a review returns exactly
one of the four verdicts, and add review to the delegation cost. The boundedness
sentence stays agent-facing and free of worker vocabulary, placed beside the
existing no-delegation-capability clause.

Then regenerate the managed harness file as a byte copy of the edited template
in three repositories: this one, `/home/mal/hb`, and `/home/mal/hb/cs-kernel`.
Never hand-edit a regenerated file.

Two mechanical constraints. `harness_version` stays at `8`: the profile version
governs contract shape and the byte comparison carries content changes, so
bumping it would force a `doc-create` migration this edit does not need. And
adding review to the delegation cost must not rewrap the phrase `never delegate
a trivial local edit` across a line break — `tests/test_agent_profiles.sh:34`
greps it as a single line.

Ordering rationale: M1 lands first and breaks nothing. The hook is untouched, so
every existing hook assertion still passes, and `tests/test_agent_profiles.sh`'s
template greps at `:31,34,109` stay true.

Verification: `python3 shared/scripts/doc-check.py --repo .` clean here, and the
equivalent check clean in the other two repositories. Full test suite green.

Ownership: implemented directly. The edit is four sentences and the regeneration
is a copy; delegation would cost more than the work.

Out-of-repo boundary: the two files outside this repository are regenerated but
**not committed**. Those commits are batched for the CTO at the end.

## M2 — Hook reduction and test retargeting

Scope items 1, 2 and the test half of 8. Depends on M1, because the retargeted
assertions land on the edited template.

`claude/scripts/router-hook.py` stops printing `DIRECTIVE`, reduces
`MEMORY_NOTE` to the session-file sentences while preserving its literal
`Session memory:` opening, and prints nothing at all when it has nothing to say.
Update the module docstring, which currently describes the removed injection.

Retarget `tests/test_agent_profiles.sh:85-100`: five assertions move onto the
installed template that the same file already installs and greps; the plan-gate
and verdict-boundedness assertions move onto the text M1 added; the negative
guard is replaced by a positive assertion that the template still says never to
delegate a trivial local edit. That test's own hook payload has no `docs/` tree,
so its hook check becomes an empty-output assertion. Replace
`tests/test_router_install.sh:80-85` with the same empty-output assertion;
`:91-92` stay untouched.

`tests/test_router_install.sh:32` is the third binding and the one that breaks
first: inside the copy/symlink loop it greps the **installed hook file** for a
string that lives only in `DIRECTIVE`, so the suite dies there before printing a
single `PASS`. That assertion exists to prove the installed file is really this
hook, so it retargets to a marker the change preserves — the dormancy flag path
`router.on`, which is the property that loop is actually about.

Verification in three parts. First, both test scripts pass. Second, every
retargeted **template** assertion is proven able to fail: copy the whole kit to
a scratch directory, because `KIT_DIR` derives from `BASH_SOURCE` and every
candidate carrier resolves through it — `tests/test_agent_profiles.sh:28` reads
the kit's own `shared/templates/CLAUDE.md`, and `:109` reads the installed
`CLAUDE.template.md`, which in the symlink iteration points back into that same
tree and in the copy iteration was taken from it at install time. In that copy,
delete one rule at a time from the template and confirm the matching assertion
fails, then restore.

Each assertion is judged individually, by the message it prints, never by the
suite turning red: `tests/test_router_install.sh:32` runs before the
empty-output assertions, so a suite-level failure can come from a different line
entirely and be misread as the category being falsified. The three
non-template assertions each get their own mutation. The two empty-output
assertions are falsified by restoring `DIRECTIVE` in the scratch copy. The
`router.on` marker cannot be — the flag lives at `claude/scripts/router-hook.py:38`,
outside the `DIRECTIVE` literal, so that grep passes whether the directive is
there or not; it is falsified by deleting its own line from the scratch copy's
hook.

Third, a real routed Claude Code session shows no lifecycle directive and a
working session-memory path.

Ownership: implemented directly. The retargeting is judgment about what each
assertion defends, which is the part that has already gone wrong twice in
review.

## M3 — The two commands and their installation

Scope items 5, 6 and 7. Independent of M1 and M2 in code; sequenced after them
so that the real-client checks run against the final hook.

Create `shared/shortcuts/nr.md` and `shared/shortcuts/av.md` in English, with
descriptions that state effect rather than name. Wire a new cross-tool
`--features` value in `install.sh` with explicit `add_one` entries to
`~/.claude/commands/` and `~/.config/opencode/commands/`, offered in the
interactive prompt like the existing features and rejected for unselected
runtimes the way the router already is. Add one test in the style of
`tests/test_codex_install.sh`: a real install under a sandboxed `HOME` for both
`copy` and `symlink` modes, then `uninstall.sh` removing exactly those manifest
entries.

M3 owns every edit to `README.md` and to `install.sh`'s help text — both the new
feature's entry and the corrected description of what the router feature
installs. M4 touches neither, so no file is written twice.

Codex first, because it decides the shape: confirm against the running client
whether an operator-typed prompt directory exists. If it does not, fall back to
skills under `~/.agents/skills/`, give `nr` a description saying it runs only
when the operator asks for it — a self-triggering machinery-suspending skill is
the one shape worth guarding against — and record the asymmetry in `README.md`
rather than describing the runtimes as equivalent.

Verification: the sandboxed install and uninstall test, then real sessions.
Claude Code with the router **on** answering an `nr` question with no tool call
and no delegation, refusing an action request, and stating what it would have to
check when it does not know; the same in OpenCode; the same in Codex through
whichever mechanism it has. `av` expands with and without an argument.
Non-interactive client runs must clear `ANTHROPIC_API_KEY` for the process,
which otherwise takes precedence over the subscription login and yields zero
tokens.

Ownership: the build is bounded and substantive with real context isolation, so
`worker-sonnet` implements it against the specification above. The Codex
experiment and every real-client acceptance check stay with the lead, because
they are judgment about whether a claim is true.

## M4 — Live-doc reconciliation

The doc half of scope item 8. Depends on M2 and M3 being final, so nothing is
written twice.

Correct `docs/model-router.md:54,150` and re-read `:21-25`, and
`docs/documentation-harness.md:286`. The hook's own docstring belongs to M2 and
`README.md` plus the installer help belong to M3; those are the whole live set.
Closed briefs and completed execution plans keep the historical record and are
not rewritten.

M4 also closes the work trace: this plan's `status` becomes `completed`,
`docs/active-context.md` is brought to current reality — including its stale
claim that the OpenCode executable is unavailable, when it is installed at
`~/.opencode/bin/opencode` — and the session file is closed.

Verification:
`grep -rniE "injected directive|router.{0,20}directive|routing directive" --include=*.md docs/ README.md AGENTS.md`,
excluding briefs, plans, sessions and the archive, returns nothing; and
`python3 shared/scripts/doc-check.py --repo .` stays clean.

Ownership: implemented directly.

## Risk and rollback

Every change is in version control. The one change with reach beyond this
repository is M1's template edit, which invalidates the byte-for-byte gate in
three repositories at once; rollback is restoring the template and re-copying it,
and the two out-of-repo files are restored from their own repositories' HEAD
because they are never committed here.

The failure mode this plan is built against is a retargeted assertion that
cannot fail — a green test defending nothing. M2's verification therefore
requires proving each assertion fails against a template with the rule removed,
not merely that the suite is green.

## Reviews

M1, M2 and M3 each receive an integration review from a fresh `worker-opus`
before dependent work begins. After M4, a different fresh `worker-opus` runs the
final end-to-end review through the operator's own path: a real routed session
using both commands.
