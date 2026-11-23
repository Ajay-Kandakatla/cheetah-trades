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
/** 🏆 past-winner tag (2026-11-22) — Ajay: "Please actually add a past winner tag in our new ones looks for past
 *  winnings please if found again..". Served on a card ONLY when its symbol has an earlier 🏆 win (no key otherwise). */
export type RpPastWin = {
  day?: string; kind?: string; close_gain_pct?: number | null; file?: string; sub?: string; text?: string;
};
export type RpPastWinFields = {
  past_winner?: RpPastWin[] | null; past_winner_count?: number | null; past_winner_more_text?: string | null;
};
export type RpPotential = {
  first_stored_et?: string | null; trigger?: unknown; stop?: unknown; page_text?: string | null; setup_text?: string | null;
};
export type RpVideo = {
  file: string; src: string; symbol: string; setup?: string; setup_text?: string; page?: string; page_text?: string;
  grade?: string; why?: string[]; story?: string; ring_id?: string; ring_day?: string; carried?: boolean;
  speed?: number | null; speed_text?: string; minutes?: number | null; length_text?: string;
  move_pct?: number | null; move_base?: string | null; trig_pct?: number | null; fill_px?: number | null;
  no_risk?: unknown; window?: string; plan_word?: string | null; potential?: RpPotential | null; group?: string;
} & RpPastWinFields;
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

/** The 🏆 past-winner chips of a served card: each served entry's served `text` (non-strings / blanks dropped), then the
 *  served `past_winner_more_text` ("+N more") when it is a non-empty string. No served list → [] (no chip, no noise).
 *  The FE composes no word. Since 2026-11-22 the day-card chips LINK to their reel through `rpPastWinItems` /
 *  `rpJumpParams` (below); this helper still feeds "+N more" and the 🏆 row chips (which stay text). Pure. */
export function rpPastWinChips(v: RpPastWinFields | null | undefined): { wins: string[]; more: string } {
  const list = v && Array.isArray(v.past_winner) ? v.past_winner : [];
  const wins = list.map((w) => rpText(w && typeof w === 'object' ? w.text : undefined)).filter((s) => s.length > 0);
  const more = wins.length ? rpText(v ? v.past_winner_more_text : undefined) : '';
  return { wins, more };
}

/** The `<video>` src for a served card: the API base + the served `src`, ONLY when the served `src` is on the owner
 *  video route. A served `src` anywhere else → '' and the board renders no `<video>` for it. */
export function rpVideoSrc(v: { src?: unknown } | null | undefined): string {
  const src = v ? v.src : undefined;
  if (typeof src !== 'string' || !src.startsWith(`${RP_PATH}/video/`)) return '';
  return `${API}${src}`;
}

/** The next URL params when the session date changes: a COPY of `prev` with `date` set (or deleted on null / '').
 *  Every other param — `tab`, a future `focus`, the 🏆 `reel` (a mounted video is not reloaded) — rides along untouched,
 *  except `card` (2026-11-22, pwjump C9): the origin mark names a card of the session being left. Pure. */
export function rpDateParams(prev: URLSearchParams, date: string | null): URLSearchParams {
  const next = new URLSearchParams(prev);
  next.delete(RP_CARD_PARAM);
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
/** The URL param naming the ONE stock row that opens expanded (`?winners=1&sym=AKAN`, 2026-11-22). */
export const RP_WINNERS_SYM_PARAM = 'sym';
/** The ONE FE word of the section: its collapsed title (== backend constants.WINNERS_TITLE, contract-pinned). */
export const RP_WINNERS_TITLE = '🏆 Past winners';

export type RpWinner = {
  file: string; sub: string; src: string; symbol: string; kind?: string; kind_text?: string;
  date?: string; label_date?: string; days?: string[]; days_text?: string;
  close_gain_pct?: number | null; gain_text?: string; high_pct?: number | null; high_text?: string | null;
  spike_print?: boolean; spike_text?: string | null; pick_text?: string | null;
  speed?: number | null; speed_text?: string; minutes?: number | null; length_text?: string;
  seek_s?: number | null; seek_text?: string | null;
} & RpPastWinFields & RpWinnerLabelFields;
/** 🏆 setup + timing (2026-11-22) — Ajay: "can you categorize past winners like some are kiss and fly based and some
 *  might be VCP based some might be horizontal faded.. Do we have those metrics? also reversal squeeze is mainly what I
 *  look for." · "dont't remove but add a tag but sort by EOD and Intraday ones on the top". Every word is SERVED. */
export type RpWinnerLabelFields = {
  setup?: string | null; setup_text?: string | null; setup_class?: string | null; setup_class_text?: string | null;
  setup_chips?: string[]; setup_chips_text?: string[]; stopped_before_peak?: boolean; stopped_text?: string | null;
  timing?: string | null; timing_text?: string | null;
};
/** 🏆 one row per stock (2026-11-22) — Ajay: "Just AKAN can you please bring its past winner session to like from MAY
 *  multiday when ever a stock has multiday group it in the same role for past winners please." · "CLRO another example
 *  add all the videos may be click them together". The SERVER builds and orders the rows (timing of the newest
 *  single-day reel, then the newest win, then the best close gain) and the reels inside (newest first); every header
 *  word is served; `filter_keys` = the setup keys at least one reel passes (🎾 also by a secondary chip). */
export type RpWinnerRow = {
  key?: string; symbol: string; wins?: number; wins_text?: string | null; newest_date?: string | null;
  newest_text?: string | null; setup?: string | null; setup_text?: string | null; timing?: string | null;
  timing_text?: string | null; best_close_gain_pct?: number | null; filter_keys?: string[]; videos: RpWinner[];
};
export type RpWinnersCounts = {
  videos?: number; single_day?: number; multi_day?: number; skipped_window?: number; skipped_bad?: number;
  no_sidecar?: number; skipped_label?: number;
};
export type RpSetupOption = { key: string; label: string; count: number };
export type RpWinnersPayload = {
  state: RpState | string; title?: string; tab?: string; text?: string | null; note?: string; window?: string;
  window_note?: string; summary_text?: string | null; counts?: RpWinnersCounts; rows?: RpWinnerRow[];
  setups?: RpSetupOption[]; jump_missing_text?: string | null;
};

/** The 'show every card' filter key (== backend constants.WIN_SETUP_ALL). Its label is SERVED. */
export const RP_SETUP_ALL = 'all';
/** localStorage key of the picked 🏆 setup filter (a per-viewer convenience; a private window just forgets it). */
export const RP_SETUP_LS_KEY = 'rp_winners_setup';

/** The served filter row, in served order: entries with a non-empty string key + string label + finite count ≥ 0;
 *  anything else dropped. Not a list → []. Pure. */
export function rpSetupOptions(x: unknown): RpSetupOption[] {
  if (!Array.isArray(x)) return [];
  return x.filter((o): o is RpSetupOption => !!o && typeof o === 'object'
    && typeof o.key === 'string' && o.key.length > 0 && typeof o.label === 'string'
    && typeof o.count === 'number' && Number.isFinite(o.count) && o.count >= 0);
}

/** Does a served ROW pass the picked filter? 'all' → every row; otherwise the key must be in the served
 *  `filter_keys` (the server decides: a 🎾 float-gated reel carries no 🎾 key). Junk → false. Pure. */
export function rpRowMatches(r: { filter_keys?: unknown } | null | undefined, key: string): boolean {
  if (key === RP_SETUP_ALL) return true;
  return !!r && rpList(r.filter_keys).includes(key);
}

/** The served rows that pass the filter, served order kept (the FE never reorders); a row with no reel list is
 *  dropped. Pure. */
export function rpFilterWinnerRows(rows: unknown, key: string): RpWinnerRow[] {
  if (!Array.isArray(rows)) return [];
  return rows.filter((r): r is RpWinnerRow => !!r && typeof r === 'object' && Array.isArray(r.videos)
    && rpRowMatches(r, key));
}

/** The filter key actually applied: the remembered pick when the server serves it WITH a count above 0; anything
 *  else (an unknown key, a 0-count key — 2026-11-22 review fix (d)) → 'all', so nothing is hidden by a stale pick. */
export function rpPickedFilter(opts: RpSetupOption[], picked: string): string {
  return opts.some((o) => o.key === picked && (o.count > 0 || o.key === RP_SETUP_ALL)) ? picked : RP_SETUP_ALL;
}

/** The ONE stock row the URL opens expanded (`sym`, upper-cased; '' when absent). Pure. */
export function rpWinnersSym(params: URLSearchParams): string {
  return (params.get(RP_WINNERS_SYM_PARAM) || '').trim().toUpperCase();
}

/** The served setup / class / stopped / timing chips of a 🏆 card — served text only; `stopped` only when the served
 *  flag is exactly `true`; `also` = the served words of the other setups armed / A+ that day. Pure. */
export function rpWinnerLabelChips(v: RpWinnerLabelFields | null | undefined): {
  setup: string; cls: string; stopped: string; timing: string; also: string[];
} {
  if (!v) return { setup: '', cls: '', stopped: '', timing: '', also: [] };
  return {
    setup: rpText(v.setup_text), cls: rpText(v.setup_class_text),
    stopped: v.stopped_before_peak === true ? rpText(v.stopped_text) : '', timing: rpText(v.timing_text),
    also: rpList(v.setup_chips_text).filter((s) => s.length > 0),
  };
}

/** The remembered filter key, or '' when there is none / storage is blocked. */
export function rpReadSetupFilter(): string {
  try { return window.localStorage.getItem(RP_SETUP_LS_KEY) || ''; } catch { return ''; }
}

export function rpWriteSetupFilter(key: string): void {
  try { window.localStorage.setItem(RP_SETUP_LS_KEY, key); } catch { /* private window: the pick lasts this visit */ }
}

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

// ── 🏆 chip → jump to that win's replay at its peak (2026-11-22, pwjump spec §3.3) ──────────────────────────────────
// Ajay 2026-11-22, verbatim: "New feature when I click on this past winner tag take me to that video so change the date
// and focus me on that video at that. time" · "past winner 11-18 +57%". Navigation only: no gate, no push, no rank, no
// label. A day-card 🏆 chip links to `?…[&date=<win day>]&winners=1&sym=<SYM>&reel=<sub>/<file>`; the 🏆 section opens
// that ONE reel, scrolls to it and opens it at the reel's SERVED second (backend store.seek_seconds — no clock arithmetic
// here). The origin history entry is marked `card=<served date>/<file>` (and loses any `reel`) so Back lands on the card.
// UNMEASURED.

/** The URL param naming the ONE 🏆 reel a jump opens: `${sub}/${file}`. */
export const RP_REEL_PARAM = 'reel';
/** The URL param marking the day card a jump started from: `${served date}/${file}`. */
export const RP_CARD_PARAM = 'card';
/** The 🏆 reel folders (== backend constants.WINNER_SUB_KEYS, test-pinned). */
export const RP_WINNER_SUBS = ['winners', 'multiday'] as const;
/** A served reel file name (== backend constants.FILE_RE, test-pinned): no '/', no leading dot, .mp4. */
export const RP_FILE_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.mp4$/;
export type RpJumpTarget = { symbol: string; day: string; sub: string; file: string; reel: string };

const RP_DAY_RE = /^\d{4}-\d{2}-\d{2}$/;

/** `${sub}/${file}` when `sub` is a 🏆 folder and `file` a served reel name; anything else → ''. Pure. */
export function rpReelKey(sub: unknown, file: unknown): string {
  if (typeof sub !== 'string' || !(RP_WINNER_SUBS as readonly string[]).includes(sub)) return '';
  if (typeof file !== 'string' || !RP_FILE_RE.test(file)) return '';
  return `${sub}/${file}`;
}

/** The day-card 🏆 chips with their jump target, in served order. An entry with no non-empty string `text` is dropped
 *  (the rpPastWinChips rule). `target` is non-null only when the card's symbol is a non-empty string, the entry's `day`
 *  is YYYY-MM-DD and its `sub` / `file` name a 🏆 reel. Pure. */
export function rpPastWinItems(v: (RpPastWinFields & { symbol?: unknown }) | null | undefined):
  { text: string; target: RpJumpTarget | null }[] {
  const list = v && Array.isArray(v.past_winner) ? v.past_winner : [];
  const symbol = v && typeof v.symbol === 'string' && v.symbol.trim().length > 0 ? v.symbol : '';
  const out: { text: string; target: RpJumpTarget | null }[] = [];
  for (const w of list) {
    const e = w && typeof w === 'object' ? w : null;
    const text = rpText(e ? e.text : undefined);
    if (!text) continue;
    const reel = e ? rpReelKey(e.sub, e.file) : '';
    const day = e && typeof e.day === 'string' && RP_DAY_RE.test(e.day) ? e.day : '';
    out.push({ text, target: symbol && day && reel && e
      ? { symbol, day, sub: e.sub as string, file: e.file as string, reel } : null });
  }
  return out;
}

/** The jump URL: a COPY of `prev` with winners=1, sym, reel set and `card` deleted; `date` = the win's day ONLY when
 *  the server lists that session (otherwise `date` is left exactly as it was). Every other param rides along. Pure. */
export function rpJumpParams(prev: URLSearchParams, t: RpJumpTarget, dates: string[]): URLSearchParams {
  const next = new URLSearchParams(prev);
  next.set(RP_WINNERS_PARAM, '1');
  next.set(RP_WINNERS_SYM_PARAM, t.symbol);
  next.set(RP_REEL_PARAM, t.reel);
  next.delete(RP_CARD_PARAM);
  if (dates.includes(t.day)) next.set(RP_DATE_PARAM, t.day);
  return next;
}

/** `${date}/${file}` of a day card; '' when either is not a non-empty string. Pure. */
export function rpCardKey(date: unknown, file: unknown): string {
  return typeof date === 'string' && date && typeof file === 'string' && file ? `${date}/${file}` : '';
}

/** The origin entry of a jump: a COPY of `prev` with card=rpCardKey(date, file) AND `reel` deleted (pwjump C2 — the
 *  origin is the card, never a reel). An empty key → the copy unchanged (reel kept). Pure. */
export function rpOriginParams(prev: URLSearchParams, date: string | null, file: string): URLSearchParams {
  const next = new URLSearchParams(prev);
  const key = rpCardKey(date, file);
  if (!key) return next;
  next.set(RP_CARD_PARAM, key);
  next.delete(RP_REEL_PARAM);
  return next;
}

/** The `card` param, or ''. Pure. */
export function rpCardParam(params: URLSearchParams): string {
  return params.get(RP_CARD_PARAM) || '';
}

/** The `reel` param when it is exactly `${sub}/${file}` (one '/', a 🏆 folder, a served reel name); else ''. Pure. */
export function rpJumpReel(params: URLSearchParams): string {
  const r = params.get(RP_REEL_PARAM) || '';
  const parts = r.split('/');
  if (parts.length !== 2) return '';
  return rpReelKey(parts[0], parts[1]) === r ? r : '';
}

/** The identity of ONE jump (pwjump C1): '' when there is no reel; else `${reel}|${n}` — a new reel OR a new click on
 *  the same chip (n = the board's click count) gives a new key. Pure. */
export function rpJumpKey(reel: string, n: number): string {
  return reel ? `${reel}|${n}` : '';
}

/** The jump's reel: ONLY inside the row whose served symbol, trimmed + upper-cased (the rpWinnersSym normal form), is
 *  `sym`; ONLY the video whose rpReelKey(sub, file) is `reel` and whose rpWinnerSrc is non-empty. Anything else → null —
 *  never another row, never another reel. Pure. */
export function rpFindReel(rows: unknown, sym: string, reel: string): { row: RpWinnerRow; video: RpWinner } | null {
  const want = typeof sym === 'string' ? sym.trim().toUpperCase() : '';
  if (!want || !reel || !Array.isArray(rows)) return null;
  for (const row of rows) {
    if (!row || typeof row !== 'object' || typeof row.symbol !== 'string') continue;
    if (row.symbol.trim().toUpperCase() !== want || !Array.isArray(row.videos)) continue;
    for (const video of row.videos) {
      if (video && typeof video === 'object' && rpReelKey(video.sub, video.file) === reel && rpWinnerSrc(video) !== '') {
        return { row: row as RpWinnerRow, video: video as RpWinner };
      }
    }
  }
  return null;
}

/** The served seek second when it is a finite number > 0; anything else → null (the video opens at the start). Pure. */
export function rpSeekSeconds(v: { seek_s?: unknown } | null | undefined): number | null {
  const s = v ? v.seek_s : undefined;
  return typeof s === 'number' && Number.isFinite(s) && s > 0 ? s : null;
}

/** The src with a media fragment `#t=<served second>` (iOS ignores currentTime before metadata); no second → src. */
export function rpSeekSrc(src: string, seek: number | null): string {
  return src && seek != null ? `${src}#t=${seek}` : src;
}

/** A plain left click (no ⌘ / ctrl / shift / alt, button 0) — anything else is left to the browser (new tab). Pure. */
export function rpPlainClick(e: { button?: number; metaKey?: boolean; ctrlKey?: boolean; shiftKey?: boolean; altKey?: boolean }): boolean {
  return (e.button ?? 0) === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;
}
