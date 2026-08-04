---
description: Bootstrap the doc-harness in this repo — create the docs/ skeleton, the profile, and a thin index.
allowed-tools: Bash(git *) Bash(ls *) Bash(mkdir *) Bash(cat *) Bash(python3 *) Write Edit
---

Bootstrap this repo's documentation harness. **Idempotent** — create only what is missing; never overwrite existing content. **Never fabricate knowledge** — you create the *mechanism* (skeleton + profile + gate wiring), not invented architecture/convention prose. Everything you write is in **English**.

## Harness version preflight — run before every other step
This command implements `harness_version = 2`. If `docs/.doc-profile` exists, read its `harness_version` before inspecting or changing anything else.

- Equal to `2` ⇒ continue normally.
- Missing or lower than `2` ⇒ stop and report: `Harness version mismatch: repo docs are older than the installed commands (docs: <version|legacy>, commands: 2). Upgrade docs/ explicitly with doc-create, or cancel and leave the repo unchanged.` Do not migrate until the user explicitly chooses the docs upgrade.
- Greater than `2` ⇒ stop and report: `Harness version mismatch: installed commands are older than the repo docs (commands: 2, docs: <version>). Upgrade mrcall-ai-kit and reinstall its commands; docs/ must not be downgraded.`

When the user explicitly authorizes a docs upgrade, migrate only harness-owned structure and metadata, preserve all repository knowledge, add/update `harness_version = 2` last, run the mechanical gate, and report every changed file. Never perform a downgrade. A missing profile means this is a fresh bootstrap, not a mismatch.

**Migrating from `harness_version = 1`**: no profile keys change. The one behavioral migration is `docs/active-context.md`: if it violates the living-context shape (any `##` section beyond `State now` / `Unresolved` / `Next`, chronological/dated narrative, or well over the ~120-line target — the append-only-changelog failure mode v1 did not guard against), perform the same archive-and-trim repair described in `doc-end.md` Phase 3 and in the `doc-critic` skill: move every non-current section to `docs/active-context-archive.md` (create it; dated sections, newest first, verbatim — nothing is discarded, only relocated) and rewrite `docs/active-context.md` down to the compliant shape. Report the line-count before/after and the archive file's new size. A repo already compliant (e.g. freshly bootstrapped) has nothing to migrate here.

## Step 1 — Detect current state
- Is there a `docs/` dir? a `docs/.doc-profile`? an index file (`CLAUDE.md`)?
- Is this a **meta-repo** (does it check out other independent git repos as sub-dirs) or a **leaf** repo? `ls -d */.git 2>/dev/null` hints at it. Report what you found; do not assume.

## Step 2 — Write the profile (ask only what you cannot detect)
Create `docs/.doc-profile` (skip if it exists — show it instead):
```
harness_version = 2
schema_version = 1
mode = meta | leaf            # choose exactly one; meta only for independent sub-repos
index_file = CLAUDE.md
inventory_ignore =            # (meta only) sub-repo dirs to skip, comma-separated
index_max_lines = 200
# build = <executable smoke command>  # omit this key when unknown
```
The profile is machine-readable: one `key = value` per line; comments never carry values. `harness_version` is the compatibility handshake and is required. `schema_version` describes the profile syntax. Required keys for new profiles are `harness_version`, `schema_version`, `mode`, `index_file`, `inventory_ignore`, and `index_max_lines`. `build` or `smoke` is optional, but if present its value must be a non-empty executable command. Ask for it only if it cannot be detected; omit the key when unknown and do not invent one.

## Step 3 — Create the docs/ skeleton (only the missing pieces)
- `docs/active-context.md` — with frontmatter `doc_baseline_commit: <git rev-parse HEAD>` and `doc_baseline_date: <today>`, and only `State now`, `Unresolved`, and `Next` sections. It is current state, not a changelog; target at most 120 lines and route durable knowledge elsewhere before pruning history.
- `docs/README.md` — a THIN pointer: "index of transversal docs; the repo inventory / roles / ownership live only in the index file." No repo table.
- `docs/execution-plans/` — dir with a `.gitkeep`.
- Every plan begins with YAML frontmatter containing exactly one lifecycle value: `status: planned | active | blocked | completed | superseded`. Never encode authoritative status in headings, emoji, prose, or checkboxes.
- Stubs (empty-but-titled), only if the repo will use them: `docs/known-issues-and-solutions.md`, `docs/quality-grades.md`, `docs/harness-backlog.md`. Do NOT stub `ARCHITECTURE.md` / `CONVENTIONS.md` / `system-rules.md` — a fabricated architecture doc is worse than none; write those when the knowledge exists.

## Step 4 — Ensure the index is thin and single-source
- If `CLAUDE.md` is missing, create a thin one: a short intro + pointers to `docs/`. For a **meta** repo, add a `## Services` table (one row per sub-repo you actually detected — name, path, stack, role; do not invent repos). For a **leaf** repo, no Services table is needed.
- If `CLAUDE.md` already exists but has grown into prose, FLAG it (don't silently rewrite) — the harness wants a thin index.

## Step 5 — Verify the gate, then hand off
- Run the gate against this repo:
  !`python3 "$HOME/.config/mrcall-ai-kit/doc-check.py" --repo . 2>&1 || true`
- Fix anything it reports (dead links, inventory drift), then re-run until clean.
- **Git hooks are out of scope** (repo-local plumbing, not shipped by the kit). If the user wants a pre-commit block, tell them the optional one-liner: create `.githooks/pre-commit` that runs the gate, then `git config core.hooksPath .githooks`.

## Output
`Doc-harness bootstrapped in <repo> (<mode> mode). Created: [files]. Profile: docs/.doc-profile. Gate: clean. Next: /doc-start to begin sessions.`
