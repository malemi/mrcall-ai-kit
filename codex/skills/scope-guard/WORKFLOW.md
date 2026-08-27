# Scope-guard workflow

Accept one of `on`, `off`, `status`, `unregister`, or `unmark <nonce>`. For the
first four operations, run:

```text
python3 ~/.config/mrcall-ai-kit/scope-guard/scope_guard_register.py codex <operation>
```

For unmark, run
`python3 ~/.config/mrcall-ai-kit/scope-guard/scope_guard.py unmark <nonce>` as the
agent's own deliberate follow-up action, without asking the operator.

Report the command result. `on` must leave Codex's owned `PreToolUse` hook visible
for trust review before calling it active. Do not use `ask`, request operator
approval for a guarded edit, or describe degraded mode as reason attestation:
Codex delivers the scope and denies the first exact mutation, then the agent
decides whether to retry.
