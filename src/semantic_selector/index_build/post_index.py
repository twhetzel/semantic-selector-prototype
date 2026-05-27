from __future__ import annotations

import json
import sqlite3
from typing import Any


def compute_term_iri_reuse(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT term_iri, GROUP_CONCAT(DISTINCT artifact_id) AS artifact_ids,
               COUNT(DISTINCT artifact_id) AS artifact_count
        FROM terms
        GROUP BY term_iri
        HAVING artifact_count > 1
        """
    ).fetchall()
    for row in rows:
        artifact_ids = sorted(str(row["artifact_ids"]).split(","))
        reuse_count = max(len(artifact_ids) - 1, 0)
        conn.execute(
            """
            INSERT OR REPLACE INTO term_iri_reuse (term_iri, reuse_count, artifact_ids_json)
            VALUES (?, ?, ?)
            """,
            (row["term_iri"], reuse_count, json.dumps(artifact_ids)),
        )


def compute_inbound_owl_import_counts(conn: sqlite3.Connection) -> None:
    ontology_to_artifact: dict[str, str] = {}
    for row in conn.execute(
        "SELECT artifact_id, canonical_uri, version_iri FROM artifacts"
    ).fetchall():
        for iri in (row["canonical_uri"], row["version_iri"]):
            if iri:
                ontology_to_artifact[str(iri)] = row["artifact_id"]

    inbound: dict[str, list[str]] = {}
    for row in conn.execute(
        "SELECT artifact_id, imported_ontology_iri FROM artifact_owl_imports"
    ).fetchall():
        target = ontology_to_artifact.get(str(row["imported_ontology_iri"]))
        if not target:
            continue
        inbound.setdefault(target, []).append(row["artifact_id"])

    for artifact_id, importers in inbound.items():
        unique_importers = sorted(set(importers))
        count = float(len(unique_importers))
        conn.execute(
            """
            UPDATE artifact_criterion_values
            SET numeric_value = ?, evidence_json = ?, computed_at = datetime('now')
            WHERE artifact_id = ? AND criterion_id = 'inbound_owl_import_count'
            """,
            (
                count,
                json.dumps(
                    {
                        "inbound_import_count": len(unique_importers),
                        "importing_artifact_ids": unique_importers,
                    }
                ),
                artifact_id,
            ),
        )

    for row in conn.execute("SELECT artifact_id FROM artifacts").fetchall():
        artifact_id = row["artifact_id"]
        if artifact_id in inbound:
            continue
        conn.execute(
            """
            UPDATE artifact_criterion_values
            SET numeric_value = 0.0,
                evidence_json = ?,
                computed_at = datetime('now')
            WHERE artifact_id = ? AND criterion_id = 'inbound_owl_import_count'
            """,
            (
                json.dumps({"inbound_import_count": 0, "importing_artifact_ids": []}),
                artifact_id,
            ),
        )


def load_term_reuse_map(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    try:
        rows = conn.execute(
            "SELECT term_iri, reuse_count, artifact_ids_json FROM term_iri_reuse"
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        artifact_ids = json.loads(row["artifact_ids_json"])
        out[row["term_iri"]] = {
            "reuse_count": int(row["reuse_count"]),
            "artifact_ids": artifact_ids,
        }
    return out
