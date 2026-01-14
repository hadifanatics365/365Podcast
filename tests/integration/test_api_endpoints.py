"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

from src.main import app


class TestHealthEndpoints:
    """Test health check endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_root_endpoint(self, client: TestClient):
        """Root endpoint should return service info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "docs" in data

    def test_health_endpoint(self, client: TestClient):
        """Health endpoint should return healthy status."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_ready_endpoint(self, client: TestClient):
        """Readiness endpoint should return ready status."""
        response = client.get("/api/v1/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True

    def test_live_endpoint(self, client: TestClient):
        """Liveness endpoint should return alive status."""
        response = client.get("/api/v1/live")
        assert response.status_code == 200
        data = response.json()
        assert data["alive"] is True


class TestPodcastEndpoints:
    """Test podcast generation endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_generate_requires_game_ids(self, client: TestClient):
        """Generate endpoint should require game_ids."""
        response = client.post(
            "/api/v1/podcast/generate",
            json={},
        )
        assert response.status_code == 422  # Validation error

    def test_generate_validates_game_ids_not_empty(self, client: TestClient):
        """Generate endpoint should reject empty game_ids."""
        response = client.post(
            "/api/v1/podcast/generate",
            json={"game_ids": []},
        )
        assert response.status_code == 422

    def test_generate_validates_max_games(self, client: TestClient):
        """Generate endpoint should limit game count."""
        response = client.post(
            "/api/v1/podcast/generate",
            json={"game_ids": [str(i) for i in range(25)]},  # More than 20
        )
        assert response.status_code == 422

    @patch("src.api.routes.podcast.get_orchestrator")
    def test_generate_sync_success(
        self,
        mock_get_orchestrator,
        client: TestClient,
    ):
        """Generate endpoint should return result on success."""
        # Mock orchestrator
        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.job_id = "pod_test123"
        mock_result.status = "completed"
        mock_result.audio_url = "https://example.com/audio.mp3"
        mock_result.duration_seconds = 120.5
        mock_result.script = "Test script"
        mock_result.created_at = "2024-01-15T10:00:00Z"

        mock_orchestrator.generate_podcast = AsyncMock(return_value=mock_result)
        mock_get_orchestrator.return_value = mock_orchestrator

        response = client.post(
            "/api/v1/podcast/generate",
            json={"game_ids": ["12345"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "pod_test123"
        assert data["status"] == "completed"
        assert data["audio_url"] == "https://example.com/audio.mp3"

    @patch("src.api.routes.podcast.get_orchestrator")
    def test_generate_handles_data_fetch_error(
        self,
        mock_get_orchestrator,
        client: TestClient,
    ):
        """Generate should return 404 on data fetch error."""
        from src.exceptions import DataFetchError

        mock_orchestrator = MagicMock()
        mock_orchestrator.generate_podcast = AsyncMock(
            side_effect=DataFetchError("Game not found", game_ids=["99999"])
        )
        mock_get_orchestrator.return_value = mock_orchestrator

        response = client.post(
            "/api/v1/podcast/generate",
            json={"game_ids": ["99999"]},
        )

        assert response.status_code == 404
        data = response.json()["detail"]
        assert data["error"] == "GameNotFound"

    @patch("src.api.routes.podcast.get_orchestrator")
    def test_generate_handles_rate_limit(
        self,
        mock_get_orchestrator,
        client: TestClient,
    ):
        """Generate should return 429 on rate limit."""
        from src.exceptions import RateLimitError

        mock_orchestrator = MagicMock()
        mock_orchestrator.generate_podcast = AsyncMock(
            side_effect=RateLimitError(
                "Rate limit exceeded",
                service="anthropic",
                retry_after=60,
            )
        )
        mock_get_orchestrator.return_value = mock_orchestrator

        response = client.post(
            "/api/v1/podcast/generate",
            json={"game_ids": ["12345"]},
        )

        assert response.status_code == 429
        data = response.json()["detail"]
        assert data["error"] == "RateLimitExceeded"
        assert data["retry_after"] == 60

    def test_status_endpoint_not_found(self, client: TestClient):
        """Status endpoint should return 404 for unknown job."""
        response = client.get("/api/v1/podcast/status/unknown_job")
        assert response.status_code == 404

    def test_voices_endpoint(self, client: TestClient):
        """Voices endpoint should list available voices."""
        with patch("src.api.routes.podcast.AudioSynthesizer") as mock:
            mock_synth = MagicMock()
            mock_synth.get_available_voices = AsyncMock(
                return_value=[
                    {"voice_id": "test1", "name": "Test Voice"},
                ]
            )
            mock_synth.default_voice = "test1"
            mock.return_value = mock_synth

            response = client.get("/api/v1/podcast/voices")

            assert response.status_code == 200
            data = response.json()
            assert "voices" in data
            assert "default" in data
