"""Game data models mapped from iOS SCModel/SCModelData/Game.swift."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class Competitor(BaseModel):
    """Team/competitor model."""

    id: int = Field(alias="ID")
    name: str = Field(default="", alias="Name")
    short_name: str = Field(default="", alias="SName")
    symbolic_name: Optional[str] = Field(default=None, alias="SymbolicName")
    main_color: Optional[str] = Field(default=None, alias="Color")
    img_version: Optional[int] = Field(default=None, alias="ImgVer")
    country_id: Optional[int] = Field(default=None, alias="CoID")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class Event(BaseModel):
    """Game event (goal, card, substitution, etc.)."""

    gt: Optional[int] = Field(default=None, alias="GT")  # Game time
    gtd: Optional[str] = Field(default=None, alias="GTD")  # Game time display
    player: Optional[str] = Field(default=None, alias="Player")
    player_id: Optional[int] = Field(default=None, alias="PID")
    type: Optional[int] = Field(default=None, alias="Type")
    stype: Optional[int] = Field(default=None, alias="SType")  # Sub-type
    num: Optional[int] = Field(default=None, alias="Num")  # Competitor number (0 or 1)
    comp: Optional[int] = Field(default=None, alias="Comp")
    reason: Optional[str] = Field(default=None, alias="Reason")
    description: Optional[str] = Field(default=None, alias="Description")
    extra_player: Optional[str] = Field(default=None, alias="ExtraPlayer")  # Assist, sub in

    model_config = {"populate_by_name": True, "extra": "ignore"}


class Statistic(BaseModel):
    """Game statistic (possession, shots, etc.)."""

    type: Optional[int] = Field(default=None, alias="Type")
    name: Optional[str] = Field(default=None, alias="Name")
    vals: list[str] = Field(default_factory=list, alias="Vals")
    vals_pct: list[float] = Field(default_factory=list, alias="ValsPct")
    is_bold: bool = Field(default=False, alias="IsBold")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class Player(BaseModel):
    """Player in a lineup."""

    pid: int = Field(alias="PID")
    name: str = Field(default="", alias="Name")
    position: Optional[int] = Field(default=None, alias="Pos")
    position_name: Optional[str] = Field(default=None, alias="PosName")
    rating: Optional[float] = Field(default=None, alias="Rating")
    shirt_number: Optional[int] = Field(default=None, alias="SN")
    is_captain: bool = Field(default=False, alias="IsCaptain")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class LineUp(BaseModel):
    """Team lineup."""

    players: list[Player] = Field(default_factory=list, alias="Players")
    formation: Optional[str] = Field(default=None, alias="Formation")
    comp_num: Optional[int] = Field(default=None, alias="CompNum")  # 0 = home, 1 = away

    model_config = {"populate_by_name": True, "extra": "ignore"}


class BetLineOption(BaseModel):
    """Individual betting option."""

    num: int = Field(alias="Num")
    rate: Optional[str] = Field(default=None, alias="Rate")
    name: Optional[str] = Field(default=None, alias="Name")
    won: bool = Field(default=False, alias="Won")
    trend: Optional[int] = Field(default=None, alias="Trend")  # 1=up, -1=down, 0=stable

    model_config = {"populate_by_name": True, "extra": "ignore"}


class BetLine(BaseModel):
    """Betting line with options."""

    line_id: int = Field(alias="ID")
    type: int = Field(alias="Type")
    options: list[BetLineOption] = Field(default_factory=list, alias="Options")
    overunder: Optional[str] = Field(default=None, alias="P")  # Over/under line
    link: Optional[str] = Field(default=None, alias="Link")
    bookmaker_id: Optional[int] = Field(default=None, alias="BKID")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class Venue(BaseModel):
    """Match venue."""

    id: Optional[int] = Field(default=None, alias="ID")
    name: Optional[str] = Field(default=None, alias="Name")
    city: Optional[str] = Field(default=None, alias="City")
    country: Optional[str] = Field(default=None, alias="Country")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class ActualPlayTime(BaseModel):
    """Actual play time information."""

    first_half: Optional[int] = Field(default=None, alias="FirstHalf")
    second_half: Optional[int] = Field(default=None, alias="SecondHalf")
    extra_time: Optional[int] = Field(default=None, alias="ExtraTime")
    total: Optional[int] = Field(default=None, alias="Total")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class TopPerformer(BaseModel):
    """Top performer data (MOTM, etc.)."""

    player_id: Optional[int] = Field(default=None, alias="PID")
    player_name: Optional[str] = Field(default=None, alias="Name")
    rating: Optional[float] = Field(default=None, alias="Rating")
    comp_num: Optional[int] = Field(default=None, alias="CompNum")
    stats: Optional[dict[str, Any]] = Field(default=None, alias="Stats")

    model_config = {"populate_by_name": True, "extra": "ignore"}


class Game(BaseModel):
    """
    Comprehensive Game model mapped from iOS SCModel/SCModelData/Game.swift.

    This model includes 50+ fields relevant for podcast generation,
    covering game status, scores, events, statistics, lineups, and betting data.
    """

    # Core identifiers
    gid: int = Field(alias="ID")
    name: Optional[str] = Field(default=None, alias="Name")
    sport_type_id: int = Field(default=1, alias="SID")
    competition_id: Optional[int] = Field(default=None, alias="Comp")

    # Status and timing
    gt: int = Field(default=0, alias="GT")  # Game status (see GameStatus enum)
    gtd: Optional[str] = Field(default=None, alias="GTD")  # Game time display
    stime: Optional[str] = Field(default=None, alias="STime")  # Start time ISO
    is_started: bool = Field(default=False, alias="IsStarted")
    is_active: bool = Field(default=False, alias="Active")

    # Competition info
    competition_display_name: Optional[str] = Field(default=None, alias="CompetitionDisplayName")
    round_name: Optional[str] = Field(default=None, alias="RoundName")
    stage: Optional[int] = Field(default=None, alias="Stage")
    season: Optional[int] = Field(default=None, alias="Season")

    # Competitors (teams)
    comps: list[Competitor] = Field(default_factory=list, alias="Comps")

    # Scores
    scrs: list[int] = Field(default_factory=list, alias="Scrs")
    extra_scores: list[dict[str, Any]] = Field(default_factory=list, alias="ExtraScores")
    aggregated_scores: list[int] = Field(default_factory=list, alias="AggregatedScore")
    penalties_score: list[int] = Field(default_factory=list, alias="PenaltiesScore")
    winner: Optional[int] = Field(default=None, alias="Winner")  # 0=draw, 1=home, 2=away

    # Events (goals, cards, subs)
    events: list[Event] = Field(default_factory=list, alias="Events")

    # Statistics
    statistics: list[Statistic] = Field(default_factory=list, alias="Statistics")
    pre_game_statistics: list[Statistic] = Field(default_factory=list, alias="PreGameStatistics")
    has_statistics: bool = Field(default=False, alias="HasStatistics")

    # Lineups
    lineups: list[LineUp] = Field(default_factory=list, alias="Lineups")
    has_lineups: bool = Field(default=False, alias="HasLineups")
    lineups_status_text: Optional[str] = Field(default=None, alias="LineupsStatusText")

    # Betting
    main_odds: Optional[BetLine] = Field(default=None, alias="MainOdds")
    live_odds: Optional[dict[str, Any]] = Field(default=None, alias="LiveOdds")
    best_odds: Optional[dict[str, Any]] = Field(default=None, alias="BestOdds")
    has_bets: bool = Field(default=False, alias="HasBets")
    has_player_bets: bool = Field(default=False, alias="HasPlayerBets")

    # Top performers
    top_performers_data: Optional[list[TopPerformer]] = Field(default=None, alias="TopPerformers")
    has_top_performers: bool = Field(default=False, alias="HasTopPerformers")

    # Additional context
    venue: Optional[Venue] = Field(default=None, alias="Venue")
    actual_play_time: Optional[ActualPlayTime] = Field(default=None, alias="ActualPlayTime")
    added_time: int = Field(default=0, alias="AddedTime")
    attendance: Optional[int] = Field(default=None, alias="Attendance")

    # News and content
    news_data: Optional[dict[str, Any]] = Field(default=None, alias="News")
    has_news: bool = Field(default=False, alias="HasNews")

    # Trends and insights
    has_team_trends: bool = Field(default=False, alias="HasTrends")
    promoted_trends: Optional[list[dict[str, Any]]] = Field(default=None, alias="PromotedTrends")
    insight_data: Optional[list[dict[str, Any]]] = Field(default=None, alias="PromotedInsights")

    # Media
    has_video: bool = Field(default=False, alias="HasVideo")
    has_play_by_play: bool = Field(default=False, alias="HasPlayByPlay")
    has_shot_chart: bool = Field(default=False, alias="HasShotChart")

    # Last matches (for form)
    last_matches: Optional[list[dict[str, Any]]] = Field(default=None, alias="LastMatches")

    model_config = {"populate_by_name": True, "extra": "ignore"}

    @property
    def home_team(self) -> Optional[Competitor]:
        """Get home team (first competitor)."""
        return self.comps[0] if self.comps else None

    @property
    def away_team(self) -> Optional[Competitor]:
        """Get away team (second competitor)."""
        return self.comps[1] if len(self.comps) > 1 else None

    @property
    def home_score(self) -> int:
        """Get home team score."""
        return self.scrs[0] if self.scrs else 0

    @property
    def away_score(self) -> int:
        """Get away team score."""
        return self.scrs[1] if len(self.scrs) > 1 else 0

    @property
    def start_datetime(self) -> Optional[datetime]:
        """Parse start time to datetime."""
        if self.stime:
            try:
                return datetime.fromisoformat(self.stime.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None


class ScoresData(BaseModel):
    """Container for scores API response."""

    games: list[Game] = Field(default_factory=list, alias="Games")
    request_update_id: Optional[int] = Field(default=None, alias="RequestUpdateID")
    last_update_id: Optional[int] = Field(default=None, alias="LastUpdateID")
    updates_frequency: Optional[int] = Field(default=None, alias="UpdatesFrequency")

    model_config = {"populate_by_name": True, "extra": "ignore"}
