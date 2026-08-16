/* Sector Rotation — where money left, where it went, and since when.
 *
 * Ajay 2026-08-16: "I want you to have sector rotation tracker what I feel now
 * is money is rotating out of that themes I gave you" and "add a rule to also
 * track sector rotations time to time and make sure few other sectors that
 * wallstreet rotates in to historically. Like safe haves vs in general."
 *
 * Two columns carry the whole page: the full window says what already happened,
 * the 21-day says whether it is still happening. A group that is deeply negative
 * on the window and positive on 21d has TURNED — that is the only cell on the
 * page that changes what you do next, so it gets the badge.
 */
import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { API } from '../lib/apiBase';
import { InfoButton } from '../components/InfoButton';
import {
  WINDOWS, boardQuery, etfGapLine, isThinGroup, pct, pp, riskStance, tone,
  turned, type RotBoard, type RotRow,
} from '../lib/rotation';

const HowItWorks = (
  <>
    <p>What moved, relative to the <strong>equal-weight</strong> S&amp;P (RSP) —
      not SPY. Cap-weight drag is not rotation: over the measured window RSP rose
      6.7% while SPY rose 2.6%, so 4pp of "outperformance" against SPY was pure
      index construction.</p>
    <ul>
      <li><strong>pp</strong> means percentage POINTS versus the benchmark. A
        sector at −2.7pp may still have gone up — it just went up less.</li>
      <li><strong>Median member, not the ETF.</strong> SOXX read −3.3% while the
        median liquid semiconductor stock was −11.7%. Where they disagree by more
        than 2pp the page says so — that gap measures how much of a move is a
        handful of mega-caps.</li>
      <li><strong>Turned</strong> marks a group that was negative over the full
        window and positive over the last 21 days. A bounce off a deep decline is
        not a base; it is a reason to look, not to buy.</li>
      <li><strong>Dead tickers are excluded.</strong> Acquired and delisted names
        keep returning stale price frames that would read as a flat 0% and drag a
        median toward zero. Dropped counts are shown.</li>
    </ul>
    <p><strong>Safe havens.</strong> Gold, treasuries and low-volatility are
      tracked beside the sectors. Defensive minus cyclical is the one-line read on
      whether money is hiding.</p>
    <p><strong>What this is not.</strong> A measurement of what already moved.
      Not a forecast, not a business-cycle call, and not a buy signal. It reads no
      13F data — institutional filings arrive 45 days after quarter end, so they
      are a lagging level, never a flow.</p>
  </>
);

function Row({ r, showEtf }: { r: RotRow; showEtf?: boolean }) {
  const t = turned(r);
  const gap = showEtf ? etfGapLine(r) : null;
  return (
    <tr>
      <td className="rot-name">
        <b>{r.group}</b>
        {r.stance ? <span className={`rot-stance rot-stance-${r.stance}`}>{r.stance}</span> : null}
        {t ? <span className={`rot-turn rot-turn-${t}`}>turned {t}</span> : null}
        <span className="rot-n">
          n={r.n}
          {r.dropped ? <span className="rot-dropped" title={(r.dropped_symbols || []).join(', ')}>
            {' '}· {r.dropped} dead
          </span> : null}
        </span>
        {gap ? <div className="rot-gap">{gap}</div> : null}
      </td>
      <td className={`mono rot-${tone(r.rel_window)}`}>{pp(r.rel_window)}</td>
      <td className={`mono rot-${tone(r.rel_21d)}`}>{pp(r.rel_21d)}</td>
      <td className="mono rot-abs">{pct(r.median_window)}</td>
      <td className="mono rot-abs">{r.pct_positive == null ? '—' : `${r.pct_positive}%`}</td>
    </tr>
  );
}

function Table({ title, rows, showEtf, note }:
  { title: string; rows: RotRow[]; showEtf?: boolean; note?: string }) {
  const usable = rows.filter((r) => !isThinGroup(r) || r.rel_window != null);
  return (
    <section className="rot-section">
      <h3>{title}</h3>
      {note ? <p className="rot-note">{note}</p> : null}
      <div className="rot-scroll">
        <table className="rot-table">
          <thead>
            <tr>
              <th>Group</th>
              <th>vs equal-weight</th>
              <th>last 21d</th>
              <th>median move</th>
              <th>% green</th>
            </tr>
          </thead>
          <tbody>
            {usable.map((r) => <Row key={r.group} r={r} showEtf={showEtf} />)}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function Rotation() {
  const [params, setParams] = useSearchParams();
  const start = params.get('start') || WINDOWS[0].key;
  const [data, setData] = useState<RotBoard | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async (refresh = false) => {
    setErr(null);
    setLoading(true);
    try {
      const res = await fetch(`${API}/rotation?${boardQuery({ start, refresh })}`,
                              { credentials: 'include' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const j: RotBoard = await res.json();
      if (j.error) throw new Error(j.error);
      setData(j);
    } catch (e: any) {
      setErr(e?.message || 'failed to load');
    } finally {
      setLoading(false);
    }
  }, [start]);

  useEffect(() => { load(); }, [load]);

  const stance = data ? riskStance(data.stance) : null;

  return (
    <div className="rot-page">
      <div className="rot-head">
        <h2>
          Sector Rotation
          <InfoButton title="How this is measured">{HowItWorks}</InfoButton>
        </h2>
        <div className="rot-controls">
          {WINDOWS.map((w) => (
            <button
              key={w.key}
              type="button"
              className={`sepa-btn${w.key === start ? ' is-active' : ''}`}
              onClick={() => setParams((p) => {
                const n = new URLSearchParams(p);
                n.set('start', w.key);
                return n;
              }, { replace: true })}
            >{w.label}</button>
          ))}
          <button type="button" className="sepa-btn" onClick={() => load(true)}>
            Refresh
          </button>
        </div>
      </div>

      {err ? <p className="sepa-empty">Could not load rotation: {err}</p> : null}
      {loading && !data ? <p className="sepa-empty">Measuring…</p> : null}

      {data ? (
        <>
          <div className="rot-summary">
            <div>
              <span className="rot-label">Benchmark</span>
              <b>{data.benchmark.symbol} {pct(data.benchmark.window)}</b>
            </div>
            <div>
              <span className="rot-label">Stance</span>
              <b>{stance?.label}{stance?.spread == null ? '' : ` (${pp(stance.spread)})`}</b>
            </div>
            <div>
              <span className="rot-label">Leading</span>
              <b>{(data.leaders || []).join(' · ') || '—'}</b>
            </div>
            <div>
              <span className="rot-label">Lagging</span>
              <b>{(data.laggards || []).join(' · ') || '—'}</b>
            </div>
            <div>
              <span className="rot-label">As of</span>
              <b className="mono">{data.as_of}</b>
            </div>
          </div>

          <Table title="Sectors" rows={data.sectors} showEtf
                 note="Median liquid member of each sector, versus the sector ETF where they disagree." />
          <Table title="Your themes" rows={data.themes}
                 note="The build-out rosters — space, quantum, semis, AI power, nuclear, energy, optical, robotics, infra." />
          <Table title="Safe havens" rows={data.havens}
                 note="Where money historically hides. Equal-weight S&P is the 0.0 line by definition." />

          {data.note ? <p className="rot-foot">{data.note}</p> : null}
        </>
      ) : null}
    </div>
  );
}

export default Rotation;
