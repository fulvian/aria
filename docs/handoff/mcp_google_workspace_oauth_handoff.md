# MCP Google Workspace OAuth - Handoff per GPT 5.3 Codex

**Creato:** 2026-04-21  
**Problema:** OAuth PKCE flow non funziona - il code viene generato dal browser ma il server callback non lo riceve mai.

---

## Contesto

### Setup
- Client ID Google OAuth: `PLACEHOLDER_CLIENT_ID_OLD`
- Client Secret: `PLACEHOLDER_CLIENT_SECRET_OLD` (Desktop app, non richiede PKCE secret)
- Scope richiesto: `https://www.googleapis.com/auth/gmail.readonly`
- Redirect URI: `http://localhost:8080/callback`

### Il Problema In Sintesi

L'utente completa l'autenticazione Google nel browser, ma il server Python in ascolto su `localhost:8080` **non riceve mai il callback**.

Sintomi:
1. Il browser mostra "Connessione rifiutata" o simile dopo il redirect
2. `netstat`/`ss` mostrano che la porta 8080 non è effettivamente in ascolto TCP (connect返回98 "Address already in use" ma nessun processo lo usa)
3. L'utente HA il code valorizedall'URL nella barra (es: `4/0Aci98E9p-HeLKIT25j3UR0KTScSqgS4gsbwXJ8XxaHe1xLhBGvvzvtuyAdxaB6fE4bvKqw`) ma non può completare lo scambio token

### Cosa Abbiamo Verificato

1. **Keyring funziona** - `KeyringStore().put_oauth()` e `get_oauth()` funzionano correttamente
2. **Token endpoint funziona** - `httpx.post` al token endpoint Google restituisce risposte corrette (400 per code invalidi, 200 per flow validi)
3. **Il code dalla URL funziona** - L'utente ha estratto il code dall'URL di redirect e può usarlo direttamente
4. **Il problema è nel receive callback** - Il server HTTPServer non riceve la callback dal browser

### Root Cause Sospetta

Il browser Probabilmente:
- Prova a connettersi a `http://localhost:8080` 
- La connessione viene rifiutata (la porta non è accessibile dal browser per qualche reason)
- L'utente vede l'URL con il code ma il server non lo legge mai

**Alternativa:** Il code nella URL è quello giusto, ma dobbiamo solo completare manualmente lo scambio token.

---

## Cosa Serve a Codex

### Opzione 1: Risolvere ilReceive Callback
Capire perché `HTTPServer(('localhost', 8080), Handler)` non riceve connessioni dal browser. Possibili cause:
- Firewall locale che blocca connessioni in entrata su 8080
- WSL/network configuration che non espone localhost al browser Windows
- Browser che cerca di usare IPv6 invece di IPv4

### Opzione 2: Completare lo Scambio Token Manualmente
Il code è: `4/0Aci98E9p-HeLKIT25j3UR0KTScSqgS4gsbwXJ8XxaHe1xLhBGvvzvtuyAdxaB6fE4bvKqw`

Il PKCE verifier usato per generare quel code è andato perso. Servirebbe:
- Generare un nuovo verifier/challenge
- Chiamare il token endpoint con il code vecchio ma verifier nuovo
- Google potrebbe rifiutare se il verifier non corrisponde al challenge originale

**NOTA:** Il code Google OAuth ha validità breve (~60 secondi). Potrebbe essere scaduto.

### Codice di Test Funzionante

```python
# Token exchange - funziona
import httpx
r = httpx.post('https://oauth2.googleapis.com/token', 
    data={'client_id': 'PLACEHOLDER_CLIENT_ID_OLD',
          'client_secret': 'PLACEHOLDER_CLIENT_SECRET_OLD',
          'code': 'IL_CODE_DALL_URL',
          'code_verifier': 'IL_VERIFIER_GENERATO_CON generate_code_verifier(64)',
          'grant_type': 'authorization_code',
          'redirect_uri': 'http://localhost:8080/callback'}, timeout=30)
# Se status=200 e refresh_token presente -> success
```

```python
# Keyring storage - funziona
from aria.credentials.keyring_store import KeyringStore
KeyringStore().put_oauth('google_workspace', 'primary', 'refresh_token_value')
```

---

## File Relevanti

- `scripts/oauth_first_setup.py` - Script di setup OAuth (ha problemi con il receive callback)
- `src/aria/credentials/keyring_store.py` - KeyringStore funzionante
- `scripts/wrappers/google-workspace-wrapper.sh` - Wrapper che legge token dal keyring

---

## Suggerimenti per Codex

1. **Priorità 1:** Verificare se il code è ancora valido chiedendo all'utente di rigenerare un nuovo URL con un nuova sessione del browser, poi estrarre il code immediatamente

2. **Priorità 2:** Risolvere il problema di rete - perché il browser non può connettersi a localhost:8080? È un problema di WSL? Di firewall? Di binding?

3. **Priorità 3:** Se il code è scaduto, creare un flusso alternativo che non richiede receive callback:
   - Generare URL → Utente apre browser
   - Utente copia URL di redirect completo dopo il redirect (anche se la pagina dà errore)
   - Estrarre il code dall'URL copiato
   - Completare token exchange lato server senza bisogno di ascoltare su una porta

4. **Considerazione importante:** Il client è un OAuth "Desktop app" - il flusso standard prevede che il redirect URI sia `http://localhost` con qualsiasi porta. Il problema potrebbe essere che il server HTTPServer si binds a un indirizzo che il browser Windows non può raggiungere da WSL.
