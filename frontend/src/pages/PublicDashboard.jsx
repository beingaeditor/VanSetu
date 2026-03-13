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

  return (
    <div className="app">
      <Sidebar
        activeLayers={activeLayers}
        setActiveLayers={setActiveLayers}
      />
      <main className="main-content">
        <Map activeLayers={activeLayers} />
      </main>
    </div>
  );
}
