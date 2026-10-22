"""
Layers Router — Layer metadata, scientific provenance, and spatial parameters.
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any

from app.config import get_settings, Settings, DATASET_METADATA

router = APIRouter()


@router.get("/layers")
async def list_layers(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """
    List all available map layers with metadata, scientific classification,
    and spatial resolution warnings.
    """
    return {
        "layers": [
            {
                "id": "ndvi",
                "name": "Vegetation Index (NDVI)",
                "description": "Normalized Difference Vegetation Index from Sentinel-2 (10m high-resolution)",
                "type": "raster",
                "colormap": "YlGn",
                "unit": "index [-1 to 1]",
                "range": [settings.ndvi_min, settings.ndvi_max],
                "provenance": DATASET_METADATA.get("ndvi", {}),
                "legend": {
                    "min_label": "Low Vegetation (Sparse/Paved)",
                    "max_label": "Dense Canopy Vegetation"
                }
            },
            {
                "id": "lst",
                "name": "Land Surface Temperature (Screening LST)",
                "description": "Macro-thermal surface temperature from MODIS 1km product (resampled for regional screening)",
                "type": "raster",
                "colormap": "RdYlBu_r",
                "unit": "°C",
                "range": [settings.lst_min, settings.lst_max],
                "provenance": DATASET_METADATA.get("lst", {}),
                "spatial_warning": "Coarse 1km native resolution resampled to 10m grid. Represents macro-surface heat screening, NOT street-level pedestrian microclimate.",
                "legend": {
                    "min_label": "Cooler Surface (~22°C)",
                    "max_label": "Hotter Surface (~32°C)"
                }
            },
            {
                "id": "gdi",
                "name": "Green Deficit Index (GDI)",
                "description": "Composite priority metric combining thermal exposure and vegetation deficit",
                "type": "raster",
                "colormap": "GnYlRd",
                "unit": "priority [0 to 1]",
                "range": [0, 1],
                "formula": f"({settings.gdi_heat_weight} × Heat) + ({settings.gdi_ndvi_weight} × (1 - NDVI))",
                "legend": {
                    "min_label": "Low Deficit (Existing Greenery)",
                    "max_label": "High Deficit (Severe Need)"
                }
            },
            {
                "id": "roads",
                "name": "Walkable Road Network",
                "description": "OpenStreetMap pedestrian-accessible street hierarchy (primaries, secondaries, tertiaries, pedestrian ways)",
                "type": "vector",
                "geometry": "LineString",
                "provenance": DATASET_METADATA.get("roads", {})
            },
            {
                "id": "corridors",
                "name": "Prioritized VanSetu Corridors",
                "description": "High-priority pedestrian segments with multi-criteria scores, feasibility, confidence, and intervention recommendations",
                "type": "vector",
                "geometry": "LineString"
            }
        ],
        "bounds": settings.delhi_bounds,
        "center": {
            "lat": (settings.delhi_north + settings.delhi_south) / 2,
            "lng": (settings.delhi_east + settings.delhi_west) / 2
        },
        "default_zoom": 11,
        "dataset_metadata": DATASET_METADATA
    }


@router.get("/layers/metadata")
async def get_dataset_metadata() -> Dict[str, Any]:
    """Retrieve complete scientific provenance and limitations for all platform datasets."""
    return {
        "platform": "VanSetu Urban Climate Resilience Platform",
        "datasets": DATASET_METADATA,
        "evaluation_notes": {
            "surface_vs_air_temp": (
                "Land Surface Temperature (LST) measures radiometric radiative skin temperature. "
                "Near-surface air temperature (T_air) and Mean Radiant Temperature (T_mrt) govern human "
                "thermal comfort (PET/UTCI). LST serves as a macro-screening proxy for surface solar absorption."
            ),
            "ecological_vs_pedestrian": (
                "Connecting urban street corridors does not by itself create biological habitat corridors. "
                "Ecological connectivity requires continuous vegetation canopies and stepping-stone patches "
                "tailored to specific avian and pollinator species."
            )
        }
    }


@router.get("/layers/{layer_id}")
async def get_layer_info(
    layer_id: str,
    settings: Settings = Depends(get_settings)
) -> Dict[str, Any]:
    """Get detailed information about a specific layer."""
    layers_data = await list_layers(settings)
    for layer in layers_data["layers"]:
        if layer["id"] == layer_id:
            return layer
    raise HTTPException(status_code=404, detail=f"Layer '{layer_id}' not found")
