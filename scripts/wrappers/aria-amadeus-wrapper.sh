#!/usr/bin/env bash
# wrapper: aria-amadeus-mcp — FastMCP locale per Amadeus Self-Service API
#
# Auto-acquisisce le credenziali Amadeus da SOPS (api-keys.enc.yaml)
# e le inietta come variabili d'ambiente per il server FastMCP.
#
# Env var risolte:
#   AMADEUS_CLIENT_ID      — da SOPS providers.amadeus.client_id
#   AMADEUS_CLIENT_SECRET  — da SOPS providers.amadeus.client_secret (decifrata)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"

# Ensure SOPS_AGE_KEY_FILE for credential decrypt
if [[ -z "${SOPS_AGE_KEY_FILE:-}" ]]; then
  if [[ -f "$HOME/.config/sops/age/keys.txt" ]]; then
    export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
  elif [[ -f "/home/fulvio/.config/sops/age/keys.txt" ]]; then
    export SOPS_AGE_KEY_FILE="/home/fulvio/.config/sops/age/keys.txt"
  fi
fi

# Strip placeholder ${VAR} literals
if [[ "${AMADEUS_CLIENT_ID:-}" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
  unset AMADEUS_CLIENT_ID
fi
if [[ "${AMADEUS_CLIENT_SECRET:-}" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
  unset AMADEUS_CLIENT_SECRET
fi

# Auto-acquire credentials via SOPS decrypt (if not already set)
if [[ -z "${AMADEUS_CLIENT_ID:-}" || -z "${AMADEUS_CLIENT_SECRET:-}" ]] && [[ -x "$VENV_PYTHON" ]]; then
  ACQUIRED="$("$VENV_PYTHON" -c '
import subprocess, sys, yaml
from pathlib import Path

candidates = [
    Path(".aria/credentials/secrets/api-keys.enc.yaml"),
    Path("/home/fulvio/coding/aria/.aria/credentials/secrets/api-keys.enc.yaml"),
]
sops_path = next((p for p in candidates if p.exists()), None)
if sops_path is None:
    sys.exit(0)

result = subprocess.run(
    ["sops", "--decrypt", str(sops_path)],
    capture_output=True, text=True, timeout=15,
)
if result.returncode != 0:
    sys.exit(0)

data = yaml.safe_load(result.stdout)
amadeus = (data or {}).get("providers", {}).get("amadeus", {})
cid = (amadeus.get("client_id") or "").strip()
csec = (amadeus.get("client_secret") or "").strip()
if cid:
    print(f"AMADEUS_CLIENT_ID={cid}")
if csec:
    print(f"AMADEUS_CLIENT_SECRET={csec}")
' 2>/dev/null || true)"

  if [[ -n "$ACQUIRED" ]]; then
    while IFS= read -r line; do
      if [[ -n "$line" ]]; then
        export "$line"
      fi
    done <<< "$ACQUIRED"
  fi
fi

if [[ -z "${AMADEUS_CLIENT_ID:-}" ]]; then
  echo "WARN: AMADEUS_CLIENT_ID missing; amadeus-mcp will return 401 for all tools." >&2
fi
if [[ -z "${AMADEUS_CLIENT_SECRET:-}" ]]; then
  echo "WARN: AMADEUS_CLIENT_SECRET missing; amadeus-mcp will return 401 for all tools." >&2
fi

exec "$VENV_PYTHON" -m aria.tools.amadeus.mcp_server
