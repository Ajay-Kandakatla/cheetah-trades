# GG example charts: are his setups calmer? (read 2026-11-26)

Sources: F4VS's write-ups of GG's masterclass (third party; the valid/invalid labels come from that page's section headings), GG's own X posts, and GG's own Reversal Squeeze video (setup5, 13:47 long, no price axis in any frame).
Folder: /Users/ajay/clinet-test/eod-audits/research/2026-11-26_gg_charts/ (images/, frames_rs/, manifest.json, manifest.md)
Everything below describes only what is visible on the charts. "approx" means read between gridlines. "n/r" means not readable. No rule was changed.

---

## 1. Headline

- **Yes, his VALID examples are visibly calmer.** Graded by eye: calm on 31 of 55 valid setups, medium on 24, and choppy on 0. The 11 INVALID setups grade 0 calm and 11 choppy. The two X-post losers (INTS, ABVC) and SNES, which lost -13.5% on its own fill labels, are all choppy too.
- **What separates them:**
  - **Base length:** no valid base is 1 bar (minimum 2 bars on bull flags, 3–4 on kiss & fly, about 6 on VCP, about 9 on horizontal fade, about 4–6 quiet bars on the reversal squeeze).
  - **Bar size and position:** base bars are clearly narrower than the run bars and sit in the upper part of the run.
  - **EMA hold:** the base sits on or above the 9 EMA (flags, kiss & fly) or the 21 EMA (VCP, fade, reversal squeeze). Every invalid chart instead shows lower highs, wide two-way wicks, or price cutting under tangled EMAs.
  - **Entry location:** 30 of 44 readable valid entries are within about 4% of the day's high so far, and **0 of 44 are 20% or more under it**.
- **Volume dry-up does NOT separate them.** It is present on most valid bases but also on 7 invalid or loser charts (RKDA, NVCT, BWV-fade, BE, LQR, AYLA, INTS).

---

## 2. Reversal squeeze: his charts vs our 🎾 detector

Our detector (verified tonight):
- drop of 8% or more that closes back within 2% inside 3 bars;
- quiet base of 1 bar (RS_BASE_MIN_BARS 1), with base volume at most 0.50× the run back up;
- trigger = top of the run back up after the first pause, with a median of -20.3% under the day's high (only 5 of 31 within 2%).

The 8 / 2 / 3 / 1 numbers are Ajay's, not GG's.

**Tennis-ball size (readable charts only)**
- TPST (rs_03): one wick drops approx 20% (approx 1.02 down to approx 0.80) and is taken back in the same or next bar. The chart's note reads "quick dump and reclaim".
- BACK (rs_10/11): a 2-bar drop of approx 16% (to approx 2.68), then 2 bars back above the 3.65 run high, wicking to approx 4.1.
- YELL (rs_04/05): one long lower wick under the 21 EMA. The price axis is cropped, so the size is n/r.
- POL (rs_08) and FFIE (X study) do not snap back. They flush approx 28–35% at the open and take approx 15–20 bars to rebuild.
- In the video, the size is n/r on every one of the 18 charts. The quick (1–3 bar) returns are TPST, YELL, BACK, VVOS and "TOP". The gradual returns (4–12 bars) are VERB, OMH, NBSE, POL and UCAR #1, and he still calls those valid.
- **No readable valid example has a tennis ball as small as 8–15%.** The readable quick ones are 16–20%. Our 8% is looser than anything visible, and 8% is also the size of the normal swings inside the invalid SASI chop (approx -12%, repeatedly).

**Quiet bars before the trigger**
- In the images, the full pauses run approx 14–60 bars: TPST approx 60 flat bars, YELL approx 52, VERB approx 60, HUDI approx 45, POL approx 18 after the flush, BACK approx 28 + 28, FFIE approx 16 + 12.
- The calm stretch right before the trigger is approx 9–14 bars: TPST approx 8–9, FFIE approx 12, YELL approx 14–17.
- The video's waits run approx 4–40 bars: VERB 4–6, UCAR #2 5–6, CING 6–8, TPST approx 8, POL 8–10, NBSE 8–12, YELL 15–17, BACK more than 20, VVOS 35–40.
- He rejects SNES explicitly for having no base of a few bars.
- **Our 1-bar base is looser than every one of his valid charts.**

**Entry vs prior highs**
- TPST: at or above the premarket high (approx 1.25) and the after-hours high (approx 1.17–1.18).
- YELL: about level with the 9:00 high, under the 12:00 spike wick. % n/r.
- BACK: the video cursor sits approx at the 3.65 run high, under the 4.1 tennis-ball wick (my read, approx).
- VERB: just under the day high, % n/r.
- POL: approx 15% under the premarket 2.50.
- FFIE (study): approx 14% under the premarket high, approx 3% under the open-bar high.
- Video: UCAR #2, chart 9, VVOS, POL and BACK sit below the day's high so far; CING and YELL are at the earlier high.
- **Readable reversal-squeeze entries span approx 0–15% under the day's high. None is 20% or more under. Our median of -20.3% sits further under than any of his reversal-squeeze entries.**

**The SNES correction (it matters here).** The first reading put SNES's entry at approx 1.52, about 15% under the high. The video frame crop (frames_rs/crops/snes_buy.png) clearly shows the fill as 50000@1.9228. That puts the invalid SNES entry approx 6% ABOVE the overnight wick high (approx 1.81 by my read of rs_12's axis).
- So SNES was a retake of the highs that failed: one bar, the day's biggest red volume, a short base under the EMAs, sold at 1.6628 (-13.5%).
- **Retaking the high is not enough on his charts. The calm multi-bar base before it is what the valid ones have and SNES lacks.**
- GG's "retakes the previous highs" shows up as the snap-back retaking the pause or premarket highs (TPST's 6:00 push, BACK's 6:15 spike), and not always as the entry bar.

**Our numbers that look looser than his charts, with the evidence files**
- **1-bar base.** Every valid reversal-squeeze chart (rs_03 to rs_11), FFIE, and the video's 14 valid charts have 4 or more quiet bars. SNES (rs_12) is the rejected no-base case.
- **8% depth.** The readable quick tennis balls are 16–20% (rs_03 TPST, rs_10/11 BACK). An 8% swing is routine inside the invalid rs_13 SASI.
- **Trigger 20% under.** The readable reversal-squeeze entries are 0–15% under (rs_03, rs_04, rs_08, FFIE), and the video entries are at or below the day's high but none is shown far under it.
- **Tighter, not looser: the 3-bar recovery.** It is stricter than his charts: POL, FFIE, VERB, OMH, NBSE and UCAR #1 take 4–20 bars and are still valid.

**Stop.** In the video he points at a stop only once (VERB): it sits on the pause bars just before the push, above the lowest dump bar (approx). Ours is the lowest low of the base.

---

## 3. Per chart

Grades are calm / medium / choppy. "Base" is the number of bars in the pause before the trigger. "Entry vs high" is measured against the day's high so far. "Run after" is the move off the entry or trigger.

**Reversal squeeze (F4VS images + FFIE X post)**

| file | ticker | label | smooth | base bars | vol dried | entry vs high | run after |
|---|---|---|---|---|---|---|---|
| reversal_squeeze_03_TPST.png | TPST | valid | calm | ~60 flat; ~8–9 step bars before trigger | clearly | at/above PM high ~1.25 (0%) | ~+75% in 1 bar, ~+100% later |
| reversal_squeeze_04/05_YELL.png | YELL | valid | calm | ~52; ~14 narrow at top | clearly | ~level with 9:00 high (axis cropped) | +40% to Hi 5 (fill labels), ~16 bars |
| reversal_squeeze_06_VERB.png | VERB | valid | medium | ~60, wicky pokes, dip under EMAs | somewhat | just under day high, % n/r | +35% to Hi 3.75 (labels), ~10 bars |
| reversal_squeeze_07_HUDI.png | HUDI | valid | calm | ~6 + ~45 stair-step | clearly | under run's first high, % n/r | vertical, n/r |
| reversal_squeeze_08/09_POL.png | POL | valid | medium | ~18 after a -28% flush | clearly | ~15% under PM 2.50 | ~+55%+ in ~3 bars |
| reversal_squeeze_10/11_BACK.png | BACK | valid | medium | ~28 + ~28 after tennis ball | clearly | not marked; video ~at 3.65 run high, under 4.1 wick (approx) | Hi 5.4, ~+64% from ~3.3, ~8 bars |
| x_1790871471419482145_FFIE.png | FFIE | study | medium | ~16 + ~12 shelf | clearly | ~14% under PM high; ~3% under open high | +63% to 0.98, ~15 bars |
| reversal_squeeze_12_SNES.jpg | SNES | invalid | choppy | ~10, under EMAs | somewhat, then biggest red bar | fill 1.9228, ~6% ABOVE overnight high (corrected) | sold 1.6628 (-13.5%) |
| reversal_squeeze_13_SASI.jpg | SASI | invalid | choppy | ~200 chop, lower highs | tiny, then sold burst | none marked | drift to ~3.85 |
| reversal_squeeze_14_SGD.png | SGD | invalid | choppy | none; lower highs | heaviest is red, at open | none marked | lower, under 21 EMA |

**Bull flag**

| file | ticker | label | smooth | base bars | vol dried | entry vs high | run after |
|---|---|---|---|---|---|---|---|
| bull_flag_03_VCIG.png | VCIG | valid | calm | 2 | somewhat | ~3% under | ~+110% in ~7–8 bars |
| bull_flag_04_LIFW.png | LIFW | valid | calm (price) | 3 | no | at HOD | >= +40% in ~4 bars |
| bull_flag_05_BRSH.png | BRSH | valid | calm | 4 and 3 | clearly | just under leg high, % n/r | to 0.7891 in ~2 bars, % n/r |
| bull_flag_06/07/08_NXTP.png | NXTP | valid | medium | 4 (wide bars) | somewhat to clearly | ~16–19% under PM spike; top of RTH run | ~+60–65% in ~3 bars |
| bull_flag_09_DWAC.png | DWAC | valid | calm | 2–3 | somewhat | ~1–3% | ~+40% over ~50 bars |
| bull_flag_10_UPST.png | UPST | valid | medium | 3 | clearly | under 8:35 high, % n/r | +9.5% to Hi |
| bull_flag_11/12_ZYNE.png/.jpg | ZYNE | valid | calm | ~5 | clearly | at HOD | +21% in 2 bars |
| bull_flag_13_EHTH.png | EHTH | valid | calm | 4 | somewhat to clearly | ~0.3% | ~+4% in 2 bars |
| bull_flag_14_SECO.png | SECO | valid | calm | 2 | clearly | at HOD so far | to 3.79 in ~9 bars |
| bull_flag_15_FEMY.jpg (15m) | FEMY | valid | calm | 2 | clearly | at HOD | ~+45% in ~5 bars |
| bull_flag_16_OPGN.png | OPGN | valid | medium/choppy | 2, deep | no | at HOD | ~+180% in 3 bars |
| bull_flag_17_RKDA.png | RKDA | invalid | choppy | 2, ~54% giveback | clearly | % n/r | +8% to Hi, then failed |
| bull_flag_18_NVCT.png | NVCT | invalid | choppy | 5, 1-bar run | clearly | ~6% under | +1.6% best; sold -4.3% |
| bull_flag_19_OCX.png | OCX | invalid | choppy | ~3+, lower highs | no | ~6% under | sold -3.5% |

**EMA Kiss & Fly (no invalid charts in this set)**

| file | ticker | label | smooth | base bars | vol dried | entry vs high | run after |
|---|---|---|---|---|---|---|---|
| kiss_fly_03/04/05_USEA.png | USEA | valid | medium | ~5, wicky | somewhat | 0% | ~+24% in 3 bars |
| kiss_fly_06/07_BBBY.png | BBBY | valid | calm | 4 | somewhat to clearly | ~2% | ~+40% in ~8 bars |
| kiss_fly_08/09_MEGL.png | MEGL | valid | calm | 5 | clearly | ~4% | ~+55% in ~8 bars |
| kiss_fly_10_AERC.png | AERC | valid | medium | 5 / 3 / 3 | clearly | n/r (late fills -3.4%) | n/r |
| kiss_fly_11_AERC.png | AERC | valid | calm | 8–9, then shorter | clearly | n/r (fills -7% on one bar) | ran higher, n/r |
| kiss_fly_12_NRDY.png | NRDY | valid | medium | ~7, wide wicks | somewhat | at/near high | large, n/r |
| kiss_fly_13_HKD.png | HKD | valid | medium | ~9 | clearly | under wick high, % n/r | to Hi 56.01 in ~3 bars |
| kiss_fly_14/15_SATX.png | SATX | valid | medium | ~7 | clearly by end | leaves base ~14% under; through high in same bar | ~+39% from 28.7 |
| kiss_fly_16_GNS.png | GNS | valid | calm | ~11 / 8 / 8 | clearly | ~6% | +25% (fill), ~+40% high |
| kiss_fly_17/18_ELOX.png | ELOX | valid | calm | ~7 | clearly | ~2% | ~+70% in ~7 bars |
| kiss_fly_19_TUP.png | TUP | valid | medium | ~4 | somewhat | late fill ~2% (not the marked base) | fill -5.6% |
| kiss_fly_20_ICCT.png | ICCT | valid | calm | ~10 | somewhat to clearly | ~1.5% | +25% to +48% (fills); high 7.5 |
| kiss_fly_21_VFS.png | VFS | valid | medium | 4 | somewhat | 0% (at/above) | +16% to +20% (fills); 34 later |
| kiss_fly_22_NBSE.png | NBSE | valid | medium | ~8 | somewhat | ~8% (bar leaving base) | ~+37% in 3–4 bars |
| kiss_fly_23_BNOX.png | BNOX | valid | calm | ~7 | clearly | 0% | > +117% in ~12 bars |
| kiss_fly_24/25_TPST.png | TPST | valid | medium | ~6, wicky | somewhat | 0% | ~+50% |
| kiss_fly_26/27_LIFW.png | LIFW | valid | medium | ~8, wide | clearly | ~10% | ~+100% |
| x_1752509866852462684_NEXI.jpg | NEXI | winner | medium | ~5 | somewhat | ~1% | +16% to +36% (sells); Hi 28.69 |

**Horizontal fade** (file 10 "QNRX" is a crop of the PXMD chart and is not counted; 04 may be KALA, per its status line)

| file | ticker | label | smooth | base bars | vol dried | entry vs high | run after |
|---|---|---|---|---|---|---|---|
| horiz_fade_04_AERC.png | AERC (KALA?) | valid | calm | ~30 | clearly | at high | to Hi 23.7 in ~16 bars, % n/r |
| horiz_fade_05_KALA.png | KALA | valid | calm | ~13 (base 1) | clearly | at high | to Hi 56.72, % n/r |
| horiz_fade_06_PALT.png (3m) | PALT | valid | medium | ~12 / ~12 | clearly / no (base 2) | ~8% (base 1); ~12–20% (base 2, bodies vs wick) | ~+55–70% / ~+65% |
| horiz_fade_07/08_APLD.png (15m) | APLD | valid | medium | ~9 | clearly | ~8% | ~+30% in ~4 bars |
| horiz_fade_09_HKD.png | HKD | valid | calm | ~65 | clearly | under spike high, % n/r | off frame, n/r |
| horiz_fade_11_PXMD.png | PXMD | valid | calm | ~17 | mostly | ~1% | ~+22% in ~8 bars |
| horiz_fade_12_MEGL.png | MEGL | valid | medium | ~10, long wicks | clearly | under 8:50 high, % n/r | to Hi 2.9 in ~4 bars |
| horiz_fade_13/14_VVOS.png (15m) | VVOS | valid | calm | ~12 | clearly | ~10–12% | ~+170% in ~4 bars |
| horiz_fade_15_MLGO.png | MLGO | valid | calm (base 2) | ~28 | clearly | 0% (entry 1); ~4.5–8% (entry 2) | ~+55% in ~4 bars |
| horiz_fade_16/17_SPRB.png | SPRB | valid | calm | ~18 | clearly | 0% | > +38% in ~24 bars |
| horiz_fade_18/19/20_BWV.png | BWV | invalid | choppy | ~24, wide, crossing 9 EMA | dried | ~6% (impatient fill) | fill -2.8%; 5.00 line taken ~1h later, +28%, then full reversal |

**Intraday VCP + X posts INBS / MNPR**

| file | ticker | label | smooth | base bars | vol dried | entry vs high | run after |
|---|---|---|---|---|---|---|---|
| intraday_vcp_04/05_ELEV.png | ELEV | valid | calm | ~28 | clearly | ~13.5% | ~+56% in ~27 bars |
| intraday_vcp_06/07_DWAC.png | DWAC | valid | calm | 8 / ~34 | somewhat / clearly | ~2% / ~4% | ~+13% in ~18 bars |
| intraday_vcp_08_PHUN.png | PHUN | valid | medium | ~6 | somewhat | just under spike high, % n/r | off chart, n/r |
| intraday_vcp_09_SHOT.png | SHOT | valid | medium | ~20 | clearly | ~7.6% | ~+13% in ~18 bars |
| intraday_vcp_10_SIGA.png | SIGA | valid | calm | ~33 | somewhat | ~1.7% | ~+5% in ~34 bars |
| intraday_vcp_11_BWV.png | BWV | valid | calm | ~26 | clearly | ~9% | ~+80% to Hi 8 |
| intraday_vcp_12_SHPH.png | SHPH | valid | medium | ~8 | somewhat | at/slightly above | large, off chart |
| intraday_vcp_13_SHFS.png | SHFS | valid | medium | ~20 | clearly | ~9% | ~+60% in ~10 bars |
| intraday_vcp_14_CFVI.png | CFVI | valid | calm | ~19 | clearly | ~3.6% | ~+20% in ~21 bars |
| intraday_vcp_15_DWAC.png | DWAC | valid | calm | ~19 | clearly | 0% | ~+50% in ~56 bars |
| intraday_vcp_16_NVVE.png | NVVE | valid | medium | ~33 | clearly | ~14% | ~+55% in 3–4 bars |
| intraday_vcp_18/19_LQR.png/.jpg | LQR | invalid | choppy | ~40 flat, far under | yes | far under, % n/r | faded |
| intraday_vcp_20_AYLA.png | AYLA | invalid | choppy | ~20, wide/wicky | clearly | ~15% (fills) | fills sold 1.95 / 2.14; to ~1.64 |
| intraday_vcp_21_BE.png | BE | invalid | choppy | base halfway down spike | very clearly | >= 5% | fell to ~19.8 |
| intraday_vcp_22_MNRA.png | MRNA | invalid | choppy | chop | yes | fills 163.08 / 162.80 | both sold lower |
| x_1753525024026218742_INBS.png | INBS | study | medium | ~10 + more | somewhat | ~18% (line end) | high never retaken |
| x_1760876336258941369_MNPR.jpg | MNPR | no label | medium | cup ~23 + handle ~3 | clearly / somewhat | 0% | ~+28%, then slid back under |

**Other X posts**

| file | ticker | label | smooth | base bars | vol dried | entry vs high | run after |
|---|---|---|---|---|---|---|---|
| x_1733178876023521301_unknown.jpg + x_1733882105204011109_unknown.jpg | INTS | loser | choppy | ~12, lower highs a>b>c | clearly | ~31–33% under HOD 15; ~9–12% under 11.4 | ~-28% in ~3 bars |
| x_1772832725969596865_CGC.jpg | CGC | no label | calm | ~11 | somewhat, then clearly at end | ~0–1% | ~+12% in ~8 bars |
| x_nopost_ABVC.png | ABVC | no label (fills show a loss) | choppy | ~9, wide two-way | no (red bar taller than run) | ~19% under HOD; ~5% under local high | fill -5.8% |
| x_nopost_NVIV.jpg | NVIV | no label | calm | ~14 | clearly | ~26% under HOD wick; ~18% under closing high | +80% (his tag) in ~6 bars |

**Reversal Squeeze video** (frames_rs/; no price axis anywhere, so every size is n/r)

| chart | label | return to EMAs | wait bars | entry vs day high so far |
|---|---|---|---|---|
| TPST | valid | 1–4 bars | ~8, then steps | at/above PM highs |
| MSS | valid | 2–3 bars | none flat | arrow at the dip; highs taken after |
| YELL | valid | 1–2 bars | ~15–17 | ~at earlier high |
| VERB | valid | 4–6 bars | 4–6 | below 8:50 high (approx) |
| UCAR #1 | valid | 4–6 bars | short | arrow before the vertical move |
| UCAR #2 | valid | no dump; held 21 EMA | 5–6 | at/below PM high |
| OMH | valid | 8–10 bars | climbs in steps | at/above PM (approx) |
| "TOP" (ticker cut) | valid | 2–4 bars | none clear | below the 260 Hi |
| ticker n/r (11/3/22) | valid | gradual | ~9 tight bars | below spike high |
| VVOS | valid | 1 bar (13:10 dip) | 35–40 | below 10:00 peak |
| NBSE | valid | 8–12 bars | 8–12 | breaks PM range |
| POL | valid | ~6 bars | 8–10 | below PM tops |
| BACK | valid | 1–3 bars | more than 20 | under the 6:15 top |
| CING | valid | slow | 6–8 | ~at the 8:30 high |
| SNES | invalid | 1 bar to the highs | none | above prior high (fill 1.9228), rejected |
| Sigma Additive | invalid | none; lower highs | none | none marked |
| Omega | invalid | random | none | none |
| Safe & Green | invalid | ~8 bars to EMAs | none | expected move never came |

---

## 4. Caveats

- **Selection bias.** These are hand-picked teaching examples chosen after the fact, and most valid charts show a big run after the entry. The 11 invalid examples are also hand-picked and few. Nothing here gives a hit rate.
- **Third-party source.** Most charts come from F4VS's write-up, built from GG's material. The labels are section headings, and some fills on those charts may belong to F4VS rather than GG. GG's own material here is the video and the X posts.
- **Unreadable charts (counted).**
  - Price axis n/r on 19 image charts: reversal squeeze YELL, VERB, HUDI, SGD; bull flag BRSH, UPST, RKDA; kiss & fly AERC x2, NRDY, HKD, TUP; fade AERC/KALA, KALA, HKD, MEGL; VCP PHUN, SHPH, LQR.
  - Six VCP charts are scaled from tags only (SHOT, SIGA, BWV, SHFS, DWAC-15, NVVE), so their numbers are approx.
  - The video has no price axis on any of its 18 charts.
  - 11 of the 55 valid setups had no readable entry distance (or only late fills), which is why the entry counts use 44.
- **Manifest errors.**
  - horiz_fade_10_QNRX.png is a crop of the PXMD chart, so no QNRX chart exists.
  - horiz_fade_04_AERC.png may be KALA.
  - The SNES entry was misread at first (corrected in §2).
- **Subjective grades.** Calm / medium / choppy is one reader's eye per chart. Bar counts are approx, read off time-axis spacing.
- **Counterexample.** NVIV (no label, calm) triggered approx 26% under its HOD wick, at the EMAs after a long dried-up slide. Distance from the high alone does not decide calm vs choppy.
- **Different timeframes.** FEMY, APLD and VVOS are 15m and PALT is 3m; the rest are 5m. The ToS clocks read Central (8:30 = open).

**Verification (charts I opened myself with Read before writing):**
- rs_03 TPST: confirmed. The run is approx 16–18 bars (15:00–16:30). The tennis-ball wick is approx 0.80 and the entry is approx 1.2–1.37.
- rs_12 SNES: **corrected.** The fill is 1.9228 (video crop snes_buy.png), approx 6% above the overnight high, not 15% under.
- rs_10 BACK: confirmed, and I added the entry read.
- bull_flag_03 VCIG: confirmed (entry approx 5.44, stop approx 4.88, Hi 11.32).
- horiz_fade_18 BWV: confirmed (fills 4.6899 / 4.5586, 5.00 high, approx 6.4 peak, reversal).
- intraday_vcp_04 ELEV: confirmed (approx 0.87 to 1.48, first low approx 1.06, approx 2.0 by about 14:45–15:15).
- rs_08 POL: confirmed (2.48–2.50 premarket high, flush to approx 1.65, entry approx 2.02–2.11).
- X INTS: confirmed (Hi 15, approx 11.4 session high, entry approx 10.15, approx 7.3 after).

---

## 5. What could be MEASURED next (no rule change; every threshold is HIS CALL)

Run these on our own 🎾 triggers (the 31 from tonight) and on the track record, bucketed. Every range below comes from his charts.

1. **Trigger distance under the day's high so far.**
   - His readable valid entries: 30 of 44 within approx 4%, 12 at approx 5–14%, 2 at approx 15–19% (POL, NXTP), and 0 at 20% or more.
   - For the reversal squeeze alone: approx 0–15%.
   - Measure outcomes by bucket: 4% or less, 4–15%, more than 15%. The candidate X range is **4–15%**.
2. **Quiet bars before the trigger.**
   - His reversal-squeeze waits run approx 4–40 bars, and the calm stretch right before the trigger is usually approx 8–14.
   - Across all setups the minimum is 2 (bull flag).
   - Measure outcomes for 1, 2–3, 4–7, 8–14 and 15 or more bars. The candidate N range is **4–14**.
3. **Tennis-ball depth and speed.**
   - The readable quick tennis balls are approx 16–20%, reclaimed in 1–3 bars. The flushes (approx 28–35%) rebuild over approx 15–20 bars and are still valid.
   - Measure 8–15% vs 15% or more, and 1–3 vs 4–20 recovery bars.
4. **Base position vs EMAs.** Measure the share of base closes on or above the 21 EMA, and whether the 9 is above the 21 at the trigger. Every valid base holds them; every invalid base tangles or cuts under.
5. **Lower highs inside the base.** Count the swing highs that are lower than the one before. Lower highs mark the invalid and loser charts (SASI, SGD, OCX, INTS).
6. **Bar range in the base vs the run.** Measure the median base-bar range divided by the median run-bar range. Base bars are clearly narrower on the valid charts and wide with two-way wicks on BWV, AYLA, ABVC and INTS.
7. **Red volume inside the base.** Flag any base bar whose red volume is at or above the mean run-bar volume (ABVC, OCX, SNES).
8. **Volume at most 0.50× the run (current K3_VOL_FRAC).** Measure it alongside items 1–7. On his charts it passes on several invalid ones, and some valid kiss & fly bases sit at approx 0.5–0.8×.
9. **Stop placement.** Compare the lowest low of the base (ours) with the low of the last pause bar (his VERB stop, kiss & fly TPST and BBBY) on the same triggers.

None of this changes K8_DROP_PCT, K8_RECOVER_PCT, K8_RECOVER_BARS, RS_BASE_MIN_BARS or K3_VOL_FRAC. The numbers to adopt, if any, are Ajay's call after the measurement.
