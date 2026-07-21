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
2. Read `<project>/docs/plans/execution.md` (skip if doesn't exist)
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
  question: "Quale modello usiamo come orchestratore?\n\nModello corrente: <current>\n\nSeleziona il modello per questa sessione:",
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
  question: "Ecco la strategia che propongo:\n\n## Obiettivo\n<what>\n\n## Approccio\n<high-level>\n\n## File coinvolti\n<list>\n\n## Rischi\n<issues>\n\n## Risultato atteso\n<outcome>",
  header: "Strategy",
  options: [
    {label: "Approvo", description: "Procedi con i sotto-task"},
    {label: "Modifiche", description: "Voglio modificare qualcosa"},
    {label: "Riproponi", description: "Non sono convinto, riproponi"}
  ]
}]
```

**DO NOT PROCEED WITHOUT USER APPROVAL.**

## Phase 4: Task Decomposition — YOU MUST ASK

Break work into discrete subtasks. Present via `question`:

```
question: [{
  question: "Ecco i sotto-task:\n\n## Task 1: <name>\n- **Descrizione**: <what>\n- **Worker**: <LLM>\n- **File**: <files>\n- **Owns**: <paths>\n- **Test**: <verification>\n\n## Task 2: ...\n\n## ORDINE DI ESECUZIONE\n<parallel/sequential>\n\n## COSTO STIMATO\n<$/$$>",
  header: "Tasks",
  options: [
    {label: "Approvo tutto", description: "Esegui"},
    {label: "Modifica", description: "Cambia qualcosa"},
    {label: "Aggiungi/rimuovi task", description: "Cambia il piano"}
  ]
}]
```

Use `~/.config/opencode/llms.md` Selection Guide to pick the right LLM per task.

**DO NOT EXECUTE WITHOUT USER APPROVAL.**

## Phase 5: Execution

Only after Phase 4 approval, delegate to workers.

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
  question: "Verifica completata:\n\n## Completati\n<done>\n\n## Con problemi\n<issues>\n\n## Falliti\n<failed>",
  header: "Results",
  options: [
    {label: "Tutto OK", description: "Chiudi il piano"},
    {label: "Correggi", description: "Fix i problemi"},
    {label: "Review completa", description: "Voglio vedere la review di Task N"}
  ]
}]
```

## Plan Persistence

### Schema for `execution.md`

```markdown
# Execution Plan
## Status: <in_progress | completed | failed>
## Updated: <timestamp>

### Tasks
| # | Name | Worker | Status | Files | Verified |
|---|------|--------|--------|-------|----------|
| 1 | ... | worker-x | done | path | ✅ |
| 2 | ... | worker-y | blocked | path | ❌ reason |
```

### Persistence rules
- Write after each phase transition
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
