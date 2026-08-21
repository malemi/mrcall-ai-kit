---
status: active
---

# Opt-in model router + session memory + /ai-help

Brief: [../briefs/2026-08-21-cc-model-router.md](../briefs/2026-08-21-cc-model-router.md)

## Steps

- [x] `claude/agents/worker-fable.md` — new pinned worker, modeled on worker-opus.md
- [x] `claude/scripts/router-hook.py` — dormant UserPromptSubmit hook (flag-gated; Python, not bash, for stdlib JSON parsing)
- [x] `claude/commands/router.md` — `/router on|off|status|sweep|unregister`
- [x] `shared/commands/ai-help.md` — runtime inventory of installed commands/skills/agents
- [x] `install.sh` — new `router` feature (Claude Code-only, gated like orchestration/workers/migrate); help text
- [x] `shared/commands/doc-end.md` — promotion step: read `docs/sessions/<id>.md`, fold into active-context, flip to closed
- [x] `shared/commands/doc-create.md` — create `docs/sessions/` + add to `.gitignore`
- [x] `shared/commands/doc-start.md` — exclude `docs/sessions/**` from read scope (same rule as `docs/projects/**`)
- [x] `shared/scripts/doc-check.py` — validate `status: open|closed` on `docs/sessions/*.md`; advisory count of open files
- [x] `shared/scripts/tests/test_doc_check.py` — tests for the session-status check
- [x] `README.md` — "What's inside" bullet
- [x] `docs/documentation-harness.md` — session-memory contract (shape, write protocol, promotion, lifecycle)
- [x] `tests/test_router_install.sh` — sandbox install/uninstall test for the `router` feature
- [x] `codex/skills/{doc-create,doc-start,doc-end}/WORKFLOW.md` — re-synced byte-for-byte with their `shared/commands/*.md` originals (not in the original plan; `test_codex_install.sh`'s `cmp` check caught the drift)

## Remaining

- [ ] Live smoke test in a real session: `./install.sh --features router`, `/router on`, restart, `/model haiku`, verify trivial-vs-delegated routing and the session-memory write/read/promote cycle end to end. Needs a real session restart and model switch — not something this build turn can execute itself.
  - Partially attempted 2026-08-21: `/router on` and `/model haiku` were both
    run in a live session. Still open — see `docs/active-context.md`
    Unresolved/Next: the model switch could not be confirmed, and routing
    itself was never exercised because every turn had a more specific
    override in play.
