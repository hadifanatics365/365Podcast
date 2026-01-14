"""ElevenLabs text-to-speech synthesis."""

import logging
from typing import Optional

from elevenlabs import ElevenLabs
from elevenlabs.core import ApiError as ElevenLabsAPIError

from src.config import Settings, get_settings
from src.exceptions import AudioSynthesisError, RateLimitError
from src.services.script_engine.ssml_processor import SSMLProcessor

logger = logging.getLogger(__name__)


class AudioSynthesizer:
    """
    Synthesizes speech audio using ElevenLabs API.

    Features:
    - Uses turbo_v2 model for fast synthesis
    - Processes SSML markers for natural pacing
    - Configurable voice selection
    """

    # Default voice: Rachel - natural, professional female voice
    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

    # Alternative voices for variety
    VOICE_OPTIONS = {
        "rachel": "21m00Tcm4TlvDq8ikWAM",  # Female, professional
        "adam": "pNInz6obpgDQGcFmaJgB",  # Male, deep
        "josh": "TxGEqnHWrfWFTfGW9XjX",  # Male, young
        "elli": "MF3mGyEYCl7XYWbV9V6O",  # Female, young
        "sam": "yoZ06aMxZJJ28mfd3POQ",  # Male, narrative
    }

    def __init__(
        self,
        settings: Optional[Settings] = None,
        ssml_processor: Optional[SSMLProcessor] = None,
    ):
        self.settings = settings or get_settings()
        self.ssml_processor = ssml_processor or SSMLProcessor()

        self.client = ElevenLabs(api_key=self.settings.elevenlabs_api_key)
        self.model = self.settings.elevenlabs_model
        self.default_voice = self.settings.elevenlabs_default_voice

    async def synthesize(
        self,
        script: str,
        voice_id: Optional[str] = None,
    ) -> bytes:
        """
        Convert script to audio using ElevenLabs.

        Args:
            script: Script text with SSML markers
            voice_id: Optional ElevenLabs voice ID

        Returns:
            MP3 audio bytes

        Raises:
            AudioSynthesisError: If synthesis fails
            RateLimitError: If rate limited
        """
        voice = voice_id or self.default_voice
        logger.info(f"Synthesizing audio with voice {voice}, script length: {len(script)}")

        # Process SSML markers for ElevenLabs compatibility
        processed_script = self.ssml_processor.process_for_elevenlabs(script)

        try:
            # Generate audio using ElevenLabs
            audio_generator = self.client.text_to_speech.convert(
                voice_id=voice,
                model_id=self.model,
                text=processed_script,
                output_format="mp3_44100_128",
            )

            # Collect audio bytes from generator
            audio_chunks = []
            for chunk in audio_generator:
                audio_chunks.append(chunk)

            audio_bytes = b"".join(audio_chunks)

            logger.info(f"Generated audio: {len(audio_bytes)} bytes")
            return audio_bytes

        except ElevenLabsAPIError as e:
            error_str = str(e).lower()
            if "rate" in error_str or "limit" in error_str or "quota" in error_str:
                logger.error(f"ElevenLabs rate limit: {e}")
                raise RateLimitError(
                    message="ElevenLabs rate limit exceeded",
                    service="elevenlabs",
                    retry_after=60,
                    cause=e,
                )
            logger.error(f"ElevenLabs API error: {e}")
            raise AudioSynthesisError(
                message=f"ElevenLabs API error: {str(e)}",
                voice_id=voice,
                script_length=len(script),
                cause=e,
            )
        except Exception as e:
            logger.error(f"Unexpected error during synthesis: {e}")
            raise AudioSynthesisError(
                message=f"Audio synthesis failed: {str(e)}",
                voice_id=voice,
                script_length=len(script),
                cause=e,
            )

    def get_voice_id(self, voice_name: Optional[str] = None) -> str:
        """
        Get voice ID from name or return default.

        Args:
            voice_name: Optional voice name (rachel, adam, etc.)

        Returns:
            ElevenLabs voice ID
        """
        if voice_name:
            voice_lower = voice_name.lower()
            if voice_lower in self.VOICE_OPTIONS:
                return self.VOICE_OPTIONS[voice_lower]
            # Assume it's already a voice ID
            if len(voice_name) > 10:
                return voice_name

        return self.default_voice

    def estimate_cost(self, script: str) -> float:
        """
        Estimate synthesis cost in USD.

        ElevenLabs pricing is based on character count.
        As of 2024, approximately $0.30 per 1000 characters.

        Args:
            script: Script text

        Returns:
            Estimated cost in USD
        """
        # Remove SSML markers for accurate count
        clean_script = self.ssml_processor.process_for_elevenlabs(script)
        char_count = len(clean_script)

        # Approximate pricing
        cost_per_1000_chars = 0.30
        return (char_count / 1000) * cost_per_1000_chars

    async def get_available_voices(self) -> list[dict]:
        """
        Get list of available voices.

        Returns:
            List of voice info dictionaries
        """
        try:
            voices = self.client.voices.get_all()
            return [
                {
                    "voice_id": v.voice_id,
                    "name": v.name,
                    "category": getattr(v, "category", "unknown"),
                }
                for v in voices.voices
            ]
        except Exception as e:
            logger.warning(f"Failed to fetch voices: {e}")
            return [
                {"voice_id": vid, "name": name, "category": "default"}
                for name, vid in self.VOICE_OPTIONS.items()
            ]
