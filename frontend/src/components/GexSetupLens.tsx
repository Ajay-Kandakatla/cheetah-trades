/* GexSetupLens — compact GEX + VEX "best case" read for the Setup tab
 * (Ajay 2026-07-17: "add VEX and GEX to individual stocks to show me what is
 * the best case possibility in the setup tab"). Reads the SAME
 * /options/opex/{sym} payload the OpEx panel uses — the backend's best_case
 * block does the thinking (options/opex.best_case), this only renders, so
 * the lens can never disagree with the engine. Renders nothing when the
 * chain is missing (thin options) — the Setup tab stays clean. */
import { useOpex } from '../hooks/useOpex';
import { InfoButton } from './InfoButton';
import { fmtGex } from '../lib/opex';
import { nodeChips, type BoardRow } from '../lib/gexBoard';

const BIAS_STYLE: Record<string, { color: string; label: string }> = {
  bullish: { color: 'var(--positive, #34d399)', label: '🟢 gamma helps' },
  bearish: { color: 'var(--negative, #f87171)', label: '🔴 gamma hurts' },
  mixed:   { color: 'var(--warning, #f59e0b)',  label: '🌫️ gamma split' },
};

export function GexSetupLens({ symbol }: { symbol: string }) {
  const { data } = useOpex(symbol);
  const bc = (data as any)?.best_case;
  const gamma = (data as any)?.gamma;
  const vex = (data as any)?.vex;
  if (!data || !bc || !gamma) return null;

  const bias = BIAS_STYLE[bc.bias] ?? BIAS_STYLE.mixed;
  const chips = nodeChips({
    symbol,
    spot: (data as any).spot,
    flip_strike: gamma.flip_strike,
    call_wall: gamma.call_wall,
    put_wall: gamma.put_wall,
    magnet: gamma.magnet_strike,
  } as BoardRow);

  return (
    <div style={{ border: '1px solid var(--cm-border, #2a2f3a)', borderRadius: 10,
                  padding: '0.6rem 0.75rem', margin: '0.6rem 0',
                  background: 'var(--cm-card, #161a22)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <b style={{ fontSize: '0.8rem' }}>🎯 Options lens</b>
        <span style={{ fontSize: '0.72rem', fontWeight: 700, color: bias.color }}>{bias.label}</span>
        <span className="mono" style={{ fontSize: '0.7rem', opacity: 0.85 }}>
          {fmtGex(gamma.net_gex_dollars)} GEX
          {vex?.net_vex_dollars != null ? ` · ${fmtGex(vex.net_vex_dollars)} VEX` : ''}
        </span>
        <InfoButton inline title="GEX + VEX in one minute" align="right">
          <p><strong>GEX</strong> — how market makers must hedge as price moves.
            Positive (pinning): they buy dips → your setup gets help holding its
            pivot. Negative (amplifying): their hedging pushes moves further —
            breakouts run harder but failures slide harder too.</p>
          <p><strong>VEX (vanna)</strong> — how their hedge shifts when IV moves.
            "Tailwind" = falling IV forces dealers to buy stock — the calm
            grind-up fuel.</p>
          <p>Heuristic dealer-book math — strongest on index/ETF, approximate on
            single names. It never overrides the SEPA setup; it colors it.</p>
        </InfoButton>
      </div>
      <p style={{ fontSize: '0.76rem', margin: '0.35rem 0 0' }}>
        <b>{bc.headline}</b> {bc.path}
      </p>
      <p style={{ fontSize: '0.72rem', margin: '0.2rem 0 0', color: 'var(--cm-slate, #94a3b8)' }}>
        Risk: {bc.risk}{bc.vanna_note ? ` · VEX: ${bc.vanna_note}.` : ''}
      </p>
      {chips.length > 0 && (
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginTop: 6 }}>
          {chips.map((c) => (
            <span key={c.label} className="mono" title={c.label}
                  style={{ fontSize: '0.68rem', border: '1px solid var(--cm-border, #2a2f3a)',
                           borderRadius: 999, padding: '1px 7px' }}>
              {c.icon} {c.label} {c.text}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
