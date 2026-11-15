# Debugger agent

## Intent

Add a spawnable `debugger` specialist to AI-KIT. The operator's debugging
instruction is to take the actual failing data and follow what the software
does, function by function, until the first demonstrated divergence. A familiar
error label or a passing unit test is not a causal explanation.

## Scope

Ship one canonical diagnostic role through the existing Claude Code, Codex and
OpenCode agent generation and installation paths. Keep diagnosis distinct from
`execute` implementation, `verify` truth checks and `reviewer` lifecycle gates.
The debugger is a leaf, read-only investigator: it may run authorized diagnostic
commands and report evidence, but does not modify product code, configuration
or production data. Destructive, paid or externally visible reproductions need
explicit authority and a bounded allowance.

The role records concrete input, branch/predicate, transformation, output or
exception and downstream consumer for the relevant failing path. It separates
observed execution, exact replay, source reconstruction and counterfactuals;
tracks the original failure through wrappers and cleanup; names missing evidence;
and selects the smallest decisive next check. Trace detail goes in scratch,
with a concise causal handoff to the lead. Missing payloads stay missing rather
than being silently replaced by today's state.

Preserve existing protections. No speculative increases to timeouts, context or
budget, weakened authority checks, or repeated paid calls without new evidence.
Account for shared deadlines and successful operations before attributing a
timeout to a provider. Protect secrets and sensitive case data in reports.

## Constraints

- Preserve the working tree's existing supervision changes.
- Use canonical role sources and generated profiles, never hand-edit renderings.
- Codex inherits the session model. Other runtimes use budget resolution with
  the same selection requirements as `verify`; reuse the recorded selection
  when equivalent, without a catalogue refresh or a hand-picked model.
- Reuse valid evidence; bound delegated work and live acceptance. No release,
  production debugging, supervision restart or unrelated cleanup is authorized.

## Acceptance

1. `debugger` is generated and installed/discoverable through all three supported
   runtime paths, with existing common/report rules and explicit diagnostic scope.
2. Model resolution, installer inventories and role-routing documentation agree.
3. Generated parity, relevant installation and resolution regressions pass.
4. A real native Codex invocation loads the installed debugger and diagnoses a
   deterministic local failing case, showing the first divergence rather than
   blaming its misleading outer error. Evidence distinguishes what was run from
   reconstructed behavior. This proves a bounded sample, not general reliability.
5. Fresh lifecycle reviews and documentation closure pass; runtime limitations
   remain explicit. No claim of a fixed product bug is made by creating a role.

## Assumptions

The existing role layer is the correct distribution mechanism. Read-only is a
task boundary reinforced by runtime permissions where supported, not a guarantee
that arbitrary shell diagnostics have no side effects. The earlier question
about roles actually used in PROBLEMI3 remains a separate, deferred audit.
