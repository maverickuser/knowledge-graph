# Diagnostic Knowledge Graph Spec

- Status: Draft
- Date: 2026-06-09
- Target repo: `knowledge-graph`
- Design basis: [GraphRAG / arXiv:2404.16130](https://arxiv.org/pdf/2404.16130)

## 1. Summary

This project will build a syllabus-grounded knowledge graph that acts as the ground truth for an LLM-powered grading and feedback agent.

The graph is not just a storage layer. It is a diagnostic map that must let the agent:

- identify the exact concept a student missed or misunderstood
- trace that failure backward through prerequisite dependencies
- match the student's reasoning against a library of known misconceptions
- produce feedback that is evidence-backed and verifiable
- abstain when the graph cannot support a grounded diagnosis

The design is inspired by GraphRAG's local-to-global indexing pattern: extract structured entities and relations, partition them into hierarchical communities, precompute summaries, and use those summaries at query time instead of reasoning from raw text alone.

## 2. Problem Statement

When grading open-ended student responses, an LLM can often produce a plausible explanation for why the student was wrong, even when that explanation is not supported by the curriculum or by the response itself.

That is the failure mode this project is meant to remove.

The system must treat the knowledge graph as the authoritative source for:

- syllabus structure
- concept dependencies
- canonical reasoning steps
- known incorrect reasoning patterns
- feedback language that is grounded in source evidence

If the graph cannot support a conclusion, the agent must not guess.

## 3. Goals

### 3.1 Primary goals

- Encode the syllabus as a hierarchical curriculum graph.
- Represent atomic concepts, procedural skills, and prerequisite dependencies explicitly.
- Maintain a curated misconception library that maps common wrong turns to specific concepts.
- Support hierarchical communities so the agent can retrieve from coarse-to-fine topic clusters.
- Produce community summaries that make the graph usable at query time without scanning the full corpus.
- Return grounded diagnostic outputs for student answers, including the root cause of an error when evidence exists.
- Persist the canonical graph in AWS DynamoDB with versioned access patterns.

### 3.2 Secondary goals

- Support versioning of syllabus content and misconception definitions.
- Preserve provenance for every concept, relation, and diagnostic claim.
- Make diagnosis paths inspectable by humans.
- Allow future expansion to multiple subjects and exam variants without redesigning the core graph model.

## 4. Scope

### 4.1 In scope

- Syllabus ingestion and normalization.
- Concept extraction and canonical naming.
- Prerequisite modeling between concepts and skills.
- Representation of canonical solution structure where relevant.
- Representation of known misconceptions and wrong-answer patterns.
- Hierarchical community construction for scalable retrieval.
- Precomputed community summaries for each community level.
- Query-time diagnostic selection from relevant communities.
- Grounded feedback generation with citations to graph evidence.
- Abstention when the graph cannot justify a diagnosis.

### 4.2 In scope for later phases, not necessarily phase 1

- Multi-subject support.
- Multiple curriculum boards or syllabi.
- Cross-year trend analysis of misconception frequency.
- Human review workflows for approving new misconceptions.
- Fine-grained confidence calibration from empirical grading data.

## 5. Non-Goals

The following are explicitly outside the scope of this spec:

- General-purpose tutoring or open-domain question answering.
- Replacing the grading policy or human examiner judgment.
- Inference of student intent beyond what the answer and graph support.
- Automatic discovery of new misconceptions without human review.
- OCR, handwriting recognition, or image parsing of answer sheets.
- Automatic rubric generation from scratch.
- Free-form explanatory answers that are not tied to graph evidence.
- Internet-based retrieval at query time.
- Storing personally identifying student data in the graph layer.

## 6. Core Design Principles

### 6.1 Grounded diagnosis only

Every diagnostic conclusion must be traceable to:

- at least one graph node
- at least one explicit graph edge or path
- at least one provenance-bearing evidence artifact

If no grounded path exists, the output must be `abstained`.

### 6.2 Hierarchy is mandatory

The graph must support both:

- a top-down syllabus hierarchy
- a graph-derived community hierarchy

The syllabus hierarchy expresses curriculum order. The community hierarchy expresses retrieval efficiency and topical cohesion.

### 6.3 Canonical identities

Each concept, skill, and misconception must have a stable canonical identifier.

Aliases, paraphrases, and alternate spellings may exist, but they must map back to one canonical node.

### 6.4 Versioned truth

The graph must be versioned. A diagnostic output is only valid relative to the graph version that produced it.

### 6.5 Fail closed

The agent must prefer abstention over unsupported certainty.

### 6.6 DynamoDB-backed persistence

The canonical operational graph must be persisted in AWS DynamoDB.

- The repository layer must hide the DynamoDB access pattern behind a stable interface.
- Versioned graph items must be written so that prior versions remain auditable.
- Query-time retrieval must read from DynamoDB-backed graph artifacts, not raw source files.
- Local extraction and graph construction remain local workflows that emit graph seed bundles and reviewed graph snapshots before persistence.
- Raw source documents remain outside the canonical AWS graph store.

## 7. Data Model

The graph should be modeled as a typed knowledge graph with provenance. The model below is the minimum viable persistent schema for the DynamoDB-backed operational graph.

### 7.1 Persistent entities

| Entity | Purpose | Required fields | Key relations |
| --- | --- | --- | --- |
| `SyllabusNode` | Represents a syllabus container such as chapter, unit, or topic. | `id`, `title`, `level`, `parent_id`, `order_index`, `source_ref`, `version` | Contains `Concept`, `Skill`, or child `SyllabusNode` items. |
| `Concept` | Atomic idea that a student must understand. | `id`, `canonical_name`, `definition`, `subject`, `grade_band`, `source_refs`, `aliases`, `version` | Has prerequisite edges, belongs to a syllabus node, links to misconceptions. |
| `Skill` | Procedural or applied competency. | `id`, `canonical_name`, `success_criteria`, `source_refs`, `version` | Depends on concepts and other skills. |
| `PrerequisiteEdge` | Directed dependency between two concepts or skills. | `from_id`, `to_id`, `relation_type`, `strength`, `rationale`, `source_refs`, `version` | Must point from prerequisite to dependent node. |
| `Misconception` | Curated incorrect belief or reasoning pattern. | `id`, `label`, `description`, `trigger_patterns`, `diagnostic_signals`, `remediation_hint`, `source_refs`, `version` | Maps to one or more concepts or skills. |
| `EvidenceArtifact` | Provenance-bearing source material. | `id`, `artifact_type`, `locator`, `excerpt`, `source_system`, `version`, `timestamp` | Supports concepts, skills, misconceptions, or diagnostic claims. |
| `AssessmentItem` | Question, prompt, or step that the graph can diagnose against. | `id`, `prompt`, `expected_concepts`, `expected_steps`, `rubric_ref`, `version` | Links to concepts, skills, and common misconceptions. |
| `Community` | Graph-derived or syllabus-aligned cluster used for retrieval. | `id`, `level`, `parent_id`, `member_ids`, `theme`, `version` | Contains nodes and lower-level communities. |
| `CommunitySummary` | Precomputed summary of a community. | `id`, `community_id`, `summary_text`, `salient_concepts`, `salient_prereqs`, `salient_misconceptions`, `evidence_refs`, `generated_at`, `version` | Summarizes the community and feeds query-time retrieval. |
| `DiagnosticRecord` | Structured runtime output for one student response. | `id`, `assessment_item_id`, `student_response_id`, `primary_gap`, `prerequisite_chain`, `misconception_match`, `evidence_refs`, `confidence`, `abstained`, `version` | References graph nodes and evidence used to produce feedback. |

### 7.2 Recommended node and edge types

The implementation should support, at minimum, these relationships:

- `contains`
- `is_a`
- `prerequisite_of`
- `depends_on`
- `maps_to`
- `confused_with`
- `supported_by`
- `evidenced_by`
- `assessed_by`
- `summarized_in`

### 7.3 Diagnostic output contract

The grading agent should emit a structured record similar to the following:

```json
{
  "assessment_item_id": "math-algebra-001",
  "student_response_id": "resp-42",
  "primary_gap": {
    "concept_id": "concept-quadratic-factorization",
    "label": "Factoring a quadratic expression"
  },
  "prerequisite_chain": [
    "concept-distributive-law",
    "concept-expression-simplification",
    "concept-quadratic-factorization"
  ],
  "misconception_match": {
    "misconception_id": "misconception-sign-error",
    "confidence": 0.84
  },
  "evidence_refs": [
    "evidence-textbook-chapter-3",
    "evidence-syllabus-unit-2"
  ],
  "confidence": 0.91,
  "abstained": false
}
```

If the graph cannot support the diagnosis, the record must set:

- `abstained = true`
- `primary_gap = null`
- `misconception_match = null`

and should include a short reason such as `insufficient_grounding`.

### 7.4 Graph invariants

The graph must satisfy the following invariants:

- Every `Concept` has at least one canonical definition and one provenance reference.
- Every `Concept` belongs to at least one `SyllabusNode`.
- Every `PrerequisiteEdge` is directed from prerequisite to dependent concept or skill.
- The prerequisite graph must be acyclic within a given curriculum path unless a cross-link is explicitly marked.
- Every `Misconception` links to at least one concept or skill.
- Every `CommunitySummary` references only members inside its community.
- Every `DiagnosticRecord` must cite evidence from the graph and may not rely solely on model memory.

## 8. Community Hierarchy

The project must use a hierarchical community model inspired by GraphRAG.

### 8.1 Syllabus hierarchy

The syllabus hierarchy is the authoritative structural backbone. It should reflect curriculum ordering such as:

- subject
- unit
- chapter
- topic
- subtopic
- concept

This hierarchy is used for navigation and curriculum traceability.

### 8.2 Retrieval communities

Communities are derived clusters used for scalable diagnosis.

They should satisfy the following:

- leaf communities are tightly related and small enough to summarize precisely
- higher-level communities aggregate lower-level communities
- community summaries should support coarse-to-fine retrieval
- cross-cutting prerequisites may appear in multiple summaries, but the canonical node identity must remain singular

### 8.3 Summary strategy

Community summaries must capture:

- the key concepts in the community
- the major prerequisite bottlenecks
- the most common misconceptions
- the kinds of questions or errors the community explains

Summaries should be generated from graph content, not invented by the model.

## 9. Query-Time Diagnostic Flow

When a student response is evaluated, the system should follow this sequence:

1. Normalize the assessment item and student response.
2. Identify the most relevant syllabus nodes and communities.
3. Retrieve the most relevant community summaries.
4. Walk backward through prerequisite edges to find the earliest missing dependency that explains the error.
5. Compare the response against misconception patterns.
6. Rank candidate diagnoses by evidence strength.
7. Produce a structured diagnostic record and feedback text.
8. Abstain if no candidate reaches the grounding threshold.

The diagnosis must explain not only what is wrong, but why the reasoning broke at a particular dependency or misconception.

## 10. Scope Boundaries for Feedback

The feedback layer should be limited to the graph-backed diagnosis.

Allowed:

- naming the missing concept
- naming the prerequisite that was not mastered
- naming the misconception pattern
- pointing to source-backed evidence
- explaining the minimal correction path

Not allowed:

- speculative psychoanalysis of the student
- unsupported claims about motivation or effort
- invented pedagogical history
- explanations that contradict the graph

## 11. Acceptance Criteria

### 11.1 Graph coverage

- Every syllabus leaf node must map to at least one `Concept`.
- Every `Concept` must have at least one provenance-bearing `EvidenceArtifact`.
- Every `Concept` that depends on another concept must have at least one outgoing `PrerequisiteEdge`.
- Every curated misconception must map to at least one concept or skill.

### 11.2 Structural correctness

- The syllabus hierarchy must be navigable from root to leaf without orphan nodes.
- The prerequisite graph must be machine-checkable for direction and cycle constraints.
- Community partitions must cover the entire graph with no uncovered nodes at the selected partition level.
- Community summaries must be regenerable from graph state alone.

### 11.3 Diagnostic correctness

- For a curated test set of student answers with known root causes, the system must identify the correct primary concept gap for the majority of cases defined by the test suite.
- For responses that match a known misconception, the system must return the matching misconception id or an explicitly ranked candidate list.
- Every non-abstaining diagnosis must include at least one supporting evidence reference.
- If no grounded diagnosis exists, the system must abstain instead of guessing.

### 11.4 Explainability

- The final feedback must include the diagnosis path in human-readable form.
- A reviewer must be able to trace the feedback back to specific graph nodes and evidence artifacts.
- The explanation must distinguish between a concept gap, a prerequisite gap, and a misconception when possible.

### 11.5 Stability

- Re-running diagnosis against the same graph version and same student response must produce the same structured diagnosis, aside from controlled nondeterminism in text phrasing.
- A graph version change must invalidate or re-tag dependent community summaries and diagnostic outputs.

### 11.6 Operational behavior

- The system must use precomputed community summaries at query time rather than regenerating summaries from raw source content.
- The diagnostic path must be derivable without scanning the entire graph indiscriminately.

## 12. Open Questions

- What is the canonical syllabus source for the first release?
- Which exam variants are in scope first: JEE Main, JEE Advanced, or a custom internal syllabus?
- How should the system represent multiple valid solution paths to the same answer?
- What confidence threshold should trigger abstention?
- Which misconception types must be curated manually versus inferred from historical errors?
- How should contradictory evidence be handled when different sources disagree?

## 13. Reference Basis

This spec borrows the indexing and retrieval pattern from GraphRAG:

- build a graph from source documents
- partition the graph into hierarchical communities
- precompute summaries for those communities
- answer queries by combining relevant community summaries

The key adaptation for this project is that the graph is not used to summarize an arbitrary corpus. It is used to provide a rigid curriculum diagnosis layer for grading and feedback.
