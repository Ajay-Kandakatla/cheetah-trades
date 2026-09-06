import { useEffect, useRef, useState, Fragment } from 'react';
import { useStickyTop } from '../hooks/useStickyTop';
import { NavLink, useLocation } from 'react-router-dom';
import { ThemeToggle } from './ThemeToggle';
import { NotificationBell } from './NotificationBell';
import { useCurrentUser } from '../hooks/useUser';
import { useMyMenu, type MenuItem } from '../hooks/useMyMenu';
import { NavLabel } from './NavLabel';
import { MarketGaugeBadge } from './MarketGaugeBadge';
import { IvBadge } from './IvBadge';
import { ScanHealthChip } from './ScanHealthChip';
import { MarketPostureBanner } from './MarketPostureBanner';
import { GlobalSearch } from './GlobalSearch';
import { openRail } from '../lib/railBus';

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

// The old "Misc" dropdown was a 15-item junk drawer (UX teardown #4: "no
// destination named Misc; section by JOB so a friend can predict the contents").
// We keep ONE "Tools" dropdown but render it under named job sub-headers so it's
// navigable by label. Maps feature id → sub-group; unknown ids fall to "More".
const TOOLS_SUBGROUP: Record<string, string> = {
  trading: 'Trade',
  'day-trading': 'Screeners', scalping: 'Screeners', patterns: 'Screeners', 'supply-demand': 'Screeners',
  'signal-lab': 'Screeners',
  'demand-zones': 'Zones', zones: 'Zones',
  live: 'Tape', chatter: 'Tape', 'chatter-india': 'Tape',
  'market-gauge': 'Signals', catalysts: 'Signals', options: 'Signals', 'gex-board': 'Signals', track: 'Signals', pankaj: 'Signals',
  // Research moved out of the primary bar 2026-08-16 to make room for Chart
  // Maps. Without an entry here it would drop into the catch-all 'More'
  // bucket; it is analysis, so it sits with the other Signals pages.
  research: 'Signals',
  // /alerts (2026-09-05) is the phone's log — what the zone passes pushed and
  // what the gate skipped. It reads a signal surface, so it sits with them.
  alerts: 'Signals',
  food: 'Life', kids: 'Life', volleyball: 'Life', house: 'Life',
};
const SUBGROUP_ORDER = ['Trade', 'Screeners', 'Zones', 'Tape', 'Signals', 'Life', 'More'];
// The ⌘K palette (GlobalSearch) names its group chips from the same map, so
// "Tools ▸ Signals" in the search reads exactly like the dropdown header.
const toolsSubgroupOf = (feature?: string): string => TOOLS_SUBGROUP[feature ?? ''] ?? 'More';

function groupTools(items: MenuItem[]): Array<{ label: string; items: MenuItem[] }> {
  const buckets = new Map<string, MenuItem[]>();
  for (const it of items) {
    const g = TOOLS_SUBGROUP[it.feature ?? ''] ?? 'More';
    if (!buckets.has(g)) buckets.set(g, []);
    buckets.get(g)!.push(it);
  }
  return SUBGROUP_ORDER.filter((g) => buckets.has(g)).map((g) => ({ label: g, items: buckets.get(g)! }));
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
  // Market Gauge badge (top-right, every page) — only when the user has access.
  const hasGauge = [...menu.primary, ...menu.misc].some((t) => t.feature === 'market-gauge');
  // Mobile-only entry points for the floating rails. On phones the rails' fixed
  // edge tabs are hidden (they overlapped page content), so the NavBar action
  // bar is the way to open them (Ajay 2026-06-16). Shown only for users who
  // actually have the feature — same gate as the rails / routes.
  const railFeature = (id: string) =>
    [...menu.primary, ...menu.scanners, ...menu.misc, ...menu.profile].some((t) => t.feature === id);
  const hasWatchlist = railFeature('watchlist');
  const hasPortfolio = railFeature('portfolio');

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
  /* Phone nav is sticky (navbar.css) — publish its height as --sticky-top so
   * sticky table headers sit under it instead of behind it (2026-09-02). */
  const mobileBarRef = useRef<HTMLElement>(null);
  useStickyTop(mobileBarRef, isMobile);

  if (isMobile) {
    return (
      <>
      <header className="cm-nav cm-nav--mobile" ref={mobileBarRef}>
        <div className="cm-nav__brand">
          <div className="cm-nav__wordmark">Pounce</div>
          {currentTab && <div className="cm-nav__current">· {currentTab.label}</div>}
        </div>

        <div className="cm-nav__mobile-actions">
          {hasGauge && <MarketGaugeBadge compact />}
          {hasGauge && <IvBadge compact />}
          <ScanHealthChip compact />
          <GlobalSearch compact subgroupOf={toolsSubgroupOf} />
          {hasPortfolio && (
            <button
              type="button"
              className="cm-nav__rail-btn"
              onClick={() => openRail('portfolio')}
              aria-label="Open portfolio"
              title="Portfolio"
            >
              💼
            </button>
          )}
          {hasWatchlist && (
            <button
              type="button"
              className="cm-nav__rail-btn"
              onClick={() => openRail('watchlist')}
              aria-label="Open watchlist"
              title="Watchlist"
            >
              ⭐
            </button>
          )}
          <button
            type="button"
            className={`cm-nav__hamburger${drawerOpen ? ' is-open' : ''}`}
            onClick={() => setDrawerOpen(!drawerOpen)}
            aria-label={drawerOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={drawerOpen}
          >
            <span /><span /><span />
          </button>
        </div>

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
                      <NavLabel item={t} />
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
                      <NavLabel item={t} />
                    </NavLink>
                  ))}
                </>
              )}
              {SECONDARY_VISIBLE.length > 0 && (
                <>
                  <div className="cm-nav__drawer-section-label">Tools</div>
                  {groupTools(SECONDARY_VISIBLE).map((grp) => (
                    <Fragment key={grp.label}>
                      <div className="cm-nav__drawer-subgroup-label">{grp.label}</div>
                      {grp.items.map((t) => (
                        <NavLink
                          key={t.to}
                          to={t.to}
                          className={({ isActive }) => `cm-nav__drawer-link${isActive ? ' is-active' : ''}`}
                          onClick={() => setDrawerOpen(false)}
                        >
                          <NavLabel item={t} />
                        </NavLink>
                      ))}
                    </Fragment>
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
                      <NavLabel item={t} />
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
      {/* Market-correction posture floats at the BOTTOM on mobile so its wide
          label never crowds the hamburger out of the top nav row (2026-06-25). */}
      <MarketPostureBanner placement="bottom" />
      </>
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
            <NavLabel item={t} />
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
                    <NavLabel item={t} />
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
              Tools <span className="cm-nav__caret">▾</span>
            </button>
            {moreOpen && (
              <div className="cm-nav__dropdown" role="menu">
                {groupTools(SECONDARY_VISIBLE).map((grp) => (
                  <Fragment key={grp.label}>
                    <div className="cm-nav__dropdown-grouplabel">{grp.label}</div>
                    {grp.items.map((t) => (
                      <NavLink
                        key={t.to}
                        to={t.to}
                        className={({ isActive }) => `cm-nav__dropdown-link${isActive ? ' is-active' : ''}`}
                        role="menuitem"
                      >
                        <NavLabel item={t} />
                      </NavLink>
                    ))}
                  </Fragment>
                ))}
              </div>
            )}
          </div>
        )}
      </nav>

      <div className="cm-nav__meta">
        <MarketPostureBanner />
        {hasGauge && <MarketGaugeBadge />}
        {/* Implied-volatility read beside the gauge (Ajay 2026-09-06). */}
        {hasGauge && <IvBadge />}
        {/* Are-all-scans-OK count (Ajay 2026-08-25) — links to /health. */}
        <ScanHealthChip />
        <span className="cm-nav__meta-date mono">{TODAY}</span>
        <ThemeToggle />
        {/* ⌘K search over every menu entry (Ajay 2026-09-06). */}
        <GlobalSearch subgroupOf={toolsSubgroupOf} />
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
                  <NavLabel item={t} />
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
