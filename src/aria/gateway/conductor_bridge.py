"""
Bridge between Gateway and ARIA-Conductor per blueprint §8.6 and W1.3.I.

Consumer of `gateway.user_message` bus event.
Spawns KiloCode child sessions for Conductor delegation.

Strategies (tried in order per sprint-03 plan):
  A. npx --yes kilocode run --session <id> --agent aria-conductor --input '<msg>'
  B. kilocode chat --input '<msg>' with KILOCODE_SESSION_ID

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
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aria.memory.schema import Actor
from aria.utils.logging import new_trace_id

if TYPE_CHECKING:
    from aria.memory.episodic import EpisodicStore

logger = logging.getLogger(__name__)

# Default timeout for child session (10 min per blueprint §8.6)
DEFAULT_CONDUCTOR_TIMEOUT_S = 600


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
        await self._store.add(
            session_id=aria_session_id,
            actor=Actor.AGENT_INFERENCE,
            role="assistant",
            content=result.get("text", ""),
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
                "text": result.get("text", ""),
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
        child_session_id = str(uuid.uuid4())

        # Prepare subprocess
        env = {
            "KILOCODE_CONFIG_DIR": "/home/fulvio/coding/aria/.aria/kilocode",
            "KILOCODE_STATE_DIR": str(self._sessions_dir),
            "ARIA_HOME": "/home/fulvio/coding/aria",
            "ARIA_RUNTIME": "/home/fulvio/coding/aria/.aria/runtime",
            "ARIA_TRACE_ID": trace_id,
        }

        # Try strategy A: npx kilocode run with session + agent + input
        cmd: list[str] = [
            "npx",
            "--yes",
            "kilocode",
            "run",
            "--session",
            child_session_id,
            "--agent",
            "aria-conductor",
            "--input",
            input_text,
        ]

        logger.info(
            "Spawning conductor child session: %s",
            child_session_id,
            extra={"trace_id": trace_id},
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                cwd="/home/fulvio/coding/aria",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout_s)

            if proc.returncode != 0:
                stderr_text = stderr.decode("utf-8", errors="replace")[:500]
                logger.error(
                    "Conductor subprocess failed (code %d): %s",
                    proc.returncode,
                    stderr_text,
                    extra={"trace_id": trace_id},
                )
                raise RuntimeError(f"Conductor failed: {stderr_text}")

            # Parse stdout for result
            # Expected: JSON with {text, status, ...}
            stdout_text = stdout.decode("utf-8", errors="replace").strip()

            # Try to extract JSON from stdout
            try:
                output_data = json.loads(stdout_text)
                return {
                    "text": output_data.get("result", stdout_text[:2000]),
                    "child_session_id": child_session_id,
                    "tokens_used": output_data.get("tokens_used", 0),
                }
            except json.JSONDecodeError:
                # Fallback: use raw stdout
                return {
                    "text": stdout_text[:2000],
                    "child_session_id": child_session_id,
                    "tokens_used": 0,
                }

        except TimeoutError:
            logger.error(
                "Conductor subprocess timed out after %ds",
                self._timeout_s,
                extra={"trace_id": trace_id},
            )
            raise RuntimeError(f"Conductor timed out after {self._timeout_s}s") from None
        except FileNotFoundError:
            # Strategy B fallback: try kilocode chat
            logger.warning("npx kilocode not found, trying strategy B")
            return await self._spawn_conductor_fallback(input_text, session_id, trace_id)

    async def _spawn_conductor_fallback(
        self,
        input_text: str,
        session_id: str,
        trace_id: str,
    ) -> dict[str, Any]:
        """Fallback strategy B: kilocode chat with input file IPC.

        Args:
            input_text: User message.
            session_id: ARIA session ID.
            trace_id: Trace ID.

        Returns:
            Dict with result.
        """
        child_session_id = str(uuid.uuid4())
        input_file = self._children_dir / f"{child_session_id}.input.json"

        # Write input to file
        self._children_dir.mkdir(parents=True, exist_ok=True)
        input_file.write_text(
            json.dumps({"input": input_text, "session_id": session_id}),
            encoding="utf-8",
        )

        env = {
            "KILOCODE_CONFIG_DIR": "/home/fulvio/coding/aria/.aria/kilocode",
            "KILOCODE_STATE_DIR": str(self._sessions_dir),
            "KILOCODE_SESSION_ID": child_session_id,
            "ARIA_HOME": "/home/fulvio/coding/aria",
            "ARIA_RUNTIME": "/home/fulvio/coding/aria/.aria/runtime",
            "ARIA_TRACE_ID": trace_id,
        }

        cmd = [
            "kilocode",
            "chat",
            "--input",
            str(input_file),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                cwd="/home/fulvio/coding/aria",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self._timeout_s)

            if proc.returncode != 0:
                stderr_text = stderr.decode("utf-8", errors="replace")[:500]
                raise RuntimeError(f"Conductor fallback failed: {stderr_text}")

            stdout_text = stdout.decode("utf-8", errors="replace").strip()
            return {
                "text": stdout_text[:2000],
                "child_session_id": child_session_id,
                "tokens_used": 0,
            }

        finally:
            # Clean up input file
            if input_file.exists():
                input_file.unlink()
