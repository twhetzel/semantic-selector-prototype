from __future__ import annotations

from semantic_selector.evaluators.base import BaseEvaluator
from semantic_selector.models import CriterionResult, ExtractedArtifactFacts


class DefinitionCoverageEvaluator(BaseEvaluator):
    criterion_id = "definition_coverage"
    display_name = "Term definition coverage across ontology"
    description = "Share of labeled terms with at least one definition (Ont: Term Details)."

    def evaluate(self, facts: ExtractedArtifactFacts) -> CriterionResult:
        labeled = [t for t in facts.terms if t.get("preferred_label")]
        with_definition = [t for t in labeled if t.get("definitions")]
        denominator = len(labeled)
        numerator = len(with_definition)
        value = (numerator / denominator) if denominator else 0.0
        return CriterionResult(
            criterion_id=self.criterion_id,
            numeric_value=value,
            text_value=None,
            evidence={
                "numerator": numerator,
                "denominator": denominator,
                "predicates": [
                    "http://www.w3.org/2004/02/skos/core#definition",
                    "http://purl.obolibrary.org/obo/IAO_0000115",
                ],
                "extractor_versions": facts.extractor_versions,
            },
        )


class SynonymCoverageEvaluator(BaseEvaluator):
    criterion_id = "synonym_coverage"
    display_name = "Synonym coverage across ontology"
    description = "Share of labeled terms with at least one synonym."

    def evaluate(self, facts: ExtractedArtifactFacts) -> CriterionResult:
        labeled = [t for t in facts.terms if t.get("preferred_label")]
        with_synonym = [t for t in labeled if t.get("synonyms")]
        denominator = len(labeled)
        numerator = len(with_synonym)
        value = (numerator / denominator) if denominator else 0.0
        return CriterionResult(
            criterion_id=self.criterion_id,
            numeric_value=value,
            text_value=None,
            evidence={
                "numerator": numerator,
                "denominator": denominator,
                "predicates": [
                    "http://www.w3.org/2004/02/skos/core#altLabel",
                    "http://www.geneontology.org/formats/oboInOwl#hasExactSynonym",
                ],
                "extractor_versions": facts.extractor_versions,
            },
        )
