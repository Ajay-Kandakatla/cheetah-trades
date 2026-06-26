/* TomorrowBias — overnight / after-hours → next-session lean.
 *
 *  Per-ticker (top of the options-flow tab) and market-level (top of the
 *  Overnight page). A single lean badge + confluence-gated confidence + a
 *  one-line why + the honest caveat. The detail (the three pillars, the
 *  expected-move band, the active flags) drills in below.
 *
 *  Reads from backend/options/tomorrow_bias.py. The whole point: it TILTS
 *  probability for reacting at the open — it does not predict the overnight. */
import { useState } from 'react';
import { useTomorrowBias, useMarketBias } from '../hooks/useTomorrowBias';
import type { TickerBias, MarketBias } from '../hooks/useTomorrowBias';
import { LEAN_VISUAL, TIER_COLOR, flagLabel, confLabel } from '../lib/tomorrowBias';

const CARD: React.CSSProperties = {
  padding: '0.8rem 1rem',
  background: 'rgba(255,255,255,0.02)',
  border: '1px solid rgba(255,255,255,0.10)',
  borderRadius: 8,
  marginTop: '1rem',
};

function LeanBadge({ lean, tier, confidence }: {
  lean: TickerBias['lean']; tier: TickerBias['confidence_tier']; confidence?: number;
}) {
  const v = LEAN_VISUAL[lean];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '0.45rem',
      padding: '0.3rem 0.8rem', borderRadius: 12, fontWeight: 800,
      fontSize: '0.95rem', letterSpacing: '0.02em',
      background: `${v.color}1a`, border: `1px solid ${v.color}55`, color: v.color,
    }}>
      <span style={{ fontSize: '1rem' }}>{v.arrow}</span>
      {v.label.toUpperCase()}
      <span style={{
        fontSize: '0.72rem', fontWeight: 700, color: TIER_COLOR[tier],
        background: 'rgba(0,0,0,0.25)', padding: '0.1rem 0.4rem', borderRadius: 8,
      }}>
        {confLabel(tier, confidence)}
      </span>
    </span>
  );
}

function Caveat({ text }: { text: string }) {
  return (
    <p style={{ margin: '0.55rem 0 0', fontSize: '0.72rem', lineHeight: 1.45,
      color: 'var(--cm-slate, #9ca3af)', fontStyle: 'italic' }}>
      {text}
    </p>
  );
}

function Flags({ flags }: { flags: string[] }) {
  const show = flags.filter((f) => !f.startsWith('earnings_source:') || flags.includes('event_risk'));
  if (!show.length) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem 0.5rem', marginTop: '0.5rem' }}>
      {show.map((f) => (
        <span key={f} style={{
          fontSize: '0.68rem', color: 'var(--cm-slate)',
          background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: 6, padding: '0.12rem 0.4rem',
        }}>
          {flagLabel(f)}
        </span>
      ))}
    </div>
  );
}

function pillarColor(score?: number | null): string {
  if (score == null) return '#6b7280';
  if (score > 0.1) return '#10b981';
  if (score < -0.1) return '#ef4444';
  return '#9ca3af';
}

/* ============================ per-ticker ============================ */
export function TomorrowBiasBlock({ symbol }: { symbol: string }) {
  const { data, loading, error } = useTomorrowBias(symbol);
  const [open, setOpen] = useState(false);

  if (loading && !data) {
    return <section style={CARD}><Eyebrow /><p className="sepa-empty">Reading the overnight tape…</p></section>;
  }
  if (error || !data) {
    return (
      <section style={CARD}>
        <Eyebrow />
        <p style={{ fontSize: '0.8rem', color: 'var(--cm-slate)', margin: '0.4rem 0 0' }}>
          Tomorrow bias unavailable right now — react at the open.
        </p>
      </section>
    );
  }

  const b = data;
  const band = b.expected_move_band;
  return (
    <section style={CARD}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: '0.5rem' }}>
        <Eyebrow />
        {b.beta != null && (
          <span className="mono" style={{ fontSize: '0.68rem', color: 'var(--cm-slate)' }}>β {b.beta.toFixed(2)}</span>
        )}
      </div>

      <div style={{ margin: '0.55rem 0 0.4rem' }}>
        <LeanBadge lean={b.lean} tier={b.confidence_tier} confidence={b.confidence} />
      </div>

      <p style={{ margin: '0.3rem 0 0', fontSize: '0.85rem', lineHeight: 1.5, color: 'var(--cm-text, #d1d5db)' }}>
        {b.reason}
      </p>

      {band && (
        <p className="mono" style={{ margin: '0.45rem 0 0', fontSize: '0.78rem', color: 'var(--cm-slate)' }}>
          Expected range to next expiry: <strong style={{ color: '#cfcfd4' }}>±{Math.abs(band.high_pct).toFixed(1)}%</strong>
          {' '}(${band.low.toFixed(2)} – ${band.high.toFixed(2)})
        </p>
      )}

      <Flags flags={b.flags} />

      <button type="button" onClick={() => setOpen((o) => !o)} style={{
        marginTop: '0.6rem', background: 'none', border: 'none', cursor: 'pointer',
        color: 'var(--cm-slate)', fontSize: '0.72rem', padding: 0, textDecoration: 'underline',
      }}>
        {open ? 'Hide the three pillars' : 'How is this scored? (3 pillars)'}
      </button>

      {open && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.5rem' }}>
          <Pillar title="Stock move" score={b.pillars.stock?.score}
            detail={b.pillars.stock?.gap_pct != null
              ? `${b.pillars.stock.session ?? 'EH'} ${b.pillars.stock.gap_pct > 0 ? '+' : ''}${b.pillars.stock.gap_pct.toFixed(1)}%`
              : '—'} />
          <Pillar title="Options flow" score={b.pillars.options?.score}
            detail={b.pillars.options?.soir_volume != null
              ? `P/C vol ${b.pillars.options.soir_volume.toFixed(2)}${b.pillars.options.schaeffer_signal ? ` · ${b.pillars.options.schaeffer_signal}` : ''}`
              : '—'} />
          <Pillar title="Market backdrop" score={b.pillars.backdrop?.score}
            detail={b.pillars.backdrop?.spy_gap_pct != null
              ? `SPY ${b.pillars.backdrop.spy_gap_pct > 0 ? '+' : ''}${b.pillars.backdrop.spy_gap_pct.toFixed(2)}%${b.pillars.backdrop.vix != null ? ` · VIX ${b.pillars.backdrop.vix.toFixed(0)}` : ''}`
              : '—'} />
        </div>
      )}

      <Caveat text={b.caveat} />
    </section>
  );
}

function Pillar({ title, score, detail }: { title: string; score?: number | null; detail: string }) {
  return (
    <div style={{
      flex: '1 1 120px', minWidth: 120, padding: '0.45rem 0.6rem',
      background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 6,
    }}>
      <div style={{ fontSize: '0.64rem', color: 'var(--cm-slate)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{title}</div>
      <div className="mono" style={{ fontSize: '0.95rem', fontWeight: 800, color: pillarColor(score) }}>
        {score == null ? '—' : `${score > 0 ? '+' : ''}${score.toFixed(2)}`}
      </div>
      <div style={{ fontSize: '0.68rem', color: 'var(--cm-slate)', marginTop: 1 }}>{detail}</div>
    </div>
  );
}

function Eyebrow() {
  return (
    <div>
      <div className="eyebrow">Tomorrow bias · overnight → next open</div>
      <h3 style={{ margin: '0.1rem 0 0', fontSize: '1rem' }}>Where this leans into tomorrow</h3>
    </div>
  );
}

/* ============================ market-level ============================ */
export function MarketBiasPanel() {
  const { data, loading } = useMarketBias();
  if (loading && !data) return null;
  if (!data) return null;
  const b: MarketBias = data;
  const v = LEAN_VISUAL[b.lean];

  return (
    <section style={{ ...CARD, marginTop: 0, marginBottom: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div>
          <div className="eyebrow">Market tomorrow bias · {b.read_session === 'MORNING_PREMARKET' ? 'premarket read' : 'after-hours read'}</div>
          <h3 style={{ margin: '0.1rem 0 0', fontSize: '1.05rem' }}>Where the tape leans into the next session</h3>
        </div>
        <LeanBadge lean={b.lean} tier={b.confidence_tier} />
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.6rem' }}>
        <MiniStat label="SPY (ES proxy)" value={fmtGap(b.spy_gap_pct)} color={gapColor(b.spy_gap_pct)} />
        <MiniStat label="QQQ (NQ proxy)" value={fmtGap(b.qqq_gap_pct)} color={gapColor(b.qqq_gap_pct)} />
        <MiniStat label="Gap" value={b.gap_state ?? '—'} color={b.gap_state === 'HOLDING' ? '#10b981' : '#f59e0b'} />
        {b.vix != null && <MiniStat label="VIX" value={b.vix.toFixed(1)} />}
        <MiniStat label="Confluence" value={`${b.agreement_count}/3`} />
      </div>

      <p style={{ margin: '0.6rem 0 0', fontSize: '0.86rem', lineHeight: 1.5, color: 'var(--cm-text, #d1d5db)' }}>
        <strong style={{ color: v.color }}>{v.arrow} {v.label}.</strong> {b.what_to_watch}
      </p>

      <Flags flags={b.flags} />
      <Caveat text={b.caveat} />
    </section>
  );
}

function MiniStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ padding: '0.35rem 0.6rem', background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.06)', borderRadius: 6, minWidth: 90 }}>
      <div style={{ fontSize: '0.62rem', color: 'var(--cm-slate)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{label}</div>
      <div className="mono" style={{ fontSize: '0.95rem', fontWeight: 800, color: color ?? '#cfcfd4' }}>{value}</div>
    </div>
  );
}

function fmtGap(g?: number | null): string {
  if (g == null) return '—';
  return `${g > 0 ? '+' : ''}${g.toFixed(2)}%`;
}
function gapColor(g?: number | null): string {
  if (g == null) return '#9ca3af';
  return g > 0.05 ? '#10b981' : g < -0.05 ? '#ef4444' : '#9ca3af';
}
