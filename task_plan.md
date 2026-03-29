# ARIA Implementation Plan

## Current Status
**FASE 0-4: COMPLETE ✅**  
**FASE 5: Specialized Agencies - IN PROGRESS (PLANNING COMPLETE)**

---

## FASE 0-4 Summary

| Fase | Stato | Note |
|------|-------|------|
| FASE 0: Foundation | 100% ✅ | Namespace, schema DB, interfacce |
| FASE 1: Core System | 100% ✅ | Orchestrator, Development Agency, Skill System, Routing |
| FASE 2: Memory & Learning | 100% ✅ | E2E test completato |
| FASE 3: Scheduling | 100% ✅ | Scheduler, task persistence, recurring tasks, TUI |
| FASE 4: Proactivity | 100% ✅ | Guardrails, permissions |

---

## FASE 5: Specialized Agencies

**Durata**: 8-12 settimane  
**Obiettivo**: Implementare agencies specializzate oltre Development

### Overview

FASE 5 implementa le agencies specializzate che estendono ARIA oltre il dominio di sviluppo.

### Agencies Target

| Agency | Dominio | Complessità | Status |
|--------|---------|-------------|--------|
| Knowledge | Research, learning, Q&A | Media | Planning |
| Creative | Writing, design, content | Media | Planning |
| Productivity | Planning, scheduling, organization | Alta | Planning |
| Personal | Health, finance, lifestyle | Bassa | Planning |
| Analytics | Data analysis, visualization | Alta | Planning |

### Piano Dettagliato
- `docs/plans/2026-03-29-fase5-agencies-implementation-plan.md`

### 5.1 Implementation Order

1. **Knowledge Agency** (Settimana 1-2)
   - web search/scrape tools
   - Researcher agent

2. **Creative Agency** (Settimana 3-4)
   - Writer, Translator agents
   - Template system

3. **Productivity Agency** (Settimana 5-7)
   - Calendar integration
   - Planner, Scheduler agents

4. **Personal Agency** (Settimana 7-8)
   - Assistant agent
   - Wellness, Finance basics

5. **Analytics Agency** (Settimana 9-11)
   - Data loading
   - Analysis, Visualization agents

### 5.2 Tasks

#### Knowledge Agency
- [ ] Creare `internal/aria/agency/knowledge.go`
- [ ] Implementare web search/scrape tools
- [ ] Researcher, Educator, Analyst agents

#### Creative Agency
- [ ] Creare `internal/aria/agency/creative.go`
- [ ] Implementare Writer, Translator, Designer agents
- [ ] Template system

#### Productivity Agency
- [ ] Creare `internal/aria/agency/productivity.go`
- [ ] Calendar integration
- [ ] Planner, Scheduler, Organizer agents

#### Personal Agency
- [ ] Creare `internal/aria/agency/personal.go`
- [ ] Assistant, Wellness, Finance agents

#### Analytics Agency
- [ ] Creare `internal/aria/agency/analytics.go`
- [ ] Data loading, transformation
- [ ] Analyst, Visualizer, Reporter agents

#### Agency Registry
- [ ] Aggiornare `internal/aria/agency/registry.go`
- [ ] Configurazione in `internal/aria/config`

---

## FASE 5 Deliverables

- [ ] Knowledge Agency funzionante
- [ ] Creative Agency funzionante
- [ ] Productivity Agency funzionante
- [ ] Personal Agency funzionante
- [ ] Analytics Agency funzionante
- [ ] 20+ skills implementati
- [ ] MCP integrations per external tools
- [ ] Comprehensive testing

---

## Technical Notes

### Dependencies
- `internal/aria/agency.Agency` (interface esistente)
- `internal/aria/skill.Skill` (skills system esistente)
- `internal/aria/config` (configurazione agencies)

### Tools Esterni da Integrare

| Tool | Provider | Uso |
|------|----------|-----|
| Tavily | tavily.ai | Web search/research |
| Brave Search | brave.com | Web search alternative |
| Perplexity | perplexity.ai | Research con AI |
| Google Calendar | Google API | Calendar integration |
| OpenWeather | openweathermap | Weather data |

---

## Verification Plan

1. `go build ./...` - Must pass
2. `go test ./internal/aria/agency/...` - Agency tests
3. Manual test: Query each agency with appropriate task
4. Integration test: Cross-agency task

---

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-28 | LegacyAgentWrapper pattern | Mantiene retrocompatibilità con agent esistente |
| 2026-03-28 | FASE 1 COMPLETE | Tutti i componenti core implementati |
| 2026-03-28 | FASE 2 Planning | Memory Service, Learning Loop, Self-Analysis |
| 2026-03-29 | FASE 5 Planning | Specialized agencies implementation plan |

---

## Next Phase (After FASE 5)
**FASE 6: Polish & Expand** - Refinement, performance optimization, new capabilities

---

## FASE 6: Polish & Expand (NOT STARTED)

**Durata**: Ongoing  
**Obiettivo**: Raffinamento e espansione

### Tasks

1. **Performance optimization**
   - Caching strategies
   - Query optimization
   - Parallel processing

2. **UX improvements**
   - TUI enhancements
   - Better error messages
   - Help system

3. **New capabilities**
   - Plugin system
   - Custom agencies
   - Community skills

4. **Community features**
   - Skill marketplace
   - Agency sharing
   - Template repository
