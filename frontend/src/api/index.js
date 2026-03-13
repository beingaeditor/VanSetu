/**
 * API Service — centralized API calls to the backend
 * 
 * Updated to support AQI integration for Multi-Exposure Priority scoring.
 */
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

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
 * Roads endpoints
 */
export const roadsApi = {
  simple: () => api.get('/roads/simple'),
  withGdi: (includeAqi = true) => api.get('/roads', { params: { include_aqi: includeAqi } }),
  corridors: (percentile = 85, includeAqi = true) => api.get('/corridors', { 
    params: { percentile, include_aqi: includeAqi } 
  }),
};

/**
 * Aggregated Corridors endpoints (Point-Based Corridor Aggregation)
 * 
 * These endpoints provide the new corridor aggregation feature that:
 * - Takes existing high-priority points as input
 * - Connects spatially continuous points into corridors
 * - Preserves all original points
 * - Adds a new corridor abstraction layer on top
 */
export const corridorsApi = {
  /**
   * Get aggregated corridors as GeoJSON
   * @param {number} dMax - Maximum connection distance in meters (default: 30)
   * @param {number} nMin - Minimum points for valid corridor (default: 5)
   * @param {number} percentile - Percentile threshold for high-priority points (default: 85)
   */
  aggregated: (dMax = 30, nMin = 5, percentile = 85) => api.get('/corridors/aggregated', {
    params: { d_max: dMax, n_min: nMin, percentile }
  }),
  
  /**
   * Get specific corridor with point details
   * @param {string} corridorId - UUID of the corridor
   * @param {boolean} includePoints - Include full point details (default: true)
   */
  detail: (corridorId, includePoints = true) => api.get(`/corridors/aggregated/${corridorId}`, {
    params: { include_points: includePoints }
  }),
  
  /**
   * Get high-priority points used for aggregation
   * @param {number} percentile - Percentile threshold
   * @param {boolean} includeAll - Include all points, not just high-priority
   */
  points: (percentile = 85, includeAll = false) => api.get('/corridors/points', {
    params: { percentile, include_all: includeAll }
  }),
  
  /**
   * Get corridor statistics
   */
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
 * 
 * Allows users to submit suggestions and upvote corridors.
 * Rate limited: 3 suggestions per corridor per hour, 10 upvotes per hour.
 */
export const suggestionsApi = {
  /**
   * Get all suggestions for a corridor
   * @param {string} corridorId - The corridor UUID
   * @returns {Promise} List of suggestions
   */
  list: (corridorId) => api.get(`/corridors/${corridorId}/suggestions`),
  
  /**
   * Submit a new suggestion for a corridor
   * @param {string} corridorId - The corridor UUID
   * @param {string} text - Suggestion text (3-300 characters)
   * @returns {Promise} Created suggestion
   */
  create: (corridorId, text) => api.post(`/corridors/${corridorId}/suggestions`, { text }),
  
  /**
   * Upvote a corridor
   * @param {string} corridorId - The corridor UUID
   * @returns {Promise} Updated corridor upvote count
   */
  upvoteCorridor: (corridorId) => api.post(`/corridors/${corridorId}/upvote`),
  
  /**
   * Get corridor upvote count
   * @param {string} corridorId - The corridor UUID
   * @returns {Promise} Corridor upvote count
   */
  getCorridorUpvotes: (corridorId) => api.get(`/corridors/${corridorId}/upvotes`),
  
  /**
   * Get suggestion statistics for a corridor
   * @param {string} corridorId - The corridor UUID
   * @returns {Promise} Suggestion count and total upvotes
   */
  stats: (corridorId) => api.get(`/corridors/${corridorId}/suggestions/stats`),
};

/**
 * Get tile URL template for Leaflet
 */
export const getTileUrl = (layer) => {
  return `${API_BASE}/tiles/${layer}/{z}/{x}/{y}.png`;
};

export default api;
