/* 🔥 Hottest — multi-column sort, the pure half (2026-09-28).
 *
 * Ajay 2026-09-28: "can you help me with multi column sort".
 *
 * The SERVER sorts (rotation/hottest.py): the payload keeps only
 * `names_per_group` rows per group, so a browser sort would rank the visible 25
 * and never reach the 46th name. This file only decides what to ASK for and
 * how to DRAW what came back:
 *
 *  - `sort` + `dir` stay exactly as they were (the primary key); tie-breaks
 *    ride ONE extra param, `then_by=key:dir,key:dir`.
 *  - A plain click is today's rule and clears the tie-breaks; shift / ⌘ / ctrl
 *    adds a tie-break, flips it, then removes it.
 *  - Every mark on screen, and every click, reads `sortBasis()`: the SERVED
 *    plan once a read has landed, the request in flight while it has not —
 *    never a guessed client state sitting over rows that were ranked on
 *    something else (e.g. after a click whose read failed).
 *
 * PURE: no `.sort(`, no clock, no set* call, nothing imported from the board. */

export type HsSortDir = 'desc' | 'asc';
export type HsSortKey = { key: string; dir: HsSortDir };
export type HsSortState = { sort: string; dir: HsSortDir; thenBy: HsSortKey[] };

/** Primary + up to two tie-breaks. Contract: equals hottest.py MAX_SORT_KEYS. */
export const HS_MAX_SORT_KEYS = 3;
/** Contract: equals hottest.py DEFAULT_SORT. */
export const HS_DEFAULT_SORT = 'rel_5d';

const isDir = (v: unknown): v is HsSortDir => v === 'desc' || v === 'asc';

/** Every column opens DESC (its interesting end) except Next ER, which opens
 *  ASC — "who reports soonest". Today's rule, moved here unchanged. */
export function defaultDirFor(key: string): HsSortDir {
  return key === 'next_earnings' ? 'asc' : 'desc';
}

const flip = (d: HsSortDir): HsSortDir => (d === 'desc' ? 'asc' : 'desc');

/** What one header click asks for next.
 *
 *  PLAIN: today's click, and the tie-breaks go — same key flips, a new key
 *  opens at its default direction.
 *  ADDITIVE (shift / ⌘ / ctrl, or the "then by" control): the primary flips;
 *  a tie-break cycles default dir → flipped → removed; a new key is appended
 *  while there is a free slot. At the cap the SAME object comes back, which the
 *  board reads as "no change, no fetch". */
export function nextSortState(s: HsSortState, key: string, additive: boolean,
                              maxKeys = HS_MAX_SORT_KEYS): HsSortState {
  if (!additive) {
    if (key === s.sort) return { sort: s.sort, dir: flip(s.dir), thenBy: [] };
    return { sort: key, dir: defaultDirFor(key), thenBy: [] };
  }
  if (key === s.sort) return { sort: s.sort, dir: flip(s.dir), thenBy: s.thenBy };
  const at = s.thenBy.findIndex((t) => t.key === key);
  if (at >= 0) {
    const cur = s.thenBy[at];
    if (cur.dir === defaultDirFor(key)) {
      return { ...s, thenBy: s.thenBy.map((t, i) => (i === at ? { key, dir: flip(cur.dir) } : t)) };
    }
    return { ...s, thenBy: s.thenBy.filter((_, i) => i !== at) };
  }
  if (1 + s.thenBy.length < maxKeys) {
    return { ...s, thenBy: [...s.thenBy, { key, dir: defaultDirFor(key) }] };
  }
  return s;
}

/** The query-string tail. A single-key sort sends NOTHING extra — the URL is
 *  byte-identical to the one the board sent before tie-breaks existed. */
export function thenByParam(t: HsSortKey[]): string {
  if (!t.length) return '';
  return '&then_by=' + encodeURIComponent(t.map((k) => `${k.key}:${k.dir}`).join(','));
}

/** The tie-breaks the server APPLIED. Absent or malformed → none; never the
 *  client's request standing in for the server's answer. */
export function shownThenBy(d?: { sorted_then_by?: unknown } | null): HsSortKey[] {
  const raw = d?.sorted_then_by;
  if (!Array.isArray(raw)) return [];
  const out: HsSortKey[] = [];
  for (const e of raw) {
    if (!e || typeof e !== 'object') continue;
    const key = (e as { key?: unknown }).key;
    const dir = (e as { dir?: unknown }).dir;
    if (typeof key === 'string' && key && isDir(dir)) out.push({ key, dir });
  }
  return out;
}

/** THE plan the header draws and every click builds on.
 *
 *  `shown` is the board's pinned primary rule (`shownSortKey`), used while a
 *  read is in flight (or none has landed): the plan is then the request. Once
 *  a read has landed the WHOLE plan is what the server says it applied —
 *  primary (`sorted_by`), direction and tie-breaks together. The primary must
 *  come from the payload too: a click whose read FAILED leaves the old board on
 *  screen, and a primary taken from the client state would draw "Quality 1▲
 *  then Q EPS ▼" over rows still ranked on 5 days (critic, 2026-09-28).
 *  `shown` stands in only when the payload carries no usable `sorted_by`.
 *  PURE — no set*, no clock. */
export function sortBasis(shown: string, state: HsSortState,
                          d: { sorted_by?: unknown; sorted_dir?: unknown;
                               sorted_then_by?: unknown } | null | undefined,
                          loading: boolean): HsSortState {
  if (loading || !d) return { sort: shown, dir: state.dir, thenBy: state.thenBy };
  return {
    sort: typeof d.sorted_by === 'string' && d.sorted_by ? d.sorted_by : shown,
    dir: isDir(d.sorted_dir) ? d.sorted_dir : state.dir,
    thenBy: shownThenBy(d),
  };
}

/** Same plan, compared by value (the tie-break list in order). */
export function samePlan(a: HsSortState, b: HsSortState): boolean {
  return a.sort === b.sort && a.dir === b.dir && a.thenBy.length === b.thenBy.length
    && a.thenBy.every((t, i) => t.key === b.thenBy[i].key && t.dir === b.thenBy[i].dir);
}

/** A header's mark. One key: exactly the old arrow (' ▼' / ' ▲' / ''). Several:
 *  a priority number with its direction — ' 1▼', ' 2▲' … */
export function sortMark(key: string, primary: string, primaryDir: HsSortDir,
                         then: HsSortKey[]): string {
  const arrowOf = (d: HsSortDir) => (d === 'desc' ? '▼' : '▲');
  if (!then.length) return key === primary ? ` ${arrowOf(primaryDir)}` : '';
  if (key === primary) return ` 1${arrowOf(primaryDir)}`;
  const at = then.findIndex((t) => t.key === key);
  return at >= 0 ? ` ${at + 2}${arrowOf(then[at].dir)}` : '';
}

/** The board's opening order: 5 days, high → low, no tie-breaks. */
export function isDefaultSort(s: HsSortState): boolean {
  return s.sort === HS_DEFAULT_SORT && s.dir === 'desc' && s.thenBy.length === 0;
}
