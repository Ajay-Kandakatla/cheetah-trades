# 💋 EMA Kiss & Fly — relative volume first, closest to the 9 EMA next, and the "lifting off the 9 EMA" toggle (2026-11-11)

**Display only.** No gate, rule, threshold, push, count, lane or 🏁 change. The new order is **UNMEASURED**, and the one
measured prior on volume inside the list is null-to-negative (below).

## His words

Ajay 2026-11-11 ~12:50 ET, verbatim: *"I think we should do these two things. Sort by relative volume, and closer to the
EMA. and bouncing. This filter is needed for EMA Kiss atleast"*

The ✨ entry and every served word quote only his two whole sentences, *"Sort by relative volume, and closer to the
EMA."* and *"This filter is needed for EMA Kiss atleast"*. The fragment with the b-word is never printed on a surface he
reads. It maps to "lifting off the 9 EMA" (the toggle) and to the existing state ranks (§2).

## 1. What shipped

| Piece | What it does | Where |
|---|---|---|
| Relative volume | This pass's session volume ÷ the average of the last `MB.VOL_AVG_BARS` (50) closed sessions, through the house sort engine `drop10_tab.rvol_read`. During market hours it is projected to a full session (from `MB.BURST_PROJECTION_MIN_FRAC` of the session). It is the whole-session ratio after hours, and **none** pre-market. | `context.warm_squeeze_history` stores `avg_vol_50` (from `MB.avg_volume_before`, on the 🎾 chip's own daily frame, no new read). `run.run_pass` sets `ctx["rvol"]` from `sv[s]`, the volume THIS pass read, never the stored scan row. |
| 💋 order | Inside each state: relative volume ↓, then the 9 EMA distance ↑, then the 📊 volume ↓, float ↑, then today's key. | `tab._kf_slot` (the 💋 sub only, `GC.RVOL_SORT_SETUPS`). Precedence is set by `GC.KF_EMA_SORT = "rvol_first"`. |
| 9 EMA distance | The K5 row's own printed number: how far the last closed bar's low sits from the 9 EMA, absolute. "low at the 9 EMA" counts as 0. | `tab._kiss_gap_pct` parses `detectors._kiss_text`. No new detector field, so the WRITES golden stays byte-identical. |
| Card stat | "Rel volume" in `drop10_tab.rvol_text` words, right after Volume, shown only when known. | `tab.setup_tile(kf_rank=True)`, set at the setup-sub call only. 🧠 cards, the banner and the focus resolve get none. |
| `order_note` | `KF_ORDER_TEXT["rvol_first"]`: "💋 A+ and triggered, then kissing the 9 EMA now, on top · then highest relative volume · then closest to the 9 EMA". | `tab.build` |
| `list_note` | Printed on a MIXED board only (some cards have a relative volume and some do not): "💋 U of N have no relative volume yet (fewer than 50 trading days, or not read yet) — they sit last in their state". | `tab.kf_list_note`, counted over the sub's cards before the cut |
| Toggle (addendum) | "💋 lifting off the 9 EMA only", a chip on the 💋 sub, default **OFF**, remembered per viewer (localStorage `gg-kiss-filter`; a blocked store reads OFF). When ON it hides only the cards served `kiss_now: false` and prints "N shown · M hidden (not at the 9 EMA now) · K unknown kept". It never reorders, never changes a count, and 🚫 names keep their bottom place. | Served: per 💋 card `kiss_now` (`tab.kiss_now_of`) and the sub's `kiss_filter` {label, hint, hidden_text_template} (`tab.kiss_filter_block`). The FE (`GajjalaBoard.tsx`, `lib/gajjala.ts`) types none of the words. |

`kiss_now`, from the EXISTING state reads only (no new rule, no new number):
- **true**: A+ / triggered ("flew"), or forming-ready (kissing the 9 EMA on the latest closed bar per the K5 read:
  the low within `GC.K5_KISS_TOL_PCT` of the 9 EMA or the bar spans it, and the close above it).
- **false**: partial / stopped, or a forming read whose K5 row says it is not kissing.
- **null** (unknown, never hidden): a forming read whose K5 row is missing or not judged, or is judged as kissing while
  another row is still unjudged; the 🧪 held state; anything else.

The toggle is served on the 💋 sub of all three pages (🚩 GG5, 1-minute, 🧪 Audited), because they share `tab.build`.

## 2. The key table (the 💋 sub)

| Rank | Key | Unknown |
|---|---|---|
| 1 | State: A+ 0 › 🧪 held 0.5 › triggered 1 › forming-ready (kissing now) 2 › forming 3 › partial 4 › stopped 5 (unchanged) | — |
| 2 | Relative volume ↓ | `inf`: last in its state, never 0 |
| 3 | 9 EMA distance ↑ (the K5 row's number) | `inf`: last at that key |
| 4 | Volume ↓, float ↑ (the 📊 slot, unchanged) | last |
| 5 | Today's key (newest A+, nearest trigger, …) | — |

Placement is `GC.RS_FLOAT_SORT = "within_state"` (a test pins it beside `KF_ORDER_TEXT`). Then come the limit cut
(`GC.TILE_LIMIT_DEFAULT`), `broker_bottom` (🚫 last) and 🔝 Focus 5, all unchanged. Every other sub (🚩 ➖ 🌀 🎾, 🧠,
☀️, 🌙) keeps its exact key. `potential.order_key` is untouched.

"Bouncing" maps to the existing ranks: flew (A+ / triggered) then kissing now (forming-ready) already sat on top. **In
practice only relative volume changes the order.**

## 3. Unknown and pre-market

- **Pre-market**: no relative volume (the engine's "premarket" code: a part day is never set against full days). An
  all-unknown board sorts by the 9 EMA distance, then volume. `order_note` still names relative volume. `list_note` stays
  silent (it prints on a mixed board only).
- **Fewer than 50 closed sessions** (new listings): no average, so no relative volume. They sit last in their state and
  can fall past the 24-card cut (Q5).
- **Not read yet**: the in-pass cap `GC.DAILY_MAX_NEW_PER_PASS` new daily reads (alphabetical). On deploy day, daily docs
  already cached are never re-read, so those names show no relative volume until the nightly warm fills the next
  session.

## 4. The measured prior

The 2026-11-11 entries study (`eod-audits/research/2026-11-11_entries_followthrough.md`) found that inside the list
**the loudest three names won slightly LESS often**:

| Page | Volume top-3 so far | The rest | Δ win [95%] | Δ R [95%] |
|---|---|---|---|---|
| 5-minute 🧠 rings (742) | 46% · −0.58 R (n 239) | 50% · −0.48 R (n 500) | −4 pp [−13, +5] | −0.10 [−1.24, +0.67] |
| 1-minute 🧠 rings (330) | 40% | 51% | −12 pp [−27, 0] | — |

The study did NOT propose ranking by volume inside the list. **Relative volume itself was never measured.** GG's sourced
rules hold no relative-volume rule; his floor is absolute (`GC.SCAN_MIN_VOLUME`). This order is **UNMEASURED**.

## 5. Traps

- **Two reads on one card**: "Volume" is the stored last-qualified row (+25% pass), while "Rel volume" uses this pass's
  volume. A pulled-back name can show a lower Volume next to a relative volume built on a higher one (Q12).
- **Pre-market shares are in the projection**: `min.av` includes pre-market, so the printed number reads high early in
  RTH for gappers. Every card in a pass shares one session fraction, so the ORDER is unaffected. Whether Massive's daily
  bars include extended hours is unverified.
- **Partial yesterday in the average**: the loader accepts a cached frame whose last bar was saved mid-session, so a
  day-2 spike name can read too high. The 🎾 squeeze-history chip shares this read today (Q13).
- **A wording change to `_kiss_text`** would make every distance unknown. A round-trip test guards it.

## 6. Goldens

- `backend/tests/fixtures/gajjala/gg5_board_2026_10_27.json` (BOARD): 8 leaves, all on the 💋 sub, both modes, verified
  key for key:
  - `kiss_fly/order_note`: `VOL_ORDER_TEXT` → `KF_ORDER_TEXT["rvol_first"]` (2 changed).
  - `kiss_fly/kiss_filter` added (2).
  - `kiss_now: false` added on each of the two 💋 tiles (4).
  - No tile reordered, no stat added, `list_note` still null.

  Dated in `tests/test_gajjala_variant_gg5_identity.py`.
- The WRITES golden is **byte-identical** (the fixture loader has no average, so no ctx `rvol`).
- The frontend goldens did not move.

Recipe: `GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_variant_gg5_identity.py -k test_gg5_board_is_byte_identical`.

## 7. Tests

- Backend: `tests/test_gajjala_rvol_avg_2026_11_11.py` (data) and `tests/test_gajjala_kiss_rvol_sort_2026_11_11.py`
  (order, stat, words, `kiss_now`, the block). Re-pinned `order_note` lines: `test_gajjala_tab.py`,
  `test_gajjala_fade_ema_rank_2026_11_08.py`, plus the banned-word loop in `test_gajjala_volume_sort_2026_11_09.py`.
- Frontend: `GajjalaBoard.kiss_rvol.test.tsx`.
- Contracts: "💋 EMA Kiss rel volume order + lifting-off toggle (2026-11-11)".

## 8. HIS CALL (short questions)

1. **The filter.** Built: the "💋 lifting off the 9 EMA only" toggle, default OFF. When ON it hides the cards not
   kissing the 9 EMA now; A+ / triggered stay, and so do unknown cards. Should it default ON? Should the unknown cards
   be hidden too?
2. **"Bouncing"** = flew (A+ / triggered), then kissed the 9 EMA on the last bar (touched within `GC.K5_KISS_TOL_PCT` and
   closed above). Those cards were already on top, so the word changed nothing. Or must it also turn up (a green bar or
   a higher close after the touch)? That would be a new rule.
3. **"Relative volume"** = today's volume so far (pre-market included) ÷ the average of the last 50 full days, projected
   to a full day in market hours (the same number as the 🔻 Down 10% tab)? Or the latest 5-min bar ÷ its 50-bar average,
   or volume ÷ float?
4. **Pre-market** shows no relative volume, so pre-market 💋 cards sort by closest to the 9 EMA, then volume. OK, or use
   the raw so-far ratio pre-market?
5. **Under 50 trading days** means no relative volume: the card sits last in its state and can fall past the 24-card cut.
   The probe that counts how often the 💋 board passes 24 cards was **not run** (market hours), so its number is still
   owed. Should the average use fewer days for new listings? If so, how many?
6. **Precedence**: highest relative volume first, then closest to the 9 EMA (your word order, built)? Or closest to the
   9 EMA first (`"ema_first"`)?
7. **"Closer to the EMA"** = the bar's low vs the 9 EMA (the K5 row's number; a low that dipped under counts by how far
   under)? Or the current price vs the 9 EMA?
8. **Scope**: 💋 only (built), or relative volume first on 🚩 ➖ 🌀 🎾 too?
9. **The card figure**: keep "Rel volume 2.35× projected to a full session (40% done)" (a third stat on the phone card)
   and the "N have no relative volume yet" line?
10. **🧠 Potential** stays volume first. Change it too? It also orders the 🧠 pass's tracking.
11. **Measured**: on 11-11 the loudest three names inside the list won slightly LESS often (5-min 46% vs 50%, Δ −4
    [−13, +5]; 1-min 40% vs 51%). Relative volume was never measured. Keep this order labelled UNMEASURED, or measure
    first?
12. **The card's Volume number** (and the 📊 volume order on every sub) comes from the last pass the name was up 25%+,
    not this pass. Switch it to this pass's number? That would reorder every sub.
13. **Fresh daily fetch**: the 50-day average can include yesterday's bar saved mid-session, so a name that spiked
    yesterday reads too high. Always fetch fresh? That means more data calls, and it also changes the 🎾 squeeze-history
    chip's read.

Two MINE calls you may overrule. (a) `kiss_now` is null (kept) for the 🧪 held state and for a forming read whose K5 row
is not judged. (b) The toggle shows on the 💋 sub of the 1-minute and 🧪 pages too.
