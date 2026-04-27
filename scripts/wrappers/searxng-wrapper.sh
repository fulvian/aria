#!/usr/bin/env bash

set -euo pipefail

server_url="${SEARXNG_SERVER_URL:-}"
if [[ -z "$server_url" || "$server_url" == \$\{*\} ]]; then
    server_url="${SEARXNG_URL:-}"
fi
if [[ -z "$server_url" || "$server_url" == \$\{*\} ]]; then
    server_url="http://localhost:8888"
fi

export SEARXNG_SERVER_URL="$server_url"

exec npx -y searxng-mcp
