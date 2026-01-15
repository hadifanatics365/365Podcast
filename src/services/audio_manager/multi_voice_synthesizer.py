"""Multi-voice synthesis for panel discussion podcasts."""

import io
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from elevenlabs import ElevenLabs

from src.config import Settings, get_settings
from src.exceptions import AudioSynthesisError
from src.models.characters import DEFAULT_CHARACTERS, Character, VoiceSettings, get_all_voice_ids

logger = logging.getLogger(__name__)


@dataclass
class DialogueLine:
    """A single line of dialogue from a character."""
    character: str
    text: str
    voice_id: str
    voice_settings: VoiceSettings = field(default_factory=VoiceSettings)


class MultiVoiceSynthesizer:
    """
    Synthesizes multi-character podcast audio using ElevenLabs.

    Parses scripts with [CHARACTER]: format and generates audio
    with different voices for each character.
    """

    # Pattern to match [CHARACTER]: text
    DIALOGUE_PATTERN = re.compile(r'\[([A-Z]+)\]:\s*(.+?)(?=\[[A-Z]+\]:|$)', re.DOTALL)

    # Silence duration between speakers (in bytes for MP3)
    # Approximately 0.5 seconds of silence
    PAUSE_DURATION_MS = 500

    def __init__(
        self,
        settings: Optional[Settings] = None,
        characters: Optional[list[Character]] = None,
    ):
        self.settings = settings or get_settings()
        self.characters = characters or DEFAULT_CHARACTERS
        self.client = ElevenLabs(api_key=self.settings.elevenlabs_api_key)
        self.model = self.settings.elevenlabs_model

        # Build voice mapping from characters (includes voice settings)
        # Map both character names and role labels to voices
        self.voice_map: dict[str, tuple[str, VoiceSettings]] = {}
        
        for char in self.characters:
            # Map character name (e.g., "SARAH", "MARCUS", "RIO")
            self.voice_map[char.name.upper()] = (char.voice_id, char.voice_settings)
            
            # Map role labels (e.g., "HOST", "ANALYST", "FAN", "LEGEND")
            role_label = char.role.value.upper()
            self.voice_map[role_label] = (char.voice_id, char.voice_settings)
        
        # Explicit mappings for common labels
        # HOST = SARAH (Female voice)
        host_char = next((c for c in self.characters if c.role.value == "host"), None)
        if host_char:
            self.voice_map["HOST"] = (host_char.voice_id, host_char.voice_settings)
        
        # ANALYST = MARCUS (Male voice)
        analyst_char = next((c for c in self.characters if c.role.value == "analyst"), None)
        if analyst_char:
            self.voice_map["ANALYST"] = (analyst_char.voice_id, analyst_char.voice_settings)
        
        # FAN/SUPPORTER = RIO (Male voice) - map both FAN and LEGEND to RIO
        fan_char = next((c for c in self.characters if c.role.value == "legend"), None)
        if fan_char:
            self.voice_map["FAN"] = (fan_char.voice_id, fan_char.voice_settings)
            self.voice_map["SUPPORTER"] = (fan_char.voice_id, fan_char.voice_settings)
            self.voice_map["LEGEND"] = (fan_char.voice_id, fan_char.voice_settings)

        logger.info(f"MultiVoiceSynthesizer initialized with voices: {list(self.voice_map.keys())}")
        logger.info(f"Voice mapping: HOST={host_char.name if host_char else 'N/A'} (Female), "
                   f"ANALYST={analyst_char.name if analyst_char else 'N/A'} (Male), "
                   f"FAN={fan_char.name if fan_char else 'N/A'} (Male)")

    def parse_script(self, script: str) -> list[DialogueLine]:
        """
        Parse a multi-character script into dialogue lines.

        Args:
            script: Script with [CHARACTER]: format

        Returns:
            List of DialogueLine objects
        """
        lines = []

        # Find all dialogue matches
        matches = self.DIALOGUE_PATTERN.findall(script)

        for character, text in matches:
            character = character.upper().strip()
            text = text.strip()

            if not text:
                continue

            # Get voice ID and settings for character
            voice_data = self.voice_map.get(character)
            if not voice_data:
                # Try common aliases
                if character == "HOST":
                    voice_data = self.voice_map.get("SARAH") or self.voice_map.get("ALEX")
                elif character == "ANALYST":
                    voice_data = self.voice_map.get("MARCUS")
                elif character in ["FAN", "SUPPORTER", "LEGEND"]:
                    voice_data = self.voice_map.get("RIO") or self.voice_map.get("DAVID")
                
                if not voice_data:
                    logger.warning(f"Unknown character '{character}', using default host voice (SARAH)")
                    voice_data = self.voice_map.get("SARAH") or self.voice_map.get("HOST")
                    if not voice_data:
                        voice_data = (self.settings.elevenlabs_default_voice, VoiceSettings())

            voice_id, voice_settings = voice_data
            
            # Log voice assignment for verification
            logger.debug(f"Character '{character}' → Voice ID: {voice_id[:8]}...")

            lines.append(DialogueLine(
                character=character,
                text=text,
                voice_id=voice_id,
                voice_settings=voice_settings,
            ))

        logger.info(f"Parsed {len(lines)} dialogue lines from script")
        return lines

    async def synthesize_line(self, line: DialogueLine) -> bytes:
        """
        Synthesize a single dialogue line.

        Args:
            line: DialogueLine to synthesize

        Returns:
            Audio bytes (MP3)
        """
        try:
            # Clean text for TTS
            clean_text = self._clean_text_for_tts(line.text)

            logger.debug(f"Synthesizing {line.character}: {clean_text[:50]}...")

            # Apply voice settings for more expressive/stable output
            vs = line.voice_settings

            # Generate audio with voice settings
            audio_generator = self.client.text_to_speech.convert(
                voice_id=line.voice_id,
                model_id=self.model,
                text=clean_text,
                output_format="mp3_44100_128",
                voice_settings={
                    "stability": vs.stability,
                    "similarity_boost": vs.similarity_boost,
                    "style": vs.style,
                    "use_speaker_boost": vs.use_speaker_boost,
                },
            )

            # Collect chunks
            chunks = []
            for chunk in audio_generator:
                chunks.append(chunk)

            return b"".join(chunks)

        except Exception as e:
            logger.error(f"Failed to synthesize line for {line.character}: {e}")
            raise AudioSynthesisError(
                message=f"Failed to synthesize {line.character}'s line: {str(e)}",
                voice_id=line.voice_id,
            )

    async def synthesize_panel_discussion(self, script: str) -> bytes:
        """
        Synthesize a complete panel discussion with multiple voices.

        Args:
            script: Full script with [CHARACTER]: format

        Returns:
            Complete audio bytes (MP3)
        """
        # Parse script into lines
        lines = self.parse_script(script)

        if not lines:
            raise AudioSynthesisError(
                message="No dialogue lines found in script",
                details={"script_length": len(script)},
            )

        # Verify voice assignments (each character should have distinct voice)
        character_voices = {}
        for line in lines:
            if line.character in character_voices:
                if character_voices[line.character] != line.voice_id:
                    logger.warning(
                        f"Character '{line.character}' has conflicting voice IDs: "
                        f"{character_voices[line.character]} vs {line.voice_id}"
                    )
            else:
                character_voices[line.character] = line.voice_id
        
        # Log voice assignments for verification
        logger.info(f"[STEP 8] Voice assignments:")
        for char, voice_id in character_voices.items():
            char_name = next((c.name for c in self.characters if c.voice_id == voice_id), "Unknown")
            logger.info(f"  - {char} → {char_name} (Voice ID: {voice_id[:8]}...)")
        
        # Verify all three characters are present
        required_chars = {"HOST", "ANALYST", "FAN"}
        found_chars = set(character_voices.keys())
        missing_chars = required_chars - found_chars
        if missing_chars:
            logger.warning(f"[STEP 8] Missing characters in script: {missing_chars}")
        
        logger.info(f"[STEP 8] Synthesizing {len(lines)} dialogue lines...")

        # Generate audio for each line
        audio_segments = []

        for i, line in enumerate(lines):
            logger.info(f"Processing line {i+1}/{len(lines)}: {line.character}")

            # Synthesize the line
            audio = await self.synthesize_line(line)
            audio_segments.append(audio)

        # Concatenate all segments
        # Note: Simple concatenation works for MP3, but for production
        # you might want to use pydub or ffmpeg for proper audio processing
        combined = b"".join(audio_segments)

        logger.info(f"Combined audio: {len(combined)} bytes from {len(audio_segments)} segments")

        return combined

    def _clean_text_for_tts(self, text: str) -> str:
        """Clean text for TTS processing."""
        # Remove [PAUSE] markers - we handle pauses between speakers
        text = re.sub(r'\[PAUSE(?::\w+)?\]', '', text)

        # Convert *emphasis* markdown to plain text (TTS reads asterisks weirdly)
        # The emphasis is conveyed through the voice/context, not markers
        text = re.sub(r'\*([^*]+)\*', r'\1', text)

        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text)

        # Remove any remaining brackets
        text = re.sub(r'\[.*?\]', '', text)

        return text.strip()

    def estimate_duration(self, script: str, words_per_minute: int = 150) -> float:
        """
        Estimate total audio duration.

        Args:
            script: Full script
            words_per_minute: Average speaking rate

        Returns:
            Estimated duration in seconds
        """
        lines = self.parse_script(script)

        total_words = sum(len(line.text.split()) for line in lines)
        speech_time = (total_words / words_per_minute) * 60

        # Add pause time between speakers (0.5s per transition)
        pause_time = len(lines) * 0.5

        return speech_time + pause_time

    def get_character_stats(self, script: str) -> dict[str, int]:
        """
        Get word count per character.

        Args:
            script: Full script

        Returns:
            Dict of character name to word count
        """
        lines = self.parse_script(script)
        stats: dict[str, int] = {}

        for line in lines:
            word_count = len(line.text.split())
            stats[line.character] = stats.get(line.character, 0) + word_count

        return stats
