from __future__ import annotations

from typing import Any

from semantic_selector.models import CriterionResult


def explain_criterion(criterion_id: str, result: CriterionResult) -> list[str]:
    evidence = result.evidence
    lines: list[str] = []
    if criterion_id == "has_version_metadata":
        if result.numeric_value and result.numeric_value >= 1.0:
            lines.append("Version metadata is present.")
        else:
            lines.append("Version metadata is absent.")
    elif criterion_id == "definition_coverage":
        num = evidence.get("numerator", 0)
        den = evidence.get("denominator", 0)
        pct = int((result.numeric_value or 0) * 100)
        lines.append(f"{pct}% of labeled terms have definitions ({num}/{den}).")
    elif criterion_id == "synonym_coverage":
        num = evidence.get("numerator", 0)
        den = evidence.get("denominator", 0)
        pct = int((result.numeric_value or 0) * 100)
        lines.append(f"{pct}% of labeled terms have synonyms ({num}/{den}).")
    elif criterion_id == "term_match_frequency":
        pct = int((result.numeric_value or 0) * 100)
        matched = evidence.get("matched_queries", 0)
        total = evidence.get("total_queries", 0)
        lines.append(f"Matched {matched}/{total} requested concepts ({pct}%).")
    elif criterion_id == "inbound_owl_import_count":
        count = int(result.numeric_value or 0)
        if count:
            lines.append(f"{count} other indexed ontology artifact(s) import this ontology.")
        else:
            lines.append("No inbound owl:imports from other indexed ontologies.")
    elif criterion_id == "multilanguage_annotations":
        langs = evidence.get("languages") or []
        if langs:
            lines.append(f"Annotation languages present: {', '.join(langs)}.")
        else:
            lines.append("No language-tagged annotations found.")
    return lines


def build_selection_explanation(
    *,
    match_type: str | None,
    criterion_scores: dict[str, float],
    criterion_evidence: dict[str, dict[str, Any]],
    filter_exclusions: list[str] | None = None,
) -> list[str]:
    lines: list[str] = []
    if match_type == "preferred_label_exact":
        lines.append("Exact preferred-label match found.")
    elif match_type:
        lines.append(f"Term matched via {match_type.replace('_', ' ')}.")

    for criterion_id, score in criterion_scores.items():
        fake = CriterionResult(criterion_id, score, None, criterion_evidence.get(criterion_id, {}))
        lines.extend(explain_criterion(criterion_id, fake))

    if filter_exclusions:
        lines.extend(filter_exclusions)
    return lines
