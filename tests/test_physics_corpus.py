from __future__ import annotations

from pathlib import Path
import json
from tempfile import TemporaryDirectory
from unittest import TestCase

from jee_rag_knowledge_graph.community.partition import partition_communities
from jee_rag_knowledge_graph.community.summarize import generate_community_summaries
from jee_rag_knowledge_graph.diagnosis.retrieve import diagnose_response
from jee_rag_knowledge_graph.graph.build import build_graph
from jee_rag_knowledge_graph.ingestion.physics_corpus import build_physics_seed_bundle


class PhysicsCorpusTests(TestCase):
    def test_build_physics_corpus_seed_bundle(self) -> None:
        fixture_root = Path(__file__).resolve().parent / "fixtures"
        seed_bundle = build_physics_seed_bundle(
            fixture_root,
            graph_version="physics-v1",
            extraction_version="physics-extract-v1",
        )

        snapshot = build_graph(seed_bundle)
        communities = partition_communities(snapshot)
        summaries = generate_community_summaries(snapshot, communities)
        enriched = snapshot.with_communities(communities).with_summaries(summaries)
        diagnosis = diagnose_response(
            enriched,
            assessment_item_id="SAMPLE-PHYS-01",
            student_response_id="response-01",
            response_text="I used the parallel-axis theorem on the tangent axis.",
        )

        self.assertEqual(len(seed_bundle.assessment_items), 2)
        self.assertGreaterEqual(len(seed_bundle.concepts), 2)
        self.assertGreaterEqual(len(seed_bundle.skills), 2)
        self.assertGreaterEqual(len(seed_bundle.misconceptions), 3)
        self.assertGreaterEqual(len(communities), 3)
        self.assertGreaterEqual(len(summaries), 3)
        self.assertFalse(diagnosis.abstained)
        self.assertTrue(diagnosis.evidence_refs)
        self.assertIsNotNone(diagnosis.primary_gap)
        self.assertGreater(diagnosis.confidence, 0.0)

    def test_jsonl_import_normalizes_layout_and_rejects_corrupt_questions(self) -> None:
        valid = {
            "question_ref": "Q-1",
            "paper_ref": "P-1",
            "paper_title": "Paper",
            "question_text": "Find the moment of\ninertia of two connected rods about the given axis.",
            "solution_text": "Use the parallel-axis theorem.",
            "pitfalls": ["Do not omit the axis shift."],
            "official_answer": "4",
        }
        corrupt = {
            "question_ref": "Q-2",
            "paper_ref": "P-1",
            "question_text": "2. Ans",
            "solution_text": "",
        }
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "questions.jsonl"
            source.write_text(
                "\n".join(json.dumps(item) for item in (valid, corrupt)),
                encoding="utf-8",
            )
            seed_bundle = build_physics_seed_bundle(source.parent)

        self.assertEqual(len(seed_bundle.assessment_items), 1)
        self.assertEqual(seed_bundle.concepts[0].canonical_name, "Rotational Mechanics")
