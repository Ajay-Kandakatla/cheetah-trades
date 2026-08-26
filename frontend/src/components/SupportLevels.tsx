/* SupportLevels — the Chart Maps tab that answers "where is support on <ticker>
 * at <zoom>".
 *
 * Ajay 2026-08-19: "a new feature where I can look at support levels on demand
 * … toggle a drop down to check montly vs 3 months vs 6 months demand zones …
 * I should be able to a search of all the Ticker I do today … I want look at
 * recent support levels as well."
 *
 * The other three Chart Maps tabs are boards fed by a scan. This one has no
 * list: you type a ticker and it computes. So it owns its own fetch rather than
 * riding the page's board loader — the shapes have nothing in common past the
 * tile.
 *
 * The chart is the SAME `PatternChart` the boards use, on the same tile
 * contract, so the two surfaces cannot drift apart. Underneath it is a table,
 * because a support level is a number you place a stop against and a chart
 * cannot be read to the cent.
 *
 * Ticker search reuses `SymbolSearch` (the /symbol-search typeahead already
 * wired for the watch table) rather than growing a second one.
 */
import { useCallback, useEffect, useState } from 'react';
import { API } from '../lib/apiBase';
import { PatternChart } from '../components/PatternChart';
import { SymbolSearch } from '../components/SymbolSearch';
import {
  FALLBACK_WINDOWS, bandLabel, distanceLabel, evidenceLabel, headline,
  normalizeSymbol, parseWindow, priceAsOf, recencyLabel, recentCount,
  shortHistoryNote, supportQuery, testedCount,
  type SupportLevel, type SupportPayload,
} from '../lib/supportLevels';

type Props = {
  symbol: string;
  window: string;
  onSymbol: (sym: string) => void;
  onWindow: (win: string) => void;
};

function LevelRow({ lv, side }: { lv: SupportLevel; side: 'support' | 'overhead' }) {
  return (
    <tr className={`sl-row${lv.recent ? ' sl-row-recent' : ''}`
                   + `${lv.tested ? '' : ' sl-row-untested'}`}>
      <td className="sl-band">{bandLabel(lv)}</td>
      <td className="sl-dist">{distanceLabel(lv, side)}</td>
      <td className="sl-ev">{evidenceLabel(lv)}</td>
      <td className="sl-when">
        {lv.recent ? <span className="sl-dot" aria-hidden="true">●</span> : null}
        {recencyLabel(lv)}
      </td>
    </tr>
  );
}

function LevelTable({ title, levels, side, empty }: {
  title: string; levels: SupportLevel[]; side: 'support' | 'overhead'; empty: string;
}) {
  return (
    <div className="sl-table-wrap">
      <h3 className="sl-table-title">{title}</h3>
      {levels.length ? (
        <table className="sl-table">
          <thead>
            <tr>
              <th>Band</th><th>Distance</th><th>Evidence</th><th>Last tested</th>
            </tr>
          </thead>
          <tbody>
            {levels.map((lv) => (
              <LevelRow key={`${lv.lo}-${lv.hi}-${lv.origin}`} lv={lv} side={side} />
            ))}
          </tbody>
        </table>
      ) : (
        <p className="sl-empty">{empty}</p>
      )}
    </div>
  );
}

export function SupportLevels({ symbol, window: win, onSymbol, onWindow }: Props) {
  const [data, setData] = useState<SupportPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    const sym = normalizeSymbol(symbol);
    if (!sym) { setData(null); setErr(null); return; }
    setLoading(true);
    setErr(null);
    try {
      const r = await fetch(`${API}/chart-maps/support?${supportQuery({ symbol: sym, window: win })}`,
        { credentials: 'include', cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    } finally {
      setLoading(false);
    }
  }, [symbol, win]);

  useEffect(() => { void load(); }, [load]);

  // The server's own list once it lands, so retiring a window backend-side does
  // not need a frontend deploy.
  const windows = data?.windows?.length ? data.windows : FALLBACK_WINDOWS;
  const sym = normalizeSymbol(symbol);
  const supports = data?.supports || [];
  const overhead = data?.overhead || [];
  const shortNote = shortHistoryNote(data);

  return (
    <div className="sl-panel">
      <div className="sl-controls">
        <div className="sl-search">
          <SymbolSearch
            placeholder="Search any ticker — e.g. NVDA, DHI, MOS"
            onAdd={(s) => onSymbol(normalizeSymbol(s))}
          />
        </div>
        <label className="cm-ctl">
          Zoom
          <select value={parseWindow(win, windows)}
                  onChange={(e) => onWindow(e.target.value)}>
            {windows.map((w) => (
              <option key={w.key} value={w.key}>{w.label}</option>
            ))}
          </select>
        </label>
      </div>

      {!sym ? (
        <div className="cm-note">
          Search a ticker above to see where its support sits. The zoom changes
          the answer on purpose — a 1-month read finds the level this week's
          trade is standing on, a 1-year read finds the structural floor.
        </div>
      ) : null}

      {loading && !data ? <div className="cm-note">Reading {sym}…</div> : null}
      {err ? (
        <div className="cm-note cm-note-err">Couldn't load {sym} — {err}</div>
      ) : null}

      {data?.error ? <div className="cm-note cm-note-warn">{data.error}</div> : null}

      {data && !data.error && data.tile ? (
        <>
          <div className="sl-head">
            <h2 className="sl-sym">
              {data.symbol}
              {data.name ? <span className="sl-name">{data.name}</span> : null}
            </h2>
            <div className="sl-meta">
              <span className="sl-zoom">{data.window_label}</span>
              <span className="sl-recent">
                {recentCount(supports)} of {supports.length} touched in the last{' '}
                {data.recent_bars} sessions
              </span>
              <span className="sl-recent">
                {testedCount(supports)} of {supports.length} turned at more than once
              </span>
            </div>
          </div>

          <p className="sl-headline">{headline(data)}</p>
          {shortNote ? <p className="cm-note cm-note-warn">{shortNote}</p> : null}

          <div className="sl-chart">
            <PatternChart tile={data.tile} height={320} />
          </div>

          <div className="sl-tables">
            <LevelTable title="Support below" levels={supports} side="support"
                        empty={`No band below price in the last ${data.window_label} — `
                               + 'nothing here to place a stop under. Try a longer zoom.'} />
            <LevelTable title="Overhead" levels={overhead} side="overhead"
                        empty="Nothing overhead in this window — clear above." />
          </div>

          {data.levels_capped ? (
            <p className="cm-note">
              Showing the nearest levels only — there is more structure in this
              window than the table lists.
            </p>
          ) : null}

          <p className="sl-legend">
            <span className="sl-dot" aria-hidden="true">●</span>
            touched inside the last {data.recent_bars} sessions ·
            {' '}<em>single low</em> = price turned there once, so it is a bar
            you can see rather than a floor that has held. Bands are where the
            turns clustered; a stop goes under the low, not at the midpoint.
          </p>
          {(() => {
            const stamp = priceAsOf(data.as_of, data.data_through, Date.now());
            return stamp ? <p className="cm-note sl-asof">{stamp}</p> : null;
          })()}
          {data.note ? <p className="cm-note">{data.note}</p> : null}
          {data.disclaimer ? (
            <div className="cm-disclaimer">{data.disclaimer}</div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

export default SupportLevels;
