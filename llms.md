# Available LLMs

Metadata for all LLMs available to the orchestrator. Used for informed task delegation.

The static tables below age: model slugs get superseded and per-task best
picks drift week to week. Two OpenRouter mechanisms (verified available in the
OpenCode registry, 2026-07-25) let you stop hand-maintaining that — see
[Auto-updating mechanisms](#auto-updating-mechanisms).

## Orchestrator Models (primary agents)

| Model | ID | Cost (in/out per 1M) | Context | Best for |
|-------|----|-----------------------|---------|----------|
| Claude Opus 4.8 | `opencode/claude-opus-4-8` | $5.00 / $25.00 | 1M | Complex reasoning, orchestrator default |
| Claude Fable 5 | `opencode/claude-fable-5` | $10.00 / $50.00 | 1M | Premium reasoning, adaptive thinking |
| GPT-5.6 Sol | `opencode/gpt-5.6-sol` | ? / ? | 1M | Flagship OpenAI, frontier capability |
| Big Pickle | `opencode/big-pickle` | ? / ? | ? | Custom model — default orchestrator |

## Scaleway Workers (paid, European sovereign cloud)

| Worker | Model | Cost (EUR in/out per 1M) | Context | Params (active) | Best for |
|--------|-------|--------------------------|---------|-----------------|----------|
| worker-glm | GLM 5.2 | 1.80 / 5.50 | 1M | 744B (~40B) | Long-horizon coding, codebase ingestion, debugging |
| worker-qwen | Qwen3.5 397B | 0.60 / 3.60 | 262K (ext 1M) | 397B (17B) | Multilingual, multimodal, RAG, complex reasoning |
| worker-qwen-coder | Qwen3 235B | 0.75 / 2.25 | 260K | 235B (22B) | Agentic coding, real-time workflows, instruction following |
| worker-mistral | Mistral Medium 3.5 | 1.50 / 7.50 | 256K | 128B (dense) | Agentic coding, multimodal, reasoning |
| worker-mistral-fast | Mistral Small 3.2 | 0.15 / 0.35 | 128K | 24B (dense) | Budget coding, lightweight tasks, vision |
| worker-llama | Llama 3.3 70B | 0.90 / 0.90 | 128K | 70B (dense) | General-purpose, text-only, reliable baseline |

## Zen Workers (OpenCode hosted)

### Free tier (data may be used for model improvement)

| Worker | Model | Cost | Context | Params (active) | Best for |
|--------|-------|------|---------|-----------------|----------|
| worker-deepseek-free | DeepSeek V4 Flash Free | Free | 200K | 284B (13B) | Experimentation, lightweight tasks |
| worker-mimo | MiMo v2.5 | Free | 200K | 310B (15B) | Multimodal (text+vision+audio+video), free reasoning |
| worker-nemotron | Nemotron 3 Ultra | Free | 1M | 550B (55B) | Long-running agentic workflows, high throughput, complex reasoning |

### Paid tier

| Worker | Model | Cost (in/out per 1M) | Context | Params (active) | Best for |
|--------|-------|----------------------|---------|-----------------|----------|
| worker-deepseek | DeepSeek V4 Pro | $1.74 / $3.48 | 1M | 1.6T (49B) | Complex coding, long-context reasoning, flagship open model |
| worker-deepseek-flash | DeepSeek V4 Flash | $0.14 / $0.28 | 1M | 284B (13B) | High-volume coding, everyday agentic tasks, best value |
| worker-gemini | Gemini 3.5 Flash | $1.50 / $9.00 | 1M | Proprietary | Multimodal (text+image+video+audio+PDF), document analysis |
| worker-gpt | GPT 5.4 Nano | $0.20 / $1.25 | 400K | Proprietary | Classification, extraction, high-throughput pipelines |
| worker-kimi | Kimi K2.7 Code | $0.95 / $4.00 | 256K | ~1.1T (32B) | Coding specialist, MCP tool workflows, refactoring |
| worker-sonnet | Claude Sonnet 5 | $2.00 / $10.00 | 1M | Proprietary | Production coding, balanced intelligence + cost |

## Auto-updating mechanisms

Two OpenRouter features remove manual maintenance from model selection. Both
are verified present in the OpenCode registry (`opencode models`, 2026-07-25)
and usable as an agent's `model:` field.

### 1. Elastic worker — Auto Router (which model per task)

`worker-auto` (`opencode/agents/worker-auto.md`) uses
`openrouter/openrouter/auto`. OpenRouter classifies each prompt into ~30 task
types and routes to the model with the highest community share-of-spend over a
trailing 7-day window, then follows the crowd as workloads migrate — no
retraining, no manual curation. Verified end-to-end via subagent delegation
(see `docs/briefs/2026-08-01-test-worker-auto.md`).

- **Use it when** the right worker for a task is unknown or volatile, or you
  don't want to pin a specific model.
- **Slug**: `openrouter/openrouter/auto` (the double prefix is OpenCode adding
  its own `openrouter/` provider prefix to OpenRouter's `openrouter/auto` model
  id — this is correct, not a typo). `openrouter/openrouter/auto-beta` is **not**
  in the OpenCode registry, so `auto` is the slug to use here.
- **Model actually used** is surfaced in the response `model` field.

### 2. Tilde-latest aliases (models change weekly)

Instead of pinning a versioned slug (e.g. `anthropic/claude-opus-4.8`) that
goes stale, target a family alias that auto-resolves to the newest version.
Available in the OpenCode registry:

| Alias | Resolves to newest |
|-------|--------------------|
| `openrouter/~anthropic/claude-opus-latest` | Claude Opus family |
| `openrouter/~anthropic/claude-sonnet-latest` | Claude Sonnet family |
| `openrouter/~anthropic/claude-haiku-latest` | Claude Haiku family |
| `openrouter/~anthropic/claude-fable-latest` | Claude Fable family |
| `openrouter/~openai/gpt-latest` | GPT flagship family |
| `openrouter/~openai/gpt-mini-latest` | GPT mini family |
| `openrouter/~google/gemini-pro-latest` | Gemini Pro family |
| `openrouter/~google/gemini-flash-latest` | Gemini Flash family |
| `openrouter/~moonshotai/kimi-latest` | Kimi family |
| `openrouter/~x-ai/grok-latest` | Grok family |

- **Use it when** you want a specific family (its strengths, its price band) but
  always the current version, without editing agent files on each release.
- **Trade-off**: versionless slugs mean the underlying model can change under
  you; pin an exact version when you need reproducibility.

## Selection Guide

### By task complexity
| Complexity | Recommended | Why |
|------------|-------------|-----|
| Trivial (formatting, typo) | worker-mistral-fast | Cheapest, fastest |
| Simple (boilerplate, docs) | worker-llama or worker-mistral-fast | Reliable, cheap |
| Medium (single-file changes) | worker-qwen-coder or worker-deepseek-flash | Good coding, affordable |
| Complex (multi-file refactor) | worker-qwen or worker-glm | Large context, strong reasoning |
| Frontier (architecture, critical) | worker-deepseek or worker-sonnet | Top-tier intelligence |

### By priority
| Priority | Recommended | Why |
|----------|-------------|-----|
| Prototype/experiment | worker-deepseek-free | Free, good enough |
| Production | worker-sonnet or worker-qwen | Proven, reliable |
| Cost-sensitive batch | worker-deepseek-flash | Best value at $0.14/$0.28 |

### By capability
| Need | Recommended | Why |
|------|-------------|-----|
| Multimodal (images, video) | worker-gemini or worker-mimo | Native multimodal |
| Large context (>256K) | worker-glm, worker-deepseek, worker-nemotron | 1M context |
| Multilingual | worker-qwen | 201 languages |
| Tool calling / MCP | worker-kimi or worker-sonnet | Best tool profiles |
| Right model unknown / volatile | worker-auto | Auto Router picks per task — see [Auto-updating mechanisms](#auto-updating-mechanisms) |
| Always-newest of a family | tilde-latest alias | Auto-resolves to current version — see [Auto-updating mechanisms](#auto-updating-mechanisms) |
