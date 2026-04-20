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

    # Copy unit files
    cp "$ARIA_HOME/systemd/aria-scheduler.service" "$SYSTEMD_USER_DIR/"
    cp "$ARIA_HOME/systemd/aria-gateway.service" "$SYSTEMD_USER_DIR/"

    # Reload systemd daemon
    systemctl --user daemon-reload

    log_info "Unit files installed to $SYSTEMD_USER_DIR"
}

# === Uninstall unit files ===
uninstall_units() {
    log_info "Uninstalling systemd unit files..."

    rm -f "$SYSTEMD_USER_DIR/aria-scheduler.service"
    rm -f "$SYSTEMD_USER_DIR/aria-gateway.service"

    systemctl --user daemon-reload

    log_info "Unit files removed"
}

# === Start services ===
start_services() {
    log_info "Starting ARIA services..."
    systemctl --user start aria-scheduler.service
    systemctl --user start aria-gateway.service
    log_info "Services started"
}

# === Stop services ===
stop_services() {
    log_info "Stopping ARIA services..."
    systemctl --user stop aria-scheduler.service
    systemctl --user stop aria-gateway.service
    log_info "Services stopped"
}

# === Show status ===
show_status() {
    echo "=== ARIA Services Status ==="
    systemctl --user status aria-scheduler.service --no-pager || true
    echo ""
    systemctl --user status aria-gateway.service --no-pager || true
}

# === Enable services ===
enable_services() {
    log_info "Enabling ARIA services..."
    systemctl --user enable aria-scheduler.service
    systemctl --user enable aria-gateway.service
    log_info "Services enabled"
}

# === Disable services ===
disable_services() {
    log_info "Disabling ARIA services..."
    systemctl --user disable aria-scheduler.service
    systemctl --user disable aria-gateway.service
    log_info "Services disabled"
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
