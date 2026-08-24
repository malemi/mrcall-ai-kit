# Brief: Test worker-auto (OpenRouter Auto Router in OpenCode)

**Created**: 2026-07-25

## Outcome (2026-07-25)

The open question is **answered: YES**. OpenCode accepts the OpenRouter Auto
Router as a subagent model and routes to a real model end-to-end.

**Verified facts (checked against `opencode models` registry + official docs,
not model memory):**

1. **Slug in OpenCode is `openrouter/openrouter/auto`**, NOT `auto-beta`.
   - The registry exposes `openrouter/openrouter/auto` (double prefix: OpenCode
     adds its own `openrouter/` provider prefix to OpenRouter's `openrouter/auto`).
   - `openrouter/openrouter/auto-beta` is **NOT** in the OpenCode registry, even
     though the OpenRouter API supports `auto-beta`. So the "auto-beta" naming in
     the original brief title/backlog was aspirational — the working, available
     slug is `openrouter/openrouter/auto`. The `-beta` suffix from an even earlier
     session was fabricated; this is now fully resolved.
2. **Tilde-latest aliases are REAL and already in the OpenCode registry** (10 of
   them): `openrouter/~anthropic/claude-{opus,sonnet,haiku,fable}-latest`,
   `openrouter/~openai/gpt{,-mini}-latest`,
   `openrouter/~google/gemini-{pro,flash}-latest`,
   `openrouter/~moonshotai/kimi-latest`, `openrouter/~x-ai/grok-latest`.
   These auto-resolve to the newest version of each family — the solution to
   "models change weekly" without manual table maintenance.
3. **End-to-end test passed**: delegated a tiny README-reading task to
   `subagent_type="worker-auto"`; it returned 118 lines / `# mrcall-ai-kit` /
   `bash` — all three cross-checked against the file and correct. Model surfaced:
   `openrouter/openrouter/auto`.

**Implemented as a result:** `llms.md` gained an "Auto-updating mechanisms"
section (tilde-latest alias table + elastic `worker-auto` guidance).

## Background — what is already verified (do NOT re-verify)

This brief comes from a session where the question "which LLM for which task,
given that models change weekly on OpenRouter?" was investigated end-to-end.
The following are VERIFIED facts (checked against official OpenRouter docs at
openrouter.ai, not against model memory). Do not redo this work:

1. **Gemini's answer was ~half fabricated.** Real: OpenRouter MCP server
   exists (but it's build-time discovery, NOT runtime routing), sticky
   routing + `session_id`, `models: [...]` fallback array, `response-healing`
   plugin, `openrouter:subagent` server tool. Fabricated/exaggerated: "80% fix
   rate", "latency in milliseconds", tier lists "re indiscusso".
2. **The real solutions** for the two original problems:
   - #1 (which LLM for a task) → Auto Router `openrouter/openrouter/auto`:
     classifies the prompt into ~30 task types, routes to the model with the
     highest community share-of-spend over a trailing 7-day window.
   - #2 (models change weekly) → tilde-latest aliases
     (`~anthropic/claude-haiku-latest` auto-resolves to newest version).
3. **Root cause of the previous session's failure** — VERIFIED via control
   experiment: OpenCode does NOT hot-reload agent files mid-session. A second
   agent `worker-auto-test` with a KNOWN-good model (`opencode/gpt-5.4-nano`,
   identical to working `worker-gpt`) returned the same `Unknown agent type`.
   So the failure was NOT the `openrouter/auto-beta` model ID; it was the
   agent not being in the registry. See `docs/known-issues-and-solutions.md`.

## Sources (already fetched and verified — for reference, do not re-fetch unless needed)

- Auto Router: https://openrouter.ai/docs/guides/routing/routers/auto-router.md
- Model Fallbacks: https://openrouter.ai/docs/guides/routing/model-fallbacks.md
- OpenCode integration: https://openrouter.ai/docs/cookbook/coding-agents/opencode-integration.md
- MCP server (build-time, not runtime): https://openrouter.ai/docs/guides/overview/mcp-server.md
- Subagent server tool (related, future pattern): https://openrouter.ai/docs/guides/features/server-tools/subagent.md
