"""Human-readable and machine-readable output formatting."""

from __future__ import annotations

import json

from ..domain.models import DiagnosticRecord


def diagnostic_record_to_json(record: DiagnosticRecord, *, indent: int = 2) -> str:
    return json.dumps(record.to_dict(), indent=indent, sort_keys=True)


def format_feedback(record: DiagnosticRecord) -> str:
    if record.abstained:
        reason = record.abstention_reason or "insufficient_grounding"
        return f"Abstained: {reason}."

    gap = record.primary_gap.label if record.primary_gap else "unknown"
    chain = " -> ".join(record.prerequisite_chain) if record.prerequisite_chain else "none"
    misconception = (
        f"{record.misconception_match.misconception_id} ({record.misconception_match.confidence:.2f})"
        if record.misconception_match
        else "none"
    )
    evidence = ", ".join(record.evidence_refs) if record.evidence_refs else "none"
    return (
        f"Primary gap: {gap}. "
        f"Prerequisite chain: {chain}. "
        f"Misconception match: {misconception}. "
        f"Confidence: {record.confidence:.2f}. "
        f"Evidence: {evidence}."
    )
