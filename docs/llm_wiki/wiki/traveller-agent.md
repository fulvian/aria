# Traveller Agent

**Status**: ✅ v8.10 — shared-proxy caller contamination neutralized after research/travel cross-session drift
**Ultimo aggiornamento**: 2026-05-04T09:15
**Source**: `docs/plans/agents/traveller_agent_plan.md` (canonical), `docs/analysis/traveller_agent_analysis.md` (research v7.4)

**External analysis tracked**: `docs/analysis/traveller_amadeus_airbnb_issues.md` (2026-05-04, source-backed review of Airbnb robots blocking, Amadeus July 2026 sunset, candidate replacements)

## Overview

Sub-agente ARIA domain-primary per pianificazione e assistenza viaggi. Copre l'intero ciclo di vita: ideazione, trasporto, alloggio, esperienza locale, itinerario, esecuzione/monitoraggio. Consulente travel — **NON** booking executor in MVP (out-of-scope: prenotazioni live, pagamenti, OAuth provider).

## Stato attuale

| Fase | Stato |
|------|-------|
| Ricerca ecosistema | ✅ Completa (v7.4) |
| Foundation plan | ✅ Ratificato (v7.5) |
| **Fase 1 — capability matrix + prompt + conductor** | **✅ Completa (v7.6)** |
| Fase 2 — backend MCP (airbnb + osm-mcp + aria-amadeus-mcp catalog) | ✅ Completa (v7.7) |
| Fase 3 — `aria-amadeus-mcp` (FastMCP wrapper) | ✅ Completa (v7.8) |
| Fase 4 — skill core (destination + accommodation + transport) | ✅ Completa (v7.9) |
| Fase 5 — skill complementari + booking gated → **enabled** (v8.5) | ✅ Completa (v8.0→v8.5) |
| Fase 6 — export integration via productivity-agent | ✅ Completa (v8.1) |
| Fase 7 — observability + cost circuit breaker | ✅ Completa (v8.2) |
| Fase 8 — ADR-0017 + ADR-0018 + wiki sync | ✅ Completa (v8.3) |
| Fase 9 — smoke E2E | ✅ Completa (v8.4) |

## Backend MCP registrati (Fase 2 + 3 completata)

| Backend | Sorgente | Tool | Auth | Costo | Lifecycle |
|---------|----------|------|------|-------|-----------|
| `airbnb` | `npx @openbnb/mcp-server-airbnb` (⭐442, MIT) | `airbnb_search`, `airbnb_listing_details` | keyless | gratuito | enabled |
| `osm-mcp` | `uvx osm-mcp-server` | 12 tool (geocoding, POI, routes, explore) | keyless | gratuito | enabled |
| `aria-amadeus-mcp` | `scripts/wrappers/aria-amadeus-wrapper.sh` (FastMCP in `src/aria/tools/amadeus/mcp_server.py`) | 6 tool read-only | AMADEUS_CLIENT_ID/SECRET (SOPS) | gratuito (2K/mese) | enabled |

**Nota**: Google Maps Platform (`@cablate/mcp-google-map`) **escluso** — richiedeva billing account Google Cloud non attivabile. Sostituito con `osm-mcp-server` basato su OpenStreetMap (100% free, no API key, no billing).

## ADR ratificati (Fase 8 completata)

| ADR | Titolo | File |
|-----|--------|------|
| ADR-0017 | traveller-agent — travel domain sub-agent introduction | `docs/foundation/decisions/ADR-0017-traveller-agent-introduction.md` |
| ADR-0018 | aria-amadeus-mcp — local FastMCP wrapper for Amadeus | `docs/foundation/decisions/ADR-0018-aria-amadeus-mcp.md` |

Entrambi gli ADR sono marcati `Status: Implemented` e coprono: decisioni
architetturali, razionale, conseguenze, mitigazioni e riferimenti a file
di implementazione.

## Observability + anti-drift (Fase 7 completata)

### Eventi tipati
Nuovi eventi in `src/aria/observability/events.py`:
- `TravellerEvent` con `TravellerEventKind`: dispatch_received, skill_invoked, proxy_call, hitl_requested, hitl_resolved, export_delegated, amadeus_quota_warning

### Cost circuit breaker (aria-amadeus-mcp)
Integrato nel server FastMCP `mcp_server.py`:
- `_check_quota()`: conteggio chiamate con limite free tier (2000/mese)
- Warning a 90%: log warning
- Auto-quarantine a 100%: error 429, nessuna altra chiamata API
- `_reset_quota()` per reset mensile

### Anti-drift tests (16 test)
`tests/unit/agents/traveller/test_traveller_anti_drift.py`:
- source-of-truth: frontmatter allineato
- host tools: prompt vieta Glob/Read/Write/bash per travel
- HITL: solo hitl-queue__ask, mai conferma testuale
- Memory: 1 wiki_update per turn, wiki_recall a inizio
- Self-remediation: no edit codice/config/kill
- Naming: server__tool wildcard

### ADR ratificati
| ADR | File | Stato |
|-----|------|-------|
| ADR-0017 | `docs/foundation/decisions/ADR-0017-traveller-agent-introduction.md` | ✅ Implementato |
| ADR-0018 | `docs/foundation/decisions/ADR-0018-aria-amadeus-mcp.md` | ✅ Implementato |

## Handoff chain (Fase 6 completata)

La catena di delega per export è configurata su 3 livelli:

```
traveller-agent  ──spawn-subagent──▶  productivity-agent  ──proxy──▶  workspace-agent
    │                                       │
    │   export Drive/Calendar/email          │  Gmail/Calendar/Drive API
    │                                       │
    └──search-agent (solo contesto non travel, max depth 1)
```

- **Prompt**: sezione `## Delega` con regole esplicite
- **Conductor**: catene `traveller → productivity` e `traveller → search`
- **HITL**: tutte le write esterne passano per `hitl-queue__ask`
- **Depth guard**: `max_spawn_depth: 1` (traveller → productivity → workspace = 2 hop OK)
- **19 test integrazione** per handoff chain

## Skill implementate (Fase 4 + 5 completata)

| Skill | SKILL.md | Tool MCP usati |
|-------|----------|---------------|
| `destination-research` | `.aria/kilocode/skills/destination-research/SKILL.md` | osm-mcp__geocode_address, osm-mcp__explore_area |
| `accommodation-comparison` | `.aria/kilocode/skills/accommodation-comparison/SKILL.md` | airbnb__airbnb_search, aria-amadeus-mcp__hotel_*, osm-mcp__geocode_address |
| `transport-planning` | `.aria/kilocode/skills/transport-planning/SKILL.md` | aria-amadeus-mcp__flight_*, osm-mcp__geocode_address, osm-mcp__get_route_directions |

Skills registrate in `.aria/kilocode/skills/_registry.json` con category: `travel`.

Tutte le 6 skill sono state implementate (Fase 4 + Fase 5 completate).

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
ARIA Conductor → traveller-agent → proxy (airbnb, osm-mcp, booking, aria-amadeus-mcp) → backend
```

## Remediation v8.7 — runtime contract riallineato

- `search_tools` va invocato direttamente come `aria-mcp-proxy__search_tools(query=...)`
- `call_tool` va invocato direttamente come `aria-mcp-proxy__call_tool(name="server__tool", arguments={..., "_caller_id": "traveller-agent"})`
- Pattern errato rimosso: `aria-mcp-proxy__call_tool(name="call_tool", arguments={...})`
- `CapabilityMatrixMiddleware` ora:
  - nega `call_tool` senza caller identity
  - nega `call_tool` verso tool sintetici (`search_tools`, `call_tool`)
  - reintroduce il controllo capability sul backend target
- `scripts/wrappers/aria-amadeus-wrapper.sh` deve essere eseguibile; aggiunto test statico dedicato

## Remediation v8.8 — deep debug su Sessione 8

- Il traveller non deve più fermarsi al primo backend fallito: continua in **degraded mode** se almeno un backend travel utile sopravvive.
- `transport-planning` ora codifica fallback esplicito:
  - `nearest_airport` fallisce → provare `locations_search`
  - `flight_offers_search` instabile → evitare burst paralleli e delegare a `search-agent` solo come fallback grounded
- `accommodation-comparison` ora codifica fallback esplicito:
  - `airbnb` `robots.txt` → proseguire con Booking + Amadeus superstite
  - `hotel_list_by_geocode` fallisce → tentare `hotel_offers_search(city_code=...)`
  - Booking come unico backend superstite → usare anche sort/filter tools
- `budget-analysis` ora ammette budget parziale esplicito quando i provider di pricing live falliscono.
- `aria-amadeus-mcp` ora restituisce errori strutturati con:
  - `retryable`
  - `reason` (`upstream_rate_limited`, `upstream_error`, `local_quota_exhausted`, ...)
  - `fallback_hint`
  - un retry leggero su `429/5xx`

## Remediation v8.9 — persistent Amadeus 38189

- Riprodotto localmente che le credenziali Amadeus correnti, sul test environment,
  restituiscono `500` provider code `38189 Internal error` su tutti gli endpoint
  travel principali provati (`locations`, `airports`, `hotels`, `flight offers`).
- Verificato via documentazione ufficiale che i metodi Python usati sono corretti;
  il problema non è un semplice errore di parametri nel wrapper.
- Le stesse credenziali in `hostname='production'` restituiscono `401 invalid_client`:
  non sono credenziali production-ready.
- `aria-amadeus-mcp` ora:
  - tratta `38189` come `upstream_internal_error` non retryable
  - entra in quarantena temporanea locale dopo failure sistemiche ripetute
  - restituisce `upstream_service_quarantined` per evitare retry inutili nella stessa sessione
- `search-agent` ora ha un boundary esplicito: non deve mai usare backend MCP travel
  (`aria-amadeus-mcp`, `booking`, `airbnb`, `osm-mcp`) via proxy.

## Remediation v8.10 — shared proxy caller contamination

- Una sessione research `search-agent` poteva ancora comportarsi come `traveller-agent`
  se il proxy ereditava un `ARIA_CALLER_ID=traveller-agent` dal `.env` locale.
- Effetto osservato nei log: discovery centrata su tool travel e denial come
  `fetch__fetch not allowed for traveller-agent` durante task di ricerca.
- Fix applicato nel proxy:
  - il boot filtering ora usa solo `ARIA_PROXY_BOOT_CALLER_ID`
  - `call_tool` richiede `_caller_id` esplicito e non prende più il caller
    da env legacy condivise
  - esempi prompt/skill di discovery aggiornati con `_caller_id`

## Stato strategico backend traveller (2026-05-04)

- **Airbnb MCP**: funzionalmente fragile per dipendenza da scraping e controllo `robots.txt`; l'analisi dettagliata e le opzioni correttive sono archiviate in `docs/analysis/traveller_amadeus_airbnb_issues.md`.
- **Amadeus Self-Service**: oltre all'instabilità corrente del test env (`38189`), il backend ha rischio di obsolescenza strutturale per sunset del portale Self-Service a luglio 2026; la wiki mantiene qui lo stato operativo corrente, mentre il documento di analisi raccoglie le alternative candidate (Duffel, LetsFly/LetsFG, toolkit travel-hacking, Booking-first fallback).
- **Implicazione di governance**: il fix odierno risolve il misrouting tra agenti, ma non elimina il debito architetturale dei backend travel upstream; le prossime decisioni dovranno separare chiaramente remediation runtime da migrazione provider.

## Riferimenti

- `docs/plans/agents/traveller_agent_plan.md` — foundation plan completo (9 fasi TDD)
- `docs/analysis/traveller_amadeus_airbnb_issues.md` — analisi estesa di fragilità Airbnb + sunset Amadeus + alternative provider
- `.aria/kilocode/agents/traveller-agent.md` — prompt canonico
- `.aria/config/agent_capability_matrix.yaml` — capability matrix
- `.aria/kilocode/agents/aria-conductor.md` — conductor dispatch rules
