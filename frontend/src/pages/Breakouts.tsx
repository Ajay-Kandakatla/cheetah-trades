/* BreakoutsPage — a dedicated tracker for breakouts (Ajay 2026-06-16: "a page to
 * track ONLY breakouts and # of breakouts, starting with the highest breakouts.
 * Some passing Minervinis and some not, and Pradeep Bondi — but mainly around
 * breakouts").
 *
 * Every name that has actually broken out, ranked by breakout COUNT (highest
 * first — book p.203 definition: close above the prior 21-day high on >1.5×
 * average volume), each carrying the Minervini+Bonde buy_verdict so the
 * passing-vs-not mix is visible at a glance. Filter chips slice the same
 * breakout list by which methodology passes. Display-only — feeds no score.
 *
 * Reads GET /sepa/breakout-board (backend/sepa/breakout.board). Tap a row → its
 * detail Breakout tab (where each breakout fired on the chart).
 */
import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import { useBreakoutBoard, type BreakoutBoardRow } from '../hooks/useBreakoutBoard';
import { useSepaScanStream } from '../hooks/useSepaScanStream';
import { useSort, type SortDir } from '../lib/useSort';
import { aiSectorSortValue } from '../lib/breakoutSort';
import { marchToTarget, stageMeta, isExtendedToR2 } from '../lib/breakoutTargets';
import { LeveragedBadge } from '../components/LeveragedBadge';
import { BreakoutBreadthStrip } from '../components/BreakoutBreadthStrip';
import { isBaseSetup, setupBadge } from '../lib/baseSetup';
import { BuyVerdictChip } from '../components/BuyVerdictChip';
import { ListSkeleton } from '../components/Skeletons';
import { InfoButton } from '../components/InfoButton';
import { NewBadge } from '../components/NewBadge';

type FilterKey = 'all' | 'today' | 'buyable' | 'minervini_pass' | 'minervini_fail' | 'bonde_pass' | 'bonde_fail' | 'both_pass';

const mPass = (r: BreakoutBoardRow) => r.buy_verdict?.minervini?.passed === true;
const mFail = (r: BreakoutBoardRow) => r.buy_verdict?.minervini?.passed === false;
const bPass = (r: BreakoutBoardRow) => r.buy_verdict?.bonde?.passed === true;
const bFail = (r: BreakoutBoardRow) => r.buy_verdict?.bonde?.passed === false;

const FILTERS: { key: FilterKey; label: string; tip: string; match: (r: BreakoutBoardRow) => boolean }[] = [
  { key: 'all',            label: 'All breakouts',  tip: 'Every name with ≥1 volume-confirmed breakout, most recent first.', match: () => true },
  { key: 'today',          label: '⚡ Broke out today', tip: 'Cleared its pivot on volume TODAY (days since breakout = 0).', match: (r) => r.broke_out_today },
  { key: 'buyable',        label: '🎯 Buyable now', tip: 'Clears the strict Minervini buy-now gate (is_buyable, pp.79-83/198-203): Stage 2 + a setup + not avoid-stage (base ≥5) + not exhausted + a volume-confirmed breakout, in the buy zone. The SAME gate as the SEPA scan\'s 🟢 Enter — not just the Trend-Template qualifier.', match: (r) => r.is_buyable === true },
  { key: 'both_pass',      label: '🟢 Minervini + Bonde', tip: 'Both frameworks agree — Minervini buyable-stock gate AND Bonde sales both pass.', match: (r) => r.buy_verdict?.both_pass === true },
  { key: 'minervini_pass', label: 'Minervini ✓',    tip: 'Passes Minervini\'s Trend-Template qualifier (p.79).', match: mPass },
  { key: 'minervini_fail', label: 'Minervini ✗',    tip: 'Breaking out but NOT a Minervini qualifier — broke out from a non-Stage-2 / non-template structure.', match: mFail },
  { key: 'bonde_pass',     label: 'Bonde ✓',        tip: 'Passes Bonde\'s sales test (≥5% growth + acceleration or 2+ consecutive growth quarters).', match: bPass },
  { key: 'bonde_fail',     label: 'Bonde ✗',        tip: 'Breaking out but sales don\'t clear Bonde\'s bar.', match: bFail },
];

const PageInfo = (
  <>
    <p>
      Every name that has <strong>broken out</strong> — a close above its prior
      21-day high on more than 1.5× average volume (Minervini p.203) — ranked by
      <strong> how many times</strong> it's done so over the trailing year.
    </p>
    <ul>
      <li><strong># breakouts</strong> — count of distinct volume-confirmed breakouts. A column, no longer the ranking.</li>
      <li><strong>Verdict</strong> — the combined Minervini-buyable + Bonde-sales PASS/PARTIAL/FAIL. Filter the list by which side passes.</li>
      <li><strong>⚡ today</strong> — it cleared its pivot on volume in the latest session.</li>
      <li><strong>Stage</strong> — Weinstein/Minervini stage. <strong>✓ S2</strong> (advancing) is the only buyable stage; S4 (decline) is avoid.</li>
      <li><strong>→ R1/R2</strong> — which trade-plan target (entry +1R / +2R) it's marching toward, and the % above price to reach it. “Past R2” = extended.</li>
    </ul>
    <p className="mono">Display-only. Not investment advice.</p>
  </>
);

/* Column reference — opened from the ⓘ on the table itself, so the meaning of
 * every column is one tap away right where the data is (Ajay 2026-06-17). */
const ColumnsInfo = (
  <>
    <p>
      What each column means. The table sorts by <strong>any</strong> column — tap
      a header, tap again to flip. Default sort is <strong>income + growth,
      quarter over quarter</strong> (Ajay 2026-09-12: “May show any stage but
      prioritize income and growth only quarter over quarter”). The server ranks
      the same way <em>before</em> the top-250 cut, so the 250 you see are the
      250 best-ranked of ~2,840 candidates — not a re-sort of a list picked on
      other grounds. The <strong>🕑 Most recent</strong> chip restores this
      morning’s recency order.
    </p>
    <p>
      <strong>Quarter over quarter means the quarter just ended against the one
      before it</strong> — not against the same quarter a year ago. The board
      shows both: the big number is sequential, the small grey <em>y/y</em>
      beneath it is the year-over-year comparison the page has always carried.
      They disagree more often than you would expect (measured Spearman 0.58 on
      revenue, 0.37 on EPS): JFB’s revenue was <em>+418% y/y</em> and
      <em>−89% sequentially</em>, and sequential caught the collapse. Sequential
      also answers for names year-over-year cannot, because it needs two
      quarters where year-over-year needs five. It has one weakness
      year-over-year does not: <strong>seasonality</strong>. A retailer’s
      January quarter is smaller than its December quarter every single year,
      and sequential reads that as a decline. Measured on this board, the median
      sequential revenue move is <strong>+5.3%</strong> for a fiscal Q1→Q2
      transition against <strong>−4.0%</strong> for Q4→Q1 — a Q1 reporter is
      docked about nine points of “growth” for nothing but the calendar.
    </p>
    <p>
      So the <strong>ranking</strong> compares each name’s sequential move to
      what <em>the same transition did a year earlier</em>, and ranks on the
      difference. That is still quarter over quarter — measured against the
      company’s own calendar instead of against zero. <strong>🔁</strong> marks
      a row making a move it makes every year, and the number you see is still
      the plain sequential one.
    </p>
    <p>
      <strong>The honest limit, measured.</strong> Rank the board on last
      quarter’s <em>raw</em> sequential EPS and look at what those names did the
      next quarter: median <strong>+0.4%</strong>, 50% still positive
      <em>[25, 70]</em>. The placebo — every other name on the board — was
      median <strong>+24.0%</strong>, 70% positive <em>[61, 79]</em>. The raw
      sequential leaderboard did <em>worse</em> than the rest of the board. Part
      of that is mechanical: a big quarter becomes the next quarter’s
      denominator. That is exactly why the ranking uses the seasonally
      referenced number and not the raw one. Nothing here has been measured
      against forward <em>stock returns</em> at all — this orders what already
      broke out, it does not predict.
    </p>
    <ul>
      <li><strong>#</strong> — rank in the current sort.</li>
      <li><strong>Ticker</strong> — symbol + company. Tap a row to open its detail <em>Breakout</em> tab (where each breakout fired on the chart).</li>
      <li><strong># breakouts</strong> — how many <em>distinct, volume-confirmed</em> breakouts over the trailing year: a close above the prior 21-day high on &gt;1.5× the 50-day average volume (Minervini p.203). <strong>⚡</strong> = one was today. <strong>No longer the ranking</strong> — a high count can be a name that has not broken out in months.</li>
      <li><strong>Last</strong> — how long since its most recent breakout (“today”, “3d ago”). “—” = none recorded, and those sort to the BOTTOM in both directions: unknown is not recent. Ties inside a day break on AI-sector rank, so same-day AI-ecosystem breakouts still lead.</li>
      <li><strong>Sales Q/Q · EPS Q/Q</strong> — revenue and diluted EPS, <em>this quarter against last quarter</em>, with the year-over-year number in small grey underneath and the full comparison in the tooltip. Both come from the same weekly research cache the 🔥 Hottest board reads, so the two boards can never disagree; up to a week behind a fresh print.
        <br/><strong>“loss”</strong> is not missing data — it means the company lost money (or broke even) last quarter, so a percentage change would be meaningless: −0.02 → +0.30 would read “+1,600%”. Those rows are never ranked on an invented number. <strong>“≈0”</strong> means last quarter’s figure was a rounding error, which is different from a loss. <strong>“—”</strong> means we do not have two consecutive quarters. <strong>↗</strong> = first profitable quarter after a loss — a real event, but not a growth rate.
        <br/><strong>🔁</strong> = it made a move of the same size and direction at this exact point in its calendar last year, so most of the number is the calendar rather than growth. The tooltip gives last year’s figure and the genuine improvement in points.
        <br/><strong>🚀</strong> = on the Explosive Growth board (100%+ sales AND 100%+ quarterly EPS year-over-year, prior quarter also growing); <strong>🚀⛔</strong> = it qualifies there but the trading engine will refuse to buy it; <strong>✨</strong> = it <em>arrived</em> on that board recently.</li>
      <li><strong>The ranking</strong> — income and growth are blended by <strong>percentile within the whole candidate list</strong>, not by raw percentage, so a single +5,000% EPS print is worth exactly one rank and cannot own the top. Names that <em>actually earned money</em> last quarter rank as a block above names that did not — you cannot prioritise income by ignoring whether there is any. A name with only one of the two legs is ranked on that leg and says so; a name with neither sorts to the bottom, never to the top. The chip shows how many rows could be scored at all.</li>
      <li><strong>Stage gate</strong> — <strong>off by default</strong> since 2026-09-12 (“May show any stage”), so stages 1, 3 and 4 all appear. Tap <strong>✓ S2 only</strong> to bring back the stage-2-plus-explosive-grower gate; it runs on the SERVER before the top-250 cut, so with it on the 250 you see are 250 <em>qualifying</em> names, and the chip says how many it removed. <strong>Read the Stage column.</strong> Fundamentals lag price by up to a quarter, so a name already in stage 4 can still print a superb quarter and rank high here.</li>
      <li><strong>Price</strong> — latest close.</li>
      <li><strong>Δ%</strong> — today’s percent change (green up / red down).</li>
      <li><strong>Vol %</strong> — today’s volume as a % of its 50-day average. <strong>≥150%</strong> (gold) is the 1.5× volume that confirms a breakout (p.203).</li>
      <li><strong>Total Vol</strong> — today’s share volume.</li>
      <li><strong>Conv.</strong> — the momentum-led conviction rank (volume + dried volume + momentum). Buyable names first, then highest conviction. Was the default until 2026-09-12; still one tap away.</li>
      <li><strong>Turnover</strong> — dollar volume traded today (price × volume) — “where the money is.”</li>
      <li><strong>Stage</strong> — Weinstein/Minervini market stage. <strong>✓ S2</strong> (advancing) is the only buyable stage; S4 (decline) = avoid.</li>
      <li><strong>Beta</strong> — 1-year daily volatility vs the market (SPY). <strong>&lt;1</strong> (green) = calmer than the market / lower-volatility; <strong>&gt;1.3</strong> (red) = jumpier. Tap the header to <strong>sort low-volatility first</strong>.</li>
      <li><strong>→ R1/R2</strong> — which trade-plan target (entry +1R / +2R) it’s marching toward, and the % above price to reach it. “Past R2” = extended.</li>
      <li><strong>Verdict</strong> — the combined <strong>Minervini buyable-stock</strong> gate + <strong>Bonde sales</strong> test: PASS / PARTIAL / FAIL. Filter by either side with the chips above. <em>“Verdict pending”</em> = the latest scan hasn’t computed it yet.</li>
    </ul>
    <p className="mono">Display-only. Not investment advice.</p>
  </>
);

const pct = (v?: number | null) => (v != null ? `${v > 0 ? '+' : ''}${v.toFixed(2)}%` : '—');

/* "Scanned Nm ago" from the board's scan timestamp (epoch seconds). */
function scanAgeLabel(ts: number | null): string {
  if (!ts) return 'No scan yet';
  const mins = Math.max(0, Math.round(Date.now() / 1000 / 60 - ts / 60));
  if (mins < 1) return 'Scanned just now';
  if (mins < 60) return `Scanned ${mins}m ago`;
  const h = Math.floor(mins / 60);
  return `Scanned ${h}h ${mins % 60}m ago`;
}

/* Derived metrics — both computed client-side from fields already in the board
 * payload (no backend change). Turnover = price × today's volume (dollar volume
 * traded). Vol % = today's volume as a % of its 50-day average (≥150% is the
 * 1.5× volume-confirmation threshold, Minervini p.203). */
const turnoverOf = (r: BreakoutBoardRow): number | null =>
  r.last_close != null && r.last_vol != null ? r.last_close * r.last_vol : null;
const volPctOf = (r: BreakoutBoardRow): number | null =>
  r.last_vol != null && r.avg_vol_50 ? (r.last_vol / r.avg_vol_50) * 100 : null;

const fmtVol = (n?: number | null): string => {
  if (n == null) return '—';
  const a = Math.abs(n);
  if (a >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${Math.round(n / 1e3)}K`;
  return String(Math.round(n));
};
const fmtDollar = (v?: number | null): string => {
  if (v == null) return '—';
  const a = Math.abs(v);
  if (a >= 1e12) return `$${(v / 1e12).toFixed(1)}T`;
  if (a >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `$${Math.round(v / 1e3)}K`;
  return `$${Math.round(v)}`;
};
const fmtVolPct = (v: number | null): string => (v != null ? `${Math.round(v)}%` : '—');

type Sorter = { toggle: (k: string, p?: SortDir) => void; arrow: (k: string) => string; key: string };

/* Short AI-ecosystem sector chips (Ajay 2026-06-25: breakout list leads with
 * AI-sector winners). Maps backend ai_sector_id → emoji + short label. */
const AI_SECTOR_CHIP: Record<string, string> = {
  ai_chips: '🔌 Chips', memory_hbm: '🔌 Memory', uranium: '⚛️ Nuclear',
  power_grid: '⚡ Power', oil_gas: '🛢 Energy', datacenter_water_cooling: '💧 Cooling',
  grid_equipment: '🔧 Grid', ai_software: '💻 Software', datacenter_reits: '🏢 DC REIT',
  optical_interconnect: '🔗 Optical',
};

/* Sortable header cell — click to sort, click again to flip (delegates to
 * useSort). Active column is gold so the current sort is obvious. */
function Th({ label, k, style, align = 'left', preferred = 'desc', sort }: {
  label: string; k: string; style: CSSProperties;
  align?: 'left' | 'right'; preferred?: SortDir; sort: Sorter;
}) {
  const active = sort.key === k;
  return (
    <span style={{ ...style, display: 'flex', justifyContent: align === 'right' ? 'flex-end' : 'flex-start' }}>
      <button
        type="button"
        onClick={() => sort.toggle(k, preferred)}
        title={`Sort by ${label}`}
        style={{
          font: 'inherit', letterSpacing: 'inherit', textTransform: 'uppercase',
          background: 'none', border: 'none', padding: 0, margin: 0, cursor: 'pointer',
          whiteSpace: 'nowrap', color: active ? 'var(--gold, #c9a227)' : 'inherit',
          fontWeight: active ? 700 : undefined,
        }}
      >
        {label}{sort.arrow(k)}
      </button>
    </span>
  );
}

function Stat({ n, label, tone }: { n: number; label: string; tone?: string }) {
  return (
    <div style={{ textAlign: 'center', minWidth: 76 }}>
      <div style={{ fontSize: '1.3rem', fontWeight: 800, color: tone || 'var(--ink, #eee)' }}>{n}</div>
      <div style={{ fontSize: '0.62rem', color: 'var(--cm-slate, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{label}</div>
    </div>
  );
}

export function BreakoutsPage() {
  /* Ajay 2026-09-12, second word on the same day: "May show any stage but
     prioritize income and growth only quarter over quarter."

     So the stage gate is OFF by default — every stage shows — and the RANKING
     is income + growth measured quarter over quarter. Both run on the SERVER,
     before the top-N cut: ranking the already-cut 250 would reorder a list that
     had already thrown the answer away, the same mistake the count-ranked cut
     made with recency this morning. The gate is still one tap away. */
  const [stageGate, setStageGate] = useState(false);
  const [rankMode, setRankMode] = useState<'qoq' | 'recent'>('qoq');
  const { rows, summary, scanTs, loading, error, reload, stageInfo: rawStage,
          rankInfo: rawRank } = useBreakoutBoard(250, 1, stageGate, rankMode);
  // Defensive: an older/mocked hook may not carry it, and a missing count must
  // never blank the board.
  const stageInfo = rawStage ?? { on: false, dropped: 0, qualifying: 0, scanned: 0 };
  // Defensive PER FIELD, not per object. `rawRank ?? {...}` only fires when the
  // whole thing is undefined, so an older hook — or a payload from a server
  // that has not been redeployed yet — hands over a PARTIAL object and every
  // `.toLocaleString()` throws, blanking the entire board. That exact shape
  // crashed this page once already today on `stageInfo`; a count nobody has is
  // a zero, never a white screen.
  const n = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : 0);
  const rankInfo = {
    sort: rawRank?.sort === 'recent' ? ('recent' as const) : ('qoq' as const),
    scored: n(rawRank?.scored), income: n(rawRank?.income),
    growth: n(rawRank?.growth), seasonalBasis: n(rawRank?.seasonalBasis),
    seasonalEcho: n(rawRank?.seasonalEcho), total: n(rawRank?.total),
  };
  const [filter, setFilter] = useState<FilterKey>('all');
  // Base-only is ON by default (Ajay 2026-06-22): hide bare breakouts that have
  // no detected base; keep VCP / Power Play / pocket pivot. Toggle off to widen.
  const [baseOnly, setBaseOnly] = useState(true);
  // Fresh-only is ON by default (Ajay 2026-06-23, "do not show me the ones with
  // r2"): hide names that have already cleared R1 and are marching to / past R2
  // — extended, no longer a fresh breakout. Keeps the board breakout-focused.
  const [freshOnly, setFreshOnly] = useState(true);

  // Dynamic re-scan (Ajay 2026-06-18). "Refresh" just re-pulls the latest scan
  // (instant, reuses what the cron / other pages already scanned). "Update" runs
  // a FAST scan (~30s) — joins cached research with today's prices over the broad
  // universe — NOT an expensive full scan — then re-pulls. mode:'broad' matches
  // the board's universe so the scan never shrinks it.
  const scan = useSepaScanStream();
  useEffect(() => {
    if (scan.phase === 'done') { reload(); scan.reset(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scan.phase]);

  const shown = useMemo(() => {
    const f = FILTERS.find((x) => x.key === filter) ?? FILTERS[0];
    return rows
      .filter(f.match)
      .filter((r) => !baseOnly || isBaseSetup(r.setup_type))
      .filter((r) => !freshOnly || !isExtendedToR2(r.last_close, r.r1, r.r2));
  }, [rows, filter, baseOnly, freshOnly]);

  // Client-side sort over the filtered list. Default (Ajay 2026-06-22):
  // CONVICTION — Enter-eligible (is_buyable) names first, then by the momentum-
  // led conviction rank (volume + dried volume + momentum, backend
  // sepa/conviction.py). Climax names are suppressed in the conviction number so
  // they sink. Composite key = is_buyable*1e9 + conviction (1e9 dominates a
  // 0-100 conviction yet stays exact under 2^53). The prior buyable+turnover
  // sort is KEPT as a column. Every column is still sortable via its header.
  const sort = useSort<BreakoutBoardRow>(shown, {
    ticker: (r) => r.symbol,
    count: (r) => r.breakout_count,
    last: (r) => r.days_since_breakout,
    sales: (r) => r.sales_yoy ?? null,
    eps: (r) => r.q_eps_yoy ?? null,
    // SEQUENTIAL quarter-over-quarter (Ajay 2026-09-12). `useSort` sinks nulls
    // in BOTH directions, which is what a refused ratio needs: a name that lost
    // money last quarter has no percentage, and "no percentage" must never
    // outrank a measured decline.
    growthq: (r) => r.growth_qoq ?? null,
    incomeq: (r) => r.income_qoq ?? null,
    // The ranking itself: percentile blend of both legs, with names that
    // actually EARNED money last quarter as a block on top — you cannot
    // prioritise income by ignoring whether there is any.
    qoq: (r) => (r.qoq_score == null ? null
                 : (r.income_qoq != null ? 1e6 : 0) + r.qoq_score),
    price: (r) => r.last_close,
    change: (r) => r.day_change_pct,
    volpct: volPctOf,
    volume: (r) => r.last_vol,
    turnover: turnoverOf,
    stage: (r) => r.stage,
    beta: (r) => r.beta,
    march: (r) => marchToTarget(r.last_close, r.r1, r.r2).pct,
    buyable: (r) => (r.is_buyable ? 1e15 : 0) + (turnoverOf(r) || 0),
    conviction: (r) => (r.is_buyable ? 1e9 : 0) + (r.conviction ?? 0),
    // AI-sector priority (Ajay 2026-06-25): AI-ecosystem winners first — by
    // sector rank (chips→energy/nuclear→water-cooling→grid→software→…), then
    // buyable + conviction within. Non-AI names sink below. See lib/breakoutSort.
    sector: aiSectorSortValue,
    // 🚀 membership first, then the EPS number inside it — a 100/100 grower
    // breaking out is the row worth reading twice.
    explosive: (r) => (r.explosive ? 1e9 : 0) + (r.q_eps_yoy ?? 0),
    // RECENT FIRST is the default now (Ajay 2026-09-12: "Sort it by recent
    // breakout instead of # of breakouts"). `useSort` sinks nulls in both
    // directions, so a name with no recorded breakout date stays at the bottom.
    //
    // HIS 2026-06-25 STANDING RULE IS NOT DROPPED, it moved INSIDE the day: the
    // server now orders by recency and breaks ties on AI-sector rank, so
    // same-day AI-ecosystem breakouts still lead. The 'sector' sort is kept as
    // a column if he wants it back wholesale.
  }, 'qoq', 'desc');

  return (
    <div className="sepa-page">
      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">Breakouts</div>
          <h1 className="display sepa-page__h1" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            🚀 Breakouts
            <InfoButton inline title="Breakouts">{PageInfo}</InfoButton>
            <NewBadge id="breakouts-beta" label="Beta column + sort by low volatility" />
          </h1>
          <p className="lede">
            Every name that's broken out, ranked by <strong>income and growth,
            quarter over quarter</strong> — the quarter just ended against the one
            before it. Each carries the <strong>Minervini + Bonde</strong> verdict,
            so you can see which breakouts pass the book and which don't. Every
            stage shows; the Stage column tells you which.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span
            style={{ fontSize: '0.66rem', color: 'var(--cm-slate)' }}
            title={scanTs ? new Date(scanTs * 1000).toLocaleString() : 'no scan yet'}
          >
            {scan.scanning ? (scan.phaseMessage || 'Scanning…') : scanAgeLabel(scanTs)}
          </span>
          <button
            className="sepa-btn sepa-btn--ghost"
            onClick={reload}
            disabled={loading || scan.scanning}
            title="Re-pull the latest scan — instant, reuses what's already been scanned"
          >
            {loading ? '↻ …' : '↻ Refresh'}
          </button>
          <button
            className="sepa-btn"
            onClick={() => scan.start({ fast: true, mode: 'broad' })}
            disabled={scan.scanning}
            title="Fast re-scan (~30s) — reuses cached research + today's prices over the full universe, not an expensive full scan"
          >
            {scan.scanning ? '⟳ Updating…' : '⟳ Update'}
          </button>
        </div>
      </div>

      {/* Breakout breadth — the book's market thermometer (exposure guidance
          only, never an entry gate — TLSW p.164/165/303/307) */}
      <BreakoutBreadthStrip />

      {/* Summary mix — the "some pass, some don't" read at a glance */}
      {summary && (
        <div style={{
          display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'center',
          border: '1px solid var(--rule, #2a2a2a)', borderRadius: 8, padding: '0.7rem 1rem',
          margin: '0.4rem 0 0.9rem', background: 'var(--bg-raised, #181818)',
        }}>
          <Stat n={summary.total} label="breakouts" />
          <Stat n={summary.broke_out_today} label="today" tone="#eab308" />
          <Stat n={summary.buyable} label="🎯 buyable" tone="#10b981" />
          <Stat n={summary.both_pass} label="M + Bonde" tone="#10b981" />
          <Stat n={summary.minervini_pass} label="Minervini ✓" tone="#34d399" />
          <Stat n={summary.minervini_fail} label="Minervini ✗" tone="#f87171" />
          <Stat n={summary.bonde_pass} label="Bonde ✓" tone="#34d399" />
          <Stat n={summary.bonde_fail} label="Bonde ✗" tone="#f87171" />
        </div>
      )}

      {/* Filter chips */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: '0.8rem' }}>
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`sepa-chip ${filter === f.key ? 'is-active' : ''}`}
            title={f.tip}
            onClick={() => setFilter(f.key)}
            style={{
              cursor: 'pointer', fontSize: '0.74rem',
              ...(filter === f.key ? { borderColor: 'var(--gold, #c9a227)', color: 'var(--gold, #c9a227)', fontWeight: 700 } : {}),
            }}
          >
            {f.label}
          </button>
        ))}
        {/* THE RANKING (Ajay 2026-09-12: "prioritize income and growth only
            quarter over quarter"). A server round-trip, like the stage chip: the
            order decides which 250 of 2,840 candidates survive the cut, so it
            cannot be a client-side re-sort. Says how much of the board could
            actually be ranked — a board ordered by income where most names have
            no income has to admit it. */}
        <button
          className={`sepa-chip ${rankMode === 'qoq' ? 'is-active' : ''}`}
          title={rankMode === 'qoq'
            ? `Ranked by INCOME + GROWTH, quarter over quarter — this quarter against the one before it, both legs blended by PERCENTILE so one +5,000% print cannot own the top. Names that actually earned money last quarter rank as a block above those that did not. ${rankInfo.seasonalBasis.toLocaleString()} of ${rankInfo.total.toLocaleString()} rows are ranked against their OWN prior-year transition rather than against zero, which is what stops a refiner's ordinary strong quarter reading as an earnings explosion; 🔁 marks the ${rankInfo.seasonalEcho.toLocaleString()} rows making a move they make every year. ${rankInfo.income.toLocaleString()} rows have an EPS number, ${rankInfo.growth.toLocaleString()} a revenue number, ${rankInfo.scored.toLocaleString()} could be scored at all. Tap for most-recent-breakout order.`
            : 'Ranked by most recent breakout. Tap to rank by income + growth, quarter over quarter.'}
          onClick={() => setRankMode((m) => (m === 'qoq' ? 'recent' : 'qoq'))}
          style={{
            cursor: 'pointer', fontSize: '0.74rem',
            ...(rankMode === 'qoq' ? { borderColor: 'var(--gold, #c9a227)', color: 'var(--gold, #c9a227)', fontWeight: 700 } : {}),
          }}
        >
          {rankMode === 'qoq'
            ? `📈 Income + growth Q/Q (${rankInfo.scored.toLocaleString()}/${rankInfo.total.toLocaleString()})`
            : '🕑 Most recent'}
        </button>
        {/* Stage gate (Ajay 2026-09-12: "From the breakout remove any S3. Only S2
            stocks and if thy have explosive growth its ok to have s1 and s3"),
            then OFF the same day ("May show any stage"). Kept one tap away.
            Unlike the chips beside it this one is a SERVER round-trip: the gate
            runs before the top-250 cut, so turning it on re-ranks 2,840
            candidates rather than hiding 250 already-cut rows. */}
        <button
          className={`sepa-chip ${stageGate ? 'is-active' : ''}`}
          title={stageGate
            ? `Stage 2 only — plus an explosive grower at stage 1 or 3. Stage 4 is never kept. ${stageInfo.dropped.toLocaleString()} of ${stageInfo.scanned.toLocaleString()} breakouts removed; ${stageInfo.qualifying.toLocaleString()} qualify. Tap to show every stage.`
            : 'Showing EVERY stage, including 3 and 4. Tap to keep stage 2 only (plus explosive growers at 1/3).'}
          onClick={() => setStageGate((b) => !b)}
          style={{
            cursor: 'pointer', fontSize: '0.74rem',
            ...(stageGate ? { borderColor: 'var(--gold, #c9a227)', color: 'var(--gold, #c9a227)', fontWeight: 700 } : {}),
          }}
        >
          ✓ S2 only{stageGate && stageInfo.dropped > 0
            ? ` (−${stageInfo.dropped.toLocaleString()})` : ''}
        </button>
        {/* Base-only toggle (Ajay 2026-06-22) — ANDs with the filter above; ON by
            default so bare breakouts (no base) are hidden. */}
        <button
          className={`sepa-chip ${baseOnly ? 'is-active' : ''}`}
          title="Show only real-base breakouts (VCP / Power Play / pocket pivot) and hide bare breakouts that have no detected base (Minervini pp.198-205). On by default — tap to show all."
          onClick={() => setBaseOnly((b) => !b)}
          style={{
            cursor: 'pointer', fontSize: '0.74rem',
            ...(baseOnly ? { borderColor: 'var(--gold, #c9a227)', color: 'var(--gold, #c9a227)', fontWeight: 700 } : {}),
          }}
        >
          🧱 Base only
        </button>
        {/* Fresh-only toggle (Ajay 2026-06-23) — hide names already marching to /
            past R2 (extended); keep the board to fresh, near-entry breakouts. ON
            by default. */}
        <button
          className={`sepa-chip ${freshOnly ? 'is-active' : ''}`}
          title="Hide names that have already cleared their 1st target (→ R2 / Past R2) — extended, no longer a fresh breakout. On by default — tap to show extended names too."
          onClick={() => setFreshOnly((b) => !b)}
          style={{
            cursor: 'pointer', fontSize: '0.74rem',
            ...(freshOnly ? { borderColor: 'var(--gold, #c9a227)', color: 'var(--gold, #c9a227)', fontWeight: 700 } : {}),
          }}
        >
          🌱 Fresh only
        </button>
        {/* Explicit sort selector (Ajay 2026-08-03: "sort option volume") —
            same state as the clickable column headers, just discoverable.
            Volume options lead since that was the ask. */}
        <label style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center',
                        gap: 6, fontSize: '0.72rem', color: 'var(--cm-slate, #94a3b8)' }}>
          Sort
          <select
            aria-label="Sort breakouts"
            value={sort.key}
            onChange={(e) => sort.toggle(e.target.value, 'desc')}
            style={{ padding: '0.22rem 0.5rem', borderRadius: 8, fontSize: '0.74rem',
                     border: '1px solid var(--cm-border, #2a2f3a)',
                     background: 'var(--cm-card, #161a22)', color: 'inherit' }}
          >
            <option value="sector">🤖 AI sectors (default)</option>
            <option value="volume">📊 Today's volume</option>
            <option value="volpct">📈 Volume vs normal (×)</option>
            <option value="turnover">💵 $ turnover</option>
            <option value="conviction">🏆 Conviction</option>
            <option value="count">🔁 Breakout count</option>
            <option value="change">⚡ % change today</option>
          </select>
        </label>
      </div>

      {error && <p className="sepa-err">Couldn't load breakouts: {error}</p>}
      {loading && rows.length === 0 && <ListSkeleton rows={10} label="🚀 Breakouts" />}

      {!loading && rows.length === 0 && !error && (
        <div className="sepa-empty">
          <p>No breakouts in the latest scan yet. They populate after a scan runs
          (a fresh scan computes each name's breakout count + verdict).</p>
        </div>
      )}

      {shown.length > 0 && (
        <>
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 6, marginBottom: 6 }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--cm-slate, #94a3b8)' }}>What do these columns mean?</span>
          <InfoButton inline align="right" title="Breakout columns">{ColumnsInfo}</InfoButton>
        </div>
        <div
          className="breakouts-scroll"
          data-testid="breakouts-scroll"
          style={{
            overflowX: 'auto',
            // Momentum scroll + don't let a horizontal swipe rubber-band the
            // whole page on phones (the table is wider than the viewport, so
            // it must scroll on its own — Ajay 2026-06-16 mobile fix).
            WebkitOverflowScrolling: 'touch',
            overscrollBehaviorX: 'contain',
          }}
        >
          <div className="breakouts-table" role="table" style={{ minWidth: 1200 }}>
            <div className="breakouts-row breakouts-row--head" role="row" style={headRow}>
              <span style={{ width: 36 }}>#</span>
              <Th label="Ticker" k="ticker" style={colTicker} preferred="asc" sort={sort} />
              <Th label="Conv." k="conviction" style={colConviction} align="right" sort={sort} />
              <Th label="# breakouts" k="count" style={colCount} sort={sort} />
              <Th label="Last" k="last" style={colLast} preferred="asc" sort={sort} />
              <Th label="Sales Q/Q" k="growthq" style={colSales} align="right" sort={sort} />
              <Th label="EPS Q/Q" k="incomeq" style={colEps} align="right" sort={sort} />
              <Th label="Price" k="price" style={colPrice} align="right" sort={sort} />
              <Th label="Δ%" k="change" style={colChg} align="right" sort={sort} />
              <Th label="Vol %" k="volpct" style={colVolPct} align="right" sort={sort} />
              <Th label="Total Vol" k="volume" style={colVol} align="right" sort={sort} />
              <Th label="Turnover" k="turnover" style={colTurnover} align="right" sort={sort} />
              <Th label="Stage" k="stage" style={colStage} sort={sort} />
              <Th label="Beta" k="beta" style={colBeta} align="right" preferred="asc" sort={sort} />
              <Th label="→ R1/R2" k="march" style={colMarch} preferred="asc" sort={sort} />
              <span style={colVerdict}>verdict</span>
            </div>
            {sort.sorted.map((r, i) => {
              const to = turnoverOf(r);
              const vp = volPctOf(r);
              return (
                <Link
                  key={r.symbol}
                  /* No ?tab= — relies on the page default, Supply / Demand
                   * (Ajay 2026-09-03: "in all pages"). Was ?tab=breakout. */
                  to={`/sepa/${r.symbol}`}
                  className="breakouts-row"
                  role="row"
                  style={dataRow}
                >
                  <span style={{ width: 36, color: 'var(--cm-slate)', fontWeight: 700 }}>{i + 1}</span>
                  <span style={{ ...colTicker, display: 'flex', flexDirection: 'column' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                      <strong className="mono">{r.symbol}</strong>
                      <LeveragedBadge symbol={r.symbol} name={r.name} compact />
                      {(() => {
                        /* Setup badge (Ajay 2026-08-03: "show if something
                           had a vcp") — 📐 VCP / ⚡ PP / 🎯 pocket pivot. */
                        const sb = setupBadge(r.setup_type);
                        return sb ? (
                          <span title={sb.title}
                            style={{ fontSize: '0.58rem', fontWeight: 800, color: 'var(--cm-cyan, #38bdf8)',
                              border: '1px solid rgba(56,189,248,0.45)', background: 'rgba(56,189,248,0.10)',
                              borderRadius: 5, padding: '0 4px', whiteSpace: 'nowrap', cursor: 'help' }}>
                            {sb.icon} {sb.label}
                          </span>
                        ) : null;
                      })()}
                      {r.ai_sector_id && (
                        <span title={`AI-ecosystem sector: ${r.ai_sector}${r.ai_sector_etf ? ` · ETF ${r.ai_sector_etf}` : ''} — these lead the breakout list`}
                          style={{ fontSize: '0.58rem', fontWeight: 800, color: 'var(--gold,#c9a227)',
                            border: '1px solid rgba(201,162,39,0.5)', background: 'rgba(201,162,39,0.12)',
                            borderRadius: 5, padding: '0 4px', whiteSpace: 'nowrap' }}>
                          {AI_SECTOR_CHIP[r.ai_sector_id] ?? r.ai_sector}
                        </span>
                      )}
                      {r.is_buyable ? (
                        <span title="Buyable now — clears the strict Minervini buy gate (is_buyable), same as the SEPA scan's 🟢 Enter"
                          style={{ fontSize: '0.6rem', fontWeight: 800, color: '#10b981',
                            border: '1px solid rgba(16,185,129,0.45)', background: 'rgba(16,185,129,0.12)',
                            borderRadius: 5, padding: '0 4px', whiteSpace: 'nowrap' }}>🎯 BUYABLE</span>
                      ) : r.setup_ready && r.setup_note?.kind === 'extended' ? (
                        <span title={`Broke out, but closed +${r.setup_note.ext_pct}% past the ${r.setup_note.pivot != null ? `$${r.setup_note.pivot} ` : ''}pivot — too far to chase (Minervini, TLSW p.224). Held out of the buy tier; wait for a pullback toward the pivot before entering.`}
                          style={{ fontSize: '0.6rem', fontWeight: 800, color: '#f59e0b',
                            border: '1px solid rgba(245,158,11,0.5)', background: 'rgba(245,158,11,0.12)',
                            borderRadius: 5, padding: '0 4px', whiteSpace: 'nowrap' }}>
                          ⏸ EXTENDED +{r.setup_note.ext_pct}% · wait for pullback{r.setup_note.pivot != null ? ` → $${r.setup_note.pivot}` : ''}
                        </span>
                      ) : r.setup_ready ? (
                        <span title="Set up, waiting for the trigger (setup_ready) — one volume-confirmed breakout away from buyable"
                          style={{ fontSize: '0.6rem', fontWeight: 700, color: '#eab308',
                            border: '1px solid rgba(234,179,8,0.4)', background: 'rgba(234,179,8,0.10)',
                            borderRadius: 5, padding: '0 4px', whiteSpace: 'nowrap' }}>SETUP</span>
                      ) : null}
                    </span>
                    {r.name && <span style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 160 }}>{r.name}</span>}
                  </span>
                  <span
                    className="mono"
                    style={colConviction}
                    title={
                      r.conviction_detail
                        ? (r.conviction_detail.suppressed
                            ? `Conviction suppressed — ${r.conviction_detail.suppress_reason}`
                            : `Conviction ${r.conviction} · led by ${r.conviction_detail.lead} — momentum ${r.conviction_detail.legs.momentum} / coil ${r.conviction_detail.legs.coil} / demand ${r.conviction_detail.legs.demand} / R:R ${r.conviction_detail.legs.reward_risk}. Volume + dried volume + momentum (TLSW p.34/79).`)
                        : 'Momentum-led conviction rank — volume + dried volume + momentum (TLSW p.34/79)'
                    }
                  >
                    {r.conviction != null ? (
                      <span style={{ fontWeight: 800, color: r.conviction_detail?.suppressed ? '#f87171' : r.is_buyable ? '#10b981' : 'var(--ink, #eee)' }}>
                        {Math.round(r.conviction)}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--cm-slate)' }}>—</span>
                    )}
                  </span>
                  <span style={colCount}>
                    <span style={{ fontWeight: 800, fontSize: '1.05rem' }}>{r.breakout_count}</span>
                    {r.broke_out_today && <span title="Broke out today" style={{ marginLeft: 5, color: '#eab308' }}>⚡</span>}
                  </span>
                  <span style={{ ...colLast, color: 'var(--cm-slate)', fontSize: '0.74rem' }}>
                    {r.broke_out_today ? 'today' : r.days_since_breakout != null ? `${r.days_since_breakout}d ago` : '—'}
                  </span>
                  {/* Sequential quarter-over-quarter leads, year-over-year sits
                      under it as the check (Ajay 2026-09-12). Two columns, not
                      four: the table already carries sixteen, and repurposing
                      beats appending. A blank is an em-dash, never a zero, and a
                      REFUSED ratio says which refusal it was — "lost money last
                      quarter" is a fact, not a gap in our data. */}
                  <span className="mono" style={{ ...colSales, fontSize: '0.74rem',
                        color: qoqColor(r.growth_qoq) }}
                        title={qoqTitle('Revenue', r.growth_qoq, r.growth_base, r.sales_yoy)}>
                    {qoqText(r.growth_qoq, r.growth_base)}
                    {r.seasonal_echo && (
                      <span title={`It moved the same way at this point in its calendar last year too (${r.growth_qoq_ly != null ? `${r.growth_qoq_ly >= 0 ? '+' : ''}${r.growth_qoq_ly.toFixed(0)}%` : 'same direction'}), so most of this is the calendar, not growth. Genuine improvement over its own seasonal norm: ${r.growth_vs_seasonal != null ? `${r.growth_vs_seasonal >= 0 ? '+' : ''}${r.growth_vs_seasonal.toFixed(0)} points` : 'unknown'}. The ranking already uses that difference — this badge is why the row may sit lower than its big number suggests.`}
                            style={{ marginLeft: 3, opacity: 0.85 }}>🔁</span>
                    )}
                    <span style={{ display: 'block', fontSize: '0.6rem', color: 'var(--cm-slate)' }}>
                      {r.sales_yoy == null ? 'y/y —' : `y/y ${r.sales_yoy >= 0 ? '+' : ''}${r.sales_yoy.toFixed(0)}%`}
                    </span>
                  </span>
                  <span className="mono" style={{ ...colEps, fontSize: '0.74rem',
                        color: qoqColor(r.income_qoq) }}
                        title={qoqTitle('EPS', r.income_qoq, r.income_base, r.q_eps_yoy, r.income_turn)}>
                    {qoqText(r.income_qoq, r.income_base)}
                    {r.income_turn === 'to_profit' && (
                      <span title="First profitable quarter after a loss. A real event — but not a growth percentage, and it never competes as one."
                            style={{ marginLeft: 3 }}>↗</span>
                    )}
                    <span style={{ display: 'block', fontSize: '0.6rem', color: 'var(--cm-slate)' }}>
                      {r.q_eps_yoy == null ? 'y/y —' : `y/y ${r.q_eps_yoy >= 0 ? '+' : ''}${r.q_eps_yoy.toFixed(0)}%`}
                    </span>
                    {r.explosive && r.explosive_new && (
                      <span title="✨ NEWLY found on the Explosive Growth board — it arrived there recently, rather than having sat on it for months."
                            style={{ marginLeft: 4 }}>✨</span>
                    )}
                    {r.explosive && (
                      <span title={r.explosive_refused
                        ? '🚀 On the Explosive Growth board (100% sales AND 100% quarterly EPS) — but the trading engine REFUSES this one (under $2, or a known cap under $700M).'
                        : '🚀 On the Explosive Growth board: 100%+ sales AND 100%+ quarterly EPS year-over-year, with the prior quarter also growing.'}
                            style={{ marginLeft: 4 }}>
                        🚀{r.explosive_refused ? '⛔' : ''}
                      </span>
                    )}
                  </span>
                  <span className="mono" style={colPrice}>
                    {r.last_close != null ? `${r.last_close.toFixed(2)}` : '—'}
                  </span>
                  <span
                    className="mono"
                    style={{ ...colChg, fontSize: '0.74rem', color: r.day_change_pct == null ? 'var(--cm-slate)' : r.day_change_pct >= 0 ? 'var(--positive, #10b981)' : 'var(--negative, #f87171)' }}
                  >
                    {pct(r.day_change_pct)}
                  </span>
                  <span
                    className="mono"
                    title={vp != null ? 'Today’s volume vs its 50-day average (≥150% = the 1.5× breakout threshold, p.203)' : undefined}
                    style={{ ...colVolPct, fontSize: '0.78rem', color: vp != null && vp >= 150 ? 'var(--gold, #c9a227)' : 'var(--ink, #eee)', fontWeight: vp != null && vp >= 150 ? 700 : 400 }}
                  >
                    {fmtVolPct(vp)}
                  </span>
                  <span className="mono" style={{ ...colVol, color: 'var(--cm-slate)' }}>{fmtVol(r.last_vol)}</span>
                  <span className="mono" title="Dollar volume traded today (price × volume)" style={{ ...colTurnover, fontWeight: 600 }}>{fmtDollar(to)}</span>
                  {(() => {
                    // Stage — Weinstein/Minervini stage analysis. Stage 2 (the
                    // advancing phase) is the only buyable stage; ✓ + green.
                    const sm = stageMeta(r.stage, r.stage_label);
                    return (
                      <span
                        style={{ ...colStage, fontSize: '0.74rem', color: sm.tone, fontWeight: sm.isStage2 ? 700 : 400 }}
                        title={sm.isStage2 ? 'Stage 2 — the advancing phase (the only buyable stage, Minervini/Weinstein)' : sm.label}
                      >
                        {sm.isStage2 ? `✓ S2` : (r.stage != null ? `S${r.stage}` : '—')}
                      </span>
                    );
                  })()}
                  {(() => {
                    // Beta — 1y daily volatility vs SPY. <1 = calmer than the
                    // market (green/low-vol); >1.3 = jumpy (red). Sort ascending
                    // to surface the low-volatility breakouts.
                    const b = r.beta;
                    const tone =
                      b == null ? 'var(--cm-slate, #94a3b8)' :
                      b < 1 ? 'var(--positive, #10b981)' :
                      b > 1.3 ? 'var(--negative, #f87171)' : 'var(--ink, #eee)';
                    return (
                      <span
                        className="mono"
                        style={{ ...colBeta, fontSize: '0.78rem', color: tone }}
                        title={b == null ? 'Beta unavailable (need ~1yr of history)'
                          : `1-year daily beta vs SPY — ${b < 1 ? 'less' : 'more'} volatile than the market`}
                      >
                        {b == null ? '—' : b.toFixed(2)}
                      </span>
                    );
                  })()}
                  {(() => {
                    // Marching toward R1/R2 — distance (%) above current price to
                    // the next trade-plan target (entry+1R / +2R).
                    const m = marchToTarget(r.last_close, r.r1, r.r2);
                    const tone =
                      m.state === 'to_r1' ? 'var(--positive, #10b981)' :
                      m.state === 'to_r2' ? 'var(--gold, #c9a227)' :
                      m.state === 'past_r2' ? '#eab308' : 'var(--cm-slate, #94a3b8)';
                    const text =
                      m.pct != null ? `${m.label} ${pct(m.pct)}` :
                      m.state === 'past_r2' ? '⚠ Past R2' : '—';
                    return (
                      <span
                        className="mono"
                        style={{ ...colMarch, fontSize: '0.74rem', color: tone }}
                        title={
                          m.state === 'past_r2' ? 'Extended past both R1 and R2 targets'
                          : m.pct != null ? `${(m.toR1Pct != null ? `R1 ${pct(m.toR1Pct)}` : '')}  ${(m.toR2Pct != null ? `R2 ${pct(m.toR2Pct)}` : '')}`.trim()
                          : 'No trade-plan targets on this row'
                        }
                      >
                        {text}
                      </span>
                    );
                  })()}
                  <span style={colVerdict}>
                    {r.is_etf ? (
                      <span style={{ fontSize: '0.72rem', color: 'var(--cm-slate)' }}>ETF — no Minervini verdict</span>
                    ) : r.buy_verdict ? (
                      <BuyVerdictChip row={r} />
                    ) : (
                      <span style={{ fontSize: '0.72rem', color: 'var(--cm-slate)' }}>verdict pending</span>
                    )}
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
        </>
      )}

      {!loading && shown.length === 0 && rows.length > 0 && (
        <div className="sepa-empty"><p>No breakouts match this filter. Try “All breakouts”.</p></div>
      )}

      <div style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', marginTop: '0.8rem', lineHeight: 1.5 }}>
        Breakout = close above the prior 21-day high on &gt;1.5× the 50-day average volume
        (Minervini, <em>Trade Like a Stock Market Wizard</em>, p.203). Verdict combines that
        buyable-stock gate with Pradeep Bonde / Stockbee's sales test — see
        <code> docs/sepa/buyable_verdict_methodology.md</code>. Display-only.
      </div>
    </div>
  );
}

const headRow: CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, padding: '0.3rem 0.6rem',
  fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: '0.05em',
  color: 'var(--cm-slate, #94a3b8)', borderBottom: '1px solid var(--rule, #2a2a2a)',
};
const dataRow: CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, padding: '0.5rem 0.6rem',
  borderBottom: '1px solid var(--rule, #1f1f1f)', textDecoration: 'none',
  color: 'var(--ink, #eee)',
};
const colTicker: CSSProperties = { flex: '1 1 120px', minWidth: 110 };
const colCount: CSSProperties = { width: 96, textAlign: 'left' };
const colConviction: CSSProperties = { width: 64, textAlign: 'right' };
const colLast: CSSProperties = { width: 68 };
// EPS + explosive growth (Ajay 2026-09-12) — narrow, right-aligned numerics.

/* ── Sequential quarter-over-quarter rendering (Ajay 2026-09-12) ───────────
 * The board must never print a percentage it does not have, and must never
 * print "—" for two different reasons. `growth_base`/`income_base` say WHICH:
 *   non_positive — it lost money (or broke even) last quarter, so (now−then)/then
 *                  is meaningless; -0.02 → +0.30 would read "+1,600%"
 *   too_small    — it earned a rounding error; the ratio is noise
 *   unknown      — we do not have the two quarters
 * Each gets its own glyph so a reader can tell a fact from a gap. */
function qoqColor(v?: number | null): string {
  if (v == null) return 'var(--cm-slate)';
  return v >= 0 ? 'var(--positive, #10b981)' : 'var(--negative, #f87171)';
}
function qoqText(v?: number | null, base?: string | null): string {
  if (v != null) return `${v >= 0 ? '+' : ''}${v.toFixed(0)}%`;
  if (base === 'non_positive') return 'loss';
  if (base === 'too_small') return '≈0';
  return '—';
}
function qoqTitle(what: string, v?: number | null, base?: string | null,
                  yoy?: number | null, turn?: string | null): string {
  const yy = yoy == null ? 'no year-over-year number' :
    `${yoy >= 0 ? '+' : ''}${yoy.toFixed(1)}% vs the same quarter a year ago`;
  let head: string;
  if (v != null) {
    head = `${what} ${v >= 0 ? '+' : ''}${v.toFixed(1)}% vs LAST quarter.`;
  } else if (base === 'non_positive') {
    head = `${what} was negative or zero last quarter, so a percentage change would be meaningless — a swing from −0.02 to +0.30 reads as "+1,600%". No percentage is shown and this row is not ranked on one.`;
  } else if (base === 'too_small') {
    head = `${what} last quarter was too near zero to carry a ratio. Not a loss — a rounding error.`;
  } else {
    head = `No two consecutive quarters on file for ${what.toLowerCase()}.`;
  }
  const t = turn === 'to_profit' ? ' First profitable quarter after a loss.'
    : turn === 'narrowing' ? ' Still a loss, but a narrowing one.'
    : turn === 'to_loss' ? ' Profitable a quarter ago, at a loss now.' : '';
  return `${head}${t} Year-over-year: ${yy}. The two comparisons disagree often — measured Spearman 0.58 on revenue, 0.37 on EPS.`;
}

const colSales: CSSProperties = { width: 72 };
const colEps: CSSProperties = { width: 84 };
const colPrice: CSSProperties = { width: 76, textAlign: 'right' };
const colChg: CSSProperties = { width: 70, textAlign: 'right' };
const colVolPct: CSSProperties = { width: 80, textAlign: 'right' };
const colVol: CSSProperties = { width: 82, textAlign: 'right' };
const colTurnover: CSSProperties = { width: 96, textAlign: 'right' };
const colStage: CSSProperties = { width: 62 };
const colBeta: CSSProperties = { width: 60, textAlign: 'right' };
const colMarch: CSSProperties = { width: 104 };
const colVerdict: CSSProperties = { flex: '2 1 220px', minWidth: 200 };
