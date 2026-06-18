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
import { useMemo, useState, type CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import { useBreakoutBoard, type BreakoutBoardRow } from '../hooks/useBreakoutBoard';
import { useSort, type SortDir } from '../lib/useSort';
import { marchToTarget, stageMeta } from '../lib/breakoutTargets';
import { BuyVerdictChip } from '../components/BuyVerdictChip';
import { ListSkeleton } from '../components/Skeletons';
import { InfoButton } from '../components/InfoButton';

type FilterKey = 'all' | 'today' | 'minervini_pass' | 'minervini_fail' | 'bonde_pass' | 'bonde_fail' | 'both_pass';

const mPass = (r: BreakoutBoardRow) => r.buy_verdict?.minervini?.passed === true;
const mFail = (r: BreakoutBoardRow) => r.buy_verdict?.minervini?.passed === false;
const bPass = (r: BreakoutBoardRow) => r.buy_verdict?.bonde?.passed === true;
const bFail = (r: BreakoutBoardRow) => r.buy_verdict?.bonde?.passed === false;

const FILTERS: { key: FilterKey; label: string; tip: string; match: (r: BreakoutBoardRow) => boolean }[] = [
  { key: 'all',            label: 'All breakouts',  tip: 'Every name with ≥1 volume-confirmed breakout, ranked by count.', match: () => true },
  { key: 'today',          label: '⚡ Broke out today', tip: 'Cleared its pivot on volume TODAY (days since breakout = 0).', match: (r) => r.broke_out_today },
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
      <li><strong># breakouts</strong> — count of distinct volume-confirmed breakouts. Highest first.</li>
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
      a header, tap again to flip. Default sort is <strong>Turnover</strong>, highest first.
    </p>
    <ul>
      <li><strong>#</strong> — rank in the current sort.</li>
      <li><strong>Ticker</strong> — symbol + company. Tap a row to open its detail <em>Breakout</em> tab (where each breakout fired on the chart).</li>
      <li><strong># breakouts</strong> — how many <em>distinct, volume-confirmed</em> breakouts over the trailing year: a close above the prior 21-day high on &gt;1.5× the 50-day average volume (Minervini p.203). <strong>⚡</strong> = one was today. This is the headline ranking.</li>
      <li><strong>Last</strong> — how long since its most recent breakout (“today”, “3d ago”). “—” = none recent.</li>
      <li><strong>Price</strong> — latest close.</li>
      <li><strong>Δ%</strong> — today’s percent change (green up / red down).</li>
      <li><strong>Vol %</strong> — today’s volume as a % of its 50-day average. <strong>≥150%</strong> (gold) is the 1.5× volume that confirms a breakout (p.203).</li>
      <li><strong>Total Vol</strong> — today’s share volume.</li>
      <li><strong>Turnover</strong> — dollar volume traded today (price × volume) — “where the money is.” The default sort.</li>
      <li><strong>Stage</strong> — Weinstein/Minervini market stage. <strong>✓ S2</strong> (advancing) is the only buyable stage; S4 (decline) = avoid.</li>
      <li><strong>Beta</strong> — 1-year daily volatility vs the market (SPY). <strong>&lt;1</strong> (green) = calmer than the market / lower-volatility; <strong>&gt;1.3</strong> (red) = jumpier. Tap the header to <strong>sort low-volatility first</strong>.</li>
      <li><strong>→ R1/R2</strong> — which trade-plan target (entry +1R / +2R) it’s marching toward, and the % above price to reach it. “Past R2” = extended.</li>
      <li><strong>Verdict</strong> — the combined <strong>Minervini buyable-stock</strong> gate + <strong>Bonde sales</strong> test: PASS / PARTIAL / FAIL. Filter by either side with the chips above. <em>“Verdict pending”</em> = the latest scan hasn’t computed it yet.</li>
    </ul>
    <p className="mono">Display-only. Not investment advice.</p>
  </>
);

const pct = (v?: number | null) => (v != null ? `${v > 0 ? '+' : ''}${v.toFixed(2)}%` : '—');

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
  const { rows, summary, loading, error, reload } = useBreakoutBoard(250, 1);
  const [filter, setFilter] = useState<FilterKey>('all');

  const shown = useMemo(() => {
    const f = FILTERS.find((x) => x.key === filter) ?? FILTERS[0];
    return rows.filter(f.match);
  }, [rows, filter]);

  // Client-side sort over the filtered list. Default: turnover (dollar volume)
  // descending — the most-actionable "where's the money" view. Every column is
  // sortable via its header (Ajay 2026-06-16).
  const sort = useSort<BreakoutBoardRow>(shown, {
    ticker: (r) => r.symbol,
    count: (r) => r.breakout_count,
    last: (r) => r.days_since_breakout,
    price: (r) => r.last_close,
    change: (r) => r.day_change_pct,
    volpct: volPctOf,
    volume: (r) => r.last_vol,
    turnover: turnoverOf,
    stage: (r) => r.stage,
    beta: (r) => r.beta,
    march: (r) => marchToTarget(r.last_close, r.r1, r.r2).pct,
  }, 'turnover', 'desc');

  return (
    <div className="sepa-page">
      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">Breakouts</div>
          <h1 className="display sepa-page__h1" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            🚀 Breakouts
            <InfoButton inline title="Breakouts">{PageInfo}</InfoButton>
          </h1>
          <p className="lede">
            Every name that's broken out, ranked by <strong>how often</strong> — highest first.
            Each carries the <strong>Minervini + Bonde</strong> verdict, so you can see which
            breakouts pass the book and which don't. Filter by either side below.
          </p>
        </div>
        <button className="sepa-btn sepa-btn--ghost" onClick={reload} disabled={loading} title="Re-fetch the breakout board">
          {loading ? '↻ …' : '↻ Refresh'}
        </button>
      </div>

      {/* Summary mix — the "some pass, some don't" read at a glance */}
      {summary && (
        <div style={{
          display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'center',
          border: '1px solid var(--rule, #2a2a2a)', borderRadius: 8, padding: '0.7rem 1rem',
          margin: '0.4rem 0 0.9rem', background: 'var(--bg-raised, #181818)',
        }}>
          <Stat n={summary.total} label="breakouts" />
          <Stat n={summary.broke_out_today} label="today" tone="#eab308" />
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
              <Th label="# breakouts" k="count" style={colCount} sort={sort} />
              <Th label="Last" k="last" style={colLast} preferred="asc" sort={sort} />
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
                  to={`/sepa/${r.symbol}?tab=breakout`}
                  className="breakouts-row"
                  role="row"
                  style={dataRow}
                >
                  <span style={{ width: 36, color: 'var(--cm-slate)', fontWeight: 700 }}>{i + 1}</span>
                  <span style={{ ...colTicker, display: 'flex', flexDirection: 'column' }}>
                    <strong className="mono">{r.symbol}</strong>
                    {r.name && <span style={{ fontSize: '0.66rem', color: 'var(--cm-slate)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 160 }}>{r.name}</span>}
                  </span>
                  <span style={colCount}>
                    <span style={{ fontWeight: 800, fontSize: '1.05rem' }}>{r.breakout_count}</span>
                    {r.broke_out_today && <span title="Broke out today" style={{ marginLeft: 5, color: '#eab308' }}>⚡</span>}
                  </span>
                  <span style={{ ...colLast, color: 'var(--cm-slate)', fontSize: '0.74rem' }}>
                    {r.broke_out_today ? 'today' : r.days_since_breakout != null ? `${r.days_since_breakout}d ago` : '—'}
                  </span>
                  <span className="mono" style={colPrice}>
                    {r.last_close != null ? `$${r.last_close.toFixed(2)}` : '—'}
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
const colLast: CSSProperties = { width: 68 };
const colPrice: CSSProperties = { width: 76, textAlign: 'right' };
const colChg: CSSProperties = { width: 70, textAlign: 'right' };
const colVolPct: CSSProperties = { width: 80, textAlign: 'right' };
const colVol: CSSProperties = { width: 82, textAlign: 'right' };
const colTurnover: CSSProperties = { width: 96, textAlign: 'right' };
const colStage: CSSProperties = { width: 62 };
const colBeta: CSSProperties = { width: 60, textAlign: 'right' };
const colMarch: CSSProperties = { width: 104 };
const colVerdict: CSSProperties = { flex: '2 1 220px', minWidth: 200 };
