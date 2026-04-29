#!/usr/bin/env bash
# Rollback Drill — Ritorno a Baseline MCP Profile in <5 minuti
#
# Questo script ripristina il profilo baseline di ARIA MCP, ritornando
# allo stato last-known-good. Operazioni:
#   1. Backup dello stato corrente (mcp.json, agent files modificati)
#   2. Ripristino dei file baseline da git
#   3. Verifica integrita' dei file ripristinati
#   4. Report summary
#
# Usage:
#   ./scripts/rollback_baseline.sh                    # rollback completo
#   ./scripts/rollback_baseline.sh --dry-run           # solo simulazione
#   ./scripts/rollback_baseline.sh --list-backups      # elenca backup disponibili
#   ./scripts/rollback_baseline.sh --restore BACKUP_TIMESTAMP  # ripristino specifico
#
# Vincoli:
#   - NON tocca .aria/runtime/ (credenziali, stato rotator)
#   - NON tocca .aria/kilo-home/ (caching, runtime rigenerabile)
#   - Richiede git per ripristinare i file baseline
#   - Tempo stimato: < 2 minuti (full) / < 30 secondi (dry-run)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARIA_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"

BACKUP_DIR="$ARIA_HOME/.aria/runtime/rollback_backups"
BASELINE_BRANCH="${BASELINE_BRANCH:-main}"

# ─── File da backup/ripristino ───────────────────────────────────────────────
# Solo file di configurazione, nessun dato runtime

BASELINE_FILES=(
    ".aria/kilocode/mcp.json"
    ".aria/kilocode/agents/search-agent.md"
    ".aria/kilocode/agents/aria-conductor.md"
    ".aria/kilocode/agents/productivity-agent.md"
    ".aria/kilocode/agents/workspace-agent.md"
)

MCP_JSON="$ARIA_HOME/.aria/kilocode/mcp.json"

# ─── Colors ──────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ─── Functions ───────────────────────────────────────────────────────────────

list_backups() {
    local backup_count=0
    log_info "Backup disponibili in: $BACKUP_DIR"
    echo ""
    for dir in "$BACKUP_DIR"/*/; do
        if [ -d "$dir" ]; then
            ts=$(basename "$dir")
            local date_part="${ts:0:8}"
            local time_part="${ts:9:4}"
            log_info "  $ts  (${date_part:0:4}-${date_part:4:2}-${date_part:6:2} ${time_part:0:2}:${time_part:2:2})"
            [ -f "$dir/rollback_manifest.txt" ] && head -1 "$dir/rollback_manifest.txt" | while IFS= read -r line; do
                echo "    $line"
            done
            backup_count=$((backup_count + 1))
        fi
    done
    if [ "$backup_count" -eq 0 ]; then
        log_warn "Nessun backup trovato."
    fi
    echo ""
    log_info "Totale backup: $backup_count"
}

do_backup() {
    local ts
    ts=$(date +%Y%m%d_%H%M%S)
    local backup_path="$BACKUP_DIR/$ts"

    mkdir -p "$backup_path"
    log_info "Backup in corso → $backup_path"

    for relpath in "${BASELINE_FILES[@]}"; do
        local src="$ARIA_HOME/$relpath"
        local dst="$backup_path/$(dirname "$relpath")"
        if [ -f "$src" ]; then
            mkdir -p "$dst"
            cp "$src" "$dst/$(basename "$relpath")"
            log_ok "  Backup: $relpath"
        else
            log_warn "  Skipped (not found): $relpath"
        fi
    done

    # Manifest
    {
        echo "Rollback backup creato il $(date)"
        echo "Baseline branch: $BASELINE_BRANCH"
        echo "File inclusi: ${#BASELINE_FILES[@]}"
        echo ""
        git -C "$ARIA_HOME" log --oneline -3
    } > "$backup_path/rollback_manifest.txt"

    log_ok "Backup completato: $ts"
    echo "$ts"
}

do_restore_from_git() {
    local dry_run="${1:-false}"

    log_info "Ripristino baseline da git (branch: $BASELINE_BRANCH)..."
    echo ""

    if [ "$dry_run" = "true" ]; then
        log_info "[DRY RUN] Operazioni simulate:"
    fi

    local restored=0 skipped=0 failed=0

    for relpath in "${BASELINE_FILES[@]}"; do
        local fullpath="$ARIA_HOME/$relpath"

        if [ "$dry_run" = "true" ]; then
            echo "  [DRY RUN] git checkout $BASELINE_BRANCH -- $relpath"
            restored=$((restored + 1))
            continue
        fi

        if git -C "$ARIA_HOME" show "$BASELINE_BRANCH:$relpath" >/dev/null 2>&1; then
            git -C "$ARIA_HOME" checkout "$BASELINE_BRANCH" -- "$relpath" 2>/dev/null
            log_ok "  Ripristinato: $relpath"
            restored=$((restored + 1))
        else
            log_warn "  Non trovato in $BASELINE_BRANCH: $relpath"
            skipped=$((skipped + 1))
        fi
    done

    echo ""
    if [ "$dry_run" = "false" ]; then
        log_info "Ripristino completato: $restored ripristinati, $skipped saltati, $failed falliti"
    fi
}

verify_integrity() {
    log_info "Verifica integrità..."
    local errors=0

    # Verifica che mcp.json sia JSON valido
    if [ -f "$MCP_JSON" ]; then
        if python3 -c "import json; json.load(open('$MCP_JSON'))" 2>/dev/null; then
            log_ok "  mcp.json: JSON valido"
        else
            log_error "  mcp.json: JSON INVALIDO!"
            errors=$((errors + 1))
        fi
    else
        log_error "  mcp.json: FILE MANCANTE!"
        errors=$((errors + 1))
    fi

    # Verifica che gli agent file abbiano YAML frontmatter valido
    for relpath in "${BASELINE_FILES[@]:1}"; do
        local fullpath="$ARIA_HOME/$relpath"
        if [ -f "$fullpath" ]; then
            if python3 -c "
import yaml
with open('$fullpath') as f:
    content = f.read()
parts = content.split('---', 2)
assert len(parts) >= 3, f'No YAML frontmatter in $relpath'
yaml.safe_load(parts[1])
print(f'  $relpath: YAML valido')
" 2>/dev/null; then
                :
            else
                log_error "  $relpath: YAML INVALIDO!"
                errors=$((errors + 1))
            fi
        else
            log_warn "  $relpath: file non presente (ok se non ancora creato su $BASELINE_BRANCH)"
        fi
    done

    echo ""
    if [ "$errors" -eq 0 ]; then
        log_info "Verifica integrità: ✅ PASS (0 errori)"
    else
        log_error "Verifica integrità: ❌ $errors errore(i)"
        return 1
    fi
}

do_restore_specific_backup() {
    local ts="$1"
    local backup_path="$BACKUP_DIR/$ts"

    if [ ! -d "$backup_path" ]; then
        log_error "Backup non trovato: $ts"
        exit 1
    fi

    log_info "Ripristino da backup: $ts"
    echo ""

    local restored=0 skipped=0

    for relpath in "${BASELINE_FILES[@]}"; do
        local src="$backup_path/$(dirname "$relpath")/$(basename "$relpath")"
        local dst="$ARIA_HOME/$relpath"
        if [ -f "$src" ]; then
            mkdir -p "$(dirname "$dst")"
            cp "$src" "$dst"
            log_ok "  Ripristinato: $relpath (da backup)"
            restored=$((restored + 1))
        else
            log_warn "  Non trovato in backup: $relpath"
            skipped=$((skipped + 1))
        fi
    done

    echo ""
    log_info "Ripristino completato: $restored ripristinati, $skipped saltati"
}


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ARIA Rollback Drill"
echo "  Baseline branch: $BASELINE_BRANCH"
echo "  Data: $(date)"
echo "═══════════════════════════════════════════════════"
echo ""

# Parse args
case "${1:-}" in
    --list-backups|-l)
        list_backups
        exit 0
        ;;
    --dry-run|-n)
        do_backup
        do_restore_from_git "true"
        exit 0
        ;;
    --restore)
        if [ -z "${2:-}" ]; then
            log_error "Specificare timestamp backup: $0 --restore YYYYMMDD_HHMMSS"
            list_backups
            exit 1
        fi
        do_restore_specific_backup "$2"
        verify_integrity
        exit 0
        ;;
    --help|-h)
        echo "Usage:"
        echo "  $0                          Rollback completo (backup + restore + verify)"
        echo "  $0 --dry-run                Simulazione (senza modifiche)"
        echo "  $0 --list-backups           Elenca backup disponibili"
        echo "  $0 --restore TIMESTAMP      Ripristino da backup specifico"
        echo "  $0 --help                   Questo messaggio"
        exit 0
        ;;
esac

# ─── Full rollback ───────────────────────────────────────────────────────────

log_info "FASE 1/4: Backup dello stato corrente..."
backup_ts=$(do_backup)
echo ""

log_info "FASE 2/4: Ripristino baseline da git..."
do_restore_from_git
echo ""

log_info "FASE 3/4: Verifica integrità..."
verify_integrity || {
    log_warn "Verifica fallita. Ripristino backup precedente..."
    do_restore_specific_backup "$backup_ts"
    exit 1
}
echo ""

log_info "FASE 4/4: Report finale"
echo ""
echo "  Backup creato:    $BACKUP_DIR/$backup_ts/"
echo "  Baseline branch:  $BASELINE_BRANCH"
echo "  Stato:            ✅ COMPLETATO"
echo "  Tempo stimato:    < 2 minuti"
echo ""
log_info "Rollback completato con successo."

# Verifica che git status sia pulito per i file ripristinati
if git -C "$ARIA_HOME" status --short "${BASELINE_FILES[@]}" | grep -q .; then
    echo ""
    log_warn "ATTENZIONE: I seguenti file differiscono dal branch $BASELINE_BRANCH:"
    git -C "$ARIA_HOME" status --short "${BASELINE_FILES[@]}"
    echo ""
    log_info "Per confermare: git checkout $BASELINE_BRANCH -- ${BASELINE_FILES[*]}"
fi
