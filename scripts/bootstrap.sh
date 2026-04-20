#!/usr/bin/env bash
# ARIA Bootstrap Script
# Initializes the ARIA environment for first-time use
# Idempotent - safe to run multiple times

set -euo pipefail

ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"
ARIA_PYTHON_BIN="${ARIA_PYTHON_BIN:-$(command -v python3)}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# === Check mode (for CI or interactive) ===
CHECK_MODE=false
if [[ "${1:-}" == "--check" ]]; then
    CHECK_MODE=true
fi

# === Pre-flight checks ===
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=()
    local tools=("sops" "age" "sqlite3")

    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing+=("$tool")
        fi
    done

    # Check for uv
    if ! command -v uv &> /dev/null; then
        missing+=("uv")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        if [[ "$CHECK_MODE" == "true" ]]; then
            log_error "Missing tools: ${missing[*]}"
            exit 1
        else
            log_warn "Missing tools: ${missing[*]}"
            log_warn "Install with: apt install sops age sqlite3 && curl -LsSf https://astral.sh/uv/install.sh | sh"
        fi
    fi

    # Check SQLite version
    local sqlite_version
    sqlite_version=$(sqlite3 --version | awk '{print $1}')
    local required_version="3.51.3"
    if [[ "$(printf '%s\n' "$required_version" "$sqlite_version" | sort -V | head -n1)" != "$required_version" ]]; then
        log_error "SQLite version $sqlite_version is below minimum required $required_version"
        log_error "See: https://sqlite.org/releaselog/3_51_3.html"
        exit 1
    fi

    # Check Python sqlite runtime version (authoritative for ARIA code)
    local py_sqlite_version
    py_sqlite_version=$($ARIA_PYTHON_BIN -c "import sqlite3; print(sqlite3.sqlite_version)")
    if [[ "$(printf '%s\n' "$required_version" "$py_sqlite_version" | sort -V | head -n1)" != "$required_version" ]]; then
        log_error "Python sqlite runtime $py_sqlite_version is below minimum required $required_version"
        log_error "Set ARIA_PYTHON_BIN to an interpreter with sqlite >= $required_version"
        exit 1
    fi

    log_info "Prerequisites OK"
}

# === Create directory structure ===
create_directories() {
    log_info "Creating directory structure..."
    mkdir -p "$ARIA_HOME/.aria/runtime/memory/semantic"
    mkdir -p "$ARIA_HOME/.aria/runtime/scheduler"
    mkdir -p "$ARIA_HOME/.aria/runtime/gateway"
    mkdir -p "$ARIA_HOME/.aria/runtime/logs"
    mkdir -p "$ARIA_HOME/.aria/runtime/tmp"
    mkdir -p "$ARIA_HOME/.aria/credentials/secrets"
    mkdir -p "$ARIA_HOME/.aria/kilocode/agents/_system"
    mkdir -p "$ARIA_HOME/.aria/kilocode/skills"
    mkdir -p "$ARIA_HOME/.aria/kilocode/modes"
    mkdir -p "$ARIA_HOME/.aria/kilocode/sessions"
    mkdir -p "$HOME/.config/sops/age"
    log_info "Directory structure created"
}

# === Initialize Python environment ===
init_python() {
    log_info "Initializing Python environment..."

    if [[ ! -d "$ARIA_HOME/.venv" ]]; then
        uv venv --python "$ARIA_PYTHON_BIN" "$ARIA_HOME/.venv"
        log_info "Virtual environment created"
    else
        log_info "Virtual environment already exists"
    fi

    uv sync --extra dev
    log_info "Python dependencies installed"
}

# === Generate age keypair ===
generate_age_keys() {
    log_info "Checking age keys..."

    local key_file="$HOME/.config/sops/age/keys.txt"
    local pub_file="$ARIA_HOME/.age.pub"

    if [[ -f "$key_file" ]]; then
        log_info "Age key already exists at $key_file"
        # Show public key
        age-keygen -y "$key_file" > "$pub_file" 2>/dev/null || true
        log_info "Public key saved to $pub_file"
    else
        log_warn "Age key not found at $key_file"
        log_warn "Generate with: age-keygen -o $key_file"
        log_warn "Then update .aria/credentials/.sops.yaml with your public key"
    fi
}

# === Verify SOPS configuration ===
verify_sops() {
    log_info "Verifying SOPS configuration..."

    local sops_conf="$ARIA_HOME/.aria/credentials/.sops.yaml"
    local api_keys="$ARIA_HOME/.aria/credentials/secrets/api-keys.enc.yaml"

    if [[ -f "$sops_conf" ]]; then
        log_info "SOPS config found: $sops_conf"
    else
        log_error "SOPS config missing: $sops_conf"
        return 1
    fi

    if [[ -f "$api_keys" ]]; then
        log_info "Encrypted API keys file found: $api_keys"
        # Try to decrypt as a smoke test
        if sops -d "$api_keys" &> /dev/null; then
            log_info "SOPS decryption test: OK"
        else
            log_warn "SOPS decryption test failed (expected if not yet encrypted with valid key)"
        fi
    else
        log_error "API keys file missing: $api_keys"
        return 1
    fi
}

# === Verify KiloCode configuration ===
verify_kilocode() {
    log_info "Verifying KiloCode configuration..."

    local kilo_json="$ARIA_HOME/.aria/kilocode/kilo.json"
    local mcp_json="$ARIA_HOME/.aria/kilocode/mcp.json"

    if [[ -f "$kilo_json" ]]; then
        log_info "KiloCode config found: $kilo_json"
    else
        log_error "KiloCode config missing: $kilo_json"
        return 1
    fi

    if [[ -f "$mcp_json" ]]; then
        log_info "MCP config found: $mcp_json"
    else
        log_error "MCP config missing: $mcp_json"
        return 1
    fi
}

# === Main bootstrap ===
main() {
    log_info "ARIA Bootstrap Script"
    log_info "ARIA_HOME: $ARIA_HOME"

    check_prerequisites
    create_directories

    if [[ "$CHECK_MODE" == "false" ]]; then
        init_python
        generate_age_keys
    fi

    verify_sops
    verify_kilocode

    log_info "Bootstrap complete!"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Generate age keys: age-keygen -o ~/.config/sops/age/keys.txt"
    log_info "  2. Update .aria/credentials/.sops.yaml with your public key"
    log_info "  3. Encrypt your API keys: sops .aria/credentials/secrets/api-keys.enc.yaml"
    log_info "  4. Test launcher: ./bin/aria --help"
}

main "$@"
