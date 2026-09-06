/* DemandReentryPanel — S&P 500 names entering BACK INTO a demand zone.
 *
 * Ajay 2026-08-13: "update my Supply and demand page with stocks that entering
 * back in to demand zones and give me a scan button … scan only S&P 500."
 *
 * A transition read, not a snapshot: the name ran above the band, came back
 * down into it, and the trend still holds. Each row carries the written plan
 * (buy band / stop / target) and the reason it qualified.
 *
 * Backend: GET /supply-demand/demand-reentry, POST …/scan (force).
 * Configured price-structure method — NOT a book method, NOT advice.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { TickerLink } from './TickerLink';
import { useBounceRoom } from '../hooks/useBounceRoom';
import {
  ROOM_MIN_PCT, bounceLabel, compareBounceRoom, coverageNote, roomLabel,
  type BounceRoomRow, type RoomRead, type RoomState,
} from '../lib/bounceRoom';
import { DemandTrackRecord } from './DemandTrackRecord';
import {
  bandLabel, blockCount, breakEvenWinPct, freshnessLabel, level, liquidityView, money,
  planLine, retailView, rrBand, venueView, volLabel,
} from '../lib/zonePlan';
import type { ZoneMapPayload } from '../lib/zonePlan';
import { API } from '../lib/apiBase';
import { DemandScanProgress } from './DemandScanProgress';
import type { DemandScanProgress as DemandScanProgressPayload } from '../lib/demandScanProgress';
import { useDemandScanProgress } from '../hooks/useDemandScanProgress';
import { ZoneEdgeBoard } from './ZoneEdgeBoard';
import { useAlertedToday } from '../hooks/useAlertHistory';
import { AlertedTodayChip } from './AlertedTodayChip';
import { RulesInfo } from './RulesInfo';


/* The server's room block on every row (2026-09-05, GET /supply-demand/
 * demand-reentry?min_room=): % from the PRINT to the first UNBROKEN band
 * overhead — supply not broken under prev_close, plus demand bands above —
 * excluding the row's own entry band. `basis` says which print: the live
 * snapshot when one was available, else the scan's close. CLEAR = nothing
 * overhead; IN_BAND = the print is inside a band. Owner setting, not advice. */
type ServerRoom = {
  room_pct: number | null;
  /** unrounded pct the server compared (room_floor.room_block, 2026-09-05) */
  room_pct_raw?: number | null;
  target_lo: number | null;
  target_hi: number | null;
  target_kind: string | null;
  state: RoomState;
  basis: 'live' | 'scan';
};

type ReentryRow = ZoneMapPayload & { room?: ServerRoom | null };

type Payload = {
  rows: ReentryRow[];
  n: number;
  scanned: number;
  universe: number;
  universe_note: string;
  universe_is_sp500: boolean;
  universe_key?: string;
  universe_label?: string;
  universe_choices?: { key: string; label: string }[];
  /* Age in days when the constituent list came from an expired cache, else
   * null. `universe_is_sp500` only catches the loud failure (fell through to
   * the curated list); a stale cache holds the REAL constituents and so was
   * indistinguishable from a fresh list — it sat 76 days out of date without
   * a word on the page. See STALE_DAYS_WARN below. */
  universe_stale_days: number | null;
  universe_source: string | null;
  took_sec: number;
  as_of: string;
  cached: boolean;
  /* True while a cold scan runs in the background. A full sp1500 pass is ~2-3
   * minutes and the gateway cuts at ~100s, so the API returns immediately and
   * we poll instead of holding the request open. */
  warming?: boolean;
  /* Live counter carried on the warming payload, so the board poll alone shows
   * a moving number even before the faster progress poll lands. */
  progress?: DemandScanProgressPayload | null;
  /* Reward:risk floor applied to this payload, and how many rows it removed.
   * Ajay 2026-08-17 chose this over the three "buyers in control" candidates,
   * all of which failed measurement. */
  min_rr?: number;
  min_rr_default?: number;
  dropped_low_rr?: number;
  /* Room floor applied on the server (2026-09-05) and how many rows it hid.
   * Ajay, on TRU 0.3% under a supply band: "Why is it still in in Demand
   * page? There is only 0.5% room" → "stocks that have more room atleast
   * >5%". Same ALERT_MIN_ROOM_PCT the phone gate uses. */
  min_room?: number;
  dropped_low_room?: number;
  disclaimer: string;
};

/* Days of cache staleness past which the notice goes from muted to loud.
 * The cache TTL is 30 days, so any staleness at all already means the live
 * fetch is broken — but the S&P turns over only a few names a quarter, so a
 * month or two adrift is a footnote, not an alarm. Two quarters is an alarm. */
const STALE_DAYS_LOUD = 120;

/* One universe (Ajay 2026-08-25: "Remove all these themes and just do
 * default universe scan"). The picker went with it — the server folds every
 * legacy key (sp500, sp1500, ...) into the SEPA `full` alias, so old
 * bookmarked URLs still resolve to this same scan. */
const UNIVERSE = 'full';
const UNIVERSE_LABEL = 'Full universe (Russell 1000 ∪ S&P 1500 ∪ themes)';

/* Sort keys. 🪃 bounce · room leads (Ajay 2026-09-05: "for in demand Make sure
 * you sort stocks by bouncing off of demand zone and have big gap in to
 * supply"): names bouncing off a demand band first, then the biggest gap to the
 * first supply band overhead (nothing overhead = "open sky" leads), pending
 * coverage last. One rule shared with SEPA and Catalysts — lib/bounceRoom.ts.
 * R:R stays one click away: it is still the only cohort that backtested
 * positive, and the R:R FLOOR below applies whatever the sort.
 * Retail COUNT is deliberately not offered: a heavily traded name has more
 * retail prints whatever else is true, so it would mostly re-sort by volume.
 * Imbalance (direction) and participation (% of volume) carry information. */
const SORTS: { key: string; label: string }[] = [
  { key: 'bounce_room', label: '🪃 Bouncing · room to supply (default)' },
  { key: 'rr',       label: '🎯 R:R' },
  { key: 'retailimb',label: '🧍 Retail imbalance' },
  { key: 'retailpct',label: '🧍 Retail % of volume' },
  { key: 'dark',     label: '🟣 Off-exchange %' },
  { key: 'rvol',     label: '📊 Relative volume' },
  { key: 'fresh',    label: '🕐 Freshest re-entry' },
];

/* Reward:risk floor. 1.0 is the house default and it is NOT the backtest's best
 * cell — 1.25 measured better (exSPY -0.003% vs -0.101%), but excess-vs-SPY is
 * NOT monotone across the sweep, so the peak of a nine-cell search is a fitted
 * number, not a measured one. 1.0 is what "never risk more than the first
 * objective pays" implies, and that claim needs no backtest.
 * See docs/supply_demand/rr_floor.md. */
const RR_FLOORS: { key: string; label: string }[] = [
  { key: '0',    label: '🎯 R:R floor — none' },
  { key: '1',    label: '🎯 R:R ≥ 1 (default)' },
  { key: '1.5',  label: '🎯 R:R ≥ 1.5' },
  { key: '2',    label: '🎯 R:R ≥ 2' },
];

/* Room floor (Ajay 2026-09-05): "I need the same logic in Demand and deep
 * demand zone. So that there are stocks that have more room atleast >5%".
 * Two options only — the alert gate's floor (ALERT_MIN_ROOM_PCT = 5.0, owner
 * setting, mirrored as ROOM_MIN_PCT) or off. Not a tunable: the phone and the
 * board must describe the same list, and a third number would be one Ajay did
 * not give. Sent to the server as min_room on both the read and the scan. */
const ROOM_FLOORS: { key: string; label: string }[] = [
  { key: String(ROOM_MIN_PCT), label: `🧱 Room ≥ ${ROOM_MIN_PCT}% (default)` },
  { key: '0', label: '🧱 any room' },
];

/** The server's room block as the shared RoomRead so ONE label / ONE sort
 *  rule (lib/bounceRoom.ts) covers both the board's own read and the
 *  bounce-room hook's. ATR-days and the 52-week flag are not in the block;
 *  they are left null rather than guessed. */
function toRoomRead(sr: ServerRoom): RoomRead {
  const band = sr.target_lo != null && Number.isFinite(sr.target_lo)
    ? { kind: sr.target_kind === 'broken_support' ? 'broken_support' as const
             : sr.target_kind === 'demand' ? 'demand' as const : 'supply' as const,
        lo: sr.target_lo, hi: sr.target_hi ?? sr.target_lo, touches: 0 }
    : null;
  return { state: sr.state, room_pct: sr.room_pct, room_pct_raw: sr.room_pct_raw ?? null,
           atr_days: null, band, at_highs: false };
}

/** The read a row is sorted and labelled by: the server's room block when the
 *  payload carries one (it is measured from the same print the floor was
 *  applied on, so the page and the count agree), else the hook's row. The
 *  bounce half always comes from the hook — the server block has none. */
function mergedRead(r: ReentryRow, hookRow: BounceRoomRow | undefined): BounceRoomRow | undefined {
  if (!r.room) return hookRow;
  return {
    symbol: r.symbol.toUpperCase(),
    coverage: hookRow?.coverage ?? 'store',
    print: r.last_price,
    fresh: r.room.basis === 'live',
    bounce: hookRow?.bounce ?? null,
    room: toRoomRead(r.room),
  };
}

export function DemandReentryPanel() {
  const universe = UNIVERSE;
  const [sortKey, setSortKey] = useState<string>('bounce_room');
  const [minRr, setMinRr] = useState<string>('1');
  const [minRoom, setMinRoom] = useState<string>(String(ROOM_MIN_PCT));
  const [data, setData] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async (force: boolean) => {
    force ? setScanning(true) : setLoading(true);
    setErr(null);
    try {
      const u = `universe=${encodeURIComponent(universe)}&min_rr=${encodeURIComponent(minRr)}`
        + `&min_room=${encodeURIComponent(minRoom)}`;
      const r = force
        ? await fetch(`${API}/supply-demand/demand-reentry/scan?${u}`, {
            method: 'POST', credentials: 'include',
          })
        : await fetch(`${API}/supply-demand/demand-reentry?${u}`, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setLoading(false);
      setScanning(false);
    }
  }, [universe, minRr, minRoom]);

  useEffect(() => { load(false); }, [load]);

  /* Poll while a background scan is running. Stops as soon as rows arrive, and
   * on unmount, so switching tabs never leaves a timer behind. */
  useEffect(() => {
    if (!data?.warming) return undefined;
    const t = setInterval(() => { load(false); }, 10_000);
    return () => clearInterval(t);
  }, [data?.warming, load]);

  const busy = loading || scanning;

  /* The live counter. Ajay 2026-08-17: "its hard to tell if its scanning or
   * now". Runs whenever work is in flight — the background warm (`warming`) or
   * the inline Scan button, which holds its request open and so would otherwise
   * show nothing at all for the whole pass. */
  const progress = useDemandScanProgress(universe, Boolean(data?.warming) || scanning);

  /* Bounce / room-to-supply read for every row on the board — one POST per
   * scan result, shared 30 s cache (Ajay 2026-09-05). Drives the default sort
   * and the one-line 🪃 / room read under each plan. Coverage is printed, not
   * assumed: a row the server is still building shows "room pending" and
   * sorts last rather than disappearing. */
  const rowSymbols = useMemo(() => (data?.rows ?? []).map((r) => r.symbol), [data]);
  const { map: br, payload: brPayload } = useBounceRoom(rowSymbols);

  /* 🔔 "alerted HH:MM ET" — Ajay 2026-09-05: "Do we have the same logic in
   * back end demand for the ones that I get alerts. Would it be the same list
   * of stocks.." No: this board is a closed-bar scan with an R:R floor; the
   * phone gets live $1B+ names through the alert gate. The chip marks the
   * overlap so the two lists can be compared by eye. One read shared with the
   * zone-edge board above (same module cache). */
  const alerted = useAlertedToday();

  return (
    <section className="sd-section">
      {/* The minute-by-minute edge board sits on top (Ajay 2026-09-03: "add
        * #1 stocks in to Demand zone too ones breaking resistance"): names
        * within 1% of breaking their LAST supply band toward new highs, and
        * names inside / within 1% above a demand band. Its own fetch, its
        * own clock — the scan below is a closed-bar read and this is not. */}
      <ZoneEdgeBoard mode="both" />

      <div className="sepa-tab-help">
        <strong>🟢 Back in demand</strong> — S&P 500 names that ran up, then pulled
        back <em>into</em> a demand band they had already left, while the structure
        still holds. Sorted <strong>🪃 bouncing off demand WITH room first</strong>, then
        names with room, then bounces heading straight into a band (⛔), then the rest
        (Ajay 2026-09-05 asked for bouncing-off-demand names first, biggest gap to the
        first band overhead next — "open sky" means nothing overhead in the 1-year
        frame; R:R is still one click away in the sort menu). The <strong>Room</strong>{' '}
        floor is the phone's own gate — at least <strong>{ROOM_MIN_PCT}%</strong> from the
        live print to the first unbroken band overhead, measured on the server; a name
        already at its lid (TRU, 2026-09-05: 0.3% under a supply band sitting inside
        the demand zone) is hidden by default and counted, and "any room" shows it
        flagged. The <strong>R:R</strong> floor applies whatever the sort:
        measured over 737 walk-forward trades, <strong>36% of this board's wins hit
        target on the entry bar itself at a median 0.45R</strong> — plans whose
        objective was already inside the entry day's range. The floor removes those.
        It does <em>not</em> make the rule beat SPY (it doesn't, on 13.5 months of
        data); it removes bad trade construction. Bounce and room are a configured
        price-structure read (owner settings), not advice. <strong>Liq</strong> is
        average daily dollar volume (a great R:R you can't get filled in is not a
        trade) and <strong>dark</strong> is the share that printed off-exchange.
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap', margin: '0.6rem 0' }}>
        <select value={sortKey} onChange={(e) => setSortKey(e.target.value)}
                className="sepa-select" aria-label="Sort by"
                style={{ fontSize: '0.78rem', padding: '0.3rem 0.4rem' }}>
          {SORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
        </select>
        <select value={minRr} onChange={(e) => setMinRr(e.target.value)}
                disabled={busy} className="sepa-select" aria-label="Reward:risk floor"
                style={{ fontSize: '0.78rem', padding: '0.3rem 0.4rem' }}
                title="A plan that risks more than its first objective pays is not a trade. 36% of this board's backtested wins hit target on the ENTRY bar at a median 0.45R — this removes those.">
          {RR_FLOORS.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
        </select>
        <select value={minRoom} onChange={(e) => setMinRoom(e.target.value)}
                disabled={busy} className="sepa-select" aria-label="Room floor"
                style={{ fontSize: '0.78rem', padding: '0.3rem 0.4rem' }}
                title={`Room from the live print to the first unbroken band overhead (supply not broken under yesterday's close, plus demand bands above), excluding this row's own entry band. The phone only pages a name with ≥ ${ROOM_MIN_PCT}%; this board now applies the same floor. TRU 2026-09-05: 0.3% room, R:R 0.09 from the print.`}>
          {ROOM_FLOORS.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
        </select>
        <button className="sepa-btn" onClick={() => load(true)} disabled={busy}>
          {scanning ? 'Scanning…' : '🔄 Scan'}
        </button>
        {data && (
          <span className="mono" style={{ fontSize: '0.72rem', opacity: 0.75 }}>
            {data.n} in demand · {data.scanned}/{data.universe} scanned
            {!!data.dropped_low_rr && (
              <span title={`Removed by the R:R ≥ ${data.min_rr} floor. A plan that risks more than its first objective pays is not a trade.`}>
                {' '}· {data.dropped_low_rr} below R:R {data.min_rr}
              </span>
            )}
            {!!data.dropped_low_room && (
              <span title={`Hidden by the room floor: fewer than ${data.min_room ?? ROOM_MIN_PCT}% from the live print to the first unbroken band overhead. Pick "any room" to see them flagged ⛔.`}>
                {' '}· {data.dropped_low_room} hidden: room &lt; {data.min_room ?? ROOM_MIN_PCT}%
              </span>
            )}
            {data.took_sec ? ` · ${data.took_sec}s` : ''}
            {data.cached ? ' · cached' : ''}
            {sortKey === 'bounce_room' && coverageNote(brPayload) && (
              <span title="How many of the rows have a bounce / room read yet. Pending rows sort last and say 'room pending' — they are not missing, just not built yet.">
                {' '}· 🪃 {coverageNote(brPayload)}
              </span>
            )}
          </span>
        )}
        {/* ℹ️ Rules — this board's picks / stops / alerts from GET
          * /supply-demand/rules (Ajay 2026-09-06); the panel drops to its own
          * line under the toolbar when open. */}
        <RulesInfo section="in_demand" />
      </div>

      {data && !data.universe_is_sp500 && (
        <div className="sepa-err" style={{ marginBottom: '0.6rem' }}>
          ⚠️ {data.universe_note} — this is NOT the full universe. Results below
          cover the curated fallback list instead.
        </div>
      )}

      {/* Stale-but-real constituents. Different failure from the one above and
        * it needs a different volume: these ARE the S&P 500, just frozen on the
        * day the live fetch broke, so the list is ~99% right and the scan is
        * still worth reading. Muted note by default; escalates past
        * STALE_DAYS_LOUD, where enough quarterly index turnover has stacked up
        * to actually miss names. */}
      {data && data.universe_is_sp500 && data.universe_stale_days != null && (
        <div
          className={data.universe_stale_days > STALE_DAYS_LOUD ? 'sepa-err' : undefined}
          style={{
            marginBottom: '0.6rem',
            fontSize: '0.74rem',
            ...(data.universe_stale_days > STALE_DAYS_LOUD ? {} : {
              color: 'var(--cm-slate)',
              border: '1px solid var(--cm-border, #2a3244)',
              borderRadius: '6px',
              padding: '0.45rem 0.6rem',
            }),
          }}
        >
          🕰️ Constituent list is <strong>{data.universe_stale_days} days old</strong> — the
          live S&P 500 fetch is failing, so this is the last good snapshot. Real
          constituents, but index adds/drops since then are missed.
        </div>
      )}

      {err && <div className="sepa-err">Scan failed: {err}</div>}

      {/* The live scan. Replaces the static sentence that read the same whether
        * the scan was 3% through or had died three minutes ago. */}
      {(Boolean(data?.warming) || scanning) && (
        <DemandScanProgress
          progress={progress ?? data?.progress}
          running
          universeLabel={data?.universe_label ?? UNIVERSE_LABEL}
        />
      )}

      {/* Fallback for the first render, before the first poll lands. */}
      {busy && !data && !progress ? (
        <div style={{ color: 'var(--cm-slate)', padding: '1rem' }}>
          Scanning for demand-zone re-entries…
        </div>
      ) : null}

      {data && data.rows.length === 0 && !busy && !data.warming && (
        <div style={{ color: 'var(--cm-slate)', padding: '1rem' }}>
          Nothing is pulling back into demand right now across {data.scanned}{' '}
          {data.universe_label ?? 'S&P 500'} names. That is a real answer, not an empty list — press Scan after the close
          to re-check.
        </div>
      )}

      {data && data.rows.length > 0 && (
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          {[...data.rows].sort((a, b) => {
            const n = (v: number | null | undefined, d = -Infinity) => (v == null ? d : v);
            switch (sortKey) {
              /* The shared rule (lib/bounceRoom.ts): bouncing WITH room, then
               * room ok (CLEAR / ≥ 5%), then bounces into supply (⛔), then the
               * rest; inside a group CLEAR, then biggest room %, IN_BAND under
               * any room, no read last. The server's room block (same print the
               * floor ran on) is preferred over the hook's when present. The
               * comparator tiebreaks on the READ's symbol, which is '' for an
               * unloaded row — so the board's own symbol settles it and the
               * order never flickers while the read loads. */
              case 'bounce_room': {
                const c = compareBounceRoom(mergedRead(a, br.get(a.symbol.toUpperCase())),
                                            mergedRead(b, br.get(b.symbol.toUpperCase())));
                return c !== 0 ? c : a.symbol.localeCompare(b.symbol);
              }
              case 'retailimb': return n(b.retail?.imbalance_pct) - n(a.retail?.imbalance_pct);
              case 'retailpct': return n(b.retail?.retail_pct_of_volume) - n(a.retail?.retail_pct_of_volume);
              case 'dark':      return n(b.venues?.dark_pct) - n(a.venues?.dark_pct);
              case 'rvol':      return n(b.liquidity?.rvol) - n(a.liquidity?.rvol);
              case 'fresh':     return n(a.bars_since_above, Infinity) - n(b.bars_since_above, Infinity);
              default:          return n(b.plan?.rr) - n(a.plan?.rr);
            }
          }).map((r) => {
            const rr = rrBand(r.plan?.rr);
            const be = r.breakeven_win_pct ?? breakEvenWinPct(r.plan?.rr);
            const liq = liquidityView(r.liquidity);
            const ven = venueView(r.venues);
            const ret = retailView(r.retail);
            const brRow = mergedRead(r, br.get(r.symbol.toUpperCase()));
            const bounce = bounceLabel(brRow);
            /* Server block first (2026-09-05): it is the read the floor was
             * applied on. A read taken from the scan's close rather than a
             * live print says so — a 0.3% room on a stale print is a different
             * claim from 0.3% now. */
            const roomBase = brRow?.coverage === 'pending' && !r.room ? '' : roomLabel(brRow);
            const room = roomBase && r.room?.basis === 'scan' ? `${roomBase} · scan close` : roomBase;
            return (
              <div key={r.symbol} style={{
                padding: '0.6rem 0.75rem', borderRadius: 10,
                background: 'rgba(148,163,184,0.07)',
                borderLeft: `3px solid ${liq.warn ? '#d97706' : '#22c55e'}`,
              }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {/* tab="supply" (was "setup", 2026-08-17): Ajay 2026-09-03
                    * wants every SEPA click on Supply / Demand — the band this
                    * row is standing in is drawn there. */}
                  <TickerLink ticker={r.symbol} fromLabel="Back in Demand"
                          tab="supply" fromKey="supply-demand" />
                  <AlertedTodayChip symbol={r.symbol} hit={alerted.get(r.symbol.toUpperCase())} />
                  <span style={{ fontSize: '0.78rem', opacity: 0.8 }}>{r.name}</span>
                  <span className="mono" style={{ fontSize: '0.74rem' }}>{money(r.last_price)}</span>
                  <span style={{
                    fontSize: '0.62rem', padding: '1px 7px', borderRadius: 999,
                    background: 'rgba(34,197,94,0.16)', color: '#22c55e', fontWeight: 600,
                  }}>
                    {freshnessLabel(r.bars_since_above)}
                  </span>
                  {r.fell_from_pct != null && (
                    <span className="mono" style={{ fontSize: '0.7rem', opacity: 0.7 }}>
                      fell from +{r.fell_from_pct}%
                    </span>
                  )}
                  <span className="mono" title="Swing-low direction + 50-day slope — the falling-knife guard that replaced the Minervini trend template."
                        style={{ fontSize: '0.7rem', opacity: 0.7, marginLeft: 'auto' }}>
                    lows {r.structure?.trend ?? '—'}
                    {r.structure?.ma50_rising != null && ` · 50d ${r.structure.ma50_rising ? '↑' : '↓'}`}
                  </span>
                </div>
                <div className="mono" style={{ fontSize: '0.74rem', marginTop: '0.3rem' }}>
                  {planLine(r.plan, r.zone_broken)}
                </div>
                {/* 🪃 bounce · room line (Ajay 2026-09-05). Bounce = session low
                  * touched a demand band / broken-supply shelf in the last 5
                  * sessions and the print is 3% / one ATR above it; room = % to
                  * the bottom of the first supply band overhead (same read as
                  * the Portfolio sell side). Owner settings, not advice. */}
                {(bounce || room || (brRow?.coverage === 'pending' && !r.room)) && (
                  <div className="mono" style={{ fontSize: '0.72rem', marginTop: '0.2rem', opacity: 0.85 }}
                       title={`Bounce: the session low touched a demand band or broken-supply shelf within the last 5 sessions and price is now at least 3% / one ATR above it. Room: % from the print to the first unbroken band overhead (${r.room?.target_kind ? `here a ${r.room.target_kind} band, ` : ''}${r.room ? `measured on the ${r.room.basis === 'live' ? 'live print' : "scan's close"}` : 'bounce-room read'}); open sky = nothing overhead in the 1-year frame; ⛔ = under the ${ROOM_MIN_PCT}% floor the phone gate uses. Configured price-structure read (owner settings), not advice.`}>
                    {bounce && <span style={{ color: '#22c55e', fontWeight: 600 }}>{bounce}</span>}
                    {bounce && (room || (brRow?.coverage === 'pending' && !r.room)) && ' · '}
                    {room.startsWith('⛔') ? <span style={{ color: '#ef4444', fontWeight: 600 }}>{room}</span> : room}
                    {brRow?.coverage === 'pending' && !r.room && (
                      <span style={{ opacity: 0.55 }}>room pending</span>
                    )}
                  </div>
                )}
                {/* A row here has already passed the broken-band guard, so this
                    only fires when the band held on a closing basis and the wick
                    under it still ran the stop. Ajay 2026-08-17, NBIX. */}
                {r.plan?.stop_recently_hit && (
                  <div style={{ fontSize: '0.7rem', color: '#ef4444', marginTop: '0.2rem' }}>
                    ⚠️ stop {level(r.plan.stop)} already traded through
                    {r.plan.bars_since_stop_hit === 0 ? ' today'
                      : r.plan.bars_since_stop_hit === 1 ? ' yesterday'
                      : r.plan.bars_since_stop_hit != null ? ` ${r.plan.bars_since_stop_hit}d ago` : ''}
                  </div>
                )}
                <div style={{ display: 'flex', gap: '0.9rem', flexWrap: 'wrap',
                              fontSize: '0.7rem', opacity: 0.85, marginTop: '0.25rem' }}>
                  <span title="Reward divided by risk, and the win rate you'd need just to break even at it.">
                    <strong style={{ color: rr.tone === 'good' ? '#22c55e' : rr.tone === 'poor' ? '#ef4444' : 'inherit' }}>
                      {rr.label}
                    </strong>
                    {be != null && <span style={{ opacity: 0.75 }}> · need {be}% wins</span>}
                  </span>
                  <span title={`Average 50-day dollar volume. ${liq.warn ? 'Thin tape — the spread can eat the edge before the setup works.' : 'Enough tape to get filled.'}`}>
                    liq <strong style={{ color: liq.color }}>{liq.label}</strong>
                    <span style={{ opacity: 0.7 }}> {volLabel(r.liquidity?.avg_dollar_vol_50)}</span>
                  </span>
                  <span title={ret.title}>
                    retail <strong style={{ color: ret.color }}>{ret.label}</strong>
                    {r.retail?.divergence && (
                      <span title={r.retail.divergence.note} style={{ cursor: 'help' }}> ⚡</span>
                    )}
                  </span>
                  <span title={ven.title}>
                    dark <strong style={{ color: ven.color }}>{ven.label}</strong>
                    {blockCount(r.venues) != null && (
                      <span style={{ opacity: 0.7 }}> · {blockCount(r.venues)} blk</span>
                    )}
                  </span>
                  <span style={{ opacity: 0.7 }}>
                    band {bandLabel(r.entry_zone)} · {r.entry_zone?.touches ?? 0}×
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <DemandTrackRecord universe={universe} />

      {data && (
        <p style={{ fontSize: '0.68rem', opacity: 0.55, marginTop: '0.7rem' }}>
          {data.disclaimer}
        </p>
      )}
    </section>
  );
}
