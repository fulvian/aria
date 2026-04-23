from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _run_wrapper(*args: str, extra_env: dict[str, str] | None = None) -> list[str]:
    script_path = (
        Path(__file__).resolve().parents[3] / "scripts" / "wrappers" / "google-workspace-wrapper.sh"
    )
    env = os.environ.copy()
    env["WORKSPACE_WRAPPER_DRY_RUN"] = "true"
    if extra_env:
        env.update(extra_env)

    result = subprocess.run(
        ["bash", str(script_path), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def test_wrapper_injects_safe_defaults_when_no_tool_selector() -> None:
    output = _run_wrapper()
    assert output == ["--tool-tier", "core", "--read-only"]


def test_wrapper_keeps_explicit_tool_selection_unchanged() -> None:
    output = _run_wrapper("--tools", "drive", "slides", "--read-only")
    assert output == ["--tools", "drive", "slides", "--read-only"]


def test_wrapper_can_disable_default_read_only_injection() -> None:
    output = _run_wrapper(extra_env={"WORKSPACE_DEFAULT_READ_ONLY": "false"})
    assert output == ["--tool-tier", "core"]
