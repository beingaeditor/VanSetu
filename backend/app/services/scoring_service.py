"""
Scoring Service — 10-Factor Multi-Exposure Priority Index

Computes a comprehensive priority score for road segments using 10 weighted
signals derived from raster data, AQI stations, road metadata, and community
feedback.

SIGNAL WEIGHTS (sum = 1.0):
    Heat Intensity          0.20   LST-based normalized temperature
    Green Deficit           0.15   1 − NDVI (lack of vegetation)
    AQI (Air Quality)       0.15   PM2.5 normalized
    Pedestrian Density      0.15   Highway-type proxy
    Vulnerable Population   0.10   Simulated zone proximity
    Park Connectivity       0.08   Inverse distance to green space
    Community Demand        0.07   Suggestion count normalized
    Cost-Impact Efficiency  0.05   Road-category inverse (narrow = cheaper)
    Health Risk             0.05   Heat × AQI interaction term

PROXY SIGNALS (no new data sources required):
    • Pedestrian density   : mapped from OSM highway tag
    • Vulnerable population: zone-based lookup for known Delhi areas
    • Park connectivity    : inverse of distance to nearest NDVI>0.4 pixel
    • Community demand     : per-corridor suggestion count (from MongoDB or fallback)
    • Health risk          : multiplicative interaction heat_norm × aqi_norm
    • Cost-impact          : inverse road category ordinal
"""

from typing import Optional, Dict

# ──────────────────────────────────────────────────────────────────────────────
# Weights — MUST sum to 1.0
# ──────────────────────────────────────────────────────────────────────────────

WEIGHTS: Dict[str, float] = {
    "heat":              0.20,
    "green_deficit":     0.15,
    "aqi":               0.15,
    "pedestrian":        0.15,
    "vulnerable_pop":    0.10,
    "park_connectivity": 0.08,
    "community_demand":  0.07,
    "cost_impact":       0.05,
    "health_risk":       0.05,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


# ──────────────────────────────────────────────────────────────────────────────
# Proxy helpers
# ──────────────────────────────────────────────────────────────────────────────

# Highway tag → pedestrian density proxy [0, 1]
_PEDESTRIAN_MAP: Dict[str, float] = {
    "primary":   0.90,
    "secondary": 0.70,
    "tertiary":  0.50,
    "trunk":     0.40,
    "motorway":  0.20,
}

# Known vulnerable zones in Delhi (lat, lon, radius_deg, score)
# Schools, elderly-dense areas, low-income clusters
_VULNERABLE_ZONES = [
    (28.6353, 77.2250, 0.02, 0.95),   # Old Delhi / Chandni Chowk
    (28.6469, 77.3164, 0.02, 0.90),   # Anand Vihar (pollution + vendors)
    (28.5708, 77.0712, 0.02, 0.70),   # Dwarka (school zone)
    (28.7253, 77.1656, 0.015, 0.85),  # Jahangirpuri (low-income)
    (28.5506, 77.2156, 0.015, 0.60),  # Siri Fort (elderly residential)
    (28.5350, 77.2530, 0.02, 0.80),   # Okhla (industrial workers)
    (28.6700, 77.2300, 0.02, 0.75),   # Shahdara (vendors)
    (28.6800, 77.0500, 0.02, 0.65),   # Mundka (industrial)
    (28.6100, 77.2800, 0.02, 0.70),   # Mayur Vihar (school zone)
    (28.7400, 77.1100, 0.02, 0.80),   # Bawana (low-income industrial)
]


def pedestrian_proxy(highway_type: Optional[str]) -> float:
    """Map OSM highway tag to a pedestrian density score [0, 1]."""
    if highway_type is None:
        return 0.50  # default mid-range
    # Handle list-valued highway tags
    tag = highway_type if isinstance(highway_type, str) else str(highway_type)
    tag = tag.strip("[]'\" ").split(",")[0].strip("'\" ")
    return _PEDESTRIAN_MAP.get(tag, 0.50)


def vulnerable_population_proxy(lon: float, lat: float) -> float:
    """
    Score how close a point is to known vulnerable population zones.
    Returns max score among all overlapping zones, or 0.30 baseline.
    """
    max_score = 0.30  # baseline — everyone is somewhat vulnerable
    for z_lat, z_lon, radius, score in _VULNERABLE_ZONES:
        dist = ((lat - z_lat) ** 2 + (lon - z_lon) ** 2) ** 0.5
        if dist <= radius:
            # Linear decay within radius
            proximity = 1.0 - (dist / radius)
            max_score = max(max_score, score * proximity)
    return min(1.0, max_score)


def park_connectivity_proxy(ndvi_norm: Optional[float]) -> float:
    """
    Proxy for how disconnected this point is from existing green space.
    High NDVI = already connected → low need → low score.
    Low NDVI = disconnected → high need → high score.
    """
    if ndvi_norm is None:
        return 0.50
    # Invert and boost low-green areas
    return max(0.0, min(1.0, 1.0 - ndvi_norm * 1.2))


def community_demand_proxy(suggestion_count: int = 0, max_suggestions: int = 10) -> float:
    """
    Normalize suggestion count to [0, 1].
    More community requests → higher demand signal.
    """
    if max_suggestions <= 0:
        return 0.0
    return min(1.0, suggestion_count / max_suggestions)


def cost_impact_proxy(highway_type: Optional[str]) -> float:
    """
    Inverse road category: smaller roads = cheaper interventions = higher efficiency.
    Motorway interventions are very expensive; tertiary streets are cheap.
    """
    cost_map = {
        "tertiary":  0.90,
        "secondary": 0.70,
        "primary":   0.50,
        "trunk":     0.30,
        "motorway":  0.15,
    }
    if highway_type is None:
        return 0.50
    tag = highway_type if isinstance(highway_type, str) else str(highway_type)
    tag = tag.strip("[]'\" ").split(",")[0].strip("'\" ")
    return cost_map.get(tag, 0.50)


def health_risk_proxy(heat_norm: Optional[float], aqi_norm: Optional[float]) -> float:
    """
    Interaction term: areas that are BOTH hot AND polluted carry highest health risk.
    Formula: heat × AQI (multiplicative interaction, capped at 1.0).
    """
    h = heat_norm if heat_norm is not None else 0.0
    a = aqi_norm if aqi_norm is not None else 0.0
    return min(1.0, h * a * 2.0)  # ×2 to amplify non-trivially


# ──────────────────────────────────────────────────────────────────────────────
# Main scoring function
# ──────────────────────────────────────────────────────────────────────────────

def compute_10factor_priority(
    heat_norm: Optional[float] = None,
    ndvi_norm: Optional[float] = None,
    aqi_norm: Optional[float] = None,
    highway_type: Optional[str] = None,
    lon: float = 77.1,
    lat: float = 28.6,
    suggestion_count: int = 0,
    max_suggestions: int = 10,
) -> float:
    """
    Compute the 10-factor Multi-Exposure Priority Index.

    All inputs are optional and gracefully degrade to defaults.

    Args:
        heat_norm:        Normalized LST [0,1]  (higher = hotter)
        ndvi_norm:        Normalized NDVI [0,1]  (higher = greener)
        aqi_norm:         Normalized AQI [0,1]   (higher = worse air)
        highway_type:     OSM highway tag string  (e.g. "primary")
        lon, lat:         Centroid coordinates for zone lookups
        suggestion_count: Number of community suggestions for this corridor
        max_suggestions:  Normalization cap for suggestion count

    Returns:
        Priority score in [0, 1]  (higher = needs more intervention)
    """
    h = heat_norm if heat_norm is not None else 0.0
    g = (1.0 - ndvi_norm) if ndvi_norm is not None else 0.5
    a = aqi_norm if aqi_norm is not None else 0.0

    signals = {
        "heat":              h,
        "green_deficit":     g,
        "aqi":               a,
        "pedestrian":        pedestrian_proxy(highway_type),
        "vulnerable_pop":    vulnerable_population_proxy(lon, lat),
        "park_connectivity": park_connectivity_proxy(ndvi_norm),
        "community_demand":  community_demand_proxy(suggestion_count, max_suggestions),
        "cost_impact":       cost_impact_proxy(highway_type),
        "health_risk":       health_risk_proxy(heat_norm, aqi_norm),
    }

    score = sum(WEIGHTS[k] * signals[k] for k in WEIGHTS)
    return max(0.0, min(1.0, score))
