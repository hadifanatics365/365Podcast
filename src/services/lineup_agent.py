"""AI Executive Producer service for planning podcast episode structure."""

import json
import logging
from enum import Enum
from typing import Any, Optional

from anthropic import Anthropic, APIError
from pydantic import BaseModel, Field

from src.config import Settings, get_settings
from src.exceptions import ScriptGenerationError
from src.models import Game, GameStatus

logger = logging.getLogger(__name__)


class EpisodeStatus(str, Enum):
    """Episode status type."""

    PRE_MATCH = "pre_match"
    POST_MATCH = "post_match"


class SegmentTone(str, Enum):
    """Tone for podcast segments (legacy support)."""

    ANALYTICAL = "analytical"
    EXCITED = "excited"
    DRAMATIC = "dramatic"
    CONVERSATIONAL = "conversational"
    INFORMATIVE = "informative"


class PodcastSegment(BaseModel):
    """A single segment in the podcast lineup."""

    topic: str = Field(description="Segment topic/title")
    key_data_points: list[str] = Field(
        default_factory=list,
        description="Specific facts from the game data to be used (ONLY from provided JSON)",
    )
    tone_level: int = Field(
        ge=1,
        le=5,
        description="Tone level: 1=Cold/Analytical, 2=Informative, 3=Conversational, 4=Energetic, 5=High Octane/Excited",
    )
    tone: SegmentTone = Field(
        default=SegmentTone.CONVERSATIONAL,
        description="Legacy tone field (derived from tone_level)",
    )
    allocated_time: int = Field(description="Duration in seconds")
    estimated_word_count: int = Field(description="Estimated words based on speaking speed")
    source_data_refs: list[str] = Field(
        default_factory=list,
        description="JSON keys/paths from GameContext used in this segment (for grounding verification)",
    )
    transition_cue: str = Field(
        default="",
        description="Instruction on how to bridge from the previous segment",
    )


class PodcastLineup(BaseModel):
    """Complete podcast episode lineup/plan."""

    episode_title: str = Field(description="Catchy headline for the episode")
    status: EpisodeStatus = Field(description="PRE_MATCH or POST_MATCH")
    match_status: str = Field(description="Human-readable match status (PRE_MATCH or POST_MATCH)")
    total_duration_minutes: int = Field(description="Total episode duration")
    segments: list[PodcastSegment] = Field(default_factory=list, description="Episode segments")
    priority_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Overall priority/importance score for this episode",
    )

    def to_human_rundown(self) -> str:
        """
        Generate a human-readable production rundown (no JSON, no technical metadata).

        Returns:
            Beautifully formatted string for human producers/narrators
        """
        lines = []
        lines.append("=" * 80)
        lines.append(f"PODCAST PRODUCTION RUNDOWN")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"📻 EPISODE: {self.episode_title}")
        lines.append(f"⏱️  DURATION: {self.total_duration_minutes} minutes")
        lines.append(f"📊 STATUS: {self.match_status}")
        lines.append(f"⭐ PRIORITY SCORE: {self.priority_score}/100")
        lines.append("")
        lines.append("-" * 80)
        lines.append("SEGMENT BREAKDOWN")
        lines.append("-" * 80)
        lines.append("")

        total_time = 0
        for i, segment in enumerate(self.segments, 1):
            tone_desc = self._get_tone_description_for_rundown(segment.tone_level)
            
            lines.append(f"🎬 SEGMENT {i}: {segment.topic}")
            lines.append(f"   ⏱️  Time: {segment.allocated_time}s (~{segment.estimated_word_count} words)")
            lines.append(f"   🎭 Tone: {tone_desc}")
            
            if segment.key_data_points:
                lines.append(f"   📝 Key Facts:")
                for point in segment.key_data_points:
                    lines.append(f"      • {point}")
            
            if segment.transition_cue and i > 1:
                prev_seg = self.segments[i - 2]
                lines.append(f"   🔗 Transition from '{prev_seg.topic}':")
                lines.append(f"      {segment.transition_cue}")
            
            # Producer Note
            producer_note = self._generate_producer_note(segment, i)
            if producer_note:
                lines.append(f"   📌 PRODUCER NOTE: {producer_note}")
            
            lines.append("")
            total_time += segment.allocated_time

        lines.append("-" * 80)
        lines.append(f"TOTAL RUNTIME: {total_time} seconds ({total_time/60:.1f} minutes)")
        lines.append("=" * 80)
        
        return "\n".join(lines)

    @staticmethod
    def _get_tone_description_for_rundown(tone_level: int) -> str:
        """Get human-readable tone description for rundown."""
        descriptions = {
            1: "Cold & Analytical (pure stats, no emotion)",
            2: "Informative (factual but accessible)",
            3: "Conversational (friendly, engaging)",
            4: "Energetic (excited, animated)",
            5: "High Octane (maximum energy, dramatic)",
        }
        return descriptions.get(tone_level, "Conversational")

    @staticmethod
    def _generate_producer_note(segment: PodcastSegment, segment_num: int) -> str:
        """Generate a one-sentence producer note for the narrator."""
        if not segment.key_data_points:
            return "Emphasize the narrative flow and maintain listener engagement."
        
        # Pick the most impactful data point
        key_point = segment.key_data_points[0] if segment.key_data_points else ""
        
        # Generate context-specific note
        if "score" in key_point.lower() or "goal" in key_point.lower():
            return f"Emphasize the specific score or goal moment: '{key_point}' - make it dramatic."
        elif "injury" in key_point.lower() or "suspension" in key_point.lower():
            return f"Highlight the impact: '{key_point}' - explain how this affects the team's chances."
        elif "formation" in key_point.lower() or "tactical" in key_point.lower():
            return f"Break down the tactical element: '{key_point}' - explain why this matters."
        elif "odds" in key_point.lower() or "betting" in key_point.lower():
            return f"Present the betting angle clearly: '{key_point}' - explain what this means for bettors."
        else:
            return f"Emphasize this key fact: '{key_point}' - make it memorable for listeners."


class LineupAgent:
    """
    AI Executive Producer that plans podcast episode structure.

    Responsibilities:
    - Detect game status (PRE-MATCH vs POST-MATCH)
    - Score and prioritize data points
    - Allocate time dynamically across segments
    - Generate script prompts for ScriptGenerator
    """

    # Average speaking speed: 150 words per minute = 2.5 words per second
    WORDS_PER_MINUTE = 150
    WORDS_PER_SECOND = 2.5

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.client = Anthropic(api_key=self.settings.anthropic_api_key)
        self.model = self.settings.claude_model

    def detect_status(self, game: Game) -> EpisodeStatus:
        """
        Detect if the game is PRE-MATCH or POST-MATCH.

        Args:
            game: Game object

        Returns:
            EpisodeStatus enum
        """
        if GameStatus.is_finished(game.gt):
            return EpisodeStatus.POST_MATCH
        elif GameStatus.is_upcoming(game.gt):
            return EpisodeStatus.PRE_MATCH
        elif GameStatus.is_live(game.gt):
            # Live games treated as post-match for analysis
            return EpisodeStatus.POST_MATCH
        else:
            # Default to pre-match for unknown status
            return EpisodeStatus.PRE_MATCH

    async def create_lineup(
        self,
        game_context: dict[str, Any],
        total_duration_minutes: int = 5,
    ) -> PodcastLineup:
        """
        Create a podcast lineup/plan based on game context.

        Args:
            game_context: Enriched game context from DataEnricher
            total_duration_minutes: Total episode duration (default: 5 minutes)

        Returns:
            PodcastLineup with planned segments
        """
        # Extract game data
        game_data = game_context.get("game") or (game_context.get("games", [{}])[0] if game_context.get("games") else {})
        
        # Detect status
        # Try to get game status from context - check if we have a Game object or just dict
        game_status = 0  # Default to upcoming
        
        # Check if game_context has a Game object directly
        if "game" in game_context and isinstance(game_context["game"], Game):
            status = self.detect_status(game_context["game"])
        elif "games" in game_context and game_context["games"]:
            # Check if first game is a Game object
            first_game = game_context["games"][0]
            if isinstance(first_game, Game):
                status = self.detect_status(first_game)
            else:
                # Extract from dict
                game_status = game_data.get("game_status") or game_data.get("gt", 0)
                game_id = game_data.get("game_id") or game_data.get("gid", 0)
                minimal_game = Game(
                    gid=game_id,
                    gt=game_status,
                    stime=game_data.get("start_time"),
                )
                status = self.detect_status(minimal_game)
        else:
            # Extract from dict
            game_status = game_data.get("game_status") or game_data.get("gt", 0)
            game_id = game_data.get("game_id") or game_data.get("gid", 0)
            minimal_game = Game(
                gid=game_id,
                gt=game_status,
                stime=game_data.get("start_time"),
            )
            status = self.detect_status(minimal_game)

        logger.info(f"Creating lineup for {status.value} episode (duration: {total_duration_minutes} min)")

        # Use Claude to analyze and prioritize
        prioritized_data = await self._analyze_with_claude(game_context, status, total_duration_minutes)

        # Allocate time to segments (pass game_context for data-driven titles)
        segments = self._allocate_time(prioritized_data, total_duration_minutes, status, game_context)

        # Generate episode title
        episode_title = await self._generate_title(game_context, status, prioritized_data)

        # Calculate overall priority score
        priority_score = self._calculate_priority_score(game_context, prioritized_data)

        return PodcastLineup(
            episode_title=episode_title,
            status=status,
            match_status=status.value.upper().replace("_", " "),
            total_duration_minutes=total_duration_minutes,
            segments=segments,
            priority_score=priority_score,
        )

    async def _analyze_with_claude(
        self,
        game_context: dict[str, Any],
        status: EpisodeStatus,
        total_duration_minutes: int,
    ) -> dict[str, Any]:
        """
        Use Claude to analyze game context and prioritize content.

        Args:
            game_context: Enriched game context
            status: Episode status (PRE_MATCH or POST_MATCH)
            total_duration_minutes: Total duration

        Returns:
            Prioritized data structure
        """
        # Build analysis prompt
        context_json = json.dumps(game_context, indent=2, default=str)

        # Extract available data keys for grounding
        available_keys = self._extract_available_keys(game_context)
        available_keys_str = json.dumps(available_keys[:50], indent=2)  # Limit to first 50 for prompt size

        if status == EpisodeStatus.PRE_MATCH:
            narrative_flow = """
            STANDARDIZED NARRATIVE FLOW (MUST FOLLOW THIS ORDER):
            1. The Hook (Intro): Match basics & High-level stakes
            2. Contextual Landscape: Standings, Recent Form, and H2H (The "Story" so far)
            3. The Personnel: Injuries, Suspensions, and Confirmed/Probable Lineups
            4. The X-Factor: Tactical analysis and Key Player matchups
            5. The Smart Money: Trends, Odds movement, and Prediction votes
            6. The Wrap-up (Outro): Closing thoughts
            """
            focus_areas = """
            PRE-MATCH DATA ONLY (FORBIDDEN to mention post-match data):
            - Core: Game info, Recent Form, H2H, Trends
            - Personnel: Probable lineups, Injuries, Key players
            - Market: Odds movements, Betting insights, Prediction results
            - Context: League standings, Pre-game news/headlines
            """
        else:
            narrative_flow = """
            STANDARDIZED NARRATIVE FLOW (MUST FOLLOW THIS ORDER):
            1. The Hook (Intro): Final score & Match result
            2. Key Moments: Goals, cards, substitutions, VAR decisions
            3. Statistical Breakdown: Possession, shots, passing accuracy
            4. Man of the Match: Top performers and ratings
            5. League Impact: Standings changes and implications
            6. The Wrap-up (Outro): Closing thoughts
            """
            focus_areas = """
            POST-MATCH DATA ONLY (FORBIDDEN to mention pre-game data):
            - Action: Match events (Goals, MOTM, Important subs, Red cards)
            - Performance: Player ratings, Post-game stats (xG, Possession), Shots map
            - Aftermath: Actual play time, Box scores, Standings update, Post-match quotes/news
            - Future: Prediction results (who was right?), Next matches mini-recap for betting
            """

        system_prompt = """You are a professional sports producer for a podcast. Your job is to analyze game data and create a prioritized content plan.

CRITICAL REQUIREMENTS - STRICT DATA GROUNDING & STATUS-SPECIFIC FILTERING:
1. ONLY use facts present in the provided GameContext JSON
2. DO NOT invent, assume, or hallucinate any data points
3. STATUS-SPECIFIC DATA FILTERING (CRITICAL):
   - If status is PRE_MATCH: ONLY use pre-game data (form, H2H, probable lineups, injuries, pre-game odds, standings, pre-game news)
   - If status is POST_MATCH: ONLY use post-match data (events, final score, post-game stats, MOTM, standings update, post-match news)
   - FORBIDDEN: Do NOT mention pre-game data in post-match pods, and vice-versa
4. If a specific data point is missing, pivot to another available data point from the correct status category
5. For each data point you use, reference the exact JSON key/path where it comes from
6. If data is not in JSON, explicitly state "NOT_AVAILABLE" and move to next available point

NARRATIVE CONTEXTUALIZATION - NO GENERIC TITLES:
- Generate SPECIFIC, DATA-DRIVEN segment titles based on actual data
- Bad: "Tactical Preview" → Good: "The Kanichowsky Factor: Can Hapoel Stop Maccabi's Engine?"
- Bad: "Match Events" → Good: "The 89th Minute Heartbreak: Zahavi's Clinical Finish Analyzed"
- Use actual player names, specific moments, specific statistics when available
- Make titles compelling and specific to THIS match, not generic

NARRATIVE FLOW:
Follow the standardized narrative flow exactly as specified. Do not deviate from the segment order.

TONE SCALE (1-5):
1: Cold/Analytical (pure stats, no emotion)
2: Informative (factual but accessible)
3: Conversational (friendly, engaging)
4: Energetic (excited, animated)
5: High Octane/Excited (maximum energy, dramatic)

TRANSITION RULES:
- Cannot jump more than 2 tone levels between consecutive segments
- If moving from Level 5 to Level 1, insert a bridge segment at Level 3
- Ensure smooth tonal transitions for natural listening experience

Focus on:
- Breaking news (injuries, lineup changes) - ONLY if in JSON and appropriate for status
- Dramatic statistics - ONLY if in JSON and appropriate for status
- Compelling narratives based on available data from correct status category
- Key tactical insights from available formations/stats (pre-match) or performance analysis (post-match)
- Betting value and trends - ONLY if in JSON and appropriate for status"""

        user_prompt = f"""Analyze this {status.value.upper()} game context and create a prioritized content plan:

GAME CONTEXT (ONLY USE DATA FROM THIS JSON):
{context_json}

AVAILABLE DATA KEYS (sample - verify data exists before using):
{available_keys_str}

{narrative_flow}

FOCUS AREAS FOR {status.value.upper()}:
{focus_areas}

TOTAL DURATION: {total_duration_minutes} minutes

Your task:
1. Follow the standardized narrative flow EXACTLY
2. STATUS-SPECIFIC FILTERING: Only use data appropriate for {status.value.upper()} status
3. Generate SPECIFIC, DATA-DRIVEN segment titles (use player names, specific moments, not generic titles)
4. For each data point, reference the JSON key/path (e.g., "game.home_team.name", "standings.home_team.position")
5. If data is missing, explicitly note "NOT_AVAILABLE" and use alternative available data from correct status category
6. Assign tone_level (1-5) to each segment
7. Ensure tone transitions don't jump more than 2 levels
8. Create transition_cue for each segment (except first)

Return a JSON object with this EXACT structure:
{{
    "priority_stories": [
        {{
            "story": "Brief description",
            "score": 85,
            "data_points": ["fact 1", "fact 2"],
            "source_refs": ["game.home_team.name", "standings.home_team.position"],
            "tone_level": 4
        }}
    ],
    "segment_suggestions": [
        {{
            "topic": "SPECIFIC title with player names/moments (e.g., 'The Kanichowsky Factor: Can Hapoel Stop Maccabi's Engine?')",
            "priority": 90,
            "suggested_duration_seconds": 45,
            "key_facts": ["fact 1 from JSON", "fact 2 from JSON"],
            "source_refs": ["exact.json.path.1", "exact.json.path.2"],
            "tone_level": 3,
            "transition_cue": "How to bridge from previous segment"
        }}
    ],
    "explosive_quotes": ["quote 1 from news JSON", "quote 2 from news JSON"],
    "betting_highlights": ["highlight 1 from betting JSON", "highlight 2 from betting JSON"],
    "missing_data": ["data_point_1", "data_point_2"],
    "status_data_used": ["list", "of", "data", "types", "from", "correct", "status", "category"]
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
            )

            # Extract JSON from response
            content = response.content[0].text
            logger.debug(f"Claude analysis response: {content[:500]}")

            # Try to extract JSON from the response
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                return json.loads(json_str)
            else:
                # Fallback: try to parse the whole response
                return json.loads(content)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.debug(f"Response content: {content[:1000]}")
            # Return fallback structure
            return self._create_fallback_prioritization(game_context, status)
        except APIError as e:
            logger.error(f"Claude API error: {e}")
            return self._create_fallback_prioritization(game_context, status)
        except Exception as e:
            logger.error(f"Unexpected error in Claude analysis: {e}")
            return self._create_fallback_prioritization(game_context, status)

    def _create_fallback_prioritization(
        self,
        game_context: dict[str, Any],
        status: EpisodeStatus,
    ) -> dict[str, Any]:
        """Create a fallback prioritization if Claude fails - uses status-specific data only."""
        game_data = game_context.get("game") or (game_context.get("games", [{}])[0] if game_context.get("games") else {})
        home_team = game_data.get("home_team", {}).get("name", "Home Team") if game_data else "Home Team"
        away_team = game_data.get("away_team", {}).get("name", "Away Team") if game_data else "Away Team"

        if status == EpisodeStatus.PRE_MATCH:
            # PRE-MATCH: Only pre-game data
            segments = [
                {
                    "topic": f"{home_team} vs {away_team}: What's at Stake",
                    "priority": 80,
                    "suggested_duration_seconds": 60,
                    "key_facts": [
                        f"{home_team} vs {away_team}",
                        f"Competition: {game_data.get('competition', 'Unknown')}",
                    ],
                    "tone_level": 4,
                    "source_refs": ["game.home_team", "game.away_team", "game.competition"],
                    "transition_cue": "",
                },
                {
                    "topic": "Recent Form & Head-to-Head Analysis",
                    "priority": 70,
                    "suggested_duration_seconds": 45,
                    "key_facts": ["Recent form data if available"],
                    "tone_level": 2,
                    "source_refs": ["form", "standings"],
                    "transition_cue": "Now let's examine recent form",
                },
            ]
        else:
            # POST-MATCH: Only post-game data
            final_score = game_data.get("final_score", {}) if game_data else {}
            home_score = final_score.get("home", 0) if final_score else 0
            away_score = final_score.get("away", 0) if final_score else 0
            
            segments = [
                {
                    "topic": f"{home_team} {home_score}-{away_score} {away_team}: The Final Result",
                    "priority": 90,
                    "suggested_duration_seconds": 90,
                    "key_facts": [
                        f"Final score: {home_team} {home_score}-{away_score} {away_team}",
                    ],
                    "tone_level": 5,
                    "source_refs": ["final_score", "winner"],
                    "transition_cue": "",
                },
                {
                    "topic": "Key Match Events: Goals & Decisive Moments",
                    "priority": 85,
                    "suggested_duration_seconds": 60,
                    "key_facts": ["Match events if available"],
                    "tone_level": 4,
                    "source_refs": ["events"],
                    "transition_cue": "Let's break down the key moments",
                },
            ]

        return {
            "priority_stories": [],
            "segment_suggestions": segments,
            "explosive_quotes": [],
            "betting_highlights": [],
        }

    def _extract_available_keys(self, game_context: dict[str, Any], prefix: str = "") -> list[str]:
        """
        Extract all available keys from game context for grounding verification.

        Args:
            game_context: Game context dictionary
            prefix: Current key prefix for nested structures

        Returns:
            List of key paths
        """
        keys = []
        for key, value in game_context.items():
            current_path = f"{prefix}.{key}" if prefix else key
            keys.append(current_path)
            
            if isinstance(value, dict):
                keys.extend(self._extract_available_keys(value, current_path))
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                # Handle list of dicts
                keys.append(f"{current_path}[0]")
                if len(value) > 0:
                    keys.extend(self._extract_available_keys(value[0], f"{current_path}[0]"))
        
        return keys

    def _allocate_time(
        self,
        prioritized_data: dict[str, Any],
        total_duration_minutes: int,
        status: EpisodeStatus,
        game_context: Optional[dict[str, Any]] = None,
    ) -> list[PodcastSegment]:
        """
        Allocate time to segments based on priority.

        Args:
            prioritized_data: Data from Claude analysis
            total_duration_minutes: Total duration
            status: Episode status

        Returns:
            List of PodcastSegment objects
        """
        total_seconds = total_duration_minutes * 60
        segments_data = prioritized_data.get("segment_suggestions", [])

        if not segments_data:
            # Create default segments following narrative flow with actual data
            segments_data = self._create_default_segments(status, total_seconds, game_context)

        # DO NOT sort by priority - maintain narrative flow order
        # The segments should already be in the correct order from Claude
        
        # Validate and fix tone transitions
        segments_data = self._enforce_tone_transitions(segments_data)

        # Calculate total priority for proportional allocation
        total_priority = sum(seg.get("priority", 50) for seg in segments_data)
        if total_priority == 0:
            total_priority = len(segments_data) * 50  # Fallback

        allocated_segments = []
        allocated_time = 0

        # Reserve time for intro/outro (30 seconds total)
        intro_outro_time = 30
        available_time = total_seconds - intro_outro_time

        previous_tone_level = 4  # Start at energetic for intro (level 4)

        for i, seg_data in enumerate(segments_data):
            priority = seg_data.get("priority", 50)
            suggested_duration = seg_data.get("suggested_duration_seconds", 0)
            tone_level = seg_data.get("tone_level", 3)  # Default to conversational

            # Calculate proportional time
            if i < len(segments_data) - 1:
                # Proportional allocation for all but last segment
                proportional_time = int((priority / total_priority) * available_time)
                # Use suggested duration as a guide
                duration = min(max(proportional_time, suggested_duration // 2), available_time - allocated_time)
            else:
                # Last segment gets remaining time
                duration = available_time - allocated_time

            # Ensure minimum duration
            duration = max(duration, 15)  # Minimum 15 seconds

            # Calculate word count
            word_count = int(duration * self.WORDS_PER_SECOND)

            # Get transition cue (empty for first segment)
            transition_cue = seg_data.get("transition_cue", "") if i > 0 else ""

            # Get source data refs
            source_refs = seg_data.get("source_refs", [])

            # Map tone_level to legacy tone enum
            tone = self._tone_level_to_enum(tone_level)

            segment = PodcastSegment(
                topic=seg_data.get("topic", f"Segment {i+1}"),
                key_data_points=seg_data.get("key_facts", []),
                tone_level=tone_level,
                tone=tone,
                allocated_time=duration,
                estimated_word_count=word_count,
                source_data_refs=source_refs,
                transition_cue=transition_cue,
            )

            allocated_segments.append(segment)
            allocated_time += duration
            previous_tone_level = tone_level

        # Add intro/outro segments with proper tone levels
        intro_segment = PodcastSegment(
            topic="Introduction",
            key_data_points=[],
            tone_level=4,  # Energetic for intro
            tone=SegmentTone.EXCITED,
            allocated_time=intro_outro_time // 2,
            estimated_word_count=int((intro_outro_time // 2) * self.WORDS_PER_SECOND),
            source_data_refs=[],
            transition_cue="",
        )

        outro_segment = PodcastSegment(
            topic="Outro",
            key_data_points=[],
            tone_level=3,  # Conversational for outro
            tone=SegmentTone.CONVERSATIONAL,
            allocated_time=intro_outro_time // 2,
            estimated_word_count=int((intro_outro_time // 2) * self.WORDS_PER_SECOND),
            source_data_refs=[],
            transition_cue="",
        )

        # Insert intro at start, outro at end
        allocated_segments.insert(0, intro_segment)
        allocated_segments.append(outro_segment)

        # Verify total time matches
        total_allocated = sum(seg.allocated_time for seg in allocated_segments)
        if total_allocated != total_seconds:
            # Adjust the last segment to match exactly
            difference = total_seconds - total_allocated
            if allocated_segments:
                allocated_segments[-1].allocated_time += difference
                allocated_segments[-1].estimated_word_count = int(
                    allocated_segments[-1].allocated_time * self.WORDS_PER_SECOND
                )

        logger.info(
            f"Allocated {len(allocated_segments)} segments totaling {total_seconds} seconds "
            f"({total_duration_minutes} minutes)"
        )

        return allocated_segments

    def _enforce_tone_transitions(self, segments_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Enforce tone transition rules (max 2 level jumps).

        Args:
            segments_data: List of segment data dictionaries

        Returns:
            Adjusted segments with proper tone transitions
        """
        if not segments_data:
            return segments_data

        adjusted_segments = []
        previous_tone = 3  # Start at conversational

        for i, seg in enumerate(segments_data):
            current_tone = seg.get("tone_level", 3)
            tone_diff = abs(current_tone - previous_tone)

            if tone_diff > 2:
                # Need to insert bridge or adjust
                # Adjust current tone to be within 2 levels
                if current_tone > previous_tone:
                    adjusted_tone = min(previous_tone + 2, current_tone)
                else:
                    adjusted_tone = max(previous_tone - 2, current_tone)

                seg["tone_level"] = adjusted_tone
                seg["transition_cue"] = f"Gradually shift from tone level {previous_tone} to {adjusted_tone}"
                logger.info(
                    f"Adjusted tone transition: {previous_tone} -> {current_tone} "
                    f"(too large) -> {adjusted_tone}"
                )
            elif i > 0:
                # Add transition cue if not present
                if not seg.get("transition_cue"):
                    seg["transition_cue"] = f"Transition from previous segment (tone {previous_tone})"

            adjusted_segments.append(seg)
            previous_tone = seg.get("tone_level", 3)

        return adjusted_segments

    def _tone_level_to_enum(self, tone_level: int) -> SegmentTone:
        """Convert tone level (1-5) to SegmentTone enum."""
        if tone_level <= 1:
            return SegmentTone.ANALYTICAL
        elif tone_level == 2:
            return SegmentTone.INFORMATIVE
        elif tone_level == 3:
            return SegmentTone.CONVERSATIONAL
        elif tone_level == 4:
            return SegmentTone.EXCITED
        else:  # tone_level == 5
            return SegmentTone.DRAMATIC

    def _create_default_segments(
        self,
        status: EpisodeStatus,
        total_seconds: int,
        game_context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Create default segments following narrative flow if Claude analysis fails.
        
        Uses actual data from game_context to generate specific titles.
        """
        # Extract team names for specific titles
        game_data = {}
        if game_context:
            game_data = game_context.get("game") or (game_context.get("games", [{}])[0] if game_context.get("games") else {})
        
        home_team = game_data.get("home_team", {}).get("name", "Home Team") if game_data else "Home Team"
        away_team = game_data.get("away_team", {}).get("name", "Away Team") if game_data else "Away Team"
        
        if status == EpisodeStatus.PRE_MATCH:
            return [
                {
                    "topic": f"The {home_team} vs {away_team} Showdown: What's at Stake",
                    "priority": 80,
                    "suggested_duration_seconds": int(total_seconds * 0.15),
                    "key_facts": [],
                    "tone_level": 4,
                    "source_refs": ["game.home_team", "game.away_team", "game.competition"],
                    "transition_cue": "",
                },
                {
                    "topic": "Recent Form & Head-to-Head: The Story So Far",
                    "priority": 75,
                    "suggested_duration_seconds": int(total_seconds * 0.25),
                    "key_facts": [],
                    "tone_level": 2,
                    "source_refs": ["standings", "form"],
                    "transition_cue": "Now let's look at how these teams have been performing",
                },
                {
                    "topic": "Team News: Injuries, Suspensions & Probable Lineups",
                    "priority": 70,
                    "suggested_duration_seconds": int(total_seconds * 0.25),
                    "key_facts": [],
                    "tone_level": 3,
                    "source_refs": ["lineups", "injuries"],
                    "transition_cue": "Turning to team news and availability",
                },
                {
                    "topic": "Tactical Preview: Formations & Key Matchups",
                    "priority": 65,
                    "suggested_duration_seconds": int(total_seconds * 0.2),
                    "key_facts": [],
                    "tone_level": 2,
                    "source_refs": ["lineups.formation", "pre_game_stats"],
                    "transition_cue": "Let's break down the tactical battle",
                },
                {
                    "topic": "The Betting Angle: Odds & Predictions",
                    "priority": 60,
                    "suggested_duration_seconds": int(total_seconds * 0.1),
                    "key_facts": [],
                    "tone_level": 3,
                    "source_refs": ["betting"],
                    "transition_cue": "Finally, what do the bookmakers think?",
                },
            ]
        else:
            # Post-match: Extract specific data for titles
            final_score = game_data.get("final_score", {}) if game_data else {}
            home_score = final_score.get("home", 0) if final_score else 0
            away_score = final_score.get("away", 0) if final_score else 0
            
            # Try to get top performer name
            top_performer_name = "Key Player"
            if game_data:
                top_performers = game_data.get("top_performers", [])
                if top_performers and len(top_performers) > 0:
                    top_performer_name = top_performers[0].get("name", "Key Player")
            
            return [
                {
                    "topic": f"{home_team} {home_score}-{away_score} {away_team}: The Final Verdict",
                    "priority": 90,
                    "suggested_duration_seconds": int(total_seconds * 0.2),
                    "key_facts": [],
                    "tone_level": 5,
                    "source_refs": ["final_score", "winner"],
                    "transition_cue": "",
                },
                {
                    "topic": "The Decisive Moments: Goals, Cards & Game-Changing Events",
                    "priority": 85,
                    "suggested_duration_seconds": int(total_seconds * 0.3),
                    "key_facts": [],
                    "tone_level": 4,
                    "source_refs": ["events"],
                    "transition_cue": "Let's relive the key moments that shaped this match",
                },
                {
                    "topic": "By the Numbers: Possession, Shots & Statistical Dominance",
                    "priority": 75,
                    "suggested_duration_seconds": int(total_seconds * 0.25),
                    "key_facts": [],
                    "tone_level": 2,
                    "source_refs": ["statistics"],
                    "transition_cue": "Now let's analyze the numbers",
                },
                {
                    "topic": f"Man of the Match: {top_performer_name}'s Standout Performance",
                    "priority": 70,
                    "suggested_duration_seconds": int(total_seconds * 0.15),
                    "key_facts": [],
                    "tone_level": 3,
                    "source_refs": ["top_performers"],
                    "transition_cue": "Turning to individual performances",
                },
                {
                    "topic": "League Table Impact: How This Result Changes Everything",
                    "priority": 65,
                    "suggested_duration_seconds": int(total_seconds * 0.1),
                    "key_facts": [],
                    "tone_level": 2,
                    "source_refs": ["standings"],
                    "transition_cue": "Finally, what does this mean for the league?",
                },
            ]

    async def _generate_title(
        self,
        game_context: dict[str, Any],
        status: EpisodeStatus,
        prioritized_data: dict[str, Any],
    ) -> str:
        """
        Generate a catchy episode title.

        Args:
            game_context: Game context
            status: Episode status
            prioritized_data: Prioritized data from Claude

        Returns:
            Episode title string
        """
        game_data = game_context.get("game") or (game_context.get("games", [{}])[0] if game_context.get("games") else {})
        home_team = game_data.get("home_team", {}).get("name", "Home")
        away_team = game_data.get("away_team", {}).get("name", "Away")
        competition = game_data.get("competition", "")

        # Try to use explosive quotes or high-priority stories for title
        explosive_quotes = prioritized_data.get("explosive_quotes", [])
        priority_stories = prioritized_data.get("priority_stories", [])

        if priority_stories and priority_stories[0].get("score", 0) > 80:
            # Use high-priority story for title
            story = priority_stories[0].get("story", "")
            if story:
                return f"{home_team} vs {away_team}: {story}"

        if status == EpisodeStatus.PRE_MATCH:
            return f"{home_team} vs {away_team} - {competition} Preview"
        else:
            final_score = game_data.get("final_score", {})
            home_score = final_score.get("home", 0)
            away_score = final_score.get("away", 0)
            return f"{home_team} {home_score}-{away_score} {away_team} - {competition} Recap"

    def _calculate_priority_score(
        self,
        game_context: dict[str, Any],
        prioritized_data: dict[str, Any],
    ) -> float:
        """
        Calculate overall priority score for the episode.

        Args:
            game_context: Game context
            prioritized_data: Prioritized data

        Returns:
            Priority score (0-100)
        """
        priority_stories = prioritized_data.get("priority_stories", [])
        
        if not priority_stories:
            return 50.0  # Default medium priority

        # Average of top 3 story scores
        top_scores = [story.get("score", 50) for story in priority_stories[:3]]
        avg_score = sum(top_scores) / len(top_scores) if top_scores else 50.0

        # Boost for explosive quotes
        explosive_quotes = prioritized_data.get("explosive_quotes", [])
        if explosive_quotes:
            avg_score = min(100.0, avg_score + 10.0)

        return round(avg_score, 1)

    def generate_script_prompt(self, lineup: PodcastLineup, game_context: dict[str, Any]) -> str:
        """
        Generate a detailed script prompt from the lineup for ScriptGenerator.

        Args:
            lineup: PodcastLineup object
            game_context: Enriched game context

        Returns:
            Detailed prompt string for Claude ScriptGenerator with status-filtered data
        """
        # Filter game_context based on status to ensure only relevant data is used
        filtered_context = self._filter_context_by_status(game_context, lineup.status)
        
        segments_text = []
        total_time = 0

        for i, segment in enumerate(lineup.segments, 1):
            # Build data points with source references
            data_points_text = ""
            if segment.key_data_points:
                for point in segment.key_data_points:
                    data_points_text += f"  • {point}\n"
            else:
                data_points_text = "  • Use relevant data from context\n"

            # Add source references
            source_refs_text = ""
            if segment.source_data_refs:
                source_refs_text = f"- Source Data References (verify these exist in JSON): {', '.join(segment.source_data_refs)}\n"

            # Build transition section with detailed instructions
            transition_section = ""
            if i == 1:
                # First segment - opening instructions
                transition_section = "- Transition: This is the opening segment. Start with energy and hook the listener immediately.\n"
            elif segment.transition_cue:
                # Get previous segment info for context
                prev_segment = lineup.segments[i - 2] if i > 1 else None
                if prev_segment:
                    tone_shift = segment.tone_level - prev_segment.tone_level
                    tone_shift_desc = ""
                    if tone_shift > 0:
                        tone_shift_desc = f" (increasing energy by {tone_shift} level{'s' if tone_shift > 1 else ''})"
                    elif tone_shift < 0:
                        tone_shift_desc = f" (decreasing energy by {abs(tone_shift)} level{'s' if abs(tone_shift) > 1 else ''})"
                    else:
                        tone_shift_desc = " (maintaining similar energy)"
                    
                    transition_section = f"""- Transition from Previous Segment:
  • Previous Topic: {prev_segment.topic}
  • Previous Tone: {prev_segment.tone_level}/5 ({self._get_tone_description(prev_segment.tone_level)})
  • Current Tone: {segment.tone_level}/5 ({self._get_tone_description(segment.tone_level)}){tone_shift_desc}
  • Transition Instruction: {segment.transition_cue}
  • IMPORTANT: Create a smooth bridge that naturally flows from "{prev_segment.topic}" to "{segment.topic}". 
    Use connecting phrases, callbacks, or narrative threads to make the transition feel organic.
    If tone is changing, gradually shift the energy level - don't make abrupt jumps.
"""
            else:
                # No explicit transition cue, but still need to bridge
                prev_segment = lineup.segments[i - 2] if i > 1 else None
                if prev_segment:
                    transition_section = f"""- Transition from Previous Segment:
  • Previous Topic: {prev_segment.topic}
  • Create a natural bridge from the previous segment to this one
  • Maintain narrative flow and logical progression
"""

            segments_text.append(
                f"""
SEGMENT {i}: {segment.topic}
- Duration: {segment.allocated_time} seconds (~{segment.estimated_word_count} words)
- Tone Level: {segment.tone_level}/5 ({self._get_tone_description(segment.tone_level)})
- Key Data Points (ONLY use if present in JSON):
{data_points_text}{source_refs_text}{transition_section}"""
            )
            total_time += segment.allocated_time

        prompt = f"""Generate a podcast script following this EXACT structure and timing:

EPISODE TITLE: {lineup.episode_title}
STATUS: {lineup.status.value.upper()}
TOTAL DURATION: {lineup.total_duration_minutes} minutes ({total_time} seconds)

SEGMENT BREAKDOWN:
{''.join(segments_text)}

CRITICAL REQUIREMENTS - STRICT DATA GROUNDING:
1. ONLY use facts present in the GameContext JSON below
2. DO NOT invent, assume, or hallucinate any data points
3. If a data point is referenced but not in JSON, skip it and use alternative available data
4. For each fact you mention, verify it exists in the JSON first
5. Follow the segment structure EXACTLY - each segment must match its allocated time
6. Use the specified tone level for each segment (1=Cold/Analytical, 5=High Octane/Excited)
7. TRANSITION REQUIREMENTS - CRITICAL:
   - Read and follow the transition instructions for EACH segment carefully
   - Create smooth bridges between segments using the provided transition cues
   - If tone level is changing, gradually shift energy - don't make abrupt jumps
   - Use connecting phrases, callbacks, or narrative threads to link segments naturally
   - Example transition phrases: "Speaking of...", "But that's not all...", "Now let's shift focus to...", "Building on that..."
8. Ensure the total script duration matches {lineup.total_duration_minutes} minutes
9. Make it FUN and ENJOYABLE - listeners should be engaged throughout
10. Include [PAUSE:short/medium/long] markers for pacing, especially at segment transitions
11. DO NOT use asterisks (*word*) for emphasis

GAME CONTEXT (ONLY USE DATA FROM THIS JSON - {lineup.match_status} DATA ONLY):
{json.dumps(filtered_context, indent=2, default=str)}

STATUS-SPECIFIC DATA FILTERING:
- This is a {lineup.match_status} episode
- FORBIDDEN: Do NOT mention pre-game data (lineups, pre-game stats, pre-game news) if this is POST-MATCH
- FORBIDDEN: Do NOT mention post-game data (events, final score, post-game stats) if this is PRE-MATCH
- ONLY use data appropriate for {lineup.match_status} status

Remember: This is a {lineup.status.value} episode. Focus on the appropriate content type.
The priority score for this episode is {lineup.priority_score}/100 - ensure the script reflects this importance level.

Generate the complete script following the segment structure above, using ONLY data from the JSON."""

        return prompt

    def _get_tone_description(self, tone_level: int) -> str:
        """Get human-readable description of tone level."""
        descriptions = {
            1: "Cold/Analytical",
            2: "Informative",
            3: "Conversational",
            4: "Energetic",
            5: "High Octane/Excited",
        }
        return descriptions.get(tone_level, "Conversational")

    def _filter_context_by_status(
        self,
        game_context: dict[str, Any],
        status: EpisodeStatus,
    ) -> dict[str, Any]:
        """
        Filter game context to only include data appropriate for the episode status.

        PRE_MATCH: Remove post-game data (events, final_score, top_performers, etc.)
        POST_MATCH: Remove pre-game data (probable lineups, pre_game_stats, pre-game news, etc.)

        Args:
            game_context: Full game context
            status: Episode status

        Returns:
            Filtered context with only status-appropriate data
        """
        import copy
        filtered = copy.deepcopy(game_context)

        # Get game data
        game_data = filtered.get("game")
        if not game_data and filtered.get("games"):
            game_data = filtered["games"][0] if filtered["games"] else {}
        
        if status == EpisodeStatus.PRE_MATCH:
            # Remove post-match data
            if isinstance(game_data, dict):
                game_data.pop("final_score", None)
                game_data.pop("winner", None)
                game_data.pop("events", None)
                game_data.pop("statistics", None)  # Post-game stats
                game_data.pop("top_performers", None)
                game_data.pop("actual_play_time", None)
                game_data.pop("betting_result", None)
                game_data.pop("detailed_statistics", None)
                # Keep: lineups, pre_game_stats, form, betting (pre-game), standings, news (pre-game)
        else:
            # Remove pre-match data
            if isinstance(game_data, dict):
                game_data.pop("pre_game_stats", None)
                # Note: Keep lineups for post-match (actual lineups used)
                game_data.pop("lineups_status", None)
                # Keep: final_score, events, statistics, top_performers, standings (updated), news (post-game)

        # Filter games array if present
        if "games" in filtered and isinstance(filtered["games"], list):
            for game in filtered["games"]:
                if isinstance(game, dict):
                    if status == EpisodeStatus.PRE_MATCH:
                        game.pop("final_score", None)
                        game.pop("winner", None)
                        game.pop("events", None)
                        game.pop("statistics", None)
                        game.pop("top_performers", None)
                    else:
                        game.pop("pre_game_stats", None)
                        game.pop("lineups_status", None)

        return filtered
