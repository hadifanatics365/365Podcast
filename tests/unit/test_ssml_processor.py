"""Tests for SSMLProcessor."""

import pytest

from src.services.script_engine.ssml_processor import SSMLProcessor


class TestSSMLProcessor:
    """Test suite for SSMLProcessor."""

    @pytest.fixture
    def processor(self) -> SSMLProcessor:
        """Create SSMLProcessor instance."""
        return SSMLProcessor()

    def test_process_short_pause_for_elevenlabs(self, processor: SSMLProcessor):
        """Short pause should convert to period."""
        script = "Hello [PAUSE:short] world"
        result = processor.process_for_elevenlabs(script)
        assert "[PAUSE" not in result
        assert "." in result

    def test_process_medium_pause_for_elevenlabs(self, processor: SSMLProcessor):
        """Medium pause should convert to ellipsis."""
        script = "Hello [PAUSE:medium] world"
        result = processor.process_for_elevenlabs(script)
        assert "[PAUSE" not in result
        assert "..." in result

    def test_process_long_pause_for_elevenlabs(self, processor: SSMLProcessor):
        """Long pause should convert to double ellipsis."""
        script = "Hello [PAUSE:long] world"
        result = processor.process_for_elevenlabs(script)
        assert "[PAUSE" not in result
        assert "... ..." in result

    def test_process_emphasis_removed_for_elevenlabs(self, processor: SSMLProcessor):
        """Emphasis markers should be removed."""
        script = "The *winner* is here"
        result = processor.process_for_elevenlabs(script)
        assert "*" not in result
        assert "winner" in result

    def test_process_for_ssml_creates_break_elements(self, processor: SSMLProcessor):
        """SSML output should have break elements."""
        script = "Hello [PAUSE:short] world"
        result = processor.process_for_ssml(script)
        assert '<break time="0.5s"/>' in result
        assert "<speak>" in result
        assert "</speak>" in result

    def test_process_for_ssml_creates_emphasis_elements(self, processor: SSMLProcessor):
        """SSML output should have emphasis elements."""
        script = "The *winner* is here"
        result = processor.process_for_ssml(script)
        assert '<emphasis level="strong">winner</emphasis>' in result

    def test_estimate_duration_basic(self, processor: SSMLProcessor):
        """Duration estimation should work for basic text."""
        # 150 words at 150 wpm = 60 seconds
        script = " ".join(["word"] * 150)
        duration = processor.estimate_duration(script)
        assert 55 < duration < 65  # Allow some variance

    def test_estimate_duration_with_pauses(self, processor: SSMLProcessor):
        """Duration should include pause times."""
        script = "Hello [PAUSE:long] world"  # 2 words + 1.5s pause
        duration = processor.estimate_duration(script)
        # 2 words at 150 wpm = 0.8s + 1.5s pause = ~2.3s
        assert duration > 2.0

    def test_validate_script_empty_fails(self, processor: SSMLProcessor):
        """Empty script should fail validation."""
        is_valid, error = processor.validate_script("")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_validate_script_too_short_fails(self, processor: SSMLProcessor):
        """Very short script should fail validation."""
        is_valid, error = processor.validate_script("Hi")
        assert is_valid is False
        assert "short" in error.lower()

    def test_validate_script_too_long_fails(self, processor: SSMLProcessor):
        """Very long script should fail validation."""
        script = "word " * 20000
        is_valid, error = processor.validate_script(script)
        assert is_valid is False
        assert "long" in error.lower()

    def test_validate_script_unbalanced_emphasis_fails(self, processor: SSMLProcessor):
        """Unbalanced emphasis markers should fail."""
        script = "Hello *world is great"  # Missing closing *
        is_valid, error = processor.validate_script(script)
        assert is_valid is False
        assert "emphasis" in error.lower() or "balanced" in error.lower()

    def test_validate_script_valid_passes(self, processor: SSMLProcessor):
        """Valid script should pass validation."""
        script = "Welcome to 365Scores. [PAUSE:short] Here is your *daily recap*."
        is_valid, error = processor.validate_script(script)
        assert is_valid is True
        assert error is None

    def test_custom_pause_duration(self, processor: SSMLProcessor):
        """Custom pause duration should be parsed."""
        script = "Hello [PAUSE:2s] world"
        result = processor.process_for_ssml(script)
        assert '<break time="2.0s"/>' in result

    def test_add_natural_pauses(self, processor: SSMLProcessor):
        """Should add pauses after transition phrases."""
        script = "Moving on to the next match"
        result = processor.add_natural_pauses(script)
        assert "[PAUSE" in result
