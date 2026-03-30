# ARIA Standalone Separation Plan v2

**Date:** 2026-03-30  
**Author:** General Manager (based on codebase verification)  
**Status:** PROPOSTA PRONTA PER APPROVAZIONE E IMPLEMENTAZIONE  
**Objective:** Rendere ARIA completamente autonoma e isolata da OpenCode, a livello di binario, configurazione, dipendenze, runtime e release.

---

## 1) Executive Summary

Il piano v1 definisce una direzione corretta, ma non è sufficiente per ottenere isolamento reale perché ARIA è ancora accoppiata a componenti OpenCode (`internal/llm/*`, `internal/message`, `internal/session`, `internal/config`, TUI branding/path legacy).

Questo piano v2 introduce una separazione **strutturale** (contratti + adapter), non solo una riorganizzazione directory. È allineato a best practice Go/CLI 2026:
- entrypoint multipli per binari distinti (`cmd/aria/main.go`, `cmd/opencode/main.go`)
- dipendenze governate da interfacce e boundary checks in CI
- configurazione e data-path isolati per prodotto
- release engineering dual-binary con verifiche automatiche anti-regressione

---

## 2) Scope

### In Scope
- Binario `aria` standalone
- Binario `opencode` standalone
- Isolamento configurazione (`aria.json` + `ARIA_*`)
- Isolamento runtime/data paths
- Separazione import path e dipendenze
- Branding ARIA indipendente
- CI/CD e release dual binary

### Out of Scope (per questa iterazione)
- Split immediato in due repository separati (valutato in fase finale opzionale)
- Riscrittura funzionale completa di skill/agency (si lavora per adapter progressivi)

---

## 3) Stato attuale verificato (e gap)

### 3.1 Entry point e bootstrap
- `main.go` usa `cmd.Execute()`
- `cmd/root.go` è root CLI `opencode`
- Nessun entrypoint dedicato `aria`

**Gap:** manca separazione formale dei binari.

### 3.2 Accoppiamenti ARIA -> OpenCode
Esempi rilevanti:
- `internal/aria/agency/development.go` importa:
  - `internal/llm/agent`
  - `internal/message`
  - `internal/session`
- `internal/aria/skill/tdd.go` e `debugging.go` importano `internal/llm/tools`
- `internal/aria/memory/service.go` importa `internal/db`, `internal/logging`
- `internal/aria/analysis/service.go` importa `internal/db`, `internal/logging`

**Gap:** ARIA non è isolabile tramite semplice move/rename cartelle.

### 3.3 Configurazione condivisa
- `.opencode.json` contiene sezione `aria`
- `internal/config/config.go` include `ARIAConfig`
- `internal/aria/config/config.go` già legge `ARIA_*`

**Gap:** doppia fonte e contaminazione configurativa.

### 3.4 Branding/UI legacy
- riferimenti OpenCode in `internal/tui/*` (logo, OpenCode.md, path `.opencode`, tema opencode)

**Gap:** identità ARIA non completamente separata.

---

## 4) Target Architecture (v2)

```
cmd/
  aria/main.go
  opencode/main.go

internal/
  aria/
    core/
    agency/
    skill/
    routing/
    memory/
    scheduler/
    guardrail/
    config/
    contracts/
      runtime/         # interfacce boundary ARIA
  opencode/
    app/
    llm/
    tui/
    config/
    adapters/          # implementazioni runtime contracts per ARIA
  platform/
    db/
    logging/
    pubsub/
    format/
    version/
    history/
    permission/
```

### Regola di dipendenza
- `internal/aria/*` **NON** importa `internal/opencode/*`
- `internal/aria/*` importa solo:
  - `internal/aria/*`
  - `internal/platform/*`
  - standard/third-party
- integrazione con OpenCode tramite `internal/aria/contracts/runtime` + adapter.

---

## 5) Piano di Implementazione v2 (Fasi)

## Fase V2-0 — Boundary Audit (Gate 0)
**Obiettivo:** mappa completa dipendenze e confini prima del refactor.

### Task
1. Generare dependency matrix package-level (aria/opencode/shared/platform).
2. Identificare import proibiti e import transitori tollerati.
3. Definire policy di confine automatizzabile in CI.

### Deliverable
- `docs/plans/aria-separation-dependency-matrix.md`
- elenco import da eliminare per fase.

### Exit Criteria
- confini approvati e baseline dependency snapshot versionata.

---

## Fase V2-1 — Multi-binary Entry Points
**Obiettivo:** separare bootstrap e comandi dei due prodotti.

### Task
1. Creare `cmd/aria/main.go`.
2. Creare `cmd/opencode/main.go`.
3. Portare root command OpenCode sotto package dedicato.
4. Preparare bootstrap ARIA dedicato (senza TUI OpenCode obbligatoria).

### Deliverable
- build indipendente dei due binari.

### Exit Criteria
- `go build ./cmd/aria` OK
- `go build ./cmd/opencode` OK

---

## Fase V2-2 — Contracts & Adapters (separazione strutturale)
**Obiettivo:** rompere accoppiamenti diretti ARIA -> OpenCode.

### Task
1. Definire interfacce in `internal/aria/contracts/runtime`:
   - AgentRunner
   - ToolRunner
   - SessionStore
   - MessageStore
   - PermissionGateway
2. Refactor ARIA agency/skill per dipendere da tali interfacce.
3. Implementare adapter in `internal/opencode/adapters/*`.
4. Sostituire costruttori ARIA con dependency injection.

### Deliverable
- ARIA core compilabile senza import a `internal/opencode/*` o `internal/llm/*` diretti.

### Exit Criteria
- nessun import diretto proibito nel layer ARIA.

---

## Fase V2-3 — Package Ristructuring (opencode/platform)
**Obiettivo:** riflettere i confini nel filesystem e import path.

### Task
1. Spostare package OpenCode in `internal/opencode/*`.
2. Spostare componenti infrastrutturali neutrali in `internal/platform/*`.
3. Aggiornare import path con refactor atomici e test incrementali.

### Deliverable
- tree coerente con target architecture.

### Exit Criteria
- `go test ./...` verde o con fail noti tracciati e bloccanti risolti.

---

## Fase V2-4 — Config & Runtime/Data Isolation
**Obiettivo:** eliminare condivisione di config e stato tra prodotti.

### Task
1. Rimuovere sezione `aria` da `.opencode.json` e da `internal/opencode/config`.
2. Introdurre loader `aria.json`:
   - lookup: project root -> `~/.config/aria/aria.json`
   - merge precedence: CLI flags > env `ARIA_*` > `aria.json` > default
3. Definire data path ARIA dedicato (`~/.local/share/aria` o `~/.aria`), incluso DB.
4. Implementare migrazione automatica opzionale da config legacy.

### Deliverable
- ARIA configurabile senza dipendere da `.opencode.json`.

### Exit Criteria
- test config loader ARIA (precedenza, fallback, invalid schema).

---

## Fase V2-5 — Identity & UX Separation (Splash + branding cleanup)
**Obiettivo:** identità ARIA completa e rimozione leakage OpenCode.

### Task
1. Implementare splash screen ARIA (`internal/aria/ui/splash.go`) con lipgloss.
2. Definire icone/stili ARIA dedicati.
3. Eliminare riferimenti OpenCode dalla UX ARIA:
   - logo
   - testo prodotto
   - memory file naming
   - path legacy `.opencode` in flussi ARIA
4. Version/tagline/repo URL in startup ARIA.

### Deliverable
- startup ARIA con branding autonomo.

### Exit Criteria
- nessun riferimento “OpenCode” in percorso runtime ARIA.

---

## Fase V2-6 — CI/CD e Release Engineering
**Obiettivo:** rendere la separazione enforceable e distribuibile.

### Task
1. Aggiornare pipeline CI con matrix:
   - build/test aria
   - build/test opencode
2. Aggiungere boundary checks automatici (script import guard).
3. Aggiornare goreleaser per due binari e artifacts distinti.
4. Aggiornare documentazione install/upgrade.

### Deliverable
- pipeline stabile dual-binary.

### Exit Criteria
- CI verde con guardrail di confine attivi.

---

## Fase V2-7 — Hardening & Verification Finale (Gate finale)
**Obiettivo:** dimostrare isolamento reale, non solo compilazione.

### Task
1. End-to-end test su entrambi i binari.
2. Regression test su feature critiche.
3. Static checks su dependency boundaries.
4. Smoke test su ambienti clean (senza config legacy).

### Deliverable
- report finale di separazione con evidenze.

### Exit Criteria (obbligatorie)
- `aria` standalone funziona senza `.opencode.json`
- `opencode` standalone funziona senza moduli ARIA runtime-critical
- nessun import proibito ARIA -> OpenCode
- test/build/release pipeline verdi

---

## Fase V2-8 (Opzionale) — Repository Split
**Obiettivo:** isolamento organizzativo completo.

### Task
1. Estrarre ARIA in repo dedicato.
2. Migrare CI/release/docs separati.
3. Definire compatibilità e versioning cross-project.

### Exit Criteria
- governance e ciclo release indipendenti.

---

## 6) File-level changes (indicativi v2)

### Nuovi file/dir
- `cmd/aria/main.go`
- `cmd/opencode/main.go`
- `internal/aria/contracts/runtime/*.go`
- `internal/opencode/adapters/*.go`
- `internal/aria/ui/splash.go`
- `internal/aria/ui/icons.go`
- `internal/aria/ui/styles.go`
- `docs/plans/aria-separation-dependency-matrix.md`

### Modifiche ad alto impatto
- `internal/app/*` (split bootstrap)
- `internal/config/*` (rimozione ARIA da OpenCode config)
- `.opencode.json` (rimozione blocco aria)
- componenti TUI con riferimenti OpenCode hardcoded

---

## 7) Risk Register (aggiornato)

| Risk | Impatto | Prob. | Mitigation |
|------|---------|-------|------------|
| Refactor massivo rompe import chain | Alto | Medio | Fasi atomiche + adapter first |
| Circular dependencies durante move | Alto | Medio | Contracts + inversione dipendenze prima di spostare |
| Regressioni UX in TUI | Medio | Medio | Snapshot/smoke test UI |
| Drift configurazione tra env/file | Medio | Alto | precedence tests + schema validation |
| CI rallentata da doppio build matrix | Basso | Medio | caching modules + test selection |

---

## 8) Best Practice 2026 adottate

1. **Architecture by boundaries**: isolamento per interfacce, non per cartelle.
2. **Dependency inversion**: dominio ARIA dipende da contratti, non da implementazioni OpenCode.
3. **Dual-product release discipline**: pipeline e artifact separati.
4. **Policy-as-code**: boundary checks in CI come gate obbligatorio.
5. **Config precedence deterministic**: flag > env > file > default.
6. **Runtime/data isolation**: path e DB per prodotto distinti.

---

## 9) Acceptance Criteria Finali

### Separazione strutturale
- [ ] Nessun import `internal/aria/* -> internal/opencode/*`
- [ ] Nessun import `internal/aria/* -> internal/llm/*` diretto (solo contratti/adapter)
- [ ] Nessuna dipendenza ARIA da `.opencode.json`

### Build/Run
- [ ] `go build ./cmd/aria` success
- [ ] `go build ./cmd/opencode` success
- [ ] `aria` run standalone in ambiente clean
- [ ] `opencode` run standalone in ambiente clean

### Config/Data
- [ ] `aria.json` supportato con precedence corretta
- [ ] `ARIA_*` supportato e documentato
- [ ] path runtime ARIA isolato da OpenCode

### UX/Brand
- [ ] Splash ARIA attivo
- [ ] Nessun branding OpenCode nella UX ARIA

### Quality/Release
- [ ] Test suite verde
- [ ] CI boundary checks verdi
- [ ] Release dual-binary completata

---

## 10) Sequenza operativa consigliata (ordine rigido)

1. V2-0 Boundary Audit  
2. V2-1 Multi-binary Entrypoints  
3. V2-2 Contracts & Adapters  
4. V2-3 Ristrutturazione package  
5. V2-4 Config/Data isolation  
6. V2-5 Branding separation  
7. V2-6 CI/CD & Release  
8. V2-7 Hardening finale  
9. V2-8 Repo split (opzionale)

---

## 11) Decisione richiesta (HitL)

Per avvio implementazione serve approvazione esplicita del piano v2 e dell’ordine fasi, con gate obbligatori tra una fase e la successiva.
