/* TopPicksTracker — "how the Top Picks set churns over time" on the Leaderboard
   page. Ajay (2026-06-03): saw BB/LBRT/NUE on the phone but BB/TECL/CORZ/LBRT/AMAT
   on desktop and wanted to TRACK that drift to build confidence — who PERSISTS as
   a pick vs who was a one-scan flash.

   Two tabs (his spec):
     • Streak + churn  — the CURRENT pick set, each with a durability streak
       (consecutive days/scans as a pick), score trend ▲▼, first-seen, plus who
       ENTERED / DROPPED at the latest point. A Day/Scan toggle: Scan exposes the
       intraday churn that explains a phone-vs-desktop mismatch.
     • Daily timeline  — day-by-day, newest first; each day's picks as chips with
       NEW entrants flagged (new-vs-last) and droppers shown dim.

   Reads GET /sepa/top-picks/tracker (sepa/top_picks_history.py). Fails quiet. */
import { useEffect, useState } from 'react';
import { TickerName } from './TickerCell';
import { Link } from 'react-router-dom';
import { API } from '../lib/apiBase';

type CurPick = {
  symbol: string; name?: string | null; score: number;
  status: 'buyable' | 'ready'; tier: number;
  streak: number; appearances: number; first_date: string | null;
  score_trend: string; is_new: boolean;
};
type TLPoint = {
  t: number; date: string | null; picks: string[];
  scores: Record<string, number>; entered: string[]; dropped: string[];
};
type Tracker = {
  granularity: string; n: number; days: number; scans_in_window: number;
  current: CurPick[]; churn: { entered: string[]; dropped: string[] }; timeline: TLPoint[];
};

const STATUS: Record<string, { label: string; color: string }> = {
  buyable: { label: 'buyable', color: '#10b981' },
  ready:   { label: 'ready',   color: '#eab308' },
};
const trendColor = (t: string) => (t === '▲' ? '#10b981' : t === '▼' ? '#f87171' : '#64748b');

export function TopPicksTracker({ n = 5, days = 14 }: { n?: number; days?: number }) {
  const [tab, setTab] = useState<'streak' | 'daily'>('streak');
  const [streakGran, setStreakGran] = useState<'daily' | 'intraday'>('daily');
  const [data, setData] = useState<Tracker | null>(null);
  const [state, setState] = useState<'loading' | 'ok' | 'empty' | 'err'>('loading');

  const gran = tab === 'daily' ? 'daily' : streakGran;

  useEffect(() => {
    let alive = true;
    setState('loading');
    fetch(`${API}/sepa/top-picks/tracker?n=${n}&days=${days}&granularity=${gran}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d: Tracker) => {
        if (!alive) return;
        setData(d);
        setState((d.current || []).length || (d.timeline || []).length ? 'ok' : 'empty');
      })
      .catch(() => alive && setState('err'));
    return () => { alive = false; };
  }, [n, days, gran]);

  return (
    <section className="tpt">
      <div className="tpt__head">
        <span className="eyebrow">🎯 Top-Picks tracker · who's persisting</span>
        <div className="tpt__tabs">
          <button className={tab === 'streak' ? 'is-on' : ''} onClick={() => setTab('streak')}>Streak + churn</button>
          <button className={tab === 'daily' ? 'is-on' : ''} onClick={() => setTab('daily')}>Daily timeline</button>
        </div>
      </div>

      {state === 'loading' && <p className="tpt__msg mono">…loading tracker</p>}
      {state === 'err' && <p className="tpt__msg mono">Couldn't load the tracker.</p>}
      {state === 'empty' && <p className="tpt__msg mono">No pick history yet — it builds as scans accumulate.</p>}

      {state === 'ok' && data && tab === 'streak' && (
        <div className="tpt__streak">
          <div className="tpt__bar">
            <span className="tpt__sub mono">
              Current picks over the last {data.scans_in_window} {gran === 'daily' ? 'days' : 'scans'} ·
              streak = {gran === 'daily' ? 'days' : 'scans'} in a row as a pick
            </span>
            <div className="tpt__gran">
              <button className={streakGran === 'daily' ? 'is-on' : ''} onClick={() => setStreakGran('daily')}>Day</button>
              <button className={streakGran === 'intraday' ? 'is-on' : ''} onClick={() => setStreakGran('intraday')}>Scan</button>
            </div>
          </div>

          <div className="tpt__list">
            {data.current.map((c) => {
              const s = STATUS[c.status] || STATUS.ready;
              return (
                <Link key={c.symbol} to={`/sepa/${c.symbol}`} className="tpt__row"
                      title={`${c.appearances} of ${data.scans_in_window} ${gran === 'daily' ? 'days' : 'scans'} · first seen ${c.first_date ?? '—'}`}>
                  <span className="tpt__streakbadge mono" data-strong={c.streak >= 3 ? '1' : '0'}>
                    {c.streak >= 3 ? '🔥' : ''}{c.streak}
                  </span>
                  <span className="tpt__sym">{c.symbol}<TickerName symbol={c.symbol} width={16} /></span>
                  <span className="tpt__score mono">
                    {c.score}<b style={{ color: trendColor(c.score_trend) }}> {c.score_trend}</b>
                  </span>
                  <span className="tpt__status" style={{ color: s.color, borderColor: s.color }}>{s.label}</span>
                  <span className="tpt__since mono">{c.appearances}/{data.scans_in_window} · since {c.first_date ?? '—'}</span>
                  {c.is_new && <span className="tpt__new">NEW</span>}
                </Link>
              );
            })}
          </div>

          <div className="tpt__churn">
            <div className="tpt__churn-col">
              <span className="tpt__churn-h mono" style={{ color: '#10b981' }}>↑ entered (latest)</span>
              {data.churn.entered.length
                ? data.churn.entered.map((s) => <Link key={s} to={`/sepa/${s}`} className="tpt__chip tpt__chip--in">{s}</Link>)
                : <span className="tpt__churn-none mono">—</span>}
            </div>
            <div className="tpt__churn-col">
              <span className="tpt__churn-h mono" style={{ color: '#f87171' }}>↓ dropped (latest)</span>
              {data.churn.dropped.length
                ? data.churn.dropped.map((s) => <Link key={s} to={`/sepa/${s}`} className="tpt__chip tpt__chip--out">{s}</Link>)
                : <span className="tpt__churn-none mono">—</span>}
            </div>
          </div>
        </div>
      )}

      {state === 'ok' && data && tab === 'daily' && (
        <div className="tpt__daily">
          <p className="tpt__sub mono">
            One pick set per day, newest first · <b style={{ color: '#10b981' }}>green = new vs the day before</b>,
            dim = dropped that day.
          </p>
          {[...data.timeline].reverse().map((pt) => (
            <div key={pt.t} className="tpt__day">
              <span className="tpt__day-date mono">{pt.date ?? '—'}</span>
              <div className="tpt__day-picks">
                {pt.picks.map((s) => (
                  <Link key={s} to={`/sepa/${s}`}
                        className={`tpt__chip${pt.entered.includes(s) ? ' tpt__chip--in' : ''}`}
                        title={pt.scores[s] != null ? `score ${pt.scores[s]}` : undefined}>
                    {s}{pt.entered.includes(s) ? ' •' : ''}
                  </Link>
                ))}
                {pt.dropped.map((s) => (
                  <span key={`d-${s}`} className="tpt__chip tpt__chip--out" title="dropped out this day">{s}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="tpt__foot mono">Reconstructed from SEPA scan history · not investment advice</p>
    </section>
  );
}
