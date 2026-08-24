---
status: active
---
# Context economics: sequencing the seven proposals

Brief: [../briefs/2026-08-24-harness-context-economics.md](../briefs/2026-08-24-harness-context-economics.md)

The brief measures where a session's context actually goes and proposes seven
changes. This plan is the lifecycle half: what has shipped, what is accepted as
an idea and nothing more, and what is waiting on a decision nobody has taken.

Proposals 1 and 2 are done. Proposals 3 to 7 are `planned` in the schema's exact
sense — conceived and written down, not started, and none of them may begin
without an explicit go. Three of them need a decision from Mario before they
need an engineer, and those decisions are named below rather than assumed.

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

**Proposal 3 third**, because it is the only deterministic layer among the seven.
Every other proposal is a sentence addressed to a model. This repository's own
contract already records what that is worth: three layers hold the
living-context rule, only one is deterministic, and only that one applies to an
edit made by something that never ran a `doc-*` command. A guard that fires on
the `Read` itself is the layer that survives a bad session.

**Proposals 4 to 7 have no forced order among themselves.** Each is gated on a
decision rather than on another proposal, so they are ordered by whoever answers
first.

## What depends on what

| item | depends on | nature |
|---|---|---|
| 1 | — | none |
| 2 | 1 | soft. The ledger works without bytes; the verdicts are better informed with them, and both shipped together |
| 3 | — | none, technically. It reuses `doc_max_lines` rather than adding a profile key, so the gate and the guard agree on "big" without new config |
| 4 routing rule | — | none. Prose only |
| 4 orientation head | a decision on the marker | the gate change is small; rewriting ten sub-repo index heads is the real work, and it lands in `hb`, not here |
| 5 | the `router-hook.py` `cwd` policy call, **and** the `docs/sessions/` gitignore gap | hard. Rotation cannot rest on a path that moves |
| 6 | a decision on the evidence path | none on 1-5. On Claude Code, deterministic enforcement additionally depends on an unverified `SubagentStop` capability |
| 7 directive half | — | none. Two lines in the router hook's directive |
| 7 meter half | 3 | hard. The per-session read counter lives inside the read guard's script |

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

Deliberately not in scope: the **thresholds** stay line-based. The brief's
finding that "the checker measures the wrong quantity" argues for reporting
bytes, not for a `doc_max_bytes` key — a new profile key would fail every older
installed checker as an unknown key, which is the compatibility trap the
`doc_max_lines` documentation already warns about.

Follow-up, left undone by instruction: `shared/commands/doc-start.md` still
describes the advisory as naming an oversized doc "by path and line count". That
now under-describes what the gate prints. It is a factual touch-up to a command
this pass was told not to open; fix it the next time `doc-start` is edited.

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

## 3 — A read guard that fires on the read — planned

A second Claude Code hook script, `read-guard.py`, on `PreToolUse` for `Read`.
It allows silently when the call already carries `offset` or `limit` or targets
a file at or under `doc_max_lines`; otherwise it returns
`permissionDecision: ask` once per session per path, with the file's size, its
heading map, and the three ways forward; a second request for the same file
whole is allowed in silence.

- [ ] `claude/scripts/read-guard.py` — roughly 60 to 80 lines of stdlib Python
- [ ] A registration verb, alongside the one that already manages hook
      registration in `~/.claude/settings.json`
- [ ] An install test in the style of `tests/test_router_install.sh`
- [ ] `docs/documentation-harness.md`: the guard's contract

Claude Code only. The kit ships no hook mechanism for OpenCode, and the only
read control its agents carry is the per-agent `permission` block — verified
today: all 20 files in `opencode/agents/` set `read: allow`, which is a switch on
the whole tool and not a guard that can inspect the file being read. Codex gets
Proposal 2's ledger and the prose protocol only.

The "allow the second request" step is not a nicety. Sometimes the whole file
genuinely is the answer, and a guard that cannot be overruled becomes a guard
that gets uninstalled.

## 4 — The meta-repo tax — planned

Two independent halves. The first is prose and free; the second is a small gate
change plus real editing work in `hb`.

- [ ] Write down that the ownership map in the meta-repo index answers routing by
      itself, and that a sub-repo index is opened when work enters that
      repository's code — never to decide where work belongs
- [ ] **Decision needed**: the orientation-head marker. The brief proposes
      `<!-- orientation ends -->` with stack, entry points, build and test
      command, and the rules that must not be broken above it
- [ ] `shared/scripts/doc-check.py`: in `meta` mode, an advisory naming any
      sub-repo index in the `## Services` table that lacks the marker. The table
      parsing already exists in `canonical_repo_dirs`
- [ ] Rewrite the top of ten sub-repo indexes — mechanical, one repository at a
      time, and it lands in `hb` rather than in this kit

Enforcement has to come from the meta-repo's gate rather than from each
sub-repo's profile, because four of the ten sub-repos have no profile at all and
no per-repository rule reaches them. More thresholds are not the answer: raising
a limit does not stop a file growing, it only moves the line the file crosses.

## 5 — Session rotation as a context boundary — planned, and blocked on a policy call

Rotation brackets a **context window**; `/doc-start` and `/doc-end` bracket a
**work session** and own the git baseline. A rotation must never run `doc-end`,
never advance the baseline, and never promote anything into `active-context.md`.

Two prerequisites, and neither is inside the proposal:

- [ ] **Mario's call**: `claude/scripts/router-hook.py` builds the session-memory
      path from the `cwd` in its payload (verified: lines 50-56). The shell's
      working directory persists across tool calls, so one `cd` into a sub-repo
      moves the session file for the rest of the session, silently. Three
      answers are defensible — pin to the directory the session started in,
      resolve to the git top level, or prefer whichever file already exists. The
      brief recommends pinning. Whichever wins, the hook should also decline to
      create a second file for a session id that already has one elsewhere,
      because that check catches the failure even if the path rule is wrong
- [ ] `doc-create.md` adds the `docs/sessions/` line to `.gitignore` at bootstrap
      and nothing else in the kit ever adds it, so a repository bootstrapped
      before that existed never gets it. Two repositories in this tree are in
      that state

Then the proposal itself:

- [ ] The `## Hand-off` template as a fixed section of `docs/sessions/<id>.md`:
      goal in the user's words, constraints first because compaction destroys
      them, decided, rejected, state, next, ask-the-user
- [ ] Frontmatter gains `successor_of` and `rotated_at`; `status` stays `open`,
      because the gate accepts exactly `open` or `closed` and a third value
      would fail every older installed checker
- [ ] The resume rule: the successor reads the hand-off plus
      `docs/active-context.md` and does **not** run `/doc-start`
- [ ] The trigger, about 15 lines in `router-hook.py`, using the transcript size
      as an upper-bound proxy — the threshold needs calibrating against several
      real sessions

The hand-off file and the resume rule work in all three environments. The
automatic trigger is Claude Code only, because it rides the router hook, so on
OpenCode rotation is a manual act.

## 6 — A budget for the worker report — planned

The premise this proposal started from was wrong, and the brief already corrects
it: the workers **do** have a report format. Verified today — all 3
`claude/agents/worker-*.md` and all 16 `opencode/agents/worker-*.md` carry the
`## Done` block. The gap is a length budget, an exclusion list, and a path
convention on the `Changed:` line.

- [ ] **Decision needed**: the evidence path. The brief proposes
      `$TMPDIR/mrcall-ai-kit/<task-id>/<worker>.log`, outside the repository,
      because a worker's scratch output is not repository knowledge
- [ ] The budget rule in each agent file: at most twenty lines, never a diff, a
      file listing, a stack trace, or more than three consecutive lines of
      command output
- [ ] The `Unverified:` line added, and never dropped for brevity — it is the
      counterweight to a short report that omits the load-bearing detail
- [ ] The matching rule on the caller: relay the verdict and the evidence path,
      never paste a worker's report verbatim
- [ ] Roughly 20 files of near-identical mechanical edits — a `worker-sonnet`
      task — plus the contract paragraphs in `doc-end.md` and
      `documentation-harness.md`
- [ ] OpenCode can enforce it deterministically today, in about fifteen lines in
      `opencode/skills/orchestrator/scripts/post_task_gate.py`, which already
      runs after every `task()` return and already parses the output
- [ ] Claude Code: establish first whether a `SubagentStop` hook can see the
      subagent's returned text. Until that is settled, nothing enforces the
      budget there

## 7 — Constant cost per request, measured — planned

The property worth keeping from the rejected external draft: the dispatcher's
cost per user request should be roughly constant regardless of the request's
difficulty, because difficulty is absorbed by workers. The kit already has the
mechanism and measures nothing.

- [ ] Two lines in `DIRECTIVE` in `claude/scripts/router-hook.py`, adding about
      150 bytes and 37 tokens to each routed turn. It belongs there and not in
      command prose, because `doc-start` and `doc-end` are not where general work
      happens, and not in an agent definition, because the discipline binds the
      caller
- [ ] It must be a budget and not a prohibition: about 100 lines of orienting
      reads, then delegate. "The dispatcher never reads source code" is wrong
      often enough to be discredited on its first day, since reading twenty lines
      is routinely cheaper than briefing a worker to read them
- [ ] The meter is a per-session running total inside Proposal 3's script, which
      already intercepts every `Read`, emitting one line when the budget is
      passed and nothing while the session is inside it

## Rejected, and not to be re-proposed

The brief carries the full list with reasons: an append-only `DISPATCH.md`, a
routing `INDEX.md` capped at fifty lines, per-repository persistent lead agents,
a cron watchdog restarting a dead dispatcher, a new `decisions/` store, "the
dispatcher never reads source code", a `rotated` value in the session `status`
enum, a heading map printed for every oversized doc on every gate run, making
`doc_max_lines` a gate failure, and a machine-readable `.doc-sizes` file that
suppresses reviewed documents from the advisory. Read the brief before
re-opening any of them.
