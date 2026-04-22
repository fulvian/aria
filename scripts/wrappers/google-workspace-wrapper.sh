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

sync_workspace_credentials_file() {
    local user_email="$1"
    local client_id="$2"
    local client_secret="$3"
    local refresh_token="$4"

    "$PYTHON_BIN" -c "
import json
import os
import re
from pathlib import Path

user_email = os.environ['GW_USER_EMAIL'].strip()
client_id = os.environ['GW_CLIENT_ID'].strip()
client_secret = os.environ.get('GW_CLIENT_SECRET', '').strip()
refresh_token = os.environ['GW_REFRESH_TOKEN'].strip()
aria_home = Path('$ARIA_HOME')

# Load scopes from canonical source (per W1.1 - de-hardcode)
# Priority: 1) WORKSPACE_SCOPES_OVERRIDE env var, 2) scopes file, 3) empty
scopes = []
scopes_override = os.environ.get('WORKSPACE_SCOPES_OVERRIDE', '').strip()
if scopes_override:
    scopes = scopes_override.split(',')
else:
    scopes_file = aria_home / '.aria' / 'runtime' / 'credentials' / 'google_workspace_scopes_primary.json'
    if scopes_file.exists():
        try:
            data = json.loads(scopes_file.read_text(encoding='utf-8'))
            scopes = data.get('scopes', [])
        except Exception:
            scopes = []

creds_dir = Path(os.environ['WORKSPACE_MCP_CREDENTIALS_DIR']).expanduser()
creds_dir.mkdir(parents=True, exist_ok=True)
os.chmod(creds_dir, 0o700)

safe_email = re.sub(r'[^a-zA-Z0-9@._-]', '_', user_email)
creds_path = creds_dir / f'{safe_email}.json'

existing_token = ''
if creds_path.exists():
    try:
        existing = json.loads(creds_path.read_text(encoding='utf-8'))
        existing_token = str(existing.get('token') or '')
    except Exception:
        existing_token = ''

payload = {
    'token': existing_token,
    'refresh_token': refresh_token,
    'token_uri': 'https://oauth2.googleapis.com/token',
    'client_id': client_id,
    'client_secret': client_secret,
    'scopes': scopes,
    'expiry': None,
}

fd = os.open(str(creds_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as f:
    json.dump(payload, f, indent=2)
"
}

get_oauth_config() {
    "$PYTHON_BIN" -c "
import json
import os
from pathlib import Path

aria_home = Path('$ARIA_HOME')
session_file = aria_home / '.aria' / 'runtime' / 'credentials' / 'google_oauth_manual_session.json'
email_file = aria_home / '.aria' / 'runtime' / 'credentials' / 'google_workspace_user_email.txt'

client_id = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '').strip()
client_secret = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', '').strip()
user_email = os.environ.get('USER_GOOGLE_EMAIL', '').strip()

if session_file.exists():
    try:
        data = json.loads(session_file.read_text(encoding='utf-8'))
        client_id = client_id or str(data.get('client_id', '')).strip()
        client_secret = client_secret or str(data.get('client_secret', '')).strip()
    except Exception:
        pass

if email_file.exists() and not user_email:
    try:
        user_email = email_file.read_text(encoding='utf-8').strip()
    except Exception:
        pass

print(client_id)
print(client_secret)
print(user_email)
"
}

# Main
main() {
    # Get refresh token from keyring
    local refresh_token
    refresh_token="$(get_refresh_token)"
    refresh_token="$(printf '%s' "$refresh_token" | tr -d '\r\n')"

    if [[ -z "${refresh_token:-}" ]]; then
        echo "ERROR: No refresh token found in keyring." >&2
        echo "Run 'python scripts/oauth_first_setup.py' first." >&2
        exit 1
    fi

    # Export refresh token for google_workspace_mcp
    export GOOGLE_OAUTH_REFRESH_TOKEN="${refresh_token}"

    # Resolve OAuth client config from env, with runtime fallback.
    local oauth_config
    oauth_config="$(get_oauth_config)"
    local client_id client_secret user_google_email
    client_id="$(printf '%s\n' "$oauth_config" | sed -n '1p')"
    client_secret="$(printf '%s\n' "$oauth_config" | sed -n '2p')"
    user_google_email="$(printf '%s\n' "$oauth_config" | sed -n '3p')"

    if [[ -z "${client_id:-}" ]]; then
        echo "ERROR: GOOGLE_OAUTH_CLIENT_ID missing (env or runtime session file)." >&2
        exit 1
    fi

    export GOOGLE_OAUTH_CLIENT_ID="${client_id}"
    if [[ -n "${client_secret:-}" ]]; then
        export GOOGLE_OAUTH_CLIENT_SECRET="${client_secret}"
    fi
    if [[ -n "${user_google_email:-}" ]]; then
        export USER_GOOGLE_EMAIL="${user_google_email}"
    fi

    # Force legacy OAuth flow for stdio + local refresh_token integration.
    export MCP_ENABLE_OAUTH21="false"

    # Ensure workspace-mcp can read credentials from a deterministic location.
    export WORKSPACE_MCP_CREDENTIALS_DIR="$ARIA_HOME/.aria/runtime/credentials/google_workspace_mcp"

    if [[ -n "${user_google_email:-}" ]]; then
        GW_USER_EMAIL="$user_google_email" \
        GW_CLIENT_ID="$client_id" \
        GW_CLIENT_SECRET="$client_secret" \
        GW_REFRESH_TOKEN="$refresh_token" \
        sync_workspace_credentials_file "$user_google_email" "$client_id" "$client_secret" "$refresh_token"
    fi

    # Execute upstream Google Workspace MCP via uvx
    # Context7 docs: command is `workspace-mcp`
    exec uvx workspace-mcp "$@"
}

main "$@"
