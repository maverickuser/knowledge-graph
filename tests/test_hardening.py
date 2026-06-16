from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from dataclasses import replace
from unittest import TestCase

from jee_rag_knowledge_graph.community.partition import partition_communities
from jee_rag_knowledge_graph.community.summarize import generate_community_summaries
from jee_rag_knowledge_graph.diagnosis.retrieve import diagnose_response
from jee_rag_knowledge_graph.graph.build import build_graph
from jee_rag_knowledge_graph.domain.ids import stable_id
from tests.sample_data import build_sample_seed_bundle


def _canonical_snapshot_payload(snapshot) -> dict:
    payload = snapshot.to_dict()
    payload.pop("built_at", None)
    payload.pop("version", None)
    for source in payload.get("source_documents", []):
        source.pop("ingested_at", None)
    for evidence in payload.get("evidence_artifacts", []):
        evidence.pop("timestamp", None)
    for summary in payload.get("community_summaries", []):
        summary.pop("generated_at", None)
    return payload


class HardeningTests(TestCase):
    def setUp(self) -> None:
        fixture_path = Path(__file__).resolve().parent / "fixtures" / "evaluation_cases.json"
        self.evaluation_cases = json.loads(fixture_path.read_text(encoding="utf-8"))

    def _build_enriched_snapshot(self):
        seed_bundle = build_sample_seed_bundle()
        snapshot = build_graph(seed_bundle)
        communities = partition_communities(snapshot)
        summaries = generate_community_summaries(snapshot, communities)
        return snapshot.with_communities(communities).with_summaries(summaries)

    def test_curated_evaluation_cases(self) -> None:
        snapshot = self._build_enriched_snapshot()

        for case in self.evaluation_cases:
            case_snapshot = snapshot
            if case.get("requires_visual_interpretation"):
                visual_item = replace(
                    snapshot.assessment_items[0],
                    requires_visual_interpretation=True,
                )
                case_snapshot = replace(snapshot, assessment_items=(visual_item,))

            diagnosis = diagnose_response(
                case_snapshot,
                assessment_item_id=case["assessment_item_id"],
                student_response_id=case["student_response_id"],
                response_text=case["response_text"],
                threshold=case.get("threshold", 0.55),
            )

            self.assertEqual(diagnosis.abstained, case["expected_abstained"], case["case_id"])
            if case["expected_abstained"]:
                self.assertEqual(diagnosis.abstention_reason, case["expected_abstention_reason"], case["case_id"])
            else:
                expected_primary_gap = stable_id(*case["expected_primary_gap"].split(":", 1))
                self.assertIsNotNone(diagnosis.primary_gap, case["case_id"])
                self.assertEqual(diagnosis.primary_gap.concept_id, expected_primary_gap, case["case_id"])
                self.assertGreater(diagnosis.confidence, 0.0, case["case_id"])

    def test_deterministic_builds_for_same_inputs(self) -> None:
        seed_bundle = build_sample_seed_bundle()

        snapshot_a = build_graph(seed_bundle)
        snapshot_a = snapshot_a.with_communities(partition_communities(snapshot_a))
        snapshot_a = snapshot_a.with_summaries(generate_community_summaries(snapshot_a, snapshot_a.communities))

        snapshot_b = build_graph(seed_bundle)
        snapshot_b = snapshot_b.with_communities(partition_communities(snapshot_b))
        snapshot_b = snapshot_b.with_summaries(generate_community_summaries(snapshot_b, snapshot_b.communities))

        self.assertEqual(_canonical_snapshot_payload(snapshot_a), _canonical_snapshot_payload(snapshot_b))

    def test_build_and_diagnosis_hot_paths_stay_within_budget(self) -> None:
        seed_bundle = build_sample_seed_bundle()
        start = perf_counter()
        for _ in range(20):
            snapshot = build_graph(seed_bundle)
            communities = partition_communities(snapshot)
            summaries = generate_community_summaries(snapshot, communities)
            enriched = snapshot.with_communities(communities).with_summaries(summaries)
            diagnosis = diagnose_response(
                enriched,
                assessment_item_id="assessment-quadratic-001",
                student_response_id="performance-response",
                response_text="I factor quadratics by using the distributive law, but I made a sign error.",
            )
            self.assertFalse(diagnosis.abstained)
        duration = perf_counter() - start
        self.assertLess(duration, 5.0)
