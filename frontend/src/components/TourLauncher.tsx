/* TourLauncher — a global floating 🧭 button that (re)starts the SiteTour from
   any page. Sibling of the floating ChatWidget, mounted once in App.tsx.

   The tour itself lives on /sepa (its steps point at SEPA elements), so the
   launcher routes there first, then signals the page to open the tour. It uses
   both a sessionStorage flag (survives the navigation + mount) and a window
   event (for when /sepa is already mounted) — see the listener in Sepa.tsx.

   Dark glass circle + gold compass so it's visually distinct from the gold
   chat bubble on the opposite corner. Added 2026-06-12 per user request. */
import { useLocation, useNavigate } from 'react-router-dom';

export function TourLauncher() {
  const navigate = useNavigate();
  const location = useLocation();

  const start = () => {
    const fire = () => window.dispatchEvent(new CustomEvent('cheetah:start-tour'));
    if (location.pathname === '/sepa') {
      fire();
      return;
    }
    try { sessionStorage.setItem('cheetah_start_tour', '1'); } catch { /* ignore */ }
    navigate('/sepa');
    // Belt-and-suspenders: if /sepa was already mounted (lazy chunk cached),
    // the flag-on-mount effect won't re-run, so also fire the event shortly.
    setTimeout(fire, 600);
  };

  return (
    <button
      type="button"
      onClick={start}
      aria-label="Take the site tour"
      title="Take the site tour"
      style={{
        position: 'fixed',
        left: 'max(env(safe-area-inset-left), 14px)',
        bottom: 'max(env(safe-area-inset-bottom), 14px)',
        zIndex: 998,
        width: 46, height: 46,
        borderRadius: '50%',
        background: '#15171c',
        border: '1px solid rgba(212,175,55,0.55)',
        boxShadow: '0 6px 22px rgba(0,0,0,0.45), 0 0 0 1px rgba(212,175,55,0.18)',
        cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 0,
      }}
    >
      <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" style={{ display: 'block' }}>
        <circle cx="12" cy="12" r="9" fill="none" stroke="#d4af37" strokeWidth="1.7" />
        <polygon points="12,12 16.2,7.8 12.9,11.1" fill="#d4af37" />
        <polygon points="12,12 7.8,16.2 11.1,12.9" fill="#d4af37" opacity="0.45" />
        <circle cx="12" cy="12" r="1.15" fill="#d4af37" />
      </svg>
    </button>
  );
}
