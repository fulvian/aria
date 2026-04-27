# ARIA Memory Wiki — Profile Auto-Inject
#
# Per docs/plans/auto_persistence_echo.md §6.1 + §6.2.
#
# Profile auto-inject: builds the <memory> block for conductor prompt
# injection with:
#   - <profile>: current user profile (always injected)
#   - Memory contract header
#
# The conductor agent template has a {{ARIA_MEMORY_BLOCK}} placeholder.
# On boot and on profile update, this module regenerates the active
# agent file by reading the template source, building the memory block,
# and substituting the placeholder.
#
# Usage:
#   from aria.memory.wiki.prompt_inject import regenerate_conductor_template
#   await regenerate_conductor_template(store)

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aria.memory.wiki.db import WikiStore

logger = logging.getLogger(__name__)

# === Constants ===

# Placeholder in template source file
PLACEHOLDER = "{{ARIA_MEMORY_BLOCK}}"

# Template source and active target filenames
_TEMPLATE_FILENAME = "_aria-conductor.template.md"
_ACTIVE_FILENAME = "aria-conductor.md"

# Token budget for profile block (plan §6.1: ~300 tokens)
_PROFILE_MAX_CHARS = 1200  # ~300 tokens at 4 chars/token

# Memory contract section injected with profile
_MEMORY_CONTRACT_HEADER = (
    "## Memoria contestuale (auto-iniettata)\n\n"
    "Il seguente profilo utente è stato caricato da wiki.db.\n"
    "Usa queste informazioni per personalizzare ogni risposta.\n"
)

_MEMORY_CONTRACT_FOOTER = ""


def _resolve_agent_dir() -> Path:
    """Resolve the Kilo agents directory path."""
    aria_home = Path(os.environ.get("ARIA_HOME", "/home/fulvio/coding/aria"))
    return aria_home / ".aria" / "kilo-home" / ".kilo" / "agents"


async def build_memory_block(store: WikiStore) -> str:
    """Build the <memory> block for conductor prompt injection.

    Per plan §6.1: inlines current profile body. ~300 token budget.

    Args:
        store: WikiStore instance.

    Returns:
        Memory block string ready for template substitution.
    """
    from aria.memory.wiki.recall import WikiRecallEngine

    engine = WikiRecallEngine(store)
    profile = await engine.get_profile()

    parts = [_MEMORY_CONTRACT_HEADER]

    if profile is not None:
        body = profile.body_md
        # Truncate to budget
        if len(body) > _PROFILE_MAX_CHARS:
            body = body[:_PROFILE_MAX_CHARS] + "\n...[truncated]"
        parts.append(f"<profile>\n{body}\n</profile>")
    else:
        parts.append("<profile>\nNo profile established yet.\n</profile>")

    parts.append(_MEMORY_CONTRACT_FOOTER)

    return "\n".join(parts)


async def build_recall_block(
    store: WikiStore,
    user_message: str,
    max_pages: int = 5,
    min_score: float = 0.3,
) -> str:
    """Build recall context block from FTS5 search against user message.

    Per plan §6.2: called at turn start, returns relevant pages.
    This is a convenience function for the recall tool results,
    formatted as a prompt block.

    Args:
        store: WikiStore instance.
        user_message: The current user message to match against.
        max_pages: Maximum pages to return.
        min_score: Minimum relevance score.

    Returns:
        Formatted recall block string, or empty string if no results.
    """
    from aria.memory.wiki.recall import WikiRecallEngine

    engine = WikiRecallEngine(store)
    results = await engine.recall(
        query=user_message,
        max_pages=max_pages,
        min_score=min_score,
    )

    if not results:
        return ""

    parts = ["<relevant_pages>"]
    for r in results:
        parts.append(
            f"- [{r.kind.value}/{r.slug}] {r.title} (score={r.score:.2f}):\n  {r.body_excerpt}"
        )
    parts.append("</relevant_pages>")

    return "\n".join(parts)


async def regenerate_conductor_template(
    store: WikiStore,
    agent_dir: Path | None = None,
) -> bool:
    """Regenerate the active conductor agent template with profile substitution.

    Per plan §6.1:
    1. Read template source (_aria-conductor.template.md) with {{ARIA_MEMORY_BLOCK}}
    2. Build memory block from wiki.db profile
    3. Substitute placeholder → write active agent file (aria-conductor.md)

    Args:
        store: WikiStore instance for profile access.
        agent_dir: Optional override for agents directory (testing).

    Returns:
        True if template was regenerated, False on error.
    """
    agents_path = agent_dir or _resolve_agent_dir()
    template_path = agents_path / _TEMPLATE_FILENAME
    active_path = agents_path / _ACTIVE_FILENAME

    if not template_path.exists():  # noqa: ASYNC240
        logger.warning("Template source not found: %s", template_path)
        return False

    try:
        # Read template source
        template_content = template_path.read_text(encoding="utf-8")

        if PLACEHOLDER not in template_content:
            logger.warning(
                "Template source %s does not contain %s placeholder",
                template_path,
                PLACEHOLDER,
            )
            return False

        # Build memory block
        memory_block = await build_memory_block(store)

        # Substitute
        active_content = template_content.replace(PLACEHOLDER, memory_block)

        # Write active agent file
        active_path.write_text(active_content, encoding="utf-8")

        logger.info("Regenerated conductor template: %s", active_path)
        return True

    except Exception as exc:
        logger.error("Failed to regenerate conductor template: %s", exc)
        return False
