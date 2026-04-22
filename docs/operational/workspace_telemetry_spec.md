# Workspace Telemetry Specification

## Overview

This document defines the tool-level telemetry schema for ARIA workspace operations. Per Phase F (W1.6.F1), we define a structured telemetry format that captures trace_id, tool, profile, latency, retries, outcome, and error_type for all workspace MCP tool invocations.

## Context7 References

Based on `/modelcontextprotocol/python-sdk` Context capabilities:
- `ctx.request_id` - Unique request identifier for tracing
- `ctx.info(message, extra=dict)` - Structured logging with extra fields
- `ctx.report_progress(progress, total, message)` - Progress reporting for long operations
- `ctx.debug/warning/error` - Log levels for debugging

## Telemetry Schema

### ToolInvocationEvent

```json
{
  "trace_id": "uuid-v4",
  "timestamp": "ISO8601",
  "profile": "workspace-mail-read|workspace-docs-write|...",
  "skill": "triage-email|gmail-composer-pro|...",
  "tool": "google_workspace_search_gmail_messages",
  "latency_ms": 150,
  "retries": 0,
  "outcome": "success|failed|error",
  "error_type": "auth|quota|network|tool_error|null",
  "error_detail": "optional human-readable error message"
}
```

### Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `trace_id` | UUID v4 | Unique identifier for this tool invocation chain |
| `timestamp` | ISO8601 | When the tool was invoked |
| `profile` | string | Agent profile used (e.g., `workspace-mail-read`) |
| `skill` | string | Skill that triggered the invocation |
| `tool` | string | MCP tool name (e.g., `google_workspace_search_gmail_messages`) |
| `latency_ms` | integer | Time from invocation to completion |
| `retries` | integer | Number of retry attempts (0 = first try) |
| `outcome` | enum | `success`, `failed`, `error` |
| `error_type` | enum | `auth`, `quota`, `network`, `tool_error`, `null` |
| `error_detail` | string | Human-readable error message (optional) |

### Outcome Values

- `success`: Tool completed successfully
- `failed`: Tool failed but was handled (e.g., HITL rejected)
- `error`: Tool failed with unhandled exception

### Error Types

- `auth`: Authentication or authorization failure (401, 403)
- `quota`: Rate limit or quota exceeded (429)
- `network`: Network connectivity issues (timeout, DNS failure)
- `tool_error`: Tool-specific error (invalid params, server error 5xx)
- `null`: No error (success case)

## Log Format

For structured JSON logging in daemon logs:

```json
{
  "event": "tool_invocation",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-04-22T19:15:00+02:00",
  "profile": "workspace-mail-read",
  "skill": "gmail-thread-intelligence",
  "tool": "google_workspace_search_gmail_messages",
  "latency_ms": 142,
  "retries": 0,
  "outcome": "success",
  "error_type": null,
  "error_detail": null
}
```

## Usage in Code

### Python Telemetry Logger

```python
import logging
import uuid
from datetime import datetime
from typing import Literal

logger = logging.getLogger("aria.telemetry")

def log_tool_invocation(
    trace_id: str,
    profile: str,
    skill: str,
    tool: str,
    latency_ms: int,
    retries: int = 0,
    outcome: Literal["success", "failed", "error"] = "success",
    error_type: Literal["auth", "quota", "network", "tool_error", "null"] | None = None,
    error_detail: str | None = None,
) -> None:
    """Log a tool invocation event."""
    logger.info(
        "tool_invocation",
        extra={
            "trace_id": trace_id,
            "timestamp": datetime.now().isoformat(),
            "profile": profile,
            "skill": skill,
            "tool": tool,
            "latency_ms": latency_ms,
            "retries": retries,
            "outcome": outcome,
            "error_type": error_type,
            "error_detail": error_detail,
        },
    )
```

### Integration in TaskRunner

For Sprint 1.6, the `_exec_workspace_task` method logs structured events:

```python
logger.info(
    "[%s] Workspace task %s: tool=%s latency=%dms outcome=%s",
    trace_prefix,
    task.id,
    tool_name,
    latency_ms,
    outcome,
)
```

## Metrics Dashboard (Reference)

For operational monitoring:

| Metric | Description | Threshold |
|--------|-------------|-----------|
| `tool_invocation_total` | Total tool invocations by profile/skill | - |
| `tool_latency_p95` | 95th percentile latency | < 500ms |
| `tool_error_rate` | Error rate by error_type | < 2% |
| `hitl_approval_rate` | HITL approval ratio for write skills | - |
| `retry_rate` | Retry rate by tool | < 5% |

## Error Recovery Patterns

Based on Context7 guidance and Google Workspace MCP:

1. **Auth errors (401/403)**: Do not retry; escalate to re-consent
2. **Quota errors (429)**: Retry with exponential backoff (max 3 retries)
3. **Network errors**: Retry with jitter (max 2 retries)
4. **Tool errors (5xx)**: Retry once after 1s delay
5. **Client errors (4xx)**: Do not retry; log and fail fast

## Acceptance Criteria (W1.6.F1)

- [x] Telemetry schema defined with all required fields
- [ ] Structured logging in runner.py for workspace invocations
- [ ] Dashboard reference documentation
- [ ] Error type classification for all workspace tool errors

## References

- Context7: `/modelcontextprotocol/python-sdk` - Context capabilities for logging and progress
- Context7: `/taylorwilsdon/google_workspace_mcp` - Tool error handling patterns