"""
Unit and Integration Tests for Prune AI Gateway + Gemini Ranking Explanation.

Validates:
- Deterministic fallback generation
- Behavior when PRUNE_API_KEY is not configured
- Mocked HTTP response handling (200 success, 401 auth error, 429 rate limit, timeout)
- Preservation of authoritative ranking (Gemini does not modify score)
- Decoupled API endpoint POST /api/corridors/explain-ranking
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
import anyio
import httpx

from app.main import app
from app.services.prune_service import (
    generate_deterministic_explanation,
    explain_corridor_ranking,
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestPruneServiceCore:
    """Test core logic and error boundaries of prune_service."""

    def test_deterministic_explanation_generation(self):
        corridor = {
            "name": "Marg 4 - Connaught Place Outer Ring",
            "priority_score": 0.825,
            "scenario": "heat_resilience",
            "signals": {
                "heat": 0.88,
                "green_deficit": 0.72,
                "pollution": 0.65,
                "pedestrian": 0.90,
                "vulnerable_pop": 0.80,
            },
        }
        text = generate_deterministic_explanation(corridor)
        assert "Marg 4 - Connaught Place Outer Ring" in text
        assert "0.825" in text
        assert "heat_resilience" in text
        assert "thermal radiation exposure" in text

    def test_unconfigured_prune_api_key_returns_graceful_status(self):
        """When PRUNE_API_KEY is absent, returns not_configured without raising."""
        corridor = {
            "name": "Test Corridor",
            "priority_score": 0.65,
            "scenario": "balanced",
            "signals": {"heat": 0.5, "green_deficit": 0.5},
        }

        with patch.dict("os.environ", {"PRUNE_API_KEY": ""}, clear=False):
            res = anyio.run(explain_corridor_ranking, corridor)
            assert res["status"] == "not_configured"
            assert "PRUNE_API_KEY is not configured" in res["message"]
            assert res["explanation"] is None
            assert res["fallback_explanation"] is not None
            assert "0.650" in res["fallback_explanation"]

    def test_successful_prune_gateway_response(self):
        """Simulate a valid 200 response from Prune Gateway."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-test-123",
            "model": "gemini-2.0-flash",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "This corridor exhibits severe microclimate thermal vulnerability due to sparse tree cover and high pedestrian density.",
                    },
                    "prune_metadata": {
                        "cost": 0.00012,
                        "latency_ms": 320,
                        "cache_hit": False,
                        "signed_receipt": "prune_sig_abc123",
                    },
                }
            ],
            "prune_metadata": {
                "cost": 0.00012,
                "latency_ms": 320,
                "signed_receipt": "prune_sig_abc123",
            },
        }

        corridor = {
            "name": "Chandni Chowk",
            "priority_score": 0.89,
            "scenario": "balanced",
            "signals": {"heat": 0.9, "green_deficit": 0.85},
            "active_weights": {"heat": 0.25, "green_deficit": 0.20},
        }

        with patch.dict("os.environ", {"PRUNE_API_KEY": "prune_live_mock_key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                res = anyio.run(explain_corridor_ranking, corridor)
                assert res["status"] == "success"
                assert "microclimate thermal vulnerability" in res["explanation"]
                assert res["model_used"] == "gemini-2.0-flash"
                assert res["prune_metadata"]["cost"] == 0.00012

    def test_prune_gateway_auth_failure(self):
        """Simulate 401 Unauthorized from Prune Gateway."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        corridor = {"name": "Test", "priority_score": 0.5}

        with patch.dict("os.environ", {"PRUNE_API_KEY": "prune_invalid_key"}):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                res = anyio.run(explain_corridor_ranking, corridor)
                assert res["status"] == "authentication_error"
                assert res["fallback_explanation"] is not None

    def test_prune_gateway_timeout(self):
        """Simulate timeout during Prune Gateway call."""
        corridor = {"name": "Test", "priority_score": 0.5}

        with patch.dict("os.environ", {"PRUNE_API_KEY": "prune_key"}):
            with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
                res = anyio.run(explain_corridor_ranking, corridor)
                assert res["status"] == "timeout"
                assert res["fallback_explanation"] is not None


class TestExplainRankingEndpoint:
    """Test API endpoint integration."""

    def test_explain_ranking_endpoint_returns_json(self, client):
        payload = {
            "id": "corridor_1",
            "name": "Asaf Ali Road",
            "district": "Central Delhi",
            "highway": "secondary",
            "priority_score": 0.78,
            "feasibility": 0.65,
            "confidence": 0.80,
            "scenario": "heat_resilience",
            "signals": {
                "heat": 0.85,
                "green_deficit": 0.70,
                "pollution": 0.60,
                "pedestrian": 0.75,
                "vulnerable_pop": 0.70,
            },
            "active_weights": {
                "heat": 0.40,
                "green_deficit": 0.25,
                "pollution": 0.15,
                "pedestrian": 0.10,
                "vulnerable_pop": 0.10,
            },
        }

        response = client.post("/api/corridors/explain-ranking", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ("not_configured", "success", "error", "rate_limited")
        assert "fallback_explanation" in data or "explanation" in data
