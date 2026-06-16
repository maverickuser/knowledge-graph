from __future__ import annotations

from unittest import TestCase

from knowledge_graph.domain.ids import stable_id
from knowledge_graph.domain.models import Concept, GraphSnapshot
from knowledge_graph.domain.validation import ValidationError, validate_graph_snapshot
from tests.sample_data import build_sample_snapshot


class DomainTests(TestCase):
    def test_stable_id_is_deterministic(self) -> None:
        self.assertEqual(stable_id("concept", "distributive law"), stable_id("concept", "distributive law"))

    def test_graph_snapshot_round_trip_serialization(self) -> None:
        snapshot = build_sample_snapshot()
        self.assertEqual(GraphSnapshot.from_dict(snapshot.to_dict()), snapshot)

    def test_validation_rejects_missing_provenance(self) -> None:
        snapshot = build_sample_snapshot()
        invalid_concept = Concept(
            id="concept-invalid",
            canonical_name="invalid",
            definition="A concept without provenance.",
            subject="Mathematics",
            grade_band="Secondary",
            source_refs=(),
            syllabus_node_ids=(snapshot.syllabus_nodes[0].id,),
            version="1",
        )
        invalid_snapshot = snapshot.with_communities(()).with_summaries(())
        invalid_snapshot = invalid_snapshot.__class__(
            id=invalid_snapshot.id,
            graph_version=invalid_snapshot.graph_version,
            seed_bundle_id=invalid_snapshot.seed_bundle_id,
            source_documents=invalid_snapshot.source_documents,
            normalized_documents=invalid_snapshot.normalized_documents,
            syllabus_nodes=invalid_snapshot.syllabus_nodes,
            concepts=(invalid_concept,),
            skills=invalid_snapshot.skills,
            prerequisite_edges=invalid_snapshot.prerequisite_edges,
            misconceptions=invalid_snapshot.misconceptions,
            evidence_artifacts=invalid_snapshot.evidence_artifacts,
            assessment_items=invalid_snapshot.assessment_items,
            communities=(),
            community_summaries=(),
            diagnostic_records=(),
            built_at=invalid_snapshot.built_at,
            version=invalid_snapshot.version,
        )
        report = validate_graph_snapshot(invalid_snapshot)
        self.assertFalse(report.is_valid)
        with self.assertRaises(ValidationError):
            report.raise_for_errors()

