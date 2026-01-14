"""Custom exceptions for the podcast generation service."""

from .errors import (
    PodcastGenerationError,
    DataFetchError,
    ScriptGenerationError,
    AudioSynthesisError,
    StorageError,
    ConfigurationError,
    RateLimitError,
)

__all__ = [
    "PodcastGenerationError",
    "DataFetchError",
    "ScriptGenerationError",
    "AudioSynthesisError",
    "StorageError",
    "ConfigurationError",
    "RateLimitError",
]
