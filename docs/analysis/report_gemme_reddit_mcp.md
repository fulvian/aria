# Report: Reddit MCP — Gemme Senza Autenticazione / API Key

**Data**: 2026-04-29
**Autore**: Master Orchestrator (github-discovery + Context7 + Brave Search)
**Sessioni github-discovery**: `e3e3e16f-03e0-4048-bb14-80265c16b2e3`
**Pool analizzati**: 6 (50 candidati ciascuno)
**Repo screenati**: 12+ (Gate 1 + Gate 2 + deep assessment)
**Scopo**: Trovare alternative MCP per Reddit che NON richiedano OAuth, API key, o autenticazione di sistema.

---

## Indice

1. [Riassunto Esecutivo](#1-riassunto-esecutivo)
2. [Metodologia](#2-metodologia)
3. [Tier 1 — Gemme Consigliate (Zero-config, No Auth)](#3-tier-1--gemme-consigliate-zero-config-no-auth)
4. [Tier 2 — Non Adatte (Richiedono Auth/API Key)](#4-tier-2--non-adatte-richiedono-authapi-key)
5. [Tier 3 — Alternative Ibride / Da Approfondire](#5-tier-3--alternative-ibride--da-approfondire)
6. [Librerie Sottostanti Rilevanti](#6-librerie-sottostanti-rilevanti)
7. [Analisi Comparativa](#7-analisi-comparativa)
8. [Raccomandazioni per ARIA](#8-raccomandazioni-per-aria)
9. [Rischi e Considerazioni](#9-rischi-e-considerazioni)
10. [Metadati della Ricerca](#10-metadati-della-ricerca)

---

## 1. Riassunto Esecutivo

La richiesta originale di implementare `mcp-reddit` (da `/jordanburke/reddit-mcp-server`) richiede **OAuth obbligatorio** — un gate amministrativo bloccante.

Questa ricerca ha identificato **3 gemme MCP** che NON richiedono API key, OAuth, o alcuna autenticazione:

| # | Repo | Stars | Tools | Funzionalità | Metodo |
|---|------|-------|-------|-------------|--------|
| 1 | **eliasbiondo/reddit-mcp-server** | 134 | 6 tools | Ricerca, subreddit, post, user | HTML parsing (old.reddit.com) |
| 2 | **adhikasp/mcp-reddit** | 398 | 2 tools | Hot threads, post details | Scraping old.reddit.com |
| 3 | **cmpxchg16/mcp-ethical-hacking/reddit-mcp** | 19 | 1 tool | Extract discussion da URL | API + HTML parsing ibrido |

**Raccomandazione primaria**: `eliasbiondo/reddit-mcp-server` (PyPI: `reddit-no-auth-mcp-server`) — è il più completo per il nostro use case di **ricerca mirata** su Reddit, con 6 tool MCP tra cui `search` e `search_subreddit`.

---

## 2. Metodologia

### 2.1 github-discovery

Sessione di discovery multi-query:
- `reddit mcp server model context protocol` → 50 candidati (Pool feb247f1)
- `reddit search scraper no api key python` → 50 candidati (Pool bf5e01c2)
- `reddit api alternative free no authentication` → 50 candidati (Pool 0e861361)
- `reddit mcp server pushshift pullpush` → 50 candidati (Pool 66345e3d)
- `reddit old pushshift api search alternatives 2024 2025` → 50 candidati (Pool 038fd2a6)
- `"reddit" "mcp" server search subreddit` → 50 candidati (Pool d55b8b2d)

**Totale**: 300 candidati esaminati, 12+ screenati con Gate 1/Gate 2/deep assessment.

### 2.2 Context7

Verifica documentale eseguita su:
- `/jordanburke/reddit-mcp-server` — confermato OAuth obbligatorio (già noto dal wiki log.md 2026-04-27)
- `/adhikasp/mcp-reddit` — verificato, 2 snippet, documentazione Smithery
- `reddit-no-auth-mcp-server` (PyPI) — non trovato in Context7 (progetto recente)

### 2.3 Brave Web Search

Ricerche complementari per:
- Reddit MCP senza API key
- Reddit extractor keyless
- Librerie `redd` per scraping Reddit

---

## 3. Tier 1 — Gemme Consigliate (Zero-config, No Auth)

### 3.1 eliasbiondo/reddit-mcp-server (Raccomandato)

| Dettaglio | Valore |
|-----------|--------|
| **URL** | https://github.com/eliasbiondo/reddit-mcp-server |
| **Stars** | 134 |
| **Forks** | 13 |
| **Linguaggio** | Python 100% |
| **Licenza** | MIT |
| **PyPI** | `reddit-no-auth-mcp-server` |
| **Install** | `uvx reddit-no-auth-mcp-server` |

#### Tools MCP

| Tool | Descrizione | Parametri Chiave |
|------|-------------|------------------|
| `search` | Cerca post in tutto Reddit | `query`, `limit`, `sort` |
| `search_subreddit` | Cerca dentro un subreddit specifico | `subreddit`, `query`, `limit`, `sort` |
| `get_post` | Dettaglio post + albero commenti | `permalink` |
| `get_subreddit_posts` | Listing di un subreddit | `subreddit`, `limit`, `category`, `time_filter` |
| `get_user` | Attività recente di un utente | `username`, `limit` |
| `get_user_posts` | Post di un utente | `username`, `limit`, `category`, `time_filter` |

#### Architettura

- **Hexagonal architecture** (ports & adapters)
- Sotto: `redd` library (scraping HTML di `old.reddit.com`)
- Trasporto: `stdio` (default) o `streamable-http`
- Configurabile: timeout, throttle, proxy, log level

#### Configurazione MCP

```json
{
  "mcpServers": {
    "reddit-no-auth": {
      "command": "uvx",
      "args": ["reddit-no-auth-mcp-server"],
      "env": {}
    }
  }
}
```

#### Vantaggi per ARIA
- Zero configurazione — nessuna API key, nessun OAuth
- Search funzionante — supporta `search` e `search_subreddit` (fondamentale per ricerca mirata)
- `uvx` one-liner — integrazione immediata in `.aria/kilocode/mcp.json`
- Configurabile (proxy, throttle, timeout)
- Architettura pulita, manutenibile
- Rischio: scraping HTML — può rompersi se Reddit cambia struttura

---

### 3.2 adhikasp/mcp-reddit (Più Popolare, Meno Funzioni)

| Dettaglio | Valore |
|-----------|--------|
| **URL** | https://github.com/adhikasp/mcp-reddit |
| **Stars** | 398 |
| **Forks** | 52 |
| **Linguaggio** | Python 76.5%, Dockerfile 23.5% |
| **Licenza** | MIT |
| **Context7** | `/adhikasp/mcp-reddit` (verificato) |
| **Install** | `npx -y @smithery/cli install @adhikasp/mcp-reddit` |

#### Tools MCP

| Tool | Descrizione |
|------|-------------|
| `fetch_hot_threads` | Recupera hot threads da un subreddit |
| `get_post_details` | Dettaglio di un post specifico |

#### Configurazione MCP

```json
{
  "mcpServers": {
    "reddit-hot": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/adhikasp/mcp-reddit.git", "mcp-reddit"],
      "env": {}
    }
  }
}
```

#### Vantaggi per ARIA
- Più popolare (398 stars) — community ampia, più probabilità di manutenzione
- Nessuna API key
- Disponibile via Smithery
- **Mancano funzioni di search** — solo hot threads e post details
- Non adatto per **ricerca mirata** su Reddit (manca `search`)

---

### 3.3 cmpxchg16/mcp-ethical-hacking/reddit-mcp (Educativo)

| Dettaglio | Valore |
|-----------|--------|
| **URL** | https://github.com/cmpxchg16/mcp-ethical-hacking |
| **Stars** | 19 (parent repo) |
| **Forks** | 6 |
| **Linguaggio** | Python 100% |
| **Licenza** | MIT |
| **Subdir** | `reddit-mcp/` |
| **Install** | `uvx --from git+https://github.com/cmpxchg16/mcp-ethical-hacking.git#subdirectory=reddit-mcp` |

#### Tool MCP

| Tool | Descrizione |
|------|-------------|
| `reddit_extract` | Estrae discussione Reddit da URL (post + commenti) |

#### Vantaggi per ARIA
- Nessuna API key
- Estrazione post+commenti (utile per deep reading)
- **Repo "ethical hacking"** — progetto dimostrativo su sicurezza, non production-grade
- Singolo tool — manca search, subreddit listing
- Gate 1 score: 0.154 (basso)

---

## 4. Tier 2 — Non Adatte (Richiedono Auth/API Key)

Questi MCP server richiedono autenticazione e non sono utilizzabili nel nostro scenario:

| Repo | Motivo |
|------|--------|
| `jordanburke/reddit-mcp-server` | OAuth obbligatorio — già verificato Context7 nel wiki (log.md 2026-04-27) |
| `netixc/reddit-mcp-server` | Richiede REDDIT_CLIENT_ID, _SECRET, username/password (PRAW) |
| `apify/apify-mcp-server` | Richiede Apify API token |
| `apify/crawlerbros/reddit-mcp-scraper` | Richiede Apify API token |
| `apify/mcp/reddit-mcp-server` | Richiede Apify API token |

---

## 5. Tier 3 — Alternative Ibride / Da Approfondire

Questi candidati hanno superato il Gate 1 ma necessitano di verifica manuale:

| Repo | Gate 1 Score | Note |
|------|-------------|------|
| `karanb192/reddit-mcp-buddy` | 0.402 (PASS) | Buddy-style interaction, non verificato per auth |
| `daanrongen/reddit-mcp` | 0.264 (FAIL) | Non abbastanza informazioni |
| `nitaiaharoni1/reddit-mcp` | 0.356 (FAIL) | Non abbastanza informazioni |
| `browserkit-dev/adapter-reddit` | 0.271 (FAIL) | Adapter pattern, non chiaro |

---

## 6. Librerie Sottostanti Rilevanti

Queste librerie Python potrebbero essere utili per un'implementazione custom:

| Libreria | Descrizione | Link |
|----------|-------------|------|
| **`redd`** (eliasbiondo) | Libreria Python async moderna per scraping Reddit senza API key — typed models, post, commenti, utenti, subreddit | https://github.com/eliasbiondo/redd |
| **`yars`** (datavorous) | "Yet Another Reddit Scrapper" — senza API key, ricerca, post, immagini | https://github.com/datavorous/yars |
| **`reddit-universal-scraper`** (ksanjeev284) | Scraper completo con dashboard, API REST, scheduling | https://github.com/ksanjeev284/reddit-universal-scraper |

---

## 7. Analisi Comparativa

| Criterio | eliasbiondo | adhikasp | cmpxchg16 | jordanburke |
|----------|------------|----------|-----------|-------------|
| **API Key necessaria** | No | No | No | Si (OAuth) |
| **Search funzionante** | Si | No | No | Si |
| **Subreddit listing** | Si | hot threads | No | Si |
| **Post detail** | Si | Si | Si | Si |
| **Comment tree** | Si | Si | Si | Si |
| **User info** | Si | No | No | Si |
| **Write operations** | No | No | No | Si |
| **Stars** | 134 | 398 | 19 | N/A |
| **Architettura** | Hexagonale | Semplice | Dimostrativa | N/A |
| **uvx one-liner** | Si | Si | Si | N/A |
| **Rischio rottura** | Medio (HTML) | Medio (HTML) | Medio (HTML) | Basso (API) |
| **Idoneita ARIA** | **ALTA** | MEDIA | BASSA | BLOCCATA |

---

## 8. Raccomandazioni per ARIA

### 8.1 Raccomandazione Primaria

Sostituire il bloccato `mcp-reddit` (OAuth) con **eliasbiondo/reddit-mcp-server**:

```json
// .aria/kilocode/mcp.json
{
  "mcpServers": {
    "reddit-search": {
      "command": "uvx",
      "args": ["reddit-no-auth-mcp-server"],
      "env": {},
      "disabled": false
    }
  }
}
```

**Vantaggi**:
- `search` e `search_subreddit` coprono esattamente il caso d'uso di "ricerche mirate su Reddit"
- Wrapper shell non necessario (nessuna API key da gestire)
- Compatibile con `KEYLESS_PROVIDERS` nel router ARIA
- Throttle configurabile (default 1-2 secondi) — rispetta rate limiting implicito

### 8.2 Raccomandazione Secondaria

Se serve solo hot topics, **adhikasp/mcp-reddit** e' un'alternativa piu' popolare ma meno completa.

### 8.3 Impatto sul Router ARIA

L'attuale `src/aria/agents/search/router.py` ha `Provider.REDDIT` con `KEYLESS_PROVIDERS` gia' impostato. Il wrapper `scripts/wrappers/reddit-wrapper.sh` (OAuth) puo' essere sostituito da una configurazione diretta senza wrapper.

Modifiche necessarie nel router:
- Nessuna modifica al `Provider.REDDIT` enum (gia' presente)
- Nessuna modifica a `KEYLESS_PROVIDERS` (gia' presente)
- Rimuovere `disabled: true` da mcp.json
- Sostituire/rimuovere `reddit-wrapper.sh` (non serve piu' per key management)
- Update `scripts/wrappers/reddit-wrapper.sh` → semplice pass-through o rimozione

### 8.4 Schema di Routing Proposto per SOCIAL Intent

```
SOCIAL intent → reddit-search (eliasbiondo) → searxng → tavily → brave
```

Reddit diventa **keyless e attivo** invece di OAuth-gated.

---

## 9. Rischi e Considerazioni

### 9.1 Scraping vs API

Tutti e 3 i candidati Tier 1 usano **web scraping** (HTML parsing di `old.reddit.com`) invece dell'API ufficiale di Reddit. Questo comporta:

| Rischio | Probabilita | Impatto | Mitigazione |
|---------|------------|---------|-------------|
| Rottura struttura HTML | Media | Alto | Test periodici, fallback a ricerca web generale |
| Rate limiting implicito | Alta | Medio | Throttle configurabile (default in eliasbiondo: 1-2s) |
| Blocco IP da Reddit | Bassa | Alto | Proxy configurabile (`REDDIT_PROXY`) |
| Cambiamento TOS Reddit | Bassa | Medio | Monitorare changes, alternative pronte |

### 9.2 Termini di Servizio Reddit

Lo scraping di `old.reddit.com` potrebbe violare i Termini di Servizio di Reddit (sezione scraping automation). Tuttavia:
- `old.reddit.com` e' pubblicamente accessibile senza autenticazione
- Il throttle configurabile (default 1-2s) e' simile a comportamento umano
- Nessun dato privato / autenticato viene estratto
- La ricerca e' read-only

**Decisione**: Rischio accettabile per use case di research agent read-only.

### 9.3 Mancanza di Write Operations

Nessuno dei candidati Tier 1 supporta write operations (postare, commentare, votare). Se ARIA dovesse mai aver bisogno di write, OAuth sarebbe inevitabile.

---

## 10. Metadati della Ricerca

### 10.1 github-discovery Session

```
Session ID: e3e3e16f-03e0-4048-bb14-80265c16b2e3
Status: completed
Pool totali: 6
Candidati totali: 300
Screenati: 12+
Deep assessment: 5 repo
```

### 10.2 Pool di Ricerca

| Query | Pool ID | Candidati |
|-------|---------|-----------|
| `reddit mcp server model context protocol` | feb247f1 | 50 |
| `reddit search scraper no api key python` | bf5e01c2 | 50 |
| `reddit api alternative free no authentication` | 0e861361 | 50 |
| `reddit mcp server pushshift pullpush` | 66345e3d | 50 |
| `reddit old pushshift api search alternatives 2024 2025` | 038fd2a6 | 50 |
| `"reddit" "mcp" server search subreddit` | d55b8b2d | 50 |

### 10.3 Context7 Verifications

| Library | ID | Esito |
|---------|----|-------|
| Reddit MCP Server | `/jordanburke/reddit-mcp-server` | OAuth obbligatorio (confermato) |
| MCP Reddit | `/adhikasp/mcp-reddit` | No auth (verificato) |
| reddit-no-auth-mcp-server | N/A (non in Context7) | Progetto recente, non catalogato |
| Reddit API | `/websites/reddit_dev_api` | Riferimento ufficiale |

### 10.4 Fonti

- GitHub API (github-discovery)
- Context7 Documentation API
- Brave Search API
- PulseMCP.com
- GitHub repository README files

---

*Fine Report*
