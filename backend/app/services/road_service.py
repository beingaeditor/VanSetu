"""
Road Service — Fetch and process road network from OpenStreetMap.

Handles OSM road fetching, GDI sampling, AQI assignment, and corridor detection.

Uses the 6-factor Priority Index:
    Priority = (Heat × 0.25) + (Pollution × 0.20) + (Green Deficit × 0.20)
             + (Pedestrian Density × 0.15) + (Health Risk Index × 0.12)
             + (Vulnerable Pop. × 0.08)
"""
import numpy as np
import geopandas as gpd
import osmnx as ox
from shapely.geometry import MultiLineString
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from cachetools import TTLCache
import json

from app.config import Settings
from app.services.raster_service import RasterService

# Avoid circular import
if TYPE_CHECKING:
    from app.services.aqi_service import AQIService


class RoadService:
    """Service for road network operations."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._roads_cache: Optional[gpd.GeoDataFrame] = None
        self._corridors_cache: Optional[gpd.GeoDataFrame] = None
        self._cache_lock = False
    
    @property
    def delhi_bbox(self) -> tuple:
        """Return bbox as (west, south, east, north)."""
        b = self.settings.delhi_bounds
        return (b['west'], b['south'], b['east'], b['north'])
    
    def fetch_roads(self, force_refresh: bool = False) -> gpd.GeoDataFrame:
        """
        Fetch road network from OpenStreetMap.
        
        Args:
            force_refresh: Force re-fetch from OSM
            
        Returns:
            GeoDataFrame with road geometries
        """
        if self._roads_cache is not None and not force_refresh:
            return self._roads_cache
        
        print("  ⏳ Fetching road network from OpenStreetMap...")
        
        tags = {
            'highway': ['motorway', 'trunk', 'primary', 'secondary', 'tertiary']
        }
        
        bbox = self.delhi_bbox
        
        # Fetch features
        features = ox.features_from_bbox(bbox=bbox, tags=tags)
        
        # Convert to GeoDataFrame and filter geometries
        gdf = gpd.GeoDataFrame(features).reset_index()
        
        # Keep only line geometries
        valid_types = ['LineString', 'MultiLineString']
        gdf = gdf[gdf.geometry.geom_type.isin(valid_types)].copy()
        
        # Ensure CRS
        if gdf.crs is None:
            gdf = gdf.set_crs('EPSG:4326')
        else:
            gdf = gdf.to_crs('EPSG:4326')
        
        # Simplify to essential columns
        keep_cols = ['geometry']
        if 'name' in gdf.columns:
            keep_cols.append('name')
        if 'highway' in gdf.columns:
            keep_cols.append('highway')
        
        gdf = gdf[keep_cols].copy()
        
        print(f"  ✅ Fetched {len(gdf)} road segments")
        
        self._roads_cache = gdf
        return gdf
    
    def sample_gdi_along_roads(
        self, 
        raster_service: RasterService
    ) -> gpd.GeoDataFrame:
        """
        Sample GDI values along road segments.
        
        Args:
            raster_service: RasterService instance with loaded GDI data
            
        Returns:
            GeoDataFrame with 'gdi_mean' column added
        """
        roads = self.fetch_roads()
        
        if roads is None or len(roads) == 0:
            return gpd.GeoDataFrame(geometry=[], crs='EPSG:4326')
        
        gdi = raster_service.gdi
        transform = raster_service.transform
        
        if gdi is None or transform is None:
            return roads
        
        from rasterio.transform import rowcol
        
        gdi_values = []
        h, w = gdi.shape
        
        for geom in roads.geometry:
            try:
                # Handle MultiLineString
                if isinstance(geom, MultiLineString):
                    coords = []
                    for line in geom.geoms:
                        coords.extend(list(line.coords))
                else:
                    coords = list(geom.coords)
                
                if len(coords) == 0:
                    gdi_values.append(np.nan)
                    continue
                
                # Sample along line
                num_samples = max(10, int(geom.length / 0.001))
                pixel_vals = []
                
                for i in range(num_samples):
                    pt = geom.interpolate(i / num_samples, normalized=True)
                    try:
                        row, col = rowcol(transform, pt.x, pt.y)
                        if 0 <= row < h and 0 <= col < w:
                            val = gdi[row, col]
                            if np.isfinite(val):
                                pixel_vals.append(val)
                    except Exception:
                        continue
                
                if pixel_vals:
                    gdi_values.append(np.mean(pixel_vals))
                else:
                    gdi_values.append(np.nan)
                    
            except Exception:
                gdi_values.append(np.nan)
        
        roads = roads.copy()
        roads['gdi_mean'] = gdi_values
        
        return roads
    
    def sample_with_aqi(
        self,
        raster_service: RasterService,
        aqi_service: "AQIService"
    ) -> gpd.GeoDataFrame:
        """
        Sample GDI values and assign AQI to road segments.

        Computes the 6-factor Priority Index:
            Priority = (Heat × 0.25) + (Pollution × 0.20) + (Green Deficit × 0.20)
                     + (Pedestrian Density × 0.15) + (Health Risk Index × 0.12)
                     + (Vulnerable Pop. × 0.08)

        Health Risk Index and Vulnerable Population are derived from secondary
        (ground-level) user inputs when available, falling back to proxies.

        Args:
            raster_service: RasterService instance with loaded raster data
            aqi_service: AQIService instance with AQI station data

        Returns:
            GeoDataFrame with priority_score and all component signals
        """
        from app.services.aqi_service import normalize_aqi
        from app.services.scoring_service import (
            compute_priority,
            pedestrian_proxy,
            vulnerable_population_proxy,
        )

        roads = self.sample_gdi_along_roads(raster_service)

        if roads is None or len(roads) == 0:
            return gpd.GeoDataFrame(geometry=[], crs='EPSG:4326')

        # Ensure AQI data is loaded
        aqi_service.fetch_stations()

        # Get raster data for individual component sampling
        ndvi = raster_service.ndvi
        lst = raster_service.lst
        transform = raster_service.transform
        settings = raster_service.settings

        # Initialize new columns
        heat_norms = []
        ndvi_norms = []
        aqi_raws = []
        aqi_norms = []
        priority_scores = []
        pedestrian_scores = []
        vulnerable_scores = []
        signal_breakdowns = []
        data_source_infos = []

        h, w = ndvi.shape if ndvi is not None else (0, 0)

        from rasterio.transform import rowcol

        for idx, row in roads.iterrows():
            geom = row.geometry

            # Get centroid for AQI lookup
            centroid = geom.centroid

            # Sample heat and NDVI at centroid
            heat_norm = None
            ndvi_norm = None

            if ndvi is not None and lst is not None and transform is not None:
                try:
                    r, c = rowcol(transform, centroid.x, centroid.y)
                    if 0 <= r < h and 0 <= c < w:
                        ndvi_val = ndvi[r, c]
                        lst_val = lst[r, c]

                        if np.isfinite(ndvi_val) and np.isfinite(lst_val):
                            ndvi_norm = (ndvi_val - settings.ndvi_min) / (settings.ndvi_max - settings.ndvi_min)
                            ndvi_norm = max(0.0, min(1.0, ndvi_norm))

                            heat_norm = (lst_val - settings.lst_min) / (settings.lst_max - settings.lst_min)
                            heat_norm = max(0.0, min(1.0, heat_norm))
                except Exception:
                    pass

            # Get AQI from nearest station
            aqi_info = aqi_service.get_aqi_at_point(centroid.x, centroid.y)
            aqi_raw = aqi_info.get("aqi_raw")
            aqi_norm = aqi_info.get("aqi_norm")

            # Get highway type for proxy signals
            highway_type = row.get('highway') if 'highway' in roads.columns else None

            # Compute 6-factor priority with signal breakdown
            if heat_norm is not None and ndvi_norm is not None:
                result = compute_priority(
                    heat_norm=heat_norm,
                    ndvi_norm=ndvi_norm,
                    aqi_norm=aqi_norm,
                    highway_type=highway_type,
                    lon=centroid.x,
                    lat=centroid.y,
                )
                priority = result["score"]
                signals = result["signals"]
                data_sources = result["data_sources"]
            else:
                priority = row.get('gdi_mean')
                signals = {}
                data_sources = {}

            ped_score = pedestrian_proxy(highway_type)
            vuln_score = vulnerable_population_proxy(centroid.x, centroid.y)

            heat_norms.append(heat_norm)
            ndvi_norms.append(ndvi_norm)
            aqi_raws.append(aqi_raw)
            aqi_norms.append(aqi_norm)
            priority_scores.append(priority)
            pedestrian_scores.append(ped_score)
            vulnerable_scores.append(vuln_score)
            signal_breakdowns.append(signals)
            data_source_infos.append(data_sources)

        # Add new columns
        roads = roads.copy()
        roads['heat_norm'] = heat_norms
        roads['ndvi_norm'] = ndvi_norms
        roads['aqi_raw'] = aqi_raws
        roads['aqi_norm'] = aqi_norms
        roads['priority_score'] = priority_scores
        roads['pedestrian_score'] = pedestrian_scores
        roads['vulnerable_score'] = vulnerable_scores
        roads['priority_signals'] = signal_breakdowns
        roads['priority_data_sources'] = data_source_infos

        print(f"  ✅ Computed 6-factor priority for {len(roads)} road segments")

        return roads
    
    def detect_corridors(
        self, 
        raster_service: RasterService,
        percentile: float = 85,
        aqi_service: Optional["AQIService"] = None
    ) -> gpd.GeoDataFrame:
        """
        Detect high-priority VanSetu corridors.
        
        If aqi_service is provided, uses Multi-Exposure Priority score.
        Otherwise, falls back to original GDI-based scoring.
        
        Args:
            raster_service: RasterService with GDI data
            percentile: Percentile threshold for high-priority roads
            aqi_service: Optional AQIService for multi-exposure scoring
            
        Returns:
            GeoDataFrame with corridor segments
        """
        if self._corridors_cache is not None:
            return self._corridors_cache
        
        # Use multi-exposure priority if AQI service available
        if aqi_service is not None:
            roads = self.sample_with_aqi(raster_service, aqi_service)
            score_col = 'priority_score'
        else:
            roads = self.sample_gdi_along_roads(raster_service)
            score_col = 'gdi_mean'
        
        if len(roads) == 0 or score_col not in roads.columns:
            return gpd.GeoDataFrame(geometry=[], crs='EPSG:4326')
        
        # Filter to valid score values
        valid = roads[roads[score_col].notna()].copy()
        
        if len(valid) == 0:
            return gpd.GeoDataFrame(geometry=[], crs='EPSG:4326')
        
        # Get threshold based on score column
        threshold = valid[score_col].quantile(percentile / 100)
        
        # Filter high-priority corridors
        corridors = valid[valid[score_col] >= threshold].copy()
        
        score_type = "multi-exposure priority" if aqi_service else "GDI"
        print(f"  🛤️  Identified {len(corridors)} corridor segments (top {100-percentile:.0f}% by {score_type})")
        
        self._corridors_cache = corridors
        return corridors
    
    def roads_to_geojson(self, roads: gpd.GeoDataFrame) -> Dict[str, Any]:
        """Convert GeoDataFrame to GeoJSON dict."""
        if roads is None or len(roads) == 0:
            return {"type": "FeatureCollection", "features": []}

        # Handle non-JSON-serializable values (numpy float32, NaN, dicts with numpy)
        roads_copy = roads.copy()
        for col in roads_copy.columns:
            if col == 'geometry':
                continue
            roads_copy[col] = roads_copy[col].apply(self._make_serializable)

        return json.loads(roads_copy.to_json())

    @staticmethod
    def _make_serializable(x):
        """Convert numpy types and NaN to JSON-safe Python types."""
        if x is None:
            return None
        if isinstance(x, float) and np.isnan(x):
            return None
        if isinstance(x, (np.floating,)):
            return float(x)
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, dict):
            return {k: RoadService._make_serializable(v) for k, v in x.items()}
        if isinstance(x, list):
            return [RoadService._make_serializable(v) for v in x]
        return x
    
    def clear_cache(self):
        """Clear cached data."""
        self._roads_cache = None
        self._corridors_cache = None
