"""Extracts betting-related talking points."""

import logging
from typing import Any, Optional

from src.services.intelligence.talking_points import Priority, StoryType, TalkingPoint

from .base import BaseExtractor

logger = logging.getLogger(__name__)


class BettingExtractor(BaseExtractor):
    """
    Extracts betting-related talking points.

    Data sources:
    - InsightData from /Data/Bets/Insights/ API
    - PredictionsData from /Data/games/Predictions/ API
    - game.mainOdds for odds movements
    - game.mostPopularBet for community favorites
    """

    # Minimum votes for prediction to be noteworthy
    MIN_PREDICTION_VOTES = 100

    @property
    def name(self) -> str:
        return "BettingExtractor"

    @property
    def story_types(self) -> list[StoryType]:
        return [StoryType.BETTING_INSIGHT, StoryType.PREDICTION]

    def can_extract(self, game_data: dict[str, Any]) -> bool:
        """Check if betting data is available. Always try - API data may have insights."""
        return True  # Always try - insights come from API

    def extract(
        self,
        game_data: dict[str, Any],
        api_data: dict[str, Any],
    ) -> list[TalkingPoint]:
        """Extract betting-related talking points."""
        points: list[TalkingPoint] = []
        game_id = game_data.get("game_id")

        # Extract from insights API
        insights_data = api_data.get("insights", {})
        if insights_data:
            insight_points = self._extract_from_insights(insights_data, game_data, game_id)
            points.extend(insight_points)

        # Extract from predictions API
        predictions_data = api_data.get("predictions", {})
        if predictions_data:
            prediction_points = self._extract_from_predictions(predictions_data, game_data, game_id)
            points.extend(prediction_points)

        # Extract from odds movements
        betting_data = game_data.get("betting") or game_data.get("main_odds")
        if betting_data:
            odds_points = self._extract_odds_movements(betting_data, game_data, game_id)
            points.extend(odds_points)

        logger.debug(f"BettingExtractor found {len(points)} points for game {game_id}")
        return points

    def _extract_from_insights(
        self,
        insights_data: dict[str, Any],
        game_data: dict[str, Any],
        game_id: Optional[int],
    ) -> list[TalkingPoint]:
        """Extract from InsightData API response."""
        points = []

        # Build provider lookup
        providers = {}
        for p in insights_data.get("Providers", []):
            pid = p.get("ID", p.get("Id", p.get("id")))
            pname = p.get("Name", p.get("name"))
            if pid and pname:
                providers[pid] = pname

        # Process insights
        for insight in insights_data.get("Insights", []):
            text = insight.get("Text", insight.get("text", ""))
            if not text or len(text) < 15:
                continue

            # Get provider attribution
            provider_id = insight.get("ProviderID", insight.get("providerId"))
            provider_name = providers.get(provider_id)

            # Check if top trend (featured)
            is_top = insight.get("TopTrend", insight.get("topTrend", False))

            # Get community validation
            likes = insight.get("Likes", insight.get("likes", 0))
            dislikes = insight.get("Dislikes", insight.get("dislikes", 0))

            priority = Priority.HIGH if is_top else Priority.MEDIUM

            points.append(TalkingPoint(
                id=self._generate_id(StoryType.BETTING_INSIGHT, insight.get("ID", text[:20])),
                story_type=StoryType.BETTING_INSIGHT,
                priority=priority,
                headline=text[:60] + "..." if len(text) > 60 else text,
                narrative=text,
                game_id=game_id,
                source="Expert Insights",
                provider_name=provider_name,
                data_points={
                    "likes": likes,
                    "dislikes": dislikes,
                    "is_featured": is_top,
                    "provider_id": provider_id,
                },
                relevance_score=0.8 if is_top else 0.6,
            ))

        return points

    def _extract_from_predictions(
        self,
        predictions_data: dict[str, Any],
        game_data: dict[str, Any],
        game_id: Optional[int],
    ) -> list[TalkingPoint]:
        """Extract from PredictionsData API response."""
        points = []

        for prediction in predictions_data.get("Predictions", []):
            votes = prediction.get("Votes", prediction.get("votes", []))
            percentages = prediction.get("VotesPercentage", prediction.get("votesPercentage", []))

            if not votes or not percentages:
                continue

            total_votes = sum(votes) if isinstance(votes, list) else 0
            if total_votes < self.MIN_PREDICTION_VOTES:
                continue

            # Find dominant prediction
            max_idx = 0
            max_votes = 0
            for i, v in enumerate(votes):
                if v > max_votes:
                    max_votes = v
                    max_idx = i

            if max_idx >= len(percentages):
                continue

            percentage = percentages[max_idx]
            if isinstance(percentage, str):
                percentage = percentage.rstrip("%")
            try:
                percentage = int(float(percentage))
            except (ValueError, TypeError):
                continue

            # Skip if not a strong majority
            if percentage < 50:
                continue

            # Determine what the prediction is for
            line_type = prediction.get("LineTypeID", prediction.get("lineTypeId", 0))
            prediction_name = self._get_prediction_name(line_type, max_idx, game_data)

            narrative = f"*{percentage} percent* of fans predict {prediction_name}, based on {total_votes:,} votes"

            points.append(TalkingPoint(
                id=self._generate_id(StoryType.PREDICTION, game_id or 0, line_type),
                story_type=StoryType.PREDICTION,
                priority=Priority.MEDIUM,
                headline=f"{percentage}% back {prediction_name}",
                narrative=narrative,
                game_id=game_id,
                source="Community Predictions",
                data_points={
                    "total_votes": total_votes,
                    "percentage": percentage,
                    "option_index": max_idx,
                    "line_type": line_type,
                },
                relevance_score=min(1.0, percentage / 100),
            ))

        return points

    def _get_prediction_name(
        self,
        line_type: int,
        option_idx: int,
        game_data: dict[str, Any],
    ) -> str:
        """Convert line type and option to readable name."""
        home_name = game_data.get("home_team", {}).get("short_name", "Home")
        away_name = game_data.get("away_team", {}).get("short_name", "Away")

        # 1X2 bet (line_type 1)
        if line_type == 1:
            options = [f"a {home_name} win", "a draw", f"an {away_name} win"]
            return options[option_idx] if option_idx < len(options) else "the result"

        # Over/Under (line_type 3)
        if line_type == 3:
            options = ["over", "under"]
            return options[option_idx] if option_idx < len(options) else "the total"

        return "the outcome"

    def _extract_odds_movements(
        self,
        betting_data: dict[str, Any],
        game_data: dict[str, Any],
        game_id: Optional[int],
    ) -> list[TalkingPoint]:
        """Extract significant odds movements."""
        points = []

        options = betting_data.get("options", [])
        if not options:
            return points

        home_name = game_data.get("home_team", {}).get("short_name", "Home")
        away_name = game_data.get("away_team", {}).get("short_name", "Away")

        for i, option in enumerate(options):
            trend = option.get("trend", 0)
            name = option.get("name", "")
            odds = option.get("odds", option.get("rate", 0))

            # Only report significant movements
            if trend == 0 or not name:
                continue

            # Map option name to team if applicable
            if i == 0:
                display_name = home_name
            elif i == 2:
                display_name = away_name
            else:
                display_name = name

            direction = "shortened" if trend < 0 else "drifted"
            narrative = f"Odds on {display_name} have {direction}"

            if odds:
                narrative += f" and are currently at {odds}"

            points.append(TalkingPoint(
                id=self._generate_id(StoryType.BETTING_INSIGHT, "odds", name, trend),
                story_type=StoryType.BETTING_INSIGHT,
                priority=Priority.LOW,
                headline=f"{display_name} odds {direction}",
                narrative=narrative,
                game_id=game_id,
                data_points={
                    "option_name": name,
                    "trend": trend,
                    "direction": direction,
                    "current_odds": odds,
                },
                relevance_score=0.4,
            ))

        return points
