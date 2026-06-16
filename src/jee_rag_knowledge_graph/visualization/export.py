"""Export graph snapshots as lightweight visual artifacts."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..domain.models import Community, CommunitySummary, Concept, GraphSnapshot


@dataclass(frozen=True, slots=True)
class VisualNode:
    id: str
    label: str
    theme: str
    level: str
    depth: int
    x: float
    y: float
    width: float
    height: float
    concept_count: int
    skill_count: int
    misconception_count: int
    member_count: int
    summary: str


@dataclass(frozen=True, slots=True)
class VisualEdge:
    source: str
    target: str
    kind: str
    label: str
    strength: float
    count: int


@dataclass(frozen=True, slots=True)
class ConceptView:
    id: str
    name: str
    aliases: tuple[str, ...]
    definition: str
    community_id: str | None
    community_theme: str | None
    source_refs: tuple[str, ...]
    incoming_relations: tuple[str, ...]
    outgoing_relations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MatrixCell:
    source_id: str
    target_id: str
    count: int
    strength: float


@dataclass(frozen=True, slots=True)
class GraphVisualization:
    title: str
    subtitle: str
    width: int
    height: int
    nodes: tuple[VisualNode, ...]
    edges: tuple[VisualEdge, ...]
    concepts: tuple[ConceptView, ...]
    matrix_cells: tuple[MatrixCell, ...]
    summary: dict[str, Any]


def _truncate(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 3)].rstrip() + "..."


def _community_statistics(snapshot: GraphSnapshot) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    concept_index = {concept.id: concept for concept in snapshot.concepts}
    skill_index = {skill.id: skill for skill in snapshot.skills}
    misconception_index = {misconception.id: misconception for misconception in snapshot.misconceptions}

    concept_counts: dict[str, int] = defaultdict(int)
    skill_counts: dict[str, int] = defaultdict(int)
    misconception_counts: dict[str, int] = defaultdict(int)

    for community in snapshot.communities:
        member_ids = set(community.member_ids)
        concept_counts[community.id] = sum(item_id in concept_index for item_id in member_ids)
        skill_counts[community.id] = sum(item_id in skill_index for item_id in member_ids)
        misconception_counts[community.id] = sum(item_id in misconception_index for item_id in member_ids)

    return concept_counts, skill_counts, misconception_counts


def _community_summaries(snapshot: GraphSnapshot) -> dict[str, CommunitySummary]:
    return {summary.community_id: summary for summary in snapshot.community_summaries}


def _community_depths(communities: tuple[Community, ...]) -> dict[str, int]:
    by_id = {community.id: community for community in communities}
    depths: dict[str, int] = {}

    def depth(community_id: str) -> int:
        if community_id in depths:
            return depths[community_id]
        community = by_id[community_id]
        if community.parent_id is None or community.parent_id not in by_id:
            value = 0
        else:
            value = depth(community.parent_id) + 1
        depths[community_id] = value
        return value

    for community in communities:
        depth(community.id)
    return depths


def _best_community_id(
    member_id: str,
    community_memberships: dict[str, list[str]],
    depths: dict[str, int],
) -> str | None:
    memberships = community_memberships.get(member_id, [])
    if not memberships:
        return None
    return max(memberships, key=lambda community_id: (depths.get(community_id, 0), community_id))


def _preview_relations(labels: list[str], limit: int = 6) -> tuple[str, ...]:
    if not labels:
        return ()
    ordered = sorted(dict.fromkeys(labels))
    if len(ordered) <= limit:
        return tuple(ordered)
    return tuple(ordered[: limit - 1] + ["..."])


def build_graph_visualization(snapshot: GraphSnapshot) -> GraphVisualization:
    """Build a layered community visualization for a graph snapshot."""

    if not snapshot.communities:
        raise ValueError("snapshot does not contain communities")

    summaries = _community_summaries(snapshot)
    concept_counts, skill_counts, misconception_counts = _community_statistics(snapshot)
    depths = _community_depths(snapshot.communities)
    concept_index = {concept.id: concept for concept in snapshot.concepts}
    skill_index = {skill.id: skill for skill in snapshot.skills}
    entity_name_by_id = {concept.id: concept.canonical_name for concept in snapshot.concepts}
    entity_name_by_id.update({skill.id: skill.canonical_name for skill in snapshot.skills})
    community_memberships: dict[str, list[str]] = defaultdict(list)
    for community in snapshot.communities:
        for member_id in community.member_ids:
            community_memberships[member_id].append(community.id)
    levels: dict[int, list[Community]] = defaultdict(list)
    for community in snapshot.communities:
        levels[depths[community.id]].append(community)
    for level_items in levels.values():
        level_items.sort(key=lambda item: (item.theme.lower(), item.id))

    node_width = 240
    node_height = 88
    x_gap = 290
    y_gap = 165
    margin_x = 80
    margin_y = 120
    max_per_level = max(len(items) for items in levels.values())
    width = max(1280, int(margin_x * 2 + (max_per_level - 1) * x_gap + node_width))
    height = int(margin_y * 2 + (max(depths.values()) * y_gap) + node_height)

    nodes: list[VisualNode] = []
    node_by_id: dict[str, VisualNode] = {}
    for depth, level_items in sorted(levels.items()):
        span = (len(level_items) - 1) * x_gap
        start_x = (width - span) / 2
        for index, community in enumerate(level_items):
            x = start_x + index * x_gap
            y = margin_y + depth * y_gap
            summary = summaries.get(community.id)
            summary_text = summary.summary_text if summary else ""
            node = VisualNode(
                id=community.id,
                label=_truncate(community.theme, 32),
                theme=community.theme,
                level=community.level,
                depth=depth,
                x=x,
                y=y,
                width=node_width,
                height=node_height,
                concept_count=concept_counts[community.id],
                skill_count=skill_counts[community.id],
                misconception_count=misconception_counts[community.id],
                member_count=len(community.member_ids),
                summary=_truncate(summary_text, 140),
            )
            nodes.append(node)
            node_by_id[node.id] = node

    community_by_member: dict[str, str] = {}
    for member_id in sorted(community_memberships):
        best_id = _best_community_id(member_id, community_memberships, depths)
        if best_id is not None:
            community_by_member[member_id] = best_id

    concept_views: list[ConceptView] = []
    for concept in sorted(snapshot.concepts, key=lambda item: (item.canonical_name.lower(), item.id)):
        best_community_id = _best_community_id(concept.id, community_memberships, depths)
        best_community_theme = next(
            (community.theme for community in snapshot.communities if community.id == best_community_id),
            None,
        )
        incoming_relations = [
            entity_name_by_id.get(edge.from_id, edge.from_id)
            for edge in snapshot.prerequisite_edges
            if edge.to_id == concept.id
        ]
        outgoing_relations = [
            entity_name_by_id.get(edge.to_id, edge.to_id)
            for edge in snapshot.prerequisite_edges
            if edge.from_id == concept.id
        ]
        concept_views.append(
            ConceptView(
                id=concept.id,
                name=concept.canonical_name,
                aliases=concept.aliases,
                definition=concept.definition,
                community_id=best_community_id,
                community_theme=best_community_theme,
                source_refs=concept.source_refs,
                incoming_relations=_preview_relations(incoming_relations),
                outgoing_relations=_preview_relations(outgoing_relations),
            )
        )

    parent_edges = {
        (community.parent_id, community.id)
        for community in snapshot.communities
        if community.parent_id and community.parent_id in node_by_id
    }
    prerequisite_edge_stats: dict[tuple[str, str], dict[str, float]] = {}
    for edge in snapshot.prerequisite_edges:
        source_community = community_by_member.get(edge.from_id)
        target_community = community_by_member.get(edge.to_id)
        if (
            source_community is None
            or target_community is None
            or source_community == target_community
        ):
            continue
        stats = prerequisite_edge_stats.setdefault(
            (source_community, target_community),
            {"count": 0.0, "strength": 0.0},
        )
        stats["count"] += 1.0
        stats["strength"] += edge.strength

    matrix_cells = tuple(
        MatrixCell(
            source_id=source_id,
            target_id=target_id,
            count=int(stats["count"]),
            strength=stats["strength"] / max(stats["count"], 1.0),
        )
        for (source_id, target_id), stats in sorted(
            prerequisite_edge_stats.items(),
            key=lambda item: (-item[1]["strength"], -item[1]["count"], item[0][0], item[0][1]),
        )
    )

    edges: list[VisualEdge] = []
    for parent_id, child_id in sorted(parent_edges):
        parent = node_by_id[parent_id]
        child = node_by_id[child_id]
        edges.append(
            VisualEdge(
                source=parent.id,
                target=child.id,
                kind="hierarchy",
                label="parent",
                strength=1.0,
                count=1,
            )
        )

    for (source_id, target_id), stats in sorted(
        prerequisite_edge_stats.items(),
        key=lambda item: (-item[1]["strength"], -item[1]["count"], item[0][0], item[0][1]),
    ):
        edges.append(
            VisualEdge(
                source=source_id,
                target=target_id,
                kind="prerequisite",
                label=f"{int(stats['count'])} prerequisite{'s' if stats['count'] != 1 else ''}",
                strength=stats["strength"] / max(stats["count"], 1.0),
                count=int(stats["count"]),
            )
        )

    title = f"{snapshot.graph_version} knowledge graph"
    subtitle = (
        f"{len(snapshot.communities)} communities, {len(snapshot.concepts)} concepts, "
        f"{len(snapshot.skills)} skills, {len(snapshot.prerequisite_edges)} prerequisite edges"
    )
    summary = {
        "graph_version": snapshot.graph_version,
        "snapshot_id": snapshot.id,
        "community_count": len(snapshot.communities),
        "concept_count": len(snapshot.concepts),
        "skill_count": len(snapshot.skills),
        "prerequisite_edge_count": len(snapshot.prerequisite_edges),
        "cross_community_prerequisite_count": len(matrix_cells),
    }
    return GraphVisualization(
        title=title,
        subtitle=subtitle,
        width=width,
        height=height,
        nodes=tuple(nodes),
        edges=tuple(edges),
        concepts=tuple(concept_views),
        matrix_cells=matrix_cells,
        summary=summary,
    )


def render_graph_svg(visualization: GraphVisualization) -> str:
    node_index = {node.id: node for node in visualization.nodes}
    buffer: list[str] = []
    buffer.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {visualization.width} {visualization.height}" '
        'role="img" aria-labelledby="graph-title graph-desc">'
    )
    buffer.append("<defs>")
    buffer.append(
        '<marker id="arrow-prereq" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    )
    buffer.append('<path d="M 0 0 L 10 5 L 0 10 z" fill="#b45309" />')
    buffer.append("</marker>")
    buffer.append(
        '<marker id="arrow-tree" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    )
    buffer.append('<path d="M 0 0 L 10 5 L 0 10 z" fill="#374151" />')
    buffer.append("</marker>")
    buffer.append("</defs>")
    buffer.append(f'<title id="graph-title">{html.escape(visualization.title)}</title>')
    buffer.append(f'<desc id="graph-desc">{html.escape(visualization.subtitle)}</desc>')

    for edge in visualization.edges:
        source = node_index[edge.source]
        target = node_index[edge.target]
        x1 = source.x + source.width / 2
        y1 = source.y + source.height
        x2 = target.x + target.width / 2
        y2 = target.y
        if edge.kind == "hierarchy":
            stroke = "#374151"
            dash = ""
            marker = "url(#arrow-tree)"
            opacity = "0.65"
        else:
            stroke = "#b45309"
            dash = "6 5"
            marker = "url(#arrow-prereq)"
            opacity = "0.36"
        mid_y = (y1 + y2) / 2
        path = (
            f"M {x1:.1f} {y1:.1f} "
            f"C {x1:.1f} {mid_y:.1f} {x2:.1f} {mid_y:.1f} {x2:.1f} {y2:.1f}"
        )
        buffer.append(
            f'<path d="{path}" fill="none" stroke="{stroke}" stroke-width="{1.6 + min(edge.strength, 1.0) * 2:.2f}" '
            f'stroke-dasharray="{dash}" stroke-linecap="round" opacity="{opacity}" marker-end="{marker}">'
            f"<title>{html.escape(edge.label)}: {html.escape(source.theme)} -> {html.escape(target.theme)}</title>"
            "</path>"
        )

    for node in visualization.nodes:
        buffer.append(
            f'<g class="node" data-node-id="{html.escape(node.id)}" '
            f'transform="translate({node.x:.1f}, {node.y:.1f})">'
        )
        buffer.append(
            f'<rect x="0" y="0" rx="18" ry="18" width="{node.width:.1f}" height="{node.height:.1f}" '
            'fill="#f8fafc" stroke="#0f172a" stroke-width="1.6" />'
        )
        buffer.append(
            f'<rect x="1.5" y="1.5" rx="16" ry="16" width="{node.width - 3:.1f}" height="{node.height - 3:.1f}" '
            'fill="none" stroke="#cbd5e1" stroke-width="1" />'
        )
        title_y = node.height / 2 - 9
        subtitle_y = node.height / 2 + 14
        buffer.append(
            f'<text x="{node.width / 2:.1f}" y="{title_y:.1f}" text-anchor="middle" '
            'font-size="15" font-weight="700" fill="#0f172a">'
            f"<tspan x=\"{node.width / 2:.1f}\" dy=\"0\">{html.escape(node.label)}</tspan>"
            "</text>"
        )
        buffer.append(
            f'<text x="{node.width / 2:.1f}" y="{subtitle_y:.1f}" text-anchor="middle" '
            'font-size="11.5" fill="#475569">'
            f"<tspan x=\"{node.width / 2:.1f}\" dy=\"0\">{node.concept_count} concepts | {node.skill_count} skills | {node.misconception_count} misconceptions</tspan>"
            "</text>"
        )
        buffer.append(
            "<title>"
            + html.escape(
                "\n".join(
                    [
                        node.theme,
                        f"Level: {node.level}",
                        f"Members: {node.member_count}",
                        f"Concepts: {node.concept_count}",
                        f"Skills: {node.skill_count}",
                        f"Misconceptions: {node.misconception_count}",
                        node.summary or "No summary available.",
                    ]
                )
            )
            + "</title>"
        )
        buffer.append("</g>")

    buffer.append("</svg>")
    return "".join(buffer)


def render_graph_html(visualization: GraphVisualization) -> str:
    nodes_payload = [
        {
            "id": node.id,
            "theme": node.theme,
            "label": node.label,
            "level": node.level,
            "depth": node.depth,
            "concept_count": node.concept_count,
            "skill_count": node.skill_count,
            "misconception_count": node.misconception_count,
            "member_count": node.member_count,
            "summary": node.summary,
        }
        for node in visualization.nodes
    ]
    edges_payload = [
        {
            "source": edge.source,
            "target": edge.target,
            "kind": edge.kind,
            "label": edge.label,
            "strength": edge.strength,
            "count": edge.count,
        }
        for edge in visualization.edges
    ]
    concepts_payload = [
        {
            "id": concept.id,
            "name": concept.name,
            "aliases": concept.aliases,
            "definition": concept.definition,
            "community_id": concept.community_id,
            "community_theme": concept.community_theme,
            "source_refs": concept.source_refs,
            "incoming_relations": concept.incoming_relations,
            "outgoing_relations": concept.outgoing_relations,
        }
        for concept in visualization.concepts
    ]
    matrix_payload = [
        {
            "source_id": cell.source_id,
            "target_id": cell.target_id,
            "count": cell.count,
            "strength": cell.strength,
        }
        for cell in visualization.matrix_cells
    ]
    matrix_by_pair = {(cell.source_id, cell.target_id): cell for cell in visualization.matrix_cells}
    max_matrix_count = max((cell.count for cell in visualization.matrix_cells), default=0)
    svg = render_graph_svg(visualization)

    concept_cards_html = "".join(
        f"""
        <button class="concept-card" type="button" data-concept-id="{html.escape(concept.id)}">
          <div class="concept-card-title">{html.escape(concept.name)}</div>
          <div class="concept-card-subtitle">{html.escape(concept.community_theme or 'Unassigned')}</div>
          <div class="concept-card-meta">{len(concept.aliases)} aliases | {len(concept.source_refs)} refs</div>
        </button>
        """
        for concept in visualization.concepts
    )

    matrix_header_cells = "".join(
        f'<th title="{html.escape(node.theme)}">{html.escape(node.label)}</th>' for node in visualization.nodes
    )
    matrix_row_html: list[str] = []
    for row in visualization.nodes:
        row_cells: list[str] = []
        for col in visualization.nodes:
            cell = matrix_by_pair.get((row.id, col.id))
            if cell is None:
                row_cells.append('<td class="matrix-empty">&nbsp;</td>')
                continue
            alpha = 0.12 if max_matrix_count == 0 else min(0.12 + 0.62 * (cell.count / max_matrix_count), 0.82)
            row_cells.append(
                '<td class="matrix-hit" '
                f'style="background: rgba(180, 83, 9, {alpha:.3f});" '
                f'title="{html.escape(row.theme)} -> {html.escape(col.theme)} | {cell.count} edges | '
                f'avg strength {cell.strength:.2f}">'
                f'<span class="matrix-count">{cell.count}</span>'
                f'<span class="matrix-strength">{cell.strength:.2f}</span>'
                "</td>"
            )
        matrix_row_html.append(
            "<tr>"
            f'<th class="matrix-row-label" title="{html.escape(row.theme)}">{html.escape(row.label)}</th>'
            + "".join(row_cells)
            + "</tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(visualization.title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --panel: #ffffff;
      --ink: #0f172a;
      --muted: #475569;
      --accent: #b45309;
      --accent-soft: rgba(180, 83, 9, 0.12);
      --border: #cbd5e1;
    }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(180, 83, 9, 0.12), transparent 34%),
        radial-gradient(circle at bottom right, rgba(15, 23, 42, 0.07), transparent 28%),
        var(--bg);
      color: var(--ink);
    }}
    header {{
      padding: 28px 32px 8px;
    }}
    h1 {{
      margin: 0;
      font-size: 30px;
      letter-spacing: -0.03em;
    }}
    .subtitle {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 14px;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.9fr) minmax(320px, 0.8fr);
      gap: 18px;
      padding: 16px 24px 28px;
      align-items: start;
    }}
    .stack {{
      display: grid;
      gap: 18px;
      padding: 0 24px 28px;
    }}
    .panel {{
      background: rgba(255, 255, 255, 0.88);
      border: 1px solid rgba(203, 213, 225, 0.9);
      border-radius: 20px;
      box-shadow: 0 18px 55px rgba(15, 23, 42, 0.08);
      backdrop-filter: blur(8px);
    }}
    .graph-panel {{
      padding: 14px;
      overflow: auto;
    }}
    .sidebar {{
      padding: 18px;
      position: sticky;
      top: 18px;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 14px;
    }}
    .metric {{
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 12px;
      background: #fff;
    }}
    .metric .value {{
      font-size: 20px;
      font-weight: 700;
    }}
    .metric .label {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 3px;
    }}
    .details {{
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
    }}
    .details h2 {{
      font-size: 17px;
      margin: 0 0 8px;
    }}
    .details .empty {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }}
    .tag-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }}
    .tag {{
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
      font-weight: 600;
    }}
    .legend {{
      margin-top: 16px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }}
    .section-heading {{
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: baseline;
      margin-bottom: 14px;
    }}
    .section-heading h2 {{
      margin: 0;
      font-size: 20px;
      letter-spacing: -0.02em;
    }}
    .section-heading p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}
    .drilldown-layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1.25fr);
      gap: 14px;
    }}
    .concept-grid {{
      display: grid;
      gap: 10px;
      max-height: 520px;
      overflow: auto;
      padding-right: 4px;
    }}
    .concept-card {{
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: #fff;
      padding: 12px 14px;
      text-align: left;
      cursor: pointer;
      transition: transform 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
    }}
    .concept-card:hover {{
      transform: translateY(-1px);
      border-color: rgba(180, 83, 9, 0.45);
      box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
    }}
    .concept-card.active {{
      border-color: #b45309;
      background: #fff7ed;
    }}
    .concept-card-title {{
      font-size: 14px;
      font-weight: 700;
      color: var(--ink);
    }}
    .concept-card-subtitle {{
      margin-top: 4px;
      font-size: 12px;
      color: var(--muted);
    }}
    .concept-card-meta {{
      margin-top: 6px;
      font-size: 12px;
      color: #7c2d12;
    }}
    .detail-card {{
      border: 1px solid var(--border);
      border-radius: 18px;
      background: linear-gradient(180deg, #ffffff, #fffaf5);
      padding: 16px;
      min-height: 320px;
    }}
    .detail-card h3 {{
      margin: 0;
      font-size: 19px;
      letter-spacing: -0.02em;
    }}
    .detail-card .detail-subtitle {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 14px;
    }}
    .detail-metric {{
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 10px;
      background: #fff;
    }}
    .detail-metric .label {{
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .detail-metric .value {{
      margin-top: 4px;
      font-size: 13px;
      color: var(--ink);
      line-height: 1.4;
    }}
    .detail-section {{
      margin-top: 12px;
    }}
    .detail-section h4 {{
      margin: 0 0 6px;
      font-size: 13px;
      color: var(--ink);
    }}
    .detail-section p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }}
    .matrix-scroll {{
      overflow: auto;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: #fff;
    }}
    .matrix-table {{
      border-collapse: collapse;
      width: max-content;
      min-width: 100%;
    }}
    .matrix-table th,
    .matrix-table td {{
      border: 1px solid rgba(203, 213, 225, 0.85);
      padding: 8px;
      min-width: 72px;
      text-align: center;
      vertical-align: middle;
    }}
    .matrix-table thead th {{
      position: sticky;
      top: 0;
      background: #f8fafc;
      z-index: 1;
      font-size: 11px;
      color: var(--muted);
      min-width: 98px;
    }}
    .matrix-row-label {{
      position: sticky;
      left: 0;
      background: #f8fafc;
      z-index: 1;
      text-align: left;
      font-size: 11px;
      color: var(--ink);
      min-width: 140px;
      max-width: 140px;
    }}
    .matrix-hit {{
      color: #7c2d12;
      font-weight: 700;
    }}
    .matrix-empty {{
      background: #f8fafc;
    }}
    .matrix-count,
    .matrix-strength {{
      display: block;
      line-height: 1.1;
    }}
    .matrix-count {{
      font-size: 13px;
    }}
    .matrix-strength {{
      margin-top: 2px;
      font-size: 11px;
      opacity: 0.85;
    }}
    svg {{
      width: 100%;
      height: auto;
      min-width: {visualization.width}px;
    }}
    .node {{
      cursor: pointer;
      transition: transform 120ms ease, filter 120ms ease;
    }}
    .node:hover {{
      filter: drop-shadow(0 8px 14px rgba(15, 23, 42, 0.18));
    }}
    .selected rect:first-of-type {{
      fill: #fff7ed;
      stroke: #b45309;
    }}
    .selected rect:nth-of-type(2) {{
      stroke: #f59e0b;
    }}
    @media (max-width: 1100px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}
      .sidebar {{
        position: static;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(visualization.title)}</h1>
    <div class="subtitle">{html.escape(visualization.subtitle)}</div>
  </header>
  <main class="layout">
    <section class="panel graph-panel">
      {svg}
    </section>
    <aside class="panel sidebar">
      <strong>Overview</strong>
      <div class="metric-grid">
        <div class="metric"><div class="value">{len(visualization.nodes)}</div><div class="label">Communities</div></div>
        <div class="metric"><div class="value">{len([edge for edge in visualization.edges if edge.kind == "prerequisite"])}</div><div class="label">Cross-community prereqs</div></div>
        <div class="metric"><div class="value">{visualization.summary["concept_count"]}</div><div class="label">Concepts</div></div>
        <div class="metric"><div class="value">{visualization.summary["skill_count"]}</div><div class="label">Skills</div></div>
      </div>
      <div class="details">
        <h2 id="details-title">Select a community</h2>
        <div id="details-body" class="empty">Click a community node to inspect its summary, counts, and placement in the syllabus hierarchy.</div>
        <div id="details-tags" class="tag-list"></div>
      </div>
      <div class="legend">
        <strong>Legend</strong><br />
        Dark lines show syllabus parent-child structure. Orange dashed lines show prerequisite relationships aggregated across concepts and skills.
      </div>
    </aside>
  </main>
  <section class="stack">
    <section class="panel" style="padding: 18px;">
      <div class="section-heading">
        <div>
          <h2>Concept Drilldown</h2>
          <p>Inspect a concept, its owning community, and its direct prerequisite neighborhood.</p>
        </div>
      </div>
      <div class="drilldown-layout">
        <div class="concept-grid" id="concept-grid">
          {concept_cards_html}
        </div>
        <div class="detail-card">
          <h3 id="concept-title">Select a concept</h3>
          <div class="detail-subtitle" id="concept-subtitle">Click a concept card to inspect its details.</div>
          <div class="detail-grid">
            <div class="detail-metric">
              <div class="label">Community</div>
              <div class="value" id="concept-community">None</div>
            </div>
            <div class="detail-metric">
              <div class="label">Source refs</div>
              <div class="value" id="concept-source-refs">None</div>
            </div>
          </div>
          <div class="detail-section">
            <h4>Aliases</h4>
            <p id="concept-aliases">None</p>
          </div>
          <div class="detail-section">
            <h4>Definition</h4>
            <p id="concept-definition">Select a concept to read its definition.</p>
          </div>
          <div class="detail-section">
            <h4>Incoming prerequisites</h4>
            <p id="concept-incoming">None</p>
          </div>
          <div class="detail-section">
            <h4>Outgoing prerequisites</h4>
            <p id="concept-outgoing">None</p>
          </div>
        </div>
      </div>
    </section>
    <section class="panel" style="padding: 18px;">
      <div class="section-heading">
        <div>
          <h2>Community Prerequisite Matrix</h2>
          <p>Cross-community prerequisite pressure. Darker cells mean more prerequisite edges between communities.</p>
        </div>
      </div>
      <div class="matrix-scroll">
        <table class="matrix-table">
          <thead>
            <tr>
              <th></th>
              {matrix_header_cells}
            </tr>
          </thead>
          <tbody>
            {"".join(matrix_row_html)}
          </tbody>
        </table>
      </div>
    </section>
  </section>
  <script type="application/json" id="graph-data">{json.dumps({"nodes": nodes_payload, "edges": edges_payload, "concepts": concepts_payload, "matrix_cells": matrix_payload}, sort_keys=True).replace("</", "<\\/")}</script>
  <script>
    const graphData = JSON.parse(document.getElementById("graph-data").textContent);
    const nodeData = new Map(graphData.nodes.map((node) => [node.id, node]));
    const conceptData = new Map(graphData.concepts.map((concept) => [concept.id, concept]));
    const detailsTitle = document.getElementById("details-title");
    const detailsBody = document.getElementById("details-body");
    const detailsTags = document.getElementById("details-tags");
    const conceptGrid = document.getElementById("concept-grid");
    const conceptTitle = document.getElementById("concept-title");
    const conceptSubtitle = document.getElementById("concept-subtitle");
    const conceptCommunity = document.getElementById("concept-community");
    const conceptSourceRefs = document.getElementById("concept-source-refs");
    const conceptAliases = document.getElementById("concept-aliases");
    const conceptDefinition = document.getElementById("concept-definition");
    const conceptIncoming = document.getElementById("concept-incoming");
    const conceptOutgoing = document.getElementById("concept-outgoing");

    function renderDetails(node) {{
      detailsTitle.textContent = node.theme;
      detailsBody.textContent = node.summary || "No summary available.";
      detailsTags.innerHTML = "";
      [
        `Level: ${{node.level}}`,
        `Depth: ${{node.depth}}`,
        `${{node.member_count}} members`,
        `${{node.concept_count}} concepts`,
        `${{node.skill_count}} skills`,
        `${{node.misconception_count}} misconceptions`
      ].forEach((label) => {{
        const chip = document.createElement("span");
        chip.className = "tag";
        chip.textContent = label;
        detailsTags.appendChild(chip);
      }});
    }}

    function formatList(values) {{
      if (!values || values.length === 0) {{
        return "None";
      }}
      return values.join(", ");
    }}

    function selectConcept(conceptId) {{
      const concept = conceptData.get(conceptId);
      if (!concept) {{
        return;
      }}
      conceptTitle.textContent = concept.name;
      conceptSubtitle.textContent = concept.community_theme ? `Community: ${{concept.community_theme}}` : "Community: unassigned";
      conceptCommunity.textContent = concept.community_theme || "None";
      conceptSourceRefs.textContent = formatList(concept.source_refs);
      conceptAliases.textContent = formatList(concept.aliases);
      conceptDefinition.textContent = concept.definition || "No definition available.";
      conceptIncoming.textContent = formatList(concept.incoming_relations);
      conceptOutgoing.textContent = formatList(concept.outgoing_relations);

      document.querySelectorAll(".concept-card").forEach((card) => {{
        card.classList.toggle("active", card.getAttribute("data-concept-id") === conceptId);
      }});
    }}

    document.querySelectorAll(".node").forEach((group) => {{
      const nodeId = group.getAttribute("data-node-id");
      const node = nodeData.get(nodeId);
      group.addEventListener("click", () => {{
        document.querySelectorAll(".node").forEach((item) => item.classList.remove("selected"));
        group.classList.add("selected");
        renderDetails(node);
      }});
    }});

    document.querySelectorAll(".concept-card").forEach((card) => {{
      card.addEventListener("click", () => {{
        selectConcept(card.getAttribute("data-concept-id"));
      }});
    }});

    const first = graphData.nodes[0];
    if (first) {{
      renderDetails(first);
      const selected = document.querySelector(`.node[data-node-id="${{first.id}}"]`);
      if (selected) {{
        selected.classList.add("selected");
      }}
    }}
    const firstConcept = graphData.concepts?.[0];
    if (firstConcept) {{
      selectConcept(firstConcept.id);
    }}
  </script>
</body>
</html>
"""


def export_graph_visualization(
    snapshot: GraphSnapshot,
    output_dir: str | Path,
    *,
    base_name: str | None = None,
) -> dict[str, Path]:
    """Write SVG, HTML, and JSON representations to disk."""

    visualization = build_graph_visualization(snapshot)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    stem = base_name or snapshot.graph_version

    svg_path = output_path / f"{stem}.svg"
    html_path = output_path / f"{stem}.html"
    json_path = output_path / f"{stem}.json"

    svg_path.write_text(render_graph_svg(visualization), encoding="utf-8")
    html_path.write_text(render_graph_html(visualization), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "summary": visualization.summary,
                "nodes": [asdict(node) for node in visualization.nodes],
                "edges": [asdict(edge) for edge in visualization.edges],
                "concepts": [asdict(concept) for concept in visualization.concepts],
                "matrix_cells": [asdict(cell) for cell in visualization.matrix_cells],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return {"svg": svg_path, "html": html_path, "json": json_path}
