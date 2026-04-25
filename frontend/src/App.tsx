import { Navigate, Route, Routes } from 'react-router-dom';
import { NavBar } from './components/NavBar';
import { ModernDashboard } from './pages/ModernDashboard';
import { LiveStream } from './pages/LiveStream';
import { SepaPage } from './pages/Sepa';

export function App() {
  return (
    <div className="app">
      <NavBar />
      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<ModernDashboard />} />
          <Route path="/live" element={<LiveStream />} />
          <Route path="/sepa" element={<SepaPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}
