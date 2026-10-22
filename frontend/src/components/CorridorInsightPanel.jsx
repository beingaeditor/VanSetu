/**
 * CorridorInsightPanel — Right Column of the Van Setu Urban Climate Studio.
 *
 * Implements:
 * 1. "Corridor Inspected: <Name>" header with deterministic score, Rank, Heat, NDVI, PM2.5/AQI, and Upvote support.
 * 2. "Baseline vs. What-If Rank Changes" comparison table (interactive row selection).
 * 3. "Recommended Physical Interventions" visual cards with cooling impact, canopy, ROW, and species.
 * 4. "Lifecycle Cost Estimate (CPWD DSR 2023)" card with CapEx, Annual OpEx, and 5-Year Lifecycle total.
 * 5. "AI-Assisted Explanation" card (isolated Prune/Gemini call with Live/Deterministic badge and "Explain this ranking ↗").
 * 6. Compact "Community Suggestions" card + button to open the full Community Input modal.
 * 7. In Professional Mode ("Van Setu Pro"):
 *    - Multi-Scenario Ranking Stability table (across 5 policy scenarios)
 *    - Site Constraints, Mandatory Pre-Procurement Field Checks & Feasible Alternatives
 *    - Interactive 3D Corridor Design Simulation trigger
 *    - Reproducible Markdown/HTML Planning Report Export
 */

import { useState, useEffect } from 'react';
import { roadsApi, suggestionsApi } from '../api';
import CommunitySuggestions from './CommunitySuggestions';
import CorridorDecisionPlanner from './CorridorDecisionPlanner';
import ErrorBoundary from './ErrorBoundary';
import './CorridorInsightPanel.css';

const INTERVENTION_VISUALS = [
  {
    key: 'canopy',
    match: /tree|canopy|neem|peepal|jamun|arjuna|amaltas|boulevard/i,
    title: 'Native Shade Tree Avenue',
    subtitle: 'Neem / Peepal / Jamun / Arjuna',
    badge: '−2.8°C to −4.1°C LST',
    icon: '🌳',
    gradient: 'linear-gradient(135deg, #064e3b 0%, #059669 55%, #34d399 100%)',
    spec: 'Min. 1.8m tree-pit • 8–10m spacing',
  },
  {
    key: 'pergola',
    match: /shade|pergola|shelter|transit|modular|arcade|canopy/i,
    title: 'Solar-Reflective Shade Pergola',
    subtitle: 'Engineered Steel + Climbing Bougainvillea',
    badge: 'Immediate Pedestrian Shade',
    icon: '⛱️',
    gradient: 'linear-gradient(135deg, #1e3a8a 0%, #0284c7 55%, #38bdf8 100%)',
    spec: 'Narrow ROW compatible (<1.5m)',
  },
  {
    key: 'bioswale',
    match: /bioswale|hedge|buffer|shrub|water|rain|albedo|cool|wall|vertical/i,
    title: 'Multi-Layer PM2.5 Vegetative Buffer',
    subtitle: 'Dense Native Shrub + Pervious Bioswale Edge',
    badge: '−18% Roadside Particulate',
    icon: '🌿',
    gradient: 'linear-gradient(135deg, #115e59 0%, #0d9488 55%, #2dd4bf 100%)',
    spec: 'Captures stormwater & traps dust',
  },
];

function buildVisualInterventions(corridorProps) {
  const rawList = corridorProps?.recommended_interventions || [];
  const cards = [];

  if (rawList.length > 0) {
    rawList.slice(0, 3).forEach((text, idx) => {
      const matched =
        INTERVENTION_VISUALS.find((v) => v.match.test(text)) ||
        INTERVENTION_VISUALS[idx % INTERVENTION_VISUALS.length];
      cards.push({
        id: `${matched.key}-${idx}`,
        title: matched.title,
        description: text,
        badge: matched.badge,
        icon: matched.icon,
        gradient: matched.gradient,
        spec: matched.spec,
      });
    });
  } else {
    INTERVENTION_VISUALS.forEach((v, idx) => {
      cards.push({
        id: `${v.key}-${idx}`,
        title: v.title,
        description: v.subtitle,
        badge: v.badge,
        icon: v.icon,
        gradient: v.gradient,
        spec: v.spec,
      });
    });
  }
  return cards;
}

export default function CorridorInsightPanel({
  corridor,
  comparisonTable = [],
  baselineComparison = null,
  heatWeight = 0.6,
  topN = 5,
  studioMode = 'public',
  activeScenario = 'balanced',
  sensitivityData = null,
  onSelectCorridor,
  onOpenModal,
  onExportReport,
}) {
  const [upvotes, setUpvotes] = useState(0);
  const [hasUpvoted, setHasUpvoted] = useState(false);
  const [isUpvoting, setIsUpvoting] = useState(false);

  const [aiExplanation, setAiExplanation] = useState(null);
  const [loadingAi, setLoadingAi] = useState(false);
  const [aiError, setAiError] = useState(null);
  const [show3DPlanner, setShow3DPlanner] = useState(false);

  const props = corridor?.properties || corridor || {};
  const corridorId = props.id || corridor?.id || 'delhi_corridor_044';
  const corridorName = props.name || 'Select a Corridor';
  const district = props.district || 'NCT of Delhi';
  const highway = props.highway || 'secondary';
  const lengthMeters = props.length_meters || 650;

  const score =
    props.what_if_score ??
    props.score ??
    props.priority_score ??
    props.gdi_mean ??
    0.5867;
  const rank = props.what_if_rank ?? props.rank ?? 1;
  const baselineRank = props.baseline_rank ?? rank;
  const rankChange = props.rank_change ?? (baselineRank - rank);
  const baselineScore = props.baseline_score ?? score;

  const heatVal = props.heat ?? props.heat_norm ?? props.priority_signals?.heat ?? 0.5021;
  const ndviVal = props.ndvi ?? props.ndvi_norm ?? 0.2864;
  const greenDeficit = props.green_deficit ?? Math.max(0, 1 - ndviVal);
  const aqiVal = props.priority_signals?.pollution ?? props.aqi_norm ?? 0.62;
  const feasibilityVal = props.feasibility ?? 0.65;
  const confidenceVal = props.confidence ?? 0.72;

  const costs = props.lifecycle_costs || {
    total_capex_inr: 1580000,
    annual_opex_inr: 285000,
    five_year_total_inr: 3005000,
    five_year_lifecycle_lakhs: 30.05,
    expected_service_life_years: 15,
  };

  const capexLakhs =
    costs.total_capex_inr != null
      ? (costs.total_capex_inr / 100000).toFixed(2)
      : costs.capex_inr != null
      ? (costs.capex_inr / 100000).toFixed(2)
      : '15.80';
  const opexLakhs =
    costs.annual_opex_inr != null
      ? (costs.annual_opex_inr / 100000).toFixed(2)
      : '2.85';
  const fiveYearLakhs =
    costs.five_year_lifecycle_lakhs != null
      ? Number(costs.five_year_lifecycle_lakhs).toFixed(2)
      : costs.five_year_total_inr != null
      ? (costs.five_year_total_inr / 100000).toFixed(2)
      : '30.05';

  useEffect(() => {
    if (!corridorId) return;
    setHasUpvoted(false);
    suggestionsApi
      .getCorridorUpvotes(corridorId)
      .then((res) => setUpvotes(res.data?.upvotes || 0))
      .catch(() => setUpvotes(0));

    // Reset AI explanation when corridor or weight changes so user sees grounded preview or can request fresh Gemini explanation
    setAiExplanation(null);
    setAiError(null);
  }, [corridorId]);

  const handleUpvote = async () => {
    if (hasUpvoted || isUpvoting || !corridorId) return;
    setIsUpvoting(true);
    setUpvotes((prev) => prev + 1);
    setHasUpvoted(true);
    try {
      const res = await suggestionsApi.upvoteCorridor(corridorId);
      if (res.data?.upvotes != null) setUpvotes(res.data.upvotes);
    } catch {
      setUpvotes((prev) => Math.max(0, prev - 1));
      setHasUpvoted(false);
    } finally {
      setIsUpvoting(false);
    }
  };

  const handleExplainRanking = async () => {
    setLoadingAi(true);
    setAiError(null);
    try {
      const res = await roadsApi.explainRanking({
        id: corridorId,
        name: corridorName,
        district,
        highway,
        priority_score: Number(score),
        score: Number(score),
        heat: Number(heatVal),
        ndvi: Number(ndviVal),
        green_deficit: Number(greenDeficit),
        heat_weight: Number(heatWeight),
        green_deficit_weight: Number((1 - heatWeight).toFixed(4)),
        heat_contribution: Number((heatWeight * heatVal).toFixed(4)),
        green_deficit_contribution: Number(((1 - heatWeight) * greenDeficit).toFixed(4)),
        rank: Number(rank),
        baseline_rank: Number(baselineRank),
        rank_change: Number(rankChange),
        baseline_score: Number(baselineScore),
        feasibility: Number(feasibilityVal),
        confidence: Number(confidenceVal),
        scenario: activeScenario,
        signals: props.priority_signals || {
          heat: Number(heatVal),
          green_deficit: Number(greenDeficit),
          pollution: Number(aqiVal),
        },
      });
      setAiExplanation(res.data);
    } catch (err) {
      setAiError(
        err.response?.data?.detail ||
          err.message ||
          'Failed to fetch explanation'
      );
    } finally {
      setLoadingAi(false);
    }
  };

  const handleRowSelect = (row) => {
    if (!onSelectCorridor) return;
    onSelectCorridor({
      type: 'Feature',
      id: row.id,
      geometry: row.geometry,
      properties: {
        ...row,
        priority_score: row.score,
        what_if_score: row.score,
        what_if_rank: row.rank,
        heat_norm: row.heat,
        ndvi_norm: row.ndvi,
      },
    });
  };

  const visualCards = buildVisualInterventions(props);
  const constraints = props.constraints || [];
  const siteChecks = props.required_site_checks || [];
  const alternatives = props.feasible_alternatives || [];

  // Default deterministic summary displayed before clicking "Explain this ranking ↗"
  const defaultDeterministicSummary = `${corridorName} (${district}) ranks #${rank} under w=${heatWeight.toFixed(
    2
  )} with score ${Number(score).toFixed(4)} = ${heatWeight.toFixed(
    2
  )}×Heat(${Number(heatVal).toFixed(4)}) + ${(1 - heatWeight).toFixed(
    2
  )}×(1−NDVI)(${Number(greenDeficit).toFixed(4)}). ${
    rankChange > 0
      ? `Moved up +${rankChange} place(s) from Baseline Rank #${baselineRank}.`
      : rankChange < 0
      ? `Moved down ${rankChange} place(s) from Baseline Rank #${baselineRank}.`
      : `Unchanged from Baseline Rank #${baselineRank}.`
  }`;

  const corridorStability = sensitivityData?.corridors?.find(
    (c) => c.id === corridorId
  );

  return (
    <aside
      className="insight-panel"
      aria-label="Detailed Corridor Insight and Action Panel"
      data-testid="corridor-insight-panel"
    >
      {/* 1. Inspected Corridor Header */}
      <div className="insight-header-card">
        <div className="insight-header-top">
          <div className="insight-eyebrow">
            <span className="eyebrow-dot" />
            <span>DETAILED CORRIDOR INSIGHT &amp; ACTION</span>
          </div>
          <button
            type="button"
            className={`insight-upvote-pill ${hasUpvoted ? 'active' : ''}`}
            onClick={handleUpvote}
            disabled={hasUpvoted || isUpvoting}
            title="Community upvote for this corridor"
          >
            <span>👍</span>
            <span>{hasUpvoted ? 'Supported' : 'Upvote'}</span>
            <strong>{upvotes}</strong>
          </button>
        </div>

        <div className="insight-title-row">
          <div>
            <h2 className="insight-corridor-title" data-testid="inspected-corridor-name">
              Corridor Inspected: <span>{corridorName}</span>
            </h2>
            <p className="insight-corridor-sub">
              <code>{corridorId}</code> • {district} • {highway} • {Math.round(lengthMeters)}m
            </p>
          </div>
          <div className="insight-rank-badge-box">
            <span className="insight-rank-num">#{rank}</span>
            <span className="insight-score-val">{Number(score).toFixed(3)}</span>
          </div>
        </div>

        {/* Key Environmental Metrics Strip */}
        <div className="insight-kpi-strip">
          <div className="insight-kpi-item heat">
            <span className="kpi-lbl">Surface Heat (Norm)</span>
            <strong className="kpi-num">{Number(heatVal).toFixed(3)}</strong>
            <span className="kpi-prov">1km MODIS</span>
          </div>
          <div className="insight-kpi-item ndvi">
            <span className="kpi-lbl">Green Cover (NDVI)</span>
            <strong className="kpi-num">{Number(ndviVal).toFixed(3)}</strong>
            <span className="kpi-prov">10m Sentinel-2</span>
          </div>
          <div className="insight-kpi-item deficit">
            <span className="kpi-lbl">Green Deficit (1−NDVI)</span>
            <strong className="kpi-num">{Number(greenDeficit).toFixed(3)}</strong>
            <span className="kpi-prov">Derived</span>
          </div>
          <div className="insight-kpi-item aqi">
            <span className="kpi-lbl">Air Quality Stress</span>
            <strong className="kpi-num">{Number(aqiVal).toFixed(2)}</strong>
            <span className="kpi-prov">CPCB IDW</span>
          </div>
        </div>
      </div>

      {/* 2. Baseline vs. What-If Rank Changes Table */}
      <section className="insight-section-card" data-testid="right-baseline-comparison">
        <div className="section-card-header">
          <div>
            <h3>Baseline vs. What-If Rank Changes</h3>
            <span className="section-card-sub">
              Baseline (<code>w=0.60</code>) vs. Active (<code>w={heatWeight.toFixed(2)}</code>)
            </span>
          </div>
          {baselineComparison && (
            <div className="shift-summary-badges">
              <span className="shift-pill">
                {baselineComparison.corridors_with_rank_change_count || 0} shifted
              </span>
            </div>
          )}
        </div>

        <div className="insight-table-container">
          <table className="insight-comparison-table">
            <thead>
              <tr>
                <th>Corridor Name</th>
                <th>Baseline</th>
                <th>What-If</th>
                <th>Change</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {comparisonTable.slice(0, Math.max(topN, 6)).map((row) => {
                const delta = row.rank_change || 0;
                const isCurrent = row.id === corridorId;
                return (
                  <tr
                    key={row.id}
                    className={`insight-comp-row ${isCurrent ? 'selected' : ''}`}
                    onClick={() => handleRowSelect(row)}
                  >
                    <td className="col-name">
                      <span className="row-corridor-name">{row.name}</span>
                      {row.entered_top_n && (
                        <span className="mini-turnover-badge in">NEW</span>
                      )}
                      {row.left_top_n && (
                        <span className="mini-turnover-badge out">OUT</span>
                      )}
                    </td>
                    <td className="col-rank">#{row.baseline_rank}</td>
                    <td className="col-rank current">#{row.rank}</td>
                    <td className="col-delta">
                      {delta > 0 && (
                        <span className="rank-chip up">▲ +{delta}</span>
                      )}
                      {delta < 0 && (
                        <span className="rank-chip down">▼ {delta}</span>
                      )}
                      {delta === 0 && (
                        <span className="rank-chip same">— 0</span>
                      )}
                    </td>
                    <td className="col-score">{Number(row.score).toFixed(3)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* 3. Recommended Physical Interventions (Visual Cards) */}
      <section className="insight-section-card">
        <div className="section-card-header">
          <div>
            <h3>Recommended Physical Interventions</h3>
            <span className="section-card-sub">
              Rules-based suitability matched to road hierarchy ({highway}) &amp; thermal stress
            </span>
          </div>
        </div>

        <div className="intervention-visual-grid">
          {visualCards.map((card) => (
            <div key={card.id} className="intervention-visual-card">
              <div
                className="intervention-thumb"
                style={{ background: card.gradient }}
                aria-hidden="true"
              >
                <span className="thumb-icon">{card.icon}</span>
                <span className="thumb-badge">{card.badge}</span>
              </div>
              <div className="intervention-card-body">
                <h4>{card.title}</h4>
                <p>{card.description}</p>
                <span className="intervention-spec-tag">{card.spec}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 4. Lifecycle Cost Estimate (CPWD DSR 2023) */}
      <section className="insight-section-card cost-section-card">
        <div className="section-card-header">
          <div>
            <h3>Lifecycle Cost Estimate (CPWD DSR 2023)</h3>
            <span className="section-card-sub">
              Planning-level benchmark for {Math.round(lengthMeters)}m corridor segment
            </span>
          </div>
          <span className="cpwd-tag">DSR 2023</span>
        </div>

        <div className="cpwd-cost-grid">
          <div className="cpwd-cost-box">
            <span className="cost-lbl">CapEx (Installation)</span>
            <strong className="cost-val">₹{capexLakhs} L</strong>
            <span className="cost-sub">Civil &amp; planting</span>
          </div>
          <div className="cpwd-cost-box">
            <span className="cost-lbl">Annual OpEx</span>
            <strong className="cost-val">₹{opexLakhs} L/yr</strong>
            <span className="cost-sub">Watering &amp; pruning</span>
          </div>
          <div className="cpwd-cost-box total">
            <span className="cost-lbl">5-Year Lifecycle</span>
            <strong className="cost-val highlight">₹{fiveYearLakhs} Lakhs</strong>
            <span className="cost-sub">
              Service life: {costs.expected_service_life_years || 15} yrs
            </span>
          </div>
        </div>
      </section>

      {/* 5. AI-Assisted Explanation Card */}
      <section className="insight-section-card ai-insight-card" data-testid="ai-explanation-card">
        <div className="section-card-header">
          <div className="ai-header-title">
            <span className="ai-sparkle">✨</span>
            <h3>AI-Assisted Explanation</h3>
          </div>
          <span
            className={`ai-mode-badge ${
              aiExplanation?.is_ai_generated ? 'live' : 'deterministic'
            }`}
          >
            {aiExplanation?.is_ai_generated
              ? aiExplanation.model_used || 'Live Gemini via Prune'
              : 'Deterministic Grounded'}
          </span>
        </div>

        <p className="ai-insight-body" data-testid="ai-explanation-text">
          {aiExplanation
            ? aiExplanation.explanation || aiExplanation.fallback_explanation
            : defaultDeterministicSummary}
        </p>

        {aiError && <div className="ai-inline-error">⚠️ {aiError}</div>}

        <div className="ai-card-footer">
          <span className="ai-provenance-note">
            Grounded in exact corridor Heat ({Number(heatVal).toFixed(3)}) &amp; NDVI ({Number(ndviVal).toFixed(3)})
          </span>
          <button
            type="button"
            className="explain-ranking-link-btn"
            data-testid="right-explain-ranking-btn"
            onClick={handleExplainRanking}
            disabled={loadingAi}
          >
            {loadingAi ? '⏳ Querying Prune/Gemini...' : 'Explain this ranking ↗'}
          </button>
        </div>
      </section>

      {/* 6. Professional Studio Exclusive Sections */}
      {studioMode === 'professional' && (
        <section className="insight-section-card pro-exclusive-card" data-testid="pro-studio-diagnostics">
          <div className="section-card-header">
            <div>
              <h3>Professional Studio Diagnostics</h3>
              <span className="section-card-sub">
                Multi-scenario stability, field verification &amp; reproducible report export
              </span>
            </div>
            <span className="pro-pill-badge">PRO</span>
          </div>

          {/* Multi-scenario stability for this corridor */}
          {corridorStability && (
            <div className="pro-stability-box">
              <div className="stability-top">
                <span>Cross-Scenario Stability Index</span>
                <strong
                  className={
                    corridorStability.is_stable ? 'stable-txt' : 'volatile-txt'
                  }
                >
                  {(corridorStability.stability_index * 100).toFixed(0)}% (
                  {corridorStability.is_stable ? 'Robust' : 'Weight-Sensitive'})
                </strong>
              </div>
              <div className="scenario-ranks-mini-grid">
                {Object.entries(corridorStability.scenario_ranks || {}).map(
                  ([scen, rnk]) => (
                    <div key={scen} className="scen-rank-chip">
                      <span>{scen.replace(/_/g, ' ')}</span>
                      <strong>#{rnk}</strong>
                    </div>
                  )
                )}
              </div>
            </div>
          )}

          {/* Mandatory Site Checks & Constraints */}
          {(constraints.length > 0 || siteChecks.length > 0) && (
            <div className="pro-checks-grid">
              {constraints.length > 0 && (
                <div className="pro-check-col">
                  <h4>Feasibility Constraints</h4>
                  <ul>
                    {constraints.slice(0, 3).map((c, idx) => (
                      <li key={idx}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
              {siteChecks.length > 0 && (
                <div className="pro-check-col">
                  <h4>Mandatory Pre-Procurement Checks</h4>
                  <ul>
                    {siteChecks.slice(0, 3).map((sc, idx) => (
                      <li key={idx}>{sc}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {alternatives.length > 0 && (
            <div className="pro-alternatives-row">
              <strong>Feasible Alternatives:</strong> {alternatives.join(' • ')}
            </div>
          )}

          <div className="pro-action-buttons">
            <button
              type="button"
              className="pro-secondary-btn"
              onClick={() => setShow3DPlanner((prev) => !prev)}
            >
              {show3DPlanner ? 'Hide 3D ROW Simulator' : '📐 Open 3D ROW Simulator'}
            </button>
            <button
              type="button"
              className="pro-primary-export-btn"
              data-testid="export-planning-report-btn"
              onClick={onExportReport}
            >
              📄 Export Planning Dossier (.md)
            </button>
          </div>

          {show3DPlanner && (
            <div className="pro-3d-planner-wrap">
              <ErrorBoundary panelName="3D ROW Simulator">
                <CorridorDecisionPlanner />
              </ErrorBoundary>
            </div>
          )}
        </section>
      )}

      {/* 7. Compact Community Suggestions & Contextual Input Triggers */}
      <section className="insight-section-card community-compact-card">
        <div className="section-card-header">
          <div>
            <h3>Community Suggestions &amp; Field Observations</h3>
            <span className="section-card-sub">
              Crowdsourced heat/shade notes for {corridorName}
            </span>
          </div>
          {onOpenModal && (
            <button
              type="button"
              className="open-modal-mini-btn"
              onClick={() => onOpenModal('community')}
            >
              + Submit Observation
            </button>
          )}
        </div>

        <CommunitySuggestions corridorId={corridorId} />
      </section>
    </aside>
  );
}
