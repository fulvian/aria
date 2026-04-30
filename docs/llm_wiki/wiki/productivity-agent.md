# Productivity-Agent

**Status**: Active
**Created**: 2026-04-29
**Updated**: 2026-04-29 (Sprint 2 — email-draft)
**Source**: ADR-0008, `docs/plans/agents/productivity_agent_foundation_plan.md`
**Branch**: `feature/productivity-agent-mvp`

## Overview

Productivity-agent è il 3° sub-agente operativo di ARIA, specializzato in
workflow consulente: ingestion office files locali, briefing multi-documento,
meeting prep da calendario.

## Architecture

```
utente
  └─→ aria-conductor
       └─→ productivity-agent
              ├─ markitdown-mcp    (office → markdown conversion)
              ├─ aria-memory       (wiki recall + update)
              ├─ filesystem        (read documenti locali)
              ├─ fetch             (URL pubblici)
              ├─ hitl-queue/ask    (REPL locale)
              └─ delega → workspace-agent (gmail/calendar/drive)
```

Pattern **delega 2-hop**: productivity-agent non tocca direttamente Google Workspace;
spawna child session di workspace-agent per tutte le API Gmail/Calendar/Drive.

## Skills (Sprint 1)

| Skill | Version | Description |
|-------|---------|-------------|
| `office-ingest` | 2.0.0 | Estrae testo/tabelle/metadata da PDF/DOCX/XLSX/PPTX/TXT/HTML/CSV in markdown LLM-ready via markitdown-mcp. Deprecates `pdf-extract@1.0.0`. |
| `consultancy-brief` | 1.0.0 | Sintesi executive multi-documento con outline strutturato: TL;DR, Contesto, Findings, Decisioni, Open Questions. |
| `meeting-prep` | 1.0.0 | Briefing pre-meeting da evento calendario con partecipanti, allegati Drive, contesto wiki. |

## Skills

| Skill | Version | Sprint | Description |
|-------|---------|--------|-------------|
| `office-ingest` | 2.0.0 | 1 | Estrae testo/tabelle/metadata da PDF/DOCX/XLSX/PPTX/TXT/HTML/CSV in markdown LLM-ready via markitdown-mcp. Deprecates `pdf-extract@1.0.0`. |
| `consultancy-brief` | 1.0.0 | 1 | Sintesi executive multi-documento con outline strutturato: TL;DR, Contesto, Findings, Decisioni, Open Questions. |
| `meeting-prep` | 1.0.0 | 1 | Briefing pre-meeting da evento calendario con partecipanti, allegati Drive, contesto wiki. |
| `email-draft` | 1.0.0 | 2 | Bozze email con stile dinamico derivato runtime dalle conversazioni con il recipient (Q7). NESSUNA lesson statica. |

## Agent Definition

File: `.aria/kilocode/agents/productivity-agent.md`
- 11 tool autorizzati (markitdown-mcp/convert_to_markdown, filesystem/*, aria-memory/*, hitl-queue/ask, fetch/fetch, sequential-thinking/*, spawn-subagent)
- 5 skill required (office-ingest, consultancy-brief, meeting-prep, email-draft, planning-with-files)
- MCP dependencies: [markitdown-mcp, aria-memory, filesystem]
- Temperatura: 0.2

## Tool Budget

- **Tool count**: 11 su limite 20 (P9 ampiamente rispettato)
- **Nuovo MCP**: markitdown-mcp (Microsoft, MIT, Context7 Bench 90.05)
- **Keyless**: nessuna API key richiesta

## Key Decisions

- Boundary strict: NO accesso diretto a Gmail/Calendar/Drive (Q1 = delega B)
- HITL via REPL locale, mai Telegram (Q8)
- Niente OCR, niente audio transcription (Q3, Q5, Q6 = no)
- Stile email dinamico per-recipient, nessuna lesson statica (Q7)
- Knowledge base esterna (Obsidian/Notion) non integrata (Q11 = nessuna)

## File Layout

```
src/aria/agents/productivity/
├── __init__.py            # Module docstring
├── ingest.py              # Office file ingestion (detect_format, hash_file, parse_markitdown_output, IngestResult)
├── synthesizer.py         # Multi-doc brief composition (compose_brief, BriefOutline, render_markdown)
├── meeting_prep.py        # Meeting briefing (MeetingBrief, build_meeting_brief, render_meeting_brief)
└── email_style.py         # (Sprint 2) Dynamic email style discovery (derive_style, draft_email, StyleProfile)

tests/
├── unit/agents/productivity/
│   ├── __init__.py
│   ├── test_ingest.py       # 25 tests
│   ├── test_synthesizer.py  # 10 tests
│   ├── test_meeting_prep.py # 14 tests
│   └── test_email_style.py  # 33 tests (Sprint 2)
├── integration/productivity/
│   ├── test_office_ingest_mcp.py  # 13 tests (2 E2E with real MCP)
│   └── test_email_draft_e2e.py   # 5 tests (Sprint 2, mock workspace-agent)
└── fixtures/office_files/
    ├── sample_notes.txt
    ├── sample_invoice.pdf
    ├── sample_proposal.docx
    ├── sample_budget.xlsx
    └── sample_pitch.pptx
```

## References

- ADR-0008: `docs/foundation/decisions/ADR-0008-productivity-agent-introduction.md`
- Foundation plan: `docs/plans/agents/productivity_agent_foundation_plan.md`
- Blueprint: `docs/foundation/aria_foundation_blueprint.md` §8.3.3, §8.5, §9.5, §15
- MCP: `github.com/microsoft/markitdown` (Context7 `/microsoft/markitdown` Bench 90.05)
- Research input: `docs/analysis/ricerca_mcp_produttività.md`
