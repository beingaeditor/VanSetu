"""
Unit and Integration Tests for VanSetu Intervention Suitability & Lifecycle Costing:
- Catalog schema integrity
- Multi-criteria suitability rules
- Grounded CPWD/DPGS lifecycle cost models
- Site checks, constraints, alternatives, and missing evidence
- Post-implementation monitoring framework
"""

import pytest
from app.services.intervention_service import (
    INTERVENTION_CATALOG,
    evaluate_suitability,
    calculate_corridor_lifecycle_costs,
    generate_monitoring_framework,
    enrich_corridor_with_interventions,
    enrich_geojson_corridors,
    get_subsidy_info,
)


class TestInterventionCatalogIntegrity:
    """Validate catalog completeness and schema conformity."""

    REQUIRED_TYPES = [
        "street_trees_canopy",
        "shade_structures_waiting",
        "water_sensitive_infrastructure",
        "vertical_greenery_facades",
        "cool_pavements_surfaces",
    ]

    def test_catalog_contains_all_five_intervention_types(self):
        for itype in self.REQUIRED_TYPES:
            assert itype in INTERVENTION_CATALOG, f"Missing {itype} in catalog"

    def test_catalog_entries_have_required_metadata(self):
        for itype, spec in INTERVENTION_CATALOG.items():
            assert "name" in spec
            assert "category" in spec
            assert "icon" in spec
            assert "constraints" in spec and len(spec["constraints"]) > 0
            assert "required_site_checks" in spec and len(spec["required_site_checks"]) > 0
            assert "feasible_alternatives" in spec and len(spec["feasible_alternatives"]) > 0
            assert "cost_model" in spec

            cm = spec["cost_model"]
            assert cm["capex_inr"] > 0
            assert cm["annual_opex_inr"] > 0
            assert cm["five_year_lifecycle_cost_inr"] > 0
            assert cm["expected_service_life_yrs"] > 0


class TestSuitabilityDecisionMatrix:
    """Test multi-criteria suitability rules under varying spatial conditions."""

    def test_street_trees_suitable_on_wide_heat_stressed_corridor(self):
        """Street trees selected for wide right-of-way with high thermal and green deficit."""
        recs = evaluate_suitability(
            priority=0.8,
            feasibility=0.7,
            heat_norm=0.75,
            green_deficit=0.85,
            aqi_norm=0.5,
            pedestrian_score=0.6,
            vulnerable_score=0.5,
            highway_type="secondary",
            estimated_width_m=18.0,
        )
        rec_ids = [r["id"] for r in recs]
        assert "street_trees_canopy" in rec_ids
        tree_rec = next(r for r in recs if r["id"] == "street_trees_canopy")
        assert tree_rec["suitability_score"] >= 0.70
        assert "continuous canopy" in tree_rec["rationale"]
        assert len(tree_rec["required_site_checks"]) > 0
        assert len(tree_rec["constraints"]) > 0
        assert len(tree_rec["feasible_alternatives"]) > 0

    def test_vertical_greenery_triggered_on_narrow_polluted_alley(self):
        """Vertical greenery recommended when street width is too narrow for standard trees."""
        recs = evaluate_suitability(
            priority=0.75,
            feasibility=0.6,
            heat_norm=0.5,
            green_deficit=0.8,
            aqi_norm=0.85,
            pedestrian_score=0.7,
            vulnerable_score=0.6,
            highway_type="pedestrian",
            estimated_width_m=4.0,  # Narrow alley
        )
        rec_ids = [r["id"] for r in recs]
        assert "vertical_greenery_facades" in rec_ids

    def test_shade_structures_triggered_on_high_pedestrian_exposure(self):
        """Immediate shade structures selected for high footfall exposure."""
        recs = evaluate_suitability(
            priority=0.85,
            feasibility=0.8,
            heat_norm=0.8,
            green_deficit=0.5,
            aqi_norm=0.4,
            pedestrian_score=0.9,
            vulnerable_score=0.8,
            highway_type="tertiary",
            estimated_width_m=12.0,
        )
        rec_ids = [r["id"] for r in recs]
        assert "shade_structures_waiting" in rec_ids
        shade_rec = next(r for r in recs if r["id"] == "shade_structures_waiting")
        assert "zero-latency shade" in shade_rec["rationale"]

    def test_bioswales_triggered_on_wide_arterial(self):
        """Bioswales triggered when corridor is wide enough (>=12m)."""
        recs = evaluate_suitability(
            priority=0.7,
            feasibility=0.75,
            heat_norm=0.6,
            green_deficit=0.6,
            aqi_norm=0.4,
            pedestrian_score=0.5,
            vulnerable_score=0.4,
            highway_type="primary",
            estimated_width_m=24.0,
        )
        rec_ids = [r["id"] for r in recs]
        assert "water_sensitive_infrastructure" in rec_ids


class TestLifecycleCosting:
    """Test cost estimation scaling and consistency."""

    def test_lifecycle_cost_scales_linearly_with_length(self):
        recs = [INTERVENTION_CATALOG["street_trees_canopy"]]

        cost_1km = calculate_corridor_lifecycle_costs(recs, length_meters=1000.0)
        cost_2km = calculate_corridor_lifecycle_costs(recs, length_meters=2000.0)

        assert cost_1km["corridor_length_km"] == 1.0
        assert cost_2km["corridor_length_km"] == 2.0

        assert pytest.approx(cost_2km["capex_inr"], rel=1e-3) == cost_1km["capex_inr"] * 2.0
        assert pytest.approx(cost_2km["annual_opex_inr"], rel=1e-3) == cost_1km["annual_opex_inr"] * 2.0
        assert pytest.approx(cost_2km["five_year_lifecycle_inr"], rel=1e-3) == cost_1km["five_year_lifecycle_inr"] * 2.0
        assert cost_1km["currency"] == "INR (₹)"
        assert len(cost_1km["cost_assumptions"]) >= 3


class TestMonitoringFrameworkAndEnrichment:
    """Test monitoring schema contract and GeoJSON enrichment."""

    def test_monitoring_framework_structure(self):
        mf = generate_monitoring_framework(
            corridor_id="corridor_42",
            baseline_heat=0.7,
            baseline_ndvi=0.2,
            baseline_aqi=0.6,
        )
        assert mf["corridor_id"] == "corridor_42"
        assert "baseline_recorded" in mf
        assert "target_milestones" in mf
        assert "year_1" in mf["target_milestones"]
        assert "year_3" in mf["target_milestones"]
        assert "year_5" in mf["target_milestones"]
        assert len(mf["verification_protocol"]) >= 3

    def test_corridor_enrichment(self):
        raw_corridor = {
            "id": "c_101",
            "name": "Chandni Chowk Main Road",
            "heat_norm": 0.8,
            "ndvi_norm": 0.1,
            "aqi_norm": 0.7,
            "priority_score": 0.85,
            "feasibility": 0.75,
            "pedestrian_score": 0.9,
            "highway": "secondary",
            "length_meters": 1200.0,
        }
        enriched = enrich_corridor_with_interventions(raw_corridor)

        assert "corridor_type" in enriched
        assert "interventions_detailed" in enriched
        assert "lifecycle_costs" in enriched
        assert "monitoring_framework" in enriched
        assert "severity_tier" in enriched
        assert enriched["severity_tier"] == "critical"
        assert enriched["subsidy_tier"] == "flagship"

    def test_geojson_featurecollection_enrichment(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": [[77.2, 28.6], [77.21, 28.61]]},
                    "properties": {
                        "id": "road_1",
                        "heat_norm": 0.6,
                        "ndvi_norm": 0.3,
                        "priority_score": 0.65,
                    }
                }
            ]
        }
        enriched_fc = enrich_geojson_corridors(fc)
        p = enriched_fc["features"][0]["properties"]
        assert "lifecycle_costs" in p
        assert "monitoring_framework" in p
