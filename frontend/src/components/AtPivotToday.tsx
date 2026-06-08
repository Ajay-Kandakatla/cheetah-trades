/* AtPivotToday — Leaderboard section: SEPA candidates sitting AT or just under
 * their buy point today, with a LIVE-price overlay flagging which are still at the
 * pivot vs. already gapped over it overnight. The low-risk Minervini entry is the
 * breakout AT the pivot (p.203), not chasing. (Ajay 2026-06-08: "I'm missing a lot
 * of pivots… add it in the leaderboard.") Reads /sepa/at-pivot. NOT advice.
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { InfoButton } from './InfoButton';

type Row = {
  symbol: string;
  pivot: number;
  last_close: number;
  live_price: number | null;
  dist_pct: number;
  rs_rank: number | null;
  setup_type: string | null;
  decision: string | null;
  vcp_tightness?: number | null;
  bucket: 'at_pivot' | 'approaching' | 'gapped_over';
};
type Payload = {
  rows: Row[];
  n: number;
  counts: { at_pivot: number; approaching: number; gapped_over: number };
  generated_at: number;
};

const BUCKET: Record<Row['bucket'], { tag: string; cls: string }> = {
  at_pivot:    { tag: '● AT PIVOT',   cls: 'at' },
  approaching: { tag: '◓ approaching', cls: 'near' },
  gapped_over: { tag: '⚡ gapped over', cls: 'gap' },
};

const PageInfo = (
  <>
    <p>
      SEPA candidates sitting <strong>at or just under their pivot</strong> right now —
      Stage 2, with a setup, <em>not</em> extended and <em>not</em> climaxing. The
      low-risk Minervini entry is the breakout <strong>at the pivot</strong> on volume
      (p.203), never chasing a run.
    </p>
    <ul>
      <li><strong>● AT PIVOT</strong> — in the buy zone now (catchable).</li>
      <li><strong>◓ approaching</strong> — coiling within 5% below — set the alert / buy-stop.</li>
      <li><strong>⚡ gapped over</strong> — already past the buy zone pre-market (you missed it; don't chase).</li>
    </ul>
    <p className="mono">
      Live price vs the pivot updates every ~2 min, so an overnight/pre-market gap
      shows up here instead of stealing the entry. Educational, not advice.
    </p>
  </>
);

export function AtPivotToday() {
  const nav = useNavigate();
  const [data, setData] = useState<Payload | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/sepa/at-pivot`);
      if (r.ok) setData(await r.json());
    } catch {
      /* keep last */
    }
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 120_000); return () => clearInterval(t); }, [load]);

  if (!data) return null;

  return (
    <section className="day-section ap-section">
      <div className="day-section__head-row">
        <h2 className="day-section__h">
          🎯 At the pivot today
          <InfoButton inline title="At the pivot today">{PageInfo}</InfoButton>
        </h2>
        <span className="ap-counts mono">
          {data.counts.at_pivot} at · {data.counts.approaching} approaching
          {data.counts.gapped_over ? ` · ${data.counts.gapped_over} gapped` : ''}
        </span>
      </div>
      <p className="ap-lede">
        Names sitting at or just under their buy point — Stage 2, not extended, not
        climaxing. Live price vs the pivot, so you catch the breakout instead of
        missing it to a gap. <strong>Buy at the pivot, not chasing</strong> (p.203).
      </p>

      {data.rows.length === 0 ? (
        <div className="day-empty">
          Nothing at the pivot right now — leaders are extended or still basing. Patience is a position.
        </div>
      ) : (
        <div className="ap-list">
          <div className="ap-row ap-row--head">
            <span>Status</span><span>Symbol</span>
            <span className="ap-num">vs pivot</span><span className="ap-num">Pivot</span>
            <span className="ap-num">Live</span><span className="ap-num">RS</span><span>Setup</span>
          </div>
          {data.rows.map((r) => {
            const b = BUCKET[r.bucket];
            return (
              <div
                key={r.symbol}
                className={`ap-row ap-row--${b.cls}`}
                role="button"
                tabIndex={0}
                onClick={() => nav(`/sepa/${encodeURIComponent(r.symbol)}`,
                  { state: { from: '/leaderboard', label: 'Leaderboard' } })}
                title={`Chart ${r.symbol}`}
              >
                <span className={`ap-tag ap-tag--${b.cls}`}>{b.tag}</span>
                <span className="ap-sym"><strong>{r.symbol}</strong></span>
                <span className={`ap-num mono ${r.dist_pct > 0 ? 'pos' : r.dist_pct < 0 ? 'neg' : ''}`}>
                  {r.dist_pct > 0 ? '+' : ''}{r.dist_pct}%
                </span>
                <span className="ap-num mono">${r.pivot}</span>
                <span className="ap-num mono">{r.live_price != null ? `$${r.live_price}` : '—'}</span>
                <span className="ap-num mono">{r.rs_rank ?? '—'}</span>
                <span className="ap-setup mono">
                  {r.setup_type}
                  {r.decision === 'ENTER' && <span className="ap-enter">ENTER</span>}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
