/* Back in Demand — "is it actually working?", under the board.
 *
 * Ajay 2026-08-17: "Can you maintain history of our In deman page please.. I
 * think its working out.. I saw CIEN you recommended is bouncing out of the
 * zone now.. I would imagine the same with other stocks. Want you to track it"
 *
 * COLLAPSED BY DEFAULT, and deliberately. The board above it is already a
 * dense decision surface — universe, sort, R:R floor, progress, then a row per
 * name carrying plan, liquidity, venue and band. A track record is something
 * you go and check, not something you read while picking a trade. The summary
 * line is the only thing that shows unasked, because "are we ahead of SPY" is
 * one number and it changes how you read every row above it.
 *
 * Reads GET /supply-demand/demand-reentry/history. Fails quiet: a page that
 * still shows the board is worth more than one that shows an error box.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';
import {
  type TrackRecord, churnRuns, headline, pct, tone, verdict,
} from '../lib/demandTrackRecord';

const TONE_COLOR: Record<string, string> = {
  good: 'var(--good, #34d399)',
  bad: 'var(--bad, #f87171)',
  flat: 'var(--muted, #9ca3af)',
};

function Stat({ k, v, t }: { k: string; v: string; t?: 'good' | 'bad' | 'flat' }) {
  return (
    <div style={{ minWidth: '5.5rem' }}>
      <div style={{ fontSize: '0.62rem', opacity: 0.6, textTransform: 'uppercase',
                    letterSpacing: '0.04em' }}>{k}</div>
      <div className="mono" style={{ fontSize: '0.9rem', fontWeight: 600,
                                     color: t ? TONE_COLOR[t] : undefined }}>{v}</div>
    </div>
  );
}

export function DemandTrackRecord({ universe }: { universe: string }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<TrackRecord | null>(null);

  useEffect(() => {
    let dead = false;
    fetch(`${API}/supply-demand/demand-reentry/history?universe=${encodeURIComponent(universe)}&runs=30`,
          { credentials: 'include' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => { if (!dead && j) setData(j); })
      .catch(() => {});
    return () => { dead = true; };
  }, [universe]);

  if (!data) return null;
  const v = verdict(data);
  const churn = churnRuns(data, 12);

  return (
    <section style={{ marginTop: '0.9rem', borderTop: '1px solid var(--border, #2a2a2a)',
                      paddingTop: '0.7rem' }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem',
                    flexWrap: 'wrap' }}>
        <button className="sepa-btn" onClick={() => setOpen(!open)}
                aria-expanded={open}
                style={{ fontSize: '0.72rem', padding: '0.2rem 0.5rem' }}>
          {open ? '▾' : '▸'} Track record
        </button>
        <span role="status" style={{ fontSize: '0.75rem', opacity: 0.85 }}>
          {headline(data)}
        </span>
      </div>

      {open && (
        <div style={{ marginTop: '0.7rem' }}>
          {v === 'empty' ? (
            <p style={{ fontSize: '0.74rem', opacity: 0.75, maxWidth: '46rem' }}>
              Every scan now records what the board published — the names, their
              plans, and the day. Each one is graded at the following session's
              open against the plan frozen when it first appeared, so nothing
              here can be rewritten by a later change to the rule. An episode
              gets up to {60} bars to reach target or stop, so the first
              outcomes land in a few weeks.{' '}
              {(data.open ?? 0) > 0 && <><strong>{data.open}</strong> still racing.</>}
            </p>
          ) : (
            <>
              <div style={{ display: 'flex', gap: '1.2rem', flexWrap: 'wrap',
                            margin: '0.2rem 0 0.6rem' }}>
                <Stat k="vs SPY" v={pct(data.excess_vs_spy_pct)}
                      t={tone(data.excess_vs_spy_pct)} />
                <Stat k="Expectancy" v={pct(data.expectancy_pct)}
                      t={tone(data.expectancy_pct)} />
                <Stat k="Finished" v={String(data.raced ?? 0)} />
                <Stat k="Win rate" v={data.win_pct == null ? '—' : `${data.win_pct}%`} />
                <Stat k="Median R:R" v={data.median_rr == null ? '—' : data.median_rr.toFixed(2)} />
                <Stat k="Still open" v={String(data.open ?? 0)} />
                {/* Not a footnote: these never got a fill, so they are neither
                    a win nor a loss and sit outside every ratio above. */}
                <Stat k="Never filled" v={String(data.never_filled ?? 0)} />
              </div>
              <p style={{ fontSize: '0.68rem', opacity: 0.6, maxWidth: '46rem' }}>
                Live record since {data.since ?? '—'} across {data.symbols ?? 0} names.
                Entry is the next session's open; a bar holding both stop and
                target counts as a loss; gross of costs. Read <strong>vs SPY</strong>,
                not the win rate — a dip-buying board in a rising tape shows
                profit with or without skill.
              </p>
            </>
          )}

          {churn.length > 0 && (
            <div style={{ marginTop: '0.6rem' }}>
              <div style={{ fontSize: '0.62rem', opacity: 0.6, textTransform: 'uppercase',
                            letterSpacing: '0.04em', marginBottom: '0.3rem' }}>
                Board changes
              </div>
              {churn.map((r) => (
                <div key={r.et_date} className="mono"
                     style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap',
                              fontSize: '0.72rem', padding: '0.15rem 0' }}>
                  <span style={{ opacity: 0.7, minWidth: '5.5rem' }}>{r.et_date}</span>
                  {(r.entered ?? []).map((s) => (
                    <TickerLink key={`in-${s}`} ticker={s} tab="setup"
                                fromKey="supply-demand" fromLabel="Back in Demand"
                                showWatchlist={false}
                                style={{ color: TONE_COLOR.good }} title="joined the board">
                      +{s}
                    </TickerLink>
                  ))}
                  {(r.dropped ?? []).map((s) => (
                    <TickerLink key={`out-${s}`} ticker={s} tab="setup"
                                fromKey="supply-demand" fromLabel="Back in Demand"
                                showWatchlist={false}
                                style={{ color: TONE_COLOR.bad }} title="left the board">
                      −{s}
                    </TickerLink>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
