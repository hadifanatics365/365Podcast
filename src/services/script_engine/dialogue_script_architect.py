"""Dialogue-based script architect for natural Moderator-Fan conversations."""

import json
import logging
from typing import Any, Optional

from anthropic import Anthropic, APIError

from src.config import Settings, get_settings
from src.exceptions import HolyTriangleError, ScriptGenerationError
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
        logger.info(f"[STEP 7] Generating dialogue script for {lineup.match_status} episode")

        # Verify Holy Triangle (PILLAR 1, 2, 3)
        logger.info("[STEP 7] Verifying Holy Triangle prerequisites...")
        
        # PILLAR 1 (The WHAT): Enriched Data Context
        if not game_context:
            raise HolyTriangleError(
                message="PILLAR 1 (Enriched Data Context) is missing",
                missing_pillar="PILLAR_1",
                pillar_details={"context_exists": False}
            )
        
        game_data = game_context.get("game") or (game_context.get("games", [{}])[0] if game_context.get("games") else {})
        if not game_data:
            raise HolyTriangleError(
                message="PILLAR 1 (Enriched Data Context) missing basic game info",
                missing_pillar="PILLAR_1",
                pillar_details={"has_game_data": False}
            )
        
        logger.info("[STEP 7] ✓ PILLAR 1 (The WHAT): Enriched Data Context verified")
        
        # PILLAR 2 (The HOW): Structured Lineup & Timing
        if not lineup:
            raise HolyTriangleError(
                message="PILLAR 2 (Structured Lineup) is missing",
                missing_pillar="PILLAR_2",
                pillar_details={"lineup_exists": False}
            )
        
        if not lineup.segments:
            raise HolyTriangleError(
                message="PILLAR 2 (Structured Lineup) has no segments",
                missing_pillar="PILLAR_2",
                pillar_details={"segment_count": 0}
            )
        
        if not lineup.episode_title:
            raise HolyTriangleError(
                message="PILLAR 2 (Structured Lineup) missing episode title",
                missing_pillar="PILLAR_2",
                pillar_details={"has_title": False}
            )
        
        logger.info("[STEP 7] ✓ PILLAR 2 (The HOW): Structured Lineup & Timing verified")
        
        # PILLAR 3 (The WHO): Personality & Vibe Profiles
        # Personas are defined in system prompt (hardcoded)
        # We verify by checking the service is properly initialized
        if not self.client:
            raise HolyTriangleError(
                message="PILLAR 3 (Personality & Vibe Profiles) - Claude client not initialized",
                missing_pillar="PILLAR_3",
                pillar_details={"client_exists": False}
            )
        
        logger.info("[STEP 7] ✓ PILLAR 3 (The WHO): Personality & Vibe Profiles verified")
        logger.info("[STEP 7] ✓ Holy Triangle verified - all three pillars present")

        # Detect match status from game data
        match_status = self._detect_match_status(game_context, lineup.status)

        # Build system prompt (includes Panel Dynamics and Conflict Rule)
        system_prompt = self._build_system_prompt(match_status)

        # Build user prompt with game data and lineup (includes grounding instructions)
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
            
            # Validate timing
            self._validate_script_timing(script, lineup)
            
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

👥 THE PANELISTS (The "365 Crew") - PANEL DYNAMICS:

1. THE HOST (The "Anchor"):
   - Role: Keeps time and pacing, introduces segments and transitions, mediates between Analyst and Fan
   - Style: High-energy, professional, seeks headlines. She drives the pace.
   - Calibrated Enthusiasm: Her reaction MUST scale with the data importance:
     * Standard Data (e.g., 1-0 win): Professional and warm
     * Unusual Data (e.g., Late comeback): Excited and inquisitive
     * Historic/Rare Data (e.g., Record-breaking stat): Absolute shock and high intensity
   - Human Touch: She laughs, teases the guys, and reacts emotionally to the "story" of the game.
   - Uses names: "Listen, [Name]...", "What do you think, [Name]?"
   - Mediation: When Fan and Analyst disagree, she naturally bridges their perspectives

2. THE ANALYST (The "Brain"):
   - Role: Uses stats, xG, tactical terms. Skeptical of "luck" - prefers data-driven arguments
   - Style: Tactical expert who simplifies complex data (xG, heatmaps, transitions).
   - Vibe: A "social freak" – polite but loves a good tactical debate. CALM and MEASURED - not overly excited.
   - Tone Balance: Keep excitement CALIBRATED:
     * Most of the time: Calm, measured, analytical - "Yeah, the numbers show..."
     * When passionate about a specific play: Slightly more energy, but still controlled
     * Avoid: Over-the-top excitement for standard stats or routine plays
     * Sound like a knowledgeable friend explaining tactics, not a hype man
   - Language: Clear English with occasional "street-wise" football slang when passionate about a specific play.
   - Examples: "That's a proper shift from the midfield", "Absolute worldie of a finish", "They bottled it in the final third"
   - Data-Driven: Challenges emotional arguments with facts. Says things like "The numbers don't lie" or "But the xG tells a different story"
   - Skeptical: Questions "luck" and prefers statistical explanations
   - Natural Delivery: Sound conversational and relaxed, not like reading from a script

3. THE FAN (The "Heart"):
   - Role: Passionate, biased towards one team (assigned dynamically at start). Uses emotional arguments
   - Style: Emotional, direct, and lives for the "spirit" of the game.
   - Affiliation: [MANDATORY] At the start of the script, assign the Fan to one of the two teams.
   - Tone Balance: Keep excitement CALIBRATED and REALISTIC:
     * If his team won: Happy and proud, but not over-the-top - "Yeah, buzzing with that result!"
     * If his team lost: Disappointed but measured - "Gutted, but fair play to them"
     * If PRE-MATCH: Nervous/excited, but controlled - "Nervous, but excited to see what happens"
     * Avoid: Constant high-energy excitement - match the actual emotional state
     * Sound like a real fan, not a hype machine
   - Emotional Arguments: Reacts with gut feeling, not just stats. Says things like "But you can't measure heart!" or "The stats don't show the passion on the pitch"
   - Biased: Naturally favors his team but remains respectful
   - Natural Delivery: Sound authentic and genuine, not like performing

🎭 CONFLICT RULE (CRITICAL):
   - At least ONCE per episode, especially in "The Final Ticket" segment, the Fan and Analyst MUST have a friendly disagreement
   - Based on their different perspectives: Data vs. Emotion
   - Example: 
     * ANALYST: "The numbers don't lie - that xG suggests they should've scored more."
     * FAN: "But you can't measure heart! Did you see the passion out there?"
     * ANALYST: "I hear you, but passion doesn't win games - clinical finishing does."
     * HOST: [Mediates] "Alright, both of you make valid points. Let's see what the data says..."
   - Must be respectful and conversational, not argumentative
   - Host naturally mediates the disagreement
   - This creates authentic chemistry and engaging dialogue

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

3. CALIBRATED PERSONA REFINEMENT (TONE BALANCE - CRITICAL):
   - The Host: Natural and conversational, NOT robotic or formal. Sound like a friend hosting a chat, not a news anchor. Keep enthusiasm CALIBRATED:
     * Standard stats: Casual, warm, conversational - "Yeah, that's interesting"
     * Unusual stats: Genuinely interested but natural - "Oh, really? That's cool"
     * Historic stats: Surprised but authentic - "Wait, that's mad!"
     * NO formal announcements or scripted-sounding phrases
     * Use natural speech: "So, lads..." not "Now, let's discuss..."
     * Vary sentence structure, use natural pauses and fillers
   - The Fan (Grounded Passion): Keep excitement REALISTIC and CALIBRATED:
     * If team won: Happy and proud, but not over-the-top - "Yeah, buzzing with that!"
     * If team lost: Disappointed but measured - "Gutted, but fair play"
     * If PRE-MATCH: Nervous/excited, but controlled - "Nervous, but excited"
     * Avoid constant high-energy - match the actual emotional state
     * Sound like a real fan, not a hype machine
     * Use slang naturally when it fits, not forced
   - The Analyst: CALM and MEASURED, not overly excited:
     * Most of the time: Calm, analytical, conversational - "Yeah, the numbers show..."
     * When passionate: Slightly more energy, but still controlled
     * Avoid over-the-top excitement for standard stats
     * Sound like a knowledgeable friend explaining tactics, not a hype man
     * Explain data as "insider secrets" to friends, keeping tone light and social
     * Casual, relatable, natural language - chatting at a pub, not presenting in a boardroom

4. SEAMLESS TRANSITIONS:
   - No Segments: NEVER mention "Moving to the next topic" or "Let's talk about..." or "Now we'll discuss..." Transition naturally based on the flow: "Speaking of that defense, did you see the lineup Arteta put out?" or "You know what, that reminds me of..." or "Wait, hold on - before we get into that..."
   - The "N/A" Silence: If data is missing, it is INVISIBLE. Never apologize for missing data ("Unfortunately, we don't have..."). Simply pivot to the next exciting thing that IS available. Act as if the missing topic never existed.

🗣️ DYNAMIC SENTENCE FLOW & PACING (The "Real Talk" Update):

1. BREAK THE MONOLOGUES - SHORT LINES RULE (CRITICAL):
   - No Speeches: Avoid long blocks of text for any single speaker. A panelist's turn should feel like a thought, not a presentation.
   - SHORT LINES UNLESS EXPLAINING: Keep dialogue lines SHORT (1-2 sentences max) UNLESS the character is:
     * Explaining something important (tactical insight, key stat, story context)
     * Telling a story or anecdote
     * Providing crucial context that requires more detail
   - Default to SHORT: Most lines should be 1-2 sentences. Only go longer when absolutely necessary for clarity or storytelling.
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

5. DIALOGUE FORMAT (CRITICAL - MUST USE BRACKETS):
   - Use clear speaker labels with SQUARE BRACKETS: "[HOST]:", "[ANALYST]:", "[FAN]:"
   - Format: [CHARACTER]: dialogue text
   - Example:
     [HOST]: Yes! Come on! That beat? Electric.
     [ANALYST]: Mental! Absolutely mental.
     [FAN]: Seriously? That's...
   - Make it feel like a real conversation with back-and-forth
   - BREAK MONOLOGUES: Short, punchy sentences. Avoid long blocks of text. Use fragments naturally.
   - The Host drives the pace, the Analyst provides tactical insight, the Fan gives emotional perspective
   - They finish each other's sentences, use names, engage in banter
   - Include stage directions for reactions: [chuckles], [laughs], [quick interruption], [sighs]
   - STRICTLY use contractions throughout (don't, it's, you're, we've, that's, they're)
   - CONVERSATIONAL TENNIS: Quick back-and-forth with short interjections ("Spot on!", "Mental!", "No way...", "Seriously?")
   - VARIABLE LENGTH: Mix longer analytical points with very short reactions. Not every turn needs to be a full sentence.
   - STACCATO DELIVERY: Use short, detached sentences during high excitement, especially after the trance intro.
   
   🎭 REALISTIC OVERLAPPING DIALOGUE (CRITICAL - 4-5 TIMES PER EPISODE):
   - Characters sometimes try to talk at the same time - this is REALISTIC and makes dialogue feel natural
   - Format overlapping dialogue like this:
     [HOST]: So, looking at the stats--
     [ANALYST]: [interrupting] Yeah, the xG is--
     [HOST]: [laughs] Let me finish! The stats show...
   - Or:
     [FAN]: But you can't--
     [ANALYST]: [simultaneously] The numbers don't lie--
     [HOST]: [mediating] Alright, both of you! [Name], you first.
   - Include 4-5 instances of overlapping/interrupting dialogue throughout the episode
   - Use stage directions: [interrupting], [simultaneously], [talking over], [cuts in]
   - This creates authentic, natural conversation flow - people don't wait perfectly for each other
   - Place overlaps at natural moments: when someone is excited, when there's disagreement, when someone wants to add a point

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

        # Build segment summary with detailed data points and TIMING TARGETS
        segment_summary = []
        total_target_words = 0
        
        for i, segment in enumerate(lineup.segments, 1):
            if segment.topic in ["Introduction", "Outro"]:
                continue  # Skip intro/outro in segment list
            
            # CRITICAL: Include timing targets for each segment
            segment_info = f"- {segment.topic}"
            segment_info += f"\n  ⏱️  TIMING TARGET: {segment.allocated_time} seconds = ~{segment.estimated_word_count} words"
            segment_info += f"\n  📝 WORD COUNT TARGET: Approximately {segment.estimated_word_count} words (MUST MATCH)"
            total_target_words += segment.estimated_word_count
            
            # Include key data points - CRITICAL for data grounding
            if segment.key_data_points:
                # Only include available data points
                available_points = [
                    p for p in segment.key_data_points 
                    if "NOT_AVAILABLE" not in p.upper() and "N/A" not in p.upper()
                ]
                if available_points:
                    segment_info += f"\n  KEY DATA POINTS (MUST USE IN DIALOGUE):"
                    for point in available_points[:5]:  # Show up to 5 key points
                        segment_info += f"\n    • {point}"
            
            # Include source data references for verification
            if segment.source_data_refs:
                segment_info += f"\n  SOURCE DATA REFS: {', '.join(segment.source_data_refs[:3])}"
            
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

        # Calculate total target word count
        total_target_words = lineup.total_duration_minutes * 150  # 150 words per minute
        total_target_seconds = lineup.total_duration_minutes * 60
        
        prompt = f"""Generate a natural THREE-PERSON PANEL dialogue script for "The 365 Crew at the Blue House":

EPISODE TITLE: {lineup.episode_title}
MATCH STATUS: {match_status}
⏱️  TOTAL DURATION: {lineup.total_duration_minutes} minutes ({total_target_seconds} seconds)
📝 TOTAL WORD COUNT TARGET: {total_target_words} words (MUST MATCH EXACTLY - NEITHER LESS NOR MORE)
🎯 SPEAKING RATE: 150 words per minute = 2.5 words per second

SEGMENT STRUCTURE (follow this order, but make transitions seamless and conversational):
{chr(10).join(segment_summary)}

⚠️ CRITICAL: DATA USAGE REQUIREMENT
- Each segment has KEY DATA POINTS listed above - you MUST incorporate these specific facts into the dialogue
- The SOURCE DATA REFS show where this data comes from in the Game Data JSON below
- For each segment, ensure the characters discuss the KEY DATA POINTS - don't just mention them, have them debate, react, and analyze them
- The dialogue MUST be grounded in these specific data points - this is the Holy Triangle PILLAR 1 (The WHAT)
- If a KEY DATA POINT is listed, it MUST appear in the dialogue for that segment
- Use the actual values from the data (team names, scores, stats, player names, odds, etc.) - don't generalize

GAME DATA (PILLAR 1 - The WHAT):
{json.dumps(filtered_context, indent=2, default=str)}

{betting_info}

CRITICAL INSTRUCTIONS:

1. THREE-PERSON PANEL (TONE BALANCE - CRITICAL):
   - HOST: Natural, conversational, warm - NOT robotic or formal. Sound like a friend hosting a chat:
     * Keep enthusiasm CALIBRATED: Casual for standard stats, genuinely interested for unusual stats, naturally surprised for historic stats
     * NO formal announcements or scripted-sounding phrases
     * Use natural speech: "So, lads..." not "Now, let's discuss..."
     * Vary sentence structure, use natural pauses and fillers
     * High-energy opening that acknowledges trance intro, but then settles into natural conversation
   - ANALYST: CALM and MEASURED, not overly excited:
     * Most of the time: Calm, analytical, conversational - "Yeah, the numbers show..."
     * When passionate: Slightly more energy, but still controlled
     * Avoid over-the-top excitement for standard stats
     * Sound like a knowledgeable friend explaining tactics, not a hype man
     * Casual, relatable, natural - chatting at a pub, not presenting data
   - FAN: Keep excitement REALISTIC and CALIBRATED:
     * If team won: Happy and proud, but not over-the-top
     * If team lost: Disappointed but measured
     * If PRE-MATCH: Nervous/excited, but controlled
     * Avoid constant high-energy - match the actual emotional state
     * Sound like a real fan, not a hype machine

2. FAN ASSIGNMENT (MANDATORY):
   - At the very start, assign the Fan to either the home team or away team
   - If POST-MATCH: Fan's mood depends on result (buzzing if won, gutted/annoyed if lost - match the actual emotion)
   - If PRE-MATCH: Fan shows nerves/excitement for his team
   - Fan uses slang ONLY when it fits naturally, not forced into every sentence

3. DIALOGUE STYLE - SHORT LINES RULE (CRITICAL):
   - "Work-mates" vibe - they work together at 365Scores
   - Use names, finish each other's sentences, light banter
   - **SHORT LINES BY DEFAULT: Keep dialogue lines SHORT (1-2 sentences max) unless:**
     * Explaining something important (tactical insight, key stat, crucial context)
     * Telling a story or anecdote
     * Providing context that requires more detail for clarity
   - BREAK MONOLOGUES: Short, punchy sentences - avoid long blocks of text. Use fragments naturally.
   - Most lines should be brief and punchy - this creates natural flow and prevents robotic monologues
   - Break longer thoughts into multiple short exchanges between characters
   - Natural transitions - no "Segment 1", "Segment 2" mentions
   - STRICTLY use contractions (don't, it's, you're, we've, that's, they're)
   - Use verbal fillers naturally: "I mean," "Look," "To be fair," "Actually," "Wait, wait, wait"
   - Include reactive listening with stage directions: [chuckles], [laughs], [quick interruption]
   - Use referential talk: "Like [Name] just said..." or "I get your point, but..."
   - CONVERSATIONAL TENNIS: Quick back-and-forth with short interjections ("Spot on!", "Mental!", "No way...", "Seriously?", "Exactly my point")
   - VARIABLE SENTENCE LENGTH: Mix longer analytical points with very short reactions. Not every turn needs to be a full sentence.
   - STACCATO DELIVERY: After the trance intro, use short, detached sentences to match the high energy.

4. DATA INJECTION (CRITICAL - USE KEY DATA POINTS):
   - **MANDATORY**: Each segment has KEY DATA POINTS listed above - you MUST use these specific facts in the dialogue
   - Analyst provides the numbers/tactics from the KEY DATA POINTS
   - Host reacts with calibrated enthusiasm (scales with data importance) to the KEY DATA POINTS
   - Fan gives emotional perspective from the stands about the KEY DATA POINTS
   - **DO NOT** create generic dialogue - reference specific teams, players, scores, stats, odds from the KEY DATA POINTS
   - **DO NOT** skip data points - if a KEY DATA POINT is listed, it must be discussed in that segment
   - Use actual values: "Man United won 3-1" not "the home team won", "2.10 odds" not "favorable odds"
   - Reference specific players by name when mentioned in KEY DATA POINTS
   - Use actual standings positions, points, goal differences from KEY DATA POINTS

5. FOOTBALL SLANG:
   - Use authentic English football terms naturally
   - "Worldie", "Top bins", "Clinical finish", "Proper shift", "Bottled it", etc.

6. SHORT LINES RULE (CRITICAL - ANTI-ROBOTIC):
   - Keep dialogue lines SHORT (1-2 sentences max) by default
   - Only use longer lines when:
     * Explaining something important (tactical insight, key stat, crucial context)
     * Telling a story or anecdote
     * Providing context that requires more detail for clarity
   - Most lines should be brief and punchy - this creates natural flow and prevents robotic monologues
   - Break longer thoughts into multiple short exchanges between characters
   - Example of SHORT (preferred):
     [HOST]: Mental result!
     [ANALYST]: Yeah, the xG was wild.
     [FAN]: Seriously?
     [ANALYST]: 2.3 to 0.8. They bottled it.
   - Example of LONG (only when explaining important context):
     [ANALYST]: Look, here's the thing - when you look at the pressing triggers, they were actually winning the ball back in dangerous areas, but the final pass was just off. The xG model shows 2.3 expected goals, but they only converted once. That's the difference between a good performance and a great one.

7. THE "N/A" FILTER:
   - If data is "N/A" or "NOT_AVAILABLE", ignore it completely
   - Don't mention missing data - just skip to next available topic

8. GROUNDING & ANTI-HALLUCINATION (CRITICAL):
   - STRICT GROUNDING GUARDRAIL: If a specific data point (player name, score, odd, stat) is missing from the Enriched Context (PILLAR 1), you MUST:
     * Option 1: Pivot to a different available data point
     * Option 2: Generalize without specific numbers (e.g., "high odds" instead of "3.57")
     * Option 3: Skip the topic entirely
   - NEVER FABRICATE:
     * Specific player names not in context
     * Specific scores not in context
     * Specific odds not in context
     * Specific stats not in context
   - Fabrication is a CRITICAL FAILURE - verify all data points against the provided context
   - Cross-reference every specific fact you mention against the Game Data JSON below

9. CONFLICT RULE (MANDATORY):
   - At least ONCE per episode, especially in "The Final Ticket" segment, create a friendly disagreement between the Fan and Analyst
   - Fan uses emotional arguments ("But you can't measure heart!")
   - Analyst uses data-driven arguments ("The numbers don't lie")
   - Host mediates naturally
   - Must be respectful and conversational, not argumentative

10. ⏱️  EXACT DURATION REQUIREMENT (CRITICAL - MANDATORY):
   - **TOTAL DURATION:** The complete script MUST generate exactly {lineup.total_duration_minutes} minutes ({total_target_seconds} seconds)
   - **TOTAL WORD COUNT:** The complete script MUST generate approximately {total_target_words} words
   - **NEITHER LESS NOR MORE** - this is a hard requirement
   - **PER-SEGMENT TIMING:** Each segment above has a specific timing target:
     * Segment timing targets are listed in the SEGMENT STRUCTURE above
     * Each segment's dialogue must match its allocated time and word count target
     * Example: If a segment is allocated 60 seconds (150 words), generate approximately 150 words for that segment
   - **TIMING PRECISION:**
     * Total script word count must be within ±5% of {total_target_words} words
     * Each segment's word count must be within ±10% of its target
     * If you exceed a segment's target, trim it. If you fall short, expand it naturally.
   - **CALCULATION:**
     * Speaking rate: 150 words per minute = 2.5 words per second
     * For each segment: target_words = allocated_time * 2.5
     * Total: {total_target_words} words = {lineup.total_duration_minutes} minutes * 150 words/minute
   - **VALIDATION:**
     * After generating the script, count the words
     * Ensure total word count matches {total_target_words} words (±5%)
     * Ensure each segment matches its word count target (±10%)
     * If validation fails, adjust the script to match targets exactly

11. FORMAT:
   - Use clear labels with SQUARE BRACKETS: [HOST]:, [ANALYST]:, [FAN]:
   - Include [PAUSE:short/medium/long] markers for pacing
   - **Total duration: EXACTLY {lineup.total_duration_minutes} minutes ({total_target_words} words) - MANDATORY**

⚠️ FINAL CRITICAL REQUIREMENT - DATA USAGE:
- Each segment above has KEY DATA POINTS listed - these are SPECIFIC facts extracted from the Game Data JSON
- You MUST incorporate these KEY DATA POINTS into the dialogue for each segment
- DO NOT create generic dialogue - use the actual values from KEY DATA POINTS:
  * Use actual team names (not "the home team")
  * Use actual scores (not "they won")
  * Use actual stats (not "good performance")
  * Use actual player names (not "the striker")
  * Use actual odds (not "favorable odds")
  * Use actual standings positions (not "high in table")
- The SOURCE DATA REFS show where this data comes from - verify it exists in the Game Data JSON before using
- If a KEY DATA POINT is listed for a segment, it MUST appear in that segment's dialogue
- This is the Holy Triangle PILLAR 1 (The WHAT) - the dialogue MUST be grounded in this specific data

Generate the complete THREE-PERSON PANEL dialogue script now. Ensure at least one friendly disagreement between Fan and Analyst, and verify all data points against the provided context. MOST IMPORTANTLY: Use the KEY DATA POINTS from each segment in the actual dialogue."""

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
    
    def _validate_script_timing(self, script: str, lineup: PodcastLineup) -> None:
        """
        Validate that the generated script matches the target duration.
        
        Args:
            script: Generated dialogue script
            lineup: PodcastLineup with timing targets
        """
        # Calculate word count
        word_count = len(script.split())
        
        # Calculate target word count (150 words per minute)
        target_words = lineup.total_duration_minutes * 150
        target_seconds = lineup.total_duration_minutes * 60
        
        # Calculate tolerance (±5% for total, ±10% per segment)
        total_tolerance = target_words * 0.05
        min_words = target_words - total_tolerance
        max_words = target_words + total_tolerance
        
        # Log validation results
        logger.info(f"[STEP 7] Timing Validation:")
        logger.info(f"  Target: {target_words} words ({lineup.total_duration_minutes} minutes / {target_seconds} seconds)")
        logger.info(f"  Actual: {word_count} words")
        logger.info(f"  Tolerance: ±{total_tolerance:.0f} words (±5%)")
        logger.info(f"  Range: {min_words:.0f} - {max_words:.0f} words")
        
        # Check if within tolerance
        if word_count < min_words:
            shortfall = min_words - word_count
            shortfall_percent = (shortfall / target_words) * 100
            logger.warning(
                f"[STEP 7] ⚠️  Script is TOO SHORT: {word_count} words (target: {target_words} words)"
                f" - Shortfall: {shortfall:.0f} words ({shortfall_percent:.1f}%)"
            )
            logger.warning(
                f"[STEP 7] ⚠️  Script duration: ~{word_count / 150:.1f} minutes (target: {lineup.total_duration_minutes} minutes)"
            )
        elif word_count > max_words:
            excess = word_count - max_words
            excess_percent = (excess / target_words) * 100
            logger.warning(
                f"[STEP 7] ⚠️  Script is TOO LONG: {word_count} words (target: {target_words} words)"
                f" - Excess: {excess:.0f} words ({excess_percent:.1f}%)"
            )
            logger.warning(
                f"[STEP 7] ⚠️  Script duration: ~{word_count / 150:.1f} minutes (target: {lineup.total_duration_minutes} minutes)"
            )
        else:
            logger.info(f"[STEP 7] ✓ Script duration validated: {word_count} words within tolerance")
            logger.info(f"[STEP 7] ✓ Estimated duration: ~{word_count / 150:.1f} minutes (target: {lineup.total_duration_minutes} minutes)")
        
        # Note: We log warnings but don't raise errors to allow flexibility
        # The prompt instructions should guide Claude to generate the correct length