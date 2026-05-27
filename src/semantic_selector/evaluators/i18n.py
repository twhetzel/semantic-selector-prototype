from __future__ import annotations

from semantic_selector.evaluators.base import BaseEvaluator
from semantic_selector.models import CriterionResult, ExtractedArtifactFacts


def _collect_language_tags(facts: ExtractedArtifactFacts) -> list[str]:
    tags = facts.metadata.get("language_tags", [])
    return sorted({str(tag).strip() for tag in tags if tag and str(tag).strip()})


class MultilanguageAnnotationsEvaluator(BaseEvaluator):
    criterion_id = "multilanguage_annotations"
    display_name = "Multi-language annotations"
    description = "Distinct annotation language tags present in the ontology."

    def evaluate(self, facts: ExtractedArtifactFacts) -> CriterionResult:
        languages = _collect_language_tags(facts)
        literal_count = int(facts.metadata.get("language_tagged_literal_count", [0])[0] or 0)
        return CriterionResult(
            criterion_id=self.criterion_id,
            numeric_value=float(len(languages)),
            text_value=", ".join(languages) if languages else None,
            evidence={
                "languages": languages,
                "language_count": len(languages),
                "language_tagged_literal_count": literal_count,
                "extractor_versions": facts.extractor_versions,
            },
        )
