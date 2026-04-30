# Piano di Miglioramento e Ottimizzazione MCP + Coordinamento Agenti

> **Data**: 2026-04-29  
> **Scope**: Search-Agent, Workspace-Agent, Productivity-Agent, orchestrazione Conductor, layer MCP  
> **Input**: segnalazione runtime su `scientific-papers-mcp` e `pubmed-mcp`, integrazione regole productivity-agent, coordinamento tra i tre agenti  
> **Vincoli**: `AGENTS.md`, blueprint ARIA, wiki-first, isolamento `.aria/*`, no azioni distruttive

---

## 1) Executive Summary

L’analisi della codebase evidenzia che il problema non è solo di affidabilità dei due MCP accademici, ma di **drift di esposizione tool** e **coordinamento incompleto tra agenti**:

1. `search-agent` dichiara policy tier con `pubmed` e `scientific_papers`, ma non espone i rispettivi tool in `allowed-tools` né in `mcp-dependencies`.
2. `aria-conductor` non elenca `productivity-agent` tra i sub-agenti disponibili nel prompt operativo.
3. `scientific-papers-wrapper.sh` usa patching cache-based fragile (`npx` cache mutation), con rischio di non determinismo tra ambienti/sessioni.
4. `pubmed-wrapper.sh` dipende da `bunx` per startup (ottimizzazione), ma introduce un punto di failure extra rispetto a `npx`/`uvx` fallback.
5. Manca una **matrice canonica di capability cross-agent** (chi può invocare cosa, con quali gate) sincronizzata tra config MCP, agent prompt e wiki.

Conseguenza: i provider possono risultare “presenti in config” ma **non realmente invocabili in modo robusto** nel flusso agentico end-to-end.

---

## 2) Evidenze Tecniche (as-is)

## 2.1 MCP config presente

Fonte: `.aria/kilocode/mcp.json` (2026-04-29)

- `pubmed-mcp`: enabled, wrapper dedicato
- `scientific-papers-mcp`: enabled, wrapper dedicato
- `reddit-search`, `markitdown-mcp`, `google_workspace` presenti

## 2.2 Drift search-agent ↔ policy

Fonte: `.aria/kilocode/agents/search-agent.md`

- La tabella tier include `pubmed` e `scientific_papers`.
- `allowed-tools` non include tool namespace per `pubmed-mcp/*` e `scientific-papers-mcp/*`.
- `mcp-dependencies` non include `pubmed-mcp` e `scientific-papers-mcp`.

Impatto: policy dichiarata ma non pienamente eseguibile in pratica.

## 2.3 Coordinamento conductor ↔ productivity

Fonte: `.aria/kilocode/agents/aria-conductor.md`

- Sezione “Sub-agenti disponibili” elenca solo `search-agent` e `workspace-agent`.
- `productivity-agent` esiste e ha definizione completa, ma non risulta incorporato nella lista operativa del conductor.

Impatto: decomposizione task non sistematica verso productivity workflows.

## 2.4 Rischi wrapper runtime

Fonti: `scripts/wrappers/pubmed-wrapper.sh`, `scripts/wrappers/scientific-papers-wrapper.sh`

- Scientific papers: patch su cache `npx` via copia file JS patched. Rischio drift/version mismatch, scarsa riproducibilità.
- PubMed: path veloce `bunx` senza fallback esplicito automatico se Bun non presente o incompatibile.

## 2.5 Policy di routing vs implementazione

Fonte: `src/aria/agents/search/router.py`

- Router include `Provider.PUBMED` e `Provider.SCIENTIFIC_PAPERS` e relativo tiering.
- Quindi la parte Python è allineata, ma la superficie tool dell’agente non è completamente coerente.

---

## 3) Obiettivi di Miglioramento (to-be)

1. **Ripristino affidabilità MCP accademici** con startup deterministico e probe di compatibilità.
2. **Allineamento completo config/prompt/runtime** (mcp.json ↔ agent definitions ↔ router ↔ wiki).
3. **Integrazione solida productivity-agent** nel ciclo decisionale del conductor.
4. **Coordinamento esplicito dei tre agenti** tramite protocollo di handoff e capability matrix.
5. **Osservabilità operativa** con health checks, schema snapshots e rollback gates per dominio.

---

## 4) Piano di Intervento (rollback-first)

## Fase A — Stabilizzazione immediata (P0)

1. **Search-Agent exposure fix**
   - Aggiungere a `allowed-tools` le entry `pubmed-mcp/*` e `scientific-papers-mcp/*` (tool specifici, non wildcard indiscriminata).
   - Aggiungere `pubmed-mcp` e `scientific-papers-mcp` in `mcp-dependencies`.
2. **Conductor agent registry fix**
   - Aggiornare `aria-conductor.md` includendo `productivity-agent` tra i sub-agenti disponibili e relative regole di dispatch.
3. **Wrapper hardening quick wins**
   - PubMed wrapper: fallback automatico `bunx -> npx` (o `uvx`) con log evento.
   - Scientific wrapper: fail-fast se patch seed manca/incompatibile, con messaggio diagnostico chiaro.

**Gate uscita Fase A**
- `search-agent` può invocare davvero `pubmed/scientific`.
- `conductor` può delegare esplicitamente a productivity-agent.
- Startup wrappers senza errori bloccanti nelle condizioni standard.

## Fase B — Refactor affidabilità MCP accademici (P1)

1. **Rimuovere dipendenza da patch cache mutabile** per scientific papers:
   - Opzione preferita: fork controllato interno del wrapper driver (senza toccare upstream ARIA core), versione pin + patch esplicita in repo.
   - In alternativa: script di patch idempotente con checksum/version guard + test di integrità.
2. **Capability probe all’avvio**
   - `initialize` + `tools/list` snapshot per `pubmed-mcp` e `scientific-papers-mcp`.
   - Quarantena server se mismatch critico.
3. **Query preprocessor centralizzato**
   - Consolidare regole query per academic intent in modulo unico con test dedicati.

**Gate uscita Fase B**
- Nessun comportamento dipendente da stato cache locale non tracciato.
- Snapshot tools/version disponibili e confrontabili.

## Fase C — Coordinamento formale tra i 3 agenti (P1)

1. **Capability Matrix canonica** (`docs/foundation/` + wiki mirror)
   - Colonne: Agent, Allowed Tools, MCP Dependencies, Delegation Targets, HITL Required.
2. **Protocollo handoff standardizzato**
   - Payload JSON minimo per `spawn-subagent`: `goal`, `constraints`, `required_output`, `timeout`, `trace_id`.
3. **Routing policy unificata**
   - Criteri chiari: quando conductor usa search-agent, workspace-agent, productivity-agent o chain combinata.

**Gate uscita Fase C**
- Nessuna ambiguità di ownership task.
- Handoff ripetibile e verificabile nei log.

## Fase D — Verifica, test e rollout (P0/P1)

1. **Test unit/integration aggiuntivi**
   - Search-agent config consistency tests (tier policy vs allowed-tools/mcp-dependencies).
   - Wrapper startup fallback tests (pubmed/scientific).
   - Conductor dispatch tests con productivity-agent incluso.
2. **Smoke E2E per intent academic**
   - Query benchmark su `pubmed` e `scientific_papers` con assert su fallback chain.
3. **Rollback drill**
   - Profili baseline/candidate: ritorno a baseline in <5 minuti con script documentato.

---

## 5) Backlog Operativo Prioritizzato

## P0 (questa settimana)

- [ ] Allineare `search-agent.md` (tools + dependencies) a policy academic.
- [ ] Allineare `aria-conductor.md` con `productivity-agent`.
- [ ] Fallback startup `pubmed-wrapper` + error telemetry.
- [ ] Hard fail diagnostico `scientific-papers-wrapper` su patch mismatch.

## P1 (sprint successivo)

- [ ] Capability probe + snapshot framework per MCP accademici.
- [ ] Stabilizzare patching scientific papers con versione pin/checksum.
- [ ] Capability matrix + protocollo handoff cross-agent.
- [ ] Suite test di coerenza configurativa e dispatch.

## P2 (ottimizzazione)

- [ ] Metriche startup/latency per dominio search.
- [ ] Valutazione gateway selettivo search (solo se dati giustificano).

---

## 6) KPI di Successo

1. **Academic MCP availability**: >99% startup success su sessioni locali standard.
2. **Routing correctness**: 100% test pass su matrix intent→provider chain.
3. **Agent coordination coverage**: 100% casi target con dispatch corretto conductor→(search/workspace/productivity).
4. **MTTR rollback**: <5 minuti per tornare a baseline profile.
5. **Drift incidents**: riduzione >80% entro 2 sprint.

---

## 7) Rischi e Mitigazioni

- **Rischio**: regressioni sui wrapper MCP accademici.  
  **Mitigazione**: profilo baseline sempre disponibile + rollback drill per release.

- **Rischio**: complessità eccessiva nella governance.  
  **Mitigazione**: YAGNI rigoroso, introdurre solo controlli che hanno KPI associato.

- **Rischio**: disallineamento documentazione/codice.  
  **Mitigazione**: gate CI “policy consistency” su agent files + mcp config + router.

---

## 8) Fonti e Provenienza

- `AGENTS.md` (vincoli operativi)
- `docs/llm_wiki/wiki/index.md`, `docs/llm_wiki/wiki/log.md`
- `docs/llm_wiki/wiki/mcp-architecture.md`
- `docs/llm_wiki/wiki/research-routing.md`
- `docs/llm_wiki/wiki/productivity-agent.md`
- `.aria/kilocode/mcp.json`
- `.aria/kilocode/agents/search-agent.md`
- `.aria/kilocode/agents/aria-conductor.md`
- `.aria/kilocode/agents/workspace-agent.md`
- `.aria/kilocode/agents/productivity-agent.md`
- `scripts/wrappers/pubmed-wrapper.sh`
- `scripts/wrappers/scientific-papers-wrapper.sh`
- `src/aria/agents/search/router.py`
- Context7:
  - `/cyanheads/pubmed-mcp-server`
  - `/benedict2310/scientific-papers-mcp`
  - `/modelcontextprotocol/modelcontextprotocol`
