"""Corpus-to-graph seed extraction for the provided JEE Physics folder."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import re

from ..domain.ids import normalize_text, stable_id, stable_slug
from ..domain.models import (
    AssessmentItem,
    Concept,
    EvidenceArtifact,
    GraphSeedBundle,
    Misconception,
    PrerequisiteEdge,
    Skill,
    SyllabusNode,
)
from .loaders import load_local_source
from .normalize import normalize_source_document
from .physics_syllabus import PHYSICS_SYLLABUS
from .reference_corpus import SOURCE_AUTHORITY_WEIGHTS, load_reference_corpus


SUPPORTED_SOURCE_SUFFIXES = {
    ".csv",
    ".docx",
    ".htm",
    ".html",
    ".json",
    ".jsonl",
    ".md",
    ".markdown",
    ".pdf",
    ".rst",
    ".txt",
}


@dataclass(frozen=True, slots=True)
class PhysicsQuestionRecord:
    question_id: str
    paper_ref: str
    paper_title: str
    topic: str
    question_text: str
    solution_text: str
    pitfalls: tuple[str, ...]
    final_answer: str
    source_path: str


@dataclass(frozen=True, slots=True)
class PhysicsCorpusBundle:
    source_documents: tuple
    normalized_documents: tuple
    question_records: tuple[PhysicsQuestionRecord, ...]
    skipped_sources: tuple[str, ...] = ()
    reference_warnings: tuple[str, ...] = ()
    source_authority_weights: tuple[tuple[str, float], ...] = ()


_QUESTION_SECTION_RE = re.compile(
    r"^###\s+Question ID:\s*(?P<question_id>.+?)\n(?P<body>.*?)(?=^###\s+Question ID:|\Z)",
    re.M | re.S,
)

_LINE_FIELD_RE = re.compile(r"^\*\*(?P<label>[^*]+):\*\*\s*(?P<value>.+?)\s*$", re.M)

_SKILL_RULES: tuple[tuple[re.Pattern[str], str, tuple[str, ...]], ...] = (
    (re.compile(r"parallel-axis theorem", re.I), "apply parallel-axis theorem", ("parallel-axis theorem",)),
    (re.compile(r"mechanical energy conservation|energy conservation", re.I), "apply energy conservation", ("energy conservation",)),
    (re.compile(r"meter bridge|wheatstone", re.I), "use bridge balance relation", ("bridge balance", "wheatstone bridge")),
    (re.compile(r"projectile", re.I), "resolve projectile motion components", ("projectile components",)),
    (re.compile(r"lens|mirror", re.I), "apply the lens formula", ("lens formula", "sign convention")),
    (re.compile(r"prism|refraction|snell", re.I), "apply Snell's law", ("snell's law", "refraction")),
    (re.compile(r"therm|adiabatic|gas", re.I), "apply thermodynamics relations", ("adiabatic relation", "thermodynamics")),
    (re.compile(r"induction|magnetic", re.I), "apply electromagnetic induction", ("lenz's law", "magnetic flux")),
    (re.compile(r"electric field|charge", re.I), "resolve electric field vectors", ("vector components", "field superposition")),
    (re.compile(r"gravitation|escape velocity", re.I), "use gravitation scaling relations", ("inverse-square law", "escape speed")),
    (re.compile(r"fluid|pressure", re.I), "apply fluid pressure relations", ("pressure balance",)),
    (re.compile(r"resistance|circuit", re.I), "reduce circuit equivalents", ("series and parallel", "equivalent resistance")),
    (re.compile(r"dimensional", re.I), "perform dimensional analysis", ("dimensional analysis",)),
)

_TOPIC_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"moment of inertia|torque|angular momentum|rolling|rotational", re.I), "Rotational Mechanics"),
    (re.compile(r"projectile|kinematic|relative velocity|uniform acceleration|position after|coordinate is given|river .*boat|velocity .*distance|acceleration .*distance|thrown .*ball|maximum height", re.I), "Kinematics"),
    (re.compile(r"friction|newton'?s law|pulley|tension|inclined plane|force .*time|free fall|parachute", re.I), "Laws of Motion"),
    (re.compile(r"work[- ]energy|mechanical energy|potential energy|power|collision|momentum|explodes|kinetic energy|work done|conservative force", re.I), "Work, Energy and Power"),
    (re.compile(r"gravitation|escape velocity|satellite|orbital velocity", re.I), "Gravitation"),
    (re.compile(r"simple harmonic|oscillation|spring|pendulum", re.I), "Oscillations"),
    (re.compile(r"wave|sound|doppler|organ pipe|stretched string", re.I), "Waves"),
    (re.compile(r"fluid|bernoulli|viscosity|surface tension|pressure|floats|submerged|terminal velocity", re.I), "Properties of Matter"),
    (re.compile(r"calorim|heat|thermal expansion|specific heat|coefficient of linear expansion", re.I), "Thermal Properties of Matter"),
    (re.compile(r"thermodynamic|adiabatic|isothermal|ideal gas|carnot", re.I), "Thermodynamics"),
    (re.compile(r"kinetic theory|r\.?m\.?s\.? speed|mean free path", re.I), "Kinetic Theory"),
    (re.compile(r"electric field|electric potential|gauss|capacitor|charge", re.I), "Electrostatics"),
    (re.compile(r"current|resistance|resistivity|meter bridge|wheatstone|kirchhoff|potentiometer|galvanometer", re.I), "Current Electricity"),
    (re.compile(r"magnetic field|biot|ampere|cyclotron|moving charge", re.I), "Moving Charges and Magnetism"),
    (re.compile(r"magnetism|magnetic dipole|bar magnet", re.I), "Magnetism and Matter"),
    (re.compile(r"electromagnetic induction|induced emf|faraday|lenz", re.I), "Electromagnetic Induction"),
    (re.compile(r"alternating current|transformer|lcr|reactance", re.I), "Alternating Current"),
    (re.compile(r"electromagnetic wave", re.I), "Electromagnetic Waves"),
    (re.compile(r"ray optics|lens|mirror|prism|refraction|snell", re.I), "Ray Optics"),
    (re.compile(r"wave optics|interference|diffraction|young'?s", re.I), "Wave Optics"),
    (re.compile(r"photoelectric|de broglie|dual nature", re.I), "Dual Nature of Matter"),
    (re.compile(r"nucleus|nuclei|nuclear|radioactive|binding energy|alpha particle|fission", re.I), "Atoms and Nuclei"),
    (re.compile(r"semiconductor|diode|transistor|logic gate|logical circuit|truth table|led to glow|zener|circuit works as", re.I), "Semiconductor Electronics"),
    (re.compile(r"dimension|significant figure|error|vernier|screw gauge|least count|magnetic induction.*magnetic flux", re.I), "Units and Measurements"),
    (re.compile(r"hydrogen like atom|bohr|energy state|electron orbit", re.I), "Atoms and Nuclei"),
    (re.compile(r"microscope|telescope|spherical glass surface|total internal reflection|polarized|polarised|brewster", re.I), "Ray Optics"),
    (re.compile(r"double slit|young'?s|fringe|coherent", re.I), "Wave Optics"),
    (re.compile(r"photon|work function|photoelectron|laser source", re.I), "Dual Nature of Matter"),
    (re.compile(r"co-?centric conducting spherical shells|potential of the spheres", re.I), "Electrostatics"),
    (re.compile(r"point source.*intensity|intensity.*detector", re.I), "Waves"),
)

_TOPIC_PREREQUISITES: tuple[tuple[str, str], ...] = (
    ("Units and Measurements", "Kinematics"),
    ("Kinematics", "Laws of Motion"),
    ("Laws of Motion", "Work, Energy and Power"),
    ("Work, Energy and Power", "Rotational Mechanics"),
    ("Laws of Motion", "Gravitation"),
    ("Laws of Motion", "Properties of Matter"),
    ("Laws of Motion", "Oscillations"),
    ("Oscillations", "Waves"),
    ("Thermal Properties of Matter", "Thermodynamics"),
    ("Kinetic Theory", "Thermodynamics"),
    ("Electrostatics", "Current Electricity"),
    ("Current Electricity", "Moving Charges and Magnetism"),
    ("Moving Charges and Magnetism", "Magnetism and Matter"),
    ("Moving Charges and Magnetism", "Electromagnetic Induction"),
    ("Electromagnetic Induction", "Alternating Current"),
    ("Waves", "Wave Optics"),
    ("Ray Optics", "Wave Optics"),
    ("Dual Nature of Matter", "Atoms and Nuclei"),
    ("Atoms and Nuclei", "Semiconductor Electronics"),
)


def _is_supported_source(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_SOURCE_SUFFIXES


def discover_corpus_paths(source_root: str | Path) -> tuple[Path, ...]:
    root = Path(source_root).resolve()
    paths = [path for path in root.rglob("*") if _is_supported_source(path)]
    return tuple(sorted(paths, key=lambda item: str(item.relative_to(root)).lower()))


def _strip_block_wrappers(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in {"~~~", "~~~text", "```", "```text"}:
            continue
        cleaned_lines.append(line.rstrip())
    return "\n".join(cleaned_lines).strip()


def _extract_line_value(body: str, label: str, default: str = "") -> str:
    match = re.search(rf"^\*\*{re.escape(label)}\*\*\s*(?P<value>.+?)\s*$", body, re.M)
    return match.group("value").strip() if match else default


def _extract_block_value(body: str, label: str, following_labels: tuple[str, ...]) -> str:
    start_match = re.search(rf"^\*\*{re.escape(label)}\*\*\s*$", body, re.M)
    if not start_match:
        return ""

    start = start_match.end()
    end = len(body)
    for following_label in following_labels:
        following_match = re.search(rf"^\*\*{re.escape(following_label)}\*\*\s*$", body[start:], re.M)
        if following_match is not None:
            end = min(end, start + following_match.start())
    return _strip_block_wrappers(body[start:end].strip())


def _extract_pitfalls(body: str) -> tuple[str, ...]:
    raw = _extract_block_value(body, "Common Pitfalls & Misconceptions:", ("Final Answer:",))
    if not raw:
        return ()

    pitfalls: list[str] = []
    current: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                pitfalls.append(" ".join(current).strip())
                current = []
            continue
        if stripped.startswith(("-", "*")):
            if current:
                pitfalls.append(" ".join(current).strip())
            current = [stripped.lstrip("-* ").strip()]
            continue
        if current:
            current.append(stripped)
        else:
            current = [stripped]
    if current:
        pitfalls.append(" ".join(current).strip())

    return tuple(pitfall for pitfall in pitfalls if pitfall)


def _split_topic(topic: str) -> tuple[str, str | None]:
    normalized = topic.strip()
    if not normalized:
        return ("Physics", None)

    if "(" in normalized and normalized.endswith(")"):
        base, detail = normalized.split("(", 1)
        base = base.strip(" -:")
        detail = detail[:-1].strip()
        if base and detail and base.lower() != detail.lower():
            return (base, detail)

    for separator in (" - ", ": "):
        if separator in normalized:
            base, detail = normalized.split(separator, 1)
            base = base.strip()
            detail = detail.strip()
            if base and detail and base.lower() != detail.lower():
                return (base, detail)

    return (normalized, None)


def _topic_aliases(topic: str, base_topic: str, detail_topic: str | None) -> tuple[str, ...]:
    aliases = {
        normalize_text(topic),
        normalize_text(base_topic),
        stable_slug(topic).replace("-", " "),
    }
    if detail_topic:
        aliases.add(normalize_text(detail_topic))
    return tuple(sorted(alias for alias in aliases if alias))


def _infer_skill_data(topic: str, topic_text: str) -> tuple[str, tuple[str, ...]]:
    combined = f"{topic}\n{topic_text}"
    aliases: set[str] = {normalize_text(topic)}
    for pattern, canonical_name, extra_aliases in _SKILL_RULES:
        if pattern.search(combined):
            aliases.add(normalize_text(canonical_name))
            aliases.update(normalize_text(alias) for alias in extra_aliases)
            return (canonical_name, tuple(sorted(alias for alias in aliases if alias)))

    canonical_name = f"solve {topic.lower()} problems"
    aliases.add(normalize_text(canonical_name))
    return (canonical_name, tuple(sorted(alias for alias in aliases if alias)))


def _infer_misconception_patterns(pitfall: str) -> tuple[str, ...]:
    normalized = normalize_text(pitfall)
    tokens = [token for token in re.split(r"[^a-z0-9']+", normalized) if len(token) > 3]
    patterns = {normalized}
    patterns.update(tokens[:4])
    return tuple(sorted(patterns))


def _append_syllabus_node(
    syllabus_nodes: list[SyllabusNode],
    seen_node_ids: set[str],
    node: SyllabusNode,
) -> None:
    if node.id in seen_node_ids:
        return
    syllabus_nodes.append(node)
    seen_node_ids.add(node.id)


def _merge_concept(
    concepts: dict[str, Concept],
    *,
    concept_id: str,
    canonical_name: str,
    definition: str,
    source_refs: tuple[str, ...],
    aliases: tuple[str, ...],
    syllabus_node_id: str,
    graph_version: str,
) -> None:
    concept = concepts.get(concept_id)
    if concept is None:
        concepts[concept_id] = Concept(
            id=concept_id,
            canonical_name=canonical_name,
            definition=definition,
            subject="Physics",
            grade_band="JEE",
            source_refs=source_refs,
            aliases=aliases,
            syllabus_node_ids=(syllabus_node_id,),
            version=graph_version,
        )
        return

    concepts[concept_id] = Concept(
        id=concept.id,
        canonical_name=concept.canonical_name,
        definition=concept.definition,
        subject=concept.subject,
        grade_band=concept.grade_band,
        source_refs=tuple(dict.fromkeys(concept.source_refs + source_refs)),
        aliases=tuple(sorted(set(concept.aliases) | set(aliases))),
        syllabus_node_ids=tuple(sorted(set(concept.syllabus_node_ids) | {syllabus_node_id})),
        version=graph_version,
    )


def _seed_canonical_syllabus(
    *,
    root_node: SyllabusNode,
    root_source_ref: str,
    graph_version: str,
    syllabus_nodes: list[SyllabusNode],
    seen_node_ids: set[str],
    concepts: dict[str, Concept],
) -> None:
    for chapter_index, chapter in enumerate(PHYSICS_SYLLABUS, start=1):
        chapter_id = stable_id("syllabus", "physics", chapter.title)
        _append_syllabus_node(
            syllabus_nodes,
            seen_node_ids,
            SyllabusNode(
                id=chapter_id,
                title=chapter.title,
                level="chapter",
                parent_id=root_node.id,
                order_index=chapter_index * 1000,
                source_ref=root_source_ref,
                version=graph_version,
            ),
        )
        _merge_concept(
            concepts,
            concept_id=stable_id("concept", chapter.title),
            canonical_name=chapter.title,
            definition=f"JEE Physics chapter covering {chapter.title.lower()}.",
            source_refs=(root_source_ref,),
            aliases=(normalize_text(chapter.title), stable_slug(chapter.title).replace("-", " ")),
            syllabus_node_id=chapter_id,
            graph_version=graph_version,
        )

        for topic_index, topic in enumerate(chapter.topics, start=1):
            topic_id = stable_id("syllabus", "physics", chapter.title, topic.title)
            _append_syllabus_node(
                syllabus_nodes,
                seen_node_ids,
                SyllabusNode(
                    id=topic_id,
                    title=topic.title,
                    level="topic",
                    parent_id=chapter_id,
                    order_index=chapter_index * 1000 + topic_index * 10,
                    source_ref=root_source_ref,
                    version=graph_version,
                ),
            )
            for concept_index, concept_name in enumerate(topic.concepts, start=1):
                concept_node_id = stable_id(
                    "syllabus",
                    "physics",
                    chapter.title,
                    topic.title,
                    concept_name,
                )
                _append_syllabus_node(
                    syllabus_nodes,
                    seen_node_ids,
                    SyllabusNode(
                        id=concept_node_id,
                        title=concept_name,
                        level="subconcept",
                        parent_id=topic_id,
                        order_index=chapter_index * 1000 + topic_index * 10 + concept_index,
                        source_ref=root_source_ref,
                        version=graph_version,
                    ),
                )
                _merge_concept(
                    concepts,
                    concept_id=stable_id("concept", concept_name),
                    canonical_name=concept_name,
                    definition=(
                        f"JEE Physics concept under {chapter.title} > {topic.title}."
                    ),
                    source_refs=(root_source_ref,),
                    aliases=tuple(
                        sorted(
                            {
                                normalize_text(concept_name),
                                stable_slug(concept_name).replace("-", " "),
                                normalize_text(topic.title),
                                normalize_text(chapter.title),
                            }
                        )
                    ),
                    syllabus_node_id=concept_node_id,
                    graph_version=graph_version,
                )


def _parse_question_records(markdown_path: Path) -> tuple[PhysicsQuestionRecord, ...]:
    text = markdown_path.read_text(encoding="utf-8")
    records: list[PhysicsQuestionRecord] = []

    for section_match in _QUESTION_SECTION_RE.finditer(text):
        question_id = section_match.group("question_id").strip()
        body = section_match.group("body")
        topic = _extract_line_value(body, "Topic:", default="Physics")
        paper_ref = _extract_line_value(body, "Paper Reference:", default=markdown_path.stem)
        paper_title = _extract_line_value(body, "Paper Title:", default=markdown_path.stem)
        question_text = _extract_block_value(
            body,
            "Question:",
            ("Step-by-Step Solution:", "Common Pitfalls & Misconceptions:", "Final Answer:"),
        )
        solution_text = _extract_block_value(
            body,
            "Step-by-Step Solution:",
            ("Common Pitfalls & Misconceptions:", "Final Answer:"),
        )
        if not solution_text:
            solution_text = _extract_block_value(body, "Worked Solution:", ("Common Pitfalls & Misconceptions:", "Final Answer:"))
        final_answer = _extract_line_value(body, "Final Answer:", default="")
        pitfalls = _extract_pitfalls(body)

        records.append(
            PhysicsQuestionRecord(
                question_id=question_id,
                paper_ref=paper_ref,
                paper_title=paper_title,
                topic=topic,
                question_text=question_text,
                solution_text=solution_text,
                pitfalls=pitfalls,
                final_answer=final_answer,
                source_path=str(markdown_path),
            )
        )

    return tuple(records)


def _normalized_question_key(question_id: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", question_id.upper())


def _infer_topic(question_text: str, solution_text: str) -> str:
    combined = re.sub(r"\s+", " ", f"{question_text}\n{solution_text}").strip()
    for pattern, topic in _TOPIC_RULES:
        if pattern.search(combined):
            return topic
    return "General Physics"


def _is_usable_question(question_text: str) -> bool:
    normalized = normalize_text(question_text)
    meaningful_tokens = re.findall(r"[a-z]{3,}", normalized)
    return len(normalized) >= 40 and len(meaningful_tokens) >= 5


def _load_jsonl_question_records(
    jsonl_path: Path,
    topic_by_question: dict[str, str],
) -> tuple[PhysicsQuestionRecord, ...]:
    records: list[PhysicsQuestionRecord] = []
    with jsonl_path.open("r", encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSONL record at {jsonl_path}:{line_number}") from error

            question_id = str(payload.get("question_ref", "")).strip()
            question_text = str(payload.get("question_text", "")).strip()
            solution_text = str(payload.get("solution_text", "")).strip()
            if not question_id or not _is_usable_question(question_text):
                continue
            topic = topic_by_question.get(_normalized_question_key(question_id))
            if topic is None:
                topic = _infer_topic(question_text, solution_text)
            pitfalls = tuple(
                str(pitfall).strip()
                for pitfall in payload.get("pitfalls", ())
                if str(pitfall).strip()
            )
            records.append(
                PhysicsQuestionRecord(
                    question_id=question_id,
                    paper_ref=str(payload.get("paper_ref", jsonl_path.stem)).strip(),
                    paper_title=str(payload.get("paper_title", jsonl_path.stem)).strip(),
                    topic=topic,
                    question_text=question_text,
                    solution_text=solution_text,
                    pitfalls=pitfalls,
                    final_answer=str(payload.get("official_answer", "")).strip(),
                    source_path=str(jsonl_path),
                )
            )
    return tuple(records)


def load_physics_corpus(source_root: str | Path) -> PhysicsCorpusBundle:
    root = Path(source_root).resolve()
    source_documents = []
    normalized_documents = []
    question_records: list[PhysicsQuestionRecord] = []
    skipped_sources: list[str] = []
    paths = discover_corpus_paths(root)

    markdown_records = [
        record
        for source_path in paths
        if source_path.suffix.lower() in {".md", ".markdown"}
        for record in _parse_question_records(source_path)
    ]
    topic_by_question = {
        _normalized_question_key(record.question_id): record.topic
        for record in markdown_records
        if record.topic
    }
    jsonl_paths = [path for path in paths if path.suffix.lower() == ".jsonl"]
    canonical_paths = set(jsonl_paths)
    canonical_paths.update(
        path
        for path in paths
        if path.suffix.lower() in {".md", ".markdown"}
        and _parse_question_records(path)
    )

    for source_path in paths:
        if source_path not in canonical_paths:
            relative_parts = {
                part.lower() for part in source_path.relative_to(root).parts
            }
            if not relative_parts & {
                "refrencebook_hcverma",
                "refrencebook_ncert",
                "syllabus",
            }:
                skipped_sources.append(
                    f"{source_path}: skipped because a structured derivative is available"
                )
            continue
        source_type = source_path.suffix.lower()
        if source_type == ".jsonl":
            source_type = "text"
        elif source_type == ".md":
            source_type = "markdown"
        elif source_type == ".markdown":
            source_type = "markdown"
        elif source_type in {".txt", ".rst"}:
            source_type = "text"
        elif source_type in {".html", ".htm"}:
            source_type = "html"
        elif source_type == ".json":
            source_type = "json"
        elif source_type == ".csv":
            source_type = "csv"
        elif source_type == ".docx":
            source_type = "docx"
        elif source_type == ".pdf":
            source_type = "pdf"
        else:
            source_type = "text"

        read = load_local_source(source_path, source_type=source_type, version="corpus-v1")
        normalized = normalize_source_document(read.source_document, read.raw_text, version="corpus-v1")
        source_documents.append(read.source_document)
        normalized_documents.append(normalized)

    if jsonl_paths:
        for jsonl_path in jsonl_paths:
            question_records.extend(_load_jsonl_question_records(jsonl_path, topic_by_question))
    else:
        question_records.extend(markdown_records)

    return PhysicsCorpusBundle(
        source_documents=tuple(source_documents),
        normalized_documents=tuple(normalized_documents),
        question_records=tuple(question_records),
        skipped_sources=tuple(skipped_sources),
    )


def build_physics_seed_bundle(
    source_root: str | Path,
    *,
    graph_version: str = "physics-v1",
    extraction_version: str = "physics-extract-v1",
    visual_corpus=None,
) -> GraphSeedBundle:
    """Build a deterministic graph seed bundle from a local physics corpus folder."""

    corpus = load_physics_corpus(source_root)
    if not corpus.question_records:
        raise ValueError(f"no physics question records were found under {Path(source_root).resolve()}")

    reference_corpus = load_reference_corpus(source_root, version=extraction_version)
    root_source_ref = (
        reference_corpus.syllabus_source_id
        or (corpus.source_documents[0].id if corpus.source_documents else stable_id("source", "physics", graph_version))
    )
    root_node = SyllabusNode(
        id=stable_id("syllabus", "physics"),
        title="Physics",
        level="subject",
        parent_id=None,
        order_index=1,
        source_ref=root_source_ref,
        version=graph_version,
    )

    base_topics: dict[str, dict[str, object]] = {}
    topic_nodes: dict[str, dict[str, object]] = {}
    concepts: dict[str, Concept] = {}
    skills: dict[str, Skill] = {}
    prerequisite_edges: dict[str, PrerequisiteEdge] = {}
    misconceptions: dict[str, Misconception] = {}
    evidence_artifacts: dict[str, EvidenceArtifact] = {}
    assessment_items: dict[str, AssessmentItem] = {}
    syllabus_nodes: list[SyllabusNode] = [root_node]
    seen_syllabus_node_ids = {root_node.id}

    _seed_canonical_syllabus(
        root_node=root_node,
        root_source_ref=root_source_ref,
        graph_version=graph_version,
        syllabus_nodes=syllabus_nodes,
        seen_node_ids=seen_syllabus_node_ids,
        concepts=concepts,
    )

    for order_index, record in enumerate(corpus.question_records, start=1):
        base_topic, detail_topic = _split_topic(record.topic)
        topic_label = record.topic.strip() or "Physics"
        chapter_key = base_topic
        if chapter_key not in base_topics:
            base_topics[chapter_key] = {
                "order_index": order_index,
                "source_ref": root_source_ref,
            }
        if topic_label not in topic_nodes:
            topic_nodes[topic_label] = {
                "id": stable_id("syllabus", "physics", chapter_key, topic_label) if detail_topic else stable_id("syllabus", "physics", topic_label),
                "title": detail_topic or topic_label,
                "parent_id": stable_id("syllabus", "physics", chapter_key),
                "order_index": order_index,
                "source_ref": root_source_ref,
                "detail": detail_topic,
            }

        evidence_id = stable_id("evidence", record.question_id, record.paper_ref)
        evidence_artifacts[evidence_id] = EvidenceArtifact(
            id=evidence_id,
            artifact_type="worked_solution",
            locator=f"{Path(record.source_path).name}::{record.question_id}",
            excerpt=record.question_text[:240].strip(),
            source_system="local",
            version=graph_version,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
        )

        concept_id = stable_id("concept", topic_label)
        skill_name, skill_aliases = _infer_skill_data(topic_label, record.solution_text)
        skill_id = stable_id("skill", skill_name)
        reference_evidence = reference_corpus.evidence_by_topic.get(topic_label, ())
        reference_refs = tuple(evidence.id for evidence in reference_evidence)

        concept = concepts.get(concept_id)
        if concept is None:
            _merge_concept(
                concepts,
                concept_id=concept_id,
                canonical_name=topic_label,
                definition=f"Physics topic extracted from {record.question_id}.",
                source_refs=reference_refs + (evidence_id, root_source_ref),
                aliases=_topic_aliases(topic_label, base_topic, detail_topic),
                syllabus_node_id=str(topic_nodes[topic_label]["id"]),
                graph_version=graph_version,
            )
        else:
            _merge_concept(
                concepts,
                concept_id=concept_id,
                canonical_name=concept.canonical_name,
                definition=concept.definition,
                source_refs=reference_refs + (evidence_id, root_source_ref),
                aliases=_topic_aliases(topic_label, base_topic, detail_topic),
                syllabus_node_id=str(topic_nodes[topic_label]["id"]),
                graph_version=graph_version,
            )

        skill = skills.get(skill_id)
        if skill is None:
            skills[skill_id] = Skill(
                id=skill_id,
                canonical_name=skill_name,
                success_criteria=f"Solve {topic_label} questions correctly.",
                source_refs=reference_refs + (evidence_id, root_source_ref),
                aliases=skill_aliases,
                syllabus_node_ids=(topic_nodes[topic_label]["id"],),
                version=graph_version,
            )
        else:
            skills[skill_id] = Skill(
                id=skill.id,
                canonical_name=skill.canonical_name,
                success_criteria=skill.success_criteria,
                source_refs=tuple(dict.fromkeys(skill.source_refs + reference_refs + (evidence_id, root_source_ref))),
                aliases=tuple(sorted(set(skill.aliases) | set(skill_aliases))),
                syllabus_node_ids=tuple(sorted(set(skill.syllabus_node_ids) | {topic_nodes[topic_label]["id"]})),
                version=graph_version,
            )

        prerequisite_id = stable_id("edge", skill_id, concept_id)
        prerequisite_edges[prerequisite_id] = PrerequisiteEdge(
            id=prerequisite_id,
            from_id=skill_id,
            to_id=concept_id,
            relation_type="prerequisite_of",
            strength=0.9,
            rationale=f"The skill {skill_name} supports solving {topic_label} problems.",
            source_refs=(evidence_id, root_source_ref),
            version=graph_version,
        )

        visual_evidence_refs = (
            visual_corpus.evidence_by_question.get(record.question_id, ())
            if visual_corpus is not None
            else ()
        )
        assessment_items[record.question_id] = AssessmentItem(
            id=record.question_id,
            prompt=record.question_text,
            expected_concepts=(concept_id,),
            expected_steps=(skill_id,),
            rubric_ref=evidence_id,
            source_refs=visual_evidence_refs + (evidence_id, root_source_ref),
            visual_evidence_refs=visual_evidence_refs,
            requires_visual_interpretation=(
                record.question_id in visual_corpus.requires_visual
                if visual_corpus is not None
                else False
            ),
            version=graph_version,
        )

        for pitfall_index, pitfall in enumerate(record.pitfalls, start=1):
            misconception_id = stable_id("misconception", record.question_id, str(pitfall_index), pitfall)
            mapped_to_ids = (concept_id, skill_id)
            trigger_patterns = _infer_misconception_patterns(pitfall)
            misconceptions[misconception_id] = Misconception(
                id=misconception_id,
                label=pitfall[:120].strip(),
                description=pitfall,
                trigger_patterns=trigger_patterns,
                diagnostic_signals=trigger_patterns,
                remediation_hint=f"Revisit the worked solution for {topic_label}.",
                source_refs=(evidence_id, root_source_ref),
                mapped_to_ids=mapped_to_ids,
                version=graph_version,
            )

    concept_by_name = {
        concept.canonical_name: concept for concept in concepts.values()
    }
    for prerequisite_name, dependent_name in _TOPIC_PREREQUISITES:
        prerequisite = concept_by_name.get(prerequisite_name)
        dependent = concept_by_name.get(dependent_name)
        if prerequisite is None or dependent is None:
            continue
        edge_id = stable_id(
            "edge",
            "textbook-prerequisite",
            prerequisite.id,
            dependent.id,
        )
        prerequisite_edges[edge_id] = PrerequisiteEdge(
            id=edge_id,
            from_id=prerequisite.id,
            to_id=dependent.id,
            relation_type="prerequisite_of",
            strength=0.8,
            rationale=(
                f"{prerequisite_name} provides the conceptual foundation for "
                f"{dependent_name} in the JEE Physics curriculum."
            ),
            source_refs=tuple(
                dict.fromkeys(prerequisite.source_refs + dependent.source_refs)
            ),
            version=graph_version,
        )

    for base_topic, meta in sorted(base_topics.items(), key=lambda item: (item[1]["order_index"], item[0].lower())):
        chapter_id = stable_id("syllabus", "physics", base_topic)
        _append_syllabus_node(
            syllabus_nodes,
            seen_syllabus_node_ids,
            SyllabusNode(
                id=chapter_id,
                title=base_topic,
                level="chapter",
                parent_id=root_node.id,
                order_index=int(meta["order_index"]),
                source_ref=str(meta["source_ref"]),
                version=graph_version,
            ),
        )

    topic_order: dict[str, int] = {}
    for index, record in enumerate(corpus.question_records, start=1):
        topic_label = record.topic.strip() or "Physics"
        topic_order.setdefault(topic_label, index)

    for record in corpus.question_records:
        base_topic, detail_topic = _split_topic(record.topic)
        if not detail_topic:
            continue

        topic_label = record.topic.strip() or "Physics"
        topic_meta = topic_nodes[topic_label]
        topic_id = str(topic_meta["id"])
        _append_syllabus_node(
            syllabus_nodes,
            seen_syllabus_node_ids,
            SyllabusNode(
                id=topic_id,
                title=str(topic_meta["title"]),
                level="topic",
                parent_id=str(topic_meta["parent_id"]),
                order_index=topic_order[topic_label],
                source_ref=str(topic_meta["source_ref"]),
                version=graph_version,
            ),
        )

    created_at = datetime.now(tz=timezone.utc).isoformat()
    reference_evidence_artifacts = tuple(
        evidence
        for topic_evidence in reference_corpus.evidence_by_topic.values()
        for evidence in topic_evidence
    )
    visual_source_documents = (
        visual_corpus.source_documents if visual_corpus is not None else ()
    )
    visual_evidence_artifacts = (
        visual_corpus.evidence_artifacts if visual_corpus is not None else ()
    )
    return GraphSeedBundle(
        id=stable_id("seed", graph_version, extraction_version, Path(source_root).resolve().name),
        graph_version=graph_version,
        extraction_version=extraction_version,
        source_documents=(
            corpus.source_documents
            + reference_corpus.source_documents
            + visual_source_documents
        ),
        normalized_documents=corpus.normalized_documents + reference_corpus.normalized_documents,
        syllabus_nodes=tuple(syllabus_nodes),
        concepts=tuple(sorted(concepts.values(), key=lambda item: (item.canonical_name.lower(), item.id))),
        skills=tuple(sorted(skills.values(), key=lambda item: (item.canonical_name.lower(), item.id))),
        prerequisite_edges=tuple(sorted(prerequisite_edges.values(), key=lambda item: (item.from_id, item.to_id, item.id))),
        misconceptions=tuple(sorted(misconceptions.values(), key=lambda item: (item.label.lower(), item.id))),
        evidence_artifacts=tuple(
            sorted(
                tuple(evidence_artifacts.values())
                + reference_evidence_artifacts
                + visual_evidence_artifacts,
                key=lambda item: (
                    -SOURCE_AUTHORITY_WEIGHTS.get(item.source_system, 0.0),
                    item.locator,
                    item.id,
                ),
            )
        ),
        assessment_items=tuple(sorted(assessment_items.values(), key=lambda item: (item.id, item.prompt[:40]))),
        created_at=created_at,
        version=graph_version,
    )
