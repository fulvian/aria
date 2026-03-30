# ARIA Standalone Separation Plan v4

**Date:** 2026-03-30  
**Author:** General Manager (v4 integrata da v2 + vincoli v3)  
**Status:** READY FOR EXECUTIVE APPROVAL (HitL Milestone)  
**Objective:** Completare l’autonomia di ARIA nel repository attuale (già ARIA-only), eliminando ogni riferimento operativo a OpenCode nel codice, mantenendo solo attribution nei credits ufficiali.

---

## 0) Change Log (v4 vs v2/v3)

### Cosa mantiene da v2 (non semplificato)
- Boundary audit iniziale con dependency matrix.
- Separazione strutturale tramite **contracts + dependency inversion**.
- Migrazione configurazione con precedence deterministica.
- Runtime/data-path isolation.
- Branding separation completa.
- CI policy-as-code con guardrail automatici.
- Hardening finale con evidenze verificabili.
- Risk register + acceptance criteria completi.

### Cosa aggiorna da v3 (nuovi vincoli)
- **Rimosso completamente il modello dual-product (aria/opencode)**.
- **Rimossa qualsiasi previsione di split repository**.
- Piano centrato su un unico prodotto/binario: **ARIA**.
- Introduce formalmente la **Credits-only policy**: OpenCode solo in documentazione ufficiale.

---

## 1) Executive Summary

Il repo corrente è già il repo prodotto ARIA. Il problema non è più “separare due prodotti”, ma completare una **decontaminazione tecnica e semantica** da residui OpenCode nel runtime.

L’isolamento viene trattato su 6 livelli:
1. **Identità CLI/UI** (comando, help, logo, testi, tema).
2. **Configurazione** (namespace e file ARIA-only).
3. **Dipendenze** (nessun accoppiamento semantico/tecnico a componenti legacy nominati OpenCode).
4. **Runtime state** (path e storage ARIA-only).
5. **Release/CI** (naming, artifact e guardrail anti-regressione).
6. **Documentazione** (OpenCode solo credits, non runtime docs operative).

---

## 2) Scope

### In Scope
- Unico binario prodotto: `aria`.
- Cleanup completo riferimenti OpenCode nel codice eseguibile.
- Config ARIA-only (`ARIA_*` + `aria.json` opzionale).
- Runtime/data paths ARIA-only.
- Boundary rules su package e import.
- Rebranding completo TUI/UX.
- CI/CD e release ARIA-only.
- Credits ufficiali “Based on OpenCode”.

### Out of Scope
- Gestione backward-compat permanente con naming/config OpenCode.
- Mantenimento di un secondo prodotto o secondo binario.
- Creazione/gestione di un secondo repository.

---

## 3) Vincoli Architetturali (non negoziabili)

1. **Single product policy**: il codice runtime espone esclusivamente ARIA.
2. **No OpenCode runtime references**: vietato in CLI, TUI, config, logs, path, prompts utente runtime.
3. **Attribution-only policy**: stringhe OpenCode consentite solo in docs credits/acknowledgements/licensing.
4. **Dependency boundaries**: i layer ARIA core dipendono da contratti/interfacce, non da implementazioni concrete legacy.
5. **Evidence before completion**: nessuna fase chiusa senza prove (build/test/check/report).

---

## 4) Stato Attuale Verificato (baseline)

### 4.1 CLI/entrypoint
- `main.go` chiama `cmd.Execute()`.
- `cmd/root.go` ancora con `Use: "opencode"`.

### 4.2 Config
- `.opencode.json` presente.
- `internal/config/config.go` usa `appName = "opencode"`, path e defaults legacy.
- `internal/aria/config/config.go` già orientato `ARIA_*` (base utile).

### 4.3 Branding TUI
- riferimenti OpenCode in componenti TUI e tema (`internal/tui/**`).
- logo/icona/label/testi init con naming OpenCode.

### 4.4 Accoppiamenti tecnici da rifinire
- Alcuni moduli ARIA dipendono da componenti infrastrutturali/agent/tool condivisi storicamente.
- Necessaria formalizzazione boundary tramite contracts + adapter interni ARIA.

### 4.5 Documentazione
- attribution non formalizzata in una policy unica e consistente.

---

## 5) Target Architecture (v4, single-repo ARIA-only)

```
main.go                     # entrypoint unico ARIA
cmd/
  root.go                   # root command aria

internal/
  aria/
    core/
    agency/
    skill/
    routing/
    memory/
    scheduler/
    guardrail/
    analysis/
    config/
    ui/
    contracts/
      runtime/              # interfacce boundary ARIA
    adapters/               # adapter verso servizi concreti interni

  platform/                 # infrastruttura neutra riusabile
    db/
    logging/
    pubsub/
    format/
    version/
    history/
    permission/

  (eventuali package legacy rinominati o assorbiti)
```

### Dependency Rule Set
- `internal/aria/core|agency|skill|routing|analysis` importa solo:
  - `internal/aria/*`
  - `internal/platform/*`
  - stdlib/third-party
- vietate dipendenze a package con naming legacy OpenCode.
- integrazioni effettuate via `internal/aria/contracts/runtime`.

---

## 6) Implementation Plan v4 (phased, gate-based)

## Fase V4-0 — Boundary Audit & Inventory Freeze (Gate 0)
**Obiettivo:** avere mappa completa prima di toccare codice.

### Task
1. Generare inventario riferimenti:
   - `opencode`, `OpenCode`, `.opencode`, `OpenCode.md`, tema `opencode`, icone legacy.
2. Generare dependency matrix package-level.
3. Definire allowlist/denylist import e string policy.
4. Baseline report versionato.

### Deliverable
- `docs/plans/aria-opencode-cleanup-inventory.md`
- `docs/plans/aria-separation-dependency-matrix.md`
- `docs/plans/aria-boundary-policy.md`

### Exit Criteria
- Copertura inventory >= 100% file runtime impattati.
- Policy approvata e pronta per CI checks.

---

## Fase V4-1 — CLI Identity Migration (ARIA-only)
**Obiettivo:** standardizzare identità prodotto su comando e help.

### Task
1. Aggiornare `cmd/root.go`:
   - `Use: "aria"`
   - descrizione, examples, long help ARIA-only.
2. Aggiornare eventuali comandi secondari e output version.
3. Verificare startup e modalità non interattiva con naming ARIA-only.

### Deliverable
- CLI coerente ARIA.

### Exit Criteria
- `go run ./main.go -h` senza riferimenti OpenCode.
- comando principale e docs CLI coerenti.

---

## Fase V4-2 — Contracts & Dependency Inversion (structural decoupling)
**Obiettivo:** mantenere robustezza architetturale di v2 senza modello dual-repo.

### Task
1. Definire/intergrare `internal/aria/contracts/runtime` per:
   - Agent runtime interaction
   - Tool execution abstraction
   - Session/message abstraction
   - Permission gateway
2. Refactor `internal/aria/agency/*` e `internal/aria/skill/*` per dipendere da interfacce.
3. Implementare adapter in `internal/aria/adapters/*` verso implementazioni concrete esistenti.
4. Sostituire costruttori diretti con dependency injection.

### Deliverable
- ARIA core indipendente da dettagli concreti legacy e naming OpenCode.

### Exit Criteria
- assenza di import proibiti nel layer core ARIA.
- test unit su interfacce e adapter.

---

## Fase V4-3 — Package Normalization & Runtime Renaming
**Obiettivo:** eliminare residui semantici/strutturali legacy nel codice.

### Task
1. Rinominare package/const/docstring/messages con naming ARIA.
2. Consolidare infrastruttura neutra sotto `internal/platform/*` dove opportuno.
3. Rimuovere dead code e compat layer non necessari.
4. Aggiornare import path con refactor atomici.

### Deliverable
- struttura coerente con target architecture ARIA-only.

### Exit Criteria
- `go test ./...` verde (o failure bloccanti documentati e risolti).
- nessun path/package runtime con naming OpenCode.

---

## Fase V4-4 — Config & Data Isolation
**Obiettivo:** completare separazione config/state con standard ARIA.

### Task
1. Deprecare/rimuovere `.opencode.json` dal runtime ARIA.
2. Stabilire loader `aria.json` opzionale:
   - lookup: project root -> `~/.config/aria/aria.json`
   - precedence: `flags > ARIA_* > aria.json > defaults`
3. Standardizzare data path ARIA (es. `~/.local/share/aria`).
4. Migrazione one-shot opzionale da legacy config/path (best effort, non dipendenza runtime).
5. Test schema/config precedence/fallback.

### Deliverable
- stack config ARIA-only, deterministico.

### Exit Criteria
- avvio ARIA in ambiente clean senza file/path OpenCode.
- suite test config verde.

---

## Fase V4-5 — Identity & UX Separation (Splash + Full Brand Purge)
**Obiettivo:** identità visuale e testuale interamente ARIA.

### Task
1. Implementare splash ARIA (`internal/aria/ui/splash.go`).
2. Implementare set icone/stili ARIA dedicati.
3. Rimuovere riferimenti OpenCode in:
   - chat header/logo
   - dialog init
   - memory file guidance
   - temi default
4. Garantire versione/tagline/URL ARIA nello startup.

### Deliverable
- UX ARIA completa, senza leakage legacy.

### Exit Criteria
- test/smoke TUI senza stringhe OpenCode.

---

## Fase V4-6 — Documentation, Credits & Policy Enforcement
**Obiettivo:** mantenere attribuzione corretta fuori dal runtime.

### Task
1. Aggiungere/aggiornare sezione Credits in doc ufficiale:
   - “ARIA is based on OpenCode…”
2. Aggiornare README/onboarding/config docs in ottica ARIA-only.
3. Formalizzare policy:
   - OpenCode ammesso solo in `docs/credits`, `ACKNOWLEDGEMENTS`, eventuali note licenza.
4. Allineare changelog e note migrazione utenti.

### Deliverable
- documentazione consistente, attribution corretta, runtime pulito.

### Exit Criteria
- nessun riferimento operativo a OpenCode nelle docs utente runtime.
- credits presenti e validati.

---

## Fase V4-7 — CI/CD, Release Engineering, Hardening Finale (Gate finale)
**Obiettivo:** rendere permanente la separazione e prevenire regressioni.

### Task
1. Pipeline ARIA-only:
   - build
   - test
   - lint/vet
2. Aggiungere guardrail automatici:
   - string check anti-legacy su codice runtime
   - boundary import checks
3. Aggiornare release artifacts e naming ARIA-only.
4. Eseguire hardening:
   - smoke test in clean env
   - regression test feature critiche
   - evidence report finale

### Deliverable
- pipeline stabile con enforcement automatico.
- report finale di conformità.

### Exit Criteria
- CI verde con guardrail attivi.
- nessuna regressione su identità/config/runtime ARIA.

---

## 7) File-Level Changes (indicativi, completi)

### Nuovi file/dir probabili
- `internal/aria/contracts/runtime/*.go`
- `internal/aria/adapters/*.go`
- `internal/aria/ui/splash.go`
- `internal/aria/ui/icons.go`
- `internal/aria/ui/styles.go`
- `docs/plans/aria-opencode-cleanup-inventory.md`
- `docs/plans/aria-boundary-policy.md`

### Modifiche ad alto impatto
- `main.go`
- `cmd/root.go`
- `internal/config/config.go`
- `internal/aria/config/*`
- `internal/tui/**/*` (o percorso UI equivalente adottato)
- `.opencode.json` (deprecazione/rimozione runtime)
- docs (`README`, quickstart, config docs, changelog)
- CI/release config

---

## 8) Risk Register (v4)

| Risk | Impatto | Prob. | Mitigazione |
|------|---------|-------|-------------|
| Refactor esteso rompe import chain | Alto | Medio | Fasi atomiche + test per fase + rollback point |
| Regressioni UX durante brand purge | Medio | Medio | smoke/snapshot TUI + QA checklist |
| Drift config tra env/file/default | Medio | Alto | test precedenza + schema validation |
| Reintroduzione riferimenti OpenCode | Medio | Alto | CI guardrails + denylist string/import |
| Migrazione utenti legacy incompleta | Medio | Medio | migration note + one-shot migrator opzionale |
| Costi CI aumentati per nuovi checks | Basso | Medio | caching + check selettivi per path |

---

## 9) Best Practices 2026 adottate

1. **Architecture by boundaries**: isolamento via contratti, non solo rename directory.
2. **Dependency inversion**: core ARIA indipendente da implementazioni concrete.
3. **Policy-as-code**: regole anti-regressione codificate in CI.
4. **Deterministic configuration layering**: flags > env > file > defaults.
5. **Runtime state isolation**: config/data paths chiaramente separati e documentati.
6. **Brand integrity engineering**: UX e CLI coerenti con singola identità prodotto.
7. **Evidence-driven delivery**: gate chiusi solo con prove verificabili.

---

## 10) Acceptance Criteria Finali (v4)

### A) Runtime & Code
- [ ] CLI principale è `aria`.
- [ ] Nessun riferimento OpenCode nel codice eseguibile/runtime paths/log user-facing.
- [ ] Nessuna dipendenza runtime da `.opencode.json` o `.opencode` path.

### B) Architecture & Dependencies
- [ ] Layer ARIA core conforme a boundary policy.
- [ ] Interazioni con servizi concreti mediate da contratti/adapter.
- [ ] Nessun import proibito definito in denylist.

### C) Config & Data
- [ ] `ARIA_*` supportato e documentato.
- [ ] `aria.json` opzionale supportato con precedence corretta.
- [ ] data path ARIA unico e stabile.

### D) UX/Brand
- [ ] Splash ARIA attivo.
- [ ] Tema/icone/testi ARIA-only.
- [ ] Assenza totale di brand OpenCode nelle schermate ARIA.

### E) Docs & Credits
- [ ] Credits ufficiali presenti (“Based on OpenCode”).
- [ ] Nessun riferimento operativo a OpenCode nelle guide utente ARIA.

### F) Quality & Delivery
- [ ] `go build` e `go test ./...` verdi.
- [ ] CI guardrails (string/import checks) verdi.
- [ ] Release artifacts ARIA-only completati.

---

## 11) Verification Matrix (per fase)

| Fase | Verifica minima | Evidenza |
|------|------------------|----------|
| V4-0 | inventory + policy complete | file report versionati |
| V4-1 | help/version ARIA-only | output CLI catturato |
| V4-2 | boundary imports rispettati | report static checks + test unit |
| V4-3 | refactor package/naming completato | `go test ./...` |
| V4-4 | config precedence corretta | test config + smoke clean env |
| V4-5 | zero brand leakage | grep report + screenshot/log TUI |
| V4-6 | credits docs + policy attiva | docs updated + policy doc |
| V4-7 | CI/release hardening | pipeline logs + release artifacts |

---

## 12) Sequenza Operativa Rigida

1. V4-0 Boundary Audit & Inventory Freeze  
2. V4-1 CLI Identity Migration  
3. V4-2 Contracts & Dependency Inversion  
4. V4-3 Package Normalization & Runtime Renaming  
5. V4-4 Config & Data Isolation  
6. V4-5 Identity & UX Separation  
7. V4-6 Documentation, Credits & Policy Enforcement  
8. V4-7 CI/CD, Release Engineering, Hardening Finale

---

## 13) Credits Text (approved template)

> ARIA is based on OpenCode. We acknowledge the original OpenCode project and its contributors for the foundational architecture and ideas that enabled ARIA’s evolution.

**Placement policy:** solo documentazione ufficiale (es. README/ACKNOWLEDGEMENTS/docs credits), mai nel runtime user-facing.

---

## 14) Decisione richiesta (HitL)

Per avviare implementazione serve approvazione del piano v4 e della sequenza fasi con gate obbligatori tra una fase e la successiva.
