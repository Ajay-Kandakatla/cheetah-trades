/* 📅 Runners kept on the 👀 Watch for two weeks — the FE plumbing (2026-11-26, spec watchrun rev 2 §3.5, WP fe-roster).
 *
 * Ajay 2026-11-26: "Ok then add them to our watch list and track them please.. I know he tracks them for two weeks
 * sometimes.. before he discards them.. Can you do that please" · "Make it 30% please after A+".
 *
 * The server (backend chart_maps/gajjala_watch/runseat.py) seats the runners and serves a LIGHT roster under the tiles
 * (`board.runners`) plus two chips on the tile of a seated name (`row.runner`); the nightly record
 * (runtrack.py) is read lazily through GGW_RUNTRACK_PATH. This module holds the two routes, the TYPES, the parsers and the
 * two hooks. Every word, number and threshold is SERVED — the parsers keep strings verbatim and the served order; the
 * only FE-typed strings are the control chrome below (the GGW_RUN precedent).
 *
 * TWO ×, TWO LISTS [fixed: C4]: the roster's × is its OWN hook (useGgwRunSeatRemove) → DELETE ggwRunSeatPath(sym) only.
 * It never calls ggwSymbolPath and never touches the board's write queue; a tile's × never calls this path.
 * No import from ./gajjalaWatch at runtime: gajjalaWatch.ts imports the parsers from here (no module cycle).
 * Display + his own 📅 list write only. Nothing rings; UNMEASURED. */
import { useCallback, useEffect, useRef, useState } from 'react';
import { API } from './apiBase';

/** == backend gajjala_watch/constants.API_RUNTRACK_PATH (contract — main session). */
export const GGW_RUNTRACK_PATH = '/chart-maps/gajjala-watch/runners/track';
/** == backend constants.API_RUNSEAT_PATH minus "/{symbol}" (contract — main session). DELETE only. */
export const GGW_RUNSEAT_PATH = '/chart-maps/gajjala-watch/runners/seat';
/** The roster × route for one ticker (the ggwRunPath shape; the server normalizes the symbol). */
export function ggwRunSeatPath(sym: string): string {
  return `${GGW_RUNSEAT_PATH}/${encodeURIComponent(String(sym).trim())}`;
}
/** The record route, all runs or one ticker's runs. */
export function ggwRunTrackPath(sym?: string | null): string {
  const s = typeof sym === 'string' ? sym.trim() : '';
  return s ? `${GGW_RUNTRACK_PATH}?symbol=${encodeURIComponent(s)}` : GGW_RUNTRACK_PATH;
}

/** Control chrome only (no word about a stock): the ⓘ fold glyph, the per-row record toggle, the roster ×. */
export const GGW_RUNROSTER = { info: 'ⓘ', infoLabel: 'info', history: '🧾', remove: '×' } as const;
export function ggwRunHistoryTitle(sym: string): string { return `${sym} — record`; }

/** 📱 The phone's open roster (a per-viewer convenience, beside `ggw.opened`): "1" = opened; anything else → folded. */
export const GGW_RUNROSTER_OPEN_KEY = 'ggw.runners.opened';
export function readGgwRunRosterOpen(): boolean {
  try { return window.localStorage.getItem(GGW_RUNROSTER_OPEN_KEY) === '1'; } catch { return false; }
}
export function saveGgwRunRosterOpen(open: boolean): void {
  try {
    if (open) window.localStorage.setItem(GGW_RUNROSTER_OPEN_KEY, '1');
    else window.localStorage.removeItem(GGW_RUNROSTER_OPEN_KEY);
  } catch { /* private window: the fold lasts this visit */ }
}

/** 📅 The two served chips on a seated name's tile (backend runseat.tag_of). */
export type GgwRunnerTag = {
  day_n: number | null; keep: number | null; day_text: string | null; seat_text: string | null;
  seat_title: string | null; rule: string | null; run_day: string | null;
};
/** One roster line (backend runseat.roster rows), in SERVED order (🚫 last as served). */
export type GgwRunRosterRow = {
  symbol: string; day_n: number | null; day_text: string | null; seat_text: string | null; seat_title: string | null;
  rule: string | null; run_day: string | null; broker_text: string | null; on_watch: boolean;
  on_watch_text: string | null; remove_title: string | null;
};
export type GgwRunNotSeated = { symbol: string | null; session: string | null; why: string | null; text: string };
/** The served roster block (`board.runners`); `state` "unreadable" → `text` is the served fault line, no rows. */
export type GgwRunRoster = {
  state: string; title: string | null; text: string | null; n: number | null; keep_sessions: number | null;
  hint: string | null; folded_default: boolean; fold_at: number | null; more_text: string | null;
  less_text: string | null; track_path: string | null; not_seated: GgwRunNotSeated[]; rows: GgwRunRosterRow[];
};
/** One served table: the heads' labels and every row's cells as served strings, aligned to the heads. */
export type GgwRunTable = { heads: string[]; rows: string[][] };
/** The record of every run (GET GGW_RUNTRACK_PATH). */
export type GgwRunTrack = {
  state: string; title: string | null; text: string | null; summary_text: string | null; note: string | null;
  asof_text: string | null; shown_text: string | null; open_n: number | null; closed_n: number | null;
  table: GgwRunTable;
};
export type GgwRunTrackDoc = {
  run_day: string | null; seat_text: string | null; state_text: string | null; base_note: string | null; table: GgwRunTable;
};
/** One ticker's record (GET GGW_RUNTRACK_PATH?symbol=SYM). */
export type GgwRunTrackSymbol = {
  state: string; symbol: string | null; title: string | null; text: string | null; note: string | null;
  docs: GgwRunTrackDoc[];
};
/** The roster × answer (backend runseat.dismiss): state ∈ dismissed / absent / error, `text` served. */
export type GgwRunSeatAnswer = { state: string; symbol: string | null; text: string | null };

type Obj = Record<string, unknown>;
const isObj = (x: unknown): x is Obj => !!x && typeof x === 'object' && !Array.isArray(x);
const str = (x: unknown): string | null => (typeof x === 'string' && x.trim() !== '' ? x : null);
const num = (x: unknown): number | null => (typeof x === 'number' && Number.isFinite(x) ? x : null);
const count = (x: unknown): number | null => { const k = num(x); return k != null && k >= 0 ? k : null; };
const foldSize = (x: unknown): number | null => (typeof x === 'number' && Number.isInteger(x) && x >= 1 ? x : null);

/** The tile's served tag; junk / no chip text at all → null (a tile without it draws no new chip). */
export function parseRunnerTag(v: unknown): GgwRunnerTag | null {
  if (!isObj(v)) return null;
  const day_text = str(v.day_text);
  const seat_text = str(v.seat_text);
  if (!day_text && !seat_text) return null;
  return {
    day_n: count(v.day_n), keep: count(v.keep), day_text, seat_text, seat_title: str(v.seat_title),
    rule: str(v.rule), run_day: str(v.run_day),
  };
}

function parseRosterRow(v: unknown): GgwRunRosterRow | null {
  if (!isObj(v) || !str(v.symbol)) return null;
  return {
    symbol: (v.symbol as string).trim(), day_n: count(v.day_n), day_text: str(v.day_text), seat_text: str(v.seat_text),
    seat_title: str(v.seat_title), rule: str(v.rule), run_day: str(v.run_day), broker_text: str(v.broker_text),
    on_watch: v.on_watch === true, on_watch_text: str(v.on_watch_text), remove_title: str(v.remove_title),
  };
}

function parseNotSeated(v: unknown): GgwRunNotSeated | null {
  if (!isObj(v) || !str(v.text)) return null;
  return { symbol: str(v.symbol), session: str(v.session), why: str(v.why), text: v.text as string };
}

/** The served roster; junk / no string `state` → null (nothing drawn). Rows without a ticker are dropped. */
export function parseRunRoster(v: unknown): GgwRunRoster | null {
  if (!isObj(v) || !str(v.state)) return null;
  const rows = Array.isArray(v.rows) ? v.rows : [];
  const ns = Array.isArray(v.not_seated) ? v.not_seated : [];
  return {
    state: v.state as string, title: str(v.title), text: str(v.text), n: count(v.n), keep_sessions: count(v.keep_sessions),
    hint: str(v.hint), folded_default: v.folded_default === true, fold_at: foldSize(v.fold_at),
    more_text: str(v.more_text), less_text: str(v.less_text), track_path: str(v.track_path),
    not_seated: ns.map(parseNotSeated).filter((x): x is GgwRunNotSeated => x !== null),
    rows: rows.map(parseRosterRow).filter((x): x is GgwRunRosterRow => x !== null),
  };
}

/** One served head → [key, label]: `[key, label]` pairs (the house 🏁 shape), `{key, label}` objects or bare labels. */
function headOf(h: unknown, i: number): [string, string] | null {
  if (Array.isArray(h) && h.length >= 2 && typeof h[0] === 'string' && typeof h[1] === 'string') return [h[0], h[1]];
  if (isObj(h) && typeof h.label === 'string') return [typeof h.key === 'string' ? h.key : String(i), h.label];
  if (typeof h === 'string') return [String(i), h];
  return null;
}
/** One served cell → its served string ('' when none): a string, or an object's served `text`. Never formats a number. */
function cellOf(c: unknown): string {
  if (typeof c === 'string') return c;
  if (isObj(c) && typeof c.text === 'string') return c.text;
  return '';
}
/** A served table → heads + string cells aligned to them. A row is an array of cells, `{cells: [...]}`, `{cells: {key: …}}`
 *  or an object keyed by the head keys (its `<key>_text` string first — "every cell is a served string beside its raw
 *  number"). Nothing is computed, sorted or formatted. */
export function parseRunTable(headsRaw: unknown, rowsRaw: unknown): GgwRunTable {
  const hs = (Array.isArray(headsRaw) ? headsRaw : []).map(headOf).filter((x): x is [string, string] => x !== null);
  const rows: string[][] = [];
  for (const r of Array.isArray(rowsRaw) ? rowsRaw : []) {
    let cells: string[] | null = null;
    const src: unknown = isObj(r) && 'cells' in r ? r.cells : r;
    if (Array.isArray(src)) cells = hs.length ? hs.map((_h, i) => cellOf(src[i])) : src.map(cellOf);
    else if (isObj(src) && hs.length) {
      cells = hs.map(([k]) => {
        const t = src[`${k}_text`];
        return typeof t === 'string' ? t : cellOf(src[k]);
      });
    }
    if (cells && cells.some((c) => c !== '')) rows.push(cells);
  }
  return { heads: hs.map(([, l]) => l), rows };
}

/** The record of every run; junk / no string `state` → null. */
export function parseRunTrack(v: unknown): GgwRunTrack | null {
  if (!isObj(v) || !str(v.state)) return null;
  return {
    state: v.state as string, title: str(v.title), text: str(v.text), summary_text: str(v.summary_text), note: str(v.note),
    asof_text: str(v.asof_text), shown_text: str(v.shown_text), open_n: count(v.open_n), closed_n: count(v.closed_n),
    table: parseRunTable(v.heads, v.rows),
  };
}

/** One ticker's record; junk / no string `state` → null. Docs in SERVED order. */
export function parseRunTrackSymbol(v: unknown): GgwRunTrackSymbol | null {
  if (!isObj(v) || !str(v.state)) return null;
  const docs = Array.isArray(v.docs) ? v.docs : [];
  return {
    state: v.state as string, symbol: str(v.symbol), title: str(v.title), text: str(v.text), note: str(v.note),
    docs: docs.filter(isObj).map((d) => ({
      run_day: str(d.run_day), seat_text: str(d.seat_text), state_text: str(d.state_text), base_note: str(d.base_note),
      table: parseRunTable(d.heads, d.rows),
    })),
  };
}

/** The roster × answer; junk / no string `state` → null. */
export function parseRunSeatAnswer(v: unknown): GgwRunSeatAnswer | null {
  if (!isObj(v) || !str(v.state)) return null;
  return { state: v.state as string, symbol: str(v.symbol), text: str(v.text) };
}

export type GgwRunTrackState =
  | { phase: 'idle' } | { phase: 'busy' } | { phase: 'failed' }
  | { phase: 'all'; data: GgwRunTrack } | { phase: 'symbol'; data: GgwRunTrackSymbol };

/** The record, fetched ONLY while `open` (the ⓘ fold or a row's 🧾), once per open; closing aborts a read in flight and
 *  forgets the answer (the next open reads again). 404 / junk → failed (nothing printed but the fold's served words). */
export function useGgwRunTrack(open: boolean, symbol?: string | null): GgwRunTrackState {
  const [st, setSt] = useState<GgwRunTrackState>({ phase: 'idle' });
  const sym = typeof symbol === 'string' && symbol.trim() ? symbol.trim() : null;
  useEffect(() => {
    if (!open) { setSt({ phase: 'idle' }); return undefined; }
    const ctl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    let live = true;
    setSt({ phase: 'busy' });
    Promise.resolve()
      .then(() => fetch(`${API}${ggwRunTrackPath(sym)}`,
        { credentials: 'include', cache: 'no-store', ...(ctl ? { signal: ctl.signal } : {}) }))
      .then((r) => (r.ok ? r.json() : null))
      .then((raw: unknown) => {
        if (!live) return;
        if (sym) { const d = parseRunTrackSymbol(raw); setSt(d ? { phase: 'symbol', data: d } : { phase: 'failed' }); }
        else { const d = parseRunTrack(raw); setSt(d ? { phase: 'all', data: d } : { phase: 'failed' }); }
      })
      .catch(() => { if (live) setSt({ phase: 'failed' }); });
    return () => { live = false; ctl?.abort(); };
  }, [open, sym]);
  return st;
}

/** The roster's OWN × [fixed: C4]: ONE DELETE on ggwRunSeatPath(sym) per tap (a second tap on that name while it is in
 *  flight is ignored), then `onDone(served text | null)` while mounted. Never ggwSymbolPath, never the board's queue. */
export function useGgwRunSeatRemove(onDone: (text: string | null) => void): {
  remove: (sym: string) => void; pending: (sym: string) => boolean;
} {
  const inFlight = useRef(new Set<string>());
  const mounted = useRef(true);
  const done = useRef(onDone);
  done.current = onDone;
  const [, setTick] = useState(0);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const remove = useCallback((symRaw: string) => {
    const sym = String(symRaw || '').trim();
    if (!sym || inFlight.current.has(sym)) return;
    inFlight.current.add(sym);
    setTick((t) => t + 1);
    let text: string | null = null;
    void Promise.resolve()
      .then(() => fetch(`${API}${ggwRunSeatPath(sym)}`, { method: 'DELETE', credentials: 'include', cache: 'no-store' }))
      .then((r) => (r.ok ? r.json() : null))
      .then((raw: unknown) => { text = parseRunSeatAnswer(raw)?.text ?? null; })
      .catch(() => { text = null; })
      .finally(() => {
        inFlight.current.delete(sym);
        if (!mounted.current) return;
        setTick((t) => t + 1);
        done.current(text);
      });
  }, []);
  const pending = (sym: string) => inFlight.current.has(sym);
  return { remove, pending };
}
