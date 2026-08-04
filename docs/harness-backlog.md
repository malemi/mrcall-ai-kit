# Harness Backlog

Deferred doc-harness / orchestration improvements.

## DONE — Archive pruned active-context.md content instead of discarding it (harness v2)

**Status**: DONE (2026-08-04, commit `838eb78`). `doc-end` Phase 3 already said
"reconsolidate, don't append", but nothing mechanical enforced it — a real
downstream repo's `active-context.md` grew from ~120 to ~1500 lines over two
months of sessions that each said "consolidate" in their own commit message.

**Outcome**: pruned session narrative now moves to
`docs/active-context-archive.md` (dated, newest first, verbatim) instead of
being deleted. `doc-end` archives it proactively every session; `doc-critic`
gained an independent living-context shape check that repairs the file
directly (not just flags it) when it drifts. `harness_version` bumped 1→2
(protocol change, per this repo's own compatibility-handshake design);
`doc-create` gained an explicit v1→v2 migration note. Verified: 18 doc-check
tests + the Codex install layout test pass, and the shape-repair behavior was
exercised for real against a scratch fixture — confirmed byte-for-byte zero
information loss versus the pre-repair git blob, correct STALE detection on
the post-repair remainder.

**Follow-up (open, see `docs/active-context.md` Next)**: the v1→v2 migration
note in `doc-create.md` has not itself been exercised against a real v1 repo
yet — only `doc-critic`'s repair was tested directly.

## DONE — Wire OpenRouter into OpenCode for Auto Router

**Status**: DONE (2026-07-25). Authentication and the Auto Router were verified
end-to-end by delegating to `subagent_type="worker-auto"`. No extra provider
declaration in `opencode.json` was required; the key in `auth.json` was enough.

**Outcome**: the working OpenCode slug is `openrouter/openrouter/auto`, not
`auto-beta`, which is absent from the registry. Full detail is in
`docs/briefs/test-worker-auto.md` and `docs/active-context.md`.

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
