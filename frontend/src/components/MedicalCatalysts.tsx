/* 🧬 Medical catalysts — Chart Maps ▸ Catalysts ▸ 🧬 Medical
 * (/chart-maps?tab=catalysts&sub=medical).
 *
 * Ajay 2026-09-29: "can you add a new routine to scan for … amd trails or other
 * medi cal nws and sector them separatively like new fdaapprovals or break
 * throughs like mrnaresearch how to catch thsse sectorsand companiesand add
 * right setup and alerts".
 *
 * Reads GET /catalysts/medical. The backend routine (catalysts/medical, riding
 * promo_live's 5-minute cron line) files each item by event, modality and
 * area; this page groups what was served by family, filters it, and shows the
 * 🔥 roll-up of which modalities / areas are getting the news. The served
 * UNMEASURED note and `setup` are rendered as served — the page never types
 * them, and never shows a price to act at.
 */
import { useMemo, useState } from 'react';
import { MedicalEventRow } from './MedicalEventRow';
import { useMedicalBoard } from '../hooks/useMedicalCatalysts';
import {
  etClock, filterEvents, fmtMovePct, groupByFamily, sortRollup, toLabelMap,
  type MedBoard, type MedPass, type RollRow, type RollSortKey,
} from '../lib/medicalCatalysts';

export const MED_WINDOWS = [7, 30, 90] as const;

function passStamp(pass: MedPass | undefined): string {
  const t = etClock(pass?.as_of ?? null);
  if (!t) return 'no pass recorded yet';
  const read = pass?.counts?.sliced ?? pass?.counts?.finnhub_calls;
  return `last pass ${t} ET${read != null ? ` · ${read} names read` : ''}`;
}

function passCounts(pass: MedPass | undefined): string {
  const c = pass?.counts ?? {};
  const parts: string[] = [];
  for (const [k, lbl] of [['roster', 'roster'], ['articles_new', 'new articles'], ['events_new', 'new events'], ['errors', 'errors']] as const) {
    if (c[k] != null) parts.push(`${lbl} ${c[k]}`);
  }
  if (pass?.reason) parts.push(pass.reason);
  return parts.join(' · ');
}

function RollTable({ rows, sortKey }: { rows: RollRow[]; sortKey: RollSortKey }) {
  const sorted = useMemo(() => sortRollup(rows, sortKey), [rows, sortKey]);
  if (!sorted.length) return <div className="mc-dim">Nothing classified in this window.</div>;
  return (
    <div className="mc-roll__wrap">
      <table className="mc-roll" data-testid="mc-roll">
        <thead>
          <tr>
            <th>group</th><th>events</th><th>high</th><th>+ / −</th><th>names</th><th>obs</th>
            <th>median day</th><th>median 5d</th><th>median 21d</th><th>tickers</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.key} className={r.small_n ? 'mc-roll__row mc-roll__row--small' : 'mc-roll__row'}
                data-testid={`mc-roll-${r.key}`}>
              <td>{r.label}{r.small_n ? <span className="mc-roll__n" title="fewer than 5 names — too few to read">n&lt;5</span> : null}</td>
              <td className="mono">{r.n_events}</td>
              <td className="mono">{r.n_high}</td>
              <td className="mono">{r.n_positive} / {r.n_negative}</td>
              <td className="mono">{r.n_tickers}</td>
              <td className="mono">{r.n_obs}</td>
              <td className="mono">{fmtMovePct(r.median_day_pct)} <span className="mc-dim">n{r.n_day}</span></td>
              <td className="mono">{fmtMovePct(r.median_ret_5d_pct)} <span className="mc-dim">n{r.n_5d}</span></td>
              <td className="mono">{fmtMovePct(r.median_ret_21d_pct)} <span className="mc-dim">n{r.n_21d}</span></td>
              <td className="mono mc-dim">{r.tickers.join(' ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MedicalBoardView({ data, days, onDays }: {
  data: MedBoard; days: number; onDays: (d: number) => void;
}) {
  const [families, setFamilies] = useState<string[]>([]);
  const [modality, setModality] = useState<string>('');
  const [area, setArea] = useState<string>('');
  const [highOnly, setHighOnly] = useState(false);
  const [rollBy, setRollBy] = useState<'modality' | 'area'>('modality');
  const [rollSort, setRollSort] = useState<RollSortKey>('n_events');

  const tax = data.taxonomy;
  const modLabels = useMemo(() => toLabelMap(tax?.modalities), [tax]);
  const areaLabels = useMemo(() => toLabelMap(tax?.areas), [tax]);
  const shown = useMemo(
    () => filterEvents(data.events ?? [], { families, modality: modality || null, area: area || null, highOnly }),
    [data.events, families, modality, area, highOnly],
  );
  const groups = useMemo(() => groupByFamily(shown, tax?.families ?? []), [shown, tax]);
  const toggleFamily = (k: string) =>
    setFamilies((cur) => (cur.includes(k) ? cur.filter((x) => x !== k) : [...cur, k]));
  const total = (data.events ?? []).length;

  return (
    <div className="mc-board" data-testid="mc-board">
      <div className="mc-head">
        <h3 className="mc-head__title">🧬 Medical catalysts — FDA decisions, trial readouts, designations, holds, deals, financing</h3>
        <div className="mc-note" data-testid="mc-unmeasured">{data.labels.note}</div>
        <div className="mc-setup" data-testid="mc-setup">Setup: {data.labels.setup}</div>
        <div className="mc-meta mc-dim">
          {data.sources?.length ? <>Sources: {data.sources.map((s) => s.label).join(' · ')} · </> : null}
          <span data-testid="mc-pass">{passStamp(data.pass)}</span>
        </div>
        {data.push?.gate_text ? <div className="mc-meta mc-dim" data-testid="mc-gate">🔔 Phone: {data.push.gate_text}</div> : null}
      </div>

      <div className="mc-filters">
        <div className="mc-filters__fams">
          <button type="button" className={`mc-fam${families.length === 0 ? ' is-active' : ''}`}
                  onClick={() => setFamilies([])}>All</button>
          {(tax?.families ?? []).map((f) => (
            <button key={f.key} type="button" aria-pressed={families.includes(f.key)}
                    className={`mc-fam${families.includes(f.key) ? ' is-active' : ''}`}
                    onClick={() => toggleFamily(f.key)}>
              {f.emoji} {f.label}
            </button>
          ))}
        </div>
        <div className="mc-filters__row">
          <label className="mc-filters__sel">modality{' '}
            <select value={modality} onChange={(e) => setModality(e.target.value)} aria-label="modality">
              <option value="">all</option>
              {(tax?.modalities ?? []).map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
            </select>
          </label>
          <label className="mc-filters__sel">area{' '}
            <select value={area} onChange={(e) => setArea(e.target.value)} aria-label="area">
              <option value="">all</option>
              {(tax?.areas ?? []).map((a) => <option key={a.key} value={a.key}>{a.label}</option>)}
            </select>
          </label>
          <label className="mc-filters__chk" title={tax?.high_impact_text}>
            <input type="checkbox" checked={highOnly} onChange={(e) => setHighOnly(e.target.checked)} /> High impact only
          </label>
          <span className="mc-filters__win">
            {MED_WINDOWS.map((d) => (
              <button key={d} type="button" className={`mc-win${d === days ? ' is-active' : ''}`}
                      onClick={() => onDays(d)}>{d}d</button>
            ))}
          </span>
        </div>
      </div>

      <details open className="mc-rollup">
        <summary>🔥 Where the news is — events and median moves by {rollBy}</summary>
        <div className="mc-rollup__bar">
          <button type="button" className={`mc-win${rollBy === 'modality' ? ' is-active' : ''}`}
                  onClick={() => setRollBy('modality')}>By modality</button>
          <button type="button" className={`mc-win${rollBy === 'area' ? ' is-active' : ''}`}
                  onClick={() => setRollBy('area')}>By area</button>
          <label className="mc-filters__sel">sort{' '}
            <select value={rollSort} onChange={(e) => setRollSort(e.target.value as RollSortKey)} aria-label="roll-up sort">
              <option value="n_events">events</option>
              <option value="median_day_pct">median day</option>
              <option value="median_ret_5d_pct">median 5d</option>
              <option value="median_ret_21d_pct">median 21d</option>
            </select>
          </label>
        </div>
        <RollTable rows={rollBy === 'modality' ? data.rollup?.by_modality ?? [] : data.rollup?.by_area ?? []} sortKey={rollSort} />
        {data.rollup?.note ? <div className="mc-note mc-note--small" data-testid="mc-roll-note">{data.rollup.note}</div> : null}
      </details>

      {total === 0 ? (
        <div className="mc-empty" data-testid="mc-empty">
          No classified medical events in the last {data.window_days ?? days} days — {passStamp(data.pass)}
          {passCounts(data.pass) ? ` (${passCounts(data.pass)})` : ''}
        </div>
      ) : groups.length === 0 ? (
        <div className="mc-empty" data-testid="mc-empty-filter">No events match these filters ({total} in the window).</div>
      ) : (
        groups.map((g) => (
          <section key={g.key} className="mc-fam-sec" data-testid={`mc-fam-${g.key}`}>
            <h4 className="mc-fam-sec__h">{g.emoji} {g.label} <span className="mc-dim">({g.events.length})</span></h4>
            {g.events.map((ev) => (
              <MedicalEventRow key={ev.event_key} ev={ev} modalityLabels={modLabels} areaLabels={areaLabels} />
            ))}
          </section>
        ))
      )}
    </div>
  );
}

export function MedicalCatalysts() {
  const [days, setDays] = useState<number>(30);
  const { data, error, loading } = useMedicalBoard(days);
  if (!data) {
    if (error) {
      return <div className="mc-board mc-empty" data-testid="mc-error">🧬 Medical catalysts unavailable ({error}).</div>;
    }
    return <div className="mc-board mc-dim">{loading ? 'Loading 🧬 medical catalysts…' : 'No data.'}</div>;
  }
  return (
    <>
      {error ? <div className="mc-dim" data-testid="mc-error-stale">Refresh failed ({error}) — showing the last payload.</div> : null}
      <MedicalBoardView data={data} days={days} onDays={setDays} />
    </>
  );
}
