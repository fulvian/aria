#!/usr/bin/env bash
# Scientific Papers MCP Wrapper — keyless (Europe PMC, arXiv, OpenAlex, etc.)
#
# ⚠️  VERSIONE CON PATCH AUTOMATICA ⚠️
# Il pacchetto npm @futurelab-studio/latest-science-mcp v0.1.40 ha 3 bug critici
# nella costruzione query per arXiv ed EuropePMC. Questo wrapper applica le
# patch automaticamente a qualsiasi cache entry npx prima di avviare il server.
#
# Bug risolti:
#   BUG 1: arXiv driver — query wrappata in doppi apici (frase esatta)
#   BUG 2: EuropePMC driver — stessa cosa + sort=relevance rompe API
#   BUG 3: search-papers — nessuna pre-elaborazione query centralizzata
#
# Per Context7 /benedict2310/scientific-papers-mcp:
# v0.1.40 — 6 sources: arXiv, OpenAlex, PMC, Europe PMC, bioRxiv/medRxiv, CORE
# Tools: search_papers, fetch_content, fetch_latest, list_categories, fetch_top_cited
# Europe PMC: https://www.ebi.ac.uk/europepmc/webservices/rest (10 req/min, no key)
# No API keys required (all sources public)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARIA_HOME="${ARIA_HOME:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

# ═══════════════════════════════════════════════════════════════════
# CONFIG — Version pin + checksum manifest (vedi MANIFEST.md)
# ═══════════════════════════════════════════════════════════════════
SCIENTIFIC_PAPERS_PINNED_VERSION="0.1.40"

# SHA256 checksum dei file originali (da npm pack @0.1.40)
declare -A ORIGINAL_CHECKSUMS=(
    ["arxiv-driver.js"]="3145e8c34ff525df0962ac3b20434446fe191b40767d3d61f6b5c031b72b43a9"
    ["europepmc-driver.js"]="7e92d06a28a9864931119f530e8c256a62e55c0bc5d7b3de73dab0ded58638db"
    ["search-papers.js"]="36f3582d3fbde4a9d40c831e8b78256798557e3bca70d8ff32c3f044c2fa97d7"
)

# SHA256 checksum dei file patchati (verificati in docs/patches/)
declare -A PATCHED_CHECKSUMS=(
    ["arxiv-driver.js"]="dc753890acd9e4d7a546f907a6979b07531eb1b9812c549416241b221d79aae6"
    ["europepmc-driver.js"]="27db225741f7c16b90d0286c721803abf811147ecc61aa64e19c17ed64def831"
    ["search-papers.js"]="aad32f63fcb3bf0519b4a124c8f161b5f087ed35ee4ebaa01395b565d1eab42b"
)

REQUIRED_PATCH_FILES=(
    "arxiv-driver.js"
    "europepmc-driver.js"
    "search-papers.js"
)

# ═══════════════════════════════════════════════════════════════════
# Patch seed validation
# ═══════════════════════════════════════════════════════════════════
PATCH_SEED="$ARIA_HOME/docs/patches/scientific-papers-mcp"
PATCH_SEED_VALID=1  # 1=OK, 0=failure

if [ ! -d "$PATCH_SEED" ]; then
    echo "ERROR: Patch seed directory missing: $PATCH_SEED" >&2
    PATCH_SEED_VALID=0
else
    for f in "${REQUIRED_PATCH_FILES[@]}"; do
        expected="${PATCHED_CHECKSUMS[$f]}"
        actual=$(sha256sum "$PATCH_SEED/$f" 2>/dev/null | cut -d' ' -f1 || echo "")
        if [ "$actual" != "$expected" ]; then
            echo "ERROR: Patch seed file checksum mismatch: $PATCH_SEED/$f" >&2
            echo "ERROR:   expected: $expected" >&2
            echo "ERROR:   actual:   ${actual:-MISSING}" >&2
            PATCH_SEED_VALID=0
        fi
    done
fi

if [ "$PATCH_SEED_VALID" -eq 0 ]; then
    echo "" >&2
    echo "FATAL: Il seed patching e invalido o incompleto. Il server restituira risultati vuoti." >&2
    echo "FATAL:   - Ripristina da git: git checkout -- docs/patches/scientific-papers-mcp/" >&2
    echo "FATAL:   - O aggiorna MANIFEST.md se il pacchetto npm e cambiato." >&2
    echo "FATAL: Per disabilitare il controllo: SCIENTIFIC_PAPERS_SKIP_PATCH=1" >&2
    if [ "${SCIENTIFIC_PAPERS_SKIP_PATCH:-0}" != "1" ]; then
        exit 1
    fi
fi

# ═══════════════════════════════════════════════════════════════════
# Apply patches to npx cache entries
# ═══════════════════════════════════════════════════════════════════
NPX_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/npm/_npx"
if [ ! -d "$NPX_CACHE" ]; then
    NPX_CACHE="$HOME/.npm/_npx"
fi

if [ "$PATCH_SEED_VALID" -eq 1 ] && [ -d "$NPX_CACHE" ]; then
    for entry in "$NPX_CACHE"/*/; do
        pkg="$entry/node_modules/@futurelab-studio/latest-science-mcp"
        if [ ! -f "$pkg/dist/drivers/europepmc-driver.js" ]; then
            continue
        fi

        # Check if already patched (look for our fix markers)
        if grep -q 'FIXED v2' "$pkg/dist/drivers/europepmc-driver.js" 2>/dev/null; then
            continue
        fi

        # ─── Verify original files BEFORE patching ───
        ORIGINAL_OK=1
        for f in "${REQUIRED_PATCH_FILES[@]}"; do
            expected="${ORIGINAL_CHECKSUMS[$f]}"
            # Map patched file name to original path in npm package
            orig_path="$pkg/dist/drivers/$f"
            [ "$f" = "search-papers.js" ] && orig_path="$pkg/dist/tools/$f"
            actual=$(sha256sum "$orig_path" 2>/dev/null | cut -d' ' -f1 || echo "")
            if [ "$actual" != "$expected" ]; then
                echo "WARN: Original file checksum mismatch: $f" >&2
                echo "WARN:   expected: $expected  (npm v$SCIENTIFIC_PAPERS_PINNED_VERSION)" >&2
                echo "WARN:   actual:   ${actual:-MISSING}" >&2
                echo "WARN:   Il pacchetto npm potrebbe essere stato aggiornato. Saltato patching." >&2
                ORIGINAL_OK=0
                break
            fi
        done

        if [ "$ORIGINAL_OK" -eq 0 ]; then
            continue
        fi

        # ─── Apply patches ───
        cp "$PATCH_SEED/arxiv-driver.js" "$pkg/dist/drivers/arxiv-driver.js"
        cp "$PATCH_SEED/europepmc-driver.js" "$pkg/dist/drivers/europepmc-driver.js"
        cp "$PATCH_SEED/search-papers.js" "$pkg/dist/tools/search-papers.js"

        # ─── Verify patched files ───
        PATCH_OK=1
        for f in "${REQUIRED_PATCH_FILES[@]}"; do
            expected="${PATCHED_CHECKSUMS[$f]}"
            patched_path="$pkg/dist/drivers/$f"
            [ "$f" = "search-papers.js" ] && patched_path="$pkg/dist/tools/$f"
            actual=$(sha256sum "$patched_path" 2>/dev/null | cut -d' ' -f1 || echo "")
            if [ "$actual" != "$expected" ]; then
                echo "ERROR: Patch verification failed: $f" >&2
                echo "ERROR:   expected: $expected" >&2
                echo "ERROR:   actual:   ${actual:-MISSING}" >&2
                PATCH_OK=0
            fi
        done

        if [ "$PATCH_OK" -eq 1 ]; then
            echo "INFO: Patched $entry (v$SCIENTIFIC_PAPERS_PINNED_VERSION)" >&2
        else
            echo "FATAL: Patching $entry fallito — integrita non verificata." >&2
            exit 1
        fi
    done
fi

# ═══ Avvia MCP server via npx (versione pinata) ═══
exec uv run "$(dirname "$0")/../mcp-stdio-filter.py" -- npx -y "@futurelab-studio/latest-science-mcp@${SCIENTIFIC_PAPERS_PINNED_VERSION}"
