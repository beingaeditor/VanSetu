"""
Application configuration and settings.
Includes scientific dataset metadata and configurable prioritization weights.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Dict, Any


def get_data_dir() -> Path:
    """
    Get data directory.
    Works for both local development and container deployments.
    """
    if os.environ.get("DATA_DIR"):
        return Path(os.environ["DATA_DIR"])
    return Path(__file__).resolve().parent.parent / "data"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Settings
    app_name: str = "VanSetu Platform"
    debug: bool = True
    api_prefix: str = "/api"

    # Data paths
    data_dir: Path = get_data_dir()
    ndvi_path: str = "delhi_ndvi_10m.tif"
    lst_path: str = "delhi_lst_modis_daily_celsius.tif"
    roads_cache_path: str = "delhi_roads_cached.geojson"

    # Delhi geographic bounds (WGS84 EPSG:4326)
    delhi_north: float = 28.87
    delhi_south: float = 28.40
    delhi_east: float = 77.35
    delhi_west: float = 76.73

    # Default Prioritization Weights (sum to 1.0)
    weight_heat: float = 0.25
    weight_pollution: float = 0.20
    weight_green_deficit: float = 0.20
    weight_pedestrian: float = 0.15
    weight_health_risk: float = 0.12
    weight_vulnerability: float = 0.08

    # Legacy GDI weights (for backward compatibility)
    gdi_heat_weight: float = 0.6
    gdi_ndvi_weight: float = 0.4

    # Normalization ranges (clamped to realistic regional distributions)
    ndvi_min: float = -0.2
    ndvi_max: float = 0.8
    lst_min: float = 22.0
    lst_max: float = 32.0

    # Tile settings
    tile_size: int = 256
    max_zoom: int = 15
    min_zoom: int = 8

    # Cache settings
    cache_ttl: int = 3600

    # External APIs
    openaq_api_key: str = ""
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "urban_green_corridors"

    # Prune AI Gateway (Backend only)
    prune_api_key: str = ""
    prune_base_url: str = "https://api.withprune.com/v1"
    prune_model: str = "gemini-2.0-flash"

    # Pydantic V2 Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def ndvi_full_path(self) -> Path:
        return self.data_dir / self.ndvi_path

    @property
    def lst_full_path(self) -> Path:
        return self.data_dir / self.lst_path

    @property
    def roads_cache_full_path(self) -> Path:
        return self.data_dir / self.roads_cache_path

    @property
    def delhi_bounds(self) -> dict:
        return {
            "north": self.delhi_north,
            "south": self.delhi_south,
            "east": self.delhi_east,
            "west": self.delhi_west,
        }

    @property
    def default_weights(self) -> Dict[str, float]:
        return {
            "heat": self.weight_heat,
            "pollution": self.weight_pollution,
            "green_deficit": self.weight_green_deficit,
            "pedestrian": self.weight_pedestrian,
            "health_risk": self.weight_health_risk,
            "vulnerable_pop": self.weight_vulnerability,
        }


# Provenance metadata for scientific accountability
DATASET_METADATA: Dict[str, Dict[str, Any]] = {
    "ndvi": {
        "dataset_name": "Copernicus Sentinel-2 Surface Reflectance (Harmonized)",
        "provider": "European Space Agency (ESA) via Google Earth Engine",
        "native_spatial_resolution": "10 meters",
        "temporal_coverage": "2024-11-01 to 2025-02-28 (Post-monsoon / Winter composite)",
        "units": "Unitless normalized difference [-1 to 1]",
        "crs": "EPSG:4326 (reprojected from UTM 43N)",
        "processing": "Cloud masked via QA60 band, median reduction over period",
        "limitations": "Measures canopy greenness (vigor) rather than 3D canopy volume or understory shade.",
        "scientific_classification": "Direct high-resolution vegetation observation"
    },
    "lst": {
        "dataset_name": "MODIS Terra Daily Land Surface Temperature (MOD11A1.061)",
        "provider": "NASA LP DAAC via Google Earth Engine",
        "native_spatial_resolution": "1,000 meters (1 km)",
        "temporal_coverage": "2024-10-01 to 2025-03-31 (Late Autumn / Winter / Early Spring composite)",
        "units": "Degrees Celsius (°C)",
        "crs": "EPSG:4326 (reprojected from Sinusoidal)",
        "processing": "Multi-month mean day LST scaled by 0.02 - 273.15, resampled to 10m grid via bilinear interpolation",
        "limitations": (
            "WARNING: Coarse 1km native resolution. Bilinear resampling to 10m provides spatial alignment "
            "but DOES NOT create microclimate or street-canyon thermal information. Also reflects winter/spring "
            "temperatures, not peak pre-monsoon Delhi summer extremes (45°C-50°C)."
        ),
        "scientific_classification": "Macro-thermal regional screening estimate (NOT validated street-level temperature)"
    },
    "aqi": {
        "dataset_name": "Continuous Ambient Air Quality Monitoring (CAAQMS)",
        "provider": "Central Pollution Control Board (CPCB) / DPCC via OpenAQ & WAQI",
        "native_spatial_resolution": "Point station monitoring (~40 stations across Delhi NCT)",
        "temporal_coverage": "Near-real-time hourly / daily observations",
        "units": "Indian National Air Quality Index (NAQI) / PM2.5 (µg/m³)",
        "crs": "WGS84 point coordinates",
        "processing": "Inverse distance / nearest station spatial assignment with 50-300 cap normalization",
        "limitations": "Sparse station density between stations; unobserved local roadside micro-variations.",
        "scientific_classification": "Interpolated ground-station observation"
    },
    "roads": {
        "dataset_name": "OpenStreetMap Street Network",
        "provider": "OpenStreetMap Contributors via OSMnx / Overpass API",
        "native_spatial_resolution": "Vector polyline geometry",
        "temporal_coverage": "Current OSM database snapshot",
        "units": "Meters (length)",
        "crs": "EPSG:4326",
        "processing": "Filtered for walkable street hierarchies (primary, secondary, tertiary, residential, living_street, pedestrian), excluding motorways",
        "limitations": "Footpath presence, effective walking width, and surface quality are partially mapped in OSM.",
        "scientific_classification": "Walkable network topology proxy"
    }
}


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
