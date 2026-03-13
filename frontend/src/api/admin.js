/**
 * Admin API — endpoints for the government / business dashboard
 */
import api from './index';

const adminApi = {
  /** Platform-wide analytics summary */
  summary: () => api.get('/admin/summary'),

  /** All corridors with full breakdown + statuses */
  corridors: (percentile = 85) =>
    api.get('/admin/corridors', { params: { percentile } }),

  /** Update corridor implementation status */
  updateStatus: (corridorName, status, notes = null) =>
    api.post(`/admin/corridors/${encodeURIComponent(corridorName)}/status`, {
      status,
      notes,
    }),

  /** Export corridors as downloadable file */
  exportCorridors: (format = 'geojson', percentile = 85) => {
    const base = api.defaults.baseURL;
    return `${base}/admin/corridors/export?format=${format}&percentile=${percentile}`;
  },

  /** All community suggestions (admin review) */
  allSuggestions: () => api.get('/admin/suggestions'),

  /** Zone-level statistics */
  zoneStats: () => api.get('/admin/zone-stats'),

  /** Subsidy allocation statistics */
  subsidyStats: () => api.get('/admin/subsidy-stats'),

  /** Simulated medical / heat-illness data */
  medicalData: () => api.get('/admin/medical-data'),

  /** Passive / inactive community users */
  passiveUsers: () => api.get('/admin/passive-users'),

  /** Remove a passive user */
  removePassiveUser: (userId) => api.delete(`/admin/passive-users/${userId}`),

  /** Signal coverage for 10-factor scoring */
  signalCoverage: () => api.get('/admin/signal-coverage'),
};

export default adminApi;
