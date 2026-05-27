from __future__ import annotations

from semantic_selector.evaluators.base import BaseEvaluator
from semantic_selector.models import CriterionResult, ExtractedArtifactFacts


class HasVersionMetadataEvaluator(BaseEvaluator):
    criterion_id = "has_version_metadata"
    display_name = "Has Version Metadata"
    description = "Artifact declares at least one version metadata property."

    def evaluate(self, facts: ExtractedArtifactFacts) -> CriterionResult:
        version_values = facts.metadata.get("version_values", [])
        matched = [v for v in version_values if v is not None and str(v).strip()]
        value = 1.0 if matched else 0.0
        return CriterionResult(
            criterion_id=self.criterion_id,
            numeric_value=value,
            text_value=None,
            evidence={
                "matched_values": [str(v) for v in matched],
                "extractor_versions": facts.extractor_versions,
                "absence_statement": None if matched else "No version metadata values found.",
            },
        )
