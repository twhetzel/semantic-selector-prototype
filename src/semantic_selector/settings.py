from __future__ import annotations

from pathlib import Path

from semantic_selector import __version__

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
DEFAULT_INDEX_PATH = PROJECT_ROOT / "data" / "indexes" / "selector-index.sqlite"


def resolve_path(path: str | Path, base: Path | None = None) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    root = base or PROJECT_ROOT
    return (root / p).resolve()
