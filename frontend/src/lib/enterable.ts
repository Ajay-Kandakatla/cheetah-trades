/* 🎯 enterable — the FE mirror of backend/supply_demand/enterable.py.
 *
 * Ajay 2026-09-15: "We really need to figure out the entries, I only wanna see
 * the stocks that are enterable. ... I do not want to see not enterable alerts
 * or stocks in any of the chart maps."
 *
 * THIS FILE COMPUTES NO VERDICT. The verdict, its reason codes, the sentences
 * behind them and the study's own status are all SERVED — built on the backend
 * from the enforcing constants (alert_gates.ALERT_MIN_ROOM_PCT,
 * ALERT_MAX_ABOVE_DEMAND_PCT, FLOOR_HELD_STATES, premarket_entry's measured
 * drags). Everything here is a renderer and a stable partition: it reads
 * `verdict`, `reason_short` and `reason_text` exactly as they arrive. A second
 * copy of the rule in TSX is a second, drifting engine — the mistake this app
 * has already paid for once with the room read.
 *
 * The partition is PINNED against the same file the backend test reads,
 * backend/tests/fixtures/enterable_mirror_2026_09_15.json. Edit the fixture and
 * both suites fail.
 *
 * NOTHING IS EVER SILENTLY LOST. A row with no read (a pending bounce-room row,
 * a legacy doc, a name the store has no bands for) is NEVER hidden: it is kept,
 * placed last, and counted separately so the count line can say so.
 */

/** premarket_entry.GRADE_READY / GRADE_WATCH / GRADE_BLOCKED, as served. */
export type EnterableVerdict = 'READY' | 'WATCH' | 'BLOCKED';

/** enterable.KIND_DEMAND / KIND_SUPPLY_BREAK / KIND_NA, as served. */
export type EnterableKind = 'demand' | 'supply_break' | 'n/a';

/** Which gate reads what. `floor_state` is the sweep read's own word — the FE
 *  never compares it to a state literal, the backend does that against
 *  alert_gates.FLOOR_HELD_STATES. */
export type EnterableGates = {
  room_ok?: boolean | null;
  prox_ok?: boolean | null;
  floor_state?: string | null;
  /** false = today's session low was not in the floor read (pre-market, or a
   *  tile read off the closed print). */
  session_low?: boolean | null;
};

/** The print the read was taken on, and where it came from: 'live' = the one
 *  bulk snapshot the board fans out; 'scan' = the closed scan print (the tape
 *  is down, or the snapshot had nothing usable). */
export type EnterablePrint = { px?: number | null; source?: 'live' | 'scan' | string | null };

/** premarket_entry.approach_drag / day_change_drag — measured, 2026-09-08. */
export type EnterableDrag = { key: string; text?: string | null; [k: string]: unknown };

/** The entry-trigger study's survivor, when one ever lands. `ok` null = the
 *  trigger could not be read (never "fired"). */
export type EnterableSurvivor = {
  key: string;
  ok?: boolean | null;
  text?: string | null;
  touch_date?: string | null;
  [k: string]: unknown;
};

/** What the study says about itself, carried on every read so a chip can never
 *  show a verdict without its status. */
export type EnterableMeasured = {
  status: string;
  run_date?: string | null;
  n_episodes?: number | null;
  survivor_key?: string | null;
  mdl?: number | null;
  script?: string | null;
};

/** The served room block. Deliberately NOT bounceRoom's RoomRead: the backend
 *  normalises CLEAR (nothing overhead) to `{state: 'CLEAR', room_pct: null}`
 *  and serves `room: null` ONLY for an unreadable print, so the two can be told
 *  apart on the page. */
export type EnterableRoom = {
  state?: string | null;
  room_pct?: number | null;
  room_pct_raw?: number | null;
  target?: number | null;
  touches?: number | null;
  band?: { lo?: number | null; hi?: number | null } | null;
  weak?: boolean | null;
};

/** backend/supply_demand/enterable.py::read() / assess() — mirror. */
export type EnterableRead = {
  kind: EnterableKind | string;
  /** null on the n/a kind: there is no demand read for those rows at all. */
  verdict: EnterableVerdict | null;
  /** Machine reason codes, in the order the backend appended them. */
  reasons: string[];
  /** One sentence per reason, already scrubbed for his surfaces. */
  reason_text: string[];
  /** The short label the chip and the count line print, verbatim. */
  reason_short: string[];
  gates?: EnterableGates | null;
  print?: EnterablePrint | null;
  drags?: EnterableDrag[] | null;
  band?: { lo: number; hi: number } | null;
  room?: EnterableRoom | null;
  survivor?: EnterableSurvivor | null;
  measured?: EnterableMeasured | null;
};

/** backend/supply_demand/enterable.py::measured_verdict() — the banner. */
export type EnterableStudy = {
  headline: string;
  body?: string | null;
  fallback_note?: string | null;
  limits?: string | null;
  status?: string | null;
};

/** What the filter hides. 'enterable' = the served BLOCKED verdict only; 'all'
 *  = nothing (the `?show=all` escape hatch). */
export type EnterableMode = 'enterable' | 'all';

/** Is this row shown under `mode`? An unknown read (null, or a verdict the
 *  backend did not grade) is ALWAYS shown — never hidden on an absence. */
export function isShown(read?: EnterableRead | null, mode: EnterableMode = 'enterable'): boolean {
  if (mode === 'all') return true;
  return read?.verdict !== 'BLOCKED';
}

/** How the study's own status reaches a TOOLTIP (m6, 2026-09-15).
 *
 *  The backend serves `measured.status` as a MACHINE token — `no_signal`,
 *  `pending`, `separates` — because the rules section, the alert-status payload
 *  and both suites key off it. Pasted raw at the end of an English sentence it
 *  read "…the push gate needs one of ('intact',) — no_signal", which looks like
 *  a leaked identifier, not a measurement.
 *
 *  This substitutes NOTHING and decides NOTHING: it prints the SERVED token's
 *  own words with the underscores taken out, under the key the backend gave the
 *  block. The full sentence — the study's headline and its numbers — is served
 *  separately as `enterable_study` and is passed in when the surface has it. */
export function measuredStatusWords(status?: string | null): string {
  if (typeof status !== 'string') return '';
  const words = status.trim().replace(/_+/g, ' ').replace(/\s+/g, ' ').trim();
  return words ? `measured: ${words}` : '';
}

/** The chip a surface prints, or null when there is nothing to say.
 *    READY   → "🎯 READY"
 *    WATCH   → "🎯 WATCH · <served reason_short[0]>"
 *    BLOCKED → "⛔ <served reason_short[0]>"
 *    n/a     → "n/a", muted, the served sentence in the title
 *    no read → null (unknown never wears a chip)
 *  The title carries every served reason sentence, the closed-bar caveat when
 *  the read was taken off the scan print, and what the study says about itself:
 *  the served `study.headline` when the surface holds the banner payload,
 *  otherwise the served status IN WORDS (never the raw token — m6). No verdict
 *  maths and no number is computed here. */
export function enterableChipText(read?: EnterableRead | null, study?: EnterableStudy | null): {
  text: string;
  tone: 'ready' | 'watch' | 'blocked' | 'na';
  title: string;
} | null {
  if (!read) return null;
  const lines = (read.reason_text || []).filter((s) => typeof s === 'string' && s.length > 0);
  const short = (read.reason_short || []).filter((s) => typeof s === 'string' && s.length > 0);

  const bits: string[] = [...lines];
  if (read.print?.source === 'scan') bits.push('closed-bar read (no live print)');
  const headline = typeof study?.headline === 'string' ? study.headline.trim() : '';
  const words = headline || measuredStatusWords(read.measured?.status);
  if (words) bits.push(words);
  const title = bits.join(' — ');

  if (read.kind === 'n/a') return { text: 'n/a', tone: 'na', title };
  const verdict = read.verdict;
  if (!verdict) return null;
  if (verdict === 'READY') return { text: '🎯 READY', tone: 'ready', title };
  if (verdict === 'WATCH') {
    return { text: short[0] ? `🎯 WATCH · ${short[0]}` : '🎯 WATCH', tone: 'watch', title };
  }
  return { text: short[0] ? `⛔ ${short[0]}` : '⛔ BLOCKED', tone: 'blocked', title };
}

/** The label a hidden row is counted under: the SERVED short reason, never a
 *  sentence this file builds. `blocked` only when the backend sent none. */
export const UNLABELLED_REASON = 'blocked';

export type EnterablePartition<T> = {
  /** Shown rows in their SERVED order, then the rows with no read in theirs. */
  rows: T[];
  hidden: number;
  unread: number;
  hiddenByReason: Record<string, number>;
};

/** A stable partition — NOT a sort. Shown rows keep the order the board chose
 *  for them, rows without a read follow in theirs, and the hidden ones are
 *  counted by their served reason so the count line can name them.
 *
 *  `enabled` false → every row back, untouched, and zero counts. */
export function partitionEnterable<T>(
  rows: readonly T[],
  symbolOf: (row: T) => string | null | undefined,
  map?: Map<string, EnterableRead | null | undefined> | null,
  enabled = false,
): EnterablePartition<T> {
  const all = (rows || []) as readonly T[];
  if (!enabled) return { rows: all.slice(), hidden: 0, unread: 0, hiddenByReason: {} };

  const shown: T[] = [];
  const unread: T[] = [];
  const hiddenByReason: Record<string, number> = {};
  let hidden = 0;

  for (const row of all) {
    const symbol = String(symbolOf(row) ?? '').toUpperCase();
    const read = symbol ? map?.get(symbol) ?? null : null;
    if (!read || !read.verdict) {
      unread.push(row);
      continue;
    }
    if (isShown(read)) {
      shown.push(row);
      continue;
    }
    hidden += 1;
    const key = (read.reason_short || []).find((s) => typeof s === 'string' && s.length > 0)
      || UNLABELLED_REASON;
    hiddenByReason[key] = (hiddenByReason[key] || 0) + 1;
  }

  return { rows: [...shown, ...unread], hidden, unread: unread.length, hiddenByReason };
}

/** The top reasons behind a hidden count, most first, ties by label so the
 *  line does not reshuffle between renders. */
export function topHiddenReasons(
  hiddenByReason: Record<string, number> | null | undefined,
  limit = 3,
): { reason: string; n: number }[] {
  const entries = Object.entries(hiddenByReason || {});
  entries.sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0]));
  return entries.slice(0, limit).map(([reason, n]) => ({ reason, n }));
}
