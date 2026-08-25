# Harness Backlog

Deferred doc-harness / orchestration improvements.

## OPEN — orchestrator docs contradict the agent files they describe

**Logged**: 2026-08-24. Three statements in the orchestrator's documentation
disagree with the files they describe. `opencode/agents/worker-glm.md`
advertises "256k context" in its description while `llms.md` gives GLM 5.2 a
1M window, so an orchestrator choosing a worker for a large-context task reads
the wrong number. `opencode/agents/reviewer.md` hardcodes
`model: opencode/claude-sonnet-5`, and no table in `llms.md` covers the
reviewer, so the one model choice the protocol makes on the user's behalf is
the only one left undocumented. `SKILL.md` and `ARCHITECTURE.md` carry the
same procedures twice — the four-step watchdog protocol, the retry policy and
the parallel-versus-sequential rule are near-verbatim in both — which
guarantees they drift apart on the next edit. `SKILL.md` should hold the
runtime instructions and `ARCHITECTURE.md` the design rationale, with no
procedure copied between them.

## OPEN — the orchestrator cannot change its model without being restarted

**Logged**: 2026-08-24. `SKILL.md` Phase 1 asks which model should orchestrate
the session and builds the options from the "Orchestrator Models" table in
`llms.md`. If the user picks anything other than the model already running,
the only instruction is to run `/models` and re-run the skill, which throws
away the session and restarts the protocol at Phase 1. Phase 1 should instead
offer to continue on the current model, or to switch manually and resume at
Phase 2.

## OPEN — every task is verified three times

**Logged**: 2026-08-24. Lint, typecheck and tests each run three times per
task. The worker prompt template in `SKILL.md` Phase 5 tells the worker to run
them. The circuit-breaker step after every worker return tells the
orchestrator to run them again through `bash`. The Phase 6 reviewer prompt
passes the same commands to the reviewer, and `opencode/agents/reviewer.md`
runs them a third time. On a slow suite that triples both the wall clock and
the token spend of every delegation. The worker should run a minimal smoke
test, the orchestrator the critical commands once per batch, and the reviewer
should re-run only when something looks wrong.

## OPEN — parallel delegation has no fan-out cap

**Logged**: 2026-08-24. `SKILL.md` says that multiple `task` calls in one
message run in parallel, and to parallelize whenever the subtasks are
independent. Nothing bounds how many run at once. The watchdog enforces a
timeout and a budget per worker, so a wide fan-out satisfies every guardrail
the system has while still saturating a provider rate limit and multiplying
spend by the number of workers. Concurrency needs a declared maximum the same
way timeouts and budgets have one.

## OPEN — a delegation cannot be resumed, and nobody has checked whether it could be

**Logged**: 2026-08-24. Every delegation is one-shot: the orchestrator calls
`task`, the worker returns, and any follow-up is a fresh call with a fresh
prompt. Nothing under `opencode/` uses a resume primitive — no agent, command
or skill mentions resuming a worker by task id — and whether OpenCode's `task`
tool supports one has never been checked against the tool's own schema. Until
someone checks, a worker that stops one step short costs a full re-run. The
check is cheap and it settles whether this is a gap in the protocol or a limit
of the platform.

## OPEN — the gate never inspects a repository's root-level `AGENTS.md`

**Logged**: 2026-08-24. `index_docs()` in `shared/scripts/doc-check.py` builds
the document set from exactly three sources: `README.md`, the `index_file`
named in `docs/.doc-profile`, and everything matching `docs/**/*.md`. A
root-level `AGENTS.md` matches none of them unless a repository happens to
have named it as its index, so every check that walks that set skips it —
dead links and the oversize advisory both. `AGENTS.md` is the agent
instruction file OpenCode and Codex read, it is prose that links to other
docs like any index does, and it is exactly the kind of file that keeps a
pointer to something deleted months ago. Either `index_docs()` should include
the root agent-instruction files by name, or the profile should gain a field
naming extra top-level docs to cover.

## OPEN — two orchestrator entry points that do not carry the same protocol

**Logged**: 2026-08-24. The kit ships the orchestrator twice. `/orchestrator`
runs the `opencode/agents/orchestrator.md` primary agent, which inlines its
own eight-step protocol. The `orchestrator` skill carries a fuller version of
the same protocol and loads into whichever agent is running. Nothing tells a
user which to use, and the two are not equivalent: the agent omits the
watchdog daemon startup, the post-task gate that `SKILL.md` calls mandatory,
and the precedence rules over `AGENTS.md`. A session started through the
command therefore runs without the enforcement the skill treats as compulsory.
The two also diverge at shutdown: the agent's Step 1 mirrors `SKILL.md`'s
startup and creates `memory.md` when it is absent, but its Step 8 has no
equivalent to `SKILL.md`'s "Shutdown = final flush + update `memory.md`", so a
session driven through the agent creates the file and never updates it.

## Oversized docs — reviewed

One line per document the gate's oversized advisory has named, with the verdict
that settled it. A document listed here is never asked about again.

- `docs/documentation-harness.md` — **split**, 2026-08-25. It had crossed the 400-line
  limit by accumulating a second subject: the opt-in model router, its session memory,
  the rotation hand-off, and the worker-report budget. Those moved to
  `docs/model-router.md`, leaving the harness contract comfortably under the
  limit. The
  split is by subject and not by size — the gate and the `/doc-*` contract apply
  whether or not the router is installed, so a session that wants to know what
  `/doc-start` does should not pay for the delegation machinery.
- `docs/briefs/2026-08-24-harness-context-economics.md` — **keep whole**, 555
  lines. It is a dated brief: the record of one analysis, argued end to end, and
  its verdict is already stated in its own opening. Splitting an argument leaves
  two halves that each read as incomplete, and nothing here is a log.
