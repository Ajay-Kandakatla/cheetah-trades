/* TickerPatternPanel — on-demand pattern scanner for ONE ticker, on the
 * detail page's Chart tab (Ajay 2026-06-09: "Add an on-demand pattern scanner
 * in the individual tickers also"). Auto-runs on open (fresh ~10ms compute on
 * the cached daily chart, not the stored verdict scan) + a ↻ re-scan button.
 * Shows: the pattern it matches (or is closest to, with % to the line), the
 * recent candle reads, an EXPLICIT no-match statement, and THIS chart's own
 * historical record per pattern (+21-bar outcomes, win or lose). */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';
import type { PatternMatch, PatternFormation } from '../hooks/usePatternVerdicts';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#6b7280' };
const LABEL: Record<string, string> = {
  double_bottom: 'Double bottom (W)', triple_bottom: 'Triple bottom',
  inverse_head_shoulders: 'Inverse head & shoulders', cup_with_handle: 'Cup with handle',
};
const BULKOWSKI: Record<string, string> = {
  double_bottom: 'Bulkowski: break-even failure 12–16% by variant; unconfirmed Ws continue LOWER 48% of the time (daily bars, hindsight, no costs)',
  inverse_head_shoulders: 'Bulkowski (n=3,197): break-even failure 11%, throwback 65%, rank 13/39 (daily bars, hindsight, no costs)',
  triple_bottom: 'Bulkowski (n>2,500): break-even failure 13%, throwback 65%, rank 12/39 (daily bars, hindsight, no costs)',
  cup_with_handle: 'Bulkowski (n=913): break-even failure 5%, rank 3/39 — but 47% dropped substantially within two months of breakout (his 1990–2024 lesson)',
};
const READ_COLOR: Record<string, string> = {
  bullish_reversal_setup: C.green, bearish_warning: C.red, indecision: C.muted,
};

type Verdict = {
  symbol: string; matches: PatternMatch[]; no_match: boolean; error?: string;
  candles?: { formations: PatternFormation[]; last_bar?: { read?: string } | null; trend?: string } | null;
  validation?: Record<string, { n: number; pct_positive_21d: number; median_fwd_21d_pct: number; median_max_gain_21d_pct: number }>;
  generated_at?: number; disclaimer?: string;
};

export function TickerPatternPanel({ symbol }: { symbol: string }) {
  const navigate = useNavigate();
  const [data, setData] = useState<Verdict | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(false);

  const load = useCallback(() => {
    setBusy(true);
    setErr(false);
    fetch(`${API}/patterns/symbol/${encodeURIComponent(symbol)}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(setData)
      .catch(() => setErr(true))
      .finally(() => setBusy(false));
  }, [symbol]);

  useEffect(() => { load(); }, [load]);

  const formations = data?.candles?.formations || [];
  const trend = data?.candles?.trend;
  const val = Object.entries(data?.validation || {});

  return (
    <div style={{ margin: '0.8rem 0', padding: '0.7rem 0.85rem', borderRadius: 12,
                  border: '1px solid var(--hairline,#2a2a2a)', background: 'var(--bg-raised,#16181d)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span className="eyebrow">📐 Chart patterns — this ticker</span>
        <button onClick={load} disabled={busy}
                title="Re-run the pattern detectors on this chart right now"
                style={{ marginLeft: 'auto', fontSize: '0.72rem', fontWeight: 600, cursor: busy ? 'wait' : 'pointer',
                         padding: '0.15rem 0.6rem', borderRadius: 6, background: 'transparent',
                         color: 'var(--gold,#c9a227)', border: '1px solid var(--gold,#c9a227)' }}>
          {busy ? 'Scanning…' : '↻ Scan now'}
        </button>
      </div>

      {err && <p className="mono" style={{ color: C.red, fontSize: '0.74rem' }}>Pattern scan failed — retry.</p>}
      {!data && !err && <p className="mono" style={{ opacity: 0.6, fontSize: '0.74rem' }}>…scanning the daily chart</p>}

      {data && (
        <>
          {data.error && (
            <p style={{ fontSize: '0.76rem', color: C.muted }}>Can't read this chart: {data.error}</p>
          )}

          {/* The headline answer: matched / closest / explicitly nothing */}
          {data.matches.length > 0 ? data.matches.map((m, i) => {
            const conf = m.status === 'confirmed';
            const col = conf ? C.green : C.amber;
            return (
              <div key={`${m.pattern}-${i}`}
                   style={{ marginTop: 8, padding: '0.5rem 0.65rem', borderRadius: 9,
                            border: `1px solid ${col}55`, background: `${col}0d` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <b style={{ fontSize: '0.85rem' }}>{LABEL[m.pattern] || m.pattern}</b>
                  <span style={{ fontSize: '0.68rem', fontWeight: 700, color: col,
                                 border: `1px solid ${col}55`, borderRadius: 5, padding: '1px 7px' }}>
                    {conf ? `CONFIRMED ${m.bars_since_confirm === 0 ? 'TODAY' : 'yesterday'}` : `FORMING · ${m.to_confirm_pct}% to the line`}
                  </span>
                  {conf && m.bars_since_confirm === 0 && (
                    <span style={{ fontSize: '0.64rem', color: C.muted }}>
                      provisional — counts only if today CLOSES above the line
                    </span>
                  )}
                  {conf && m.ext_past_confirm_pct != null && m.ext_past_confirm_pct > 5 && (
                    <span style={{ fontSize: '0.68rem', color: C.amber }}>⚠ +{m.ext_past_confirm_pct}% past the line — extended</span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 14, marginTop: 4, fontSize: '0.74rem', color: C.muted, flexWrap: 'wrap' }}>
                  <span>line <b>{m.neckline}</b></span>
                  <span style={{ color: C.green }}>target {m.target} <span style={{ color: C.sub }}>(measure rule)</span></span>
                  <span style={{ color: C.red }}>stop {m.stop}</span>
                </div>
                {!conf && (
                  <div style={{ fontSize: '0.68rem', color: C.muted, marginTop: 4 }}>
                    A shape, not a signal — it only counts on a CLOSE above the line.
                  </div>
                )}
                <div style={{ fontSize: '0.64rem', color: C.sub, marginTop: 4 }}>{BULKOWSKI[m.pattern]}</div>
              </div>
            );
          }) : !data.error && (
            <p style={{ fontSize: '0.78rem', color: C.muted, margin: '8px 0 0' }}>
              <b>Matches none</b> of the four patterns (double bottom, triple bottom, inverse H&amp;S,
              cup-with-handle) on the daily chart right now
              {trend ? <> · 10-bar trend: <b>{trend}</b></> : null}.
            </p>
          )}

          {/* Candle reads — bullish / bearish / indecision, with the honesty stat */}
          {formations.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: '0.64rem', color: C.sub, textTransform: 'uppercase', marginBottom: 3 }}>
                Recent candle reads (context, not signals)
              </div>
              {formations.map((f) => (
                <div key={`${f.name}-${f.date}`} style={{ fontSize: '0.74rem', marginBottom: 3 }}>
                  <b style={{ color: READ_COLOR[f.read] || C.muted }}>{f.name.replace(/_/g, ' ')}</b>
                  <span style={{ color: C.sub }}> ({f.date}) — {f.note}.</span>
                  {f.stat && <span style={{ color: C.sub, fontSize: '0.66rem' }}> {f.stat}.</span>}
                </div>
              ))}
            </div>
          )}

          {/* This chart's own record — the self-validation that keeps us honest */}
          {val.length > 0 && (
            <div style={{ marginTop: 8, fontSize: '0.72rem', color: C.muted }}>
              <div style={{ fontSize: '0.64rem', color: C.sub, textTransform: 'uppercase', marginBottom: 3 }}>
                This chart's own record (+21 trading days after past confirmations, gross)
              </div>
              {val.map(([k, v]) => (
                <div key={k}>
                  <b>{LABEL[k] || k}</b>: n={v.n} · {v.pct_positive_21d}% positive ·
                  median {v.median_fwd_21d_pct > 0 ? '+' : ''}{v.median_fwd_21d_pct}%
                </div>
              ))}
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginTop: 8 }}>
            <button onClick={() => navigate('/patterns')}
                    style={{ fontSize: '0.68rem', background: 'transparent', border: 'none', padding: 0,
                             color: 'var(--gold,#c9a227)', cursor: 'pointer', textDecoration: 'underline' }}>
              All pattern verdicts →
            </button>
            <span style={{ fontSize: '0.62rem', color: C.sub }}>{data.disclaimer}</span>
          </div>
        </>
      )}
    </div>
  );
}
