from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from aria.credentials.rotator import CircuitState, Rotator


class _FakeSops:
    def __init__(self) -> None:
        self.state: dict = {}

    def decrypt(self, _path: Path) -> dict:
        return self.state

    def encrypt_inplace(self, path: Path, data: dict) -> None:
        self.state = data
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("enc", encoding="utf-8")

    def edit_atomic(self, _path: Path, mutate_fn):
        self.state = mutate_fn(self.state)


@pytest.mark.asyncio
async def test_rotator_acquire_and_success(tmp_path: Path) -> None:
    sops = _FakeSops()
    state_path = tmp_path / "providers_state.enc.yaml"
    rotator = Rotator(sops=cast("Any", sops), state_path=state_path)
    rotator.sync_provider_keys(
        "tavily",
        [{"key_id": "tvly-1", "credits_total": 100}, {"key_id": "tvly-2", "credits_total": 100}],
    )

    key = await rotator.acquire("tavily")
    assert key is not None
    assert key.key_id in {"tvly-1", "tvly-2"}
    await rotator.report_success("tavily", key.key_id, credits_used=10)

    status = rotator.status("tavily")
    assert status["provider"] == "tavily"
    assert len(status["keys"]) == 2


@pytest.mark.asyncio
async def test_circuit_breaker_transitions(tmp_path: Path) -> None:
    clock = {"value": datetime(2026, 1, 1, tzinfo=UTC)}

    def now() -> datetime:
        return clock["value"]

    sops = _FakeSops()
    rotator = Rotator(sops=cast("Any", sops), state_path=tmp_path / "state.enc.yaml", clock=now)
    rotator.sync_provider_keys("tavily", [{"key_id": "tvly-1", "credits_total": 10}])

    for _ in range(3):
        await rotator.report_failure("tavily", "tvly-1", "error")

    status = rotator.status("tavily")
    key_state = status["keys"][0]
    assert key_state["circuit_state"] == CircuitState.OPEN.value

    clock["value"] = clock["value"] + timedelta(minutes=31)
    key = await rotator.acquire("tavily")
    assert key is not None
    assert key.circuit_state == CircuitState.HALF_OPEN

    await rotator.report_success("tavily", "tvly-1", credits_used=1)
    status_after = rotator.status("tavily")
    assert status_after["keys"][0]["circuit_state"] == CircuitState.CLOSED.value


@pytest.mark.asyncio
async def test_flush_persists_runtime(tmp_path: Path) -> None:
    sops = _FakeSops()
    state_path = tmp_path / "runtime.enc.yaml"
    rotator = Rotator(sops=cast("Any", sops), state_path=state_path)
    rotator.sync_provider_keys("brave", [{"key_id": "brv-1"}])

    await rotator.flush()
    assert "providers" in sops.state
    assert state_path.exists()


@pytest.mark.asyncio
async def test_no_candidate_and_status_all(tmp_path: Path) -> None:
    sops = _FakeSops()
    rotator = Rotator(sops=cast("Any", sops), state_path=tmp_path / "state.enc.yaml")
    rotator.sync_provider_keys("none", [{"key_id": "k1", "credits_total": 0}])
    assert await rotator.acquire("none") is None
    all_status = rotator.status()
    assert "none" in all_status


def test_recover_from_corruption(tmp_path: Path) -> None:
    sops = _FakeSops()
    rotator = Rotator(sops=cast("Any", sops), state_path=tmp_path / "state.enc.yaml")
    rotator.recover_from_corruption("bad yaml")
    assert rotator.status() == {}


@pytest.mark.asyncio
async def test_load_state_from_list_and_strategy_paths(tmp_path: Path) -> None:
    state = {
        "providers": {
            "tavily": {
                "rotation_strategy": "round_robin",
                "keys": [
                    {
                        "key_id": "a",
                        "credits_total": 5,
                        "credits_used": 0,
                        "circuit_state": "closed",
                        "failure_count": 0,
                    },
                    {
                        "key_id": "b",
                        "credits_total": 5,
                        "credits_used": 0,
                        "circuit_state": "closed",
                        "failure_count": 0,
                    },
                ],
            }
        }
    }

    class _StateSops(_FakeSops):
        def decrypt(self, _path: Path) -> dict:
            return state

    state_path = tmp_path / "state.enc.yaml"
    state_path.write_text("enc", encoding="utf-8")
    rotator = Rotator(sops=cast("Any", _StateSops()), state_path=state_path)

    key_rr = await rotator.acquire("tavily", strategy="round_robin")
    assert key_rr is not None

    key_failover = await rotator.acquire("tavily", strategy="failover")
    assert key_failover is not None


def test_load_state_corruption_fallback(tmp_path: Path) -> None:
    class _BrokenSops(_FakeSops):
        def decrypt(self, _path: Path) -> dict:
            raise RuntimeError("broken")

    state_path = tmp_path / "state.enc.yaml"
    state_path.write_text("enc", encoding="utf-8")
    rotator = Rotator(sops=cast("Any", _BrokenSops()), state_path=state_path)
    assert rotator.status() == {}
