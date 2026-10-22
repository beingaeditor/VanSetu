# Van Setu — Comprehensive Technical Audit & System Diagnosis

**Repository:** `beingaeditor/VanSetu`  
**Audit Date:** October 2026  
**Auditor Role:** Senior Geospatial Software Engineer, Urban Climate Researcher & System Architect  

---

## 1. Executive Summary

Van Setu ("Forest Bridge") is designed as a geospatial decision-support platform for Delhi National Capital Territory (NCT) to identify pedestrian corridors subject to acute urban heat, prioritize green infrastructure interventions, and facilitate evidence-based municipal planning.

An exhaustive technical, architectural, and scientific audit was performed directly on the codebase. While the platform has a functional React-Leaflet frontend and a FastAPI backend with XYZ raster tile serving, the audit revealed **critical scientific limitations, mathematical inconsistencies across scoring implementations, broken automated tests, unhandled missing data, and unverified assumptions regarding street-level microclimate and walkability**.

This document outlines all verified findings and provides an actionable implementation roadmap to transform Van Setu into a scientifically defensible, explainable, and production-ready urban resilience tool.

---

## 2. End-to-End Data Flow Architecture

The current system data flow operates as follows:

```
[Satellite Data Ingestion]
  ├── Google Earth Engine (engine.js)
  │     ├── Sentinel-2 SR Harmonized (10m, Bands B8 & B4) → delhi_ndvi_10m.tif
  │     └── MODIS/061/MOD11A1 LST Day (1km, scaled to °C) → delhi_lst_modis_daily_celsius.tif
  └── Live Air Quality
        ├── OpenAQ / WAQI REST API (CPCB/DPCC monitoring stations in Delhi)
        └── Station coordinates + PM2.5 / PM10 observations

[Backend Processing Pipeline]
  ├── RasterService (raster_service.py)
  │     ├── Loads NDVI (5572 x 7794 float32 raster @ ~10m resolution)
  │     ├── Loads MODIS LST (57 x 79 float32 raster @ ~1km resolution)
  │     ├── Interpolates LST 1km → 10m via scipy.ndimage.zoom(order=1) [SCIENTIFIC ISSUE]
  │     └── Computes Green Deficit Index (GDI = 0.6*Heat + 0.4*(1-NDVI))
  ├── TileService (tile_service.py)
  │     └── Serves 256x256 PNG map tiles for NDVI, LST, and GDI
  ├── RoadService (road_service.py)
  │     ├── Queries OpenStreetMap via OSMnx Overpass API (ox.features_from_bbox) [PERFORMANCE ISSUE]
  │     ├── Samples interpolated raster along road polylines
  │     ├── Assigns nearest AQI station measurements via Haversine distance
  │     └── Filters top 15% priority segments (quantile threshold = 0.85)
  ├── ScoringService (scoring_service.py)
  │     └── Computes composite priority index (Heat, Green Deficit, Pollution, Pedestrian, Health, Vulnerability)
  ├── CorridorService (corridor_service.py)
  │     └── Aggregates contiguous priority road points via KDTree (D_max <= 30m, N_min >= 5)
  └── InterventionService (intervention_service.py)
        └── Assigns intervention types, rationale, and subsidy tiers

[Storage & APIs]
  ├── JSON file persistence (backend/data/feedback/community_data.json, health_data.json, votes.json)
  └── FastAPI endpoints (/api/layers, /api/tiles, /api/roads, /api/corridors, /api/stats, /api/admin)

[Frontend Presentation]
  ├── React 19 + Vite + Leaflet SPA
  ├── Layer controls (NDVI, LST, GDI, Roads, Corridors, AQI Stations)
  ├── Corridor detail & Intervention drawer with 3D viewer
  └── Community submission forms and Admin Dashboard
```

---

## 3. Verified Bugs & Implementation Flaws

### 3.1 Broken Test Suite (`test_aqi.py`)
- **Status:** **CRITICAL BUG (VERIFIED)**
- **Evidence:** Running `pytest backend/tests/test_aqi.py` immediately crashed with:
  `ImportError: cannot import name 'park_connectivity_proxy' from 'app.services.scoring_service'`.
- **Cause:** `scoring_service.py` was refactored from an older "10-factor" model to a "6-factor" model, but the test suite was never updated, and `pytest` was omitted from `requirements.txt`.

### 3.2 Missing Data Coercion to Zero
- **Status:** **VERIFIED**
- **Evidence:** In `scoring_service.py` lines 258–260:
  ```python
  h = float(heat_norm) if heat_norm is not None else 0.0
  g = float(1.0 - ndvi_norm) if ndvi_norm is not None else 0.5
  a = float(aqi_norm) if aqi_norm is not None else 0.0
  ```
- **Consequence:** If satellite thermal data or AQI sensor coverage is missing for a segment, the code sets exposure to `0.0`. This treats lack of observation as complete safety, severely biasing prioritization against data-sparse areas.

### 3.3 Conflicting Formulas Across Codebase
- **Status:** **VERIFIED**
- **Evidence:**
  1. `README.md` & `raster_service.py`: `GDI = 0.6 * Heat + 0.4 * (1 - NDVI)`
  2. `aqi_service.py`: `Priority = 0.45 * Heat + 0.35 * Green Deficit + 0.20 * AQI`
  3. `scoring_service.py`: `Priority = 0.25*Heat + 0.20*Pollution + 0.20*GreenDeficit + 0.15*Pedestrian + 0.12*Health + 0.08*Vuln`
  4. `test_aqi.py`: References legacy 10-factor weights.
- **Consequence:** The frontend displays labels and explanations that contradict the underlying computed scores depending on which endpoint was queried.

### 3.4 Fragile Overpass API Dependency & Absence of Local Cache
- **Status:** **VERIFIED**
- **Evidence:** `RoadService.fetch_roads()` executes `ox.features_from_bbox` across the entire bounding box of Delhi (`[76.73, 28.40, 77.35, 28.87]`, ~1,500 km²) against public Overpass servers on startup without local caching.
- **Consequence:** Overpass requests regularly hit rate limits (HTTP 429) or gateway timeouts (HTTP 504), or fail when running offline/sandboxed, leaving the backend without any road network.

### 3.5 Illusion of Multi-Criteria Decision in `CorridorDecisionPlanner.jsx`
- **Status:** **VERIFIED**
- **Evidence:** In `CorridorDecisionPlanner.jsx`:
  ```javascript
  const width = Number(form.roadWidth);
  if (width < 6) setCorridorType("tree_corridor");
  else if (width >= 6 && width < 12) setCorridorType("shade_corridor");
  else setCorridorType("green_mobility_corridor");
  ```
- **Consequence:** The form presents 7 detailed inputs (Pedestrian Activity, Heat Exposure, Shade Level, Pollution Level, Vulnerable Population, Land Availability, Road Width), but completely discards 6 of them, basing decisions solely on road width.

### 3.6 Pydantic V2 Deprecation Warnings
- **Status:** **VERIFIED**
- **Evidence:** `config.py` uses legacy `class Config: env_file = ".env"`, emitting `PydanticDeprecatedSince20` warnings across all startup and test logs.

---

## 4. Scientific Limitations & Data Integrity

### 4.1 Coarse Thermal Data (1km) vs. Street-Level Claims
- **Satellite Product:** MODIS/Terra Daily LST (`MOD11A1.061`).
- **Native Resolution:** 1,000 meters. The exported GeoTIFF (`delhi_lst_modis_daily_celsius.tif`) has dimensions of **only 57 × 79 pixels** for the whole of Delhi NCT.
- **Flawed Assumption:** In `raster_service.py`, this 57×79 array is resampled via bilinear zoom to **5,572 × 7,794 pixels** (10m grid).
- **Scientific Reality:** Resampling a 1 km cell does not produce 10 m street microclimate. Urban street canyons, aspect ratio ($H/W$), surface albedo, vehicular exhaust, and building shadows vary within 10–30 meters. Resampled MODIS LST must be strictly labeled as **macro-thermal screening**, not street-level thermal measurement.

### 4.2 Severe Temporal Mismatch in Thermal Ingestion
- **Export Window in `engine.js`:** `lstStart = '2024-10-01'` to `lstEnd = '2025-03-31'`.
- **Recorded Values:** Minimum 22.7°C, Maximum 29.0°C, Mean 25.8°C.
- **Scientific Reality:** October through March represents late autumn, winter, and early spring in Delhi. Delhi's lethal heat waves occur between **April and June**, where ambient temperatures reach 45°C–49°C and Land Surface Temperatures regularly exceed 55°C. Using winter temperature distributions to prioritize summer heat corridors misidentifies the locations of peak thermal stress.

### 4.3 Land Surface Temperature (LST) vs. Pedestrian Thermal Comfort
- **LST:** Radiometric surface skin temperature seen by a downward-looking satellite sensor (roofs, asphalt, dry soil).
- **$T_{air}$ (Air Temperature):** Thermodynamic temperature of ambient air at 1.5–2m height.
- **$T_{mrt}$ (Mean Radiant Temperature):** The total shortwave and longwave radiant flux absorbed by a human body.
- **PET / UTCI:** Human biometeorological comfort indices.
- **Correction Required:** Van Setu must never conflate satellite LST with the thermal comfort felt by a pedestrian standing on a shaded versus unshaded sidewalk.

### 4.4 Non-Walkable Road Hierarchy in Pedestrian Corridors
- **OsmHighway Selection:** `['motorway', 'trunk', 'primary', 'secondary', 'tertiary']`.
- **Flawed Assumption:** `pedestrian_proxy()` assigns score `0.20` to motorways and `0.40` to trunk roads, while treating them as candidate green corridors.
- **Physical Reality:** Delhi expressways (e.g., Delhi-Noida Direct Flyway, Outer Ring Road expressway segments) are grade-separated motorways strictly prohibited to pedestrians. Classifying motorways as pedestrian green corridors is dangerous and unfeasible.

---

## 5. Architectural & Implementation Gaps

| Area | Current Implementation | Required Standard |
| :--- | :--- | :--- |
| **Prioritization Output** | Single scalar `priority_score` | Three distinct vectors: **Priority (Need)**, **Feasibility (Implementation Plausibility)**, and **Evidence Confidence (Data Quality/Age)** |
| **Sensitivity Analysis** | None (Hardcoded static weights) | Dynamic weight variation, ranking volatility test, and corridor stability index |
| **Intervention Engine** | Pseudo-random hash selection `(offset + i * 7) % len(items)` | Multi-criteria feasibility rules: sidewalk width, soil depth, utilities, water, shade gap, constraint flags |
| **Cost Modeling** | Fixed tuple `(40, 80) lakhs` | Comprehensive lifecycle costing: CapEx, 3-year establishment/OpEx, irrigation, replacement rate, service life |
| **Equity & Vulnerability** | 10 hardcoded coordinate points | Vulnerability indicator combining informal settlement / slum exposure, heat mortality sensitivity, and lack of private cooling |
| **Community Feedback** | Basic JSON file append | Validated schema, rate-limiting, deduplication, geographic fuzzing for privacy, verification lifecycle |

---

## 6. Features to Preserve

1. **Leaflet Map Experience:** The multi-layer tile view with NDVI, LST, GDI, and OSM overlay is responsive and intuitive.
2. **XYZ Tile Generation:** Fast raster slicing and caching via `TileService`.
3. **Point Query Capability:** Real-time retrieval of raster values at clicked coordinates.
4. **Clean Modern Design:** Distinct palette, dark header, card drawers, and side panels.
5. **Admin & Public Dashboards:** Role-based dual interface with KPI summaries and exports.
6. **Community Submission Intent:** Structured data entry for community groups and health centers.

---

## 7. Phased Implementation Plan

```
[Phase 1] Scientific Data Integrity & Alignment
  ├── Correct metadata schemas & documentation
  ├── Proper labeling of macro-thermal screening vs street-level LST
  └── Fix no-data handling and coordinate transformations

[Phase 2] Explainable Prioritization Engine
  ├── Unified, configurable multi-objective scoring formula
  ├── Defensible missing-data imputation and dynamic reweighting
  ├── Three distinct outputs: Priority, Feasibility, Confidence
  └── Parameter sensitivity analysis & ranking stability metrics

[Phase 3] Walkable Pedestrian Corridors & Network Safety
  ├── Filter OSM road classes to exclude pedestrian-prohibited motorways
  ├── Create robust offline Delhi road network cache for offline resilience
  └── Distinguish pedestrian walkability corridors from ecological habitat connectivity

[Phase 4] Feasibility & Intervention Engine
  ├── Rule-based suitability matrix based on physical site constraints
  ├── Intervention-specific requirements (sidewalk width, soil, utilities, irrigation)
  └── Required site checks, alternative recommendations, and confidence flags

[Phase 5] Lifecycle Costing, Equity & Community Governance
  ├── Itemized lifecycle cost estimation (CapEx, OpEx, replacement, service life)
  ├── Equity-focused vulnerability metrics (socio-economic heat stress)
  ├── Hardened community feedback workflow (deduplication, privacy, moderation)
  └── Post-implementation monitoring data contract

[Phase 6] Frontend Visual & Explanatory Enhancements
  ├── Surface Priority, Feasibility, and Confidence on corridor inspection
  ├── Data resolution warnings and acquisition provenance in UI
  ├── Fix CorridorDecisionPlanner to evaluate all form parameters
  └── Add sensitivity analysis explorer and accessibility compliance

[Phase 7] Backend Hardening, Performance & Validation
  ├── Standardize GeoJSON and API response schemas
  ├── Fix Pydantic V2 deprecations and CORS/security posture
  └── Build comprehensive automated pytest suite covering all modules

[Phase 8] Research Synthesis
  └── Author VANSETU_RESEARCH_AND_DIFFERENTIATION.md citing primary literature
```
