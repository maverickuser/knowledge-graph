"""Repository interface for graph persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..domain.models import CommunitySummary, DiagnosticRecord, GraphSnapshot


class KnowledgeGraphRepository(Protocol):
    """Persistence API for the canonical graph and derived artifacts."""

    def save_snapshot(self, snapshot: GraphSnapshot) -> None: ...

    def load_snapshot(self, graph_version: str) -> GraphSnapshot | None: ...

    def save_summary(self, summary: CommunitySummary) -> None: ...

    def load_summary(self, community_id: str, version: str) -> CommunitySummary | None: ...

    def list_summaries(self, graph_version: str | None = None) -> tuple[CommunitySummary, ...]: ...

    def save_diagnostic_record(self, record: DiagnosticRecord) -> None: ...

    def load_diagnostic_record(self, record_id: str, version: str) -> DiagnosticRecord | None: ...

    def list_diagnostic_records(
        self, assessment_item_id: str, graph_version: str | None = None
    ) -> tuple[DiagnosticRecord, ...]: ...


def ensure_directory(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory
