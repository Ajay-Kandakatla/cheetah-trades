/* EmaFramesBoard — 〰️ 9 EMA · W/M on Chart Maps (2026-09-23).
 *
 * Ajay: "Also a new tab for 9EMA lines on our charts for weekly charts and
 * monthly charts please".
 *
 * ONE tab, one frame at a time. Weekly is the default view (zero clicks);
 * Monthly is one click. Two stacked sections would cost zero clicks too, but
 * it would put a name's weekly bar and its monthly bar a full grid apart — the
 * comparison he is actually making is the same chart at two bar sizes, and a
 * toggle keeps them in the same place on screen.
 *
 * THE COHORT IS NOT NEW. It is the ⚡ Signals watchlist — his own tickers,
 * merged with anything he holds, exactly the list the Signals tab already
 * runs on (GET /day/signal-lab/watchlist). No universe pass is started here
 * and none can be: one cached daily frame per name, resampled. Signals reads
 * those names on 1-minute candles; this reads the same names on weekly and
 * monthly bars.
 *
 * NOT MEASURED. Nothing about a 9 EMA on weekly or monthly bars has been
 * tested on this universe — no study, no interval, no out-of-sample. This
 * board draws; it orders nothing, hides nothing, gates nothing and pushes
 * nothing.
 *
 * NO ORDERING TOGGLE, and that is deliberate:
 * there is no read on this board to rank by.
 * The cohort IS his ⚡ Signals watchlist and the tiles come back in
 * that list's own order. The 🚀 / 🧨 / 🎯 chips on each tile are that NAME's
 * reads, carried so the tab is not a dead end — they are not this board's, and
 * sorting on one would hand a drawing surface a preference it cannot defend.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { PatternChart } from './PatternChart';
import OverlayLegend from './OverlayLegend';
import { GrowthChip } from './GrowthChip';
import { ExplosiveChip } from './ExplosiveChip';
import { EnterableChip } from './EnterableChip';
import { useBounceRoom } from '../hooks/useBounceRoom';
import { filterTile, loadHidden, presentGroups, saveHidden } from '../lib/chartOverlays';
import {
  EMA_FRAMES, EMA_FRAME_LABEL, countLine, emaFramesQuery, emptyReason,
  formingNote, frameStat, loadEmaFrame, saveEmaFrame,
  type EmaFrame, type EmaFrameRead,
} from '../lib/emaFrames';
import type { CmTile } from '../lib/chartMaps';

export default function EmaFramesBoard() {
  const [frame, setFrame] = useState<EmaFrame>(() => loadEmaFrame());
  const [symbols, setSymbols] = useState<string[] | null>(null);
  const [listErr, setListErr] = useState<string | null>(null);
  const [reads, setReads] = useState<Record<string, EmaFrameRead>>({});
  /* ONE bounce-room POST for every name on screen — the 🚀 growth and 🧨
   * explosive chips read that one map. A chip that fetched per tile would be
   * the 2026-09-21 AMD mistake again (80 tiles x 1 call = 65 s), and both
   * chip contracts grep for exactly this shape. The chips are a name's read,
   * not this tab's: nothing here is ordered, filtered or gated by them. */
  const room = useBounceRoom(symbols || []);
  const [loading, setLoading] = useState(false);

  const [hidden, setHidden] = useState<Set<string>>(() => loadHidden());
  /* THE TAB'S OWN FAMILY IS FORCED VISIBLE HERE, the 🌀 KC / AMD rule
   * (chartOverlays.tabFamily): a tab that exists to draw one overlay must not
   * open as bare candles because that box happens to be unticked. His saved
   * choice is untouched — every other tab still honours it — and the ledger
   * shows the box locked so the reason is on screen, not in a comment. */
  const LOCKED = useMemo(() => new Set(['ema9']), []);
  const shown = useMemo(() => {
    if (!hidden.has('ema9')) return hidden;
    const next = new Set(hidden);
    next.delete('ema9');
    return next;
  }, [hidden]);
  const toggleOverlay = (key: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      saveHidden(next);
      return next;
    });
  };

  const pickFrame = (f: EmaFrame) => {
    setFrame(f);
    saveEmaFrame(f);
  };

  // His ⚡ Signals watchlist — the cohort, read once per mount.
  useEffect(() => {
    let alive = true;
    fetch(`${API}/day/signal-lab/watchlist`, { credentials: 'include', cache: 'no-store' })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        const list: string[] = (d?.symbols || [])
          .filter((s: unknown) => typeof s === 'string' && s.trim())
          .map((s: string) => s.trim().toUpperCase());
        if (alive) setSymbols(list);
      })
      .catch((e) => { if (alive) { setSymbols([]); setListErr(String(e?.message ?? e)); } });
    return () => { alive = false; };
  }, []);

  const seq = useRef(0);
  const load = useCallback(async () => {
    if (!symbols || !symbols.length) { setReads({}); return; }
    const my = ++seq.current;
    setLoading(true);
    const out: Record<string, EmaFrameRead> = {};
    await Promise.all(symbols.map(async (sym) => {
      try {
        const r = await fetch(`${API}/chart-maps/ema-frames?${emaFramesQuery(sym, frame)}`,
                              { credentials: 'include', cache: 'no-store' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        out[sym] = (await r.json()) as EmaFrameRead;
      } catch (e: any) {
        out[sym] = { symbol: sym, frame, tile: null, error: String(e?.message ?? e) };
      }
    }));
    if (my !== seq.current) return;
    setReads(out);
    setLoading(false);
  }, [symbols, frame]);

  useEffect(() => { void load(); }, [load]);

  const rows = useMemo(
    () => (symbols || []).map((s) => reads[s]).filter(Boolean) as EmaFrameRead[],
    [symbols, reads]);
  const tiles = useMemo(
    () => rows.map((r) => r.tile).filter(Boolean) as CmTile[], [rows]);
  const groups = useMemo(() => presentGroups(tiles), [tiles]);
  const empty = emptyReason(symbols, listErr);
  // The frame sentence is the SERVED one, off the first tile that arrived —
  // the page never describes a resample it did not receive.
  const what = frameStat(tiles[0] || null);

  return (
    <div>
      {/* The house toggle markup (the same one Back in Demand's phase tabs
        * use), so the tab needs no CSS of its own. */}
      <div className="cm-phase" role="tablist" aria-label="Bar size">
        {EMA_FRAMES.map((f) => (
          <button key={f} type="button" role="tab" aria-selected={f === frame}
                  className={`cm-phase-btn${f === frame ? ' cm-phase-on' : ''}`}
                  onClick={() => pickFrame(f)}>
            {EMA_FRAME_LABEL[f]}
          </button>
        ))}
        {what ? <span className="cm-phase-hint">{what}</span> : null}
      </div>

      <div className="cm-note">
        The 9 EMA on {frame} bars, on your ⚡ Signals watchlist. Nothing about a
        9 EMA on weekly or monthly bars has been measured on this universe — no
        study, no interval, no out-of-sample — so this board draws and nothing
        else: it orders nothing, hides nothing and alerts nothing.
      </div>

      <OverlayLegend present={groups} hidden={shown} locked={LOCKED}
                     onToggle={toggleOverlay} />

      {empty ? <div className="cm-note" data-testid="ema-empty">{empty}</div> : null}

      <div className={`cm-grid${loading ? ' cm-grid-stale' : ''}`}
           aria-busy={loading || undefined}>
        {rows.map((r) => {
          if (!r.tile) {
            return (
              <div key={r.symbol} className="cm-note cm-note-err"
                   data-testid={`ema-error-${r.symbol}`}>
                <strong>{r.symbol}</strong> — {r.error || 'no chart'}
              </div>
            );
          }
          const note = formingNote(r);
          const roomRow = room.map.get(r.symbol);
          return (
            <div key={`${r.symbol}-${r.frame}`}>
              <div className="cm-tile-chips" data-testid={`ema-chips-${r.symbol}`}>
                <GrowthChip symbol={r.symbol} />
                {' '}<ExplosiveChip study={room.payload?.explosive_study}
                                    read={roomRow?.explosive} />
                {' '}<EnterableChip read={roomRow?.enterable} />
              </div>
              <PatternChart tile={filterTile(r.tile, shown)} />
              {note ? (
                <div className="cm-note" data-testid={`ema-forming-${r.symbol}`}>{note}</div>
              ) : null}
              {r.curve_reason ? (
                <div className="cm-note" data-testid={`ema-nocurve-${r.symbol}`}>
                  {r.curve_reason}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      {tiles.length ? (
        <div className="cm-foot">{countLine(tiles.length, (symbols || []).length, frame)}</div>
      ) : null}
    </div>
  );
}
