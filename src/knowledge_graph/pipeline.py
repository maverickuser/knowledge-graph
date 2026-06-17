"""Operational workflows for building and persisting graph artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .community.partition import partition_communities
from .community.summarize import generate_community_summaries
from .domain.models import GraphSnapshot
from .domain.validation import ValidationReport, validate_graph_snapshot
from .graph.build import build_graph
from .ingestion.physics_corpus import build_physics_seed_bundle, load_physics_corpus
from .ingestion.reference_corpus import SOURCE_AUTHORITY_WEIGHTS
from .ingestion.visual_corpus import extract_visual_corpus
from .storage.json import JsonKnowledgeGraphRepository


def build_physics_graph(
    source_root: str | Path,
    *,
    graph_version: str,
    extraction_version: str,
    visual_output_dir: str | Path | None = None,
) -> tuple[GraphSnapshot, dict[str, Any]]:
    """Build the complete local graph and a reviewable build manifest."""

    source_path = Path(source_root).resolve()
    corpus = load_physics_corpus(source_path)
    visual_corpus = (
        extract_visual_corpus(
            source_path,
            visual_output_dir,
            version=extraction_version,
        )
        if visual_output_dir is not None
        and (source_path / "PastYearPaper" / "jee_physics_knowledge_graph.jsonl").exists()
        else None
    )
    seed_bundle = build_physics_seed_bundle(
        source_path,
        graph_version=graph_version,
        extraction_version=extraction_version,
        visual_corpus=visual_corpus,
    )
    snapshot = build_graph(seed_bundle)
    communities = partition_communities(snapshot)
    summaries = generate_community_summaries(snapshot, communities)
    snapshot = snapshot.with_communities(communities).with_summaries(summaries)
    report = validate_graph_snapshot(snapshot)
    report.raise_for_errors()

    topic_counts: dict[str, int] = {}
    for record in corpus.question_records:
        topic_counts[record.topic] = topic_counts.get(record.topic, 0) + 1

    manifest = {
        "built_at": datetime.now(tz=timezone.utc).isoformat(),
        "source_root": str(source_path),
        "graph_version": graph_version,
        "extraction_version": extraction_version,
        "seed_bundle_id": seed_bundle.id,
        "snapshot_id": snapshot.id,
        "counts": {
            "source_documents": len(snapshot.source_documents),
            "normalized_documents": len(snapshot.normalized_documents),
            "assessment_items": len(snapshot.assessment_items),
            "syllabus_nodes": len(snapshot.syllabus_nodes),
            "concepts": len(snapshot.concepts),
            "skills": len(snapshot.skills),
            "prerequisite_edges": len(snapshot.prerequisite_edges),
            "misconceptions": len(snapshot.misconceptions),
            "corrective_actions": len(snapshot.corrective_actions),
            "evidence_artifacts": len(snapshot.evidence_artifacts),
            "communities": len(snapshot.communities),
            "community_summaries": len(snapshot.community_summaries),
            "visual_evidence_artifacts": sum(
                evidence.artifact_type == "question_visual"
                for evidence in snapshot.evidence_artifacts
            ),
            "visual_assessment_items": sum(
                bool(item.visual_evidence_refs) for item in snapshot.assessment_items
            ),
            "requires_visual_interpretation": sum(
                item.requires_visual_interpretation
                for item in snapshot.assessment_items
            ),
        },
        "topic_counts": dict(sorted(topic_counts.items())),
        "skipped_sources": list(corpus.skipped_sources),
        "reference_warnings": [
            warning
            for source in snapshot.source_documents
            if source.source_system == "jee_syllabus"
            for warning in (
                "The registered syllabus PDF contains no extractable text; "
                "the JEE topic taxonomy is used for hierarchy.",
            )
        ],
        "source_authority_weights": SOURCE_AUTHORITY_WEIGHTS,
        "visual_warnings": list(visual_corpus.warnings) if visual_corpus else [],
        "validation": {"is_valid": report.is_valid, "issues": []},
    }
    return snapshot, manifest


def persist_local_graph(
    snapshot: GraphSnapshot,
    manifest: dict[str, Any],
    *,
    graph_dir: str | Path,
    manifests_dir: str | Path,
) -> tuple[Path, Path]:
    repository = JsonKnowledgeGraphRepository(graph_dir)
    repository.save_snapshot(snapshot)

    manifest_path = Path(manifests_dir) / f"{snapshot.graph_version}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    snapshot_path = repository.snapshots_dir / f"{snapshot.graph_version}.json"
    return snapshot_path, manifest_path


def validate_local_graph(
    graph_version: str,
    *,
    graph_dir: str | Path,
) -> tuple[GraphSnapshot, ValidationReport]:
    repository = JsonKnowledgeGraphRepository(graph_dir)
    snapshot = repository.load_snapshot(graph_version)
    if snapshot is None:
        raise FileNotFoundError(f"graph snapshot not found: {graph_version}")
    return snapshot, validate_graph_snapshot(snapshot)
