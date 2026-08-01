# Known Issues and Solutions

Recurring problems and their fixes.

## OpenCode non hot-reloada agent files mid-session

**Sintomo**: un nuovo `*.md` creato in `~/.config/opencode/agents/` (o
copiato lì) durante una sessione attiva risulta `Unknown agent type:
<name> is not a valid agent type` quando lo si passa come `subagent_type`
al tool `task()`.

**Causa root** (verificata 2026-07-25): OpenCode carica il registry agent
a session-start e non hot-reloada. Non è un problema del model ID, del
frontmatter YAML, dei permessi o del path — è il caricamento stesso.

**Verifica**: creato un agent di controllo `worker-auto-test` con un model
NOTO funzionante (`opencode/gpt-5.4-nano`, identico al `worker-gpt`
operativo) → stesso `Unknown agent type`. Esclude ogni altra ipotesi.

**Soluzione**: riavviare OpenCode per caricare il nuovo agent nel registry.
Creare agent mid-session è inutile; pianificare l'aggiunta al prossimo
restart.

**Anti-pattern**: NON tentare workaround (ricaricare config, symlink strani,
path alternativi) — la fix è strutturale in OpenCode, richiede restart.
