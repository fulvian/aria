#!/usr/bin/env bash

set -euo pipefail

api_url="${FIRECRAWL_API_URL:-}"
if [[ -z "$api_url" || "$api_url" == \$\{*\} ]]; then
    export FIRECRAWL_API_URL="https://api.firecrawl.dev"
fi

exec npx -y firecrawl-mcp@3.10.3
