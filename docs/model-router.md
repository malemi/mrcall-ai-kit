# The model router: session memory, rotation, and worker reports

The opt-in model router and everything that hangs off it. Split out of
[`documentation-harness.md`](documentation-harness.md) on 2026-08-25, when that
document crossed its own size advisory: the doc-harness contract and the
delegation machinery are two subjects, and only one of them is loaded by a
session that just wants to know what `/doc-start` does.

## Session memory (opt-in model router, Claude Code only)

`--features router` installs a dormant `UserPromptSubmit` hook plus `/router`
and `worker-fable`. `/ai-help` ships with `doc-harness` instead — it lives in
`shared/commands/` alongside the other cross-tool commands, not in the
router's Claude-only branch. Off by default: the hook checks for
`~/.config/mrcall-ai-kit/router.on` and exits with no output when the flag is
absent, at the cost of one filesystem check per prompt. `/router on` registers
the hook in `~/.claude/settings.json` (if not already registered) and creates
the flag; `/router off` removes only the flag, leaving registration in place;
`/router unregister` removes both.

The intended shape: the session model is a cheap engineering lead (Haiku) that
answers trivial prompts and performs narrow local work itself. It delegates
only bounded substantive work when the value of a fresh specialist context is
greater than prompting, waiting, and review: `worker-sonnet` for execution,
`worker-opus` for hard judgment, and `worker-fable` for explicitly requested or
genuinely frontier-hard work. Because a subagent starts with a fresh context,
delegation without continuity loses whatever the previous worker understood —
so a routed session gets a shared-memory file,
`docs/sessions/<session-id>.md`, the same kind of object as
`docs/active-context.md`: a living snapshot, never a log, same anti-drift
discipline, same repo, readable with `cat`.

**Where it lives**: the repository the session started in, decided once and
then fixed for the rest of the session. The hook's payload carries the shell's
working directory, and that moves with every `cd`, so deriving the path from it
gives a session a different memory file the moment work enters a sub-repo. The
failure is silent by construction: a successor that follows the moved path
finds nothing, creates an empty file, and starts from zero while the
accumulated snapshot sits in another repository. So the hook resolves the
directory once, records it under `~/.config/mrcall-ai-kit/sessions/`, and reads
that record on every later turn. Two rules run before the record is written. A
`docs/sessions/<session-id>.md` that already exists in the working directory or
any of its parents is adopted rather than duplicated — one session never gets
two files, and a session already split by the old cwd-derived path is repaired
by its next routed turn. Failing that, the starting directory is recovered from
the transcript path, whose project directory Claude Code fixes when the session
opens. A session whose start cannot be established at all falls back to the
working directory, and only when a `docs/` tree is already there: this hook
names a path, it never creates one.

**Who writes it, and when**: whoever answers the turn, at their own
discretion — not the classifying model. The model that did the work is the
only one that knows what was worth recording; a trivial turn correctly writes
nothing. The write protocol travels in the hook's injected directive and in
delegation prompts, so no worker definition changes for this.

**Lifecycle**: a session file's frontmatter `status` is `open` until `/doc-end`
reads it (when the router named one for this turn — see Phase 2 of the end
workflow), folds whatever is durable into `active-context.md`, and flips it to
`closed`. A session that ends without `/doc-end` leaves an `open` orphan.
Liveness cannot be determined — Claude Code exposes no PID or lock for a
session, only a transcript file whose mtime cannot distinguish a dead session
from an idle one — so `/router sweep` reports open files with their age and a
*probably dead* flag past 24 hours, and never closes or edits one itself;
that judgment stays with a human.

**Read scope**: `docs/sessions/**` follows the same rule as `docs/projects/**`
— `doc-start` never opens it. The mechanical gate still indexes it: it
validates `status` is exactly `open` or `closed` (a gate failure otherwise,
the same enforcement as execution-plan status) and reports an advisory count
of files still open (never a failure — an open file mid-session is normal,
and judging which are stale is `/router sweep`'s job, not the gate's).
`docs/sessions/` is gitignored by `doc-create` — these files are per-machine
and ephemeral by design, not repository knowledge.

## Session rotation

A context window fills up, and what happens then is not neutral: compaction
decides on its own what to keep, and the first thing it drops is the material
that reads as settled — the constraints, the approaches already rejected, the
correction the operator gave two hours ago. The work survives; the reasons for
its shape do not. Rotation is the deliberate alternative — hand the window over
before it is taken.

**Rotation is not the end of a session, and the distinction is load-bearing.**
A rotation brackets a *context window*. `/doc-start` and `/doc-end` bracket a
*work session*, and they own the git baseline. So a rotation never runs
`doc-end`, never advances `doc_baseline_commit`, and never promotes anything
into `active-context.md`. One work session can span several windows, and only
its last one is entitled to consolidate.

**The hand-off** is a fixed section of `docs/sessions/<id>.md`, written by the
outgoing window:

```
## Hand-off
- Goal: <in the operator's own words, not paraphrased into task-speak>
- Constraints: <first, because these are exactly what compaction destroys>
- Decided: <what was settled, and what it turned on>
- Rejected: <what was considered and ruled out, with the reason>
- State: <what is done, what is half-done, what is untouched>
- Next: <the immediate next action>
- Ask: <what needs the operator, and nothing that does not>
```

Constraints come first because they are the least recoverable. Everything else
in the list can be re-derived from the repository by a successor willing to
read; a constraint that was stated once in conversation cannot.

**Frontmatter** gains `successor_of` and `rotated_at`. `status` stays `open` —
it is the same work session, and in any case the gate accepts exactly `open` or
`closed`, so a third value would fail every older installed checker.

**Resume**: the successor reads the hand-off and `docs/active-context.md`, and
does **not** run `/doc-start`. Running it would re-read the durable layer the
predecessor already paid for and re-establish a baseline that never moved.

**Rotation is manual, in every environment** — decided 2026-08-25. An automatic
trigger was designed (transcript size as an upper-bound proxy for the window,
about fifteen lines inside the router hook) and not built, because this kit
does not grow hook logic its users did not ask for. The consequence is worth
stating rather than glossing: nothing watches the window, so rotation happens
when the operator remembers, and the moment it is most needed is the moment
nobody is watching for it. A late rotation still beats a silent compaction.

## Worker reports and proportional execution

A worker exists to keep work out of the delegating session's context. A worker
that returns a diff, a file listing or a stack trace hands that context straight
back and cancels the delegation it just performed — which is a thing that
happens, not a hypothetical.

**The budget**: at most twenty lines, no diff, no file listing, no stack trace,
no more than three consecutive lines of command output. Evidence longer than
that goes to `$TMPDIR/mrcall-ai-kit/<task-id>/<worker>.log`, and the report
carries the path on its `Evidence:` line. The location is outside the repository
on purpose: a worker's scratch output is not repository knowledge, and it must
not be one missing `.gitignore` line away from a commit. It is lost on reboot,
which is the right trade — it exists to be read in the minutes after the worker
returns, not to be kept.

**The `Unverified:` line** is part of the block and is never dropped for
brevity. It is the counterweight to the budget: a short report that quietly
omits what was not checked is worse than a long one that admits it.

**On the caller's side**: relay the worker's verdict and its evidence path in
your own words, and never paste the report verbatim. The caller owns routine
technical decisions, failure recovery, integration, and the final synthesis;
worker output is evidence, not something to forward to the operator. This rule
travels in the router's injected directive because it binds the caller and not
the worker.

**Enforcement is asymmetric, and the asymmetry is deliberate.** On OpenCode,
`post_task_gate.py` already runs after every `task()` return and already parses
the output, so it rejects an over-budget report, a pasted diff, a stack trace, or
a missing `Unverified:` line, and `--budget-lines 0` disables the check for a
caller that means it. On Claude Code nothing enforces it: the only mechanism was
a `SubagentStop` hook, and this kit does not install hooks on its users. There
the budget is prose in the agent definition and depends on the worker honouring
it.

**The caller's execution budget** is the task's consequence. Narrow,
reversible work stays local when delegation would cost as much as doing it; its
investigation and verification stay focused. Broader or riskier work earns
fresh worker context and broader evidence. Nothing imposes a line, duration, or
test-count quota: the routing invariant is that coordination must have positive
expected value, not that delegation must happen.
