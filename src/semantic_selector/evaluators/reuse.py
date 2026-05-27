from __future__ import annotations

from semantic_selector.evaluators.base import BaseEvaluator
from semantic_selector.models import CriterionResult, ExtractedArtifactFacts


class InboundOwlImportCountEvaluator(BaseEvaluator):
    """Per-artifact placeholder; inbound count is computed post-build across all artifacts."""

    criterion_id = "inbound_owl_import_count"
    display_name = "Inbound ontology imports"
    description = "Number of other indexed ontologies that owl:import this ontology."

    def evaluate(self, facts: ExtractedArtifactFacts) -> CriterionResult:
        outbound = facts.metadata.get("owl_import_iris", [])
        return CriterionResult(
            criterion_id=self.criterion_id,
            numeric_value=0.0,
            text_value=None,
            evidence={
                "outbound_import_iris": [str(v) for v in outbound],
                "inbound_import_count": 0,
                "importing_artifact_ids": [],
                "note": "Inbound count computed after all artifacts are indexed.",
                "extractor_versions": facts.extractor_versions,
            },
        )
