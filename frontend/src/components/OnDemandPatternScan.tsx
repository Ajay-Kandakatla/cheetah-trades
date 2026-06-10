/* OnDemandPatternScan — the 📐 "scan these names now" button + results panel
 * for the Day Trading and Scalping pages (Ajay 2026-06-10: "I do not see an
 * on-demand scan button on the scalper page and don't see the patterns in the
 * day trading page").
 *
 * Why it exists: those pages' universes are today's liquid movers — mostly
 * OUTSIDE the stored verdict scan (qualifiers + holdings + leaders), so the
 * passive chips had nothing to show. This button computes fresh verdicts for
 * exactly the names on screen via GET /patterns/verdicts-for (cached daily
 * frames, ~10ms/symbol) and renders tiny cards: matched patterns first
 * (confirmed ✓ today/1d, forming with % to line), candle reads, and an honest
 * "n with no pattern" count. Click a card → the full SEPA read. */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../lib/apiBase';
import type { PatternVerdict } from '../hooks/usePatternVerdicts';

const C = { green: '#10b981', red: '#ef4444', amber: '#f59e0b', muted: '#94a3b8', sub: '#6b7280', gold: 'var(--gold,#c9a227)' };
const SHORT: Record<string, string> = {
  double_bottom: 'Double bottom', triple_bottom: 'Triple bottom',
  inverse_head_shoulders: 'Inv H&S', cup_with_handle: 'Cup w/ handle',
};
const READ_COLOR: Record<string, string> = {
  bullish_reversal_setup: C.green, bearish_warning: C.red, indecision: C.muted,
};

type Resp = { generated_at: number; n_symbols: number; n_matched: number;
              verdicts: PatternVerdict[]; disclaimer?: string };

export function OnDemandPatternScan({ symbols, title = '📐 Daily-pattern scan — the names on this page' }: {
  symbols: string[]; title?: string;
}) {
  const navigate = useNavigate();
  const [data, setData] = useState<Resp | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(false);
  const syms = Array.from(new Set(symbols.filter(Boolean).map((s) => s.toUpperCase()))).slice(0, 60);

  const scan = () => {
    if (!syms.length) return;
    setBusy(true);
    setErr(false);
    fetch(`${API}/patterns/verdicts-for?symbols=${encodeURIComponent(syms.join(','))}`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(setData)
      .catch(() => setErr(true))
      .finally(() => setBusy(false));
  };

  const matched = (data?.verdicts || []).filter((v) => v.matches.length > 0)
    .sort((a, b) => (a.matches[0].status === 'confirmed' ? 0 : 1) - (b.matches[0].status === 'confirmed' ? 0 : 1));
  const candleOnly = (data?.verdicts || []).filter((v) => !v.matches.length && (v.candles?.formations?.length || 0) > 0);
  const noMatch = (data?.verdicts || []).filter((v) => v.no_match);

  return (
    <section style={{ margin: '0.9rem 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 6 }}>
        <span className="eyebrow">{title}</span>
        <button onClick={scan} disabled={busy || !syms.length}
                title={syms.length ? `Run the four Bulkowski detectors + candle reads on ${syms.length} names' daily charts right now` : 'No symbols on the page yet'}
                style={{ fontSize: '0.74rem', fontWeight: 700, cursor: busy ? 'wait' : 'pointer',
                         padding: '0.25rem 0.75rem', borderRadius: 7, border: 'none',
                         background: C.gold, color: '#1a1a1a', opacity: busy || !syms.length ? 0.6 : 1 }}>
          {busy ? 'Scanning…' : `📐 Scan ${syms.length} names`}
        </button>
        {data && (
          <span style={{ fontSize: '0.68rem', color: C.sub }}>
            {data.n_matched} match a pattern · {candleOnly.length} candle reads · {noMatch.length} no pattern
            {' · '}{new Date(data.generated_at * 1000).toLocaleTimeString()}
          </span>
        )}
      </div>
      {err && <p className="mono" style={{ color: C.red, fontSize: '0.74rem' }}>Scan failed — retry.</p>}

      {data && matched.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(168px, 1fr))', gap: 7 }}>
          {matched.map((v) => {
            const m = v.matches[0];
            const conf = m.status === 'confirmed';
            const col = conf ? C.green : C.amber;
            const bearish = (v.candles?.formations || []).some((f) => f.read === 'bearish_warning');
            return (
              <div key={v.symbol} role="button" tabIndex={0}
                   onClick={() => navigate(`/sepa/${encodeURIComponent(v.symbol)}`)}
                   onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') navigate(`/sepa/${encodeURIComponent(v.symbol)}`); }}
                   style={{ padding: '0.45rem 0.55rem', borderRadius: 9, cursor: 'pointer',
                            background: 'var(--bg-raised,#16181d)', border: `1px solid ${col}55` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <b style={{ fontSize: '0.86rem' }}>{v.symbol}</b>
                  <span style={{ marginLeft: 'auto', fontSize: '0.62rem', fontWeight: 700,
                                 color: v.sepa?.is_buyable ? C.green : v.sepa?.is_candidate ? C.muted : C.sub }}>
                    {v.sepa?.is_buyable ? '✅ BUYABLE' : v.sepa?.is_candidate ? 'qualifier' : 'mover'}
                  </span>
                </div>
                <div style={{ fontSize: '0.7rem', color: col, fontWeight: 600, marginTop: 1 }}>
                  📐 {SHORT[m.pattern] || m.pattern} {conf
                    ? `✓ ${m.bars_since_confirm === 0 ? 'today' : '1d'}`
                    : `· ${m.to_confirm_pct}% to line`}
                </div>
                <div style={{ fontSize: '0.66rem', color: C.muted, marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
                  line {m.neckline} → tgt {m.target} · <span style={{ color: C.red }}>stop {m.stop}</span>
                </div>
                {bearish && <div style={{ fontSize: '0.62rem', color: C.red, marginTop: 2 }}>⚠ bearish candle read</div>}
              </div>
            );
          })}
        </div>
      )}

      {data && candleOnly.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 7 }}>
          {candleOnly.map((v) => {
            const f = v.candles!.formations[0];
            const col = READ_COLOR[f.read] || C.muted;
            return (
              <button key={v.symbol} onClick={() => navigate(`/sepa/${encodeURIComponent(v.symbol)}`)}
                      title={`${f.note}. ${f.stat || ''}`}
                      style={{ fontSize: '0.7rem', padding: '2px 9px', borderRadius: 6, cursor: 'pointer',
                               background: 'var(--bg-sunken,#0f1115)', color: col, border: `1px solid ${col}44` }}>
                {v.symbol} · {f.name.replace(/_/g, ' ')}
              </button>
            );
          })}
        </div>
      )}

      {data && (
        <div style={{ fontSize: '0.64rem', color: C.sub, marginTop: 6 }}>
          {noMatch.length > 0 && <>No pattern: {noMatch.map((v) => v.symbol).join(' · ')} — an answer, not a gap. </>}
          {data.disclaimer}
        </div>
      )}
    </section>
  );
}
