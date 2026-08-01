# Harness Backlog

Deferred doc-harness / orchestration improvements.

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
