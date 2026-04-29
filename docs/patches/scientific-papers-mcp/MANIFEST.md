# Scientific Papers MCP — Patch Manifest

**Package**: `@futurelab-studio/latest-science-mcp`
**Version pinned**: `0.1.40`
**Last verified**: 2026-04-29

## Purpose

Il pacchetto npm `@futurelab-studio/latest-science-mcp` v0.1.40 ha 3 bug
nella costruzione query per arXiv ed EuropePMC che causano risultati vuoti.
Questo patch set corregge i 3 bug senza modificare il pacchetto upstream.

## Files

| File | Type | SHA256 | Size |
|------|------|--------|------|
| `arxiv-driver.js` | **Patched** | `dc753890acd9e4d7a546f907a6979b07531eb1b9812c549416241b221d79aae6` | 17965 |
| `arxiv-driver.original.js` | Original (npm v0.1.40) | `3145e8c34ff525df0962ac3b20434446fe191b40767d3d61f6b5c031b72b43a9` | 15659 |
| `europepmc-driver.js` | **Patched** | `27db225741f7c16b90d0286c721803abf811147ecc61aa64e19c17ed64def831` | 23248 |
| `europepmc-driver.original.js` | Original (npm v0.1.40) | `7e92d06a28a9864931119f530e8c256a62e55c0bc5d7b3de73dab0ded58638db` | 18537 |
| `search-papers.js` | **Patched** | `aad32f63fcb3bf0519b4a124c8f161b5f087ed35ee4ebaa01395b565d1eab42b` | 3714 |
| `search-papers.original.js` | Original (npm v0.1.40) | `36f3582d3fbde4a9d40c831e8b78256798557e3bca70d8ff32c3f044c2fa97d7` | 3017 |

## Bugs Fixed

| Bug | File | Fix |
|-----|------|-----|
| BUG 1: arXiv driver | `arxiv-driver.js` | `_parseArxivQuery()` con Boolean AND search (non frase esatta) |
| BUG 2: EuropePMC driver | `europepmc-driver.js` | `_parseQuery()` senza sort=relevance + hasFullText !== "N" invece di === "Y" |
| BUG 3: search-papers.js | `search-papers.js` | `preprocessQuery()` centralizzata con strip quote esterne + normalize whitespace |

## Update Procedure

Quando il pacchetto npm viene aggiornato:

1. `npm view @futurelab-studio/latest-science-mcp version` per verificare nuova versione
2. Scaricare i nuovi originali: `npm pack @futurelab-studio/latest-science-mcp@<version>`
3. Estrarre e confrontare i `.original.js` con quelli esistenti per vedere se i bug sono risolti
4. Se i bug sono ancora presenti, aggiornare i file `.js` (patched) con le stesse correzioni
5. Aggiornare checksum in questo file
6. Aggiornare `SCIENTIFIC_PAPERS_PINNED_VERSION` nel wrapper
