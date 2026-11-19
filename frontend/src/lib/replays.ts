/* 🎬 Replays — the Chart Maps tab's FE plumbing (2026-11-17, replays spec §3.3, WP-FE).
 *
 * Ajay 2026-11-17: "Can you store the videos in to the app please". 2026-11-16: "I only wanna see ones from 4 AM to
 * 8 pm please" — the SERVER applies that rule (backend chart_maps/replays/constants.FULL_DAY_WINDOW); nothing here
 * types it.
 *
 * The board is ONE read-only GET per session date (GET /chart-maps/replays[?date=], backend chart_maps/replays/api.py)
 * plus the owner-only video route the `<video>` element reads with Range requests. This module holds the route, the
 * payload TYPES (spec §3.1 `payload`), the text guards, the video-src guard, the URL helper and the date-select helper.
 * Every word the board prints is SERVED; the ONE FE sentence is FETCH_FAILED (the request itself failed — there is no
 * payload to serve a reason). Owner only (server-gated + the tab is hidden for a loaded non-owner). UNMEASURED. */
import { API } from './apiBase';

/** The tab id (== backend chart_maps/replays/constants.TAB). */
export const RP_TAB = 'replays';
/** The board route (== backend chart_maps/replays/constants.API_PATH — contract-pinned by the main session). */
export const RP_PATH = '/chart-maps/replays';
/** The ONE URL param this board owns: the session date it shows. */
export const RP_DATE_PARAM = 'date';
/** The one FE sentence: the GET itself failed, so nothing was served. */
export const FETCH_FAILED = 'Could not load the replays.';

// ── payload types (store.payload, spec §3.1) ────────────────────────────────────────────────────────────────────────

export type RpState = 'no_folder' | 'empty' | 'ready';
export type RpPotential = {
  first_stored_et?: string | null; trigger?: unknown; stop?: unknown; page_text?: string | null; setup_text?: string | null;
};
export type RpVideo = {
  file: string; src: string; symbol: string; setup?: string; setup_text?: string; page?: string; page_text?: string;
  grade?: string; why?: string[]; story?: string; ring_id?: string; ring_day?: string; carried?: boolean;
  speed?: number | null; speed_text?: string; minutes?: number | null; length_text?: string;
  move_pct?: number | null; move_base?: string | null; trig_pct?: number | null; fill_px?: number | null;
  no_risk?: unknown; window?: string; plan_word?: string | null; potential?: RpPotential | null; group?: string;
};
export type RpGroup = { key: string; label: string; videos: RpVideo[] };
export type RpRsColumn = { key: string; label: string };
export type RpRsRow = { cells: Record<string, string> };
export type RpRs = { title: string; note: string; columns: RpRsColumn[]; rows: RpRsRow[]; text: string | null };
export type RpCounts = { videos?: number; skipped_window?: number; no_sidecar?: number; skipped_bad?: number };
export type RpPayload = {
  state: RpState | string; title?: string; tab?: string; date: string | null; dates: string[];
  window?: string; window_note?: string; text?: string; groups?: RpGroup[]; counts?: RpCounts; rs?: RpRs | null;
};

// ── guards ──────────────────────────────────────────────────────────────────────────────────────────────────────────

/** A served text: a string prints as itself; anything else prints nothing. */
export function rpText(x: unknown): string {
  return typeof x === 'string' ? x : '';
}

/** A served list of strings: non-strings dropped; not a list → []. */
export function rpList(x: unknown): string[] {
  return Array.isArray(x) ? x.filter((s): s is string => typeof s === 'string') : [];
}

/** The served session dates, in served order (newest first by the server); junk → []. */
export function rpDates(x: unknown): string[] {
  return rpList(x).filter((s) => s.length > 0);
}

/** The `<video>` src for a served card: the API base + the served `src`, ONLY when the served `src` is on the owner
 *  video route. A served `src` anywhere else → '' and the board renders no `<video>` for it. */
export function rpVideoSrc(v: { src?: unknown } | null | undefined): string {
  const src = v ? v.src : undefined;
  if (typeof src !== 'string' || !src.startsWith(`${RP_PATH}/video/`)) return '';
  return `${API}${src}`;
}

/** The next URL params when the session date changes: a COPY of `prev` with `date` set (or deleted on null / '').
 *  Every other param — `tab`, a future `focus` — rides along untouched (replays spec C7). Pure. */
export function rpDateParams(prev: URLSearchParams, date: string | null): URLSearchParams {
  const next = new URLSearchParams(prev);
  if (date) next.set(RP_DATE_PARAM, date);
  else next.delete(RP_DATE_PARAM);
  return next;
}

/** The `<select>` options: the served dates in served order; when the served `date` is a non-empty string NOT among
 *  them (a well-formed day with no folder), it is PREPENDED disabled, so the control always shows the served `date`
 *  (replays spec C8). */
export function rpSelectDates(dates: string[], date: string | null): { value: string; disabled: boolean }[] {
  const out = dates.map((d) => ({ value: d, disabled: false }));
  if (typeof date === 'string' && date && !dates.includes(date)) out.unshift({ value: date, disabled: true });
  return out;
}

// ── 🏆 Past winners (2026-11-18, pastwinners spec §3.6, WP-APP) ─────────────────────────────────────────────────────
// Ajay 2026-11-18 ~21:45 ET, verbatim: "can you work on todays videos and also..  Winners in general from the past".
// A collapsed section at the bottom of 🎬 Replays: ONE lazy GET (GET /chart-maps/replays/winners) only when opened
// (`?winners=1`), its own owner-only video route. Every word is SERVED except the section title (the section is
// collapsed before anything is fetched) — contract-pinned equal to backend constants.WINNERS_TITLE. Descriptive,
// UNMEASURED, not a signal.

/** The 🏆 listing route (== backend chart_maps/replays/constants.WINNERS_API_PATH). */
export const RP_WINNERS_PATH = `${RP_PATH}/winners`;
/** The URL param that opens the 🏆 section (`winners=1`). */
export const RP_WINNERS_PARAM = 'winners';
/** The ONE FE word of the section: its collapsed title (== backend constants.WINNERS_TITLE, contract-pinned). */
export const RP_WINNERS_TITLE = '🏆 Past winners';

export type RpWinner = {
  file: string; sub: string; src: string; symbol: string; kind?: string; kind_text?: string;
  date?: string; label_date?: string; days?: string[]; days_text?: string;
  close_gain_pct?: number | null; gain_text?: string; high_pct?: number | null; high_text?: string | null;
  spike_print?: boolean; spike_text?: string | null; pick_text?: string | null;
  speed?: number | null; speed_text?: string; minutes?: number | null; length_text?: string;
};
export type RpWinnerGroup = { date: string; label: string; videos: RpWinner[] };
export type RpWinnersCounts = {
  videos?: number; single_day?: number; multi_day?: number; skipped_window?: number; skipped_bad?: number;
  no_sidecar?: number;
};
export type RpWinnersPayload = {
  state: RpState | string; title?: string; tab?: string; text?: string | null; note?: string; window?: string;
  window_note?: string; summary_text?: string | null; counts?: RpWinnersCounts; groups?: RpWinnerGroup[];
};

/** The `<video>` src for a served 🏆 card: API + the served `src`, ONLY when it is on the 🏆 video route. Anything
 *  else → '' and no `<video>` is rendered for it. */
export function rpWinnerSrc(v: { src?: unknown } | null | undefined): string {
  const src = v ? v.src : undefined;
  if (typeof src !== 'string' || !src.startsWith(`${RP_WINNERS_PATH}/video/`)) return '';
  return `${API}${src}`;
}

/** The next URL params when the 🏆 section opens / closes: a COPY of `prev` with `winners=1` set (open) or deleted
 *  (closed). Every other param — `tab`, `date` — rides along untouched. Pure. */
export function rpWinnersParams(prev: URLSearchParams, open: boolean): URLSearchParams {
  const next = new URLSearchParams(prev);
  if (open) next.set(RP_WINNERS_PARAM, '1');
  else next.delete(RP_WINNERS_PARAM);
  return next;
}
