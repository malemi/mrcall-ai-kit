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

Both session start and consolidation may delegate to pinned-model workers where
the environment provides them — `worker-sonnet` for mechanical execution, `worker-opus` for
independent verification — through whatever subagent primitive the tool
exposes (`Agent` in Claude Code, `task` in OpenCode). Workers declare their own
model, so the tier follows the task rather than the delegating session; a
subagent that declares none inherits the parent's and therefore saves context
only.

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

- The configured index file is thin and owns repository inventory, roles, and
  ownership.
- `docs/README.md` routes readers without duplicating the index.
- Durable documents describe verified, long-lived facts.
- `docs/active-context.md` is a volatile snapshot of current state, unresolved
  work, and immediate next steps. It is reconsolidated, not appended to.
- Execution plans describe bounded multi-step work and expose state in YAML
  frontmatter.
- Briefs (`docs/briefs/`) record a workstream's what and why — the analysis,
  the decision, the approach — one dated file each. They carry no lifecycle
  metadata; state lives only in the paired execution plan.

## Mechanical and semantic guarantees

The deterministic, repository-local mechanical gate recursively indexes
Markdown under `docs/`, plus the root README and configured index. It checks:

- relative Markdown links;
- `.doc-profile` keys and values;
- execution-plan status metadata;
- session-memory status metadata (`docs/sessions/*.md`);
- the configured index and meta-repository inventory ownership;
- baseline format and ancestry when a baseline is present;
- the living context's section headings: `docs/active-context.md` carries only
  `State now`, `Unresolved`, and `Next`. This is the objective half of the shape
  contract and the only half a checker can own; narrative prose and "longer than
  what it says warrants" need judgment and stay with the semantic critic. A `##`
  line inside a code fence is content, not a section. `active-context-archive.md`
  is exempt by design — dated sections are what it is for.

The gate also emits advisories — docs past `doc_max_lines`, work-trace files
(briefs, execution plans) named without the `YYYY-MM-DD-` date prefix, and
session-memory files (`docs/sessions/*.md`) still `open`. Advisories name
paths and never affect the exit code.

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
- `index_file`: repository-relative existing Markdown index;
- `inventory_ignore`: optional comma-separated top-level directory names for
  meta-repository inventory checks;
- `build`: optional smoke/build command used before code changes; omit the key
  when no command is known;
- `smoke`: optional smoke command when it is distinct from `build`;
- `index_max_lines`: optional non-negative thin-index limit; `0` disables
  that size check;
- `doc_max_lines`: optional non-negative advisory size limit applied to every
  indexed doc, default `400`; `0` disables the report. Purely informational —
  the gate names each doc past the limit by path and line count, and the exit
  code is unaffected. Because a profile travels in git while the checker is
  installed per machine, write this key only when the repo wants a value other
  than the default: an older checker rejects it as an unknown key and fails.

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
with a clean mechanical gate. Codex entry-point skills inherit the version from
their installed shared `WORKFLOW.md`, so all three environments use the same
handshake.

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

Because no `doc-*` command is running at the moment such work begins, the rule
itself must already be in context: the configured index file carries a one-line
pointer stating it (`doc-create` writes that line), which is what makes the
rule fire exactly in repositories that use this harness and nowhere else.

Enforcement is layered like the living-context shape: `doc-end` creates a
missing pair retroactively in-session (it holds the transcript that says what
the work was and why); a delegated critic reports the absence instead of
inventing content; the mechanical gate reports undated trace filenames as an
advisory, never a failure.

## Session memory (opt-in model router, Claude Code only)

`--features router` installs a dormant `UserPromptSubmit` hook plus `/router`
and `worker-fable`. `/ai-help` ships with `doc-harness` instead — it lives in
`shared/commands/` alongside the other cross-tool commands, not in the
router's Claude-only branch. Off by default: the hook checks for
`~/.config/mrcall-ai-kit/router.on` and exits with no output when the flag is
absent, at the cost of one filesystem check per prompt. `/router on` registers
the hook in `~/.claude/settings.json` (if not already registered) and creates
the flag; `/router off` removes only the flag, leaving registration in place;
`/router unregister` removes both.

The intended shape: the session model is a cheap classifier (Haiku) that
answers trivial prompts itself and delegates everything else to a pinned-model
worker (`worker-sonnet` / `worker-opus` / `worker-fable`) via the native
subagent primitive. Because a subagent starts with a fresh context, delegation
without continuity loses whatever the previous worker understood — so a routed
session gets a shared-memory file, `docs/sessions/<session-id>.md`, the same
kind of object as `docs/active-context.md`: a living snapshot, never a log,
same anti-drift discipline, same repo, readable with `cat`.

**Who writes it, and when**: whoever answers the turn, at their own
discretion — not the classifying model. The model that did the work is the
only one that knows what was worth recording; a trivial turn correctly writes
nothing. The write protocol travels in the hook's injected directive and in
delegation prompts, so no worker definition changes for this.

**Lifecycle**: a session file's frontmatter `status` is `open` until `/doc-end`
reads it (when the router named one for this turn — see Phase 2 of the end
workflow), folds whatever is durable into `active-context.md`, and flips it to
`closed`. A session that ends without `/doc-end` leaves an `open` orphan.
Liveness cannot be determined — Claude Code exposes no PID or lock for a
session, only a transcript file whose mtime cannot distinguish a dead session
from an idle one — so `/router sweep` reports open files with their age and a
*probably dead* flag past 24 hours, and never closes or edits one itself;
that judgment stays with a human.

**Read scope**: `docs/sessions/**` follows the same rule as `docs/projects/**`
— `doc-start` never opens it. The mechanical gate still indexes it: it
validates `status` is exactly `open` or `closed` (a gate failure otherwise,
the same enforcement as execution-plan status) and reports an advisory count
of files still open (never a failure — an open file mid-session is normal,
and judging which are stale is `/router sweep`'s job, not the gate's).
`docs/sessions/` is gitignored by `doc-create` — these files are per-machine
and ephemeral by design, not repository knowledge.

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
referenced code commit. A docs-only reconciliation commit after the baseline is
therefore not product drift. Start-of-session reporting distinguishes
code-bearing commits from docs-only commits when possible and reports
uncommitted changes separately.

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
