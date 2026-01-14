"""365Scores API client for fetching game data."""

import logging
from typing import Any, Optional

import httpx

from src.config import Settings, get_settings
from src.exceptions import DataFetchError
from src.models import Game, ScoresData
from src.utils import with_retry

logger = logging.getLogger(__name__)


class GameFetcher:
    """
    Fetches game data from 365Scores Mobile API.

    Based on iOS MobileAPIRequest.swift patterns:
    - Base URL: https://mobileapi.365scores.com
    - Games endpoint: /data/games
    - Statistics endpoint: /data/games/gamecenter/statistics/all
    """

    GAMES_PATH = "/data/games"
    STATISTICS_PATH = "/data/games/gamecenter/statistics/all"
    GAME_CENTER_PATH = "/data/games/gamecenter"

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.scores_api_base_url
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    def _get_base_params(self) -> dict[str, str]:
        """Get base parameters for all API requests."""
        return {
            "langId": str(self.settings.scores_api_language),
            "tz": str(self.settings.scores_api_timezone),
            "apptype": "4",  # iOS app type from the codebase
        }

    @with_retry(
        max_attempts=3,
        initial_delay=0.5,
        exceptions=(httpx.TimeoutException, httpx.HTTPStatusError),
    )
    async def fetch_games(
        self,
        game_ids: list[int],
        with_main_odds: bool = True,
        with_odds_previews: bool = True,
    ) -> list[Game]:
        """
        Fetch games by IDs from 365Scores API.

        Args:
            game_ids: List of game IDs to fetch
            with_main_odds: Include main betting odds
            with_odds_previews: Include odds preview data

        Returns:
            List of Game objects

        Raises:
            DataFetchError: If the API request fails
        """
        if not game_ids:
            return []

        params = self._get_base_params()
        params["Games"] = ",".join(str(gid) for gid in game_ids)

        if with_main_odds:
            params["withmainodds"] = "true"
        if with_odds_previews:
            params["WithOddsPreviews"] = "true"

        url = f"{self.base_url}{self.GAMES_PATH}"

        logger.info(f"Fetching {len(game_ids)} games from 365Scores API")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                scores_data = ScoresData.model_validate(data)

                logger.info(f"Successfully fetched {len(scores_data.games)} games")
                return scores_data.games

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching games: {e.response.status_code}")
            raise DataFetchError(
                message=f"API returned status {e.response.status_code}",
                game_ids=[str(gid) for gid in game_ids],
                status_code=e.response.status_code,
                cause=e,
            )
        except httpx.RequestError as e:
            logger.error(f"Request error fetching games: {e}")
            raise DataFetchError(
                message="Failed to connect to 365Scores API",
                game_ids=[str(gid) for gid in game_ids],
                cause=e,
            )
        except Exception as e:
            logger.error(f"Unexpected error fetching games: {e}")
            raise DataFetchError(
                message=f"Unexpected error: {str(e)}",
                game_ids=[str(gid) for gid in game_ids],
                cause=e,
            )

    @with_retry(
        max_attempts=3,
        initial_delay=0.5,
        exceptions=(httpx.TimeoutException, httpx.HTTPStatusError),
    )
    async def fetch_game_statistics(self, game_id: int) -> dict[str, Any]:
        """
        Fetch detailed statistics for a single game.

        Args:
            game_id: The game ID to fetch statistics for

        Returns:
            Dictionary containing statistics data

        Raises:
            DataFetchError: If the API request fails
        """
        params = self._get_base_params()
        params["gameid"] = str(game_id)

        url = f"{self.base_url}{self.STATISTICS_PATH}"

        logger.debug(f"Fetching statistics for game {game_id}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()

        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch statistics for game {game_id}: {e.response.status_code}")
            return {}
        except Exception as e:
            logger.warning(f"Error fetching statistics for game {game_id}: {e}")
            return {}

    @with_retry(
        max_attempts=3,
        initial_delay=0.5,
        exceptions=(httpx.TimeoutException, httpx.HTTPStatusError),
    )
    async def fetch_game_center(self, game_id: int) -> Optional[Game]:
        """
        Fetch full game center data for a single game.

        This provides more detailed data including lineups, events, and statistics.

        Args:
            game_id: The game ID to fetch

        Returns:
            Game object with full details, or None if not found

        Raises:
            DataFetchError: If the API request fails
        """
        params = self._get_base_params()
        params["gameid"] = str(game_id)
        params["withmainodds"] = "true"
        params["WithOddsPreviews"] = "true"

        url = f"{self.base_url}{self.GAME_CENTER_PATH}"

        logger.debug(f"Fetching game center for game {game_id}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                # Game center can return data in different structures:
                # 1. {"Game": {...}} - game data under Game key
                # 2. {"Games": [{...}]} - game data in Games array
                # 3. Direct game data at root level
                game_data = None

                if "Game" in data and isinstance(data["Game"], dict):
                    game_data = data["Game"]
                elif "Games" in data and isinstance(data["Games"], list) and data["Games"]:
                    game_data = data["Games"][0]
                elif "ID" in data:
                    game_data = data

                if not game_data:
                    logger.debug(f"Game center response has unexpected structure for {game_id}")
                    return None

                return Game.model_validate(game_data)

        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch game center for {game_id}: {e.response.status_code}")
            return None
        except Exception as e:
            logger.debug(f"Could not parse game center for {game_id}: {e}")
            return None

    async def fetch_featured_games(
        self,
        country_id: Optional[int] = None,
        limit: int = 10,
    ) -> list[Game]:
        """
        Fetch featured/editor's choice games for fallback.

        Args:
            country_id: User's country ID for localization
            limit: Maximum number of games to return

        Returns:
            List of featured games
        """
        params = self._get_base_params()
        params["withmainodds"] = "true"

        if country_id:
            params["uc"] = str(country_id)

        url = f"{self.base_url}{self.GAMES_PATH}"

        logger.info("Fetching featured games for fallback")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                scores_data = ScoresData.model_validate(data)

                # Filter for editors choice or featured games
                featured = [
                    g for g in scores_data.games
                    if hasattr(g, "editors_choice") or g.has_bets
                ]

                # Fallback to any available games
                if not featured:
                    featured = scores_data.games

                return featured[:limit]

        except Exception as e:
            logger.error(f"Failed to fetch featured games: {e}")
            return []
