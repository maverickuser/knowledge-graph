"""Grounded diagnosis retrieval and response analysis."""

from __future__ import annotations

from collections import defaultdict

from ..domain.ids import normalize_text, stable_id
from ..domain.models import (
    Community,
    DiagnosticRecord,
    GraphSnapshot,
    MisconceptionMatch,
    PrimaryGap,
)
from .abstain import should_abstain
from .rank import DiagnosisCandidate, rank_candidates


_EVIDENCE_AUTHORITY = {
    "hc_verma": 1.0,
    "jee_syllabus": 0.95,
    "local": 0.9,
    "ncert": 0.8,
}


def _concept_name_map(snapshot: GraphSnapshot) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for concept in snapshot.concepts:
        mapping[concept.id] = concept.canonical_name
        for alias in concept.aliases:
            mapping[alias] = concept.id
    for skill in snapshot.skills:
        mapping[skill.id] = skill.canonical_name
        for alias in skill.aliases:
            mapping[alias] = skill.id
    return mapping


def _lookup_node_label(snapshot: GraphSnapshot, node_id: str) -> str:
    for concept in snapshot.concepts:
        if concept.id == node_id:
            return concept.canonical_name
    for skill in snapshot.skills:
        if skill.id == node_id:
            return skill.canonical_name
    return node_id


def _node_source_refs(snapshot: GraphSnapshot, node_id: str) -> tuple[str, ...]:
    for concept in snapshot.concepts:
        if concept.id == node_id:
            return concept.source_refs
    for skill in snapshot.skills:
        if skill.id == node_id:
            return skill.source_refs
    return ()


def _rank_evidence_refs(snapshot: GraphSnapshot, refs: set[str]) -> tuple[str, ...]:
    evidence_by_id = {evidence.id: evidence for evidence in snapshot.evidence_artifacts}
    return tuple(
        sorted(
            refs,
            key=lambda ref: (
                -_EVIDENCE_AUTHORITY.get(
                    evidence_by_id[ref].source_system if ref in evidence_by_id else "local",
                    0.0,
                ),
                ref,
            ),
        )
    )


def _known_nodes(snapshot: GraphSnapshot) -> set[str]:
    return {node.id for node in snapshot.concepts} | {node.id for node in snapshot.skills}


def _expected_node_ids(snapshot: GraphSnapshot, assessment_item_id: str) -> tuple[str, ...]:
    assessment_item = next((item for item in snapshot.assessment_items if item.id == assessment_item_id), None)
    if assessment_item is None:
        return ()
    return tuple(sorted(set(assessment_item.expected_concepts) | set(assessment_item.expected_steps)))


def _response_coverage(snapshot: GraphSnapshot, response_text: str) -> set[str]:
    normalized_response = normalize_text(response_text)
    covered: set[str] = set()

    for concept in snapshot.concepts:
        if concept.canonical_name.lower() in normalized_response:
            covered.add(concept.id)
            continue
        if any(alias.lower() in normalized_response for alias in concept.aliases):
            covered.add(concept.id)

    for skill in snapshot.skills:
        if skill.canonical_name.lower() in normalized_response:
            covered.add(skill.id)
            continue
        if any(alias.lower() in normalized_response for alias in skill.aliases):
            covered.add(skill.id)

    return covered


def _find_misconception_match(
    snapshot: GraphSnapshot,
    response_text: str,
) -> tuple[MisconceptionMatch | None, tuple[str, ...]]:
    normalized_response = normalize_text(response_text)
    best_match: MisconceptionMatch | None = None
    best_refs: tuple[str, ...] = ()

    for misconception in snapshot.misconceptions:
        trigger_hits = sum(1 for pattern in misconception.trigger_patterns if pattern.lower() in normalized_response)
        signal_hits = sum(1 for pattern in misconception.diagnostic_signals if pattern.lower() in normalized_response)
        total_hits = trigger_hits + signal_hits
        if not total_hits:
            continue

        confidence = min(1.0, 0.35 + 0.2 * total_hits)
        match = MisconceptionMatch(misconception_id=misconception.id, confidence=confidence)
        if best_match is None or confidence > best_match.confidence or (
            confidence == best_match.confidence and misconception.id < best_match.misconception_id
        ):
            best_match = match
            best_refs = misconception.source_refs

    return best_match, best_refs


def _prerequisite_parents(snapshot: GraphSnapshot) -> dict[str, tuple[str, ...]]:
    parents: dict[str, list[str]] = defaultdict(list)
    for edge in snapshot.prerequisite_edges:
        if edge.cross_link:
            continue
        parents[edge.to_id].append(edge.from_id)
    return {node_id: tuple(sorted(parent_ids)) for node_id, parent_ids in parents.items()}


def _trace_missing_chain(
    snapshot: GraphSnapshot,
    target_id: str,
    covered: set[str],
    parent_map: dict[str, tuple[str, ...]],
    path: tuple[str, ...] = (),
) -> tuple[str, ...]:
    if target_id in path:
        return ()

    prerequisites = parent_map.get(target_id, ())
    for prerequisite_id in prerequisites:
        prerequisite_chain = _trace_missing_chain(
            snapshot=snapshot,
            target_id=prerequisite_id,
            covered=covered,
            parent_map=parent_map,
            path=path + (target_id,),
        )
        if prerequisite_chain:
            return prerequisite_chain + (target_id,)
        if prerequisite_id not in covered:
            return (prerequisite_id, target_id)

    if target_id not in covered:
        return (target_id,)
    return ()


def _build_candidate(
    snapshot: GraphSnapshot,
    assessment_item_id: str,
    response_text: str,
) -> DiagnosisCandidate | None:
    expected_node_ids = _expected_node_ids(snapshot, assessment_item_id)
    covered = _response_coverage(snapshot, response_text)
    misconception_match, misconception_refs = _find_misconception_match(snapshot, response_text)
    parent_map = _prerequisite_parents(snapshot)

    chains = []
    for expected_id in expected_node_ids:
        chain = _trace_missing_chain(snapshot, expected_id, covered, parent_map)
        if chain:
            chains.append(chain)

    best_chain = min(chains, key=lambda chain: (len(chain), chain)) if chains else ()
    primary_gap = None
    if best_chain:
        gap_id = best_chain[0]
        primary_gap = PrimaryGap(concept_id=gap_id, label=_lookup_node_label(snapshot, gap_id))
    elif misconception_match is not None:
        mapped_target = next(
            (node_id for node_id in snapshot.misconceptions if node_id.id == misconception_match.misconception_id),
            None,
        )
        if mapped_target is not None and mapped_target.mapped_to_ids:
            gap_id = mapped_target.mapped_to_ids[0]
            primary_gap = PrimaryGap(concept_id=gap_id, label=_lookup_node_label(snapshot, gap_id))

    evidence_refs = _rank_evidence_refs(
        snapshot,
        set(misconception_refs)
        | set(next((item.source_refs for item in snapshot.assessment_items if item.id == assessment_item_id), ()))
        | {
            ref
            for gap_id in (best_chain or ())
            for ref in _node_source_refs(snapshot, gap_id)
        }
    )

    if primary_gap is None:
        return None

    score = 0.0
    if primary_gap is not None:
        score += 0.4
    if best_chain and len(best_chain) > 1:
        score += min(0.2, 0.05 * len(best_chain))
    if misconception_match is not None:
        score += misconception_match.confidence * 0.4
    if evidence_refs:
        score += 0.15
    if covered:
        score += min(0.15, 0.02 * len(covered))
    score = min(1.0, score)

    return DiagnosisCandidate(
        primary_gap=primary_gap,
        prerequisite_chain=best_chain,
        misconception_match=misconception_match,
        evidence_refs=evidence_refs,
        score=score,
    )


def find_relevant_communities(snapshot: GraphSnapshot, assessment_item_id: str, response_text: str) -> tuple[Community, ...]:
    expected_ids = set(_expected_node_ids(snapshot, assessment_item_id))
    covered = _response_coverage(snapshot, response_text)
    relevant: list[Community] = []
    for community in snapshot.communities:
        member_ids = set(community.member_ids)
        if member_ids & expected_ids or member_ids & covered:
            relevant.append(community)
    return tuple(sorted(relevant, key=lambda item: (item.level, item.theme, item.id)))


def _leaf_communities(communities: tuple[Community, ...]) -> tuple[Community, ...]:
    parent_ids = {community.parent_id for community in communities if community.parent_id}
    leaves = tuple(community for community in communities if community.id not in parent_ids)
    return leaves or communities


def diagnose_response(
    snapshot: GraphSnapshot,
    assessment_item_id: str,
    student_response_id: str,
    response_text: str,
    *,
    version: str | None = None,
    threshold: float = 0.55,
) -> DiagnosticRecord:
    assessment_item = next((item for item in snapshot.assessment_items if item.id == assessment_item_id), None)
    if assessment_item is None:
        raise ValueError(f"unknown assessment item: {assessment_item_id}")
    if (
        assessment_item.requires_visual_interpretation
        and not assessment_item.visual_interpretation
    ):
        return DiagnosticRecord(
            id=stable_id("diagnostic", assessment_item_id, student_response_id, version or snapshot.graph_version),
            assessment_item_id=assessment_item_id,
            student_response_id=student_response_id,
            primary_gap=None,
            prerequisite_chain=(),
            misconception_match=None,
            evidence_refs=_rank_evidence_refs(
                snapshot,
                set(assessment_item.source_refs)
                | set(assessment_item.visual_evidence_refs),
            ),
            confidence=0.0,
            abstained=True,
            abstention_reason="visual_interpretation_required",
            version=version or snapshot.graph_version,
        )

    candidate = _build_candidate(snapshot, assessment_item_id, response_text)
    relevant_communities = _leaf_communities(
        find_relevant_communities(snapshot, assessment_item_id, response_text)
    )
    community_evidence_refs = {
        ref
        for community in relevant_communities
        for summary in snapshot.community_summaries
        if summary.community_id == community.id
        for ref in summary.evidence_refs
    }
    if should_abstain(candidate, threshold=threshold):
        return DiagnosticRecord(
            id=stable_id("diagnostic", assessment_item_id, student_response_id, version or snapshot.graph_version),
            assessment_item_id=assessment_item_id,
            student_response_id=student_response_id,
            primary_gap=None,
            prerequisite_chain=(),
            misconception_match=None,
            evidence_refs=_rank_evidence_refs(
                snapshot, set(assessment_item.source_refs) | community_evidence_refs
            ),
            confidence=0.0,
            abstained=True,
            abstention_reason="insufficient_grounding",
            version=version or snapshot.graph_version,
        )

    assert candidate is not None
    evidence_refs = _rank_evidence_refs(
        snapshot,
        set(candidate.evidence_refs)
        | set(assessment_item.source_refs)
        | community_evidence_refs
        | {ref for gap_id in candidate.prerequisite_chain for ref in _node_source_refs(snapshot, gap_id)},
    )

    return DiagnosticRecord(
        id=stable_id("diagnostic", assessment_item_id, student_response_id, version or snapshot.graph_version),
        assessment_item_id=assessment_item_id,
        student_response_id=student_response_id,
        primary_gap=candidate.primary_gap,
        prerequisite_chain=candidate.prerequisite_chain,
        misconception_match=candidate.misconception_match,
        evidence_refs=evidence_refs,
        confidence=candidate.score,
        abstained=False,
        abstention_reason=None,
        version=version or snapshot.graph_version,
    )
