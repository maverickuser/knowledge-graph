"""Build a validated graph snapshot from local seed artifacts."""

from __future__ import annotations

from datetime import datetime, timezone

from ..domain.ids import stable_id
from ..domain.models import GraphSeedBundle, GraphSnapshot
from ..domain.validation import validate_graph_seed_bundle, validate_graph_snapshot


def build_graph(seed_bundle: GraphSeedBundle) -> GraphSnapshot:
    """Create a graph snapshot from a validated local seed bundle."""

    seed_report = validate_graph_seed_bundle(seed_bundle)
    seed_report.raise_for_errors()

    snapshot = GraphSnapshot(
        id=stable_id("graph", seed_bundle.graph_version),
        graph_version=seed_bundle.graph_version,
        seed_bundle_id=seed_bundle.id,
        source_documents=seed_bundle.source_documents,
        normalized_documents=seed_bundle.normalized_documents,
        syllabus_nodes=seed_bundle.syllabus_nodes,
        concepts=seed_bundle.concepts,
        skills=seed_bundle.skills,
        prerequisite_edges=seed_bundle.prerequisite_edges,
        misconceptions=seed_bundle.misconceptions,
        corrective_actions=seed_bundle.corrective_actions,
        evidence_artifacts=seed_bundle.evidence_artifacts,
        assessment_items=seed_bundle.assessment_items,
        built_at=datetime.now(tz=timezone.utc).isoformat(),
        version=seed_bundle.graph_version,
    )

    report = validate_graph_snapshot(snapshot)
    report.raise_for_errors()
    return snapshot
