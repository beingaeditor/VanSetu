/**
 * App Component — Main application with route-based layout
 *
 * Routes:
 *   /       — Public dashboard (map + sidebar)
 *   /admin  — Government / Business dashboard
 */
import { Routes, Route } from 'react-router-dom';
import PublicDashboard from './pages/PublicDashboard';
import AdminDashboard from './pages/AdminDashboard';
import './App.css';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<PublicDashboard />} />
      <Route path="/admin/*" element={<AdminDashboard />} />
    </Routes>
  );
}
