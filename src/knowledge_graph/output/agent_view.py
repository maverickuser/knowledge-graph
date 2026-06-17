"""Build a denormalized graph view for agent inspection."""

from __future__ import annotations

from typing import Any

from ..domain.models import GraphSnapshot


def _label_by_id(snapshot: GraphSnapshot) -> dict[str, str]:
    labels = {node.id: node.title for node in snapshot.syllabus_nodes}
    labels.update({concept.id: concept.canonical_name for concept in snapshot.concepts})
    labels.update({skill.id: skill.canonical_name for skill in snapshot.skills})
    labels.update({misconception.id: misconception.label for misconception in snapshot.misconceptions})
    return labels


def _syllabus_paths(snapshot: GraphSnapshot) -> dict[str, tuple[str, ...]]:
    node_by_id = {node.id: node for node in snapshot.syllabus_nodes}
    paths: dict[str, tuple[str, ...]] = {}

    def path_for(node_id: str) -> tuple[str, ...]:
        if node_id in paths:
            return paths[node_id]
        node = node_by_id[node_id]
        if node.parent_id and node.parent_id in node_by_id:
            value = path_for(node.parent_id) + (node.title,)
        else:
            value = (node.title,)
        paths[node_id] = value
        return value

    for node in snapshot.syllabus_nodes:
        path_for(node.id)
    return paths


def _hierarchy(snapshot: GraphSnapshot) -> list[dict[str, Any]]:
    children_by_parent: dict[str | None, list[Any]] = {}
    for node in snapshot.syllabus_nodes:
        children_by_parent.setdefault(node.parent_id, []).append(node)
    for children in children_by_parent.values():
        children.sort(key=lambda item: (item.order_index, item.title, item.id))

    def build(parent_id: str | None) -> list[dict[str, Any]]:
        return [
            {
                "id": node.id,
                "title": node.title,
                "level": node.level,
                "source_ref": node.source_ref,
                "children": build(node.id),
            }
            for node in children_by_parent.get(parent_id, [])
        ]

    return build(None)


def build_agent_graph_view(snapshot: GraphSnapshot) -> dict[str, Any]:
    """Return a label-rich view optimized for tutor-agent graph traversal."""

    labels = _label_by_id(snapshot)
    paths = _syllabus_paths(snapshot)
    actions_by_misconception: dict[str, list[dict[str, Any]]] = {}
    for action in snapshot.corrective_actions:
        actions_by_misconception.setdefault(action.misconception_id, []).append(
            {
                "id": action.id,
                "title": action.title,
                "action_type": action.action_type,
                "guidance": action.guidance,
                "practice_prompt": action.practice_prompt,
                "mapped_targets": [
                    {"id": target_id, "label": labels.get(target_id, target_id)}
                    for target_id in action.mapped_to_ids
                ],
                "source_refs": list(action.source_refs),
            }
        )

    return {
        "graph_version": snapshot.graph_version,
        "snapshot_id": snapshot.id,
        "hierarchy": _hierarchy(snapshot),
        "concepts": [
            {
                "id": concept.id,
                "name": concept.canonical_name,
                "aliases": list(concept.aliases),
                "definition": concept.definition,
                "syllabus_paths": [
                    list(paths[node_id])
                    for node_id in concept.syllabus_node_ids
                    if node_id in paths
                ],
                "source_refs": list(concept.source_refs),
            }
            for concept in snapshot.concepts
        ],
        "misconceptions": [
            {
                "id": misconception.id,
                "label": misconception.label,
                "description": misconception.description,
                "mapped_targets": [
                    {"id": target_id, "label": labels.get(target_id, target_id)}
                    for target_id in misconception.mapped_to_ids
                ],
                "corrective_actions": actions_by_misconception.get(misconception.id, []),
                "source_refs": list(misconception.source_refs),
            }
            for misconception in snapshot.misconceptions
        ],
        "relationships": [
            {
                "id": edge.id,
                "type": edge.relation_type,
                "from": {"id": edge.from_id, "label": labels.get(edge.from_id, edge.from_id)},
                "to": {"id": edge.to_id, "label": labels.get(edge.to_id, edge.to_id)},
                "strength": edge.strength,
                "rationale": edge.rationale,
                "source_refs": list(edge.source_refs),
            }
            for edge in snapshot.prerequisite_edges
        ],
    }
