# Actor Tagging Helpers
#
# Per blueprint §5.3 and sprint plan W1.1.J.
#
# Functions:
# - derive_actor_from_role: map role to actor
# - actor_trust_score: trust score per actor type
# - actor_aggregate: aggregate multiple actors
#
# Usage:
#   from aria.memory.actor_tagging import (
#       derive_actor_from_role, actor_trust_score, actor_aggregate,
#   )
#
#   actor = derive_actor_from_role("user", is_tool_result=False)
#   score = actor_trust_score(actor)
#   agg = actor_aggregate([Actor.USER_INPUT, Actor.TOOL_OUTPUT])

from __future__ import annotations

from aria.memory.schema import Actor

# === Trust Scores (per blueprint P5) ===

TRUST_SCORES: dict[Actor, float] = {
    Actor.USER_INPUT: 1.0,  # Maximum trust
    Actor.TOOL_OUTPUT: 0.9,  # High trust (verifiable)
    Actor.AGENT_INFERENCE: 0.6,  # Conditional trust
    Actor.SYSTEM_EVENT: 0.5,  # Metadata only
}

_ROLE_TO_ACTOR: dict[str, Actor] = {
    "user": Actor.USER_INPUT,
    "assistant": Actor.AGENT_INFERENCE,
    "tool": Actor.TOOL_OUTPUT,
    "system": Actor.SYSTEM_EVENT,
}


def derive_actor_from_role(
    role: str,
    is_tool_result: bool = False,
) -> Actor:
    """Derive actor from message role.

    Per blueprint §5.3:
    - user → USER_INPUT
    - assistant → AGENT_INFERENCE (or USER_INPUT if echo)
    - tool → TOOL_OUTPUT
    - system → SYSTEM_EVENT

    Args:
        role: Message role string
        is_tool_result: If True, overrides to TOOL_OUTPUT

    Returns:
        Actor enum value
    """
    if is_tool_result:
        return Actor.TOOL_OUTPUT

    return _ROLE_TO_ACTOR.get(role.lower(), Actor.SYSTEM_EVENT)


def actor_trust_score(actor: Actor) -> float:
    """Get trust score for an actor.

    Args:
        actor: Actor enum value

    Returns:
        Trust score between 0.0 and 1.0
    """
    return TRUST_SCORES.get(actor, 0.5)


def actor_aggregate(actors: list[Actor]) -> Actor:
    """Aggregate multiple actors into one.

    Per blueprint P5 - downgrade rules:
    - Mix with AGENT_INFERENCE → AGENT_INFERENCE (don't promote)
    - Mix user + tool → TOOL_OUTPUT
    - Single actor → that actor

    Args:
        actors: List of actor values to aggregate

    Returns:
        Aggregated actor
    """
    if not actors:
        return Actor.SYSTEM_EVENT

    if len(actors) == 1:
        return actors[0]

    # Precedence (blueprint P5): AGENT_INFERENCE dominates (no promotion),
    # then TOOL_OUTPUT (user+tool downgrades to tool), then USER_INPUT,
    # then SYSTEM_EVENT.
    if Actor.AGENT_INFERENCE in actors:
        return Actor.AGENT_INFERENCE
    if Actor.TOOL_OUTPUT in actors:
        return Actor.TOOL_OUTPUT
    if Actor.USER_INPUT in actors:
        return Actor.USER_INPUT
    return Actor.SYSTEM_EVENT


def format_actor_tag(actor: Actor) -> str:
    """Format actor for display/logging.

    Args:
        actor: Actor value

    Returns:
        Human-readable tag
    """
    tags = {
        Actor.USER_INPUT: "[USER]",
        Actor.TOOL_OUTPUT: "[TOOL]",
        Actor.AGENT_INFERENCE: "[AGENT]",
        Actor.SYSTEM_EVENT: "[SYS]",
    }
    return tags.get(actor, "[???]")
