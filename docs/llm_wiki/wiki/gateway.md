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

## Vedi anche

- [[scheduler]] — HITL pending management
- [[agents-hierarchy]] — Conductor bridge
- [[tools-mcp]] — MCP server connectivity
