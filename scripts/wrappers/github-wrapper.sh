#!/usr/bin/env bash
# GitHub MCP wrapper per blueprint §10.3
# Decrypts SOPS api-keys.enc.yaml, extracts github.token, injects GITHUB_PERSONAL_ACCESS_TOKEN,
# launches @modelcontextprotocol/server-github via npx with correct bin resolution.

set -euo pipefail

ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"
SOPS_KEY_FILE="${SOPS_AGE_KEY_FILE:-$HOME/.config/sops/age/keys.txt}"
SECRETS_FILE="$ARIA_HOME/.aria/credentials/secrets/api-keys.enc.yaml"

if [[ ! -f "$SECRETS_FILE" ]]; then
    echo "github-wrapper: missing secrets file: $SECRETS_FILE" >&2
    exit 1
fi
if [[ ! -f "$SOPS_KEY_FILE" ]]; then
    echo "github-wrapper: missing SOPS age key: $SOPS_KEY_FILE" >&2
    exit 1
fi

GH_TOKEN="$(SOPS_AGE_KEY_FILE="$SOPS_KEY_FILE" sops -d "$SECRETS_FILE" \
    | "$ARIA_HOME/.venv/bin/python" -c "
import sys, yaml
data = yaml.safe_load(sys.stdin)
tok = data.get('github', {}).get('token')
if not tok:
    sys.stderr.write('github-wrapper: no github.token in secrets\n'); sys.exit(2)
print(tok)
")"

if [[ -z "$GH_TOKEN" ]]; then
    echo "github-wrapper: empty github token" >&2
    exit 3
fi

exec env -i \
    HOME="$HOME" \
    PATH="$PATH" \
    USER="$USER" \
    GITHUB_PERSONAL_ACCESS_TOKEN="$GH_TOKEN" \
    npx -y --package=@modelcontextprotocol/server-github mcp-server-github
