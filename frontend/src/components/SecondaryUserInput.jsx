/**
 * SecondaryUserInput — Environmental & community data input form
 *
 * Allows secondary users (community activity providers and
 * environmental risk authorities) to submit structured observations.
 */
import { useState } from "react";
import { communityDataApi } from "../api";
import "./SecondaryUserInput.css";

export default function SecondaryUserInput() {
  const [formData, setFormData] = useState({
    city: "Delhi",
    ward: "Ward 1",
    street: "",
    userType: "Street Vendor",
    heatLevel: "Comfortable",
    shadeLevel: "Full shade",
    pedestrianActivity: "Low (<200 people/day)",
    peakTime: "Morning",
    pollutionLevel: "Low",
    pollutionSource: "Traffic corridor",
    heatwaveRisk: "Low risk",
    vulnerablePopulation: "Low",
    emergencyHeatIncidents: "None",
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
      await communityDataApi.submit(formData);
      setFeedback({ type: "success", text: "Data submitted successfully" });
    } catch (err) {
      console.error("Community data submission failed:", err);
      setFeedback({
        type: "error",
        text: err.response?.data?.detail || "Failed to submit data",
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="secondary-user-panel">

      <form onSubmit={handleSubmit}>

        {/* Location */}
        <h3>Location</h3>

        <label>City</label>
        <select name="city" value={formData.city} onChange={handleChange}>
          <option>Delhi</option>
          <option>Mumbai</option>
          <option>Bangalore</option>
        </select>

        <label>Ward</label>
        <select name="ward" value={formData.ward} onChange={handleChange}>
          <option>Ward 1</option>
          <option>Ward 2</option>
          <option>Ward 3</option>
        </select>

        <label>Street / Area</label>
        <input
          type="text"
          name="street"
          placeholder="Enter street or area"
          value={formData.street}
          onChange={handleChange}
        />

        {/* User Type */}
        <h3>User Type</h3>

        <select name="userType" value={formData.userType} onChange={handleChange}>
          <option>Street Vendor</option>
          <option>School</option>
          <option>College / University</option>
        </select>

        {/* Heat Exposure */}
        <h3>Heat Exposure</h3>

        <select name="heatLevel" value={formData.heatLevel} onChange={handleChange}>
          <option>Comfortable</option>
          <option>Warm</option>
          <option>Very Hot</option>
          <option>Extremely Hot</option>
        </select>

        {/* Shade Availability */}
        <h3>Shade Availability</h3>

        <select name="shadeLevel" value={formData.shadeLevel} onChange={handleChange}>
          <option>Full shade</option>
          <option>Partial shade</option>
          <option>Very little shade</option>
          <option>No shade</option>
        </select>

        {/* Pedestrian Activity */}
        <h3>Pedestrian Activity</h3>

        <select name="pedestrianActivity" value={formData.pedestrianActivity} onChange={handleChange}>
          <option>Low (&lt;200 people/day)</option>
          <option>Medium (200–800 people/day)</option>
          <option>High (800–2000 people/day)</option>
          <option>Very High (&gt;2000 people/day)</option>
        </select>

        {/* Peak Time */}
        <h3>Peak Activity Time</h3>

        <select name="peakTime" value={formData.peakTime} onChange={handleChange}>
          <option>Morning</option>
          <option>Afternoon</option>
          <option>Evening</option>
          <option>All Day</option>
        </select>

        {/* Environmental Authority Inputs */}
        <h3>Environmental Risk Data</h3>

        <label>Air Pollution Level</label>
        <select name="pollutionLevel" value={formData.pollutionLevel} onChange={handleChange}>
          <option>Low</option>
          <option>Moderate</option>
          <option>High</option>
          <option>Severe</option>
        </select>

        <label>Major Pollution Source</label>
        <select name="pollutionSource" value={formData.pollutionSource} onChange={handleChange}>
          <option>Traffic corridor</option>
          <option>Market / commercial activity</option>
          <option>Industrial activity</option>
          <option>Mixed urban pollution</option>
        </select>

        <label>Heatwave Risk Level</label>
        <select name="heatwaveRisk" value={formData.heatwaveRisk} onChange={handleChange}>
          <option>Low risk</option>
          <option>Moderate risk</option>
          <option>High risk</option>
          <option>Extreme heat risk zone</option>
        </select>

        <label>Vulnerable Population</label>
        <select name="vulnerablePopulation" value={formData.vulnerablePopulation} onChange={handleChange}>
          <option>Low</option>
          <option>Moderate</option>
          <option>High</option>
          <option>Very High</option>
        </select>

        <label>Emergency Heat Incidents</label>
        <select name="emergencyHeatIncidents" value={formData.emergencyHeatIncidents} onChange={handleChange}>
          <option>None</option>
          <option>Occasional</option>
          <option>Frequent</option>
          <option>Critical hotspot</option>
        </select>

        {feedback && (
          <div className={`submit-feedback ${feedback.type}`}>
            {feedback.type === "success" ? "✅" : "❌"} {feedback.text}
          </div>
        )}

        <button type="submit" disabled={submitting}>
          {submitting ? "Submitting…" : "Submit Data"}
        </button>

      </form>

    </div>
  );
}