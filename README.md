---
title: Vansetu
emoji: 🌳
colorFrom: green
colorTo: blue
sdk: docker
pinned: false
---

# VanSetu Platform

A full-stack web application for visualizing and analyzing VanSetu corridor planning data for Delhi NCT.

## Architecture

```
├── backend/           # FastAPI REST API
│   ├── app/
│   │   ├── config.py      # Settings & configuration
│   │   ├── dependencies.py # Dependency injection
│   │   ├── main.py        # FastAPI application
│   │   ├── routers/       # API endpoints
│   │   │   ├── layers.py  # Layer metadata
│   │   │   ├── tiles.py   # XYZ tile server
│   │   │   ├── roads.py   # Road network & corridors
│   │   │   └── stats.py   # Statistics endpoints
│   │   └── services/      # Business logic
│   │       ├── raster_service.py  # GeoTIFF processing
│   │       ├── tile_service.py    # PNG tile generation
│   │       └── road_service.py    # OSM data handling
│   └── requirements.txt
├── frontend/          # React + Vite application
│   └── src/
│       ├── api/       # API client
│       ├── components/
│       │   ├── Map.jsx     # Leaflet map
│       │   └── Sidebar.jsx # Layer controls
│       └── App.jsx
└── Data files
    ├── delhi_ndvi_10m.tif
    └── delhi_lst_modis_daily_celsius.tif
```

## Quick Start

### 1. Backend Setup

\`\`\`bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\\Scripts\\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
\`\`\`

### 2. Frontend Setup

\`\`\`bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev
\`\`\`

### 3. Access the Application

- **Frontend**: http://localhost:5173
- **API Docs**: http://localhost:8000/docs
- **API Base**: http://localhost:8000/api

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| \`/api/layers\` | GET | List all available layers |
| \`/api/tiles/{layer}/{z}/{x}/{y}.png\` | GET | Get map tile |
| \`/api/roads\` | GET | Get road network GeoJSON |
| \`/api/corridors\` | GET | Get corridor GeoJSON |
| \`/api/stats\` | GET | Get all statistics |
| \`/api/stats/{layer}\` | GET | Get layer statistics |
| \`/api/point?lat=&lng=\` | GET | Query values at point |
| \`/api/corridors/{id}/suggestions\` | GET | Get community suggestions for a corridor |
| \`/api/corridors/{id}/suggestions\` | POST | Submit a suggestion for a corridor |
| \`/api/suggestions/{id}/upvote\` | POST | Upvote a suggestion |

## Features

- **Interactive Map**: Leaflet-based map with multiple data layers
- **XYZ Tile Server**: Efficient raster tile serving for large datasets
- **Layer Controls**: Toggle visibility of NDVI, LST, GDI, roads, and corridors
- **Point Query**: Click anywhere to get layer values at that location
- **Statistics Panel**: Real-time statistics for loaded data
- **Community Suggestions**: Users can submit and upvote suggestions for corridors

## Community Suggestions

The platform includes a community participation feature that allows users to:
- Submit suggestions for selected corridors (max 300 characters)
- Upvote existing suggestions
- View community sentiment

**Rate Limits** (to prevent abuse):
- Suggestions: 3 per IP per corridor per hour
- Upvotes: 10 per IP per hour

> **Note:** Community suggestions are advisory and do not affect corridor ranking.

## Data Layers

| Layer | Description | Source |
|-------|-------------|--------|
| NDVI | Vegetation Index | Sentinel-2 (10m resolution) |
| LST | Land Surface Temperature | MODIS (resampled) |
| GDI | Green Deficit Index | Computed: \`0.6×Heat + 0.4×(1-NDVI)\` |
| Roads | Road Network | OpenStreetMap |
| Corridors | Priority Corridors | Top 15% GDI on roads |

## Tech Stack

- **Backend**: FastAPI, Rasterio, NumPy, GeoPandas, OSMnx, MongoDB (PyMongo)
- **Frontend**: React, Vite, Leaflet, Axios
- **Data**: GeoTIFF rasters, OpenStreetMap vectors

## Environment Variables

For community suggestions to work, set up MongoDB:

\`\`\`bash
# MongoDB connection (defaults to localhost)
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=urban_green_corridors
\`\`\`

## License

MIT
