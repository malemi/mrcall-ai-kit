# Extend persistent supervision to Claude Code

## Intent and boundaries

Let a dedicated Claude Code supervisor drive explicitly connected Claude root
sessions to verified completion, with the same persistent clock, memory, authority
and failure-retention semantics as Codex. Session messaging is a transport, not
proof of compliance. Preserve every current WIP artifact and previous evidence.
Do not message existing operational sessions, alter TEST-SUPERVISOR2/3, start paid
model trials, commit or release. Local dormant installation is included.

## Approach

Reuse SQLite tasks, scheduler, policy, harness inspection and control authority.
Persist runtime in the existing binding runtime field; existing bindings remain
Codex. A binding has one runtime; mixed-runtime target sets are not introduced.
Choose transports from binding identity, not a caller's guess. Support multiple
bindings of different runtimes in the same state root and preserve cron ownership.

Implement a Linux Claude adapter using live native session discovery/registry,
exact UUIDs and read-only JSONL public transcript evidence. Include worker evidence
through its verified root relationship; never expose private reasoning or invent
progress from inactivity. Preserve large tool output and report incomplete/corrupt
history explicitly. A missing or unsupported runtime must fail clearly.

Claude's inbox socket is documented, but its wire frame and transcript shape are
version-sensitive. Inspect the installed 2.1.296 implementation, gate supported
protocol/version, validate private owned paths and connected process identity,
and document that narrower support. Do not alter recipient permissions or claim
the sender is the receiver's child. A socket write is uncertain until recipient
history proves delivery; held/refused/lost sends never trigger blind resends.

## Acceptance

- Runtime identity is immutable across rebind, dispatch, reads and intervention;
  Codex's existing behavior and stored caps/history remain intact.
- Actual CLI scenarios exercise Claude activation, clock dispatch, public history,
  intervention identity, restart/reconciliation and pause/detach fences. Preserve
  failures through success. Test functional outcomes, not a scalar-validator matrix.
- Cron and install/uninstall cover Claude-only and combined delivery, custom state,
  foreign assets and dormant installation. Existing Codex checks remain applicable.
- Validate against installed native Claude without a paid model call when feasible,
  using isolated processes/state and a local model fixture if needed. Clearly
  separate protocol mechanics from unverified model supervisory judgment.
- Ship a Claude supervisor entry and update runtime-specific instructions, command
  reference, discovery docs and measured support. No automatic activation or
  creation of operational sessions. Complete reviews, doc-end and local install.
