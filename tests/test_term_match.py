from __future__ import annotations

from semantic_selector.ranking.term_match import classify_term_match, rank_term_rows


def test_preferred_label_exact_ranks_before_prefix_match() -> None:
    rows = [
        {
            "artifact_id": "obo:ncit",
            "term_iri": "http://purl.obolibrary.org/obo/NCIT_C91477",
            "preferred_label": "Melanoma Pathway",
            "synonyms_text": "",
            "definitions_text": "",
        },
        {
            "artifact_id": "obo:mondo",
            "term_iri": "http://purl.obolibrary.org/obo/MONDO_0005105",
            "preferred_label": "melanoma",
            "synonyms_text": "",
            "definitions_text": "",
        },
    ]
    ranked = rank_term_rows(
        rows,
        query="melanoma",
        bm25_scores=[-10.0, -9.0],
        ontology_scores={"obo:ncit": 0.9, "obo:mondo": 0.5},
    )
    assert ranked[0][0]["preferred_label"] == "melanoma"
    assert ranked[0][2] == "preferred_label_exact"


def test_synonym_exact_ranks_before_partial_match() -> None:
    rows = [
        {
            "artifact_id": "obo:mondo",
            "term_iri": "http://purl.obolibrary.org/obo/MONDO_0005015",
            "preferred_label": "diabetes mellitus",
            "synonyms_text": "",
            "definitions_text": "",
        },
        {
            "artifact_id": "obo:mondo",
            "term_iri": "http://purl.obolibrary.org/obo/MONDO_0000001",
            "preferred_label": "disease",
            "synonyms_text": "diabetes",
            "definitions_text": "",
        },
    ]
    ranked = rank_term_rows(
        rows,
        query="diabetes",
        bm25_scores=[0.0, 0.0],
        ontology_scores={"obo:mondo": 0.8},
    )
    assert ranked[0][2] == "synonym_exact"
    assert classify_term_match(ranked[0][0], "diabetes") == "synonym_exact"


def test_ontology_score_breaks_ties_within_match_tier() -> None:
    rows = [
        {
            "artifact_id": "obo:low-score",
            "term_iri": "http://example.org/low",
            "preferred_label": "melanoma",
            "synonyms_text": "",
            "definitions_text": "",
        },
        {
            "artifact_id": "obo:high-score",
            "term_iri": "http://example.org/high",
            "preferred_label": "melanoma",
            "synonyms_text": "",
            "definitions_text": "",
        },
    ]
    ranked = rank_term_rows(
        rows,
        query="melanoma",
        bm25_scores=[0.0, 0.0],
        ontology_scores={"obo:low-score": 0.4, "obo:high-score": 0.9},
    )
    assert ranked[0][0]["artifact_id"] == "obo:high-score"
