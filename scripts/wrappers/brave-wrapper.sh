#!/usr/bin/env bash
# Brave Search MCP wrapper per blueprint §10.3
# Decrypts SOPS api-keys.enc.yaml, extracts brave.active key, injects BRAVE_API_KEY,
# launches @brave/brave-search-mcp-server via npx with correct bin resolution.

set -euo pipefail

ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"
SOPS_KEY_FILE="${SOPS_AGE_KEY_FILE:-$HOME/.config/sops/age/keys.txt}"
SECRETS_FILE="$ARIA_HOME/.aria/credentials/secrets/api-keys.enc.yaml"

if [[ ! -f "$SECRETS_FILE" ]]; then
    echo "brave-wrapper: missing secrets file: $SECRETS_FILE" >&2
    exit 1
fi
if [[ ! -f "$SOPS_KEY_FILE" ]]; then
    echo "brave-wrapper: missing SOPS age key: $SOPS_KEY_FILE" >&2
    exit 1
fi

# Decrypt and extract first brave key (blueprint §10.4 rotation policy: first is primary)
BRAVE_KEY="$(SOPS_AGE_KEY_FILE="$SOPS_KEY_FILE" sops -d "$SECRETS_FILE" \
    | "$ARIA_HOME/.venv/bin/python" -c "
import sys, yaml
data = yaml.safe_load(sys.stdin)
keys = data.get('providers', {}).get('brave', [])
if not keys:
    sys.stderr.write('brave-wrapper: no brave keys in secrets\n'); sys.exit(2)
print(keys[0]['key'])
")"

if [[ -z "$BRAVE_KEY" ]]; then
    echo "brave-wrapper: empty brave key" >&2
    exit 3
fi

exec env -i \
    HOME="$HOME" \
    PATH="$PATH" \
    USER="$USER" \
    BRAVE_API_KEY="$BRAVE_KEY" \
    npx -y --package=@brave/brave-search-mcp-server brave-search-mcp-server
