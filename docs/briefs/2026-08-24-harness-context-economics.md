# Context economics: the harness starts cheap and reads expensive

**Date**: 2026-08-24 · **Plan**:
[../execution-plans/2026-08-24-harness-context-economics.md](../execution-plans/2026-08-24-harness-context-economics.md),
which carries the lifecycle — Proposals 1 and 2 shipped on 2026-08-24, the rest
are `planned` and none of them has a go.

The gate names this file in its oversized-doc advisory. Verdict under Proposal
2's own rule: **keep whole** — it is one argument resting on one table, and
splitting it would mean reading three files to follow it.

## Problem

The complaint that started this was one sentence: the `hb` meta-repo is
excellent to work in, and it burns context fast.

A design draft arrived from an external model to answer it, proposing a
dispatcher above per-repo lead agents above workers, a routing `INDEX.md` capped
at fifty lines, an append-only `DISPATCH.md` of every hand-off, a `decisions/`
store, and a cron watchdog to restart a dead dispatcher. It was written without
access to `hb` and without a single measurement of it.

Measuring moved the problem. Session start-up in `hb` costs about thirteen
thousand tokens, which is cheap and is not growing. One document in the same
repository costs more than the entire start-up, and it grew by nearly four
hundred percent in three months while the harness reported its size at every
session and nothing in the harness was permitted to act on the report.

## The measurement

Every number is `wc -c` on a real file on this machine at 13:52 UTC on
2026-08-24, or a live run of the hook it describes. The repository changes under
the table, so the measurement time is part of the measurement. Token figures are
bytes divided by four. That divisor is a convention for English prose and not a
tokenizer result, and it carries none of the argument: every conclusion below is
a ratio between two numbers produced by the same divisor, so a wrong divisor
cancels out.

### What a session pays before the user says anything

| path | bytes | est. tokens |
|---|---|---|
| `~/.claude/CLAUDE.md` (user global) | 5,084 | 1,271 |
| `hb/CLAUDE.md` (project index) | 14,973 | 3,743 |
| `~/.claude/projects/-home-mal-hb/memory/MEMORY.md` (index only) | 4,772 | 1,193 |
| skill and command catalog (generated, 23 entries) | 7,932 | 1,983 |
| `~/.claude/commands/doc-start.md` | 8,169 | 2,042 |
| `docs/README.md` | 3,638 | 910 |
| `docs/active-context.md` | 7,872 | 1,968 |
| `docs/.doc-profile` | 287 | 72 |
| **total** | **52,727** | **13,182** |

That is close to the floor for a ten-repo meta-repo with the doc-harness, the
router, and a personal memory index loaded. Per-turn recurring cost is 1,162
bytes, about 291 tokens, of which the router hook's directive is 1,090 bytes.

### What one document costs

The gate names ten documents in `hb` as past the 400-line advisory limit. The
five largest:

| doc | lines | bytes | est. tokens |
|---|---|---|---|
| `docs/known-issues-and-solutions.md` | 1,186 | 71,585 | 17,896 |
| `docs/briefs/cs-kernel-manifest-separation.md` | 766 | 61,632 | 15,408 |
| `docs/execution-plans/mrcall-credits-desktop.md` | 820 | 51,854 | 12,964 |
| `docs/briefs/2026-08-01-mrcall-desktop-cs-kernel-engineering-brief.md` | 908 | 38,590 | 9,648 |
| `docs/dependency-map.md` | 684 | 36,718 | 9,180 |
| **those five** | | **260,379** | **65,095** |
| **all ten** | | **375,107** | **93,777** |

Reading `known-issues-and-solutions.md` once costs 1.36 times the entire session
bootstrap. The five together cost 4.94 times it, and all ten cost 7.11 times it.
Four of the ten are execution plans totalling 123,563 bytes, and an 820-line
execution plan is a lifecycle problem wearing a size problem's clothes.

The growth of the worst offender is the evidence that this does not
self-correct. Measured at four monthly points from git, it went from 241 lines
and 16,210 bytes on 2026-05-24 to 754, then 967, then 1,186 lines and 71,585
bytes today — an increase of 392% over the three months. It crossed the 400-line
limit on 2026-06-16 at 415 lines and 26,445 bytes, and since then the gate has
named it at every `/doc-start` and every `/doc-end` while it added roughly
19,900 bytes a month. Each of those months adds about 4,600 tokens to the price
of reading it once.

### What the meta-repo costs on demand

Ten sub-repository indexes sit under `hb`, totalling 77,521 bytes and about
19,380 tokens. They load when work enters that sub-repo, which the meta-repo's
own critical rules require, and no session pays all ten. A single-repo session
pays between 361 tokens for `mrcall-ai-kit/CLAUDE.md` and 4,171 for
`mrcall-cs/CLAUDE.md`; a change touching the four largest — `mrcall-cs`,
`cs-kernel`, `mrcall-tracking`, `mrcall-dashboard` — pays 49,538 bytes, about
12,385 tokens, which is 94% of the whole bootstrap. Six of the ten run the
doc-harness and four have no `docs/.doc-profile` at all, which determines where
any rule about them can be enforced.

### What the numbers say

Context here is not burned at start-up. It is burned mid-session, on whole-file
reads of documents nobody is allowed to shrink.

A second finding hides in the same numbers. The gate's limits count lines and
the bill is paid in bytes, and the two do not track each other.
`known-issues-and-solutions.md` averages 60 bytes a line and `hb/CLAUDE.md`
averages 94 because it is dense tables, so `hb/CLAUDE.md` passes the 200-line
thin-index check comfortably at 160 lines while being the most expensive single
item in the bootstrap at 3,743 tokens. The checker measures the wrong quantity.

## Platform facts these proposals rely on

**Claude Code can resume a subagent, and the kit already depends on it.**
Verified from local files. `~/.claude/cache/changelog.md` carries the entry
`The Agent tool no longer accepts a resume parameter — use SendMessage({to:
agentId}) to continue a previously spawned agent`, plus later entries about
auto-resuming stopped agents. A stored tool result under
`~/.claude/projects/-home-mal-hb/` returns `agentId: <id> (use SendMessage with
to: '<id>', summary: '<5-10 word recap>' to continue this agent)`. The memory
note in `claude/scripts/router-hook.py` already tells a routed session to
continue the same worker via `SendMessage` instead of spawning a new one. The
same changelog documents `PreToolUse` hooks returning `additionalContext` with a
`permissionDecision` of `ask`, and `SubagentStop` hooks returning
`hookSpecificOutput.additionalContext`, which two proposals below need.

**Whether OpenCode has an equivalent of `SendMessage` is unverified, and this
brief treats it as absent.** Searching the whole `opencode/` tree for
`SendMessage`, `agentId`, and `agent_id` returns nothing at all, and `resume`
returns exactly one line, in `opencode/agents/orchestrator.md`, telling the
orchestrator to "resume an open pair" of work-trace documents rather than
duplicate them — a rule about brief-and-plan files, not about agents. No shipped
agent, command, or skill names a way to continue a worker. Whether the `task`
tool can resume a subagent at all is an open question, carried in
`docs/harness-backlog.md`; nothing in the shipped orchestrator implements or
documents it. The only OpenCode session API
the kit exercises is the
watchdog's `POST /session/{id}/abort`, which proves a session-scoped local API
exists and says nothing about resuming a subagent. Where a proposal needs
continuity on OpenCode the fallback is a file inbox: write the thread state
outside the repository and re-invoke `task` with a prompt whose first
instruction is to read it. That is strictly weaker, because the worker's
reasoning is gone and only what it wrote survives.

## Proposal 1 — Report the bill in the unit that is paid

`doc-check.py`'s advisory lines gain bytes and an estimated token count beside
the line count, and the thin-index failure message gains the same.

```
- docs/known-issues-and-solutions.md: 1186 lines, 71,585 bytes, ~17,896 tokens (advisory limit: 400 lines)
```

This comes first because every other proposal argues from a number the operator
cannot currently see. "1186 lines" is a fact about a file. "~17,896 tokens" is a
fact about what opening it does to the session, and that is the fact that
decides anything. The gate already reads each indexed document to count lines,
so the bytes are free. One sentence in `documentation-harness.md` records that
the estimate is a convention, not a measurement.

**Cost**: two f-strings, two or three test assertions, one paragraph of
contract, identical on all three environments since `doc-check.py` is the one
shared tool-independent artifact. No new profile key, so no older-checker
compatibility risk, and no `harness_version` bump. **Does not fix**: nothing at
all by itself; it shrinks no file and prevents no read.

## Proposal 2 — Give the oversized-doc advisory an actuator

The advisory has no consumer. `doc-start.md` says of it: "Do not open a named
file to assess it, do not trim or rename it, do not propose a restructuring
unasked — reporting is the whole job, and the operator decides what to do about
it." `doc-end.md` says: "Report those lines and stop there." Each rule is right
on its own terms. Together they build a control loop with a sensor, a display,
and no actuator, which is how a document grew from 26 KB to 71 KB while being
reported at every session for the two months since it first crossed the limit.

`doc-end`, never `doc-start`, gains one obligation: compare the gate's oversized
list against a fixed section of `docs/harness-backlog.md`, and record a verdict
for any named document not yet listed there.

```markdown
## Oversized docs — reviewed

| doc | lines at review | verdict | date |
|---|---|---|---|
| docs/known-issues-and-solutions.md | 1186 | split into docs/known-issues/ | 2026-08-24 |
| docs/dependency-map.md | 684 | keep whole — read by section | 2026-08-24 |
```

Two verdicts exist: `split`, which is work and therefore also a backlog item, or
`keep whole` with the reason on the same line. `doc-start` keeps doing nothing,
so the start of a session stays cheap, and the obligation lands where the
harness already holds an editing licence and a human is present. It is a narrow
amendment to `doc-end`'s rule that its licence covers only what the session
changed: it may write the backlog, which Phase 3 already tells it to do, and it
still may not touch the oversized document itself. The steady state is zero
work, because a document with a recorded verdict is never asked about again.

**The split rule, because "split it" needs one: split logs, never split
indexes.** A log is retrieved by search, so cutting it into one file per entry
makes the search return a small file and the read small. An index is retrieved
by traversal, so cutting it up means more reads rather than fewer. In `hb`,
`known-issues-and-solutions.md` becomes `docs/known-issues/YYYY-MM-DD-<slug>.md`
per incident with a one-line symptom index above it, `dependency-map.md` and
`operator-access.md` stay whole and are read by section, and the four oversized
execution plans are a lifecycle question `doc-end` already owns.

**Cost**: about 20 lines of prose in `shared/commands/doc-end.md`, mirrored into
the Codex workflow, plus one section per adopting repository. No code, no
version bump, identical on all three environments. **Does not fix**: it shrinks
nothing by itself and does not stop a session reading a big document whole; it
guarantees only that somebody decides, once, per document, in writing.

## Proposal 3 — A read guard that fires on the read

Every rule in this kit about reading less is a sentence addressed to a model,
and `docs/documentation-harness.md` already records what that is worth: "Three
layers hold this rule, because two of them are LLM judgment and judgment is what
failed", and of the single deterministic layer among the three, "only the first
applies to an edit made by something that never ran a `doc-*` command at all."
The expensive event is a `Read` of a 71 KB file with no offset and no limit, and
nothing observes that event.

A second hook script, `read-guard.py`, registered on `PreToolUse` for `Read` and
installed by the same command that already manages hook registration in
`~/.claude/settings.json`:

1. Allow and emit nothing when the call is not a `Read`, already carries
   `offset` or `limit`, or targets a file at or under the threshold. The
   threshold is the repository's `doc_max_lines`, defaulting to 400, so the
   guard and the gate agree on what "big" means without a new profile key.
2. Otherwise return `permissionDecision: ask`, once per session per path, with
   the file's size in bytes and tokens, its heading map from
   `grep -n '^#\{1,3\} '`, and the three ways forward: read a named range, grep
   for the term, or hand the whole-file read to a worker.
3. Record the path, and allow a second request for the same file whole in
   silence.

That last step is what makes it shippable. Sometimes the whole file genuinely is
the answer, and a guard that cannot be overruled becomes a guard that gets
uninstalled.

**Cost**: roughly 60 to 80 lines of stdlib Python, a registration verb, and a
test in the style of `tests/test_router_install.sh` — a focused day. Claude Code
only: the kit ships no hook mechanism for OpenCode, whether OpenCode exposes a
pre-tool hook API was not verified here, and the only read control the kit's
OpenCode agents carry is the per-agent `permission` block, which all twenty of
them set to `read: allow` — a switch on the whole tool, not a guard that can
inspect the file being read. Until someone
verifies an equivalent, OpenCode gets Proposal 2's ledger and the prose protocol
only. **Does not fix**: it reduces the size of nothing, does nothing on OpenCode
or Codex, and cannot help a session that burns context on reasoning.

## Proposal 4 — The meta-repo tax

Two changes, in proportion to a tax that is real and is not an emergency.

First, a routing rule that costs nothing. The meta-repo index already contains
the ownership map, a table answering "which repository owns this concern". That
is the routing index the external draft wanted to build, it exists, and it is
already paid for in the bootstrap. Write down that the ownership map answers
routing by itself, and that a sub-repo index is opened when work enters that
repository's code, never to decide where work belongs.

Second, an orientation head for sub-repo indexes. The first section answers
stack, entry points, build and test command, and the two or three rules that
must not be broken. Everything below a `<!-- orientation ends -->` marker is
detail. A session entering a sub-repo reads to the marker and goes past it only
when the work is not covered. In `meta` mode the gate reports, as an advisory,
any sub-repo index in the `## Services` table lacking the marker; the parsing
already exists in `canonical_repo_dirs`. Enforcement has to come from the
meta-repo's gate rather than each sub-repo's profile, because four of the ten
sub-repos have no profile and no per-repository rule reaches them.

More thresholds are not the answer. `mrcall-cs/docs/.doc-profile` raises
`index_max_lines` from the default 200 to 221, with a comment explaining that
the index is rendered from a `cs-kernel` template and that 221 keeps the
thin-index check meaningful without fighting the template. `mrcall-cs/CLAUDE.md`
is now 290 lines. It is 69 lines past the limit written for it, and that
repository's gate fails its thin-index check today. A per-repository tunable does
not stop a file growing; it only moves the line the file crosses.

**Cost**: about 25 lines in `doc-check.py` plus tests, one line in
`doc-create.md`, and a rewrite of the top of ten sub-repo indexes, which is the
real work and is a mechanical worker's task one repository at a time. Shared
across all three environments. **Does not fix**: it saves nothing unless the
orientation head is genuinely sufficient for most visits, and only weeks of use
can establish that.

## Proposal 5 — Session rotation is a context boundary, not a work boundary

Get this distinction right or the feature does damage. `/doc-start` and
`/doc-end` bracket a **work session**, and their unit of account is a git
baseline: `doc-end` advances `doc_baseline_commit` to the commit whose behavior
has been reconciled into the documentation. Rotation brackets a **context
window**, and its unit of account is a conversation. One work session can span
several context windows, so a rotation must not run `doc-end`, must not advance
the baseline, and must not promote anything into `active-context.md`. Both
failure modes deserve naming. A rotation that calls `doc-end` advances the
baseline over unfinished work and records an in-flight workstream as reconciled.
A `doc-end` that behaves like a rotation leaves the baseline stale and the
documentation unreconciled while everyone believes the session closed properly.

Rotation beats auto-compaction because compaction is lossy in the wrong
direction: it preserves recent detail and drops the early turns, and the early
turns are where the user states the constraints.

**The trigger.** The router hook already runs on every user prompt with
`session_id` and `cwd`, and `/router sweep` already knows Claude Code's
transcript path convention. So the hook can `stat` this session's transcript,
use its size as a monotone proxy for what the session has consumed, and append
one line to the directive it already emits once past the threshold. The proxy
over-counts, because the transcript holds everything ever sent including material
a compaction has evicted, so it is an upper bound on live context. The threshold
needs calibrating against real sessions, and the data available today is that
the largest top-level session transcript in this repository is 3,373,821 bytes,
four sit between 1.2 and 2.5 MB, and the session that produced this brief was
at 963,833 bytes when the table above was measured.

**What the hand-off must contain**, as a fixed section of
`docs/sessions/<session-id>.md`:

```markdown
## Hand-off

- **Goal** — the user's request in the user's own words, quoted, not paraphrased.
- **Constraints** — every instruction that narrows the solution space, quoted
  where short. This is the material compaction destroys, so it is first.
- **Decided** — one line per decision, with its reason.
- **Rejected** — one line per approach tried and abandoned, with its reason, so
  the successor does not retry it.
- **State** — files changed so far; commands whose output is load-bearing, with
  that output.
- **Next** — the immediate next action, written as an instruction to the successor.
- **Ask the user** — open questions only the user can answer.
```

Frontmatter gains `successor_of` and `rotated_at`. The `status` stays `open`,
which is both true and useful: the file has not been promoted, and the gate
accepts exactly `open` or `closed` and would fail on anything else.

**How the successor resumes.** The shipped path is manual and needs no code. The
outgoing session prints the hand-off path, the user opens a new session and
pastes it, and the successor reads that file plus `docs/active-context.md`. The
successor does not run `/doc-start`: the baseline has not moved, the gate ran at
the top of the work session, and the plan scan has not changed, so re-running it
re-pays the bootstrap for no new information. The hand-off header says exactly
that and carries the unchanged baseline SHA. Optionally the hook can name a
hand-off marked `rotation_pending` to the new session, which is about ten lines
and carries a real ambiguity: two concurrent sessions in one repository would
both see it, so the hook can only offer a candidate to confirm with the user.

Session A can rotate to B and B to C, and the `doc-end` that ends the work
session promotes and closes all three. The machinery for a broken chain exists:
the gate's open-session advisory names every file still `open`, and
`/router sweep` flags the ones whose transcripts look dead. One prerequisite
nobody has noticed is that `doc-create` adds `docs/sessions/` to `.gitignore`
only at bootstrap, and nothing else in the kit ever adds it, so a repository
bootstrapped earlier never gets the line. Two repositories in this tree are in
that state: `cs-kernel` has no such line and has already committed a session
file, and `mrcall-cs` has no such line and holds four session files that nothing
prevents from being committed next.

**A second prerequisite, and it is a live defect.** `router-hook.py` builds the
session-memory path from the `cwd` in its payload, as
`cwd / "docs" / "sessions" / f"{session_id}.md"`. That `cwd` is the shell's
working directory, and the shell's working directory persists across tool calls.
One `cd` into a sub-repository therefore moves the session file for every later
turn of the same session. This happened while this brief was being written: a
`cd` into `mrcall-ai-kit` to run its gate, and the next turn's directive named
`mrcall-ai-kit/docs/sessions/<id>.md` where every previous turn had named
`hb/docs/sessions/<id>.md`. Nothing was written to the moved path in this
instance and no memory was lost, but the failure is silent by construction. A
successor following the directive finds no file, creates an empty one, and
starts from nothing while the real snapshot sits in the other repository. No
error is raised at any point, because creating a missing session file is the
documented behavior.

Rotation cannot rest on a path that moves, so this is a prerequisite for
Proposal 5 rather than an aside. The repair is a policy choice and not a patch,
because three answers are each defensible: pin the path to the directory the
session started in, resolve it to the git top level, or prefer whichever
`docs/sessions/<id>.md` already exists. Pinning to the starting directory is the
most predictable, since it does not change when the work does. Whichever is
chosen, the hook should also decline to create a second file for a session id
that already has one elsewhere, because that check catches the failure even if
the path rule is wrong.

**Cost**: the template and rules are prose in `documentation-harness.md` and the
hook's memory note, half a day; the trigger is about 15 lines in
`router-hook.py` plus a threshold needing several real sessions to calibrate. The
hand-off file and the resume rule work in all three environments; the automatic
trigger is Claude Code only because it rides the router hook, so on OpenCode
rotation is a manual act. **Does not fix**: a hand-off is a summary and summaries
lose things, and the claim is only that it loses the right ones. It does nothing
for a session that dies without warning, which stays an `open` orphan.

## Proposal 6 — A budget for the worker report

**Correcting the premise first.** The assumption behind this section was that
the kit's worker agents have no report format. They do. All three
`claude/agents/worker-*.md` end with a `## Done` block carrying `Changed` /
`What` / `Verified` and a `## Blocked` block carrying `Reason` / `What I tried` /
`Suggestion`; all sixteen `opencode/agents/worker-*.md` carry the same skeleton;
`shared/commands/doc-end.md` states the contract and what to do when it is
violated.

The real gap is three specific things. The format has no length budget:
`What: <1-2 sentence summary>` is bounded and `Verified: <command + its real
output>` is not, and "its real output" invites pasting a two-hundred-line test
run into the caller's context. The format has no exclusion list, so nothing
forbids a diff, a file listing, or a stack trace travelling upward. The
`Changed:` line has no path convention, and that gap is already patched outside
the agent files by a runtime addendum asking for absolute paths, which is
evidence somebody felt it and fixed it in the wrong place.
`opencode/agents/reviewer.md` is a fourth case, with a larger format and no cap.

**The tension, and its resolution.** A "what I verified" section is what makes a
report trustworthy and is also exactly the upward traffic that needs rationing.
So evidence is relocated rather than suppressed: the verdict lines travel, the
bulk goes to a file, and the report names the path, so the caller pays for
evidence only when it decides it needs it. That is the principle the gate already
applies when it names an oversized document by path and line count instead of
summarizing it.

```markdown
## Done
- Changed: <absolute paths, comma-separated; or "none — review only">
- What: <at most 3 sentences>
- Verified: <one command per line, each followed by at most 3 lines of its real
  output — the lines that carry the verdict, not the whole run>
- Unverified: <one line per claim you could not check; omit the line if none>
- Evidence: <path to the full output, when it exceeded the budget; omit if not>

## Blocked
- Reason: <at most 2 sentences>
- What I tried: <at most 4 lines, one step each>
- Suggestion: <at most 2 sentences: what the caller should do next>
- Evidence: <path, when there is output worth keeping; omit if not>
```

The budget rule, stated in each agent file: the whole report is at most twenty
lines and never contains a diff, a file listing, a stack trace, or more than
three consecutive lines of command output. Anything larger goes to
`$TMPDIR/mrcall-ai-kit/<task-id>/<worker>.log` and is named on `Evidence`, which
is outside the repository because a worker's scratch output is not repository
knowledge and the OpenCode orchestrator already sets that precedent with
`/tmp/opencode/last_worker_out.txt`. The caller owes the matching rule: relay the
verdict and the evidence path, never paste a worker's report verbatim.

OpenCode can enforce this deterministically today, because
`opencode/skills/orchestrator/scripts/post_task_gate.py` already runs after every
`task()` return and already parses the output. Claude Code has a `SubagentStop`
hook that can return `additionalContext`, so the same check looks possible;
whether that hook can see the subagent's returned text was not verified, so
shipping it should start by establishing that.

**Cost**: three Claude agent files, sixteen OpenCode workers, the reviewer, the
orchestrator's prompt template, and the contract paragraphs in `doc-end.md` and
`documentation-harness.md` — about twenty files of near-identical mechanical
edits, which is a `worker-sonnet` task, plus roughly fifteen lines in
`post_task_gate.py`. **Does not fix**: on Claude Code nothing enforces the budget
until the `SubagentStop` question is settled, and a short report that omits the
load-bearing detail is a worse failure than a long one. The `Unverified` line is
the counterweight and must never be dropped for brevity.

## Proposal 7 — Constant cost per request, measured

The idea worth keeping from the external draft is that the dispatcher's cost per
user request should be roughly constant regardless of the request's difficulty,
because difficulty is absorbed by workers. That is a metric, not a mechanism.
The kit already has the mechanism, since the router classifies and pinned-model
workers absorb, and nothing measures whether the property holds.

The rule belongs in the router hook's directive. Not in command prose, because
`doc-start` and `doc-end` are not where general work happens. Not in an agent
definition, because the discipline binds the caller and the workers are the wrong
end of the wire. The directive is the only text that fires on every turn of
exactly the sessions where routing is supposed to be happening.

It has to be a budget, not a prohibition. "The dispatcher never reads source
code" is too absolute and is wrong often enough to be discredited on its first
day, because reading twenty lines is routinely cheaper than briefing a worker to
read them. The workable form: the session may read about 100 lines while
orienting a request, and past that it delegates. A number can be checked; a
prohibition can only be argued with. The read guard from Proposal 3 already
intercepts every `Read`, so it can keep a per-session running total and emit one
line when the budget is passed, and nothing while the session is inside it.

**Cost**: two lines in `DIRECTIVE` in `router-hook.py`, adding roughly 150 bytes
and 37 tokens to each routed turn, plus a counter in a script Proposal 3 is
already adding. The directive works anywhere; the meter is Claude Code only.
OpenCode's orchestrator already states a stronger version in its edit policy,
which forbids it from writing code beyond an approved one-line fix — though that
file also records that its own `edit: allow` permission will not enforce the
rule, so the approval has to come from a `question`. **Does
not fix**: a budget on bytes read says nothing about a session that burns context
on long reasoning or twenty small tool calls.

## What was rejected, and why

**An append-only `DISPATCH.md`.** Exactly the changelog drift the kit's own
`doc-critic` skill and mechanical gate police in `active-context.md`, where a
real repository grew the file to 1,036 lines over three months before a single
consolidation cut it back to 59. A file that grows forever is a context bomb.

**A routing `INDEX.md` capped at fifty lines.** Redundant, because
`index_max_lines` already caps the index; backwards, because splitting an index
costs more reads rather than fewer; and aimed at the wrong target, since
`hb/CLAUDE.md` is 3,743 tokens against a 71,585-byte document nobody reads
partially.

**Per-repository persistent lead agents.** `hb` already routes cross-repo work
with the ownership map in its index, at zero marginal cost because that table is
already in the bootstrap. Where a standing worker is genuinely wanted, Claude
Code agents are resumable by `agentId` through `SendMessage`, which gives the
continuity without a permanent fleet to keep alive and in sync.

**A cron watchdog restarting a dead dispatcher.** It solves a problem the user
does not have, since he is present in his sessions, and the kit already declined
the analogous OpenCode watchdog for Claude Code on recorded grounds.

**A new `decisions/` store.** A fourth durable store beside briefs, known-issues,
and active-context, where `docs/README.md` already rules that "other durable docs
are added only when the knowledge exists". Decisions already have a home: the
brief holds the what and why, the paired plan holds the lifecycle.

**"The dispatcher never reads source code."** Too absolute; replaced by the
budget in Proposal 7.

**A `rotated` value in the session `status` enum.** The gate accepts exactly
`open` or `closed`, so a third value fails every older installed checker and
forces a `harness_version` bump plus a migration for no behavioral gain. An
`open` file with `successor_of` says the same thing.

**Printing a heading map for every oversized document in every gate run.** Nearly
free to compute and about 200 lines injected at every `doc-start` for a read that
happens rarely. Charging every session for a map most sessions never use is the
same mistake this brief is about; the read guard emits it exactly when a session
is about to need it.

**Making `doc_max_lines` a gate failure.** The kit settled this for work-trace
filenames: a blocking check would break existing repositories and require a
version bump plus a migration, and the convention can get teeth without either.
The ledger in Proposal 2 is those teeth.

**A machine-readable `.doc-sizes` file suppressing reviewed documents from the
advisory.** Rejected because it moves a judgment into a config file where nobody
re-examines it, and because ten advisory lines a session is far too cheap to be
worth suppressing.

## Order

Proposal 1 makes the cost visible and everything later argues from what it
prints. Proposal 2 installs the missing actuator without a line of code.
Proposal 3 is the only deterministic one, and this kit's own history says the
deterministic layer is the one that survives contact with a bad session.
