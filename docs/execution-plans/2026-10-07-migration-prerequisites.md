---
status: active
brief: docs/briefs/2026-10-07-migration-prerequisites.md
---

# Migration prerequisite delivery

Brief approved by fresh reviewer `ses_eea95a1bcffemBOIbk14x2W1Yl`, round 2.
No commit, push or publication is authorized. Approved artifact bytes and raw
verdicts are retained outside source under `/tmp/opencode/migration-prerequisites`.

## M1 — Bounded stop and executable evidence acquisition

Lead owns doc-create source and its Codex byte copy, shared role rules and lead
stubs, generated agents, and migration CLI refusal diagnostics. One bounded
worker may own the collector/report helper, its tests, and installer wiring.

1. Add an explicit refusal boundary: prerequisite failure stops downstream
   work; kit-home and symlink targets are not downstream scope. Do not read or
   modify helper source, runtime-policy internals, installed prompts/config, or
   unrelated report/history directories. Only documented preflight/rollback
   commands are allowed; no manual managed-file edits or fabricated reports.
2. Add `doc-compat.py` with prepare/collect/report commands. `prepare` creates
   disposable minimal v9 startup/documentation fixtures outside target content,
   binds target instruction inventory and kit content hashes, and mirrors
   relevant ancestor instruction bytes under an external fixture hierarchy.
   Root layout/ownership refusals remain hard stops. User instructions remain
   ambient; target root/local conflicts are not suppressed. Preparation records
   what is tested and explicitly does not test application behavior.
3. `collect` runs current OpenCode with `run --dir ABS --format json`, using
   ambient configuration/model/guards, on separate startup and documentation
   fixtures. Preserve entire stdout/stderr/event logs, actual command, version,
   file diff and results. Timeouts and failed runs remain failed, never passing
   reports. No success is inferred from exit status or nonce echo alone.
4. A fresh semantic reviewer judges complete native results (instruction
   loading, orientation before source, no startup writes, real documentation
   reconciliation/critic/mechanical/completion evidence, application untouched).
   `report` requires an explicit APPROVED review bound to the collection hashes
   and readable full raw report. Bind schema-1 compatibility report to current
   target instruction observations and measured exact runtime/config/scopes.
   Changes to target inventory, kit instructions, raw logs or review invalidate
   the report. Rejection preserves target bytes; output goes only to the
   explicitly selected external evidence directory.
   Keep schema-1; for newly enrolled versions require an additional exact
   `environment_files` inventory checked by doc-migrate at consumption. It
   covers target/ancestor AGENTS, CLAUDE/local instructions, user Claude/Codex/
   OpenCode AGENTS, OpenCode global and target/ancestor JSON/JSONC configuration
   files and active OPENCODE_CONFIG path when present. Added/removed files change
   this inventory. Configuration contents are hashed, not printed or copied into
   reports; relevant ancestor instruction files are mirrored byte-for-byte in
   the probe hierarchy. Every present bound input, kit workflow/helper/block,
   native log, collection manifest, and semantic review is an evidence[]
   absolute-path/SHA-256 reference so the existing consumer checks its bytes.
   Old measured-version reports remain on their existing bounded contract;
   new versions require the extended inventory and explicit preflight evidence.
   Refuse preflight when OPENCODE_CONFIG_CONTENT/OPENCODE_CONFIG_DIR or target/
   ancestor `.opencode` overrides are present until those sources are explicitly
   supported; never silently run a differently configured probe.
5. Install the helper under kit-home. Document prepare/collect/review/report
   before helper dry-run/apply, and stop when any step refuses. Retain old
   0.160.0/1.18.32 policy entries. Current versions are not enabled until M2
   native evidence passes. Codex needs separate native-app-server evidence;
   collect/report must not label `codex exec` as that mode.
6. Verify CLI fixtures, invalidation/refusal cases, workflow-copy identity,
   generator synchronization and installer source completeness. Integration
   review before M2.
   No-evidence/unsupported-version JSON includes a machine-readable
   `next_action`: use only installed doc-compat prepare/collect/review/report;
   on failure stop, never inspect/edit kit internals. Test this for absent
   report and the two current versions before enrollment. Test helper dry-run
   no-write refusal after each bound-input change, including additions/removals.

## M2 — Current-client proof, bounded policy update and closure

0. Before installed-path trials, back up affected installed kit-owned paths and
   manifest outside source. First refresh affected physical Codex role copies
   (and workflow copies if any), verifying each preimage against its most recent
   installed.tsv ownership hash. Preserve/refuse foreign preimages. This happens
   before installer preflight because skip-mode refuses stale Codex copies.
   Then run `./install.sh --environment all --features
   doc-harness --mode symlink --on-exist skip --yes --dry-run`, then the same
   real command: this installs missing helper assets, preserves existing owned
   symlinks/copies, foreign files and activation. Require a successful dry-run
   before the real command.
   Freeze instruction/helper bytes before collection; any later relevant edits
   require recollection rather than relabeling old observations.
1. Run the installed helper acquisition path on disposable recognized v8
   targets. Real target repositories remain unchanged. Native trials are
   bounded to startup/documentation; no model/client config or guard changes.
2. After independent evidence approval, enroll exact OpenCode 1.18.34 for
   startup/documentation only. If trials fail, repair in-scope collector defects
   and retry; behavioral/provider failures remain honestly unsupported. Inspect
   Codex 0.160.1 feasibility; do not enroll without native-app-server evidence.
3. Compile a real target-bound report; installed doc-migrate dry-run/apply,
   installed checker and exact rollback must succeed on a disposable v8 target.
   Missing/stale/failed/wrong-target evidence and unsupported modes/scopes remain
   no-write refusals. Relevant regression suite plus real CLI path are required.
4. Update runtime support and harness contracts, changelog, and living context
   without historical loss. Refresh affected kit-owned installed artifacts with
   foreign/config preservation; record that sessions need restart.
5. Initialize development completion only after frozen checker/workflow edits.
   Retain brief/plan/M1/M2 approved bytes and actual raw verdicts; record all
   applicable evidence, mechanical/focused/critic/shape and pre-review check.
   Fresh separate final review with approved-version comparison precedes full
   completion check and finalize. Declare active-to-completed plan transition;
   do not hand-edit baseline/status metadata. No commit/push/release.

## Risks and rollback

Native failures may reflect quota, ambient instruction shadowing, scope guards,
or model noncompliance. Those do not authorize bypass or source exploration by
downstream agents. Mirrored fixtures measure only a finite configuration; exact
target binding and raw evidence references are not authenticated proof of model
judgment. Migration publication/rollback code is unchanged. Installer changes
are backed up; all source changes remain local and independently revertible.

## State

Plan approved by reviewer `ses_eea9189e8ffeK7YAeRc9y41JRZ`, round 3.
Review text recovered from the OpenCode database is retained under
`/tmp/mrcall-migration-resume`; original immutable approved artifacts were not
recovered. M1 integration and final reviews remain pending.

Operator scope correction on 2026-10-07: enable current clients immediately
and defer tests. `--allow-unverified` now explicitly skips compatibility report
validation while retaining ownership/staging/publication/rollback checks;
the transaction records that verification is deferred. Current version
identities are accepted on the strict path with extended environment evidence.
The Codex doc-create installed workflow was refreshed with the option.
No native compatibility claim, downstream migration, commit or release is made.
Collector hardening and later migration tests remain unexecuted. The earlier
migration suite completed before deferral (15 tests passed); this does not
verify the subsequent operator-deferral change. Baseline is not advanced.
