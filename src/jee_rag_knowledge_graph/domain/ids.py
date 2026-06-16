"""Deterministic identifiers and normalization helpers."""

from __future__ import annotations

from hashlib import sha256
import re


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value.strip().lower())


def stable_slug(value: str) -> str:
    normalized = normalize_text(value)
    slug = _NON_ALNUM_RE.sub("-", normalized).strip("-")
    return slug or "item"


def stable_id(prefix: str, *parts: str, length: int = 12) -> str:
    """Create a stable, short identifier from deterministic inputs."""

    digest_source = "\u241f".join(normalize_text(part) for part in parts if part)
    digest = sha256(digest_source.encode("utf-8")).hexdigest()[:length]
    return f"{stable_slug(prefix)}-{digest}"
