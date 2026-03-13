"""
Admin Router — Government / Business Dashboard Endpoints

Provides aggregated analytics, corridor management, data export,
and suggestion moderation endpoints for the admin dashboard.

ENDPOINTS:
- GET  /admin/summary           — Overall platform analytics
- GET  /admin/corridors         — All corridors with full details
- GET  /admin/corridors/export  — Export corridors as CSV or GeoJSON
- GET  /admin/ward-stats        — Ward-level / zone breakdown
- GET  /admin/suggestions       — All suggestions across corridors
- POST /admin/corridors/{id}/status — Update corridor implementation status
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from enum import Enum
import csv
import io
import json
import numpy as np

from app.dependencies import (
    get_raster_service,
    get_road_service,
    get_aqi_service,
    get_corridor_service,
    get_suggestion_service,
)
from app.services.raster_service import RasterService
from app.services.road_service import RoadService
from app.services.aqi_service import AQIService
from app.services.corridor_service import CorridorService
from app.services.suggestion_service import SuggestionService
from app.services.intervention_service import enrich_geojson_corridors

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class CorridorStatus(str, Enum):
    identified = "identified"
    planned = "planned"
    in_progress = "in_progress"
    completed = "completed"
    rejected = "rejected"


class StatusUpdate(BaseModel):
    status: CorridorStatus
    notes: Optional[str] = Field(None, max_length=500)


# In-memory status store (would be DB in production)
_corridor_statuses: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Summary / Analytics
# ---------------------------------------------------------------------------


@router.get("/summary")
async def get_platform_summary(
    raster_service: RasterService = Depends(get_raster_service),
    road_service: RoadService = Depends(get_road_service),
    aqi_service: AQIService = Depends(get_aqi_service),
) -> Dict[str, Any]:
    """
    Comprehensive analytics overview for the admin dashboard.

    Returns aggregated KPIs: raster stats, corridor counts, AQI overview,
    priority distribution, and coverage metrics.
    """
    # Raster layer stats
    ndvi_stats = raster_service.get_statistics("ndvi")
    lst_stats = raster_service.get_statistics("lst")
    gdi_stats = raster_service.get_statistics("gdi")

    # GDI distribution buckets
    gdi = raster_service.gdi
    gdi_distribution = {}
    if gdi is not None:
        valid = gdi[np.isfinite(gdi)]
        if len(valid) > 0:
            gdi_distribution = {
                "low_0_30": float((valid < 0.3).sum() / len(valid)),
                "moderate_30_50": float(((valid >= 0.3) & (valid < 0.5)).sum() / len(valid)),
                "high_50_70": float(((valid >= 0.5) & (valid < 0.7)).sum() / len(valid)),
                "critical_70_100": float((valid >= 0.7).sum() / len(valid)),
            }

    # AQI overview
    stations = aqi_service.stations
    aqi_overview = {
        "station_count": len(stations),
        "last_updated": aqi_service.last_updated.isoformat() if aqi_service.last_updated else None,
        "average_pm25": round(np.mean([s.pm25 for s in stations if s.pm25]), 1) if stations else None,
        "max_pm25": round(max((s.pm25 for s in stations if s.pm25), default=0), 1),
        "min_pm25": round(min((s.pm25 for s in stations if s.pm25), default=0), 1),
    }

    # Corridor summary from cache
    corridors = road_service.detect_corridors(raster_service, 85, aqi_service)
    corridor_count = len(corridors) if corridors is not None else 0

    # Priority score stats from corridors
    priority_stats = {}
    if corridors is not None and len(corridors) > 0:
        scores = corridors["priority_score"].dropna()
        if len(scores) > 0:
            priority_stats = {
                "min": float(scores.min()),
                "max": float(scores.max()),
                "mean": float(scores.mean()),
                "std": float(scores.std()),
                "p25": float(scores.quantile(0.25)),
                "p50": float(scores.quantile(0.50)),
                "p75": float(scores.quantile(0.75)),
            }

    # Status summary
    status_counts = {}
    for info in _corridor_statuses.values():
        s = info.get("status", "identified")
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "raster": {
            "ndvi": ndvi_stats,
            "lst": lst_stats,
            "gdi": gdi_stats,
            "shape": raster_service.shape,
            "bounds": raster_service.bounds,
        },
        "corridors": {
            "total_segments": corridor_count,
            "priority_stats": priority_stats,
            "status_counts": status_counts,
        },
        "aqi": aqi_overview,
        "gdi_distribution": gdi_distribution,
    }


# ---------------------------------------------------------------------------
# Corridor Management
# ---------------------------------------------------------------------------


@router.get("/corridors")
async def get_admin_corridors(
    percentile: float = Query(default=85, ge=50, le=99),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service),
) -> Dict[str, Any]:
    """
    Full corridor list with all metadata for the management table.

    Each corridor includes priority breakdown, intervention type,
    implementation status, and suggestion count.
    """
    corridors = road_service.detect_corridors(raster_service, percentile, aqi_service)
    geojson = road_service.roads_to_geojson(corridors)
    enriched = enrich_geojson_corridors(geojson)

    # Attach statuses
    for feature in enriched.get("features", []):
        props = feature.get("properties", {})
        name = props.get("name", "")
        if name in _corridor_statuses:
            props["implementation_status"] = _corridor_statuses[name]["status"]
            props["status_notes"] = _corridor_statuses[name].get("notes")
        else:
            props["implementation_status"] = "identified"
            props["status_notes"] = None

    features = enriched.get("features", [])
    priority_values = [
        f["properties"].get("priority_score") or f["properties"].get("gdi_mean") or 0
        for f in features if f.get("properties")
    ]

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "count": len(features),
            "priority_min": min(priority_values) if priority_values else 0,
            "priority_max": max(priority_values) if priority_values else 1,
        },
    }


@router.post("/corridors/{corridor_name}/status")
async def update_corridor_status(
    corridor_name: str,
    body: StatusUpdate,
) -> Dict[str, Any]:
    """
    Update implementation status of a corridor.

    Statuses: identified → planned → in_progress → completed (or rejected)
    """
    _corridor_statuses[corridor_name] = {
        "status": body.status.value,
        "notes": body.notes,
    }
    return {
        "corridor": corridor_name,
        "status": body.status.value,
        "notes": body.notes,
        "message": "Status updated",
    }


# ---------------------------------------------------------------------------
# Data Export
# ---------------------------------------------------------------------------


@router.get("/corridors/export")
async def export_corridors(
    format: str = Query(default="geojson", description="Export format: geojson or csv"),
    percentile: float = Query(default=85, ge=50, le=99),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service),
):
    """
    Export corridor data in GeoJSON or CSV format for offline analysis.
    """
    corridors = road_service.detect_corridors(raster_service, percentile, aqi_service)
    geojson = road_service.roads_to_geojson(corridors)
    enriched = enrich_geojson_corridors(geojson)

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        header = [
            "name", "priority_score", "heat_norm", "ndvi_norm",
            "aqi_raw", "aqi_norm", "gdi_mean",
            "corridor_type", "recommended_interventions",
            "implementation_status",
        ]
        writer.writerow(header)

        for feature in enriched.get("features", []):
            props = feature.get("properties", {})
            name = props.get("name", "Unnamed")
            status_info = _corridor_statuses.get(name, {})
            writer.writerow([
                name,
                props.get("priority_score"),
                props.get("heat_norm"),
                props.get("ndvi_norm"),
                props.get("aqi_raw"),
                props.get("aqi_norm"),
                props.get("gdi_mean"),
                props.get("corridor_type"),
                "; ".join(props.get("recommended_interventions", [])),
                status_info.get("status", "identified"),
            ])

        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=corridors_export.csv"},
        )

    # Default: GeoJSON
    content = json.dumps(enriched, indent=2)
    return StreamingResponse(
        io.StringIO(content),
        media_type="application/geo+json",
        headers={"Content-Disposition": "attachment; filename=corridors_export.geojson"},
    )


# ---------------------------------------------------------------------------
# Suggestions Review (all corridors at once)
# ---------------------------------------------------------------------------


@router.get("/suggestions")
async def get_all_suggestions(
    suggestion_service: SuggestionService = Depends(get_suggestion_service),
) -> Dict[str, Any]:
    """
    Retrieve all community suggestions across all corridors.

    For admin review and moderation.
    """
    try:
        suggestions = suggestion_service.get_all_suggestions()
    except Exception:
        suggestions = []

    return {
        "suggestions": suggestions,
        "total": len(suggestions),
    }


# ---------------------------------------------------------------------------
# Ward / Zone Statistics
# ---------------------------------------------------------------------------


@router.get("/zone-stats")
async def get_zone_statistics(
    raster_service: RasterService = Depends(get_raster_service),
    road_service: RoadService = Depends(get_road_service),
    aqi_service: AQIService = Depends(get_aqi_service),
) -> Dict[str, Any]:
    """
    Priority breakdown by geographic zone (quadrant-based).

    Divides Delhi into NW / NE / SW / SE quadrants and computes
    per-zone statistics for comparative analysis.
    """
    gdi = raster_service.gdi
    bounds = raster_service.bounds  # (west, south, east, north)

    if gdi is None:
        raise HTTPException(status_code=503, detail="Raster data not loaded")

    w, s, e, n = bounds
    mid_lat_row = gdi.shape[0] // 2
    mid_lon_col = gdi.shape[1] // 2

    zones = {
        "NW": gdi[:mid_lat_row, :mid_lon_col],
        "NE": gdi[:mid_lat_row, mid_lon_col:],
        "SW": gdi[mid_lat_row:, :mid_lon_col],
        "SE": gdi[mid_lat_row:, mid_lon_col:],
    }

    zone_stats = {}
    for name, data in zones.items():
        valid = data[np.isfinite(data)]
        if len(valid) == 0:
            continue
        zone_stats[name] = {
            "mean_priority": round(float(np.mean(valid)), 4),
            "max_priority": round(float(np.max(valid)), 4),
            "high_priority_pct": round(float((valid >= 0.5).sum() / len(valid) * 100), 1),
            "pixel_count": int(len(valid)),
        }

    # AQI by zone
    mid_lat = (s + n) / 2
    mid_lon = (w + e) / 2
    for station in aqi_service.stations:
        lat, lon = station.latitude, station.longitude
        if lat >= mid_lat:
            zone = "NW" if lon < mid_lon else "NE"
        else:
            zone = "SW" if lon < mid_lon else "SE"
        if zone in zone_stats:
            zone_stats[zone].setdefault("aqi_stations", []).append({
                "name": station.name,
                "pm25": station.pm25,
            })

    return {"zones": zone_stats}


# ---------------------------------------------------------------------------
# Subsidy Statistics
# ---------------------------------------------------------------------------


@router.get("/subsidy-stats")
async def get_subsidy_stats(
    percentile: float = Query(default=85, ge=50, le=99),
    road_service: RoadService = Depends(get_road_service),
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service),
) -> Dict[str, Any]:
    """
    Subsidy allocation statistics across all corridors.

    Returns per-tier: corridor count, total estimated cost,
    subsidy coverage percentage, and promotional budget.
    """
    from app.services.intervention_service import (
        get_subsidy_tier,
        SUBSIDY_TIERS,
    )

    corridors = road_service.detect_corridors(raster_service, percentile, aqi_service)
    if corridors is None or len(corridors) == 0:
        return {"tiers": {}, "total_corridors": 0}

    tier_buckets: Dict[str, list] = {"flagship": [], "priority": [], "standard": []}

    for _, row in corridors.iterrows():
        score = row.get("priority_score") or row.get("gdi_mean") or 0
        tier = get_subsidy_tier(score)
        tier_buckets[tier].append(float(score))

    result = {}
    for tier_name, scores in tier_buckets.items():
        info = SUBSIDY_TIERS[tier_name]
        count = len(scores)
        avg_score = round(float(np.mean(scores)), 4) if scores else 0
        cost_range = info["est_cost_per_km_lakhs"]
        result[tier_name] = {
            "label": info["label"],
            "count": count,
            "avg_priority": avg_score,
            "subsidy_pct": info["subsidy_pct"],
            "est_cost_range_lakhs": list(cost_range),
            "total_est_cost_lakhs": [cost_range[0] * count, cost_range[1] * count],
            "promotional_budget_lakhs": info["promotional_budget_lakhs"] * count,
            "description": info["description"],
        }

    return {
        "tiers": result,
        "total_corridors": len(corridors),
        "total_promotional_budget_lakhs": sum(
            v["promotional_budget_lakhs"] for v in result.values()
        ),
    }


# ---------------------------------------------------------------------------
# Medical Data (Simulated)
# ---------------------------------------------------------------------------


@router.get("/medical-data")
async def get_medical_data() -> Dict[str, Any]:
    """
    Simulated heat-related health data by Delhi zone.

    Provides representative numbers for heat stress, dehydration,
    and heat-related hospital admissions per zone.

    NOTE: This is simulated data for hackathon demonstration.
    In production, this would connect to hospital/IDSP APIs.
    """
    # Simulated monthly heat-illness data for current season
    zones_data = [
        {
            "zone": "North Delhi",
            "heat_stress_cases": 342,
            "dehydration_cases": 215,
            "hospital_admissions": 48,
            "heat_stroke_deaths": 2,
            "most_affected_area": "Jahangirpuri",
            "reporting_centers": 12,
        },
        {
            "zone": "South Delhi",
            "heat_stress_cases": 198,
            "dehydration_cases": 145,
            "hospital_admissions": 28,
            "heat_stroke_deaths": 0,
            "most_affected_area": "Okhla Phase-2",
            "reporting_centers": 15,
        },
        {
            "zone": "East Delhi",
            "heat_stress_cases": 410,
            "dehydration_cases": 280,
            "hospital_admissions": 62,
            "heat_stroke_deaths": 3,
            "most_affected_area": "Anand Vihar",
            "reporting_centers": 10,
        },
        {
            "zone": "West Delhi",
            "heat_stress_cases": 275,
            "dehydration_cases": 190,
            "hospital_admissions": 35,
            "heat_stroke_deaths": 1,
            "most_affected_area": "Mundka",
            "reporting_centers": 8,
        },
        {
            "zone": "Central Delhi",
            "heat_stress_cases": 156,
            "dehydration_cases": 98,
            "hospital_admissions": 22,
            "heat_stroke_deaths": 0,
            "most_affected_area": "Chandni Chowk",
            "reporting_centers": 18,
        },
        {
            "zone": "New Delhi",
            "heat_stress_cases": 88,
            "dehydration_cases": 52,
            "hospital_admissions": 10,
            "heat_stroke_deaths": 0,
            "most_affected_area": "Connaught Place",
            "reporting_centers": 14,
        },
    ]

    totals = {
        "total_heat_stress": sum(z["heat_stress_cases"] for z in zones_data),
        "total_dehydration": sum(z["dehydration_cases"] for z in zones_data),
        "total_admissions": sum(z["hospital_admissions"] for z in zones_data),
        "total_deaths": sum(z["heat_stroke_deaths"] for z in zones_data),
        "total_reporting_centers": sum(z["reporting_centers"] for z in zones_data),
    }

    return {
        "zones": zones_data,
        "totals": totals,
        "period": "March 2026 (simulated)",
        "source": "Simulated — based on IDSP/hospital reporting patterns",
        "note": "This is demonstration data. Production would use real hospital APIs.",
    }


# ---------------------------------------------------------------------------
# Passive Users
# ---------------------------------------------------------------------------

# In-memory passive user store (simulated community participants)
_passive_users: list = [
    {"id": "usr_001", "ip_hash": "a3b8..d1e2", "last_active": "2026-02-01", "suggestions": 0, "zone": "North Delhi"},
    {"id": "usr_002", "ip_hash": "f7c1..9a4b", "last_active": "2026-01-15", "suggestions": 0, "zone": "East Delhi"},
    {"id": "usr_003", "ip_hash": "d2e5..3f8c", "last_active": "2026-02-10", "suggestions": 1, "zone": "South Delhi"},
    {"id": "usr_004", "ip_hash": "b9a4..6d7e", "last_active": "2026-01-20", "suggestions": 0, "zone": "West Delhi"},
    {"id": "usr_005", "ip_hash": "e1f3..8c2d", "last_active": "2026-02-05", "suggestions": 0, "zone": "Central Delhi"},
    {"id": "usr_006", "ip_hash": "c4d6..1a9b", "last_active": "2026-01-28", "suggestions": 0, "zone": "East Delhi"},
    {"id": "usr_007", "ip_hash": "a8b2..5e3f", "last_active": "2026-02-14", "suggestions": 2, "zone": "North Delhi"},
    {"id": "usr_008", "ip_hash": "f0e9..7c1d", "last_active": "2026-01-05", "suggestions": 0, "zone": "South Delhi"},
]


@router.get("/passive-users")
async def get_passive_users() -> Dict[str, Any]:
    """
    List passive community users — those with no suggestion activity
    in the past 30+ days.

    NOTE: Simulated data since there is no user auth system.
    Each 'user' represents a unique IP that interacted with the platform.
    """
    return {
        "users": _passive_users,
        "total": len(_passive_users),
        "note": "Passive = no suggestions in 30+ days. Simulated for demo.",
    }


@router.delete("/passive-users/{user_id}")
async def remove_passive_user(user_id: str) -> Dict[str, Any]:
    """
    Remove a passive user record.

    In production this would revoke incentive eligibility
    or archive the user's participation record.
    """
    global _passive_users
    before = len(_passive_users)
    _passive_users = [u for u in _passive_users if u["id"] != user_id]

    if len(_passive_users) == before:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    return {
        "removed": user_id,
        "remaining": len(_passive_users),
        "message": f"Passive user {user_id} removed",
    }


# ---------------------------------------------------------------------------
# Signal Coverage
# ---------------------------------------------------------------------------


@router.get("/signal-coverage")
async def get_signal_coverage(
    raster_service: RasterService = Depends(get_raster_service),
    aqi_service: AQIService = Depends(get_aqi_service),
) -> Dict[str, Any]:
    """
    Report coverage and availability of each scoring signal.

    Useful for identifying data gaps in the 10-factor Priority Index.
    """
    from app.services.scoring_service import WEIGHTS

    signals = []

    # Raster-based signals
    ndvi = raster_service.ndvi
    lst = raster_service.lst
    gdi = raster_service.gdi

    ndvi_coverage = 0.0
    if ndvi is not None:
        valid = np.isfinite(ndvi).sum()
        ndvi_coverage = round(float(valid / ndvi.size * 100), 1)

    lst_coverage = 0.0
    if lst is not None:
        valid = np.isfinite(lst).sum()
        lst_coverage = round(float(valid / lst.size * 100), 1)

    signals.append({
        "signal": "Heat Intensity",
        "weight": WEIGHTS["heat"],
        "source": "MODIS LST raster",
        "coverage_pct": lst_coverage,
        "status": "live" if lst is not None else "unavailable",
    })
    signals.append({
        "signal": "Green Deficit",
        "weight": WEIGHTS["green_deficit"],
        "source": "Sentinel-2 NDVI raster",
        "coverage_pct": ndvi_coverage,
        "status": "live" if ndvi is not None else "unavailable",
    })

    # AQI signal
    stations = aqi_service.stations
    signals.append({
        "signal": "Air Quality (AQI)",
        "weight": WEIGHTS["aqi"],
        "source": "WAQI / CPCB stations",
        "coverage_pct": round(min(100.0, len(stations) * 10.0), 1),
        "status": "live" if stations else "fallback",
        "station_count": len(stations),
    })

    # Proxy signals
    proxy_items = [
        ("Pedestrian Density", "pedestrian", "OSM highway tag proxy"),
        ("Vulnerable Population", "vulnerable_pop", "Zone-based lookup (10 zones)"),
        ("Park Connectivity", "park_connectivity", "NDVI inverse distance proxy"),
        ("Community Demand", "community_demand", "Suggestion count (MongoDB)"),
        ("Cost-Impact Efficiency", "cost_impact", "Road category inverse"),
        ("Health Risk", "health_risk", "Heat × AQI interaction"),
    ]
    for label, key, source in proxy_items:
        signals.append({
            "signal": label,
            "weight": WEIGHTS[key],
            "source": source,
            "coverage_pct": 100.0,
            "status": "proxy",
        })

    return {
        "signals": signals,
        "total_weight": round(sum(s["weight"] for s in signals), 2),
        "live_signals": sum(1 for s in signals if s["status"] == "live"),
        "proxy_signals": sum(1 for s in signals if s["status"] == "proxy"),
    }
