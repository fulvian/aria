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

# Pre-refresh the access token so workspace-mcp sees valid credentials
# and doesn't trigger its own OAuth re-auth flow.
refresh_access_token() {
    local refresh_token="$1"
    local client_id="$2"
    local client_secret="$3"

    "$PYTHON_BIN" -c "
import json, os, sys, urllib.parse, urllib.request

refresh_token = os.environ['GW_REFRESH_TOKEN'].strip()
client_id = os.environ['GW_CLIENT_ID'].strip()
client_secret = os.environ.get('GW_CLIENT_SECRET', '').strip()

if not refresh_token or not client_id:
    # Output empty — caller will fall back to null token
    print('')
    sys.exit(0)

payload = {
    'client_id': client_id,
    'refresh_token': refresh_token,
    'grant_type': 'refresh_token',
}
if client_secret:
    payload['client_secret'] = client_secret

try:
    req = urllib.request.Request(
        'https://oauth2.googleapis.com/token',
        data=urllib.parse.urlencode(payload).encode('utf-8'),
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    access_token = data.get('access_token', '')
    expires_in = data.get('expires_in', 3600)
    if access_token:
        from datetime import datetime, timezone, timedelta
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        print(f'{access_token}\n{expiry}')
    else:
        print('')
except Exception as e:
    print(f'WARN: token refresh failed: {e}', file=sys.stderr)
    print('')
" 2>/dev/null
}

sync_workspace_credentials_file() {
    local user_email="$1"
    local client_id="$2"
    local client_secret="$3"
    local refresh_token="$4"

    # Pre-refreshed token is passed via GW_PRETOKEN / GW_PREEXPIRY env vars
    # (set in main() before calling this function).

    "$PYTHON_BIN" -c "
import json
import os
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path

user_email = os.environ['GW_USER_EMAIL'].strip()
client_id = os.environ['GW_CLIENT_ID'].strip()
client_secret = os.environ.get('GW_CLIENT_SECRET', '').strip()
refresh_token = os.environ['GW_REFRESH_TOKEN'].strip()
wrapper_args_raw = os.environ.get('GW_WRAPPER_ARGS', '')
prerefreshed_token = os.environ.get('GW_PRETOKEN', '').strip()
prerefreshed_expiry = os.environ.get('GW_PREEXPIRY', '').strip()
aria_home = Path('$ARIA_HOME')

GOOGLE_SCOPE_PREFIX = 'https://www.googleapis.com/auth/'
CORE_READ_SCOPES = {
    f'{GOOGLE_SCOPE_PREFIX}gmail.readonly',
    f'{GOOGLE_SCOPE_PREFIX}calendar.readonly',
    f'{GOOGLE_SCOPE_PREFIX}drive.readonly',
    f'{GOOGLE_SCOPE_PREFIX}documents.readonly',
    f'{GOOGLE_SCOPE_PREFIX}spreadsheets.readonly',
    f'{GOOGLE_SCOPE_PREFIX}presentations.readonly',
}


def normalize_scope(scope: str) -> str:
    scope = scope.strip()
    if not scope:
        return ''
    if scope.startswith('https://'):
        return scope
    return f'{GOOGLE_SCOPE_PREFIX}{scope}'


def parse_governance_rows(matrix_path: Path) -> list[dict[str, str]]:
    if not matrix_path.exists():
        return []

    lines = matrix_path.read_text(encoding='utf-8').splitlines()
    expected_headers = [
        'tool_name',
        'domain',
        'rw',
        'risk',
        'policy',
        'hitl_required',
        'min_scope',
        'owner',
        'testcase_id',
    ]
    rows: list[dict[str, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('|') and 'tool_name' in line.lower():
            i += 2
            while i < len(lines) and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].split('|') if c.strip()]
                if len(cells) >= len(expected_headers) and not all(c.startswith('-') for c in cells):
                    row = {h: cells[idx] for idx, h in enumerate(expected_headers)}
                    if row.get('tool_name') and row['tool_name'] != 'tool_name':
                        rows.append(row)
                i += 1
            continue
        i += 1

    return rows


def parse_cli_args(argv: list[str], all_domains: set[str]) -> tuple[set[str], bool, dict[str, str]]:
    domains: set[str] = set()
    permissions: dict[str, str] = {}
    read_only = '--read-only' in argv

    tier_map = {
        'core': {'gmail', 'calendar', 'drive', 'docs', 'sheets', 'slides'},
        'extended': {'gmail', 'calendar', 'drive', 'docs', 'sheets', 'slides', 'chat', 'tasks', 'forms', 'contacts'},
        'complete': set(all_domains),
    }

    if '--tool-tier' in argv:
        idx = argv.index('--tool-tier')
        if idx + 1 < len(argv):
            tier = argv[idx + 1].strip().lower()
            domains = tier_map.get(tier, set())

    if '--tools' in argv:
        idx = argv.index('--tools') + 1
        tool_domains: list[str] = []
        while idx < len(argv) and not argv[idx].startswith('--'):
            tool_domains.append(argv[idx].strip().lower())
            idx += 1
        if tool_domains:
            domains = set(tool_domains)

    if '--permissions' in argv:
        idx = argv.index('--permissions') + 1
        while idx < len(argv) and not argv[idx].startswith('--'):
            raw = argv[idx].strip().lower()
            if ':' in raw:
                service, level = raw.split(':', 1)
                permissions[service] = level
            idx += 1
        if permissions:
            domains = set(permissions.keys())

    return domains, read_only, permissions


def enforce_scope_coherence(resolved_scopes: list[str], argv: list[str]) -> set[str]:
    enforce = os.environ.get('WORKSPACE_ENFORCE_SCOPE_COHERENCE', 'true').strip().lower()
    if enforce in {'0', 'false', 'no'}:
        return set()

    matrix_path = aria_home / 'docs' / 'roadmaps' / 'workspace_tool_governance_matrix.md'
    rows = parse_governance_rows(matrix_path)
    if not rows:
        return set()

    all_domains = {row['domain'] for row in rows}
    active_domains, read_only, permissions = parse_cli_args(argv, all_domains)

    if not active_domains:
        # Pragmatic default: when no explicit tier/tools are provided, assume core read
        # coverage is needed to avoid runtime authorization prompts for simple read tasks.
        return set(CORE_READ_SCOPES)

    required_scopes: set[str] = set()
    gmail_level_map = {
        'readonly': {'gmail.readonly'},
        'organize': {'gmail.readonly', 'gmail.modify'},
        'drafts': {'gmail.readonly', 'gmail.modify', 'gmail.drafts'},
        'send': {'gmail.readonly', 'gmail.modify', 'gmail.drafts', 'gmail.send'},
        'full': {'gmail.readonly', 'gmail.modify', 'gmail.drafts', 'gmail.send', 'gmail'},
    }

    for row in rows:
        if row['domain'] not in active_domains:
            continue
        if row.get('policy') == 'deny':
            continue

        if permissions:
            service_level = permissions.get(row['domain'])
            if not service_level:
                continue
            if row['domain'] == 'gmail':
                min_scope = row.get('min_scope', '').strip()
                if min_scope and min_scope not in gmail_level_map.get(service_level, set()):
                    continue
            elif service_level == 'readonly' and row.get('rw') != 'read':
                continue
        elif read_only and row.get('rw') != 'read':
            continue

        scope = normalize_scope(row.get('min_scope', ''))
        if scope:
            required_scopes.add(scope)

    granted = set(resolved_scopes)
    missing = sorted(required_scopes - granted)
    if missing:
        raise SystemExit(
            'Missing OAuth scopes for active workspace toolset: '
            + ', '.join(missing)
            + '. Re-run oauth setup with required scopes or adjust --tools/--tool-tier/--permissions.'
        )

    return required_scopes

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

scopes = sorted({normalize_scope(scope) for scope in scopes if normalize_scope(scope)})
wrapper_args = shlex.split(wrapper_args_raw)
coherence_required = enforce_scope_coherence(scopes, wrapper_args)

# Scope floor policy (default: core-read) to keep read operations functional across
# Drive/Docs/Sheets/Slides even when runtime scopes metadata is stale/incomplete.
scope_floor_mode = os.environ.get('WORKSPACE_SCOPE_FLOOR', 'core-read').strip().lower()
scope_floor = set()
if scope_floor_mode in {'core-read', 'read-core', 'read'}:
    scope_floor |= CORE_READ_SCOPES

effective_scopes = sorted(set(scopes) | scope_floor | coherence_required)

creds_dir = Path(os.environ['GOOGLE_MCP_CREDENTIALS_DIR']).expanduser()
creds_dir.mkdir(parents=True, exist_ok=True)
os.chmod(creds_dir, 0o700)

safe_email = re.sub(r'[^a-zA-Z0-9@._-]', '_', user_email)
creds_path = creds_dir / f'{safe_email}.json'

existing_token: str | None = None
existing_expiry: str | None = None
if creds_path.exists():
    try:
        existing = json.loads(creds_path.read_text(encoding='utf-8'))
        token_candidate = existing.get('token')
        expiry_candidate = existing.get('expiry')

        def _parse_expiry(value: object) -> datetime | None:
            if not isinstance(value, str) or not value.strip():
                return None
            raw = value.strip()
            if raw.endswith('Z'):
                raw = raw[:-1] + '+00:00'
            try:
                parsed = datetime.fromisoformat(raw)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed

        parsed_expiry = _parse_expiry(expiry_candidate)
        if (
            isinstance(token_candidate, str)
            and token_candidate.strip()
            and parsed_expiry is not None
            and parsed_expiry > datetime.now(timezone.utc)
        ):
            existing_token = token_candidate.strip()
            existing_expiry = expiry_candidate.strip() if isinstance(expiry_candidate, str) else None
    except Exception:
        existing_token = None
        existing_expiry = None

# Important: a blank token with null expiry is considered valid by google-auth,
# which can produce unauthenticated requests (Drive 403 unregistered callers).
# Force refresh path when we only have refresh_token bootstrap material.
# Pre-refreshed token takes priority over existing file token.
if prerefreshed_token:
    final_token = prerefreshed_token
    final_expiry = prerefreshed_expiry if prerefreshed_expiry else '1970-01-01T00:00:00+00:00'
elif existing_token:
    final_token = existing_token
    final_expiry = existing_expiry if existing_expiry else '1970-01-01T00:00:00+00:00'
else:
    final_token = None
    final_expiry = '1970-01-01T00:00:00+00:00'

payload = {
    'token': final_token,
    'refresh_token': refresh_token,
    'token_uri': 'https://oauth2.googleapis.com/token',
    'client_id': client_id,
    'client_secret': client_secret,
    'scopes': effective_scopes,
    'expiry': final_expiry,
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

is_truthy() {
    local value="${1:-}"
    value="${value,,}"
    [[ -n "$value" && "$value" != "0" && "$value" != "false" && "$value" != "no" ]]
}

emit_default_tools() {
    local raw_tools="${WORKSPACE_DEFAULT_TOOLS:-gmail,calendar,drive,docs,sheets,slides}"
    local normalized="${raw_tools//,/ }"

    for tool in $normalized; do
        local trimmed="${tool//[[:space:]]/}"
        if [[ -n "$trimmed" ]]; then
            printf '%s\n' "$trimmed"
        fi
    done
}

build_workspace_mcp_args() {
    local -n _out_args=$1
    shift

    local -a input_args=("$@")
    _out_args=("${input_args[@]}")

    local has_selector=0
    local idx=0
    while [[ $idx -lt ${#input_args[@]} ]]; do
        case "${input_args[$idx]}" in
            --tool-tier|--tools|--permissions)
                has_selector=1
                ;;
        esac
        idx=$((idx + 1))
    done

    if [[ $has_selector -eq 0 ]]; then
        local -a default_tools=()
        while IFS= read -r tool; do
            default_tools+=("$tool")
        done < <(emit_default_tools)

        if [[ ${#default_tools[@]} -gt 0 ]]; then
            _out_args+=("--tools")
            _out_args+=("${default_tools[@]}")
        else
            local default_tier="${WORKSPACE_DEFAULT_TOOL_TIER:-core}"
            if [[ -n "$default_tier" ]]; then
                _out_args+=("--tool-tier" "$default_tier")
            fi
        fi

        if is_truthy "${WORKSPACE_DEFAULT_READ_ONLY:-true}"; then
            _out_args+=("--read-only")
        fi
    fi
}

prune_workspace_args_by_granted_scopes() {
    local -n _args_ref=$1
    local refresh_token="$2"
    local client_id="$3"
    local client_secret="$4"

    if ! is_truthy "${WORKSPACE_AUTO_PRUNE_TO_GRANTED_SCOPES:-true}"; then
        return 0
    fi

    local serialized_args
    serialized_args="$(printf '%s\n' "${_args_ref[@]}")"

    local pruned_output
    if ! pruned_output="$(
        GW_SERIALIZED_ARGS="$serialized_args" \
        GW_REFRESH_TOKEN="$refresh_token" \
        GW_CLIENT_ID="$client_id" \
        GW_CLIENT_SECRET="$client_secret" \
        "$PYTHON_BIN" - <<'PY'
import json
import os
import sys
import urllib.parse
import urllib.request

GOOGLE_SCOPE_PREFIX = 'https://www.googleapis.com/auth/'

args = [line for line in os.environ.get('GW_SERIALIZED_ARGS', '').splitlines() if line]
if '--tools' not in args:
    print('\n'.join(args))
    raise SystemExit(0)

refresh_token = os.environ.get('GW_REFRESH_TOKEN', '').strip()
client_id = os.environ.get('GW_CLIENT_ID', '').strip()
client_secret = os.environ.get('GW_CLIENT_SECRET', '').strip()
override_raw = os.environ.get('WORKSPACE_GRANTED_SCOPES_OVERRIDE', '').strip()

granted = set()
if override_raw:
    granted = {
        scope.strip()
        for scope in override_raw.replace(',', ' ').split()
        if scope.strip().startswith(GOOGLE_SCOPE_PREFIX)
    }

if not granted:
    if not refresh_token or not client_id:
        print('\n'.join(args))
        raise SystemExit(0)

    payload = {
        'client_id': client_id,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    }
    if client_secret:
        payload['client_secret'] = client_secret

    try:
        request = urllib.request.Request(
            'https://oauth2.googleapis.com/token',
            data=urllib.parse.urlencode(payload).encode('utf-8'),
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            token_data = json.loads(response.read().decode('utf-8'))
    except Exception:
        print('\n'.join(args))
        raise SystemExit(0)

    granted = {
        scope.strip()
        for scope in str(token_data.get('scope', '')).split()
        if scope.strip().startswith(GOOGLE_SCOPE_PREFIX)
    }

if not granted:
    print('\n'.join(args))
    raise SystemExit(0)

required = {
    'gmail': f'{GOOGLE_SCOPE_PREFIX}gmail.readonly',
    'calendar': f'{GOOGLE_SCOPE_PREFIX}calendar.readonly',
    'drive': f'{GOOGLE_SCOPE_PREFIX}drive.readonly',
    'docs': f'{GOOGLE_SCOPE_PREFIX}documents.readonly',
    'sheets': f'{GOOGLE_SCOPE_PREFIX}spreadsheets.readonly',
    'slides': f'{GOOGLE_SCOPE_PREFIX}presentations.readonly',
}

idx = args.index('--tools') + 1
tool_end = idx
while tool_end < len(args) and not args[tool_end].startswith('--'):
    tool_end += 1

tools = args[idx:tool_end]
keep_tools = []
dropped = []
for tool in tools:
    name = tool.strip().lower()
    needed = required.get(name)
    if needed and needed not in granted:
        dropped.append((name, needed))
        continue
    keep_tools.append(tool)

if not dropped:
    # No tools were pruned - all requested scopes are granted
    print('\n'.join(args))
    raise SystemExit(0)

if not keep_tools:
    # ALL requested tools were pruned - user lacks ALL required scopes.
    # Fall back to a minimal set of definitely-granted scopes so at least
    # Drive read works (via get_drive_file_content). Slides/Docs/etc will
    # require separate re-authorization with specific scopes.
    # Use the subset of tools that ARE granted.
    minimal_granted = []
    for tool in tools:
        name = tool.strip().lower()
        needed = required.get(name)
        if needed and needed in granted:
            minimal_granted.append(tool)

    if not minimal_granted:
        # Nothing at all is granted - should not happen but be safe
        print('\n'.join(args))
        raise SystemExit(0)

    drop_details = ', '.join(f'{name}({scope})' for name, scope in dropped)
    print(f'WARNING: Missing granted scopes for all requested tools. ', file=sys.stderr)
    print(f'Driving: falling back to granted tools: {" ".join(minimal_granted)}', file=sys.stderr)
    new_args = args[:idx] + minimal_granted + args[tool_end:]
    print('\n'.join(new_args))
    raise SystemExit(0)

new_args = args[:idx] + keep_tools + args[tool_end:]
drop_details = ', '.join(f'{name}({scope})' for name, scope in dropped)
print(f'INFO: workspace wrapper pruned tools missing granted scope: {drop_details}', file=sys.stderr)
print('\n'.join(new_args))
PY
    )"; then
        return 0
    fi

    local -a pruned_args=()
    while IFS= read -r line; do
        if [[ -n "$line" ]]; then
            pruned_args+=("$line")
        fi
    done <<<"$pruned_output"

    if [[ ${#pruned_args[@]} -gt 0 ]]; then
        _args_ref=("${pruned_args[@]}")
    fi
}

# Main
main() {
    local -a effective_args
    build_workspace_mcp_args effective_args "$@"

    if is_truthy "${WORKSPACE_WRAPPER_DRY_RUN:-false}"; then
        printf '%s\n' "${effective_args[@]}"
        return 0
    fi

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
    export GOOGLE_MCP_CREDENTIALS_DIR="$ARIA_HOME/.aria/runtime/credentials/google_workspace_mcp"

    if [[ -n "${user_google_email:-}" ]]; then
        prune_workspace_args_by_granted_scopes effective_args "$refresh_token" "$client_id" "$client_secret"

        # Pre-refresh access token so workspace-mcp gets valid credentials
        # and doesn't trigger its own OAuth re-auth flow.
        local refreshed
        refreshed="$(refresh_access_token "$refresh_token" "$client_id" "$client_secret")" || refreshed=""
        local fresh_access_token
        local fresh_expiry
        fresh_access_token="$(printf '%s\n' "$refreshed" | sed -n '1p')"
        fresh_expiry="$(printf '%s\n' "$refreshed" | sed -n '2p')"

        local wrapper_args_serialized=""
        if [[ ${#effective_args[@]} -gt 0 ]]; then
            wrapper_args_serialized="$(printf '%q ' "${effective_args[@]}")"
        fi

        GW_USER_EMAIL="$user_google_email" \
        GW_CLIENT_ID="$client_id" \
        GW_CLIENT_SECRET="$client_secret" \
        GW_REFRESH_TOKEN="$refresh_token" \
        GW_WRAPPER_ARGS="$wrapper_args_serialized" \
        GW_PRETOKEN="$fresh_access_token" \
        GW_PREEXPIRY="$fresh_expiry" \
        sync_workspace_credentials_file "$user_google_email" "$client_id" "$client_secret" "$refresh_token"
    fi

    # Execute upstream Google Workspace MCP via uvx
    # Context7 docs: command is `workspace-mcp`
    exec uvx workspace-mcp "${effective_args[@]}"
}

main "$@"
