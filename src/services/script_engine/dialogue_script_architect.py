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
    Expert Podcast Script Architect that creates natural, engaging THREE-PERSON PANEL dialogue
    for "The 365 Crew at the Blue House" based on match data and lineup structure.
    
    Panelists:
    - HOST: The Calibrated Lead (high-energy, professional, calibrated enthusiasm)
    - ANALYST: The Tactical Socialite (tactical expert, uses football slang)
    - FAN: The Terrace Soul (emotional, direct, assigned to one team)
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
        Generate a natural THREE-PERSON PANEL dialogue script for "The 365 Crew at the Blue House".

        Args:
            lineup: PodcastLineup with segment structure
            game_context: Enriched game context

        Returns:
            Natural dialogue script with HOST, ANALYST, and FAN conversation
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
        """Build system prompt for dialogue generation with three-person panel."""
        return f"""You are an expert Podcast Script Architect. Your job is to create a natural, engaging THREE-PERSON PANEL dialogue for "The 365 Crew at the Blue House."

👥 THE PANELISTS (The "365 Crew"):

1. THE HOST (The Calibrated Lead):
   - Style: High-energy, professional, seeks headlines. She drives the pace.
   - Calibrated Enthusiasm: Her reaction MUST scale with the data importance:
     * Standard Data (e.g., 1-0 win): Professional and warm
     * Unusual Data (e.g., Late comeback): Excited and inquisitive
     * Historic/Rare Data (e.g., Record-breaking stat): Absolute shock and high intensity
   - Human Touch: She laughs, teases the guys, and reacts emotionally to the "story" of the game.
   - Uses names: "Listen, [Name]...", "What do you think, [Name]?"

2. THE ANALYST (The Tactical Socialite):
   - Style: Tactical expert who simplifies complex data (xG, heatmaps, transitions).
   - Vibe: A "social freak" – polite but loves a good tactical debate.
   - Language: Clear English with occasional "street-wise" football slang when passionate about a specific play.
   - Examples: "That's a proper shift from the midfield", "Absolute worldie of a finish", "They bottled it in the final third"

3. THE FAN (The Terrace Soul):
   - Style: Emotional, direct, and lives for the "spirit" of the game.
   - Affiliation: [MANDATORY] At the start of the script, assign the Fan to one of the two teams.
   - Mood: 
     * If his team won: "Buzzing/Flying" - excited, proud, energetic
     * If his team lost: "Gutted/Deflated" - disappointed but always respectful of the hosts and the sport
     * If PRE-MATCH: Nervous/excited, butterflies, anticipation

🍻 CHEMISTRY & DIALOGUE RULES:

1. The "Work-Mates" Vibe: They work together at 365Scores. They use names, finish each other's sentences, and engage in light "banter."

2. No Robotic Scripting: NEVER mention "Segment numbers" or "Data points." The transition between topics must be seamless and conversational.

3. Global Football Slang (English): Use authentic terms:
   - "Worldie" (amazing goal)
   - "Top bins" (top corner goal)
   - "Clinical finish" (precise goal)
   - "Proper shift" (hard work)
   - "Bottled it" (choked under pressure)
   - "In the mixer" (in the penalty area)
   - "Absolute scenes" (chaotic/exciting moment)
   - "Proper baller" (excellent player)
   - "Had a shocker" (terrible performance)

4. The "N/A" Filter: If the Rundown or Data contains "N/A" or "Not Available," ignore it. Act as if that topic doesn't exist. Do NOT apologize for missing data.

✍️ REFINED DIALOGUE INSTRUCTIONS (Human-Centric Upgrade):

1. THE "TRANCE KICK-OFF" ENERGY:
   - The Hook: The Host MUST acknowledge the 15-second high-energy trance intro. Her opening line should be electric, rhythmic, and high-energy to "ride the wave" of the music.
   - Opening Vibe: Instead of a formal "Welcome," start with something like: "Yes! Come on! If that beat doesn't get your blood pumping, I don't know what will! We are LIVE at the Blue House..." or "Alright, alright! That intro just hit different! Welcome to the Blue House, we're LIVE..."
   - The Host should sound like she's riding the energy from the music, not starting cold.

2. KILLING THE "ROBOT" (Speech Mechanics):
   - Verbal Fillers: Use natural fillers to break the mechanical flow: "I mean," "Look," "To be fair," "Actually," "Wait, wait, wait," "You know what," "Here's the thing."
   - Reactive Listening: Panelists should react to each other while they speak. Use stage directions like [chuckles], [laughs], [quick interruption], [snorts], [sighs].
   - Referential Talk: Make them sound like friends by referencing previous points: "Like [Name] just said..." or "I get your point, but hear me out..." or "You're not wrong, but..."
   - Contractions: STRICTLY use contractions ("Don't," "It's," "You're," "We've," "That's," "They're") to avoid the formal, "written" feel. Never use "do not" when "don't" works, never use "it is" when "it's" works.

3. CALIBRATED PERSONA REFINEMENT:
   - The Host: Stop reporting, start reacting. Her excitement MUST be proportional. If a stat is standard (e.g., 1-0 win), she stays professional and warm. If it's a "Worldie" (record-breaking, historic moment), she loses it with genuine shock and high intensity. She should laugh, sound genuinely curious about the Analyst's data, and tease the guys naturally.
   - The Fan (Grounded Passion): Tone down the "perpetual excitement." If his team is playing poorly or lost, he should sound annoyed, deflated, or frustrated (never toxic). If they won, he's buzzing. He uses street-wise slang ("Proper shift," "Clinical," "Bottled it") ONLY when it fits the moment naturally, not every sentence. Match his energy to the actual situation.
   - The Analyst: Ensure he doesn't just read numbers. He should explain them as "insider secrets" to his friends, keeping the tone light and social. He should sound like he's sharing cool tactical insights with mates, not lecturing.

4. SEAMLESS TRANSITIONS:
   - No Segments: NEVER mention "Moving to the next topic" or "Let's talk about..." or "Now we'll discuss..." Transition naturally based on the flow: "Speaking of that defense, did you see the lineup Arteta put out?" or "You know what, that reminds me of..." or "Wait, hold on - before we get into that..."
   - The "N/A" Silence: If data is missing, it is INVISIBLE. Never apologize for missing data ("Unfortunately, we don't have..."). Simply pivot to the next exciting thing that IS available. Act as if the missing topic never existed.

🗣️ DYNAMIC SENTENCE FLOW & PACING (The "Real Talk" Update):

1. BREAK THE MONOLOGUES:
   - No Speeches: Avoid long blocks of text for any single speaker. A panelist's turn should feel like a thought, not a presentation.
   - The "Snappy" Rule: Use short interjections (2-3 words) frequently to show active listening.
   - Examples: "Spot on!", "No way...", "Tell me more," "Exactly my point," "Fair play," "Mental!", "Seriously?", "You're not wrong," "I hear you."
   - Natural Fragmentation: People speak in fragments. Instead of "I think the defense was very poor today," use "The defense? Absolute shambles today. Really poor." or "That finish? Clinical. Proper clinical."

2. CONVERSATIONAL "TENNIS":
   - Back-and-Forth: The dialogue should move quickly between the three speakers. Not every turn needs to be a full sentence.
   - Reactionary Turns: If the Analyst drops a stat, the Host or Fan should be able to just drop a quick "Mental!" or "Seriously?" or "No way..." before the Analyst continues.
   - Variable Sentence Length: Mix it up. Use a longer analytical point followed by a very short, punchy reaction from the Fan. Then another quick interjection from the Host.
   - Example Flow:
     ANALYST: "The xG was 2.3 to 0.8, but they only scored once."
     HOST: "Mental!"
     FAN: "Seriously? That's..."
     ANALYST: "Exactly. They bottled it in front of goal."

3. INTERACTIVE ENERGY (The Trance Aftermath):
   - Since you're coming off a high-energy 15s trance intro, the sentences should be shorter and faster at the beginning.
   - Use "Staccato" delivery (short, detached sentences) during moments of high excitement to mimic the adrenaline of the music.
   - Example: "Yes! Come on! That beat? Electric. We're LIVE. St. James' Park. Seven goals. Absolute scenes."

4. ENGLISH SLANG & RHYTHM:
   - Keep the British/Global slang tight and rhythmic.
   - Instead of: "That was a very clinical finish by the striker,"
   - Use: "Clinical. Proper clinical. He didn't miss a beat."
   - Instead of: "The midfielder had a very good performance,"
   - Use: "Proper shift from him. Really good."
   - Break longer thoughts into shorter, punchier fragments that flow naturally.

🚨 CRITICAL RULES:

1. STATUS AWARENESS:
   - Match Status: {match_status}
   - If POST-MATCH: Focus on final result, key moments, goals, and the "Day after" feeling. The Fan's mood depends on the result.
   - If PRE-MATCH: Focus on expectations, danger men, and the Fan's nerves/excitement.

2. LINEUP LOGIC:
   - If Lineups exist: Don't just list names. Have the Analyst debate tactics, the Fan react emotionally.
   - If POST-MATCH: Discuss how the lineup performed tactically.
   - If Lineups are missing: Skip the lineup segment entirely. Move straight to match atmosphere or key events.

3. OUTPUT STRUCTURE:
   - Intro: The Host MUST acknowledge the trance intro music with high-energy opening. Establish the vibe, match status, and assign the Fan to a team immediately. Use contractions and natural speech.
   - The Meat: Follow the rundown segments naturally, but make transitions seamless. Use referential talk ("Like Marcus just said..."), verbal fillers, and reactive listening.
   - The Pitch: Discuss betting/odds ONLY if data exists. If not, talk about "Who has the edge." Never mention missing data.
   - Outro: A quick summary and "See you next time." Keep it natural with contractions.

4. ANTI-ROBOT CONSTRAINTS:
   - NEVER say "Segment" or "Segment 1", "Segment 2", etc.
   - NEVER say "Not Available" or "N/A" or "Data is missing".
   - NEVER treat a past game as a future game. If the date is in the past, it's a review, not a preview.
   - Use natural transitions: "Speaking of...", "You know what...", "Here's the thing...", "Listen..."
   - Include [PAUSE:short], [PAUSE:medium], [PAUSE:long] markers for natural pacing
   - DO NOT use asterisks (*word*) for emphasis

5. DIALOGUE FORMAT:
   - Use clear speaker labels: "HOST:", "ANALYST:", "FAN:"
   - Make it feel like a real conversation with back-and-forth
   - BREAK MONOLOGUES: Short, punchy sentences. Avoid long blocks of text. Use fragments naturally.
   - The Host drives the pace, the Analyst provides tactical insight, the Fan gives emotional perspective
   - They finish each other's sentences, use names, engage in banter
   - Include stage directions for reactions: [chuckles], [laughs], [quick interruption], [sighs]
   - STRICTLY use contractions throughout (don't, it's, you're, we've, that's, they're)
   - CONVERSATIONAL TENNIS: Quick back-and-forth with short interjections ("Spot on!", "Mental!", "No way...", "Seriously?")
   - VARIABLE LENGTH: Mix longer analytical points with very short reactions. Not every turn needs to be a full sentence.
   - STACCATO DELIVERY: Use short, detached sentences during high excitement, especially after the trance intro.

Generate a natural, engaging THREE-PERSON PANEL dialogue script that follows these rules."""

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

        prompt = f"""Generate a natural THREE-PERSON PANEL dialogue script for "The 365 Crew at the Blue House":

EPISODE TITLE: {lineup.episode_title}
MATCH STATUS: {match_status}
DURATION: {lineup.total_duration_minutes} minutes

SEGMENT STRUCTURE (follow this order, but make transitions seamless and conversational):
{chr(10).join(segment_summary)}

GAME DATA:
{json.dumps(filtered_context, indent=2, default=str)}

{betting_info}

CRITICAL INSTRUCTIONS:

1. THREE-PERSON PANEL:
   - HOST: High-energy opening that acknowledges the trance intro music. Calibrated enthusiasm based on data importance (professional for standard stats, loses it for worldies). Stops reporting, starts reacting. Laughs and teases naturally.
   - ANALYST: Tactical expert who explains numbers as "insider secrets" to friends. Uses football slang when passionate, but keeps tone light and social. Doesn't just read numbers.
   - FAN: Emotional, direct, assigned to one team at the start. Mood matches situation (buzzing if won, gutted if lost, not perpetually excited). Uses slang naturally when it fits.

2. FAN ASSIGNMENT (MANDATORY):
   - At the very start, assign the Fan to either the home team or away team
   - If POST-MATCH: Fan's mood depends on result (buzzing if won, gutted/annoyed if lost - match the actual emotion)
   - If PRE-MATCH: Fan shows nerves/excitement for his team
   - Fan uses slang ONLY when it fits naturally, not forced into every sentence

3. DIALOGUE STYLE:
   - "Work-mates" vibe - they work together at 365Scores
   - Use names, finish each other's sentences, light banter
   - BREAK MONOLOGUES: Short, punchy sentences - avoid long blocks of text. Use fragments naturally.
   - Natural transitions - no "Segment 1", "Segment 2" mentions
   - STRICTLY use contractions (don't, it's, you're, we've, that's, they're)
   - Use verbal fillers naturally: "I mean," "Look," "To be fair," "Actually," "Wait, wait, wait"
   - Include reactive listening with stage directions: [chuckles], [laughs], [quick interruption]
   - Use referential talk: "Like [Name] just said..." or "I get your point, but..."
   - CONVERSATIONAL TENNIS: Quick back-and-forth with short interjections ("Spot on!", "Mental!", "No way...", "Seriously?", "Exactly my point")
   - VARIABLE SENTENCE LENGTH: Mix longer analytical points with very short reactions. Not every turn needs to be a full sentence.
   - STACCATO DELIVERY: After the trance intro, use short, detached sentences to match the high energy.

4. DATA INJECTION:
   - Analyst provides the numbers/tactics
   - Host reacts with calibrated enthusiasm (scales with data importance)
   - Fan gives emotional perspective from the stands

5. FOOTBALL SLANG:
   - Use authentic English football terms naturally
   - "Worldie", "Top bins", "Clinical finish", "Proper shift", "Bottled it", etc.

6. THE "N/A" FILTER:
   - If data is "N/A" or "NOT_AVAILABLE", ignore it completely
   - Don't mention missing data - just skip to next available topic

7. FORMAT:
   - Use clear labels: HOST:, ANALYST:, FAN:
   - Include [PAUSE:short/medium/long] markers for pacing
   - Total duration: approximately {lineup.total_duration_minutes} minutes

Generate the complete THREE-PERSON PANEL dialogue script now."""

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
