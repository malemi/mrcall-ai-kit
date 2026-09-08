# Documentation Harness Contract

This document defines what the harness guarantees. Command prose and checker
behavior must agree with it.

## Environments

The same documentation model serves Claude Code, Codex, and OpenCode. Tool
integration may differ: Codex discovers user-level skills under
`$HOME/.agents/skills`; deprecated custom prompts under `~/.codex/prompts`
are not part of the design. OpenCode-only orchestration remains outside this
cross-tool contract.

## Delegation boundary

Both session start and consolidation may delegate bounded, substantive work to
pinned-model workers where the environment provides them — `worker-sonnet` for
mechanical execution, `worker-opus` for independent verification — through
whatever subagent primitive the tool exposes (`Agent` in Claude Code, `task` in
OpenCode). Delegation is conditional: parallelism, specialist capability, or
context isolation must be worth more than prompting, waiting, and review.
Narrow local work stays with the primary agent. Workers declare their own
model, so the tier follows the task rather than the delegating session; a
subagent that declares none inherits the parent's and therefore saves context
only.

Two OpenCode capabilities are deliberately not ported to Claude Code: the
watchdog daemon, which enforces timeout and budget through OpenCode's own
session-abort API and has no Claude Code equivalent; and the multi-provider
worker roster, since `model:` selects among models the session can already
reach and provider routing is process-level, leaving Sonnet as the one useful
cheaper tier.

Two parts of consolidation are never delegable, in any environment: gathering
the session signal, and deciding which knowledge is current. Both depend on the
session transcript — decisions taken, approaches rejected, corrections
received — which no subagent can observe and none may reconstruct by
inference. At session start the same line falls elsewhere: the mechanical
checks are delegable, but reading the index, the docs index, and the volatile
snapshot is not, because loading those into the session is the purpose of the
command and a worker's summary of them defeats it.

Where no worker exists, the delegable work is done inline; a step is never
skipped for want of a worker. A worker's report is evidence only when it quotes
the command output it claims to have produced.

## Layers and ownership

- Root `AGENTS.md` is the configured project-owned index. It is thin and owns
  repository instructions, inventory, roles, conventions, commands, and links
  to durable knowledge. Its 200-line budget is entirely project content.
- Root `CLAUDE.md` is the configured harness-managed entry point. It is an exact
  copy of the installed versioned template: generic protocol, engineering-lead
  operating contract, reviewed delivery flow, inline scope, and `@AGENTS.md`.
  Repositories never customize it.
- `docs/README.md` routes readers without duplicating the index.
- Durable documents describe verified, long-lived facts.
- `docs/active-context.md` is a volatile snapshot of current state, unresolved
  work, and immediate next steps. It is reconsolidated, not appended to.
- Execution plans describe bounded multi-step work and expose state in YAML
  frontmatter.
- Briefs (`docs/briefs/`) record a workstream's what and why — the analysis,
  the decision, the approach — one dated file each. They carry no lifecycle
  metadata; state lives only in the paired execution plan.

## Managed entry point and document scopes (harness v8)

Harness v8 retains the v6 machine-readable statement of
purpose and boundary:

```markdown
<!-- doc-scope:start -->
Scope: A concise, non-empty statement of this document's purpose and boundary;
the text may continue on following lines.
<!-- doc-scope:end -->
```

Managed `CLAUDE.md`, project-owned `AGENTS.md`, `docs/README.md`, and
`docs/active-context.md` each require exactly one canonical block. Other indexed
Markdown files need no declaration, but any declaration that appears is
validated. Delimiters occupy their own lines exactly, outside fenced code, and
enclose non-empty text beginning `Scope:`. Partial, duplicate, reversed,
malformed, or empty blocks fail the mechanical gate. The v5
`doc-index-scope` form is obsolete and rejected.

The inline block consumes only its small canonical declaration in `AGENTS.md`;
this is deliberate. Project instructions need a boundary visible to every
runtime that loads the file, and every remaining line in the 200-line budget
belongs to the project. No other harness protocol consumes that budget.

Syntax is only the deterministic half of the contract. The semantic critic
compares changed declarations with the file's actual routing role and content;
stale, misleading, or over-broad scope is semantic drift. A delegated critic
reports it without inventing a replacement. An in-session critic repairs it
only when transcript-backed knowledge determines the correct boundary.

Declarations are useful without runtime enforcement: they put the intended
boundary in every agent's document context. Optional hook/plugin enforcement,
capability labels, activation, and bypasses are specified separately in
[`scope-guard.md`](scope-guard.md).

## Mechanical and semantic guarantees

The deterministic, repository-local mechanical gate recursively indexes
Markdown under `docs/`, plus the root README, configured project index, and
configured managed entry point. It checks:

- relative Markdown links;
- `.doc-profile` keys and values;
- execution-plan status metadata;
- session-memory status metadata (`docs/sessions/*.md`);
- the configured index and meta-repository inventory ownership;
- canonical inline scope syntax and required routing-file presence;
- exact equality between configured `harness_file` and the installed template,
  fixed ownership paths introduced in v6, and absence of the obsolete v5
  sidecar;
- baseline format and ancestry when a baseline is present;
- the living context's section headings: `docs/active-context.md` carries only
  `State now`, `Unresolved`, and `Next`. This is the objective half of the shape
  contract and the only half a checker can own; narrative prose and "longer than
  what it says warrants" need judgment and stay with the semantic critic. A `##`
  line inside a code fence is content, not a section. `active-context-archive.md`
  is exempt by design — dated sections are what it is for.

The gate also emits advisories — docs past `doc_max_lines`, work-trace files
(briefs, execution plans) named without the `YYYY-MM-DD-` date prefix,
session-memory files (`docs/sessions/*.md`) still `open`, and in `meta` mode any
sub-repo index without an orientation head. Advisories name paths and never
affect the exit code.

**Orientation heads.** A sub-repo index should open with stack, entry points,
build and test command, and the rules that must not be broken, closed by an
`<!-- orientation ends -->` marker. A session entering that repository then
orients on a dozen lines instead of the whole index. The marker is an HTML
comment so it vanishes from the rendered document while staying greppable;
"everything above the first `##`" was rejected as the convention because it
gives the gate nothing to test — an index opening straight into `## Docs` would
be indistinguishable from one with a well-written head. Enforcement lives in the
meta-repo's gate rather than in each sub-repo's profile because sub-repos are
not required to have a profile, and a per-repository rule reaches none of the
ones that don't. The gate resolves each sub-repo's index through its own profile
when it has one, and falls back to `AGENTS.md`. The advisory pairs with a rule
in `doc-start`: in a meta-repo the index's ownership map answers routing by
itself, so a sub-repo index is opened when work enters that repository's code,
never to decide whether it belongs there.

Every size message — the oversized-doc advisory and the thin-index failure —
carries bytes and an estimated token count beside the line count. The limits
count lines while a context window is billed in bytes, and the two do not track
each other: a dense table of 160 lines can outweigh 400 lines of prose, so an
index passes its thin-index check while being the most expensive single item a
session loads. Bytes are the on-disk size, the number `wc -c` prints. The token
figure is a stated convention, bytes divided by four, and never a tokenizer
result; it is printed with a `~` and is accurate within a small factor, which is
all any decision here turns on — every comparison is a ratio between two numbers
produced by the same divisor.

The oversized list has exactly one consumer, and it is `doc-end`. For every
document the gate names that is not already carried in the
`## Oversized docs — reviewed` section of `docs/harness-backlog.md`, `doc-end`
records a verdict there: `split`, which is work and therefore also an ordinary
backlog entry, or `keep whole` with its reason on the same line. `doc-start`
does nothing with the list beyond reporting it, so session start stays cheap.
Neither command may touch the oversized document itself — the verdict is a line
in the backlog and nothing else moves — and a document with a recorded verdict
is never asked about again, so the steady state is zero work.

`split` is a deletion decision before it is anything else: it means judging what
in the document still deserves to exist and removing what does not, never moving
the same prose into an existing document to shrink a line count. One move is
legitimate and narrow — a document that has grown a second subject may be cut
along that seam into a new document with its own title, its own routing line and
a pointer left behind, provided both halves stand alone. Moving text into a
generated file — one a template overwrites, marked as such by a "regenerated
by" / "do not hand-edit" header or equivalent — is forbidden outright, because
the next render discards it; content that belongs there belongs in the
template's own repository instead. And a durable document is never an append
target: an as-built or architecture document describes what the system *is*,
while rationale and history belong in a CHANGELOG or a dated brief, so a
document that accumulates entries over time has become a log whatever its title
says.

A clean mechanical gate means the document graph and metadata are internally
consistent. It does **not** mean prose matches runtime behavior.

The semantic critic reviews factual claims in changed documentation against
code and wiring. It classifies unsupported claims instead of guessing and
enforces English for repository artifacts. Session consolidation requires a
clean mechanical gate, zero stale semantic claims, and no unresolved
living-context shape violation; unverifiable claims stay explicit in the
result.

## Profile schema

`docs/.doc-profile` uses `key = value` records:

- `harness_version`: required protocol version shared by the repo docs, the
  installed commands, and the mechanical checker;
- `schema_version`: `1` in every newly created profile; a missing value is
  accepted only for backward compatibility with legacy profiles;
- `mode`: `leaf` or `meta`;
- `index_file`: root `AGENTS.md` since harness v6, the project-owned Markdown
  index;
- `harness_file`: root `CLAUDE.md` since harness v6, the managed Markdown entry
  point, distinct from `index_file`;
- `inventory_ignore`: optional comma-separated top-level directory names for
  meta-repository inventory checks;
- `build`: optional smoke/build command used before code changes; omit the key
  when no command is known;
- `smoke`: optional smoke command when it is distinct from `build`;
- `index_max_lines`: optional non-negative thin-index limit; `0` disables
  that size check;
- `doc_max_lines`: optional non-negative advisory size limit applied to every
  indexed doc, default `400`; `0` disables the report. Purely informational —
  the gate names each doc past the limit by path, line count, byte size and
  estimated tokens, and the exit code is unaffected. Because a profile travels
  in git while the checker is installed per machine, write this key only when
  the repo wants a value other than the default: an older checker rejects it as
  an unknown key and fails.

Unknown keys and invalid enum values are errors. Comments are explanatory only;
a commented `build` example is not a configured build command. Defaults keep
non-versioned checker use possible, but every command requires an exact harness
version match before doing any work.

## Harness compatibility handshake

Every `doc-*` workflow embeds the protocol version it implements and compares
it with `harness_version` before reading context, running consolidation, or
changing repository documentation.

- Equal versions proceed normally.
- A missing or lower repository version means the installed commands are newer.
  The workflow stops and offers an explicit `docs/` migration through
  `doc-create`; it never migrates implicitly.
- A higher repository version means the installed commands are stale. The
  workflow stops and directs the user to upgrade and reinstall mrcall-ai-kit.
- Downgrading repository docs is never offered.

An authorized docs migration changes only harness-owned metadata and structure,
preserves repository knowledge, writes the new version last, and must finish
with a clean mechanical gate. The v7-to-v8 migration replaces only the exact
managed `CLAUDE.md` template and advances the profile after the reviewed
delivery flow is present. The v6-to-v7 migration similarly introduced the
engineering-lead contract. The explicit v5-to-v6 migration preserves the
complete old project index in root `AGENTS.md`, replaces root `CLAUDE.md` with
the canonical template, removes the obsolete sidecar, swaps the profile paths,
and stops before mutation on a conflicting non-empty `AGENTS.md`. An explicitly
reconciled repository may proceed because the current task already made the
content decision; migration logic never guesses a merge. Older migrations
remove only exact historical harness markers before applying the same split.
`doc-start` and `doc-end` never perform a migration implicitly. Codex
entry-point skills inherit the version from their installed shared
`WORKFLOW.md`, so all three environments use the same handshake.

## Work traces

Substantial work always leaves a trace, so "what are we doing, is it finished,
in progress, or only conceived" is never a matter of memory. The trace is a
pair of dated files sharing one slug:

- `docs/briefs/YYYY-MM-DD-<slug>.md` — the what and why: problem, decision,
  approach, rejected alternatives. Written once, updated only if the
  understanding changes. No status frontmatter.
- `docs/execution-plans/YYYY-MM-DD-<slug>.md` — the lifecycle: YAML frontmatter
  `status` (schema below) plus the step list. Work that is only conceived is
  `planned`; work that never gets a go becomes `superseded`, not deleted.

The pair is created **before execution starts** whenever work is orchestrated —
delegated to multiple agents or workers, in any environment — and whenever a
workstream is expected to span sessions or is too large for the living context
alone. A quick single-session fix needs no pair; the living context and git
already record it.

The rule itself lives in managed root `CLAUDE.md`. Claude Code reads that file
and follows its `@AGENTS.md` import; Codex and OpenCode read root `AGENTS.md`
natively. `doc-start` explicitly loads both configured files unless the current
session confirms their exact content is already present, so workflow behavior
does not depend on guessing runtime injection.

This does not claim a universal Codex primary profile. The kit deliberately
does not overwrite Codex's user-owned global `~/.codex/AGENTS.md`; outside a
workflow that reads managed `CLAUDE.md`, ordinary Codex behavior follows the
operator's global and project `AGENTS.md` chain. OpenCode orchestration has its
own installed primary profiles, while Claude receives the contract from managed
`CLAUDE.md` and from each worker agent's `description`.

Enforcement is layered like the living-context shape: `doc-end` creates a
missing pair retroactively in-session (it holds the transcript that says what
the work was and why); a delegated critic reports the absence instead of
inventing content; the mechanical gate reports undated trace filenames as an
advisory, never a failure.

## Reviewed delivery lifecycle

The managed primary-agent contract divides implementation into two lanes. The
fast path is available only for a local, obvious, reversible change that alters
no public contract, behavior boundary, persistent data, security posture,
dependency graph, or migration, needs neither decomposition nor delegation,
and can be established by one focused real check.

Every other development request is substantial. Its brief is written and
independently reviewed before planning begins; its milestone plan is written
and independently reviewed before implementation begins. A `REVISE` verdict
blocks the next stage until its blocking findings are repaired and re-reviewed.
`FAST_PATH` is valid at brief or plan review only when the reviewer demonstrates
every fast-path criterion. `BLOCKED` is reserved for a product decision,
material risk, irreversible or external action, or missing authority that needs
the CTO.

Implementation proceeds through the smallest independently reviewable
milestones. Each milestone review must pass before dependent work starts, and
a separate final review exercises the integrated result through the final-user
path. A runtime without fresh subagents performs an explicit separate review
pass and reports that limitation instead of silently omitting review. These are
internal engineering gates, not CTO approval checkpoints.

## Session memory, rotation, and worker reports

The opt-in model router, the per-session shared memory it writes
(`docs/sessions/<id>.md`), the hand-off that brackets a context window, and the
budget a worker's report must respect all live in
[`model-router.md`](model-router.md). They are a separate subject: the gate and
the `/doc-*` contract below apply whether or not the router is installed.

## Execution-plan schema

Every Markdown file under `docs/execution-plans/` except placeholders has YAML
frontmatter with one `status` value:

- `planned`: accepted but not started;
- `active`: currently being executed;
- `blocked`: unable to advance until its recorded condition changes;
- `completed`: all required work and verification are done;
- `superseded`: replaced or deliberately abandoned, with the reason recorded.

Commands derive plan state from metadata, never from prose. Only `completed`
plans are finished; the other states remain visible with their labels.
Checkboxes inside a plan are a reading aid, not lifecycle state: unticked boxes
under `status: completed` are untidiness, not a contradiction, and no command
treats them as work to investigate or as a reason to withhold consolidation.

## Baseline semantics

`doc_baseline_commit` identifies the code commit whose behavior has been
reconciled into living documentation. It must resolve and be an ancestor of
`HEAD`.

The documentation update recording that baseline can be committed after the
referenced code commit. A reconciliation commit touching only `docs/**`, the
configured project index, and the configured harness entry point after the baseline is
therefore not product drift. Start-of-session reporting distinguishes
code-bearing commits from harness-only commits and reports uncommitted changes
separately.

The end workflow reviews committed changes since the baseline and relevant
working-tree changes. It advances the baseline only after the mechanical gate
passes, semantic review has zero stale claims, and no unresolved
living-context shape violation remains.
Advancing it to `HEAD` records what was reviewed; it cannot represent an
uncommitted code change as part of that commit.

## Living-context discipline

`active-context.md` contains only current facts:

- verified capabilities that materially affect current work;
- work in progress or awaiting verification;
- unresolved failures and blockers;
- immediate next actions.

It does not retain per-session done lists, corrected theories, or chronological
notes. A durable architectural fact belongs in a durable doc; a decision fully
captured by a completed plan or brief needs no duplicate here. Session
narrative that is neither of those — the detailed "what we tried, what broke,
what we verified" record of a session — moves to `docs/active-context-archive.md`
instead of being deleted outright: dated sections, newest first, preserved
verbatim. Nothing that was ever true is lost, it is just no longer on the path
every session pays to read. Contradictory current and historical claims are a
semantic failure even when the mechanical gate is clean.

The archive is deliberately outside `doc-start`'s Phase 2 (volatile-layer) read
set — it exists to answer "when did we do X", read on demand, not to be loaded
every session start. It is still an ordinary file under `docs/`: the mechanical
gate indexes it like any other Markdown file (dead links inside it are still
checked, and it is never exempt from `index_docs()`; the single exception is the
advisory `doc_max_lines` report, which skips it precisely because cold storage
is meant to grow), and it is discoverable through a routing line in
`docs/README.md`, the same as every other durable doc.

Two independent points enforce this, so a lazy "consolidate" (prepend today's
notes, touch nothing else) cannot silently drift the file into a changelog for
months unnoticed. `doc-end` Phase 3 archives-then-trims as part of normal
per-session reconsolidation (proactive). The `doc-critic` skill independently
checks the file's shape — extra dated headings, narrative prose, well over the
line target — and is the reactive safety net that catches a sloppy Phase 3.

Three layers hold this rule, because two of them are LLM judgment and judgment
is what failed: the mechanical gate rejects a non-canonical section outright,
the end workflow treats a shape violation as a reason to consolidate, and the
semantic critic catches the drift a heading cannot express. Only the first is
deterministic, and only the first applies to an edit made by something that
never ran a `doc-*` command at all.

The shape is checked on every consolidation attempt, including one that
concludes no consolidation is needed. Drift here does not follow from the
current session's work and is invisible to `git status`: the file may have been
mis-shaped for months, or rewritten by something that never invoked the end
workflow. A run that only asks whether new work exists would report nothing to
do and leave the violation standing indefinitely, so a mis-shaped file is
itself a reason to consolidate.

What the safety net then does depends on who is running it, and follows from
the delegation boundary above. Running in-session, it repairs the file:
archive and rewrite. Running as a delegate, it reports the violation and does
not repair, because sorting current from historical is the Phase-3 decision
that needs the transcript it does not have. Such a report is blocking: the
baseline may not advance over a mis-shaped `active-context.md`, so the session
returns to Phase 3 and redoes it. Both paths refuse to let the violation
through; only one of them is entitled to fix it.
