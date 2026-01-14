"""Data enrichment service for adding additional context to games."""

import logging
from typing import Any

from src.models import ContentMode, Game, GameStatus
from src.services.retrieval.game_fetcher import GameFetcher

logger = logging.getLogger(__name__)


class DataEnricher:
    """
    Enriches game data with additional context for podcast generation.

    Handles:
    - Fetching detailed statistics for post-game analysis
    - Organizing games by status (finished, upcoming, live)
    - Adding H2H and form data where available
    """

    def __init__(self, game_fetcher: GameFetcher):
        self.game_fetcher = game_fetcher

    async def enrich_games(
        self,
        games: list[Game],
        mode: ContentMode,
    ) -> dict[str, Any]:
        """
        Enrich games with additional data based on content mode.

        Args:
            games: List of games to enrich
            mode: Content generation mode

        Returns:
            Enriched data context for script generation
        """
        context: dict[str, Any] = {
            "mode": mode.value,
            "games_count": len(games),
            "games": [],
        }

        if mode == ContentMode.DAILY_RECAP:
            context = await self._enrich_for_daily_recap(games, context)
        elif mode == ContentMode.GAME_SPOTLIGHT_PREGAME:
            context = await self._enrich_for_pregame(games[0], context)
        elif mode == ContentMode.GAME_SPOTLIGHT_POSTGAME:
            context = await self._enrich_for_postgame(games[0], context)

        return context

    async def _enrich_for_daily_recap(
        self,
        games: list[Game],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Enrich games for Daily Recap mode."""
        categorized = self._categorize_games(games)

        context["ended_games"] = []
        context["upcoming_games"] = []
        context["live_games"] = []

        # Process ended games (focus on results and key moments)
        for game in categorized["ended"]:
            enriched = self._extract_postgame_data(game)
            context["ended_games"].append(enriched)

        # Process upcoming games (focus on preview data)
        for game in categorized["upcoming"]:
            enriched = self._extract_pregame_data(game)
            context["upcoming_games"].append(enriched)

        # Process live games
        for game in categorized["live"]:
            enriched = self._extract_live_data(game)
            context["live_games"].append(enriched)

        # Add all games in order for script generation
        context["games"] = (
            context["ended_games"] +
            context["live_games"] +
            context["upcoming_games"]
        )

        return context

    async def _enrich_for_pregame(
        self,
        game: Game,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Enrich single game for pre-game spotlight."""
        enriched = self._extract_pregame_data(game)

        # Try to fetch additional game center data
        detailed_game = await self.game_fetcher.fetch_game_center(game.gid)
        if detailed_game:
            enriched.update(self._extract_pregame_data(detailed_game))

        context["game"] = enriched
        context["games"] = [enriched]

        return context

    async def _enrich_for_postgame(
        self,
        game: Game,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Enrich single game for post-game spotlight."""
        enriched = self._extract_postgame_data(game)

        # Fetch detailed statistics
        stats = await self.game_fetcher.fetch_game_statistics(game.gid)
        if stats:
            enriched["detailed_statistics"] = stats

        # Try to fetch full game center data
        detailed_game = await self.game_fetcher.fetch_game_center(game.gid)
        if detailed_game:
            enriched.update(self._extract_postgame_data(detailed_game))

        context["game"] = enriched
        context["games"] = [enriched]

        return context

    def _categorize_games(self, games: list[Game]) -> dict[str, list[Game]]:
        """Categorize games by status."""
        categorized: dict[str, list[Game]] = {
            "ended": [],
            "upcoming": [],
            "live": [],
        }

        for game in games:
            if GameStatus.is_finished(game.gt):
                categorized["ended"].append(game)
            elif GameStatus.is_upcoming(game.gt):
                categorized["upcoming"].append(game)
            elif GameStatus.is_live(game.gt):
                categorized["live"].append(game)
            else:
                # Default to ended for unknown status
                categorized["ended"].append(game)

        return categorized

    def _extract_pregame_data(self, game: Game) -> dict[str, Any]:
        """Extract pre-game relevant data."""
        data: dict[str, Any] = {
            "game_id": game.gid,
            "sport_type": game.sport_type_id,
            "competition": game.competition_display_name,
            "round": game.round_name,
            "start_time": game.stime,
            "venue": None,
            "home_team": None,
            "away_team": None,
            "lineups": None,
            "pre_game_stats": [],
            "betting": None,
            "form": None,
            "trends": None,
        }

        # Teams
        if game.home_team:
            data["home_team"] = {
                "id": game.home_team.id,
                "name": game.home_team.name,
                "short_name": game.home_team.short_name,
            }
        if game.away_team:
            data["away_team"] = {
                "id": game.away_team.id,
                "name": game.away_team.name,
                "short_name": game.away_team.short_name,
            }

        # Venue
        if game.venue:
            data["venue"] = {
                "name": game.venue.name,
                "city": game.venue.city,
            }

        # Lineups
        if game.has_lineups and game.lineups:
            data["lineups"] = self._format_lineups(game.lineups)
            data["lineups_status"] = game.lineups_status_text

        # Pre-game statistics
        if game.pre_game_statistics:
            data["pre_game_stats"] = [
                {"name": s.name, "values": s.vals}
                for s in game.pre_game_statistics
            ]

        # Betting odds
        if game.has_bets and game.main_odds:
            data["betting"] = self._format_betting(game.main_odds)

        # Trends
        if game.has_team_trends and game.promoted_trends:
            data["trends"] = game.promoted_trends

        # Last matches (form)
        if game.last_matches:
            data["form"] = game.last_matches

        return data

    def _extract_postgame_data(self, game: Game) -> dict[str, Any]:
        """Extract post-game relevant data."""
        data: dict[str, Any] = {
            "game_id": game.gid,
            "sport_type": game.sport_type_id,
            "competition": game.competition_display_name,
            "round": game.round_name,
            "start_time": game.stime,
            "home_team": None,
            "away_team": None,
            "final_score": {
                "home": game.home_score,
                "away": game.away_score,
            },
            "winner": game.winner,  # 0=draw, 1=home, 2=away
            "events": [],
            "statistics": [],
            "top_performers": None,
            "actual_play_time": None,
            "betting_result": None,
        }

        # Teams
        if game.home_team:
            data["home_team"] = {
                "id": game.home_team.id,
                "name": game.home_team.name,
                "short_name": game.home_team.short_name,
            }
        if game.away_team:
            data["away_team"] = {
                "id": game.away_team.id,
                "name": game.away_team.name,
                "short_name": game.away_team.short_name,
            }

        # Events (goals, cards, subs)
        if game.events:
            data["events"] = [
                {
                    "time": e.gtd or str(e.gt),
                    "player": e.player,
                    "type": e.type,
                    "team": e.num,  # 0=home, 1=away
                    "description": e.description,
                    "extra_player": e.extra_player,
                }
                for e in game.events
            ]

        # Statistics
        if game.has_statistics and game.statistics:
            data["statistics"] = [
                {"name": s.name, "values": s.vals, "percentages": s.vals_pct}
                for s in game.statistics
            ]

        # Top performers
        if game.has_top_performers and game.top_performers_data:
            data["top_performers"] = [
                {
                    "name": p.player_name,
                    "rating": p.rating,
                    "team": p.comp_num,
                }
                for p in game.top_performers_data
            ]

        # Actual play time
        if game.actual_play_time:
            data["actual_play_time"] = {
                "first_half": game.actual_play_time.first_half,
                "second_half": game.actual_play_time.second_half,
                "extra_time": game.actual_play_time.extra_time,
                "total": game.actual_play_time.total,
            }

        # Betting result
        if game.main_odds:
            data["betting_result"] = self._format_betting_result(game.main_odds, game.winner)

        return data

    def _extract_live_data(self, game: Game) -> dict[str, Any]:
        """Extract live game data."""
        data = self._extract_postgame_data(game)
        data["is_live"] = True
        data["current_time"] = game.gtd
        data["added_time"] = game.added_time
        return data

    def _format_lineups(self, lineups: list) -> dict[str, Any]:
        """Format lineups for script generation."""
        formatted: dict[str, Any] = {"home": None, "away": None}

        for lineup in lineups:
            team_key = "home" if lineup.comp_num == 0 else "away"
            formatted[team_key] = {
                "formation": lineup.formation,
                "players": [
                    {
                        "name": p.name,
                        "position": p.position_name,
                        "number": p.shirt_number,
                        "is_captain": p.is_captain,
                    }
                    for p in lineup.players
                ],
            }

        return formatted

    def _format_betting(self, bet_line) -> dict[str, Any]:
        """Format betting data for script generation."""
        return {
            "type": bet_line.type,
            "options": [
                {
                    "name": opt.name,
                    "odds": opt.rate,
                    "trend": opt.trend,
                }
                for opt in bet_line.options
            ],
            "over_under_line": bet_line.overunder,
        }

    def _format_betting_result(self, bet_line, winner: int | None) -> dict[str, Any]:
        """Format betting result (which options won)."""
        return {
            "type": bet_line.type,
            "winning_options": [
                opt.name for opt in bet_line.options if opt.won
            ],
            "match_winner": winner,
        }
