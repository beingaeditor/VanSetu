/**
 * Map Component — Centre Spatial Canvas of the Van Setu Urban Climate Studio.
 *
 * Includes:
 * - Floating top-left OVERLAYS card (Heat, NDVI/Green Cover, Priority Index (GDI), Corridors, AQI Stations, plus expandable OSM overlays & legend)
 * - Top-right LocationSearch + "Fit to Corridor" / "Reset View" spatial navigation controls
 * - Glowing cyan (#00f2fe) selected corridor geometry highlight + permanent callout badge
 * - Bottom-center Interactive Layer Opacity & Provenance Controller bar
 * - Point inspection popup on click
 */

import { useEffect, useState, useCallback, useRef } from "react";
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

function SearchController({ location }) {
  const map = useMap();

  useEffect(() => {
    if (location) {
      map.flyTo([location.lat, location.lon], 13, { duration: 1.2 });
    }
  }, [location, map]);

  return null;
}

function ClickHandler({ onPointQuery }) {
  useMapEvents({
    click: (e) => {
      onPointQuery(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function MapController({ selectedCorridor, fitTrigger, resetTrigger }) {
  const map = useMap();
  const lastCorridorIdRef = useRef(null);

  useEffect(() => {
    const cid =
      selectedCorridor?.properties?.id || selectedCorridor?.id || null;
    if (selectedCorridor && selectedCorridor.geometry && cid !== lastCorridorIdRef.current) {
      lastCorridorIdRef.current = cid;
      try {
        const bounds = L.geoJSON(selectedCorridor).getBounds();
        if (bounds.isValid()) {
          map.fitBounds(bounds, {
            padding: [70, 70],
            maxZoom: 14,
            animate: true,
          });
        }
      } catch (err) {
        console.error("Failed to fit corridor bounds:", err);
      }
    }
  }, [selectedCorridor, map]);

  useEffect(() => {
    if (fitTrigger > 0 && selectedCorridor && selectedCorridor.geometry) {
      try {
        const bounds = L.geoJSON(selectedCorridor).getBounds();
        if (bounds.isValid()) {
          map.fitBounds(bounds, {
            padding: [60, 60],
            maxZoom: 15,
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
}) {
  const [corridors, setCorridors] = useState(null);
  const [roads, setRoads] = useState(null);
  const [aqiStations, setAqiStations] = useState(null);
  const [pointData, setPointData] = useState(null);

  const [internalSelectedCorridor, setInternalSelectedCorridor] =
    useState(null);
  const [showMoreOverlays, setShowMoreOverlays] = useState(false);
  const [rasterOpacity, setRasterOpacity] = useState(0.72);
  const [fitTrigger, setFitTrigger] = useState(0);
  const [resetTrigger, setResetTrigger] = useState(0);

  const selectedCorridor =
    externalSelectedCorridor !== undefined
      ? externalSelectedCorridor
      : internalSelectedCorridor;

  const updateSelectedCorridor = useCallback(
    (feature) => {
      if (onSelectCorridor) {
        onSelectCorridor(feature);
      } else {
        setInternalSelectedCorridor(feature);
      }
    },
    [onSelectCorridor]
  );

  const [searchedLocation, setSearchedLocation] = useState(null);
  const [selectedDistrict, setSelectedDistrict] = useState(null);
  const [parkData, setParkData] = useState(null);
  const [residentialData, setResidentialData] = useState(null);

  useEffect(() => {
    if (activeLayers.corridors && !corridors) {
      roadsApi
        .corridors(85, true)
        .then((res) => setCorridors(res.data))
        .catch((err) => console.error(err));
    }
  }, [activeLayers.corridors, corridors]);

  useEffect(() => {
    if (activeLayers.roads && !roads) {
      roadsApi
        .simple()
        .then((res) => setRoads(res.data))
        .catch((err) => console.error(err));
    }
  }, [activeLayers.roads, roads]);

  useEffect(() => {
    if (activeLayers.aqi && !aqiStations) {
      aqiApi
        .stations()
        .then((res) => setAqiStations(res.data))
        .catch((err) => console.error(err));
    }
  }, [activeLayers.aqi, aqiStations]);

  const handlePointQuery = useCallback(async (lat, lng) => {
    try {
      const res = await statsApi.point(lat, lng);
      setPointData(res.data);
    } catch (err) {
      console.error(err);
    }
  }, []);

  useEffect(() => {
    if (activeLayers.osmParks && !parkData) {
      const query = `[out:json][timeout:30][bbox:28.40,76.73,28.87,77.35];
        (way["leisure"="park"];way["leisure"="garden"];way["landuse"="forest"];
         way["landuse"="meadow"];way["leisure"="nature_reserve"];relation["leisure"="park"];);
        out geom;`;
      fetch(
        `https://overpass-api.de/api/interpreter?data=${encodeURIComponent(
          query
        )}`
      )
        .then((r) => r.json())
        .then((data) => {
          const features = data.elements
            .filter((el) => el.geometry && el.geometry.length > 2)
            .map((el) => ({
              type: "Feature",
              properties: {
                name: el.tags?.name || "",
                type: el.tags?.leisure || el.tags?.landuse || "park",
              },
              geometry: {
                type: "Polygon",
                coordinates: [el.geometry.map((p) => [p.lon, p.lat])],
              },
            }));
          setParkData({ type: "FeatureCollection", features });
        })
        .catch((err) => console.error("Parks fetch failed:", err));
    }
  }, [activeLayers.osmParks, parkData]);

  useEffect(() => {
    if (activeLayers.osmResidential && !residentialData) {
      const query = `[out:json][timeout:30][bbox:28.40,76.73,28.87,77.35];
        (way["landuse"="residential"];);
        out geom;`;
      fetch(
        `https://overpass-api.de/api/interpreter?data=${encodeURIComponent(
          query
        )}`
      )
        .then((r) => r.json())
        .then((data) => {
          const features = data.elements
            .filter((el) => el.geometry && el.geometry.length > 2)
            .map((el) => ({
              type: "Feature",
              properties: { name: el.tags?.name || "" },
              geometry: {
                type: "Polygon",
                coordinates: [el.geometry.map((p) => [p.lon, p.lat])],
              },
            }));
          setResidentialData({ type: "FeatureCollection", features });
        })
        .catch((err) => console.error("Residential fetch failed:", err));
    }
  }, [activeLayers.osmResidential, residentialData]);

  const handleLocationFound = (location) => {
    const district = districts.features.find(
      (d) =>
        d.properties.district.toLowerCase() === location.name.toLowerCase()
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

  const corridorStyle = (feature) => {
    const score =
      feature.properties?.priority_score ?? feature.properties?.gdi_mean ?? 0;
    return {
      color: priorityColor(score, corridors?.metadata),
      weight: 5,
      opacity: 0.9,
    };
  };

  const filteredCorridors =
    selectedDistrict && corridors
      ? {
          ...corridors,
          features: corridors.features.filter((f) => {
            const coord = f.geometry.coordinates[0][0];
            const latlng = L.latLng(coord[1], coord[0]);
            const bounds = L.geoJSON(selectedDistrict).getBounds();
            return bounds.contains(latlng);
          }),
        }
      : corridors;

  const selectedName =
    selectedCorridor?.properties?.name || selectedCorridor?.name || "Corridor";
  const selectedScore =
    selectedCorridor?.properties?.what_if_score ??
    selectedCorridor?.properties?.priority_score ??
    selectedCorridor?.score ??
    null;

  return (
    <div className="map-container" data-testid="interactive-map-canvas">
      {/* Top-Left Floating OVERLAYS Control (Matching Reference Screenshot) */}
      <div className="floating-overlays-card" data-testid="floating-overlays-card">
        <div className="overlays-card-header">
          <span className="overlays-title">OVERLAYS</span>
          <button
            type="button"
            className="overlays-more-btn"
            onClick={() => setShowMoreOverlays((prev) => !prev)}
          >
            {showMoreOverlays ? "Less ▴" : "More ▾"}
          </button>
        </div>

        <div className="overlays-toggle-list">
          <label className="overlay-check-row">
            <input
              type="checkbox"
              checked={Boolean(activeLayers.lst)}
              onChange={() => toggleLayer("lst")}
            />
            <span className="overlay-dot" style={{ background: "#ef4444" }} />
            <span className="overlay-name">Heat (MODIS LST)</span>
          </label>

          <label className="overlay-check-row">
            <input
              type="checkbox"
              checked={Boolean(activeLayers.ndvi)}
              onChange={() => toggleLayer("ndvi")}
            />
            <span className="overlay-dot" style={{ background: "#10b981" }} />
            <span className="overlay-name">NDVI / Green Cover</span>
          </label>

          <label className="overlay-check-row">
            <input
              type="checkbox"
              checked={Boolean(activeLayers.gdi)}
              onChange={() => toggleLayer("gdi")}
            />
            <span className="overlay-dot" style={{ background: "#f59e0b" }} />
            <span className="overlay-name">Priority Index (GDI)</span>
          </label>

          <label className="overlay-check-row">
            <input
              type="checkbox"
              checked={Boolean(activeLayers.corridors)}
              onChange={() => toggleLayer("corridors")}
            />
            <span className="overlay-dot" style={{ background: "#00f2fe" }} />
            <span className="overlay-name">Corridors</span>
          </label>

          <label className="overlay-check-row">
            <input
              type="checkbox"
              checked={Boolean(activeLayers.aqi)}
              onChange={() => toggleLayer("aqi")}
            />
            <span className="overlay-dot" style={{ background: "#a855f7" }} />
            <span className="overlay-name">AQI Stations</span>
          </label>

          {showMoreOverlays && (
            <div className="overlays-extra-group">
              <label className="overlay-check-row">
                <input
                  type="checkbox"
                  checked={Boolean(activeLayers.roads)}
                  onChange={() => toggleLayer("roads")}
                />
                <span className="overlay-dot" style={{ background: "#94a3b8" }} />
                <span className="overlay-name">Walkable Road Network</span>
              </label>
              <label className="overlay-check-row">
                <input
                  type="checkbox"
                  checked={Boolean(activeLayers.osmParks)}
                  onChange={() => toggleLayer("osmParks")}
                />
                <span className="overlay-dot" style={{ background: "#22c55e" }} />
                <span className="overlay-name">OSM Parks &amp; Forests</span>
              </label>
              <label className="overlay-check-row">
                <input
                  type="checkbox"
                  checked={Boolean(activeLayers.osmResidential)}
                  onChange={() => toggleLayer("osmResidential")}
                />
                <span className="overlay-dot" style={{ background: "#d4a76a" }} />
                <span className="overlay-name">OSM Residential Zones</span>
              </label>
            </div>
          )}
        </div>

        {/* Mini Priority Gradient Legend */}
        <div className="overlays-mini-legend">
          <div className="mini-legend-labels">
            <span>Low Stress</span>
            <span>High Priority</span>
          </div>
          <div className="mini-legend-bar" />
        </div>
      </div>

      {/* Top-Right Search & Map Action Controls */}
      <div className="map-top-right-controls">
        <LocationSearch onLocationFound={handleLocationFound} />
        <div className="map-quick-nav-btns">
          {selectedCorridor && (
            <button
              type="button"
              className="map-action-pill"
              onClick={() => setFitTrigger((c) => c + 1)}
              title="Zoom to selected corridor"
            >
              🎯 Fit Corridor
            </button>
          )}
          <button
            type="button"
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
        <div className="district-indicator">
          <span>📍 {selectedDistrict.properties.district}</span>
          <button
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
            {pointData.coordinates?.lat?.toFixed(4)}°N,{" "}
            {pointData.coordinates?.lng?.toFixed(4)}°E
          </div>
          <div className="point-values">
            <div className="value-row">
              <span className="label">NDVI (10m)</span>
              <span className="value">
                {pointData.values?.ndvi != null
                  ? pointData.values.ndvi.toFixed(3)
                  : "NoData"}
              </span>
              <span className="interpretation">Sentinel-2</span>
            </div>
            <div className="value-row">
              <span className="label">LST (1km)</span>
              <span className="value">
                {pointData.values?.lst != null
                  ? `${pointData.values.lst.toFixed(1)}°C`
                  : "NoData"}
              </span>
              <span className="interpretation">MODIS</span>
            </div>
            <div className="value-row">
              <span className="label">GDI Index</span>
              <span className="value priority">
                {pointData.values?.gdi != null
                  ? pointData.values.gdi.toFixed(3)
                  : "NoData"}
              </span>
              <span className="interpretation">Composite</span>
            </div>
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

        <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />

        {activeLayers.ndvi && (
          <TileLayer url={getTileUrl("ndvi")} opacity={rasterOpacity} />
        )}

        {activeLayers.lst && (
          <TileLayer url={getTileUrl("lst")} opacity={rasterOpacity} />
        )}

        {activeLayers.gdi && (
          <TileLayer url={getTileUrl("gdi")} opacity={rasterOpacity} />
        )}

        {activeLayers.osmRoads && (
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png"
            opacity={0.5}
            className="osm-roads-overlay"
          />
        )}

        {activeLayers.osmParks && parkData && (
          <GeoJSON
            key="parks-overlay"
            data={parkData}
            style={{
              color: "#2d8b2d",
              weight: 1,
              fillColor: "#34a853",
              fillOpacity: 0.35,
              opacity: 0.6,
            }}
            onEachFeature={(feature, layer) => {
              if (feature.properties.name) {
                layer.bindTooltip(feature.properties.name, {
                  sticky: true,
                  className: "corridor-tooltip",
                });
              }
            }}
          />
        )}

        {activeLayers.osmResidential && residentialData && (
          <GeoJSON
            key="residential-overlay"
            data={residentialData}
            style={{
              color: "#c4a484",
              weight: 1,
              fillColor: "#d4a76a",
              fillOpacity: 0.2,
              opacity: 0.4,
            }}
          />
        )}

        {selectedDistrict && (
          <GeoJSON
            data={selectedDistrict}
            style={{
              color: "#00ffff",
              weight: 4,
              fillOpacity: 0.05,
            }}
          />
        )}

        {activeLayers.roads && roads && <GeoJSON data={roads} />}

        {activeLayers.corridors && filteredCorridors && (
          <GeoJSON
            data={filteredCorridors}
            style={corridorStyle}
            onEachFeature={(feature, layer) => {
              const name = feature.properties?.name || "Corridor";
              const score =
                feature.properties?.priority_score ??
                feature.properties?.gdi_mean;
              const tier = feature.properties?.severity_tier;
              const ctype = feature.properties?.corridor_type?.replace(
                /_/g,
                " "
              );
              layer.bindTooltip(
                `<strong>${name}</strong>${
                  score != null ? `<br/>Priority: ${score.toFixed(3)}` : ""
                }${tier ? `<br/>Severity: ${tier}` : ""}${
                  ctype ? `<br/>Type: ${ctype}` : ""
                }`,
                { sticky: true, className: "corridor-tooltip" }
              );
              layer.on("click", () => {
                updateSelectedCorridor(feature);
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
                opacity: 0.38,
              }}
            />
            <GeoJSON
              key={`selected-${
                selectedCorridor.properties?.id ||
                selectedCorridor.id ||
                "corridor"
              }`}
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

        {activeLayers.aqi &&
          aqiStations &&
          aqiStations.features &&
          aqiStations.features.map((station, idx) => {
            const coords = station.geometry.coordinates;
            return (
              <CircleMarker
                key={idx}
                center={[coords[1], coords[0]]}
                radius={8}
                fillColor="#a855f7"
                color="#fff"
                weight={2}
                fillOpacity={0.85}
              >
                <Popup>{station.properties.name}</Popup>
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
            type="range"
            min="0.15"
            max="1.0"
            step="0.05"
            value={rasterOpacity}
            onChange={(e) => setRasterOpacity(parseFloat(e.target.value))}
          />
        </div>

        <div className="temporal-honesty-tag" title="Multi-year historical raster time-series are not loaded; displaying validated composite baseline.">
          ⏱️ Composite Baseline (Multi-date rasters not loaded)
        </div>
      </div>
    </div>
  );
}
