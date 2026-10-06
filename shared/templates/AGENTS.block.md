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
