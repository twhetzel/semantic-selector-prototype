from __future__ import annotations

from semantic_selector.models import ArtifactEvaluator, CriterionResult, ExtractedArtifactFacts


class BaseEvaluator:
    criterion_id: str
    display_name: str
    description: str
    evaluator_version: str = "0.1.0"

    def evaluate(self, facts: ExtractedArtifactFacts) -> CriterionResult:
        raise NotImplementedError
