"""JSON file repository for local development and fixture persistence."""

from __future__ import annotations

import json
from pathlib import Path

from ..domain.models import CommunitySummary, DiagnosticRecord, GraphSnapshot
from .repository import KnowledgeGraphRepository, ensure_directory


class JsonKnowledgeGraphRepository(KnowledgeGraphRepository):
    def __init__(self, root: str | Path) -> None:
        self.root = ensure_directory(root)
        self.snapshots_dir = ensure_directory(self.root / "snapshots")
        self.summaries_dir = ensure_directory(self.root / "summaries")
        self.diagnostics_dir = ensure_directory(self.root / "diagnostics")

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _read_json(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_snapshot(self, snapshot: GraphSnapshot) -> None:
        self._write_json(self.snapshots_dir / f"{snapshot.graph_version}.json", snapshot.to_dict())
        for summary in snapshot.community_summaries:
            self.save_summary(summary)
        for diagnostic in snapshot.diagnostic_records:
            self.save_diagnostic_record(diagnostic)

    def load_snapshot(self, graph_version: str) -> GraphSnapshot | None:
        payload = self._read_json(self.snapshots_dir / f"{graph_version}.json")
        if payload is None:
            return None
        return GraphSnapshot.from_dict(payload)

    def save_summary(self, summary: CommunitySummary) -> None:
        summary_dir = ensure_directory(self.summaries_dir / summary.community_id)
        self._write_json(summary_dir / f"{summary.version}.json", summary.to_dict())

    def load_summary(self, community_id: str, version: str) -> CommunitySummary | None:
        payload = self._read_json(self.summaries_dir / community_id / f"{version}.json")
        if payload is None:
            return None
        return CommunitySummary.from_dict(payload)

    def list_summaries(self, graph_version: str | None = None) -> tuple[CommunitySummary, ...]:
        summaries: list[CommunitySummary] = []
        for community_dir in sorted(self.summaries_dir.iterdir()):
            if not community_dir.is_dir():
                continue
            for summary_file in sorted(community_dir.glob("*.json")):
                summary = CommunitySummary.from_dict(json.loads(summary_file.read_text(encoding="utf-8")))
                if graph_version is None or summary.version == graph_version:
                    summaries.append(summary)
        return tuple(sorted(summaries, key=lambda item: (item.community_id, item.version)))

    def save_diagnostic_record(self, record: DiagnosticRecord) -> None:
        record_dir = ensure_directory(self.diagnostics_dir / record.assessment_item_id / record.id)
        self._write_json(record_dir / f"{record.version}.json", record.to_dict())

    def load_diagnostic_record(self, record_id: str, version: str) -> DiagnosticRecord | None:
        for assessment_dir in sorted(self.diagnostics_dir.iterdir()):
            if not assessment_dir.is_dir():
                continue
            record_payload = self._read_json(assessment_dir / record_id / f"{version}.json")
            if record_payload is not None:
                return DiagnosticRecord.from_dict(record_payload)
        return None

    def list_diagnostic_records(
        self, assessment_item_id: str, graph_version: str | None = None
    ) -> tuple[DiagnosticRecord, ...]:
        assessment_dir = self.diagnostics_dir / assessment_item_id
        if not assessment_dir.exists():
            return ()
        diagnostics: list[DiagnosticRecord] = []
        for record_dir in sorted(assessment_dir.iterdir()):
            if not record_dir.is_dir():
                continue
            for payload_file in sorted(record_dir.glob("*.json")):
                record = DiagnosticRecord.from_dict(
                    json.loads(payload_file.read_text(encoding="utf-8"))
                )
                if graph_version is None or record.version == graph_version:
                    diagnostics.append(record)
        return tuple(sorted(diagnostics, key=lambda item: (item.assessment_item_id, item.version, item.id)))
