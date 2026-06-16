# Diagnostic Knowledge Graph Implementation Plan

- Status: Draft
- Date: 2026-06-10
- Scope base: [Diagnostic Knowledge Graph Spec](./diagnostic-knowledge-graph-spec.md)

## 1. Objective

Implement a syllabus-grounded knowledge graph that supports grounded grading and feedback for student answer sheets.

The implementation must:

- encode syllabus structure, concepts, skills, prerequisites, and misconceptions
- build hierarchical communities for retrieval
- precompute community summaries
- support query-time diagnosis with explicit evidence
- abstain when grounding is insufficient
- persist the canonical graph in AWS DynamoDB
- keep source extraction and graph construction local
- provision the AWS infrastructure with Terraform
- validate and deliver changes through GitHub Actions

This plan assumes the GraphRAG pattern referenced in the spec: local graph evidence is organized into hierarchical communities and summarized before query time.

## 2. Delivery Strategy

The work should be delivered in stages so each layer can be validated before the next layer depends on it.

Recommended order:

1. Define the canonical data model and invariants.
2. Implement persistence and repository abstractions.
3. Implement syllabus ingestion and normalization.
4. Build the prerequisite graph and misconception mapping.
5. Build community partitioning and summary generation.
6. Implement query-time diagnosis and abstention logic.
7. Add regression tests and evaluation fixtures.
8. Harden for versioning, provenance, and reproducibility.

## 3. High-Level Design

### 3.1 System overview

The system is a pipeline with five major layers:

1. Ingestion layer
2. Graph construction layer
3. Community and summary layer
4. Diagnostic retrieval layer
5. Feedback rendering layer

Each layer should have a clear input and output contract so that graph content, summaries, and diagnosis results can be validated independently.

### 3.2 Components

#### A. Ingestion and normalization

Responsibilities:

- load approved local syllabus, rubric, and misconception source bundles
- normalize terminology into canonical concept and skill names
- extract provenance-bearing evidence records
- resolve aliases to canonical IDs
- operate without network access in the extraction path

Outputs:

- `SyllabusNode` records
- `Concept` records
- `Skill` records
- `EvidenceArtifact` records
- `AssessmentItem` records
- `GraphSeedBundle` for the graph construction layer

#### B. Graph builder

Responsibilities:

- create node records
- create prerequisite edges
- connect concepts to syllabus structure
- map misconceptions to concepts and skills
- validate invariants such as edge direction and acyclicity

Outputs:

- a versioned knowledge graph
- validation reports

#### C. Community partitioner

Responsibilities:

- group related nodes into communities
- produce hierarchical clusters
- ensure leaf-to-root community coverage

Outputs:

- `Community` records
- hierarchy metadata

#### D. Summary generator

Responsibilities:

- summarize each community from graph content
- identify salient concepts, prerequisites, and misconceptions
- store versioned `CommunitySummary` artifacts

Outputs:

- `CommunitySummary` records

#### E. Diagnostic engine

Responsibilities:

- resolve a student response to relevant graph areas
- compare response signals to prerequisite failures and misconception patterns
- rank candidate diagnoses
- emit grounded diagnostic records
- abstain if evidence is weak or missing

Outputs:

- `DiagnosticRecord` records
- human-readable feedback text

### 3.3 Runtime data flow

1. A student response and assessment item enter the diagnostic engine.
2. The engine identifies relevant communities using the assessment item and response features.
3. It retrieves the precomputed summaries for those communities.
4. It walks prerequisite chains to find the earliest missing dependency.
5. It compares the response against known misconception patterns.
6. It ranks candidate causes using evidence strength and coverage.
7. It emits a structured diagnosis and feedback.
8. If no grounded path exists, it abstains.

### 3.4 Deployment shape

For the current repository size, the implementation can remain a single Python package with separable modules.

Recommended deployment units:

- library code in `src/jee_rag_knowledge_graph`
- tests in `tests`
- spec artifacts in `.specify`
- terraform infrastructure in `terraform`
- CI/CD workflows in `.github/workflows`

The repository abstraction should hide storage details, but the production backend is DynamoDB. Local in-memory and JSON adapters remain useful for tests and local workflows.

The extraction layer should remain local-first: it reads only from approved workspace paths and writes graph seed artifacts locally before graph construction begins.

The graph construction layer should also run locally when building or refreshing graph snapshots. Only the persisted operational graph and its derived artifacts are stored in AWS.

### 3.5 Persistence and delivery model

The system should treat local processing and AWS persistence as separate boundaries.

Local workflow:

- source extraction and normalization happen on the local machine
- graph construction and review happen locally
- reviewed graph snapshots are emitted as versioned build artifacts

AWS workflow:

- DynamoDB stores the canonical graph, communities, summaries, and diagnostic records
- Terraform provisions the AWS resources needed for the persistence layer and deployment access
- GitHub Actions validates code and infrastructure changes before deployment

Recommended AWS infrastructure:

- a DynamoDB table or small table set for graph entities, edges, summaries, and diagnostics
- AWS IAM roles and policies for GitHub Actions via OIDC
- optional S3 backend for Terraform state if remote state is adopted
- encryption at rest and point-in-time recovery for production tables

## 4. Low-Level Design

### 4.1 Package structure

Recommended module layout:

- `src/jee_rag_knowledge_graph/__init__.py`
- `src/jee_rag_knowledge_graph/main.py`
- `src/jee_rag_knowledge_graph/config.py`
- `src/jee_rag_knowledge_graph/domain/models.py`
- `src/jee_rag_knowledge_graph/domain/validation.py`
- `src/jee_rag_knowledge_graph/ingestion/normalize.py`
- `src/jee_rag_knowledge_graph/ingestion/loaders.py`
- `src/jee_rag_knowledge_graph/graph/build.py`
- `src/jee_rag_knowledge_graph/graph/validate.py`
- `src/jee_rag_knowledge_graph/community/partition.py`
- `src/jee_rag_knowledge_graph/community/summarize.py`
- `src/jee_rag_knowledge_graph/diagnosis/retrieve.py`
- `src/jee_rag_knowledge_graph/diagnosis/rank.py`
- `src/jee_rag_knowledge_graph/diagnosis/abstain.py`
- `src/jee_rag_knowledge_graph/output/format.py`
- `src/jee_rag_knowledge_graph/storage/repository.py`
- `src/jee_rag_knowledge_graph/storage/memory.py`
- `src/jee_rag_knowledge_graph/storage/json.py`
- `src/jee_rag_knowledge_graph/storage/dynamodb.py`

This layout keeps concerns isolated and makes unit testing easier.

### 4.2 Core algorithms

#### A. Concept normalization

Input:

- raw syllabus strings
- rubric text
- misconception descriptions

Process:

- lowercase and trim where safe
- map synonyms to canonical concepts
- assign stable IDs
- attach provenance references

Output:

- canonical `Concept` and `Skill` objects

#### B. Prerequisite graph construction

Input:

- normalized concept and skill records
- explicit prerequisite statements
- curriculum ordering hints

Process:

- create directed prerequisite edges from prerequisite to dependent node
- validate edge direction
- detect cycles
- flag uncertain edges for review

Output:

- validated prerequisite graph

#### C. Community partitioning

Input:

- validated graph

Process:

- cluster related nodes by syllabus locality and dependency density
- create a multi-level hierarchy
- ensure each node belongs to at least one relevant community

Output:

- hierarchical community tree

#### D. Summary generation

Input:

- community membership
- node metadata
- prerequisite chains
- misconception mappings

Process:

- select salient concepts and bottlenecks
- compose concise summaries from graph state
- store evidence references used in the summary

Output:

- versioned community summaries

#### E. Diagnosis ranking

Input:

- assessment item
- student response
- relevant community summaries

Process:

- identify candidate primary gaps
- score prerequisite failures
- score misconception matches
- compare evidence coverage
- apply abstention threshold

Output:

- ranked diagnosis candidates or abstention

#### F. DynamoDB persistence

Input:

- reviewed graph snapshots
- community summaries
- diagnostic records

Process:

- write versioned graph items through the repository abstraction
- preserve prior versions for auditability
- expose query-friendly access patterns through partition and sort keys
- use secondary indexes only where they simplify retrieval without breaking version integrity

Output:

- persisted DynamoDB graph state

#### G. Terraform provisioning

Input:

- infrastructure definitions
- environment configuration

Process:

- define DynamoDB tables, IAM roles, and optional state storage
- keep deployment resources reproducible and reviewable
- validate infrastructure changes before apply

Output:

- provisioned AWS infrastructure

#### H. GitHub Actions CI/CD

Input:

- source changes
- test fixtures
- Terraform configuration

Process:

- run formatting and lint checks
- run unit tests
- run integration tests
- run Terraform fmt and validate
- publish plans for review and apply approved infrastructure changes on protected branches

Output:

- verified code and infrastructure changes

### 4.3 Error handling

The system should distinguish between these failure classes:

- missing source data
- invalid graph structure
- unsupported diagnosis
- summary generation failure
- version mismatch

Each failure should produce a deterministic error type and a clear message.

### 4.4 Versioning rules

Every persisted object must carry a version reference.

Rules:

- graph objects and summaries are versioned together
- a changed concept definition invalidates dependent summaries
- a changed prerequisite edge may invalidate community partitioning
- diagnosis outputs must reference the graph version they were produced against

### 4.5 Determinism rules

Where practical, the implementation should be deterministic:

- stable IDs
- stable ordering of nodes in summaries
- stable ranking tie-breakers
- stable serialization format

This is important for regression testing and for reproducible grading behavior.

## 5. Data Model

### 5.1 Entity model

The implementation should support these persisted entities:

| Entity | Purpose | Key fields |
| --- | --- | --- |
| `SyllabusNode` | Curriculum container | `id`, `title`, `level`, `parent_id`, `order_index`, `source_ref`, `version` |
| `Concept` | Atomic knowledge unit | `id`, `canonical_name`, `definition`, `subject`, `grade_band`, `aliases`, `source_refs`, `version` |
| `Skill` | Procedural competency | `id`, `canonical_name`, `success_criteria`, `source_refs`, `version` |
| `PrerequisiteEdge` | Dependency relation | `from_id`, `to_id`, `relation_type`, `strength`, `rationale`, `source_refs`, `version` |
| `Misconception` | Known wrong reasoning pattern | `id`, `label`, `description`, `trigger_patterns`, `diagnostic_signals`, `remediation_hint`, `source_refs`, `version` |
| `EvidenceArtifact` | Source-backed evidence | `id`, `artifact_type`, `locator`, `excerpt`, `source_system`, `timestamp`, `version` |
| `AssessmentItem` | Question or prompt | `id`, `prompt`, `expected_concepts`, `expected_steps`, `rubric_ref`, `version` |
| `Community` | Retrieval cluster | `id`, `level`, `parent_id`, `member_ids`, `theme`, `version` |
| `CommunitySummary` | Precomputed community digest | `id`, `community_id`, `summary_text`, `salient_concepts`, `salient_prereqs`, `salient_misconceptions`, `evidence_refs`, `generated_at`, `version` |
| `DiagnosticRecord` | Structured runtime diagnosis | `id`, `assessment_item_id`, `student_response_id`, `primary_gap`, `prerequisite_chain`, `misconception_match`, `evidence_refs`, `confidence`, `abstained`, `version` |

### 5.2 Relationship model

Supported relationships should include:

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

### 5.3 Validation invariants

The following invariants should be enforced in code:

- every `Concept` has a canonical definition and at least one provenance reference
- every `Concept` belongs to a syllabus node
- every prerequisite edge points from prerequisite to dependent node
- prerequisite cycles are rejected unless explicitly modeled as cross-links
- every `Misconception` maps to at least one concept or skill
- every `CommunitySummary` only references members inside its community
- every `DiagnosticRecord` has evidence references or explicit abstention

### 5.4 Suggested persistence format

Phase 1 should use a simple local persistence format to keep development fast:

- JSON files for seed data and fixtures
- in-memory repository for unit tests
- optional SQLite adapter for persistence tests

This keeps the project lightweight while allowing future migration to a graph database.

## 6. Implementation Phases

### Phase 0: Project scaffold

Deliverables:

- package skeleton under `src/jee_rag_knowledge_graph`
- base test harness
- configuration entry points
- repository abstraction

Exit criteria:

- project runs locally
- tests execute in CI or local equivalent

### Phase 1: Domain model and validation

Deliverables:

- dataclasses or Pydantic-style domain objects
- invariant validation utilities
- stable ID and version conventions

Exit criteria:

- model objects serialize and validate correctly
- invalid graph structures are rejected by tests

### Phase 2: Ingestion and normalization

Deliverables:

- source loaders
- normalization rules
- alias resolution
- provenance capture

Exit criteria:

- raw syllabus and misconception inputs produce canonical domain objects
- provenance survives round-trip serialization

### Phase 3: Graph construction

Deliverables:

- graph builder
- prerequisite edge construction
- cycle detection
- graph validation report

Exit criteria:

- a valid graph can be built from curated fixtures
- invalid graphs fail closed

### Phase 4: Community partitioning and summaries

Deliverables:

- community partition algorithm
- summary generation pipeline
- summary regeneration from graph state

Exit criteria:

- every node is covered by a community partition at the chosen level
- summaries are reproducible and versioned

### Phase 5: Diagnostic engine

Deliverables:

- retrieval of relevant communities
- prerequisite tracing
- misconception matching
- candidate ranking
- abstention logic

Exit criteria:

- curated answer fixtures produce grounded diagnoses
- unsupported cases abstain

### Phase 6: Output formatting

Deliverables:

- structured diagnostic record serializer
- human-readable feedback formatter
- traceability fields in the output

Exit criteria:

- every diagnosis can be rendered as both machine-readable and human-readable output

### Phase 7: Evaluation and regression tests

Deliverables:

- fixture set of known answers and expected diagnoses
- regression tests for abstention and grounding
- versioning and determinism tests

Exit criteria:

- acceptance criteria in the spec are covered by automated tests

### Phase 8: Hardening

Deliverables:

- logging and metrics
- performance checks for hot paths
- caching for summaries and retrieval

Exit criteria:

- implementation is stable enough for iterative subject expansion

## 7. Test Plan

### 7.1 Unit tests

Cover:

- ID generation
- alias resolution
- node and edge validation
- cycle detection
- summary serialization
- abstention logic

### 7.2 Integration tests

Cover:

- loading a full fixture syllabus
- building the graph
- partitioning communities
- generating summaries
- diagnosing a sample answer

### 7.3 Regression tests

Cover:

- a known misconception mapped to the correct diagnosis
- a prerequisite failure mapped to the right chain
- unsupported answers that must abstain

### 7.4 Determinism tests

Cover:

- repeated runs over the same inputs produce the same structured outputs
- version changes invalidate dependent summaries as expected

## 8. Risks and Mitigations

### Risk: ambiguous prerequisite chains

Mitigation:

- store edge confidence or strength
- allow multiple candidate chains
- require abstention when evidence is weak

### Risk: summary drift from graph truth

Mitigation:

- regenerate summaries from graph state only
- tie summaries to graph version

### Risk: overconfident hallucinated diagnosis

Mitigation:

- enforce fail-closed abstention
- require evidence references for every non-abstaining record

### Risk: schema changes breaking diagnostics

Mitigation:

- version all persisted records
- add migration tests

## 9. Definition of Done

The implementation is complete when:

- the graph model is implemented and validated
- community partitioning and summaries are generated from graph data
- diagnosis returns grounded structured records
- abstention works for unsupported cases
- acceptance criteria are encoded as automated tests
- all persisted artifacts are versioned and traceable

## 10. Immediate Next Actions

1. Implement the domain model and validation layer.
2. Add repository abstractions and fixture loading.
3. Build graph construction and invariant checks.
4. Add community partitioning and summary generation.
5. Implement diagnosis and abstention logic.
6. Add integration tests around the full pipeline.
