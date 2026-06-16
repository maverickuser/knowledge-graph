from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from knowledge_graph.main import main
from knowledge_graph.visualization.export import build_graph_visualization, export_graph_visualization
from tests.sample_data import build_sample_seed_bundle
from knowledge_graph.community.partition import partition_communities
from knowledge_graph.community.summarize import generate_community_summaries
from knowledge_graph.graph.build import build_graph


class VisualizationTests(TestCase):
    def test_export_graph_visualization_writes_files(self) -> None:
        snapshot = build_graph(build_sample_seed_bundle())
        snapshot = snapshot.with_communities(partition_communities(snapshot))
        snapshot = snapshot.with_summaries(generate_community_summaries(snapshot, snapshot.communities))

        with TemporaryDirectory() as temp_dir:
            written = export_graph_visualization(snapshot, temp_dir, base_name="sample-graph")
            self.assertTrue(written["svg"].exists())
            self.assertTrue(written["html"].exists())
            self.assertTrue(written["json"].exists())

            svg = written["svg"].read_text(encoding="utf-8")
            html = written["html"].read_text(encoding="utf-8")
            payload = json.loads(written["json"].read_text(encoding="utf-8"))

            self.assertIn("<svg", svg)
            self.assertEqual(written["svg"].name, "sample-graph.svg")
            self.assertEqual(written["html"].name, "sample-graph.html")
            self.assertEqual(written["json"].name, "sample-graph.json")
            self.assertIn("graph-v1 knowledge graph", html)
            self.assertIn("Concept Drilldown", html)
            self.assertIn("Community Prerequisite Matrix", html)
            self.assertGreaterEqual(len(payload["nodes"]), 2)
            self.assertGreaterEqual(len(payload["edges"]), 1)
            self.assertIn("concepts", payload)
            self.assertIn("matrix_cells", payload)

    def test_visualize_cli_exports_local_graph(self) -> None:
        fixture_root = Path(__file__).resolve().parent / "fixtures"
        with TemporaryDirectory() as temp_dir:
            env_root = Path(temp_dir)
            previous = __import__("os").environ.get("JEE_RAG_WORKSPACE_ROOT")
            __import__("os").environ["JEE_RAG_WORKSPACE_ROOT"] = str(env_root)
            try:
                self.assertEqual(
                    main(
                        [
                            "build",
                            "--source-root",
                            str(fixture_root),
                            "--graph-version",
                            "viz-v1",
                        ]
                    ),
                    0,
                )
                self.assertEqual(
                    main(
                        [
                            "visualize",
                            "--graph-version",
                            "viz-v1",
                            "--format",
                            "html",
                        ]
                    ),
                    0,
                )
                output_dir = env_root / "visualizations" / "viz-v1"
                self.assertTrue((output_dir / "viz-v1.html").exists())
            finally:
                if previous is None:
                    __import__("os").environ.pop("JEE_RAG_WORKSPACE_ROOT", None)
                else:
                    __import__("os").environ["JEE_RAG_WORKSPACE_ROOT"] = previous

