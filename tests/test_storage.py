from __future__ import annotations

from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from jee_rag_knowledge_graph.storage.dynamodb import DynamoDBKnowledgeGraphRepository
from jee_rag_knowledge_graph.storage.json import JsonKnowledgeGraphRepository
from jee_rag_knowledge_graph.storage.memory import InMemoryKnowledgeGraphRepository
from tests.sample_data import build_sample_snapshot


class StorageTests(TestCase):
    def test_memory_repository_round_trip(self) -> None:
        snapshot = build_sample_snapshot()
        repository = InMemoryKnowledgeGraphRepository()
        repository.save_snapshot(snapshot)

        loaded = repository.load_snapshot(snapshot.graph_version)
        self.assertEqual(loaded, snapshot)
        self.assertTrue(repository.list_summaries(snapshot.graph_version))
        self.assertTrue(repository.list_diagnostic_records("assessment-quadratic-001", snapshot.graph_version))

    def test_json_repository_round_trip(self) -> None:
        snapshot = build_sample_snapshot()
        with TemporaryDirectory() as temp_dir:
            repository = JsonKnowledgeGraphRepository(temp_dir)
            repository.save_snapshot(snapshot)

            loaded = repository.load_snapshot(snapshot.graph_version)
            self.assertEqual(loaded, snapshot)

    def test_dynamodb_repository_writes_and_loads_snapshot(self) -> None:
        class FakeTable:
            def __init__(self) -> None:
                self.items = []

            def put_item(self, *, Item) -> None:
                self.items.append(Item)

        class FakeResource:
            def __init__(self, table: FakeTable) -> None:
                self.table = table

            def Table(self, name: str) -> FakeTable:
                self.name = name
                return self.table

        snapshot = build_sample_snapshot()
        table = FakeTable()
        repository = DynamoDBKnowledgeGraphRepository(
            "graph-table",
            "ap-south-1",
            resource=FakeResource(table),
        )
        repository.save_snapshot(snapshot)

        artifact_types = {item["artifact_type"] for item in table.items}
        self.assertIn("GraphSnapshot", artifact_types)
        self.assertIn("CommunitySummary", artifact_types)
        self.assertIn("DiagnosticRecord", artifact_types)
        snapshot_item = next(
            item for item in table.items if item["artifact_type"] == "GraphSnapshot"
        )
        with patch.object(repository, "_query_single", return_value=snapshot_item):
            loaded = repository.load_snapshot(snapshot.graph_version)
        self.assertEqual(loaded, snapshot)
