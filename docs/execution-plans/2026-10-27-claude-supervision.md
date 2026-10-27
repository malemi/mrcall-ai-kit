---
status: completed
---
# Claude supervision delivery

Brief: ../briefs/2026-10-27-claude-supervision.md
Evidence and before bytes: `/tmp/claude-supervisor-20261027/` (retain).

## M1 — Adapter and runtime integration

After plan approval, an execute worker owns only claude/supervision/transport.py
and focused adapter tests. The lead owns shared supervision store/scheduler/CLI/
cron integration, install routes, skill and documentation. These responsibilities
are independent until integration review; nobody reverts other WIP.

Use native `claude agents --json` to identify live root sessions, then the matching
owned ~/.claude/sessions/<pid>.json record for socket and protocol metadata. Honor
CLAUDE_CONFIG_DIR. Gate the inspected Linux 2.1.296/peerProtocol 1 surface; reject
unsupported layouts/versions instead of guessing. Validate live PID/start identity,
private socket and connected SO_PEERCRED identity before sending. Do not send an
own-child token, claim a permission mode, or modify recipient inbound controls.
The native newline-JSON user frame includes a stable event UUID and an explicit
ai-kit marker. Socket submission alone returns uncertain. Reconcile only a public
recipient user-message marker from its transcript, never an assistant quote or
missing/incomplete history. No automatic second submission after uncertainty. Add explicit `execution-reconcile
--id` for a supervisor awakened before its receipt is confirmed: inspect the same
active generation/event in history, grant normal authority only after delivery
evidence, and never submit another message. Explicit `execution-reconcile` and
`intervention-reconcile` may recheck later evidence after an earlier inconclusive
reconciliation; the existing automatic one-shot recovery remains bounded. Preserve
each observation in audit history. Both commands reject paused/detached/stale
authority. `execution-read` remains read-only. Functional checks include immediate
wake, delayed approval after inconclusive reconciliation, and paused/detached refusal.

Read exact-root JSONL transcripts under the configured Claude projects directory,
including public text/tool calls/results and lifecycle evidence, excluding private
reasoning recursively. Return explicit root-linked subagent transcripts under the
root's subagents directory as worker evidence; workers are not intervention targets.
Use validated cursor anchors that detect rewrites, partial records and truncation.
Retain full public tool outputs. Reject unsafe paths, ambiguous roots and corruption.
An unavailable/incomplete read cannot establish absence or successful completion.

Persist runtime in the existing binding field, defaulting old calls to Codex;
include runtime in immutable binding identity. Select transport from the bound
runtime for tick, activate, session-read, transport-read and intervene. Keep injected
test transports supported. Add --claude-path without changing --codex-path behavior.
Cron retains exact absolute executable/config paths for both available runtimes;
owned-command parsing must recognize old and new entries and preserve foreign ones.
No mixed-runtime targets within one binding; different bindings may share state.

Install the Claude adapter and Claude supervisor skill through supervision, with
both adapters available to the shared CLI and runtime-selected skill destinations.
OpenCode supervision remains unsupported. Installation stays dormant; uninstall
retains owned-state deactivation and foreign-file protections. Existing private
runtime setup remains reusable; no independent scheduler or memory store.

## M2 — Real checks and local delivery

Review M1 integration before dependent installation. Use a few functional CLI/socket
scenarios for dispatch→uncertainty→history reconciliation, duplicate prevention,
wrong/runtime-stale identity, public root/worker history with large output and
failure preservation, and pause/detach authority. Reuse existing Codex/cron/install
checks where their behavior is affected, avoiding trivial validator matrices.

Inspect the actual installed native frame/registry implementation and retain the
version/source evidence. When feasible, run an isolated native CLI with a local
model endpoint fixture or held inbox to validate mechanics without paid calls.
Never target existing operational sessions or alter their permission settings.
Report native model supervisory judgment as unverified. If a native interface
contradicts the adapter, repair the adapter and affected checks before delivery.

Install the integrated source locally for Codex and Claude, preserving unrelated
assets and existing supervision state/cron. Do not activate a supervisor session.
Retain complete logs, initial failures, source hashes and actual exit results.

## Closure and rollback

Reconcile docs/supervision.md, shared/supervision/{POLICY,COMMANDS}.md, supervisor
skill entries, README, docs index and runtime discovery/help/tutorial as affected.
Active context remains a living snapshot; archive only displaced historical text
verbatim. Apply doc-end, mechanical gate, explicit doc-critic, separate final review,
and checker finalization for active→completed. No release/commit/push.
Restore only task-owned changes from before bytes if rollback is needed. Keep old
Codex bindings and unresolved failures intact; do not reset the working tree or
clean evidence directories. Preserve pending obligations in this plan on interruption.
