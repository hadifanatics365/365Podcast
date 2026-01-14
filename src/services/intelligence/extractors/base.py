"""Base extractor class for story extraction."""

import hashlib
from abc import ABC, abstractmethod
from typing import Any, Optional

from src.services.intelligence.talking_points import StoryType, TalkingPoint


class BaseExtractor(ABC):
    """
    Abstract base class for story extractors.

    Each extractor is responsible for:
    1. Identifying relevant data in the game context
    2. Transforming raw data into TalkingPoint objects
    3. Assigning appropriate priority based on significance
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for logging."""
        pass

    @property
    @abstractmethod
    def story_types(self) -> list[StoryType]:
        """Story types this extractor produces."""
        pass

    @abstractmethod
    def extract(
        self,
        game_data: dict[str, Any],
        api_data: dict[str, Any],
    ) -> list[TalkingPoint]:
        """
        Extract talking points from game data.

        Args:
            game_data: Enriched game data from DataEnricher
            api_data: Additional API responses (trends, insights, predictions)

        Returns:
            List of TalkingPoint objects
        """
        pass

    @abstractmethod
    def can_extract(self, game_data: dict[str, Any]) -> bool:
        """
        Check if this extractor has relevant data to process.

        Args:
            game_data: Enriched game data

        Returns:
            True if extractor can produce talking points
        """
        pass

    def _generate_id(self, story_type: StoryType, *args: Any) -> str:
        """Generate unique ID for a talking point."""
        content = f"{story_type.value}-{'-'.join(str(a) for a in args)}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _get_team_name(self, game_data: dict[str, Any], team_key: str) -> str:
        """Get team name from game data."""
        team = game_data.get(team_key, {})
        return team.get("name", team.get("short_name", "Unknown"))

    def _get_team_id(self, game_data: dict[str, Any], team_key: str) -> Optional[int]:
        """Get team ID from game data."""
        team = game_data.get(team_key, {})
        return team.get("id")
