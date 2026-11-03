from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def repo_root(backend_root: Path) -> Path:
    return backend_root.parent
