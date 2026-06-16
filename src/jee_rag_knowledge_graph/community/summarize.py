"""Generate deterministic summaries from graph communities."""

from __future__ import annotations

from datetime import datetime, timezone

from ..domain.ids import stable_id
from ..domain.models import Community, CommunitySummary, GraphSnapshot


def _node_label(snapshot: GraphSnapshot, node_id: str) -> str:
    for concept in snapshot.concepts:
        if concept.id == node_id:
            return concept.canonical_name
    for skill in snapshot.skills:
        if skill.id == node_id:
            return skill.canonical_name
    return node_id


def generate_community_summaries(
    snapshot: GraphSnapshot,
    communities: tuple[Community, ...],
) -> tuple[CommunitySummary, ...]:
    """Create summary artifacts from the graph state only."""

    concept_by_id = {concept.id: concept for concept in snapshot.concepts}
    skill_by_id = {skill.id: skill for skill in snapshot.skills}
    misconception_by_id = {misconception.id: misconception for misconception in snapshot.misconceptions}
    edge_by_id = {edge.id: edge for edge in snapshot.prerequisite_edges}

    summaries: list[CommunitySummary] = []
    generated_at = datetime.now(tz=timezone.utc).isoformat()

    for community in communities:
        member_ids = set(community.member_ids)
        salient_concepts = tuple(
            sorted(
                (
                    node_id
                    for node_id in member_ids
                    if node_id in concept_by_id or node_id in skill_by_id
                ),
                key=lambda node_id: (_node_label(snapshot, node_id), node_id),
            )
        )

        salient_prereqs = tuple(
            sorted(
                {
                    edge.from_id
                    for edge in snapshot.prerequisite_edges
                    if edge.to_id in member_ids and edge.from_id in member_ids
                }
                | {
                    edge.to_id
                    for edge in snapshot.prerequisite_edges
                    if edge.to_id in member_ids and edge.from_id in member_ids
                }
            )
        )

        salient_misconceptions = tuple(
            sorted(
                misconception_id
                for misconception_id in member_ids
                if misconception_id in misconception_by_id
            )
        )

        evidence_refs = sorted(
            {
                ref
                for node_id in salient_concepts
                for ref in (
                    concept_by_id.get(node_id).source_refs if node_id in concept_by_id else skill_by_id[node_id].source_refs
                )
            }
            | {
                ref
                for misconception_id in salient_misconceptions
                for ref in misconception_by_id[misconception_id].source_refs
            }
            | {
                ref
                for prereq_id in salient_prereqs
                for edge in edge_by_id.values()
                if prereq_id in {edge.from_id, edge.to_id}
                for ref in edge.source_refs
            }
        )

        concept_labels = [
            _node_label(snapshot, node_id)
            for node_id in salient_concepts
        ]
        misconception_labels = [misconception_by_id[node_id].label for node_id in salient_misconceptions]
        prereq_labels = [
            _node_label(snapshot, node_id)
            for node_id in salient_prereqs
        ]
        summary_text = (
            f"Theme: {community.theme}. "
            f"Concepts: {', '.join(concept_labels[:5]) or 'none'}. "
            f"Prerequisites: {', '.join(prereq_labels[:5]) or 'none'}. "
            f"Misconceptions: {', '.join(misconception_labels[:5]) or 'none'}."
        )

        summaries.append(
            CommunitySummary(
                id=stable_id("summary", community.id, snapshot.graph_version),
                community_id=community.id,
                summary_text=summary_text,
                salient_concepts=salient_concepts,
                salient_prereqs=salient_prereqs,
                salient_misconceptions=salient_misconceptions,
                evidence_refs=tuple(evidence_refs),
                generated_at=generated_at,
                version=snapshot.graph_version,
            )
        )

    return tuple(summaries)
