/* OpExPanel — options-expiration mechanics for one ticker, in the options-flow
 * tab. Next expiration + max-pain magnet + a dealer-gamma pin/amplify read with
 * the call/put walls that bracket the expected range.
 *
 * Honest by design: a tendency INTO expiration, not a guarantee. Max-pain leads
 * (gamma-agnostic, robust); the gamma sign is a heuristic flagged lower-
 * confidence on single names (where it can invert). Reads /options/opex/{sym}. */
import { useOpex } from '../hooks/useOpex';
import { EXPIRY_CHIP, regimeView, fmtGex, magnetDistance } from '../lib/opex';

const CARD: React.CSSProperties = {
  padding: '0.8rem 1rem',
  background: 'rgba(255,255,255,0.02)',
  border: '1px solid rgba(255,255,255,0.10)',
  borderRadius: 8,
  marginTop: '1rem',
};

function Tile({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div style={{ padding: '0.45rem 0.65rem', background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.06)', borderRadius: 6, minWidth: 110 }}>
      <div style={{ fontSize: '0.63rem', color: 'var(--cm-slate,#9ca3af)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{label}</div>
      <div className="mono" style={{ fontSize: '1rem', fontWeight: 800, color: color ?? '#e5e7eb', marginTop: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: 1 }}>{sub}</div>}
    </div>
  );
}

export function OpExPanel({ symbol }: { symbol: string }) {
  const { data, loading } = useOpex(symbol);

  if (loading && !data) {
    return <section style={CARD}><Eyebrow /><p className="sepa-empty">Reading the options chain…</p></section>;
  }
  if (!data || !data.found) {
    return (
      <section style={CARD}>
        <Eyebrow />
        <p style={{ fontSize: '0.8rem', color: 'var(--cm-slate)', margin: '0.4rem 0 0' }}>
          {data?.message ?? 'No options chain for this ticker.'}
        </p>
      </section>
    );
  }

  const exp = EXPIRY_CHIP[data.expiration_type] ?? EXPIRY_CHIP.weekly;
  const mp = data.max_pain;
  const g = data.gamma;
  const rv = regimeView(g?.regime);
  const singleName = data.gex_reliability === 'single_name';

  return (
    <section style={CARD}>
      <Eyebrow />

      {/* Next expiration */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', margin: '0.55rem 0' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '0.25rem 0.7rem',
          borderRadius: 12, fontWeight: 800, fontSize: '0.82rem',
          background: 'rgba(56,189,248,0.12)', border: '1px solid rgba(56,189,248,0.4)', color: '#38bdf8' }}
          title={`${exp.weight}. The 3rd-Friday monthly + quarterly quad-witching carry the heaviest open interest, so the pin tendency is strongest there.`}>
          {exp.icon} {exp.label}
        </span>
        <span className="mono" style={{ fontSize: '0.8rem', color: 'var(--cm-slate)' }}>
          {data.expiration_date} · in {data.days_to_expiry}d
        </span>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
        {mp && (
          <Tile label="Max pain" value={`$${mp.max_pain_strike}`}
            sub={`${magnetDistance(mp.pct_from_spot)}${mp.max_pain_tie ? ' · soft pin' : ''}`}
            color="#f59e0b" />
        )}
        {data.spot != null && <Tile label="Spot" value={`$${data.spot}`} />}
        {g && (
          <Tile label="Dealer gamma" value={`${rv.icon} ${rv.label}`}
            sub={`net GEX ${fmtGex(g.net_gex_dollars)} / 1%`} color={rv.color} />
        )}
        {g && (g.put_wall != null || g.call_wall != null) && (
          <Tile label="Gamma range" value={`$${g.put_wall ?? '—'} ↔ $${g.call_wall ?? '—'}`}
            sub="put wall ↔ call wall" />
        )}
      </div>

      {/* What it means */}
      {g && (
        <p style={{ margin: '0.6rem 0 0', fontSize: '0.82rem', lineHeight: 1.5, color: 'var(--cm-text,#d1d5db)' }}>
          <strong style={{ color: rv.color }}>{rv.icon} {rv.label}.</strong> {rv.blurb}.
          {mp && <> Into <strong>{data.expiration_date}</strong>, the magnet is <strong>${mp.max_pain_strike}</strong>.</>}
        </p>
      )}

      {/* Honesty caveats */}
      {singleName && g && (
        <p style={{ margin: '0.45rem 0 0', fontSize: '0.7rem', color: '#f59e0b' }}>
          ⚠️ Single-name: the gamma sign is a heuristic and can invert on momentum leaders — treat the pin/amplify read as low-confidence; max-pain is the more robust magnet.
        </p>
      )}
      {g && g.oi_coverage_pct < 80 && (
        <p style={{ margin: '0.3rem 0 0', fontSize: '0.68rem', color: 'var(--cm-slate)' }}>
          Gamma from {g.oi_coverage_pct}% of open interest (rest missing greeks).
        </p>
      )}
      <p style={{ margin: '0.5rem 0 0', fontSize: '0.7rem', lineHeight: 1.45, color: 'var(--cm-slate)', fontStyle: 'italic' }}>
        A tendency into expiration, not a guarantee — confirm with the SEPA setup. An earnings print or macro shock overwhelms dealer hedging.
      </p>
    </section>
  );
}

function Eyebrow() {
  return (
    <div>
      <div className="eyebrow">OpEx · options expiration mechanics</div>
      <h3 style={{ margin: '0.1rem 0 0', fontSize: '1rem' }}>Where expiration pulls the price</h3>
    </div>
  );
}
