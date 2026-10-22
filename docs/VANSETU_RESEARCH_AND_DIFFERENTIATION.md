# Van Setu — Research, Scientific Foundation & Competitive Differentiation

**Document Version:** 2.0.0  
**Author:** Senior Geospatial Software Engineer, Urban Climate Researcher, & Product Architect  
**Project:** Van Setu (`beingaeditor/VanSetu`)  
**Target Region:** National Capital Territory (NCT) of Delhi, India  

---

## 1. Executive Summary & Purpose

Rapid urbanization, high population density, and intensifying summer heatwaves have made Delhi one of the most thermally vulnerable megacities in the Global South. During summer peaks, ambient air temperatures exceed 45°C–49°C, with severe Land Surface Temperatures (LST) and extreme Wet-Bulb Globe Temperatures threatening millions of daily pedestrian commuters, street vendors, and public transit passengers.

**Van Setu** is a geospatial decision-support platform designed to transition municipal urban heat planning from static, macro-level academic vulnerability maps into **actionable, explainable, and pedestrian-centric urban green infrastructure investments**.

This document outlines the scientific foundations, satellite data characteristics, architectural decisions, and comparative benchmarks that differentiate Van Setu from existing academic models, navigation tools, and government action plans.

---

## 2. Comparative Analysis with Existing Platforms & Paradigms

| Feature / Dimension | WRI Cool Cities Lab | CoolPaths / Cool Routes | EPA / UNEP Community Heat Tools | Delhi Heat Action Plan (DDMA / HAP) | **Van Setu (Current Evolved Implementation)** |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary Scope** | City-level macro heat policy & spatial planning | Individual trip routing along shaded streets | Neighborhood social vulnerability indices | Emergency heat alerts & hospital preparedness | **Corridor-scale capital intervention & green infrastructure prioritization** |
| **Target User** | Urban planners, policymakers, researchers | Commuters, tourists, pedestrians | Community organizers, municipal NGOs | District magistrates, health officers, citizens | **Municipal engineers (PWD/MCD), urban foresters, transport planners, and RWAs** |
| **Spatial Unit** | 100m–1km grid cells or administrative wards | Routing graph edges (point-to-point) | Census tracts / wards | District level (11 Delhi revenue districts) | **Walkable pedestrian street segments (OSM hierarchy, 50m–1500m links)** |
| **Scientific Metric Distinction** | Blends LST and Air Temperature into generic heat index | Combines shade geometry with solar azimuth | Combines demographic data with census variables | Temperature thresholds (e.g. 40°C Yellow, 45°C Red alert) | **Strictly separates Priority Need, Implementation Feasibility, and Evidence Confidence** |
| **Resolution Transparency** | Often presents smoothed 1km LST as street-level heat | Microscale solar calculations, lacks live AQI | Census ward resolution; coarse spatial granularity | Regional forecast stations (Safdarjung, Palam) | **Explicitly labels 1km MODIS as macro screening; pairs with 10m Sentinel-2 and station AQI** |
| **Intervention Engine** | High-level typologies (e.g. "Increase tree cover by 15%") | None (navigation only) | Policy checklists and toolkits | Emergency cooling centers, water tankers, advisories | **Rules-based multi-criteria matching across 5 discrete types with site checks & alternatives** |
| **Cost & Lifecycle Modeling** | Broad municipal CapEx estimates | None | Qualitative budgeting guides | Disaster relief funds | **Itemized lifecycle costs (CapEx, OpEx, 15% mortality replacement, 5-yr total) grounded in CPWD DSR 2023** |
| **Explainability & Sensitivity** | Static weighted overlay | Black-box routing cost function | Multi-attribute ranking | Static institutional matrix | **What-if sensitivity engine with Ranking Stability Index + Decoupled Prune/Gemini AI explanations** |

---

## 3. Remote Sensing & Environmental Data Specifications

A core scientific principle implemented in Van Setu is **truth in data representation**: fine visual display must never be mistaken for high-resolution ground truth.

```
+-------------------------------------------------------------------------------------------------+
|                                    VAN SETU DATA HARVESTING                                     |
+-------------------------------------------------------------------------------------------------+
|                                                                                                 |
|   1. Sentinel-2 MSI (10m)          2. MODIS Terra (1 km)               3. CPCB CAAQMS (~40 Stns) |
|   - Surface Reflectance            - Land Surface Temp (Day LST)      - Near-Real-Time AQI      |
|   - Multi-month Winter Composite   - Scaled 0.02 - 273.15 -> Celsius  - Inverse-Distance Spline |
|   - Cloud-masked (QA60 band)       - Bilinear Resampling to 10m       - Station Distance Metric |
|   - Direct Vegetation Observation  - Regional Macro Screening         - Ambient Multi-Stress    |
|                                                                                                 |
|                                         +                                                       |
|                                                                                                 |
|   4. OpenStreetMap (OSM)           5. Socio-Spatial Ground Truth       6. Community Feedback    |
|   - Walkable Network Filtering     - 10 Identified Exposure Nodes      - Salted IP Hashing      |
|   - Expressways/Motorways flagged  - Old Delhi, Anand Vihar, etc.      - 5-min Rate Limiting    |
|   - Geodesic Meter Lengths         - Clinical Heatstroke Secondary     - Verification Lifecycle |
+-------------------------------------------------------------------------------------------------+
```

### 3.1 Copernicus Sentinel-2 MSI (10-Meter Vegetation Vigor)
- **Data Provider:** European Space Agency (ESA) via Google Earth Engine (`COPERNICUS/S2_SR_HARMONIZED`).
- **Native Spatial Resolution:** 10 meters (Bands B4 Red and B8 Near-Infrared).
- **Temporal Window:** November 1, 2024 to February 28, 2025 (cloud-masked composite).
- **Metric Formulation:** $\text{NDVI} = \frac{\text{NIR} - \text{Red}}{\text{NIR} + \text{Red}}$, normalized between $-0.2$ and $+0.8$.
- **Green Deficit:** Defined as $\text{Green Deficit} = 1.0 - \text{NDVI}_{\text{normalized}}$.
- **Scientific Limitation:** Measures chlorophyll absorption (canopy vigor and ground vegetation), not volumetric 3D canopy height or under-canopy pedestrian shade.

### 3.2 MODIS Terra LST (1,000-Meter Macro Thermal Screening)
- **Data Provider:** NASA LP DAAC via Google Earth Engine (`MODIS/061/MOD11A1`).
- **Native Spatial Resolution:** 1,000 meters (1 kilometer).
- **Temporal Window:** October 1, 2024 to March 31, 2025.
- **Conversion Formula:** $\text{LST}_{\text{Celsius}} = (\text{DN} \times 0.02) - 273.15$.
- **Scientific Reality & Caveats:** 
  - Bilinear interpolation from 1km to 10m enables spatial overlay across streets, but **does not create new street-canyon microclimate information**.
  - LST measures radiant skin temperature of rooftops, asphalt, and bare soil; it is not near-surface air temperature ($T_{\text{air}}$) or Mean Radiant Temperature ($T_{\text{mrt}}$).
  - Explicitly classified in Van Setu as **Macro-Thermal Regional Screening**, preventing unwarranted municipal claims of street-level precision.

### 3.3 CPCB Continuous Ambient Air Quality Monitoring (CAAQMS)
- **Data Provider:** Central Pollution Control Board (CPCB) / DPCC via OpenAQ and WAQI.
- **Spatial Resolution:** Point station network (~40 continuous monitoring stations across Delhi NCT).
- **Interpolation:** Haversine inverse-distance weighting with recorded distance to nearest monitoring node. Corridors >10 km from a station incur an explicit confidence penalty.

---

## 4. Methodological Innovations & Core Differentiators

### 4.1 The Tri-Vector Evaluation Framework
Traditional systems collapse all indicators into a single arbitrary score. Van Setu produces three distinct, uncoupled evaluative vectors:

1. **Priority Need ($P \in [0, 1]$):** Quantifies human exposure and environmental stress based on thermal hazard, canopy deficit, air pollution, pedestrian density, and social vulnerability.
2. **Implementation Feasibility ($F \in [0, 1]$):** Evaluates physical space, Right-of-Way (ROW) width, and highway classification. Non-walkable expressways (e.g., Ring Road motorways) receive heavy feasibility penalties ($F < 0.15$), recognizing that planting street trees without sidewalk infrastructure is impractical.
3. **Evidence Confidence ($C \in [0, 1]$):** Dynamically computed certainty index. Reflects sensor resolution limitations (e.g., MODIS 1km deduction), missing indicators, or distant air quality stations.

### 4.2 Defensible Missing-Data Behavior
In earlier systems and naive implementations, missing indicators are coerced to zero, artificially deflating priority in data-scarce zones. Van Setu dynamically re-normalizes active weights:
$$\bar{w}_i = \frac{w_i}{\sum_{j \in \text{Available}} w_j}$$
When an indicator is unavailable, the remaining active indicators scale proportionally to sum to $1.0$, and an explicit penalty is deducted from the Evidence Confidence score.

### 4.3 What-If Scenario Sensitivity & Ranking Stability
Urban planners face conflicting political mandates. Van Setu includes 5 pre-configured policy scenarios:
- **Balanced (Default):** Heat (0.25), Green Deficit (0.20), AQI (0.20), Pedestrian (0.15), Health Risk (0.12), Vulnerability (0.08).
- **Heat Resilience:** Heat (0.40), Green Deficit (0.25), AQI (0.15), Pedestrian (0.10), Health (0.05), Vulnerability (0.05).
- **Air Quality Focus:** AQI (0.40), Green Deficit (0.20), Heat (0.15), Pedestrian (0.10), Health (0.10), Vulnerability (0.05).
- **Pedestrian Equity:** Pedestrian (0.25), Vulnerability (0.20), Heat (0.15), AQI (0.15), Green Deficit (0.15), Health (0.10).
- **Extreme Vulnerability:** Vulnerability (0.20), Health Risk (0.20), Heat (0.20), AQI (0.15), Pedestrian (0.15), Green Deficit (0.10).

The **Sensitivity Engine** evaluates corridor rankings across all 5 scenarios and computes:
- $\sigma_{\text{rank}}$: Standard deviation of ranking positions.
- $\Delta_{\text{max}}$: Maximum rank shift across scenarios.
- **Stability Index ($S \in [0, 1]$):** $S = 1.0 - \frac{\sigma_{\text{rank}}}{\max(1, N / 2)}$. Corridors with $S \ge 0.70$ represent robust high-priority investments whose urgency is invariant to political weighting.

### 4.4 Rules-Based Intervention Suitability & CPWD Lifecycle Costing
Rather than using opaque machine learning or random hashing, Van Setu implements an empirical suitability decision matrix across 5 intervention archetypes:
1. **Linear Street Trees & Native Canopy Expansion:** Staggered native species (Neem, Peepal, Pilkhan, Amaltas, Jamun). Triggered by heat $\ge 0.40$ and $\text{ROW} \ge 6\text{m}$.
2. **Architectural Shade Structures & Waiting Shelters:** Modular tensile fabric and pergolas with climbing bougainvillea. Triggered by high pedestrian density ($\ge 0.55$) and vulnerability.
3. **Roadside Bioswales & Water-Sensitive Infrastructure:** Bio-retention infiltration trenches with Vetiver grass. Triggered by wide rights-of-way ($\ge 12\text{m}$) and stormwater risk.
4. **Living Green Walls & Boundary Trellises:** Vertical facade greenery. Triggered along narrow corridors ($< 10\text{m}$) with high particulate pollution ($\text{AQI} \ge 0.60$).
5. **High-Albedo Cool Pavements & Reflective Walkways:** Solar-reflective sidewalk sealants. Triggered by surface thermal extremes ($\ge 0.55$) and pedestrian plazas.

**Lifecycle Cost Benchmarks:**
All cost models are grounded in the **CPWD Delhi Schedule of Rates (DSR) 2023** and **Delhi Parks and Gardens Society (DPGS)** urban forestry standards:
- Capital Expenditure (CapEx per km).
- Annual Operations & Maintenance (OpEx per km including tanker irrigation during dry months).
- 15% mortality replacement in years 1–2.
- 5-year total lifecycle commitment and expected asset service life (12 to 30 years).

---

## 5. Prune AI Gateway & Google Gemini Integration Architecture

### 5.1 Architecture & Separation of Concerns
To empower municipal non-technical stakeholders without compromising algorithmic integrity, Van Setu incorporates an **Explain This Ranking** capability via the **Prune AI Gateway** backed by **Google Gemini 2.0 Flash**:

```
+------------------+         POST /explain-ranking         +--------------------+
|  VanSetu Web UI  |  ---------------------------------->  |  FastAPI Backend   |
| (React Leaflet)  |  <----------------------------------  | (roads.py Router)  |
+------------------+     JSON Explanation + Receipt        +--------------------+
                                                                     |
                                                          Internal Service Call
                                                                     v
                                                           +--------------------+
                                                           |  prune_service.py  |
                                                           +--------------------+
                                                                     |
                                                          HTTPS Bearer PRUNE_API_KEY
                                                                     v
                                                           +--------------------+
                                                           |  Prune AI Gateway  |
                                                           | (withprune.com/v1) |
                                                           +--------------------+
                                                                     |
                                                          Vaulted Credentials
                                                                     v
                                                           +--------------------+
                                                           | Google Gemini LLM  |
                                                           | (gemini-2.0-flash) |
                                                           +--------------------+
```

### 5.2 Key Invariants
1. **Authoritative Invariance:** The deterministic mathematical formula is the sole source of ranking. Gemini is strictly prohibited from recalculating, modifying, or fabricating ranking numbers.
2. **Decoupled Asynchrony:** The `/api/corridors/explain-ranking` endpoint is isolated from the spatial `/corridors` query. Moving slider bars in the web application never triggers external LLM requests or introduces latency.
3. **Vaulted Zero-Leakage Security:** The Google Gemini API key is vaulted inside Prune (`Connect > Providers`). The `PRUNE_API_KEY` exists exclusively in the backend environment and is never leaked to the client.
4. **Deterministic Fallback:** If `PRUNE_API_KEY` is not configured, or if the external gateway encounters network timeouts or rate limits, the system immediately returns a structured, deterministic mathematical explanation without throwing unhandled exceptions.

---

## 6. Implementation Constraints in Urban Delhi

Real-world deployment of green infrastructure in Delhi faces severe physical constraints that Van Setu explicitly integrates into corridor recommendations:

1. **Subsurface Utility Congestion:** High density of shallow water mains, optical fiber conduits, and gas pipelines prevents standard 1.5m tree-pit excavation. Van Setu requires **Ground Penetrating Radar (GPR) utility verification** before procurement.
2. **Overhead Electrical Distribution:** Un-insulated 11kV/33kV distribution lines cross tertiary and secondary market roads. Requires selection of compact lateral-branching species (e.g., Amaltas) or architectural pergolas.
3. **Paved-over Root Collars & Compaction:** Concrete and interlocking pavers flush against tree trunks cause widespread premature tree mortality. Van Setu mandates minimum $1.5\text{m} \times 1.5\text{m}$ unpaved permeable tree basins.
4. **Summer Irrigation Dependency:** Delhi experiences an intense 3-month dry summer with temperatures exceeding 45°C. Un-irrigated saplings suffer >60% mortality. Van Setu's cost models include **non-potable tanker and drip irrigation for years 1–3**.

---

## 7. Conclusion

By grounding spatial analysis in actual sensor limitations, enforcing mathematical explainability, distinguishing need from feasibility, and providing CPWD-compliant financial estimates, Van Setu moves beyond theoretical heat maps to deliver a robust, scientifically defensible platform for climate-resilient pedestrian planning across Delhi.
