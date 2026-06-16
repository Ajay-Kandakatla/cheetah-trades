/* FloatTurnover — the "total shares (float) + turnover" supply chip on SEPA
   cards (Ajay 2026-06-15: "total shares are actually an important measure... add
   this to all the sepa cards").

   Turnover = today's volume ÷ float = how much of the tradeable supply actually
   changed hands. Raw volume misleads (a mega-cap trades 100M+ shares yet ~1% of
   its float); turnover is the real supply read. Self-fetches /sepa/shares/{symbol}
   (yfinance, cached weekly) and computes turnover from the card's last_vol.

   Renders NOTHING when there's no float (ETFs) or no volume — display-only. */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { fmtVol } from './BreakoutStats';

type Shares = {
  ok?: boolean;
  float_shares?: number | null;
  shares_outstanding?: number | null;
  market_cap?: number | null;
};

export function FloatTurnover({ symbol, lastVol }: { symbol?: string; lastVol?: number | null }) {
  const [sh, setSh] = useState<Shares | null>(null);

  useEffect(() => {
    if (!symbol) return;
    let alive = true;
    fetch(`${API}/sepa/shares/${encodeURIComponent(symbol)}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (alive && j && j.ok) setSh(j as Shares); })
      .catch(() => { /* non-fatal */ });
    return () => { alive = false; };
  }, [symbol]);

  const float = sh?.float_shares ?? sh?.shares_outstanding ?? null;
  if (float == null || float <= 0) return null;        // ETFs / no data → nothing

  const turnover = lastVol != null && lastVol > 0 ? (lastVol / float) * 100 : null;
  // High turnover = a real supply/demand event; mega-cap low turnover = quiet.
  const tone = turnover == null ? '#94a3b8' : turnover >= 20 ? '#10b981' : turnover >= 5 ? '#eab308' : '#94a3b8';
  const title =
    `Total shares (float): ${float.toLocaleString()}. ` +
    (turnover != null
      ? `Today's ${lastVol!.toLocaleString()} shares = ${turnover.toFixed(1)}% of the float turned over. `
      : '') +
    `Turnover (volume ÷ float) is the supply read — a mega-cap can trade huge raw volume yet turn over ~1% of its float (little push); a thin float turning over 20%+ is a real supply/demand event.`;

  return (
    <span className="sepa-chip" title={title}
          style={{ color: tone, borderColor: tone, cursor: 'help', fontSize: '0.72rem' }}>
      🔁 float {fmtVol(float)}
      {turnover != null && (
        <span style={{ opacity: 0.85 }}> · {turnover.toFixed(turnover < 10 ? 1 : 0)}% turnover</span>
      )}
    </span>
  );
}
