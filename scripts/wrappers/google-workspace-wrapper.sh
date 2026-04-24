#!/usr/bin/env bash
#
# Google Workspace MCP Wrapper Script
#
# This wrapper provides a robust startup profile for the Google Workspace MCP server
# with proper OAuth configuration and loopback IP callback for reliability.
#
# Usage:
#   ./google-workspace-wrapper.sh [--readonly]
#   ./google-workspace-wrapper.sh [--check]
#
# Environment Variables Required:
#   GOOGLE_OAUTH_CLIENT_ID     - OAuth client ID
#   GOOGLE_OAUTH_CLIENT_SECRET - OAuth client secret
#
# Environment Variables Optional:
#   GOOGLE_OAUTH_REDIRECT_URI  - Callback URI (default: http://127.0.0.1:8080/callback)
#   OAUTHLIB_INSECURE_TRANSPORT=1  - For local development only
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default values
REDIRECT_PORT="${GOOGLE_OAUTH_REDIRECT_PORT:-8080}"
TOOLS="${GOOGLE_WORKSPACE_TOOLS:-docs sheets slides drive}"
MODE="write"

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
REDIRECT_URI="http://127.0.0.1:${REDIRECT_PORT}/callback"

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
    echo ""
    echo "Configuration OK"
    exit 0
fi

# Build command
CMD="uvx workspace-mcp --tools $TOOLS"

echo "=== Starting Google Workspace MCP ==="
echo "Mode: $MODE"
echo "Tools: $TOOLS"
echo "Redirect URI: $REDIRECT_URI"
echo "Command: $CMD"
echo ""

# Execute
exec $CMD
