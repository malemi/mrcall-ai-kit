---
description: Manage the opt-in scope guard for Claude Code
allowed-tools: Bash(python3 *)
---

For `on`, `off`, `status`, or `unregister`, run
`python3 ~/.config/mrcall-ai-kit/scope-guard/scope_guard_register.py claude $ARGUMENTS`
and report its output exactly. For an unmark challenge, run
`python3 ~/.config/mrcall-ai-kit/scope-guard/scope_guard.py unmark <nonce>`.
This is the agent's own deliberate follow-up action; never turn it or an ordinary
scope decision into an operator permission question.
