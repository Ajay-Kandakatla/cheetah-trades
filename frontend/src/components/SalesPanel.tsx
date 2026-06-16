/* SalesPanel — the "Sales Confidence" breakdown on the SEPA detail page (Sales
 * tab). Pradeep Bonde / Stockbee, sales-driven: revenue growth and — above all —
 * ACCELERATION drive stock prices, and sales are harder to manipulate than
 * earnings, so they're a cleaner read than EPS.
 *
 * Renders data.base.fundamentals.sales (backend/sepa/sales.py): the 0-100 score,
 * the tier, latest-vs-prior YoY growth (accelerating?), consecutive growth
 * quarters, and whether the growth is sales-LED (top line outpacing the bottom).
 */

type Sales = {
  score: number | null;
  tier: 'explosive' | 'strong' | 'steady' | 'weak' | 'declining' | 'unknown';
  growth_yoy_pct: number | null;
  prior_yoy_pct: number | null;
  accelerating: boolean | null;
  consecutive_growth_q: number;
  sales_led: boolean | null;
  reason?: string;
};

const TIER_TONE: Record<string, string> = {
  explosive: '#10b981', strong: '#34d399', steady: '#eab308',
  weak: '#94a3b8', declining: '#f87171', unknown: '#94a3b8',
};
const TIER_LABEL: Record<string, string> = {
  explosive: '🚀 explosive', strong: 'strong', steady: 'steady',
  weak: 'weak', declining: 'declining', unknown: 'unknown',
};

const pct = (v?: number | null) => (v != null ? `${v > 0 ? '+' : ''}${v}%` : '—');

function Flag({ on, label }: { on?: boolean | null; label: string }) {
  const tone = on === true ? '#10b981' : on === false ? '#f87171' : '#64748b';
  const mark = on === true ? '✓' : on === false ? '✗' : '?';
  return <span style={{ color: tone, fontSize: '0.78rem' }}>{mark} {label}</span>;
}

function Metric({ label, value, note, tone }: { label: string; value: string; note?: string; tone?: string }) {
  return (
    <div style={{
      border: '1px solid var(--rule, #2a2a2a)', borderRadius: 6, padding: '0.45rem 0.6rem',
      background: 'var(--bg, #0f0f0f)',
    }}>
      <div style={{ fontSize: '0.64rem', color: 'var(--cm-slate, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{label}</div>
      <div style={{ fontSize: '1rem', fontWeight: 700, color: tone || 'var(--ink, #eee)' }}>{value}</div>
      {note && <div style={{ fontSize: '0.62rem', color: 'var(--cm-slate, #94a3b8)' }}>{note}</div>}
    </div>
  );
}

export function SalesPanel({ sales }: { sales?: Sales | null }) {
  if (!sales) return null;
  const tone = TIER_TONE[sales.tier || 'unknown'] || '#94a3b8';
  const tierLabel = TIER_LABEL[sales.tier || 'unknown'] || sales.tier;

  // Acceleration is THE Bonde signal — derive a plain read from latest vs prior.
  const g = sales.growth_yoy_pct, p = sales.prior_yoy_pct;
  const accelText = sales.accelerating === true
    ? 'accelerating ⚡'
    : g != null && p != null ? (g < p ? 'decelerating' : 'steady') : '—';
  const accelTone = sales.accelerating === true ? '#10b981'
    : g != null && p != null && g < p ? '#f87171' : undefined;

  return (
    <div style={{
      marginTop: '0.9rem', border: '1px solid var(--rule, #333)', borderRadius: 8,
      background: 'var(--bg-raised, #181818)', padding: '0.85rem 1rem',
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>Sales Confidence</span>
        <span style={{ fontSize: '0.7rem', color: 'var(--cm-slate, #94a3b8)' }}>
          Pradeep Bonde · Stockbee — sales-driven (sales lead earnings; harder to fake)
        </span>
        <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <span style={{
            fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.06em',
            color: tone, border: `1px solid ${tone}`, borderRadius: 999, padding: '1px 8px', fontWeight: 700,
          }}>
            {tierLabel}
          </span>
          <span style={{ fontWeight: 800, fontSize: '1.1rem', color: tone }}>
            {sales.score != null ? sales.score : '—'}
            <span style={{ fontSize: '0.7rem', color: 'var(--cm-slate)' }}>/100</span>
          </span>
        </span>
      </div>

      {sales.score == null && (
        <div style={{ fontSize: '0.82rem', color: 'var(--ink-muted, #cbd5e1)', marginTop: 6 }}>
          {sales.reason || 'Not enough reported revenue history yet (need ≥5 quarters).'}
        </div>
      )}

      {/* Metric grid — acceleration leads (Bonde's core thesis). */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: 8, marginTop: '0.7rem',
      }}>
        <Metric label="Acceleration" value={accelText} tone={accelTone}
          note="latest vs prior-quarter YoY — the signal that moves stocks" />
        <Metric label="Sales growth (YoY)" value={pct(g)}
          note={`latest quarter · prior ${pct(p)}`} />
        <Metric label="Consecutive growth" value={`${sales.consecutive_growth_q}/4 q`}
          note="quarters of positive YoY in a row" />
        <Metric label="Sales-led" value={sales.sales_led === true ? 'yes ✓' : sales.sales_led === false ? 'no' : '—'}
          note="revenue outpacing EPS = organic, not cost-cuts"
          tone={sales.sales_led === true ? '#10b981' : undefined} />
      </div>

      {/* Flags */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: '0.7rem',
        paddingTop: '0.6rem', borderTop: '1px solid var(--rule, #2a2a2a)' }}>
        <Flag on={sales.accelerating} label="sales accelerating" />
        <Flag on={sales.sales_led} label="sales-led growth" />
        <Flag on={sales.consecutive_growth_q >= 3 ? true : sales.consecutive_growth_q === 0 ? false : null}
          label={`${sales.consecutive_growth_q} consecutive growth quarters`} />
      </div>

      <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate, #94a3b8)', marginTop: '0.6rem', lineHeight: 1.5 }}>
        Bonde thresholds: ≥5% floor, 25% preferred, 100%+ "explosive". Acceleration and
        consistency add to the score. Display-only on this tab — see
        <code> docs/sepa/sales_confidence_methodology.md</code>.
      </div>
    </div>
  );
}
