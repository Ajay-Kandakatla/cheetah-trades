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
 * The un-hide-by-reason ignore set (2026-09-17) does not change that sentence:
 * it decides only what is DRAWN. No verdict is computed, recomputed or
 * overridden here — an un-hidden row is still the served BLOCKED.
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

/* ── 🎯 UN-HIDE BY REASON (Ajay 2026-09-17: "Can you give me a toggle for the
 *    room too? I am not seeing all stocks on the selected filter due to this
 *    now") ──────────────────────────────────────────────────────────────────
 *
 * THIS STILL COMPUTES NO VERDICT. The ignore set decides what is DRAWN; it
 * never decides what is enterable. An un-hidden row is BLOCKED in the payload,
 * BLOCKED on its tile chip, blocked on the phone and refused by every lane.
 * There is no backend counterpart by design — a view preference must be unable
 * to reach a gate. */

/** Served reason CODES a view un-hides. Never a label, never a base code. */
export type IgnoreSet = ReadonlySet<string>;
export const NO_IGNORE: IgnoreSet = new Set<string>();

/** One chip on the count line. `code` + `label` are SERVED, verbatim. */
export type EnterableReasonStat = {
  /** The served `reasons[i]`, or UNLABELLED_REASON for the synthesised stat. */
  code: string;
  /** The served `reason_short[i]`; '' when the backend sent none. */
  label: string;
  /** BLOCKED rows on this list CARRYING `code` — informational, never the sort key. */
  total: number;
  /** Rows attributed to `code` with an EMPTY ignore set — THE SORT KEY. */
  baseline: number;
  /** Rows STILL hidden and attributed to `code` — the number the chip prints. */
  hidden: number;
  /** In the ignore set. */
  ignored: boolean;
  /** false when `label` is empty — rendered as text, never as a button. */
  toggleable: boolean;
};

/** The (code, label) pairs a BLOCKED row is blocked for, zipped BY INDEX —
 *  `assess()` builds `reasons` / `reason_text` / `reason_short` from one code
 *  list, so `reasons[i] ↔ reason_short[i]`.
 *
 *  `[]` for a non-BLOCKED row, a missing / non-array `reasons`, or a non-string
 *  code anywhere in it — all of which FAIL CLOSED through `isShown` below. A
 *  code whose index is missing from `reason_short` (short array, '', non-string)
 *  yields label '' and makes the whole row un-hideable: un-hiding is always
 *  explicit, never silent. */
export function blockReasons(read?: EnterableRead | null): { code: string; label: string }[] {
  if (!read || read.verdict !== 'BLOCKED') return [];
  const codes = read.reasons;
  if (!Array.isArray(codes) || !codes.length) return [];
  const shorts = Array.isArray(read.reason_short) ? read.reason_short : [];
  const out: { code: string; label: string }[] = [];
  for (let i = 0; i < codes.length; i += 1) {
    const code = codes[i];
    if (typeof code !== 'string' || !code) return [];
    const raw = shorts[i];
    out.push({ code, label: typeof raw === 'string' ? raw : '' });
  }
  return out;
}

/** Is this row shown under `mode`? An unknown read (null, or a verdict the
 *  backend did not grade) is ALWAYS shown — never hidden on an absence.
 *
 *  A BLOCKED row comes back ONLY when EVERY one of its block reasons has been
 *  un-hidden. A row blocked for `proximity` AND `room` stays hidden while only
 *  `room` is un-hidden — otherwise the count line lies about what he is looking
 *  at. A BLOCKED row with nothing named, or with a block reason the backend
 *  sent no label for, can never be un-hidden at all. */
export function isShown(
  read?: EnterableRead | null,
  mode: EnterableMode = 'enterable',
  ignore: IgnoreSet = NO_IGNORE,
): boolean {
  if (mode === 'all') return true;
  if (read?.verdict !== 'BLOCKED') return true;
  const rs = blockReasons(read);
  if (!rs.length) return false;
  if (rs.some((r) => !r.label)) return false;
  return rs.every((r) => ignore.has(r.code));
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
  /** UNCHANGED, keyed by the served LABEL — the shared-fixture pin reads this. */
  hiddenByReason: Record<string, number>;
  /** Rows drawn ONLY because their every block reason is in the ignore set. */
  unhidden: number;
  /** The chips, ordered per the rule below. Empty when the filter is off. */
  reasons: EnterableReasonStat[];
};

/** Which stat a hidden row is counted under: its FIRST block reason whose code
 *  is not in the ignore set AND which the backend labelled. `null` → the
 *  synthesised UNLABELLED_REASON stat.
 *
 *  Skipping the unlabelled ones is what keeps this identical to the line today
 *  at an empty ignore set: `partitionEnterable` has always counted a hidden row
 *  under the first NON-EMPTY `reason_short`, and `reason_short[i]` is the label
 *  of `reasons[i]`. So `baseline` is, index for index, the number the shipped
 *  board prints. */
function attribute(
  rs: readonly { code: string; label: string }[],
  ignore: IgnoreSet,
): { code: string; label: string } | null {
  for (const r of rs) {
    if (!r.label) continue;
    if (ignore.has(r.code)) continue;
    return r;
  }
  return null;
}

/** Chip order: `baseline` desc, then label asc, then code asc.
 *
 *  `baseline` — not the live `hidden`, and not `total` — because two properties
 *  are both required: at an empty ignore set the printed number IS `baseline`,
 *  so the line stays byte-identical to today's `topHiddenReasons` order; and
 *  `baseline` never moves when he clicks, so chips never reshuffle under his
 *  cursor. The synthesised stat has no label, so it sorts under its code, which
 *  is the very key (`blocked`) the line already counts it by. */
function sortStats(stats: EnterableReasonStat[]): EnterableReasonStat[] {
  return stats.sort((a, b) => (b.baseline - a.baseline)
    || (a.label || a.code).localeCompare(b.label || b.code)
    || a.code.localeCompare(b.code));
}

/** Merge per-section chip lists into one line (BondeBoard renders one count for
 *  several partitions). Sums by CODE, ORs `ignored`, ANDs `toggleable`, keeps
 *  the first non-empty served label, and re-sorts by the same rule. */
export function mergeReasonStats(
  parts: readonly EnterableReasonStat[][],
): EnterableReasonStat[] {
  const by = new Map<string, EnterableReasonStat>();
  for (const list of parts || []) {
    for (const s of list || []) {
      const cur = by.get(s.code);
      if (!cur) {
        by.set(s.code, { ...s });
        continue;
      }
      cur.total += s.total;
      cur.baseline += s.baseline;
      cur.hidden += s.hidden;
      cur.ignored = cur.ignored || s.ignored;
      cur.toggleable = cur.toggleable && s.toggleable;
      if (!cur.label && s.label) cur.label = s.label;
    }
  }
  return sortStats(Array.from(by.values()));
}

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
  ignore: IgnoreSet = NO_IGNORE,
): EnterablePartition<T> {
  const all = (rows || []) as readonly T[];
  if (!enabled) {
    return { rows: all.slice(), hidden: 0, unread: 0, hiddenByReason: {}, unhidden: 0, reasons: [] };
  }

  const shown: T[] = [];
  const unread: T[] = [];
  const hiddenByReason: Record<string, number> = {};
  let hidden = 0;
  let unhidden = 0;

  /* One walk, both attributions: `baseline` (ignore-independent, the order key)
   * and `hidden` (what this chip is still holding back). */
  const stats = new Map<string, EnterableReasonStat>();
  const stat = (code: string, label: string): EnterableReasonStat => {
    let s = stats.get(code);
    if (!s) {
      s = { code, label, total: 0, baseline: 0, hidden: 0,
            ignored: ignore.has(code), toggleable: Boolean(label) };
      stats.set(code, s);
    } else if (!s.label && label) {
      s.label = label;
      s.toggleable = true;
    }
    return s;
  };

  for (const row of all) {
    const symbol = String(symbolOf(row) ?? '').toUpperCase();
    const read = symbol ? map?.get(symbol) ?? null : null;
    if (!read || !read.verdict) {
      unread.push(row);
      continue;
    }
    if (read.verdict !== 'BLOCKED') {
      shown.push(row);
      continue;
    }

    const rs = blockReasons(read);
    for (const r of rs) stat(r.code, r.label).total += 1;

    const base = attribute(rs, NO_IGNORE);
    (base ? stat(base.code, base.label) : stat(UNLABELLED_REASON, '')).baseline += 1;

    if (isShown(read, 'enterable', ignore)) {
      shown.push(row);
      unhidden += 1;
      continue;
    }

    hidden += 1;
    const key = (read.reason_short || []).find((s) => typeof s === 'string' && s.length > 0)
      || UNLABELLED_REASON;
    hiddenByReason[key] = (hiddenByReason[key] || 0) + 1;
    const live = attribute(rs, ignore);
    (live ? stat(live.code, live.label) : stat(UNLABELLED_REASON, '')).hidden += 1;
  }

  return {
    rows: [...shown, ...unread],
    hidden,
    unread: unread.length,
    hiddenByReason,
    unhidden,
    reasons: sortStats(Array.from(stats.values())),
  };
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
