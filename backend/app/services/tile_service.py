"""
Tile Service — Generate map tiles from raster data.

Converts raster arrays to PNG tiles for Leaflet consumption.
"""
import numpy as np
from PIL import Image
import io
from typing import Tuple, Optional
from cachetools import TTLCache
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from app.services.raster_service import RasterService


class TileService:
    """Service for generating XYZ map tiles from raster data."""
    
    # Color maps for different layers
    COLORMAPS = {
        'ndvi': 'YlGn',
        'lst': 'RdYlBu_r',
        'gdi': None,  # Custom colormap
    }
    
    # Value ranges for normalization
    # These are used for tile rendering; GDI uses actual data range (set at init)
    VALUE_RANGES = {
        'ndvi': (-0.2, 0.8),
        'lst': (24, 29),
        'gdi': (0, 1),  # Will be overridden with actual data percentiles
    }
    
    def __init__(self, raster_service: RasterService, tile_size: int = 256):
        self.raster_service = raster_service
        self.tile_size = tile_size
        self._cache = TTLCache(maxsize=1000, ttl=3600)
        
        # Create custom GDI colormap (Green → Yellow-Green → Yellow → Orange → Red)
        # 5-stop colormap gives better visual differentiation
        self._gdi_cmap = mcolors.LinearSegmentedColormap.from_list(
            'gdi', ['#1a9850', '#91cf60', '#fee08b', '#fc8d59', '#d73027']
        )
        
        # Set GDI tile range to actual data percentiles for maximum color spread
        gdi = raster_service.gdi
        if gdi is not None:
            valid = gdi[np.isfinite(gdi)]
            if len(valid) > 0:
                # Use P2–P98 to ignore outliers while spreading the color range
                self.VALUE_RANGES = dict(self.VALUE_RANGES)  # Don't mutate class var
                self.VALUE_RANGES['gdi'] = (
                    float(np.percentile(valid, 2)),
                    float(np.percentile(valid, 98))
                )
                print(f"  🎨 GDI tile range set to [{self.VALUE_RANGES['gdi'][0]:.3f}, {self.VALUE_RANGES['gdi'][1]:.3f}]")
                
                # Also set LST range based on actual data
                lst = raster_service.lst
                if lst is not None:
                    valid_lst = lst[np.isfinite(lst)]
                    if len(valid_lst) > 0:
                        self.VALUE_RANGES['lst'] = (
                            float(np.percentile(valid_lst, 2)),
                            float(np.percentile(valid_lst, 98))
                        )
                        print(f"  🎨 LST tile range set to [{self.VALUE_RANGES['lst'][0]:.3f}, {self.VALUE_RANGES['lst'][1]:.3f}]")
    
    def get_tile(self, layer: str, z: int, x: int, y: int) -> Optional[bytes]:
        """
        Generate a PNG tile for the specified layer and tile coordinates.
        
        Args:
            layer: Layer name (ndvi, lst, gdi)
            z: Zoom level
            x: Tile X coordinate
            y: Tile Y coordinate
            
        Returns:
            PNG image bytes or None if tile is outside bounds
        """
        cache_key = f"{layer}_{z}_{x}_{y}"
        
        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Get tile bounds in geographic coordinates
        tile_bounds = self._tile_to_bounds(z, x, y)
        
        # Check if tile intersects our data bounds
        data_bounds = self.raster_service.bounds
        if not self._bounds_intersect(tile_bounds, data_bounds):
            return None
        
        # Get layer data
        data = self.raster_service.get_layer_data(layer)
        if data is None:
            return None
        
        # Extract tile data from raster
        tile_data = self._extract_tile_data(data, tile_bounds, data_bounds, z=z, x=x, y=y)
        if tile_data is None:
            return None
        
        # Convert to image
        img_bytes = self._data_to_png(tile_data, layer)
        
        # Cache result
        self._cache[cache_key] = img_bytes
        
        return img_bytes
    
    def _tile_to_bounds(self, z: int, x: int, y: int) -> Tuple[float, float, float, float]:
        """Convert tile coordinates to geographic bounds (west, south, east, north)."""
        n = 2 ** z
        
        west = x / n * 360.0 - 180.0
        east = (x + 1) / n * 360.0 - 180.0
        
        north = np.arctan(np.sinh(np.pi * (1 - 2 * y / n))) * 180.0 / np.pi
        south = np.arctan(np.sinh(np.pi * (1 - 2 * (y + 1) / n))) * 180.0 / np.pi
        
        return (west, south, east, north)
    
    def _bounds_intersect(self, bounds1: Tuple, bounds2: Tuple) -> bool:
        """Check if two bounding boxes intersect."""
        w1, s1, e1, n1 = bounds1
        w2, s2, e2, n2 = bounds2
        
        return not (e1 < w2 or e2 < w1 or n1 < s2 or n2 < s1)
    
    def _lat_to_tile_y(self, lat: float, z: int) -> float:
        """Convert latitude in degrees to fractional Web Mercator tile Y coordinate."""
        lat_rad = np.radians(np.clip(lat, -85.05112878, 85.05112878))
        n = 2.0 ** z
        return (1.0 - np.log(np.tan(lat_rad) + 1.0 / np.cos(lat_rad)) / np.pi) / 2.0 * n

    def _lon_to_tile_x(self, lon: float, z: int) -> float:
        """Convert longitude in degrees to fractional Web Mercator tile X coordinate."""
        n = 2.0 ** z
        return (lon + 180.0) / 360.0 * n

    def _extract_tile_data(
        self, 
        data: np.ndarray, 
        tile_bounds: Tuple, 
        data_bounds: Tuple,
        z: Optional[int] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
    ) -> Optional[np.ndarray]:
        """
        Extract and resample raster data for a tile with exact sub-tile placement
        and NaN-aware bilinear interpolation so boundary tiles never stretch
        or bleed NoData values across out-of-bounds areas.
        """
        tw, ts, te, tn = tile_bounds
        dw, ds, de, dn = data_bounds

        # Compute geographic intersection between tile and raster bounds
        iw = max(tw, dw)
        ie = min(te, de)
        is_ = max(ts, ds)
        in_ = min(tn, dn)

        if iw >= ie or is_ >= in_:
            return None

        h, w = data.shape
        px_per_lon = w / (de - dw)
        px_per_lat = h / (dn - ds)

        # Source raster pixel indices for the intersection bbox
        col_start = max(0, int(np.floor((iw - dw) * px_per_lon)))
        col_end = min(w, int(np.ceil((ie - dw) * px_per_lon)))
        row_start = max(0, int(np.floor((dn - in_) * px_per_lat)))
        row_end = min(h, int(np.ceil((dn - is_) * px_per_lat)))

        if col_start >= col_end or row_start >= row_end:
            return None

        subset = data[row_start:row_end, col_start:col_end]
        if subset.size == 0:
            return None

        # Destination pixel coordinates within the 256x256 tile canvas
        S = self.tile_size
        dst_x0 = int(np.round((iw - tw) / (te - tw) * S))
        dst_x1 = int(np.round((ie - tw) / (te - tw) * S))

        if z is not None and y is not None:
            # Exact Web Mercator Y pixel mapping within tile y
            ty_north = (self._lat_to_tile_y(in_, z) - y) * S
            ty_south = (self._lat_to_tile_y(is_, z) - y) * S
            dst_y0 = int(np.round(ty_north))
            dst_y1 = int(np.round(ty_south))
        else:
            dst_y0 = int(np.round((tn - in_) / (tn - ts) * S))
            dst_y1 = int(np.round((tn - is_) / (tn - ts) * S))

        dst_x0 = max(0, min(S, dst_x0))
        dst_x1 = max(0, min(S, dst_x1))
        dst_y0 = max(0, min(S, dst_y0))
        dst_y1 = max(0, min(S, dst_y1))

        out_w = dst_x1 - dst_x0
        out_h = dst_y1 - dst_y0
        if out_w <= 0 or out_h <= 0:
            return None

        # NaN-safe resampling: interpolate valid data and valid mask separately
        sub_f32 = subset.astype(np.float32)
        valid_mask = np.isfinite(sub_f32) & (sub_f32 > -999.0)
        if not np.any(valid_mask):
            return None

        filled = np.where(valid_mask, sub_f32, 0.0).astype(np.float32)
        mask_f32 = valid_mask.astype(np.float32)

        img_val = Image.fromarray(filled, mode='F').resize(
            (out_w, out_h), Image.Resampling.BILINEAR
        )
        img_msk = Image.fromarray(mask_f32, mode='F').resize(
            (out_w, out_h), Image.Resampling.BILINEAR
        )

        res_val = np.array(img_val, dtype=np.float32)
        res_msk = np.array(img_msk, dtype=np.float32)

        with np.errstate(divide='ignore', invalid='ignore'):
            resampled = np.where(res_msk > 0.25, res_val / np.maximum(res_msk, 1e-5), np.nan)

        # Place resampled intersection into full 256x256 tile canvas (rest is NaN/transparent)
        canvas = np.full((S, S), np.nan, dtype=np.float32)
        canvas[dst_y0:dst_y1, dst_x0:dst_x1] = resampled
        return canvas
    
    def _data_to_png(self, data: np.ndarray, layer: str) -> bytes:
        """Convert normalized data array to PNG bytes."""
        # Get value range
        vmin, vmax = self.VALUE_RANGES.get(layer, (0, 1))
        
        # Normalize data
        normalized = (data - vmin) / (vmax - vmin + 1e-8)
        normalized = np.clip(normalized, 0, 1)
        
        # Handle NaN values
        mask = ~np.isfinite(data)
        
        # Get colormap
        if layer == 'gdi':
            cmap = self._gdi_cmap
        else:
            cmap = plt.get_cmap(self.COLORMAPS.get(layer, 'viridis'))
        
        # Apply colormap
        rgba = cmap(normalized)
        
        # Set transparent for NaN/NoData
        rgba[mask] = [0, 0, 0, 0]
        
        # Convert to 8-bit RGBA
        rgba_uint8 = (rgba * 255).astype(np.uint8)
        
        # Create PNG
        img = Image.fromarray(rgba_uint8, mode='RGBA')
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)
        
        return buffer.getvalue()
    
    def get_transparent_tile(self) -> bytes:
        """Return a cached 256x256 transparent PNG tile for out-of-bounds requests."""
        cache_key = "__transparent_tile__"
        if cache_key in self._cache:
            return self._cache[cache_key]
        rgba = np.zeros((self.tile_size, self.tile_size, 4), dtype=np.uint8)
        img = Image.fromarray(rgba, mode='RGBA')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)
        png_bytes = buffer.getvalue()
        self._cache[cache_key] = png_bytes
        return png_bytes

    def clear_cache(self):
        """Clear the tile cache."""
        self._cache.clear()
