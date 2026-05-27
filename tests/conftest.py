from __future__ import annotations

from pathlib import Path

import pytest

from semantic_selector.settings import PROJECT_ROOT


@pytest.fixture
def fixtures_dir() -> Path:
    return PROJECT_ROOT / "data" / "fixtures"


@pytest.fixture
def config_dir() -> Path:
    return PROJECT_ROOT / "config"


@pytest.fixture
def index_path(tmp_path: Path) -> Path:
    return tmp_path / "selector-index.sqlite"
