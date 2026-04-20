# ARIA Foundation Blueprint Audit

- Documento audit: `docs/foundation/aria_foundation_blueprint.md`
- Data audit: 2026-04-20
- Auditor: Kilo (technical audit)
- Obiettivo: valutare coerenza architetturale, fattibilita implementativa, allineamento a librerie e best practice aggiornate ad aprile 2026, e proporre azioni correttive con priorita.

---

## 1) Executive assessment

### Valutazione complessiva

**Esito: APPROVABILE CON MODIFICHE MIRATE (high-confidence).**

Il blueprint e architetturalmente solido, con principi molto forti su:
- isolamento operativo (P1),
- invariance rispetto a upstream (P2),
- privacy local-first (P4),
- memoria con provenienza esplicita (P5-P6),
- HITL sulle azioni rischiose (P7),
- governance anti-drift (P10).

Queste scelte sono robuste e in linea con pattern moderni di agentic systems.

### Aree critiche da correggere prima della build piena

1. **Drift versioni dipendenze** (FastMCP, Telegram, whisper stack) rispetto a stato 2026.
2. **Rischio SQLite WAL non esplicitamente mitigato** (bug WAL-reset risolto in SQLite >= 3.51.3).
3. **Hardening systemd migliorabile** (policy home/filesystem ancora ampia su alcuni punti).
4. **OAuth Google aggiornabile a PKCE secret-less** (coerente con release recenti `google_workspace_mcp`).
5. **Uso di default mutabili nei modelli Pydantic** da rifinire (best practice `default_factory`).
6. **Tier grafo con `networkx + pickle`**: rischio sicurezza/operabilita da ridurre.

---

## 2) Metodologia di audit

- Lettura completa del blueprint (sezioni 0-18, 1918 linee).
- Verifica incrociata con documentazione ufficiale aggiornata (aprile 2026) su:
  - MCP e FastMCP,
  - Python Telegram stack,
  - Google OAuth / best practices,
  - SQLite WAL/FTS5,
  - SOPS+age,
  - keyring,
  - Pydantic fields/defaults,
  - LanceDB.
- Classificazione rilievi: `APPROVE`, `WARNING`, `REJECT`.
- Prioritizzazione remediation: `P0` (bloccante), `P1` (alta), `P2` (media).

---

## 3) Sezione per sezione: valutazione critica

## 0. Front Matter & Policy

**Valutazione: APPROVE**

- Governance documentale molto matura: source-of-truth + ADR obbligatori + aggiornamento periodico.
- Buona separazione tra principi inderogabili e dettagli evolutivi.

**Suggerimento**
- Aggiungere una mini-sezione "compatibility window" (es. review tecnica ogni 30 giorni su dipendenze P0/P1).

---

## 1. Visione e Scope

**Valutazione: APPROVE**

- Scope MVP realistico e chiaro.
- Non-obiettivi ben definiti, riducono scope creep.

**Warning minore**
- Il caso d'uso "ricerca approfondita" dipende da provider con quote/costi variabili: va codificata una degradazione esplicita di qualita quando quote terminate.

---

## 2. Principi Architetturali Inderogabili

**Valutazione: APPROVE (forte)**

I principi P1-P10 sono coerenti con pratiche enterprise-grade per agent systems.

**Nota critica positiva**
- P5/P6 (actor-aware + verbatim preservation) sono un vantaggio differenziante su affidabilita memoria.

---

## 3. Architettura di Sistema

**Valutazione: APPROVE CON WARNING**

**Punti forti**
- Layering corretto (canali -> gateway -> conductor/sub-agents -> tool layer -> backend services -> persistence).
- Distinzione sincrono/asincrono ben modellata.

**Warning**
- `Exa` e `SearXNG` sono previsti come script/provider, ma non e definita chiaramente la politica di fallback in assenza totale di crediti API.

**Raccomandazione**
- Definire runbook "provider exhaustion" con soglie, fallback e messaging all'utente.

---

## 4. Isolamento dall'ambiente KiloCode globale

**Valutazione: APPROVE CON WARNING**

**Punti forti**
- Layout directory eccellente.
- Separazione `.aria/runtime` e credenziali molto chiara.

**Warning P1**
- `pyproject.toml` nel blueprint ha vincoli ormai datati su alcune librerie (vedi sezione 4 del presente audit).

**Warning P1 (service hardening)**
- Nel service template lo schema e buono, ma puo essere reso piu restrittivo su `ProtectHome` e altre guard rails.

---

## 5. Sottosistema di Memoria 5D

**Valutazione: APPROVE CON WARNING**

**Punti forti**
- Tassonomia 5D sensata.
- Invariante T0 immutabile e corretta.
- Distillazione asincrona con provenance preservation ottima.

**Warning P1 (schema Pydantic)**
- In esempio `EpisodicEntry` e `SemanticChunk` ci sono default mutabili (`[]`, `{}`) che vanno sostituiti con `default_factory` per robustezza e chiarezza manutentiva.

**Warning P1 (Tier 3 associativo)**
- `networkx pickled` espone rischi di sicurezza e scarsa portabilita/versioning (pickle non e formato robusto per persistenza long-term in sistemi con trust boundary non nullo).

**Raccomandazione**
- Per Fase 2, preferire un backend non-pickle (SQLite graph table o engine dedicato) con serializzazione sicura.

---

## 6. Scheduler & Autonomia

**Valutazione: APPROVE CON WARNING IMPORTANTE**

**Punti forti**
- Schema scheduler completo (tasks/runs/dlq/hitl_pending).
- Policy gate e budget gate sono ben disegnati.
- DLQ esplicita ottima.

**Warning P0 (SQLite WAL)**
- Il blueprint usa intensamente SQLite WAL ma non esplicita pinning versione minima SQLite patched per bug WAL-reset.

**Raccomandazioni**
- Richiedere `SQLite >= 3.51.3` (o backport ufficiali citati) in ambiente runtime.
- Formalizzare strategy checkpoint (`wal_autocheckpoint`, checkpoint manuali programmati, monitor WAL growth).

---

## 7. Gateway Esterno

**Valutazione: APPROVE**

**Punti forti**
- Session manager multi-utente isolato corretto.
- Whitelist Telegram + HMAC webhook allineati a baseline security.

**Warning P1**
- Per STT locale, `openai-whisper` e funzionale ma oggi meno efficiente di alternative moderne (`faster-whisper`/CTranslate2).

---

## 8. Gerarchia Agenti

**Valutazione: APPROVE (molto buona)**

- Regola orchestrator -> sub-agent -> skill -> tool e corretta.
- Boundaries per tool access ben impostati.
- Child sessions isolate: ottima scelta per contenimento contesto.

**Warning minore**
- Alcuni `mcp-dependencies` vanno riallineati (es. Search-Agent non dovrebbe dipendere da `google_workspace` se non lo usa direttamente).

---

## 9. Skills Layer

**Valutazione: APPROVE CON WARNING**

- Pattern progressive disclosure allineato a pratiche moderne.
- Registry e catalogazione skill adeguati.

**Warning P2**
- Definire versioning policy forte per skill (`semver` + compatibility matrix su tool signatures), altrimenti rischio drift funzionale.

---

## 10. Tools & MCP Ecosystem

**Valutazione: APPROVE CON WARNING IMPORTANTE**

**Punti forti**
- Tool Priority Ladder e ottimo anti-bloat pattern.
- `mcp.json` centralizzato e chiaro.

**Warning P1**
- `fastmcp>=0.3` nel blueprint e obsoleto rispetto stato 2026.
- Alcuni MCP wrapper dipendono da crediti esterni; senza fallback locale si rischiano failure cascata.

---

## 11. Sub-Agent di Ricerca Web

**Valutazione: APPROVE CON WARNING**

- Router intent-aware ben concepito.
- Circuit breaker per chiavi API e ottima pratica.

**Warning P1**
- Assunti economici/quote provider possono cambiare rapidamente.
- Necessario introdurre health-check runtime e policy di degradazione deterministiche.

---

## 12. Sub-Agent Google Workspace

**Valutazione: APPROVE CON MODIFICA CONSIGLIATA**

**Punti forti**
- Scopes minimi e principle of least privilege.
- Runtime token in keyring: corretto.

**Aggiornamento consigliato P1**
- Tenere esplicitamente conto del supporto recente a **secret-less PKCE** in `google_workspace_mcp` (v1.19.0), riducendo esposizione del client secret dove possibile.

---

## 13. Credential Management

**Valutazione: APPROVE CON WARNING**

**Punti forti**
- SOPS+age + keyring separa bene static secrets e OAuth runtime.
- Circuit breaker e audit trail per chiavi API molto buoni.

**Warning P1**
- `providers.enc.yaml` ad alta frequenza di scrittura non dovrebbe stare in git (rumore e rischio operativo). Meglio runtime-only + snapshot periodici firmati.

---

## 14. Governance & Osservabilita

**Valutazione: APPROVE CON WARNING**

**Punti forti**
- JSON structured logging + trace_id propagation: eccellente.
- Metriche principali ben selezionate.

**Warning P2**
- Esplicitare che endpoint metriche e bindato a localhost e protetto in caso di future esposizioni remote.

---

## 15. Roadmap

**Valutazione: APPROVE**

- Sequenza Foundation -> MVP -> Maturazione -> Scale e coerente.
- Deliverable sono verificabili.

**Suggerimento**
- Inserire quality gates quantitativi per uscita Fase 1 (SLO su latenza recall memoria, tasso DLQ, tasso HITL timeout).

---

## 16. Ten Commandments

**Valutazione: APPROVE (core invariants corretti)**

Nessuna modifica sostanziale consigliata.

---

## 17. Auto-aggiornamento blueprint

**Valutazione: APPROVE CON WARNING**

- Ottima idea il `blueprint-keeper`.

**Warning P2**
- Evitare PR automatiche troppo invasive: introdurre limite per batch e severity labels (`docs-only`, `breaking`, `security`).

---

## 18. Appendici

**Valutazione: APPROVE CON AGGIORNAMENTO FONTI**

- Struttura utile.
- Da aggiornare periodicamente le versioni di riferimento (MCP spec version date, library versions).

---

## 4) Verifica librerie/framework rispetto ad aprile 2026

## 4.1 Dipendenze principali: delta blueprint vs stato corrente

| Componente | Blueprint | Stato rilevato (apr 2026) | Valutazione | Azione |
|---|---:|---:|---|---|
| FastMCP | `>=0.3` | `3.2.4` (PyPI, 2026-04-14) | WARNING | Aggiornare constraint e testare API break |
| python-telegram-bot | `>=21.0` | `v22.7` docs stabili | APPROVE/WARNING | Alzare lower-bound a serie 22 |
| google_workspace_mcp | `v1.19.0+` citato | `v1.19.0` latest release (2026-04-15) | APPROVE | Confermare pin minimo 1.19.0 |
| openai-whisper | `>=20231117` | latest repo release `v20250625` | WARNING | Aggiornare o valutare sostituzione runtime |
| faster-whisper | non previsto come primario | attivo e maturo (`v1.2.1`, benchmark dichiarati) | WARNING | Considerare default STT locale |
| LanceDB | `>=0.4` | PyPI mostra ramo `0.30.x` | WARNING | Aggiornare vincolo minimo |
| keyring | `>=24.0` | docs 25.x | APPROVE | Facoltativo bump |

---

## 4.2 Note tecniche per componente

### FastMCP
- La differenza `0.3 -> 3.x` e sostanziale (major evolution).
- Il blueprint deve evitare range troppo aperti senza upper guard su major.

**Raccomandazione**
- Pin iniziale: `fastmcp>=3.2,<4.0` + smoke test su `remember/recall` server.

### Telegram stack
- PTB conferma API asincrone mature e supporto Python 3.10+.
- Blueprint e concettualmente allineato.

**Raccomandazione**
- Allineare docs interne al pattern `Application` async nativo PTB v22.

### Google Workspace MCP + OAuth
- Versione 1.19.0 include estensioni security (anche PKCE secret-less).
- Best practice Google: scope incrementali in contesto feature, token storage sicuro, gestione revoca/expiry.

**Raccomandazione**
- Rendere PKCE il default dove possibile; client secret solo quando realmente necessario.

### SQLite (WAL + FTS5)
- Blueprint centra bene WAL+FTS5, ma manca hard requirement su versione sicura.
- Documentazione SQLite segnala WAL-reset bug corretto in 3.51.3.

**Raccomandazione**
- Imporre versione minima SQLite patched e policy checkpoint monitorata.

### Whisper stack
- `openai-whisper` resta valido ma puo essere costoso in CPU deployment.
- `faster-whisper` dichiara migliori tradeoff speed/memory e non richiede ffmpeg di sistema (PyAV bundled).

**Raccomandazione**
- Tenere `openai-whisper` come fallback, introdurre `faster-whisper` come default locale in MVP se target e macchina locale.

### Pydantic schema hygiene
- I default mutabili nei modelli sono supportati ma non best practice manutentiva.

**Raccomandazione**
- Usare sempre `Field(default_factory=list)` / `Field(default_factory=dict)`.

---

## 5) Pattern e best practice: confronto con blueprint

## Gia allineato (promosso)

- **Least privilege** su scope Workspace.
- **Human approval gates** su azioni distruttive/non idempotenti.
- **Context provenance** nella memoria.
- **Layering orchestrativo** con tool scoping.
- **Documented governance** via ADR.

## Da potenziare

1. **Dependency governance**: introdurre lock/constraints piu stretti e policy di aggiornamento semestrale.
2. **SQLite operational hardening**: checkpoint strategy, WAL growth alarms, version floor.
3. **systemd hardening**: ridurre superfici con direttive aggiuntive per servizi non privilegiati.
4. **Provider exhaustion strategy**: fallback deterministici e UX esplicita su degrado qualita.
5. **Graph persistence safety**: no pickle per persistenza a lungo termine.

---

## 6) Risk register (prioritizzato)

| ID | Rischio | Prob. | Impatto | Priorita | Mitigazione |
|---|---|---|---|---|---|
| R1 | Drift dipendenze critiche (FastMCP/LanceDB/Whisper) | Alta | Alta | P0 | Pin versioni + CI compatibility matrix |
| R2 | Corruzione/instabilita WAL in runtime non patchato | Media | Alta | P0 | Enforce SQLite >= 3.51.3 + checkpoint policy |
| R3 | OAuth config non minimizzata (client secret non necessario) | Media | Alta | P1 | PKCE first, secret only when mandatory |
| R4 | Persistenza grafo via pickle | Media | Media-Alta | P1 | Storage sicuro non pickle |
| R5 | Fallimento provider web per quote/crediti | Alta | Media | P1 | Fallback tree + graceful degradation |
| R6 | Eccessiva permissivita filesystem service | Bassa-Media | Media | P2 | Hardening systemd incrementale |

---

## 7) Decisione finale e raccomandazioni operative

## Decisione

**Blueprint promosso con remediation obbligatorie prima del freeze implementativo Fase 1.**

## Remediation minime obbligatorie (prima di Sprint 1.1 pieno)

1. Aggiornare e pinare dipendenze critiche (`fastmcp`, `lancedb`, STT stack, PTB floor).
2. Introdurre baseline SQLite sicura e policy checkpoint esplicita in blueprint.
3. Adottare `default_factory` nei modelli Pydantic del blueprint.
4. Formalizzare strategy OAuth PKCE-first per Google Workspace.
5. Definire ADR su storage Tier 3 (evitare pickle per persistenza autorevole).

## Remediation consigliate (entro Fase 1)

1. Hardening systemd addizionale per scheduler/gateway.
2. Runbook "provider exhausted" + fallback deterministico.
3. Metriche SLO/SLI esplicite per uscita MVP.

---

## 8) Proposte ADR immediate

- **ADR-0001**: Dependency Baseline 2026Q2 (FastMCP 3.x, PTB 22.x, LanceDB 0.30.x, STT dual stack).
- **ADR-0002**: SQLite Reliability Policy (version floor + WAL/checkpoint + backup cadence).
- **ADR-0003**: OAuth Security Posture (PKCE-first, secret minimization, scope escalation in-context).
- **ADR-0004**: Associative Memory Persistence Format (no pickle for canonical storage).

---

## 9) Fonti e riferimenti (ufficiali)

### Protocollo/MCP
- MCP Specification (2025-11-25): https://modelcontextprotocol.io/specification/2025-11-25

### FastMCP
- FastMCP docs (installation/versioning): https://gofastmcp.com/getting-started/installation
- FastMCP PyPI (latest/release history): https://pypi.org/project/fastmcp/

### Telegram
- python-telegram-bot docs (v22.7): https://docs.python-telegram-bot.org/

### Google OAuth e Workspace
- OAuth best practices: https://developers.google.com/identity/protocols/oauth2/resources/best-practices
- OAuth 2.0 overview + refresh token expiration cases: https://developers.google.com/identity/protocols/oauth2
- google_workspace_mcp releases (latest v1.19.0): https://github.com/taylorwilsdon/google_workspace_mcp/releases

### SQLite
- WAL docs (including WAL-reset bug note/fix): https://www.sqlite.org/wal.html
- FTS5 extension docs: https://www.sqlite.org/fts5.html

### Secrets/Credential stack
- SOPS docs: https://getsops.io/docs/
- age project/format: https://github.com/FiloSottile/age
- Python keyring docs: https://keyring.readthedocs.io/en/latest/

### Data/validation layer
- LanceDB docs: https://docs.lancedb.com
- LanceDB PyPI (version lineage): https://pypi.org/project/lancedb/
- Pydantic fields/defaults/mutable defaults: https://docs.pydantic.dev/latest/concepts/fields/

### STT stack
- OpenAI Whisper repo/releases: https://github.com/openai/whisper
- faster-whisper repo/benchmarks: https://github.com/SYSTRAN/faster-whisper

### systemd hardening reference mirror
- systemd.exec man page (Debian manpages mirror): https://manpages.debian.org/unstable/systemd/systemd.exec.5.en.html

---

## 10) Esito sintetico per passaggio a agente di coding

- Stato blueprint: **solido e implementabile**.
- Condizione per green-light engineering: **chiudere 5 remediation obbligatorie** (sezione 7).
- Dopo remediation: blueprint idoneo come base prescrittiva per Phase 1 MVP.
