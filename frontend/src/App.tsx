import { Navigate, Route, Routes } from 'react-router-dom';
import { NavBar } from './components/NavBar';
import { ModernDashboard } from './pages/ModernDashboard';
import { LiveStream } from './pages/LiveStream';
import { SepaPage } from './pages/Sepa';
import { SepaCandidatePage } from './pages/SepaCandidate';
import { DualMomentumPage } from './pages/DualMomentum';
import { ChatterPage } from './pages/Chatter';

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
          <Route path="/sepa/:symbol" element={<SepaCandidatePage />} />
          <Route path="/dual-momentum" element={<DualMomentumPage />} />
          <Route path="/chatter" element={<ChatterPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}
