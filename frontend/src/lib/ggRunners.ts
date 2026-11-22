/* 📅 Previous day runners — the strip's lib: the served payload, its parse, the poll hook, the remembered fold
 * (2026-11-22, spec watch_org rev 4 §3.6, WP-FE-STRIP — placement-neutral, NO page mount here).
 *
 * Ajay 2026-11-22: "remove hot sectors mess from Gajjalas top view I need a new thing there.. use that space between the
 * parent tab of Gajjala and watch tab to be for previous day runners but remove them if they don’t run the current day".
 *
 * The server is the ONE engine (backend chart_maps/gajjala_watch/runners.py): it decides who ran last session, who is
 * still in today, the order, the fold sizes, the poll cadence and EVERY word. This file types no threshold, no clock
 * time and no sentence — it parses, polls and remembers whether the strip is open. Owner only: anyone else is served
 * `owner_only` and the strip renders nothing. Display only, UNMEASURED: nothing here rings, gates, adds or trades. */
import { useEffect, useState } from 'react';
import { API } from './apiBase';

/** == backend `API_RUNNERS_PATH` (`API_PATH + "/runners"`) — the contract pins the equality. */
export const GG_RUNNERS_PATH = '/chart-maps/gajjala-watch/runners';

/** The strip's open / folded choice, remembered per browser. */
export const GGR_OPEN_KEY = 'ggr.open';

export type GgRunnersState = 'ok' | 'empty' | 'error' | 'off' | 'owner_only';
const STATES: ReadonlyArray<GgRunnersState> = ['ok', 'empty', 'error', 'off', 'owner_only'];

export type GgRunnerRow = {
  symbol: string;
  run_pct: number | null;
  run_text: string;
  timing: string | null;
  timing_text: string | null;
  peak_et: string | null;
  float_text: string | null;
  float_title: string | null;
  past_winner_text: string | null;
  past_winner_title: string | null;
  broker_text: string | null;
  today_state: string | null;            // served verbatim; null before the cut
  today_pct: number | null;
  today_text: string | null;
  title: string | null;
};

export type GgRunnerRemoved = { symbol: string; run_text: string; today_pct: number | null; text: string | null };

export type GgRunnersPayload = {
  state: GgRunnersState;
  title: string | null;
  text: string | null;
  hint: string | null;
  day: string | null;
  day_word: string | null;
  today: string | null;
  live: boolean;
  cut_active: boolean;
  cut_at: string | null;
  refresh_sec: number;                   // 0 = never re-fetch
  fold_at: number | null;                // null = show every chip
  fold_at_phone: number | null;          // null = every mini on the phone's folded line
  more_text: string | null;
  less_text: string | null;
  n: number | null;
  // the served k-count key is deliberately untyped: the FE prints only the served `text` (no word typed here)
  n_not_read: number | null;
  no_bars: number | null;
  as_of_et: string | null;
  stale: boolean;
  rows: GgRunnerRow[];
  removed: GgRunnerRemoved[];
  removed_text: string | null;
};

/** A non-finite number anywhere in the payload means the server's scrub failed — the whole strip is not trusted. */
class Junk extends Error {}

const str = (x: unknown): string | null => (typeof x === 'string' && x.trim() ? x : null);

/** A served number: absent / null → null; a finite number → itself; NaN, ±Infinity or a non-number → the whole parse
 *  is junk (never a "NaN" on screen). */
function num(x: unknown): number | null {
  if (x === undefined || x === null) return null;
  if (typeof x !== 'number' || !Number.isFinite(x)) throw new Junk();
  return x;
}

/** A fold size: a whole number of at least one, else null (the component then shows all). */
function foldSize(x: unknown): number | null {
  return typeof x === 'number' && Number.isInteger(x) && x >= 1 ? x : null;
}

function parseRow(x: unknown): GgRunnerRow | null {
  if (!x || typeof x !== 'object') return null;
  const o = x as Record<string, unknown>;
  const symbol = str(o.symbol), run_text = str(o.run_text);
  const run_pct = num(o.run_pct), today_pct = num(o.today_pct);
  if (!symbol || !run_text) return null;
  return {
    symbol: symbol.trim(), run_pct, run_text,
    timing: str(o.timing), timing_text: str(o.timing_text), peak_et: str(o.peak_et),
    float_text: str(o.float_text), float_title: str(o.float_title),
    past_winner_text: str(o.past_winner_text), past_winner_title: str(o.past_winner_title),
    broker_text: str(o.broker_text),
    today_state: str(o.today_state), today_pct, today_text: str(o.today_text),
    title: str(o.title),
  };
}

function parseRemoved(x: unknown): GgRunnerRemoved | null {
  if (!x || typeof x !== 'object') return null;
  const o = x as Record<string, unknown>;
  const symbol = str(o.symbol), run_text = str(o.run_text);
  const today_pct = num(o.today_pct);
  if (!symbol || !run_text) return null;
  return { symbol: symbol.trim(), run_text, today_pct, text: str(o.text) };
}

/** The served answer → the strip's payload. Junk (not an object, an unknown `state`, a non-finite number) → null.
 *  A row without `symbol` + `run_text` is dropped. `fold_at` / `fold_at_phone` that are not a whole number ≥ 1 → null. */
export function parseGgRunners(raw: unknown): GgRunnersPayload | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const o = raw as Record<string, unknown>;
  const state = o.state as GgRunnersState;
  if (typeof o.state !== 'string' || !STATES.includes(state)) return null;
  try {
    const refresh = num(o.refresh_sec);
    const rows = Array.isArray(o.rows) ? o.rows.map(parseRow).filter((r): r is GgRunnerRow => r !== null) : [];
    const removed = Array.isArray(o.removed)
      ? o.removed.map(parseRemoved).filter((r): r is GgRunnerRemoved => r !== null) : [];
    return {
      state,
      title: str(o.title), text: str(o.text), hint: str(o.hint),
      day: str(o.day), day_word: str(o.day_word), today: str(o.today),
      live: o.live === true, cut_active: o.cut_active === true, cut_at: str(o.cut_at),
      refresh_sec: refresh !== null && refresh > 0 ? refresh : 0,
      fold_at: foldSize(o.fold_at), fold_at_phone: foldSize(o.fold_at_phone),
      more_text: str(o.more_text), less_text: str(o.less_text),
      n: num(o.n), n_not_read: num(o.n_not_read), no_bars: num(o.no_bars),
      as_of_et: str(o.as_of_et), stale: o.stale === true,
      rows, removed, removed_text: str(o.removed_text),
    };
  } catch (e) {
    if (e instanceof Junk) return null;
    throw e;
  }
}

/** "+{n} more" with the count filled in ({n} is the only slot). */
export function ggrMoreText(tpl: string, n: number): string {
  return tpl.split('{n}').join(String(n));
}

/** Remembered open / folded; anything but the saved "open" mark (junk, absent, storage blocked) → folded. */
export function readGgrOpen(): boolean {
  try {
    return typeof localStorage !== 'undefined' && localStorage.getItem(GGR_OPEN_KEY) === 'open';
  } catch {
    return false;
  }
}

export function saveGgrOpen(open: boolean): void {
  try {
    if (typeof localStorage === 'undefined') return;
    if (open) localStorage.setItem(GGR_OPEN_KEY, 'open');
    else localStorage.removeItem(GGR_OPEN_KEY);
  } catch {
    /* storage blocked: the fold just is not remembered */
  }
}

export type GgRunnersHook = { phase: 'loading' | 'done'; data: GgRunnersPayload | null };

const visible = () => typeof document === 'undefined' || document.visibilityState === 'visible';

/** Fetch on mount; re-fetch every served `refresh_sec` (> 0) while the page is visible; abort on unmount. A served
 *  answer that does not parse hides the strip; a failed fetch keeps the strip already shown (one blip never hides it). */
export function useGgRunners(): GgRunnersHook {
  const [st, setSt] = useState<GgRunnersHook>({ phase: 'loading', data: null });
  const [tick, setTick] = useState(0);
  const refresh = st.data?.refresh_sec ?? 0;

  useEffect(() => {
    const ac = new AbortController();
    Promise.resolve()
      .then(() => fetch(`${API}${GG_RUNNERS_PATH}`, { credentials: 'include', cache: 'no-store', signal: ac.signal }))
      .then((r) => (r.ok ? r.json().then((j) => ({ served: true, j }), () => ({ served: true, j: null }))
        : { served: false, j: null }))
      .then(({ served, j }) => {
        if (ac.signal.aborted) return;
        if (served) setSt({ phase: 'done', data: parseGgRunners(j) });
        else setSt((s) => (s.data ? s : { phase: 'done', data: null }));
      })
      .catch(() => {
        if (!ac.signal.aborted) setSt((s) => (s.data ? s : { phase: 'done', data: null }));
      });
    return () => ac.abort();
  }, [tick]);

  useEffect(() => {
    if (!(refresh > 0)) return;
    const id = setInterval(() => { if (visible()) setTick((t) => t + 1); }, refresh * 1000);
    return () => clearInterval(id);
  }, [refresh]);

  return st;
}
