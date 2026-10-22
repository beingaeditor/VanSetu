# Van Setu — Release & Deployment Audit (`docs/RELEASE_AND_DEPLOYMENT_AUDIT.md`)

**Date:** 2026-10-22  
**Repository:** `https://github.com/beingaeditor/VanSetu`  
**Local Workspace:** `/Users/user/Documents/TeleSol-mac-release/VanSetu`  
**Current Branch:** `main`  
**Current `HEAD` Commit:** `2949c4b3e6d0aff208b9d0e1b33aee44cd3df455` (`fix: Update API endpoints to support VITE_API_BASE_URL for production deployment`)

---

## 1. Source-of-Truth & Repository Reconciliation

### 1.1 Git Commit History & Authorship
Inspection of `git log` in `beingaeditor/VanSetu` shows a single unified history shared between the two team contributor accounts (`niharika19singh` / `niharika1912singh@gmail.com` and `beingaeditor`):

| Commit | Author | Subject |
|---|---|---|
| `2949c4b` | `beingaeditor <darkroyalemas.101@gmail.com>` | `fix: Update API endpoints to support VITE_API_BASE_URL for production deployment` |
| `04e1090` | `beingaeditor <darkroyalemas.101@gmail.com>` | `Add Dockerfile for unified Hugging Face Spaces deployment` |
| `f650b98` | `niharika <127630213+niharika19singh@users.noreply.github.com>` | `Merge branch 'main' of https://github.com/niharika19singh/Van-Setu` |
| `6a0df61` | `niharika singh <nonisingh991@gmail.com>` | `Clean repo and track TIF with LFS` |
| `7b7c2fa` | `niharika <127630213+niharika19singh@users.noreply.github.com>` | `Initial commit: Full project with GEE scripts, FastAPI backend, and React frontend` |

**Conclusion:** `beingaeditor/VanSetu` already incorporates the full commit history from `niharika19singh/Van-Setu` (merged at `f650b98`) plus the unified deployment commits (`04e1090` and `2949c4b`). There is no lost work in a separate branch.

---

## 2. Vercel Dashboard Projects Analysis

The organizer/user screenshot of the Vercel dashboard shows four projects under `niharika19singh`'s Vercel account:

| Vercel Project | Live Domain | Last Commit Shown | Git Repository in Screenshot | Assessment |
|---|---|---|---|---|
| **`van-setu-final`** | `van-setu-final.vercel.app` | `fix: Update API endpoints to support...` (`2949c4b`, Mar 24 on `main`) | `niharika19singh/Van-Setu` (synced to `2949c4b`) | **Most up-to-date production deployment** matching `HEAD` (`2949c4b`) with `VITE_API_BASE_URL` support across all frontend API calls. |
| **`van-setu-frontend`** | `van-setu-frontend.vercel.app` | `Initial commit: Full project with GEE...` (`7b7c2fa`, Mar 13 on `main`) | `niharika19singh/Van-Setu` | Older deployment from initial commit (`7b7c2fa`); lacks `VITE_API_BASE_URL` updates. |
| **`vansetu-slk1`** | `vansetu-slk1.vercel.app` | `Initial commit: Full project with GEE...` (`7b7c2fa`, Mar 13 on `main`) | `niharika19singh/Van-Setu` | Duplicate early deployment from initial commit (`7b7c2fa`). |
| **`vansetu`** | `vansetu.vercel.app` | `Initial commit: Full project with GEE...` (`7b7c2fa`, Mar 13 on `main`) | `niharika19singh/Van-Setu` | Earliest deployment from initial commit (`7b7c2fa`). |

### Canonical Target Recommendation
- **Primary Vercel Project:** **`van-setu-final`** (`https://van-setu-final.vercel.app`) is the canonical frontend deployment because it is the only Vercel project deployed from commit `2949c4b` (`fix: Update API endpoints to support VITE_API_BASE_URL for production deployment`), which added `import.meta.env.VITE_API_BASE_URL` support across `Map.jsx`, `Sidebar.jsx`, `PriorityRanking.jsx`, `InterventionPanel.jsx`, `DataCards.jsx`, and `AnalyticsPage.jsx`.
- **Root Directory & `vercel.json`:** Configured via root `vercel.json` (`installCommand: "npm install --prefix frontend"`, `buildCommand: "npm run build --prefix frontend"`, `outputDirectory: "frontend/dist"`, SPA rewrites to `/index.html`).
- **Latest Production Deployment Verified:** `https://van-setu-final.vercel.app` (aliased from `https://van-setu-final-riddbrhsn-niharika-singhs-projects-b3043020.vercel.app`).

---

## 3. Backend Deployment Architecture

1. **Production Backend Host (`frontend/.env.production`):**
   - `frontend/.env.production` sets:
     ```env
     VITE_API_BASE_URL=https://noni1991-vansetu.hf.space
     ```
   - Commit `04e1090` added a root `Dockerfile` designed for Hugging Face Spaces (port `7860`) that builds the frontend into `backend/static` and runs `uvicorn app.main:app --host 0.0.0.0 --port 7860`.
2. **Dockerfile Path Fix Required & Applied:**
   - Commit `6a0df61` moved `delhi_ndvi_10m.tif` and `delhi_lst_modis_daily_celsius.tif` into `backend/data/`, whereas `Dockerfile` lines 51–52 still copied `delhi_ndvi_10m.tif* ./` from the repository root.
   - Updating `Dockerfile` so `backend/data/` (including the GeoTIFF rasters and `delhi_roads_cached.geojson`) is available at `/app/data` ensures containerized deployments work out-of-the-box without external Overpass API dependency.

---

## 4. Feature & File Inventory in Current Workspace

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
