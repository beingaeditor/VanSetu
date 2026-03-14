"""
Roads Router — Road network and corridor endpoints.

Updated to support Multi-Exposure Priority scoring with AQI integration.
Includes intervention classification for corridor planning.
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from typing import Dict, Any

from app.dependencies import get_raster_service, get_road_service, get_aqi_service
from app.services.raster_service import RasterService
from app.services.road_service import RoadService
from app.services.aqi_service import AQIService
from app.services.intervention_service import enrich_geojson_corridors

router = APIRouter()


@router.get("/roads")
async def get_roads(
    include_aqi: bool = Query(default=True, description="Include AQI data in response"),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Get road network as GeoJSON with Multi-Exposure Priority scores.
    
    Returns GeoJSON FeatureCollection with road geometries and priority data.
    
    When include_aqi=true (default), each road segment includes:
    - gdi_mean: Original Green Deficit Index (backward compatibility)
    - heat_norm: Normalized temperature score [0, 1]
    - ndvi_norm: Normalized vegetation score [0, 1]
    - aqi_raw: Raw PM2.5 value from nearest station
    - aqi_norm: Normalized AQI score [0, 1]
    - priority_score: Multi-Exposure Priority (heat + green deficit + AQI)
    """
    try:
        if include_aqi:
            roads = road_service.sample_with_aqi(raster_service, aqi_service)
        else:
            roads = road_service.sample_gdi_along_roads(raster_service)
        
        geojson = road_service.roads_to_geojson(roads)
        
        return {
            "type": "FeatureCollection",
            "features": geojson.get("features", []),
            "metadata": {
                "count": len(geojson.get("features", [])),
                "source": "OpenStreetMap",
                "aqi_included": include_aqi,
                "scoring_method": "multi-exposure" if include_aqi else "gdi-only"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/roads/simple")
async def get_roads_simple(
    road_service: RoadService = Depends(get_road_service)
) -> Dict[str, Any]:
    """
    Get road network as GeoJSON (without GDI sampling).
    
    Faster endpoint for initial display.
    """
    try:
        roads = road_service.fetch_roads()
        geojson = road_service.roads_to_geojson(roads)
        
        return {
            "type": "FeatureCollection",
            "features": geojson.get("features", []),
            "metadata": {
                "count": len(geojson.get("features", [])),
                "source": "OpenStreetMap"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corridors")
async def get_corridors(
    percentile: float = Query(default=85, description="Percentile threshold (default 85 = top 15%)"),
    include_aqi: bool = Query(default=True, description="Use Multi-Exposure Priority scoring"),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Get high-priority VanSetu corridors as GeoJSON with intervention suggestions.
    
    When include_aqi=true (default), corridors are ranked by 6-factor Priority Index:
        Priority = (Heat × 0.25) + (Pollution × 0.20) + (Green Deficit × 0.20)
                 + (Pedestrian Density × 0.15) + (Health Risk Index × 0.12)
                 + (Vulnerable Pop. × 0.08)
    
    Each corridor includes:
    - corridor_type: Classification (heat_dominated, pollution_dominated, green_deficit, mixed_exposure)
    - recommended_interventions: List of suggested green infrastructure interventions
    - intervention_rationale: Human-readable explanation of why these interventions fit
    
    Args:
        percentile: Percentile threshold (default 85 = top 15%)
        include_aqi: Use AQI in priority scoring (default true)
        
    Returns GeoJSON with corridor segments, priority breakdown, and intervention suggestions.
    """
    try:
        if include_aqi:
            corridors = road_service.detect_corridors(raster_service, percentile, aqi_service)
            scoring_method = "multi-exposure"
        else:
            corridors = road_service.detect_corridors(raster_service, percentile)
            scoring_method = "gdi-only"
        
        geojson = road_service.roads_to_geojson(corridors)
        
        # Enrich corridors with intervention classification and suggestions
        enriched_geojson = enrich_geojson_corridors(geojson)
        
        # Compute priority range so frontend can normalize colors
        features = enriched_geojson.get("features", [])
        priority_values = [
            f["properties"].get("priority_score") or f["properties"].get("gdi_mean") or 0
            for f in features
            if f.get("properties")
        ]
        priority_min = min(priority_values) if priority_values else 0
        priority_max = max(priority_values) if priority_values else 1
        
        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "count": len(features),
                "percentile_threshold": percentile,
                "scoring_method": scoring_method,
                "description": f"Top {100-percentile:.0f}% highest priority road segments",
                "includes_interventions": True,
                "priority_min": priority_min,
                "priority_max": priority_max
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corridors/priority-ranking")
async def get_priority_ranking(
    percentile: float = Query(default=85, description="Percentile threshold (default 85 = top 15%)"),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Real-time Priority Ranking of corridors using the 6-factor Priority Index.

    Formula:
        Priority = (Heat × 0.25) + (Pollution × 0.20) + (Green Deficit × 0.20)
                 + (Pedestrian Density × 0.15) + (Health Risk Index × 0.12)
                 + (Vulnerable Pop. × 0.08)

    Returns corridors ranked from highest to lowest priority, with full
    per-signal breakdown showing which factors are driving each corridor's
    score and whether data comes from real-time sources or proxies.
    """
    from app.services.scoring_service import WEIGHTS

    try:
        corridors = road_service.detect_corridors(raster_service, percentile, aqi_service)

        if corridors is None or len(corridors) == 0:
            return {"ranked_corridors": [], "metadata": {"count": 0}}

        geojson = road_service.roads_to_geojson(corridors)
        enriched = enrich_geojson_corridors(geojson)
        features = enriched.get("features", [])

        ranked = []
        for feat in features:
            p = feat.get("properties", {})
            score = p.get("priority_score")
            if score is None:
                continue

            signals = p.get("priority_signals") or {}
            data_sources = p.get("priority_data_sources") or {}

            ranked.append({
                "name": p.get("name", "Unnamed Road"),
                "priority_score": round(score, 4),
                "signals": {k: round(v, 4) if v is not None else None for k, v in signals.items()} if signals else None,
                "data_sources": data_sources or None,
                "corridor_type": p.get("corridor_type", "unknown"),
                "severity_tier": p.get("severity_tier", "moderate"),
                "heat_norm": round(p.get("heat_norm", 0), 4) if p.get("heat_norm") is not None else None,
                "aqi_norm": round(p.get("aqi_norm", 0), 4) if p.get("aqi_norm") is not None else None,
                "ndvi_norm": round(p.get("ndvi_norm", 0), 4) if p.get("ndvi_norm") is not None else None,
                "geometry": feat.get("geometry"),
            })

        ranked.sort(key=lambda x: x["priority_score"], reverse=True)

        for i, item in enumerate(ranked):
            item["rank"] = i + 1

        return {
            "ranked_corridors": ranked,
            "metadata": {
                "count": len(ranked),
                "formula": "Priority = (Heat × 0.25) + (Pollution × 0.20) + (Green Deficit × 0.20) + (Pedestrian Density × 0.15) + (Health Risk Index × 0.12) + (Vulnerable Pop. × 0.08)",
                "weights": WEIGHTS,
                "data_freshness": "real-time",
                "percentile_threshold": percentile,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/roads/refresh")
async def refresh_roads(
    background_tasks: BackgroundTasks,
    road_service: RoadService = Depends(get_road_service)
):
    """
    Trigger a refresh of road data from OpenStreetMap.
    """
    road_service.clear_cache()

    # Fetch in background
    background_tasks.add_task(road_service.fetch_roads, True)

    return {"status": "ok", "message": "Road refresh initiated"}
