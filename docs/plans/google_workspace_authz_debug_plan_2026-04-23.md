# Piano di Debugging Esteso — Autenticazione/Autorizzazione Google Workspace MCP (Read Drive/Slides)

## 1) Obiettivo operativo

Sbloccare in modo stabile le operazioni di **lettura file Google Drive/Slides** (es. `search_drive_files`, `get_drive_file_content`) evitando i loop di ri-autenticazione e i falsi negativi di autorizzazione nel server MCP `workspace-mcp` integrato in ARIA.

## 2) Sintomi osservati (dalla sessione riportata)

### Comportamento
- Chiamata tool `google_workspace_search_drive_files` fallisce con:
  - `ACTION REQUIRED: Google Authentication Needed for Google Drive for 'fulviold@gmail.com'`
  - URL OAuth di consenso e istruzione a rifare il comando.

### Indicatori importanti
- L'URL di consenso richiede un set scope **molto ampio** (Gmail, Calendar, Drive, Docs, Sheets, Slides, Chat, Tasks, Contacts, ecc.), non solo i soli scope di lettura Drive/Slides.
- La richiesta utente era read-only (ricerca + lettura contenuto), ma la negoziazione OAuth è da profilo quasi completo.

## 3) Evidenze tecniche locali già verificate

### Wrapper + runtime credentials
- File wrapper: `scripts/wrappers/google-workspace-wrapper.sh`
  - legge refresh token da keyring (`KeyringStore`).
  - crea runtime credentials in `.aria/runtime/credentials/google_workspace_mcp/<email>.json`.
  - espone `GOOGLE_MCP_CREDENTIALS_DIR` e forza `MCP_ENABLE_OAUTH21=false`.
- Presenza token in keyring verificata (`present`).
- Runtime credentials file presente per `fulviold@gmail.com`.

### Stato scope runtime ARIA
- Scope file: `.aria/runtime/credentials/google_workspace_scopes_primary.json`
  - include scope read base, ma non il set esteso completo di tool abilitati upstream.
- Runtime cred include anche `presentations.readonly` via scope-floor wrapper.

### Verifica upstream (codice ufficiale)
- Upstream `auth/google_auth.py` (`taylorwilsdon/google_workspace_mcp`) conferma:
  - priorita directory credenziali: `WORKSPACE_MCP_CREDENTIALS_DIR` (preferred), fallback `GOOGLE_MCP_CREDENTIALS_DIR` (compat).
  - messaggio `ACTION REQUIRED: Google Authentication Needed ...` viene emesso quando non ci sono credenziali valide/coerenti per `required_scopes` correnti.
  - in modalita non single-user, mismatch tra `session_user` e `user_google_email` puo bypassare cache sessione e forzare lookup/re-auth.

## 4) Ipotesi root-cause (ordinate per probabilita)

### H1 (Alta): Scope richiesti dal server > scope realmente concessi
Il server viene avviato senza restringere il perimetro tool (di fatto "all tools"), quindi il suo `required_scopes` e molto esteso. Con credenziali ottenute solo su scope parziali/read, `has_required_scopes(...)` fallisce e parte il flow OAuth ogni volta.

**Perche e coerente con i sintomi:** l'URL di auth contiene scope enormi non necessari alla singola operazione di Drive read.

### H2 (Media): Drift sessione utente (`user_google_email`) e mapping OAuth runtime
Con `MCP_ENABLE_OAUTH21=false` + stdio, se session mapping e email richiesta divergono o non sono persistiti correttamente, il server non riusa la sessione e rientra in auth bootstrap.

### H3 (Media-Bassa): Callback OAuth non finalizzato correttamente
L'utente autorizza nel browser ma callback/consumo stato non completa in processo MCP attivo (es. flusso interrotto, state non consumato, account mismatch). Risultato: nessuna credenziale valida salvata per la sessione richiesta.

### H4 (Bassa): Incoerenza metadati scope ARIA vs granted scopes reali Google
Il wrapper puo scrivere scope "attesi" nel JSON runtime, ma il server usa i `granted_scopes` effettivi in credenziale; se parziali, il controllo scope continua a fallire.

## 5) Strategia di debug (a imbuto, con gate)

## Fase A — Riproduzione deterministica e raccolta prove

1. Avvio server in modalita controllata (stesso wrapper) e cattura log auth lato MCP.
2. Esecuzione test call minima: `search_drive_files` con `user_google_email` fissato.
3. Persistenza artefatti:
   - risposta tool completa,
   - log server auth,
   - snapshot credenziali runtime (redatte),
   - scope richiesti correnti lato server.

**Output atteso:** conferma oggettiva di quale condizione scatena `ACTION REQUIRED`.

## Fase B — Verifica mismatch scope richiesti/concessi (test principale)

1. Avviare server con profilo ridotto solo read Drive/Slides:
   - opzione 1: `--permissions drive:readonly`
   - opzione 2: `--tools drive slides --read-only`
2. Ripetere stessa chiamata `search_drive_files`.
3. Confrontare comportamento con avvio default (all tools).

**Criterio diagnostico:**
- Se in profilo ridotto l'errore sparisce, H1 e confermata.
- Se persiste uguale, investigare H2/H3.

## Fase C — Verifica mapping identita e sessione

1. Validare coerenza tra:
   - `user_google_email` passato nel tool,
   - email in `.aria/runtime/credentials/google_workspace_user_email.txt`,
   - email identificata dal callback OAuth,
   - eventuale user associato a sessione MCP.
2. Eseguire test con e senza `user_google_email` esplicito.
3. Eseguire test in `--single-user` per bypassare session mapping.

**Criterio diagnostico:**
- Se `--single-user` risolve stabilmente, problema su layer mapping session/user (H2).

## Fase D — Verifica callback OAuth end-to-end

1. Forzare nuova auth da stato pulito controllato (senza revoche distruttive globali).
2. Completare callback e verificare immediatamente:
   - credenziale salvata,
   - refresh token presente,
   - granted scopes effettivi,
   - riuso credenziale alla call successiva.

**Criterio diagnostico:**
- Se callback non popola stato/credenziali in modo riusabile, H3 confermata.

## Fase E — Allineamento configurazione ARIA

In base all'esito A-D:
- impostare il profilo avvio MCP workspace coerente col caso d'uso (`read-core` o `permissions` granulari),
- evitare che richieste read attivino scope pack "complete",
- introdurre controllo preflight che blocca startup incoerente (toolset vs scope policy) con errore esplicito e non con prompt OAuth tardivo.

## 6) Test matrix proposta

| ID | Modalita avvio | Input tool | Atteso |
|----|----------------|-----------|--------|
| T1 | default (all tools) | `search_drive_files` + email | probabile re-auth (baseline) |
| T2 | `--tools drive slides --read-only` | stesso input | no re-auth, risultati file |
| T3 | `--permissions drive:readonly` | stesso input | no re-auth |
| T4 | default + senza `user_google_email` | stesso query | capire binding automatico account |
| T5 | `--single-user` + email coerente | stesso input | no loop auth se mapping era la causa |
| T6 | post-auth retry immediato stessa sessione | stesso input | riuso credenziale, no nuovo prompt |

## 7) Strumentazione e logging da aggiungere (debug build)

1. Wrapper (`google-workspace-wrapper.sh`)
   - loggare (senza segreti):
     - directory credenziali effettiva,
     - email runtime usata,
     - modalita scope floor,
     - argomenti startup MCP (`--tools`, `--read-only`, `--permissions`).
2. Avvio MCP
   - loggare set `required_scopes` calcolato runtime.
3. Auth layer
   - loggare motivo di `get_credentials -> None` con categorie:
     - `missing_credentials`,
     - `scope_mismatch`,
     - `session_user_mismatch`,
     - `refresh_failed`.

## 8) Piano di fix (dopo diagnosi)

### Fix candidato A (preferito)
- Avvio `workspace-mcp` in profilo minimizzato per ARIA runtime primario:
  - default `--tool-tier core --read-only` per read path,
  - escalation tool/write solo quando il task lo richiede esplicitamente.

### Fix candidato B
- Branching di wrapper per profili (`workspace-read`, `workspace-write`) con `--permissions` granulari, mantenendo server unico ma startup policy-driven.

### Fix candidato C
- Hardening del mapping utente/sessione: fallback robusto a credenziale file per email esplicita e clear diagnostics quando mismatch.

## 9) Criteri di uscita (Definition of Done)

1. `search_drive_files` e `get_drive_file_content` funzionano senza prompt OAuth ripetuti in 3 run consecutivi.
2. Nessun `ACTION REQUIRED` su richieste read in sessione gia autenticata.
3. Scope richiesti coerenti con tool effettivamente abilitati (no scope inflation).
4. Evidenze salvate in handoff tecnico con log e command transcript.

## 10) Rischi e mitigazioni

- **Rischio:** ridurre scope/tool rompe use case write.
  - **Mitigazione:** profili separati read/write e fallback escalation esplicita.
- **Rischio:** regressioni multi-account.
  - **Mitigazione:** test matrix con `user_google_email` presente/assente + single-user.
- **Rischio:** dipendenza da comportamento upstream variabile.
  - **Mitigazione:** pin versione `workspace-mcp` e smoke test auth in CI e2e.

## 11) Sequenza operativa consigliata (ordine esecuzione)

1. Eseguire Fase A (baseline).
2. Eseguire Fase B (test profilo ridotto) — decision gate su H1.
3. Se necessario, Fase C e D.
4. Applicare Fix A/B/C.
5. Rieseguire test matrix T1-T6.
6. Pubblicare handoff con evidenze e raccomandazione finale.

---

### Nota conclusiva

L'anomalia osservata e altamente compatibile con una **incoerenza tra scope richiesti dal server (derivati dal toolset attivo) e scope effettivamente concessi** alle credenziali usate per le call read di Drive/Slides. Il debugging deve quindi partire dalla riduzione controllata del perimetro tool/scope al bootstrap del server MCP.
