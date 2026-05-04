# Traveller Agent — Analisi e Proposte di Risoluzione

> **Data**: 2026-05-04
> **Autore**: ARIA Conductor / Ricerca sub-agenti (search-agent, code-discovery)
> **Stato**: Bozza di analisi — richiede validazione e implementazione
> **Progetto**: ARIA — traveller-agent backend MCP

---

## Indice

1. [Sommario Esecutivo](#1-sommario-esecutivo)
2. [Problema 1: Airbnb MCP — robots.txt blocking](#2-problema-1-airbnb-mcp--robotstxt-blocking)
   - 2.1 Contesto
   - 2.2 Indagine tecnica
   - 2.3 Analisi del codice
   - 2.4 Impatto sul traveller-agent
   - 2.5 Soluzioni proposte
   - 2.6 Raccomandazione
3. [Problema 2: Amadeus Self-Service API Sunset (Luglio 2026)](#3-problema-2-amadeus-self-service-api-sunset-luglio-2026)
   - 3.1 Contesto e conferma
   - 3.2 Cosa cambia esattamente
   - 3.3 Impatto su aria-amadeus-mcp
   - 3.4 Alternative valutate
   - 3.5 Soluzioni proposte
   - 3.6 Raccomandazione
4. [Piano di Implementazione](#4-piano-di-implementazione)
5. [Riferimenti](#5-riferimenti)

---

## 1. Sommario Esecutivo

Il traveller-agent di ARIA ha due criticità sui backend MCP che ne minano l'affidabilità
e la sostenibilità a medio termine:

| # | Problema | Gravità | Urgenza | Impatto |
|---|----------|---------|---------|---------|
| 1 | **Airbnb MCP**: restituisce errore robots.txt su ogni chiamata `airbnb_search` perché Airbnb's `robots.txt` disallowa `/s/*/homes` per tutti gli user-agent. | **Alta** — bloccante per la funzionalità Airbnb. | **Immediata** — il tool non funziona in configurazione default. | Ricerca vacation rental disabilitata. |
| 2 | **Amadeus API**: Amadeus decommissiona l'intero Self-Service API portal il **17 Luglio 2026**. Tutte le API key Self-Service verranno disattivate. | **Critica** — l'intero backend aria-amadeus-mcp cessa di funzionare a luglio. | **Media** (73 giorni) — va risolto prima della scadenza. | Voli, hotel GDS e location search completamente disabilitati. |

---

## 2. Problema 1: Airbnb MCP — robots.txt blocking

### 2.1 Contesto

Il backend `airbnb` è registrato nel catalogo MCP come:
```yaml
source_of_truth: npx -y @openbnb/mcp-server-airbnb
```

Package npm: `@openbnb/mcp-server-airbnb` (v0.1.4 npm, v0.2.0 GitHub)
GitHub: `openbnb-org/mcp-server-airbnb` (⭐442, 105 forks, MIT)
Repo attività: 22 commit totali, ultimo commit 2026-04-14

Il server espone 2 tool:
- `airbnb_search` — ricerca alloggi per località, date, ospiti
- `airbnb_listing_details` — dettagli di un annuncio specifico

### 2.2 Indagine tecnica — Root cause

Il server implementa **web scraping puro** di `airbnb.com`:

1. Costruisce URL: `https://www.airbnb.com/s/{slug}/homes`
2. Prima di fetchare, **verifica il path contro `robots.txt`** usando la libreria `robots-parser`
3. Airbnb's `robots.txt` contiene:

```robotstxt
User-agent: *
Disallow: /s/*?
Disallow: /s/*/homes
```

**Il path `/s/*/homes` è disallow per TUTTI gli user-agent**, incluso quello generico.
Il server usa User-Agent `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36`
che matcha `*`.

Il risultato è un errore strutturato:
```json
{
  "error": "This path is disallowed by Airbnb's robots.txt to this User-agent. You may or may not want to run the server with '--ignore-robots-txt' args"
}
```

**Questo NON è un bug del tool MCP** — è un comportamento voluto. Il server ha un
meccanismo di compliance robots.txt che blocca le richieste a percorsi disallow.

### 2.3 Cosa restituisce — chiarimento

L'utente segnala "restituisce robots.txt" — più precisamente:
- Il server **non** restituisce il contenuto di robots.txt come risposta
- Restituisce un **errore applicativo** che dice "path disallowed by robots.txt"
- L'agente AI interpreta questo messaggio come "robots.txt content" quando il testo
  dell'errore viene incluso nel prompt
- **Non c'è fallback** — il server blocca completamente la richiesta

### 2.4 Impatto sul traveller-agent

La skill `accommodation-comparison` prescrive chiamata OBBLIGATORIA a
`airbnb__airbnb_search` nella sua pipeline. Con il robots.txt blocking:

1. `airbnb_search` fallisce sempre in configurazione default
2. La skill ha degraded mode prevista (Airbnb down → usa Amadeus + Booking)
3. Ma Airbnb non è "down" — è bloccato da robots.txt, che degraded mode non distingue
4. Booking è gated e Amadeus ha i suoi problemi (errore 38189 persistente)
5. Risultato netto: **accommodation comparison è effettivamente rotto al 100%**

### 2.5 Soluzioni proposte

#### Soluzione A: `--ignore-robots-txt` flag (RAPIDA — 5 min)

Modificare `source_of_truth` in `mcp_catalog.yaml`:

```yaml
source_of_truth: npx -y @openbnb/mcp-server-airbnb --ignore-robots-txt
```

**Pro**: Fix immediato, bypassa il robots.txt check lato client.
**Contro**:
- Airbnb potrebbe comunque bloccare a livello server (CAPTCHA, IP block, rate limit)
- Airbnb ha aggiunto blocchi specifici per AI bot (`ClaudeBot`, `anthropic-ai`, `GPTBot`)
- La risorsa `#data-deferred-state-0` potrebbe sparire in futuro
- Questione etico-legale: ignorare robots.txt esplicitamente
- Airbnb cambia struttura HTML periodicamente (già successo, v0.1.1 fix)

#### Soluzione B: openbnb.ai hosted service (MEDIO TERMINE)

Il maintainer offre ora un hosted MCP server su `mcp.openbnb.ai/mcp`:
- Richiede connessione esterna (no locale)
- Gestione scraping lato server
- Free tier disponibile
- Supporta ChatGPT, Claude, MCP client

**Pro**: Manutenzione a carico del provider, funzionalità extra.
**Contro**: Dipendenza esterna, latenza di rete, SLA non garantito.

#### Soluzione C: Disabilitare Airbnb come backend MCP e reindirizzare su Booking

Booking ha un backend MCP (`@striderlabs/mcp-booking`) via Playwright, lifecycle `gated`.

**Pro**: Booking ha API più stabile via Playwright (browser automation vs HTML parsing).
**Contro**: Richiede abilitazione Booking + risorse browser (Playwright), solo hotel (no case vacanze).

#### Soluzione D: Sostituire Airbnb con scraper alternativo

Non ci sono fork significativi che risolvano diversamente il robots.txt issue.
Tutti i 105 fork sono personali senza modifiche sostanziali.
Una possibilità: creare un wrapper locale che ignori robots.txt nativamente.

#### Soluzione E: Usare `travel-hacking-toolkit` per Airbnb

`borski/travel-hacking-toolkit` (⭐467) include un MCP server Airbnb come parte
del toolkit. Ha 6 MCP server, di cui 5 free (Airbnb, Kiwi, Skiplagged, Trivago, Ferryhopper).

**Pro**: Già collaudato, ampia adozione.
**Contro**: Airbnb è solo una parte del toolkit (overhead inutile per un solo backend).

### 2.6 Raccomandazione

**Short-term (oggi)**: Applicare Soluzione A — aggiungere `--ignore-robots-txt` alla
configurazione del backend Airbnb. È il minimo sforzo per sbloccare la funzionalità.

**Medium-term**: Valutare Soluzione E (travel-hacking-toolkit) come parte della
migrazione più ampia verso un ecosistema MCP più robusto. Il toolkit include
già Kiwi (utile per la sostituzione Amadeus — vedi sezione 3).

**Considerazione architetturale**: Airbnb è l'unico backend MCP del traveller-agent
basato su web scraping invece che su API ufficiali. La fragilità è intrinseca.
Un'alternativa a lungo termine sarebbe integrare Booking.com (che ha API ufficiale
via Partner Program) per coprire sia hotel che case vacanze.

---

## 3. Problema 2: Amadeus Self-Service API Sunset (Luglio 2026)

### 3.1 Contesto e conferma

**Amadeus sta dismettendo l'intero Self-Service API portal il 17 Luglio 2026.**

Tutte le API key Self-Service verranno disattivate. Nuove registrazioni sono state
sospese da Marzo 2026. La conferma proviene da:
- Annunci ufficiali sul portale developers.amadeus.com
- Comunicazioni email agli sviluppatori registrati
- Forum della community Amadeus for Developers

**Non esiste un piano "Developer" sostitutivo.** L'unica opzione Amadeus post-July 2026
è **Amadeus Enterprise (Quick Connect / AQC)** che richiede:
- IATA accreditation (o sponsorizzazione tramite consolidatore)
- Contratto commerciale firmato
- Volume minimo di transazioni
- Commissioni di setup: stimate $1,000–$10,000+
- Minimi mensili: $500–$5,000+
- Processo di integrazione certificato

**L'Enterprise path non è fattibile per un progetto personale/hobby.**

### 3.2 Cosa cambia esattamente

| Aspetto | Prima (Self-Service) | Dopo (Enterprise) |
|---------|---------------------|-------------------|
| **Costo** | Free tier (2K/mese) + Paid tier | Minimo $500/mese + setup fee |
| **Onboarding** | Self-service, chiavi immediate | Contratto, IATA, settimane/mesi |
| **API Surface** | 6+ endpoint flight/hotel/location | Full GDS (booking, pricing, inventory) |
| **Low-cost carriers** | ❌ Esclusi | Dipende dal contratto |
| **MCP Server** | Custom (aria-amadeus-mcp) | Non esistente, da costruire |

### 3.3 Impatto su aria-amadeus-mcp

L'attuale implementazione (`src/aria/tools/amadeus/mcp_server.py`, 638 linee) fornisce
6 tool read-only:
- `flight_offers_search` — ricerca voli
- `hotel_offers_search` — ricerca hotel
- `hotel_list_by_geocode` — hotel per coordinate
- `locations_search` — ricerca aeroporti/città
- `nearest_airport` — aeroporto più vicino
- `flight_status` — stato volo

**Nessuno di questi funzionerà dopo il 17 Luglio 2026.**

### 3.4 Alternative valutate

#### Alternative per voli

| API | Flight Search | Low-Cost | Free Tier | Onboarding | MCP Server | Voto |
|-----|:---:|:---:|:---:|:---:|:---:|:---:|
| **LetsFG** (916⭐) | ✅ | ✅ (400+ airlines) | ✅ 100% free | Nessuno (npx) | `npx letsfg-mcp` | ⭐⭐⭐⭐⭐ |
| **Duffel** | ✅ | ✅ (150+ airlines) | ✅ Free search | Istantaneo (5-30 min) | `ravinahp/flights-mcp` (189⭐) | ⭐⭐⭐⭐ |
| **Kiwi Tequila** | ✅ Virtual interlining | ✅ Ryanair, Wizz, etc. | ✅ Limitato | Istantaneo | via travel-hacking-toolkit (467⭐) | ⭐⭐⭐⭐ |
| **travel-hacking-toolkit** | ✅ Multi (Kiwi, Skiplagged) | ✅ | ✅ 5 server free | Nessuno | Incluso nel toolkit | ⭐⭐⭐⭐ |
| Skyscanner | ❌ Solo business | — | ❌ | 2 settimane review | ❌ | ⭐ |
| AviationStack | ❌ Solo status | — | 100 req/mese | Istantaneo | ❌ | ⭐ |

#### Alternative per hotel

| API | Hotel Search | Free Tier | Onboarding | MCP Server |
|-----|:---:|:---:|:---:|:---:|
| **Duffel** (Stays) | ✅ | ✅ Free search | Istantaneo | `clockworked247/flights-mcp-ts` |
| **Booking** (via Browser) | ✅ | ✅ Gratuito | Istantaneo | `@striderlabs/mcp-booking` |
| **LetsFG** | ❌ Soli voli | — | — | — |

#### Alternative per location/airport lookup + geocoding

| API | Geocoding | Airport Lookup | Free | Già in uso |
|-----|:---:|:---:|:---:|:---:|
| **osm-mcp** (OpenStreetMap) | ✅ | Parziale (via Overpass) | ✅ 100% | ✅ Già integrato |
| **Nominatim** | ✅ | ❌ | ✅ Rate-limited | ✅ Usato da openbnb |
| **Photon** (Komoot) | ✅ | ❌ | ✅ | ✅ Usato da openbnb |

### 3.5 Soluzioni proposte

#### Soluzione A: Migrare a Duffel API (PRIMARIA — RACCOMANDATA)

**Backend**: Duffel API via `ravinahp/flights-mcp` (Python, 189⭐) o wrapper custom.
**Cosa copre**: Flight search (con low-cost), hotel search (Stays), car rental.
**Costo**: Ricerca gratuita, solo $3/ordine se si prenota (non previsto in MVP).
**Onboarding**: 5-30 minuti, chiave test immediata, live con carta di credito.

**Workflow proposto**:
1. Creare `src/aria/tools/duffel/mcp_server.py` (simile a aria-amadeus-mcp)
2. Registrare backend `aria-duffel-mcp` nel catalogo MCP
3. Mantenere la stessa interfaccia di 6 tool (flight_offers_search, hotel_offers_search, ecc.)
4. Aggiungere API key Duffel in SOPS (`api-keys.enc.yaml`)

**Vantaggi rispetto a Amadeus**:
- Inclusione low-cost carriers (Ryanair, Wizz Air, EasyJet, etc.)
- Hotel search nativo (non solo GDS)
- Nessun limite di tier mensile per la ricerca
- Onboarding istantaneo
- MCP server Python già pronto come riferimento

#### Soluzione B: LetsFG come backend flight search (COMPLEMENTARE)

**Backend**: `npx letsfg-mcp` — 100% free, nessuna API key, 400+ airlines.
**Cosa copre**: Voli con low-cost, virtual interlining (combinazione voli).
**Costo**: Zero.
**Onboarding**: Nessuno — `npx letsfg-mcp` immediato.

**Vantaggi unici**:
- Copre Ryanair, Wizz Air, EasyJet, Southwest, Spirit, Norwegian
- Virtual interlining (es. Ryanair outbound + Wizz Air return)
- Zero configurazione
- MCP server nativo

**Workflow proposto**:
1. Aggiungere backend `letsfg` nel catalogo MCP: `npx letsfg-mcp`
2. Aggiornare la skill `transport-planning` per chiamare `letsfg__*` invece di `aria-amadeus-mcp__*`
3. Convive con Duffel come fonte di dati alternativa

#### Soluzione C: travel-hacking-toolkit (ALTERNATIVA COMPOSITA)

**Backend**: `borski/travel-hacking-toolkit` (467⭐, Python) — include 6 MCP server:
- **Kiwi.com** (gratuito, no API key) — voli con low-cost
- **Skiplagged** — voli
- **Trivago** — hotel
- **Airbnb** — vacation rental
- **Ferryhopper** — traghetti
- **Seats.aero** — award flights

**Costo**: Zero (5 dei 6 server sono free).
**Vantaggio**: Copre sia voli che hotel che Airbnb in unico ecosistema.

#### Soluzione D: Duffel + LetsFG + osm-mcp (COMBINAZIONE RACCOMANDATA)

La strategia più robusta combina:
- **Duffel** → flight search strutturato (GDS-simile a Amadeus)
- **LetsFG** → low-cost carriers + virtual interlining
- **osm-mcp** → geocoding + airport lookup (sostituisce locations_search + nearest_airport)
- **Booking** → hotel (sostituisce hotel GDS search)

Questo schema preserva il pattern multi-backend già adottato dal traveller-agent,
con un backend primario e un fallback per ogni dominio.

#### Tabella comparativa strumento-per-strumento

| Tool Amadeus | Sostituto Primario | Sostituto Fallback |
|---|---|---|
| `flight_offers_search` | Duffel flight offers | LetsFG flight search |
| `hotel_offers_search` | Booking hotel search | Duffel Stays |
| `hotel_list_by_geocode` | Booking + osm-mcp geocoding | Duffel geo search |
| `locations_search` | osm-mcp geocoding + Photon/Nominatim | — |
| `nearest_airport` | osm-mcp poi + Photon reverse geocode | — |
| `flight_status` | AviationStack (gratuito 100 req/mese) | AeroDataBox (free 600 unità/mese) |

### 3.6 Raccomandazione

**Strategy**: Combinazione Duffel (primario) + LetsFG (complementare low-cost).

**Timeline**:
1. **Entro 30 giorni** (Giugno 2026): Implementare Duffel MCP server come sostituto primario
2. **Entro 60 giorni** (Luglio 2026 prima del sunset): Aggiungere LetsFG come fallback, testare integrazione end-to-end
3. **17 Luglio 2026**: Disabilitare aria-amadeus-mcp, rendere Duffel + LetsFG operativi
4. **Post-Luglio**: Valutare se integrare anche travel-hacking-toolkit per copertura extra

**Note**:
- `osm-mcp` è già integrato e 100% free — va espanso per coprire location/airport lookup che
  ora fa Amadeus
- Booking è già registrato come backend gated — va promosso a enabled per hotel search
- Flight status (tracking) ha alternative gratuite ma non è critico per MVP

---

## 4. Piano di Implementazione

### Fase 0 — Quick Fix Airbnb (oggi)

| Azione | File | Dettaglio |
|--------|------|-----------|
| Aggiungere `--ignore-robots-txt` | `.aria/config/mcp_catalog.yaml` | Modificare `source_of_truth` del backend `airbnb` |
| Aggiornare wiki con lesson | wiki_update | Registrare decisione: Airbnb richiede `--ignore-robots-txt` |
| Testare funzionamento | Manuale | Chiamare `airbnb_search` e verificare risposta |

**Stima**: 15 minuti.

### Fase 1 — Duffel MCP Server (Giugno 2026)

| Azione | File | Dettaglio |
|--------|------|-----------|
| Creare `src/aria/tools/duffel/mcp_server.py` | Nuovo file | FastMCP server con tool flight + hotel search |
| Registrare backend `aria-duffel-mcp` | `.aria/config/mcp_catalog.yaml` | Nuovo backend tier 1 |
| Ottenere API key Duffel | Duffel dashboard | Test mode + live mode |
| Salvare credenziale in SOPS | `.aria/credentials/secrets/api-keys.enc.yaml` | `providers.duffel.api_key` |
| Scrivere test unitari | `tests/unit/agents/traveller/test_duffel_server.py` | Mock API Duffel |
| Scrivere test integrazione | `tests/integration/agents/traveller/` | End-to-end con Duffel sandbox |

**Stima**: 3-5 giorni lavorativi.

### Fase 2 — LetsFG Backend (Giugno-Luglio 2026)

| Azione | File | Dettaglio |
|--------|------|-----------|
| Aggiungere backend `letsfg` nel catalogo | `.aria/config/mcp_catalog.yaml` | `npx letsfg-mcp` |
| Aggiornare skill `transport-planning` | `.aria/kilocode/skills/transport-planning/SKILL.md` | Aggiungere tool LetsFG |
| Aggiornare traveller-agent prompt | `.aria/kilocode/agents/traveller-agent.md` | Aggiungere backend + esempi proxy |

**Stima**: 1-2 giorni lavorativi.

### Fase 3 — Degradare Amadeus (Luglio 2026)

| Azione | File | Dettaglio |
|--------|------|-----------|
| Impostare lifecycle `disabled` per aria-amadeus-mcp | `.aria/config/mcp_catalog.yaml` | Dopo il 17 Luglio 2026 |
| Aggiornare ADR-0018 | `docs/foundation/decisions/ADR-0018-aria-amadeus-mcp.md` | Stato → `Deprecated` |
| Rimuovere credenziali Amadeus da SOPS | (opzionale) | Se non più utilizzate per altro |

**Stima**: 30 minuti.

### Fase 4 — Booking da gated a enabled (opzionale)

| Azione | File | Dettaglio |
|--------|------|-----------|
| Promuovere Booking a enabled | `.aria/config/mcp_catalog.yaml` | lifecycle: shadow → enabled |
| Aggiornare degraded mode skill | `.aria/kilocode/skills/accommodation-comparison/SKILL.md` | Booking come default |

**Stima**: 1 ora.

---

## 5. Riferimenti

### Repo e package

| Risorsa | URL |
|---------|-----|
| openbnb-org/mcp-server-airbnb | https://github.com/openbnb-org/mcp-server-airbnb |
| openbnb.ai (hosted) | https://openbnb.ai/ |
| ravinahp/flights-mcp (Duffel, Python) | https://github.com/ravinahp/flights-mcp |
| clockworked247/flights-mcp-ts (Duffel, TS) | https://github.com/clockworked247/flights-mcp-ts |
| LetsFG (916⭐, flight search) | https://github.com/LetsFG/LetsFG |
| travel-hacking-toolkit (467⭐) | https://github.com/borski/travel-hacking-toolkit |
| Duffel API docs | https://duffel.com/docs |
| Kiwi Tequila API | https://tequila.kiwi.com |
| Amadeus for Developers | https://developers.amadeus.com |

### Documenti ARIA correlati

| Documento | Percorso |
|-----------|----------|
| ADR-0017 (traveller-agent) | `docs/foundation/decisions/ADR-0017-traveller-agent-introduction.md` |
| ADR-0018 (aria-amadeus-mcp) | `docs/foundation/decisions/ADR-0018-aria-amadeus-mcp.md` |
| Traveller Agent wiki | `docs/llm_wiki/wiki/traveller-agent.md` |
| Traveller backend setup | `docs/operations/traveller-backend-setup.md` |
| Accommodation comparison skill | `.aria/kilocode/skills/accommodation-comparison/SKILL.md` |
| MCP catalog | `.aria/config/mcp_catalog.yaml` |
| aria-amadeus-mcp server | `src/aria/tools/amadeus/mcp_server.py` |

### Issues Airbnb MCP notevoli

| Issue | Stato | Descrizione |
|-------|-------|-------------|
| [#10](https://github.com/openbnb-org/mcp-server-airbnb/issues/10) | Chiusa | Primo report robots.txt blocking (2025-05-04) |
| [#21](https://github.com/openbnb-org/mcp-server-airbnb/issues/21) | **Aperta** | Claude desktop + robots.txt (2026-01-26) |
| [#26](https://github.com/openbnb-org/mcp-server-airbnb/pull/26) | **Aperta** | Retry con exponential backoff su HTTP 429 |

---

## Appendice: Degraded mode matrix (aggiornata)

Dopo le modifiche proposte, la matrice di degraded mode dell'accommodation-comparison
diventa:

| Scenario | Backend superstiti | Azione |
|----------|-------------------|--------|
| Tutti OK | Duffel + LetsFG + Booking + osm-mcp | Confronto completo |
| Duffel down | LetsFG + Booking + osm-mcp | Degraded mode: voli LetsFG, hotel Booking |
| LetsFG down | Duffel + Booking + osm-mcp | Degraded mode: solo GDS + hotel |
| Booking down | Duffel + LetsFG + osm-mcp | Degraded mode: solo voli + geocoding |
| Airbnb down (robots) | Booking solo per alloggi | Degraded mode: solo hotel Booking |
| Duffel + LetsFG giù | Booking (hotel) + osm-mcp (geo) | Degraded mode: solo alloggi |
| Tutti giù | — | "Backend travel non disponibili" |

---

> **Nota**: Questo report è un'analisi preliminare basata su ricerche web e
> documentazione. Prima dell'implementazione, ogni soluzione proposta richiede
> validazione tecnica e, per modifiche distruttive/costose, passa attraverso
> il gate HITL (Human-in-the-Loop).
