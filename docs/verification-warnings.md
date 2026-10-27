# Verification warnings

Verification warnings report required command evidence for one explicitly
selected completion task. They reuse the existing mechanical and focused check
receipts. Missing, failed, content-changing or stale execution evidence produces
an advisory; current passing receipts and finalized historical tasks are quiet.
The advisory never executes a check or changes its completion record.

## Direct use

```sh
python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/verification-warnings/verification_warnings.py" check --repo "$repo_root" --task "$task_id"
```

The command returns zero even when it reports a warning or diagnostic. Required
completion checks remain separate and retain their existing refusal semantics.
Warnings do not grant permission, block a session or establish successful tests.

## Optional runtime notifications

The feature installs dormant. Claude Code and OpenCode expose
`/verification-warnings`; Codex exposes the `verification-warnings` skill.
The management commands are `on`, `off` and `status`. Direct registration is:

```sh
python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/verification-warnings/register.py" codex on
```

Use `claude` or `opencode` for those clients. Codex registration still requires
its native hook trust review; registration alone does not establish activation.

Each native session needs an explicit binding to its actual runtime identifier,
canonical repository, worktree Git directory and existing task:

```sh
python3 "${MRCALL_KIT_HOME:-$HOME/.config/mrcall-ai-kit}/verification-warnings/verification_warnings.py" bind --runtime codex --session "$actual_session_id" --repo "$repo_root" --task "$task_id"
```

Never substitute a lead context token for the native session ID or guess a task
from the newest record. When that ID is unavailable, use the direct check;
runtime callbacks stay silent. `unbind --runtime ... --session ...` removes the
selected binding. Repeated identical runtime warnings are suppressed; changed
diagnostics or recurrence after a quiet interval can produce another warning.

The optional installer activation flag is
`--activate-verification-warnings claude|codex|opencode|all`. Selecting the
feature or using `--yes` alone does not activate it. Registration and uninstall
preserve unrelated hook handlers and plugin configuration. Scope guard and
reread remain independent features.

## Coverage and verification

The [supervisor](supervision.md) uses these advisory diagnostics alongside the
existing completion checker. Its read-only adapter also checks content freshness
after finalization and leaves lead-context availability unverified. It neither
creates a second completion certificate nor activates these notification hooks.

Detection covers required mechanical/focused execution receipts in the selected
task. It does not parse final-answer prose, detect arbitrary undeclared tests,
authenticate an agent's honesty, force lifecycle invocation or make a missing
native binding look verified. It does not replace the explicit completion gate.

Native notification visibility and trust behavior require client-specific
evidence. Adapter fixtures and CLI acceptance establish their deterministic
behavior only; native model launches and a broad matrix remain deferred.
