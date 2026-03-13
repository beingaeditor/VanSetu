"""
Statistics Router — Data statistics and analysis endpoints.

Updated to include AQI data in point queries.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, Optional

from app.dependencies import get_raster_service, get_aqi_service
from app.services.raster_service import RasterService
from app.services.aqi_service import AQIService, compute_multi_exposure_priority

router = APIRouter()


@router.get("/stats")
async def get_all_stats(
    raster_service: RasterService = Depends(get_raster_service)
) -> Dict[str, Any]:
    """
    Get statistics for all raster layers.
    """
    return {
        "ndvi": raster_service.get_statistics("ndvi"),
        "lst": raster_service.get_statistics("lst"),
        "gdi": raster_service.get_statistics("gdi"),
        "shape": raster_service.shape,
        "bounds": raster_service.bounds
    }


@router.get("/stats/{layer}")
async def get_layer_stats(
    layer: str,
    raster_service: RasterService = Depends(get_raster_service)
) -> Dict[str, Any]:
    """
    Get statistics for a specific layer.
    
    Args:
        layer: Layer name (ndvi, lst, gdi)
    """
    valid_layers = ['ndvi', 'lst', 'gdi']
    
    if layer.lower() not in valid_layers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid layer. Must be one of: {valid_layers}"
        )
    
    stats = raster_service.get_statistics(layer.lower())
    
    if not stats:
        raise HTTPException(status_code=404, detail="No statistics available")
    
    return {
        "layer": layer.lower(),
        "statistics": stats
    }


@router.get("/stats/{layer}/histogram")
async def get_layer_histogram(
    layer: str,
    bins: int = Query(default=50, ge=10, le=200),
    raster_service: RasterService = Depends(get_raster_service)
) -> Dict[str, Any]:
    """
    Get histogram data for a layer.
    
    Args:
        layer: Layer name (ndvi, lst, gdi)
        bins: Number of histogram bins (10-200)
    """
    valid_layers = ['ndvi', 'lst', 'gdi']
    
    if layer.lower() not in valid_layers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid layer. Must be one of: {valid_layers}"
        )
    
    histogram = raster_service.get_histogram(layer.lower(), bins)
    
    if not histogram:
        raise HTTPException(status_code=404, detail="No histogram data available")
    
    return {
        "layer": layer.lower(),
        "bins": bins,
        "histogram": histogram
    }


@router.get("/point")
async def get_point_values(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Get all layer values at a specific geographic point.
    
    Includes raster values (NDVI, LST, GDI) and AQI from nearest station.
    Also computes the Multi-Exposure Priority score.
    
    Args:
        lat: Latitude
        lng: Longitude
    """
    ndvi = raster_service.get_value_at_point("ndvi", lat, lng)
    lst = raster_service.get_value_at_point("lst", lat, lng)
    gdi = raster_service.get_value_at_point("gdi", lat, lng)
    
    # Get AQI from nearest station
    aqi_info = aqi_service.get_aqi_at_point(lng, lat)
    aqi_raw = aqi_info.get("aqi_raw")
    aqi_norm = aqi_info.get("aqi_norm")
    
    # Compute normalized heat and NDVI for multi-exposure calculation
    settings = raster_service.settings
    heat_norm = None
    ndvi_norm = None
    priority_score = None
    
    if lst is not None:
        heat_norm = (lst - settings.lst_min) / (settings.lst_max - settings.lst_min)
        heat_norm = max(0.0, min(1.0, heat_norm))
    
    if ndvi is not None:
        ndvi_norm = (ndvi - settings.ndvi_min) / (settings.ndvi_max - settings.ndvi_min)
        ndvi_norm = max(0.0, min(1.0, ndvi_norm))
    
    if heat_norm is not None and ndvi_norm is not None:
        priority_score = compute_multi_exposure_priority(heat_norm, ndvi_norm, aqi_norm)
    
    return {
        "location": {"lat": lat, "lng": lng},
        "values": {
            "ndvi": ndvi,
            "lst": lst,
            "gdi": gdi,
            "aqi_raw": aqi_raw,
            "aqi_norm": aqi_norm,
            "priority_score": priority_score
        },
        "interpretation": {
            "vegetation": _interpret_ndvi(ndvi) if ndvi else None,
            "temperature": _interpret_lst(lst) if lst else None,
            "air_quality": _interpret_aqi(aqi_raw) if aqi_raw else None,
            "priority": _interpret_priority(priority_score) if priority_score else _interpret_gdi(gdi) if gdi else None
        },
        "aqi_station": aqi_info.get("station"),
        "aqi_distance_km": aqi_info.get("distance_km")
    }


def _interpret_ndvi(value: float) -> str:
    """Interpret NDVI value."""
    if value < 0:
        return "Water or built-up area"
    elif value < 0.2:
        return "Bare soil or sparse vegetation"
    elif value < 0.4:
        return "Light vegetation"
    elif value < 0.6:
        return "Moderate vegetation"
    else:
        return "Dense vegetation"


def _interpret_lst(value: float) -> str:
    """Interpret LST value."""
    if value < 25:
        return "Cool surface"
    elif value < 28:
        return "Moderate temperature"
    elif value < 30:
        return "Warm surface"
    else:
        return "Hot surface (heat island)"


def _interpret_gdi(value: float) -> str:
    """Interpret GDI value."""
    if value < 0.3:
        return "Low priority - already green"
    elif value < 0.5:
        return "Moderate priority"
    elif value < 0.7:
        return "High priority"
    else:
        return "Critical priority - needs intervention"


def _interpret_aqi(value: float) -> str:
    """
    Interpret AQI/PM2.5 value based on Indian AQI scale.
    
    Categories:
    - Good: 0-50
    - Satisfactory: 51-100
    - Moderate: 101-200
    - Poor: 201-300
    - Very Poor: 301-400
    - Severe: 401+
    """
    if value <= 50:
        return "Good air quality"
    elif value <= 100:
        return "Satisfactory"
    elif value <= 200:
        return "Moderate pollution"
    elif value <= 300:
        return "Poor air quality"
    elif value <= 400:
        return "Very poor air quality"
    else:
        return "Severe pollution"


def _interpret_priority(value: float) -> str:
    """Interpret Multi-Exposure Priority score."""
    if value < 0.3:
        return "Low priority - minimal exposure"
    elif value < 0.5:
        return "Moderate priority"
    elif value < 0.7:
        return "High priority - multiple exposures"
    else:
        return "Critical priority - heat + pollution hotspot"
