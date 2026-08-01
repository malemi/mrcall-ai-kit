# Brief: Test worker-auto (OpenRouter Auto Router in OpenCode)

**Status**: ✅ DONE — experiment succeeded, auto-updating mechanisms implemented (2026-07-25)
**Created**: 2026-07-25
**Supersedes context from**: previous session that ended with `/doc-end`

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
3. **End-to-end test passed**: delegated the tiny README task (below) to
   `subagent_type="worker-auto"`; it returned 118 lines / `# mrcall-ai-kit` /
   `bash` — all three cross-checked against the file and correct. Model surfaced:
   `openrouter/openrouter/auto`.

**Implemented as a result:** `llms.md` gained an "Auto-updating mechanisms"
section (tilde-latest alias table + elastic `worker-auto` guidance). Both
OpenRouter backlog items closed in `harness-backlog.md`.

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
   - #1 (which LLM for a task) → Auto Router `openrouter/auto-beta`: classifies
     the prompt into ~30 task types, routes to the model with the highest
     community share-of-spend over a trailing 7-day window.
   - #2 (models change weekly) → tilde-latest aliases
     (`~anthropic/claude-haiku-latest` auto-resolves to newest version).
3. **Root cause of the previous session's failure** — VERIFIED via control
   experiment: OpenCode does NOT hot-reload agent files mid-session. A second
   agent `worker-auto-test` with a KNOWN-good model (`opencode/gpt-5.4-nano`,
   identical to working `worker-gpt`) returned the same `Unknown agent type`.
   So the failure was NOT the `openrouter/auto-beta` model ID; it was the
   agent not being in the registry. See `docs/known-issues-and-solutions.md`.

## The one open question (ANSWERED — yes, see Outcome above)

**Does OpenCode accept the OpenRouter Auto Router as a subagent's `model:`
field, and if so, does the Auto Router actually route to a real model?**

This was NOT testable in the previous session (agent frozen out of registry).
It is testable now, in a fresh session, because:
- `worker-auto.md` is installed at `~/.config/opencode/agents/worker-auto.md`
  (and in the kit at `opencode/agents/worker-auto.md`).
- OpenRouter is wired: `~/.local/share/opencode/auth.json` has entry
  `openrouter` = `{type: api, key: sk-or-...434d}`.

## Pre-flight checks (run these FIRST, before delegating)

Verify the new session can actually see the agent and the auth:

```bash
# 1. agent file is present in the registry path
ls -la ~/.config/opencode/agents/worker-auto.md

# 2. OpenRouter is wired in auth.json (do NOT print the key value)
python3 -c "import json; d=json.load(open('/home/mal/.local/share/opencode/auth.json')); print('openrouter in auth:', 'openrouter' in d); print('keys present:', list(d.keys()))"

# 3. whether the provider is declared in opencode.json
python3 -c "import json; d=json.load(open('/home/mal/.config/opencode/opencode.json')); print('providers declared:', list(d.get('provider',{}).keys()))"
```

If check #1 fails → the install didn't survive; re-copy from
`opencode/agents/worker-auto.md`.
If check #2 shows no `openrouter` → the user must `/connect` → OpenRouter.
If check #3 does not list `openrouter` → note it; it MAY be needed (see
"Decision branch" below).

## The test (the actual experiment)

Delegate a deliberately tiny real task to `worker-auto`. The task must be
self-contained and verifiable, so we can tell routing success from failure:

```
Read the file /home/mal/hb/mrcall-ai-kit/README.md and report three facts:
1. The total line count.
2. The exact text of the first level-1 heading (line starting with `# `).
3. The language tag of the first fenced code block (the word right after
   the opening triple-backtick).
Reply in the ## Done format. Under "Model used", state the model that served
this request if surfaced anywhere in your runtime; else "not surfaced".
```

Call it with `subagent_type="worker-auto"`.

## Decision branch (interpret the result)

- **SUCCESS — worker returns the 3 facts correctly:**
  - OpenCode accepts `openrouter/auto-beta` as a model ID ✓
  - The Auto Router routed to a real model ✓
  - Record which model was used (if surfaced) in `docs/active-context.md`.
  - Then: this is the green light for backlog item "update llms.md to
    auto-updating mechanisms" (tilde-latest aliases + elastic worker type).

- **FAILURE — `Unknown agent type: worker-auto`:**
  - The restart did NOT load the agent. Re-verify the file is at
    `~/.config/opencode/agents/worker-auto.md` and is valid YAML frontmatter.
  - Do NOT hack around it; fix the registry load.

- **FAILURE — provider/auth error (e.g. "model openrouter/auto-beta not found"
  or 401):**
  - The agent loaded but OpenRouter isn't resolvable as a provider.
  - Declare `openrouter` under `provider` in `opencode.json`. Per the OpenCode
    integration doc, the config shape is:
    ```json
    "provider": {
      "openrouter": {
        "options": { "apiKey": "{env:OPENROUTER_API_KEY}" }
      }
    }
    ```
    — but since the key is already in `auth.json` as `{type: api}`, you may
    NOT need to pass apiKey here. Try without first; add only if it errors.
  - Re-run the test after the config change (another restart may be needed).

- **FAILURE — model ID rejected but agent loads:**
  - Try the deprecated slug `openrouter/auto` as a fallback (the docs mark it
    deprecated but functional). If that works, the beta slug has an issue in
    this OpenCode version; record it and use the working one.

## What NOT to do

- Do NOT re-investigate Gemini's claims — they're debunked (see Background).
- Do NOT create a different/new agent file to "try again" — `worker-auto.md`
  is structurally valid (verified: same pattern as `worker-gpt.md`, valid
  YAML, same permissions). The previous failure was hot-reload, now solved by
  the fresh session.
- Do NOT fabricate results. If routing happened but the model isn't surfaced,
  say "not surfaced" — don't invent a model name.
- Do NOT commit anything unless the user explicitly asks.

## Sources (already fetched and verified — for reference, do not re-fetch unless needed)

- Auto Router: https://openrouter.ai/docs/guides/routing/routers/auto-router.md
- Model Fallbacks: https://openrouter.ai/docs/guides/routing/model-fallbacks.md
- OpenCode integration: https://openrouter.ai/docs/cookbook/coding-agents/opencode-integration.md
- MCP server (build-time, not runtime): https://openrouter.ai/docs/guides/overview/mcp-server.md
- Subagent server tool (related, future pattern): https://openrouter.ai/docs/guides/features/server-tools/subagent.md

## Success criteria for the brief itself

The experiment is done when EITHER:
- (a) `worker-auto` returns a correct answer → Auto Router works in OpenCode,
  record the model used, proceed to backlog; OR
- (b) a specific failure mode is identified and the next concrete fix is
  written into `docs/active-context.md` and this brief's status.

Update `docs/active-context.md` "Next" section with the outcome.
