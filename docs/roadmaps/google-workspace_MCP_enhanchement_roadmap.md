# Google Workspace MCP Enhancement Roadmap

## 0. Documento, finalita e perimetro

Questo documento e la roadmap complessiva per l'intervento di enhancement Google Workspace MCP in ARIA.
Ha ruolo di blueprint specifico dell'intervento e base per i piani implementativi di fase.

Obiettivo strategico:
- sbloccare in modo governato il 100% delle funzionalita del server upstream `workspace-mcp`;
- integrare tool, skills, workflow e policy nel sub-agente `workspace-agent`;
- garantire conformita a `docs/foundation/aria_foundation_blueprint.md` (P1..P10) e ADR attive;
- portare ARIA a livello professionale per assistenza agentica produttiva e di ricerca su Google Workspace.

Non obiettivi:
- fork o modifica del codice upstream `taylorwilsdon/google_workspace_mcp`;
- bypass del gate HITL su operazioni write/distruttive/costose;
- espansione multi-tenant in questa iniziativa (fuori scope fase corrente).

---

## 1. Baseline documentale (Context7 + evidenze repo)

### 1.1 Fonti ufficiali verificate su Context7

- `/taylorwilsdon/google_workspace_mcp`
  - comandi ufficiali `uvx workspace-mcp`
  - modalita `--tools`, `--tool-tier`, `--permissions`, `--read-only`, `--single-user`, `--transport`
  - superfice tool multi-dominio Workspace
- `/openai/codex`
  - baseline ufficiale per workflow CLI agentico e prompting orientato a task verificabili
- `/anthropics/claude-code`
  - baseline ufficiale per workflow agentico terminale e orchestrazione task multi-file

Nota: per OpenCode e KiloCode non emerge una singola libreria ufficiale univoca in Context7 equivalente alle precedenti; per questi sistemi si adotta la documentazione operativa gia ratificata nel repository (`AGENTS.md`, blueprint ARIA, ADR) come baseline vincolante.

### 1.2 Evidenze tecniche attuali (stato reale)

- ARIA usa upstream `workspace-mcp` via wrapper (`scripts/wrappers/google-workspace-wrapper.sh`) e non un fork locale.
- Versione runtime rilevata: `workspace-mcp 1.19.0`.
- Auth stdio locale stabilizzata rispetto al bug OAuth 2.1 context-bound (fix in commit recenti).
- Limite attuale: scope runtime effettivo ancora Gmail read-only in ambiente verificato.
- Scheduler workspace ancora in stub (`category != system -> not_implemented`).

---

## 2. Principi architetturali vincolanti per il programma

1. **Upstream invariance (P2)**
   - nessuna modifica al sorgente `google_workspace_mcp`; solo configurazione/adapter ARIA.
2. **Tool priority ladder (P8)**
   - prima MCP upstream, poi skill, poi eventuale script locale solo se necessario e temporaneo.
3. **Scoped toolsets (P9)**
   - `workspace-agent` non deve superare 20 tool simultanei; usare profili/toolset segmentati.
4. **HITL by default per write (P7)**
   - tutte le operazioni write in `ask` con evidenza testata e auditabile.
5. **Local-first + secrets posture (P4, ADR-0003)**
   - keyring come storage principale token; no segreti in git; hardening file runtime di compatibilita.
6. **Self-documenting evolution (P10)**
   - ogni divergenza da blueprint registrata via ADR prima del merge operativo.

---

## 3. Target architecture (to-be)

### 3.1 Livelli

- **L1 Transport**: `google_workspace` MCP server upstream avviato via wrapper ARIA.
- **L2 Governance**: policy matrix centralizzata (tool -> rischio -> scope -> HITL -> logging).
- **L3 Agent Runtime**: `workspace-agent` con toolset dinamico per dominio e intent.
- **L4 Skills**: libreria completa di skill workspace production-grade (read/write path separati).
- **L5 Orchestration**: conductor + scheduler + gateway con esecuzione reale, non-stub.
- **L6 Observability**: telemetria tool-level, report adozione, drift detection upstream/local.

### 3.2 Obiettivo di copertura

- 100% domini upstream presi in carico in governance matrix:
  Gmail, Calendar, Drive, Docs, Sheets, Slides, Forms, Chat, Tasks, Contacts, App Script, Custom Search.
- almeno 1 workflow production-grade per dominio.
- progressione in tranche per ridurre rischio operativo.

---

## 4. Modello di pianificazione e prompting multi-agent

Questa roadmap usa un prompt-contract standard comune a Codex, Claude Code, OpenCode e KiloCode, con adattatori minimi per piattaforma.

### 4.1 Prompt Contract standard (obbligatorio)

Ogni piano di fase e ogni task tecnico deve includere sempre:

1. `Objective`
2. `Context` (file/path e vincoli blueprint)
3. `Constraints` (P1..P10, ADR, sicurezza)
4. `Inputs` (documenti, schema, API refs)
5. `Execution Plan` (step atomici)
6. `Definition of Done`
7. `Verification` (comandi test/lint/typecheck/e2e)
8. `Expected Output` (artefatti e path)
9. `Non-goals`

### 4.2 Best practice prompting per piattaforma

#### A) Codex (CLI)
- prompt brevi ma deterministici, con path assoluti/relativi espliciti;
- richiedere sempre verifica eseguibile (`pytest`, `make quality`, smoke MCP);
- imporre output strutturato: patch + reasoning operativo + evidenze test.

Template minimo:
```text
Objective: <goal>
Context files: <paths>
Constraints: <blueprint rules>
Do:
1) ...
2) ...
Verify:
- <commands>
Deliverables:
- <files>
```

#### B) Claude Code
- decomporre in sub-task con checkpoints espliciti;
- esplicitare cosa NON modificare (no file unrelated, no destructive git);
- chiedere sempre esito sintetico con evidenze e line references.

#### C) OpenCode
- usare task unitari e idempotenti;
- preferire prompt orientati a output machine-checkable;
- includere sempre fallback path se tool primario fallisce.

#### D) KiloCode (ARIA runtime)
- rispettare `AGENTS.md` + blueprint + ADR;
- allineare naming tool al runtime (`google_workspace_*`);
- mantenere policy HITL e limiti P9 in ogni skill/agent definition.

### 4.3 Anti-pattern da evitare

- prompt ambigui senza DoD verificabile;
- richieste "implementa tutto" senza slicing per fase;
- assenza di vincoli di sicurezza/HITL;
- assenza di test evidence o metriche osservabili.

---

## 5. Roadmap per fasi

## Fase 0 - Program setup e governance baseline (P0)

### Obiettivo
Creare base di controllo unica per evitare drift tra upstream, agent config, skills, security e test.

### Attivita
1. Freeze baseline tecnica:
   - snapshot tool upstream (versione e domini);
   - snapshot config locale (`kilo.json`, `workspace-agent`, skills, scheduler).
2. Costruire `Tool Governance Matrix` centralizzata:
   - campi minimi: tool, dominio, read/write, rischio, HITL, scope minimo, owner, test-id.
3. Formalizzare ADR su credenziali runtime di compatibilita wrapper (se non gia coperto in modo esplicito).
4. Aggiornare validator:
   - migrazione `mcp.json` -> `kilo.json`;
   - check P9 automatico su agent e skill.

### Deliverable
- `docs/roadmaps/workspace_tool_governance_matrix.md`
- ADR dedicata a posture credenziali wrapper/runtime
- `scripts/validate_agents.py` e `scripts/validate_skills.py` aggiornati

### Exit criteria
- governance matrix completa per tutti i domini upstream;
- validator verdi su config reale;
- nessuna policy write senza owner e gate HITL definito.

---

## Fase 1 - Auth, scope e security hardening (P0)

### Obiettivo
Portare auth/scope da "Gmail read stabile" a baseline multi-servizio conforme blueprint/ADR.

### Attivita
1. Rimuovere hardcode scope `gmail.readonly` nel wrapper.
2. Derivare scope da sorgente canonica (`google_workspace_scopes_primary.json` + env policy).
3. Introdurre verifica di coerenza scope runtime vs scope richiesti dai tool attivi.
4. Hardening credenziali runtime:
   - permessi file/dir e lifecycle cleanup;
   - redaction logging;
   - policy di rotazione/revoca testata.
5. Test auth end-to-end:
   - setup manual fallback;
   - token refresh;
   - revoca e re-consent.

### Deliverable
- patch `scripts/wrappers/google-workspace-wrapper.sh`
- suite test auth estesa (`oauth_helper`, `scope_manager`, wrapper behavior)
- runbook `docs/operations/workspace_oauth_runbook.md`

### Exit criteria
- scope baseline minima completa attivabile e verificata;
- auth smoke pass su Gmail/Calendar/Drive/Docs/Sheets;
- zero token leakage in log.

---

## Fase 2 - Toolset enablement e segmentazione P9 (P1)

### Obiettivo
Rendere disponibili tutte le capability upstream mantenendo limite <=20 tool per sub-agente.

### Attivita
1. Disegnare toolset segmentati per intent/dominio (profili):
   - `workspace-mail`, `workspace-calendar`, `workspace-drive-docs`, `workspace-data`, `workspace-collab`, `workspace-admin-lite`.
2. Definire meccanismo di routing profilo dal conductor.
3. Aggiornare frontmatter agent/skill con allowlist esplicite.
4. Normalizzare naming tool in tutte le skill (`google_workspace_*`).
5. Generare inventory automatico upstream->local mapping con alert su drift.

### Deliverable
- aggiornamento `.aria/kilocode/agents/workspace-agent.md` (o split agent per profilo)
- catalogo allowlist per profilo
- script `scripts/workspace_tool_inventory.py`

### Exit criteria
- 100% tool upstream mappati a un profilo governato;
- nessun profilo supera 20 tool;
- routing deterministico documentato.

---

## Fase 3 - Skill pack completo e workflow production-grade (P1/P2)

### Obiettivo
Costruire libreria skill completa per usare operativamente tutta la superficie MCP.

### Attivita
1. Implementare skill pack a tranche:
   - Tranche A: Gmail, Calendar, Drive, Docs, Sheets
   - Tranche B: Slides, Forms, Chat, Tasks
   - Tranche C: Contacts, App Script, Custom Search
2. Per ogni skill:
   - read path e write path separati;
   - gate HITL esplicito per write;
   - fallback strategy + retry policy;
   - memory write policy (`actor=tool_output`).
3. Definire workflow canonici per use case produttivi e ricerca:
   - inbox command center;
   - meeting intelligence;
   - drive knowledge navigator;
   - docs/sheets/slides reporting factory;
   - forms intake + tasks dispatch;
   - chat ops digest;
   - contact enrichment;
   - appscript orchestration.

### Deliverable
- skill docs e prompt operativi in `.aria/kilocode/skills/*`
- mapping skill->tool->scope->HITL->testcase
- playbook `docs/operations/workspace_workflows.md`

### Exit criteria
- almeno 1 workflow production-grade per ciascun dominio upstream;
- 100% write path con HITL testato;
- test funzionali skill verdi.

---

## Fase 4 - Orchestrazione reale: scheduler/gateway/conductor (P1)

### Obiettivo
Eliminare il percorso stub e rendere i workflow workspace eseguibili in automazione reale.

### Attivita
1. Implementare execution path `workspace` nel runner scheduler.
2. Collegare task payload a sub-agent + skill + policy gate.
3. Definire idempotenza e retry semantics per task workspace.
4. Aggiungere task seed multi-dominio (non solo email triage).
5. Aggiornare test integrazione scheduler->agent->tool.

### Deliverable
- patch `src/aria/scheduler/runner.py`
- estensioni `scripts/seed_scheduler.py`
- test integration/e2e su task workspace

### Exit criteria
- `Scheduler workspace execution rate` = 100% non-stub;
- run outcome misurabili per dominio;
- nessun task write bypassa HITL.

---

## Fase 5 - Osservabilita, quality gates e compliance (P1/P2)

### Obiettivo
Rendere misurabile e auditabile il comportamento workspace end-to-end.

### Attivita
1. Telemetria tool-level:
   - `trace_id`, `tool_name`, `domain`, `latency`, `status`, `error_reason`, `retry_count`.
2. Reporting settimanale:
   - invoked vs enabled tools;
   - top error causes;
   - scope/HITL coverage.
3. Quality gate CI specifico workspace:
   - unit + integration + e2e selettive;
   - lint + typecheck + policy checks.
4. Drift detection:
   - nuove capability upstream non ancora governate.

### Deliverable
- dashboard/metriche in `docs/operations/telemetry.md`
- report generator `scripts/workspace_weekly_report.py`
- pipeline CI workspace

### Exit criteria
- KPI osservabili e storicizzati;
- audit trail completo per write ops;
- regressioni rilevate automaticamente.

---

## Fase 6 - Rollout professionale e hardening enterprise (P2/P3)

### Obiettivo
Portare la capability a standard operativo stabile per uso quotidiano produttivo.

### Attivita
1. Rollout progressivo per tranche (canary account -> primary account).
2. Test di resilienza:
   - quota pressure, auth invalidation, API errors, retry storms.
3. SLO/SLA definiti per domini prioritari (mail/calendar/drive/docs/sheets).
4. Runbook incident response workspace.
5. Go-live checklist e acceptance finale.

### Deliverable
- `docs/operations/workspace_incident_response.md`
- `docs/operations/workspace_slo_sla.md`
- report di readiness finale

### Exit criteria
- SLO rispettati in periodo di osservazione;
- nessun blocker P0/P1 aperto;
- sign-off tecnico e operativo.

---

## 6. Piano temporale indicativo (macro)

- Fase 0: 1 settimana
- Fase 1: 1 settimana
- Fase 2: 1-2 settimane
- Fase 3: 3-5 settimane (a tranche)
- Fase 4: 1-2 settimane
- Fase 5: 1-2 settimane
- Fase 6: 1-2 settimane

Durata totale stimata: 9-15 settimane, dipendente da disponibilita test account e complessita workflow cross-dominio.

---

## 7. KPI programma (globali)

1. `Upstream Governance Coverage` = tool governati / tool upstream totali (target 100%).
2. `Workflow Domain Coverage` = domini con >=1 workflow production-grade / domini totali (target 100%).
3. `Workspace Execution Rate` = run workspace non-stub / run workspace totali (target 100%).
4. `HITL Compliance` = write ops con HITL evidenziato / write ops totali (target 100%).
5. `Operational Success Rate` per tool call (target >=98%, esclusi errori permessi utente).
6. `Recovery Success` su 403/429/5xx via retry/backoff (target >=90%).
7. `Adoption Depth` = numero tool distinti invocati settimanalmente (target progressivo).

---

## 8. Rischi principali e mitigazioni

1. **Scope creep e frizione consenso**
   - mitigazione: incremental authorization + governance matrix + ADR escalation.
2. **Regressioni auth in refactor wrapper**
   - mitigazione: canary, test e2e auth, rollback plan.
3. **Violazione P9 con toolset troppo ampi**
   - mitigazione: segmentazione profili + validazione automatica.
4. **Drift upstream non governato**
   - mitigazione: inventory job periodico + alert.
5. **Task automation non idempotente**
   - mitigazione: policy gate, retry discipline, compensating actions.

---

## 9. Governance decisionale e milestone

Milestone di controllo (con gate di approvazione):

1. **M1 - Governance Baseline Ready** (fine Fase 0)
2. **M2 - Auth/Scope Professional Baseline** (fine Fase 1)
3. **M3 - Full Tool Governance + P9 Compliance** (fine Fase 2)
4. **M4 - Full Skill Pack Operational** (fine Fase 3)
5. **M5 - Real Automation (no stub)** (fine Fase 4)
6. **M6 - Observability & Compliance Green** (fine Fase 5)
7. **M7 - Production Readiness Sign-off** (fine Fase 6)

Ogni milestone richiede:
- evidenze test;
- checklist blueprint compliance;
- aggiornamento documentazione/ADR;
- stato KPI minimo della fase.

---

## 10. Output attesi per i futuri piani implementativi di fase

Da questa roadmap dovranno derivare piani di fase dettagliati con:

1. backlog atomico per fase (task tecnici, owner, effort, dipendenze);
2. prompt pack operativi per Codex/Claude/OpenCode/KiloCode;
3. test plan (unit/integration/e2e/security);
4. piano di rollout e rollback;
5. aggiornamenti docs e ADR obbligatorie.

---

## 11. Riferimenti

- `docs/analysis/workspace_enhancement_analysis.md`
- `docs/foundation/aria_foundation_blueprint.md`
- `docs/foundation/decisions/ADR-0003-oauth-security-posture.md`
- Context7: `/taylorwilsdon/google_workspace_mcp`
- Context7: `/openai/codex`
- Context7: `/anthropics/claude-code`
