"""News fetcher for 365Scores API with relevance filtering."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from src.config import Settings, get_settings
from src.models import Game, GameStatus
from src.utils import with_retry

logger = logging.getLogger(__name__)


class NewsItem:
    """Represents a single news item."""

    def __init__(self, data: dict[str, Any]):
        self.id = data.get("ID") or data.get("id")
        self.title = data.get("Title") or data.get("title", "")
        self.text = data.get("Text") or data.get("text", "")
        self.summary = data.get("Summary") or data.get("summary", "")
        self.publish_date = self._parse_date(data.get("Date") or data.get("date") or data.get("PublishDate"))
        self.image_url = data.get("Image") or data.get("image") or data.get("ImageUrl")
        self.source = data.get("Source") or data.get("source", "365Scores")
        self.category = data.get("Category") or data.get("category")
        self.team_ids = data.get("TeamIDs") or data.get("team_ids", [])
        self.player_ids = data.get("PlayerIDs") or data.get("player_ids", [])
        self.game_id = data.get("GameID") or data.get("game_id")
        self.competition_id = data.get("CompetitionID") or data.get("competition_id")
        self.relevance_score = 0.0  # Will be calculated

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
        try:
            # Try ISO format
            if "T" in date_str or "Z" in date_str:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            # Try other common formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M"]:
                try:
                    return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "text": self.text,
            "summary": self.summary,
            "publish_date": self.publish_date.isoformat() if self.publish_date else None,
            "image_url": self.image_url,
            "source": self.source,
            "category": self.category,
            "relevance_score": self.relevance_score,
        }


class NewsFetcher:
    """
    Fetches and filters relevant news from 365Scores API.

    Relevance criteria:
    - News mentions game teams (by name or ID)
    - News mentions key players from the game
    - News is about the same competition
    - News is about the specific game
    - News is within the time window (last 24h for scheduled, after match for finished)
    """

    # Common 365Scores news endpoints (may vary)
    NEWS_PATH = "/data/news"
    GAME_NEWS_PATH = "/data/games/news"
    TEAM_NEWS_PATH = "/data/teams/news"

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.scores_api_base_url
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    def _get_base_params(self) -> dict[str, str]:
        """Get base parameters for all API requests."""
        return {
            "langId": str(self.settings.scores_api_language),
            "tz": str(self.settings.scores_api_timezone),
            "apptype": "4",
        }

    @with_retry(
        max_attempts=3,
        initial_delay=0.5,
        exceptions=(httpx.TimeoutException, httpx.HTTPStatusError),
    )
    async def fetch_game_news(
        self,
        game_id: int,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Fetch news related to a specific game.

        Args:
            game_id: Game ID
            limit: Maximum number of news items to fetch

        Returns:
            List of news items
        """
        params = self._get_base_params()
        params["gameid"] = str(game_id)
        params["limit"] = str(limit)

        url = f"{self.base_url}{self.GAME_NEWS_PATH}"

        logger.debug(f"Fetching news for game {game_id}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                # Handle different response structures
                news_list = data.get("News") or data.get("news") or data.get("Items") or []
                return news_list if isinstance(news_list, list) else []

        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch game news for {game_id}: {e.response.status_code}")
            return []
        except Exception as e:
            logger.warning(f"Error fetching game news for {game_id}: {e}")
            return []

    @with_retry(
        max_attempts=3,
        initial_delay=0.5,
        exceptions=(httpx.TimeoutException, httpx.HTTPStatusError),
    )
    async def fetch_team_news(
        self,
        team_ids: list[int],
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Fetch news related to specific teams.

        Args:
            team_ids: List of team IDs
            limit: Maximum number of news items per team

        Returns:
            List of news items
        """
        all_news = []

        for team_id in team_ids:
            params = self._get_base_params()
            params["teamid"] = str(team_id)
            params["limit"] = str(limit)

            url = f"{self.base_url}{self.TEAM_NEWS_PATH}"

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    data = response.json()

                    news_list = data.get("News") or data.get("news") or data.get("Items") or []
                    if isinstance(news_list, list):
                        all_news.extend(news_list)

            except Exception as e:
                logger.warning(f"Error fetching news for team {team_id}: {e}")
                continue

        return all_news

    async def fetch_relevant_news(
        self,
        game: Game,
        time_window_hours: int = 24,
    ) -> list[NewsItem]:
        """
        Fetch and filter relevant news for a game.

        Args:
            game: Game object
            time_window_hours: Hours to look back for news (24 for scheduled, from match end for finished)

        Returns:
            List of relevant NewsItem objects, sorted by relevance
        """
        all_news_data = []

        # Determine time window
        now = datetime.now(timezone.utc)
        if GameStatus.is_finished(game.gt):
            # For finished games, get news from match end time onwards
            match_start_time = game.start_datetime
            if match_start_time:
                # Assume match duration ~2 hours (90 min + stoppage time)
                match_end_time = match_start_time + timedelta(hours=2, minutes=15)
                # Only get news published after match ended
                time_cutoff = match_end_time
                logger.info(
                    f"Finished game: fetching news from match end ({match_end_time.isoformat()}) onwards"
                )
            else:
                # Fallback: get news from last 48 hours
                time_cutoff = now - timedelta(hours=48)
                logger.info(f"Finished game (no start time): fetching news from last 48 hours")
        else:
            # For scheduled/upcoming games, get news from last 24 hours
            time_cutoff = now - timedelta(hours=time_window_hours)
            logger.info(f"Scheduled game: fetching news from last {time_window_hours} hours")

        logger.info(
            f"Fetching relevant news for game {game.gid} "
            f"(status: {game.gt}, time window: {time_cutoff.isoformat()} to {now.isoformat()})"
        )

        # Fetch news from multiple sources
        # 1. Game-specific news
        game_news = await self.fetch_game_news(game.gid, limit=50)
        all_news_data.extend(game_news)

        # 2. Team news
        team_ids = []
        if game.home_team:
            team_ids.append(game.home_team.id)
        if game.away_team:
            team_ids.append(game.away_team.id)

        if team_ids:
            team_news = await self.fetch_team_news(team_ids, limit=30)
            all_news_data.extend(team_news)

        # Convert to NewsItem objects and filter
        news_items = []
        for news_data in all_news_data:
            try:
                news_item = NewsItem(news_data)

                # Time filter
                if news_item.publish_date:
                    if news_item.publish_date < time_cutoff:
                        continue

                # Calculate relevance
                news_item.relevance_score = self._calculate_relevance(news_item, game)

                # Only include if relevant (score > 0)
                if news_item.relevance_score > 0:
                    news_items.append(news_item)

            except Exception as e:
                logger.warning(f"Failed to process news item: {e}")
                continue

        # Sort by relevance (highest first) and recency
        news_items.sort(
            key=lambda x: (
                x.relevance_score,
                x.publish_date.timestamp() if x.publish_date else 0,
            ),
            reverse=True,
        )

        # Limit to top 10 most relevant
        relevant_news = news_items[:10]

        logger.info(
            f"Found {len(relevant_news)} relevant news items "
            f"(from {len(all_news_data)} total, filtered by time and relevance)"
        )

        return relevant_news

    def _calculate_relevance(self, news_item: NewsItem, game: Game) -> float:
        """
        Calculate relevance score for a news item.

        Scoring:
        - Direct game mention: +10 points
        - Team ID match: +8 points per team
        - Team name mention: +5 points per team
        - Player mention: +3 points per player
        - Competition match: +4 points
        - Recency bonus: +1 point per hour within last 6 hours

        Returns:
            Relevance score (0.0 to 100.0)
        """
        score = 0.0

        # Direct game mention
        if news_item.game_id == game.gid:
            score += 10.0

        # Team ID matches
        home_team_id = game.home_team.id if game.home_team else None
        away_team_id = game.away_team.id if game.away_team else None

        if home_team_id and home_team_id in news_item.team_ids:
            score += 8.0
        if away_team_id and away_team_id in news_item.team_ids:
            score += 8.0

        # Team name mentions in title/text
        home_team_name = game.home_team.name.lower() if game.home_team else ""
        away_team_name = game.away_team.name.lower() if game.away_team else ""
        home_team_short = game.home_team.short_name.lower() if game.home_team and game.home_team.short_name else ""
        away_team_short = game.away_team.short_name.lower() if game.away_team and game.away_team.short_name else ""

        text_content = (news_item.title + " " + news_item.text + " " + news_item.summary).lower()

        if home_team_name and home_team_name in text_content:
            score += 5.0
        if away_team_name and away_team_name in text_content:
            score += 5.0
        if home_team_short and home_team_short in text_content:
            score += 3.0
        if away_team_short and away_team_short in text_content:
            score += 3.0

        # Player mentions (check top performers and key players)
        if game.has_top_performers and game.top_performers_data:
            for performer in game.top_performers_data:
                if performer.player_id and performer.player_id in news_item.player_ids:
                    score += 3.0
                if performer.player_name:
                    player_name_lower = performer.player_name.lower()
                    if player_name_lower in text_content:
                        score += 2.0

        # Competition match
        if game.competition_id and news_item.competition_id == game.competition_id:
            score += 4.0

        # Competition name mention
        if game.competition_display_name:
            comp_name_lower = game.competition_display_name.lower()
            if comp_name_lower in text_content:
                score += 2.0

        # Recency bonus (more recent = higher score)
        if news_item.publish_date:
            now = datetime.now(timezone.utc)
            hours_ago = (now - news_item.publish_date).total_seconds() / 3600
            if hours_ago <= 6:
                score += max(0, 6 - hours_ago)  # Up to 6 points for very recent news

        return min(score, 100.0)  # Cap at 100

    def _is_relevant_news(self, news_item: NewsItem, game: Game) -> bool:
        """
        Determine if news is relevant to the game.

        News is relevant if:
        1. Mentions the game directly (game_id match)
        2. Mentions either team (by ID or name)
        3. Mentions key players from the game
        4. Is about the same competition
        5. Is within the time window (checked separately)

        Args:
            news_item: News item to check
            game: Game to match against

        Returns:
            True if news is relevant
        """
        # Direct game match
        if news_item.game_id == game.gid:
            return True

        # Team matches
        home_team_id = game.home_team.id if game.home_team else None
        away_team_id = game.away_team.id if game.away_team else None

        if home_team_id in news_item.team_ids or away_team_id in news_item.team_ids:
            return True

        # Name matches in text
        text_content = (news_item.title + " " + news_item.text).lower()
        if game.home_team:
            if game.home_team.name.lower() in text_content:
                return True
            if game.home_team.short_name and game.home_team.short_name.lower() in text_content:
                return True
        if game.away_team:
            if game.away_team.name.lower() in text_content:
                return True
            if game.away_team.short_name and game.away_team.short_name.lower() in text_content:
                return True

        # Competition match
        if game.competition_id and news_item.competition_id == game.competition_id:
            return True

        return False
