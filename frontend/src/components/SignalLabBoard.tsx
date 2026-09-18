/* SignalLabBoard — the Signal Lab's working surface (controls + tiles +
 * feeds), shared by the standalone /signal-lab page and the Chart Maps
 * ⚡ Signals tab (Ajay 2026-09-01: "add the signals tab inside chart maps").
 *
 * Ajay 2026-09-01: "calculate entries with a buy or sell indicator on a
 * stock ticker I add to a new page ... interface like GainzAlgo ... same
 * concepts from what we build with ORB, Liquidity grab, BOS ... custom
 * tickers on demand like the session tab but more real time feedback."
 *
 * Presentation borrows GainzAlgo's UI conventions (BUY/SELL labels printed
 * at the signal candle, stop/target attached, non-repainting closed-bar
 * signals). The math is this app's own — daytrading/signal_lab.py — and
 * SMC stays flagged as uncited convention.
 *
 * Realtime = polling: 1-minute candles close once a minute, so the board
 * refreshes every 45s while a session is on (premarket/regular/afterhours)
 * and sits still when the market is closed. Whoever asked LAST owns the
 * screen (the Support-tab race lesson, 2026-08-31).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { API } from '../lib/apiBase';
import { useSignalWatchlist } from '../hooks/useSignalWatchlist';
import { PatternChart } from './PatternChart';
import { GrowthChip } from './GrowthChip';
import { ExplosiveChip } from './ExplosiveChip';
import { EnterableChip } from './EnterableChip';
import { BandStructureChip } from './BandStructureChip';
import { HiddenCount } from './HiddenCount';
import { useEnterableFilter, useEnterablePartition } from '../hooks/useEnterableFilter';
import { ExplosiveFirstToggle } from './ExplosiveFirstToggle';
import { useBounceRoom } from '../hooks/useBounceRoom';
import { useExplosiveOrder } from '../hooks/useExplosiveOrder';
import { SymbolSearch } from './SymbolSearch';
import { PremarketEntry } from './PremarketEntry';
import type { CmTile } from '../lib/chartMaps';

type Feed = {
  t: string; kind: string; label: string;
  price?: number | null; stop?: number | null; target?: number | null; why: string;
};
type Row = {
  symbol: string; error?: string; tile?: CmTile; feed?: Feed[];
  latest?: Feed | null; session?: string; last_bar_et?: string;
};
type Payload = {
  rows: Row[]; count: number; session_state: string;
  method_note: string; as_of: string;
};

const POLL_MS = 45_000;
export function SignalLabBoard() {
  // ONE watchlist for the app (Ajay 2026-09-07: "one click and add to signals
  // tab" from every board) — the store fetches the account's list once, the
  // cards' + Signals buttons write to it, this board renders it.
  const wl = useSignalWatchlist();
  const symbols = wl.symbols;
  const held = useMemo(() => new Set(wl.held), [wl.held]);
  const [data, setData] = useState<Payload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [explosiveFirst, setExplosiveFirst] = useState(false);
  /* 🧨 One bounce-room POST for the board's 12 names; the chip and the
   * opt-in ordering both read it. */
  const rowSymbols = useMemo(() => (data?.rows || []).map((r) => r.symbol).filter(Boolean), [data]);
  const room = useBounceRoom(rowSymbols);
  const rows = useExplosiveOrder(data?.rows || [], (r) => r.symbol, room.map, explosiveFirst);
  /* 🎯 The enterable cut over the watchlist order (2026-09-15). <PremarketEntry>
   * above is deliberately NOT touched — it serves its own grades from
   * supply_demand/premarket_entry and answers a different question. */
  const { enterableOnly, kind, setEnterableOnly, ignoreReasons, toggleReason } = useEnterableFilter();
  const part = useEnterablePartition(rows, (r) => r.symbol, room.map, enterableOnly);
  const seq = useRef(0);
  const timer = useRef<number | null>(null);

  const load = useCallback((quiet = false) => {
    if (!symbols.length) { setData(null); return; }
    const my = ++seq.current;
    if (!quiet) setLoading(true);
    fetch(`${API}/day/signal-lab/board?symbols=${encodeURIComponent(symbols.join(','))}`,
          { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j: Payload) => {
        if (my !== seq.current) return;
        setData(j); setErr(null); setLoading(false);
      })
      .catch((e) => {
        if (my !== seq.current) return;
        setErr(String(e?.message ?? e)); setLoading(false);
      });
  }, [symbols]);

  useEffect(() => { load(); }, [load]);

  // poll only while a session is on — closed tape produces no new closed bars
  useEffect(() => {
    if (timer.current) window.clearInterval(timer.current);
    if (!data || data.session_state === 'closed') return undefined;
    timer.current = window.setInterval(() => load(true), POLL_MS);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [data?.session_state, load]);

  const add = wl.add;
  const remove = wl.remove;

  return (
    <div className="slab">
      {/* Ajay 2026-09-09: "I wanna see this category in the signals page with a
       * section for it." It LEADS the tab because it answers the question he
       * opens the page with — what can I enter right now — while everything
       * below is the per-ticker tape. Collapsible, so the watchlist is one
       * click away when he does not want it. */}
      <PremarketEntry />

      <div className="slab-controls">
        <SymbolSearch onAdd={add} placeholder="Add a ticker to watch — e.g. TSLA, IREN, SNDK" />
        <div className="slab-chips">
          {symbols.map((s) => (
            <span key={s} className="slab-chip" title={held.has(s) ? 'In your portfolio — rides the board by default' : undefined}>
              {held.has(s) ? '💼 ' : ''}{s}
              {held.has(s) ? null : (
                <button type="button" className="slab-chip__x" aria-label={`Remove ${s}`}
                        onClick={() => remove(s)}>×</button>
              )}
            </span>
          ))}
        </div>
      </div>

      {!symbols.length ? (
        <div className="cm-note">Add a ticker above — the board watches up to 12 at once.</div>
      ) : null}
      {loading && !data ? <div className="cm-note">Reading the tape…</div> : null}
      {err ? <div className="cm-note cm-note-warn">Signal lab unavailable: {err}</div> : null}

      {data ? (
        <>
          <div className="slab-meta">
            {/* 🧨 opt-in ordering over the board's own bounce-room read —
                default OFF, so the watchlist order he typed is what he sees. */}
            <ExplosiveFirstToggle checked={explosiveFirst} onChange={setExplosiveFirst} />
            <span className={`slab-state slab-state--${data.session_state}`}>
              {data.session_state === 'regular' ? 'LIVE — refreshing every 45s'
                : data.session_state === 'closed' ? 'MARKET CLOSED — last session shown'
                : `${data.session_state.toUpperCase()} — refreshing every 45s`}
            </span>
          </div>
          {enterableOnly && kind !== 'n/a' ? (
            <HiddenCount hidden={part.hidden} unread={part.unread}
                         hiddenByReason={part.hiddenByReason} enabled kind={kind}
                         reasons={part.reasons} unhidden={part.unhidden}
                         onToggleReason={toggleReason} unhideCount={ignoreReasons.size}
                         onShowAll={() => setEnterableOnly(false)} />
          ) : null}
          {/* 🪜 No row on this list came back with a band read — say so once, the
              way the 🎯 n/a tabs do, instead of showing no chip anywhere and
              letting it read as a board where the read silently stopped. The
              sentence is SERVED (bounce_room.BAND_STRUCTURE_NO_READ). */}
          {room.payload?.band_structure_coverage?.note ? (
            <div className="cm-hidden-count" data-testid="band-structure-note">
              🪜 {room.payload.band_structure_coverage.note}
            </div>
          ) : null}
          <div className="cm-grid">
            {part.rows.map((r) => r.tile ? (
              <div key={r.symbol} className="slab-cell">
                {/* 🪜 Ajay 2026-09-16 "in all chartmaps tabs". The Signal Lab
                    endpoint never runs chart_maps/board.attach_band_structure, so
                    the row's SERVED read is put on the tile the one renderer
                    already reads it from. */}
                <PatternChart tvTf="daily" study={room.payload?.explosive_study}
                              bandStudy={room.payload?.band_structure_study}
                              tile={{ ...r.tile,
                                      band_structure: room.map.get(String(r.symbol).toUpperCase())?.band_structure ?? null }} />
                {r.latest ? (
                  <div className={`slab-latest slab-latest--${r.latest.kind}`}>
                    <b>{r.latest.label}</b> {r.latest.t} @ ${r.latest.price?.toFixed(2)}
                    {r.latest.stop != null ? <> · stop ${r.latest.stop.toFixed(2)}</> : null}
                    {r.latest.target != null ? <> · target ${r.latest.target.toFixed(2)}</> : null}
                  </div>
                ) : (
                  <div className="slab-latest slab-latest--none">no entry signal this session</div>
                )}
                <ul className="slab-feed">
                  {(r.feed || []).slice(0, 5).map((f, i) => (
                    <li key={`${f.t}-${f.kind}-${i}`} className={`slab-feed__row slab-feed__row--${f.kind}`}>
                      <span className="mono">{f.t}</span>
                      <b>{f.label}</b>
                      <span className="slab-feed__why">{f.why}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div key={r.symbol} className="cm-note cm-note-warn">
                {r.symbol}
                {/* 🚀 also on the Explosive Growth board. The tiles above get
                    this from PatternChart; the no-data rows are the only place
                    a Signals name renders without one. */}
                <GrowthChip symbol={r.symbol} className="cm-badge" />
                <ExplosiveChip className="cm-badge" study={room.payload?.explosive_study}
                               read={room.map.get(String(r.symbol).toUpperCase())?.explosive} />
                <EnterableChip className="cm-badge"
                               read={room.map.get(String(r.symbol).toUpperCase())?.enterable} />
                <BandStructureChip className="cm-badge" study={room.payload?.band_structure_study}
                                   read={room.map.get(String(r.symbol).toUpperCase())?.band_structure} />
                : {r.error || 'no data'}
              </div>
            ))}
          </div>
          <p className="rw__note">{data.method_note}</p>
        </>
      ) : null}
    </div>
  );
}
