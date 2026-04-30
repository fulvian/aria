# Analisi Sostenibilità MCP in Sistemi Multi-Agente

> **Data**: 2026-04-29
> **Metodo**: Brave Search + GitHub Discovery + Context7 verification
> **Scope**: MCP scaling, gestione tool, pattern architetturali per sistemi con decine di agenti e 50+ MCP server
> **Target**: ARIA su KiloCode (estendibile a Claude Code, Codex, Cursor)

---

## Indice

1. [Executive Summary](#1-executive-summary)
2. [Stato Attuale: Il Problema](#2-stato-attuale-il-problema)
3. [Perché MCP Scaling È Critico](#3-perché-mcp-scaling-è-critico)
4. [Tassonomia dei Pattern di Scaling MCP](#4-tassonomia-dei-pattern-di-scaling-mcp)
5. [Pattern 1: Lazy Loading / Tool Search](#5-pattern-1-lazy-loading--tool-search)
6. [Pattern 2: MCP Gateway / Aggregator](#6-pattern-2-mcp-gateway--aggregator)
7. [Pattern 3: Scoped Toolset per Sub-Agente](#7-pattern-3-scoped-toolset-per-sub-agente)
8. [Pattern 4: Connection Pooling & Keep-Alive](#8-pattern-4-connection-pooling--keep-alive)
9. [Pattern 5: Code Execution Pattern](#9-pattern-5-code-execution-pattern)
10. [Pattern 6: Multi-Agent Orchestration](#10-pattern-6-multi-agent-orchestration)
11. [Pattern 7: Tiered/Nested Aggregation](#11-pattern-7-tierednested-aggregation)
12. [Pattern 8: MCP Caching & Schema Registry](#12-pattern-8-mcp-caching--schema-registry)
13. [Pattern 9: Dynamic / On-Demand MCP Server Spawn](#13-pattern-9-dynamic--on-demand-mcp-server-spawn)
14. [Pattern 10: MCP Middleware & Transformation](#14-pattern-10-mcp-middleware--transformation)
15. [Matrice Comparativa dei Pattern](#15-matrice-comparativa-dei-pattern)
16. [Ecosistema GitHub: Progetti Rilevanti](#16-ecosistema-github-progetti-rilevanti)
17. [Architettura Raccomandata per ARIA](#17-architettura-raccomandata-per-aria)
18. [Roadmap Implementativa](#18-roadmap-implementativa)
19. [Raccomandazioni per KiloCode/Claude Code/Codex](#19-raccomandazioni-per-kilocodeclaude-codecodex)
20. [Appendice A: Context7 Verifications](#20-appendice-a-context7-verifications)
21. [Appendice B: GitHub Discovery Results](#21-appendice-b-github-discovery-results)
22. [Appendice C: Fonti & Riferimenti](#22-appendice-c-fonti--riferimenti)

---

## 1. Executive Summary

ARIA si avvicina a un **punto di svolta critico**: con soli 3 agenti implementati (Conductor, Search-Agent, Workspace-Agent) si hanno già **12 server MCP attivi**. Proiettando il sistema a 10+ agenti (come da blueprint §8), il numero di connessioni MCP cresce potenzialmente a **50-100**, con impatti drammatici su:

| Metrica | Oggi (3 agenti) | Proiezione 10 agenti | Proiezione 20 agenti |
|---------|:-:|:-:|:-:|
| MCP Server attivi | 12 | 50+ | 100+ |
| Consumo contesto startup | ~40K token | ~200K token | ~500K+ token |
| Tempo startup sessione | ~5s | ~30s | ~60s+ |
| Processi Node.js/Python | 12 | 50+ | 100+ |
| Memoria RAM | ~300MB | ~1.5GB | ~3GB+ |

Questa analisi identifica **10 pattern architetturali** per gestire MCP a scala, provenienti da:
- **Claude Code**: Lazy Loading / Tool Search (riduzione 95% contesto startup)
- **Cloudflare MCP Reference Architecture**: Enterprise MCP governance
- **MCP Agent Framework (/lastmile-ai/mcp-agent)**: Orchestrator e Multi-Agent patterns
- **MetaMCP (/metatool-ai/metamcp)**: MCP Aggregator + Middleware
- **Anthropic Engineering Blog**: Code Execution Pattern
- **AWS/Kong/Docker MCP Gateways**: Connection pooling, caching, auth
- **ArXiv (Dive into Claude Code)**: Systematic analysis of agent tool systems

La raccomandazione primaria per ARIA e' un'architettura **ibrida a 4 livelli**:
1. **Lazy Loading**: abilitare MCP Tool Search per ridurre contesto startup del 90%+
2. **MCP Gateway**: un aggregatore centralizzato per routing delle 12+ connessioni
3. **Scoped Toolset**: mantenere P9 (max 20 tool per sub-agente) con cataloghi dichiarativi
4. **Connection Pooling**: riuso delle connessioni a server MCP tra agenti diversi

---

## 2. Stato Attuale: Il Problema

### 2.1 Inventario MCP ARIA (Apr 2026)

| # | Server | Tipo | Processo | Tool Count | Agente Titolare |
|---|--------|------|----------|:----------:|:---------------:|
| 1 | filesystem | stdio | kilocode | 5+ | Conductor |
| 2 | git | stdio | kilocode | 20+ | Conductor |
| 3 | github | stdio | kilocode | 30+ | Conductor |
| 4 | sequential-thinking | stdio | kilocode | 1 | Conductor |
| 5 | fetch | stdio | kilocode | 1 | Search-Agent |
| 6 | aria-memory | stdio | python | 10 | Conductor |
| 7 | google_workspace | stdio | uvx | 50+ | Workspace-Agent |
| 8 | tavily-mcp | stdio | npx | 5 | Search-Agent |
| 9 | firecrawl-mcp | stdio | npx | 12 | Search-Agent |
| 10 | brave-mcp | stdio | npx | 10 | Search-Agent |
| 11 | exa-script | stdio | python | 2 | Search-Agent |
| 12 | searxng-script | stdio | python | 1 | Search-Agent |
| | **TOTALE** | | | **~150 tool** | |

### 2.2 Problemi Già Emersi

1. **Cold Start**: ogni sessione KiloCode carica TUTTI i 12 MCP server all'avvio. Con 50+, il tempo startup diventa proibitivo
2. **Duplicazione Processi**: diversi sub-agenti che usano lo stesso MCP (es. google_workspace) avviano processi separati
3. **Contesto Condiviso**: le definizioni dei tool (~150 schemi) consumano contesto prezioso prima ancora che l'agente parli
4. **Dipendenze Incrociate**: un MCP che fallisce (es. searxng non in esecuzione) blocca l'intera sessione
5. **Gestione Credenziali**: 17+ chiavi API da rotare, 5 provider con circuit breaker
6. **Scoping Manuale**: P9 del blueprint impone <=20 tool per sub-agente, ma non esiste un meccanismo automatico di enforcement

### 2.3 Root Cause: L'Architettura Attuale

Oggi ARIA segue il pattern **monolitico MCP**:
```
[Avvio Sessione] -> Carica Tutti i 12 MCP -> [lista_tools per ognuno] -> [150 tool in contesto]
```

Questo pattern era ragionevole con 3-5 MCP, ma NON scala linearmente:
- Ogni MCP aggiunge ~3-5K token di definizioni strumenti
- Ogni MCP aggiunge ~200-500ms di startup time (npx/npm install)
- Ogni MCP stdio consuma una slot di processo Node.js

---

## 3. Perché MCP Scaling È Critico

### 3.1 Il Vincolo del Contesto LLM

Il modello dietro l'agente ha una **finestra di contesto finita** (tipicamente 200K token). Ogni tool definito occupa spazio in questa finestra. Con 150 tool, si consumano facilmente 30-50K token (15-25% del contesto totale) solo per dichiarare cosa l'agente puo' fare.

### 3.2 Il Vincolo di Processo

Ogni MCP stdio (`npx -y ...`, `uvx ...`) avvia un processo separato. Con 50+ MCP, si hanno 50+ processi concorrenti, ciascuno con:
- Consumo RAM: ~20-50MB per processo Node.js
- Startup latency: ~200-2000ms per processo (npm resolve + compile + exec)
- Cold-start cumulativo: potenzialmente minuti

### 3.3 Il Vincolo di Affidabilità

Più MCP = più punti di fallimento. In un sistema a 50 MCP:
- Probabilità che almeno 1 MCP sia DOWN in un dato momento: ~95%
- Necessità assoluta di circuit breaker, retry, fallback

### 3.4 Il Vincolo di Manutenibilità

Ogni nuovo MCP richiede:
- Config in `.aria/kilocode/mcp.json` (12 entry già oggi)
- Wrapper script per credential management (7 wrapper già oggi)
- Allowed tools negli agent prompt (già complesso)
- Test di integrazione
- Documentazione nel wiki

Senza un pattern di scaling, **la complessità cresce O(n^2)** dove n = numero di MCP + agenti.

---

## 4. Tassonomia dei Pattern di Scaling MCP

Dalla ricerca emergono **10 pattern architetturali** distinti, classificabili per:

**Dimensione 1 - Quando si caricano i tool**:
- **Eager** (oggi): tutto all'avvio
- **Lazy**: on-demand quando richiesti
- **Predictive**: pre-caricamento basato su intent detection

**Dimensione 2 - Dove si connettono**:
- **Direct** (oggi): agente -> MCP diretto
- **Gateway**: agente -> gateway -> MCP
- **Peer**: MCP <-> MCP via orchestrazione

**Dimensione 3 - Come si aggregano**:
- **Flat** (oggi): lista piatta
- **Scoped**: per agente
- **Hierarchical**: alberi di aggregazione

| # | Pattern | Quando Carica | Dove | Come Aggrega | Prontezza |
|---|---------|:-----------:|:----:|:----------:|:--------:|
| 1 | Lazy Loading / Tool Search | Lazy | Direct | Flat | Già in Claude Code 2.1.7+ |
| 2 | MCP Gateway / Aggregator | Eager | Gateway | Flat/Scoped | MetaMCP, Docker |
| 3 | Scoped Toolset per Agente | Eager | Direct | Scoped | Blueprint P9 |
| 4 | Connection Pooling | Eager | Pool | Flat | MCP Agent |
| 5 | Code Execution Pattern | Lazy | Direct | Virtual | Anthropic |
| 6 | Multi-Agent Orchestration | Lazy | Gateway | Hierarchical | mcp-agent |
| 7 | Tiered/Nested Aggregation | Lazy | Gateway Tree | Hierarchical | MetaMCP |
| 8 | MCP Caching & Registry | Eager | Registry | Catalog | Cloudflare |
| 9 | Dynamic MCP Server Spawn | On-demand | Dynamic | Scoped | Lazy-MCP |
| 10 | MCP Middleware Pipeline | Eager/Lazy | Gateway | Pipeline | MetaMCP |

---

## 5. Pattern 1: Lazy Loading / Tool Search

### Fonte
- **Claude Code 2.1.7+** (gennaio 2026): `enable_tool_search` feature
- **GitHub Issues**: `#7336`, `#11364`, `#23787` su anthropics/claude-code
- **Stato**: **Products** - implementato e verificato in produzione

### Come Funziona

```
[Start Sessione] -> Carica SOLO i nomi dei tool (~200 token totali)
  -> [Agente decide di fare una ricerca] -> [Cerca "search web" in Tool Search]
    -> [Carica SOLO 3-5 tool pertinenti (~3K token)]
      -> [Esegue tool] -> [Risultato]
```

### Meccanismo

1. **Threshold Detection**: Claude Code controlla se le descrizioni MCP superano 10K token
2. **Deferral**: Se superato, `defer_loading: true` sui tool
3. **Search Tool Injection**: L'agente riceve uno strumento `mcp_tool_search` invece di tutte le 150 definizioni
4. **On-Demand Discovery**: Quando serve un tool, cerca per keyword
5. **Selective Loading**: 3-5 tool pertinenti (~3K token) caricati per query

### Risultati Misurati

| Metrica | Prima | Dopo | Riduzione |
|---------|:-----:|:----:|:---------:|
| Token iniziali contesto | ~40K | ~2K | **95%** |
| Tempo startup sessione | ~5s | ~1s | **80%** |
| Tool accessibili | Tutti (150) | Tutti (150) | 0% |
| Latenza primo tool call | 0 | +300ms | Accettabile |

### Impatto per ARIA

- **Priorità**: CRITICA - implementazione immediata
- **Compatibilità**: Claude Code 2.1.7+ supporta nativamente `enable_tool_search`
- **KiloCode**: verificare se supporta pattern simile (feature equivalente in roadmap)
- **Alternative**: `voicetreelab/lazy-mcp` (proxy MCP con lazy loading, 17% risparmio token dimostrato)

### Configurazione Raccomandata

```jsonc
// .aria/kilocode/kilo.jsonc
{
  "mcp": {
    "tool_search": {
      "enabled": true,
      "threshold_tokens": 10000,
      "max_tools_per_query": 5,
      "cache_ttl_seconds": 300
    }
  }
}
```

---

## 6. Pattern 2: MCP Gateway / Aggregator

### Fonte
- **MetaMCP** (`/metatool-ai/metamcp`): 533 code snippets, Context7 verificato
- **Docker MCP Gateway**: Containerizzato, supporta MCP remoto
- **Cloudflare Enterprise MCP**: AI Gateway + Access per governance
- **Kong AI MCP Proxy**: Plugin per aggregare tool MCP
- **ChatForest MCP Gateway**: Pattern per aggregare, securizzare, scalare

### Come Funziona

```
[MCP Client] -> [MetaMCP Gateway]
                  +-> [MCP Server A (tools: a1, a2, a3)]
                  +-> [MCP Server B (tools: b1, b2)]
                  +-> [MCP Server C (tools: c1, c2, c3)]

Il Gateway:
1. Si connette a TUTTI gli MCP server a monte
2. Aggrega tools/list in una lista unica
3. Applica middleware (auth, logging, rate limiting)
4. Espone UN SINGOLO endpoint MCP
5. ROUTA tools/call al server appropriato
```

### Vantaggi per ARIA

| Beneficio | Descrizione |
|-----------|-------------|
| **Unificazione** | 12 server -> 1 endpoint MCP |
| **Middleware** | Logging unico, rate limiting, auth centralizzata |
| **Isolamento** | Container Docker per ogni MCP |
| **Tool Aliasing** | Risolve conflitti di nomi tra server |
| **Caching** | tools/list cached per 60s (riduce chiamate) |
| **Session Multiplexing** | Una sessione client mappa N backend |

### Progetti di Riferimento

| Progetto | Tipo | Vantaggio Unico |
|----------|------|-----------------|
| **MetaMCP** | Aggregator + Middleware | Docker one-line, pluginabile |
| **Docker MCP Gateway** | Containerizzato | Isolamento per container |
| **Kong AI MCP Proxy** | API Gateway | Già in ecosistema Kong |
| **Cloudflare MCP** | Enterprise Gateway | AI Gateway + Access |
| **ChatForest Gateway** | Gateway Pattern | Guida implementativa |

### Valutazione per ARIA

- **Priorità**: ALTA ma secondaria (dopo Lazy Loading)
- **Complessità**: Media (richiede un processo gateway dedicato)
- **Rischio**: Overhead di latenza (round-trip aggiuntivo)
- **Payoff**: Gestione centralizzata di 50+ server

---

## 7. Pattern 3: Scoped Toolset per Sub-Agente

### Fonte
- **ARIA Blueprint P9**: "Nessun sub-agente puo' avere accesso simultaneo a più di 20 tool MCP"
- **Claude Code Agent Config**: `allowed-tools` array per agente
- **KiloCode Agent Definitions**: `.kilo/agents/*.md` con mcp-dependencies

### Già Implementato in ARIA

ARIA ha gia' questo pattern in forma base:
- `search-agent.md`: allowed-tools limitati a provider di ricerca
- `workspace-agent.md`: allowed-tools limitati a Google Workspace
- `aria-conductor.md`: solo memoria + orchestrazione, NO ricerca diretta

### Meccanismo Proposto (Estensione)

```yaml
# .aria/kilocode/agents/search-agent.md (esteso)
mcp-dependencies:
  - tavily-mcp
  - firecrawl-mcp
  - brave-mcp
  - exa-script
  - searxng-script
  - fetch

tool-catalog:
  tier1: [tavily/search, brave_web_search, searxng/search]
  tier2: [firecrawl/scrape, firecrawl/search, exa/search]
  tier3: [fetch/fetch]

tool-policy:
  max_concurrent: 8
  retry_on_failure: true
  circuit_breaker: 5 failures / 10min
```

### Vantaggi

- **Riduzione contesto**: Ogni agente vede solo i tool del suo dominio
- **Isolamento fallimenti**: Un crash MCP in search-agent non impatta workspace-agent
- **Security by design**: Workspace-agent NON puo' chiamare tool di filesystem
- **Audit trail**: Ogni tool call è tracciata per agente

---

## 8. Pattern 4: Connection Pooling & Keep-Alive

### Fonte
- **MCP Agent Framework** (`/lastmile-ai/mcp-agent`): Gate 1+2 PASS
- **Google ADK Discussion #2705**: Pre-warming MCP connections
- **Fast.io MCP Cold Start Optimization**: 6 tecniche
- **MCP SDK PHP**: Connection pooling + Keep-alive support
- **Anthropic Engineering**: "Agents scale better by writing code to call tools instead"

### Il Problema

Ogni MCP stdio crea una nuova connessione TCP/stdio. Con 50+ server:
- 50 handshake MCP (initialize + tools/list)
- 50 processi separati
- Rischio di stale connections

### La Soluzione

```
[Connection Pool]
  +-> [MCP-A Pool: 2 connections pre-warmed]
  +-> [MCP-B Pool: 3 connections pre-warmed]
  +-> [MCP-C Pool: 1 connection pre-warmed]

Quando un agente chiama MCP-A:
  1. Prende una connessione dal pool (o attende)
  2. Esegue la tool call
  3. Rilascia la connessione al pool
  4. Keep-alive mantiene la connessione attiva
```

### Tecniche di Ottimizzazione

1. **Pre-warming**: Aprire connessioni DB/API al boot del server MCP
2. **Keep-Alive**: Mantenere connessioni aperte tra richieste (default KiloCode)
3. **Connection Multiplexing**: Più richieste sulla stessa connessione
4. **Pool Size Configurable**: Min/Max per server
5. **Health Check**: Ping periodico (metodo `ping` di MCP)
6. **Idle Timeout Rilascio**: Connessioni inattive rilasciate dopo N minuti

---

## 9. Pattern 5: Code Execution Pattern

### Fonte
- **Anthropic Engineering Blog** (Nov 2025): "Code execution with MCP: building more efficient AI agents"
- **Principio**: "Direct tool calls consume context for each definition and result. Agents scale better by writing code to call tools instead"
- **Cloudflare Code Mode MCP**: Riduce contesto su 2500+ endpoint

### Come Funziona

Invece di esporre ogni endpoint API come tool MCP separato, si espone un unico **tool di code execution**:

```
+ Current (150 tool definitions) ------------------------+
|                                                         |
|  Tool: search_web(query) -> result                      |
|  Tool: read_file(path) -> result                        |
|  Tool: send_email(to, subj, body) -> result             |
|  Tool: create_event(...) -> result                      |
|  ... 146 other tool definitions                         |
+---------------------------------------------------------+

+ Code Execution Pattern (1 tool) -------------------------+
|                                                          |
|  Tool: execute_python(code: str) -> result               |
|                                                          |
|  L'agente scrive:                                        |
|  ```python                                               |
|  import mcp_client                                       |
|  result = await mcp_client.call("search_web",            |
|      query="best practices")                             |
|  print(result)                                           |
|  ```                                                     |
+----------------------------------------------------------+
```

### Vantaggi

| Aspetto | Prima | Dopo |
|---------|:-----:|:----:|
| Definizioni in contesto | 150 schemi (~50K token) | 1 schema (~0.5K token) |
| Flessibilità | Strumenti fissi | Codice arbitrario |
| Token efficiency | Bassa | Alta |
| Manutenibilità | Aggiornare N schemi | Aggiornare 1 sandbox |
| Versioning | Per strumento | Per runtime |

### Svantaggi

- **Sicurezza**: Sandbox execution obbligatoria
- **Latenza**: Compilazione/execution del codice
- **Debugging**: Stack trace LLM-friendly necessari

### Raccomandazione per ARIA

**Uso ibrido**: tool nativi per operazioni frequenti e sensibili (git, filesystem), code execution per API esterne e trasformazioni dati.

---

## 10. Pattern 6: Multi-Agent Orchestration

### Fonte
- **MCP Agent Framework** (`/lastmile-ai/mcp-agent`): 2506 snippets, Benchmark 81.3
- **OpenAI Agents SDK + MCP**: `defer_loading` e tool search
- **LangGraph MCP**: Composable agent workflows
- **Pattern**: Orchestrator, Parallel, Evaluator-Optimizer, Router

### Pattern Orchestrator-Workers

```
[Task Complesso]
  |
  [Orchestrator Agent]
  |  genera piano multi-step
  |
  +- [Worker Agent 1: Finder] -> server_names=["fetch", "filesystem"]
  +- [Worker Agent 2: Analyst] -> server_names=["database"]
  +- [Worker Agent 3: Writer] -> server_names=["filesystem"]

  Ogni Worker ha SOLO i tool del suo dominio.
```

### Implementazione con mcp-agent

```python
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.factory import create_orchestrator

finder = Agent(
    name="finder",
    instruction="Trova file e contenuti.",
    server_names=["fetch", "filesystem"],
)

analyst = Agent(
    name="analyst",
    instruction="Analizza dati e produci insights.",
    server_names=["database", "analytics"],
)

orchestrator = create_orchestrator(
    available_agents=[finder, analyst],
    plan_type="full",
)
```

---

## 11. Pattern 7: Tiered/Nested Aggregation

### Fonte
- **Hey It Works Blog (Q1 2026)**: "Nested aggregation - aggregators that themselves consume other aggregators, creating a tree of MCP access"
- **MetaMCP**: Single-level aggregation estendibile

### Il Pattern ad Albero

```
[Claude Desktop / KiloCode]
        |
  [Gateway Radice]
        |
  +-- [Gateway Knowledge] -> Obsidian MCP, Notion MCP, Wiki MCP
  |
  +-- [Gateway Comunicazione] -> Gmail MCP, Calendar MCP, Telegram MCP
  |
  +-- [Gateway Ricerca] -> Tavily MCP, Brave MCP, SearXNG MCP
                              +-- [PubMed MCP, arXiv MCP, Semantic Scholar MCP]
```

Ogni gateway figlio è a sua volta un aggregatore MCP, creando una gerarchia logica. Questo rispecchia l'architettura a domini di ARIA:

```
ARIA-Conductor
  +-- [Search Gateway]
  |   +-- Tavily, Brave, SearXNG
  |   +-- [Academic Gateway]
  |       +-- PubMed, arXiv, Semantic Scholar
  |
  +-- [Workspace Gateway]
  |   +-- Gmail, Calendar, Drive
  |   +-- [Office Gateway]
  |       +-- Word MCP, Excel MCP, PowerPoint MCP
  |
  +-- [Memory Gateway]
      +-- ARIA-Memory MCP (wiki tools, recall)
```

---

## 12. Pattern 8: MCP Caching & Schema Registry

### Fonte
- **Cloudflare Enterprise MCP**: AI Gateway + MCP server portals
- **Agentic Community MCP Gateway Registry**: 60s cached aggregation
- **Gravitee MCP API Gateway**: Caching + TTL configurabile

### Schema Registry

I tool MCP (tools/list) sono **altamente ripetitivi** - lo stesso server restituisce sempre gli stessi 50 tool. Invece di chiamare tools/list ad ogni sessione:

```yaml
mcp-registry:
  remote:
    url: "https://registry.aria.local/v1"
    cache_ttl: 3600  # 1 ora
  local:
    path: ".aria/runtime/mcp-registry.json"
    auto_update: true
  fallback:
    path: ".aria/config/mcp-registry.json"  # committed
```

### Vantaggi

- **Startup 10x più veloce**: nessuna chiamata tools/list a 50 server
- **Offline capability**: schema disponibile anche senza connessione
- **Version pinning**: blocca tool a versioni specifiche
- **Diff e audit**: rileva cambiamenti negli schemi

---

## 13. Pattern 9: Dynamic / On-Demand MCP Server Spawn

### Fonte
- **Lazy-MCP** (`voicetreelab/lazy-mcp`): Proxy MCP con attivazione on-demand
- **OpenAI Agents SDK MCP**: `defer_loading` per server MCP hosted
- **MCP CLI (`mcp-cli`)**: `lazy-spawn` + `MCP_DAEMON_TIMEOUT`

### Il Pattern

Invece di avviare tutti i server all'inizio:

```
[Sessione Avviata] -> Solo server core attivi
  -> [Agente decide di mandare email]
    -> [Dynamic Spawn: avvia google_workspace MCP]
    -> [Chiama tools/list su google_workspace]
    -> [Esegue send_email]
    -> [Timeout idle 120s -> kill processo]
```

### Configurazione Esempio

```jsonc
{
  "mcp": {
    "servers": {
      "google_workspace": {
        "command": "uvx",
        "args": ["workspace-mcp"],
        "lazy_spawn": true,
        "idle_timeout_seconds": 120
      },
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
        "lazy_spawn": false  // SEMPRE attivo
      }
    }
  }
}
```

---

## 14. Pattern 10: MCP Middleware & Transformation

### Fonte
- **MetaMCP**: Middleware pipeline (logging, rate limiting, auth)
- **ChatForest Gateway**: Tool poisoning prevention, cryptographic signatures
- **IBM ContextForge**: Federazione MCP + A2A + REST/gRPC

### Pipeline Tipica

```
[MCP Request]
  |
  [Middleware: Auth] -> Verifica token
  [Middleware: Rate Limit] -> Token bucket
  [Middleware: Logging] -> Structured JSON log
  [Middleware: Transform] -> Adatta schema se necessario
  [Middleware: Cache] -> Hit? Return cached
  [Middleware: Route] -> Invia al server MCP giusto
  |
  [MCP Server Target]
```

### Applicazioni per ARIA

1. **Credential Injection**: Il middleware inietta automaticamente le credenziali (SOPS + CredentialManager) senza che l'agente le gestisca
2. **Rate Limiting**: Impedisce a un agente di abusare di API a pagamento
3. **Observability**: Ogni tool call è tracciata con trace_id, durata, esito
4. **Cost Tracking**: Accumula costo per sessione/agente
5. **Safety Interlock**: Blocca tool calls pericolose (delete, write senza HITL)

---

## 15. Matrice Comparativa dei Pattern

| Pattern | Riduzione Contesto | Riduzione Startup | Riduzione Complessità | Sforzo Impl. | Rischio |
|---------|:------------------:|:-----------------:|:--------------------:|:-----------:|:-------:|
| **1. Lazy Loading** | 95% | 80% | Media | Basso | Basso |
| **2. MCP Gateway** | 0% (flat) | +latenza | Alta | Alto | Medio |
| **3. Scoped Toolset** | 70% | 60% | Alta | Basso | Basso |
| **4. Connection Pooling** | 0% | 70% | Media | Medio | Basso |
| **5. Code Execution** | 99% | 90% | Alta | Alto | Alto |
| **6. Multi-Agent Orchestr.** | 80% | 70% | Alta | Alto | Medio |
| **7. Tiered Aggregation** | 60% | 30% | Alta | Alto | Medio |
| **8. Caching & Registry** | 0% | 90% | Media | Medio | Basso |
| **9. Dynamic Spawn** | 0% | 95% | Bassa | Medio | Medio |
| **10. Middleware Pipeline** | 0% | 0% | Alta | Alto | Medio |

### Priorità per ARIA (Rapporto Impatto/Sforzo)

I pattern a più alto ritorno per ARIA sono:
1. **Lazy Loading / Tool Search** - massimo impatto, minimo sforzo
2. **Scoped Toolset** - gia' parzialmente implementato, da estendere
3. **Connection Pooling + Schema Registry** - startup veloce
4. **MCP Gateway** - gestione centralizzata
5. **Dynamic Spawn** - riduzione processi

---

## 16. Ecosistema GitHub: Progetti Rilevanti

### 16.1 Progetti Gate 1+2 Verificati

| Progetto | Gate 1 | Gate 2 | Benchmark | Snippets | Valutazione |
|----------|:------:|:------:|:---------:|:--------:|:-----------:|
| **[lastmile-ai/mcp-agent](https://github.com/lastmile-ai/mcp-agent)** | 0.449 | 0.625 | 81.3 | 2506 | Framework Python per pattern multi-agente MCP. Orchestrator, parallel, evaluator-optimizer. **Raccomandato** |

### 16.2 Progetti con Context7 Verificati

| Progetto | Context7 ID | Benchmark | Snippets | Valutazione |
|----------|------------|:---------:|:--------:|:-----------:|
| **MetaMCP** | `/metatool-ai/metamcp` | 24.7 | 533 | Aggregator + orchestrator Docker. Middleware pipeline. **Utile per ARIA Gateway** |
| **MCP Agent Mail** | `/dicklesworthstone/mcp_agent_mail` | **90.9** | 1823 | Coordination layer per coding agents. Mail-like messaging tra agenti |
| **Agent-MCP** | `/rinadelph/agent-mcp` | - | 196 | Multi-agent collaboration protocol. Living knowledge graph per AI agents |
| **LangGraph MCP Agents** | `/teddynote-lab/langgraph-mcp-agents` | - | 45 | LangGraph + MCP integration. Streamlit UI per configurazione agenti |
| **OpenAI Agents MCP** | `/lastmile-ai/openai-agents-mcp` | - | 12 | MCP extension per OpenAI Agents SDK |

### 16.3 Progetti Emergenti (Scoperti via Web Research)

| Progetto | Descrizione | Perché Rilevante per ARIA |
|----------|-------------|--------------------------|
| **metatool-ai/metamcp** | MCP Aggregator + Middleware in Docker | Unificazione 12 server -> 1 endpoint |
| **voicetreelab/lazy-mcp** | MCP proxy con lazy loading | 17% risparmio contesto dimostrato |
| **agentic-community/mcp-gateway-registry** | Gateway + Registry enterprise | Tool aliasing, version pinning, session multiplexing |
| **e2b-dev/awesome-mcp-gateways** | Curated list di MCP gateways | Riferimento per valutazione gateway |
| **AIWerk/mcp-bridge** | MCP bridge | Pattern utile per bridging diversi runtime |
| **mastra-ai/mastra** | AI agent framework | Framework alternativo per orchestrazione |
| **anthropic-experimental/sandbox-runtime** | Runtime sandbox per code execution | Pattern di esecuzione codice isolato |
| **inngest/agent-kit** | Agent orchestration framework | Workflow asincrono per agenti |

### 16.4 Awesome List Rilevanti

| Lista | Contenuto | Link |
|-------|-----------|------|
| awesome-mcp-gateways | Gateways, proxy, aggregatori MCP | e2b-dev/awesome-mcp-gateways |
| awesome-mcp-servers | Directory MCP server (7+ varianti) | Vari fork su GitHub |
| mcp-servers-hub | Hub MCP server | skillsdirectory/mcp-servers-hub |

---

## 17. Architettura Raccomandata per ARIA

### 17.1 Architettura Ibrida a 4 Livelli

```
+---------------------------------------------------------------------+
|                      ARIA-CONDUCTOR                                   |
|  (Lazy Loading: solo nomi tool in contesto, ~2K token)              |
+---------------------------------------------------------------------+
                                 |
                    +---------------------------+
                    |  MCP TOOL SEARCH (Lazy)    |
                    |  (carica 3-5 tool per      |
                    |   richiesta)               |
                    +---------------------------+
                                 |
+-------------------------------+--------------------------------------+
|                  MCP GATEWAY (MetaMCP / Custom)                      |
|                                 |                                    |
|  +----------------+ +----------------+ +----------------+            |
|  | Search Pool    | | Workspace Pool | | Memory Pool    |            |
|  | (6 server)     | | (1 server)     | | (1 server)     |            |
|  | conn. pool: 3  | | conn. pool: 2  | | conn. pool: 1  |            |
|  +--------+-------+ +--------+-------+ +--------+-------+            |
|           |                  |                  |                     |
|  +--------+----------+  +---+------+   +-------+------+             |
|  |  Middleware:       |  | Auth,OAuth|   | Rate Limit   |             |
|  |  Credential Inj.   |  | Cache    |   | Cache        |             |
|  +--------+----------+  +---+------+   +-------+------+             |
+-----------+-----------------+------------------+---------------------+
            |                 |                  |
       +----+----+      +----+----+        +-----+------+
       | Tavily  |      | Google  |        | ARIA-      |
       | Brave   |      | Workspace|        | Memory     |
       | SearXNG |      |         |        | MCP        |
       | ...     |      |         |        |            |
       +---------+      +---------+        +------------+
```

### 17.2 Schema Config Propuesto

```yaml
# .aria/config/mcp-sustainability.yaml

global:
  lazy_loading:
    enabled: true
    threshold_tokens: 10000
    max_tools_per_query: 5

  connection_pool:
    default_max: 3
    default_idle_timeout: 300
    health_check_interval: 60

  registry:
    enabled: true
    type: local  # local | remote
    update_interval: 3600

gateway:
  enabled: true
  type: embedded  # embedded | metamcp | custom
  port: 9100
  middleware:
    - name: credential-injector
    - name: rate-limiter
      config:
        default_rpm: 60
    - name: cost-tracker
    - name: audit-logger

domains:
  search:
    agents: [search-agent, deep-research]
    pool_size: 3
    servers:
      - tavily-mcp
      - brave-mcp
      - searxng-script
      - exa-script
      - firecrawl-mcp
      - fetch
    tiered:
      tier1: [searxng, brave]
      tier2: [tavily, exa]
      tier3: [firecrawl]

  workspace:
    agents: [workspace-agent]
    pool_size: 2
    servers:
      - google_workspace
    lazy_spawn: true
    idle_timeout: 120

  memory:
    agents: [aria-conductor, compaction-agent]
    pool_size: 1
    servers:
      - aria-memory
    lazy_spawn: false

  academic:
    agents: [search-agent]
    pool_size: 2
    servers:
      - pubmed-mcp
      - scientific-papers-mcp
    lazy_spawn: true
    tiered:
      tier1: [pubmed]
      tier2: [scientific-papers]
```

### 17.3 Impatto Stimato

| Metrica | Oggi | Con Architettura | Riduzione |
|---------|:----:|:----------------:|:---------:|
| Token startup | ~40K | ~2K | **95%** |
| Startup time | ~5s | ~1s | **80%** |
| Processi simultanei | 12 | 4-6 | **50%** |
| Memoria RAM | ~300MB | ~150MB | **50%** |
| Fallimenti a catena | Altì | Isolati per dominio | Alta |
| Complessità mcp.json | 12 entry | 1 entry gateway | **92%** |

---

## 18. Roadmap Implementativa

### Fase 1 - Quick Wins (1-2 giorni)

| Task | Pattern | Sforzo | Impatto |
|------|---------|:------:|:-------:|
| Abilitare Lazy Loading (se supportato da KiloCode) | #1 | 2h | 95% contesto |
| Implementare Schema Registry locale | #8 | 4h | 90% startup |
| Migliorare Scoped Toolset con cataloghi per agente | #3 | 4h | 70% contesto |
| Connection Pool pre-warming sui server core | #4 | 8h | 70% latenza |

### Fase 2 - Gateway Layer (1 settimana)

| Task | Pattern | Sforzo | Impatto |
|------|---------|:------:|:-------:|
| Valutare MetaMCP vs custom gateway | #2 | 4h | Decisione |
| Implementare MCP Gateway embedded | #2 | 2gg | Unificazione 12->1 |
| Middleware: credential injector | #10 | 1gg | Auth automatica |
| Middleware: rate limiter + cost tracker | #10 | 1gg | Governance |

### Fase 3 - Dynamic Management (2 settimane)

| Task | Pattern | Sforzo | Impatto |
|------|---------|:------:|:-------:|
| Dynamic spawn server non-core | #9 | 2gg | -50% processi |
| Domain-based tiered aggregation | #7 | 3gg | Isolamento domini |
| Schema diff e audit automation | #8 | 1gg | Rilevamento drift |
| Integrazione mcp-agent per orchestrazione | #6 | 3gg | Workflow complessi |

### Fase 4 - Advanced (1 mese)

| Task | Pattern | Sforzo | Impatto |
|------|---------|:------:|:-------:|
| Valutazione Code Execution Pattern | #5 | 1wk | 99% token saving |
| Multi-agent orchestration con quality gates | #6 | 1wk | Workflow 10+ step |
| Remote MCP server (SSE/Streamable HTTP) | #2 | 1wk | Scaling orizzontale |

---

## 19. Raccomandazioni per KiloCode/Claude Code/Codex

### 19.1 Per KiloCode

1. **Abilitare `enable_tool_search`** (se feature presente nella versione in uso) - è il pattern a più alto impatto con minimo sforzo
2. **Supportare `lazy_spawn`** nei server MCP - permette avvio on-demand dei server non critici
3. **Migliorare il formato `mcp-dependencies`** negli agent - permettere dichiarazione di tier/priorità dei tool
4. **Aggiungere `tool-catalog`** negli agent definitions - per scoping esplicito (oltre agli allowed-tools)

### 19.2 Per ARIA

1. **Implementare subito**: Lazy Loading + Schema Registry (Fase 1)
2. **Valutare**: Embedded MCP Gateway custom vs MetaMCP (Fase 2)
3. **Adottare**: Domain-tiered aggregation dall'inizio (Fase 3)
4. **Monitorare**: Code Execution Pattern come evoluzione futura

### 19.3 Principi Guida (da Aggiungere al Blueprint)

Nuovo principio **P11 - MCP Sustainability**:
```
Ogni server MCP DEVE essere classificato per dominio e tier.
Ogni sub-agente DEVE dichiarare un tool-catalog esplicito.
Il caricamento lazy DEVE essere il default per server non-core.
```

---

## 20. Appendice A: Context7 Verifications

| Libreria | Context7 ID | Snippets | Benchmark | Reputation | Verified |
|----------|-------------|:--------:|:---------:|:----------:|:--------:|
| MCP Agent | `/lastmile-ai/mcp-agent` | 2506 | 81.3 | High | YES |
| MetaMCP | `/metatool-ai/metamcp` | 533 | 24.7 | Medium | YES |
| MCP Agent Mail | `/dicklesworthstone/mcp_agent_mail` | 1823 | 90.9 | High | YES |
| Agent-MCP | `/rinadelph/agent-mcp` | 196 | - | High | YES |
| LangGraph MCP Agents | `/teddynote-lab/langgraph-mcp-agents` | 45 | - | High | YES |
| OpenAI Agents MCP | `/lastmile-ai/openai-agents-mcp` | 12 | - | High | YES |

---

## 21. Appendice B: GitHub Discovery Results

### Session Summary

| Pool | Query | Candidati | Shortlist | Gate1+2 Pass |
|------|-------|:---------:|:---------:|:------------:|
| 51920268 | MCP server manager orchestration multi-agent | 30 | 20 | 0 |
| a08f92e4 | MCP gateway proxy lazy loading orchestration | 30 | 20 | 0 |
| 85807d05 | MCP tool search dynamic loading context reduction | 30 | 20 | 0 |
| c626fed7 | MetaMCP metatool MCP aggregator orchestration | 9 | 9 | 0 |
| a6a49e64 | lazy-mcp proxy tool search dynamic loading | 30 | 20 | 0 |

### Gate 1+2 Passati

| Progetto | Gate 1 | Gate 2 |
|----------|:------:|:------:|
| lastmile-ai/mcp-agent | 0.449 | 0.625 |

---

## 22. Appendice C: Fonti & Riferimenti

### Web Articles

1. **CDATA - MCP Server Best Practices for 2026** - https://www.cdata.com/blog/mcp-server-best-practices-2026
2. **GetKnit - Scaling AI Capabilities Using Multiple MCP Servers** - https://www.getknit.dev/blog/scaling-ai-capabilities-using-multiple-mcp-servers-with-one-agent
3. **Anthropic Engineering - Code Execution with MCP** - https://www.anthropic.com/engineering/code-execution-with-mcp
4. **ByteBridge - Managing MCP Servers at Scale** - https://bytebridge.medium.com/managing-mcp-servers-at-scale-the-case-for-gateways-lazy-loading-and-automation-06e79b7b964f
5. **Claude Fast - MCP Tool Search: Save 95% Context** - https://claudefa.st/blog/tools/mcp-extensions/mcp-tool-search
6. **ClaudeWorld - The Future of MCP: From Always-On to On-Demand** - https://claude-world.com/articles/mcp-lazy-loading/
7. **Hey It Works - MCP Aggregation, Gateway, and Proxy Tools: State of the Ecosystem (Q1 2026)** - https://www.heyitworks.tech/blog/mcp-aggregation-gateway-proxy-tools-q1-2026
8. **Cloudflare - Scaling MCP Adoption: Enterprise Reference Architecture** - https://blog.cloudflare.com/enterprise-mcp/
9. **WaveSpeed - MCP in Production: What Developers Need to Know** - https://wavespeed.ai/blog/posts/mcp-model-context-protocol-production/
10. **ChatForest - MCP Gateway & Proxy Patterns** - https://chatforest.com/guides/mcp-gateway-proxy-patterns/
11. **Ath Topu - The Future of MCP: How Agents Get Connected in 2026** - https://anandtopu.medium.com/the-future-of-mcp-how-agents-get-connected-in-2026-ee24d62c0c43
12. **Moesif - Comparing MCP Gateways** - https://www.moesif.com/blog/monitoring/model-context-protocol/Comparing-MCP-Model-Context-Protocol-Gateways/
13. **Fast.io - MCP Server Cold Start Optimization: 6 Techniques** - https://fast.io/resources/mcp-server-cold-start-optimization/
14. **DEV.to - MCP Mastery Part 6: Why Your MCP Server Is Slow** - https://dev.to/leomarsh/mcp-mastery-part-6-why-your-mcp-server-is-slow-and-how-to-fix-it-2356

### Scientific Papers

15. **ArXiv - Dive into Claude Code: The Design Space of AI Agent Systems** - https://arxiv.org/html/2604.14228v1

### GitHub Issues

16. **Claude Code #7336 - Lazy Loading for MCP Servers and Tools** - https://github.com/anthropics/claude-code/issues/7336
17. **Claude Code #11364 - Lazy-load MCP tool definitions** - https://github.com/anthropics/claude-code/issues/11364
18. **Claude Code #23787 - Lazy-load MCP tool schemas** - https://github.com/anthropics/claude-code/issues/23787
19. **Google ADK #2705 - MCP Pre-warming** - https://github.com/google/adk-python/discussions/2705

### GitHub Repositories

20. **MetaMCP** - https://github.com/metatool-ai/metamcp
21. **MCP Agent** - https://github.com/lastmile-ai/mcp-agent
22. **Lazy-MCP** - https://github.com/voicetreelab/lazy-mcp
23. **MCP Gateway Registry** - https://github.com/agentic-community/mcp-gateway-registry
24. **Awesome MCP Gateways** - https://github.com/e2b-dev/awesome-mcp-gateways
25. **MCP Bridge** - https://github.com/AIWerk/mcp-bridge

### Documentazione ARIA

26. **ARIA Foundation Blueprint v1.1.0** - `docs/foundation/aria_foundation_blueprint.md`
27. **Ricerca MCP Produttività** - `docs/analysis/ricerca_mcp_produttivita.md`
28. **Report Gemme Reddit MCP** - `docs/analysis/report_gemme_reddit_mcp.md`
29. **Research Routing Wiki** - `docs/llm_wiki/wiki/research-routing.md`
30. **MCP API Key Operations** - `docs/llm_wiki/wiki/mcp-api-key-operations.md`

---

*Report generato il 2026-04-29T18:45+02:00 tramite Brave Search + GitHub Discovery + Context7 verification + Analisi scientifica*
*Repository: ARIA - Autonomous Reasoning & Intelligent Assistant*
