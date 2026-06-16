from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from jee_rag_knowledge_graph.main import main
from tests.sample_data import build_sample_snapshot


class CliTests(TestCase):
    def test_build_validate_and_show_local_graph(self) -> None:
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
                            "cli-v1",
                        ]
                    ),
                    0,
                )
                self.assertEqual(main(["validate", "--graph-version", "cli-v1"]), 0)
                snapshot_path = env_root / "data" / "graph" / "snapshots" / "cli-v1.json"
                manifest_path = env_root / "data" / "manifests" / "cli-v1.json"
                self.assertTrue(snapshot_path.exists())
                self.assertTrue(manifest_path.exists())
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual(manifest["counts"]["assessment_items"], 2)
                self.assertTrue(manifest["validation"]["is_valid"])
            finally:
                if previous is None:
                    __import__("os").environ.pop("JEE_RAG_WORKSPACE_ROOT", None)
                else:
                    __import__("os").environ["JEE_RAG_WORKSPACE_ROOT"] = previous

    def test_persist_snapshot_command_writes_local_json(self) -> None:
        snapshot = build_sample_snapshot()
        with TemporaryDirectory() as temp_dir:
            env_root = Path(temp_dir)
            previous = __import__("os").environ.get("JEE_RAG_WORKSPACE_ROOT")
            __import__("os").environ["JEE_RAG_WORKSPACE_ROOT"] = str(env_root)
            try:
                release_dir = env_root / "release"
                release_dir.mkdir(parents=True, exist_ok=True)
                snapshot_path = release_dir / "graph.json"
                snapshot_path.write_text(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
                self.assertEqual(
                    main(
                        [
                            "persist-snapshot",
                            "--snapshot-path",
                            str(snapshot_path),
                            "--backend",
                            "json",
                        ]
                    ),
                    0,
                )
                persisted = env_root / "data" / "graph" / "snapshots" / f"{snapshot.graph_version}.json"
                self.assertTrue(persisted.exists())
            finally:
                if previous is None:
                    __import__("os").environ.pop("JEE_RAG_WORKSPACE_ROOT", None)
                else:
                    __import__("os").environ["JEE_RAG_WORKSPACE_ROOT"] = previous
