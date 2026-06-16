# Local Data Extraction Process

- Status: Draft
- Date: 2026-06-10
- Scope base: [Diagnostic Knowledge Graph Spec](./diagnostic-knowledge-graph-spec.md)
- Design basis: [GraphRAG / arXiv:2404.16130](https://arxiv.org/pdf/2404.16130)

## 1. Purpose

This document defines the local, offline extraction pipeline that converts approved source material into canonical graph seed artifacts used to build the knowledge graph.

The extraction process must produce grounded, versioned, provenance-bearing data. It must not invent concepts or relations that are not supported by the source material.

## 2. Local Execution Model

### 2.1 Local-only inputs

- All inputs must already exist on the local filesystem.
- Paths must resolve to approved workspace roots or repository-relative directories.
- Remote URLs, cloud buckets, live APIs, and database-backed reads are out of scope for the extraction path.
- If OCR or ML assistance is used, it must run locally with pinned local assets or binaries.

### 2.2 Deterministic processing

- The same source files, build configuration, and extraction version must produce the same outputs.
- Stable source checksums, stable IDs, and stable ordering are required.
- Non-deterministic ranking or generation must be avoided in the extraction stage.

### 2.3 Build boundary

- Extraction produces graph seed artifacts.
- Graph construction consumes those seed artifacts and does not read raw source documents directly.
- Community partitioning and summaries are generated from the built graph, not from raw source content.

## 3. Source Types

The extraction pipeline should support the following local inputs:

- syllabus documents
- chapter and topic outlines
- textbook or reference content
- official rubrics and marking schemes
- worked examples and solution outlines
- curated misconception notes
- historical incorrect-answer examples, if available and approved, stored locally

Accepted file formats may include PDF, DOCX, HTML, markdown, TXT, JSON, and CSV when supported by the local extractor.

Student answer sheets are not part of the graph build pipeline. They are used later at query time for diagnosis. Only aggregated patterns from prior answers should be considered for misconception extraction, and only if the project explicitly enables that source.

## 4. Extraction Outputs

The pipeline should produce these canonical artifacts:

- `SyllabusNode`
- `Concept`
- `Skill`
- `PrerequisiteEdge`
- `Misconception`
- `EvidenceArtifact`
- `AssessmentItem`
- `Community`
- `CommunitySummary`
- `GraphSeedBundle`

Every output object must carry:

- a stable canonical id
- a source reference
- a version
- an extraction confidence or review state where applicable

### 4.1 Recommended local artifact layout

The implementation should use a local workspace layout similar to the following:

- `data/raw/` for original source files
- `data/work/normalized/` for normalized text and structure
- `data/work/segments/` for chunked document segments
- `data/work/extracted/` for extracted entity and relation candidates
- `data/work/review/` for review queues and decisions
- `data/manifests/` for source and build manifests
- `data/graph/` for graph build outputs and snapshots

## 5. Extraction Pipeline

### 5.1 Source intake

Goal:

- register the local source and assign source-level metadata

Actions:

- record source file name, local path, type, and version
- capture publication metadata where available
- generate a source checksum
- store the ingestion timestamp
- validate that the source path stays inside the approved workspace boundary
- record whether the source is fully local, locally mirrored, or manually curated

Output:

- source registry record

### 5.2 Document normalization

Goal:

- convert local source material into a consistent textual form

Actions:

- extract text from PDF, DOCX, HTML, markdown, TXT, JSON, or CSV when supported
- remove page headers, footers, and repeated boilerplate
- preserve section titles and structural markers
- retain page and section references for provenance
- use local OCR only if the source requires it and a local OCR engine is available

Output:

- normalized document representation with structural anchors

### 5.3 Structural segmentation

Goal:

- split the document into logical units that can be extracted independently

Actions:

- detect chapters, sections, subsections, examples, definitions, and exercises
- preserve parent-child structure
- assign chunk ids and offsets

Output:

- ordered document segments with hierarchy metadata

### 5.4 Entity extraction

Goal:

- identify candidate concepts, skills, assessment items, and misconceptions

Actions:

- extract noun phrases and definitional statements as concept candidates
- extract procedural verbs and success conditions as skill candidates
- extract question stems and rubric language as assessment item candidates
- extract repeated wrong-turn patterns as misconception candidates
- prefer explicit source evidence over inferred candidates
- mark weak candidates for review instead of promoting them automatically

Output:

- candidate entity records with confidence scores

### 5.5 Relation extraction

Goal:

- identify structured relationships between extracted entities

Actions:

- infer containment from document structure
- infer prerequisites from explicit wording and curriculum order
- infer `maps_to` links between misconceptions and concepts
- infer `confused_with` links where wrong patterns consistently overlap

Output:

- candidate edge records with evidence spans

### 5.6 Canonicalization and deduplication

Goal:

- merge duplicate or near-duplicate entities into a single canonical node

Actions:

- normalize surface forms
- map aliases to canonical ids
- merge semantically identical concept candidates
- reject duplicates that are only lexical variants

Output:

- canonical entities with alias sets

### 5.7 Provenance binding

Goal:

- ensure every extracted object is traceable to a source span

Actions:

- attach source document id
- attach section, page, or offset references
- store an excerpt or locator for review
- preserve extraction method metadata

Output:

- provenance-bearing graph objects

### 5.8 Confidence scoring

Goal:

- decide whether an extracted object can be auto-accepted, queued for review, or rejected

Actions:

- score extraction confidence based on evidence strength
- boost explicit definitions and explicit prerequisite statements
- penalize weakly supported or ambiguous relations

Suggested states:

- `accepted`
- `needs_review`
- `rejected`

### 5.9 Human review gate

Goal:

- prevent unsupported concepts, edges, or misconceptions from entering the canonical graph

Actions:

- review low-confidence entities and relations
- approve or reject ambiguous prerequisites
- verify misconception-to-concept mappings
- resolve conflicts between sources

Output:

- reviewed canonical graph updates

### 5.10 Persistence and versioning

Goal:

- store extracted data in a reproducible, versioned form

Actions:

- write entities and edges with graph version tags
- invalidate dependent summaries when canonical nodes change
- keep prior versions for audit and rollback

Output:

- versioned graph snapshot

### 5.11 Graph build handoff

Goal:

- package reviewed local extraction outputs for graph construction

Actions:

- serialize accepted entities, edges, evidence, and review state into a `GraphSeedBundle`
- include source checksums, extraction version, and graph version in the build manifest
- ensure the graph builder can consume the bundle without rereading raw documents
- fail closed if the bundle is incomplete or if provenance links are missing

Output:

- local graph seed bundle ready for graph construction

## 6. Entity-Specific Extraction Rules

### 6.1 SyllabusNode

Extract from:

- chapter headings
- unit headings
- topic trees
- table of contents

Rules:

- preserve ordering from the source
- keep parent-child containment explicit
- do not infer absent hierarchy levels unless supported by source structure

### 6.2 Concept

Extract from:

- definitions
- repeated technical terms
- named ideas in explanations
- learning objectives

Rules:

- each concept must have a canonical name and definition
- a concept should represent one atomic learning unit
- avoid combining multiple ideas into one node

### 6.3 Skill

Extract from:

- procedural instructions
- worked solution steps
- rubric criteria
- command words such as "derive", "simplify", "prove"

Rules:

- distinguish knowledge from execution
- attach success criteria where possible
- keep skills separate from the concepts they depend on

### 6.4 PrerequisiteEdge

Extract from:

- explicit prerequisite language
- dependency chains in solved examples
- syllabus ordering where clearly justified

Rules:

- edge direction must be prerequisite to dependent node
- explicit source support is preferred over inferred support
- cycles require review unless cross-links are intentionally modeled

### 6.5 Misconception

Extract from:

- official misconception lists
- recurring wrong-answer patterns
- annotated solution errors

Rules:

- each misconception must map to at least one concept or skill
- the misconception should describe the wrong reasoning, not just the wrong answer
- unsupported speculation must be excluded

### 6.6 EvidenceArtifact

Extract from:

- source document spans
- rubric lines
- worked example passages

Rules:

- store the locator, excerpt, and source metadata
- keep evidence as the grounding layer for downstream diagnosis

### 6.7 AssessmentItem

Extract from:

- exam prompts
- textbook exercises
- rubric-aligned tasks

Rules:

- capture expected concepts and expected steps
- link the item to the graph nodes it is designed to assess

## 7. GraphRAG Alignment

The extraction pipeline should mirror the GraphRAG pattern in a subject-specific way:

1. Extract structured entities and relations from source documents.
2. Build a graph from those entities and relations.
3. Partition the graph into hierarchical communities.
4. Summarize each community.
5. Use the summaries for query-time diagnosis.

The important adaptation is that the graph is not a general document index. It is a curriculum diagnosis structure, so extraction must preserve educational meaning and dependency structure. The raw source files are only used in the local extraction stage; the graph builder and downstream diagnosis stages operate on graph artifacts.

## 8. Quality Gates

The pipeline should reject or flag data when:

- a concept has no provenance
- a prerequisite edge has no evidence span
- a misconception is not linked to a concept or skill
- a source section is too ambiguous to canonicalize safely
- a node conflicts with an existing canonical definition
- a source path escapes the approved local workspace
- an extraction step attempts to use a remote dependency or network resource

The pipeline should also verify:

- every graph object has a version
- every accepted entity can be traced to source evidence
- every summary can be regenerated from graph state alone

## 9. Incremental Update Strategy

The extraction pipeline should support incremental updates instead of rebuilding everything on every change.

Recommended behavior:

- re-extract only changed source documents
- recanonicalize impacted entities
- invalidate dependent edges, communities, and summaries
- regenerate only affected summaries
- preserve prior graph versions for auditability
- use source checksums and build manifests to detect affected artifacts quickly

## 10. Minimal Example Flow

1. Ingest a syllabus PDF.
2. Normalize the text and detect chapter structure.
3. Extract concepts and skills from definitions and learning objectives.
4. Extract prerequisite links from explicit wording and worked examples.
5. Attach evidence spans to each extracted object.
6. Deduplicate aliases into canonical nodes.
7. Send uncertain items to human review.
8. Persist the reviewed graph version.
9. Generate communities and summaries from the accepted graph.

## 11. Acceptance Criteria

- raw local source documents can be converted into canonical entities, edges, and evidence
- every accepted entity is provenance-backed
- low-confidence objects are either reviewed or rejected
- graph updates are versioned and reproducible
- summary generation uses extracted graph state, not raw source re-reading at query time
- the resulting graph supports grounded diagnosis without unsupported inference
- the graph builder can build from the local `GraphSeedBundle` without touching raw source documents
- the full extraction pipeline can run on a disconnected machine with only local source files and local dependencies

## 12. Open Questions

- Which source types are authoritative for the first release?
- How much can be inferred from structure versus explicit text?
- What confidence threshold should trigger human review?
- Should misconception extraction be allowed from historical answers in phase 1?
- Which storage backend should be used for canonical graph persistence first?
- Will local OCR or local model assistance be part of the first release?
