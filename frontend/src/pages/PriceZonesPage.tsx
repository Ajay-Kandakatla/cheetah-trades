import { useState, type FormEvent } from 'react';
import { API } from '../lib/apiBase';

/* ==========================================================================
   PriceZonesPage — on-demand per-ticker supply/demand zones + entry read.
   Type any symbol → the price-structure bands (swing-high clusters = overhead
   supply / resistance; swing-low clusters = demand / support, weighted by tests
   + volume), where the live price sits, and a plain favorable/caution/neutral
   entry read. Configured method (not a book method); decision-support, not advice.
   Backend: GET /supply-demand/price-zones/{symbol} (supply_demand/price_zones.py).
   ========================================================================== */

type Zone = {
  kind: 'supply' | 'demand';
  lo: number; hi: number; mid: number;
  touches: number; volume: number; strength: number;
  bars_since_test: number; in_price?: boolean;
};
type Verdict = {
  state: string; entry_read: 'favorable' | 'caution' | 'neutral'; label: string;
  resistance_pct: number | null; support_pct: number | null;
};
type ZonesResp = {
  symbol: string; last_price: number;
  supply_zones: Zone[]; demand_zones: Zone[];
  nearest_resistance: Zone | null; nearest_support: Zone | null;
  verdict: Verdict; disclaimer: string; error?: string;
};

const READ_COLOR: Record<string, string> = {
  favorable: '#10b981', caution: '#f59e0b', neutral: '#94a3b8',
};

export function PriceZonesPage() {
  const [input, setInput] = useState('');
  const [data, setData] = useState<ZonesResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = async (sym: string) => {
    const s = sym.trim().toUpperCase();
    if (!s) return;
    setLoading(true); setErr(null); setData(null);
    try {
      const r = await fetch(`${API}/supply-demand/price-zones/${encodeURIComponent(s)}`);
      const j: ZonesResp = await r.json();
      if (j.error) { setErr(`${s}: ${j.error}`); }
      else setData(j);
    } catch (e) {
      setErr(`Could not load ${s} — ${String(e)}`);
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e: FormEvent) => { e.preventDefault(); run(input); };

  // Ladder rows: all bands + the live price marker, sorted high → low.
  const rows: Array<{ kind: 'price' } | Zone> = data
    ? [
        ...data.supply_zones, ...data.demand_zones,
        { kind: 'price' as const } as any,
      ].sort((a: any, b: any) => {
        const pa = a.kind === 'price' ? data.last_price : a.mid;
        const pb = b.kind === 'price' ? data.last_price : b.mid;
        return pb - pa;
      })
    : [];

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: '1rem' }}>
      <h1 style={{ fontSize: '1.25rem', marginBottom: 4 }}>Supply / Demand Zones</h1>
      <p style={{ color: 'var(--ink-muted, #94a3b8)', fontSize: '0.8rem', marginTop: 0 }}>
        Type any ticker — where supply (resistance) and demand (support) sit, and whether
        it’s a clean place to enter. Decision-support, not advice.
      </p>

      <form onSubmit={onSubmit} style={{ display: 'flex', gap: 8, margin: '0.8rem 0 1.2rem' }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. NVDA"
          autoCapitalize="characters"
          style={{
            flex: 1, padding: '0.55rem 0.7rem', fontSize: '1rem',
            background: 'var(--bg-sunken, #0f1115)', color: 'inherit',
            border: '1px solid var(--hairline, #2a2a2a)', borderRadius: 8,
            textTransform: 'uppercase',
          }}
        />
        <button type="submit" disabled={loading}
          style={{
            padding: '0.55rem 1.1rem', fontWeight: 600, borderRadius: 8, cursor: 'pointer',
            background: 'var(--gold, #c9a227)', color: '#1a1a1a', border: 'none',
          }}>
          {loading ? '…' : 'Check'}
        </button>
      </form>

      {err && <div style={{ color: '#f87171', fontSize: '0.85rem' }}>{err}</div>}

      {data && (
        <>
          {/* Verdict */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14,
            padding: '0.7rem 0.9rem', borderRadius: 10,
            border: `1px solid ${READ_COLOR[data.verdict.entry_read]}55`,
            background: `${READ_COLOR[data.verdict.entry_read]}14`,
          }}>
            <span style={{ fontSize: '1.4rem' }}>
              {data.verdict.entry_read === 'favorable' ? '🟢'
                : data.verdict.entry_read === 'caution' ? '🟠' : '⚪️'}
            </span>
            <div>
              <div style={{ fontWeight: 700, color: READ_COLOR[data.verdict.entry_read] }}>
                {data.symbol} ${data.last_price} · {data.verdict.state.replace(/_/g, ' ')}
              </div>
              <div style={{ fontSize: '0.84rem', lineHeight: 1.35 }}>{data.verdict.label}</div>
            </div>
          </div>

          {/* Nearest levels */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 14, fontSize: '0.8rem' }}>
            <div style={{ flex: 1, padding: '0.5rem 0.7rem', borderRadius: 8, background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.35)' }}>
              <div style={{ color: '#f87171', fontWeight: 600 }}>↑ Resistance</div>
              {data.nearest_resistance
                ? <div>${data.nearest_resistance.lo}–${data.nearest_resistance.hi}
                    {data.verdict.resistance_pct != null && <> (+{data.verdict.resistance_pct}%)</>}
                    {' '}· {data.nearest_resistance.touches}× tested</div>
                : <div style={{ opacity: 0.7 }}>none — clear above (at/near highs)</div>}
            </div>
            <div style={{ flex: 1, padding: '0.5rem 0.7rem', borderRadius: 8, background: 'rgba(16,185,129,0.10)', border: '1px solid rgba(16,185,129,0.35)' }}>
              <div style={{ color: '#34d399', fontWeight: 600 }}>↓ Support</div>
              {data.nearest_support
                ? <div>${data.nearest_support.lo}–${data.nearest_support.hi}
                    {data.verdict.support_pct != null && <> (−{data.verdict.support_pct}%)</>}
                    {' '}· {data.nearest_support.touches}× tested</div>
                : <div style={{ opacity: 0.7 }}>none in range</div>}
            </div>
          </div>

          {/* Ladder */}
          <div style={{ display: 'grid', gap: 4 }}>
            {rows.map((row: any, i) => {
              if (row.kind === 'price') {
                return (
                  <div key={`px-${i}`} style={{
                    display: 'flex', alignItems: 'center', gap: 8, padding: '0.3rem 0.6rem',
                    borderRadius: 6, background: 'var(--gold, #c9a227)', color: '#1a1a1a', fontWeight: 700,
                  }}>
                    <span style={{ flex: 1 }}>▸ Current price</span>
                    <span>${data.last_price}</span>
                  </div>
                );
              }
              const isSupply = row.kind === 'supply';
              const c = isSupply ? '#f87171' : '#34d399';
              return (
                <div key={`z-${i}`} style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '0.35rem 0.6rem',
                  borderRadius: 6, fontSize: '0.82rem',
                  background: `${c}12`, border: `1px solid ${c}33`,
                }}>
                  <span style={{ color: c, fontWeight: 600, width: 70 }}>
                    {isSupply ? 'SUPPLY' : 'DEMAND'}
                  </span>
                  <span style={{ flex: 1 }}>${row.lo} – ${row.hi}</span>
                  <span style={{ opacity: 0.75 }}>{row.touches}× · str {row.strength}</span>
                </div>
              );
            })}
          </div>

          <p style={{ color: 'var(--ink-subtle, #8a93a6)', fontSize: '0.68rem', marginTop: 14 }}>
            {data.disclaimer}
          </p>
        </>
      )}
    </div>
  );
}
