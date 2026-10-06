# Documentation Harness Contract

The harness defines repository orientation, request scope, documentation
reconciliation, and reviewed delivery. Instructions, deterministic checks, and
observed runtime behavior are separate forms of evidence.

## Entry and ownership

Harness v9 uses root `AGENTS.md` as its single repository instruction entry.
Exactly one `mrcall-ai-kit:delivery` block contains the canonical managed
protocol. Everything outside that block remains project-owned: operating rules,
inventory, ownership, commands, and links. The default 200-line thin-index limit
counts the complete file, including the managed block.

The kit does not require a live root `CLAUDE.md`. Exact historical v6/v7/v8
templates remain migration data. A customized or foreign `CLAUDE.md` is a
compatibility conflict to preserve and resolve explicitly, never a file to
silently delete. The mechanical gate fails while a root `CLAUDE.md`,
`CLAUDE.local.md`, or `.claude/rules/doc-harness.md` exists in a v9 repository.
Loading `AGENTS.md` depends on the client and configuration; the compatibility
checks apply before migration, and measured conditions are in
[`harness-runtime-support.md`](harness-runtime-support.md).

- `docs/README.md` routes readers without duplicating the root inventory.
- Durable documents describe current, verified behavior and ownership.
- `docs/active-context.md` is the current operational snapshot.
- `docs/briefs/YYYY-MM-DD-<slug>.md` records intent, decisions, and rationale.
- `docs/execution-plans/YYYY-MM-DD-<slug>.md` records execution and status.
- `docs/active-context-archive.md` preserves displaced session narrative.

Codex discovers user skills under `~/.agents/skills` and physical custom-role
profiles under `~/.codex/agents`; deprecated custom prompts are not part of this
design. A repository may vendor its own doc-start, doc-end, and doc-critic under
`.agents/skills/`; the managed block directs agents to load those copies instead
of same-named global workflows. The installer never creates repository-local
copies. Its installed global instruction block routes leads to the repository's
managed AGENTS entry and installed roles. Other content in the global file is
operator-owned. OpenCode-only orchestration and watchdog behavior remain
outside this cross-client documentation contract.

## Request scope and delivery

Before substantive source investigation, the lead invokes `doc-start` and
personally obtains the complete root index, docs index, active context, and
relevant durable documentation. Exact content already present in context is
reused. A worker summary never substitutes for these reads.

| Request | Required result and closure |
|---|---|
| Explanation or read-only diagnosis | Orient, investigate, answer with uncertainty; no required edits, trace, consolidation, baseline change, or release. |
| Brief-only or review-only | Orient and deliver the requested artifact or verdict; no automatic plan, implementation, migration, baseline change, or release. |
| Direct fast path | Establish every fast-path condition, implement, run the focused real check, and state documentation impact. Invoke proportional `doc-end` if docs are affected. |
| Documentation-only | Lead reconciliation, mechanical check, explicit `doc-critic`, living-context shape check, and completion check. No development review chain is required. |
| Substantial development | Reviewed brief, reviewed plan, reviewed milestones, documentation closure, and a separate final review before baseline finalization. |

The fast path requires a local, obvious, reversible change with no public
contract, behavior boundary, persistent data, security, dependency-graph, or
migration change; no decomposition or delegation; and one focused real check
that establishes the result. Every other development request is substantial.

Substantial work follows brief → fresh reviewer APPROVED → plan → fresh
reviewer APPROVED → implementation → milestone review before dependent work →
separate final review through the final-user path. A `REVISE` finding blocks the
next stage until repaired and re-reviewed by that reviewer. `FAST_PATH` requires
proof of every criterion. `BLOCKED` identifies unresolved intent, material risk,
irreversible or external action, or authority. These are internal gates, not
routine requests for human permission. Without fresh-review capability, make a
separate pass and disclose the limitation.

The lead acts as the engineer responsible for deciding and finishing within
scope. Model instructions and reviewer judgments do not make the host intercept
every noncompliant final answer.

## Startup and context cost

`doc-check.py --repo PATH --startup` produces compact deterministic startup
facts; `--json` exposes the same facts. They include version and mechanical
outcome, indexed count, baseline validity, complete content-drift count,
separate staged/unstaged/untracked state, every open plan and open or malformed
issue status, violations, and advisories. Unknown metadata is reported rather
than silently treated as closed.

The helper owns recursive integrity work and status scans. Its compact output
does not mean total filesystem work is constant. The lead consumes the result
without dumping inventories, historical records, or unrelated project bodies
into context. Repository indexes route meta-repository work; a child index is
read when entering that child's code, not as a substitute for parent routing.

Startup loads one applicable workflow copy and avoids rereading exact available
content. Mechanical work stays inline by default. Delegation must justify its
coordination cost; it is not an automatic way to reduce context. Changes to
repository, worktree, applicable instructions, or available context invalidate
the affected orientation; ordinary source edits do not require a complete
restart. A configured smoke/build command runs before code changes, including
when the initial working tree was clean.

Cost reports separate preloaded instructions, newly delivered workflow/docs/tool
results, assistant output, and child usage. Bytes divided by four are only a
token estimate. Cumulative billed tokens and visible text totals are not actual
context occupancy. Moving instructions into AGENTS preload is not eliminated
cost. Runtime measurements and their limitations are in
[`harness-runtime-support.md`](harness-runtime-support.md).

## Delegation boundary

Delegate bounded substantive work when parallelism, specialist capability, or
isolation exceeds prompting, waiting, and review costs. Use `execute` for decided
work, `verify` for consequential truth checks, `plan` for read-only planning,
and `reviewer` for lifecycle gates where those installed roles are available.
Claude exposes `Agent`, OpenCode `task`, and Codex `spawn_agent`.

Workers receive scoped ownership, relevant orientation, and current result
references. They reload only required knowledge they lack. The lead cannot
delegate session-signal gathering or deciding which knowledge remains current:
both require the transcript. Independent semantic verification may be delegated,
but a delegated critic reports living-context defects instead of reconstructing
the lead's session and repairing them.

Claude and OpenCode role models follow the machine's `/ai-budget`; Codex roles
inherit the session model. A missing worker means eligible work runs inline,
not that the obligation disappears. Reports need actual command/result evidence;
a statement of success alone is insufficient.

## Mechanical and semantic checks

The mechanical gate indexes Markdown recursively under `docs/`, the root README,
and the configured AGENTS index. It checks relative links, profile fields,
execution-plan and session-memory status, inventory ownership, inline scopes,
the exact single managed block, obsolete layout conflicts, and baseline format
and ancestry. It rejects active-context `##` headings other than `State now`,
`Unresolved`, and `Next`; fenced content and the archive are handled separately.

Required scope declarations remain in AGENTS, docs/README, and active-context:

```markdown
<!-- doc-scope:start -->
Scope: A non-empty statement of this document's purpose and boundary.
<!-- doc-scope:end -->
```

Delimiters occupy exact standalone lines outside fences. Partial, duplicate,
reversed, malformed, empty, or obsolete `doc-index-scope` blocks fail. Other
indexed files need no scope, but any present declaration must be valid. The
semantic critic also checks whether a declaration matches the document's role.
Optional scope-write interception is a separate feature documented in
[`scope-guard.md`](scope-guard.md).

Advisories report oversized docs, undated work traces, open session memories,
and missing meta-child orientation heads without changing the exit status.
Orientation heads end with `<!-- orientation ends -->`; they are an advisory
on a complete index, not permission to truncate required reads. Size messages
include lines, bytes, and explicitly estimated tokens.

`doc-start` reports size advisories without editing files. During `doc-end`, each
newly named oversized document gets one verdict in the `Oversized docs —
reviewed` ledger in `docs/harness-backlog.md`: `keep whole` with a reason, or
`split` plus an ordinary backlog item. Existing rows are not reconsidered on
every run. Projects are outside automatic cleanup; active-context shape belongs
to reconciliation. A verdict does not authorize a split. Follow the full
deletion-first split rules in the closure workflow: do not relocate redundant
prose into existing or generated documents to evade a size advisory.

A clean mechanical gate proves graph/metadata consistency, not factual truth.
The lead identifies affected documentation from changed behavior, including
unchanged contracts, dependencies, routing, and missing coverage. Explicitly
invoke the current `doc-critic` skill over that scope, always including
active-context shape even when untouched. Generic code review is not a critic
result. The affected-document list bounds documentation reads; an additional
document needs a concrete dependency on changed behavior. Unrelated project
and session histories are not ambient audit input. Repair STALE claims and repeat affected checks; retain UNVERIFIABLE
claims honestly. Repository artifacts remain English.

## Profile and version handshake

`docs/.doc-profile` contains `key = value` records:

| Key | Meaning |
|---|---|
| `harness_version` | Required exact protocol version, now 9. |
| `schema_version` | `1` for new profiles; legacy absence follows checker compatibility rules. |
| `mode` | `leaf` or `meta`. |
| `index_file` | Root `AGENTS.md`; includes both managed and project-owned content. |
| `inventory_ignore` | Optional comma-separated top-level directory names excluded from meta inventory. |
| `build`, `smoke` | Optional known real commands; commented examples are not configuration. |
| `release` | Optional command accepting one `vX.Y.Z`; configures release mechanics and changelog format, not task authorization. |
| `index_max_lines` | Optional nonnegative thin-index limit; `0` disables it. |
| `doc_max_lines` | Optional nonnegative advisory limit, default `400`; `0` disables it. |

The v9 profile has no `harness_file`. Unknown keys and invalid values fail.
Commands require a matching version before ordinary work. v6, v7, and v8
profiles migrate explicitly through `doc-create`; a profile without
`harness_version`, v1–v5 profiles, and ambiguous layouts are unsupported and the
helper refuses them. A repository with no profile is a fresh bootstrap. A newer repository
requires upgrading the kit installation. Neither startup nor closure performs
an implicit migration or downgrade. Codex wrappers use their installed shared
WORKFLOW version.

Migration uses the deterministic `doc-migrate.py` helper, with inspection,
dry-run, apply, and exact rollback. It validates compatibility evidence,
ownership, scopes, symlinks, collisions, markers, and recognized historical
bytes before mutation. It preserves project bytes and optional profile
settings, validates staged v9 content, removes only a recognized managed
CLAUDE, and publishes the profile version last. Saved transactions permit
recovery; rollback refuses unrelated subsequent edits. Customized or ambiguous
legacy layouts stop untouched instead of guessing a merge. Installing the kit
does not migrate repositories or change client instruction-loading settings.

## Reconciliation, evidence, and baseline

`doc-end` gathers committed changes since the valid baseline plus staged,
unstaged, and relevant untracked changes. The lead also gathers session-only
decisions, corrections, and rejected approaches, then reconciles living docs.
Configured session memory is read only when this session's exact file is known;
do not glob unrelated sessions to reconstruct a history.

Order is lead reconciliation → mechanical and affected-document semantic
checks → explicit completion check and applicable final review → baseline
finalization → separately authorized release. A documentation-only change still
needs explicit completion even without a development reviewer. Missing or stale
required evidence blocks closure. Changed code, docs, instructions, or reviewed
artifacts require the affected results to be refreshed; a receipt cannot restore
knowledge lost from the lead's context.

`doc_baseline_commit` must be a real ancestor of HEAD. It means the last reviewed
repository commit, never the hypothetical commit containing current dirty work.
Documentation/index-only commits do not create content drift; dirty changes are
reported separately. Advance the baseline only after mechanical success, zero
STALE findings, valid living-context shape, and all applicable reviews. Narrow
baseline/status finalization is distinct from changing reviewed prose.

The completion checker is a refusing CLI gate when invoked. It is not a
host-level guarantee that a model cannot bypass the entire lifecycle or invent
an attestation. Preserve actual result references, pending obligations, and
unverifiable findings across delegation and resumption.

## Work traces and living context

Substantial or multi-session work has a dated brief and plan before execution.
Briefs record intent and rationale without lifecycle frontmatter. Plans use
`status: planned | active | blocked | completed | superseded`. Only `completed`
means finished; checkboxes are reading aids, not authoritative state. A small
single-session fix can omit the pair with an explicit work-trace decision.
Consolidation creates a missing required trace from the lead's transcript;
delegated critics report absence instead of inventing content.

Active context contains verified operational facts, unresolved work, and next
actions under only `State now`, `Unresolved`, and `Next`; target about 120 lines.
It is not a changelog. Route durable facts to durable docs. Preserve displaced
session narrative verbatim in dated sections at the top of the archive, with
an honest unknown date when necessary. Do not silently delete history.

The archive remains indexed for links but is exempt from the oversized-doc
advisory and startup reading. The mechanical gate checks headings; the semantic
critic checks narrative and excess length. Shape alone can require closure even
on a clean tree. A delegated shape failure blocks baseline advancement and
returns reconciliation to the lead.

## Releasing

Versions are `MAJOR.MINOR.PATCH`; major equals `HARNESS_VERSION`. Protocol
changes require a major version and explicit repository migration; other
capabilities use minor and fixes use patch. Reinstall after updating the kit:
copy installs require refresh, while symlinks can expose changed source files
immediately but do not install new assets.

The kit checkout ties the enforced protocol to the release tags:
`HARNESS_VERSION` equals the major of the newest release tag. A protocol bump
is an authorized release act — developed in a linked worktree or separate
clone, never by checking a protocol branch out in the installed checkout,
whose working tree the symlinks expose to every session on the machine. The
gate enforces the tie mechanically in the kit repository: on `main` — and in
the checkout the installed `doc-check.py` resolves into, on every branch and
detached HEAD — a constant different from the newest tag's major is a
blocking violation, except that an ahead constant with a `## vN.x.y` heading
in `CHANGELOG.md` (a release in flight, or retained pending an authorized
retry) downgrades to a named advisory; when no release tag is visible at all
(a fresh or shallow clone), the finding is likewise an advisory, not a
violation. Recorded limits: a raw push from
another clone is caught only when this checkout pulls it; a retained version
section whose release run died stays an advisory until an authorized retry
completes it; the gate reads local tags only and never fetches.

`CHANGELOG.md` contains `Unreleased` and dated version sections. Release requires
authorization in the current task as well as a configured command. When
authorized, `doc-end` Phase 5 owns version selection, changelog/commit ordering,
baseline update, push, and invocation; unrelated tracked work is not included.
The profile setting alone never authorizes publication or commits.

`shared/scripts/release.sh` runs from the checkout, never the installed command
directory. It checks semver, matching protocol major, tag absence, nonempty
changelog section, clean tracked tree, `main` at `origin/main`, the mechanical
gate, all shell tests, and Python suites before tagging, pushing, and publishing.
`--dry-run` runs checks and prints publication commands. Its fixture tests use
a bare remote and a `gh` stub; those tests are not a production release.
