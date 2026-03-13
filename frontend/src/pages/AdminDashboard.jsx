/**
 * AdminDashboard — Government / Business analytical dashboard
 *
 * Sections:
 *  1. KPI Summary Cards
 *  2. GDI Distribution Chart
 *  3. Zone Comparison
 *  4. Corridor Management Table (with status updates)
 *  5. Community Suggestions Review
 *  6. Data Export
 */
import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import adminApi from '../api/admin';
import './AdminDashboard.css';

/* ===================================================================
   Small reusable pieces
   =================================================================== */

function KpiCard({ label, value, unit, icon, color }) {
  return (
    <div className="kpi-card" style={{ borderTop: `3px solid ${color || 'var(--primary-green)'}` }}>
      <span className="kpi-icon">{icon}</span>
      <div className="kpi-body">
        <span className="kpi-value">
          {value !== null && value !== undefined ? value : '—'}
          {unit && <small className="kpi-unit">{unit}</small>}
        </span>
        <span className="kpi-label">{label}</span>
      </div>
    </div>
  );
}

function DistributionBar({ label, pct, color }) {
  return (
    <div className="dist-row">
      <span className="dist-label">{label}</span>
      <div className="dist-track">
        <div className="dist-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="dist-pct">{pct.toFixed(1)}%</span>
    </div>
  );
}

/* Status badge colors */
const STATUS_COLORS = {
  identified: '#5b8def',
  planned: '#f5a623',
  in_progress: '#91cf60',
  completed: '#1a9850',
  rejected: '#d73027',
};

const STATUS_LABELS = {
  identified: 'Identified',
  planned: 'Planned',
  in_progress: 'In Progress',
  completed: 'Completed',
  rejected: 'Rejected',
};

function StatusBadge({ status }) {
  return (
    <span
      className="status-badge"
      style={{ background: STATUS_COLORS[status] || '#666' }}
    >
      {STATUS_LABELS[status] || status}
    </span>
  );
}

/* ===================================================================
   Main dashboard
   =================================================================== */

export default function AdminDashboard() {
  const [summary, setSummary] = useState(null);
  const [corridors, setCorridors] = useState(null);
  const [zoneStats, setZoneStats] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Status update UI
  const [statusModal, setStatusModal] = useState(null); // { name, currentStatus }
  const [newStatus, setNewStatus] = useState('');
  const [statusNotes, setStatusNotes] = useState('');
  const [updatingStatus, setUpdatingStatus] = useState(false);

  // Active tab
  const [activeTab, setActiveTab] = useState('overview');

  /* ---------- data fetching ---------- */
  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, corRes, zoneRes, sugRes] = await Promise.all([
        adminApi.summary(),
        adminApi.corridors(),
        adminApi.zoneStats(),
        adminApi.allSuggestions(),
      ]);
      setSummary(sumRes.data);
      setCorridors(corRes.data);
      setZoneStats(zoneRes.data);
      setSuggestions(sugRes.data.suggestions || []);
    } catch (err) {
      console.error('Admin fetch error:', err);
      setError('Failed to load dashboard data. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  /* ---------- status update ---------- */
  const handleStatusUpdate = async () => {
    if (!statusModal || !newStatus) return;
    setUpdatingStatus(true);
    try {
      await adminApi.updateStatus(statusModal.name, newStatus, statusNotes || null);
      // Optimistic update
      setCorridors(prev => {
        if (!prev) return prev;
        const updated = { ...prev };
        updated.features = updated.features.map(f => {
          if (f.properties?.name === statusModal.name) {
            return {
              ...f,
              properties: {
                ...f.properties,
                implementation_status: newStatus,
                status_notes: statusNotes || null,
              },
            };
          }
          return f;
        });
        return updated;
      });
      setStatusModal(null);
      setNewStatus('');
      setStatusNotes('');
    } catch (err) {
      console.error('Status update failed:', err);
    } finally {
      setUpdatingStatus(false);
    }
  };

  /* ---------- derived data ---------- */
  const features = (corridors?.features || []).filter(f => {
    const name = f.properties?.name;
    return name && name.toLowerCase() !== 'unnamed';
  });

  // Sort corridors by priority descending, then deduplicate by name (keep highest priority)
  const sortedCorridors = (() => {
    const sorted = [...features].sort((a, b) => {
      const pa = a.properties?.priority_score ?? a.properties?.gdi_mean ?? 0;
      const pb = b.properties?.priority_score ?? b.properties?.gdi_mean ?? 0;
      return pb - pa;
    });
    const seen = new Set();
    return sorted.filter(f => {
      const name = f.properties?.name;
      if (seen.has(name)) return false;
      seen.add(name);
      return true;
    });
  })();

  const gdiDist = summary?.gdi_distribution || {};
  const zones = zoneStats?.zones || {};

  /* ===================================================================
     RENDER
     =================================================================== */
  return (
    <div className="admin-dashboard">
      {/* -------- Header -------- */}
      <header className="admin-header">
        <div className="admin-header-left">
          <span className="admin-logo">🌿</span>
          <div>
            <h1>VanSetu — Admin Dashboard</h1>
            <span className="admin-subtitle">Government &amp; Business Analytics</span>
          </div>
        </div>
        <div className="admin-header-right">
          <Link to="/" className="back-link">← Public Map</Link>
          <button className="refresh-btn" onClick={fetchAll} disabled={loading}>
            {loading ? '⟳ Loading…' : '⟳ Refresh'}
          </button>
        </div>
      </header>

      {/* -------- Tab navigation -------- */}
      <nav className="admin-tabs">
        {['overview', 'corridors', 'suggestions', 'export'].map(tab => (
          <button
            key={tab}
            className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'overview' && '📊 Overview'}
            {tab === 'corridors' && '🛤️ Corridors'}
            {tab === 'suggestions' && '💬 Suggestions'}
            {tab === 'export' && '📥 Export'}
          </button>
        ))}
      </nav>

      {/* -------- Content -------- */}
      <main className="admin-content">
        {error && <div className="admin-error">{error}</div>}

        {loading && !summary ? (
          <div className="admin-loading">Loading dashboard data…</div>
        ) : (
          <>
            {/* ============== OVERVIEW TAB ============== */}
            {activeTab === 'overview' && summary && (
              <div className="tab-panel">
                {/* KPI Cards */}
                <section className="kpi-grid">
                  <KpiCard
                    icon="🛤️" label="Corridor Segments"
                    value={summary.corridors?.total_segments}
                    color="#fc8d59"
                  />
                  <KpiCard
                    icon="📊" label="Mean Priority"
                    value={summary.corridors?.priority_stats?.mean?.toFixed(3)}
                    color="#d73027"
                  />
                  <KpiCard
                    icon="🌿" label="Mean NDVI"
                    value={summary.raster?.ndvi?.mean?.toFixed(3)}
                    color="#1a9850"
                  />
                  <KpiCard
                    icon="🌡️" label="Mean Temp"
                    value={summary.raster?.lst?.mean?.toFixed(1)}
                    unit="°C" color="#fc8d59"
                  />
                  <KpiCard
                    icon="💨" label="Avg PM2.5"
                    value={summary.aqi?.average_pm25}
                    color="#7b3294"
                  />
                  <KpiCard
                    icon="📡" label="AQI Stations"
                    value={summary.aqi?.station_count}
                    color="#5b8def"
                  />
                </section>

                {/* GDI Distribution */}
                <section className="admin-card">
                  <h2>Priority Distribution</h2>
                  <p className="card-desc">Share of pixels in each priority band across the entire raster.</p>
                  <div className="dist-bars">
                    <DistributionBar label="Low (0–0.3)" pct={(gdiDist.low_0_30 || 0) * 100} color="#1a9850" />
                    <DistributionBar label="Moderate (0.3–0.5)" pct={(gdiDist.moderate_30_50 || 0) * 100} color="#fee08b" />
                    <DistributionBar label="High (0.5–0.7)" pct={(gdiDist.high_50_70 || 0) * 100} color="#fc8d59" />
                    <DistributionBar label="Critical (0.7–1.0)" pct={(gdiDist.critical_70_100 || 0) * 100} color="#d73027" />
                  </div>
                </section>

                {/* Zone Comparison */}
                <section className="admin-card">
                  <h2>Zone Comparison</h2>
                  <p className="card-desc">Delhi divided into quadrants — NW, NE, SW, SE.</p>
                  <div className="zone-grid">
                    {Object.entries(zones).map(([zone, data]) => (
                      <div key={zone} className="zone-card">
                        <h3>{zone}</h3>
                        <div className="zone-stat">
                          <span>Mean Priority</span><strong>{data.mean_priority?.toFixed(3)}</strong>
                        </div>
                        <div className="zone-stat">
                          <span>Max Priority</span><strong>{data.max_priority?.toFixed(3)}</strong>
                        </div>
                        <div className="zone-stat">
                          <span>High Priority %</span><strong>{data.high_priority_pct}%</strong>
                        </div>
                        {data.aqi_stations && (
                          <div className="zone-stations">
                            <small>AQI stations: {data.aqi_stations.length}</small>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </section>

                {/* Priority stats box */}
                {summary.corridors?.priority_stats && (
                  <section className="admin-card">
                    <h2>Priority Score Distribution (Corridors)</h2>
                    <div className="priority-stats-grid">
                      {Object.entries(summary.corridors.priority_stats).map(([key, val]) => (
                        <div key={key} className="pstat">
                          <span className="pstat-label">{key.toUpperCase()}</span>
                          <span className="pstat-value">{typeof val === 'number' ? val.toFixed(4) : val}</span>
                        </div>
                      ))}
                    </div>
                  </section>
                )}
              </div>
            )}

            {/* ============== CORRIDORS TAB ============== */}
            {activeTab === 'corridors' && (
              <div className="tab-panel">
                <section className="admin-card full-width">
                  <div className="card-header-row">
                    <h2>Corridor Management ({sortedCorridors.length})</h2>
                  </div>
                  <div className="table-wrap">
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Name</th>
                          <th>Priority</th>
                          <th>Type</th>
                          <th>Heat</th>
                          <th>NDVI</th>
                          <th>AQI</th>
                          <th>Interventions</th>
                          <th>Status</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedCorridors.map((f, idx) => {
                          const p = f.properties || {};
                          const priority = p.priority_score ?? p.gdi_mean ?? 0;
                          return (
                            <tr key={idx}>
                              <td className="cell-num">{idx + 1}</td>
                              <td className="cell-name">{p.name || 'Unnamed'}</td>
                              <td className="cell-priority">
                                <span
                                  className="priority-pill"
                                  style={{ background: priorityColor(priority, corridors?.metadata) }}
                                >
                                  {priority?.toFixed(3)}
                                </span>
                              </td>
                              <td>
                                <span className="type-tag">{p.corridor_type_icon} {formatType(p.corridor_type)}</span>
                              </td>
                              <td>{p.heat_norm?.toFixed(2) ?? '—'}</td>
                              <td>{p.ndvi_norm?.toFixed(2) ?? '—'}</td>
                              <td>{p.aqi_raw ? Math.round(p.aqi_raw) : '—'}</td>
                              <td className="cell-interventions">
                                {(p.recommended_interventions || []).join(', ') || '—'}
                              </td>
                              <td><StatusBadge status={p.implementation_status || 'identified'} /></td>
                              <td>
                                <button
                                  className="action-btn"
                                  onClick={() => {
                                    setStatusModal({ name: p.name, currentStatus: p.implementation_status || 'identified' });
                                    setNewStatus(p.implementation_status || 'identified');
                                    setStatusNotes(p.status_notes || '');
                                  }}
                                >
                                  ✏️
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </section>
              </div>
            )}

            {/* ============== SUGGESTIONS TAB ============== */}
            {activeTab === 'suggestions' && (
              <div className="tab-panel">
                <section className="admin-card full-width">
                  <h2>Community Suggestions ({suggestions.length})</h2>
                  {suggestions.length === 0 ? (
                    <p className="empty-msg">No suggestions yet.</p>
                  ) : (
                    <div className="suggestions-list">
                      {suggestions.map((s, idx) => (
                        <div key={s.id || idx} className="suggestion-row">
                          <div className="sug-text">{s.text}</div>
                          <div className="sug-meta">
                            <span>Corridor: <strong>{s.corridor_id?.slice(0, 8) || '?'}</strong></span>
                            <span>👍 {s.upvotes || 0}</span>
                            <span>{s.created_at ? new Date(s.created_at).toLocaleDateString() : ''}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              </div>
            )}

            {/* ============== EXPORT TAB ============== */}
            {activeTab === 'export' && (
              <div className="tab-panel">
                <section className="admin-card">
                  <h2>Export Corridor Data</h2>
                  <p className="card-desc">
                    Download all corridor segments with priority scores,
                    intervention suggestions, and implementation statuses.
                  </p>
                  <div className="export-buttons">
                    <a
                      className="export-btn geojson"
                      href={adminApi.exportCorridors('geojson')}
                      target="_blank" rel="noopener noreferrer"
                    >
                      📄 Download GeoJSON
                    </a>
                    <a
                      className="export-btn csv"
                      href={adminApi.exportCorridors('csv')}
                      target="_blank" rel="noopener noreferrer"
                    >
                      📊 Download CSV
                    </a>
                  </div>
                </section>
              </div>
            )}
          </>
        )}
      </main>

      {/* -------- Status Update Modal -------- */}
      {statusModal && (
        <div className="modal-overlay" onClick={() => setStatusModal(null)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <h3>Update Status — {statusModal.name || 'Corridor'}</h3>
            <label>
              Status
              <select value={newStatus} onChange={e => setNewStatus(e.target.value)}>
                {Object.entries(STATUS_LABELS).map(([val, label]) => (
                  <option key={val} value={val}>{label}</option>
                ))}
              </select>
            </label>
            <label>
              Notes (optional)
              <textarea
                rows={3}
                maxLength={500}
                value={statusNotes}
                onChange={e => setStatusNotes(e.target.value)}
                placeholder="Implementation notes…"
              />
            </label>
            <div className="modal-actions">
              <button className="modal-cancel" onClick={() => setStatusModal(null)}>Cancel</button>
              <button
                className="modal-save"
                onClick={handleStatusUpdate}
                disabled={updatingStatus}
              >
                {updatingStatus ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ===================================================================
   Helpers
   =================================================================== */

function priorityColor(value, metadata) {
  const pMin = metadata?.priority_min ?? 0.3;
  const pMax = metadata?.priority_max ?? 0.7;
  const range = pMax - pMin || 0.1;
  const t = Math.max(0, Math.min(1, (value - pMin) / range));

  const stops = [
    [26, 152, 80],
    [145, 207, 96],
    [254, 224, 139],
    [252, 141, 89],
    [215, 48, 39],
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

function formatType(type) {
  if (!type) return '—';
  return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}
