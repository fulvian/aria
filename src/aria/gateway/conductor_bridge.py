"""
Bridge between Gateway and ARIA-Conductor per blueprint §8.6 and W1.3.I.

Consumer of `gateway.user_message` bus event.
Spawns KiloCode child sessions for Conductor delegation.

Strategies (tried in order per sprint-03 plan):
  A. npx --yes --package @kilocode/cli kilo run --session <id>
     --agent aria-conductor --format json --auto '<msg>'
  B. kilo (or kilocode) run --session <id> --agent aria-conductor
     --format json --auto '<msg>'

The Conductor runs in an isolated child session with separate context window.
Transcript is saved to `.aria/kilocode/sessions/children/<id>.json`.

Prompt injection frame (ADR-0006):
  Every tool_output injected into Conductor system prompt MUST be wrapped
  in <<TOOL_OUTPUT>>...<</TOOL_OUTPUT>> with nested frame sanitization.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aria.memory.schema import Actor
from aria.utils.logging import new_trace_id
from aria.utils.prompt_safety import redact_secrets, sanitize_nested_frames, wrap_tool_output

if TYPE_CHECKING:
    from aria.memory.episodic import EpisodicStore

logger = logging.getLogger(__name__)

# Default timeout for child session (10 min per blueprint §8.6)
DEFAULT_CONDUCTOR_TIMEOUT_S = 600


def _new_kilo_session_id() -> str:
    """Generate a Kilo-compatible session id.

    Kilo validates that session IDs start with ``ses``.
    """
    return f"ses_{uuid.uuid4().hex}"


def _parse_kilo_ndjson_output(stdout_text: str) -> dict[str, Any]:
    """Parse KiloCode NDJSON streaming output from stdout.

    KiloCode emits newline-delimited JSON events when run with ``--format json``.
    Each event is a dict with ``type`` and ``part`` fields.  We collect text
    from events of ``type == "text"`` (or ``part.type == "text"``).

    Falls back to the legacy single-JSON-result parsing (looking for ``result``
    key in the last valid JSON line), and finally to raw text if nothing matches.

    Args:
        stdout_text: Raw stdout from KiloCode subprocess.

    Returns:
        Dict with keys: text (str), tokens_used (int), result_raw (dict | None).
    """
    text_parts: list[str] = []
    last_json: dict[str, Any] | None = None
    tokens_used = 0

    for line in stdout_text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        try:
            event = json.loads(cleaned)
        except json.JSONDecodeError:
            continue

        if not isinstance(event, dict):
            continue

        last_json = event

        # Collect text from streaming events
        event_type = event.get("type", "")
        part = event.get("part")
        if event_type == "text" and isinstance(part, dict):
            part_text = part.get("text", "")
            if part_text:
                text_parts.append(part_text)
            # Check for tokens_used in part metadata
            if "tokens_used" in part:
                tokens_used = int(part["tokens_used"] or 0)
            time_info = part.get("time")
            if isinstance(time_info, dict) and "tokens_used" in time_info:
                tokens_used = int(time_info["tokens_used"] or 0)

        # Also try top-level tokens_used
        if "tokens_used" in event:
            tokens_used = int(event["tokens_used"] or 0)

    # Strategy 1: we found NDJSON text events → concatenate
    if text_parts:
        return {
            "text": "".join(text_parts).strip(),
            "tokens_used": tokens_used,
            "result_raw": last_json,
        }

    # Strategy 2: fallback to legacy single-result JSON (look for "result" key)
    if last_json is not None and "result" in last_json:
        return {
            "text": str(last_json["result"]),
            "tokens_used": int(last_json.get("tokens_used", 0) or 0),
            "result_raw": last_json,
        }

    # Strategy 3: raw text
    return {
        "text": stdout_text[:2000],
        "tokens_used": 0,
        "result_raw": None,
    }


def _kilo_npx_packages() -> list[str]:
    env_packages = os.getenv("ARIA_KILO_NPX_PACKAGES", "").strip()
    if env_packages:
        return [p.strip() for p in env_packages.split(",") if p.strip()]

    system_name = platform.system().lower()
    machine = platform.machine().lower()

    if system_name == "linux" and machine in {"x86_64", "amd64"}:
        return ["@kilocode/cli-linux-x64", "@kilocode/cli-linux-x64-baseline", "@kilocode/cli"]
    if system_name == "linux" and machine in {"aarch64", "arm64"}:
        return ["@kilocode/cli-linux-arm64", "@kilocode/cli"]
    if system_name == "darwin" and machine in {"x86_64", "amd64"}:
        return ["@kilocode/cli-darwin-x64", "@kilocode/cli"]
    if system_name == "darwin" and machine in {"arm64", "aarch64"}:
        return ["@kilocode/cli-darwin-arm64", "@kilocode/cli"]

    return ["@kilocode/cli"]


class ConductorBridge:
    """Bridge between Gateway and ARIA-Conductor.

    Handles:
    1. Consuming gateway.user_message events
    2. Looking up / creating ARIA session
    3. Saving user message to episodic memory (actor=USER_INPUT)
    4. Spawning KiloCode child session for Conductor
    5. Streaming output back to Gateway (via gateway.reply event)
    6. Saving assistant response to episodic (actor=AGENT_INFERENCE)
    """

    def __init__(
        self,
        bus: Any,  # EventBus - imported lazily to avoid circular  # noqa: ANN401
        store: EpisodicStore,
        config: Any,  # AriaConfig  # noqa: ANN401
        sessions_dir: Path | None = None,
        timeout_s: int = DEFAULT_CONDUCTOR_TIMEOUT_S,
    ) -> None:
        """Initialize bridge.

        Args:
            bus: Event bus for publishing/receiving events.
            store: EpisodicStore for memory operations.
            config: AriaConfig instance.
            sessions_dir: Path to KiloCode sessions dir.
            timeout_s: Subprocess timeout in seconds.
        """
        self._bus = bus
        self._store = store
        self._config = config
        self._sessions_dir = sessions_dir or Path(
            os.getenv(
                "KILOCODE_STATE_DIR",
                "/home/fulvio/coding/aria/.aria/kilocode/sessions",
            )
        )
        self._children_dir = self._sessions_dir / "children"
        self._timeout_s = timeout_s
        self._children_dir.mkdir(parents=True, exist_ok=True)

    async def handle_user_message(self, payload: dict[str, Any]) -> None:
        """Handle gateway.user_message event payload.

        Args:
            payload: Dict containing:
                - text: message text
                - session_id: Gateway session ID
                - telegram_user_id: Telegram user ID
                - trace_id: optional trace ID
        """
        text = payload.get("text", "")
        gateway_session_id = payload.get("session_id", "")
        telegram_user_id = payload.get("telegram_user_id", "")
        trace_id = payload.get("trace_id") or new_trace_id()

        if not text:
            logger.warning("Empty message received, ignoring")
            return

        # Create or reuse ARIA session ID
        aria_session_id = gateway_session_id or str(uuid.uuid4())

        # Step 1: Save user message to episodic (actor=USER_INPUT)

        await self._store.add(
            session_id=aria_session_id,
            actor=Actor.USER_INPUT,
            role="user",
            content=text,
            tags=["gateway_message"],
            meta={
                "telegram_user_id": telegram_user_id,
                "gateway_session_id": gateway_session_id,
                "trace_id": trace_id,
            },
        )

        # Step 2: Spawn KiloCode child session
        try:
            result = await self._spawn_conductor(
                input_text=text,
                session_id=aria_session_id,
                trace_id=trace_id,
            )
        except Exception as exc:
            logger.error("Conductor spawn failed: %s", exc)
            await self._bus.publish(
                "gateway.reply",
                {
                    "text": f"Mi dispiace, ho incontrato un errore: {exc}",
                    "session_id": gateway_session_id,
                    "trace_id": trace_id,
                },
            )
            return

        # Step 3: Save assistant response to episodic (actor=AGENT_INFERENCE)
        safe_result_text = redact_secrets(result.get("text", ""))

        framed_tool_output = result.get("framed_tool_output")
        if isinstance(framed_tool_output, str) and framed_tool_output:
            await self._store.add(
                session_id=aria_session_id,
                actor=Actor.TOOL_OUTPUT,
                role="tool",
                content=framed_tool_output,
                tags=["tool_output_framed"],
                meta={
                    "trace_id": trace_id,
                    "child_session_id": result.get("child_session_id"),
                },
            )

        await self._store.add(
            session_id=aria_session_id,
            actor=Actor.AGENT_INFERENCE,
            role="assistant",
            content=safe_result_text,
            tags=["conductor_response"],
            meta={
                "trace_id": trace_id,
                "child_session_id": result.get("child_session_id"),
                "tokens_used": result.get("tokens_used", 0),
            },
        )

        # Step 4: Publish reply to Gateway
        await self._bus.publish(
            "gateway.reply",
            {
                "text": safe_result_text,
                "session_id": gateway_session_id,
                "trace_id": trace_id,
            },
        )

    async def _spawn_conductor(
        self,
        input_text: str,
        session_id: str,
        trace_id: str,
    ) -> dict[str, Any]:
        """Spawn KiloCode child session for Conductor.

        Args:
            input_text: User message text.
            session_id: ARIA session ID.
            trace_id: Trace ID for logging.

        Returns:
            Dict with keys: text, child_session_id, tokens_used

        Raises:
            RuntimeError: If subprocess fails.
        """
        child_session_id = _new_kilo_session_id()

        # Prepare subprocess
        env = {
            "HOME": os.environ.get("ARIA_KILO_HOME", "/home/fulvio/coding/aria/.aria/kilo-home"),
            "PATH": os.environ.get("PATH", ""),
            "USER": os.environ.get("USER", ""),
            "KILOCODE_CONFIG_DIR": "/home/fulvio/coding/aria/.aria/kilocode",
            "KILOCODE_STATE_DIR": str(self._sessions_dir),
            "KILO_CONFIG_DIR": "/home/fulvio/coding/aria/.aria/kilocode",
            "KILO_DISABLE_EXTERNAL_SKILLS": "true",
            "ARIA_HOME": "/home/fulvio/coding/aria",
            "ARIA_RUNTIME": "/home/fulvio/coding/aria/.aria/runtime",
            "ARIA_TRACE_ID": trace_id,
        }
        env["XDG_CONFIG_HOME"] = os.path.join(env["HOME"], ".config")
        env["XDG_DATA_HOME"] = os.path.join(env["HOME"], ".local", "share")
        env["XDG_STATE_HOME"] = os.path.join(env["HOME"], ".local", "state")
        os.makedirs(env["XDG_CONFIG_HOME"], exist_ok=True)
        os.makedirs(env["XDG_DATA_HOME"], exist_ok=True)
        os.makedirs(env["XDG_STATE_HOME"], exist_ok=True)

        logger.info(
            "Spawning conductor child session: %s",
            child_session_id,
            extra={"trace_id": trace_id},
        )

        try:
            for kilo_package in _kilo_npx_packages():
                cmd: list[str] = [
                    "npx",
                    "--yes",
                    "--package",
                    kilo_package,
                    "kilo",
                    "run",
                    "--agent",
                    "aria-conductor",
                    "--format",
                    "json",
                    "--auto",
                    "--",
                    input_text,
                ]

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    env=env,
                    cwd="/home/fulvio/coding/aria",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    close_fds=True,
                )

                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout_s)
                if proc.returncode != 0:
                    stderr_text = stderr.decode("utf-8", errors="replace")[:500]
                    logger.warning(
                        "Conductor npx package %s failed (code %d): %s",
                        kilo_package,
                        proc.returncode,
                        stderr_text,
                        extra={"trace_id": trace_id},
                    )
                    continue

                stdout_text = stdout.decode("utf-8", errors="replace").strip()
                parsed = _parse_kilo_ndjson_output(stdout_text)
                return {
                    "text": parsed["text"],
                    "child_session_id": child_session_id,
                    "tokens_used": parsed["tokens_used"],
                    "framed_tool_output": self._extract_framed_tool_output(
                        parsed["result_raw"] or {}
                    ),
                }

            logger.warning("Conductor strategy A packages exhausted, trying strategy B")
            return await self._spawn_conductor_fallback(input_text, session_id, trace_id)

        except TimeoutError:
            logger.error(
                "Conductor subprocess timed out after %ds",
                self._timeout_s,
                extra={"trace_id": trace_id},
            )
            raise RuntimeError(f"Conductor timed out after {self._timeout_s}s") from None
        except FileNotFoundError:
            # Strategy B fallback: try direct executable
            logger.warning("npx @kilocode/cli not found, trying strategy B")
            return await self._spawn_conductor_fallback(input_text, session_id, trace_id)

    def _extract_framed_tool_output(self, output_data: dict[str, Any]) -> str | None:
        """Extract and frame tool output from child session payload.

        If the child emits a `tool_output` field, sanitize any nested frame
        delimiters and wrap content in a trusted frame before persistence.
        """
        tool_output = output_data.get("tool_output")
        if not isinstance(tool_output, str) or not tool_output.strip():
            return None
        sanitized = sanitize_nested_frames(tool_output)
        if not sanitized.strip():
            return None
        return wrap_tool_output(sanitized)

    async def _spawn_conductor_fallback(
        self,
        input_text: str,
        session_id: str,
        trace_id: str,
    ) -> dict[str, Any]:
        """Fallback strategy B: direct executable ``kilo run`` invocation.

        Args:
            input_text: User message.
            session_id: ARIA session ID.
            trace_id: Trace ID.

        Returns:
            Dict with result.
        """
        child_session_id = _new_kilo_session_id()

        env = {
            "HOME": os.environ.get("ARIA_KILO_HOME", "/home/fulvio/coding/aria/.aria/kilo-home"),
            "PATH": os.environ.get("PATH", ""),
            "USER": os.environ.get("USER", ""),
            "KILOCODE_CONFIG_DIR": "/home/fulvio/coding/aria/.aria/kilocode",
            "KILOCODE_STATE_DIR": str(self._sessions_dir),
            "KILOCODE_SESSION_ID": child_session_id,
            "KILO_CONFIG_DIR": "/home/fulvio/coding/aria/.aria/kilocode",
            "KILO_DISABLE_EXTERNAL_SKILLS": "true",
            "ARIA_HOME": "/home/fulvio/coding/aria",
            "ARIA_RUNTIME": "/home/fulvio/coding/aria/.aria/runtime",
            "ARIA_TRACE_ID": trace_id,
        }
        env["XDG_CONFIG_HOME"] = os.path.join(env["HOME"], ".config")
        env["XDG_DATA_HOME"] = os.path.join(env["HOME"], ".local", "share")
        env["XDG_STATE_HOME"] = os.path.join(env["HOME"], ".local", "state")
        os.makedirs(env["XDG_CONFIG_HOME"], exist_ok=True)
        os.makedirs(env["XDG_DATA_HOME"], exist_ok=True)
        os.makedirs(env["XDG_STATE_HOME"], exist_ok=True)

        for executable in ("kilo", "kilocode"):
            cmd = [
                executable,
                "run",
                "--agent",
                "aria-conductor",
                "--format",
                "json",
                "--auto",
                "--",
                input_text,
            ]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    env=env,
                    cwd="/home/fulvio/coding/aria",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    close_fds=True,
                )
                break
            except FileNotFoundError:
                logger.warning("Executable '%s' not found for fallback", executable)
        else:
            raise RuntimeError("Conductor fallback failed: no Kilo executable found in PATH")

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout_s)

        if proc.returncode != 0:
            stderr_text = stderr.decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Conductor fallback failed: {stderr_text}")

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        parsed = _parse_kilo_ndjson_output(stdout_text)
        return {
            "text": parsed["text"],
            "child_session_id": child_session_id,
            "tokens_used": parsed["tokens_used"],
            "framed_tool_output": self._extract_framed_tool_output(parsed["result_raw"] or {}),
        }
