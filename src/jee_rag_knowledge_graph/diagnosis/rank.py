"""Candidate ranking for grounded diagnoses."""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.models import MisconceptionMatch, PrimaryGap


@dataclass(frozen=True, slots=True)
class DiagnosisCandidate:
    primary_gap: PrimaryGap | None
    prerequisite_chain: tuple[str, ...]
    misconception_match: MisconceptionMatch | None
    evidence_refs: tuple[str, ...]
    score: float


def rank_candidates(candidates: tuple[DiagnosisCandidate, ...]) -> DiagnosisCandidate | None:
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda candidate: (
            candidate.score,
            len(candidate.evidence_refs),
            len(candidate.prerequisite_chain),
            candidate.primary_gap.concept_id if candidate.primary_gap else "",
        ),
    )
