#!/usr/bin/env bash
# ARIA systemd User Service Installer
# Copies systemd unit files to ~/.config/systemd/user/

set -euo pipefail

ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

show_usage() {
    cat <<'EOF'
ARIA systemd Service Installer

Usage: ./scripts/install_systemd.sh [command]

Commands:
  install     Install systemd unit files (default)
  reload      Reload systemd user daemon
  uninstall   Remove systemd unit files
  start       Start all ARIA services
  stop        Stop all ARIA services
  status      Show service status
  enable      Enable services to start on boot
  disable     Disable services from starting on boot

Examples:
  ./scripts/install_systemd.sh install
  ./scripts/install_systemd.sh start
  ./scripts/install_systemd.sh status

EOF
}

# === Install unit files ===
install_units() {
    log_info "Installing systemd unit files..."

    mkdir -p "$SYSTEMD_USER_DIR"

    if command -v systemd-analyze >/dev/null 2>&1; then
        log_info "Verifying unit files with systemd-analyze..."
        systemd-analyze verify \
            "$ARIA_HOME/systemd/aria-scheduler.service" \
            "$ARIA_HOME/systemd/aria-gateway.service" \
            "$ARIA_HOME/systemd/aria-memory.service"
    fi

    # Track if we need to reload
    local needs_reload=0

    # Copy scheduler unit (idempotent - only copy if different or missing)
    if [[ ! -f "$SYSTEMD_USER_DIR/aria-scheduler.service" ]] || \
       ! cmp -s "$ARIA_HOME/systemd/aria-scheduler.service" "$SYSTEMD_USER_DIR/aria-scheduler.service"; then
        cp "$ARIA_HOME/systemd/aria-scheduler.service" "$SYSTEMD_USER_DIR/"
        needs_reload=1
        log_info "Updated aria-scheduler.service"
    else
        log_info "aria-scheduler.service already up-to-date"
    fi

    # Copy gateway unit (idempotent - only copy if different or missing)
    if [[ ! -f "$SYSTEMD_USER_DIR/aria-gateway.service" ]] || \
       ! cmp -s "$ARIA_HOME/systemd/aria-gateway.service" "$SYSTEMD_USER_DIR/aria-gateway.service"; then
        cp "$ARIA_HOME/systemd/aria-gateway.service" "$SYSTEMD_USER_DIR/"
        needs_reload=1
        log_info "Updated aria-gateway.service"
    else
        log_info "aria-gateway.service already up-to-date"
    fi

    # Copy memory unit (idempotent - only copy if different or missing)
    if [[ ! -f "$SYSTEMD_USER_DIR/aria-memory.service" ]] || \
       ! cmp -s "$ARIA_HOME/systemd/aria-memory.service" "$SYSTEMD_USER_DIR/aria-memory.service"; then
        cp "$ARIA_HOME/systemd/aria-memory.service" "$SYSTEMD_USER_DIR/"
        needs_reload=1
        log_info "Updated aria-memory.service"
    else
        log_info "aria-memory.service already up-to-date"
    fi

    # Only reload if we actually changed something
    if [[ $needs_reload -eq 1 ]]; then
        systemctl --user daemon-reload
        log_info "Systemd daemon reloaded"
    fi

    log_info "Unit files installed to $SYSTEMD_USER_DIR"
}

# === Uninstall unit files ===
uninstall_units() {
    log_info "Uninstalling systemd unit files..."

    local removed=0

    if [[ -f "$SYSTEMD_USER_DIR/aria-scheduler.service" ]]; then
        rm -f "$SYSTEMD_USER_DIR/aria-scheduler.service"
        removed=1
        log_info "Removed aria-scheduler.service"
    else
        log_info "aria-scheduler.service not installed"
    fi

    if [[ -f "$SYSTEMD_USER_DIR/aria-gateway.service" ]]; then
        rm -f "$SYSTEMD_USER_DIR/aria-gateway.service"
        removed=1
        log_info "Removed aria-gateway.service"
    else
        log_info "aria-gateway.service not installed"
    fi

    if [[ -f "$SYSTEMD_USER_DIR/aria-memory.service" ]]; then
        rm -f "$SYSTEMD_USER_DIR/aria-memory.service"
        removed=1
        log_info "Removed aria-memory.service"
    else
        log_info "aria-memory.service not installed"
    fi

    if [[ $removed -eq 1 ]]; then
        systemctl --user daemon-reload
        log_info "Systemd daemon reloaded"
    else
        log_info "Nothing to uninstall"
    fi
}

# === Start services ===
start_services() {
    log_info "Starting ARIA services..."

    if [[ -f "$SYSTEMD_USER_DIR/aria-scheduler.service" ]]; then
        systemctl --user start aria-scheduler.service
        log_info "Started aria-scheduler.service"
    else
        log_info "aria-scheduler.service not installed, skipping start"
    fi

    if [[ -f "$SYSTEMD_USER_DIR/aria-gateway.service" ]]; then
        systemctl --user start aria-gateway.service
        log_info "Started aria-gateway.service"
    else
        log_info "aria-gateway.service not installed, skipping start"
    fi

    if [[ -f "$SYSTEMD_USER_DIR/aria-memory.service" ]]; then
        log_info "aria-memory.service installed but not auto-started (optional first-start path)"
    else
        log_info "aria-memory.service not installed, skipping optional memory start"
    fi

    log_info "Services started"
}

# === Stop services ===
stop_services() {
    log_info "Stopping ARIA services..."

    systemctl --user stop aria-scheduler.service 2>/dev/null || true
    systemctl --user stop aria-gateway.service 2>/dev/null || true
    systemctl --user stop aria-memory.service 2>/dev/null || true

    log_info "Services stopped"
}

# === Show status ===
show_status() {
    echo "=== ARIA Services Status ==="
    systemctl --user status aria-scheduler.service --no-pager || true
    echo ""
    systemctl --user status aria-gateway.service --no-pager || true
    echo ""
    systemctl --user status aria-memory.service --no-pager || true
}

# === Enable services ===
enable_services() {
    log_info "Enabling ARIA services..."

    if [[ -f "$SYSTEMD_USER_DIR/aria-scheduler.service" ]]; then
        systemctl --user enable aria-scheduler.service
        log_info "Enabled aria-scheduler.service"
    else
        log_info "aria-scheduler.service not installed, skipping enable"
    fi

    if [[ -f "$SYSTEMD_USER_DIR/aria-gateway.service" ]]; then
        systemctl --user enable aria-gateway.service
        log_info "Enabled aria-gateway.service"
    else
        log_info "aria-gateway.service not installed, skipping enable"
    fi

    if [[ -f "$SYSTEMD_USER_DIR/aria-memory.service" ]]; then
        log_info "aria-memory.service installed but not auto-enabled by default"
    else
        log_info "aria-memory.service not installed, skipping optional memory enable"
    fi

    log_info "Services enabled"
}

# === Disable services ===
disable_services() {
    log_info "Disabling ARIA services..."

    if [[ -f "$SYSTEMD_USER_DIR/aria-scheduler.service" ]]; then
        systemctl --user disable aria-scheduler.service
        log_info "Disabled aria-scheduler.service"
    else
        log_info "aria-scheduler.service not installed, skipping disable"
    fi

    if [[ -f "$SYSTEMD_USER_DIR/aria-gateway.service" ]]; then
        systemctl --user disable aria-gateway.service
        log_info "Disabled aria-gateway.service"
    else
        log_info "aria-gateway.service not installed, skipping disable"
    fi

    if [[ -f "$SYSTEMD_USER_DIR/aria-memory.service" ]]; then
        if systemctl --user disable aria-memory.service >/dev/null 2>&1; then
            log_info "Disabled aria-memory.service"
        else
            log_info "aria-memory.service disable skipped (not enabled or unavailable)"
        fi
    else
        log_info "aria-memory.service not installed, skipping disable"
    fi

    log_info "Services disabled"
}

reload_daemon() {
    log_info "Reloading systemd user daemon..."
    systemctl --user daemon-reload
    log_info "Systemd daemon reloaded"
}

# === Main ===
main() {
    local action="${1:-install}"

    case "$action" in
        install)
            install_units
            ;;
        uninstall)
            uninstall_units
            ;;
        reload)
            reload_daemon
            ;;
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        status)
            show_status
            ;;
        enable)
            enable_services
            ;;
        disable)
            disable_services
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            log_error "Unknown action: $action"
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
