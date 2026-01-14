"""Main content intelligence service that orchestrates story extraction."""

import logging
from typing import Any, Optional

from src.config import Settings, get_settings
from src.models import ContentMode

from .extractors import (
    BaseExtractor,
    BettingExtractor,
    FormExtractor,
    InjuryExtractor,
    LineupExtractor,
)
from .intelligence_fetcher import IntelligenceFetcher
from .talking_points import (
    GameIntelligence,
    IntelligenceContext,
    Priority,
    TalkingPoint,
)

logger = logging.getLogger(__name__)


class ContentIntelligence:
    """
    Main service that orchestrates intelligence extraction.

    Transforms raw game data into structured talking points
    for more compelling podcast scripts.

    Workflow:
    1. Fetch additional data from API (trends, insights, predictions)
    2. Run all extractors to generate TalkingPoints
    3. Prioritize and aggregate points
    4. Return IntelligenceContext for script generation
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        intelligence_fetcher: Optional[IntelligenceFetcher] = None,
    ):
        self.settings = settings or get_settings()
        self.fetcher = intelligence_fetcher or IntelligenceFetcher(self.settings)

        # Initialize all extractors
        self.extractors: list[BaseExtractor] = [
            InjuryExtractor(),
            FormExtractor(),
            BettingExtractor(),
            LineupExtractor(),
        ]

        logger.info(f"ContentIntelligence initialized with {len(self.extractors)} extractors")

    async def analyze(
        self,
        enriched_context: dict[str, Any],
        mode: ContentMode,
        include_betting: bool = True,
    ) -> IntelligenceContext:
        """
        Analyze games and extract talking points.

        Args:
            enriched_context: Output from DataEnricher
            mode: Content generation mode
            include_betting: Include betting-related points

        Returns:
            IntelligenceContext with structured talking points
        """
        games = enriched_context.get("games", [])
        logger.info(f"Analyzing {len(games)} games for intelligence (mode: {mode.value})")

        game_intelligences: list[GameIntelligence] = []
        all_talking_points: list[TalkingPoint] = []

        for game_data in games:
            game_intel = await self._analyze_game(
                game_data=game_data,
                include_betting=include_betting,
            )
            game_intelligences.append(game_intel)
            all_talking_points.extend(game_intel.talking_points)

        # Select top stories across all games
        top_stories = self._select_top_stories(all_talking_points, mode)

        logger.info(
            f"Intelligence analysis complete: {len(all_talking_points)} total points, "
            f"{len(top_stories)} top stories"
        )

        return IntelligenceContext(
            mode=mode.value,
            games=game_intelligences,
            top_stories=top_stories,
            raw_context=enriched_context,
        )

    async def _analyze_game(
        self,
        game_data: dict[str, Any],
        include_betting: bool,
    ) -> GameIntelligence:
        """Analyze a single game and extract talking points."""
        game_id = game_data.get("game_id")

        # Fetch additional intelligence data from API
        api_data = await self.fetcher.fetch_all_intelligence(
            game_id=game_id,
            top_bookmaker_id=game_data.get("top_bookmaker_id", 0),
        )

        # Debug log API data
        trends_count = len(api_data.get("trends", {}).get("Trends", []))
        insights_count = len(api_data.get("insights", {}).get("Insights", []))
        logger.debug(f"API data for game {game_id}: {trends_count} trends, {insights_count} insights")

        # Create game intelligence container
        home_team = game_data.get("home_team", {})
        away_team = game_data.get("away_team", {})

        game_intel = GameIntelligence(
            game_id=game_id,
            home_team=home_team.get("name", "Home"),
            away_team=away_team.get("name", "Away"),
            competition=game_data.get("competition"),
        )

        # Run all extractors
        for extractor in self.extractors:
            # Skip betting extractors if not requested
            if not include_betting and "betting" in extractor.name.lower():
                continue

            try:
                if extractor.can_extract(game_data):
                    points = extractor.extract(game_data, api_data)
                    for point in points:
                        game_intel.add_point(point)
                    logger.debug(
                        f"{extractor.name} extracted {len(points)} points for game {game_id}"
                    )
            except Exception as e:
                logger.warning(f"{extractor.name} failed for game {game_id}: {e}")
                continue

        return game_intel

    def _select_top_stories(
        self,
        all_points: list[TalkingPoint],
        mode: ContentMode,
        max_count: int = 6,
    ) -> list[TalkingPoint]:
        """
        Select top stories based on priority and relevance.

        Ensures diversity by limiting points per category.
        """
        if not all_points:
            return []

        # Sort by priority (lower is higher priority) then relevance
        sorted_points = sorted(
            all_points,
            key=lambda p: (p.priority.value, -p.relevance_score),
        )

        # Ensure diversity (max 2 from same story type)
        selected: list[TalkingPoint] = []
        type_counts: dict[str, int] = {}

        for point in sorted_points:
            story_type = point.story_type.value
            current_count = type_counts.get(story_type, 0)

            # Allow max 2 of same type (but always allow critical priority)
            if current_count < 2 or point.priority == Priority.CRITICAL:
                selected.append(point)
                type_counts[story_type] = current_count + 1

            if len(selected) >= max_count:
                break

        return selected

    def get_extractors(self) -> list[str]:
        """Get list of active extractor names."""
        return [e.name for e in self.extractors]
