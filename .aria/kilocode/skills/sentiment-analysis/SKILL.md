---
name: sentiment-analysis
version: 1.0.0
description: News scoring, bias analysis, social sentiment aggregation, source credibility
trigger-keywords: [sentiment, news, bias, social, Reuters, CNN, Reuters, financial news, media]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - aria-memory__wiki_update_tool
  - aria-memory__wiki_recall_tool
  - sequential-thinking__*
max-tokens: 50000
estimated-cost-eur: 0.08
---

# Sentiment Analysis Skill

## Obiettivo

Analizzare il sentiment di mercato: news scoring, bias dei media,
social sentiment, e aggregazione multi-source.

## Tool disponibili (via helium-mcp)

| Tool | Funzione |
|------|----------|
| `search_news` | Full-text search 3.2M+ articles, 5000+ sources |
| `search_balanced_news` | AI-synthesized balanced coverage |
| `get_source_bias` | Deep bias analysis per source |
| `get_bias_from_url` | Per-article bias scores |
| `get_all_source_biases` | Bias scores for every tracked source |

## Pipeline

### Fase 1 — News Search
1. Cerca news rilevanti per ticker/sector
2. Filtra per data, source, category
3. Ordina per rank/shares/date

### Fase 2 — Bias Analysis
Per le fonti più rilevanti:
- Political lean
- Emotionality score
- Factfulness score
- Signature phrases

### Fase 3 — Source Credibility
1. Valuta credibilità fonti (bias scores)
2. Identifica fonti affidabili vs sensational
3. Confronta copertura left/right/center

### Fase 4 — Aggregated Sentiment
1. Aggrega scores da multiple sources
2. Calcola weighted average (per credibility)
3. Identifica key themes e narratives
4. Confronta con price action

## Regole operative

1. **Usa SEMPRE il proxy** con `_caller_id: "trader-agent"`
2. Usa `helium-mcp` come fonte primaria per news/sentiment
3. **Disclaimer obbligatorio** su ogni output

## Esempio proxy call

Nel runtime Kilo i tool del proxy possono apparire come alias
`aria-mcp-proxy_search_tools` / `aria-mcp-proxy_call_tool`.

```python
# Discovery
aria-mcp-proxy__search_tools({"query": "news sentiment analysis scoring", "_caller_id": "trader-agent"})

# Esecuzione — helium-mcp è HTTP/SSE, attualmente disabilitato (Phase 2)
# Usa search-agent per news come fallback, o financekit-mcp per dati di mercato
aria-mcp-proxy__call_tool({
    "name": "financekit-mcp__search_news",
    "arguments": {"query": "AAPL earnings", "limit": 10},
    "_caller_id": "trader-agent"
})
```

> **Nota backend**: `helium-mcp` (news intelligence + bias scoring) è HTTP/SSE, attualmente disabilitato (Phase 2).
> Per sentiment news, delega tramite `trader-agent → search-agent` o usa `financekit-mcp` per dati di mercato disponibili.

## Output strutturato

```
# Sentiment Report: <TICKER/SECTOR>

## Top Headlines
<lista headlines con data e fonte>

## Source Bias Distribution
<political lean spectrum visualization>

## Key Themes
<1-3 themes identificati>

## Credibility Assessment
<fonte piu/meno credibili>

## Aggregated Sentiment Score
<bullish/bearish/neutral>

## Comparison with Price
<correlazione sentiment vs price action>
```
