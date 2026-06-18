from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from knowledge_graph.graph.build import build_graph
from knowledge_graph.grounding.syllabus import (
    build_syllabus_term_index,
    ground_question_to_syllabus,
    verify_syllabus_path,
)
from knowledge_graph.ingestion.physics_corpus import build_physics_seed_bundle
from knowledge_graph.output.agent_view import build_agent_graph_view


class SyllabusGroundingTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture_root = Path(__file__).resolve().parent / "fixtures"
        cls.snapshot = build_graph(
            build_physics_seed_bundle(
                fixture_root,
                graph_version="grounding-v1",
                extraction_version="grounding-extract-v1",
            )
        )

    def test_question_maps_only_to_known_syllabus_terms(self) -> None:
        result = ground_question_to_syllabus(
            self.snapshot,
            "Find the moment of inertia of the rods using the parallel-axis theorem.",
        )

        self.assertTrue(result["is_grounded"])
        paths = [
            " > ".join(node["title"] for node in match["path"])
            for match in result["matches"]
        ]
        self.assertTrue(any("Rotational Mechanics" in path for path in paths))
        self.assertTrue(any("Moment of inertia" in path for path in paths))

    def test_unrelated_question_does_not_get_syllabus_mapping(self) -> None:
        result = ground_question_to_syllabus(
            self.snapshot,
            "Discuss symbolism and narrative voice in a poem.",
        )

        self.assertFalse(result["is_grounded"])
        self.assertEqual(result["abstention_reason"], "no_known_syllabus_terms")
        self.assertEqual(result["matches"], [])

    def test_syllabus_path_verification_accepts_only_real_hierarchy(self) -> None:
        verified = verify_syllabus_path(
            self.snapshot,
            {
                "chapter": "Rotational Mechanics",
                "topic": "Moment of inertia",
                "concept": "moment of inertia",
                "subconcept": "moment of inertia fundamentals",
                "microconcept": "moment of inertia problem application",
            },
        )
        invalid = verify_syllabus_path(
            self.snapshot,
            {
                "chapter": "Ray Optics",
                "topic": "Moment of inertia",
            },
        )

        self.assertTrue(verified["is_verified"])
        self.assertFalse(invalid["is_verified"])
        self.assertEqual(invalid["reason"], "path_not_found_in_graph")

    def test_agent_view_exposes_grounding_terms(self) -> None:
        term_index = build_syllabus_term_index(self.snapshot)
        agent_view = build_agent_graph_view(self.snapshot)

        self.assertTrue(term_index)
        self.assertEqual(agent_view["grounding_policy"]["question_mapping"], "exact_known_term_match_only")
        self.assertEqual(agent_view["syllabus_term_index"], term_index)
