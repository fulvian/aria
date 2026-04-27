# DEPRECATED: complete_turn removed in Phase D (2026-04-27). See ADR-0005.

import pytest

pytest.skip(reason="complete_turn removed in Phase D — see ADR-0005", allow_module_level=True)


@pytest.mark.asyncio
async def test_complete_turn_persists_assistant_response(
    monkeypatch,
) -> None:
    pass  # stub to satisfy pytest collection
