/* RallyScanPanel — the 🚀 on-demand "confirmed bullish, room to rally" scan
 * on the Scalping page (Ajay 2026-06-10: "identify confirmed bullish stocks
 * that can rally a few $" + "add the on demand scan button").
 *
 * Button-driven: GET /scalping/rally composes three measured ingredients —
 * confirmed bullish (daily pattern ✓ ≤1d or full Minervini buy gate, no
 * bearish last-bar candle), dollar room (price × ADR ≥ $2/day typical range),
 * and a live 5-min tape check on the leaders. Cards lead with the $ range
 * because that's the question this screen answers. Capacity ≠ prediction —
 * the disclaimer rides on every result. */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { TickerCell } from './TickerCell';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#6b7280', gold: 'var(--gold,#c9a227)' };
const SHORT: Record<string, string> = {
  double_bottom: 'Double bottom', triple_bottom: 'Triple bottom',
  inverse_head_shoulders: 'Inv H&S', cup_with_handle: 'Cup w/ handle',
};
const TAPE_COLOR: Record<string, string> = {
  BREAKOUT_STRONG: C.green, RECLAIM: C.green, BREAKOUT_WEAK: C.amber,
  REJECTION: C.amber, BREAKDOWN: C.red, STALL: C.muted,
};

type Cand = {
  symbol: string; price: number; adr_pct?: number | null; dollar_range: number;
  rs_rank?: number | null; confirmed_pattern?: string | null; confirmed_today?: boolean;
  neckline?: number | null; target?: number | null; stop?: number | null;
  is_buyable: boolean; why: string[]; bullish_candle?: string | null;
  tape_state?: string; tape_verdict?: string;
};
type Resp = { generated_at: number; n_pool: number; n_candidates: number;
              candidates: Cand[]; criteria?: string; disclaimer?: string };

export function RallyScanPanel({ profile = 'aggressive', onChart }: {
  profile?: string; onChart?: (sym: string) => void;
}) {
  const navigate = useNavigate();
  const [data, setData] = useState<Resp | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(false);

  const scan = () => {
    setBusy(true);
    setErr(false);
    fetch(`${API}/scalping/rally?profile=${encodeURIComponent(profile)}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(setData)
      .catch(() => setErr(true))
      .finally(() => setBusy(false));
  };

  return (
    <section style={{ margin: '0.9rem 0', padding: '0.7rem 0.85rem', borderRadius: 12,
                      border: `1px solid ${C.green}44`, background: 'var(--bg-raised,#16181d)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span className="eyebrow">🚀 Confirmed bullish · room to rally</span>
        <button onClick={scan} disabled={busy}
                title="Scan today's movers + every current buyable: confirmed bullish daily setup AND a typical daily range big enough to rally a few dollars"
                style={{ fontSize: '0.74rem', fontWeight: 700, cursor: busy ? 'wait' : 'pointer',
                         padding: '0.25rem 0.8rem', borderRadius: 7, border: 'none',
                         background: C.green, color: '#0c1210', opacity: busy ? 0.6 : 1 }}>
          {busy ? 'Scanning…' : '🚀 Scan now'}
        </button>
        {data && (
          <span style={{ fontSize: '0.68rem', color: C.sub }}>
            {data.n_candidates} of {data.n_pool} screened qualify · {new Date(data.generated_at * 1000).toLocaleTimeString()}
          </span>
        )}
      </div>
      {data?.criteria && <div style={{ fontSize: '0.66rem', color: C.sub, marginTop: 3 }}>{data.criteria}</div>}
      {err && <p className="mono" style={{ color: C.red, fontSize: '0.74rem' }}>Scan failed — retry.</p>}

      {data && data.candidates.length === 0 && (
        <div style={{ fontSize: '0.78rem', color: C.muted, marginTop: 8 }}>
          Nothing currently pairs a confirmed bullish setup with a ${'>'}2/day range — that's the
          honest answer today, not a bug. Confirmed setups are rare by design.
        </div>
      )}

      {data && data.candidates.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: 7, marginTop: 8 }}>
          {data.candidates.map((c) => {
            const star = c.confirmed_pattern && c.is_buyable;
            return (
              <div key={c.symbol} role="button" tabIndex={0}
                   onClick={() => (onChart ? onChart(c.symbol) : navigate(`/sepa/${encodeURIComponent(c.symbol)}`))}
                   onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') navigate(`/sepa/${encodeURIComponent(c.symbol)}`); }}
                   title={`${c.why.join(' + ')}. Click for the live chart.`}
                   style={{ padding: '0.5rem 0.6rem', borderRadius: 9, cursor: 'pointer',
                            background: star ? 'rgba(16,185,129,0.08)' : 'var(--bg-sunken,#0f1115)',
                            border: `1px solid ${star ? C.green : C.green + '44'}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <TickerCell symbol={c.symbol} />
                  {star && <span title="Confirmed pattern AND full Minervini buy gate">⭐</span>}
                  <span style={{ marginLeft: 'auto', fontWeight: 800, color: C.green, fontSize: '0.82rem' }}
                        title="Typical daily range = price × ADR — capacity, not a prediction">
                    ~${c.dollar_range}/day
                  </span>
                </div>
                <div style={{ fontSize: '0.68rem', color: C.muted, marginTop: 2 }}>
                  ${c.price}{c.adr_pct != null ? ` · ADR ${c.adr_pct}%` : ''}{c.rs_rank != null ? ` · RS ${c.rs_rank}` : ''}
                </div>
                <div style={{ fontSize: '0.68rem', marginTop: 3 }}>
                  {c.confirmed_pattern && (
                    <span style={{ color: C.green, fontWeight: 600 }}>
                      📐 {SHORT[c.confirmed_pattern] || c.confirmed_pattern} ✓{c.confirmed_today ? ' today' : ' 1d'}
                    </span>
                  )}
                  {c.is_buyable && <span style={{ color: C.green }}>{c.confirmed_pattern ? ' · ' : ''}✅ buyable</span>}
                  {c.bullish_candle && <span style={{ color: C.muted }}> · 🕯 {c.bullish_candle.replace(/_/g, ' ')}</span>}
                </div>
                {c.target != null && (
                  <div style={{ fontSize: '0.64rem', color: C.muted, marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
                    line {c.neckline} → tgt {c.target} · <span style={{ color: C.red }}>stop {c.stop}</span>
                  </div>
                )}
                {c.tape_state && (
                  <div style={{ fontSize: '0.64rem', marginTop: 2, color: TAPE_COLOR[c.tape_state] || C.muted }}>
                    tape now: {c.tape_state.replace(/_/g, ' ')} · {c.tape_verdict}
                  </div>
                )}
                {c.confirmed_today && (
                  <div style={{ fontSize: '0.6rem', color: C.sub, marginTop: 2 }}>
                    provisional — counts only if today CLOSES above the line
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
      {data?.disclaimer && <div style={{ fontSize: '0.62rem', color: C.sub, marginTop: 7 }}>{data.disclaimer}</div>}
    </section>
  );
}
