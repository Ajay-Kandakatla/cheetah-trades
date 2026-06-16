import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  useOptionsPulse, refreshOptionsPulse, useSoirScanByDate,
  type SoirRow, type SoirSignal,
} from '../hooks/useOptionsPulse';
import { InfoButton } from '../components/InfoButton';
import { OptionsDateScrubber } from '../components/OptionsDateScrubber';
import { TradePlanInline } from '../components/TradePlanInline';

/* ==========================================================================
   /options — Schaeffer's Open Interest Ratio (SOIR) + Expectational Analysis.

   Three-pillar contrarian framework, published by Bernie Schaeffer
   (Schaeffer's Investment Research, 1981+):
     1. TECHNICAL  — stage-2 uptrend / stage-4 downtrend gate
     2. FUNDAMENTAL — defers to SEPA score (re-uses our existing pipeline)
     3. SENTIMENT  — SOIR percentile rank vs trailing 52-weeks (contrarian)

   BULLISH = uptrend + SOIR ≥ 80th percentile (crowd loaded with puts)
   BEARISH = downtrend + SOIR ≤ 20th percentile (crowd loaded with calls)

   Reference: "The Option Advisor" (Schaeffer, 1997).
   Academic backing: Pan & Poteshman 2006, RFS.
   ========================================================================== */

const PageInfo = (
  <>
    <p>
      <strong>Options Pulse</strong> applies <em>Schaeffer's Expectational
      Analysis</em> (Bernie Schaeffer, 1997) — a published, contrarian
      framework that reads the options crowd's positioning as a sentiment
      extreme detector. Same shape as SEPA: only fires when{' '}
      <em>all three pillars</em> line up.
    </p>
    <p><strong>The three pillars:</strong></p>
    <ul>
      <li><strong>Technical</strong> — stage-2 uptrend (price &gt; 50d &gt; 200d)
        OR stage-4 downtrend (price &lt; 50d &lt; 200d).</li>
      <li><strong>Fundamental</strong> — borrows the SEPA composite score so we
        only fire bullish on names that are also fundamentally OK.</li>
      <li><strong>Sentiment</strong> — <strong>SOIR</strong> ranked as a
        percentile against the ticker's own 52-week history. Schaeffer's
        contrarian rule: extremes signal unwinding pressure in the
        opposite direction.</li>
    </ul>

    <p><strong>The formulas (short version):</strong></p>
    <ul className="mono" style={{ fontSize: '0.85rem' }}>
      <li>SOIR = Σ put OI / Σ call OI (across front 3 expirations)</li>
      <li>Percentile = % of past 52w days with SOIR below today's value</li>
      <li>Expected move ≈ ATM straddle premium / spot ≈ 1 SD by expiry</li>
      <li>ATM IV = average IV of ATM call + ATM put, annualized</li>
    </ul>

    <p><strong>How to use:</strong></p>
    <ul>
      <li><strong>Confirmation:</strong> a SEPA candidate that's also BULLISH
        here = two independent frameworks agreeing → size up.</li>
      <li><strong>Disagreement:</strong> SEPA likes it but Options Pulse
        flags BEARISH → smaller position OR wait one more close.</li>
      <li><strong>Sizing:</strong> compare expected-move % to your stop-pivot
        gap. Expected move &lt; stop range = options market doesn't see
        your target → review setup quality.</li>
      <li><strong>Validate historically:</strong> use the date scrubber to
        load past SOIR scans, then check whether BULLISH names actually
        worked over the next 30 days. Build evidence before risking capital.</li>
    </ul>

    <p className="mono" style={{ opacity: 0.7, fontSize: '0.78rem' }}>
      Universe: Russell 1000 ∪ SEPA candidates ∪ watchlist ∪ mega-cap context
      (~1100 names). Cron Mon-Fri 5:30pm ET + Sun 9pm ET, parallel via 10
      threads. yfinance chains take ~3-5 min for the full universe.
    </p>

    <p style={{ fontSize: '0.95rem' }}>
      <strong>📖 Full methodology + every formula derivation:</strong>{' '}
      <Link to="/options/methodology">/options/methodology</Link>
    </p>

    <p style={{ fontSize: '0.85rem', opacity: 0.85 }}>
      <strong>References:</strong> Schaeffer, "The Option Advisor" (Wiley
      1997); Pan & Poteshman, "The Information in Option Volume for Future
      Stock Prices," <em>RFS</em> 2006.
    </p>
  </>
);

const SIGNAL_TONE: Record<SoirSignal, string> = {
  BULLISH: 'op-sig--bull',
  BEARISH: 'op-sig--bear',
  WATCH:   'op-sig--watch',
  NEUTRAL: 'op-sig--neutral',
};

const SIGNAL_LABEL: Record<SoirSignal, string> = {
  BULLISH: 'Bullish',
  BEARISH: 'Bearish',
  WATCH:   'Watch',
  NEUTRAL: 'Neutral',
};

function fmtPct(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return '—';
  return `${v.toFixed(1)}%`;
}

function fmtSoir(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return '—';
  return v.toFixed(2);
}

function fmtNum(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return '—';
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return String(v);
}

export default function OptionsPulsePage() {
  // Filter persists across reloads — same UX as SEPA's filter persistence.
  // Reading from localStorage should always pick up where you left off.
  const FILTER_KEY = 'options_pulse_filter_v1';
  const [filter, setFilter] = useState<'ALL' | SoirSignal>(() => {
    if (typeof window === 'undefined') return 'ALL';
    const v = window.localStorage.getItem(FILTER_KEY);
    if (v === 'ALL' || v === 'BULLISH' || v === 'BEARISH' || v === 'WATCH' || v === 'NEUTRAL') {
      return v;
    }
    return 'ALL';
  });
  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(FILTER_KEY, filter);
  }, [filter]);
  const [refreshing, setRefreshing] = useState(false);

  // Date scrubber: when set, the list comes from the historical snapshot at
  // that date instead of the live scan. Persists in URL hash so links to
  // historical states are shareable (mirrors SEPA's pattern).
  const [historicalDate, setHistoricalDate] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    const m = window.location.hash.match(/date=(\d{4}-\d{2}-\d{2})/);
    return m ? m[1] : null;
  });
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (historicalDate) {
      window.location.hash = `date=${historicalDate}`;
    } else if (window.location.hash.startsWith('#date=')) {
      window.location.hash = '';
    }
  }, [historicalDate]);

  const { data: liveData, loading: liveLoading, refetch } = useOptionsPulse(
    filter === 'ALL' ? undefined : filter,
  );
  const { scan: histScan, loading: histLoading, error: histError } = useSoirScanByDate(historicalDate);
  const navigate = useNavigate();

  // Adapt the historical snapshot shape to the live-scan shape so the rest
  // of the page renders against either source without branching.
  const data = useMemo(() => {
    if (!historicalDate) return liveData;
    if (!histScan) return null;
    let rows = histScan.rows;
    if (filter !== 'ALL') rows = rows.filter((r) => r.signal === filter);
    return {
      as_of: histScan.date,
      rows,
      n: rows.length,
      filter_signal: filter === 'ALL' ? null : filter,
    };
  }, [historicalDate, liveData, histScan, filter]);

  const loading = historicalDate ? histLoading : liveLoading;

  const counts = useMemo(() => {
    const c = { BULLISH: 0, BEARISH: 0, WATCH: 0, NEUTRAL: 0 };
    const source = historicalDate ? (histScan?.rows ?? []) : (liveData?.rows ?? []);
    for (const r of source) if (r.signal) c[r.signal]++;
    return c;
  }, [historicalDate, histScan, liveData]);

  const handleRefresh = async () => {
    if (historicalDate) {
      alert('Switch to Live to run a fresh scan.');
      return;
    }
    if (!confirm('Run SOIR scan now? Takes 5-15 min depending on universe size.')) return;
    setRefreshing(true);
    try {
      await refreshOptionsPulse();
      // Poll every 30s for new results — crude but adequate
      setTimeout(refetch, 30_000);
      alert('Scan started in background. Refresh the page in a few minutes to see updated results.');
    } catch (e) {
      alert(`Refresh failed: ${e}`);
    } finally {
      setRefreshing(false);
    }
  };

  const rows = data?.rows ?? [];

  return (
    <div className="op-page">
      <div className="op-page__title">
        <InfoButton title="Options Pulse — Schaeffer's Expectational Analysis">
          {PageInfo}
        </InfoButton>
        <div>
          <div className="eyebrow">Options crowd</div>
          <h1 className="display op-page__h1">Options Pulse</h1>
          <p className="lede">
            Schaeffer's Open Interest Ratio (SOIR) crossed with stage-2/stage-4
            trend. Contrarian: when the crowd is wrong-footed, that's fuel
            for the trade.
          </p>
          <div className="op-page__links mono">
            <Link to="/options/methodology">📖 Full methodology &amp; formulas</Link>
            <span className="op-page__sep">·</span>
            <span>
              Russell 1000 universe · Schaeffer 1997 framework · cron 5:30pm ET
            </span>
          </div>
        </div>
      </div>

      <OptionsDateScrubber value={historicalDate} onChange={setHistoricalDate} />

      {historicalDate && histError && (
        <div className="op-empty" style={{ marginTop: '0.5rem' }}>
          <p><strong>{histError}</strong></p>
          <p>Pick another date or return to <strong>Live</strong>.</p>
        </div>
      )}

      <div className="op-tabs">
        {([
          { k: 'ALL'     as const, label: `All${rows.length ? ` · ${data?.n ?? rows.length}` : ''}` },
          { k: 'BULLISH' as const, label: `★ Bullish${counts.BULLISH ? ` · ${counts.BULLISH}` : ''}` },
          { k: 'BEARISH' as const, label: `Bearish${counts.BEARISH ? ` · ${counts.BEARISH}` : ''}` },
          { k: 'WATCH'   as const, label: `Watch${counts.WATCH ? ` · ${counts.WATCH}` : ''}` },
          { k: 'NEUTRAL' as const, label: `Neutral${counts.NEUTRAL ? ` · ${counts.NEUTRAL}` : ''}` },
        ]).map(({ k, label }) => (
          <button key={k}
                  className={`sepa-chip ${filter === k ? 'is-active' : ''}`}
                  onClick={() => setFilter(k)}>
            {label}
          </button>
        ))}
        {data?.as_of && (
          <span className="op-tabs__generated mono">
            scan {new Date(data.as_of).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
          </span>
        )}
        <button
          type="button"
          className="op-refresh-btn"
          onClick={handleRefresh}
          disabled={refreshing}
          title="Run a fresh SOIR scan (background, 5-15 min)"
        >
          {refreshing ? 'Refreshing…' : '↻ Refresh now'}
        </button>
      </div>

      {loading ? (
        <div className="op-empty">Loading options pulse…</div>
      ) : rows.length === 0 ? (
        <div className="op-empty">
          <p><strong>{data?.message || 'No SOIR data yet at this filter.'}</strong></p>
          <p>
            The nightly cron (5:30pm ET weekdays) builds the SOIR snapshot.
            Until the first run completes, this page will be empty. Click
            <strong> ↻ Refresh now</strong> to trigger one immediately.
          </p>
          <p className="mono" style={{ opacity: 0.65 }}>
            Note: the first 30 days of data accumulate before time-series
            percentiles activate. Until then we use a cross-section
            percentile (vs today's universe) so the tool is useful from
            day one — just less stable than the eventual rolling 52-week rank.
          </p>
        </div>
      ) : (
        <div className="op-grid">
          {rows.map((r) => (
            <SoirCard key={r.symbol} r={r} onClick={() =>
              navigate(`/sepa/${encodeURIComponent(r.symbol)}`, {
                state: { from: '/options', label: 'Options Pulse' },
              })
            } />
          ))}
        </div>
      )}
    </div>
  );
}

function SoirCard({ r, onClick }: { r: SoirRow; onClick: () => void }) {
  const sig = r.signal ?? 'NEUTRAL';
  const tone = SIGNAL_TONE[sig];
  const pct = r.soir_percentile;
  const pctSource = r.percentile_source === 'cross_section' ? ' (cross-section)' : '';

  return (
    <article className={`op-card ${tone}`} onClick={onClick} role="button" tabIndex={0}>
      <header className="op-card__head">
        <div className="op-card__sym">{r.symbol}</div>
        <div className={`op-card__signal ${tone}`}>{SIGNAL_LABEL[sig]}</div>
      </header>

      <div className="op-card__metrics">
        <div className="op-metric">
          <div className="eyebrow">SOIR</div>
          <div className="op-metric__num mono">{fmtSoir(r.soir)}</div>
          <div className="op-metric__sub mono">
            {r.put_oi != null && r.call_oi != null
              ? `${fmtNum(r.put_oi)}p / ${fmtNum(r.call_oi)}c`
              : '—'}
          </div>
        </div>
        <div className="op-metric">
          <div className="eyebrow">Percentile{pctSource}</div>
          <div className="op-metric__num mono">{fmtPct(pct)}</div>
          <div className="op-metric__sub mono">vs 52w</div>
        </div>
        <div className="op-metric">
          <div className="eyebrow">Expected move</div>
          <div className="op-metric__num mono">±{fmtPct(r.expected_move_pct)}</div>
          <div className="op-metric__sub mono">front straddle</div>
        </div>
        <div className="op-metric">
          <div className="eyebrow">ATM IV</div>
          <div className="op-metric__num mono">{fmtPct(r.atm_iv)}</div>
          <div className="op-metric__sub mono">annualized</div>
        </div>
      </div>

      <div className="op-card__pillars mono">
        <span className={`op-pill op-pill--trend-${r.trend ?? 'neutral'}`}>
          trend: <strong>{r.trend ?? '—'}</strong>
        </span>
        <span className="op-pill">
          SEPA: <strong>{r.sepa_score != null ? r.sepa_score.toFixed(0) : '—'}</strong>
        </span>
        <span className="op-pill">
          spot <strong>${r.spot?.toFixed(2) ?? '—'}</strong>
        </span>
      </div>

      {/* Trade plan — entry/stop/+1R from the SEPA scan when this ticker
          is also in SEPA's coverage. Only shown for BULLISH/BEARISH signals
          since NEUTRAL doesn't imply a directional trade. */}
      {r.trade_plan && (r.signal === 'BULLISH' || r.signal === 'BEARISH') && (
        <TradePlanInline plan={r.trade_plan} />
      )}

      {r.reason && (
        <div className="op-card__reason">{r.reason}</div>
      )}
    </article>
  );
}
