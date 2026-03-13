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
};

export default adminApi;
