"""API response models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PodcastResponse(BaseModel):
    """Response after initiating podcast generation."""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")
    audio_url: Optional[str] = Field(
        default=None,
        description="URL to the generated audio file (available when completed)",
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Duration of the generated audio in seconds",
    )
    script: Optional[str] = Field(
        default=None,
        description="Generated podcast script (if requested)",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Timestamp when the job was created",
    )

    model_config = {"json_schema_extra": {
        "example": {
            "job_id": "pod_abc123def456",
            "status": "processing",
            "audio_url": None,
            "duration_seconds": None,
            "script": None,
            "created_at": "2024-01-15T10:30:00Z",
        }
    }}


class PodcastStatusResponse(BaseModel):
    """Response for podcast generation status check."""

    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(
        ...,
        description="Current status: pending, processing, completed, failed",
    )
    progress: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Progress from 0.0 to 1.0",
    )
    audio_url: Optional[str] = Field(
        default=None,
        description="URL to the generated audio file",
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Duration of the audio in seconds",
    )
    script: Optional[str] = Field(
        default=None,
        description="Generated podcast script",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if status is 'failed'",
    )
    mode: Optional[str] = Field(
        default=None,
        description="Content mode used (daily_recap, game_spotlight_pregame, game_spotlight_postgame)",
    )
    games_count: Optional[int] = Field(
        default=None,
        description="Number of games included in the podcast",
    )

    model_config = {"json_schema_extra": {
        "example": {
            "job_id": "pod_abc123def456",
            "status": "completed",
            "progress": 1.0,
            "audio_url": "https://cdn.365scores.com/podcasts/2024/01/15/pod_abc123.mp3",
            "duration_seconds": 180.5,
            "script": "Welcome to 365Scores Daily Recap...",
            "error_message": None,
            "mode": "daily_recap",
            "games_count": 5,
        }
    }}


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="healthy")
    version: str = Field(default="1.0.0")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
    )
