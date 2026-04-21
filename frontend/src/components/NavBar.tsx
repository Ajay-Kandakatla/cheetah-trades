import { NavLink } from 'react-router-dom';

export function NavBar() {
  return (
    <header className="navbar">
      <div className="brand">
        <span className="brand-mark" />
        <div>
          <div className="brand-title">Cheetah Market</div>
          <div className="brand-sub">Research + real-time</div>
        </div>
      </div>
      <nav>
        <NavLink to="/dashboard" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          Dashboard
        </NavLink>
        <NavLink to="/live" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          Live Stream
        </NavLink>
      </nav>
      <div className="nav-meta">
        Prepared for <strong>Aj</strong> · Apr 20 2026
      </div>
    </header>
  );
}
