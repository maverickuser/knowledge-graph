"""Deterministic community partitioning based on syllabus structure."""

from __future__ import annotations

from collections import defaultdict

from ..domain.ids import stable_id
from ..domain.models import Community, GraphSnapshot, SyllabusNode


def _children_index(nodes: tuple[SyllabusNode, ...]) -> dict[str | None, list[SyllabusNode]]:
    index: dict[str | None, list[SyllabusNode]] = defaultdict(list)
    for node in nodes:
        index[node.parent_id].append(node)
    for node_list in index.values():
        node_list.sort(key=lambda item: (item.order_index, item.title, item.id))
    return index


def _descendant_ids(node_id: str, children_by_parent: dict[str | None, list[SyllabusNode]]) -> set[str]:
    descendants: set[str] = {node_id}
    for child in children_by_parent.get(node_id, []):
        descendants.update(_descendant_ids(child.id, children_by_parent))
    return descendants


def partition_communities(snapshot: GraphSnapshot) -> tuple[Community, ...]:
    """Build communities from the syllabus hierarchy."""

    children_by_parent = _children_index(snapshot.syllabus_nodes)
    descendant_cache: dict[str, set[str]] = {
        node.id: _descendant_ids(node.id, children_by_parent) for node in snapshot.syllabus_nodes
    }

    communities: list[Community] = []
    for node in sorted(snapshot.syllabus_nodes, key=lambda item: (item.order_index, item.title, item.id)):
        descendant_node_ids = descendant_cache[node.id]
        member_ids: set[str] = set()

        for concept in snapshot.concepts:
            if set(concept.syllabus_node_ids) & descendant_node_ids:
                member_ids.add(concept.id)
        for skill in snapshot.skills:
            if set(skill.syllabus_node_ids) & descendant_node_ids:
                member_ids.add(skill.id)

        member_concept_skill_ids = member_ids.copy()
        for misconception in snapshot.misconceptions:
            if set(misconception.mapped_to_ids) & member_concept_skill_ids:
                member_ids.add(misconception.id)

        parent_id = stable_id("community", snapshot.graph_version, node.parent_id) if node.parent_id else None
        communities.append(
            Community(
                id=stable_id("community", snapshot.graph_version, node.id),
                level=node.level,
                parent_id=parent_id,
                member_ids=tuple(sorted(member_ids)),
                theme=node.title,
                version=snapshot.graph_version,
            )
        )

    return tuple(communities)
