# Harness Backlog

Deferred doc-harness / orchestration improvements.

## OPEN — orchestrator REVIEW.md is an Italian artifact

**Logged**: 2026-08-14. `opencode/skills/orchestrator/REVIEW.md` is a ~300-line
review document written in Italian. The work-trace pass of 2026-08-14 rewrote
the orchestrator's *live* protocol files into English (SKILL.md question
templates, `agents/orchestrator.md`) but deliberately left REVIEW.md: it is a
historical analysis whose findings partly shaped the current protocol, and a
wholesale rewrite is a dedicated job, not a side edit. On the next pass that
touches the orchestrator, rewrite it in English — or decide it is superseded
and archive it.

## DONE — Mechanical enforcement of the living-context shape (harness v3)

**Status**: DONE (2026-08-04). The shape rule had two enforcement layers and
both were LLM judgment, so both failed in the same repo on the same day: it
drifted to ~1500 lines across two months of sessions that each said
"consolidate", and was then cut from 1441 lines to 76 by a session that never
invoked `doc-end`, discarding 1436 lines with no archive and four durable
engineering invariants with them. No instruction to an agent can prevent an
edit made by something that does not run the command.

**Outcome**: `doc-check.py` gained `check_living_context` — any `##` section in
`docs/active-context.md` outside `State now` / `Unresolved` / `Next` fails the
gate. Deliberately narrow: headings are the objective half of the contract, so
prose narration and "too long for what it says" stay with the semantic critic
where judgment belongs. A `##` inside a code fence is content, not a section
(the real file that motivated this contains such lines). The archive is exempt
by design. `harness_version` bumped 2→3, since this is a new requirement on
what a repository's `docs/` must contain.

**Verified**: 21 checker tests (5 new, covering canonical/non-canonical, case
and subsections, code fences, absent file, and archive exemption); replayed
against the real pre-trim `active-context.md` from the repo above it reports 27
violations.

## DONE — Pinned-model workers for Claude Code, so doc-end stops burning top-tier tokens

**Status**: DONE (2026-08-04). `doc-end` ran entirely on whatever model the
session used, which on a top-tier model is expensive for work that is partly
mechanical. Delegating with no declared model does not help: a subagent
inherits the parent's model, saving context but not cost.

**Outcome**: `claude/agents/worker-sonnet.md` (mechanical execution) and
`claude/agents/worker-opus.md` (independent verification) declare their own
`model:`, installed to `~/.claude/agents/` as part of `doc-harness` — not an
opt-out, since `doc-end` depends on them. `doc-end` gained `Agent` in
`allowed-tools` plus a delegation section written tool-agnostically, so the
Codex and OpenCode mirrors stay byte-identical and degrade to inline work
where no worker exists. Phases 2 and 3 (session signal; deciding what is
current) are declared non-delegable — only the session holds the transcript.

**Verified live, both directions**: a Sonnet parent delegating to `worker-opus`
got `claude-opus-5[1m]`; an Opus parent delegating to `worker-sonnet` got
`claude-sonnet-5`, and that worker confirmed it has no `Agent` tool (no
recursive delegation, mirroring OpenCode's `task: deny`). Installer verified in
a disposable HOME. No `harness_version` bump: delegation changes how the
command executes, not what a repository's `docs/` must contain.

**Not ported from OpenCode** (deliberate): the watchdog daemon, which enforces
timeout/budget through OpenCode's own session-abort API and has no Claude Code
equivalent; and the multi-provider worker roster, since `model:` selects among
models the session can already reach and provider routing is process-level,
leaving Sonnet as the one useful cheaper tier.

## DONE — Archive pruned active-context.md content instead of discarding it (harness v2)

**Status**: DONE (2026-08-04, commit `838eb78`). `doc-end` Phase 3 already said
"reconsolidate, don't append", but nothing mechanical enforced it — a real
downstream repo's `active-context.md` grew from ~120 to ~1500 lines over two
months of sessions that each said "consolidate" in their own commit message.

**Outcome**: pruned session narrative now moves to
`docs/active-context-archive.md` (dated, newest first, verbatim) instead of
being deleted. `doc-end` archives it proactively every session; `doc-critic`
gained an independent living-context shape check which, as shipped in that
commit, repaired the file directly rather than only flagging it — split the
same day into report-when-delegated / repair-in-session, per the entry above,
so this clause records `838eb78` and not current behavior. `harness_version` bumped 1→2
(protocol change, per this repo's own compatibility-handshake design);
`doc-create` gained an explicit v1→v2 migration note. Verified: 16 doc-check
tests + the Codex install layout test pass, and the shape-repair behavior was
exercised for real against a scratch fixture — confirmed byte-for-byte zero
information loss versus the pre-repair git blob, correct STALE detection on
the post-repair remainder. (Commit `838eb78`'s message says "18 doc-check
tests"; the real count is 16 — 14 pre-existing plus 2 added. The commit
message cannot be corrected, this line is the correction.)

**Follow-up (open, see `docs/active-context.md` Next)**: the v1→v2 migration
note in `doc-create.md` has not itself been exercised against a real v1 repo
yet — only `doc-critic`'s repair was tested directly.

## DONE — Wire OpenRouter into OpenCode for Auto Router

**Status**: DONE (2026-07-25). Authentication and the Auto Router were verified
end-to-end by delegating to `subagent_type="worker-auto"`. No extra provider
declaration in `opencode.json` was required; the key in `auth.json` was enough.

**Outcome**: the working OpenCode slug is `openrouter/openrouter/auto`, not
`auto-beta`, which is absent from the registry. Full detail is in
`docs/briefs/2026-08-01-test-worker-auto.md` and `docs/active-context.md`.

**Sources** (verified 2026-07-25 on docs.openrouter.ai):
- Auto Router: `https://openrouter.ai/docs/guides/routing/routers/auto-router.md`
- OpenCode integration: `https://openrouter.ai/docs/cookbook/coding-agents/opencode-integration.md`
- Latest Model Resolution: `https://openrouter.ai/docs/guides/routing/routers/latest-resolution`

## DONE — Document auto-updating mechanisms in llms.md

**Status**: DONE (2026-07-25).

**Outcome**: `llms.md` now documents (1) the elastic `worker-auto` using
`openrouter/openrouter/auto` and (2) the ten tilde-latest aliases present in the
OpenCode registry (`openrouter/~anthropic/claude-opus-latest`,
`~openai/gpt-latest`, and others). The Selection Guide routes unknown or
volatile model choices and always-latest family choices to that section. It was
verified against `opencode models` and official OpenRouter documentation.
