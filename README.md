# knowledge-graph

Local-first knowledge graph pipeline for curriculum diagnosis.

## Getting started

```powershell
poetry install
poetry run knowledge-graph --show-config
```

## Project Shape

- Local extraction and graph construction run on the developer machine.
- Canonical graph metadata is persisted in AWS DynamoDB; full graph snapshots are stored in S3.
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
from knowledge_graph.ingestion.physics_corpus import build_physics_seed_bundle

seed_bundle = build_physics_seed_bundle(Path(r"C:\Users\Saurabh\Downloads\physics"))
```

The importer uses the structured text outputs in that folder first and will skip unreadable PDFs in environments where the local PDF toolchain is blocked.

Build the complete graph, communities, summaries, manifest, and local JSON snapshot:

```powershell
$env:PYTHONPATH = "src"
python -m knowledge_graph.main build `
  --source-root "C:\Users\Saurabh\Downloads\physics" `
  --graph-version physics-v1
```

Validate or inspect the persisted graph:

```powershell
python -m knowledge_graph.main validate --graph-version physics-v1
python -m knowledge_graph.main show --graph-version physics-v1
```

Local output is written under `data/graph/` and `data/manifests/`. A checked-in
release snapshot is stored under `release/` for the CD pipeline. To persist the
same validated snapshot to AWS, add `--backend dynamodb` after applying the
Terraform stack and configuring AWS credentials. The DynamoDB item stores
snapshot metadata, counts, checksum, indexes, and the S3 pointer; the full
snapshot JSON is written to S3.

When the corpus contains `RefrenceBook_HCVERMA`, `RefrenceBook_NCERT`, and
`syllabus` folders, the build adds compact textbook evidence to concepts and
skills. Evidence authority is ranked as HC Verma, JEE syllabus, past papers,
then NCERT. Past papers remain authoritative for assessment prompts and
misconceptions.

The graph builder seeds canonical JEE Physics coverage before adding
question-derived links, so the persisted snapshot includes the hierarchy
`Physics -> chapter -> topic -> concept -> subconcept -> microconcept`.
Syllabus and reference books are treated as primary sources for the learning
hierarchy. PYQ prompts and worked solutions are used for assessment items,
misconception signals, and corrective actions.

The DynamoDB row intentionally stores compact metadata and S3 pointers. The
full normalized graph JSON is stored in S3, and a denormalized agent-view JSON
is written next to it for label-rich traversal. The normalized graph uses IDs
for edges; the agent view resolves those IDs into labels, syllabus paths,
misconception mappings, and corrective actions.

For structured PYQ corpora, the build also renders each question region from
its source PDF into `data/work/visual/<graph-version>/`. These crops preserve
diagrams, graphs, circuits, equations, and visual answer options. Every crop is
checksum-addressed and linked to its assessment item with PDF page and bounding
box provenance.

Generate structured semantic interpretations locally through Codex:

```powershell
$env:PYTHONPATH = "src"
python -m knowledge_graph.main interpret-visual `
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
python -m knowledge_graph.main visualize `
  --graph-version physics-v4
```

The exporter writes HTML, SVG, and JSON artifacts under
`visualizations/<graph-version>/`. The HTML view includes the community
backbone, a concept drilldown panel, and a community prerequisite matrix.

To persist the checked-in release snapshot to the configured DynamoDB table:

```powershell
$env:PYTHONPATH = "src"
$env:JEE_RAG_DYNAMODB_TABLE = "knowledge-graph-dev"
$env:JEE_RAG_SNAPSHOT_BUCKET = "knowledge-graph-dev-snapshots-<aws-account-id>"
python -m knowledge_graph.main persist-snapshot `
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
4. Store graph snapshot metadata, summaries, and diagnostics in DynamoDB.
5. Store full graph snapshot JSON objects in S3.
6. For release builds, persist the checked-in snapshot from `release/` after Terraform apply.

The CD workflow expects these GitHub repository variables/secrets:

- `secrets.AWS_ROLE_ARN`: set this to the Terraform output `github_actions_role_arn`.
- `vars.AWS_REGION`: optional, defaults to `ap-south-1`.
- `vars.TF_STATE_BUCKET`: optional remote Terraform state bucket, defaults to `knowledge-graph-terraform-state-bucket`.
- `vars.TF_STATE_KEY`: optional remote Terraform state key, defaults to `knowledge-graph/terraform.tfstate`.
- `vars.TF_STATE_DYNAMODB_TABLE`: optional remote Terraform lock table, defaults to `knowledge-graph-terraform-lock`.

The Terraform lock table must use a string partition key named `LockID`.
If Terraform reports a missing key named `Key` or a schema mismatch while
locking state, the configured lock table was created with the wrong key schema.
Create or recreate `knowledge-graph-terraform-lock` with partition key `LockID`,
or point `TF_STATE_DYNAMODB_TABLE` to the bootstrap output
`state_lock_table_name`.

The main Terraform stack reuses the account-level GitHub Actions OIDC provider
for `https://token.actions.githubusercontent.com`. If the account does not have
that provider yet, create it once before applying the main stack.

After `terraform apply`, the workflow reads `dynamodb_table_name` and
`snapshot_bucket_name` from Terraform outputs and passes them as
`JEE_RAG_DYNAMODB_TABLE` and `JEE_RAG_SNAPSHOT_BUCKET` to the persistence step.
The workflow passes Terraform's required `github_repository` input from
`${{ github.repository }}`.

## Terraform bootstrap

The bootstrap stack creates the S3 bucket and DynamoDB lock table used by the main Terraform stack for remote state.

```powershell
cd terraform/bootstrap
terraform init
terraform apply
```

Provide `state_bucket_name` through `terraform.tfvars` or `-var` before applying, and make sure the bucket name is globally unique.

