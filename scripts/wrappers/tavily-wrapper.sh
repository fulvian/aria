#!/usr/bin/env bash
# Tavily MCP Wrapper — with key pre-verification and automatic rotation
#
# Acquires a Tavily API key via ARIA CredentialManager, verifies it via the
# Tavily search API, and falls back to the next key if the current one is
# exhausted/deactivated. This provides automatic rotation across multiple
# accounts without requiring manual state file edits.

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
if [[ "${TAVILY_API_KEY:-}" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
  unset TAVILY_API_KEY
fi

# Key pre-verification loop via Python (handles key_id↔key mapping internally)
# Each iteration acquires a key from the Rotator (round_robin), tests it via
# the Tavily search API, and reports failures back to the Rotator.
if [[ -z "${TAVILY_API_KEY:-}" ]] && [[ -x "$PYTHON_BIN" ]]; then
  ACQUIRED_KEY="$($PYTHON_BIN - <<'PY' || true
import asyncio, httpx

from aria.config import get_config
from aria.credentials.manager import CredentialManager


async def find_working_key() -> str:
    cm = CredentialManager(get_config())
    await asyncio.sleep(0.2)  # let background key loading complete

    for attempt in range(1, 9):  # max 8 attempts
        key = await cm.acquire("tavily")
        if key is None:
            return ""

        key_value = key.key.get_secret_value()
        key_id = key.key_id

        # Test the key via Tavily API
        try:
            resp = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": key_value,
                    "query": "ping",
                    "search_depth": "basic",
                    "max_results": 1,
                },
                timeout=10,
            )

            if resp.status_code == 200:
                return key_value  # success!

            # Report failure to Rotator
            if resp.status_code in (432, 429):
                reason = "credits_exhausted"
            elif resp.status_code == 401:
                reason = "account_deactivated"
            else:
                reason = f"http_{resp.status_code}"

            await cm.report_failure("tavily", key_id, reason)
            print(f"WARN: key {key_id} is {reason}; trying next...", file=__import__("sys").stderr)

        except httpx.RequestError as e:
            # Network error - try next key
            print(f"WARN: key {key_id} network error: {e}; trying next...", file=__import__("sys").stderr)
            await cm.report_failure("tavily", key_id, "network_error")
            continue

    return ""  # all keys exhausted


print(asyncio.run(find_working_key()), end="")
PY
)"

  if [[ -n "$ACQUIRED_KEY" ]]; then
    export TAVILY_API_KEY="$ACQUIRED_KEY"
  fi
fi

if [[ -z "${TAVILY_API_KEY:-}" ]]; then
  echo "WARN: TAVILY_API_KEY missing; tavily-mcp will start but tool calls may fail." >&2
fi

exec uv run "$(dirname "$0")/../mcp-stdio-filter.py" -- npx -y tavily-mcp@0.2.19
