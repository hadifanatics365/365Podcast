"""SSML marker processing for text-to-speech."""

import re
from typing import Optional


class SSMLProcessor:
    """
    Processes SSML-like markers in scripts for TTS compatibility.

    Supported markers:
    - [PAUSE:short] → 0.5s pause
    - [PAUSE:medium] → 1.0s pause
    - [PAUSE:long] → 1.5s pause
    - [PAUSE:Xs] → Custom X second pause
    - *text* → Emphasis
    """

    PAUSE_DURATIONS = {
        "short": 0.5,
        "medium": 1.0,
        "long": 1.5,
        "beat": 0.3,
    }

    PAUSE_PATTERN = re.compile(r"\[PAUSE(?::(\w+|[\d.]+s?))?\]", re.IGNORECASE)
    EMPHASIS_PATTERN = re.compile(r"\*([^*]+)\*")

    def process_for_elevenlabs(self, script: str) -> str:
        """
        Process script markers for ElevenLabs TTS.

        ElevenLabs uses natural punctuation for pauses and
        handles emphasis through context. This method converts
        our markers to ElevenLabs-compatible format.

        Args:
            script: Raw script with markers

        Returns:
            Processed script for ElevenLabs
        """
        result = script

        # Convert pause markers to punctuation-based pauses
        def replace_pause(match: re.Match) -> str:
            duration_str = match.group(1)
            if duration_str:
                duration_str = duration_str.lower().rstrip("s")
                if duration_str in self.PAUSE_DURATIONS:
                    duration = self.PAUSE_DURATIONS[duration_str]
                else:
                    try:
                        duration = float(duration_str)
                    except ValueError:
                        duration = 0.5
            else:
                duration = 0.5

            # ElevenLabs handles pauses through punctuation
            if duration >= 1.5:
                return "... ..."  # Long pause
            elif duration >= 1.0:
                return "..."  # Medium pause
            else:
                return "."  # Short pause

        result = self.PAUSE_PATTERN.sub(replace_pause, result)

        # Remove emphasis markers (ElevenLabs handles naturally)
        result = self.EMPHASIS_PATTERN.sub(r"\1", result)

        # Clean up multiple spaces
        result = re.sub(r" +", " ", result)

        # Clean up multiple periods
        result = re.sub(r"\.{4,}", "...", result)

        return result.strip()

    def process_for_ssml(self, script: str) -> str:
        """
        Convert script to standard SSML format.

        Useful for Google TTS or other SSML-compatible services.

        Args:
            script: Raw script with markers

        Returns:
            SSML-formatted script
        """
        result = script

        # Convert pause markers to SSML break elements
        def replace_pause_ssml(match: re.Match) -> str:
            duration_str = match.group(1)
            if duration_str:
                duration_str = duration_str.lower().rstrip("s")
                if duration_str in self.PAUSE_DURATIONS:
                    duration = self.PAUSE_DURATIONS[duration_str]
                else:
                    try:
                        duration = float(duration_str)
                    except ValueError:
                        duration = 0.5
            else:
                duration = 0.5

            return f'<break time="{duration}s"/>'

        result = self.PAUSE_PATTERN.sub(replace_pause_ssml, result)

        # Convert emphasis markers to SSML emphasis
        result = self.EMPHASIS_PATTERN.sub(r'<emphasis level="strong">\1</emphasis>', result)

        # Wrap in speak tags
        result = f'<speak>\n{result}\n</speak>'

        return result

    def add_natural_pauses(self, script: str) -> str:
        """
        Add natural pauses after sentences and sections.

        Args:
            script: Script text

        Returns:
            Script with added pause markers
        """
        # Add pause after match transitions
        transitions = [
            "Moving on to",
            "Now let's look at",
            "Turning to",
            "Meanwhile",
            "In other action",
            "Elsewhere",
        ]

        result = script
        for transition in transitions:
            result = result.replace(
                transition,
                f"[PAUSE:medium] {transition}"
            )

        return result

    def estimate_duration(self, script: str, words_per_minute: int = 150) -> float:
        """
        Estimate audio duration from script.

        Args:
            script: Script text with or without markers
            words_per_minute: Speaking rate

        Returns:
            Estimated duration in seconds
        """
        # Remove markers for word count
        clean = self.PAUSE_PATTERN.sub("", script)
        clean = self.EMPHASIS_PATTERN.sub(r"\1", clean)

        # Count words
        words = len(clean.split())
        word_time = (words / words_per_minute) * 60

        # Add pause durations
        pause_time = 0.0
        for match in self.PAUSE_PATTERN.finditer(script):
            duration_str = match.group(1)
            if duration_str:
                duration_str = duration_str.lower().rstrip("s")
                if duration_str in self.PAUSE_DURATIONS:
                    pause_time += self.PAUSE_DURATIONS[duration_str]
                else:
                    try:
                        pause_time += float(duration_str)
                    except ValueError:
                        pause_time += 0.5
            else:
                pause_time += 0.5

        return word_time + pause_time

    def validate_script(self, script: str) -> tuple[bool, Optional[str]]:
        """
        Validate script for TTS compatibility.

        Args:
            script: Script to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not script or not script.strip():
            return False, "Script is empty"

        if len(script) < 50:
            return False, "Script is too short (minimum 50 characters)"

        if len(script) > 50000:
            return False, "Script is too long (maximum 50000 characters)"

        # Check for unbalanced emphasis markers
        asterisks = script.count("*")
        if asterisks % 2 != 0:
            return False, "Unbalanced emphasis markers (*)"

        return True, None
