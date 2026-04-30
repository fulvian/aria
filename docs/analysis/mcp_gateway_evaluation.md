# MCP Gateway Evaluation — Search Domain

**Date**: 2026-04-29  
**Status**: Complete  
**Source**: `scripts/benchmarks/mcp_startup_latency.py` (run 2026-04-29T21:04)  
**Previous analysis**: `docs/analysis/analisi_sostenibilita_mcp_report.md`

## 1) Executive Summary

La valutazione del gateway selettivo per il dominio search conclude che **NON è
giustificato** al momento attuale. Le metriche di startup/latency raccolte mostrano
che l'overhead di avvio è accettabile (~700ms medio per server) e che un gateway
introdurrebbe complessità senza benefici significativi.

L'ottimizzazione consigliata è invece **lazy loading per intent** (caricare solo
gli MCP server necessari per l'intent corrente), che può essere implementato a
livello di routing/configuration senza un gateway layer.

## 2) Benchmark Results

### Full results (9 MCP servers)

| Server | Domain | Cold (ms) | Warm (ms) | tools/list | Tools |
|--------|--------|-----------|-----------|-----------|-------|
| `filesystem` | core | 633 | 626 | 3.5ms | 14 |
| `sequential-thinking` | core | 608 | 613 | 2.3ms | 1 |
| `aria-memory` | core | 546 | 572 | 2.9ms | 10 |
| `fetch` | search | 342 | 329 | 1.6ms | 1 |
| `searxng-script` | search | 1453 | 1452 | 1.8ms | 1 |
| `reddit-search` | search | 510 | 526 | 2.8ms | 6 |
| `pubmed-mcp` | search | 635 | 652 | 10.8ms | 9 |
| `scientific-papers-mcp` | search | 1137 | 670 | 2.8ms | 6 |
| `markitdown-mcp` | productivity | 632 | 676 | 1.0ms | 1 |

### Aggregate

| Metric | Value |
|--------|-------|
| **Total cold start** (9 servers) | 6.5s |
| **Avg cold start** | 722ms |
| **Total warm start** (9 servers) | 6.1s |
| **Avg warm start** | 680ms |
| **Total tools exposed** | 49 |
| **Total search-specific** | 4 servers, avg cold 835ms, 3.4s total |

### Key observations

1. **searxng-script** e' il piu lento (1.45s) — invariato tra cold e warm perche
   il backend Docker `searxng` non e' soggetto a caching npm.
2. **scientific-papers-mcp** ha un ampio delta cold→warm (1137→670ms, -41%)
   grazie al caching npm del pacchetto `@futurelab-studio/latest-science-mcp`.
3. **fetch**, **reddit-search**, **pubmed-mcp** sono veloci (<650ms).
4. Le chiamate `tools/list` sono costantemente <11ms — il bottleneck e' lo
   startup, non la negoziazione capability.
5. **49 tools totali** esposti (42 senza markitdown-mcp).

## 3) Gateway Analysis

### Cosa farebbe un gateway

Un MCP gateway (es. MetaMCP o custom) aggregherebbe N server MCP in 1 endpoint,
riducendo il numero di processi stdio e potenzialmente velocizzando lo startup.

Scenario gateway:
- 1 processo gateway (invece di 9 processi stdio)
- 1 connessione invece di 9
- tools/list piu' veloce? Non necessariamente (deve ancora interrogare tutti i server)

### Perche NON e' giustificato

| Fattore | Valore attuale | Con gateway | Giudizio |
|---------|---------------|-------------|----------|
| Cold start 9 servers | 6.5s | ~5s (riduzione marginale) | ❌ Miglioramento modesto |
| Warm start 9 servers | 6.1s | ~5.5s | ❌ Miglioramento modesto |
| tools/list | 1-11ms per server | 2-15ms (overhead gateway) | ❌ Peggioramento possibile |
| Complessita' operativa | Bassa (npx/uvx) | Alta (gateway da mantenere) | ❌ Peggioramento |
| Affidabilita' | Alta (ogni server indipendente) | Media (single point of failure) | ❌ Peggioramento |
| Debug | Facile (log per processo) | Difficile (traffico aggregato) | ❌ Peggioramento |
| Costo sviluppo | Zero | Significativo (mesi) | ❌ Ingiustificato |
| Pattern tempestivi | Lazy loading per intent | Gateway layer | ✅ **Meglio lazy loading** |

### L'alternativa migliore: Lazy Loading per Intent

Invece di un gateway, l'ottimizzazione consigliata e' **caricare solo gli MCP
server necessari per l'intent corrente**:

| Intent | Server da caricare | Risparmio |
|--------|-------------------|-----------|
| `general/news` | filesystem, sequential-thinking, aria-memory, fetch, searxng, reddit-search, tavily, brave | No scientific-papers/pubmed (~1.8s risparmiati) |
| `academic` | filesystem, sequential-thinking, aria-memory, fetch, searxng, reddit-search, pubmed, scientific-papers, tavily | ~carico completo |
| `social` | filesystem, sequential-thinking, aria-memory, fetch, reddit-search, searxng | No pubmed/scientific-papers/tavily/brave (~2.5s risparmiati) |
| `productivity` | filesystem, sequential-thinking, aria-memory, markitdown-mcp | Solo 4 server (~0.6s totale) |

### Implementazione lazy loading

Il lazy loading puo' essere implementato a livello di `mcp.json`:

```json
{
  "mcpServers": {
    "scientific-papers-mcp": {
      "command": "...",
      "disabled": true,
      "_lazy": true,
      "_lazy_intents": ["academic"]
    },
    "pubmed-mcp": {
      "command": "...",
      "disabled": true,
      "_lazy": true,
      "_lazy_intents": ["academic"]
    }
  }
}
```

Il launcher `bin/aria` abiliterebbe dinamicamente i server in base all'intent
classificato, usando un profilo di startup "minimo + X" invece del "tutto abilitato".

### Quando riconsiderare il gateway

Un gateway MCP potrebbe diventare giustificato se:

1. **Numero server > 25** (oltre la soglia di gestibilita')
2. **Startup totale > 20s** (deterioramento percepibile dell'esperienza utente)
3. **Tool count > 200** (saturazione contestuale del LLM)
4. **Richieste cross-server frequenti** (es. search che chiama pubmed + scientific-papers
   + reddit simultaneamente)

Nessuna di queste condizioni e' vera oggi.

## 4) Raccomandazioni

1. **NON implementare un gateway MCP** al momento (costi > benefici).
2. **Implementare lazy loading per intent** nel launcher/bin/aria come profilazione
   dinamica: profilo `minimal` (core) + `search-{intent}` (server specifici per intent).
3. **Ripetere il benchmark trimestralmente** per monitorare la crescita del tool count
   e rivalutare la soglia gateway.
4. **Aggiungere metriche di startup** in `aria-memory/health` per tracking continuo.

## 5) Provenance

- Script: `scripts/benchmarks/mcp_startup_latency.py`
- Run: 2026-04-29T21:04 (9/9 servers success)
- Platform: Linux, Python 3.12.3, npx/uvx/bunx
- Server config: `.aria/kilocode/mcp.json` (16 server, 9 testati)
- Previous report: `docs/analysis/analisi_sostenibilita_mcp_report.md`
- Gateway frameworks analizzati: `/metatool-ai/metamcp`, `/lastmile-ai/mcp-agent` (Context7 2026-04-29)
