/* SepaGlobalCard — the minimal, jargon-free card for the SEPA Global page.
 * Shows a traffic-light verdict, plain-English reason, the buy zone, the
 * "sell if" stop with the % at risk (risk-first, Minervini), and a simple
 * strength label. Pure presentational — takes a GlobalCard (see lib/sepaGlobal). */
import type { GlobalCard } from '../lib/sepaGlobal';
import { LeveragedBadge } from './LeveragedBadge';

const TONE: Record<GlobalCard['tone'], string> = {
  green: 'var(--positive, #10b981)',
  amber: 'var(--gold, #c9a227)',
  red: 'var(--negative, #f87171)',
  slate: 'var(--cm-slate, #94a3b8)',
};

function money(n: number | null): string {
  return n == null ? '—' : `$${n.toFixed(2)}`;
}

export function SepaGlobalCard({ card, onClick }: { card: GlobalCard; onClick?: () => void }) {
  const tone = TONE[card.tone];
  const chg = card.dayChangePct;
  return (
    <div
      data-testid="global-card"
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      title={onClick ? 'Tap for the details' : undefined}
      onClick={onClick}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } } : undefined}
      style={{
        border: '1px solid var(--cm-border, #2a2f3a)',
        borderLeft: `4px solid ${tone}`,
        borderRadius: 10,
        padding: '0.7rem 0.85rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.4rem',
        background: 'var(--cm-card, #161a22)',
        cursor: onClick ? 'pointer' : undefined,
      }}
    >
      {/* Row 1: ticker + name ............ price + day change */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '0.5rem' }}>
        <div style={{ minWidth: 0 }}>
          <span style={{ fontWeight: 800, fontSize: '1.02rem' }}>{card.symbol}</span>
          <LeveragedBadge symbol={card.symbol} name={card.name} compact />
          {card.name && (
            <span style={{ color: 'var(--cm-slate, #94a3b8)', marginLeft: 6, fontSize: '0.82rem' }}>
              {card.name}
            </span>
          )}
        </div>
        <div style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
          {card.isLive && (
            <span
              title="Live price"
              style={{
                display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
                background: 'var(--positive, #10b981)', marginRight: 5, verticalAlign: 'middle',
              }}
            />
          )}
          <span style={{ fontWeight: 700 }}>{money(card.price)}</span>
          {chg != null && (
            <span
              style={{
                marginLeft: 6, fontSize: '0.82rem',
                color: chg >= 0 ? 'var(--positive, #10b981)' : 'var(--negative, #f87171)',
              }}
            >
              {chg >= 0 ? '+' : ''}{chg.toFixed(1)}%
            </span>
          )}
        </div>
      </div>

      {/* Row 2: verdict pill + strength */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <span
          style={{
            background: tone, color: '#0b0e14', fontWeight: 800, fontSize: '0.74rem',
            padding: '0.12rem 0.5rem', borderRadius: 999,
          }}
        >
          {card.verdictLabel}
        </span>
        <span style={{ fontSize: '0.74rem', color: 'var(--cm-slate, #94a3b8)' }}>
          Strength: <strong style={{ color: 'var(--cm-fg, #e6e8ec)' }}>{card.strength}</strong>
        </span>
      </div>

      {/* Row 3: plain reason */}
      <p style={{ margin: 0, fontSize: '0.86rem', lineHeight: 1.35 }}>{card.reason}</p>

      {/* Row 4: the only numbers a beginner needs — buy zone + sell-if/risk */}
      {(card.buyZone || card.sellIf != null) && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem 1.1rem', fontSize: '0.82rem' }}>
          {card.buyZone && (
            <span>
              <span style={{ color: 'var(--cm-slate, #94a3b8)' }}>Buy range </span>
              <strong>{money(card.buyZone.lo)}–{money(card.buyZone.hi)}</strong>
            </span>
          )}
          {card.sellIf != null && (
            <span>
              <span style={{ color: 'var(--cm-slate, #94a3b8)' }}>Sell if it falls to </span>
              <strong>{money(card.sellIf)}</strong>
              {card.riskPct != null && (
                <span style={{ color: 'var(--negative, #f87171)' }}> (−{card.riskPct}% risk)</span>
              )}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
