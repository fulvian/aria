#!/usr/bin/env bash
# ARIA Backup/Restore Test Script
# Creates a synthetic test DB, backs it up, restores, and validates.
# Per blueprint §14.4 and sprint plan W1.4.I.

set -euo pipefail

ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/.aria-backups}"
TEST_DIR=$(mktemp -d)
EXIT_CODE=0

cleanup() {
    rm -rf "$TEST_DIR"
}
trap cleanup EXIT

log_info() {
    echo "[INFO] $1"
}

log_pass() {
    echo "[PASS] $1"
}

log_fail() {
    echo "[FAIL] $1"
    EXIT_CODE=1
}

log_section() {
    echo ""
    echo "=== $1 ==="
}

# === Test functions ===

test_backup_restore() {
    log_section "Backup/Restore Test"

    # Create test DB with synthetic data
    local test_db="$TEST_DIR/test_episodic.db"
    log_info "Creating test DB at $test_db"

    sqlite3 "$test_db" "
        CREATE TABLE episodes (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            ts INTEGER,
            actor TEXT,
            content TEXT
        );
        INSERT INTO episodes VALUES ('test-1', 'session-1', $(date +%s), 'user_input', 'test content');
        INSERT INTO episodes VALUES ('test-2', 'session-2', $(date +%s), 'tool_output', 'tool result');
    "

    # Create a mock backup
    log_info "Creating mock backup..."
    mkdir -p "$ARIA_HOME/.aria/runtime/memory"
    cp "$test_db" "$ARIA_HOME/.aria/runtime/memory/episodic.db"

    # Run backup script
    log_info "Running backup.sh..."
    if ! "$ARIA_HOME/scripts/backup.sh" backup; then
        log_fail "backup.sh failed"
        return 1
    fi

    # Find the backup file
    local backup_file
    backup_file=$(ls -t "$BACKUP_DIR"/aria-backup-*.tar.age 2>/dev/null | head -n1)
    if [[ -z "$backup_file" ]]; then
        log_fail "No backup file created"
        return 1
    fi
    log_info "Backup file: $backup_file"

    # Clean up original
    rm -f "$ARIA_HOME/.aria/runtime/memory/episodic.db"

    # Restore
    log_info "Running restore.sh..."
    if ! "$ARIA_HOME/scripts/restore.sh" "$backup_file" <<< "y"; then
        log_fail "restore.sh failed"
        return 1
    fi

    # Verify restored DB
    if [[ ! -f "$ARIA_HOME/.aria/runtime/memory/episodic.db" ]]; then
        log_fail "Restored DB not found"
        return 1
    fi

    local count
    count=$(sqlite3 "$ARIA_HOME/.aria/runtime/memory/episodic.db" "SELECT COUNT(*) FROM episodes")
    if [[ "$count" -ne 2 ]]; then
        log_fail "Expected 2 records, got $count"
        return 1
    fi

    log_pass "Backup/restore test passed"
    return 0
}

# === Main ===
main() {
    echo "ARIA Backup/Restore Test"
    echo "========================"

    # Check prerequisites
    if ! command -v sqlite3 &>/dev/null; then
        echo "ERROR: sqlite3 not found" >&2
        exit 1
    fi

    if [[ ! -f "$ARIA_HOME/scripts/backup.sh" ]]; then
        echo "ERROR: backup.sh not found at $ARIA_HOME/scripts/backup.sh" >&2
        exit 1
    fi

    if [[ ! -f "$ARIA_HOME/scripts/restore.sh" ]]; then
        echo "ERROR: restore.sh not found at $ARIA_HOME/scripts/restore.sh" >&2
        exit 1
    fi

    # Check for age CLI
    if ! command -v age &>/dev/null; then
        echo "ERROR: age CLI not found" >&2
        exit 1
    fi

    # Run tests
    test_backup_restore

    # Cleanup test backup files
    rm -f "$BACKUP_DIR"/aria-backup-*.tar.age

    echo ""
    echo "========================"
    if [[ "$EXIT_CODE" -eq 0 ]]; then
        echo "All tests PASSED"
    else
        echo "Some tests FAILED"
    fi

    exit "$EXIT_CODE"
}

main "$@"
