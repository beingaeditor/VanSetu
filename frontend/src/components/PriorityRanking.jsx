/**
 * PriorityRanking — Real-time priority ranking panel
 *
 * Fetches corridor priority data from /corridors/priority-ranking and
 * displays a ranked list showing which corridors need intervention most
 * urgently, with per-signal breakdown.
 */

import { useEffect, useState, useCallback } from 'react';
import { roadsApi } from '../api';
import './PriorityRanking.css';

const SIGNAL_LABELS = {
  heat: 'Heat',
  pollution: 'Pollution',
  green_deficit: 'Green Deficit',
  pedestrian: 'Pedestrian Density',
  health_risk: 'Health Risk Index',
  vulnerable_pop: 'Vulnerable Pop.',
};

const SIGNAL_COLORS = {
  heat: '#d73027',
  pollution: '#7b3294',
  green_deficit: '#1a9850',
  pedestrian: '#2166ac',
  health_risk: '#fc8d59',
  vulnerable_pop: '#b35806',
};

const SIGNAL_WEIGHTS = {
  heat: 0.25,
  pollution: 0.20,
  green_deficit: 0.20,
  pedestrian: 0.15,
  health_risk: 0.12,
  vulnerable_pop: 0.08,
};

const SOURCE_LABELS = {
  secondary_input: 'Live Data',
  community_input: 'Community',
  proxy_heat_x_aqi: 'Proxy',
  proxy_zone_lookup: 'Proxy',
  proxy_osm_highway: 'OSM',
};

function severityClass(tier) {
  if (tier === 'critical') return 'severity-critical';
  if (tier === 'high') return 'severity-high';
  return 'severity-moderate';
}

export default function PriorityRanking() {
  const [ranking, setRanking] = useState(null);
  const [scenario, setScenario] = useState('balanced');
  const [sensitivity, setSensitivity] = useState(null);
  const [showSensitivity, setShowSensitivity] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedIdx, setExpandedIdx] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchRanking = useCallback((selectedScenario = scenario) => {
    setLoading(true);
    setError(null);
    Promise.all([
      roadsApi.priorityRanking(85, selectedScenario),
      roadsApi.sensitivity(85).catch(() => ({ data: null })),
    ])
      .then(([res, sensRes]) => {
        setRanking(res.data);
        if (sensRes?.data) {
          setSensitivity(sensRes.data);
        }
        setLastUpdated(new Date());
      })
      .catch((err) => {
        console.error('Priority ranking fetch failed:', err);
        setError('Failed to load ranking data');
      })
      .finally(() => setLoading(false));
  }, [scenario]);

  useEffect(() => {
    fetchRanking(scenario);
  }, [scenario, fetchRanking]);

  const corridors = ranking?.ranked_corridors || ranking?.corridors || [];
  const meta = ranking?.metadata || {};
  const availableScenarios = ranking?.available_scenarios || [
    'balanced',
    'heat_resilience',
    'air_quality_focus',
    'pedestrian_equity',
    'extreme_vulnerability',
  ];

  return (
    <div className="priority-ranking">
      <div className="pr-header">
        <h3>6-Factor Multi-Criteria Priority</h3>
        <button className="pr-refresh-btn" onClick={() => fetchRanking(scenario)} disabled={loading}>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', alignItems: 'center' }}>
        <label htmlFor="pr-scenario-select" style={{ fontSize: '10px', color: '#9ca3af' }}>Scenario:</label>
        <select
          id="pr-scenario-select"
          value={scenario}
          onChange={(e) => setScenario(e.target.value)}
          style={{
            flex: 1,
            background: 'rgba(15,23,42,0.8)',
            color: '#fff',
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: '4px',
            padding: '3px 6px',
            fontSize: '11px',
          }}
        >
          {availableScenarios.map((sc) => (
            <option key={sc} value={sc}>
              {sc.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
        {sensitivity && (
          <button
            type="button"
            className="pr-refresh-btn"
            onClick={() => setShowSensitivity(!showSensitivity)}
          >
            {showSensitivity ? 'Hide Stability' : '5-Scenario Stability'}
          </button>
        )}
      </div>

      {showSensitivity && sensitivity && (
        <div
          style={{
            background: 'rgba(15, 23, 42, 0.7)',
            border: '1px solid rgba(56, 189, 248, 0.25)',
            borderRadius: '6px',
            padding: '8px',
            marginBottom: '10px',
            fontSize: '10.5px',
          }}
        >
          <div style={{ fontWeight: 600, color: '#38bdf8', marginBottom: '4px' }}>
            Multi-Scenario Rank Stability ({sensitivity.corridor_count} Corridors)
          </div>
          <div style={{ color: '#cbd5e1', marginBottom: '4px' }}>
            Stable: <strong>{sensitivity.stability_summary?.stable_corridors_count}</strong> •
            Sensitive: <strong>{sensitivity.stability_summary?.volatile_corridors_count}</strong>
          </div>
          <div style={{ color: '#94a3b8', fontSize: '9.5px' }}>
            {sensitivity.stability_summary?.note}
          </div>
        </div>
      )}

      {lastUpdated && (
        <div className="pr-timestamp">
          Updated: {lastUpdated.toLocaleTimeString()}
        </div>
      )}

      {error && <div className="pr-error">{error}</div>}

      {!loading && corridors.length === 0 && !error && (
        <div className="pr-empty">No corridors available. Make sure the backend is running.</div>
      )}

      <div className="pr-formula-bar">
        {Object.entries(SIGNAL_WEIGHTS).map(([key, weight]) => (
          <span key={key} className="pr-weight-chip" style={{ borderColor: SIGNAL_COLORS[key] }}>
            <span className="pr-weight-dot" style={{ background: SIGNAL_COLORS[key] }} />
            {SIGNAL_LABELS[key]} ({(weight * 100).toFixed(0)}%)
          </span>
        ))}
      </div>

      <div className="pr-list">
        {corridors.slice(0, 20).map((c, idx) => {
          const isExpanded = expandedIdx === idx;
          const signals = c.signals || {};
          const sources = c.data_sources || {};

          return (
            <div
              key={idx}
              className={`pr-item ${severityClass(c.severity_tier)} ${isExpanded ? 'expanded' : ''}`}
              onClick={() => setExpandedIdx(isExpanded ? null : idx)}
            >
              <div className="pr-item-main">
                <span className="pr-rank">#{c.rank}</span>
                <div className="pr-item-info">
                  <span className="pr-item-name">{c.name}</span>
                  <span className="pr-item-type">{c.corridor_type?.replace(/_/g, ' ')}</span>
                </div>
                <div className="pr-item-score">
                  <span className="pr-score-value">{c.priority_score?.toFixed(3)}</span>
                  <span className={`pr-severity-badge ${severityClass(c.severity_tier)}`}>
                    {c.severity_tier}
                  </span>
                </div>
              </div>

              {isExpanded && (
                <div className="pr-item-detail">
                  <div className="pr-signal-bars">
                    {Object.entries(SIGNAL_LABELS).map(([key, label]) => {
                      const val = signals[key];
                      if (val == null) return null;
                      const weighted = val * SIGNAL_WEIGHTS[key];
                      const source = sources[key];
                      return (
                        <div key={key} className="pr-signal-row">
                          <span className="pr-signal-label">
                            {label}
                            {source && (
                              <span className={`pr-source-tag ${source.includes('secondary') || source.includes('community') ? 'live' : 'proxy'}`}>
                                {SOURCE_LABELS[source] || source}
                              </span>
                            )}
                          </span>
                          <div className="pr-bar-track">
                            <div
                              className="pr-bar-fill"
                              style={{
                                width: `${Math.min(val * 100, 100)}%`,
                                background: SIGNAL_COLORS[key],
                              }}
                            />
                          </div>
                          <span className="pr-signal-val">
                            {val.toFixed(2)} &times; {SIGNAL_WEIGHTS[key]} = {weighted.toFixed(3)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {corridors.length > 20 && (
        <div className="pr-more">
          Showing top 20 of {meta.count} corridors
        </div>
      )}
    </div>
  );
}
