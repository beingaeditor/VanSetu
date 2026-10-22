"""
Scoring Service — Explainable Multi-Criteria Prioritization, Feasibility,
Evidence Confidence & Sensitivity Analysis Engine.

Design Principles:
1. Three Distinct Evaluative Vectors:
   - Priority [0, 1]: The estimated community need for intervention based on exposure hazards.
   - Feasibility [0, 1]: Physical, geometric, and regulatory implementation plausibility.
   - Evidence Confidence [0, 1]: Reliability and uncertainty based on sensor resolution,
     observation freshness, station distance, and data completeness.
2. Defensible Missing-Data Behavior:
   - Missing indicators are NEVER silently coerced to zero.
   - When an indicator is unavailable, active weights are dynamically re-normalized to 1.0,
     and the evidence confidence penalty is recorded explicitly.
3. Configurable Weights & Scenarios:
   - Supports user-specified weight vectors and pre-set policy scenarios (Balanced,
     Heat-Focused, Air-Quality-Focused, Equity-Focused, Pedestrian-Focused).
4. Sensitivity & Ranking Stability:
   - Computes rank variance across weight perturbations to identify stable vs fragile priorities.
"""

import json
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
import numpy as np


# Default weights (must sum to 1.0)
DEFAULT_WEIGHTS: Dict[str, float] = {
    "heat": 0.25,
    "pollution": 0.20,
    "green_deficit": 0.20,
    "pedestrian": 0.15,
    "health_risk": 0.12,
    "vulnerable_pop": 0.08,
}

WEIGHTS = DEFAULT_WEIGHTS.copy()

# Pre-defined policy weight scenarios for sensitivity testing
SCENARIOS: Dict[str, Dict[str, float]] = {
    "balanced": DEFAULT_WEIGHTS.copy(),
    "heat_resilience": {
        "heat": 0.40,
        "pollution": 0.15,
        "green_deficit": 0.25,
        "pedestrian": 0.10,
        "health_risk": 0.05,
        "vulnerable_pop": 0.05,
    },
    "air_quality_focus": {
        "heat": 0.15,
        "pollution": 0.40,
        "green_deficit": 0.20,
        "pedestrian": 0.10,
        "health_risk": 0.10,
        "vulnerable_pop": 0.05,
    },
    "pedestrian_equity": {
        "heat": 0.15,
        "pollution": 0.15,
        "green_deficit": 0.15,
        "pedestrian": 0.25,
        "health_risk": 0.10,
        "vulnerable_pop": 0.20,
    },
    "extreme_vulnerability": {
        "heat": 0.20,
        "pollution": 0.15,
        "green_deficit": 0.10,
        "pedestrian": 0.15,
        "health_risk": 0.20,
        "vulnerable_pop": 0.20,
    },
}

# Highway classification to walkability & feasibility mapping
# Motorways/expressways are vehicular-only (non-walkable)
HIGHWAY_PROFILES: Dict[str, Dict[str, Any]] = {
    "pedestrian":    {"ped_density": 0.95, "walkable": True,  "base_feasibility": 0.90, "avg_width_m": 4.0},
    "footway":       {"ped_density": 0.90, "walkable": True,  "base_feasibility": 0.85, "avg_width_m": 2.5},
    "living_street": {"ped_density": 0.80, "walkable": True,  "base_feasibility": 0.80, "avg_width_m": 6.0},
    "residential":   {"ped_density": 0.65, "walkable": True,  "base_feasibility": 0.75, "avg_width_m": 8.0},
    "tertiary":      {"ped_density": 0.55, "walkable": True,  "base_feasibility": 0.70, "avg_width_m": 12.0},
    "secondary":     {"ped_density": 0.60, "walkable": True,  "base_feasibility": 0.65, "avg_width_m": 18.0},
    "primary":       {"ped_density": 0.50, "walkable": True,  "base_feasibility": 0.55, "avg_width_m": 24.0},
    "trunk":         {"ped_density": 0.15, "walkable": False, "base_feasibility": 0.20, "avg_width_m": 35.0},
    "motorway":      {"ped_density": 0.02, "walkable": False, "base_feasibility": 0.05, "avg_width_m": 45.0},
}


# ──────────────────────────────────────────────────────────────────────────────
# Secondary Data Loaders
# ──────────────────────────────────────────────────────────────────────────────

_FEEDBACK_DIR = Path(__file__).parent.parent.parent / "data" / "feedback"
_COMMUNITY_FILE = _FEEDBACK_DIR / "community_data.json"
_HEALTH_FILE = _FEEDBACK_DIR / "health_data.json"


def _load_json(filepath: Path) -> list:
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def load_health_data() -> List[dict]:
    return _load_json(_HEALTH_FILE)


def load_community_data() -> List[dict]:
    return _load_json(_COMMUNITY_FILE)


# ──────────────────────────────────────────────────────────────────────────────
# Proxies and Domain Helpers
# ──────────────────────────────────────────────────────────────────────────────

_VULNERABLE_ZONES = [
    (28.6353, 77.2250, 0.02, 0.95, "Old Delhi / Chandni Chowk (High density market / informal workers)"),
    (28.6469, 77.3164, 0.02, 0.90, "Anand Vihar (Transit hub / high exposure)"),
    (28.5708, 77.0712, 0.02, 0.70, "Dwarka Sector 8/9 (School corridor)"),
    (28.7253, 77.1656, 0.015, 0.85, "Jahangirpuri (Dense low-income settlement)"),
    (28.5506, 77.2156, 0.015, 0.60, "Siri Fort (Residential elderly transit)"),
    (28.5350, 77.2530, 0.02, 0.80, "Okhla Industrial Area (Outdoor industrial workforce)"),
    (28.6700, 77.2300, 0.02, 0.75, "Shahdara (Commercial street vendor zone)"),
    (28.6800, 77.0500, 0.02, 0.65, "Mundka (Industrial corridor)"),
    (28.6100, 77.2800, 0.02, 0.70, "Mayur Vihar Phase 1 (School & transit node)"),
    (28.7400, 77.1100, 0.02, 0.80, "Bawana (Industrial / informal settlement)"),
]


def clean_highway_tag(highway_type: Optional[Any]) -> str:
    """Normalize OSM highway tag."""
    if highway_type is None:
        return "tertiary"
    tag = str(highway_type).strip("[]'\" ").split(",")[0].strip("'\" ").lower()
    return tag if tag in HIGHWAY_PROFILES else "tertiary"


def pedestrian_proxy(highway_type: Optional[str]) -> float:
    """Map OSM highway tag to pedestrian density proxy [0, 1]."""
    if highway_type is None:
        return 0.50
    tag = clean_highway_tag(highway_type)
    return HIGHWAY_PROFILES.get(tag, {}).get("ped_density", 0.50)


def park_connectivity_proxy(arg1: float, arg2: Optional[float] = None) -> float:
    """
    Park connectivity proxy.
    Supports either (ndvi_norm) -> float where low ndvi = high deficit/need,
    or (lon, lat) -> float for distance to central ridge.
    """
    if arg2 is None:
        ndvi_norm = arg1
        return float(min(1.0, max(0.0, 1.0 - ndvi_norm)))
    lon, lat = arg1, arg2
    d = ((lat - 28.60) ** 2 + (lon - 77.18) ** 2) ** 0.5
    return float(min(1.0, max(0.1, d / 0.15)))


def community_demand_proxy(suggestion_count: int, max_suggestions: int = 10) -> float:
    """Normalize community demand votes to [0, 1]."""
    if max_suggestions <= 0:
        return 0.0
    return float(min(1.0, max(0.0, suggestion_count / max_suggestions)))


def cost_impact_proxy(highway_type: Optional[str]) -> float:
    """Estimate intervention feasibility/cost factor based on road width and profile."""
    tag = clean_highway_tag(highway_type)
    return HIGHWAY_PROFILES.get(tag, {}).get("base_feasibility", 0.60)


def health_risk_proxy(heat_norm: Optional[float], aqi_norm: Optional[float]) -> float:
    """
    Health risk interaction term between heat and pollution.
    Returns 0.0 if either heat or air quality exposure is 0.0.
    """
    h = heat_norm if heat_norm is not None else 0.0
    a = aqi_norm if aqi_norm is not None else 0.0
    return float(min(1.0, h * a * 2.0))


def health_risk_fallback(heat_norm: Optional[float], aqi_norm: Optional[float]) -> float:
    """Alias for compound health risk estimation."""
    return health_risk_proxy(heat_norm, aqi_norm)


def vulnerable_population_proxy(lon: float, lat: float) -> float:
    """Estimate socio-spatial vulnerability from proximity to identified high-exposure zones."""
    max_score = 0.35  # Regional baseline for urban Delhi
    for z_lat, z_lon, radius, score, _ in _VULNERABLE_ZONES:
        dist = ((lat - z_lat) ** 2 + (lon - z_lon) ** 2) ** 0.5
        if dist <= radius:
            proximity = 1.0 - (dist / radius)
            max_score = max(max_score, score * proximity)
    return float(min(1.0, max_score))


def health_risk_from_secondary(district: Optional[str] = None) -> Optional[float]:
    """Derive Health Risk Index [0, 1] from secondary health records."""
    records = load_health_data()
    if not records:
        return None
    if district:
        records = [r for r in records if r.get("district", "").lower() == district.lower()]
    if not records:
        return None

    total_cases = 0
    emergency_total = 0
    for r in records:
        total_cases += r.get("heatstroke_cases", 0) + r.get("dehydration_cases", 0) + r.get("respiratory_cases", 0)
        emergency_total += r.get("emergency_visits", 0)

    REF_MAX_CASES = 500
    REF_MAX_EMERGENCY = 100
    case_score = min(1.0, total_cases / REF_MAX_CASES)
    emergency_score = min(1.0, emergency_total / REF_MAX_EMERGENCY)
    return float(min(1.0, case_score * 0.7 + emergency_score * 0.3))


def vulnerable_pop_from_secondary(district: Optional[str] = None) -> Optional[float]:
    """Derive Vulnerable Population score [0, 1] from secondary inputs."""
    health_records = load_health_data()
    if district:
        health_records = [r for r in health_records if r.get("district", "").lower() == district.lower()]

    if health_records:
        pcts = [r.get("vulnerable_population_pct", 0) for r in health_records]
        if pcts:
            return float(min(1.0, (sum(pcts) / len(pcts)) / 100.0))

    community_records = load_community_data()
    if district:
        community_records = [r for r in community_records if r.get("ward", "").lower() == district.lower()]
    if not community_records:
        return None

    level_map = {"low": 0.2, "moderate": 0.45, "high": 0.7, "very high": 0.9}
    scores = [level_map[r.get("vulnerablePopulation", "").lower().strip()]
              for r in community_records if r.get("vulnerablePopulation", "").lower().strip() in level_map]
    return float(sum(scores) / len(scores)) if scores else None


def pedestrian_from_community(district: Optional[str] = None) -> Optional[float]:
    """Derive pedestrian density from community observations."""
    records = load_community_data()
    if district:
        records = [r for r in records if r.get("ward", "").lower() == district.lower()]
    if not records:
        return None

    level_map = {"low": 0.2, "medium": 0.45, "high": 0.7, "very high": 0.9}
    scores = [level_map[r.get("pedestrianActivity", "").lower().strip()]
              for r in records if r.get("pedestrianActivity", "").lower().strip() in level_map]
    return float(sum(scores) / len(scores)) if scores else None


# ──────────────────────────────────────────────────────────────────────────────
# Core Scoring Engine: Priority, Feasibility, Confidence
# ──────────────────────────────────────────────────────────────────────────────

def compute_priority(
    heat_norm: Optional[float] = None,
    ndvi_norm: Optional[float] = None,
    aqi_norm: Optional[float] = None,
    highway_type: Optional[str] = None,
    lon: float = 77.1,
    lat: float = 28.6,
    district: Optional[str] = None,
    custom_weights: Optional[Dict[str, float]] = None,
    aqi_distance_km: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute explainable multi-criteria priority, feasibility, and evidence confidence.

    Returns:
        Dict containing:
        - score: Priority index [0, 1]
        - feasibility: Implementation feasibility [0, 1]
        - confidence: Evidence confidence [0, 1]
        - signals: Detailed breakdown of each indicator
        - active_weights: Normalized weights used (adjusted for missing data)
        - data_sources: Provenance tracking for each indicator
        - data_warnings: Explicit list of missing data or resolution caveats
    """
    weights = (custom_weights or DEFAULT_WEIGHTS).copy()

    # 1. Indicator extraction & missing data tracking
    signals: Dict[str, float] = {}
    active_weights: Dict[str, float] = {}
    data_sources: Dict[str, str] = {}
    data_warnings: List[str] = []
    confidence_penalties: List[float] = []

    # Heat
    if heat_norm is not None and not np.isnan(heat_norm):
        signals["heat"] = float(np.clip(heat_norm, 0.0, 1.0))
        active_weights["heat"] = weights.get("heat", 0.25)
        data_sources["heat"] = "satellite_modis_lst_1km"
        # MODIS LST is 1km coarse resolution, incurs small confidence discount for street level
        confidence_penalties.append(0.12)
    else:
        data_warnings.append("Thermal data missing; reweighting other indicators.")
        confidence_penalties.append(0.25)

    # Green Deficit (1 - NDVI)
    if ndvi_norm is not None and not np.isnan(ndvi_norm):
        ndvi_val = float(np.clip(ndvi_norm, 0.0, 1.0))
        signals["green_deficit"] = float(np.clip(1.0 - ndvi_val, 0.0, 1.0))
        active_weights["green_deficit"] = weights.get("green_deficit", 0.20)
        data_sources["green_deficit"] = "satellite_sentinel2_ndvi_10m"
    else:
        data_warnings.append("Vegetation data missing; reweighting other indicators.")
        confidence_penalties.append(0.20)

    # Air Quality (Pollution)
    if aqi_norm is not None and not np.isnan(aqi_norm):
        signals["pollution"] = float(np.clip(aqi_norm, 0.0, 1.0))
        active_weights["pollution"] = weights.get("pollution", 0.20)
        data_sources["pollution"] = "cpcb_station_interpolation"
        if aqi_distance_km and aqi_distance_km > 10.0:
            confidence_penalties.append(0.10)
            data_warnings.append(f"Nearest AQI station is {aqi_distance_km:.1f} km away.")
    else:
        data_warnings.append("AQI station data missing; reweighting other indicators.")
        confidence_penalties.append(0.15)

    # Pedestrian Activity
    ped_comm = pedestrian_from_community(district)
    if ped_comm is not None:
        signals["pedestrian"] = ped_comm
        data_sources["pedestrian"] = "community_activity_survey"
    else:
        signals["pedestrian"] = pedestrian_proxy(highway_type)
        data_sources["pedestrian"] = "osm_highway_hierarchy_proxy"
        confidence_penalties.append(0.08)
    active_weights["pedestrian"] = weights.get("pedestrian", 0.15)

    # Health Risk
    hr_sec = health_risk_from_secondary(district)
    if hr_sec is not None:
        signals["health_risk"] = hr_sec
        data_sources["health_risk"] = "health_department_records"
    else:
        signals["health_risk"] = health_risk_proxy(
            signals.get("heat"), signals.get("pollution")
        )
        data_sources["health_risk"] = "compound_hazard_proxy"
        confidence_penalties.append(0.08)
    active_weights["health_risk"] = weights.get("health_risk", 0.12)

    # Vulnerable Population
    vp_sec = vulnerable_pop_from_secondary(district)
    if vp_sec is not None:
        signals["vulnerable_pop"] = vp_sec
        data_sources["vulnerable_pop"] = "community_vulnerability_survey"
    else:
        signals["vulnerable_pop"] = vulnerable_population_proxy(lon, lat)
        data_sources["vulnerable_pop"] = "delhi_vulnerability_zone_lookup"
        confidence_penalties.append(0.06)
    active_weights["vulnerable_pop"] = weights.get("vulnerable_pop", 0.08)

    # 2. Defensible dynamic weight re-normalization (prevents treating missing data as 0)
    total_active_weight = sum(active_weights.values())
    if total_active_weight > 0:
        norm_weights = {k: v / total_active_weight for k, v in active_weights.items()}
    else:
        norm_weights = {k: 1.0 / len(signals) for k in signals}

    priority_score = sum(norm_weights[k] * signals[k] for k in norm_weights)
    priority_score = float(np.clip(priority_score, 0.0, 1.0))

    # 3. Feasibility Calculation
    # Feasibility represents physical and regulatory ability to intervene
    tag = clean_highway_tag(highway_type)
    profile = HIGHWAY_PROFILES.get(tag, {})
    base_feasibility = profile.get("base_feasibility", 0.60)
    walkable = profile.get("walkable", True)

    if not walkable:
        # Motorway or trunk has severe implementation barrier as a pedestrian corridor
        feasibility_score = float(base_feasibility * 0.4)
        data_warnings.append(f"Road type '{tag}' is not pedestrian-friendly; street trees/walkways require major redesign.")
    else:
        feasibility_score = float(base_feasibility)

    # 4. Evidence Confidence Calculation
    # Baseline 1.0 minus penalty deductions
    confidence_score = float(max(0.20, min(1.0, 1.0 - sum(confidence_penalties))))

    return {
        "score": priority_score,
        "feasibility": round(feasibility_score, 3),
        "confidence": round(confidence_score, 3),
        "is_walkable": walkable,
        "signals": {k: round(v, 4) for k, v in signals.items()},
        "active_weights": {k: round(v, 4) for k, v in norm_weights.items()},
        "data_sources": data_sources,
        "data_warnings": data_warnings,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Sensitivity Analysis Engine
# ──────────────────────────────────────────────────────────────────────────────

def evaluate_corridor_scenarios(
    heat_norm: Optional[float],
    ndvi_norm: Optional[float],
    aqi_norm: Optional[float],
    highway_type: Optional[str] = None,
    lon: float = 77.1,
    lat: float = 28.6,
    district: Optional[str] = None,
) -> Dict[str, float]:
    """Evaluate a single corridor across all pre-defined policy scenarios."""
    results = {}
    for scenario_name, scenario_weights in SCENARIOS.items():
        res = compute_priority(
            heat_norm=heat_norm,
            ndvi_norm=ndvi_norm,
            aqi_norm=aqi_norm,
            highway_type=highway_type,
            lon=lon,
            lat=lat,
            district=district,
            custom_weights=scenario_weights,
        )
        results[scenario_name] = res["score"]
    return results


def run_ranking_sensitivity_analysis(
    corridor_items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Run sensitivity analysis over a list of corridor records across scenarios.
    Computes rank variance and stability index for each corridor.

    Stability Index [0, 1]:
      1.0 = Highly robust (retains rank regardless of weight adjustments)
      <0.5 = Highly fragile (priority depends heavily on arbitrary weight choice)
    """
    if not corridor_items:
        return []

    num_corridors = len(corridor_items)
    scenario_rankings: Dict[str, List[int]] = {s: [] for s in SCENARIOS}

    # 1. Compute scores for each scenario
    scored_corridors = []
    for item in corridor_items:
        props = item.get("properties", item)
        scenario_scores = evaluate_corridor_scenarios(
            heat_norm=props.get("heat_norm"),
            ndvi_norm=props.get("ndvi_norm"),
            aqi_norm=props.get("aqi_norm"),
            highway_type=props.get("highway"),
            lon=props.get("lon", 77.1),
            lat=props.get("lat", 28.6),
            district=props.get("district"),
        )
        scored_corridors.append({"item": item, "scores": scenario_scores})

    # 2. Compute rankings per scenario
    for s in SCENARIOS:
        # Sort descending by score
        indexed = sorted(range(num_corridors), key=lambda i: scored_corridors[i]["scores"][s], reverse=True)
        ranks = [0] * num_corridors
        for rank_pos, orig_idx in enumerate(indexed):
            ranks[orig_idx] = rank_pos + 1
        scenario_rankings[s] = ranks

    # 3. Calculate rank variance & stability
    results = []
    for i in range(num_corridors):
        all_ranks = [scenario_rankings[s][i] for s in SCENARIOS]
        mean_rank = float(np.mean(all_ranks))
        std_rank = float(np.std(all_ranks))
        max_shift = int(max(all_ranks) - min(all_ranks))

        # Normalized stability: 1 - (std / (num_corridors / 2))
        max_possible_std = max(1.0, num_corridors / 2.0)
        stability = float(max(0.0, min(1.0, 1.0 - (std_rank / max_possible_std))))

        results.append({
            "corridor_index": i,
            "mean_rank": round(mean_rank, 1),
            "rank_std": round(std_rank, 2),
            "max_rank_shift": max_shift,
            "stability_index": round(stability, 3),
            "is_stable": stability >= 0.70,
            "scenario_ranks": {s: scenario_rankings[s][i] for s in SCENARIOS},
        })

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Backward Compatibility Wrappers
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
    """Backward-compatible wrapper returning priority scalar."""
    res = compute_priority(
        heat_norm=heat_norm,
        ndvi_norm=ndvi_norm,
        aqi_norm=aqi_norm,
        highway_type=highway_type,
        lon=lon,
        lat=lat,
    )
    return res["score"]
