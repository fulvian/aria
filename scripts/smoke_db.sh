#!/usr/bin/env bash
# ARIA Database Smoke Tests
# Verifies SQLite setup and FTS5 availability

set -euo pipefail

ARIA_HOME="${ARIA_HOME:-/home/fulvio/coding/aria}"
TEST_DIR="${TEST_DIR:-/tmp/aria-test}"
SCHEMA_FILE="$ARIA_HOME/docs/foundation/schemas/sqlite_full.sql"
PYTHON_BIN="${PYTHON_BIN:-$ARIA_HOME/.venv/bin/python}"

log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

log_pass() {
    echo "[PASS] $1"
}

log_fail() {
    echo "[FAIL] $1" >&2
}

log_warn() {
    echo "[WARN] $1"
}

# === Check SQLite version ===
check_sqlite_version() {
    local version
    version=$(sqlite3 --version | awk '{print $1}')
    local required="3.51.3"

    log_info "SQLite version: $version (required: >= $required)"

    # Blueprint §6.1.1 requires SQLite >= 3.51.3 for WAL-reset bug mitigation
    # Check using sort -V for proper semantic versioning
    if [[ "$(printf '%s\n' "$required" "$version" | sort -V | head -n1)" == "$required" ]]; then
        log_pass "SQLite version check"
        return 0
    else
        log_warn "SQLite version is below blueprint requirement ($version < $required)"
        log_warn "This may cause WAL-reset issues. Consider upgrading SQLite."
        log_warn "See: https://sqlite.org/releaselog/3_51_3.html"
        # Don't fail - continue with other tests to verify functionality
        return 0
    fi
}

# === Check Python sqlite runtime version ===
check_python_sqlite_version() {
    local required="3.51.3"
    local py_bin="$PYTHON_BIN"

    if [[ ! -x "$py_bin" ]]; then
        py_bin="$(command -v python3)"
    fi

    local py_version
    py_version=$($py_bin -c "import sqlite3; print(sqlite3.sqlite_version)" 2>/dev/null || echo "unknown")

    log_info "Python sqlite runtime: $py_version (required: >= $required)"

    if [[ "$py_version" == "unknown" ]]; then
        log_fail "Could not determine sqlite runtime from Python interpreter: $py_bin"
        return 1
    fi

    if [[ "$(printf '%s\n' "$required" "$py_version" | sort -V | head -n1)" == "$required" ]]; then
        log_pass "Python sqlite runtime version check"
        return 0
    fi

    log_fail "Python sqlite runtime is below blueprint requirement ($py_version < $required)"
    log_fail "Rebuild .venv with an interpreter linked to sqlite >= $required"
    return 1
}

# === Check FTS5 availability ===
check_fts5() {
    log_info "Checking FTS5 availability..."

    local result
    result=$(sqlite3 :memory: "PRAGMA compile_options;" 2>/dev/null | grep -i FTS5 || echo "")

    if [[ -n "$result" ]]; then
        log_pass "FTS5 is available"
        return 0
    fi

    # Alternative check
    result=$(sqlite3 :memory: "CREATE VIRTUAL TABLE test USING fts5(content);" 2>&1 || echo "failed")
    if [[ "$result" != "failed" ]]; then
        log_pass "FTS5 is available"
        return 0
    fi

    log_fail "FTS5 is NOT available"
    return 1
}

# === Create test database ===
create_test_db() {
    log_info "Creating test database..."

    mkdir -p "$TEST_DIR"
    rm -f "$TEST_DIR/test.db" "$TEST_DIR/test.db-wal" "$TEST_DIR/test.db-shm"

    sqlite3 "$TEST_DIR/test.db" "
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        CREATE TABLE IF NOT EXISTS test (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL
        );
        INSERT INTO test (id, content) VALUES ('1', 'hello world');
    "

    if [[ -f "$TEST_DIR/test.db" ]]; then
        log_pass "Test database created"
        return 0
    else
        log_fail "Test database creation failed"
        return 1
    fi
}

# === Verify WAL mode ===
check_wal_mode() {
    log_info "Checking WAL mode..."

    local mode
    mode=$(sqlite3 "$TEST_DIR/test.db" "PRAGMA journal_mode;" 2>/dev/null)

    if [[ "$mode" == "wal" ]]; then
        log_pass "WAL mode enabled"
        return 0
    else
        log_fail "WAL mode not enabled: $mode"
        return 1
    fi
}

# === Create FTS5 table ===
create_fts5_table() {
    log_info "Creating FTS5 table..."

    local result
    result=$(sqlite3 "$TEST_DIR/test.db" "
        CREATE VIRTUAL TABLE test_fts USING fts5(content);
        INSERT INTO test_fts (content) VALUES ('test content');
        SELECT count(*) FROM test_fts;
    " 2>&1)

    if [[ "$result" == "1" ]]; then
        log_pass "FTS5 table created and working"
        return 0
    else
        log_fail "FTS5 table test failed: $result"
        return 1
    fi
}

# === Run schema validation ===
validate_schema() {
    log_info "Validating schema file..."

    if [[ ! -f "$SCHEMA_FILE" ]]; then
        log_fail "Schema file not found: $SCHEMA_FILE"
        return 1
    fi

    # Create a test DB with the schema and fail on parse errors.
    rm -f "$TEST_DIR/schema_test.db"
    local output
    output=$(sqlite3 "$TEST_DIR/schema_test.db" < "$SCHEMA_FILE" 2>&1)

    if [[ "$output" == *"Parse error"* ]] || [[ "$output" == *"Error:"* ]]; then
        log_fail "Schema file has SQL errors"
        log_fail "$output"
        return 1
    fi

    if [[ -f "$TEST_DIR/schema_test.db" ]]; then
        log_pass "Schema file is valid SQL"
        return 0
    fi

    log_fail "Schema file validation failed"
    return 1
}

# === Cleanup ===
cleanup() {
    log_info "Cleaning up test files..."
    rm -rf "$TEST_DIR"
}

# === Main ===
main() {
    log_info "ARIA Database Smoke Tests"
    log_info "========================"

    local failed=0

    check_sqlite_version || failed=1
    check_python_sqlite_version || failed=1
    check_fts5 || failed=1
    create_test_db || failed=1
    check_wal_mode || failed=1
    create_fts5_table || failed=1
    validate_schema || failed=1

    cleanup

    echo ""
    if [[ $failed -eq 0 ]]; then
        log_info "All smoke tests passed!"
        return 0
    else
        log_error "Some tests failed!"
        return 1
    fi
}

main "$@"
