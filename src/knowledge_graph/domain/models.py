"""Canonical graph and extraction data models."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from .ids import stable_id
from .serialization import SerializableArtifact, register_artifact


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


@register_artifact
@dataclass(frozen=True, slots=True)
class SourceDocument(SerializableArtifact):
    id: str
    local_path: str
    source_type: str
    title: str
    version: str
    checksum: str
    ingested_at: str
    source_system: str = "local"


@register_artifact
@dataclass(frozen=True, slots=True)
class DocumentSection(SerializableArtifact):
    id: str
    source_id: str
    title: str
    path: tuple[str, ...]
    start_line: int
    end_line: int
    text: str


@register_artifact
@dataclass(frozen=True, slots=True)
class NormalizedDocument(SerializableArtifact):
    id: str
    source_id: str
    normalized_text: str
    sections: tuple[DocumentSection, ...]
    version: str


@register_artifact
@dataclass(frozen=True, slots=True)
class SyllabusNode(SerializableArtifact):
    id: str
    title: str
    level: str
    parent_id: str | None
    order_index: int
    source_ref: str
    version: str


@register_artifact
@dataclass(frozen=True, slots=True)
class Concept(SerializableArtifact):
    id: str
    canonical_name: str
    definition: str
    subject: str
    grade_band: str
    source_refs: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    syllabus_node_ids: tuple[str, ...] = ()
    version: str = "1"


@register_artifact
@dataclass(frozen=True, slots=True)
class Skill(SerializableArtifact):
    id: str
    canonical_name: str
    success_criteria: str
    source_refs: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    syllabus_node_ids: tuple[str, ...] = ()
    version: str = "1"


@register_artifact
@dataclass(frozen=True, slots=True)
class PrerequisiteEdge(SerializableArtifact):
    id: str
    from_id: str
    to_id: str
    relation_type: str
    strength: float
    rationale: str
    source_refs: tuple[str, ...]
    version: str = "1"
    cross_link: bool = False


@register_artifact
@dataclass(frozen=True, slots=True)
class Misconception(SerializableArtifact):
    id: str
    label: str
    description: str
    trigger_patterns: tuple[str, ...]
    diagnostic_signals: tuple[str, ...]
    remediation_hint: str
    source_refs: tuple[str, ...]
    mapped_to_ids: tuple[str, ...]
    version: str = "1"


@register_artifact
@dataclass(frozen=True, slots=True)
class EvidenceArtifact(SerializableArtifact):
    id: str
    artifact_type: str
    locator: str
    excerpt: str
    source_system: str
    version: str
    timestamp: str


@register_artifact
@dataclass(frozen=True, slots=True)
class VisualInterpretation(SerializableArtifact):
    summary: str
    diagram_type: str
    entities: tuple[str, ...]
    relationships: tuple[str, ...]
    equations: tuple[str, ...]
    answer_relevant_observations: tuple[str, ...]
    ambiguities: tuple[str, ...]
    confidence: float
    requires_human_review: bool
    model: str
    visual_evidence_refs: tuple[str, ...]
    interpreted_at: str


@register_artifact
@dataclass(frozen=True, slots=True)
class AssessmentItem(SerializableArtifact):
    id: str
    prompt: str
    expected_concepts: tuple[str, ...]
    expected_steps: tuple[str, ...]
    rubric_ref: str
    source_refs: tuple[str, ...]
    visual_evidence_refs: tuple[str, ...] = ()
    requires_visual_interpretation: bool = False
    visual_interpretation: VisualInterpretation | None = None
    visual_interpretation_confidence: float = 0.0
    version: str = "1"


@register_artifact
@dataclass(frozen=True, slots=True)
class Community(SerializableArtifact):
    id: str
    level: str
    parent_id: str | None
    member_ids: tuple[str, ...]
    theme: str
    version: str


@register_artifact
@dataclass(frozen=True, slots=True)
class CommunitySummary(SerializableArtifact):
    id: str
    community_id: str
    summary_text: str
    salient_concepts: tuple[str, ...]
    salient_prereqs: tuple[str, ...]
    salient_misconceptions: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    generated_at: str
    version: str


@register_artifact
@dataclass(frozen=True, slots=True)
class PrimaryGap(SerializableArtifact):
    concept_id: str
    label: str


@register_artifact
@dataclass(frozen=True, slots=True)
class MisconceptionMatch(SerializableArtifact):
    misconception_id: str
    confidence: float


@register_artifact
@dataclass(frozen=True, slots=True)
class DiagnosticRecord(SerializableArtifact):
    id: str
    assessment_item_id: str
    student_response_id: str
    primary_gap: PrimaryGap | None
    prerequisite_chain: tuple[str, ...]
    misconception_match: MisconceptionMatch | None
    evidence_refs: tuple[str, ...]
    confidence: float
    abstained: bool
    abstention_reason: str | None
    version: str


@register_artifact
@dataclass(frozen=True, slots=True)
class GraphSeedBundle(SerializableArtifact):
    id: str
    graph_version: str
    extraction_version: str
    source_documents: tuple[SourceDocument, ...]
    normalized_documents: tuple[NormalizedDocument, ...]
    syllabus_nodes: tuple[SyllabusNode, ...]
    concepts: tuple[Concept, ...]
    skills: tuple[Skill, ...]
    prerequisite_edges: tuple[PrerequisiteEdge, ...]
    misconceptions: tuple[Misconception, ...]
    evidence_artifacts: tuple[EvidenceArtifact, ...]
    assessment_items: tuple[AssessmentItem, ...]
    created_at: str
    version: str


@register_artifact
@dataclass(frozen=True, slots=True)
class GraphSnapshot(SerializableArtifact):
    id: str
    graph_version: str
    seed_bundle_id: str
    source_documents: tuple[SourceDocument, ...]
    normalized_documents: tuple[NormalizedDocument, ...]
    syllabus_nodes: tuple[SyllabusNode, ...]
    concepts: tuple[Concept, ...]
    skills: tuple[Skill, ...]
    prerequisite_edges: tuple[PrerequisiteEdge, ...]
    misconceptions: tuple[Misconception, ...]
    evidence_artifacts: tuple[EvidenceArtifact, ...]
    assessment_items: tuple[AssessmentItem, ...]
    communities: tuple[Community, ...] = ()
    community_summaries: tuple[CommunitySummary, ...] = ()
    diagnostic_records: tuple[DiagnosticRecord, ...] = ()
    built_at: str = ""
    version: str = "1"

    def with_communities(self, communities: tuple[Community, ...]) -> "GraphSnapshot":
        return replace(self, communities=communities)

    def with_summaries(self, summaries: tuple[CommunitySummary, ...]) -> "GraphSnapshot":
        return replace(self, community_summaries=summaries)

    def with_diagnostics(self, diagnostics: tuple[DiagnosticRecord, ...]) -> "GraphSnapshot":
        return replace(self, diagnostic_records=diagnostics)


def make_source_document(
    local_path: Path,
    source_type: str,
    title: str,
    version: str,
    checksum: str,
    ingested_at: datetime | None = None,
    source_system: str = "local",
) -> SourceDocument:
    timestamp = (ingested_at or utc_now()).isoformat()
    return SourceDocument(
        id=stable_id("source", source_type, title, checksum, version),
        local_path=str(local_path),
        source_type=source_type,
        title=title,
        version=version,
        checksum=checksum,
        ingested_at=timestamp,
        source_system=source_system,
    )


def make_document_section(
    source_id: str,
    title: str,
    path: tuple[str, ...],
    start_line: int,
    end_line: int,
    text: str,
) -> DocumentSection:
    return DocumentSection(
        id=stable_id("section", source_id, title, str(start_line), str(end_line)),
        source_id=source_id,
        title=title,
        path=path,
        start_line=start_line,
        end_line=end_line,
        text=text,
    )


def make_normalized_document(
    source_id: str,
    normalized_text: str,
    sections: tuple[DocumentSection, ...],
    version: str,
) -> NormalizedDocument:
    return NormalizedDocument(
        id=stable_id("normalized", source_id, version),
        source_id=source_id,
        normalized_text=normalized_text,
        sections=sections,
        version=version,
    )
