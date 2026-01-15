"""Main orchestrator for podcast generation workflow."""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from src.config import Settings, get_settings
from src.exceptions import DataFetchError, HolyTriangleError, PodcastGenerationError
from src.models import ContentMode, Game, PodcastRequest
from src.models.requests import PodcastFormat, PodcastMode
from src.services.audio_manager import AudioMerger, AudioStorage, AudioSynthesizer
from src.services.audio_manager.multi_voice_synthesizer import MultiVoiceSynthesizer
from src.services.intelligence import ContentIntelligence
from src.services.lineup_agent import LineupAgent
from src.services.retrieval import DataEnricher, GameFetcher
from src.services.script_engine import ContentRouter, DialogueScriptArchitect, ScriptGenerator, SSMLProcessor

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
    format: Optional[str] = None
    games_count: int = 0
    created_at: str = ""
    error_message: Optional[str] = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class PodcastOrchestrator:
    """
    Orchestrates the complete podcast generation workflow following the 11-Step Pipeline.

    Supports two formats:
    - Single voice: Traditional single narrator podcast
    - Panel discussion: 3-person TV studio style with Host, Analyst, and Fan

    Workflow (11 Steps):
    1. Initialize & Validate
    2. Fetch Game Data
    3. Determine Content Mode
    4. Enrich Game Data
    5. Extract Content Intelligence
    6. Create Podcast Lineup (LineupAgent)
    7. Generate Dialogue Script (DialogueScriptArchitect with Holy Triangle verification)
    8. Synthesize Audio (ElevenLabs)
    9. Merge with Intro and Outro
    10. Store Audio File
    11. Copy to Project Directory (handled by caller)
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        game_fetcher: Optional[GameFetcher] = None,
        data_enricher: Optional[DataEnricher] = None,
        content_router: Optional[ContentRouter] = None,
        content_intelligence: Optional[ContentIntelligence] = None,
        script_generator: Optional[ScriptGenerator] = None,
        audio_synthesizer: Optional[AudioSynthesizer] = None,
        multi_voice_synthesizer: Optional[MultiVoiceSynthesizer] = None,
        audio_storage: Optional[AudioStorage] = None,
    ):
        self.settings = settings or get_settings()

        # Initialize services
        self.game_fetcher = game_fetcher or GameFetcher(self.settings)
        self.data_enricher = data_enricher or DataEnricher(self.game_fetcher)
        self.content_router = content_router or ContentRouter()
        self.content_intelligence = content_intelligence or ContentIntelligence(self.settings)
        self.script_generator = script_generator or ScriptGenerator(self.settings)
        self.lineup_agent = LineupAgent(self.settings)
        self.dialogue_architect = DialogueScriptArchitect(self.settings)
        self.ssml_processor = SSMLProcessor()
        self.audio_synthesizer = audio_synthesizer or AudioSynthesizer(self.settings)
        self.multi_voice_synthesizer = multi_voice_synthesizer or MultiVoiceSynthesizer(self.settings)
        self.audio_storage = audio_storage or AudioStorage(self.settings)
        self.audio_merger = AudioMerger(self.settings)

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
        is_panel = request.format == PodcastFormat.PANEL

        logger.info(
            f"[STEP 1] Starting podcast generation job {job_id} for {len(request.game_ids)} games "
            f"(format: {'panel' if is_panel else 'single_voice'})"
        )

        try:
            # STEP 1: Initialize & Validate
            logger.info("[STEP 1] Initialize & Validate")
            if self.settings.skip_audio_synthesis:
                logger.warning("[STEP 1] SKIP_AUDIO_SYNTHESIS is True - audio synthesis will be skipped")
            logger.info(f"[STEP 1] Validated game IDs: {request.game_ids}")

            # STEP 2: Fetch Game Data
            logger.info("[STEP 2] Fetch Game Data")
            games = await self._fetch_games(request.game_ids)

            if not games:
                # Fallback to featured games if none found
                logger.warning("[STEP 2] No games found, fetching featured games")
                games = await self.game_fetcher.fetch_featured_games(
                    country_id=request.user_country_id,
                    limit=5,
                )

            if not games:
                raise DataFetchError(
                    message="No games available for podcast",
                    game_ids=request.game_ids,
                )
            
            logger.info(f"[STEP 2] ✓ Fetched {len(games)} game(s)")

            # STEP 3: Determine Content Mode
            logger.info("[STEP 3] Determine Content Mode")
            mode = self._determine_mode(games, request)
            logger.info(f"[STEP 3] ✓ Content mode: {mode.value}")

            # STEP 4: Enrich Game Data
            logger.info("[STEP 4] Enrich Game Data")
            context = await self.data_enricher.enrich_games(games, mode)
            
            # CUSTOM DATA INJECTION for game 4452679
            if games[0].gid == 4452679:
                logger.info("[STEP 4] Injecting custom data for game 4452679")
                game_data = context.get("game_data") or context.get("games", [{}])[0]
                
                # Inject custom pre-game stats
                game_data["pre_game_stats"] = [
                    {
                        "name": "Recent Form",
                        "values": [
                            "Manchester City: Won 25 from latest 30 games",
                            "Manchester United: Lost 7 games from 25 games"
                        ]
                    },
                    {
                        "name": "Clean Sheets",
                        "values": [
                            "Manchester United: Only 2 clean sheets in 25 games",
                            "Manchester City: 13 clean sheets from 30 games"
                        ]
                    }
                ]
                
                # Inject custom key players
                game_data["key_players"] = [
                    {
                        "name": "Erling Haaland",
                        "team": "Manchester City",
                        "goals": 20,
                        "description": "Haaland scores 20 goals from the start of the season"
                    },
                    {
                        "name": "Benjamin Sesko",
                        "team": "Manchester United",
                        "goals": 4,
                        "description": "Sesko scores only 4 goals"
                    }
                ]
                
                # Inject custom standings
                game_data["standings"] = {
                    "home_team": {
                        "position": 7,
                        "points": 32,
                        "team_name": "Manchester United"
                    },
                    "away_team": {
                        "position": 2,
                        "points": 43,
                        "team_name": "Manchester City"
                    },
                    "position_difference": 5
                }
                
                # Inject custom betting odds (Sporting bet)
                # Format must match what LineupAgent expects
                game_data["betting"] = {
                    "type": 1,  # Full-time Result
                    "bookmaker": "Sporting bet",  # LineupAgent looks for "bookmaker" or "Bookmaker"
                    "Bookmaker": "Sporting bet",  # Also add capitalized version
                    "bookmaker_id": 161,  # Sporting bet ID
                    "options": [
                        {"name": "1", "rate": 3.58, "odds": 3.58, "description": "Manchester United Win", "Num": 1, "original_rate": 3.58},
                        {"name": "X", "rate": 3.78, "odds": 3.78, "description": "Draw", "Num": 2, "original_rate": 3.78},
                        {"name": "2", "rate": 1.94, "odds": 1.94, "description": "Manchester City Win", "Num": 3, "original_rate": 1.94}
                    ]
                }
                # Also add to context level for easier access
                context["betting"] = game_data["betting"]
                
                # Update context
                if "game_data" in context:
                    context["game_data"] = game_data
                if "games" in context and context["games"]:
                    context["games"][0] = game_data
                
                logger.info("[STEP 4] ✓ Custom data injected for game 4452679")
            
            # Validate PILLAR 1 (The WHAT): Enriched Data Context
            if not context:
                raise HolyTriangleError(
                    message="PILLAR 1 (Enriched Data Context) is missing",
                    missing_pillar="PILLAR_1",
                    pillar_details={"context_exists": False}
                )
            
            # Check minimum required data
            game_data = context.get("game") or (context.get("games", [{}])[0] if context.get("games") else {})
            if not game_data:
                raise HolyTriangleError(
                    message="PILLAR 1 (Enriched Data Context) missing basic game info",
                    missing_pillar="PILLAR_1",
                    pillar_details={"has_game_data": False}
                )
            
            logger.info("[STEP 4] ✓ Enriched data context created (PILLAR 1 verified)")

            # STEP 5: Extract Content Intelligence
            logger.info("[STEP 5] Extract Content Intelligence")
            intelligence = await self.content_intelligence.analyze(
                enriched_context=context,
                mode=mode,
                include_betting=request.include_betting,
            )
            logger.info(f"[STEP 5] ✓ Extracted {len(intelligence.top_stories)} top talking points")

            # STEP 6: Create Podcast Lineup
            logger.info("[STEP 6] Create Podcast Lineup (LineupAgent)")
            lineup = await self.lineup_agent.create_lineup(
                game_context=context,
                total_duration_minutes=5,  # Default duration
            )
            
            # Validate PILLAR 2 (The HOW): Structured Lineup & Timing
            if not lineup:
                raise HolyTriangleError(
                    message="PILLAR 2 (Structured Lineup) is missing",
                    missing_pillar="PILLAR_2",
                    pillar_details={"lineup_exists": False}
                )
            
            if not lineup.segments:
                raise HolyTriangleError(
                    message="PILLAR 2 (Structured Lineup) has no segments",
                    missing_pillar="PILLAR_2",
                    pillar_details={"segment_count": 0}
                )
            
            if not lineup.episode_title:
                raise HolyTriangleError(
                    message="PILLAR 2 (Structured Lineup) missing episode title",
                    missing_pillar="PILLAR_2",
                    pillar_details={"has_title": False}
                )
            
            if not lineup.match_status:
                raise HolyTriangleError(
                    message="PILLAR 2 (Structured Lineup) missing match status",
                    missing_pillar="PILLAR_2",
                    pillar_details={"has_status": False}
                )
            
            logger.info(f"[STEP 6] ✓ Lineup created: {len(lineup.segments)} segments (PILLAR 2 verified)")

            # STEP 7: Generate Dialogue Script (with Holy Triangle verification)
            logger.info("[STEP 7] Generate Dialogue Script")
            
            # Verify PILLAR 3 (The WHO): Personality & Vibe Profiles
            # Personas are hardcoded in DialogueScriptArchitect system prompt
            # We verify they exist by checking the service is initialized
            if not self.dialogue_architect:
                raise HolyTriangleError(
                    message="PILLAR 3 (Personality & Vibe Profiles) - DialogueScriptArchitect not initialized",
                    missing_pillar="PILLAR_3",
                    pillar_details={"dialogue_architect_exists": False}
                )
            
            logger.info("[STEP 7] ✓ Holy Triangle verified: All three pillars present")
            logger.info("  - PILLAR 1 (The WHAT): Enriched Data Context ✓")
            logger.info("  - PILLAR 2 (The HOW): Structured Lineup & Timing ✓")
            logger.info("  - PILLAR 3 (The WHO): Personality & Vibe Profiles ✓")
            
            # Generate dialogue script using DialogueScriptArchitect
            if is_panel:
                script = await self.dialogue_architect.generate_dialogue_script(
                    lineup=lineup,
                    game_context=context,
                )
            else:
                # Fallback to ScriptGenerator for single voice
                script = await self.script_generator.generate_script(
                    context=context,
                    intelligence=intelligence,
                    mode=mode,
                    include_betting=request.include_betting,
                )
            
            logger.info(f"[STEP 7] ✓ Dialogue script generated: {len(script)} characters")

            # STEP 8: Synthesize Audio
            logger.info("[STEP 8] Synthesize Audio")
            if self.settings.skip_audio_synthesis:
                logger.info("[STEP 8] ⚠️  Skipping audio synthesis (skip_audio_synthesis=True)")
                audio_bytes = None
                audio_url = None
                duration = self.ssml_processor.estimate_duration(script)
            else:
                if is_panel:
                    logger.info("[STEP 8] Synthesizing multi-voice panel discussion...")
                    audio_bytes = await self.multi_voice_synthesizer.synthesize_panel_discussion(script)
                    duration = self.multi_voice_synthesizer.estimate_duration(script)
                else:
                    voice_id = self.audio_synthesizer.get_voice_id(request.voice_id)
                    audio_bytes = await self.audio_synthesizer.synthesize(
                        script=script,
                        voice_id=voice_id,
                    )
                    duration = self.ssml_processor.estimate_duration(script)
                
                logger.info(f"[STEP 8] ✓ Audio synthesized: {len(audio_bytes)} bytes, {duration:.1f}s")

                # STEP 9: Merge with Intro and Outro
                logger.info("[STEP 9] Merge with Intro and Outro")
                try:
                    merged_audio_bytes = self.audio_merger.merge_audio(
                        content_audio_bytes=audio_bytes,
                        include_intro=True,
                        include_outro=True,
                    )
                    logger.info("[STEP 9] ✓ Successfully merged audio with intro and outro")
                    audio_bytes = merged_audio_bytes
                except Exception as e:
                    logger.warning(f"[STEP 9] ⚠️  Failed to merge intro/outro, using original audio: {e}")
                    # Continue with original audio if merging fails

                # STEP 10: Store Audio File
                logger.info("[STEP 10] Store Audio File")
                metadata = {
                    "game_ids": [int(gid) for gid in request.game_ids],
                    "mode": mode.value,
                    "format": "panel" if is_panel else "single_voice",
                    "language": request.language,
                }
                audio_url = await self.audio_storage.store_audio(
                    audio_bytes=audio_bytes,
                    job_id=job_id,
                    metadata=metadata,
                )
                logger.info(f"[STEP 10] ✓ Audio stored: {audio_url}")

            logger.info(f"[COMPLETE] Podcast generation complete: {job_id}")

            return PodcastResult(
                job_id=job_id,
                status="completed",
                audio_url=audio_url,
                duration_seconds=duration,
                script=script,
                mode=mode.value,
                format="panel" if is_panel else "single_voice",
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
        from src.models import GameStatus

        # Panel discussion mode
        if request.mode == PodcastMode.PANEL_DISCUSSION:
            return ContentMode.PANEL_DISCUSSION

        # Check if mode is explicitly specified
        if request.mode == PodcastMode.DAILY_RECAP:
            return ContentMode.DAILY_RECAP
        elif request.mode == PodcastMode.GAME_SPOTLIGHT:
            # Determine pre/post game for single game
            if games:
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
    panel_format: bool = False,
) -> PodcastResult:
    """
    Simple interface for generating a podcast.

    Args:
        game_ids: List of game IDs
        include_betting: Include betting insights
        voice_id: Optional ElevenLabs voice ID
        panel_format: Use 3-person panel discussion format

    Returns:
        PodcastResult with audio URL
    """
    request = PodcastRequest(
        game_ids=game_ids,
        include_betting=include_betting,
        voice_id=voice_id,
        format=PodcastFormat.PANEL if panel_format else PodcastFormat.SINGLE_VOICE,
    )

    orchestrator = PodcastOrchestrator()
    return await orchestrator.generate_podcast(request)
