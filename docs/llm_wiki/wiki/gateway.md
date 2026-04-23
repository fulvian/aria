---
title: Gateway
sources:
  - docs/foundation/aria_foundation_blueprint.md §7
  - docs/foundation/decisions/ADR-0007-stt-stack-dual.md
last_updated: 2026-04-23
tier: 1
---

# Gateway — Telegram Gateway

## Architettura

Gateway Python standalone, daemon systemd. In MVP **solo Telegram**; predisposto per multi-canale in Fase 2.

```
┌────────────────────────────────────────────────────┐
│  Gateway Daemon (Python)                           │
│  ├─ Channel Adapters                               │
│  │   └─ Telegram (python-telegram-bot v22)         │
│  ├─ Session Manager (SQLite mapping)               │
│  ├─ Auth & Authz (whitelist + HMAC)                │
│  ├─ Multimodal Handlers                            │
│  │   ├─ Image → OCR (pytesseract) / VLM pass-thru  │
│  │   └─ Voice → Whisper (locale o API)             │
│  └─ ARIA Core invoker (spawn KiloCode child)       │
└────────────────────────────────────────────────────┘
```

*source: `docs/foundation/aria_foundation_blueprint.md` §7.1*

## Sessioni Multi-Utente

Tabella `gateway_sessions` in SQLite con mapping `channel + external_user_id → aria_session_id`.

- Ogni utente Telegram whitelisted ha una sessione KiloCode dedicata
- Context window **non condivisa** tra utenti
- Locale di default: `it-IT`

*source: `docs/foundation/aria_foundation_blueprint.md` §7.2*

## Autenticazione

- **Whitelist**: solo `external_user_id` in `ARIA_TELEGRAM_WHITELIST`
- Messaggi da ID non whitelisted → log + scartati silenziosamente
- Webhook HMAC-SHA256 con secret rotabile
- Fase 2: ruoli (`owner`, `guest`) per multi-user

*source: `docs/foundation/aria_foundation_blueprint.md` §7.3*

## Multimodalità

| Tipo | Pipeline | Dettaglio |
|------|----------|-----------|
| **Immagini** | Download → OCR pytesseract / VLM | Passaggio diretto a modello vision |
| **Voce** | Download → STT → testo → `user_input` | `faster-whisper` (default), `openai-whisper` (fallback) |
| **PDF** | Skill `pdf-extract` (PyMuPDF) → testo | Ingesto come episodic |

### STT Stack (ADR-0007)

- **Primary**: `faster-whisper` (local, model `small`, CPU/GPU auto)
- **Fallback**: `openai-whisper` (se faster-whisper import fails)
- **Cloud Whisper API**: Solo con flag esplicito `WHISPER_USE_CLOUD=1`
- **Lazy loading**: Modello caricato alla prima chiamata, non all'import
- **Graceful degradation**: Se nessun Whisper installato → `""` + warning log

*source: `docs/foundation/decisions/ADR-0007-stt-stack-dual.md`*

## HITL Responder

Il gateway include un HITL responder (`src/aria/gateway/hitl_responder.py`) che:
- Riceve eventi HITL dallo scheduler
- Invia inline keyboard a Telegram
- Gestisce risposte utente e le propaga allo scheduler

## Roadmap Canali

| Canale | MVP | Fase 2 |
|--------|-----|--------|
| CLI | ✅ | |
| Telegram | ✅ | |
| Slack | | ✅ |
| WhatsApp | | ✅ |
| Discord | | ✅ |
| WebUI | | ✅ (Tauri+React o FastAPI+HTMX) |

*source: `docs/foundation/aria_foundation_blueprint.md` §7.5*

## Implementazione Codice

```
src/aria/gateway/
├── __init__.py
├── daemon.py             # systemd entrypoint
├── telegram_adapter.py   # python-telegram-bot v22 integration
├── session_manager.py    # SQLite session management
├── auth.py               # Whitelist + HMAC
├── multimodal.py         # OCR/vision, Whisper
├── conductor_bridge.py   # Spawn KiloCode subprocess
├── hitl_responder.py     # HITL via Telegram
├── metrics_server.py     # Prometheus endpoint
└── schema.py             # Pydantic models
```

## Criticita Osservate (2026-04-23)

1. **Servizio non persistente per default**
   - Stato rilevato: `aria-gateway.service` inattivo (dead) in systemd user.
   - Impatto: il bot non consuma update, quindi nessuna risposta ai messaggi.
   - source: `systemd/aria-gateway.service`, `scripts/install_systemd.sh`
   - last_updated: 2026-04-23

2. **Filtro chat troppo restrittivo (`PRIVATE` only)**
   - Tutti gli handler Telegram sono registrati con `filters.ChatType.PRIVATE`.
   - Impatto: messaggi inviati in gruppi/canali non vengono processati.
   - source: `src/aria/gateway/telegram_adapter.py`
   - last_updated: 2026-04-23

3. **Pipeline Conductor non cablata nel daemon**
   - `gateway.user_message` viene pubblicato, ma `ConductorBridge` non viene istanziato né sottoscritto.
   - Impatto: niente risposta AI reale (solo ack locale se l'handler viene eseguito).
   - source: `src/aria/gateway/daemon.py`, `src/aria/gateway/conductor_bridge.py`, `src/aria/gateway/telegram_adapter.py`
   - last_updated: 2026-04-23

4. **Schema payload incoerente tra adapter e bridge**
   - Adapter pubblica `user_id`; bridge legge `telegram_user_id`.
   - Impatto: perdita metadati utente nel tracciamento e memoria episodica.
   - source: `src/aria/gateway/telegram_adapter.py`, `src/aria/gateway/conductor_bridge.py`
   - last_updated: 2026-04-23

5. **Gap test coverage su integrazione gateway end-to-end**
   - Assenti test dedicati per wiring daemon/adapter/bridge/reply loop.
   - Impatto: regressioni runtime non intercettate dai quality gate correnti.
   - source: `tests/`
   - last_updated: 2026-04-23

6. **Hardening incompatibile con child Node/V8**
   - `MemoryDenyWriteExecute=true` nel servizio gateway provoca crash V8 durante spawn Conductor (`SetPermissionsOnExecutableMemoryChunk`).
   - Impatto: nessuna risposta AI reale; solo messaggi di errore fallback.
   - source: `systemd/aria-gateway.service`, `src/aria/gateway/conductor_bridge.py`
   - last_updated: 2026-04-23

## Remediation Implementata (2026-04-23)

1. **Wiring completo daemon -> bridge -> reply**
   - `ConductorBridge` ora viene inizializzato nel daemon con store episodico connesso.
   - Sottoscrizioni eventi aggiunte:
     - `gateway.user_message` -> `ConductorBridge.handle_user_message`
     - `gateway.reply` -> `TelegramAdapter.handle_gateway_reply`
   - source: `src/aria/gateway/daemon.py`
   - last_updated: 2026-04-23

2. **Delivery delle risposte Telegram via event bus**
   - Aggiunti in `TelegramAdapter`:
     - `send_text(chat_id, text)`
     - `handle_gateway_reply(payload)` con risoluzione destinazione via `session_id` o fallback `telegram_user_id/user_id`.
   - source: `src/aria/gateway/telegram_adapter.py`
   - last_updated: 2026-04-23

3. **Allineamento schema payload adapter/bridge**
   - `gateway.user_message` pubblica ora sia `user_id` sia `telegram_user_id`.
   - source: `src/aria/gateway/telegram_adapter.py`
   - last_updated: 2026-04-23

4. **Sblocco processing oltre chat private**
   - Rimossi i vincoli `filters.ChatType.PRIVATE` dagli handler.
   - I messaggi restano protetti dal controllo whitelist per `effective_user`.
   - source: `src/aria/gateway/telegram_adapter.py`
   - last_updated: 2026-04-23

5. **Hardening operativo systemd start path**
   - `install_systemd.sh start` ora esegue `enable --now` per scheduler/gateway, riducendo rischio servizio down post-reboot.
   - source: `scripts/install_systemd.sh`
   - last_updated: 2026-04-23

6. **Copertura test aggiunta**
   - Nuovi test unit per:
     - payload con `telegram_user_id`
     - reply delivery via `session_id`
     - fallback reply via `telegram_user_id`
   - source: `tests/unit/gateway/test_telegram_adapter.py`
   - last_updated: 2026-04-23

7. **Compatibilita systemd con Conductor (Node/V8)**
   - Impostato `MemoryDenyWriteExecute=false` su `aria-gateway.service` con nota esplicita di compatibilita.
   - Unit reinstallata e servizio riavviato; proprieta runtime verificata (`MemoryDenyWriteExecute=no`).
   - source: `systemd/aria-gateway.service`, `scripts/install_systemd.sh`
   - last_updated: 2026-04-23

8. **Compatibilita CLI Kilo (`run`)**
   - Root cause ulteriore emersa in E2E: bridge usava `--input` (non supportato da `kilo run` corrente).
   - Correzione applicata:
     - usa prompt come argomento posizionale (`-- <message>`)
     - forza `--format json --auto` per parsing stabile e non-interattivo
     - fallback aggiornato da `kilo chat --input` a `kilo run` con stessi flag.
   - ulteriore correzione: rimosso `--session` dai run one-shot (il flag è per continuare sessioni esistenti).
   - allineamento analogo nel runner scheduler workspace.
   - source: `src/aria/gateway/conductor_bridge.py`, `src/aria/scheduler/runner.py`
   - last_updated: 2026-04-24

## Vedi anche

- [[scheduler]] — HITL pending management
- [[agents-hierarchy]] — Conductor bridge
- [[tools-mcp]] — MCP server connectivity
