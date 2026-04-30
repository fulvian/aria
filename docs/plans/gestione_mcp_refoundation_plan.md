# Piano di Refoundation MCP per ARIA

> **Data**: 2026-04-29  
> **Owner proposto**: ARIA platform / Fulvio  
> **Input primario**: `docs/analysis/analisi_sostenibilita_mcp_report.md`  
> **Fonti verificate**: `AGENTS.md`, `docs/foundation/aria_foundation_blueprint.md` (§10, §14), `.aria/kilocode/mcp.json`, agent definitions, Context7 (`/modelcontextprotocol/modelcontextprotocol`, `/lastmile-ai/mcp-agent`, `/metatool-ai/metamcp`), Anthropic Engineering, Cloudflare enterprise MCP architecture.

---

## 1. Obiettivo

Rivedere e ottimizzare la struttura MCP di ARIA per:

1. ridurre il costo di startup e di contesto;
2. evitare drift tra configurazione, agenti e runtime isolato;
3. introdurre governance esplicita su domini, ownership, tier e lifecycle dei server MCP;
4. preparare ARIA a crescere oltre l'attuale assetto senza introdurre complessità prematura.

Questo piano segue esplicitamente:
- **P1** isolation first;
- **P8** tool priority ladder;
- **P9** scoped toolsets;
- **P10** self-documenting evolution;
- linee guida di **governance/osservabilità** del blueprint §14.

---

## 2. Executive Summary

Il report di sostenibilità individua correttamente il problema di scala, ma l'inventario operativo è già cambiato: la configurazione attuale contiene **16 server MCP dichiarati, 15 abilitati**, non più i 12 riportati nell'analisi iniziale.

La criticità principale non è solo il numero di server, ma la combinazione di questi fattori:

- registro MCP **piatto** e non classificato;
- startup **eager** dei server via config statica;
- **duplicazione** fra sorgente `.aria/kilocode/*` e runtime sincronizzato `.aria/kilo-home/.kilo/*`;
- **assenza** di un registry/snapshot di schema;
- **assenza** di un layer di governance unico per policy, audit e connessioni;
- **drift operativo** fra server configurati e server realmente esposti ai sub-agent.

La raccomandazione è una refoundation in **3 livelli progressivi**, non in un big bang:

1. **Hardening del modello attuale**: inventario, classificazione, drift detection, scoping automatico, schema snapshot.
2. **Ottimizzazione del runtime**: tool-search/lazy loading se supportato, serverInstructions, lifecycle policy core vs non-core, bootstrap leggero.
3. **Gateway selettivo per domini ad alta crescita**: introdurre un gateway solo quando i dati misurati lo giustificano, iniziando da `search`.

**Non raccomandato subito**:
- migrazione immediata a gateway totale per tutti i server;
- code execution pattern come default globale;
- remote MCP enterprise-style alla Cloudflare, perché oggi confliggerebbe con P1/P4 e introdurrebbe overhead non ancora giustificato.

---

## 3. Stato Attuale dell'Architettura MCP

## 3.1 Inventario osservato

Fonte: `.aria/kilocode/mcp.json` interrogato il 2026-04-29.

### Server configurati
- Core locale: `filesystem`, `git`, `github`, `sequential-thinking`, `fetch`, `aria-memory`
- Ricerca: `tavily-mcp`, `brave-mcp`, `exa-script`, `searxng-script`, `pubmed-mcp`, `scientific-papers-mcp`, `reddit-search`
- Workspace/produttività: `google_workspace`, `markitdown-mcp`
- Disabilitato: `playwright`

### Conteggio
- **Totale dichiarati**: 16
- **Abilitati**: 15
- **Disabilitati**: 1

## 3.2 Modello operativo corrente

L'architettura attuale è ancora sostanzialmente:

```text
Kilo/ARIA session
  -> carica config MCP piatta
  -> avvia/risolve server stdio o wrapper locali
  -> espone tool per agenti tramite allowed-tools
  -> delega dal conductor ai sub-agent
```

Elementi positivi già presenti:
- conductor scoped e non operativo direttamente;
- search/workspace/productivity agent separati;
- wrappers locali per credenziali/provider;
- isolamento runtime tramite `bin/aria` e `.aria/kilo-home`.

## 3.3 Drift e inconsistenze osservate

### A. Drift tra report e runtime reale
Il report di input parla di 12 server e include `firecrawl-mcp`; il runtime attuale ha 16 server dichiarati e non include `firecrawl-mcp`.

### B. Drift fra config MCP e exposure agentica
I server `pubmed-mcp` e `scientific-papers-mcp` sono configurati, ma il `search-agent` non li dichiara in `mcp-dependencies`/`allowed-tools` nonostante il prompt li descriva come parte del flusso academic.

### C. Doppia sorgente pratica di configurazione
Le definizioni vivono in `.aria/kilocode/*`, ma il runtime reale usa copie sincronizzate in `.aria/kilo-home/.kilo/*`. Questo aumenta il rischio di:
- divergenza silenziosa;
- bug difficili da diagnosticare;
- review più lente su problemi MCP.

### D. Registry piatto
`mcp.json` non codifica:
- dominio;
- owner;
- tier;
- criticità;
- lifecycle policy;
- dipendenze transitive;
- modalità di bootstrap;
- costo/limite/affidabilità.

### E. Nessuno snapshot di schema
Non esiste un artefatto versionato che congeli l'ultima `tools/list` attesa per server. Quindi:
- i drift di schema sono invisibili finché qualcosa si rompe;
- l'onboarding di nuovi MCP non è governato da diff.

---

## 4. Criticità Prioritarie

## 4.1 Criticità P0 — Governance e coerenza

1. **Inventory drift**: documentazione e config divergono già.
2. **Agent exposure drift**: server configurati ma non realmente utilizzabili dagli agenti giusti.
3. **Ownership implicita**: mancano owner e policy per dominio.
4. **Assenza di gating strutturato** per aggiunta/rimozione server MCP.

## 4.2 Criticità P1 — Costo operativo locale

1. **Bootstrap eager** del parco MCP.
2. **Un processo per server** su stdio/wrapper.
3. **Contesto speso in definizioni tool** senza controllo esplicito lato config.
4. **Failure surface ampia**: basta un wrapper o una dipendenza rotta per degradare la sessione.

## 4.3 Criticità P1 — Manutenibilità

1. Crescita di `mcp.json` non strutturata.
2. Crescita di `allowed-tools`/prompt manuale.
3. Nessun catalogo machine-readable di dominio/tier/costo.
4. Aggiornamenti ai provider non accompagnati da schema diff automatico.

## 4.4 Criticità P2 — Architettura futura

1. Nessun piano esplicito per connection reuse.
2. Nessun gateway selettivo per domini ad alta crescita.
3. Nessuna policy codificata core/non-core.
4. Nessuna misurazione baseline di startup, memoria, latenza, error rate.

---

## 5. Best Practice Verificate Online e via Context7

## 5.1 Progressive disclosure / lazy loading

**Verifica**:
- Anthropic: il costo principale cresce quando tool definitions e intermediate results passano tutti nel context window.
- Articoli su Tool Search: valore pratico massimo quando i server sono molti e con descrizioni ampie.

**Implicazione per ARIA**:
- il caricamento lazy è il quick win a maggior leverage;
- ma va introdotto solo dopo una fase di **classificazione** e **serverInstructions** pulite, altrimenti la discoverability peggiora.

## 5.2 Gateway/aggregator come layer di governance, non come fine

**Verifica**:
- MetaMCP supporta aggregazione, namespace, middleware e più trasporti.
- Cloudflare mostra che il valore reale del gateway è: policy, auditing, discovery, DLP/cost control, esposizione selettiva.

**Implicazione per ARIA**:
- un gateway ha senso solo se risolve problemi misurati di crescita e governance;
- per ARIA oggi il primo candidato è **solo il dominio search**, non tutto il parco MCP.

## 5.3 Scoped workers + connection reuse

**Verifica**:
- `mcp-agent` conferma il pattern orchestrator/worker con `server_names` scoped e connection manager persistente.

**Implicazione per ARIA**:
- la direzione corretta non è “più tool per tutti”, ma **domini piccoli e connessioni riusabili**;
- search/workspace/productivity vanno consolidati come domini formali con mapping esplicito server -> agenti.

## 5.4 Sicurezza e session binding

**Verifica**:
- spec MCP e guidance correlate insistono su initialize/capability negotiation, access control, rate limiting, isolamento di sessione/task.
- Cloudflare enfatizza shadow MCP, policy centrali, autenticazione e audit.

**Implicazione per ARIA**:
- anche in locale servono almeno:
  - classificazione core/non-core;
  - audit dei tool esposti;
  - policy hitl e write controls per i tool sensibili;
  - versione/owner dei wrapper.

## 5.5 Code execution pattern: forte ma non MVP

**Verifica**:
- Anthropic e Cloudflare mostrano vantaggi enormi di token efficiency.
- Entrambi presuppongono sandboxing serio e controllo del runtime.

**Implicazione per ARIA**:
- pattern promettente per il futuro;
- **non** da adottare ora come refoundation primaria;
- da trattare come fase R&D separata con ADR dedicato.

---

## 6. Principi di Refoundation

1. **Single source of truth**: una sola sorgente canonica per inventory e policy MCP.
2. **Classificazione prima dell'ottimizzazione**: niente lazy/gateway prima di un catalogo accurato.
3. **Core always-on, non-core opt-in**: il runtime deve distinguere chiaramente i server essenziali da quelli opzionali.
4. **Misurare prima di complicare**: ogni salto architetturale richiede baseline e target.
5. **Gateway selettivo, non totale**: introdurre middleware solo dove il dominio lo richiede.
6. **Prompt/config coherence**: agent prompt, dependencies e registry devono derivare dallo stesso catalogo.
7. **ADR per ogni divergenza significativa**: conforme a P10.

---

## 7. Architettura Target Raccomandata

## 7.1 Livello A — Catalogo canonico MCP

Introdurre un file canonico dedicato, ad esempio:

`docs/foundation/mcp_catalog.yaml` oppure `.aria/config/mcp_catalog.yaml`

Contenuti minimi per server:
- `name`
- `domain` (`core`, `search`, `workspace`, `productivity`, `memory`, `experimental`)
- `owner_agent`
- `tier` (`core`, `primary`, `secondary`, `experimental`)
- `transport` (`stdio`, `wrapper`, `http`, `sse`)
- `lifecycle` (`always_on`, `session_lazy`, `manual`, `disabled`)
- `auth_mode` (`none`, `api_key`, `oauth`, `local_only`)
- `statefulness` (`stateless`, `sessionful`)
- `expected_tools`
- `risk_level`
- `cost_class`
- `source_of_truth` (repo/package/version/wrapper)

Questo catalogo diventa la base per generare/verificare:
- `mcp.json`
- matrice agent -> allowed-tools
- documentazione wiki
- controlli di drift

## 7.2 Livello B — Bootstrap minimale per sessione

### Always-on solo per core
Raccomandati come **core**:
- `filesystem`
- `git`
- `github`
- `sequential-thinking`
- `aria-memory`
- `fetch`

### Non-core caricati per dominio/necessità
- `search`: `searxng-script`, `reddit-search`, `tavily-mcp`, `exa-script`, `brave-mcp`, `pubmed-mcp`, `scientific-papers-mcp`
- `workspace`: `google_workspace`
- `productivity`: `markitdown-mcp`
- `experimental`: `playwright`

## 7.3 Livello C — Tool discovery / progressive disclosure

Se Kilo supporta realmente `enable_tool_search` o equivalente, abilitarlo **solo dopo**:
- pulizia inventory;
- definizione `serverInstructions` per ogni server non banale;
- prova compatibilità locale;
- benchmark prima/dopo.

Se non supportato:
- mantenere backlog aperto;
- non introdurre proxy custom immediati salvo forte evidenza di pain.

## 7.4 Livello D — Gateway solo per search domain

Gateway selettivo candidato:

```text
search-agent
  -> search-gateway
       -> searxng / reddit / tavily / exa / brave / pubmed / scientific-papers
```

Funzioni del gateway v1:
- aliasing coerente dei tool;
- health check e disabled state centralizzato;
- logging unificato;
- policy di fallback;
- possibile caching di discovery metadata.

Funzioni **non** da mettere in v1:
- multi-tenant auth complex;
- DLP enterprise-style;
- code execution integrata;
- gateway universale per tutto ARIA.

---

## 8. Piano di Implementazione

## Fase 0 — Baseline e allineamento inventario (1 giorno)

### Obiettivi
- bloccare il drift;
- produrre baseline numerica;
- allineare report, config e agent exposure.

### Attività
1. Estrarre inventory canonico da `.aria/kilocode/mcp.json`.
2. Classificare ogni server per dominio, tier, owner, lifecycle.
3. Verificare per ogni server:
   - è configurato?
   - è documentato?
   - è esposto a un agente?
   - è ancora usato?
4. Correggere mismatch immediati:
   - `pubmed-mcp` / `scientific-papers-mcp` vs `search-agent`
   - eventuali server orfani o zombie
5. Aggiornare il report di sostenibilità o creare ADR/appendice di correzione inventario.

### Deliverable
- catalogo MCP v1
- tabella server -> agent -> tool exposure
- baseline metriche startup/context/processi

### Gate di uscita
- nessun server attivo senza owner/domino/tier
- nessun tool descritto nei prompt ma non realmente esposto

## Fase 1 — Hardening del modello attuale (2-3 giorni)

### Obiettivi
- rendere sostenibile l'architettura corrente senza cambiare paradigma.

### Attività
1. Introdurre `mcp_catalog.yaml` come single source of truth.
2. Generare/validare `mcp.json` dal catalogo o almeno validarlo contro il catalogo.
3. Aggiungere `serverInstructions`/metadata descrittivi per i server dove il client lo supporta.
4. Introdurre schema snapshot locale, ad esempio:
   - `.aria/runtime/mcp-schema-snapshots/<server>.json`
5. Introdurre check CI o script locale per:
   - drift config vs catalogo
   - drift catalogo vs prompt agenti
   - drift schema atteso vs schema reale
6. Formalizzare policy core/non-core.

### Deliverable
- catalogo MCP v1 operativo
- validatore drift
- snapshots schema
- documentazione wiki aggiornata

### KPI target
- 100% server classificati
- 0 server orfani
- 0 mismatch prompt/config noti

## Fase 2 — Ottimizzazione bootstrap e scoping (2-4 giorni)

### Obiettivi
- ridurre il costo di sessione senza introdurre gateway completo.

### Attività
1. Fare **capability probe** del client Kilo per verificare supporto reale a:
   - tool search
   - lazy loading
   - eventuali per-server instructions
2. Se supportato, abilitare tool search in ambiente isolato di test.
3. Separare bootstrap in:
   - core always-on
   - domain-on-demand/logical lazy
4. Rafforzare scoping P9 generando la matrice `allowed-tools` dal catalogo.
5. Aggiungere benchmark misurati:
   - tempo startup
   - token iniziali
   - numero processi
   - memoria RSS indicativa

### Deliverable
- report benchmark pre/post
- policy bootstrap aggiornata
- configurazione tool search, se disponibile

### KPI target
- riduzione startup >= 30% senza regressioni funzionali
- riduzione contesto iniziale misurabile e documentata

## Fase 3 — Search Gateway PoC (4-6 giorni)

### Obiettivi
- introdurre governance locale dove il problema è più forte: dominio ricerca.

### Attività
1. Valutare **MetaMCP vs gateway custom minimo** con una scorecard:
   - compatibilità locale
   - overhead
   - osservabilità
   - costo di manutenzione
   - supporto namespace/middleware
2. Realizzare PoC solo su `search`.
3. Portare nel gateway v1:
   - tool aliasing
   - health-state registry
   - fallback policy metadata
   - logging unico
4. Tenere fuori il resto.

### Decisione raccomandata
- usare MetaMCP **solo se** riduce chiaramente il lavoro custom e non rompe P1/P4;
- altrimenti costruire un gateway minimale e locale solo per search.

### Gate di uscita
- search domain funziona end-to-end senza regressione utenti
- osservabilità migliore della baseline
- overhead latenza accettabile

## Fase 4 — Governance permanente (1-2 giorni + continuo)

### Obiettivi
- impedire ricadute nel drift.

### Attività
1. Aggiungere sezione blueprint/ADR per **P11 — MCP Sustainability**.
2. Aggiornare wiki con pagina dedicata all'architettura MCP corrente.
3. Introdurre checklist obbligatoria per nuovi MCP:
   - esiste già un MCP maturo? (P8)
   - quale agente owner?
   - quale dominio/tier?
   - quali tool esporre?
   - qual è il rischio/costo?
   - serve davvero in always-on?
4. Inserire review mensile del catalogo MCP.

---

## 9. Decisioni Raccomandate

## Da fare subito

1. **Creare catalogo MCP canonico**.
2. **Correggere i mismatch** tra config, prompt e dependencies.
3. **Misurare** startup/context/processi prima di ogni altra scelta.
4. **Preparare drift checks** per inventory e schema.
5. **Verificare il supporto reale del client** a tool search/lazy loading.

## Da fare dopo evidenza misurata

1. Abilitare tool search/lazy loading.
2. Introdurre gateway selettivo su search.
3. Valutare connection reuse/manager lato runtime custom.

## Non fare ora

1. Gateway totale per tutti i domini.
2. Refactor completo verso remote MCP enterprise.
3. Code execution pattern globale.
4. Nuovi server MCP aggiuntivi prima di aver chiuso la refoundation.

---

## 10. Rischi e Mitigazioni

| Rischio | Impatto | Mitigazione |
|---|---|---|
| Abilitare lazy/tool search senza metadata puliti | tool discoverability bassa | introdurre `serverInstructions` e fare capability probe prima |
| Gateway introdotto troppo presto | complessità e latenza inutili | limitarlo a PoC search-domain |
| Catalogo mantenuto a mano ma non enforced | drift ricorrente | validatore automatico config/prompt/schema |
| Correzione inventory rompe agenti esistenti | regressioni silenziose | baseline + test smoke per agent/domain |
| Doppia config `.aria/kilocode` vs `.aria/kilo-home` | bug diagnostici | documentare la catena di sync e validarla esplicitamente |
| Over-engineering | rallentamento del progetto | seguire YAGNI: quick wins prima, advanced solo dopo metriche |

---

## 11. KPI di Successo

### KPI tecnici
- tempo startup sessione ARIA
- token iniziali consumati dalla disponibilità tool
- numero di processi MCP avviati a cold start
- mismatch catalogo/config/prompt = 0
- percentuale server con owner/tier/domain/lifecycle definiti = 100%

### KPI operativi
- tempo per aggiungere un nuovo MCP in modo conforme
- numero di incidenti dovuti a drift MCP
- numero di server “configured but unreachable/unexposed”

### KPI architetturali
- percentuale di tool exposure derivata da catalogo, non da editing manuale
- presenza di benchmark documentati per ogni salto architetturale

---

## 12. File da Creare/Aggiornare

## Nuovi artefatti raccomandati
- `docs/plans/gestione_mcp_refoundation_plan.md` — questo piano
- `docs/llm_wiki/wiki/mcp-architecture.md` — pagina wiki dedicata alla struttura MCP corrente
- `.aria/config/mcp_catalog.yaml` oppure `docs/foundation/mcp_catalog.yaml`
- `scripts/check_mcp_drift.py` — validazione inventory/prompt/schema
- `.aria/runtime/mcp-schema-snapshots/` — snapshot discovery per server

## Aggiornamenti previsti
- `docs/foundation/aria_foundation_blueprint.md` — introdurre P11 o integrare §10.5
- `docs/analysis/analisi_sostenibilita_mcp_report.md` — appendice o nota di drift inventario
- `.aria/kilocode/agents/*.md` — riallineamento `allowed-tools` e `mcp-dependencies`
- `.aria/kilocode/mcp.json` — eventuale normalizzazione guidata dal catalogo

---

## 13. ADR Raccomandati

1. **ADR — MCP catalog as single source of truth**
2. **ADR — Core vs non-core MCP lifecycle policy**
3. **ADR — Search gateway introduction (solo se PoC approvato)**
4. **ADR — Tool search/lazy loading enablement decision**
5. **ADR — Code execution deferred/not adopted for MVP**

---

## 14. Sequenza Operativa Consigliata

```text
Step 1  Inventory reale e classificazione
Step 2  Correzione drift config <-> agenti <-> wiki
Step 3  Catalogo canonico + drift checks
Step 4  Baseline benchmark
Step 5  Capability probe tool search/lazy
Step 6  Ottimizzazione bootstrap
Step 7  Search gateway PoC (solo se metriche lo giustificano)
Step 8  ADR/blueprint/wiki consolidation
```

---

## 15. Conclusione

ARIA non ha ancora un problema di “troppi MCP” in senso assoluto; ha già però un problema concreto di **governance, coerenza e crescita non strutturata**.

La refoundation corretta non è introdurre subito una nuova mega-architettura, ma:
- congelare e normalizzare l'inventario reale;
- rendere catalogo, config e agenti coerenti;
- introdurre progressive disclosure solo se realmente supportata;
- portare un gateway solo dove serve davvero.

La priorità assoluta è quindi: **inventory authority -> drift elimination -> measured optimization -> selective gatewaying**.

---

## Provenance

- Source: `docs/analysis/analisi_sostenibilita_mcp_report.md` (updated 2026-04-29)
- Source: `AGENTS.md` (read 2026-04-29)
- Source: `docs/foundation/aria_foundation_blueprint.md` §10, §14 (read 2026-04-29)
- Source: `.aria/kilocode/mcp.json` (read 2026-04-29)
- Source: `.aria/kilocode/kilo.json` (read 2026-04-29)
- Source: `.aria/kilocode/agents/search-agent.md` (read 2026-04-29)
- Source: `.aria/kilocode/agents/workspace-agent.md` (read 2026-04-29)
- Source: `.aria/kilocode/agents/productivity-agent.md` (read 2026-04-29)
- Source: `docs/llm_wiki/wiki/aria-launcher-cli-compatibility.md` (read 2026-04-29)
- Source: Context7 `/metatool-ai/metamcp` (queried 2026-04-29)
- Source: Context7 `/lastmile-ai/mcp-agent` (queried 2026-04-29)
- Source: Context7 `/modelcontextprotocol/modelcontextprotocol` (queried 2026-04-29)
- Source: Anthropic Engineering — `https://www.anthropic.com/engineering/code-execution-with-mcp` (queried 2026-04-29)
- Source: Cloudflare Blog — `https://blog.cloudflare.com/enterprise-mcp/` (queried 2026-04-29)
- Source: Claude Fast article on MCP Tool Search — `https://claudefa.st/blog/tools/mcp-extensions/mcp-tool-search` (queried 2026-04-29; secondary/non-authoritative for exact config semantics)
