"""Command line entry point for local graph workflows."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from .config import load_app_config
from .domain.models import GraphSnapshot
from .pipeline import build_physics_graph, persist_local_graph, validate_local_graph
from .storage.dynamodb import DynamoDBKnowledgeGraphRepository
from .storage.json import JsonKnowledgeGraphRepository
from .visualization.export import export_graph_visualization
from .vision.interpret import (
    CodexCliVisionInterpreter,
    OpenAIResponsesVisionInterpreter,
    enrich_visual_interpretations,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="knowledge-graph")
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Print the resolved runtime configuration as JSON.",
    )
    subparsers = parser.add_subparsers(dest="command")

    build_command = subparsers.add_parser("build", help="Build and persist a Physics graph.")
    build_command.add_argument("--source-root", type=Path, required=True)
    build_command.add_argument("--graph-version", default="physics-v1")
    build_command.add_argument("--extraction-version", default="physics-extract-v1")
    build_command.add_argument(
        "--backend",
        choices=("json", "dynamodb"),
        default="json",
        help="Persistence backend. JSON artifacts are always written first.",
    )

    validate_command = subparsers.add_parser(
        "validate",
        help="Validate a persisted local graph snapshot.",
    )
    validate_command.add_argument("--graph-version", default="physics-v1")

    show_command = subparsers.add_parser("show", help="Show persisted graph statistics.")
    show_command.add_argument("--graph-version", default="physics-v1")

    persist_command = subparsers.add_parser(
        "persist-snapshot",
        help="Persist a checked-in graph snapshot to JSON storage or DynamoDB.",
    )
    persist_command.add_argument("--snapshot-path", type=Path, required=True)
    persist_command.add_argument(
        "--backend",
        choices=("json", "dynamodb"),
        default="dynamodb",
    )

    visualize_command = subparsers.add_parser(
        "visualize",
        help="Export a visual community/prerequisite representation of a graph snapshot.",
    )
    visualize_command.add_argument("--graph-version", default="physics-v1")
    visualize_command.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for the generated visualization files.",
    )
    visualize_command.add_argument(
        "--format",
        choices=("all", "svg", "html", "json"),
        default="all",
    )

    interpret_command = subparsers.add_parser(
        "interpret-visual",
        help="Generate structured multimodal interpretations for visual PYQs.",
    )
    interpret_command.add_argument("--graph-version", default="physics-v3")
    interpret_command.add_argument(
        "--provider",
        choices=("codex", "openai"),
        default="codex",
    )
    interpret_command.add_argument(
        "--model",
        default=None,
    )
    interpret_command.add_argument("--question-id", action="append", default=[])
    interpret_command.add_argument("--limit", type=int)
    interpret_command.add_argument("--minimum-confidence", type=float, default=0.7)
    interpret_command.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    config = load_app_config()

    if args.show_config:
        config.ensure_directories()
        print(
            json.dumps(
                {
                    "workspace_root": str(config.workspace_root),
                    "raw_data_dir": str(config.raw_data_dir),
                    "work_dir": str(config.work_dir),
                    "manifests_dir": str(config.manifests_dir),
                    "graph_dir": str(config.graph_dir),
                    "aws_region": config.aws_region,
                    "dynamodb_table_name": config.dynamodb_table_name,
                    "environment": config.environment,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "build":
        config.ensure_directories()
        snapshot, manifest = build_physics_graph(
            args.source_root,
            graph_version=args.graph_version,
            extraction_version=args.extraction_version,
            visual_output_dir=config.work_dir / "visual" / args.graph_version,
        )
        snapshot_path, manifest_path = persist_local_graph(
            snapshot,
            manifest,
            graph_dir=config.graph_dir,
            manifests_dir=config.manifests_dir,
        )
        if args.backend == "dynamodb":
            repository = DynamoDBKnowledgeGraphRepository(
                config.dynamodb_table_name,
                config.aws_region,
            )
            repository.save_snapshot(snapshot)
        print(
            json.dumps(
                {
                    "status": "built",
                    "backend": args.backend,
                    "snapshot_path": str(snapshot_path),
                    "manifest_path": str(manifest_path),
                    **manifest["counts"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command in {"validate", "show"}:
        snapshot, report = validate_local_graph(
            args.graph_version,
            graph_dir=config.graph_dir,
        )
        payload = {
            "graph_version": snapshot.graph_version,
            "snapshot_id": snapshot.id,
            "valid": report.is_valid,
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "artifact_id": issue.artifact_id,
                }
                for issue in report.issues
            ],
            "counts": {
                "assessment_items": len(snapshot.assessment_items),
                "concepts": len(snapshot.concepts),
                "skills": len(snapshot.skills),
                "misconceptions": len(snapshot.misconceptions),
                "communities": len(snapshot.communities),
                "community_summaries": len(snapshot.community_summaries),
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if report.is_valid else 1

    if args.command == "persist-snapshot":
        config.ensure_directories()
        snapshot_path = args.snapshot_path
        if not snapshot_path.exists():
            parser.error(f"snapshot file not found: {snapshot_path}")
        snapshot = GraphSnapshot.from_dict(json.loads(snapshot_path.read_text(encoding="utf-8")))
        if args.backend == "json":
            repository = JsonKnowledgeGraphRepository(config.graph_dir)
            repository.save_snapshot(snapshot)
            destination = repository.snapshots_dir / f"{snapshot.graph_version}.json"
        else:
            repository = DynamoDBKnowledgeGraphRepository(
                config.dynamodb_table_name,
                config.aws_region,
            )
            repository.save_snapshot(snapshot)
            destination = Path(f"dynamodb://{config.dynamodb_table_name}/{snapshot.graph_version}")
        print(
            json.dumps(
                {
                    "status": "persisted",
                    "backend": args.backend,
                    "graph_version": snapshot.graph_version,
                    "snapshot_path": str(snapshot_path),
                    "destination": str(destination),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "visualize":
        config.ensure_directories()
        repository = JsonKnowledgeGraphRepository(config.graph_dir)
        snapshot = repository.load_snapshot(args.graph_version)
        if snapshot is None:
            parser.error(f"graph snapshot not found: {args.graph_version}")
        output_dir = args.output_dir or (
            config.workspace_root / "visualizations" / args.graph_version
        )
        written = export_graph_visualization(snapshot, output_dir, base_name=args.graph_version)
        selected = (
            written
            if args.format == "all"
            else {args.format: written[args.format]}
        )
        print(
            json.dumps(
                {
                    "graph_version": args.graph_version,
                    "output_dir": str(Path(output_dir)),
                    "written": {name: str(path) for name, path in selected.items()},
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "interpret-visual":
        repository = JsonKnowledgeGraphRepository(config.graph_dir)
        snapshot = repository.load_snapshot(args.graph_version)
        if snapshot is None:
            parser.error(f"graph snapshot not found: {args.graph_version}")
        question_ids = set(args.question_id) or None
        candidates = [
            item.id
            for item in snapshot.assessment_items
            if item.requires_visual_interpretation
            and item.visual_interpretation is None
            and (question_ids is None or item.id in question_ids)
        ]
        if args.limit is not None:
            candidates = candidates[: args.limit]
        if args.dry_run:
            print(
                json.dumps(
                    {
                        "graph_version": args.graph_version,
                        "provider": args.provider,
                        "model": args.model or "provider-default",
                        "candidate_count": len(candidates),
                        "question_ids": candidates,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

        if args.provider == "codex":
            interpreter = CodexCliVisionInterpreter(model=args.model)
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                parser.error("OPENAI_API_KEY is required for --provider openai")
            interpreter = OpenAIResponsesVisionInterpreter(
                api_key,
                model=args.model or os.environ.get("OPENAI_VISION_MODEL", "gpt-5.5"),
            )
        run = enrich_visual_interpretations(
            snapshot,
            interpreter,
            cache_dir=config.work_dir / "visual-interpretations" / args.graph_version,
            question_ids=set(candidates),
            limit=args.limit,
            minimum_confidence=args.minimum_confidence,
        )
        repository.save_snapshot(run.snapshot)
        manifest_path = config.manifests_dir / f"{args.graph_version}.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            interpreted_items = [
                item
                for item in run.snapshot.assessment_items
                if item.visual_interpretation is not None
            ]
            manifest.setdefault("counts", {}).update(
                {
                    "visual_interpretations": len(interpreted_items),
                    "visual_interpretations_requiring_review": sum(
                        item.visual_interpretation.requires_human_review
                        for item in interpreted_items
                    ),
                }
            )
            manifest["visual_interpretation_provider"] = args.provider
            manifest["visual_interpretation_model"] = interpreter.model
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        print(
            json.dumps(
                {
                    "graph_version": args.graph_version,
                    "provider": args.provider,
                    "model": interpreter.model,
                    "interpreted": run.interpreted,
                    "cached": run.cached,
                    "skipped": run.skipped,
                    "failed": list(run.failed),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    print("knowledge-graph is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
