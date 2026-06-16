"""Deterministic document normalization and segmentation."""

from __future__ import annotations

from dataclasses import dataclass
import re

from ..domain.ids import normalize_text, stable_id
from ..domain.models import DocumentSection, NormalizedDocument, SourceDocument, make_document_section, make_normalized_document


_MARKDOWN_HEADING_RE = re.compile(r"^(?P<marks>#+)\s+(?P<title>.+)$")
_NUMERIC_HEADING_RE = re.compile(r"^(?P<number>\d+(?:\.\d+)*)\s+(?P<title>.+)$")


@dataclass(frozen=True, slots=True)
class Heading:
    level: int
    title: str


def _clean_lines(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    cleaned: list[str] = []
    previous_blank = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if not previous_blank:
                cleaned.append("")
            previous_blank = True
            continue
        cleaned.append(stripped)
        previous_blank = False
    return cleaned


def _detect_heading(line: str) -> Heading | None:
    markdown_match = _MARKDOWN_HEADING_RE.match(line)
    if markdown_match:
        return Heading(level=len(markdown_match.group("marks")), title=markdown_match.group("title").strip())

    numeric_match = _NUMERIC_HEADING_RE.match(line)
    if numeric_match:
        level = numeric_match.group("number").count(".") + 1
        return Heading(level=level, title=numeric_match.group("title").strip())

    return None


def split_into_sections(source_id: str, text: str) -> tuple[DocumentSection, ...]:
    """Split normalized text into deterministic structural sections."""

    lines = _clean_lines(text)
    sections: list[DocumentSection] = []
    stack: list[str] = []
    current_title = "document"
    current_path: tuple[str, ...] = ("document",)
    current_start = 1
    buffer: list[str] = []

    def flush(end_line: int) -> None:
        if not buffer:
            return
        body = "\n".join(buffer).strip()
        if not body:
            return
        section = make_document_section(
            source_id=source_id,
            title=current_title,
            path=current_path,
            start_line=current_start,
            end_line=max(current_start, end_line),
            text=body,
        )
        sections.append(section)

    for index, line in enumerate(lines, start=1):
        heading = _detect_heading(line)
        if heading is not None:
            if buffer or not sections:
                flush(index - 1)
            stack = stack[: max(heading.level - 1, 0)]
            stack.append(heading.title)
            current_title = heading.title
            current_path = tuple(stack)
            current_start = index + 1
            buffer = []
            continue

        buffer.append(line)

    flush(len(lines))

    if not sections:
        sections.append(
            make_document_section(
                source_id=source_id,
                title="document",
                path=("document",),
                start_line=1,
                end_line=max(1, len(lines)),
                text="\n".join(lines).strip(),
            )
        )

    return tuple(sections)


def normalize_source_document(
    source_document: SourceDocument,
    raw_text: str,
    *,
    version: str,
) -> NormalizedDocument:
    """Normalize a source document into stable text and sections."""

    normalized_text = normalize_text("\n".join(_clean_lines(raw_text)))
    sections = split_into_sections(source_document.id, raw_text)
    return make_normalized_document(
        source_id=source_document.id,
        normalized_text=normalized_text,
        sections=sections,
        version=version,
    )
