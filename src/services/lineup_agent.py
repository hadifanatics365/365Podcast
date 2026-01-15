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


class BettingCornerConfig(BaseModel):
    """Configuration for 'The Final Ticket' betting segment."""

    bookmaker_name: str = Field(default="", description="Name of the bookmaker to promote")
    target_market: str = Field(default="Full-time Result", description="Betting market (e.g., 'Full-time Result', 'Over/Under 2.5')")
    featured_odds: dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary of odds rates (current, original, moving rates)",
    )
    prediction_context: str = Field(
        default="",
        description="Short summary of data point used for prediction",
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
    betting_corner_config: Optional[BettingCornerConfig] = Field(
        default=None,
        description="Configuration for 'The Final Ticket' sponsored betting segment",
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
            
            # Check if this is "The Final Ticket" segment
            is_final_ticket = segment.topic == "The Final Ticket" or "Final Ticket" in segment.topic
            
            if is_final_ticket:
                lines.append(f"🎬 SEGMENT {i}: {segment.topic}")
                lines.append(f"   ⭐ SPONSORED SEGMENT: THE FINAL TICKET ⭐")
                if self.betting_corner_config:
                    lines.append(f"   📊 Bookmaker: {self.betting_corner_config.bookmaker_name}")
                    lines.append(f"   🎯 Market: {self.betting_corner_config.target_market}")
                    if self.betting_corner_config.featured_odds:
                        lines.append(f"   💰 Featured Odds:")
                        for key, value in self.betting_corner_config.featured_odds.items():
                            lines.append(f"      • {key}: {value}")
                    if self.betting_corner_config.prediction_context:
                        lines.append(f"   📈 Prediction Context: {self.betting_corner_config.prediction_context}")
            else:
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
            producer_note = self._generate_producer_note(segment, i, is_final_ticket)
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
    def _generate_producer_note(segment: PodcastSegment, segment_num: int, is_final_ticket: bool = False) -> str:
        """
        Generate producer note emphasizing conversational flow and tactical debates.
        
        Enhanced to focus on "Pub Vibe" - friendly dialogue, emotional reactions, and tactical discussions.
        """
        if is_final_ticket:
            return (
                "SPONSORED SEGMENT - THE FINAL TICKET: Create a friendly panel debate in 'pub vibe' style. "
                "One host makes a 'safe' pick based on data (e.g., H2H dominance, form trends), another host picks a 'wildcard' or 'upset' based on trends or patterns. "
                "Explicitly mention the bookmaker name and specific market (e.g., 'Full-time Result', 'Over/Under 2.5'). "
                "Detail the current, original, and moving odds rates from the featured_odds data. "
                "Each prediction MUST be supported by at least one specific data point from GameContext (e.g., 'I'm going with Over 2.5 because the last 3 derbies averaged 4 goals'). "
                "Use inviting, conversational tone ('What's your ticket looking like?') - keep it casual, not a hard sell. "
                "This is a panel discussion, not an advertisement."
            )
        
        if not segment.key_data_points:
            return "Keep it casual and conversational - discuss the feeling, maintain the 'pub vibe' between Moderator and Fan."
        
        # Pick the most impactful data point
        key_point = segment.key_data_points[0] if segment.key_data_points else ""
        key_lower = key_point.lower()
        
        # Generate context-specific note with conversational emphasis
        if "lineup" in key_lower or "formation" in key_lower or "xi" in key_lower or "starting" in key_lower:
            return (
                "TACTICAL DEBATE - Do NOT list the 11 players. Instead, have a friendly debate about the lineup choices. "
                "Focus on talking points: surprising inclusions, major absences, or the coach's tactical gamble. "
                "PRE-MATCH: 'Is this lineup too attacking for a big away game?' POST-MATCH: 'Did the starting XI choice cost them the game, or was it a masterstroke?' "
                "Keep it conversational - react to the lineup, discuss the feeling, maintain the pub vibe."
            )
        elif "score" in key_lower or "goal" in key_lower:
            return (
                "POST-MATCH EMOTION: React to the result emotionally. If the Fan's team won, he should sound uplifted and proud. "
                "If they lost, he should be subtly deflated or frustrated (never toxic). Discuss the specific score/goal moment. "
                "Keep it reflective and emotional - 'The Day After' feeling. Maintain synchronized mood between Moderator and Fan."
            )
        elif "injury" in key_lower or "suspension" in key_lower:
            return (
                "Discuss the impact in a friendly, conversational way. How does this affect the team's chances? "
                "The Fan should react with concern or relief depending on which team. Keep it casual - discuss the feeling, not just facts."
            )
        elif "odds" in key_lower or "betting" in key_lower:
            return (
                "Present the betting angle in a conversational, friendly way. Discuss what the odds tell us, not just state them. "
                "Keep it casual - 'What's your take on these odds?' Maintain the pub vibe."
            )
        elif "form" in key_lower or "standings" in key_lower or "h2h" in key_lower:
            return (
                "Discuss the context in a friendly dialogue style. The Fan should react to the form/standings with emotion. "
                "PRE-MATCH: High energy, butterflies, speculation. POST-MATCH: Reflective analysis. Keep it conversational - react to the data."
            )
        else:
            return (
                f"Friendly dialogue style: Discuss '{key_point}' in a conversational way. The Fan should react emotionally. "
                "The Moderator should ask for the Fan's take rather than just stating facts. Keep it casual - maintain the pub vibe."
            )


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
        
        Enhanced logic: Checks for scores/results and compares match date to current time.

        Args:
            game: Game object

        Returns:
            EpisodeStatus enum
        """
        # Primary check: If score exists and is valid, it's POST-MATCH
        if game.scrs and len(game.scrs) >= 2:
            # Check if scores are non-zero (ignore -1 values which indicate no score)
            valid_scores = [s for s in game.scrs if s >= 0]
            if valid_scores and any(score > 0 for score in valid_scores):
                return EpisodeStatus.POST_MATCH
            # Also check if winner is set (even if 0-0 draw, winner might be 0)
            if game.winner is not None and game.winner >= 0:
                return EpisodeStatus.POST_MATCH
        
        # Secondary check: Game status enum
        if GameStatus.is_finished(game.gt):
            return EpisodeStatus.POST_MATCH
        elif GameStatus.is_upcoming(game.gt):
            return EpisodeStatus.PRE_MATCH
        elif GameStatus.is_live(game.gt):
            # Live games treated as post-match for analysis
            return EpisodeStatus.POST_MATCH
        
        # Check for status codes that indicate finished games (99, 100, etc.)
        # Status 99 often means "finished" in some API versions
        if game.gt == 99 or (game.gt >= 90 and game.gt < 200):
            # If game has started or has any completion indicators, treat as POST-MATCH
            if game.is_started or (game.scrs and len(game.scrs) >= 2):
                return EpisodeStatus.POST_MATCH
        
        # Tertiary check: Compare match date to current time
        if game.stime:
            from datetime import datetime, timezone
            try:
                # Try ISO format first
                try:
                    match_time = datetime.fromisoformat(game.stime.replace("Z", "+00:00"))
                except ValueError:
                    # Try DD-MM-YYYY HH:MM format
                    try:
                        match_time = datetime.strptime(game.stime, "%d-%m-%Y %H:%M")
                        # Assume UTC if no timezone specified
                        match_time = match_time.replace(tzinfo=timezone.utc)
                    except ValueError:
                        # Try other common formats
                        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M"]:
                            try:
                                match_time = datetime.strptime(game.stime, fmt)
                                match_time = match_time.replace(tzinfo=timezone.utc)
                                break
                            except ValueError:
                                continue
                        else:
                            raise ValueError(f"Could not parse date: {game.stime}")
                
                current_time = datetime.now(timezone.utc)
                
                # If match time is in the past, likely POST-MATCH
                if match_time < current_time:
                    # Check if it's been more than 2 hours (enough time for a match to finish)
                    time_diff = current_time - match_time
                    if time_diff.total_seconds() > 7200:  # 2 hours
                        return EpisodeStatus.POST_MATCH
                    # Or if we have any indication of completion
                    if game.scrs or (game.winner is not None and game.winner >= 0):
                        return EpisodeStatus.POST_MATCH
            except (ValueError, AttributeError) as e:
                logger.debug(f"Could not parse match time '{game.stime}': {e}")
        
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
        # Extract game data - check for Game object first, then dict
        game_obj = None
        game_data = None
        
        # Priority 1: Check if game_context has a Game object directly (stored by DataEnricher)
        if "game" in game_context:
            if isinstance(game_context["game"], Game):
                game_obj = game_context["game"]
            else:
                game_data = game_context["game"]
        
        # Priority 2: Check games array for Game object
        if game_obj is None and "games" in game_context and game_context["games"]:
            first_item = game_context["games"][0]
            if isinstance(first_item, Game):
                game_obj = first_item
            else:
                game_data = first_item
        
        # Priority 3: Use game_data dict if we have it
        if game_obj is None and game_data is None:
            game_data = game_context.get("game_data") or game_context.get("game") or (game_context.get("games", [{}])[0] if game_context.get("games") else {})
        
        # Detect status from Game object if available
        if game_obj:
            status = self.detect_status(game_obj)
            logger.info(f"Detected game status from Game object: {status.value} (game_id={game_obj.gid}, gt={game_obj.gt})")
        elif game_data and isinstance(game_data, dict):
            # Construct Game object from dict data
            game_status = game_data.get("game_status") or game_data.get("gt", 0)
            game_id = game_data.get("game_id") or game_data.get("gid", 0)
            stime = game_data.get("start_time") or game_data.get("stime")
            scrs = game_data.get("scrs") or game_data.get("scores") or []
            winner = game_data.get("winner")
            is_started = game_data.get("is_started") or game_data.get("IsStarted", False)
            
            # Also check for final_score in dict format
            final_score = game_data.get("final_score")
            if final_score and isinstance(final_score, dict):
                # Convert final_score to scrs format
                home_score = final_score.get("home", 0)
                away_score = final_score.get("away", 0)
                if home_score is not None and away_score is not None:
                    scrs = [home_score, away_score]
            
            # Create minimal Game object with all available data
            minimal_game = Game(
                gid=game_id,
                gt=game_status,
                stime=stime,
                scrs=scrs if isinstance(scrs, list) else [],
                winner=winner,
                is_started=is_started,
            )
            status = self.detect_status(minimal_game)
            game_obj = minimal_game
            logger.info(f"Detected game status from dict data: {status.value} (game_id={game_id}, gt={game_status})")
        else:
            # Fallback: default to PRE_MATCH
            status = EpisodeStatus.PRE_MATCH
            logger.warning("Could not detect game status - defaulting to PRE_MATCH")

        logger.info(f"Creating lineup for {status.value} episode (duration: {total_duration_minutes} min)")

        # Use Claude to analyze and prioritize
        prioritized_data = await self._analyze_with_claude(game_context, status, total_duration_minutes)

        # Allocate time to segments (pass game_context for data-driven titles)
        segments = self._allocate_time(prioritized_data, total_duration_minutes, status, game_context)

        # Generate episode title
        episode_title = await self._generate_title(game_context, status, prioritized_data)

        # Calculate overall priority score
        priority_score = self._calculate_priority_score(game_context, prioritized_data)
        
        # Extract betting corner config
        betting_config = self._extract_betting_corner_config(game_context, status)

        return PodcastLineup(
            episode_title=episode_title,
            status=status,
            match_status=status.value.upper().replace("_", " "),
            total_duration_minutes=total_duration_minutes,
            segments=segments,
            priority_score=priority_score,
            betting_corner_config=betting_config,
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
            PRE-MATCH DATA CATEGORIES (MUST EXTRACT AND USE FROM GAME CONTEXT):
            - Game info: Teams, date, venue, competition
            - Recent form: Last 5 matches, win/loss streaks, goals scored/conceded
            - Head-to-head (H2H): Historical results, recent meetings, patterns
            - Trends: Form trends, goal trends, performance patterns
            - Probable lineups: Expected starting XI, key players, tactical setup
            - Betting oriented: Current odds, odds movements, market analysis
            - News: Pre-game news, team news, transfer news, injury updates
            - Stats: Pre-game statistics, team stats, player stats
            - Key players: Star players, danger men, players to watch
            - Standings position: League table position, points, goal difference
            - Odds movements: How odds have changed, market sentiment
            - Predictions results: Community predictions, expert picks
            
            FOR EACH SEGMENT: Extract SPECIFIC data points from these categories and list them in key_data_points.
            Reference the exact JSON paths where this data comes from in source_data_refs.
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
            POST-MATCH DATA CATEGORIES (MUST EXTRACT AND USE FROM GAME CONTEXT):
            - Match events: Goals, MOTM (Man of the Match), important subs, injuries during match, important events (red cards, VAR decisions)
            - Actual play time: Time played, stoppage time, key time periods
            - Post game stats: xG, possession, shots, passing accuracy, tackles, interceptions
            - Standings position: Updated league table position, points change, goal difference impact
            - After game news: Post-match quotes, manager comments, player interviews
            - Prediction results: Who predicted correctly, community prediction accuracy
            - Post match info: Final score, scorers, assists, cards, substitutions
            - Player ratings: Individual player performance ratings, top performers
            - Key players: Who stood out, who underperformed, impact players
            - Shots map: Shot locations, shot accuracy, goal locations
            - Box scores: Detailed match statistics (if available, especially for American sports)
            - Next matches mini recap: Upcoming fixtures for betting segment (especially for winning team)
            
            FOR EACH SEGMENT: Extract SPECIFIC data points from these categories and list them in key_data_points.
            Reference the exact JSON paths where this data comes from in source_data_refs.
            """

        system_prompt = """You are a professional sports producer for a podcast. Your job is to analyze game data and create a prioritized content plan.

🚨 CRITICAL REQUIREMENTS - STRICT DATA GROUNDING & ZERO-TOLERANCE FOR MISSING DATA:

1. ZERO-TOLERANCE FOR MISSING DATA (THE "NO-N/A" RULE):
   - If a data point (Lineups, Odds, Injuries, Stats) is missing or labeled "NOT_AVAILABLE", DO NOT create a segment for it
   - NO "Information Voids": Never mention that data is missing
   - If a segment exists in the rundown, it MUST be because there is rich, factual data to discuss
   - If there is no data, skip to the next topic naturally - do not create empty segments

2. STATUS-SPECIFIC DATA FILTERING (CRITICAL):
   - If status is PRE_MATCH: ONLY use pre-game data (form, H2H, probable lineups, injuries, pre-game odds, standings, pre-game news)
   - If status is POST_MATCH: ONLY use post-match data (events, final score, post-game stats, MOTM, standings update, post-match news)
   - FORBIDDEN: Do NOT mention pre-game data in post-match pods, and vice-versa
   - STRICT TIMELINE ALIGNMENT: Never treat a past game as a future event

3. ONLY use facts present in the provided GameContext JSON
4. DO NOT invent, assume, or hallucinate any data points
5. For each data point you use, reference the exact JSON key/path where it comes from
6. **CRITICAL: DATA EXTRACTION REQUIREMENT**
   - For EACH segment you create, you MUST extract SPECIFIC data points from the GameContext JSON
   - List these specific data points in the "key_data_points" field
   - Include the JSON path/keys in "source_data_refs" field
   - Example: If discussing form, extract actual match results like "Won last 3 matches: 2-1 vs Arsenal, 3-0 vs Chelsea, 1-0 vs Liverpool"
   - Example: If discussing standings, extract actual positions like "Man United: 3rd place, 45 points, +12 goal difference"
   - Example: If discussing odds, extract actual odds like "Home win: 2.10, Draw: 3.40, Away win: 3.20"
   - DO NOT create generic segments - each segment MUST reference specific, extractable data from the JSON

🎭 PERSONA CHEMISTRY & "THE PUB VIBE":

The Moderator (Host): She is a "Football Geek," not a news anchor. Her tone must be casual, inquisitive, and warm. She should lead the conversation by asking for the Fan's take rather than just stating facts.

The Fan (Guest): He speaks with the heart of someone in the stands. He is passionate but maintains "football proportion"—loving the game but keeping it respectful.

Shared Mood & Atmosphere:
- PRE-MATCH: High energy, butterflies, and speculation about the "vibe" on the ground
- POST-MATCH: Reflective and emotional. If the Fan's team lost, his tone should be subtly "deflated" or frustrated (never toxic). If they won, he should sound "uplifted" and proud.

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
3: Conversational (friendly, engaging) - DEFAULT for "Pub Vibe"
4: Energetic (excited, animated)
5: High Octane/Excited (maximum energy, dramatic)

TRANSITION RULES:
- Cannot jump more than 2 tone levels between consecutive segments
- If moving from Level 5 to Level 1, insert a bridge segment at Level 3
- Ensure smooth tonal transitions for natural listening experience

⚽ TACTICAL LINEUP UPGRADE:
- Do NOT instruct hosts to list the 11 players
- Focus on "Tactical Debate" - surprising inclusions, major absences, or the coach's tactical gamble
- PRE-MATCH: "Is this lineup too attacking for a big away game?"
- POST-MATCH: "Did the starting XI choice cost them the game, or was it a masterstroke?"

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
3. ZERO-TOLERANCE FOR MISSING DATA: If a data point is missing or "NOT_AVAILABLE", DO NOT create a segment for it. Skip to the next topic naturally.
4. Generate SPECIFIC, DATA-DRIVEN segment titles (use player names, specific moments, not generic titles)
5. For each data point, reference the JSON key/path (e.g., "game.home_team.name", "standings.home_team.position")
6. If data is missing, DO NOT create a segment - only create segments with rich, factual data
7. Assign tone_level (1-5) to each segment - default to 3 (Conversational) for "Pub Vibe"
8. Ensure tone transitions don't jump more than 2 levels
9. Create transition_cue for each segment (except first) - use natural, conversational phrases
10. For lineup segments: Focus on TACTICAL DEBATE, not listing players. Emphasize surprising inclusions, absences, or tactical gambles.

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
        # Get game data - could be Game object or dict
        game_obj_or_dict = game_context.get("game") or (game_context.get("games", [{}])[0] if game_context.get("games") else {})
        
        # Extract team names - handle both Game object and dict
        if isinstance(game_obj_or_dict, Game):
            home_team = game_obj_or_dict.home_team.name if game_obj_or_dict.home_team else "Home Team"
            away_team = game_obj_or_dict.away_team.name if game_obj_or_dict.away_team else "Away Team"
            game_data = {}  # Use empty dict for other data
        else:
            game_data = game_obj_or_dict if isinstance(game_obj_or_dict, dict) else {}
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
                        f"Competition: {game_data.get('competition', 'Unknown') if isinstance(game_data, dict) else 'Unknown'}",
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
            # Extract scores from Game object or dict
            if isinstance(game_obj_or_dict, Game):
                home_score = game_obj_or_dict.home_score if hasattr(game_obj_or_dict, 'home_score') else (game_obj_or_dict.scrs[0] if game_obj_or_dict.scrs and len(game_obj_or_dict.scrs) > 0 else 0)
                away_score = game_obj_or_dict.away_score if hasattr(game_obj_or_dict, 'away_score') else (game_obj_or_dict.scrs[1] if game_obj_or_dict.scrs and len(game_obj_or_dict.scrs) > 1 else 0)
            else:
                final_score = game_data.get("final_score", {}) if isinstance(game_data, dict) else {}
                home_score = final_score.get("home", 0) if isinstance(final_score, dict) else 0
                away_score = final_score.get("away", 0) if isinstance(final_score, dict) else 0
            
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

        # Reserve time for intro/outro and "The Final Ticket" segment
        intro_outro_time = 30  # 15s intro + 15s outro
        final_ticket_time = 30  # Reserve 30s for "The Final Ticket"
        available_time = total_seconds - intro_outro_time - final_ticket_time

        previous_tone_level = 4  # Start at energetic for intro (level 4)

        for i, seg_data in enumerate(segments_data):
            # ZERO-TOLERANCE FOR MISSING DATA: Skip segments with NOT_AVAILABLE data
            key_facts = seg_data.get("key_facts", [])
            has_available_data = self._has_available_data(key_facts, seg_data)
            
            if not has_available_data:
                logger.debug(f"Skipping segment '{seg_data.get('topic')}' - no available data")
                continue  # Skip this segment entirely
            
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

            # Filter out NOT_AVAILABLE from key_data_points
            filtered_key_facts = [
                fact for fact in key_facts 
                if "NOT_AVAILABLE" not in fact.upper() and "N/A" not in fact.upper()
            ]

            segment = PodcastSegment(
                topic=seg_data.get("topic", f"Segment {i+1}"),
                key_data_points=filtered_key_facts,
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

        # Insert intro at start
        allocated_segments.insert(0, intro_segment)
        
        # Create and insert "The Final Ticket" betting segment before outro
        # Use reserved time for final ticket
        final_ticket_segment = self._create_final_ticket_segment(
            status, game_context, final_ticket_time
        )
        
        if final_ticket_segment:
            # Ensure final ticket uses reserved time
            final_ticket_segment.allocated_time = final_ticket_time
            final_ticket_segment.estimated_word_count = int(final_ticket_time * self.WORDS_PER_SECOND)
            allocated_segments.append(final_ticket_segment)
        
        # Insert outro at end (uses reserved time)
        allocated_segments.append(outro_segment)

        # Verify total time matches - adjust outro if needed
        total_allocated = sum(seg.allocated_time for seg in allocated_segments)
        if total_allocated != total_seconds:
            # Adjust the last segment (outro) to match exactly
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
        # Get game data - could be Game object or dict
        game_obj_or_dict = game_context.get("game") or (game_context.get("games", [{}])[0] if game_context.get("games") else {})
        
        # Extract team names - handle both Game object and dict
        if isinstance(game_obj_or_dict, Game):
            home_team = game_obj_or_dict.home_team.name if game_obj_or_dict.home_team else "Home"
            away_team = game_obj_or_dict.away_team.name if game_obj_or_dict.away_team else "Away"
            competition = game_obj_or_dict.competition_display_name or ""
        else:
            game_data = game_obj_or_dict if isinstance(game_obj_or_dict, dict) else {}
            home_team = game_data.get("home_team", {}).get("name", "Home") if isinstance(game_data.get("home_team"), dict) else "Home"
            away_team = game_data.get("away_team", {}).get("name", "Away") if isinstance(game_data.get("away_team"), dict) else "Away"
            competition = game_data.get("competition", "") if isinstance(game_data, dict) else ""

        # Try to use explosive quotes or high-priority stories for title
        explosive_quotes = prioritized_data.get("explosive_quotes", []) if isinstance(prioritized_data, dict) else []
        priority_stories = prioritized_data.get("priority_stories", []) if isinstance(prioritized_data, dict) else []

        if priority_stories and len(priority_stories) > 0:
            first_story = priority_stories[0] if isinstance(priority_stories[0], dict) else {}
            if first_story.get("score", 0) > 80:
                # Use high-priority story for title
                story = first_story.get("story", "")
                if story:
                    return f"{home_team} vs {away_team}: {story}"

        if status == EpisodeStatus.PRE_MATCH:
            return f"{home_team} vs {away_team} - {competition} Preview"
        else:
            # Extract final score - handle both Game object and dict
            if isinstance(game_obj_or_dict, Game):
                home_score = game_obj_or_dict.home_score if hasattr(game_obj_or_dict, 'home_score') else (game_obj_or_dict.scrs[0] if game_obj_or_dict.scrs and len(game_obj_or_dict.scrs) > 0 else 0)
                away_score = game_obj_or_dict.away_score if hasattr(game_obj_or_dict, 'away_score') else (game_obj_or_dict.scrs[1] if game_obj_or_dict.scrs and len(game_obj_or_dict.scrs) > 1 else 0)
            else:
                game_data = game_obj_or_dict if isinstance(game_obj_or_dict, dict) else {}
                final_score = game_data.get("final_score", {}) if isinstance(game_data, dict) else {}
                home_score = final_score.get("home", 0) if isinstance(final_score, dict) else 0
                away_score = final_score.get("away", 0) if isinstance(final_score, dict) else 0
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
        priority_stories = prioritized_data.get("priority_stories", []) if isinstance(prioritized_data, dict) else []
        
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
            # Check if this is "The Final Ticket" segment
            is_final_ticket = segment.topic == "The Final Ticket" or "Final Ticket" in segment.topic
            
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

            # Add special instructions for "The Final Ticket" segment
            final_ticket_instructions = ""
            if is_final_ticket and lineup.betting_corner_config:
                # Determine prediction target based on status
                if lineup.status == EpisodeStatus.PRE_MATCH:
                    prediction_target = "the outcome of the current game"
                else:
                    prediction_target = "the outcome of the next match for the winning team (extract from 'next matches mini-recap' data if available)"
                
                final_ticket_instructions = f"""
- SPONSORED SEGMENT - THE FINAL TICKET (CRITICAL INSTRUCTIONS):
  • Bookmaker: {lineup.betting_corner_config.bookmaker_name}
  • Market: {lineup.betting_corner_config.target_market}
  • Featured Odds: {json.dumps(lineup.betting_corner_config.featured_odds, indent=2)}
  • Panel Prediction Challenge: Predict {prediction_target}
  • Panel Debate Requirements:
    - Create a back-and-forth panel debate in conversational style
    - One host makes a "safe" pick based on data (e.g., "{lineup.betting_corner_config.prediction_context}")
    - Another host picks a "wildcard" or "upset" based on trends or patterns
    - Each prediction MUST be supported by at least one specific data point from GameContext
    - Example: "I'm going with Over 2.5 because the last 3 derbies averaged 4 goals"
  • Scripting Requirements:
    - Explicitly mention the bookmaker name: "{lineup.betting_corner_config.bookmaker_name}"
    - Explicitly mention the specific market: "{lineup.betting_corner_config.target_market}"
    - Detail the current, original, and moving odds rates from featured_odds above
    - Use inviting, conversational tone: "What's your ticket looking like?" (NOT a hard sell)
    - Make it conversational and engaging - this is a panel discussion, not an advertisement
    - Keep the "pub vibe" - friendly debate, not a sales pitch"""

            segments_text.append(
                f"""
SEGMENT {i}: {segment.topic}
- Duration: {segment.allocated_time} seconds (~{segment.estimated_word_count} words)
- Tone Level: {segment.tone_level}/5 ({self._get_tone_description(segment.tone_level)})
- Key Data Points (ONLY use if present in JSON):
{data_points_text}{source_refs_text}{transition_section}{final_ticket_instructions}"""
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

        # Get game data - handle both Game object and dict
        game_obj_or_dict = filtered.get("game")
        if not game_obj_or_dict and filtered.get("games"):
            game_obj_or_dict = filtered["games"][0] if filtered["games"] else {}
        
        # Only filter dict data, not Game objects (Game objects are immutable)
        if isinstance(game_obj_or_dict, dict):
            if status == EpisodeStatus.PRE_MATCH:
                # Remove post-match data
                game_obj_or_dict.pop("final_score", None)
                game_obj_or_dict.pop("winner", None)
                game_obj_or_dict.pop("events", None)
                game_obj_or_dict.pop("statistics", None)  # Post-game stats
                game_obj_or_dict.pop("top_performers", None)
                game_obj_or_dict.pop("actual_play_time", None)
                game_obj_or_dict.pop("betting_result", None)
                game_obj_or_dict.pop("detailed_statistics", None)
                # Keep: lineups, pre_game_stats, form, betting (pre-game), standings, news (pre-game)
            else:
                # Remove pre-match data
                game_obj_or_dict.pop("pre_game_stats", None)
                # Note: Keep lineups for post-match (actual lineups used)
                game_obj_or_dict.pop("lineups_status", None)
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

    def _has_available_data(self, key_facts: list[str], seg_data: dict[str, Any]) -> bool:
        """
        Check if segment has available data (not NOT_AVAILABLE).
        
        Zero-tolerance rule: If all data is NOT_AVAILABLE, return False to skip segment.
        
        Args:
            key_facts: List of key facts for the segment
            seg_data: Full segment data dictionary
            
        Returns:
            True if segment has available data, False if all data is missing
        """
        # Check key facts
        if key_facts:
            available_facts = [
                fact for fact in key_facts 
                if "NOT_AVAILABLE" not in fact.upper() 
                and "N/A" not in fact.upper()
                and fact.strip()  # Not empty
            ]
            if available_facts:
                return True
        
        # Check source refs - if we have valid source references, we might have data
        source_refs = seg_data.get("source_refs", [])
        if source_refs:
            # If we have source refs, assume data might be available
            return True
        
        # If no key facts and no source refs, skip this segment
        return False

    def _create_final_ticket_segment(
        self,
        status: EpisodeStatus,
        game_context: Optional[dict[str, Any]],
        available_time: int,
    ) -> Optional[PodcastSegment]:
        """
        Create "The Final Ticket" betting segment (penultimate, before Outro).

        Args:
            status: Episode status (PRE_MATCH or POST_MATCH)
            game_context: Game context for extracting betting data
            available_time: Available time in seconds

        Returns:
            PodcastSegment for "The Final Ticket" or None if no betting data
        """
        if not game_context:
            return None

        # Extract betting data - try multiple paths
        game_obj_or_dict = game_context.get("game") or (game_context.get("games", [{}])[0] if game_context.get("games") else {})
        
        # Try different betting data paths
        betting_data = None
        
        # If game_obj_or_dict is a Game object, try to access main_odds attribute
        if isinstance(game_obj_or_dict, Game):
            if game_obj_or_dict.main_odds:
                betting_data = game_obj_or_dict.main_odds
        elif isinstance(game_obj_or_dict, dict):
            betting_data = (
                game_obj_or_dict.get("betting") 
                or game_obj_or_dict.get("main_odds") 
                or game_obj_or_dict.get("MainOdds")
                or game_obj_or_dict.get("mainOdds")
            )
        
        # Try context-level betting data
        if not betting_data:
            betting_data = game_context.get("betting") or game_context.get("relevant_odds")
        
        # If still no betting data, create segment anyway with placeholder data
        # This ensures "The Final Ticket" always appears
        if not betting_data:
            logger.warning("No betting data found for 'The Final Ticket' segment - creating with placeholder")
            # Create segment with placeholder betting info
            betting_data = {
                "type": 1,  # 1X2 market
                "options": [
                    {"name": "Home Win", "rate": "N/A", "trend": 0},
                    {"name": "Draw", "rate": "N/A", "trend": 0},
                    {"name": "Away Win", "rate": "N/A", "trend": 0},
                ]
            }

        # Allocate time (30-45 seconds for betting segment)
        duration = min(max(30, available_time // 8), 45)
        word_count = int(duration * self.WORDS_PER_SECOND)

        # Build key data points from betting data
        key_points = []
        source_refs = ["betting", "main_odds"]
        
        # Extract odds information
        if isinstance(betting_data, dict):
            if "options" in betting_data:
                for option in betting_data.get("options", [])[:3]:  # Top 3 options
                    name = option.get("name") or option.get("Name", "")
                    rate = option.get("rate") or option.get("Rate", "")
                    trend = option.get("trend") or option.get("Trend", 0)
                    if name and rate:
                        trend_text = "↑" if trend == 1 else "↓" if trend == -1 else "→"
                        key_points.append(f"{name}: {rate} {trend_text}")
            
            # Add market type
            market_type = betting_data.get("type") or betting_data.get("Type", "")
            if market_type:
                if market_type == 1 or market_type == "1X2":
                    key_points.append("Market: Full-time Result (1X2)")
                elif market_type == 2 or "over" in str(market_type).lower():
                    over_under = betting_data.get("overunder") or betting_data.get("P", "")
                    key_points.append(f"Market: Over/Under {over_under or '2.5'}")
        
        # Add prediction context based on status
        if status == EpisodeStatus.PRE_MATCH:
            key_points.append("Panel Prediction Challenge: Predict the outcome of the current game")
        else:
            # POST-MATCH: Look ahead to next match for winning team
            key_points.append("Panel Prediction Challenge: Predict the outcome of the next match for the winning team (extract from 'next matches mini-recap' data)")

        return PodcastSegment(
            topic="The Final Ticket",
            key_data_points=key_points,
            tone_level=3,  # Conversational for betting discussion
            tone=SegmentTone.CONVERSATIONAL,
            allocated_time=duration,
            estimated_word_count=word_count,
            source_data_refs=source_refs,
            transition_cue="Now let's talk about where the smart money is going...",
        )

    def _extract_betting_corner_config(
        self,
        game_context: dict[str, Any],
        status: EpisodeStatus,
    ) -> Optional[BettingCornerConfig]:
        """
        Extract betting corner configuration from game context.

        Args:
            game_context: Game context
            status: Episode status

        Returns:
            BettingCornerConfig or None if no betting data
        """
        game_obj_or_dict = game_context.get("game") or (game_context.get("games", [{}])[0] if game_context.get("games") else {})
        
        # Try different betting data paths
        betting_data = None
        
        # If game_obj_or_dict is a Game object, try to access main_odds attribute
        if isinstance(game_obj_or_dict, Game):
            if game_obj_or_dict.main_odds:
                betting_data = game_obj_or_dict.main_odds
        elif isinstance(game_obj_or_dict, dict):
            betting_data = (
                game_obj_or_dict.get("betting") 
                or game_obj_or_dict.get("main_odds") 
                or game_obj_or_dict.get("MainOdds")
                or game_obj_or_dict.get("mainOdds")
            )
        
        # Try context-level betting data
        if not betting_data:
            betting_data = game_context.get("betting") or game_context.get("relevant_odds")
        
        # If no betting data, create default config
        if not betting_data:
            logger.warning("No betting data found - creating default BettingCornerConfig")
            betting_data = {
                "type": 1,
                "options": [
                    {"name": "Home Win", "rate": "N/A", "trend": 0},
                    {"name": "Draw", "rate": "N/A", "trend": 0},
                    {"name": "Away Win", "rate": "N/A", "trend": 0},
                ]
            }

        # Extract bookmaker name (default if not available)
        bookmaker_name = "365Scores"  # Default bookmaker
        if isinstance(betting_data, dict):
            bookmaker_name = betting_data.get("bookmaker") or betting_data.get("Bookmaker", bookmaker_name)
        
        logger.info(f"[STEP 6] 'The Final Ticket' segment - Bookmaker: {bookmaker_name}")

        # Determine target market (explicitly named)
        market_type = betting_data.get("type") or betting_data.get("Type", "")
        if market_type == 1 or market_type == "1X2" or str(market_type) == "1":
            target_market = "Full-time Result"
        elif market_type == 2 or "over" in str(market_type).lower():
            over_under = betting_data.get("overunder") or betting_data.get("P", "2.5")
            target_market = f"Over/Under {over_under}"
        else:
            target_market = "Full-time Result"  # Default
        
        logger.info(f"[STEP 6] 'The Final Ticket' segment - Market: {target_market}")

        # Extract featured odds
        featured_odds = {}
        if isinstance(betting_data, dict) and "options" in betting_data:
            for option in betting_data.get("options", [])[:3]:
                name = option.get("name") or option.get("Name", "")
                rate = option.get("rate") or option.get("Rate", "")
                trend = option.get("trend") or option.get("Trend", 0)
                original_rate = option.get("original_rate") or option.get("OriginalRate", rate)
                
                if name and rate:
                    featured_odds[name] = {
                        "current": rate,
                        "original": original_rate,
                        "trend": "↑" if trend == 1 else "↓" if trend == -1 else "→",
                    }

        # Build prediction context
        prediction_context = ""
        if status == EpisodeStatus.PRE_MATCH:
            # Use H2H, form, or standings data
            if isinstance(game_obj_or_dict, dict):
                h2h = game_obj_or_dict.get("head_to_head") or game_context.get("head_to_head")
                form = game_obj_or_dict.get("form") or game_context.get("form")
            else:
                h2h = game_context.get("head_to_head")
                form = game_context.get("form")
            if h2h:
                prediction_context = "Based on head-to-head records and recent form"
            elif form:
                prediction_context = "Based on recent team form and league standings"
            else:
                prediction_context = "Based on available match data"
        else:
            # POST-MATCH: Look ahead to next match for winning team
            if isinstance(game_obj_or_dict, Game):
                winner = game_obj_or_dict.winner
            elif isinstance(game_obj_or_dict, dict):
                winner = game_obj_or_dict.get("winner") or game_obj_or_dict.get("Winner")
            else:
                winner = None
            
            # POST-MATCH: Search for next match data for winning team
            # Try multiple paths to find next match information
            next_matches = (
                game_context.get("next_matches") 
                or game_context.get("upcoming_fixtures")
                or game_context.get("next_games")
                or game_context.get("future_matches")
            )
            
            # Also check if game object has next match info
            if isinstance(game_obj_or_dict, Game):
                # Check if Game object has related matches or next match data
                next_match_data = None
            elif isinstance(game_obj_or_dict, dict):
                next_match_data = (
                    game_obj_or_dict.get("next_match")
                    or game_obj_or_dict.get("nextMatch")
                    or game_obj_or_dict.get("upcoming_match")
                )
            else:
                next_match_data = None
            
            # Determine winning team ID for searching
            winning_team_id = None
            if isinstance(game_obj_or_dict, Game):
                if winner == 0:  # Home team won
                    winning_team_id = game_obj_or_dict.home_team.id if game_obj_or_dict.home_team else None
                elif winner == 1:  # Away team won
                    winning_team_id = game_obj_or_dict.away_team.id if game_obj_or_dict.away_team else None
            elif isinstance(game_obj_or_dict, dict):
                if winner == 0:
                    home_team = game_obj_or_dict.get("home_team") or game_obj_or_dict.get("HomeTeam")
                    winning_team_id = home_team.get("id") if isinstance(home_team, dict) else None
                elif winner == 1:
                    away_team = game_obj_or_dict.get("away_team") or game_obj_or_dict.get("AwayTeam")
                    winning_team_id = away_team.get("id") if isinstance(away_team, dict) else None
            
            # Build prediction context based on available data
            if winner is not None and winner >= 0:
                if next_matches or next_match_data:
                    prediction_context = "Based on match result and next match preview for the winning team (from next matches mini-recap)"
                else:
                    prediction_context = "Based on match result and upcoming fixture analysis for the winning team"
            else:
                prediction_context = "Based on match performance and next match preview"

        betting_config = BettingCornerConfig(
            bookmaker_name=bookmaker_name,
            target_market=target_market,
            featured_odds=featured_odds,
            prediction_context=prediction_context,
        )
        
        logger.info(
            f"[STEP 6] ✓ 'The Final Ticket' betting config created: "
            f"Bookmaker={bookmaker_name}, Market={target_market}, "
            f"Odds={len(featured_odds)} options"
        )
        
        return betting_config