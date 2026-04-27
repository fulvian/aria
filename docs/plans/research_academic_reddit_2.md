# Piano di Implementazione v2 — Provider Accademici + Social per ARIA Research Agent

> **Documento**: `docs/plans/research_academic_reddit_2.md`
> **Versione**: 2.0 (audit-corrected)
> **Data**: 2026-04-27
> **Supersedes**: `docs/plans/research_academic_reddit_1.md` (v1.0)
> **Analisi sorgente**: `docs/analysis/research_agent_enhancement.md`
> **Blueprint rif.**: `docs/foundation/aria_foundation_blueprint.md` §11
> **Stato**: DRAFT — Pre-implementazione, post-audit severo
> **Audit Context7**: 2026-04-27 (4 librerie verificate, fonti riportate)

---

## Indice

1. [Cambi rispetto a v1](#1-cambi-rispetto-a-v1)
2. [Findings dell'audit (severity-ordered)](#2-findings-dellaudit-severity-ordered)
3. [Conformità Blueprint + Ten Commandments](#3-conformità-blueprint--ten-commandments)
4. [Provider selezionati v2 — Context7 verified](#4-provider-selezionati-v2--context7-verified)
5. [Strategia di implementazione v2](#5-strategia-di-implementazione-v2)
6. [Modifiche al Router](#6-modifiche-al-router)
7. [Modifiche a Intent Classifier](#7-modifiche-a-intent-classifier)
8. [Wrapper script + mcp.json](#8-wrapper-script--mcpjson)
9. [Credenziali — pattern allineato ARIA](#9-credenziali--pattern-allineato-aria)
10. [ADR obbligatorio (P10)](#10-adr-obbligatorio-p10)
11. [Strategy di Test](#11-strategy-di-test)
12. [Pre-existing issues confermate](#12-pre-existing-issues-confermate)
13. [Piano di rollout](#13-piano-di-rollout)
14. [Wiki maintenance (CLAUDE.md mandate)](#14-wiki-maintenance-claudemd-mandate)
15. [Rischi e mitigazioni](#15-rischi-e-mitigazioni)
16. [Quality gates](#16-quality-gates)
17. [Stima effort](#17-stima-effort)
18. [Appendici](#18-appendici)

---

## 1. Cambi rispetto a v1

| # | Cambio | Motivazione | Severità |
|---|--------|-------------|----------|
| **C1** | Europe PMC: **MCP** (`scientific-papers-mcp`) anziché provider Python nativo | Viola P8 (MCP > Skill > Python). YAGNI argument v1 errato: con un MCP esistente che copre Europe PMC, il pattern ARIA impone di usarlo. | 🔴 ALTA |
| **C2** | Reddit: **OAuth obbligatorio** (no anonymous claim) | Context7 docs di `jordanburke/reddit-mcp-server` riportano solo pattern OAuth (`REDDIT_CLIENT_ID`/`SECRET`). Claim "anonymous 10 req/min" v1 NON verificato. | 🔴 ALTA |
| **C3** | **ADR-0006 obbligatorio** prima di mergeare codice | Blueprint §11.1 hardcoda 6 provider + §11.2 routing. Aggiunta 4 provider + SOCIAL intent = divergence → P10 (Self-Documenting Evolution). | 🔴 ALTA |
| **C4** | `scientific-papers-mcp` come fonte unica per arXiv + Europe PMC | Il singolo MCP copre arXiv, Europe PMC, OpenAlex, biorxiv, CORE, PMC. Riduce wrapper, RAM, manutenzione. `blazickjp/arxiv-mcp-server` opzionale solo per PDF read pipeline. | 🟡 MEDIA |
| **C5** | arXiv: install `arxiv-mcp-server[pdf]` (non plain) | Senza `[pdf]` extra, paper PDF-only (es. pre-2007) falliscono download. Verificato Context7. | 🟡 MEDIA |
| **C6** | NCBI key in **api-keys.enc.yaml** (SOPS) + `CredentialManager` | Plan v1 usa raw env var. ARIA pattern (brave-wrapper, exa-wrapper) acquisisce sempre via SOPS+CredentialManager anche per chiave singola. P4 (Local-First, Privacy-First). | 🟡 MEDIA |
| **C7** | PubMed env vars completi: aggiunto `UNPAYWALL_EMAIL` + defaults Zod | Context7 docs di `cyanheads/pubmed-mcp-server` includono `UNPAYWALL_EMAIL` per full-text fallback. Plan v1 omesso. | 🟡 MEDIA |
| **C8** | Wiki maintenance esplicita (3 file, ts assoluti) | Plan v1 generico ("aggiornare wiki"). CLAUDE.md mandate: aggiornare `index.md` (`Last Updated`), `research-routing.md`, append `log.md` con timestamp. | 🟢 BASSA |
| **C9** | Test fix scope enumerato (file:line) | Plan v1 elenca file ma non i match esatti. Audit ha verificato: 4 file, 18 occorrenze `FIRECRAWL` da bonificare. | 🟢 BASSA |

---

## 2. Findings dell'audit (severity-ordered)

### F1 — Reddit "anonymous mode" claim non verificato 🔴

**Evidenza**: Context7 query `/jordanburke/reddit-mcp-server` (2026-04-27) restituisce SOLO snippet di config con `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` come env required. Nessun snippet documenta modalità anonima o rate limit 10 req/min senza credenziali.

**Sorgente analisi v0**: `docs/analysis/research_agent_enhancement.md` §4.3 cita "modalità anonima 10 req/min" ma la fonte primaria non è verificata su Context7.

**Decisione v2**:
- Reddit MCP **richiede OAuth** in produzione.
- HITL Milestone: registrare app Reddit (https://www.reddit.com/prefs/apps), salvare `client_id`+`client_secret` in SOPS YAML.
- Se OAuth non disponibile: **defer** integrazione Reddit MCP; SearXNG `reddit` engine come fallback unico per `Intent.SOCIAL`.

### F2 — Europe PMC native provider viola P8 🔴

**Tool Priority Ladder** (Ten Commandment #8): `MCP > Skill > Python script; never skip a layer`.

**Plan v1 §3.3 motivazione**: "YAGNI: non serve un mega-MCP con 6 fonti quando ci serve solo Europe PMC".

**Audit risposta**:
- P8 non ammette eccezioni "perché ne basta uno".
- `scientific-papers-mcp` (Context7 ID `/benedict2310/scientific-papers-mcp`, snippets 5319, benchmark 67.0) espone tool `search_papers` con `source: "europepmc"` — verificato Context7.
- Lo stesso MCP fornisce arXiv (sostituendo `blazickjp/arxiv-mcp-server` per la sola search), riducendo da 2 MCP a 1.
- Wrapper Python nativo richiederebbe codice da mantenere, test, error handling, mentre MCP è zero-LOC.

**Decisione v2**: **adottare `scientific-papers-mcp`** per Europe PMC + arXiv search. Mantenere `blazickjp/arxiv-mcp-server` SOLO se serve la pipeline `download_paper` + `read_paper` (storage locale PDF).

### F3 — ADR mancante (P10) 🔴

**Blueprint §11.1** (Provider supportati MVP) hardcoda 6 provider: Tavily, Firecrawl, Brave, Exa, SearXNG, SerpAPI.
**Blueprint §11.2** definisce `INTENT_ROUTING` con 3 chiavi (`general/news`, `academic`, `deep_scrape`).

**Plan v2 introduce**:
- 3+ nuovi provider (PubMed, scientific-papers, opzionale arxiv-mcp-server, opzionale Reddit)
- Nuovo intent `SOCIAL`
- Riordinamento ladder `ACADEMIC` (oggi == `GENERAL_NEWS`)

**P10**: "Every divergence from blueprint registered via ADR".

**Decisione v2**: **ADR-0006-research-agent-academic-social-expansion.md** obbligatorio. Senza ADR mergeato, la fase 4 (router update) NON parte. Vedi §10.

### F4 — Consolidamento mancato 🟡

**Sceintific-papers-mcp** (verified Context7) espone `search_papers` con `source` parametrizzabile su: `arxiv | openalex | pmc | europepmc | biorxiv | core`.

**Plan v1**: usa 2 MCP separati (cyanheads pubmed + blazickjp arxiv) + 1 provider Python nativo (Europe PMC) = 3 sorgenti di codice.

**Plan v2**:
- `scientific-papers-mcp` copre arXiv + Europe PMC (search-only)
- `cyanheads/pubmed-mcp-server` resta dedicato a PubMed (9 tool specializzati: spell_check, MeSH, ID convert, fulltext via Unpaywall)
- `blazickjp/arxiv-mcp-server` **opzionale Phase 2**: solo se serve PDF download/read

Riduzione: 4 MCP target → 2 MCP P0 + 1 opzionale.

### F5 — arXiv `[pdf]` extra 🟡

Context7 (`/blazickjp/arxiv-mcp-server`) docs:
> "Install with PDF support for older papers: `uv tool install 'arxiv-mcp-server[pdf]'`"

Plan v1 §3.2 omette. Fallirebbe su paper pre-2007 (solo PDF, no HTML). Se `blazickjp` viene mantenuto in Phase 2, install command corretta:

```bash
uv tool install 'arxiv-mcp-server[pdf]'
```

### F6 — Credenziali fuori pattern ARIA 🟡

**Pattern esistente** (`scripts/wrappers/tavily-wrapper.sh`):
1. Wrapper acquisisce key via `CredentialManager.acquire(provider)` (legge da `api-keys.enc.yaml`).
2. Pre-verifica chiave (HTTP probe).
3. Esegue MCP server con env var iniettata.

**Plan v1 §3.1**: `mcp.json` riceve `${NCBI_API_KEY}` da env, non da SOPS. Bypassa il pattern.

**Decisione v2**:
- Aggiungere PubMed in `api-keys.enc.yaml` (anche se 1 sola chiave).
- Wrapper `pubmed-wrapper.sh` segue stesso pattern di brave/exa.
- Vantaggio: chiave cifrata at-rest (P4), pronta per multi-account futuro.

### F7 — Wiki maintenance specs deboli 🟢

**CLAUDE.md "Wiki Maintenance (continuous)"**:
1. Aggiornare pagine in `docs/llm_wiki/wiki/`
2. Refresh `index.md` (raw source mapping)
3. Append timestamp in `log.md`

**Plan v1 §10 fase 7** dice "Aggiornare wiki" senza enumerare file/timestamp.

**Decisione v2**: vedi §14 — checklist esplicita.

---

## 3. Conformità Blueprint + Ten Commandments

| Commandment | Plan v2 — come è rispettato |
|-------------|------------------------------|
| **P1** Isolation First | Tutti gli MCP nuovi configurati in `.aria/kilocode/mcp.json` (workspace ARIA isolato); nessun impatto su KiloCode globale |
| **P2** Upstream Invariance | Nessuna fork/patch dei MCP server upstream; consumo via `npx`/`uv tool run` |
| **P3** Polyglot Pragmatism | MCP è il glue (TS/Python upstream); ARIA Python rimane invariato |
| **P4** Local-First, Privacy-First | NCBI key + Reddit OAuth in `api-keys.enc.yaml` (SOPS+age); nessun secret in mcp.json |
| **P5** Actor-Aware Memory | Risultati ricerca mantengono tag `tool_output` (stesso pattern esistente) |
| **P6** Verbatim Preservation | Risultati Tier 0 nel cache; nessuna modifica al pattern esistente |
| **P7** HITL on Destructive Actions | Reddit OAuth setup = HITL gate; nessun write Reddit (solo read in Phase 1) |
| **P8** Tool Priority Ladder | **MCP > Python** rispettato: Europe PMC via MCP (non native), tutti i 4 provider sono MCP |
| **P9** Scoped Toolsets | `search-agent.md` toolset attuale + 9 (PubMed) + 2 (scientific-papers) = stima ≤ 20 tool. Verifica in Phase 4 |
| **P10** Self-Documenting Evolution | **ADR-0006 OBBLIGATORIO** prima del merge — vedi §10 |

**Stella Polare check**: nessuna modifica del blueprint stesso; ADR registra divergenza in §11 senza alterarlo.

---

## 4. Provider selezionati v2 — Context7 verified

### 4.1 PubMed — `@cyanheads/pubmed-mcp-server`

| Caratteristica | Valore |
|----------------|--------|
| Context7 ID | `/cyanheads/pubmed-mcp-server` |
| Snippets | 1053 |
| Benchmark | 83.7 |
| License | Apache 2.0 |
| Versione | 2.6.4 (npm latest) |
| Installazione | `npx -y @cyanheads/pubmed-mcp-server@latest` (non richiede Bun) |
| Transport | stdio |
| Env required | `NCBI_API_KEY` (opt), `NCBI_ADMIN_EMAIL`, `MCP_TRANSPORT_TYPE=stdio` |
| Env optional | `UNPAYWALL_EMAIL` (full-text fallback), `NCBI_TOOL_IDENTIFIER`, `NCBI_REQUEST_DELAY_MS` (default 334), `NCBI_MAX_RETRIES` (default 6), `NCBI_TIMEOUT_MS` (default 30000) |
| Tools | 9 (search_articles, fetch_articles, fetch_fulltext, format_citations, find_related, spell_check, lookup_mesh, lookup_citation, convert_ids) |

**Sorgente Context7**: snippet "Configure Self-Hosted PubMed Instance with npx" + "Configure Server Environment Variables with Zod" (recuperati 2026-04-27).

### 4.2 Scientific Papers — `benedict2310/scientific-papers-mcp` ⭐ NUOVO

| Caratteristica | Valore |
|----------------|--------|
| Context7 ID | `/benedict2310/scientific-papers-mcp` |
| Snippets | 5319 |
| Benchmark | 67.0 |
| Sorgenti supportate | arxiv, openalex, pmc, **europepmc**, biorxiv, core |
| Tools chiave | `search_papers(source, query, field, sortBy)`, `fetch_content(id)`, `list_categories(source)` |
| Endpoint Europe PMC | `https://www.ebi.ac.uk/europepmc/webservices/rest` (10 req/min, no key) |
| Installazione | `npx -y @futurelab-studio/latest-science-mcp@latest` (npm package name, verified 2026-04-27) |

**Sorgente Context7**: snippet "Search Papers by Query on Europe PMC" + "List Available Categories".

**Razionale scelta**:
- Europe PMC nativo nel tool, no codice ARIA da scrivere.
- arXiv coperto (anche se senza pipeline PDF storage).
- Bonus future: OpenAlex, biorxiv, CORE attivabili senza nuovi MCP.

### 4.3 arXiv standalone — `blazickjp/arxiv-mcp-server` (Phase 2, opzionale)

| Caratteristica | Valore |
|----------------|--------|
| Context7 ID | `/blazickjp/arxiv-mcp-server` |
| Snippets | 112 |
| Benchmark | 76.1 |
| Installazione | `uv tool install 'arxiv-mcp-server[pdf]'` (con extra PDF) |
| Avvio | `uv tool run arxiv-mcp-server --storage-path <path>` |
| Tools | `search_papers`, `download_paper`, `list_papers`, `read_paper` |
| Use case | Solo se serve scaricare/leggere PDF localmente |

**Decisione P0/P2**: **Phase 2 opzionale**. Se `scientific-papers-mcp` arXiv search è sufficiente per il workflow corrente, skip questo MCP (riduce 1 wrapper, ~20 MB RAM, 1 dipendenza uv).

### 4.4 Reddit — `jordanburke/reddit-mcp-server` (OAuth obbligatorio)

| Caratteristica | Valore |
|----------------|--------|
| Context7 ID | `/jordanburke/reddit-mcp-server` |
| Snippets | 39 |
| License | MIT |
| Installazione | `npx reddit-mcp-server` |
| Env **required** | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` (per stdio mode) |
| Env optional | `REDDIT_USER_AGENT`, `REDDIT_USERNAME`, `REDDIT_PASSWORD` (per write ops) |
| Tools | 11 (read+write); v2 USA solo read tools |

**Sorgente Context7**: snippet "Configure Stdio Transport for Desktop/Cursor (JSON)" + "Reddit MCP Server Environment Setup" (2026-04-27).

**HITL gate**:
1. Utente registra app Reddit https://www.reddit.com/prefs/apps (type: `script`)
2. Salva `client_id` + `client_secret` in `api-keys.enc.yaml`
3. Verifica RBP compliance (Responsible Builder Policy, nov 2025)

**Fallback se HITL non si chiude**: Reddit MCP **non viene aggiunto**, intent `SOCIAL` usa solo SearXNG `reddit` engine + Tavily.

---

## 5. Strategia di implementazione v2

### 5.1 Fasi

```
Fase 0 (gate):     ADR-0006 redatto + approvato HITL                    [P0, blocking]
Fase 1 (pulizia):  Bonifica test FIRECRAWL refs                         [P0]
Fase 2 (P0 MCP):   PubMed + scientific-papers (Europe PMC + arXiv)      [P0]
Fase 3 (router):   Provider enum + Intent SOCIAL + INTENT_TIERS         [P0]
Fase 4 (intent):   INTENT_KEYWORDS update + classify_intent()           [P0]
Fase 5 (Reddit):   OAuth setup + Reddit MCP                             [P1, HITL gate]
Fase 6 (test):     Unit + integration nuovi provider                    [P0]
Fase 7 (arxiv-pdf):blazickjp/arxiv-mcp-server[pdf] OPZIONALE            [P2, conditional]
Fase 8 (wiki+ADR): Wiki maintenance + index/log/research-routing         [P0]
```

### 5.2 Dipendenze tra fasi

```
F0 (ADR)  ──────────────────────────────────► F3 (router)
                                       │
F1 (test) ────► F2 (P0 MCP) ─────────► F3 (router) ──► F4 (intent) ──► F6 (test)
                                                              │
                                  F5 (Reddit-HITL) ───────────┤
                                                              │
                                  F7 (arxiv-PDF)──────────────┤
                                                              ▼
                                                          F8 (wiki+ADR)
```

---

## 6. Modifiche al Router

### 6.1 `Provider` enum — esteso

`src/aria/agents/search/router.py`:

```python
class Provider(StrEnum):
    # Provider esistenti
    SEARXNG = "searxng"
    TAVILY = "tavily"
    EXA = "exa"
    BRAVE = "brave"
    FETCH = "fetch"
    WEBFETCH = "webfetch"

    # Nuovi v2
    PUBMED = "pubmed"
    SCIENTIFIC_PAPERS = "scientific_papers"   # copre arxiv + europepmc + altri
    REDDIT = "reddit"                          # solo se OAuth attivo
    ARXIV = "arxiv"                            # opzionale Phase 2 (blazickjp)
```

### 6.2 `Intent` enum — esteso

```python
class Intent(StrEnum):
    GENERAL_NEWS = "general/news"
    ACADEMIC = "academic"
    DEEP_SCRAPE = "deep_scrape"
    SOCIAL = "social"           # NUOVO v2
    UNKNOWN = "unknown"
```

### 6.3 `INTENT_TIERS` — ridisegnato

```python
INTENT_TIERS: dict[Intent, tuple[Provider, ...]] = {
    Intent.GENERAL_NEWS: (
        Provider.SEARXNG,
        Provider.TAVILY,
        Provider.EXA,
        Provider.BRAVE,
        Provider.FETCH,
    ),
    Intent.ACADEMIC: (
        Provider.SEARXNG,            # tier 1 — meta self-hosted
        Provider.PUBMED,             # tier 2 — biomedico specialized
        Provider.SCIENTIFIC_PAPERS,  # tier 3 — arXiv+Europe PMC+altri
        Provider.TAVILY,             # tier 4 — fallback generale LLM-ready
        Provider.EXA,                # tier 5 — semantic
        Provider.BRAVE,              # tier 6 — fallback
        Provider.FETCH,              # tier 7 — HTTP
    ),
    Intent.DEEP_SCRAPE: (
        Provider.FETCH,
        Provider.WEBFETCH,
    ),
    Intent.SOCIAL: (
        # Tier 1 condizionale a OAuth Reddit:
        Provider.REDDIT,             # solo se REDDIT_CLIENT_ID presente
        Provider.SEARXNG,            # tier fallback (engine reddit nativo)
        Provider.TAVILY,
        Provider.BRAVE,
    ),
}
```

**Nota condizionalità Reddit**: il router NON deve fallire se Reddit non è configurato. Soluzione:
- `_refresh_health` marca `Provider.REDDIT` come `DOWN` se mcp.json non contiene `reddit-mcp` o se chiavi mancanti.
- `route()` salta naturalmente al tier successivo (logica esistente già gestisce DOWN).

### 6.4 `route()` — keyless providers list aggiornata

```python
# router.py:226 (current)
if rotator_provider in ("searxng", "fetch", "webfetch"):
    return provider, None

# v2:
KEYLESS_PROVIDERS = frozenset({
    "searxng", "fetch", "webfetch",
    "scientific_papers",  # nessuna API key (Europe PMC + arXiv senza key)
})
if rotator_provider in KEYLESS_PROVIDERS:
    return provider, None
```

PubMed e Reddit usano key → passano dal Rotator.

### 6.5 `_refresh_health()` — esteso

```python
async def _refresh_health(self, provider: str) -> None:
    if provider in KEYLESS_PROVIDERS:
        self._health[provider] = HealthState.AVAILABLE
        return
    # ... existing logic per key-based providers (pubmed, reddit, tavily, ...)
```

---

## 7. Modifiche a Intent Classifier

`src/aria/agents/search/intent.py`:

```python
INTENT_KEYWORDS: dict[Intent, frozenset[str]] = {
    Intent.DEEP_SCRAPE: frozenset({
        "deep", "scrape", "crawl", "extract",
        "full page", "complete", "entire website",
        "all pages", "deep scrape", "scraping", "estrai",
    }),
    Intent.ACADEMIC: frozenset({
        "academic", "research", "paper", "journal", "article",
        "study", "scholar", "citation", "doi", "arxiv",
        "publication", "preprint", "conference", "proceedings",
        # NUOVI v2:
        "pubmed", "pmid", "europe pmc", "europepmc", "openalex",
        "biorxiv", "scientific", "experiment", "clinical trial",
        "abstract", "peer review", "literature review", "mesh",
        # IT esistenti:
        "ricerca", "pubblicazione", "studio", "articolo scientifico",
    }),
    Intent.GENERAL_NEWS: frozenset({
        "news", "latest", "current", "recent", "breaking",
        "today", "headline", "update",
        "notizie", "ultime", "attualità", "novità",
    }),
    Intent.SOCIAL: frozenset({                  # NUOVO v2
        "reddit", "social media", "forum", "discussion",
        "community", "subreddit", "trending", "viral",
        "what people are saying", "public opinion",
        "reddit discussion", "hacker news",
    }),
}
```

`classify_intent()` aggiunto SOCIAL allo `scores`:

```python
scores: dict[Intent, int] = {
    Intent.GENERAL_NEWS: 0,
    Intent.ACADEMIC: 0,
    Intent.DEEP_SCRAPE: 0,
    Intent.SOCIAL: 0,        # NUOVO
}
```

---

## 8. Wrapper script + mcp.json

### 8.1 `scripts/wrappers/pubmed-wrapper.sh`

Pattern allineato a `tavily-wrapper.sh` (acquisizione via CredentialManager):

```bash
#!/usr/bin/env bash
# PubMed MCP Wrapper — acquires NCBI_API_KEY via CredentialManager (SOPS-encrypted)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

# Ensure SOPS_AGE_KEY_FILE
if [[ -z "${SOPS_AGE_KEY_FILE:-}" ]]; then
  if [[ -f "$HOME/.config/sops/age/keys.txt" ]]; then
    export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
  fi
fi

# Strip placeholder ${VAR} literal
if [[ "${NCBI_API_KEY:-}" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
  unset NCBI_API_KEY
fi

# Acquire via CredentialManager (single key, no rotation needed)
if [[ -z "${NCBI_API_KEY:-}" ]] && [[ -x "$PYTHON_BIN" ]]; then
  ACQUIRED_KEY="$($PYTHON_BIN - <<'PY' || true
import asyncio
from aria.config import get_config
from aria.credentials.manager import CredentialManager

async def main() -> str:
    cm = CredentialManager(get_config())
    await asyncio.sleep(0.2)
    key = await cm.acquire("pubmed")
    return key.key.get_secret_value() if key else ""

print(asyncio.run(main()))
PY
)"
  if [[ -n "$ACQUIRED_KEY" ]]; then
    export NCBI_API_KEY="$ACQUIRED_KEY"
  else
    echo "WARN: NCBI_API_KEY missing; rate limit will be 3 req/s" >&2
  fi
fi

export NCBI_ADMIN_EMAIL="${NCBI_ADMIN_EMAIL:-fulviold@gmail.com}"
export UNPAYWALL_EMAIL="${UNPAYWALL_EMAIL:-$NCBI_ADMIN_EMAIL}"
export MCP_TRANSPORT_TYPE="${MCP_TRANSPORT_TYPE:-stdio}"
export MCP_LOG_LEVEL="${MCP_LOG_LEVEL:-info}"

exec npx -y @cyanheads/pubmed-mcp-server@latest
```

### 8.2 `scripts/wrappers/scientific-papers-wrapper.sh`

```bash
#!/usr/bin/env bash
# Scientific Papers MCP Wrapper — keyless (Europe PMC + arXiv)
set -euo pipefail
exec npx -y @futurelab-studio/latest-science-mcp@latest
```

(Npm package name verificato: `@futurelab-studio/latest-science-mcp` su npm registry, non `scientific-papers-mcp`.)

### 8.3 `scripts/wrappers/reddit-wrapper.sh` (Phase 5)

```bash
#!/usr/bin/env bash
# Reddit MCP Wrapper — OAuth credentials via CredentialManager
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

if [[ -z "${SOPS_AGE_KEY_FILE:-}" ]] && [[ -f "$HOME/.config/sops/age/keys.txt" ]]; then
  export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
fi

# Reddit OAuth: 2 valori (client_id + client_secret) salvati in api-keys.enc.yaml
# come "reddit" provider con 2 key entries id=client_id e id=client_secret.
if [[ -z "${REDDIT_CLIENT_ID:-}" || -z "${REDDIT_CLIENT_SECRET:-}" ]]; then
  CREDS="$($PYTHON_BIN - <<'PY' || true
import asyncio
from aria.config import get_config
from aria.credentials.manager import CredentialManager

async def main() -> tuple[str, str]:
    cm = CredentialManager(get_config())
    await asyncio.sleep(0.2)
    cid = await cm.acquire("reddit_client_id")
    sec = await cm.acquire("reddit_client_secret")
    cid_val = cid.key.get_secret_value() if cid else ""
    sec_val = sec.key.get_secret_value() if sec else ""
    return cid_val, sec_val

cid, sec = asyncio.run(main())
print(f"{cid}|{sec}")
PY
)"
  IFS='|' read -r REDDIT_CLIENT_ID REDDIT_CLIENT_SECRET <<<"$CREDS"
  export REDDIT_CLIENT_ID REDDIT_CLIENT_SECRET
fi

if [[ -z "${REDDIT_CLIENT_ID:-}" || -z "${REDDIT_CLIENT_SECRET:-}" ]]; then
  echo "ERROR: Reddit OAuth creds missing — refusing to start MCP" >&2
  exit 1
fi

exec npx reddit-mcp-server
```

### 8.4 `.aria/kilocode/mcp.json` — entries v2

```json
"pubmed-mcp": {
  "command": "/home/fulvio/coding/aria/scripts/wrappers/pubmed-wrapper.sh",
  "disabled": false,
  "env": {
    "NCBI_API_KEY": "${NCBI_API_KEY}",
    "NCBI_ADMIN_EMAIL": "${NCBI_ADMIN_EMAIL}",
    "UNPAYWALL_EMAIL": "${UNPAYWALL_EMAIL}",
    "SOPS_AGE_KEY_FILE": "/home/fulvio/.config/sops/age/keys.txt",
    "ARIA_HOME": "/home/fulvio/coding/aria",
    "MCP_TRANSPORT_TYPE": "stdio"
  }
},
"scientific-papers-mcp": {
  "command": "/home/fulvio/coding/aria/scripts/wrappers/scientific-papers-wrapper.sh",
  "disabled": false
},
"reddit-mcp": {
  "command": "/home/fulvio/coding/aria/scripts/wrappers/reddit-wrapper.sh",
  "disabled": true,
  "_comment": "Enabled when OAuth setup completed (Phase 5 HITL gate)",
  "env": {
    "SOPS_AGE_KEY_FILE": "/home/fulvio/.config/sops/age/keys.txt",
    "ARIA_HOME": "/home/fulvio/coding/aria"
  }
}
```

(arxiv-mcp-server entry aggiunta solo in Phase 7 conditional.)

---

## 9. Credenziali — pattern allineato ARIA

### 9.1 `api-keys.enc.yaml` — entries v2

Visualizzato decriptato:

```yaml
providers:
  # ... existing entries (tavily, brave, exa, ...) ...
  pubmed:
    - id: ncbi-primary
      key: <NCBI_API_KEY_value>
      owner: fulvio
      credits_total: null     # nessun limite, solo rate limit
  reddit_client_id:
    - id: reddit-app
      key: <client_id_value>
      owner: fulvio
  reddit_client_secret:
    - id: reddit-app
      key: <client_secret_value>
      owner: fulvio
```

### 9.2 `.env.example` — nuove variabili (placeholder)

```bash
# === PubMed / NCBI (ottenere chiave gratuita) ===
# https://www.ncbi.nlm.nih.gov/account/settings/
# NCBI_API_KEY=  # opzionale, raccomandata (10 req/s vs 3)
# NCBI_ADMIN_EMAIL=fulviold@gmail.com
# UNPAYWALL_EMAIL=fulviold@gmail.com

# === Reddit OAuth (Phase 5, HITL gate) ===
# https://www.reddit.com/prefs/apps  (type: script)
# REDDIT_CLIENT_ID=
# REDDIT_CLIENT_SECRET=
```

### 9.3 Operatività registrazione chiavi

```bash
# PubMed
python -m aria.credentials add --provider pubmed --id ncbi-primary --key <KEY>

# Reddit (dopo registrazione app)
python -m aria.credentials add --provider reddit_client_id --id reddit-app --key <CID>
python -m aria.credentials add --provider reddit_client_secret --id reddit-app --key <SEC>
```

(Verificare il comando esatto del CLI `aria.credentials` in fase di setup; pattern equivalente a quanto fatto per Tavily.)

---

## 10. ADR obbligatorio (P10)

**File**: `docs/foundation/decisions/ADR-0006-research-agent-academic-social-expansion.md`

**Contenuto minimo**:

```markdown
# ADR-0006 — Research Agent Academic + Social Provider Expansion

Status: Accepted
Date: 2026-04-27
Supersedes: —
Related: ADR-0001 (dependency baseline)

## Context

Blueprint §11.1 elenca 6 provider MVP (Tavily, Firecrawl, Brave, Exa, SearXNG, SerpAPI)
e §11.2 definisce 3 intent (general/news, academic, deep_scrape).
Firecrawl rimosso 2026-04-27 (esaurimento). Necessità operativa di:
- Provider accademici dedicati (PubMed, Europe PMC, arXiv)
- Provider social (Reddit) per intent SOCIAL

## Decision

1. Aggiungere 3 MCP server: `cyanheads/pubmed-mcp-server`,
   `benedict2310/scientific-papers-mcp` (Europe PMC + arXiv search),
   `jordanburke/reddit-mcp-server` (OAuth obbligatorio).
2. Introdurre `Intent.SOCIAL` con tier ladder: REDDIT > SEARXNG > TAVILY > BRAVE.
3. Riordinare `Intent.ACADEMIC`: SEARXNG > PUBMED > SCIENTIFIC_PAPERS > TAVILY > EXA > BRAVE > FETCH.
4. Mantenere pattern wrapper + CredentialManager + SOPS per tutte le chiavi.

## Consequences

- Blueprint §11.1 e §11.2 divergenti dal codice (registrato qui per P10).
- 3 nuovi MCP in mcp.json (~150 MB RAM stimati).
- Reddit gated su HITL OAuth setup; fallback SearXNG sufficiente.
- arXiv standalone (`blazickjp`) opzionale Phase 2 solo se serve PDF read.
```

**Gate**: senza questo ADR mergeato in `docs/foundation/decisions/`, la Fase 3 (router code) NON parte.

---

## 11. Strategy di Test

### 11.1 Nuovi test

| File | Cosa testa |
|------|------------|
| `tests/unit/agents/search/test_provider_pubmed.py` | enum, tier ACADEMIC, _refresh_health |
| `tests/unit/agents/search/test_provider_scientific_papers.py` | enum, keyless detection, tier ACADEMIC posizione 3 |
| `tests/unit/agents/search/test_provider_reddit.py` | enum, tier SOCIAL, condizionalità OAuth |
| `tests/unit/agents/search/test_intent_social.py` | SOCIAL keywords match, classify_intent priority |
| `tests/unit/agents/search/test_router_academic_tiers.py` | ordine tier ACADEMIC esatto |
| `tests/unit/agents/search/test_router_social_tiers.py` | ordine tier SOCIAL, fallback con Reddit DOWN |

### 11.2 Test pre-esistenti da bonificare (vedi §12)

### 11.3 Comandi

```bash
# baseline
pytest tests/unit/agents/search/ -q

# nuovo
pytest tests/unit/agents/search/test_provider_pubmed.py -q
pytest tests/unit/agents/search/test_router_academic_tiers.py -q
pytest tests/unit/agents/search/test_router_social_tiers.py -q

# full quality gate
make quality
```

---

## 12. Pre-existing issues confermate

Audit ha verificato 18 occorrenze di `FIRECRAWL` in test code (non più nel codice prod):

| File | Riga | Match |
|------|------|-------|
| `tests/unit/agents/search/conftest.py` | 34 | `Provider.FIRECRAWL_EXTRACT` |
| `tests/unit/agents/search/conftest.py` | 44 | `Provider.FIRECRAWL_EXTRACT` |
| `tests/unit/agents/search/conftest.py` | 45 | `Provider.FIRECRAWL_SCRAPE` |
| `tests/unit/agents/search/test_router.py` | 23 | `Provider.FIRECRAWL_EXTRACT.value` |
| `tests/unit/agents/search/test_router.py` | 24 | `Provider.FIRECRAWL_SCRAPE.value` |
| `tests/unit/agents/search/test_router_integration.py` | 88,101-103,116,188-211 | 13 occorrenze |

**Fix richiesto Fase 1**: rimuovere/sostituire tutte 18 occorrenze. Senza questa pulizia, `pytest` fallisce con `AttributeError: type object 'Provider' has no attribute 'FIRECRAWL_EXTRACT'`.

---

## 13. Piano di rollout

### Fase 0 — ADR (30 min, P0 BLOCKING)
- [ ] Redigere `ADR-0006-research-agent-academic-social-expansion.md`
- [ ] HITL approvazione utente
- [ ] Commit: `docs(adr): ADR-0006 academic+social research expansion`

### Fase 1 — Test bonifica (30 min, P0)
- [ ] Aggiornare `conftest.py`, `test_router.py`, `test_router_integration.py`
- [ ] Verificare `pytest tests/unit/agents/search/ -q` baseline pulito
- [ ] Commit: `test(search): remove stale FIRECRAWL provider references`

### Fase 2 — PubMed + Scientific Papers MCP (1.5h, P0)
- [ ] HITL: registrare NCBI API key
- [ ] Aggiungere `pubmed` in `api-keys.enc.yaml` (SOPS edit)
- [ ] Creare `scripts/wrappers/pubmed-wrapper.sh`
- [ ] Creare `scripts/wrappers/scientific-papers-wrapper.sh`
- [ ] Aggiungere `pubmed-mcp` + `scientific-papers-mcp` in `mcp.json`
- [ ] Aggiornare `.env.example`
- [ ] Verifica startup MCP via `/mcps` nel REPL Kilo
- [ ] Commit: `feat(search): add PubMed and Scientific Papers MCP servers`

### Fase 3 — Router (45 min, P0, blocked by F0)
- [ ] `Provider` enum: PUBMED, SCIENTIFIC_PAPERS, REDDIT, ARXIV (opzionale)
- [ ] `Intent` enum: SOCIAL
- [ ] `INTENT_TIERS` ridisegnato
- [ ] `KEYLESS_PROVIDERS` frozenset
- [ ] `_refresh_health` esteso
- [ ] Commit: `feat(router): expand intent ladder with academic+social providers`

### Fase 4 — Intent classifier (30 min, P0)
- [ ] `INTENT_KEYWORDS` esteso (ACADEMIC + SOCIAL)
- [ ] `classify_intent()` includes SOCIAL score
- [ ] Commit: `feat(intent): add SOCIAL intent + new academic keywords`

### Fase 5 — Reddit MCP (HITL gate, 1h, P1)
- [ ] HITL: registrare Reddit app https://www.reddit.com/prefs/apps
- [ ] Salvare credenziali in `api-keys.enc.yaml`
- [ ] Creare `scripts/wrappers/reddit-wrapper.sh`
- [ ] Aggiungere `reddit-mcp` in `mcp.json` (`disabled: false` solo dopo HITL)
- [ ] Verifica startup
- [ ] Commit: `feat(search): add Reddit MCP server (OAuth)`

### Fase 6 — Test (1.5h, P0)
- [ ] 6 nuovi test files
- [ ] `make quality` passa green
- [ ] Commit: `test(search): cover new academic+social providers and SOCIAL intent`

### Fase 7 — arXiv standalone PDF (opzionale, 1h, P2)
- [ ] CONDIZIONE: solo se serve `download_paper`/`read_paper`
- [ ] `uv tool install 'arxiv-mcp-server[pdf]'`
- [ ] Wrapper + mcp.json entry
- [ ] Commit: `feat(search): add blazickjp/arxiv-mcp-server for PDF pipeline`

### Fase 8 — Wiki + ADR finale (45 min, P0)
- [ ] Aggiornare `docs/llm_wiki/wiki/research-routing.md` (nuovo tier matrix)
- [ ] Aggiornare `docs/llm_wiki/wiki/index.md` (`Last Updated`, raw sources table)
- [ ] Append timestamped entry in `docs/llm_wiki/wiki/log.md`
- [ ] Commit: `docs(wiki): document v2 research expansion (PubMed, Scientific Papers, Reddit)`

---

## 14. Wiki maintenance (CLAUDE.md mandate)

Per CLAUDE.md "Wiki Maintenance (continuous)" + "Every wiki fact must record `source` + `last_updated`":

### 14.1 `docs/llm_wiki/wiki/index.md`

- Aggiornare header: `Last Updated: 2026-04-27T<HH:MM> (v2 plan applied)`.
- Raw Sources Table: aggiungere righe:
  - `docs/plans/research_academic_reddit_2.md` | Piano v2 audit-corrected | 2026-04-27
  - `docs/foundation/decisions/ADR-0006-research-agent-academic-social-expansion.md` | ADR divergence §11 | 2026-04-27
- Pages table: aggiornare riga `research-routing` con stato post-v2.

### 14.2 `docs/llm_wiki/wiki/research-routing.md`

- Sezione "Provider Tier Matrix": aggiornare con tier matrix v2.
- "Planned Expansion (2026-04-27)" → "Active Expansion v2 (2026-04-27)".
- Context7 Verified Sources table: aggiungere `scientific-papers-mcp` riga.

### 14.3 `docs/llm_wiki/wiki/log.md`

Append:

```markdown
## 2026-04-27T<HH:MM> — Plan v2 audit-corrected drafted

**Operazione**: AUDIT + REPLAN — Plan v1 (research_academic_reddit_1.md) sottoposto a audit severo.
**Findings critici**:
- Europe PMC native provider violava P8 (tool ladder) → switch a scientific-papers-mcp
- Reddit "anonymous mode" claim non verificato Context7 → OAuth obbligatorio
- ADR-0006 mancante (P10 violato) → richiesto pre-merge
- arXiv [pdf] extra omesso
- Credential pattern bypassato (raw env var) → switch a SOPS+CredentialManager

**Output**: `docs/plans/research_academic_reddit_2.md` v2.
```

---

## 15. Rischi e mitigazioni

| Rischio | Prob | Impatto | Mitigazione v2 |
|---------|------|---------|----------------|
| Reddit MCP fallisce startup senza OAuth | Alta | Alto | Wrapper exit 1 su key mancanti; mcp.json `disabled: true` finché HITL non chiude |
| PubMed senza NCBI key | Bassa | Basso | Wrapper emette WARN, server funziona a 3 req/s |
| `scientific-papers-mcp` package name diverso da quanto assunto | Media | Basso | Verifica `npm view scientific-papers-mcp` in fase 2 setup; fallback bunx/uvx → **RISOLTO**: npm name è `@futurelab-studio/latest-science-mcp` |
| ADR non approvato | Bassa | Critico | Gate Fase 0 BLOCKING; nessun codice merge senza approvazione |
| RAM aggiuntiva 3 MCP | Bassa | Basso | Stima ~150 MB; accettabile su workstation MVP |
| Reddit RBP blocco accesso | Media | Alto | Fallback SearXNG `reddit` engine in tier 2 SOCIAL |
| `scientific-papers-mcp` rate limit Europe PMC (10 req/min) | Media | Medio | Cache 6h già attiva (blueprint §11.5) |
| Dipendenza `benedict2310` non manutenuta | Bassa | Medio | License MIT + 5319 snippet Context7 = adoption alta; fork ARIA se necessario |

---

## 16. Quality gates

| Gate | Comando | Criterio |
|------|---------|----------|
| Lint | `make lint` (= `ruff check src/`) | 0 errori |
| Format | `ruff format --check src/` | 0 differenze |
| Type check | `make typecheck` (= `mypy src`) | 0 errori |
| Unit tests | `pytest tests/unit/agents/search/ -q` | tutti passano |
| Full suite | `make quality` | green |
| MCP health | `/mcps` REPL Kilo | pubmed-mcp + scientific-papers-mcp connected; reddit-mcp condizionale |
| Wiki sync | manuale: index.md + log.md + research-routing.md | 3 file aggiornati con timestamp |
| ADR | `ls docs/foundation/decisions/ADR-0006*` | file esiste |

---

## 17. Stima effort

| Fase | Effort | Dipendenze |
|------|--------|------------|
| F0 ADR | 30 min | HITL approval |
| F1 test bonifica | 30 min | — |
| F2 PubMed + Scientific Papers MCP | 1.5h | NCBI key (HITL) |
| F3 Router | 45 min | F0 mergeato |
| F4 Intent | 30 min | F3 |
| F5 Reddit OAuth | 1h | HITL Reddit app |
| F6 Test nuovi | 1.5h | F3+F4 |
| F7 arXiv PDF (opzionale) | 1h | bisogno reale di PDF read |
| F8 Wiki + index/log | 45 min | F3-F6 completati |
| **Totale P0** | **~5.5h** | (F7 escluso) |
| **Totale con F7** | **~6.5h** | |

Riduzione vs v1 (~6h): comparabile. Risparmio su Europe PMC native (1h) + arxiv standalone (30min) compensato da ADR (30min) + wrapper Python pubmed/reddit più completi.

---

## 18. Appendici

### A. Context7 verification log v2

| Provider | Context7 ID | Snippets | Benchmark | Verificato | Note v2 |
|----------|-------------|----------|-----------|-----------|---------|
| PubMed | `/cyanheads/pubmed-mcp-server` | 1053 | 83.7 | 2026-04-27 | npx + 9 tool + UNPAYWALL_EMAIL confermato |
| Scientific Papers | `/benedict2310/scientific-papers-mcp` | 5319 | 67.0 | 2026-04-27 | `search_papers(source=europepmc)` confermato; 6 sorgenti; npm: `@futurelab-studio/latest-science-mcp` |
| arXiv standalone | `/blazickjp/arxiv-mcp-server` | 112 | 76.1 | 2026-04-27 | `[pdf]` extra confermato |
| Reddit | `/jordanburke/reddit-mcp-server` | 39 | — | 2026-04-27 | OAuth env vars **obbligatori** confermato; no anonymous mode in docs |

### B. Decisioni architetturali v2

| Decisione | Motivazione |
|-----------|-------------|
| Europe PMC via `scientific-papers-mcp` (no native) | P8 Tool Ladder MCP > Python; MCP esistente verified Context7 |
| Reddit OAuth required | Context7 docs non validano modalità anonima; sicurezza > convenienza |
| ADR-0006 BLOCKING gate | P10 Self-Documenting Evolution; blueprint §11 divergence |
| `scientific-papers-mcp` per arXiv search | Consolidamento (1 MCP vs 2); arxiv-mcp-server solo per PDF pipeline |
| Pattern CredentialManager per NCBI key | Coerenza con tavily/brave/exa wrappers; P4 privacy |
| `Intent.SOCIAL` separato da `GENERAL_NEWS` | Tier dedicato Reddit > SearXNG > Tavily; semantica chiara |

### C. Riferimenti

| Risorsa | URL |
|---------|-----|
| Plan v1 (superseded) | `docs/plans/research_academic_reddit_1.md` |
| Analisi origine | `docs/analysis/research_agent_enhancement.md` |
| Blueprint §11 | `docs/foundation/aria_foundation_blueprint.md` |
| Wiki research-routing | `docs/llm_wiki/wiki/research-routing.md` |
| ADR-0006 (da creare) | `docs/foundation/decisions/ADR-0006-research-agent-academic-social-expansion.md` |
| PubMed MCP Context7 | https://context7.com/cyanheads/pubmed-mcp-server/llms.txt |
| Scientific Papers Context7 | https://context7.com/benedict2310/scientific-papers-mcp/llms.txt |
| arXiv MCP Context7 | https://context7.com/blazickjp/arxiv-mcp-server/llms.txt |
| Reddit MCP Context7 | https://context7.com/jordanburke/reddit-mcp-server/llms.txt |
| NCBI API Key | https://www.ncbi.nlm.nih.gov/account/settings/ |
| Reddit App Registration | https://www.reddit.com/prefs/apps |
| Europe PMC API | https://europepmc.org/RestfulWebService |

---

> **Fine piano v2.** Documento autoritativo per l'implementazione (sostituisce v1).
> Approvazione HITL Milestone (Technical Design + ADR-0006) richiesta prima di Fase 3.
