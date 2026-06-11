/* Pankaj's Market Analysis — a trusted outside analyst's curated picks, shown
   WITH the app's own SEPA indicators + a live price + where price sits vs each
   of his entry/stop/target levels. Owner-scoped alerts fire (via the alerts
   cron) when price reaches one of his levels.

   Ajay 2026-06-09: "a dude I trust — I want indicators against his stock picks …
   any time I update this page account for his indicators + add alerts."

   These are PANKAJ's discretionary calls, surfaced for context. Not advice. */
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { usePankaj, type PankajPick, type PankajSetup, type SetupStatus } from '../hooks/usePankaj';

const fmt = (n: number | null | undefined, d = 2): string =>
  n == null || Number.isNaN(n) ? '—' : Number(n).toFixed(d);

function pct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '';
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`;
}

// ── App-rating → colour (reuses the engine's own rating word) ──────────────
function ratingColor(rating?: string | null): string {
  switch ((rating || '').toUpperCase()) {
    case 'STRONG_BUY':
    case 'BUY': return 'var(--positive)';
    case 'AVOID':
    case 'SELL':
    case 'REDUCE': return 'var(--negative)';
    default: return 'var(--ink-muted)';
  }
}

// ── Setup live-status → badge style ────────────────────────────────────────
const STATUS_META: Record<SetupStatus['state'], { label: string; color: string; bg: string }> = {
  triggered:   { label: 'TRIGGERED',  color: 'var(--positive)', bg: 'color-mix(in srgb, var(--positive) 14%, transparent)' },
  in_zone:     { label: 'IN ZONE',    color: 'var(--positive)', bg: 'color-mix(in srgb, var(--positive) 14%, transparent)' },
  approaching: { label: 'APPROACHING', color: 'var(--warn)',    bg: 'color-mix(in srgb, var(--warn) 16%, transparent)' },
  below:       { label: 'BELOW',      color: 'var(--ink-muted)', bg: 'var(--bg-sunken)' },
  above_zone:  { label: 'ABOVE ZONE', color: 'var(--ink-muted)', bg: 'var(--bg-sunken)' },
  below_zone:  { label: 'NEAR STOP',  color: 'var(--negative)', bg: 'color-mix(in srgb, var(--negative) 12%, transparent)' },
  unknown:     { label: 'NO PRICE',   color: 'var(--ink-faint)', bg: 'var(--bg-sunken)' },
};

function StatusBadge({ status }: { status: SetupStatus }) {
  const m = STATUS_META[status.state] ?? STATUS_META.unknown;
  return (
    <span
      className="mono"
      title={status.detail}
      style={{
        color: m.color, background: m.bg, border: `1px solid ${m.color}`,
        borderRadius: 'var(--r-2)', padding: '2px 8px', fontSize: '0.72rem',
        fontWeight: 600, letterSpacing: '0.04em', whiteSpace: 'nowrap',
      }}
    >
      {m.label}
    </span>
  );
}

// ── The app's indicators for the pick (the "indicators against his picks") ──
function IndicatorStrip({ pick }: { pick: PankajPick }) {
  const i = pick.indicators;
  if (!i?.in_scan) {
    return (
      <div className="mono" style={{ fontSize: '0.8rem', color: 'var(--ink-faint)' }}>
        Not in the SEPA universe — price-only. (Off the Russell-3000 scan; levels &amp; alerts still track live.)
      </div>
    );
  }
  const cell = (label: string, value: ReactNode, color?: string) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 56 }}>
      <span className="eyebrow" style={{ fontSize: '0.62rem' }}>{label}</span>
      <span className="mono" style={{ fontSize: '0.92rem', fontWeight: 600, color: color || 'var(--ink)' }}>{value}</span>
    </div>
  );
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px 20px', alignItems: 'flex-end' }}>
      {cell('App score', fmt(i.score, 1))}
      {cell('Rating', (i.rating || '—').replace('_', ' '), ratingColor(i.rating))}
      {cell('RS rank', i.rs_rank ?? '—')}
      {cell('Stage', i.stage || '—')}
      {cell('Trend', i.trend_passed != null ? `${i.trend_passed}/8${i.trend_pass_all ? ' ✓' : ''}` : '—',
        i.trend_pass_all ? 'var(--positive)' : 'var(--ink-muted)')}
      {cell('Buyable', i.is_buyable ? 'YES' : 'no', i.is_buyable ? 'var(--positive)' : 'var(--ink-muted)')}
      {i.pivot != null && cell('App pivot', fmt(i.pivot))}
    </div>
  );
}

function targetsText(s: PankajSetup): string {
  if (!s.targets?.length) return '';
  return s.targets.map((t) => `${fmt(t.lo, t.lo % 1 ? 2 : 0)}-${fmt(t.hi, t.hi % 1 ? 2 : 0)}`).join(' → ');
}

function SetupRow({ s }: { s: PankajSetup }) {
  const isBreakout = s.kind === 'breakout';
  return (
    <div style={{
      border: '1px solid var(--border, var(--bg-sunken))', borderRadius: 'var(--r-2)',
      padding: '10px 12px', background: 'var(--bg-raised)', display: 'grid', gap: 6,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 600 }}>
          {isBreakout ? '▲ ' : '▼ '}{s.label}{s.extreme ? <span className="mono" style={{ color: 'var(--warn)', fontSize: '0.7rem', marginLeft: 6 }}>EXTREME</span> : null}
        </span>
        <StatusBadge status={s.status} />
      </div>
      <div className="mono" style={{ fontSize: '0.8rem', color: 'var(--ink-muted)', display: 'flex', flexWrap: 'wrap', gap: '4px 16px' }}>
        {isBreakout
          ? <span>Trigger <strong style={{ color: 'var(--ink)' }}>{fmt(s.trigger)}</strong>{s.confirm ? ` · ${s.confirm.conservative} = cons, ${s.confirm.aggressive} = aggr` : ''}</span>
          : <span>Zone <strong style={{ color: 'var(--ink)' }}>{fmt(s.zone?.lo)}–{fmt(s.zone?.hi)}</strong></span>}
        {targetsText(s) && <span>🎯 {targetsText(s)}</span>}
        {s.stops && <span>🛑 {fmt(s.stops.aggressive)} aggr / {fmt(s.stops.conservative)} cons</span>}
      </div>
      {s.status.detail && <div style={{ fontSize: '0.78rem', color: 'var(--ink-subtle)' }}>{s.status.detail}</div>}
      {s.note && <div style={{ fontSize: '0.8rem', color: 'var(--ink-subtle)', fontStyle: 'italic' }}>{s.note}</div>}
    </div>
  );
}

function PickCard({ pick }: { pick: PankajPick }) {
  const i = pick.indicators;
  const chg = i?.day_change_pct;
  const chgColor = chg == null ? 'var(--ink-muted)' : chg >= 0 ? 'var(--positive)' : 'var(--negative)';
  // ALWAYS a link (Ajay 2026-06-11: "VG does not go to the ticker details
  // page, it's stuck"). The old in_scan gate made off-universe picks dead
  // text — but /sepa/{symbol} handles any ticker and offers the on-demand
  // re-scan, so there's no reason to strand them here.
  const symEl = (
    <Link to={`/sepa/${pick.symbol}`}
          title={i?.in_scan ? pick.name : `${pick.name} — not in the latest scan; the detail page can re-scan it on demand`}
          style={{ color: 'var(--ink)', textDecoration: 'none' }}>
      {pick.symbol}
    </Link>
  );

  return (
    <section className="card" style={{ display: 'grid', gap: 14, padding: '16px 18px' }}>
      {/* Header: symbol · name · live price */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.3rem', letterSpacing: '0.01em' }}>
            {symEl} <span style={{ color: 'var(--ink-muted)', fontWeight: 400, fontSize: '0.95rem' }}>{pick.name}</span>
          </h2>
          <div className="mono" style={{ fontSize: '0.74rem', color: 'var(--ink-faint)', marginTop: 2 }}>
            {pick.horizon ? `${pick.horizon} · ` : ''}updated {pick.updated} · {pick.analyst}'s call
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="mono" style={{ fontSize: '1.25rem', fontWeight: 600 }}>{pick.price != null ? `$${fmt(pick.price)}` : '—'}</div>
          {chg != null && <div className="mono" style={{ fontSize: '0.8rem', color: chgColor }}>{pct(chg)}</div>}
        </div>
      </div>

      {/* App indicators */}
      <div style={{ borderTop: '1px solid var(--bg-sunken)', paddingTop: 12 }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>App indicators</div>
        <IndicatorStrip pick={pick} />
      </div>

      {/* Pankaj's thesis + setups */}
      <div style={{ borderTop: '1px solid var(--bg-sunken)', paddingTop: 12, display: 'grid', gap: 10 }}>
        <div className="eyebrow">{pick.analyst}'s setups</div>
        {pick.thesis && <p style={{ margin: 0, fontSize: '0.88rem', color: 'var(--ink-subtle)' }}>{pick.thesis}</p>}
        {pick.setups.map((s) => <SetupRow key={s.id} s={s} />)}
      </div>
    </section>
  );
}

export function PankajAnalysisPage() {
  const { data, loading, err } = usePankaj();

  return (
    <div className="sepa-page">
      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">№ — Trusted analyst</div>
          <h1 className="display sepa-page__h1">Pankaj's Market Analysis</h1>
          <p className="lede">
            Picks from <strong>Pankaj</strong> — a trader you trust — surfaced next to the app's
            own SEPA indicators and a live read on where price sits versus his entry, stop and
            target levels. You'll get a Pounce alert when price reaches one of his levels.
          </p>
        </div>
      </div>

      {loading && <div className="rsx-loading" style={{ padding: 24, color: 'var(--ink-muted)' }}>Loading Pankaj's picks…</div>}
      {err && <div className="sepa-err">Couldn't load Pankaj's analysis: {err}</div>}

      {data?.ok && (
        <>
          <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))' }}>
            {data.picks.map((p) => <PickCard key={p.symbol} pick={p} />)}
          </div>
          <p className="mono" style={{ marginTop: 20, fontSize: '0.74rem', color: 'var(--ink-faint)', maxWidth: 720 }}>
            {data.disclaimer} Levels are {data.analyst}'s, transcribed verbatim; the indicators and
            live status are the app's. This is a data read for context — not a recommendation.
          </p>
        </>
      )}
    </div>
  );
}
