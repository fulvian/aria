---
title: ARIA LLM Wiki Activity Log
sources: []
last_updated: 2026-04-23T15:35:00+02:00
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
