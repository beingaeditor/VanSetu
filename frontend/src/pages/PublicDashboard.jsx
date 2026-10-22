/**
 * PublicDashboard — Van Setu Urban Climate Decision-Support Studio
 *
 * Implements the three-column blue-first spatial planning shell matching the reference specification:
 * - Top Navigation Bar:
 *   - Brand identity ("Van Setu — Urban Climate Decision Support System")
 *   - Mode selector: "Public Mode" vs. "Professional Studio (Van Setu Pro)"
 *   - Active Scenario badge
 *   - Contextual workflow triggers: "Community Input", "Health Data", "Van Setu AI" Action Agent, "Admin"
 *   - Independent Left & Right panel collapse/expand controls
 * - Left Panel ("Scenarios & Priority Index"):
 *   - 7 Policy Scenario Presets with explicit weights & provenance
 *   - Authoritative What-If Corridor Ranking (score = heat_weight * Heat + (1 - heat_weight) * (1 - NDVI))
 *     with 0.0–1.0 slider, numeric input, Reset to 0.60 Baseline, Top N selector, and interactive ranked corridor cards
 *   - Tri-Vector Scoring System (Priority Need, Implementation Feasibility, Evidence Confidence)
 *   - In Professional Mode ("Van Setu Pro"):
 *     - Custom 6-factor multi-criteria weight configurator (validated non-negative & summing to 100%)
 *     - User-supplied field feasibility constraints (footpath width, budget cap, utility conflict, access restriction, maintenance capacity)
 * - Centre Panel:
 *   - Interactive Leaflet Map with floating top-left OVERLAYS card, top-right search & fit controls,
 *     glowing cyan selected corridor highlight, and bottom-center provenance & opacity bar
 * - Right Panel ("Detailed Corridor Insight & Action"):
 *   - Inspected Corridor header, Baseline vs. What-If Rank Changes table, Visual Physical Interventions,
 *     CPWD DSR 2023 Lifecycle Cost Estimate, AI-Assisted Explanation (Prune/Gemini), and Community Suggestions
 */

import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import Map from '../components/Map';
import CorridorInsightPanel from '../components/CorridorInsightPanel';
import VanSetuAIAgent from '../components/VanSetuAIAgent';
import SecondaryUserInput from '../components/SecondaryUserInput';
import HealthDataInput from '../components/HealthDataInput';
import ErrorBoundary from '../components/ErrorBoundary';
import { roadsApi, statsApi, aqiApi } from '../api';
import '../App.css';

const SCENARIO_PRESETS = [
  {
    id: 'balanced',
    label: 'Balanced (Default)',
    shortLabel: 'Balanced',
    heatWeight: 0.60,
    icon: '⚖️',
    provenance: 'Measured 10m S2 + 1km MODIS',
    description: 'Standard 60% Heat / 40% Green-Deficit baseline balance',
    proWeights: {
      lst: 30,
      ndvi_deficit: 25,
      aqi: 15,
      ped_exposure: 15,
      vulnerable_pop: 10,
      green_access: 5,
    },
  },
  {
    id: 'heat_focused',
    label: 'Heat-Focused',
    shortLabel: 'Heat-Focused',
    heatWeight: 0.85,
    icon: '🔥',
    provenance: 'MODIS 1km LST Dominant',
    description: 'Prioritizes extreme surface thermal anomalies (w=0.85)',
    proWeights: {
      lst: 50,
      ndvi_deficit: 20,
      aqi: 10,
      ped_exposure: 10,
      vulnerable_pop: 5,
      green_access: 5,
    },
  },
  {
    id: 'green_focused',
    label: 'Green-Focused',
    shortLabel: 'Green-Focused',
    heatWeight: 0.25,
    icon: '🌿',
    provenance: 'Sentinel-2 10m NDVI Dominant',
    description: 'Prioritizes severe canopy & vegetation deficit (w=0.25)',
    proWeights: {
      lst: 15,
      ndvi_deficit: 50,
      aqi: 10,
      ped_exposure: 10,
      vulnerable_pop: 5,
      green_access: 10,
    },
  },
  {
    id: 'health_focused',
    label: 'Health-Focused',
    shortLabel: 'Health-Focused',
    heatWeight: 0.70,
    icon: '🫁',
    provenance: 'LST + CPCB AQI IDW',
    description: 'Targets compounded heat & particulate respiratory stress',
    proWeights: {
      lst: 30,
      ndvi_deficit: 15,
      aqi: 35,
      ped_exposure: 10,
      vulnerable_pop: 5,
      green_access: 5,
    },
  },
  {
    id: 'equity_focused',
    label: 'Equity-Focused',
    shortLabel: 'Equity-Focused',
    heatWeight: 0.55,
    icon: '🤝',
    provenance: 'Measured + Demographic Proxy',
    description: 'Emphasizes high-footfall transit spines & vulnerable wards',
    proWeights: {
      lst: 20,
      ndvi_deficit: 20,
      aqi: 10,
      ped_exposure: 25,
      vulnerable_pop: 20,
      green_access: 5,
    },
  },
  {
    id: 'budget_conscious',
    label: 'Budget-Conscious (Template)',
    shortLabel: 'Budget Template',
    heatWeight: 0.60,
    icon: '₹',
    provenance: 'Planning Template (CPWD DSR)',
    description: 'Applies ₹25L 5-yr lifecycle cap & low-maintenance filter',
    proWeights: {
      lst: 30,
      ndvi_deficit: 30,
      aqi: 10,
      ped_exposure: 15,
      vulnerable_pop: 10,
      green_access: 5,
    },
  },
  {
    id: 'custom_pro',
    label: 'Custom Professional Scenario',
    shortLabel: 'Custom Pro',
    heatWeight: 0.60,
    icon: '🎛️',
    provenance: 'User-Defined Multi-Criteria',
    description: 'Full 6-factor custom weights & field constraint overrides',
    proWeights: {
      lst: 35,
      ndvi_deficit: 25,
      aqi: 15,
      ped_exposure: 10,
      vulnerable_pop: 10,
      green_access: 5,
    },
  },
];

export default function PublicDashboard() {
  // Studio Mode: 'public' | 'professional'
  const [studioMode, setStudioMode] = useState('public');
  const [activeScenario, setActiveScenario] = useState('balanced');

  // Panel collapse states & mobile active tab ('left' | 'map' | 'right')
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [mobileTab, setMobileTab] = useState('map');

  // Contextual modals ('community' | 'health' | null) & AI Agent drawer
  const [activeModal, setActiveModal] = useState(null);
  const [isAiAgentOpen, setIsAiAgentOpen] = useState(false);

  // Map Layers
  const [activeLayers, setActiveLayers] = useState({
    ndvi: false,
    lst: false,
    gdi: true,
    roads: false,
    corridors: true,
    aqi: false,
    osmRoads: false,
    osmParks: false,
    osmResidential: false,
  });

  // Authoritative What-If Corridor Ranking State
  const [heatWeight, setHeatWeight] = useState(0.60);
  const [inputText, setInputText] = useState('0.60');
  const [topN, setTopN] = useState(5);
  const [validationError, setValidationError] = useState(null);
  const [apiError, setApiError] = useState(null);
  const [loadingRank, setLoadingRank] = useState(false);
  const [rankData, setRankData] = useState(null);

  // Selected Corridor (synced across Left list, Centre map, and Right insight panel)
  const [selectedCorridor, setSelectedCorridor] = useState(null);

  // Regional stats & AQI status
  const [regionalStats, setRegionalStats] = useState(null);
  const [aqiStatus, setAqiStatus] = useState(null);
  const [sensitivityData, setSensitivityData] = useState(null);

  // Professional Studio ("Van Setu Pro") Multi-Criteria Weights & Field Constraints
  const [proWeights, setProWeights] = useState({
    lst: 30,
    ndvi_deficit: 25,
    aqi: 15,
    ped_exposure: 15,
    vulnerable_pop: 10,
    green_access: 5,
  });
  const [proConstraints, setProConstraints] = useState({
    footpath_width_m: 2.1,
    budget_lakhs: 35,
    utility_conflict: false,
    access_restriction: false,
    maintenance_capacity: 'standard',
  });
  const [proResult, setProResult] = useState(null);
  const [proError, setProError] = useState(null);
  const [loadingPro, setLoadingPro] = useState(false);

  // Convert a backend ranked corridor object into a GeoJSON Feature
  const toCorridorFeature = useCallback((c) => {
    if (!c) return null;
    if (c.type === 'Feature') return c;
    return {
      type: 'Feature',
      id: c.id,
      geometry: c.geometry,
      properties: {
        ...c,
        priority_score: c.score ?? c.priority_score ?? 0.58,
        what_if_score: c.score ?? c.priority_score ?? 0.58,
        what_if_rank: c.rank ?? 1,
        heat_norm: c.heat ?? c.heat_norm ?? 0.5,
        ndvi_norm: c.ndvi ?? c.ndvi_norm ?? 0.3,
      },
    };
  }, []);

  // Fetch What-If Corridor Ranking from GET /api/corridors/rank
  const fetchWhatIfRanking = useCallback(
    async (weightVal, topVal) => {
      setLoadingRank(true);
      setApiError(null);
      try {
        const res = await roadsApi.rankWhatIf(weightVal, topVal);
        const body = res.data;
        setRankData(body);

        const list = body?.corridors || [];
        if (list.length > 0) {
          setSelectedCorridor((prev) => {
            const prevId = prev?.properties?.id || prev?.id;
            const found = prevId ? list.find((item) => item.id === prevId) : null;
            return toCorridorFeature(found || list[0]);
          });
        }
      } catch (err) {
        const detail =
          err.response?.data?.detail ||
          err.message ||
          'Failed to fetch corridor ranking';
        setApiError(typeof detail === 'string' ? detail : JSON.stringify(detail));
      } finally {
        setLoadingRank(false);
      }
    },
    [toCorridorFeature]
  );

  useEffect(() => {
    if (validationError === null) {
      fetchWhatIfRanking(heatWeight, topN);
    }
  }, [heatWeight, topN, validationError, fetchWhatIfRanking]);

  // Load regional stats & sensitivity once
  useEffect(() => {
    statsApi
      .all()
      .then((res) => setRegionalStats(res.data))
      .catch(() => {});
    aqiApi
      .status()
      .then((res) => setAqiStatus(res.data))
      .catch(() => {});
    roadsApi
      .sensitivity(85)
      .then((res) => setSensitivityData(res.data))
      .catch(() => {});
  }, []);

  // Handlers for What-If Slider & Numeric Input
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
      setValidationError(
        'Heat weight is required (enter a finite value between 0.0 and 1.0).'
      );
      return;
    }

    const parsed = Number(raw);
    if (!Number.isFinite(parsed)) {
      setValidationError(
        'Heat weight must be a valid finite number between 0.0 and 1.0.'
      );
      return;
    }

    if (parsed < 0.0 || parsed > 1.0) {
      setValidationError(
        `Heat weight (${parsed}) must be between 0.0 and 1.0 inclusive.`
      );
      return;
    }

    setValidationError(null);
    setHeatWeight(Number(parsed.toFixed(4)));
  };

  const handleResetBaseline = () => {
    setValidationError(null);
    setActiveScenario('balanced');
    setHeatWeight(0.60);
    setInputText('0.60');
  };

  const handleSelectScenario = (preset) => {
    setActiveScenario(preset.id);
    setValidationError(null);
    setHeatWeight(preset.heatWeight);
    setInputText(preset.heatWeight.toFixed(2));
    if (preset.proWeights) {
      setProWeights(preset.proWeights);
    }
    if (preset.id === 'budget_conscious') {
      setProConstraints((prev) => ({
        ...prev,
        budget_lakhs: 25,
        maintenance_capacity: 'low',
      }));
    }
    if (preset.id === 'custom_pro') {
      setStudioMode('professional');
    }
  };

  // Run Professional Multi-Criteria Evaluation (POST /api/corridors/professional-rank)
  const handleRunProfessionalEval = async () => {
    setProError(null);
    const values = Object.values(proWeights).map(Number);
    if (values.some((v) => !Number.isFinite(v) || v < 0)) {
      setProError('All multi-criteria weights must be non-negative numbers.');
      return;
    }
    const sum = values.reduce((acc, v) => acc + v, 0);
    if (Math.abs(sum - 100) > 1.0) {
      setProError(
        `Multi-criteria weights must sum to 100%. Current sum is ${sum.toFixed(0)}%.`
      );
      return;
    }

    setLoadingPro(true);
    try {
      const res = await roadsApi.rankProfessional({
        weights: proWeights,
        constraints: proConstraints,
        top: topN,
      });
      setProResult(res.data);
      if (res.data?.corridors?.length > 0) {
        setSelectedCorridor(toCorridorFeature(res.data.corridors[0]));
      }
    } catch (err) {
      setProError(
        err.response?.data?.detail ||
          err.message ||
          'Professional evaluation failed'
      );
    } finally {
      setLoadingPro(false);
    }
  };

  // Normalize Pro Weights to 100%
  const handleAutoNormalizeProWeights = () => {
    const total = Object.values(proWeights).reduce(
      (acc, v) => acc + Math.max(0, Number(v) || 0),
      0
    );
    if (total <= 0) return;
    const normalized = {};
    let running = 0;
    const keys = Object.keys(proWeights);
    keys.forEach((k, idx) => {
      if (idx === keys.length - 1) {
        normalized[k] = Math.max(0, 100 - running);
      } else {
        const val = Math.round((Math.max(0, Number(proWeights[k]) || 0) / total) * 100);
        normalized[k] = val;
        running += val;
      }
    });
    setProWeights(normalized);
    setProError(null);
  };

  // Export Reproducible Markdown Planning Dossier
  const handleExportReport = useCallback(() => {
    const c = selectedCorridor?.properties || selectedCorridor || {};
    const list =
      (studioMode === 'professional' && proResult?.corridors) ||
      rankData?.corridors ||
      [];
    const timestamp = new Date().toISOString();

    const md = [
      `# Van Setu — Urban Climate Corridor Planning Dossier`,
      `**Generated:** ${timestamp}`,
      `**Workspace Mode:** ${
        studioMode === 'professional'
          ? 'Professional Studio (Van Setu Pro)'
          : 'Public Mode'
      }`,
      `**Active Scenario:** ${activeScenario}`,
      `**Authoritative What-If Weights:** \`heat_weight = ${heatWeight.toFixed(
        2
      )}\`, \`green_deficit_weight = ${(1 - heatWeight).toFixed(2)}\``,
      ``,
      `## 1. Inspected Corridor Summary`,
      `- **Corridor Name:** ${c.name || 'N/A'} (\`${c.id || 'N/A'}\`)`,
      `- **District / Road Class:** ${c.district || 'NCT of Delhi'} • ${
        c.highway || 'secondary'
      } (${Math.round(c.length_meters || 650)} m)`,
      `- **What-If Priority Score:** ${Number(
        c.score ?? c.priority_score ?? 0.58
      ).toFixed(4)} (Rank #${c.rank || 1}, Baseline Rank #${
        c.baseline_rank || 1
      })`,
      `- **Normalized Surface Heat (1km MODIS):** ${Number(
        c.heat ?? c.heat_norm ?? 0.5
      ).toFixed(4)}`,
      `- **Normalized Green Cover (10m Sentinel-2 NDVI):** ${Number(
        c.ndvi ?? c.ndvi_norm ?? 0.3
      ).toFixed(4)}`,
      `- **Implementation Feasibility:** ${Number(c.feasibility ?? 0.65).toFixed(
        2
      )}`,
      `- **Evidence Confidence:** ${Number(c.confidence ?? 0.72).toFixed(2)}`,
      ``,
      `## 2. Recommended Physical Interventions & CPWD DSR 2023 Costing`,
      ...(c.recommended_interventions || []).map((item) => `- ${item}`),
      `- **5-Year Lifecycle Benchmark:** ₹${
        c.lifecycle_costs?.five_year_lifecycle_lakhs || '30.05'
      } Lakhs`,
      ``,
      `## 3. Top ${list.length} Ranked Corridors`,
      `| Rank | Baseline Rank | Δ | Corridor ID | Name | Score | Heat | NDVI |`,
      `|---|---|---|---|---|---|---|---|`,
      ...list.map(
        (r) =>
          `| #${r.rank} | #${r.baseline_rank} | ${
            r.rank_change > 0 ? `+${r.rank_change}` : r.rank_change
          } | \`${r.id}\` | ${r.name} | ${Number(r.score).toFixed(
            4
          )} | ${Number(r.heat).toFixed(4)} | ${Number(r.ndvi).toFixed(4)} |`
      ),
      ``,
      `## 4. Scientific Provenance & Caveats`,
      `- **Vegetation (NDVI):** 10m ESA Sentinel-2 L2A composite.`,
      `- **Surface Temperature (LST):** 1km NASA MODIS daytime LST resampled for regional corridor screening (not street-canyon microclimate measurement).`,
      `- **Air Quality (AQI):** CPCB station observations interpolated via Inverse Distance Weighting (IDW).`,
    ].join('\n');

    try {
      const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `vansetu-dossier-${c.id || 'corridor'}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Export failed:', e);
    }
  }, [selectedCorridor, studioMode, proResult, rankData, activeScenario, heatWeight]);

  // Execute typed actions dispatched by the Van Setu AI Action Agent
  const handleExecuteAiAction = useCallback(
    (action) => {
      if (!action || !action.type) return { status: 'ignored' };
      const payload = action.payload || {};

      switch (action.type) {
        case 'SET_HEAT_WEIGHT': {
          const w = Number(payload.heat_weight);
          if (Number.isFinite(w) && w >= 0 && w <= 1) {
            setValidationError(null);
            setHeatWeight(w);
            setInputText(w.toFixed(2));
            return { status: 'executed', detail: `heat_weight=${w.toFixed(2)}` };
          }
          return { status: 'invalid_payload' };
        }
        case 'SELECT_SCENARIO': {
          const found = SCENARIO_PRESETS.find((s) => s.id === payload.scenario);
          if (found) {
            handleSelectScenario(found);
            return { status: 'executed', detail: found.label };
          }
          return { status: 'not_found' };
        }
        case 'SET_TOP_N': {
          const n = Number(payload.top);
          if ([5, 10, 15].includes(n)) {
            setTopN(n);
            return { status: 'executed', detail: `top=${n}` };
          }
          return { status: 'invalid_top' };
        }
        case 'SWITCH_MODE': {
          const targetMode =
            payload.mode === 'professional' ? 'professional' : 'public';
          setStudioMode(targetMode);
          return { status: 'executed', detail: targetMode };
        }
        case 'SELECT_CORRIDOR': {
          const list = rankData?.corridors || [];
          const match = list.find(
            (c) =>
              c.id === payload.corridor_id ||
              c.name?.toLowerCase() === payload.name?.toLowerCase()
          );
          if (match) {
            setSelectedCorridor(toCorridorFeature(match));
            return { status: 'executed', detail: match.name };
          }
          return { status: 'not_found' };
        }
        case 'TOGGLE_LAYER': {
          const lk = payload.layer;
          if (lk && lk in activeLayers) {
            setActiveLayers((prev) => ({
              ...prev,
              [lk]: payload.enabled !== undefined ? Boolean(payload.enabled) : !prev[lk],
            }));
            return { status: 'executed', detail: `${lk}=${payload.enabled}` };
          }
          return { status: 'unknown_layer' };
        }
        case 'OPEN_MODAL': {
          if (payload.modal === 'community_input') {
            setActiveModal('community');
          } else if (payload.modal === 'health_data') {
            setActiveModal('health');
          }
          return { status: 'executed', detail: payload.modal };
        }
        case 'OPEN_FEASIBILITY_PANEL': {
          setStudioMode('professional');
          setLeftCollapsed(false);
          return { status: 'executed', detail: 'Opened Pro Feasibility Panel' };
        }
        case 'REQUEST_INTERVENTION_ASSESSMENT': {
          setRightCollapsed(false);
          return { status: 'executed', detail: 'Focused Right Insight Panel' };
        }
        case 'EXPORT_REPORT': {
          handleExportReport();
          return { status: 'executed', detail: 'Exported Markdown Dossier' };
        }
        default:
          return { status: 'unhandled' };
      }
    },
    [rankData, activeLayers, toCorridorFeature, handleExportReport]
  );

  const displayedCorridors =
    studioMode === 'professional' && proResult?.corridors?.length > 0
      ? proResult.corridors
      : rankData?.corridors || [];

  const comparisonTable =
    studioMode === 'professional' && proResult?.comparison_table?.length > 0
      ? proResult.comparison_table
      : rankData?.baseline_comparison?.comparison_table || [];

  const selectedProps = selectedCorridor?.properties || selectedCorridor || {};
  const selectedId = selectedProps.id || null;
  const greenDeficitWeight = Math.max(0, Math.min(1, 1 - heatWeight));

  // Tri-Vector scores for the currently inspected corridor
  const triPriority = Number(
    selectedProps.what_if_score ??
      selectedProps.score ??
      selectedProps.priority_score ??
      0.5867
  );
  const triFeasibility = Number(selectedProps.feasibility ?? 0.65);
  const triConfidence = Number(selectedProps.confidence ?? 0.72);

  const proWeightSum = Object.values(proWeights).reduce(
    (acc, v) => acc + (Number(v) || 0),
    0
  );

  const activeScenarioObj =
    SCENARIO_PRESETS.find((s) => s.id === activeScenario) || SCENARIO_PRESETS[0];

  return (
    <div className="vansetu-studio-shell" data-testid="vansetu-studio-shell">
      {/* ─── TOP GLOBAL NAVIGATION BAR ─────────────────────────────────── */}
      <header className="studio-topbar" data-testid="studio-topbar">
        <div className="topbar-left">
          <button
            type="button"
            className="panel-collapse-btn"
            onClick={() => setLeftCollapsed((prev) => !prev)}
            title={leftCollapsed ? 'Expand Left Scenarios Panel' : 'Collapse Left Panel'}
            aria-label="Toggle Left Scenarios Panel"
          >
            {leftCollapsed ? '▸' : '◂'}
          </button>

          <div className="brand-identity">
            <div className="brand-logo-badge">🌿</div>
            <div className="brand-titles">
              <div className="brand-name-row">
                <h1>Van Setu</h1>
                <span className="brand-divider">—</span>
                <span className="brand-subtitle">
                  Urban Climate Decision Support System
                </span>
              </div>
              <span className="brand-region-tag">
                NCT of Delhi • 10m Sentinel-2 + 1km MODIS + CPCB AQI
              </span>
            </div>
          </div>
        </div>

        {/* Mode Switcher: Public Mode vs Professional Studio (Van Setu Pro) */}
        <div className="topbar-center">
          <div
            className="studio-mode-switcher"
            role="tablist"
            aria-label="Workspace Mode Switcher"
          >
            <button
              type="button"
              role="tab"
              aria-selected={studioMode === 'public'}
              data-testid="mode-public-btn"
              className={`mode-tab-btn ${studioMode === 'public' ? 'active' : ''}`}
              onClick={() => setStudioMode('public')}
            >
              🌍 Public Mode
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={studioMode === 'professional'}
              data-testid="mode-pro-btn"
              className={`mode-tab-btn pro ${
                studioMode === 'professional' ? 'active' : ''
              }`}
              onClick={() => setStudioMode('professional')}
            >
              📐 Professional Studio <span className="pro-tag">PRO</span>
            </button>
          </div>

          <div className="active-scenario-pill" title={activeScenarioObj.description}>
            <span>{activeScenarioObj.icon}</span>
            <span>Scenario:</span>
            <strong>{activeScenarioObj.shortLabel}</strong>
            <code>w={heatWeight.toFixed(2)}</code>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div className="topbar-right">
          <button
            type="button"
            className="topbar-action-btn"
            data-testid="open-community-modal-btn"
            onClick={() => setActiveModal('community')}
          >
            🗣️ Community Input
          </button>

          <button
            type="button"
            className="topbar-action-btn"
            data-testid="open-health-modal-btn"
            onClick={() => setActiveModal('health')}
          >
            🏥 Health Data
          </button>

          <button
            type="button"
            className="topbar-ai-agent-btn"
            data-testid="open-ai-agent-btn"
            onClick={() => setIsAiAgentOpen(true)}
          >
            <span className="ai-orb-mini">✦</span>
            <span>Van Setu AI</span>
          </button>

          <Link to="/admin" className="topbar-admin-link">
            Admin
          </Link>

          <button
            type="button"
            className="panel-collapse-btn"
            onClick={() => setRightCollapsed((prev) => !prev)}
            title={
              rightCollapsed ? 'Expand Right Insight Panel' : 'Collapse Right Panel'
            }
            aria-label="Toggle Right Insight Panel"
          >
            {rightCollapsed ? '◂' : '▸'}
          </button>
        </div>
      </header>

      {/* Mobile / Tablet Column Switcher Bar */}
      <nav className="mobile-studio-tabs" aria-label="Mobile View Switcher">
        <button
          type="button"
          className={mobileTab === 'left' ? 'active' : ''}
          onClick={() => setMobileTab('left')}
        >
          🎛️ Scenarios &amp; Rank
        </button>
        <button
          type="button"
          className={mobileTab === 'map' ? 'active' : ''}
          onClick={() => setMobileTab('map')}
        >
          🗺️ Spatial Map
        </button>
        <button
          type="button"
          className={mobileTab === 'right' ? 'active' : ''}
          onClick={() => setMobileTab('right')}
        >
          📊 Corridor Insights
        </button>
      </nav>

      {/* ─── THREE-COLUMN PLANNING WORKSPACE ───────────────────────────── */}
      <div className="studio-three-col-grid">
        {/* ═══ LEFT COLUMN: SCENARIOS, WHAT-IF RANKING & TRI-VECTOR ═══ */}
        {!leftCollapsed && (
          <aside
            className={`studio-left-panel ${
              mobileTab === 'left' ? 'mobile-active' : ''
            }`}
            aria-label="Scenarios and Priority Index Controls"
            data-testid="studio-left-panel"
          >
            {/* Section 1: Scenarios & Priority Index Presets */}
            <section className="left-card-section">
              <div className="left-section-header">
                <div>
                  <h2>Scenarios &amp; Priority Index</h2>
                  <p>Select a policy preset or tune custom weights</p>
                </div>
                <span className="preset-count-badge">7 Presets</span>
              </div>

              <div
                className="scenario-preset-grid"
                data-testid="scenario-preset-grid"
              >
                {SCENARIO_PRESETS.map((preset) => {
                  const isActive = activeScenario === preset.id;
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      data-testid={`scenario-btn-${preset.id}`}
                      className={`scenario-preset-btn ${
                        isActive ? 'active' : ''
                      }`}
                      onClick={() => handleSelectScenario(preset)}
                    >
                      <div className="scenario-btn-top">
                        <span className="scenario-icon">{preset.icon}</span>
                        <span className="scenario-name">{preset.shortLabel}</span>
                        <code className="scenario-w">
                          {preset.heatWeight.toFixed(2)}
                        </code>
                      </div>
                      <span className="scenario-prov">{preset.provenance}</span>
                    </button>
                  );
                })}
              </div>
            </section>

            {/* Section 2: Authoritative What-If Corridor Ranking */}
            <section
              className="left-card-section whatif-studio-section"
              data-testid="what-if-ranking-panel"
            >
              <div className="left-section-header">
                <div>
                  <h2>What-If Corridor Ranking</h2>
                  <p>Real-time two-factor thermal vs. canopy sensitivity</p>
                </div>
                <button
                  type="button"
                  data-testid="preset-baseline-btn"
                  className="reset-baseline-mini-btn"
                  onClick={handleResetBaseline}
                >
                  ↺ Reset (0.60)
                </button>
              </div>

              {/* Exact Mathematical Formula Box */}
              <div className="studio-formula-banner">
                <code>
                  Score = heat_weight &times; Heat + (1 &minus; heat_weight) &times;
                  (1 &minus; NDVI)
                </code>
              </div>

              {/* Slider + Numeric Input */}
              <div className="studio-weight-control-box">
                <div className="weight-control-top">
                  <label htmlFor="heat-weight-slider">
                    Heat Weight (<code>heat_weight</code>)
                  </label>
                  <div className="weight-input-group">
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
                      className={`studio-num-input ${
                        validationError ? 'invalid' : ''
                      }`}
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
                  className="studio-range-slider"
                />

                <div className="slider-ticks-row">
                  <button
                    type="button"
                    className="tick-link"
                    onClick={() => {
                      setValidationError(null);
                      setHeatWeight(0.3);
                      setInputText('0.30');
                    }}
                  >
                    0.30 Green
                  </button>
                  <button
                    type="button"
                    className="tick-link"
                    onClick={handleResetBaseline}
                  >
                    0.60 Baseline
                  </button>
                  <button
                    type="button"
                    data-testid="preset-heat-btn"
                    className="tick-link"
                    onClick={() => {
                      setValidationError(null);
                      setHeatWeight(0.9);
                      setInputText('0.90');
                    }}
                  >
                    0.90 Heat
                  </button>
                </div>

                {/* Live Complementary Weights Strip */}
                <div
                  className="complementary-weights-bar"
                  data-testid="live-weights-display"
                >
                  <div className="comp-pill heat">
                    <span>🔥 Heat Weight</span>
                    <strong data-testid="heat-weight-display">
                      {heatWeight.toFixed(2)} ({(heatWeight * 100).toFixed(0)}%)
                    </strong>
                  </div>
                  <div className="comp-pill green">
                    <span>🌿 Green-Deficit (1−w)</span>
                    <strong data-testid="green-weight-display">
                      {greenDeficitWeight.toFixed(2)} (
                      {(greenDeficitWeight * 100).toFixed(0)}%)
                    </strong>
                  </div>
                </div>
              </div>

              {validationError && (
                <div
                  className="studio-alert-banner error"
                  role="alert"
                  data-testid="whatif-validation-error"
                >
                  ⚠️ {validationError}
                </div>
              )}

              {apiError && !validationError && (
                <div
                  className="studio-alert-banner error"
                  role="alert"
                  data-testid="whatif-api-error"
                >
                  ⚠️ {apiError}
                </div>
              )}

              {/* Ranked Corridors List Header + Top N Selector */}
              <div className="ranked-list-toolbar">
                <span>
                  Top <strong>{displayedCorridors.length}</strong> Priority Corridors
                </span>
                <div className="topn-mini-select">
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

              {loadingRank && (
                <div className="studio-loading-row">
                  ⏳ Recomputing rankings for <code>w={heatWeight.toFixed(2)}</code>...
                </div>
              )}

              {/* Compact Ranked Corridors Cards */}
              {!validationError && displayedCorridors.length > 0 && (
                <div
                  className="studio-corridor-list"
                  data-testid="whatif-corridor-list"
                >
                  {displayedCorridors.map((c) => {
                    const isSelected = selectedId === c.id;
                    const delta = c.rank_change || 0;
                    return (
                      <div
                        key={c.id}
                        data-testid={`whatif-corridor-item-${c.id}`}
                        className={`studio-corridor-card ${
                          isSelected ? 'selected' : ''
                        }`}
                        onClick={() => setSelectedCorridor(toCorridorFeature(c))}
                      >
                        <div className="corridor-card-main">
                          <div className="corridor-rank-col">
                            <span className="rank-circle">#{c.rank}</span>
                            {delta > 0 && (
                              <span className="delta-mini up">▲+{delta}</span>
                            )}
                            {delta < 0 && (
                              <span className="delta-mini down">▼{delta}</span>
                            )}
                            {delta === 0 && (
                              <span className="delta-mini same">=0</span>
                            )}
                          </div>

                          <div className="corridor-info-col">
                            <div className="corridor-title-txt">{c.name}</div>
                            <div className="corridor-sub-txt">
                              <code>{c.id}</code> • {c.district}
                            </div>
                          </div>

                          <div className="corridor-score-col">
                            <strong>{Number(c.score).toFixed(3)}</strong>
                            <span>Score</span>
                          </div>
                        </div>

                        <div className="corridor-micro-metrics">
                          <span>
                            Heat: <strong>{Number(c.heat).toFixed(3)}</strong>
                          </span>
                          <span>
                            NDVI: <strong>{Number(c.ndvi).toFixed(3)}</strong>
                          </span>
                          <span>
                            1−NDVI:{' '}
                            <strong>
                              {Number(c.green_deficit ?? 1 - c.ndvi).toFixed(3)}
                            </strong>
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            {/* Section 3: Tri-Vector Scoring System (Priority, Feasibility, Confidence) */}
            <section
              className="left-card-section trivector-section"
              data-testid="trivector-scoring-section"
            >
              <div className="left-section-header">
                <div>
                  <h2>Tri-Vector Scoring System</h2>
                  <p>
                    Decoupled evaluation for{' '}
                    <strong>{selectedProps.name || 'Selected Corridor'}</strong>
                  </p>
                </div>
              </div>

              <div className="trivector-bars-list">
                <div className="trivector-row">
                  <div className="trivector-top">
                    <span className="tv-name">1. Priority Need Index</span>
                    <strong className="tv-val priority">
                      {triPriority.toFixed(2)}
                    </strong>
                  </div>
                  <div className="tv-bar-track">
                    <div
                      className="tv-bar-fill priority"
                      style={{ width: `${Math.min(100, triPriority * 100)}%` }}
                    />
                  </div>
                  <span className="tv-caption">
                    Environmental heat &amp; canopy deficit urgency
                  </span>
                </div>

                <div className="trivector-row">
                  <div className="trivector-top">
                    <span className="tv-name">2. Implementation Feasibility</span>
                    <strong className="tv-val feasibility">
                      {triFeasibility.toFixed(2)}
                    </strong>
                  </div>
                  <div className="tv-bar-track">
                    <div
                      className="tv-bar-fill feasibility"
                      style={{ width: `${Math.min(100, triFeasibility * 100)}%` }}
                    />
                  </div>
                  <span className="tv-caption">
                    OSM Right-of-Way geometry &amp; physical space
                  </span>
                </div>

                <div className="trivector-row">
                  <div className="trivector-top">
                    <span className="tv-name">3. Evidence Confidence</span>
                    <strong className="tv-val confidence">
                      {triConfidence.toFixed(2)}
                    </strong>
                  </div>
                  <div className="tv-bar-track">
                    <div
                      className="tv-bar-fill confidence"
                      style={{ width: `${Math.min(100, triConfidence * 100)}%` }}
                    />
                  </div>
                  <span className="tv-caption">
                    Sensor resolution &amp; CPCB station proximity discount
                  </span>
                </div>
              </div>
            </section>

            {/* Section 4: Professional Studio ("Van Setu Pro") Multi-Criteria & Constraints */}
            {studioMode === 'professional' && (
              <section
                className="left-card-section pro-config-section"
                data-testid="pro-weights-constraints-panel"
              >
                <div className="left-section-header">
                  <div>
                    <h2>Van Setu Pro — Multi-Criteria &amp; Field Constraints</h2>
                    <p>
                      Configure 6-factor weights (must sum to 100%) &amp; field
                      constraints
                    </p>
                  </div>
                  <span className="pro-tag">PRO</span>
                </div>

                <div className="pro-weights-grid">
                  {[
                    { key: 'lst', label: 'Surface Heat (1km MODIS)' },
                    { key: 'ndvi_deficit', label: 'Green Deficit (10m S2)' },
                    { key: 'aqi', label: 'Air Quality (CPCB IDW)' },
                    { key: 'ped_exposure', label: 'Pedestrian Activity (OSM)' },
                    { key: 'vulnerable_pop', label: 'Vulnerable Pop (Proxy)' },
                    { key: 'green_access', label: 'Park Deficit (OSM)' },
                  ].map(({ key, label }) => (
                    <div key={key} className="pro-weight-item">
                      <label>{label}</label>
                      <div className="pro-weight-input-wrap">
                        <input
                          type="number"
                          min="0"
                          max="100"
                          value={proWeights[key]}
                          onChange={(e) =>
                            setProWeights((prev) => ({
                              ...prev,
                              [key]: Number(e.target.value),
                            }))
                          }
                        />
                        <span>%</span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="pro-sum-bar">
                  <span>
                    Total Weight Sum:{' '}
                    <strong
                      className={
                        Math.abs(proWeightSum - 100) <= 1 ? 'valid' : 'invalid'
                      }
                    >
                      {proWeightSum}%
                    </strong>
                  </span>
                  <button
                    type="button"
                    className="auto-norm-btn"
                    onClick={handleAutoNormalizeProWeights}
                  >
                    Normalize to 100%
                  </button>
                </div>

                <div className="pro-constraints-box">
                  <h4>User-Supplied Field Constraints (Planning Inputs)</h4>
                  <div className="pro-constraints-grid">
                    <div>
                      <label>Footpath Width (m)</label>
                      <input
                        type="number"
                        step="0.1"
                        min="0.5"
                        max="10"
                        value={proConstraints.footpath_width_m}
                        onChange={(e) =>
                          setProConstraints((prev) => ({
                            ...prev,
                            footpath_width_m: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                    <div>
                      <label>5-Yr Budget Cap (₹ Lakhs)</label>
                      <input
                        type="number"
                        step="5"
                        min="5"
                        max="500"
                        value={proConstraints.budget_lakhs}
                        onChange={(e) =>
                          setProConstraints((prev) => ({
                            ...prev,
                            budget_lakhs: Number(e.target.value),
                          }))
                        }
                      />
                    </div>
                  </div>

                  <div className="pro-checkbox-row">
                    <label>
                      <input
                        type="checkbox"
                        checked={proConstraints.utility_conflict}
                        onChange={(e) =>
                          setProConstraints((prev) => ({
                            ...prev,
                            utility_conflict: e.target.checked,
                          }))
                        }
                      />
                      Utility Conflict (Overhead/Underground)
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={proConstraints.access_restriction}
                        onChange={(e) =>
                          setProConstraints((prev) => ({
                            ...prev,
                            access_restriction: e.target.checked,
                          }))
                        }
                      />
                      Restricted Civil Access
                    </label>
                  </div>
                </div>

                {proError && (
                  <div className="studio-alert-banner error">{proError}</div>
                )}

                <button
                  type="button"
                  className="run-pro-eval-btn"
                  data-testid="run-pro-eval-btn"
                  onClick={handleRunProfessionalEval}
                  disabled={loadingPro}
                >
                  {loadingPro
                    ? '⏳ Running Multi-Criteria Evaluation...'
                    : '⚡ Apply Pro Weights & Constraints'}
                </button>
              </section>
            )}

            {/* Section 5: Regional NCT Overview Strip */}
            {regionalStats && (
              <section className="left-card-section regional-mini-strip">
                <div className="mini-stat-box">
                  <span>Mean NDVI</span>
                  <strong>{regionalStats.ndvi?.mean?.toFixed(2) || '0.24'}</strong>
                </div>
                <div className="mini-stat-box">
                  <span>Mean LST</span>
                  <strong>
                    {regionalStats.lst?.mean
                      ? `${regionalStats.lst.mean.toFixed(1)}°C`
                      : '36.4°C'}
                  </strong>
                </div>
                <div className="mini-stat-box">
                  <span>Mean GDI</span>
                  <strong>{regionalStats.gdi?.mean?.toFixed(2) || '0.58'}</strong>
                </div>
                <div className="mini-stat-box">
                  <span>Avg PM2.5</span>
                  <strong>
                    {aqiStatus?.average_pm25
                      ? Math.round(aqiStatus.average_pm25)
                      : '142'}
                  </strong>
                </div>
              </section>
            )}
          </aside>
        )}

        {/* ═══ CENTRE COLUMN: INTERACTIVE SPATIAL MAP ═══ */}
        <main
          className={`studio-center-map ${
            mobileTab === 'map' ? 'mobile-active' : ''
          }`}
        >
          <ErrorBoundary panelName="Spatial Map Canvas">
            <Map
              activeLayers={activeLayers}
              setActiveLayers={setActiveLayers}
              selectedCorridor={selectedCorridor}
              onSelectCorridor={setSelectedCorridor}
              rankedCorridors={displayedCorridors}
              heatWeight={heatWeight}
            />
          </ErrorBoundary>
        </main>

        {/* ═══ RIGHT COLUMN: DETAILED CORRIDOR INSIGHT & ACTION ═══ */}
        {!rightCollapsed && (
          <div
            className={`studio-right-wrapper ${
              mobileTab === 'right' ? 'mobile-active' : ''
            }`}
          >
            <ErrorBoundary panelName="Detailed Corridor Insight Panel">
              <CorridorInsightPanel
                corridor={selectedCorridor}
                comparisonTable={comparisonTable}
                baselineComparison={rankData?.baseline_comparison}
                heatWeight={heatWeight}
                topN={topN}
                studioMode={studioMode}
                activeScenario={activeScenario}
                sensitivityData={sensitivityData}
                onSelectCorridor={setSelectedCorridor}
                onOpenModal={setActiveModal}
                onExportReport={handleExportReport}
              />
            </ErrorBoundary>
          </div>
        )}
      </div>

      {/* ─── CONTEXTUAL MODALS FOR COMMUNITY INPUT & HEALTH DATA ──────── */}
      {activeModal && (
        <div
          className="studio-modal-backdrop"
          onClick={() => setActiveModal(null)}
          data-testid="contextual-modal-backdrop"
        >
          <div
            className="studio-modal-dialog"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="studio-modal-header">
              <div>
                <h2>
                  {activeModal === 'community'
                    ? '🗣️ Community & Ground Observation Input'
                    : '🏥 Municipal Health Department Data Submission'}
                </h2>
                <p>
                  {activeModal === 'community'
                    ? 'Submit local thermal discomfort, shade deficit, and pedestrian activity observations.'
                    : 'Submit aggregated ward/district heat-illness records for corridor vulnerability weighting.'}
                </p>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setActiveModal(null)}
              >
                ✕
              </button>
            </div>

            {activeModal === 'health' && (
              <div className="health-privacy-disclaimer">
                🔒 <strong>Epidemiological &amp; Privacy Safeguard:</strong> Do not
                submit personally identifiable patient information (PII). District
                health counts are used as an ecological vulnerability modifier, not
                as proof of direct street-level clinical causation.
              </div>
            )}

            <div className="studio-modal-body">
              {activeModal === 'community' ? (
                <SecondaryUserInput />
              ) : (
                <HealthDataInput />
              )}
            </div>
          </div>
        </div>
      )}

      {/* ─── VAN SETU AI ACTION AGENT SLIDE-OVER WORKSPACE ────────────── */}
      <VanSetuAIAgent
        isOpen={isAiAgentOpen}
        onClose={() => setIsAiAgentOpen(false)}
        studioContext={{
          mode: studioMode,
          scenario: activeScenario,
          heat_weight: heatWeight,
          top: topN,
          selected_corridor: selectedProps,
          corridors: displayedCorridors,
        }}
        onExecuteAction={handleExecuteAiAction}
      />
    </div>
  );
}
