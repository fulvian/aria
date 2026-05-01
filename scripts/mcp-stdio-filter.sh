#!/usr/bin/env bash
# MCP stdio filter — redirects non-JSONRPC stdout lines to stderr.
#
# Wraps any MCP server process so that only lines starting with '{"jsonrpc":'
# go to stdout. Everything else (startup info, log messages) goes to stderr.
#
# Usage (in a wrapper script):
#   exec "$(dirname "$0")/mcp-stdio-filter.sh" -- <real-server-command> [args...]

set -euo pipefail

if [[ "$*" != *"--"* ]]; then
    echo "Usage: mcp-stdio-filter.sh -- <command> [args...]" >&2
    exit 1
fi

# Find the -- separator
args=("$@")
sep_idx=0
for i in "${!args[@]}"; do
    if [[ "${args[$i]}" == "--" ]]; then
        sep_idx=$i
        break
    fi
done

cmd=("${args[@]:$((sep_idx + 1))}")

if [[ ${#cmd[@]} -eq 0 ]]; then
    echo "No command specified." >&2
    exit 1
fi

# Save original stdout
exec 3>&1

# Start the real server, pipe stdout through a JSONRPC filter
"${cmd[@]}" 2>&1 | while IFS= read -r line; do
    if [[ "$line" == '{"jsonrpc':* ]]; then
        echo "$line" >&3
    else
        echo "[mcp-filter] $line" >&2
    fi
done

exit "${PIPESTATUS[0]}"
