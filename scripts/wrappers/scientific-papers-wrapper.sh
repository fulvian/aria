#!/usr/bin/env bash
# Scientific Papers MCP Wrapper — keyless (Europe PMC, arXiv, OpenAlex, etc.)
#
# ⚠️  VERSIONE CON PATCH AUTOMATICA ⚠️
# Il pacchetto npm @futurelab-studio/latest-science-mcp v0.1.40 ha 3 bug critici
# nella costruzione query per arXiv ed EuropePMC. Questo wrapper applica le
# patch automaticamente a qualsiasi cache entry npx prima di avviare il server.
#
# Bug risolti:
#   BUG 1: arXiv driver — query wrappata in doppi apici (frase esatta)
#   BUG 2: EuropePMC driver — stessa cosa + sort=relevance rompe API
#   BUG 3: search-papers — nessuna pre-elaborazione query centralizzata
#
# Per Context7 /benedict2310/scientific-papers-mcp:
# v0.1.40 — 6 sources: arXiv, OpenAlex, PMC, Europe PMC, bioRxiv/medRxiv, CORE
# Tools: search_papers, fetch_content, fetch_latest, list_categories, fetch_top_cited
# Europe PMC: https://www.ebi.ac.uk/europepmc/webservices/rest (10 req/min, no key)
# No API keys required (all sources public)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARIA_HOME="${ARIA_HOME:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

# ─── Self-patching: applica le correzioni a qualsiasi cache npx ───
# Le patch vengono copiate da un seed patched noto sotto docs/patches/
PATCH_SEED="$ARIA_HOME/docs/patches/scientific-papers-mcp"
NPX_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/npm/_npx"
if [ ! -d "$NPX_CACHE" ]; then
    NPX_CACHE="$HOME/.npm/_npx"
fi

if [ -d "$PATCH_SEED" ] && [ -d "$NPX_CACHE" ]; then
    for entry in "$NPX_CACHE"/*/; do
        pkg="$entry/node_modules/@futurelab-studio/latest-science-mcp"
        if [ -f "$pkg/dist/drivers/europepmc-driver.js" ]; then
            # Check if already patched (look for our fix markers)
            if ! grep -q 'FIXED v2' "$pkg/dist/drivers/europepmc-driver.js" 2>/dev/null; then
                cp "$PATCH_SEED/arxiv-driver.js" "$pkg/dist/drivers/arxiv-driver.js"
                cp "$PATCH_SEED/europepmc-driver.js" "$pkg/dist/drivers/europepmc-driver.js"
                cp "$PATCH_SEED/search-papers.js" "$pkg/dist/tools/search-papers.js"
            fi
        fi
    done
fi

# ─── Avvia MCP server via npx ───
exec npx -y @futurelab-studio/latest-science-mcp@latest
