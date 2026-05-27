from __future__ import annotations

from semantic_selector.evaluators.hierarchy import HierarchyPresenceEvaluator
from semantic_selector.evaluators.i18n import MultilanguageAnnotationsEvaluator
from semantic_selector.evaluators.metadata import HasVersionMetadataEvaluator
from semantic_selector.evaluators.reuse import InboundOwlImportCountEvaluator
from semantic_selector.evaluators.term_annotations import (
    DefinitionCoverageEvaluator,
    SynonymCoverageEvaluator,
)
from semantic_selector.models import ArtifactEvaluator

EVALUATOR_REGISTRY: dict[str, type] = {
    "metadata.has_version_metadata": HasVersionMetadataEvaluator,
    "term_annotations.definition_coverage": DefinitionCoverageEvaluator,
    "term_annotations.synonym_coverage": SynonymCoverageEvaluator,
    "i18n.multilanguage_annotations": MultilanguageAnnotationsEvaluator,
    "reuse.inbound_owl_import_count": InboundOwlImportCountEvaluator,
    # Deprecated: hierarchy_presence removed from criteria config; class retained for tests if needed
    "hierarchy.hierarchy_presence": HierarchyPresenceEvaluator,
}


def create_evaluator(evaluator_key: str) -> ArtifactEvaluator:
    cls = EVALUATOR_REGISTRY.get(evaluator_key)
    if cls is None:
        raise KeyError(f"Unknown evaluator: {evaluator_key}")
    return cls()


def list_evaluator_keys() -> list[str]:
    return sorted(EVALUATOR_REGISTRY.keys())
