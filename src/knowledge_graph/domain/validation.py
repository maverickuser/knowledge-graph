"""Validation rules for graph artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..exceptions import ValidationError
from .models import (
    AssessmentItem,
    Community,
    CommunitySummary,
    Concept,
    DiagnosticRecord,
    GraphSeedBundle,
    GraphSnapshot,
    Misconception,
    PrerequisiteEdge,
    Skill,
    SyllabusNode,
)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    artifact_id: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.issues

    def raise_for_errors(self) -> None:
        if self.issues:
            details = "; ".join(f"{issue.code}: {issue.message}" for issue in self.issues)
            raise ValidationError(details)


def _indexed(items: Iterable[object]) -> dict[str, object]:
    index: dict[str, object] = {}
    for item in items:
        item_id = getattr(item, "id", None)
        if item_id:
            index[item_id] = item
    return index


def _detect_cycles(edges: Iterable[PrerequisiteEdge]) -> list[list[str]]:
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        if edge.cross_link:
            continue
        adjacency.setdefault(edge.from_id, []).append(edge.to_id)

    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            if node_id in stack:
                idx = stack.index(node_id)
                cycles.append(stack[idx:] + [node_id])
            return

        visiting.add(node_id)
        stack.append(node_id)
        for neighbor in adjacency.get(node_id, []):
            visit(neighbor)
        stack.pop()
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in sorted(adjacency):
        visit(node_id)

    return cycles


def validate_graph_seed_bundle(bundle: GraphSeedBundle) -> ValidationReport:
    issues: list[ValidationIssue] = []
    if not bundle.graph_version.strip():
        issues.append(ValidationIssue("missing_graph_version", "graph_version must not be empty", bundle.id))
    if not bundle.extraction_version.strip():
        issues.append(ValidationIssue("missing_extraction_version", "extraction_version must not be empty", bundle.id))
    if not bundle.source_documents:
        issues.append(ValidationIssue("missing_sources", "at least one source document is required", bundle.id))
    return ValidationReport(tuple(issues))


def validate_graph_snapshot(snapshot: GraphSnapshot) -> ValidationReport:
    issues: list[ValidationIssue] = []

    concept_index = _indexed(snapshot.concepts)
    skill_index = _indexed(snapshot.skills)
    node_index = {
        **_indexed(snapshot.syllabus_nodes),
        **concept_index,
        **skill_index,
    }
    evidence_index = _indexed(snapshot.evidence_artifacts)

    for concept in snapshot.concepts:
        if not concept.definition.strip():
            issues.append(ValidationIssue("missing_definition", "concept definition is required", concept.id))
        if not concept.source_refs:
            issues.append(ValidationIssue("missing_provenance", "concept must have provenance", concept.id))
        if not concept.syllabus_node_ids:
            issues.append(ValidationIssue("missing_syllabus_link", "concept must belong to a syllabus node", concept.id))

    for skill in snapshot.skills:
        if not skill.success_criteria.strip():
            issues.append(ValidationIssue("missing_success_criteria", "skill success criteria is required", skill.id))
        if not skill.source_refs:
            issues.append(ValidationIssue("missing_provenance", "skill must have provenance", skill.id))
        if not skill.syllabus_node_ids:
            issues.append(ValidationIssue("missing_syllabus_link", "skill must belong to a syllabus node", skill.id))

    for edge in snapshot.prerequisite_edges:
        if edge.from_id == edge.to_id:
            issues.append(ValidationIssue("self_cycle", "prerequisite edge cannot point to itself", edge.id))
        if edge.from_id not in node_index:
            issues.append(ValidationIssue("missing_from_node", "prerequisite source node was not found", edge.id))
        if edge.to_id not in node_index:
            issues.append(ValidationIssue("missing_to_node", "prerequisite target node was not found", edge.id))
        if edge.strength < 0.0 or edge.strength > 1.0:
            issues.append(ValidationIssue("invalid_strength", "strength must be between 0 and 1", edge.id))
        if not edge.source_refs:
            issues.append(ValidationIssue("missing_provenance", "prerequisite edge must have provenance", edge.id))

    for misconception in snapshot.misconceptions:
        if not misconception.mapped_to_ids:
            issues.append(
                ValidationIssue("missing_mapping", "misconception must map to at least one concept or skill", misconception.id)
            )
        if not misconception.source_refs:
            issues.append(ValidationIssue("missing_provenance", "misconception must have provenance", misconception.id))

    for assessment in snapshot.assessment_items:
        for evidence_ref in assessment.visual_evidence_refs:
            evidence = evidence_index.get(evidence_ref)
            if evidence is None:
                issues.append(
                    ValidationIssue(
                        "missing_visual_evidence",
                        "assessment references unknown visual evidence",
                        assessment.id,
                    )
                )
            elif getattr(evidence, "artifact_type", "") != "question_visual":
                issues.append(
                    ValidationIssue(
                        "invalid_visual_evidence",
                        "assessment visual reference must target question_visual evidence",
                        assessment.id,
                    )
                )
        if assessment.requires_visual_interpretation and not assessment.visual_evidence_refs:
            issues.append(
                ValidationIssue(
                    "visual_evidence_required",
                    "visually dependent assessment has no visual evidence",
                    assessment.id,
                )
            )
        if (
            assessment.visual_interpretation_confidence < 0.0
            or assessment.visual_interpretation_confidence > 1.0
        ):
            issues.append(
                ValidationIssue(
                    "invalid_visual_confidence",
                    "visual interpretation confidence must be between 0 and 1",
                    assessment.id,
                )
            )
        if assessment.visual_interpretation is not None:
            if (
                assessment.visual_interpretation.visual_evidence_refs
                != assessment.visual_evidence_refs
            ):
                issues.append(
                    ValidationIssue(
                        "visual_interpretation_evidence_mismatch",
                        "visual interpretation must reference the assessment visuals",
                        assessment.id,
                    )
                )
            if (
                assessment.visual_interpretation.confidence
                != assessment.visual_interpretation_confidence
            ):
                issues.append(
                    ValidationIssue(
                        "visual_interpretation_confidence_mismatch",
                        "assessment and interpretation confidence must match",
                        assessment.id,
                    )
                )

    for summary in snapshot.community_summaries:
        community = next((item for item in snapshot.communities if item.id == summary.community_id), None)
        if community is None:
            issues.append(ValidationIssue("missing_community", "summary references an unknown community", summary.id))
            continue

        member_ids = set(community.member_ids)
        for concept_id in summary.salient_concepts:
            if concept_id not in member_ids:
                issues.append(ValidationIssue("summary_out_of_bounds", "summary concept must belong to the community", summary.id))
        for prereq_id in summary.salient_prereqs:
            if prereq_id not in member_ids:
                issues.append(ValidationIssue("summary_out_of_bounds", "summary prerequisite must belong to the community", summary.id))
        for misconception_id in summary.salient_misconceptions:
            if misconception_id not in member_ids and misconception_id not in {m.id for m in snapshot.misconceptions}:
                issues.append(ValidationIssue("summary_out_of_bounds", "summary misconception must be known", summary.id))

    for diagnostic in snapshot.diagnostic_records:
        if not diagnostic.abstained:
            if diagnostic.primary_gap is None:
                issues.append(ValidationIssue("missing_primary_gap", "non-abstaining diagnostics must include a primary gap", diagnostic.id))
            if not diagnostic.evidence_refs:
                issues.append(ValidationIssue("missing_evidence", "non-abstaining diagnostics must include evidence", diagnostic.id))
        elif diagnostic.abstention_reason is None:
            issues.append(ValidationIssue("missing_abstention_reason", "abstentions should state a reason", diagnostic.id))

    cycles = _detect_cycles(snapshot.prerequisite_edges)
    for cycle in cycles:
        issues.append(ValidationIssue("prerequisite_cycle", "prerequisite cycle detected", " -> ".join(cycle)))

    return ValidationReport(tuple(issues))
