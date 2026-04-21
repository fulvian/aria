from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_script_module():
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "oauth_first_setup.py"
    spec = importlib.util.spec_from_file_location("oauth_first_setup", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load scripts/oauth_first_setup.py")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_oauth_code_from_full_redirect_url() -> None:
    module = _load_script_module()
    code = module.extract_oauth_code_from_input(
        "http://localhost:8080/callback?code=abc123&state=expected-state",
        expected_state="expected-state",
    )
    assert code == "abc123"


def test_extract_oauth_code_from_raw_code() -> None:
    module = _load_script_module()
    code = module.extract_oauth_code_from_input("abc123", expected_state="expected-state")
    assert code == "abc123"


def test_extract_oauth_code_rejects_state_mismatch() -> None:
    module = _load_script_module()
    with pytest.raises(module.StateMismatchError):
        module.extract_oauth_code_from_input(
            "http://localhost:8080/callback?code=abc123&state=wrong-state",
            expected_state="expected-state",
        )


def test_extract_oauth_code_raises_on_missing_code() -> None:
    module = _load_script_module()
    with pytest.raises(module.OAuthSetupError):
        module.extract_oauth_code_from_input(
            "http://localhost:8080/callback?state=expected-state",
            expected_state="expected-state",
        )
