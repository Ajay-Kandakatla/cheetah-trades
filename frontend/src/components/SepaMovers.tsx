import { useMemo, useState } from 'react';
import { useSepaRuns, useSepaDiff } from '../hooks/useSepaHistory';
import { TickerLink } from './TickerLink';

/* ==========================================================================
   SepaMovers — what changed in the SEPA candidate list between two scans
   ==========================================================================
   Three sections:
     - NEWLY TRACKED  (entered candidate set)
     - DROPPED OUT    (exited candidate set)
     - SCORE MOVES    (still in set but score changed materially)
   With a [Today vs Yesterday | 7d | 30d] range selector and a custom
   from/to date picker for arbitrary scrubbing.
   ========================================================================== */

type Range = 'today' | '7d' | '30d' | 'custom';

function formatRelative(date: string) {
  const today = new Date().toISOString().slice(0, 10);
  if (date === today) return 'today';
  const diffDays = Math.round(
    (new Date(today).getTime() - new Date(date).getTime()) / 86400000,
  );
  if (diffDays === 1) return 'yesterday';
  if (diffDays >= 0 && diffDays < 30) return `${diffDays}d ago`;
  return date;
}

export function SepaMovers() {
  const { runs, loading: runsLoading } = useSepaRuns(60);
  const [range, setRange] = useState<Range>('today');
  const [customFrom, setCustomFrom] = useState<string>('');
  const [customTo, setCustomTo] = useState<string>('');

  // Reduce to one row per date_et (the most recent run per day)
  const dateOptions = useMemo(() => {
    const seen = new Set<string>();
    const out: { date: string; count: number }[] = [];
    for (const r of runs) {
      if (!r.date_et || seen.has(r.date_et)) continue;
      seen.add(r.date_et);
      out.push({ date: r.date_et, count: r.candidate_count ?? 0 });
    }
    return out;
  }, [runs]);

  // Resolve from/to dates for the selected range
  const { fromDate, toDate } = useMemo(() => {
    if (range === 'custom') {
      return { fromDate: customFrom || null, toDate: customTo || null };
    }
    if (dateOptions.length < 2) {
      return { fromDate: null, toDate: dateOptions[0]?.date ?? null };
    }
    const to = dateOptions[0].date;
    if (range === 'today') {
      // "Today" = most recent vs the one before it (first different date)
      const from = dateOptions[1].date;
      return { fromDate: from, toDate: to };
    }
    const days = range === '7d' ? 7 : 30;
    const cutoff = new Date(to);
    cutoff.setDate(cutoff.getDate() - days);
    const cutoffStr = cutoff.toISOString().slice(0, 10);
    // Pick the oldest snapshot ≤ cutoff (or the oldest available)
    const candidate = [...dateOptions].reverse().find((d) => d.date >= cutoffStr);
    return { fromDate: candidate?.date ?? dateOptions[dateOptions.length - 1].date, toDate: to };
  }, [range, customFrom, customTo, dateOptions]);

  const { diff, loading: diffLoading } = useSepaDiff(fromDate, toDate);

  if (runsLoading) {
    return <div className="movers-empty">Loading scan history…</div>;
  }
  if (dateOptions.length < 2 && range !== 'custom') {
    return (
      <div className="movers-empty">
        <p>Not enough history yet — need at least two scans on different days.</p>
        <p className="mono">Available: {dateOptions.length} snapshot day(s)</p>
      </div>
    );
  }

  return (
    <div className="movers">
      {/* Range selector */}
      <div className="movers__controls">
        <div className="movers__range">
          {(['today', '7d', '30d', 'custom'] as Range[]).map((r) => (
            <button
              key={r}
              className={`sepa-chip ${range === r ? 'is-active' : ''}`}
              onClick={() => setRange(r)}
            >
              {r === 'today' ? 'Today vs Yesterday' :
               r === '7d' ? '7 days' :
               r === '30d' ? '30 days' :
               'Custom'}
            </button>
          ))}
        </div>

        {range === 'custom' && (
          <div className="movers__custom">
            <label>
              <span className="mono">From</span>
              <select value={customFrom} onChange={(e) => setCustomFrom(e.target.value)}>
                <option value="">—</option>
                {dateOptions.map((d) => (
                  <option key={d.date} value={d.date}>
                    {d.date} ({d.count})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="mono">To</span>
              <select value={customTo} onChange={(e) => setCustomTo(e.target.value)}>
                <option value="">—</option>
                {dateOptions.map((d) => (
                  <option key={d.date} value={d.date}>
                    {d.date} ({d.count})
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

        {fromDate && toDate && (
          <div className="movers__period mono">
            Comparing <strong>{toDate}</strong> ({formatRelative(toDate)}) vs{' '}
            <strong>{fromDate}</strong> ({formatRelative(fromDate)})
          </div>
        )}
      </div>

      {diffLoading && <div className="movers-empty">Computing diff…</div>}

      {diff && !diffLoading && (
        <div className="movers__sections">
          {/* Newly tracked */}
          <section className="movers__section movers__section--entered">
            <header className="movers__section-head">
              <span className="movers__pill movers__pill--enter">+</span>
              <h3>Newly tracked</h3>
              <span className="mono movers__count">{diff.entered.length}</span>
            </header>
            {diff.entered.length === 0 ? (
              <p className="movers__empty mono">none</p>
            ) : (
              <ul className="movers__list">
                {diff.entered.map((sym) => (
                  <li key={sym}>
                    <TickerLink ticker={sym} fromLabel="movers" className="movers__sym" />
                    <span className="movers__sub mono">first appeared {formatRelative(toDate!)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Dropped */}
          <section className="movers__section movers__section--exited">
            <header className="movers__section-head">
              <span className="movers__pill movers__pill--exit">−</span>
              <h3>Dropped out</h3>
              <span className="mono movers__count">{diff.exited.length}</span>
            </header>
            {diff.exited.length === 0 ? (
              <p className="movers__empty mono">none</p>
            ) : (
              <ul className="movers__list">
                {diff.exited.map((sym) => (
                  <li key={sym}>
                    <TickerLink ticker={sym} fromLabel="movers" className="movers__sym" />
                    <span className="movers__sub mono">no longer a candidate as of {toDate}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Score moves */}
          <section className="movers__section movers__section--deltas">
            <header className="movers__section-head">
              <span className="movers__pill movers__pill--delta">Δ</span>
              <h3>Score moves</h3>
              <span className="mono movers__count">{diff.score_deltas.length}</span>
            </header>
            {diff.score_deltas.length === 0 ? (
              <p className="movers__empty mono">no material changes</p>
            ) : (
              <ul className="movers__list movers__list--deltas">
                {diff.score_deltas.slice(0, 25).map((d) => (
                  <li key={d.symbol}>
                    <TickerLink ticker={d.symbol} fromLabel="movers" className="movers__sym" />
                    <span className="mono movers__delta">
                      {d.from?.toFixed(0) ?? '—'} → {d.to?.toFixed(0) ?? '—'}
                    </span>
                    <span className={`mono movers__deltapct ${d.delta > 0 ? 'is-up' : 'is-down'}`}>
                      {d.delta > 0 ? '+' : ''}{d.delta.toFixed(1)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
