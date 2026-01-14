"""Fetches additional intelligence data from 365Scores API."""

import asyncio
import logging
from typing import Any, Optional

import httpx

from src.config import Settings, get_settings
from src.utils import with_retry

logger = logging.getLogger(__name__)


class IntelligenceFetcher:
    """
    Fetches additional data from 365Scores API endpoints
    for richer content intelligence.

    Endpoints:
    - /Data/Bets/Trends/ - Team form trends and streaks
    - /Data/Bets/Insights/ - Expert betting insights
    - /Data/games/Predictions/ - Community predictions
    """

    # API Paths
    TRENDS_PATH = "/Data/Bets/Trends/"
    INSIGHTS_PATH = "/Data/Bets/Insights/"
    PREDICTIONS_PATH = "/Data/games/Predictions/"

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.scores_api_base_url
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    def _get_base_params(self) -> dict[str, str]:
        """Get base API parameters."""
        return {
            "langId": str(self.settings.scores_api_language),
            "tz": str(self.settings.scores_api_timezone),
            "apptype": "4",
        }

    @with_retry(max_attempts=2, initial_delay=0.3)
    async def fetch_team_trends(
        self,
        game_id: int,
        top_bookmaker_id: int = 0,
    ) -> dict[str, Any]:
        """
        Fetch team trends from /Data/Bets/Trends/

        Returns data like:
        - Win/loss streaks
        - Goal scoring patterns
        - Historical betting trends
        - Competitor insights with pre-written text
        """
        params = self._get_base_params()
        params.update({
            "GameID": str(game_id),
            "TopBM": str(top_bookmaker_id),
            "ShowNAOdds": "true",
        })

        url = f"{self.base_url}{self.TRENDS_PATH}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                logger.debug(f"Fetched trends for game {game_id}: {len(data.get('Trends', []))} trends")
                return data
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error fetching trends for game {game_id}: {e.response.status_code}")
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch trends for game {game_id}: {e}")
            return {}

    @with_retry(max_attempts=2, initial_delay=0.3)
    async def fetch_betting_insights(
        self,
        game_id: int,
        top_bookmaker_id: int = 0,
    ) -> dict[str, Any]:
        """
        Fetch expert betting insights from /Data/Bets/Insights/

        Returns:
        - Expert predictions with pre-written text
        - Provider attributions (Opta, etc.)
        - Related odds
        - Likes/dislikes for community validation
        """
        params = self._get_base_params()
        params.update({
            "GameID": str(game_id),
            "TopBM": str(top_bookmaker_id),
            "ShowNAOdds": "true",
        })

        url = f"{self.base_url}{self.INSIGHTS_PATH}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                logger.debug(f"Fetched insights for game {game_id}: {len(data.get('Insights', []))} insights")
                return data
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error fetching insights for game {game_id}: {e.response.status_code}")
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch insights for game {game_id}: {e}")
            return {}

    @with_retry(max_attempts=2, initial_delay=0.3)
    async def fetch_predictions(
        self,
        game_id: int,
        top_bookmaker_id: int = 0,
    ) -> dict[str, Any]:
        """
        Fetch community predictions from /Data/games/Predictions/

        Returns:
        - Vote counts per option
        - Vote percentages
        - Related betting lines
        - Records text (historical accuracy)
        """
        params = self._get_base_params()
        params.update({
            "GameID": str(game_id),
            "TopBM": str(top_bookmaker_id),
            "ShowNAOdds": "true",
            "oddsformat": "-1",
        })

        url = f"{self.base_url}{self.PREDICTIONS_PATH}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                logger.debug(f"Fetched predictions for game {game_id}")
                return data
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error fetching predictions for game {game_id}: {e.response.status_code}")
            return {}
        except Exception as e:
            logger.warning(f"Failed to fetch predictions for game {game_id}: {e}")
            return {}

    async def fetch_all_intelligence(
        self,
        game_id: int,
        top_bookmaker_id: int = 0,
    ) -> dict[str, Any]:
        """
        Fetch all intelligence data for a game in parallel.

        Returns dict with keys: trends, insights, predictions
        """
        logger.info(f"Fetching intelligence for game {game_id}")

        results = await asyncio.gather(
            self.fetch_team_trends(game_id, top_bookmaker_id),
            self.fetch_betting_insights(game_id, top_bookmaker_id),
            self.fetch_predictions(game_id, top_bookmaker_id),
            return_exceptions=True,
        )

        return {
            "trends": results[0] if not isinstance(results[0], Exception) else {},
            "insights": results[1] if not isinstance(results[1], Exception) else {},
            "predictions": results[2] if not isinstance(results[2], Exception) else {},
        }
