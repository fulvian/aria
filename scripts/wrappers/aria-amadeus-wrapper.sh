#!/usr/bin/env bash
# wrapper: aria-amadeus-mcp — FastMCP locale per Amadeus Self-Service API
# Injected via ARIA MCP proxy -> CredentialInjector middleware
#
# Env vars (risolti dal proxy):
#   AMADEUS_CLIENT_ID
#   AMADEUS_CLIENT_SECRET
#
set -euo pipefail

ARIA_HOME="/home/fulvio/coding/aria"
VENV="$ARIA_HOME/.venv"

exec "$VENV/bin/python" -m aria.tools.amadeus.mcp_server
