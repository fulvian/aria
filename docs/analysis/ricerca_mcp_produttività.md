# Ricerca MCP Produttività — Hidden Gems su GitHub

> **Data**: 2026-04-29
> **Metodo**: github-discovery MCP + Brave Search + Context7 verification
> **Scope**: MCP server per produttività personale con agenti AI
> **Categorie**: Document Analysis, Calendar/Agenda, Task Management, Knowledge Management, Email, Microsoft 365

---

## Indice

1. [Executive Summary](#1-executive-summary)
2. [Categoria 1: Document Analysis — Word/Office/DOCX](#2-categoria-1-document-analysis--wordofficedocx)
3. [Categoria 2: Calendar & Agenda](#3-categoria-2-calendar--agenda)
4. [Categoria 3: Task Management](#4-categoria-3-task-management)
5. [Categoria 4: Knowledge Management (Obsidian, Notion)](#5-categoria-4-knowledge-management-obsidian-notion)
6. [Categoria 5: Microsoft 365 / Outlook](#6-categoria-5-microsoft-365--outlook)
7. [Categoria 6: Email (Gmail)](#7-categoria-6-email-gmail)
8. [Hidden Gems — La Classifica](#8-hidden-gems--la-classifica)
9. [Matrice Comparativa Globale](#9-matrice-comparativa-globale)
10. [Raccomandazioni per ARIA](#10-raccomandazioni-per-aria)
11. [Appendice: Contest7 Verifications](#11-appendice-context7-verifications)

---

## 1. Executive Summary

Sono stati identificati **oltre 40 MCP server** su GitHub che supportano la produttività dell'utente con agenti AI. La ricerca ha coperto 6 macro-aree, utilizzando:
- **github-discovery MCP**: 12 pool di candidati, ~300 candidati totali, screening Gate 1+2
- **Brave Search**: ricerche web mirate per gemme nascoste
- **Context7**: verifica documentazione ufficiale, API patterns, code snippets
- **Web fetch**: lettura diretta README dei repository candidati

### Risultati principali

| Categoria | Candidati | Gemme primarie | Gemme nascoste |
|-----------|-----------|----------------|----------------|
| Document Analysis | 8 | GongRzhe/Office-Word-MCP-Server, UseJunior/safe-docx | Aanerud/MCP-Microsoft-Office |
| Calendar/Agenda | 12 | nspady/google-calendar-mcp, MarimerLLC/calendar-mcp | deciduus/calendar-mcp |
| Task Management | 10 | cjo4m06/shrimp-task-manager, task-graph-mcp | Pimzino/agentic-tools-mcp |
| Knowledge Mgmt | 8 | aaronsb/obsidian-mcp-plugin | grey-iris/easy-notion-mcp |
| Microsoft 365 | 6 | softeria/ms-365-mcp-server | elyxlz/microsoft-mcp |
| Email | 4 | gongrzhe/gmail-mcp-server | shinzo-labs/gmail-mcp |

### Top 5 Hidden Gems (basso numero di stelle, altissimo valore)

1. ⭐ **grey-iris/easy-notion-mcp** — Benchmark 97.1, 92% risparmio token su Notion ufficiale
2. ⭐ **aaronsb/obsidian-mcp-plugin** — Benchmark 87.65, 8 gruppi tool semantici per Obsidian vault
3. ⭐ **oortonaut/task-graph-mcp** — Benchmark 84.4, 896 snippets, workflow strutturati per AI agents
4. ⭐ **markuspfundstein/mcp-obsidian** — Benchmark 84.2, Obsidian vault interazione via REST API
5. ⭐ **usejunior/safe-docx** — Gate 1+2 passati, editing chirurgico DOCX con tracked changes

---

## 2. Categoria 1: Document Analysis — Word/Office/DOCX

### 2.1 GongRzhe/Office-Word-MCP-Server

| Campo | Valore |
|-------|--------|
| **URL** | https://github.com/GongRzhe/Office-Word-MCP-Server |
| **Context7 ID** | `/gongrzhe/office-word-mcp-server` |
| **Code Snippets** | 95 |
| **Source Reputation** | High |
| **Benchmark Score** | 68.1 |
| **Gate 1** | ❌ (0.374, soglia 0.4) |
| **Stars** | Basse (repo recente) |

**Descrizione**: MCP server per creare, leggere e manipolare documenti Microsoft Word. Bridge tra AI assistant e documenti .docx.

**Tool disponibili**:
- `create_document` — Crea nuovo documento Word con metadati
- `add_heading` — Inserisce intestazioni con formattazione
- `add_paragraph` — Inserisce paragrafi con font/size/color/bold/italic
- `add_table` / `format_table` / `highlight_header` / `apply_alternating_rows` — Tabelle
- `insert_header_near_text` / `insert_line_or_paragraph_near_text` — Inserimento contestuale
- `insert_numbered_list_near_text` — Liste bullet/numerate
- `add_image` — Immagini con scaling proporzionale
- `add_footnote` / `add_endnote` — Note a piè di pagina
- `search_replace` — Cerca e sostituisci
- `extract_text` — Estrazione testo
- `merge_documents` — Merge multi-documento
- `convert_to_pdf` — Conversione Word → PDF
- `set_password` — Protezione password
- `add_digital_signature` — Firma digitale
- `extract_comments` / `filter_comments_by_author` — Estrazione commenti

**Installazione**: `npx -y @gongrzhe/office-word-mcp-server`

**Verdetto**: ⭐⭐⭐⭐⭐ **ESSENZIALE** per ARIA — copre il caso d'uso "leggi questo DOCX e dimmi i punti chiave" del blueprint (§1.4 item 4).

---

### 2.2 UseJunior/safe-docx

| Campo | Valore |
|-------|--------|
| **URL** | https://github.com/UseJunior/safe-docx |
| **Gate 1 Score** | 0.506 ✅ |
| **Gate 2 Score** | 0.625 ✅ |
| **Stars** | Basse (repo nuovo) |

**Descrizione**: Safe Docx Suite — editing chirurgico di file .docx esistenti con preservazione della formattazione. Ottimizzato per flussi di lavoro dove un agente propone modifiche e un umano le applica. Usato da studi legali Am Law top-10 per contratti (22M+ token processati).

**Tool MCP**:
- `read_file` — Legge documento in formato token-efficiente (formato "toon" con ID paragrafi stabili)
- `grep` — Cerca pattern nel documento
- `replace_text` — Sostituzione chirurgica con `target_paragraph_id`
- `save` — Salva output pulito + tracked changes

**Punti di forza**:
- `npx -y @usejunior/safe-docx` — zero configurazione
- TypeScript runtime, non richiede Python/LibreOffice
- Comportamento deterministico — le modifiche sono chiamate tool, non prompt LLM
- Tracciabilità: produce artefatti di revisione estraibili

**Verdetto**: ⭐⭐⭐⭐⭐ Per use-case di revisione contratti/documenti legali con AI.

---

### 2.3 Aanerud/MCP-Microsoft-Office

| Campo | Valore |
|-------|--------|
| **URL** | https://github.com/Aanerud/MCP-Microsoft-Office |
| **Stars** | Basse (repo recente) |

**Descrizione**: Singolo MCP server multi-utente per Microsoft 365 via Graph API. 117 tool in 12 moduli.

**Tool disponibili (12 moduli)**: Mail, Calendar, Files, **Excel**, **Word**, **PowerPoint**, Teams, Contacts, To-Do, Groups, People, Search.

**Punti di forza**:
- Multi-utente: supporta un intero team con dati isolati
- 18 permessi Microsoft Graph delegati
- **Word**, **Excel**, **PowerPoint** tools nativi
- Token cifrati a riposo

**Installazione**: Server Node.js + MCP Adapter locale.

**Verdetto**: ⭐⭐⭐⭐ Per scenario Office 365 completo, ma richiede tenant Microsoft.

---

### 2.4 altri candidati

| Repository | Note |
|------------|------|
| `as7722314/mcp-office-parser` | Office parser MCP (scoperto in pool) |
| `gamemaker1/office-text-extractor` | Estrazione testo da Office |
| `m87shaonv/word_mcp` | 42 snippets, Benchmark 77.3, alternativa leggera |

---

## 3. Categoria 2: Calendar & Agenda

### 3.1 nspady/google-calendar-mcp

| Campo | Valore |
|-------|--------|
| **URL** | https://github.com/nspady/google-calendar-mcp |
| **Context7 ID** | `/nspady/google-calendar-mcp` |
| **Code Snippets** | 18 |
| **Gate 1 Score** | 0.462 ✅ |

**Descrizione**: MCP server per Google Calendar con multi-account, eventi ricorrenti, scheduling intelligente.

**Caratteristiche**:
- Multi-account: collega account lavoro + personale simultaneamente
- Multi-calendario: eventi da più calendari in una richiesta
- Cross-account conflict detection
- Event management: create, update, delete, search
- Recurring events: modifica avanzata eventi ricorrenti
- Free/busy queries: disponibilità su più calendari
- Smart scheduling: comprensione linguaggio naturale per date
- Intelligent Import: aggiungi eventi da immagini, PDF, web link

**Installazione**: `npx @cocal/google-calendar-mcp`

**Verdetto**: ⭐⭐⭐⭐⭐ **BEST IN CLASS** per Google Calendar — multi-account, conflitti cross-calendario, import intelligente.

---

### 3.2 MarimerLLC/calendar-mcp

| Campo | Valore |
|-------|--------|
| **URL** | https://github.com/MarimerLLC/calendar-mcp |
| **Stars** | Basse (nuovo, ma solido) |

**Descrizione**: Server MCP unificato per email, calendario e contatti multi-provider.

**Provider supportati**:
| Provider | Email | Calendar | Contacts | Auth |
|----------|:-----:|:--------:|:--------:|------|
| Microsoft 365 | ✅ | ✅ | ✅ | OAuth MSAL |
| Outlook.com | ✅ | ✅ | ✅ | OAuth MSAL |
| Google/Gmail | ✅ | ✅ | ✅ | OAuth 2.0 |
| IMAP/SMTP | ✅ | — | — | Password |
| ICS Feeds | — | ✅ (RO) | — | Public |
| JSON Calendar | — | ✅ (RO) | — | File locali |

**Tool MCP**: list_accounts, get_emails, search_emails, send_email, list_calendars, get_calendar_events, find_available_times, create_event, delete_event, respond_to_event, get_contacts, search_contacts, create_contact, update_contact, delete_contact.

**Installazione**: Binari precompilati per Win/Mac/Linux (self-contained, no .NET runtime needed).

**Verdetto**: ⭐⭐⭐⭐⭐ **GIOIELLO NASCOSTO** — unico server MCP che unifica M365 + Google + Outlook.com in un solo tool.

---

### 3.3 Altri calendari

| Repository | Note |
|------------|------|
| `guinacio/mcp-google-calendar` | Python, Google Calendar + workspace completo |
| `deciduus/calendar-mcp` | **Python**, analisi busyness, scheduling mutuo, free/busy |
| `merajmehrabi/Outlook_Calendar_MCP` | Outlook locale (Windows-only, VBScript) |
| `pashpashpash/google-calendar-mcp` | 93 snippets, High reputation |
| `am2rican5/mcp-google-calendar` | 37 snippets, Benchmark 67.4 |
| `piotr-agier/google-drive-mcp` | **211 snippets** — Drive + Calendar + Docs + Sheets |
| `RossiFire/mcp-google-calendar` | Da awesome-list |
| `gongrzhe/server-calendar-autoauth-mcp` | Calendar auto auth |

---

## 4. Categoria 3: Task Management

### 4.1 cjo4m06/mcp-shrimp-task-manager 🦐

| Campo | Valore |
|-------|--------|
| **URL** | https://github.com/cjo4m06/mcp-shrimp-task-manager |
| **Context7 ID** | `/cjo4m06/mcp-shrimp-task-manager` |
| **Code Snippets** | 488 |
| **Reputation** | Medium |
| **Benchmark Score** | 73.7 |
| **Stars** | Crescita rapida |

**Descrizione**: Intelligent task management per AI agents. Converte linguaggio naturale in task strutturati con dependency tracking e raffinamento iterativo.

**Tool MCP**:
- `plan_task` — Analisi approfondita requisiti prima dell'implementazione
- `execute_task` — Esecuzione guidata step-by-step
- `list_tasks` — Visualizzazione stato task
- `delete_task` / `complete_task` / `update_task`
- `research_mode` — Esplorazione sistematica
- `agent_system` — Assegna agenti specializzati a task specifici
- Task Memory: backup/restore automatico cronologia task

**Punti di forza**:
- Memoria persistente tra sessioni
- Decomposizione intelligente in subtask atomici
- Dependency tracking automatico
- Web UI React per gestione visuale (drag-and-drop)
- Supporto multilingua (10 lingue)

**Installazione**: `git clone + npm install + npm run build`

**Verdetto**: ⭐⭐⭐⭐⭐ **BEST IN CLASS per AI agents** — specificamente progettato per agenti AI, non per umani.

---

### 4.2 oortonaut/task-graph-mcp

| Campo | Valore |
|-------|--------|
| **URL** | https://github.com/oortonaut/task-graph-mcp |
| **Context7 ID** | `/oortonaut/task-graph-mcp` |
| **Code Snippets** | 896 |
| **Benchmark Score** | **84.4** |
| **Stars** | Basse (HIDDEN GEM) |

**Descrizione**: Framework per workflow strutturati di AI agent con fasi, prompt automatici e quality gates.

**Tool MCP CRUD**:
| Tool | Scopo | Parametri chiave |
|------|-------|------------------|
| `create` | Crea task singolo | title, description, parent, priority, blocked_by |
| `create_tree` | Struttura nidificata | tree, parent, child_type |
| `get` | Recupera task | task, children, format |
| `list_tasks` | Query task | status, ready, blocked, owner, parent |
| `update` | Modifica task + stato | worker_id, task, state, phase |
| `delete` | Rimuovi task | task, cascade |
| `claim` | Assegna task a worker | worker_id, task |
| `connect` | Registra agente | worker_id, tags, workflow, overlays |
| `thinking` | Condivide progresso | agent, thought |
| `check_gates` | Verifica quality gates | task |
| `attach` | Allega evidenza | task, type, content |

**Fasi workflow**: explore → implement → review → test → deploy

**Punti di forza**:
- Multi-agente: più agenti collaborano sullo stesso workflow
- Quality gates: condizioni verificabili prima di avanzare fase
- Overlay system: git, troubleshooting, ecc.
- Stato persistente SQLite

**Verdetto**: ⭐⭐⭐⭐⭐ **GIOIELLO NASCOSTO** — perfetto per orchestrazione multi-agente con quality gates.

---

### 4.3 Pimzino/agentic-tools-mcp

| Campo | Valore |
|-------|--------|
| **URL** | https://github.com/Pimzino/agentic-tools-mcp |
| **npm** | `@pimzino/agentic-tools-mcp` |

**Descrizione**: Task management avanzato + agent memories con gerarchia illimitata.

**Tool MCP**:
- **Project**: list_projects, create_project, get_project, update_project, delete_project
- **Task (gerarchia illimitata)**: list_tasks (albero), add_task, update_task_status
- **Memories**: store_memory, search_memories (scoring: 60% titolo, 30% contenuto, 20% categoria)

**Punti di forza**:
- Gerarchia task infinita (tasks → subtasks → sub-subtasks → ...)
- Priority 1-10, complexity estimation, time tracking
- Project-specific storage (git-trackable JSON)
- Agent memories con ranking avanzato
- VS Code Extension companion

**Verdetto**: ⭐⭐⭐⭐ Ottimo per task management ibrido umano+AI, con memories persistenti.

---

### 4.4 Altri task manager

| Repository | Note |
|------------|------|
| `tradesdontlie/task-manager-mcp` | Python, PRD parsing, complexity estimation, subtask expansion |
| `liao1fan/schedule-task-mcp` | **npm**, schedulazione cron/interval/date, SQLite persistenza |
| `greirson/mcp-todoist` | Gate 1+2 passato ✅, integrazione Todoist |
| `flesler/mcp-tasks` | Markdown/JSON/YAML, LLM budget efficient |
| `bsmi021/mcp-task-manager-server` | SQLite, import/export |
| `dream-star-end/task-manager-mcp` | Subtask expansion, LLM-driven |
| `gpayer/mcp-task-manager` | Go-based, leggero |

---

## 5. Categoria 4: Knowledge Management (Obsidian, Notion)

### 5.1 aaronsb/obsidian-mcp-plugin

| Campo | Valore |
|-------|--------|
| **URL** | https://github.com/aaronsb/obsidian-mcp-plugin |
| **Context7 ID** | `/aaronsb/obsidian-mcp-plugin` |
| **Code Snippets** | **382** |
| **Source Reputation** | High |
| **Benchmark Score** | **87.65** |
| **Stars** | Medie (HIDDEN GEM) |

**Descrizione**: Plugin Obsidian che connette il vault agli AI assistant via MCP. Espone 8 gruppi di tool semantici.

**8 Gruppi Tool**:
1. **vault** — Operazioni sul vault (list, search, read)
2. **edit** — Creazione/modifica note
3. **view** — Visualizzazione note
4. **graph** — Grafo delle connessioni: `neighbors`, `traverse`, `path`, `backlinks`, `forwardlinks`, `tag_traverse`, `tag_analysis`, `shared_tags`, `statistics`
5. **workflow** — Flussi di lavoro
6. **dataview** — Query Dataview
7. **bases** — Database-like views (formule, template, export, custom views)
8. **system** — Stato sistema

**Punti di forza**:
- **Navigazione semantica del grafo** — trova percorsi tra note, analisi tag, traversali beam-search
- Connessione pooling per sessioni concorrenti
- API key authentication + path validation
- HTTP/HTTPS server embedded in Obsidian

**Installazione**: Plugin Obsidian (Community), poi configura MCP client → `http://localhost:3001/mcp`

**Verdetto**: ⭐⭐⭐⭐⭐ **ESSENZIALE** per chi usa Obsidian — trasforma il vault in un grafo di conoscenza navigabile dagli AI agent.

---

### 5.2 grey-iris/easy-notion-mcp

| Campo | Valore |
|-------|--------|
| **URL** | https://github.com/grey-iris/easy-notion-mcp |
| **Context7 ID** | `/grey-iris/easy-notion-mcp` |
| **Code Snippets** | 132 |
| **Benchmark Score** | **97.1** 🏆 |
| **Stars** | Basse (MEGA HIDDEN GEM) |

**Descrizione**: MCP server markdown-first per Notion. **92% risparmio token** rispetto al server ufficiale Notion MCP.

**26 Tool in 5 categorie**:
- **Pages**: `create_page`, `read_page`, `update_page`, `delete_page`
- **Navigation**: `search`, `list_pages`, `get_page_property`
- **Databases**: `query_database`, `create_database`, `update_database`
- **Comments**: `get_comments`, `create_comment`
- **Users**: `list_users`, `get_user`

**Punti di forza**:
- Markdown GFM bidirezionale invece di JSON verboso Notion
- Supporta 25 block types: toggle, columns, callouts, tables, equations, file uploads
- Schema detection automatico per database
- Prompt injection defense built-in
- HTTP transport con OAuth browser flow
- Full round-trip fidelity

**Installazione**: `npx easy-notion-mcp-http`

**Verdetto**: ⭐⭐⭐⭐⭐ **MIGLIOR MCP PER NOTION** — 97.1 benchmark, 92% token savings, supera l'ufficiale.

---

### 5.3 Altri Knowledge Management

| Repository | Note |
|------------|------|
| `makenotion/notion-mcp-server` | 91 snippets, Benchmark 61.7, UFFICIALE |
| `markuspfundstein/mcp-obsidian` | **Benchmark 84.2**, 55 snippets, Obsidian via REST API |
| `cyanheads/obsidian-mcp-server` | 29 snippets, High reputation |
| `stevenstavrakis/obsidian-mcp` | 31 snippets, High reputation |
| `originalbyteme/the-obsidian-brain-mcp` | 165 snippets, Benchmark 68.2 |
| `umair-ds92/notion-mcp-agent` | 50 snippets, Benchmark 73.2, AutoGen-based |

---

## 6. Categoria 5: Microsoft 365 / Outlook

### 6.1 softeria/ms-365-mcp-server

| Campo | Valore |
|-------|--------|
| **URL** | https://github.com/Softeria/ms-365-mcp-server |
| **npm** | `@softeria/ms-365-mcp-server` |

**Descrizione**: **200+ tool** che coprono la superficie Microsoft Graph API. Ogni tool mappa 1-to-1 a un endpoint Graph.

**Aree**: Email (Outlook), Calendar, OneDrive Files, **Excel**, **OneNote**, **To Do Tasks**, **Planner**, Contacts, User Profile, Search.

**Installazione**: `npx -y @softeria/ms-365-mcp-server --toon`

**Verdetto**: ⭐⭐⭐⭐ Il più completo per Microsoft 365, 200+ tool.

---

### 6.2 Altri M365

| Repository | Tool | Note |
|------------|------|------|
| `Aanerud/MCP-Microsoft-Office` | 117 | Già analizzato in §2.3 — multi-utente M365 |
| `eesb99/office365-mcp-server` | 45 | Email, Calendar, Files, Contacts, Teams, Tasks |
| `hvkshetry/office-365-mcp-server` | 24 | 24 tool consolidati |
| `elyxlz/microsoft-mcp` | — | Minimal, potente: Outlook, Calendar, OneDrive |
| `XenoXilus/outlook-mcp` | — | Outlook + Calendar + SharePoint |
| `AojdevStudio/microsoft-mcp` | — | Multi-account Microsoft Graph |

---

## 7. Categoria 6: Email (Gmail)

### 7.1 gongrzhe/gmail-mcp-server

| Campo | Valore |
|-------|--------|
| **Context7 ID** | `/gongrzhe/gmail-mcp-server` |
| **Code Snippets** | 48 |
| **Source Reputation** | High |
| **Benchmark Score** | 58.7 |

**Descrizione**: MCP server per Gmail con auto-authentication. Permette agli AI assistant di gestire Gmail in linguaggio naturale.

**Verdetto**: ⭐⭐⭐⭐ Buona integrazione Gmail, auto-auth semplifica setup.

---

### 7.2 shinzo-labs/gmail-mcp

| Campo | Valore |
|-------|--------|
| **Context7 ID** | `/shinzo-labs/gmail-mcp` |
| **Code Snippets** | 83 |
| **Source Reputation** | High |
| **Benchmark Score** | 59.63 |

**Descrizione**: Implementazione completa MCP per Gmail API con email management, invio, recupero, label management, configurazioni.

**Verdetto**: ⭐⭐⭐⭐ Più snippet e più completo di gongrzhe.

---

## 8. Hidden Gems — La Classifica

### Classifica per Benchmark Score (Context7)

| # | Repository | Benchmark | Snippets | Categoria |
|---|------------|-----------|----------|-----------|
| 1 | **grey-iris/easy-notion-mcp** | **97.1** 🏆 | 132 | Knowledge Mgmt |
| 2 | **aaronsb/obsidian-mcp-plugin** | **87.65** | **382** | Knowledge Mgmt |
| 3 | **oortonaut/task-graph-mcp** | **84.4** | **896** | Task Mgmt |
| 4 | **markuspfundstein/mcp-obsidian** | **84.2** | 55 | Knowledge Mgmt |
| 5 | **m87shaonv/word_mcp** | **77.3** | 42 | Document Analysis |
| 6 | **cjo4m06/mcp-shrimp-task-manager** | **73.7** | 488 | Task Mgmt |
| 7 | **gongrzhe/office-word-mcp-server** | **68.1** | 95 | Document Analysis |

### Classifica Hidden Gems (basse stelle, alto valore)

| # | Repository | Perché è nascosta |
|---|------------|-------------------|
| 1 | **grey-iris/easy-notion-mcp** | Benchmark 97.1, pochissime stelle, supera l'ufficiale Notion |
| 2 | **oortonaut/task-graph-mcp** | 896 snippets, 84.4 benchmark, framework multi-agente completo |
| 3 | **UseJunior/safe-docx** | Gate 1+2 passati, usato da studi legali Am Law |
| 4 | **Pimzino/agentic-tools-mcp** | Task + memories + gerarchia illimitata, VS Code companion |
| 5 | **liao1fan/schedule-task-mcp** | Schedulazione cron/interval, sampling-aware, SQLite |
| 6 | **MarimerLLC/calendar-mcp** | Unico MCP unificato M365+Google, binari precompilati |
| 7 | **deciduus/calendar-mcp** | Analisi busyness, scheduling mutuo automatico |

---

## 9. Matrice Comparativa Globale

| MCP Server | Categoria | Keyless? | OAuth? | Install | Tool Count | Benchmark | Valutazione |
|------------|-----------|:--------:|:------:|---------|:----------:|:---------:|:-----------:|
| Office-Word-MCP | Document | ❌ | ❌ | npx | 25+ | 68.1 | ⭐⭐⭐⭐⭐ |
| safe-docx | Document | ✅ | ❌ | npx | 5 | Gate 1+2 | ⭐⭐⭐⭐⭐ |
| MCP-Microsoft-Office | Document | ❌ | ✅ M365 | Node.js | **117** | — | ⭐⭐⭐⭐ |
| google-calendar-mcp (nspady) | Calendar | ❌ | ✅ Google | npx | 10+ | Gate 1 | ⭐⭐⭐⭐⭐ |
| calendar-mcp (Marimer) | Calendar | ❌ | ✅ Multi | Binary | **20+** | — | ⭐⭐⭐⭐⭐ |
| Outlook_Calendar_MCP | Calendar | ❌ | ✅ Local | npm | 5+ | — | ⭐⭐⭐ |
| shrimp-task-manager | Task | ✅ | ❌ | Node.js | 10+ | **73.7** | ⭐⭐⭐⭐⭐ |
| task-graph-mcp | Task | ✅ | ❌ | Node.js | 15+ | **84.4** | ⭐⭐⭐⭐⭐ |
| agentic-tools-mcp | Task | ✅ | ❌ | npm | 15+ | — | ⭐⭐⭐⭐ |
| schedule-task-mcp | Task | ✅ | ❌ | npm | 6 | — | ⭐⭐⭐⭐ |
| obsidian-mcp-plugin | Knowledge | ✅ | ❌ | Plugin | **8 gruppi** | **87.65** | ⭐⭐⭐⭐⭐ |
| easy-notion-mcp | Knowledge | ❌ | ✅ OAuth | npx | **26** | **97.1** | ⭐⭐⭐⭐⭐ |
| gmail-mcp-server | Email | ❌ | ✅ Google | npx | 10+ | 58.7 | ⭐⭐⭐⭐ |
| ms-365-mcp-server | M365 | ❌ | ✅ M365 | npx | **200+** | — | ⭐⭐⭐⭐ |

---

## 10. Raccomandazioni per ARIA

Basate sul blueprint ARIA (§1.4 — casi d'uso fondativi MVP) e sul principio P8 (Tool Priority Ladder: MCP > skill > script locale):

### Priorità 1 — Document Analysis (caso d'uso MVP #4)
> "ARIA, leggi questo PDF/DOCX e dimmi i punti chiave"

**Raccomandazione**: Integrare **GongRzhe/Office-Word-MCP-Server** per lettura/analisi documenti Word. Abbinare **UseJunior/safe-docx** per editing chirurgico con tracked changes.

Config MCP:
```json
{
  "office-word-mcp": {
    "command": "npx",
    "args": ["-y", "@gongrzhe/office-word-mcp-server"]
  },
  "safe-docx": {
    "command": "npx",
    "args": ["-y", "@usejunior/safe-docx"]
  }
}
```

### Priorità 2 — Calendar Management (caso d'uso MVP #3)
> "ARIA, pianifica una call di 30min con Mario la prossima settimana"

**Raccomandazione**: Sostituire/integrare l'attuale `google_workspace_mcp` con **nspady/google-calendar-mcp** per funzionalità calendario avanzate (multi-account, conflitti cross-calendario). Oppure **MarimerLLC/calendar-mcp** per unificare M365 + Google.

### Priorità 3 — Task Management (estensione MVP)
> "ARIA, gestisci i miei task e promemoria"

**Raccomandazione**: **cjo4m06/mcp-shrimp-task-manager** per task management AI-native con decomposizione automatica. **liao1fan/schedule-task-mcp** per schedulazione reminder con trigger cron/interval.

### Priorità 4 — Knowledge Management (estensione MVP)
> "ARIA, cerca nelle mie note Obsidian/Notion"

**Raccomandazione**: **aaronsb/obsidian-mcp-plugin** (se si usa Obsidian) con navigazione semantica del grafo. **grey-iris/easy-notion-mcp** (se si usa Notion) con 92% risparmio token.

### Priorità 5 — Email Triage (caso d'uso MVP #2)
> "ARIA, leggimi la posta e riassumi"

**Raccomandazione**: **gongrzhe/gmail-mcp-server** o **shinzo-labs/gmail-mcp** per triage email.

### Costo stimato integrazione
Tutti gli MCP sopra sono **gratuiti** (open source MIT). Il costo è solo:
- API key Google Cloud (calendario/email) — già presenti in ARIA
- API key Notion (se si usa Notion) — gratuita
- Obsidian vault locale — gratuito

---

## 11. Appendice: Context7 Verifications

| Provider | Context7 ID | Snippets | Benchmark | Verified |
|----------|-------------|:--------:|:---------:|:--------:|
| Office Word | `/gongrzhe/office-word-mcp-server` | 95 | 68.1 | ✅ |
| Word MCP | `/m87shaonv/word_mcp` | 42 | 77.3 | ✅ |
| Shrimp Task | `/cjo4m06/mcp-shrimp-task-manager` | 488 | 73.7 | ✅ |
| Task Graph | `/oortonaut/task-graph-mcp` | 896 | **84.4** | ✅ |
| Google Calendar (nspady) | `/nspady/google-calendar-mcp` | 18 | — | ✅ |
| Google Calendar (pash) | `/pashpashpash/google-calendar-mcp` | 93 | — | ✅ |
| Google Calendar (am2rican5) | `/am2rican5/mcp-google-calendar` | 37 | 67.4 | ✅ |
| Google Drive+Calendar | `/piotr-agier/google-drive-mcp` | 211 | 65.94 | ✅ |
| Obsidian Plugin | `/aaronsb/obsidian-mcp-plugin` | **382** | **87.65** | ✅ |
| Obsidian (pfundstein) | `/markuspfundstein/mcp-obsidian` | 55 | **84.2** | ✅ |
| Obsidian Brain | `/originalbyteme/the-obsidian-brain-mcp` | 165 | 68.2 | ✅ |
| Easy Notion | `/grey-iris/easy-notion-mcp` | 132 | **97.1** 🏆 | ✅ |
| Notion Official | `/makenotion/notion-mcp-server` | 91 | 61.7 | ✅ |
| Gmail (gongrzhe) | `/gongrzhe/gmail-mcp-server` | 48 | 58.7 | ✅ |
| Gmail (shinzo) | `/shinzo-labs/gmail-mcp` | 83 | 59.63 | ✅ |

---

*Report generato il 2026-04-29T17:58+02:00 tramite github-discovery MCP + Brave Search + Context7*
