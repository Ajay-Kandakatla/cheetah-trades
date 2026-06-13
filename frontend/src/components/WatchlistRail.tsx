/* WatchlistRail — a persistent watchlist drawer on EVERY page (Ajay 2026-06-11:
 * "I need watch list to be shown on all pages like StockTwits").
 *
 * Mounted once in App.tsx as a floating, dismissible drawer (sibling of the
 * chat widget + alert banner). Reuses useWatchlist (add/remove/rows) +
 * useLiveQuote for live price + day%.
 *
 * 2026-06-12 (Ajay: "covering the entire page… make it slidable and hidable…
 * on desktop make it floatable and hidable too"):
 *   - MOBILE: a right-side slide-in drawer that is HIDDEN by default, slides
 *     away off-screen, and dims the page behind it with a tap-to-dismiss
 *     backdrop. It no longer blankets the whole screen on load.
 *   - DESKTOP: a floating card you can DRAG anywhere (grip the header), collapse
 *     to a slim edge tab, and that remembers both open state and position.
 * Open state persists in localStorage; on phones it stays closed unless you've
 * explicitly opened it. Hidden on the auth pages. */
import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useWatchlist } from '../hooks/useWatchlist';
import { useLiveQuote } from '../hooks/useLiveQuote';
import { TickerLink } from './TickerLink';

const C = { green: '#10b981', red: '#ef4444', muted: '#94a3b8', sub: '#8a93a6' };
const MOBILE_MQ = '(max-width: 768px)';

function isMobileNow() {
  return typeof window !== 'undefined' && window.matchMedia(MOBILE_MQ).matches;
}

function Row({ ticker, name, onRemove }: { ticker: string; name?: string | null; onRemove: () => void }) {
  const q = useLiveQuote(ticker);
  const px = q?.last_price;
  const chg = q?.day_pct;
  const up = (chg ?? 0) >= 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 2px',
                  borderTop: '1px solid var(--hairline,#2a2a2a)' }}>
      <div style={{ minWidth: 0, flex: 1 }}>
        <TickerLink ticker={ticker} showWatchlist={false} title={name || ticker}
                    style={{ fontWeight: 700, fontSize: '0.82rem', color: 'inherit', textDecoration: 'none' }}>
          {ticker}
        </TickerLink>
        {name && (
          <div style={{ fontSize: '0.6rem', color: C.sub, whiteSpace: 'nowrap',
                        overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.1 }}>{name}</div>
        )}
      </div>
      <div className="mono" style={{ textAlign: 'right', fontSize: '0.76rem', minWidth: 64 }}>
        <div style={{ fontWeight: 600 }}>{px != null ? `$${px.toFixed(2)}` : '—'}</div>
        {chg != null && (
          <div style={{ color: up ? C.green : C.red, fontSize: '0.68rem' }}>
            {up ? '▲' : '▼'} {Math.abs(chg).toFixed(2)}%
          </div>
        )}
      </div>
      <button onClick={onRemove} aria-label={`Remove ${ticker} from watchlist`} title="Remove from watchlist"
              style={{ background: 'transparent', border: 'none', color: C.sub, cursor: 'pointer',
                       fontSize: '0.9rem', lineHeight: 1, padding: '4px 6px' }}>×</button>
    </div>
  );
}

export function WatchlistRail() {
  const loc = useLocation();
  const { rows, add, remove } = useWatchlist();

  const [isMobile, setIsMobile] = useState(isMobileNow);
  const [open, setOpen] = useState<boolean>(() => {
    try {
      const s = localStorage.getItem('wl_rail_open');
      if (s === '1') return true;
      if (s === '0') return false;
    } catch { /* ignore */ }
    // No saved preference: open on desktop, closed on phones (don't cover the page).
    return !isMobileNow();
  });
  const [draft, setDraft] = useState('');

  // Desktop free-float position {x,y}; null = docked to the right edge.
  const [pos, setPos] = useState<{ x: number; y: number } | null>(() => {
    try { const s = localStorage.getItem('wl_rail_pos'); return s ? JSON.parse(s) : null; } catch { return null; }
  });
  const panelRef = useRef<HTMLElement | null>(null);
  const drag = useRef<{ dx: number; dy: number } | null>(null);

  useEffect(() => {
    const m = window.matchMedia(MOBILE_MQ);
    const h = () => setIsMobile(m.matches);
    m.addEventListener('change', h);
    return () => m.removeEventListener('change', h);
  }, []);

  useEffect(() => {
    try { localStorage.setItem('wl_rail_open', open ? '1' : '0'); } catch { /* ignore */ }
  }, [open]);

  // ── Desktop drag-to-float ──────────────────────────────────────────────
  const onDragMove = (e: PointerEvent) => {
    if (!drag.current || !panelRef.current) return;
    const w = panelRef.current.offsetWidth;
    const h = panelRef.current.offsetHeight;
    const x = Math.max(8, Math.min(e.clientX - drag.current.dx, window.innerWidth - w - 8));
    const y = Math.max(8, Math.min(e.clientY - drag.current.dy, window.innerHeight - h - 8));
    setPos({ x, y });
  };
  const onDragEnd = () => {
    drag.current = null;
    window.removeEventListener('pointermove', onDragMove);
    window.removeEventListener('pointerup', onDragEnd);
    setPos((p) => {
      try { if (p) localStorage.setItem('wl_rail_pos', JSON.stringify(p)); } catch { /* ignore */ }
      return p;
    });
  };
  const onDragStart = (e: React.PointerEvent) => {
    if (isMobile || !panelRef.current) return;            // no drag on phones
    const r = panelRef.current.getBoundingClientRect();
    drag.current = { dx: e.clientX - r.left, dy: e.clientY - r.top };
    if (!pos) setPos({ x: r.left, y: r.top });            // adopt current spot, then float
    window.addEventListener('pointermove', onDragMove);
    window.addEventListener('pointerup', onDragEnd);
  };
  const redock = () => {
    setPos(null);
    try { localStorage.removeItem('wl_rail_pos'); } catch { /* ignore */ }
  };

  // Don't intrude on the auth pages.
  if (loc.pathname === '/signin' || loc.pathname === '/signup') return null;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = draft.trim().toUpperCase();
    if (t) { add(t); setDraft(''); }
  };

  // Collapsed edge tab.
  if (!open) {
    return (
      <button onClick={() => setOpen(true)} aria-label="Open watchlist"
              className="wl-rail__tab"
              style={{ position: 'fixed', right: 0, top: '40%', zIndex: 900,
                       transform: 'translateY(-50%)', writingMode: 'vertical-rl',
                       background: 'var(--bg-raised,#16181d)', color: 'inherit',
                       border: '1px solid var(--hairline,#2a2a2a)', borderRight: 'none',
                       borderRadius: '8px 0 0 8px', padding: '10px 5px', cursor: 'pointer',
                       fontSize: '0.74rem', fontWeight: 700, letterSpacing: '0.04em',
                       boxShadow: '-2px 0 10px rgba(0,0,0,0.25)' }}>
        ⭐ Watchlist{rows.length ? ` · ${rows.length}` : ''}
      </button>
    );
  }

  const floating = !isMobile && pos != null;
  const panelStyle: React.CSSProperties = isMobile
    ? { position: 'fixed', right: 0, top: 0, bottom: 0, width: 'min(290px, 80vw)',
        borderRadius: '12px 0 0 12px',
        transform: open ? 'translateX(0)' : 'translateX(105%)',
        transition: 'transform 0.25s ease' }
    : floating
      ? { position: 'fixed', left: pos!.x, top: pos!.y, width: 290,
          maxHeight: 'min(560px, 80vh)', borderRadius: 12 }
      : { position: 'fixed', right: 0, top: 64, width: 290,
          maxHeight: 'calc(100vh - 88px)', borderRadius: '12px 0 0 12px' };

  return (
    <>
      {isMobile && (
        <div onClick={() => setOpen(false)} aria-hidden
             style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.45)' }} />
      )}
      <aside ref={panelRef as any} className="wl-rail"
             style={{ zIndex: isMobile ? 1001 : 900, display: 'flex', flexDirection: 'column',
                      background: 'var(--bg-raised,#16181d)', color: 'var(--ink,inherit)',
                      border: '1px solid var(--hairline,#2a2a2a)',
                      borderRight: isMobile || floating ? '1px solid var(--hairline,#2a2a2a)' : 'none',
                      boxShadow: '-4px 0 18px rgba(0,0,0,0.4)', ...panelStyle }}>
        <div onPointerDown={onDragStart} onDoubleClick={floating ? redock : undefined}
             style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0.55rem 0.65rem',
                      borderBottom: '1px solid var(--hairline,#2a2a2a)',
                      cursor: isMobile ? 'default' : 'move', touchAction: 'none' }}
             title={isMobile ? undefined : 'Drag to move · double-click to re-dock'}>
          {!isMobile && <span aria-hidden style={{ color: C.sub, fontSize: '0.8rem', marginRight: -2 }}>⠿</span>}
          <span style={{ fontWeight: 700, fontSize: '0.82rem' }}>⭐ Watchlist</span>
          <span className="mono" style={{ fontSize: '0.68rem', color: C.sub }}>{rows.length}</span>
          <a href="/watchlist" onPointerDown={(e) => e.stopPropagation()}
             style={{ marginLeft: 'auto', fontSize: '0.68rem', color: C.muted, textDecoration: 'none' }}
             title="Open the full watchlist page">full ↗</a>
          <button onClick={() => setOpen(false)} onPointerDown={(e) => e.stopPropagation()}
                  aria-label="Hide watchlist" title="Hide"
                  style={{ background: 'transparent', border: 'none', color: C.sub, cursor: 'pointer',
                           fontSize: '1rem', lineHeight: 1, padding: '0 2px' }}>
            {isMobile ? '✕' : '›'}
          </button>
        </div>

        <div style={{ overflowY: 'auto', padding: '0 0.65rem', flex: 1 }}>
          {rows.length === 0 ? (
            <p style={{ color: C.sub, fontSize: '0.74rem', padding: '0.6rem 0' }}>
              Empty — tap the ☆ on any buyable or earnings name, or add one below.
            </p>
          ) : (
            rows.map((r) => (
              <Row key={r.ticker} ticker={r.ticker} name={r.research?.name}
                   onRemove={() => remove(r.ticker)} />
            ))
          )}
        </div>

        <form onSubmit={submit} style={{ display: 'flex', gap: 4, padding: '0.5rem 0.65rem',
                                         paddingBottom: 'max(env(safe-area-inset-bottom), 0.5rem)',
                                         borderTop: '1px solid var(--hairline,#2a2a2a)' }}>
          <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="+ add ticker"
                 style={{ flex: 1, minWidth: 0, fontSize: '0.78rem', padding: '4px 8px', borderRadius: 6,
                          background: 'var(--bg-sunken,#0f1115)', color: 'inherit',
                          border: '1px solid var(--hairline,#2a2a2a)' }} />
          <button type="submit" className="mono"
                  style={{ fontSize: '0.74rem', padding: '4px 10px', borderRadius: 6, cursor: 'pointer',
                           background: 'var(--gold,#c9a227)', color: '#1a1a1a', border: 'none' }}>add</button>
        </form>
      </aside>
    </>
  );
}
