#!/usr/bin/env bash
# ARIA Backup Script
# Creates encrypted backups of runtime data

set -euo pipefail

ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/.aria-backups}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/aria-backup-$TIMESTAMP.tar.age"
BACKUP_PUB_FILE="${ARIA_BACKUP_PUB_FILE:-$ARIA_HOME/.age-backup.pub}"
LEGACY_BACKUP_PUB_FILE="$ARIA_HOME/.age.pub"
BACKUP_PRIVATE_KEY="${ARIA_BACKUP_PRIVATE_KEY:-$HOME/.aria-backup-keys/backup_key.txt}"
LEGACY_PRIVATE_KEY="$HOME/.config/sops/age/keys.txt"

log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

# === Create backup ===
create_backup() {
    log_info "Creating backup..."

    # Create backup directory if needed
    mkdir -p "$BACKUP_DIR"

    # Flush WAL files before archiving for consistency
    local db_paths=(
        "$ARIA_HOME/.aria/runtime/memory/episodic.db"
        "$ARIA_HOME/.aria/runtime/scheduler/scheduler.db"
        "$ARIA_HOME/.aria/runtime/gateway/sessions.db"
    )
    for db_path in "${db_paths[@]}"; do
        if [[ -f "$db_path" ]]; then
            sqlite3 "$db_path" "PRAGMA wal_checkpoint(TRUNCATE);" >/dev/null || true
        fi
    done

    # Check for age public key file
    local pub_file="$BACKUP_PUB_FILE"
    if [[ ! -f "$pub_file" ]]; then
        pub_file="$LEGACY_BACKUP_PUB_FILE"
    fi
    if [[ ! -f "$pub_file" ]]; then
        log_error "Missing public key file: $pub_file"
        log_error "Cannot encrypt backup without public key"
        return 1
    fi

    # Get public key
    local pub_key
    pub_key=$(cat "$pub_file")

    # Create archive and encrypt
    tar -czf - \
        -C "$ARIA_HOME" \
        .aria/runtime \
        .aria/credentials \
        --exclude='.aria/runtime/tmp/*' \
        --exclude='*.log' \
        | age -r "$pub_key" -o "$BACKUP_FILE"

    log_info "Backup created: $BACKUP_FILE"

    # Cleanup old backups (keep 30 days)
    find "$BACKUP_DIR" -name "aria-backup-*.tar.age" -mtime +30 -type f -delete
    log_info "Old backups cleaned"
}

# === Restore from backup ===
restore_backup() {
    local backup_file="$1"

    if [[ ! -f "$backup_file" ]]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi

    log_info "Restoring from: $backup_file"

    # Check for age private key
    local key_file="$BACKUP_PRIVATE_KEY"
    if [[ ! -f "$key_file" ]]; then
        key_file="$LEGACY_PRIVATE_KEY"
    fi
    if [[ ! -f "$key_file" ]]; then
        log_error "Missing private key: $key_file"
        return 1
    fi

    # Decrypt and extract
    age -d -i "$key_file" "$backup_file" | tar -xzf - -C "$ARIA_HOME"

    log_info "Restore complete"
}

# === List backups ===
list_backups() {
    echo "Available backups:"
    ls -la "$BACKUP_DIR"/aria-backup-*.tar.age 2>/dev/null || echo "No backups found"
}

# === Main ===
main() {
    local action="${1:-backup}"

    case "$action" in
        backup)
            create_backup
            ;;
        restore)
            restore_backup "${2:-}"
            ;;
        list)
            list_backups
            ;;
        *)
            echo "Usage: $0 {backup|restore <file>|list}"
            exit 1
            ;;
    esac
}

main "$@"
