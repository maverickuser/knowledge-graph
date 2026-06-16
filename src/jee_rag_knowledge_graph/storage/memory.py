"""In-memory repository for local workflows and tests."""

from __future__ import annotations

from ..domain.models import CommunitySummary, DiagnosticRecord, GraphSnapshot
from .repository import KnowledgeGraphRepository


class InMemoryKnowledgeGraphRepository(KnowledgeGraphRepository):
    def __init__(self) -> None:
        self._snapshots: dict[str, GraphSnapshot] = {}
        self._summaries: dict[tuple[str, str], CommunitySummary] = {}
        self._diagnostics: dict[tuple[str, str], DiagnosticRecord] = {}

    def save_snapshot(self, snapshot: GraphSnapshot) -> None:
        self._snapshots[snapshot.graph_version] = snapshot
        for summary in snapshot.community_summaries:
            self.save_summary(summary)
        for diagnostic in snapshot.diagnostic_records:
            self.save_diagnostic_record(diagnostic)

    def load_snapshot(self, graph_version: str) -> GraphSnapshot | None:
        return self._snapshots.get(graph_version)

    def save_summary(self, summary: CommunitySummary) -> None:
        self._summaries[(summary.community_id, summary.version)] = summary

    def load_summary(self, community_id: str, version: str) -> CommunitySummary | None:
        return self._summaries.get((community_id, version))

    def list_summaries(self, graph_version: str | None = None) -> tuple[CommunitySummary, ...]:
        summaries = tuple(self._summaries.values())
        if graph_version is None:
            return tuple(sorted(summaries, key=lambda item: (item.community_id, item.version)))
        return tuple(sorted((item for item in summaries if item.version == graph_version), key=lambda item: (item.community_id, item.version)))

    def save_diagnostic_record(self, record: DiagnosticRecord) -> None:
        self._diagnostics[(record.id, record.version)] = record

    def load_diagnostic_record(self, record_id: str, version: str) -> DiagnosticRecord | None:
        return self._diagnostics.get((record_id, version))

    def list_diagnostic_records(
        self, assessment_item_id: str, graph_version: str | None = None
    ) -> tuple[DiagnosticRecord, ...]:
        diagnostics = tuple(
            item for item in self._diagnostics.values() if item.assessment_item_id == assessment_item_id
        )
        if graph_version is None:
            return tuple(sorted(diagnostics, key=lambda item: (item.assessment_item_id, item.version, item.id)))
        return tuple(
            sorted(
                (item for item in diagnostics if item.version == graph_version),
                key=lambda item: (item.assessment_item_id, item.version, item.id),
            )
        )
