---
document: ARIA Phase 1 — Sprint 1.3 Implementation Plan
version: 1.0.0
status: draft
date_created: 2026-04-20
last_review: 2026-04-20
owner: fulvio
phase: 1
sprint: "1.3"
canonical_blueprint: docs/foundation/aria_foundation_blueprint.md
blueprint_sections: ["§8", "§9", "§10", "§11", "§14.3"]
phase_overview: docs/plans/phase-1/README.md
depends_on: docs/plans/phase-1/sprint-02.md
---

# Sprint 1.3 — ARIA-Conductor & Search-Agent

## 1) Obiettivo, scope, vincoli

### 1.1 Obiettivo

Collegare **Gateway → Conductor → Sub-Agente → Tool MCP** con un primo sub-agente operativo: il **Search-Agent**. Al termine dello sprint, un messaggio Telegram "ARIA, fai una ricerca su X" deve produrre un **report** consolidato con fonti, salvato in memoria episodica con tag `research_report`.

### 1.2 In scope

- Definizioni agent markdown: `aria-conductor.md`, `search-agent.md`, `_system/{compaction-agent,summary-agent,memory-curator,blueprint-keeper,security-auditor}.md` (Conductor + Search + 5 sistema; Workspace rimane placeholder in Sprint 1.3).
- Skills markdown: `planning-with-files/`, `deep-research/`, `pdf-extract/`, `hitl-queue/`, `memory-distillation/` (blueprint-keeper rimane stub markdown da espandere in Fase 2).
- Python `src/aria/agents/search/` completo: `router.py` (intent-aware), `providers/{tavily,brave,firecrawl,exa,searxng}.py`, `dedup.py`, `cache.py`, `health.py`.
- MCP wrappers per Tavily e Firecrawl (blueprint §10.3): `scripts/wrappers/tavily-wrapper.sh` → Python MCP server `src/aria/tools/tavily/mcp_server.py` (FastMCP). Brave MCP: usare pacchetto upstream `@brave/brave-search-mcp-server` (attivo in `mcp.json`).
- Integrazione gateway→conductor: consumer del bus `gateway.user_message` che spawna child session KiloCode via subprocess `npx kilocode run ...` oppure API se disponibile (controllare KiloCode docs, altrimenti fallback spawn).
- Prompt injection frame obbligatorio (blueprint §14.3).
- Skill `deep-research` che orchestra i 4 provider con rotation e cache.
- Caching query→results in memoria episodica tag `search_cache` TTL 6h.
- Provider health check + graceful degradation runbook `docs/operations/provider_exhaustion.md`.
- ADR-0006 (Prompt Injection Mitigation) accepted.

### 1.3 Out of scope

- Workspace-Agent (Sprint 1.4).
- Blueprint-keeper skill eseguibile (solo metadata + stub; implementazione in Fase 2 post-MVP).
- LLM routing automatico (blueprint §8.2: manuale in MVP; Fase 2).
- Playwright MCP (disabilitato in `mcp.json`; Fase 2).
- SerpAPI (solo stub skeleton, attivato on-demand).

### 1.4 Vincoli inderogabili

- **P8 Tool Priority Ladder**: usare MCP maturo quando disponibile. Brave ha MCP ufficiale → usarlo. Tavily/Firecrawl: wrapping custom via FastMCP (blueprint §10.4).
- **P9 ≤ 20 tool per sub-agente**: Search-Agent ha `tavily-mcp/search`, `firecrawl-mcp/scrape`, `firecrawl-mcp/extract`, `brave-mcp/web_search`, `brave-mcp/news_search`, `exa-script/search`, `searxng-script/search`, `aria-memory/remember`, `aria-memory/recall`, `fetch/fetch` → 10 tool. OK.
- **P14.3 Prompt injection mitigation**: ogni `tool_output` incapsulato in `<<TOOL_OUTPUT>>...<</TOOL_OUTPUT>>` con sanitizer. Conductor system prompt vieta esecuzione di istruzioni trovate in tool_output.
- **Child session isolate** (blueprint §8.6): Conductor delega via spawn, context window separato, transcript salvato.

## 2) Pre-requisiti

- Sprint 1.2 chiuso: scheduler + gateway operativi; HITL flow funzionante.
- `CredentialManager` popolato con chiavi Tavily/Brave/Firecrawl/Exa in `api-keys.enc.yaml` (almeno 1 per provider; se mancanti, `aria creds list` evidenzia gap).
- `ARIA-Memory` MCP server funzionante da KiloCode REPL (verifica `/tools aria-memory/stats`).
- Account Google/Tavily/etc con API key: responsabilita dell'utente (Fulvio) prima di iniziare Sprint 1.3.

## 3) Work Breakdown Structure (WBS)

### W1.3.A — Agent definitions (KiloCode `.md`)

**Directory**: `.aria/kilocode/agents/` e `.aria/kilocode/agents/_system/`.

Gia esistenti stub da Phase 0. Completare contenuto secondo blueprint §8.2-§8.4. Regole:

**ARIA-Conductor** (`.aria/kilocode/agents/aria-conductor.md`):
- Frontmatter blueprint §8.2 letteralmente (color, temperature=0.2, etc.).
- `allowed-tools`:
  ```yaml
  allowed-tools:
    - aria-memory/*
    - sequential-thinking/*
  ```
- `required-skills: [planning-with-files, hitl-queue]`
- Body: regole strette, no invenzione fatti, interrogazione memoria obbligatoria pre-risposta, HITL su distructive.

**Search-Agent** (`.aria/kilocode/agents/search-agent.md`):
- Frontmatter blueprint §8.3.1.
- `allowed-tools`:
  ```yaml
  allowed-tools:
    - tavily-mcp/search
    - firecrawl-mcp/scrape
    - firecrawl-mcp/extract
    - brave-mcp/web_search
    - brave-mcp/news_search
    - exa-script/search
    - aria-memory/remember
    - aria-memory/recall
    - fetch/fetch
  ```
- Body: istruzioni su rotation, deduplica, citazione fonti obbligatoria.

**Workspace-Agent** (stub in Sprint 1.3, riempito Sprint 1.4):
- Frontmatter blueprint §8.3.2 ma `disabled: true` temporaneo.

**Agent di sistema** (blueprint §8.4):
- `compaction-agent.md`: temperature 0, tool = `aria-memory/*` + `sequential-thinking/*`. Prompt: "preserva provenienza, mai promuovere inferenze".
- `summary-agent.md`: come sopra, produce title+summary.
- `memory-curator.md`: tool `aria-memory/curate`, `aria-memory/forget`, `hitl-queue/ask`. Periodico.
- `blueprint-keeper.md`: stub minimale; Fase 2.
- `security-auditor.md`: stub minimale; Fase 2.

**Acceptance**:
- `aria repl` → `/agents list` mostra tutti gli agent sopra con color/description corretti.
- Validator script `scripts/validate_agents.py`: controlla che ogni agent rispetti schema (top 20 tool, skill esistono).

### W1.3.B — Skills markdown

Per ogni skill sotto `.aria/kilocode/skills/<slug>/SKILL.md`, seguire pattern blueprint §9.1. Le directory esistono gia (Phase 0).

**Skills da implementare** (contenuto completo):

1. **`planning-with-files/SKILL.md`**:
   - Crea file `.aria/runtime/tmp/plans/<session_id>-task_plan.md`, `findings.md`, `progress.md`.
   - Procedura: decomponi richiesta in step numerati, mantieni stato in `progress.md`, scrivi findings incrementali.
   - Tool usati: `filesystem/*`, `aria-memory/*`.

2. **`deep-research/SKILL.md`**:
   - Vedi blueprint §9.1 letteralmente.
   - `max-tokens: 50000`, `estimated-cost-eur: 0.10`.
   - Procedura: 3-7 sub-query, rotation Tavily>Brave>Firecrawl>Exa, deduplica, scrape top-N, sintesi report, salva tag `research_report`.
   - Invarianti: cita fonti, dichiara incompletezza se < 3 fonti.

3. **`pdf-extract/SKILL.md`**:
   - Dipendenza: aggiungere `pymupdf>=1.24` a `pyproject.toml [ml]`.
   - Procedura: input path PDF → testo + metadati (title, author, date) → ingesto in memoria episodica tag `pdf_source`.
   - Tool: `filesystem/read_file`, `aria-memory/remember`, script Python locale `scripts/pdf_extract.py`.

4. **`hitl-queue/SKILL.md`**:
   - Wrapper per invocare `hitl_manager.ask` dal Conductor.
   - Tool: wrapper custom expose via MCP `aria-memory` (ADR-0005 potrebbe richiedere movimento a `aria-scheduler` MCP; decidere in Sprint 1.3 via nota in ADR-0006 o nuovo ADR-0008).
   - **Decisione Sprint 1.3**: esporre `hitl.ask/hitl.resolve` come **nuovo tool in `aria-memory` MCP server** (diventano 9 tool totali, ancora sotto budget 10). Alternativa piu pulita: nuovo MCP `aria-ops` con solo `hitl.*`. Raccomandato: **aria-ops** con 3 tool (`hitl_ask`, `hitl_list_pending`, `hitl_cancel`) — crea `src/aria/tools/ops/mcp_server.py`. Update `mcp.json` e agent allowed-tools.

5. **`memory-distillation/SKILL.md`**:
   - Invoca `aria-memory/distill` su session_id o range.
   - Procedura: verifica quota-utente, chiama `distill`, presenta top-5 chunk all'utente per curare.

6. **`blueprint-keeper/SKILL.md`** (stub):
   - Solo metadata + "TBD Fase 2".

7. **`_registry.json`**:
   - Aggiornare con ogni skill e version.

**Acceptance**:
- CI lint script `scripts/validate_skills.py`: parse frontmatter, verifica `allowed-tools` esistono in `mcp.json` o sono wildcard noti, `max-tokens` definito.

### W1.3.C — Search router (intent-aware)

**File**: `src/aria/agents/search/router.py`.

**Responsabilita**: decidere il provider target data la query. Implementazione minimale blueprint §11.2:

```python
INTENT_ROUTING = {
    "news":             ["tavily", "brave_news"],
    "academic":         ["exa", "tavily"],
    "deep_scrape":      ["firecrawl_extract", "firecrawl_scrape"],
    "general":          ["brave", "tavily"],
    "privacy":          ["searxng", "brave"],
    "fallback":         ["serpapi"],
}

class IntentClassifier:
    def classify(self, query: str) -> str: ...   # keyword-based; Sprint 1.3 NO LLM call

class SearchRouter:
    def __init__(self, cm: CredentialManager, health: ProviderHealth, cache: SearchCache): ...
    async def route(self, query: str, intent: str | None = None) -> SearchResult: ...
```

`IntentClassifier.classify` euristica:
- Regex `\b(oggi|ieri|ultim[ae]|breaking|news)\b` → `news`.
- Regex `\b(paper|arxiv|publication|doi|abstract)\b` → `academic`.
- URL in query → `deep_scrape`.
- Default → `general`.

**Acceptance**:
- Tabella test input→intent (≥ 20 casi).
- `SearchRouter.route` respekta `ProviderHealth.status(provider)` (skip se `degraded`/`down`) e `CredentialManager.acquire` (skip se `credits_remaining == 0`).

### W1.3.D — Search providers (Python adapter)

**Directory**: `src/aria/agents/search/providers/`.

Ogni provider: modulo con classe conforme a `Protocol`:

```python
class SearchProvider(Protocol):
    name: str
    async def search(self, query: str, top_k: int = 10, **kwargs) -> list[SearchHit]: ...
    async def health_check(self) -> ProviderStatus: ...   # available|degraded|down|credits_exhausted
```

**Modelli**:

```python
class SearchHit(BaseModel):
    title: str
    url: HttpUrl
    snippet: str
    published_at: datetime | None = None
    score: float = 0.0
    provider: str
    provider_raw: dict = Field(default_factory=dict)      # raw provider payload (non esporre in UI)
```

Provider da implementare:

1. **`tavily.py`**: HTTP `POST https://api.tavily.com/search` con `api_key`, `query`, `search_depth="basic"`. Docs https://docs.tavily.com/.
2. **`brave.py`**: usa MCP ufficiale Brave (no adapter Python necessario, ma wrapper di normalizzazione per deduplicare formato): il Search-Agent chiama `brave-mcp/web_search` via KiloCode; il router Python serve solo per telemetria + circuit breaker. ADR note: la rotation key Brave avviene nel wrapper bash; invocazione MCP riceve env pre-caricato con `BRAVE_API_KEY_ACTIVE`.
3. **`firecrawl.py`**: `POST https://api.firecrawl.dev/v1/scrape` per `scrape`, `/v1/extract` per structured. Docs https://docs.firecrawl.dev/.
4. **`exa.py`**: `POST https://api.exa.ai/search`. Docs https://exa.ai/.
5. **`searxng.py`**: `GET <SEARXNG_URL>/search?format=json&q=...` (self-hosted opzionale; default disabled in MVP).
6. **`serpapi.py`**: stub fallback `GET https://serpapi.com/search?api_key=...` (enabled solo se `ARIA_SEARCH_SERPAPI_ENABLED=1`).

**Hardening HTTP** (tutti):
- `httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_connections=20))`
- Retry con `tenacity` backoff 1-2-4s su `5xx` e `429` (Retry-After header-aware).
- Integrazione `CredentialManager`: `acquire("tavily")` -> chiamata -> `report_success(credits_used=1)` o `report_failure`.

**Acceptance**:
- Unit test con `respx` mock per ogni provider (happy path, 429, 5xx, network timeout).
- Integration test marker `@pytest.mark.requires_network` skippato di default (solo on demand per smoke manuale).

### W1.3.E — Dedup + ranking

**File**: `src/aria/agents/search/dedup.py`.

Blueprint §11.4:

```python
def canonicalize_url(url: str) -> str: ...
# remove utm_*, fbclid, gclid; normalize trailing slash; lowercase host

def title_similarity(a: str, b: str) -> float: ...
# Levenshtein ratio (rapidfuzz)

def dedup_hits(hits: list[SearchHit], title_threshold: float = 0.85) -> list[SearchHit]: ...

def rank_hits(hits: list[SearchHit],
              provider_weights: dict[str, float] = ...,
              now: datetime | None = None) -> list[SearchHit]: ...
# score = provider_weight * relevance * recency_decay(half_life=30d)
```

Dipendenza: aggiungere `rapidfuzz>=3.0` a `pyproject.toml`.

**Acceptance**:
- Dataset fixture 50 hit misti da 3 provider con 10 duplicati noti → dedup corretto.

### W1.3.F — Cache search

**File**: `src/aria/agents/search/cache.py`.

Riusa `EpisodicStore` con tag `search_cache` (blueprint §11.5):

```python
class SearchCache:
    def __init__(self, store: EpisodicStore, ttl_hours: int = 6): ...
    async def get(self, query: str, intent: str) -> list[SearchHit] | None: ...
    async def put(self, query: str, intent: str, hits: list[SearchHit]) -> None: ...
    async def invalidate(self, query: str | None = None) -> int: ...
```

Chiave cache: `sha256(f"{intent}:{canonicalize_query(query)}")`; salva hit list come JSON in `EpisodicEntry.meta["search_cache"]`, `actor=SYSTEM_EVENT`, `tags=["search_cache", intent]`.

**Acceptance**:
- TTL verificato: entry scaduta non restituita, ma presente nel DB (P6).

### W1.3.G — Provider health + circuit integration

**File**: `src/aria/agents/search/health.py`.

```python
class ProviderStatus(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    DOWN = "down"
    CREDITS_EXHAUSTED = "credits_exhausted"

class ProviderHealth:
    def __init__(self, cm: CredentialManager, providers: dict[str, SearchProvider]): ...
    async def probe_all(self) -> dict[str, ProviderStatus]: ...
    async def run_forever(self, interval_s: int = 300) -> None: ...
    def status(self, provider: str) -> ProviderStatus: ...
```

Cadenza probe: ogni 5 min. Risultati in-memory + metrics gauge `aria_provider_status{provider}`.

### W1.3.H — Tavily + Firecrawl MCP wrapper custom

**File**: `src/aria/tools/tavily/mcp_server.py`, `src/aria/tools/firecrawl/mcp_server.py`.

Wrapper FastMCP che espone `search(query, top_k)` / `scrape(url)` / `extract(url, schema)`. Internamente usa `src/aria/agents/search/providers/tavily.py` e `firecrawl.py` (riuso).

Motivazione: P8 Tool Priority Ladder e blueprint §10.3: "promuovere a MCP custom entro 2 sprint" — in Sprint 1.3 lo facciamo subito per evitare debito.

Wrapper bash `scripts/wrappers/tavily-wrapper.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
export ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"
exec "$ARIA_HOME/.venv/bin/python" -m aria.tools.tavily.mcp_server
```

Update `.aria/kilocode/mcp.json`: cambiare `disabled: true` → `disabled: false` per `tavily` e `firecrawl`.

**Acceptance**:
- `aria repl` → `/tools list` mostra `tavily-mcp/*` e `firecrawl-mcp/*`.
- Test integration `tests/integration/tools/test_tavily_mcp.py`: invoke via FastMCP in-process.

### W1.3.I — Bridge Gateway → Conductor

**File**: `src/aria/gateway/conductor_bridge.py`.

Consumer del bus `gateway.user_message`. Strategia Sprint 1.3:

**Opzione A (preferita)**: subprocess `npx --yes kilocode run --session <session_id> --agent aria-conductor --input '<msg>'` (verificare flags reali della CLI Kilocode; se non disponibile, fallback a file-based: scrivi `session_input.json` e lancia `kilocode chat --auto`).

**Opzione B fallback**: usa `KILOCODE_SESSION_ID` var + `kilocode chat --input '<msg>'`. Sprint 1.3 documenta quale opzione funziona.

```python
class ConductorBridge:
    def __init__(self, bus: EventBus, sessions: SessionManager, config: AriaConfig): ...
    async def handle_user_message(self, payload: dict) -> None: ...
    # 1. lookup/crea session ARIA
    # 2. salva user message in episodic (actor=USER_INPUT)
    # 3. spawna kilocode child session con input
    # 4. streamming output → messaggi Telegram (risponde via bus event `gateway.reply`)
    # 5. salva assistant response in episodic (actor=AGENT_INFERENCE)
```

Timeout subprocess: 10 min (blueprint §8.6 default). Configurabile via `ARIA_CONDUCTOR_TIMEOUT_S`.

**Prompt injection frame** (blueprint §14.3):
- Ogni `tool_output` salvato in episodic deve essere wrappato come `<<TOOL_OUTPUT>>{content}<</TOOL_OUTPUT>>` **quando iniettato nel system prompt del Conductor**.
- Sanitizer: strippare eventuali `<<TOOL_OUTPUT>>` nested dentro `content` (previene TOCTOU).
- Utility: `src/aria/utils/prompt_safety.py` → `wrap_tool_output(text: str) -> str`, `sanitize_nested_frames(text: str) -> str`.

**Acceptance**:
- E2E test: `ConductorBridge.handle_user_message({"text":"ciao","session_id":..., "telegram_user_id":...})` → entry episodic user, subprocess spawned, entry assistant, reply event pubblicato.

### W1.3.J — Skill `deep-research` integrazione

Linea di responsabilita fra Python layer e skill markdown:

- **Skill markdown** definisce la **procedura** in linguaggio naturale per il modello LLM.
- **Python layer (`SearchRouter`, `dedup`, `cache`)** e invocato via tool MCP esposti dai wrapper `tavily-mcp`/`firecrawl-mcp` (e `brave-mcp` upstream).
- Nessun orchestratore Python duplicato: il modello legge la skill e invoca i tool.

Verifica funzionale (Sprint 1.3 D4):
- Utente via Telegram: "ARIA, ricerca approfondita su `LOCOMO long-term memory benchmark`".
- Conductor legge skill `deep-research`, decompone in sub-query, invoca `tavily-mcp/search`, `brave-mcp/web_search`, `firecrawl-mcp/scrape` su top URL.
- Report sintetizzato, `aria-memory/remember` con tag `research_report`.
- Reply Telegram con report (troncato + "full in memory").

### W1.3.K — Runbook provider exhaustion

**File**: `docs/operations/provider_exhaustion.md` (nuovo).

Contenuto (scaffolding):

1. Health-check matrix (5-min cadence).
2. Fallback tree per intent (blueprint §11.6).
3. Procedura manuale di swap chiave: `aria creds rotate <provider>` + `aria creds status`.
4. Alert: `aria_provider_status{provider="tavily"}=2` (down) in metrics → notifica Telegram system_event.
5. Modalita `local-only`: SearXNG self-hosted + cache stale.

## 4) Piano sprint (5 giorni)

### D1 — Agent/skill definitions + registry
- W1.3.A agents markdown (conductor, search, system stubs)
- W1.3.B skills markdown (planning, deep-research, pdf-extract, hitl-queue, memory-distillation)
- `scripts/validate_{agents,skills}.py`
- End-of-day: `aria repl` / `/agents list` e `/skills list` mostrano tutti.

### D2 — Search router + providers 1/2
- W1.3.C router + IntentClassifier
- W1.3.D providers Tavily + Firecrawl (adapter Python)
- W1.3.F cache search
- End-of-day: test `respx` verde per 2 provider.

### D3 — Providers 3/4 + dedup + health
- W1.3.D providers Exa + SearXNG (serpapi stub)
- W1.3.E dedup/ranking
- W1.3.G provider health
- End-of-day: `SearchRouter.route("news LOCOMO")` funziona in integration test con mock HTTP.

### D4 — MCP wrappers custom + gateway bridge + demo
- W1.3.H Tavily/Firecrawl MCP wrappers attivi
- W1.3.I conductor bridge + prompt injection frame
- Demo live: Telegram → conductor → deep-research → report in memoria
- End-of-day: video/log dell'E2E catturato

### D5 — Runbook + ADR + quality gate
- W1.3.K provider_exhaustion.md
- ADR-0006 (Prompt Injection Mitigation) accepted
- Eventuale ADR-0008 (aria-ops MCP server per hitl tools) se scelta implementata
- Quality gates + evidence pack

## 5) Exit criteria Sprint 1.3

- [ ] Agent definitions valide; `aria repl` mostra Conductor + Search + 5 system agents
- [ ] Skill `deep-research` eseguita end-to-end con ≥ 3 fonti reali recuperate (una sessione live)
- [ ] `aria-memory/recall query="LOCOMO"` restituisce il report salvato
- [ ] Provider health endpoint metrics attivo (`aria_provider_status{provider=...}`)
- [ ] Cache hit verificata su seconda query identica entro TTL
- [ ] Coverage search module ≥ 75%, agents bridge ≥ 65%
- [ ] ADR-0006 accepted
- [ ] `docs/operations/provider_exhaustion.md` mergato

## 6) Deliverable checklist

- [ ] `.aria/kilocode/agents/{aria-conductor,search-agent,workspace-agent}.md` (workspace stub)
- [ ] `.aria/kilocode/agents/_system/{compaction-agent,summary-agent,memory-curator,blueprint-keeper,security-auditor}.md`
- [ ] `.aria/kilocode/skills/{planning-with-files,deep-research,pdf-extract,hitl-queue,memory-distillation,blueprint-keeper}/SKILL.md` (+ `resources/`, `scripts/` dove applicabile)
- [ ] `.aria/kilocode/skills/_registry.json` aggiornato
- [ ] `src/aria/agents/search/{router,dedup,cache,health,providers/*}.py`
- [ ] `src/aria/tools/{tavily,firecrawl}/mcp_server.py`
- [ ] `src/aria/tools/ops/mcp_server.py` (se scelta aria-ops)
- [ ] `src/aria/gateway/conductor_bridge.py`
- [ ] `src/aria/utils/prompt_safety.py`
- [ ] `scripts/wrappers/{tavily,firecrawl}-wrapper.sh` attivi
- [ ] `scripts/validate_agents.py`, `scripts/validate_skills.py`
- [ ] `tests/unit/agents/search/` + `tests/integration/agents/search/`
- [ ] `docs/operations/provider_exhaustion.md`
- [ ] ADR-0006 (e opzionalmente ADR-0008) accepted
- [ ] Implementation Log entry

## 7) Quality gates

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/aria/agents/search src/aria/tools src/aria/gateway/conductor_bridge.py src/aria/utils/prompt_safety.py

uv run pytest tests/unit tests/integration -q --cov=aria.agents.search --cov=aria.tools --cov=aria.gateway.conductor_bridge --cov-report=term-missing

# Validation
uv run python scripts/validate_agents.py
uv run python scripts/validate_skills.py

# MCP smoke
./bin/aria repl      # in REPL:
                     # /agents list               -> 8 agent
                     # /tools list                -> include tavily-mcp/*, firecrawl-mcp/*, brave-mcp/*, aria-memory/*
                     # /skills list               -> 6 skill

# E2E demo (manuale, con account Telegram test)
# "ARIA, ricerca approfondita su LOCOMO long-term memory"
```

## 8) Risk register

| ID  | Rischio                                                            | Impatto | Mitigazione                                                                |
|-----|--------------------------------------------------------------------|---------|----------------------------------------------------------------------------|
| R31 | KiloCode CLI non offre API stabile per spawn child session         | Alto    | Documentare opzione A vs B; fallback `kilocode chat --input` + file IPC   |
| R32 | Prompt injection da tool_output malizioso                          | Alto    | Frame `<<TOOL_OUTPUT>>` + sanitizer + system prompt vietante (ADR-0006)   |
| R33 | Provider API breaking change (Tavily/Firecrawl/Exa)                | Medio   | Wrapper adapter isolati; test contract su fixture JSON                     |
| R34 | Dedup/ranking con rapidfuzz lento su grandi insiemi                | Basso   | Top-N hits limitato a 50 per intent; algoritmi O(n log n)                   |
| R35 | Wrapper bash non portabile o eredita env polluto                  | Medio   | `env -i` reset + solo var necessarie esplicite                              |
| R36 | Cache search collide con entry user legittima per P6              | Basso   | Tag esplicito `search_cache`; query filtering esclude di default            |
| R37 | Skill LLM interpreta `<<TOOL_OUTPUT>>` come tag XML attivo        | Medio   | Usare delimitatori non-XML: `"[BEGIN_TOOL_OUTPUT]...[END_TOOL_OUTPUT]"` se ADR-0006 lo preferisce |
| R38 | Budget Sprint 1.3 esaurito (skills markdown molte)                 | Basso   | Stub skills `_system/*` aspettano Fase 2                                   |

## 9) ADR collegati

- **ADR-0006 — Prompt Injection Mitigation** (Accepted): frame sintattico + sanitizer + system prompt.
- **ADR-0008 (opzionale) — aria-ops MCP server separato per HITL tools**: se scelta, formalizzare.

## 10) Tracciabilita blueprint -> task

| Sezione blueprint                 | Task Sprint 1.3                     |
|-----------------------------------|-------------------------------------|
| §8.2 ARIA-Conductor               | W1.3.A                              |
| §8.3.1 Search-Agent               | W1.3.A + W1.3.B + W1.3.D            |
| §8.4 Sub-agenti sistema           | W1.3.A stubs                        |
| §8.5 Matrice capabilities         | W1.3.A (allowed-tools)              |
| §8.6 Child sessions isolate       | W1.3.I                              |
| §9.1-9.3 Skills format + registry | W1.3.B                              |
| §9.4 Skills versioning            | `_registry.json`                    |
| §9.5 Skills fondative MVP         | W1.3.B                              |
| §10.1-10.3 MCP ecosystem          | W1.3.H (wrapper custom)             |
| §10.4 Wrapper Python→MCP          | W1.3.H                              |
| §11.1-11.6 Search-Agent           | W1.3.C + W1.3.D + W1.3.E + W1.3.F + W1.3.G + W1.3.K |
| §14.3 Prompt injection mitigation | W1.3.I + ADR-0006                   |

## 11) Note prescrittive per l'LLM implementatore (anti-allucinazione)

### 11.1 Riferimenti ufficiali

| Provider     | Docs autoritative                                     |
|--------------|-------------------------------------------------------|
| Tavily       | https://docs.tavily.com/                              |
| Firecrawl    | https://docs.firecrawl.dev/                           |
| Brave Search | https://brave.com/search/api/                         |
| Exa          | https://exa.ai/                                       |
| Brave MCP    | `@brave/brave-search-mcp-server` npm (upstream)       |
| FastMCP      | https://gofastmcp.com/                                |
| rapidfuzz    | https://rapidfuzz.github.io/RapidFuzz/                |

### 11.2 Errori comuni

1. **NON** hardcoddare API key in codice o in `mcp.json` — usare `${VAR}` espanso da wrapper che a sua volta chiama `CredentialManager`.
2. **NON** scrivere provider adapter che espongono raw payload al modello — normalizzare sempre in `SearchHit`.
3. **NON** saltare `canonicalize_url` prima di dedup — falsi negativi garantiti con UTM params.
4. **NON** scrivere query cache con TTL > 24h — SEM blueprint §11.5 limita a 6h default.
5. **NON** inserire `<<TOOL_OUTPUT>>` nei messaggi utente: e riservato al system prompt del Conductor; violazione apre vettore di prompt injection.
6. **NON** chiamare direttamente `brave-mcp` dal Conductor: il Conductor delega al Search-Agent child session (§8.1).
7. **NON** implementare nuovi tool nell'`aria-memory` MCP — se servono nuovi tool, creare nuovo MCP server (es. `aria-ops`) per preservare P9.
8. **NON** usare `os.system` o `os.popen` per spawn KiloCode — usare `asyncio.create_subprocess_exec` con `close_fds=True`.
9. **NON** consumare stdout MCP (reservato JSON-RPC) — logger sempre su file.
10. **NON** rimuovere `disabled: true` da `playwright` in `mcp.json` — Fase 2.

### 11.3 Specifiche Python layer vs skill markdown

La **responsabilita di orchestrazione** e del **modello LLM guidato dalla skill markdown**. Il Python layer fornisce **tool atomici** (search, scrape) con comportamento deterministico (rotation, dedup, cache, health). NON duplicare l'orchestrazione in Python: se trovi un loop Python che decide quante sub-query fare, quale provider chiamare in sequenza, come sintetizzare il report → **stai violando §8.1**.

Eccezione lecita: rotation key e circuit breaker sono deterministici e infrastrutturali, stanno in Python.

### 11.4 Sicurezza

- **Whitelist egress**: se configurato `ARIA_EGRESS_WHITELIST`, ogni `httpx` call verso dominio fuori whitelist logga warning (blueprint §14.3). In Sprint 1.3 solo log; enforcement bloccante in Fase 2.
- **Secret in query**: mai loggare query utente che inizino con `sk-`, `ghp_`, `exa-`, `tvly-`; `redact_secret` detector.
- **Child session file access**: il Conductor child non deve poter scrivere fuori `.aria/kilocode/sessions/children/`. Configurare filesystem MCP con root bounded.

### 11.5 Non-requisiti

- NON implementare `blueprint-keeper` logica reale: solo stub markdown.
- NON implementare LLM-based intent classifier: regex in Sprint 1.3, LLM in Fase 2.
- NON aggiungere Playwright (Fase 2).
- NON creare UI web per demo: basta Telegram + CLI.
- NON collegare Workspace-Agent (Sprint 1.4).

---

**Fine Sprint 1.3.** Exit criteria verdi → procedere con `sprint-04.md`.
