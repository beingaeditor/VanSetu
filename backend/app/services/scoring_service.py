"""
Scoring Service — 6-Factor Priority Index

Computes a priority score for road segments using 6 weighted signals,
matching the published Priority Index Formula:

    Priority = (Heat × 0.25)
             + (Pollution × 0.20)
             + (Green Deficit × 0.20)
             + (Pedestrian Density × 0.15)
             + (Health Risk Index × 0.12)
             + (Vulnerable Pop. × 0.08)

    Weights sum to 1.00.

Health Risk Index and Vulnerable Population are derived from secondary
(ground-level) user inputs submitted via the community/health data forms.
When no secondary data is available, proxy values are used as fallback.

REAL-TIME DATA SOURCES:
    • Heat           : LST raster (MODIS daily, normalized)
    • Pollution      : Live AQI from monitoring stations (PM2.5 normalized)
    • Green Deficit  : 1 − NDVI (Sentinel-2 10 m, normalized)
    • Pedestrian Dens: OSM highway-tag proxy + community observations
    • Health Risk Idx: Secondary input (heatstroke + dehydration + respiratory
                       cases) with fallback to heat × AQI interaction
    • Vulnerable Pop : Secondary input (reported %) with fallback to zone lookup
"""

import json
from pathlib import Path
from typing import Optional, Dict, List

# ──────────────────────────────────────────────────────────────────────────────
# Weights — MUST sum to 1.0  (matches the Priority Index Formula)
# ──────────────────────────────────────────────────────────────────────────────

WEIGHTS: Dict[str, float] = {
    "heat":           0.25,
    "pollution":      0.20,
    "green_deficit":  0.20,
    "pedestrian":     0.15,
    "health_risk":    0.12,
    "vulnerable_pop": 0.08,
}

assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"


# ──────────────────────────────────────────────────────────────────────────────
# Secondary data loaders  (community & health JSON files)
# ──────────────────────────────────────────────────────────────────────────────

_FEEDBACK_DIR = Path(__file__).parent.parent.parent / "data" / "feedback"
_COMMUNITY_FILE = _FEEDBACK_DIR / "community_data.json"
_HEALTH_FILE = _FEEDBACK_DIR / "health_data.json"


def _load_json(filepath: Path) -> list:
    if filepath.exists():
        with open(filepath, "r") as f:
            return json.load(f)
    return []


def load_health_data() -> List[dict]:
    """Load all health data submissions."""
    return _load_json(_HEALTH_FILE)


def load_community_data() -> List[dict]:
    """Load all community data submissions."""
    return _load_json(_COMMUNITY_FILE)


def health_risk_from_secondary(district: Optional[str] = None) -> Optional[float]:
    """
    Derive Health Risk Index [0, 1] from secondary health data.

    Uses total heat-related cases (heatstroke + dehydration + respiratory)
    normalized against a reference maximum.  Returns None when no data exists
    so the caller can fall back to the proxy.
    """
    records = load_health_data()
    if not records:
        return None

    # Filter by district if specified
    if district:
        records = [r for r in records if r.get("district", "").lower() == district.lower()]
    if not records:
        return None

    # Aggregate the most recent record (or all records for the district)
    total_cases = 0
    emergency_total = 0
    for r in records:
        total_cases += r.get("heatstroke_cases", 0) + r.get("dehydration_cases", 0) + r.get("respiratory_cases", 0)
        emergency_total += r.get("emergency_visits", 0)

    # Normalize: reference max of 500 total cases across a district
    REF_MAX_CASES = 500
    case_score = min(1.0, total_cases / REF_MAX_CASES)

    # Boost by emergency visits (reference max 100)
    REF_MAX_EMERGENCY = 100
    emergency_score = min(1.0, emergency_total / REF_MAX_EMERGENCY)

    # Weighted combination
    return min(1.0, case_score * 0.7 + emergency_score * 0.3)


def vulnerable_pop_from_secondary(district: Optional[str] = None) -> Optional[float]:
    """
    Derive Vulnerable Population score [0, 1] from secondary inputs.

    Uses `vulnerable_population_pct` from health data and
    `vulnerablePopulation` qualitative level from community data.
    Returns None when no data exists so the caller can fall back to the proxy.
    """
    # Try health data first (quantitative)
    health_records = load_health_data()
    if district:
        health_records = [r for r in health_records if r.get("district", "").lower() == district.lower()]

    if health_records:
        pcts = [r.get("vulnerable_population_pct", 0) for r in health_records]
        avg_pct = sum(pcts) / len(pcts)
        return min(1.0, avg_pct / 100.0)

    # Fallback to community data (qualitative)
    community_records = load_community_data()
    if district:
        community_records = [r for r in community_records if r.get("ward", "").lower() == district.lower()]
    if not community_records:
        return None

    level_map = {"low": 0.2, "moderate": 0.45, "high": 0.7, "very high": 0.9}
    scores = []
    for r in community_records:
        lvl = r.get("vulnerablePopulation", "").lower().strip()
        if lvl in level_map:
            scores.append(level_map[lvl])
    if scores:
        return sum(scores) / len(scores)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Proxy / fallback helpers
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
        return 0.50
    tag = highway_type if isinstance(highway_type, str) else str(highway_type)
    tag = tag.strip("[]'\" ").split(",")[0].strip("'\" ")
    return _PEDESTRIAN_MAP.get(tag, 0.50)


def vulnerable_population_proxy(lon: float, lat: float) -> float:
    """
    Fallback: score how close a point is to known vulnerable population zones.
    Used only when no secondary data is available.
    """
    max_score = 0.30
    for z_lat, z_lon, radius, score in _VULNERABLE_ZONES:
        dist = ((lat - z_lat) ** 2 + (lon - z_lon) ** 2) ** 0.5
        if dist <= radius:
            proximity = 1.0 - (dist / radius)
            max_score = max(max_score, score * proximity)
    return min(1.0, max_score)


def health_risk_fallback(heat_norm: Optional[float], aqi_norm: Optional[float]) -> float:
    """
    Fallback Health Risk Index when no secondary health data exists.
    Uses heat × pollution interaction term.
    """
    h = heat_norm if heat_norm is not None else 0.0
    a = aqi_norm if aqi_norm is not None else 0.0
    return min(1.0, h * a * 2.0)


def pedestrian_from_community(district: Optional[str] = None) -> Optional[float]:
    """
    Try to derive pedestrian density from community observations.
    Returns None if no data.
    """
    records = load_community_data()
    if district:
        records = [r for r in records if r.get("ward", "").lower() == district.lower()]
    if not records:
        return None

    level_map = {"low": 0.2, "medium": 0.45, "high": 0.7, "very high": 0.9}
    scores = []
    for r in records:
        lvl = r.get("pedestrianActivity", "").lower().strip()
        if lvl in level_map:
            scores.append(level_map[lvl])
    if scores:
        return sum(scores) / len(scores)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Main scoring function  — 6-Factor Priority Index
# ──────────────────────────────────────────────────────────────────────────────

def compute_priority(
    heat_norm: Optional[float] = None,
    ndvi_norm: Optional[float] = None,
    aqi_norm: Optional[float] = None,
    highway_type: Optional[str] = None,
    lon: float = 77.1,
    lat: float = 28.6,
    district: Optional[str] = None,
) -> Dict[str, float]:
    """
    Compute the 6-factor Priority Index.

    Priority = (Heat × 0.25) + (Pollution × 0.20) + (Green Deficit × 0.20)
             + (Pedestrian Density × 0.15) + (Health Risk Index × 0.12)
             + (Vulnerable Pop. × 0.08)

    Health Risk Index and Vulnerable Pop. are pulled from secondary
    (ground-level) user inputs when available, falling back to proxies.

    Returns:
        Dict with 'score' and per-signal breakdown.
    """
    h = float(heat_norm) if heat_norm is not None else 0.0
    g = float(1.0 - ndvi_norm) if ndvi_norm is not None else 0.5
    a = float(aqi_norm) if aqi_norm is not None else 0.0

    # Pedestrian density: community data first, then OSM highway proxy
    ped_community = pedestrian_from_community(district)
    ped = ped_community if ped_community is not None else pedestrian_proxy(highway_type)

    # Health Risk Index: secondary health data first, then fallback
    hr_secondary = health_risk_from_secondary(district)
    hr = hr_secondary if hr_secondary is not None else health_risk_fallback(heat_norm, aqi_norm)

    # Vulnerable Population: secondary data first, then zone-based proxy
    vp_secondary = vulnerable_pop_from_secondary(district)
    vp = vp_secondary if vp_secondary is not None else vulnerable_population_proxy(lon, lat)

    signals = {
        "heat":           float(h),
        "pollution":      float(a),
        "green_deficit":  float(g),
        "pedestrian":     float(ped),
        "health_risk":    float(hr),
        "vulnerable_pop": float(vp),
    }

    score = sum(WEIGHTS[k] * signals[k] for k in WEIGHTS)
    score = float(max(0.0, min(1.0, score)))

    return {
        "score": score,
        "signals": signals,
        "data_sources": {
            "health_risk": "secondary_input" if hr_secondary is not None else "proxy_heat_x_aqi",
            "vulnerable_pop": "secondary_input" if vp_secondary is not None else "proxy_zone_lookup",
            "pedestrian": "community_input" if ped_community is not None else "proxy_osm_highway",
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Backward compatibility alias
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
    """Backward-compatible wrapper that returns only the scalar score."""
    result = compute_priority(
        heat_norm=heat_norm,
        ndvi_norm=ndvi_norm,
        aqi_norm=aqi_norm,
        highway_type=highway_type,
        lon=lon,
        lat=lat,
    )
    return result["score"]
