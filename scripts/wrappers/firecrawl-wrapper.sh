#!/usr/bin/env bash
# Firecrawl MCP wrapper per blueprint §10.4
#
set -euo pipefail

ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"

exec env -i \
    HOME="$HOME" \
    PATH="$PATH" \
    USER="$USER" \
    ARIA_HOME="$ARIA_HOME" \
    ARIA_RUNTIME="$ARIA_HOME/.aria/runtime" \
    ARIA_CREDENTIALS="$ARIA_HOME/.aria/credentials" \
    SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt" \
    "$ARIA_HOME/.venv/bin/python" -m aria.tools.firecrawl.mcp_server
