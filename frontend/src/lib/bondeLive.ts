/* 📈 Bonde — the live Today leg and the period-pair marks, as pure functions.
 *
 * Ajay 2026-09-20: "make his page more live".
 *
 * Everything in here is pure and tested on its own, because all of it is about
 * SAYING which session a number came from — and that is exactly the class of
 * thing a render test is bad at proving and a board is dangerous getting wrong.
 *
 * TWO RULES THIS FILE EXISTS TO HOLD:
 *
 * 1. THE COLUMN IS NEVER HALF LIVE. The backend (`sepa/bonde_live.py`) serves
 *    one basis for the whole board; on the close basis every row carries
 *    `today_pct: null` and this renders an em-dash. A cell that fell back to a
 *    last-close number under a "Today" header would be a different measurement
 *    wearing the same title.
 *
 * 2. THE COST SENTENCE IS BONDE'S OWN. `RESCAN_COST_SENTENCE` in
 *    HottestSectors is its own measured count over its own ~1.7k names — that board's
 *    count, not this one's. This board is capped at 260 names plus the
 *    benchmark, which is 2 snapshot calls, and that 2 is PINNED by
 *    `backend/tests/test_bonde_live.py::test_the_full_board_costs_exactly_two_snapshot_calls`,
 *    which counts the chunks a real `prices.bulk_snapshot` would send off
 *    `SECTION_CAP` and `_SNAP_CHUNK`. Importing Hottest's sentence here would
 *    print that board's universe size on a board of 260.
 */

/** The served day block. Exactly the keys `bonde_live.D1_KEYS` carries. */
export type BondeD1 = {
  basis?: string | null;
  live?: boolean | null;
  /** The market calendar's OWN words ("weekend", a holiday name), or null. */
  market_closed?: string | null;
  in_session?: boolean | null;
  session_window?: string | null;
  as_of?: string | null;
  close_as_of?: string | null;
  symbols?: number | null;
  live_names?: number | null;
  reason?: string | null;
  tape_session?: string | null;
  note?: string | null;
};

/** One row of the held-out table (§3.6's pinned shape). */
export type BondeHeldOut = {
  symbol: string;
  tier?: string | null;
  latest?: string | null;
  year_ago?: string | null;
};

/** What one ↻ Live prices click costs, in this board's own numbers. Pinned by
 *  the backend test named in the header — never typed twice, never Hottest's. */
export const BONDE_LIVE_COST_SENTENCE =
  'One snapshot read: 2 Massive snapshot calls (up to 260 board names plus RSP, '
  + '250 per call). Nothing is re-scanned.';

/** `period_ok: false` — the pair the growth board refuses. */
export const PAIR_WARN_TITLE =
  'This name’s newest quarter and its “year-ago” slot are NOT four fiscal quarters '
  + 'apart, so the growth percentage compares two different quarters. The 🚀 growth '
  + 'board refuses the same row.';

/** `period_ok: null` — 'unverifiable', which is not 'fine'. */
export const UNVERIFIED_TITLE =
  'no fiscal-period keys on file — the pair could not be checked';

const num = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null;

/** Signed, with a REAL minus sign, to match the rest of this board. */
export function signedPct(v: number | null | undefined, dp = 1): string {
  const x = num(v);
  if (x == null) return '—';
  return `${x > 0 ? '+' : ''}${x.toFixed(dp).replace('-', '−')}%`;
}

export function isLive(d1?: BondeD1 | null): boolean {
  return Boolean(d1?.live);
}

/** The Today cell: text, tone class and the title that names its basis.
 *
 *  On the close basis this is an em-dash on EVERY row, including rows whose
 *  price did come back — see rule 1 in the header. */
export function todayCell(
  row: { today_pct?: number | null } | null | undefined,
  d1?: BondeD1 | null,
): { text: string; tone: string; title: string } {
  const live = isLive(d1);
  if (!live) {
    const day = d1?.close_as_of || 'the last';
    const why = d1?.reason ? ` — ${d1.reason}` : '';
    return {
      text: '—', tone: 'bd-dim',
      title: `Today is not being shown: this board is on the ${day} close${why}. `
        + 'Every row on it reads the same session — a table that was live for some '
        + 'names and last-close for the rest would describe neither.',
    };
  }
  const v = num(row?.today_pct);
  if (v == null) {
    return {
      text: '—', tone: 'bd-dim',
      title: 'No live price came back for this name in the board’s snapshot. '
        + 'The rest of the column is this session.',
    };
  }
  return {
    text: signedPct(v, 1),
    tone: v > 0 ? 'bd-good' : v < 0 ? 'bd-bad' : 'bd-dim',
    title: 'This name’s own move so far in this session (not relative to the '
      + 'benchmark). Every other column comes from the last scan.',
  };
}

/** 'HH:MM ET' from the served UTC stamp, or null. */
export function etClock(iso?: string | null): string | null {
  if (!iso) return null;
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return null;
  try {
    return `${t.toLocaleTimeString('en-US', {
      timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false,
    })} ET`;
  } catch { return null; }
}

/** How the tape was tagged, in the words the other boards print. RTH adds
 *  nothing — the default case needs no badge (Rule #5). */
export function tapeLabel(tape?: string | null): string | null {
  switch (tape) {
    case 'premarket': return 'pre-mkt';
    case 'afterhours': return 'after-hrs';
    case 'closed': return 'tape closed';
    default: return null;
  }
}

/** The one line above the sections that says which session Today is. */
export function basisLine(d1?: BondeD1 | null): string {
  if (!d1) return 'Today = last close — no live price read was made';
  if (isLive(d1)) {
    const clock = etClock(d1.as_of);
    const tape = tapeLabel(d1.tape_session);
    return ['Today = live print',
            clock ? `as of ${clock}` : null,
            tape].filter(Boolean).join(' · ');
  }
  const day = d1.close_as_of ? ` ${d1.close_as_of}` : '';
  return `Today = last close${day}${d1.reason ? ` — ${d1.reason}` : ''}`;
}

/** The mark that rides a row whose year-over-year pair could not be trusted.
 *
 *  THREE states, never two: `false` is "checked and wrong", `null` is "could
 *  not be checked", `true` is "checked and fine". Collapsing null into true
 *  would print a tick over 352 of the scan's rows that nobody verified. */
export function periodMark(
  periodOk: boolean | null | undefined,
): { text: string; cls: string; title: string } | null {
  if (periodOk === false) return { text: '⚠ pair', cls: 'bd-pair-warn', title: PAIR_WARN_TITLE };
  if (periodOk === null || periodOk === undefined) {
    return { text: 'unverified', cls: 'bd-unverified', title: UNVERIFIED_TITLE };
  }
  return null;
}

/** The tier word, or an em-dash when the board WITHHELD it (a mismatched pair
 *  on a row that stays for its Episodic Pivot). Never an empty cell — blank
 *  reads as a rendering bug, an em-dash reads as "not stated". */
export function tierText(tier?: string | null): string {
  const t = (tier || '').trim();
  return t ? t : '—';
}

/** The board's OWN held-out sentence, lifted out of the served `note`.
 *
 *  Deliberately NOT retyped here: `sepa/bonde.py::note()` composes it from the
 *  count it actually held out, and two surfaces wording the same fact
 *  differently is how a board starts disagreeing with itself. When the
 *  sentence is not present (an older payload), this returns null and the block
 *  renders its columns without a header line rather than inventing prose. */
export function heldOutSentence(note?: string | null): string | null {
  const src = String(note || '');
  const at = src.search(/\bheld OUT\b/);
  if (at < 0) return null;
  // Back up to the start of the SENTENCE that carries it, not to the start of
  // the note — the note opens with his pass count, which belongs at the foot.
  const start = Math.max(src.lastIndexOf('.', at), src.lastIndexOf(';', at)) + 1;
  const end = src.indexOf('Listed under the board.', at);
  const cut = src.slice(start, end < 0 ? undefined : end + 'Listed under the board.'.length);
  return cut.trim() || null;
}
