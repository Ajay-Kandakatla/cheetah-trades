/* PromoCircuit — tickers recently tagged by the pump/alert accounts we
 * caught seeding the 8/31–9/1 movers (provenance study 2026-09-01).
 *
 * Ajay: "auto-mark tickers recently tagged by these known alert accounts,
 * plus a 13G/resale-shelf EDGAR watch ... I need the same logic at least
 * as watch list." A tag from the roster is the PROMOTION, not foresight:
 * SEEDING rows are being loaded RIGHT NOW (the early warning), RAN/DUMPED
 * rows show how the last campaign ended. Never a buy list.
 *
 * Reads /catalysts/promo-circuit; the roster lives in
 * backend/catalysts/promo_circuit.py (user-editable, like fundTiers).
 */
import React, { Fragment, useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { API } from '../lib/apiBase';
import { TickerLink } from './TickerLink';
import { Link } from 'react-router-dom';
import { MiniTape, PromoTagTape } from './PromoTagTape';
import { mdy, type AddEvent } from './RussellWatch';

type TaggedBy = {
  handle: string; tier: 'S' | 'A' | 'B';
  last_tagged_at: string; n_messages?: number | null; sample?: string | null;
};
type EdgarFlag = { form: string; filing_date: string; url?: string | null } | null;
/* The five tells (Ajay 2026-09-02) — computed on the 10-min board, carried
 * unchanged onto the live rows. null = not read yet / nothing there. */
export type RussellJoin = { board: 'add_r2000' | 'promote_r1000'; market_cap?: number | null; add_event?: AddEvent | null; first_seen?: string | null; as_of?: string | null };
export type SalesRead = { tier: string | null; growth_yoy_pct: number | null; prior_yoy_pct?: number | null; accelerating?: boolean | null; score?: number | null; reason?: string | null; source?: string };
export type CatalystRead = { n_48h: number; n_bullish: number; n_bearish: number; verdict: 'REAL' | 'THIN' | 'NONE';
  top: { title: string; url?: string | null; publisher?: string | null; published_utc?: string | null; tone: string } | null };
export type EightK = { form: string; filing_date: string; url?: string | null; items: string[]; n_14d?: number };
export type SecRollup = { n_30d: number; forms: string[]; latest: { form: string; filing_date: string; url?: string | null }; n_form4: number; has_offering: boolean };
type Tells = { russell?: RussellJoin | null; sales?: SalesRead | null; catalyst?: CatalystRead | null; eightk?: EightK | null; sec?: SecRollup | null };
type Row = Tells & {
  /** shares × last close from the weekly shares cache; null = unknown (kept visible, says 'cap n/a'). */
  market_cap?: number | null;
  ticker: string; accounts: TaggedBy[]; best_tier: 'S' | 'A' | 'B';
  first_tagged_at: string; last_tagged_at?: string | null; days_since_first_tag: number;
  pct_since_tag: number | null; max_gain_pct: number | null;
  drop_from_peak_pct: number | null; last_close: number | null;
  status: 'SEEDING' | 'RAN' | 'DUMPED' | 'QUIET' | 'UNKNOWN';
  edgar: { owner_stake: EdgarFlag; shelf: EdgarFlag };
};
type RosterEntry = {
  handle: string; tier: 'S' | 'A' | 'B'; note: string; evidence: string;
  /** Measured Aug-2026 track record (hit rate, median fade) — present once audited. */
  audit?: string | null;
};
type Payload = {
  rows: Row[]; n_tickers: number; roster: RosterEntry[];
  sweep: { last_sweep_at: string | null; accounts_failed: string[] } | null;
  method_note: string; as_of: string;
};

const TIER_COLORS: Record<string, string> = {
  S: 'var(--negative, #e5484d)',
  A: '#e8a33d',
  B: 'var(--muted, #8b8fa3)',
};
const TIER_HINTS: Record<string, string> = {
  S: 'Documented pump-circuit tell — tags preceded verticals on silent tapes',
  A: 'Alert-room promoter — sells access / victory-laps; their crowd IS the move',
  B: 'Watchlist reposter — context only, never penalizes the score',
};
const STATUS_META: Record<Row['status'], { label: string; hint: string }> = {
  SEEDING: { label: '🌱 SEEDING', hint: 'Tagged, hasn’t run — the promotion is loaded. Expect the pop; chasing it makes you the exit.' },
  RAN: { label: '🚀 RAN', hint: 'Already popped ≥30% since the first tag — late.' },
  DUMPED: { label: '💥 DUMPED', hint: 'Ran, then gave back ≥40% from the peak — the circuit exited.' },
  QUIET: { label: '💤 QUIET', hint: 'Old tag that never ran.' },
  UNKNOWN: { label: '· no price', hint: 'No daily bars for this symbol yet.' },
};

const pct = (v: number | null | undefined) =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`;

/* StockTwits profile — every handle on this tab is a StockTwits account. */
export const accountUrl = (handle: string) => `https://stocktwits.com/${encodeURIComponent(handle)}`;

function AccountChip({ a }: { a: TaggedBy }) {
  const c = TIER_COLORS[a.tier] ?? TIER_COLORS.B;
  return (
    <a
      className="pcw__acct mono"
      href={accountUrl(a.handle)} target="_blank" rel="noreferrer"
      style={{ borderColor: c, color: c }}
      title={`${TIER_HINTS[a.tier] ?? ''}${a.sample ? `\n“${a.sample}”` : ''}\nOpen @${a.handle} on StockTwits`}
    >
      {a.tier}·@{a.handle}
    </a>
  );
}

function EdgarChips({ e }: { e: Row['edgar'] }) {
  if (!e?.owner_stake && !e?.shelf) return <span className="pcw__dim">—</span>;
  return (
    <span className="pcw__edgar">
      {e.owner_stake && (
        <a
          className="pcw__flag pcw__flag--owner"
          href={e.owner_stake.url ?? undefined}
          target="_blank" rel="noreferrer"
          title="Beneficial-owner stake filed ≤14d — the one genuinely predictive public signal in the study (GPRO’s 13G)"
        >
          🧾 {e.owner_stake.form} {e.owner_stake.filing_date}
        </a>
      )}
      {e.shelf && (
        <a
          className="pcw__flag pcw__flag--shelf"
          href={e.shelf.url ?? undefined}
          target="_blank" rel="noreferrer"
          title="Fresh shelf/offering plumbing ≤30d — dilution tell (NWGL resale, SSM direct, LIDR ATM)"
        >
          🪧 {e.shelf.form} {e.shelf.filing_date}
        </a>
      )}
    </span>
  );
}

/* "Sep 1 · 3:20p ET" — when the tag actually landed (Ajay 2026-09-02: "show me
 * when it was tagged with a date"). */
export function tagStamp(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const day = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'America/New_York' });
  const t = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/New_York' })
    .replace(' AM', 'a').replace(' PM', 'p');
  return `${day} · ${t} ET`;
}


/* Most recent announcement first (Ajay 2026-09-02: "Sort by most recent announcement"). */
export function sortRecent<T extends { first_tagged_at: string | null; last_tagged_at?: string | null }>(rows: T[]): T[] {
  const at = (r: T) => Date.parse(r.last_tagged_at ?? r.first_tagged_at ?? '') || 0;
  return [...rows].sort((a, b) => at(b) - at(a));
}

export const symbolUrl = (t: string) => `https://stocktwits.com/symbol/${encodeURIComponent(t)}`;

/* Symbol + where to go next: the StockTwits stream and our SEPA page landing
 * on the Supply / Demand tab (Ajay 2026-09-02: "I wanna land on the sepa page
 * with supply tab open"). */
/* Valuation floor (Ajay 2026-09-03: "filter out any company that its
 * valuation is less than a billion"; lowered the same afternoon: "In the PROMO
 * tab I do not want to see anything in less then 700 million"). Unknown caps
 * stay visible and say so — hiding what we cannot size would hide real names,
 * not just shells. */
export const MIN_CAP_USD = 7e8;
export const passesCapFloor = (cap: number | null | undefined, on: boolean) => !on || cap == null || cap >= MIN_CAP_USD;
export const fmtCapShort = (v: number | null | undefined) =>
  v == null ? 'cap n/a' : v >= 1e12 ? `$${(v / 1e12).toFixed(1)}T` : v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${(v / 1e6).toFixed(0)}M`;
const CAP_FLOOR_KEY = 'pcw.capFloor';
export function readCapFloorPref(): boolean {
  try { return localStorage.getItem(CAP_FLOOR_KEY) !== 'off'; } catch { return true; }
}
export function writeCapFloorPref(on: boolean): void {
  try { localStorage.setItem(CAP_FLOOR_KEY, on ? 'on' : 'off'); } catch { /* private mode */ }
}

function SymCell({ ticker, cap }: { ticker: string; cap?: number | null }) {
  return (
    <>
      <TickerLink ticker={ticker} tab="supply" fromLabel="Promo circuit" />
      <span className="pcw__links mono">
        <a href={symbolUrl(ticker)} target="_blank" rel="noreferrer" title={`$${ticker} on StockTwits`}>ST↗</a>
        <Link to={`/sepa/${encodeURIComponent(ticker)}?tab=supply`} title={`${ticker} on our SEPA page, Supply / Demand tab`}>SEPA</Link>
      </span>
      <span className={`pcw__cap mono pcw__dim${cap != null && cap < MIN_CAP_USD ? ' is-small' : ''}`}
            title={cap == null ? 'market cap unknown — no shares data yet' : `market cap ≈ ${fmtCapShort(cap)} (shares × last close)`}>{fmtCapShort(cap)}</span>
    </>
  );
}

export type RoomRead = {
  state: 'UNPRICED' | 'CLEAR' | 'IN_BAND' | 'NEAR' | 'ROOM' | 'PENDING' | 'UNAVAILABLE';
  room_pct: number | null; band: { lo: number; hi: number; kind: string } | null; error?: string;
};
const band$ = (b: { lo: number; hi: number }) => `$${b.lo.toFixed(2)}–${b.hi.toFixed(2)}`;
/* Room to run — same read as the Portfolio 🎯 table: % to the first band overhead. */
export function RoomCell({ room }: { room?: RoomRead | null }) {
  if (!room || room.state === 'PENDING') return <td className="og__num mono pcw__dim" title="zones computing — fills in on the next refresh">…</td>;
  if (room.state === 'UNAVAILABLE') return <td className="og__num mono pcw__dim" title={room.error ?? 'zone engine unavailable'}>—</td>;
  if (room.state === 'UNPRICED') return <td className="og__num mono pcw__dim">—</td>;
  if (room.state === 'CLEAR') return <td className="og__num mono pcw__room is-clear" title="nothing overhead in the 1-year read — unknown, not unlimited">clear</td>;
  const b = room.band!;
  const kind = b.kind === 'broken_support' ? ' (support it broke)' : '';
  if (room.state === 'IN_BAND') return <td className="og__num mono pcw__room is-in" title={`inside the band ${band$(b)}${kind} — the sell zone is here`}>in band<span className="pcw__room-band">{band$(b)}</span></td>;
  return (
    <td className={`og__num mono pcw__room ${room.state === 'NEAR' ? 'is-near' : 'is-room'}`}
        title={`${room.room_pct?.toFixed(1)}% from the live print to the bottom of ${band$(b)}${kind}`}>
      +{room.room_pct?.toFixed(1)}%<span className="pcw__dim pcw__room-band">→ {band$(b)}</span>
    </td>
  );
}

export type LiveRow = {
  ticker: string; status: string; best_tier: 'S' | 'A' | 'B'; accounts: string[];
  alertable?: boolean; pct_since_tag_live?: number | null;
  first_tagged_at?: string | null; last_tagged_at?: string | null;
  days_since_last_tag: number | null; last: number | null; prev_close: number | null;
  rth_close?: number | null; day_pct: number | null; ah_pct?: number | null;
  session: string; pct_since_tag: number | null;
  /** Room to run: first overhead band + % to it (daily-bar zones, 30-min cache). */
  room?: RoomRead | null;
  max_gain_pct?: number | null;
  edgar?: Row['edgar'] | null;
  market_cap?: number | null;
} & Tells;
export type LivePayload = {
  rows: LiveRow[]; n: number; alert_threshold_pct: number; alert_handles?: string[];
  live: { state: string; refresh_sec: number; as_of: string | null }; method_note: string;
  room_note?: string;
};
const CLOSED_POLL_SEC = 300;


/* ⚡ Live — Ajay 2026-09-02: "Give me a real time page.. with percentage".
 * Every tagged name priced off one snapshot, pre/post market included,
 * sorted by today's move; re-reads every 30s while the tape is open. */
export function usePromoLive() {
  const [data, setData] = useState<LivePayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const seq = useRef(0);
  const load = useCallback(() => {
    const my = ++seq.current;
    fetch(`${API}/catalysts/promo-circuit/live`, { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => { if (my === seq.current) { setData(j); setErr(null); } })
      .catch((e) => { if (my === seq.current) setErr(String(e?.message ?? e)); });
  }, []);
  useEffect(() => { load(); }, [load]);
  /* Server cadence while open; slow tick while closed so it wakes at 04:00 ET
   * on its own and retries after an error. A failed poll keeps the table. */
  const refresh = data?.live?.refresh_sec || 0;
  useEffect(() => {
    const id = setInterval(load, (refresh || CLOSED_POLL_SEC) * 1000);
    return () => clearInterval(id);
  }, [refresh, load]);
  return { data, err };
}


/* ── One table for every view — Ajay 2026-09-02: "I want both be the same with
 * dates and new columns and give me sort functionality on possible columns".
 * A board row and a live row for the same ticker merge into one UnifiedRow;
 * the ⚡ table is the live-priced set sorted by today's move, the board tables
 * are split by status and sorted by the latest tag. Every column that holds a
 * value is click-sortable: first click = the column's natural order, second =
 * the reverse, third = back to the table's default. Empty cells always sort
 * last. */
export type UnifiedRow = Tells & {
  market_cap?: number | null;
  ticker: string; status: Row['status']; best_tier: Row['best_tier'];
  accounts: (TaggedBy | { handle: string })[];
  first_tagged_at: string | null; last_tagged_at: string | null; days_since_first_tag: number | null;
  pct_since_tag: number | null; max_gain_pct: number | null; edgar: Row['edgar'] | null;
  live: LiveRow | null;
};
const tells = (x: Tells): Tells => ({ russell: x.russell ?? null, sales: x.sales ?? null, catalyst: x.catalyst ?? null, eightk: x.eightk ?? null, sec: x.sec ?? null });
export function unifyBoard(r: Row, lv?: LiveRow | null): UnifiedRow {
  return { ...tells(r), market_cap: r.market_cap ?? null, ticker: r.ticker, status: r.status, best_tier: r.best_tier, accounts: r.accounts,
    first_tagged_at: r.first_tagged_at, last_tagged_at: r.last_tagged_at ?? null, days_since_first_tag: r.days_since_first_tag,
    pct_since_tag: r.pct_since_tag, max_gain_pct: r.max_gain_pct, edgar: r.edgar, live: lv ?? null };
}
export function unifyLive(lv: LiveRow, b?: Row | null): UnifiedRow {
  if (b) return unifyBoard(b, lv);
  return { ...tells(lv), market_cap: lv.market_cap ?? null, ticker: lv.ticker, status: lv.status as Row['status'], best_tier: lv.best_tier,
    accounts: lv.accounts.map((handle) => ({ handle })),           // tiers unknown without the board row
    first_tagged_at: lv.first_tagged_at ?? null, last_tagged_at: lv.last_tagged_at ?? null, days_since_first_tag: null,
    pct_since_tag: lv.pct_since_tag, max_gain_pct: lv.max_gain_pct ?? null, edgar: lv.edgar ?? null, live: lv };
}

export type SortDir = 'asc' | 'desc';
export type SortState = { key: string; dir: SortDir } | null;
export type ColDef = { key: string; label: string; num?: boolean; title?: string; sort?: (r: UnifiedRow) => number | string | null | undefined; sortDefault?: SortDir };
const ms = (iso?: string | null) => (iso ? (Date.parse(iso) || null) : null);
const roomRank = (room?: RoomRead | null) =>
  !room ? null : room.state === 'IN_BAND' ? 0 : room.state === 'CLEAR' ? Number.POSITIVE_INFINITY : room.room_pct ?? null;
const STATUS_RANK: Record<string, number> = { SEEDING: 0, RAN: 1, DUMPED: 2, QUIET: 3, UNKNOWN: 4 };
const CAT_RANK: Record<string, number> = { REAL: 0, THIN: 1, NONE: 2 };
const secRank = (r: UnifiedRow) => {
  const n = r.sec?.n_30d ?? 0, t = (r.edgar?.owner_stake ? 10 : 0) + (r.edgar?.shelf ? 10 : 0);
  return n + t || (r.sec || r.edgar?.owner_stake || r.edgar?.shelf ? 0 : null);
};
export const COLUMNS: ColDef[] = [
  { key: 'symbol', label: 'Symbol', sort: (r) => r.ticker, sortDefault: 'asc' },
  { key: 'session', label: 'Session', sort: (r) => r.live?.session ?? null, sortDefault: 'asc' },
  { key: 'last', label: 'Last', num: true, sort: (r) => r.live?.last ?? null },
  { key: 'tagged', label: 'Tagged by' },
  { key: 'first', label: 'First tag', num: true, title: 'when the first roster post landed (ET) · days since', sort: (r) => ms(r.first_tagged_at) },
  { key: 'lastTag', label: 'Last tag', num: true, title: 'the latest roster post (ET)', sort: (r) => ms(r.last_tagged_at) },
  { key: 'today', label: 'Today', num: true, sort: (r) => r.live?.day_pct ?? null },
  { key: 'since', label: 'Since tag', num: true, sort: (r) => r.live?.pct_since_tag_live ?? r.pct_since_tag },
  { key: 'peak', label: 'Peak', num: true, sort: (r) => r.max_gain_pct },
  { key: 'room', label: 'Room', num: true, title: '% from the live print to the first band overhead (daily-bar zones)', sort: (r) => roomRank(r.live?.room) },
  { key: 'tape', label: 'Tape', title: 'price path since the tag — marker at the first post, colored by the read' },
  { key: 'russell', label: 'Russell', title: 'on the Russell inclusion watch: R2000 add / R1000 promotion and the in-index date', sort: (r) => (r.russell ? (ms(r.russell.add_event?.in_index) ?? Number.MAX_SAFE_INTEGER) : null), sortDefault: 'asc' },
  { key: 'sales', label: 'Sales', num: true, title: 'Bonde sales read: latest quarter revenue vs a year earlier (YoY)', sort: (r) => r.sales?.growth_yoy_pct ?? null },
  { key: 'catalyst', label: 'Catalyst', title: 'news in the last 48h: REAL = a tagged headline (contract, approval, offering…), THIN = untagged chatter, NONE = nothing', sort: (r) => (r.catalyst ? CAT_RANK[r.catalyst.verdict] : null), sortDefault: 'asc' },
  { key: 'eightk', label: '8-K', num: true, title: 'newest 8-K in 14 days with its item codes', sort: (r) => (r.eightk ? ms(r.eightk.filing_date) : null) },
  { key: 'sec', label: 'SEC', num: true, title: 'EDGAR: 13D/G owner stake ≤14d, shelf/offering ≤30d, plus every other filing in 30 days', sort: secRank },
  { key: 'status', label: 'Status', sort: (r) => STATUS_RANK[r.status] ?? 9, sortDefault: 'asc' },
];
/* Fixed column budget in px (table-layout: fixed) — sums to ~1790 so all 17
 * fit a 1920-wide screen with the sticky headers intact; narrower windows
 * fall back to the horizontal scroll (useWideTable). */
export const COL_WIDTHS: Record<string, number> = {
  symbol: 120, session: 50, last: 70, tagged: 150, first: 135, lastTag: 105, today: 70, since: 75, peak: 58,
  room: 100, tape: 104, russell: 100, sales: 105, catalyst: 170, eightk: 110, sec: 145, status: 92,
};
export function nextSort(cur: SortState, col: ColDef): SortState {
  const first: SortDir = col.sortDefault ?? (col.num ? 'desc' : 'asc');
  if (!cur || cur.key !== col.key) return { key: col.key, dir: first };
  if (cur.dir === first) return { key: col.key, dir: first === 'asc' ? 'desc' : 'asc' };
  return null;
}
export function sortRows(rows: UnifiedRow[], sort: SortState, fallback: (rows: UnifiedRow[]) => UnifiedRow[]): UnifiedRow[] {
  const col = sort ? COLUMNS.find((c) => c.key === sort.key) : undefined;
  if (!sort || !col?.sort) return fallback(rows);
  const dir = sort.dir === 'asc' ? 1 : -1;
  const empty = (v: unknown) => v == null || v === '' || (typeof v === 'number' && Number.isNaN(v));
  return rows.map((r, i) => ({ r, i, v: col.sort!(r) }))
    .sort((a, b) => {
      const ae = empty(a.v), be = empty(b.v);
      if (ae && be) return a.i - b.i;
      if (ae) return 1;
      if (be) return -1;
      const d = (typeof a.v === 'number' && typeof b.v === 'number') ? a.v - b.v : String(a.v).localeCompare(String(b.v));
      return (Number.isNaN(d) ? 0 : d) * dir || a.i - b.i;
    })
    .map((x) => x.r);
}

const SESSION_TAG_ALL: Record<string, string> = { premarket: 'PRE', rth: 'RTH', afterhours: 'AH', closed: '—' };
/* Column-width budget: 17 columns must fit a wide screen without a horizontal
 * scrollbar (which would kill the sticky headers). Times drop the " ET" suffix
 * (the header says ET), the chip list shows two + "+N", Room wraps its band
 * onto a second line, the tape is 100px. */
export const tagStampShort = (iso: string | null | undefined) => tagStamp(iso).replace(/ ET$/, '').replace(' · ', ' ');   // "Sep 2 7:55p"
const MAX_CHIPS = 2;
const pctCompact = (v: number | null | undefined) =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}${Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1)}%`;

/* Sticky headers need the page to be the scroller, so the table can never
 * live in an overflow-x:auto wrapper by default. When it is wider than its
 * box anyway (a narrow window), trade the sticky header for a horizontal
 * scrollbar — hidden columns are worse than a scrolling header. */
function useWideTable(ref: React.RefObject<HTMLDivElement | null>, deps: unknown[]): boolean {
  const [wide, setWide] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const t = el.querySelector('table');
      setWide(!!t && t.scrollWidth > el.clientWidth + 2);
    };
    measure();
    const RO = typeof ResizeObserver === 'undefined' ? null : ResizeObserver;
    const ro = RO ? new RO(() => measure()) : null;
    ro?.observe(el);
    window.addEventListener('resize', measure);
    return () => { ro?.disconnect(); window.removeEventListener('resize', measure); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return wide;
}
const trunc = (t: string, n: number) => (t.length > n ? t.slice(0, n - 1) + '…' : t);

function RussellCell({ r }: { r?: RussellJoin | null }) {
  if (!r) return <td className="mono pcw__dim">—</td>;
  const e = r.add_event;
  const board = r.board === 'add_r2000' ? 'R2K add' : 'R1K promo';
  const title = `${r.board === 'add_r2000' ? 'Russell 2000 add' : 'Russell 1000 promotion'} candidate on the Russell watch (cap screen, board as of ${r.as_of ?? '?'})`
    + (e ? ` — ${e.label}: rank day ${mdy(e.rank_day)}, preliminary list ${mdy(e.prelim)}, in the index ${mdy(e.in_index)}${e.lists_published ? ' · FTSE\'s list is already out — check it' : ''}` : ' — no add date loaded')
    + (r.board === 'promote_r1000' ? ' · promotions are usually NET SELLING by trackers' : '');
  return (
    <td className={`mono pcw__russ ${r.board === 'add_r2000' ? 'is-add' : 'is-promo'}`} title={title}>
      {board}{e ? <span className="pcw__line2"><b>{mdy(e.in_index)}</b>{e.lists_published ? <span className="pcw__dim"> list out</span> : null}</span> : null}
    </td>
  );
}
const TIER_CLASS: Record<string, string> = { explosive: 'is-explosive', strong: 'is-strong', steady: 'is-steady', weak: 'is-weak', declining: 'is-declining' };
function SalesCell({ s }: { s?: SalesRead | null }) {
  if (!s) return <td className="og__num mono pcw__dim" title="no revenue read yet — not in the SEPA research cache; the board looks it up in batches">—</td>;
  if (!s.tier || s.tier === 'unknown' || s.growth_yoy_pct == null) {
    return <td className="og__num mono pcw__dim" title={s.reason ?? 'insufficient revenue history — pre-revenue or too few quarters'}>no rev hist</td>;
  }
  return (
    <td className={`og__num mono pcw__sales ${TIER_CLASS[s.tier] ?? ''}`}
        title={`Bonde sales read: ${s.tier}, latest quarter ${pct(s.growth_yoy_pct)} YoY${s.prior_yoy_pct != null ? `, prior ${pct(s.prior_yoy_pct)}` : ''}${s.accelerating ? ', accelerating' : ''} · score ${s.score ?? '—'} · ${s.source ?? ''}`}>
      {pctCompact(s.growth_yoy_pct)}<span className="pcw__dim pcw__line2">{s.tier}{s.accelerating ? ' ↑' : ''}</span>
    </td>
  );
}
const CAT_CLASS: Record<string, string> = { REAL: 'is-real', THIN: 'is-thin', NONE: 'is-none' };
function CatalystCell({ c }: { c?: CatalystRead | null }) {
  if (!c) return <td className="pcw__dim" title="no news read yet — fills on the next board build">—</td>;
  const top = c.top;
  const line = top ? `${top.title}${top.publisher ? ` — ${top.publisher}` : ''}${top.published_utc ? ` · ${tagStamp(top.published_utc)}` : ''}` : 'nothing in 48h';
  return (
    <td className={`pcw__cat ${CAT_CLASS[c.verdict] ?? ''}`}
        title={`${c.verdict}: ${c.n_48h} headline(s) in 48h · ${c.n_bullish} bullish / ${c.n_bearish} bearish\n${line}`}>
      <span className="pcw__cat-verdict">{c.verdict}</span>
      {top ? <> <a href={top.url ?? undefined} target="_blank" rel="noreferrer" className={`pcw__cat-top tone-${top.tone}`}>{trunc(top.title, 30)}</a></> : null}
    </td>
  );
}
function EightKCell({ k }: { k?: EightK | null }) {
  if (!k) return <td className="og__num mono pcw__dim" title="no 8-K in the last 14 days">—</td>;
  return (
    <td className="og__num mono pcw__8k"
        title={`${k.form} filed ${k.filing_date}${k.items.length ? ` · items ${k.items.join(', ')}` : ''}${(k.n_14d ?? 0) > 1 ? ` · ${k.n_14d} in 14d` : ''}`}>
      <a href={k.url ?? undefined} target="_blank" rel="noreferrer">{mdy(k.filing_date)}{k.items.length ? <span className="pcw__dim"> {k.items.slice(0, 2).join(',')}{k.items.length > 2 ? `+${k.items.length - 2}` : ''}</span> : null}</a>
    </td>
  );
}
function SecCell({ e, s }: { e?: Row['edgar'] | null; s?: SecRollup | null }) {
  const hasTell = !!(e?.owner_stake || e?.shelf);
  if (!hasTell && !s) return <td className="pcw__dim" title="nothing filed in 30 days (or not read yet)">—</td>;
  return (
    <td className="pcw__sec">
      {hasTell ? <EdgarChips e={e!} /> : null}
      {s ? (
        <a className="pcw__sec-roll mono" href={s.latest?.url ?? undefined} target="_blank" rel="noreferrer"
           title={`${s.n_30d} other filing(s) in 30d: ${s.forms.join(', ')}${s.n_form4 ? ` · Form 4 ×${s.n_form4}` : ''}${s.has_offering ? ' · offering plumbing' : ''} · latest ${s.latest.form} ${s.latest.filing_date}`}>
          {s.n_30d}× {s.forms.slice(0, 2).join(', ')}
        </a>
      ) : null}
    </td>
  );
}

function PromoRowView({ r, isOpen, toggle, thr, isLiveTable }: { r: UnifiedRow; isOpen: boolean; toggle: () => void; thr?: number; isLiveTable: boolean }) {
  const lv = r.live;
  const since = lv?.pct_since_tag_live ?? r.pct_since_tag;
  const isLive = lv?.pct_since_tag_live != null;
  const move = lv ? (lv.ah_pct != null ? lv.ah_pct : lv.day_pct) : null;
  const big = !!lv && (lv.alertable ?? true) && move != null && thr != null && Math.abs(move) >= thr;
  return (
    <Fragment>
      <tr className={big && isLiveTable ? 'pcw__live-big' : undefined}>
        <td className="og__sym">
          <SymCell ticker={r.ticker} cap={r.market_cap} />
          <button type="button" className={`ptt__toggle${isOpen ? ' is-on' : ''}`}
                  aria-label={`${isOpen ? 'Hide' : 'Show'} tape for ${r.ticker}`}
                  title="Price path around the tag — before or after the move?" onClick={toggle}>📈</button>
        </td>
        <td className="mono pcw__dim">{lv ? (SESSION_TAG_ALL[lv.session] || lv.session) : '—'}</td>
        <td className="og__num mono">{lv?.last != null ? `$${lv.last.toFixed(2)}` : '—'}</td>
        <td className="pcw__tagged">
          {r.accounts.slice(0, MAX_CHIPS).map((a) => ('tier' in a
            ? <AccountChip key={a.handle} a={a} />
            : <span key={a.handle} className="mono pcw__dim"><a href={accountUrl(a.handle)} target="_blank" rel="noreferrer" className="pcw__acct-link">@{a.handle}</a> </span>))}
          {r.accounts.length > MAX_CHIPS ? (
            <span className="pcw__acct pcw__acct-more mono" title={r.accounts.slice(MAX_CHIPS).map((a) => `${'tier' in a ? a.tier + '·' : ''}@${a.handle}`).join('\n')}>
              +{r.accounts.length - MAX_CHIPS}
            </span>
          ) : null}
        </td>
        <td className="og__num mono" title={`${tagStamp(r.first_tagged_at)}${r.days_since_first_tag != null ? ` · ${r.days_since_first_tag.toFixed(1)} days ago` : ''}`}>
          {tagStampShort(r.first_tagged_at)}{r.days_since_first_tag != null ? <span className="pcw__dim"> · {r.days_since_first_tag.toFixed(0)}d</span> : null}
        </td>
        <td className="og__num mono pcw__dim" title={tagStamp(r.last_tagged_at)}>{tagStampShort(r.last_tagged_at)}</td>
        <td className={`og__num mono pcw__pct ${((lv?.day_pct ?? 0) >= 0) ? 'og__up' : 'og__dn'}`}
            title={lv ? `last $${lv.last?.toFixed(2)} vs prior close $${lv.prev_close?.toFixed(2)}${lv.ah_pct != null ? ` · after-hours ${pct(lv.ah_pct)} vs today's close` : ''}` : 'no live print yet'}>
          {lv ? pct(lv.day_pct) : '—'}{lv?.ah_pct != null ? <span className="pcw__dim"> ({pct(lv.ah_pct)} AH)</span> : null}{big ? ' 🎪' : ''}
        </td>
        <td className={`og__num mono ${((since ?? 0) >= 0) ? 'og__up' : 'og__dn'}`}
            title={isLive ? `live print vs the pre-tag close · daily close read: ${pct(r.pct_since_tag)}` : 'daily close read'}>
          {isLive ? <span className="pcw__livedot">●</span> : null}{pct(since)}
        </td>
        <td className="og__num mono">{pct(r.max_gain_pct)}</td>
        <RoomCell room={lv?.room} />
        <td className="ptt__mini-cell"><MiniTape ticker={r.ticker} onOpen={toggle} width={100} /></td>
        <RussellCell r={r.russell} />
        <SalesCell s={r.sales} />
        <CatalystCell c={r.catalyst} />
        <EightKCell k={r.eightk} />
        <SecCell e={r.edgar} s={r.sec} />
        <td title={STATUS_META[r.status]?.hint}>{STATUS_META[r.status]?.label ?? r.status}</td>
      </tr>
      {isOpen ? (
        <tr className="ptt__row"><td colSpan={COLUMNS.length}><PromoTagTape ticker={r.ticker} /></td></tr>
      ) : null}
    </Fragment>
  );
}

export function PromoTable({ title, hint, rows, defaultOrder, className, emptyText, thr, isLiveTable = false, label }: {
  title: ReactNode; hint: ReactNode; rows: UnifiedRow[];
  defaultOrder: (rows: UnifiedRow[]) => UnifiedRow[];
  className?: string; emptyText?: string; thr?: number; isLiveTable?: boolean;
  /** Short table name repeated in the sticky header row ("⚡ live", "🌱 seeding") — the title scrolls, this stays. */
  label?: string;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const [sort, setSort] = useState<SortState>(null);
  const sorted = sortRows(rows, sort, defaultOrder);
  const box = useRef<HTMLDivElement>(null);
  const wide = useWideTable(box, [rows.length]);
  return (
    <div ref={box} className={`pcw__table${className ? ` ${className}` : ''}${wide ? ' is-wide' : ''}`}
         title={wide ? 'Window too narrow for every column — scroll sideways (headers stop sticking while it scrolls)' : undefined}>
      <h3 className="day-section__h">{title}</h3>
      <p className="rw__hint">{hint}</p>
      {rows.length === 0 ? (
        <div className="day-empty">{emptyText ?? 'Nothing here right now.'}</div>
      ) : (
        <table className="og__table pcw__grid">
          <colgroup>
            {COLUMNS.map((c) => <col key={c.key} style={{ width: COL_WIDTHS[c.key] }} />)}
          </colgroup>
          <thead>
            <tr>
              {COLUMNS.map((c) => {
                const active = sort?.key === c.key;
                const ariaSort = active ? (sort!.dir === 'asc' ? 'ascending' : 'descending') : c.sort ? 'none' : undefined;
                return (
                  <th key={c.key} className={`${c.num ? 'og__num ' : ''}${c.sort ? 'og__sortable' : ''}${active ? ' is-sorted' : ''}`}
                      title={c.title} aria-sort={ariaSort as 'ascending' | 'descending' | 'none' | undefined}>
                    {c.sort ? (
                      <button type="button" className="og__sortbtn" onClick={() => setSort(nextSort(sort, c))}
                              aria-label={`Sort by ${c.label}`}>
                        {c.label}<span className="og__sortarrow" aria-hidden="true">{active ? (sort!.dir === 'asc' ? ' ▲' : ' ▼') : ' ⇅'}</span>
                      </button>
                    ) : c.label}
                    {c.key === 'symbol' && label ? <span className="pcw__tablabel">{label}</span> : null}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <PromoRowView key={r.ticker} r={r} isOpen={open === r.ticker} thr={thr} isLiveTable={isLiveTable}
                            toggle={() => setOpen(open === r.ticker ? null : r.ticker)} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/* Board tables: most recent announcement first. Live table: today's move. */
const byLatestTag = (rows: UnifiedRow[]) => sortRecent(rows);
const byTodaysMove = (rows: UnifiedRow[]) =>
  [...rows].sort((a, b) => ((b.live?.day_pct == null ? -Infinity : b.live.day_pct) - (a.live?.day_pct == null ? -Infinity : a.live.day_pct)));

export function PromoLive({ data, err, board, rowFilter }: { data: LivePayload | null; err: string | null; board?: Row[]; rowFilter?: (lv: LiveRow) => boolean }) {
  if (err && !data) return <div className="cm-note cm-note-warn">Live board unavailable: {err}</div>;
  if (!data) return <div className="cm-note">Pricing the circuit's names…</div>;
  const thr = data.alert_threshold_pct;
  const who = (data.alert_handles && data.alert_handles.length)
    ? data.alert_handles.map((h) => '@' + h).join(', ') : 'any roster account';
  const boardBy = Object.fromEntries((board ?? []).map((r) => [r.ticker, r]));
  const rows = data.rows.filter((lv) => !rowFilter || rowFilter(lv)).map((lv) => unifyLive(lv, boardBy[lv.ticker]));
  return (
    <PromoTable
      className="pcw__live"
      isLiveTable
      label="⚡ live"
      thr={thr}
      title={(
        <>
          ⚡ Live movers
          <span className={`sl-live sl-live-${data.live.state}`} style={{ marginLeft: 8 }}>
            {data.live.refresh_sec ? '● LIVE' : '○ CLOSED'} · {data.live.state}
            {err ? <span className="sl-stale" title={err}> · stale</span> : null}
          </span>
        </>
      )}
      hint={(
        <>
          Every tagged name, priced now (pre/post market included), sorted by today's move.
          A move of ±{thr.toFixed(0)}% on a name tagged by {who} pushes a 🎪 alert — once per direction per trading day
          (after the bell, measured against today's close). Click any column header to sort.
        </>
      )}
      rows={rows}
      defaultOrder={byTodaysMove}
      emptyText="Nothing tagged is priced right now."
    />
  );
}

export function PromoCircuit() {
  const [data, setData] = useState<Payload | null>(null);
  /* One live fetch (30s while open) feeds the ⚡ table AND the Today / live since-tag cells below. */
  const live = usePromoLive();
  const liveBySym = Object.fromEntries((live.data?.rows ?? []).map((r) => [r.ticker, r]));
  const [err, setErr] = useState<string | null>(null);
  /* Sweep failures get their OWN state: a failed "Sweep now" must not
   * blank an already-rendered board (review finding 2026-09-01). */
  const [sweepErr, setSweepErr] = useState<string | null>(null);
  const [sweeping, setSweeping] = useState(false);
  const [capFloor, setCapFloorState] = useState<boolean>(readCapFloorPref);
  const setCapFloor = (on: boolean) => { setCapFloorState(on); writeCapFloorPref(on); };
  const seq = useRef(0);

  const load = useCallback((force: boolean) => {
    const my = ++seq.current;
    fetch(`${API}/catalysts/promo-circuit${force ? '?force=true' : ''}`,
      { credentials: 'include', cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((j) => { if (my === seq.current) { setData(j); setErr(null); } })
      .catch((e) => { if (my === seq.current) setErr(String(e?.message ?? e)); });
  }, []);

  useEffect(() => { load(false); }, [load]);

  const sweepNow = useCallback(() => {
    setSweeping(true);
    setSweepErr(null);
    fetch(`${API}/catalysts/promo-circuit/sweep`, { method: 'POST', credentials: 'include' })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); })
      .then(() => load(true))
      .catch((e) => setSweepErr(String(e?.message ?? e)))
      .finally(() => setSweeping(false));
  }, [load]);

  if (err) return <div className="cm-note cm-note-warn">Promo circuit unavailable: {err}</div>;
  if (!data) return <div className="cm-note">Reading the circuit’s recent tags…</div>;

  const visibleRows = data.rows.filter((r) => passesCapFloor(r.market_cap, capFloor));
  const hiddenSmall = data.rows.length - visibleRows.length;
  const unknownCap = data.rows.filter((r) => r.market_cap == null).length;
  const seeding = visibleRows.filter((r) => r.status === 'SEEDING');
  const played = visibleRows.filter((r) => r.status === 'RAN' || r.status === 'DUMPED');
  const rest = visibleRows.filter((r) => !['SEEDING', 'RAN', 'DUMPED'].includes(r.status));

  return (
    <section className="day-section pcw">
      <header className="cat-section__head">
        <div>
          <h2 className="day-section__h">🎪 Promo-circuit watch</h2>
          <p className="rw__hint">
            The accounts below were caught seeding the 8/31–9/1 movers — a fresh tag from them
            is the <b>promotion itself</b>, never foresight. This is a <b>do-not-chase</b> radar,
            not a buy list.
          </p>
          <label className="pcw__capfilter mono">
            <input type="checkbox" checked={capFloor} onChange={(e) => setCapFloor(e.target.checked)} />
            Hide names under $700M
            <span className="pcw__dim"> · {capFloor ? `${hiddenSmall} hidden` : 'showing all'}{unknownCap ? ` · ${unknownCap} cap unknown, kept` : ''}</span>
          </label>
        </div>
        <div className="pcw__sweepbox">
          <button type="button" className="lifeboard-btn" onClick={sweepNow} disabled={sweeping}>
            {sweeping ? 'Sweeping…' : '↻ Sweep now'}
          </button>
          {sweepErr && <div className="pcw__sweep-err">Sweep failed: {sweepErr} — showing the last board.</div>}
        </div>
      </header>

      <PromoLive data={live.data} err={live.err} board={visibleRows} rowFilter={(lv) => passesCapFloor(lv.market_cap, capFloor)} />

      <PromoTable
        label="🌱 seeding"
        title="🌱 Being seeded now"
        hint="Tagged in the last days by the circuit, hasn’t run yet. If it pops on no news, you watched the machine work. Newest announcement first — click a header to sort."
        rows={seeding.map((r) => unifyBoard(r, liveBySym[r.ticker]))}
        defaultOrder={byLatestTag}
      />
      <PromoTable
        label="🚀💥 played"
        title="How the last campaigns ended"
        hint="Tagged names that already ran (≥30% since first tag) or ran and got dumped (gave back ≥40% from the peak)."
        rows={played.map((r) => unifyBoard(r, liveBySym[r.ticker]))}
        defaultOrder={byLatestTag}
      />
      {rest.length > 0 && (
        <PromoTable label="💤 old" title="Old / unpriced tags" hint="Tags that never ran, or symbols without daily bars yet."
                    rows={rest.map((r) => unifyBoard(r, liveBySym[r.ticker]))} defaultOrder={byLatestTag} />
      )}

      <div className="pcw__roster">
        <h3 className="day-section__h">The roster</h3>
        <ul className="pcw__roster-list">
          {data.roster.map((r) => (
            <li key={r.handle}>
              <span className="pcw__acct mono" style={{ borderColor: TIER_COLORS[r.tier], color: TIER_COLORS[r.tier] }}>
                {r.tier}·@{r.handle}
              </span>{' '}
              <span className="pcw__note">{r.note}</span>{' '}
              <span className="pcw__dim">— {r.evidence}</span>
              {r.audit && <div className="pcw__audit">📏 {r.audit}</div>}
            </li>
          ))}
        </ul>
      </div>

      <p className="rw__note">
        {data.sweep?.last_sweep_at
          ? <>Last sweep: <b>{new Date(data.sweep.last_sweep_at).toLocaleString()}</b>
              {data.sweep.accounts_failed.length > 0 && <> · failed: {data.sweep.accounts_failed.join(', ')}</>}</>
          : <>No sweep recorded yet — cron runs every 30 min on weekdays; use “Sweep now” to seed the board.</>}
      </p>
      <p className="rw__note">{data.method_note}</p>
    </section>
  );
}
