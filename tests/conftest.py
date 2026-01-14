"""Pytest fixtures for podcast generation service tests."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import Settings
from src.models import (
    BetLine,
    BetLineOption,
    Competitor,
    Event,
    Game,
    LineUp,
    Player,
    Statistic,
)


@pytest.fixture
def settings() -> Settings:
    """Test settings with mock API keys."""
    return Settings(
        anthropic_api_key="test-anthropic-key",
        elevenlabs_api_key="test-elevenlabs-key",
        storage_type="local",
        local_storage_path="/tmp/test-podcasts",
        debug=True,
    )


@pytest.fixture
def sample_competitor_home() -> Competitor:
    """Sample home team competitor."""
    return Competitor(
        id=101,
        name="Manchester United",
        short_name="MUN",
        symbolic_name="manchester-united",
        main_color="#DA291C",
    )


@pytest.fixture
def sample_competitor_away() -> Competitor:
    """Sample away team competitor."""
    return Competitor(
        id=102,
        name="Liverpool FC",
        short_name="LIV",
        symbolic_name="liverpool",
        main_color="#C8102E",
    )


@pytest.fixture
def sample_event_goal() -> Event:
    """Sample goal event."""
    return Event(
        gt=23,
        gtd="23'",
        player="Marcus Rashford",
        player_id=1001,
        type=1,  # Goal
        num=0,  # Home team
        extra_player="Bruno Fernandes",  # Assist
    )


@pytest.fixture
def sample_statistic() -> Statistic:
    """Sample match statistic."""
    return Statistic(
        type=1,
        name="Possession",
        vals=["55%", "45%"],
        vals_pct=[55.0, 45.0],
        is_bold=True,
    )


@pytest.fixture
def sample_lineup() -> LineUp:
    """Sample team lineup."""
    return LineUp(
        formation="4-3-3",
        comp_num=0,  # Home team
        players=[
            Player(pid=1, name="David de Gea", position=1, position_name="GK", rating=7.2),
            Player(pid=2, name="Luke Shaw", position=2, position_name="LB", rating=7.0),
            Player(pid=3, name="Harry Maguire", position=3, position_name="CB", rating=6.8, is_captain=True),
        ],
    )


@pytest.fixture
def sample_bet_line() -> BetLine:
    """Sample betting line."""
    return BetLine(
        line_id=1,
        type=1,  # 1X2
        options=[
            BetLineOption(num=1, name="1", rate="2.10", trend=1),
            BetLineOption(num=2, name="X", rate="3.50", trend=0),
            BetLineOption(num=3, name="2", rate="3.20", trend=-1),
        ],
    )


@pytest.fixture
def sample_game_pregame(
    sample_competitor_home: Competitor,
    sample_competitor_away: Competitor,
    sample_lineup: LineUp,
    sample_bet_line: BetLine,
) -> Game:
    """Sample pre-game (not started) game."""
    return Game(
        gid=12345,
        name="Manchester United vs Liverpool",
        sport_type_id=1,  # Football
        competition_id=8,
        competition_display_name="Premier League",
        round_name="Matchday 15",
        gt=0,  # DIDNT_START
        gtd="",
        stime="2024-01-20T15:00:00Z",
        is_started=False,
        comps=[sample_competitor_home, sample_competitor_away],
        scrs=[],
        lineups=[sample_lineup],
        has_lineups=True,
        main_odds=sample_bet_line,
        has_bets=True,
        has_statistics=False,
    )


@pytest.fixture
def sample_game_postgame(
    sample_competitor_home: Competitor,
    sample_competitor_away: Competitor,
    sample_event_goal: Event,
    sample_statistic: Statistic,
    sample_bet_line: BetLine,
) -> Game:
    """Sample finished game."""
    return Game(
        gid=12346,
        name="Manchester United vs Liverpool",
        sport_type_id=1,
        competition_id=8,
        competition_display_name="Premier League",
        round_name="Matchday 14",
        gt=1,  # FINISHED
        gtd="FT",
        stime="2024-01-15T15:00:00Z",
        is_started=True,
        comps=[sample_competitor_home, sample_competitor_away],
        scrs=[2, 1],
        winner=1,  # Home win
        events=[sample_event_goal],
        statistics=[sample_statistic],
        has_statistics=True,
        main_odds=sample_bet_line,
        has_bets=True,
    )


@pytest.fixture
def sample_games_multiple(
    sample_game_pregame: Game,
    sample_game_postgame: Game,
) -> list[Game]:
    """Multiple games for daily recap testing."""
    return [sample_game_postgame, sample_game_pregame]


@pytest.fixture
def sample_game_response() -> dict[str, Any]:
    """Sample 365Scores API response."""
    return {
        "Games": [
            {
                "ID": 12345,
                "Name": "Test Match",
                "SID": 1,
                "Comp": 8,
                "CompetitionDisplayName": "Premier League",
                "GT": 1,
                "GTD": "FT",
                "STime": "2024-01-15T15:00:00Z",
                "Comps": [
                    {"ID": 101, "Name": "Team A", "SName": "TMA"},
                    {"ID": 102, "Name": "Team B", "SName": "TMB"},
                ],
                "Scrs": [2, 1],
                "Winner": 1,
                "HasStatistics": True,
                "HasBets": True,
            }
        ],
        "RequestUpdateID": 123456,
    }


@pytest.fixture
def mock_httpx_client(sample_game_response: dict[str, Any]):
    """Mock httpx AsyncClient."""
    with patch("httpx.AsyncClient") as mock:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = sample_game_response
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response
        mock.return_value.__aenter__.return_value = mock_client
        yield mock


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic client."""
    with patch("src.services.script_engine.script_generator.Anthropic") as mock:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(text="Welcome to 365Scores. [PAUSE:short] Here's your recap...")
        ]
        mock_client.messages.create.return_value = mock_response
        mock.return_value = mock_client
        yield mock


@pytest.fixture
def mock_elevenlabs():
    """Mock ElevenLabs client."""
    with patch("src.services.audio_manager.synthesizer.ElevenLabs") as mock:
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"fake_audio_chunk"])
        mock.return_value = mock_client
        yield mock


@pytest.fixture
def sample_script() -> str:
    """Sample generated podcast script."""
    return """Welcome to 365Scores Daily Recap. [PAUSE:short]

In today's Premier League action, *Manchester United* took on *Liverpool* at Old Trafford.
[PAUSE:medium]

The home side came out on top with a 2-1 victory. Marcus Rashford opened the scoring in
the 23rd minute with a brilliant strike, assisted by Bruno Fernandes.
[PAUSE:short]

United dominated possession with 55% of the ball. [PAUSE:medium]

That's your recap for today. Thanks for listening to 365Scores."""
