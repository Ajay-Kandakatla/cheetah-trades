# 🩳 Short interest column on the 📋 All strategies table (2026-11-16)

## The ask, verbatim
Ajay 2026-11-16 (screenshot of the 📋 All strategies table on 🚩 Gajjala's tab): "Add a short interest colume fo this
table when available".

## What changed
- `backend/chart_maps/gajjala/all_table.py`: `HEADS` gains `("si", "Short interest")` LAST, right after Float (the dated
  comment sits above `HEADS`; `TITLE` stays the line directly below — the contracts HEADS regex needs it). New served
  words `SI_KEYS`, `SI_HEAD_TITLE`, `SI_FAULT_TEXT`; new pure `si_cell(blk)` and `attach_si(rows, si_by)`. `row_of` serves
  the four si keys as None by default (shape stable without a read). `block(..., si_read=None)` calls the injected reader
  ONCE, after the cut and both ranks, with the kept rows' distinct upper-cased symbols. The module imports nothing from
  `short_interest` — the seam is the injected reader.
- `backend/chart_maps/gajjala/tab.py` (the `elif table_sub:` branch only): `_si_read(syms)` returns None when
  `short_interest.client._get_db()` is None, else `short_interest.read.si_map(syms, db=db, today=_et(now).date())`.
  Lazy import, like `all_table`. GG5 + the 1-minute page (`table_on`); 🧪 Audited has no table and never reads.

## Payload keys
- Row: `si_text` (the house 🩳 chip verbatim, `read.chip_text`), `si_title` (the chip's hover, `read.title_text` — opens
  with "🩳 Short interest — FINRA settlement {date} (published ~{date})."), `si_stale` (bool), `si_asof` (settlement date).
- Block: `si_head_title` (= `SI_HEAD_TITLE`, the head hover), `si_fault_text` (= `SI_FAULT_TEXT` when no short-interest
  store was reachable this build, else null). `heads` gains `{"key": "si", "label": "Short interest"}` LAST.
- `rank`, `near_rank`, `tier`, `in_watch`, `sorts`, `watch` are byte-identical with or without short-interest docs.

## The blank rule
No FINRA record on file (absent from `si_map`), a remembered miss (`settlement_date: None` → `_no_record_block`, chip
None), or no block → all four keys None → the cell prints NOTHING. Never 0, never a dash, never "not read" on the row.
The head hover explains the blank.

## The three chip bases (inside `read.chip_text`, never re-derived here)
1. `% float` when a float is on file and not suspect — e.g. "🩳 SI 30.0% float · 2.3d · 9/30".
2. `% shs out` when the float is missing or suspect (`read._float_suspect`: `FLOAT_EXCEEDS_SHARES`,
   `SHORT_EXCEEDS_FLOAT` under `SUSPECT_MAX_SHARES_OUT_FRACTION`) — e.g. "🩳 SI 24.0% shs out · 2.3d · 9/30".
3. The raw shares-short count when neither denominator is on file — e.g. "🩳 SI 1.2M sh · 2.3d · 9/30".
Then "· {dtc}d" only when days to cover > 0, "· m/d", and "· stale" when stale.

## The stale rule
`read.freshness` (FINRA calendar: `FINRA_PUBLICATION_BDAYS`, `SI_INGEST_GRACE_BDAYS`): stale when a newer settlement was
due and this app still holds the older one. `today` = the ET date of the BUILD clock through `tab._et` (naive → UTC
first). The `/short-interest/map` GET uses `read._today` → `date.today()` (container-local); the two can differ by one
calendar day between ~19:00/20:00 ET and local midnight. A label, not a gate.

## The fault rule
`si_read` returns None = no short-interest handle this build (Mongo unreachable) → `si_fault_text = SI_FAULT_TEXT`,
every row kept, every si key None. A dict (possibly `{}`) = the read worked; an absent name has no record — NOT a fault.
A raising reader is treated as None (belt-and-braces; the real `si_map` never raises — it returns `{}` on a blip, which is
why the handle is checked first). Mongo down costs one 2 s server-selection timeout per table build; `_soft` keeps the
board up either way.

## Guards
- U10 (`verified_rules.json`): "Short interest: no threshold and no short-interest filter in ANY source." DISPLAY ONLY —
  `near_order` / `tier_of` never read an si key; no other gajjala module, `trading/gajjala_*.py` or `push/hooks.py`
  names it (S10 source guard).
- The column inherits the chip's float snapshot (SI-warm time) — "% of float" can disagree with the Float column on the
  same row (the POM class). Not changed here; that HIS CALL stays open.
- `si_map` caps at `MAP_MAX_SYMBOLS` (200); the table caps at `TILE_LIMIT_MAX` (80) — never reached.

## Goldens
- `backend/tests/fixtures/gajjala/gg5_board_2026_10_27.json` regenerated (`GG_WRITE_GOLDEN=1 … -k board`, through pytest
  only). Key-for-key diff: 56 leaves ADDED, 0 changed, 0 removed, every one under `<mode>/all_strategies/table`: the head
  (key + label, 2), the four si keys null on all 6 rows (24), `si_head_title` + `si_fault_text` (2) — per mode. (The spec
  counted the head as one entry → "54"; at leaf level it is 56.)
- WHY the golden carries the fault sentence: the hermetic suite refuses MongoClient (tests/conftest.py), so the build has
  no handle. GGB is a real ticker with a live FINRA doc on the local store — a regen outside pytest would write its
  wall-clock-dependent chip. The NEGATIVE in `test_gg5_board_is_byte_identical` and S15 fail before that can land.
- WRITES golden (`gg5_writes_2026_10_27.json`) byte-identical (sha1 6093b1ab…, before = after) — the table is build-only.
- The 1-minute FE golden does not move (it builds no table); the three FE GG5 goldens carry `subs` only.

## Tests
`backend/tests/test_gajjala_all_table_si_2026_11_16.py` — S1–S15, 28 tests. NEGATIVES: S3 no record / remembered miss,
S6 no read on other subs / 🧪, S6b the clock (naive / aware / after ET midnight), S7 raising read, S7b no handle (0
reads), S7c reachable-but-empty (not a fault), S9 🧪, S10 source guard, S14 lower-case map key never matched, S15 golden
guard. Mutation-checked (bytecode purged): the fault never set (3 red), the attach join not upper-cased (2 red),
`si_stale` hard-coded (2 red). Plus the NEGATIVE block inside `test_gg5_board_is_byte_identical`.

## UNMEASURED
A data label. Short interest on this app's universe is unmeasured and documented as "not a forecast"
(`short_interest/read.py`). No rank, tier, gate or alert reads it.

## HIS CALLs (from the spec §7)
1. "make some videos of the trends from today watchlist and other stocks" — a different ask, not built here.
2. Blank + no hover for "no record" (built) vs a "not read — no FINRA record at the last warm" hover.
3. Join the live `shares_cache` float into "% of float" (the open 11-08 call) — not done.
4. ✨ position: fold into the existing 📋 ✨ (recommended) vs a new FIRST ✨.
5. Stale tone: muted + the word "stale" (built) vs amber.
6. 🧪 Audited keeps no table; GG5 + 1-minute only — confirm no third page.
7. Served-row column (built) vs a FE-side join through `useShortInterest`.
8. The fault sentence under the table when no store is reachable (built) vs a silent blank column.

## 2026-11-18 (later) — the tier word arrives through `si_text`

Ajay: "Yes please and may be add better terminilogy like Moderate with a percentage relative to float."
The 🩳 column's `si_text` is still the house chip verbatim, so it now carries the served tier word
(`🩳 SI EXTREME 30.0% float · 2.3d · 9/30`, `🩳 SI High 36.4% float · float unconfirmed · …`). **No new served
key:** `SI_KEYS` is still `("si_text", "si_title", "si_stale", "si_asof")` (a NEGATIVE pins it), so the gg5 BOARD
and WRITES goldens do not move. No colour, no sort, no gate. On the phone the `td.gg-all-si` nowrap widens the
column and the table scrolls. Rule and HIS CALLs: `docs/gajjala/si_extreme_note_2026_11_18.md`.
