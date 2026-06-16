"""Compact evidence extraction from local Physics reference books."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

from ..domain.ids import normalize_text, stable_id
from ..domain.models import (
    DocumentSection,
    EvidenceArtifact,
    NormalizedDocument,
    SourceDocument,
    make_normalized_document,
    make_source_document,
)
from .loaders import read_source_text


SOURCE_AUTHORITY_WEIGHTS = {
    "hc_verma": 1.0,
    "jee_syllabus": 0.95,
    "past_paper": 0.9,
    "ncert": 0.8,
}

_TOPIC_TERMS: dict[str, tuple[str, ...]] = {
    "Units and Measurements": ("units and measurement", "dimensional analysis"),
    "Kinematics": ("kinematics", "motion in a straight line"),
    "Laws of Motion": ("newton's laws of motion", "laws of motion"),
    "Work, Energy and Power": ("work and energy", "work, energy and power"),
    "Rotational Mechanics": ("rotational mechanics", "rotational motion", "moment of inertia"),
    "Gravitation": ("gravitation", "gravitational field"),
    "Properties of Matter": ("properties of matter", "fluid mechanics", "surface tension"),
    "Thermal Properties of Matter": ("thermal properties", "heat and temperature"),
    "Thermodynamics": ("thermodynamics",),
    "Kinetic Theory": ("kinetic theory", "kinetic theory of gases"),
    "Oscillations": ("simple harmonic motion", "oscillations"),
    "Waves": ("wave motion", "waves"),
    "Electrostatics": ("electric field", "electrostatic potential", "coulomb's law"),
    "Current Electricity": ("current electricity", "electric current"),
    "Moving Charges and Magnetism": ("magnetic field", "moving charges and magnetism"),
    "Magnetism and Matter": ("magnetism and matter", "magnetic properties"),
    "Electromagnetic Induction": ("electromagnetic induction",),
    "Alternating Current": ("alternating current",),
    "Electromagnetic Waves": ("electromagnetic waves",),
    "Ray Optics": ("ray optics", "geometrical optics", "optical instruments"),
    "Wave Optics": ("wave optics", "interference of light"),
    "Dual Nature of Matter": ("dual nature", "photoelectric effect"),
    "Atoms and Nuclei": ("atomic physics", "nuclear physics", "atoms and nuclei"),
    "Semiconductor Electronics": ("semiconductor", "electronics"),
}

_HCV_VOLUME_TOPICS = {
    "volume_1": {
        "Units and Measurements",
        "Kinematics",
        "Laws of Motion",
        "Work, Energy and Power",
        "Rotational Mechanics",
        "Gravitation",
        "Properties of Matter",
        "Oscillations",
        "Waves",
        "Ray Optics",
        "Wave Optics",
    },
    "volume_2": {
        "Thermal Properties of Matter",
        "Thermodynamics",
        "Kinetic Theory",
        "Electrostatics",
        "Current Electricity",
        "Moving Charges and Magnetism",
        "Magnetism and Matter",
        "Electromagnetic Induction",
        "Alternating Current",
        "Electromagnetic Waves",
        "Dual Nature of Matter",
        "Atoms and Nuclei",
        "Semiconductor Electronics",
    },
}


@dataclass(frozen=True, slots=True)
class ReferenceCorpus:
    source_documents: tuple[SourceDocument, ...]
    normalized_documents: tuple[NormalizedDocument, ...]
    evidence_by_topic: dict[str, tuple[EvidenceArtifact, ...]]
    syllabus_source_id: str | None
    warnings: tuple[str, ...]


def _source_system(path: Path) -> str:
    path_text = str(path).lower()
    if "hcverma" in path_text:
        return "hc_verma"
    if "ncert" in path_text:
        return "ncert"
    if "syllabus" in path_text:
        return "jee_syllabus"
    return "local"


def _source_document(path: Path, source_system: str, version: str) -> SourceDocument:
    return make_source_document(
        local_path=path,
        source_type="pdf",
        title=path.stem,
        version=version,
        checksum=sha256(path.read_bytes()).hexdigest(),
        source_system=source_system,
    )


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _find_excerpt(text: str, terms: tuple[str, ...], limit: int = 700) -> str | None:
    compact = _compact_text(text)
    lowered = compact.lower()
    positions = [lowered.find(term.lower()) for term in terms]
    positions = [position for position in positions if position >= 0]
    if not positions:
        return None
    start = max(0, min(positions) - 120)
    return compact[start : start + limit].strip()


def _make_reference_artifacts(
    source: SourceDocument,
    topic: str,
    excerpt: str,
    source_system: str,
    version: str,
) -> tuple[NormalizedDocument, EvidenceArtifact]:
    section = DocumentSection(
        id=stable_id("section", source.id, topic),
        source_id=source.id,
        title=topic,
        path=(source.title, topic),
        start_line=1,
        end_line=max(1, excerpt.count("\n") + 1),
        text=excerpt,
    )
    normalized = make_normalized_document(
        source_id=source.id,
        normalized_text=normalize_text(excerpt),
        sections=(section,),
        version=version,
    )
    evidence = EvidenceArtifact(
        id=stable_id("evidence", source_system, source.id, topic),
        artifact_type="reference_support",
        locator=f"{Path(source.local_path).name}::{topic}",
        excerpt=excerpt,
        source_system=source_system,
        version=version,
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
    )
    return normalized, evidence


def _ncert_topic(text: str) -> str | None:
    prefix = _compact_text(text[:12000]).lower()
    matches: list[tuple[int, str]] = []
    for topic, terms in _TOPIC_TERMS.items():
        for term in terms:
            position = prefix.find(term.lower())
            if position >= 0:
                matches.append((position, topic))
    return min(matches)[1] if matches else None


def load_reference_corpus(source_root: str | Path, *, version: str) -> ReferenceCorpus:
    root = Path(source_root).resolve()
    hcv_paths = sorted((root / "RefrenceBook_HCVERMA").glob("*.pdf"))
    ncert_paths = sorted(
        path
        for path in (root / "RefrenceBook_NCERT").glob("*.pdf")
        if re.fullmatch(r"[kl]eph\d{3}\.pdf", path.name.lower())
    )
    syllabus_paths = sorted((root / "syllabus").glob("*.pdf"))

    source_documents: list[SourceDocument] = []
    normalized_documents: list[NormalizedDocument] = []
    evidence_by_topic: dict[str, list[EvidenceArtifact]] = {
        topic: [] for topic in _TOPIC_TERMS
    }
    warnings: list[str] = []
    syllabus_source_id: str | None = None

    for path in syllabus_paths:
        source = _source_document(path, "jee_syllabus", version)
        source_documents.append(source)
        syllabus_source_id = source.id
        text = read_source_text(path)
        if len(text.strip()) < 40:
            warnings.append(
                f"{path}: registered by checksum but no syllabus text could be extracted"
            )

    for path in hcv_paths:
        source = _source_document(path, "hc_verma", version)
        source_documents.append(source)
        text = read_source_text(path)
        volume_key = "volume_1" if "volume_1" in path.stem.lower() else "volume_2"
        for topic in sorted(_HCV_VOLUME_TOPICS[volume_key]):
            terms = _TOPIC_TERMS[topic]
            excerpt = _find_excerpt(text, terms)
            if excerpt is None:
                continue
            normalized, evidence = _make_reference_artifacts(
                source, topic, excerpt, "hc_verma", version
            )
            normalized_documents.append(normalized)
            evidence_by_topic[topic].append(evidence)

    for path in ncert_paths:
        source = _source_document(path, "ncert", version)
        source_documents.append(source)
        text = read_source_text(path)
        topic = _ncert_topic(text)
        if topic is None:
            warnings.append(f"{path}: NCERT chapter topic could not be classified")
            continue
        excerpt = _find_excerpt(text, _TOPIC_TERMS[topic]) or _compact_text(text[:700])
        normalized, evidence = _make_reference_artifacts(
            source, topic, excerpt, "ncert", version
        )
        normalized_documents.append(normalized)
        evidence_by_topic[topic].append(evidence)

    return ReferenceCorpus(
        source_documents=tuple(source_documents),
        normalized_documents=tuple(normalized_documents),
        evidence_by_topic={
            topic: tuple(
                sorted(
                    evidence,
                    key=lambda item: (
                        -SOURCE_AUTHORITY_WEIGHTS.get(item.source_system, 0.0),
                        item.locator,
                    ),
                )
            )
            for topic, evidence in evidence_by_topic.items()
        },
        syllabus_source_id=syllabus_source_id,
        warnings=tuple(warnings),
    )
