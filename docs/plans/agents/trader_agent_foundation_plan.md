# Trader-Agent — Foundation Plan

```yaml
status: DRAFT — in revisione
author: aria-conductor (sessione fulvio)
created: 2026-05-02
language: IT
audience: fulvio + agent implementatori
input-source: richiesta utente 2026-05-02
related-blueprint-sections:
  - "§8 Gerarchia Agenti"
  - "§9 Skills Layer"
  - "§10 Tools & MCP Ecosystem"
  - "§16 Ten Commandments"
related-adrs:
  - "ADR-0008-productivity-agent-introduction.md"
  - "ADR-0015-fastmcp-native-proxy.md"
new-adrs:
  - "ADR-00XX-trader-agent-introduction.md (da redigere)"
research-sources:
  - "github.com/TauricResearch/TradingAgents (multi-agent trading framework)"
  - "github.com/imbenrabi/Financial-Modeling-Prep-MCP-Server (253+ tools)"
  - "github.com/connerlambden/helium-mcp (news + options)"
  - "github.com/Jaldekoa/mcp-fredapi (FRED macro)"
  - "github.com/vdalhambra/financekit-mcp (risk metrics)"
implementation-branch: feature/trader-agent-mvp
estimated-effort: 2-3 settimane
```

---

## 0. Analisi di fit e boundary (Fase C — Protocollo)

### 0.1 È un nuovo agente necessario?

**Risposta: SÌ.**

L'utente richiede un agente esperto di finanza, stock, ETF, materie prime e crypto,
futures e derivati, che abbia accesso a informazioni fondamentali, macroeconomiche e di
sentiment, e sia capace di prendere decisioni di trading sulla base di analisi fondamentale
e tecnica.

Dominio: **autonomo e coerente** — trading/financial analysis è un dominio
verticale distinto da:
- `search-agent` (web search generico)
- `productivity-agent` (document workflow)
- `workspace-agent` (Google Workspace)

### 0.2 Criterio hard gate (protocollo §2.1)

Un nuovo sub-agente si approva solo se il dominio è **autonomo e coerente**, non per
nascondere debolezze di prompt o routing. Il dominio trading è:
- Autonomo: ha workflow, skill e tool specificityhe proprie
- Coerente: analisi fondamentale + tecnica + sentiment è un ciclo chiuso
- Non overlapping: non c'è overlap sostanziale con agenti esistenti

### 0.3 Domande obbligatorie (protocollo §C)

| # | Domanda | Risposta |
|---|---------|----------|
| 1 | Il bisogno può restare dentro un agente esistente? | NO — trading richiede MCP specializzati (FMP, FRED, Helium) non presenti negli altri agenti |
| 2 | Può essere coperto da una skill aggiuntiva? | NO — la skill da sola non giustificherebbe l'accesso a 253+ tool MCP |
| 3 | Può essere ottenuto solo ampliando la capability matrix? | NO — la complessità (analisi multi-dimensionale, HITL trading) richiede un agente dedicato |
| 4 | Il dominio è distinto da `search-agent` o `productivity-agent`? | SÌ — trading è un dominio verticale, non trasversale |
| 5 | La proposta aumenta o riduce hop, complessità, rischio e carico HITL? | riduce rischio di confusione tra domain diversi |

### 0.4 Non-obiettivi espliciti

- L'agente **NON** esegue trading automatico — è un **analista consulente**, non un execution bot
- L'agente **NON** fornisce consulenza finanziaria legale — analisi strutturata, non raccomandazione di investimento
- L'agente **NON** gestisce direttamente wallet crypto o accounts — delega a tool MCP di sola lettura (no write su exchange)
- L'agente **NON** fa execution — le operazioni di trading richiedono HITL esplicito

---

## 1. Scope dell'agente

### 1.1 Missione

L'agente risponde a domande di analisi finanziaria in linguaggio naturale:
- "Analizza NVDA: fondamentali, tecnica, sentiment e dammi un verdetto trading"
- "Come sta influenzando il treasury yield a 10 anni l'S&P500?"
- "Fammi un brief su BTC da prospettiva macro + on-chain + tecnica"
- "Confronta 3 ETF obbligazionari long-term per reddito e duration risk"

### 1.2 Capability primarie

| # | Capability | Descrizione |
|---|------------|-------------|
| C1 | **Stock/ETF Analysis** | Analisi prezzi storici, fondamentali, comparazione multi-ticker |
| C2 | **Options/Futures Analysis** | Catene opzioni, grecs, prob ITM, strategie |
| C3 | **Macro Economic Intelligence** | Dati FRED, tassi, inflazione, NFP, GDP, PMI |
| C4 | **Sentiment & News** | News scoring, bias analysis, social sentiment |
| C5 | **Technical Analysis** | Indicatori (RSI, MACD, SMA, EMA, BB), pattern matching |
| C6 | **Crypto/DeFi Intelligence** | Prezzi crypto, DEX data, funding rates, on-chain |
| C7 | **Commodity Intelligence** | Oro, petrolio, agricoli, futures |
| C8 | **Trading Decision Support** | Synthesis di tutte le dimensioni → raccomandazione strutturata |

### 1.3 Output attesi

- **Trading Brief**: documento strutturato ( TL;DR → Context → Analysis → Risk → Recommendation )
- **Ticker Comparison**: tabella comparativa multi-asset
- **Macro Dashboard**: sintesi indicatori macro chiave
- **Options Chain Analysis**: analisi catena opzioni con grecs
- **Sentiment Report**: news + social aggregated score

---

## 2. MCP Stack — Tool Decision Ladder (P8)

### 2.1 Ordine vincolante (protocollo §F)

```
1. Riuso MCP esistente maturo
2. Nuova skill che compone tool esistenti
3. Tool Python locale solo se 1 e 2 falliscono
```

### 2.2 Stack MCP selezionato

| MCP Server | Priorità | Tipo | Copertura | API Key |
|------------|----------|------|-----------|---------|
| **Financial Modeling Prep MCP** | PRIMARY | Nuovo | Stocks, ETF, options, futures, crypto, forex, commodities, macro, fundamentals, technicals, news, SEC, analyst estimates (253+ tools) — copre 6/7 requirement in un server | SÌ (free tier disponibile) |
| **Helium MCP** | PRIMARY | Nuovo | News intelligence + bias scoring + ML options pricing | No |
| **mcp-fredapi (FRED)** | PRIMARY | Nuovo | Macroeconomico (rates, GDP, inflation, NFP) — gold standard per macro | No |
| **financekit-mcp** | SECONDARY | Nuovo | Risk metrics (VaR, Sharpe, Sortino, Beta), correlation, technicals | No |
| **Alpaca MCP** | EXECUTION (solo lettura) | Nuovo | Market data + paper trading execution (no real money) | SÌ |

### 2.3 MCP che NON soddisfano P8 ladder

- Yahoo Finance MCP servers (molti, non affidabili, rate-limiting Yahoo)
- Binance MCP, ccxt-mcp (execution — out of scope per ora)

### 2.4 Nessun Python locale necessario

L'Stack scelto copre tutti i requirement senza tool Python locale. I server MCP sono
tutti FastMCP-stdio o HTTP/SSE compatibili con `aria-mcp-proxy`.

---

## 3. Architettura dell'agente

### 3.1 Posizionamento nella gerarchia ARIA

```
utente
  └─→ aria-conductor (orchestrator primario)
       ├─→ search-agent     (ricerca web generica)
       ├─→ productivity-agent (document workflow)
       └─→ trader-agent      (NUOVO — analisi finanziaria)
              ├─ financial-modeling-prep-mcp (253+ tools)
              ├─ helium-mcp (news/sentiment/options)
              ├─ fredapi-mcp (macro)
              ├─ financekit-mcp (risk/technicals)
              └─ alpaca-mcp (market data, solo lettura)
```

### 3.2 Boundary dell'agente

- **NON** esegue operazioni di trading reale — è un consulente di analisi
- **NON** accede a wallet crypto o exchange account write
- **NON** fornisce consulenza legale di investimento
- **TUTTE** le raccomandazioni sono MARKED come "analisi non consulenza finanziaria"
- Delega **NON** prevista ad altri agenti (2-hop non necessario per analysis)

### 3.3 Intent categories

L'agente risponde a:
- `finance.stock-analysis` — analisi singolo/multiple stock/ETF
- `finance.options-analysis` — catene opzioni, strategie, grecs
- `finance.macro-analysis` — indicatori macroeconomici
- `finance.sentiment` — news + social sentiment
- `finance.crypto` — crypto/deFi analysis
- `finance.commodity` — commodity futures
- `finance.comparison` — comparazione multi-asset
- `finance.brief` — trading brief strutturato

---

## 4. Allowed Tools e Capability Matrix

### 4.1 Allowed Tools (P9: ≤20)

```yaml
allowed-tools:
  # MCP servers finanziari
  - financial-modeling-prep-mcp__*          # 253+ tools — cornerstone
  - helium-mcp__*                            # news/sentiment/options ML
  - fredapi-mcp__*                           # macro data
  - financekit-mcp__*                        # risk/technical metrics
  - alpaca-mcp__*                            # market data (lettura)

  # Sistema ARIA
  - aria-memory__wiki_update_tool           # salva analisi/trading-brief
  - aria-memory__wiki_recall_tool           # recupera contesto storico
  - aria-memory__wiki_show_tool
  - aria-memory__wiki_list_tool
  - hitl-queue__ask                          # HITL per operazioni costose

  # Tool di sistema
  - sequential-thinking__*                  # ragionamento strutturato
  - spawn-subagent                          # solo per escalation a conductor
```

**Conteo**: 5 MCP server × wildcard = 5 entry + 6 aria-memory + 1 hitl + 1 seq + 1 spawn = **14 tool entries** ✅ (sotto 20)

### 4.2 MCP Dependencies

```yaml
mcp_dependencies:
  - aria-mcp-proxy    # via proxy per tutti i backend
  - aria-memory
```

### 4.3 HITL triggers

```yaml
hitl_triggers:
  - operazioni di write su exchange (disabilitato per ora)
  - analisi su asset con exposure > 50k€ (budget gate)
  - richiesta esplicita di "trading recommendation" come output formale
  - qualsiasi operazione che cambia stato (wiki write除外 — solo display)
```

### 4.4 Max spawn depth

```yaml
max_spawn_depth: 0  # Leaf agent — non spawna sub-agenti
```

---

## 5. Skill necessarie

### 5.1 Skill proposed

| Skill | Version | Descrizione |
|-------|---------|-------------|
| `trading-analysis` | 1.0.0 | Orchestratore: riceve ticker/asset → analisi multi-dimensionale → synthesis |
| `fundamental-analysis` | 1.0.0 | Analisi fondamentali: earnings, statements, DCF, analyst estimates |
| `technical-analysis` | 1.0.0 | Indicatori tecnici, pattern, support/resistance, trend |
| `macro-intelligence` | 1.0.0 | Dati macro: FRED, tassi, inflazione, correlazioni |
| `sentiment-analysis` | 1.0.0 | News scoring, bias, social sentiment aggregation |
| `options-analysis` | 1.0.0 | Catene opzioni, grecs, strategie base |
| `crypto-analysis` | 1.0.0 | On-chain, DEX, funding rates, whale tracking |

**Nessuna skill preexisting disponibile** — tutte nuove.

---

## 6. Memoria, Provenance e Wiki.db (Fase H)

### 6.1 Wiki pages toccate

| Page kind | Azione | Frequenza |
|-----------|--------|-----------|
| `trading-brief` | CREATE on-demand | Ogni analisi richiesta dall'utente |
| `ticker-<symbol>` | UPDATE/CREATE | Analisi ripetute su stesso ticker |
| `macro-snapshot` | CREATE | Dashboard macro periodiche |
| `lesson` | CREATE (HITL) | Regole apprese da risultati trading |

### 6.2 Actor-aware tagging

- Output agente: `actor: agent_inference`
- Dati MCP: `actor: tool_output`
- Input utente: `actor: user_input`
- Hitl decisions: `actor: system_event`

### 6.3 Wiki recall pattern

```
Inizio turno: wiki_recall(query=<ticker + context>) per recupera analisi precedenti
Fine turno: wiki_update se l'utente richiede salvataggio esplicito (no auto-save)
```

### 6.4 Cosa NON salvare automaticamente

- Analisi "one-shot" senza richiesta esplicita di salvataggio
- Inference parziali non validate
- Trade "recommendations" senza disclaimer legale

---

## 7. HITL, Sicurezza e Comportamento (Fase I)

### 7.1 Hard rules

1. **Tutte** le raccomandazioni di trading includono disclaimer: "Analisi non consulenza finanziaria. Verifica con un professionista prima di investire."
2. **Nessuna** operazione di write su exchange abilitata (no trading reale)
3. **Nessuna** automazione di trading — solo analisi on-demand
4. HITL gate per analisi che richiedono budget > 50k token per singola sessione
5. HITL gate per output "formal trading recommendation" (verifica utente)

### 7.2 Self-remediation prohibition

Durante workflow utente l'agente **NON** può:
- Modificare codice, config o prompt
- Killare processi
- Auto-remediation runtime

Se bug emerge → l'agente si ferma, descrive l'anomalia, demanda a workflow manutenzione separato.

### 7.3 Disclaimer pattern

```markdown
---
⚠️ DISCLAIMER: Le informazioni prodotte da questo agente sono per scopi
di analisi e ricerca ONLY. Non costituiscono consulenza finanziaria,
sollecitazione all'investimento, o raccomandazione di trading.
Tutti gli investimenti comportano rischio. Consulta un professionista
qualificato prima di prendere decisioni di investimento.
---
```

---

## 8. Osservabilità e Test (Fase J)

### 8.1 Osservabilità minima

- `trace_id` end-to-end
- Eventi: `trader_analysis_request`, `trader_analysis_complete`, `trader_hitl_gate`
- Log JSON strutturato con ticker, intent category, tool invoked, tokens used

### 8.2 Anti-drift obbligatori

Il piano prevede controlli per:
- source-of-truth drift (prompt vs runtime)
- host-native tool drift (deve usare solo proxy MCP)
- pseudo-HITL drift (conferma testuale ≠ HITL)
- self-remediation leakage

### 8.3 Test plan

| Test | Scope | Marker |
|------|-------|--------|
| `test_trader_prompt_contract` | Verifica che il prompt non usi host-native tools, usa solo proxy MCP | unit |
| `test_trader_hitl_gate_wording` | Verifica che il prompt abbia il disclaimer e il pattern HITL reale | unit |
| `test_capability_matrix_yaml` | Verifica allineamento YAML allowed_tools con mcp_catalog | unit |
| `test_mcp_server_connectivity` | Smoke test per ogni MCP server | integration |
| `test_fmp_mcp_basic_quotes` | Verifica che FMP MCP ritorna dati stock | integration |
| `test_fredapi_mcp_basic` | Verifica che FRED MCP ritorna dati macro | integration |
| `test_helium_mcp_news` | Verifica che Helium MCP ritorna news | integration |

---

## 9. Phased Implementation Steps

### Step 0 — Pre-flight & Branch

- [ ] Creare branch `feature/trader-agent-mvp` da `main`
- [ ] Redigere `docs/foundation/decisions/ADR-00XX-trader-agent-introduction.md`
- [ ] Aggiornare wiki log

### Step 1 — MCP Server Setup

- [ ] Verificare tutti gli MCP server smoke-test
- [ ] Aggiornare `.aria/kilocode/mcp.json` con i 4-5 nuovi server
- [ ] Verificare boot senza errori in `bin/aria repl`

### Step 2 — Agent Definition

- [ ] Creare `.aria/kilocode/agents/trader-agent.md`
- [ ] Definire frontmatter con allowed-tools, intent-categories
- [ ] Scrivere body prompt (role, boundary, disclaimer)

### Step 3 — Skill Creation

- [ ] Creare `trading-analysis@1.0.0` SKILL.md
- [ ] Creare `fundamental-analysis@1.0.0` SKILL.md
- [ ] Creare `technical-analysis@1.0.0` SKILL.md
- [ ] Creare `macro-intelligence@1.0.0` SKILL.md
- [ ] Creare `sentiment-analysis@1.0.0` SKILL.md
- [ ] Creare `options-analysis@1.0.0` SKILL.md
- [ ] Creare `crypto-analysis@1.0.0` SKILL.md

### Step 4 — Capability Matrix Update

- [ ] Aggiornare `.aria/config/agent_capability_matrix.yaml`
- [ ] Aggiornare `docs/foundation/agent-capability-matrix.md`

### Step 5 — Test Suite

- [ ] Test unitari per prompt contract
- [ ] Test di integrazione per ogni MCP server
- [ ] Quality gate

### Step 6 — Conductor Update

- [ ] Aggiornare `aria-conductor.md` con `trader-agent` nei sub-agenti disponibili
- [ ] Aggiungere routing rules per intent `finance.*`

### Step 7 — Wiki & ADR

- [ ] Creare `docs/llm_wiki/wiki/trader-agent.md`
- [ ] Aggiornare `docs/llm_wiki/wiki/index.md`
- [ ] Aggiornare `docs/llm_wiki/wiki/log.md`

### Step 8 — Quality Gate & PR

- [ ] `make quality` verde
- [ ] PR verso `main`

---

## 10. Out of Scope

- **Execution reale**: nessun order placement, nessun write su exchange
- **Real money management**: l'agente è consulente, non gestore
- **Auto-trading**: nessuna automazione di strategie
- **Broker integration write**: Alpaca MCP solo in modalità lettura/data
- **Legal advice**: disclaimer obbligatorio su ogni output

---

## 11. Riferimenti

- **TradingAgents** (TauricResearch) — multi-agent trading framework ispiratore
- **FMP MCP Server** — 253+ tools, copre stocks/ETF/crypto/forex/commodities/fundamentals/macro/technical
- **Helium MCP** — news intelligence + ML options pricing
- **mcp-fredapi** — FRED macro data (gold standard)
- **financekit-mcp** — risk metrics (VaR, Sharpe, Sortino)
- **Protocollo**: `docs/protocols/protocollo_creazione_agenti.md`

---

**FINE FOUNDATION PLAN.**

> Prossime azioni:
> 1. HITL utente: approvazione scope e stack MCP
> 2. Se approvato: Step 0 + redigere ADR-00XX
> 3. Eventuale ricerca manuale via ARIA per approfondire best practice multi-agent trading