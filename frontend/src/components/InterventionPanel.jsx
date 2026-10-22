/**
 * InterventionPanel — Right-side sliding panel for corridor intervention inspection.
 *
 * Displays:
 * - 3 Distinct Evaluative Vectors: Priority Need, Implementation Feasibility, Evidence Confidence
 * - Scientific Data Provenance & Resolution Warnings
 * - Transparent Rules-Based Greening & Shading Recommendations
 * - Itemized Lifecycle Cost Estimates (CPWD Delhi Schedule of Rates benchmarks)
 * - Mandatory Pre-Implementation Site Checks & Constraints
 * - Feasible Alternatives
 * - Upvotes & Community Suggestions
 * - Multi-Criteria Corridor Decision Simulation (3D Viewer)
 */

import { useEffect, useRef, useState } from 'react';
import './InterventionPanel.css';
import CommunitySuggestions from './CommunitySuggestions';
import CorridorDecisionPlanner from './CorridorDecisionPlanner';
import { suggestionsApi, roadsApi } from '../api';

const ICON_KEYWORDS = [
  [/tree|canopy|neem|peepal|banyan|albizia|cassia|arjuna/i, "🌳"],
  [/shade|cool|mist|reflective|solar|shelter/i, "☂️"],
  [/hedge|buffer|screen|bamboo|filter|dust/i, "🌲"],
  [/pocket|park|garden|micro-forest|miyawaki/i, "🏞️"],
  [/cycle|pedestrian|walkway|boulevard/i, "🚴"],
  [/wall|vertical|façade|creeper|climbing/i, "🌿"],
  [/rain|bioswale|stormwater|drain/i, "💧"],
  [/community|adopt|school|citizen|RWA/i, "🤝"],
  [/AQI|monitor|display|sensor/i, "📊"],
  [/food|market|composting/i, "🌱"],
  [/pavement|albedo|coating/i, "🎨"],
];

function interventionIcon(text) {
  for (const [re, icon] of ICON_KEYWORDS) {
    if (re.test(text)) return icon;
  }
  return "🌱";
}

const TYPE_LABELS = {
  street_trees_canopy: "Linear Street Trees & Native Canopy Expansion",
  shade_structures_waiting: "Architectural Shade Structures & Transit Shelters",
  water_sensitive_infrastructure: "Roadside Bioswales & Water-Sensitive Drainage",
  vertical_greenery_facades: "Living Green Walls & Boundary Facade Trellises",
  cool_pavements_surfaces: "High-Albedo Cool Pavements & Reflective Walkways",
  heat_dominated: "Heat-Dominated Pedestrian Corridor",
  pollution_dominated: "Air Quality Intervention Corridor",
  green_deficit: "Green Connectivity Deficit Corridor",
  mixed_exposure: "Multi-Stress Environmental Corridor",
  pedestrian_hotspot: "High-Density Pedestrian Spine",
  vulnerable_zone: "Vulnerable Community Transit Corridor",
};

export default function InterventionPanel({ corridor, onClose }) {
  const panelRef = useRef(null);

  const [upvotes, setUpvotes] = useState(0);
  const [hasUpvoted, setHasUpvoted] = useState(false);
  const [isUpvoting, setIsUpvoting] = useState(false);

  // Prune AI Gateway + Gemini Ranking Explanation
  const [aiExplanation, setAiExplanation] = useState(null);
  const [loadingAi, setLoadingAi] = useState(false);
  const [aiError, setAiError] = useState(null);

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

    setAiExplanation(null);
    setAiError(null);
  }, [corridorId]);

  const handleExplainRanking = async () => {
    setLoadingAi(true);
    setAiError(null);
    try {
      const res = await roadsApi.explainRanking({
        id: corridorId || 'corridor',
        name: roadName,
        district: props.district || 'NCT of Delhi',
        highway: props.highway || 'secondary',
        priority_score: priorityScore != null ? priorityScore : 0.5,
        feasibility: feasibilityScore,
        confidence: confidenceScore,
        scenario: props.scenario || 'balanced',
        signals: props.priority_signals || {
          heat: props.heat_norm || 0.5,
          green_deficit: props.ndvi_norm != null ? (1 - props.ndvi_norm) : 0.5,
          pollution: props.aqi_norm || 0.5,
        },
        active_weights: props.active_weights || {},
      });
      setAiExplanation(res.data);
    } catch (err) {
      console.error('Failed to explain ranking:', err);
      setAiError(err.response?.data?.detail || err.message || 'Failed to generate explanation');
    } finally {
      setLoadingAi(false);
    }
  };

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

  const corridorType = props.corridor_type || 'street_trees_canopy';
  const interventions = props.recommended_interventions || [];
  const rationale = props.intervention_rationale || '';
  const typeIcon = props.corridor_type_icon || '🌳';
  const typeColor = props.corridor_type_color || '#1a9850';
  const roadName = props.name || 'Selected Corridor';
  const costs = props.lifecycle_costs || {};
  const constraints = props.constraints || [];
  const siteChecks = props.required_site_checks || [];
  const alternatives = props.feasible_alternatives || [];
  const warnings = props.data_warnings || [];

  const priorityScore = props.priority_score != null ? props.priority_score : (props.gdi_mean != null ? props.gdi_mean : null);
  const feasibilityScore = props.feasibility != null ? props.feasibility : 0.65;
  const confidenceScore = props.confidence != null ? props.confidence : 0.70;

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
          <span className="panel-subtitle">
            {props.district ? `${props.district} • ` : ''}
            {props.length_meters ? `${Math.round(props.length_meters)} meters • ` : ''}
            Walkable Segment
          </span>
        </div>
      </div>

      {/* Upvote Button */}
      <div className="corridor-upvote-section">
        <button
          className={`corridor-upvote-btn ${hasUpvoted ? 'upvoted' : ''}`}
          onClick={handleUpvote}
          disabled={hasUpvoted || isUpvoting}
        >
          <span className="upvote-icon">👍</span>
          <span className="upvote-text">
            {hasUpvoted ? 'Supported by Community' : 'Support This Corridor'}
          </span>
          <span className="upvote-count">{upvotes}</span>
        </button>
      </div>

      {/* Core Evaluative Metrics: 3 Distinct Vectors */}
      <div className="evaluative-vectors-card">
        <div className="vector-item">
          <div className="vector-label">Priority Need</div>
          <div className="vector-value priority-text">
            {priorityScore != null ? priorityScore.toFixed(2) : 'N/A'}
          </div>
          <div className="vector-caption">Exposure & Stress</div>
        </div>

        <div className="vector-item">
          <div className="vector-label">Feasibility</div>
          <div className="vector-value feasibility-text">
            {feasibilityScore.toFixed(2)}
          </div>
          <div className="vector-caption">Physical ROW & Space</div>
        </div>

        <div className="vector-item">
          <div className="vector-label">Confidence</div>
          <div className="vector-value confidence-text">
            {confidenceScore.toFixed(2)}
          </div>
          <div className="vector-caption">Data Quality & Res.</div>
        </div>
      </div>

      {/* Explain This Ranking with Prune + Gemini */}
      <div className="ai-explanation-section">
        {!aiExplanation && !loadingAi && (
          <button
            className="ai-explain-btn"
            onClick={handleExplainRanking}
          >
            <span className="ai-sparkle-icon">✨</span>
            Explain This Ranking (Prune AI)
          </button>
        )}

        {loadingAi && (
          <div className="ai-loading-state">
            <span className="spinner-mini">⏳</span>
            <span>Querying Prune Gateway & Gemini model...</span>
          </div>
        )}

        {aiError && (
          <div className="ai-error-box">
            <span>⚠️ {aiError}</span>
          </div>
        )}

        {aiExplanation && (
          <div className="ai-explanation-card">
            <div className="ai-card-header">
              <div className="ai-card-title">
                <span className="ai-sparkle-icon">✨</span>
                <strong>AI Ranking Analysis</strong>
              </div>
              <span className={`ai-badge ${aiExplanation.is_ai_generated ? 'live' : 'offline'}`}>
                {aiExplanation.is_ai_generated ? (aiExplanation.model_used || 'Gemini 2.0 Flash') : 'Deterministic Fallback'}
              </span>
            </div>

            <p className="ai-explanation-body">
              {aiExplanation.explanation || aiExplanation.fallback_explanation}
            </p>

            {aiExplanation.status === 'not_configured' && (
              <div className="ai-setup-notice">
                ℹ️ <em>PRUNE_API_KEY unconfigured. Grounded deterministic breakdown displayed. Vault Gemini key in Prune to activate live AI reasoning.</em>
              </div>
            )}

            {aiExplanation.prune_metadata && (
              <div className="prune-receipt-bar">
                <span>🛡️ Prune Receipt: {aiExplanation.prune_metadata.signed_receipt?.slice(0, 16) || 'verified'}</span>
                {aiExplanation.prune_metadata.cost != null && (
                  <span>Cost: ${(aiExplanation.prune_metadata.cost).toFixed(5)}</span>
                )}
              </div>
            )}

            <button
              className="ai-refresh-btn"
              onClick={handleExplainRanking}
              disabled={loadingAi}
            >
              🔄 Refresh Analysis
            </button>
          </div>
        )}
      </div>

      {/* Data Quality & Spatial Resolution Caveat */}
      <div className="resolution-warning-box">
        <strong>⚠️ Data Provenance & Resolution Notice:</strong>
        <p>
          Thermal data originates from 1 km MODIS satellite observations resampled for regional screening.
          Results represent screening-level priority estimates, not microclimate field measurements.
        </p>
        {warnings.length > 0 && (
          <ul className="specific-warnings-list">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        )}
      </div>

      {/* Corridor Strategy Classification */}
      <div className="corridor-type-section">
        <div
          className="corridor-type-badge"
          style={{ borderColor: typeColor, color: typeColor }}
        >
          {TYPE_LABELS[corridorType] || corridorType}
        </div>
      </div>

      {/* Multi-Criteria Signal Breakdown */}
      <div className="attributes-section">
        <h4>Multi-Criteria Indicators</h4>
        {props.priority_signals ? (
          <div className="priority-signals-grid">
            {[
              { key: 'heat', label: 'Surface Heat', weight: '0.25', color: '#d73027' },
              { key: 'pollution', label: 'Air Quality (AQI)', weight: '0.20', color: '#7b3294' },
              { key: 'green_deficit', label: 'Green Deficit', weight: '0.20', color: '#1a9850' },
              { key: 'pedestrian', label: 'Pedestrian Flow', weight: '0.15', color: '#2166ac' },
              { key: 'health_risk', label: 'Health Risk', weight: '0.12', color: '#fc8d59' },
              { key: 'vulnerable_pop', label: 'Vulnerability', weight: '0.08', color: '#b35806' },
            ].map(({ key, label, weight, color }) => {
              const val = props.priority_signals[key];
              if (val == null) return null;
              const source = props.priority_data_sources?.[key];
              return (
                <div key={key} className="signal-bar-row">
                  <span className="signal-label-text">
                    {label}
                    {source && (
                      <span className={`signal-source-tag ${source.includes('secondary') || source.includes('community') ? 'live' : ''}`}>
                        {source.includes('sentinel') ? '10m S2' : (source.includes('modis') ? '1km MODIS' : (source.includes('cpcb') ? 'CPCB AQI' : 'Proxy'))}
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
        ) : (
          <div className="fallback-signals">
            <div><strong>Heat Intensity:</strong> {props.heat_norm != null ? props.heat_norm.toFixed(2) : "N/A"}</div>
            <div><strong>Green Deficit:</strong> {props.ndvi_norm != null ? (1 - props.ndvi_norm).toFixed(2) : "N/A"}</div>
            <div><strong>AQI Score:</strong> {props.aqi_norm != null ? props.aqi_norm.toFixed(2) : "N/A"}</div>
          </div>
        )}
      </div>

      {/* Suggested Interventions */}
      <div className="interventions-section">
        <h3>Suitability Recommendations</h3>
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

      {/* Why This Works (Rationale) */}
      <div className="rationale-section">
        <h3>Recommendation Rationale</h3>
        <p className="rationale-text">{rationale}</p>
      </div>

      {/* Itemized Lifecycle Cost Estimates */}
      {costs && costs.five_year_lifecycle_lakhs && (
        <div className="lifecycle-cost-card">
          <h3>Lifecycle Cost Estimate (Planning Benchmark)</h3>
          <p className="cost-meta-note">
            Grounded in CPWD Delhi Schedule of Rates (DSR 2023) and municipal forestry standards:
          </p>
          <div className="cost-breakdown-grid">
            <div className="cost-col">
              <span className="cost-subhead">CapEx (Installation)</span>
              <span className="cost-amount">₹{(costs.capex_inr / 100000).toFixed(1)} Lakhs</span>
            </div>
            <div className="cost-col">
              <span className="cost-subhead">Annual OpEx (Watering & Pruning)</span>
              <span className="cost-amount">₹{(costs.annual_opex_inr / 100000).toFixed(1)} Lakhs/yr</span>
            </div>
            <div className="cost-col highlight">
              <span className="cost-subhead">5-Year Total Cost</span>
              <span className="cost-amount-large">₹{costs.five_year_lifecycle_lakhs} Lakhs</span>
            </div>
          </div>
          <span className="service-life-tag">
            Expected Service Life: {costs.expected_service_life_years} years
          </span>
        </div>
      )}

      {/* Implementation Constraints & Mandatory Site Checks */}
      {(constraints.length > 0 || siteChecks.length > 0) && (
        <div className="site-checks-card">
          {constraints.length > 0 && (
            <div className="constraints-block">
              <h4>Site Constraints & Feasibility Barriers</h4>
              <ul>
                {constraints.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}

          {siteChecks.length > 0 && (
            <div className="site-checks-block">
              <h4>Mandatory Pre-Procurement Field Checks</h4>
              <ul>
                {siteChecks.map((sc, i) => (
                  <li key={i}>{sc}</li>
                ))}
              </ul>
            </div>
          )}

          {alternatives.length > 0 && (
            <div className="alternatives-block">
              <h4>Feasible Alternatives</h4>
              <ul>
                {alternatives.map((alt, i) => (
                  <li key={i}>{alt}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Community Suggestions */}
      {corridorId && (
        <CommunitySuggestions corridorId={corridorId} />
      )}

      {/* Corridor Design Simulation */}
      <div className="design-planner-section">
        <h3>Corridor Design Simulation</h3>
        <p className="planner-description">
          Simulate street greening scenarios across variable Right-of-Way widths,
          shade requirements, and pedestrian activity.
        </p>
        <CorridorDecisionPlanner />
      </div>
    </div>
  );
}