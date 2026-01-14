"""TalkingPoint models for content intelligence extraction."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class StoryType(str, Enum):
    """Categories of narrative talking points."""

    INJURY = "injury"
    SUSPENSION = "suspension"
    RETURN = "return"
    FORM_STREAK = "form_streak"
    BETTING_INSIGHT = "betting_insight"
    PREDICTION = "prediction"
    DEBUT = "debut"
    KEY_ABSENCE = "key_absence"
    MILESTONE = "milestone"
    H2H = "h2h"


class Priority(int, Enum):
    """Priority levels for talking points."""

    CRITICAL = 1  # Must include (star player injury, 5+ game streak)
    HIGH = 2      # Should include if space
    MEDIUM = 3    # Include for depth
    LOW = 4       # Optional filler


class TalkingPoint(BaseModel):
    """
    A structured narrative element extracted from game data.

    Represents a single "story" that can be woven into the podcast script.
    The narrative field contains pre-composed text ready for Claude to incorporate.
    """

    # Identity
    id: str = Field(description="Unique identifier for this talking point")
    story_type: StoryType
    priority: Priority = Priority.MEDIUM

    # Content
    headline: str = Field(description="Short summary, e.g. 'Salah out with hamstring'")
    narrative: str = Field(description="Pre-composed natural language for Claude to use")

    # Context
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    player_id: Optional[int] = None
    player_name: Optional[str] = None
    competition: Optional[str] = None
    game_id: Optional[int] = None

    # Supporting data for Claude context
    data_points: dict[str, Any] = Field(default_factory=dict)

    # Attribution
    source: Optional[str] = None  # e.g., "Opta", "Community", "365Scores"
    provider_name: Optional[str] = None  # For expert insights

    # Scoring
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)

    # Metadata
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"extra": "ignore"}


class GameIntelligence(BaseModel):
    """Aggregated intelligence for a single game."""

    game_id: int
    home_team: str
    away_team: str
    competition: Optional[str] = None

    # All talking points for this game
    talking_points: list[TalkingPoint] = Field(default_factory=list)

    # Categorized for easy access
    injury_points: list[TalkingPoint] = Field(default_factory=list)
    form_points: list[TalkingPoint] = Field(default_factory=list)
    betting_points: list[TalkingPoint] = Field(default_factory=list)
    lineup_points: list[TalkingPoint] = Field(default_factory=list)

    # Summary
    total_points: int = 0
    high_priority_count: int = 0

    def add_point(self, point: TalkingPoint) -> None:
        """Add a talking point and categorize it."""
        self.talking_points.append(point)
        self.total_points += 1

        if point.priority.value <= Priority.HIGH.value:
            self.high_priority_count += 1

        # Categorize
        if point.story_type in (StoryType.INJURY, StoryType.SUSPENSION, StoryType.RETURN):
            self.injury_points.append(point)
        elif point.story_type == StoryType.FORM_STREAK:
            self.form_points.append(point)
        elif point.story_type in (StoryType.BETTING_INSIGHT, StoryType.PREDICTION):
            self.betting_points.append(point)
        elif point.story_type in (StoryType.DEBUT, StoryType.KEY_ABSENCE):
            self.lineup_points.append(point)


class IntelligenceContext(BaseModel):
    """Complete intelligence context passed to script generator."""

    mode: str  # daily_recap, game_spotlight_pregame, etc.
    games: list[GameIntelligence] = Field(default_factory=list)

    # Top stories across all games (prioritized)
    top_stories: list[TalkingPoint] = Field(default_factory=list)

    # Original enriched data (for Claude context)
    raw_context: dict[str, Any] = Field(default_factory=dict)

    def get_all_points(self) -> list[TalkingPoint]:
        """Get all talking points across all games."""
        points = []
        for game in self.games:
            points.extend(game.talking_points)
        return points

    def format_for_prompt(self) -> str:
        """Format talking points for inclusion in Claude prompt."""
        if not self.top_stories:
            return ""

        lines = ["KEY TALKING POINTS (incorporate these naturally into the script):"]
        lines.append("")

        for i, point in enumerate(self.top_stories, 1):
            type_label = point.story_type.value.upper().replace("_", " ")
            lines.append(f"{i}. [{type_label}] {point.headline}")
            lines.append(f'   Suggested: "{point.narrative}"')

            if point.provider_name:
                lines.append(f"   Source: {point.provider_name}")

            if point.data_points:
                data_str = ", ".join(f"{k}={v}" for k, v in list(point.data_points.items())[:3])
                lines.append(f"   Data: {data_str}")

            lines.append("")

        lines.append("IMPORTANT: Reference these specific facts. Avoid generic statements.")
        lines.append("")

        return "\n".join(lines)
