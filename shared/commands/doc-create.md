---
description: Bootstrap or explicitly migrate a repository to the AGENTS-only v9 documentation harness.
allowed-tools: Bash(git *) Bash(ls *) Bash(mkdir *) Bash(cat *) Bash(python3 *) Write Edit
---

Create only missing project content, preserve existing knowledge, and use the
installed deterministic helper for managed layout changes. Write in English.
A request to bootstrap or upgrade authorizes that operation; ordinary startup,
closure, or a version mismatch does not authorize migration.

## Preflight and compatibility

This workflow implements `harness_version = 9`. Read an existing
`docs/.doc-profile` completely. A newer version stops without changes; upgrade
the installed kit. v6/v7/v8 require an explicitly requested upgrade. v9 may be
reapplied idempotently. Earlier or ambiguous layouts are unsupported: preserve
them and report the helper's refusal rather than manually guessing ownership.

Resolve `doc-migrate.py`, `doc-check.py`, `AGENTS.block.md`, and `legacy/` under
`${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}`. A source-tree run may use
`shared/scripts/doc-migrate.py` with `MRCALL_DOC_HARNESS_TEMPLATE` set to the
absolute `shared/templates/AGENTS.block.md` path. Missing assets are setup
failures. The helper imports its sibling checker and resolves historical data
beside the canonical block. Do not reproduce managed prose or remove CLAUDE
files by hand.

Run the read-only inspection with an absolute repository root:

```sh
python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-migrate.py" inspect --repo "$repo_root" --json
```

Inspection without compatibility evidence returns `ready: false` and a
nonzero exit status. Its `instruction_files` inventory binds exact ancestor
CLAUDE, root/ancestor CLAUDE.local, and user CLAUDE observations. It writes
nothing. Never modify those external instruction files.

Require a schema-1 compatibility report for every intended client and task
scope before applying migration. The report binds the real repository path,
that exact instruction inventory, required scopes, observed instruction
loading, passing lifecycle results, measured configuration, and absolute
SHA-256-bound evidence paths. `startup` and `documentation` are always required.
Use actual result artifacts; never fabricate evidence or infer lifecycle
success from a version number or loading canary. The helper validates the
finite measured version/mode policy and reports unsupported configurations.
Codex native-app-server and OpenCode run-explicit-dir support only their tested
scopes; Claude print currently fails the measured lifecycle policy. An
attestation plus matching hashes does not authenticate model behavior or block
a client that skips the lifecycle. If the required evidence is unavailable,
stop before bootstrap writes and report that missing prerequisite.

## Prepare only missing project content

For fresh bootstrap, inspect actual repository boundaries and choose explicit
`leaf` or `meta` mode. Require a Git repository with an existing commit; do not
create a commit without task authorization. An existing profile's mode must
remain unchanged. Preserve project content and optional profile settings.

Before any write, resolve ownership collisions. A foreign/customized CLAUDE,
partial/duplicate/stale managed markers, symlinked managed paths, or obsolete
sidecar is a refusal. Existing v6/v7/v8 CLAUDE must exactly match recognized
historical bytes. Do not merge ambiguous instruction sets or discard prose.

For a fresh repository, prepare these scoped documents before helper apply:

- `AGENTS.md`: project-owned operating rules and thin routing index. Preserve
  existing bytes; if absent, create only verified project facts and docs
  pointers. In meta mode, the services table lists actual child repositories.
- `docs/README.md`: thin transversal-doc router; inventory stays in AGENTS.
- `docs/active-context.md`: real baseline frontmatter and the current snapshot
  under `State now`, `Unresolved`, and `Next`. Do not invent verification.
- `docs/execution-plans/` and `docs/briefs/`, with `.gitkeep` when empty.
- Add `docs/sessions/` to `.gitignore`; do not create that runtime directory.

Each required routing document has exactly one inline declaration:

```markdown
<!-- doc-scope:start -->
Scope: <verified purpose and ownership boundary>
<!-- doc-scope:end -->
```

The helper writes the managed AGENTS block and profile; it does not generate
project prose. Fresh profiles have `harness_version = 9`, `schema_version = 1`,
explicit `mode`, and `index_file = AGENTS.md`; there is no `harness_file`.
Only add optional build/smoke or limit settings from verified project knowledge.
Keep the complete AGENTS within its configured thin-index limit; do not trim
project content merely to silence a limit. Optional titled quality/backlog
stubs are created only when useful. Substantial development keeps its dated
brief/plan pair: `docs/briefs/YYYY-MM-DD-<slug>.md` and
`docs/execution-plans/YYYY-MM-DD-<slug>.md`. Every plan uses one valid lifecycle
frontmatter status: `planned | active | blocked | completed | superseded`.

For existing documentation, the lead identifies affected project scope and
routing prose, including pointers to the retired managed CLAUDE. Reconcile those
claims within the authorized migration, then explicitly invoke doc-critic over
the affected changed and unchanged docs. The helper preserves project-owned
bytes and cannot perform that semantic decision. For living-context shape,
use doc-end's lead-owned current/historical decision and doc-critic's in-session
repair: archive historical passages verbatim and preserve current knowledge.
Keep these authorized project-prose edits separate from the helper transaction,
which owns only AGENTS, CLAUDE and profile; report their recovery limits.

## Stage, apply, and verify

After fresh preparation, inspect again to capture current collisions and the
instruction inventory. Run dry-run with the real compatibility report:

```sh
python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-migrate.py" dry-run --repo "$repo_root" --mode "$repo_mode" --compatibility "$compatibility_report" --json
```

Require `ready: true`. This stages and mechanically validates the proposed
layout without mutating repository files. Choose a new absolute transaction
directory outside repository content or below its worktree-specific Git
directory; its parent must exist. Preserve the saved transaction for recovery.
Then run the same validated operation:

```sh
python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-migrate.py" apply --repo "$repo_root" --mode "$repo_mode" --compatibility "$compatibility_report" --transaction "$transaction_dir" --json
python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-check.py" --repo "$repo_root" --startup --json
```

The helper validates before mutation, publishes the profile version last, and
removes only an exactly recognized managed CLAUDE after staging its replacement.
Report real output and changed paths. A refusal preserves ambiguous files; do
not work around it with shell edits. For interrupted migration, inspect its
saved manifest and invoke explicit rollback when recovery is required:

```sh
python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/doc-migrate.py" rollback --repo "$repo_root" --transaction "$transaction_dir" --json
```

Rollback refuses unrelated later edits. It restores transaction-owned bytes
and modes, not project prose prepared outside the transaction. Never claim a
rollback or clean gate that did not run. Mechanical success does not establish
semantic review. Hooks, global configuration, commits and release are outside
bootstrap authorization.

## Output

Report `Doc-harness v9: applied|unchanged|refused`, repository/mode, actual
created or migrated paths, compatibility outcome and limits, transaction path,
and mechanical result. Only a successful verified layout ends with
`Next: doc-start`. Preserve every refusal reason and advisory.
