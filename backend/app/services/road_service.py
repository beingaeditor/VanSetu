"""
Road Service — Fetch, Cache, and Process Road & Pedestrian Networks.

Handles:
- OSM road network fetching with local GeoJSON caching for offline resilience
- Filtering of walkable pedestrian networks (excluding vehicular expressways/motorways)
- Spatial sampling of Sentinel-2 NDVI and MODIS LST along segment polylines
- Integration of live CPCB/DPCC monitoring stations
- Multi-criteria evaluation: Priority [0,1], Feasibility [0,1], Evidence Confidence [0,1]
- Transparent corridor selection rationale
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List, TYPE_CHECKING
import numpy as np
import geopandas as gpd
from shapely.geometry import MultiLineString, LineString, mapping
from shapely.ops import transform
import pyproj

from app.config import Settings
from app.services.raster_service import RasterService
from app.services.scoring_service import (
    compute_priority,
    pedestrian_proxy,
    vulnerable_population_proxy,
    clean_highway_tag,
    HIGHWAY_PROFILES,
)

if TYPE_CHECKING:
    from app.services.aqi_service import AQIService


class RoadService:
    """Service for road network and pedestrian corridor operations."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._roads_cache: Optional[gpd.GeoDataFrame] = None
        self._corridors_cache: Optional[gpd.GeoDataFrame] = None
        self._corridor_metrics_cache: Optional[List[Dict[str, Any]]] = None
        self._corridor_metrics_cache_key: Optional[tuple] = None

    @property
    def delhi_bbox(self) -> tuple:
        """Return bbox as (west, south, east, north)."""
        b = self.settings.delhi_bounds
        return (b["west"], b["south"], b["east"], b["north"])

    def fetch_roads(self, force_refresh: bool = False) -> gpd.GeoDataFrame:
        """
        Fetch walkable road network.
        Prefers local cached GeoJSON file, falling back to OSM Overpass if refresh is forced.
        """
        if self._roads_cache is not None and not force_refresh:
            return self._roads_cache

        cache_path = self.settings.roads_cache_full_path

        # 1. Try loading cached file first
        if not force_refresh and cache_path.exists():
            try:
                gdf = gpd.read_file(cache_path)
                if len(gdf) > 0:
                    if gdf.crs is None:
                        gdf = gdf.set_crs("EPSG:4326")
                    else:
                        gdf = gdf.to_crs("EPSG:4326")
                    print(f"  ✅ Loaded {len(gdf)} road segments from local cache: {cache_path.name}")
                    self._roads_cache = gdf
                    return gdf
            except Exception as e:
                print(f"  ⚠️ Failed to read local road cache ({e}); attempting OSM fetch...")

        # 2. Attempt Overpass API fetch via OSMnx
        try:
            import osmnx as ox
            print("  ⏳ Fetching road network from OpenStreetMap...")
            tags = {
                "highway": ["primary", "secondary", "tertiary", "residential", "living_street", "pedestrian"]
            }
            features = ox.features_from_bbox(bbox=self.delhi_bbox, tags=tags)
            gdf = gpd.GeoDataFrame(features).reset_index()

            valid_types = ["LineString", "MultiLineString"]
            gdf = gdf[gdf.geometry.geom_type.isin(valid_types)].copy()

            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            else:
                gdf = gdf.to_crs("EPSG:4326")

            keep_cols = ["geometry"]
            for col in ["name", "highway", "district"]:
                if col in gdf.columns:
                    keep_cols.append(col)

            gdf = gdf[keep_cols].copy()

            # Ensure ID
            if "id" not in gdf.columns:
                gdf["id"] = [f"osm_road_{i+1:04d}" for i in range(len(gdf))]

            # Save to cache
            try:
                gdf.to_file(cache_path, driver="GeoJSON")
                print(f"  💾 Cached {len(gdf)} segments to {cache_path.name}")
            except Exception:
                pass

            self._roads_cache = gdf
            return gdf

        except Exception as err:
            print(f"  ⚠️ OSM Overpass fetch failed: {err}")
            # If cache file exists, use it as fallback
            if cache_path.exists():
                gdf = gpd.read_file(cache_path)
                if gdf.crs is None:
                    gdf = gdf.set_crs("EPSG:4326")
                self._roads_cache = gdf
                return gdf

            # If no cache exists, return empty GeoDataFrame
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

    def _calculate_length_meters(self, geom) -> float:
        """Calculate geodesic length of geometry in meters."""
        if geom is None or geom.is_empty:
            return 0.0
        try:
            # Project to UTM 43N (Delhi EPSG:32643) for accurate meter measurement
            project = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True).transform
            utm_geom = transform(project, geom)
            return float(utm_geom.length)
        except Exception:
            # Degree approximation fallback at lat 28.6
            return float(geom.length * 111320.0)

    def sample_gdi_along_roads(self, raster_service: RasterService) -> gpd.GeoDataFrame:
        """Sample Green Deficit Index values along road segments."""
        roads = self.fetch_roads()
        if roads is None or len(roads) == 0:
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

        gdi = raster_service.gdi
        transform_affine = raster_service.transform
        if gdi is None or transform_affine is None:
            return roads

        from rasterio.transform import rowcol
        h, w = gdi.shape
        gdi_values = []
        lengths_m = []

        for geom in roads.geometry:
            lengths_m.append(self._calculate_length_meters(geom))
            try:
                if isinstance(geom, MultiLineString):
                    coords = []
                    for line in geom.geoms:
                        coords.extend(list(line.coords))
                else:
                    coords = list(geom.coords)

                if len(coords) == 0:
                    gdi_values.append(np.nan)
                    continue

                num_samples = max(10, int(geom.length / 0.001))
                pixel_vals = []
                for i in range(num_samples):
                    pt = geom.interpolate(i / num_samples, normalized=True)
                    try:
                        r, c = rowcol(transform_affine, pt.x, pt.y)
                        if 0 <= r < h and 0 <= c < w:
                            val = gdi[r, c]
                            if np.isfinite(val):
                                pixel_vals.append(val)
                    except Exception:
                        continue

                gdi_values.append(float(np.mean(pixel_vals)) if pixel_vals else np.nan)
            except Exception:
                gdi_values.append(np.nan)

        roads = roads.copy()
        roads["gdi_mean"] = gdi_values
        roads["length_meters"] = lengths_m
        return roads

    def sample_with_aqi(
        self,
        raster_service: RasterService,
        aqi_service: "AQIService",
        custom_weights: Optional[Dict[str, float]] = None,
    ) -> gpd.GeoDataFrame:
        """
        Sample satellite rasters and assign AQI to road segments.
        Computes 3 distinct outputs: Priority, Feasibility, and Evidence Confidence.
        """
        roads = self.sample_gdi_along_roads(raster_service)
        if roads is None or len(roads) == 0:
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

        aqi_service.fetch_stations()
        ndvi = raster_service.ndvi
        lst = raster_service.lst
        transform_affine = raster_service.transform
        settings = raster_service.settings
        h, w = ndvi.shape if ndvi is not None else (0, 0)

        from rasterio.transform import rowcol

        heat_norms = []
        ndvi_norms = []
        aqi_raws = []
        aqi_norms = []
        priority_scores = []
        feasibility_scores = []
        confidence_scores = []
        is_walkables = []
        pedestrian_scores = []
        vulnerable_scores = []
        signal_breakdowns = []
        active_weights_list = []
        data_source_infos = []
        data_warning_infos = []
        selection_rationales = []

        for idx, row in roads.iterrows():
            geom = row.geometry
            centroid = geom.centroid

            # Sample NDVI and LST
            heat_norm = None
            ndvi_norm = None
            if ndvi is not None and lst is not None and transform_affine is not None:
                try:
                    r, c = rowcol(transform_affine, centroid.x, centroid.y)
                    if 0 <= r < h and 0 <= c < w:
                        ndvi_val = ndvi[r, c]
                        lst_val = lst[r, c]
                        if np.isfinite(ndvi_val):
                            ndvi_norm = float(np.clip(
                                (ndvi_val - settings.ndvi_min) / (settings.ndvi_max - settings.ndvi_min),
                                0.0, 1.0
                            ))
                        if np.isfinite(lst_val):
                            heat_norm = float(np.clip(
                                (lst_val - settings.lst_min) / (settings.lst_max - settings.lst_min),
                                0.0, 1.0
                            ))
                except Exception:
                    pass

            # AQI from nearest station
            aqi_info = aqi_service.get_aqi_at_point(centroid.x, centroid.y)
            aqi_raw = aqi_info.get("aqi_raw")
            aqi_norm = aqi_info.get("aqi_norm")
            aqi_dist = aqi_info.get("distance_km")

            highway_type = row.get("highway")
            district = row.get("district")

            eval_res = compute_priority(
                heat_norm=heat_norm,
                ndvi_norm=ndvi_norm,
                aqi_norm=aqi_norm,
                highway_type=highway_type,
                lon=centroid.x,
                lat=centroid.y,
                district=district,
                custom_weights=custom_weights,
                aqi_distance_km=aqi_dist,
            )

            priority = eval_res["score"]
            feasibility = eval_res["feasibility"]
            confidence = eval_res["confidence"]
            walkable = eval_res["is_walkable"]
            signals = eval_res["signals"]
            weights_used = eval_res["active_weights"]
            sources = eval_res["data_sources"]
            warnings = eval_res["data_warnings"]

            # Descriptive selection rationale
            road_name = row.get("name") or f"Corridor segment {idx}"
            rationale = (
                f"{road_name}: Need priority {priority:.2f} driven by "
                f"heat={signals.get('heat', 0):.2f}, pollution={signals.get('pollution', 0):.2f}, "
                f"green deficit={signals.get('green_deficit', 0):.2f}. "
                f"Feasibility: {feasibility:.2f} ({'Walkable' if walkable else 'Restricted vehicular corridor'}). "
                f"Evidence confidence: {confidence:.2f}."
            )

            heat_norms.append(heat_norm)
            ndvi_norms.append(ndvi_norm)
            aqi_raws.append(aqi_raw)
            aqi_norms.append(aqi_norm)
            priority_scores.append(priority)
            feasibility_scores.append(feasibility)
            confidence_scores.append(confidence)
            is_walkables.append(walkable)
            pedestrian_scores.append(signals.get("pedestrian", 0.5))
            vulnerable_scores.append(signals.get("vulnerable_pop", 0.35))
            signal_breakdowns.append(signals)
            active_weights_list.append(weights_used)
            data_source_infos.append(sources)
            data_warning_infos.append(warnings)
            selection_rationales.append(rationale)

        roads = roads.copy()
        roads["heat_norm"] = heat_norms
        roads["ndvi_norm"] = ndvi_norms
        roads["aqi_raw"] = aqi_raws
        roads["aqi_norm"] = aqi_norms
        roads["priority_score"] = priority_scores
        roads["feasibility"] = feasibility_scores
        roads["confidence"] = confidence_scores
        roads["is_walkable"] = is_walkables
        roads["pedestrian_score"] = pedestrian_scores
        roads["vulnerable_score"] = vulnerable_scores
        roads["priority_signals"] = signal_breakdowns
        roads["active_weights"] = active_weights_list
        roads["data_sources"] = data_source_infos
        roads["data_warnings"] = data_warning_infos
        roads["selection_rationale"] = selection_rationales
        roads["ecological_note"] = (
            "Human pedestrian corridors connect walking routes. True ecological connectivity "
            "requires continuous vegetation canopy and stepping-stone habitat patches for urban fauna."
        )

        return roads

    def detect_corridors(
        self,
        raster_service: RasterService,
        percentile: float = 85,
        aqi_service: Optional["AQIService"] = None,
        custom_weights: Optional[Dict[str, float]] = None,
    ) -> gpd.GeoDataFrame:
        """
        Detect priority corridors based on multi-criteria priority and feasibility.
        """
        if self._corridors_cache is not None and custom_weights is None:
            return self._corridors_cache

        if aqi_service is not None:
            roads = self.sample_with_aqi(raster_service, aqi_service, custom_weights=custom_weights)
            score_col = "priority_score"
        else:
            roads = self.sample_gdi_along_roads(raster_service)
            score_col = "gdi_mean"

        if len(roads) == 0 or score_col not in roads.columns:
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

        valid = roads[roads[score_col].notna()].copy()
        if len(valid) == 0:
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

        threshold = float(valid[score_col].quantile(percentile / 100))
        corridors = valid[valid[score_col] >= threshold].copy()

        # Add ranking and selection metadata
        corridors = corridors.sort_values(by=score_col, ascending=False).reset_index(drop=True)
        corridors["priority_rank"] = range(1, len(corridors) + 1)
        corridors["percentile_threshold"] = percentile
        corridors["threshold_value"] = round(threshold, 3)

        if custom_weights is None:
            self._corridors_cache = corridors

        return corridors

    def roads_to_geojson(self, roads: gpd.GeoDataFrame) -> Dict[str, Any]:
        """Convert GeoDataFrame to GeoJSON dict with clean serialization."""
        if roads is None or len(roads) == 0:
            return {"type": "FeatureCollection", "features": []}

        roads_copy = roads.copy()
        for col in roads_copy.columns:
            if col == "geometry":
                continue
            roads_copy[col] = roads_copy[col].apply(self._make_serializable)

        return json.loads(roads_copy.to_json())

    @staticmethod
    def _make_serializable(x):
        """Convert numpy types, NaN, and complex objects to JSON-safe Python types."""
        if x is None:
            return None
        if isinstance(x, (float, np.floating)):
            return None if np.isnan(x) else float(x)
        if isinstance(x, (int, np.integer)):
            return int(x)
        if isinstance(x, (bool, np.bool_)):
            return bool(x)
        if isinstance(x, dict):
            return {k: RoadService._make_serializable(v) for k, v in x.items()}
        if isinstance(x, list):
            return [RoadService._make_serializable(v) for v in x]
        return x

    def sample_corridor_heat_ndvi(self, raster_service: RasterService) -> List[Dict[str, Any]]:
        """
        Precompute and cache per-corridor normalized Heat [0, 1] and NDVI [0, 1]
        from valid finite raster pixels along each corridor polyline.
        Keyed by the underlying raster array identities so interactive What-if
        slider updates execute instantaneously without re-sampling GeoTIFF rasters,
        while custom/mock rasters in tests are automatically respected.
        """
        ndvi = raster_service.ndvi
        lst = raster_service.lst
        transform_affine = raster_service.transform
        settings = getattr(raster_service, "settings", self.settings) or self.settings

        cache_key = (
            id(ndvi) if ndvi is not None else None,
            id(lst) if lst is not None else None,
            id( self._roads_cache) if self._roads_cache is not None else None,
        )
        if (
            self._corridor_metrics_cache is not None
            and self._corridor_metrics_cache_key == cache_key
        ):
            return self._corridor_metrics_cache

        roads = self.fetch_roads()
        if roads is None or len(roads) == 0:
            return []

        from rasterio.transform import rowcol

        h, w = ndvi.shape if ndvi is not None else (0, 0)
        lst_h, lst_w = lst.shape if lst is not None else (0, 0)

        ndvi_min = getattr(settings, "ndvi_min", -0.2)
        ndvi_max = getattr(settings, "ndvi_max", 0.8)
        lst_min = getattr(settings, "lst_min", 22.0)
        lst_max = getattr(settings, "lst_max", 32.0)

        metrics: List[Dict[str, Any]] = []

        for idx, row in roads.iterrows():
            geom = row.geometry
            corridor_id = str(row.get("id") or f"corridor_{idx+1:03d}")
            name = str(row.get("name") or f"Corridor {corridor_id}")
            district = str(row.get("district") or "NCT of Delhi")
            highway = clean_highway_tag(row.get("highway"))
            length_m = round(self._calculate_length_meters(geom), 1)

            if geom is None or geom.is_empty or ndvi is None or lst is None or transform_affine is None:
                metrics.append({
                    "id": corridor_id,
                    "name": name,
                    "district": district,
                    "highway": highway,
                    "length_meters": length_m,
                    "heat": None,
                    "ndvi": None,
                    "valid_samples": 0,
                    "centroid": None,
                    "geometry": None,
                })
                continue

            centroid = geom.centroid
            num_samples = max(10, int(geom.length / 0.001))
            heat_vals: List[float] = []
            ndvi_vals: List[float] = []

            for i in range(num_samples):
                pt = geom.interpolate(i / num_samples, normalized=True)
                try:
                    r, c = rowcol(transform_affine, pt.x, pt.y)
                    if 0 <= r < h and 0 <= c < w and 0 <= r < lst_h and 0 <= c < lst_w:
                        n_val = float(ndvi[r, c])
                        l_val = float(lst[r, c])
                        if np.isfinite(n_val) and np.isfinite(l_val):
                            n_norm = float(np.clip((n_val - ndvi_min) / (ndvi_max - ndvi_min), 0.0, 1.0))
                            h_norm = float(np.clip((l_val - lst_min) / (lst_max - lst_min), 0.0, 1.0))
                            ndvi_vals.append(n_norm)
                            heat_vals.append(h_norm)
                except Exception:
                    continue

            if len(heat_vals) > 0 and len(ndvi_vals) > 0:
                heat_mean = round(float(np.mean(heat_vals)), 4)
                ndvi_mean = round(float(np.mean(ndvi_vals)), 4)
                valid_count = len(heat_vals)
            else:
                heat_mean = None
                ndvi_mean = None
                valid_count = 0

            metrics.append({
                "id": corridor_id,
                "name": name,
                "district": district,
                "highway": highway,
                "length_meters": length_m,
                "heat": heat_mean,
                "ndvi": ndvi_mean,
                "valid_samples": valid_count,
                "centroid": [round(float(centroid.x), 6), round(float(centroid.y), 6)],
                "geometry": mapping(geom),
            })

        self._corridor_metrics_cache = metrics
        self._corridor_metrics_cache_key = (
            id(ndvi) if ndvi is not None else None,
            id(lst) if lst is not None else None,
            id(self._roads_cache) if self._roads_cache is not None else None,
        )
        return metrics

    def rank_corridors_what_if(
        self,
        raster_service: RasterService,
        heat_weight: float,
        top: int = 5,
        baseline_heat_weight: float = 0.6,
    ) -> Dict[str, Any]:
        """
        Rank corridors dynamically using the What-if Corridor Ranking formula:
            score = heat_weight * Heat + (1 - heat_weight) * (1 - NDVI)
        Also computes Baseline vs. What-if rank & score changes against baseline_heat_weight (0.6).
        """
        raw_metrics = self.sample_corridor_heat_ndvi(raster_service)
        green_deficit_weight = round(1.0 - float(heat_weight), 6)
        heat_w = round(float(heat_weight), 6)
        base_heat_w = round(float(baseline_heat_weight), 6)
        base_green_w = round(1.0 - base_heat_w, 6)

        valid_items: List[Dict[str, Any]] = []
        excluded_no_data = 0

        for m in raw_metrics:
            heat = m.get("heat")
            ndvi = m.get("ndvi")
            if (
                heat is None
                or ndvi is None
                or not np.isfinite(heat)
                or not np.isfinite(ndvi)
            ):
                excluded_no_data += 1
                continue

            heat_f = float(heat)
            ndvi_f = float(ndvi)
            green_deficit = round(1.0 - ndvi_f, 4)

            # Exact formula: score = heat_weight * Heat + (1 - heat_weight) * (1 - NDVI)
            heat_contrib = heat_w * heat_f
            green_contrib = green_deficit_weight * (1.0 - ndvi_f)
            current_score = round(heat_contrib + green_contrib, 4)

            base_heat_contrib = base_heat_w * heat_f
            base_green_contrib = base_green_w * (1.0 - ndvi_f)
            base_score = round(base_heat_contrib + base_green_contrib, 4)

            valid_items.append({
                "id": m["id"],
                "name": m["name"],
                "district": m["district"],
                "highway": m["highway"],
                "length_meters": m["length_meters"],
                "heat": round(heat_f, 4),
                "ndvi": round(ndvi_f, 4),
                "green_deficit": green_deficit,
                "score": current_score,
                "heat_weight": round(heat_w, 4),
                "green_deficit_weight": round(green_deficit_weight, 4),
                "heat_contribution": round(heat_contrib, 4),
                "green_deficit_contribution": round(green_contrib, 4),
                "baseline_score": base_score,
                "baseline_heat_contribution": round(base_heat_contrib, 4),
                "baseline_green_deficit_contribution": round(base_green_contrib, 4),
                "valid_samples": m["valid_samples"],
                "centroid": m["centroid"],
                "geometry": m["geometry"],
            })

        # Deterministic sorting: descending score, then ascending corridor ID for ties
        baseline_sorted = sorted(
            valid_items,
            key=lambda c: (-round(c["baseline_score"], 8), str(c["id"])),
        )
        baseline_rank_map = {
            c["id"]: rank_idx for rank_idx, c in enumerate(baseline_sorted, start=1)
        }

        current_sorted = sorted(
            valid_items,
            key=lambda c: (-round(c["score"], 8), str(c["id"])),
        )

        enriched_all: List[Dict[str, Any]] = []
        for current_rank, item in enumerate(current_sorted, start=1):
            cid = item["id"]
            base_rank = baseline_rank_map[cid]
            rank_change = base_rank - current_rank  # + means moved up (e.g. #3 -> #1 = +2)
            score_change = round(item["score"] - item["baseline_score"], 4)
            in_base_top = base_rank <= top
            in_curr_top = current_rank <= top
            entered_top = (not in_base_top) and in_curr_top
            left_top = in_base_top and (not in_curr_top)

            if entered_top:
                top_status = "entered"
            elif left_top:
                top_status = "left"
            elif in_curr_top and in_base_top:
                top_status = "retained"
            else:
                top_status = "outside"

            enriched_item = {
                "rank": current_rank,
                **item,
                "baseline_rank": base_rank,
                "rank_change": rank_change,
                "score_change": score_change,
                "entered_top_n": entered_top,
                "left_top_n": left_top,
                "top_n_status": top_status,
            }
            enriched_all.append(enriched_item)

        top_corridors = enriched_all[:top]
        comparison_corridors = [
            c for c in enriched_all if c["rank"] <= top or c["baseline_rank"] <= top
        ]
        entered_list = [c for c in enriched_all if c["entered_top_n"]]
        left_list = [c for c in enriched_all if c["left_top_n"]]

        rank_changes = [c["rank_change"] for c in enriched_all]
        max_gain = max(rank_changes) if rank_changes else 0
        max_drop = min(rank_changes) if rank_changes else 0
        shifted_count = sum(1 for c in enriched_all if c["rank_change"] != 0)

        return {
            "corridors": top_corridors,
            "baseline_comparison": {
                "baseline_heat_weight": round(base_heat_w, 4),
                "baseline_green_deficit_weight": round(base_green_w, 4),
                "current_heat_weight": round(heat_w, 4),
                "current_green_deficit_weight": round(green_deficit_weight, 4),
                "top": top,
                "corridors_with_rank_change_count": shifted_count,
                "max_rank_gain": max_gain,
                "max_rank_drop": max_drop,
                "entered_top_n": entered_list,
                "left_top_n": left_list,
                "comparison_table": comparison_corridors,
            },
            "metadata": {
                "heat_weight": round(heat_w, 4),
                "green_deficit_weight": round(green_deficit_weight, 4),
                "baseline_heat_weight": round(base_heat_w, 4),
                "top": top,
                "returned_count": len(top_corridors),
                "total_eligible_corridors": len(enriched_all),
                "excluded_no_data_corridors": excluded_no_data,
                "formula": "score = heat_weight * Heat + (1 - heat_weight) * (1 - NDVI)",
                "tie_breaking_rule": "Descending score, then ascending corridor id",
            },
        }

    def clear_cache(self):
        """Clear memory cache."""
        self._roads_cache = None
        self._corridors_cache = None
        self._corridor_metrics_cache = None
        self._corridor_metrics_cache_key = None
