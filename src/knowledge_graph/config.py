"""Runtime configuration for local and AWS-backed workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from .exceptions import ConfigurationError


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Resolved application configuration."""

    workspace_root: Path
    raw_data_dir: Path
    work_dir: Path
    manifests_dir: Path
    graph_dir: Path
    aws_region: str
    dynamodb_table_name: str
    environment: str = "local"

    def ensure_directories(self) -> None:
        for path in (
            self.raw_data_dir,
            self.work_dir,
            self.manifests_dir,
            self.graph_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


def load_app_config(env: dict[str, str] | None = None) -> AppConfig:
    """Load configuration from environment variables with local defaults."""

    source = env if env is not None else os.environ
    workspace_root = Path(source.get("JEE_RAG_WORKSPACE_ROOT", _repo_root())).resolve()
    aws_region = source.get("AWS_REGION", source.get("JEE_RAG_AWS_REGION", "ap-south-1"))
    dynamodb_table_name = source.get(
        "JEE_RAG_DYNAMODB_TABLE", "knowledge-graph"
    )
    environment = source.get("JEE_RAG_ENVIRONMENT", "local")

    if not dynamodb_table_name.strip():
        raise ConfigurationError("JEE_RAG_DYNAMODB_TABLE must not be empty")

    data_root = workspace_root / "data"
    return AppConfig(
        workspace_root=workspace_root,
        raw_data_dir=data_root / "raw",
        work_dir=data_root / "work",
        manifests_dir=data_root / "manifests",
        graph_dir=data_root / "graph",
        aws_region=aws_region,
        dynamodb_table_name=dynamodb_table_name,
        environment=environment,
    )
