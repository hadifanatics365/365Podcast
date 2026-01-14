"""Tests for game data models."""

import pytest

from src.models import (
    BetLine,
    BetLineOption,
    Competitor,
    Event,
    Game,
    GameStatus,
    LineUp,
    Player,
    ScoresData,
    Statistic,
)


class TestGameStatus:
    """Test GameStatus enum helpers."""

    def test_is_finished_for_finished_status(self):
        """FINISHED status should be detected."""
        assert GameStatus.is_finished(GameStatus.FINISHED) is True
        assert GameStatus.is_finished(GameStatus.JUST_ENDED) is True
        assert GameStatus.is_finished(GameStatus.TO_FINISH) is True

    def test_is_finished_for_other_status(self):
        """Non-finished status should return False."""
        assert GameStatus.is_finished(GameStatus.DIDNT_START) is False
        assert GameStatus.is_finished(GameStatus.ACTIVE) is False

    def test_is_upcoming(self):
        """DIDNT_START should be detected as upcoming."""
        assert GameStatus.is_upcoming(GameStatus.DIDNT_START) is True
        assert GameStatus.is_upcoming(GameStatus.ACTIVE) is False

    def test_is_live(self):
        """ACTIVE should be detected as live."""
        assert GameStatus.is_live(GameStatus.ACTIVE) is True
        assert GameStatus.is_live(GameStatus.FINISHED) is False


class TestCompetitor:
    """Test Competitor model."""

    def test_competitor_from_dict(self):
        """Should parse from API response dict."""
        data = {
            "ID": 101,
            "Name": "Manchester United",
            "SName": "MUN",
            "Color": "#DA291C",
        }
        comp = Competitor.model_validate(data)

        assert comp.id == 101
        assert comp.name == "Manchester United"
        assert comp.short_name == "MUN"
        assert comp.main_color == "#DA291C"

    def test_competitor_defaults(self):
        """Should have sensible defaults."""
        comp = Competitor(id=1)
        assert comp.name == ""
        assert comp.short_name == ""
        assert comp.symbolic_name is None


class TestEvent:
    """Test Event model."""

    def test_event_from_dict(self):
        """Should parse from API response dict."""
        data = {
            "GT": 45,
            "GTD": "45+2'",
            "Player": "Marcus Rashford",
            "Type": 1,
            "Num": 0,
            "ExtraPlayer": "Bruno Fernandes",
        }
        event = Event.model_validate(data)

        assert event.gt == 45
        assert event.gtd == "45+2'"
        assert event.player == "Marcus Rashford"
        assert event.type == 1
        assert event.num == 0
        assert event.extra_player == "Bruno Fernandes"


class TestStatistic:
    """Test Statistic model."""

    def test_statistic_from_dict(self):
        """Should parse from API response dict."""
        data = {
            "Type": 1,
            "Name": "Possession",
            "Vals": ["55%", "45%"],
            "ValsPct": [55.0, 45.0],
            "IsBold": True,
        }
        stat = Statistic.model_validate(data)

        assert stat.type == 1
        assert stat.name == "Possession"
        assert stat.vals == ["55%", "45%"]
        assert stat.vals_pct == [55.0, 45.0]
        assert stat.is_bold is True


class TestLineUp:
    """Test LineUp model."""

    def test_lineup_with_players(self):
        """Should parse lineup with players."""
        data = {
            "Formation": "4-3-3",
            "CompNum": 0,
            "Players": [
                {"PID": 1, "Name": "GK Player", "Pos": 1},
                {"PID": 2, "Name": "Defender", "Pos": 2},
            ],
        }
        lineup = LineUp.model_validate(data)

        assert lineup.formation == "4-3-3"
        assert lineup.comp_num == 0
        assert len(lineup.players) == 2
        assert lineup.players[0].name == "GK Player"


class TestBetLine:
    """Test BetLine model."""

    def test_betline_with_options(self):
        """Should parse betting line with options."""
        data = {
            "ID": 1,
            "Type": 1,
            "Options": [
                {"Num": 1, "Name": "1", "Rate": "2.10"},
                {"Num": 2, "Name": "X", "Rate": "3.50"},
                {"Num": 3, "Name": "2", "Rate": "3.20"},
            ],
        }
        bet = BetLine.model_validate(data)

        assert bet.line_id == 1
        assert bet.type == 1
        assert len(bet.options) == 3
        assert bet.options[0].rate == "2.10"


class TestGame:
    """Test Game model."""

    def test_game_from_api_response(self, sample_game_response):
        """Should parse from API response."""
        game_data = sample_game_response["Games"][0]
        game = Game.model_validate(game_data)

        assert game.gid == 12345
        assert game.name == "Test Match"
        assert game.sport_type_id == 1
        assert game.gt == 1  # FINISHED
        assert len(game.comps) == 2
        assert game.scrs == [2, 1]
        assert game.winner == 1

    def test_game_home_team_property(self, sample_game_postgame):
        """Should return home team from comps."""
        home = sample_game_postgame.home_team
        assert home is not None
        assert home.name == "Manchester United"

    def test_game_away_team_property(self, sample_game_postgame):
        """Should return away team from comps."""
        away = sample_game_postgame.away_team
        assert away is not None
        assert away.name == "Liverpool FC"

    def test_game_scores_properties(self, sample_game_postgame):
        """Should return scores correctly."""
        assert sample_game_postgame.home_score == 2
        assert sample_game_postgame.away_score == 1

    def test_game_start_datetime_parsing(self, sample_game_pregame):
        """Should parse start time to datetime."""
        dt = sample_game_pregame.start_datetime
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 20


class TestScoresData:
    """Test ScoresData container model."""

    def test_scores_data_from_response(self, sample_game_response):
        """Should parse full API response."""
        scores = ScoresData.model_validate(sample_game_response)

        assert len(scores.games) == 1
        assert scores.request_update_id == 123456
        assert scores.games[0].gid == 12345
