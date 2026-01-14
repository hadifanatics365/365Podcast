"""Content routing logic for determining podcast generation mode."""

import logging
from datetime import datetime, timezone

from src.models import ContentMode, Game, GameStatus
from src.utils import is_within_hours

logger = logging.getLogger(__name__)


class ContentRouter:
    """
    Determines the appropriate content generation mode based on game selection.

    Implements the dynamic routing logic:
    - > 1 game → Daily Recap Mode
    - == 1 game, not started → Game Spotlight Pre-game
    - == 1 game, finished → Game Spotlight Post-game
    """

    def determine_mode(self, games: list[Game]) -> ContentMode:
        """
        Determine the content mode based on game selection.

        Args:
            games: List of games to analyze

        Returns:
            ContentMode enum value
        """
        if not games:
            logger.warning("No games provided, defaulting to Daily Recap")
            return ContentMode.DAILY_RECAP

        if len(games) > 1:
            logger.info(f"Multiple games ({len(games)}), using Daily Recap mode")
            return ContentMode.DAILY_RECAP

        # Single game - determine pre/post game
        game = games[0]
        status = game.gt

        if GameStatus.is_upcoming(status):
            logger.info(f"Single pre-game spotlight for game {game.gid}")
            return ContentMode.GAME_SPOTLIGHT_PREGAME

        if GameStatus.is_finished(status):
            logger.info(f"Single post-game spotlight for game {game.gid}")
            return ContentMode.GAME_SPOTLIGHT_POSTGAME

        if GameStatus.is_live(status):
            # Live games treated as post-game (focus on current action)
            logger.info(f"Live game {game.gid}, treating as post-game spotlight")
            return ContentMode.GAME_SPOTLIGHT_POSTGAME

        # Default to post-game for unknown status
        logger.info(f"Unknown status {status} for game {game.gid}, defaulting to post-game")
        return ContentMode.GAME_SPOTLIGHT_POSTGAME

    def categorize_games_for_recap(
        self,
        games: list[Game],
        hours_back: int = 24,
        hours_forward: int = 24,
    ) -> dict[str, list[Game]]:
        """
        Categorize games for Daily Recap mode.

        Args:
            games: List of games to categorize
            hours_back: Hours to look back for ended games
            hours_forward: Hours to look forward for upcoming games

        Returns:
            Dictionary with categorized games:
            - ended_games: Finished in past N hours
            - upcoming_games: Starting in next N hours
            - live_games: Currently active
        """
        now = datetime.now(timezone.utc)

        categorized: dict[str, list[Game]] = {
            "ended_games": [],
            "upcoming_games": [],
            "live_games": [],
        }

        for game in games:
            status = game.gt

            if GameStatus.is_live(status):
                categorized["live_games"].append(game)
            elif GameStatus.is_finished(status):
                # Check if within time window
                if game.start_datetime and is_within_hours(
                    game.start_datetime, hours_back, future=False
                ):
                    categorized["ended_games"].append(game)
                else:
                    # Include anyway if no time check possible
                    categorized["ended_games"].append(game)
            elif GameStatus.is_upcoming(status):
                if game.start_datetime and is_within_hours(
                    game.start_datetime, hours_forward, future=True
                ):
                    categorized["upcoming_games"].append(game)
                else:
                    # Include anyway if no time check possible
                    categorized["upcoming_games"].append(game)

        # Sort by time
        categorized["ended_games"].sort(
            key=lambda g: g.start_datetime or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,  # Most recent first
        )
        categorized["upcoming_games"].sort(
            key=lambda g: g.start_datetime or datetime.max.replace(tzinfo=timezone.utc),
        )

        logger.info(
            f"Categorized {len(games)} games: "
            f"{len(categorized['ended_games'])} ended, "
            f"{len(categorized['live_games'])} live, "
            f"{len(categorized['upcoming_games'])} upcoming"
        )

        return categorized

    def get_content_priorities(self, mode: ContentMode) -> list[str]:
        """
        Get content priorities for a given mode.

        Args:
            mode: Content generation mode

        Returns:
            List of content priorities in order of importance
        """
        if mode == ContentMode.DAILY_RECAP:
            return [
                "match_results",
                "key_moments",
                "standings_impact",
                "upcoming_previews",
                "betting_context",
            ]
        elif mode == ContentMode.GAME_SPOTLIGHT_PREGAME:
            return [
                "match_introduction",
                "lineups",
                "form_analysis",
                "head_to_head",
                "betting_preview",
                "key_matchups",
                "prediction",
            ]
        elif mode == ContentMode.GAME_SPOTLIGHT_POSTGAME:
            return [
                "final_score",
                "key_moments",
                "man_of_match",
                "statistics",
                "player_performances",
                "standings_impact",
                "next_fixtures",
                "betting_recap",
            ]
        else:
            return []

    def should_include_betting(
        self,
        games: list[Game],
        include_betting: bool = True,
    ) -> bool:
        """
        Determine if betting content should be included.

        Args:
            games: List of games
            include_betting: User preference

        Returns:
            True if betting content should be included
        """
        if not include_betting:
            return False

        # Check if any game has betting data
        return any(game.has_bets or game.main_odds for game in games)
