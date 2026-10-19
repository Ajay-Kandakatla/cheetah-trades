/* 🌙 Overnight session board — Chart Maps ▸ Overnight ▸ 🌙 Overnight session
 * (BUILD_SPEC16 §3.7, 2026-10-19).
 *
 * Ajay 2026-10-19: "Can you do an over night scan for all the stocks they are
 * all growing over night" · "These are over night check qqq for example".
 *
 * Every sentence on this board is SERVED by backend/overnight/board.py and
 * printed verbatim: the session clock, the last pass (amber when late), the
 * counts line with its floors, the price rule with the pass's median trade age,
 * the leverage rule, UNMEASURED and the disclaimer. The sort labels come from
 * the served `sorts`. This file types no floor, no clock and no dollar
 * threshold; it only formats the numbers each row carries.
 *
 * AMENDMENTS16 A1: the `q` chip marks a bid/ask-midpoint price (the common
 * case); the `t` chip marks the latest overnight trade — indicative and
 * delayed (the row's age is on hover). UNMEASURED; not advice. */
import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useOvernightSession } from '../hooks/useOvernightSession';
import { useWatchlist } from '../hooks/useWatchlist';
import {
  ON_LEV_HIDE, ON_LEV_PARAM, ON_SORT_PARAM, fmtAge, fmtPct, fmtPrice, fmtUsdShort, srcWords, watchSet,
  type OnRow,
} from '../lib/overnightSession';
import '../styles/overnight.css';

const tone = (v: number | null | undefined) =>
  typeof v === 'number' && Number.isFinite(v) ? (v > 0 ? ' ons-up' : v < 0 ? ' ons-down' : '') : '';

function SrcChip({ src }: { src: OnRow['src'] }) {
  return (
    <span className={`ons-src ons-src-${src === 'q' ? 'q' : 't'}`} title={srcWords(src)}
          data-testid={`ons-src-${src === 'q' ? 'q' : 't'}`}>
      {src === 'q' ? 'q' : 't'}
    </span>
  );
}

const ageTitle = (r: OnRow) => `${srcWords(r.src)} · ${fmtAge(r.price_age_sec)} old`;

export default function OvernightSessionBoard({ onPick }: { onPick?: (symbol: string) => void }) {
  const [params, setParams] = useSearchParams();
  const sortParam = params.get(ON_SORT_PARAM);
  const hideLev = params.get(ON_LEV_PARAM) === ON_LEV_HIDE;
  const { data, error, loading } = useOvernightSession({ sort: sortParam, hideLev });
  const { rows: wlRows } = useWatchlist();
  const watch = useMemo(() => watchSet(wlRows), [wlRows]);

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value == null) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };

  const read = data?.read ?? null;
  const lines = data?.lines;
  const activeSort = read?.sort ?? sortParam ?? data?.sorts?.[0]?.key ?? null;
  const pick = (sym: string) => onPick?.(sym);

  return (
    <div className="ons-board" data-testid="ons-board">
      {data?.session?.line ? <div className="ons-line ons-session" data-testid="ons-session-line">{data.session.line}</div> : null}
      {data?.last_pass?.line ? (
        <div className={`ons-line${data.last_pass.stale ? ' ons-stale' : ''}${data.last_pass.ok === false ? ' ons-error' : ''}`}
             data-testid="ons-last-pass">
          {data.last_pass.line}
        </div>
      ) : null}
      {read && read.current === false && lines?.read_old ? (
        <div className="ons-line ons-old" data-testid="ons-read-old">{lines.read_old}</div>
      ) : null}
      {error ? (
        <div className="ons-line ons-error" data-testid="ons-error">
          {data ? `Could not refresh the overnight read (${error}) — showing the last one.` : `Could not load the overnight read (${error}).`}
        </div>
      ) : null}
      {loading && !data ? <div className="ons-line ons-muted">Loading the overnight read…</div> : null}

      {read && read.refs?.length ? (
        <div className="ons-refs" data-testid="ons-refs">
          {read.refs.map((r) => (
            <button key={r.symbol} type="button" className="ons-ref" data-testid={`ons-ref-${r.symbol}`}
                    title={ageTitle(r)} onClick={() => pick(r.symbol)}>
              <span className="ons-ref-sym">{r.symbol}</span>
              <span className={`ons-ref-pct${tone(r.pct)}`}>{fmtPct(r.pct)}</span>
              <span className="ons-ref-px">{fmtPrice(r.price)} <SrcChip src={r.src} /></span>
              <span className="ons-muted">{r.price_time_et || '—'}</span>
            </button>
          ))}
        </div>
      ) : null}

      {data ? (
        <div className="ons-controls">
          <div className="ons-sorts" role="group" aria-label="Order">
            {(data.sorts || []).map((s) => (
              <button key={s.key} type="button" data-testid={`ons-sort-${s.key}`}
                      className={`ons-btn${s.key === activeSort ? ' is-active' : ''}`}
                      aria-pressed={s.key === activeSort}
                      onClick={() => setParam(ON_SORT_PARAM, s.key)}>
                {s.label}
              </button>
            ))}
          </div>
          <button type="button" data-testid="ons-hide-lev"
                  className={`ons-btn ons-chip${hideLev ? ' is-active' : ''}`} aria-pressed={hideLev}
                  onClick={() => setParam(ON_LEV_PARAM, hideLev ? null : ON_LEV_HIDE)}>
            Hide leveraged ETFs
            {hideLev && read ? <span className="ons-hidden-n" data-testid="ons-hidden-n"> · {read.n_hidden_leveraged.toLocaleString('en-US')} hidden</span> : null}
          </button>
        </div>
      ) : null}

      {read && lines?.counts ? <div className="ons-line ons-counts" data-testid="ons-counts">{lines.counts}</div> : null}
      {read && read.reason ? <div className="ons-line ons-muted" data-testid="ons-reason">{read.reason}</div> : null}

      {data && !read ? <div className="ons-line ons-empty" data-testid="ons-empty">{lines?.empty}</div> : null}

      {read ? (
        <div className="ons-scroll">
          <table className="ons-table" data-testid="ons-table">
            <thead>
              <tr>
                <th aria-label="On your watchlist">⭐</th>
                <th>Symbol</th>
                <th>Overnight %</th>
                <th>Now</th>
                <th>Base close</th>
                <th>Overnight $ vol</th>
                <th>Prior-session %</th>
                <th>Time of print</th>
                <th>Src</th>
              </tr>
            </thead>
            <tbody>
              {read.rows.map((r) => (
                <tr key={r.symbol} data-testid={`ons-row-${r.symbol}`} className="ons-row" tabIndex={0}
                    onClick={() => pick(r.symbol)}
                    onKeyDown={(e) => { if (e.key === 'Enter') pick(r.symbol); }}>
                  <td className="ons-star">{watch.has(r.symbol.toUpperCase()) ? <span data-testid="ons-star" title="On your watchlist">⭐</span> : null}</td>
                  <td className="ons-sym">
                    <span className="ons-sym-t">{r.symbol}</span>
                    {r.lev_label ? <span className="ons-lev-chip" data-testid="ons-lev-chip">{r.lev_label}</span> : null}
                    {r.name ? <span className="ons-name">{r.name}</span> : null}
                  </td>
                  <td className={`ons-num${tone(r.pct)}`}>{fmtPct(r.pct)}</td>
                  <td className="ons-num" title={ageTitle(r)}>{fmtPrice(r.price)} <SrcChip src={r.src} /></td>
                  <td className="ons-num">
                    {fmtPrice(r.base_close)}
                    {r.base_date ? <span className="ons-sub">{r.base_date}</span> : null}
                  </td>
                  <td className="ons-num">{fmtUsdShort(r.on_dollar)}</td>
                  <td className={`ons-num${tone(r.prior_pct)}`}>{fmtPct(r.prior_pct)}</td>
                  <td className="ons-time" title={ageTitle(r)}>{r.price_time_et || '—'}</td>
                  <td className="ons-srcw">{srcWords(r.src)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {data ? (
        <div className="ons-foot">
          {lines?.price_rule ? <p data-testid="ons-price-rule">{lines.price_rule}</p> : null}
          {lines?.leveraged ? <p data-testid="ons-lev-line">{lines.leveraged}</p> : null}
          {lines?.unmeasured ? <p className="ons-unmeasured" data-testid="ons-unmeasured">{lines.unmeasured}</p> : null}
          {data.disclaimer ? <p className="ons-muted" data-testid="ons-disclaimer">{data.disclaimer}</p> : null}
        </div>
      ) : null}
    </div>
  );
}

export { OvernightSessionBoard };
