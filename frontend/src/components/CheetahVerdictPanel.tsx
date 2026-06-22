/* CheetahVerdictPanel — the Cheetah Verdict: composite BUY / WATCH / AVOID that
 * leads the SEPA detail Analysis tab (Ajay 2026-06-16: "make the logic follow
 * Minervini and Pradeep Bonde's verdict of buy and sell"; branded "Cheetah").
 *
 * Combines two frameworks on data the scan payload already carries:
 *   • Minervini SEPA — Trend Template (8 price/MA/RS gates) + pivot breakout.
 *   • Bonde / Stockbee — Episodic Pivot, 4% breakout, momentum burst, group
 *     leadership, AND the anti-thesis SELL signals.
 * Logic lives in src/lib/cheetahVerdict.ts (pure, unit-tested). This is render-only.
 */
import { computeCheetahVerdict, type FrameworkResult, type VerdictCheck } from '../lib/cheetahVerdict';

function CheckRow({ c }: { c: VerdictCheck }) {
  const tone = c.ok === true ? '#10b981' : c.ok === false ? '#f87171' : '#64748b';
  const mark = c.ok === true ? '✓' : c.ok === false ? '✗' : '—';
  return (
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: '0.78rem', padding: '2px 0' }}>
      <span style={{ color: tone, fontWeight: 700, width: 12, flexShrink: 0 }}>{mark}</span>
      <span style={{ color: 'var(--ink, #e5e5e5)' }}>{c.label}</span>
      {c.detail && (
        <span style={{ marginLeft: 'auto', color: 'var(--cm-slate, #94a3b8)', fontSize: '0.72rem', whiteSpace: 'nowrap' }}>
          {c.detail}
        </span>
      )}
    </div>
  );
}

function Pillar({ fw, cite }: { fw: FrameworkResult; cite: string }) {
  const vTone = fw.verdict === 'buy' ? '#10b981' : fw.verdict === 'watch' ? '#eab308' : '#f87171';
  return (
    <div
      style={{
        flex: '1 1 300px',
        border: `1px solid ${vTone}`,
        borderRadius: 8,
        background: 'var(--bg-raised, #181818)',
        padding: '0.8rem 0.9rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: '0.92rem' }}>{fw.name}</div>
          <div style={{ fontSize: '0.64rem', color: 'var(--cm-slate, #94a3b8)' }}>{cite}</div>
        </div>
        <span
          style={{
            fontSize: '0.66rem',
            fontWeight: 800,
            letterSpacing: '0.06em',
            color: vTone,
            border: `1px solid ${vTone}`,
            borderRadius: 999,
            padding: '2px 9px',
            textTransform: 'uppercase',
            whiteSpace: 'nowrap',
          }}
        >
          {/* Display label only — relabel buy→enter (Ajay 2026-06-21). */}
          {fw.verdict === 'buy' ? 'enter' : fw.verdict}
        </span>
      </div>
      <div style={{ marginTop: '0.6rem', borderTop: '1px solid var(--rule, #2a2a2a)', paddingTop: '0.5rem' }}>
        {fw.checks.map((c, i) => (
          <CheckRow key={i} c={c} />
        ))}
      </div>
    </div>
  );
}

export function CheetahVerdictPanel({
  row,
  catalystSurprisePct,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  row: any;
  catalystSurprisePct?: number | null;
}) {
  const v = computeCheetahVerdict({ row, catalystSurprisePct });

  return (
    <div style={{ marginBottom: '1rem' }}>
      {/* Headline verdict */}
      <div
        style={{
          border: `2px solid ${v.tone}`,
          borderRadius: 10,
          background: 'var(--bg-raised, #181818)',
          padding: '0.9rem 1rem',
          marginBottom: '0.8rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 800, fontSize: '0.92rem', letterSpacing: '0.02em' }}>
            🐆 Cheetah Verdict:
          </span>
          <span
            style={{
              fontSize: '1.1rem',
              fontWeight: 900,
              letterSpacing: '0.04em',
              color: v.tone,
              border: `2px solid ${v.tone}`,
              borderRadius: 8,
              padding: '3px 14px',
            }}
          >
            {v.label}
          </span>
          <span style={{ fontSize: '0.7rem', color: 'var(--cm-slate, #94a3b8)' }}>
            Minervini SEPA + Pradeep Bonde (Stockbee) — entry &amp; sell
          </span>
        </div>
        <div style={{ fontSize: '0.85rem', color: 'var(--ink-muted, #cbd5e1)', marginTop: 8 }}>{v.why}</div>
      </div>

      {/* Two framework pillars with their pass/fail checks */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <Pillar fw={v.minervini} cite="Trend Template + pivot breakout (Trade Like a Stock Market Wizard)" />
        <Pillar fw={v.bonde} cite="Episodic Pivot · 4% breakout · momentum · sell signals (Stockbee)" />
      </div>

      <div style={{ fontSize: '0.64rem', color: 'var(--cm-slate, #94a3b8)', marginTop: '0.6rem', lineHeight: 1.5 }}>
        A full <strong style={{ color: '#10b981' }}>ENTER</strong> needs both frameworks to confirm; any anti-thesis sell
        signal (or broken trend) forces <strong style={{ color: '#f87171' }}>AVOID</strong>. See{' '}
        <code>docs/sepa/trade_verdict_methodology.md</code>.
      </div>
    </div>
  );
}
