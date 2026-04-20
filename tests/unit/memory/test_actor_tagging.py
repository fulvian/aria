from __future__ import annotations

from aria.memory.actor_tagging import (
    actor_aggregate,
    actor_trust_score,
    derive_actor_from_role,
    format_actor_tag,
)
from aria.memory.schema import Actor


def test_derive_actor_from_role() -> None:
    assert derive_actor_from_role("user") == Actor.USER_INPUT
    assert derive_actor_from_role("assistant") == Actor.AGENT_INFERENCE
    assert derive_actor_from_role("tool") == Actor.TOOL_OUTPUT
    assert derive_actor_from_role("system") == Actor.SYSTEM_EVENT
    assert derive_actor_from_role("whatever", is_tool_result=True) == Actor.TOOL_OUTPUT


def test_actor_trust_score_values() -> None:
    assert actor_trust_score(Actor.USER_INPUT) == 1.0
    assert actor_trust_score(Actor.TOOL_OUTPUT) == 0.9


def test_actor_aggregate_rules() -> None:
    assert actor_aggregate([]) == Actor.SYSTEM_EVENT
    assert actor_aggregate([Actor.USER_INPUT, Actor.TOOL_OUTPUT]) == Actor.TOOL_OUTPUT
    assert actor_aggregate([Actor.USER_INPUT, Actor.AGENT_INFERENCE]) == Actor.AGENT_INFERENCE


def test_format_actor_tag() -> None:
    assert format_actor_tag(Actor.USER_INPUT) == "[USER]"
