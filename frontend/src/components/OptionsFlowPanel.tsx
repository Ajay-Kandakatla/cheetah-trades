/* OptionsFlowPanel — per-ticker options-flow read for the SEPA detail page.
 *
 *  Shows what the options crowd is doing on a single ticker:
 *
 *    ╔═══════════════════════════════════════════════════════════════╗
 *    ║ Options flow · SOIR              Last scan: 2026-05-22 17:30   ║
 *    ║ ┌─────────────────────────────────────────────────────────────┐║
 *    ║ │ Signal: BULLISH        crowd contrarianly in puts            │║
 *    ║ └─────────────────────────────────────────────────────────────┘║
 *    ║ Put OI: 12.3k    Call OI: 4.1k    P/C: 3.0  (87th pct)         ║
 *    ║ Put vol: 4.2k   Call vol: 2.1k                                 ║
 *    ║ ATM IV: 38%  ·  Expected move ±5.2%  ·  Straddle $3.45         ║
 *    ║                                                                  ║
 *    ║ History (last 30d trajectory) — sparkline of P/C ratio           ║
 *    ║                                                                  ║
 *    ║ Why this signal: Schaeffer SOIR percentile in top 15% of last    ║
 *    ║ 90 days, trend up, fundamentals score 70+. The options crowd is  ║
 *    ║ heavily in puts which contrarianly = bullish — when wrong-footed ║
 *    ║ puts unwind, that's fuel for upside.                              ║
 *    ╚═══════════════════════════════════════════════════════════════╝
 *
 *  Data source: backend/options/soir.py — Schaeffer's Open Interest Ratio
 *  (SOIR) cached nightly + on-demand refresh. Reads from
 *  /options/soir/{symbol} (this hook) — no fresh chain fetch on render.
 *
 *  When SOIR has no data yet for the ticker (e.g. NOK / RYOJ on first
 *  visit), shows a "request scan" CTA that fires POST /options/soir/refresh
 *  for this single symbol. Polls every 8s for up to 2 minutes for the
 *  result to land.
 */
import { useState } from 'react';
import {
  useOptionsPulseForSymbol,
  useSoirSymbolHistory,
  scanOneSymbolOptions,
  type SoirRow,
} from '../hooks/useOptionsPulse';

/** Compact pill — same visual vocabulary as the SignalChips above so
 *  the user reads them as one connected concept. */
const PILL: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  padding: '0.2rem 0.55rem',
  borderRadius: 12,
  fontSize: '0.72rem',
  fontWeight: 700,
  letterSpacing: '0.03em',
  border: '1px solid',
};

const SIGNAL_STYLE: Record<string, { bg: string; border: string; color: string; label: string }> = {
  BULLISH: { bg: 'rgba(16,185,129,0.10)', border: 'rgba(16,185,129,0.35)', color: '#10b981',
             label: 'BULLISH · crowd in puts → unwind = upside' },
  BEARISH: { bg: 'rgba(239,68,68,0.10)',  border: 'rgba(239,68,68,0.35)',  color: '#ef4444',
             label: 'BEARISH · crowd in calls → unwind = downside' },
  WATCH:   { bg: 'rgba(245,158,11,0.10)', border: 'rgba(245,158,11,0.35)', color: '#f59e0b',
             label: 'WATCH · sentiment skewed but trend disagrees' },
  NEUTRAL: { bg: 'rgba(255,255,255,0.05)', border: 'rgba(255,255,255,0.15)', color: '#cfcfd4',
             label: 'NEUTRAL · no contrarian edge' },
};

/* Compact stat tile — used for the OI / vol / IV / move blocks. */
function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div
      style={{
        padding: '0.4rem 0.6rem',
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.06)',
        borderRadius: 6,
        minWidth: 100,
      }}
      title={hint}
    >
      <div style={{ fontSize: '0.65rem', color: 'var(--cm-slate, #9ca3af)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </div>
      <div className="mono" style={{ fontSize: '0.95rem', fontWeight: 700, marginTop: 2 }}>
        {value}
      </div>
    </div>
  );
}

/** Sparkline-style mini chart of the put/call OI ratio trajectory.
 *  Lightweight inline SVG — keeps the bundle small. Min/max scaling so
 *  the line is always visible even when the ratio is tightly clustered. */
function SoirSparkline({ history }: { history: SoirRow[] }) {
  if (history.length < 2) return null;

  // Build a series of P/C ratios over time (oldest first).
  const series = history
    .filter((r) => r.soir != null)
    .map((r) => r.soir!);
  if (series.length < 2) return null;

  const W = 220;
  const H = 36;
  const min = Math.min(...series);
  const max = Math.max(...series);
  const range = Math.max(max - min, 0.01);
  const points = series
    .map((v, i) => {
      const x = (i / (series.length - 1)) * W;
      const y = H - ((v - min) / range) * H;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  // Trend direction colors the line — rising P/C = green (more contrarian
  // bullish setup), falling = neutral gray.
  const direction = series[series.length - 1] - series[0];
  const stroke = direction > 0.1 ? '#10b981' : direction < -0.1 ? '#ef4444' : '#9ca3af';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <svg width={W} height={H} style={{ overflow: 'visible' }}>
        <polyline
          points={points}
          fill="none"
          stroke={stroke}
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="mono" style={{ fontSize: '0.7rem', color: 'var(--cm-slate)' }}>
        {series.length}-pt P/C history
      </span>
    </div>
  );
}

export function OptionsFlowPanel({ symbol }: { symbol: string }) {
  const { data, loading } = useOptionsPulseForSymbol(symbol);
  const { snapshots } = useSoirSymbolHistory(symbol, 90);

  // On-demand scan state. With Massive Options Advanced (2026-05-24+)
  // a single-symbol chain pull is ~200ms — we can block on the request
  // and get the SOIR snapshot back synchronously. Previously this was a
  // fire-and-poll loop because yfinance took 15-60s per ticker.
  const [scanning, setScanning] = useState(false);
  const [scanMsg, setScanMsg] = useState<string | null>(null);
  const [overrideData, setOverrideData] = useState<SoirRow | null>(null);

  const row = overrideData ?? data;

  if (loading && !row) {
    return (
      <section style={containerStyle}>
        <Header symbol={symbol} />
        <p className="sepa-empty">Loading options flow…</p>
      </section>
    );
  }

  // No SOIR data — offer to scan on-demand. Gate on `row` only: an on-demand
  // scan sets overrideData (→ row truthy) but does NOT flip `found` (that's from
  // the initial GET), so gating on `!found` here kept showing the empty CTA even
  // after a successful scan returned a full snapshot. (OGN bug 2026-06-03.)
  if (!row) {
    return (
      <section style={containerStyle}>
        <Header symbol={symbol} />
        <div style={{ padding: '0.6rem 0', color: 'var(--cm-slate)' }}>
          <p style={{ margin: '0 0 0.6rem' }}>
            No options-flow snapshot yet for <strong>{symbol}</strong>. The
            nightly scan only covers SEPA-universe names; ad-hoc tickers need
            a one-shot refresh.
          </p>
          <button
            type="button"
            className="sepa-btn sepa-btn--ghost"
            disabled={scanning}
            onClick={async () => {
              setScanning(true);
              setScanMsg(null);
              try {
                const result = await scanOneSymbolOptions(symbol);
                if (result.found) {
                  setOverrideData(result);
                  setScanMsg(null);
                } else {
                  setScanMsg(result.message ?? `No chain found for ${symbol}.`);
                }
              } catch (e) {
                setScanMsg(`Scan failed: ${e}`);
              } finally {
                setScanning(false);
              }
            }}
          >
            {scanning ? '↻ Scanning options chain…' : `Scan options flow for ${symbol}`}
          </button>
          {scanMsg && (
            <p className="mono" style={{ marginTop: '0.5rem', fontSize: '0.78rem' }}>
              {scanMsg}
            </p>
          )}
        </div>
      </section>
    );
  }

  // Got data — render the panel.
  const sigKey = row.signal ?? 'NEUTRAL';
  const sig = SIGNAL_STYLE[sigKey] ?? SIGNAL_STYLE.NEUTRAL;
  const putOi = row.put_oi ?? 0;
  const callOi = row.call_oi ?? 0;
  const putVol = row.put_vol ?? 0;
  const callVol = row.call_vol ?? 0;
  const soir = row.soir ?? null;
  const pct = row.soir_percentile;
  // atm_iv arrives ALREADY in percent (soir.py:264 / soir.py:391 both do
  // `round(atm_iv * 100, 2)` before returning, so we just round-display here).
  // The earlier `* 100` here was multiplying again and producing values like
  // "1937%" for AAPL — fixed 2026-05-24.
  const ivPct = row.atm_iv != null ? row.atm_iv.toFixed(0) : null;
  const movePct = row.expected_move_pct != null ? row.expected_move_pct.toFixed(1) : null;
  const straddle = row.atm_straddle_premium != null ? row.atm_straddle_premium.toFixed(2) : null;

  const scanned = row.scanned_at
    ? new Date(row.scanned_at).toLocaleString(undefined, {
        month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
      })
    : null;

  return (
    <section style={containerStyle}>
      <Header symbol={symbol} scannedAt={scanned} source={row._source} />

      {/* Signal pill — big and obvious. */}
      <div style={{ margin: '0.6rem 0' }}>
        <span
          style={{
            ...PILL,
            background: sig.bg, borderColor: sig.border, color: sig.color,
            padding: '0.3rem 0.8rem', fontSize: '0.85rem',
          }}
          title={row.reason ?? sig.label}
        >
          {sig.label}
        </span>
        {pct != null && (
          <span className="mono" style={{ marginLeft: '0.6rem', fontSize: '0.78rem', color: 'var(--cm-slate)' }}>
            SOIR {pct.toFixed(0)}th pct
            {row.percentile_source === 'cross_section' ? ' (cross-section)' : ' (90d)'}
          </span>
        )}
      </div>

      {/* OI / Vol / IV stat tiles. Tooltips explain the framework. */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.6rem' }}>
        <StatTile
          label="Put OI"
          value={fmt(putOi)}
          hint="Open interest on all put strikes — the bigger the number relative to calls, the more crowded the bearish side. Schaeffer's contrarian read: crowded puts = setup for upside when they unwind."
        />
        <StatTile
          label="Call OI"
          value={fmt(callOi)}
          hint="Open interest on all call strikes. Crowded calls = setup for downside when wrong-footed longs unwind."
        />
        <StatTile
          label="P/C OI"
          value={soir != null ? soir.toFixed(2) : '—'}
          hint="Schaeffer's Open Interest Ratio = Put OI / Call OI. Higher = more contrarianly bullish. Above 1.0 means more puts than calls open."
        />
        <StatTile
          label="Put vol"
          value={fmt(putVol)}
          hint="Today's put-side volume. Compare with OI to spot fresh positioning vs leftover OI."
        />
        <StatTile
          label="Call vol"
          value={fmt(callVol)}
          hint="Today's call-side volume."
        />
        {ivPct && (
          <StatTile
            label="ATM IV"
            value={`${ivPct}%`}
            hint="Implied volatility at the at-the-money strike — the market's bet on how much this stock will move. Higher = expecting bigger moves (earnings, catalysts, news risk)."
          />
        )}
        {movePct && (
          <StatTile
            label="Expected ±"
            value={`±${movePct}%`}
            hint="Expected move to next monthly expiry based on ATM straddle premium. The options market's range estimate."
          />
        )}
        {straddle && (
          <StatTile
            label="Straddle"
            value={`$${straddle}`}
            hint="ATM straddle premium (call + put at the same strike). The dollar cost of betting on a move in either direction."
          />
        )}
      </div>

      {/* 30-day P/C trajectory. */}
      {snapshots && snapshots.length > 1 && (
        <div style={{ marginBottom: '0.6rem' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--cm-slate)', marginBottom: 4 }}>
            P/C ratio · last {snapshots.length} snapshots
          </div>
          <SoirSparkline history={snapshots} />
        </div>
      )}

      {/* Why this signal — Schaeffer framework, pillar by pillar. */}
      {row.reason && (
        <div
          style={{
            padding: '0.6rem 0.8rem',
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 6,
            fontSize: '0.82rem',
            lineHeight: 1.5,
            color: 'var(--cm-text, #d1d5db)',
          }}
        >
          <div style={{
            fontSize: '0.65rem', color: 'var(--cm-slate)',
            textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4,
          }}>
            Why this signal
          </div>
          {row.reason}
        </div>
      )}

      {/* Pillars block — trend / sentiment / fundamental. */}
      {row.pillars && (
        <div style={{
          display: 'flex', flexWrap: 'wrap', gap: '0.6rem',
          marginTop: '0.5rem', fontSize: '0.78rem',
        }}>
          {row.pillars.trend && (
            <span className="mono" title="Trend pillar — SEPA-derived direction of the underlying. Schaeffer's contrarian read NEEDS the trend to support the unwind direction.">
              Trend: <strong style={{ color: pillarColor(row.pillars.trend) }}>{row.pillars.trend}</strong>
            </span>
          )}
          {row.pillars.sentiment_pct != null && (
            <span className="mono" title="Sentiment percentile — how extreme the put/call OI skew is vs the last 90 days. >85th = strong contrarian setup.">
              Sentiment: <strong>{row.pillars.sentiment_pct.toFixed(0)}th pct</strong>
            </span>
          )}
          {row.pillars.fundamental_score != null && (
            <span className="mono" title="Fundamental score — SEPA composite (trend + RS + setup + fundamentals). Schaeffer's signal only fires when fundamentals support the contrarian read.">
              Fundamental: <strong>{row.pillars.fundamental_score.toFixed(0)}/100</strong>
            </span>
          )}
        </div>
      )}
    </section>
  );
}

const containerStyle: React.CSSProperties = {
  padding: '0.8rem 1rem',
  background: 'rgba(255,255,255,0.02)',
  border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: 8,
  marginTop: '1rem',
};

function Header({ symbol, scannedAt, source }: { symbol: string; scannedAt?: string | null; source?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap' }}>
      <div>
        <div className="eyebrow">Options flow · SOIR (Schaeffer)</div>
        <h3 style={{ margin: '0.15rem 0 0', fontSize: '1rem' }}>
          {symbol} — what the options crowd is doing
        </h3>
      </div>
      {(scannedAt || source) && (
        <span className="mono" style={{ fontSize: '0.7rem', color: 'var(--cm-slate)' }}>
          {scannedAt && `Last scan: ${scannedAt}`}
          {scannedAt && source && ' · '}
          {source && `via ${source}`}
        </span>
      )}
    </div>
  );
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toLocaleString();
}

function pillarColor(trend: string): string {
  const t = trend.toLowerCase();
  if (t.includes('up') || t.includes('bull')) return '#10b981';
  if (t.includes('down') || t.includes('bear')) return '#ef4444';
  return '#cfcfd4';
}
