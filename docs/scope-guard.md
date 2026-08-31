# Scope Guard

This document defines the inline scope declaration introduced by documentation
harness v4, its v6 ownership model, and the contract for optional runtime
enforcement. Implementation is in progress. No runtime adapter is considered
working until it passes the installed-client acceptance flow described in the
execution plan.

## Declaration format

A declaration is a delimited block outside fenced code:

```markdown
<!-- doc-scope:start -->
Scope: A concise, non-empty statement of the document's purpose and boundary;
the text may continue on following lines.
<!-- doc-scope:end -->
```

The delimiters must occupy their own lines exactly. The content is non-empty
text beginning `Scope:` and may continue on following lines. Harness v6 requires
one block in each mechanically required routing document:

- the configured `harness_file`, the exact managed root `CLAUDE.md`;
- the configured project-owned `index_file`, root `AGENTS.md`;
- `docs/README.md`;
- `docs/active-context.md`.

Each file owns its declaration. The guard parses only the target's inline
`doc-scope` block and never consults `docs/.doc-profile` or another document for
an external scope. The v5 `doc-index-scope` sidecar format is obsolete and the
mechanical gate rejects a remaining active declaration. Non-Markdown files are
never parsed for scope markers: source code and fixtures may contain the
canonical strings as examples without becoming protected files.

Other indexed Markdown files may omit a declaration. If either delimiter or a
block appears, the mechanical gate validates it and rejects partial, duplicate,
reversed, empty, or malformed declarations. The semantic critic separately
checks that valid scope text still matches the document's actual role and is not
misleading or over-broad.

The declaration is an instruction boundary, not a claim that the guard can
decide whether an edit is semantically relevant. The agent receives the scope
and owns that judgment.

## Runtime behavior

The optional guard is installed dormant. Interactive installation asks, once
per selected runtime:

`Activate scope guard for <runtime> now (it adds a hook)?`

The default is no. Non-interactive installation requires a separate explicit
activation option; accepting ordinary installer defaults must not activate a
hook. Once active, the guard does not ask the operator for confirmation during
writes, retries, scope changes, or deliberate unmarking.

For a supported file mutation, the adapter normalizes the runtime event and the
shared engine reads the complete target. An unmarked file passes without noise.
For an existing marked file, the first attempt is denied and returns the full
scope plus a challenge. The agent decides whether to stop or retry. A later
eligible attempt can proceed according to that runtime's measured capability
level. The proposed postimage is validated before an allowed mutation so a
normal supported tool cannot silently remove, duplicate, truncate, or corrupt
the block.

The Codex adapter cannot rely on successive tool calls receiving distinct turn
identifiers. In degraded mode the engine therefore admits an identical retry
after a 200 ms boundary. Calls that arrive concurrently inside that boundary
remain denied, while the engine makes no unsupported claim that it attested the
commentary text.

Changing scope is protected as a transition bound to the exact old and new
content. Removing a declaration is a distinct challenge-based administrative
action, not an ordinary write and not a human permission prompt.

Codex's normal workspace sandbox cannot mutate guard state under
`~/.config/mrcall-ai-kit`. Its `scope-guard unmark <nonce>` command therefore
falls back to a per-user `/tmp` handoff containing only the random challenge
nonce. The host hook consumes a fresh request once, only for the exact pending
postimage, and deletes it. The handoff does not weaken ordinary writes or make
the sandbox request operator approval.

## Capability levels

- `full`: the runtime proves the required visible-reason ordering before retry.
- `degraded`: the runtime reliably delivers scope and denies the first attempt,
  but cannot attest that a model-authored reason appeared in the operator UI.
- `unavailable`: the runtime cannot safely provide the required interception
  and context path.

The label is evidence, not aspiration. Unit and fixture tests do not promote an
adapter to `full` or `degraded`; that requires a captured run through the
installed user-facing client.

## Runtime verification matrix

| Runtime | Intended intercepted tools | Current status | Required proof before release |
|---|---|---|---|
| Claude Code | Native `Write` and `Edit` pre-tool events | Unverified | Install/activate, first denial, context delivery, retry ordering, scope transition, resume, and subagent write |
| Codex | Native `apply_patch` pre-tool events, including every target in a multi-file patch | Unverified | Trust/activation, single and multi-file patches, system-message visibility, resume, code-mode call, and subagent write |
| OpenCode | `write`, `edit`, and `apply_patch` plugin events | Unverified | Compatible plugin version, error/context visibility, all mutation tools, resume, and subagent write |

Exact runtime versions and observed capability labels are recorded here only
after those tests run. Until then, this matrix deliberately makes no claim that
an adapter works.

## State and safety boundary

Per-session state belongs below
`~/.config/mrcall-ai-kit/scope-guard/state/<runtime>/<session-id>/`. Target
records use a digest of the normalized canonical path rather than a path-derived
filename. State transitions are serialized and written atomically; stale state
is cleaned within a bounded owned directory.

The Codex administrative-unmark handoff uses a mode-0700 per-user directory in
`/tmp`, rejects symlinked roots, stores mode-0600 requests under nonce digests,
and accepts only exact requests newer than five minutes. Requests are single-use.

The guard evaluates both the existing document and the proposed result. A
mutation it cannot reconstruct safely is denied. Multi-file patches are atomic
from the guard's perspective: one protected unopened or invalid target denies
the call rather than allowing other targets to conceal it.

## Known limits

Coverage is limited to the file tools each adapter explicitly intercepts. Shell
writes, direct filesystem access, MCP tools, specialized tools, or another
process may bypass that path. A new file has no pre-existing declaration to
protect. There remains a time-of-check/time-of-use boundary between a hook
decision and the runtime's write. These are documented limits, not implied
coverage.

Activation also depends on each runtime loading and trusting its registered
hook or plugin. Status output must distinguish installed, registered, active,
and measured capability; adapter failure must never masquerade as successful
enforcement.

## Harness migration

Migration to v6 is explicit through `doc-create`. A v5 migration preserves the
complete project-owned index payload in root `AGENTS.md`, replaces root
`CLAUDE.md` with the exact managed template, removes the obsolete harness
sidecar, gives both configured files their own inline declaration, swaps the
profile paths, and writes `harness_version = 6` last. It stops on a conflicting
non-empty `AGENTS.md`; it never merges repository prose heuristically or trims
the index to make the gate pass. Older repositories follow the explicit
migration chain before this v5-to-v6 transition.

`doc-start` and `doc-end` only compare versions. On an older repository they
stop and direct the operator to the explicit migration; neither workflow mutates
the repository to make its own preflight pass.
