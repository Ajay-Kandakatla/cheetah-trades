/* PortfolioRail — a persistent, hideable LIVE portfolio drawer on every page
 * (Ajay 2026-06-13: "Add a floating Portfolio also that is live. Like watch list
 * and hideable").
 *
 * Sibling of WatchlistRail, mounted once in App.tsx. Mirrors its behaviour —
 * collapsed edge tab, slide-in drawer on mobile, draggable floating card on
 * desktop, open state + position persisted — but docks to the LEFT edge so the
 * two rails never overlap, and shows holdings with live value + P&L instead of
 * watchlist quotes.
 *
 * Live: useHoldings() silently refreshes every 60s (quotes have a 60s TTL), so
 * value / P&L / today's move update on their own while the rail is open. We only
 * mount the fetch when the rail is open (enabled=open) to keep collapsed pages
 * free of the heavy holdings call. Gated to users who actually have the
 * portfolio feature. Hidden on the auth pages. */
import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useHoldings, type HoldingRow } from '../hooks/usePortfolio';
import { useMyFeatures } from '../hooks/useMyFeatures';
import { TickerLink } from './TickerLink';
import { RAIL_OPEN_EVENT, type RailName } from '../lib/railBus';

const C = { green: '#10b981', red: '#ef4444', muted: '#94a3b8', sub: '#8a93a6' };
const MOBILE_MQ = '(max-width: 768px)';

function isMobileNow() {
  return typeof window !== 'undefined' && window.matchMedia(MOBILE_MQ).matches;
}

function fmtMoney(n: number | null | undefined): string {
  if (n == null) return '—';
  return `$${Math.round(n).toLocaleString()}`;
}

function Row({ h }: { h: HoldingRow }) {
  const plPct = h.pl_pct;
  const plUp = (plPct ?? 0) >= 0;
  const day = h.day_change_pct;
  const dayUp = (day ?? 0) >= 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 2px',
                  borderTop: '1px solid var(--hairline,#2a2a2a)' }}>
      <div style={{ minWidth: 0, flex: 1 }}>
        <TickerLink ticker={h.symbol} showWatchlist={false} title={h.name || h.symbol}
                    style={{ fontWeight: 700, fontSize: '0.82rem', color: 'inherit', textDecoration: 'none' }}>
          {h.symbol}
        </TickerLink>
        <div style={{ fontSize: '0.62rem', color: C.sub, whiteSpace: 'nowrap',
                      overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.15 }}>
          {h.quantity != null ? `${h.quantity} sh` : ''}
          {day != null && (
            <span style={{ color: dayUp ? C.green : C.red, marginLeft: 6 }}>
              {dayUp ? '▲' : '▼'} {Math.abs(day).toFixed(2)}% today
            </span>
          )}
        </div>
      </div>
      <div className="mono" style={{ textAlign: 'right', fontSize: '0.76rem', minWidth: 72 }}>
        <div style={{ fontWeight: 600 }}>{fmtMoney(h.current_value)}</div>
        {plPct != null && (
          <div style={{ color: plUp ? C.green : C.red, fontSize: '0.68rem' }}>
            {plUp ? '▲' : '▼'} {Math.abs(plPct).toFixed(1)}%
          </div>
        )}
      </div>
    </div>
  );
}

export function PortfolioRail() {
  const loc = useLocation();
  const feat = useMyFeatures();

  const [isMobile, setIsMobile] = useState(isMobileNow);
  const [open, setOpen] = useState<boolean>(() => {
    try {
      const s = localStorage.getItem('pf_rail_open');
      if (s === '1') return true;
      if (s === '0') return false;
    } catch { /* ignore */ }
    return false;   // default closed — portfolio is opt-in glance, don't cover the page
  });

  // Only run the heavy holdings fetch while the rail is open.
  const { data, updatedAt } = useHoldings(open);

  // Desktop free-float position {x,y}; null = docked to the LEFT edge.
  const [pos, setPos] = useState<{ x: number; y: number } | null>(() => {
    try { const s = localStorage.getItem('pf_rail_pos'); return s ? JSON.parse(s) : null; } catch { return null; }
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
    try { localStorage.setItem('pf_rail_open', open ? '1' : '0'); } catch { /* ignore */ }
  }, [open]);

  // Open on request from the NavBar's mobile action bar — the collapsed edge
  // tab is hidden on phones (it overlapped page content), so this is the way
  // in (Ajay 2026-06-16).
  useEffect(() => {
    const h = (e: Event) => {
      if ((e as CustomEvent<RailName>).detail === 'portfolio') setOpen(true);
    };
    window.addEventListener(RAIL_OPEN_EVENT, h);
    return () => window.removeEventListener(RAIL_OPEN_EVENT, h);
  }, []);

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
      try { if (p) localStorage.setItem('pf_rail_pos', JSON.stringify(p)); } catch { /* ignore */ }
      return p;
    });
  };
  const onDragStart = (e: React.PointerEvent) => {
    if (isMobile || !panelRef.current) return;
    const r = panelRef.current.getBoundingClientRect();
    drag.current = { dx: e.clientX - r.left, dy: e.clientY - r.top };
    if (!pos) setPos({ x: r.left, y: r.top });
    window.addEventListener('pointermove', onDragMove);
    window.addEventListener('pointerup', onDragEnd);
  };
  const redock = () => {
    setPos(null);
    try { localStorage.removeItem('pf_rail_pos'); } catch { /* ignore */ }
  };

  // Gate: hide on auth pages and for users without portfolio access.
  if (loc.pathname === '/signin' || loc.pathname === '/signup') return null;
  if (feat.loaded && !feat.features.has('portfolio')) return null;

  const rows = [...(data?.rows ?? [])].sort(
    (a, b) => (b.current_value ?? 0) - (a.current_value ?? 0),
  );
  const totalValue = rows.reduce((s, r) => s + (r.current_value ?? 0), 0);
  const totalCost = rows.reduce(
    (s, r) => s + (r.cost_basis ?? (r.avg_cost != null && r.quantity != null ? r.avg_cost * r.quantity : 0)),
    0,
  );
  const totalPL = rows.reduce((s, r) => s + (r.pl_dollars ?? 0), 0);
  const totalPLpct = totalCost > 0 ? (totalPL / totalCost) * 100 : null;
  const plUp = totalPL >= 0;

  // Collapsed edge tab (LEFT edge). Desktop only — on phones the fixed vertical
  // tab sat ON TOP of dense tables (covered the breakouts row numbers), so it's
  // hidden and opened from the NavBar instead.
  if (!open) {
    if (isMobile) return null;
    return (
      <button onClick={() => setOpen(true)} aria-label="Open portfolio"
              className="pf-rail__tab"
              style={{ position: 'fixed', left: 0, top: '40%', zIndex: 900,
                       transform: 'translateY(-50%)', writingMode: 'vertical-rl',
                       background: 'var(--bg-raised,#16181d)', color: 'inherit',
                       border: '1px solid var(--hairline,#2a2a2a)', borderLeft: 'none',
                       borderRadius: '0 8px 8px 0', padding: '10px 5px', cursor: 'pointer',
                       fontSize: '0.74rem', fontWeight: 700, letterSpacing: '0.04em',
                       boxShadow: '2px 0 10px rgba(0,0,0,0.25)' }}>
        💼 Portfolio{totalPLpct != null ? ` · ${plUp ? '+' : ''}${totalPLpct.toFixed(1)}%` : ''}
      </button>
    );
  }

  const floating = !isMobile && pos != null;
  const panelStyle: React.CSSProperties = isMobile
    ? { position: 'fixed', left: 0, top: 0, bottom: 0, width: 'min(300px, 82vw)',
        borderRadius: '0 12px 12px 0',
        transform: open ? 'translateX(0)' : 'translateX(-105%)',
        transition: 'transform 0.25s ease' }
    : floating
      ? { position: 'fixed', left: pos!.x, top: pos!.y, width: 300,
          maxHeight: 'min(560px, 80vh)', borderRadius: 12 }
      : { position: 'fixed', left: 0, top: 64, width: 300,
          maxHeight: 'calc(100vh - 88px)', borderRadius: '0 12px 12px 0' };

  return (
    <>
      {isMobile && (
        <div onClick={() => setOpen(false)} aria-hidden
             style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.45)' }} />
      )}
      <aside ref={panelRef as any} className="pf-rail"
             style={{ zIndex: isMobile ? 1001 : 900, display: 'flex', flexDirection: 'column',
                      background: 'var(--bg-raised,#16181d)', color: 'var(--ink,inherit)',
                      border: '1px solid var(--hairline,#2a2a2a)',
                      borderLeft: isMobile || floating ? '1px solid var(--hairline,#2a2a2a)' : 'none',
                      boxShadow: '4px 0 18px rgba(0,0,0,0.4)', ...panelStyle }}>
        <div onPointerDown={onDragStart} onDoubleClick={floating ? redock : undefined}
             style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0.55rem 0.65rem',
                      borderBottom: '1px solid var(--hairline,#2a2a2a)',
                      cursor: isMobile ? 'default' : 'move', touchAction: 'none' }}
             title={isMobile ? undefined : 'Drag to move · double-click to re-dock'}>
          {!isMobile && <span aria-hidden style={{ color: C.sub, fontSize: '0.8rem', marginRight: -2 }}>⠿</span>}
          <span style={{ fontWeight: 700, fontSize: '0.82rem' }}>💼 Portfolio</span>
          {data && <span aria-hidden title={updatedAt ? `Updated ${new Date(updatedAt).toLocaleTimeString()}` : 'Live'}
                         style={{ color: C.green, fontSize: '0.55rem' }}>● live</span>}
          <a href="/portfolio" onPointerDown={(e) => e.stopPropagation()}
             style={{ marginLeft: 'auto', fontSize: '0.68rem', color: C.muted, textDecoration: 'none' }}
             title="Open the full portfolio page">full ↗</a>
          <button onClick={() => setOpen(false)} onPointerDown={(e) => e.stopPropagation()}
                  aria-label="Hide portfolio" title="Hide"
                  style={{ background: 'transparent', border: 'none', color: C.sub, cursor: 'pointer',
                           fontSize: '1rem', lineHeight: 1, padding: '0 2px' }}>
            {isMobile ? '✕' : '‹'}
          </button>
        </div>

        {/* Totals strip */}
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
                      gap: 8, padding: '0.5rem 0.65rem', borderBottom: '1px solid var(--hairline,#2a2a2a)' }}>
          <span className="mono" style={{ fontSize: '0.95rem', fontWeight: 700 }}>{fmtMoney(totalValue)}</span>
          {totalPLpct != null && (
            <span className="mono" style={{ color: plUp ? C.green : C.red, fontSize: '0.8rem', fontWeight: 600 }}>
              {plUp ? '▲' : '▼'} {fmtMoney(Math.abs(totalPL))} ({plUp ? '+' : ''}{totalPLpct.toFixed(1)}%)
            </span>
          )}
        </div>

        <div style={{ overflowY: 'auto', padding: '0 0.65rem 0.5rem', flex: 1 }}>
          {rows.length === 0 ? (
            <p style={{ color: C.sub, fontSize: '0.74rem', padding: '0.6rem 0' }}>
              No holdings yet — add them on the <a href="/portfolio" style={{ color: C.muted }}>Portfolio page</a>.
            </p>
          ) : (
            rows.map((h) => <Row key={h.symbol} h={h} />)
          )}
        </div>
      </aside>
    </>
  );
}
