# Protocollo di creazione agenti ARIA

**Versione**: 1.0.0  
**Stato**: active  
**Creato**: 2026-05-01  
**Owner**: fulvio  
**Fonti autoritative**: `AGENTS.md`, `docs/foundation/aria_foundation_blueprint.md`, `docs/foundation/agent-capability-matrix.md`, `docs/foundation/decisions/ADR-0008-productivity-agent-introduction.md`, `docs/foundation/decisions/ADR-0015-fastmcp-native-proxy.md`, `docs/llm_wiki/wiki/index.md`, `docs/llm_wiki/wiki/log.md`, `docs/llm_wiki/wiki/mcp-proxy.md`, `docs/llm_wiki/wiki/mcp-architecture.md`, `docs/llm_wiki/wiki/agent-capability-matrix.md`, `docs/llm_wiki/wiki/productivity-agent.md`

---

## 1. Scopo

Questo protocollo è la **procedura unica di riferimento** per trasformare un'idea
utente in:

1. analisi strutturata del bisogno;
2. ricerca tecnica e architetturale;
3. decisione su riuso vs nuova capability;
4. piano completo di implementazione;
5. salvataggio del piano in `docs/plans/agents/`.

Il protocollo è obbligatorio per:
- nuovi sub-agenti ARIA;
- estensioni sostanziali di sub-agenti esistenti;
- nuove skill di dominio;
- nuovi MCP/tool Python locali collegati a un nuovo agente.

---

## 2. Principi inderogabili

Questo protocollo eredita integralmente `AGENTS.md` e il blueprint. In caso di
conflitto, prevale il blueprint.

### 2.1 Invarianti architetturali
- **P1 Isolation First**: nessuna contaminazione con il KiloCode globale.
- **P2 Upstream Invariance**: non si modifica KiloCode upstream; si lavora via
  config, prompt, MCP, wrapper Python locali.
- **P4 Local-first / privacy-first**: dati, memoria, credenziali e ricerca interna
  devono restare locali salvo necessità esplicita di provider esterni.
- **P5 Actor-aware memory**: nessuna inferenza diventa fatto senza provenienza.
- **P7 HITL obbligatorio**: ogni write/distruttiva/costosa/esterna non idempotente
  deve avere gate reale.
- **P8 Tool Priority Ladder**: MCP esistente → skill → tool Python locale.
- **P9 Scoped Active Capabilities**: massimo 20 capability attive per task/sessione;
  sharing ammesso solo con policy, `_caller_id`, least privilege, audit e HITL.
- **P10 Self-documenting evolution**: ogni divergenza significativa richiede ADR
  e aggiornamento wiki.

### 2.2 Lezioni obbligatorie dal ciclo proxy v6.3
Ogni nuovo agente deve prevenire esplicitamente i seguenti failure mode:
- **runtime/source-of-truth drift** tra file live, template e documentazione;
- **host-native tool drift** (`Glob`, `Read`, `Write`, ecc.) quando esiste un path
  MCP/proxy canonico;
- **pseudo-HITL** testuale al posto di un gate reale;
- **duplicate wiki updates** o payload schema-invalid;
- **self-remediation leakage**: durante normali workflow utente gli agenti non
  devono editare codice, config, né killare processi.

---

## 3. Quando usare questo protocollo

Usare questo protocollo quando l'utente chiede:
- un nuovo agente di dominio;
- un ampliamento di scope di un agente esistente;
- nuove automazioni che attraversano memoria, proxy MCP, skill e servizi backend;
- una nuova superficie tool che modifica i confini tra conductor e sub-agenti.

**Non usare** questo protocollo per:
- micro-fix di prompt o bug localizzati;
- sola aggiunta di una regola in skill esistente;
- sola documentazione senza impatto architetturale.

---

## 4. Workflow canonico

## Fase A — Intake dell'idea

### Obiettivo
Tradurre l'idea utente in un problema delimitato.

### Output obbligatorio
- nome provvisorio dell'iniziativa;
- descrizione del workflow utente target;
- outcome osservabile desiderato;
- non-obiettivi espliciti;
- categoria:
  - nuovo sub-agente,
  - estensione agente esistente,
  - sola skill,
  - sola esposizione capability,
  - tool Python locale/MCP.

### Regole
- non si inizia da una soluzione tecnica;
- non si assume che serva un nuovo agente;
- se il bisogno è copribile da `search-agent` o `productivity-agent`, va provato
  prima di proporre un nuovo agente.

---

## Fase B — Ricostruzione delle fonti di verità

### Obiettivo
Recuperare il contesto reale del sistema prima della ricerca.

### Letture obbligatorie
1. `docs/llm_wiki/wiki/index.md`
2. `docs/llm_wiki/wiki/log.md`
3. pagine wiki rilevanti, tra cui almeno dove pertinenti:
   - `mcp-proxy.md`
   - `mcp-architecture.md`
   - `agent-capability-matrix.md`
   - `productivity-agent.md`
   - `memory-v3.md`
   - `observability.md`
   - `research-routing.md`
4. `AGENTS.md`
5. `docs/foundation/aria_foundation_blueprint.md`
6. ADR pertinenti

### Regole
- la wiki si legge **prima** delle fonti raw;
- ogni contraddizione doc/runtime si registra come **drift blocking issue**;
- file canonici e file runtime vanno verificati come bersagli separati.

---

## Fase C — Analisi di fit e boundary

### Obiettivo
Stabilire se il nuovo bisogno giustifica davvero un nuovo agente.

### Domande obbligatorie
1. Il bisogno può restare dentro un agente esistente?
2. Può essere coperto da una skill aggiuntiva?
3. Può essere ottenuto solo ampliando la capability matrix?
4. Il dominio è davvero distinto da `search-agent` o `productivity-agent`?
5. La proposta aumenta o riduce hop, complessità, rischio e carico HITL?

### Hard rule
Un nuovo sub-agente si approva solo se il dominio è **autonomo e coerente**, non
per nascondere debolezze di prompt o routing di agenti esistenti.

---

## Fase D — Ricerca tecnica e di ecosistema

### Obiettivo
Capire cosa esiste già internamente ed esternamente.

### Input di ricerca obbligatori
- analisi repository + wiki;
- capability matrix attuale;
- superficie proxy/catalog attuale;
- ADR storici;
- eventuale analisi di MCP/tool esterni maturi.

### Strumenti ammessi
- wiki/repo analysis;
- `github-discovery` per cercare MCP o repo maturi;
- Context7 per documentazione ufficiale di librerie/SDK da usare;
- ricerca manuale via ARIA, se serve approfondimento esplorativo.

### Regole di ricerca
- i claim esterni non diventano ipotesi di progetto finché non sono verificati;
- la ricerca deve produrre evidenze su:
  - riuso interno possibile;
  - MCP maturi già disponibili;
  - skill componibili;
  - gap reali che richiedono nuova capability.

---

## Fase E — Branch di ricerca manuale via ARIA

Quando la ricerca richiede valutazioni qualitative o esplorative che l'utente
preferisce eseguire manualmente in ARIA, il protocollo deve generare prompt pronti.

### Regola
L'assistente che prepara il protocollo **non esegue** automaticamente questa fase:
prepara invece prompt per l'utente, che eseguirà ARIA manualmente e riporterà le
risposte come evidenza di ricerca.

### Formato obbligatorio dei prompt manuali
Ogni prompt deve contenere:
- obiettivo della ricerca;
- vincoli;
- formato di output richiesto;
- divieto di implementare o modificare codice;
- richiesta di evidenze, fonti e limiti.

### Template 1 — Ricerca di fattibilità architetturale
```text
Analizza questa idea per ARIA: <idea>.

Obiettivo:
- capire se serve un nuovo sub-agente, una nuova skill, un ampliamento di agente esistente o solo una nuova capability/tool.

Vincoli:
- non modificare codice
- non proporre implementazione prematura
- confronta esplicitamente con search-agent, productivity-agent, proxy MCP, capability matrix, wiki.db
- evidenzia riuso interno prima di proporre nuove dipendenze

Output richiesto:
1. problema reale da risolvere
2. opzioni architetturali
3. riuso possibile interno
4. gap reali
5. raccomandazione motivata
6. rischi
```

### Template 2 — Ricerca ecosistema MCP/tool
```text
Fai una ricerca comparativa per ARIA su questa capability: <capability>.

Valuta in ordine:
1. MCP esistenti maturi
2. skill componibili con tool già presenti
3. necessità eventuale di tool Python locale

Per ogni opzione dammi:
- maturità
- maintenance burden
- compliance con proxy MCP e _caller_id
- impatto su capability matrix
- impatto su HITL
- rischi di drift o lock-in
- raccomandazione finale

Non implementare nulla.
```

### Uso delle risposte manuali
Le risposte manuali di ARIA:
- sono **input di ricerca**, non verità finale;
- vanno ricontrollate contro repo, wiki, blueprint e ADR;
- devono essere citate con provenienza nel piano finale.

---

## Fase F — Tool decision ladder (P8 hard gate)

Questa fase è obbligatoria e sequenziale.

### Ordine vincolante
1. **Riuso di MCP esistente maturo**
2. **Nuova skill che compone tool esistenti**
3. **Tool Python locale** solo se le due precedenti falliscono

### Divieti
- vietato aggiungere un tool Python locale se un MCP maturo copre il caso;
- vietato aggiungere un nuovo MCP se una skill composta basta;
- vietato creare un nuovo agente per un semplice problema di prompt.

### Se si arriva a tool Python locale
Il piano deve includere:
- motivazione per cui MCP/skill non bastano;
- interfaccia dati esplicita;
- isolamento locale;
- piano di promozione a MCP/proxy-compatible entro 2 sprint.

---

## Fase G — Progettazione boundary, proxy e capability model

### Obiettivo
Assicurare compatibilità con il sistema proxy e con la policy runtime.

### Regole obbligatorie
- l'accesso operativo ai backend deve passare da `aria-mcp-proxy`, salvo tool
  intenzionalmente diretti come memoria;
- il nuovo agente deve poter lavorare con `search_tools` → `call_tool`;
- tutte le chiamate routed devono essere compatibili con `_caller_id`;
- le capability devono essere esprimibili nella capability matrix;
- il naming logico deve essere `server__tool`.

### Checklist di boundary
- Il nuovo agente è:
  - domain-primary,
  - compatibility-only,
  - transitional,
  - internal/system-only?
- quali capability read ha?
- quali capability write ha?
- quali capability richiedono HITL?
- quali capability può condividere con altri agenti secondo P9?

### Regola conductor
Il conductor **non** deve fare lavoro operativo diretto per compensare il nuovo
agente. Se il design richiede questo, il design è sbagliato.

---

## Fase H — Memoria, provenance e wiki.db

### Obiettivo
Garantire compatibilità con il modello `wiki.db` e con la memoria 5D.

### Regole obbligatorie
- non introdurre dual-write non governate;
- distinguere chiaramente tra:
  - raw/verbatim,
  - distillato,
  - inferenza;
- rispettare `actor-aware tagging`;
- non promuovere inferenze a fatti senza fonte.

### Il piano deve dichiarare
- quali page kind tocca il nuovo agente;
- quando fa `wiki_recall`;
- quando fa `wiki_update`;
- quali patch sono ammesse;
- quali informazioni **non** devono essere salvate automaticamente.

### Regola anti-drift memoria
- **una sola** `wiki_update_tool` per turn/change-set significativo;
- niente retry multipli con schema errato;
- niente memorializzazione di percorsi architetturalmente invalidi.

---

## Fase I — HITL, sicurezza e comportamento in workflow utente

### Regole hard
- conferma testuale ≠ HITL;
- ogni operazione distruttiva/costosa/esterna non idempotente richiede gate reale;
- il piano deve elencare tutte le azioni side-effectful e il loro gate;
- durante workflow utente ordinari è vietato:
  - editare codice,
  - editare config,
  - killare processi,
  - fare auto-remediation runtime.

### Se emerge un bug durante un workflow utente
Il nuovo agente deve:
1. fermarsi;
2. descrivere l'anomalia;
3. non correggere il sistema live;
4. demandare la correzione a un workflow di manutenzione separato.

---

## Fase J — Osservabilità, drift prevention e testabilità

### Osservabilità minima obbligatoria
- `trace_id` end-to-end;
- log JSON strutturati;
- eventi tool/agent/HITL;
- outcome misurabili.

### Anti-drift obbligatori
Il piano deve prevedere test o controlli per:
- source-of-truth drift;
- host-native tool drift;
- pseudo-HITL drift;
- duplicate wiki updates;
- self-remediation leakage.

### Test strategy minima obbligatoria
- unit test di prompt/policy contract;
- test capability matrix / proxy enforcement;
- test handoff/spawn depth;
- test HITL path;
- test failure/degraded mode;
- test runtime-vs-source alignment per prompt/template se applicabile.

Se un comportamento chiave non è testabile, non può essere approvato come core
workflow.

---

## Fase K — Redazione del piano di implementazione

### Output obbligatorio
Un file Markdown in `docs/plans/agents/`.

### Naming obbligatorio
Usare uno di questi schemi:
- `docs/plans/agents/<agent_slug>_foundation_plan.md`
- `docs/plans/agents/<agent_slug>_extension_plan.md`
- `docs/plans/agents/<agent_slug>_research_plan.md`

### Struttura minima del piano
1. Frontmatter / status / owner / date
2. Problema e obiettivi
3. Fonti e ricerca svolta
4. Decision ladder outcome (MCP vs skill vs Python)
5. Boundary e architettura target
6. Proxy / `_caller_id` / capability matrix implications
7. Memory and wiki.db implications
8. HITL map
9. Osservabilità e logging
10. Test plan
11. Rollback / degraded mode
12. ADR richiesti
13. Wiki update richiesti
14. Phased implementation steps
15. Explicit out-of-scope

### Regola
Il piano è il **gate package** per l'implementazione, non l'approvazione automatica.

---

## Fase L — ADR e aggiornamento wiki

### ADR obbligatorio se cambia uno di questi punti
- boundary agenti;
- interpretazione di P8/P9;
- modello proxy/enforcement;
- HITL policy;
- modello memoria;
- osservabilità;
- runtime architecture.

### Wiki obbligatoria
Per ogni nuova iniziativa approvata il protocollo deve richiedere:
- aggiornamento pagina wiki rilevante o creazione nuova pagina;
- aggiornamento `docs/llm_wiki/wiki/index.md`;
- append timestampato in `docs/llm_wiki/wiki/log.md`;
- provenienza con path e data.

---

## 5. Hard gates prima dell'implementazione

L'implementazione **non può iniziare** finché tutti i gate non sono verdi.

- [ ] idea utente tradotta in problema delimitato e non-obiettivi;
- [ ] ricostruzione wiki-first completata;
- [ ] nessun drift doc/runtime bloccante aperto;
- [ ] analisi riuso interno completata;
- [ ] P8 ladder giustificata in ordine;
- [ ] P9 rispettato con capability budget e scoping;
- [ ] compatibilità proxy e `_caller_id` dimostrata;
- [ ] impatti su `wiki.db` / actor-aware memory definiti;
- [ ] HITL reale mappata per tutte le side-effect operations;
- [ ] nessuna auto-remediation prevista durante workflow utente;
- [ ] osservabilità e test strategy definite;
- [ ] rollback/degraded mode documentati;
- [ ] lista ADR/wiki updates definita;
- [ ] file piano creato in `docs/plans/agents/`.

---

## 6. Template sintetico di esecuzione del protocollo

```text
Input utente
→ Intake e scope
→ Wiki-first reconstruction
→ Fit & boundary analysis
→ Ricerca repo + capability matrix + proxy surface
→ Eventuale github-discovery / ricerca manuale via ARIA
→ Decision ladder P8
→ Boundary/proxy/memory/HITL/test design
→ Draft piano in docs/plans/agents/
→ Lista ADR/wiki updates richiesti
→ Gate approval
→ Solo dopo: implementazione
```

---

## 7. Output finale del protocollo

Ogni esecuzione corretta di questo protocollo deve lasciare:
1. un piano Markdown in `docs/plans/agents/`;
2. una decisione esplicita su riuso vs nuovo agente;
3. una lista chiara di ADR e wiki update richiesti;
4. una base verificabile per implementare senza deriva architetturale.
