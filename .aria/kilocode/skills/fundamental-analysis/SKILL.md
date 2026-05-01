---
name: fundamental-analysis
version: 1.0.0
description: Analisi fondamentali — earnings, statements, DCF, analyst estimates, valuation ratios
trigger-keywords: [fondamentale, earnings, bilancio, income statement, balance sheet, cash flow, DCF, valuation, fatturato, utile, EPS]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - aria-memory__wiki_update_tool
  - aria-memory__wiki_recall_tool
  - sequential-thinking__*
max-tokens: 60000
estimated-cost-eur: 0.10
---

# Fundamental Analysis Skill

## Obiettivo

Condurre un'analisi fondamentale completa su un titolo azionario o asset:
 Earnings, financial statements, DCF valuation, analyst estimates.

## Pipeline

### Fase 1 — Quote e overview
Recupera quotazione attuale e metriche chiave:
- Prezzo, variazione % (1D, 5D, 1M, YTD)
- Volume, market cap, P/E ratio
- 52-week high/low

### Fase 2 — Financial Statements
Estrai e analizza:
- **Income Statement**: revenue, gross margin, operating margin, net income, EPS
- **Balance Sheet**: total assets, debt, equity, current ratio
- **Cash Flow Statement**: operating cash flow, free cash flow, capex

### Fase 3 — Valuation
Calcola e interpreta:
- P/E, P/S, P/B ratios vs sector average
- EV/EBITDA, EV/Sales
- PEG ratio
- Price targets vs current price

### Fase 4 — Analyst Estimates
- Consensus target price
- Rating distribution (buy/hold/sell)
- Revision trends (upgrades/downgrades)
- Long-term growth projections

### Fase 5 — DCF (se dati disponibili)
- Revenue growth assumptions
- EBITDA margin assumptions
- Discount rate (WACC)
- Terminal value calculation

## Regole operative

1. **Usa SEMPRE il proxy** con `_caller_id: "trader-agent"`
2. Usa `financial-modeling-prep-mcp` come fonte primaria
3. Per crypto, usa `financekit-mcp` per metrics base
4. **Disclaimer obbligatorio** su ogni output

## Esempio proxy call

```python
aria-mcp-proxy__call_tool("call_tool", {
    "name": "financial-modeling-prep-mcp/get_financial_statement",
    "arguments": {"symbol": "AAPL", "statement_type": "income", "period": "annual"},
    "_caller_id": "trader-agent"
})
```

## Output strutturato

```
# Fundamental Analysis: <TICKER>

## Quote Overview
<metriche basic>

## Financial Health
<income, margins, cash flow>

## Valuation
<ratios, targets>

## Analyst Consensus
<ratings, revisions>

## DCF Scenario
<assunzioni, fair value range>
```