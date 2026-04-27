# Workspace Agent Enhancement Analysis

## Scope e obiettivo

Questo documento analizza il workflow end-to-end dell'agente Google Workspace in ARIA e propone un percorso di enhancement per passare da configurazione "basic" a utilizzo professionale, affidabile e osservabile.

Obiettivi principali:
- aumentare copertura tool realmente usati;
- migliorare robustezza OAuth + scope management;
- allineare skills/agent config ai tool reali esposti dal MCP;
- introdurre osservabilita e test e2e specifici Workspace.

---

## Verifica tecnica reale (stato al 2026-04-22)

Questa sezione integra l'analisi con evidenze concrete sullo stato auth/runtime attuale, senza sostituire le sezioni gia presenti.

## A) Autenticazione: cosa risulta davvero funzionante

Evidenze raccolte nel repository/runtime locale:

- Commit di stabilizzazione OAuth presenti e recenti (`ab34afd`, `59c001e`), con fix specifici su wrapper e setup script.
- Wrapper Google Workspace avviabile con successo e bootstrap auth coerente (`scripts/wrappers/google-workspace-wrapper.sh --help`):
  - risolve keyring + config runtime;
  - imposta `WORKSPACE_MCP_CREDENTIALS_DIR`;
  - espone user context al server upstream.
- Test unitari auth/scope script passati localmente:
  - `tests/unit/agents/workspace/test_oauth_helper.py`
  - `tests/unit/agents/workspace/test_scope_manager.py`
  - `tests/unit/credentials/test_oauth_first_setup_script.py`
  - esito: **10 passed**.

Conclusione tecnica: il problema bloccante "OAuth 2.1 mode requires an authenticated user" risulta mitigato nello scenario stdio locale; il flusso auth non e piu in stato "rotto", ma resta limitato perimetralmente (vedi punto B).

## B) Limiti reali ancora aperti nella catena auth/scope

1. **Scope operativo effettivo ancora Gmail-only**
   - File runtime scope (`.aria/runtime/credentials/google_workspace_scopes_primary.json`) mostra solo `gmail.readonly`.
   - Wrapper sincronizza il credential file upstream con scope hardcoded `gmail.readonly`.
   - Effetto: il runtime reale non e ancora allineato alla matrice scope minima completa di blueprint/ADR (Calendar/Drive/Docs/Sheets non realmente attivati a livello token grant).

2. **Bridge custom obbligatorio tra ARIA e upstream**
   - In runtime viene forzato `MCP_ENABLE_OAUTH21=false` per compatibilita con flusso locale keyring/stdio.
   - E una scelta tecnica pragmatica che stabilizza il funzionamento locale, ma rappresenta una modalita integrativa specifica ARIA (non default upstream).

3. **Persistenza credenziali in file runtime upstream-format**
   - Il wrapper genera `<email>.json` in `.aria/runtime/credentials/google_workspace_mcp/` includendo refresh token/client metadata per compatibilita con `workspace-mcp`.
   - Questo e funzionale al bootstrap, ma va trattato esplicitamente come deroga governata rispetto alla regola "refresh token solo keyring" (ADR-0003 §2.3), con mitigazioni documentate (path runtime, permessi 0600, esclusione dal git).

## C) Upstream o versione custom?

Risposta verificata:

- **Server MCP usato**: upstream pubblicato (`workspace-mcp`), avviato via `uvx workspace-mcp`.
- **Versione rilevata**: `1.19.0`.
- **Fork locale del server upstream**: **non evidenziato** nel repository (nessun codice `google_workspace_mcp` vendorizzato/modificato).
- **Componente custom ARIA**: adapter di integrazione (`scripts/wrappers/google-workspace-wrapper.sh`) + flusso setup (`scripts/oauth_first_setup.py`) + helper runtime (`oauth_helper.py`, `scope_manager.py`).

Perche esiste il custom layer:

- integra keyring ARIA e naming coerente account/service;
- allinea il bootstrap credenziali al formato file atteso dall'upstream;
- riduce attrito operativo del flusso locale stdio.

Valutazione policy blueprint:

- **P2 Upstream Invariance**: rispettato sul server MCP (nessuna patch al sorgente upstream).
- **P8 Tool Priority Ladder**: rispettato (si usa MCP maturo invece di reimplementare API Workspace).
- **P1/P4 isolamento+local-first**: rispettato (runtime in `.aria/`, non in global KiloCode).
- **P7/P9/P12/P13**: allineamento parziale (vedi sezione D).

## D) Allineamento complessivo a blueprint + architettura corrente

### Allineato

- dependency upstream dichiarata e usata (`uvx workspace-mcp`, blueprint §12.1);
- PKCE-first nel setup OAuth (con fallback manuale robusto);
- token principal in keyring via `KeyringStore`;
- isolamento configurativo in `.aria/kilocode/kilo.json` e runtime locale.

### Parzialmente allineato / da chiudere

1. **Scope baseline incompleta in runtime effettivo** (solo Gmail readonly).
2. **Workspace scheduler ancora stub** (`src/aria/scheduler/runner.py`: category non-system -> `not_implemented`), quindi non c'e ancora esecuzione autonoma reale dei workflow Workspace.
3. **Governance agent/skill incompleta**:
   - `workspace-agent` senza allowlist `allowed-tools` esplicita in frontmatter;
   - validation scripts ancora puntati a `mcp.json` legacy invece di `kilo.json`.
4. **HITL coverage non dimostrata e2e** su tutte le write operation oltre il subset base.
5. **Telemetria tool-level insufficiente** per validare adozione reale e failure modes.

### Punto di attenzione architetturale (da formalizzare)

Il bridge wrapper che replica credenziali in formato upstream e una soluzione tecnica valida per l'operativita attuale, ma va esplicitata come:

- allineamento documentato a ADR-0003 (o nuova ADR specifica),
- con policy di hardening e lifecycle chiara su questi file runtime.

---

## Workflow attuale (as-is)

Flusso operativo reale nel repository:

1. **Ingress**: Telegram/Gateway riceve messaggio utente.
2. **Bridge**: `ConductorBridge` avvia child session `kilo run --agent aria-conductor`.
3. **Dispatch**: `aria-conductor` delega a `workspace-agent` via tool `task` per intent workspace.
4. **Execution**: `workspace-agent` usa tool `google_workspace_*` (MCP `google_workspace`).
5. **OAuth runtime**: wrapper `scripts/wrappers/google-workspace-wrapper.sh` legge refresh token da keyring e avvia `uvx workspace-mcp`.
6. **Policy/HITL**: write ops dovrebbero passare da HITL (definito a livello prompt/skill).
7. **Memory**: risultati rilevanti dovrebbero essere persistiti in `aria-memory`.
8. **Scheduler**: task cron `daily-email-triage` instrada `workspace-agent` + skill `triage-email`.

File chiave del workflow:
- `src/aria/gateway/conductor_bridge.py`
- `.aria/kilocode/agents/aria-conductor.md`
- `.aria/kilocode/agents/workspace-agent.md`
- `scripts/wrappers/google-workspace-wrapper.sh`
- `src/aria/agents/workspace/oauth_helper.py`
- `src/aria/agents/workspace/scope_manager.py`
- `scripts/seed_scheduler.py`

---

## Tool inventory: upstream vs implementato vs usato

## 1) Upstream `workspace-mcp` (tool disponibili)

Dalla documentazione ufficiale (`/taylorwilsdon/google_workspace_mcp` via Context7):

- **Gmail**: `search_gmail_messages`, `get_gmail_message_content`, `send_gmail_message`, `draft_gmail_message`
- **Calendar**: `list_calendars`, `get_events`, `get_event`, `create_event`, `modify_event`, `delete_event`
- **Drive**: `search_drive_files`, `get_drive_file_content`, `list_drive_items`, `create_drive_file`
- **Docs**: `search_docs`, `get_doc_content`, `list_docs_in_folder`, `create_doc`, comment/reply/resolve tools
- **Sheets**: `list_spreadsheets`, `get_spreadsheet_info`, `read_sheet_values`, `modify_sheet_values`, create/comment tools
- **Slides**: creation/read/update/comment tools
- **Forms**: create/read/publish/response tools
- **Chat**: space/message search/send tools

Copertura upstream: **molto ampia (multi-prodotto Workspace)**.

## 2) Implementato in ARIA (config + prompt + skill)

- MCP server `google_workspace` abilitato in `.aria/kilocode/kilo.json`.
- Wrapper custom per OAuth/keyring + bootstrap credenziali upstream.
- `workspace-agent` con regole P7/P8, ma **frontmatter minimale** (no `allowed-tools` espliciti, no `required-skills` dichiarati).
- Skills workspace presenti:
  - `triage-email`
  - `calendar-orchestration`
  - `doc-draft`

## 3) Realmente usato (evidenze)

- Scheduler DB contiene solo task workspace seedato: `daily-email-triage` (`workspace-agent` + `triage-email`).
- Evidenza live MVP use-case ancora pendente in `docs/implementation/phase-1/mvp_demo_2026-04-21.md`.
- Dai log disponibili non emerge una telemetria strutturata dei `tools_invoked` Workspace per sessione.
- Riscontro operativo aggiornato: query Gmail (`search_gmail_messages`) riallineata dopo fix OAuth stdio; perimetro operativo reale ancora principalmente Gmail read-only.

Conclusione: **la piattaforma e configurata per Workspace, con auth Gmail ora stabilizzata, ma l'uso effettivo resta concentrato su pochi casi (prevalentemente Gmail read).**

---

## Matrice dei 8 tool core (focus richiesto)

| Tool core | Upstream disponibile | Implementato in ARIA | Uso reale osservato | Gap principale |
|---|---:|---:|---:|---|
| `search_gmail_messages` | SI | SI | PARZIALE (ad-hoc) | auth flow stabilizzato; manca evidence e2e strutturata |
| `get_gmail_message_content` | SI | SI | BASSO/NON EVIDENZIATO | mancano metriche per prova uso |
| `send_gmail_message` | SI | SI | NON EVIDENZIATO | HITL non verificato e2e |
| `list_calendars` | SI | SI | NON EVIDENZIATO | skill non validata live |
| `get_events` | SI | SI | NON EVIDENZIATO | manca pipeline free/busy testata |
| `create_event` | SI | SI | NON EVIDENZIATO | gating HITL da convalidare |
| `search_drive_files` | SI | SI | NON EVIDENZIATO | assenza casi reali e test integrati |
| `get_drive_file_content` | SI | SI | NON EVIDENZIATO | assenza casi reali e test integrati |

Nota: il repository include anche tool Docs/Sheets nel blueprint/prompt, ma non risultano ancora parte di un ciclo operativo stabile con evidenze runtime.

---

## Gap analysis tecnica

1. **Configurazione agente incompleta rispetto blueprint**
   - `workspace-agent` non esplicita `allowed-tools`/`required-skills` nel formato operativo desiderato dal blueprint.

2. **Mismatch naming tool tra documentazione skill e runtime**
   - Skills usano pattern con slash (`google_workspace/search_gmail_messages`) mentre il runtime espone tool con underscore (`google_workspace_search_gmail_messages`).
   - Rischio: istruzioni non allineate, tool selection meno deterministica.

3. **Scope management non allineato alla strategia minima dichiarata**
   - Nel wrapper la credenziale sincronizzata contiene scopes hardcoded a `gmail.readonly`.
   - Questo riduce di fatto la capacita reale su Calendar/Drive/Docs/Sheets.

4. **Osservabilita insufficiente sul fronte "tool usage"**
   - Manca una traccia affidabile per sessione: `tools_invoked`, esito tool, latenza, retry, errore reason.
   - Difficile capire cosa viene davvero usato in produzione.

5. **Validation tooling obsoleto**
   - Script di validazione agent/skill referenziano `mcp.json` legacy, mentre il runtime usa `.aria/kilocode/kilo.json`.

6. **Copertura test workspace limitata al perimetro unit/infrastrutturale**
   - Mancano test e2e end-to-end robusti per i workflow principali Gmail/Calendar/Drive con HITL.

---

## Best practice Google Workspace API (ricerca esterna)

Fonti ufficiali Google Developer consultate:
- Gmail sync: `https://developers.google.com/workspace/gmail/api/guides/sync`
- Gmail push: `https://developers.google.com/workspace/gmail/api/guides/push`
- Calendar sync: `https://developers.google.com/workspace/calendar/api/guides/sync`
- Calendar quota/error: `https://developers.google.com/workspace/calendar/api/guides/quota`, `https://developers.google.com/workspace/calendar/api/guides/errors`
- Drive performance/error: `https://developers.google.com/drive/api/guides/performance`, `https://developers.google.com/workspace/drive/api/guides/handle-errors`
- OAuth best practices: `https://developers.google.com/identity/protocols/oauth2/resources/best-practices`

Raccomandazioni chiave da adottare:

1. **Incremental sync e token persistence**
   - Gmail: full sync iniziale + partial sync con `historyId`; fallback full sync su `404` history out-of-range.
   - Calendar: persist `nextSyncToken`; su `410` fare wipe cache locale + full sync.

2. **Riduzione polling con push notification**
   - Gmail watch + Pub/Sub (renew periodico, ack obbligatorio, fallback poll se notifiche perse).
   - Calendar push per ridurre carico quota.

3. **Quota discipline + retry strategy**
   - Exponential backoff (truncated) su 403/429/5xx.
   - Randomizzazione traffico schedulato (evitare burst allineati).

4. **Performance API**
   - `fields` parameter per partial response.
   - gzip e patch update dove applicabile.
   - Batch requests con limiti prudenti (Gmail consiglia evitare batch troppo grandi; Drive max 100, ma usare sizing conservativo).

5. **OAuth security posture**
   - PKCE, `state` anti-CSRF, secure token storage, revoca token quando non necessari.
   - Incremental authorization: richiedere scope nel momento d'uso feature.

---

## Linee di enhancement proposte

## Fase A — Hardening configurazione (P0, 1 settimana)

### A1. Allineamento tool naming e policy
- Normalizzare naming tool in skills/agent al formato runtime effettivo (`google_workspace_*`).
- Aggiungere `allowed-tools` espliciti al `workspace-agent` con subset controllato e <= 20 tool.

**Deliverable**:
- update `.aria/kilocode/agents/workspace-agent.md`
- update skills `triage-email`, `calendar-orchestration`, `doc-draft`

### A2. Scope e OAuth stabilization
- Rimuovere hardcode `gmail.readonly` nella sync credentials file del wrapper.
- Derivare scopes concessi da file runtime (`google_workspace_scopes_primary.json`) o env canonicale.
- Gestire chiaramente modalita callback fail-safe (manual code fallback gia documentato).

**Deliverable**:
- patch `scripts/wrappers/google-workspace-wrapper.sh`
- test unit/regression su helper OAuth/scope manager

### A3. Validation scripts update
- Portare `validate_agents.py` / `validate_skills.py` su `.aria/kilocode/kilo.json` reale.

---

## Fase B — Capability unlock (P1, 1-2 settimane)

### B1. Abilitazione toolset core 8 end-to-end
- Validare i 8 tool core con smoke test reali e fixture test.
- Produrre evidence strutturata per ogni tool: request class, response schema, failure modes.

### B2. Skill enrichment
- `triage-email`: supporto query temporali robuste (`after:`/`newer_than:`), dedup thread, priorita.
- `calendar-orchestration`: free/busy multi-calendario, slot scoring, timezone safety.
- `doc-draft`: template-driven drafting + metadata tagging in memory.

### B3. HITL rigoroso su tutte le write
- matrice write op -> mandatory HITL gate testata e documentata.

---

## Fase C — Observability e operativita (P1, 1 settimana)

### C1. Workspace telemetry
- Per ogni chiamata tool: `trace_id`, `tool_name`, latency, status, error.reason, retry_count.
- Dashboard minima: success rate per tool, top error reasons, quota pressure.

### C2. Evidence pipeline
- Script automatico che genera report settimanale uso tool (quali tool usati davvero e frequenza).

---

## Fase D — Advanced professional usage (P2, 2+ settimane)

### D1. Push-based architecture
- Gmail watch + Pub/Sub consumer + fallback poll.
- Calendar push channel renewal.

### D2. Incremental sync state store
- Persistenza robusta di `historyId`/`syncToken` per account e risorsa.
- Recovery flow su 404/410 con replay controllato.

### D3. Estensione coverage tool
- Aprire gradualmente Docs/Sheets comment workflows e Drive list/create avanzati.

---

## KPI e criteri di successo

KPI operativi proposti:
- Copertura tool core 8 con test e2e: **100%**.
- Success rate workspace tool calls: **>= 98%** (esclusi errori di permesso utente).
- Retry-recovered failures su 403/429/5xx: **>= 90%**.
- Percentuale richieste gestite via sync incrementale o push (vs polling full): **>= 80%**.
- HITL compliance write operations: **100%**.

---

## Backlog prioritizzato (execution-ready)

1. **P0**: fix wrapper scope hardcode + allineamento naming tool runtime.
2. **P0**: aggiornamento `workspace-agent` con allowed-tools espliciti e required-skills.
3. **P1**: test e2e su 8 tool core + evidence documentata.
4. **P1**: telemetry `tools_invoked` e report settimanale di utilizzo reale.
5. **P2**: push notifications Gmail/Calendar + sync token store.
6. **P2**: estensione capability Docs/Sheets/Drive advanced.

---

## Rischi e mitigazioni

- **Rischio**: regressione OAuth durante refactor wrapper.
  - **Mitigazione**: canary su account test + rollback immediato a script attuale.

- **Rischio**: aumento scope e frizione consenso utente.
  - **Mitigazione**: incremental auth per feature, UX di motivazione scope in-context.

- **Rischio**: rate-limit in ambienti multi-task scheduler.
  - **Mitigazione**: jitter scheduling + backoff + quota dashboard.

---

## Stato finale atteso

A valle del percorso proposto, l'agente Workspace passa da "configurato ma poco sfruttato" a "operativo professionale":
- tool core realmente usati e osservabili;
- auth/scopes robusti e aderenti best practice Google;
- workflow Gmail/Calendar/Drive/Docs/Sheets testati end-to-end con HITL e metriche.

---

## Approfondimento esteso: censimento completo upstream e coverage reale

## Metodo di analisi (deep-dive)

Per garantire un inventario completo e non approssimato ho usato tre fonti con cross-check:

1. **Repository upstream** `taylorwilsdon/google_workspace_mcp` (branch `main`), inclusi moduli tool `*_tools.py`.
2. **Manifest ufficiale upstream** (`manifest.json`) per verificare domini funzionali pubblicati.
3. **Estrazione automatica dai decorator tool** sui moduli upstream: risultato **114 tool** catalogati.

Nota: il server upstream espone 10 domini principali nel manifest (`google_calendar`, `google_drive`, `gmail`, `google_docs`, `google_sheets`, `google_slides`, `google_forms`, `google_chat`, `google_tasks`, `google_custom_search`), con ulteriori moduli avanzati nel repository (`gcontacts`, `gappsscript`).

---

## Catalogo completo tool upstream (114)

### Gmail (14)
- `search_gmail_messages`
- `get_gmail_message_content`
- `get_gmail_messages_content_batch`
- `get_gmail_attachment_content`
- `send_gmail_message`
- `draft_gmail_message`
- `get_gmail_thread_content`
- `get_gmail_threads_content_batch`
- `list_gmail_labels`
- `manage_gmail_label`
- `list_gmail_filters`
- `manage_gmail_filter`
- `modify_gmail_message_labels`
- `batch_modify_gmail_message_labels`

### Google Calendar (7)
- `list_calendars`
- `get_events`
- `manage_event`
- `manage_out_of_office`
- `manage_focus_time`
- `query_freebusy`
- `create_calendar`

### Google Drive (14)
- `search_drive_files`
- `get_drive_file_content`
- `get_drive_file_download_url`
- `list_drive_items`
- `create_drive_folder`
- `create_drive_file`
- `import_to_google_doc`
- `get_drive_file_permissions`
- `check_drive_file_public_access`
- `update_drive_file`
- `get_drive_shareable_link`
- `manage_drive_access`
- `copy_drive_file`
- `set_drive_file_permissions`

### Google Docs (20)
- `search_docs`
- `get_doc_content`
- `list_docs_in_folder`
- `create_doc`
- `modify_doc_text`
- `find_and_replace_doc`
- `insert_doc_elements`
- `insert_doc_image`
- `update_doc_headers_footers`
- `batch_update_doc`
- `inspect_doc_structure`
- `debug_docs_runtime_info`
- `create_table_with_data`
- `debug_table_structure`
- `export_doc_to_pdf`
- `update_paragraph_style`
- `get_doc_as_markdown`
- `insert_doc_tab`
- `delete_doc_tab`
- `update_doc_tab`

### Google Sheets (11)
- `list_spreadsheets`
- `get_spreadsheet_info`
- `read_sheet_values`
- `modify_sheet_values`
- `format_sheet_range`
- `manage_conditional_formatting`
- `create_spreadsheet`
- `create_sheet`
- `list_sheet_tables`
- `append_table_rows`
- `resize_sheet_dimensions`

### Google Slides (5)
- `create_presentation`
- `get_presentation`
- `batch_update_presentation`
- `get_page`
- `get_page_thumbnail`

### Google Forms (6)
- `create_form`
- `get_form`
- `set_publish_settings`
- `get_form_response`
- `list_form_responses`
- `batch_update_form`

### Google Chat (6)
- `list_spaces`
- `get_messages`
- `send_message`
- `search_messages`
- `create_reaction`
- `download_chat_attachment`

### Google Tasks (6)
- `list_task_lists`
- `get_task_list`
- `manage_task_list`
- `list_tasks`
- `get_task`
- `manage_task`

### Google Custom Search (2)
- `search_custom`
- `get_search_engine_info`

### Google Contacts (8)
- `list_contacts`
- `get_contact`
- `search_contacts`
- `manage_contact`
- `list_contact_groups`
- `get_contact_group`
- `manage_contacts_batch`
- `manage_contact_group`

### Google Apps Script (15)
- `list_script_projects`
- `get_script_project`
- `get_script_content`
- `create_script_project`
- `update_script_content`
- `run_script_function`
- `manage_deployment`
- `list_deployments`
- `list_script_processes`
- `delete_script_project`
- `list_versions`
- `create_version`
- `get_version`
- `get_script_metrics`
- `generate_trigger_code`

---

## Mappatura capability: upstream vs ARIA

## A) Livello trasporto/tooling MCP

- **Stato**: ARIA avvia `uvx workspace-mcp` tramite `scripts/wrappers/google-workspace-wrapper.sh`.
- **Implicazione**: a livello server MCP, ARIA puo potenzialmente accedere all'intera superficie upstream (non solo ai tool core 8).

## B) Livello agent policy e governance

- `workspace-agent` corrente non dichiara una allowlist esplicita completa nel frontmatter.
- Le regole P7/HITL documentano solo un sottoinsieme write (`send_gmail_message`, `create_event`, `create_doc`, `modify_sheet_values`, `create_drive_file`).
- Mancano policy equivalenti per write avanzate su:
  - Calendar advanced (`manage_event`, `manage_out_of_office`, `manage_focus_time`, `create_calendar`)
  - Drive ACL/link/sharing (`manage_drive_access`, `set_drive_file_permissions`, `update_drive_file`)
  - Docs/Sheets batch e formatting
  - Chat send/reaction
  - Tasks/Contacts/App Script

## C) Livello skill/workflow

Skill workspace presenti (3):
- `triage-email`
- `calendar-orchestration`
- `doc-draft`

Coverage skill attuale: focalizzata su use case base Gmail/Calendar/Docs.

Assenti skill dedicate per:
- Drive knowledge retrieval avanzato
- Sheets analytics e data ops
- Slides briefing automation
- Forms intake pipeline
- Tasks workload management
- Chat operational assistant
- Contacts enrichment
- App Script orchestration
- Custom Search grounding

## D) Livello esecuzione reale (workflow realmente usati)

Evidenze runtime locali:
- Scheduler contiene task workspace `daily-email-triage`, ma i run risultano `not_implemented` con summary: `Task category 'workspace' not implemented in Sprint 1.2 (stub)`.
- In pratica, il percorso scheduler->workspace non esegue ancora tool Workspace reali.
- Episodic memory locale non mostra tracce consistenti di invocazioni Workspace operative.
- Riscontro manuale utente: tentativi Gmail presenti, con frizioni OAuth in alcune sessioni.

Conclusione operativa:
- **Potenziale disponibile**: molto alto (surface upstream ampia).
- **Potenziale orchestrato e governato**: medio-basso.
- **Potenziale realmente esercito nei workflow**: basso.

---

## Gap critici emersi dal deep-dive

1. **Gap di ampiezza funzionale**
   - L'analisi iniziale copre bene i core 8, ma non l'intera superficie 114 tool.

2. **Gap di orchestrazione**
   - Manca un layer skill che renda utilizzabili in modo sistematico Tasks/Chat/Forms/Slides/Contacts/App Script/Search.

3. **Gap di compliance HITL**
   - Policy write incomplete su domini oltre Gmail/Calendar/Docs/Sheets/Drive base.

4. **Gap di execution path**
   - Scheduler workspace in stub: niente automazioni reali in produzione locale.

5. **Gap di observability**
   - Nessun inventory automatico periodico "tool enabled vs tool invoked".

---

## Sezione aggiuntiva: proposte di ampliamento funzionalita Workspace Agent

Questa sezione estende l'analisi senza sostituire le sezioni precedenti e punta a sfruttare **tutte** le potenzialita upstream in modo governato.

## 1) Nuova libreria di skills agentiche (proposta)

### 1.1 Inbox Command Center
- **Tool**: Gmail labels/filters/thread batch + Tasks.
- **Funzione**: triage intelligente, creazione task da email, follow-up automatici in bozza, SLA inbox.
- **Best practice**: query Gmail con operatori avanzati, sincronizzazione incrementale, batch moderato.

### 1.2 Meeting Intelligence Orchestrator
- **Tool**: Calendar `query_freebusy`, `manage_event`, `manage_out_of_office`, `manage_focus_time` + Gmail/Chat.
- **Funzione**: proposta slot multi-attendee, gestione buffer, blocchi focus, notifiche pre-meeting.
- **Best practice**: freebusy API, timezone robusta, fallback su sync token invalidati.

### 1.3 Drive Knowledge Navigator
- **Tool**: `search_drive_files`, `list_drive_items`, `get_drive_file_content`, `get_drive_file_permissions`.
- **Funzione**: retrieval semantico cross-folder, access validation, knowledge packs per progetto.
- **Best practice**: query `q` mirate, `fields` minimali, `corpora` controllato, `incompleteSearch` handling.

### 1.4 Docs Production Assistant
- **Tool**: docs batch/edit/structure/tab/table/export.
- **Funzione**: generazione documenti enterprise con template, sezioni, tabelle KPI, export PDF.
- **Best practice**: operazioni idempotenti, patch semantico, validazione struttura prima di publish.

### 1.5 Sheets DataOps Copilot
- **Tool**: read/modify/format/conditional/create/append/resize.
- **Funzione**: aggiornamento KPI, pulizia dati, controlli qualità, report periodici.
- **Best practice**: write batch atomiche, validazione schema range, rollback logico.

### 1.6 Slides Briefing Builder
- **Tool**: create/get/batch_update/page/thumbnail.
- **Funzione**: deck automatici da dati Sheets/Docs con outline business-ready.

### 1.7 Forms Intake Processor
- **Tool**: create/get/publish/list responses.
- **Funzione**: intake richieste (IT/HR/Finance), ingest risposte e dispatch su Tasks/Sheets.

### 1.8 Chat Ops Assistant
- **Tool**: list spaces, search, send, reactions, attachment download.
- **Funzione**: alerting operativo, escalation, digest standup automatico.

### 1.9 Personal Workload Agent (Tasks)
- **Tool**: task list + task management.
- **Funzione**: trasformare email/eventi in backlog prioritizzato con due-date e reminder.

### 1.10 CRM-lite Contact Agent
- **Tool**: contacts and contact groups.
- **Funzione**: arricchimento rubrica, dedup contatti, gruppi dinamici per campagna/progetto.

### 1.11 Workspace Script Orchestrator
- **Tool**: Apps Script project/content/run/deploy/versioning.
- **Funzione**: creare micro-automazioni custom e trigger generation governata.

### 1.12 Grounded Research Connector
- **Tool**: `search_custom` + Drive/Docs.
- **Funzione**: ricerca esterna site-scoped e consolidamento in documenti interni.

---

## 2) Best practice agentiche (ricerca online) da incorporare nel design

## 2.1 Prompting e flow design (Workspace Studio guidance)
Riferimento: supporto ufficiale Workspace Studio.

Principi utili da applicare anche alle nostre skills:
- definire trigger in modo esplicito (quando parte il flow);
- identificare persone via email (evitare ambiguita sui nomi);
- dichiarare esplicitamente le app coinvolte;
- fornire contesto operativo minimo e output atteso.

## 2.2 Governance OAuth e sicurezza
Riferimento: Google OAuth best practices.

- least privilege + incremental authorization per feature;
- storage sicuro token refresh/access; revoca e cleanup;
- PKCE + `state` anti-CSRF obbligatorio;
- gestire esplicitamente invalidazione refresh token.

## 2.3 Efficienza API e quota hygiene
Riferimenti: Gmail/Calendar/Drive docs.

- sincronizzazione incrementale (`historyId`, `nextSyncToken`);
- push notifications dove utili (watch + renew);
- exponential backoff su 403/429/5xx;
- partial response con `fields` e paginazione controllata;
- randomizzazione dei job scheduler per evitare burst.

## 2.4 Ricerca contenuti Workspace professionale
Riferimenti: Gmail filtering e Drive search docs.

- query DSL robuste (Gmail operatori, Drive `q` + corpora);
- distinzione tra ricerca per metadati e full-text;
- validazione permessi prima di azioni write/share;
- pipeline retrieval -> scoring -> sintesi con citazioni interne.

---

## 3) Estensione analisi operativa (aggiunta alle fasi A-D)

## Fase E — Full Surface Adoption (P2/P3)

### E1. Skill pack completo 12+ skills
- Implementare skill pack elencato in sezione 1 con catalogo tool dichiarato.
- Definire per ogni skill: read-only path, write path con HITL, fallback e retry.

### E2. Coverage target per dominio
- Gmail, Calendar, Drive, Docs, Sheets, Slides, Forms, Chat, Tasks, Contacts, Apps Script, Custom Search.
- Obiettivo: almeno 1 workflow production-grade per dominio.

### E3. Tool governance matrix
- Matrice centralizzata: tool -> rischio -> HITL policy -> scope richiesto -> logging required.

## Fase F — Production Intelligence Layer (P3)

### F1. Tool telemetry avanzata
- metriche per tool/domain: success, p95 latency, retry depth, error reason distribution.
- trend settimanale "invoked tools" vs "enabled tools".

### F2. Capability drift detection
- job automatico che confronta upstream tool list (repo) con mapping ARIA locale.
- alert su nuovi tool upstream non governati/skillless.

### F3. Scenario testing continuo
- regression suite multi-dominio (happy path + edge + quota + auth failures).

---

## 4) Nuovi KPI (integrazione ai KPI esistenti)

- **Upstream coverage ratio**: tool upstream governati / tool upstream totali (target >= 90%).
- **Workflow domain coverage**: domini con almeno 1 workflow live / domini totali (target 100%).
- **Scheduler workspace execution rate**: run workspace non-stub / run workspace totali (target 100%).
- **HITL policy coverage**: write tool con policy esplicita / write tool totali (target 100%).
- **Adoption depth**: numero tool distinti invocati settimanalmente (target progressivo, >= 40 entro fase E).

---

## 5) Backlog esteso (priorita aggiornata)

1. **P0**: rimuovere path scheduler stub per category `workspace` (abilitare esecuzione reale).
2. **P0**: allineare policy HITL su tutti i write tool non coperti.
3. **P1**: introdurre inventory automatico upstream->local mapping (114 tool baseline).
4. **P1**: implementare skill pack E1 in tranche (Gmail/Calendar/Drive prima, poi resto).
5. **P2**: push-based Gmail/Calendar + sync tokens persistenti.
6. **P2**: telemetry + drift detection + weekly capability report.
7. **P3**: hardening enterprise (SLO/SLA, canary, synthetic tests multi-account).

---

## Fonti usate in questo approfondimento

### Upstream repository e metadata
- `https://github.com/taylorwilsdon/google_workspace_mcp`
- `https://raw.githubusercontent.com/taylorwilsdon/google_workspace_mcp/main/manifest.json`

### Best practice Google API/Workspace
- Gmail sync: `https://developers.google.com/workspace/gmail/api/guides/sync`
- Gmail push: `https://developers.google.com/workspace/gmail/api/guides/push`
- Gmail filtering/search: `https://developers.google.com/workspace/gmail/api/guides/filtering`
- Calendar sync: `https://developers.google.com/workspace/calendar/api/guides/sync`
- Calendar freebusy reference: `https://developers.google.com/workspace/calendar/api/v3/reference/freebusy/query`
- Calendar errors/quota: `https://developers.google.com/workspace/calendar/api/guides/errors`, `https://developers.google.com/workspace/calendar/api/guides/quota`
- Drive performance/search/errors: `https://developers.google.com/drive/api/guides/performance`, `https://developers.google.com/workspace/drive/api/guides/search-files`, `https://developers.google.com/workspace/drive/api/guides/handle-errors`
- OAuth best practices: `https://developers.google.com/identity/protocols/oauth2/resources/best-practices`

### Agentic workflow guidance (Workspace)
- Workspace Studio tips: `https://support.google.com/a/users/answer/16430486?hl=en`
- Workspace Studio announcement/use-case patterns: `https://workspace.google.com/blog/product-announcements/introducing-google-workspace-studio-agents-for-everyday-work`
