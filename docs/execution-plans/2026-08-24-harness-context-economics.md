---
status: completed
---
# Context economics: sequencing the seven proposals

Brief: [../briefs/2026-08-24-harness-context-economics.md](../briefs/2026-08-24-harness-context-economics.md)

The brief measures where a session's context actually goes and proposes seven
changes. This plan is the lifecycle half: what has shipped, what is accepted as
an idea and nothing more, and what is waiting on a decision nobody has taken.

Proposals 1 and 2 shipped on 2026-08-24. **Proposal 3 is rejected** — see its
section for the reason, which is a standing constraint on this kit and not a
judgement on the design. Proposals 4, 6 and 7 shipped on 2026-08-25, with 7 at
half its original scope because its meter lived inside Proposal 3's script.
Proposal 5 shipped its contract, invoked by asking for a hand-off in words.
Nothing on this plan is open.

The plan therefore closes with the harness measurably cheaper to start and one
thing it cannot do: nothing deterministic enforces any of it on Claude Code.
Every surviving mechanism there is prose addressed to a model. That is the price
of the hook rule, it was paid knowingly, and it should not be quietly forgotten
the next time someone asks why a budget was ignored.

## Order, and why it is this one

The brief's order is 1 → 2 → 3, and each reason survives review.

**Proposal 1 first**, because every other proposal argues from a number the
operator could not previously see. `1186 lines` is a fact about a file;
`~17,896 tokens` is a fact about what opening it does to the session. The second
is what any decision here turns on, and until the gate printed it, the argument
for every other proposal rested on a measurement nobody could reproduce from the
tool itself.

**Proposal 2 second**, because it installs the missing actuator and costs no
code. The size advisory had a sensor and a display and no consumer: `doc-start`
was told to report and not act, `doc-end` was told to report and stop there, and
both rules were right on their own terms. That is how a document reached 71 KB
while being named at every session for the two months since it first crossed the
limit. Proposal 2 is prose in one command file, so it can ship in the same pass
as Proposal 1 and be judged on its own.

**Proposal 3 was third**, and its argument still stands on the merits: it was the
only deterministic layer among the seven, and every other proposal is a sentence
addressed to a model. It is rejected anyway, on a constraint that sits above the
argument. With it goes the one layer that would have survived a bad session, and
this plan should not pretend otherwise: what remains is prose, and prose is
advisory.

**Proposals 4 to 7 have no forced order among themselves**, and no longer wait on
anything. Each was gated on a decision rather than on another proposal, all the
decisions are taken, so they are ordered by whoever picks one up.

## What depends on what

| item | depends on | nature |
|---|---|---|
| 1 | — | none |
| 2 | 1 | soft. The ledger works without bytes; the verdicts are better informed with them, and both shipped together |
| 3 | — | rejected 2026-08-25. Nothing depends on it any more except 7's meter, which is dropped with it |
| 4 routing rule | — | none. Prose only |
| 4 orientation head | nothing outstanding. The marker was decided on 2026-08-25 | the gate change is small; rewriting ten sub-repo index heads is the real work, and it lands in `hb`, not here |
| 5 | nothing outstanding. Both prerequisites cleared on 2026-08-24 — the path is pinned, and `docs/sessions/` is ignored everywhere it needed to be | was hard: rotation cannot rest on a path that moves, and it no longer moves |
| 6 | nothing outstanding. The evidence path was decided on 2026-08-25 | none on 1-5. On Claude Code nothing enforces it, because enforcement there would be a hook |
| 7 directive half | — | none. Two lines in the router hook's directive |
| ~~7 meter half~~ | ~~3~~ | dropped with 3. The per-session read counter lived inside the read guard's script and has no other home |

## 1 — Report the bill in the unit that is paid — completed 2026-08-24

- [x] `shared/scripts/doc-check.py`: `BYTES_PER_TOKEN = 4` and a `size_note()`
      helper; the oversized-doc advisory and the thin-index failure both carry
      bytes and an estimated token count beside the line count
- [x] Bytes come from `stat`, the number `wc -c` prints, and not from
      `len(text.encode())`: `read_text` translates CRLF, so re-encoding
      under-reports a CRLF file by one byte per line
- [x] `docs/documentation-harness.md`: the bytes/4 estimate recorded as a stated
      convention and never a tokenizer result; the `doc_max_lines` profile-key
      description updated to match what the gate now prints
- [x] `shared/scripts/tests/test_doc_check.py`: five new tests (the advisory's
      three numbers, the divisor pinned, `stat`-versus-re-encode on a CRLF
      fixture, the thin-index message, and the prose rules of 1 and 2); two
      existing assertions updated for the new line format
- [x] Verified: gate clean on this repo, and re-run against `hb`, where the
      printed line matches the brief's proposed line exactly
- [x] `shared/commands/doc-start.md` and its byte-identical Codex mirror: the
      read-scope paragraph described the advisory as naming an oversized doc "by
      path and line count", which under-describes what the gate prints — it is
      path, line count, bytes, and estimated tokens

Deliberately not in scope: the **thresholds** stay line-based. The brief's
finding that "the checker measures the wrong quantity" argues for reporting
bytes, not for a `doc_max_bytes` key — a new profile key would fail every older
installed checker as an unknown key, which is the compatibility trap the
`doc_max_lines` documentation already warns about.

## 2 — Give the oversized-doc advisory an actuator — completed 2026-08-24

- [x] `shared/commands/doc-end.md` Phase 4.1: one obligation. Every document the
      gate's oversized list names must carry a recorded verdict in the
      `## Oversized docs — reviewed` section of `docs/harness-backlog.md`;
      append a row for each named document not already there, and create the
      section (and the backlog file, if the repository has none) the first time
      it fires
- [x] Two verdicts, and no third: `split`, which is work and therefore also an
      ordinary `OPEN` backlog entry, or `keep whole` with its reason on the same
      line
- [x] The split rule stated, because "split it" needs one: split logs, never
      split indexes
- [x] The licence is one line in the backlog. The oversized document itself is
      never touched, `docs/projects/**` stays out of scope, and
      `docs/active-context.md` needs no row because Phase 3 owns it
- [x] `doc-start.md` untouched — it keeps doing nothing with the list, so the
      start of a session stays cheap
- [x] Mirrored byte-for-byte into `codex/skills/doc-end/WORKFLOW.md`;
      `tests/test_codex_install.sh` proves the two files still match
- [x] `docs/documentation-harness.md` records the obligation, because that
      document opens by requiring command prose and checker behavior to agree
      with it

Not done here, and correctly so: this repository's own
`## Oversized docs — reviewed` section does not exist yet. It is written by the
next `/doc-end` run in this repository, which is the mechanism working as
designed, not an omission. The one document that will be named is the brief
itself, which already carries its verdict — keep whole — in its own opening.

## 3 — A read guard that fires on the read — REJECTED 2026-08-25

The proposal was a second Claude Code hook script, `read-guard.py`, on
`PreToolUse` for `Read`, returning `permissionDecision: ask` once per session for
any oversized file requested whole.

**Mario's call, 2026-08-25: this kit does not put hooks on the people who install
it.** The reason is a property of the kit rather than of this proposal. A hook is
ambient machinery: it runs on tool calls its owner never asked it to run on, it
is invisible at the point where it fires, and someone who installed a
documentation harness did not consent to a gate on every `Read` in every
repository they touch. The kit's one existing hook is the model router, and that
one is opt-in behind `/router` — which is the shape any future hook would have to
take, not a precedent for shipping another by default.

This is a standing constraint, so treat it as the answer for the next
hook-shaped proposal too, and do not re-litigate it per proposal.

What is lost, stated plainly rather than softened: this was the only
deterministic layer among the seven. Everything that survives is a sentence
addressed to a model, and a sentence does not bind a session that never read it.
The alternative on Claude Code is not a weaker hook — it is accepting that the
read budget is advisory.

Two things fall out of the rejection:

- **Proposal 7's meter half** lived inside this script and is dropped with it.
  The directive half is unaffected.
- **Proposal 5's automatic trigger** would have been ~15 lines inside the router
  hook. That one is opt-in already, so the constraint above does not strictly
  reach it, but Mario chose manual rotation anyway on the same day. See 5.

## 4 — The meta-repo tax — completed 2026-08-25

Two independent halves. The first is prose and free; the second is a small gate
change plus real editing work in `hb`.

- [x] Written down, as a `## Routing in a meta-repo` section in
      `shared/commands/doc-start.md` and its byte-identical Codex mirror: the
      ownership map answers routing by itself, and a sub-repo index is opened
      when work enters that repository's code — never to decide where work
      belongs. With the corollary that matters when it fails: if the map cannot
      answer, the defect is in the map, and the fix is to mend the map rather
      than pay ten reads to route one change
- [x] **Decided 2026-08-25: the marker is `<!-- orientation ends -->`**, the
      brief's proposal. Above it go stack, entry points, build and test command,
      and the rules that must not be broken. An HTML comment was chosen over a
      `## Orientation` heading because it disappears from the rendered document
      while staying greppable, and over "everything above the first `##`" because
      that convention gives the gate nothing to check: an index that opens
      straight into `## Docs` would be indistinguishable from one with a
      well-written head
- [x] `shared/scripts/doc-check.py`: in `meta` mode, an advisory naming any
      sub-repo index in the `## Services` table that lacks the marker. The table
      parsing already existed in `canonical_repo_dirs`. A sub-repo's index is
      resolved through its own `docs/.doc-profile` when it has one and falls back
      to `CLAUDE.md`, which is what the ones without a profile actually use. A
      sub-repo whose index is missing or unreadable is skipped in silence — that
      is INVENTORY DRIFT's finding, and saying it twice in two vocabularies helps
      nobody. Five tests, and the advisory is proven not to move the exit code
- [x] The tops of the sub-repo indexes rewritten — **nine, not ten**: the tenth
      row of `hb`'s `## Services` table is `docs/`, which is not a repository.
      Every value was copied from that repo's own `CLAUDE.md` or from `hb`'s
      Services / Ownership Map / Quick Reference tables, and a line with no
      written source was omitted rather than guessed. The advisory now prints
      nothing for `hb`. Uncommitted in all nine repositories, deliberately

Enforcement has to come from the meta-repo's gate rather than from each
sub-repo's profile, because three of the nine sub-repos have no profile at all —
`mrcall-dashboard`, `starchat` and `mrcall-website` — and no per-repository rule
reaches them. More thresholds are not the answer: raising a limit does not stop
a file growing, it only moves the line the file crosses.

**What writing the heads exposed**, which is worth more than the heads
themselves: twelve lines had to be omitted across five repositories because the
fact was written down nowhere. `mrcall-desktop`, `mrcall-cs` and `mrcall-ai-kit`
document no build and no test command; `mrcall-website` names neither an entry
point nor a test; `mrcall-tracking` names no entry point, no build and no test;
`cs-kernel` has a test command and no build. Nine repositories, and a session
arriving cold can learn how to build three of them. The heads did not create
that gap, they made it countable — and filling it is documentation work in each
repository, not a harness change.

`mrcall-cs/CLAUDE.md` now sits at 220 lines against its own `index_max_lines` of
221. One line of headroom is not a margin; the next edit to that index fails its
own gate.

## 5 — Session rotation as a context boundary — completed 2026-08-25

Rotation brackets a **context window**; `/doc-start` and `/doc-end` bracket a
**work session** and own the git baseline. A rotation must never run `doc-end`,
never advance the baseline, and never promote anything into `active-context.md`.

Two prerequisites, neither inside the proposal, both now met:

- [x] **Mario's call, taken 2026-08-24: pin the path to the directory the
      session started in**, because it does not move when the work does.
      `claude/scripts/router-hook.py` had built the session-memory path from the
      `cwd` in its payload, which persists across tool calls, so one `cd` into a
      sub-repo moved the session file for the rest of the session, silently. The
      hook now resolves the directory once per session and reads that record on
      every later turn. The second guard shipped with it: a
      `docs/sessions/<id>.md` that already exists in the working directory or any
      of its parents is adopted instead of duplicated, which catches the failure
      even if the path rule is wrong and repairs a session already split by the
      old one
- [x] `docs/sessions/` is in `.gitignore` in `hb`, `mrcall-ai-kit`, `cs-kernel`
      and the clone template `cs/templates/project/.gitignore.j2`, so no
      repository in this tree can commit session memory. The gap itself is
      narrowed, not closed: `doc-create.md` still writes that line only at
      bootstrap and nothing else in the kit ever adds it, so a repository
      bootstrapped before it existed still needs the line by hand

Then the proposal itself:

- [x] The `## Hand-off` template as a fixed section of `docs/sessions/<id>.md`:
      goal in the operator's words, constraints first because compaction destroys
      them, decided, rejected, state, next, ask. Recorded in
      `docs/documentation-harness.md` under `## Session rotation`
- [x] Frontmatter gains `successor_of` and `rotated_at`; `status` stays `open`,
      because the gate accepts exactly `open` or `closed` and a third value
      would fail every older installed checker. No gate change was needed — the
      session check reads `status` and ignores keys beside it
- [x] The resume rule: the successor reads the hand-off plus
      `docs/active-context.md` and does **not** run `/doc-start`
- [x] **How a rotation is invoked: in words, and that is the whole mechanism.**
      A `/router rotate` verb was floated on 2026-08-25 and dropped the same day
      — it was never part of this proposal, and the contract needs no command to
      be usable. The operator asks for a hand-off and the session writes one
- [x] **Decided 2026-08-25: rotation is manual, in every environment.** The
      automatic trigger — about 15 lines in `router-hook.py`, using transcript
      size as an upper-bound proxy — is dropped. It was the one piece of this
      proposal that rode a hook, and although the router is opt-in and so was not
      strictly caught by Proposal 3's rejection, Mario chose not to build it. The
      operator says when to rotate

The consequence to keep in view: without a trigger, rotation happens when someone
remembers, and the moment it is most needed is the moment nobody is watching for
it. The hand-off file is still worth building — a rotation done late is far
better than a compaction that silently drops the constraints — but this proposal
no longer claims to catch the window filling up. It claims to make the hand-off
good once you decide to do one.

The hand-off file and the resume rule work in all three environments, which is
now true without qualification: there is no Claude Code-only half left.

## 6 — A budget for the worker report — completed 2026-08-25

The premise this proposal started from was wrong, and the brief already corrects
it: the workers **do** have a report format. Verified today — all 3
`claude/agents/worker-*.md` and all 16 `opencode/agents/worker-*.md` carry the
`## Done` block. The gap is a length budget, an exclusion list, and a path
convention on the `Changed:` line.

- [x] **Decided 2026-08-25: `$TMPDIR/mrcall-ai-kit/<task-id>/<worker>.log`**, the
      brief's proposal, outside the repository, because a worker's scratch output
      is not repository knowledge and must not be one missing `.gitignore` line
      away from being committed. The evidence is lost on reboot, which is the
      correct trade: it exists to be read in the minutes after the worker
      returns, not to be kept
- [x] A `## Report budget` section in each agent file: at most twenty lines,
      never a diff, a file listing, a stack trace, or more than three consecutive
      lines of command output
- [x] The `Unverified:` line added to the `## Done` block, with the rule that it
      is never dropped for brevity — it is the counterweight to a short report
      that omits the load-bearing detail. `Evidence:` added beside it
- [x] The matching rule on the caller, in the router's `MEMORY_NOTE`: relay the
      verdict and the evidence path in your own words, never paste the report
      verbatim
- [x] 19 files of near-identical mechanical edits — 3 `claude/agents/worker-*.md`
      and 16 `opencode/agents/worker-*.md`, applied by `worker-sonnet`. One shape
      deviation handled rather than flattened: `opencode/agents/worker-auto.md`
      carries an extra `Model used:` field and kept it. The contract paragraph
      landed in `documentation-harness.md`; `doc-end.md` needed none, because the
      rule binds every delegation and not that one command
- [x] OpenCode enforces it: `post_task_gate.py` rejects an over-budget report, a
      pasted diff, a stack trace, or a missing `Unverified:` line, with
      `--budget-lines 0` as the escape for a caller that means it. Verified on
      four hand-built reports — one passing, three failing one rule each
- [x] Claude Code: **not enforced, and this is now settled rather than open.** The
      only mechanism was a `SubagentStop` hook, whose capability was never
      verified and which is a hook regardless — see 3. On Claude Code the budget
      is the agent file's prose and nothing else, so the asymmetry is real:
      OpenCode rejects an over-budget report, Claude Code merely asked for a
      short one

## 7 — Constant cost per request, no longer measured — completed 2026-08-25 at half scope

The property worth keeping from the rejected external draft: the dispatcher's
cost per user request should be roughly constant regardless of the request's
difficulty, because difficulty is absorbed by workers. The kit already has the
mechanism and measures nothing.

- [x] One line in `DIRECTIVE` in `claude/scripts/router-hook.py`, not the two
      budgeted. It belongs there and not in command prose, because `doc-start`
      and `doc-end` are not where general work happens, and not in an agent
      definition, because the discipline binds the caller
- [x] Stated as a budget and not a prohibition: about 100 lines of orienting
      reads, then delegate. "The dispatcher never reads source code" is wrong
      often enough to be discredited on its first day, since reading twenty lines
      is routinely cheaper than briefing a worker to read them
- [x] ~~The meter is a per-session running total inside Proposal 3's script~~ —
      **dropped 2026-08-25 with Proposal 3.** Counting reads requires
      intercepting reads, and the only interception point was that hook. There is
      no second way to build this half, so it is not deferred, it is gone. What
      ships is the budget without its meter: the directive states the number, and
      nothing measures whether the number is respected

## Rejected, and not to be re-proposed

**Any hook this kit would install on its users** — decided 2026-08-25, and it is
the constraint that killed Proposal 3, Proposal 5's trigger, Proposal 7's meter,
and the `SubagentStop` enforcement of Proposal 6. It is a rule about the kit's
relationship with the people who install it, not a verdict on any one design, so
a new proposal does not get to re-argue it by being a better hook. The single
exception already in the tree is the model router, and its licence is that
nothing happens until someone runs `/router`. Anything hook-shaped must be
opt-in in that same explicit sense, and must earn the opt-in on its own.

The brief carries the full list with reasons: an append-only `DISPATCH.md`, a
routing `INDEX.md` capped at fifty lines, per-repository persistent lead agents,
a cron watchdog restarting a dead dispatcher, a new `decisions/` store, "the
dispatcher never reads source code", a `rotated` value in the session `status`
enum, a heading map printed for every oversized doc on every gate run, making
`doc_max_lines` a gate failure, and a machine-readable `.doc-sizes` file that
suppresses reviewed documents from the advisory. Read the brief before
re-opening any of them.
