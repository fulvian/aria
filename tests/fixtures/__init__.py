# Test configuration for pytest

from pathlib import Path

import pytest


@pytest.fixture
def aria_home(tmp_path: Path) -> Path:
    """Fixture providing a temporary ARIA home directory."""
    home = tmp_path / ".aria"
    home.mkdir()
    (home / "runtime").mkdir()
    (home / "kilocode").mkdir()
    return home


@pytest.fixture
def episodic_db(aria_home: Path) -> Path:
    """Fixture providing a path to a test episodic database."""
    db_path = aria_home / "runtime" / "memory" / "episodic.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path
