"""API request models."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PodcastMode(str, Enum):
    """Podcast generation mode."""

    AUTO = "auto"
    DAILY_RECAP = "daily_recap"
    GAME_SPOTLIGHT = "game_spotlight"
    PANEL_DISCUSSION = "panel_discussion"


class PodcastFormat(str, Enum):
    """Podcast format type."""

    SINGLE_VOICE = "single_voice"
    PANEL = "panel"


class PodcastRequest(BaseModel):
    """Request to generate a podcast."""

    game_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of game IDs to include in the podcast",
    )
    mode: PodcastMode = Field(
        default=PodcastMode.AUTO,
        description="Generation mode (auto, daily_recap, game_spotlight, panel_discussion)",
    )
    format: PodcastFormat = Field(
        default=PodcastFormat.PANEL,
        description="Podcast format: single_voice (one narrator) or panel (3-person discussion)",
    )
    language: str = Field(
        default="en",
        description="Language code for the podcast",
    )
    voice_id: Optional[str] = Field(
        default=None,
        description="ElevenLabs voice ID for single_voice format (uses default if not specified)",
    )
    include_betting: bool = Field(
        default=True,
        description="Include betting insights and odds in the podcast",
    )
    user_country_id: Optional[int] = Field(
        default=None,
        description="User's country ID for localized content",
    )

    model_config = {"json_schema_extra": {
        "example": {
            "game_ids": ["12345", "67890"],
            "mode": "auto",
            "format": "panel",
            "language": "en",
            "include_betting": True,
        }
    }}
