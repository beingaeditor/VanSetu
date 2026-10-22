/**
 * API Service — Centralized API client for the VanSetu platform.
 * Supports multi-criteria priority, feasibility, confidence, sensitivity analysis, and provenance.
 */
import axios from 'axios';

function resolveApiBase() {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL.replace(/\/$/, '');
  }
  if (import.meta.env.VITE_API_BASE_URL) {
    const base = import.meta.env.VITE_API_BASE_URL.replace(/\/$/, '');
    return base.endsWith('/api') ? base : `${base}/api`;
  }
  return 'http://localhost:8000/api';
}

const API_BASE = resolveApiBase();

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

/**
 * Layer endpoints
 */
export const layersApi = {
  list: () => api.get('/layers'),
  get: (layerId) => api.get(`/layers/${layerId}`),
  metadata: () => api.get('/layers/metadata'),
};

/**
 * Statistics endpoints
 */
export const statsApi = {
  all: () => api.get('/stats'),
  layer: (layerId) => api.get(`/stats/${layerId}`),
  histogram: (layerId, bins = 50) => api.get(`/stats/${layerId}/histogram`, { params: { bins } }),
  point: (lat, lng) => api.get('/point', { params: { lat, lng } }),
};

/**
 * Roads and Corridors endpoints
 */
export const roadsApi = {
  simple: () => api.get('/roads/simple'),
  withGdi: (includeAqi = true, scenario = 'balanced') => api.get('/roads', {
    params: { include_aqi: includeAqi, scenario }
  }),
  corridors: (percentile = 85, includeAqi = true, scenario = 'balanced') => api.get('/corridors', {
    params: { percentile, include_aqi: includeAqi, scenario }
  }),
  priorityRanking: (percentile = 85, scenario = 'balanced') => api.get('/corridors/priority-ranking', {
    params: { percentile, scenario }
  }),
  rankWhatIf: (heatWeight, top = 5) => api.get('/corridors/rank', {
    params: { heat_weight: heatWeight, top }
  }),
  sensitivity: (percentile = 85) => api.get('/corridors/sensitivity', {
    params: { percentile }
  }),
  explainRanking: (data) => api.post('/corridors/explain-ranking', data),
};

/**
 * Aggregated Corridors endpoints
 */
export const corridorsApi = {
  aggregated: (dMax = 30, nMin = 5, percentile = 85) => api.get('/corridors/aggregated', {
    params: { d_max: dMax, n_min: nMin, percentile }
  }),
  detail: (corridorId, includePoints = true) => api.get(`/corridors/aggregated/${corridorId}`, {
    params: { include_points: includePoints }
  }),
  points: (percentile = 85, includeAll = false) => api.get('/corridors/points', {
    params: { percentile, include_all: includeAll }
  }),
  stats: () => api.get('/corridors/stats'),
};

/**
 * AQI endpoints
 */
export const aqiApi = {
  stations: () => api.get('/aqi/stations'),
  status: () => api.get('/aqi/status'),
  atPoint: (lat, lng) => api.get('/aqi/point', { params: { lat, lng } }),
  refresh: () => api.post('/aqi/refresh'),
};

/**
 * Community Suggestions endpoints
 */
export const suggestionsApi = {
  list: (corridorId) => api.get(`/corridors/${corridorId}/suggestions`),
  create: (corridorId, text) => api.post(`/corridors/${corridorId}/suggestions`, { text }),
  upvoteCorridor: (corridorId) => api.post(`/corridors/${corridorId}/upvote`),
  getCorridorUpvotes: (corridorId) => api.get(`/corridors/${corridorId}/upvotes`),
  stats: (corridorId) => api.get(`/corridors/${corridorId}/suggestions/stats`),
};

/**
 * Health Data endpoints
 */
export const healthApi = {
  submit: (data) => api.post('/health-data', data),
  byDistrict: (district) => api.get(`/health-data/${encodeURIComponent(district)}`),
  all: () => api.get('/health-data'),
};

/**
 * Community / Environmental Data endpoints
 */
export const communityDataApi = {
  submit: (data) => api.post('/community-data', data),
  all: (status) => api.get('/community-data', { params: { status } }),
};

/**
 * Tile URL template for Leaflet
 */
export const getTileUrl = (layer) => {
  return `${API_BASE}/tiles/${layer}/{z}/{x}/{y}.png`;
};

export default api;
