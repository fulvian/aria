# Analisi Comparativa: MCP Tool Search Proxy per ARIA

**Data**: 2026-05-01  
**Versione**: 1.0  
**Oggetto**: Analisi approfondita dei due candidati per implementare un MCP Tool Search Proxy in sostituzione del Lazy Loader attuale (Opzione A: `fussraider/tool-search-tools-mcp` vs Opzione B: `rupinder2/mcp-orchestrator`).

---

## Indice

1. [Contesto](#1-contesto)
2. [Metodologia di analisi](#2-metodologia-di-analisi)
3. [Opzione A: tool-search-tools-mcp](#3-opzione-a-tool-search-tools-mcp)
4. [Opzione B: mcp-orchestrator](#4-opzione-b-mcp-orchestrator)
5. [Matrice comparativa](#5-matrice-comparativa)
6. [Implicazioni di integrazione in ARIA](#6-implicazioni-di-integrazione-in-aria)
7. [Raccomandazione finale](#7-raccomandazione-finale)

---

## 1. Contesto

ARIA attualmente ha **14 server MCP attivi** su 4 domini (system, search, productivity, browser), con ~100+ definizioni tool. L'architettura attuale è **eager/monolitica**: tutti i 14 server vengono caricati all'avvio, consumando ~40K token di contesto (20% della finestra 200K).

Il **Lazy Loader** (`src/aria/launcher/lazy_loader.py`) è stato implementato come workaround per filtrare i server basandosi su `intent_tags` nel catalogo YAML. Tuttavia:
- Richiede di conoscere gli intent a priori
- Non è adattivo a runtime
- Filtra solo a livello di server (quelli caricati consumano comunque tutto il loro contesto)
- Riduzione stimata solo del 30-50%

La soluzione target è un **MCP Tool Search Proxy** che espone 1-2 tool al client (`search_tools` + `call_tool`), caricando le definizioni dei tool on-demand con una riduzione del ~95% del contesto startup.

KiloCode **NON supporta nativamente** `tool_search` né `defer_loading` (feature solo di Claude Code 2.1.7+): serve un proxy.

---

## 2. Metodologia di analisi

L'analisi è condotta su:
- **Codice sorgente** completo di entrambi i repository (letto via GitHub API)
- **Struttura directory** e organizzazione moduli
- **Dipendenze** (package.json, pyproject.toml)
- **Test** (vitest per Opzione A, pytest per Opzione B)
- **Documentazione** e README
- **File di configurazione**

I due candidati sono stati valutati su 8 dimensioni:
1. Architettura e design
2. Qualità e copertura del codice
3. Maturità e manutenibilità
4. Ricerca e qualità dei risultati
5. Gestione errori e robustezza
6. Dipendenze e impatto operativo
7. Integrabilità con ARIA
8. Community e sostenibilità

---

## 3. Opzione A: tool-search-tools-mcp

**Repository**: https://github.com/fussraider/tool-search-tools-mcp  
**Linguaggio**: TypeScript 5.9 / Node.js 22+  
**Package Manager**: pnpm  
**Versione**: 0.2.2  
**Licenza**: MIT  
**Build**: tsc (ES2022, NodeNext)  
**Test**: vitest (4 test, 2 file)  
**CI**: GitHub Actions (badge presente nel README)  
**Ultimo aggiornamento**: 2026-04-06  

### 3.1 Struttura del codice

```
tool-search-tools-mcp/
├── src/
│   ├── server.ts            # Entry point MCP (~200 linee)
│   ├── cli.ts               # CLI test utility (~100 linee)
│   ├── mcp/
│   │   ├── registry.ts      # Registro server + tool (~300 linee)
│   │   ├── search.ts        # Ricerca ibrida (fuse + vector) (~260 linee)
│   │   ├── executor.ts      # Esecuzione tool + skills (~30 linee)
│   │   ├── skills.ts        # Motore skills YAML (~180 linee)
│   │   └── _tests_/
│   │       ├── search-integration.test.ts  # Test ricerca
│   │       └── embeddings-cache.test.ts    # Test cache embeddings
│   └── utils/
│       ├── embeddings.ts    # Generazione/ caching embeddings (~250 linee)
│       ├── logger.ts        # Logger strutturato (~120 linee)
│       ├── text.ts          # NLP: tokenize, normalizza, keywords (~50 linee)
│       └── _tests_/       # (vuoto)
├── tests/
│   └── skills.test.ts       # Test skills (~200 linee)
├── mcp-config.json          # Config server backend (esempio)
├── skills.yaml              # Skills esempio
├── package.json
├── tsconfig.json
└── pnpm-lock.yaml
```

**Totale**: ~1.900 linee di TypeScript, 3 file di test.

### 3.2 Architettura

```
                    tool-search-tools-mcp
                    ┌─────────────────────┐
     ┌──────────────┤  McpServer (server) ├──────────────┐
     │              └──────────┬──────────┘              │
     │                         │                          │
     ▼                         ▼                          ▼
┌──────────┐          ┌──────────────┐          ┌──────────────┐
│ search_tools │      │  call_tool   │          │   skills    │
│ (tool MCP)  │      │ (tool MCP)   │          │   (macro)   │
└──────┬──────┘      └──────┬───────┘          └──────┬───────┘
       │                    │                          │
       ▼                    ▼                          │
┌──────────┐          ┌───────────┐                    │
│  search  │          │ executor  │                    │
│ (fuse.js)│          │           │                    │
│ (vector) │          └─────┬─────┘                    │
└──────────┘                │                          │
                            ▼                          ▼
                    ┌──────────────────┐        ┌──────────┐
                    │  MCPRegistry    │        │ skills   │
                    │  (registry.ts)  │        │ engine   │
                    │                 │        └──────────┘
                    │  Gestisce:      │
                    │  - Client MCP   │
                    │  - StdioClient  │
                    │  - ToolMap      │
                    │  - Embeddings   │
                    └────────────────┘
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
       Server A        Server B        Server C
       (stdio)         (stdio)         (stdio)
```

### 3.3 Flusso di esecuzione

1. **Avvio** (`server.ts:start()`):
   - Legge `mcp-config.json` (14 server per ARIA)
   - Per ogni server: crea `StdioClientTransport` + `Client` SDK, chiama `listTools()`, registra tool in `MCPRegistry`
   - Se `MCP_SEARCH_MODE=vector`: genera embeddings per ogni tool (locale, `Xenova/all-MiniLM-L6-v2`), caching su disco
   - Se skills YAML presente: carica skills come tool virtuali
   - Registra i 2 tool esposti al client: `search_tools` e `call_tool`

2. **Ricerca** (`search.ts`):
   - **Modalità fuzzy** (default): `fuse.js` con pesi (name 0.5, description 0.3, keywords 0.15, server 0.05)
   - **Modalità vettoriale** (`MCP_SEARCH_MODE=vector`): coseno-similarità con soglia 0.35, `transformers.js` locale
   - Cache dell'istanza Fuse con `WeakMap` invalidata su `updatedAt`
   - Fallback: se pochi risultati, tokenizza query e ritenta parola per parola
   - Risultati ordinati per peso match (count keyword + score Fuse)

3. **Esecuzione** (`executor.ts`):
   - Se tool.isSkill → `executeSkill()` (macro con variabili `{{var}}`, multi-step)
   - Altrimenti → `client.callTool({name, arguments})` sul client MCP SDK del server
   - Risultato pass-through (nessuna trasformazione)

4. **Skills** (`skills.ts`):
   - YAML caricato e validato con Zod
   - Variabili risolte con regex `{{var}}` (ricorsivo su oggetti annidati)
   - `result_var` per passaggio dati tra step
   - Estrazione text da risposte MCP standard (`content[0].text`)

5. **Embeddings** (`embeddings.ts`):
   - Modello locale: `Xenova/all-MiniLM-L6-v2` (384 dimensioni)
   - Pipeline singleton lazy (`getPipeline()`)
   - Cache persistente su disco in `.cache/embeddings/{sha256}.json`
   - Cache streamed (buffer 1MB) per file grandi
   - Cleanup automatico degli hash orfani
   - Calcolo memoria: `Float32Array` + stima overhead

### 3.4 Modello dati

```typescript
type MCPTool = {
    server: string
    name: string
    description: string
    schema: any            // JSON Schema input
    schemaKeywords?: string
    normalizedText?: string
    client?: Client        // SDK Client (condiviso per server)
    embedding?: Float32Array | number[]
    isSkill?: boolean
    steps?: SkillStep[]
}
```

Lo stesso client SDK è condiviso tra tutti i tool di uno stesso server (efficienza).

### 3.5 Punti di forza

- **Ricerca ibrida**: fuzzy + vettoriale locale. Il vettoriale cattura relazioni semantiche che il fuzzy perde.
- **Embedding locale**: `transformers.js` con modello ONNX, zero chiamate esterne, privacy garantita.
- **Caching persistente**: embeddings su disco evitano rigenerazione a ogni avvio.
- **Skills YAML**: composizione multi-tool con variabili, utile per macro ARIA-specifiche.
- **Zero dipendenze esterne runtime**: tutto il NLP è on-device (nessuna API esterna).
- **Logging strutturato**: scoped logger con livelli DEBUG/INFO/WARN/ERROR, output file o stderr.
- **Gestione errori differenziata**: ENOENT graceful, parse JSON fallito, server crash.
- **Concorrenza limitata**: batch di 10 connessioni parallele (`CONCURRENCY_LIMIT=10`).
- **Shutdown graceful**: process.exit solo su errore critico di startup.

### 3.6 Criticità

- **Config statico**: `mcp-config.json` non supporta variabili d'ambiente per credenziali (`${VAR}`). Per ARIA servirebbe injection da CredentialManager.
- **Nessun health-check**: se un server backend crasha, il client SDK potrebbe non recuperare.
- **Nessuna timeout configurabile**: le connessioni stdio non hanno timeout esplicito.
- **Test limitati**: 3 file di test, coverage basso. Skills test mocka completamente executeTool.
- **Embedding generato su CPU**: `transformers.js` con modello ~22MB, primo avvio lento (download + compilazione ONNX).
- **Logging con emoji**: le emoji nei log (🟪🟦🟧🟥) sono poco professionali per un sistema produttivo.
- **Maturità bassa**: versione 0.2.2, ultimo commit 6 aprile 2026, unico contributor.
- **Nessun namespacing**: se due server espongono tool con lo stesso nome, il `_toolsByNameMap` li accumula ma `_toolMap` usa `server:name`.
- **Gestione errori nelle skills**: un passo fallito non fa rollback degli step precedenti.
- **Mancanza di metriche**: nessun conteggio di chiamate, latenza, error rate.

---

## 4. Opzione B: mcp-orchestrator

**Repository**: https://github.com/rupinder2/mcp-orchestrator  
**Linguaggio**: Python 3.11+  
**Package Manager**: uv (con hatchling build)  
**Versione**: 0.1.2  
**Licenza**: MIT  
**Build**: hatchling  
**Test**: pytest + pytest-asyncio (6 file di test)  
**CI**: GitHub Actions (badge presente)  
**Ultimo aggiornamento**: 2026-02-26 (repository stabile da gennaio 2026)  
**PyPI**: disponibile come `pip install mcp-orchestrator`

### 4.1 Struttura del codice

```
mcp-orchestrator/
├── src/mcp_orchestrator/
│   ├── _init_.py
│   ├── main.py               # Entry point, DI wiring (~150 linee)
│   ├── models.py             # Pydantic v2 models (~180 linee)
│   ├── config_loader.py      # Caricamento server da JSON (~230 linee)
│   ├── mcp_server.py         # FastMCP server, dynamic tools (~650 linee)
│   ├── server/
│   │   ├── _init_.py
│   │   └── registry.py       # ServerRegistry con storage persistente (~250 linee)
│   ├── tools/
│   │   ├── _init_.py
│   │   ├── search.py         # ToolSearchService (BM25 + regex) (~450 linee)
│   │   └── router.py         # ToolRouter (HTTP + stdio routing) (~320 linee)
│   └── storage/
│       ├── _init_.py
│       ├── base.py           # Interfaccia astratta StorageBackend (~60 linee)
│       ├── memory.py         # Backend in-memory (~90 linee)
│       └── redis.py          # Backend Redis (~90 linee)
├── tests/
│   ├── _init_.py
│   ├── test_search.py        # Test ricerca (~200 linee)
│   ├── test_registry.py      # Test registry (~130 linee)
│   ├── test_storage.py       # Test storage (~120 linee)
│   ├── test_models.py        # Test Pydantic models (~100 linee)
│   └── test_integration.py   # Test integrazione (~350 linee)
├── stdio_server/             # Server stdio di esempio per test
├── server_config.json        # Config server backend (esempio)
├── server.json               # Metadati per MCP marketplace
├── pyproject.toml
├── uv.lock
├── .env.example
└── docs/                     # Documentazione
```

**Totale**: ~2.500 linee di Python, 5 file di test (~900 linee).

### 4.2 Architettura

```
                    mcp-orchestrator
                  ┌───────────────────┐
                  │   FastMCP Server   │
                  │  (mcp_server.py)  │
                  └────────┬──────────┘
                           │
         ┌─────────────────┼─────────────────────┐
         │                 │                      │
         ▼                 ▼                      ▼
  ┌────────────┐   ┌──────────────┐    ┌──────────────┐
  │ tool_search │   │ call_remote  │    │ Dynamic     │
  │ (BM25/regex)│   │ _tool       │    │ Tools        │
  └──────┬─────┘   └──────┬───────┘    │ (per-server) │
         │                │            └──────┬───────┘
         ▼                ▼                    │
  ┌────────────┐   ┌───────────┐              │
  │ ToolSearch │   │ ToolRouter│              │
  │ Service    │   │           │              │
  │ (search.py)│   │ (router.py)             │
  │            │   │ HTTP + stdio│            │
  └────────────┘   └─────┬──────┘              │
                         │                     │
                         ▼                     │
                 ┌──────────────┐              │
                 │ ServerReg.  │◄─────────────┘
                 │ (registry.py)│
                 │              │
                 │ Storage:    │
                 │ InMemory /  │
                 │ Redis       │
                 └──────────────┘
                         │
           ┌─────────────┼──────────────┐
           ▼             ▼              ▼
     Server A        Server B        Server C
     (HTTP/stdio)    (HTTP/stdio)    (HTTP/stdio)
```

### 4.3 Flusso di esecuzione

1. **Avvio** (`main.py`):
   - Crea config da env vars (`OrchestratorConfig` Pydantic)
   - Crea `StorageBackend` (InMemory o Redis)
   - Crea `ServerRegistry(storage)` + `ToolSearchService()`
   - Crea `MCPOrchestratorServer(storage, registry, tool_search, auth_mode, transport)`
   - Se `server_config.json` esiste: carica e registra server via `ConfigLoader`
   - ConfigLoader fa `discover_tools()` per ogni server
   - Registra i 3 tool esposti: `tool_search`, `call_remote_tool`
   - Se `expose_tools=true`: crea dynamic tools namespaced

2. **Ricerca** (`search.py`: `ToolSearchService`):
   - **BM25** (default): punteggio basato su keyword matching con pesi migliorativi:
     - Name match: +8.0
     - Name start: +4.0
     - Description match: +15.0 (massimo peso)
     - Semantic equivalents: boost per sinonimi (search↔query, docs↔documentation)
     - Fuzzy parziale: match parziale su parole con +2.0/+1.0
     - Moltiplicatore 2.0 se name AND description match
   - **Regex** (opzionale): Python `re.compile(pattern, IGNORECASE)` su `searchable_text`
   - Fallback: senza whoosh, usa regex generata dai keywords
   - **Stop words** rimosse dal corpus
   - Namespacing automatico `server_name_tool_name`

3. **Esecuzione** (`router.py` + `mcp_server.py:call_remote_tool`):
   - `call_remote_tool(tool_name, arguments)`:
     - Parsa `server_name_tool_name` da `tool_name`
     - Recupera `ServerInfo` dal registry (inclusi auth, url, transport)
     - Se HTTP: `streamable_http_client` + `ClientSession`
     - Se stdio: `stdio_client` + `StdioServerParameters`
     - Auth: statico (da registro) o forward (da client)
   - **Dynamic tools**: alternativa che crea funzioni Python con `inspect.Signature` per ogni tool namespaced, registrate via `@self._mcp.tool(name=namespaced_name)`. Permette chiamata diretta come tool FastMCP invece che via `call_remote_tool`.

4. **Storage** (`storage/`):
   - Interfaccia `StorageBackend` astratta: `get/set/delete/exists/keys/hget/hset/hgetall/hdel/close`
   - `InMemoryStorage`: dict semplice per sviluppo
   - `RedisStorage`: connessione Redis per produzione
   - Usato per: server info, tool metadata, auth config

5. **Auth**:
   - Tre modalità: `auto` (HTTP → forward, stdio → static), `static`, `forward`
   - `AuthConfig` per server: type (none/static/forward), headers, header_name, header_prefix
   - `expose_tools=false` di default: i tool backend non appaiono in `tools/list`, solo via `call_remote_tool` e `tool_search`

### 4.4 Modello dati

```python
class ToolReference(BaseModel):
    server_name: str
    tool_name: str
    namespaced_name: str  # server_name_tool_name
    description: str
    input_schema: Dict[str, Any]
    defer_loading: bool = True

class ToolSearchResponse(BaseModel):
    tool_references: List[ToolReferenceBlock]
    tools: List[ToolSearchResultEntry]
    total_matches: int
    query: str

class ServerRegistration(BaseModel):
    name: str
    url: str
    transport: Literal["http", "stdio"]
    command: Optional[str]
    args: Optional[List[str]]
    env: Optional[Dict[str, str]]
    auth: AuthConfig
    auto_discover: bool = True
    loading_mode: Literal["eager", "deferred"] = "eager"
```

### 4.5 Punti di forza

- **Python puro**: stack identico ad ARIA (FastMCP, Pydantic, asyncio). Integrabile come `src/aria/mcp/tool_search_proxy/`.
- **BM25 avanzato**: sistema di pesi sofisticato con semantic equivalents, fuzzy parziale, boost su name+description.
- **Storage persistente**: Redis come backend production-ready. InMemory per sviluppo.
- **Namespacing formale**: `server_name_tool_name` previene conflitti tra server.
- **Auth flessibile**: tre modalità (auto, static, forward) con supporto per OAuth bearer.
- **Timeout espliciti**: 30s default per connessioni, `asyncio.timeout` ovunque.
- **Pydantic models**: 17 modelli tipizzati, validazione automatica input/output.
- **Deferred loading nativo**: `loading_mode: "deferred"` esplicito, `defer_loading: True` su ogni `ToolReference`.
- **Tool metadata persistenti**: anche dopo riavvio, i tool metadata sono recuperabili da storage.
- **Copertura test**: 5 file di test, asyncio mode auto, test per registry, search, storage, models, integrazione.
- **CI/CD funzionante**: badge tests, badge Python 3.11-3.13.
- **Documentazione**: README completo, CODE_OF_CONDUCT, CONTRIBUTING, docs/.
- **PyPI pubblicato**: installabile con `pip install mcp-orchestrator`.
- **HTTP + stdio**: supporta entrambi i transport per downstream servers.
- **Tool caching**: `TTLCache` (1000 entry, 5 min TTL) per schemi tool.
- **Rimozione pulita**: `remove_server_tools()` e `remove_tool_metadata()` su deregistration.

### 4.6 Criticità

- **Nessuna ricerca vettoriale**: solo BM25 + regex. Nessuna comprensione semantica oltre ai semantic equivalents manuali.
- **BM25 senza whoosh**: se `whoosh` non è installato, il BM25 fallback a regex generata, che è molto meno accurata.
- **Dynamic tools via inspect**: la creazione di funzioni Python via `inspect.Signature` è fragile. I parametri JSON Schema non sempre mappano 1:1 con Python types.
- **Nessuna skills/macro**: non c'è il sistema di composizione multi-step che Opzione A ha con le skills YAML.
- **Redis dipendenza opzionale ma installata**: `redis>=5.0.0` è in dependencies, non optional-dependencies.
- **Maturità bassa**: versione 0.1.2, ultimo commit febbraio 2026.
- **No lazy loading runtime al client**: nonostante il `defer_loading` nei modelli, il proxy carica comunque le definizioni di tutti i tool backend all'avvio. Il "deferred" è concettuale nel formato di risposta.
- **Nessuna metrica di contesto**: non calcola quanti token occupano le definizioni.
- **Config JSON vs YAML**: ARIA usa YAML per il catalogo, mcp-orchestrator usa JSON. Piccola frizione.
- **No health-check periodico**: solo stato "unknown" all'avvio.
- **Variabile d'ambiente centralizzata**: `server_config.json` singolo, non facile da segmentare per agente.

---

## 5. Matrice comparativa

### 5.1 Tabella riassuntiva

| Dimensione | Opzione A (tool-search-tools-mcp) | Opzione B (mcp-orchestrator) |
|---|---|---|
| **Linguaggio** | TypeScript / Node.js 22+ | Python 3.11+ |
| **Framework MCP** | MCP SDK ufficiale (@modelcontextprotocol/sdk) | FastMCP |
| **Modelli dati** | TypeScript types (manuali) | Pydantic v2 (17 modelli) |
| **Ricerca default** | fuzzy (fuse.js) | BM25 |
| **Ricerca vettoriale** | ✅ Sì (transformers.js, locale) | ❌ No |
| **Ricerca regex** | ❌ No | ✅ Sì (Python re) |
| **Embedding modello** | Xenova/all-MiniLM-L6-v2 (384d) | N/A |
| **Embedding caching** | ✅ Su disco (JSON streamed) | N/A |
| **Skills / Macro** | ✅ YAML multi-step con variabili | ❌ No |
| **Timeout** | ❌ Non configurabili | ✅ 30s default, configurabili |
| **Auth backend** | ❌ Nessuno | ✅ 3 modalità (auto/static/forward) |
| **Health check** | ❌ No | ❌ Solo stato "unknown" |
| **Namespacing** | `server:name` (informale) | `server_name` (formale Pydantic) |
| **Storage** | Solo in-memory | In-memory + Redis |
| **Transport backend** | Solo stdio | stdio + HTTP |
| **Transport proxy** | Solo stdio | stdio + HTTP (uvicorn/CORS) |
| **Test coverage** | Bassa (3 file, mock pesanti) | Media (5 file, asyncio) |
| **CI/CD** | ✅ GitHub Actions | ✅ GitHub Actions |
| **PyPI/npm** | ❌ Solo repo | ✅ PyPI disponibile |
| **Linee di codice** | ~1.900 TS | ~2.500 Python |
| **Dipendenze runtime** | 5 (mcp-sdk, transformers, fuse, yaml, zod) | 9 (fastmcp, mcp, pydantic, redis, httpx, whoosh, tenacity, structlog, cachetools) |
| **Metriche contesto** | ❌ No | ❌ No |

### 5.2 Qualità della ricerca a confronto

Dimensione fondamentale: l'agente LLM deve trovare il tool giusto con una query in linguaggio naturale.

| Aspetto | Opzione A | Opzione B |
|---|---|---|
| **Match esatto nome** | Fuse.js threshold 0.4, weight 0.5 | +8.0 base, +4.0 se startswith, +2x se anche desc match |
| **Match descrizione** | Fuse.js weight 0.3 | +15.0 (massimo), +5.0 se nei primi 100 char |
| **Match paramentro** | keywords da inputSchema.properties | searchable_text include prop name, enum, desc |
| **Ricerca semantica** | ✅ Cos-sim su embedding 384d (soglia 0.35) | ❌ Solo keyword |
| **Sinonimi** | ❌ No (affidamento a vettoriale) | ✅ 5 gruppi manuali (query↔search, docs↔doc...) |
| **Fuzzy parziale** | Fuse.js built-in | Match parziale su parole con +2.0/+1.0 |
| **Stop words** | ❌ No | ✅ 120+ parole rimosse |
| **Multi-word** | Tokenizza e ritenta parola per parola se pochi risultati | Concatenazione keywords per regex fallback |

Opzione A vince sulla ricerca **semantica** (vettoriale cattura relazioni che il keyword non può). Opzione B vince sulla **precisione** (sistema di pesi sofisticato con boost mirati).

### 5.3 Robustezza e gestione errori

| Aspetto | Opzione A | Opzione B |
|---|---|---|
| **Timeout connessione** | ❌ Nessuno | ✅ 30s asyncio.timeout |
| **Retry** | ❌ No | ✅ max_retries=3 (con tenacity) |
| **Graceful shutdown per tool crash** | ❌ throw generico, catch "Error" | ❌ throw generico |
| **Validazione input** | ✅ Zod | ✅ Pydantic |
| **Validazione output** | ❌ No | ❌ No |
| **Logging** | ✅ Scoped, livelli, file | ✅ structlog |
| **Error categorization** | ❌ No | ✅ ErrorCode enum (TOO_MANY_REQUESTS, INVALID_PATTERN...) |

Opzione B è significativamente più robusta su timeout, retry, e categorizzazione errori.

### 5.4 Impatto contesto LLM

Metrica chiave per ARIA. Confronto dell'impatto teorico sul contesto:

| Metrica | Oggi (14 MCP eager) | Opzione A | Opzione B |
|---|---|---|---|
| **Tool esposti al client** | ~100+ | 2 (`search_tools` + `call_tool`) | 3 (`tool_search` + `call_remote_tool` + eventuali dynamic) |
| **Token contesto startup** | ~40K | ~1.5K (2 definizioni) | ~2K (3 definizioni) |
| **Token a runtime** | 40K fissi | 1.5K + (3-5 tool * 1K) = ~6.5K | 2K + (3-5 tool * 1K) = ~7K |
| **Riduzione picco** | — | **~84%** | **~82%** |
| **Scalabilità teorica** | 15-20 server | 100+ server | 100+ server |

Entrambe le opzioni risolvono il problema della scalabilità. La differenza è marginale.

---

## 6. Implicazioni di integrazione in ARIA

### 6.1 Mappa delle integrazioni

```
                        ARIA Architecture
                    ┌────────────────────────┐
                    │     KiloCode Client     │
                    │  mcp.json → 1 entry    │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Tool Search Proxy     │ ◄── DA IMPLEMENTARE
                    │  (Opzione A o B)       │
                    └───┬───────────────┬────┘
                        │               │
              ┌─────────▼───┐    ┌──────▼────────┐
              │  Capability  │    │ 14 MCP Server │
              │  Probe       │    │ Backend       │
              │ (drift detect)│   │ (filesystem,  │
              └──────────────┘    │ search, ...)  │
                                  └───────────────┘
```

### 6.2 Integrazione Opzione A (tool-search-tools-mcp)

#### Configurazione mcp.json

```json
{
  "mcpServers": {
    "aria-tool-search": {
      "command": "npx",
      "args": [
        "-y",
        "tool-search-tools-mcp"
      ],
      "env": {
        "MCP_CONFIG_PATH": "/path/to/.aria/kilocode/mcp-backend.json",
        "MCP_SEARCH_MODE": "vector",
        "MCP_CACHE_DIR": "/path/to/.aria/cache/embeddings",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Oppure** come processo Node.js locale (più controllo):
```json
{
  "mcpServers": {
    "aria-tool-search": {
      "command": "node",
      "args": ["/path/to/node_modules/tool-search-tools-mcp/dist/server.js"],
      "env": {
        "MCP_CONFIG_PATH": "/path/to/.aria/kilocode/mcp-backend.json",
        ...
      }
    }
  }
}
```

#### Cosa cambia nell'ecosistema ARIA

| Componente | Cambiamento |
|---|---|
| `.aria/kilocode/mcp.json` | Da 14 entry a 1 entry (proxy) |
| `mcp_catalog.yaml` | Rimane come governance layer, ma i 14 server vanno nel `mcp-backend.json` |
| `lazy_loader.py` | **Deprecato** — non serve più filtrare per intent; il proxy carica tutto ma espone solo search |
| `capability_probe.py` | Deve essere adattato per puntare ai backend direttamente (non più al client) |
| `credential_manager.py` | **Problema**: Opzione A non ha env vars interpolation. Serve un wrapper che generi `mcp-backend.json` con chiavi iniettate |
| Avvio sessione | Più lento (~15-30s per scaricare modello embeddings al primo avvio), poi veloce |

#### Vantaggi specifici ARIA

- **Skills YAML**: si potrebbe mappare `skills.yaml` su workflow ARIA (es. "search_and_summarize" → cerca + archivia)
- **Vector search**: semanticamente più potente per domini misti di ARIA (academic, web, productivity)
- **Rapido da testare**: `pnpm install + pnpm start` in 5 minuti

#### Svantaggi specifici ARIA

- **Dipende da Node.js**: ARIA è un progetto Python. Aggiungere Node.js come runtime aumenta la complessità operativa (versione 22+, npx/pnpm, sharp native build)
- **Nessuna integrazione con credential manager**: le chiavi API Tavily, Brave, Exa non possono essere iniettate dinamicamente
- **Il modello di embeddings è ~22MB**: primo download + compilazione ONNX richiede CPU e tempo
- **No Redis/no persistenza**: ARIA perde lo stato se il proxy crasha
- **Manutenzione linguaggio diverso**: il team ARIA lavora in Python; modificare TypeScript richiede skill set diverso

### 6.3 Integrazione Opzione B (mcp-orchestrator)

#### Configurazione mcp.json

```json
{
  "mcpServers": {
    "aria-tool-search": {
      "command": ".venv/bin/python",
      "args": ["-m", "aria.mcp.tool_search_orchestrator"],
      "env": {
        "ORCHESTRATOR_LOG_LEVEL": "INFO",
        "SERVER_CONFIG_PATH": "/path/to/.aria/config/orchestrator_servers.json",
        "STORAGE_BACKEND": "memory"
      }
    }
  }
}
```

Oppure, ancora meglio, come **pacchetto importato** in `src/aria/mcp/`:

```python
# src/aria/mcp/tool_search_orchestrator/main.py
from mcp_orchestrator.main import create_config_from_env, create_storage
from mcp_orchestrator.server.registry import ServerRegistry
from mcp_orchestrator.tools.search import ToolSearchService
from mcp_orchestrator.mcp_server import MCPOrchestratorServer

# ARIA-specific customization
from aria.credentials.manager import CredentialManager
from aria.config.catalog import MCPCatalog

# Inject credentials into server config
# Customize auth flow
# etc.
```

#### Cosa cambia nell'ecosistema ARIA

| Componente | Cambiamento |
|---|---|
| `.aria/kilocode/mcp.json` | Da 14 entry a 1 entry (proxy) |
| `mcp_catalog.yaml` | Può essere usato per GENERARE `orchestrator_servers.json` (conversione YAML→JSON) |
| `lazy_loader.py` | **Deprecato** — sostituito dal proxy |
| `capability_probe.py` | Può essere integrato nella fase di `auto_discover` del config_loader |
| `credential_manager.py` | **Integrazione naturale**: basta un wrapper che genera `orchestrator_servers.json` con le chiavi iniettate |
| `aria.mcp` package | Nuovo modulo `aria.mcp.tool_search_orchestrator/` con wrapper ARIA-specifico |

#### Vantaggi specifici ARIA

- **Stesso stack Python**: integrabile come dipendenza `pip install mcp-orchestrator` o come codice sorgente in `src/aria/mcp/`
- **CredentialManager si integra nativamente**: basta un wrapper che inietta chiavi nel JSON di config
- **YAML → JSON**: il catalogo YAML può essere convertito nel formato di `orchestrator_servers.json`
- **Storage Redis opzionale**: ARIA può usare InMemory per sviluppo, Redis per produzione
- **Auth modes**: ARIA può usare `static` per API key backend, `forward` per OAuth Google Workspace
- **FastMCP già in uso**: ARIA già usa FastMCP per `aria-memory` — stesso pattern
- **Pydantic già in uso**: ARIA usa Pydantic in tutto il progetto
- **Test già in pytest**: i test esistenti di ARIA condividono lo stesso runner
- **Timeouts e retry**: la config di connessione di ARIA (CredentialManager ha già circuit breaker) può allinearsi

#### Svantaggi specifici ARIA

- **Nessuna ricerca vettoriale**: per il dominio ARIA (ricerca web multi-fonte), BM25 potrebbe non catturare relazioni semantiche complesse
- **Nessuna skills/macro**: ARIA perde la possibilità di comporre tool multi-step a livello proxy
- **BM25 dipende da whoosh**: se non installato, degrada a regex (meno accurato)
- **Dynamic tools con inspect**: il pattern `inspect.Signature` per creare funzioni è fragile con JSON Schema complesso (enum, oneOf, anyOf)
- **Redis dipendenza in production**: ARIA dovrebbe comunque gestire Redis per lo storage persistente
- **Maturità 0.1.2**: poche versioni, rischio di breaking changes

### 6.4 Mappa delle differenze chiave per la decisione

| Domanda | Opzione A | Opzione B |
|---|---|---|
| Quanto tempo per un proof-of-concept funzionante? | 1 ora (npm install + config) | 30 minuti (pip install + config) |
| Quanto tempo per integrazione completa ARIA? | 2-3 giorni (wrapper credential, backend config) | 1-2 giorni (wrapper credential, catalog converter) |
| Rischio di regressioni per il team ARIA? | Alto (stack diverso) | Basso (stesso stack) |
| Qualità ricerca per domini misti ARIA? | Migliore (vettoriale) | Buona (BM25 con sinomimi) |
| Manutenibilità a 6 mesi? | Bassa (servono competenze TS) | Alta (team già Python) |
| Integrazione credential manager? | Complessa (no env vars) | Nativa (wrapper Python) |
| Skills/macro utili per ARIA? | Sì (workflow multi-tool) | No |
| Testabilità? | Media (vitest, mock pesanti) | Alta (pytest, asyncio supportato) |
| Costo startup primo avvio? | Alto (download modello 22MB) | Basso (solo import Python) |

---

## 7. Raccomandazione finale

### 7.1 Giudizio sintetico

| Criterio | Peso | Opzione A | Opzione B |
|---|---|---|---|
| Integrabilità stack ARIA | 30% | 3/10 | **9/10** |
| Qualità ricerca | 20% | **8/10** | 7/10 |
| Robustezza / error handling | 15% | 5/10 | **8/10** |
| Manutenibilità | 15% | 4/10 | **9/10** |
| Velocità integrazione | 10% | 7/10 | **8/10** |
| Maturità / test | 10% | 5/10 | **7/10** |
| **Punteggio ponderato** | 100% | **5.05/10** | **8.15/10** |

### 7.2 Opzione consigliata: B (mcp-orchestrator), con integrazione progressiva

L'**Opzione B** è la scelta migliore per ARIA per una ragione dominante: **l'integrabilità nello stack Python/FastMCP/Pydantic esistente**. I vantaggi in termini di manutenibilità, credential management, e testing superano i benefici marginali della ricerca vettoriale di Opzione A.

### 7.3 Strategia di integrazione raccomandata

**Fase 1 — Short term (1-2 giorni)**
1. `pip install mcp-orchestrator` in `.venv`
2. Scrivere `src/aria/mcp/tool_search_orchestrator/_init_.py` che:
   - Legge `mcp_catalog.yaml` e genera il JSON di config per orchestrator
   - Inietta le credenziali tramite CredentialManager
   - Lancia il server con InMemory storage
3. Modificare `.aria/kilocode/mcp.json` → 1 entry
4. **Testare**: una sessione KiloCode deve poter usare `tool_search` e `call_remote_tool`

**Fase 2 — Medium term (1 settimana)**
1. Integrare il `capability_probe` nel `config_loader` (drift detection)
2. Aggiungere metriche di contesto (quanti token risparmiati?)
3. Opzionale: implementare skills/macro come estensione ARIA (l'architettura di mcp-orchestrator lo permette tramite `ToolSearchService.index_tool_metadata()`)

**Fase 3 — Long term (2+ settimane)**
1. Valutare se aggiungere ricerca vettoriale al BM25 (usando `sentence-transformers` via `fastembed` invece di Node.js)
2. Redis storage per produzione
3. Deprecare formalmente `lazy_loader.py` e rimuovere `intent_tags` dal catalogo YAML

### 7.4 Cosa rimane del Lazy Loader

Il Lazy Loader corrente e il suo catalogo con `intent_tags` possono essere:
- **Sostituiti nel runtime** dal proxy (il proxy decide cosa caricare, non il filtro di intent)
- **Mantenuti nel catalogo YAML** come metadati di governance (tier, domain, risk level, rollback class)
- **Ridefiniti concettualmente**: invece di "quali server caricare", il catalogo descrive "quali server esistono" — l'intent è implicito nella query di tool_search

Il catalogo YAML rimane utile per:
- Audit: quali server sono autorizzati
- Rollback: quale versione di un server era baseline
- Risk: quali server sono ad alto rischio
- Tier: quali server sono core vs experimental

Ma **non più** come meccanismo di filtraggio del contesto.

---

*Fine del documento di analisi. Decisione finale a cura del team ARIA.*
