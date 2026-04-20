#!/usr/bin/env bash
# Tavily MCP wrapper per blueprint §10.4
#
# Resets environment and loads only necessary variables before invoking
# the FastMCP Python server. This prevents environment pollution.
#
set -euo pipefail

ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"

# Use env -i to start with clean environment, then add only required vars
exec env -i \
    HOME="$HOME" \
    PATH="$PATH" \
    USER="$USER" \
    ARIA_HOME="$ARIA_HOME" \
    ARIA_RUNTIME="$ARIA_HOME/.aria/runtime" \
    ARIA_CREDENTIALS="$ARIA_HOME/.aria/credentials" \
    SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt" \
    "$ARIA_HOME/.venv/bin/python" -m aria.tools.tavily.mcp_server
