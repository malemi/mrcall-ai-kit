---
name: doc-critic
description: Verify documentation against code reality, and check whether docs/active-context.md has drifted into a changelog. Given the docs changed this session, flag any claim that describes a feature/endpoint/file/flag that does not exist or is not wired (dead code documented as live), plus non-English artifacts. Also independently checks that active-context.md still matches the living-snapshot contract (reporting the violation when delegated, repairing it when run in-session) and that substantial work since the baseline left its brief+plan work trace. Used by /doc-end before advancing the baseline.
---

# doc-critic — does the documentation match the code, and is active-context.md still a snapshot?

The mechanical gate (`doc-check.py`) catches dead links, inventory drift, and duplicate indexes. It CANNOT catch *semantic* drift: a doc that confidently describes something the code no longer does. That is the rot that survives for months — a dead pipeline documented as live, an architecture describing a service that was split, a "supported" flag that was removed. This skill is that check. It also cannot catch *shape* drift: `doc-end` Phase 3 says "reconsolidate, don't append" every time it runs, but that instruction is easy to satisfy lazily (prepend today's summary, touch nothing else) and nothing mechanical was watching — a real repo's `active-context.md` grew from ~120 to ~1500 lines over two months of sessions that each individually said "consolidate" in their commit message. The shape check below is the backstop for exactly that failure.

## When to run
Invoked by `/doc-end`, scoped to the **docs touched this session** (`git diff <doc_baseline_commit>..HEAD -- '*.md'`). Can also run standalone as a full-repo audit, or in-session from `doc-create`'s migration. Run the living-context shape check (next section) before the per-claim audit in every case: where you are allowed to repair, the claim pass then only has to verify the small current remainder rather than the history on its way out; where you are not, you still want the violation reported before anything else, because it changes what the claim pass is auditing.

## Living-context shape (`docs/active-context.md`) — always check; repair only in-session

**Decide first whether you may repair. The default is NO.**

- **Delegated to you as a subagent** — from `doc-end` Phase 4, or any prompt handing you this check from a parent session: **report, never repair.** By Phase 4 the session has already decided what is current, in Phase 3, using transcript knowledge you do not have and cannot reconstruct. A violation surviving that far does not mean the file needs tidying; it means the decision was skipped or botched, and redoing it belongs to the session holding the transcript. Emit exactly `active-context.md: shape violation — NOT repaired here, Phase 3 must redo it`, list what is mis-shaped, and treat it as a blocking finding: the caller must not advance the baseline over it.
- **Running in-session** — a standalone full-repo audit, `doc-create`'s migration, or a `doc-end` with no worker available, where you are the session and not a delegate: **repair it**, per the recipe below. There is no other decision-maker to defer to. Use every kind of evidence you actually hold: in a full-repo audit or a migration that is the documents and the code, but inside a worker-less `doc-end` you also hold the session transcript, and it outranks both — what you learned this session about which work is finished, abandoned, or superseded is exactly what the sort needs and what a delegate is denied.

If you cannot tell which situation you are in, you are a delegate: report, do not repair. Rewriting a file you were only asked to inspect is the more expensive mistake.

**Detect a violation** — any of these means the contract (`documentation-harness.md`, "Living-context discipline") is not being met:
- A second-level heading other than `State now`, `Unresolved`, or `Next` — most tellingly anything shaped like `## <date> — <title>`, which is the append-only-changelog pattern this file must never become.
- Prose that narrates what happened — past-tense session recaps, "we tried X then Y", corrected theories, verification blow-by-blow — rather than declaring what's true right now. This can hide inside `State now` even without an extra heading.
- Well past the ~120-line target with no corresponding density of genuinely current, operationally-relevant material.

**If no violation**: say so, move on to the per-claim audit.

**If violated and you are a delegate**: report as specified above and move on to the per-claim audit — which now audits the file as it stands, history included.

**If violated and you are in-session, repair it:**
1. Read the full file. Sort every passage into CURRENT (materially affects ongoing work, an unresolved failure/blocker, or an immediate next action) or HISTORICAL (everything else — it was true, it just isn't the present state anymore). **Sort by meaning, not by heading.** A file organized under names of its own — `Known Issues`, `Active workstreams`, `What Is Built`, `Immediate Next Steps` — violates the shape, but its content is largely CURRENT and belongs *folded into* the canonical section it matches (`Unresolved`, `State now`, `Next`), not moved to the archive. Archiving is for material that is no longer true of the present; a current fact under an unexpected heading is a renaming job, and archiving it would be data loss dressed up as tidying.
2. Nothing is deleted, only relocated. Take every HISTORICAL passage, and if it isn't already under a `## <date> — <title>` heading, wrap it under the best-known date (git log on the file, dates named in the prose itself); if truly undated, say `## date unknown — <title>` rather than inventing one. Prepend these sections, verbatim, newest-first, to the top of `docs/active-context-archive.md`. If that file doesn't exist yet, create it with a short English header: what it is (pruned session narrative, dated, newest-first), that it is cold storage never read by `/doc-start`, and that it exists to answer "when did we do X" without reconstructing it from `git log -p`. If you are creating it for the first time, add one routing line to `docs/README.md` pointing at it (so it stays discoverable) — do not add it anywhere `/doc-start` treats as must-read.
3. Rewrite `docs/active-context.md` to contain only its frontmatter (leave `doc_baseline_commit` / `doc_baseline_date` exactly as they were — this repair is orthogonal to baseline advancement, which stays `/doc-end` Phase 4's job), the `# Active Context` title, and `## State now` / `## Unresolved` / `## Next` built from the CURRENT material only, declarative and present-tense.
4. Report what you did: lines before → after in `active-context.md`, and the archive's new line count.

## Work-trace presence — report; the trace decision is the session's

The contract pairs substantial work with `docs/briefs/YYYYMMDD-<slug>.md` +
`docs/execution-plans/YYYYMMDD-<slug>.md`. From the diff alone you can see one
signal: a change set since the baseline that is clearly multi-step — many
non-doc files, new modules, the fingerprints of an orchestrated fan-out — with
no brief and no plan created or updated alongside it. Report that as
`TRACE: substantial change set with no brief/plan touched — Phase 3 must decide`.
Never create the pair yourself when delegated: what the work was, why it was
done, and whether it is below the trace threshold is transcript knowledge you
do not have. Running in-session (a full-repo audit, a migration, a worker-less
`doc-end`) you hold that knowledge — create or update the pair as `doc-end`
Phase 3 prescribes. This finding sends the decision back; it does not force a
pair into existence: the session may resolve it by stating, in its output's
*work trace* slot, that the work was a small fix needing no trace.

## What to verify — for each factual claim in the changed docs
Extract the concrete, checkable claims (not prose/opinion) and verify each against the actual code:

1. **Existence** — a named file / module / function / class / endpoint / env var / CLI flag / config key the doc mentions: does it exist? `grep`/`ls`/read to confirm. A doc naming `services/foo.py` or `POST /api/x` that isn't there is a defect.
2. **Wired, not dead** — does the described capability actually run? An endpoint that exists but 500s on every call (broken import), a tool defined but never registered, a method with zero callers — the doc must not present it as a live feature. Trace at least one caller / registration on the runtime path.
3. **Accurate shape** — counts ("9 tools"), routes, table/column names, ports, hosts: spot-check the load-bearing ones against source.
4. **Right owner** — does the doc attribute a capability to the correct service/repo? (e.g. after a split, don't describe repo A as doing what moved to repo B.)
5. **English** — is every artifact (docs, comments, script prompts) in English? Flag non-English content unless it is explicitly end-user-facing localized copy (a customer email, an `it-IT` UI string). The surrounding code/docs stay English.

## How to work (reflexion loop)
- For each claim: verdict `CONFIRMED` (matches code), `STALE` (code says otherwise — quote the file:line), or `UNVERIFIABLE` (say why; do not guess).
- Return the STALE + UNVERIFIABLE findings to `/doc-end`, which repairs the doc and re-runs this skill until zero STALE remain.
- **Never fabricate.** If you cannot verify a claim against code, mark it UNVERIFIABLE — do not invent a confirmation. Correctness over coverage.
- Prefer reading the real source over trusting a prior doc; the code wins over the doc every time.

## Output
Lead with the shape check, always — one of `active-context.md: shape OK`, `active-context.md: archived — N → M lines (archive: +K lines)` (repaired in-session), or `active-context.md: shape violation — NOT repaired here, Phase 3 must redo it` plus the list of what is mis-shaped (delegated). The third form is a blocking finding, not an observation: whoever called you must not advance the baseline until it is resolved. If the diff shows substantial work with no trace pair touched, add the `TRACE:` line next — resolved by the session's explicit decision, never by inventing files. Then the claim list: `STALE: <claim> — code says <file:line: reality>` / `UNVERIFIABLE: <claim> — <why>`. If everything checks out: `Critic clean — N claims verified.`
