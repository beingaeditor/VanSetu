"""
Corridor Aggregation Service — Point-Based Connectivity Analysis

This service creates corridors by aggregating spatially continuous high-priority points.

DESIGN PRINCIPLES:
- ❌ Points are NEVER deleted, merged, or modified
- ✅ Corridors reference points, they don't replace them
- ✅ Each point belongs to at most ONE corridor
- ✅ Corridors are deterministic and reproducible

WHY DISTANCE-BASED CONNECTIVITY:
- Street-scale continuity (30m default matches typical block spacing)
- Avoids jumping across urban blocks
- Based on walkability & exposure literature
- Deterministic and reproducible results

ALGORITHM:
1. Build KD-tree from point coordinates
2. Query pairs within D_max distance
3. Build graph from connected pairs
4. Extract connected components = corridors
5. Filter trivial corridors (< N_min points)
6. Compute corridor metadata (derived only)
"""

import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

import numpy as np
from scipy.spatial import KDTree
from shapely.geometry import Point, LineString, MultiPoint
from shapely.ops import unary_union

from app.config import Settings


class CorridorService:
    """
    Service for point-based corridor aggregation.
    
    Connects spatially continuous high-priority points into corridors
    without modifying or losing any original point data.
    """
    
    # Default configuration
    DEFAULT_D_MAX = 30.0  # meters - connectivity threshold
    DEFAULT_N_MIN = 5     # minimum points for a valid corridor
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._corridors_cache: Optional[List[Dict]] = None
        self._points_cache: Optional[List[Dict]] = None
        
        # Cache directory for persisting corridors
        self.cache_dir = Path(__file__).parent.parent.parent / "cache"
        self.cache_dir.mkdir(exist_ok=True)
    
    def _degrees_to_meters(self, lat: float) -> Tuple[float, float]:
        """
        Convert degrees to approximate meters at a given latitude.
        
        Returns: (meters_per_degree_lon, meters_per_degree_lat)
        """
        # At Delhi's latitude (~28.6°N)
        # 1 degree latitude ≈ 111,320 meters
        # 1 degree longitude ≈ 111,320 * cos(lat) meters
        lat_rad = np.radians(lat)
        meters_per_lat = 111320.0
        meters_per_lon = 111320.0 * np.cos(lat_rad)
        return meters_per_lon, meters_per_lat
    
    def _distance_meters(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """
        Calculate approximate distance in meters between two lat/lng points.
        Uses Haversine approximation for small distances.
        """
        lon1, lat1 = p1
        lon2, lat2 = p2
        
        avg_lat = (lat1 + lat2) / 2
        meters_per_lon, meters_per_lat = self._degrees_to_meters(avg_lat)
        
        dx = (lon2 - lon1) * meters_per_lon
        dy = (lat2 - lat1) * meters_per_lat
        
        return np.sqrt(dx * dx + dy * dy)
    
    def _d_max_to_degrees(self, d_max_meters: float, center_lat: float) -> float:
        """
        Convert D_max from meters to approximate degrees for KD-tree query.
        Uses the average conversion factor at the given latitude.
        """
        meters_per_lon, meters_per_lat = self._degrees_to_meters(center_lat)
        # Use the average of lon/lat conversion (conservative estimate)
        avg_meters_per_degree = (meters_per_lon + meters_per_lat) / 2
        return d_max_meters / avg_meters_per_degree
    
    def _build_connectivity_graph(
        self, 
        points: List[Dict], 
        d_max_meters: float
    ) -> Dict[int, List[int]]:
        """
        Build a connectivity graph from points using KD-tree spatial indexing.
        
        Two points are connected if distance(A, B) ≤ D_max.
        
        Args:
            points: List of point dictionaries with 'coordinates' [lon, lat]
            d_max_meters: Maximum connection distance in meters
            
        Returns:
            Adjacency list representation: {point_idx: [connected_point_indices]}
        """
        if len(points) == 0:
            return {}
        
        # Extract coordinates
        coords = np.array([p['coordinates'] for p in points])  # [lon, lat]
        
        # Calculate center latitude for coordinate conversion
        center_lat = np.mean(coords[:, 1])
        
        # Convert D_max to approximate degrees for KD-tree query
        d_max_degrees = self._d_max_to_degrees(d_max_meters, center_lat)
        
        # Build KD-tree (note: KD-tree uses Euclidean distance in coordinate space)
        tree = KDTree(coords)
        
        # Query all pairs within D_max (in degrees)
        pairs = tree.query_pairs(r=d_max_degrees, output_type='ndarray')
        
        # Build adjacency list
        graph: Dict[int, List[int]] = {i: [] for i in range(len(points))}
        
        for i, j in pairs:
            # Double-check actual distance in meters (for accuracy)
            actual_dist = self._distance_meters(coords[i], coords[j])
            if actual_dist <= d_max_meters:
                graph[i].append(j)
                graph[j].append(i)
        
        return graph
    
    def _find_connected_components(self, graph: Dict[int, List[int]]) -> List[List[int]]:
        """
        Find connected components in the graph using BFS.
        
        Each connected component represents one corridor.
        This guarantees:
        - No point is lost
        - No point appears in two corridors
        - Corridors emerge naturally from spatial continuity
        
        Args:
            graph: Adjacency list representation
            
        Returns:
            List of components, each component is a list of point indices
        """
        visited = set()
        components = []
        
        for start_node in graph:
            if start_node in visited:
                continue
            
            # BFS to find all connected nodes
            component = []
            queue = [start_node]
            
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                
                visited.add(node)
                component.append(node)
                
                for neighbor in graph[node]:
                    if neighbor not in visited:
                        queue.append(neighbor)
            
            if component:
                components.append(component)
        
        return components
    
    def _order_points_along_corridor(
        self, 
        points: List[Dict], 
        indices: List[int]
    ) -> List[int]:
        """
        Order points along the corridor using nearest-neighbor chaining.
        
        This is a visual improvement only - it creates a logical ordering
        for rendering the corridor as a line.
        
        Args:
            points: All points
            indices: Indices of points in this corridor
            
        Returns:
            Ordered list of indices
        """
        if len(indices) <= 2:
            return indices
        
        # Extract coordinates for this corridor
        coords = {i: np.array(points[i]['coordinates']) for i in indices}
        
        # Start from the point with minimum longitude (westernmost)
        ordered = [min(indices, key=lambda i: coords[i][0])]
        remaining = set(indices) - {ordered[0]}
        
        # Nearest neighbor chaining
        while remaining:
            last = ordered[-1]
            last_coord = coords[last]
            
            # Find nearest unvisited point
            nearest = min(remaining, key=lambda i: np.linalg.norm(coords[i] - last_coord))
            ordered.append(nearest)
            remaining.remove(nearest)
        
        return ordered
    
    def _compute_corridor_geometry(
        self, 
        points: List[Dict], 
        ordered_indices: List[int]
    ) -> Dict[str, Any]:
        """
        Compute corridor geometry (LineString) from ordered points.
        
        Args:
            points: All points
            ordered_indices: Ordered indices for this corridor
            
        Returns:
            GeoJSON geometry object
        """
        coords = [points[i]['coordinates'] for i in ordered_indices]
        
        if len(coords) == 1:
            return {
                "type": "Point",
                "coordinates": coords[0]
            }
        elif len(coords) == 2:
            return {
                "type": "LineString",
                "coordinates": coords
            }
        else:
            return {
                "type": "LineString",
                "coordinates": coords
            }
    
    def _compute_corridor_length(self, points: List[Dict], ordered_indices: List[int]) -> float:
        """
        Compute approximate corridor length in meters.
        Sum of inter-point distances along the ordered chain.
        """
        if len(ordered_indices) < 2:
            return 0.0
        
        total_length = 0.0
        for i in range(len(ordered_indices) - 1):
            p1 = points[ordered_indices[i]]['coordinates']
            p2 = points[ordered_indices[i + 1]]['coordinates']
            total_length += self._distance_meters(p1, p2)
        
        return total_length
    
    def _compute_corridor_metadata(
        self, 
        points: List[Dict], 
        indices: List[int],
        corridor_geometry: Dict,
        corridor_length: float
    ) -> Dict[str, Any]:
        """
        Compute derived metadata for a corridor.
        
        ⚠️ This does NOT modify underlying point records.
        All metadata is derived from existing point data.
        
        Args:
            points: All points
            indices: Indices of points in this corridor
            corridor_geometry: GeoJSON geometry
            corridor_length: Length in meters
            
        Returns:
            Corridor metadata dictionary
        """
        corridor_points = [points[i] for i in indices]
        
        # Extract values, handling missing data gracefully
        priority_scores = [p.get('priority_score') for p in corridor_points if p.get('priority_score') is not None]
        aqi_values = [p.get('aqi_norm') for p in corridor_points if p.get('aqi_norm') is not None]
        heat_values = [p.get('heat_norm') for p in corridor_points if p.get('heat_norm') is not None]
        ndvi_values = [p.get('ndvi_norm') for p in corridor_points if p.get('ndvi_norm') is not None]
        
        # Determine dominant exposure type
        mean_heat = np.mean(heat_values) if heat_values else 0
        mean_green_deficit = 1 - np.mean(ndvi_values) if ndvi_values else 0
        mean_aqi = np.mean(aqi_values) if aqi_values else 0
        
        exposure_scores = {
            'heat': mean_heat,
            'green_deficit': mean_green_deficit,
            'air_quality': mean_aqi
        }
        dominant_exposure = max(exposure_scores, key=exposure_scores.get) if exposure_scores else 'unknown'
        
        return {
            'mean_priority': float(np.mean(priority_scores)) if priority_scores else None,
            'mean_aqi': float(np.mean(aqi_values)) if aqi_values else None,
            'mean_heat': float(np.mean(heat_values)) if heat_values else None,
            'mean_ndvi': float(np.mean(ndvi_values)) if ndvi_values else None,
            'dominant_exposure': dominant_exposure,
            'corridor_length_m': corridor_length,
        }
    
    def aggregate_corridors(
        self,
        high_priority_points: List[Dict],
        d_max_meters: float = None,
        n_min: int = None
    ) -> List[Dict]:
        """
        Aggregate high-priority points into corridors.
        
        ALGORITHM:
        1. Build connectivity graph using KD-tree
        2. Extract connected components
        3. Filter trivial corridors (< N_min points)
        4. Compute corridor metadata
        
        Args:
            high_priority_points: List of point dictionaries, each with:
                - point_id: Unique identifier
                - coordinates: [lon, lat]
                - priority_score: Multi-exposure priority
                - aqi_norm, heat_norm, ndvi_norm: Component scores
            d_max_meters: Maximum connection distance (default: 30m)
            n_min: Minimum points for valid corridor (default: 5)
            
        Returns:
            List of corridor dictionaries
        """
        d_max = d_max_meters if d_max_meters is not None else self.DEFAULT_D_MAX
        n_min = n_min if n_min is not None else self.DEFAULT_N_MIN
        
        if len(high_priority_points) == 0:
            return []
        
        print(f"  🔗 Building connectivity graph (D_max={d_max}m)...")
        
        # Step 1: Build connectivity graph
        graph = self._build_connectivity_graph(high_priority_points, d_max)
        
        # Step 2: Find connected components
        components = self._find_connected_components(graph)
        
        print(f"  📊 Found {len(components)} connected components")
        
        # Step 3: Filter trivial corridors and build corridor objects
        corridors = []
        orphan_count = 0
        
        for component in components:
            if len(component) < n_min:
                # Points remain visible individually, just don't form a corridor
                orphan_count += len(component)
                continue
            
            # Order points for visualization
            ordered_indices = self._order_points_along_corridor(high_priority_points, component)
            
            # Compute geometry
            geometry = self._compute_corridor_geometry(high_priority_points, ordered_indices)
            
            # Compute length
            length = self._compute_corridor_length(high_priority_points, ordered_indices)
            
            # Compute metadata
            metadata = self._compute_corridor_metadata(
                high_priority_points, 
                ordered_indices,
                geometry,
                length
            )
            
            # Build corridor object
            corridor = {
                'corridor_id': str(uuid.uuid4()),
                'point_ids': [high_priority_points[i]['point_id'] for i in ordered_indices],
                'num_points': len(ordered_indices),
                'geometry': geometry,
                **metadata,
                'created_at': datetime.utcnow().isoformat() + 'Z'
            }
            
            corridors.append(corridor)
        
        print(f"  🛤️  Created {len(corridors)} corridors (filtered {orphan_count} orphan points)")
        
        # Sort by mean priority (highest first)
        corridors.sort(key=lambda c: c.get('mean_priority') or 0, reverse=True)
        
        return corridors
    
    def get_corridors_from_road_segments(
        self,
        road_geojson: Dict[str, Any],
        d_max_meters: float = None,
        n_min: int = None,
        percentile_threshold: float = 85
    ) -> Dict[str, Any]:
        """
        Convert road segment GeoJSON to high-priority points and aggregate into corridors.
        
        This method bridges the existing road-based system with the new point-based
        corridor aggregation.
        
        Args:
            road_geojson: GeoJSON FeatureCollection of road segments
            d_max_meters: Maximum connection distance
            n_min: Minimum points for valid corridor
            percentile_threshold: Only include points above this priority percentile
            
        Returns:
            Dictionary with corridors and original points
        """
        features = road_geojson.get('features', [])
        
        if not features:
            return {
                'corridors': [],
                'points': [],
                'metadata': {'total_points': 0, 'total_corridors': 0}
            }
        
        # Convert road segments to points (use centroids)
        all_points = []
        for idx, feature in enumerate(features):
            geom = feature.get('geometry', {})
            props = feature.get('properties', {})
            
            # Get centroid of the road segment
            coords = geom.get('coordinates', [])
            if geom.get('type') == 'LineString' and len(coords) >= 2:
                # Use midpoint of the line
                mid_idx = len(coords) // 2
                centroid = coords[mid_idx]
            elif geom.get('type') == 'MultiLineString' and coords:
                # Use midpoint of first line
                first_line = coords[0]
                mid_idx = len(first_line) // 2 if first_line else 0
                centroid = first_line[mid_idx] if first_line else [0, 0]
            else:
                continue
            
            point = {
                'point_id': f"pt_{idx}_{hash(str(centroid)) % 100000}",
                'coordinates': centroid,
                'priority_score': props.get('priority_score'),
                'aqi_norm': props.get('aqi_norm'),
                'aqi_raw': props.get('aqi_raw'),
                'heat_norm': props.get('heat_norm'),
                'ndvi_norm': props.get('ndvi_norm'),
                'road_name': props.get('name'),
                'road_type': props.get('highway'),
                'original_geometry': geom
            }
            
            all_points.append(point)
        
        # Filter to high-priority points based on percentile
        priority_scores = [p['priority_score'] for p in all_points if p['priority_score'] is not None]
        
        if not priority_scores:
            return {
                'corridors': [],
                'points': all_points,
                'metadata': {'total_points': len(all_points), 'total_corridors': 0}
            }
        
        threshold = np.percentile(priority_scores, percentile_threshold)
        high_priority_points = [
            p for p in all_points 
            if p['priority_score'] is not None and p['priority_score'] >= threshold
        ]
        
        print(f"  📍 {len(high_priority_points)} high-priority points (top {100-percentile_threshold:.0f}%)")
        
        # Store points for later reference
        self._points_cache = all_points
        
        # Aggregate into corridors
        corridors = self.aggregate_corridors(high_priority_points, d_max_meters, n_min)
        
        # Cache corridors
        self._corridors_cache = corridors
        
        return {
            'corridors': corridors,
            'points': high_priority_points,
            'all_points': all_points,
            'metadata': {
                'total_points': len(all_points),
                'high_priority_points': len(high_priority_points),
                'total_corridors': len(corridors),
                'd_max_meters': d_max_meters or self.DEFAULT_D_MAX,
                'n_min': n_min or self.DEFAULT_N_MIN,
                'percentile_threshold': percentile_threshold
            }
        }
    
    def corridors_to_geojson(self, corridors: List[Dict]) -> Dict[str, Any]:
        """
        Convert corridors to GeoJSON FeatureCollection.
        
        Args:
            corridors: List of corridor dictionaries
            
        Returns:
            GeoJSON FeatureCollection
        """
        features = []
        
        for corridor in corridors:
            feature = {
                'type': 'Feature',
                'geometry': corridor['geometry'],
                'properties': {
                    'corridor_id': corridor['corridor_id'],
                    'num_points': corridor['num_points'],
                    'mean_priority': corridor.get('mean_priority'),
                    'mean_aqi': corridor.get('mean_aqi'),
                    'mean_heat': corridor.get('mean_heat'),
                    'mean_ndvi': corridor.get('mean_ndvi'),
                    'dominant_exposure': corridor.get('dominant_exposure'),
                    'corridor_length_m': corridor.get('corridor_length_m'),
                    'point_ids': corridor['point_ids'],
                    'created_at': corridor.get('created_at')
                }
            }
            features.append(feature)
        
        return {
            'type': 'FeatureCollection',
            'features': features
        }
    
    def points_to_geojson(self, points: List[Dict]) -> Dict[str, Any]:
        """
        Convert points to GeoJSON FeatureCollection.
        
        Args:
            points: List of point dictionaries
            
        Returns:
            GeoJSON FeatureCollection
        """
        features = []
        
        for point in points:
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': point['coordinates']
                },
                'properties': {
                    'point_id': point['point_id'],
                    'priority_score': point.get('priority_score'),
                    'aqi_norm': point.get('aqi_norm'),
                    'aqi_raw': point.get('aqi_raw'),
                    'heat_norm': point.get('heat_norm'),
                    'ndvi_norm': point.get('ndvi_norm'),
                    'road_name': point.get('road_name'),
                    'road_type': point.get('road_type')
                }
            }
            features.append(feature)
        
        return {
            'type': 'FeatureCollection',
            'features': features
        }
    
    def get_corridor_by_id(self, corridor_id: str) -> Optional[Dict]:
        """
        Get a specific corridor by ID.
        
        Args:
            corridor_id: UUID of the corridor
            
        Returns:
            Corridor dictionary or None
        """
        if self._corridors_cache is None:
            return None
        
        for corridor in self._corridors_cache:
            if corridor['corridor_id'] == corridor_id:
                return corridor
        
        return None
    
    def get_points_for_corridor(self, corridor_id: str) -> List[Dict]:
        """
        Get all points belonging to a specific corridor.
        
        Args:
            corridor_id: UUID of the corridor
            
        Returns:
            List of point dictionaries
        """
        corridor = self.get_corridor_by_id(corridor_id)
        if corridor is None or self._points_cache is None:
            return []
        
        point_ids = set(corridor['point_ids'])
        return [p for p in self._points_cache if p['point_id'] in point_ids]
    
    def clear_cache(self):
        """Clear cached corridor and point data."""
        self._corridors_cache = None
        self._points_cache = None
