# ARIA Standalone Separation Plan v3

**Date:** 2026-03-30  
**Author:** General Manager (revisione su indicazioni utente)  
**Status:** APPROVABILE PER IMPLEMENTAZIONE  
**Objective:** Rendere ARIA pienamente autonoma nel repository corrente, eliminando ogni riferimento operativo a OpenCode dal codice.

---

## 1) Contesto e Decisione Architetturale

### Decisione chiave (vincolo di progetto)
Questo repository è già il repository prodotto di **ARIA**.  
Non è richiesto (né desiderato) mantenere dualità ARIA/OpenCode nel codice, né creare due repository.

### Implicazioni
- **Target unico:** un solo prodotto (`aria`) e un solo entrypoint CLI.
- **No backward compatibility verso opencode nel codice runtime.**
- **OpenCode** deve rimanere solo come attribuzione storica/documentale nei credits ufficiali.

---

## 2) Goal v3 (aggiornato)

1. Rimuovere dal codice sorgente qualunque naming/branding/flow legato a OpenCode.
2. Consolidare struttura e configurazione esclusivamente ARIA.
3. Mantenere solo i crediti in documentazione: “ARIA è basato su OpenCode”.
4. Garantire build/test/release con naming ARIA-only.

---

## 3) Stato attuale (verificato) e gap principali

### 3.1 Branding e naming runtime ancora OpenCode
- `cmd/root.go`: `Use: "opencode"`, help/examples con opencode.
- TUI e dialog mostrano riferimenti OpenCode.
- Icona e tema default orientati OpenCode.

### 3.2 Config e path legacy
- `.opencode.json` presente con sezione `aria`.
- `internal/config/config.go` usa `appName = "opencode"` e path `.opencode`.
- Memory-file guidance e path utente ancora OpenCode-centric.

### 3.3 Struttura package ereditata
- package e commenti ancora in forma mista (origine OpenCode + ARIA).

### 3.4 Documentazione crediti non formalizzata
- manca sezione credits ufficiale coerente e centralizzata.

---

## 4) Strategia v3 (single-product cleanup)

La separazione non è “ARIA vs OpenCode”, ma **“ripulitura definitiva di ARIA”**.

### Principi
1. **Single binary, single brand, single config namespace.**
2. **No runtime alias** verso `opencode` (nessun comando o file compat mantenuto salvo scelta esplicita temporanea di migrazione).
3. **Attribution-only policy**: OpenCode citato esclusivamente in documentazione ufficiale.

---

## 5) Piano di implementazione v3 (fasi)

## Fase V3-0 — Inventory & Freeze
**Obiettivo:** congelare baseline e inventariare tutto ciò che richiama OpenCode.

### Task
1. Mappare stringhe e simboli: `opencode`, `OpenCode`, `.opencode`, `OpenCode.md`, icone dedicate.
2. Catalogare impatto per area: CLI, config, TUI, docs, scripts, CI/release.
3. Definire rename map ufficiale.

### Deliverable
- `docs/plans/aria-opencode-cleanup-inventory.md`

### Exit Criteria
- lista completa e versionata dei riferimenti da rimuovere.

---

## Fase V3-1 — CLI Identity Migration
**Obiettivo:** rendere la CLI esclusivamente ARIA.

### Task
1. Aggiornare root command a `aria`.
2. Rinominare descrizioni, examples, help text e version output branding.
3. Verificare script di avvio e istruzioni quickstart.

### Deliverable
- CLI avviabile come `aria` senza riferimenti OpenCode.

### Exit Criteria
- `go run ./main.go` mostra branding/comando ARIA-only.

---

## Fase V3-2 — Config & Data Path Migration
**Obiettivo:** eliminare namespace e file legacy OpenCode.

### Task
1. Sostituire `.opencode.json` con configurazione ARIA (`aria.json` dove previsto).
2. Aggiornare loader config per path ARIA (`~/.config/aria`, `~/.aria` / data dir ufficiale deciso).
3. Rimuovere campi legacy OpenCode dal modello config.
4. Implementare eventuale migrazione one-shot (best effort) da file legacy, senza mantenerne dipendenza runtime.

### Deliverable
- stack configurazione ARIA-only.

### Exit Criteria
- ARIA funziona in clean environment senza alcun file/path OpenCode.

---

## Fase V3-3 — TUI/UX Brand Purge
**Obiettivo:** rimuovere completamente il brand OpenCode dalla UX.

### Task
1. Sostituire logo/icona/testi OpenCode con artefatti ARIA.
2. Aggiornare schermate init, messaggi guidati e memory file naming.
3. Impostare tema default ARIA (non opencode).
4. Inserire splash screen ARIA definitivo (ASCII/lipgloss).

### Deliverable
- interfaccia ARIA coerente e autonoma.

### Exit Criteria
- nessuna stringa OpenCode in percorsi UI ARIA.

---

## Fase V3-4 — Codebase Cleanup (naming, package comments, costanti)
**Obiettivo:** eliminare residui semantici nel codice.

### Task
1. Rinominare costanti, commenti, docstring, variabili e messaggi di log legacy.
2. Allineare naming tecnico a dominio ARIA.
3. Ripulire file/dead code introdotto solo per compatibilità OpenCode.

### Deliverable
- codice sorgente senza riferimenti OpenCode (salvo credits docs).

### Exit Criteria
- ricerca full-repo non trova riferimenti OpenCode nel codice runtime.

---

## Fase V3-5 — Documentation & Credits Policy
**Obiettivo:** mantenere attribuzione corretta senza contaminare il runtime.

### Task
1. Aggiungere sezione Credits nella documentazione ufficiale:
   - “ARIA è basato su OpenCode”
   - eventuale link repository e licenza di riferimento.
2. Aggiornare README, docs introduttivi e changelog.
3. Definire policy: OpenCode ammesso solo in `docs/credits|acknowledgements`.

### Deliverable
- documentazione conforme, attribution completa, runtime pulito.

### Exit Criteria
- credits presenti e validati; nessun riferimento operativo a OpenCode.

---

## Fase V3-6 — CI/CD, Release, Verification
**Obiettivo:** blindare la separazione con controlli automatici.

### Task
1. Aggiornare pipeline build/test per prodotto unico ARIA.
2. Aggiornare packaging/release con naming ARIA-only.
3. Aggiungere check automatico anti-regressione stringhe legacy (`opencode`, `.opencode`, ecc.) nel codice runtime.
4. Eseguire smoke test su ambiente clean.

### Deliverable
- pipeline stabile e guardrail anti-reintroduzione.

### Exit Criteria
- build/test/release verdi + checks anti-legacy verdi.

---

## 6) File/aree ad alto impatto (indicative)

- `main.go`
- `cmd/root.go`
- `internal/config/config.go`
- `internal/tui/**/*`
- `.opencode.json` (deprecazione/rimozione)
- docs principali (`README`, docs onboarding, docs config)
- script release/CI

---

## 7) Risk Register (v3)

| Risk | Impatto | Prob. | Mitigazione |
|------|---------|-------|-------------|
| Regressioni config utenti esistenti | Medio | Medio | Migrazione one-shot + note upgrade |
| Rottura UX per rinomina asset/testi | Medio | Medio | smoke test TUI + checklist QA |
| Riferimenti legacy reintrodotti | Medio | Alto | CI lint/check dedicato |
| Ambiguità path dati | Alto | Medio | standardizzare data dir e documentarlo |

---

## 8) Acceptance Criteria finali (v3)

### Codice e runtime
- [ ] Comando CLI e output runtime ARIA-only
- [ ] Nessun riferimento OpenCode nel codice eseguibile
- [ ] Nessuna dipendenza da `.opencode.json` o path `.opencode`

### Configurazione
- [ ] Config ARIA dedicata e documentata
- [ ] Migrazione legacy (se prevista) non obbligatoria a runtime

### UX
- [ ] Branding ARIA completo (logo, splash, testi)
- [ ] Nessuna stringa OpenCode nelle schermate ARIA

### Documentazione
- [ ] Credits ufficiali presenti: “Based on OpenCode”
- [ ] Nessun riferimento operativo a OpenCode nelle guide d’uso ARIA

### Delivery
- [ ] `go build` e `go test ./...` verdi
- [ ] CI con guardrail anti-legacy attivo

---

## 9) Ordine operativo rigido

1. V3-0 Inventory & Freeze  
2. V3-1 CLI Identity Migration  
3. V3-2 Config & Data Path Migration  
4. V3-3 TUI/UX Brand Purge  
5. V3-4 Codebase Cleanup  
6. V3-5 Documentation & Credits  
7. V3-6 CI/CD & Verification

---

## 10) Nota Credits (testo base proposto)

> ARIA is based on OpenCode. We acknowledge the original OpenCode project and its contributors for the foundational architecture and ideas that enabled ARIA’s evolution.

(da includere nella documentazione ufficiale, non nel runtime)
