from __future__ import annotations

import json
import sqlite3
from typing import Any


def _format_criterion_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["applies_to"] = json.loads(data.pop("applies_to_json", "[]") or "[]")
    data["config"] = json.loads(data.pop("config_json", "{}") or "{}")
    data["table_aligned"] = bool(data.get("table_aligned"))
    data["enabled"] = bool(data.get("enabled"))
    return data


def get_manifest(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM index_manifest LIMIT 1").fetchone()
    return dict(row) if row else None


def list_artifacts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM artifacts ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def get_artifact(conn: sqlite3.Connection, artifact_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
    return dict(row) if row else None


def list_criteria(conn: sqlite3.Connection, *, enabled_only: bool = False) -> list[dict[str, Any]]:
    if enabled_only:
        rows = conn.execute(
            "SELECT * FROM criterion_definitions WHERE enabled = 1 ORDER BY criterion_id"
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM criterion_definitions ORDER BY criterion_id").fetchall()
    return [_format_criterion_row(r) for r in rows]


def get_criterion(conn: sqlite3.Connection, criterion_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM criterion_definitions WHERE criterion_id = ?",
        (criterion_id,),
    ).fetchone()
    return _format_criterion_row(row) if row else None


def get_artifact_criteria(conn: sqlite3.Connection, artifact_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT acv.*, cd.display_name, cd.description, cd.value_type
        FROM artifact_criterion_values acv
        JOIN criterion_definitions cd ON cd.criterion_id = acv.criterion_id
        WHERE acv.artifact_id = ?
        ORDER BY acv.criterion_id
        """,
        (artifact_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def count_terms(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS c FROM terms").fetchone()
    return int(row["c"]) if row else 0


def count_processing_events(conn: sqlite3.Connection, severity: str | None = None) -> int:
    if severity:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM processing_events WHERE severity = ?",
            (severity,),
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) AS c FROM processing_events").fetchone()
    return int(row["c"]) if row else 0
