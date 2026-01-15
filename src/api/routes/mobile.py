"""Mobile-friendly podcast endpoints for iOS/Android integration."""

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.config import get_settings
from src.models import PodcastRequest
from src.services.job_store import get_job_store, JobStatus
from src.services.push_notifications import get_apns_service, PushNotification
from src.services.scheduler import get_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mobile/podcast", tags=["Mobile"])


# =============================================================================
# Request/Response Models
# =============================================================================

class PodcastAvailabilityResponse(BaseModel):
    """Response for podcast availability check."""
    game_id: int
    available: bool
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    generated_at: Optional[str] = None


class GenerateAsyncRequest(BaseModel):
    """Request to generate podcast asynchronously."""
    game_id: int
    device_token: Optional[str] = Field(
        default=None,
        description="APNs device token for push notification when ready"
    )
    format: str = Field(default="panel", description="Podcast format")
    include_betting: bool = Field(default=True)


class GenerateAsyncResponse(BaseModel):
    """Response for async generation request."""
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status check."""
    job_id: str
    status: str
    progress: float
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/game/{game_id}", response_model=PodcastAvailabilityResponse)
async def check_podcast_availability(game_id: int) -> PodcastAvailabilityResponse:
    """
    Check if a podcast is available for a game.

    Use this endpoint to check if a pre-generated podcast exists
    before showing the "Play Podcast" button in the app.

    Returns:
        - available=true with audio_url if podcast exists
        - available=false if user needs to request generation
    """
    settings = get_settings()

    # Demo mode - return static URL for all games
    if settings.demo_mode and settings.demo_audio_url:
        logger.info(f"Demo mode: returning static URL for game {game_id}")
        return PodcastAvailabilityResponse(
            game_id=game_id,
            available=True,
            audio_url=settings.demo_audio_url,
            duration_seconds=120.0,
            generated_at="2025-01-15T00:00:00Z",
        )

    job_store = get_job_store()

    # Check cache
    cached = await job_store.get_cached_podcast(game_id)

    if cached:
        logger.info(f"Podcast available for game {game_id}")
        return PodcastAvailabilityResponse(
            game_id=game_id,
            available=True,
            audio_url=cached.audio_url,
            duration_seconds=cached.duration_seconds,
            generated_at=cached.generated_at.isoformat(),
        )

    logger.info(f"No podcast available for game {game_id}")
    return PodcastAvailabilityResponse(
        game_id=game_id,
        available=False,
    )


@router.post("/generate", response_model=GenerateAsyncResponse)
async def generate_podcast_async(
    request: GenerateAsyncRequest,
    background_tasks: BackgroundTasks,
) -> GenerateAsyncResponse:
    """
    Request podcast generation for a game.

    This endpoint returns immediately with a job_id.
    The podcast is generated in the background.

    If device_token is provided, a push notification will be sent
    when the podcast is ready.

    Poll /mobile/podcast/job/{job_id} for status updates.
    """
    job_store = get_job_store()

    # Check if already cached
    cached = await job_store.get_cached_podcast(request.game_id)
    if cached:
        return GenerateAsyncResponse(
            job_id="cached",
            status="completed",
            message="Podcast already available",
        )

    # Create job
    job_id = f"pod_{uuid.uuid4().hex[:12]}"

    await job_store.create_job(
        job_id=job_id,
        game_ids=[request.game_id],
        device_token=request.device_token,
    )

    # Queue background task
    background_tasks.add_task(
        _background_generate_with_notification,
        job_id=job_id,
        game_id=request.game_id,
        device_token=request.device_token,
        format=request.format,
        include_betting=request.include_betting,
    )

    logger.info(f"Queued podcast generation job {job_id} for game {request.game_id}")

    return GenerateAsyncResponse(
        job_id=job_id,
        status="processing",
        message="Podcast generation started. Check /job/{job_id} for status.",
    )


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """
    Check the status of a podcast generation job.

    Poll this endpoint to track progress.

    Status values:
    - pending: Job queued
    - processing: Generation in progress
    - completed: Audio ready (check audio_url)
    - failed: Generation failed (check error_message)
    """
    job_store = get_job_store()

    job = await job_store.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail={"error": "JobNotFound", "message": f"Job {job_id} not found"}
        )

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        audio_url=job.audio_url,
        duration_seconds=job.duration_seconds,
        error_message=job.error_message,
    )


@router.get("/available-games")
async def list_available_games() -> dict:
    """
    Get list of games with pre-generated podcasts.

    Use this to show "podcast available" badges in the app.
    """
    job_store = get_job_store()

    game_ids = await job_store.get_all_cached_games()

    return {
        "count": len(game_ids),
        "game_ids": game_ids,
    }


@router.post("/refresh/{game_id}")
async def refresh_podcast(
    game_id: int,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Force regeneration of podcast for a game.

    Use this if the match status has changed (e.g., half-time update).
    """
    job_store = get_job_store()

    # Invalidate existing cache
    await job_store.invalidate_cache(game_id)

    # Create new job
    job_id = f"pod_{uuid.uuid4().hex[:12]}"

    await job_store.create_job(
        job_id=job_id,
        game_ids=[game_id],
    )

    # Queue background task
    background_tasks.add_task(
        _background_generate_with_notification,
        job_id=job_id,
        game_id=game_id,
        device_token=None,
        format="panel",
        include_betting=True,
    )

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Podcast refresh started",
    }


@router.get("/demo-audio")
async def get_demo_audio() -> FileResponse:
    """
    Serve the demo podcast audio file.
    """
    demo_file = Path(__file__).parent.parent.parent.parent / "podcast_game_4452679_complete.mp3"

    if not demo_file.exists():
        raise HTTPException(status_code=404, detail="Demo audio file not found")

    return FileResponse(
        path=demo_file,
        media_type="audio/mpeg",
        filename="demo_podcast.mp3"
    )


# =============================================================================
# Background Tasks
# =============================================================================

async def _background_generate_with_notification(
    job_id: str,
    game_id: int,
    device_token: Optional[str],
    format: str,
    include_betting: bool,
) -> None:
    """Background task that generates podcast and sends push notification."""
    from src.services.orchestrator import PodcastOrchestrator

    job_store = get_job_store()
    apns = get_apns_service()

    try:
        # Update status
        await job_store.update_job(job_id, status=JobStatus.PROCESSING, progress=0.1)

        # Create orchestrator and generate
        orchestrator = PodcastOrchestrator()

        request = PodcastRequest(
            game_ids=[str(game_id)],
            format=format,
            include_betting=include_betting,
        )

        await job_store.update_job(job_id, progress=0.3)

        result = await orchestrator.generate_podcast(request)

        if result.status == "completed" and result.audio_url:
            # Update job
            await job_store.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                progress=1.0,
                audio_url=result.audio_url,
                duration_seconds=result.duration_seconds,
                script=result.script,
                mode=result.mode,
            )

            # Cache the podcast
            await job_store.cache_podcast(
                game_id=game_id,
                audio_url=result.audio_url,
                duration_seconds=result.duration_seconds or 0,
                mode=result.mode or format,
                script=result.script,
            )

            logger.info(f"Job {job_id} completed: {result.audio_url}")

            # Send push notification if device token provided
            if device_token and apns.is_configured:
                await apns.send_podcast_ready_notification(
                    device_token=device_token,
                    game_id=game_id,
                    audio_url=result.audio_url,
                )
        else:
            await job_store.update_job(
                job_id,
                status=JobStatus.FAILED,
                error_message="Generation did not complete successfully",
            )

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        await job_store.update_job(
            job_id,
            status=JobStatus.FAILED,
            error_message=str(e),
        )
