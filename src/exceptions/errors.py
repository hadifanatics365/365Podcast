"""Custom exception classes for the podcast generation service."""

from typing import Any, Optional


class PodcastGenerationError(Exception):
    """Base exception for podcast generation errors."""

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.cause = cause

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class DataFetchError(PodcastGenerationError):
    """Failed to fetch game data from 365Scores API."""

    def __init__(
        self,
        message: str = "Failed to fetch game data",
        game_ids: Optional[list[str]] = None,
        status_code: Optional[int] = None,
        **kwargs: Any,
    ):
        details = kwargs.pop("details", {})
        if game_ids:
            details["game_ids"] = game_ids
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, details=details, **kwargs)


class ScriptGenerationError(PodcastGenerationError):
    """Failed to generate podcast script via Claude."""

    def __init__(
        self,
        message: str = "Failed to generate podcast script",
        model: Optional[str] = None,
        **kwargs: Any,
    ):
        details = kwargs.pop("details", {})
        if model:
            details["model"] = model
        super().__init__(message, details=details, **kwargs)


class AudioSynthesisError(PodcastGenerationError):
    """Failed to synthesize audio via ElevenLabs."""

    def __init__(
        self,
        message: str = "Failed to synthesize audio",
        voice_id: Optional[str] = None,
        script_length: Optional[int] = None,
        **kwargs: Any,
    ):
        details = kwargs.pop("details", {})
        if voice_id:
            details["voice_id"] = voice_id
        if script_length:
            details["script_length"] = script_length
        super().__init__(message, details=details, **kwargs)


class StorageError(PodcastGenerationError):
    """Failed to store or retrieve audio file."""

    def __init__(
        self,
        message: str = "Storage operation failed",
        storage_type: Optional[str] = None,
        file_path: Optional[str] = None,
        **kwargs: Any,
    ):
        details = kwargs.pop("details", {})
        if storage_type:
            details["storage_type"] = storage_type
        if file_path:
            details["file_path"] = file_path
        super().__init__(message, details=details, **kwargs)


class ConfigurationError(PodcastGenerationError):
    """Invalid or missing configuration."""

    def __init__(
        self,
        message: str = "Configuration error",
        missing_key: Optional[str] = None,
        **kwargs: Any,
    ):
        details = kwargs.pop("details", {})
        if missing_key:
            details["missing_key"] = missing_key
        super().__init__(message, details=details, **kwargs)


class RateLimitError(PodcastGenerationError):
    """Rate limit exceeded for external API."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        service: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs: Any,
    ):
        details = kwargs.pop("details", {})
        if service:
            details["service"] = service
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(message, details=details, **kwargs)


class HolyTriangleError(PodcastGenerationError):
    """Holy Triangle prerequisite not met for script generation."""

    def __init__(
        self,
        message: str = "Holy Triangle prerequisite not met",
        missing_pillar: Optional[str] = None,
        pillar_details: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ):
        details = kwargs.pop("details", {})
        if missing_pillar:
            details["missing_pillar"] = missing_pillar
        if pillar_details:
            details["pillar_details"] = pillar_details
        super().__init__(message, details=details, **kwargs)
