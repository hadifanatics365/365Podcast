"""Podcast generation endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from src.exceptions import (
    DataFetchError,
    PodcastGenerationError,
    RateLimitError,
    ScriptGenerationError,
    AudioSynthesisError,
)
from src.models import PodcastRequest, PodcastResponse, PodcastStatusResponse
from src.services import PodcastOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/podcast", tags=["Podcast"])

# Singleton orchestrator instance
_orchestrator: Optional[PodcastOrchestrator] = None


def get_orchestrator() -> PodcastOrchestrator:
    """Get or create orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = PodcastOrchestrator()
    return _orchestrator


@router.post("/generate", response_model=PodcastResponse)
async def generate_podcast(
    request: PodcastRequest,
    background_tasks: BackgroundTasks,
    sync: bool = Query(
        default=True,
        description="If true, wait for completion. If false, return immediately with job_id.",
    ),
) -> PodcastResponse:
    """
    Generate a podcast for specified game IDs.

    **Modes:**
    - `auto`: Automatically determines mode based on game count and status
    - `daily_recap`: Multi-game summary with transitions
    - `game_spotlight`: Deep dive into a single game

    **Sync vs Async:**
    - `sync=true` (default): Waits for generation to complete and returns audio URL
    - `sync=false`: Returns immediately with job_id for status polling

    **Request Body:**
    ```json
    {
        "game_ids": ["123456", "789012"],
        "mode": "auto",
        "language": "en",
        "include_betting": true,
        "voice_id": null
    }
    ```
    """
    orchestrator = get_orchestrator()

    logger.info(f"Podcast generation request: {len(request.game_ids)} games, sync={sync}")

    if sync:
        # Synchronous generation - wait for completion
        try:
            result = await orchestrator.generate_podcast(request)

            return PodcastResponse(
                job_id=result.job_id,
                status=result.status,
                audio_url=result.audio_url,
                duration_seconds=result.duration_seconds,
                script=result.script,
                created_at=result.created_at,
            )

        except DataFetchError as e:
            logger.error(f"Data fetch error: {e}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "GameNotFound",
                    "message": e.message,
                    "details": e.details,
                },
            )
        except RateLimitError as e:
            logger.error(f"Rate limit error: {e}")
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "RateLimitExceeded",
                    "message": e.message,
                    "retry_after": e.details.get("retry_after_seconds", 60),
                },
            )
        except ScriptGenerationError as e:
            logger.error(f"Script generation error: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "ScriptGenerationFailed",
                    "message": e.message,
                },
            )
        except AudioSynthesisError as e:
            logger.error(f"Audio synthesis error: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "AudioSynthesisFailed",
                    "message": e.message,
                },
            )
        except PodcastGenerationError as e:
            logger.error(f"Podcast generation error: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "GenerationFailed",
                    "message": e.message,
                    "details": e.details,
                },
            )
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "InternalError",
                    "message": "An unexpected error occurred",
                },
            )
    else:
        # Asynchronous generation - return job_id immediately
        # TODO: Implement background task with Redis queue
        job_id = f"pod_{hash(str(request.game_ids)) % 1000000:06d}"

        # For now, just queue the background task
        # In production, this would use a proper job queue
        background_tasks.add_task(
            _background_generate,
            orchestrator,
            request,
            job_id,
        )

        return PodcastResponse(
            job_id=job_id,
            status="processing",
        )


async def _background_generate(
    orchestrator: PodcastOrchestrator,
    request: PodcastRequest,
    job_id: str,
) -> None:
    """Background task for async generation."""
    try:
        result = await orchestrator.generate_podcast(request)
        # TODO: Store result in Redis for status polling
        logger.info(f"Background job {job_id} completed: {result.audio_url}")
    except Exception as e:
        logger.error(f"Background job {job_id} failed: {e}")
        # TODO: Store error in Redis


@router.get("/status/{job_id}", response_model=PodcastStatusResponse)
async def get_podcast_status(job_id: str) -> PodcastStatusResponse:
    """
    Check the status of a podcast generation job.

    **Job States:**
    - `pending`: Job is queued
    - `processing`: Generation in progress
    - `completed`: Audio ready
    - `failed`: Generation failed

    Returns audio URL when status is `completed`.
    """
    orchestrator = get_orchestrator()

    # TODO: Implement proper job tracking with Redis
    status = await orchestrator.get_job_status(job_id)

    if status is None:
        # Job not found or tracking not implemented
        raise HTTPException(
            status_code=404,
            detail={
                "error": "JobNotFound",
                "message": f"Job {job_id} not found",
            },
        )

    return PodcastStatusResponse(
        job_id=job_id,
        status=status.get("status", "unknown"),
        progress=status.get("progress", 0.0),
        audio_url=status.get("audio_url"),
        duration_seconds=status.get("duration_seconds"),
        script=status.get("script"),
        error_message=status.get("error_message"),
        mode=status.get("mode"),
        games_count=status.get("games_count"),
    )


@router.get("/voices")
async def list_voices() -> dict:
    """
    List available voices for podcast generation.

    Returns available ElevenLabs voice options.
    """
    from src.services.audio_manager import AudioSynthesizer

    synthesizer = AudioSynthesizer()
    voices = await synthesizer.get_available_voices()

    return {
        "voices": voices,
        "default": synthesizer.default_voice,
    }
