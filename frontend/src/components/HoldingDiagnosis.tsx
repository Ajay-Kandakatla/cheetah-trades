/* HoldingDiagnosis — "what's driving this move?" expander on a portfolio card.

   Ajay 2026-06-04: a write-up explaining the trend — accumulation/distribution,
   macro, sector rotation, liquidity, or stock-specific — with a factor scorecard
   and an LLM read (Claude Sonnet). Lazy: fetches /portfolio/diagnosis/{symbol}
   only when expanded (the LLM write-up is the slow part; the backend caches it). */
import { useState } from 'react';
import { useEffect } from 'react';
import { API } from '../lib/apiBase';
import { EarningsQualityPanel } from './EarningsQualityPanel';

type Factor = { score: number; note: string };
type Tripwire = { label: string; level: number | null; distance_pct: number | null; note: string; cite: string };
type Target = { label: string; price: number | null; pct_from_here: number | null };
type Fired = { rule: string; verdict: string; msg: string };
type Position = {
  entry: number;
  shares?: number | null;
  last_close: number;
  gain_pct: number | null;
  gain_dollars?: number | null;
  r_multiple: number | null;
  to_breakeven_pct: number;
  verdict?: string | null;
  verdict_summary?: string | null;
  stage?: number | null;
  stop?: { price: number | null; distance_pct: number | null } | null;
  targets?: Target[];
  tripwires?: Tripwire[];
  fired?: Fired[];
};
type Diagnosis = {
  symbol: string;
  sector?: string | null;
  name?: string | null;
  move_pct: number | null;
  verdict?: string | null;
  headline_label?: string;
  uptrend_driver?: { label: string; note: string } | null;
  position?: Position | null;
  writeup?: string | null;
  scorecard?: Record<string, Factor>;
  // Minervini Ch.8 earnings quality — a sell-RISK heads-up (not a verdict change).
  earnings_quality?: any | null;
  eq_sell_risk?: string[] | null;
  // Imminent macro events (FOMC/CPI/jobs/PCE) — a binary-event heads-up, also
  // informational (does not change the price-based verdict).
  macro_events?: string[] | null;
};

// label + whether a high score means "pressure" (red) or "health" (green).
const FACTOR_META: Record<string, { label: string; health?: boolean }> = {
  market_macro:    { label: 'Broad market (macro)' },
  sector_rotation: { label: 'Sector rotation' },
  distribution:    { label: 'Distribution (selling)' },
  liquidity:       { label: 'Thin liquidity' },
  stock_specific:  { label: 'Stock-specific' },
  macro_risk_fwd:  { label: 'Macro risk (forward)' },
  trend_health:    { label: 'Trend health', health: true },
};
const ORDER = ['market_macro', 'sector_rotation', 'distribution', 'stock_specific', 'macro_risk_fwd', 'liquidity', 'trend_health'];

function barColor(score: number, health?: boolean): string {
  if (health) return score >= 65 ? '#22c55e' : score >= 40 ? '#d97706' : '#ef4444';
  return score >= 60 ? '#ef4444' : score >= 35 ? '#d97706' : '#64748b';
}

export function HoldingDiagnosis({ symbol, defaultOpen = false }: { symbol: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const [data, setData] = useState<Diagnosis | null>(null);
  const [loading, setLoading] = useState(false);
  const [writingUp, setWritingUp] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const base = `${API}/portfolio/diagnosis/${encodeURIComponent(symbol)}?writeup=`;
  const load = (force = false) => {
    setLoading(true); setErr(null);
    const f = force ? '&force=true' : '';
    // Phase 1 — instant scorecard (no LLM). A cache hit returns the full read
    // (write-up included) so this is usually one-and-done.
    fetch(`${base}false${f}`, { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j: Diagnosis) => {
        setData(j); setLoading(false);
        if (!j.writeup) {
          // Phase 2 — the tailored write-up streams in.
          setWritingUp(true);
          fetch(`${base}true${f}`, { credentials: 'include' })
            .then((r) => (r.ok ? r.json() : null))
            .then((j2: Diagnosis | null) => { if (j2) setData(j2); })
            .finally(() => setWritingUp(false));
        }
      })
      .catch((e) => { setErr(String(e?.message || e)); setLoading(false); });
  };

  // Auto-load when opened by default (each holding shows its own read).
  useEffect(() => { if (defaultOpen && !data && !loading) load(); /* eslint-disable-next-line */ }, []);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && !data && !loading) load();
  };

  return (
    <div className="hdiag">
      <button type="button" className="hdiag__toggle" onClick={toggle} aria-expanded={open}>
        {open ? '▾' : '▸'} 🔍 Why is it moving?
      </button>
      {open && (
        <div className="hdiag__body">
          {loading && <div className="hdiag__muted">Diagnosing {symbol}…</div>}
          {err && <div className="hdiag__muted">Couldn’t load: {err}</div>}
          {data && (
            <>
              {/* De-duped (2026-06-13): the P&L, verdict, fired triggers and the
                  R-target ladder are already shown by the card header + PositionSignal
                  above — this panel keeps only what's UNIQUE: the % back to cost when
                  underwater, and the Minervini "hold until one fires" tripwire ladder. */}
              {data.position && (() => {
                const p = data.position!;
                const up = (p.gain_pct ?? 0) >= 0;
                return (
                  <div className="hdiag__pos">
                    {!up && p.to_breakeven_pct > 0 && (
                      <div className="hdiag__be">Back to your cost: <b>+{p.to_breakeven_pct}%</b> from here</div>
                    )}
                    {(p.tripwires?.length ?? 0) > 0 && (
                      <div className="hdiag__trip">
                        <div className="hdiag__triphead">
                          You hold until one of these fires
                          <span className="hdiag__cite"> · Minervini pp.295–296</span>
                        </div>
                        {p.tripwires!.map((t, i) => (
                          <div key={i} className="hdiag__tripitem" title={`${t.note} (Minervini ${t.cite})`}>
                            <span className="hdiag__tripname">{t.label}</span>
                            {t.level != null && <span className="hdiag__triplvl mono">${t.level}</span>}
                            {t.distance_pct != null && (
                              <span className="hdiag__tripdist mono">{t.distance_pct >= 0 ? '+' : ''}{t.distance_pct}%</span>
                            )}
                            <span className="hdiag__tripnote">{t.note}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })()}
              {data.headline_label && (
                <div className="hdiag__headline">
                  {data.uptrend_driver ? 'Powered by: ' : 'Likely driver: '}<strong>{data.headline_label}</strong>
                  {data.sector && data.sector !== '—' && <span className="hdiag__sector"> · {data.sector}</span>}
                  {data.move_pct != null && <span className="hdiag__move"> · {data.position ? 'stock’s last 5d ' : ''}{data.move_pct >= 0 ? '+' : ''}{data.move_pct}%{data.position ? '' : ' (5d)'}</span>}
                </div>
              )}
              {data.uptrend_driver?.note && <div className="hdiag__muted" style={{ marginBottom: '0.4rem' }}>{data.uptrend_driver.note}</div>}
              {data.writeup
                ? <p className="hdiag__writeup">{data.writeup}</p>
                : writingUp
                  ? <p className="hdiag__muted">✍️ Writing the tailored read for {symbol}…</p>
                  : <p className="hdiag__muted">Scorecard ready — the tailored write-up fills in shortly.</p>}
              {data.scorecard && (
                <div className="hdiag__scores">
                  {ORDER.filter((k) => data.scorecard![k]).map((k) => {
                    const f = data.scorecard![k]; const m = FACTOR_META[k];
                    return (
                      <div key={k} className="hdiag__row" title={f.note}>
                        <span className="hdiag__label">{m.label}</span>
                        <span className="hdiag__track"><span className="hdiag__fill" style={{ width: `${Math.max(0, Math.min(100, f.score))}%`, background: barColor(f.score, m.health) }} /></span>
                        <span className="hdiag__num">{Math.round(f.score)}</span>
                      </div>
                    );
                  })}
                </div>
              )}
              {/* Minervini Ch.8 earnings quality — sell-RISK heads-up. Does NOT
                  change the price-based hold/sell verdict above; it just makes a
                  deteriorating earnings story visible before price confirms. */}
              {data.eq_sell_risk && data.eq_sell_risk.length > 0 && (
                <div style={{
                  marginTop: '0.7rem', padding: '0.5rem 0.75rem', borderRadius: 6,
                  background: 'rgba(217,119,6,0.10)', border: '1px solid rgba(217,119,6,0.40)',
                  fontSize: '0.8rem', color: 'var(--ink, #eee)',
                }}>
                  <strong style={{ color: '#d97706' }}>⚠️ Earnings-quality sell-risk</strong>
                  <span style={{ color: 'var(--cm-slate, #94a3b8)' }}> — heads-up, not a sell signal (Minervini sells on price):</span>
                  <ul style={{ margin: '0.3rem 0 0', paddingLeft: '1.1rem' }}>
                    {data.eq_sell_risk.map((r, i) => <li key={i} style={{ marginTop: 2 }}>{r}</li>)}
                  </ul>
                </div>
              )}
              {data.macro_events && data.macro_events.length > 0 && (
                <div style={{
                  marginTop: '0.7rem', padding: '0.5rem 0.75rem', borderRadius: 6,
                  background: 'rgba(37,99,235,0.10)', border: '1px solid rgba(37,99,235,0.40)',
                  fontSize: '0.8rem', color: 'var(--ink, #eee)',
                }}>
                  <strong style={{ color: '#60a5fa' }}>📅 Macro event ahead</strong>
                  <span style={{ color: 'var(--cm-slate, #94a3b8)' }}> — binary event risk, not a sell signal (Minervini sells on price):</span>
                  <ul style={{ margin: '0.3rem 0 0', paddingLeft: '1.1rem' }}>
                    {data.macro_events.map((r, i) => <li key={i} style={{ marginTop: 2 }}>{r}</li>)}
                  </ul>
                </div>
              )}
              {data.earnings_quality && <EarningsQualityPanel eq={data.earnings_quality} />}
              <button type="button" className="hdiag__refresh" onClick={() => load(true)} disabled={loading}>↻ Re-run</button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
