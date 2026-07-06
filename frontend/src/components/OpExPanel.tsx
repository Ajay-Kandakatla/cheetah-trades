/* OpExPanel — options-expiration mechanics for one ticker, in the options-flow
 * tab. Next expiration + max-pain magnet + a dealer-gamma pin/amplify read with
 * the call/put walls that bracket the expected range.
 *
 * Honest by design: a tendency INTO expiration, not a guarantee. Max-pain leads
 * (gamma-agnostic, robust); the gamma sign is a heuristic flagged lower-
 * confidence on single names (where it can invert). Reads /options/opex/{sym}. */
import { useOpex } from '../hooks/useOpex';
import { InfoButton } from './InfoButton';
import { EXPIRY_CHIP, cavemanSummary, regimeView, fmtGex, magnetDistance } from '../lib/opex';

const CARD: React.CSSProperties = {
  padding: '0.8rem 1rem',
  background: 'rgba(255,255,255,0.02)',
  border: '1px solid rgba(255,255,255,0.10)',
  borderRadius: 8,
  marginTop: '1rem',
};

function Tile({ label, value, sub, color, info }: {
  label: string; value: string; sub?: string; color?: string; info?: React.ReactNode;
}) {
  return (
    <div style={{ padding: '0.45rem 0.65rem', background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.06)', borderRadius: 6, minWidth: 110 }}>
      <div style={{ fontSize: '0.63rem', color: 'var(--cm-slate,#9ca3af)', textTransform: 'uppercase',
        letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: 4 }}>{label}{info}</div>
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
            color="#f59e0b"
            info={
              <InfoButton title="Max pain — the magnet" inline align="left">
                <p><strong>The price where option BUYERS lose the most</strong> (and option
                  sellers keep the most). Add up what every call and put would pay out at each
                  possible price — the price with the smallest total payout is "max pain."</p>
                <p>Why it matters: prices often drift toward this level in the days before
                  expiration, because that's where the hedging pressure from dealers eases off.
                  It's a magnet, not a law.</p>
                <p><em>"Soft pin"</em> = two strikes were nearly tied, so the magnet is a zone,
                  not one exact number.</p>
              </InfoButton>
            } />
        )}
        {data.spot != null && <Tile label="Spot" value={`$${data.spot}`} sub="today's stock price" />}
        {g && (
          <Tile label="Dealer gamma" value={`${rv.icon} ${rv.label}`}
            sub={`net GEX ${fmtGex(g.net_gex_dollars)} / 1%`} color={rv.color}
            info={
              <InfoButton title="Dealer gamma — brake or tailwind" inline align="left">
                <p>Market makers sold most of these options, and they hedge by trading the
                  stock itself. Which direction they must trade creates one of two weather
                  systems:</p>
                <p>📌 <strong>Pinning (brake)</strong> — they sell rallies and buy dips.
                  Moves get smothered; the stock tends to sit in a range into expiration.</p>
                <p>🚀 <strong>Amplifying (tailwind)</strong> — they buy rallies and sell dips.
                  Moves get pushed further; breakouts and breakdowns both run hotter.</p>
                <p><em>net GEX</em> = the size of that force, in dollars of stock dealers must
                  trade per 1% move. Bigger number = stronger weather.</p>
              </InfoButton>
            } />
        )}
        {g && (g.put_wall != null || g.call_wall != null) && (
          <Tile label="Gamma range" value={`$${g.put_wall ?? '—'} ↔ $${g.call_wall ?? '—'}`}
            sub="put wall ↔ call wall"
            info={
              <InfoButton title="Gamma range — floor and ceiling" inline align="left">
                <p>The two strikes where dealer hedging is heaviest.</p>
                <p><strong>Put wall</strong> (left number) — heavy downside hedging tends to
                  act like a <strong>floor</strong>: dips into it often slow down or bounce.</p>
                <p><strong>Call wall</strong> (right number) — heavy upside hedging tends to
                  act like a <strong>ceiling</strong>: rallies into it often stall.</p>
                <p>Between the two is the expected playing field into expiration. A decisive
                  move OUTSIDE the range means the weather has changed — re-check the read.</p>
              </InfoButton>
            } />
        )}
      </div>

      {/* Caveman translation — dynamic plain-English rewrite of the numbers above */}
      {(() => {
        const lines = cavemanSummary(data);
        if (!lines.length) return null;
        return (
          <div style={{ marginTop: '0.7rem', padding: '0.55rem 0.75rem', borderRadius: 6,
            background: 'rgba(56,189,248,0.06)', border: '1px solid rgba(56,189,248,0.25)' }}>
            <div style={{ fontSize: '0.7rem', fontWeight: 800, color: '#38bdf8', marginBottom: '0.3rem' }}>
              🪓 IN PLAIN ENGLISH
            </div>
            <ul style={{ margin: 0, padding: '0 0 0 1rem', display: 'grid', gap: '0.25rem' }}>
              {lines.map((l, i) => (
                <li key={i} style={{ fontSize: '0.78rem', lineHeight: 1.5, color: 'var(--cm-text,#d1d5db)' }}>{l}</li>
              ))}
            </ul>
          </div>
        );
      })()}

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
      <h3 style={{ margin: '0.1rem 0 0', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: 6 }}>
        Where expiration pulls the price
        <InfoButton title="What is OpEx?" inline align="left">
          <p><strong>OpEx = options expiration.</strong> Options are side-bets on the stock
            with a deadline. Every Friday some expire; the <strong>3rd Friday of the month</strong> is
            the big one, and four times a year ("quad-witching") is the biggest.</p>
          <p>Billions of dollars of these bets sit at specific prices (strikes). The market
            makers on the other side hedge by buying/selling the actual stock — and that
            hedging <em>pulls</em> the stock around in the days before the deadline.</p>
          <p>This panel reads those forces: the <strong>magnet</strong> (max pain), the
            <strong> weather</strong> (brake vs tailwind), and the <strong>playing field</strong>
            (put wall to call wall). After expiration the board resets.</p>
        </InfoButton>
      </h3>
    </div>
  );
}
