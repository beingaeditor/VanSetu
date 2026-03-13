"""
Layers Router — Layer metadata and information endpoints.
"""
from fastapi import APIRouter, Depends
from typing import Dict, Any, List

from app.config import get_settings, Settings

router = APIRouter()


@router.get("/layers")
async def list_layers(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """
    List all available map layers with metadata.
    """
    return {
        "layers": [
            {
                "id": "ndvi",
                "name": "Vegetation Index (NDVI)",
                "description": "Normalized Difference Vegetation Index from Sentinel-2",
                "type": "raster",
                "colormap": "YlGn",
                "unit": "index",
                "range": [settings.ndvi_min, settings.ndvi_max],
                "legend": {
                    "min_label": "Low Vegetation",
                    "max_label": "Dense Vegetation"
                }
            },
            {
                "id": "lst",
                "name": "Land Surface Temperature",
                "description": "Daytime surface temperature from MODIS",
                "type": "raster",
                "colormap": "RdYlBu_r",
                "unit": "°C",
                "range": [settings.lst_min, settings.lst_max],
                "legend": {
                    "min_label": "Cooler",
                    "max_label": "Hotter"
                }
            },
            {
                "id": "gdi",
                "name": "Green Deficit Index",
                "description": "Composite priority metric combining heat and vegetation deficit",
                "type": "raster",
                "colormap": "GnYlRd",
                "unit": "priority",
                "range": [0, 1],
                "legend": {
                    "min_label": "Low Priority (Green)",
                    "max_label": "High Priority (Needs Corridors)"
                }
            },
            {
                "id": "roads",
                "name": "Road Network",
                "description": "Major roads from OpenStreetMap",
                "type": "vector",
                "geometry": "LineString"
            },
            {
                "id": "corridors",
                "name": "Proposed VanSetu Corridors",
                "description": "High-priority road segments for green intervention",
                "type": "vector",
                "geometry": "LineString"
            }
        ],
        "bounds": settings.delhi_bounds,
        "center": {
            "lat": (settings.delhi_north + settings.delhi_south) / 2,
            "lng": (settings.delhi_east + settings.delhi_west) / 2
        },
        "default_zoom": 11
    }


@router.get("/layers/{layer_id}")
async def get_layer_info(
    layer_id: str,
    settings: Settings = Depends(get_settings)
) -> Dict[str, Any]:
    """Get detailed information about a specific layer."""
    layers = await list_layers(settings)
    
    for layer in layers["layers"]:
        if layer["id"] == layer_id:
            return layer
    
    return {"error": f"Layer '{layer_id}' not found"}
