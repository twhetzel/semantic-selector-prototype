from __future__ import annotations

from semantic_selector.evaluators.base import BaseEvaluator
from semantic_selector.models import CriterionResult, ExtractedArtifactFacts


class HierarchyPresenceEvaluator(BaseEvaluator):
    criterion_id = "hierarchy_presence"
    display_name = "Hierarchy Presence"
    description = "At least one direct hierarchy relation exists among indexed terms."

    def evaluate(self, facts: ExtractedArtifactFacts) -> CriterionResult:
        term_iris = {str(t["term_iri"]) for t in facts.terms}
        hierarchy_relations = [
            r for r in facts.relations if r.get("relation_type") == "hierarchy"
        ]
        matched = [
            r
            for r in hierarchy_relations
            if r.get("subject_iri") in term_iris and r.get("object_iri") in term_iris
        ]
        value = 1.0 if matched else 0.0
        return CriterionResult(
            criterion_id=self.criterion_id,
            numeric_value=value,
            text_value=None,
            evidence={
                "relation_count": len(matched),
                "sample_relations": matched[:5],
                "extractor_versions": facts.extractor_versions,
            },
        )
