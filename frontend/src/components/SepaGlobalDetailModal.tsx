/* SepaGlobalDetailModal — the plain-English "click to details" view for SEPA
 * Global. Shows the trade plan (buy range, stop + risk, targets, reward:risk)
 * and a "why it's strong" read (leadership, trend, volume) — the important
 * details a beginner needs, without the admin page's jargon. */
import type { GlobalDetail } from '../lib/sepaGlobal';

const TONE: Record<GlobalDetail['tone'], string> = {
  green: 'var(--positive, #10b981)',
  amber: 'var(--gold, #c9a227)',
  red: 'var(--negative, #f87171)',
  slate: 'var(--cm-slate, #94a3b8)',
};

const money = (n: number | null) => (n == null ? '—' : `$${n.toFixed(2)}`);
const Label = ({ children }: { children: React.ReactNode }) => (
  <span style={{ color: 'var(--cm-slate, #94a3b8)' }}>{children}</span>
);

export function SepaGlobalDetailModal({ detail, onClose }: { detail: GlobalDetail; onClose: () => void }) {
  const tone = TONE[detail.tone];
  const chg = detail.dayChangePct;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`${detail.symbol} details`}
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 9500, background: 'rgba(0,0,0,0.55)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: 460, maxHeight: '88vh', overflowY: 'auto',
          background: 'var(--cm-card, #161a22)', border: '1px solid var(--cm-border, #2a2f3a)',
          borderTop: `4px solid ${tone}`, borderRadius: 12, padding: '1rem 1.1rem',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
          <div>
            <div style={{ fontWeight: 800, fontSize: '1.15rem' }}>{detail.symbol}</div>
            {detail.name && <div style={{ color: 'var(--cm-slate, #94a3b8)', fontSize: '0.85rem' }}>{detail.name}</div>}
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontWeight: 700 }}>
              {detail.isLive && (
                <span title="Live price" style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: 'var(--positive, #10b981)', marginRight: 5, verticalAlign: 'middle' }} />
              )}
              {money(detail.price)}
              {chg != null && (
                <span style={{ marginLeft: 6, fontSize: '0.82rem', color: chg >= 0 ? 'var(--positive, #10b981)' : 'var(--negative, #f87171)' }}>
                  {chg >= 0 ? '+' : ''}{chg.toFixed(1)}%
                </span>
              )}
            </div>
            <button onClick={onClose} aria-label="Close" style={{ marginTop: 6, background: 'transparent', border: '1px solid var(--cm-border, #2a2f3a)', color: 'inherit', borderRadius: 6, cursor: 'pointer', padding: '0.1rem 0.5rem' }}>✕</button>
          </div>
        </div>

        {/* Verdict + strength + reason */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '0.7rem 0 0.4rem' }}>
          <span style={{ background: tone, color: '#0b0e14', fontWeight: 800, fontSize: '0.78rem', padding: '0.15rem 0.6rem', borderRadius: 999 }}>
            {detail.verdictLabel}
          </span>
          <span style={{ fontSize: '0.8rem', color: 'var(--cm-slate, #94a3b8)' }}>
            Strength: <strong style={{ color: 'var(--cm-fg, #e6e8ec)' }}>{detail.strength}</strong>
          </span>
        </div>
        <p style={{ margin: '0 0 0.6rem', fontSize: '0.9rem', lineHeight: 1.4 }}>{detail.reason}</p>

        {/* Your plan */}
        <div style={{ borderTop: '1px solid var(--cm-border, #2a2f3a)', paddingTop: '0.6rem' }}>
          <div style={{ fontWeight: 700, fontSize: '0.84rem', marginBottom: 4 }}>Your plan</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: '0.86rem' }}>
            {detail.buyZone && <div><Label>Buy range </Label><strong>{money(detail.buyZone.lo)}–{money(detail.buyZone.hi)}</strong></div>}
            {detail.sellIf != null && (
              <div>
                <Label>Sell if it falls to </Label><strong>{money(detail.sellIf)}</strong>
                {detail.riskPct != null && <span style={{ color: 'var(--negative, #f87171)' }}> (−{detail.riskPct}% risk)</span>}
              </div>
            )}
            {detail.targets.map((t) => (
              <div key={t.label}>
                <Label>{t.label} </Label><strong>{money(t.price)}</strong>
                {t.pct != null && <span style={{ color: 'var(--positive, #10b981)' }}> (+{t.pct}%)</span>}
              </div>
            ))}
            {detail.rewardRisk != null && (
              <div><Label>Reward vs risk </Label><strong>{detail.rewardRisk.toFixed(1)}×</strong> <Label>— the potential gain is {detail.rewardRisk.toFixed(1)}× what you risk.</Label></div>
            )}
            {!detail.buyZone && detail.sellIf == null && detail.targets.length === 0 && (
              <Label>No trade plan yet — it isn’t at a buy point.</Label>
            )}
          </div>
        </div>

        {/* Why it's strong */}
        <div style={{ borderTop: '1px solid var(--cm-border, #2a2f3a)', paddingTop: '0.6rem', marginTop: '0.6rem' }}>
          <div style={{ fontWeight: 700, fontSize: '0.84rem', marginBottom: 4 }}>Why it’s on the list</div>
          <ul style={{ margin: 0, paddingLeft: '1.1rem', fontSize: '0.86rem', lineHeight: 1.45 }}>
            <li>{detail.trendText}</li>
            {detail.leadership != null && <li>Stronger than <strong>{Math.round(detail.leadership)}%</strong> of all stocks (relative strength).</li>}
            {detail.volumeText && <li>{detail.volumeText}</li>}
          </ul>
        </div>

        <p className="mono" style={{ margin: '0.8rem 0 0', fontSize: '0.72rem', color: 'var(--cm-slate, #94a3b8)' }}>
          Educational only — not financial advice.
        </p>
      </div>
    </div>
  );
}
