---
status: completed
---

# Managed CLAUDE and project AGENTS execution plan

Brief: [../briefs/2026-08-30-harness-sidecar.md](../briefs/2026-08-30-harness-sidecar.md)

## 1. Versioned ownership contract

- Bump the checker, critic, and all workflows to harness v6.
- Make `harness_file = CLAUDE.md` and `index_file = AGENTS.md` the fresh profile
  defaults without changing the profile schema.
- Add one canonical managed `CLAUDE.md` template with `@AGENTS.md`, inline scope,
  and generic work-trace behavior.
- Remove the v5 external `doc-index-scope` format from the active contract.

## 2. Installation, bootstrap, and migration

- Install the canonical template beside the mechanical checker for every
  runtime that installs the documentation harness.
- Make fresh `doc-create` render the managed template and create only a thin
  project-owned `AGENTS.md` stub when no project index exists.
- Implement explicit v5-to-v6 migration: preserve the full configured-index
  payload in root `AGENTS.md`, replace `CLAUDE.md` with the exact template,
  remove the obsolete sidecar, swap profile paths, and update the version last.
- Stop safely on an existing conflicting `AGENTS.md`; never merge prose by
  heuristic.
- Deliberately reconcile this repository's existing operator rules and v5
  project index in `AGENTS.md`, then complete the same v6 ownership contract;
  do not weaken the general collision stop to automate this one known choice.

## 3. Gate, critic, and scope guard

- Index and validate both configured files, applying the 200-line limit only to
  project-owned `index_file`.
- Require exact template equality for `harness_file` and an inline project scope
  on `index_file`; reject external index-scope markers.
- Remove external-scope resolution from the scope guard and its tests.
- Update semantic review to treat template drift and misplaced project guidance
  as ownership violations.

## 4. Workflows and durable documentation

- Make `doc-start` load managed harness instructions and the project index while
  respecting confirmed native loading.
- Make `doc-end` exclude both configured files from content-drift commits and
  preserve the same baseline semantics.
- Keep shared commands and Codex workflow mirrors byte-identical.
- Update the harness, scope-guard, README routing, active context, and migration
  docs to one v6 description.

## 5. Verification

- Run all Python and adapter tests, installer/mirror shell suites, diff checks,
  and the repository mechanical gate.
- Exercise fresh bootstrap and v5-to-v6 migration in disposable Git repositories.
- Exercise installed `doc-create` and `doc-start` through the real user-facing
  clients available on this machine, including verification that project
  guidance is actually loaded.
- Run independent semantic review and complete `doc-end` only after real flows
  pass.

## Outcome

- Harness v6 uses exact managed root `CLAUDE.md` and project-owned root
  `AGENTS.md`; this repository's two pre-existing project instruction sets were
  deliberately reconciled into the latter.
- The checker, scope guard, workflows, critic, installer, and Codex mirrors
  implement the same ownership contract; the obsolete v5 sidecar is absent.
- 86 Python tests, every shell suite, mirror/template comparisons, diff checks,
  and the repository mechanical gate pass.
- Installed Codex completed fresh bootstrap, explicit v5-to-v6 migration with
  real scope-guard unmark, project-instruction loading, and `doc-start`.
- One primary-session installed-Claude run loaded the `AGENTS.md` probe through
  managed `CLAUDE.md`, proving the import chain. The shell's API-key path times
  out, `claude doctor` reports HTTP 401 for managed settings, and an independent
  critic environment reports `Not logged in`; no broader authentication-health
  claim follows from the successful probe. OpenCode is not installed and
  receives no real-client portability claim.
- Final semantic review reports shape OK, zero stale claims, zero story prose,
  and one explicit unverifiable item: OpenCode's unavailable real-client path.
