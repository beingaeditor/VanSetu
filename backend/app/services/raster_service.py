"""
Raster Service — Core data loading and processing.

Handles NDVI, LST loading and GDI computation.
"""
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from scipy.ndimage import zoom
from typing import Optional, Tuple, Dict, Any
from cachetools import TTLCache
import threading

from app.config import Settings


class RasterService:
    """
    Service for loading and processing raster data.
    Thread-safe with caching support.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.Lock()
        
        # Raw data storage
        self._ndvi_data: Optional[np.ndarray] = None
        self._lst_data: Optional[np.ndarray] = None
        self._gdi_data: Optional[np.ndarray] = None
        
        # Metadata
        self._ndvi_profile: Optional[Dict] = None
        self._lst_profile: Optional[Dict] = None
        self._bounds: Optional[Tuple[float, float, float, float]] = None
        
        # Tile cache
        self._tile_cache = TTLCache(maxsize=500, ttl=settings.cache_ttl)
        
        self._is_loaded = False
    
    @property
    def is_loaded(self) -> bool:
        return self._is_loaded
    
    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """Return (west, south, east, north) bounds."""
        if self._bounds:
            return self._bounds
        s = self.settings
        return (s.delhi_west, s.delhi_south, s.delhi_east, s.delhi_north)
    
    @property
    def ndvi(self) -> Optional[np.ndarray]:
        return self._ndvi_data
    
    @property
    def lst(self) -> Optional[np.ndarray]:
        return self._lst_data
    
    @property
    def gdi(self) -> Optional[np.ndarray]:
        return self._gdi_data
    
    @property
    def shape(self) -> Tuple[int, int]:
        if self._ndvi_data is not None:
            return self._ndvi_data.shape
        return (0, 0)
    
    @property
    def transform(self):
        if self._ndvi_profile:
            return self._ndvi_profile.get('transform')
        return None
    
    def load_data(self) -> None:
        """Load all raster data and compute derived layers."""
        with self._lock:
            print(f"  📂 Loading NDVI: {self.settings.ndvi_full_path}")
            self._ndvi_data, self._ndvi_profile = self._load_geotiff(
                self.settings.ndvi_full_path
            )
            print(f"     Shape: {self._ndvi_data.shape}")
            
            print(f"  📂 Loading LST: {self.settings.lst_full_path}")
            lst_raw, self._lst_profile = self._load_geotiff(
                self.settings.lst_full_path
            )
            print(f"     Shape (original): {lst_raw.shape}")
            
            # Resample LST to match NDVI resolution
            print("  ⚙️  Resampling LST to match NDVI...")
            self._lst_data = self._resample_to_match(lst_raw, self._ndvi_data.shape)
            print(f"     Shape (resampled): {self._lst_data.shape}")
            
            # Compute GDI
            print("  🧮 Computing Green Deficit Index...")
            self._gdi_data = self._compute_gdi()
            print(f"     GDI range: [{np.nanmin(self._gdi_data):.3f}, {np.nanmax(self._gdi_data):.3f}]")
            
            # Set bounds from NDVI profile
            if self._ndvi_profile and 'transform' in self._ndvi_profile:
                t = self._ndvi_profile['transform']
                h, w = self._ndvi_data.shape
                self._bounds = (
                    t.c,  # west
                    t.f + t.e * h,  # south
                    t.c + t.a * w,  # east
                    t.f  # north
                )
            
            self._is_loaded = True
            print("  ✅ All raster data loaded successfully")
    
    def _load_geotiff(self, filepath) -> Tuple[np.ndarray, Dict]:
        """Load a GeoTIFF file."""
        with rasterio.open(filepath) as src:
            data = src.read(1).astype(np.float32)
            profile = dict(src.profile)
            profile['transform'] = src.transform
            profile['crs'] = src.crs
        return data, profile
    
    def _resample_to_match(self, source: np.ndarray, target_shape: Tuple[int, int]) -> np.ndarray:
        """Resample source array to match target shape."""
        zoom_factors = (target_shape[0] / source.shape[0], 
                       target_shape[1] / source.shape[1])
        resampled = zoom(source, zoom_factors, order=1)
        # Ensure exact match
        if resampled.shape != target_shape:
            resampled = resampled[:target_shape[0], :target_shape[1]]
        return resampled
    
    def _normalize(self, arr: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
        """Normalize array to [0, 1] range."""
        result = (arr - vmin) / (vmax - vmin + 1e-8)
        return np.clip(result, 0, 1)
    
    def _compute_gdi(self) -> np.ndarray:
        """
        Compute Green Deficit Index.
        GDI = (normalized_heat * weight) + ((1 - normalized_ndvi) * weight)
        """
        s = self.settings
        
        ndvi_norm = self._normalize(self._ndvi_data, s.ndvi_min, s.ndvi_max)
        lst_norm = self._normalize(self._lst_data, s.lst_min, s.lst_max)
        
        gdi = (lst_norm * s.gdi_heat_weight) + ((1 - ndvi_norm) * s.gdi_ndvi_weight)
        return np.clip(gdi, 0, 1)
    
    def get_layer_data(self, layer_name: str) -> Optional[np.ndarray]:
        """Get data for a specific layer."""
        layers = {
            'ndvi': self._ndvi_data,
            'lst': self._lst_data,
            'gdi': self._gdi_data,
        }
        return layers.get(layer_name.lower())
    
    def get_value_at_point(self, layer: str, lat: float, lon: float) -> Optional[float]:
        """Get raster value at a geographic point."""
        data = self.get_layer_data(layer)
        if data is None or self.transform is None:
            return None
        
        try:
            from rasterio.transform import rowcol
            row, col = rowcol(self.transform, lon, lat)
            if 0 <= row < data.shape[0] and 0 <= col < data.shape[1]:
                value = data[row, col]
                if np.isfinite(value):
                    return float(value)
        except Exception:
            pass
        return None
    
    def get_statistics(self, layer: str) -> Dict[str, Any]:
        """Get statistics for a layer."""
        data = self.get_layer_data(layer)
        if data is None:
            return {}
        
        valid_data = data[np.isfinite(data)]
        if len(valid_data) == 0:
            return {}
        
        return {
            "min": float(np.min(valid_data)),
            "max": float(np.max(valid_data)),
            "mean": float(np.mean(valid_data)),
            "std": float(np.std(valid_data)),
            "median": float(np.median(valid_data)),
            "valid_pixels": int(len(valid_data)),
            "total_pixels": int(data.size),
        }
    
    def get_histogram(self, layer: str, bins: int = 50) -> Dict[str, Any]:
        """Get histogram data for a layer."""
        data = self.get_layer_data(layer)
        if data is None:
            return {}
        
        valid_data = data[np.isfinite(data)]
        if len(valid_data) == 0:
            return {}
        
        hist, bin_edges = np.histogram(valid_data, bins=bins)
        return {
            "counts": hist.tolist(),
            "bin_edges": bin_edges.tolist(),
        }
