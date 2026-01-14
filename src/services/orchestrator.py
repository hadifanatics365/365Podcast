"""Main orchestrator for podcast generation workflow."""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from src.config import Settings, get_settings
from src.exceptions import DataFetchError, PodcastGenerationError
from src.models import ContentMode, Game, PodcastRequest
from src.services.audio_manager import AudioStorage, AudioSynthesizer
from src.services.retrieval import DataEnricher, GameFetcher
from src.services.script_engine import ContentRouter, ScriptGenerator, SSMLProcessor

logger = logging.getLogger(__name__)


@dataclass
class PodcastResult:
    """Result of podcast generation."""

    job_id: str
    status: str
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    script: Optional[str] = None
    mode: Optional[str] = None
    games_count: int = 0
    created_at: str = ""
    error_message: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class PodcastOrchestrator:
    """
    Orchestrates the complete podcast generation workflow.

    Workflow:
    1. Fetch game data from 365Scores API
    2. Determine content mode (Daily Recap vs Game Spotlight)
    3. Enrich data with additional context
    4. Generate script via Claude
    5. Synthesize audio via ElevenLabs
    6. Store and return audio URL
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        game_fetcher: Optional[GameFetcher] = None,
        data_enricher: Optional[DataEnricher] = None,
        content_router: Optional[ContentRouter] = None,
        script_generator: Optional[ScriptGenerator] = None,
        audio_synthesizer: Optional[AudioSynthesizer] = None,
        audio_storage: Optional[AudioStorage] = None,
    ):
        self.settings = settings or get_settings()

        # Initialize services
        self.game_fetcher = game_fetcher or GameFetcher(self.settings)
        self.data_enricher = data_enricher or DataEnricher(self.game_fetcher)
        self.content_router = content_router or ContentRouter()
        self.script_generator = script_generator or ScriptGenerator(self.settings)
        self.ssml_processor = SSMLProcessor()
        self.audio_synthesizer = audio_synthesizer or AudioSynthesizer(self.settings)
        self.audio_storage = audio_storage or AudioStorage(self.settings)

    async def generate_podcast(
        self,
        request: PodcastRequest,
    ) -> PodcastResult:
        """
        Generate a complete podcast from a request.

        Args:
            request: PodcastRequest with game_ids and options

        Returns:
            PodcastResult with audio URL and metadata

        Raises:
            PodcastGenerationError: If any step fails
        """
        job_id = self._generate_job_id()
        logger.info(f"Starting podcast generation job {job_id} for {len(request.game_ids)} games")

        try:
            # Step 1: Fetch game data
            games = await self._fetch_games(request.game_ids)

            if not games:
                # Fallback to featured games if none found
                logger.warning("No games found, fetching featured games")
                games = await self.game_fetcher.fetch_featured_games(
                    country_id=request.user_country_id,
                    limit=5,
                )

            if not games:
                raise DataFetchError(
                    message="No games available for podcast",
                    game_ids=request.game_ids,
                )

            # Step 2: Determine content mode
            mode = self._determine_mode(games, request)
            logger.info(f"Content mode: {mode.value}")

            # Step 3: Enrich data
            context = await self.data_enricher.enrich_games(games, mode)

            # Step 4: Generate script
            script = await self.script_generator.generate_script(
                context=context,
                mode=mode,
                include_betting=request.include_betting,
            )

            # Step 5: Synthesize audio
            voice_id = self.audio_synthesizer.get_voice_id(request.voice_id)
            audio_bytes = await self.audio_synthesizer.synthesize(
                script=script,
                voice_id=voice_id,
            )

            # Step 6: Store audio
            metadata = {
                "game_ids": [int(gid) for gid in request.game_ids],
                "mode": mode.value,
                "language": request.language,
            }
            audio_url = await self.audio_storage.store_audio(
                audio_bytes=audio_bytes,
                job_id=job_id,
                metadata=metadata,
            )

            # Calculate duration
            duration = self.ssml_processor.estimate_duration(script)

            logger.info(f"Podcast generation complete: {job_id}")

            return PodcastResult(
                job_id=job_id,
                status="completed",
                audio_url=audio_url,
                duration_seconds=duration,
                script=script,
                mode=mode.value,
                games_count=len(games),
            )

        except PodcastGenerationError:
            raise
        except Exception as e:
            logger.error(f"Podcast generation failed: {e}")
            raise PodcastGenerationError(
                message=f"Podcast generation failed: {str(e)}",
                details={"job_id": job_id, "game_ids": request.game_ids},
                cause=e,
            )

    async def _fetch_games(self, game_ids: list[str]) -> list[Game]:
        """Fetch games by IDs."""
        # Convert to integers
        int_ids = []
        for gid in game_ids:
            try:
                int_ids.append(int(gid))
            except ValueError:
                logger.warning(f"Invalid game ID: {gid}")

        if not int_ids:
            return []

        return await self.game_fetcher.fetch_games(
            game_ids=int_ids,
            with_main_odds=True,
            with_odds_previews=True,
        )

    def _determine_mode(
        self,
        games: list[Game],
        request: PodcastRequest,
    ) -> ContentMode:
        """Determine content mode based on games and request."""
        from src.models import PodcastMode

        # Check if mode is explicitly specified
        if request.mode == PodcastMode.DAILY_RECAP:
            return ContentMode.DAILY_RECAP
        elif request.mode == PodcastMode.GAME_SPOTLIGHT:
            # Determine pre/post game for single game
            if games:
                from src.models import GameStatus
                if GameStatus.is_upcoming(games[0].gt):
                    return ContentMode.GAME_SPOTLIGHT_PREGAME
                else:
                    return ContentMode.GAME_SPOTLIGHT_POSTGAME
            return ContentMode.GAME_SPOTLIGHT_POSTGAME

        # Auto mode - let router decide
        return self.content_router.determine_mode(games)

    def _generate_job_id(self) -> str:
        """Generate unique job ID."""
        return f"pod_{uuid.uuid4().hex[:12]}"

    async def get_job_status(self, job_id: str) -> Optional[dict[str, Any]]:
        """
        Get status of a generation job.

        Note: In production, this would query a job queue/database.
        For now, returns None (job tracking not implemented).
        """
        # TODO: Implement job tracking with Redis
        return None


# Convenience function for simple usage
async def generate_podcast(
    game_ids: list[str],
    include_betting: bool = True,
    voice_id: Optional[str] = None,
) -> PodcastResult:
    """
    Simple interface for generating a podcast.

    Args:
        game_ids: List of game IDs
        include_betting: Include betting insights
        voice_id: Optional ElevenLabs voice ID

    Returns:
        PodcastResult with audio URL
    """
    request = PodcastRequest(
        game_ids=game_ids,
        include_betting=include_betting,
        voice_id=voice_id,
    )

    orchestrator = PodcastOrchestrator()
    return await orchestrator.generate_podcast(request)
