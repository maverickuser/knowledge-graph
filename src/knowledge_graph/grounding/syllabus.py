"""Deterministic syllabus grounding for anti-hallucination checks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

from ..domain.models import GraphSnapshot, SyllabusNode


LEVEL_ORDER = ("subject", "chapter", "topic", "concept", "subconcept", "microconcept")
GROUNDING_LEVELS = {"chapter", "topic", "concept", "subconcept", "microconcept"}
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_LEVEL_WEIGHT = {
    "chapter": 1.0,
    "topic": 2.0,
    "concept": 3.0,
    "subconcept": 4.0,
    "microconcept": 5.0,
}


def _phrase(value: str) -> str:
    return " ".join(_TOKEN_RE.findall(value.lower()))


def _contains_phrase(text: str, term: str) -> bool:
    if not term:
        return False
    return f" {term} " in f" {text} "


def _path_nodes(snapshot: GraphSnapshot) -> dict[str, tuple[SyllabusNode, ...]]:
    node_by_id = {node.id: node for node in snapshot.syllabus_nodes}
    paths: dict[str, tuple[SyllabusNode, ...]] = {}

    def path_for(node_id: str) -> tuple[SyllabusNode, ...]:
        if node_id in paths:
            return paths[node_id]
        node = node_by_id[node_id]
        if node.parent_id and node.parent_id in node_by_id:
            value = path_for(node.parent_id) + (node,)
        else:
            value = (node,)
        paths[node_id] = value
        return value

    for node in snapshot.syllabus_nodes:
        path_for(node.id)
    return paths


def _path_payload(path: tuple[SyllabusNode, ...]) -> list[dict[str, str]]:
    return [
        {
            "id": node.id,
            "level": node.level,
            "title": node.title,
        }
        for node in path
    ]


def _term_entry(
    *,
    term: str,
    source: str,
    node: SyllabusNode,
    path: tuple[SyllabusNode, ...],
) -> dict[str, Any] | None:
    normalized = _phrase(term)
    if len(normalized) < 4:
        return None
    return {
        "term": normalized,
        "source": source,
        "node_id": node.id,
        "level": node.level,
        "title": node.title,
        "path": _path_payload(path),
    }


def build_syllabus_term_index(snapshot: GraphSnapshot) -> list[dict[str, Any]]:
    """Build exact-match terms that are allowed to ground LLM syllabus claims."""

    paths = _path_nodes(snapshot)
    node_by_id = {node.id: node for node in snapshot.syllabus_nodes}
    entries: dict[tuple[str, str], dict[str, Any]] = {}

    for node in snapshot.syllabus_nodes:
        if node.level not in GROUNDING_LEVELS:
            continue
        entry = _term_entry(
            term=node.title,
            source="syllabus_node",
            node=node,
            path=paths[node.id],
        )
        if entry is not None:
            entries[(entry["term"], node.id)] = entry

    for concept in snapshot.concepts:
        for node_id in concept.syllabus_node_ids:
            node = node_by_id.get(node_id)
            if node is None or node.level not in GROUNDING_LEVELS:
                continue
            for term in (concept.canonical_name, *concept.aliases):
                entry = _term_entry(
                    term=term,
                    source="concept_alias",
                    node=node,
                    path=paths[node.id],
                )
                if entry is not None:
                    entries[(entry["term"], node.id)] = entry

    return sorted(
        entries.values(),
        key=lambda item: (
            item["path"][1]["title"] if len(item["path"]) > 1 else "",
            LEVEL_ORDER.index(item["level"]),
            item["title"],
            item["term"],
        ),
    )


def ground_question_to_syllabus(
    snapshot: GraphSnapshot,
    question_text: str,
    *,
    max_results: int = 8,
) -> dict[str, Any]:
    """Map a question to graph syllabus paths using known exact terms only."""

    normalized_question = _phrase(question_text)
    if not normalized_question:
        return {
            "is_grounded": False,
            "matches": [],
            "abstention_reason": "empty_question",
        }

    by_node: dict[str, dict[str, Any]] = {}
    for entry in build_syllabus_term_index(snapshot):
        term = entry["term"]
        if not _contains_phrase(normalized_question, term):
            continue
        node_id = entry["node_id"]
        match = by_node.setdefault(
            node_id,
            {
                "node_id": node_id,
                "level": entry["level"],
                "title": entry["title"],
                "path": entry["path"],
                "matched_terms": [],
                "score": 0.0,
            },
        )
        if term not in {item["term"] for item in match["matched_terms"]}:
            match["matched_terms"].append(
                {
                    "term": term,
                    "source": entry["source"],
                }
            )
            match["score"] += _LEVEL_WEIGHT.get(entry["level"], 0.0) + min(len(term) / 30.0, 1.0)

    matches = sorted(
        by_node.values(),
        key=lambda item: (
            -item["score"],
            -LEVEL_ORDER.index(item["level"]),
            item["title"],
            item["node_id"],
        ),
    )[:max_results]

    return {
        "is_grounded": bool(matches),
        "matches": matches,
        "abstention_reason": None if matches else "no_known_syllabus_terms",
    }


def _provided_path(path: Mapping[str, str] | Sequence[str]) -> dict[str, str]:
    if isinstance(path, Mapping):
        return {
            level: title
            for level, title in path.items()
            if level in LEVEL_ORDER and str(title).strip()
        }
    return {
        level: title
        for level, title in zip(LEVEL_ORDER, path, strict=False)
        if str(title).strip()
    }


def verify_syllabus_path(
    snapshot: GraphSnapshot,
    path: Mapping[str, str] | Sequence[str],
) -> dict[str, Any]:
    """Verify an LLM-proposed syllabus path against the graph hierarchy."""

    provided = _provided_path(path)
    if not provided:
        return {
            "is_verified": False,
            "matched_path": [],
            "missing_levels": list(LEVEL_ORDER),
            "reason": "empty_path",
        }

    normalized = {level: _phrase(title) for level, title in provided.items()}
    deepest_level = max(normalized, key=lambda level: LEVEL_ORDER.index(level))
    candidates: list[tuple[SyllabusNode, ...]] = []
    for node_path in _path_nodes(snapshot).values():
        path_by_level = {node.level: _phrase(node.title) for node in node_path}
        if path_by_level.get(deepest_level) != normalized[deepest_level]:
            continue
        if all(path_by_level.get(level) == title for level, title in normalized.items()):
            candidates.append(node_path)

    if not candidates:
        return {
            "is_verified": False,
            "matched_path": [],
            "missing_levels": [
                level
                for level in provided
                if normalized[level]
            ],
            "reason": "path_not_found_in_graph",
        }

    best = max(candidates, key=len)
    best_levels = {node.level for node in best}
    return {
        "is_verified": True,
        "matched_path": _path_payload(best),
        "missing_levels": [
            level
            for level in LEVEL_ORDER
            if level not in best_levels
        ],
        "reason": None,
    }
