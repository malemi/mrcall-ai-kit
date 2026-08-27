---
description: Bootstrap the doc-harness in this repo — create the docs/ skeleton, the profile, and a thin index.
allowed-tools: Bash(git *) Bash(ls *) Bash(mkdir *) Bash(cat *) Bash(python3 *) Write Edit
---

Bootstrap this repo's documentation harness. **Idempotent** — create only what is missing; never overwrite existing content. **Never fabricate knowledge** — you create the *mechanism* (skeleton + profile + gate wiring), not invented architecture/convention prose. Everything you write is in **English**.

## Harness version preflight — run before every other step
This command implements `harness_version = 4`. If `docs/.doc-profile` exists, read its `harness_version` before inspecting or changing anything else.

- Equal to `4` ⇒ continue normally.
- Missing or lower than `4` ⇒ stop and report: `Harness version mismatch: repo docs are older than the installed commands (docs: <version|legacy>, commands: 4). Upgrade docs/ explicitly with doc-create, or cancel and leave the repo unchanged.` Do not migrate until the user explicitly chooses the docs upgrade.
- Greater than `4` ⇒ stop and report: `Harness version mismatch: installed commands are older than the repo docs (commands: 4, docs: <version>). Upgrade mrcall-ai-kit and reinstall its commands; docs/ must not be downgraded.`

When the user explicitly authorizes a docs upgrade, migrate only harness-owned structure and metadata, preserve all repository knowledge, add/update `harness_version = 4` last, run the mechanical gate, and report every changed file. Never perform a downgrade. A missing profile means this is a fresh bootstrap, not a mismatch.

**Migrating to `harness_version = 4`**:

- *From `3`*: add exactly one canonical block to the configured index,
  `docs/README.md`, and `docs/active-context.md`, choosing concise scope text
  from each file's actual routing role. Validate any scope block already present
  instead of adding a second one. Do not add blocks to other documents merely
  because they exist. Update `harness_version` only after all three declarations
  pass the gate.
- *From `1` or `2`, or legacy*: first perform the older migration below, then
  perform the v3-to-v4 scope migration above. There is no implicit migration in
  `doc-start` or `doc-end`.

**Older migrations** — from `1` or `2`, or from a legacy profile predating the key entirely:

- *From `1` or `2`*: no profile keys change.
- *From legacy* (no `harness_version` at all): add only the required keys the profile lacks — `harness_version`, `schema_version`, `index_max_lines` — leaving every existing key, comment, and deliberate omission as it stands. Expect a legacy repo to fail gate checks it was never held to: plan `status` fields carrying prose instead of one enumerated value, an index over the thin limit, dead links older than the profile. Report every one. Repair what is harness-owned metadata (a `status` value; a missing profile key). Do NOT invent a file to satisfy a dead link or rewrite prose you were not asked to touch — surface those and let the user decide.

In every case the behavioral migration is `docs/active-context.md`: if it violates the living-context shape (any `##` section beyond `State now` / `Unresolved` / `Next`, chronological/dated narrative, or well over the ~120-line target — the append-only-changelog failure mode v1 did not guard against), perform the same repair described in `doc-end.md` Phase 3 and, in full, in the `doc-critic` skill. You are running in-session here, not as a delegate, so that skill's repair branch is yours to perform. Follow its rule about sorting by meaning rather than by heading: current material under a non-canonical heading is folded into the section it belongs to, and only genuinely historical material moves to `docs/active-context-archive.md` (created if absent; dated sections, newest first, verbatim — nothing discarded, only relocated). Report the line-count before/after and the archive's size. A repo already compliant has nothing to migrate here.

From `3` onward the heading half of that shape is enforced mechanically — `doc-check.py` fails on any `##` section in `docs/active-context.md` outside the canonical three — so a repo that skips this migration step will not pass its own gate. From `4` onward the three routing declarations are also enforced mechanically. That is the point: the earlier versions asked an LLM to notice drift and it went unnoticed for two months in a real repo.

## Step 1 — Detect current state
- Is there a `docs/` dir? a `docs/.doc-profile`? an index file (`CLAUDE.md`)?
- Is this a **meta-repo** (does it check out other independent git repos as sub-dirs) or a **leaf** repo? `ls -d */.git 2>/dev/null` hints at it. Report what you found; do not assume.

## Step 2 — Write the profile (ask only what you cannot detect)
Create `docs/.doc-profile` (skip if it exists — show it instead):
```
harness_version = 4
schema_version = 1
mode = meta | leaf            # choose exactly one; meta only for independent sub-repos
index_file = CLAUDE.md
inventory_ignore =            # (meta only) sub-repo dirs to skip, comma-separated
index_max_lines = 200
# doc_max_lines = 400         # optional; defaults to 400. Advisory only — names docs
                              # past this, never fails the gate. Write it only to change
                              # the default or to disable the report with 0.
# build = <executable smoke command>  # omit this key when unknown
```
The profile is machine-readable: one `key = value` per line; comments never carry values. `harness_version` is the compatibility handshake and is required. `schema_version` describes the profile syntax. Required keys for new profiles are `harness_version`, `schema_version`, `mode`, `index_file`, `inventory_ignore`, and `index_max_lines`. `build`, `smoke`, and `doc_max_lines` are optional. A `build`/`smoke` value must be a non-empty executable command; ask for it only if it cannot be detected, omit the key when unknown, and do not invent one. Leave `doc_max_lines` out unless the repo wants a different limit: profiles travel in git while the checker is installed per machine, so writing an optional key that only newer checkers know turns every older machine's gate into a hard failure on an unknown key.

## Step 3 — Create the docs/ skeleton (only the missing pieces)
- `docs/active-context.md` — with frontmatter `doc_baseline_commit: <git rev-parse HEAD>` and `doc_baseline_date: <today>`, one canonical scope block, and only `State now`, `Unresolved`, and `Next` sections. It is current state, not a changelog; target at most 120 lines and route durable knowledge elsewhere before pruning history.
- `docs/README.md` — a THIN pointer with one canonical scope block: "index of transversal docs; the repo inventory / roles / ownership live only in the index file." No repo table.
- `docs/execution-plans/` — dir with a `.gitkeep`.
- `docs/briefs/` — dir with a `.gitkeep`.
- `docs/sessions/` — add a `docs/sessions/` line to `.gitignore` (create the
  file if it does not exist; append the line if it does and does not already
  have it). Do not create the directory or a placeholder file in it — this is
  the opt-in model router's per-session shared memory, one `<session-id>.md`
  file per routed session, and the directory comes into existence only when
  the router's hook or a delegated worker first writes to it. `/doc-end`
  promotes what matters into `active-context.md`; the file itself stays
  behind.
- Every plan begins with YAML frontmatter containing exactly one lifecycle value: `status: planned | active | blocked | completed | superseded`. Never encode authoritative status in headings, emoji, prose, or checkboxes.
- Briefs and plans are the repo's **work traces**, each named `YYYY-MM-DD-<slug>.md` with one shared slug per workstream: the brief holds the what/why (no status frontmatter), the plan holds the lifecycle. Orchestrated or multi-session work creates both before execution starts; the index carries this rule as a one-line pointer (Step 4). The gate reports undated trace filenames as an advisory.
- Stubs (empty-but-titled), only if the repo will use them: `docs/known-issues-and-solutions.md`, `docs/quality-grades.md`, `docs/harness-backlog.md`. Do NOT stub `ARCHITECTURE.md` / `CONVENTIONS.md` / `system-rules.md` — a fabricated architecture doc is worse than none; write those when the knowledge exists.

## Step 4 — Ensure the index is thin and single-source
- If `CLAUDE.md` is missing, create a thin one: a short intro, one canonical scope block, and pointers to `docs/`. For a **meta** repo, add a `## Services` table (one row per sub-repo you actually detected — name, path, stack, role; do not invent repos). For a **leaf** repo, no Services table is needed.
- If `CLAUDE.md` already exists but has grown into prose, FLAG it (don't silently rewrite) — the harness wants a thin index.
- Whether the index is created or found, ensure it carries the one-line work-trace rule; add it if missing (this is harness-owned structure, not prose): `Work traces: orchestrated or multi-session work starts by creating docs/briefs/YYYY-MM-DD-<slug>.md (what/why) + docs/execution-plans/YYYY-MM-DD-<slug>.md (status frontmatter) before execution.` The index is the only file guaranteed to be in context at the moment such work begins — no `doc-*` command runs then — so this line is what makes the rule fire in harness repos and nowhere else.

The canonical declaration printed into each fresh routing file is exactly:
```markdown
<!-- doc-scope:start -->
Scope: <concise, non-empty statement of this document's purpose and boundary,
optionally continued on following lines>
<!-- doc-scope:end -->
```
Print all three declarations during fresh bootstrap; tailor the text to the
configured index, docs router, and volatile snapshot respectively. The
delimiters are exact and each routing file has exactly one block.

## Step 5 — Verify the gate, then hand off
- Run the gate against this repo:
  !`python3 "$HOME/.config/mrcall-ai-kit/doc-check.py" --repo . 2>&1 || true`
- Fix anything it reports (dead links, inventory drift), then re-run until clean.
- **Git hooks are out of scope** (repo-local plumbing, not shipped by the kit). If the user wants a pre-commit block, tell them the optional one-liner: create `.githooks/pre-commit` that runs the gate, then `git config core.hooksPath .githooks`.

## Output
`Doc-harness bootstrapped in <repo> (<mode> mode). Created: [files]. Profile: docs/.doc-profile. Gate: clean. Next: /doc-start to begin sessions.`
