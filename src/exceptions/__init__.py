"""Custom exceptions for the podcast generation service."""

from .errors import (
    PodcastGenerationError,
    DataFetchError,
    ScriptGenerationError,
    AudioSynthesisError,
    StorageError,
    ConfigurationError,
    RateLimitError,
    HolyTriangleError,
)

__all__ = [
    "PodcastGenerationError",
    "DataFetchError",
    "ScriptGenerationError",
    "AudioSynthesisError",
    "StorageError",
    "ConfigurationError",
    "RateLimitError",
    "HolyTriangleError",
]
