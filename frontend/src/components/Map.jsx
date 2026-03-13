/**
 * Map Component — Main Leaflet map with layer controls
 * 
 * Updated to support AQI visualization, Multi-Exposure Priority scoring,
 * and Corridor Intervention panel with animated focus.
 */
import { useEffect, useState, useCallback, useRef, memo } from 'react';
import { MapContainer, TileLayer, LayersControl, GeoJSON, useMap, useMapEvents, CircleMarker, Popup, Tooltip } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { getTileUrl, roadsApi, statsApi, aqiApi } from '../api';
import './Map.css';
import InterventionPanel from './InterventionPanel';

// Delhi NCT center and bounds
const DELHI_CENTER = [28.6139, 77.209];
const DELHI_BOUNDS = [
  [28.40, 76.73],  // Southwest
  [28.87, 77.35]   // Northeast
];

/**
 * Custom hook for click-to-query functionality
 */
function ClickHandler({ onPointQuery, disabled }) {
  useMapEvents({
    click: (e) => {
      if (onPointQuery && !disabled) {
        onPointQuery(e.latlng.lat, e.latlng.lng);
      }
    },
  });
  return null;
}

/**
 * Map controller for programmatic map interactions (zoom, pan)
 */
function MapController({ selectedCorridor, previousView, onViewSaved }) {
  const map = useMap();
  
  useEffect(() => {
    if (selectedCorridor && selectedCorridor.geometry) {
      // Save current view before zooming
      if (!previousView.current) {
        previousView.current = {
          center: map.getCenter(),
          zoom: map.getZoom()
        };
        onViewSaved();
      }
      
      // Create bounds from the corridor geometry
      const coords = selectedCorridor.geometry.coordinates;
      const latLngs = coords.map(coord => [coord[1], coord[0]]);
      const bounds = L.latLngBounds(latLngs);
      
      // Animated zoom to corridor with padding for the panel
      map.fitBounds(bounds, {
        padding: [50, 420], // Extra padding on right for panel
        maxZoom: 15,
        animate: true,
        duration: 0.6
      });
    }
  }, [selectedCorridor, map, previousView, onViewSaved]);
  
  return null;
}

/**
 * Restore map view when panel is closed
 */
function MapViewRestorer({ shouldRestore, previousView, onRestored }) {
  const map = useMap();
  
  useEffect(() => {
    if (shouldRestore && previousView.current) {
      map.setView(
        previousView.current.center,
        previousView.current.zoom,
        { animate: true, duration: 0.5 }
      );
      previousView.current = null;
      onRestored();
    }
  }, [shouldRestore, map, previousView, onRestored]);
  
  return null;
}

/**
 * Legend component for the active layer
 * Updated to reflect Multi-Exposure Priority scoring
 */
const Legend = memo(function Legend({ activeLayer }) {
  const legends = {
    ndvi: {
      title: 'NDVI',
      colors: ['#f7fcf5', '#c7e9c0', '#74c476', '#238b45', '#00441b'],
      labels: ['Low', '', '', '', 'High'],
    },
    lst: {
      title: 'Temperature',
      colors: ['#4575b4', '#91bfdb', '#fee090', '#fc8d59', '#d73027'],
      labels: ['Cool', '', '', '', 'Hot'],
    },
    gdi: {
      title: 'Multi-Exposure Priority',
      subtitle: 'Heat + Green + Air Quality',
      colors: ['#1a9850', '#91cf60', '#fee08b', '#fc8d59', '#d73027'],
      labels: ['Low', '', '', '', 'High'],
    },
  };

  const legend = legends[activeLayer];
  if (!legend) return null;

  return (
    <div className="map-legend" role="figure" aria-label={`${legend.title} legend`}>
      <h4>{legend.title}</h4>
      {legend.subtitle ? <span className="legend-subtitle">{legend.subtitle}</span> : null}
      <div className="legend-gradient">
        {legend.colors.map((color, i) => (
          <div
            key={i}
            className="legend-color"
            style={{ backgroundColor: color }}
          />
        ))}
      </div>
      <div className="legend-labels">
        <span>{legend.labels[0]}</span>
        <span>{legend.labels[4]}</span>
      </div>
    </div>
  );
});

/**
 * Point info popup — shows all layer values including AQI
 */
const PointInfo = memo(function PointInfo({ data, onClose }) {
  if (!data) return null;

  const getPriorityColor = (value) => {
    if (value < 0.3) return 'var(--primary-green)';
    if (value < 0.5) return '#91cf60';
    if (value < 0.7) return 'var(--warning-yellow)';
    return 'var(--alert-red)';
  };

  const getAqiColor = (aqi) => {
    if (aqi <= 50) return 'var(--primary-green)';
    if (aqi <= 100) return '#91cf60';
    if (aqi <= 200) return 'var(--warning-yellow)';
    if (aqi <= 300) return '#fc8d59';
    return 'var(--alert-red)';
  };

  const getAqiLabel = (aqi) => {
    if (aqi <= 50) return 'Good';
    if (aqi <= 100) return 'Satisfactory';
    if (aqi <= 200) return 'Moderate';
    if (aqi <= 300) return 'Poor';
    return 'Very Poor';
  };

  // Use priority_score if available, otherwise fall back to gdi
  const priorityValue = data.values.priority_score ?? data.values.gdi;

  return (
    <div className="point-info" role="dialog" aria-label="Point analysis">
      <button className="close-btn" onClick={onClose} aria-label="Close point info">×</button>
      <h4>📍 Point Analysis</h4>
      <div className="point-coords">
        {data.location.lat.toFixed(4)}°N, {data.location.lng.toFixed(4)}°E
      </div>
      <div className="point-values">
        {data.values.ndvi !== null ? (
          <div className="value-row">
            <span className="label">🌿 NDVI</span>
            <span className="value">{data.values.ndvi.toFixed(3)}</span>
            <span className="interpretation">{data.interpretation.vegetation}</span>
          </div>
        ) : null}
        {data.values.lst !== null ? (
          <div className="value-row">
            <span className="label">🌡️ LST</span>
            <span className="value">{data.values.lst.toFixed(1)}°C</span>
            <span className="interpretation">{data.interpretation.temperature}</span>
          </div>
        ) : null}
        {data.values.aqi_raw !== null && data.values.aqi_raw !== undefined ? (
          <div className="value-row">
            <span className="label">💨 PM2.5</span>
            <span 
              className="value"
              style={{ color: getAqiColor(data.values.aqi_raw) }}
            >
              {Math.round(data.values.aqi_raw)}
            </span>
            <span className="interpretation">
              {getAqiLabel(data.values.aqi_raw)}
              {data.aqi_station ? (
                <span className="station-info"> ({data.aqi_station.name})</span>
              ) : null}
            </span>
          </div>
        ) : null}
        {priorityValue !== null && priorityValue !== undefined ? (
          <div className="value-row highlight">
            <span className="label">📊 Priority</span>
            <span 
              className="value priority"
              style={{ color: getPriorityColor(priorityValue) }}
            >
              {priorityValue.toFixed(3)}
            </span>
            <span className="interpretation">{data.interpretation.priority}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
});

/**
 * Main Map component
 */
export default function Map({ activeLayers, onStatsUpdate }) {
  const [corridors, setCorridors] = useState(null);
  const [roads, setRoads] = useState(null);
  const [aqiStations, setAqiStations] = useState(null);
  const [pointData, setPointData] = useState(null);
  const [loading, setLoading] = useState({});
  
  // State for corridor hover highlighting
  const [hoveredCorridor, setHoveredCorridor] = useState(null);
  
  // State for corridor selection and intervention panel
  const [selectedCorridor, setSelectedCorridor] = useState(null);
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [shouldRestoreView, setShouldRestoreView] = useState(false);
  const previousViewRef = useRef(null);

  // Determine which raster layer is active (only one at a time for clarity)
  const activeRaster = activeLayers.gdi ? 'gdi' : activeLayers.lst ? 'lst' : activeLayers.ndvi ? 'ndvi' : null;

  // Load corridors when toggled
  useEffect(() => {
    if (activeLayers.corridors && !corridors) {
      setLoading(prev => ({ ...prev, corridors: true }));
      roadsApi.corridors(85, true)  // Include AQI in scoring
        .then(res => setCorridors(res.data))
        .catch(err => console.error('Failed to load corridors:', err))
        .finally(() => setLoading(prev => ({ ...prev, corridors: false })));
    }
  }, [activeLayers.corridors, corridors]);

  // Load roads when toggled
  useEffect(() => {
    if (activeLayers.roads && !roads) {
      setLoading(prev => ({ ...prev, roads: true }));
      roadsApi.simple()
        .then(res => setRoads(res.data))
        .catch(err => console.error('Failed to load roads:', err))
        .finally(() => setLoading(prev => ({ ...prev, roads: false })));
    }
  }, [activeLayers.roads, roads]);

  // Load AQI stations when toggled
  useEffect(() => {
    if (activeLayers.aqi && !aqiStations) {
      setLoading(prev => ({ ...prev, aqi: true }));
      aqiApi.stations()
        .then(res => setAqiStations(res.data))
        .catch(err => console.error('Failed to load AQI stations:', err))
        .finally(() => setLoading(prev => ({ ...prev, aqi: false })));
    }
  }, [activeLayers.aqi, aqiStations]);

  // Handle point click query
  const handlePointQuery = useCallback(async (lat, lng) => {
    try {
      const res = await statsApi.point(lat, lng);
      setPointData(res.data);
    } catch (err) {
      console.error('Failed to query point:', err);
    }
  }, []);

  // Style for corridors (high priority = red)
  // Uses relative color scaling based on actual data range for visual contrast
  const corridorStyle = useCallback((feature) => {
    const priority = feature.properties?.priority_score ?? feature.properties?.gdi_mean ?? 0.5;
    const featureId = feature.properties?.name || feature.id || JSON.stringify(feature.geometry?.coordinates?.[0]);
    const isHovered = hoveredCorridor === featureId;
    const isSelected = selectedCorridor?.properties?.name === feature.properties?.name;
    const hasSelection = selectedCorridor !== null;
    
    // Normalize priority within the corridor dataset range for maximum color spread
    // Use metadata range if available, otherwise sensible defaults
    const pMin = corridors?.metadata?.priority_min ?? 0.3;
    const pMax = corridors?.metadata?.priority_max ?? 0.7;
    const range = pMax - pMin || 0.1;
    const t = Math.max(0, Math.min(1, (priority - pMin) / range)); // 0 = lowest, 1 = highest
    
    // 5-stop color scale: green → yellow-green → yellow → orange → red
    const colorStops = [
      [26, 152, 80],    // #1a9850 - green (low priority)
      [145, 207, 96],   // #91cf60 - yellow-green
      [254, 224, 139],  // #fee08b - yellow
      [252, 141, 89],   // #fc8d59 - orange
      [215, 48, 39],    // #d73027 - red (high priority)
    ];
    
    // Interpolate between color stops
    const segIdx = Math.min(t * (colorStops.length - 1), colorStops.length - 1.001);
    const i = Math.floor(segIdx);
    const f = segIdx - i;
    const c0 = colorStops[i];
    const c1 = colorStops[Math.min(i + 1, colorStops.length - 1)];
    const r = Math.round(c0[0] + (c1[0] - c0[0]) * f);
    const g = Math.round(c0[1] + (c1[1] - c0[1]) * f);
    const b = Math.round(c0[2] + (c1[2] - c0[2]) * f);
    const color = `rgb(${r}, ${g}, ${b})`;
    
    // If a corridor is selected, dim others
    if (hasSelection && !isSelected) {
      return {
        color: '#666',
        weight: 2,
        opacity: 0.3,
        lineCap: 'round',
        lineJoin: 'round',
      };
    }
    
    // Selected corridor gets emphasized styling
    if (isSelected) {
      return {
        color: '#00ffff',
        weight: 8,
        opacity: 1,
        lineCap: 'round',
        lineJoin: 'round',
      };
    }
    
    return {
      color: isHovered ? '#00ffff' : color,
      weight: isHovered ? 7 : 5,
      opacity: isHovered ? 1 : 0.9,
      lineCap: 'round',
      lineJoin: 'round',
    };
  }, [hoveredCorridor, selectedCorridor, corridors]);

  // Style for roads (subtle gray)
  const roadStyle = {
    color: '#666',
    weight: 1.5,
    opacity: 0.6,
  };

  // Get AQI station color based on PM2.5 value
  const getAqiStationColor = (pm25) => {
    if (pm25 <= 50) return '#1a9850';
    if (pm25 <= 100) return '#91cf60';
    if (pm25 <= 200) return '#fee08b';
    if (pm25 <= 300) return '#fc8d59';
    return '#d73027';
  };

  return (
    <div className="map-container">
      <MapContainer
        center={DELHI_CENTER}
        zoom={11}
        minZoom={10}
        maxZoom={16}
        maxBounds={[
          [28.2, 76.5],
          [29.0, 77.6]
        ]}
      >
        {/* Base map */}
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        />

        {/* NDVI layer */}
        {activeLayers.ndvi && (
          <TileLayer
            url={getTileUrl('ndvi')}
            opacity={0.7}
            zIndex={100}
          />
        )}

        {/* LST layer */}
        {activeLayers.lst && (
          <TileLayer
            url={getTileUrl('lst')}
            opacity={0.7}
            zIndex={101}
          />
        )}

        {/* GDI layer */}
        {activeLayers.gdi && (
          <TileLayer
            url={getTileUrl('gdi')}
            opacity={0.75}
            zIndex={102}
          />
        )}

        {/* OSM Roads Overlay - translucent highway network */}
        {activeLayers.osmRoads && (
          <TileLayer
            url="https://stamen-tiles-{s}.a.ssl.fastly.net/toner-lines/{z}/{x}/{y}{r}.png"
            opacity={0.35}
            zIndex={110}
            className="osm-roads-overlay"
            attribution='&copy; <a href="http://stamen.com">Stamen</a>'
          />
        )}

        {/* OSM Parks Overlay - OpenStreetMap standard with green filter */}
        {activeLayers.osmParks && (
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            opacity={0.35}
            zIndex={111}
            className="osm-parks-overlay"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          />
        )}

        {/* OSM Residential Overlay - OpenStreetMap standard with sepia/tan filter */}
        {activeLayers.osmResidential && (
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            opacity={0.3}
            zIndex={112}
            className="osm-residential-overlay"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          />
        )}

        {/* Roads layer */}
        {activeLayers.roads && roads && (
          <GeoJSON
            key="roads"
            data={roads}
            style={roadStyle}
          />
        )}

        {/* Corridors layer - with hover highlighting and tooltips */}
        {activeLayers.corridors && corridors && (
          <GeoJSON
            key={`corridors-${hoveredCorridor || 'none'}-${selectedCorridor?.properties?.name || 'none'}`}
            data={corridors}
            style={corridorStyle}
            onEachFeature={(feature, layer) => {
              const props = feature.properties;
              if (props) {
                const priority = props.priority_score ?? props.gdi_mean ?? 0.5;
                const aqi = props.aqi_raw;
                const heat = props.heat_norm;
                const ndvi = props.ndvi_norm;
                const aqiNorm = props.aqi_norm;
                const roadName = props.name || 'Unnamed Road';
                const featureId = props.name || feature.id || JSON.stringify(feature.geometry?.coordinates?.[0]);
                
                // Use relative scaling for priority label
                const pMin = corridors?.metadata?.priority_min ?? 0.3;
                const pMax = corridors?.metadata?.priority_max ?? 0.7;
                const pRange = pMax - pMin || 0.1;
                const pNorm = Math.max(0, Math.min(1, (priority - pMin) / pRange));
                const priorityColor = pNorm > 0.7 ? '#d73027' : pNorm > 0.4 ? '#fc8d59' : '#91cf60';
                const priorityLabel = pNorm > 0.7 ? 'Critical' : pNorm > 0.4 ? 'High' : 'Moderate';
                
                // Only show tooltip if no corridor is selected
                if (!selectedCorridor) {
                  // Bind tooltip for hover display
                  layer.bindTooltip(`
                    <div class="corridor-tooltip">
                      <div class="tooltip-header">
                        <span class="tooltip-icon">🛤️</span>
                        <span class="tooltip-title">${roadName}</span>
                        <span class="tooltip-priority" style="background: ${priorityColor}">${priorityLabel}</span>
                      </div>
                      <div class="tooltip-stats">
                        <div class="tooltip-stat">
                          <span class="stat-icon">📊</span>
                          <span class="stat-value">${priority?.toFixed(2) || '—'}</span>
                          <span class="stat-label">priority</span>
                        </div>
                        ${aqi ? `
                        <div class="tooltip-stat">
                          <span class="stat-icon">💨</span>
                          <span class="stat-value">${Math.round(aqi)}</span>
                          <span class="stat-label">PM2.5</span>
                        </div>
                        ` : ''}
                      </div>
                      <div class="tooltip-bars">
                        ${heat != null ? `
                          <div class="tooltip-bar">
                            <span class="bar-icon">🌡️</span>
                            <div class="bar-track"><div class="bar-fill heat" style="width: ${heat * 100}%"></div></div>
                            <span class="bar-pct">${(heat * 100).toFixed(0)}%</span>
                          </div>
                        ` : ''}
                        ${ndvi != null ? `
                          <div class="tooltip-bar">
                            <span class="bar-icon">🌿</span>
                            <div class="bar-track"><div class="bar-fill green" style="width: ${ndvi * 100}%"></div></div>
                            <span class="bar-pct">${(ndvi * 100).toFixed(0)}%</span>
                          </div>
                        ` : ''}
                        ${aqiNorm != null ? `
                          <div class="tooltip-bar">
                            <span class="bar-icon">💨</span>
                            <div class="bar-track"><div class="bar-fill aqi" style="width: ${aqiNorm * 100}%"></div></div>
                            <span class="bar-pct">${(aqiNorm * 100).toFixed(0)}%</span>
                          </div>
                        ` : ''}
                      </div>
                      <div class="tooltip-hint">Click for intervention suggestions</div>
                    </div>
                  `, {
                    sticky: true,
                    direction: 'top',
                    offset: [0, -10],
                    className: 'corridor-tooltip-container'
                  });
                }
                
                // Click handler to select corridor and open panel
                layer.on('click', (e) => {
                  L.DomEvent.stopPropagation(e);
                  setSelectedCorridor(feature);
                  setIsPanelOpen(true);
                  setHoveredCorridor(null);
                });
                
                // Hover events for highlighting (only when no selection)
                layer.on('mouseover', () => {
                  if (!selectedCorridor) {
                    setHoveredCorridor(featureId);
                    layer.bringToFront();
                  }
                });
                
                layer.on('mouseout', () => {
                  if (!selectedCorridor) {
                    setHoveredCorridor(null);
                  }
                });
              }
            }}
          />
        )}

        {/* AQI Stations layer */}
        {activeLayers.aqi && aqiStations && aqiStations.features && (
          aqiStations.features.map((station, idx) => {
            const coords = station.geometry.coordinates;
            const props = station.properties;
            const pm25 = props.pm25 || props.aqi_raw;
            
            return (
              <CircleMarker
                key={`aqi-${idx}`}
                center={[coords[1], coords[0]]}
                radius={8}
                fillColor={getAqiStationColor(pm25)}
                color="#fff"
                weight={2}
                opacity={1}
                fillOpacity={0.8}
              >
                <Popup>
                  <div className="aqi-popup">
                    <b>💨 {props.name}</b><br/>
                    PM2.5: <span style={{color: getAqiStationColor(pm25), fontWeight: 'bold'}}>
                      {pm25 ? Math.round(pm25) : 'N/A'}
                    </span><br/>
                    {props.pm10 && <>PM10: {Math.round(props.pm10)}<br/></>}
                    Source: {props.source}
                  </div>
                </Popup>
              </CircleMarker>
            );
          })
        )}

        {/* Click handler for point queries */}
        <ClickHandler onPointQuery={handlePointQuery} disabled={isPanelOpen} />
        
        {/* Map controller for animated zoom to selected corridor */}
        <MapController 
          selectedCorridor={selectedCorridor}
          previousView={previousViewRef}
          onViewSaved={() => {}}
        />
        
        {/* Map view restorer when panel closes */}
        <MapViewRestorer 
          shouldRestore={shouldRestoreView}
          previousView={previousViewRef}
          onRestored={() => setShouldRestoreView(false)}
        />
      </MapContainer>

      {/* Legend */}
      {activeRaster && <Legend activeLayer={activeRaster} />}

      {/* Point info popup */}
      {pointData && (
        <PointInfo data={pointData} onClose={() => setPointData(null)} />
      )}

      {/* Loading indicators */}
      {(loading.corridors || loading.roads || loading.aqi) && (
        <div className="loading-indicator">
          Loading {loading.corridors ? 'corridors' : loading.aqi ? 'AQI stations' : 'roads'}…
        </div>
      )}
      
      {/* Intervention Panel — slides in from right when corridor is selected */}
      {isPanelOpen && selectedCorridor ? (
        <InterventionPanel 
          corridor={selectedCorridor}
          onClose={() => {
            setIsPanelOpen(false);
            setSelectedCorridor(null);
            setShouldRestoreView(true);
          }}
        />
      ) : null}
    </div>
  );
}
