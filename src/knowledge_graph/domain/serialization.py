"""Generic artifact serialization helpers."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints
import types


ARTIFACT_REGISTRY: dict[str, type[Any]] = {}


def register_artifact(cls: type[Any]) -> type[Any]:
    ARTIFACT_REGISTRY[cls.__name__] = cls
    return cls


class SerializableArtifact:
    """Mixin for stable JSON-friendly artifacts."""

    def to_dict(self) -> dict[str, Any]:
        return serialize_artifact(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Any:
        return deserialize_dataclass(cls, data)


def serialize_artifact(value: Any) -> Any:
    if is_dataclass(value):
        payload: dict[str, Any] = {"__type__": value.__class__.__name__}
        for field in fields(value):
            payload[field.name] = serialize_artifact(getattr(value, field.name))
        return payload

    if isinstance(value, tuple):
        return [serialize_artifact(item) for item in value]

    if isinstance(value, list):
        return [serialize_artifact(item) for item in value]

    if isinstance(value, dict):
        return {str(key): serialize_artifact(value[key]) for key in sorted(value)}

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    return value


def _deserialize_sequence(annotation: Any, value: Any) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin not in (list, tuple):
        return value

    inner_type = args[0] if args else Any
    items = [deserialize_value(inner_type, item) for item in value]
    if origin is tuple:
        return tuple(items)
    return items


def deserialize_value(annotation: Any, value: Any) -> Any:
    if value is None:
        return None

    if annotation in (Any, object):
        return value

    origin = get_origin(annotation)
    if origin in (types.UnionType, getattr(types, "UnionType", None)):  # pragma: no cover
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        for arg in args:
            if arg is Any:
                return value
            try:
                return deserialize_value(arg, value)
            except Exception:
                continue
        return value

    if origin in (list, tuple):
        return _deserialize_sequence(annotation, value)

    if annotation is Path:
        return Path(value)

    if annotation is datetime:
        return datetime.fromisoformat(value)

    if isinstance(value, dict) and "__type__" in value:
        artifact_type = value["__type__"]
        artifact_cls = ARTIFACT_REGISTRY.get(artifact_type)
        if artifact_cls is None:
            raise ValueError(f"Unknown artifact type: {artifact_type}")
        return deserialize_dataclass(artifact_cls, value)

    if is_dataclass(annotation):
        return deserialize_dataclass(annotation, value)

    return value


def deserialize_dataclass(cls: type[Any], data: dict[str, Any]) -> Any:
    type_hints = get_type_hints(cls, globalns=vars(__import__(cls.__module__, fromlist=["*"])))
    kwargs: dict[str, Any] = {}
    for field in fields(cls):
        if field.name not in data:
            continue
        kwargs[field.name] = deserialize_value(type_hints.get(field.name, Any), data[field.name])
    return cls(**kwargs)
