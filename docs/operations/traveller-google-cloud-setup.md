# Traveller Agent — Google Cloud Setup

> **Scopo**: Creare un progetto Google Cloud e generare API key per Google Maps Platform (Places, Routes, Geocoding) da usare con `@cablate/mcp-google-map` via proxy ARIA.
>
> **Stato**: ⏳ Setup required
> **Owner**: Fulvio Ventura
> **Creato**: 2026-05-03
> **Source**: `docs/plans/agents/traveller_agent_plan.md` §Fase 2 Step 2.1

## Prerequisiti

- Account Google (già esistente per Google Workspace)
- Browser web
- Carta di credito (richiesta da Google Cloud per attivazione fatturazione — ma le API Maps hanno quote gratuite sufficienti per MVP)

## Procedura

### Passo 1 — Accedi a Google Cloud Console

1. Apri browser → [console.cloud.google.com](https://console.cloud.google.com)
2. Accedi con il tuo account Google (quello di Google Workspace)

### Passo 2 — Crea nuovo progetto

3. In alto nella barra, clicca sul selettore progetti (vicino al logo Google Cloud)
4. Clicca **"NUOVO PROGETTO"**
5. Nome progetto: `aria-traveller`
6. Posizione: lascia "No organization" (o scegli la tua Organization)
7. Clicca **"CREA"**

### Passo 3 — Attiva fatturazione

8. Dal menu hamburger ☰ → **"Fatturazione"**
9. Collega un account di fatturazione (carta di credito)
   - **NOTA**: non verrai addebitato finché stai dentro le quote gratuite
   - Quote gratuite per MVP: Geocoding 10K/mese, Places 5K/mese, Routes 10K/mese
   - Per uso personale ~50 chiamate/mese = $0

### Passo 4 — Abilita le API necessarie

10. Dal menu ☰ → **"API e Servizi" → "Libreria"**
11. Cerca e ABILITA una alla volta:

    | API | Nome esatto nella libreria | Per cosa serve |
    |-----|---------------------------|----------------|
    | **Places API (New)** | `Places API (New)` | Ricerca ristoranti/POI, dettagli luoghi |
    | **Routes API** | `Routes API` | Pianificazione itinerari, distanze |
    | **Geocoding API** | `Geocoding API` | Coordinate → indirizzo e viceversa |

    Per ognuna: clicca su **"ABILITA"**

### Passo 5 — Genera API key

12. Dal menu ☰ → **"API e Servizi" → "Credenziali"**
13. Clicca **"CREA CREDENZIALI"** → **"Chiave API"**
14. Si apre un popup con la chiave — **NON chiuderlo ancora**
15. Clicca **"RESTRINGI CHIAVE"** (molto importante per sicurezza)

### Passo 6 — Restringi la chiave API

Nella schermata di restrizione:

16. **Restrizione applicazioni**: scegli `Indirizzi IP` (se ARIA è su un server con IP fisso) oppure `Nessuna restrizione` per uso locale (meno sicuro ma ok per MVP)

17. **Restrizione API**: seleziona
    - ☑ Places API (New)
    - ☑ Routes API  
    - ☑ Geocoding API
    - (NON selezionare altre API non necessarie)

18. Clicca **"SALVA"**

### Passo 7 — Copia la chiave

19. Copia la chiave API (stringa tipo `AIzaSyBp...`)
20. **Non condividerla** e **non committerla in chiaro**

### Passo 8 — Fornisci la chiave a me (l'agente)

21. Mandami la chiave in chat (es. `GOOGLE_MAPS_API_KEY=AIzaSy...`)
22. La critto con SOPS in `.aria/credentials/secrets/api-keys.enc.yaml`
23. La chiave non sarà mai in chiaro nel repository

## Verifica

Dopo il setup completo, test:

```bash
curl -X POST "https://maps.googleapis.com/maps/api/geocode/json?address=Catania&key=AIzaSy..."
```

Risposta attesa: JSON con `"status": "OK"`.

## Rollback

- **Disabilita API**: da console.cloud.google.com → API e Servizi → Dashboard → Disabilita
- **Revoca chiave**: da Credenziali → elimina/rigenera chiave
- **Elimina progetto**: Impostazioni progetto → ARRIVA → ELIMINA

## Riferimenti

- `@cablate/mcp-google-map`: MCP server che consumerà questa API key
- `.aria/config/mcp_catalog.yaml`: entry `google-maps` nel catalogo
- `.aria/credentials/secrets/api-keys.enc.yaml`: storage cifrato
