"""
Intervention Service — Corridor Classification & Green Intervention Suggestions

This service classifies corridors based on their dominant exposure type and
suggests appropriate green infrastructure interventions.

HOW INTERVENTION SUGGESTIONS ARE DERIVED:
=========================================

1. EXPOSURE SHARE CALCULATION:
   - Total = mean_heat + mean_aqi + mean_green_deficit
   - heat_share = mean_heat / Total
   - pollution_share = mean_aqi / Total
   - green_share = mean_green_deficit / Total

2. CLASSIFICATION (primary + secondary):
   - Primary type chosen by dominant share (heat / pollution / green_deficit / mixed)
   - Secondary type chosen by second-highest share (adds cross-cutting suggestions)

3. SEVERITY TIER (from priority score):
   - critical: priority >= 0.70
   - high:     priority >= 0.50
   - moderate: priority <  0.50

4. INTERVENTION SELECTION (deterministic but diverse):
   - 8–12 candidate interventions per type, split into severity tiers
   - 2–3 picked from primary type based on severity
   - 1 picked from secondary type (cross-cutting)
   - 1 picked from contextual add-ons based on specific metric values
   - A hash of the corridor's metric values rotates which candidates are
     selected, so corridors with the same type but different values get
     different suggestions.

This approach ensures:
- Deterministic, reproducible results — same corridor always gets same output
- High diversity — even corridors of the same type get varied suggestions
- No machine learning or complex models
- Clear rationale for each suggestion
- Actionable recommendations for urban planners
"""

import hashlib
from typing import Dict, List, Tuple, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Intervention pools — evidence-based, split by severity tier
# Each type has a large pool; the selector picks a subset per corridor.
# ──────────────────────────────────────────────────────────────────────────────

INTERVENTION_POOLS: Dict[str, Dict] = {
    "heat_dominated": {
        "icon": "🌡️",
        "color": "#d73027",
        "critical": [
            "Dense shade tree canopy (Neem / Peepal / Banyan)",
            "Cool pavement coating with high solar reflectance",
            "Mist-cooling stations at pedestrian nodes",
            "Shaded bus-stop green shelters",
        ],
        "high": [
            "Linear street tree planting (min 8 m canopy spread)",
            "Reflective roofing incentives for adjacent buildings",
            "Pergola-covered walkways with climbing vines",
            "Roadside bioswales with evaporative cooling effect",
        ],
        "moderate": [
            "Median strip tree planting",
            "Green awnings on south-facing facades",
            "Light-colored permeable paving",
            "Community shade garden along setback areas",
        ],
    },
    "pollution_dominated": {
        "icon": "💨",
        "color": "#7b3294",
        "critical": [
            "Multi-row dense vegetation buffer (3–5 m depth)",
            "Vertical green walls on boundary walls",
            "PM-trapping hedge rows (Thevetia / Ficus)",
            "Anti-dust green mesh barriers during construction",
        ],
        "high": [
            "Roadside dense shrub planting for particulate capture",
            "Green screens on pedestrian-side railings",
            "Staggered tree + shrub layering for max filtration",
            "Dust-suppressing ground-cover planting on verges",
        ],
        "moderate": [
            "Single-row pollution-tolerant tree planting",
            "Green noise + dust barrier along flyover edges",
            "Creeper-covered chain-link fencing",
            "Raised planter beds with air-purifying species",
        ],
    },
    "green_deficit": {
        "icon": "🌿",
        "color": "#1a9850",
        "critical": [
            "Pocket park network (every 300 m along corridor)",
            "Continuous green cycle lane with native planting",
            "Reclaim unused road margin for micro-forests (Miyawaki)",
            "Pedestrian-priority green boulevard redesign",
        ],
        "high": [
            "Median green strip with flowering native species",
            "Tree-lined footpath connecting existing parks",
            "Corner-plot pocket gardens at intersections",
            "Rain garden chain along roadside drains",
        ],
        "moderate": [
            "Container-based mobile greenery at key junctions",
            "Climbing-plant trellises on dividers and walls",
            "Community-adopted verge planting program",
            "Weekend pop-up green market zones",
        ],
    },
    "mixed_exposure": {
        "icon": "🌳",
        "color": "#fc8d59",
        "critical": [
            "Multi-functional green corridor: shade + filtration + habitat",
            "Integrated stormwater bio-retention with canopy trees",
            "Complete street redesign: reduce lanes, add green median + buffers",
            "Urban food forest pilot with canopy, shrub, and ground layers",
        ],
        "high": [
            "Combined tree + shrub planting for cooling and dust capture",
            "Green transit corridor: shaded BRT lane with vegetation buffer",
            "Swale-and-shade parkway along arterial service road",
            "Pollinator pathway with native wildflowers and shade trees",
        ],
        "moderate": [
            "Tactical urbanism: painted + potted greenery pilot",
            "Layered planting: ground cover + shrub + small tree",
            "Neighbourhood green link connecting two open spaces",
            "Green signage corridor: information boards + planting",
        ],
    },
    "pedestrian_hotspot": {
        "icon": "🚶",
        "color": "#2166ac",
        "critical": [
            "Continuous shaded pedestrian canopy walkway",
            "Mist-cooling stations at high-footfall junctions",
            "Pedestrian-priority green boulevard with traffic calming",
            "Covered walkways with climbing-vine pergolas",
        ],
        "high": [
            "Street tree planting at 8 m intervals for shade continuity",
            "Shaded bus-stop green shelters with seating",
            "Pedestrian island green pockets at major crossings",
            "Cool-pavement coating on sidewalks and crosswalks",
        ],
        "moderate": [
            "Potted green barriers separating pedestrians from traffic",
            "Green wayfinding signage with planter bases",
            "Community-adopted shaded rest spots every 200 m",
            "Mobile green kiosks at transit stops",
        ],
    },
    "vulnerable_zone": {
        "icon": "🛡️",
        "color": "#b35806",
        "critical": [
            "Priority shade infrastructure near schools and hospitals",
            "Dense tree planting around elderly care facilities",
            "Emergency cooling shelters with green roofs",
            "Vendor-zone green canopy markets",
        ],
        "high": [
            "Green buffer zones around low-income housing clusters",
            "School-route shaded corridors with air-purifying hedges",
            "Community health gardens with native medicinal plants",
            "Street-vendor shade structures with integrated planting",
        ],
        "moderate": [
            "Tree-adoption programs targeting vulnerable neighbourhoods",
            "Mobile green health camps with portable shade",
            "Awareness signage on heat safety with green installations",
            "Neighbourhood pocket parks near community centres",
        ],
    },
}


# Contextual add-on interventions triggered by specific metric conditions.
# Each entry: (condition_fn, suggestion_text)
CONTEXTUAL_ADDONS: List[Tuple] = [
    (lambda h, a, g, p: a is not None and a > 0.7,
     "Install real-time AQI display boards to raise community awareness"),
    (lambda h, a, g, p: h is not None and h > 0.8,
     "Prioritize fast-growing shade species (e.g., Albizia, Cassia) for rapid canopy"),
    (lambda h, a, g, p: g is not None and g > 0.8,
     "Establish tree-adoption program with local residents and schools"),
    (lambda h, a, g, p: p is not None and p > 0.75,
     "Fast-track implementation: deploy pre-grown container trees for immediate impact"),
    (lambda h, a, g, p: h is not None and a is not None and h > 0.5 and a > 0.5,
     "Deploy smog-eating vertical gardens on adjacent building façades"),
    (lambda h, a, g, p: g is not None and g < 0.3,
     "Maintain and protect existing vegetation — add tree guards and no-parking zones"),
    (lambda h, a, g, p: a is not None and a < 0.2,
     "Focus on shade and aesthetics — install ornamental flowering tree avenues"),
    (lambda h, a, g, p: p is not None and p < 0.35,
     "Low-cost beautification: painted kerbs, potted plants, and community murals"),
]


# Classification thresholds
HEAT_THRESHOLD = 0.45      # heat_share >= 0.45 → heat_dominated
POLLUTION_THRESHOLD = 0.40  # pollution_share >= 0.40 → pollution_dominated
GREEN_THRESHOLD = 0.35      # green_share >= 0.35 → green_deficit
PEDESTRIAN_THRESHOLD = 0.70 # pedestrian proxy >= 0.70 → pedestrian_hotspot
VULNERABLE_THRESHOLD = 0.65 # vulnerable proxy >= 0.65 → vulnerable_zone


# ──────────────────────────────────────────────────────────────────────────────
# Subsidy tier definitions
# ──────────────────────────────────────────────────────────────────────────────

SUBSIDY_TIERS = {
    "flagship": {
        "label": "Flagship Corridor",
        "priority_min": 0.70,
        "subsidy_pct": 90,
        "est_cost_per_km_lakhs": (80, 150),
        "promotional_budget_lakhs": 15,
        "description": "Top-priority corridors eligible for full government funding and public launch events.",
    },
    "priority": {
        "label": "Priority Corridor",
        "priority_min": 0.50,
        "subsidy_pct": 70,
        "est_cost_per_km_lakhs": (40, 80),
        "promotional_budget_lakhs": 8,
        "description": "High-need corridors with partial government subsidy and CSR co-funding.",
    },
    "standard": {
        "label": "Standard Corridor",
        "priority_min": 0.0,
        "subsidy_pct": 40,
        "est_cost_per_km_lakhs": (15, 40),
        "promotional_budget_lakhs": 3,
        "description": "Community-led corridors with basic government support.",
    },
}


def get_subsidy_tier(priority: Optional[float]) -> str:
    """Determine subsidy tier from priority score."""
    if priority is None:
        return "standard"
    if priority >= 0.70:
        return "flagship"
    if priority >= 0.50:
        return "priority"
    return "standard"


def get_subsidy_info(priority: Optional[float]) -> Dict:
    """Return full subsidy metadata for a corridor."""
    tier = get_subsidy_tier(priority)
    info = dict(SUBSIDY_TIERS[tier])
    info["tier"] = tier
    return info


def _severity_tier(priority: Optional[float]) -> str:
    """Map priority score to severity tier."""
    if priority is None:
        return "high"
    if priority >= 0.70:
        return "critical"
    if priority >= 0.50:
        return "high"
    return "moderate"


def _deterministic_pick(items: List[str], seed: float, count: int) -> List[str]:
    """
    Deterministically pick `count` items from `items` using a float seed.
    
    Uses a hash of the seed to generate an offset so corridors with different
    metric values select different items even from the same pool.
    """
    if not items:
        return []
    count = min(count, len(items))
    # Convert seed to a stable integer via md5
    digest = hashlib.md5(f"{seed:.6f}".encode()).hexdigest()
    offset = int(digest[:8], 16)
    picked = []
    for i in range(count):
        idx = (offset + i * 7) % len(items)   # stride of 7 for spread
        if items[idx] not in picked:
            picked.append(items[idx])
        else:
            # collision — walk forward to find unused item
            for j in range(1, len(items)):
                alt = (idx + j) % len(items)
                if items[alt] not in picked:
                    picked.append(items[alt])
                    break
    return picked


def classify_corridor(
    mean_heat: Optional[float],
    mean_aqi: Optional[float],
    mean_ndvi: Optional[float],
    priority: Optional[float] = None,
    pedestrian_score: Optional[float] = None,
    vulnerable_score: Optional[float] = None,
) -> Tuple[str, str, Dict]:
    """
    Classify a corridor and return its type, secondary type, and exposure shares.
    
    Now supports 6 corridor types:
        heat_dominated, pollution_dominated, green_deficit,
        pedestrian_hotspot, vulnerable_zone, mixed_exposure
    
    Returns:
        Tuple of (primary_type, secondary_type, shares_dict)
    """
    heat = mean_heat if mean_heat is not None else 0.0
    aqi = mean_aqi if mean_aqi is not None else 0.0
    green_deficit = (1.0 - mean_ndvi) if mean_ndvi is not None else 0.5
    ped = pedestrian_score if pedestrian_score is not None else 0.0
    vuln = vulnerable_score if vulnerable_score is not None else 0.0

    total = heat + aqi + green_deficit
    if total < 0.001:
        total = 0.001  # prevent division by zero

    shares = {
        "heat_share": heat / total,
        "pollution_share": aqi / total,
        "green_share": green_deficit / total,
    }

    # Check new types FIRST (pedestrian_hotspot and vulnerable_zone)
    # These override the exposure-based classification when their signal is strong
    if ped >= PEDESTRIAN_THRESHOLD and ped >= vuln:
        primary_type = "pedestrian_hotspot"
    elif vuln >= VULNERABLE_THRESHOLD:
        primary_type = "vulnerable_zone"
    elif shares["heat_share"] >= HEAT_THRESHOLD:
        primary_type = "heat_dominated"
    elif shares["pollution_share"] >= POLLUTION_THRESHOLD:
        primary_type = "pollution_dominated"
    elif shares["green_share"] >= GREEN_THRESHOLD:
        primary_type = "green_deficit"
    else:
        primary_type = "mixed_exposure"

    # Rank shares to get secondary type
    type_map = [
        ("heat_dominated", shares["heat_share"]),
        ("pollution_dominated", shares["pollution_share"]),
        ("green_deficit", shares["green_share"]),
    ]
    type_map.sort(key=lambda x: x[1], reverse=True)
    secondary_type = type_map[0][0] if type_map[0][0] != primary_type else type_map[1][0]

    return primary_type, secondary_type, shares


def select_interventions(
    primary_type: str,
    secondary_type: str,
    tier: str,
    mean_heat: Optional[float],
    mean_aqi: Optional[float],
    mean_green_deficit: Optional[float],
    priority: Optional[float],
) -> Tuple[List[str], str]:
    """
    Select a diverse set of 3–5 interventions for a corridor.
    
    Returns:
        (list_of_interventions, rationale_text)
    """
    pool_primary = INTERVENTION_POOLS.get(primary_type, INTERVENTION_POOLS["mixed_exposure"])
    pool_secondary = INTERVENTION_POOLS.get(secondary_type, INTERVENTION_POOLS["mixed_exposure"])

    # Build a seed from the actual metric values for deterministic rotation
    seed = (
        (mean_heat or 0.0) * 1000
        + (mean_aqi or 0.0) * 100
        + (mean_green_deficit or 0.0) * 10
        + (priority or 0.0)
    )

    # 1) Pick 2 from primary type at the right severity tier
    primary_candidates = pool_primary.get(tier, pool_primary["high"])
    primary_picks = _deterministic_pick(primary_candidates, seed, 2)

    # 2) Pick 1 from secondary type (cross-cutting) — use a shifted seed
    secondary_candidates = pool_secondary.get(tier, pool_secondary["high"])
    secondary_picks = _deterministic_pick(secondary_candidates, seed + 999, 1)

    # 3) Pick 1 contextual add-on
    contextual_picks = []
    for condition_fn, suggestion in CONTEXTUAL_ADDONS:
        try:
            if condition_fn(mean_heat, mean_aqi, mean_green_deficit, priority):
                contextual_picks.append(suggestion)
        except Exception:
            pass
    # Deterministically pick 1 from qualifying contextual add-ons
    if contextual_picks:
        contextual_pick = _deterministic_pick(contextual_picks, seed + 777, 1)
    else:
        contextual_pick = []

    # Combine — deduplicate while preserving order
    all_picks: List[str] = []
    for item in primary_picks + secondary_picks + contextual_pick:
        if item not in all_picks:
            all_picks.append(item)

    # Build rationale
    type_labels = {
        "heat_dominated": "extreme surface heat",
        "pollution_dominated": "high air pollution",
        "green_deficit": "severe vegetation deficit",
        "mixed_exposure": "multiple environmental stressors",
    }
    primary_label = type_labels.get(primary_type, "environmental stress")
    secondary_label = type_labels.get(secondary_type, "secondary exposure")
    tier_label = {"critical": "Critical", "high": "High", "moderate": "Moderate"}[tier]

    rationale = (
        f"{tier_label}-severity corridor primarily affected by {primary_label}, "
        f"with secondary {secondary_label}. "
        f"Interventions target the dominant exposure while addressing co-benefits."
    )

    return all_picks, rationale


def enrich_corridor_with_interventions(corridor_properties: Dict) -> Dict:
    """
    Enrich corridor properties with intervention classification, suggestions,
    and subsidy tier.
    """
    mean_heat = corridor_properties.get('heat_norm')
    mean_aqi = corridor_properties.get('aqi_norm')
    mean_ndvi = corridor_properties.get('ndvi_norm')
    priority = corridor_properties.get('priority') or corridor_properties.get('priority_score')
    ped_score = corridor_properties.get('pedestrian_score')
    vuln_score = corridor_properties.get('vulnerable_score')

    green_deficit_val = (1.0 - mean_ndvi) if mean_ndvi is not None else 0.5

    primary_type, secondary_type, shares = classify_corridor(
        mean_heat, mean_aqi, mean_ndvi, priority,
        pedestrian_score=ped_score,
        vulnerable_score=vuln_score,
    )
    tier = _severity_tier(priority)

    interventions, rationale = select_interventions(
        primary_type, secondary_type, tier,
        mean_heat, mean_aqi, green_deficit_val, priority,
    )

    pool = INTERVENTION_POOLS.get(primary_type, INTERVENTION_POOLS["mixed_exposure"])

    # Subsidy info
    subsidy = get_subsidy_info(priority)

    enriched = dict(corridor_properties)
    enriched['corridor_type'] = primary_type
    enriched['corridor_type_secondary'] = secondary_type
    enriched['severity_tier'] = tier
    enriched['corridor_type_icon'] = pool['icon']
    enriched['corridor_type_color'] = pool['color']
    enriched['recommended_interventions'] = interventions
    enriched['intervention_rationale'] = rationale
    enriched['subsidy_tier'] = subsidy['tier']
    enriched['subsidy_pct'] = subsidy['subsidy_pct']
    enriched['est_cost_per_km_lakhs'] = subsidy['est_cost_per_km_lakhs']

    return enriched


def enrich_geojson_corridors(geojson: Dict) -> Dict:
    """
    Enrich all corridors in a GeoJSON FeatureCollection with intervention data.
    """
    if not geojson or 'features' not in geojson:
        return geojson

    enriched_features = []
    for feature in geojson.get('features', []):
        if feature.get('properties'):
            feature['properties'] = enrich_corridor_with_interventions(feature['properties'])
        enriched_features.append(feature)

    return {
        **geojson,
        'features': enriched_features
    }
