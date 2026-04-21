#!/usr/bin/env bash
# SearXNG MCP wrapper
set -euo pipefail

ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"

exec env -i \
    HOME="$HOME" \
    PATH="$PATH" \
    USER="$USER" \
    ARIA_HOME="$ARIA_HOME" \
    ARIA_RUNTIME="$ARIA_HOME/.aria/runtime" \
    ARIA_CREDENTIALS="$ARIA_HOME/.aria/credentials" \
    ARIA_SEARCH_SEARXNG_URL="${ARIA_SEARCH_SEARXNG_URL:-}" \
    "$ARIA_HOME/.venv/bin/python" -m aria.tools.searxng.mcp_server
