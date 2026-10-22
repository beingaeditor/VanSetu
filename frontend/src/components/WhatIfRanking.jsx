/**
 * WhatIfRanking — Interactive What-if Corridor Ranking & Baseline vs. What-if Rank Changes
 *
 * Implements:
 * 1. Mandatory Hackathon Feature:
 *    - GET /api/corridors/rank?heat_weight=0.6&top=5
 *    - Exact formula: score = heat_weight * Heat + (1 - heat_weight) * (1 - NDVI)
 *    - Interactive Heat Weight slider (0.0 to 1.0, default 0.6) + numeric input
 *    - Live display of heat_weight and complementary green-deficit weight (1 - heat_weight)
 *    - Ranked corridor cards with Rank, ID, Name, Score, Heat, NDVI, and map selection
 * 2. In-Scope Novelty:
 *    - "Baseline vs. What-if Rank Changes" panel comparing Baseline (heat_weight = 0.6)
 *      against the current user-selected heat_weight.
 * 3. Isolated "Explain This Ranking" action via Prune AI Gateway + Google Gemini.
 */

import { useState, useEffect, useCallback } from 'react';
import { roadsApi } from '../api';
import './WhatIfRanking.css';

const BASELINE_WEIGHT = 0.6;

export default function WhatIfRanking({ selectedCorridor, onSelectCorridor }) {
  const [heatWeight, setHeatWeight] = useState(0.6);
  const [inputText, setInputText] = useState('0.60');
  const [topN, setTopN] = useState(5);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [validationError, setValidationError] = useState(null);
  const [apiError, setApiError] = useState(null);

  // Isolated Prune + Gemini AI explanation per corridor ID
  const [explanations, setExplanations] = useState({});
  const [explainingId, setExplainingId] = useState(null);

  const fetchWhatIfRanking = useCallback(async (weightVal, topVal) => {
    setLoading(true);
    setApiError(null);
    try {
      const res = await roadsApi.rankWhatIf(weightVal, topVal);
      setData(res.data);
    } catch (err) {
      const detail =
        err.response?.data?.detail ||
        err.message ||
        'Failed to fetch What-if Corridor Ranking';
      setApiError(typeof detail === 'string' ? detail : JSON.stringify(detail));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (validationError === null) {
      fetchWhatIfRanking(heatWeight, topN);
    }
  }, [heatWeight, topN, validationError, fetchWhatIfRanking]);

  const handleSliderChange = (e) => {
    const val = parseFloat(e.target.value);
    setValidationError(null);
    setHeatWeight(val);
    setInputText(val.toFixed(2));
  };

  const handleNumericInputChange = (e) => {
    const raw = e.target.value;
    setInputText(raw);

    if (raw.trim() === '') {
      setValidationError('Heat weight is required (enter a value between 0.0 and 1.0).');
      return;
    }

    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) {
      setValidationError('Heat weight must be a valid finite number between 0.0 and 1.0.');
      return;
    }

    if (parsed < 0.0 || parsed > 1.0) {
      setValidationError(`Heat weight (${parsed}) must be between 0.0 and 1.0 inclusive.`);
      return;
    }

    setValidationError(null);
    setHeatWeight(Number(parsed.toFixed(4)));
  };

  const handlePresetClick = (presetWeight) => {
    setValidationError(null);
    setHeatWeight(presetWeight);
    setInputText(presetWeight.toFixed(2));
  };

  const handleCorridorClick = (corridorItem) => {
    if (!onSelectCorridor) return;
    // Construct a GeoJSON Feature compatible with Map.jsx and InterventionPanel.jsx
    const feature = {
      type: 'Feature',
      id: corridorItem.id,
      geometry: corridorItem.geometry,
      properties: {
        id: corridorItem.id,
        name: corridorItem.name,
        district: corridorItem.district,
        highway: corridorItem.highway,
        length_meters: corridorItem.length_meters,
        priority_score: corridorItem.score,
        gdi_mean: corridorItem.baseline_score,
        heat_norm: corridorItem.heat,
        ndvi_norm: corridorItem.ndvi,
        what_if_score: corridorItem.score,
        what_if_rank: corridorItem.rank,
        baseline_rank: corridorItem.baseline_rank,
        rank_change: corridorItem.rank_change,
        heat_weight: corridorItem.heat_weight,
        green_deficit_weight: corridorItem.green_deficit_weight,
        heat_contribution: corridorItem.heat_contribution,
        green_deficit_contribution: corridorItem.green_deficit_contribution,
        priority_signals: {
          heat: corridorItem.heat,
          green_deficit: corridorItem.green_deficit,
        },
        selection_rationale: `${corridorItem.name}: What-if Rank #${corridorItem.rank} (score ${corridorItem.score.toFixed(4)} = ${corridorItem.heat_weight.toFixed(2)}×Heat(${corridorItem.heat.toFixed(4)}) + ${corridorItem.green_deficit_weight.toFixed(2)}×(1-NDVI)(${corridorItem.green_deficit.toFixed(4)})).`,
      },
    };
    onSelectCorridor(feature);
  };

  const handleExplainClick = async (e, corridorItem) => {
    e.stopPropagation();
    const cid = corridorItem.id;
    setExplainingId(cid);
    try {
      const res = await roadsApi.explainRanking({
        id: cid,
        name: corridorItem.name,
        district: corridorItem.district,
        highway: corridorItem.highway,
        priority_score: corridorItem.score,
        score: corridorItem.score,
        heat: corridorItem.heat,
        ndvi: corridorItem.ndvi,
        green_deficit: corridorItem.green_deficit,
        heat_weight: corridorItem.heat_weight,
        green_deficit_weight: corridorItem.green_deficit_weight,
        heat_contribution: corridorItem.heat_contribution,
        green_deficit_contribution: corridorItem.green_deficit_contribution,
        rank: corridorItem.rank,
        baseline_rank: corridorItem.baseline_rank,
        rank_change: corridorItem.rank_change,
        baseline_score: corridorItem.baseline_score,
        scenario: `what_if_heat_${corridorItem.heat_weight.toFixed(2)}`,
        signals: {
          heat: corridorItem.heat,
          green_deficit: corridorItem.green_deficit,
        },
        active_weights: {
          heat_weight: corridorItem.heat_weight,
          green_deficit_weight: corridorItem.green_deficit_weight,
        },
      });
      setExplanations((prev) => ({
        ...prev,
        [cid]: res.data,
      }));
    } catch (err) {
      setExplanations((prev) => ({
        ...prev,
        [cid]: {
          status: 'error',
          fallback_explanation: `${corridorItem.name} scored ${corridorItem.score.toFixed(4)} (Heat=${corridorItem.heat.toFixed(4)}, NDVI=${corridorItem.ndvi.toFixed(4)}, heat_weight=${corridorItem.heat_weight.toFixed(2)}).`,
        },
      }));
    } finally {
      setExplainingId(null);
    }
  };

  const greenDeficitWeight = Math.max(0, Math.min(1, 1 - heatWeight));
  const corridors = data?.corridors || [];
  const baselineComp = data?.baseline_comparison || null;
  const comparisonRows = baselineComp?.comparison_table || [];
  const selectedId =
    selectedCorridor?.properties?.id || selectedCorridor?.id || null;

  return (
    <div className="whatif-ranking" data-testid="what-if-ranking-panel">
      {/* Formula Banner */}
      <div className="whatif-formula-box">
        <div className="whatif-formula-label">Authoritative What-if Formula</div>
        <code className="whatif-formula-code">
          score = heat_weight &times; Heat + (1 &minus; heat_weight) &times; (1 &minus; NDVI)
        </code>
      </div>

      {/* Controls: Slider + Numeric Input + Live Weights */}
      <div className="whatif-controls-card">
        <div className="whatif-weight-header">
          <label htmlFor="heat-weight-slider" className="whatif-control-title">
            Heat Weight (<code>heat_weight</code>)
          </label>
          <div className="whatif-numeric-group">
            <input
              id="heat-weight-input"
              data-testid="heat-weight-input"
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={inputText}
              onChange={handleNumericInputChange}
              aria-label="Heat weight numeric value"
              className={`whatif-number-input ${validationError ? 'invalid' : ''}`}
            />
          </div>
        </div>

        <input
          id="heat-weight-slider"
          data-testid="heat-weight-slider"
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={heatWeight}
          onChange={handleSliderChange}
          aria-label="Heat weight slider"
          className="whatif-slider"
        />

        <div className="whatif-scale-ticks">
          <span>0.0 (NDVI Deficit Only)</span>
          <span>0.6 (Baseline)</span>
          <span>1.0 (Heat Only)</span>
        </div>

        {/* Live Complementary Weight Pills */}
        <div className="whatif-weight-pills" data-testid="live-weights-display">
          <div className="weight-pill heat-pill">
            <span className="pill-label">Heat Weight</span>
            <strong className="pill-val" data-testid="heat-weight-display">
              {heatWeight.toFixed(2)} ({(heatWeight * 100).toFixed(0)}%)
            </strong>
          </div>
          <div className="weight-pill green-pill">
            <span className="pill-label">Green-Deficit (1 &minus; w)</span>
            <strong className="pill-val" data-testid="green-weight-display">
              {greenDeficitWeight.toFixed(2)} ({(greenDeficitWeight * 100).toFixed(0)}%)
            </strong>
          </div>
        </div>

        {/* Quick Presets + Top N Selector */}
        <div className="whatif-presets-row">
          <div className="preset-buttons">
            <button
              type="button"
              className={`preset-btn ${Math.abs(heatWeight - 0.3) < 0.001 ? 'active' : ''}`}
              onClick={() => handlePresetClick(0.3)}
            >
              0.30 Green
            </button>
            <button
              type="button"
              data-testid="preset-baseline-btn"
              className={`preset-btn ${Math.abs(heatWeight - BASELINE_WEIGHT) < 0.001 ? 'active' : ''}`}
              onClick={() => handlePresetClick(0.6)}
            >
              0.60 Baseline
            </button>
            <button
              type="button"
              data-testid="preset-heat-btn"
              className={`preset-btn ${Math.abs(heatWeight - 0.9) < 0.001 ? 'active' : ''}`}
              onClick={() => handlePresetClick(0.9)}
            >
              0.90 Heat
            </button>
          </div>

          <div className="topn-selector">
            <label htmlFor="whatif-top-select">Top:</label>
            <select
              id="whatif-top-select"
              data-testid="whatif-top-select"
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={15}>15</option>
            </select>
          </div>
        </div>
      </div>

      {/* Validation or API Error States */}
      {validationError && (
        <div className="whatif-error-banner" role="alert" data-testid="whatif-validation-error">
          ⚠️ {validationError}
        </div>
      )}

      {apiError && !validationError && (
        <div className="whatif-error-banner" role="alert" data-testid="whatif-api-error">
          ⚠️ {apiError}
        </div>
      )}

      {loading && (
        <div className="whatif-loading" aria-live="polite">
          Recomputing corridor rankings for <code>heat_weight={heatWeight.toFixed(2)}</code>...
        </div>
      )}

      {/* Ranked Corridors List */}
      {!validationError && !loading && corridors.length === 0 && !apiError && (
        <div className="whatif-empty">No valid corridors found.</div>
      )}

      {!validationError && corridors.length > 0 && (
        <div className="whatif-corridor-list" data-testid="whatif-corridor-list">
          <div className="whatif-list-header">
            <span>Top {corridors.length} Ranked Corridors</span>
            <span className="click-hint">Click to highlight on map</span>
          </div>

          {corridors.map((c) => {
            const isSelected = selectedId === c.id;
            const rankDelta = c.rank_change || 0;
            const totalScore = c.score || 0.0001;
            const heatPct = Math.min(100, Math.max(0, (c.heat_contribution / totalScore) * 100));
            const greenPct = Math.max(0, 100 - heatPct);
            const expData = explanations[c.id];

            return (
              <div
                key={c.id}
                data-testid={`whatif-corridor-item-${c.id}`}
                className={`whatif-card ${isSelected ? 'selected' : ''}`}
                onClick={() => handleCorridorClick(c)}
              >
                <div className="whatif-card-top">
                  <div className="whatif-rank-group">
                    <span className="whatif-rank-badge">#{c.rank}</span>
                    {rankDelta > 0 && (
                      <span className="rank-delta-badge up" title={`Baseline Rank #${c.baseline_rank} → Current #${c.rank}`}>
                        ▲ +{rankDelta}
                      </span>
                    )}
                    {rankDelta < 0 && (
                      <span className="rank-delta-badge down" title={`Baseline Rank #${c.baseline_rank} → Current #${c.rank}`}>
                        ▼ {rankDelta}
                      </span>
                    )}
                    {rankDelta === 0 && (
                      <span className="rank-delta-badge same" title={`Unchanged from Baseline Rank #${c.baseline_rank}`}>
                        = 0
                      </span>
                    )}
                  </div>

                  <div className="whatif-title-group">
                    <div className="whatif-corridor-name">{c.name}</div>
                    <div className="whatif-corridor-meta">
                      <code>{c.id}</code> • {c.district} • {c.highway}
                    </div>
                  </div>

                  <div className="whatif-score-box">
                    <span className="whatif-score-num">{c.score.toFixed(4)}</span>
                    <span className="whatif-score-lbl">Score</span>
                  </div>
                </div>

                {/* Raw Normalized Values: Heat, NDVI, 1-NDVI */}
                <div className="whatif-metrics-row">
                  <div className="metric-chip heat">
                    <span>Heat:</span>
                    <strong>{c.heat.toFixed(4)}</strong>
                  </div>
                  <div className="metric-chip ndvi">
                    <span>NDVI:</span>
                    <strong>{c.ndvi.toFixed(4)}</strong>
                  </div>
                  <div className="metric-chip deficit">
                    <span>1&minus;NDVI:</span>
                    <strong>{c.green_deficit.toFixed(4)}</strong>
                  </div>
                </div>

                {/* Contribution Bar */}
                <div className="whatif-contrib-section">
                  <div className="whatif-contrib-bar">
                    <div
                      className="contrib-segment heat"
                      style={{ width: `${heatPct}%` }}
                      title={`Heat contribution: ${c.heat_contribution.toFixed(4)}`}
                    />
                    <div
                      className="contrib-segment green"
                      style={{ width: `${greenPct}%` }}
                      title={`Green-deficit contribution: ${c.green_deficit_contribution.toFixed(4)}`}
                    />
                  </div>
                  <div className="whatif-contrib-legend">
                    <span>
                      🔥 Heat contrib: <strong>{c.heat_contribution.toFixed(4)}</strong>
                    </span>
                    <span>
                      🌿 Green deficit: <strong>{c.green_deficit_contribution.toFixed(4)}</strong>
                    </span>
                  </div>
                </div>

                {/* Top-N Entry Badge & Explain Button */}
                <div className="whatif-card-actions">
                  {c.entered_top_n ? (
                    <span className="topn-entry-tag entered">★ Entered Top {topN}</span>
                  ) : (
                    <span className="topn-entry-tag retained">
                      Baseline #{c.baseline_rank} ({c.baseline_score.toFixed(4)})
                    </span>
                  )}

                  <button
                    type="button"
                    className="whatif-explain-btn"
                    data-testid={`explain-btn-${c.id}`}
                    onClick={(e) => handleExplainClick(e, c)}
                    disabled={explainingId === c.id}
                  >
                    {explainingId === c.id ? '⏳ Explaining...' : '✨ Explain This Ranking'}
                  </button>
                </div>

                {/* AI Explanation Output (when requested for this corridor) */}
                {expData && (
                  <div
                    className="whatif-ai-box"
                    onClick={(e) => e.stopPropagation()}
                    data-testid={`explanation-box-${c.id}`}
                  >
                    <div className="whatif-ai-header">
                      <strong>✨ Prune / Gemini Explanation</strong>
                      <span className={`whatif-ai-tag ${expData.is_ai_generated ? 'live' : 'fallback'}`}>
                        {expData.is_ai_generated ? (expData.model_used || 'Gemini via Prune') : 'Deterministic'}
                      </span>
                    </div>
                    <p className="whatif-ai-text">
                      {expData.explanation || expData.fallback_explanation}
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Phase 2 Novelty: Baseline vs. What-if Rank Changes Panel */}
      {!validationError && baselineComp && (
        <div className="baseline-comparison-panel" data-testid="baseline-comparison-panel">
          <div className="baseline-panel-header">
            <h4>Baseline vs. What-if Rank Changes</h4>
            <span className="baseline-sub">
              Baseline (<code>w=0.60</code>) vs. Current (<code>w={heatWeight.toFixed(2)}</code>)
            </span>
          </div>

          <div className="baseline-summary-strip">
            <div className="summary-stat">
              <span className="stat-num">{baselineComp.corridors_with_rank_change_count}</span>
              <span className="stat-lbl">Corridors Shifted</span>
            </div>
            <div className="summary-stat">
              <span className="stat-num up">
                {baselineComp.max_rank_gain > 0 ? `+${baselineComp.max_rank_gain}` : '0'}
              </span>
              <span className="stat-lbl">Max Gain</span>
            </div>
            <div className="summary-stat">
              <span className="stat-num down">
                {baselineComp.max_rank_drop < 0 ? `${baselineComp.max_rank_drop}` : '0'}
              </span>
              <span className="stat-lbl">Max Drop</span>
            </div>
          </div>

          {/* Entered / Left Top-N Callouts */}
          {(baselineComp.entered_top_n?.length > 0 || baselineComp.left_top_n?.length > 0) && (
            <div className="topn-turnover-box">
              {baselineComp.entered_top_n?.map((c) => (
                <div key={`in-${c.id}`} className="turnover-item entered">
                  <span>🟢 <strong>Entered Top {topN}:</strong> {c.name} (#{c.baseline_rank} → #{c.rank})</span>
                </div>
              ))}
              {baselineComp.left_top_n?.map((c) => (
                <div key={`out-${c.id}`} className="turnover-item left">
                  <span>🔴 <strong>Left Top {topN}:</strong> {c.name} (#{c.baseline_rank} → #{c.rank})</span>
                </div>
              ))}
            </div>
          )}

          {/* Compact Comparison Table */}
          <div className="baseline-table-wrap">
            <table className="baseline-table">
              <thead>
                <tr>
                  <th>Corridor</th>
                  <th>Base → Curr</th>
                  <th>Δ Rank</th>
                  <th>Base → Curr Score (Δ)</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map((row) => {
                  const rChange = row.rank_change || 0;
                  const sChange = row.score_change || 0;
                  return (
                    <tr
                      key={row.id}
                      className={`comp-row ${row.top_n_status}`}
                      onClick={() => handleCorridorClick(row)}
                    >
                      <td className="comp-name-cell">
                        <div className="comp-road-name">{row.name}</div>
                        <div className="comp-contrib-mini">
                          H:{row.heat_contribution.toFixed(3)} | G:{row.green_deficit_contribution.toFixed(3)}
                        </div>
                      </td>
                      <td className="comp-rank-cell">
                        #{row.baseline_rank} &rarr; <strong>#{row.rank}</strong>
                      </td>
                      <td className="comp-delta-cell">
                        {rChange > 0 && <span className="delta-pill up">+{rChange}</span>}
                        {rChange < 0 && <span className="delta-pill down">{rChange}</span>}
                        {rChange === 0 && <span className="delta-pill same">0</span>}
                      </td>
                      <td className="comp-score-cell">
                        <div>{row.baseline_score.toFixed(3)} &rarr; <strong>{row.score.toFixed(3)}</strong></div>
                        <span className={`score-diff ${sChange >= 0 ? 'pos' : 'neg'}`}>
                          ({sChange >= 0 ? `+${sChange.toFixed(4)}` : sChange.toFixed(4)})
                        </span>
                      </td>
                      <td className="comp-status-cell">
                        {row.entered_top_n && <span className="status-tag entered">Entered</span>}
                        {row.left_top_n && <span className="status-tag left">Left Top {topN}</span>}
                        {!row.entered_top_n && !row.left_top_n && (
                          <span className="status-tag retained">Top {topN}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
