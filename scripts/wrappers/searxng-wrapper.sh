#!/usr/bin/env bash

set -euo pipefail

# Backward-compatible env fallback.
if [[ "${SEARXNG_SERVER_URL:-}" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
  unset SEARXNG_SERVER_URL
fi

if [[ "${SEARXNG_URL:-}" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
  unset SEARXNG_URL
fi

if [[ -z "${SEARXNG_SERVER_URL:-}" ]] && [[ -n "${SEARXNG_URL:-}" ]]; then
  export SEARXNG_SERVER_URL="$SEARXNG_URL"
fi

# Keep MCP server bootable in local-first mode even without explicit env.
if [[ -z "${SEARXNG_SERVER_URL:-}" ]]; then
  # Check if local Docker on port 8888 is running
  if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://127.0.0.1:8888/search?q=ping 2>/dev/null | grep -q 200; then
    export SEARXNG_SERVER_URL="http://127.0.0.1:8888"
    echo "INFO: Found local SearXNG on port 8888; using ${SEARXNG_SERVER_URL}." >&2
  else
    export SEARXNG_SERVER_URL="http://127.0.0.1:8080"
    echo "WARN: SEARXNG_SERVER_URL missing; defaulting to ${SEARXNG_SERVER_URL}." >&2
  fi
fi

exec uv run "$(dirname "$0")/../mcp-stdio-filter.py" -- npx -y searxng-mcp@1.0.1
