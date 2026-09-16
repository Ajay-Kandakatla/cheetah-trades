/* HoldingsBoard — 📁 My holdings on Chart Maps (2026-09-14).
 *
 * Ajay: "I about the new portfolio stocks I want to run these against them."
 *
 * One Support-tab tile per name on his Portfolio page, fetched in parallel
 * from /chart-maps/support (the same payload the Support tab draws, so the
 * bands, the AMD / Keltner reads and the SMC blocks cannot differ between the
 * two surfaces), then decorated with his cost and his typed stop. Worst
 * position first. The overlay ledger is the same one every other tile surface
 * mounts, on the same localStorage key.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { PatternChart } from './PatternChart';
import OverlayLegend from './OverlayLegend';
import { GrowthChip } from './GrowthChip';
import { ExplosiveChip } from './ExplosiveChip';
import { EnterableChip } from './EnterableChip';
import { ExplosiveFirstToggle } from './ExplosiveFirstToggle';
import { useBounceRoom } from '../hooks/useBounceRoom';
import { useExplosiveOrder } from '../hooks/useExplosiveOrder';
import { filterTile, loadHidden, presentGroups, saveHidden, studiesWanted } from '../lib/chartOverlays';
import { supportQuery } from '../lib/supportLevels';
import {
  HOLDINGS_WINDOWS, decorateHoldingTile, holdingsWindow, sortHoldings, type HoldingLike,
} from '../lib/holdingsBoard';
import type { CmTile } from '../lib/chartMaps';
import type { BandStructureStudy } from '../lib/bandStructure';

type TileRead = {
  tile: CmTile; last?: number | null; error?: string | null;
  /* 🪜 The band-structure VERDICT as /chart-maps/support served it beside
   * this name's tile. Carried per read rather than fetched once: every tile on
   * this board comes from its own request, and the banner must come off the
   * same responses the chips came off. */
  bandStudy?: BandStructureStudy | null;
  /* 🪜 The SERVED "no band read" sentence for THIS name, when the
   * response came back with no ceiling and no floor at all
   * (chart_maps/board.band_structure_coverage -> bounce_room
   * .BAND_STRUCTURE_NO_READ). Per read, because each position is its own
   * request: one name the store has not warmed must say so without silencing
   * the six beside it that read fine. */
  bandNote?: string | null;
};

export default function HoldingsBoard({ days }: { days?: number | null }) {
  const [rows, setRows] = useState<HoldingLike[] | null>(null);
  const [rowsErr, setRowsErr] = useState<string | null>(null);
  const [win, setWin] = useState<string>(() => holdingsWindow(days));
  const [reads, setReads] = useState<Record<string, TileRead>>({});
  const [loading, setLoading] = useState(false);

  const [hiddenOverlays, setHiddenOverlays] = useState<Set<string>>(() => loadHidden());
  const hiddenRef = useRef(hiddenOverlays);
  hiddenRef.current = hiddenOverlays;
  const [studiesOn, setStudiesOn] = useState<boolean>(() => studiesWanted(hiddenRef.current));

  const toggleOverlay = (key: string) => {
    setHiddenOverlays((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      saveHidden(next);
      // Crossing the studies boundary changes what the SERVER must send —
      // refetch on the crossing only, like the Support tab.
      setStudiesOn(studiesWanted(next));
      return next;
    });
  };

  // His holdings — the manual rows on the Portfolio page.
  useEffect(() => {
    let alive = true;
    setRowsErr(null);
    fetch(`${API}/portfolio/holdings`, { credentials: 'include', cache: 'no-store' })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        const list: HoldingLike[] = (d?.rows || [])
          .filter((h: any) => h && h.symbol)
          .map((h: any) => ({ ...h, symbol: String(h.symbol).toUpperCase() }));
        if (alive) setRows(list);
      })
      .catch((e) => { if (alive) { setRows([]); setRowsErr(String(e?.message ?? e)); } });
    return () => { alive = false; };
  }, []);

  const seq = useRef(0);
  const load = useCallback(async () => {
    if (!rows || !rows.length) { setReads({}); return; }
    const my = ++seq.current;
    setLoading(true);
    const out: Record<string, TileRead> = {};
    await Promise.all(rows.map(async (h) => {
      try {
        const r = await fetch(
          `${API}/chart-maps/support?${supportQuery({ symbol: h.symbol, window: win })}`
          + (studiesOn ? '&studies=true' : ''),
          { credentials: 'include', cache: 'no-store' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const p = await r.json();
        if (p?.error || !p?.tile) {
          out[h.symbol] = { tile: null as any, error: String(p?.error || 'no chart') };
          return;
        }
        out[h.symbol] = {
          tile: p.tile as CmTile, last: p.last_price ?? null,
          bandStudy: (p.band_structure_study as BandStructureStudy | null) ?? null,
          bandNote: (p.band_structure_coverage?.note as string | null) ?? null,
        };
      } catch (e: any) {
        out[h.symbol] = { tile: null as any, error: String(e?.message ?? e) };
      }
    }));
    if (my !== seq.current) return;
    setReads(out);
    setLoading(false);
  }, [rows, win, studiesOn]);

  useEffect(() => { void load(); }, [load]);

  const ordered = useMemo(() => {
    if (!rows) return [];
    return sortHoldings(rows.map((h) => ({ h, last: reads[h.symbol]?.last ?? h.current_price ?? null })));
  }, [rows, reads]);

  const tiles = useMemo(() => ordered
    .map(({ h, last }) => {
      const rd = reads[h.symbol];
      if (!rd || rd.error || !rd.tile) return null;
      return { h, tile: filterTile(decorateHoldingTile(rd.tile, h, last), hiddenOverlays) };
    })
    .filter(Boolean) as Array<{ h: HoldingLike; tile: CmTile }>, [ordered, reads, hiddenOverlays]);

  /* 🧨 One bounce-room POST for the holdings on screen; the chip on the
   * no-chart rows and the opt-in ordering read that one map. */
  const rowSymbols = useMemo(() => ordered.map(({ h }) => h.symbol).filter(Boolean), [ordered]);
  const room = useBounceRoom(rowSymbols);
  const [explosiveFirst, setExplosiveFirst] = useState(false);
  const shownTiles = useExplosiveOrder(tiles, (t) => t.tile.symbol, room.map, explosiveFirst);

  /* 🪜 One banner for the board, off the reads that came back. Every response
   * carries the same served verdict (band_structure.measured_verdict()), so the
   * first one that has a headline is the board's; nothing is invented when not
   * one response carried it. The 🪜 chip rides on each tile, and the banner
   * saying `MEASURED.status` is `no_signal` has to ride with it. */
  const bandStudy = useMemo(() => {
    for (const { h } of ordered) {
      const st = reads[h.symbol]?.bandStudy;
      if (st?.headline) return st;
    }
    return null;
  }, [ordered, reads]);

  /* 🪜 THE SILENT BLANK, closed (critique J2, 2026-09-16). The chip
   * renders nothing for a name with no bands, so a position the zone store
   * does not carry drew a chart here with no Bands line and NO REASON — while
   * the ten row boards, which build the doc on demand, served the read for that
   * same name on the same day. Demonstrated on BTBT, which he owns. The names
   * are listed and the SENTENCE IS THE SERVED ONE those boards print
   * (bounce_room.band_structure_no_read_note): nothing is worded here, so this
   * board can never say it differently from them, and a response that carried
   * no note prints no line.
   *
   * ONE LINE PER SENTENCE (critique 5, BLOCKING). The note is no longer one
   * fixed string: a name UNDER the store's cap floor is told no refresh brings
   * it a read, a name the store is still warming is told to wait, and a name
   * whose cap nobody can see is told the neutral truth. Holdings is the one
   * board that can show all three at once, so the names are GROUPED BY THE
   * SENTENCE THEY WERE SERVED — printing the first name's note over all of
   * them is exactly the lie this fix removes (BTBT, $562.6M, was being told to
   * wait for a refresh that cannot come). Insertion order = his row order. */
  const bandGroups = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const { h } of ordered) {
      const note = reads[h.symbol]?.bandNote;
      if (!note) continue;
      const at = m.get(note);
      if (at) at.push(h.symbol); else m.set(note, [h.symbol]);
    }
    return [...m.entries()];
  }, [ordered, reads]);

  const failed = ordered.filter(({ h }) => reads[h.symbol]?.error);
  const present = useMemo(() => presentGroups(tiles.map((t) => t.tile)), [tiles]);

  if (rows === null) return <div className="cm-foot mono">Loading your holdings…</div>;
  if (!rows.length) {
    return (
      <div className="cm-foot mono">
        {rowsErr ? `Could not read your holdings (${rowsErr}).`
                 : 'No holdings on your Portfolio page yet — add one there and it shows up here.'}
      </div>
    );
  }

  return (
    <div className="cm-holdings">
      <div className="cm-controls">
        <label className="cm-ctl">
          Window
          <select aria-label="Holdings window" value={win}
                  onChange={(e) => setWin(e.target.value)}>
            {HOLDINGS_WINDOWS.map((w) => (
              <option key={w.key} value={w.key}>{w.label}</option>
            ))}
          </select>
        </label>
        <span className="cm-foot mono">
          {rows.length} holding{rows.length === 1 ? '' : 's'} · worst position first
          {loading ? ' · loading charts…' : ''}
        </span>
        <ExplosiveFirstToggle checked={explosiveFirst} onChange={setExplosiveFirst} />
      </div>

      <OverlayLegend present={present} hidden={hiddenOverlays} onToggle={toggleOverlay} />

      {/* No scope note and no sort_unavailable note: this board is not ordered
        * by the 🪜 key — it is worst position first, which is his ordering and
        * stays his ordering. Only the read and its status are shown. */}
      {bandStudy?.headline ? (
        <div className="cm-note cm-band-study" data-testid="hb-band-structure-study">
          <strong>{bandStudy.headline}</strong>
          {bandStudy.body ? <p>{bandStudy.body}</p> : null}
          {bandStudy.fallback_note ? <p>{bandStudy.fallback_note}</p> : null}
          {bandStudy.limits ? <p className="cm-dim">{bandStudy.limits}</p> : null}
        </div>
      ) : null}

      {bandGroups.map(([note, syms]) => (
        <p className="cm-note" data-testid="hb-band-structure-no-read" key={note}>
          🪜 {syms.join(', ')} — {note}
        </p>
      ))}

      <div className="cm-grid">
        {shownTiles.map(({ tile }) => (
          <PatternChart key={`${tile.symbol}-${win}`} tile={tile}
                        study={room.payload?.explosive_study}
                        bandStudy={bandStudy} />
        ))}
      </div>

      {failed.length ? (
        <div className="cm-foot mono">
          {failed.map(({ h }) => (
            // A name with no chart still says whether it is on the 🚀 growth
            // list (Ajay 2026-09-11: "ALL TABS IN CHART MAPS").
            <div key={h.symbol}>
              <b>{h.symbol}</b> <GrowthChip symbol={h.symbol} />
              {' '}<ExplosiveChip study={room.payload?.explosive_study}
                                  read={room.map.get(String(h.symbol).toUpperCase())?.explosive} />
              {/* 🎯 chip only. This board never hides a position: the enterable
                  filter answers "can I enter this now", and a name he already
                  owns is a name he has to keep looking at whatever the read
                  says. The chip tells him it is not an entry; the row stays. */}
              {' '}<EnterableChip read={room.map.get(String(h.symbol).toUpperCase())?.enterable} />
              {' '}{reads[h.symbol]?.error}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
