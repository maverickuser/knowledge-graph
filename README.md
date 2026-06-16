# knowledge-graph

Local-first knowledge graph pipeline for curriculum diagnosis.

## Getting started

```powershell
poetry install
poetry run knowledge-graph --show-config
```

## Project Shape

- Local extraction and graph construction run on the developer machine.
- Canonical graph state is persisted in AWS DynamoDB.
- Terraform provisions the AWS table and GitHub Actions access role.
- GitHub Actions runs unit tests, integration tests, and Terraform validation.

## Local workflow

1. Place source material under `data/raw/`.
2. Run extraction and normalization locally.
3. Build the graph and summaries locally.
4. Persist the graph snapshot through the repository layer.

If you already have a local corpus folder, you can build a seed bundle directly from it:

```python
from pathlib import Path
from jee_rag_knowledge_graph.ingestion.physics_corpus import build_physics_seed_bundle

seed_bundle = build_physics_seed_bundle(Path(r"C:\Users\Saurabh\Downloads\physics"))
```

The importer uses the structured text outputs in that folder first and will skip unreadable PDFs in environments where the local PDF toolchain is blocked.

Build the complete graph, communities, summaries, manifest, and local JSON snapshot:

```powershell
$env:PYTHONPATH = "src"
python -m jee_rag_knowledge_graph.main build `
  --source-root "C:\Users\Saurabh\Downloads\physics" `
  --graph-version physics-v1
```

Validate or inspect the persisted graph:

```powershell
python -m jee_rag_knowledge_graph.main validate --graph-version physics-v1
python -m jee_rag_knowledge_graph.main show --graph-version physics-v1
```

Local output is written under `data/graph/` and `data/manifests/`. A checked-in
release snapshot is stored under `release/` for the CD pipeline. To persist the
same validated snapshot to the configured DynamoDB table, add
`--backend dynamodb` after applying the Terraform stack and configuring AWS
credentials.

When the corpus contains `RefrenceBook_HCVERMA`, `RefrenceBook_NCERT`, and
`syllabus` folders, the build adds compact textbook evidence to concepts and
skills. Evidence authority is ranked as HC Verma, JEE syllabus, past papers,
then NCERT. Past papers remain authoritative for assessment prompts and
misconceptions.

For structured PYQ corpora, the build also renders each question region from
its source PDF into `data/work/visual/<graph-version>/`. These crops preserve
diagrams, graphs, circuits, equations, and visual answer options. Every crop is
checksum-addressed and linked to its assessment item with PDF page and bounding
box provenance.

Generate structured semantic interpretations locally through Codex:

```powershell
$env:PYTHONPATH = "src"
python -m jee_rag_knowledge_graph.main interpret-visual `
  --graph-version physics-v4
```

Use `--dry-run`, `--limit`, or repeated `--question-id` arguments before a full
run. Responses are cached under `data/work/visual-interpretations/`. The model
returns a strict schema containing diagram type, entities, relationships,
equations, answer-relevant observations, ambiguities, confidence, and review
state.

Codex is the default provider and uses the locally authenticated Codex CLI with
read-only sandboxing. `--provider openai` remains available for direct API use.

Export a project-local visualization of the current graph snapshot:

```powershell
$env:PYTHONPATH = "src"
python -m jee_rag_knowledge_graph.main visualize `
  --graph-version physics-v4
```

The exporter writes HTML, SVG, and JSON artifacts under
`visualizations/<graph-version>/`. The HTML view includes the community
backbone, a concept drilldown panel, and a community prerequisite matrix.

To persist the checked-in release snapshot to the configured DynamoDB table:

```powershell
$env:PYTHONPATH = "src"
python -m jee_rag_knowledge_graph.main persist-snapshot `
  --snapshot-path release/physics-v4.snapshot.json `
  --backend dynamodb
```

## Hardening checks

The repo includes a curated evaluation fixture set, determinism checks, and
lightweight performance sanity checks under `tests/`.

Run the full suite locally with:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover tests -v
```

The hardening tests cover:

- supported diagnosis cases
- abstention cases
- visual-interpretation abstention
- repeated-build determinism over the same inputs
- basic build and diagnosis performance budgets

## AWS workflow

1. Bootstrap the remote state bucket and lock table once from `terraform/bootstrap/`.
2. Run `terraform init`, `terraform plan`, and `terraform apply` from `terraform/` with the S3 backend configured.
3. Use the GitHub Actions OIDC role for CI/CD access.
4. Store graph snapshots, summaries, and diagnostics in DynamoDB.
5. For release builds, persist the checked-in snapshot from `release/` after Terraform apply.

## Terraform bootstrap

The bootstrap stack creates the S3 bucket and DynamoDB lock table used by the main Terraform stack for remote state.

```powershell
cd terraform/bootstrap
terraform init
terraform apply
```

Provide `state_bucket_name` through `terraform.tfvars` or `-var` before applying, and make sure the bucket name is globally unique.
