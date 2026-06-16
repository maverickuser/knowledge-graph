"""Abstention rules for unsupported diagnoses."""

from __future__ import annotations

from .rank import DiagnosisCandidate


def should_abstain(candidate: DiagnosisCandidate | None, threshold: float = 0.55) -> bool:
    if candidate is None:
        return True
    if candidate.primary_gap is None:
        return True
    return candidate.score < threshold
