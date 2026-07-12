# Available LLMs

Metadata for all LLMs available to the orchestrator. Used for informed task delegation.

## Orchestrator Models (primary agents)

| Model | ID | Cost (in/out per 1M) | Context | Best for |
|-------|----|-----------------------|---------|----------|
| Claude Opus 4.8 | `opencode/claude-opus-4-8` | $5.00 / $25.00 | 1M | Complex reasoning, orchestrator default |
| Claude Fable 5 | `opencode/claude-fable-5` | $10.00 / $50.00 | 1M | Premium reasoning, adaptive thinking |
| GPT-5.6 Sol | `opencode/gpt-5.6-sol` | ? / ? | 1M | Flagship OpenAI, frontier capability |
| Big Pickle | `opencode/big-pickle` | ? / ? | ? | Custom model, if available |

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
