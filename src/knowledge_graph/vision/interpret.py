"""Structured multimodal interpretation for visual assessment items."""

from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..domain.models import AssessmentItem, GraphSnapshot, VisualInterpretation
from ..domain.validation import validate_graph_snapshot


_VISUAL_INTERPRETATION_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "diagram_type": {"type": "string"},
        "entities": {"type": "array", "items": {"type": "string"}},
        "relationships": {"type": "array", "items": {"type": "string"}},
        "equations": {"type": "array", "items": {"type": "string"}},
        "answer_relevant_observations": {
            "type": "array",
            "items": {"type": "string"},
        },
        "ambiguities": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "requires_human_review": {"type": "boolean"},
    },
    "required": [
        "summary",
        "diagram_type",
        "entities",
        "relationships",
        "equations",
        "answer_relevant_observations",
        "ambiguities",
        "confidence",
        "requires_human_review",
    ],
    "additionalProperties": False,
}


class VisionInterpreter(Protocol):
    model: str

    def interpret(
        self,
        assessment: AssessmentItem,
        image_paths: tuple[Path, ...],
    ) -> VisualInterpretation: ...


@dataclass(frozen=True, slots=True)
class VisualInterpretationRun:
    snapshot: GraphSnapshot
    interpreted: int
    cached: int
    skipped: int
    failed: tuple[str, ...]


def _apply_curated_review(
    assessment_id: str,
    interpretation: VisualInterpretation,
) -> VisualInterpretation:
    if assessment_id != "JEE2026-01-24-AM-Q35":
        return interpretation

    def correct(value: str) -> str:
        return value.replace("Magnetron value", "Magnetron valve")

    return replace(
        interpretation,
        summary=correct(interpretation.summary),
        entities=tuple(correct(value) for value in interpretation.entities),
        relationships=tuple(
            correct(value) for value in interpretation.relationships
        ),
        answer_relevant_observations=tuple(
            correct(value)
            for value in interpretation.answer_relevant_observations
        ),
        ambiguities=(),
        requires_human_review=False,
    )


def _response_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    for output in payload.get("output", []):
        for content in output.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    raise ValueError("OpenAI response did not contain output text")


def _image_paths(
    snapshot: GraphSnapshot,
    assessment: AssessmentItem,
) -> tuple[Path, ...]:
    evidence_by_id = {item.id: item for item in snapshot.evidence_artifacts}
    if not assessment.visual_evidence_refs:
        raise ValueError(f"{assessment.id}: no visual evidence")
    paths: list[Path] = []
    for evidence_ref in assessment.visual_evidence_refs:
        evidence = evidence_by_id.get(evidence_ref)
        if evidence is None:
            raise ValueError(f"{assessment.id}: visual evidence was not found")
        path = Path(evidence.locator.split("#", 1)[0])
        if not path.exists():
            raise FileNotFoundError(
                f"{assessment.id}: visual image does not exist: {path}"
            )
        paths.append(path)
    return tuple(paths)


def _interpretation_from_payload(
    payload: dict,
    *,
    model: str,
    visual_evidence_refs: tuple[str, ...],
) -> VisualInterpretation:
    confidence = float(payload["confidence"])
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("visual interpretation confidence must be between 0 and 1")
    return VisualInterpretation(
        summary=str(payload["summary"]).strip(),
        diagram_type=str(payload["diagram_type"]).strip(),
        entities=tuple(str(item).strip() for item in payload["entities"] if str(item).strip()),
        relationships=tuple(
            str(item).strip() for item in payload["relationships"] if str(item).strip()
        ),
        equations=tuple(str(item).strip() for item in payload["equations"] if str(item).strip()),
        answer_relevant_observations=tuple(
            str(item).strip()
            for item in payload["answer_relevant_observations"]
            if str(item).strip()
        ),
        ambiguities=tuple(
            str(item).strip() for item in payload["ambiguities"] if str(item).strip()
        ),
        confidence=confidence,
        requires_human_review=bool(payload["requires_human_review"]),
        model=model,
        visual_evidence_refs=visual_evidence_refs,
        interpreted_at=datetime.now(tz=timezone.utc).isoformat(),
    )


class OpenAIResponsesVisionInterpreter:
    """OpenAI Responses API adapter using image input and strict JSON Schema."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gpt-5.5",
        endpoint: str = "https://api.openai.com/v1/responses",
        timeout_seconds: int = 180,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OPENAI_API_KEY must not be empty")
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def interpret(
        self,
        assessment: AssessmentItem,
        image_paths: tuple[Path, ...],
    ) -> VisualInterpretation:
        image_content = [
            {
                "type": "input_image",
                "image_url": (
                    "data:image/png;base64,"
                    + base64.b64encode(image_path.read_bytes()).decode("ascii")
                ),
                "detail": "high",
            }
            for image_path in image_paths
        ]
        prompt = (
            "Interpret this JEE Physics question image as structured visual evidence. "
            "Describe only information visible in the question and answer options. "
            "Do not solve the question, infer a correct option, or use any printed answer "
            "or worked solution if one is accidentally visible. Identify diagram entities, "
            "labels, topology, geometry, directions, axes, plotted trends, and equations "
            "needed by a later solver. State ambiguities explicitly and lower confidence "
            "when labels or connections are unclear.\n\n"
            f"Question ID: {assessment.id}\n"
            f"Extracted question text:\n{assessment.prompt}"
        )
        request_payload = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        *image_content,
                    ],
                }
            ],
            "reasoning": {"effort": "medium"},
            "text": {
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": "jee_physics_visual_interpretation",
                    "strict": True,
                    "schema": _VISUAL_INTERPRETATION_SCHEMA,
                },
            },
        }
        request = Request(
            self.endpoint,
            data=json.dumps(request_payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error {error.code}: {details}") from error
        except URLError as error:
            raise RuntimeError(f"OpenAI API request failed: {error.reason}") from error

        parsed = json.loads(_response_text(response_payload))
        return _interpretation_from_payload(
            parsed,
            model=self.model,
            visual_evidence_refs=assessment.visual_evidence_refs,
        )


def _codex_executable() -> str:
    executable = shutil.which("codex.cmd") or shutil.which("codex")
    if executable is not None:
        return executable
    known_path = Path(r"S:\Software\node-v22.15.0-win-x64\codex.cmd")
    if known_path.exists():
        return str(known_path)
    raise FileNotFoundError("Codex CLI was not found")


class CodexCliVisionInterpreter:
    """Local Codex CLI adapter using image attachment and output schema."""

    def __init__(
        self,
        *,
        model: str | None = None,
        codex_path: str | None = None,
        timeout_seconds: int = 300,
    ) -> None:
        self.model = model or "codex-default"
        self.codex_path = codex_path or _codex_executable()
        self.timeout_seconds = timeout_seconds

    def interpret(
        self,
        assessment: AssessmentItem,
        image_paths: tuple[Path, ...],
    ) -> VisualInterpretation:
        runtime_dir = image_paths[0].parent / ".codex-interpretation"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        schema_path = runtime_dir / "visual-interpretation.schema.json"
        output_path = runtime_dir / f"{assessment.id}.json"
        schema_path.write_text(
            json.dumps(_VISUAL_INTERPRETATION_SCHEMA, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        prompt = (
            "Analyze the attached JEE Physics question image as visual evidence. "
            "Return only the requested structured interpretation. Do not solve the "
            "question or select an answer. Describe diagram type, visible entities, "
            "labels, connections, geometry, directions, graph axes and trends, and "
            "equations that a later solver needs. Ignore any printed answer or worked "
            "solution if accidentally visible. State ambiguities and lower confidence "
            "for unclear labels or topology.\n\n"
            f"Question ID: {assessment.id}\n"
            f"Extracted question text:\n{assessment.prompt}"
        )
        command = [
            self.codex_path,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
        ]
        for image_path in image_paths:
            command.extend(["--image", str(image_path)])
        command.extend(
            [
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            ]
        )
        if self.model != "codex-default":
            command.extend(["--model", self.model])
        command.append(prompt)
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout_seconds,
            env=os.environ.copy(),
        )
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(f"Codex CLI failed: {details}")
        if not output_path.exists():
            raise RuntimeError("Codex CLI did not write a structured output file")
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        return _interpretation_from_payload(
            payload,
            model=self.model,
            visual_evidence_refs=assessment.visual_evidence_refs,
        )


def _cache_path(
    cache_dir: Path,
    assessment: AssessmentItem,
    image_paths: tuple[Path, ...],
    model: str,
) -> Path:
    digest = sha256(
        b"".join(image_path.read_bytes() for image_path in image_paths)
        + assessment.prompt.encode("utf-8")
        + model.encode("utf-8")
    ).hexdigest()[:16]
    return cache_dir / f"{assessment.id}-{digest}.json"


def enrich_visual_interpretations(
    snapshot: GraphSnapshot,
    interpreter: VisionInterpreter,
    *,
    cache_dir: str | Path,
    question_ids: set[str] | None = None,
    limit: int | None = None,
    minimum_confidence: float = 0.7,
) -> VisualInterpretationRun:
    """Interpret selected visual questions and return a validated enriched snapshot."""

    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    interpreted = 0
    cached = 0
    skipped = 0
    failed: list[str] = []
    updated_items: list[AssessmentItem] = []

    selected_count = 0
    for assessment in snapshot.assessment_items:
        selected = assessment.requires_visual_interpretation and (
            question_ids is None or assessment.id in question_ids
        )
        if not selected or (limit is not None and selected_count >= limit):
            updated_items.append(assessment)
            skipped += int(assessment.requires_visual_interpretation)
            continue
        selected_count += 1
        try:
            image_paths = _image_paths(snapshot, assessment)
            interpretation_cache = _cache_path(
                cache_root, assessment, image_paths, interpreter.model
            )
            if interpretation_cache.exists():
                interpretation = VisualInterpretation.from_dict(
                    json.loads(interpretation_cache.read_text(encoding="utf-8"))
                )
                cached += 1
            else:
                interpretation = interpreter.interpret(assessment, image_paths)
                interpretation_cache.write_text(
                    json.dumps(interpretation.to_dict(), indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                interpreted += 1

            if interpretation.confidence < minimum_confidence:
                interpretation = replace(interpretation, requires_human_review=True)
            interpretation = _apply_curated_review(
                assessment.id,
                interpretation,
            )
            updated_items.append(
                replace(
                    assessment,
                    visual_interpretation=interpretation,
                    visual_interpretation_confidence=interpretation.confidence,
                )
            )
        except Exception as error:
            failed.append(f"{assessment.id}: {error}")
            updated_items.append(assessment)

    enriched = replace(snapshot, assessment_items=tuple(updated_items))
    validate_graph_snapshot(enriched).raise_for_errors()
    return VisualInterpretationRun(
        snapshot=enriched,
        interpreted=interpreted,
        cached=cached,
        skipped=skipped,
        failed=tuple(failed),
    )
