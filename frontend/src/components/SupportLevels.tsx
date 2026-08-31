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
  FALLBACK_TIMEFRAMES, FALLBACK_WINDOWS, bandLabel, distanceLabel,
  evidenceLabel, headline, money, parseTf, sourceLabel,
  normalizeSymbol, parseWindow, priceAsOf, recencyLabel, recentCount,
  shortHistoryNote, supportQuery, testedCount,
  type SupportLevel, type SupportPayload,
} from '../lib/supportLevels';

type Props = {
  symbol: string;
  window: string;
  /** Bar timeframe (Ajay 2026-08-29). Optional so existing callers that
   *  only pass a zoom keep the daily behaviour they had. */
  tf?: string;
  onSymbol: (sym: string) => void;
  onWindow: (win: string) => void;
  onTf?: (tf: string) => void;
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

export function SupportLevels({ symbol, window: win, tf, onSymbol, onWindow,
                               onTf }: Props) {
  const [data, setData] = useState<SupportPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    const sym = normalizeSymbol(symbol);
    if (!sym) { setData(null); setErr(null); return; }
    setLoading(true);
    setErr(null);
    try {
      const r = await fetch(
        `${API}/chart-maps/support?${supportQuery({ symbol: sym, window: win, tf })}`,
        { credentials: 'include', cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    } finally {
      setLoading(false);
    }
  }, [symbol, win, tf]);

  useEffect(() => { void load(); }, [load]);

  // The server's own list once it lands, so retiring a window backend-side does
  // not need a frontend deploy.
  const windows = data?.windows?.length ? data.windows : FALLBACK_WINDOWS;
  const timeframes = data?.timeframes?.length ? data.timeframes : FALLBACK_TIMEFRAMES;
  const tradeLevels = data?.trade_levels || [];
  const orb = data?.opening_range || null;
  const bullish = data?.bullish_patterns || null;
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
        {onTf && (
          <label className="cm-ctl" title="Which bars the structure is read from">
            Timeframe
            <select value={parseTf(tf, timeframes)}
                    onChange={(e) => onTf(e.target.value)}>
              {timeframes.map((t) => (
                <option key={t.key} value={t.key}>{t.label}</option>
              ))}
            </select>
          </label>
        )}
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

          {tradeLevels.length > 0 ? (
            <div className="sl-trades">
              <h4>Entry &amp; stop, computed per band</h4>
              <div className="sl-scroll">
                <table className="sl-table">
                  <thead>
                    <tr>
                      <th>Band</th><th>What</th><th>Side</th><th>Entry</th>
                      <th>Stop</th><th>Target 1</th><th>R:R</th><th>Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tradeLevels.filter((t) => t.trade).map((t, i) => (
                      <tr key={`${t.source}-${t.lo}-${i}`}>
                        <td>{money(t.lo)}–{money(t.hi)}</td>
                        <td>{sourceLabel(t)}</td>
                        <td>{t.trade?.side}</td>
                        <td>{money(t.trade?.entry)}</td>
                        <td>{money(t.trade?.stop)}</td>
                        <td>
                          {money(t.trade?.target1)}
                          <span className="sl-basis"> {t.trade?.target_basis}</span>
                        </td>
                        <td>{t.trade?.rr != null ? `${t.trade.rr}R` : '—'}</td>
                        <td>{t.trade?.risk_pct != null ? `${t.trade.risk_pct}%` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="cm-note">
                Entry is the edge price reaches first; the stop sits beyond the
                far edge by {data.atr ? `${(data.atr).toFixed(2)} ATR-scaled` : 'a'}
                {' '}buffer, because a stop resting exactly on a visible level is
                the liquidity that gets taken. Size off the stop distance, not
                off conviction.
              </p>
            </div>
          ) : null}

          {orb ? (
            <p className="cm-note">
              <strong>Opening range</strong> ({orb.minutes}m, {orb.session}):{' '}
              {money(orb.lo)}–{money(orb.hi)}. Above it buyers won the session's
              first auction; below it sellers did.
            </p>
          ) : null}

          {bullish && (bullish.patterns || []).length > 0 ? (
            <div className="sl-patterns">
              <h4>Bullish patterns on this timeframe</h4>
              <ul>
                {(bullish.patterns || []).map((p, i) => (
                  <li key={`${p.kind}-${i}`}>
                    <strong>{p.label || p.kind}</strong>
                    {p.confirmed ? ' · confirmed' : ' · forming'}
                    {p.entry != null && (
                      <> · entry {money(p.entry)} · stop {money(p.stop)}
                        {p.target != null && <> · target {money(p.target)}</>}</>
                    )}
                    {!p.cited && <span className="sl-basis"> · no cited source</span>}
                  </li>
                ))}
              </ul>
              {bullish.stats_transfer === false ? (
                <p className="cm-note cm-note-warn">
                  Shape only — Bulkowski&apos;s hit rates and throwback stats were
                  measured on DAILY bars and do not transfer to this timeframe.
                </p>
              ) : null}
              {(bullish.out_of_range || []).length > 0 ? (
                <p className="cm-note">
                  Out of range on this timeframe (needs more bars than the window
                  holds): {(bullish.out_of_range || []).join(', ').replace(/_/g, ' ')}.
                </p>
              ) : null}
            </div>
          ) : null}

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
