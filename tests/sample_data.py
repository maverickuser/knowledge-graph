"""Reusable sample graph data for tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from jee_rag_knowledge_graph.community.partition import partition_communities
from jee_rag_knowledge_graph.community.summarize import generate_community_summaries
from jee_rag_knowledge_graph.diagnosis.retrieve import diagnose_response
from jee_rag_knowledge_graph.domain.ids import stable_id
from jee_rag_knowledge_graph.domain.models import (
    AssessmentItem,
    Concept,
    EvidenceArtifact,
    GraphSeedBundle,
    GraphSnapshot,
    Misconception,
    PrerequisiteEdge,
    Skill,
    SyllabusNode,
)
from jee_rag_knowledge_graph.graph.build import build_graph
from jee_rag_knowledge_graph.ingestion.loaders import load_local_source
from jee_rag_knowledge_graph.ingestion.normalize import normalize_source_document


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
SAMPLE_SYLLABUS = FIXTURE_DIR / "sample_syllabus.md"


def build_sample_seed_bundle() -> GraphSeedBundle:
    read = load_local_source(SAMPLE_SYLLABUS, title="Sample Syllabus", version="1")
    normalized = normalize_source_document(read.source_document, read.raw_text, version="1")

    root = SyllabusNode(
        id=stable_id("syllabus", "algebra"),
        title="Algebra",
        level="subject",
        parent_id=None,
        order_index=1,
        source_ref="evidence-syllabus-1",
        version="1",
    )
    chapter = SyllabusNode(
        id=stable_id("syllabus", "algebra", "quadratic-expressions"),
        title="Quadratic Expressions",
        level="topic",
        parent_id=root.id,
        order_index=1,
        source_ref="evidence-syllabus-1",
        version="1",
    )

    distributive_law = Concept(
        id=stable_id("concept", "distributive-law"),
        canonical_name="distributive law",
        definition="The distributive law expands products over sums.",
        subject="Mathematics",
        grade_band="Secondary",
        source_refs=("evidence-textbook-ch-1",),
        aliases=("distribution law",),
        syllabus_node_ids=(chapter.id,),
        version="1",
    )
    factor_quadratics = Concept(
        id=stable_id("concept", "factor-quadratics"),
        canonical_name="factoring quadratics",
        definition="Rewrite a quadratic expression as a product of binomials.",
        subject="Mathematics",
        grade_band="Secondary",
        source_refs=("evidence-textbook-ch-3",),
        aliases=("factor quadratics", "quadratic factoring"),
        syllabus_node_ids=(chapter.id,),
        version="1",
    )
    expand_skill = Skill(
        id=stable_id("skill", "expand-expressions"),
        canonical_name="expand expressions",
        success_criteria="Expand expressions correctly using the distributive law.",
        source_refs=("evidence-rubric-1",),
        aliases=("expand using the distributive law",),
        syllabus_node_ids=(chapter.id,),
        version="1",
    )

    prereq_edge = PrerequisiteEdge(
        id=stable_id("edge", distributive_law.id, factor_quadratics.id),
        from_id=distributive_law.id,
        to_id=factor_quadratics.id,
        relation_type="prerequisite_of",
        strength=0.95,
        rationale="The distributive law is needed before factoring quadratics.",
        source_refs=("evidence-textbook-ch-3",),
        version="1",
    )

    misconception = Misconception(
        id=stable_id("misconception", "sign-error"),
        label="sign error during factoring",
        description="The student drops or flips a sign while factoring a quadratic expression.",
        trigger_patterns=("sign error", "wrong sign", "minus sign"),
        diagnostic_signals=("forgot the negative", "lost a sign"),
        remediation_hint="Re-check the sign pattern after expanding the factors.",
        source_refs=("evidence-misconception-1",),
        mapped_to_ids=(factor_quadratics.id,),
        version="1",
    )

    evidence_artifacts = (
        EvidenceArtifact(
            id="evidence-syllabus-1",
            artifact_type="syllabus",
            locator="chapter-2",
            excerpt="Quadratic Expressions",
            source_system="local",
            version="1",
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
        ),
        EvidenceArtifact(
            id="evidence-textbook-ch-1",
            artifact_type="textbook",
            locator="chapter-1",
            excerpt="The distributive law expands products over sums.",
            source_system="local",
            version="1",
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
        ),
        EvidenceArtifact(
            id="evidence-textbook-ch-3",
            artifact_type="textbook",
            locator="chapter-3",
            excerpt="Factoring quadratics rewrites the expression as binomials.",
            source_system="local",
            version="1",
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
        ),
        EvidenceArtifact(
            id="evidence-rubric-1",
            artifact_type="rubric",
            locator="mark-scheme-1",
            excerpt="Expand expressions correctly using the distributive law.",
            source_system="local",
            version="1",
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
        ),
        EvidenceArtifact(
            id="evidence-misconception-1",
            artifact_type="misconception",
            locator="note-1",
            excerpt="Common sign error when factoring quadratics.",
            source_system="local",
            version="1",
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
        ),
    )

    assessment_item = AssessmentItem(
        id="assessment-quadratic-001",
        prompt="Factor the quadratic expression x^2 - 5x + 6.",
        expected_concepts=(factor_quadratics.id,),
        expected_steps=(expand_skill.id,),
        rubric_ref="evidence-rubric-1",
        source_refs=("evidence-rubric-1", "evidence-textbook-ch-3"),
        version="1",
    )

    return GraphSeedBundle(
        id=stable_id("seed", "graph-v1", "extract-v1", read.source_document.id),
        graph_version="graph-v1",
        extraction_version="extract-v1",
        source_documents=(read.source_document,),
        normalized_documents=(normalized,),
        syllabus_nodes=(root, chapter),
        concepts=(distributive_law, factor_quadratics),
        skills=(expand_skill,),
        prerequisite_edges=(prereq_edge,),
        misconceptions=(misconception,),
        evidence_artifacts=evidence_artifacts,
        assessment_items=(assessment_item,),
        created_at=datetime.now(tz=timezone.utc).isoformat(),
        version="graph-v1",
    )


def build_sample_snapshot() -> GraphSnapshot:
    seed_bundle = build_sample_seed_bundle()
    snapshot = build_graph(seed_bundle)
    communities = partition_communities(snapshot)
    summaries = generate_community_summaries(snapshot, communities)
    diagnostic = diagnose_response(
        snapshot.with_communities(communities).with_summaries(summaries),
        assessment_item_id="assessment-quadratic-001",
        student_response_id="response-001",
        response_text="I factor quadratics by using the distributive law, but I made a sign error.",
    )
    return snapshot.with_communities(communities).with_summaries(summaries).with_diagnostics((diagnostic,))
