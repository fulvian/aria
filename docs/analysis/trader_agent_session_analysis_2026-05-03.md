# Report di Analisi: Sessione Trader-Agent del 3 Maggio 2026

**Data analisi:** 2026-05-03
**Session ID:** ses_212fe1909ffeNpUzcxnG3HCqhw
**Analista:** Master Orchestrator (Aria-Conductor)
**Template di riferimento:** AGENTS.md + docs/foundation/aria_foundation_blueprint.md + docs/llm_wiki/wiki/trader-agent.md
**Documenti consultati:**
- `docs/llm_wiki/wiki/trader-agent.md` (wiki pagina dedicata, v1.4)
- `docs/llm_wiki/wiki/log.md` (log implementazione)
- `.aria/kilocode/agents/trader-agent.md` (prompt agente, 267 linee)
- `docs/foundation/decisions/ADR-00XX-trader-agent-introduction.md` (ADR)
- `docs/plans/agents/trader_agent_foundation_plan.md` (piano fondativo)
- `docs/llm_wiki/wiki/agent-coordination.md` (L1 coordination system)
- `docs/llm_wiki/wiki/mcp-proxy.md` (proxy contract)
- `docs/llm_wiki/wiki/index.md` (wiki v7.0)

---

## Indice

1. [Executive Summary](#1-executive-summary)
2. [Cosa ha Funzionato](#2-cosa-ha-funzionato)
3. [Cosa NON ha Funzionato — Gap Analysis](#3-cosa-non-ha-funzionato--gap-analysis)
4. [Tabella di Conformità Architetturale](#4-tabella-di-conformità-architetturale)
5. [Root Cause Analysis](#5-root-cause-analysis)
6. [Raccomandazioni Priorizzate](#6-raccomandazioni-priorizzate)
7. [Appendice: Sequenza Eventi Vs. Attesa](#7-appendice-sequenza-eventi-vs-attesa)

---

## 1. Executive Summary

La sessione di analisi finanziaria del 3 maggio 2026 ha prodotto un output **ricco e strutturato** dal punto di vista del contenuto finanziario (piano di ribilanciamento in 5 fasi, 8 idee speculative, analisi fiscale). Tuttavia, dal punto di vista architetturale, la sessione **non ha rispettato il contratto architetturale previsto per il trader-agent**.

Il problema principale: **nessun dato finanziario live è stato recuperato tramite MCP proxy**. L'agente ha prodotto prezzi, RSI, MACD, P/E e altre metriche basandosi esclusivamente su dati wiki pregressi (1-2 giorni vecchi) e conoscenza LLM, senza mai invocare `aria-mcp-proxy_call_tool` su nessun backend finanziario abilitato (financekit-mcp, mcp-fredapi, alpaca-mcp).

**Score complessivo: 4/13 obblighi architetturali soddisfatti (31%)**

---

## 2. Cosa ha Funzionato

### 2.1 Routing del Conductor ✅
Il conductor ha correttamente identificato la richiesta come finanziaria e l'ha dispatchata al trader-agent tramite i meccanismi KiloCode (`task` con `subagent_type: "trader-agent"`). Le regole di dispatch finanziario con keyword routing (40+ termini) presenti nel prompt del conductor hanno funzionato.

### 2.2 Continuità della Memoria Wiki ✅
Il conductor ha chiamato `wiki_recall_tool` all'inizio del proprio turno, recuperando due topic preesistenti:
- `portafoglio-etf` (analisi del 2 maggio)
- `interesse-investimenti` (ricerca best practice)

Questo ha permesso di riutilizzare il contesto della sessione precedente ed evitare di ricominciare da zero.

### 2.3 Completezza del Contenuto ✅
L'output finale è oggettivamente di alta qualità:
- 19 ETF classificati in 12 categorie con percentuali precise
- 5 fasi di ribilanciamento con calcolo impatto fiscale
- 8 idee speculative con prezzi, P/E, yield, catalyst
- Timeline azioni (7/30/60/90 giorni)
- Disclaimer obbligatorio presente

### 2.4 Compliance al Disclaimer ✅
Il disclaimer obbligatorio ("Le informazioni prodotte da questo agente sono per scopi di analisi e ricerca ONLY...") è presente sia nell'output del trader-agent sia nella risposta finale del conductor. Il trader-agent ha un disclaimer obbligatorio per ogni output, e questo requisito è stato soddisfatto.

### 2.5 Persistenza Wiki post-analisi ✅
Il topic `portafoglio-etf` è stato aggiornato con i risultati completi dell'analisi, inclusi il piano di ribilanciamento, le allocazioni target e le idee speculative, garantendo tracciabilità per sessioni future.

### 2.6 Consapevolezza dei Boundary ✅
L'agente non ha tentato di eseguire operazioni di trading reale, non ha scritto su exchange, e non ha modificato codice/config in runtime. Il boundary "consulente di analisi, NON execution bot" è stato rispettato.

---

## 3. Cosa NON ha Funzionato — Gap Analysis

### 🔴 CRITICAL — GAP #1: Nessun uso del proxy MCP per dati live

**Cosa doveva succedere (da trader-agent.md §47-68):**
> "Tutte le operazioni su backend MCP finanziari passano esclusivamente tramite i tool sintetici del proxy"
> "NON invocare mai direttamente tool backend — passa sempre dal proxy"

**Cosa è successo:** La sessione non mostra NESSUNA invocazione di:
- `aria-mcp-proxy_search_tools` (per scoprire tool)
- `aria-mcp-proxy_call_tool` (per chiamare tool backend finanziari)

**Prova:** La sezione di log mostra solo:
1. `wiki_recall_tool` (conductor)
2. `wiki_show_tool` (conductor, 2x)
3. `task` (conductor → trader-agent)
4. Output testo (trader-agent)
5. `wiki_update_tool` (conductor)

Nessun `financekit-mcp_*`, `mcp-fredapi_*` o `alpaca-mcp_*` tool è stato invocato.

**Impatto:** Tutti i dati di mercato nel report (prezzi QQQ $674.15, SPY $720.65, RSI(14) valori, P/E, indicatori tecnici) sono potenzialmente basati su conoscenza LLM o dati wiki pregressi, NON su dati live. Le raccomandazioni di trading sono basate su dati non verificati.

---

### 🔴 CRITICAL — GAP #2: Dati non live, potenzialmente non accurati

**Evidenza:** Il report cita valori RSI specifici (QQQ RSI 74.9, SCHD RSI 66.9, GLD RSI 43.2) e prezzi esatti ($674.15 per QQQ, $423.18 per GLD). Questi valori:
- Potrebbero essere allucinazioni LLM (valori plausibili ma non reali)
- Potrebbero essere calcolati da dati wiki del 1-2 maggio (già non freschi)
- Potrebbero essere approssimazioni non verificate

Il prezzo di GLD ($423.18) citato come "live" differisce dal prezzo nel topic wiki ($420.49 del 1 maggio), suggerendo che l'agente ha generato il numero autonomamente.

**Impatto:** Un investitore che segue le raccomandazioni basate su questi dati potrebbe prendere decisioni su informazioni non accurate.

---

### 🟡 HIGH — GAP #3: Nessuna classificazione dell'intent

**Cosa doveva succedere (da trader-agent.md §108-117):**
> "Fase 1 — Input e intent classification: Identifica il tipo di richiesta"

Il prompt elenca 8 intent categories (finance.stock-analysis, finance.comparison, finance.brief, ecc.) e richiede una classificazione esplicita.

**Cosa è successo:** Il trader-agent ha saltato completamente la fase di intent classification, passando direttamente all'analisi. Non c'è alcuna traccia di classificazione dell'intent, nè di selezione di una categoria specifica.

---

### 🟡 HIGH — GAP #4: Formato output non conforme al Trading Brief template

**Cosa doveva succedere (da trader-agent.md §157-189):**
Il template Trading Brief prevede:
```
TL;DR → Context → Analysis (Fundamental / Technical / Macro / Sentiment)
→ Risk → Recommendation
```

**Cosa è successo:** L'output ha una struttura custom in due parti (Parte A: Ribilanciamento ETF, Parte B: Opportunità Speculative). Pur essendo ben organizzato, non segue il template standardizzato. Questo impedisce:
- Parsing automatico del formato
- Confronto strutturato tra analisi diverse
- Validazione della completezza

---

### 🟡 HIGH — GAP #5: Pipeline skill non attivata

**Cosa doveva succedere (da trader-agent.md §17-24 e foundation plan §5):**
Il trader-agent ha 7 skills obbligatorie:
- `trading-analysis` · `fundamental-analysis` · `technical-analysis`
- `macro-intelligence` · `sentiment-analysis`
- `options-analysis` · `crypto-analysis`

**Cosa è successo:** Nessuna skill è stata individualmente invocata. L'analisi è stata prodotta dal LLM in forma monolitica senza attivare il layer skill specializzato.

**Impatto:** Le skill esistono in `.aria/kilocode/skills/` ma non vengono utilizzate in pratica. Questo significa che le istruzioni specialistiche in ogni skill (pattern di chiamata, tool specifici, workflow) sono ignorate.

---

### 🟡 HIGH — GAP #6: Meccanismo di dispatch non conforme all'architettura L1

**Cosa doveva succedere (da agent-coordination.md §37-39 e protocollo Fase L):**
> "Ogni chiamata `spawn-subagent` DEVE includere un `HandoffRequest` valido"
> "Validator runtime rifiuta payload free-form"

**Cosa è successo:** Il conductor ha usato lo strumento generico KiloCode `task` (con `subagent_type: "trader-agent"`) invece del meccanismo `spawn-subagent` con `HandoffRequest` validato.

**Impatto:** L'intero layer L1 (Handoff Pydantic, ContextEnvelope, Registry validation, Spawn Validator) viene bypassato. Non c'è:
- Validazione del payload di handoff
- Propagazione envelope
- Guard sulla profondità di spawn (max_spawn_depth: 0 per trader-agent)
- Evento `aria_agent_spawn_total{trace_id, parent, target}`

---

### 🟡 HIGH — GAP #7: wiki_update eseguito dal conductor, non dal trader-agent

**Cosa doveva succedere (da trader-agent.md §238-244):**
> "Fine turno: `wiki_update_tool` con patches solo se l'utente richiede esplicitamente il salvataggio"
> "`wiki_update_tool` va chiamato **esattamente una sola volta** per turno, con **payload valido**"

**Cosa è successo:** È stato il conductor a eseguire `wiki_update_tool`, non il trader-agent. Questo rompe l'attore-aware tagging (l'attore dovrebbe essere `agent_inference` del trader-agent) e viola il principio che ogni agente gestisce la propria persistenza.

---

### 🟡 HIGH — GAP #8: Nessuna propagazione trace_id (violazione L4)

**Cosa doveva succedere (da observability.md e ADR-0014):**
Ogni richiesta deve generare un `trace_id` UUIDv7 propagato end-to-end attraverso conductor → sub-agent → tool chain.

**Cosa è successo:** Nessun `trace_id` è stato generato o propagato nella sessione. I log mostrano un `session_id` di sessione ma non un `trace_id` operativo.

**Impatto:** Impossibile correlare eventi, fare debugging della latenza, o tracciare la catena di chiamate.

---

### 🟡 MEDIUM — GAP #9: Specificità delle raccomandazioni al limite dell'HITL trigger

**Da ADR-00XX §3.3:**
> "HITL gate per output 'formal trading recommendation'"
> "Tutte le raccomandazioni di trading includono disclaimer"

Il report include frasi come:
- "VENDI UPRO" + "VENDI TQQQ" + "VENDI SPY" (azioni di vendita esplicite)
- "ACQUISTARE MOS (9 azioni, ~$208)" (quantità e prezzo specifici)
- Prezzi target: "Target 12 mesi: $30–$35 (+30/50%)"

Mentre la richiesta dell'utente era per "indicazioni", la specificità delle raccomandazioni si avvicina pericolosamente a ciò che richiederebbe un gate HITL formale. Il disclaimer mitiga parzialmente ma non elimina il rischio.

---

### 🟢 LOW — GAP #10: Performance della sessione

La durata totale della sessione è di ~745 secondi (~12.5 minuti), di cui 620.5 secondi (10+ minuti) spesi nel task del trader-agent. Questo è estremamente lento per un'interazione utente.

Possibili cause:
- Il modello ha prodotto analisi estesa senza chiamate MCP (output monolitico)
- Timeout/retry in chiamate a backend non raggiungibili
- Limitazioni del modelo GLM-5.1 per analisi multi-asset complesse

---

## 4. Tabella di Conformità Architetturale

| # | Obbligo Architetturale | Fonte | Risultato | Note |
|---|---|---|---|---|
| 1 | Dati finanziari solo via proxy MCP | trader-agent.md §47-68 | ❌ FAIL | Nessuna chiamata proxy |
| 2 | `_caller_id: "trader-agent"` obbligatorio | trader-agent.md §50 | ❌ FAIL | Nessuna chiamata proxy da propagare |
| 3 | Wiki recall a inizio turno | trader-agent.md §235-236 | ✅ PASS | Fatto dal conductor |
| 4 | Wiki update a fine turno (esattamente 1x) | trader-agent.md §238-244 | ⚠️ PARTIAL | Fatto dal conductor, non dal trader-agent |
| 5 | Intent classification (Fase 1) | trader-agent.md §108-117 | ❌ FAIL | Non eseguita |
| 6 | Output Trading Brief strutturato | trader-agent.md §157-189 | ⚠️ PARTIAL | Custom 2-part, non template standard |
| 7 | 7 skills invocate individualmente | foundation plan §5 | ❌ FAIL | Nessuna skill attivata |
| 8 | Disclaimer obbligatorio | trader-agent.md §205-217 | ✅ PASS | Presente |
| 9 | HITL gate per raccomandazioni formali | trader-agent.md §221-228 | ✅ PASS | < $50K, no richiesta formale |
| 10 | Boundary: NO execution, NO write | trader-agent.md §193-203 | ✅ PASS | Rispettato |
| 11 | Spawn via HandoffRequest validato | agent-coordination.md §37-39 | ❌ FAIL | Usato `task` KiloCode generico |
| 12 | Trace_id end-to-end | observability.md §2 | ❌ FAIL | Non presente |
| 13 | Proxy-only: NO tool nativi host | trader-agent.md §86-93 | ⚠️ UNCLEAR | Output senza tool call — impossibile verificare se usati |
| 14 | FMP MCP cornerstone (253+ tool) | ADR-00XX §2.2 | ❌ FAIL | Disabilitato (HTTP/SSE Phase 2) |

**Score: 4/14 ✅ PASS, 3/14 ⚠️ PARTIAL, 6/14 ❌ FAIL, 1/14 ⚠️ UNCLEAR**

---

## 5. Root Cause Analysis

### RCA #1: Backend MCP finanziari insufficienti

**Problema:** Il cornerstone architetturale designato — `financial-modeling-prep-mcp` (253+ tool) — è disabilitato perché richiede trasporto HTTP/SSE (Phase 2). Anche `helium-mcp` (news/sentiment) è disabilitato per lo stesso motivo.

**Backend abilitati vs. necessità:**

| Funzione | Backend designato | Stato | Alternativa disponibile |
|---|---|---|---|
| Stock/ETF fundamentals | FMP MCP (253 tool) | 🔴 DISABILITATO | financekit-mcp (solo risk metrics) |
| Technical analysis | FMP MCP + financekit | 🟡 financekit SOLO | Financekit ha technicals limitati |
| News/sentiment | Helium MCP (9 tool) | 🔴 DISABILITATO | Nessuno |
| Options analysis | Helium + FMP | 🔴 DISABILITATO | Nessuno |
| Macro data | mcp-fredapi (3 tool) | 🟢 ABILITATO | Copertura FRED OK |
| Market data | alpaca-mcp (22 tool) | 🟢 ABILITATO | Solo lettura, dati USA |
| Crypto | financekit-mcp | 🟢 ABILITATO | OK |

**Conseguenza:** Il trader-agent non ha abbastanza backends abilitati per fare un'analisi finanziaria completa via proxy. Per una copertura accettabile servono almeno FMP MCP (dati fondamentali/tecnici) e Helium (news/sentiment).

### RCA #2: Modello di esecuzione sub-agente KiloCode vs ARIA

**Problema:** La dispatch è avvenuta tramite `task` tool di KiloCode, non via il sistema di coordinamento ARIA (`spawn-subagent` con `HandoffRequest`). Questo significa:

1. Il sub-agente non riceve un `ContextEnvelope` con wiki pages pre-caricate
2. Il sub-agente potrebbe non avere accesso agli MCP proxy tool nella propria tool list
3. La capability matrix non viene validata
4. Non esiste un guard sulla profondità di spawn

**Ipotesi:** È possibile che, nel contesto del sub-agente KiloCode, i tool `aria-mcp-proxy_search_tools` / `aria-mcp-proxy_call_tool` non siano visibili, costringendo l'agente ad operare in modalità "sola conoscenza".

### RCA #3: Nessuna verifica runtime dell'uso del proxy

**Problema:** Non esiste un meccanismo runtime che verifichi se il trader-agent ha effettivamente usato il proxy MCP per ottenere dati live. Il prompt dice "usa il proxy" ma l'agente può semplicemente ignorare questa istruzione e produrre output senza chiamate MCP.

Il middleware proxy (`middleware.py`) ha fail-closed per chiamate a backend non autorizzate, ma non può obbligare l'agente a fare chiamate.

### RCA #4: Assenza di standardizzazione dell'output

**Problema:** Il template Trading Brief definito nel prompt non è stato utilizzato. L'agente ha prodotto un formato ad-hoc. Non esiste:
- Validazione dell'output rispetto al template
- Struttura dati comune per analisi finanziarie
- Meccanismo per forzare l'output in formato standard

---

## 6. Raccomandazioni Priorizzate

### 🔴 P0 — Intervento Immediato

| # | Raccomandazione | Sforzo | Dettaglio |
|---|---|---|---|
| P0.1 | **Abilitare FMP MCP (Phase 1.5)** | 2-3gg | Il cornerstone con 253+ tool è disabilitato per via del trasporto HTTP/SSE. Valutare wrapper stdio o proxy tramite `mcp-gateway` per esporlo come stdio. Senza FMP, il trader-agent non può fare analisi fondamentali/tecniche live. |
| P0.2 | **Abilitare Helium MCP (Phase 1.5)** | 1-2gg | Necessario per news/sentiment e options analysis. Stesso problema HTTP/SSE. |
| P0.3 | **Diagnosticare disponibilità MCP in sub-agente task** | 0.5gg | Verificare se i tool proxy sono visibili in una sessione sub-agente KiloCode. Se non lo sono, il trader-agent non potrà MAI usare il proxy da sottosessione. |

### 🟡 P1 — Breve Termine (questa settimana)

| # | Raccomandazione | Sforzo | Dettaglio |
|---|---|---|---|
| P1.1 | **Implementare verifica runtime uso proxy** | 2-3gg | Aggiungere un guard nel conductor o nel middleware che verifichi: prima di accettare output da trader-agent, controlla se almeno una chiamata `aria-mcp-proxy_call_tool` è stata fatta. Se no, flagga output come "analisi senza dati live". |
| P1.2 | **Adottare spawn-subagent ARIA per dispatch** | 1-2gg | Sostituire `task` tool KiloCode con `spawn-subagent` + `HandoffRequest` per il dispatch interno ad ARIA. Questo abilita trace_id, envelope, validazione, e guard di profondità. |
| P1.3 | **Far eseguire wiki_update dal trader-agent** | 0.5gg | Correggere il flusso: il trader-agent deve chiamare `wiki_update_tool` alla fine del proprio turno, non il conductor. |
| P1.4 | **Inserire intent classification come hard gate** | 0.5gg | Modificare il prompt del trader-agent per rendere la classificazione dell'intent obbligatoria e verificabile (prima riga di output). |
| P1.5 | **Standardizzare formato Trading Brief** | 0.5gg | Template obbligatorio con marcatori parsabili. Validazione output contro template. |

### 🟢 P2 — Medio Termine (prossimo sprint)

| # | Raccomandazione | Sforzo | Dettaglio |
|---|---|---|---|
| P2.1 | **Audit performance sessione** | 1gg | Investigare i 620.5s di latenza del trader-agent. Possibili cause: reasoning eccessivo, timeout backend, rate limiting. |
| P2.2 | **Aggiungere gate HITL per recommendation specifiche** | 1gg | Se il report include frasi come "VENDI TICKER" + quantità + prezzo, attivare `hitl-queue_ask`. |
| P2.3 | **Propagazione trace_id obbligatoria** | 1gg | Strumento per generare e propagare trace_id UUIDv7 attraverso tutta la catena. |
| P2.4 | **Test di integrazione con dati live via proxy** | 2-3gg | Suite di test che verifica: (a) trader-agent chiama proxy, (b) proxy restituisce dati reali, (c) output contiene disclaimer. Resistente ad agent drift. |

---

## 7. Appendice: Sequenza Eventi vs. Attesa

### Sequenza Effettiva (dalla sessione log)

```
utente → conductor (8.3s)
  ├─ [thinking] riconosce richiesta finanziaria
  ├─ wiki_recall_tool("portafoglio ETF...") (5.0s) ✅ wiki ok
  │   └─ ottiene topic "portafoglio-etf" + "interesse-investimenti"
  ├─ wiki_show_tool("portafoglio-etf") ✅
  ├─ wiki_show_tool("interesse-investimenti") ✅
  ├─ [thinking] "delego al trader-agent"
  └─ task(trader-agent, prompt portfolio) (620.5s) ⚠️ lunghissimo
       └─ [NESSUN tool MCP chiamato] ❌ gap
           → output testo (report strutturato)
conductor → wiki_update_tool (portafoglio-etf) (111.0s) ⚠️ fatto da conductor, non trader-agent
conductor → risposta finale utente
```

### Sequenza Attesa (dall'architettura)

```
utente → conductor
  ├─ wiki_recall_tool() ✅ recupera contesto
  ├─ spawn-subagent(HandoffRequest{
  │     trace_id: "uuidv7",
  │     parent_agent: "aria-conductor",
  │     goal: "analisi portafoglio ETF + stock picks"
  │ })
  └─ trader-agent
       ├─ [intent classification] → finance.brief + finance.comparison ✅
       ├─ wiki_recall_tool() ✅
       ├─ trading-analysis skill (orchestratore)
       │   ├─ fundamental-analysis skill
       │   │   └─ aria-mcp-proxy_call_tool(financekit-mcp_*, _caller_id="trader-agent")
       │   │   └─ aria-mcp-proxy_call_tool(alpaca-mcp_*, _caller_id="trader-agent")
       │   ├─ technical-analysis skill
       │   │   └─ aria-mcp-proxy_call_tool(financekit-mcp_technical_analysis, _caller_id="trader-agent")
       │   ├─ macro-intelligence skill
       │   │   └─ aria-mcp-proxy_call_tool(mcp-fredapi_*, _caller_id="trader-agent")
       │   └─ sentiment-analysis skill
       │       └─ aria-mcp-proxy_call_tool(helium-mcp_*, _caller_id="trader-agent") [se abilitato]
       ├─ synthesis → Trading Brief template ✅
       ├─ wiki_update_tool(trading-brief) ✅ esattamente 1x
       └─ output → conductor → utente
```

---

## Conclusione

La sessione dimostra che **il trader-agent funziona come generatore di analisi LLM ma non come agente ARIA architetturalmente conforme**. Il contenuto finanziario è di qualità soddisfacente per un umano, ma i meccanismi di orchestrazione (proxy MCP, skill pipeline, intent classification, trace_id, template output) non sono stati attivati.

Il **gap più critico** è P0.1/P0.2: i backend MCP cornerstone (FMP 253+ tool, Helium) sono disabilitati. Senza di essi, il trader-agent non può fare analisi con dati live, indipendentemente dalla correttezza del prompt e del routing.

**Raccomandazione immediata:** Prima di iterare sul prompt o sulle skill del trader-agent, risolvere P0.1 e P0.3 (abilitare FMP MCP e diagnosticare la visibilità dei tool proxy in sub-sessione). Senza questi due fix, ogni altra ottimizzazione architetturale è inefficace.

---

*Report generato da Aria-Conductor (Master Orchestrator) il 2026-05-03T11:35*
*Basato su AGENTS.md §290-297: "Prefer minimal, reviewable diffs" — questo report non modifica codice, solo documentazione*
