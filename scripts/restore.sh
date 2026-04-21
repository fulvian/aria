#!/usr/bin/env bash
# ARIA Restore Script
# Restores ARIA from an encrypted backup

set -euo pipefail

ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/.aria-backups}"
BACKUP_PRIVATE_KEY="${ARIA_BACKUP_PRIVATE_KEY:-$HOME/.aria-backup-keys/backup_key.txt}"
LEGACY_PRIVATE_KEY="$HOME/.config/sops/age/keys.txt"

log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

show_usage() {
    cat <<'EOF'
ARIA Restore Script

Usage: ./scripts/restore.sh <backup_file>

Examples:
  ./scripts/restore.sh ~/.aria-backups/aria-backup-20260503-120000.tar.age
  ./scripts/restore.sh last  # Restore most recent backup

EOF
}

restore_backup() {
    local backup_file="$1"

    # Handle "last" argument
    if [[ "$backup_file" == "last" ]]; then
        backup_file=$(ls -t "$BACKUP_DIR"/aria-backup-*.tar.age 2>/dev/null | head -n1)
        if [[ -z "$backup_file" ]]; then
            log_error "No backups found"
            exit 1
        fi
        log_info "Using most recent backup: $backup_file"
    fi

    if [[ ! -f "$backup_file" ]]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi

    log_info "Restoring from: $backup_file"

    # Check for age private key
    local key_file="$BACKUP_PRIVATE_KEY"
    if [[ ! -f "$key_file" ]]; then
        key_file="$LEGACY_PRIVATE_KEY"
    fi
    if [[ ! -f "$key_file" ]]; then
        log_error "Missing private key: $key_file"
        log_error "Cannot decrypt backup without private key"
        exit 1
    fi

    # Confirm before overwriting
    echo ""
    echo "This will OVERWRITE existing runtime data!"
    echo "Press Ctrl+C to cancel, or Enter to continue..."
    read -r

    # Decrypt and extract
    age -d -i "$key_file" "$backup_file" | tar -xzf - -C "$ARIA_HOME"

    log_info "Restore complete"
    log_info "Restart ARIA services to apply changes"
}

# === Main ===
main() {
    if [[ $# -lt 1 ]]; then
        show_usage
        exit 1
    fi

    restore_backup "$1"
}

main "$@"
