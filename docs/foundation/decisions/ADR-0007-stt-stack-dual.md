---
adr: ADR-0007
title: STT Stack Dual — faster-whisper vs openai-whisper
status: accepted
date_created: 2026-04-20
date_accepted: 2026-04-20
author: ARIA Chief Architect
project: ARIA — Autonomous Reasoning & Intelligent Assistant
context: W1.2.K (multimodal), Sprint 1.2
---

# ADR-0007: STT Stack Dual

## Status

**Accepted** — 2026-04-20

## Context

ARIA's gateway handles voice messages via Speech-to-Text (STT). The
blueprint (§7.4) specifies two potential STT backends:

1. **`faster-whisper`** — local inference, small model, CPU/GPU
2. **`openai-whisper`** — offline-capable but heavier, or cloud API variant

This ADR documents the binding decision and operational constraints for
Sprint 1.2 multimodal components (W1.2.K).

---

## Decision

### Primary: `faster-whisper` (local)

- **Model size**: `small` (default)
- **Inference**: local, no network required
- **Cache location**: `.aria/runtime/models/`
- **Device**: `auto` (CPU or CUDA if available)
- **Install**: `pip install aria[ml]` → pulls `faster-whisper>=1.2,<2.0`

### Fallback: `openai-whisper`

- Used when `faster-whisper` import fails at runtime
- Same model size (`small`)
- **Requires explicit flag** to use cloud Whisper API (`WHISPER_USE_CLOUD=1`)
- Cloud API **never used without explicit flag** (privacy-first, local-first)

### Cloud Whisper API — Explicit Opt-In Only

- `WHISPER_USE_CLOUD=1` env var required to activate cloud Whisper API
- Without the flag, the system degrades to local inference only
- Cloud API sends audio data to OpenAI/Microsoft; local-first policy requires
  user to explicitly opt into cloud processing

---

## Implementation Constraints

1. **Lazy loading** — Whisper model is NOT loaded at import time; loaded
   on first `transcribe_audio()` call. This avoids startup latency and
   watchdog timeout issues (Risk R25).
2. **Graceful degradation** — if neither `faster-whisper` nor `openai-whisper`
   is installed, `transcribe_audio()` returns `""` and logs a warning.
   The gateway continues to operate without STT.
3. **Model caching** — downloaded model files are stored under
   `.aria/runtime/models/` and reused across restarts.
4. **Non-blocking** — the metrics and HITL paths must not be blocked by
   model loading; load is triggered on first actual voice message.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_USE_CLOUD` | `0` (false) | Set to `1` to enable cloud Whisper API |
| `ARIA_RUNTIME_MODELS_DIR` | `.aria/runtime/models` | Override model cache directory |

---

## Consequences

### Positive
- Zero network dependency for STT in default configuration
- Consistent with P4 (Local-First, Privacy-First) and P9 (Scoped Toolsets)
- Lazy loading keeps startup fast

### Negative
- `small` model has lower accuracy than `medium`/`large`
- CPU inference is slower than GPU

### Neutral
- Requires ML optional dependency to be installed (`aria[ml]`)

---

## References

- Blueprint §7.4 (Multimodal — Voice → Whisper)
- Sprint-02.md §W1.2.K
- Risk R25 (faster-whisper startup watchdog timeout)
- ADR-0001 (dependency baseline — ML moved to optional)