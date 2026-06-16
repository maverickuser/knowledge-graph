"""Local source loading and normalization."""

from .physics_corpus import build_physics_seed_bundle, load_physics_corpus
from .loaders import load_local_source, read_source_text
from .normalize import normalize_source_document, split_into_sections

__all__ = [
    "build_physics_seed_bundle",
    "load_local_source",
    "load_physics_corpus",
    "normalize_source_document",
    "read_source_text",
    "split_into_sections",
]
