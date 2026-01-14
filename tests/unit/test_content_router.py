"""Tests for ContentRouter."""

import pytest

from src.models import ContentMode, Game, GameStatus
from src.services.script_engine.content_router import ContentRouter


class TestContentRouter:
    """Test suite for ContentRouter."""

    @pytest.fixture
    def router(self) -> ContentRouter:
        """Create ContentRouter instance."""
        return ContentRouter()

    def test_empty_games_returns_daily_recap(self, router: ContentRouter):
        """Empty games list should default to daily recap."""
        mode = router.determine_mode([])
        assert mode == ContentMode.DAILY_RECAP

    def test_single_pregame_returns_spotlight_pregame(
        self,
        router: ContentRouter,
        sample_game_pregame: Game,
    ):
        """Single pre-game should return GAME_SPOTLIGHT_PREGAME."""
        mode = router.determine_mode([sample_game_pregame])
        assert mode == ContentMode.GAME_SPOTLIGHT_PREGAME

    def test_single_postgame_returns_spotlight_postgame(
        self,
        router: ContentRouter,
        sample_game_postgame: Game,
    ):
        """Single finished game should return GAME_SPOTLIGHT_POSTGAME."""
        mode = router.determine_mode([sample_game_postgame])
        assert mode == ContentMode.GAME_SPOTLIGHT_POSTGAME

    def test_multiple_games_returns_daily_recap(
        self,
        router: ContentRouter,
        sample_games_multiple: list[Game],
    ):
        """Multiple games should return DAILY_RECAP."""
        mode = router.determine_mode(sample_games_multiple)
        assert mode == ContentMode.DAILY_RECAP

    def test_single_live_game_returns_postgame(
        self,
        router: ContentRouter,
        sample_game_postgame: Game,
    ):
        """Live game should be treated as post-game spotlight."""
        sample_game_postgame.gt = GameStatus.ACTIVE
        mode = router.determine_mode([sample_game_postgame])
        assert mode == ContentMode.GAME_SPOTLIGHT_POSTGAME

    def test_categorize_games_separates_by_status(
        self,
        router: ContentRouter,
        sample_games_multiple: list[Game],
    ):
        """Games should be categorized by status."""
        categorized = router.categorize_games_for_recap(sample_games_multiple)

        assert "ended_games" in categorized
        assert "upcoming_games" in categorized
        assert "live_games" in categorized

        # One finished, one upcoming
        assert len(categorized["ended_games"]) == 1
        assert len(categorized["upcoming_games"]) == 1
        assert len(categorized["live_games"]) == 0

    def test_get_content_priorities_daily_recap(self, router: ContentRouter):
        """Daily recap should have expected priorities."""
        priorities = router.get_content_priorities(ContentMode.DAILY_RECAP)

        assert "match_results" in priorities
        assert "key_moments" in priorities
        assert "betting_context" in priorities

    def test_get_content_priorities_pregame(self, router: ContentRouter):
        """Pre-game spotlight should have preview priorities."""
        priorities = router.get_content_priorities(ContentMode.GAME_SPOTLIGHT_PREGAME)

        assert "lineups" in priorities
        assert "form_analysis" in priorities
        assert "betting_preview" in priorities

    def test_get_content_priorities_postgame(self, router: ContentRouter):
        """Post-game spotlight should have recap priorities."""
        priorities = router.get_content_priorities(ContentMode.GAME_SPOTLIGHT_POSTGAME)

        assert "final_score" in priorities
        assert "key_moments" in priorities
        assert "man_of_match" in priorities

    def test_should_include_betting_respects_preference(
        self,
        router: ContentRouter,
        sample_games_multiple: list[Game],
    ):
        """Betting inclusion should respect user preference."""
        # With betting enabled
        assert router.should_include_betting(sample_games_multiple, True) is True

        # With betting disabled
        assert router.should_include_betting(sample_games_multiple, False) is False

    def test_should_include_betting_checks_game_data(
        self,
        router: ContentRouter,
        sample_game_pregame: Game,
    ):
        """Should only include betting if game has betting data."""
        # Game with bets
        assert router.should_include_betting([sample_game_pregame], True) is True

        # Game without bets
        sample_game_pregame.has_bets = False
        sample_game_pregame.main_odds = None
        assert router.should_include_betting([sample_game_pregame], True) is False
