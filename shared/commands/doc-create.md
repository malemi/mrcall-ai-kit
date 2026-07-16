---
description: Bootstrap the doc-harness in this repo — create the docs/ skeleton, the profile, and a thin index.
allowed-tools: Bash(git *) Bash(ls *) Bash(mkdir *) Bash(cat *) Bash(python3 *) Write Edit
---

Bootstrap this repo's documentation harness. **Idempotent** — create only what is missing; never overwrite existing content. **Never fabricate knowledge** — you create the *mechanism* (skeleton + profile + gate wiring), not invented architecture/convention prose. Everything you write is in **English**.

## Step 1 — Detect current state
- Is there a `docs/` dir? a `docs/.doc-profile`? an index file (`CLAUDE.md`)?
- Is this a **meta-repo** (does it check out other independent git repos as sub-dirs) or a **leaf** repo? `ls -d */.git 2>/dev/null` hints at it. Report what you found; do not assume.

## Step 2 — Write the profile (ask only what you cannot detect)
Create `docs/.doc-profile` (skip if it exists — show it instead):
```
mode = meta | leaf            # meta only if this repo checks out other repos
index_file = CLAUDE.md
inventory_ignore =            # (meta only) sub-repo dirs to skip, comma-separated
```
Ask the user for the build/smoke command if it is not obvious from the repo (`sbt` / `npm` / `make` / `pytest`); record it as a `# build = ...` comment line.

## Step 3 — Create the docs/ skeleton (only the missing pieces)
- `docs/active-context.md` — with frontmatter `doc_baseline_commit: <git rev-parse HEAD>` and `doc_baseline_date: <today>`, and a one-line "state now" placeholder. This is the volatile source of truth.
- `docs/README.md` — a THIN pointer: "index of transversal docs; the repo inventory / roles / ownership live only in the index file." No repo table.
- `docs/execution-plans/` — dir with a `.gitkeep`.
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
