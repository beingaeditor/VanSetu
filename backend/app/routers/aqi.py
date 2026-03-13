"""
AQI Router — Air Quality Index endpoints.

Provides endpoints for AQI station data and debugging.
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any

from app.dependencies import get_aqi_service
from app.services.aqi_service import AQIService

router = APIRouter()


@router.get("/aqi/stations")
async def get_aqi_stations(
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Get AQI monitoring stations as GeoJSON.
    
    Returns GeoJSON FeatureCollection with station locations and PM2.5 values.
    Useful for debugging and visualization of AQI station coverage.
    """
    try:
        geojson = aqi_service.stations_to_geojson()
        return geojson
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/aqi/point")
async def get_aqi_at_point(
    lat: float,
    lng: float,
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Get AQI value at a specific geographic point.
    
    Args:
        lat: Latitude
        lng: Longitude
        
    Returns:
        AQI information from nearest station including:
        - aqi_raw: Raw PM2.5 value
        - aqi_norm: Normalized AQI [0, 1]
        - station: Nearest station info
        - distance_km: Distance to station
    """
    try:
        result = aqi_service.get_aqi_at_point(lng, lat)
        return {
            "location": {"lat": lat, "lng": lng},
            "aqi": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/aqi/refresh")
async def refresh_aqi_data(
    background_tasks: BackgroundTasks,
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, str]:
    """
    Trigger a refresh of AQI data from OpenAQ.
    
    Fetches latest PM2.5 readings from CPCB/DPCC stations.
    """
    try:
        # Clear cache and refetch
        aqi_service.clear_cache()
        stations = aqi_service.fetch_stations(force_refresh=True)
        
        return {
            "status": "ok",
            "message": f"Refreshed AQI data: {len(stations)} stations"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/aqi/status")
async def get_aqi_status(
    aqi_service: AQIService = Depends(get_aqi_service)
) -> Dict[str, Any]:
    """
    Get AQI service status.
    
    Returns information about cached data and last update time.
    """
    stations = aqi_service.stations
    last_updated = aqi_service.last_updated
    
    # Calculate average AQI
    aqi_values = [s.aqi_raw for s in stations if s.aqi_raw is not None]
    avg_aqi = sum(aqi_values) / len(aqi_values) if aqi_values else None
    
    return {
        "status": "ok",
        "stations_count": len(stations),
        "last_updated": last_updated.isoformat() if last_updated else None,
        "average_pm25": round(avg_aqi, 1) if avg_aqi else None,
        "coverage": "Delhi NCT"
    }
