# Productivity-Agent — Draft 2 (revisione austera post-confronto MCP report)

```yaml
status: DRAFT-2 (discussion only — non implementare)
author: aria-conductor (sessione fulvio)
created: 2026-04-29
updated: 2026-04-29 (v2)
language: IT
audience: fulvio (utente principale + product owner ARIA)
related-blueprint-sections:
  - "§8.3 Sub-agenti OPERATIVI (MVP)"
  - "§9 Skills Layer"
  - "§10 Tools & MCP Ecosystem"
  - "§12 Sub-Agent Google Workspace"
  - "§16 Ten Commandments (P1..P10)"
  - "§15 Roadmap (Fase 2 nuovi sub-agenti)"
related-adrs:
  - "ADR-0001-dependency-baseline-2026q2.md (baseline deps)"
  - "ADR-0006-research-agent-academic-social-expansion.md (template P10 divergence)"
input-reports:
  - "docs/analysis/ricerca_mcp_produttività.md (2026-04-29 — github-discovery + Context7)"
research-sources:
  - "github.com/microsoft/markitdown (Context7: /microsoft/markitdown)"
  - "github.com/docling-project/docling (Context7: /docling-project/docling)"
  - "github.com/anthropics/skills (reference SKILL.md pattern — N.B. esecuzione cloud-only)"
  - "Anthropic Agent Skills overview (platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)"
```

---

## 0. Cambi rispetto a Draft 1 (changelog)

Confronto con `docs/analysis/ricerca_mcp_produttività.md` ha forzato una
revisione **austera**. Principio guida: **minimum viable agent**, no MCP
proliferation, sostenibilità del sistema sopra la copertura.

| Sezione | Cambio | Motivazione |
|---------|--------|-------------|
| §1 | Missione invariata | OK |
| §2 | Aggiunto vincolo "no-bloat budget MCP" | Sostenibilità complessiva |
| §3 | Opzione B confermata, Opzioni A/C ribadite come scartate | OK |
| §4 | **Scope MVP ridotto** (3 skill iniziali, non 5) | Evitare over-eng |
| §5 | **Drop docling tier 2 di default**; safe-docx opt-in; baseline a 1 solo MCP nuovo | No bloat |
| §5.5 (NEW) | Criteri di accettazione "no-bloat" per nuovi MCP | Gate quantitativo |
| §6 | Correzione Anthropic skills (cloud-only) | Fact error draft 1 |
| §10 | Open questions 11-13 nuove (Obsidian/Notion, M365, contratti DOCX) | Decisione informed |
| §12 | Roadmap divisa in **MVP fase 1a** (1 settimana) e **fase 1b** (2-3 settimane) | Iterativa |

### Correzioni fattuali da Draft 1

1. **Anthropic skills `pptx/docx/xlsx/pdf` ufficiali** sono disponibili **solo** via
   Claude API + code-execution container (beta `code-execution-2025-08-25` +
   `skills-2025-10-02`). **Non runnano dentro KiloCode locale**. Quindi NON sono
   utilizzabili come backend per `deliverable-draft`. Vanno usate come
   *reference di pattern SKILL.md*, non come dipendenza eseguibile.
2. **`spawn-subagent`** non è un tool MCP standard ma un meccanismo KiloCode
   di delega tra agenti via child session (§8.6 blueprint). Conta nel budget
   tool ma con semantica diversa.
3. **Il triage-email skill (esistente)** rimane saldamente su `workspace-agent`.
   Productivity-agent non lo importa, lo richiama solo per delega.

---

## 1. Missione del nuovo sub-agente

(invariato rispetto a Draft 1)

**Nome proposto**: `productivity-agent`

**One-liner**: assistente di produttività per il lavoro di **consulenza** dell'utente
— ingestione, analisi, sintesi e produzione di artefatti (email, eventi, deliverable,
documenti office esterni a Google Workspace).

| Sub-agent | Domain | Pattern operativo |
|-----------|--------|------------------|
| `search-agent` | sapere esterno | discovery → dedup → sintesi |
| `workspace-agent` | Google Workspace API | CRUD su Gmail/Cal/Drive/Docs/Sheets |
| **`productivity-agent`** (proposta) | **deliverable + workflow consulente** | ingestion locale → composition → drafting → HITL |

---

## 2. Conformità inderogabile + budget di sostenibilità

### 2.1 Ten Commandments (riepilogo dipendenze)

| # | Principio | Implicazione |
|---|-----------|-------------|
| P1 | Isolation First | Tool e file leggono SOLO da `${ARIA_HOME}` + path whitelist |
| P2 | Upstream Invariance | Riusa MCP esistenti — niente fork |
| P3 | Polyglot Pragmatism | Skills MD + Python locale per fallback |
| P4 | Local-First | Office files restano on-disk, conversioni in locale |
| P5 | Actor-Aware Memory | Patch wiki taggate per origine actor |
| P6 | Verbatim Preservation | Tier 0 = full text + path file originale |
| P7 | HITL on Destructive | Send/create/write → `policy=ask` |
| P8 | Tool Priority Ladder | MCP esistente > skill compositiva > Python locale |
| **P9** | **Scoped Toolsets ≤20** | Vincolo critico — vedi §5.4 |
| P10 | Self-Documenting | ADR-0008 obbligatorio |

### 2.2 Budget di sostenibilità (NEW)

Stato attuale repository ARIA: **12 MCP server** già in `.aria/kilocode/mcp.json`
(filesystem, git, github, sequential-thinking, fetch, aria-memory, tavily-mcp,
brave-mcp, exa-script, searxng-script, google_workspace, playwright-disabled,
pubmed-mcp, scientific-papers-mcp, reddit-search).

**Costo non-evidente di ogni MCP**:
- Memoria + processo per server (avg 80-200 MB RAM idle)
- Latenza startup `bin/aria repl` (Kilo carica TUTTI server al boot)
- Branch review overhead (già fixato a ~5s, ma più server = più tool da scansionare)
- Sup/security audit + credential management
- Drift risk: MCP unmaintained = security debt

**Budget proposto productivity-agent**: **+1 MCP nuovo** (massimo +2 con opt-in).

Ogni MCP aggiuntivo deve passare il **gate no-bloat** (vedi §5.5).

---

## 3. Boundary vs `workspace-agent`

(Conferma Draft 1 — Opzione B raccomandata)

`productivity-agent` orchestra workflow consulente. Per Gmail/Cal/Drive
**delega a `workspace-agent`** via meccanismo KiloCode child session
(blueprint §8.6).

| Opzione | Verdict |
|---------|---------|
| A — Productivity assorbe Workspace | ❌ Breaking change, rejected |
| **B — Coesistenza con delega** | ✅ **Raccomandata** |
| C — Overlap diretto Google Workspace | ❌ Sfora P9, drift risk |

---

## 4. Capability set MVP — versione austera

### 4.1 Scope MVP **ridotto** (Fase 1a + 1b)

#### **Fase 1a — Spike (1 settimana)**: solo essential

3 skill, 1 MCP nuovo, no opt-in attivi.

| Cluster | Skill | Status v2 |
|---------|-------|-----------|
| Office Ingestion | `office-ingest` (deprecates `pdf-extract@1.0.0` → v2.0.0) | **Nuova** |
| Document Synthesis | `consultancy-brief` | **Nuova** |
| Meeting Prep | `meeting-prep` | **Nuova** |

#### **Fase 1b — Estensione condizionale (2-3 settimane post-feedback)**: opt-in

| Skill | Trigger di attivazione |
|-------|----------------------|
| `email-draft` | Solo se Open Q7 = sì (campioni stile email forniti) |
| `contract-review` | Solo se Open Q13 = sì (consulente fa tracked-changes su DOCX clienti) |

#### **Fase 2 (rimandato — out of scope)**: confermato

| Skill | Motivazione rinvio |
|-------|-------------------|
| `deliverable-draft` (DOCX/PPTX/XLSX gen) | Anthropic skills NON disponibili in Kilo; richiede python-docx/pptx/openpyxl in agente separato (`deliverable-agent`) per non sforare P9 |
| `meeting-transcribe` (STT meeting) | Dipende ADR-0007 STT stack + hardware |

### 4.2 Skills MVP — frontmatter draft

#### `office-ingest@2.0.0` (ex `pdf-extract@1.0.0`)

```yaml
---
name: office-ingest
version: 2.0.0
description: Estrae testo + tabelle + metadata da PDF/DOCX/XLSX/PPTX/TXT/HTML in markdown LLM-ready
trigger-keywords: [pdf, word, docx, excel, xlsx, powerpoint, pptx, leggi documento, estrai, ingest, parse]
user-invocable: true
allowed-tools:
  - markitdown-mcp/convert_to_markdown
  - filesystem/read
  - aria-memory/wiki_update_tool
max-tokens: 8000
estimated-cost-eur: 0.02
deprecates: pdf-extract@1.0.0
---
```

Tool count: 3.

#### `consultancy-brief@1.0.0`

```yaml
---
name: consultancy-brief
version: 1.0.0
description: Sintesi executive multi-documento con outline strutturato per consulente
trigger-keywords: [briefing, executive summary, sintesi cliente, riepilogo dossier]
user-invocable: true
allowed-tools:
  - office-ingest                    # nested skill
  - aria-memory/wiki_recall_tool
  - aria-memory/wiki_update_tool
  - planning-with-files              # esistente, riusato
max-tokens: 20000
estimated-cost-eur: 0.10
---
```

#### `meeting-prep@1.0.0`

```yaml
---
name: meeting-prep
version: 1.0.0
description: Briefing pre-meeting da evento calendario, allegati e storia partecipanti
trigger-keywords: [prepara meeting, briefing meeting, prep evento]
user-invocable: true
allowed-tools:
  - aria-memory/wiki_recall_tool
  - office-ingest
  - <delega workspace-agent per calendar.get_event>
max-tokens: 10000
estimated-cost-eur: 0.05
---
```

---

## 5. Stack MCP/tooling proposto — versione austera

### 5.1 Decisione netta: **+1 MCP nuovo** in MVP

| Server | Add MVP? | Razionale |
|--------|----------|-----------|
| **markitdown-mcp** | ✅ **SÌ** | Unico nuovo. Copre PDF/DOCX/XLSX/PPTX/HTML/TXT in 1 tool. Microsoft, MIT, Context7 90.05. Sostituisce 4-5 wrapper Python locali |
| docling | ❌ NO (rinviato) | Solo se Q3 OCR/PDF-complessi=sì. Aggiungibile in 30min |
| safe-docx | ❌ NO default; ✅ **opt-in se Q13=sì** | Solo se contratti DOCX tracked-changes |
| GongRzhe Office-Word | ❌ **NO** | 25+ tool sforerebbe P9 da solo. Riassegnato a `deliverable-agent` Fase 2 |
| task-graph-mcp / shrimp | ❌ NO | Duplicano `planning-with-files` + wiki memory |
| obsidian-mcp-plugin | ❌ NO default; ✅ **opt-in se Q11a=Obsidian** | Knowledge base esterna |
| easy-notion-mcp | ❌ NO default; ✅ **opt-in se Q11b=Notion** | Knowledge base esterna (XOR con Obsidian) |
| MarimerLLC calendar / nspady google-cal | ❌ NO | Workspace-agent già copre Google Cal |
| ms-365-mcp / ufficio M365 | ❌ NO default; ✅ **opt-in se Q12=sì** | Solo se utente lavora M365/Outlook |
| gongrzhe gmail / shinzo-labs gmail | ❌ NO | Duplicano google_workspace gmail.* |

**Conclusione**: MVP introduce **1 solo nuovo MCP** (markitdown-mcp).
Tutto il resto opt-in, attivato solo da risposta utente specifica.

### 5.2 MCP esistenti riusati (zero nuovi)

- `aria-memory` — wiki_update/recall/show/list
- `google_workspace` — via delega a workspace-agent (NO chiamata diretta da productivity-agent)
- `filesystem` — read locale
- `fetch` — fallback URL pubblici nei documenti

### 5.3 Wrapper SOPS

`markitdown-mcp` non richiede API key. Niente SOPS wrapper. Eccezione: se in
Fase 2 si attiva plugin `markitdown-ocr`, serve `OPENAI_API_KEY` via
`CredentialManager` esistente — pattern stesso di `tavily-wrapper.sh`.

### 5.4 Budget tool — **conteggio finale MVP austero**

Productivity-agent `allowed-tools` MVP:

| Tool | Count |
|------|-------|
| `markitdown-mcp/convert_to_markdown` | 1 |
| `filesystem/read` | 1 |
| `filesystem/list_directory` | 1 |
| `aria-memory/wiki_update_tool` | 1 |
| `aria-memory/wiki_recall_tool` | 1 |
| `aria-memory/wiki_show_tool` | 1 |
| `aria-memory/wiki_list_tool` | 1 |
| `hitl-queue/ask` | 1 |
| `fetch/fetch` | 1 |
| `sequential-thinking/*` | 1 |
| `<delega workspace-agent>` (KiloCode child session, conta come 1) | 1 |
| **Totale MVP** | **11** |

Margine 9 tool rispetto a P9=20. Spazio per:
- `safe-docx/*` (4 tool) se Q13=sì → 15
- `obsidian-mcp-plugin/*` (8 gruppi tool) se Q11a=Obsidian → ~19 (rischio sforo)
- `easy-notion-mcp/*` (26 tool wildcard counted as 1) se Q11b=Notion → 12

**Vincolo P9**: se Q11a=Obsidian E Q13=sì E Q12=sì → split in 2 sub-agenti
(`productivity-agent` + `deliverable-agent`) anticipando Fase 2.

### 5.5 Gate "no-bloat" per accettazione MCP (NEW)

Ogni MCP candidato deve soddisfare **tutti**:

| Criterio | Soglia | Esempio FAIL |
|----------|--------|--------------|
| **License** | MIT, Apache-2, BSD | GPL = audit ADR |
| **Manutentore** | Org riconosciuta (Microsoft, IBM, Anthropic, etc.) o repo con commit ultimi 90gg | Repo abbandonato 2024 |
| **Context7-verified** | Benchmark ≥70 OR Source Reputation High | Repo senza Context7 entry |
| **Tool count** | ≤15 tool nominali (wildcard ammessi se sub-tool sono organici) | 200+ tool MS-365 = no |
| **Keyless preferred** | Keyless > OAuth > API key | API key paid-only = no |
| **Coverage unicità** | Copre ≥1 capability **non già coperta** da MCP esistente | Duplicato gmail-mcp = no |
| **Footprint runtime** | <300 MB RAM idle, <2s cold start | Java JVM heavyweight = audit |

Approccio: **prima si dimostra che la skill esistente non basta**, poi si valuta MCP, poi script Python locale come fallback (P8 ladder).

---

## 6. Architettura interna (Python) — invariato + chiarimenti

### 6.1 Layout

```
src/aria/agents/productivity/
├── __init__.py
├── ingest.py          # office-ingest dispatcher (markitdown-only in MVP)
├── synthesizer.py     # outline + multi-doc summarization helpers
├── meeting_prep.py    # builder briefing per evento
└── tests/
    └── test_ingest.py
```

Pattern allineato a `src/aria/agents/search/router.py`.

### 6.2 Disclaimer Anthropic Skills (correzione Draft 1)

Le skill ufficiali Anthropic `pptx/docx/xlsx/pdf` sono disponibili **solo
via Claude API code-execution container** (beta header `code-execution-2025-08-25`
+ `skills-2025-10-02`). KiloCode locale **non le esegue**.

Implicazioni:
- Repo `github.com/anthropics/skills` resta utile come **reference di pattern
  SKILL.md** (struttura, descrizioni, esempi).
- Per generazione documenti DOCX/PPTX/XLSX in Fase 2 serve Python locale
  (`python-docx`, `python-pptx`, `openpyxl`) o MCP terzi (GongRzhe family) in
  `deliverable-agent` separato.

### 6.3 Pattern di delega 2-hop (invariato)

```
utente → conductor → productivity-agent (child session)
                           ↓ markitdown-mcp ingest dei file
                           ↓ wiki_recall per contesto
                           ↓ se serve email/cal: delega → workspace-agent
                                                          ↓ gmail.*/calendar.*
                           ↓ aggrega
                     ← restituisce
```

---

## 7. Memoria & wiki (invariato Draft 1)

Pagine wiki create dal productivity-agent:

| Pagina | Kind | Trigger |
|--------|------|---------|
| `client-<slug>` | entity | nuovo cliente menzionato |
| `project-<slug>` | topic | nuovo progetto consulenza |
| `meeting-<date>-<slug>` | topic | post-meeting summary |
| `template-<doc-type>` | entity | template DOCX/PPTX riusabile |
| `email-style-fulvio` | lesson | **solo se Fase 1b email-draft attivato** |

Patch tagga origine actor (`tool_output`/`agent_inference`/`user_input`)
via Memory v3 wiki schema esistente.

---

## 8. Dipendenze ADR e blueprint

### ADR-0008 (proposto): "Productivity Agent — austere MVP introduction"

Template ADR-0006-style:
- **Context**: blueprint §15 prevede in Fase 2 nuovi sub-agenti (Finance/Health),
  productivity-agent **non esplicito**. Workflow consulente utente richiede
  orchestratore dedicato per office files locali + multi-doc synthesis.
- **Decision**: introdurre `productivity-agent` come 3° sub-agente operativo,
  scope MVP austero (1 MCP nuovo: markitdown-mcp; 3 skills nuove).
  Capability email/cal **delegate** a workspace-agent.
- **Consequences**:
  - +1 MCP server (markitdown-mcp) — passa gate no-bloat §5.5
  - +3 skills (office-ingest deprecates pdf-extract; consultancy-brief; meeting-prep)
  - Update §8.5 capability matrix (nuova riga)
  - Update §9.5 skills MVP (deprecation pdf-extract → office-ingest)
  - Update §15 roadmap (productivity diventa Fase 2 explicit)
  - Fase 1b condizionale (email-draft, contract-review) basata su risposte open Q
  - Fase 2 split possibile: `deliverable-agent` separato per DOCX/PPTX/XLSX gen

### Aggiornamenti blueprint richiesti

- `§8.3.3 Productivity-Agent` — nuova sotto-sezione (spec + handbook scope austero)
- `§8.5` — riga matrice nuova
- `§9.5` — skills MVP estese, deprecation pdf-extract
- `§15` — Fase 2 productivity explicit + nota su `deliverable-agent`/`meeting-transcribe-agent` futuri

---

## 9. Diff Draft 2 vs Report `ricerca_mcp_produttività.md`

Tabella sintetica delle 13+ MCP del report e decisione austera:

| MCP del report | Decisione v2 | Note |
|----------------|--------------|------|
| GongRzhe Office-Word | ❌ DROP scope | Tool count 25+ sfora P9. Riassegnato Fase 2 deliverable-agent |
| safe-docx | 🔶 OPT-IN (Q13) | Tracked changes contratti — caso d'uso reale solo se utente fa review legali |
| Aanerud MCP-Microsoft-Office | ❌ DROP | M365 coverage; solo se Q12=sì |
| nspady google-calendar-mcp | ❌ DROP scope | Workspace-agent già copre Google Calendar |
| MarimerLLC calendar-mcp | ❌ DROP | Multi-provider M365+Google, eccessivo |
| shrimp-task-manager | ❌ DROP | Duplica planning-with-files + wiki |
| oortonaut task-graph-mcp | ❌ DROP | Multi-agent workflow eccessivo per MVP single-conductor |
| Pimzino agentic-tools | ❌ DROP | Duplica wiki memory |
| aaronsb obsidian-mcp-plugin | 🔶 OPT-IN (Q11a) | Knowledge base esterna |
| grey-iris easy-notion-mcp | 🔶 OPT-IN (Q11b, XOR Obsidian) | Knowledge base esterna |
| softeria ms-365-mcp-server | ❌ DROP default | 200+ tool, M365 only — Q12 opt-in con ADR aggiuntivo |
| gongrzhe gmail-mcp / shinzo-labs gmail | ❌ DROP | Duplica google_workspace gmail.* |
| guinacio mcp-google-calendar / deciduus | ❌ DROP | Duplicato calendar |

**Solo markitdown-mcp passa il gate no-bloat in MVP**.

---

## 10. Open questions (estese a 13 — input utente richiesto)

> Risposte servono prima di redigere Draft 3 / ADR-0008 / spec finale.

1. **Boundary vs workspace-agent**: confermi **Opzione B** (delega)?
2. **Scope Fase 1a MVP**: confermi solo `office-ingest` + `consultancy-brief` + `meeting-prep`?
3. **PDF complessi**: PDF accademici / contratti / scansioni nel tuo workflow?
   - Se **sì** → docling tier 2 in Fase 1b
   - Se **no** → markitdown sufficiente
4. **Deliverable output frequenti**: DOCX, PPTX, XLSX, PDF, Markdown, tutti?
   (Risposta condiziona priorità Fase 2 `deliverable-agent`)
5. **OCR su immagini in documenti**: serve? (Costo: chiave OpenAI Vision via plugin markitdown-ocr)
6. **Audio meeting**: trascriverai meeting? (Fase 2 `meeting-transcribe-agent`)
7. **Stile email**: vuoi attivare `email-draft` Fase 1b? Se sì, fornisci 10-20 campioni email tue.
8. **HITL canale**: gate destructive via Telegram (default §7) o REPL prompt locale?
9. **Multi-cliente parallelo**: serve auto-tagging entity `client-<slug>`?
10. **Naming agente**: `productivity-agent` ok o preferisci `consulting-agent`/`assistant-agent`/`office-agent`?
11. **Knowledge base esterna** (NEW v2):
    - **(a)** Obsidian → `obsidian-mcp-plugin` opt-in (~8 gruppi tool)
    - **(b)** Notion → `easy-notion-mcp` opt-in (1 wildcard)
    - **(c)** Nessuno → wiki ARIA sufficiente (default v2)
    - **(d)** Entrambi → richiede split agente (sfora P9)
12. **Microsoft 365 / Outlook** (NEW v2): lavori su M365? (default: NO; se sì → ADR-0009 separato per ms-365-mcp-server)
13. **Revisione contratti / DOCX tracked-changes** (NEW v2): fai editing chirurgico DOCX clienti? Se sì → `safe-docx` opt-in + skill `contract-review` Fase 1b.

---

## 11. Rischi e mitigazioni

| Rischio | Probabilità | Mitigazione v2 |
|---------|-------------|----------------|
| Sforamento P9 con opt-in cumulativi | Media | Gate no-bloat §5.5 + auto-split a `deliverable-agent` quando count >18 |
| Drift `triage-email` (workspace) vs `email-draft` (productivity) | Bassa (Fase 1b condizionale) | Lock di responsabilità: workspace = read/classify; productivity = compose draft |
| Lock-in markitdown se cambia API | Bassa | Wrapper `ingest.py` astrae chiamata MCP |
| Office files con dati sensibili | Alta | Local-first default; mai upload a markitdown-ocr senza HITL esplicito |
| Hallucination email draft | Media | HITL obbligatorio pre-send; diff con storia conversazione visibile in prompt |
| Conflitto deprecation `pdf-extract` v1 | Bassa | Backward-compatible trigger keywords su `office-ingest` v2 |
| MCP unmaintained drift | Media | Audit trimestrale via security-auditor (§8.4); gate no-bloat al re-onboarding |
| Sostenibilità complessiva (RAM/IO) | Media | **Limit hard +1 MCP/agente nuovo** salvo ADR; documentato in §2.2 |

---

## 12. Roadmap di approvazione

> Nessun passaggio finché Fulvio non risponde a §10 (Q1-13).

1. ⏳ **Discussione Draft 2** (questo file) — feedback utente su 13 Q
2. ⏳ Draft 3: integrazione decisioni utente (sblocco opt-in Q3/Q11/Q12/Q13)
3. ⏳ ADR-0008 redazione
4. ⏳ Spec finale (path TBD: `docs/superpowers/specs/...` o `docs/plans/agents/productivity_agent_plan_final.md`)
5. ⏳ Implementation plan via skill `writing-plans` (TDD-driven)
6. ⏳ **Fase 1a Spike** (1 settimana): markitdown-mcp + 3 skill su feature branch `feature/productivity-agent-mvp`
7. ⏳ E2E test: caso d'uso "leggi questo PDF e dimmi i punti chiave" + "prepara meeting Acme domani"
8. ⏳ **Fase 1b condizionale** (2-3 settimane post-feedback): email-draft / contract-review se opt-in
9. ⏳ PR con quality gates (`make quality`) + ADR + blueprint update + wiki update

---

## 13. Riferimenti

### Codebase ARIA
- `docs/foundation/aria_foundation_blueprint.md` (§8, §9, §10, §12, §15, §16)
- `docs/analysis/ricerca_mcp_produttività.md` (input report v2)
- `.aria/kilocode/agents/aria-conductor.md`
- `.aria/kilocode/agents/search-agent.md`
- `.aria/kilocode/agents/workspace-agent.md`
- `.aria/kilocode/skills/_registry.json`
- `.aria/kilocode/skills/pdf-extract/SKILL.md` (deprecando)
- `.aria/kilocode/skills/triage-email/SKILL.md` (resta su workspace-agent)
- `.aria/kilocode/mcp.json`
- `docs/foundation/decisions/ADR-0006-research-agent-academic-social-expansion.md` (template P10)
- `docs/llm_wiki/wiki/index.md`

### Risorse esterne (Context7-verified)
- [Microsoft MarkItDown — github.com/microsoft/markitdown](https://github.com/microsoft/markitdown) — `/microsoft/markitdown` Bench 90.05 — MCP single-tool `convert_to_markdown(uri)`, formati PDF/DOCX/XLSX/PPTX/HTML/Audio
- [Docling — github.com/docling-project/docling](https://github.com/docling-project/docling) — `/docling-project/docling` Bench 84.56 — fallback PDF avanzato (Fase 1b condizionale)
- [Anthropic Skills repo — github.com/anthropics/skills](https://github.com/anthropics/skills) — reference pattern SKILL.md (NB: esecuzione cloud-only)
- [Anthropic Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [UseJunior safe-docx — opt-in Q13](https://github.com/UseJunior/safe-docx) — tracked changes DOCX
- [aaronsb obsidian-mcp-plugin — opt-in Q11a](https://github.com/aaronsb/obsidian-mcp-plugin) — `/aaronsb/obsidian-mcp-plugin` Bench 87.65
- [grey-iris easy-notion-mcp — opt-in Q11b](https://github.com/grey-iris/easy-notion-mcp) — `/grey-iris/easy-notion-mcp` Bench 97.1

---

## 14. Appendice — esempio flow utente (invariato Draft 1)

**Scenario**: Fulvio ha meeting domani con cliente Acme. Ricevuti via mail
3 PDF (proposta, contratto, slide), 12 email scambiate con referente.

**Comando**: *"ARIA, prepara meeting Acme di domani"*

**Flow MVP (post-Fase 1a)**:

1. Conductor → wiki_recall → trova entity `client-acme`, topic `project-acme-q2`.
2. Conductor → delega `productivity-agent` skill `meeting-prep` (args: event=domani, client=acme).
3. `productivity-agent` (child session):
   1. Delega → workspace-agent → `calendar.list_events(date=tomorrow, q="acme")` → evento + allegati Drive
   2. Delega → workspace-agent → `gmail.search(from:acme.com, after:30d)` → 12 email
   3. office-ingest sui 3 PDF → markdown via markitdown-mcp
   4. wiki_recall su `client-acme` + `project-acme-q2`
   5. consultancy-brief skill compone:
      - Profilo cliente
      - Stato avanzamento progetto
      - Punti aperti dalle email
      - Highlight dai PDF
      - Decisioni pending
   6. Output → markdown brief 2 pagine + opzionale push Telegram + salva wiki `meeting-2026-04-30-acme`
4. Conductor → restituisce brief inline + link meeting page.

Tempo stimato: 15-30s (dominato da markitdown-mcp su 3 PDF + LLM synthesis).

---

**FINE DRAFT 2.** In attesa feedback su Open Questions §10 (13 domande).
