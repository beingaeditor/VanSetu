/**
 * PublicDashboard — The existing public-facing map view
 */
import { useState } from 'react';
import Map from '../components/Map';
import Sidebar from '../components/Sidebar';

export default function PublicDashboard() {
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

  const [selectedCorridor, setSelectedCorridor] = useState(null);

  return (
    <div className="app">
      <Sidebar
        activeLayers={activeLayers}
        setActiveLayers={setActiveLayers}
        selectedCorridor={selectedCorridor}
        onSelectCorridor={setSelectedCorridor}
      />
      <main className="main-content">
        <Map
          activeLayers={activeLayers}
          selectedCorridor={selectedCorridor}
          onSelectCorridor={setSelectedCorridor}
        />
      </main>
    </div>
  );
}
