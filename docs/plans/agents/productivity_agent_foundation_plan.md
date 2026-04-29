# Productivity-Agent — Foundation Plan (piano implementazione approvato)

```yaml
status: APPROVED — pronto per implementazione (post Open Questions Draft 2)
author: aria-conductor (sessione fulvio)
created: 2026-04-29
language: IT
audience: fulvio + agent implementatori
supersedes: docs/plans/agents/productivity_agent_plan_draf_1.md (DRAFT-2)
input-decisions: Open Questions §10 Draft 2 — risposte utente acquisite 2026-04-29
related-blueprint-sections:
  - "§8.3 Sub-agenti OPERATIVI (MVP)"
  - "§8.5 Capability matrix"
  - "§8.6 Child sessions isolate"
  - "§9 Skills Layer"
  - "§10 Tools & MCP Ecosystem"
  - "§12 Sub-Agent Google Workspace"
  - "§15 Roadmap"
  - "§16 Ten Commandments"
related-adrs:
  - "ADR-0006-research-agent-academic-social-expansion.md (template P10)"
new-adrs:
  - "ADR-0008-productivity-agent-introduction.md (da redigere in Step 0)"
research-sources:
  - "Microsoft MarkItDown — Context7 /microsoft/markitdown Bench 90.05"
  - "Anthropic Agent Skills overview (reference SKILL.md pattern)"
implementation-branch: feature/productivity-agent-mvp
estimated-effort: 1 settimana Fase 1a (Sprint 1) + 1-2 settimane Fase 1b (Sprint 2)
```

---

## 0. Decisioni utente acquisite (Open Questions Draft 2)

| # | Domanda | Risposta utente | Effetto sul piano |
|---|---------|-----------------|-------------------|
| Q1 | Boundary vs workspace-agent | **Sì — Opzione B** (delega) | Architettura confermata |
| Q2 | Scope Fase 1a (3 skill) | **Sì** — office-ingest + consultancy-brief + meeting-prep | Sprint 1 |
| Q3 | PDF complessi (OCR/scansioni) | **No** | Niente docling, niente markitdown-ocr |
| Q4 | Deliverable output locale (DOCX/PPTX/XLSX) | **Solo via Google Workspace, mai in locale** | Fase 2 `deliverable-agent` cambia: deleghi a workspace-agent (Drive/Docs/Sheets/Slides) — niente python-docx/pptx/openpyxl |
| Q5 | OCR su immagini | **No** | Niente OPENAI_API_KEY per markitdown-ocr |
| Q6 | Audio meeting STT | **No** | meeting-transcribe-agent rimosso da roadmap |
| Q7 | email-draft Fase 1b | **Sì, ma con stile dinamico** — il sistema cerca conversazioni precedenti con stesso interlocutore via google_workspace, ricostruisce contesto + stile, si adatta runtime per-thread | **Architettura email-draft riprogettata**: niente lesson `email-style-fulvio` statica, niente bootstrap utente. Il tono è derivato runtime dal thread/recipient |
| Q8 | HITL canale | **REPL locale** (non Telegram) | `hitl-queue/ask` configurato con prompter locale (no Telegram inline keyboard per productivity-agent) |
| Q9 | Multi-cliente auto-tagging | **No** | Pagine wiki `client-<slug>` create solo on-demand (esplicita richiesta utente), non discovery proattivo |
| Q10 | Naming agente | **`productivity-agent`** | Confermato |
| Q11 | Knowledge base esterna (Obsidian/Notion) | **Nessuna** | Niente obsidian-mcp-plugin, niente easy-notion-mcp |
| Q12 | Microsoft 365 / Outlook | **Rinviato** | Niente ms-365-mcp; eventuale futuro ADR-0009 separato fuori scope |
| Q13 | Tracked-changes contratti DOCX | **No** | Niente safe-docx, niente skill `contract-review` |

### Implicazioni nette

- **Solo 1 MCP nuovo**: `markitdown-mcp` (Microsoft, MIT, Context7 90.05).
- **4 skill totali**: `office-ingest@2.0.0`, `consultancy-brief@1.0.0`, `meeting-prep@1.0.0` (Sprint 1), `email-draft@1.0.0` con dynamic style (Sprint 2).
- **Tool budget productivity-agent**: 11 tool su limite 20 (P9 ampiamente rispettato; nessun opt-in attivato).
- **Fase 2 ridefinita**: `deliverable-agent` futuro userà solo Google Workspace API via delega, niente librerie Python office locali.
- **HITL**: prompter REPL locale tramite `hitl-queue/ask`.

---

## 1. Scope finale

### 1.1 Sprint 1 (Fase 1a — 1 settimana)

3 skill nuove + 1 MCP nuovo + 1 sub-agente nuovo.

| Deliverable | Path | Stato |
|-------------|------|-------|
| MCP server config | `.aria/kilocode/mcp.json` (entry `markitdown-mcp`) | Nuovo |
| MCP wrapper (opzionale) | `scripts/wrappers/markitdown-wrapper.sh` | Nuovo se serve env override |
| Agent definition | `.aria/kilocode/agents/productivity-agent.md` | Nuovo |
| Skill: office-ingest | `.aria/kilocode/skills/office-ingest/SKILL.md` | Nuova (deprecates `pdf-extract@1.0.0`) |
| Skill: consultancy-brief | `.aria/kilocode/skills/consultancy-brief/SKILL.md` | Nuova |
| Skill: meeting-prep | `.aria/kilocode/skills/meeting-prep/SKILL.md` | Nuova |
| Python helper | `src/aria/agents/productivity/__init__.py` | Nuovo |
| Python helper | `src/aria/agents/productivity/ingest.py` | Nuovo |
| Python helper | `src/aria/agents/productivity/synthesizer.py` | Nuovo |
| Python helper | `src/aria/agents/productivity/meeting_prep.py` | Nuovo |
| Test suite | `tests/unit/agents/productivity/` | Nuovo |
| Test suite | `tests/integration/productivity/` | Nuovo |
| Test fixtures | `tests/fixtures/office_files/` (PDF/DOCX/XLSX/PPTX/TXT samples) | Nuovo |
| Skill registry | `.aria/kilocode/skills/_registry.json` | Update (registra 3 skill nuove + flag deprecation `pdf-extract`) |
| Conductor delega | `.aria/kilocode/agents/aria-conductor.md` | Update (aggiunge productivity-agent ai sub-agenti disponibili) |
| ADR | `docs/foundation/decisions/ADR-0008-productivity-agent-introduction.md` | Nuovo |
| Blueprint update | `docs/foundation/aria_foundation_blueprint.md` | Update §8.3.3, §8.5, §9.5, §15 |
| Wiki page | `docs/llm_wiki/wiki/productivity-agent.md` | Nuova |
| Wiki index | `docs/llm_wiki/wiki/index.md` | Update |
| Wiki log | `docs/llm_wiki/wiki/log.md` | Append |

### 1.2 Sprint 2 (Fase 1b — 1-2 settimane)

1 skill aggiuntiva con architettura dynamic-style.

| Deliverable | Path | Stato |
|-------------|------|-------|
| Skill: email-draft | `.aria/kilocode/skills/email-draft/SKILL.md` | Nuova |
| Python helper | `src/aria/agents/productivity/email_style.py` | Nuovo (dynamic style analyzer) |
| Test suite | `tests/unit/agents/productivity/test_email_style.py` | Nuovo |
| Test integration | `tests/integration/productivity/test_email_draft_e2e.py` | Nuovo (mock workspace-agent) |
| Skill registry | `.aria/kilocode/skills/_registry.json` | Update |
| ProductivityAgent allowed-tools | `.aria/kilocode/agents/productivity-agent.md` | Update (registra skill) |

### 1.3 Out of scope (rinviato a Fase 2 dietro nuovi ADR)

- `deliverable-draft` — generazione documenti (solo via Google Workspace; richiederà `deliverable-agent` o estensione di `workspace-agent`)
- `contract-review` (Q13 = no)
- `meeting-transcribe` (Q6 = no)
- ms-365 / Outlook (Q12 = rinviato)
- Obsidian / Notion knowledge base (Q11 = nessuna)

---

## 2. Architettura definitiva

### 2.1 Boundary

```
utente
  └─→ aria-conductor (Kilo primary)
       ├─→ search-agent           (web, social, academic)
       ├─→ workspace-agent        (Google Workspace API low-level)
       └─→ productivity-agent     (NUOVO — workflow consulente)
              ├─ markitdown-mcp   (ingestion office files locali)
              ├─ aria-memory      (wiki recall + update)
              ├─ filesystem       (read documenti locali)
              ├─ fetch            (URL pubblici nei documenti)
              ├─ hitl-queue/ask   (REPL locale — Q8)
              └─ delega → workspace-agent (gmail.*/calendar.*/drive.*)
```

### 2.2 Pattern delega 2-hop

```
productivity-agent (child session di Conductor)
   ↓ esempio: meeting-prep
   ↓ avvia child session ulteriore di workspace-agent (via Conductor)
   workspace-agent
     ↓ chiama gmail.search
     ↓ chiama calendar.list_events
     ↓ chiama drive.search
   ← restituisce JSON serializzato a productivity-agent
   ↓ productivity-agent compone brief con office-ingest + consultancy-brief
   ← restituisce a Conductor
Conductor → utente
```

Pattern allineato a §8.6 blueprint (child sessions isolate, transcript salvato in `sessions/children/<id>.json`, output JSON `{status, result, tokens_used, tools_invoked[]}`, timeout default 10min).

### 2.3 Productivity-agent definition

```markdown
---
name: productivity-agent
type: subagent
description: Workflow consulente — ingestion office files, briefing multi-doc, meeting prep, email drafting con stile dinamico
color: "#7C3AED"
category: productivity
temperature: 0.2
allowed-tools:
  - markitdown-mcp/convert_to_markdown
  - filesystem/read
  - filesystem/list_directory
  - aria-memory/wiki_update_tool
  - aria-memory/wiki_recall_tool
  - aria-memory/wiki_show_tool
  - aria-memory/wiki_list_tool
  - hitl-queue/ask
  - fetch/fetch
  - sequential-thinking/*
  - spawn-subagent           # delega workspace-agent (KiloCode child session)
required-skills:
  - office-ingest
  - consultancy-brief
  - meeting-prep
  - email-draft               # disponibile post Sprint 2
  - planning-with-files       # esistente, riusato
mcp-dependencies: [markitdown-mcp, aria-memory, filesystem]
---

# Productivity-Agent

Workflow consulente: leggi/sintetizza file office locali (PDF/DOCX/XLSX/PPTX/TXT/HTML),
componi briefing multi-documento, prepara meeting da eventi calendario, drafta email
con stile dinamico per-recipient.

## Boundary
- NON tocca direttamente Gmail/Calendar/Drive — delega a `workspace-agent` via spawn-subagent.
- NON crea documenti DOCX/PPTX/XLSX in locale — eventuale generazione passa da workspace-agent
  (Google Drive/Docs/Sheets/Slides).

## HITL
Tutte le azioni con effetti laterali (send mail via workspace-agent, scrittura wiki
con `decision`/`lesson` immutable, write Drive) → `hitl-queue/ask` su REPL locale.

## Memoria contestuale
Inizio turno: chiama `wiki_recall_tool(query=<input utente>)` per recuperare
profilo + topic ricorrenti.
Fine turno: `wiki_update_tool` con patches (entity client/project se utente lo cita esplicitamente; topic meeting/<date>; lesson solo se l'utente fornisce una regola esplicita).
Default `no_salience_reason="tool_only"` se la sessione è solo ingestion + risposta.
```

---

## 3. Stack tecnologico

### 3.1 Nuovo MCP: markitdown-mcp

| Campo | Valore |
|-------|--------|
| Repo | https://github.com/microsoft/markitdown |
| Context7 ID | `/microsoft/markitdown` (Bench 90.05) |
| License | MIT |
| Versione target | v0.1.5 (feb 2026) o successiva |
| Install | `pip install 'markitdown[all]'` (in `.venv`) o `uvx markitdown-mcp` |
| Tool esposto | `convert_to_markdown(uri)` — accetta `http:`, `https:`, `file:`, `data:` URIs |
| Formati | PDF, DOCX, XLSX, XLS, PPTX, HTML, audio (WAV/MP3 — non usato), Outlook .msg, immagini, ZIP, YouTube |
| Plugin OCR | DISABILITATO (Q5 = no) |
| Network | Local-only (eccezione: `https://` URIs richiamati esplicitamente) |
| Credentials | Nessuna |

### 3.2 Configurazione `mcp.json` (entry da aggiungere)

```json
"markitdown-mcp": {
  "command": "uvx",
  "args": ["markitdown-mcp"],
  "disabled": false,
  "_comment": "@productivity-mvp Microsoft markitdown — formati office → markdown LLM-ready"
}
```

Wrapper SOPS **non necessario** (no API key). Se in futuro emergesse bisogno
di `OPENAI_API_KEY` per OCR, si aggiungerà wrapper standard come `tavily-wrapper.sh`.

### 3.3 Dipendenze Python (pyproject.toml)

```toml
# Già presenti, riusati
# - pydantic
# - mcp / fastmcp (per skill nested via aria-memory)

# Nuove dipendenze produttività (solo se serve fallback Python locale)
# Nessuna in Sprint 1 — markitdown-mcp è esterno (uvx).
# Eventuali in Sprint 2 (email-draft):
# - python-dateutil (parsing datetime email headers)  # già presente
```

Verifica pre-implementazione: `uvx markitdown-mcp --help` deve rispondere
con la lista tool. Se fallisce, fallback `pip install markitdown[all]` in
`.venv` ARIA + invocazione via `python -m markitdown.mcp`.

---

## 4. Spec skill — versioni implementabili

### 4.1 `office-ingest@2.0.0`

**Path**: `.aria/kilocode/skills/office-ingest/SKILL.md`

```markdown
---
name: office-ingest
version: 2.0.0
description: Estrae testo, tabelle e metadata da PDF/DOCX/XLSX/PPTX/TXT/HTML/CSV in markdown LLM-ready. Sostituisce pdf-extract@1.0.0 con copertura formati estesa via markitdown-mcp.
trigger-keywords:
  - pdf
  - word
  - docx
  - excel
  - xlsx
  - powerpoint
  - pptx
  - leggi documento
  - estrai
  - ingest
  - parse
  - apri file
  - converti
user-invocable: true
allowed-tools:
  - markitdown-mcp/convert_to_markdown
  - filesystem/read
  - filesystem/list_directory
  - aria-memory/wiki_update_tool
max-tokens: 8000
estimated-cost-eur: 0.02
deprecates: pdf-extract@1.0.0
---

# Office Ingest

## Obiettivo
Convertire un file office locale (o URL pubblico) in markdown strutturato pronto per LLM.

## Procedura
1. Risolvi path: se l'utente fornisce path relativo, espandi rispetto a `${ARIA_HOME}` o cwd.
2. Verifica esistenza con `filesystem/read` (head 1KB) — se manca, errore esplicito.
3. Costruisci URI `file://<absolute_path>` o `https://...`.
4. Invoca `markitdown-mcp/convert_to_markdown(uri=<URI>)`.
5. Estrai metadata da output (markitdown emette un blocco YAML con title/author/date dove disponibili).
6. Se output > max-tokens: trunca con marker `[...truncated, N pagine residue...]` e suggerisci scope (range pagine).
7. Salva in wiki ARIA solo se l'utente esplicitamente lo richiede (es. "salva il riassunto"); default no_salience_reason="tool_only".

## Output
- Markdown body con sezioni preservate (headings, tabelle, liste).
- Metadata dict: {file_path, format, title?, author?, page_count?, byte_size, sha256}.
- Tag opzionali: [office_ingest, source_document].

## Invarianti
- Mai modificare il file originale.
- Mai uploadare a servizi esterni se non esplicito (Q5: OCR off).
- Per documenti > 50 MB: warning + prompt HITL prima di proseguire.
- File con dati sensibili (parole chiave: "contratto", "riservato", "confidential") → nota di sicurezza nel summary.

## Failure modes
- markitdown-mcp DOWN → fallback `filesystem/read` raw + warning "estrazione povera, no struttura".
- File corrotto → errore con suggerimento (es. "PDF criptato — fornisci password via HITL").
- Formato non supportato (es. .pages) → suggerisci conversione manuale.
```

### 4.2 `consultancy-brief@1.0.0`

**Path**: `.aria/kilocode/skills/consultancy-brief/SKILL.md`

```markdown
---
name: consultancy-brief
version: 1.0.0
description: Sintesi executive multi-documento per workflow consulente. Compone outline strutturato (TL;DR, contesto, findings, decisioni, open questions) da N file ingested + contesto wiki.
trigger-keywords:
  - briefing
  - executive summary
  - sintesi cliente
  - riepilogo dossier
  - dossier
  - sintesi documenti
user-invocable: true
allowed-tools:
  - office-ingest
  - aria-memory/wiki_recall_tool
  - aria-memory/wiki_update_tool
  - planning-with-files
max-tokens: 20000
estimated-cost-eur: 0.10
---

# Consultancy Brief

## Obiettivo
Produrre brief executive (1-3 pagine markdown) integrando N documenti + storia wiki.

## Procedura
1. Identifica i file in input (path list o glob pattern).
2. Per ogni file: invoca `office-ingest` skill (nested).
3. Recupera contesto wiki: `wiki_recall_tool(query=<topic+entità>)`.
4. Pianifica outline con `planning-with-files`:
   - sezioni: TL;DR (3-5 bullet) → Contesto → Findings → Decisioni pending → Aperti / next steps → Sources.
5. Sintetizza ogni sezione (max 200 parole, citando fonte file:lineblock o pagina dove applicabile).
6. Genera output markdown finale.
7. Default no_salience_reason="recall_only" se nessun fatto nuovo emerge; altrimenti propone topic patch.

## Output
- File markdown brief (in cwd o `${ARIA_HOME}/.aria/runtime/briefs/<timestamp>-<slug>.md`).
- Lista citazioni fonti.

## Invarianti
- Mai inventare dati: se 3+ fonti contraddittorie, riportale tutte.
- Se < 2 fonti totali: avvisa "brief povero" e raccomanda search-agent.
- Cita SEMPRE i file con path relativo + sezione/pagina.
```

### 4.3 `meeting-prep@1.0.0`

**Path**: `.aria/kilocode/skills/meeting-prep/SKILL.md`

```markdown
---
name: meeting-prep
version: 1.0.0
description: Briefing pre-meeting da evento calendario. Aggrega: descrizione evento, partecipanti (storia conversazioni), allegati Drive (ingested), contesto wiki.
trigger-keywords:
  - prepara meeting
  - briefing meeting
  - prep evento
  - prep call
  - prep call cliente
user-invocable: true
allowed-tools:
  - aria-memory/wiki_recall_tool
  - aria-memory/wiki_update_tool
  - office-ingest
  - spawn-subagent     # delega workspace-agent per calendar/gmail/drive
max-tokens: 10000
estimated-cost-eur: 0.05
---

# Meeting Prep

## Obiettivo
Produrre brief 1 pagina markdown per prep meeting/call.

## Procedura
1. Parsing input utente: data/ora evento + parole chiave (cliente, progetto).
2. Spawn workspace-agent → `calendar.list_events(date_range=<window>, q=<keywords>)` → seleziona evento.
3. Estrai partecipanti (campo `attendees`).
4. Per ogni partecipante (esterno, non self):
   - Spawn workspace-agent → `gmail.search(from:<email> OR to:<email>, after:90d)` → ultime N=20 email
   - Sintetizza topic ricorrenti + tono interlocutore.
5. Allegati Drive dell'evento → spawn workspace-agent → `drive.read` → URL/path locali; invoca office-ingest.
6. wiki_recall su `<participant_name>` e `<keywords>` → eventuali topic/decision storici.
7. Compone brief: Profilo evento → Partecipanti (storia + tono) → Allegati key → Decisioni pending → Domande aperte.

## Output
- Markdown 1 pagina (≤ 800 parole).
- Salva in `${ARIA_HOME}/.aria/runtime/briefs/meeting-<date>-<slug>.md`.
- Wiki patch opzionale `meeting-<YYYY-MM-DD>-<slug>` (kind=topic) — solo se l'utente conferma esito post-meeting.

## Invarianti
- Q9 = no auto-tagging: NON crea entity `client-<slug>` automaticamente. Crea SOLO se l'utente chiede esplicitamente "salva questo cliente in wiki".
- Tempi target: 15-30s end-to-end.
- Se partecipanti > 10: tronca a top-5 per frequenza email.
```

### 4.4 `email-draft@1.0.0` (Sprint 2 — dynamic style)

**Path**: `.aria/kilocode/skills/email-draft/SKILL.md`

```markdown
---
name: email-draft
version: 1.0.0
description: Compone bozze email con stile dinamico. Per ogni recipient, analizza runtime le ultime conversazioni via google_workspace e adatta tono/registro/lessico. NESSUN bootstrap di stile fisso, NESSUNA lesson statica.
trigger-keywords:
  - scrivi email
  - drafta mail
  - rispondi a
  - bozza email
  - rispondi mail
user-invocable: true
allowed-tools:
  - aria-memory/wiki_recall_tool
  - hitl-queue/ask
  - spawn-subagent     # workspace-agent per gmail.search + gmail.draft_create
max-tokens: 6000
estimated-cost-eur: 0.04
---

# Email Draft

## Obiettivo
Comporre una bozza email coerente con lo stile usato dall'utente in conversazioni precedenti con lo STESSO recipient (o gruppo). Bozza salvata come Gmail draft (no auto-send).

## Procedura
1. Parsing input: recipient (To), eventuale thread_id o subject di riferimento, scopo (rispondere/ proporre/ chiedere).
2. **Style discovery dinamico (Q7)**:
   a. Spawn workspace-agent → `gmail.search(to:<recipient> OR from:<recipient>, after:365d)` → ultimi 10-30 thread.
   b. Estrai dai thread:
      - Saluto iniziale (es. "Ciao Mario", "Egregio Dott.", "Hi Mario")
      - Saluto finale (es. "A presto", "Cordiali saluti", "Best")
      - Pronome (tu/lei/voi)
      - Lunghezza media frasi
      - Registro (formale / cordiale / conciso / tecnico)
      - Frasi ricorrenti / tic stilistici
   c. Costruisci profilo stile **runtime** (NON salvare in wiki — è transitorio e per-recipient).
3. Recall contesto thread:
   a. Se reply: spawn workspace-agent → `gmail.get_thread(thread_id)` → leggi cronologia.
   b. wiki_recall su recipient name → eventuali entity/topic correlati.
4. Genera bozza rispettando profilo stile + contesto thread + scopo.
5. **HITL locale (Q8)**: `hitl-queue/ask` mostra il diff/preview della bozza all'utente in REPL — utente conferma, modifica o annulla.
6. Su conferma: spawn workspace-agent → `gmail.draft_create(to=<recipient>, subject=<...>, body=<...>, in_reply_to=<thread_id?>)`.
7. **Mai send diretto**: l'invio richiede passo HITL ulteriore esplicito ("invia ora?").

## Output
- Bozza salvata come Gmail draft (resta in cassetto bozze utente).
- Riepilogo testuale all'utente: "Bozza salvata, ID draft <id>. Apri Gmail per inviarla, oppure conferma 'invia' per inviarla via ARIA."

## Invarianti
- **NO lesson statica `email-style-fulvio`** (Q7 esplicito).
- **NO bootstrap utente**: lo stile si auto-discover ad ogni invocazione.
- Se < 3 conversazioni storiche con il recipient: dichiara "stile incerto, propongo registro neutro cordiale" + chiedi conferma HITL.
- Su recipient mai visto: registro default cordiale + conferma HITL prima di drafting.
- Mai includere informazioni da altre conversazioni nel testo della bozza (privacy).
- Cache stile profile in memoria sessione (non disco): scade a fine session.

## Failure modes
- workspace-agent DOWN → degradation: bozza generata con prompt utente puro, no style adaptation.
- Thread quote troppo lunghe → tronca history > 5 messaggi recenti.
- Recipient gruppo (multipli) → discovery sul gruppo aggregato, non per singolo.
```

### 4.5 Aggiornamento `_registry.json`

```json
{
  "skills": [
    {"name": "planning-with-files", "path": "planning-with-files/SKILL.md", "version": "1.0.0", "category": "system"},
    {"name": "deep-research", "path": "deep-research/SKILL.md", "version": "1.0.0", "category": "research"},
    {"name": "pdf-extract", "path": "pdf-extract/SKILL.md", "version": "1.0.0", "category": "ingest", "deprecated_by": "office-ingest@2.0.0"},
    {"name": "office-ingest", "path": "office-ingest/SKILL.md", "version": "2.0.0", "category": "productivity"},
    {"name": "consultancy-brief", "path": "consultancy-brief/SKILL.md", "version": "1.0.0", "category": "productivity"},
    {"name": "meeting-prep", "path": "meeting-prep/SKILL.md", "version": "1.0.0", "category": "productivity"},
    {"name": "email-draft", "path": "email-draft/SKILL.md", "version": "1.0.0", "category": "productivity"},
    {"name": "triage-email", "path": "triage-email/SKILL.md", "version": "0.9.0", "category": "workspace"},
    {"name": "memory-distillation", "path": "memory-distillation/SKILL.md", "version": "1.0.0", "category": "memory"},
    {"name": "hitl-queue", "path": "hitl-queue/SKILL.md", "version": "1.0.0", "category": "system"},
    {"name": "blueprint-keeper", "path": "blueprint-keeper/SKILL.md", "version": "1.0.0", "category": "governance"}
  ]
}
```

`pdf-extract` resta presente con flag `deprecated_by` per backward compatibility (versioning policy §9.4 blueprint).

---

## 5. Architettura Python interna

### 5.1 Layout `src/aria/agents/productivity/`

```
src/aria/agents/productivity/
├── __init__.py
├── ingest.py            # office-ingest dispatcher: validate path → markitdown → metadata
├── synthesizer.py       # consultancy-brief: outline + section composer + citation formatter
├── meeting_prep.py      # meeting-prep: orchestratore delega workspace-agent + ingest
└── email_style.py       # email-draft: thread analyzer + style profile runtime (Sprint 2)
```

### 5.2 `ingest.py` — schema funzioni

```python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

@dataclass
class IngestResult:
    file_path: str
    format: Literal["pdf", "docx", "xlsx", "pptx", "txt", "html", "csv", "other"]
    markdown: str
    title: str | None
    author: str | None
    page_count: int | None
    byte_size: int
    sha256: str
    truncated: bool

async def ingest_file(uri: str, max_bytes: int = 50 * 1024 * 1024) -> IngestResult:
    """Entry point per office-ingest skill. Valida URI, invoca markitdown-mcp,
    parse output, restituisce IngestResult tipizzato."""
    ...

def detect_format(path: Path) -> str: ...
def hash_file(path: Path) -> str: ...
def parse_markitdown_output(raw: str) -> dict: ...
```

### 5.3 `synthesizer.py` — schema

```python
@dataclass
class BriefOutline:
    tldr: list[str]
    context: str
    findings: list[dict]   # {fact, source_file, source_loc}
    decisions_pending: list[str]
    open_questions: list[str]
    sources: list[str]

async def compose_brief(
    files: list[IngestResult],
    wiki_context: dict,
    objective: str,
) -> BriefOutline: ...

def render_markdown(outline: BriefOutline) -> str: ...
```

### 5.4 `meeting_prep.py` — schema

```python
@dataclass
class MeetingBrief:
    event_id: str
    event_summary: str
    start_time: str
    participants: list[dict]   # {name, email, history_summary}
    attachments: list[IngestResult]
    wiki_context: dict
    pending_decisions: list[str]

async def build_meeting_brief(
    event_query: dict,
    workspace_delegate,    # callable per spawn-subagent workspace-agent
) -> MeetingBrief: ...
```

### 5.5 `email_style.py` — schema (Sprint 2)

```python
@dataclass
class StyleProfile:
    recipient: str
    sample_count: int
    greeting: str
    closing: str
    pronoun: Literal["tu", "lei", "voi", "you"]
    register: Literal["formal", "cordial", "concise", "technical", "neutral"]
    avg_sentence_len_words: int
    confidence: float    # 0.0-1.0

async def derive_style(
    recipient: str,
    workspace_delegate,
    lookback_days: int = 365,
    min_samples: int = 3,
) -> StyleProfile: ...

async def draft_email(
    recipient: str,
    subject: str,
    objective: str,
    thread_id: str | None,
    workspace_delegate,
) -> str: ...
```

---

## 6. Test plan (TDD-driven)

### 6.1 Sprint 1 — test obbligatori

| Test file | Scope | Marker |
|-----------|-------|--------|
| `tests/unit/agents/productivity/test_ingest.py` | `detect_format`, `hash_file`, `parse_markitdown_output` (puri); `ingest_file` con mock MCP | `unit` |
| `tests/unit/agents/productivity/test_synthesizer.py` | `compose_brief` con fixture IngestResult statici; `render_markdown` snapshot | `unit` |
| `tests/unit/agents/productivity/test_meeting_prep.py` | `build_meeting_brief` con mock workspace_delegate | `unit` |
| `tests/integration/productivity/test_office_ingest_mcp.py` | E2E con markitdown-mcp reale su 5 fixture file (1 per formato: pdf, docx, xlsx, pptx, txt) | `integration` |
| `tests/integration/productivity/test_consultancy_brief_e2e.py` | 3 fixture file → brief markdown atteso (snapshot) | `integration` |
| `tests/integration/productivity/test_meeting_prep_e2e.py` | mock workspace-agent + 1 fixture event + 2 fixture allegati | `integration` |

**Fixtures** in `tests/fixtures/office_files/`:
- `sample_invoice.pdf` (single page, layout pulito)
- `sample_proposal.docx` (heading + tabella + lista)
- `sample_budget.xlsx` (2 sheet, formule basic)
- `sample_pitch.pptx` (5 slide, title+content layout)
- `sample_notes.txt`

### 6.2 Sprint 2 — test email-draft

| Test file | Scope | Marker |
|-----------|-------|--------|
| `tests/unit/agents/productivity/test_email_style.py` | `derive_style` con thread fixture (formal/cordial/technical) | `unit` |
| `tests/integration/productivity/test_email_draft_e2e.py` | mock gmail.search + gmail.get_thread + gmail.draft_create; verifica draft contiene saluto + closing coerenti con sample | `integration` |

### 6.3 Quality gate

Pre-merge obbligatori (per CLAUDE.md):

```bash
make lint           # ruff check src/
ruff format --check src/
make typecheck      # mypy src/
make test-unit      # pytest -q tests/unit
make test-integration  # pytest -q tests/integration -k productivity
```

`pytest --cov=src/aria/agents/productivity --cov-report=term-missing` target ≥ 80% line coverage.

---

## 7. Implementation steps (ordinati)

### Sprint 1 (Fase 1a — 1 settimana)

> Branch: `feature/productivity-agent-mvp`
> Sequenza step e definition of done per ciascuno.

#### Step 0 — Pre-flight & ADR

- [ ] Creare branch `feature/productivity-agent-mvp` da `main` aggiornato.
- [ ] Redigere `docs/foundation/decisions/ADR-0008-productivity-agent-introduction.md` (template ADR-0006) — status: Proposed.
- [ ] Aggiornare `docs/llm_wiki/wiki/log.md` con entry timestamped.
- **DoD**: ADR committato, branch creato, wiki log aggiornato.

#### Step 1 — markitdown-mcp wiring

- [ ] `uvx markitdown-mcp --help` smoke-test (host).
- [ ] Aggiungere entry `markitdown-mcp` in `.aria/kilocode/mcp.json`.
- [ ] Verificare avvio: `bin/aria repl` carica server senza errori.
- [ ] Test manuale: `convert_to_markdown("file:///tmp/sample.pdf")`.
- **DoD**: server attivo, tool listato, conversione single-file ok.

#### Step 2 — Skeleton agent + skills (TDD)

- [ ] Creare `.aria/kilocode/agents/productivity-agent.md` (frontmatter + body §2.3).
- [ ] Creare `.aria/kilocode/skills/office-ingest/SKILL.md` (§4.1).
- [ ] Creare `.aria/kilocode/skills/consultancy-brief/SKILL.md` (§4.2).
- [ ] Creare `.aria/kilocode/skills/meeting-prep/SKILL.md` (§4.3).
- [ ] Aggiornare `_registry.json` (§4.5).
- [ ] Aggiornare `aria-conductor.md` aggiungendo `productivity-agent` ai sub-agenti disponibili.
- **DoD**: file presenti, conductor list mostra productivity-agent in `<sub-agents>`.

#### Step 3 — `ingest.py` (TDD)

- [ ] Scrivere test `tests/unit/agents/productivity/test_ingest.py` (red).
- [ ] Implementare `src/aria/agents/productivity/ingest.py` (green).
- [ ] Refactor (clean code, type hints, docstring solo dove serve).
- [ ] Integration test con fixture file reali.
- **DoD**: 80%+ coverage modulo, integration test passa.

#### Step 4 — `synthesizer.py` (TDD)

- [ ] Test → impl → integration.
- [ ] Snapshot test su brief markdown atteso.
- **DoD**: `consultancy-brief` skill testabile end-to-end via Conductor manuale.

#### Step 5 — `meeting_prep.py` (TDD)

- [ ] Test con mock workspace_delegate.
- [ ] Integration test con mock spawn-subagent.
- **DoD**: 1 caso d'uso reale (event mock + 2 allegati pdf/docx) → brief markdown.

#### Step 6 — Capability matrix + blueprint update

- [ ] Update `docs/foundation/aria_foundation_blueprint.md`:
  - §8.3.3 — nuova sotto-sezione productivity-agent
  - §8.5 — nuova riga matrice (productivity-agent: aria-memory ✅, markitdown ✅, filesystem ✅, fetch ✅)
  - §9.5 — skills MVP estese (deprecation pdf-extract → office-ingest)
  - §15 — Fase 2 explicit menzione productivity-agent
- **DoD**: blueprint coerente, ADR-0008 referenziato.

#### Step 7 — Wiki maintenance

- [ ] Creare `docs/llm_wiki/wiki/productivity-agent.md` (page status Active).
- [ ] Aggiornare `docs/llm_wiki/wiki/index.md` (Pages table + Raw Sources Table).
- [ ] Append `docs/llm_wiki/wiki/log.md` con timestamped entry chiusura Sprint 1.

#### Step 8 — Quality gate + PR

- [ ] `make quality` deve passare.
- [ ] PR contro `main`: titolo `feat(productivity): introduce productivity-agent MVP (Sprint 1)`.
- [ ] Body PR include: link ADR-0008, riepilogo Q&A, checklist DoD, test evidence.

### Sprint 2 (Fase 1b — 1-2 settimane)

> Stesso branch o `feature/productivity-agent-email-draft` (da decidere a fine Sprint 1).

#### Step 9 — `email_style.py` (TDD)

- [ ] Test su fixture thread JSON (formal/cordial/technical).
- [ ] Impl `derive_style` con heuristic + LLM optional refinement.
- **DoD**: 80%+ coverage; precision discovered style ≥ 70% su 10 thread reali (test manuale supervisionato).

#### Step 10 — `email-draft` skill + agent registration

- [ ] Creare `.aria/kilocode/skills/email-draft/SKILL.md` (§4.4).
- [ ] Update `_registry.json` + `productivity-agent.md`.
- **DoD**: skill registrata, frontmatter valido, trigger keyword test ok.

#### Step 11 — Integration test E2E

- [ ] mock workspace-agent + scenario reale: drafting reply a thread esistente con stile cordial.
- [ ] HITL REPL flow test: prompt utente → conferma → draft saved.

#### Step 12 — Quality gate + PR Sprint 2

---

## 8. ADR-0008 stub (da redigere in Step 0)

```markdown
# ADR-0008: Productivity Agent — Austere MVP Introduction

Status: Proposed
Date: 2026-04-29
Authors: fulvio
Related: ADR-0006 (P10 divergence template)

## Context
Blueprint §15 prevede Fase 2 sub-agenti (Finance/Health/Research-Academic) ma
non `productivity-agent`. L'utente richiede orchestratore dedicato per
workflow consulente: ingestion office files locali, briefing multi-doc,
meeting prep, email drafting con stile dinamico.

## Decision
Introduzione `productivity-agent` come 3° sub-agente operativo, scope austero:
- 1 MCP nuovo: `markitdown-mcp` (Microsoft, MIT, Context7 90.05)
- 4 skill nuove: `office-ingest@2.0.0`, `consultancy-brief@1.0.0`,
  `meeting-prep@1.0.0`, `email-draft@1.0.0`
- Boundary: NO chiamata diretta google_workspace; delega a `workspace-agent`
- HITL: REPL locale (no Telegram per productivity)

## Consequences
- +1 MCP server (passa gate no-bloat: MIT, manutentore Microsoft, Context7
  Bench 90, tool count 1, keyless, capability unica)
- +3 skill in Sprint 1, +1 skill in Sprint 2
- Deprecation `pdf-extract@1.0.0` → `office-ingest@2.0.0` (backward-compatible
  trigger keywords)
- Update blueprint §8.3.3, §8.5, §9.5, §15
- Niente bootstrap stile email statico (decisione utente Q7)
- Fase 2 deliverable-agent userà solo Google Workspace API (decisione utente Q4),
  niente python-docx/pptx/openpyxl locali

## Alternatives considered
- Opzione A (assorbi workspace) → rejected: breaking change, regression risk
- Opzione C (overlap diretto google_workspace) → rejected: sfora P9, drift risk
- Anthropic skills pptx/docx/xlsx → rejected: cloud-only Claude API, non in Kilo
- safe-docx tracked-changes → rejected: utente non fa review legali (Q13)
- docling tier 2 → rejected: PDF complessi non nel workflow utente (Q3)
- obsidian-mcp / easy-notion-mcp → rejected: nessuna KB esterna usata (Q11)
- ms-365-mcp / outlook → rinviato (Q12)

## References
- docs/plans/agents/productivity_agent_foundation_plan.md (questo documento)
- docs/plans/agents/productivity_agent_plan_draf_1.md (DRAFT-2 superseded)
- docs/analysis/ricerca_mcp_produttività.md (input)
- github.com/microsoft/markitdown
```

---

## 9. Rischi e mitigazioni

| Rischio | Probabilità | Mitigazione |
|---------|-------------|-------------|
| `markitdown-mcp` lento su PDF >100 pagine | Media | Skill timeout 60s + truncation + warning utente |
| Fallback ingest senza markitdown | Bassa | `filesystem/read` raw + warning struttura persa |
| Delega 2-hop instabile (workspace-agent down) | Media | Circuit breaker su spawn-subagent: 3 tentativi → degraded mode |
| Email-draft style discovery povero (< 3 thread) | Media | Fallback registro neutro cordiale + HITL conferma |
| Deprecation `pdf-extract` rompe trigger esistenti | Bassa | trigger keywords backward-compatible su `office-ingest` |
| LLM drift su synthesizer (hallucination) | Media | Citazioni mandatorie file:loc; prompt vincola "no facts non in fonte" |
| HITL REPL bloccato (utente assente) | Media | Timeout 5min su `hitl-queue/ask` → action skipped + log |
| Privacy email cross-thread | Alta (impatto, bassa prob.) | Lock per-recipient: lo style profile è transitorio in-memory, mai includere testo da altri thread |
| Costo runtime email-draft | Media | Cache style profile per session; gmail.search lookback 365d hard cap |
| Sostenibilità RAM con +1 MCP | Bassa | markitdown leggero (<200MB idle). Audit a fine Sprint 1 |

---

## 10. Branch & PR strategy

- Branch: `feature/productivity-agent-mvp` (Sprint 1)
- Eventuale split: `feature/productivity-agent-email-draft` (Sprint 2)
- PR Sprint 1 → review fulvio → merge `main` (squash merge)
- ADR-0008 status `Proposed` → `Accepted` solo dopo merge Sprint 1
- Conventional commits:
  - `feat(productivity): add markitdown-mcp + office-ingest skill`
  - `feat(productivity): consultancy-brief skill + synthesizer`
  - `feat(productivity): meeting-prep skill + delegation flow`
  - `chore(skills): deprecate pdf-extract@1.0.0 in favor of office-ingest@2.0.0`
  - `docs(adr): ADR-0008 productivity-agent introduction`
  - `docs(blueprint): §8.3.3 productivity-agent + capability matrix`
  - `docs(wiki): productivity-agent page + index update`

---

## 11. Acceptance criteria (Definition of Done — Sprint 1)

L'agente è considerato pronto quando:

- [ ] `bin/aria repl` avvia senza errori, productivity-agent visibile in conductor list
- [ ] Comando manuale "leggi `tests/fixtures/office_files/sample_proposal.docx`" → markdown ben formato emesso (test E2E)
- [ ] Comando manuale "fammi un brief sui 3 file in `tests/fixtures/office_files/`" → brief markdown 1-3 pagine con sezioni TL;DR/Findings/Sources
- [ ] Comando manuale "prepara meeting Acme di domani" (con mock event) → brief 1 pagina con partecipanti + allegati ingested
- [ ] `make quality` verde (lint + format + typecheck + test)
- [ ] Coverage `src/aria/agents/productivity/` ≥ 80%
- [ ] ADR-0008 status `Proposed` mergeable
- [ ] Blueprint §8.3.3, §8.5, §9.5, §15 aggiornati
- [ ] Wiki productivity-agent page Active
- [ ] PR aperta verso `main` con review request

Sprint 2 DoD aggiuntivo:

- [ ] Comando "scrivi mail di risposta a mario.rossi@acme.com proponendo call settimana prossima" → bozza salvata in Gmail draft (mock o reale), stile coerente con storia conversazioni recipient (verificato manualmente su 3 recipient diversi)

---

## 12. Riferimenti

### Codebase ARIA (sorgenti)
- `docs/foundation/aria_foundation_blueprint.md` (§8, §9, §10, §12, §15, §16)
- `docs/plans/agents/productivity_agent_plan_draf_1.md` (DRAFT-2 superseded)
- `docs/analysis/ricerca_mcp_produttività.md` (input gemme MCP)
- `.aria/kilocode/agents/{aria-conductor,search-agent,workspace-agent}.md`
- `.aria/kilocode/skills/{pdf-extract,triage-email,planning-with-files,deep-research}/SKILL.md`
- `.aria/kilocode/mcp.json`
- `docs/foundation/decisions/ADR-0006-research-agent-academic-social-expansion.md` (template)
- `docs/llm_wiki/wiki/index.md`

### Risorse esterne (Context7-verified)
- [Microsoft MarkItDown — github.com/microsoft/markitdown](https://github.com/microsoft/markitdown) — `/microsoft/markitdown` Bench 90.05
- [Anthropic Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) — pattern SKILL.md (reference only, esecuzione non Kilo)

---

**FINE FOUNDATION PLAN.**

> Pronto per Step 0. Prossima azione operativa: redigere ADR-0008 + creare branch
> `feature/productivity-agent-mvp` previa autorizzazione utente.
