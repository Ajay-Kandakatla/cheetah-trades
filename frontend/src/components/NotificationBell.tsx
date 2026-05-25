/* NotificationBell — small dropdown of recent notifications next to the
 *  profile avatar in the NavBar.
 *
 *  Layout:
 *    [🔔ⁿ]  — bell icon + small badge with unread count
 *      └ on tap → dropdown with last 8 unified notifications
 *
 *  Data source: GET /notifications/recent (merges push_history +
 *  sepa_breakouts so volume breakouts and flashcards show up in one
 *  feed). Polls every 60s while mounted; the BreakoutAlertBanner's
 *  SSE bus would be nice to share but the data shape is different
 *  enough that a small poll is simpler.
 *
 *  "Unread" semantics: tracks the highest-seen `ts` in localStorage.
 *  Opening the dropdown marks everything currently visible as seen.
 *  Survives page reloads + nav changes.
 *
 *  Tap routing: each row's `url` opens via react-router. The dropdown
 *  closes on selection so the user lands cleanly on the destination.
 */
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { API } from '../lib/apiBase';

type FeedRow = {
  _id:        string;
  ts:         number;
  ts_iso:     string | null;
  title:      string;
  body:       string;
  kind:       string | null;
  ticker:     string | null;
  url:        string | null;
  source:     'push' | 'breakout';
  sent?:      number;
  total?:     number;
  dismissed?: boolean;
};

const LAST_SEEN_KEY = 'pounce.notif_bell.last_seen_ts';
const POLL_MS = 60_000;
const DROPDOWN_LIMIT = 8;
const FETCH_LIMIT = 25;

function loadLastSeen(): number {
  if (typeof window === 'undefined') return 0;
  try {
    const v = window.localStorage.getItem(LAST_SEEN_KEY);
    return v ? Number(v) : 0;
  } catch { return 0; }
}

function saveLastSeen(ts: number) {
  if (typeof window === 'undefined') return;
  try { window.localStorage.setItem(LAST_SEEN_KEY, String(ts)); } catch { /* */ }
}

function fmtAgo(ts: number): string {
  const sec = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (sec < 60)    return `${sec}s`;
  if (sec < 3600)  return `${Math.round(sec / 60)}m`;
  if (sec < 86400) return `${Math.round(sec / 3600)}h`;
  return `${Math.round(sec / 86400)}d`;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<FeedRow[]>([]);
  const [lastSeen, setLastSeen] = useState<number>(() => loadLastSeen());
  const containerRef = useRef<HTMLDivElement | null>(null);
  const location = useLocation();

  // Fetch + poll. Doesn't 401-redirect (the installAuthRedirect
  // monkeypatch handles credentials) so the dropdown stays empty
  // gracefully if the user isn't signed in instead of crashing.
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch(`${API}/notifications/recent?limit=${FETCH_LIMIT}`);
        if (!r.ok) return;
        const j = await r.json();
        if (cancelled) return;
        setRows((j?.rows || []) as FeedRow[]);
      } catch { /* silent — the bell isn't a critical path */ }
    };
    load();
    const id = window.setInterval(load, POLL_MS);
    return () => { cancelled = true; window.clearInterval(id); };
  }, []);

  // Outside-click to close the dropdown. Mirrors the pattern used by
  // the profile dropdown in the same NavBar.
  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onEsc);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onEsc);
    };
  }, [open]);

  // Close on route change so the dropdown doesn't linger after the
  // user taps a row and the page navigates.
  useEffect(() => { setOpen(false); }, [location.pathname]);

  const unreadCount = rows.filter((r) => (r.ts || 0) > lastSeen).length;
  const visible = rows.slice(0, DROPDOWN_LIMIT);

  const handleOpen = () => {
    setOpen((v) => !v);
    // Opening = mark everything currently visible as seen. We take the
    // MAX ts of the first row so any item that arrives during the next
    // poll is correctly flagged as "new" relative to this open event.
    if (!open && rows.length > 0) {
      const newest = rows[0].ts || 0;
      setLastSeen(newest);
      saveLastSeen(newest);
    }
  };

  return (
    <div ref={containerRef} className="cm-nav__bell" style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={handleOpen}
        aria-label={`Notifications${unreadCount ? ` (${unreadCount} new)` : ''}`}
        aria-expanded={open}
        title={unreadCount > 0 ? `${unreadCount} new notification${unreadCount === 1 ? '' : 's'}` : 'Notifications'}
        style={{
          background: 'transparent',
          border: '1px solid rgba(255,255,255,0.12)',
          color: unreadCount > 0 ? '#d4af37' : '#cfcfd4',
          padding: '4px 9px',
          borderRadius: 6,
          fontSize: '0.95rem',
          fontFamily: 'inherit',
          cursor: 'pointer',
          position: 'relative',
          lineHeight: 1,
        }}
      >
        🔔
        {unreadCount > 0 && (
          <span
            aria-hidden="true"
            style={{
              position: 'absolute',
              top: -4, right: -4,
              minWidth: 16, height: 16, padding: '0 4px',
              borderRadius: 8,
              background: '#d4af37',
              color: '#1a1a1a',
              fontSize: '0.62rem',
              fontWeight: 700,
              lineHeight: '16px',
              textAlign: 'center',
              border: '1px solid #141416',
            }}
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Recent notifications"
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: 0,
            zIndex: 1000,
            width: 'min(360px, calc(100vw - 24px))',
            maxHeight: '70vh',
            overflowY: 'auto',
            background: '#141416',
            color: '#e6e6e6',
            border: '1px solid rgba(212,175,55,0.35)',
            borderRadius: 10,
            boxShadow: '0 14px 40px rgba(0,0,0,0.55)',
          }}
        >
          <div style={{
            position: 'sticky', top: 0, zIndex: 1,
            display: 'flex', alignItems: 'baseline',
            justifyContent: 'space-between',
            padding: '0.55rem 0.75rem',
            background: 'rgba(212,175,55,0.08)',
            borderBottom: '1px solid rgba(255,255,255,0.07)',
          }}>
            <div>
              <div style={{
                fontSize: '0.62rem', color: '#d4af37',
                letterSpacing: '0.1em', fontWeight: 700,
                textTransform: 'uppercase',
              }}>
                🔔 Recent · {rows.length} loaded
              </div>
              <div style={{ fontSize: '0.66rem', color: '#9a9aa3', marginTop: 1 }}>
                Pushes + volume breakouts in one feed.
              </div>
            </div>
            <Link
              to="/notifications"
              onClick={() => setOpen(false)}
              style={{
                fontSize: '0.7rem',
                color: '#9aa8c8',
                textDecoration: 'none',
                padding: '3px 8px',
                border: '1px solid rgba(154,168,200,0.3)',
                borderRadius: 4,
                whiteSpace: 'nowrap',
              }}
            >
              See all →
            </Link>
          </div>

          {visible.length === 0 && (
            <div style={{
              padding: '0.9rem 0.9rem',
              fontSize: '0.8rem',
              color: '#9a9aa3',
              lineHeight: 1.5,
            }}>
              No notifications yet. Pushes (flashcards, breakouts, morning brief)
              and volume breakouts will appear here as they fire.
            </div>
          )}

          <div>
            {visible.map((r) => {
              const isUnread = (r.ts || 0) > lastSeen;
              const rowStyle: React.CSSProperties = {
                display: 'block',
                padding: '0.45rem 0.75rem',
                borderBottom: '1px solid rgba(255,255,255,0.05)',
                background: isUnread ? 'rgba(212,175,55,0.04)' : 'transparent',
                color: 'inherit',
                textDecoration: 'none',
              };
              const inner = (
                <>
                  <div style={{
                    display: 'flex', justifyContent: 'space-between',
                    alignItems: 'baseline', gap: '0.4rem',
                  }}>
                    <div style={{
                      fontSize: '0.84rem', fontWeight: 600,
                      lineHeight: 1.3,
                      overflow: 'hidden', textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      flex: 1, minWidth: 0,
                    }}>
                      {isUnread && (
                        <span style={{
                          display: 'inline-block', width: 6, height: 6,
                          borderRadius: 3, background: '#d4af37',
                          marginRight: 6, verticalAlign: 'middle',
                        }} />
                      )}
                      {r.title}
                    </div>
                    <div style={{ fontSize: '0.66rem', color: '#6a6a72', whiteSpace: 'nowrap' }}>
                      {fmtAgo(r.ts || 0)}
                    </div>
                  </div>
                  {r.body && (
                    <div style={{
                      fontSize: '0.74rem',
                      color: '#cfcfd4',
                      marginTop: 2,
                      lineHeight: 1.4,
                      // Clamp to 2 lines in the bell. /notifications shows full.
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}>
                      {r.body}
                    </div>
                  )}
                  <div style={{ fontSize: '0.6rem', color: '#6a6a72', marginTop: 2 }}>
                    {r.source === 'breakout'
                      ? (r.dismissed ? 'breakout · dismissed' : 'breakout · active')
                      : 'push'}
                  </div>
                </>
              );
              // In-app link if URL is relative, otherwise plain div.
              if (r.url && r.url.startsWith('/')) {
                return (
                  <Link key={r._id} to={r.url} onClick={() => setOpen(false)} style={rowStyle}>
                    {inner}
                  </Link>
                );
              }
              return <div key={r._id} style={rowStyle}>{inner}</div>;
            })}
          </div>
        </div>
      )}
    </div>
  );
}
