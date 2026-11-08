# 🧪 / 1-min entry zone — 2026-11-08

**The ask (Ajay, 2026-11-07, verbatim):** "On the Gajjalas Audited and Gajjalas 1 min tab can you add entry signal on the
chart please like a small zone. Based on what he said, Like when its imminent with volume drying and selling pressure is
low. and Also when the pullback is ideal and close EMAs I guess based on what he says."

**What ships:** one served band on a FORMING setup card of the 1-minute page (GG1) and the 🧪 Audited tab (GGA). The 🚩
5-minute tab (GG5) serves none, so its cards keep `bands: []` byte for byte. It is display only. Nothing here gates,
filters, pushes or trades. **UNMEASURED.** The 2026-10-14 study of the five setups read NULL
(`docs/gajjala/study_2026_10_13.md`).

## Engine

`backend/chart_maps/gajjala/entry_zone.py` is called once from `tab.setup_tile` on the **stored** read. The stored read
carries `base`; the served `gajjala` block does not.

| key | value |
|---|---|
| `kind` | `gg_entry` (`ZONE_KIND`, the same key as the FE `BAND_FILL` / `BAND_NAME` entry and the `CmBand` union member) |
| `lo` / `hi` | the read's `stop` / `trigger` (the house band across the chart; no new level) |
| `label` | `V.word("zone_label", v)` = **"entry zone"**, the short word the chart `<title>` and crosshair readout print [C1] |
| `note` | `V.word("zone_note", v, why=…)` = "{why} · UNMEASURED", the sentence the card line prints [C1] |

The words live in `variant.WORDS_1M` and `variant.WORDS_GGA` only. `variant.word` returns None for GG5, so GG5 gets no band.

## When — his words → the existing reads (no new rule, no new number)

| reason | the read | GG's words |
|---|---|---|
| **imminent** | `ready` True (every criterion met, K3 volume dry among them) AND `context.red_closes_chip(red_closes)` is None (≤ `RED_CLOSES_WAIT` red closes in a row) | GG S11 "The volume will dry up during the entries of all my setups"; GG X 1733882105204011109 "more than 3 red closes is red flag to me" |
| **ideal pullback** 💋 | `k3_vol` ✓ AND `k5a_honor` ✓ (honours the 9 EMA) | GG KF1 |
| **ideal pullback** 🌀 | `k3_vol` ✓ AND `k7_ema21` ✓ (holds the 21 EMA) | GG VCP1 |
| **ideal pullback** ➖ | `k3_vol` ✓ AND `k6_merge` ✓ (9 and 21 EMA within `K6_MERGE_PCT`) | GG S8 32:49 |

- 🚩 Bull Flag and 🎾 Reversal Squeeze have no EMA criterion, so they get the imminent zone only.
- Guards: the state must be `forming`. The base must span at least one bar, because K3's volume check is vacuously True
  over an EMPTY pullback (`detectors.k3_vol_ok`; same precedent as `POTENTIAL_NEEDS_BASE`). The plan must be `ok` under
  the one plan rule (`ledger.plan_of`), so trigger > stop.
- [C4] The red-closes clause appears in the sentence only while `RED_CLOSES_MODE` is not `"off"`.
- [C5] With `KF_HONOR_ALL_PULLBACK_CLOSES` False, the 💋 read has no `k5a_honor` row, so there is no EMA leg and no crash.
- Off a forming read there is no zone: partial, A+, held, triggered, stopped, invalid and none. The ☀️ / 🌙 rows get
  none either.
- 🧠 Potential cards on GG1 / GGA carry the band, because they are `setup_tile` cards of their primary setup.

Note examples:
- "imminent — trigger armed, volume dry, no more than 3 red closes in a row · UNMEASURED"
- "ideal pullback — low volume, honours the 9 EMA · UNMEASURED"
- with both reasons, imminent comes first, joined by " · "

## Golden delta (proved path by path, 2026-11-08)

- `frontend/src/components/__fixtures__/gajjala_1m_board_2026_10_27.json`: exactly two paths changed,
  `boards/bull_flag/tiles[GGB].bands` and `boards/potential/tiles[GGB].bands`. Each gained ONE band: `gg_entry`,
  lo 10.8125 = stop, hi 10.9375 = trigger, label "entry zone". GGB has `red_closes` 3 = `RED_CLOSES_WAIT`, the [C8]
  boundary. The GGA cards have no band: GGA's bull_flag is A+, and its potential card is a horizontal_fade that is not
  ready with `k3_vol` and `k6_merge` False.
- `backend/tests/fixtures/gajjala/gg5_board_2026_10_27.json`: no band anywhere. Every tile still has `bands: []`.
- `gg5_writes_2026_10_27.json`: byte-identical.

## HIS CALLs (built as stated, never decided here)

1. IMMINENT = ready AND no red-closes flag. The alternatives are ready alone, or K3 + K6 decay without ready.
2. The red-closes count as a zone ingredient keeps `RED_CLOSES_MODE = "chip"`.
3. IDEAL PULLBACK = K3 + the setup's own EMA rule. A 9 EMA read for 🚩 would be a NEW rule and is not built.
4. Geometry = stop→trigger across the chart. Bounding it to the base bars would need a PatternChart change; trigger→+1R
   would invent a level and is refused.
5. FORMING reads only. Partial reads with the missed rule named are the alternative.
11. The card line restates the ✓ rows. It is kept because phones have no hover.

## NOT built

No zone on partial / A+ / triggered / stopped reads. No 9 EMA exit word or trail grade (his 2026-11-06 "keep it"). No
measurement. No new criterion, gate or push.
