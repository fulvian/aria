---
name: triage-email
version: 1.0.0
description: Classificazione inbox Gmail per urgenza con digest. Usa il proxy MCP per Google Workspace.
trigger-keywords: [email, inbox, triage, leggi mail, leggi email]
user-invocable: true
allowed-tools:
  - aria-mcp-proxy__search_tools
  - aria-mcp-proxy__call_tool
  - aria-memory__wiki_update_tool
max-tokens: 8000
estimated-cost-eur: 0.05
---

# Triage Email Skill

## Obiettivo
Leggere l'inbox Gmail, classificare per urgenza, generare digest actionable.

## Classificazione
- **Urgent**: richiede azione o risposta entro 24h
- **Actionable**: richiede azione ma non urgente
- **Informational**: da leggere quando possibile
- **Newsletter/Promo**: ignorabile o archiviabile

## Procedura
1. Recupera ultimi 20 email non lette
2. Per ognuna estrai: subject, sender, preview, date
3. Classifica basandosi su keywords, sender, e patterns
4. Genera digest categorizzato
5. Salva digest in memoria episodica

## Output
Digest con sezioni per categoria, max 3 item per section.
