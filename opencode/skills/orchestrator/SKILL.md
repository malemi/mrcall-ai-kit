---
name: orchestrator
description: Interactive orchestration protocol — plan, delegate to LLM workers, verify. Use when you want to coordinate multi-step tasks with user approval at each stage.
---

# Orchestrator Protocol — MANDATORY INTERACTIVE MODE

**STOP. READ THIS FIRST.**

This skill requires **interactive back-and-forth** with the user via the `question` tool. You MUST ask questions at every phase. You MUST NOT skip phases. You MUST NOT jump straight to execution. If you skip questions, this skill is broken.

**Rule #1: Use `question` tool at EVERY phase transition. No exceptions.**
**Rule #2: Never execute without user approval.**
**Rule #3: Never skip a phase.**

## Precedence

When this skill is active, it **OVERRIDES** these AGENTS.md rules:
- **"Don't ask the user unless needed"** → Interactive approval IS the product. ALWAYS use `question` for decisions.
- **"No cheap model for cost"** → Cost-aware worker selection is allowed within quality bounds (see Phase 4).

AGENTS.md still wins on: root-cause fixes, real-env tests, no commit without ask, no shortcuts in planning.

## Startup Sequence

When activated, **STOP and execute this sequence BEFORE doing anything else**:

1. Read `~/.config/opencode/skills/orchestrator/memory.md`
2. List `<project>/docs/execution-plans/*.md` and read the files whose YAML frontmatter `status` is `planned`, `active`, or `blocked` (skip if the directory doesn't exist). These are the open work traces: resuming one of them means updating its existing brief+plan pair, never creating a duplicate.
3. Read `~/.config/opencode/llms.md`
4. **Start watchdog daemon** (if not already running):
   ```bash
   python3 ~/.config/opencode/skills/orchestrator/scripts/watchdog-cli status 2>/dev/null || \
   nohup python3 ~/.config/opencode/skills/orchestrator/scripts/watchdog.py \
     --log-dir ~/.opencode/watchdog \
     --parent-session-id <current_session_id> \
     > /tmp/watchdog_daemon.log 2>&1 &
   ```

Then **immediately proceed to Phase 1**. Do NOT analyze the user's request yet. Do NOT explore the codebase yet. Do NOT plan anything yet. The FIRST thing you do after startup is ask the model selection question.

## Phase 1: Model Selection — YOU MUST ASK

Read `~/.config/opencode/llms.md` → "Orchestrator Models" table. Generate options dynamically from that table.

**YOU MUST use the `question` tool NOW.** Example:

```
question: [{
  question: "Which model should orchestrate this session?\n\nCurrent model: <current>\n\nSelect the model for this session:",
  header: "Model Selection",
  options: [
    {label: "<Model from table>", description: "<Cost + Best for>"},
    ...more models from table...
  ]
}]
```

- If current model is in the table → present it as first option with "(current)" suffix
- If user picks current model → proceed to Phase 2
- If user picks different model → tell them to use `/models` to switch, then re-run skill

**DO NOT SKIP THIS PHASE. DO NOT PROCEED WITHOUT ASKING.**

## Phase 2: Task Understanding — YOU MUST ASK

Now engage in back-and-forth via `question` to understand:
- What exactly needs to be done
- Constraints and requirements
- Expected outcome

Explore the codebase using `read`, `glob`, `grep` to understand architecture.

**YOU MUST use `question` to confirm understanding before proceeding.**

## Phase 3: Strategy Proposal — YOU MUST ASK

Present a clear strategy via `question`:

```
question: [{
  question: "Here is the strategy I propose:\n\n## Goal\n<what>\n\n## Approach\n<high-level>\n\n## Files involved\n<list>\n\n## Risks\n<issues>\n\n## Expected outcome\n<outcome>",
  header: "Strategy",
  options: [
    {label: "Approve", description: "Proceed to task breakdown"},
    {label: "Changes", description: "I want to change something"},
    {label: "Re-propose", description: "Not convinced, propose again"}
  ]
}]
```

**DO NOT PROCEED WITHOUT USER APPROVAL.**

**On approval, write the work trace** (skip for read-only tasks): derive `<slug>` from the goal and the date from `date +%Y%m%d`, then write `docs/briefs/YYYYMMDD-<slug>.md` — the approved strategy verbatim: goal, approach, risks, expected outcome — and `docs/execution-plans/YYYYMMDD-<slug>.md` with YAML frontmatter `status: planned` (schema in Plan Persistence below). If the startup scan found an open plan for this same workstream, update that pair instead of creating a new one.

## Phase 4: Task Decomposition — YOU MUST ASK

Break work into discrete subtasks. Present via `question`:

```
question: [{
  question: "Here are the subtasks:\n\n## Task 1: <name>\n- **Description**: <what>\n- **Worker**: <LLM>\n- **Files**: <files>\n- **Owns**: <paths>\n- **Test**: <verification>\n\n## Task 2: ...\n\n## EXECUTION ORDER\n<parallel/sequential>\n\n## ESTIMATED COST\n<$/$$>",
  header: "Tasks",
  options: [
    {label: "Approve all", description: "Execute"},
    {label: "Modify", description: "Change something"},
    {label: "Add/remove tasks", description: "Change the plan"}
  ]
}]
```

Use `~/.config/opencode/llms.md` Selection Guide to pick the right LLM per task.

**DO NOT EXECUTE WITHOUT USER APPROVAL.** On approval, record the approved task table in the plan file.

## Phase 5: Execution

Only after Phase 4 approval. Set the plan's frontmatter to `status: active`, then delegate to workers.

  ### Worker Prompt Template

  ```
  ## Context
  Project: <project>
  Module: <module path>
  Files: <list>
  <1-2 paragraphs: what files do, how they fit>

  ## Task
  <Precise change description>

  ## Conventions
  - <naming from existing code>
  - <error handling pattern>
  - See @<reference-file> for pattern

  ## Verification
  After implementing, run:
  - <lint>
  - <typecheck>
  - <test>

  Report: files changed, what you did, verification results.
  
  **Workers must end with `## Done` or `## Blocked` exactly; unbounded `python -c` without timeout is forbidden.**
  ```

### Parallel vs Sequential

Multiple `task` calls in one message → parallel. One at a time → sequential.
Parallelize when independent. Serialize when B depends on A.

  ### Circuit Breaker

  #### Tool-level failures

  The watchdog daemon monitors all workers. If a worker exceeds its timeout or budget, the watchdog kills it automatically. After each `task()` return, check `watchdog-cli check` — if kills were logged, the worker was terminated by the watchdog. Retry with a different worker model.

  **MANDATORY watchdog protocol for every `task()` delegation:**

  1. **BEFORE `task()`**: Register the task with the watchdog
     ```bash
     python3 ~/.config/opencode/skills/orchestrator/scripts/watchdog-cli register <task_id> <timeout_s> <budget_usd>
     ```

  2. **Call `task()`** with timeout:
     ```
     task(description=..., subagent_type=..., timeout=timeout_s*1000)
     ```

  3. **AFTER `task()` returns**: Check if watchdog killed the worker
     ```bash
     python3 ~/.config/opencode/skills/orchestrator/scripts/watchdog-cli check
     ```
     - If kills logged for this task_id → worker was killed by watchdog → RETRY with different worker model (NEVER same model)
     - If no kills → worker completed normally → proceed with output

  4. **ON COMPLETION**: Deregister the task
     ```bash
     python3 ~/.config/opencode/skills/orchestrator/scripts/watchdog-cli deregister <task_id>
     ```

  **Task ID convention:** `<letter>` (e.g., `task_A`, `task_B`, `task_C`) — matches the delegation letter.

  **Timeout/budget defaults:**
  - Simple tasks (docs, formatting): timeout=120s, budget=$2.0
  - Medium tasks (implementation): timeout=300s, budget=$5.0
  - Complex tasks (architecture, debugging): timeout=600s, budget=$10.0

  #### Retry policy

  - **Attempt 1**: Retry with a DIFFERENT worker model. NEVER retry with the same model and same prompt.
  - **Attempt 2**: STOP and report to user via `question`. Never leave a worker hanging.

  After each worker returns:
  1. Check output for `## Done` or `## Blocked`
  2. Verify via `bash` (lint/test)
  3. Success → proceed
  4. Failure → apply retry policy above

  #### Post-task gate (mechanical)

  After EVERY `task()` return the orchestrator MUST:
  1. Write the full worker return text to `/tmp/opencode/last_worker_out.txt` (create dir if needed)
  2. Run:
     ```bash
     python3 ~/.config/opencode/skills/orchestrator/scripts/post_task_gate.py \
       --input /tmp/opencode/last_worker_out.txt \
       [--expect-files path1,path2] \
       [--run 'verify command']
     ```
  3. If exit code ≠ 0 → treat as tool-level failure (circuit breaker). **Do NOT start the next task.**
  4. Never claim worker success without exit 0 from this script.

  Note: hung worker = watchdog killed it, then gate not needed; failed return = always run gate.

## Phase 6: Verification — YOU MUST ASK

After workers complete, delegate review to the **reviewer agent**:

```
task({
  description: "Review: <task name>",
  subagent_type: "reviewer",
  prompt: "Review worker output. Check: correctness, root-cause, conventions, edge cases.\n\n## Original task\n<from Phase 4>\n\n## Worker output\n<## Done>\n\n## Files changed\n<list>\n\n## Verification\n- <lint>\n- <typecheck>\n- <test>"
})
```

### Non-code tasks

```
task({
  description: "Review: <task name>",
  subagent_type: "reviewer",
  prompt: "Review non-code output.\n\n## Original task\n<from Phase 4>\n\n## Worker output\n<## Done>\n\n## Files changed\n<list>\n\nCheck: factual accuracy, completeness, coherence, no fabricated claims."
})
```

**Based on reviewer output:**
- **✅ PASS** → proceed
- **⚠️ ISSUES** → fix if trivial (1 line) via `edit: ask`, else re-delegate
- **❌ FAIL** → apply circuit breaker

**YOU MUST report results to user via `question`:**
```
question: [{
  question: "Verification complete:\n\n## Completed\n<done>\n\n## With issues\n<issues>\n\n## Failed\n<failed>",
  header: "Results",
  options: [
    {label: "All good", description: "Close the plan"},
    {label: "Fix", description: "Fix the issues"},
    {label: "Full review", description: "Show me the full review of Task N"}
  ]
}]
```

Closing the plan means setting its frontmatter to `status: completed` (all tasks done and verified) or `status: blocked` with the reason recorded in the body (stopping on failures). A plan abandoned or replaced by a different approach becomes `status: superseded`, never deleted.

## Plan Persistence

The plan file is the doc-harness work trace: `docs/execution-plans/YYYYMMDD-<slug>.md`, paired with `docs/briefs/YYYYMMDD-<slug>.md` written at Phase 3 approval. Lifecycle lives ONLY in the YAML frontmatter `status` — one of `planned | active | blocked | completed | superseded` — never in a heading, emoji, or prose.

### Plan file schema

```markdown
---
status: planned
---
# <Workstream title>

Brief: [../briefs/YYYYMMDD-<slug>.md](../briefs/YYYYMMDD-<slug>.md)

### Tasks
| # | Name | Worker | Status | Files | Verified |
|---|------|--------|--------|-------|----------|
| 1 | ... | worker-x | done | path | ✅ |
| 2 | ... | worker-y | blocked | path | ❌ reason |
```

The task table is a reading aid; the frontmatter is the authority.

### Persistence rules
- `status: planned` at Phase 3 approval → `active` when Phase 5 starts → `completed` / `blocked` / `superseded` at close (Phase 6)
- Update the task table after **every** task completion, not only at phase transitions
- Shutdown = final flush + update memory.md
- **Read-only tasks**: skip all writes

## Edit Policy

- **Default**: NEVER write code directly — always delegate via `task`
- **Trivial exception**: 1-line fix via `edit: ask`
- **Everything else**: delegate to a worker

## Rules

- **ALWAYS use `question` tool** — this is not optional
- **ALWAYS propose before executing**
- Read `~/.config/opencode/llms.md` before selecting workers
- Fix root causes, never workarounds
- Test in real environment, not just unit tests
- Never commit unless explicitly asked
