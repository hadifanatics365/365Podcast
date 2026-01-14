"""Extracts form and streak talking points."""

import logging
from typing import Any

from src.services.intelligence.talking_points import Priority, StoryType, TalkingPoint

from .base import BaseExtractor

logger = logging.getLogger(__name__)


class FormExtractor(BaseExtractor):
    """
    Extracts form and streak talking points.

    Data sources:
    - game.lastMatches (recent form from game data)
    - TeamTrendsData from /Data/Bets/Trends/ API
    - game.promotedTrends (pre-selected trends)
    - CompetitorInsights from trends API
    """

    # Minimum streak length to report
    MIN_WIN_STREAK = 3
    MIN_LOSS_STREAK = 3
    MIN_UNBEATEN_STREAK = 5

    @property
    def name(self) -> str:
        return "FormExtractor"

    @property
    def story_types(self) -> list[StoryType]:
        return [StoryType.FORM_STREAK]

    def can_extract(self, game_data: dict[str, Any]) -> bool:
        """Check if form data is available. Always try - API data may have trends."""
        return True  # Always try - trends come from API, not game_data

    def extract(
        self,
        game_data: dict[str, Any],
        api_data: dict[str, Any],
    ) -> list[TalkingPoint]:
        """Extract form-related talking points."""
        points: list[TalkingPoint] = []
        game_id = game_data.get("game_id")

        # Extract from last matches / form data
        form_data = game_data.get("form") or game_data.get("last_matches", [])
        if form_data:
            form_points = self._extract_from_form(form_data, game_data, game_id)
            points.extend(form_points)
            logger.debug(f"FormExtractor: {len(form_points)} points from form data")

        # Extract from trends API
        trends_data = api_data.get("trends", {})
        trends_array = trends_data.get("Trends", [])
        logger.debug(f"FormExtractor: trends_data has {len(trends_array)} trend groups")
        if trends_data:
            trend_points = self._extract_from_trends_api(trends_data, game_data, game_id)
            points.extend(trend_points)
            logger.debug(f"FormExtractor: {len(trend_points)} points from trends API")

        # Extract from promoted trends on game object
        promoted_trends = game_data.get("promoted_trends", [])
        if promoted_trends:
            promoted_points = self._extract_from_promoted_trends(promoted_trends, game_data, game_id)
            points.extend(promoted_points)

        logger.info(f"FormExtractor found {len(points)} total points for game {game_id}")
        return points

    def _extract_from_form(
        self,
        form_data: list[dict[str, Any]],
        game_data: dict[str, Any],
        game_id: int | None,
    ) -> list[TalkingPoint]:
        """Extract streaks from last matches data."""
        points = []

        # Group matches by team
        home_matches = []
        away_matches = []

        for match in form_data:
            team = match.get("team", match.get("comp_num", ""))
            if team in ("home", 0, "0"):
                home_matches.append(match)
            elif team in ("away", 1, "1"):
                away_matches.append(match)

        # Analyze each team
        for team_key, matches in [("home_team", home_matches), ("away_team", away_matches)]:
            if not matches:
                continue

            team_name = self._get_team_name(game_data, team_key)
            team_id = self._get_team_id(game_data, team_key)

            streak = self._calculate_streak(matches)
            if streak:
                point = self._create_streak_point(streak, team_name, team_id, game_id)
                if point:
                    points.append(point)

        return points

    def _calculate_streak(self, matches: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Calculate current win/loss/unbeaten streak from matches."""
        if not matches:
            return None

        results = []
        for match in matches[:10]:  # Last 10 matches max
            winner = match.get("winner", -1)

            # Determine if this team won/lost/drew
            is_home = match.get("team_position", match.get("is_home", True))
            if isinstance(is_home, str):
                is_home = is_home.lower() == "home"

            if winner == 0:
                results.append("draw")
            elif (winner == 1 and is_home) or (winner == 2 and not is_home):
                results.append("win")
            else:
                results.append("loss")

        if not results:
            return None

        # Check for win/loss streak
        first_result = results[0]
        streak_length = 1
        for result in results[1:]:
            if result == first_result:
                streak_length += 1
            else:
                break

        # Return if significant streak
        if first_result == "win" and streak_length >= self.MIN_WIN_STREAK:
            return {"type": "winning", "length": streak_length, "results": results[:streak_length]}
        elif first_result == "loss" and streak_length >= self.MIN_LOSS_STREAK:
            return {"type": "losing", "length": streak_length, "results": results[:streak_length]}

        # Check for unbeaten streak (wins + draws)
        unbeaten = 0
        for result in results:
            if result != "loss":
                unbeaten += 1
            else:
                break

        if unbeaten >= self.MIN_UNBEATEN_STREAK:
            return {"type": "unbeaten", "length": unbeaten, "results": results[:unbeaten]}

        # Check for winless streak (losses + draws)
        winless = 0
        for result in results:
            if result != "win":
                winless += 1
            else:
                break

        if winless >= self.MIN_LOSS_STREAK:
            return {"type": "winless", "length": winless, "results": results[:winless]}

        return None

    def _create_streak_point(
        self,
        streak: dict[str, Any],
        team_name: str,
        team_id: int | None,
        game_id: int | None,
    ) -> TalkingPoint | None:
        """Create a talking point from a streak."""
        streak_type = streak["type"]
        length = streak["length"]

        # Determine priority based on streak length
        if length >= 5:
            priority = Priority.CRITICAL
        elif length >= 4:
            priority = Priority.HIGH
        else:
            priority = Priority.MEDIUM

        # Compose narrative based on streak type
        narratives = {
            "winning": f"{team_name} are in *scintillating form*, having won their last {length} matches",
            "losing": f"{team_name} are *struggling for form*, having lost their last {length} matches",
            "unbeaten": f"{team_name} remain *unbeaten* in their last {length} games",
            "winless": f"{team_name} are without a win in their last {length} matches",
        }

        headlines = {
            "winning": f"{team_name} on {length}-game winning streak",
            "losing": f"{team_name} on {length}-game losing streak",
            "unbeaten": f"{team_name} unbeaten in {length}",
            "winless": f"{team_name} winless in {length}",
        }

        narrative = narratives.get(streak_type)
        headline = headlines.get(streak_type)

        if not narrative or not headline:
            return None

        return TalkingPoint(
            id=self._generate_id(StoryType.FORM_STREAK, team_name, streak_type),
            story_type=StoryType.FORM_STREAK,
            priority=priority,
            headline=headline,
            narrative=narrative,
            team_name=team_name,
            team_id=team_id,
            game_id=game_id,
            data_points={
                "streak_type": streak_type,
                "streak_length": length,
                "results": streak["results"],
            },
            relevance_score=min(1.0, length / 10),
        )

    def _extract_from_trends_api(
        self,
        trends_data: dict[str, Any],
        game_data: dict[str, Any],
        game_id: int | None,
    ) -> list[TalkingPoint]:
        """Extract from TeamTrendsData API response."""
        points = []

        # Get providers for attribution (handle both cases)
        providers = {}
        for p in trends_data.get("Providers", []):
            pid = p.get("ID") or p.get("Id") or p.get("id")
            pname = p.get("Name") or p.get("name")
            if pid:
                providers[pid] = pname

        # Process trends array (API returns Trends[].CompetitorInsights[])
        for trend in trends_data.get("Trends", []):
            trend_name = trend.get("Name", "")

            for comp_insight in trend.get("CompetitorInsights", []):
                # CompetitorIds is an array
                comp_ids = comp_insight.get("CompetitorIds", [])
                comp_id = comp_ids[0] if comp_ids else None

                for insight in comp_insight.get("Insights", []):
                    text = insight.get("Text", "")
                    if not text or len(text) < 10:
                        continue

                    provider_id = insight.get("ProviderID")
                    provider_name = providers.get(provider_id)
                    is_top = insight.get("TopTrend", False)

                    # Determine team name from competitor ID
                    home_team = game_data.get("home_team", {})
                    away_team = game_data.get("away_team", {})
                    team_name = None
                    if home_team.get("id") == comp_id:
                        team_name = home_team.get("name")
                    elif away_team.get("id") == comp_id:
                        team_name = away_team.get("name")

                    priority = Priority.CRITICAL if is_top else Priority.HIGH

                    points.append(TalkingPoint(
                        id=self._generate_id(StoryType.FORM_STREAK, insight.get("ID", text[:20])),
                        story_type=StoryType.FORM_STREAK,
                        priority=priority,
                        headline=text[:50] + "..." if len(text) > 50 else text,
                        narrative=text,
                        team_name=team_name,
                        team_id=comp_id,
                        game_id=game_id,
                        source="365Scores Trends",
                        provider_name=provider_name,
                        data_points={
                            "provider_id": provider_id,
                            "trend_name": trend_name,
                            "is_top_trend": is_top,
                        },
                        relevance_score=0.9 if is_top else 0.7,
                    ))

        return points

    def _extract_from_promoted_trends(
        self,
        promoted_trends: list[dict[str, Any]],
        game_data: dict[str, Any],
        game_id: int | None,
    ) -> list[TalkingPoint]:
        """Extract from game.promotedTrends."""
        points = []

        for trend in promoted_trends:
            text = trend.get("text", trend.get("Text", ""))
            if not text or len(text) < 10:
                continue

            points.append(TalkingPoint(
                id=self._generate_id(StoryType.FORM_STREAK, "promoted", text[:20]),
                story_type=StoryType.FORM_STREAK,
                priority=Priority.HIGH,
                headline=text[:50] + "..." if len(text) > 50 else text,
                narrative=text,
                game_id=game_id,
                source="Promoted Trend",
                relevance_score=0.8,
            ))

        return points
