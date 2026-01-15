"""Data enrichment service for adding additional context to games."""

import logging
from typing import Any, Optional

from src.models import ContentMode, Game, GameStatus
from src.services.retrieval.game_fetcher import GameFetcher
from src.services.retrieval.news_fetcher import NewsFetcher

logger = logging.getLogger(__name__)


class DataEnricher:
    """
    Enriches game data with additional context for podcast generation.

    Handles:
    - Fetching detailed statistics for post-game analysis
    - Organizing games by status (finished, upcoming, live)
    - Adding H2H and form data where available
    - Fetching and filtering relevant news articles
    """

    def __init__(self, game_fetcher: GameFetcher, news_fetcher: Optional[NewsFetcher] = None):
        self.game_fetcher = game_fetcher
        self.news_fetcher = news_fetcher or NewsFetcher()

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
            # Fetch standings for finished games
            if game.competition_id:
                try:
                    standings = await self.game_fetcher.fetch_standings(game.competition_id)
                    enriched["standings"] = self._format_standings(standings, game)
                except Exception as e:
                    logger.warning(f"Failed to fetch standings for game {game.gid}: {e}")
                    enriched["standings"] = None
            # Fetch news for finished games
            try:
                news_items = await self.news_fetcher.fetch_relevant_news(game, time_window_hours=48)
                enriched["news"] = [news.to_dict() for news in news_items]
                enriched["news_count"] = len(news_items)
            except Exception as e:
                logger.warning(f"Failed to fetch news for game {game.gid}: {e}")
                enriched["news"] = []
                enriched["news_count"] = 0
            context["ended_games"].append(enriched)

        # Process upcoming games (focus on preview data)
        for game in categorized["upcoming"]:
            enriched = self._extract_pregame_data(game)
            # Fetch standings for scheduled games
            if game.competition_id:
                try:
                    standings = await self.game_fetcher.fetch_standings(game.competition_id)
                    enriched["standings"] = self._format_standings(standings, game)
                except Exception as e:
                    logger.warning(f"Failed to fetch standings for game {game.gid}: {e}")
                    enriched["standings"] = None
            # Fetch news for scheduled games (last 24 hours)
            try:
                news_items = await self.news_fetcher.fetch_relevant_news(game, time_window_hours=24)
                enriched["news"] = [news.to_dict() for news in news_items]
                enriched["news_count"] = len(news_items)
            except Exception as e:
                logger.warning(f"Failed to fetch news for game {game.gid}: {e}")
                enriched["news"] = []
                enriched["news_count"] = 0
            context["upcoming_games"].append(enriched)

        # Process live games
        for game in categorized["live"]:
            enriched = self._extract_live_data(game)
            # Fetch standings for live games
            if game.competition_id:
                try:
                    standings = await self.game_fetcher.fetch_standings(game.competition_id)
                    enriched["standings"] = self._format_standings(standings, game)
                except Exception as e:
                    logger.warning(f"Failed to fetch standings for game {game.gid}: {e}")
                    enriched["standings"] = None
            # Fetch recent news for live games
            try:
                news_items = await self.news_fetcher.fetch_relevant_news(game, time_window_hours=24)
                enriched["news"] = [news.to_dict() for news in news_items]
                enriched["news_count"] = len(news_items)
            except Exception as e:
                logger.warning(f"Failed to fetch news for game {game.gid}: {e}")
                enriched["news"] = []
                enriched["news_count"] = 0
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
        # Store the Game object in context for LineupAgent
        context["game"] = game
        context["original_game_obj"] = game
        
        enriched = self._extract_pregame_data(game)

        # Fetch comprehensive game center data (includes lineups, odds, news, standings)
        gamecenter_data = await self.game_fetcher.fetch_game_center(game.gid)
        if gamecenter_data:
            # Extract lineups from GameCenter
            if "Lineups" in gamecenter_data or "lineups" in gamecenter_data:
                lineups = gamecenter_data.get("Lineups") or gamecenter_data.get("lineups", [])
                if lineups:
                    enriched["lineups"] = self._extract_lineups_from_gamecenter(lineups)
                    enriched["lineups_status"] = gamecenter_data.get("LineupsStatusText") or "Probable Lineups"
                    logger.info(f"Extracted lineups from GameCenter for game {game.gid}")
            
            # Extract betting odds from GameCenter
            if "MainOdds" in gamecenter_data or "main_odds" in gamecenter_data:
                main_odds = gamecenter_data.get("MainOdds") or gamecenter_data.get("main_odds")
                if main_odds:
                    enriched["betting"] = self._extract_betting_from_gamecenter(main_odds, gamecenter_data)
                    logger.info(f"Extracted betting odds from GameCenter for game {game.gid}")
            
            # Extract news from GameCenter (news is in the response)
            metadata = gamecenter_data.get("_gamecenter_metadata", {})
            news_items = metadata.get("news", [])
            if not news_items:
                # Try direct access
                news_items = gamecenter_data.get("News", []) or gamecenter_data.get("news", [])
            
            if news_items:
                enriched["news"] = self._extract_news_from_gamecenter(news_items)
                enriched["news_count"] = len(enriched["news"])
                logger.info(f"Extracted {len(enriched['news'])} news items from GameCenter for game {game.gid}")
            
            # Extract standings from GameCenter (if available in Competitions)
            competitions = metadata.get("competitions", [])
            if competitions and game.competition_id:
                standings_data = self._extract_standings_from_gamecenter(competitions, game.competition_id)
                if standings_data:
                    enriched["standings"] = self._format_standings(standings_data, game)
                    logger.info(f"Extracted standings from GameCenter for competition {game.competition_id}")

        # Fetch pre-game statistics separately
        pregame_stats = await self.game_fetcher.fetch_pregame_statistics(game.gid)
        if pregame_stats:
            enriched["pre_game_stats"] = self._extract_pregame_stats_from_response(pregame_stats)
            logger.info(f"Fetched pre-game statistics for game {game.gid}")

        # Fallback: Fetch league standings if not found in GameCenter
        if not enriched.get("standings") and game.competition_id:
            try:
                standings = await self.game_fetcher.fetch_standings(game.competition_id)
                enriched["standings"] = self._format_standings(standings, game)
                logger.info(f"Fetched standings for competition {game.competition_id}")
            except Exception as e:
                logger.warning(f"Failed to fetch standings for game {game.gid}: {e}")
                enriched["standings"] = None

        # Fallback: Fetch news if not found in GameCenter
        if not enriched.get("news"):
            try:
                news_items = await self.news_fetcher.fetch_relevant_news(game, time_window_hours=24)
                enriched["news"] = [news.to_dict() for news in news_items]
                enriched["news_count"] = len(news_items)
                logger.info(f"Fetched {len(news_items)} relevant news items for pre-game")
            except Exception as e:
                logger.warning(f"Failed to fetch news for game {game.gid}: {e}")
                enriched["news"] = []
                enriched["news_count"] = 0

        # Store enriched data
        context["game_data"] = enriched  # Store enriched dict separately
        context["games"] = [enriched]

        return context

    async def _enrich_for_postgame(
        self,
        game: Game,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Enrich single game for post-game spotlight."""
        # Store the Game object in context for LineupAgent
        context["game"] = game
        context["original_game_obj"] = game
        
        enriched = self._extract_postgame_data(game)

        # Fetch comprehensive game center data (includes lineups, odds, news, standings)
        gamecenter_data = await self.game_fetcher.fetch_game_center(game.gid)
        if gamecenter_data:
            # Extract lineups from GameCenter
            if "Lineups" in gamecenter_data or "lineups" in gamecenter_data:
                lineups = gamecenter_data.get("Lineups") or gamecenter_data.get("lineups", [])
                if lineups:
                    enriched["lineups"] = self._extract_lineups_from_gamecenter(lineups)
                    enriched["lineups_status"] = gamecenter_data.get("LineupsStatusText") or "Confirmed Lineups"
                    logger.info(f"Extracted lineups from GameCenter for game {game.gid}")
            
            # Extract betting odds from GameCenter
            if "MainOdds" in gamecenter_data or "main_odds" in gamecenter_data:
                main_odds = gamecenter_data.get("MainOdds") or gamecenter_data.get("main_odds")
                if main_odds:
                    enriched["betting"] = self._extract_betting_from_gamecenter(main_odds, gamecenter_data)
                    logger.info(f"Extracted betting odds from GameCenter for game {game.gid}")
            
            # Extract news from GameCenter
            metadata = gamecenter_data.get("_gamecenter_metadata", {})
            news_items = metadata.get("news", [])
            if not news_items:
                news_items = gamecenter_data.get("News", []) or gamecenter_data.get("news", [])
            
            if news_items:
                enriched["news"] = self._extract_news_from_gamecenter(news_items)
                enriched["news_count"] = len(enriched["news"])
                logger.info(f"Extracted {len(enriched['news'])} news items from GameCenter for game {game.gid}")
            
            # Extract standings from GameCenter
            competitions = metadata.get("competitions", [])
            if competitions and game.competition_id:
                standings_data = self._extract_standings_from_gamecenter(competitions, game.competition_id)
                if standings_data:
                    enriched["standings"] = self._format_standings(standings_data, game)
                    logger.info(f"Extracted standings from GameCenter for competition {game.competition_id}")

        # Fetch detailed statistics (fallback)
        stats = await self.game_fetcher.fetch_game_statistics(game.gid)
        if stats:
            enriched["detailed_statistics"] = stats

        # Fallback: Fetch league standings if not found in GameCenter
        if not enriched.get("standings") and game.competition_id:
            try:
                standings = await self.game_fetcher.fetch_standings(game.competition_id)
                enriched["standings"] = self._format_standings(standings, game)
                logger.info(f"Fetched standings for competition {game.competition_id}")
            except Exception as e:
                logger.warning(f"Failed to fetch standings for game {game.gid}: {e}")
                enriched["standings"] = None

        # Fallback: Fetch news if not found in GameCenter
        if not enriched.get("news"):
            try:
                news_items = await self.news_fetcher.fetch_relevant_news(game, time_window_hours=48)
                enriched["news"] = [news.to_dict() for news in news_items]
                enriched["news_count"] = len(news_items)
                logger.info(f"Fetched {len(news_items)} relevant news items for post-game")
            except Exception as e:
                logger.warning(f"Failed to fetch news for game {game.gid}: {e}")
                enriched["news"] = []
                enriched["news_count"] = 0

        # Store enriched data
        context["game_data"] = enriched
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

    def _format_betting_result(self, bet_line, winner: Optional[int]) -> dict[str, Any]:
        """Format betting result (which options won)."""
        return {
            "type": bet_line.type,
            "winning_options": [
                opt.name for opt in bet_line.options if opt.won
            ],
            "match_winner": winner,
        }

    def _format_standings(
        self,
        standings_data: dict[str, Any],
        game: Game,
    ) -> dict[str, Any]:
        """
        Format standings data and extract relevant team positions.

        Args:
            standings_data: Raw standings from API
            game: Game object to extract team IDs

        Returns:
            Formatted standings with highlighted team positions
        """
        teams = standings_data.get("teams", [])
        if not teams:
            return None

        home_team_id = game.home_team.id if game.home_team else None
        away_team_id = game.away_team.id if game.away_team else None

        # Find home and away team positions
        home_team_position = None
        away_team_position = None
        home_team_data = None
        away_team_data = None

        for team in teams:
            if team.get("team_id") == home_team_id:
                home_team_position = team.get("position")
                home_team_data = team
            if team.get("team_id") == away_team_id:
                away_team_position = team.get("position")
                away_team_data = team

        # Get context around teams (teams above and below)
        home_context = self._get_standings_context(teams, home_team_position, 2)
        away_context = self._get_standings_context(teams, away_team_position, 2)

        formatted = {
            "competition_id": standings_data.get("competition_id"),
            "season_id": standings_data.get("season_id"),
            "table_name": standings_data.get("table_name"),
            "total_teams": standings_data.get("total_teams", len(teams)),
            "home_team": {
                "position": home_team_position,
                "points": home_team_data.get("points") if home_team_data else None,
                "played": home_team_data.get("played") if home_team_data else None,
                "wins": home_team_data.get("wins") if home_team_data else None,
                "draws": home_team_data.get("draws") if home_team_data else None,
                "losses": home_team_data.get("losses") if home_team_data else None,
                "goals_for": home_team_data.get("goals_for") if home_team_data else None,
                "goals_against": home_team_data.get("goals_against") if home_team_data else None,
                "goal_difference": home_team_data.get("goal_difference") if home_team_data else None,
                "form": home_team_data.get("form") if home_team_data else None,
            },
            "away_team": {
                "position": away_team_position,
                "points": away_team_data.get("points") if away_team_data else None,
                "played": away_team_data.get("played") if away_team_data else None,
                "wins": away_team_data.get("wins") if away_team_data else None,
                "draws": away_team_data.get("draws") if away_team_data else None,
                "losses": away_team_data.get("losses") if away_team_data else None,
                "goals_for": away_team_data.get("goals_for") if away_team_data else None,
                "goals_against": away_team_data.get("goals_against") if away_team_data else None,
                "goal_difference": away_team_data.get("goal_difference") if away_team_data else None,
                "form": away_team_data.get("form") if away_team_data else None,
            },
            "position_difference": (
                abs(home_team_position - away_team_position)
                if home_team_position and away_team_position
                else None
            ),
            "home_context": home_context,  # Teams around home team
            "away_context": away_context,  # Teams around away team
            "top_three": [t for t in teams[:3] if t.get("position")],  # Top 3 teams
            "bottom_three": [t for t in teams[-3:] if t.get("position")],  # Bottom 3 teams
        }

        return formatted

    def _extract_lineups_from_gamecenter(self, lineups_data: list[dict[str, Any]]) -> dict[str, Any]:
        """Extract and format lineups from GameCenter response."""
        formatted: dict[str, Any] = {"home": None, "away": None}
        
        for lineup in lineups_data:
            # Determine team (0=home, 1=away)
            comp_num = lineup.get("CompNum") or lineup.get("comp_num", 0)
            team_key = "home" if comp_num == 0 else "away"
            
            players = lineup.get("Players") or lineup.get("players", [])
            formatted[team_key] = {
                "formation": lineup.get("Formation") or lineup.get("formation"),
                "players": [
                    {
                        "name": p.get("Name") or p.get("name"),
                        "position": p.get("PositionName") or p.get("position_name"),
                        "number": p.get("ShirtNumber") or p.get("shirt_number"),
                        "is_captain": p.get("IsCaptain") or p.get("is_captain", False),
                    }
                    for p in players
                ],
            }
        
        return formatted
    
    def _extract_betting_from_gamecenter(self, main_odds: dict[str, Any], gamecenter_data: dict[str, Any]) -> dict[str, Any]:
        """Extract and format betting odds from GameCenter response."""
        options = main_odds.get("Options") or main_odds.get("options", [])
        
        # Also check for BetLine in GameCenter
        bet_line = gamecenter_data.get("BetLine") or gamecenter_data.get("bet_line")
        if bet_line:
            bet_options = bet_line.get("Options") or bet_line.get("options", [])
            if bet_options:
                options = bet_options
        
        return {
            "type": main_odds.get("Type") or main_odds.get("type", 1),  # 1=Full-time Result
            "bookmaker_id": main_odds.get("BMID") or main_odds.get("bm_id"),
            "options": [
                {
                    "name": opt.get("Name") or opt.get("name"),
                    "odds": opt.get("Rate") or opt.get("rate"),
                    "original_rate": opt.get("OriginalRate") or opt.get("original_rate"),
                    "old_rate": opt.get("OldRate") or opt.get("old_rate"),
                    "trend": opt.get("Trend") or opt.get("trend"),
                    "won": opt.get("Won") or opt.get("won", False),
                }
                for opt in options
            ],
            "over_under_line": main_odds.get("OverUnder") or main_odds.get("overunder"),
        }
    
    def _extract_news_from_gamecenter(self, news_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract and format news from GameCenter response."""
        formatted_news = []
        
        for news in news_items:
            # Extract news article data
            formatted_news.append({
                "id": news.get("ID") or news.get("id"),
                "title": news.get("Title") or news.get("title"),
                "summary": news.get("Summary") or news.get("summary"),
                "url": news.get("URL") or news.get("url") or news.get("WebUrl") or news.get("web_url"),
                "image_url": news.get("ImageURL") or news.get("image_url"),
                "published_date": news.get("PublishedDate") or news.get("published_date"),
                "source": news.get("Source") or news.get("source"),
            })
        
        return formatted_news
    
    def _extract_standings_from_gamecenter(self, competitions: list[dict[str, Any]], competition_id: int) -> Optional[dict[str, Any]]:
        """Extract standings from GameCenter competitions data."""
        for comp in competitions:
            comp_id = comp.get("ID") or comp.get("id")
            if comp_id == competition_id:
                # Check for standings/table data
                if "Standings" in comp or "standings" in comp:
                    standings = comp.get("Standings") or comp.get("standings", [])
                    return {
                        "teams": self._extract_teams_from_standings_list(standings),
                        "competition_id": competition_id,
                        "season_id": comp.get("SeasonID") or comp.get("season_id"),
                    }
                elif "Tables" in comp or "tables" in comp:
                    tables = comp.get("Tables") or comp.get("tables", [])
                    if tables:
                        first_table = tables[0]
                        standings = first_table.get("Standings") or first_table.get("standings", [])
                        return {
                            "teams": self._extract_teams_from_standings_list(standings),
                            "competition_id": competition_id,
                            "season_id": comp.get("SeasonID") or comp.get("season_id"),
                            "table_name": first_table.get("Name") or first_table.get("name"),
                        }
        
        return None
    
    def _extract_teams_from_standings_list(self, standings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract team data from standings list."""
        teams = []
        
        for item in standings:
            team_id = item.get("TeamID") or item.get("TeamId") or item.get("ID") or item.get("Id")
            team_name = item.get("Team") or item.get("TeamName") or item.get("Name")
            position = item.get("Position") or item.get("Pos") or item.get("Rank")
            
            if team_id and team_name:
                teams.append({
                    "team_id": int(team_id),
                    "team_name": str(team_name),
                    "position": int(position) if position is not None else None,
                    "points": item.get("Points") or item.get("Pts"),
                    "played": item.get("Played") or item.get("P"),
                    "wins": item.get("Wins") or item.get("W"),
                    "draws": item.get("Draws") or item.get("D"),
                    "losses": item.get("Losses") or item.get("L"),
                    "goals_for": item.get("GoalsFor") or item.get("GF"),
                    "goals_against": item.get("GoalsAgainst") or item.get("GA"),
                    "goal_difference": item.get("GoalDifference") or item.get("GD"),
                })
        
        # Sort by position
        teams.sort(key=lambda x: x["position"] if x["position"] is not None else 999)
        return teams
    
    def _extract_pregame_stats_from_response(self, stats_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract pre-game statistics from PreGame Statistics API response."""
        stats = []
        
        # Handle different response structures
        stats_list = stats_data.get("Statistics") or stats_data.get("statistics") or stats_data.get("Stats") or stats_data.get("stats")
        if not stats_list and isinstance(stats_data, list):
            stats_list = stats_data
        
        if stats_list:
            for stat in stats_list:
                stats.append({
                    "name": stat.get("Name") or stat.get("name"),
                    "values": stat.get("Values") or stat.get("values") or stat.get("Vals") or stat.get("vals"),
                    "percentages": stat.get("Percentages") or stat.get("percentages") or stat.get("ValsPct") or stat.get("vals_pct"),
                })
        
        return stats

    def _get_standings_context(
        self,
        teams: list[dict[str, Any]],
        team_position: Optional[int],
        context_size: int = 2,
    ) -> Optional[dict[str, Any]]:
        """
        Get teams around a specific position in the standings.

        Args:
            teams: List of team standings
            team_position: Position of the team
            context_size: Number of teams above and below to include

        Returns:
            Dictionary with teams above, at, and below the position
        """
        if team_position is None:
            return None

        # Find teams in the context range
        above = []
        below = []
        current = None

        for team in teams:
            pos = team.get("position")
            if pos is None:
                continue

            if pos == team_position:
                current = team
            elif pos < team_position and pos >= team_position - context_size:
                above.append(team)
            elif pos > team_position and pos <= team_position + context_size:
                below.append(team)

        return {
            "above": sorted(above, key=lambda x: x.get("position", 0)),
            "current": current,
            "below": sorted(below, key=lambda x: x.get("position", 0)),
        }
