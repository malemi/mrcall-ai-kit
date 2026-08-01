# Harness Backlog

Deferred doc-harness / orchestration improvements.

## ✅ DONE — Wireare OpenRouter in OpenCode per abilitare Auto Router

**Stato**: DONE (2026-07-25). Auth wired e Auto Router verificato end-to-end
tramite delega a `subagent_type="worker-auto"`. Nessuna dichiarazione provider
extra in `opencode.json` si è resa necessaria: la key in `auth.json` è bastata.

**Esito**: lo slug funzionante in OpenCode è `openrouter/openrouter/auto` (NON
`auto-beta`, che non è nel registry). Dettaglio completo in
`docs/briefs/test-worker-auto.md` e `docs/active-context.md`.

**Fonti** (verificate 2026-07-25 su docs.openrouter.ai):
- Auto Router: `https://openrouter.ai/docs/guides/routing/routers/auto-router.md`
- OpenCode integration: `https://openrouter.ai/docs/cookbook/coding-agents/opencode-integration.md`
- Latest Model Resolution: `https://openrouter.ai/docs/guides/routing/routers/latest-resolution`

## ✅ DONE — Aggiornare llms.md a meccanismi auto-aggiornanti

**Stato**: DONE (2026-07-25).

**Fatto**: aggiunta la sezione "Auto-updating mechanisms" in `llms.md` con
(1) `worker-auto` elastico su `openrouter/openrouter/auto` e (2) tabella dei 10
alias tilde-latest realmente presenti nel registry OpenCode
(`openrouter/~anthropic/claude-opus-latest`, `~openai/gpt-latest`, ecc.).
La `Selection Guide` rimanda alla nuova sezione per i casi "modello ignoto/
volatile" e "sempre l'ultima versione di una famiglia". Verificato contro
`opencode models` + doc ufficiali OpenRouter (niente fabbricazioni).
