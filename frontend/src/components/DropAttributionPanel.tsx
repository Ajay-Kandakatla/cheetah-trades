/* DropAttributionPanel — for each holding, is the move driven by the MARKET,
   its SECTOR, or the STOCK itself? Backend: /portfolio/attribution.
   Method + caveats: backend/portfolio/drop_attribution.py. */
import { useState } from 'react';
import { TickerCell } from './TickerCell';
import { useDropAttribution, type AttrVerdict, type AttributionRow } from '../hooks/usePortfolio';

const VERDICT: Record<AttrVerdict, { dot: string; label: string; color: string; hint: string }> = {
  macro:  { dot: '🌍', label: 'Macro',  color: 'var(--cm-slate, #8a93a6)', hint: "it's the market — ride it out" },
  sector: { dot: '🏭', label: 'Sector', color: 'var(--cm-amber, #d97706)', hint: 'your industry group is rotating' },
  stock:  { dot: '🎯', label: 'Stock',  color: 'var(--negative, #dc2626)', hint: 'stock-specific — check the news' },
  quiet:  { dot: '·',  label: 'Quiet',  color: 'var(--rule, #555)',        hint: 'move too small to attribute' },
};

const pct = (n: number | null | undefined) => (n == null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(1)}%`);

export function DropAttributionPanel() {
  const [window, setWindow] = useState(5);
  const { data, loading, error } = useDropAttribution(window);

  const rows = data?.rows ?? [];
  const c = data?.counts;

  return (
    <section className="cm-card" style={{ padding: '1rem 1.1rem', marginTop: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', flexWrap: 'wrap', gap: '0.6rem' }}>
        <h2 className="day-section__h" style={{ margin: 0 }}>Why is it moving?</h2>
        <span className="sd-meta" style={{ color: 'var(--cm-slate)' }}>
          macro vs sector vs stock-specific
        </span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
          {[1, 5].map((w) => (
            <button key={w} type="button" onClick={() => setWindow(w)}
              className="sepa-btn"
              style={{
                padding: '0.2rem 0.6rem', fontSize: '0.75rem',
                fontWeight: window === w ? 700 : 400,
                borderColor: window === w ? 'var(--cm-ink, #888)' : 'var(--rule, #333)',
              }}>
              {w}-day
            </button>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.8rem', margin: '0.6rem 0',
                    fontSize: '0.72rem', color: 'var(--cm-slate)' }}>
        {(['macro', 'sector', 'stock'] as AttrVerdict[]).map((v) => (
          <span key={v}>
            <span style={{ color: VERDICT[v].color, fontWeight: 700 }}>{VERDICT[v].dot} {VERDICT[v].label}</span>
            {' — '}{VERDICT[v].hint}{c ? ` (${c[v as 'macro' | 'sector' | 'stock']})` : ''}
          </span>
        ))}
      </div>

      {error && <div className="sepa-err">Couldn't load attribution: {error}</div>}
      {loading && !data && <div style={{ color: 'var(--cm-slate)', padding: '0.6rem' }}>Decomposing your holdings…</div>}
      {data && rows.length === 0 && !loading && (
        <div style={{ color: 'var(--cm-slate)', padding: '0.6rem' }}>No holdings to analyze.</div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginTop: '0.4rem' }}>
        {rows.map((r) => <Row key={r.symbol} r={r} />)}
      </div>

      <p style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: '0.8rem', lineHeight: 1.4 }}>
        How it works: <em>expected move = beta × benchmark move</em>; the part left over is the stock itself.
        Honest caveat — beta drifts, single-day splits are noisy, and a stock-specific flag means
        "not explained by the market," <strong>not</strong> "confirmed news." It tells you where to look.
      </p>
    </section>
  );
}

function Row({ r }: { r: AttributionRow }) {
  const v = VERDICT[r.verdict];
  const moveColor = r.move_pct >= 0 ? 'var(--positive, #16a34a)' : 'var(--negative, #dc2626)';
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 2,
      padding: '0.5rem 0.6rem', borderRadius: 6,
      border: `1px solid var(--rule, #2a2a2a)`,
      opacity: r.verdict === 'quiet' ? 0.55 : 1,
      borderLeft: `3px solid ${v.color}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontSize: '0.85rem' }}>
        <strong style={{ minWidth: 54 }}><TickerCell symbol={r.symbol} size="0.82rem" nameWidth={12} /></strong>
        <span className="mono" style={{ color: moveColor, fontWeight: 700, minWidth: 64 }}>{pct(r.move_pct)}</span>
        <span style={{ color: v.color, fontWeight: 700, fontSize: '0.78rem' }}>{v.dot} {v.label}</span>
        <span className="mono" style={{ marginLeft: 'auto', fontSize: '0.68rem', color: 'var(--cm-slate)' }}>
          mkt {pct(r.market_move_pct)} · {r.sector_etf} {pct(r.sector_move_pct)}
        </span>
      </div>
      <div style={{ fontSize: '0.72rem', color: 'var(--cm-slate)' }}>{r.summary}</div>
    </div>
  );
}
