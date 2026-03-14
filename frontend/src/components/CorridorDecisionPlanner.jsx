import { useState } from "react";
import Corridor3DViewer from "./Corridor3DViewer";
import "./CorridorDecisionPlanner.css";

export default function CorridorDecisionPlanner() {

  const [form, setForm] = useState({
    roadWidth: "",
    pedestrianActivity: "",
    shadeLevel: "",
    heatLevel: "",
    pollutionLevel: "",
    vulnerablePopulation: "",
    landAvailability: ""
  });

  const [corridorType, setCorridorType] = useState(null);

  const handleChange = (e) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value
    });
  };

  const generateCorridor = () => {

    const width = Number(form.roadWidth);

    if (width < 6) {
      setCorridorType("tree_corridor");
    }
    else if (width >= 6 && width < 12) {
      setCorridorType("shade_corridor");
    }
    else {
      setCorridorType("green_mobility_corridor");
    }
  };

  return (

    <div className="corridor-decision">

      <h2>Green Corridor Decision Engine</h2>

      {/* Inputs */}

      <div className="planner-grid">

        <label>Road Width (m)</label>
        <input
          type="number"
          name="roadWidth"
          onChange={handleChange}
        />

        <label>Pedestrian Activity</label>
        <select name="pedestrianActivity" onChange={handleChange}>
          <option>Low</option>
          <option>Medium</option>
          <option>High</option>
          <option>Very High</option>
        </select>

        <label>Heat Exposure</label>
        <select name="heatLevel" onChange={handleChange}>
          <option>Comfortable</option>
          <option>Warm</option>
          <option>Very Hot</option>
          <option>Extremely Hot</option>
        </select>

        <label>Shade Availability</label>
        <select name="shadeLevel" onChange={handleChange}>
          <option>Full Shade</option>
          <option>Partial Shade</option>
          <option>Very Little Shade</option>
          <option>No Shade</option>
        </select>

        <label>Pollution Level</label>
        <select name="pollutionLevel" onChange={handleChange}>
          <option>Low</option>
          <option>Moderate</option>
          <option>High</option>
          <option>Severe</option>
        </select>

        <label>Vulnerable Population</label>
        <select name="vulnerablePopulation" onChange={handleChange}>
          <option>Low</option>
          <option>Moderate</option>
          <option>High</option>
          <option>Very High</option>
        </select>

        <label>Land Availability</label>
        <select name="landAvailability" onChange={handleChange}>
          <option>None</option>
          <option>Small</option>
          <option>Medium</option>
          <option>Large</option>
        </select>

      </div>

      <button onClick={generateCorridor}>
        Generate Green Corridor
      </button>

      {/* 3D Output */}

      {corridorType && (
        <Corridor3DViewer type={corridorType}/>
      )}

    </div>
  );
}