from __future__ import annotations

import json
import re
import sqlite3
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from rdflib.exceptions import ParserError

from semantic_selector import __version__
from semantic_selector.db.connection import connect, init_database, transaction
from semantic_selector.index_build.post_index import (
    compute_inbound_owl_import_counts,
    compute_term_iri_reuse,
    load_term_reuse_map,
)
from semantic_selector.index_build.progress import BuildProgressReporter
from semantic_selector.criteria.enforced import (
    EnforcedSelectionConfig,
    apply_enforced_selection,
)
from semantic_selector.criteria.registry import load_criteria_config
from semantic_selector.db.queries import (
    count_processing_events,
    count_terms,
    get_criterion,
    get_manifest,
)
from semantic_selector.db.schema import rebuild_fts
from semantic_selector.db.writer import (
    insert_artifact,
    insert_artifact_owl_import,
    insert_criterion_value,
    insert_manifest,
    insert_term,
    insert_term_relation,
    log_processing_event,
    upsert_criterion_definition,
)
from semantic_selector.evaluators.registry import create_evaluator
from semantic_selector.ranking.term_evidence import (
    build_term_evidence,
    compute_term_match_frequency,
)
from semantic_selector.extractors.base import ExtractorResult, execute_extractor
from semantic_selector.extractors.normalization import join_extractor_results, normalize_label
from semantic_selector.extractors.registry import ExtractorRegistry
from semantic_selector.ingestion.local_files import LocalFileSourceAdapter
from semantic_selector.ingestion.provenance import sha256_file, utc_now_iso
from semantic_selector.models import sha256_json
from semantic_selector.ranking.explanations import build_selection_explanation
from semantic_selector.ranking.scorer import (
    apply_count_criterion_normalization,
    compute_overall_score,
    normalize_weights,
)
from semantic_selector.ranking.term_match import (
    classify_term_match,
    compute_lexical_text_scores,
    curie_to_obo_iri,
    rank_term_rows,
)
from semantic_selector.rdf.build_config import BuildConfig
from semantic_selector.rdf.build_report import ArtifactBuildReport, ExtractorBuildMetric
from semantic_selector.rdf.factory import create_rdf_backend, get_pyoxigraph_version
from semantic_selector.rdf.pyoxigraph_backend import PyoxigraphBackend


@dataclass
class BuildReport:
    snapshot_id: str
    artifacts_configured: int
    artifacts_indexed: int
    artifacts_failed: int
    terms_indexed: int
    criteria_computed: int
    warnings: int
    index_path: str
    rdf_backend: str = "rdflib"
    retain_rdf_store_after_build: bool = False
    sqlite_index_size_bytes: int = 0
    total_build_duration_seconds: float = 0.0
    artifact_reports: list[ArtifactBuildReport] = field(default_factory=list)
    status: str = "success"

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "artifacts_configured": self.artifacts_configured,
            "artifacts_indexed": self.artifacts_indexed,
            "artifacts_failed": self.artifacts_failed,
            "terms_indexed": self.terms_indexed,
            "criteria_computed": self.criteria_computed,
            "warnings": self.warnings,
            "index_path": self.index_path,
            "rdf_backend": self.rdf_backend,
            "retain_rdf_store_after_build": self.retain_rdf_store_after_build,
            "sqlite_index_size_bytes": self.sqlite_index_size_bytes,
            "total_build_duration_seconds": round(self.total_build_duration_seconds, 4),
            "status": self.status,
            "artifact_reports": [report.to_dict() for report in self.artifact_reports],
        }


def _load_enforced_selection_config(conn: sqlite3.Connection) -> EnforcedSelectionConfig:
    row = get_criterion(conn, "enforced_selection_list")
    if row is None or not row.get("enabled"):
        return EnforcedSelectionConfig(False, frozenset(), frozenset(), frozenset(), frozenset())
    raw_config = row.get("config") or {}
    allowed_artifacts = frozenset(raw_config.get("allowed_artifact_ids") or [])
    blocked_artifacts = frozenset(raw_config.get("blocked_artifact_ids") or [])
    allowed_terms = frozenset(raw_config.get("allowed_term_iris") or [])
    blocked_terms = frozenset(raw_config.get("blocked_term_iris") or [])
    if not any((allowed_artifacts, blocked_artifacts, allowed_terms, blocked_terms)):
        return EnforcedSelectionConfig(False, frozenset(), frozenset(), frozenset(), frozenset())
    return EnforcedSelectionConfig(
        enabled=True,
        allowed_artifact_ids=allowed_artifacts,
        blocked_artifact_ids=blocked_artifacts,
        allowed_term_iris=allowed_terms,
        blocked_term_iris=blocked_terms,
    )


def _load_artifact_ontology_scores(
    conn: sqlite3.Connection,
    artifact_ids: set[str],
    ranking_weights: dict[str, float],
) -> dict[str, float]:
    if not artifact_ids:
        return {}

    placeholders = ",".join("?" * len(artifact_ids))
    rows = conn.execute(
        f"""
        SELECT acv.artifact_id, acv.criterion_id, acv.numeric_value, cd.role
        FROM artifact_criterion_values acv
        JOIN criterion_definitions cd ON cd.criterion_id = acv.criterion_id
        WHERE acv.artifact_id IN ({placeholders}) AND cd.enabled = 1
        """,
        list(artifact_ids),
    ).fetchall()

    by_artifact: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        criterion_id = row["criterion_id"]
        if (
            criterion_id in ranking_weights
            and ranking_weights[criterion_id] > 0
            and row["role"] in {"ranking", "ranking_and_evidence"}
        ):
            by_artifact[row["artifact_id"]][criterion_id] = float(row["numeric_value"] or 0.0)

    normalized = apply_count_criterion_normalization(
        artifact_scores=by_artifact,
        ranking_weights=ranking_weights,
    )
    return {
        artifact_id: compute_overall_score(
            term_match_frequency=1.0,
            criterion_scores=normalized.get(artifact_id, {}),
            weights=ranking_weights,
        )
        for artifact_id in artifact_ids
    }


def _term_search_row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row["artifact_id"]), str(row["term_iri"]))


def _append_term_search_scope_filters(
    sql: str,
    params: list[Any],
    *,
    include_obsolete: bool,
    artifact_ids: list[str] | None,
    repository_ids: list[str] | None,
) -> tuple[str, list[Any]]:
    if not include_obsolete:
        sql += " AND t.is_obsolete = 0"
    if artifact_ids:
        sql += f" AND t.artifact_id IN ({','.join('?' * len(artifact_ids))})"
        params.extend(artifact_ids)
    if repository_ids:
        sql += f" AND a.repository_id IN ({','.join('?' * len(repository_ids))})"
        params.extend(repository_ids)
    return sql, params


def _fetch_direct_lexical_matches(
    conn: sqlite3.Connection,
    query: str,
    *,
    artifact_ids: list[str] | None,
    repository_ids: list[str] | None,
    include_obsolete: bool,
    exclude_term_iri: str | None = None,
) -> list[dict[str, Any]]:
    query_norm = normalize_label(query)
    if not query_norm:
        return []

    base_sql = """
        SELECT
            t.*,
            a.name AS artifact_name,
            a.declared_version,
            a.version_iri
        FROM terms t
        JOIN artifacts a ON a.artifact_id = t.artifact_id
        WHERE 1=1
    """
    matches: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    label_sql, label_params = _append_term_search_scope_filters(
        base_sql + " AND t.normalized_label = ?",
        [query_norm],
        include_obsolete=include_obsolete,
        artifact_ids=artifact_ids,
        repository_ids=repository_ids,
    )
    if exclude_term_iri:
        label_sql += " AND t.term_iri != ?"
        label_params.append(exclude_term_iri)
    for row in conn.execute(label_sql, label_params).fetchall():
        item = dict(row)
        key = _term_search_row_key(item)
        if key not in seen:
            seen.add(key)
            matches.append(item)

    synonym_sql, synonym_params = _append_term_search_scope_filters(
        base_sql
        + """
        AND t.synonyms_text != ''
        AND (
            lower(t.synonyms_text) = ?
            OR lower(t.synonyms_text) LIKE ?
            OR lower(t.synonyms_text) LIKE ?
            OR lower(t.synonyms_text) LIKE ?
        )
        """,
        [
            query_norm,
            f"{query_norm} | %",
            f"% | {query_norm} | %",
            f"% | {query_norm}",
        ],
        include_obsolete=include_obsolete,
        artifact_ids=artifact_ids,
        repository_ids=repository_ids,
    )
    if exclude_term_iri:
        synonym_sql += " AND t.term_iri != ?"
        synonym_params.append(exclude_term_iri)
    for row in conn.execute(synonym_sql, synonym_params).fetchall():
        item = dict(row)
        key = _term_search_row_key(item)
        if key in seen:
            continue
        if classify_term_match(item, query) != "synonym_exact":
            continue
        seen.add(key)
        matches.append(item)

    return matches


def _load_default_ranking_weights(conn: sqlite3.Connection) -> dict[str, float]:
    rows = conn.execute(
        """
        SELECT criterion_id, default_weight, role
        FROM criterion_definitions
        WHERE enabled = 1
        """
    ).fetchall()
    weights: dict[str, float] = {}
    for row in rows:
        if row["role"] in {"ranking", "ranking_and_evidence"} and row["default_weight"] > 0:
            weights[row["criterion_id"]] = float(row["default_weight"])
    if not weights:
        return {
            "term_match_frequency": 0.50,
            "definition_coverage": 0.35,
            "inbound_owl_import_count": 0.15,
        }
    return weights


def _split_stored_criterion_values(
    rows: list[sqlite3.Row],
    *,
    ranking_weights: dict[str, float],
) -> tuple[dict[str, float], dict[str, Any]]:
    scores: dict[str, float] = {}
    evidence: dict[str, Any] = {}
    for row in rows:
        cid = row["criterion_id"]
        role = row["role"]
        numeric = float(row["numeric_value"] or 0.0)
        payload = json.loads(row["evidence_json"])
        if cid == "inbound_owl_import_count":
            evidence[cid] = int(numeric)
            evidence["importing_artifact_ids"] = payload.get("importing_artifact_ids", [])
        if cid in ranking_weights and ranking_weights[cid] > 0:
            scores[cid] = numeric
        elif role in {"supporting_evidence", "provenance_evidence", "descriptive_evidence"}:
            if cid == "has_version_metadata":
                evidence[cid] = numeric >= 1.0
            elif cid == "multilanguage_annotations":
                evidence["annotation_languages"] = payload.get("languages", [])
            elif cid == "synonym_coverage":
                evidence[cid] = numeric
            elif cid != "inbound_owl_import_count":
                evidence[cid] = numeric
    return scores, evidence


class IndexService:
    def __init__(self, index_path: Path) -> None:
        self.index_path = index_path

    def _conn(self, *, read_only: bool = True) -> sqlite3.Connection:
        if not self.index_path.exists():
            raise FileNotFoundError(f"Index not found: {self.index_path}")
        return connect(self.index_path, read_only=read_only)

    def get_manifest(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            manifest = get_manifest(conn)
            if manifest is None:
                raise ValueError("Index manifest missing")
            return manifest
        finally:
            conn.close()

    def search_terms(
        self,
        *,
        query: str,
        artifact_ids: list[str] | None = None,
        repository_ids: list[str] | None = None,
        include_obsolete: bool = False,
        limit: int = 20,
        include_term_evidence: bool = True,
    ) -> dict[str, Any]:
        conn = self._conn()
        try:
            manifest = get_manifest(conn)
            enforced = _load_enforced_selection_config(conn)
            reuse_map = load_term_reuse_map(conn)
            ranking_weights = _load_default_ranking_weights(conn)
            direct_rows: list[dict[str, Any]] = []
            seen_keys: set[tuple[str, str]] = set()
            curie_iri = curie_to_obo_iri(query)

            def _add_direct_row(row: dict[str, Any]) -> None:
                key = _term_search_row_key(row)
                if key not in seen_keys:
                    seen_keys.add(key)
                    direct_rows.append(row)

            if curie_iri:
                direct_sql = """
                    SELECT
                        t.*,
                        a.name AS artifact_name,
                        a.declared_version,
                        a.version_iri
                    FROM terms t
                    JOIN artifacts a ON a.artifact_id = t.artifact_id
                    WHERE t.term_iri = ?
                """
                direct_params: list[Any] = [curie_iri]
                if not include_obsolete:
                    direct_sql += " AND t.is_obsolete = 0"
                if artifact_ids:
                    direct_sql += f" AND t.artifact_id IN ({','.join('?' * len(artifact_ids))})"
                    direct_params.extend(artifact_ids)
                if repository_ids:
                    direct_sql += f" AND a.repository_id IN ({','.join('?' * len(repository_ids))})"
                    direct_params.extend(repository_ids)
                direct = conn.execute(direct_sql, direct_params).fetchone()
                if direct is not None:
                    _add_direct_row(dict(direct))

            for row in _fetch_direct_lexical_matches(
                conn,
                query,
                artifact_ids=artifact_ids,
                repository_ids=repository_ids,
                include_obsolete=include_obsolete,
                exclude_term_iri=curie_iri,
            ):
                _add_direct_row(row)

            fts_query = _sanitize_fts_query(query)
            sql = """
                SELECT
                    t.*,
                    a.name AS artifact_name,
                    a.declared_version,
                    a.version_iri,
                    bm25(terms_fts) AS bm25_score
                FROM terms_fts
                JOIN terms t ON t.term_pk = terms_fts.rowid
                JOIN artifacts a ON a.artifact_id = t.artifact_id
                WHERE terms_fts MATCH ?
            """
            params: list[Any] = [fts_query]
            if not include_obsolete:
                sql += " AND t.is_obsolete = 0"
            if artifact_ids:
                sql += f" AND t.artifact_id IN ({','.join('?' * len(artifact_ids))})"
                params.extend(artifact_ids)
            if repository_ids:
                sql += f" AND a.repository_id IN ({','.join('?' * len(repository_ids))})"
                params.extend(repository_ids)
            if curie_iri:
                sql += " AND t.term_iri != ?"
                params.append(curie_iri)
            sql += " ORDER BY bm25_score LIMIT ?"
            candidate_limit = min(max(limit * 20, 200), 500)
            params.append(candidate_limit)
            fts_rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
            fts_rows = [row for row in fts_rows if _term_search_row_key(row) not in seen_keys]
            row_dicts = direct_rows + fts_rows
            bm25_values = [-1000.0 for _ in direct_rows] + [
                float(row["bm25_score"]) for row in fts_rows
            ]
            ontology_scores = _load_artifact_ontology_scores(
                conn,
                {row["artifact_id"] for row in row_dicts},
                ranking_weights,
            )
            ranked = rank_term_rows(
                row_dicts,
                query=query,
                bm25_scores=bm25_values,
                ontology_scores=ontology_scores,
            )
            ranked = ranked[:limit]
            text_scores = compute_lexical_text_scores(len(ranked))
            results = []
            for (row, _bm25, match_type), text_score in zip(ranked, text_scores, strict=True):
                exclusion = apply_enforced_selection(
                    artifact_id=row["artifact_id"],
                    term_iri=row["term_iri"],
                    config=enforced,
                )
                if exclusion:
                    continue
                results.append(
                    self._format_term_search_result(
                        row,
                        match_type=match_type,
                        text_score=text_score,
                        reuse_map=reuse_map,
                        include_term_evidence=include_term_evidence,
                    )
                )
            return {
                "query": query,
                "snapshot_id": manifest["snapshot_id"] if manifest else None,
                "results": results,
            }
        finally:
            conn.close()

    @staticmethod
    def _format_term_search_result(
        row: dict[str, Any],
        *,
        match_type: str,
        text_score: float,
        reuse_map: dict[str, dict[str, Any]] | None = None,
        include_term_evidence: bool = True,
    ) -> dict[str, Any]:
        synonyms = [s for s in (row.get("synonyms_text") or "").split(" | ") if s]
        definitions = [d for d in (row.get("definitions_text") or "").split(" | ") if d]
        result = {
            "artifact_id": row["artifact_id"],
            "artifact_name": row["artifact_name"],
            "artifact_version": row["declared_version"] or row["version_iri"],
            "term_iri": row["term_iri"],
            "preferred_label": row["preferred_label"],
            "synonyms": synonyms,
            "definition": definitions[0] if definitions else None,
            "match_type": match_type,
            "text_score": text_score,
            "normalized_label": row["normalized_label"],
            "shared_label_group": row["normalized_label"],
        }
        if include_term_evidence:
            result["term_evidence"] = build_term_evidence(
                row,
                reuse_info=(reuse_map or {}).get(row["term_iri"]),
            )
        return result

    def select_artifacts(
        self,
        *,
        query: str | None = None,
        queries: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        weights: dict[str, float] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        filters = filters or {}
        concept_queries = [q.strip() for q in (queries or []) if q and q.strip()]
        if not concept_queries:
            if not query or not query.strip():
                raise ValueError("Either query or queries must be provided")
            concept_queries = [query.strip()]

        conn = self._conn()
        try:
            default_weights = _load_default_ranking_weights(conn)
            request_weights = {**default_weights, **(weights or {})}
            normalized_w = normalize_weights(request_weights)

            manifest = get_manifest(conn)
            enforced = _load_enforced_selection_config(conn)
            reuse_map = load_term_reuse_map(conn)
            filter_exclusions: list[str] = []

            by_artifact: dict[str, list[dict[str, Any]]] = {}
            matched_queries_by_artifact: dict[str, set[str]] = defaultdict(set)

            for concept_query in concept_queries:
                term_hits = self.search_terms(
                    query=concept_query,
                    artifact_ids=filters.get("artifact_ids"),
                    repository_ids=filters.get("repository_ids"),
                    include_obsolete=not filters.get("exclude_obsolete_terms", True),
                    limit=200,
                    include_term_evidence=True,
                )
                for hit in term_hits["results"]:
                    if filters.get("require_definition") and not hit.get("definition"):
                        continue
                    exclusion = apply_enforced_selection(
                        artifact_id=hit["artifact_id"],
                        term_iri=hit["term_iri"],
                        config=enforced,
                    )
                    if exclusion:
                        if exclusion not in filter_exclusions:
                            filter_exclusions.append(exclusion)
                        continue
                    by_artifact.setdefault(hit["artifact_id"], []).append(hit)
                    matched_queries_by_artifact[hit["artifact_id"]].add(concept_query)

            candidates: list[dict[str, Any]] = []
            total_queries = len(concept_queries)
            for artifact_id, hits in by_artifact.items():
                matched_count = len(matched_queries_by_artifact.get(artifact_id, set()))
                term_match_frequency = compute_term_match_frequency(matched_count, total_queries)

                criterion_rows = conn.execute(
                    """
                    SELECT acv.*, cd.display_name, cd.role
                    FROM artifact_criterion_values acv
                    JOIN criterion_definitions cd ON cd.criterion_id = acv.criterion_id
                    WHERE acv.artifact_id = ? AND cd.enabled = 1
                    """,
                    (artifact_id,),
                ).fetchall()
                stored_scores, ontology_evidence = _split_stored_criterion_values(
                    criterion_rows,
                    ranking_weights=request_weights,
                )
                ontology_scores = {
                    "term_match_frequency": term_match_frequency,
                    **stored_scores,
                }
                criterion_evidence = {
                    "term_match_frequency": {
                        "matched_queries": matched_count,
                        "total_queries": total_queries,
                        "matched_query_strings": sorted(
                            matched_queries_by_artifact.get(artifact_id, set())
                        ),
                    },
                    **{
                        row["criterion_id"]: json.loads(row["evidence_json"])
                        for row in criterion_rows
                        if row["criterion_id"] in stored_scores
                    },
                }

                hits.sort(key=lambda h: h["text_score"], reverse=True)
                best = hits[0]
                matching_terms = [
                    {
                        "term_iri": hit["term_iri"],
                        "preferred_label": hit["preferred_label"],
                        "match_type": hit["match_type"],
                        "text_score": hit["text_score"],
                        "term_evidence": hit.get("term_evidence")
                        or build_term_evidence(
                            hit,
                            reuse_info=reuse_map.get(hit["term_iri"]),
                        ),
                    }
                    for hit in hits[:20]
                ]

                artifact = conn.execute(
                    "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
                ).fetchone()
                candidates.append(
                    {
                        "artifact_id": artifact_id,
                        "artifact_name": artifact["name"],
                        "artifact_version": artifact["declared_version"] or artifact["version_iri"],
                        "ontology_scores": ontology_scores,
                        "ontology_evidence": ontology_evidence,
                        "criterion_evidence": criterion_evidence,
                        "matching_terms": matching_terms,
                        "best_term_match": {
                            "term_iri": best["term_iri"],
                            "preferred_label": best["preferred_label"],
                            "match_type": best["match_type"],
                            "term_match_score": best["text_score"],
                        },
                        "provenance": {
                            "repository_id": artifact["repository_id"],
                            "content_sha256": artifact["content_sha256"],
                            "snapshot_id": manifest["snapshot_id"] if manifest else None,
                        },
                    }
                )

            normalized_scores = apply_count_criterion_normalization(
                artifact_scores={
                    candidate["artifact_id"]: candidate["ontology_scores"] for candidate in candidates
                },
                ranking_weights=request_weights,
            )

            ranked: list[dict[str, Any]] = []
            for candidate in candidates:
                artifact_id = candidate["artifact_id"]
                ontology_scores = normalized_scores.get(artifact_id, candidate["ontology_scores"])
                ranking_inputs = {
                    k: v for k, v in ontology_scores.items() if k in request_weights
                }
                overall = compute_overall_score(
                    term_match_frequency=ontology_scores["term_match_frequency"],
                    criterion_scores={
                        k: v for k, v in ranking_inputs.items() if k != "term_match_frequency"
                    },
                    weights=request_weights,
                )
                explanation = build_selection_explanation(
                    match_type=candidate["best_term_match"]["match_type"],
                    criterion_scores={
                        k: v
                        for k, v in ontology_scores.items()
                        if k in request_weights and request_weights[k] > 0
                    },
                    criterion_evidence=candidate["criterion_evidence"],
                    filter_exclusions=filter_exclusions or None,
                )
                ranked.append(
                    {
                        "artifact_id": artifact_id,
                        "artifact_name": candidate["artifact_name"],
                        "artifact_version": candidate["artifact_version"],
                        "overall_score": overall,
                        "ontology_scores": {
                            k: v
                            for k, v in ontology_scores.items()
                            if k in request_weights and request_weights[k] > 0
                        },
                        "ontology_evidence": candidate["ontology_evidence"],
                        "matching_terms": candidate["matching_terms"],
                        "best_term_match": candidate["best_term_match"],
                        "criterion_scores": {
                            k: v
                            for k, v in ontology_scores.items()
                            if k in request_weights and request_weights[k] > 0
                        },
                        "explanation": explanation,
                        "provenance": candidate["provenance"],
                    }
                )
            ranked.sort(key=lambda r: r["overall_score"], reverse=True)
            for idx, item in enumerate(ranked[:limit], start=1):
                item["rank"] = idx
            return {
                "query": concept_queries[0] if len(concept_queries) == 1 else None,
                "queries": concept_queries,
                "snapshot_id": manifest["snapshot_id"] if manifest else None,
                "normalized_weights": normalized_w,
                "ontology_results": ranked[:limit],
                "results": ranked[:limit],
                "filter_exclusions": filter_exclusions,
            }
        finally:
            conn.close()

    def compare_artifacts(
        self,
        *,
        artifact_ids: list[str],
        query: str | None = None,
    ) -> dict[str, Any]:
        conn = self._conn()
        try:
            manifest = get_manifest(conn)
            artifacts = []
            differences: list[dict[str, Any]] = []
            for artifact_id in artifact_ids:
                artifact = conn.execute(
                    "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
                ).fetchone()
                if artifact is None:
                    continue
                criteria = conn.execute(
                    """
                    SELECT acv.criterion_id, acv.numeric_value, acv.evidence_json, cd.display_name
                    FROM artifact_criterion_values acv
                    JOIN criterion_definitions cd ON cd.criterion_id = acv.criterion_id
                    WHERE acv.artifact_id = ?
                    """,
                    (artifact_id,),
                ).fetchall()
                artifacts.append(
                    {
                        "artifact_id": artifact_id,
                        "name": artifact["name"],
                        "version": artifact["declared_version"] or artifact["version_iri"],
                        "criteria": {
                            row["criterion_id"]: {
                                "value": row["numeric_value"],
                                "display_name": row["display_name"],
                            }
                            for row in criteria
                        },
                    }
                )
            if len(artifacts) >= 2:
                keys = set(artifacts[0]["criteria"]).union(
                    *(set(a["criteria"]) for a in artifacts[1:])
                )
                for key in sorted(keys):
                    values = [a["criteria"].get(key, {}).get("value") for a in artifacts]
                    if len(set(values)) > 1:
                        differences.append({"criterion_id": key, "values": values})

            matching_terms = []
            if query:
                search = self.search_terms(query=query, artifact_ids=artifact_ids, limit=50)
                matching_terms = search["results"]
            return {
                "snapshot_id": manifest["snapshot_id"] if manifest else None,
                "artifacts": artifacts,
                "differences": differences,
                "matching_terms": matching_terms,
            }
        finally:
            conn.close()


def build_index(
    *,
    sources_path: Path,
    extractors_path: Path,
    criteria_path: Path,
    output_path: Path,
    report_path: Path | None = None,
    progress: BuildProgressReporter | None = None,
) -> BuildReport:
    build_started = time.perf_counter()
    sources_raw = yaml.safe_load(sources_path.read_text(encoding="utf-8"))
    extractors_raw = yaml.safe_load(extractors_path.read_text(encoding="utf-8"))
    criteria_raw = yaml.safe_load(criteria_path.read_text(encoding="utf-8"))
    build_config = BuildConfig.from_sources_config(sources_raw)

    snapshot_id = sources_raw.get("index", {}).get("snapshot_id", "local-demo")
    adapter = LocalFileSourceAdapter(sources_raw)
    artifacts = adapter.list_artifacts()
    extractor_registry = ExtractorRegistry.from_yaml(extractors_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        suffix=".sqlite", dir=output_path.parent, delete=False
    ) as tmp:
        temp_path = Path(tmp.name)

    warnings = 0
    indexed = 0
    failed = 0
    criteria_computed = 0
    artifact_reports: list[ArtifactBuildReport] = []
    pyoxigraph_backends: list[PyoxigraphBackend] = []
    build_status = "success"
    progress = progress or BuildProgressReporter()
    artifact_total = len(artifacts)
    extractor_total = len(extractor_registry.enabled)

    progress.build_started(
        artifact_count=artifact_total,
        rdf_backend=build_config.rdf_backend,
        output_path=output_path,
    )

    try:
        init_database(temp_path)
        conn = connect(temp_path)

        manifest_notes = {
            "rdf_backend": build_config.rdf_backend,
            "retain_rdf_store_after_build": build_config.retain_rdf_store_after_build,
            "pyoxigraph_version": get_pyoxigraph_version(),
            "source_input_format": "native_owl_rdf",
        }

        with transaction(conn):
            insert_manifest(
                conn,
                snapshot_id=snapshot_id,
                selector_version=__version__,
                evaluator_config_hash=sha256_json(criteria_raw),
                extractor_config_hash=extractor_registry.config_hash(extractors_raw),
                extractor_queries_hash=extractor_registry.queries_hash(),
                source_config_hash=sha256_json(sources_raw),
                notes=json.dumps(manifest_notes, sort_keys=True),
            )

            criteria_configs = load_criteria_config(criteria_raw)
            evaluators = []
            for cfg in criteria_configs:
                upsert_criterion_definition(
                    conn,
                    criterion_id=cfg.id,
                    display_name=cfg.display_name,
                    description=cfg.description,
                    value_type="numeric",
                    evaluator_id=cfg.evaluator,
                    evaluator_version="0.1.0",
                    enabled=cfg.enabled,
                    default_weight=cfg.default_weight,
                    category=cfg.category,
                    source_criterion=cfg.source_criterion,
                    applies_to=cfg.applies_to,
                    role=cfg.role,
                    table_aligned=cfg.table_aligned,
                    evaluation_stage=cfg.evaluation_stage,
                    config=cfg.config,
                )
                if cfg.evaluator and cfg.evaluation_stage == "index_build" and cfg.enabled:
                    evaluators.append(create_evaluator(cfg.evaluator))

            for artifact_index, artifact in enumerate(artifacts, start=1):
                artifact_started = time.perf_counter()
                progress.artifact_started(
                    index=artifact_index,
                    total=artifact_total,
                    artifact_id=artifact.artifact_id,
                )
                artifact_report = ArtifactBuildReport(
                    artifact_id=artifact.artifact_id,
                    source_filename="",
                    source_file_size_bytes=0,
                    rdf_backend=build_config.rdf_backend,
                    store_path=None,
                    retain_rdf_store_after_build=build_config.retain_rdf_store_after_build,
                    load_duration_seconds=0.0,
                    triple_count=0,
                    store_size_bytes=None,
                )
                backend = create_rdf_backend(build_config, artifact_id=artifact.artifact_id)
                if isinstance(backend, PyoxigraphBackend):
                    pyoxigraph_backends.append(backend)

                try:
                    source_path = adapter.materialize_artifact(artifact, output_path.parent)
                except FileNotFoundError as exc:
                    failed += 1
                    artifact_report.status = "failed"
                    artifact_report.message = str(exc)
                    artifact_report.total_build_duration_seconds = time.perf_counter() - artifact_started
                    artifact_reports.append(artifact_report)
                    progress.artifact_finished(
                        artifact_id=artifact.artifact_id,
                        duration_seconds=artifact_report.total_build_duration_seconds,
                        status="failed",
                    )
                    log_processing_event(
                        conn,
                        artifact_id=artifact.artifact_id,
                        event_type="source_missing",
                        severity="error",
                        message=str(exc),
                    )
                    backend.close()
                    continue

                checksum = sha256_file(source_path)
                retrieved_at = utc_now_iso()
                artifact_report.source_filename = source_path.name
                artifact_report.source_file_size_bytes = source_path.stat().st_size

                progress.artifact_phase(artifact_id=artifact.artifact_id, message="loading RDF...")
                try:
                    load_result = backend.load_artifact(source_path)
                    parsed_at = utc_now_iso()
                    parse_status = "success"
                    parse_message = None
                    artifact_report.load_duration_seconds = load_result.load_duration_seconds
                    artifact_report.triple_count = load_result.triple_count
                    artifact_report.store_path = (
                        str(load_result.store_path) if load_result.store_path else None
                    )
                    artifact_report.store_size_bytes = load_result.store_size_bytes
                    artifact_report.reused_existing_store = load_result.reused_existing_store
                    if load_result.reused_existing_store:
                        load_message = (
                            f"reusing cached store ({load_result.triple_count:,} triples)"
                        )
                    elif load_result.load_duration_seconds > 0:
                        load_message = (
                            f"loaded {load_result.triple_count:,} triples in "
                            f"{load_result.load_duration_seconds:.1f}s"
                        )
                    else:
                        load_message = f"loaded {load_result.triple_count:,} triples"
                    progress.artifact_phase(
                        artifact_id=artifact.artifact_id,
                        message=load_message,
                    )
                except (ParserError, Exception) as exc:
                    failed += 1
                    parsed_at = utc_now_iso()
                    parse_status = "failed"
                    parse_message = str(exc)
                    artifact_report.status = "failed"
                    artifact_report.message = parse_message
                    artifact_report.total_build_duration_seconds = time.perf_counter() - artifact_started
                    artifact_reports.append(artifact_report)
                    progress.artifact_finished(
                        artifact_id=artifact.artifact_id,
                        duration_seconds=artifact_report.total_build_duration_seconds,
                        status="failed",
                    )
                    insert_artifact(
                        conn,
                        artifact_id=artifact.artifact_id,
                        repository_id=artifact.repository_id,
                        name=artifact.name,
                        canonical_uri=None,
                        source_type=artifact.source_type,
                        source_reference=str(source_path),
                        access_scope=artifact.access_scope,
                        declared_version=artifact.declared_version,
                        version_iri=None,
                        content_sha256=checksum,
                        retrieved_at=retrieved_at,
                        parsed_at=parsed_at,
                        triple_count=0,
                        parse_status=parse_status,
                        parse_message=parse_message,
                    )
                    log_processing_event(
                        conn,
                        artifact_id=artifact.artifact_id,
                        event_type="parse_error",
                        severity="error",
                        message=parse_message,
                    )
                    backend.close()
                    if isinstance(backend, PyoxigraphBackend) and not build_config.retain_rdf_store_after_build:
                        backend.cleanup_store()
                    continue

                progress.artifact_phase(
                    artifact_id=artifact.artifact_id,
                    message=f"running {extractor_total} SPARQL extractors...",
                )
                extraction_started = time.perf_counter()
                extractor_results: dict[str, ExtractorResult] = {}
                for definition in extractor_registry.enabled:
                    metric = ExtractorBuildMetric(
                        extractor_id=definition.id,
                        query_file=definition.query_file.name,
                        query_hash=extractor_registry.query_hash(definition),
                        duration_seconds=0.0,
                        row_count=0,
                        status="success",
                    )
                    extractor_started = time.perf_counter()
                    try:
                        result = execute_extractor(backend, definition)
                        extractor_results[definition.id] = result
                        metric.duration_seconds = time.perf_counter() - extractor_started
                        metric.row_count = len(result.rows)
                    except Exception as exc:
                        warnings += 1
                        metric.duration_seconds = time.perf_counter() - extractor_started
                        metric.status = "failed"
                        metric.message = str(exc)
                        log_processing_event(
                            conn,
                            artifact_id=artifact.artifact_id,
                            event_type="extractor_error",
                            severity="warning",
                            message=str(exc),
                            details={"extractor_id": definition.id},
                        )
                        extractor_results[definition.id] = ExtractorResult(
                            definition.id, definition.version, []
                        )
                    artifact_report.extractors.append(metric)
                artifact_report.extraction_duration_seconds = time.perf_counter() - extraction_started
                progress.artifact_phase(
                    artifact_id=artifact.artifact_id,
                    message=f"extracted in {artifact_report.extraction_duration_seconds:.1f}s",
                )

                facts = join_extractor_results(artifact.artifact_id, extractor_results)
                version_iri_vals = facts.metadata.get("version_iri", [])
                version_iri = str(version_iri_vals[0]) if version_iri_vals else None
                ontology_iri_vals = facts.metadata.get("ontology_iri", [])
                canonical_uri = str(ontology_iri_vals[0]) if ontology_iri_vals else None

                progress.artifact_phase(
                    artifact_id=artifact.artifact_id,
                    message="writing SQLite index...",
                )
                sqlite_write_started = time.perf_counter()
                insert_artifact(
                    conn,
                    artifact_id=artifact.artifact_id,
                    repository_id=artifact.repository_id,
                    name=artifact.name,
                    canonical_uri=canonical_uri,
                    source_type=artifact.source_type,
                    source_reference=str(source_path),
                    access_scope=artifact.access_scope,
                    declared_version=artifact.declared_version,
                    version_iri=version_iri,
                    content_sha256=checksum,
                    retrieved_at=retrieved_at,
                    parsed_at=parsed_at,
                    triple_count=artifact_report.triple_count,
                    parse_status=parse_status,
                    parse_message=parse_message,
                )

                for term in facts.terms:
                    insert_term(
                        conn,
                        artifact_id=artifact.artifact_id,
                        term_iri=str(term["term_iri"]),
                        preferred_label=term.get("preferred_label"),
                        normalized_label=term.get("normalized_label"),
                        synonyms_text=term.get("synonyms_text", ""),
                        definitions_text=term.get("definitions_text", ""),
                        language_tags_text=term.get("language_tags_text", ""),
                        is_obsolete=bool(term.get("is_obsolete")),
                        parent_count=int(term.get("parent_count", 0)),
                        child_count=int(term.get("child_count", 0)),
                        mapping_count=int(term.get("mapping_count", 0)),
                    )

                for imported_iri in facts.metadata.get("owl_import_iris", []):
                    insert_artifact_owl_import(
                        conn,
                        artifact_id=artifact.artifact_id,
                        imported_ontology_iri=str(imported_iri),
                    )

                for relation in facts.relations:
                    insert_term_relation(
                        conn,
                        artifact_id=artifact.artifact_id,
                        subject_iri=str(relation["subject_iri"]),
                        predicate_iri=str(relation["predicate_iri"]),
                        object_iri=str(relation["object_iri"]),
                        relation_type=str(relation["relation_type"]),
                    )
                artifact_report.sqlite_write_duration_seconds = time.perf_counter() - sqlite_write_started

                progress.artifact_phase(
                    artifact_id=artifact.artifact_id,
                    message="evaluating criteria...",
                )
                evaluation_started = time.perf_counter()
                for evaluator in evaluators:
                    try:
                        result = evaluator.evaluate(facts)
                        insert_criterion_value(
                            conn,
                            artifact_id=artifact.artifact_id,
                            criterion_id=result.criterion_id,
                            numeric_value=result.numeric_value,
                            text_value=result.text_value,
                            evidence=result.evidence,
                        )
                        criteria_computed += 1
                    except Exception as exc:
                        warnings += 1
                        log_processing_event(
                            conn,
                            artifact_id=artifact.artifact_id,
                            event_type="evaluator_error",
                            severity="warning",
                            message=str(exc),
                            details={"criterion_id": evaluator.criterion_id},
                        )
                artifact_report.evaluation_duration_seconds = time.perf_counter() - evaluation_started

                indexed += 1
                artifact_report.total_build_duration_seconds = time.perf_counter() - artifact_started
                artifact_reports.append(artifact_report)
                progress.artifact_finished(
                    artifact_id=artifact.artifact_id,
                    duration_seconds=artifact_report.total_build_duration_seconds,
                    term_count=len(facts.terms),
                )
                backend.close()

        progress.post_build_step("Rebuilding full-text search index...")
        rebuild_fts(conn)
        progress.post_build_step("Computing term reuse...")
        compute_term_iri_reuse(conn)
        progress.post_build_step("Computing inbound import counts...")
        compute_inbound_owl_import_counts(conn)
        conn.commit()
        progress.post_build_step("Validating index...")
        validate_index(temp_path)
        conn.close()
        progress.post_build_step(f"Writing index to {output_path}...")
        temp_path.replace(output_path)
    except Exception:
        build_status = "failed"
        if temp_path.exists():
            temp_path.unlink()
        for backend in pyoxigraph_backends:
            if not build_config.retain_rdf_store_after_build:
                backend.cleanup_store()
        raise
    finally:
        if build_status == "success":
            for backend in pyoxigraph_backends:
                if not build_config.retain_rdf_store_after_build:
                    backend.cleanup_store()

    conn = connect(output_path)
    try:
        terms_count = count_terms(conn)
        warnings += count_processing_events(conn, severity="warning")
    finally:
        conn.close()

    sqlite_index_size = output_path.stat().st_size if output_path.exists() else 0
    total_duration = time.perf_counter() - build_started

    report = BuildReport(
        snapshot_id=snapshot_id,
        artifacts_configured=len(artifacts),
        artifacts_indexed=indexed,
        artifacts_failed=failed,
        terms_indexed=terms_count,
        criteria_computed=criteria_computed,
        warnings=warnings,
        index_path=str(output_path),
        rdf_backend=build_config.rdf_backend,
        retain_rdf_store_after_build=build_config.retain_rdf_store_after_build,
        sqlite_index_size_bytes=sqlite_index_size,
        total_build_duration_seconds=total_duration,
        artifact_reports=artifact_reports,
        status=build_status,
    )

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

    progress.build_finished(
        artifacts_indexed=indexed,
        artifacts_failed=failed,
        terms_indexed=terms_count,
        duration_seconds=total_duration,
        output_path=output_path,
    )

    return report


def validate_index(index_path: Path) -> None:
    conn = connect(index_path)
    try:
        manifest = get_manifest(conn)
        if manifest is None:
            raise ValueError("Missing index manifest")
        orphan = conn.execute(
            """
            SELECT COUNT(*) AS c FROM terms t
            LEFT JOIN artifacts a ON a.artifact_id = t.artifact_id
            WHERE a.artifact_id IS NULL
            """
        ).fetchone()
        if orphan and orphan["c"] > 0:
            raise ValueError("Terms reference missing artifacts")

        parsed = conn.execute(
            "SELECT COUNT(*) AS c FROM artifacts WHERE parse_status = 'success'"
        ).fetchone()
        if parsed and parsed["c"] == 0:
            raise ValueError("No successfully parsed artifacts in index")

        fts_check = conn.execute(
            """
            SELECT COUNT(*) AS c FROM terms_fts
            WHERE terms_fts MATCH 'myocardial'
            """
        ).fetchone()
        if fts_check and fts_check["c"] == 0:
            sample = conn.execute(
                "SELECT preferred_label FROM terms WHERE preferred_label IS NOT NULL LIMIT 1"
            ).fetchone()
            if sample:
                token = _sanitize_fts_query(str(sample["preferred_label"]).split()[0])
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM terms_fts WHERE terms_fts MATCH ?",
                    (token,),
                ).fetchone()
                if row and row["c"] == 0:
                    raise ValueError("FTS index does not return expected fixture terms")
    finally:
        conn.close()


def inspect_index(index_path: Path) -> dict[str, Any]:
    conn = connect(index_path)
    try:
        manifest = get_manifest(conn)
        artifacts = conn.execute(
            "SELECT artifact_id, name, parse_status, triple_count FROM artifacts ORDER BY name"
        ).fetchall()
        events = conn.execute(
            "SELECT severity, COUNT(*) AS c FROM processing_events GROUP BY severity"
        ).fetchall()
        return {
            "manifest": dict(manifest) if manifest else None,
            "artifact_count": len(artifacts),
            "term_count": count_terms(conn),
            "artifacts": [dict(a) for a in artifacts],
            "processing_events": {row["severity"]: row["c"] for row in events},
        }
    finally:
        conn.close()


def _sanitize_fts_query(query: str) -> str:
    tokens = re.findall(r"\w+", query, flags=re.UNICODE)
    if not tokens:
        return '""'
    return " OR ".join(f'"{token}"' for token in tokens)

