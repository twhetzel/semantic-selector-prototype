from __future__ import annotations

import sqlite3
from pathlib import Path

from semantic_selector.settings import MIGRATIONS_DIR


def apply_migrations(conn: sqlite3.Connection, migrations_dir: Path | None = None) -> None:
    directory = migrations_dir or MIGRATIONS_DIR
    for sql_file in sorted(directory.glob("*.sql")):
        conn.executescript(sql_file.read_text(encoding="utf-8"))


def rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO terms_fts(terms_fts) VALUES('rebuild')")
