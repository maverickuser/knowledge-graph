# Diagnostic Knowledge Graph Task List

- Status: Draft
- Date: 2026-06-10
- Source: [Diagnostic Knowledge Graph Implementation Plan](./diagnostic-knowledge-graph-implementation-plan.md)

## Execution Model

- Local work covers data extraction, normalization, graph construction, validation, and local test execution.
- AWS work covers DynamoDB persistence and the infrastructure needed to deploy and access it.
- Terraform owns AWS infrastructure provisioning.
- GitHub Actions owns CI and CD validation gates.

## Phase 0: Project Foundation

- [ ] Add a central config module for local paths, AWS region, DynamoDB table names, workflow names, and environment selection.
- [ ] Add package stubs for domain, ingestion, graph, community, diagnosis, storage, and output modules.
- [ ] Add fixture and working directories for raw sources, normalized text, extracted candidates, review artifacts, manifests, and graph snapshots.
- [ ] Add a base test harness that can run locally without AWS access.

## Phase 1: Domain Model and Validation

- [ ] Implement the canonical domain entities for syllabus nodes, concepts, skills, prerequisite edges, misconceptions, evidence artifacts, assessment items, communities, summaries, and diagnostic records.
- [ ] Implement stable ID and version conventions for all persisted entities.
- [ ] Implement validation rules for concept provenance, prerequisite direction, acyclicity, misconception mapping, and summary membership.
- [ ] Add serialization and round-trip tests for the domain models.

## Phase 2: Local Extraction Pipeline

- [ ] Implement source intake for local files with path validation, checksum generation, metadata capture, and source registry output.
- [ ] Implement document normalization for supported local formats, including PDF, DOCX, HTML, markdown, TXT, JSON, and CSV.
- [ ] Implement structural segmentation for chapters, sections, examples, definitions, and exercises.
- [ ] Implement entity extraction for concepts, skills, assessment items, and misconceptions.
- [ ] Implement relation extraction for containment, prerequisite links, `maps_to`, and `confused_with`.
- [ ] Implement canonicalization, alias resolution, and deduplication.
- [ ] Implement provenance binding for every extracted object.
- [ ] Implement confidence scoring and review state assignment.
- [ ] Implement `GraphSeedBundle` export so graph construction can run without rereading raw source files.

## Phase 3: Local Graph Construction

- [ ] Implement a graph builder that consumes `GraphSeedBundle` artifacts and produces validated graph snapshots.
- [ ] Implement prerequisite validation, including direction checks and cycle detection.
- [ ] Implement graph validation reports for accepted, reviewed, and rejected items.
- [ ] Implement local snapshot persistence for graph build outputs.
- [ ] Add integration tests that build a graph from curated local fixtures.

## Phase 4: Community Partitioning and Summaries

- [ ] Implement community partitioning based on syllabus locality and dependency density.
- [ ] Ensure every node is covered by at least one relevant community at the chosen partition level.
- [ ] Implement community summary generation from graph state only.
- [ ] Persist summaries with graph version tags and evidence references.
- [ ] Add regression tests that verify summaries are reproducible and version-aware.

## Phase 5: Diagnosis Engine

- [ ] Implement retrieval of relevant communities using the assessment item and response features.
- [ ] Implement prerequisite tracing to identify the earliest missing dependency.
- [ ] Implement misconception matching against curated patterns.
- [ ] Implement ranking logic for candidate diagnoses using evidence strength and coverage.
- [ ] Implement abstention logic for unsupported cases.
- [ ] Implement structured diagnostic record output and human-readable feedback formatting.
- [ ] Add regression tests for correct diagnoses, misconception matches, prerequisite gaps, and abstention.

## Phase 6: DynamoDB Persistence

- [ ] Define the DynamoDB key schema and access patterns for entities, edges, summaries, and diagnostic records.
- [ ] Implement the repository abstraction for production DynamoDB access.
- [ ] Implement versioned writes that preserve prior graph versions for auditability.
- [ ] Implement query methods for retrieval by graph version, community, assessment item, and diagnostic record.
- [ ] Implement local in-memory and JSON adapters for development and tests.
- [ ] Add persistence integration tests using a local DynamoDB-compatible test environment.

## Phase 7: Terraform Infrastructure

- [ ] Create Terraform provider and variable definitions for AWS region, environment, naming, and tags.
- [ ] Create Terraform resources for the DynamoDB tables needed by the graph store.
- [ ] Enable DynamoDB encryption at rest and point-in-time recovery for production tables.
- [ ] Create IAM roles and policies for application access and GitHub Actions OIDC access.
- [ ] Add Terraform outputs for table names, role ARNs, and deployment metadata.
- [ ] Add Terraform validation steps for formatting, planning, and linting.

## Phase 8: GitHub Actions CI/CD

- [ ] Add a workflow for formatting, linting, and unit tests.
- [ ] Add a workflow for integration tests, including local graph build and persistence checks.
- [ ] Add a workflow for Terraform fmt and validate.
- [ ] Add a workflow for Terraform plan on pull requests.
- [ ] Add a deployment workflow gated to protected branches or manual approval.
- [ ] Publish test and plan artifacts for review.

## Phase 9: Hardening and Release Readiness

- [ ] Update README and developer setup instructions for local extraction, local graph build, Terraform, and CI/CD.
- [ ] Add a curated evaluation fixture set for supported diagnoses and abstention cases.
- [ ] Add determinism tests for repeated runs on the same inputs and version.
- [ ] Add targeted performance checks for extraction, graph build, and retrieval hot paths.
- [ ] Review the full workflow end to end: local extraction, local graph build, DynamoDB persistence, CI validation, and deployment readiness.

## Recommended Order

1. Phase 0 and Phase 1 establish the codebase and data contracts.
2. Phase 2 and Phase 3 create the local extraction and graph build pipeline.
3. Phase 4 and Phase 5 make the graph useful for diagnosis.
4. Phase 6 and Phase 7 add AWS persistence and infrastructure.
5. Phase 8 and Phase 9 make the system deployable and maintainable.
