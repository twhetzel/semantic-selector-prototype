from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class TermEvidence(BaseModel):
    has_definition: bool = False
    definitions: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    parent_count: int = 0
    child_count: int = 0
    mapping_count: int = 0
    language_tags: list[str] = Field(default_factory=list)
    term_reuse_count_by_iri: int = 0
    term_reuse_artifact_ids: list[str] = Field(default_factory=list)
    is_obsolete: bool = False


class TermSearchRequest(BaseModel):
    query: str
    artifact_ids: list[str] | None = None
    repository_ids: list[str] | None = None
    include_obsolete: bool = False
    limit: int = Field(default=20, ge=1, le=200)


class TermSearchResult(BaseModel):
    artifact_id: str
    artifact_name: str
    artifact_version: str | None = None
    term_iri: str
    preferred_label: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    definition: str | None = None
    match_type: str
    text_score: float
    normalized_label: str | None = None
    shared_label_group: str | None = None
    term_evidence: TermEvidence | None = None


class TermSearchResponse(BaseModel):
    query: str
    snapshot_id: str | None
    results: list[TermSearchResult]


class SelectionFilters(BaseModel):
    repository_ids: list[str] | None = None
    artifact_ids: list[str] | None = None
    exclude_obsolete_terms: bool = True
    require_definition: bool = False


class ArtifactSelectionRequest(BaseModel):
    query: str | None = None
    queries: list[str] | None = None
    filters: SelectionFilters = Field(default_factory=SelectionFilters)
    weights: dict[str, float] | None = None
    limit: int = Field(default=10, ge=1, le=100)


class MatchingTermResult(BaseModel):
    term_iri: str
    preferred_label: str | None = None
    match_type: str
    text_score: float
    term_evidence: TermEvidence | None = None


class BestTermMatch(BaseModel):
    term_iri: str
    preferred_label: str | None = None
    match_type: str
    term_match_score: float


class ArtifactSelectionResult(BaseModel):
    rank: int
    artifact_id: str
    artifact_name: str
    artifact_version: str | None = None
    overall_score: float
    ontology_scores: dict[str, float] = Field(default_factory=dict)
    ontology_evidence: dict[str, Any] = Field(default_factory=dict)
    matching_terms: list[MatchingTermResult] = Field(default_factory=list)
    best_term_match: BestTermMatch
    criterion_scores: dict[str, float] = Field(default_factory=dict)
    explanation: list[str]
    provenance: dict[str, Any]


class ArtifactSelectionResponse(BaseModel):
    query: str | None = None
    queries: list[str] = Field(default_factory=list)
    snapshot_id: str | None
    normalized_weights: dict[str, float]
    ontology_results: list[ArtifactSelectionResult]
    results: list[ArtifactSelectionResult]
    filter_exclusions: list[str] = Field(default_factory=list)


class CompareArtifactsRequest(BaseModel):
    artifact_ids: list[str] = Field(min_length=2)
    query: str | None = None
