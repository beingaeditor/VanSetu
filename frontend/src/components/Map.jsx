/**
 * Map Component — Main Leaflet map with layer controls
 * Includes:
 * - District search
 * - District boundary highlight
 * - Corridor filtering by district
 * - Corridor intervention panel
 */

import { useEffect, useState, useCallback, useRef, memo } from "react";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  useMap,
  useMapEvents,
  CircleMarker,
  Popup
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import { getTileUrl, roadsApi, statsApi, aqiApi } from "../api";
import "./Map.css";

import InterventionPanel from "./InterventionPanel";
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
    [26, 152, 80],   // green
    [145, 207, 96],  // light green
    [254, 224, 139], // yellow
    [252, 141, 89],  // orange
    [215, 48, 39],   // red
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

function ClickHandler({ onPointQuery, disabled }) {
  useMapEvents({
    click: (e) => {
      if (!disabled) {
        onPointQuery(e.latlng.lat, e.latlng.lng);
      }
    }
  });
  return null;
}

function MapController({ selectedCorridor, previousView, onViewSaved }) {
  const map = useMap();

  useEffect(() => {
    if (selectedCorridor && selectedCorridor.geometry) {
      if (!previousView.current) {
        previousView.current = {
          center: map.getCenter(),
          zoom: map.getZoom()
        };
        onViewSaved();
      }

      const coords = selectedCorridor.geometry.coordinates;
      const latLngs = coords.map((c) => [c[1], c[0]]);
      const bounds = L.latLngBounds(latLngs);

      map.fitBounds(bounds, {
        padding: [50, 420],
        maxZoom: 15,
        animate: true
      });
    }
  }, [selectedCorridor, map, previousView, onViewSaved]);

  return null;
}

function MapViewRestorer({ shouldRestore, previousView, onRestored }) {
  const map = useMap();

  useEffect(() => {
    if (shouldRestore && previousView.current) {
      map.setView(previousView.current.center, previousView.current.zoom, {
        animate: true
      });
      previousView.current = null;
      onRestored();
    }
  }, [shouldRestore, map, previousView, onRestored]);

  return null;
}

export default function Map({ activeLayers }) {
  const [corridors, setCorridors] = useState(null);
  const [roads, setRoads] = useState(null);
  const [aqiStations, setAqiStations] = useState(null);

  const [pointData, setPointData] = useState(null);

  const [selectedCorridor, setSelectedCorridor] = useState(null);
  const [isPanelOpen, setIsPanelOpen] = useState(false);

  const [shouldRestoreView, setShouldRestoreView] = useState(false);
  const previousViewRef = useRef(null);

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

  // Fetch parks from Overpass API
  useEffect(() => {
    if (activeLayers.osmParks && !parkData) {
      const query = `[out:json][timeout:30][bbox:28.40,76.73,28.87,77.35];
        (way["leisure"="park"];way["leisure"="garden"];way["landuse"="forest"];
         way["landuse"="meadow"];way["leisure"="nature_reserve"];relation["leisure"="park"];);
        out geom;`;
      fetch(`https://overpass-api.de/api/interpreter?data=${encodeURIComponent(query)}`)
        .then(r => r.json())
        .then(data => {
          const features = data.elements
            .filter(el => el.geometry && el.geometry.length > 2)
            .map(el => ({
              type: 'Feature',
              properties: { name: el.tags?.name || '', type: el.tags?.leisure || el.tags?.landuse || 'park' },
              geometry: {
                type: 'Polygon',
                coordinates: [el.geometry.map(p => [p.lon, p.lat])]
              }
            }));
          setParkData({ type: 'FeatureCollection', features });
        })
        .catch(err => console.error('Parks fetch failed:', err));
    }
  }, [activeLayers.osmParks, parkData]);

  // Fetch residential areas from Overpass API
  useEffect(() => {
    if (activeLayers.osmResidential && !residentialData) {
      const query = `[out:json][timeout:30][bbox:28.40,76.73,28.87,77.35];
        (way["landuse"="residential"];);
        out geom;`;
      fetch(`https://overpass-api.de/api/interpreter?data=${encodeURIComponent(query)}`)
        .then(r => r.json())
        .then(data => {
          const features = data.elements
            .filter(el => el.geometry && el.geometry.length > 2)
            .map(el => ({
              type: 'Feature',
              properties: { name: el.tags?.name || '' },
              geometry: {
                type: 'Polygon',
                coordinates: [el.geometry.map(p => [p.lon, p.lat])]
              }
            }));
          setResidentialData({ type: 'FeatureCollection', features });
        })
        .catch(err => console.error('Residential fetch failed:', err));
    }
  }, [activeLayers.osmResidential, residentialData]);

  const handleLocationFound = (location) => {
    const district = districts.features.find(
      (d) =>
        d.properties.district.toLowerCase() ===
        location.name.toLowerCase()
    );

    if (district) {
      setSelectedDistrict(district);
    }

    setSearchedLocation(location);
  };

  const corridorStyle = (feature) => {
    const score = feature.properties?.priority_score ?? feature.properties?.gdi_mean ?? 0;
    return {
      color: priorityColor(score, corridors?.metadata),
      weight: 5,
      opacity: 0.9
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
          })
        }
      : corridors;

  return (
    <div className="map-container">
      <LocationSearch onLocationFound={handleLocationFound} />

      {selectedDistrict && (
        <div className="district-indicator">
          <span>📍 {selectedDistrict.properties.district}</span>
          <button
            className="district-clear-btn"
            onClick={() => setSelectedDistrict(null)}
            aria-label="Clear district filter"
          >✕</button>
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
          <TileLayer url={getTileUrl("ndvi")} opacity={0.7} />
        )}

        {activeLayers.lst && (
          <TileLayer url={getTileUrl("lst")} opacity={0.7} />
        )}

        {activeLayers.gdi && (
          <TileLayer url={getTileUrl("gdi")} opacity={0.7} />
        )}

        {/* OSM Overlay Layers */}
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
              color: '#2d8b2d',
              weight: 1,
              fillColor: '#34a853',
              fillOpacity: 0.35,
              opacity: 0.6
            }}
            onEachFeature={(feature, layer) => {
              if (feature.properties.name) {
                layer.bindTooltip(feature.properties.name, { sticky: true, className: 'corridor-tooltip' });
              }
            }}
          />
        )}
        {activeLayers.osmResidential && residentialData && (
          <GeoJSON
            key="residential-overlay"
            data={residentialData}
            style={{
              color: '#c4a484',
              weight: 1,
              fillColor: '#d4a76a',
              fillOpacity: 0.2,
              opacity: 0.4
            }}
          />
        )}

        {selectedDistrict && (
          <GeoJSON
            data={selectedDistrict}
            style={{
              color: "#00ffff",
              weight: 4,
              fillOpacity: 0.05
            }}
          />
        )}

        {activeLayers.roads && roads && <GeoJSON data={roads} />}

        {activeLayers.corridors && filteredCorridors && (
          <GeoJSON
            data={filteredCorridors}
            style={corridorStyle}
            onEachFeature={(feature, layer) => {
              const name = feature.properties?.name || 'Corridor';
              const score = feature.properties?.priority_score ?? feature.properties?.gdi_mean;
              const tier = feature.properties?.severity_tier;
              const ctype = feature.properties?.corridor_type?.replace(/_/g, ' ');
              layer.bindTooltip(
                `<strong>${name}</strong>${score != null ? `<br/>Priority: ${score.toFixed(3)}` : ''}${tier ? `<br/>Severity: ${tier}` : ''}${ctype ? `<br/>Type: ${ctype}` : ''}`,
                { sticky: true, className: 'corridor-tooltip' }
              );
              layer.on("click", () => {
                setSelectedCorridor(feature);
                setIsPanelOpen(true);
              });
            }}
          />
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
                fillColor="#ff6b6b"
                color="#fff"
                weight={2}
                fillOpacity={0.8}
              >
                <Popup>{station.properties.name}</Popup>
              </CircleMarker>
            );
          })}

        <ClickHandler
          onPointQuery={handlePointQuery}
          disabled={isPanelOpen}
        />

        <MapController
          selectedCorridor={selectedCorridor}
          previousView={previousViewRef}
          onViewSaved={() => {}}
        />

        <MapViewRestorer
          shouldRestore={shouldRestoreView}
          previousView={previousViewRef}
          onRestored={() => setShouldRestoreView(false)}
        />
      </MapContainer>

      {isPanelOpen && selectedCorridor && (
        <InterventionPanel
          corridor={selectedCorridor}
          onClose={() => {
            setIsPanelOpen(false);
            setSelectedCorridor(null);
            setShouldRestoreView(true);
          }}
        />
      )}
    </div>
  );
}