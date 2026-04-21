#!/usr/bin/env bash
# Google Workspace MCP Wrapper
# Injects refresh_token from keyring before spawning google_workspace_mcp
# Per blueprint §12.1 and sprint plan W1.4.B
#
# This wrapper is required because google_workspace_mcp doesn't read keyring natively.
# It reads GOOGLE_OAUTH_REFRESH_TOKEN from the environment.

set -euo pipefail

ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"
PYTHON_BIN="${ARIA_HOME}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="python3"
fi

# Get refresh token from KeyringStore to avoid key naming drift
get_refresh_token() {
    "$PYTHON_BIN" -c "
import sys
from pathlib import Path

sys.path.insert(0, str(Path('$ARIA_HOME') / 'src'))

try:
    from aria.credentials.keyring_store import KeyringStore
    token = KeyringStore().get_oauth('google_workspace', 'primary')
    if token:
        print(token)
    else:
        print('', file=sys.stderr)
        sys.exit(1)
except Exception as e:
    print(f'Error reading keyring: {e}', file=sys.stderr)
    sys.exit(1)
"
}

# Main
main() {
    # Get refresh token from keyring
    local refresh_token
    refresh_token="$(get_refresh_token)"

    if [[ -z "${refresh_token:-}" ]]; then
        echo "ERROR: No refresh token found in keyring." >&2
        echo "Run 'python scripts/oauth_first_setup.py' first." >&2
        exit 1
    fi

    # Export refresh token for google_workspace_mcp
    export GOOGLE_OAUTH_REFRESH_TOKEN="${refresh_token}"

    # Execute upstream Google Workspace MCP via uvx
    # Context7 docs: command is `workspace-mcp`
    exec uvx workspace-mcp "$@"
}

main "$@"
