---
document: ARIA Search Provider Exhaustion Runbook
version: 1.1.0
status: active
date_created: 2026-04-20
date_updated: 2026-04-23
owner: fulvio
sprint: 1.3
---

# Provider Exhaustion Runbook

Runbook per la gestione della degradazione dei provider di ricerca per blueprint §11.6.

## 1. Health Check Matrix

| Provider | Endpoint | Cadence | Statuses |
|---------|---------|---------|----------|
| Tavily | `api.tavily.com/search` | 5 min | available, degraded, down, credits_exhausted |
| Firecrawl | `api.firecrawl.dev/v1/search` | 5 min | available, degraded, down, credits_exhausted |
| Brave | `api.search.brave.com/res/v1/web/search` | 5 min | available, degraded, down, credits_exhausted |
| Exa | `api.exa.ai/search` | 5 min | available, degraded, down, credits_exhausted |
| SearXNG | Self-hosted | 5 min | available, degraded, down |

### Status Meanings

- **available**: Provider operativo, nessuna degradazione
- **degraded**: Provider lento o parzialmente disponibile
- **down**: Provider completamente non raggiungibile
- **credits_exhausted**: Credits API esauriti

## 2. Metriche e Alert

### Prometheus Metrics

```
aria_provider_status{provider="tavily",status="available"} 0
aria_provider_status{provider="tavily",status="degraded"}   1
aria_provider_status{provider="tavily",status="down"}       2
aria_provider_status{provider="tavily",status="credits_exhausted"} 3
```

### Alert Thresholds

- Provider `down` per > 5 min → NOTIFY via Telegram system_event
- Provider `credits_exhausted` → NOTIFY immediato
- > 2 provider contemporaneamente down → NOTIFY CRITICAL

## 3. Fallback Tree per Intent

### News / General
```
Exa → Tavily → Brave → SearXNG (localhost:8888) → cache stale (banner "modalità degradata")
```

### Academic
```
Exa → Tavily → Brave web → SearXNG → cache stale
```

### Deep Scrape
```
Firecrawl → fetch_fetch (via fetch-mcp) + readability → solo metadata+fonti (no full content)
```

### Privacy
```
SearXNG (self-hosted, localhost:8888) → Brave → Tavily → Exa
```

### Tutti i provider down
```
Modalità local-only:
  1. Rispondi con "Sto incontrando problemi con i provider di ricerca. Riprova più tardi o specifica un sottoinsieme."
  2. Mostra risultati cache scaduta (TTL > 6h) se disponibili con banner
  3. Logga system_event con provider_status snapshot
```

## 4. Procedura Manuale: Rotazione Chiave API

### Via CLI

```bash
# Lista provider e stato chiavi
aria creds status

# Rotazione chiave specifica
aria creds rotate tavily --key-id tvly-2

# Ricarica stato runtime
aria creds reload
```

### Via SOPS (editing diretto)

```bash
# Apri editor con file decifrato
sops .aria/credentials/secrets/api-keys.enc.yaml

# Aggiungi nuova chiave nella lista provider
# Save → SOPS ricifra automaticamente

# Ricarica
aria creds reload
```

### Dopo rotazione

1. Verifica: `aria creds status | grep tavily`
2. Il circuit breaker resetta automaticamente dopo probe OK
3. Se credits ancora esauriti sul dashboard provider, acquista piano superiore

## 5. Configurazione SearXNG (Local-Only Mode)

### Setup SearXNG self-hosted (già deployato)

```bash
# Container attivo
docker ps --filter name=searxng

# Se non attivo, avvia:
docker run -d -p 127.0.0.1:8888:8080 \
  -v /home/fulvio/coding/aria/.aria/runtime/searxng:/etc/searxng \
  --name searxng \
  --restart unless-stopped \
  searxng/searxng:latest
```

Stato attuale: container `searxng` attivo su `localhost:8888`, restart policy `unless-stopped`.

### Configurazione ARIA

Già configurato in `.aria/kilocode/kilo.json`:
```json
"searxng-script": {
  "environment": {
    "ARIA_SEARCH_SEARXNG_URL": "http://localhost:8888"
  }
}
```

### Comportamento Docker

| Scenario | Risultato |
|----------|-----------|
| Container crash | Docker riavvia automaticamente (`unless-stopped`) |
| Spegnimento PC | Docker daemon si avvia al boot → container riavviato |
| `docker stop searxng` | Resta fermo fino a `docker start searxng` |
| `bin/aria repl` | Non interagisce con Docker — indipendenti |

## 6. Recovery Procedure

### Dopo provider outage

1. Monitora `aria_provider_status` metrics per 10 min
2. Quando provider torna `available`:
   - Il circuit breaker automaticamente reduce a half-open
   - Al primo probe OK → circuit closed
3. Verifica cache freshness:
   ```bash
   aria search --no-cache "test"  # forcing fresh results
   ```

### Dopo esaurimento credits

1. Acquista credits sul dashboard del provider
2. Attendi propagazione (~2 min)
3. Esegui probe manuale:
   ```bash
   curl -X POST "https://api.tavily.com/search" \
     -H "Authorization: Bearer $TAVILY_API_KEY" \
     -d '{"query":"test","max_results":1}'
   ```
4. Verifica circuit breaker reset via `aria creds status`

## 7. Command Cheat Sheet

```bash
# Status provider
aria creds status

# Forza probe
aria search --debug "test query"

# Pulisci cache search
aria search --no-cache

# Logs provider
tail -f .aria/runtime/logs/credentials_$(date +%Y-%m-%d).log | grep tavily

# Verifica health endpoint metrics
curl -s http://localhost:9090/metrics | grep aria_provider_status
```

## 8. Contatti Provider

| Provider | Dashboard | Support |
|----------|-----------|---------|
| Tavily | app.tavily.com | support@tavily.com |
| Firecrawl | firecrawl.dev/app | support@firecrawl.dev |
| Brave | brave.com/search/api | api@brave.com |
| Exa | dashboard.exa.ai | support@exa.ai |

---

**记住**: in caso di dubbio, meglio rispondere con qualità ridotta che non rispondere per niente.
