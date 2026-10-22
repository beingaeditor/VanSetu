import { useState } from "react";
import Corridor3DViewer from "./Corridor3DViewer";
import "./CorridorDecisionPlanner.css";

export default function CorridorDecisionPlanner() {
  const [form, setForm] = useState({
    roadWidth: "12",
    pedestrianActivity: "High",
    heatLevel: "Very Hot",
    shadeLevel: "Very Little Shade",
    pollutionLevel: "High",
    vulnerablePopulation: "High",
    landAvailability: "Medium"
  });

  const [decision, setDecision] = useState(null);

  const handleChange = (e) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value
    });
  };

  const generateCorridor = () => {
    const width = Number(form.roadWidth) || 10;
    const isPedestrianHeavy = form.pedestrianActivity === "High" || form.pedestrianActivity === "Very High";
    const isHeatSevere = form.heatLevel === "Very Hot" || form.heatLevel === "Extremely Hot";
    const isShadeDeficient = form.shadeLevel === "Very Little Shade" || form.shadeLevel === "No Shade";
    const isPollutionSevere = form.pollutionLevel === "High" || form.pollutionLevel === "Severe";
    const isVulnerable = form.vulnerablePopulation === "High" || form.vulnerablePopulation === "Very High";
    const hasSpace = form.landAvailability === "Medium" || form.landAvailability === "Large";

    let chosenType = "tree_corridor";
    let rationale = "";
    let feasibility = "High";
    let estCostLakhs = "18 - 25 Lakhs / km";
    let checks = [];

    if (width < 6 || form.landAvailability === "None") {
      // Very narrow or zero unpaved margin -> Shade canopies / vertical trellises
      chosenType = "shade_corridor";
      feasibility = "Moderate (Constrained Right-of-Way)";
      estCostLakhs = "15 - 22 Lakhs / km";
      rationale = `Narrow street profile (${width}m) and limited setback prevent deep-root canopy trees. Architectural shade structures, cantilevered awnings, and wall trellises provide zero-latency thermal protection without blocking pedestrian clearance.`;
      checks = [
        "Check minimum 1.2m clear aisle for wheelchair passage (Harmonised Accessibility Guidelines).",
        "Inspect boundary wall structural integrity for trellis anchoring.",
        "Locate non-potable water connection for vertical garden maintenance."
      ];
    } else if (width >= 14 && hasSpace && isPedestrianHeavy) {
      // Wide street with space and heavy pedestrian flow -> Integrated Green Mobility Boulevard
      chosenType = "green_mobility_corridor";
      feasibility = "High (Generous Right-of-Way)";
      estCostLakhs = "35 - 55 Lakhs / km";
      rationale = `Wide street (${width}m) with ${form.landAvailability.toLowerCase()} land margin allows a complete street redesign: continuous 8m canopy trees, bioretention swales for monsoon drainage, and dedicated shaded pedestrian paths.`;
      checks = [
        "Ground Penetrating Radar (GPR) utility survey before bioswale excavation.",
        "MCD/PWD right-of-way demarcation.",
        "Soil percolation rate test for stormwater infiltration."
      ];
    } else {
      // Moderate street (6-14m)
      if (isHeatSevere && isShadeDeficient) {
        chosenType = "tree_corridor";
        feasibility = "High";
        estCostLakhs = "20 - 30 Lakhs / km";
        rationale = `Severe heat exposure with critical shade deficit justifies linear street tree planting (Neem, Pilkhan, Jamun). Provides maximum long-term canopy cooling and particulate interception.`;
        checks = [
          "Check overhead power line clearance with local discom (BSES/Tata Power).",
          "Ensure minimum 1.5m x 1.5m unpaved permeable soil basin per tree.",
          "Arrange dedicated 3-year water tanker irrigation contract."
        ];
      } else {
        chosenType = "shade_corridor";
        feasibility = "High";
        estCostLakhs = "18 - 24 Lakhs / km";
        rationale = `Moderate thermal stress and street width permit hybrid shade shelters and modular containerized greenery at key pedestrian clusters.`;
        checks = [
          "Identify high-footfall bus stops and transit nodes.",
          "Check wind-load engineering for tensile fabric structures."
        ];
      }
    }

    setDecision({
      type: chosenType,
      feasibility,
      estCostLakhs,
      rationale,
      checks,
      parametersEvaluated: {
        width: `${width}m`,
        pedestrian: form.pedestrianActivity,
        heat: form.heatLevel,
        shade: form.shadeLevel,
        pollution: form.pollutionLevel,
        vulnerability: form.vulnerablePopulation,
        land: form.landAvailability
      }
    });
  };

  return (
    <div className="corridor-decision">
      <h2>Green Corridor Decision Engine</h2>
      <p className="planner-subtitle">
        Multi-criteria suitability evaluation: enter site parameters to determine the optimal intervention strategy, feasibility, and required site checks.
      </p>

      {/* Inputs */}
      <div className="planner-grid">
        <div className="input-group">
          <label>Road / Right-of-Way Width (m)</label>
          <input
            type="number"
            name="roadWidth"
            value={form.roadWidth}
            onChange={handleChange}
            min="2"
            max="60"
          />
        </div>

        <div className="input-group">
          <label>Pedestrian Activity</label>
          <select name="pedestrianActivity" value={form.pedestrianActivity} onChange={handleChange}>
            <option>Low</option>
            <option>Medium</option>
            <option>High</option>
            <option>Very High</option>
          </select>
        </div>

        <div className="input-group">
          <label>Heat Exposure</label>
          <select name="heatLevel" value={form.heatLevel} onChange={handleChange}>
            <option>Comfortable</option>
            <option>Warm</option>
            <option>Very Hot</option>
            <option>Extremely Hot</option>
          </select>
        </div>

        <div className="input-group">
          <label>Existing Shade Coverage</label>
          <select name="shadeLevel" value={form.shadeLevel} onChange={handleChange}>
            <option>Full Shade</option>
            <option>Partial Shade</option>
            <option>Very Little Shade</option>
            <option>No Shade</option>
          </select>
        </div>

        <div className="input-group">
          <label>Air Pollution Exposure</label>
          <select name="pollutionLevel" value={form.pollutionLevel} onChange={handleChange}>
            <option>Low</option>
            <option>Moderate</option>
            <option>High</option>
            <option>Severe</option>
          </select>
        </div>

        <div className="input-group">
          <label>Vulnerable Population</label>
          <select name="vulnerablePopulation" value={form.vulnerablePopulation} onChange={handleChange}>
            <option>Low</option>
            <option>Moderate</option>
            <option>High</option>
            <option>Very High</option>
          </select>
        </div>

        <div className="input-group">
          <label>Unpaved Margin / Land Availability</label>
          <select name="landAvailability" value={form.landAvailability} onChange={handleChange}>
            <option>None</option>
            <option>Small</option>
            <option>Medium</option>
            <option>Large</option>
          </select>
        </div>
      </div>

      <button className="generate-btn" onClick={generateCorridor}>
        Evaluate Multi-Criteria Strategy
      </button>

      {/* Decision Output Card */}
      {decision && (
        <div className="decision-results-card">
          <div className="decision-header">
            <h3>Recommended Strategy: {decision.type.replace(/_/g, " ").toUpperCase()}</h3>
            <span className="feasibility-pill">{decision.feasibility}</span>
          </div>

          <p className="decision-rationale"><strong>Rationale:</strong> {decision.rationale}</p>
          <p className="decision-cost"><strong>Estimated 5-Year Lifecycle Cost:</strong> {decision.estCostLakhs} (CPWD benchmark)</p>

          <div className="decision-checks">
            <strong>Mandatory Pre-Implementation Site Checks:</strong>
            <ul>
              {decision.checks.map((chk, i) => (
                <li key={i}>{chk}</li>
              ))}
            </ul>
          </div>

          {/* 3D Visualizer */}
          <div className="decision-3d-box">
            <h4>3D Corridor Spatial Simulation</h4>
            <Corridor3DViewer type={decision.type} />
          </div>
        </div>
      )}
    </div>
  );
}