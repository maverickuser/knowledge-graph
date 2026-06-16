from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from jee_rag_knowledge_graph.ingestion.visual_corpus import parse_question_regions


class VisualCorpusTests(TestCase):
    def test_parse_question_regions_respects_columns_and_next_question(self) -> None:
        payload = """\
<html xmlns="http://www.w3.org/1999/xhtml"><body><doc>
<page width="600" height="800"><flow><block>
<line xMin="35" yMin="100" xMax="200" yMax="115"><word>26.</word><word>A</word></line>
<line xMin="35" yMin="350" xMax="100" yMax="365"><word>Ans.</word><word>(2)</word></line>
<line xMin="35" yMin="400" xMax="200" yMax="415"><word>27.</word></line>
<line xMin="305" yMin="120" xMax="500" yMax="135"><word>28.</word></line>
</block></flow></page></doc></body></html>
"""
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bbox.html"
            path.write_text(payload, encoding="utf-8")
            regions = parse_question_regions(path)

        by_number = {region.question_no: region for region in regions}
        self.assertEqual(by_number[26].page_number, 1)
        self.assertEqual(by_number[26].y_max, 346.0)
        self.assertLess(by_number[26].x_max, 300.0)
        self.assertGreaterEqual(by_number[28].x_min, 300.0)
