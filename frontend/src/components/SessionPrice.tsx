/* SessionPrice — the regular close with its day change AND the extended-hours
 * print with its change since the close, StockTwits-style.
 *
 * Ajay 2026-09-02 (TLYS): "$3.81 ↓ $0.15 (3.79%) Today · Closed" over
 * "$5.12 ↑ $1.31 (34.38%) ☾ After Hours". One number after the bell hides
 * which move you are looking at. Reads /sepa/live-price/<sym> (Massive
 * snapshot, ext-hours aware) every 30s while a session is on. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type QuoteView = {
  session: 'premarket' | 'rth' | 'afterhours' | 'closed';
  rth_close: number | null; prev_close: number | null;
  day_change: number | null; day_change_pct: number | null;
  ext_price: number | null; ext_change: number | null; ext_change_pct: number | null;
  ext_label: string | null; last: number | null;
};

const money = (v: number | null | undefined) => (v == null ? '—' : `$${v.toFixed(2)}`);
const arrow = (v: number | null | undefined) => (v == null ? '' : v >= 0 ? '↑' : '↓');
const color = (v: number | null | undefined) =>
  v == null ? 'var(--cm-slate)' : v >= 0 ? 'var(--positive)' : 'var(--negative)';
const pct = (v: number | null | undefined) => (v == null ? '' : `(${v >= 0 ? '+' : ''}${v.toFixed(2)}%)`);

function Delta({ change, changePct }: { change: number | null; changePct: number | null }) {
  if (change == null && changePct == null) return null;
  return (
    <span className="mono" style={{ color: color(changePct ?? change), fontSize: '0.95rem', fontWeight: 600 }}>
      {arrow(changePct ?? change)} {change != null ? `$${Math.abs(change).toFixed(2)} ` : ''}{pct(changePct)}
    </span>
  );
}

/* Pure: which lines to draw. Exported for the test. */
export function lines(v: QuoteView) {
  const out: { price: number | null; change: number | null; changePct: number | null; tag: string; big: boolean; ref?: string }[] = [];
  if (v.session === 'rth') {
    out.push({ price: v.rth_close, change: v.day_change, changePct: v.day_change_pct, tag: 'Today · Live', big: true });
    return out;
  }
  if (v.session === 'premarket' || v.rth_close == null) {
    out.push({ price: v.ext_price ?? v.prev_close, change: v.ext_change, changePct: v.ext_change_pct,
               tag: v.ext_price != null ? `☀ ${v.ext_label ?? 'Pre-Market'}` : 'Closed', big: true,
               ref: v.prev_close != null ? `Prev close ${money(v.prev_close)}` : undefined });
    return out;
  }
  out.push({ price: v.rth_close, change: v.day_change, changePct: v.day_change_pct,
             tag: `Today · Closed ${money(v.rth_close)}`, big: v.ext_price == null });
  if (v.ext_price != null) {
    out.push({ price: v.ext_price, change: v.ext_change, changePct: v.ext_change_pct,
               tag: `☾ ${v.ext_label ?? 'After Hours'}`, big: true });
  }
  return out;
}

export function SessionPrice({ symbol, fallbackClose, fallbackPct, data: preset }:
  { symbol: string; fallbackClose?: number | null; fallbackPct?: number | null; data?: QuoteView | null }) {
  const [view, setView] = useState<QuoteView | null>(preset ?? null);
  useEffect(() => {
    if (preset) return;
    let live = true;
    const load = () => fetch(`${API}/sepa/live-price/${encodeURIComponent(symbol)}`, { credentials: 'include', cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (live && j?.view?.session) setView(j.view); })
      .catch(() => { /* keep the fallback */ });
    load();
    const id = setInterval(load, 30_000);
    return () => { live = false; clearInterval(id); };
  }, [symbol, preset]);

  const v: QuoteView = view ?? {
    session: 'closed', rth_close: fallbackClose ?? null, prev_close: null, day_change: null,
    day_change_pct: fallbackPct ?? null, ext_price: null, ext_change: null, ext_change_pct: null,
    ext_label: null, last: fallbackClose ?? null,
  };
  if (v.last == null && v.rth_close == null) return null;
  const rows = lines(v);
  return (
    <div className="session-price" data-session={v.session}>
      {rows.map((r, i) => (
        <div key={i} className="session-price__line" style={{ display: 'inline-flex', alignItems: 'baseline', gap: '0.6rem', flexWrap: 'wrap' }}>
          <span className="mono" style={{ fontSize: r.big ? '1.6rem' : '1.1rem', fontWeight: 700, opacity: r.big ? 1 : 0.85 }}>{money(r.price)}</span>
          <Delta change={r.change} changePct={r.changePct} />
          <span className="session-price__tag mono" style={{ fontSize: '0.72rem', color: 'var(--cm-slate)', letterSpacing: '0.03em' }}>
            {r.tag}{r.ref ? ` · ${r.ref}` : ''}
          </span>
        </div>
      ))}
    </div>
  );
}
