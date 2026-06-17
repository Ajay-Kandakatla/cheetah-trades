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
    </ul>
    <p className="mono">Display-only. Not investment advice.</p>
  </>
);

const pct = (v?: number | null) => (v != null ? `${v > 0 ? '+' : ''}${v.toFixed(2)}%` : '—');

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
        <div className="breakouts-table" role="table">
          <div className="breakouts-row breakouts-row--head" role="row" style={headRow}>
            <span style={{ width: 36 }}>#</span>
            <span style={{ flex: '1 1 120px' }}>Ticker</span>
            <span style={colCount}># breakouts</span>
            <span style={colLast}>last</span>
            <span style={colPrice}>price</span>
            <span style={{ flex: '2 1 260px' }}>verdict</span>
          </div>
          {shown.map((r, i) => (
            <Link
              key={r.symbol}
              to={`/sepa/${r.symbol}?tab=breakout`}
              className="breakouts-row"
              role="row"
              style={dataRow}
            >
              <span style={{ width: 36, color: 'var(--cm-slate)', fontWeight: 700 }}>{i + 1}</span>
              <span style={{ flex: '1 1 120px', display: 'flex', flexDirection: 'column' }}>
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
              <span style={colPrice}>
                {r.last_close != null && <span className="mono">${r.last_close.toFixed(2)}</span>}
                {r.day_change_pct != null && (
                  <span className="mono" style={{ marginLeft: 6, fontSize: '0.72rem', color: r.day_change_pct >= 0 ? 'var(--positive, #10b981)' : 'var(--negative, #f87171)' }}>
                    {pct(r.day_change_pct)}
                  </span>
                )}
              </span>
              <span style={{ flex: '2 1 260px' }}>
                {r.is_etf ? (
                  <span style={{ fontSize: '0.72rem', color: 'var(--cm-slate)' }}>ETF — no Minervini verdict</span>
                ) : r.buy_verdict ? (
                  <BuyVerdictChip row={r} />
                ) : (
                  <span style={{ fontSize: '0.72rem', color: 'var(--cm-slate)' }}>verdict pending</span>
                )}
              </span>
            </Link>
          ))}
        </div>
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
const colCount: CSSProperties = { width: 110, textAlign: 'left' };
const colLast: CSSProperties = { width: 80 };
const colPrice: CSSProperties = { width: 150 };
