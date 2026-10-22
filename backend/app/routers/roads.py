"""
Roads Router — Walkable Road network, Priority Corridors, and Sensitivity Analysis.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import json
import math

from app.dependencies import get_raster_service, get_road_service, get_aqi_service
from app.services.raster_service import RasterService
from app.services.road_service import RoadService
from app.services.aqi_service import AQIService
from app.services.intervention_service import enrich_geojson_corridors
from app.services.prune_service import explain_corridor_ranking, run_vansetu_ai_agent
from app.services.scoring_service import (
    SCENARIOS,
    DEFAULT_WEIGHTS,
    run_ranking_sensitivity_analysis,
)

router = APIRouter()


@router.get("/roads")
async def get_roads(
    include_aqi: bool = Query(default=True, description="Include AQI data in response"),
    scenario: Optional[str] = Query(default="balanced", description="Weight scenario (balanced, heat_resilience, air_quality_focus, pedestrian_equity, extreme_vulnerability)"),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Get walkable road network as GeoJSON with multi-criteria priority, feasibility, and confidence scores.
    """
    try:
        custom_weights = SCENARIOS.get(scenario, DEFAULT_WEIGHTS)
        if include_aqi:
            roads = road_service.sample_with_aqi(raster_service, aqi_service, custom_weights=custom_weights)
        else:
            roads = road_service.sample_gdi_along_roads(raster_service)

        geojson = road_service.roads_to_geojson(roads)

        return {
            "type": "FeatureCollection",
            "features": geojson.get("features", []),
            "metadata": {
                "count": len(geojson.get("features", [])),
                "source": "OpenStreetMap_Delhi_Walkable_Network",
                "scenario": scenario,
                "weights_used": custom_weights,
                "scoring_method": "multi-criteria-6factor" if include_aqi else "gdi-only"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roads/simple")
async def get_roads_simple(
    road_service: RoadService = Depends(get_road_service)
) -> Dict[str, Any]:
    """Get raw road geometries without raster sampling (fastest for base map rendering)."""
    try:
        roads = road_service.fetch_roads()
        geojson = road_service.roads_to_geojson(roads)
        return {
            "type": "FeatureCollection",
            "features": geojson.get("features", []),
            "metadata": {
                "count": len(geojson.get("features", [])),
                "source": "OpenStreetMap_Delhi_Walkable_Network"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corridors")
async def get_corridors(
    percentile: float = Query(default=85, description="Percentile threshold (default 85 = top 15% priority)"),
    scenario: Optional[str] = Query(default="balanced", description="Policy weight scenario"),
    include_aqi: bool = Query(default=True, description="Use multi-criteria scoring with AQI"),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Get prioritized VanSetu corridors as GeoJSON with feasibility, confidence,
    suitability recommendations, and itemized lifecycle costs.
    """
    try:
        custom_weights = SCENARIOS.get(scenario, DEFAULT_WEIGHTS)

        corridors = road_service.detect_corridors(
            raster_service,
            percentile=percentile,
            aqi_service=aqi_service if include_aqi else None,
            custom_weights=custom_weights,
        )

        geojson = road_service.roads_to_geojson(corridors)
        enriched_geojson = enrich_geojson_corridors(geojson)
        features = enriched_geojson.get("features", [])

        priority_values = [
            f["properties"].get("priority_score") or f["properties"].get("gdi_mean") or 0
            for f in features if f.get("properties")
        ]
        priority_min = min(priority_values) if priority_values else 0.0
        priority_max = max(priority_values) if priority_values else 1.0

        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "count": len(features),
                "percentile_threshold": percentile,
                "scenario": scenario,
                "weights_used": custom_weights,
                "priority_min": round(priority_min, 3),
                "priority_max": round(priority_max, 3),
                "description": f"Top {100-percentile:.0f}% high-priority walkable corridors",
                "outputs_distinction": {
                    "priority": "Community intervention need driven by environmental heat and vulnerability",
                    "feasibility": "Physical & geometric ability to implement without major land acquisition",
                    "confidence": "Data reliability discount based on sensor resolution and station distance"
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corridors/priority-ranking")
async def get_priority_ranking(
    percentile: float = Query(default=85, description="Percentile threshold"),
    scenario: Optional[str] = Query(default="balanced", description="Policy weight scenario"),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Ranked corridor listing with detailed indicator breakdowns, feasibility, and costs.
    """
    try:
        res = await get_corridors(
            percentile=percentile,
            scenario=scenario,
            include_aqi=True,
            road_service=road_service,
            raster_service=raster_service,
            aqi_service=aqi_service
        )
        features = res.get("features", [])

        corridors_list = []
        for rank, f in enumerate(features, 1):
            p = f.get("properties", {})
            corridors_list.append({
                "rank": rank,
                "id": p.get("id"),
                "name": p.get("name", "Unnamed Corridor"),
                "district": p.get("district", "NCT of Delhi"),
                "highway": p.get("highway", "secondary"),
                "priority_score": p.get("priority_score"),
                "feasibility": p.get("feasibility"),
                "confidence": p.get("confidence"),
                "length_meters": p.get("length_meters"),
                "primary_intervention": p.get("corridor_type"),
                "recommendations": p.get("recommended_interventions", []),
                "lifecycle_costs": p.get("lifecycle_costs", {}),
                "signals": p.get("priority_signals", {}),
                "active_weights": p.get("active_weights", {}),
                "data_warnings": p.get("data_warnings", []),
                "selection_rationale": p.get("selection_rationale")
            })

        return {
            "corridors": corridors_list,
            "ranked_corridors": corridors_list,
            "total_corridors": len(corridors_list),
            "scenario": scenario,
            "available_scenarios": list(SCENARIOS.keys())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corridors/rank")
async def rank_corridors_what_if(
    heat_weight: Optional[str] = Query(
        default=None,
        description="Required weight for Heat in [0.0, 1.0]. Formula: score = heat_weight * Heat + (1 - heat_weight) * (1 - NDVI)",
    ),
    top: Optional[str] = Query(
        default="5",
        description="Number of top corridors to return (default 5, range 1..100)",
    ),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
) -> Dict[str, Any]:
    """
    What-if Corridor Ranking endpoint:
      GET /api/corridors/rank?heat_weight=0.6&top=5

    Computes for each corridor with valid raster measurements:
      score = heat_weight * Heat + (1 - heat_weight) * (1 - NDVI)
    where Heat and NDVI are normalized [0, 1] values sampled from valid raster pixels.
    Also returns Baseline (heat_weight = 0.6) vs. What-if rank and score comparisons.
    """
    if heat_weight is None or str(heat_weight).strip() == "":
        raise HTTPException(
            status_code=422,
            detail="Missing required query parameter 'heat_weight'. Provide a finite number between 0.0 and 1.0 (e.g., ?heat_weight=0.6&top=5).",
        )

    try:
        hw_val = float(str(heat_weight).strip())
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid 'heat_weight' value '{heat_weight}'. Must be a valid number between 0.0 and 1.0.",
        )

    if not math.isfinite(hw_val):
        raise HTTPException(
            status_code=422,
            detail="Invalid 'heat_weight': NaN or Infinity is not allowed. Must be a finite number between 0.0 and 1.0.",
        )

    if hw_val < 0.0 or hw_val > 1.0:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid 'heat_weight' ({hw_val}). Must be between 0.0 and 1.0 inclusive.",
        )

    top_str = "5" if top is None or str(top).strip() == "" else str(top).strip()
    try:
        # Reject floats like "3.5"
        if "." in top_str:
            raise ValueError("top must be an integer")
        top_val = int(top_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid 'top' value '{top}'. Must be a positive integer between 1 and 100.",
        )

    if top_val < 1 or top_val > 100:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid 'top' ({top_val}). Must be between 1 and 100 inclusive.",
        )

    try:
        result = road_service.rank_corridors_what_if(
            raster_service=raster_service,
            heat_weight=hw_val,
            top=top_val,
            baseline_heat_weight=0.6,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corridors/sensitivity")
async def get_sensitivity_analysis(
    percentile: float = Query(default=85, description="Percentile threshold"),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Run multi-scenario sensitivity analysis across corridors.
    Computes ranking stability index and highlights corridors whose priority shifts dramatically.
    """
    try:
        corridors = road_service.detect_corridors(
            raster_service,
            percentile=percentile,
            aqi_service=aqi_service,
        )
        geojson = road_service.roads_to_geojson(corridors)
        features = geojson.get("features", [])

        sensitivity_results = run_ranking_sensitivity_analysis(features)

        # Merge results into output
        output_items = []
        for i, item in enumerate(features):
            props = item.get("properties", {})
            sens = sensitivity_results[i] if i < len(sensitivity_results) else {}
            output_items.append({
                "id": props.get("id"),
                "name": props.get("name"),
                "district": props.get("district"),
                "baseline_priority": props.get("priority_score"),
                "mean_rank": sens.get("mean_rank"),
                "rank_std": sens.get("rank_std"),
                "max_rank_shift": sens.get("max_rank_shift"),
                "stability_index": sens.get("stability_index"),
                "is_stable": sens.get("is_stable"),
                "scenario_ranks": sens.get("scenario_ranks", {})
            })

        output_items.sort(key=lambda x: x.get("stability_index", 0.0))

        return {
            "corridor_count": len(output_items),
            "scenarios_evaluated": list(SCENARIOS.keys()),
            "stability_summary": {
                "stable_corridors_count": sum(1 for c in output_items if c.get("is_stable")),
                "volatile_corridors_count": sum(1 for c in output_items if not c.get("is_stable")),
                "note": "Corridors with stability_index < 0.70 have priority rankings sensitive to policy weight assumptions."
            },
            "corridors": output_items
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ExplainRankingRequest(BaseModel):
    id: Optional[str] = "corridor"
    name: Optional[str] = "Unnamed Corridor"
    district: Optional[str] = "NCT of Delhi"
    highway: Optional[str] = "secondary"
    priority_score: float = Field(default=0.5, ge=0.0, le=1.0)
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    heat: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    ndvi: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    green_deficit: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    heat_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    green_deficit_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    heat_contribution: Optional[float] = None
    green_deficit_contribution: Optional[float] = None
    rank: Optional[int] = None
    baseline_rank: Optional[int] = None
    rank_change: Optional[int] = None
    baseline_score: Optional[float] = None
    feasibility: Optional[float] = 0.6
    confidence: Optional[float] = 0.7
    scenario: Optional[str] = "balanced"
    signals: Optional[Dict[str, float]] = None
    active_weights: Optional[Dict[str, float]] = None


@router.post("/corridors/explain-ranking", tags=["AI Explanation"])
async def explain_ranking_endpoint(
    request_body: ExplainRankingRequest
) -> Dict[str, Any]:
    """
    Isolated 'Explain This Ranking' endpoint using Google Gemini through the Prune AI Gateway.
    Decoupled from spatial queries to ensure interactive ranking updates remain instantaneous.
    """
    try:
        data = request_body.model_dump()
        result = await explain_corridor_ranking(data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


ALLOWED_WEIGHT_FACTORS = {
    "lst", "ndvi_deficit", "aqi", "ped_exposure", "vulnerable_pop", "green_access",
    "heat", "pollution", "green_deficit", "pedestrian", "health_risk",
}

WEIGHT_FACTOR_TO_SCORING_KEY = {
    "lst": "heat",
    "heat": "heat",
    "ndvi_deficit": "green_deficit",
    "green_deficit": "green_deficit",
    "aqi": "pollution",
    "pollution": "pollution",
    "ped_exposure": "pedestrian",
    "pedestrian": "pedestrian",
    "green_access": "health_risk",
    "health_risk": "health_risk",
    "vulnerable_pop": "vulnerable_pop",
}


class ProfessionalRankRequest(BaseModel):
    weights: Dict[str, float] = Field(
        default_factory=lambda: dict(DEFAULT_WEIGHTS),
        description="Custom multi-criteria weights (lst, ndvi_deficit, aqi, ped_exposure, vulnerable_pop, green_access). Must be non-negative and sum to 1.0 (±0.01) or 100 (±1.0).",
    )
    constraints: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="User-supplied field feasibility constraints (footpath_width_m, budget_lakhs, utility_conflict, access_restriction, maintenance_capacity)",
    )
    top: int = Field(default=10, ge=1, le=100)


@router.post("/corridors/professional-rank", tags=["Professional Mode"])
async def professional_rank_endpoint(
    request_body: ProfessionalRankRequest,
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service),
) -> Dict[str, Any]:
    """
    Professional Mode (Van Setu Pro) custom multi-criteria corridor ranking and feasibility assessment.
    Validates that all weights are finite, non-negative, and sum to 1.0 (±0.01) or 100% (±1.0%).
    """
    raw_weights = request_body.weights or {}
    if not raw_weights:
        raise HTTPException(status_code=422, detail="Custom weights dictionary cannot be empty.")

    cleaned_weights: Dict[str, float] = {}
    for k, v in raw_weights.items():
        if k not in ALLOWED_WEIGHT_FACTORS:
            raise HTTPException(
                status_code=422,
                detail=f"Unrecognized multi-criteria factor key '{k}'. Allowed keys are: lst, ndvi_deficit, aqi, ped_exposure, vulnerable_pop, green_access.",
            )
        try:
            fv = float(v)
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail=f"Invalid weight for '{k}': must be numeric.")
        if not math.isfinite(fv) or fv < 0.0:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid weight for '{k}' ({v}): weights must be finite and non-negative (>= 0).",
            )
        scoring_key = WEIGHT_FACTOR_TO_SCORING_KEY[k]
        cleaned_weights[scoring_key] = cleaned_weights.get(scoring_key, 0.0) + fv

    total_sum = sum(cleaned_weights.values())
    # Allow either normalized [0..1] summing to ~1.0 OR percentage [0..100] summing to ~100.0
    if abs(total_sum - 100.0) <= 1.0:
        cleaned_weights = {k: v / 100.0 for k, v in cleaned_weights.items()}
        total_sum = sum(cleaned_weights.values())

    if abs(total_sum - 1.0) > 0.02:
        raise HTTPException(
            status_code=422,
            detail=f"Custom multi-criteria weights must sum to 1.0 (100%). Current sum is {total_sum:.4f}.",
        )

    try:
        return road_service.rank_corridors_professional(
            raster_service=raster_service,
            aqi_service=aqi_service,
            weights=cleaned_weights,
            top=request_body.top,
            user_constraints=request_body.constraints or {},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AIAgentRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=1500, description="User instruction or question for Van Setu AI Action Agent")
    context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Current studio state (mode, scenario, heat_weight, top, selected_corridor, corridors)",
    )


@router.post("/corridors/ai-agent", tags=["AI Action Agent"])
async def ai_agent_endpoint(
    request_body: AIAgentRequest,
) -> Dict[str, Any]:
    """
    Van Setu AI Action Agent endpoint.
    Parses natural-language studio instructions into validated, typed actions and generates an grounded explanation.
    """
    try:
        ctx = dict(request_body.context or {})
        if "corridors" in ctx and "available_corridors" not in ctx:
            ctx["available_corridors"] = ctx["corridors"]
        res = await run_vansetu_ai_agent(
            user_message=request_body.prompt,
            context=ctx,
        )
        # Ensure both 'reply' and 'explanation' are populated for callers
        if "reply" in res and "explanation" not in res:
            res["explanation"] = res["reply"]
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


