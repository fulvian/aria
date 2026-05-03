# Traveller Agent

**Status**: ✅ Fase 1 completata (v7.6) — Foundation runtime integration
**Ultimo aggiornamento**: 2026-05-03T20:00
**Source**: `docs/plans/agents/traveller_agent_plan.md` (canonical), `docs/analysis/traveller_agent_analysis.md` (research v7.4)

## Overview

Sub-agente ARIA domain-primary per pianificazione e assistenza viaggi. Copre l'intero ciclo di vita: ideazione, trasporto, alloggio, esperienza locale, itinerario, esecuzione/monitoraggio. Consulente travel — **NON** booking executor in MVP (out-of-scope: prenotazioni live, pagamenti, OAuth provider).

## Stato attuale

| Fase | Stato |
|------|-------|
| Ricerca ecosistema | ✅ Completa (v7.4) |
| Foundation plan | ✅ Ratificato (v7.5) |
| **Fase 1 — capability matrix + prompt + conductor** | **✅ Completa (v7.6)** |
| Fase 2 — backend MCP airbnb + google-maps | ⏳ Pending |
| Fase 3 — `aria-amadeus-mcp` (FastMCP wrapper) | ⏳ Pending |
| Fase 4 — skill core (destination + accommodation) | ⏳ Pending |
| Fase 5 — skill complementari + booking gated | ⏳ Pending |
| Fase 6 — export integration via productivity-agent | ⏳ Pending |
| Fase 7 — observability + cost circuit breaker | ⏳ Pending |
| Fase 8 — ADR-0017 + ADR-0018 + wiki sync | ⏳ Pending |
| Fase 9 — smoke E2E | ⏳ Pending |

## Runtime Integration (Fase 1 completata)

| Touchpoint | File | Stato |
|-----------|------|-------|
| Prompt canonico | `.aria/kilocode/agents/traveller-agent.md` | ✅ |
| Prompt mirror | `.aria/kilo-home/.kilo/agents/traveller-agent.md` | ✅ (gitignored) |
| Capability matrix | `.aria/config/agent_capability_matrix.yaml` | ✅ entry + conductor delegation |
| Conductor dispatch | `.aria/kilocode/agents/aria-conductor.md` | ✅ 30+ keyword + 7 intent rules |
| Test prompt | `tests/unit/agents/traveller/test_traveller_agent_prompt.py` | ✅ 27 test |
| Test matrix | `tests/unit/agents/traveller/test_traveller_capability_matrix.py` | ✅ 14 test |
| Test conductor | `tests/unit/agents/test_conductor_dispatch.py` | ✅ 26 test |

## Intent categories

| Intent | Descrizione |
|--------|-------------|
| `travel.destination` | Ricerca destinazioni, info clima/cultura/visto |
| `travel.transport` | Voli, treni, transfer, noleggio (read-only) |
| `travel.accommodation` | Confronto multi-OTA Airbnb/Booking/Amadeus-hotel |
| `travel.activity` | POI, ristoranti, eventi, tour |
| `travel.itinerary` | Pianificazione giorno-per-giorno con route optimization |
| `travel.budget` | Stima costi e breakdown per categoria |
| `travel.brief` | Travel Brief completo end-to-end |

## Architettura target

**Pattern**: ARIA-native hub-and-spoke. **NO** LangGraph runtime.

```
ARIA Conductor → traveller-agent → proxy (airbnb, google-maps, booking, aria-amadeus-mcp) → backend
```

## Riferimenti

- `docs/plans/agents/traveller_agent_plan.md` — foundation plan completo (9 fasi TDD)
- `.aria/kilocode/agents/traveller-agent.md` — prompt canonico
- `.aria/config/agent_capability_matrix.yaml` — capability matrix
- `.aria/kilocode/agents/aria-conductor.md` — conductor dispatch rules
