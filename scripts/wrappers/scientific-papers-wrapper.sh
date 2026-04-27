#!/usr/bin/env bash
# Scientific Papers MCP Wrapper — keyless (Europe PMC, arXiv, OpenAlex, etc.)
#
# Per Context7 /benedict2310/scientific-papers-mcp:
# - npm package: @futurelab-studio/latest-science-mcp
# - 6 sources: arXiv, OpenAlex, PMC, Europe PMC, bioRxiv/medRxiv, CORE
# - Key tools: search_papers(source, query, field, count, sortBy)
#   fetch_content(source, id), fetch_latest(source, category, count),
#   list_categories(source), fetch_top_cited(concept, since, count)
# - Europe PMC endpoint: https://www.ebi.ac.uk/europepmc/webservices/rest (10 req/min, no key)
# - No API keys required (all sources public)
# - CORE: optional CORE_API_KEY for higher rate limits

set -euo pipefail

# Optional: set CORE_API_KEY for enhanced CORE access
# export CORE_API_KEY="${CORE_API_KEY:-}"

exec npx -y @futurelab-studio/latest-science-mcp@latest
