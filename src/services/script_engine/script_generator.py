"""Claude-powered script generation for podcasts."""

import logging
from typing import Any, Optional

from anthropic import Anthropic, APIError, RateLimitError as AnthropicRateLimitError

from src.config import Settings, get_settings
from src.exceptions import RateLimitError, ScriptGenerationError
from src.models import ContentMode
from src.services.intelligence.talking_points import IntelligenceContext
from src.services.script_engine.prompt_templates import PromptTemplates
from src.services.script_engine.ssml_processor import SSMLProcessor

logger = logging.getLogger(__name__)


class ScriptGenerator:
    """
    Generates podcast scripts using Claude API.

    Handles:
    - Loading appropriate prompt templates
    - Building context for LLM
    - Calling Claude API
    - Processing and validating output
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        prompt_templates: Optional[PromptTemplates] = None,
        ssml_processor: Optional[SSMLProcessor] = None,
    ):
        self.settings = settings or get_settings()
        self.prompt_templates = prompt_templates or PromptTemplates()
        self.ssml_processor = ssml_processor or SSMLProcessor()

        self.client = Anthropic(api_key=self.settings.anthropic_api_key)
        self.model = self.settings.claude_model
        self.max_tokens = self.settings.claude_max_tokens

    async def generate_script(
        self,
        context: dict[str, Any],
        mode: ContentMode,
        include_betting: bool = True,
        intelligence: Optional[IntelligenceContext] = None,
    ) -> str:
        """
        Generate a podcast script from game context.

        Args:
            context: Enriched game context from DataEnricher
            mode: Content generation mode
            include_betting: Include betting insights
            intelligence: Optional intelligence context with talking points

        Returns:
            Generated script with SSML markers

        Raises:
            ScriptGenerationError: If generation fails
            RateLimitError: If rate limited by Claude API
        """
        logger.info(f"Generating script for mode: {mode.value}")
        if intelligence and intelligence.top_stories:
            logger.info(f"Including {len(intelligence.top_stories)} talking points")

        # Get prompts
        system_prompt = self.prompt_templates.get_system_prompt(mode)
        user_prompt = self.prompt_templates.build_user_prompt(
            context, include_betting=include_betting, intelligence=intelligence
        )

        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
            )

            # Extract script from response
            script = self._extract_script(response)

            # Validate script
            is_valid, error = self.ssml_processor.validate_script(script)
            if not is_valid:
                logger.warning(f"Script validation warning: {error}")
                # Try to fix common issues
                script = self._fix_script_issues(script)

            # Estimate duration
            duration = self.ssml_processor.estimate_duration(script)
            logger.info(f"Generated script: {len(script)} chars, ~{duration:.1f}s duration")

            return script

        except AnthropicRateLimitError as e:
            logger.error(f"Claude rate limit exceeded: {e}")
            raise RateLimitError(
                message="Claude API rate limit exceeded",
                service="anthropic",
                retry_after=60,
                cause=e,
            )
        except APIError as e:
            logger.error(f"Claude API error: {e}")
            raise ScriptGenerationError(
                message=f"Claude API error: {str(e)}",
                model=self.model,
                cause=e,
            )
        except Exception as e:
            logger.error(f"Unexpected error generating script: {e}")
            raise ScriptGenerationError(
                message=f"Script generation failed: {str(e)}",
                model=self.model,
                cause=e,
            )

    def _extract_script(self, response: Any) -> str:
        """Extract script text from Claude response."""
        if not response.content:
            raise ScriptGenerationError("Empty response from Claude")

        # Get text from first content block
        for block in response.content:
            if hasattr(block, "text"):
                return block.text.strip()

        raise ScriptGenerationError("No text content in Claude response")

    def _fix_script_issues(self, script: str) -> str:
        """Attempt to fix common script issues."""
        # Remove any markdown formatting that might have slipped in
        script = script.replace("```", "")
        script = script.replace("**", "*")

        # Ensure script isn't too short
        if len(script) < 50:
            script = f"Welcome to 365Scores. {script}"

        return script.strip()

    def get_word_count_target(self, mode: ContentMode) -> tuple[int, int]:
        """
        Get target word count range for a mode.

        Returns:
            Tuple of (min_words, max_words)
        """
        targets = {
            ContentMode.DAILY_RECAP: (400, 800),
            ContentMode.GAME_SPOTLIGHT_PREGAME: (200, 350),
            ContentMode.GAME_SPOTLIGHT_POSTGAME: (350, 500),
        }
        return targets.get(mode, (300, 500))

    def estimate_duration_from_mode(self, mode: ContentMode) -> tuple[float, float]:
        """
        Get expected duration range for a mode.

        Returns:
            Tuple of (min_seconds, max_seconds)
        """
        min_words, max_words = self.get_word_count_target(mode)
        words_per_minute = 150

        min_duration = (min_words / words_per_minute) * 60
        max_duration = (max_words / words_per_minute) * 60

        return min_duration, max_duration
