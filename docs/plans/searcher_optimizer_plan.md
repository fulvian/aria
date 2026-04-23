# Searcher Optimizer Plan (Apr 2026)

## 1) Obiettivo

Definire un sistema di routing multi-provider per `search-agent` che:

- massimizzi l'uso di provider **gratuiti senza limite pratico** (self-hosted),
- preservi i provider a **credito/API key** (consumo monetario),
- mantenga qualità, freschezza e affidabilità su query agentiche reali,
- renda osservabile e governabile il costo per query.

Questo piano combina:
1) analisi AS-IS del codice ARIA,
2) benchmark qualitativo provider (fonti ufficiali online),
3) best practice moderne (fino ad Apr 2026),
4) roadmap implementativa incrementale.

---

## 2) AS-IS: come funziona oggi il search-agent

## 2.1 Architettura corrente

- Layer LLM orchestration: `.aria/kilocode/agents/search-agent.md`
- Router intent-aware Python: `src/aria/agents/search/router.py`
- Schema intent/routing: `src/aria/agents/search/schema.py`
- MCP servers provider-specific:
  - `src/aria/tools/searxng/mcp_server.py`
  - `src/aria/tools/brave` (upstream npm wrapper)
  - `src/aria/tools/tavily/mcp_server.py`
  - `src/aria/tools/exa/mcp_server.py`
  - `src/aria/tools/firecrawl/mcp_server.py`
- Gestione credenziali + rotazione + circuit breaker:
  - `src/aria/credentials/manager.py`
  - `src/aria/credentials/rotator.py`
- Cache query-level: `src/aria/agents/search/cache.py`
- Dedup + ranking: `src/aria/agents/search/dedup.py`

## 2.2 Selezione provider oggi (punti chiave)

1. **Intent classification regex-based** (`router.py` + `schema.py`).
2. Routing per intent da `INTENT_ROUTING` (`schema.py`).
3. Filtro su health (`ProviderHealth`) prima del tentativo provider.
4. Per provider con key: `CredentialManager.acquire()` + `report_success/failure()`.
5. Rotazione chiavi dentro MCP server (max 5 tentativi su Tavily/Exa/Firecrawl search).
6. Dedup + ranking + cache (TTL 6h).

## 2.3 Gap emersi rispetto all'obiettivo “free-first massivo”

1. **Nessun policy engine cost-aware globale**:
   - non esiste una strategia centralizzata “free-unlimited first, paid later”.
2. **Incoerenza tra routing Python e routing LLM doc**:
   - `schema.py` per `GENERAL` usa `brave -> tavily`, mentre lo spec agente promuove Exa primario.
3. **Fallback semantico incompleto su alcuni path**:
   - alcuni adapter ritornano liste vuote in errore (es. path storici) invece di errori classificati.
4. **Mancanza di budget policy per query/sessione**:
   - non c'e un cap esplicito tipo “spendi crediti solo se confidence < soglia”.
5. **Version drift API Firecrawl**:
   - codice usa endpoint `v1` mentre docs correnti promuovono `v2`; rischio manutenzione e costo non allineato.

---

## 3) Ricerca online provider (fonti ufficiali)

## 3.1 Tavily

Fonti:
- https://docs.tavily.com/documentation/api-credits
- https://docs.tavily.com/documentation/api-reference/endpoint/search
- https://docs.tavily.com/documentation/best-practices/best-practices-search

Caratteristiche rilevanti:
- Free tier: **1,000 credits/mese**.
- Search cost:
  - `basic/fast/ultra-fast`: 1 credito richiesta (nota docs best practices: ultra-fast talvolta indicato 0.5 in esempi, da verificare in produzione con usage response),
  - `advanced`: 2 crediti.
- Errori distintivi utili al routing: `429` rate limit, `432` plan/key usage limit.
- Best practice ufficiali:
  - query < 400 char,
  - decomposizione in sub-query,
  - 2-step search -> extract per contenuto profondo,
  - controllo esplicito del `search_depth` per governare costo/latency.

## 3.2 Exa

Fonti:
- https://exa.ai/pricing
- https://docs.exa.ai/reference/search

Caratteristiche rilevanti:
- Free tier: **fino a 1,000 requests/mese** (pricing page).
- Pricing Search: **$7 / 1k requests** (base fino a 10 risultati).
- Deep Search: costo superiore ($12 / 1k richieste), utile solo per query ad alta complessità.
- API moderna con modalità `type` (`auto`, `fast`, `deep`, `instant`) e metrica costo nel payload (`costDollars`), utile per telemetria e budget enforcement.

## 3.3 Brave Search API

Fonti:
- https://brave.com/search/api/
- https://api-dashboard.search.brave.com/app/documentation/web-search/get-started

Caratteristiche rilevanti:
- Piano Search: **$5 / 1,000 richieste**.
- Free monthly credits: **$5/mese** inclusi.
- Rate limit dipende dal piano (es. Search: 50 QPS da pagina marketing; su free plan practical cap molto più basso in burst).
- Best practice ufficiale: usare `query.more_results_available` per paginazione efficiente e non sprecare chiamate.
- Buono per web/news/images/video/local enrichment.

## 3.4 Firecrawl

Fonti:
- https://www.firecrawl.dev/pricing
- https://docs.firecrawl.dev
- Context7 `/websites/firecrawl_dev` (billing + best usage)

Caratteristiche rilevanti:
- Free: **500 credits one-time**.
- Costi:
  - Search: 2 crediti per 10 risultati,
  - Scrape/Crawl: 1 credito per pagina base,
  - JSON extraction/enhanced mode: costo addizionale.
- Endpoint e workflow orientati a scraping profondo, non ideale come first-line search bulk.
- Best practice: usare Search per discovery e Scrape/Extract solo su short-list di URL realmente necessari.

## 3.5 SearXNG (self-hosted)

Fonti:
- https://docs.searxng.org
- https://docs.searxng.org/dev/search_api.html

Caratteristiche rilevanti:
- Open-source metasearch self-hosted.
- Nessun costo per richiesta API (salvo costi infrastrutturali locali).
- Endpoint semplici `/search` con `format=json`.
- Può aggregare molti motori, configurabili da `settings.yml`.
- Ideale come **backbone free-unlimited** del routing.

## 3.6 SerpAPI

Fonte:
- https://serpapi.com/pricing

Caratteristiche rilevanti:
- Free plan: **250 searches/mese**.
- Paid entry: $25/mese per 1,000 searches.
- Ottimo fallback finale, ma non adatto come provider “massivo gratuito”.

---

## 4) Best practice multiprovider agentic (fino ad Apr 2026)

Fonti principali:
- Tavily best practices docs.
- Azure AI Search hybrid RRF docs: https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking
- Elastic RRF docs: https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion
- OpenSearch RRF article: https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/

Pattern consolidati:

1. **Rank fusion > score fusion** quando si combinano engine eterogenei (RRF con k~60 default).
2. **Retry/timeout/circuit breaker** separati per errore transitorio vs errore quota.
3. **Cost-aware routing**: non usare deep/advanced mode come default.
4. **Two-step retrieval**:
   - broad cheap search,
   - deep scrape/extract solo su candidate top-N.
5. **Adaptive pagination** (es. Brave `more_results_available`) per evitare consumo inutile.
6. **Query decomposition** per task complessi invece di query monolitiche.
7. **Observability di costo e qualità**: costo/query, provider hit-rate, freshness, empty-result rate.

---

## 5) Strategia target: Free-First Economic Router

## 5.1 Principio operativo

1. **Tier A (free-unlimited/self-hosted)**: SearXNG (primario massivo).
2. **Tier B (free-limited monthly credits)**: Brave, Tavily, Exa.
3. **Tier C (costly/deep extraction)**: Firecrawl.
4. **Tier D (last resort paid fallback)**: SerpAPI.

Default: usare Tier A finche quality gate non fallisce; salire di tier solo quando necessario.

## 5.2 Nuova policy di selezione (alto livello)

Per ogni query:

- Step 1: classifica intento (`news`, `academic`, `general`, `url-specific`, `deep-structure`).
- Step 2: genera candidate provider ordinati da:
  - costo marginale atteso,
  - quota residua,
  - health score,
  - fit per intent.
- Step 3: esegui Tier A.
- Step 4: valuta quality gates:
  - min risultati unici,
  - min coverage domini,
  - min recency score,
  - min confidence ranking.
- Step 5: se fallisce, promuovi progressivamente a Tier B, poi C/D.
- Step 6: applica RRF su risultati multi-provider e dedup finale.

## 5.3 Quality gates consigliati

- `unique_results >= 6` (o dinamico su intent).
- `distinct_domains >= 4`.
- `recency_ratio >= 0.4` per intent news.
- `top3_score_mean >= 0.65` (normalizzato internamente).
- se query include URL specifico: bypass search broad e usa pipeline scrape-first low-cost (`fetch` -> Firecrawl solo se necessario).

## 5.4 Budget guardrails

- Budget per query (credits budget) e per sessione.
- Hard stop per provider crediti se:
  - quota residua sotto soglia,
  - consumo giornaliero oltre limite.
- Policy “reserve mode”:
  - preserva Exa/Tavily per intent academic/high-precision,
  - preserva Firecrawl per estrazione strutturata ad alto valore.

## 5.5 RRF per fusione risultati

- Introdurre fusione RRF sopra output già deduplicati per-provider.
- Parametri iniziali:
  - `rank_constant = 60` (baseline industry),
  - `rank_window_size` 20-40 per contenere latenza.
- Vantaggio: robustezza tra score eterogenei e minor tuning manuale.

---

## 6) Modifiche architetturali proposte in ARIA

## 6.1 Nuovi componenti

1. `search/cost_policy.py`
   - costo stimato per tool/provider/modalità.
2. `search/quota_state.py`
   - quota residua runtime + reset windows.
3. `search/quality_gate.py`
   - valuta sufficienza risultati prima di escalation.
4. `search/fusion.py`
   - RRF + fallback ranking.
5. `search/telemetry.py`
   - metriche costo/qualità/provider.

## 6.2 Aggiornamenti componenti esistenti

- `schema.py`: routing table allineata a policy economica nuova.
- `router.py`: introduzione decisione multi-criterio (cost + health + intent).
- MCP servers: standardizzare error contract `ToolError` vs empty-success.
- Firecrawl adapter/server: allineamento API version e policy cost-aware (v2 where applicable).

## 6.3 Contratto errori unificato

Classi minime:
- `quota_exhausted`
- `rate_limited`
- `transient_upstream`
- `invalid_request`
- `provider_down`

Regola:
- `quota_exhausted`/`rate_limited` => salta provider e aggiorna budget state,
- `transient_upstream` => retry limitato poi fallback,
- mai mascherare errore reale con `results: []` salvo “no findings” verificato.

---

## 7) Piano implementativo (phased)

## Phase 0 — Hardening (1-2 giorni)

- Allineare routing doc/code (`search-agent.md` vs `schema.py`).
- Uniformare gestione errori MCP (niente swallow silenzioso).
- Aggiungere telemetria minima per provider outcome.

DoD:
- test integrazione provider pass,
- errore quota distinguibile da “zero risultati”.

## Phase 1 — Free-First Router (2-4 giorni)

- Implementare policy tierizzata A->B->C->D.
- Inserire quality gate prima di scalare provider a pagamento.
- Introdurre budget per query/sessione.

DoD:
- >70% query generali servite solo da SearXNG/Brave in benchmark interno.
- consumo Tavily/Exa ridotto senza calo significativo qualità.

## Phase 2 — Fusion & Adaptive Strategy (3-5 giorni)

- Implementare RRF fusion.
- Adaptive pagination e query decomposition automatica.
- dynamic depth tuning (`basic/fast` default; `advanced` only on demand).

DoD:
- miglioramento coverage/freshness su query news/academic.
- riduzione empty-result e fallback storms.

## Phase 3 — Governance & Continuous Optimization (continuo)

- dashboard KPI cost/quality.
- autotuning soglie quality gates.
- review mensile provider economics e performance.

---

## 8) KPI target

- `paid_calls_ratio` (chiamate paid / total): target -40% su 30 giorni.
- `avg_credit_cost_per_query`: target -35%.
- `quality_pass_rate_first_tier`: target >= 60%.
- `fallback_success_rate`: target >= 95%.
- `empty_success_rate` (success true ma inutili): target < 3%.
- `p95_latency`: non peggiorare oltre +15% rispetto baseline.

---

## 9) Rischi e mitigazioni

1. **Qualità inferiore su solo free providers**
   - mitigazione: quality gates + escalation selettiva.
2. **Rate-limit su provider free-limited (Brave free credits)**
   - mitigazione: throttle + pager intelligente + SearXNG primario.
3. **Drift API provider (Firecrawl v1/v2)**
   - mitigazione: adapter compatibility layer + integration tests versionati.
4. **Overfitting soglie quality gate**
   - mitigazione: A/B su query set realistico, tuning periodico.

---

## 10) Decisioni operative immediate (raccomandate)

1. Promuovere SearXNG a default assoluto per `general/privacy/news-first-pass`.
2. Usare Brave come secondo livello economico (quando non saturato).
3. Riservare Tavily/Exa a:
   - academic,
   - query ad alta precisione,
   - fallback quando quality gate fallisce.
4. Usare Firecrawl solo per:
   - URL-specific scraping,
   - estrazione strutturata mirata top-N.
5. Introdurre metriche costo/qualità prima di ulteriori ottimizzazioni profonde.

---

## 11) Provenienza (fonti)

### Codice e docs interne ARIA

- `.aria/kilocode/agents/search-agent.md`
- `src/aria/agents/search/router.py`
- `src/aria/agents/search/schema.py`
- `src/aria/tools/tavily/mcp_server.py`
- `src/aria/tools/exa/mcp_server.py`
- `src/aria/tools/firecrawl/mcp_server.py`
- `src/aria/tools/searxng/mcp_server.py`
- `src/aria/agents/search/providers/*.py`
- `src/aria/credentials/manager.py`
- `src/aria/credentials/rotator.py`
- `docs/llm_wiki/wiki/search-agent.md`
- `docs/llm_wiki/wiki/tools-mcp.md`

### Fonti esterne ufficiali (consultate il 2026-04-23)

- Tavily API credits: https://docs.tavily.com/documentation/api-credits
- Tavily Search API: https://docs.tavily.com/documentation/api-reference/endpoint/search
- Tavily best practices: https://docs.tavily.com/documentation/best-practices/best-practices-search
- Exa pricing: https://exa.ai/pricing
- Exa search reference: https://docs.exa.ai/reference/search
- Brave Search API page: https://brave.com/search/api/
- Brave API docs (get-started): https://api-dashboard.search.brave.com/app/documentation/web-search/get-started
- Firecrawl docs: https://docs.firecrawl.dev
- Firecrawl pricing: https://www.firecrawl.dev/pricing
- SearXNG docs: https://docs.searxng.org
- SearXNG search API: https://docs.searxng.org/dev/search_api.html
- SerpAPI pricing: https://serpapi.com/pricing
- Azure RRF: https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking
- Elastic RRF: https://www.elastic.co/docs/reference/elasticsearch/rest-apis/reciprocal-rank-fusion
- OpenSearch RRF: https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/

### Context7 verification

- `/websites/tavily`
- `/websites/firecrawl_dev`
- `/websites/api-dashboard_search_brave_app`

last_updated: 2026-04-23
