/* LivePriceTag — the REAL price next to the TradingView embed (Ajay
 * 2026-06-11: "I think the TradingView chart is not live"). It is — and it
 * can't be: the anonymous embed is ~15-min delayed by TradingView's design,
 * and a paid TV account cannot unlock it. So instead of asking the user to
 * remember that, this tag polls OUR real-time Massive feed (verified 0.1s
 * trade age) every 5s while mounted and shows the live number right beside
 * the delayed chart. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

type Quote = { price?: number | null; change_pct?: number | null; updated_at?: number };

export function LivePriceTag({ symbol }: { symbol: string }) {
  const [q, setQ] = useState<Quote | null>(null);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setInterval> | null = null;
    const tick = () => {
      fetch(`${API}/sepa/live-price/${encodeURIComponent(symbol)}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => alive && d && setQ(d))
        .catch(() => { /* silent */ });
    };
    tick();
    timer = setInterval(tick, 5000);
    return () => { alive = false; if (timer) clearInterval(timer); };
  }, [symbol]);

  if (q?.price == null) return null;
  const chg = q.change_pct;
  const up = (chg ?? 0) >= 0;
  const color = chg == null ? 'var(--ink-muted)' : up ? 'var(--positive, #10b981)' : 'var(--negative, #ef4444)';
  return (
    <span className="mono"
          title="Real-time from your Massive feed (sub-second). The TradingView embed below is ~15-min delayed by TV's design — trust THIS number."
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.8rem',
                   padding: '3px 10px', borderRadius: 6,
                   border: `1px solid ${color}55`, background: `${color}12` }}>
      <span style={{ fontWeight: 800 }}>${q.price.toFixed(2)}</span>
      {chg != null && (
        <span style={{ color, fontWeight: 700 }}>{up ? '▲' : '▼'} {Math.abs(chg).toFixed(2)}%</span>
      )}
      <span style={{ fontSize: '0.62rem', color: 'var(--ink-subtle)', textTransform: 'uppercase' }}>live</span>
    </span>
  );
}
