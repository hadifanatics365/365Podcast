"""Extracts injury, suspension, and return talking points."""

import logging
from typing import Any

from src.services.intelligence.talking_points import Priority, StoryType, TalkingPoint

from .base import BaseExtractor

logger = logging.getLogger(__name__)


class InjuryExtractor(BaseExtractor):
    """
    Extracts injury and suspension talking points.

    Data sources:
    - game.missingPlayers (from GameCenter API with WithExpanded=true)
    - Player.isInjured, Player.isSuspended
    - Player.expectedReturn, Player.injuryType
    - Lineup doubtful flags
    """

    @property
    def name(self) -> str:
        return "InjuryExtractor"

    @property
    def story_types(self) -> list[StoryType]:
        return [StoryType.INJURY, StoryType.SUSPENSION, StoryType.RETURN]

    def can_extract(self, game_data: dict[str, Any]) -> bool:
        """Check if injury data is available."""
        return (
            game_data.get("has_missing_players", False)
            or bool(game_data.get("missing_players", []))
            or bool(game_data.get("doubtful", []))
        )

    def extract(
        self,
        game_data: dict[str, Any],
        api_data: dict[str, Any],
    ) -> list[TalkingPoint]:
        """Extract injury-related talking points."""
        points: list[TalkingPoint] = []
        game_id = game_data.get("game_id")

        # Process missing players
        missing_players = game_data.get("missing_players", [])
        for player_data in missing_players:
            point = self._process_missing_player(player_data, game_data, game_id)
            if point:
                points.append(point)

        # Process doubtful players from lineups
        for team_key in ["home", "away"]:
            lineup = (game_data.get("lineups") or {}).get(team_key, {})
            if not lineup:
                continue

            team_name = self._get_team_name(game_data, f"{team_key}_team")

            for player in lineup.get("players", []):
                if player.get("doubtful"):
                    point = self._create_doubtful_point(player, team_name, game_id)
                    points.append(point)

        logger.debug(f"InjuryExtractor found {len(points)} points for game {game_id}")
        return points

    def _process_missing_player(
        self,
        player_data: dict[str, Any],
        game_data: dict[str, Any],
        game_id: int | None,
    ) -> TalkingPoint | None:
        """Process a single missing player entry."""
        player_name = player_data.get("player_name", player_data.get("name", ""))
        if not player_name:
            return None

        # Determine team
        comp_num = player_data.get("comp_num", player_data.get("team_num", 0))
        team_key = "home_team" if comp_num == 0 else "away_team"
        team_name = self._get_team_name(game_data, team_key)

        # Check if injured or suspended
        is_injured = player_data.get("is_injured", player_data.get("isInjured", False))
        is_suspended = player_data.get("is_suspended", player_data.get("isSuspended", False))

        if is_injured:
            return self._create_injury_point(player_data, player_name, team_name, game_id)
        elif is_suspended:
            return self._create_suspension_point(player_data, player_name, team_name, game_id)
        else:
            # Generic absence
            return self._create_absence_point(player_data, player_name, team_name, game_id)

    def _create_injury_point(
        self,
        player_data: dict[str, Any],
        player_name: str,
        team_name: str,
        game_id: int | None,
    ) -> TalkingPoint:
        """Create an injury talking point."""
        injury_type = player_data.get("injury_type", player_data.get("injuryType", ""))
        expected_return = player_data.get("expected_return", player_data.get("expectedReturn", ""))
        importance = player_data.get("importance_rank", player_data.get("popularityRank", 50))

        # Higher importance = higher priority
        priority = (
            Priority.CRITICAL if importance > 80
            else Priority.HIGH if importance > 50
            else Priority.MEDIUM
        )

        # Compose narrative
        if injury_type and expected_return:
            narrative = f"{player_name} is ruled out for {team_name} with a {injury_type} injury, expected to return {expected_return}"
        elif injury_type:
            narrative = f"{player_name} misses out for {team_name} due to a {injury_type} injury"
        else:
            narrative = f"{player_name} is unavailable for {team_name} through injury"

        headline = f"{player_name} out" + (f" ({injury_type})" if injury_type else "")

        return TalkingPoint(
            id=self._generate_id(StoryType.INJURY, player_name, team_name),
            story_type=StoryType.INJURY,
            priority=priority,
            headline=headline,
            narrative=narrative,
            team_name=team_name,
            player_name=player_name,
            player_id=player_data.get("athlete_id", player_data.get("id")),
            game_id=game_id,
            data_points={
                "injury_type": injury_type,
                "expected_return": expected_return,
                "importance": importance,
            },
            relevance_score=min(1.0, importance / 100) if importance else 0.5,
        )

    def _create_suspension_point(
        self,
        player_data: dict[str, Any],
        player_name: str,
        team_name: str,
        game_id: int | None,
    ) -> TalkingPoint:
        """Create a suspension talking point."""
        suspension_type = player_data.get("suspension_type", "")
        importance = player_data.get("importance_rank", player_data.get("popularityRank", 50))

        narrative = f"{player_name} is suspended and unavailable for {team_name}"
        if suspension_type:
            narrative = f"{player_name} serves a suspension for {team_name}"

        return TalkingPoint(
            id=self._generate_id(StoryType.SUSPENSION, player_name, team_name),
            story_type=StoryType.SUSPENSION,
            priority=Priority.HIGH,
            headline=f"{player_name} suspended",
            narrative=narrative,
            team_name=team_name,
            player_name=player_name,
            player_id=player_data.get("athlete_id", player_data.get("id")),
            game_id=game_id,
            data_points={"suspension_type": suspension_type},
            relevance_score=min(1.0, importance / 100) if importance else 0.6,
        )

    def _create_absence_point(
        self,
        player_data: dict[str, Any],
        player_name: str,
        team_name: str,
        game_id: int | None,
    ) -> TalkingPoint:
        """Create a generic absence talking point."""
        reason = player_data.get("reason", player_data.get("did_not_play_reason", ""))

        if reason:
            narrative = f"{player_name} misses out for {team_name} - {reason}"
        else:
            narrative = f"{player_name} is unavailable for {team_name}"

        return TalkingPoint(
            id=self._generate_id(StoryType.KEY_ABSENCE, player_name, team_name),
            story_type=StoryType.KEY_ABSENCE,
            priority=Priority.MEDIUM,
            headline=f"{player_name} unavailable",
            narrative=narrative,
            team_name=team_name,
            player_name=player_name,
            game_id=game_id,
            data_points={"reason": reason},
        )

    def _create_doubtful_point(
        self,
        player: dict[str, Any],
        team_name: str,
        game_id: int | None,
    ) -> TalkingPoint:
        """Create a doubtful status talking point."""
        player_name = player.get("name", "Unknown")

        return TalkingPoint(
            id=self._generate_id(StoryType.INJURY, player_name, "doubtful"),
            story_type=StoryType.INJURY,
            priority=Priority.LOW,
            headline=f"{player_name} doubtful",
            narrative=f"{player_name} is a doubt for {team_name} heading into this match",
            team_name=team_name,
            player_name=player_name,
            game_id=game_id,
            data_points={"status": "doubtful"},
            relevance_score=0.3,
        )
