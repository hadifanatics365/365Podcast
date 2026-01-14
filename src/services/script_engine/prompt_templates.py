"""Prompt template management for script generation."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from src.models import ContentMode

if TYPE_CHECKING:
    from src.services.intelligence.talking_points import IntelligenceContext

logger = logging.getLogger(__name__)

# Default prompts directory
PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


class PromptTemplates:
    """
    Manages prompt templates for different content modes.

    Loads templates from the prompts/ directory and formats them
    with game context for LLM processing.
    """

    TEMPLATE_FILES = {
        ContentMode.DAILY_RECAP: "daily_recap_system.txt",
        ContentMode.GAME_SPOTLIGHT_PREGAME: "game_spotlight_pregame.txt",
        ContentMode.GAME_SPOTLIGHT_POSTGAME: "game_spotlight_postgame.txt",
        ContentMode.PANEL_DISCUSSION: "panel_discussion.txt",
    }

    def __init__(self, prompts_dir: Optional[Path] = None):
        self.prompts_dir = prompts_dir or PROMPTS_DIR
        self._templates: dict[ContentMode, str] = {}
        self._load_templates()

    def _load_templates(self) -> None:
        """Load all template files into memory."""
        for mode, filename in self.TEMPLATE_FILES.items():
            filepath = self.prompts_dir / filename
            try:
                if filepath.exists():
                    self._templates[mode] = filepath.read_text(encoding="utf-8")
                    logger.debug(f"Loaded template for {mode.value}")
                else:
                    logger.warning(f"Template file not found: {filepath}")
                    self._templates[mode] = self._get_default_template(mode)
            except Exception as e:
                logger.error(f"Error loading template {filename}: {e}")
                self._templates[mode] = self._get_default_template(mode)

    def get_system_prompt(self, mode: ContentMode) -> str:
        """
        Get the system prompt for a content mode.

        Args:
            mode: Content generation mode

        Returns:
            System prompt string
        """
        return self._templates.get(mode, self._get_default_template(mode))

    def build_user_prompt(
        self,
        context: dict[str, Any],
        include_betting: bool = True,
        intelligence: Optional[IntelligenceContext] = None,
    ) -> str:
        """
        Build the user prompt with game context.

        Args:
            context: Enriched game context from DataEnricher
            include_betting: Whether to include betting data
            intelligence: Optional intelligence context with talking points

        Returns:
            Formatted user prompt with context
        """
        # Filter out betting data if not requested
        if not include_betting:
            context = self._remove_betting_data(context)

        # Format context as readable JSON
        context_json = json.dumps(context, indent=2, default=str)

        # Format talking points section if available
        talking_points_section = ""
        if intelligence and intelligence.top_stories:
            talking_points_section = intelligence.format_for_prompt()

        prompt = f"""Generate a podcast script based on the following game data:

GAMES DATA:
{context_json}

{talking_points_section}
Remember to:
- Use [PAUSE:short], [PAUSE:medium], [PAUSE:long] markers for natural pacing
- Keep the tone professional and engaging
- Follow the structure outlined in the system prompt
- IMPORTANT: Incorporate the talking points naturally - reference specific facts and data, avoid generic statements
- DO NOT use asterisks (*word*) for emphasis - the voice will convey emphasis naturally

Return only the script text, no additional commentary."""

        return prompt

    def _remove_betting_data(self, context: dict[str, Any]) -> dict[str, Any]:
        """Remove betting-related data from context."""
        import copy
        clean = copy.deepcopy(context)

        # Remove betting from top level
        clean.pop("betting", None)
        clean.pop("betting_result", None)

        # Remove from games
        for game in clean.get("games", []):
            game.pop("betting", None)
            game.pop("betting_result", None)

        # Remove from categorized games
        for key in ["ended_games", "upcoming_games", "live_games"]:
            for game in clean.get(key, []):
                game.pop("betting", None)
                game.pop("betting_result", None)

        # Remove from single game
        if "game" in clean:
            clean["game"].pop("betting", None)
            clean["game"].pop("betting_result", None)

        return clean

    def _get_default_template(self, mode: ContentMode) -> str:
        """Get default fallback template."""
        if mode == ContentMode.DAILY_RECAP:
            return """You are a sports podcast host. Create an engaging recap of multiple matches.
Include scores, key moments, and natural transitions between games.
Use [PAUSE:short/medium/long] for pacing. DO NOT use asterisks for emphasis.
Keep it professional and informative, 400-800 words."""

        elif mode == ContentMode.GAME_SPOTLIGHT_PREGAME:
            return """You are a sports analyst previewing an upcoming match.
Cover lineups, form, head-to-head, and predictions.
Use [PAUSE:short/medium/long] for pacing. DO NOT use asterisks for emphasis.
Keep it analytical, 200-350 words."""

        elif mode == ContentMode.GAME_SPOTLIGHT_POSTGAME:
            return """You are a sports commentator recapping a finished match.
Cover the final score, key moments, top performers, and statistics.
Use [PAUSE:short/medium/long] for pacing. DO NOT use asterisks for emphasis.
Keep it engaging and informative, 350-500 words."""

        return "Generate an engaging sports podcast script based on the provided data."

    def get_transition_phrases(self) -> dict[str, list[str]]:
        """Get transition phrases for multi-game scripts."""
        return {
            "to_same_competition": [
                "In another match from {competition},",
                "Also in {competition},",
                "Staying in {competition},",
            ],
            "to_different_competition": [
                "Moving over to {competition},",
                "Meanwhile in {competition},",
                "Turning our attention to {competition},",
                "In {competition} action,",
            ],
            "to_upcoming": [
                "Looking ahead,",
                "Coming up next,",
                "Still to come,",
                "Later today,",
            ],
            "closing": [
                "That's your recap for today.",
                "And that wraps up our coverage.",
                "Stay tuned for more updates.",
            ],
        }
