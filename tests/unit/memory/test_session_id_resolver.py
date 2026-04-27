# DEPRECATED: _get_session_id removed in Phase D (2026-04-27). See ADR-0005.
# Tests were tied to the remember tool which was removed.

import pytest

pytest.skip(reason="_get_session_id removed in Phase D — see ADR-0005", allow_module_level=True)


def test_get_session_id_uses_env_when_valid() -> None:
    pass  # stub
