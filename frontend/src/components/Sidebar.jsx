/**
 * Sidebar Component — Layer controls and statistics
 *
 * Updated to support 6-factor Priority Index with real-time ranking.
 */
import { useState, useEffect, memo } from 'react';
import { Link } from 'react-router-dom';
import { statsApi, layersApi, aqiApi } from '../api';
import SecondaryUserInput from './SecondaryUserInput';
import HealthDataInput from './HealthDataInput';
import PriorityRanking from './PriorityRanking';
import './Sidebar.css';

/**
 * Toggle switch component — uses real checkbox for accessibility
 */
const Toggle = memo(function Toggle({ checked, onChange, label, color }) {
  return (
    <label className="toggle-row">
      <span className="toggle-label">
        {color ? <span className="layer-indicator" style={{ backgroundColor: color }} aria-hidden="true" /> : null}
        {label}
      </span>
      <input
        type="checkbox"
        className="toggle-input sr-only"
        checked={checked}
        onChange={onChange}
        aria-label={`Toggle ${label}`}
      />
      <span className={`toggle-switch ${checked ? 'active' : ''}`} aria-hidden="true">
        <span className="toggle-knob" />
      </span>
    </label>
  );
});

/**
 * Stats card component
 */
const StatCard = memo(function StatCard({ title, value, unit, icon }) {
  return (
    <div className="stat-card">
      <span className="stat-icon" aria-hidden="true">{icon}</span>
      <div className="stat-content">
        <span className="stat-value">
          {typeof value === 'number' ? value.toFixed(2) : value || '—'}
          {unit ? <span className="stat-unit">{unit}</span> : null}
        </span>
        <span className="stat-title">{title}</span>
      </div>
    </div>
  );
});

/**
 * Main Sidebar component
 */
export default function Sidebar({ activeLayers, setActiveLayers }) {
  const [stats, setStats] = useState(null);
  const [aqiStatus, setAqiStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState({
    layers: true,
    rasters: true,
    vectors: true,
    stats: true,
  });

  // Fetch stats on mount
  useEffect(() => {
    setLoading(true);
    Promise.all([
      statsApi.all(),
      aqiApi.status()
    ])
      .then(([statsRes, aqiRes]) => {
        setStats(statsRes.data);
        setAqiStatus(aqiRes.data);
      })
      .catch(err => console.error('Failed to load stats:', err))
      .finally(() => setLoading(false));
  }, []);

  const toggleLayer = (layer) => {
    setActiveLayers(prev => ({
      ...prev,
      [layer]: !prev[layer]
    }));
  };

  const toggleSection = (section) => {
    setExpanded(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  return (
    <aside className="sidebar" role="complementary" aria-label="Dashboard controls">
      {/* Header */}
      <div className="sidebar-header">
        <div className="logo">
          <span className="logo-icon" aria-hidden="true">🌿</span>
          <div className="logo-text">
            <h1>VanSetu</h1>
            <span className="subtitle">Delhi NCT Analysis</span>
          </div>
        </div>
      </div>

      {/* Layer Controls */}
      <div className="sidebar-section">
        <button
          className="section-header"
          onClick={() => toggleSection('layers')}
          aria-expanded={expanded.layers}
          aria-controls="section-layers"
        >
          <h3>Data Layers</h3>
          <span className={`chevron ${expanded.layers ? 'open' : ''}`} aria-hidden="true">▼</span>
        </button>

        {expanded.layers ? (
          <div className="section-content" id="section-layers">
            {/* Raster layers */}
            <fieldset className="layer-group">
              <legend className="group-label">Raster Data</legend>
              <Toggle
                label="Vegetation (NDVI)"
                checked={activeLayers.ndvi}
                onChange={() => toggleLayer('ndvi')}
                color="#238b45"
              />
              <Toggle
                label="Temperature (LST)"
                checked={activeLayers.lst}
                onChange={() => toggleLayer('lst')}
                color="#e05252"
              />
              <Toggle
                label="Priority Index (GDI)"
                checked={activeLayers.gdi}
                onChange={() => toggleLayer('gdi')}
                color="#f2c94c"
              />
            </fieldset>

            {/* Vector layers */}
            <fieldset className="layer-group">
              <legend className="group-label">Vector Data</legend>
              <Toggle
                label="Road Network"
                checked={activeLayers.roads}
                onChange={() => toggleLayer('roads')}
                color="#666"
              />
              <Toggle
                label="VanSetu Corridors"
                checked={activeLayers.corridors}
                onChange={() => toggleLayer('corridors')}
                color="#fc8d59"
              />
              <Toggle
                label="AQI Stations"
                checked={activeLayers.aqi}
                onChange={() => toggleLayer('aqi')}
                color="#7b3294"
              />
            </fieldset>

            {/* OSM Overlay layers */}
            <fieldset className="layer-group">
              <legend className="group-label">OSM Overlays</legend>
              <Toggle
                label="Roads Overlay"
                checked={activeLayers.osmRoads}
                onChange={() => toggleLayer('osmRoads')}
                color="#888888"
              />
              <Toggle
                label="Parks &amp; Green"
                checked={activeLayers.osmParks}
                onChange={() => toggleLayer('osmParks')}
                color="#2d8b2d"
              />
              <Toggle
                label="Residential"
                checked={activeLayers.osmResidential}
                onChange={() => toggleLayer('osmResidential')}
                color="#c4a484"
              />
            </fieldset>
          </div>
        ) : null}
      </div>

      {/* Statistics */}
      <div className="sidebar-section">
        <button
          className="section-header"
          onClick={() => toggleSection('stats')}
          aria-expanded={expanded.stats}
          aria-controls="section-stats"
        >
          <h3>Statistics</h3>
          <span className={`chevron ${expanded.stats ? 'open' : ''}`} aria-hidden="true">▼</span>
        </button>

        {expanded.stats ? (
          <div className="section-content" id="section-stats">
            {loading ? (
              <div className="loading-stats" aria-live="polite">Loading statistics…</div>
            ) : stats ? (
              <div className="stats-grid">
                <StatCard title="Mean NDVI" value={stats.ndvi?.mean} icon="🌿" />
                <StatCard title="Mean Temp" value={stats.lst?.mean} unit="°C" icon="🌡️" />
                <StatCard title="Mean Priority" value={stats.gdi?.mean} icon="📊" />
                <StatCard title="Avg PM2.5" value={aqiStatus?.average_pm25} icon="💨" />
              </div>
            ) : (
              <div className="no-stats">No statistics available</div>
            )}
          </div>
        ) : null}
      </div>

      {/* Priority Ranking */}
      <div className="sidebar-section">
        <button
          className="section-header"
          onClick={() => toggleSection('priorityRanking')}
          aria-expanded={expanded.priorityRanking || false}
          aria-controls="section-priority-ranking"
        >
          <h3>Priority Ranking</h3>
          <span className={`chevron ${expanded.priorityRanking ? 'open' : ''}`} aria-hidden="true">&#9660;</span>
        </button>

        {expanded.priorityRanking ? (
          <div className="section-content" id="section-priority-ranking">
            <PriorityRanking />
          </div>
        ) : null}
      </div>

      {/* Community Input */}
      <div className="sidebar-section">
        <button
          className="section-header"
          onClick={() => toggleSection('communityInput')}
          aria-expanded={expanded.communityInput || false}
          aria-controls="section-community-input"
        >
          <h3>Community Input</h3>
          <span className={`chevron ${expanded.communityInput ? 'open' : ''}`} aria-hidden="true">▼</span>
        </button>

        {expanded.communityInput ? (
          <div className="section-content" id="section-community-input">
            <SecondaryUserInput />
          </div>
        ) : null}
      </div>

      {/* Health Data Input */}
      <div className="sidebar-section">
        <button
          className="section-header"
          onClick={() => toggleSection('healthData')}
          aria-expanded={expanded.healthData || false}
          aria-controls="section-health-data"
        >
          <h3>Health Data</h3>
          <span className={`chevron ${expanded.healthData ? 'open' : ''}`} aria-hidden="true">▼</span>
        </button>

        {expanded.healthData ? (
          <div className="section-content" id="section-health-data">
            <HealthDataInput />
          </div>
        ) : null}
      </div>

      {/* Info Section */}
      <div className="sidebar-section">
        <button
          className="section-header"
          onClick={() => toggleSection('info')}
          aria-expanded={expanded.info || false}
          aria-controls="section-info"
        >
          <h3>About</h3>
          <span className={`chevron ${expanded.info ? 'open' : ''}`} aria-hidden="true">▼</span>
        </button>

        {expanded.info ? (
          <div className="section-content" id="section-info">
            <div className="info-text">
              <p>
                <strong>6-Factor Priority Index</strong> combines real-time
                environmental data with ground-level secondary inputs to
                identify areas most in need of green infrastructure.
              </p>
              <p className="formula">
                Priority = (Heat &times; 0.25) + (Pollution &times; 0.20) + (Green Deficit &times; 0.20) + (Pedestrian &times; 0.15) + (Health Risk &times; 0.12) + (Vulnerable Pop. &times; 0.08)
              </p>
              <p className="formula-note">
                Health Risk Index and Vulnerable Population are derived from
                secondary (ground-level) user inputs when available.
              </p>
              <p>
                <strong>Click anywhere</strong> on the map to query layer
                values at that location.
              </p>
            </div>
          </div>
        ) : null}
      </div>

      {/* Footer */}
      <footer className="sidebar-footer">
        <Link to="/admin" className="admin-link">
          Admin Dashboard
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </Link>
        <p>VanSetu Platform</p>

      </footer>
    </aside>
  );
}
