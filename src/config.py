"""Application configuration from environment variables."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    debug: bool = False

    # 365Scores API
    scores_api_base_url: str = "https://mobileapi.365scores.com"
    scores_api_language: int = 1  # English
    scores_api_timezone: int = 0  # UTC

    # Claude API (Anthropic)
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    claude_max_tokens: int = 2000

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_model: str = "eleven_turbo_v2"
    elevenlabs_default_voice: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel
    skip_audio_synthesis: bool = Field(
        default=True,
        description="Skip ElevenLabs API calls and return script only (for testing)",
    )
    skip_audio_synthesis: bool = Field(
        default=True,
        description="Skip ElevenLabs API calls and return script only (for testing)",
    )

    # Storage
    storage_type: str = "local"  # "s3" or "local"
    s3_bucket_name: Optional[str] = None
    s3_region: str = "us-east-1"
    cdn_base_url: Optional[str] = None
    local_storage_path: str = "/tmp/podcasts"

    # Redis (for job queue)
    redis_url: str = "redis://localhost:6379"

    # Demo mode - returns static audio URL instead of generating
    demo_mode: bool = False
    demo_audio_url: Optional[str] = None  # Static MP3 URL for demo

    # Apple Push Notifications (APNs)
    apns_key_id: Optional[str] = None  # Key ID from Apple Developer
    apns_team_id: Optional[str] = None  # Team ID from Apple Developer
    apns_key_path: Optional[str] = None  # Path to .p8 auth key file
    apns_bundle_id: str = "com.scores365.app"  # Your app's bundle ID
    apns_sandbox: bool = True  # Use sandbox for development

    # Retry Configuration
    max_retry_attempts: int = 3
    retry_initial_delay: float = 1.0
    retry_backoff_factor: float = 2.0

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
