/* BuyVerdictPanel — the full two-pillar PASS/PARTIAL/FAIL breakdown that leads
 * the SEPA detail Analysis tab (Ajay 2026-06-16: "make the sales logic follow
 * Minervini's verdict of buyable stock AND Pradeep Bonde's, give it a pass/fail").
 *
 * Reads row.buy_verdict (sepa/buyable_verdict.py). The combined headline, then
 * the two independent pillars side by side:
 *   • Minervini — is this a BUYABLE STOCK? (qualifier p.79 + breakout pp.198-203)
 *   • Bonde     — is the SALES growth there? (5/25/100 + acceleration)
 * The SalesPanel (the deeper sales metric grid) is rendered beneath it on the
 * tab, so the verdict leads and the detail follows.
 */
import type { BuyVerdict } from './BuyVerdictChip';

function PillarCard({ title, subtitle, passed, pending, lines, cite, tone }: {
  title: string;
  subtitle: string;
  passed: boolean | null;
  pending?: boolean;
  lines: { label: string; value: string; ok?: boolean | null }[];
  cite: string;
  tone: string;
}) {
  const verdict = pending ? 'PENDING' : passed ? 'PASS' : 'FAIL';
  const vTone = pending ? '#94a3b8' : passed ? '#10b981' : '#f87171';
  return (
    <div style={{
      flex: '1 1 280px', border: `1px solid ${tone}`, borderRadius: 8,
      background: 'var(--bg-raised, #181818)', padding: '0.8rem 0.9rem',
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: '0.92rem' }}>{title}</div>
          <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate, #94a3b8)' }}>{subtitle}</div>
        </div>
        <span style={{
          fontSize: '0.68rem', fontWeight: 800, letterSpacing: '0.06em',
          color: vTone, border: `1px solid ${vTone}`, borderRadius: 999, padding: '2px 9px',
          whiteSpace: 'nowrap',
        }}>{verdict}</span>
      </div>
      <div style={{ marginTop: '0.6rem', display: 'flex', flexDirection: 'column', gap: 5 }}>
        {lines.map((l, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, fontSize: '0.8rem' }}>
            <span style={{ color: 'var(--cm-slate, #94a3b8)' }}>{l.label}</span>
            <span style={{
              fontWeight: 600,
              color: l.ok === true ? '#10b981' : l.ok === false ? '#f87171' : 'var(--ink, #eee)',
            }}>{l.value}</span>
          </div>
        ))}
      </div>
      <div style={{ fontSize: '0.6rem', color: 'var(--cm-slate, #94a3b8)', marginTop: '0.6rem', lineHeight: 1.4 }}>
        {cite}
      </div>
    </div>
  );
}

const pct = (v?: number | null) => (v != null ? `${v > 0 ? '+' : ''}${v}%` : '—');

export function BuyVerdictPanel({ verdict }: { verdict?: BuyVerdict | null }) {
  if (!verdict) return null;
  const { minervini: m, bonde: b } = verdict;

  return (
    <div style={{ marginBottom: '1rem' }}>
      {/* Combined headline */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
        border: `1px solid ${verdict.tone}`, borderLeft: `4px solid ${verdict.tone}`,
        borderRadius: 8, padding: '0.7rem 0.95rem', background: 'rgba(255,255,255,0.02)',
      }}>
        <span style={{ fontSize: '1.5rem' }}>{verdict.icon}</span>
        <div>
          <div style={{ fontWeight: 800, fontSize: '1.05rem', color: verdict.tone }}>
            {verdict.label}
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--cm-slate, #94a3b8)' }}>
            Minervini buyable-stock verdict + Pradeep Bonde sales verdict — both must agree for a full green.
          </div>
        </div>
      </div>

      {/* Two pillars */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: '0.7rem' }}>
        <PillarCard
          title="Minervini — buyable stock?"
          subtitle="Trade Like a Stock Market Wizard"
          passed={m.passed}
          tone={m.passed ? '#10b981' : '#f87171'}
          lines={[
            { label: 'Trend-Template qualifier (p.79)', value: m.passed ? 'yes ✓' : 'no ✗', ok: m.passed },
            { label: 'Buyable now — breakout at pivot (pp.198-203)', value: m.buyable_now ? 'yes ✓' : 'watch', ok: m.buyable_now ? true : null },
            { label: 'Stage', value: m.stage != null ? `Stage ${m.stage}` : '—', ok: m.stage === 2 ? true : null },
          ]}
          cite={m.cite}
        />
        <PillarCard
          title="Bonde — sales growth?"
          subtitle="Pradeep Bonde · Stockbee — sales-driven"
          passed={b.passed}
          pending={b.pending}
          tone={b.passed ? '#10b981' : b.pending ? '#475569' : '#f87171'}
          lines={[
            { label: 'Sales growth (YoY)', value: pct(b.growth_yoy_pct), ok: b.growth_yoy_pct != null && b.growth_yoy_pct >= 5 ? true : b.growth_yoy_pct != null ? false : null },
            { label: 'Accelerating', value: b.accelerating === true ? 'yes ⚡' : b.pending ? '—' : 'no', ok: b.accelerating ?? null },
            { label: 'Consecutive growth', value: b.pending ? '—' : `${b.consecutive_growth_q ?? 0}/4 q`, ok: (b.consecutive_growth_q ?? 0) >= 2 ? true : null },
            { label: 'Confidence', value: b.score != null ? `${b.score}/100 · ${b.tier}` : 'n/a (not enriched)', ok: b.passed },
          ]}
          cite={b.cite}
        />
      </div>

      {b.pending && (
        <div style={{ fontSize: '0.7rem', color: 'var(--cm-slate, #94a3b8)', marginTop: '0.5rem' }}>
          Sales confidence is computed for the enriched top candidates. Hit
          <strong> ↻ + catalyst</strong> above to pull this name's revenue history and
          fill in the Bonde pillar.
        </div>
      )}
    </div>
  );
}
