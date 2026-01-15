"""Pre-generation scheduler for editors choice games."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.config import Settings, get_settings
from src.models import PodcastRequest
from src.services.job_store import get_job_store, JobStatus
from src.services.retrieval.game_fetcher import GameFetcher

logger = logging.getLogger(__name__)


class PodcastScheduler:
    """
    Schedules and manages automatic podcast pre-generation.

    Pre-generates podcasts for:
    - Editors choice games (featured games)
    - Games starting within the next few hours
    - Popular competitions
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        check_interval_minutes: int = 30,
        pre_generate_hours_ahead: int = 3,
    ):
        self.settings = settings or get_settings()
        self.check_interval = timedelta(minutes=check_interval_minutes)
        self.pre_generate_hours = pre_generate_hours_ahead

        self._game_fetcher = GameFetcher(settings)
        self._job_store = get_job_store()
        self._orchestrator = None  # Lazy load to avoid circular imports
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def _get_orchestrator(self):
        """Lazy load orchestrator to avoid circular imports."""
        if self._orchestrator is None:
            from src.services.orchestrator import PodcastOrchestrator
            self._orchestrator = PodcastOrchestrator()
        return self._orchestrator

    async def start(self) -> None:
        """Start the scheduler background task."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Podcast scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Podcast scheduler stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                await self._check_and_generate()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            # Wait for next check
            await asyncio.sleep(self.check_interval.total_seconds())

    async def _check_and_generate(self) -> None:
        """Check for games needing podcasts and generate them."""
        logger.info("Checking for games to pre-generate...")

        # Get editors choice games
        games = await self._fetch_editors_choice_games()

        if not games:
            logger.info("No editors choice games found")
            return

        logger.info(f"Found {len(games)} editors choice games")

        # Filter to games that don't have cached podcasts
        games_to_generate = []
        for game in games:
            cached = await self._job_store.get_cached_podcast(game.gid)
            if not cached:
                games_to_generate.append(game)

        if not games_to_generate:
            logger.info("All editors choice games already have podcasts")
            return

        logger.info(f"Generating podcasts for {len(games_to_generate)} games")

        # Generate podcasts for each game
        for game in games_to_generate:
            try:
                await self._generate_for_game(game)
                # Small delay between generations to avoid rate limits
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Failed to generate podcast for game {game.gid}: {e}")

    async def _fetch_editors_choice_games(self) -> list:
        """Fetch editors choice / featured games from 365Scores."""
        try:
            # Fetch featured games
            games = await self._game_fetcher.fetch_featured_games(limit=10)

            # Filter to games within our time window
            now = datetime.now(timezone.utc)
            cutoff_future = now + timedelta(hours=self.pre_generate_hours)
            cutoff_past = now - timedelta(hours=6)  # Include recent finished games

            filtered = []
            for game in games:
                start_time = game.start_datetime
                if start_time:
                    if cutoff_past <= start_time <= cutoff_future:
                        filtered.append(game)
                else:
                    # Include if no start time (might be live)
                    filtered.append(game)

            return filtered[:5]  # Limit to 5 games per run

        except Exception as e:
            logger.error(f"Failed to fetch editors choice games: {e}")
            return []

    async def _generate_for_game(self, game) -> None:
        """Generate podcast for a single game."""
        orchestrator = self._get_orchestrator()

        logger.info(f"Pre-generating podcast for game {game.gid}")

        # Get team names for logging
        home_name = game.home_team.name if game.home_team else "Home"
        away_name = game.away_team.name if game.away_team else "Away"
        logger.info(f"Generating: {home_name} vs {away_name}")

        # Create request
        request = PodcastRequest(
            game_ids=[str(game.gid)],
            format="panel",
            include_betting=True,
        )

        try:
            # Generate the podcast
            result = await orchestrator.generate_podcast(request)

            if result.status == "completed" and result.audio_url:
                # Cache the result
                await self._job_store.cache_podcast(
                    game_id=game.gid,
                    audio_url=result.audio_url,
                    duration_seconds=result.duration_seconds or 0,
                    mode=result.mode or "panel",
                    script=result.script,
                    ttl_hours=24,  # Cache for 24 hours
                )
                logger.info(f"Pre-generated and cached podcast for game {game.gid}")
            else:
                logger.warning(f"Generation did not complete for game {game.gid}")

        except Exception as e:
            logger.error(f"Pre-generation failed for game {game.gid}: {e}")

    async def generate_for_game_now(self, game_id: int) -> Optional[str]:
        """
        Manually trigger generation for a specific game.

        Returns audio URL if successful, None otherwise.
        """
        orchestrator = self._get_orchestrator()

        # Check cache first
        cached = await self._job_store.get_cached_podcast(game_id)
        if cached:
            logger.info(f"Game {game_id} already has cached podcast")
            return cached.audio_url

        # Generate
        request = PodcastRequest(
            game_ids=[str(game_id)],
            format="panel",
            include_betting=True,
        )

        try:
            result = await orchestrator.generate_podcast(request)

            if result.status == "completed" and result.audio_url:
                # Cache the result
                await self._job_store.cache_podcast(
                    game_id=game_id,
                    audio_url=result.audio_url,
                    duration_seconds=result.duration_seconds or 0,
                    mode=result.mode or "panel",
                    script=result.script,
                )
                return result.audio_url

        except Exception as e:
            logger.error(f"On-demand generation failed for game {game_id}: {e}")

        return None


# Global scheduler instance
_scheduler: Optional[PodcastScheduler] = None


def get_scheduler() -> PodcastScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = PodcastScheduler()
    return _scheduler
