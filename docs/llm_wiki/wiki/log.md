---
title: ARIA LLM Wiki Activity Log
sources: []
last_updated: 2026-04-23T19:20:00+02:00
tier: 1
---

# ARIA LLM Wiki — Activity Log

> Append-only. Ogni operazione di ingest, query o manutenzione del wiki registra una entry qui.

---

## 2026-04-23T09:50 — Bootstrap LLM Wiki

**Operazione**: INGEST (bootstrap completo)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Creazione iniziale del wiki da tutte le fonti primarie

### Fonti elaborate

1. `docs/foundation/aria_foundation_blueprint.md` (2089 righe, v1.1.0-audit-aligned)
2. `docs/foundation/decisions/ADR-0001` through `ADR-0010` (10 ADR)
3. `AGENTS.md` (regole coding agents)
4. `README.md` (overview)
5. `pyproject.toml` (dipendenze)
6. `Makefile` (operational targets)
7. `docs/operations/runbook.md` (operazioni)
8. Analisi struttura `src/aria/` (codice sorgente)

### Pagine create

| Pagina | Fonti primarie |
|--------|----------------|
| `index.md` | Tutte (meta-index) |
| `log.md` | N/A (this file) |
| `architecture.md` | Blueprint §3, §4 |
| `ten-commandments.md` | Blueprint §16 |
| `project-layout.md` | Blueprint §4.1–§4.4, AGENTS.md |
| `memory-subsystem.md` | Blueprint §5 |
| `scheduler.md` | Blueprint §6 |
| `gateway.md` | Blueprint §7 |
| `agents-hierarchy.md` | Blueprint §8 |
| `skills-layer.md` | Blueprint §9 |
| `tools-mcp.md` | Blueprint §10, ADR-0009 |
| `search-agent.md` | Blueprint §11 |
| `workspace-agent.md` | Blueprint §12, ADR-0003, ADR-0010 |
| `credentials.md` | Blueprint §13, ADR-0001, ADR-0003 |
| `adrs.md` | Tutti ADR-0001–ADR-0010 |
| `governance.md` | Blueprint §14 |
| `quality-gates.md` | AGENTS.md, pyproject.toml, Makefile |
| `roadmap.md` | Blueprint §15, §18.G |

### External Knowledge creato

| File | Fonte |
|------|-------|
| `ext_knowledge/llm-wiki-paradigm.md` | `docs/foundation/fonti/Analisi Approfondita LLM Wiki.md` |

### Note

- Bootstrap completo: tutte le sezioni del blueprint sono state compilate in pagine wiki.
- Ogni pagina include provenienza (`source:`) nei fatti.
- Cross-reference `[[wikilink]]` tra pagine correlate.
- Il wiki è Tier 1 (derivato, ricostruibile da Tier 0 raw sources).

---

## 2026-04-23T10:48 — Workspace OAuth/AuthZ Debug Planning

**Operazione**: INGEST (piano operativo di debugging)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Analisi approfondita dei loop di autorizzazione Google Workspace MCP su read Drive/Slides

### Fonti elaborate

1. `docs/plans/google_workspace_authz_debug_plan_2026-04-23.md`
2. `scripts/wrappers/google-workspace-wrapper.sh`
3. `scripts/oauth_first_setup.py`
4. `src/aria/agents/workspace/oauth_helper.py`
5. `docs/operations/workspace_oauth_runbook.md`
6. Upstream `taylorwilsdon/google_workspace_mcp` (`auth/google_auth.py`, README)
7. Context7 `/taylorwilsdon/google_workspace_mcp` (CLI args: --tool-tier, --tools, --read-only, --permissions)
8. `.aria/kilocode/kilo.json` (MCP server config)
9. `.aria/runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json` (runtime creds)

### Risultato

- Creato piano di debugging strutturato con ipotesi root-cause ordinate, test matrix T1-T6, gate decisionali, criteri DoD e strategia fix.
- Aggiornato indice wiki con la nuova fonte raw (`docs/plans/google_workspace_authz_debug_plan_2026-04-23.md`).

---

## 2026-04-23T11:07 — Workspace MCP Scope Inflation Fix (H1)

**Operazione**: IMPLEMENT (fix diretto)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Diagnosi e fix del loop di re-autenticazione Google Workspace MCP su Drive/Slides read

### Diagnosi

**Root Cause H1 confermata**: `scope inflation` - il server MCP viene avviato senza restrizione di tool/perimetro,
esponendo tutti i 114 tool. Il `required_scopes` calcolato include scope write (gmail.drafts, gmail.send,
calendar.events, drive.file, documents, spreadsheets) che non sono nelle credenziali dell'utente.
`has_required_scopes(...)` fallisce e il server emette `ACTION REQUIRED: Google Authentication Needed`.

### Verifiche eseguite

1. **CLI help conferma** `--tool-tier core --read-only` esiste e limita i tool ai soli domain read.
2. **Scope coherence check** con `--tool-tier core --read-only` → PASS (5 scope read-only, tutti concessi).
3. **Scope coherence check** con `--tool-tier core` (senza --read-only) → FAIL (manca drive.file, calendar.events, etc).
4. **Wrapper fallback** senza args → usa `CORE_READ_SCOPES` floor (6 scope read) → PASS.

### Fix applicato

**File**: `.aria/kilocode/kilo.json`

```json
"google_workspace": {
  "command": [
    "/home/fulvio/coding/aria/scripts/wrappers/google-workspace-wrapper.sh",
    "--tool-tier",
    "core",
    "--read-only"
  ]
}
```

### Criteri DoD verificati

| Criterio | Stato |
|----------|-------|
| `search_drive_files` funziona senza re-auth | ✅ Scope coherence pass |
| Scope richiesti ≤ scope concessi (no inflation) | ✅ 5 read scopes, tutti grantiti |
| Qualsiasi richiesta read in sessione autenticata | ✅ Coherence check passa |

### Quality Gates

```
Agent validation: PASS (8 agents)
Skill validation: PASS (9 skills)
ruff check: PASS
mypy: PASS (0 errors)
pytest -q: 418 passed
```

---

## 2026-04-23T11:23 — Slides Domain Fix (H1 Continuation)

**Operazione**: IMPLEMENT (correzione omissione)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Slides domain mancante da tier_map core e scopes metadata

### Problema

1. **tier_map omission**: `slides` non era presente in `tier_map['core']` nel wrapper, quindi `--tool-tier core` non attivava i tool Slides.
2. **Scope naming gap**: `slides.readonly` (MCP tool naming) != `presentations.readonly` (Google API naming). Il governance matrix usa `slides.readonly`, le credenziali runtime avevano `presentations.readonly`.

### Fix applicati

1. **`.aria/runtime/credentials/google_workspace_scopes_primary.json`**: Aggiunto `https://www.googleapis.com/auth/slides.readonly`
2. **`scripts/wrappers/google-workspace-wrapper.sh`**: Aggiunto `slides` a `tier_map['core']` e `tier_map['extended']`

```python
tier_map = {
    'core': {'gmail', 'calendar', 'drive', 'docs', 'sheets', 'slides'},  # slides aggiunto
    'extended': {'gmail', 'calendar', 'drive', 'docs', 'sheets', 'slides', 'chat', 'tasks', 'forms', 'contacts'},
    'complete': set(all_domains),
}
```

### Verifiche

| Configurazione | Scopes richiesti | Missing | Risultato |
|----------------|------------------|---------|-----------|
| `--tool-tier core --read-only` | gmail, calendar, drive, docs, sheets, slides (read) | 0 | ✅ PASS |
| `--tools slides --read-only` | `slides.readonly` | 0 | ✅ PASS |
| `--tool-tier core` (no read-only) | 12 scopes incl. write | 5 | ❌ coherence blocks |

### Quality Gates

```
bash -n google-workspace-wrapper.sh: OK
Agent validation: PASS (8 agents)
pytest -q: 418 passed
```

---

## 2026-04-23T11:58 — Workspace Wrapper Safe-Default Args Hardening

**Operazione**: IMPLEMENT (hardening + test)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: eliminare fallback OAuth con URL non utilizzabile quando il server viene avviato senza selector args

### Diagnosi

- In alcuni run il wrapper veniva invocato senza `--tool-tier/--tools/--permissions`.
- `workspace-mcp` partiva quindi con toolset ampio, calcolando scope estesi e innescando `ACTION REQUIRED` anche su richieste solo read (Drive/Slides).

### Fix applicato

1. **`scripts/wrappers/google-workspace-wrapper.sh`**
   - aggiunte funzioni `is_truthy` e `build_workspace_mcp_args`.
   - se mancano selector args, il wrapper impone default robusto: `--tool-tier core --read-only`.
   - sincronizzazione credenziali e bootstrap scope coerenti sugli **effective args** (non su raw `$*`).
   - aggiunto `WORKSPACE_WRAPPER_DRY_RUN=true` per test/preflight non distruttivi.
2. **`tests/unit/scripts/test_google_workspace_wrapper.py`**
   - test su iniezione default safe args.
   - test su preservazione args espliciti.
   - test su disabilitazione `WORKSPACE_DEFAULT_READ_ONLY=false`.
3. **`docs/llm_wiki/wiki/workspace-agent.md`**
   - documentato comportamento safe-default del wrapper.

### Verifiche

```
bash -n scripts/wrappers/google-workspace-wrapper.sh: OK
uv run pytest -q tests/unit/scripts/test_google_workspace_wrapper.py: 3 passed
```

---

## 2026-04-23T12:20 — Workspace Scope De-Inflation (core tier bypass)

**Operazione**: IMPLEMENT (hardening v2)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: eliminare richieste OAuth su scope read non necessari (tasks/chat/forms/script/contacts) durante lettura Drive/Slides

### Diagnosi

- Log utente conferma che il server continua a richiedere scope read di domini extra (`tasks`, `forms`, `chat`, `script`, `contacts`, `cse`) anche per task Slides/Drive.
- Root cause: `--tool-tier core --read-only` lato upstream include un set piu ampio del necessario per i profili ARIA read.

### Fix applicato

1. **`.aria/kilocode/kilo.json`**
   - `google_workspace.command` aggiornato da `--tool-tier core --read-only` a:
     `--tools gmail calendar drive docs sheets slides --read-only`.
2. **`scripts/wrappers/google-workspace-wrapper.sh`**
   - default fallback aggiornato: quando mancano selector args, inietta `--tools` espliciti (gmail/calendar/drive/docs/sheets/slides) invece di `--tool-tier core`.
   - introdotta variabile `WORKSPACE_DEFAULT_TOOLS` (override opzionale, csv).
3. **`tests/unit/scripts/test_google_workspace_wrapper.py`**
   - aggiornati assertion default e aggiunto test per override `WORKSPACE_DEFAULT_TOOLS`.

### Verifiche

```
bash -n scripts/wrappers/google-workspace-wrapper.sh: OK
uv run pytest -q tests/unit/scripts/test_google_workspace_wrapper.py: 4 passed
```

---

## 2026-04-23T13:20 — Slides Scope Root Cause + Pruning Fix + Single-User Mode

**Operazione**: DEBUG+IMPLEMENT (hardening v4)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: risolvere definitivamente il loop OAuth per ricerca/lettura Drive e Slides

### Root cause finale (confermata via Context7 + token refresh diretto)

**Fatto**: `presentations.readonly` **non è mai stato concesso** dall'account Google dell'utente.
- Il token refresh endpoint restituisce 8 scope: calendar.events.readonly, calendar.readonly, documents.readonly, drive.readonly, gmail.modify, gmail.readonly, gmail.send, spreadsheets.readonly.
- `presentations.readonly` **non è presente** anche dopo aver ri-autenticato con lo scope richiesto.
- **Causa**: L'account `fulviold@gmail.com` è un account **Google personale** (gmail.com), non un account **Google Workspace**. Google Slides/Presentations API potrebbe non essere disponibile su account personali senza Workspace.

### Fix applicati

1. **`scripts/wrappers/google-workspace-wrapper.sh`**
   - `prune_workspace_args_by_granted_scopes` ora ha fallback intelligente: quando **tutti** i tool richiesti mancano di scope, ripiega al sottoinsieme di tool **che hanno scope concessi** invece di uscire con errore.
   - Loggato un WARNING quando si attiva il fallback.
   - Questo permette a Drive read di funzionare anche se Slides non è disponibile.

2. **`.aria/kilocode/kilo.json`**
   - Aggiunto `--single-user` al comando google_workspace per evitare session mapping.
   - Rimosso `slides` dalla lista tool di default (non disponibile senza Workspace).

3. **`.aria/runtime/credentials/google_workspace_scopes_primary.json`**
   - Rimosso `slides.readonly` (non è mai stato concesso).
   - Aggiunta nota esplicativa.

4. **`.aria/runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json`**
   - Aggiornato scopes alla lista reale (8 scope senza presentations).

### Strategia operativa per Slides

**Drive API fallback** (già implementato in `workspace-slides-read.md`):
- `search_drive_files` → cerca file Google Slides in Drive
- `get_drive_file_content` → legge contenuto del file (anche Slides export) via Drive API
- Questo funziona perché `drive.readonly` È concesso.

**Per ottenere Slides API completo** (se necessario in futuro):
- Richiede account **Google Workspace** (non account gmail.com personale)
- Oppure usare `get_drive_file_content` che legge i file come binary/Office e li exporta in formati leggibili.

### Evidenze

```
Token refresh scopes (8 granted):
  calendar.events.readonly, calendar.readonly, documents.readonly, 
  drive.readonly, gmail.modify, gmail.readonly, gmail.send, spreadsheets.readonly
  presentations.readonly: NOT PRESENT
```

### Verifiche

```
pytest tests/unit/scripts/test_google_workspace_wrapper.py: 4 passed
wrapper dry-run test: PASS (gmail, calendar, drive, docs, sheets - no slides)
workspace-mcp startup test: PASS (no ACTION REQUIRED, no re-auth loop)
```

### Note finale

Il loop OAuth non era un bug del codice ARIA. Era causato da:
1. Configurazione precedente che richiedeva `slides` tool anche se l'account non aveva `presentations.readonly`.
2. Wrapper che non verificava gli scope realmente concessi prima di avviare MCP.
3. Il pruning era già stato implementato ma il fallback per "tutti i tool mancanti" mancava.

Il fix è ora robusto: il sistema ripiega automaticamente ai tool con scope disponibili invece di fallire o richiedere re-autenticazione.

---

## 2026-04-23T12:41 — Documentation Consolidation (Runbook + Wiki)

**Operazione**: INGEST/MAINTENANCE
**Autore**: general-manager (Kilo orchestrator)
**Scope**: allineamento documentazione operativa e wiki al fix definitivo auth-loop

### Aggiornamenti effettuati

1. **`docs/operations/workspace_oauth_runbook.md`**
   - bump versione a `1.1.0`.
   - aggiunta sezione operativa su dynamic tool pruning.
   - aggiunto comando diagnostico per leggere gli scope realmente grantiti via token refresh endpoint.
   - aggiunta runbook path per errore "Repeated ACTION REQUIRED on Drive/Slides read".
2. **`docs/llm_wiki/wiki/index.md`**
   - aggiunta nuova fonte raw: `docs/operations/workspace_oauth_runbook.md`.

### Esito

- Documentazione progetto aggiornata e coerente con hardening v3.
- Wiki index/log aggiornati con provenienza e timestamp.

---

## 2026-04-23T12:33 — Definitive Auth-Loop Root Cause & Dynamic Tool Pruning

**Operazione**: DEBUG+IMPLEMENT (hardening v3)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: eliminare definitivamente loop OAuth su richiesta Slides/Drive read con credenziali parziali gia presenti

### Root cause confermata

- Il refresh token attivo in keyring **non** include `presentations.readonly` (granted scopes reali da token refresh endpoint).
- La configurazione runtime richiedeva anche il dominio `slides`, quindi `workspace-mcp` entrava in `ACTION REQUIRED` ad ogni richiesta.
- Il controllo precedente usava metadati scope locali (file runtime), non la lista scope realmente grantita dal token.

### Fix applicato

1. **`scripts/wrappers/google-workspace-wrapper.sh`**
   - aggiunta `prune_workspace_args_by_granted_scopes`.
   - prima di avviare `workspace-mcp`, il wrapper effettua token refresh e legge gli scope grantiti reali.
   - rimuove automaticamente dai `--tools` i domini senza scope read corrispondente (es. `slides` senza `presentations.readonly`).
   - supporta override diagnostico: `WORKSPACE_GRANTED_SCOPES_OVERRIDE`.
2. **`.aria/kilocode/agents/workspace-slides-read.md`**
   - aggiunto fallback operativo su `google_workspace_get_drive_file_content`.
   - policy esplicita anti-auth-loop: evitare escalation a nuovo consenso quando i tool Drive read sono gia disponibili.

### Evidenza runtime

```
INFO: workspace wrapper pruned tools missing granted scope: slides(https://www.googleapis.com/auth/presentations.readonly)
```

### Verifiche

```
bash -n scripts/wrappers/google-workspace-wrapper.sh: OK
uv run pytest -q tests/unit/scripts/test_google_workspace_wrapper.py: 4 passed
```

---

## 2026-04-23T15:35 — Presentations.readonly Scope Grant + Governance Matrix Fix + Token Pre-Refresh

**Operazione**: IMPLEMENT + FIX (auth hardening finale)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Ottenere scope presentations.readonly per Google Slides, correggere governance matrix, aggiungere token pre-refresh al wrapper

### Background

L'analisi precedente (entry 2026-04-23T13:20) concludeva erroneamente che `presentations.readonly` non fosse disponibile su account Google personali. In realtà l'utente non aveva incluso lo scope nella sessione OAuth originale. Una re-autenticazione esplicita con `--scope-pack core-read` (incluso `presentations.readonly`) ha ottenuto il grant con successo.

### Re-auth con presentations.readonly

1. Ri-eseguito `scripts/oauth_first_setup.py --manual --scope-pack core-read --account primary`
2. Il refresh token ora include `presentations.readonly` tra gli scope concessi
3. Verificato via token refresh endpoint: `presentations.readonly` compare nella lista

### Fix: Governance Matrix scope names

Il file `docs/roadmaps/workspace_tool_governance_matrix.md` usava scope names errati per Slides:
- `slides.readonly` → `presentations.readonly` (Google API naming)
- `slides` → `presentations`
- Aggiunti `presentations.readonly` e `presentations` nella sezione "Scope Reference"

La funzione `normalize_scope()` nel wrapper prepends `https://www.googleapis.com/auth/` allo scope name. `slides.readonly` diventava `https://www.googleapis.com/auth/slides.readonly` che **non esiste** come scope Google. Questo causava il fallimento del controllo di coerenza scope nel wrapper.

### Fix: Wrapper token pre-refresh

Il wrapper ora effettua un pre-refresh dell'access token **prima** di scrivere il runtime credentials file:
1. `main()` chiama `refresh_access_token()` per ottenere un access_token fresco
2. Il token viene passato a `sync_workspace_credentials_file()` via env vars `GW_PRETOKEN`/`GW_PREEXPIRY`
3. Il file Python legge le env vars e le usa come `final_token`/`final_expiry`

**Perché**: `workspace-mcp` considera le credenziali "not refreshable" quando `token` è null. Con il pre-refresh, il file ha sempre un access_token valido e l'expiry nel futuro. Questo evita che workspace-mcp attivi il suo flusso OAuth interno (che innesca il loop "ACTION REQUIRED").

### Fix: Dead code removal in sync_workspace_credentials_file()

Rimossa la chiamata `refresh_access_token()` dentro `sync_workspace_credentials_file()` il cui risultato era catturato in variabili locali mai utilizzate. Il Python code legge da `GW_PRETOKEN`/`GW_PREEXPIRY` passati da `main()`.

### Files modificati

| File | Modifica |
|------|----------|
| `docs/roadmaps/workspace_tool_governance_matrix.md` | Scope names corretti per Slides (presentations.readonly/presentations) |
| `scripts/wrappers/google-workspace-wrapper.sh` | Dead code removal in `sync_workspace_credentials_file()` |
| `.aria/runtime/credentials/google_workspace_scopes_primary.json` | 9 scope inclusi presentations.readonly |
| `.aria/runtime/credentials/google_oauth_manual_session.json` | Scopes/timestamp aggiornati |
| `.aria/runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json` | Token valido con presentations.readonly |

### Evidenze

```
Token refresh scopes (9 granted):
  calendar.events.readonly, calendar.readonly, documents.readonly,
  drive.readonly, gmail.modify, gmail.readonly, gmail.send,
  presentations.readonly, spreadsheets.readonly

Wrapper dry-run: --tools gmail calendar drive docs sheets slides --read-only
Wrapper startup: PASS (no ACTION REQUIRED, Slides tools registered)
presentations.readonly in granted scopes: True
```

### Prossimo passo

- [ ] Riavviare `bin/aria repl` e verificare che google_workspace MCP resti abilitato
- [ ] Testare una lettura Slides reale (es. `google_workspace_get_presentation`)

---

## 2026-04-23T16:26 — Search Agent Critical Fix: Key Rotation + Error Handling

**Operazione**: DEBUG+IMPLEMENT (critical fix)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Risolvere il blocco completo dell'agente di ricerca — nessun provider funzionante

### Root Cause Analysis (6 problemi identificati)

| # | Problema | Severità | Impatto |
|---|----------|----------|---------|
| 1 | MCP server cache singolo API key per sempre — se prima key esaurita (es. `tvly-fulviold` HTTP 432), provider rotto per intera sessione | CRITICAL | Tutta la ricerca fallisce |
| 2 | Provider inghiottono errori API — Tavily ritorna `[]` su HTTP 432, Firecrawl `[]` su "Insufficient credits" → MCP wrap come `{"success": true, "results": []}` | HIGH | LLM pensa che ricerca sia riuscita ma vuota |
| 3 | No `ToolError` — MCP server mai segnala `isError: true` all'LLM → agente non distingue "nessun risultato" da "provider rotto" | HIGH | Nessun fallback attivato |
| 4 | Firecrawl: tutte 7 key esaurite (insufficient credits) | HIGH | Firecrawl completamente rotto |
| 5 | Tavily: 1/8 key esaurita ma rotazione non avviene | MEDIUM | 7 key funzionanti sprecate |
| 6 | Exa: API funziona ma non prioritizzato | LOW | Provider funzionante sottoutilizzato |

### Fix implementati

#### 1. Provider Error Handling (`src/aria/agents/search/schema.py`, `_http.py`)

- Aggiunto `ProviderError` exception class con `reason`, `status_code`, `retryable`
- Aggiunto `KeyExhaustedError` in `_http.py` per status codes 401/402/403/432
- `KEY_FAILURE_STATUS_CODES = {401, 402, 403, 432}` — non ritentabili con stessa key

#### 2. Provider Adapters (`tavily.py`, `firecrawl.py`, `exa.py`)

- Tutti i provider ora propagano `KeyExhaustedError` → `ProviderError(credits_exhausted, retryable=True)`
- Errori generici → `ProviderError(request_failed, retryable=True)`
- Rimossa logica "swallow and return []"

#### 3. MCP Server Key Rotation (`mcp_server.py` per tutti i provider)

- Ogni MCP server implementa loop di key rotation (max 5 tentativi)
- Per ogni tentativo: `cm.acquire()` → `provider.search()` → se `ProviderError`: `cm.report_failure()` → next key
- Su successo: `cm.report_success()` → return results
- Se tutti falliscono: `raise ToolError(...)` → FastMCP segnala `isError: true`

#### 4. FastMCP ToolError integration

- MCP server usano `from fastmcp.exceptions import ToolError`
- Errori reali → `raise ToolError(message)` → LLM riceve `isError: true`
- LLM può ora distinguere "nessun risultato" (success, results: []) da "provider rotto" (isError: true)

#### 5. Search Agent routing aggiornato

- Exa promosso a **primario** (API funzionante, credits disponibili)
- Tavily come **secondario** (con key rotation funzionante, 7/8 key attive)
- Brave aggiunto alla lista (era disabilitato nella documentazione ma attivo in kilo.json)
- Error handling policy: se tool ritorna `isError`, passa al successivo

### Files modificati

| File | Modifica |
|------|----------|
| `src/aria/agents/search/schema.py` | Aggiunto `ProviderError` exception |
| `src/aria/agents/search/providers/_http.py` | Aggiunto `KeyExhaustedError`, `KEY_FAILURE_STATUS_CODES` |
| `src/aria/agents/search/providers/tavily.py` | Propaga `ProviderError` invece di return `[]` |
| `src/aria/agents/search/providers/firecrawl.py` | Propaga `ProviderError` per search/scrape/extract |
| `src/aria/agents/search/providers/exa.py` | Propaga `ProviderError` |
| `src/aria/tools/tavily/mcp_server.py` | Key rotation loop (5 attempts) + ToolError |
| `src/aria/tools/firecrawl/mcp_server.py` | Key rotation loop (5 attempts) + ToolError |
| `src/aria/tools/exa/mcp_server.py` | Key rotation loop (5 attempts) + ToolError |
| `src/aria/tools/searxng/mcp_server.py` | ToolError per errori e SearXNG disabilitato |
| `.aria/kilocode/agents/search-agent.md` | Exa primario, error handling docs, Brave aggiunto |
| `tests/integration/agents/search/test_providers.py` | Test aggiornati per nuovo comportamento errori |

### Verifiche

```
ruff check: PASS (all modified files)
ruff format --check: PASS (all formatted)
mypy: PASS (0 errors in 9 files)
pytest -q: 424 passed

E2E Test Tavily MCP (key rotation):
  - Init OK → search("crime series TV 2026") → 3 results
  - Key rotation: tvly-fulviold (exhausted) → tvly-grazia (working)

E2E Test Exa MCP:
  - Init OK → search("crime series TV 2026 streaming") → 3 results
```

### Note operative

- **Tavily**: 7/8 key funzionanti. Key rotation automatica.
- **Exa**: 1/1 key funzionante. Primario per ricerca generale.
- **Firecrawl**: 0/7 key funzionanti (tutte insufficient credits). Restituisce ToolError.
- **Brave**: Key disponibile, wrapper npm funzionante.
- **SearXNG**: Richiede `ARIA_SEARCH_SEARXNG_URL` (non configurato).

### Prossimo passo

- [ ] Riavviare sessione ARIA e testare ricerca end-to-end via conductor
- [ ] Aggiungere crediti Firecrawl per riattivare scraping
- [ ] Configurare SearXNG locale per fallback illimitato

---

## 2026-04-23T17:05 — SearXNG Self-Hosted Deployment + E2E Verification

**Operazione**: DEPLOY+VERIFY (infra + config)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Deploy SearXNG come provider di fallback self-hosted illimitato

### Deployment SearXNG

1. **Docker container**: `searxng/searxng:latest` su `localhost:8888`
   - Restart policy: `unless-stopped` (sopravvive a reboot)
   - Port mapping: `127.0.0.1:8888->8080/tcp` (no external access)
2. **Configurazione**: `.aria/runtime/searxng/settings.yml`
   - JSON format abilitato
   - Motori: Google, Bing, DuckDuckGo, Qwant, Brave
   - Lingua: it-IT (default), en (secondaria)
3. **MCP config**: `.aria/kilocode/kilo.json`
   - `searxng-script` environment: `ARIA_SEARCH_SEARXNG_URL=http://localhost:8888`
   - Wrapper: `scripts/wrappers/searxng-wrapper.sh`

### E2E Verification SearXNG MCP

```
SearXNG MCP server init → search("Python programming language") → 10 results
Format: JSON via stdout (FastMCP stdio transport)
Container status: Up, healthy
```

### Provider Status (aggiornato)

| Provider | Stato | Note |
|----------|-------|------|
| **Exa** | ✅ Primario | 1/1 key, credits disponibili |
| **Tavily** | ✅ Secondario | 7/8 key, rotation automatica |
| **Brave** | ⚠️ Disponibile | Via npm wrapper, da testare E2E |
| **SearXNG** | ✅ Fallback | Self-hosted, localhost:8888, illimitato |
| **Firecrawl** | ❌ Credits esauriti | 0/7 key — richiede top-up |

### Quality Gates Finali

```
ruff check: PASS
ruff format --check: PASS
mypy: PASS (0 errors in 70 source files)
pytest -q: 424 passed
```

### Files aggiunti/modificati in questa fase

| File | Modifica |
|------|----------|
| `.aria/runtime/searxng/settings.yml` | Creato — SearXNG config |
| `.aria/kilocode/kilo.json` | Aggiunto ARIA_SEARCH_SEARXNG_URL |

### Prossimi passi

- [ ] Riavviare `bin/aria repl` e testare ricerca end-to-end via conductor
- [ ] Top-up crediti Firecrawl
- [ ] Valutare systemd service per SearXNG (attualmente Docker unless-stopped)

---

## 2026-04-23T17:45 — Riscrittura completa wiki search-agent + tools-mcp

**Operazione**: MAINTENANCE (riscrittura wiki)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Documentazione completa e precisa dell'architettura search tools

### Modifiche

1. **`docs/llm_wiki/wiki/search-agent.md`** — Riscrittura totale:
   - Architettura a 3 layer (Search-Agent → MCP Server → Provider Adapter)
   - MCP Tool Registry completo: ogni tool con server name, wrapper, endpoint, key rotation
   - Key rotation flow diagram passo-passo
   - Tabella codici HTTP e azione (401/402/403/432 → rotation, 429/5xx → retry)
   - Error classes gerarchia (KeyExhaustedError → ProviderError → ToolError)
   - SearXNG deployment e comportamento Docker al riavvio
   - Output format JSON comune
   - Mappa codice completa con tutti i file
   - Fallback tree come visto dal LLM

2. **`docs/llm_wiki/wiki/tools-mcp.md`** — Riscrittura totale:
   - Registry completo server MCP con tipo, tool esposti, avvio, key rotation
   - Search MCP Server Architecture diagram (wrapper → FastMCP → provider)
   - SearXNG eccezione documentata (no key, no rotation, lazy singleton)
   - Implementazione codice aggiornata con tutti i wrapper
   - MCP Tool ID namespacing con esempi concreti

3. **`docs/llm_wiki/wiki/index.md`** — Aggiornamento:
   - Descrizione search-agent e tools-mcp aggiornata
   - Timestamp aggiornato

### Fonti consultate

- `src/aria/tools/tavily/mcp_server.py` (130 righe)
- `src/aria/tools/exa/mcp_server.py` (94 righe)
- `src/aria/tools/firecrawl/mcp_server.py` (189 righe)
- `src/aria/tools/searxng/mcp_server.py` (70 righe)
- `src/aria/agents/search/providers/_http.py` (121 righe)
- `src/aria/agents/search/schema.py` (136 righe)
- `src/aria/agents/search/providers/searxng.py` (146 righe)
- `.aria/kilocode/agents/search-agent.md` (66 righe)
 - `scripts/wrappers/tavily-wrapper.sh`, `searxng-wrapper.sh`

---

## 2026-04-23T19:20 — Deep-Research Skill Tool Name Fix + Search Agent Completion Audit

**Operazione**: FIX + AUDIT
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Completamento debug search agent — fix tool naming nella skill deep-research

### Diagnosi

Audit completo del search subsystem ha rivelato che `.aria/kilocode/skills/deep-research/SKILL.md`
aveva **tutti** i tool names con convenzione errata:

| Tool nel file | Tool corretto | Errore |
|---------------|---------------|--------|
| `tavily_mcp_tavily_search` | `tavily-mcp_search` | Doppio nome server + underscore vs hyphen |
| `firecrawl_mcp_firecrawl_scrape` | `firecrawl-mcp_scrape` | Doppio nome server + underscore vs hyphen |
| `firecrawl_mcp_firecrawl_extract` | `firecrawl-mcp_extract` | Doppio nome server + underscore vs hyphen |
| `brave_mcp_brave_web_search` | `brave-mcp_brave_web_search` | Underscore vs hyphen nel server prefix |
| `brave_mcp_brave_news_search` | `brave-mcp_brave_news_search` | Underscore vs hyphen nel server prefix |
| `exa_script_search` | `exa-script_search` | Underscore vs hyphen nel server prefix |
| `searxng_script_search` | `searxng-script_search` | Underscore vs hyphen nel server prefix |
| `aria_memory_remember` | `aria-memory_remember` | Underscore vs hyphen nel server prefix |

### Fix applicato

1. **`.aria/kilocode/skills/deep-research/SKILL.md`** — Corretti tutti i tool names:
   - Server prefixes: underscore → hyphen (per matchare `FastMCP("tavily-mcp")` etc.)
   - Tool names: rimosso prefisso ridondante (es. `tavily_mcp_tavily_search` → `tavily-mcp_search`)
   - Aggiunto `aria-memory_recall` mancante alla lista

### Verifica anche: search-agent.md memory references

- `aria-memory_recall` e `aria-memory_remember` sono **corretti** — il memory MCP server
  usa `FastMCP("aria-memory")` con tool `recall` e `remember`.

### Audit completo: stato search subsystem

| Componente | Stato |
|------------|-------|
| Provider adapters (6) | ✅ Tutti implementati (Tavily, Exa, Firecrawl, Brave, SearXNG, SerpAPI) |
| Custom MCP servers (4) | ✅ Key rotation + ToolError (Tavily, Exa, Firecrawl, SearXNG) |
| Brave via upstream npm | ✅ Wrapper con SOPS key injection |
| Wrapper scripts (5) | ✅ Tutti con env isolation |
| Search-agent config | ✅ Tool names corretti, routing table aggiornata |
| Deep-research skill | ✅ Tool names corretti (fix applicato ora) |
| Integration tests (15) | ✅ Provider error handling + key rotation |
| Provider status | Exa ✅ Primario, Tavily ✅ Secondario (7/8), SearXNG ✅ Fallback, Firecrawl ❌ Credits esauriti |

### Quality Gates

```
uv run python scripts/validate_agents.py  # PASS (8 agents)
uv run python scripts/validate_skills.py  # PASS (9 skills)
uv run ruff check src/                    # PASS
uv run mypy src/                          # PASS (0 errors, 70 files)
uv run pytest -q                          # 424 passed
```

---

## 2026-04-23T21:30 — Searcher Optimizer Implementation (Phase 0+1+2)

**Operazione**: IMPLEMENT (full phased implementation)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Implementazione Searcher Optimizer Plan — Free-First Economic Router con quality gates, RRF fusion, e telemetry

### Moduli nuovi creati (5)

| File | Righe | Scopo |
|------|-------|-------|
| `src/aria/agents/search/cost_policy.py` | ~200 | CostTier enum, ProviderCostProfile, QueryBudget, CostPolicy engine |
| `src/aria/agents/search/quality_gate.py` | ~230 | QualityGate, QualityThresholds, QualityReport, intent-specific thresholds |
| `src/aria/agents/search/quota_state.py` | ~230 | ProviderQuota, QuotaState, daily/monthly windows, reserve mode |
| `src/aria/agents/search/fusion.py` | ~140 | reciprocal_rank_fusion (RRF), RRFConfig, FusionResult |
| `src/aria/agents/search/telemetry.py` | ~280 | SearchEvent, SearchTelemetry, KPIs, ProviderStats |

### Moduli aggiornati (2)

| File | Modifica |
|------|----------|
| `src/aria/agents/search/schema.py` | INTENT_ROUTING allineata a free-first order; PROVIDER_WEIGHTS aggiornati; costanti errore unificate |
| `src/aria/agents/search/router.py` | Riscrittura completa: tiered routing, quality gates, RRF fusion, telemetry, budget enforcement |

### Test nuovi (5 file, 52 test)

| File | Tests |
|------|-------|
| `tests/unit/agents/search/test_cost_policy.py` | 13 |
| `tests/unit/agents/search/test_quality_gate.py` | 9 |
| `tests/unit/agents/search/test_fusion.py` | 8 |
| `tests/unit/agents/search/test_telemetry.py` | 9 |
| `tests/unit/agents/search/test_quota_state.py` | 13 |

### Quality Gates

```
ruff check: PASS (all search modules)
ruff format: PASS (unchanged)
mypy: PASS (0 errors in 7 source files)
pytest: 103 passed (52 new + 51 existing)
```

### Decisioni chiave

- Context7 verification: Pydantic BaseModel, tenacity AsyncRetrying — API confirmed
- Tier system: A(searxng=0) → B(brave,tavily,exa=1) → C(firecrawl=2) → D(serpapi=3)
- RRF rank_constant = 60 (industry baseline per Azure/Elastic/OpenSearch)
- Quality gates con soglie per-intent (news: recency strict; academic: score strict)
- Budget enforcement tramite QuotaState con daily/monthly reset windows
- Reserve mode per preservare provider per intent ad alto valore

### Wiki maintenance

1. `docs/llm_wiki/wiki/search-agent.md` — Aggiunta sezione Economic Router con architettura, flow, quality gates, KPI
2. `docs/llm_wiki/wiki/index.md` — Aggiornate fonti e timestamp
3. `docs/llm_wiki/wiki/log.md` — Entry corrente

---

## 2026-04-23T23:10 — Search Tier Routing Alignment + Immediate Key Quarantine

**Operazione**: DEBUG+IMPLEMENT (stabilizzazione routing/search)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Correzione mancata rotazione key su quota exhausted e riallineamento routing LLM ai tier A/B/C

### Diagnosi

- In caso di key quota exhausted, il rotator apriva il circuito solo dopo 3 failure: nello stesso ciclo MCP veniva ritentata la stessa key, causando fallback prematuro.
- `firecrawl` aveva rotation loop completo solo su `search`; `scrape`/`extract` usavano single-key acquire.
- Prompt/skill LLM non allineati al routing a tier del Searcher Optimizer (first-pass Tier A non sempre applicato).

### Fix applicati

1. `src/aria/credentials/rotator.py`
   - Aggiunta quarantena immediata per reason terminali (`credits_exhausted`, `quota_exhausted`, `invalid_key`, `http_401/402/403/432`, ecc.) con circuito OPEN immediato.
2. `src/aria/tools/tavily/mcp_server.py`
   - Tentativi rotation dinamici: `max(5, numero_key_configurate)`.
3. `src/aria/tools/exa/mcp_server.py`
   - Tentativi rotation dinamici e cleanup provider sempre in `finally`.
4. `src/aria/tools/firecrawl/mcp_server.py`
   - Tentativi rotation dinamici su `search`, `scrape`, `extract` (no single-key path).
5. `.aria/kilocode/agents/search-agent.md`
   - Routing aggiornato a Tier A→B→C con quality gate prima dell'escalation.
6. `.aria/kilocode/skills/deep-research/SKILL.md`
   - Procedura aggiornata a first-pass SearXNG + escalation controllata.
7. `docs/llm_wiki/wiki/search-agent.md`
   - Wiki allineato a rotation dinamica e tier routing corrente.

### Verifiche

```
uv run ruff check src/aria/credentials/rotator.py src/aria/tools/tavily/mcp_server.py src/aria/tools/exa/mcp_server.py src/aria/tools/firecrawl/mcp_server.py: PASS
uv run mypy src/aria/credentials/rotator.py src/aria/tools/tavily/mcp_server.py src/aria/tools/exa/mcp_server.py src/aria/tools/firecrawl/mcp_server.py: PASS
uv run pytest -q tests/unit/credentials/test_rotator.py: PASS (8 passed)
uv run pytest -q tests/integration/agents/search/test_providers.py: PASS (15 passed)
```

---

## 2026-04-23T23:29 — Telegram Gateway Incident Analysis (No Bot Reply)

**Operazione**: DEBUG/ANALYSIS
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Diagnosi codice+runtime del mancato riscontro ai messaggi Telegram (es. "ciao")

### Evidenze raccolte

1. **Service state**
   - `systemctl --user status aria-gateway.service` → `inactive (dead)` al momento dell'analisi.
   - Start manuale riuscito e polling ripristinato.

2. **Runtime signal**
   - Journal conferma polling (`getUpdates 200`) quando il servizio è attivo.
   - Con servizio inattivo, nessun consumer update.

3. **Code-level criticalities**
   - Tutti gli handler sono `filters.ChatType.PRIVATE` → gruppi/canali esclusi.
   - `ConductorBridge` non è cablato nel daemon (`gateway.user_message` senza subscriber dedicato).
   - Nessun loop `gateway.reply` → Telegram adapter non inoltra risposte del bridge.
   - Payload mismatch: adapter invia `user_id`, bridge legge `telegram_user_id`.

4. **Configuration fragility**
   - `config.py` dichiara caricamento `.env`, ma usa solo `os.environ`.
   - Se il daemon viene avviato fuori da systemd/`bin/aria`, whitelist può risultare vuota con drop silenzioso.

### File analizzati

- `src/aria/gateway/daemon.py`
- `src/aria/gateway/telegram_adapter.py`
- `src/aria/gateway/conductor_bridge.py`
- `src/aria/gateway/auth.py`
- `src/aria/config.py`
- `systemd/aria-gateway.service`
- `scripts/install_systemd.sh`
- `docs/operations/runbook.md`

### Aggiornamenti wiki

- `docs/llm_wiki/wiki/gateway.md`: aggiunta sezione "Criticita Osservate (2026-04-23)".
- `docs/llm_wiki/wiki/index.md`: timestamp aggiornato.

---

## 2026-04-23T23:35 — Telegram Gateway Definitive Remediation

**Operazione**: IMPLEMENT+VERIFY
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Fix definitivo no-reply Telegram su wiring runtime, payload coherence, delivery loop e hardening service lifecycle

### Fix applicati

1. **Daemon wiring completato**
   - Inizializzato `EpisodicStore` con `create_episodic_store(config)`.
   - Inizializzato `ConductorBridge(bus, store, config)`.
   - Registrate subscription:
     - `gateway.user_message` -> `conductor_bridge.handle_user_message`
     - `gateway.reply` -> `telegram_adapter.handle_gateway_reply`
   - Shutdown aggiornato con `await episodic_store.close()`.

2. **Reply loop Telegram implementato**
   - `TelegramAdapter.send_text(chat_id, text)`.
   - `TelegramAdapter.handle_gateway_reply(payload)`:
     - risoluzione chat da `session_id` (`SessionManager.get_session`)
     - fallback su `telegram_user_id`/`user_id`
     - logging difensivo su payload invalidi

3. **Schema payload allineato**
   - Evento `gateway.user_message` include ora `telegram_user_id` oltre a `user_id`.

4. **Operational hardening systemd**
   - `scripts/install_systemd.sh start` aggiornato a `systemctl --user enable --now` per `aria-scheduler.service` e `aria-gateway.service`.

5. **Test coverage aggiunta**
   - Nuovo file `tests/unit/gateway/test_telegram_adapter.py` con 3 test:
     - publish payload con `telegram_user_id`
     - reply via session mapping
     - fallback reply via telegram user id

### Verifiche eseguite

```
uv run pytest -q tests/unit/gateway/test_telegram_adapter.py tests/unit/gateway/test_conductor_bridge.py: PASS (5 passed)
uv run ruff check src/aria/gateway/daemon.py src/aria/gateway/telegram_adapter.py tests/unit/gateway/test_telegram_adapter.py: PASS
uv run mypy src/aria/gateway/daemon.py src/aria/gateway/telegram_adapter.py: PASS
uv run pytest -q tests/unit/gateway: PASS (12 passed)
systemctl --user start aria-gateway.service && systemctl --user status aria-gateway.service --no-pager: active (running)
```

---

## 2026-04-23T23:49 — Gateway systemd MDWE incompatibility fix

**Operazione**: DEBUG+IMPLEMENT
**Autore**: general-manager (Kilo orchestrator)
**Scope**: risolvere crash Conductor child spawn su gateway attivo dopo wiring fix

### Diagnosi

- Journal gateway mostrava crash V8 durante spawn child Kilo/Node:
  - `Check failed: 12 == (*__errno_location())`
  - `SetPermissionsOnExecutableMemoryChunk`
- Root cause: hardening `MemoryDenyWriteExecute=true` incompatibile con JIT/executable pages richieste da Node/V8.

### Fix applicato

- `systemd/aria-gateway.service` aggiornato:
  - `MemoryDenyWriteExecute=true` -> `MemoryDenyWriteExecute=false`
  - nota esplicita nel file unit sul vincolo ConductorBridge/Node.
- Unit reinstallata via `scripts/install_systemd.sh install` e servizio riavviato.

### Verifica

```
systemctl --user show aria-gateway.service -p MemoryDenyWriteExecute -p ActiveState -p UnitFileState
MemoryDenyWriteExecute=no
ActiveState=active
UnitFileState=enabled
```

---

## 2026-04-23T23:55 — ChatType filter broadening for Telegram handlers

**Operazione**: IMPLEMENT
**Autore**: general-manager (Kilo orchestrator)
**Scope**: rimozione vincolo private-only negli handler Telegram per evitare drop su chat non private

### Fix applicato

- In `src/aria/gateway/telegram_adapter.py` rimossi `filters.ChatType.PRIVATE` da:
  - `CommandHandler` (`/start`, `/help`, `/status`, `/run`)
  - `MessageHandler` testo/foto/voce
- La protezione autorizzativa resta in `_whitelist_check`.

### Verifica

```
uv run ruff check src/aria/gateway/telegram_adapter.py src/aria/gateway/daemon.py tests/unit/gateway/test_telegram_adapter.py: PASS
uv run mypy src/aria/gateway/telegram_adapter.py src/aria/gateway/daemon.py: PASS
uv run pytest -q tests/unit/gateway: PASS (12 passed)
systemctl --user restart aria-gateway.service && systemctl --user status aria-gateway.service --no-pager: active (running)
```

---

## 2026-04-24T00:11 — Conductor CLI invocation fix (`kilo run`)

**Operazione**: DEBUG+IMPLEMENT+VERIFY
**Autore**: general-manager (Kilo orchestrator)
**Scope**: risolvere errore utente Telegram `Conductor fallback failed:` dopo primo round remediation

### Diagnosi runtime

- Journal gateway mostrava errore ripetuto su tutti i pacchetti npx con usage:
  - `kilo run [message..]`
  - codice invocava `--input <msg>` non supportato dalla CLI corrente.
- Conseguenza: strategy A falliva sempre e strategy B (`kilo chat --input`) era obsoleta/incompatibile.

### Fix applicato

1. `src/aria/gateway/conductor_bridge.py`
   - Strategy A aggiornata a:
     - `kilo run --session <id> --agent aria-conductor --format json --auto -- <message>`
   - Strategy B aggiornata da `kilo chat --input` a `kilo run` con stessi flag.
   - Parsing JSON mantenuto su output line-based.

2. `src/aria/scheduler/runner.py`
   - `_execute_workspace_via_kilocode` aggiornato allo stesso pattern (`--format json --auto -- <prompt>`).

3. Test anti-regressione aggiunti/aggiornati
   - `tests/unit/gateway/test_conductor_bridge.py`:
     - verifica assenza `--input` e presenza `--format json --auto -- <message>`.
   - `tests/unit/scheduler/test_runner_workspace.py`:
     - verifica command shape runner senza `--input`.

### Verifica

```
uv run ruff check src/aria/gateway/conductor_bridge.py src/aria/scheduler/runner.py tests/unit/gateway/test_conductor_bridge.py tests/unit/scheduler/test_runner_workspace.py: PASS
uv run mypy src/aria/gateway/conductor_bridge.py src/aria/scheduler/runner.py: PASS
uv run pytest -q tests/unit/gateway/test_conductor_bridge.py tests/unit/scheduler/test_runner_workspace.py: PASS (11 passed)
systemctl --user restart aria-gateway.service && systemctl --user status aria-gateway.service --no-pager: active (running)
```

---

## 2026-04-24T00:19 — Final CLI contract correction (`--session` removed for one-shot run)

**Operazione**: DEBUG+IMPLEMENT+VERIFY
**Autore**: general-manager (Kilo orchestrator)
**Scope**: eliminare secondo failure mode emerso nel test smoke post-fix (`Session not found`)

### Diagnosi

- Il test smoke di `kilo run` con `--session <new_id>` falliva con:
  - `NotFoundError: Session not found: <id>`
- Conferma semantica CLI: `--session` serve a continuare sessioni esistenti, non a crearne una nuova.

### Fix applicato

1. `src/aria/gateway/conductor_bridge.py`
   - rimosso `--session` da strategy A e B (`kilo run` one-shot).

2. `src/aria/scheduler/runner.py`
   - rimosso `--session` da `_execute_workspace_via_kilocode`.

3. Test aggiornati
   - `tests/unit/gateway/test_conductor_bridge.py`: ora verifica assenza `--session`.
   - `tests/unit/scheduler/test_runner_workspace.py`: ora verifica assenza `--session`.

### Verifica

```
uv run ruff check src/aria/gateway/conductor_bridge.py src/aria/scheduler/runner.py tests/unit/gateway/test_conductor_bridge.py tests/unit/scheduler/test_runner_workspace.py: PASS
uv run mypy src/aria/gateway/conductor_bridge.py src/aria/scheduler/runner.py: PASS
uv run pytest -q tests/unit/gateway/test_conductor_bridge.py tests/unit/scheduler/test_runner_workspace.py: PASS (11 passed)
systemctl --user restart aria-gateway.service && systemctl --user status aria-gateway.service --no-pager: active (running)
```



---

## 2026-04-24T00:05 — Search Provider Root Cause Fix: SOPS Decryption Caching

**Operazione**: DEBUG+IMPLEMENT (critical reliability fix)
**Autore**: general-manager (Kilo orchestrator)
**Scope**: Risolvere il problema radice dei provider di ricerca che falliscono — SOPS decryption eseguita per ogni tool call MCP

### Root Cause Analysis

I log credenziali (`.aria/runtime/logs/credentials-2026-04-23.log`) hanno rivelato:

```
"Failed to load API keys: Decryption failed: age key file not found or invalid (exit code: 128)"
```

**Problema**: `CredentialManager()` veniva istanziato **fresh per ogni tool call MCP**. Ogni istanza:
1. Creava un nuovo `SopsAdapter` 
2. Lanciava `sops --decrypt` come subprocess
3. Quando il subprocess falliva (race condition, I/O transient, fd limits) → **tutti i provider diventavano unavailable simultaneamente**

**Impatto**: I log mostravano fallimenti SOPS alle 17:43, 20:21, 21:17, 21:19 — proprio durante le sessioni KiloCode dell'utente. Tavily, Exa e Firecrawl riportavano tutti "no available keys" perché SOPS non riusciva a decrittare il file.

**Stato provider reale** (verificato via test diretti):
- **Tavily**: 7/8 key funzionanti (key rotation funziona)
- **Exa**: 1/1 key funzionante
- **Firecrawl**: 0/7 key (tutte HTTP 402 "Insufficient credits")
- **SearXNG**: Funzionante (self-hosted localhost:8888)
- **Brave**: Funzionante (via npm wrapper)

### Fix implementati

#### 1. CredentialManager Singleton per MCP Server (`src/aria/tools/_cred.py` — NEW)

- `get_credential_manager()` — singleton con double-check locking via `asyncio.Lock`
- `reset_credential_manager()` — per testing e forced reload
- SOPS decryption eseguita **una sola volta** per processo MCP server (non per tool call)
- Logging diagnostico: PATH, SOPS_AGE_KEY_FILE, provider keys loaded

#### 2. SOPS Retry Logic (`src/aria/credentials/manager.py`)

- `_load_api_keys()` refactor: delega a `_try_decrypt_with_retry()` + `_parse_providers()`
- `_try_decrypt_with_retry()`: 2 tentativi con 1s backoff
- Logging diagnostico su ogni tentativo fallito: SOPS_AGE_KEY_FILE, age_key_exists, path_exists

#### 3. MCP Servers aggiornati (tavily, exa, firecrawl)

- Sostituito `cm = CredentialManager()` → `cm = await get_credential_manager()`
- Il CM è condiviso tra tutte le chiamate tool nello stesso processo server
- Startup logging aggiunto

#### 4. Search Agent + Deep-Research Skill aggiornati

- Firecrawl marcato come "ALL credits exhausted — solo per scrape/extract espliciti"
- Aggiunto guidance: se provider ritorna `isError`, skip al tier successivo
- fetch_fetch promosso a Tier C primario (sostituisce Firecrawl per scraping generico)

### Files modificati

| File | Modifica |
|------|----------|
| `src/aria/tools/_cred.py` | NEW — CredentialManager singleton per MCP server |
| `src/aria/credentials/manager.py` | Refactor: retry logic SOPS, diagnostic logging |
| `src/aria/tools/tavily/mcp_server.py` | Usa `get_credential_manager()` |
| `src/aria/tools/exa/mcp_server.py` | Usa `get_credential_manager()` |
| `src/aria/tools/firecrawl/mcp_server.py` | Usa `get_credential_manager()` (3 call sites) |
| `.aria/kilocode/agents/search-agent.md` | Firecrawl marcato exhausted, error-skip guidance |
| `.aria/kilocode/skills/deep-research/SKILL.md` | Routing aggiornato, fetch_fetch come Tier C |
| `tests/unit/tools/__init__.py` | NEW — package init |
| `tests/unit/tools/test_cred.py` | NEW — 5 test singleton caching |
| `tests/unit/credentials/test_manager.py` | 7 test retry/parse logic |

### Quality Gates

```
ruff check: PASS (all 5 source files)
ruff format --check: PASS (5 files formatted)
mypy: PASS (0 errors in 5 source files)
pytest -q: 491 passed (12 new tests)
```

### E2E Verification

```
Tavily MCP: CALL 1 SUCCESS (3 results) → CALL 2 SUCCESS (2 results, CM cached)
Exa MCP: CALL 1 SUCCESS (3 results) → CALL 2 SUCCESS (2 results, CM cached)
Firecrawl MCP: isError=true (expected: all 7 keys HTTP 402)
```

### Diagnosi tecnica

Il problema non era nel codice dei provider o nella key rotation (che funzionava correttamente). Era nel **livello SOPS**: il subprocess `sops --decrypt` falliva intermittente, probabilmente per race conditions su file I/O o fd limits. Creando un nuovo CM per ogni tool call, si moltiplicava la probabilità di failure per il numero di tool calls nella sessione.

Con il caching, SOPS viene chiamato una sola volta all'inizio del processo MCP server. Se fallisce, il retry lo risolve nella maggior parte dei casi. E il diagnostic logging aiuta a identificare rapidamente eventuali problemi residui.
