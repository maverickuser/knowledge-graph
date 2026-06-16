"""Render question regions from two-column JEE solution PDFs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from xml.etree import ElementTree as ET

from ..domain.ids import stable_id
from ..domain.models import EvidenceArtifact, SourceDocument, make_source_document


_XHTML_NAMESPACE = {"x": "http://www.w3.org/1999/xhtml"}
_QUESTION_NUMBER_RE = re.compile(r"^(2[6-9]|[3-4]\d|50)\.$")
_VISUAL_SIGNAL_RE = re.compile(
    r"\b(shown|given)\s+(?:in|by)\s+(?:the\s+)?(?:figure|graph|diagram)|"
    r"\bfigure\b|\bgraph\b|\bcircuit\b|\barrangement\b|\btruth table\b|"
    r"\bmatch\s+(?:the\s+)?list\b|\bimage\b|\bray diagram\b",
    re.I,
)
_INVALID_XML_CHARS_RE = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]"
)


@dataclass(frozen=True, slots=True)
class QuestionRegion:
    question_no: int
    page_number: int
    page_width: float
    page_height: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float


@dataclass(frozen=True, slots=True)
class VisualCorpus:
    source_documents: tuple[SourceDocument, ...]
    evidence_artifacts: tuple[EvidenceArtifact, ...]
    evidence_by_question: dict[str, tuple[str, ...]]
    requires_visual: tuple[str, ...]
    warnings: tuple[str, ...]


_SUPPLEMENTAL_REGIONS: dict[str, tuple[int, float, float, float, float]] = {
    "JEE2026-01-21-AM-Q29": (2, 20.0, 40.0, 293.7, 205.0),
    "JEE2026-01-23-AM-Q27": (1, 297.7, 130.0, 575.3, 405.0),
    "JEE2026-01-28-PM-Q28": (1, 297.7, 130.0, 575.3, 295.0),
}


def _tool(name: str) -> str:
    executable = shutil.which(name)
    if executable is not None:
        return executable
    fallback = Path(r"C:\Program Files\MiKTeX\miktex\bin\x64") / f"{name}.exe"
    if fallback.exists():
        return str(fallback)
    raise FileNotFoundError(f"{name} was not found")


def _pdf_environment(runtime: Path) -> dict[str, str]:
    log_dir = runtime / "miktex" / "log"
    data_dir = runtime / "miktex" / "data"
    config_dir = runtime / "miktex" / "config"
    for directory in (log_dir, data_dir, config_dir):
        directory.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    for key in ("APPDATA", "LOCALAPPDATA", "USERPROFILE", "HOME", "TEMP", "TMP"):
        env[key] = str(runtime)
    env["MIKTEX_LOG_DIR"] = str(log_dir)
    env["MIKTEX_USERDATA"] = str(data_dir)
    env["MIKTEX_USERCONFIG"] = str(config_dir)
    env["MIKTEX_COMMONDATA"] = str(data_dir)
    env["MIKTEX_COMMONCONFIG"] = str(config_dir)
    return env


def _extract_bbox_html(pdf_path: Path, output_path: Path, runtime: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [_tool("pdftotext"), "-bbox-layout", str(pdf_path), str(output_path)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_pdf_environment(runtime),
    )
    if not output_path.exists():
        stderr = (completed.stderr or "").strip()
        raise RuntimeError(f"failed to extract PDF coordinates for {pdf_path}: {stderr}")


def parse_question_regions(bbox_path: str | Path) -> tuple[QuestionRegion, ...]:
    """Parse question-start coordinates into two-column crop regions."""

    raw_xml = Path(bbox_path).read_text(encoding="utf-8", errors="replace")
    root = ET.fromstring(_INVALID_XML_CHARS_RE.sub("", raw_xml))
    starts: list[tuple[int, int, float, float, float, float]] = []
    answer_starts: list[tuple[int, float, bool]] = []
    pages = root.findall(".//x:page", _XHTML_NAMESPACE)
    for page_number, page in enumerate(pages, start=1):
        page_width = float(page.attrib["width"])
        page_height = float(page.attrib["height"])
        for line in page.findall(".//x:line", _XHTML_NAMESPACE):
            words = line.findall("x:word", _XHTML_NAMESPACE)
            if not words:
                continue
            first_word = "".join(words[0].itertext()).strip()
            if first_word.lower() in {"ans.", "answer."}:
                answer_starts.append(
                    (
                        page_number,
                        float(line.attrib["yMin"]),
                        float(line.attrib["xMin"]) < page_width / 2,
                    )
                )
            match = _QUESTION_NUMBER_RE.match(first_word)
            if match is None:
                continue
            starts.append(
                (
                    int(match.group(1)),
                    page_number,
                    page_width,
                    page_height,
                    float(line.attrib["xMin"]),
                    float(line.attrib["yMin"]),
                )
            )

    regions: list[QuestionRegion] = []
    for question_no, page_number, page_width, page_height, x_start, y_start in starts:
        is_left = x_start < page_width / 2
        same_column_starts = [
            other_y
            for _, other_page, _, _, other_x, other_y in starts
            if other_page == page_number
            and (other_x < page_width / 2) == is_left
            and other_y > y_start
        ]
        same_column_answers = [
            answer_y
            for answer_page, answer_y, answer_is_left in answer_starts
            if answer_page == page_number
            and answer_is_left == is_left
            and answer_y > y_start
        ]
        x_min = 20.0 if is_left else page_width / 2
        x_max = page_width / 2 - 4.0 if is_left else page_width - 20.0
        y_min = max(0.0, y_start - 8.0)
        crop_boundaries = [page_height - 20.0]
        crop_boundaries.extend(y - 8.0 for y in same_column_starts)
        crop_boundaries.extend(y - 4.0 for y in same_column_answers)
        y_max = min(crop_boundaries)
        regions.append(
            QuestionRegion(
                question_no=question_no,
                page_number=page_number,
                page_width=page_width,
                page_height=page_height,
                x_min=x_min,
                y_min=y_min,
                x_max=x_max,
                y_max=max(y_min + 20.0, y_max),
            )
        )
    return tuple(regions)


def _render_region(
    pdf_path: Path,
    region: QuestionRegion,
    output_path: Path,
    runtime: Path,
    *,
    dpi: int = 180,
) -> None:
    scale = dpi / 72.0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_prefix = output_path.with_suffix("")
    completed = subprocess.run(
        [
            _tool("pdftoppm"),
            "-f",
            str(region.page_number),
            "-l",
            str(region.page_number),
            "-singlefile",
            "-png",
            "-r",
            str(dpi),
            "-x",
            str(round(region.x_min * scale)),
            "-y",
            str(round(region.y_min * scale)),
            "-W",
            str(round((region.x_max - region.x_min) * scale)),
            "-H",
            str(round((region.y_max - region.y_min) * scale)),
            str(pdf_path),
            str(output_prefix),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_pdf_environment(runtime),
    )
    rendered_path = output_prefix.with_suffix(".png")
    if not rendered_path.exists():
        stderr = (completed.stderr or "").strip()
        raise RuntimeError(f"failed to render {pdf_path} page {region.page_number}: {stderr}")
    if rendered_path != output_path:
        rendered_path.replace(output_path)


def _load_question_rows(jsonl_path: Path) -> list[dict]:
    with jsonl_path.open("r", encoding="utf-8-sig") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def extract_visual_corpus(
    source_root: str | Path,
    output_root: str | Path,
    *,
    version: str,
) -> VisualCorpus:
    """Extract a rendered question region for every usable structured PYQ."""

    root = Path(source_root).resolve()
    output_dir = Path(output_root).resolve()
    past_paper_dir = root / "PastYearPaper"
    rows = _load_question_rows(past_paper_dir / "jee_physics_knowledge_graph.jsonl")

    rows_by_pdf: dict[str, list[dict]] = {}
    for row in rows:
        rows_by_pdf.setdefault(str(row.get("source_pdf", "")), []).append(row)

    source_documents: list[SourceDocument] = []
    evidence_artifacts: list[EvidenceArtifact] = []
    evidence_by_question: dict[str, tuple[str, ...]] = {}
    requires_visual: list[str] = []
    warnings: list[str] = []
    runtime = output_dir / ".runtime"

    for pdf_name, pdf_rows in sorted(rows_by_pdf.items()):
        pdf_path = past_paper_dir / pdf_name
        if not pdf_path.exists():
            warnings.append(f"missing source PDF: {pdf_path}")
            continue

        source_documents.append(
            make_source_document(
                local_path=pdf_path,
                source_type="pdf",
                title=pdf_path.stem,
                version=version,
                checksum=sha256(pdf_path.read_bytes()).hexdigest(),
                source_system="past_paper_visual",
            )
        )
        bbox_path = output_dir / ".bbox" / f"{pdf_path.stem}.html"
        try:
            _extract_bbox_html(pdf_path, bbox_path, runtime)
            region_by_number = {
                region.question_no: region for region in parse_question_regions(bbox_path)
            }
        except Exception as error:
            warnings.append(str(error))
            continue

        for row in pdf_rows:
            question_id = str(row.get("question_ref", "")).strip()
            question_no = int(row.get("question_no", 0))
            question_text = str(row.get("question_text", ""))
            if len(question_text.strip()) < 40:
                continue
            region = region_by_number.get(question_no)
            if region is None:
                warnings.append(f"{question_id}: question region was not found in {pdf_name}")
                continue

            image_path = output_dir / str(row["paper_ref"]) / f"{question_id}.png"
            try:
                if not image_path.exists():
                    _render_region(pdf_path, region, image_path, runtime)
            except Exception as error:
                warnings.append(f"{question_id}: {error}")
                continue
            image_checksum = sha256(image_path.read_bytes()).hexdigest()
            visual_required = bool(_VISUAL_SIGNAL_RE.search(question_text))
            if visual_required:
                requires_visual.append(question_id)
            evidence_id = stable_id("visual", question_id, image_checksum, version)
            evidence_artifacts.append(
                EvidenceArtifact(
                    id=evidence_id,
                    artifact_type="question_visual",
                    locator=(
                        f"{image_path}#source={pdf_name}&page={region.page_number}"
                        f"&bbox={region.x_min:.1f},{region.y_min:.1f},"
                        f"{region.x_max:.1f},{region.y_max:.1f}"
                    ),
                    excerpt=(
                        f"Rendered question region for {question_id}; "
                        f"requires_visual_interpretation={str(visual_required).lower()}; "
                        f"sha256={image_checksum}"
                    ),
                    source_system="past_paper_visual",
                    version=version,
                    timestamp=datetime.now(tz=timezone.utc).isoformat(),
                )
            )
            evidence_refs = [evidence_id]
            supplemental = _SUPPLEMENTAL_REGIONS.get(question_id)
            if supplemental is not None:
                page_number, x_min, y_min, x_max, y_max = supplemental
                supplemental_region = QuestionRegion(
                    question_no=question_no,
                    page_number=page_number,
                    page_width=595.3,
                    page_height=841.9,
                    x_min=x_min,
                    y_min=y_min,
                    x_max=x_max,
                    y_max=y_max,
                )
                supplemental_path = (
                    output_dir
                    / str(row["paper_ref"])
                    / f"{question_id}-supplemental.png"
                )
                if not supplemental_path.exists():
                    _render_region(
                        pdf_path,
                        supplemental_region,
                        supplemental_path,
                        runtime,
                    )
                supplemental_checksum = sha256(
                    supplemental_path.read_bytes()
                ).hexdigest()
                supplemental_id = stable_id(
                    "visual",
                    question_id,
                    "supplemental",
                    supplemental_checksum,
                    version,
                )
                evidence_artifacts.append(
                    EvidenceArtifact(
                        id=supplemental_id,
                        artifact_type="question_visual",
                        locator=(
                            f"{supplemental_path}#source={pdf_name}"
                            f"&page={page_number}&bbox={x_min:.1f},{y_min:.1f},"
                            f"{x_max:.1f},{y_max:.1f}"
                        ),
                        excerpt=(
                            f"Supplemental visual region for {question_id}; "
                            f"sha256={supplemental_checksum}"
                        ),
                        source_system="past_paper_visual",
                        version=version,
                        timestamp=datetime.now(tz=timezone.utc).isoformat(),
                    )
                )
                evidence_refs.append(supplemental_id)
            evidence_by_question[question_id] = tuple(evidence_refs)

    return VisualCorpus(
        source_documents=tuple(source_documents),
        evidence_artifacts=tuple(evidence_artifacts),
        evidence_by_question=evidence_by_question,
        requires_visual=tuple(sorted(requires_visual)),
        warnings=tuple(warnings),
    )
