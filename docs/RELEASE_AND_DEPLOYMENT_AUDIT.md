# Van Setu — Release & Deployment Audit (`docs/RELEASE_AND_DEPLOYMENT_AUDIT.md`)

**Date:** 2026-10-22  
**Primary Repository:** `https://github.com/beingaeditor/VanSetu`  
**Render Backend Mirror Repository:** `https://github.com/niharika19singh/van-setu`  
**Local Workspace:** `/Users/user/Documents/TeleSol-mac-release/VanSetu`  
**Current Branch:** `main`  

---

## 1. Source-of-Truth & Repository Reconciliation

### 1.1 Git Commit History & Authorship
Inspection of `git log` in `beingaeditor/VanSetu` and `niharika19singh/van-setu` shows how the repositories relate:

| Commit | Repository | Author | Subject |
|---|---|---|---|
| `9433176` | `beingaeditor/VanSetu` | `niharika <127630213+niharika19singh@users.noreply.github.com>` | `chore: add vercel.json for van-setu-final deployment` |
| `804de59` | `beingaeditor/VanSetu` | `niharika <127630213+niharika19singh@users.noreply.github.com>` | `feat: implement What-if Corridor Ranking, Baseline comparison, and Prune/Gemini integration` |
| `046b09f` | `niharika19singh/van-setu` | `niharika <127630213+niharika19singh@users.noreply.github.com>` | `Remove buildCommand from vercel.json` |
| `a6b6fd4` | `niharika19singh/van-setu` | `niharika singh <nonisingh991@gmail.com>` | `docs: add deep deployment guide for Render + Vercel` |
| `48a69e6` | `niharika19singh/van-setu` | `niharika singh <nonisingh991@gmail.com>` | `feat: initial deployment-ready setup` |

---

## 2. Vercel Dashboard Projects Analysis

The Vercel account (`nonisingh991-2947` / `niharika-singhs-projects-b3043020`) contains four projects:

| Vercel Project | Live Domain | Status | Assessment |
|---|---|---|---|
| **`van-setu-final`** | `https://van-setu-final.vercel.app` | **Active Canonical Production Frontend** | Selected as the sole target frontend project. Proxies `/api/:path*` to `https://van-setu-backend.onrender.com/api/:path*`. |
| **`van-setu-frontend`** | `van-setu-frontend.vercel.app` | Legacy (Untouched) | Older deployment from initial commit; left untouched. |
| **`vansetu-slk1`** | `vansetu-slk1.vercel.app` | Legacy (Untouched) | Duplicate early deployment; left untouched. |
| **`vansetu`** | `vansetu.vercel.app` | Legacy (Untouched) | Earliest deployment; left untouched. |

### `vercel.json` Configuration (`van-setu-final`)
Because `frontend/.env.production` sets `VITE_API_URL=/api`, `vercel.json` is configured with both the monorepo build commands (`frontend/`) and the `/api/:path*` proxy rewrite to the live Render backend:
```json
{
  "installCommand": "npm install --prefix frontend",
  "buildCommand": "npm run build --prefix frontend",
  "outputDirectory": "frontend/dist",
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://van-setu-backend.onrender.com/api/:path*"
    },
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

---

## 3. Production Backend Verification & Reconciliation

### 3.1 Hugging Face Space Check (`https://noni1991-vansetu.hf.space`)
- Direct HTTP checks to `https://noni1991-vansetu.hf.space/health` and `https://noni1991-vansetu.hf.space/` return **`HTTP 404 Not Found`** (Hugging Face error page: *"Sorry, we can't find the page you are looking for"*).
- That Hugging Face Space was only referenced in an older commit and is not a live backend service.

### 3.2 Live Render Production Backend (`https://van-setu-backend.onrender.com`)
- Inspection via the authenticated Render CLI (`render services list -o json`) confirmed the active production backend:
  - **Service Name:** `van-setu-backend`
  - **Service ID:** `srv-d6qfip15pdvs73b9c690`
  - **Live URL:** `https://van-setu-backend.onrender.com`
  - **Region:** Singapore (`singapore`)
  - **Root Directory:** `backend`
  - **Connected GitHub Repository:** `https://github.com/niharika19singh/van-setu` (`branch: main`, `autoDeploy: yes`)
  - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - **Health Check Path:** `/health` (`{"status":"healthy","raster_loaded":true}`)
- Note on Render Free Tier Memory Limits: `niharika19singh/van-setu` uses the lightweight `(57, 79)` Delhi NDVI GeoTIFF (`oid sha256:87599e2bdfd4ad9b2b411b540fd8d4643a40648bc85f3a6bbb42d2a7d5d93d07`, `18 KB`) alongside `delhi_lst_modis_daily_celsius.tif` (`(57, 79)`, `20 KB`) and `delhi_roads_cached.geojson` (`44` Delhi corridors) so the backend starts in `<1s` well within Render's 512 MB RAM ceiling.

---

## 4. Prune + Gemini Configuration (`PRUNE_API_KEY`)

- **Configured Prune Account:** `niharika1912singh@gmail.com` (Google Gemini provider already configured in Prune).
- **Base URL:** `https://api.withprune.com/v1` (`POST /chat/completions`)
- **Backend Service:** `backend/app/services/prune_service.py` -> `POST /api/corridors/explain-ranking`
- **Where to Set `PRUNE_API_KEY`:**
  1. **Local Development:** Create `backend/.env` (gitignored) and add:
     ```env
     PRUNE_API_KEY=<your_prune_api_key>
     PRUNE_BASE_URL=https://api.withprune.com/v1
     PRUNE_MODEL=gemini-2.0-flash
     ```
  2. **Production Backend (Render):** In the Render Dashboard -> Service **`van-setu-backend`** (`srv-d6qfip15pdvs73b9c690`) -> **Environment** -> Add Environment Variable:
     - Key: `PRUNE_API_KEY`
     - Value: `<your_prune_api_key>`
- When `PRUNE_API_KEY` is not set, `POST /api/corridors/explain-ranking` returns `HTTP 200` with `"provider": "deterministic-fallback"`, `"live_ai": false`, and a quantitative analytical summary of the active `heat_weight`, top corridors, and baseline rank shifts.

---

## 5. Feature & File Inventory

| Component | Status | Key Files |
|---|---|---|
| **What-if Corridor Ranking (`GET /api/corridors/rank`)** | Implemented & Verified | `backend/app/routers/roads.py`, `backend/app/services/road_service.py` |
| **Baseline vs. What-if Rank Changes** | Implemented & Verified | `backend/app/services/road_service.py`, `frontend/src/components/WhatIfRanking.jsx` |
| **6-Factor Priority Model + Tri-Vector (Priority, Feasibility, Confidence)** | Implemented & Verified | `backend/app/services/scoring_service.py`, `frontend/src/components/PriorityRanking.jsx` |
| **5-Scenario Sensitivity Analysis (`/api/corridors/sensitivity`)** | Implemented & Verified | `backend/app/services/scoring_service.py`, `backend/app/routers/roads.py` |
| **CPWD Lifecycle Costing & 5 Intervention Archetypes** | Implemented & Verified | `backend/app/services/intervention_service.py`, `frontend/src/components/InterventionPanel.jsx` |
| **Prune + Gemini Integration (`POST /api/corridors/explain-ranking`)** | Implemented & Verified | `backend/app/services/prune_service.py`, `backend/app/routers/roads.py` |
| **Scientific Data Provenance (`/api/layers/metadata`)** | Implemented & Verified | `backend/app/config.py`, `backend/app/routers/layers.py` |
| **Offline Verified Delhi Road Cache (44 Corridors)** | Implemented & Verified | `backend/data/delhi_roads_cached.geojson` |
