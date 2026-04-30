# Rollback Matrix — ARIA Stabilization Plan

> **Data**: 2026-04-30  
> **Piano sorgente**: `docs/plans/stabilizzazione_aria.md`  
> **Riferimenti**: `docs/plans/gestione_mcp_refoundation_plan_v2.md` §7-8, `scripts/rollback_baseline.sh`  
> **Principio guida**: Ogni fase deve essere reversibile in modo rapido e con blast radius limitato.

---

## Tabella riassuntiva

| Fase | Scope | Artefatto attivato | Trigger rollback | Rollback minimo | Blast radius | MTTR target |
|------|-------|--------------------|------------------|-----------------|--------------|:-----------:|
| F0 | global | Branch merge + tag | Test fail post-merge, regressione utente | `git revert PR` + ripristino branch | global | <30 min |
| F1 | none | Documentazione baseline | n/a | rimuovere file output | none | n/a |
| F2 | session/domain | Capability matrix YAML enforced | Validator blocca handoff legittimi | `ARIA_CAPABILITY_ENFORCEMENT=0` + revert prompt | domain | <5 min |
| F2 | session | Handoff JSON validator | Sub-agent bloccato | `ARIA_HANDOFF_VALIDATION=0` | session | <2 min |
| F3 | domain | Schema snapshot enforcement | Schema drift falso positivo, capability probe falso negativo | `ARIA_PROBE_ENFORCEMENT=0` + restore snapshot baseline | domain | <5 min |
| F3 | domain | Tool search / lazy loading probe | Bootstrap candidate fallisce, tool mancanti dopo probe | Disabilitare flag tool search/lazy, ripristinare bootstrap baseline | domain | <5 min |
| F4 | domain | MCP catalog diff validator | Catalogo drift blocca configurazione legittima | `ARIA_CATALOG_ENFORCEMENT=0` + revert baseline catalog | domain | <10 min |
| F4 | session | Schema snapshot incompatibility | Snapshot mismatch blocca startup server | `ARIA_SNAPSHOT_VALIDATION=0` + ricattura snapshot | session | <3 min |
| F5 | none | Test + drill | n/a | Test skippabili via marker | none | n/a |

---

## Rollback strategia per fase

### F0 — Baseline globale (Branch merge + tag)

**Artefatto attivato**: Merge PR su `main` + tag LKG.

**Trigger rollback**:
- Test di qualità falliscono dopo il merge (quality gate CI rosso).
- Regressione utente segnalata su funzionalità esistenti.
- Mismatch catalogo/config rilevato dal drift checker.

**Procedura di rollback**:
1. `git revert <merge-commit-hash>` sul branch `main`.
2. Ripristinare il branch feature dal revert locale.
3. Applicare `git tag -d <baseline-tag>` e ri-taggare il commit LKG precedente.
4. Notificare il team: revert su `main`, causato da `<trigger>`.

**Blast radius**: GLOBALE — l'intero repository è impattato. Ma il `git revert` è atomico e istantaneo.

**MTTR target**: <30 minuti.

**Post-rollback**: Analizzare il failure: il merge era basato su baseline sbagliata o il quality gate era insufficiente?

---

### F1 — Documentazione baseline

**Artefatto attivato**: File di documentazione baseline (wiki, runbook, mappa rollback).

**Trigger rollback**: n/a — fase puramente documentale senza cambiamento runtime.

**Procedura di rollback**: Rimuovere i file di output generati (report, snapshot dimostrativi). Nessun rollback runtime necessario perché F1 non attiva alcun cutover.

**Blast radius**: NESSUNO — solo documentazione, nessuna modifica a configurazione, codice o runtime.

**Post-rollback**: n/a.

---

### F2 — Capability matrix e handoff validation

#### F2a — Capability matrix YAML enforced

**Artefatto attivato**: Validazione `agent-capability-matrix.md` YAML all'avvio di sessione.

**Trigger rollback**:
- Il validatore blocca handoff sub-agent legittimi (falso positivo).
- La capability matrix non riflette un agente appena aggiunto.
- Cambiamento di routing necessario senza aggiornamento matrix.

**Procedura di rollback**:
1. `export ARIA_CAPABILITY_ENFORCEMENT=0` (disabilita validazione rigorosa).
2. `git checkout main -- docs/foundation/agent-capability-matrix.md` (ripristino baseline).
3. Se la validazione era inline nel prompt, rimuovere o commentare il blocco di enforcement.
4. Ricaricare la configurazione agente (nessun restart necessario).

**Blast radius**: DOMINIO — solo l'agente/tool in handoff è impattato. Altri domini continuano a funzionare.

**MTTR target**: <5 minuti.

#### F2b — Handoff JSON validator

**Artefatto attivato**: Validatore JSON per handoff sub-agent.

**Trigger rollback**:
- Sub-agent bloccato da validazione eccessiva.
- Schema handoff cambiato ma validatore non aggiornato.
- Falso positivo in catena di handoff multi-hop.

**Procedura di rollback**:
1. `export ARIA_HANDOFF_VALIDATION=0` (disabilita validazione handoff).
2. Il conductor ricade a handoff non validato (controllo solo formale).
3. Nessun deploy richiesto — variabile d'ambiente letta a runtime.

**Blast radius**: SESSIONE — solo la sessione corrente viene degradata. Altre sessioni e domini sono isolati.

**MTTR target**: <2 minuti.

---

### F3 — Schema snapshot enforcement e probe bootstrap

#### F3a — Schema snapshot enforcement

**Artefatto attivato**: Validazione schema `tools/list` contro snapshot atteso (capability probe framework).

**Trigger rollback**:
- Schema drift falso positivo: un server legittimamente aggiornato viene bloccato.
- Capability probe non riesce contro un server lento ma funzionante.
- Snapshot baseline non aggiornato dopo deploy MCP server.

**Procedura di rollback**:
1. `export ARIA_PROBE_ENFORCEMENT=0` (disabilita capability probe enforcement).
2. `git checkout main -- .aria/runtime/mcp-schema-snapshots/` (ripristino snapshot baseline).
3. Verificare che il server in quarantena sia accessibile via direct path.
4. Eventuale ricattura snapshot: `capability_probe.py --recapture --server <name>`.

**Blast radius**: DOMINIO — solo il server/dominio con snapshot mismatch è disabilitato. Altri domini operano normalmente.

**MTTR target**: <5 minuti.

#### F3b — Tool search / lazy loading probe

**Artefatto attivato**: Bootstrap candidate con tool search e/o lazy loading abilitato.

**Trigger rollback**:
- Tool mancanti dopo probe (candidate path non ha rilevato correttamente i tool).
- Startup regression: il candidate path rallenta invece di accelerare.
- Mismatch tool exposure tra probe e runtime reale.

**Procedura di rollback**:
1. Disabilitare i flag: rimuovere `ARIA_TOOL_SEARCH=1` e `ARIA_LAZY_LOAD=1`.
2. `git checkout main -- .aria/kilocode/mcp.json` (ripristino mcp.json baseline).
3. Ricaricare la configurazione: nessun restart sessione necessario (lettura a runtime).
4. Conservare snapshot del candidate per analisi delta.

**Blast radius**: DOMINIO — solo il bootstrap del dominio è impattato. Server già connessi continuano a funzionare.

**MTTR target**: <5 minuti.

---

### F4 — MCP catalog e schema snapshot governance

#### F4a — MCP catalog diff validator

**Artefatto attivato**: Validatore drift tra `mcp_catalog.yaml` e `mcp.json`/prompt runtime.

**Trigger rollback**:
- Catalogo drift blocca una configurazione MCP legittima (falso positivo).
- Shadow mode riporta mismatch che non sono veri drift (es. server non ancora catalogato).
- Cambiamento architetturale temporaneo non riflesso nel catalogo.

**Procedura di rollback**:
1. `export ARIA_CATALOG_ENFORCEMENT=0` (disabilita validazione catalogo).
2. `git checkout main -- .aria/config/mcp_catalog.yaml` (ripristino baseline catalogo).
3. Se shadow mode attivo: disabilitare enforcement diff, mantenere solo logging.
4. Ricatturare baseline con `scripts/check_mcp_drift.py --recapture`.

**Blast radius**: DOMINIO — la validazione catalogo è specifica per dominio/server. Le sessioni aperte continuano con la configurazione corrente.

**MTTR target**: <10 minuti.

#### F4b — Schema snapshot incompatibility

**Artefatto attivato**: Validazione compatibilità schema snapshot all'avvio server MCP.

**Trigger rollback**:
- Snapshot incompatibility blocca l'avvio di un server legittimo.
- Schema cambiato a valle (es. MCP server aggiornato) ma snapshot non ricatturato.
- Falso positivo nella comparazione schema.

**Procedura di rollback**:
1. `export ARIA_SNAPSHOT_VALIDATION=0` (disabilita validazione snapshot).
2. Ricatturare snapshot: `capability_probe.py --recapture --server <name>`.
3. Se la ricattura fallisce, ripristinare snapshot da backup: `git checkout main -- .aria/runtime/mcp-schema-snapshots/`.
4. Aggiornare baseline snapshot dopo verifica manuale.

**Blast radius**: SESSIONE — solo la sessione che tenta di avviare il server MCP è impattata. Altre sessioni sono isolate.

**MTTR target**: <3 minuti.

---

### F5 — Test e drill

**Artefatto attivato**: Suite di test (unit, integration, smoke) e procedure di rollback drill.

**Trigger rollback**: n/a — fase di verifica, non di cutover.

**Procedura di rollback**: I test sono skippabili via marker pytest (`-m "not rollback_drill"`). I drill falliti non bloccano il runtime — producono solo un report di remediation.

**Blast radius**: NESSUNO — i test non modificano configurazione, runtime o stato persistente.

**Post-rollback**: Il drill fallito genera una remediation action. Il test fallito blocca solo il gate CI, non il runtime in produzione.

---

## Riepilogo flag di rollback

| Variabile | Fase | Effetto |
|-----------|------|---------|
| `ARIA_CAPABILITY_ENFORCEMENT=0` | F2 | Disabilita validazione capability matrix |
| `ARIA_HANDOFF_VALIDATION=0` | F2 | Disabilita validazione JSON handoff |
| `ARIA_PROBE_ENFORCEMENT=0` | F3 | Disabilita capability probe enforcement |
| `ARIA_CATALOG_ENFORCEMENT=0` | F4 | Disabilita validazione catalogo MCP |
| `ARIA_SNAPSHOT_VALIDATION=0` | F4 | Disabilita validazione schema snapshot |
| `pytest -m "not rollback_drill"` | F5 | Skippa test di drill rollback |

Tutti i flag sono variabili d'ambiente lette a runtime — nessun deploy richiesto per il rollback.

---

## Gate di attivazione (prima del cutover)

Prima di attivare qualsiasi fase con impatto runtime (F2, F3, F4), devono essere verdi tutti i seguenti gate:

1. **Baseline metrics captured** — metriche pre-cutover registrate.
2. **Drift checks green** — nessun mismatch catalogo/config/prompt non atteso.
3. **Schema snapshot compatibility green** — snapshot atteso == snapshot reale.
4. **Smoke tests di dominio green** — test E2E minimi sul dominio passano.
5. **Rollback action documentata** — la procedura di rollback per la fase è scritta.
6. **Rollback drill eseguito almeno una volta** — la procedura è stata testata.
7. **HITL approval** — approvazione umana se il cambiamento tocca auth/write path.

---

## Provenance

- `docs/plans/stabilizzazione_aria.md` — piano stabilizzazione ARIA (F0-F5)
- `docs/plans/gestione_mcp_refoundation_plan_v2.md` §7-8 — fasi e rollback matrix minima
- `scripts/rollback_baseline.sh` — rollback drill script operativo
- `docs/foundation/aria_foundation_blueprint.md` §10, §14, §16 — blueprint vincoli architetturali
- `docs/foundation/agent-capability-matrix.md` — capability matrix canonica F2
- `src/aria/agents/search/capability_probe.py` — capability probe framework F3
- `docs/llm_wiki/wiki/log.md` — tracciato implementazione fasi stabilizzazione
