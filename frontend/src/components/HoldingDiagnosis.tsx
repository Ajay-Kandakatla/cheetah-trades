/* HoldingDiagnosis — "what's driving this move?" expander on a portfolio card.

   Ajay 2026-06-04: a write-up explaining the trend — accumulation/distribution,
   macro, sector rotation, liquidity, or stock-specific — with a factor scorecard
   and an LLM read (Claude Sonnet). Lazy: fetches /portfolio/diagnosis/{symbol}
   only when expanded (the LLM write-up is the slow part; the backend caches it). */
import { useState } from 'react';
import { useEffect } from 'react';
import { API } from '../lib/apiBase';

type Factor = { score: number; note: string };
type Diagnosis = {
  symbol: string;
  sector?: string | null;
  name?: string | null;
  move_pct: number | null;
  verdict?: string | null;
  headline_label?: string;
  uptrend_driver?: { label: string; note: string } | null;
  writeup?: string | null;
  scorecard?: Record<string, Factor>;
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
              {data.headline_label && (
                <div className="hdiag__headline">
                  {data.uptrend_driver ? 'Powered by: ' : 'Likely driver: '}<strong>{data.headline_label}</strong>
                  {data.sector && data.sector !== '—' && <span className="hdiag__sector"> · {data.sector}</span>}
                  {data.move_pct != null && <span className="hdiag__move"> · {symbol} {data.move_pct >= 0 ? '+' : ''}{data.move_pct}% (5d)</span>}
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
              <button type="button" className="hdiag__refresh" onClick={() => load(true)} disabled={loading}>↻ Re-run</button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
