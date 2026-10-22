"""
Unit tests for the Sensitivity Analysis Engine.
Validates multi-scenario evaluation, rank variance, and ranking stability index.
"""

import pytest
from app.services.scoring_service import (
    evaluate_corridor_scenarios,
    run_ranking_sensitivity_analysis,
    SCENARIOS,
)


class TestSensitivityAnalysis:
    """Tests for sensitivity analysis across policy scenarios."""

    def test_evaluate_corridor_scenarios_contains_all_scenarios(self):
        """Single corridor evaluation must return a score for every pre-defined scenario."""
        res = evaluate_corridor_scenarios(
            heat_norm=0.8,
            ndvi_norm=0.2,
            aqi_norm=0.7,
            highway_type="tertiary",
        )
        assert isinstance(res, dict)
        for s in SCENARIOS:
            assert s in res
            assert 0.0 <= res[s] <= 1.0

    def test_empty_corridors_returns_empty_sensitivity(self):
        """Empty input returns empty list without error."""
        res = run_ranking_sensitivity_analysis([])
        assert res == []

    def test_ranking_sensitivity_identifies_stable_vs_volatile(self):
        """
        Synthesize two corridors:
        1. Globally extreme across all hazards (high heat, high aqi, high deficit) -> consistently Rank 1 (stable)
        2. High in only one dimension (extreme heat, but pristine air and green) -> rank fluctuates depending on scenario
        """
        corridors = [
            {
                "properties": {
                    "id": "extreme_overall",
                    "name": "Consistently Stressed Corridor",
                    "heat_norm": 0.95,
                    "ndvi_norm": 0.05,
                    "aqi_norm": 0.95,
                    "highway": "secondary",
                }
            },
            {
                "properties": {
                    "id": "heat_only",
                    "name": "Heat-Only Spike Corridor",
                    "heat_norm": 0.90,
                    "ndvi_norm": 0.70,
                    "aqi_norm": 0.10,
                    "highway": "tertiary",
                }
            },
            {
                "properties": {
                    "id": "aqi_only",
                    "name": "AQI-Only Spike Corridor",
                    "heat_norm": 0.15,
                    "ndvi_norm": 0.60,
                    "aqi_norm": 0.95,
                    "highway": "primary",
                }
            },
            {
                "properties": {
                    "id": "low_stress",
                    "name": "Well Vegetated Cool Corridor",
                    "heat_norm": 0.20,
                    "ndvi_norm": 0.85,
                    "aqi_norm": 0.20,
                    "highway": "residential",
                }
            },
        ]

        results = run_ranking_sensitivity_analysis(corridors)
        assert len(results) == 4

        for item in results:
            assert "corridor_index" in item
            assert "mean_rank" in item
            assert "rank_std" in item
            assert "max_rank_shift" in item
            assert "stability_index" in item
            assert "is_stable" in item
            assert 0.0 <= item["stability_index"] <= 1.0

        # Corridor 0 (all high) should be rank 1 across all scenarios, hence rank_std == 0.0 and stability == 1.0
        c0 = results[0]
        assert c0["rank_std"] == 0.0
        assert c0["stability_index"] == 1.0
        assert c0["is_stable"] is True

        # Corridor 1 or 2 (single spikes) should have non-zero rank standard deviation
        c1 = results[1]
        assert c1["max_rank_shift"] >= 1
