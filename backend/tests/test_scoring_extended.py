"""
Unit and Integration Tests for VanSetu Scoring Engine:
- Configurable weights and dynamic reweighting on missing data
- Distinct outputs: priority score, feasibility, confidence, walkability
- Pre-defined policy scenarios
- Edge cases and proxy handlers
"""

import pytest
import numpy as np
from app.services.scoring_service import (
    compute_priority,
    evaluate_corridor_scenarios,
    pedestrian_proxy,
    cost_impact_proxy,
    health_risk_proxy,
    vulnerable_population_proxy,
    park_connectivity_proxy,
    clean_highway_tag,
    compute_10factor_priority,
    DEFAULT_WEIGHTS,
    SCENARIOS,
    HIGHWAY_PROFILES,
)


class TestConfigurableWeightsAndReweighting:
    """Test dynamic weight normalization when indicators are missing."""

    def test_all_indicators_present(self):
        """When all indicators are present, output active_weights match input weights."""
        res = compute_priority(
            heat_norm=0.7,
            ndvi_norm=0.2,  # green_deficit = 0.8
            aqi_norm=0.6,
            highway_type="secondary",
            lon=77.2,
            lat=28.6,
        )
        assert 0.0 <= res["score"] <= 1.0
        assert 0.0 <= res["feasibility"] <= 1.0
        assert 0.0 <= res["confidence"] <= 1.0
        assert res["is_walkable"] is True

        # Check weights sum to 1.0
        active_w = res["active_weights"]
        assert pytest.approx(sum(active_w.values()), rel=1e-3) == 1.0
        assert "heat" in active_w
        assert "green_deficit" in active_w
        assert "pollution" in active_w

    def test_missing_heat_indicator_reweights_dynamically(self):
        """Missing heat must NOT be coerced to 0.0; remaining indicators are re-normalized."""
        res_with_heat = compute_priority(
            heat_norm=0.8,
            ndvi_norm=0.2,
            aqi_norm=0.8,
            highway_type="tertiary",
        )
        res_missing_heat = compute_priority(
            heat_norm=None,
            ndvi_norm=0.2,
            aqi_norm=0.8,
            highway_type="tertiary",
        )

        assert "heat" not in res_missing_heat["active_weights"]
        assert pytest.approx(sum(res_missing_heat["active_weights"].values()), rel=1e-3) == 1.0
        assert any("Thermal data missing" in w for w in res_missing_heat["data_warnings"])
        # Confidence must be penalized for missing thermal data
        assert res_missing_heat["confidence"] < res_with_heat["confidence"]

    def test_custom_scenario_weights(self):
        """Custom policy scenarios change the priority scores accordingly."""
        corridor_data = {
            "heat_norm": 0.9,     # very high heat
            "ndvi_norm": 0.8,     # low green deficit = 0.2
            "aqi_norm": 0.2,      # low pollution
            "highway_type": "tertiary",
        }
        res_balanced = compute_priority(**corridor_data, custom_weights=SCENARIOS["balanced"])
        res_heat_focus = compute_priority(**corridor_data, custom_weights=SCENARIOS["heat_resilience"])
        res_aqi_focus = compute_priority(**corridor_data, custom_weights=SCENARIOS["air_quality_focus"])

        # Heat resilience scenario puts 40% weight on heat vs 15% in aqi_focus
        assert res_heat_focus["score"] > res_balanced["score"]
        assert res_heat_focus["score"] > res_aqi_focus["score"]

    def test_nan_inputs_handled_safely(self):
        """NaN values are treated as missing without raising exceptions."""
        res = compute_priority(
            heat_norm=float("nan"),
            ndvi_norm=float("nan"),
            aqi_norm=0.5,
            highway_type="tertiary",
        )
        assert not np.isnan(res["score"])
        assert "heat" not in res["active_weights"]
        assert "green_deficit" not in res["active_weights"]
        assert "pollution" in res["active_weights"]


class TestDistinctEvaluativeVectors:
    """Verify distinct outputs: Priority, Feasibility, Confidence, and Walkability."""

    def test_motorway_is_non_walkable_with_low_feasibility(self):
        """Motorways/expressways have high barriers for pedestrian green corridors."""
        res = compute_priority(
            heat_norm=0.9,
            ndvi_norm=0.1,
            aqi_norm=0.9,
            highway_type="motorway",
        )
        assert res["is_walkable"] is False
        assert res["feasibility"] < 0.15
        assert any("not pedestrian-friendly" in w for w in res["data_warnings"])

    def test_pedestrian_street_has_high_feasibility(self):
        """Pedestrian zones have high walkability and high feasibility."""
        res = compute_priority(
            heat_norm=0.5,
            ndvi_norm=0.5,
            aqi_norm=0.5,
            highway_type="pedestrian",
        )
        assert res["is_walkable"] is True
        assert res["feasibility"] >= 0.85

    def test_aqi_distance_penalty_on_confidence(self):
        """Corridors far from AQI monitoring stations incur confidence penalty."""
        res_near = compute_priority(
            heat_norm=0.5, ndvi_norm=0.5, aqi_norm=0.5, aqi_distance_km=2.0
        )
        res_far = compute_priority(
            heat_norm=0.5, ndvi_norm=0.5, aqi_norm=0.5, aqi_distance_km=15.0
        )
        assert res_far["confidence"] < res_near["confidence"]
        assert any("Nearest AQI station is 15.0 km away" in w for w in res_far["data_warnings"])


class TestProxiesAndHelpers:
    """Test individual domain proxies and helpers."""

    def test_clean_highway_tag(self):
        assert clean_highway_tag("residential") == "residential"
        assert clean_highway_tag("['primary', 'secondary']") == "primary"
        assert clean_highway_tag(None) == "tertiary"
        assert clean_highway_tag("unknown_type") == "tertiary"

    def test_pedestrian_proxy(self):
        assert pedestrian_proxy("pedestrian") > pedestrian_proxy("motorway")
        assert pedestrian_proxy("footway") > pedestrian_proxy("trunk")

    def test_cost_impact_proxy(self):
        assert cost_impact_proxy("pedestrian") > cost_impact_proxy("motorway")

    def test_health_risk_interaction(self):
        # Zero heat or pollution yields zero compound risk
        assert health_risk_proxy(0.0, 0.9) == 0.0
        assert health_risk_proxy(0.9, 0.0) == 0.0
        # High heat and high pollution yields elevated compound risk
        assert health_risk_proxy(0.8, 0.8) > 0.8

    def test_vulnerable_population_zones(self):
        # Chandni Chowk coordinates (28.6353, 77.2250) should return high vulnerability
        v_high = vulnerable_population_proxy(77.2250, 28.6353)
        assert v_high >= 0.80

        # Remote generic location should return baseline urban vulnerability
        v_base = vulnerable_population_proxy(77.0000, 28.4000)
        assert v_base <= 0.40

    def test_backward_compatible_wrapper(self):
        score = compute_10factor_priority(
            heat_norm=0.6,
            ndvi_norm=0.4,
            aqi_norm=0.5,
            highway_type="tertiary"
        )
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
