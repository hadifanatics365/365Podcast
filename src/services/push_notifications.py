"""Apple Push Notification Service (APNs) integration."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx
import jwt

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class PushNotification:
    """Push notification payload."""
    title: str
    body: str
    sound: str = "default"
    badge: Optional[int] = None
    category: str = "PODCAST_READY"
    data: Optional[dict] = None

    def to_apns_payload(self) -> dict:
        """Convert to APNs payload format."""
        aps = {
            "alert": {
                "title": self.title,
                "body": self.body,
            },
            "sound": self.sound,
            "category": self.category,
        }
        if self.badge is not None:
            aps["badge"] = self.badge

        payload = {"aps": aps}
        if self.data:
            payload.update(self.data)

        return payload


class APNsService:
    """
    Apple Push Notification Service client.

    Uses JWT-based authentication (recommended for server-side).
    Requires:
    - APNs Auth Key (.p8 file)
    - Key ID
    - Team ID
    - Bundle ID
    """

    # APNs endpoints
    PRODUCTION_URL = "https://api.push.apple.com"
    SANDBOX_URL = "https://api.sandbox.push.apple.com"

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

        # APNs configuration
        self.key_id = getattr(self.settings, 'apns_key_id', None)
        self.team_id = getattr(self.settings, 'apns_team_id', None)
        self.bundle_id = getattr(self.settings, 'apns_bundle_id', 'com.scores365.app')
        self.key_path = getattr(self.settings, 'apns_key_path', None)
        self.use_sandbox = getattr(self.settings, 'apns_sandbox', True)

        self._private_key: Optional[str] = None
        self._token_cache: Optional[tuple[str, float]] = None  # (token, timestamp)
        self._token_ttl = 3500  # Refresh token before 1 hour expiry

        # Load private key if available
        if self.key_path:
            try:
                with open(self.key_path, 'r') as f:
                    self._private_key = f.read()
                logger.info("APNs private key loaded")
            except FileNotFoundError:
                logger.warning(f"APNs key file not found: {self.key_path}")

    @property
    def is_configured(self) -> bool:
        """Check if APNs is properly configured."""
        return all([
            self.key_id,
            self.team_id,
            self._private_key,
        ])

    def _generate_token(self) -> str:
        """Generate JWT token for APNs authentication."""
        if not self._private_key:
            raise ValueError("APNs private key not loaded")

        now = time.time()

        # Check cache
        if self._token_cache:
            cached_token, cached_time = self._token_cache
            if now - cached_time < self._token_ttl:
                return cached_token

        # Generate new token
        headers = {
            "alg": "ES256",
            "kid": self.key_id,
        }
        payload = {
            "iss": self.team_id,
            "iat": int(now),
        }

        token = jwt.encode(payload, self._private_key, algorithm="ES256", headers=headers)
        self._token_cache = (token, now)

        logger.debug("Generated new APNs JWT token")
        return token

    async def send_notification(
        self,
        device_token: str,
        notification: PushNotification,
    ) -> bool:
        """
        Send push notification to a device.

        Args:
            device_token: APNs device token
            notification: Notification payload

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.is_configured:
            logger.warning("APNs not configured, skipping notification")
            return False

        base_url = self.SANDBOX_URL if self.use_sandbox else self.PRODUCTION_URL
        url = f"{base_url}/3/device/{device_token}"

        try:
            token = self._generate_token()

            headers = {
                "authorization": f"bearer {token}",
                "apns-topic": self.bundle_id,
                "apns-push-type": "alert",
                "apns-priority": "10",
            }

            payload = notification.to_apns_payload()

            async with httpx.AsyncClient(http2=True) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    logger.info(f"Push notification sent to {device_token[:20]}...")
                    return True
                else:
                    error = response.json() if response.content else {}
                    logger.error(f"APNs error {response.status_code}: {error}")
                    return False

        except Exception as e:
            logger.error(f"Failed to send push notification: {e}")
            return False

    async def send_podcast_ready_notification(
        self,
        device_token: str,
        game_id: int,
        audio_url: str,
        home_team: str = "Home",
        away_team: str = "Away",
    ) -> bool:
        """
        Send notification that a podcast is ready.

        Args:
            device_token: User's device token
            game_id: Game ID the podcast is for
            audio_url: URL to the audio file
            home_team: Home team name
            away_team: Away team name

        Returns:
            True if sent successfully
        """
        notification = PushNotification(
            title="🎙️ Your Podcast is Ready!",
            body=f"{home_team} vs {away_team} - Tap to listen",
            category="PODCAST_READY",
            data={
                "type": "podcast_ready",
                "game_id": game_id,
                "audio_url": audio_url,
            },
        )

        return await self.send_notification(device_token, notification)


# Global singleton
_apns_service: Optional[APNsService] = None


def get_apns_service() -> APNsService:
    """Get or create the global APNs service instance."""
    global _apns_service
    if _apns_service is None:
        _apns_service = APNsService()
    return _apns_service
