"""
Acceptance & Regression Tests for the Mandatory Hackathon Deliverable:
What-if Corridor Ranking (`GET /api/corridors/rank`) and Baseline vs. What-if Rank Changes.

Covers all Phase 1, Phase 2, and Phase 3 test cases:
1. Default / baseline weight: GET /api/corridors/rank?heat_weight=0.6&top=5
2. High heat weight: GET /api/corridors/rank?heat_weight=0.9&top=5
3. Manual calculation verification for at least two real corridors
4. Sorting and deterministic tie-breaking by ascending corridor ID
5. Missing heat_weight rejection (HTTP 422)
6. Invalid heat_weight rejection (<0, >1, NaN, Infinity, non-numeric)
7. Invalid top rejection (0, negative, >100, non-integer)
8. Missing / no-data raster pixel exclusion
9. Sensitivity across weights (0.0, 0.3, 0.6, 0.9, 1.0)
10. Baseline vs. What-if Rank Changes novelty verification
11. Prune / Gemini Explain This Ranking integration for What-if scores
"""

import math
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import get_settings
from app.services.raster_service import RasterService
from app.services.road_service import RoadService

client = TestClient(app)


class TestWhatIfCorridorRankingEndpoint:
    """End-to-end API tests for GET /api/corridors/rank."""

    def test_baseline_weight_0_6_top_5(self):
        """1. Default / baseline weight: GET /api/corridors/rank?heat_weight=0.6&top=5."""
        res = client.get("/api/corridors/rank?heat_weight=0.6&top=5")
        assert res.status_code == 200
        data = res.json()

        assert "corridors" in data
        assert "baseline_comparison" in data
        assert "metadata" in data

        corridors = data["corridors"]
        assert len(corridors) == 5

        meta = data["metadata"]
        assert meta["heat_weight"] == pytest.approx(0.6)
        assert meta["green_deficit_weight"] == pytest.approx(0.4)
        assert meta["baseline_heat_weight"] == pytest.approx(0.6)
        assert meta["top"] == 5
        assert meta["returned_count"] == 5
        assert meta["total_eligible_corridors"] == 44

        # Check descending score order and exact formula at baseline 0.6
        scores = [c["score"] for c in corridors]
        assert scores == sorted(scores, reverse=True)

        for idx, c in enumerate(corridors, start=1):
            assert c["rank"] == idx
            assert c["baseline_rank"] == idx
            assert c["rank_change"] == 0
            assert c["score_change"] == pytest.approx(0.0, abs=1e-4)
            assert 0.0 <= c["heat"] <= 1.0
            assert 0.0 <= c["ndvi"] <= 1.0
            assert c["green_deficit"] == pytest.approx(1.0 - c["ndvi"], abs=1e-4)
            expected_score = 0.6 * c["heat"] + 0.4 * (1.0 - c["ndvi"])
            assert c["score"] == pytest.approx(expected_score, abs=1e-4)
            assert c["baseline_score"] == pytest.approx(expected_score, abs=1e-4)
            assert c["geometry"] is not None

    def test_high_heat_weight_0_9_top_5(self):
        """2. High heat weight: GET /api/corridors/rank?heat_weight=0.9&top=5."""
        res = client.get("/api/corridors/rank?heat_weight=0.9&top=5")
        assert res.status_code == 200
        data = res.json()

        corridors = data["corridors"]
        assert len(corridors) == 5

        scores = [c["score"] for c in corridors]
        assert scores == sorted(scores, reverse=True)

        for idx, c in enumerate(corridors, start=1):
            assert c["rank"] == idx
            expected = 0.9 * c["heat"] + 0.1 * (1.0 - c["ndvi"])
            assert c["score"] == pytest.approx(expected, abs=1e-4)
            assert c["heat_contribution"] == pytest.approx(0.9 * c["heat"], abs=1e-4)
            assert c["green_deficit_contribution"] == pytest.approx(0.1 * (1.0 - c["ndvi"]), abs=1e-4)

        # Verify real rank swap at top:
        # At w=0.6: #1 is delhi_corridor_044 (Jafrabad), #2 is delhi_corridor_024 (GT Road Dilshad Garden)
        # At w=0.9: #1 is delhi_corridor_024 (GT Road Dilshad Garden, +1 place), #2 is delhi_corridor_044 (-1 place)
        assert corridors[0]["id"] == "delhi_corridor_024"
        assert corridors[0]["baseline_rank"] == 2
        assert corridors[0]["rank"] == 1
        assert corridors[0]["rank_change"] == 1

        assert corridors[1]["id"] == "delhi_corridor_044"
        assert corridors[1]["baseline_rank"] == 1
        assert corridors[1]["rank"] == 2
        assert corridors[1]["rank_change"] == -1

    def test_manual_calculation_verification_two_real_corridors(self):
        """
        3. Manual calculation verification for two real corridors:
           - Corridor A: delhi_corridor_044 (Jafrabad Main Market Street)
             Heat = 0.5021, NDVI = 0.2864, (1 - NDVI) = 0.7136
             * w = 0.6 -> 0.6 * 0.5021 + 0.4 * 0.7136 = 0.30126 + 0.28544 = 0.5867
             * w = 0.9 -> 0.9 * 0.5021 + 0.1 * 0.7136 = 0.45189 + 0.07136 = 0.52325 -> 0.5232
           - Corridor B: delhi_corridor_024 (Grand Trunk Road (Dilshad Garden))
             Heat = 0.5247, NDVI = 0.3724, (1 - NDVI) = 0.6276
             * w = 0.6 -> 0.6 * 0.5247 + 0.4 * 0.6276 = 0.31482 + 0.25104 = 0.56586 -> 0.5659
             * w = 0.9 -> 0.9 * 0.5247 + 0.1 * 0.6276 = 0.47223 + 0.06276 = 0.53499 -> 0.5350
        """
        res_06 = client.get("/api/corridors/rank?heat_weight=0.6&top=10").json()
        res_09 = client.get("/api/corridors/rank?heat_weight=0.9&top=10").json()

        map_06 = {c["id"]: c for c in res_06["corridors"]}
        map_09 = {c["id"]: c for c in res_09["corridors"]}

        c044_06 = map_06["delhi_corridor_044"]
        assert c044_06["heat"] == pytest.approx(0.5021, abs=1e-4)
        assert c044_06["ndvi"] == pytest.approx(0.2864, abs=1e-4)
        assert c044_06["score"] == pytest.approx(0.5867, abs=1e-4)

        c044_09 = map_09["delhi_corridor_044"]
        assert c044_09["score"] == pytest.approx(0.5232, abs=1e-4)
        assert c044_09["heat_contribution"] == pytest.approx(0.4519, abs=1e-4)
        assert c044_09["green_deficit_contribution"] == pytest.approx(0.0714, abs=1e-4)

        c024_06 = map_06["delhi_corridor_024"]
        assert c024_06["heat"] == pytest.approx(0.5247, abs=1e-4)
        assert c024_06["ndvi"] == pytest.approx(0.3724, abs=1e-4)
        assert c024_06["score"] == pytest.approx(0.5659, abs=1e-4)

        c024_09 = map_09["delhi_corridor_024"]
        assert c024_09["score"] == pytest.approx(0.5350, abs=1e-4)
        assert c024_09["heat_contribution"] == pytest.approx(0.4722, abs=1e-4)
        assert c024_09["green_deficit_contribution"] == pytest.approx(0.0628, abs=1e-4)

    def test_sorting_and_deterministic_tie_breaking(self, monkeypatch):
        """4. Sorting and deterministic tie-breaking by ascending corridor id when scores tie."""
        road_service = RoadService(get_settings())
        raster_service = RasterService(get_settings())

        synthetic_metrics = [
            {
                "id": "corridor_beta",
                "name": "Beta Road",
                "district": "Central Delhi",
                "highway": "secondary",
                "length_meters": 500.0,
                "heat": 0.5000,
                "ndvi": 0.5000,
                "valid_samples": 12,
                "centroid": [77.2, 28.6],
                "geometry": {"type": "LineString", "coordinates": [[77.2, 28.6], [77.21, 28.61]]},
            },
            {
                "id": "corridor_alpha",
                "name": "Alpha Road",
                "district": "Central Delhi",
                "highway": "secondary",
                "length_meters": 500.0,
                "heat": 0.5000,
                "ndvi": 0.5000,
                "valid_samples": 12,
                "centroid": [77.2, 28.6],
                "geometry": {"type": "LineString", "coordinates": [[77.2, 28.6], [77.21, 28.61]]},
            },
        ]
        monkeypatch.setattr(road_service, "sample_corridor_heat_ndvi", lambda rs: synthetic_metrics)

        res = road_service.rank_corridors_what_if(raster_service, heat_weight=0.6, top=5)
        ranked_ids = [c["id"] for c in res["corridors"]]
        assert ranked_ids == ["corridor_alpha", "corridor_beta"]

    def test_missing_heat_weight_rejected(self):
        """5. Missing heat_weight must return 422 validation error and NOT silently default."""
        res1 = client.get("/api/corridors/rank")
        assert res1.status_code == 422
        assert "heat_weight" in res1.json()["detail"]

        res2 = client.get("/api/corridors/rank?top=5")
        assert res2.status_code == 422
        assert "heat_weight" in res2.json()["detail"]

    @pytest.mark.parametrize(
        "bad_weight",
        ["-0.1", "-5", "1.01", "2.5", "NaN", "nan", "Infinity", "-Infinity", "inf", "abc", ""],
    )
    def test_invalid_heat_weight_rejected(self, bad_weight):
        """6. Invalid heat_weight (<0, >1, NaN, Infinity, non-numeric) returns 422."""
        res = client.get(f"/api/corridors/rank?heat_weight={bad_weight}&top=5")
        assert res.status_code == 422
        assert "detail" in res.json()

    @pytest.mark.parametrize(
        "bad_top",
        ["0", "-1", "-10", "101", "9999", "abc", "3.5"],
    )
    def test_invalid_top_rejected(self, bad_top):
        """7. Invalid top (0, negative, >100, non-integer) returns 422."""
        res = client.get(f"/api/corridors/rank?heat_weight=0.6&top={bad_top}")
        assert res.status_code == 422
        assert "detail" in res.json()

    def test_no_data_corridors_excluded_safely(self, monkeypatch):
        """8. Missing or no-data pixels are excluded safely without NaN in response."""
        road_service = RoadService(get_settings())
        raster_service = RasterService(get_settings())

        synthetic_metrics = [
            {
                "id": "valid_corridor_1",
                "name": "Valid Corridor",
                "district": "South Delhi",
                "highway": "primary",
                "length_meters": 600.0,
                "heat": 0.70,
                "ndvi": 0.30,
                "valid_samples": 15,
                "centroid": [77.2, 28.5],
                "geometry": {"type": "LineString", "coordinates": [[77.2, 28.5], [77.21, 28.51]]},
            },
            {
                "id": "nodata_corridor_2",
                "name": "NoData Corridor",
                "district": "South Delhi",
                "highway": "primary",
                "length_meters": 400.0,
                "heat": None,
                "ndvi": None,
                "valid_samples": 0,
                "centroid": [77.2, 28.5],
                "geometry": None,
            },
            {
                "id": "nan_corridor_3",
                "name": "NaN Corridor",
                "district": "South Delhi",
                "highway": "primary",
                "length_meters": 400.0,
                "heat": float("nan"),
                "ndvi": 0.4,
                "valid_samples": 0,
                "centroid": [77.2, 28.5],
                "geometry": None,
            },
        ]
        monkeypatch.setattr(road_service, "sample_corridor_heat_ndvi", lambda rs: synthetic_metrics)

        res = road_service.rank_corridors_what_if(raster_service, heat_weight=0.6, top=5)
        assert len(res["corridors"]) == 1
        assert res["corridors"][0]["id"] == "valid_corridor_1"
        assert res["metadata"]["excluded_no_data_corridors"] == 2
        assert math.isfinite(res["corridors"][0]["score"])

    def test_sensitivity_across_extreme_weights(self):
        """9. Sensitivity: w=0.0 ranks purely by (1 - NDVI); w=1.0 ranks purely by Heat."""
        res_0 = client.get("/api/corridors/rank?heat_weight=0.0&top=5").json()["corridors"]
        res_1 = client.get("/api/corridors/rank?heat_weight=1.0&top=5").json()["corridors"]

        for c in res_0:
            assert c["score"] == pytest.approx(1.0 - c["ndvi"], abs=1e-4)
            assert c["heat_contribution"] == pytest.approx(0.0, abs=1e-4)

        for c in res_1:
            assert c["score"] == pytest.approx(c["heat"], abs=1e-4)
            assert c["green_deficit_contribution"] == pytest.approx(0.0, abs=1e-4)

        # Top corridor at w=0.0 (pure green deficit) vs w=1.0 (pure heat) must differ
        assert res_0[0]["id"] != res_1[0]["id"]

    def test_baseline_vs_whatif_comparison_panel_data(self):
        """10. Verify Baseline vs. What-if Rank Changes comparison fields."""
        res = client.get("/api/corridors/rank?heat_weight=0.9&top=5")
        assert res.status_code == 200
        comp = res.json()["baseline_comparison"]

        assert comp["baseline_heat_weight"] == pytest.approx(0.6)
        assert comp["current_heat_weight"] == pytest.approx(0.9)
        assert comp["corridors_with_rank_change_count"] > 0
        assert len(comp["comparison_table"]) >= 5

        # At w=0.9 with top=3, delhi_corridor_022 enters Top 3 while delhi_corridor_041 leaves Top 3
        res_top3 = client.get("/api/corridors/rank?heat_weight=0.9&top=3").json()["baseline_comparison"]
        entered_ids_top3 = [c["id"] for c in res_top3["entered_top_n"]]
        left_ids_top3 = [c["id"] for c in res_top3["left_top_n"]]
        assert "delhi_corridor_022" in entered_ids_top3
        assert "delhi_corridor_041" in left_ids_top3

        # At w=0.0 (pure green deficit) with top=5, new green-deficit corridors enter Top 5
        res_w0 = client.get("/api/corridors/rank?heat_weight=0.0&top=5").json()["baseline_comparison"]
        assert len(res_w0["entered_top_n"]) >= 1
        assert len(res_w0["left_top_n"]) >= 1

    def test_explain_this_ranking_for_what_if_corridor(self):
        """11. Verify isolated Explain This Ranking endpoint with What-if parameters."""
        rank_res = client.get("/api/corridors/rank?heat_weight=0.9&top=5").json()
        top_corridor = rank_res["corridors"][0]

        explain_res = client.post(
            "/api/corridors/explain-ranking",
            json={
                "id": top_corridor["id"],
                "name": top_corridor["name"],
                "district": top_corridor["district"],
                "highway": top_corridor["highway"],
                "priority_score": top_corridor["score"],
                "score": top_corridor["score"],
                "heat": top_corridor["heat"],
                "ndvi": top_corridor["ndvi"],
                "green_deficit": top_corridor["green_deficit"],
                "heat_weight": top_corridor["heat_weight"],
                "green_deficit_weight": top_corridor["green_deficit_weight"],
                "heat_contribution": top_corridor["heat_contribution"],
                "green_deficit_contribution": top_corridor["green_deficit_contribution"],
                "rank": top_corridor["rank"],
                "baseline_rank": top_corridor["baseline_rank"],
                "rank_change": top_corridor["rank_change"],
                "baseline_score": top_corridor["baseline_score"],
            },
        )
        assert explain_res.status_code == 200
        body = explain_res.json()
        text = body.get("explanation") or body.get("fallback_explanation")
        assert text is not None
        assert top_corridor["name"] in text
        assert "0.90" in text or "0.9" in text

    def test_enriched_corridor_fields_in_what_if_ranking(self):
        """12. Verify enriched tri-vector, interventions, and CPWD lifecycle costs on ranked corridors."""
        res = client.get("/api/corridors/rank?heat_weight=0.6&top=5")
        assert res.status_code == 200
        c = res.json()["corridors"][0]
        assert "feasibility" in c and 0.0 <= c["feasibility"] <= 1.0
        assert "confidence" in c and 0.0 <= c["confidence"] <= 1.0
        assert "recommended_interventions" in c and len(c["recommended_interventions"]) >= 1
        assert "lifecycle_costs" in c and (
            "capex_inr" in c["lifecycle_costs"] or "five_year_lifecycle_lakhs" in c["lifecycle_costs"]
        )
        assert "priority_signals" in c

    def test_professional_rank_endpoint_validation_and_scoring(self):
        """13. Verify POST /api/corridors/professional-rank with custom multi-criteria weights & constraints."""
        # Valid normalized weights summing to 1.0
        res = client.post(
            "/api/corridors/professional-rank",
            json={
                "weights": {
                    "lst": 0.40,
                    "ndvi_deficit": 0.25,
                    "aqi": 0.15,
                    "ped_exposure": 0.10,
                    "vulnerable_pop": 0.05,
                    "green_access": 0.05,
                },
                "constraints": {
                    "footpath_width_m": 1.6,
                    "budget_lakhs": 20.0,
                    "utility_conflict": True,
                    "access_restriction": False,
                    "maintenance_capacity": "low",
                },
                "top": 5,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["corridors"]) == 5
        assert data["summary"]["user_constraints_applied"] is True
        assert any("utility conflict" in n.lower() for n in data["corridors"][0]["user_constraint_notes"])

        # Reject negative weight
        bad_neg = client.post(
            "/api/corridors/professional-rank",
            json={"weights": {"lst": -0.2, "ndvi_deficit": 1.2}},
        )
        assert bad_neg.status_code == 422

        # Reject weights not summing to 1.0 or 100
        bad_sum = client.post(
            "/api/corridors/professional-rank",
            json={"weights": {"lst": 0.2, "ndvi_deficit": 0.2}},
        )
        assert bad_sum.status_code == 422

    def test_ai_action_agent_endpoint(self):
        """14. Verify POST /api/corridors/ai-agent returns typed validated actions and grounded explanation."""
        rank_res = client.get("/api/corridors/rank?heat_weight=0.6&top=5").json()
        res = client.post(
            "/api/corridors/ai-agent",
            json={
                "prompt": "Set heat weight to 0.85, show top 5 corridors, and switch to Professional Mode",
                "context": {
                    "mode": "public",
                    "scenario": "balanced",
                    "heat_weight": 0.6,
                    "top": 5,
                    "selected_corridor": rank_res["corridors"][0],
                    "corridors": rank_res["corridors"],
                },
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert "explanation" in body and len(body["explanation"]) > 20
        assert "actions" in body and isinstance(body["actions"], list)
        action_types = [a["type"] for a in body["actions"]]
        assert "SET_HEAT_WEIGHT" in action_types
        assert "SWITCH_MODE" in action_types

