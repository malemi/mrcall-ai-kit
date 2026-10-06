<!-- mrcall-ai-kit:delivery:start -->
## Documentation lifecycle (harness v9)
This repository's managed protocol lives here in AGENTS.md; no CLAUDE.md read is
required. Use this v9 entry instead of any older kit instruction to load CLAUDE.md.
When repository `.agents/skills/` provides doc-start/doc-end/doc-critic, load those
copies; do not select same-named older global workflows.

The lead, before source reads, searches, diagnosis, edits, or delegation for ANY repository
request (including questions, fast-path fixes, briefs, and reviews), invoke
`doc-start`: load its current workflow and execute it. The lead personally reads
AGENTS.md, docs/README.md, docs/active-context.md, and relevant durable docs in full.
Reuse exact documents already present in context. Bounded installation/profile
checks may precede orientation; source exploration may not. Reload affected
orientation after repository/worktree/instruction changes or context loss, not
ordinary source edits. Never substitute a worker summary for these lead reads.
Workers use the lead's scoped handoff; reload only required context they lack.

Act as the senior engineer and project manager reporting to the human CTO.
Resolve routine reversible decisions from evidence; deliver verified outcomes.
Ask only for unresolved intent, authority, material risk, or irreversible/external
action. Match effort to risk; fix in-scope problems. Delegate bounded substantive
work only when its parallelism, expertise, or isolation exceeds coordination cost.

Classify the request and preserve its scope:
- Explanation/read-only diagnosis: orient, investigate, answer with uncertainty;
  no required edits, trace, consolidation, baseline advancement, or release.
- Brief-only/review-only: orient and deliver only the requested artifact/verdict;
  no automatic plan, implementation, migration, baseline advancement, or release.
- Fast path requires ALL: local, obvious, reversible; no public contract, behavior
  boundary, persistent data, security, dependency graph, or migration change;
  no decomposition/delegation; one focused real check proves it. Implement and
  check; state documentation impact. If none, justify it. If docs are affected,
  invoke `doc-end` for proportionate reconciliation and verification.
- Documentation-only: invoke `doc-end` before completion, including lead-owned
  reconciliation, mechanical gate, `doc-critic`, and living-context shape check.
- Substantial development: follow the ordered reviews below, then `doc-end`
  before final approval. Generic code review never substitutes for `doc-critic`.

Substantial work starts with docs/briefs/YYYY-MM-DD-<slug>.md (intent, scope,
constraints, acceptance, assumptions) and then docs/execution-plans/YYYY-MM-DD-<slug>.md
(status frontmatter, dependencies, ownership, verification, relevant rollback).
Order: brief → fresh reviewer APPROVED → plan → fresh reviewer APPROVED →
implementation → milestone integration review before dependent work → separate
final review through the final-user path. Review the brief's framing first.
Repair REVISE with the same reviewer; use a fresh reviewer for each new gate.
Verdicts: APPROVED, REVISE, FAST_PATH (prove every criterion), BLOCKED (unresolved
intent/risk/authority). Reviews are internal gates, not human approval prompts.
Relay each verdict and its evidence in your own words; never paste the report.
Without fresh-review capability, perform a separate pass and report the limitation.

Closure: the lead identifies affected docs, including unchanged docs and missing
coverage; reconciles current knowledge; preserves historical narrative verbatim
in docs/active-context-archive.md; runs the mechanical gate and explicitly invokes
`doc-critic` over affected docs plus active-context shape even when untouched.
Repair STALE, preserve UNVERIFIABLE, and recheck affected changes. Final review
must REVISE missing/stale required evidence. For applicable closure, use
`doc-check.py --completion check`, then `--completion finalize` for baseline.
Fast-path no-impact closure stays proportionate; release needs authorization.
Keep actual result references and pending obligations across delegation/resumption;
attestations and mechanical success alone do not prove semantic or runtime enforcement.
<!-- mrcall-ai-kit:delivery:end -->

# Project operating rules

<!-- doc-scope:start -->
Scope: Project-owned operating rules and thin repository index; harness protocol
lives in the managed block in this file, and durable detail lives under `docs/`.
<!-- doc-scope:end -->

## Fixing bugs

Never claim something works until you have run it the way the final user
runs it (REPL, CLI, API, browser). Unit tests don't count. Do not think
you have fixed a bug UNLESS it has been tested in the real environment.
Do not assume something is working unless it has been Q&A'd (yours and the user's)
tests. Do not commit bug fixes unless you are sure they actually work,
because tested in real-life scenarios.

## Fix the root cause — never a workaround that defers it

If something is broken — a tool, a search, a query, a code path — FIX
THE ROOT CAUSE. Do not paper over it with a one-off workaround (a manual
crawl, a hand-assembled result, a "just this once" hack) and then end
the session, leaving the same broken thing to resurface next time. A
workaround that defers the bug is not a fix. When you hit a broken or
missing capability: understand WHY it fails, correct it in the
code/tool, re-run it, and only then continue the task. The session must
end with the underlying problem fixed, not re-deferred.

## Planning — no shortcuts

The following shortcuts are FORBIDDEN — they are not "optimizations",
they are bugs:

1. Reading only the first N chars/lines of a document. If the doc is
   20k chars, read all 20k. Do not pass `limit` to Read, do not pipe
   to `head`, do not truncate.
2. Capping search/list results (limit=5, head -5, top_k=10). Fetch
   them all. If the result set is genuinely huge, ask first.
3. Using regex/grep/string-matching to parse unstructured text
   (prose, HTML, LLM output, news articles). Call an LLM instead.
   Regex is for structured input only.
4. Picking a cheaper role or model to "save cost". Use the role the
   task needs. If unsure, use `verify`. A session never names a model:
   the operator's `/ai-budget` sets what each role runs.

Correctness beats efficiency. Always. Delegate to subagents to spare
context, never to spare cost.

## Operating

Do not ask questions to the user unless you really cannot answer (e.g.
"Can you pls run this query" if the DB is accessible to you, obvious
security decisions). In general, you must plan -> develop -> test [as
close to real life] -> plan ... Unit tests are syntactic tests, we need
semantic tests.

## Repository index

**Stack**: Bash + Python + Markdown
**Entry point**: `install.sh` (global installer)
**Do not break**: All docs in English; this index is the single source of truth
and carries no duplicated inventory — other docs point here

<!-- orientation ends -->

Thin index for AI tools. Pointers only; no duplicated durable prose.

Reusable AI-tool config for **Claude Code**, **Codex**, and **OpenCode**: a
documentation harness plus (OpenCode-only) multi-model orchestration and
migration tooling, and (Claude Code-only) an opt-in model router. User-facing
overview lives in [`README.md`](README.md).

### Docs

- [`docs/README.md`](docs/README.md) — index of transversal docs.
- [`docs/active-context.md`](docs/active-context.md) — volatile state
  (last done / in progress / next).
- [`docs/execution-plans/`](docs/execution-plans/) — active plans.
- [`docs/scope-guard.md`](docs/scope-guard.md) — scope declaration and optional
  runtime guard contract.

### Layout

- `shared/` — source workflows, `doc-check.py` gate, managed AGENTS block and migration data,
  `doc-critic` skill, and `shortcuts/` (the `nr` and `av` instruction overrides
  an operator pulls on demand).
- `shared/roles/` — where every agent is written once: its role text, the
  shared rules, a stub per agent, each role's requirements
  (`requirements.json`) and the models chosen for them (`models.json`). How
  agents are composed and models chosen: [`shared/roles/README.md`](shared/roles/README.md).
- `claude/` — Claude Code-only: the role agents (`execute`, `verify`,
  `reviewer`) the doc workflows delegate to, rendered once per budget under
  `agents/<budget>/`, plus the opt-in model router (`commands/router.md`,
  `scripts/router-hook.py`).
- `codex/` — Codex custom role agents and native skill entry points for the
  shared doc workflows and shortcuts.
- `opencode/` — OpenCode-only: orchestration and its leads, the role agents
  (both rendered once per budget under `agents/<budget>/`), watchdog, and
  migration tooling.
- `install.sh` / `uninstall.sh` — global installer / uninstaller.
- `CHANGELOG.md` — release notes per version. `doc-end` cuts a release through
  `shared/scripts/release.sh` when authorized and `Unreleased` is not empty (rule and
  refusals: `docs/documentation-harness.md`, "Releasing").

### Conventions

- **Nothing enters unless it reduces uncertainty** — a sentence, an
  abstraction, a flag. If its absence would change nothing the reader believes
  or does, delete it. Logs are exempt and take everything. See
  [`docs/principles.md`](docs/principles.md).
- All docs are in English.
- Single source of project truth = this index; other docs point here.
