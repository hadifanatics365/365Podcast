"""Dialogue-based script architect for natural Moderator-Fan conversations."""

import json
import logging
from typing import Any, Optional

from anthropic import Anthropic, APIError

from src.config import Settings, get_settings
from src.exceptions import ScriptGenerationError
from src.models import Game, GameStatus
from src.services.lineup_agent import EpisodeStatus, PodcastLineup

logger = logging.getLogger(__name__)


class DialogueScriptArchitect:
    """
    Expert Podcast Script Architect that creates natural, engaging dialogue
    between a Moderator and a Fan based on match data and lineup structure.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.client = Anthropic(api_key=self.settings.anthropic_api_key)
        self.model = self.settings.claude_model
        self.max_tokens = self.settings.claude_max_tokens

    async def generate_dialogue_script(
        self,
        lineup: PodcastLineup,
        game_context: dict[str, Any],
    ) -> str:
        """
        Generate a natural dialogue script between Moderator and Fan.

        Args:
            lineup: PodcastLineup with segment structure
            game_context: Enriched game context

        Returns:
            Natural dialogue script with Moderator and Fan conversation
        """
        logger.info(f"Generating dialogue script for {lineup.match_status} episode")

        # Detect match status from game data
        match_status = self._detect_match_status(game_context, lineup.status)

        # Build system prompt
        system_prompt = self._build_system_prompt(match_status)

        # Build user prompt with game data and lineup
        user_prompt = self._build_user_prompt(lineup, game_context, match_status)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            script = self._extract_script(response)
            logger.info(f"Generated dialogue script: {len(script)} characters")

            return script

        except APIError as e:
            logger.error(f"Claude API error: {e}")
            raise ScriptGenerationError(
                message=f"Dialogue script generation failed: {str(e)}",
                model=self.model,
                cause=e,
            )
        except Exception as e:
            logger.error(f"Unexpected error generating dialogue script: {e}")
            raise ScriptGenerationError(
                message=f"Dialogue script generation failed: {str(e)}",
                model=self.model,
                cause=e,
            )

    def _detect_match_status(
        self,
        game_context: dict[str, Any],
        lineup_status: EpisodeStatus,
    ) -> str:
        """Detect if match is PRE-MATCH or POST-MATCH from actual data."""
        game_data = game_context.get("game") or (
            game_context.get("games", [{}])[0] if game_context.get("games") else {}
        )

        # Check for score/result
        if isinstance(game_data, dict):
            if game_data.get("final_score") or game_data.get("scrs") or game_data.get("winner"):
                return "POST-MATCH"
        elif isinstance(game_data, Game):
            if game_data.scrs or game_data.winner is not None:
                return "POST-MATCH"

        # Check lineup status
        if lineup_status == EpisodeStatus.POST_MATCH:
            return "POST-MATCH"

        return "PRE-MATCH"

    def _build_system_prompt(self, match_status: str) -> str:
        """Build system prompt for dialogue generation."""
        return f"""You are an expert Podcast Script Architect. Your job is to create a natural, engaging dialogue between a Moderator and a Fan.

🚨 CRITICAL RULES:

1. STATUS AWARENESS:
   - Match Status: {match_status}
   - If POST-MATCH: Focus on final result, key moments, goals, and the "Day after" feeling. The Fan's mood depends on the result.
   - If PRE-MATCH: Focus on expectations, danger men, and the Fan's nerves/excitement.

2. THE "N/A" RULE:
   - If a data field (Lineups, Stats, Odds) is missing or says "NOT_AVAILABLE", DO NOT mention it.
   - DO NOT say "Data is missing" or "N/A".
   - Simply skip that topic or pivot the conversation naturally to what IS available.

3. PERSONAS & TONE:
   - Moderator (Host): Friendly, curious, avoids "News Anchor" robotic speech. She asks questions and bridges segments naturally.
   - The Fan (Guest): Passionate but grounded. His mood depends on the result (if POST-MATCH) or his nerves/excitement (if PRE-MATCH).
   - The Vibe: A casual conversation between friends who know football inside out.

4. LINEUP LOGIC:
   - If Lineups exist: Don't just list names. Have the Fan react to them emotionally (e.g., "I can't believe they started with X instead of Y!").
   - If POST-MATCH: Discuss how the lineup performed.
   - If Lineups are missing: Skip the lineup segment entirely. Move straight to match atmosphere or key events.

5. OUTPUT STRUCTURE:
   - Intro: Establish the vibe and match status immediately.
   - The Meat:
     * POST-MATCH: Analysis of goals, drama, and the Fan's emotional state (Happy/Sad/Relieved).
     * PRE-MATCH: Expectations, danger men, and the Fan's nerves.
   - The Pitch: Discuss betting/odds ONLY if data exists. If not, talk about "Who has the edge."
   - Outro: A quick summary and "See you next time."

6. ANTI-ROBOT CONSTRAINTS:
   - NEVER say "Segment" or "Segment 1", "Segment 2", etc.
   - NEVER say "Not Available" or "N/A" or "Data is missing".
   - NEVER treat a past game as a future game. If the date is in the past, it's a review, not a preview.
   - Use natural transitions: "Speaking of...", "You know what...", "Here's the thing..."
   - Include [PAUSE:short], [PAUSE:medium], [PAUSE:long] markers for natural pacing
   - DO NOT use asterisks (*word*) for emphasis

7. DIALOGUE FORMAT:
   - Use clear speaker labels: "MODERATOR:" and "FAN:"
   - Make it feel like a real conversation with back-and-forth
   - The Fan should have opinions and react emotionally
   - The Moderator should guide the conversation but not dominate it

Generate a natural, engaging dialogue script that follows these rules."""

    def _build_user_prompt(
        self,
        lineup: PodcastLineup,
        game_context: dict[str, Any],
        match_status: str,
    ) -> str:
        """Build user prompt with lineup and game context."""
        # Filter game context to remove "NOT_AVAILABLE" markers
        filtered_context = self._filter_unavailable_data(game_context)

        # Extract key information
        game_data = filtered_context.get("game") or (
            filtered_context.get("games", [{}])[0] if filtered_context.get("games") else {}
        )

        # Build segment summary
        segment_summary = []
        for i, segment in enumerate(lineup.segments, 1):
            if segment.topic in ["Introduction", "Outro"]:
                continue  # Skip intro/outro in segment list
            
            segment_info = f"- {segment.topic} ({segment.allocated_time}s)"
            if segment.key_data_points:
                # Only include available data points
                available_points = [
                    p for p in segment.key_data_points 
                    if "NOT_AVAILABLE" not in p.upper() and "N/A" not in p.upper()
                ]
                if available_points:
                    segment_info += f"\n  Key points: {', '.join(available_points[:3])}"
            segment_summary.append(segment_info)

        # Build betting info if available
        betting_info = ""
        if lineup.betting_corner_config and lineup.betting_corner_config.featured_odds:
            betting_info = f"""
BETTING INFORMATION:
- Bookmaker: {lineup.betting_corner_config.bookmaker_name}
- Market: {lineup.betting_corner_config.target_market}
- Featured Odds: {json.dumps(lineup.betting_corner_config.featured_odds, indent=2)}
- Prediction Context: {lineup.betting_corner_config.prediction_context}
"""

        prompt = f"""Generate a natural dialogue script for this podcast episode:

EPISODE TITLE: {lineup.episode_title}
MATCH STATUS: {match_status}
DURATION: {lineup.total_duration_minutes} minutes

SEGMENT STRUCTURE (use as guide, but make conversation flow naturally):
{chr(10).join(segment_summary)}

GAME DATA:
{json.dumps(filtered_context, indent=2, default=str)}

{betting_info}

INSTRUCTIONS:
1. Create a natural dialogue between MODERATOR and FAN
2. Follow the segment topics but make it conversational, not robotic
3. If data is missing, skip it - don't mention it
4. The Fan should react emotionally based on match status
5. Include [PAUSE] markers for natural pacing
6. Make it feel like friends talking about football
7. Total duration should be approximately {lineup.total_duration_minutes} minutes

Generate the complete dialogue script now."""

        return prompt

    def _filter_unavailable_data(self, context: dict[str, Any]) -> dict[str, Any]:
        """Remove or filter out 'NOT_AVAILABLE' and 'N/A' markers from context."""
        import copy

        filtered = copy.deepcopy(context)

        def clean_dict(d: dict) -> dict:
            """Recursively clean dictionary."""
            cleaned = {}
            for key, value in d.items():
                if isinstance(value, dict):
                    cleaned[key] = clean_dict(value)
                elif isinstance(value, list):
                    cleaned[key] = [
                        clean_dict(item) if isinstance(item, dict) else item
                        for item in value
                        if not (isinstance(item, str) and ("NOT_AVAILABLE" in item.upper() or item.upper() == "N/A"))
                    ]
                elif isinstance(value, str):
                    # Skip strings that are just "NOT_AVAILABLE" or "N/A"
                    if value.upper() not in ["NOT_AVAILABLE", "N/A", "NONE"]:
                        cleaned[key] = value
                else:
                    cleaned[key] = value
            return cleaned

        return clean_dict(filtered)

    def _extract_script(self, response: Any) -> str:
        """Extract script text from Claude response."""
        if not response.content:
            raise ScriptGenerationError("Empty response from Claude")

        for block in response.content:
            if hasattr(block, "text"):
                return block.text.strip()

        raise ScriptGenerationError("No text content in Claude response")
