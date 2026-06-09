/* EarningsQualityPanel — the Minervini Ch.8 "Assessing Earnings Quality"
 * breakdown on the SEPA detail page (fundamentals tab).
 *
 * Renders the verdict from data.base.fundamentals.earnings_quality
 * (backend/sepa/earnings_quality.py): the 0-100 score, the Code 33, margin
 * expansion, EPS/sales acceleration, and the inventory/receivables red flags —
 * each tied to the book page it comes from (pp.140-159).
 */

type EQ = {
  score: number | null;
  code_33?: boolean;
  tier?: string;
  reason?: string;
  components?: {
    eps_growth_yoy_pct?: number | null;
    eps_accelerating?: boolean;
    eps_accelerating_3q?: boolean;
    rev_growth_yoy_pct?: number | null;
    rev_accelerating?: boolean;
    rev_accelerating_3q?: boolean;
    npm_latest_pct?: number | null;
    npm_prior_year_pct?: number | null;
    npm_expanding?: boolean;
    npm_seq_rising_3q?: boolean;
    sales_score?: number | null;
    sales_backed?: boolean;
  };
  red_flags?: {
    low_quality_beat?: boolean;
    inventory_vs_sales?: boolean;
    inv_growth_yoy_pct?: number | null;
    receivables_vs_sales?: boolean | null;
    recv_growth_yoy_pct?: number | null;
    double_trouble?: boolean;
  };
};

const TIER_TONE: Record<string, string> = {
  code33: '#10b981', accelerating: '#34d399', steady: '#eab308',
  red_flag: '#f87171', weak: '#94a3b8', unknown: '#94a3b8',
};

const pct = (v?: number | null) => (v != null ? `${v > 0 ? '+' : ''}${v}%` : '—');

function Flag({ on, label }: { on?: boolean | null; label: string }) {
  const tone = on === true ? '#10b981' : on === false ? '#f87171' : '#64748b';
  const mark = on === true ? '✓' : on === false ? '✗' : '?';
  return (
    <span style={{ color: tone, fontSize: '0.78rem' }}>{mark} {label}</span>
  );
}

export function EarningsQualityPanel({ eq }: { eq?: EQ | null }) {
  if (!eq || eq.score == null) return null;
  const c = eq.components || {};
  const rf = eq.red_flags || {};
  const tone = TIER_TONE[eq.tier || 'unknown'] || '#94a3b8';
  const tierLabel = (eq.tier || 'unknown').replace('_', ' ');
  const hasRedFlag = rf.low_quality_beat || rf.inventory_vs_sales || rf.double_trouble;

  return (
    <div
      style={{
        marginTop: '0.9rem', border: '1px solid var(--rule, #333)', borderRadius: 8,
        background: 'var(--bg-raised, #181818)', padding: '0.85rem 1rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>Earnings Quality</span>
        <span style={{ fontSize: '0.7rem', color: 'var(--cm-slate, #94a3b8)' }}>
          Minervini · Trade Like a Stock Market Wizard, Ch.8 (p.140–159)
        </span>
        <span
          style={{
            marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 8,
          }}
        >
          <span style={{
            fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.06em',
            color: tone, border: `1px solid ${tone}`, borderRadius: 999, padding: '1px 8px', fontWeight: 700,
          }}>
            {eq.code_33 ? '🎯 Code 33' : tierLabel}
          </span>
          <span style={{ fontWeight: 800, fontSize: '1.1rem', color: tone }}>{eq.score}<span style={{ fontSize: '0.7rem', color: 'var(--cm-slate)' }}>/100</span></span>
        </span>
      </div>

      {eq.reason && (
        <div style={{ fontSize: '0.82rem', color: 'var(--ink-muted, #cbd5e1)', marginTop: 6 }}>
          {eq.reason}
        </div>
      )}

      {/* Metric grid */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: 8, marginTop: '0.7rem',
      }}>
        <Metric label="EPS growth (YoY)" value={pct(c.eps_growth_yoy_pct)}
          note={c.eps_accelerating_3q ? 'accelerating 3q ⚡' : c.eps_accelerating ? 'accelerating ⚡' : 'p.140,158'} />
        <Metric label="Sales growth (YoY)" value={pct(c.rev_growth_yoy_pct)}
          note={c.rev_accelerating_3q ? 'accelerating 3q ⚡' : c.rev_accelerating ? 'accelerating ⚡' : 'p.140,158'} />
        <Metric label="Net margin" value={pct(c.npm_latest_pct)}
          note={`vs ${pct(c.npm_prior_year_pct)} yr-ago${c.npm_expanding ? ' · expanding ↑' : ''}`} />
        <Metric label="The Code 33" value={eq.code_33 ? 'YES 🎯' : 'no'}
          note="EPS+sales+margins accel 3q (p.158)" tone={eq.code_33 ? '#10b981' : undefined} />
      </div>

      {/* Flags */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: '0.7rem',
        paddingTop: '0.6rem', borderTop: '1px solid var(--rule, #2a2a2a)' }}>
        <Flag on={c.sales_backed} label="sales-backed earnings (p.141)" />
        <Flag on={!rf.low_quality_beat} label="not a cost-cut/one-time beat (p.143)" />
        <Flag on={rf.inventory_vs_sales ? false : true}
          label={`inventory vs sales${rf.inv_growth_yoy_pct != null ? ` (inv ${pct(rf.inv_growth_yoy_pct)})` : ''} (p.155)`} />
        {rf.receivables_vs_sales != null && (
          <Flag on={!rf.receivables_vs_sales} label={`receivables vs sales (p.157)`} />
        )}
      </div>

      {hasRedFlag && (
        <div style={{
          marginTop: '0.6rem', padding: '0.45rem 0.7rem', borderRadius: 6,
          background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.35)',
          fontSize: '0.78rem', color: '#fca5a5',
        }}>
          ⚠️ {rf.double_trouble
            ? 'Double trouble — inventory AND receivables growing faster than sales (p.157).'
            : rf.low_quality_beat
              ? 'Low-quality beat — EPS jumped on flat sales with no margin expansion (p.143).'
              : 'Inventory growing much faster than sales (p.155).'}
        </div>
      )}

      <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate, #94a3b8)', marginTop: '0.6rem', lineHeight: 1.5 }}>
        Folds into the SEPA score (the <code>fundamentals</code> bucket). Receivables and the
        finished-goods inventory split aren’t fully available from our data providers — see
        <code> docs/sepa/earnings_quality_methodology.md</code>.
      </div>
    </div>
  );
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
