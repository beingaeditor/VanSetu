---
title: VanSetu
emoji: 🌳
colorFrom: green
colorTo: blue
sdk: docker
pinned: false
---

# Van Setu — Urban Heat Resilience & Pedestrian Corridor Planning Platform

Van Setu is an open-source geospatial decision-support platform designed for urban climate researchers, municipal engineers, and urban planners. It identifies heat-exposed pedestrian corridors across the National Capital Territory (NCT) of Delhi, prioritizes green infrastructure investments, and recommends evidence-grounded urban cooling interventions.

---

## 🌟 Key Technical Innovations

1. **Interactive What-if Corridor Ranking & Baseline vs. What-if Rank Changes:**
   - **Authoritative Formula:** $\text{score} = \text{heat\_weight} \times \text{Heat} + (1 - \text{heat\_weight}) \times (1 - \text{NDVI})$ via `GET /api/corridors/rank?heat_weight=0.6&top=5`.
   - **Baseline vs. What-if Novelty:** Compares the default baseline (`heat_weight = 0.60`) against any user-selected `heat_weight` in $[0.0, 1.0]$, displaying rank gains/drops, score shifts, heat vs. green-deficit contributions, and Top-$N$ entry/exit turnover.
   - **Sub-millisecond Re-ranking:** Per-corridor normalized `Heat` and `NDVI` measurements from valid raster pixels are cached at startup so interactive slider adjustments execute instantaneously without re-sampling GeoTIFF rasters.

2. **Tri-Vector Evaluative Framework:**
   - **Priority Need $[0, 1]$:** Quantifies community need based on surface heat, canopy deficit, air pollution, pedestrian footfall, and socio-spatial vulnerability.
   - **Implementation Feasibility $[0, 1]$:** Evaluates physical space, Right-of-Way (ROW) geometry, and highway hierarchy. Excludes non-walkable expressways.
   - **Evidence Confidence $[0, 1]$:** Quantifies sensor certainty and penalizes coarse resolution or distant monitoring stations.

2. **Defensible Missing-Data Behavior:**
   - Missing indicators are **never** coerced to zero.
   - Active weights dynamically re-normalize to $1.0$, with confidence discounts recorded explicitly.

3. **Multi-Scenario Sensitivity & Ranking Stability:**
   - 5 policy scenarios: *Balanced*, *Heat Resilience*, *Air Quality Focus*, *Pedestrian Equity*, *Extreme Vulnerability*.
   - What-if sensitivity engine calculates rank standard deviation and a **Stability Index** $[0, 1]$ ($S \ge 0.70$ indicating robust priorities).

4. **Rules-Based Intervention Suitability & Lifecycle Costing:**
   - Evaluates 5 discrete intervention archetypes: Linear Street Trees, Architectural Shade Structures, Roadside Bioswales, Living Green Walls, and Cool Pavements.
   - Itemized lifecycle cost estimates grounded in the **CPWD Delhi Schedule of Rates (DSR 2023)** and **Delhi Parks and Gardens Society (DPGS)** guidelines (CapEx, annual OpEx, 15% mortality replacement, 5-year lifecycle commitment).
   - Mandatory pre-procurement site checks (GPR utility surveys, soil compaction, BSES overhead wire clearance) and feasible alternatives.

5. **Prune AI Gateway + Google Gemini Ranking Explanation:**
   - Explains corridor rankings using **Google Gemini 2.0 Flash** routed through the **Prune AI Gateway** (`https://api.withprune.com/v1`).
   - The deterministic backend formula remains the authoritative source of rankings; Gemini explains the existing metrics without altering the numbers.
   - Decoupled endpoint prevents interactive slider slowdowns; graceful deterministic fallback if `PRUNE_API_KEY` is not yet configured.

6. **Offline Network Resilience & Privacy-Preserving Feedback:**
   - Bundles verified offline Delhi road network cache (`backend/data/delhi_roads_cached.geojson`, 44 corridors across all 11 districts).
   - Community observation submissions protected via salted one-way SHA-256 IP hashing and 5-minute duplicate rate limiting.

---

## 🛰️ Scientific Data Integrity & Resolution Disclosures

| Layer / Source | Native Resolution | Temporal Window | Metric / Classification | Limitations & Disclosures |
| :--- | :--- | :--- | :--- | :--- |
| **Sentinel-2 MSI** (ESA) | 10 meters | Nov 2024 – Feb 2025 | NDVI $[-0.2 \text{ to } 0.8]$ (Vegetation Vigor) | Measures canopy greenness, not 3D volume or understory shade. |
| **MODIS Terra** (NASA) | 1,000 meters (1 km) | Oct 2024 – Mar 2025 | Day LST $[22^\circ\text{C} \text{ to } 32^\circ\text{C}]$ | **Macro-thermal screening only.** Bilinear resampling to 10m does not create street-level temperature. |
| **CAAQMS** (CPCB/DPCC) | Point Stations (~40) | Near-Real-Time Hourly | Continuous AQI $[0 \text{ to } 500]$ | Inverse-distance interpolation; distance penalties applied beyond 10 km. |
| **OpenStreetMap** | Vector Polyline | Current OSM Snapshot | Highway Classification & Walkability | Motorways/trunk roads flagged as non-walkable with feasibility penalties. |

---

## 🏗️ System Architecture

```
VanSetu/
├── backend/
│   ├── app/
│   │   ├── config.py             # Pydantic V2 settings, metadata, scenarios
│   │   ├── dependencies.py       # Singleton service lifecycle injection
│   │   ├── main.py               # FastAPI application with SPA static routing
│   │   ├── routers/
│   │   │   ├── layers.py         # Layer metadata and provenance disclosures
│   │   │   ├── tiles.py          # Dynamic XYZ PNG tile generation
│   │   │   ├── roads.py          # Walkable network, corridors, sensitivity, & Prune explanation
│   │   │   ├── stats.py          # Zonal raster statistics & point inspection
│   │   │   ├── aqi.py            # CPCB live AQI station integration
│   │   │   ├── community.py      # Hardened feedback with salted SHA-256 IP privacy
│   │   │   └── suggestions.py    # Advisory corridor suggestions & upvotes
│   │   └── services/
│   │       ├── raster_service.py # GeoTIFF sampling & normalization
│   │       ├── scoring_service.py# Tri-vector scoring, dynamic weights, sensitivity
│   │       ├── intervention_service.py # Suitability rules & CPWD lifecycle costing
│   │       ├── prune_service.py  # Prune AI Gateway + Gemini ranking explanation
│   │       ├── road_service.py   # Cached & live OSM network processing
│   │       └── aqi_service.py    # CAAQMS station spatial interpolation
│   ├── data/
│   │   ├── delhi_ndvi_10m.tif    # 10m Sentinel-2 GeoTIFF (Git LFS)
│   │   ├── delhi_lst_modis_daily_celsius.tif # 1km MODIS GeoTIFF (Git LFS)
│   │   └── delhi_roads_cached.geojson # Verified 44-corridor Delhi network
│   ├── tests/                    # 69 automated unit & integration tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/index.js          # Centralized Axios API client
│   │   ├── components/
│   │   │   ├── Map.jsx           # Leaflet interactive map with custom tiles
│   │   │   ├── InterventionPanel.jsx # Tri-vector dashboard, CPWD costs, Prune AI trigger
│   │   │   ├── CorridorDecisionPlanner.jsx # Multi-criteria 3D corridor simulator
│   │   │   └── CommunitySuggestions.jsx # Citizen engagement workflow
│   │   └── App.jsx
│   └── package.json
└── docs/
    ├── VANSETU_TECHNICAL_AUDIT.md # Technical audit & implementation plan
    └── VANSETU_RESEARCH_AND_DIFFERENTIATION.md # Comparative research & scientific benchmarks
```

---

## 🚀 Quick Start & Installation

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Node.js 18+ and npm
- Git LFS (`git lfs install && git lfs pull` to download GeoTIFF rasters)

### 2. Backend Setup
```bash
cd VanSetu/backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (optional: set PRUNE_API_KEY for live Gemini explanations)
cp .env.example .env

# Run FastAPI backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup
```bash
cd VanSetu/frontend

# Install dependencies
npm install

# Run Vite dev server
npm run dev
# or compile production bundle:
npm run build
```

Access the application:
- **Interactive UI:** http://localhost:5173
- **FastAPI Interactive Docs:** http://localhost:8000/docs
- **API Base:** http://localhost:8000/api

---

## 🧪 Automated Test Suite

VanSetu includes 102 automated test cases covering What-if corridor ranking, Baseline vs. What-if rank comparisons, scientific scoring, missing data re-normalization, sensitivity variance, CPWD lifecycle costing, Prune AI Gateway integration, and API validation:

```bash
cd VanSetu
PYTHONPATH=backend backend/venv/bin/pytest backend/tests -v
```

**Test Modules:**
- `test_what_if_ranking.py`: What-if corridor ranking (`heat_weight=0.6`, `0.9`, `0.0`, `1.0`), manual calculation verification, tie-breaking, input validation (`422`), no-data exclusion, and Baseline vs. What-if comparison (27 tests).
- `test_aqi.py`: AQI normalization, station interpolation, and subsidy tiers (34 tests).
- `test_scoring_extended.py`: Dynamic reweighting, tri-vector outputs, and edge cases (13 tests).
- `test_sensitivity.py`: Multi-scenario ranking variance and Stability Index (3 tests).
- `test_interventions.py`: Suitability decision matrix, CPWD CapEx/OpEx, and monitoring framework (10 tests).
- `test_api_endpoints.py`: FastAPI routes, provenance metadata, district validation, and rate limiting (9 tests).
- `test_prune_integration.py`: Prune AI Gateway + Gemini explanation, mock receipts, and deterministic fallback (6 tests).

---

## 🔑 Key API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/corridors/rank?heat_weight=0.6&top=5` | **What-if Corridor Ranking** (`score = heat_weight * Heat + (1 - heat_weight) * (1 - NDVI)`) + Baseline (`0.6`) rank-change comparison |
| `GET` | `/api/corridors?percentile=85&scenario=balanced` | GeoJSON of top priority corridors with feasibility, confidence, and CPWD costs |
| `GET` | `/api/corridors/priority-ranking` | Ranked corridor list with full multi-criteria signal breakdown |
| `GET` | `/api/corridors/sensitivity` | Evaluates rank variance across 5 policy scenarios and outputs Stability Index |
| `POST`| `/api/corridors/explain-ranking` | Isolated Prune Gateway + Gemini explanation of authoritative ranking |
| `GET` | `/api/layers/metadata` | Sensor provenance, native spatial resolution, and scientific disclosures |
| `POST`| `/api/community-data` | Community observation ingestion with salted SHA-256 IP privacy hashing |
| `GET` | `/api/districts` | List of valid NCT of Delhi administrative districts |

---

## 📄 License

MIT License. Designed for public municipal adoption and urban climate research.
