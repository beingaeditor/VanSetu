"""
Corridors Router — Point-Based Corridor Aggregation Endpoints

This router provides READ-ONLY endpoints for the corridor aggregation feature.
It does NOT modify existing endpoints or point data.

ENDPOINTS:
- GET /corridors/aggregated - Get all aggregated corridors
- GET /corridors/aggregated/{id} - Get specific corridor with point details
- GET /corridors/points - Get high-priority points used for aggregation

DESIGN NOTES:
- Corridors are derived from existing high-priority points
- Points are preserved - corridors reference them, not replace them
- D_max and N_min are configurable via query parameters
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, Optional

from app.dependencies import (
    get_raster_service, 
    get_road_service, 
    get_aqi_service,
    get_corridor_service
)
from app.services.raster_service import RasterService
from app.services.road_service import RoadService
from app.services.aqi_service import AQIService
from app.services.corridor_service import CorridorService

router = APIRouter()


@router.get("/corridors/aggregated")
async def get_aggregated_corridors(
    d_max: float = Query(
        default=30.0, 
        description="Maximum connection distance in meters. Two points are connected if distance ≤ D_max. Default 30m matches street-scale continuity.",
        ge=5.0,
        le=200.0
    ),
    n_min: int = Query(
        default=5, 
        description="Minimum number of points to form a valid corridor. Smaller groups remain as individual points.",
        ge=2,
        le=50
    ),
    percentile: float = Query(
        default=85, 
        description="Percentile threshold for high-priority points (default 85 = top 15%)",
        ge=50,
        le=99
    ),
    corridor_service: CorridorService = Depends(get_corridor_service),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Get aggregated high-exposure corridors as GeoJSON.
    
    This endpoint implements POINT-BASED CORRIDOR AGGREGATION:
    1. Takes existing high-priority road segments
    2. Converts them to points (segment centroids)
    3. Connects spatially continuous points into corridors
    4. Returns corridors with derived metadata
    
    KEY PRINCIPLES:
    - Points are NEVER deleted or merged
    - Corridors reference points, not replace them
    - Each point belongs to at most one corridor
    - Results are deterministic and reproducible
    
    CORRIDOR DEFINITION:
    A corridor is a connected chain of nearby high-priority points
    representing a continuous path of human exposure.
    
    Args:
        d_max: Maximum connection distance in meters (default: 30m)
        n_min: Minimum points for valid corridor (default: 5)
        percentile: Percentile threshold for high-priority points
        
    Returns:
        GeoJSON FeatureCollection with corridor geometries and metadata
    """
    try:
        # Get road segments with multi-exposure priority
        roads = road_service.sample_with_aqi(raster_service, aqi_service)
        road_geojson = road_service.roads_to_geojson(roads)
        
        # Aggregate into corridors
        result = corridor_service.get_corridors_from_road_segments(
            road_geojson,
            d_max_meters=d_max,
            n_min=n_min,
            percentile_threshold=percentile
        )
        
        # Convert to GeoJSON
        corridors_geojson = corridor_service.corridors_to_geojson(result['corridors'])
        
        return {
            "type": "FeatureCollection",
            "features": corridors_geojson.get("features", []),
            "metadata": {
                **result['metadata'],
                "description": "Point-based corridor aggregation - spatially continuous high-exposure paths",
                "algorithm": "Distance-based connectivity with connected component extraction",
                "note": "Corridors reference points, they do not replace them"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corridors/aggregated/{corridor_id}")
async def get_corridor_detail(
    corridor_id: str,
    include_points: bool = Query(
        default=True,
        description="Include full point details in response"
    ),
    corridor_service: CorridorService = Depends(get_corridor_service)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific corridor.
    
    Returns:
        - Full corridor metadata
        - List of point IDs
        - Optionally, full point details
    """
    try:
        corridor = corridor_service.get_corridor_by_id(corridor_id)
        
        if corridor is None:
            raise HTTPException(
                status_code=404, 
                detail=f"Corridor {corridor_id} not found. Make sure to call /corridors/aggregated first."
            )
        
        response = {
            "corridor": corridor,
            "geometry": corridor['geometry'],
            "summary": {
                "num_points": corridor['num_points'],
                "mean_priority": corridor.get('mean_priority'),
                "dominant_exposure": corridor.get('dominant_exposure'),
                "corridor_length_m": corridor.get('corridor_length_m')
            }
        }
        
        if include_points:
            points = corridor_service.get_points_for_corridor(corridor_id)
            response["points"] = points
            response["points_geojson"] = corridor_service.points_to_geojson(points)
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corridors/points")
async def get_corridor_points(
    percentile: float = Query(
        default=85, 
        description="Percentile threshold for high-priority points"
    ),
    include_all: bool = Query(
        default=False,
        description="Include all points, not just high-priority ones"
    ),
    corridor_service: CorridorService = Depends(get_corridor_service),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Get high-priority points used for corridor aggregation as GeoJSON.
    
    These are the INPUT points to the corridor aggregation algorithm.
    Each point represents the centroid of a high-priority road segment.
    
    WHY POINTS ARE PRESERVED:
    - Original point data is ground truth
    - Corridors are an abstraction layer on top
    - Points may belong to corridors or remain isolated
    - No point is ever deleted or modified
    
    Args:
        percentile: Percentile threshold for high-priority points
        include_all: If true, include all points (not just high-priority)
        
    Returns:
        GeoJSON FeatureCollection with point geometries
    """
    try:
        # Get road segments with multi-exposure priority
        roads = road_service.sample_with_aqi(raster_service, aqi_service)
        road_geojson = road_service.roads_to_geojson(roads)
        
        # Get points from corridor service (this also caches them)
        result = corridor_service.get_corridors_from_road_segments(
            road_geojson,
            percentile_threshold=percentile
        )
        
        # Choose which points to return
        if include_all:
            points = result.get('all_points', [])
        else:
            points = result.get('points', [])
        
        # Convert to GeoJSON
        points_geojson = corridor_service.points_to_geojson(points)
        
        return {
            "type": "FeatureCollection",
            "features": points_geojson.get("features", []),
            "metadata": {
                "total_points": len(points),
                "percentile_threshold": percentile,
                "include_all": include_all,
                "description": "High-priority points derived from road segment centroids"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corridors/stats")
async def get_corridor_stats(
    corridor_service: CorridorService = Depends(get_corridor_service)
) -> Dict[str, Any]:
    """
    Get statistics about the current corridor aggregation.
    
    Returns summary statistics without full geometry data.
    """
    try:
        if corridor_service._corridors_cache is None:
            return {
                "status": "no_data",
                "message": "No corridors computed yet. Call /corridors/aggregated first."
            }
        
        corridors = corridor_service._corridors_cache
        
        # Compute statistics
        priorities = [c['mean_priority'] for c in corridors if c.get('mean_priority')]
        lengths = [c['corridor_length_m'] for c in corridors if c.get('corridor_length_m')]
        point_counts = [c['num_points'] for c in corridors]
        
        # Exposure type distribution
        exposure_counts = {}
        for c in corridors:
            exp = c.get('dominant_exposure', 'unknown')
            exposure_counts[exp] = exposure_counts.get(exp, 0) + 1
        
        return {
            "status": "computed",
            "total_corridors": len(corridors),
            "statistics": {
                "priority": {
                    "mean": float(sum(priorities) / len(priorities)) if priorities else None,
                    "min": float(min(priorities)) if priorities else None,
                    "max": float(max(priorities)) if priorities else None
                },
                "length_m": {
                    "mean": float(sum(lengths) / len(lengths)) if lengths else None,
                    "min": float(min(lengths)) if lengths else None,
                    "max": float(max(lengths)) if lengths else None,
                    "total": float(sum(lengths)) if lengths else None
                },
                "points_per_corridor": {
                    "mean": float(sum(point_counts) / len(point_counts)) if point_counts else None,
                    "min": min(point_counts) if point_counts else None,
                    "max": max(point_counts) if point_counts else None,
                    "total": sum(point_counts)
                }
            },
            "exposure_distribution": exposure_counts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
