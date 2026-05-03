---
name: email-draft
version: 2.0.0
description: Compone bozze email con stile dinamico. Per ogni recipient, analizza runtime le ultime conversazioni via Google Workspace (proxy) e adatta tono/registro/lessico. NESSUN bootstrap di stile fisso, NESSUNA lesson statica.
trigger-keywords:
  - scrivi email
  - drafta mail
  - rispondi a
  - bozza email
  - rispondi mail
user-invocable: true
allowed-tools:
  - aria-mcp-proxy_search_tools
  - aria-mcp-proxy_call_tool
  - aria-memory_wiki_recall_tool
  - hitl-queue_ask
  - spawn-subagent
max-tokens: 6000
estimated-cost-eur: 0.04
---

# Email Draft

## Obiettivo
Comporre una bozza email coerente con lo stile usato dall'utente in conversazioni
precedenti con lo STESSO recipient (o gruppo). Bozza salvata come Gmail draft
(no auto-send).

## Proxy invocation rule

Tutte le chiamate ai backend MCP passano dal proxy. Ogni chiamata deve includere
`_caller_id: "productivity-agent"`. Le operazioni Gmail passano direttamente dal proxy.

## Procedura
1. Parsing input: recipient (To), eventuale thread_id o subject di riferimento,
   scopo (rispondere/ proporre/ chiedere).
2. **Style discovery dinamico (Q7)**:
   a. Cerca email via proxy:
      `call_tool(name="google_workspace_search_gmail_messages", arguments={"query": "to:<recipient> OR from:<recipient>", "after": "365d"}, _caller_id="productivity-agent")`
       → ultimi 10-30 thread.
   b. Estrai dai thread usando `email_style.py`:
      - Saluto iniziale (es. "Ciao Mario", "Egregio Dott.", "Hi Mario")
      - Saluto finale (es. "A presto", "Cordiali saluti", "Best")
      - Pronome (tu/lei/voi)
      - Lunghezza media frasi
      - Registro (formale / cordiale / conciso / tecnico)
   c. Profilo stile **runtime** (NON salvare in wiki — transitorio per-recipient).
3. Recall contesto thread:
   a. Se reply: leggi il messaggio Gmail più rilevante via proxy:
      `call_tool(name="google_workspace_get_gmail_message_content", arguments={"message_id": "<id>"}, _caller_id="productivity-agent")`
      → usa il `message_id` restituito dalla ricerca Gmail per recuperare il contenuto.
   b. `wiki_recall` su recipient name → eventuali entity/topic correlati.
4. Genera bozza rispettando profilo stile + contesto thread + scopo.
5. **HITL locale (Q8)**: `hitl-queue/ask` mostra preview all'utente in REPL —
   utente conferma, modifica o annulla.
   Una semplice richiesta testuale di conferma nella risposta NON è sufficiente.
6. Su conferma: crea draft via proxy:
   `call_tool(name="google_workspace_draft_gmail_message", arguments={"to": "<recipient>", "subject": "<...>", "body": "<...>", "in_reply_to": "<message_id?>"}, _caller_id="productivity-agent")`
7. **Mai send diretto**: l'invio richiede passo HITL ulteriore esplicito.

## Output
- Bozza salvata come Gmail draft.
- Riepilogo: "Bozza salvata, ID draft <id>. Apri Gmail per inviarla,
  oppure conferma 'invia' per inviarla via ARIA."

## Invarianti
- **NO lesson statica `email-style-fulvio`** (Q7 esplicito).
- **NO bootstrap utente**: stile auto-discover ad ogni invocazione.
- Se < 3 conversazioni storiche: "stile incerto, registro neutro cordiale" + HITL.
- Recipient mai visto: registro default cordiale + HITL conferma.
- Mai includere info da altre conversazioni (privacy).
- Cache profilo stile in memoria sessione (non disco).
- `wiki_update_tool` al massimo una volta per turno, con payload valido.

## Failure modes
- Google Workspace DOWN via proxy → bozza generata senza style adaptation.
- Thread quote lunghe → tronca history > 5 messaggi recenti.
- Recipient gruppo → discovery sul gruppo aggregato.
