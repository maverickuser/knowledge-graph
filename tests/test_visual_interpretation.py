from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from knowledge_graph.domain.models import EvidenceArtifact, VisualInterpretation
from knowledge_graph.vision.interpret import enrich_visual_interpretations
from tests.sample_data import build_sample_snapshot


class FakeVisionInterpreter:
    model = "fake-vision"

    def __init__(self) -> None:
        self.calls = 0

    def interpret(
        self,
        assessment,
        image_paths: tuple[Path, ...],
    ) -> VisualInterpretation:
        self.calls += 1
        return VisualInterpretation(
            summary="A quadratic graph with labeled axes.",
            diagram_type="graph",
            entities=("x-axis", "y-axis", "curve"),
            relationships=("curve is plotted against x",),
            equations=(),
            answer_relevant_observations=("The slope changes sign.",),
            ambiguities=(),
            confidence=0.9,
            requires_human_review=False,
            model=self.model,
            visual_evidence_refs=assessment.visual_evidence_refs,
            interpreted_at=datetime.now(tz=timezone.utc).isoformat(),
        )


class VisualInterpretationTests(TestCase):
    def test_enriches_and_caches_visual_interpretation(self) -> None:
        snapshot = build_sample_snapshot()
        with TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "question.png"
            image_path.write_bytes(b"test-image")
            evidence = EvidenceArtifact(
                id="visual-test",
                artifact_type="question_visual",
                locator=str(image_path),
                excerpt="Rendered question.",
                source_system="past_paper_visual",
                version=snapshot.version,
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
            )
            assessment = replace(
                snapshot.assessment_items[0],
                source_refs=snapshot.assessment_items[0].source_refs + (evidence.id,),
                visual_evidence_refs=(evidence.id,),
                requires_visual_interpretation=True,
            )
            visual_snapshot = replace(
                snapshot,
                assessment_items=(assessment,),
                evidence_artifacts=snapshot.evidence_artifacts + (evidence,),
            )
            interpreter = FakeVisionInterpreter()
            first = enrich_visual_interpretations(
                visual_snapshot,
                interpreter,
                cache_dir=Path(temp_dir) / "cache",
            )
            second = enrich_visual_interpretations(
                visual_snapshot,
                interpreter,
                cache_dir=Path(temp_dir) / "cache",
            )

        self.assertEqual(first.interpreted, 1)
        self.assertEqual(second.cached, 1)
        self.assertEqual(interpreter.calls, 1)
        self.assertIsNotNone(first.snapshot.assessment_items[0].visual_interpretation)
        self.assertEqual(
            first.snapshot.assessment_items[0].visual_interpretation_confidence,
            0.9,
        )

