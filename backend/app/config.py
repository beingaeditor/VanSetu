"""
Application configuration and settings.
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


def get_data_dir() -> Path:
    """
    Get data directory.
    Works for both local development and Render deployment.
    """
    # If explicitly provided via environment variable
    if os.environ.get("DATA_DIR"):
        return Path(os.environ["DATA_DIR"])

    # Default: backend/data directory
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

    # Delhi bounds
    delhi_north: float = 28.87
    delhi_south: float = 28.40
    delhi_east: float = 77.35
    delhi_west: float = 76.73

    # GDI weights
    gdi_heat_weight: float = 0.6
    gdi_ndvi_weight: float = 0.4

    # Normalization ranges
    ndvi_min: float = -0.2
    ndvi_max: float = 0.8
    lst_min: float = 24.0
    lst_max: float = 29.0

    # Tile settings
    tile_size: int = 256
    max_zoom: int = 15
    min_zoom: int = 8

    # Cache settings
    cache_ttl: int = 3600

    # External APIs
    openaq_api_key: str = ""

    @property
    def ndvi_full_path(self) -> Path:
        return self.data_dir / self.ndvi_path

    @property
    def lst_full_path(self) -> Path:
        return self.data_dir / self.lst_path

    @property
    def delhi_bounds(self) -> dict:
        return {
            "north": self.delhi_north,
            "south": self.delhi_south,
            "east": self.delhi_east,
            "west": self.delhi_west,
        }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
