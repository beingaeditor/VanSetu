"""
AQI Service — Air Quality Index data ingestion and processing.

Fetches real-time AQI data from OpenAQ API (CPCB/DPCC stations in Delhi)
and provides spatial assignment to road segments.

Data Flow:
    OpenAQ API → AQI Station Cache → Spatial Query → Road Segment Assignment
    
Why AQI was added:
    The original Green Deficit Index (GDI) only considered heat exposure and
    vegetation deficit. However, urban corridors should also prioritize areas
    with high air pollution exposure. By adding AQI as a third signal, we create
    a more comprehensive Multi-Exposure Priority Index that accounts for:
    - Heat stress (LST)
    - Lack of greenery (1 - NDVI) 
    - Air pollution exposure (AQI)
    
    This makes the priority score more defensible and aligned with public health
    objectives, as VanSetu corridors can help with both heat mitigation AND
    air quality improvement through particulate capture.
"""
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import math

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    import urllib.request
    import json as json_module

from app.config import Settings


# =============================================================================
# CONSTANTS — AQI Normalization Parameters
# =============================================================================

# AQI normalization bounds (based on Indian AQI scale)
# Below 50 is "Good" → normalized to 0 (no penalty)
# Above 300 is "Severe" → normalized to 1 (max penalty)
# This creates a defensible, capped normalization that prevents
# extreme AQI values from dominating the priority score.
AQI_NORM_MIN = 50    # Below this, no AQI penalty
AQI_NORM_MAX = 300   # Above this, maximum AQI penalty

# Multi-Exposure Priority Weights (must sum to 1.0)
# Rationale:
# - Heat (0.45): Remains dominant as primary health risk in Delhi summers
# - Green deficit (0.35): Vegetation is key for both heat AND pollution mitigation
# - AQI (0.20): Additive modifier, not dominant, reflects air quality exposure
WEIGHT_HEAT = 0.45
WEIGHT_GREEN_DEFICIT = 0.35  # Applied to (1 - NDVI_norm)
WEIGHT_AQI = 0.20

# WAQI (World Air Quality Index) - free tier, no auth required for basic use
WAQI_BASE_URL = "https://api.waqi.info"
WAQI_TOKEN = "demo"  # Demo token works for basic requests

# OpenAQ API configuration (v3 - requires API key)
OPENAQ_BASE_URL = "https://api.openaq.org/v3"
OPENAQ_LOCATIONS_ENDPOINT = "/locations"

# Delhi bounding box for station filtering
DELHI_BBOX = {
    "north": 28.87,
    "south": 28.40,
    "east": 77.35,
    "west": 76.73
}


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class AQIStation:
    """Represents an air quality monitoring station."""
    station_id: str
    name: str
    latitude: float
    longitude: float
    pm25: Optional[float] = None
    pm10: Optional[float] = None
    timestamp: Optional[datetime] = None
    source: str = "OpenAQ/CPCB"
    
    @property
    def location(self) -> Tuple[float, float]:
        """Return (lon, lat) for spatial operations."""
        return (self.longitude, self.latitude)
    
    @property
    def aqi_raw(self) -> Optional[float]:
        """Return primary AQI value (PM2.5 preferred)."""
        return self.pm25 if self.pm25 is not None else self.pm10
    
    @property
    def aqi_norm(self) -> Optional[float]:
        """
        Return normalized AQI value in [0, 1] range.
        
        Normalization formula:
            AQI_norm = clamp((AQI - 50) / (300 - 50), 0, 1)
        
        Rationale:
        - AQI ≤ 50: "Good" air quality, no penalty → 0
        - AQI ≥ 300: "Severe" air quality, max penalty → 1
        - Linear interpolation between bounds
        """
        if self.aqi_raw is None:
            return None
        return normalize_aqi(self.aqi_raw)


@dataclass 
class AQIStationCache:
    """Thread-safe cache for AQI station data."""
    stations: List[AQIStation] = field(default_factory=list)
    last_updated: Optional[datetime] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def update(self, stations: List[AQIStation]):
        """Update cached stations."""
        with self._lock:
            self.stations = stations
            self.last_updated = datetime.utcnow()
    
    def get_stations(self) -> List[AQIStation]:
        """Get cached stations."""
        with self._lock:
            return self.stations.copy()
    
    def is_stale(self, max_age_hours: int = 1) -> bool:
        """Check if cache is stale."""
        if self.last_updated is None:
            return True
        age = datetime.utcnow() - self.last_updated
        return age > timedelta(hours=max_age_hours)


# =============================================================================
# Utility Functions
# =============================================================================

def normalize_aqi(aqi_value: float) -> float:
    """
    Normalize AQI value to [0, 1] range using capped linear scaling.
    
    Formula: AQI_norm = clamp((AQI - 50) / (300 - 50), 0, 1)
    
    Args:
        aqi_value: Raw AQI/PM2.5 value
        
    Returns:
        Normalized value in [0, 1], or None if input is None
        
    Examples:
        - AQI 30  → 0.0   (Good air, no penalty)
        - AQI 50  → 0.0   (Threshold for penalty)
        - AQI 175 → 0.5   (Moderate penalty)
        - AQI 300 → 1.0   (Maximum penalty)
        - AQI 400 → 1.0   (Capped at max)
    """
    if aqi_value is None:
        return None
    normalized = (aqi_value - AQI_NORM_MIN) / (AQI_NORM_MAX - AQI_NORM_MIN)
    return max(0.0, min(1.0, normalized))


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Calculate great-circle distance between two points in kilometers.
    
    Used for finding nearest AQI station to a road segment centroid.
    """
    R = 6371  # Earth's radius in km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def compute_multi_exposure_priority(
    heat_norm: float,
    ndvi_norm: float,
    aqi_norm: Optional[float] = None
) -> float:
    """
    Compute Multi-Exposure Priority score.
    
    Formula:
        Priority = 0.45 × heat_norm + 0.35 × (1 - ndvi_norm) + 0.20 × aqi_norm
    
    If AQI is not available, falls back to original GDI formula with
    adjusted weights to maintain sum of 1.0:
        Priority = 0.6 × heat_norm + 0.4 × (1 - ndvi_norm)
    
    Args:
        heat_norm: Normalized LST value [0, 1] (higher = hotter)
        ndvi_norm: Normalized NDVI value [0, 1] (higher = greener)
        aqi_norm: Optional normalized AQI value [0, 1] (higher = worse air)
        
    Returns:
        Priority score in [0, 1] (higher = needs more intervention)
    """
    green_deficit = 1.0 - ndvi_norm  # Invert NDVI: low vegetation = high deficit
    
    if aqi_norm is not None:
        # Full multi-exposure formula
        priority = (
            WEIGHT_HEAT * heat_norm +
            WEIGHT_GREEN_DEFICIT * green_deficit +
            WEIGHT_AQI * aqi_norm
        )
    else:
        # Fallback to original GDI weights when AQI unavailable
        # This ensures backward compatibility and graceful degradation
        priority = 0.6 * heat_norm + 0.4 * green_deficit
    
    return max(0.0, min(1.0, priority))


# =============================================================================
# AQI Service Class
# =============================================================================

class AQIService:
    """
    Service for fetching and managing Air Quality Index data.
    
    Integrates with OpenAQ API to fetch real-time AQI data from
    CPCB/DPCC monitoring stations in Delhi NCT.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._cache = AQIStationCache()
        self._lock = threading.Lock()
    
    @property
    def stations(self) -> List[AQIStation]:
        """Get cached AQI stations."""
        return self._cache.get_stations()
    
    @property
    def last_updated(self) -> Optional[datetime]:
        """Get timestamp of last data fetch."""
        return self._cache.last_updated
    
    def fetch_stations(self, force_refresh: bool = False) -> List[AQIStation]:
        """
        Fetch AQI station data from available APIs.
        
        Tries WAQI first (free, no auth), then OpenAQ, then fallback.
        
        Args:
            force_refresh: Force re-fetch even if cache is fresh
            
        Returns:
            List of AQIStation objects with latest measurements
        """
        # Check cache first
        if not force_refresh and not self._cache.is_stale():
            print("  ✅ Using cached AQI data")
            return self._cache.get_stations()
        
        print("  ⏳ Fetching AQI data...")
        
        # Try WAQI first (free, doesn't need auth)
        try:
            stations = self._fetch_from_waqi()
            if stations:
                self._cache.update(stations)
                print(f"  ✅ Fetched {len(stations)} AQI stations from WAQI")
                return stations
        except Exception as e:
            print(f"  ⚠️  WAQI fetch failed: {e}")
        
        # Try OpenAQ as backup
        try:
            stations = self._fetch_from_openaq()
            if stations:
                self._cache.update(stations)
                print(f"  ✅ Fetched {len(stations)} AQI stations from OpenAQ")
                return stations
        except Exception as e:
            print(f"  ⚠️  OpenAQ fetch failed: {e}")
        
        # Use fallback data
        print("  ⚠️  Using fallback AQI data")
        stations = self._get_fallback_stations()
        self._cache.update(stations)
        return stations
    
    def _fetch_from_waqi(self) -> List[AQIStation]:
        """Fetch stations from WAQI API (World Air Quality Index)."""
        stations = []
        
        # WAQI map bounds API - get stations in Delhi area
        bounds_url = f"{WAQI_BASE_URL}/map/bounds/?latlng={DELHI_BBOX['south']},{DELHI_BBOX['west']},{DELHI_BBOX['north']},{DELHI_BBOX['east']}&token={WAQI_TOKEN}"
        
        if HAS_HTTPX:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(bounds_url)
                response.raise_for_status()
                data = response.json()
        else:
            req = urllib.request.Request(bounds_url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json_module.loads(response.read().decode())
        
        if data.get("status") != "ok":
            raise Exception(f"WAQI API error: {data.get('data', 'Unknown error')}")
        
        for station_data in data.get("data", []):
            try:
                lat = station_data.get("lat")
                lon = station_data.get("lon")
                aqi = station_data.get("aqi")
                
                if lat is None or lon is None:
                    continue
                
                # Skip invalid AQI values (WAQI uses "-" for unavailable)
                if aqi == "-" or aqi is None:
                    continue
                
                try:
                    aqi_value = float(aqi)
                except (ValueError, TypeError):
                    continue
                
                station = AQIStation(
                    station_id=str(station_data.get("uid", f"waqi_{lat}_{lon}")),
                    name=station_data.get("station", {}).get("name", "Unknown") if isinstance(station_data.get("station"), dict) else str(station_data.get("station", "Unknown")),
                    latitude=float(lat),
                    longitude=float(lon),
                    pm25=aqi_value,  # WAQI returns composite AQI, primarily PM2.5 based
                    pm10=None,
                    timestamp=datetime.now(),
                    source="WAQI"
                )
                stations.append(station)
                
            except Exception:
                continue
        
        return stations
    
    def _fetch_from_openaq(self) -> List[AQIStation]:
        """Fetch stations from OpenAQ API v3."""
        stations = []
        
        # OpenAQ v3 uses bbox format: west,south,east,north
        params = {
            "bbox": f"{DELHI_BBOX['west']},{DELHI_BBOX['south']},{DELHI_BBOX['east']},{DELHI_BBOX['north']}",
            "limit": 100,
        }
        
        url = f"{OPENAQ_BASE_URL}{OPENAQ_LOCATIONS_ENDPOINT}"
        headers = {
            "Accept": "application/json",
            "X-API-Key": self.settings.openaq_api_key
        }
        
        if HAS_HTTPX:
            # Use httpx if available (better async support)
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
        else:
            # Fallback to urllib
            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            full_url = f"{url}?{query_string}"
            req = urllib.request.Request(full_url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json_module.loads(response.read().decode())
        
        # Parse v3 response format
        results = data.get("results", [])
        
        # Collect location IDs that have PM2.5 sensors and recent data
        location_ids = []
        location_info = {}
        
        for loc in results:
            try:
                coords = loc.get("coordinates", {})
                lat = coords.get("latitude")
                lon = coords.get("longitude")
                
                # Filter to Delhi bounds
                if lat is None or lon is None:
                    continue
                if not (DELHI_BBOX["south"] <= lat <= DELHI_BBOX["north"]):
                    continue
                if not (DELHI_BBOX["west"] <= lon <= DELHI_BBOX["east"]):
                    continue
                
                # Check if station has PM2.5 sensor
                has_pm25 = any(
                    'pm25' in s.get('parameter', {}).get('name', '').lower()
                    for s in loc.get('sensors', [])
                )
                
                if has_pm25:
                    loc_id = loc.get('id')
                    location_ids.append(loc_id)
                    location_info[loc_id] = {
                        'name': loc.get('name', 'Unknown'),
                        'lat': lat,
                        'lon': lon
                    }
            except Exception:
                continue
        
        # Fetch latest measurements for each location (batch if possible)
        for loc_id in location_ids[:30]:  # Limit to 30 stations to avoid rate limits
            try:
                latest_url = f"{OPENAQ_BASE_URL}/locations/{loc_id}/latest"
                
                if HAS_HTTPX:
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.get(latest_url, headers=headers)
                        if resp.status_code == 200:
                            latest_data = resp.json()
                else:
                    req = urllib.request.Request(latest_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=10) as response:
                        latest_data = json_module.loads(response.read().decode())
                
                # Extract PM2.5 value from latest measurements
                pm25 = None
                pm10 = None
                timestamp = None
                
                for measurement in latest_data.get('results', []):
                    # Match sensor_id to pm25 parameter
                    sensor_id = measurement.get('sensorsId')
                    value = measurement.get('value')
                    dt = measurement.get('datetime', {})
                    
                    # We need to check if this sensor is PM2.5
                    # The sensor name usually contains "pm25"
                    if value is not None and value > 0:
                        # Assume first valid reading is PM2.5 if in expected range
                        if pm25 is None and 0 < value < 1000:
                            pm25 = value
                            timestamp = dt.get('utc') if isinstance(dt, dict) else dt
                
                if pm25 is not None:
                    info = location_info[loc_id]
                    station = AQIStation(
                        station_id=str(loc_id),
                        name=info['name'],
                        latitude=info['lat'],
                        longitude=info['lon'],
                        pm25=pm25,
                        pm10=pm10,
                        timestamp=datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if timestamp else datetime.now(),
                        source="OpenAQ/CPCB"
                    )
                    stations.append(station)
                    
            except Exception:
                continue
        
        return stations
    
    def _get_fallback_stations(self) -> List[AQIStation]:
        """
        Return fallback AQI data when API is unavailable.
        
        Uses representative CPCB stations with typical Delhi AQI values.
        This ensures the system remains functional even without live data.
        """
        # Representative CPCB/DPCC stations in Delhi with typical values
        # These are actual station locations with conservative AQI estimates
        fallback_data = [
            ("CPCB_Anand_Vihar", "Anand Vihar", 28.6469, 77.3164, 180),
            ("CPCB_ITO", "ITO", 28.6289, 77.2405, 160),
            ("CPCB_Punjabi_Bagh", "Punjabi Bagh", 28.6741, 77.1310, 170),
            ("CPCB_Dwarka", "Dwarka Sector 8", 28.5708, 77.0712, 145),
            ("CPCB_RK_Puram", "R.K. Puram", 28.5651, 77.1744, 155),
            ("CPCB_Jahangirpuri", "Jahangirpuri", 28.7253, 77.1656, 175),
            ("CPCB_Rohini", "Rohini", 28.7323, 77.1151, 165),
            ("CPCB_Shadipur", "Shadipur", 28.6514, 77.1595, 150),
            ("CPCB_Siri_Fort", "Siri Fort", 28.5506, 77.2156, 140),
            ("CPCB_Okhla", "Okhla Phase-2", 28.5308, 77.2713, 165),
        ]
        
        return [
            AQIStation(
                station_id=sid,
                name=name,
                latitude=lat,
                longitude=lon,
                pm25=pm25,
                timestamp=datetime.utcnow(),
                source="Fallback/CPCB"
            )
            for sid, name, lat, lon, pm25 in fallback_data
        ]
    
    def get_nearest_station(self, lon: float, lat: float) -> Optional[AQIStation]:
        """
        Find the nearest AQI station to a given point.
        
        Args:
            lon: Longitude of query point
            lat: Latitude of query point
            
        Returns:
            Nearest AQIStation or None if no stations available
        """
        stations = self._cache.get_stations()
        
        if not stations:
            return None
        
        nearest = None
        min_dist = float('inf')
        
        for station in stations:
            dist = haversine_distance(lon, lat, station.longitude, station.latitude)
            if dist < min_dist:
                min_dist = dist
                nearest = station
        
        return nearest
    
    def get_aqi_at_point(self, lon: float, lat: float) -> Dict[str, Any]:
        """
        Get AQI information at a specific point.
        
        Args:
            lon: Longitude
            lat: Latitude
            
        Returns:
            Dict with aqi_raw, aqi_norm, station info, and distance
        """
        station = self.get_nearest_station(lon, lat)
        
        if station is None:
            return {
                "aqi_raw": None,
                "aqi_norm": None,
                "station": None,
                "distance_km": None
            }
        
        distance = haversine_distance(lon, lat, station.longitude, station.latitude)
        
        return {
            "aqi_raw": station.aqi_raw,
            "aqi_norm": station.aqi_norm,
            "station": {
                "id": station.station_id,
                "name": station.name,
                "location": station.location
            },
            "distance_km": round(distance, 2)
        }
    
    def stations_to_geojson(self) -> Dict[str, Any]:
        """Convert stations to GeoJSON format for API response."""
        stations = self._cache.get_stations()
        
        features = []
        for station in stations:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [station.longitude, station.latitude]
                },
                "properties": {
                    "id": station.station_id,
                    "name": station.name,
                    "pm25": station.pm25,
                    "pm10": station.pm10,
                    "aqi_raw": station.aqi_raw,
                    "aqi_norm": station.aqi_norm,
                    "source": station.source,
                    "timestamp": station.timestamp.isoformat() if station.timestamp else None
                }
            }
            features.append(feature)
        
        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "count": len(features),
                "last_updated": self._cache.last_updated.isoformat() if self._cache.last_updated else None
            }
        }
    
    def clear_cache(self):
        """Clear the station cache."""
        self._cache.update([])
