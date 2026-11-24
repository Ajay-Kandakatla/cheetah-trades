# 🩳 High SI sub on 🚩 Gajjala's 5-min tab (2026-11-23)

Spec: `highsi` revision 2, WP `be-sub` (ship shapes S1 and S2). DISPLAY on the GET. **UNMEASURED. Not advice.**
The 9/21 EMA cross push is a separate package (`docs/gajjala/high_si_cross_alerts_2026_11_23.md`) and was built OFF
(`HIGH_SI_CROSS_PUSH_MODE = "off"`). **2026-11-23: gate V0 run, the main session set it to `"live"`** (his question-card answer "Live to my phone").

## His words

Ajay 2026-11-23 (voice-typed), verbatim:

> "Can you create a tab similarly like Divergent with high charging tested, SHO tag, and low floats similar to what
> we've done in Divergent tab under Gazilla? And also add alerts for these talks when they are crossing EMA, 9 EMA over
> 21 EMA. I would like to see this. So this should be dedicated to all the high charging tests, but also when you add
> something to watch list, it's easily available to you. But maintain same Gajjala rules under 100 stock and all the
> other filters that you have. Look at Divergent, most of it should be available for you."
>
> "New tab like divergence*"

[voice typing: "high charging tested" = high short interest, "Gazilla" = Gajjala, "talks" = stocks]

His question-card answers, as recorded in the spec (§0.2 — the main session confirms them through gate V0):
#1 membership = his scanner's names with short interest High or EXTREME by the house tier AND float ≤ `K8_MAX_FLOAT`;
the 🔒 Reg SHO tag is a tag; unknown tier = not listed, counted. #2 a new sub on the 🚩 5-min page right after 🌱, same
cards, chips, ➕ Watch, house order. #3 a 9-over-21 EMA cross push on the 5-min and 15-min chart (WP `be-push`).

## What shipped (this package)

| Piece | Where |
|---|---|
| 14th sub `("high_si", "🩳", "High SI")` right after 🌱, GG5 only (`GG5_ONLY_SUBS` gains `HIGH_SI_SUB`) | `chart_maps/gajjala/constants.py` |
| `HIGH_SI_MAX_FLOAT = K8_MAX_FLOAT` and the push constants (`HIGH_SI_CROSS_*`, mode `"off"`) | `constants.py` |
| `high_si.py` — `classify` (the ONE membership function, also the push's), `evaluate`, the served words, `card`, `block` | `chart_maps/gajjala/high_si.py` (new) |
| `vol_float_slot` — the ONE (volume ↓, float ↑) sort slot; `order_key` calls it (byte-equal) | `chart_maps/gajjala/tab.py` |
| ONE `HS.evaluate` per GG5 build (strip count + block); the 🩳 branch after 🌱; `high_si` key on the 🩳 sub only | `tab.py` |
| ℹ️ 🚩 section note: the 🩳 High SI clause (built from the constants; ends with `high_si.push_text()`) | `supply_demand/rules_info.py` |
| Four dated `AMENDED 2026-11-23` comment / docstring lines; no code line, no served string moved | `short_interest/read.py` |
| One dated amendment line | `docs/gajjala/si_extreme_note_2026_11_18.md` |

No crontab line, no fetch, no write, no new collection, no rule / gate / threshold / lane change. One house
short-interest `$in` read (chunked at `MAP_MAX_SYMBOLS`) per GG5 board GET.

## The rule in words

A name on this tab's stored reads is listed when its short interest reads **High or EXTREME** on the house ladder
(`short_interest.read.si_tier` — the 🩳 chip's own word) AND its float is at or under `HIGH_SI_MAX_FLOAT` (10,000,000)
— on **both** float reads. Every not-listed name is counted by its first reason (`high_si.REASONS`):
`no_si` · `stale` · `no_tier` · `not_high` / `floats_disagree` · `float_unknown` · `float_over` · `float_unknown` /
`si_float_over` (record) · `floats_disagree` · listed.

### The two-float rule [C1]

The tier's denominator is the float stored WITH the short-interest record (frozen until the next settlement warm); the
card's Float chip and the K8 gate read the pass's float. `card_pct` = the same short interest on the card's float (2-dp,
the house rounding), judged by the ONE ladder function `SR.tier_of` — no number typed. A name lists only when High /
EXTREME on the record's float, at or over the High cut on the card's float, and both floats at or under the cap. The
probe's four 2026-11-23 disagreements (spec §1.6, the NEGATIVE tests use these share counts):

| Name | Word on the record's float | % of the record's float (shares) | % of the card's float (shares) | BUILT |
|---|---|---|---|---|
| GMEX | High | 62.87 % of 20,235 | 3.52 % of 361,428 | not listed (`floats_disagree`) |
| LABT | High | 18.04 % of 847,661 | 4.78 % of 3,201,536 | not listed (`floats_disagree`) |
| KITT | Low | 3.69 % of 5,527,831 | 12.64 % of 1,612,787 | not listed (`floats_disagree`) |
| SMX | Moderate | 6.03 % of 791,704 | 16.88 % of 282,748 | not listed (`floats_disagree`) |

A Low / Moderate name whose card float is OVER the cap is `not_high` (it would not list on the card's float either).

## The panel (served `high_si` block)

`title`, `ask_text`, `rule_label` / `rule_text`, `honesty` (the 🧨 Divergence figures read from `GC.DIVERGENCE_IS`:
after hours LOST MONEY, regular hours NOT SHOWN, OOS sealed until `DIVERGENCE_OOS_SEAL_ET`), `cohort_text` (carried names
and 📌 / 🎪 adds are on the list), `counts_text` (non-zero segments only; the numbers sum to `n_read − n`), `adds_text`,
`asof_text`, `sho_text` (reads `payload["complete"]`: an unread exchange list is named, "None of …" only when every list
was read), `push_text` (🔕 while the push is off), `order_note`, `shown_text`, `excluded_text`, `disagree_text`,
`no_tier_text`, `n`, `n_read`, `empty_text`, `chartless`, `faults`, `faults_text`.

Counts line shape: `102 listed names read · 13 listed here (4 of them High · float unconfirmed) · not listed: 23 High /
EXTREME with a card float over 10,000,000 · 4 where the two float reads disagree on High · 34 Low or Moderate · 27 with
no tier word (no usable float on the short-interest record; 13 of them with a card float at or under the cap) · 1 with no
short-interest record` (figures = the 11-23 probe, for shape only).

## The card

The 🌱 card recipe with the frame a parameter (`?tf=15m` draws the 15-minute frame): Change + Volume stats, the house
chips (🩳 / 🔒 / 🚫 / ➕ Watch drawn by the FE), the cross markers of the drawn frame (`tab.ema_cross_block`, the ONE
engine), no buy marker, no ENTRY line, no plan. Criteria rows: `si_tier` (the house tier sentence + the card-float %),
`float` (`high_si.floats_text` — both floats, labelled), `cross_5m`, `cross_15m` (ok True up / False down / None none;
`need` empty while the push is off), the K11 row (`high_si.volume_row` — an unknown volume is `ok: None`, "judged at the
ring", never ✗), and `🔔 rang today` only when a pushed `GGS:` claim of the kind exists today.

Order: today's volume ↓, then float ↑ (`tab.vol_float_slot`), then symbol; a carried name has no stored volume and goes
last; 🚫 names last after the cut (`broker_bottom`).

## Five-session frequency (spec §1.6 — frequency only, never an edge)

| Session | Members | Rings, one per cross (5-min + 15-min) | Rings, one per session | Pushes delivered that day |
|---|---|---|---|---|
| 11-17 | 18 | 31 | 14 | 93 |
| 11-18 | 16 | 59 | 20 | 58 |
| 11-19 | 17 | 40 | 20 | 89 |
| 11-20 | 15 | 29 | 12 | 86 |
| 11-23 | 13 | 27 | 13 | 70 |

## Goldens (regenerated by recipe, mode "off")

| Golden | Leaves | Added | Changed | Removed | Where |
|---|---|---|---|---|---|
| `backend/tests/fixtures/gajjala/gg5_board_2026_10_27.json` | 14935 → 15507 | 572 | 546 | 0 | 840 under `subs` (🩳 at subs/8, count None; the old subs/8.. shift), 278 = each mode's new `high_si` board |
| `frontend/…/gajjala_on_open_golden_2026_10_15.json` | 2291 → 2306 | 15 | 63 | 0 | `subs` only |
| `frontend/…/gajjala_potential_golden_2026_10_15.json` | 3904 → 3914 | 10 | 44 | 0 | `subs` only |
| `frontend/…/gajjala_track_record_golden_2026_10_16.json` | 2907 → 2922 | 15 | 60 | 0 | `subs` only |
| `backend/tests/fixtures/gajjala/gg5_writes_2026_10_27.json` | — | — | — | — | **byte-identical** (sha1 7d857dc9…) |

Dropping `subs` and `high_si`, every old and new golden is IDENTICAL (checked by script). The hermetic build has no Mongo
handle, so the 🩳 board in the golden is the fault shape (`high_si: null`, `empty_note = FAULT_TEXT`, chip count None) —
the mode flip therefore moves NO leaf of the BOARD golden.

## Tests

`backend/tests/test_gajjala_high_si_2026_11_23.py` (91): classify positives and one-flip NEGATIVES; the GMEX / LABT /
KITT / SMX shapes; exact cap on both floats; the High cut exactly and one hundredth under; moving `SI_ELEV_PCT` moves
both sides; K8 parity; `si_blocks` chunking (450 → 3 reads) and db None; `evaluate` order = `order_key`'s slot, counts
sum, carried / adds on listed rows only, faults, unread SI; every word moves with its constant; the mode (off / live /
junk → off); `volume_row`; `sho_text` complete / incomplete / raising; the board wiring (subs[8], high_si key only on
its sub, `?tf=15m`, the `lim` cut, 🚫 last, GG1 / GGA fail open, fault, chartless line, carried name last);
`rang_today`; the ℹ️ clause; `read.py`'s two served strings byte-identical; source guards. Mutation checks run (bytecode
purged): `<` on the cap, dropping `hi_card`, dropping the record-float cap, `volume_row(None)` → the detector row,
`sho_text` ignoring `complete` — each turns a test red.

Widened pins (`WIDENED 2026-11-23 — 🩳 High SI after 🌱`): `test_gajjala_constants.py`,
`test_gajjala_counts_legend_2026_10_18.py`, `test_gajjala_variant_gg5_identity.py`,
`test_gajjala_divergence_tab_2026_11_18.py`, `test_gajjala_divergence_2026_11_18.py`,
`test_gajjala_diverging_2026_11_18.py`, `test_gajjala_potential_tab.py`.

## HIS CALL (spec §7 — nothing decided for him)

0. The push at all (built OFF; gate V0). 1. Label / emoji (built `🩳 High SI`). 2. Chip position (after 🌱). 3. The
latch (built one per name, chart and cross — 27–59 rings a day measured; per session 12–20). 4. GG's 1M floor on the
push (built ON). 5. His first 15 minutes (candle-START mute). 6. Pre-market and after-hours rings (the 🧨 study LOST
MONEY after hours). 7. "High · float unconfirmed" names listed (built listed). 8. Order (volume, float, 🚫 last).
9. **Which float decides** (built: both must agree — table above); a floor on the absolute short position (none built).
10. A second ring from ➖ / 👀 on the same name. 11. No up-trend filter on the cross. 12. Watch names not on his
scanner list do not list. 13. A stale read drops the name. 14. No bearish cross push. 15. No 🏁 record / study.
16–18. /alerts strip placement, Notifications wording, not sticky (WP `fe-push`). 19. No-tier names (named in ⓘ, never
tiered on the card's float). 20. Carried names and 📌 / 🎪 adds list (tagged, counted). 21. The two served "display
only" strings in `short_interest/read.py` stay unchanged.

## 2026-11-23 (night) — the % goes into the card chip

Ajay, on three cards where a 49.2% High sat beside a 26.8% EXTREME: "Why is high more than extreme? can you actually put a
percentage directly here?"

- **Why:** EXTREME on the house ladder needs ≥ 20% of the float, ≥ 10% of shares outstanding **and a confirmed float**
  (`short_interest/read.py`, 2026-11-18). A name whose float is unconfirmed is held at High whatever its % — so a High can
  carry a bigger % than an EXTREME.
- **Change (words only):** `high_si.tier_chip(read)` builds the chip: `🩳 49.2% short interest · High (float unconfirmed)
  · float at or under 10,000,000`. The % is the short-interest record's own `pct_of_float` (what the tier is read on), else
  the card's float %; no number → no %. The chartless line carries the same words (never the ticker).
- No tier, listing, order, gate or push changes. Tests: `backend/tests/test_gajjala_high_si_pct_chip_2026_11_23.py`
  (incl. NEGATIVES: no number → no %, never "None"/"nan"; a confirmed float never says "unconfirmed").

## 2026-11-24 — an upcoming Reg SHO close-out date sorts first

Ajay: "Please sort the short interest tab based on that if this date is available put that ticker higher up" ("that
date" = the 🔒 tag's day-13 close-out date, `docs/gajjala/reg_sho_closeout_day_2026_11_24.md`).

- `high_si.closeout_order(rows, items)`: a STABLE sort in `block`. A row whose 🔒 item is `state "on"`, not stale, with run
  state in `CLOSEOUT_UPCOMING_STATES = ("counting", "reached")` and an ISO `day13` sits first, the nearest date first.
  Inside one date and among the undated the house order (volume → float) holds. `tab.broker_bottom` still runs after, so
  🚫 his names stay last even with a date. The cut at `limit` runs after the sort, so a dated name is never cut first.
- No lift: a passed date (`passed`, `passed_open`), `unknown`, a stale list, no tag, a junk date.
- The Reg SHO payload is read ONCE per build (`payload(kick=False)`), shared by `sho_text` and the order. A raising read →
  the house order and `order_note = ORDER_NOTE + ORDER_SHO_UNREAD` (said, never silent); a read with `complete` not True →
  `ORDER_SHO_PARTIAL` (names on an unread list were not moved). A `reached` date is the latest list's day 13, which can be
  yesterday — the note says "still counting or reached on the latest list", never "upcoming".
- Display order only: no listing, gate, push or rule change. Tests:
  `backend/tests/test_gajjala_high_si_closeout_sort_2026_11_24.py` (19, incl. NEGATIVES; 3 mutations go red).

## 2026-11-24 — 🎾 tag on 🩳 cards (GG's own setup, graded by his rules)

Ajay: "If the SI tab stocks have reversal squeeze action add the tag on the ticker to for the tennis ball actions Run them
against Gajjals other rules to show A+.. I wonder if we do this the other way around to move them to Reversal squeeze by
default but lets not do that".

- `high_si.squeeze_read(read_doc)` reads the name's STORED 🎾 read (`setups.reversal_squeeze`) — the same read the 🎾
  card shows, graded by every GG rule in the pass. Only a state that would carry a 🎾 card (`tab.TILE_STATES`: A+,
  triggered, forming, partial, stopped) tags the card. No new grading.
- Pill: `… · float at or under 10,000,000 · 🎾 Reversal Squeeze A+` (or forming / forming · ready / triggered / partial /
  stopped). Row `squeeze` (✓ A+ / triggered, — forming, ✗ partial / stopped) with `tab.state_label` words; a
  `triggered` read never claims A+ here — whether an alert rang is the 🎾 card's to say (formulas audit D10).
- Not done, by his word: no name moves into 🎾 by default. The 🩳 order and membership and the 🎾 sub are unchanged.
- Tests: `backend/tests/test_gajjala_high_si_squeeze_tag_2026_11_24.py` (15, incl. NEGATIVES; 3 mutations go red).
