---
name: email-draft
version: 1.0.0
description: Compone bozze email con stile dinamico. Per ogni recipient, analizza runtime le ultime conversazioni via google_workspace e adatta tono/registro/lessico. NESSUN bootstrap di stile fisso, NESSUNA lesson statica.
trigger-keywords:
  - scrivi email
  - drafta mail
  - rispondi a
  - bozza email
  - rispondi mail
user-invocable: true
allowed-tools:
  - aria-memory__wiki_recall_tool
  - hitl-queue__ask
  - spawn-subagent
max-tokens: 6000
estimated-cost-eur: 0.04
---

# Email Draft

## Obiettivo
Comporre una bozza email coerente con lo stile usato dall'utente in conversazioni
precedenti con lo STESSO recipient (o gruppo). Bozza salvata come Gmail draft
(no auto-send).

## Procedura
1. Parsing input: recipient (To), eventuale thread_id o subject di riferimento,
   scopo (rispondere/ proporre/ chiedere).
2. **Style discovery dinamico (Q7)**:
   a. Spawn workspace-agent → `gmail.search(to:<recipient> OR from:<recipient>,
      after:365d)` → ultimi 10-30 thread.
   b. Estrai dai thread usando `email_style.py`:
      - Saluto iniziale (es. "Ciao Mario", "Egregio Dott.", "Hi Mario")
      - Saluto finale (es. "A presto", "Cordiali saluti", "Best")
      - Pronome (tu/lei/voi)
      - Lunghezza media frasi
      - Registro (formale / cordiale / conciso / tecnico)
   c. Profilo stile **runtime** (NON salvare in wiki — transitorio per-recipient).
3. Recall contesto thread:
   a. Se reply: spawn workspace-agent → `gmail.get_thread(thread_id)` →
      cronologia messaggi.
   b. `wiki_recall` su recipient name → eventuali entity/topic correlati.
4. Genera bozza rispettando profilo stile + contesto thread + scopo.
5. **HITL locale (Q8)**: `hitl-queue/ask` mostra preview all'utente in REPL —
   utente conferma, modifica o annulla.
6. Su conferma: spawn workspace-agent → `gmail.draft_create(to=<recipient>,
   subject=<...>, body=<...>, in_reply_to=<thread_id?>)`.
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

## Failure modes
- workspace-agent DOWN → bozza generata senza style adaptation.
- Thread quote lunghe → tronca history > 5 messaggi recenti.
- Recipient gruppo → discovery sul gruppo aggregato.
