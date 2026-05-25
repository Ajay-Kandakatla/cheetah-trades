import { useMemo, useState } from 'react';
import {
  useHeadline,
  useScoreboard,
  useAccuracyHistory,
  useObservations,
  useTopWinners,
  useMarketHistory,
  useInsights,
  type CalibrationRow,
  type HistoryRow,
  type ObservationRow,
  type MarketRow,
  type Insight,
} from '../hooks/useCalibration';
import { TickerLink } from './TickerLink';
import { InfoButton } from './InfoButton';
import { InlineInfo } from './InlineInfo';

/* ==========================================================================
   /track Calibration tab — self-learning scoreboard + drill-in.
   --------------------------------------------------------------------------
   Layout:
     [How to read · InfoButton]
     [Headline number — total right vs wrong]
     [Top wins panel — names that got called correctly multiple times]
     [Accuracy timeline — line chart over last 60d]
     [Per-source scoreboard — verdict tags, hit %, recommended weight]
     [Recent observations — tabbed (Hits | Misses | Partials | All)
                            with ticker search filter]
   ========================================================================== */

const HowToRead = (
  <>
    <p>
      <strong>What this page is.</strong> Every signal the app emits — a
      stock entering the SEPA list, a catalyst being flagged, sentiment
      turning bullish — gets logged as an <em>observation</em>. After the
      prediction's horizon expires (1 day for SEPA-tier today), an automated
      resolver fetches the actual price and grades the observation.
    </p>

    <p><strong>Definitions:</strong></p>
    <ul>
      <li>
        <strong>Hit</strong> — direction was right (stock went up when we said up)
        AND the magnitude landed in the expected range. Counts as a full point.
      </li>
      <li>
        <strong>Partial</strong> — direction was right but the magnitude was off
        (much smaller or much larger move than expected). Half-point.
      </li>
      <li>
        <strong>Miss</strong> — direction was wrong. Zero credit.
      </li>
    </ul>

    <p><strong>The two percentages:</strong></p>
    <ul>
      <li><strong>Strict hit rate</strong> = hits ÷ total. Most conservative read.</li>
      <li>
        <strong>Tolerant hit rate</strong> = (hits + 0.5 × partials) ÷ total.
        Counts being directionally right but magnitude-off as half a win.
      </li>
    </ul>

    <p>
      <strong>50% is the coin-flip baseline.</strong> Above 65% is real edge.
      Below 45% means the signal is dead weight (or a contrarian indicator —
      worth checking with the inverse hit rate).
    </p>

    <p>
      <strong>Recommended weight</strong> is what the system <em>would</em>
      use to reweight this signal in future predictions. 1.0× is neutral.
      Below 0.65× means the signal is being downweighted because it's
      underperforming. The floor is 0.30× — we never zero a source out
      entirely, in case it recovers.
    </p>

    <p style={{ marginTop: '0.8rem', padding: '0.6rem 0.8rem', background: 'var(--gold-faint)', borderLeft: '3px solid var(--gold)', borderRadius: 3 }}>
      <strong>Important caveat for SEPA-tier accuracy.</strong> Today the
      backfill grades against a <em>1-day</em> horizon. SEPA is a
      <em>positional</em> setup — Minervini designed it for 5-30 day plays.
      So a 47% next-day hit rate is expected; the real edge shows up at
      5d and 10d horizons. We'll re-run the backfill at longer horizons in
      a follow-up.
    </p>
  </>
);

function pct(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined) return '—';
  return `${(x * 100).toFixed(digits)}%`;
}

function fmtSource(s: string): string {
  if (s === 'ALL') return 'ALL · everything combined';
  if (s.startsWith('sepa_tier_')) return `SEPA · ${s.replace('sepa_tier_', '')}`;
  if (s.startsWith('catalyst_tier_')) return `Catalyst · tier ${s.replace('catalyst_tier_', '').toUpperCase()}`;
  if (s.startsWith('sentiment_')) return `Sentiment · ${s.replace('sentiment_', '')}`;
  if (s.startsWith('frenzy_')) return `Frenzy · ${s.replace('frenzy_', '').replace(/_/g, ' ')}`;
  return s.replace(/_/g, ' · ');
}

function verdict(row: CalibrationRow): { label: string; tone: 'good' | 'mid' | 'bad' | 'na'; help: string } {
  if (row.n < 5) return { label: 'no data', tone: 'na', help: 'Need at least 5 graded observations for a meaningful read.' };
  const hr = row.hit_rate ?? 0;
  if (hr >= 0.65) return { label: 'strong', tone: 'good', help: 'Real edge — hitting well above coin-flip.' };
  if (hr >= 0.55) return { label: 'useful', tone: 'good', help: 'Modest edge — adds value when combined with other signals.' };
  if (hr >= 0.48) return { label: 'marginal', tone: 'mid', help: 'About a coin flip. Needs more data or a different horizon.' };
  if (hr >= 0.40) return { label: 'weak', tone: 'bad', help: 'Underperforming. Being downweighted in the recommended weight.' };
  return { label: 'contrarian?', tone: 'bad', help: 'Hitting below 40% — the inverse signal might be the real edge.' };
}

/* ── Market timeline (SPY cum %-change) ──────────────────────────────── */
function MarketTimeline({ rows, alignDates }: { rows: MarketRow[]; alignDates: string[] }) {
  const [hovered, setHovered] = useState<number | null>(null);

  // Filter market rows to dates that overlap with the accuracy timeline so
  // both charts align visually on the x-axis.
  const filtered = useMemo(() => {
    if (!alignDates.length) return rows;
    const set = new Set(alignDates);
    return rows.filter((r) => set.has(r.date_et));
  }, [rows, alignDates]);

  if (!filtered.length) {
    return (
      <div className="cal-empty mono">
        Market data unavailable for this range.
      </div>
    );
  }

  const w = 600, h = 140, pad = 32;
  const xs = filtered.map((_, i) => pad + (i * (w - 2 * pad)) / Math.max(1, filtered.length - 1));
  const values = filtered.map((r) => r.cum_pct);
  const maxV = Math.max(2, ...values);
  const minV = Math.min(-2, ...values);
  const ys = values.map((v) => h - pad - ((v - minV) / (maxV - minV || 1)) * (h - 2 * pad));
  const path = xs.map((x, i) => `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${ys[i].toFixed(1)}`).join(' ');
  const last = filtered[filtered.length - 1];
  const lastVal = last.cum_pct;
  const yFor = (v: number) => h - pad - ((v - minV) / (maxV - minV || 1)) * (h - 2 * pad);

  const hoveredRow = hovered !== null ? filtered[hovered] : null;
  const tooltipX = hovered !== null ? xs[hovered] : 0;
  const tooltipY = hovered !== null ? ys[hovered] : 0;
  const tooltipFlip = hovered !== null && tooltipX > w * 0.7;

  // Color the path based on whether market is net positive at end
  const pathColor = lastVal >= 0 ? 'var(--cm-green)' : 'var(--cm-red, #dc2626)';
  const dotColor = pathColor;

  return (
    <div className="cal-timeline-wrap">
      <svg viewBox={`0 0 ${w} ${h}`} className="cal-timeline" preserveAspectRatio="xMidYMid meet">
        {/* 0% baseline */}
        <line x1={pad} x2={w - pad} y1={yFor(0)} y2={yFor(0)}
              stroke="var(--ink-faint)" strokeDasharray="3 4" strokeWidth="1" />
        <text x={pad - 4} y={yFor(0) + 3} textAnchor="end" fontSize="9" fill="var(--ink-faint)">0%</text>

        <path d={path} fill="none" stroke={pathColor} strokeWidth="2" strokeLinejoin="round" />

        {xs.map((x, i) => (
          <circle key={`d-${i}`} cx={x} cy={ys[i]} r={hovered === i ? 5 : 3}
                  fill={hovered === i ? 'var(--ink)' : dotColor}
                  stroke={hovered === i ? dotColor : 'none'} strokeWidth="2"
                  style={{ pointerEvents: 'none', transition: 'r 80ms' }} />
        ))}

        {xs.map((x, i) => (
          <circle key={`h-${i}`} cx={x} cy={ys[i]} r={14} fill="transparent"
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setHovered(i)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => setHovered(hovered === i ? null : i)}
                  onTouchStart={() => setHovered(i)} />
        ))}

        {hovered === null && (
          <text x={xs[xs.length - 1] + 6} y={ys[ys.length - 1] + 3}
                fontSize="10" fontWeight="700" fill={pathColor}>
            {lastVal >= 0 ? '+' : ''}{lastVal.toFixed(1)}%
          </text>
        )}

        {[0, Math.floor(filtered.length / 2), filtered.length - 1].map((i) => (
          filtered[i] && (
            <text key={`x-${i}`} x={xs[i]} y={h - 6} fontSize="9" fill="var(--ink-muted)" textAnchor="middle">
              {filtered[i].date_et.slice(5)}
            </text>
          )
        ))}

        {hoveredRow && (
          <g className="cal-tt"
             transform={`translate(${tooltipFlip ? tooltipX - 122 : tooltipX + 10}, ${Math.max(8, tooltipY - 38)})`}>
            <rect x="0" y="0" width="118" height="42" rx="4"
                  fill="var(--bg-raised)" stroke={pathColor} strokeWidth="1" />
            <text x="8" y="14" fontSize="10" fontWeight="700" fill="var(--ink)">
              {hoveredRow.date_et}
            </text>
            <text x="8" y="26" fontSize="11" fontWeight="700" fill={pathColor}>
              {hoveredRow.cum_pct >= 0 ? '+' : ''}{hoveredRow.cum_pct.toFixed(2)}% cum
            </text>
            <text x="8" y="37" fontSize="9" fill="var(--ink-muted)">
              day {hoveredRow.day_pct >= 0 ? '+' : ''}{hoveredRow.day_pct.toFixed(2)}%
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}

/* ── Insights panel — auto-extracted patterns from observation data ──── */
function InsightsPanel({ insights }: { insights: Insight[] }) {
  if (!insights.length) {
    return (
      <div className="cal-empty">
        No insights yet — needs more graded data. Insights surface automatically
        once we have at least 5 observations per bucket.
      </div>
    );
  }
  return (
    <div className="cal-insights">
      {insights.map((ins, i) => (
        <article key={i} className={`cal-insight cal-insight--${ins.tone}`}>
          <div className="cal-insight__icon">
            {ins.tone === 'good' ? '✓' : ins.tone === 'bad' ? '⚠' : '·'}
          </div>
          <div className="cal-insight__body">
            <h4 className="cal-insight__title">{ins.title}</h4>
            <p className="cal-insight__detail">{ins.detail}</p>
          </div>
        </article>
      ))}
    </div>
  );
}

/* ── Line chart of accuracy over time, with proper hover tooltip ──────── */
function AccuracyTimeline({ rows }: { rows: HistoryRow[] }) {
  const [hovered, setHovered] = useState<number | null>(null);

  if (!rows.length) {
    return (
      <div className="cal-empty mono">
        Not enough history to plot yet — needs at least a few days of resolved observations.
      </div>
    );
  }
  const w = 600, h = 140, pad = 32;
  const xs = rows.map((_, i) => pad + (i * (w - 2 * pad)) / Math.max(1, rows.length - 1));
  const values = rows.map((r) => (r.weighted_hit_rate ?? r.hit_rate ?? 0));
  const maxV = Math.max(0.7, ...values);
  const minV = Math.min(0.3, ...values);
  const ys = values.map((v) => h - pad - ((v - minV) / (maxV - minV || 1)) * (h - 2 * pad));
  const path = xs.map((x, i) => `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${ys[i].toFixed(1)}`).join(' ');
  const last = rows[rows.length - 1];
  const lastVal = (last.weighted_hit_rate ?? last.hit_rate ?? 0) * 100;
  const yFor = (v: number) => h - pad - ((v - minV) / (maxV - minV || 1)) * (h - 2 * pad);

  const hoveredRow = hovered !== null ? rows[hovered] : null;
  const tooltipX = hovered !== null ? xs[hovered] : 0;
  const tooltipY = hovered !== null ? ys[hovered] : 0;
  // Position tooltip — flip to left side if too close to right edge
  const tooltipFlip = hovered !== null && tooltipX > w * 0.7;

  return (
    <div className="cal-timeline-wrap">
      <svg viewBox={`0 0 ${w} ${h}`} className="cal-timeline" preserveAspectRatio="xMidYMid meet">
        {/* 50% coin-flip baseline */}
        <line x1={pad} x2={w - pad} y1={yFor(0.5)} y2={yFor(0.5)}
              stroke="var(--ink-faint)" strokeDasharray="3 4" strokeWidth="1" />
        <text x={pad - 4} y={yFor(0.5) + 3} textAnchor="end" fontSize="9" fill="var(--ink-faint)">50%</text>
        {/* 65% edge line */}
        {maxV >= 0.65 && (
          <>
            <line x1={pad} x2={w - pad} y1={yFor(0.65)} y2={yFor(0.65)}
                  stroke="var(--cm-green)" strokeDasharray="2 6" strokeWidth="1" opacity="0.5" />
            <text x={pad - 4} y={yFor(0.65) + 3} textAnchor="end" fontSize="9" fill="var(--cm-green)" opacity="0.7">65%</text>
          </>
        )}
        {/* Accuracy path */}
        <path d={path} fill="none" stroke="var(--gold)" strokeWidth="2" strokeLinejoin="round" />

        {/* Visible dots */}
        {xs.map((x, i) => (
          <circle key={`d-${i}`} cx={x} cy={ys[i]} r={hovered === i ? 5 : 3}
                  fill={hovered === i ? 'var(--ink)' : 'var(--gold)'}
                  stroke={hovered === i ? 'var(--gold)' : 'none'}
                  strokeWidth="2"
                  style={{ pointerEvents: 'none', transition: 'r 80ms' }} />
        ))}

        {/* Invisible big hit-targets so hover/tap is forgiving */}
        {xs.map((x, i) => (
          <circle key={`h-${i}`} cx={x} cy={ys[i]} r={14}
                  fill="transparent"
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setHovered(i)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => setHovered(hovered === i ? null : i)}
                  onTouchStart={() => setHovered(i)} />
        ))}

        {/* End point label (only if no dot is being hovered) */}
        {hovered === null && (
          <text x={xs[xs.length - 1] + 6} y={ys[ys.length - 1] + 3}
                fontSize="10" fontWeight="700" fill="var(--gold)">
            {lastVal.toFixed(0)}%
          </text>
        )}

        {/* x-axis dates */}
        {[0, Math.floor(rows.length / 2), rows.length - 1].map((i) => (
          rows[i] && (
            <text key={`x-${i}`} x={xs[i]} y={h - 6} fontSize="9" fill="var(--ink-muted)" textAnchor="middle">
              {rows[i].date_et.slice(5)}
            </text>
          )
        ))}

        {/* Tooltip — rendered as SVG group so it scales with the chart */}
        {hoveredRow && (
          <g className="cal-tt"
             transform={`translate(${tooltipFlip ? tooltipX - 122 : tooltipX + 10}, ${Math.max(8, tooltipY - 38)})`}>
            <rect x="0" y="0" width="118" height="42" rx="4"
                  fill="var(--bg-raised)" stroke="var(--gold-hairline)" strokeWidth="1" />
            <text x="8" y="14" fontSize="10" fontWeight="700" fill="var(--ink)">
              {hoveredRow.date_et}
            </text>
            <text x="8" y="26" fontSize="11" fontWeight="700" fill="var(--gold)">
              {pct(hoveredRow.weighted_hit_rate ?? hoveredRow.hit_rate)} hit rate
            </text>
            <text x="8" y="37" fontSize="9" fill="var(--ink-muted)">
              n = {hoveredRow.n} graded
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}

type StatusTab = 'hit' | 'miss' | 'partial' | 'all';
type SortKey = 'recent' | 'gain' | 'loss' | 'biggest' | 'score' | 'ticker';

const SORT_OPTIONS: { key: SortKey; label: string; help: string }[] = [
  { key: 'recent', label: 'Recent', help: 'Most recently graded first' },
  { key: 'gain', label: '↑ Best gain', help: 'Biggest positive % move first' },
  { key: 'loss', label: '↓ Worst loss', help: 'Biggest negative % move first' },
  { key: 'biggest', label: '|Δ| Biggest move', help: 'Largest absolute move regardless of direction' },
  { key: 'score', label: 'SEPA score', help: 'Highest SEPA score first' },
  { key: 'ticker', label: 'Ticker A–Z', help: 'Alphabetical by symbol' },
];

function applySort(rows: ObservationRow[], key: SortKey): ObservationRow[] {
  const out = rows.slice();
  switch (key) {
    case 'gain':
      out.sort((a, b) => (b.actual_pct ?? -Infinity) - (a.actual_pct ?? -Infinity));
      break;
    case 'loss':
      out.sort((a, b) => (a.actual_pct ?? Infinity) - (b.actual_pct ?? Infinity));
      break;
    case 'biggest':
      out.sort((a, b) => Math.abs(b.actual_pct ?? 0) - Math.abs(a.actual_pct ?? 0));
      break;
    case 'score':
      out.sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity));
      break;
    case 'ticker':
      out.sort((a, b) => a.ticker.localeCompare(b.ticker));
      break;
    case 'recent':
    default:
      out.sort((a, b) => b.ts - a.ts);
      break;
  }
  return out;
}

/* ── Observation accordion — collapsed row + expandable reason panel ── */
function ObservationAccordion({ obs }: { obs: ObservationRow }) {
  const [open, setOpen] = useState(false);
  const pct = obs.actual_pct ?? 0;
  const pctSign = pct > 0 ? '+' : '';
  const statusGlyph = obs.status === 'hit' ? '✓' : obs.status === 'miss' ? '✗' : '◐';
  const statusText = obs.status === 'hit' ? 'right' : obs.status === 'miss' ? 'wrong' : 'partial';

  return (
    <li className={`cal-obs__row cal-obs__row--${obs.status} ${open ? 'is-open' : ''}`}>
      <button
        type="button"
        className="cal-obs__head"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        title={`Click to ${open ? 'collapse' : 'see why this was ' + statusText}`}
      >
        <span className="cal-obs__status mono">{statusGlyph}</span>
        <span className="cal-obs__sym">{obs.ticker}</span>
        <span className="mono cal-obs__src">{fmtSource(obs.source)}</span>
        <span className="mono cal-obs__date">{obs.date_et}</span>
        <span className="mono cal-obs__price">
          ${obs.baseline_price?.toFixed(2)} → ${obs.actual_price?.toFixed(2)}
        </span>
        <span className={`mono cal-obs__pct ${pct < 0 ? 'is-down' : 'is-up'}`}>
          {pctSign}{pct.toFixed(1)}%
        </span>
        <span className="cal-obs__caret" aria-hidden="true">
          {open ? '▾' : '▸'}
        </span>
      </button>

      {open && (
        <div className="cal-obs__body">
          {/* Why label */}
          <div className="cal-obs__why">
            <span className={`cal-obs__why-tag cal-obs__why-tag--${obs.status}`}>
              Why we were {statusText}
            </span>
            <p className="cal-obs__reason">
              {obs.reason ?? 'No reason data — observation missing context.'}
            </p>
          </div>

          {/* Context tags */}
          {obs.tags && obs.tags.length > 0 && (
            <div className="cal-obs__tags">
              {obs.tags.map((t, ti) => (
                <span key={ti} className="cal-obs__tag mono">{t}</span>
              ))}
            </div>
          )}

          {/* Failed gates (only for misses where we have detail) */}
          {obs.failed_gates && obs.failed_gates.length > 0 && (
            <div className="cal-obs__gates">
              <span className="cal-obs__gates-label">Failed gates:</span>
              {obs.failed_gates.map((g, gi) => (
                <span key={gi} className="cal-obs__gate-x mono">✗ {g}</span>
              ))}
            </div>
          )}

          {/* Quick links */}
          <div className="cal-obs__links">
            <TickerLink
              ticker={obs.ticker}
              fromLabel="calibration"
              className="cal-obs__drill"
            >
              Open SEPA detail for {obs.ticker} →
            </TickerLink>
          </div>
        </div>
      )}
    </li>
  );
}

export function Calibration() {
  const [window, setWindow] = useState<number>(30);
  const [statusTab, setStatusTab] = useState<StatusTab>('hit');
  const [tickerFilter, setTickerFilter] = useState<string>('');
  const [sortKey, setSortKey] = useState<SortKey>('recent');

  const { data: headline } = useHeadline();
  const { rows: scoreboard, loading: sbLoading } = useScoreboard(window);
  const { rows: history } = useAccuracyHistory('ALL', window, 60);
  const { rows: market } = useMarketHistory(60);
  const { data: insightsData } = useInsights(window);
  const { rows: observations } = useObservations({
    status: statusTab,
    ticker: tickerFilter.trim() || undefined,
    // Bump limit when sorting so the sort actually surfaces extremes
    limit: sortKey === 'recent' ? 50 : 200,
  });
  const sortedObservations = useMemo(
    () => applySort(observations, sortKey),
    [observations, sortKey],
  );
  const { rows: winners } = useTopWinners(window, 8);

  const sortedScoreboard = useMemo(() => {
    const all = scoreboard.find((r) => r.source === 'ALL');
    const rest = scoreboard.filter((r) => r.source !== 'ALL')
      .sort((a, b) => (b.hit_rate ?? 0) - (a.hit_rate ?? 0));
    return all ? [all, ...rest] : rest;
  }, [scoreboard]);

  const headlineRow = headline?.by_window?.[window] as CalibrationRow | undefined;
  const totalN = headlineRow?.n ?? 0;
  const totalHits = headlineRow?.hits ?? 0;
  const totalPartials = headlineRow?.partials ?? 0;
  const totalMisses = headlineRow?.misses ?? 0;
  const hr = headlineRow?.hit_rate;
  const whr = headlineRow?.weighted_hit_rate;

  return (
    <div className="cal">
      {/* How-to-read header */}
      <div className="cal-howto">
        <InfoButton title="How to read this">{HowToRead}</InfoButton>
        <div>
          <div className="eyebrow">Self-learning · {window}d window</div>
          <p className="cal-howto__lede">
            Every signal the app emits is logged, then graded after its horizon
            expires. <strong>Click the ⓘ</strong> for the full guide on how to
            read each panel.
          </p>
        </div>
      </div>

      {/* Headline number */}
      <section className="cal-hero">
        <div className="cal-hero__main">
          <div className="eyebrow">Right vs wrong — total</div>
          <div className="cal-hero__pcts">
            <div className="cal-hero__big">
              <span className="cal-hero__num">{pct(hr, 1)}</span>
              <span className="cal-hero__label">
                strict
                <InlineInfo label="What is strict hit rate?">
                  <strong>Strict hit rate</strong> = hits ÷ total observations.
                  Most conservative read — only counts predictions where direction
                  was right AND magnitude was on target.
                </InlineInfo>
              </span>
            </div>
            <div className="cal-hero__big cal-hero__big--soft">
              <span className="cal-hero__num">{pct(whr, 1)}</span>
              <span className="cal-hero__label">
                tolerant
                <InlineInfo label="What is tolerant hit rate?">
                  <strong>Tolerant hit rate</strong> = (hits + 0.5 × partials) ÷ total.
                  Counts directionally-right-but-magnitude-off predictions as half a win.
                  Better reflection of "we were generally correct".
                </InlineInfo>
              </span>
            </div>
          </div>
          <div className="cal-hero__breakdown mono">
            <span>
              {totalHits} hits
              <InlineInfo label="What is a hit?">
                <strong>Hit</strong> — direction was right (stock went up when we said up)
                AND magnitude landed within 50%–150% of predicted. Full point.
              </InlineInfo>
            </span>
            {' · '}
            <span>
              {totalPartials} partials
              <InlineInfo label="What is a partial?">
                <strong>Partial</strong> — direction was right but magnitude was off.
                E.g. predicted +5%, got +0.8% or +12%. Half-point.
              </InlineInfo>
            </span>
            {' · '}
            <span>
              {totalMisses} misses
              <InlineInfo label="What is a miss?">
                <strong>Miss</strong> — direction was wrong (we said up, stock went down).
                Zero credit, contributes -1.0 to accuracy score.
              </InlineInfo>
            </span>
            {' · '}
            <span>{totalN} graded total</span>
          </div>
          <div className="cal-hero__note">
            <strong>50%</strong> is coin flip · <strong>65%+</strong> is real edge ·
            <strong> &lt;45%</strong> is dead weight (or contrarian)
          </div>
        </div>
        <div className="cal-hero__windows">
          {[7, 30, 90].map((w) => (
            <button key={w}
                    className={`sepa-chip ${window === w ? 'is-active' : ''}`}
                    onClick={() => setWindow(w)}
                    title={`Roll the headline + scoreboard over the last ${w} days`}>
              {w}d
            </button>
          ))}
        </div>
      </section>

      {/* Top wins — names the system called repeatedly correctly */}
      {winners.length > 0 && (
        <section className="cal-card cal-wins">
          <header className="cal-card__head">
            <h3>🏆 Names the system got right</h3>
            <span className="mono cal-card__sub">
              {window}d · ranked by hits, tie-break avg move
            </span>
          </header>
          <div className="cal-wins__grid">
            {winners.map((w) => (
              <div key={w.ticker} className="cal-win">
                <div className="cal-win__head">
                  <TickerLink ticker={w.ticker} fromLabel="calibration" className="cal-win__sym" />
                  <span className="cal-win__count mono">{w.hits}× hit</span>
                </div>
                {w.last_price != null && (
                  <div className="cal-win__price mono" title={`Last graded close on ${w.last_price_date ?? '—'}`}>
                    <span className="cal-win__price-label">Price</span>
                    <strong>${w.last_price.toFixed(2)}</strong>
                    {w.last_price_date && <span className="cal-win__price-date">as of {w.last_price_date}</span>}
                  </div>
                )}
                <div className="cal-win__pct mono">
                  avg <strong>+{w.avg_pct.toFixed(1)}%</strong> · best +{w.best_pct.toFixed(1)}%
                </div>
                <div className="cal-win__sources mono">
                  {w.sources.map(fmtSource).join(' · ')}
                </div>
                <div className="cal-win__date mono">last hit: {w.last_date}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Insights — auto-extracted learnings */}
      <section className="cal-card">
        <header className="cal-card__head">
          <h3>📈 Learnings</h3>
          <span className="mono cal-card__sub">
            patterns extracted from {insightsData?.total_n ?? 0} graded observations
          </span>
        </header>
        <InsightsPanel insights={insightsData?.insights ?? []} />
      </section>

      {/* Dual-chart: our accuracy vs the market over the same window */}
      <section className="cal-card">
        <header className="cal-card__head">
          <h3>Predictions vs. market</h3>
          <span className="mono cal-card__sub">last 60d · same x-axis</span>
        </header>
        <div className="cal-charts">
          <div className="cal-chart">
            <div className="cal-chart__title mono">
              Our hit rate <span className="cal-chart__pill cal-chart__pill--gold">tolerant %</span>
            </div>
            <AccuracyTimeline rows={history} />
          </div>
          <div className="cal-chart">
            <div className="cal-chart__title mono">
              S&amp;P 500 <span className="cal-chart__pill cal-chart__pill--mkt">cumulative %</span>
            </div>
            <MarketTimeline rows={market} alignDates={history.map((h) => h.date_et)} />
          </div>
        </div>
        <p className="cal-card__foot">
          Two charts share the same date range. Hover dots in either chart for
          the per-day values. <strong>Look for correlation</strong> — if our
          hit rate dips when the market dips, we're trend-following; if it
          stays flat through chop, we're picking real names not just beta.
        </p>
      </section>

      {/* Per-source scoreboard */}
      <section className="cal-card">
        <header className="cal-card__head">
          <h3>By signal source</h3>
          <span className="mono cal-card__sub">{window}d · sorted by hit rate · ALL row pinned</span>
        </header>
        {sbLoading ? (
          <div className="cal-empty">Loading…</div>
        ) : sortedScoreboard.length === 0 ? (
          <div className="cal-empty">
            <p>No graded observations yet.</p>
          </div>
        ) : (
          <table className="cal-table">
            <thead>
              <tr>
                <th>Source</th>
                <th className="num">
                  N
                  <InlineInfo label="What is N?">
                    <strong>N</strong> — number of graded observations from this source
                    in the selected window. Sample size. Below 5 = not enough data.
                  </InlineInfo>
                </th>
                <th className="num">
                  Hit%
                  <InlineInfo label="What is Hit %?">
                    <strong>Strict hit rate</strong> = hits ÷ N. Direction was right and
                    magnitude landed on target. Above 65% = real edge; below 45% = noise.
                  </InlineInfo>
                </th>
                <th className="num">
                  w/Hit%
                  <InlineInfo label="What is weighted hit rate?">
                    <strong>Tolerant hit rate</strong> = (hits + 0.5 × partials) ÷ N.
                    Counts "right direction, wrong magnitude" as half a win. Less harsh.
                  </InlineInfo>
                </th>
                <th className="num">Hits</th>
                <th className="num" title="Partials — direction was right but magnitude was off">Partials</th>
                <th className="num">Misses</th>
                <th className="num">
                  Weight
                  <InlineInfo label="What is the recommended weight?">
                    <strong>Recommended weight</strong> — what the synthesizer would use
                    to reweight this signal next time. <strong>1.00×</strong> = neutral.
                    Below 0.65× = signal is being downweighted because it underperforms.
                    Floor is 0.30× — we never zero a source out entirely.
                  </InlineInfo>
                </th>
                <th>Verdict</th>
              </tr>
            </thead>
            <tbody>
              {sortedScoreboard.map((r) => {
                const v = verdict(r);
                return (
                  <tr key={`${r.source}-${r.window_days}`} className={r.source === 'ALL' ? 'cal-row--all' : ''}>
                    <td>{fmtSource(r.source)}</td>
                    <td className="num">{r.n}</td>
                    <td className="num">{pct(r.hit_rate)}</td>
                    <td className="num">{pct(r.weighted_hit_rate)}</td>
                    <td className="num">{r.hits}</td>
                    <td className="num">{r.partials}</td>
                    <td className="num">{r.misses}</td>
                    <td className="num">{r.recommended_weight.toFixed(2)}x</td>
                    <td>
                      <span className={`cal-verdict cal-verdict--${v.tone}`} title={v.help}>
                        {v.label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      {/* Observations list — Hits / Misses / Partials with ticker filter */}
      <section className="cal-card">
        <header className="cal-card__head">
          <h3>Observations</h3>
          <span className="mono cal-card__sub">click any ticker to drill in</span>
        </header>
        <div className="cal-obs-controls">
          <div className="cal-obs-tabs">
            {(['hit', 'miss', 'partial', 'all'] as StatusTab[]).map((t) => (
              <button key={t}
                      className={`sepa-chip ${statusTab === t ? 'is-active' : ''}`}
                      onClick={() => setStatusTab(t)}>
                {t === 'hit' ? '✓ Hits' :
                 t === 'miss' ? '✗ Misses' :
                 t === 'partial' ? '◐ Partials' :
                 'All'}
              </button>
            ))}
          </div>
          <input
            type="search"
            className="cal-obs-filter"
            placeholder="Filter ticker (e.g. SNDK, MU)…"
            value={tickerFilter}
            onChange={(e) => setTickerFilter(e.target.value.toUpperCase())}
          />
        </div>

        {/* Sort row — separate so it wraps cleanly on its own line */}
        <div className="cal-obs-sort">
          <span className="cal-obs-sort__label mono">Sort by</span>
          <div className="cal-obs-sort__chips">
            {SORT_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                className={`sepa-chip ${sortKey === opt.key ? 'is-active' : ''}`}
                onClick={() => setSortKey(opt.key)}
                title={opt.help}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <span className="cal-obs-sort__count mono">
            {sortedObservations.length} shown
          </span>
        </div>

        {sortedObservations.length === 0 ? (
          <div className="cal-empty">
            {tickerFilter ? <>No <strong>{statusTab}</strong> observations for {tickerFilter}.</> :
             <>No {statusTab} observations yet.</>}
          </div>
        ) : (
          <ul className="cal-obs">
            {sortedObservations.map((o: ObservationRow, i) => (
              <ObservationAccordion key={`${o.ticker}-${o.ts}-${i}`} obs={o} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
