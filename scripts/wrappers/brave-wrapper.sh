#!/usr/bin/env bash
# Brave Search MCP Wrapper
#
# Provides env var name normalization and credential auto-acquire for Brave Search.
# Per Context7 /brave/brave-search-mcp-server: env var name is BRAVE_API_KEY (no _ACTIVE suffix).
#
# Environment Variables:
#   BRAVE_API_KEY          (canonical) — set by env, mcp.json, or auto-acquire
#   BRAVE_API_KEY_ACTIVE   (deprecated alias, backward-compat)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"

# Ensure SOPS_AGE_KEY_FILE for credential auto-acquire
if [[ -z "${SOPS_AGE_KEY_FILE:-}" ]]; then
  if [[ -f "$HOME/.config/sops/age/keys.txt" ]]; then
    export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
  elif [[ -f "/home/fulvio/.config/sops/age/keys.txt" ]]; then
    export SOPS_AGE_KEY_FILE="/home/fulvio/.config/sops/age/keys.txt"
  fi
fi

# Strip placeholder ${VAR} literals
if [[ "${BRAVE_API_KEY:-}" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
  unset BRAVE_API_KEY
fi

# Backward-compat alias: BRAVE_API_KEY_ACTIVE → BRAVE_API_KEY
if [[ -z "${BRAVE_API_KEY:-}" ]] && [[ -n "${BRAVE_API_KEY_ACTIVE:-}" ]]; then
  if [[ ! "$BRAVE_API_KEY_ACTIVE" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
    export BRAVE_API_KEY="$BRAVE_API_KEY_ACTIVE"
  fi
fi

# Auto-acquire via ARIA credential rotator
if [[ -z "${BRAVE_API_KEY:-}" ]] && [[ -x "$PYTHON_BIN" ]]; then
  ACQUIRED_KEY="$($PYTHON_BIN - <<'PY' || true
import asyncio

from aria.config import get_config
from aria.credentials.manager import CredentialManager


async def main() -> str:
    cm = CredentialManager(get_config())
    k = await cm.acquire("brave")
    if k is None:
        return ""
    return k.key.get_secret_value()


print(asyncio.run(main()), end="")
PY
)"

  if [[ -n "$ACQUIRED_KEY" ]]; then
    export BRAVE_API_KEY="$ACQUIRED_KEY"
  fi
fi

if [[ -z "${BRAVE_API_KEY:-}" ]]; then
  echo "WARN: BRAVE_API_KEY missing; brave-mcp will start but tool calls return 422." >&2
fi

exec npx -y @brave/brave-search-mcp-server --transport stdio
