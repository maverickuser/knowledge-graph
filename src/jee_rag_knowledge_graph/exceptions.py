"""Project-specific exceptions."""


class KnowledgeGraphError(Exception):
    """Base error for project failures."""


class ConfigurationError(KnowledgeGraphError):
    """Raised when configuration is invalid or incomplete."""


class ExtractionError(KnowledgeGraphError):
    """Raised when local extraction fails."""


class ValidationError(KnowledgeGraphError):
    """Raised when a graph artifact violates an invariant."""


class RepositoryError(KnowledgeGraphError):
    """Raised when persistence or retrieval fails."""


class StorageBackendUnavailable(RepositoryError):
    """Raised when an optional storage backend is not installed."""


class UnsupportedSourceFormatError(ExtractionError):
    """Raised when a source file format is not supported locally."""
