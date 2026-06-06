import { useEffect, useRef, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { ThemeToggle } from './ThemeToggle';
import { NotificationBell } from './NotificationBell';
import { useCurrentUser } from '../hooks/useUser';
import { useMyMenu, type MenuItem } from '../hooks/useMyMenu';

/* ==========================================================================
   NavBar — editorial masthead
   --------------------------------------------------------------------------
   Menu structure comes from the BACKEND (GET /me/menu, see
   backend/access/api.py). Each user sees only items they actually have
   access to — the frontend cannot accidentally surface a link the user
   can't reach. This eliminated the entire class of "click misc → 404"
   bugs that the previous client-filtered approach allowed when the
   features fetch raced the user's click.

   Desktop:
     - PRIMARY items (typically Morning / SEPA / Overnight or Food / Kids
       for the household-only users) live on the top bar.
     - MISC items collapse into a "Misc ▾" dropdown.
     - PROFILE items + admin items hang off the avatar at top-right.
   Mobile (<= 720px):
     - All sections collapse into a hamburger drawer with section headers.
   ========================================================================== */

const TODAY = new Date().toLocaleDateString('en-US', {
  month: 'short',
  day: '2-digit',
});

function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState<boolean>(
    typeof window !== 'undefined' ? window.innerWidth <= 720 : false,
  );
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 720px)');
    const onChange = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    setIsMobile(mq.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return isMobile;
}

export function NavBar() {
  const location = useLocation();
  const isMobile = useIsMobile();
  const [scannersOpen, setScannersOpen] = useState(false);
  const [moreOpen,    setMoreOpen]    = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [drawerOpen,  setDrawerOpen]  = useState(false);
  const scannersRef = useRef<HTMLDivElement>(null);
  const moreRef    = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  const { menu, loaded } = useMyMenu();

  // Backend has the authoritative menu — but admin tabs are kept in
  // a separate `admin` section so we can render them inside the
  // Profile dropdown beneath the regular profile items.
  const PRIMARY_VISIBLE: MenuItem[] = menu.primary;
  const SCANNERS_VISIBLE: MenuItem[] = menu.scanners;
  const SECONDARY_VISIBLE: MenuItem[] = menu.misc;
  const PROFILE_VISIBLE: MenuItem[] = [...menu.profile, ...menu.admin];

  // "Which tabs trigger this dropdown's active state?" — checks if the
  // current route starts with any of the section's hrefs.
  const isScannersActive  = SCANNERS_VISIBLE.some((t) => location.pathname.startsWith(t.to));
  const isSecondaryActive = SECONDARY_VISIBLE.some((t) => location.pathname.startsWith(t.to));
  const isProfileActive   = PROFILE_VISIBLE.some((t) => location.pathname.startsWith(t.to));

  // Find the active item for the mobile breadcrumb "Pounce · {label}".
  const allItems: MenuItem[] = [...PRIMARY_VISIBLE, ...SCANNERS_VISIBLE, ...SECONDARY_VISIBLE, ...PROFILE_VISIBLE];
  const currentTab = allItems.find((t) => location.pathname.startsWith(t.to));

  // Close desktop dropdowns on outside click + Esc.
  useEffect(() => {
    if (!moreOpen && !profileOpen && !scannersOpen) return;
    const onClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (scannersOpen && scannersRef.current && !scannersRef.current.contains(target)) {
        setScannersOpen(false);
      }
      if (moreOpen && moreRef.current && !moreRef.current.contains(target)) {
        setMoreOpen(false);
      }
      if (profileOpen && profileRef.current && !profileRef.current.contains(target)) {
        setProfileOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setScannersOpen(false); setMoreOpen(false); setProfileOpen(false); }
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [moreOpen, profileOpen, scannersOpen]);

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setDrawerOpen(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [drawerOpen]);

  // Close menus on route change.
  useEffect(() => {
    setScannersOpen(false);
    setMoreOpen(false);
    setProfileOpen(false);
    setDrawerOpen(false);
  }, [location.pathname]);

  // Lock body scroll while mobile drawer is open.
  useEffect(() => {
    if (!drawerOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [drawerOpen]);

  if (isMobile) {
    return (
      <header className="cm-nav cm-nav--mobile">
        <div className="cm-nav__brand">
          <div className="cm-nav__wordmark">Pounce</div>
          {currentTab && <div className="cm-nav__current">· {currentTab.label}</div>}
        </div>

        <button
          type="button"
          className={`cm-nav__hamburger${drawerOpen ? ' is-open' : ''}`}
          onClick={() => setDrawerOpen(!drawerOpen)}
          aria-label={drawerOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={drawerOpen}
        >
          <span /><span /><span />
        </button>

        {drawerOpen && (
          <>
            <div className="cm-nav__backdrop" onClick={() => setDrawerOpen(false)} />
            <nav className="cm-nav__drawer" aria-label="Primary">
              {/* Empty sections are omitted so a friend with just /food
                  doesn't see "Daily" / "Tools" headers with nothing
                  under them. */}
              {PRIMARY_VISIBLE.length > 0 && (
                <>
                  <div className="cm-nav__drawer-section-label">Daily</div>
                  {PRIMARY_VISIBLE.map((t) => (
                    <NavLink
                      key={t.to}
                      to={t.to}
                      className={({ isActive }) => `cm-nav__drawer-link${isActive ? ' is-active' : ''}`}
                      onClick={() => setDrawerOpen(false)}
                    >
                      {t.label}
                    </NavLink>
                  ))}
                </>
              )}
              {SCANNERS_VISIBLE.length > 0 && (
                <>
                  <div className="cm-nav__drawer-section-label">Scanners</div>
                  {SCANNERS_VISIBLE.map((t) => (
                    <NavLink
                      key={t.to}
                      to={t.to}
                      className={({ isActive }) => `cm-nav__drawer-link${isActive ? ' is-active' : ''}`}
                      onClick={() => setDrawerOpen(false)}
                    >
                      {t.label}
                    </NavLink>
                  ))}
                </>
              )}
              {SECONDARY_VISIBLE.length > 0 && (
                <>
                  <div className="cm-nav__drawer-section-label">Tools</div>
                  {SECONDARY_VISIBLE.map((t) => (
                    <NavLink
                      key={t.to}
                      to={t.to}
                      className={({ isActive }) => `cm-nav__drawer-link${isActive ? ' is-active' : ''}`}
                      onClick={() => setDrawerOpen(false)}
                    >
                      {t.label}
                    </NavLink>
                  ))}
                </>
              )}
              {PROFILE_VISIBLE.length > 0 && (
                <>
                  <div className="cm-nav__drawer-section-label">Account</div>
                  {PROFILE_VISIBLE.map((t) => (
                    <NavLink
                      key={t.to}
                      to={t.to}
                      className={({ isActive }) => `cm-nav__drawer-link${isActive ? ' is-active' : ''}`}
                      onClick={() => setDrawerOpen(false)}
                    >
                      {t.label}
                    </NavLink>
                  ))}
                </>
              )}
              {/* Sign-out always renders (regardless of feature set) so a
                  user with NO menu items can still exit the app. */}
              <a
                href="/oauth2/sign_out"
                className="cm-nav__drawer-link"
                style={{ color: 'var(--negative, #ef4444)' }}
              >
                Sign out
              </a>
              <div className="cm-nav__drawer-foot mono">
                <DrawerUser />· {TODAY}
                <ThemeToggle />
              </div>
            </nav>
          </>
        )}
      </header>
    );
  }

  // Desktop layout — same structure as before, just sourced from the
  // server-built menu. Empty sections are omitted so a friend with
  // only /food doesn't see an empty "Misc ▾" button.
  return (
    <header className="cm-nav">
      <div className="cm-nav__brand">
        <div className="cm-nav__wordmark">Pounce</div>
        <div className="cm-nav__eyebrow eyebrow">wait · then · strike</div>
      </div>

      <nav className="cm-nav__links" aria-label="Primary">
        {PRIMARY_VISIBLE.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) => `cm-nav__link${isActive ? ' is-active' : ''}`}
          >
            {t.label}
          </NavLink>
        ))}

        {SCANNERS_VISIBLE.length > 0 && (
          <div className="cm-nav__more" ref={scannersRef}>
            <button
              type="button"
              className={`cm-nav__link cm-nav__more-btn${isScannersActive ? ' is-active' : ''}${scannersOpen ? ' is-open' : ''}`}
              onClick={() => { setScannersOpen(!scannersOpen); setMoreOpen(false); setProfileOpen(false); }}
              aria-haspopup="menu"
              aria-expanded={scannersOpen}
            >
              Scanners <span className="cm-nav__caret">▾</span>
            </button>
            {scannersOpen && (
              <div className="cm-nav__dropdown" role="menu">
                {SCANNERS_VISIBLE.map((t) => (
                  <NavLink
                    key={t.to}
                    to={t.to}
                    className={({ isActive }) => `cm-nav__dropdown-link${isActive ? ' is-active' : ''}`}
                    role="menuitem"
                  >
                    {t.label}
                  </NavLink>
                ))}
              </div>
            )}
          </div>
        )}

        {SECONDARY_VISIBLE.length > 0 && (
          <div className="cm-nav__more" ref={moreRef}>
            <button
              type="button"
              className={`cm-nav__link cm-nav__more-btn${isSecondaryActive ? ' is-active' : ''}${moreOpen ? ' is-open' : ''}`}
              onClick={() => { setMoreOpen(!moreOpen); setScannersOpen(false); setProfileOpen(false); }}
              aria-haspopup="menu"
              aria-expanded={moreOpen}
            >
              Misc <span className="cm-nav__caret">▾</span>
            </button>
            {moreOpen && (
              <div className="cm-nav__dropdown" role="menu">
                {SECONDARY_VISIBLE.map((t) => (
                  <NavLink
                    key={t.to}
                    to={t.to}
                    className={({ isActive }) => `cm-nav__dropdown-link${isActive ? ' is-active' : ''}`}
                    role="menuitem"
                  >
                    {t.label}
                  </NavLink>
                ))}
              </div>
            )}
          </div>
        )}
      </nav>

      <div className="cm-nav__meta">
        <span className="cm-nav__meta-date mono">{TODAY}</span>
        <ThemeToggle />
        {/* Bell + dropdown of the last 8 unified notifications (pushes
            merged with sepa_breakouts). Sits to the left of the
            profile avatar — same visual weight, separate concern. */}
        <NotificationBell />
        {/* Profile menu is always rendered (sign-out lives here), even
            for a user whose `profile` section is empty. */}
        <div className="cm-nav__profile" ref={profileRef}>
          <button
            type="button"
            className={`cm-nav__profile-btn${isProfileActive ? ' is-active' : ''}${profileOpen ? ' is-open' : ''}`}
            onClick={() => { setProfileOpen(!profileOpen); setMoreOpen(false); setScannersOpen(false); }}
            aria-haspopup="menu"
            aria-expanded={profileOpen}
            aria-label="Profile menu"
          >
            <ProfileAvatar />
            <span className="cm-nav__caret">▾</span>
          </button>
          {profileOpen && (
            <div className="cm-nav__dropdown cm-nav__dropdown--profile" role="menu">
              <ProfileHeader />
              {PROFILE_VISIBLE.map((t) => (
                <NavLink
                  key={t.to}
                  to={t.to}
                  className={({ isActive }) => `cm-nav__dropdown-link${isActive ? ' is-active' : ''}`}
                  role="menuitem"
                >
                  {t.label}
                </NavLink>
              ))}
              <a
                href="/oauth2/sign_out"
                className="cm-nav__dropdown-link cm-nav__dropdown-link--danger"
                role="menuitem"
              >
                Sign out
              </a>
            </div>
          )}
        </div>
      </div>
      {/* `loaded` exists so we could render a subtle "loading menu"
          state in the future. For now we just let the empty arrays
          render — the menu fills in within ~50ms in practice and
          aggressive UI here adds layout churn. */}
      {!loaded && null}
    </header>
  );
}

/* ── Profile avatar — circular button trigger ───────────────────────
   First initial of the signed-in user, color-tinted. Shows "·" while
   the user query is in flight so the button never disappears entirely
   (prevents layout shift). */
function ProfileAvatar() {
  const { user } = useCurrentUser();
  const initial = (
    user?.given_name
    || user?.display_name
    || user?.email
    || '·'
  ).trim().charAt(0).toUpperCase();
  // Gold ring for admin so the avatar visually distinguishes the owner.
  // Server-driven via /auth/me's is_admin flag (replaces the old hardcoded
  // ADMIN_EMAIL comparison that leaked the personal Gmail into the bundle).
  const isAdmin = !!user?.is_admin;
  return (
    <span
      className="cm-nav__avatar"
      aria-hidden="true"
      style={isAdmin ? { borderColor: 'var(--gold, #d4af37)' } : undefined}
    >
      {initial || '·'}
    </span>
  );
}

/* ── Profile dropdown header — name + email, non-interactive. Gives
   the user a quick "yes this is me" confirmation before they take any
   action in the menu (most importantly: sign-out). */
function ProfileHeader() {
  const { user } = useCurrentUser();
  if (!user?.email) {
    return (
      <div className="cm-nav__dropdown-header">
        <small style={{ color: 'var(--cm-slate)' }}>Signed in…</small>
      </div>
    );
  }
  const display = user.display_name || user.given_name || user.email.split('@')[0];
  return (
    <div className="cm-nav__dropdown-header">
      <strong style={{ display: 'block', fontSize: '0.92rem' }}>{display}</strong>
      <small style={{ color: 'var(--cm-slate)', fontSize: '0.74rem' }}>{user.email}</small>
    </div>
  );
}

/* Mobile drawer footer — same identity, slightly different layout */
function DrawerUser() {
  const { user } = useCurrentUser();
  if (!user?.email) return <>{' '}</>;
  const display = user.given_name
    || user.display_name?.split(' ')[0]
    || user.email.split('@')[0];
  return <>{display} </>;
}
