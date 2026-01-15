"""Extracts lineup-related talking points (debuts, returns, key absences)."""

import logging
from typing import Any, Optional

from src.services.intelligence.talking_points import Priority, StoryType, TalkingPoint

from .base import BaseExtractor

logger = logging.getLogger(__name__)


class LineupExtractor(BaseExtractor):
    """
    Extracts lineup-related talking points.

    Data sources:
    - game.lineups for starting XI
    - Player seasonStats for debut detection
    - Player game history for return detection
    - Formation changes
    """

    @property
    def name(self) -> str:
        return "LineupExtractor"

    @property
    def story_types(self) -> list[StoryType]:
        return [StoryType.DEBUT, StoryType.RETURN, StoryType.KEY_ABSENCE]

    def can_extract(self, game_data: dict[str, Any]) -> bool:
        """Check if lineup data is available."""
        lineups = game_data.get("lineups") or {}
        return bool(lineups.get("home") or lineups.get("away"))

    def extract(
        self,
        game_data: dict[str, Any],
        api_data: dict[str, Any],
    ) -> list[TalkingPoint]:
        """Extract lineup-related talking points."""
        points: list[TalkingPoint] = []
        game_id = game_data.get("game_id")
        competition = game_data.get("competition")

        lineups = game_data.get("lineups") or {}

        for team_key in ["home", "away"]:
            lineup = lineups.get(team_key, {})
            if not lineup:
                continue

            team_name = self._get_team_name(game_data, f"{team_key}_team")
            team_id = self._get_team_id(game_data, f"{team_key}_team")

            # Check for debuts
            debut_points = self._check_for_debuts(lineup, team_name, team_id, competition, game_id)
            points.extend(debut_points)

            # Check for returns
            return_points = self._check_for_returns(lineup, team_name, team_id, game_id)
            points.extend(return_points)

            # Check formation
            formation_point = self._check_formation(lineup, team_name, game_id)
            if formation_point:
                points.append(formation_point)

            # Check captain
            captain_point = self._check_captain(lineup, team_name, game_id)
            if captain_point:
                points.append(captain_point)

        logger.debug(f"LineupExtractor found {len(points)} points for game {game_id}")
        return points

    def _check_for_debuts(
        self,
        lineup: dict[str, Any],
        team_name: str,
        team_id: Optional[int],
        competition: Optional[str],
        game_id: Optional[int],
    ) -> list[TalkingPoint]:
        """Check for players making their debut."""
        points = []

        for player in lineup.get("players", []):
            # Check season stats for games played
            season_stats = player.get("season_stats", player.get("seasonStats", {}))
            games_played = season_stats.get("games_played", season_stats.get("gamesPlayed", -1))

            # If first game (0 games played so far)
            if games_played == 0:
                player_name = player.get("name", "Unknown")
                age = player.get("age")
                position = player.get("position", "")

                # Compose narrative
                if age and age < 20:
                    narrative = f"{team_name} hand a debut to {age}-year-old {player_name}"
                    if competition:
                        narrative = f"{team_name} hand a {competition} debut to {age}-year-old {player_name}"
                    headline = f"{age}-year-old {player_name} debuts"
                    priority = Priority.HIGH  # Young debuts are exciting
                else:
                    narrative = f"{player_name} makes their debut for {team_name}"
                    headline = f"{player_name} makes debut"
                    priority = Priority.MEDIUM

                points.append(TalkingPoint(
                    id=self._generate_id(StoryType.DEBUT, player_name, team_name),
                    story_type=StoryType.DEBUT,
                    priority=priority,
                    headline=headline,
                    narrative=narrative,
                    team_name=team_name,
                    team_id=team_id,
                    player_name=player_name,
                    player_id=player.get("id", player.get("athlete_id")),
                    competition=competition,
                    game_id=game_id,
                    data_points={
                        "age": age,
                        "position": position,
                    },
                    relevance_score=0.8 if age and age < 20 else 0.5,
                ))

            # Check for competition debut (e.g., first CL game)
            elif games_played is not None and games_played > 0:
                comp_games = season_stats.get("competition_games", 0)
                if comp_games == 0 and competition:
                    player_name = player.get("name", "Unknown")
                    points.append(TalkingPoint(
                        id=self._generate_id(StoryType.DEBUT, player_name, competition),
                        story_type=StoryType.DEBUT,
                        priority=Priority.MEDIUM,
                        headline=f"{player_name} {competition} debut",
                        narrative=f"{player_name} makes their {competition} debut for {team_name}",
                        team_name=team_name,
                        player_name=player_name,
                        competition=competition,
                        game_id=game_id,
                        relevance_score=0.5,
                    ))

        return points

    def _check_for_returns(
        self,
        lineup: dict[str, Any],
        team_name: str,
        team_id: Optional[int],
        game_id: Optional[int],
    ) -> list[TalkingPoint]:
        """Check for players returning from absence."""
        points = []

        for player in lineup.get("players", []):
            # Check for return flag
            is_returning = player.get("is_returning", player.get("isReturning", False))
            games_missed = player.get("games_missed", player.get("gamesMissed", 0))

            if is_returning or games_missed > 2:
                player_name = player.get("name", "Unknown")
                importance = player.get("importance_rank", player.get("popularityRank", 50))

                if games_missed > 0:
                    narrative = f"{player_name} returns to the {team_name} squad after missing {games_missed} games"
                else:
                    narrative = f"{player_name} returns to action for {team_name}"

                priority = Priority.HIGH if importance > 70 else Priority.MEDIUM

                points.append(TalkingPoint(
                    id=self._generate_id(StoryType.RETURN, player_name, team_name),
                    story_type=StoryType.RETURN,
                    priority=priority,
                    headline=f"{player_name} returns",
                    narrative=narrative,
                    team_name=team_name,
                    team_id=team_id,
                    player_name=player_name,
                    player_id=player.get("id", player.get("athlete_id")),
                    game_id=game_id,
                    data_points={
                        "games_missed": games_missed,
                        "importance": importance,
                    },
                    relevance_score=min(1.0, importance / 100) if importance else 0.5,
                ))

        return points

    def _check_formation(
        self,
        lineup: dict[str, Any],
        team_name: str,
        game_id: Optional[int],
    ) -> Optional[TalkingPoint]:
        """Check for notable formation."""
        formation = lineup.get("formation", "")
        if not formation:
            return None

        # Check if it's an unusual formation (not 4-3-3, 4-4-2, 4-2-3-1)
        common_formations = {"4-3-3", "4-4-2", "4-2-3-1", "3-5-2", "4-1-4-1"}
        if formation in common_formations:
            return None

        return TalkingPoint(
            id=self._generate_id(StoryType.MILESTONE, "formation", team_name, formation),
            story_type=StoryType.MILESTONE,
            priority=Priority.LOW,
            headline=f"{team_name} line up in {formation}",
            narrative=f"{team_name} opt for an interesting {formation} formation",
            team_name=team_name,
            game_id=game_id,
            data_points={"formation": formation},
            relevance_score=0.3,
        )

    def _check_captain(
        self,
        lineup: dict[str, Any],
        team_name: str,
        game_id: Optional[int],
    ) -> Optional[TalkingPoint]:
        """Check for new/unusual captain."""
        for player in lineup.get("players", []):
            is_captain = player.get("is_captain", player.get("isCaptain", False))
            is_new_captain = player.get("is_new_captain", player.get("isNewCaptain", False))

            if is_captain and is_new_captain:
                player_name = player.get("name", "Unknown")

                return TalkingPoint(
                    id=self._generate_id(StoryType.MILESTONE, "captain", player_name),
                    story_type=StoryType.MILESTONE,
                    priority=Priority.MEDIUM,
                    headline=f"{player_name} captains {team_name}",
                    narrative=f"{player_name} wears the armband for {team_name} for the first time",
                    team_name=team_name,
                    player_name=player_name,
                    game_id=game_id,
                    relevance_score=0.5,
                )

        return None
