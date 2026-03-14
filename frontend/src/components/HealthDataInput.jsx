/**
 * HealthDataInput — Health department data submission form
 *
 * Allows health departments to submit location-specific health data:
 * - Heatstroke, dehydration, respiratory cases
 * - Emergency visits
 * - Vulnerable population percentage
 * - Heat risk classification
 */
import { useState } from 'react';
import { healthApi } from '../api';
import './HealthDataInput.css';

const DISTRICTS = [
  'Central', 'New Delhi', 'North', 'North East', 'North West',
  'East', 'West', 'South', 'South East', 'South West', 'Shahdara'
];

export default function HealthDataInput() {
  const [formData, setFormData] = useState({
    district: 'Central',
    area: '',
    heatstrokeCases: '',
    dehydrationCases: '',
    respiratoryCases: '',
    emergencyVisits: '',
    vulnerablePopulationPct: '',
    heatRiskLevel: 'Low',
  });

  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setFeedback(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setFeedback(null);

    try {
      await healthApi.submit({
        district: formData.district,
        area: formData.area,
        heatstroke_cases: Number(formData.heatstrokeCases) || 0,
        dehydration_cases: Number(formData.dehydrationCases) || 0,
        respiratory_cases: Number(formData.respiratoryCases) || 0,
        emergency_visits: Number(formData.emergencyVisits) || 0,
        vulnerable_population_pct: Number(formData.vulnerablePopulationPct) || 0,
        heat_risk_level: formData.heatRiskLevel,
      });
      setFeedback({ type: 'success', text: 'Health data submitted successfully' });
      setFormData(prev => ({
        ...prev,
        area: '',
        heatstrokeCases: '',
        dehydrationCases: '',
        respiratoryCases: '',
        emergencyVisits: '',
        vulnerablePopulationPct: '',
      }));
    } catch (err) {
      console.error('Health data submission failed:', err);
      setFeedback({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to submit health data',
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="health-input-panel">
      <p className="health-desc">
        Submit location-specific heat-related health data for corridor prioritization.
      </p>

      <form onSubmit={handleSubmit}>
        <h3>Location</h3>

        <label>District</label>
        <select name="district" value={formData.district} onChange={handleChange}>
          {DISTRICTS.map(d => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>

        <label>Area / Locality</label>
        <input
          type="text"
          name="area"
          value={formData.area}
          placeholder="e.g. Chandni Chowk, Connaught Place"
          onChange={handleChange}
        />

        <h3>Case Data</h3>

        <div className="health-grid">
          <div className="health-field">
            <label>🤒 Heatstroke</label>
            <input
              type="number"
              name="heatstrokeCases"
              value={formData.heatstrokeCases}
              placeholder="0"
              min="0"
              onChange={handleChange}
            />
          </div>

          <div className="health-field">
            <label>💧 Dehydration</label>
            <input
              type="number"
              name="dehydrationCases"
              value={formData.dehydrationCases}
              placeholder="0"
              min="0"
              onChange={handleChange}
            />
          </div>

          <div className="health-field">
            <label>🫁 Respiratory</label>
            <input
              type="number"
              name="respiratoryCases"
              value={formData.respiratoryCases}
              placeholder="0"
              min="0"
              onChange={handleChange}
            />
          </div>

          <div className="health-field">
            <label>🚑 Emergency Visits</label>
            <input
              type="number"
              name="emergencyVisits"
              value={formData.emergencyVisits}
              placeholder="0"
              min="0"
              onChange={handleChange}
            />
          </div>
        </div>

        <h3>Risk Assessment</h3>

        <label>Vulnerable Population %</label>
        <input
          type="number"
          name="vulnerablePopulationPct"
          value={formData.vulnerablePopulationPct}
          placeholder="0"
          min="0"
          max="100"
          onChange={handleChange}
        />

        <label>Heat Risk Classification</label>
        <select name="heatRiskLevel" value={formData.heatRiskLevel} onChange={handleChange}>
          <option value="Low">Low</option>
          <option value="Moderate">Moderate</option>
          <option value="High">High</option>
          <option value="Extreme">Extreme</option>
        </select>

        {feedback && (
          <div className={`health-feedback ${feedback.type}`}>
            {feedback.type === 'success' ? '✅' : '❌'} {feedback.text}
          </div>
        )}

        <button type="submit" disabled={submitting}>
          {submitting ? 'Submitting…' : 'Submit Health Data'}
        </button>
      </form>
    </div>
  );
}
