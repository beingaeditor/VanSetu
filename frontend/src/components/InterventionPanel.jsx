/**
 * InterventionPanel — Right-side sliding panel for corridor intervention suggestions
 *
 * Displays when a corridor is clicked:
 * - Corridor type classification
 * - Recommended green interventions
 * - Human-readable rationale
 * - Upvote button for community support
 * - Community suggestions
 * - Corridor design simulation (3D visualization)
 */

import { useEffect, useRef, useState } from 'react';
import './InterventionPanel.css';
import CommunitySuggestions from './CommunitySuggestions';
import CorridorDecisionPlanner from './CorridorDecisionPlanner';
import { suggestionsApi } from '../api';

const ICON_KEYWORDS = [
  [/tree|canopy|neem|peepal|banyan|albizia|cassia|arjuna/i, "🌳"],
  [/shade|cool|mist|reflective|solar/i, "☂️"],
  [/hedge|buffer|screen|bamboo|filter|dust/i, "🌲"],
  [/pocket|park|garden|micro-forest|miyawaki/i, "🏞️"],
  [/cycle|pedestrian|walkway|boulevard/i, "🚴"],
  [/wall|vertical|façade|creeper|climbing/i, "🌿"],
  [/rain|bioswale|stormwater|drain/i, "💧"],
  [/community|adopt|school|citizen|RWA/i, "🤝"],
  [/AQI|monitor|display|sensor/i, "📊"],
  [/food|market|composting/i, "🌱"],
];

function interventionIcon(text) {
  for (const [re, icon] of ICON_KEYWORDS) {
    if (re.test(text)) return icon;
  }
  return "🌱";
}

const TYPE_LABELS = {
  heat_dominated: "Heat-Dominated Corridor",
  pollution_dominated: "Air Quality Corridor",
  green_deficit: "Green Connectivity Corridor",
  mixed_exposure: "Multi-Challenge Corridor"
};

export default function InterventionPanel({ corridor, onClose }) {

  const panelRef = useRef(null);

  const [upvotes, setUpvotes] = useState(0);
  const [hasUpvoted, setHasUpvoted] = useState(false);
  const [isUpvoting, setIsUpvoting] = useState(false);

  const props = corridor?.properties || {};
  const corridorId = props.id || corridor?.id || null;

  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') onClose();
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);

  }, [onClose]);

  useEffect(() => {

    if (!corridorId) return;

    setHasUpvoted(false);
    setUpvotes(0);

    suggestionsApi.getCorridorUpvotes(corridorId)
      .then(res => setUpvotes(res.data.upvotes || 0))
      .catch(err => console.error('Failed to fetch upvotes:', err));

  }, [corridorId]);

  const handleUpvote = async () => {

    if (hasUpvoted || isUpvoting || !corridorId) return;

    setIsUpvoting(true);
    setUpvotes(prev => prev + 1);
    setHasUpvoted(true);

    try {
      const res = await suggestionsApi.upvoteCorridor(corridorId);
      setUpvotes(res.data.upvotes);
    } catch (err) {
      console.error('Failed to upvote:', err);
      setUpvotes(prev => prev - 1);
      setHasUpvoted(false);
    } finally {
      setIsUpvoting(false);
    }
  };

  if (!corridor) return null;

  const corridorType = props.corridor_type || 'mixed_exposure';
  const interventions = props.recommended_interventions || [];
  const rationale = props.intervention_rationale || '';
  const typeIcon = props.corridor_type_icon || '🛤️';
  const typeColor = props.corridor_type_color || '#fc8d59';
  const roadName = props.name || 'Selected Corridor';

  return (

    <div className="intervention-panel" ref={panelRef}>

      {/* Close button */}
      <button
        className="panel-close-btn"
        onClick={onClose}
        aria-label="Close panel"
      >
        ✕
      </button>

      {/* Header */}
      <div className="panel-header">

        <div className="panel-icon" style={{ background: typeColor }}>
          {typeIcon}
        </div>

        <div className="panel-title">
          <h2>{roadName}</h2>
          <span className="panel-subtitle">Corridor Selected</span>
        </div>

      </div>

      {/* Upvote Section */}

      <div className="corridor-upvote-section">

        <button
          className={`corridor-upvote-btn ${hasUpvoted ? 'upvoted' : ''}`}
          onClick={handleUpvote}
          disabled={hasUpvoted || isUpvoting}
        >

          <span className="upvote-icon">👍</span>

          <span className="upvote-text">
            {hasUpvoted ? 'Supported' : 'Support This Corridor'}
          </span>

          <span className="upvote-count">{upvotes}</span>

        </button>

      </div>

      {/* Corridor Type */}

      <div className="corridor-type-section">

        <div
          className="corridor-type-badge"
          style={{ borderColor: typeColor, color: typeColor }}
        >
          {TYPE_LABELS[corridorType] || corridorType}
        </div>

      </div>

      {/* Corridor Attributes — 6-Factor Priority Breakdown */}

      <div className="attributes-section">

        <div className="priority-breakdown-header">
          <strong>Priority Score:</strong>{' '}
          <span className="priority-score-display">
            {props.priority_score != null ? props.priority_score.toFixed(3) : 'N/A'}
          </span>
          {props.severity_tier && (
            <span className={`panel-severity-badge severity-${props.severity_tier}`}>
              {props.severity_tier}
            </span>
          )}
        </div>

        {props.priority_signals && (
          <div className="priority-signals-grid">
            {[
              { key: 'heat', label: 'Heat', weight: '0.25', color: '#d73027' },
              { key: 'pollution', label: 'Pollution', weight: '0.20', color: '#7b3294' },
              { key: 'green_deficit', label: 'Green Deficit', weight: '0.20', color: '#1a9850' },
              { key: 'pedestrian', label: 'Pedestrian', weight: '0.15', color: '#2166ac' },
              { key: 'health_risk', label: 'Health Risk', weight: '0.12', color: '#fc8d59' },
              { key: 'vulnerable_pop', label: 'Vulnerable Pop.', weight: '0.08', color: '#b35806' },
            ].map(({ key, label, weight, color }) => {
              const val = props.priority_signals[key];
              if (val == null) return null;
              const source = props.priority_data_sources?.[key];
              return (
                <div key={key} className="signal-bar-row">
                  <span className="signal-label-text">
                    {label} (&times;{weight})
                    {source && (
                      <span className={`signal-source-tag ${source.includes('secondary') || source.includes('community') ? 'live' : ''}`}>
                        {source.includes('secondary') || source.includes('community') ? 'Live' : 'Proxy'}
                      </span>
                    )}
                  </span>
                  <div className="signal-bar-bg">
                    <div className="signal-bar-fg" style={{ width: `${Math.min(val * 100, 100)}%`, background: color }} />
                  </div>
                  <span className="signal-val-text">{val.toFixed(2)}</span>
                </div>
              );
            })}
          </div>
        )}

        {!props.priority_signals && (
          <>
            <div className="attribute">
              <strong>Heat Intensity:</strong> {props.heat_norm != null ? props.heat_norm.toFixed(2) : "Unknown"}
            </div>
            <div className="attribute">
              <strong>Pollution (AQI):</strong> {props.aqi_norm != null ? props.aqi_norm.toFixed(2) : "Unknown"}
            </div>
            <div className="attribute">
              <strong>Green Deficit:</strong> {props.ndvi_norm != null ? (1 - props.ndvi_norm).toFixed(2) : "Unknown"}
            </div>
            <div className="attribute">
              <strong>Pedestrian Score:</strong> {props.pedestrian_score != null ? props.pedestrian_score.toFixed(2) : "Unknown"}
            </div>
          </>
        )}
      </div>

      {/* Interventions */}

      <div className="interventions-section">

        <h3>Suggested Interventions</h3>

        <div className="interventions-list">

          {interventions.length > 0 ? (

            interventions.map((intervention, idx) => (

              <div key={idx} className="intervention-item">

                <span className="intervention-icon">
                  {interventionIcon(intervention)}
                </span>

                <span className="intervention-text">
                  {intervention}
                </span>

              </div>

            ))

          ) : (

            <p>No interventions available for this corridor.</p>

          )}

        </div>

      </div>

      {/* Rationale */}

      <div className="rationale-section">

        <h3>Why This Works</h3>
        <p className="rationale-text">{rationale}</p>

      </div>

      {/* Community Suggestions */}

      {corridorId ? (
        <CommunitySuggestions corridorId={corridorId} />
      ) : null}

      {/* Corridor Design Planner */}

      <div className="design-planner-section">

        <h3>Corridor Design Simulation</h3>

        <p className="planner-description">
          Simulate green corridor layouts based on infrastructure capacity,
          pedestrian activity, and environmental risk indicators.
        </p>

        <CorridorDecisionPlanner />

      </div>

      {/* Footer */}

      <div className="panel-footer">

        <span className="footer-hint">
          Press ESC or click ✕ to return to map
        </span>

      </div>

    </div>

  );
}