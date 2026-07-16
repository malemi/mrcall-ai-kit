# Review: skill `orchestrator`

**Date:** 2026-07-11  
**Scope:** `SKILL.md`, `ARCHITECTURE.md`, `memory.md`, `llms.md`, agent `orchestrator` / `reviewer` / workers, allineamento con `AGENTS.md` + tool reali OpenCode  
**Overall:** ~6/10 — buono come design v0.2, non ancora “load and trust” in produzione

---

## Verdetto

**Buona architettura, protocollo ancora grezzo per produzione.**  
Il disegno (plan → approve → delegate → circuit breaker → review → memory) è solido. I buchi sono soprattutto: **contratti tool sbagliati**, **contraddizioni tra skill/agent/AGENTS.md**, **UX di avvio fragile**, **drift tra documenti**. Non è “rotta”, ma in una sessione reale rischia friction e comportamenti non deterministici.

---

## Cosa funziona bene

### 1. Protocollo a fasi chiaro

Startup → model selection → understanding → strategy → decomposition → execution → verification → shutdown. Un orchestratore LLM ha bisogno di un binario così; senza, tende a “fare tutto in un colpo”.

### 2. Circuit breaker

Regola d’oro:

- max 2 tentativi
- **mai** lo stesso prompt
- poi STOP + domanda all’utente

È la parte più matura del design: evita il classico burn di crediti su loop di errore.

### 3. Separazione ruoli

| Ruolo | Responsabilità |
|--------|----------------|
| Orchestrator | plan, ask, delegate, verify |
| Worker | implement leaf |
| Reviewer | read-only, report strutturato |

`task: deny` sui worker evita ricorsione infinita. Buono.

### 4. Worker prompt template

Context + Task preciso + Conventions + Verification comandi reali. Riduce l’ambiguità tipica dei subagent “ciechi”.

### 5. Memoria a 3 livelli

`memory.md` (globale) / `docs/` progetto / `execution.md` (piano). Concettualmente corretto per continuità cross-session.

### 6. Parallelismo allineato a OpenCode

Più `task` in un messaggio = parallelo; uno alla volta = sequenziale. Documentato bene, senza reinventare concurrency.

---

## Problemi critici

### C1. Schema `question` inventato (non matcha il tool reale)

La skill usa:

```yaml
question: "Ecco la strategia..."
content: |
  ## Obiettivo
  ...
options:
  - "Voglio modificare: <details>"
```

Il tool reale ha solo:

- `questions[].question`
- `questions[].header`
- `questions[].options[{label, description}]`
- `multiple`

**Non esiste `content`.**  
Le opzioni con placeholder (`<details>`, `<which ones>`) non sono “form compilabili”: o sono label fisse, o l’utente usa “Type your own answer” (custom). La skill non documenta `header`, `description`, né il custom answer.

**Effetto:** l’orchestratore improvvisa formati semi-corretti; UX inconsistente.

**Fix:** riscrivere Phase 3–6 con lo schema reale del tool, e mettere il piano nel testo del messaggio *prima* della `question` (o in `question` + `description` per opzione), non in un campo `content` fittizio.

---

### C2. “NEVER write code” vs permessi e Phase 6

| Fonte | Dice |
|--------|------|
| SKILL Rules | NEVER write code — always `task` |
| Phase 6 | “Fix it yourself if trivial, via `edit: ask`” |
| `orchestrator.md` permissions | `edit: ask`, `bash: ask` (non deny) |

Contraddizione esplicita. In pratica l’orchestratore o viola la rule, o non può fare fix banali e raddoppia i round-trip.

**Fix consigliato:** policy a livelli:

1. **Default:** no edit
2. **Trivial fix post-review** (typo, 1 riga, lint): `edit: ask` ok
3. **Tutto il resto:** worker

E allineare Rules + agent permissions.

---

### C3. Conflitto con `AGENTS.md` sulle domande e sul costo

`AGENTS.md`:

- *“Do not ask questions to the user unless you really cannot answer”*
- *“Picking a cheaper/smaller model to save cost is FORBIDDEN”*

Skill:

- *ALWAYS use `question`*
- *Prefer free LLMs for simple tasks*

Senza una **precedence esplicita** (“quando sei in modalità orchestrator, queste rule di AGENTS.md sono override”), i modelli oscillano tra “domanda tutto” e “non disturbare the user”, e tra “sempre Opus/quality” e “free per i trivial”.

**Fix:** sezione `## Precedence` in cima a `SKILL.md`:

```text
When this skill is active, it OVERRIDES AGENTS.md on:
- asking the user (interactive approval is the product)
- cost-aware worker selection (within quality bounds)
AGENTS.md still wins on: root-cause, real-env tests, no commit without ask.
```

---

### C4. Agent orchestrator quasi vuoto vs skill ricca

`agents/orchestrator.md`:

```text
When you receive a message, use the question tool to ask the user what they want to do.
```

Il protocollo vero è solo nella skill. Ma:

- la skill si carica solo se invocata / match description
- l’agent primary **non** auto-carica la skill all’avvio
- in sessione “Orchestrator” con prompt minimo, **senza** startup sequence automatica

**Effetto:** due “orchestrator” diversi (agent vs skill). L’utente che fa `/orchestrator` o sceglie l’agent non ottiene necessariamente il protocollo completo.

**Fix (scegline uno):**

**A (recommended):** body di `orchestrator.md` = “load skill `orchestrator` immediately, then follow it”  
**B:** inlinare il protocollo nell’agent e lasciare la skill come alias  
**C:** skill-only, deprecare l’agent primary

Oggi A è il minimo intervento.

---

### C5. Phase 1 Model Selection fragile

- Lista: Opus, Fable, Big Pickle, GPT-5.6
- Sessione può essere su un model non in lista (es. grok-4.5)
- Switch: “usa `/models` e ri-lancia” → spezza il flusso, perde contesto

**Problemi:** lista hardcodata e stale; UX “esci e rientra”; nessun check del model corrente vs scelta.

**Fix:**

1. Leggere model corrente
2. Se già ok → prosegui
3. Se diverso → opzioni: “continua con model attuale” / “switch manuale e riprendi da Phase 2”
4. Opzioni generate da `llms.md` Orchestrator Models, non hardcoded

---

## Problemi medi

### M1. Drift documentazione

| Item | Dove diverge |
|------|----------------|
| GLM context | agent desc “256k” vs `llms.md` “1M” |
| ARCHITECTURE vs SKILL | template worker, circuit breaker, flow: quasi duplicati |
| Worker report | `worker-glm` ha `## Blocked` completo; `worker-deepseek-flash` quasi no |
| Reviewer model | Sonnet hardcodato; non in selection guide dell’orchestrator |

Duplicazione SKILL ↔ ARCHITECTURE = bug inevitabile nel tempo.  
**Regola:** SKILL = runtime (cosa fare). ARCHITECTURE = design (perché). Zero copy-paste di procedure.

### M2. Contract worker non enforcement

Circuit breaker: cerca `## Done` / `## Blocked`.  
Ma non tutti i worker hanno lo stesso template; un modello che scrive “Done.” o “Completed successfully” fallisce il check formale.

**Fix:** un unico blocco `## Output contract` shared su tutti i worker, e orchestrator che fa parse tollerante + verifica file/test, non solo string match.

### M3. “STOP stuck worker” non è operativo

La skill dice: se loop → STOP e redelegate.  
In OpenCode l’orchestrator tipicamente **non** ha kill mid-flight del `task`; reagisce solo al return. Istruzione aspirazionale → confonde.

**Fix:** “dopo il return, se output monotono/ripetitivo o 0 file changed, tratta come fail e circuit-break”. Niente “STOP immediato” se non c’è tool.

### M4. Parallelismo senza ownership file

“Parallel se file diversi” — ok, ma manca:

- dichiarazione ownership esplicita per task
- cosa fare se due worker toccano lo stesso file
- merge / re-serializzazione

**Fix:** in Phase 4, campo obbligatorio `Owns: [paths]`; se overlap → serializza o unisci i task.

### M5. Verifica doppia costosa

Worker verifica → orchestrator verifica via bash → reviewer verifica di nuovo.  
Tre pass su lint/test = lenti e costosi.

**Fix:** worker = smoke minimo; orchestrator = comandi critici post-batch; reviewer = code review + eventuale re-run solo se sospetto.

### M6. Stima costi (Phase 4) è cosplay

“COSTO STIMATO” senza token counter reale = numeri inventati. Peggio che non stimare: dà falsa confidenza.

**Fix:** o range qualitativo (`$` / `$$` / `$$$` da tabella llms.md + rough size), o post-hoc “token usati se disponibili”. Niente stime finte precise.

### M7. Startup sequence project-centric

Assume `<project>/docs/...`. CWD può essere home, multi-repo.  
“skip if missing” ok, ma manca: come determinare root progetto, multi-package monorepo, assenza totale di docs.

**Fix:** “detect project root (git root / package root); if none, ask once; create `docs/plans/execution.md` only after first approved plan”.

### M8. Shutdown non garantito

Memory update solo “before ending session”. Sessioni killate / context full → memory stale.

**Fix:** aggiornare `execution.md` **dopo ogni task**; shutdown = solo flush finale. Non dipendere dal rituale di chiusura.

### M9. Typo / qualità copy

- “Non sono **convisto**” → **convinto**
- Mix IT UI / EN protocol: ok, ma opzioni tipo `"Cambiami i worker: <which ones>"` sono pessime come label fisse

### M10. `edit: ask` / `bash: ask` sul reviewer e orchestrator

Reviewer con `bash: ask` può bloccare la review in attesa di approval umana su ogni test. Per un subagent “automatico” è attrito alto.

**Fix reviewer:** `bash: allow` su comandi di verifica non distruttivi, o whitelist; `edit: deny` resta.

---

## Problemi minori / gap

| Gap | Nota |
|-----|------|
| Resume mid-plan | Nessun protocollo “riprendi da Task 3” leggendo `execution.md` |
| `task_id` resume worker | Tool lo supporta; skill non lo menziona |
| Cap parallelismo | 5 worker in parallelo possono saturare rate limit |
| Security worker | `bash: allow` su tutti i worker = superficie ampia; nessun sandbox note |
| Research workers | `explore` / `general` non integrati per Phase 2 exploration pesante |
| Golden path example | Manca un walkthrough end-to-end (1 bug fix, 2 task) |
| Invocation | Quando usare skill vs agent vs `/loop-coder` non è chiaro |
| memory.md schema | Tabella LLM performance ok ma non versionata; no “last updated” strutturato oltre last session |
| Active context | ARCHITECTURE cita `docs/active-context.md` ma SKILL non lo legge in startup |

---

## Allineamento con le regole operative (AGENTS.md)

| Regola | Skill | Giudizio |
|--------|-------|----------|
| Fix root cause | Esplicita in Rules + worker | ✅ |
| Real-env test | Verification + reviewer | ✅ (rischio triplo run) |
| No shortcuts (read full, no cap) | Non ripetuta nella skill | ⚠️ va ereditata/esplicitata per orchestrator explore |
| No cheap model for cost | Conflitto con prefer free | ❌ da risolvere con precedence |
| Don’t ask the user unless needed | Conflitto intenzionale | ⚠️ va dichiarato override |
| No commit unless asked | Esplicita | ✅ |

---

## Valutazione per area

| Area | Score | Commento |
|------|-------|----------|
| Design complessivo | 8/10 | Chiaro, composable, giusto per OpenCode |
| Operabilità tool-real | 4/10 | `question` schema falso; stop worker; model switch |
| Consistenza interna | 5/10 | NEVER code vs edit; agent vs skill; free vs AGENTS |
| Worker ecosystem | 7/10 | Buona base, contract e metadata da unificare |
| Memory / resume | 5/10 | Buon disegno, weak enforcement e resume |
| Safety / costi | 6/10 | Circuit breaker forte; stima costi e bash:allow deboli |
| Docs maintainability | 5/10 | Duplicazione SKILL/ARCHITECTURE, drift llms |

**Overall: ~6/10** — pronto come **v0.2 design**, non ancora come protocollo “load and trust”.

---

## Priorità di fix (ordine consigliato)

1. **Fix schema `question`** alle API reali + piano nel messaggio
2. **Unificare agent + skill** (agent carica skill all’avvio)
3. **Precedence vs AGENTS.md** (ask + cost selection)
4. **Policy edit** (never vs trivial exception)
5. **Contract worker unico** (`## Done` / `## Blocked`) su tutti i `worker-*.md`
6. **File ownership** in decomposition + no parallel overlap
7. **Model selection** da `llms.md` + current model, no hardcode
8. **Split SKILL (runtime) vs ARCHITECTURE (design)** — zero procedure duplicate
9. **Update `execution.md` per-task**, non solo shutdown
10. **Reviewer bash** meno bloccante; verifica non triplicata

---

## Cosa non toccherei

- Circuit breaker (2 attempt, no same prompt)
- Reviewer read-only come ruolo
- `task: deny` sui worker
- Template prompt worker (struttura)
- Preferenza IT per UX (in memory e coerente)

---

## Bottom line

La skill è un **project manager protocol** ben pensato, non un wrapper cosmetico. I fallimenti previsibili in sessione reale non sono “manca una feature fancy”, ma:

1. tool API inventate,
2. due entrypoint (agent vs skill) disallineati,
3. rule globali che contraddicono il prodotto orchestrator,
4. memoria/resume non enforcement.

Sistemati i 4 critici (C1–C4), sale facilmente a un 8/10 usabile ogni giorno.

---

## Related

- Patch plan (sessione 2026-07-11): P0–P10 verso v0.3 (entrypoint, question schema, precedence, workers contract, ownership, resume, docs dedup)
- Files reviewed:
  - `~/.config/opencode/skills/orchestrator/SKILL.md`
  - `~/.config/opencode/skills/orchestrator/ARCHITECTURE.md`
  - `~/.config/opencode/skills/orchestrator/memory.md`
  - `~/.config/opencode/llms.md`
  - `~/.config/opencode/agents/orchestrator.md`
  - `~/.config/opencode/agents/reviewer.md`
  - `~/.config/opencode/agents/worker-*.md`
  - `~/.config/opencode/AGENTS.md`
