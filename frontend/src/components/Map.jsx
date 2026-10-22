/**
 * Map Component — Centre Spatial Canvas of the Van Setu Urban Climate Studio.
 *
 * P0 Production Hardened:
 * - Unwatermarked Esri ArcGIS Online Dark Gray Canvas & World Imagery basemaps
 *   with crisp Reference Labels overlaid above raster layers (zero Carto watermarks).
 * - All 9 spatial layer toggles visible and verified:
 *   1. Vegetation (NDVI)        — /api/tiles/ndvi/{z}/{x}/{y}.png
 *   2. Temperature (LST)        — /api/tiles/lst/{z}/{x}/{y}.png
 *   3. Priority Index (GDI)     — /api/tiles/gdi/{z}/{x}/{y}.png
 *   4. Road Network             — /api/roads/simple
 *   5. Van Setu Corridors       — /api/corridors (synced with live What-If scores)
 *   6. AQI Stations             — /api/aqi/stations (39 CPCB monitors)
 *   7. Roads Overlay            — Esri World_Transportation reference layer
 *   8. Parks & Green            — Delhi Urban Forests & Parks GeoJSON + Overpass enrichment
 *   9. Residential              — Delhi Residential Zones GeoJSON + Overpass enrichment
 * - Safe geometry coordinate extraction for LineString/MultiLineString during district filtering.
 * - Non-blocking per-layer error & retry states.
 */

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  useMap,
  useMapEvents,
  CircleMarker,
  Popup,
  Tooltip,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import { getTileUrl, roadsApi, statsApi, aqiApi } from "../api";
import "./Map.css";

import LocationSearch from "./LocationSearch";
import districts from "../data/delhi_districts.json";

const DELHI_CENTER = [28.6139, 77.209];

// Unwatermarked Esri ArcGIS Online basemap & reference tile endpoints
const BASEMAPS = {
  dark: {
    id: "dark",
    label: "Dark Canvas",
    baseUrl:
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    labelUrl:
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
    attribution:
      "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ | Van Setu Spatial Studio",
  },
  satellite: {
    id: "satellite",
    label: "Satellite",
    baseUrl:
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    labelUrl:
      "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
    attribution:
      "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics",
  },
};

const ESRI_TRANSPORTATION_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}";

// Curated Delhi Major Urban Forests & Parks (instant fallback & baseline for Parks & Green layer)
const DELHI_PARKS_BASELINE = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { name: "Central Ridge Reserve Forest", type: "forest" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.155, 28.595],
            [77.195, 28.595],
            [77.205, 28.645],
            [77.168, 28.645],
            [77.155, 28.595],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "Sanjay Van Urban Forest", type: "forest" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.158, 28.522],
            [77.188, 28.522],
            [77.188, 28.546],
            [77.158, 28.546],
            [77.158, 28.522],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "Lodhi Gardens & Nehru Park Green Belt", type: "park" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.192, 28.582],
            [77.228, 28.582],
            [77.228, 28.602],
            [77.192, 28.602],
            [77.192, 28.582],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "Yamuna Biodiversity & Floodplain Park", type: "nature_reserve" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.215, 28.705],
            [77.245, 28.705],
            [77.255, 28.748],
            [77.218, 28.748],
            [77.215, 28.705],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "Jahanpanah City Forest", type: "forest" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.225, 28.524],
            [77.252, 28.524],
            [77.252, 28.542],
            [77.225, 28.542],
            [77.225, 28.524],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "Northern Kamla Nehru Ridge", type: "forest" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.208, 28.672],
            [77.226, 28.672],
            [77.226, 28.698],
            [77.208, 28.698],
            [77.208, 28.672],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "Swarn Jayanti Park (Rohini)", type: "park" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.105, 28.718],
            [77.128, 28.718],
            [77.128, 28.738],
            [77.105, 28.738],
            [77.105, 28.718],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "Indraprastha & Millennium Riverfront Park", type: "park" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.248, 28.585],
            [77.268, 28.585],
            [77.268, 28.618],
            [77.248, 28.618],
            [77.248, 28.585],
          ],
        ],
      },
    },
  ],
};

// Curated Delhi Residential Planning Zones (instant baseline for Residential layer)
const DELHI_RESIDENTIAL_BASELINE = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { name: "Rohini Residential Sub-City (Sectors 1–24)" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.065, 28.695],
            [77.145, 28.695],
            [77.145, 28.752],
            [77.065, 28.752],
            [77.065, 28.695],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "Dwarka Residential Sub-City (Sectors 1–23)" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.015, 28.555],
            [77.085, 28.555],
            [77.085, 28.618],
            [77.015, 28.618],
            [77.015, 28.555],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "Janakpuri – Rajouri Garden Residential Cluster" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.068, 28.618],
            [77.138, 28.618],
            [77.138, 28.658],
            [77.068, 28.658],
            [77.068, 28.618],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "Karol Bagh – Patel Nagar High-Density Residential" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.155, 28.638],
            [77.202, 28.638],
            [77.202, 28.668],
            [77.155, 28.668],
            [77.155, 28.638],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "Lajpat Nagar – Greater Kailash – Saket Residential Zone" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.195, 28.518],
            [77.262, 28.518],
            [77.262, 28.572],
            [77.195, 28.572],
            [77.195, 28.518],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "Mayur Vihar – Patparganj Trans-Yamuna Residential" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.278, 28.595],
            [77.332, 28.595],
            [77.332, 28.642],
            [77.278, 28.642],
            [77.278, 28.595],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "Shahdara – Yamuna Vihar High-Density Residential" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.258, 28.662],
            [77.318, 28.662],
            [77.318, 28.712],
            [77.258, 28.712],
            [77.258, 28.662],
          ],
        ],
      },
    },
  ],
};

/** Map priority score → color using a green→yellow→orange→red gradient */
function priorityColor(value, metadata) {
  const pMin = metadata?.priority_min ?? 0.3;
  const pMax = metadata?.priority_max ?? 0.7;
  const range = pMax - pMin || 0.1;
  const t = Math.max(0, Math.min(1, (value - pMin) / range));
  const stops = [
    [26, 152, 80], // green
    [145, 207, 96], // light green
    [254, 224, 139], // yellow
    [252, 141, 89], // orange
    [215, 48, 39], // red
  ];
  const segIdx = Math.min(t * (stops.length - 1), stops.length - 1.001);
  const i = Math.floor(segIdx);
  const f = segIdx - i;
  const c0 = stops[i];
  const c1 = stops[Math.min(i + 1, stops.length - 1)];
  const r = Math.round(c0[0] + (c1[0] - c0[0]) * f);
  const g = Math.round(c0[1] + (c1[1] - c0[1]) * f);
  const b = Math.round(c0[2] + (c1[2] - c0[2]) * f);
  return `rgb(${r}, ${g}, ${b})`;
}

/** Safely extract a representative [lon, lat] point from any GeoJSON geometry */
function extractRepresentativeLonLat(geometry) {
  if (!geometry || !geometry.coordinates) return null;
  const { type, coordinates } = geometry;
  if (type === "Point" && Array.isArray(coordinates) && coordinates.length >= 2) {
    return [Number(coordinates[0]), Number(coordinates[1])];
  }
  if (
    type === "LineString" &&
    Array.isArray(coordinates) &&
    coordinates.length > 0 &&
    Array.isArray(coordinates[0])
  ) {
    const mid = coordinates[Math.floor(coordinates.length / 2)];
    return [Number(mid[0]), Number(mid[1])];
  }
  if (
    (type === "MultiLineString" || type === "Polygon") &&
    Array.isArray(coordinates) &&
    coordinates.length > 0 &&
    Array.isArray(coordinates[0]) &&
    Array.isArray(coordinates[0][0])
  ) {
    const pt = coordinates[0][0];
    return [Number(pt[0]), Number(pt[1])];
  }
  return null;
}

function SearchController({ location }) {
  const map = useMap();

  useEffect(() => {
    if (location && Number.isFinite(location.lat) && Number.isFinite(location.lon)) {
      map.flyTo([location.lat, location.lon], 13, { duration: 1.1 });
    }
  }, [location, map]);

  return null;
}

function ClickHandler({ onPointQuery }) {
  useMapEvents({
    click: (e) => {
      if (e?.latlng) {
        onPointQuery(e.latlng.lat, e.latlng.lng);
      }
    },
  });
  return null;
}

function MapController({ selectedCorridor, fitTrigger, resetTrigger }) {
  const map = useMap();

  // Only zoom to corridor when user explicitly triggers fitTrigger (clicking a corridor card or "Fit Corridor")
  useEffect(() => {
    if (fitTrigger > 0 && selectedCorridor && selectedCorridor.geometry) {
      try {
        const bounds = L.geoJSON(selectedCorridor).getBounds();
        if (bounds.isValid()) {
          map.fitBounds(bounds, {
            padding: [65, 65],
            maxZoom: 14,
            animate: true,
          });
        }
      } catch (err) {
        console.error("Failed to fit corridor bounds:", err);
      }
    }
  }, [fitTrigger, selectedCorridor, map]);

  useEffect(() => {
    if (resetTrigger > 0) {
      map.flyTo(DELHI_CENTER, 11, { duration: 0.9 });
    }
  }, [resetTrigger, map]);

  return null;
}

export default function Map({
  activeLayers,
  setActiveLayers,
  selectedCorridor: externalSelectedCorridor,
  onSelectCorridor,
  rankedCorridors = [],
  heatWeight = 0.6,
}) {
  const [corridors, setCorridors] = useState(null);
  const [roads, setRoads] = useState(null);
  const [aqiStations, setAqiStations] = useState(null);
  const [pointData, setPointData] = useState(null);

  const [basemapStyle, setBasemapStyle] = useState("dark");
  const [internalSelectedCorridor, setInternalSelectedCorridor] = useState(null);
  const [rasterOpacity, setRasterOpacity] = useState(0.72);
  const [fitTrigger, setFitTrigger] = useState(0);
  const [resetTrigger, setResetTrigger] = useState(0);

  // Per-layer loading & error states for transparent diagnostics + retry
  const [layerLoading, setLayerLoading] = useState({});
  const [layerErrors, setLayerErrors] = useState({});
  const [tileRetryKey, setTileRetryKey] = useState(0);

  const selectedCorridor =
    externalSelectedCorridor !== undefined
      ? externalSelectedCorridor
      : internalSelectedCorridor;

  const updateSelectedCorridor = useCallback(
    (feature, shouldZoom = false) => {
      if (onSelectCorridor) {
        onSelectCorridor(feature);
      } else {
        setInternalSelectedCorridor(feature);
      }
      if (shouldZoom) {
        setFitTrigger((c) => c + 1);
      }
    },
    [onSelectCorridor]
  );

  const [searchedLocation, setSearchedLocation] = useState(null);
  const [selectedDistrict, setSelectedDistrict] = useState(null);
  const [parkData, setParkData] = useState(DELHI_PARKS_BASELINE);
  const [residentialData, setResidentialData] = useState(
    DELHI_RESIDENTIAL_BASELINE
  );
  const overpassParksLoadedRef = useRef(false);
  const overpassResLoadedRef = useRef(false);

  // Fetch Corridors GeoJSON
  const loadCorridors = useCallback(() => {
    setLayerLoading((prev) => ({ ...prev, corridors: true }));
    setLayerErrors((prev) => ({ ...prev, corridors: null }));
    roadsApi
      .corridors(85, true)
      .then((res) => {
        setCorridors(res.data);
        setLayerLoading((prev) => ({ ...prev, corridors: false }));
      })
      .catch((err) => {
        console.error("Corridors load failed:", err);
        setLayerErrors((prev) => ({
          ...prev,
          corridors: "Could not load corridors GeoJSON",
        }));
        setLayerLoading((prev) => ({ ...prev, corridors: false }));
      });
  }, []);

  useEffect(() => {
    if (activeLayers.corridors && !corridors && !layerLoading.corridors) {
      loadCorridors();
    }
  }, [activeLayers.corridors, corridors, layerLoading.corridors, loadCorridors]);

  // Fetch Walkable Road Network GeoJSON
  const loadRoads = useCallback(() => {
    setLayerLoading((prev) => ({ ...prev, roads: true }));
    setLayerErrors((prev) => ({ ...prev, roads: null }));
    roadsApi
      .simple()
      .then((res) => {
        setRoads(res.data);
        setLayerLoading((prev) => ({ ...prev, roads: false }));
      })
      .catch((err) => {
        console.error("Roads load failed:", err);
        setLayerErrors((prev) => ({
          ...prev,
          roads: "Could not load road network",
        }));
        setLayerLoading((prev) => ({ ...prev, roads: false }));
      });
  }, []);

  useEffect(() => {
    if (activeLayers.roads && !roads && !layerLoading.roads) {
      loadRoads();
    }
  }, [activeLayers.roads, roads, layerLoading.roads, loadRoads]);

  // Fetch CPCB AQI Stations GeoJSON
  const loadAqiStations = useCallback(() => {
    setLayerLoading((prev) => ({ ...prev, aqi: true }));
    setLayerErrors((prev) => ({ ...prev, aqi: null }));
    aqiApi
      .stations()
      .then((res) => {
        setAqiStations(res.data);
        setLayerLoading((prev) => ({ ...prev, aqi: false }));
      })
      .catch((err) => {
        console.error("AQI stations load failed:", err);
        setLayerErrors((prev) => ({
          ...prev,
          aqi: "Could not load AQI stations",
        }));
        setLayerLoading((prev) => ({ ...prev, aqi: false }));
      });
  }, []);

  useEffect(() => {
    if (activeLayers.aqi && !aqiStations && !layerLoading.aqi) {
      loadAqiStations();
    }
  }, [activeLayers.aqi, aqiStations, layerLoading.aqi, loadAqiStations]);

  // Optional Overpass enrichment for Parks & Green (with instant local baseline so it never blocks or crashes)
  useEffect(() => {
    if (activeLayers.osmParks && !overpassParksLoadedRef.current) {
      overpassParksLoadedRef.current = true;
      const query = `[out:json][timeout:12][bbox:28.45,77.05,28.75,77.32];(way["leisure"="park"]["name"];way["landuse"="forest"]["name"];);out geom 80;`;
      fetch(
        `https://overpass-api.de/api/interpreter?data=${encodeURIComponent(
          query
        )}`
      )
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data && Array.isArray(data.elements)) {
            const extraFeatures = data.elements
              .filter(
                (el) => Array.isArray(el.geometry) && el.geometry.length > 2
              )
              .map((el) => ({
                type: "Feature",
                properties: {
                  name: el.tags?.name || "Urban Green Space",
                  type: el.tags?.leisure || el.tags?.landuse || "park",
                },
                geometry: {
                  type: "Polygon",
                  coordinates: [el.geometry.map((p) => [p.lon, p.lat])],
                },
              }));
            if (extraFeatures.length > 0) {
              setParkData({
                type: "FeatureCollection",
                features: [
                  ...DELHI_PARKS_BASELINE.features,
                  ...extraFeatures,
                ],
              });
            }
          }
        })
        .catch(() => {
          // Baseline parks remain active and visible
        });
    }
  }, [activeLayers.osmParks]);

  // Optional Overpass enrichment for Residential Zones (with instant local baseline)
  useEffect(() => {
    if (activeLayers.osmResidential && !overpassResLoadedRef.current) {
      overpassResLoadedRef.current = true;
      const query = `[out:json][timeout:12][bbox:28.50,77.08,28.72,77.30];(way["landuse"="residential"]["name"];);out geom 80;`;
      fetch(
        `https://overpass-api.de/api/interpreter?data=${encodeURIComponent(
          query
        )}`
      )
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data && Array.isArray(data.elements)) {
            const extraFeatures = data.elements
              .filter(
                (el) => Array.isArray(el.geometry) && el.geometry.length > 2
              )
              .map((el) => ({
                type: "Feature",
                properties: {
                  name: el.tags?.name || "Residential Precinct",
                },
                geometry: {
                  type: "Polygon",
                  coordinates: [el.geometry.map((p) => [p.lon, p.lat])],
                },
              }));
            if (extraFeatures.length > 0) {
              setResidentialData({
                type: "FeatureCollection",
                features: [
                  ...DELHI_RESIDENTIAL_BASELINE.features,
                  ...extraFeatures,
                ],
              });
            }
          }
        })
        .catch(() => {
          // Baseline residential zones remain active and visible
        });
    }
  }, [activeLayers.osmResidential]);

  const handlePointQuery = useCallback(async (lat, lng) => {
    try {
      const res = await statsApi.point(lat, lng);
      setPointData(res.data);
    } catch (err) {
      console.error("Point query error:", err);
    }
  }, []);

  const handleLocationFound = (location) => {
    if (!location) return;
    const locName = (location.name || "").toLowerCase();
    const district = districts.features.find(
      (d) =>
        locName.includes(d.properties.district.toLowerCase()) ||
        d.properties.district.toLowerCase() === locName
    );
    if (district) {
      setSelectedDistrict(district);
    }
    setSearchedLocation(location);
  };

  const toggleLayer = (layerKey) => {
    if (!setActiveLayers) return;
    setActiveLayers((prev) => ({
      ...prev,
      [layerKey]: !prev[layerKey],
    }));
  };

  // Merge live What-If ranked corridor scores into the GeoJSON corridors collection
  const enrichedCorridors = useMemo(() => {
    if (!corridors || !Array.isArray(corridors.features)) return null;
    const scoreMap = new globalThis.Map();
    (rankedCorridors || []).forEach((rc) => {
      if (rc && rc.id) scoreMap.set(rc.id, rc);
    });

    let features = corridors.features.map((f) => {
      const fid = f.properties?.id || f.id;
      const live = fid ? scoreMap.get(fid) : null;
      if (!live) return f;
      return {
        ...f,
        properties: {
          ...f.properties,
          priority_score: live.score ?? f.properties?.priority_score,
          what_if_score: live.score,
          what_if_rank: live.rank,
          baseline_rank: live.baseline_rank,
          rank_change: live.rank_change,
          heat: live.heat,
          ndvi: live.ndvi,
          green_deficit: live.green_deficit,
        },
      };
    });

    if (selectedDistrict) {
      try {
        const districtBounds = L.geoJSON(selectedDistrict).getBounds();
        if (districtBounds.isValid()) {
          features = features.filter((f) => {
            const lonLat = extractRepresentativeLonLat(f.geometry);
            if (!lonLat) return false;
            const [lon, lat] = lonLat;
            if (!Number.isFinite(lat) || !Number.isFinite(lon)) return false;
            return districtBounds.contains(L.latLng(lat, lon));
          });
        }
      } catch (err) {
        console.error("District filter bounds error:", err);
      }
    }

    return {
      ...corridors,
      features,
    };
  }, [corridors, rankedCorridors, selectedDistrict]);

  const corridorStyle = useCallback(
    (feature) => {
      const score =
        feature.properties?.what_if_score ??
        feature.properties?.priority_score ??
        feature.properties?.gdi_mean ??
        0.5;
      const fid = feature.properties?.id || feature.id;
      const selId =
        selectedCorridor?.properties?.id || selectedCorridor?.id || null;
      const isSelected = Boolean(fid && selId && fid === selId);
      return {
        color: priorityColor(score, corridors?.metadata),
        weight: isSelected ? 7 : 4.5,
        opacity: isSelected ? 1.0 : 0.88,
      };
    },
    [corridors?.metadata, selectedCorridor]
  );

  const roadNetworkStyle = useMemo(
    () => ({
      color: "#38bdf8",
      weight: 2.2,
      opacity: 0.72,
    }),
    []
  );

  const selectedName =
    selectedCorridor?.properties?.name || selectedCorridor?.name || "Corridor";
  const selectedScore =
    selectedCorridor?.properties?.what_if_score ??
    selectedCorridor?.properties?.priority_score ??
    selectedCorridor?.score ??
    null;

  const activeBasemap = BASEMAPS[basemapStyle] || BASEMAPS.dark;

  // Count active layers for badge
  const activeLayerCount = Object.values(activeLayers || {}).filter(Boolean).length;

  // Point inspection coordinates (supporting both backend `{ location: { lat, lng } }` and `{ coordinates: { lat, lng } }`)
  const ptLat = pointData?.location?.lat ?? pointData?.coordinates?.lat;
  const ptLng = pointData?.location?.lng ?? pointData?.coordinates?.lng;

  return (
    <div className="map-container" data-testid="interactive-map-canvas">
      {/* Top-Left Floating OVERLAYS Control — All 9 Spatial Layers Accessible */}
      <div className="floating-overlays-card" data-testid="floating-overlays-card">
        <div className="overlays-card-header">
          <span className="overlays-title">
            OVERLAYS ({activeLayerCount} Active)
          </span>
          <div className="basemap-mini-Readout">
            <button
              type="button"
              data-testid="basemap-toggle-btn"
              className="overlays-more-btn"
              onClick={() =>
                setBasemapStyle((prev) =>
                  prev === "dark" ? "satellite" : "dark"
                )
              }
              title="Switch between Dark Canvas and Satellite Imagery basemap"
            >
              {basemapStyle === "dark" ? "🛰️ Satellite" : "🗺️ Dark Map"}
            </button>
          </div>
        </div>

        <div className="overlays-toggle-list" role="group" aria-label="Map Layer Toggles">
          {/* 1. Temperature (LST) */}
          <label className="overlay-check-row" data-testid="layer-toggle-lst">
            <input
              type="checkbox"
              checked={Boolean(activeLayers.lst)}
              onChange={() => toggleLayer("lst")}
            />
            <span className="overlay-dot" style={{ background: "#ef4444" }} />
            <span className="overlay-name">Temperature (LST)</span>
          </label>

          {/* 2. Vegetation (NDVI) */}
          <label className="overlay-check-row" data-testid="layer-toggle-ndvi">
            <input
              type="checkbox"
              checked={Boolean(activeLayers.ndvi)}
              onChange={() => toggleLayer("ndvi")}
            />
            <span className="overlay-dot" style={{ background: "#10b981" }} />
            <span className="overlay-name">Vegetation (NDVI)</span>
          </label>

          {/* 3. Priority Index (GDI) */}
          <label className="overlay-check-row" data-testid="layer-toggle-gdi">
            <input
              type="checkbox"
              checked={Boolean(activeLayers.gdi)}
              onChange={() => toggleLayer("gdi")}
            />
            <span className="overlay-dot" style={{ background: "#f59e0b" }} />
            <span className="overlay-name">Priority Index (GDI)</span>
          </label>

          {/* 4. Van Setu Corridors */}
          <label className="overlay-check-row" data-testid="layer-toggle-corridors">
            <input
              type="checkbox"
              checked={Boolean(activeLayers.corridors)}
              onChange={() => toggleLayer("corridors")}
            />
            <span className="overlay-dot" style={{ background: "#00f2fe" }} />
            <span className="overlay-name">Van Setu Corridors</span>
          </label>

          {/* 5. Road Network */}
          <label className="overlay-check-row" data-testid="layer-toggle-roads">
            <input
              type="checkbox"
              checked={Boolean(activeLayers.roads)}
              onChange={() => toggleLayer("roads")}
            />
            <span className="overlay-dot" style={{ background: "#38bdf8" }} />
            <span className="overlay-name">Road Network</span>
          </label>

          {/* 6. AQI Stations */}
          <label className="overlay-check-row" data-testid="layer-toggle-aqi">
            <input
              type="checkbox"
              checked={Boolean(activeLayers.aqi)}
              onChange={() => toggleLayer("aqi")}
            />
            <span className="overlay-dot" style={{ background: "#a855f7" }} />
            <span className="overlay-name">AQI Stations</span>
          </label>

          {/* 7. Roads Overlay */}
          <label className="overlay-check-row" data-testid="layer-toggle-osmRoads">
            <input
              type="checkbox"
              checked={Boolean(activeLayers.osmRoads)}
              onChange={() => toggleLayer("osmRoads")}
            />
            <span className="overlay-dot" style={{ background: "#cbd5e1" }} />
            <span className="overlay-name">Roads Overlay</span>
          </label>

          {/* 8. Parks & Green */}
          <label className="overlay-check-row" data-testid="layer-toggle-osmParks">
            <input
              type="checkbox"
              checked={Boolean(activeLayers.osmParks)}
              onChange={() => toggleLayer("osmParks")}
            />
            <span className="overlay-dot" style={{ background: "#22c55e" }} />
            <span className="overlay-name">Parks &amp; Green</span>
          </label>

          {/* 9. Residential */}
          <label className="overlay-check-row" data-testid="layer-toggle-osmResidential">
            <input
              type="checkbox"
              checked={Boolean(activeLayers.osmResidential)}
              onChange={() => toggleLayer("osmResidential")}
            />
            <span className="overlay-dot" style={{ background: "#d4a76a" }} />
            <span className="overlay-name">Residential</span>
          </label>
        </div>

        {/* Non-blocking Layer Error / Retry Strip */}
        {Object.entries(layerErrors).some(([, msg]) => Boolean(msg)) && (
          <div className="layer-error-retry-box" role="status">
            {Object.entries(layerErrors).map(([key, msg]) =>
              msg ? (
                <div key={key} className="layer-err-item">
                  <span>⚠️ {msg}</span>
                  <button
                    type="button"
                    onClick={() => {
                      if (key === "corridors") loadCorridors();
                      else if (key === "roads") loadRoads();
                      else if (key === "aqi") loadAqiStations();
                      else {
                        setLayerErrors((prev) => ({ ...prev, [key]: null }));
                        setTileRetryKey((c) => c + 1);
                      }
                    }}
                  >
                    Retry
                  </button>
                </div>
              ) : null
            )}
          </div>
        )}

        {/* Dynamic Priority / Raster Gradient Legend */}
        <div className="overlays-mini-legend" data-testid="map-active-legend">
          <div className="mini-legend-labels">
            <span>
              {activeLayers.lst
                ? "Cooler (24°C)"
                : activeLayers.ndvi
                ? "Bare (-0.2)"
                : "Low Stress"}
            </span>
            <span>
              {activeLayers.lst
                ? "Hotter (29°C+)"
                : activeLayers.ndvi
                ? "Dense Canopy (0.8)"
                : "High Priority"}
            </span>
          </div>
          <div
            className="mini-legend-bar"
            style={{
              background: activeLayers.ndvi && !activeLayers.gdi && !activeLayers.lst
                ? "linear-gradient(90deg, #ffffcc, #78c679, #006837)"
                : activeLayers.lst && !activeLayers.gdi
                ? "linear-gradient(90deg, #313695, #74add1, #fee090, #f46d43, #a50026)"
                : "linear-gradient(90deg, #1a9850, #91cf60, #fee08b, #fc8d59, #d73027)",
            }}
          />
        </div>
      </div>

      {/* Top-Right Search & Map Action Controls */}
      <div className="map-top-right-controls">
        <LocationSearch onLocationFound={handleLocationFound} />
        <div className="map-quick-nav-btns">
          {selectedCorridor && (
            <button
              type="button"
              data-testid="fit-corridor-btn"
              className="map-action-pill"
              onClick={() => setFitTrigger((c) => c + 1)}
              title="Zoom to selected corridor"
            >
              🎯 Fit Corridor
            </button>
          )}
          <button
            type="button"
            data-testid="reset-map-view-btn"
            className="map-action-pill"
            onClick={() => {
              setSelectedDistrict(null);
              setResetTrigger((c) => c + 1);
            }}
            title="Reset map to Delhi NCT overview"
          >
            🗺️ Reset View
          </button>
        </div>
      </div>

      {selectedDistrict && (
        <div className="district-indicator" data-testid="district-filter-pill">
          <span>📍 {selectedDistrict.properties.district} District</span>
          <button
            type="button"
            className="district-clear-btn"
            onClick={() => setSelectedDistrict(null)}
            aria-label="Clear district filter"
          >
            ✕
          </button>
        </div>
      )}

      {/* Point Inspection Floating Card */}
      {pointData && (
        <div className="point-info" data-testid="point-inspection-popup">
          <button
            type="button"
            className="close-btn"
            onClick={() => setPointData(null)}
            aria-label="Close point inspection"
          >
            ✕
          </button>
          <h4>Spatial Pixel Inspection</h4>
          <div className="point-coords">
            {Number.isFinite(ptLat) ? `${ptLat.toFixed(4)}°N` : "—"},{" "}
            {Number.isFinite(ptLng) ? `${ptLng.toFixed(4)}°E` : "—"}
          </div>
          <div className="point-values">
            <div className="value-row">
              <span className="label">NDVI (10m)</span>
              <span className="value">
                {pointData.values?.ndvi != null
                  ? Number(pointData.values.ndvi).toFixed(3)
                  : "NoData"}
              </span>
              <span className="interpretation">Sentinel-2</span>
            </div>
            <div className="value-row">
              <span className="label">LST (1km)</span>
              <span className="value">
                {pointData.values?.lst != null
                  ? `${Number(pointData.values.lst).toFixed(1)}°C`
                  : "NoData"}
              </span>
              <span className="interpretation">MODIS</span>
            </div>
            <div className="value-row">
              <span className="label">GDI Index</span>
              <span className="value priority">
                {pointData.values?.gdi != null
                  ? Number(pointData.values.gdi).toFixed(3)
                  : "NoData"}
              </span>
              <span className="interpretation">Composite</span>
            </div>
            {pointData.values?.aqi_raw != null && (
              <div className="value-row">
                <span className="label">PM2.5 IDW</span>
                <span className="value">
                  {Math.round(Number(pointData.values.aqi_raw))} µg/m³
                </span>
                <span className="interpretation">CPCB</span>
              </div>
            )}
          </div>
        </div>
      )}

      <MapContainer
        center={DELHI_CENTER}
        zoom={11}
        minZoom={10}
        maxZoom={16}
        style={{ height: "100%", width: "100%" }}
      >
        <SearchController location={searchedLocation} />

        {/* 1. Unwatermarked Esri ArcGIS Online Base Tile Layer */}
        <TileLayer
          key={`base-${activeBasemap.id}`}
          url={activeBasemap.baseUrl}
          attribution={activeBasemap.attribution}
          zIndex={100}
        />

        {/* 2. Raster Scientific Overlays (NDVI, LST, GDI) with clean transparency */}
        {activeLayers.ndvi && (
          <TileLayer
            key={`ndvi-${tileRetryKey}`}
            url={getTileUrl("ndvi")}
            opacity={rasterOpacity}
            zIndex={210}
          />
        )}

        {activeLayers.lst && (
          <TileLayer
            key={`lst-${tileRetryKey}`}
            url={getTileUrl("lst")}
            opacity={rasterOpacity}
            zIndex={220}
          />
        )}

        {activeLayers.gdi && (
          <TileLayer
            key={`gdi-${tileRetryKey}`}
            url={getTileUrl("gdi")}
            opacity={rasterOpacity}
            zIndex={230}
          />
        )}

        {/* 3. Roads Overlay (Esri World Transportation Reference) */}
        {activeLayers.osmRoads && (
          <TileLayer
            key="esri-transportation-overlay"
            url={ESRI_TRANSPORTATION_URL}
            opacity={0.78}
            zIndex={260}
          />
        )}

        {/* 4. Crisp Place & Boundary Reference Labels Above Raster Layers */}
        <TileLayer
          key={`labels-${activeBasemap.id}`}
          url={activeBasemap.labelUrl}
          opacity={0.9}
          zIndex={280}
        />

        {/* 5. Parks & Green Overlay */}
        {activeLayers.osmParks && parkData && (
          <GeoJSON
            key={`parks-overlay-${parkData.features?.length || 0}`}
            data={parkData}
            style={{
              color: "#22c55e",
              weight: 1.5,
              fillColor: "#16a34a",
              fillOpacity: 0.35,
              opacity: 0.85,
            }}
            onEachFeature={(feature, layer) => {
              if (feature.properties?.name) {
                layer.bindTooltip(
                  `🌿 <strong>${feature.properties.name}</strong>`,
                  {
                    sticky: true,
                    className: "corridor-tooltip",
                  }
                );
              }
            }}
          />
        )}

        {/* 6. Residential Zones Overlay */}
        {activeLayers.osmResidential && residentialData && (
          <GeoJSON
            key={`residential-overlay-${residentialData.features?.length || 0}`}
            data={residentialData}
            style={{
              color: "#f59e0b",
              weight: 1.4,
              fillColor: "#d97706",
              fillOpacity: 0.22,
              opacity: 0.7,
              dashArray: "4 3",
            }}
            onEachFeature={(feature, layer) => {
              if (feature.properties?.name) {
                layer.bindTooltip(
                  `🏘️ <strong>${feature.properties.name}</strong>`,
                  {
                    sticky: true,
                    className: "corridor-tooltip",
                  }
                );
              }
            }}
          />
        )}

        {/* 7. Selected District Boundary Highlight */}
        {selectedDistrict && (
          <GeoJSON
            key={`district-${selectedDistrict.properties?.district}`}
            data={selectedDistrict}
            style={{
              color: "#00f2fe",
              weight: 3.5,
              fillOpacity: 0.06,
            }}
          />
        )}

        {/* 8. Walkable Road Network Layer */}
        {activeLayers.roads && roads && (
          <GeoJSON
            key={`roads-network-${roads.features?.length || 0}`}
            data={roads}
            style={roadNetworkStyle}
            onEachFeature={(feature, layer) => {
              const rname =
                feature.properties?.name ||
                feature.properties?.highway ||
                "Road Segment";
              const gdiMean = feature.properties?.gdi_mean;
              layer.bindTooltip(
                `🛣️ <strong>${rname}</strong>${
                  gdiMean != null ? `<br/>GDI: ${Number(gdiMean).toFixed(3)}` : ""
                }`,
                { sticky: true, className: "corridor-tooltip" }
              );
            }}
          />
        )}

        {/* 9. Van Setu Priority Corridors Layer */}
        {activeLayers.corridors && enrichedCorridors && (
          <GeoJSON
            key={`corridors-${heatWeight.toFixed(2)}-${
              selectedDistrict?.properties?.district || "all"
            }-${selectedCorridor?.properties?.id || selectedCorridor?.id || "none"}`}
            data={enrichedCorridors}
            style={corridorStyle}
            onEachFeature={(feature, layer) => {
              const name = feature.properties?.name || "Corridor";
              const score =
                feature.properties?.what_if_score ??
                feature.properties?.priority_score ??
                feature.properties?.gdi_mean;
              const rank = feature.properties?.what_if_rank;
              const tier = feature.properties?.severity_tier;
              const ctype = feature.properties?.corridor_type?.replace(
                /_/g,
                " "
              );
              layer.bindTooltip(
                `<strong>${name}</strong>${
                  rank != null ? ` (Rank #${rank})` : ""
                }${
                  score != null ? `<br/>Score: ${Number(score).toFixed(3)}` : ""
                }${tier ? `<br/>Severity: ${tier}` : ""}${
                  ctype ? `<br/>Type: ${ctype}` : ""
                }`,
                { sticky: true, className: "corridor-tooltip" }
              );
              layer.on("click", () => {
                updateSelectedCorridor(feature, true);
              });
            }}
          />
        )}

        {/* Outer Glow + Bright Cyan Highlight for Selected Corridor */}
        {selectedCorridor && selectedCorridor.geometry && (
          <>
            <GeoJSON
              key={`glow-${
                selectedCorridor.properties?.id ||
                selectedCorridor.id ||
                "corridor"
              }`}
              data={selectedCorridor}
              style={{
                color: "#0284c7",
                weight: 15,
                opacity: 0.42,
              }}
            />
            <GeoJSON
              key={`selected-${
                selectedCorridor.properties?.id ||
                selectedCorridor.id ||
                "corridor"
              }-${Number(selectedScore || 0).toFixed(3)}`}
              data={selectedCorridor}
              style={{
                color: "#00f2fe",
                weight: 8,
                opacity: 1.0,
              }}
            >
              <Tooltip
                permanent
                direction="top"
                className="selected-corridor-map-callout"
              >
                <span>
                  <strong>{selectedName}</strong>
                  {selectedScore != null
                    ? ` (${Number(selectedScore).toFixed(2)} Score)`
                    : ""}
                </span>
              </Tooltip>
            </GeoJSON>
          </>
        )}

        {/* 10. CPCB AQI Stations Layer */}
        {activeLayers.aqi &&
          aqiStations &&
          Array.isArray(aqiStations.features) &&
          aqiStations.features.map((station, idx) => {
            const coords = station.geometry?.coordinates;
            if (!Array.isArray(coords) || coords.length < 2) return null;
            const pm25 = station.properties?.pm25 ?? station.properties?.aqi;
            const stName =
              station.properties?.name ||
              station.properties?.station ||
              `AQI Station #${idx + 1}`;
            return (
              <CircleMarker
                key={`aqi-${idx}-${stName}`}
                center={[coords[1], coords[0]]}
                radius={8}
                fillColor="#a855f7"
                color="#ffffff"
                weight={2}
                fillOpacity={0.9}
              >
                <Tooltip direction="top" className="corridor-tooltip">
                  <span>
                    💨 <strong>{stName}</strong>
                    {pm25 != null ? ` • PM2.5: ${Math.round(Number(pm25))} µg/m³` : ""}
                  </span>
                </Tooltip>
                <Popup>
                  <strong>{stName}</strong>
                  {pm25 != null ? (
                    <div>PM2.5: {Math.round(Number(pm25))} µg/m³</div>
                  ) : null}
                </Popup>
              </CircleMarker>
            );
          })}

        <ClickHandler onPointQuery={handlePointQuery} />

        <MapController
          selectedCorridor={selectedCorridor}
          fitTrigger={fitTrigger}
          resetTrigger={resetTrigger}
        />
      </MapContainer>

      {/* Bottom-Center Interactive Layer & Provenance Bar */}
      <div
        className="map-bottom-provenance-bar"
        data-testid="map-bottom-provenance-bar"
      >
        <div className="provenance-chips-group">
          <span className="prov-chip">
            🛰️ <strong>NDVI:</strong> Sentinel-2 (10m)
          </span>
          <span className="prov-chip">
            🌡️ <strong>LST:</strong> MODIS (1km screening)
          </span>
          <span className="prov-chip">
            💨 <strong>AQI:</strong> CPCB IDW
          </span>
        </div>

        <div className="opacity-slider-control">
          <label htmlFor="raster-opacity-range">
            Overlay Opacity: <strong>{Math.round(rasterOpacity * 100)}%</strong>
          </label>
          <input
            id="raster-opacity-range"
            data-testid="raster-opacity-slider"
            type="range"
            min="0.15"
            max="1.0"
            step="0.05"
            value={rasterOpacity}
            onChange={(e) => setRasterOpacity(parseFloat(e.target.value))}
          />
        </div>

        <div
          className="temporal-honesty-tag"
          title="Multi-year historical raster time-series are not loaded; displaying validated composite baseline."
        >
          ⏱️ Composite Baseline (Multi-date rasters not loaded)
        </div>
      </div>
    </div>
  );
}
