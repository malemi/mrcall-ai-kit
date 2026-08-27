---
status: active
---

# Scope guard: execution plan

Brief: [../briefs/2026-08-26-scope-guard.md](../briefs/2026-08-26-scope-guard.md)

## Outcome and non-goals

Build an opt-in scope guard with one shared scope/state engine and a thin adapter
for each runtime. A marked routing document must put its declared scope back into
the model context immediately before a supported write. Where the runtime exposes
enough ordered UI and tool events, the first write in a session must also remain
blocked until the agent has stated a non-empty reason in operator-visible text.

This remains a mitigation, not a semantic classifier or a filesystem security
boundary. It does not decide whether an edit is relevant. It does not cover writes
performed outside the runtime's intercepted file tools, and the product docs must
name those bypasses instead of turning partial coverage into a guarantee.

## Decisions fixed by this plan

### Activation remains explicitly opt-in

The standing contract in `docs/active-context.md` remains intact: installing the
kit must not register or activate hooks for the user.

- Add `scope-guard` as an explicit installer feature for Claude Code, Codex, and
  OpenCode. Installation places the common engine, dormant adapters, and the
  runtime's activation command/skill under kit-owned paths.
- In an interactive install, after the feature and target runtimes are selected,
  ask separately for each selected runtime: `Activate scope guard for <runtime>
  now (it adds a hook)?` The prompt names the settings or plugin registration it
  will add and defaults to `no`. Answering `yes` is the explicit opt-in that permits
  `install.sh` to register that runtime's adapter immediately; declining leaves
  the installed adapter dormant.
- A non-interactive install never infers activation from `--yes` or from merely
  selecting `--features scope-guard`. It requires a separate explicit activation
  flag naming the selected runtime(s), and `--dry-run` shows both artifact
  installation and every proposed registration without writing either.
- `scope-guard on` remains the later activation path for a runtime declined or
  installed non-interactively without activation. Both installer activation and
  `scope-guard on` call the same registration helper, show the exact hook/plugin,
  merge only entries carrying the kit's stable identity, and are idempotent.
  Codex must also surface its native hook trust-review step; registration is not
  reported as fully active until the hook is trusted and visible in `/hooks`.
- `scope-guard off` removes or disables the active registration, rather than only
  setting a flag that leaves an undocumented active hook. `scope-guard status`
  distinguishes installed, enabled, enabled-but-untrusted, and broken. An
  `unregister` verb removes the exact owned registration and no sibling settings.
- `uninstall.sh` detects an active owned registration and removes it through the
  same idempotent unregister implementation before deleting installed artifacts.
  Backup/restore and duplicate-manifest behavior receive tests; hand-edited or
  foreign hook entries are never removed by substring guessing.

### The scope has one parseable source

Use a visible Markdown block delimited by exact HTML comments, not a second YAML
field beside prose:

```markdown
<!-- doc-scope:start -->
Scope: This document is the living snapshot of current repository state; it does
not retain session history or per-repository detail owned elsewhere.
<!-- doc-scope:end -->
```

The text between the markers, including the `Scope:` line, is the only source.
It renders as ordinary prose, while the markers give the checker and runtime
engine an exact UTF-8 format. A document may contain either zero or one block;
empty, duplicated, nested, reversed, or unterminated blocks are invalid. The
engine reads the complete file and never infers scope from filenames or headings.

The mechanically required routing set is exactly the configured `index_file`,
`docs/README.md`, and `docs/active-context.md`. `doc-create` stamps a purpose
appropriate to each generated file. A v3-to-v4 migration wraps an already-valid
purpose sentence where one exists or asks the operator to approve newly authored
scope text; it must not preserve an unmarked duplicate sentence. Other documents
may opt in by adding the same block, but the gate does not require them.

### Reason-visible-before-write is a capability, not an assumption

The brief's deny-once/retry sequence alone proves only that the model received a
request for a reason. It neither observes nor requires an operator-visible reply.
Implementation therefore starts with the runtime spikes below and records the
result in a capability matrix. No adapter may claim the stronger guarantee until
its real client test proves this protocol:

1. On the first supported write to a scoped canonical path, atomically create a
   challenge keyed by runtime, `session_id`, and canonical path; return the full
   scope, a random nonce, and the exact required line
   `Scope reason <nonce>: <non-empty reason>`, and deny the write.
2. An adapter with an official assistant-display/message event accumulates whole
   assistant messages by the event's message identifier. Only an exact challenge
   nonce plus non-empty reason in assistant text visible in the main operator UI
   attests the challenge. Tool output, hook output, transcript scraping, hidden
   context, and subagent-only text do not count.
3. A retry remains denied until attested. Once attested, the adapter atomically
   opens that session/path and the supported write may proceed. Every later write
   still receives the current scope as context, so opening state never suppresses
   scope delivery.
4. Before allowing a supported mutation of a currently scoped target, reconstruct
   the complete proposed post-write content from `Write`, `Edit`, or `apply_patch`
   input. Removing the block, making it malformed, or producing more than one
   block is denied even when that session/path was already open. A write cannot
   make its next write silently appear unmarked.
5. A valid scope-text change is a distinct transition, not an ordinary open-state
   write. Deny the first attempt with both old and proposed scopes and create a
   challenge bound to canonical path, old scope digest, proposed scope digest, and
   proposed content digest. In full mode, only acknowledgement of the proposed
   scope opens that exact transition; the retry is allowed only while the on-disk
   old digest and proposed content digest still match. In degraded runtimes, the
   first scope-change attempt is denied with the old scope, proposed scope, nonce,
   and a request for a stated reason. After an intervening model turn, one exact
   retry of the recorded old digest, proposed scope digest, and proposed content
   digest is allowed. The adapter cannot prove that the reason was operator-visible
   and must label this weaker guarantee honestly, but it never replaces that gap
   with a human permission prompt. The agent owns the proceed/stop decision. After
   the atomic write, discard the old open record and record the new scope as
   acknowledged, leaving no unguarded interval.

Normal runtime file tools never remove a scope block from an already scoped file.
Deliberate unmarking is a distinct agent-visible action outside the ordinary write
flow: the first removal is denied with the current scope and a nonce; only a later
exact `scope-guard unmark <challenge-nonce>` transition may remove it. This is a
second deliberate agent action, not a human permission prompt. Status and audit
output must make the resulting loss of coverage explicit.

The install-time opt-in is the only routine human consent introduced by this
feature. Once enabled, the guard must never use `ask`, open a permission dialog, or
require operator confirmation for ordinary writes, scope changes, retries, or
unmarking. It supplies the boundary and forces a separate decision point; the
agent decides whether to continue.

If event ordering cannot be proven, that adapter ships only the weaker
`scope-delivered + first-attempt-denied` mode and says so. Transcript parsing is
not an acceptable fallback: Codex explicitly documents `transcript_path` as a
convenience whose file format is not stable, and no runtime's private transcript
schema becomes part of this feature's contract.

## Runtime capability matrix to implement and verify

| Runtime | Supported interception target | Context delivery and blocking | Visible-reason status before spike | Known bypass/limit |
|---|---|---|---|---|
| Claude Code | Native `Write` and `Edit` through `PreToolUse` matcher `Edit|Write` | Official `additionalContext` plus `permissionDecision: deny`; `file_path` is absolute | Candidate for full mode using official `MessageDisplay`; must prove display-before-retry ordering in interactive mode and behavior in subagents | Bash/MCP/direct filesystem writes are outside this matcher; current hook input does not provide a reliable subagent identity on every `PreToolUse` call |
| Codex | `apply_patch` through `PreToolUse` (matcher aliases `Edit|Write`); parse every patch header and target | Official deny, `permissionDecisionReason`, `additionalContext`, and UI/event `systemMessage` | Degraded unless a stable official assistant-display event appears: `systemMessage` can show hook text, but does not prove a model-authored visible reason | Specialized tools may bypass the local hook path; Bash and direct writes are not inferred from shell prose; subagents share parent `session_id`; hook trust can leave an installed adapter inactive |
| OpenCode | Stable v1 plugin `tool.execute.before` for `write`, `edit`, and `apply_patch`; v2 only if the compatibility spike selects and pins it | A before-hook can fail the tool operation; model-visible error/context behavior must be measured | Gated: neither current stable docs nor beta v2 docs establish a Claude-equivalent ordered display event | Bash is a separate permission/tool path; plugin API v2 is beta; `apply_patch` paths live in structured patch markers, not `filePath` |

Official references to re-check at implementation time:

- [Claude Code hooks](https://code.claude.com/docs/en/hooks): `PreToolUse`,
  absolute `Write`/`Edit` paths, `additionalContext`, deny decisions,
  `MessageDisplay`, common session fields, and subagent event fields.
- [Codex hooks](https://learn.chatgpt.com/docs/hooks.md): native hook locations
  and trust, `PreToolUse`, `apply_patch` aliases, `systemMessage`, tool coverage,
  shared subagent session IDs, and the unstable-transcript warning.
- [OpenCode tools](https://opencode.ai/docs/tools) and
  [OpenCode v2 plugins](https://v2.opencode.ai/docs/build/plugins/): stable tool
  argument shapes and the beta before-hook contract.

## State and path contract

- The common engine accepts a normalized event object from adapters; it never
  branches on undocumented raw payload details. Runtime adapters own extraction
  of tool name, session/turn/message identifiers, targets, and output schema.
  Python adapters import it directly; the OpenCode TypeScript adapter invokes its
  JSON-lines CLI as a short synchronous subprocess, so it does not reimplement the
  parser or state machine in a second language.
- Validate `session_id` as a bounded filename-safe token, but never use the target
  path as a state filename. State lives below
  `~/.config/mrcall-ai-kit/scope-guard/state/<runtime>/<session-id>/`; each target
  record is named by a SHA-256 digest of the normalized canonical path and stores
  the path, scope digest, challenge nonce, phase, and timestamps as JSON.
- Resolve supported existing targets to an absolute canonical path before lookup,
  following symlinks once through the platform path API. Reject invalid payloads
  safely. A new file has no pre-existing scope declaration and is therefore not
  guarded until a marked document exists; document this explicitly.
- For an existing scoped target, evaluate both preimage and proposed postimage.
  `Write` supplies the full postimage; `Edit` must apply its exact replacement
  semantics in memory and deny if the preimage cannot be reproduced unambiguously;
  `apply_patch` must apply the complete structured patch to disposable in-memory
  content before deciding. If an adapter cannot determine the postimage, it denies
  the mutation instead of allowing a possible marker removal. The marker invariant
  is evaluated independently for every target in a multi-file call.
- Parse `apply_patch` using its structured patch grammar and collect every Add,
  Update, Move-from/Move-to, and Delete target. Never use prose regexes or inspect
  only the first target. A multi-file call is denied if any existing scoped target
  is unopened, and the response lists every affected scope/challenge without
  allowing unrelated targets in the same call to slip through. Deleting or moving
  a scoped target is a protected removal: deny it in the normal tool flow. A move
  can be supported later only as one atomic administrative transition that proves
  the destination retains the same valid block and transfers state without a gap.
- Serialize state transitions with a portable atomic lock-directory protocol and
  atomic temp-file replacement in the same directory. A concurrent first call
  cannot observe a half-written record or turn the other call's denial into an
  allow. Recover only locks older than a documented short timeout.
- Remove session state on official `SessionEnd` where available. Also perform lazy
  TTL cleanup with a fixed maximum age, bounded per invocation; inspect only
  regular files below the owned state root, never follow symlinks, and tolerate
  cleanup failure without changing the current decision. `off`, `unregister`, and
  uninstall remove only this feature's owned state.
- Missing files, malformed JSON, unreadable/non-UTF-8 files, unknown tools, and
  adapter failures have an explicit tested result. Ordinary unmarked files remain
  noiseless. A scoped document whose block is malformed is denied with a repair
  message rather than silently treated as unscoped. The documentation must call
  out the remaining hook/tool and TOCTOU limits.

## Execution sequence

### 0. Prove runtime primitives and freeze the guarantee

- [ ] Create disposable scoped fixtures and run the installed, user-facing clients
  for Claude Code, Codex, and OpenCode, recording exact runtime versions.
- [ ] Claude: register temporary `PreToolUse` and `MessageDisplay` probes; verify
  `Write` and `Edit` payloads, scope/error delivery, display batch ordering before
  a retrying tool call, interactive vs `-p`, resume, parallel calls, and a real
  subagent write. Determine whether a subagent reason is actually visible in the
  parent UI. If it is not, scoped subagent writes must stay denied and return the
  proposed edit/reason to the parent for an operator-visible parent write.
- [ ] Codex: verify current native hooks in CLI/app, trust flow, `apply_patch`
  payloads with one and several files, code-mode nested calls, `systemMessage`
  visibility, resume, and subagent calls. Confirm that no stable event can attest
  assistant-visible text before keeping Codex in degraded mode.
- [ ] OpenCode: test the stable v1 plugin API already compatible with this kit and
  compare the installed runtime with beta v2. Select v1 unless a needed capability
  exists only in v2 and a minimum-version/compatibility failure can be made clear.
  Verify `write`, `edit`, and `apply_patch` inputs, thrown before-hook errors,
  message visibility, resume, parallel calls, and subagent behavior.
- [ ] Record the measured capability matrix and version floors in the durable
  `docs/scope-guard.md`. If no runtime can enforce operator-visible reason safely,
  revise the brief's guarantee before implementation proceeds; do not silently
  implement deny-once and call the gate solved.

Acceptance gate: each matrix cell cites an official primitive and a captured real
client observation. Full mode is enabled only where the nonce protocol is proven;
the other adapters have explicit degraded labels and tests for exactly that mode.

### 1. Implement the common engine

- [ ] Add `shared/scripts/scope_guard.py` with the scope-block parser, canonical
  target model, patch-target parser, challenge state machine, locking, cleanup,
  and runtime-neutral decisions (`ignore`, `deny`, `allow`) carrying scopes and
  capability labels.
- [ ] Add `shared/scripts/tests/test_scope_guard.py` covering absent/valid/empty/
  malformed/duplicate blocks; full-file parsing; Write/Edit targets; multi-target
  patch grammar; absolute/relative paths; `..`; symlinks; scope changes; malformed
  IDs/payloads; parallel first calls; stale locks; TTL cleanup; and state-root
  symlink attacks. Include an already-open target whose proposed `Write`, `Edit`,
  or `apply_patch` removes, duplicates, truncates, or malforms the block; valid
  old-to-new scope transitions bound to exact content; stale/replayed transition
  challenges; delete/move attempts; and multi-target patches where only a later
  target alters its marker.
- [ ] Ensure core output never claims semantic relevance and never logs document
  content or reason text outside the minimal per-session record required by the
  protocol.

Acceptance: the common tests pass under the repository-supported Python, two
concurrent first calls cannot both pass, and changing only the scope block forces
a new acknowledgement bound to the exact transition. No supported normal tool can
turn a currently scoped file into an unmarked or malformed file, including after
the session/path was already opened.

### 2. Build and test the runtime adapters

- [ ] Add `claude/scripts/scope-guard-hook.py` and
  `claude/commands/scope-guard.md`. Register only the proven event set. Cover both
  `Write` and `Edit`, dormant/unregistered state, malformed input, full/degraded
  mode selection, and the decided subagent hand-back behavior.
- [ ] Add `codex/scripts/scope-guard-hook.py` and
  `codex/skills/scope-guard/{SKILL.md,WORKFLOW.md}`. Use native hook JSON and
  trust review, map `apply_patch` aliases without pretending Codex sends Claude's
  `file_path`, and surface the degraded capability in status and `systemMessage`.
- [ ] Add `opencode/plugins/scope-guard.ts` plus
  `opencode/commands/scope-guard.md`, pinned to the selected stable API/version.
  Handle `write`, `edit`, and every path in `apply_patch`; refuse startup with a
  useful version error rather than loading an incompatible beta adapter.
- [ ] Add adapter fixture tests that feed complete official event shapes and assert
  exact runtime output/error schemas. Add explicit bypass tests showing Bash/direct
  filesystem writes are not intercepted, so later docs cannot claim otherwise.
  For Claude `Write`/`Edit`, Codex `apply_patch`, and OpenCode `write`/`edit`/
  `apply_patch`, assert denial of marker removal/malformation and correct handling
  of an exact scope transition. Multi-target fixtures must put the protected target
  first, middle, and last so ordering cannot hide it.

Acceptance: every supported file tool is intercepted before mutation; unmarked
files are silent; adapter failures do not masquerade as successful enforcement;
subagents cannot use a shared parent session key to skip an unopened scope; and no
adapter emits an `ask` decision or opens a human permission prompt.

### 3. Wire opt-in installation, activation, and removal

- [ ] Extend `install.sh` help, validation, plan building, copy/symlink modes, and
  manifest records for `scope-guard` in all selected environments. In interactive
  mode, ask per runtime whether to activate it now, defaulting to no and previewing
  the exact registration. In non-interactive mode require an activation flag that
  is distinct from `--features scope-guard`; `--yes` alone must never activate a
  hook. A declined install places no adapter in an active hook/plugin location.
- [ ] Implement one shared, idempotent settings-registration helper used by
  installer opt-in and the three later activation entrypoints. Identify owned
  entries structurally, preserve all foreign JSON/TOML/plugin configuration, use
  atomic writes and backups, and detect duplicates from interrupted or repeated
  activation.
- [ ] Extend `uninstall.sh` to unregister owned active entries before artifact
  removal and report whether restoration is possible. Exercise reinstall,
  `--on-exist` policies, `--dry-run`, backup restore, missing files, broken links,
  duplicate manifest lines, and on/off/unregister cycles.
- [ ] Add `tests/test_scope_guard_install.sh`; keep
  `tests/test_codex_install.sh` discovery assertions and existing router install/
  uninstall behavior green. Assert the exact interactive prompt
  `Activate scope guard for <runtime> now (it adds a hook)?`, its default-no
  behavior, explicit yes, non-interactive activation flag, and the rule that
  `--yes` without that flag remains dormant.

Acceptance: declining the installer prompt, or running non-interactively without
the separate activation flag, changes no runtime hook registry. An explicit `yes`
inside the interactive installer and the later activation command produce the
same owned registration. `off`/`unregister` and uninstall remove exactly owned
state while unrelated hooks survive byte-for-byte.

### 4. Extend the documentation harness and migrate to v4

- [ ] Bump the embedded harness protocol from v3 to v4 in
  `shared/commands/{doc-create,doc-start,doc-end}.md`, all three matching
  `codex/skills/*/WORKFLOW.md` files, `shared/skills/doc-critic/SKILL.md`,
  `shared/scripts/doc-check.py`, and tests. Provide an explicit v3-to-v4 migration;
  never mutate repositories implicitly at session start/end.
- [ ] Update `doc-create` fresh templates and migration instructions to add one
  canonical scope block to the required routing set without duplicating existing
  purpose prose. Preserve byte-for-byte equality between each shared `doc-*`
  command and its Codex `WORKFLOW.md` copy, enforced by
  `tests/test_codex_install.sh`.
- [ ] Extend `doc-check.py` to require exactly one valid non-empty block on the
  configured index, `docs/README.md`, and `docs/active-context.md`; validate
  optional blocks everywhere else; detect duplicates/malformed delimiters; and
  add focused cases to `shared/scripts/tests/test_doc_check.py`.
- [ ] Extend `doc-critic` to compare each changed declaration with the document's
  actual routing role/content. It reports stale, misleading, or over-broad scope
  as semantic drift; when run in-session it repairs only with transcript-backed
  knowledge, and when delegated it reports rather than inventing a purpose.
- [ ] Update `docs/documentation-harness.md`, add `docs/scope-guard.md`, route it
  from `docs/README.md`, and update `README.md`. On implementation completion,
  reconsolidate `docs/active-context.md`; do not record the feature as working
  until the real-client acceptance tests below pass.

Acceptance: fresh bootstrap and an explicitly approved real v3 migration both
produce one source per routing file; the mechanical gate catches format errors;
the critic catches a syntactically valid but semantically stale declaration; all
shared/Claude/OpenCode and Codex duplicates are synchronized deliberately.

### 5. Verify as users actually run it

- [ ] Run Python unit tests, shell syntax checks, all install suites, and the local
  mechanical gate. These are prerequisites, not proof that the feature works.
- [ ] Claude Code interactive TUI: install and activate through the shipped
  command, inspect `/hooks`, attempt real `Write` and `Edit` operations against a
  marked fixture, observe the first denial and full scope, verify that retry before
  a visible nonce reason is denied in full mode, then state the reason and verify
  the write. From an already-open path, attempt marker removal and malformation via
  both tools and verify the file remains unchanged; then complete one explicit
  old-to-new scope challenge and verify there is no unguarded retry between them.
  Repeat after resume and through a real subagent.
- [ ] Codex CLI/app: install, activate, complete `/hooks` trust review, and make a
  real single- and multi-file `apply_patch`. Verify scope delivery, denial count,
  `systemMessage`, resume, code mode, and subagent behavior. Report it as degraded
  unless the Phase 0 gate proved visible-reason attestation. Attempt marker removal,
  malformed replacement, delete/move, and a scope change in both single-target and
  multi-target patches; none may create an unmarked window.
- [ ] OpenCode TUI: install/activate the selected plugin version and perform real
  `write`, `edit`, and multi-file `apply_patch` calls, plus resume and subagent
  cases. Attempt marker removal/malformation with every supported mutation tool and
  complete the permitted scope-change path. Verify operator/model error visibility,
  unchanged files after denial, and label the resulting mode from Phase 0 evidence.
- [ ] In every runtime, demonstrate one documented bypass (for example a shell
  write) against a disposable fixture so the final capability matrix is based on
  observation, not omission. Restore all user settings from backups and remove
  disposable state after the test.

Final acceptance: no adapter is called "working" from unit tests alone. The three
real clients have been exercised through the same install/activate/write flow an
operator uses; the durable matrix records versions, supported tools, subagent
behavior, bypasses, and whether visible-reason attestation is full, degraded, or
unavailable.

## Expected files

New files:

- `shared/scripts/scope_guard.py`
- `shared/scripts/tests/test_scope_guard.py`
- `claude/scripts/scope-guard-hook.py`
- `claude/commands/scope-guard.md`
- `codex/scripts/scope-guard-hook.py`
- `codex/skills/scope-guard/SKILL.md`
- `codex/skills/scope-guard/WORKFLOW.md`
- `opencode/plugins/scope-guard.ts`
- `opencode/commands/scope-guard.md`
- `tests/test_scope_guard_install.sh`
- `docs/scope-guard.md`

Expected modifications:

- `install.sh`, `uninstall.sh`, `README.md`
- `shared/commands/doc-create.md`, `shared/commands/doc-start.md`,
  `shared/commands/doc-end.md`
- `codex/skills/doc-create/WORKFLOW.md`,
  `codex/skills/doc-start/WORKFLOW.md`, `codex/skills/doc-end/WORKFLOW.md`
- `shared/skills/doc-critic/SKILL.md`
- `shared/scripts/doc-check.py`, `shared/scripts/tests/test_doc_check.py`
- `tests/test_codex_install.sh`, `tests/test_router_install.sh` only where shared
  installer/uninstaller behavior changes their existing assertions
- `docs/documentation-harness.md`, `docs/README.md`, `docs/active-context.md`

The brief is not changed by planning. If Phase 0 disproves its strong visibility
claim for a runtime, changing that claim is an explicit gated design decision
before implementation, not an incidental plan edit.
