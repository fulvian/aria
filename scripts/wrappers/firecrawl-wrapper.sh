#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

if [[ "${FIRECRAWL_API_KEY:-}" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
  unset FIRECRAWL_API_KEY
fi

if [[ "${FIRECRAWL_API_URL:-}" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
  unset FIRECRAWL_API_URL
fi

# Optional key auto-acquire via ARIA credential rotation.
if [[ -z "${FIRECRAWL_API_KEY:-}" ]] && [[ -x "$PYTHON_BIN" ]]; then
  ACQUIRED_KEY="$($PYTHON_BIN - <<'PY' || true
import asyncio

from aria.config import get_config
from aria.credentials.manager import CredentialManager


async def main() -> str:
    cm = CredentialManager(get_config())
    key = await cm.acquire("firecrawl")
    if key is None:
        return ""
    return key.key.get_secret_value()


print(asyncio.run(main()), end="")
PY
)"

  if [[ -n "$ACQUIRED_KEY" ]]; then
    export FIRECRAWL_API_KEY="$ACQUIRED_KEY"
  fi
fi

if [[ -z "${FIRECRAWL_API_KEY:-}" ]] && [[ -z "${FIRECRAWL_API_URL:-}" ]]; then
  export FIRECRAWL_API_URL="https://api.firecrawl.dev"
  echo "WARN: FIRECRAWL_API_KEY missing; defaulting FIRECRAWL_API_URL=${FIRECRAWL_API_URL}." >&2
fi

exec npx -y firecrawl-mcp@3.10.3
