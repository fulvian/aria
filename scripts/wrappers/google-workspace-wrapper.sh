#!/usr/bin/env bash
#
# Google Workspace MCP Wrapper Script
#
# Provides robust OAuth configuration, credential fallback from existing token JSON,
# single-user mode for refresh_token reuse, and expanded tool set (Gmail + Calendar).
#
# Usage:
#   ./google-workspace-wrapper.sh [--readonly]
#   ./google-workspace-wrapper.sh [--check]
#
# Environment Variables:
#   GOOGLE_OAUTH_CLIENT_ID       - OAuth client ID (required)
#   GOOGLE_OAUTH_CLIENT_SECRET   - OAuth client secret (required)
#   GOOGLE_OAUTH_REDIRECT_URI    - Callback URI (default: http://127.0.0.1:8080/callback)
#   USER_GOOGLE_EMAIL            - Google account email for --single-user mode
#   GOOGLE_WORKSPACE_TOOLS       - Tool set (default: gmail drive calendar docs sheets slides)
#   OAUTHLIB_INSECURE_TRANSPORT  - Required for local loopback OAuth

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default values
REDIRECT_PORT="${GOOGLE_OAUTH_REDIRECT_PORT:-8080}"
TOOLS="${GOOGLE_WORKSPACE_TOOLS:-gmail drive calendar docs sheets slides}"
MODE="write"

# Strip placeholder ${VAR} literals from env vars
for VAR in GOOGLE_OAUTH_CLIENT_ID GOOGLE_OAUTH_CLIENT_SECRET USER_GOOGLE_EMAIL; do
  if [[ "${!VAR:-}" =~ ^\$\{[A-Z0-9_]+\}$ ]]; then
    unset "$VAR"
  fi
done

# Fallback: read OAuth credentials from existing token JSON if env vars missing
TOKEN_JSON="$PROJECT_ROOT/.aria/runtime/credentials/google_workspace_mcp/fulviold@gmail.com.json"
if [[ -z "${GOOGLE_OAUTH_CLIENT_ID:-}" ]] && [[ -f "$TOKEN_JSON" ]]; then
  export GOOGLE_OAUTH_CLIENT_ID="$(python3 -c "import json; print(json.load(open('$TOKEN_JSON'))['client_id'])" 2>/dev/null || true)"
fi
if [[ -z "${GOOGLE_OAUTH_CLIENT_SECRET:-}" ]] && [[ -f "$TOKEN_JSON" ]]; then
  export GOOGLE_OAUTH_CLIENT_SECRET="$(python3 -c "import json; print(json.load(open('$TOKEN_JSON'))['client_secret'])" 2>/dev/null || true)"
fi

# Fallback: read USER_GOOGLE_EMAIL from env or from email file
EMAIL_FILE="$PROJECT_ROOT/.aria/runtime/credentials/google_workspace_user_email.txt"
if [[ -z "${USER_GOOGLE_EMAIL:-}" ]] && [[ -f "$EMAIL_FILE" ]]; then
  USER_GOOGLE_EMAIL="$(cat "$EMAIL_FILE" | tr -d '[:space:]')"
  export USER_GOOGLE_EMAIL
fi

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --readonly)
            MODE="readonly"
            REDIRECT_PORT="${GOOGLE_OAUTH_REDIRECT_PORT_RO:-8081}"
            shift
            ;;
        --check)
            MODE="check"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--readonly] [--check]"
            echo "  --readonly  Start in read-only fallback mode"
            echo "  --check     Check configuration and exit"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Build redirect URI using loopback IP (more reliable than localhost in hybrid envs)
REDIRECT_URI="${GOOGLE_OAUTH_REDIRECT_URI:-http://127.0.0.1:${REDIRECT_PORT}/callback}"

# Export for MCP server
export GOOGLE_OAUTH_REDIRECT_URI="$REDIRECT_URI"
export GOOGLE_OAUTH_USE_PKCE="true"

# Enable insecure transport for local dev (required for loopback in some cases)
if [[ -z "${OAUTHLIB_INSECURE_TRANSPORT:-}" ]]; then
    export OAUTHLIB_INSECURE_TRANSPORT=1
fi

# Check mode - just verify configuration
if [[ "$MODE" == "check" ]]; then
    echo "=== Google Workspace MCP Configuration Check ==="
    echo "Mode: $MODE"
    echo "Tools: $TOOLS"
    echo "Redirect URI: $REDIRECT_URI"
    echo ""

    if [[ -z "${GOOGLE_OAUTH_CLIENT_ID:-}" ]]; then
        echo "ERROR: GOOGLE_OAUTH_CLIENT_ID is not set"
        exit 1
    fi
    echo "CLIENT_ID: ${GOOGLE_OAUTH_CLIENT_ID:0:20}..."

    if [[ -z "${GOOGLE_OAUTH_CLIENT_SECRET:-}" ]]; then
        echo "ERROR: GOOGLE_OAUTH_CLIENT_SECRET is not set"
        exit 1
    fi
    echo "CLIENT_SECRET: *** (set)"

    if [[ -n "${USER_GOOGLE_EMAIL:-}" ]]; then
        echo "USER_GOOGLE_EMAIL: $USER_GOOGLE_EMAIL"
    else
        echo "WARN: USER_GOOGLE_EMAIL not set (single-user mode will not work)"
    fi
    echo ""
    echo "Configuration OK"
    exit 0
fi

# Sync token to standard workspace-mcp location (~/.google_workspace_mcp/credentials/)
# workspace-mcp looks here by default (not in the ARIA project path)
STD_CRED_DIR="$HOME/.google_workspace_mcp/credentials"
if [[ -f "$TOKEN_JSON" ]]; then
  mkdir -p "$STD_CRED_DIR"
  if ! cmp -s "$TOKEN_JSON" "$STD_CRED_DIR/fulviold@gmail.com.json" 2>/dev/null; then
    cp "$TOKEN_JSON" "$STD_CRED_DIR/fulviold@gmail.com.json"
    chmod 600 "$STD_CRED_DIR/fulviold@gmail.com.json"
    echo "INFO: Token synced to $STD_CRED_DIR" >&2
  fi
fi

# Build command — always single-user with expanded tool set
CMD="uvx workspace-mcp --single-user --tools $TOOLS"

echo "=== Starting Google Workspace MCP ==="
echo "Mode: $MODE"
echo "Tools: $TOOLS"
echo "Redirect URI: $REDIRECT_URI"
echo "Command: $CMD"
echo ""

# Execute
exec $CMD
