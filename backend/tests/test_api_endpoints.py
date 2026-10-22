"""
Integration Tests for VanSetu API Endpoints:
- Health check
- Corridors GeoJSON with multi-scenario support
- Sensitivity analysis endpoint
- Layer metadata and provenance
- Community observation ingestion, IP privacy hashing, and rate limiting
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    """Test client wrapped in lifespan context manager so all services are initialized."""
    with TestClient(app) as test_client:
        yield test_client


class TestSystemEndpoints:
    """Test health and metadata endpoints."""

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "bounds" in data

    def test_layers_metadata(self, client):
        response = client.get("/api/layers/metadata")
        assert response.status_code == 200
        data = response.json()
        assert "datasets" in data
        assert "ndvi" in data["datasets"]
        assert "lst" in data["datasets"]
        assert "roads" in data["datasets"]

        # Verify resolution caveats are explicitly documented
        modis = data["datasets"]["lst"]
        assert "1 km" in modis["native_spatial_resolution"] or "1,000" in modis["native_spatial_resolution"]
        assert "macro-thermal" in modis["scientific_classification"].lower()


class TestCorridorEndpoints:
    """Test corridor query, scenario selection, ranking, and sensitivity."""

    def test_get_corridors_default_balanced(self, client):
        response = client.get("/api/corridors?percentile=70&scenario=balanced")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert "metadata" in data
        assert data["metadata"]["scenario"] == "balanced"
        assert "outputs_distinction" in data["metadata"]

        # Verify corridor feature properties contain 3 distinct evaluative vectors
        if len(data["features"]) > 0:
            first_props = data["features"][0]["properties"]
            assert "priority_score" in first_props
            assert "feasibility" in first_props
            assert "confidence" in first_props
            assert "lifecycle_costs" in first_props
            assert "monitoring_framework" in first_props

    def test_get_corridors_heat_resilience_scenario(self, client):
        response = client.get("/api/corridors?percentile=80&scenario=heat_resilience")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["scenario"] == "heat_resilience"

    def test_corridors_priority_ranking(self, client):
        response = client.get("/api/corridors/priority-ranking?percentile=80")
        assert response.status_code == 200
        data = response.json()
        assert "corridors" in data
        assert "available_scenarios" in data
        if len(data["corridors"]) > 0:
            top = data["corridors"][0]
            assert top["rank"] == 1
            assert "priority_score" in top
            assert "feasibility" in top
            assert "confidence" in top

    def test_corridors_sensitivity_analysis_endpoint(self, client):
        response = client.get("/api/corridors/sensitivity?percentile=80")
        assert response.status_code == 200
        data = response.json()
        assert "corridor_count" in data
        assert "scenarios_evaluated" in data
        assert "stability_summary" in data
        assert "corridors" in data
        if len(data["corridors"]) > 0:
            c = data["corridors"][0]
            assert "stability_index" in c
            assert "mean_rank" in c
            assert "max_rank_shift" in c
            assert "is_stable" in c


class TestCommunityEndpoints:
    """Test community feedback ingestion, district validation, and deduplication."""

    def test_get_districts(self, client):
        response = client.get("/api/districts")
        assert response.status_code == 200
        data = response.json()
        assert "districts" in data
        assert len(data["districts"]) == 11
        assert "Central Delhi" in data["districts"]

    def test_submit_community_data_and_prevent_immediate_duplicate(self, client):
        import uuid
        unique_street = f"Netaji Subhash Marg Test {uuid.uuid4().hex[:6]}"
        payload = {
            "city": "Delhi",
            "ward": "Central Delhi",
            "street": unique_street,
            "userType": "resident",
            "heatLevel": "Extreme",
            "shadeLevel": "No Shade",
            "pedestrianActivity": "High",
            "peakTime": "Afternoon",
            "pollutionLevel": "Severe",
            "pollutionSource": "Vehicular Traffic",
            "heatwaveRisk": "High",
            "vulnerablePopulation": "High",
            "emergencyHeatIncidents": "None reported",
        }

        # First submission should succeed
        res1 = client.post("/api/community-data", json=payload)
        assert res1.status_code == 200
        body1 = res1.json()
        assert body1["status"] == "success"
        assert "id" in body1
        assert "verification_status" in body1
        assert body1["verification_status"] == "unverified"

        # Immediate exact duplicate submission from same client should trigger rate-limiting / deduplication (429)
        res2 = client.post("/api/community-data", json=payload)
        assert res2.status_code == 429
        assert "Duplicate observation" in res2.json()["detail"]

    def test_submit_invalid_district_rejected(self, client):
        invalid_payload = {
            "city": "Mumbai",
            "ward": "Invalid Non-Delhi Zone",
            "street": "Marine Drive",
        }
        res = client.post("/api/community-data", json=invalid_payload)
        assert res.status_code == 400
        assert "Invalid Delhi district" in res.json()["detail"]
