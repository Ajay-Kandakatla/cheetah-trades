/* 🪜 BAND STRUCTURE (2026-09-16) — the CEILING above the print and the FLOOR
 * under it, as the frontend renders and orders them.
 *
 * THE ASK (Ajay 2026-09-16, two messages one minute apart):
 *   #1 "Now in all chartmaps tabs, can you prioritize stock by the thinnest
 *       over head or Supply zone where ever is applicable"
 *   #2 "Can you also make sure find stocks with greater support like the
 *       support bands are bigger and atleast another one very close if its
 *       falls below the first support level. Something like CRDO had at 149.
 *       It has another one right below it"
 *
 * One read answers both: least resistance above, most catch below.
 *
 * THIS FILE COMPUTES NOTHING. Every height, distance, gap and count is served
 * by backend/supply_demand/band_structure.py off ONE band selection
 * (`bounce_room.room_read` / `bounce_room.demand_read` over `zone_store`'s
 * uncapped `doc["bands"]`, board geometry, closed bars). What lives here is
 * (a) the mirror of the ordering key and (b) the chip's wording — and the
 * chip's wording is the SERVED `read.stat` string, not a sentence this file
 * assembles out of numbers. A percentage formatted in TSX is a second engine.
 *
 * THE ORDERING IS PINNED, BOTH SIDES, against
 * backend/tests/fixtures/band_structure_order_mirror_2026_09_16.json — the
 * same file backend/tests/test_band_structure_2026_09_16.py sorts. Edit the
 * fixture and both suites fail, which is the point.
 *
 * THE STUDY HAS RUN AND CAME BACK NULL. `MEASURED.status` is `no_signal`:
 * nothing was selected on any of the three out-of-sample splits, where the
 * study can only see a lift bigger than 2.8pp. So there is no score to show
 * and no grade to give, and what ships is the DESCRIPTIVE order (thinnest
 * ceiling first, the floor only breaking ties). `pending` is kept as a status
 * and behaves identically in every code path — a payload from a board that has
 * not picked up the run must land on the same fallback, never on a score. The
 * banner says all of this in his own words; this file never dresses the
 * fallback as a prediction.
 */

/** 'pending' behaves as 'no_signal' in every code path, same as 🧨. */
export type BandStructureStatus = 'separates' | 'no_signal' | 'pending';

/** One band as the read carries it — `zone_store`'s slim band, nothing more.
 *  There is no `mid` and no `volume`: the store drops them. */
export type BandStructureBand = {
  kind?: string | null;
  lo: number;
  hi: number;
  touches?: number | null;
  strength?: number | null;
  bars_since_test?: number | null;
  height_pct?: number | null;
};

/** The ceiling half — his ask #1. `state === 'CLEAR'` means nothing PROVEN
 *  overhead (the `alert_gates.is_proven_band` filter the whole app already
 *  uses), which is the thinnest ceiling there is and sorts first. */
export type BandStructureCeiling = {
  state?: string | null;
  band?: BandStructureBand | null;
  /** (hi − lo) / print × 100 of the first band overhead. null = no band. */
  height_pct?: number | null;
  /** how far up to that band, % of the print. */
  distance_pct?: number | null;
  walls_above?: number | null;
  /** lids still between the print and the 52-week high; null (never 0) when
   *  the doc carries no 252-bar high — unknown is not "none left". */
  walls_to_high?: number | null;
  at_highs?: boolean | null;
};

/** The floor half — his ask #2. `gap_pct` is null, NEVER 0, when there is no
 *  second band: "no second catch" and "the second catch touches the first"
 *  are opposite facts and must never render the same. */
export type BandStructureFloor = {
  band?: BandStructureBand | null;
  in_band?: boolean | null;
  distance_pct?: number | null;
  height_pct?: number | null;
  second?: BandStructureBand | null;
  gap_pct?: number | null;
  bands_below?: number | null;
};

/** What the study says about itself, carried on every read so a chip can
 *  never show a number without its status. */
export type BandStructureMeasured = {
  status: BandStructureStatus | string;
  run_date?: string | null;
  n_episodes?: number | null;
  oos_lift?: number | null;
  oos_ci?: number[] | null;
  mdl?: number | null;
  script?: string | null;
};

/** WHICH PRINT this read is about — `band_structure._print_block`, the same
 *  block shape `enterable.assess` already serves and `lib/enterable.ts:165`
 *  already reads (`read.print?.source`). ONE shape, not a second spelling.
 *
 *  `source` is `'live'` (a fresh trade) or `'scan'` (the stored close the
 *  snapshot fell back to), and `null` when the caller could not say — the
 *  backend serves unknown as unknown rather than asserting "live". */
export type BandStructurePrint = {
  px?: number | null;
  source?: string | null;
};

/** backend/supply_demand/band_structure.py::read() — mirror. */
export type BandStructureRead = {
  symbol?: string | null;
  kind?: string | null;
  /** false on a tab whose rows are not price-structure bands (the 🎯 n/a
   *  precedent). Such a row is never ordered and never chipped. */
  applicable?: boolean | null;
  ceiling?: BandStructureCeiling | null;
  floor?: BandStructureFloor | null;
  /** null outside the `separates` branch: there is no score to show. */
  score?: number | null;
  /** The SERVED sentence — "ceiling 3.5% wide, 0.5% up · floor 3.2% wide,
   *  2nd band 6.4% under". The chip prints it; it does not build it. */
  stat?: string | null;
  /** WHICH PRINT the two distances were measured on — the SERVED block
   *  (`read["print"]["source"]`), never a top-level `print_source`.
   *
   *  It was declared top-level for one round and the served block was never
   *  read, so both branches below were dead on every real payload and the
   *  tooltip always fell through to the rule sentence. The field a server
   *  sends is the field this file reads. */
  print?: BandStructurePrint | null;
  na_text?: string | null;
  measured?: BandStructureMeasured | null;
};

/** backend/supply_demand/band_structure.py::measured_verdict() — the banner. */
export type BandStructureStudy = {
  headline: string;
  body?: string | null;
  fallback_note?: string | null;
  limits?: string | null;
  status?: BandStructureStatus | string | null;
};

/** A row the ordering can read: its symbol and its band-structure read. */
export type BandStructureSortRow = { symbol: string; read?: BandStructureRead | null };

/** 'separates' only when the study says so. Anything else — no_signal,
 *  pending, a missing dict, a status nobody has heard of — falls back. */
export function bandStructureSeparates(status?: BandStructureStatus | string | null): boolean {
  return status === 'separates';
}

/* THE TWO COERCIONS BELOW ARE MIRRORS, NOT CONVENIENCES. The backend is the
 * canonical side (`supply_demand/band_structure.py`), and on a value the two
 * languages read differently the FRONTEND has to move. Both were latent on
 * today's payload — a `bool` applicable and rounded `float` metrics — and both
 * are pinned by rows in the shared fixture so a producer that starts sending a
 * string number, or a truthy non-`true` flag, cannot split the two orderings
 * without a suite going red. */

/** Mirrors backend `band_structure._f`: Python `float(x)`, with NaN and inf
 *  rejected. So a STRING numeric coerces (`"5.0"` is 5.0, as `float("5.0")`
 *  is), a bool coerces (`float(True)` is 1.0), and everything else — null,
 *  a list, an object, unparseable text — is None/null. */
function num(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v === 'boolean') return v ? 1 : 0;
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (typeof v === 'string') {
    const t = v.trim();
    // Number('') is 0 and Number('0x10') is 16; Python's float() raises on
    // both, so neither may reach the key as a number.
    if (!t || /^0[xXoObB]/.test(t)) return null;
    const n = Number(t);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/** Mirrors Python truthiness over JSON values, because the backend key asks
 *  `if not read.get("applicable")` — not `is True`. Every falsy JSON value is
 *  falsy in Python: null, false, 0, "", [], {}. JS disagrees on the last two,
 *  so they are spelled out. NaN is TRUTHY in Python and stays truthy here. */
function truthy(v: unknown): boolean {
  if (v === null || v === undefined || v === false) return false;
  if (typeof v === 'number') return v !== 0;
  if (typeof v === 'string') return v.length > 0;
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === 'object') return Object.keys(v as object).length > 0;
  return Boolean(v);
}

/** Mirrors backend `band_structure.band_structure_key(read, symbol)`.
 *
 *  ALWAYS a 7-tuple, in every branch, for the reason the backend says out
 *  loud: a branch that returned a shorter tuple would compare a float against
 *  a symbol the moment two branches met.
 *
 *    separates            → (0, −score, 0, 0, 0, 0, sym)     best score first
 *    separates, no score  → (1, 0, 0, 0, 0, 0, sym)          after every scored row
 *    pending / no_signal  → (0, ceilGroup, ceilHeight, floorGroup, gap,
 *                            −floorHeight, sym)
 *        ceilGroup: 0 CLEAR (nothing proven overhead — the thinnest there is)
 *                   1 a readable band, then thinnest by height
 *                   2 no readable ceiling — UNKNOWN IS NOT THIN
 *        floorGroup: 0 a second catch, closest gap first
 *                    1 one band only (its gap is UNKNOWN, never 0)
 *                    2 no band under the print
 *        −floorHeight: the last tiebreak, and the only place his "the support
 *                      bands are bigger" can decide anything.
 *    no read / not applicable → (2, …)                        LAST, ALWAYS
 *
 *  `status` defaults to the read's own measured status, so a row carrying the
 *  study's verdict needs no second argument. */
export function bandStructureOrderKey(
  read: BandStructureRead | null | undefined,
  symbol: string,
  status?: BandStructureStatus | string | null,
): [number, number, number, number, number, number, string] {
  const sym = String(symbol ?? '');
  if (!read || !truthy(read.applicable)) return [2, 0, 0, 0, 0, 0, sym];

  const st = status ?? read.measured?.status ?? 'pending';
  if (bandStructureSeparates(st)) {
    const score = num(read.score);
    if (score === null) return [1, 0, 0, 0, 0, 0, sym];
    return [0, -score, 0, 0, 0, 0, sym];
  }

  const c = read.ceiling || {};
  const f = read.floor || {};
  const cHeight = num(c.height_pct);
  let cGrp: number;
  let cVal: number;
  if (c.state === 'CLEAR') {
    cGrp = 0; cVal = 0;
  } else if (cHeight !== null) {
    cGrp = 1; cVal = cHeight;
  } else {
    cGrp = 2; cVal = 0;
  }

  const gap = num(f.gap_pct);
  const fHeight = num(f.height_pct);
  let fGrp: number;
  let fVal: number;
  if (gap !== null) {
    fGrp = 0; fVal = gap;
  } else if (fHeight !== null) {
    fGrp = 1; fVal = 0;
  } else {
    fGrp = 2; fVal = 0;
  }

  return [0, cGrp, cVal, fGrp, fVal, -(fHeight ?? 0), sym];
}

/** Sort comparator over {symbol, read} pairs. Same key, same order as the
 *  backend — both suites sort the shared fixture and must agree.
 *
 *  Returns 0 for two rows the key cannot tell apart, so `Array.prototype.sort`
 *  (stable since ES2019) leaves the SERVED order alone: an n/a tab, or a board
 *  the store has not warmed, keeps the order the board chose for it instead of
 *  being shuffled by a sort that knows nothing. */
export function compareBandStructure(
  a?: BandStructureSortRow | null,
  b?: BandStructureSortRow | null,
  status?: BandStructureStatus | string | null,
): number {
  const ka = bandStructureOrderKey(a?.read, a?.symbol ?? '', status);
  const kb = bandStructureOrderKey(b?.read, b?.symbol ?? '', status);
  for (let i = 0; i < 6; i += 1) {
    if (ka[i] !== kb[i]) return (ka[i] as number) - (kb[i] as number);
  }
  // Codepoint order, NOT localeCompare: the backend settles this leg by
  // comparing the two symbols inside a Python tuple, which is codepoint order.
  // `localeCompare` disagrees on '_' and on case ('aB' vs 'AB') — invisible on
  // real tickers (BRK.B, BF-B agree), and a divergence the moment one is not.
  if (ka[6] === kb[6]) return 0;
  return ka[6] < kb[6] ? -1 : 1;
}

/** True when not one row on the list has a usable read — the board is showing
 *  its served order and has to say so, exactly as the backend does with
 *  `BAND_STRUCTURE_SORT_UNAVAILABLE`. A sort over an all-null column returns
 *  the served order, which LOOKS like a working sort and is not one. */
export function bandStructureOrderUnavailable(
  rows: readonly BandStructureSortRow[],
): boolean {
  return !rows.some((r) => truthy(r?.read?.applicable));
}

/** enterable.KIND_NA, as served on `band_structure_kind`. */
export const BAND_STRUCTURE_KIND_NA = 'n/a';

/** LAST-RESORT mirror of `band_structure.NA_TEXT`, for the ONE case where the
 *  served sentence cannot arrive: an n/a tab that came back with ZERO tiles
 *  (0DTE outside the session). The sentence rides on the per-tile read, so a
 *  board with no tiles carries no sentence — and the page then rendered
 *  NEITHER the banner (correctly suppressed on an n/a tab) nor the n/a line.
 *  Silently absent is the failure this surface has been caught on twice, so
 *  the kind — which IS served, on `band_structure_kind` — decides the line and
 *  this string fills it.
 *
 *  The backend constant stays canonical: `bandStructure.test.ts` reads
 *  `backend/supply_demand/band_structure.py` and pins this equal to `NA_TEXT`
 *  character for character, so the two cannot drift. Prefer the served text
 *  wherever one arrives; this is the fallback, never the source. */
export const BAND_STRUCTURE_NA_TEXT =
  'no band read for this tab — its rows are not price-structure bands '
  + '(pivot / highs / lid / event / options / value)';

/** Mirrors `chart_maps/board._band_structure_sort`'s decision, and ONLY that
 *  decision — it does not carry the served note text, which is the server's to
 *  word (`BAND_STRUCTURE_SORT_NA` / `BAND_STRUCTURE_SORT_UNAVAILABLE`, rendered
 *  from `payload.sort_unavailable`).
 *
 *    'na'          the tab has NO band read — its rows are pivots, highs, lids,
 *                  events, options or value. DO NOT SORT: the control is inert
 *                  and the served order stands, exactly as the backend returns
 *                  before it reaches its own `tiles.sort`. A fake ordering over
 *                  rows that are not bands is the thing the 🎯 n/a precedent
 *                  exists to prevent.
 *    'unavailable' the tab HAS a band read but not one name on this list came
 *                  back with one. Sorting is harmless (the key puts them all in
 *                  the same group and settles them by symbol, which is what the
 *                  backend does too) but the board must say the order it is
 *                  showing is not the one that was asked for.
 *    null          a real ordering — sort.
 */
export function bandStructureSortNote(
  rows: readonly BandStructureSortRow[],
  kind?: string | null,
): 'na' | 'unavailable' | null {
  if (String(kind ?? '') === BAND_STRUCTURE_KIND_NA) return 'na';
  return bandStructureOrderUnavailable(rows) ? 'unavailable' : null;
}

/** The chip a surface prints, or null when there is nothing to say.
 *
 *    separates  → "🪜 0.82 · <the served stat>"
 *    otherwise  → "🪜 <the served stat>", MUTED — descriptive, never a grade
 *
 *  NULL, rendering nothing, when:
 *    • there is no read at all (cold store, legacy doc, a name with no bands);
 *    • the tab has no band read (`applicable === false`) — the board-level
 *      note says that once, and a chip repeating it on every row would be
 *      noise dressed as information;
 *    • the server sent no `stat` and no score — there is genuinely nothing to
 *      print, and this file will not assemble a sentence to fill the gap.
 *
 *  Every number in `text` came off the wire inside `read.stat`. */
export function bandStructureChipText(
  read?: BandStructureRead | null,
  study?: BandStructureStudy | null,
): { text: string; title: string; tone: 'band' | 'muted' } | null {
  if (!read || !truthy(read.applicable)) return null;
  const st = read.measured?.status ?? study?.status ?? 'pending';
  const separates = bandStructureSeparates(st);
  const stat = typeof read.stat === 'string' && read.stat.trim() ? read.stat.trim() : null;
  const score = num(read.score);

  let text: string;
  let tone: 'band' | 'muted';
  if (separates && score !== null) {
    text = `🪜 ${score.toFixed(2)}${stat ? ` · ${stat}` : ''}`;
    tone = 'band';
  } else if (stat) {
    text = `🪜 ${stat}`;
    tone = 'muted';
  } else {
    return null;
  }

  const bits: string[] = [];
  if (stat) bits.push(stat);
  if (study?.headline) bits.push(study.headline);
  if (study?.fallback_note) bits.push(study.fallback_note);
  bits.push(printBasisText(read.print?.source));
  return { text, title: bits.join(' — '), tone };
}

/** WHICH PRINT the served distances were measured on, said honestly.
 *
 *  The tooltip used to assert "read against the live print" unconditionally,
 *  and that is false whenever the snapshot is stale: `bounce_room.print_of`
 *  hands back `fresh=False` with the STORED CLOSE, and the tile path
 *  (`board._explosive_px`) falls back the same way. Outside RTH that made the
 *  🪜 tooltip claim a live number over a closed-bar one.
 *
 *  So: say which, when the server says which — and when it says nothing, name
 *  the RULE instead of picking a side. No value is invented here.
 *
 *  The caller passes the SERVED `read.print.source`. A payload that carries no
 *  print block, or a block whose `source` the caller could not fill, lands on
 *  the rule sentence — which is the honest answer and not a live claim. */
export function printBasisText(source?: string | null): string {
  const src = typeof source === 'string' ? source.trim().toLowerCase() : '';
  if (src === 'live') {
    return 'bands are closed-bar board geometry, read against the live print';
  }
  if (src) {
    return 'bands are closed-bar board geometry, and this is a closed-bar read '
      + '— the stored scan close, not a live print';
  }
  return 'bands are closed-bar board geometry, read against the board’s latest '
    + 'print — the live trade when the snapshot is fresh, the stored close when it is not';
}
