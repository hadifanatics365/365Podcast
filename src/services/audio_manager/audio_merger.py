"""Audio file merger for combining intro, content, and outro."""

import io
import logging
from pathlib import Path
from typing import Optional

from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

from src.config import Settings, get_settings
from src.exceptions import AudioSynthesisError

logger = logging.getLogger(__name__)


class AudioMerger:
    """
    Merges audio files: intro + content + outro.
    
    Supports MP3 format and handles different sample rates/bitrates.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.assets_path = Path(__file__).parent.parent.parent / "assets"
        self.intro_path = self.assets_path / "intro.mp3"
        self.outro_path = self.assets_path / "outro.mp3"  # Separate outro file

    def merge_audio(
        self,
        content_audio_bytes: bytes,
        include_intro: bool = True,
        include_outro: bool = True,
    ) -> bytes:
        """
        Merge intro, content, and outro audio files.

        Args:
            content_audio_bytes: MP3 audio bytes of the podcast content
            include_intro: Whether to include intro at the start (uses intro.mp3)
            include_outro: Whether to include outro at the end (uses outro.mp3, skipped if file doesn't exist)

        Returns:
            Merged MP3 audio bytes

        Raises:
            AudioSynthesisError: If merging fails (e.g., ffmpeg not installed)
        """
        try:
            # Check if intro file exists
            if include_intro and not self.intro_path.exists():
                logger.warning(f"Intro file not found at {self.intro_path}, skipping intro")
                include_intro = False
            
            # Check if outro file exists (use separate outro.mp3, don't fall back to intro)
            if include_outro and not self.outro_path.exists():
                logger.warning(f"Outro file not found at {self.outro_path}, skipping outro")
                include_outro = False
            
            # Load content audio
            logger.info("[STEP 9] Loading content audio...")
            content_audio = AudioSegment.from_mp3(
                io.BytesIO(content_audio_bytes)
            )
            
            # Detect and log original sample rate
            original_content_rate = content_audio.frame_rate
            original_content_channels = content_audio.channels
            logger.info(f"[STEP 9] Content audio: {original_content_rate} Hz, {original_content_channels} channel(s)")

            # Normalize content audio format (MP3, 44100 Hz, stereo)
            if original_content_rate != 44100:
                logger.info(f"[STEP 9] Normalizing content sample rate: {original_content_rate} Hz → 44100 Hz")
            if original_content_channels != 2:
                logger.info(f"[STEP 9] Normalizing content channels: {original_content_channels} → 2 (stereo)")
            
            content_audio = content_audio.set_frame_rate(44100).set_channels(2)
            logger.info(f"[STEP 9] ✓ Content audio normalized to 44100 Hz, stereo")

            segments = []

            # Add intro if requested
            if include_intro:
                logger.info(f"[STEP 9] Loading intro from {self.intro_path}")
                intro_audio = AudioSegment.from_mp3(str(self.intro_path))
                
                # Detect and log original sample rate
                original_intro_rate = intro_audio.frame_rate
                original_intro_channels = intro_audio.channels
                logger.info(f"[STEP 9] Intro audio: {original_intro_rate} Hz, {original_intro_channels} channel(s)")
                
                # Normalize intro to match content format (44100 Hz, stereo)
                if original_intro_rate != 44100:
                    logger.info(f"[STEP 9] Normalizing intro sample rate: {original_intro_rate} Hz → 44100 Hz")
                if original_intro_channels != 2:
                    logger.info(f"[STEP 9] Normalizing intro channels: {original_intro_channels} → 2 (stereo)")
                
                intro_audio = intro_audio.set_frame_rate(44100).set_channels(2)
                segments.append(intro_audio)
                logger.info(f"[STEP 9] ✓ Intro audio normalized and added: {len(intro_audio)}ms")

            # Add content
            segments.append(content_audio)
            logger.info(f"[STEP 9] ✓ Content audio added: {len(content_audio)}ms")

            # Add outro if requested (use separate outro.mp3 file)
            if include_outro:
                logger.info(f"[STEP 9] Loading outro from {self.outro_path}")
                outro_audio = AudioSegment.from_mp3(str(self.outro_path))
                
                # Detect and log original sample rate
                original_outro_rate = outro_audio.frame_rate
                original_outro_channels = outro_audio.channels
                logger.info(f"[STEP 9] Outro audio: {original_outro_rate} Hz, {original_outro_channels} channel(s)")
                
                # Normalize outro to match content format (44100 Hz, stereo)
                if original_outro_rate != 44100:
                    logger.info(f"[STEP 9] Normalizing outro sample rate: {original_outro_rate} Hz → 44100 Hz")
                if original_outro_channels != 2:
                    logger.info(f"[STEP 9] Normalizing outro channels: {original_outro_channels} → 2 (stereo)")
                
                outro_audio = outro_audio.set_frame_rate(44100).set_channels(2)
                segments.append(outro_audio)
                logger.info(f"[STEP 9] ✓ Outro audio normalized and added: {len(outro_audio)}ms")

            # Merge all segments (all normalized to 44100 Hz, stereo)
            logger.info("[STEP 9] Merging audio segments (all at 44100 Hz, stereo)...")
            merged_audio = sum(segments)
            
            # Verify final format
            final_rate = merged_audio.frame_rate
            final_channels = merged_audio.channels
            if final_rate != 44100 or final_channels != 2:
                logger.warning(f"[STEP 9] ⚠️  Merged audio format mismatch: {final_rate} Hz, {final_channels} channel(s)")
                # Re-normalize if needed
                merged_audio = merged_audio.set_frame_rate(44100).set_channels(2)
                logger.info("[STEP 9] Re-normalized merged audio to 44100 Hz, stereo")
            else:
                logger.info(f"[STEP 9] ✓ Merged audio verified: {final_rate} Hz, {final_channels} channel(s)")

            # Export as MP3 (44100 Hz, 128 kbps, stereo)
            logger.info("[STEP 9] Exporting merged audio to MP3 (44100 Hz, 128 kbps, stereo)...")
            output = io.BytesIO()
            merged_audio.export(
                output,
                format="mp3",
                bitrate="128k",
                parameters=["-ar", "44100"]  # Explicitly set sample rate
            )

            merged_bytes = output.getvalue()
            total_duration = len(merged_audio) / 1000.0  # Convert to seconds
            logger.info(
                f"[STEP 9] ✓ Merged audio complete: {len(merged_bytes)} bytes, "
                f"{total_duration:.1f} seconds (44100 Hz, stereo, 128 kbps)"
            )

            return merged_bytes

        except CouldntDecodeError as e:
            logger.error(f"Failed to decode audio: {e}")
            raise AudioSynthesisError(
                message=f"Failed to decode audio file: {str(e)}",
                voice_id=None,
            )
        except FileNotFoundError as e:
            logger.error(f"Audio file not found: {e}")
            raise AudioSynthesisError(
                message=f"Audio file not found: {str(e)}",
                voice_id=None,
            )
        except Exception as e:
            logger.error(f"Audio merging failed: {e}")
            raise AudioSynthesisError(
                message=f"Failed to merge audio: {str(e)}",
                voice_id=None,
            )
