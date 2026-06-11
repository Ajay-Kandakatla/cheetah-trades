/* WatchlistRail — a persistent, collapsible watchlist on EVERY page (Ajay
 * 2026-06-11: "I need watch list to be shown on all pages like StockTwits").
 *
 * Mounted once in App.tsx as a floating right-edge drawer (sibling of the
 * chat widget + alert banner), so it rides along on every route without
 * restructuring each page's layout. Reuses the existing useWatchlist store
 * (add/remove/rows) + useLiveQuote for live price + day%. Open/closed is
 * remembered in localStorage. Each row links to the ticker page, shows the
 * live quote, and has an × to remove (which is what "move it off to the
 * watchlist page" means — it leaves the rail, still on /watchlist). */
import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useWatchlist } from '../hooks/useWatchlist';
import { useLiveQuote } from '../hooks/useLiveQuote';
import { TickerLink } from './TickerLink';

const C = { green: '#10b981', red: '#ef4444', muted: '#94a3b8', sub: '#8a93a6' };

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
  const [open, setOpen] = useState<boolean>(() => {
    try { return localStorage.getItem('wl_rail_open') !== '0'; } catch { return true; }
  });
  const [draft, setDraft] = useState('');

  useEffect(() => {
    try { localStorage.setItem('wl_rail_open', open ? '1' : '0'); } catch { /* ignore */ }
  }, [open]);

  // Don't intrude on the auth pages.
  if (loc.pathname === '/signin' || loc.pathname === '/signup') return null;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = draft.trim().toUpperCase();
    if (t) { add(t); setDraft(''); }
  };

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} aria-label="Open watchlist"
              className="wl-rail__tab"
              style={{ position: 'fixed', right: 0, top: '40%', zIndex: 900,
                       transform: 'translateY(-50%)', writingMode: 'vertical-rl',
                       background: 'var(--bg-raised,#16181d)', color: 'inherit',
                       border: '1px solid var(--hairline,#2a2a2a)', borderRight: 'none',
                       borderRadius: '8px 0 0 8px', padding: '10px 5px', cursor: 'pointer',
                       fontSize: '0.74rem', fontWeight: 700, letterSpacing: '0.04em' }}>
        ⭐ Watchlist{rows.length ? ` · ${rows.length}` : ''}
      </button>
    );
  }

  return (
    <aside className="wl-rail"
           style={{ position: 'fixed', right: 0, top: 64, zIndex: 900,
                    width: 'min(280px, 86vw)', maxHeight: 'calc(100vh - 88px)',
                    display: 'flex', flexDirection: 'column',
                    background: 'var(--bg-raised,#16181d)', color: 'var(--ink,inherit)',
                    border: '1px solid var(--hairline,#2a2a2a)', borderRight: 'none',
                    borderRadius: '10px 0 0 10px', boxShadow: '-4px 0 18px rgba(0,0,0,0.35)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '0.55rem 0.65rem',
                    borderBottom: '1px solid var(--hairline,#2a2a2a)' }}>
        <span style={{ fontWeight: 700, fontSize: '0.82rem' }}>⭐ Watchlist</span>
        <span className="mono" style={{ fontSize: '0.68rem', color: C.sub }}>{rows.length}</span>
        <a href="/watchlist" style={{ marginLeft: 'auto', fontSize: '0.68rem', color: C.muted, textDecoration: 'none' }}
           title="Open the full watchlist page">full ↗</a>
        <button onClick={() => setOpen(false)} aria-label="Collapse watchlist"
                style={{ background: 'transparent', border: 'none', color: C.sub, cursor: 'pointer',
                         fontSize: '0.9rem', padding: '0 2px' }}>›</button>
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
  );
}
