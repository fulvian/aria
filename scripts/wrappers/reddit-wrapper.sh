#!/usr/bin/env bash
# Reddit MCP Wrapper — OAuth credentials via CredentialManager (SOPS-encrypted)
#
# Per Context7 /jordanburke/reddit-mcp-server:
# - npx reddit-mcp-server
# - 11 tools (read+write), v2 uses ONLY read tools
# - OAuth REQUIRED: REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET (verified: no anonymous mode)
# - HITL gate: user must register app at https://www.reddit.com/prefs/apps
#
# Fallback: if OAuth creds missing, exit with error (MCP must not start without auth).

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
if [[ "${REDDIT_CLIENT_ID:-}" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
  unset REDDIT_CLIENT_ID
fi
if [[ "${REDDIT_CLIENT_SECRET:-}" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
  unset REDDIT_CLIENT_SECRET
fi

# Auto-acquire via CredentialManager (2 values: reddit_client_id + reddit_client_secret)
if { [[ -z "${REDDIT_CLIENT_ID:-}" ]] || [[ -z "${REDDIT_CLIENT_SECRET:-}" ]]; } && [[ -x "$PYTHON_BIN" ]]; then
  CREDS="$($PYTHON_BIN - <<'PY' || true
import asyncio
from aria.config import get_config
from aria.credentials.manager import CredentialManager

async def main() -> str:
    cm = CredentialManager(get_config())
    await asyncio.sleep(0.2)
    cid = await cm.acquire("reddit_client_id")
    sec = await cm.acquire("reddit_client_secret")
    cid_val = cid.key.get_secret_value() if cid else ""
    sec_val = sec.key.get_secret_value() if sec else ""
    return f"{cid_val}|{sec_val}"

print(asyncio.run(main()))
PY
)"

  IFS='|' read -r REDDIT_CLIENT_ID REDDIT_CLIENT_SECRET <<<"$CREDS"
  export REDDIT_CLIENT_ID REDDIT_CLIENT_SECRET
fi

if [[ -z "${REDDIT_CLIENT_ID:-}" || -z "${REDDIT_CLIENT_SECRET:-}" ]]; then
  echo "ERROR: Reddit OAuth creds missing — refusing to start MCP. Register app at https://www.reddit.com/prefs/apps" >&2
  exit 1
fi

exec npx reddit-mcp-server
