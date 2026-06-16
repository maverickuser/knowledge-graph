"""Persistence abstractions and implementations."""

from .memory import InMemoryKnowledgeGraphRepository
from .repository import KnowledgeGraphRepository

__all__ = ["InMemoryKnowledgeGraphRepository", "KnowledgeGraphRepository"]
