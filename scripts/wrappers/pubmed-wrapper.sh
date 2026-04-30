#!/usr/bin/env bash
# PubMed MCP Wrapper — acquires NCBI_API_KEY via CredentialManager (SOPS-encrypted)
#
# Environment Variables:
#   NCBI_API_KEY          (optional) — set by env, mcp.json, or auto-acquire via CredentialManager
#   NCBI_ADMIN_EMAIL      (required for NCBI E-utilities compliance)
#   UNPAYWALL_EMAIL       (optional) — full-text fallback via Unpaywall
#   MCP_TRANSPORT_TYPE    (default: stdio)
#   MCP_LOG_LEVEL         (default: info)
#
# Per Context7 /cyanheads/pubmed-mcp-server (v2.6.4):
# - npx -y @cyanheads/pubmed-mcp-server@latest (no Bun required)
# - 9 MCP tools: search_articles, fetch_articles, fetch_fulltext, format_citations,
#   find_related, spell_check, lookup_mesh, lookup_citation, convert_ids
# - Env required: NCBI_ADMIN_EMAIL, MCP_TRANSPORT_TYPE=stdio
# - Env optional: NCBI_API_KEY (10 req/s vs 3 without), UNPAYWALL_EMAIL

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
if [[ "${NCBI_API_KEY:-}" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
  unset NCBI_API_KEY
fi

# Acquire via CredentialManager (single key, no rotation needed for PubMed)
if [[ -z "${NCBI_API_KEY:-}" ]] && [[ -x "$PYTHON_BIN" ]]; then
  ACQUIRED_KEY="$($PYTHON_BIN - <<'PY' || true
import asyncio
from aria.config import get_config
from aria.credentials.manager import CredentialManager

async def main() -> str:
    cm = CredentialManager(get_config())
    await asyncio.sleep(0.2)
    key = await cm.acquire("pubmed")
    return key.key.get_secret_value() if key else ""

print(asyncio.run(main()))
PY
)"

  if [[ -n "$ACQUIRED_KEY" ]]; then
    export NCBI_API_KEY="$ACQUIRED_KEY"
  else
    echo "WARN: NCBI_API_KEY missing; rate limit will be 3 req/s instead of 10" >&2
  fi
fi

# Set required env vars for PubMed MCP
export NCBI_ADMIN_EMAIL="${NCBI_ADMIN_EMAIL:-fulviold@gmail.com}"
export UNPAYWALL_EMAIL="${UNPAYWALL_EMAIL:-$NCBI_ADMIN_EMAIL}"
export MCP_TRANSPORT_TYPE="${MCP_TRANSPORT_TYPE:-stdio}"
export MCP_LOG_LEVEL="${MCP_LOG_LEVEL:-info}"

# Use npx (default) for reliable stdio MCP transport.
# bunx was tried (BL-20260429-02) but it closes the subprocess immediately when
# stdin isn't actively piped, causing "MCP error -32000: Connection closed local
# mcp startup failed" in KiloCode's MCP client. npx properly waits for stdin
# indefinitely as required by the JSON-RPC stdio protocol.
# To use bunx (faster startup), set PUBMED_USE_BUNX=1.
if [[ "${PUBMED_USE_BUNX:-0}" == "1" ]] && command -v bun &>/dev/null; then
  exec bunx @cyanheads/pubmed-mcp-server
else
  exec npx -y @cyanheads/pubmed-mcp-server
fi
