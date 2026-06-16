from __future__ import annotations

from dataclasses import replace
from unittest import TestCase

from jee_rag_knowledge_graph.community.partition import partition_communities
from jee_rag_knowledge_graph.community.summarize import generate_community_summaries
from jee_rag_knowledge_graph.diagnosis.retrieve import diagnose_response, find_relevant_communities
from jee_rag_knowledge_graph.domain.ids import stable_id
from jee_rag_knowledge_graph.graph.build import build_graph
from tests.sample_data import build_sample_seed_bundle


class PipelineTests(TestCase):
    def test_graph_build_community_summary_and_diagnosis(self) -> None:
        seed_bundle = build_sample_seed_bundle()
        snapshot = build_graph(seed_bundle)
        communities = partition_communities(snapshot)
        summaries = generate_community_summaries(snapshot, communities)
        enriched = snapshot.with_communities(communities).with_summaries(summaries)

        relevant = find_relevant_communities(
            enriched,
            "assessment-quadratic-001",
            "I factor quadratics by using the distributive law, but I made a sign error.",
        )
        diagnosis = diagnose_response(
            enriched,
            assessment_item_id="assessment-quadratic-001",
            student_response_id="response-001",
            response_text="I factor quadratics by using the distributive law, but I made a sign error.",
        )

        self.assertGreaterEqual(len(communities), 2)
        self.assertGreaterEqual(len(summaries), 2)
        self.assertTrue(relevant)
        self.assertFalse(diagnosis.abstained)
        self.assertIsNotNone(diagnosis.primary_gap)
        self.assertIsNotNone(diagnosis.misconception_match)
        self.assertEqual(diagnosis.primary_gap.concept_id, stable_id("skill", "expand-expressions"))
        self.assertEqual(diagnosis.misconception_match.misconception_id, stable_id("misconception", "sign-error"))
        self.assertGreater(diagnosis.confidence, 0.0)

    def test_visual_question_abstains_without_semantic_interpretation(self) -> None:
        snapshot = build_graph(build_sample_seed_bundle())
        visual_item = replace(
            snapshot.assessment_items[0],
            requires_visual_interpretation=True,
        )
        snapshot = replace(snapshot, assessment_items=(visual_item,))

        diagnosis = diagnose_response(
            snapshot,
            assessment_item_id=visual_item.id,
            student_response_id="visual-response",
            response_text="I selected option 2 from the diagram.",
        )

        self.assertTrue(diagnosis.abstained)
        self.assertEqual(diagnosis.abstention_reason, "visual_interpretation_required")
