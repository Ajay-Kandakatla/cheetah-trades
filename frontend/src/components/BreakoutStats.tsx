/* BreakoutStats — "how often does this name actually break out, and on what
   ACTUAL volume?" (Ajay 2026-06-13: "give me a trend and count and volume and
   its actual number instead of 2.x and expanding").

   Shows the COUNT of distinct volume-confirmed breakouts over the trailing year
   (book p.203) + today's REAL share volume vs the 50-day average — not just a
   "2.4×" ratio.

   Two modes (combine them for self-healing):
     • <BreakoutStats vol={row.volume} />  — reads the breakout_count already in
       the scan payload (no fetch). Fast path.
     • <BreakoutStats symbol="MU" />       — self-fetches /sepa/breakout/{symbol}
       (a held name isn't always in the latest scan; Portfolio uses this).
     • <BreakoutStats vol={row.volume} symbol={row.symbol} />  — SEPA cards: use
       the payload's count when present, else FALL BACK to the per-symbol fetch.
       This is why the chip survives a STALE cached scan that predates
       breakout_count (the localStorage `sepa.scan` snapshot the page hydrates
       from synchronously) — the card self-heals instead of silently hiding.
   Renders nothing until it has a breakout_count. */
import { lazy, Suspense, useEffect, useState, type MouseEvent as ReactMouseEvent } from 'react';
import { API } from '../lib/apiBase';

// Lazy so the chart modal isn't in the SEPA list's critical bundle.
const BreakoutHistoryModal = lazy(() =>
  import('./BreakoutHistoryModal').then((m) => ({ default: m.BreakoutHistoryModal })),
);

type VolLike = {
  breakout_count?: number | null;
  breakout_window_bars?: number | null;
  last_vol?: number | null;
  avg_vol_50?: number | null;
  days_since_breakout?: number | null;
  high_vol_breakout?: boolean | null;
};

export function fmtVol(n: number | null | undefined): string {
  if (n == null) return '—';
  const a = Math.abs(n);
  if (a >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${Math.round(n / 1e3)}K`;
  return String(Math.round(n));
}

function windowLabel(bars: number | null | undefined): string {
  const b = bars ?? 0;
  if (b >= 240) return '1y';
  const mo = Math.max(1, Math.round(b / 21));
  return `${mo}mo`;
}

function Chip({ v, onOpen }: { v: VolLike; onOpen?: (e: ReactMouseEvent) => void }) {
  const count = v.breakout_count;
  if (count == null) return null;
  const lv = v.last_vol ?? null;
  const av = v.avg_vol_50 ?? null;
  const ratio = lv != null && av && av > 0 ? lv / av : null;
  const todayBreakout = v.days_since_breakout === 0 || !!v.high_vol_breakout;
  const tone = count >= 8 ? '#10b981' : count >= 3 ? '#eab308' : '#94a3b8';
  const clickable = !!onOpen;
  const title = clickable
    ? `Click to chart where each of these ${count} breakout${count === 1 ? '' : 's'} fired (last ${windowLabel(v.breakout_window_bars)}).`
    : `${count} volume-confirmed breakout${count === 1 ? '' : 's'} in the last ${windowLabel(v.breakout_window_bars)} ` +
      `(close above the prior 21-day high on >1.5× average volume — Minervini, Trade Like a Stock Market Wizard p.203). ` +
      `Today's volume ${lv != null ? lv.toLocaleString() : '—'} vs the 50-day average ${av != null ? av.toLocaleString() : '—'}` +
      `${ratio != null ? ` (${ratio.toFixed(1)}×)` : ''}.`;
  return (
    <span className="sepa-chip" title={title}
          role={clickable ? 'button' : undefined}
          tabIndex={clickable ? 0 : undefined}
          onClick={onOpen}
          onKeyDown={clickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen?.(e as unknown as ReactMouseEvent); } } : undefined}
          style={{ color: tone, borderColor: tone, cursor: clickable ? 'pointer' : 'help', fontSize: '0.72rem' }}>
      🚀 {count} breakout{count === 1 ? '' : 's'} · {windowLabel(v.breakout_window_bars)}
      {lv != null && (
        <>
          {' · '}vol {fmtVol(lv)}
          {av != null && <span style={{ opacity: 0.75 }}> / {fmtVol(av)} avg</span>}
          {ratio != null && <span style={{ opacity: 0.75 }}> ({ratio.toFixed(1)}×)</span>}
        </>
      )}
      {todayBreakout && ' ⚡'}
      {clickable && <span style={{ opacity: 0.6 }}> ›</span>}
    </span>
  );
}

export function BreakoutStats({ vol, symbol }: { vol?: VolLike | null; symbol?: string }) {
  const [fetched, setFetched] = useState<VolLike | null>(null);
  const [open, setOpen] = useState(false);
  // The payload already carries the count? Use it, skip the network. Otherwise
  // (no vol, OR a stale cached row whose volume predates breakout_count) and we
  // have a symbol → self-heal by fetching the per-symbol breakout read.
  const haveCount = vol?.breakout_count != null;

  useEffect(() => {
    if (haveCount || !symbol) return;
    let alive = true;
    fetch(`${API}/sepa/breakout/${encodeURIComponent(symbol)}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive && j && j.ok) setFetched(j as VolLike); })
      .catch(() => { /* non-fatal */ });
    return () => { alive = false; };
  }, [haveCount, symbol]);

  const v = haveCount ? vol : (fetched ?? vol);
  if (!v) return null;

  // With a symbol the chip is a drill-in: click to chart WHERE each breakout
  // fired. Stop propagation so it doesn't also trigger the card's row-select.
  const onOpen = symbol
    ? (e: ReactMouseEvent) => { e.stopPropagation(); setOpen(true); }
    : undefined;

  return (
    <>
      <Chip v={v} onOpen={onOpen} />
      {open && symbol && (
        <Suspense fallback={null}>
          <BreakoutHistoryModal symbol={symbol} onClose={() => setOpen(false)} />
        </Suspense>
      )}
    </>
  );
}
