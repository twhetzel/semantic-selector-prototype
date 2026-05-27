from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any

from rdflib.term import Literal

from semantic_selector.extractors.base import ExtractorResult
from semantic_selector.models import ExtractedArtifactFacts

LABEL_PREDICATE_PRIORITY = {
    "http://www.w3.org/2004/02/skos/core#prefLabel": 0,
    "http://www.w3.org/2000/01/rdf-schema#label": 1,
}

HIERARCHY_PARENT_PREDICATES = {
    "http://www.w3.org/2000/01/rdf-schema#subClassOf",
    "http://www.w3.org/2004/02/skos/core#broader",
}

HIERARCHY_CHILD_PREDICATES = {
    "http://www.w3.org/2004/02/skos/core#narrower",
}


def normalize_label(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text.strip().lower())
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def prefer_literal(literals: list[Any]) -> str | None:
    if not literals:
        return None
    parsed: list[tuple[int, int, str]] = []
    for idx, item in enumerate(literals):
        if isinstance(item, Literal):
            lang = item.language or ""
            text = str(item)
        else:
            lang = ""
            text = str(item)
        lang_rank = 0 if lang.lower().startswith("en") else (1 if not lang else 2)
        parsed.append((lang_rank, idx, text))
    parsed.sort()
    return parsed[0][2]


def _normalize_lang_tag(tag: Any) -> str | None:
    if tag is None:
        return None
    text = str(tag).strip()
    if not text:
        return None
    return text


def _collect_lang_from_row(row: dict[str, Any], lang_key: str) -> str | None:
    return _normalize_lang_tag(row.get(lang_key))


def join_extractor_results(
    artifact_id: str,
    results: dict[str, ExtractorResult],
) -> ExtractedArtifactFacts:
    extractor_versions = {k: v.version for k, v in results.items()}

    metadata: dict[str, list[Any]] = defaultdict(list)
    for row in results.get("artifact_metadata", ExtractorResult("", "", [])).rows:
        key = row.get("metadataPredicate", "unknown")
        metadata[str(key)].append(row.get("metadataValue"))

    version_values: list[Any] = []
    version_iri: str | None = None
    for row in results.get("version_metadata", ExtractorResult("", "", [])).rows:
        predicate = str(row.get("versionPredicate", ""))
        value = row.get("versionValue")
        version_values.append(value)
        if predicate.endswith("versionIRI") and value:
            version_iri = str(value)

    metadata["version_values"] = version_values

    metadata["version_iri"] = [version_iri] if version_iri else []

    ontology_iris: list[str] = []
    for row in results.get("ontology_document", ExtractorResult("", "", [])).rows:
        ontology = row.get("ontology")
        if ontology:
            ontology_iris.append(str(ontology))
    metadata["ontology_iri"] = ontology_iris

    owl_import_iris: list[str] = []
    for row in results.get("owl_imports", ExtractorResult("", "", [])).rows:
        imported = row.get("importedOntology")
        if imported:
            owl_import_iris.append(str(imported))
    metadata["owl_import_iris"] = sorted(set(owl_import_iris))

    language_tags: set[str] = set()
    language_tagged_literal_count = 0

    labels_by_term: dict[str, list[tuple[str, Any]]] = defaultdict(list)
    label_langs_by_term: dict[str, set[str]] = defaultdict(set)
    for row in results.get("terms_and_labels", ExtractorResult("", "", [])).rows:
        term = str(row.get("term", ""))
        if not term:
            continue
        predicate = str(row.get("labelPredicate", ""))
        label = row.get("label")
        if label is not None:
            labels_by_term[term].append((predicate, label))
            lang = _collect_lang_from_row(row, "labelLang")
            if lang:
                language_tags.add(lang)
                label_langs_by_term[term].add(lang)
                language_tagged_literal_count += 1

    definitions_by_term: dict[str, list[str]] = defaultdict(list)
    definition_langs_by_term: dict[str, set[str]] = defaultdict(set)
    for row in results.get("definitions", ExtractorResult("", "", [])).rows:
        term = str(row.get("term", ""))
        definition = row.get("definition")
        if term and definition is not None:
            definitions_by_term[term].append(str(definition))
            lang = _collect_lang_from_row(row, "definitionLang")
            if lang:
                language_tags.add(lang)
                definition_langs_by_term[term].add(lang)
                language_tagged_literal_count += 1

    synonyms_by_term: dict[str, list[str]] = defaultdict(list)
    synonym_langs_by_term: dict[str, set[str]] = defaultdict(set)
    for row in results.get("synonyms", ExtractorResult("", "", [])).rows:
        term = str(row.get("term", ""))
        synonym = row.get("synonym")
        if term and synonym is not None:
            synonyms_by_term[term].append(str(synonym))
            lang = _collect_lang_from_row(row, "synonymLang")
            if lang:
                language_tags.add(lang)
                synonym_langs_by_term[term].add(lang)
                language_tagged_literal_count += 1

    metadata["language_tags"] = sorted(language_tags)
    metadata["language_tagged_literal_count"] = [language_tagged_literal_count]

    obsolete_terms: set[str] = set()
    for row in results.get("obsolete_terms", ExtractorResult("", "", [])).rows:
        term = row.get("term")
        if term:
            obsolete_terms.add(str(term))

    all_term_iris: set[str] = set(labels_by_term.keys())
    all_term_iris.update(definitions_by_term.keys())
    all_term_iris.update(synonyms_by_term.keys())
    all_term_iris.update(obsolete_terms)

    hierarchy_rows = results.get("hierarchy_relations", ExtractorResult("", "", [])).rows
    mapping_rows = results.get("mappings", ExtractorResult("", "", [])).rows

    parent_counts: dict[str, int] = defaultdict(int)
    child_counts: dict[str, int] = defaultdict(int)
    relations: list[dict[str, Any]] = []

    for row in hierarchy_rows:
        subject = str(row.get("subject", ""))
        predicate = str(row.get("predicate", ""))
        obj = str(row.get("object", ""))
        if not subject or not obj:
            continue
        relations.append(
            {
                "subject_iri": subject,
                "predicate_iri": predicate,
                "object_iri": obj,
                "relation_type": "hierarchy",
            }
        )
        if predicate in HIERARCHY_PARENT_PREDICATES:
            parent_counts[subject] += 1
        elif predicate in HIERARCHY_CHILD_PREDICATES:
            child_counts[subject] += 1
        elif predicate.endswith("subClassOf"):
            parent_counts[subject] += 1

    mapping_counts: dict[str, int] = defaultdict(int)
    for row in mapping_rows:
        subject = str(row.get("subject", ""))
        predicate = str(row.get("predicate", ""))
        obj = str(row.get("object", ""))
        if not subject:
            continue
        relations.append(
            {
                "subject_iri": subject,
                "predicate_iri": predicate,
                "object_iri": obj or "",
                "relation_type": "mapping",
            }
        )
        mapping_counts[subject] += 1

    terms: list[dict[str, Any]] = []
    for term_iri in sorted(all_term_iris):
        label_candidates = labels_by_term.get(term_iri, [])
        grouped: dict[str, list[Any]] = defaultdict(list)
        for predicate, label in label_candidates:
            grouped[predicate].append(label)

        preferred: str | None = None
        for predicate in sorted(grouped.keys(), key=lambda p: LABEL_PREDICATE_PRIORITY.get(p, 99)):
            chosen = prefer_literal(grouped[predicate])
            if chosen:
                preferred = chosen
                break

        defs = _dedupe_strings(definitions_by_term.get(term_iri, []))
        syns = _dedupe_strings(synonyms_by_term.get(term_iri, []))
        term_langs = sorted(
            label_langs_by_term.get(term_iri, set())
            | definition_langs_by_term.get(term_iri, set())
            | synonym_langs_by_term.get(term_iri, set())
        )

        terms.append(
            {
                "term_iri": term_iri,
                "preferred_label": preferred,
                "normalized_label": normalize_label(preferred) if preferred else None,
                "synonyms": syns,
                "synonyms_text": " | ".join(syns),
                "definitions": defs,
                "definitions_text": " | ".join(defs),
                "language_tags": term_langs,
                "language_tags_text": " | ".join(term_langs),
                "is_obsolete": term_iri in obsolete_terms,
                "parent_count": parent_counts.get(term_iri, 0),
                "child_count": child_counts.get(term_iri, 0),
                "mapping_count": mapping_counts.get(term_iri, 0),
            }
        )

    return ExtractedArtifactFacts(
        artifact_id=artifact_id,
        terms=terms,
        relations=relations,
        metadata=dict(metadata),
        extractor_versions=extractor_versions,
    )


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
