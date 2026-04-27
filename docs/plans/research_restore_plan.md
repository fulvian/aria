# Research Routing Restore Plan

## 1. Obiettivo

Ripristinare una sequenza di ricerca deterministica che rispetti il principio
"provider gratuito prima" con fallback a tier consecutivi, evitando drift tra
skill markdown, blueprint, configurazione MCP e implementazione runtime.

## 2. Problema osservato

La query di ricerca non ha seguito la sequenza intelligente attesa. Il sistema
attuale espone provider multipli ma non garantisce in modo verificabile
l'ordine di tentativo e fallback per intent.

## 3. Evidenze raccolte (con provenienza)

1. Sequenza hardcoded nella skill (non necessariamente allineata al blueprint):
   - `.aria/kilocode/skills/deep-research/SKILL.md:26`
   - Ordine: `Tavily > Brave > Firecrawl > Exa`

2. Search-agent dichiara "rotation intelligente" ma senza policy eseguibile:
   - `.aria/kilocode/agents/search-agent.md:25-26`

3. Blueprint definisce routing intent-aware differente:
   - `docs/foundation/aria_foundation_blueprint.md:1362-1370`
   - Esempio `general`: `brave -> tavily`

4. Blueprint definisce anche fallback tree diverso (ulteriore divergenza):
   - `docs/foundation/aria_foundation_blueprint.md:1432-1434`
   - Esempio `news/general`: `Tavily -> Brave -> SearXNG`

5. Blueprint prevede router Python, ma in repository non risulta implementato:
   - Atteso: `src/aria/agents/search/router.py` (blueprint §11.2)
   - Presente: soli placeholder `__init__.py` in `src/aria/agents/search/`

6. Incoerenza tool/fallback:
   - SearXNG è previsto nel fallback blueprint ma non è consentito nella skill
     `deep-research` (`allowed-tools` non include `searxng-script/search`).
   - SerpAPI compare nel blueprint come fallback finale ma non è presente in
     `.aria/kilocode/mcp.json`.

7. I wrapper attuali sono solo bootstrap server (nessuna logica di tiering):
   - `scripts/wrappers/tavily-wrapper.sh`
   - `scripts/wrappers/firecrawl-wrapper.sh`
   - `scripts/wrappers/exa-wrapper.sh`
   - `scripts/wrappers/searxng-wrapper.sh`

8. Stato operativo recente: esistono failure provider legati a credenziali/quota,
   fattore che rompe l'ordine atteso se non governato da router con policy
   esplicita:
   - `docs/llm_wiki/wiki/log.md:29,65`

## 4. Root cause sintetica

1. **Drift di policy**: skill, blueprint (routing intent), blueprint (fallback
   degradation) non sono allineati.
2. **Mancanza di enforcement runtime**: il router previsto non è implementato;
   la sequenza resta solo "istruzione testuale" nel prompt skill.
3. **Mancanza test di conformità sequenza**: non ci sono test che blocchino
   regressioni sull'ordine provider.
4. **Mismatch inventario provider**: fallback documentati ma non disponibili o
   non autorizzati negli `allowed-tools`.

## 5. Policy target (da congelare come single source of truth)

### 5.1 Principio

- Prima usare provider a costo nullo o con miglior capacità gratuita residua.
- Avanzare su tier successivi in ordine **deterministico e consecutivo**.
- Ogni salto di tier deve essere motivato da stato esplicito (`down`,
  `credits_exhausted`, `circuit_open`, timeout).

### 5.2 Matrice proposta (MVP)

> Nota: questa matrice va approvata e poi riflessa identica in blueprint,
> skill e codice.

- `general/news`:
  1) `searxng` (se healthy)
  2) `brave`
  3) `tavily`
  4) `firecrawl` (solo enrich/scrape top URL)
  5) `exa` (fallback semantico)
- `academic`:
  1) `exa`
  2) `tavily`
  3) `brave`
  4) `searxng`
- `deep_scrape`:
  1) `firecrawl_extract`
  2) `firecrawl_scrape`
  3) `fetch` + parsing locale (degraded)

## 6. Piano di ripristino

## Phase 0 - Allineamento specifiche (bloccante)

1. Definire policy canonica di tiering (tabella unica) e criteri "free-first".
2. Allineare i riferimenti in:
   - `docs/foundation/aria_foundation_blueprint.md` (§9 e §11)
   - `.aria/kilocode/skills/deep-research/SKILL.md`
   - `.aria/kilocode/agents/search-agent.md`
3. Decidere definitivamente SerpAPI: integrare o rimuovere da blueprint.

**Acceptance**
- Esiste una sola policy coerente citata in tutte le fonti.

## Phase 1 - Implementazione router deterministico

1. Implementare `src/aria/agents/search/router.py` con ordine per intent.
2. Implementare/collegare moduli provider + health + budget state.
3. Enforcement sequenziale:
   - tentativo tier N
   - se fallisce con motivo classificato, passaggio a tier N+1
   - no salti non motivati

**Acceptance**
- Per ogni intent il trace mostra tentativi in ordine consecutivo previsto.

## Phase 2 - Convergenza tool inventory

1. Aggiornare `allowed-tools` della skill per includere tutti i fallback reali.
2. Allineare `.aria/kilocode/mcp.json` con policy approvata.
3. Verificare startup e disponibilità tool reali (`/tools list`).

**Acceptance**
- Nessun provider citato dalla policy risulta mancante in toolset runtime.

## Phase 3 - Test di conformità sequenza (bloccanti in CI)

1. Unit test router:
   - selezione intent
   - ordine provider
   - skip su stati down/exhausted/circuit open
2. Integration test fallback:
   - simulare errore su tier 1 e verificare passaggio a tier 2
   - simulare errori multipli e verificare progressione fino a degraded mode
3. Golden trace tests:
   - confronto ordine atteso vs ordine effettivo (event log)

**Acceptance**
- Test di conformità verdi e gate CI bloccante su regressione ordine.

## Phase 4 - Osservabilità e runbook operativo

1. Logging strutturato eventi:
   - `provider_attempted`, `provider_skipped`, `fallback_advanced`,
     `degraded_mode_entered`
2. Metriche:
   - `% query che raggiungono tier >1`
   - `% query in degraded mode`
   - `credits_exhausted incidents/provider`
3. Runbook `provider_exhaustion` aggiornato con troubleshooting sequenza.

**Acceptance**
- In incident review è possibile ricostruire facilmente perché è stato
  scelto un tier specifico.

## 7. Verification Matrix

1. `general`: provider tier 1 healthy -> usa tier 1, nessun fallback.
2. `general`: tier 1 quota exhausted -> passa a tier 2.
3. `general`: tier 1+2 down -> passa a tier 3.
4. `deep_scrape`: fallimento `extract` -> fallback `scrape`, poi degraded.
5. `academic`: ordine rispettato (`exa -> tavily -> brave -> searxng`).
6. Tutti provider indisponibili -> risposta `local-only/degraded` esplicita.

## 8. Rischi e mitigazioni

- **R1: ulteriore drift documentazione/codice**
  - Mitigazione: test golden + checklist di allineamento obbligatoria in PR.
- **R2: regressioni per rate-limit/quota variabile**
  - Mitigazione: health state + circuit breaker + budget-aware skip.
- **R3: complessità eccessiva in MVP**
  - Mitigazione: implementare solo policy base deterministic-first, senza
    euristiche avanzate non necessarie (YAGNI).

## 9. Deliverable

- `docs/plans/research_restore_plan.md` (questo piano)
- Policy canonica allineata tra blueprint, skill e agent
- Router implementato e testato con gate CI
- Runbook e metriche di fallback aggiornati

## 10. Exit criteria

Il ripristino è completato quando:

1. Ordine provider per intent è deterministicamente verificabile via test.
2. Nessuna query salta tier senza motivazione tracciata.
3. In presenza di fault, il fallback avanza in modo consecutivo fino a
   modalità degraded/local-only.
4. Blueprint, skill e configurazione runtime sono coerenti e senza drift.
