# ➖ Horizontal Fade — 9 / 21 EMA rank on all three tabs — 2026-11-08

**The ask (Ajay, 2026-11-08, verbatim):** "On the horizonal fade I need a ranking in horizontal fade when the stock 9 EMA
and 21 EMA are converging or close to converge on all tabs"

**What ships:** on the ➖ sub of 🚩 Gajjala's (GG5), the 1-minute page (GG1) and 🧪 Audited (GGA), the cards are ordered
with the 9 and 21 EMA **closest to merged on top**. The sub serves `order_note` = `tab.HF_ORDER_TEXT` =
"➖ 9 and 21 EMA closest to merged on top", which the FE prints verbatim. It is order only. No card is added or hidden,
and nothing gates, pushes or trades. **UNMEASURED.**

## The number

`tab._ema_gap_pct(read)` parses the k6_merge criterion's served value exactly as `detectors._fade_checks` prints it:
`f"EMAs {gap/close*100:.2f}% apart"`, where gap = |EMA9 − EMA21| at the read's ref bar. "EMAs —% apart" (an EMA still
warming) or a missing row gives None, which sorts last. `setup_tile` stashes it as `gajjala._ema_gap_pct` on ➖ cards
only, and `_strip_private` pops it before serving. A round-trip test pins the parse
(`FX.hf_frame(gap_frac=0.0051)` → 0.51), so a reworded value fails loudly instead of degrading quietly.

**[C3] A snapshot, not a direction.** The number is how far apart the EMAs are *now*. A pair that just crossed and is
moving apart at 0.40 % ranks above a pair closing in from 0.70 %. So every served word says "closest to merged", never
"converging". A direction key (|9 − 21| shrinking bar over bar) would be a new read field, which moves the gg5_writes
golden. That is **HIS CALL #16**, not built.

## [C2] Which reads he is asking about

- `detectors.py:650-660`: a base shorter than `K4_HF_BASE_MIN` marks every criterion pending, so the read stays
  `forming` (not ready, "base n of 6 bars") whatever the EMA gap.
- `detectors.py:313-320` (`_resolve_forming`): a FULL-length base whose `k6_merge` is False is a hard miss, so the read
  is `partial` (`missed` includes `k6_merge`).
- So the "close to converge" names are mostly **partial**. Under today's key they rank 4, below every young forming base.
  The criteria (with the k6_merge value) are served on partial reads too, because `_set_criteria` runs first.

## The three orders (`constants.HF_EMA_SORT`, MINE; `HF_EMA_SORTS`)

| value | order |
|---|---|
| **`pre_break`** (built) | A+ 0 · held 0.5 · triggered 1 in today's order → [forming + partial together at `_PRE_BREAK_RANK` (= today's forming-ready rank 2) by the gap ascending, unknown last; equal gaps → ready-forming, forming, partial, then each state's own tail] → stopped 5 · else 9. [C6] Rung and stopped cards keep today's key byte-identical. |
| `within_state` | the 🎾 twin: the gap right after each state rank. A partial fade is always below a forming one, and A+ / triggered re-sort by a pre-break gap. |
| `global` | the gap above every state. An A+ fade at 3.0 % drops below a forming one at 0.1 %. |

Worked example (pinned under all three values): A = forming (pending) gap 2.61 · B = partial `missed == ["k6_merge"]`
gap 0.60 · C = A+ gap 3.0.

| `HF_EMA_SORT` | order |
|---|---|
| pre_break | **C, B, A** |
| within_state | C, A, B |
| global | B, A, C |

What stays as it is: the other four setup subs; the 🧠 Potential sub (ordered by `potential.order_key`); the cross-setup
focus pick (it builds its key without the stash); and `HF_EMA_SORT`, which stays out of `CHEETAH_DEFAULTS` (the
`RS_FLOAT_SORT` precedent).

## Golden delta (proved path by path, 2026-11-08)

`backend/tests/fixtures/gajjala/gg5_board_2026_10_27.json`, in both `live` and `shadow`:

- `horizontal_fade/tiles` order went from GGA ("EMAs 2.61% apart") then GGB ("EMAs 1.88% apart") to **GGB then GGA**.
  Each symbol's tile body is unchanged; both reads are forming, so the delta is the same under all three values.
- `horizontal_fade/order_note` went from null to HF_ORDER_TEXT.
- Every other sub and every other key is byte-identical. `gg5_writes_2026_10_27.json` is byte-identical.
- The 1-minute golden carries no ➖ sub, so the rank does not touch it.

## HIS CALLs

6. `HF_EMA_SORT = "pre_break"` is MINE. The alternatives are `within_state` and `global`; one word in constants.py
   flips it.
7. The served `order_note` word. Strike it for an order-only delta.
8. The gap = the k6_merge printed value (2 dp), parsed. A numeric key on the read is the alternative; it would move
   gg5_writes.
16. "Converging" as a direction would need a new read field. Not built.

## NOT built

No direction or slope key. No new chip (the k6_merge criteria line already prints "EMAs X.XX% apart" on every ➖ card).
No FE sort control: the server orders.
