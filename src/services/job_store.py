"""Job tracking and podcast cache for async generation."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PodcastJob:
    """Represents a podcast generation job."""
    job_id: str
    game_ids: list[int]
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    script: Optional[str] = None
    error_message: Optional[str] = None
    mode: Optional[str] = None
    device_token: Optional[str] = None  # For push notification
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "game_ids": self.game_ids,
            "status": self.status.value,
            "progress": self.progress,
            "audio_url": self.audio_url,
            "duration_seconds": self.duration_seconds,
            "script": self.script,
            "error_message": self.error_message,
            "mode": self.mode,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class CachedPodcast:
    """A pre-generated or cached podcast for a game."""
    game_id: int
    audio_url: str
    duration_seconds: float
    mode: str
    generated_at: datetime
    expires_at: datetime
    script: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.now(timezone.utc) > self.expires_at


class JobStore:
    """
    In-memory job tracking and podcast cache.

    Can be swapped to Redis for production by implementing
    the same interface with Redis backend.
    """

    def __init__(self, cache_ttl_hours: int = 24):
        self._jobs: dict[str, PodcastJob] = {}
        self._podcast_cache: dict[int, CachedPodcast] = {}  # game_id -> podcast
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._lock = asyncio.Lock()

    # =========================================================================
    # Job Tracking
    # =========================================================================

    async def create_job(
        self,
        job_id: str,
        game_ids: list[int],
        device_token: Optional[str] = None,
    ) -> PodcastJob:
        """Create a new job."""
        async with self._lock:
            job = PodcastJob(
                job_id=job_id,
                game_ids=game_ids,
                device_token=device_token,
            )
            self._jobs[job_id] = job
            logger.info(f"Created job {job_id} for games {game_ids}")
            return job

    async def get_job(self, job_id: str) -> Optional[PodcastJob]:
        """Get job by ID."""
        return self._jobs.get(job_id)

    async def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        progress: Optional[float] = None,
        audio_url: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        script: Optional[str] = None,
        error_message: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> Optional[PodcastJob]:
        """Update job status and details."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            job.updated_at = datetime.now(timezone.utc)

            if status is not None:
                job.status = status
                if status == JobStatus.COMPLETED:
                    job.completed_at = job.updated_at

            if progress is not None:
                job.progress = progress
            if audio_url is not None:
                job.audio_url = audio_url
            if duration_seconds is not None:
                job.duration_seconds = duration_seconds
            if script is not None:
                job.script = script
            if error_message is not None:
                job.error_message = error_message
            if mode is not None:
                job.mode = mode

            logger.debug(f"Updated job {job_id}: status={job.status.value}, progress={job.progress}")
            return job

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        async with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                return True
            return False

    async def get_pending_jobs(self) -> list[PodcastJob]:
        """Get all pending jobs."""
        return [j for j in self._jobs.values() if j.status == JobStatus.PENDING]

    async def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """Remove jobs older than max_age_hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        async with self._lock:
            old_jobs = [
                jid for jid, job in self._jobs.items()
                if job.created_at < cutoff
            ]
            for jid in old_jobs:
                del self._jobs[jid]
            if old_jobs:
                logger.info(f"Cleaned up {len(old_jobs)} old jobs")
            return len(old_jobs)

    # =========================================================================
    # Podcast Cache
    # =========================================================================

    async def cache_podcast(
        self,
        game_id: int,
        audio_url: str,
        duration_seconds: float,
        mode: str,
        script: Optional[str] = None,
        ttl_hours: Optional[int] = None,
    ) -> CachedPodcast:
        """Cache a generated podcast for a game."""
        ttl = timedelta(hours=ttl_hours) if ttl_hours else self._cache_ttl
        now = datetime.now(timezone.utc)

        async with self._lock:
            cached = CachedPodcast(
                game_id=game_id,
                audio_url=audio_url,
                duration_seconds=duration_seconds,
                mode=mode,
                script=script,
                generated_at=now,
                expires_at=now + ttl,
            )
            self._podcast_cache[game_id] = cached
            logger.info(f"Cached podcast for game {game_id}, expires {cached.expires_at}")
            return cached

    async def get_cached_podcast(self, game_id: int) -> Optional[CachedPodcast]:
        """Get cached podcast for a game if available and not expired."""
        cached = self._podcast_cache.get(game_id)
        if cached and not cached.is_expired:
            return cached
        elif cached and cached.is_expired:
            # Clean up expired entry
            async with self._lock:
                self._podcast_cache.pop(game_id, None)
        return None

    async def get_all_cached_games(self) -> list[int]:
        """Get list of all game IDs with valid cache."""
        now = datetime.now(timezone.utc)
        return [
            gid for gid, cached in self._podcast_cache.items()
            if cached.expires_at > now
        ]

    async def invalidate_cache(self, game_id: int) -> bool:
        """Remove a game from cache."""
        async with self._lock:
            if game_id in self._podcast_cache:
                del self._podcast_cache[game_id]
                return True
            return False

    async def cleanup_expired_cache(self) -> int:
        """Remove all expired cache entries."""
        now = datetime.now(timezone.utc)
        async with self._lock:
            expired = [
                gid for gid, cached in self._podcast_cache.items()
                if cached.expires_at < now
            ]
            for gid in expired:
                del self._podcast_cache[gid]
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired cache entries")
            return len(expired)


# Global singleton instance
_job_store: Optional[JobStore] = None


def get_job_store() -> JobStore:
    """Get or create the global job store instance."""
    global _job_store
    if _job_store is None:
        _job_store = JobStore()
    return _job_store
