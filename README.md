# 🌳 VanSetu — Urban Green Corridor Planning Platform

> **Hack4Impact 2026** — Data-driven urban greening for Delhi NCT

## 🧩 Problem Statement

Delhi is one of the most heat-stressed and polluted cities in the world. Urban Heat Islands (UHI), declining vegetation cover, and hazardous air quality disproportionately impact communities living along major road corridors. City planners lack an **accessible, data-driven tool** to identify where green interventions (tree planting, green buffers, pocket parks) would have the **highest impact**.

## 💡 Our Solution

**VanSetu** is an interactive geospatial platform that combines **satellite imagery, air quality data, and road network analysis** to automatically identify and rank the most critical corridors in Delhi for green interventions.

### How It Works

1. **Satellite Data Ingestion** — We process Sentinel-2 NDVI (vegetation index at 10m resolution) and MODIS Land Surface Temperature data to map heat and greenery across Delhi.
2. **Multi-Exposure Scoring** — Each road segment is scored using a **Green Deficit Index (GDI)** that combines heat exposure, vegetation deficit, and air quality:
   ```
   GDI = 0.6 × Heat Stress + 0.4 × (1 − NDVI)
   ```
3. **Corridor Prioritization** — The top 15% highest-GDI road segments are surfaced as priority corridors, each tagged with a recommended intervention type (shade trees, pollution buffers, pocket greens, or mixed).
4. **Community Input** — Citizens can submit and upvote corridor improvement suggestions, adding a participatory layer to planning.
5. **Before / After Visualization** — Conceptual mockups show what proposed interventions would look like on each corridor.

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🗺️ **Interactive Map** | Leaflet-based map with toggleable NDVI, LST, GDI, road, and corridor layers |
| 🔥 **Heat & Vegetation Overlays** | Real-time visualization of urban heat islands and green cover gaps |
| 📊 **Statistics Dashboard** | Live stats panel showing layer metrics (min, max, mean, distribution) |
| 📍 **Point Query** | Click anywhere on the map to get precise NDVI, LST, and GDI values |
| 🌿 **Before / After Visuals** | Conceptual corridor improvement mockups based on intervention type |
| 💬 **Community Suggestions** | Citizens can propose and upvote ideas for corridor improvements |
| 🛡️ **Admin Dashboard** | Manage corridor statuses and review community suggestions |

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 19, Vite 7, Leaflet, React-Leaflet, Axios |
| **Geospatial** | Rasterio, NumPy, GeoPandas, OSMnx, Shapely |
| **Data Sources** | Sentinel-2 (ESA), MODIS (NASA), OpenStreetMap |
| **Database** | MongoDB (community suggestions & admin) |
| **Deployment** | Docker |

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/beingaeditor/VanSetu.git
cd VanSetu

# Install frontend dependencies
cd frontend
npm install

# Start the development server
npm run dev
```

Then open **http://localhost:5173** in your browser.

## 📁 Project Structure

```
VanSetu/
├── frontend/              # React + Vite application
│   └── src/
│       ├── api/           # API client modules
│       ├── components/
│       │   ├── Map.jsx              # Interactive Leaflet map
│       │   ├── Sidebar.jsx          # Layer controls & stats
│       │   ├── InterventionPanel.jsx # Before/After corridor visuals
│       │   └── CommunitySuggestions.jsx
│       ├── pages/
│       │   └── AdminDashboard.jsx   # Admin management panel
│       └── App.jsx
├── delhi_ndvi_10m.tif               # Sentinel-2 vegetation data
├── delhi_lst_modis_daily_celsius.tif # MODIS temperature data
├── engine.js                        # Google Earth Engine export script
└── README.md
```

## 📊 Data Layers

| Layer | Description | Source | Resolution |
|-------|-------------|--------|------------|
| **NDVI** | Normalized Difference Vegetation Index | Sentinel-2 (ESA) | 10 m |
| **LST** | Land Surface Temperature | MODIS (NASA) | 1 km (resampled) |
| **GDI** | Green Deficit Index | Computed | 10 m |
| **Roads** | Road network | OpenStreetMap | Vector |
| **Corridors** | Priority green corridors | Top 15% GDI roads | Vector |

## 🌍 Impact

- **Identifies** the most heat-stressed, vegetation-deficient road corridors in Delhi
- **Prioritizes** where limited greening budgets should be spent first
- **Engages** communities in the planning process through participatory suggestions
- **Visualizes** proposed interventions so stakeholders can understand the vision

## 📜 License

MIT
