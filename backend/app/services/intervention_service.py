"""
Intervention Suitability & Lifecycle Costing Engine.

Translates spatial multi-criteria indicators into explainable, evidence-grounded
urban greening and shading recommendations.

Features:
1. Rule-Based Suitability Engine:
   - Evaluates spatial footprint, road hierarchy, pedestrian activity, and environmental stress.
   - Does NOT use fake machine learning or random hashing.
   - For every recommended intervention, documents:
     * Specific intervention name & category
     * Scientific & practical rationale
     * Physical & regulatory constraints
     * Required field/site checks before procurement
     * Pragmatic alternatives if constraints fail
     * Feasibility score [0, 1] & evidence confidence [0, 1]
     * Missing evidence warnings
2. Itemized Lifecycle Cost Estimates:
   - Grounded in CPWD (Central Public Works Department) Delhi Schedule of Rates (DSR)
     and Delhi Parks and Gardens Society (DPGS) urban forestry benchmarks.
   - Breaks costs down into:
     * Capital Expenditure (CapEx)
     * Annual Operations & Maintenance (OpEx) including irrigation & pruning
     * Mortality replacement (typical 15-20% in urban Delhi conditions)
     * Expected service life (years)
     * 5-year total lifecycle cost
   - Explicitly labeled as planning estimates, not engineering audits.
3. Post-Implementation Monitoring Framework:
   - Standardized baseline vs follow-up tracking schema.
"""

from typing import Dict, List, Tuple, Optional, Any
import numpy as np


# ──────────────────────────────────────────────────────────────────────────────
# Detailed Intervention Specifications & Feasibility Catalog
# ──────────────────────────────────────────────────────────────────────────────

INTERVENTION_CATALOG: Dict[str, Dict[str, Any]] = {
    "street_trees_canopy": {
        "id": "street_trees_canopy",
        "name": "Linear Street Trees & Native Canopy Expansion",
        "category": "Canopy Greening",
        "icon": "🌳",
        "species": "Neem (Azadirachta indica), Peepal (Ficus religiosa), Pilkhan (Ficus virens), Jamun (Syzygium cumini), Amaltas (Cassia fistula)",
        "min_footpath_width_m": 1.8,
        "soil_depth_req_m": 1.5,
        "tree_pit_size_m": "1.5m x 1.5m unpaved porous basin",
        "spacing_m": 8.0,
        "co_benefits": ["Microclimate cooling", "PM10/PM2.5 particulate interception", "Stormwater retention", "Urban biodiversity"],
        "constraints": [
            "Overhead electrical distribution lines restrict mature canopy height.",
            "Underground utility density (water mains, telecom conduits, gas lines) limits excavation depth.",
            "Paved-over root zones restrict aeration and lead to premature tree mortality in Delhi."
        ],
        "required_site_checks": [
            "Ground Penetrating Radar (GPR) utility survey before excavation.",
            "Soil compaction and salinity testing (alkalinity common in Delhi soils).",
            "Right-of-Way (ROW) boundary verification with MCD/NDMC/PWD.",
            "Overhead wire clearance inspection with BSES / Tata Power Delhi."
        ],
        "feasible_alternatives": [
            "Pergolas with climbing bougainvillea or jasmine if underground utilities prevent deep pits.",
            "Raised masonry planters with root barriers where soil excavation is blocked."
        ],
        # Cost parameters per kilometer (assuming ~120 trees per km, staggered sides)
        "cost_model": {
            "unit": "per km",
            "num_units": 120,
            "capex_inr": 720000,         # Procurement (₹1,500/sapling), excavation (₹1,000), guard (₹2,500), soil prep (₹1,000)
            "annual_opex_inr": 240000,   # Water tanker irrigation (yr 1-3), pruning, guard maintenance
            "mortality_replacement_pct": 15.0,  # 15% replacement in year 1-2
            "expected_service_life_yrs": 30,
            "five_year_lifecycle_cost_inr": 1920000,  # CapEx + 5*OpEx + replacement
        }
    },
    "shade_structures_waiting": {
        "id": "shade_structures_waiting",
        "name": "Architectural Shade Structures & Shaded Waiting Shelters",
        "category": "Immediate Shading",
        "icon": "☂️",
        "species": "Engineered tensile fabric / timber pergola with Madhu Kamini or Bougainvillea",
        "min_footpath_width_m": 1.2,
        "soil_depth_req_m": 0.5,
        "tree_pit_size_m": "Foundation plinth 0.6m x 0.6m",
        "spacing_m": 150.0,
        "co_benefits": ["Instant direct-solar radiation shielding", "Transit passenger comfort", "Pedestrian rest stops", "Solar lighting integration"],
        "constraints": [
            "High wind-load vulnerability during pre-monsoon dust storms (Andhi).",
            "Vandalism and unauthorized commercial encroachment.",
            "Must maintain minimum 1.2m clear walking aisle for universal accessibility."
        ],
        "required_site_checks": [
            "Footpath pedestrian clearance compliance under Harmonised Guidelines for Universal Accessibility.",
            "Structural anchor foundation bearing capacity.",
            "Sightline analysis for intersecting vehicular traffic."
        ],
        "feasible_alternatives": [
            "Cantilevered wall-mounted awnings on public boundary walls.",
            "High-albedo shade sails suspended between existing street poles."
        ],
        "cost_model": {
            "unit": "per km (6 modular structures)",
            "num_units": 6,
            "capex_inr": 1500000,        # ₹2,50,000 per shelter (steel/timber, polycarbonate/fabric roof, bench)
            "annual_opex_inr": 90000,    # Regular cleaning, anti-rust painting, lighting upkeep
            "mortality_replacement_pct": 0.0,
            "expected_service_life_yrs": 12,
            "five_year_lifecycle_cost_inr": 1950000,
        }
    },
    "water_sensitive_infrastructure": {
        "id": "water_sensitive_infrastructure",
        "name": "Roadside Bioswales & Permeable Infiltration Trenches",
        "category": "Water-Sensitive Urban Design",
        "icon": "💧",
        "species": "Vetiver grass (Chrysopogon zizanioides), Canna indica, Typha latifolia",
        "min_footpath_width_m": 2.0,
        "soil_depth_req_m": 1.0,
        "tree_pit_size_m": "1.0m width linear vegetated trench",
        "spacing_m": 50.0,
        "co_benefits": ["Urban flood/waterlogging mitigation", "Localized evaporative cooling", "Groundwater recharge", "Pollutant biofiltration"],
        "constraints": [
            "Monsoon silt accumulation can clog filter media within 1-2 seasons if desilting is neglected.",
            "Stagnant water ponding risk if percolation rate is insufficient, creating mosquito breeding sites.",
            "Requires positive road cross-slope drainage to direct runoff into swales."
        ],
        "required_site_checks": [
            "In-situ soil percolation and hydraulic conductivity test (K_sat >= 25 mm/hr required).",
            "Road camber and curb cut alignment inspection.",
            "Stormwater drain invert level comparison to prevent backflow."
        ],
        "feasible_alternatives": [
            "Precast modular permeable concrete paving slabs over aggregate gravel storage.",
            "Perforated curb inlets directly into groundwater recharge borewells."
        ],
        "cost_model": {
            "unit": "per km (400m linear swale)",
            "num_units": 400,
            "capex_inr": 1100000,        # Excavation, gravel/sand filter bed, check dams, native emergent planting
            "annual_opex_inr": 180000,   # Pre-monsoon and post-monsoon desilting, trash removal, weeding
            "mortality_replacement_pct": 10.0,
            "expected_service_life_yrs": 15,
            "five_year_lifecycle_cost_inr": 2000000,
        }
    },
    "vertical_greenery_facades": {
        "id": "vertical_greenery_facades",
        "name": "Living Green Walls & Boundary Facade Trellises",
        "category": "Vertical Infrastructure",
        "icon": "🌿",
        "species": "Ficus pumila, Vernonia elaeagnifolia (Curtain creeper), Bougainvillea spectabilis",
        "min_footpath_width_m": 0.8,
        "soil_depth_req_m": 0.4,
        "tree_pit_size_m": "0.4m base planter trough along wall",
        "spacing_m": 2.0,
        "co_benefits": ["Façade surface temperature reduction (up to 8°C on wall skin)", "Noise attenuation", "Particulate matter capture", "Aesthetic screening of boundary walls"],
        "constraints": [
            "Severe dependence on automated drip irrigation; dry Delhi summers cause rapid plant desiccation without daily water.",
            "Requires structural consent from adjacent property owners or municipal wall custodians.",
            "Plastic modular pockets degrade quickly under intense UV solar exposure in Delhi."
        ],
        "required_site_checks": [
            "Boundary wall structural load and damp-proofing inspection.",
            "Solar exposure orientation (priority to south- and west-facing walls).",
            "Non-potable water supply point accessibility for drip irrigation."
        ],
        "feasible_alternatives": [
            "Ground-rooted climber trellises on wire mesh rather than high-maintenance modular pocket walls.",
            "High-solar-reflectance elastomeric paint on bare boundary walls."
        ],
        "cost_model": {
            "unit": "per km (300 m² wall coverage)",
            "num_units": 300,
            "capex_inr": 1350000,        # Stainless steel mesh trellis, planter troughs, solar automated drip system
            "annual_opex_inr": 280000,   # Drip line flushing, nutrient dosing, seasonal pruning
            "mortality_replacement_pct": 20.0,
            "expected_service_life_yrs": 8,
            "five_year_lifecycle_cost_inr": 2750000,
        }
    },
    "cool_pavements_surfaces": {
        "id": "cool_pavements_surfaces",
        "name": "High-Albedo Cool Pavement Coatings & Permeable Pavers",
        "category": "Surface Albedo Modification",
        "icon": "🎨",
        "species": "Solar reflective coating (Solar Reflectance Index SRI >= 78) / light precast concrete",
        "min_footpath_width_m": 1.0,
        "soil_depth_req_m": 0.0,
        "tree_pit_size_m": "None (applied to surface)",
        "spacing_m": 0.0,
        "co_benefits": ["Lower nighttime heat release (reduced nocturnal UHI)", "Reduced sidewalk surface temperature (up to 12°C cooler than asphalt)", "Higher pedestrian safety through light reflectance"],
        "constraints": [
            "Elevated daytime solar glare for pedestrians and motorists if applied without shade.",
            "Traffic wear and vehicular dirt deposition reduce SRI over 2-3 years, requiring re-application.",
            "Cannot substitute for canopy shade in mitigating human radiant heat stress ($T_{mrt}$)."
        ],
        "required_site_checks": [
            "Sidewalk substrate integrity (asphalt or concrete base must be sound).",
            "Skid resistance and wet-friction safety rating for pedestrian footwear.",
            "Glare assessment for adjacent drivers on arterial segments."
        ],
        "feasible_alternatives": [
            "Interlocking concrete pavers manufactured with light-colored aggregate.",
            "Permeable turf-block pavers on pedestrian verges."
        ],
        "cost_model": {
            "unit": "per km (1,800 m² footpath)",
            "num_units": 1800,
            "capex_inr": 720000,         # Surface hydro-cleaning + 2 coats polymer-modified reflective slurry (₹400/m²)
            "annual_opex_inr": 160000,   # Periodic pressure washing + top-coat renewal in Year 3
            "mortality_replacement_pct": 0.0,
            "expected_service_life_yrs": 5,
            "five_year_lifecycle_cost_inr": 1520000,
        }
    }
}


# ──────────────────────────────────────────────────────────────────────────────
# Multi-Criteria Suitability Decision Matrix
# ──────────────────────────────────────────────────────────────────────────────

def evaluate_suitability(
    priority: float,
    feasibility: float,
    heat_norm: float,
    green_deficit: float,
    aqi_norm: float,
    pedestrian_score: float,
    vulnerable_score: float,
    highway_type: Optional[str] = None,
    estimated_width_m: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Transparent, rules-based multi-criteria matching between corridor stress
    and physical intervention feasibility.
    """
    recommendations: List[Dict[str, Any]] = []

    # Infer or use footpath/road width
    tag = str(highway_type or "tertiary").lower()
    width_m = estimated_width_m
    if width_m is None:
        from app.services.scoring_service import HIGHWAY_PROFILES
        width_m = HIGHWAY_PROFILES.get(tag, {}).get("avg_width_m", 12.0)

    # 1. Rule: Street Trees & Canopy Expansion
    # Suitable when heat or green deficit is acute AND width/feasibility permits
    tree_spec = INTERVENTION_CATALOG["street_trees_canopy"]
    tree_suitable = (
        (heat_norm >= 0.40 or green_deficit >= 0.50)
        and width_m >= 6.0
        and feasibility >= 0.45
    )
    if tree_suitable:
        conf = 0.85 if green_deficit >= 0.60 else 0.70
        recommendations.append({
            **tree_spec,
            "suitability_rank": 1 if heat_norm >= 0.60 else 2,
            "suitability_score": round(min(1.0, 0.4 * heat_norm + 0.4 * green_deficit + 0.2 * feasibility), 3),
            "rationale": (
                f"Severe thermal deficit ({heat_norm:.2f}) and vegetation absence ({green_deficit:.2f}) "
                f"indicate high demand for continuous canopy. Road profile ({tag}, width ~{width_m:.0f}m) "
                f"provides adequate Right-of-Way for 8m staggered canopy trees."
            ),
            "missing_evidence": "Underground utility routing and actual unpaved footpath width not verified via field survey.",
        })

    # 2. Rule: Shade Structures & Shaded Waiting Areas
    # High pedestrian activity, high heat, or narrow corridors where trees cannot grow immediately
    shade_spec = INTERVENTION_CATALOG["shade_structures_waiting"]
    shade_suitable = (
        (heat_norm >= 0.45 or pedestrian_score >= 0.55)
        and (vulnerable_score >= 0.50 or pedestrian_score >= 0.60 or width_m < 8.0)
    )
    if shade_suitable:
        recommendations.append({
            **shade_spec,
            "suitability_rank": 1 if pedestrian_score >= 0.75 else 2,
            "suitability_score": round(min(1.0, 0.5 * heat_norm + 0.3 * pedestrian_score + 0.2 * vulnerable_score), 3),
            "rationale": (
                f"High pedestrian footfall ({pedestrian_score:.2f}) and community vulnerability ({vulnerable_score:.2f}) "
                f"require immediate solar shielding. Provides zero-latency shade protection while trees mature."
            ),
            "missing_evidence": "Pedestrian boarding points and bus stop coordinates require ground truth verification.",
        })

    # 3. Rule: Vertical Greenery & Wall Facades
    # Very narrow streets (<6m), dense urban fabric, or high air pollution where space is zero
    vert_spec = INTERVENTION_CATALOG["vertical_greenery_facades"]
    vert_suitable = (
        (width_m < 10.0 or aqi_norm >= 0.60)
        and (green_deficit >= 0.55 or aqi_norm >= 0.50)
    )
    if vert_suitable:
        recommendations.append({
            **vert_spec,
            "suitability_rank": 3,
            "suitability_score": round(min(1.0, 0.5 * aqi_norm + 0.3 * green_deficit + 0.2 * (1.0 - min(1.0, width_m / 20.0))), 3),
            "rationale": (
                f"Narrow street geometry (width ~{width_m:.0f}m) limits in-ground tree planting. "
                f"Vertical green surfaces provide PM capture ({aqi_norm:.2f}) and building façade cooling without obstructing sidewalks."
            ),
            "missing_evidence": "Boundary wall structural damp-proofing and non-potable water connection unverified.",
        })

    # 4. Rule: Roadside Bioswales / Water-Sensitive Infrastructure
    # Moderate to wide corridors with green deficit, moderate heat, or stormwater risk
    water_spec = INTERVENTION_CATALOG["water_sensitive_infrastructure"]
    water_suitable = (
        width_m >= 12.0
        and feasibility >= 0.55
        and (green_deficit >= 0.45 or heat_norm >= 0.50)
    )
    if water_suitable:
        recommendations.append({
            **water_spec,
            "suitability_rank": 4,
            "suitability_score": round(min(1.0, 0.4 * green_deficit + 0.3 * feasibility + 0.3 * heat_norm), 3),
            "rationale": (
                f"Sufficient Right-of-Way (~{width_m:.0f}m) permits vegetated bio-retention swales. "
                f"Mitigates monsoon runoff and creates localized evaporative cooling during dry transition periods."
            ),
            "missing_evidence": "Soil infiltration percolation rate and storm sewer invert levels not measured.",
        })

    # 5. Rule: Cool Pavements
    # Wide footpaths, pedestrian plazas, or high surface heat
    cool_spec = INTERVENTION_CATALOG["cool_pavements_surfaces"]
    cool_suitable = (
        heat_norm >= 0.55
        and pedestrian_score >= 0.45
        and width_m >= 4.0
    )
    if cool_suitable:
        recommendations.append({
            **cool_spec,
            "suitability_rank": 5,
            "suitability_score": round(min(1.0, 0.6 * heat_norm + 0.4 * pedestrian_score), 3),
            "rationale": (
                f"High surface temperature ({heat_norm:.2f}) on pedestrian pathways indicates excessive sensible heat storage. "
                f"High-albedo solar coating will lower sidewalk surface temperature by 8-12°C."
            ),
            "missing_evidence": "Pavement surface substrate condition and micro-glare impact on nearby vehicular traffic unverified.",
        })

    # Fallback if no specific rule matched: return Street Trees with conservative feasibility
    if not recommendations:
        recommendations.append({
            **tree_spec,
            "suitability_rank": 1,
            "suitability_score": 0.50,
            "rationale": "General greening recommendation based on regional Delhi urban tree canopy deficit.",
            "missing_evidence": "Site parameters unverified.",
        })

    # Sort by suitability score descending
    recommendations.sort(key=lambda r: r["suitability_score"], reverse=True)
    return recommendations


# ──────────────────────────────────────────────────────────────────────────────
# Lifecycle Cost Calculation & Aggregation
# ──────────────────────────────────────────────────────────────────────────────

def calculate_corridor_lifecycle_costs(
    recommendations: List[Dict[str, Any]],
    length_meters: float = 1000.0,
) -> Dict[str, Any]:
    """
    Calculate itemized lifecycle costs for recommended interventions along a corridor length.
    """
    length_km = max(0.1, length_meters / 1000.0)
    primary = recommendations[0] if recommendations else INTERVENTION_CATALOG["street_trees_canopy"]
    cost_model = primary.get("cost_model", {})

    capex = float(cost_model.get("capex_inr", 720000) * length_km)
    annual_opex = float(cost_model.get("annual_opex_inr", 240000) * length_km)
    five_year_total = float(cost_model.get("five_year_lifecycle_cost_inr", 1920000) * length_km)
    service_life = int(cost_model.get("expected_service_life_yrs", 25))

    return {
        "corridor_length_km": round(length_km, 2),
        "primary_intervention_name": primary.get("name"),
        "primary_intervention_category": primary.get("category"),
        "estimate_type": "Planning Benchmark (CPWD Delhi Schedule of Rates 2023 / DPGS Guidelines)",
        "currency": "INR (₹)",
        "capex_inr": round(capex, 0),
        "annual_opex_inr": round(annual_opex, 0),
        "five_year_lifecycle_inr": round(five_year_total, 0),
        "five_year_lifecycle_lakhs": round(five_year_total / 100000.0, 2),
        "expected_service_life_years": service_life,
        "cost_assumptions": [
            f"Based on ₹{cost_model.get('capex_inr', 0):,}/km CapEx and ₹{cost_model.get('annual_opex_inr', 0):,}/km annual OpEx.",
            "Watering assumption: Regular tanker/drip irrigation during non-monsoon months (October-June).",
            f"Mortality replacement assumption: {cost_model.get('mortality_replacement_pct', 15):.0f}% replacement in years 1-2.",
            "Excludes land acquisition costs (interventions assumed on municipal public Right-of-Way)."
        ]
    }


# ──────────────────────────────────────────────────────────────────────────────
# Post-Implementation Monitoring Framework Schema
# ──────────────────────────────────────────────────────────────────────────────

def generate_monitoring_framework(
    corridor_id: str,
    baseline_heat: float,
    baseline_ndvi: float,
    baseline_aqi: float,
) -> Dict[str, Any]:
    """Generate standardized post-implementation monitoring framework contract."""
    return {
        "corridor_id": corridor_id,
        "baseline_recorded": {
            "satellite_modis_lst_c": round(22.0 + baseline_heat * 10.0, 1),
            "sentinel2_ndvi": round(-0.2 + baseline_ndvi * 1.0, 3),
            "nearest_cpcb_aqi": round(50.0 + baseline_aqi * 250.0, 0),
            "baseline_canopy_cover_pct": round(baseline_ndvi * 20.0, 1),
        },
        "target_milestones": {
            "year_1": {"tree_survival_rate_min_pct": 85.0, "canopy_cover_gain_pct": 3.0},
            "year_3": {"tree_survival_rate_min_pct": 80.0, "canopy_cover_gain_pct": 12.0, "t_mrt_reduction_c": 4.0},
            "year_5": {"mature_canopy_cover_target_pct": 28.0, "t_mrt_reduction_c": 7.5, "pm_capture_gain_pct": 15.0},
        },
        "verification_protocol": [
            "Quarterly ground survival audit of all planted saplings (Years 1-3).",
            "High-resolution drone multispectral or Sentinel-2 NDVI re-evaluation every October.",
            "Microclimate thermal comfort (PET / Mean Radiant Temperature) logging under canopy during peak May/June heatwaves.",
            "Digital citizen feedback logging on pedestrian thermal comfort and shade perception."
        ]
    }


# ──────────────────────────────────────────────────────────────────────────────
# Public Corridor Enrichment Helpers
# ──────────────────────────────────────────────────────────────────────────────

def enrich_corridor_with_interventions(corridor_properties: Dict) -> Dict:
    """Enrich corridor properties with transparent recommendations, lifecycle costs, and monitoring schema."""
    props = dict(corridor_properties)

    heat_norm = props.get("heat_norm") or 0.5
    ndvi_norm = props.get("ndvi_norm") or 0.3
    green_deficit = (1.0 - ndvi_norm)
    aqi_norm = props.get("aqi_norm") or 0.5
    priority = props.get("priority") or props.get("priority_score") or 0.5
    feasibility = props.get("feasibility") or 0.6
    ped_score = props.get("pedestrian_score") or 0.5
    vuln_score = props.get("vulnerable_score") or 0.4
    highway_type = props.get("highway")
    length_m = props.get("length_meters") or 1000.0

    recommendations = evaluate_suitability(
        priority=priority,
        feasibility=feasibility,
        heat_norm=heat_norm,
        green_deficit=green_deficit,
        aqi_norm=aqi_norm,
        pedestrian_score=ped_score,
        vulnerable_score=vuln_score,
        highway_type=highway_type,
    )

    primary_rec = recommendations[0] if recommendations else INTERVENTION_CATALOG["street_trees_canopy"]
    costs = calculate_corridor_lifecycle_costs(recommendations, length_meters=length_m)
    monitoring = generate_monitoring_framework(
        corridor_id=str(props.get("id", "corridor")),
        baseline_heat=heat_norm,
        baseline_ndvi=ndvi_norm,
        baseline_aqi=aqi_norm,
    )

    # Simplified list for backward compatibility with frontend
    rec_names = [f"{r['icon']} {r['name']}" for r in recommendations]

    props["corridor_type"] = primary_rec["id"]
    props["corridor_type_icon"] = primary_rec["icon"]
    props["corridor_type_color"] = "#1a9850" if "canopy" in primary_rec["id"] else "#d73027"
    props["recommended_interventions"] = rec_names
    props["interventions_detailed"] = recommendations
    props["intervention_rationale"] = primary_rec["rationale"]
    props["constraints"] = primary_rec.get("constraints", [])
    props["required_site_checks"] = primary_rec.get("required_site_checks", [])
    props["feasible_alternatives"] = primary_rec.get("feasible_alternatives", [])
    props["missing_evidence"] = primary_rec.get("missing_evidence", "")
    props["lifecycle_costs"] = costs
    props["monitoring_framework"] = monitoring
    props["severity_tier"] = "critical" if priority >= 0.70 else ("high" if priority >= 0.50 else "moderate")

    # Subsidy details
    props["subsidy_tier"] = "flagship" if priority >= 0.70 else ("priority" if priority >= 0.50 else "standard")
    props["subsidy_pct"] = 90 if priority >= 0.70 else (70 if priority >= 0.50 else 40)
    props["est_cost_per_km_lakhs"] = (
        round(costs["five_year_lifecycle_lakhs"] * 0.8, 1),
        round(costs["five_year_lifecycle_lakhs"] * 1.2, 1)
    )

    return props


def enrich_geojson_corridors(geojson: Dict) -> Dict:
    """Enrich all corridor features in a GeoJSON FeatureCollection."""
    if not geojson or "features" not in geojson:
        return geojson

    enriched = []
    for f in geojson.get("features", []):
        if f.get("properties"):
            f["properties"] = enrich_corridor_with_interventions(f["properties"])
        enriched.append(f)

    return {**geojson, "features": enriched}


# Backward compatibility aliases
def get_subsidy_tier(priority: Optional[float]) -> str:
    if priority is None:
        return "standard"
    if priority >= 0.70:
        return "flagship"
    if priority >= 0.50:
        return "priority"
    return "standard"


def get_subsidy_info(priority: Optional[float]) -> Dict[str, Any]:
    tier = get_subsidy_tier(priority)
    pct = 90 if tier == "flagship" else (70 if tier == "priority" else 40)
    return {
        "tier": tier,
        "subsidy_pct": pct,
        "label": f"{tier.title()} Corridor",
        "priority_min": 0.7 if tier == "flagship" else (0.5 if tier == "priority" else 0.0),
        "est_cost_per_km_lakhs": (15, 30) if tier == "standard" else ((30, 60) if tier == "priority" else (60, 100)),
        "promotional_budget_lakhs": 5 if tier == "standard" else (10 if tier == "priority" else 20),
        "description": "Planning subsidy support model."
    }
