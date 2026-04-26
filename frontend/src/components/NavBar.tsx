import { NavLink } from 'react-router-dom';
import { ThemeToggle } from './ThemeToggle';

/* ==========================================================================
   NavBar — editorial masthead
   Left:   italic serif wordmark + mono dateline
   Center: uppercase letter-spaced nav links, gold hairline for active
   Right:  "Prepared for" meta + theme toggle
   ========================================================================== */

const TODAY = new Date().toLocaleDateString('en-US', {
  month: 'short',
  day: '2-digit',
  year: 'numeric',
});

export function NavBar() {
  return (
    <header className="cm-nav">
      <div className="cm-nav__brand">
        <div className="cm-nav__wordmark">Cheetah Market</div>
        <div className="cm-nav__eyebrow eyebrow">№ 01 — Research &amp; Real-Time</div>
      </div>

      <nav className="cm-nav__links" aria-label="Primary">
        <NavLink
          to="/dashboard"
          className={({ isActive }) => `cm-nav__link${isActive ? ' is-active' : ''}`}
        >
          Dashboard
        </NavLink>
        <NavLink
          to="/live"
          className={({ isActive }) => `cm-nav__link${isActive ? ' is-active' : ''}`}
        >
          Live Stream
        </NavLink>
        <NavLink
          to="/sepa"
          className={({ isActive }) => `cm-nav__link${isActive ? ' is-active' : ''}`}
        >
          SEPA
        </NavLink>
        <NavLink
          to="/dual-momentum"
          className={({ isActive }) => `cm-nav__link${isActive ? ' is-active' : ''}`}
        >
          Dual Momentum
        </NavLink>
        <NavLink
          to="/chatter"
          className={({ isActive }) => `cm-nav__link${isActive ? ' is-active' : ''}`}
        >
          Chatter · US
        </NavLink>
        <NavLink
          to="/chatter-india"
          className={({ isActive }) => `cm-nav__link${isActive ? ' is-active' : ''}`}
        >
          Chatter · IN
        </NavLink>
      </nav>

      <div className="cm-nav__meta">
        <span className="cm-nav__meta-label">Prepared for</span>
        <span className="cm-nav__meta-name">Aj</span>
        <span className="cm-nav__meta-sep" aria-hidden="true">·</span>
        <span className="cm-nav__meta-date mono">{TODAY}</span>
        <ThemeToggle />
      </div>
    </header>
  );
}
