# Orchestrator Architecture

Design document for the interactive orchestration system. For runtime protocol, see `SKILL.md`.

## Core Principle

The orchestrator is a **skill** that transforms any agent into an interactive project manager. It asks questions, delegates to workers, and verifies — without writing code directly.

## System Components

```
~/.config/opencode/
├── skills/orchestrator/
│   ├── SKILL.md              # Runtime protocol (what to do)
│   ├── ARCHITECTURE.md       # This file (why it's designed this way)
│   └── memory.md             # Global orchestrator memory
├── llms.md                   # LLM metadata
├── agents/
│   ├── orchestrator.md       # Primary agent — loads skill on startup
│   ├── build.md              # Default dev agent
│   ├── reviewer.md           # Code reviewer (subagent)
│   └── worker-*.md           # One per LLM (subagents)
└── opencode.json             # Config
```

## Three Levels of Memory

| Level | File | Scope | Updated by |
|-------|------|-------|------------|
| Global | `skills/orchestrator/memory.md` | Cross-session, cross-project | Orchestrator at shutdown |
| Repository | `<project>/docs/` | Project rules, conventions | Developers |
| Plan | `<project>/docs/plans/execution.md` | Per-plan execution status | Orchestrator during execution |

## LLM Selection Strategy

| Factor | Weight | Example |
|--------|--------|---------|
| Task complexity | High | Multi-file refactor → Qwen 397B |
| Required quality | High | Production code → Sonnet or Qwen |
| Speed need | Medium | Quick fix → Mistral Small or DeepSeek Flash |
| Cost sensitivity | Medium | Batching → DeepSeek Free or MiMo |
| Context window | Low | Large files → Qwen 397B (262K, ext 1M) |

## Parallel Execution

OpenCode handles concurrency internally. Multiple `task` calls in one message → parallel. One at a time → sequential.

**Parallelize** when tasks are independent (different files, no dependencies).
**Serialize** when B depends on A's output.

## Error Handling (Circuit Breaker)

- Max 2 attempts per task
- NEVER retry with the same prompt
- After 2 failures, STOP and ask user
- Track failures in `memory.md` to avoid repeating

## Worker Output Contract

All workers MUST return one of these formats:

```
## Done
- Changed: <files>
- What: <1-2 sentence summary>
- Verified: <command + result>
```

```
## Blocked
- Reason: <why>
- What I tried: <steps>
- Suggestion: <what orchestrator should do>
```

The orchestrator parses these headers to determine next steps. Workers that return neither → treated as failure.

## How to Add a New LLM

1. Add entry to `~/.config/opencode/llms.md`
2. Create `~/.config/opencode/agents/worker-<name>.md` following the template in existing workers
3. Restart session to register

Do not create a short alias file (e.g. `sonnet.md`). Legacy aliases are removed. If a short alias exists for the same model, delete it.

## Security Considerations

- Workers have `bash: allow` — they can run arbitrary shell commands. Only delegate to trusted LLMs.
- `external_directory` permission gates structured tool calls (read/edit/glob/list) but does NOT sandbox shell commands. A worker with `bash: allow` can access arbitrary paths via shell argv. Treat `bash: allow` as full trust in the model.
- Legacy alias agents (short names without `worker-*` prefix) have been removed. All delegation targets are now `worker-*` agents with explicit `task: deny` to prevent recursive delegation.
- Orchestrator has `edit: ask` — user approves all edits except trivial post-review fixes.
- Reviewer has `edit: deny` — read-only, reports findings.
