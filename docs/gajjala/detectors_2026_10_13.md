# Gajjala's tab — the five detectors (WP3, 2026-10-13)

`backend/chart_maps/gajjala/detectors.py` — PURE functions over CLOSED bars (+ the 9/21 EMAs bars.py computed). No
fetch, no Mongo, no clock. Every number is a constant in `constants.py`, read at call time (`GC.NAME`), so a test can
patch any of them; a source guard refuses any numeric literal in the file other than 0 / 1 / 2 (indexing, the K6
halves) and 100 (percent). Not SEPA: no trend-template gate, import or cite. UNMEASURED — his rules as he described
them, not a forecast. Tests: `backend/tests/test_gajjala_detectors.py` (198), fixtures
`backend/tests/fixtures/gajjala/detector_frames.py` (binary-exact prices; edges built with the detector's own expression).

Binding order used: DECISIONS "ROUND A/B/C ANSWERS" > FIRST_HAND > BUILD_SPEC §3.3 > STRATEGY_SPEC §3.2 deltas.

## Input / output
- Input: `bars.Frame` (ONE definition, bars.py) — `o h l c v t session ema9 ema21 today df minutes frame`; `t` = the
  bucket's right-label ET stamp; `minutes[t[j]]` = that bucket's 1-minute bars. `read_all({"5m": F5, "15m": F15},
  {"symbol", "float_read"})` = `Frames.detector_frames()` + ctx. Every detector also takes `last=` (read as if bar `last`
  were the latest closed bar — the no-look-ahead test reads every prefix this way and against a truncated frame).
- Read keys: `setup state frame ready broke leg base trigger stop risk_pct entry_bar_t bars_since_entry criteria missed
  unjudged reason as_of_bar_t meta{structure_alive} grade variant red_closes flag_k`.
- States: `aplus` (every criterion True, clean break on the latest bar, not stopped since) · `triggered` (same, entry
  bar older) · `stopped` (clean A+ break, then a minute after the break minute or a later bar under the stop — HIS CALL
  10) · `forming` (no break; `ready` = minimums met and nothing unjudged) · `partial` (alive, ≥ 1 criterion False, or a
  break that missed a rule: `broke` True, reason "broke — not A+") · `invalid` (structure died) · `none` (no structure,
  float gate, or a placeholder unanswered — "awaiting Ajay's answer (Hn)").
- A criterion with `ok` None (EMA warm-up on a first-print name) is NOT JUDGEABLE: never A+, never raises.
- `missed` lists only REAL failures. A criterion that is only waiting on a forming read (a length minimum not reached
  yet, the kiss not printed yet) still shows ✗ in `criteria` but is NOT in `missed` (fix 2026-10-13).
- Which leg (fix 2026-10-13, `_live_structure`): today's legs are walked oldest first. A newer leg that starts inside
  the current structure (its pullback / base / cycles) or AT its break bar does NOT replace it while that read is
  forming / aplus / triggered (`LIVE_STATES`). Any other leg (after the break bar, or after the structure died / was
  stopped / went partial) starts a new structure. Before this, the newest leg always won (`legs[-1]`), so a +3%
  breakout bar or a K1 upswing inside the VCP cycles erased a live A+ (Kiss & Fly and VCP use 1-bar legs).
- `read_all` never raises: a per-setup exception reads `none("detector error")`, logged with the symbol.

## Shared helpers (BUILD §3.3.0)
- K1 `is_demand(i)`: prior-20-bar average range exists (frame index ≥ `K1_RANGE_LOOKBACK`) AND `c ≥ o × (1 +
  K1_BODY_GAIN_PCT/100)` AND `range ≥ K1_RANGE_MULT × average`. `find_legs` = maximal runs of consecutive K1 bars inside
  TODAY only (yesterday's after-hours leg never counts).
- K2 `k2_ok(s, e)`: within the leg each volume ≥ the previous and ≤ `K2_MAX_VOL_STEP` × it (HIS CALL 4, Ajay round C
  R1-5 "stays within the leg"); `K2_CHECK_FIRST_BAR` (off) would also check leg bar 1 vs the candle before (his OCX).
- K3 depth floor `h[a] − K3_DEPTH_FRAC × range(a)` binds ONLY the setups in `K3_DEPTH_SETUPS` = Bull Flag + Kiss & Fly
  (Ajay round C — reverses BUILD HIS CALL 8). K3 volume cap `K3_VOL_FRAC × mean(volume of the anchor run)` binds all
  four leg setups and the squeeze base.
- `entry_event(j)`: walk bar j's 1-minute bars — first minute above the trigger = break; under the stop first = stop
  (→ invalid "stopped before the break"); both in one minute = ambiguous (→ partial with an `entry` criterion False, never
  A+). No minutes → break if the whole bar held the stop, else ambiguous.
- `red_closes` = the longest run of red closes (`RED_CLOSE_DEF` = close < open, Ajay round C) in the pullback/base. Chip
  only (`RED_CLOSES_MODE` = "chip"); "criterion" mode adds "no more than `RED_CLOSES_WAIT` red closes in a row".

## 🚩 Bull Flag (GG S8 21:45–24:37, S9 1:59:24; K1–K4, K4a)
```
legs = find_legs(BF_LEG_MIN_BARS)  → none "no 2-bar demand leg today"; (s, e) = the live structure's leg
j = first i in [e+2 .. last] with h[i] > h[i−1]; P = [e+1 .. j−1 or last]
len(P) > K4_BF_LONG_FLAG_MAX (5)  → invalid                          # Ajay K4a
K3 depth fails                    → invalid
crit = k2, k3_vol, k4 (K4_BF_PULL_MIN–K4_BF_PULL_MAX = 1–3)
4–5 bars → k4 False, variant "long_flag" → partial (listed, never A+, never pushed)   # Ajay K4a
no j: trigger/stop = h/l[last]; 0 pullback bars = forming not ready "waiting for the pullback bar"
j:   trigger/stop = h/l[j−1] → entry_event / state table
flag_k = 1 + earlier STRUCTURES today (a leg absorbed into a live flag is not a new flag) whose own read (bounded at the next leg) was not none/invalid (display, STRATEGY D-FLAGN)
```

## 💋 EMA Kiss & Fly (GG S8 31:33–32:41, S9 1:55:28; K1–K5, K5a)
```
legs = find_legs(KF_LEG_MIN_BARS = 1); (s, e) = the live structure's leg
touch(k) = low ≤ EMA9 × (1 + K5_KISS_TOL_PCT/100) or the bar crosses EMA9;  kiss(k) = touch and close > EMA9
uptrend(k) = EMA9 > EMA21 and both > their value K5_SLOPE_BARS bars earlier
j = first i ≥ e+2 with kiss(i−1) and h[i] > h[i−1]
near-kiss (Ajay K5a, KF_ALLOW_NO_TOUCH): the first i ≥ e+2 with h[i] > h[i−1] while NO pullback bar touched yet —
    RECORDED, not final (fix 2026-10-13): the scan goes on, and a kiss-then-break j with ≤ K4_KF_PULL_MAX pullback
    bars wins; near-kiss is used only when there is no such j up to `last` AND no bar from the near-kiss bar to
    e + K4_KF_PULL_MAX has touched since (K5a: "never kissed"). Before, the first higher high froze the read and a
    later kiss was never A+.
P = [e+1 .. j−1 / near−1 / last]
len(P) > K4_KF_PULL_MAX (9)                  → invalid                 # Ajay K5a (was 8)
K3 depth fails                                → invalid
any pullback CLOSE < EMA9                     → invalid "did not honor"  # Ajay K5a REVERSES BUILD HIS CALL 5
crit = k2, k3_vol, k5_uptrend (at the kiss bar), k4, k5a_honor, k5_kiss
near-kiss: partial, broke, missed k5_kiss; variant "near_kiss" when K3 volume + uptrend pass (never A+, never pushed);
           trigger/stop = h/l of the last pullback bar (STRATEGY D-KF3)
no j: forming — kiss on the latest bar → ready; kiss None → "9 EMA warming up — not judgeable yet";
      kiss False → "x.x% above the 9 EMA — waiting for the kiss"
j: trigger/stop = h/l of the kiss bar → entry_event / state table
```

## ➖ Horizontal Fade (GG S8 32:49–33:50, 1:20:08, S9 1:56:08, 2:00:12; K1–K4, K6)
```
horizontal_fade(F15, F5): 15m read wins when aplus / triggered / forming-ready; else the 5m read, except a 15m
    structure stays when the 5m read is none / invalid (HIS CALL 27, accepted)
fade_on: legs = find_legs(HF_LEG_MIN_BARS = 2 — H3); (s, e) = the live structure's leg
base B = [e+1 .. j−1]; criteria at the bar before the entry:
    k4 6–24 bars · k3_vol · k6_tight (base high − low ≤ K6_TIGHT_PCT % of close) ·
    k6_merge (|EMA9 − EMA21| ≤ K6_MERGE_PCT % of close; None in warm-up) ·
    k6_decay (mean volume of the second half < K6_SELL_DECAY × the first half; odd middle bar dropped)
    — NO K3 depth (Ajay round C)
j = first i ≥ e+1+6 with h[i] > max(h[B]) (HF_TRIGGER "base_high", Ajay round C: "takes the new highs") and every
    criterion True; an earlier higher high while a K6 rule fails is a BASE bar
trigger = max(h[B]); stop = l[j−1] ("risk very tiny below the previous bar")
no j: B > 24 → invalid; base wider than 8% of the latest close → invalid; < 6 bars → forming "base n of 6 bars";
      a criterion False → partial; None → forming not ready; all True → forming ready
```

## 🌀 Intraday VCP (GG S8 33:50–34:37; K1, K4, K7, H3, H5)
```
legs = find_legs(VCP_LEG_MIN_BARS = 1 — H3); (s, e) = the live structure's leg
pivots = price_zones._local_extrema(bars e..last, VCP_PIVOT_WINDOW = 2 — H5)   (confirmed by closed bars only)
H1 = the highest bar from e to the first pivot low; walk pivots in time order: a pivot low deepens the current cycle;
    a pivot high after a low opens the next cycle; ANY bar above the current cycle high = the break j → STOP
    (structure frozen, C8 — later pivots never move H_n, L_n, trigger or stop)
L_n = the lowest bar between H_n and j (or last) — the bars BEFORE the break
lower low (low_k ≤ low_k−1)            → invalid (structural, his)
crit = k4_cycles (≥ K4_VCP_MIN_CYCLES), k7_ratio (each range ≤ K7_CONTRACTION × previous),
       k7_ema21 (each cycle low ≥ EMA21 × (1 − K7_EMA21_TOL_PCT/100)), k3_vol (every pullback bar) — NO K3 depth
"B — imperfect" (VCP_B_READS, Ajay round C): exactly one of {k7_ratio, k7_ema21} False and everything else True →
    partial, grade "B", reason "B — imperfect · missed …" (never A+, never pushed)
k7_ema21 False and not B               → invalid "cycle low under the 21 EMA"
trigger = h[H_n], stop = l[L_n] (HIS CALL 6: "entry the top of this cycle, stop the low of this cycle")
no break: forming, ready = ≥ 2 cycles and the cycle low is not the latest bar; break: entry_event / state table
    (entry bar under the stop before its break minute → invalid; after → stopped)
```

## 🎾 Reversal Squeeze (GG S8 35:02–38:18, S9 2:00:32–2:02:40; K8, H1, H2, H4)
```
tennis ball (r, d, k): r = running-high bar; d = first bar with low ≤ h[r] × (1 − K8_DROP_PCT/100);
    k = first bar in [d .. d + K8_RECOVER_BARS] CLOSING ≥ h[r] × (1 − K8_RECOVER_PCT/100);
    no k → a plain sell-off, the running high restarts after d.
    d may be r itself ONLY when r's 1-minute bars show the high first (see judgement call J1)
failed attempt (H1, 2 / 8): h[a] ≥ today's high so far (premarket incl.) × 0.98, close under that high, then a later bar
    — before any high exceeds max(h[a], that high) — with low ≤ h[a] × 0.92
pairing (H2 "distinct"): an attempt whose failure bar f < r; "same_ok" also admits a ≤ r and f ≤ k
tb = the latest paired tennis ball, else the latest (k8_failed False)
top p / break j: p = k; each higher high moves p unless ≥ RS_BASE_MIN_BARS (H4 = 1) base bars sat under p → j
R = [d+1 .. p] (the squeeze-back run); B = [p+1 .. j−1 / last]; trigger = h[p]; stop = min l[B]
crit = k8_tennis, k8_failed, k3_vol (base vs R), k8_base_len — NO K1 leg, NO K2, NO K3 depth (Ajay round C)
no tennis ball → none "no tennis ball today …"
float gate LAST: shares None (or a suspect float under FLOAT_SUSPECT_POLICY "ineligible") → none "float unknown";
    shares > K8_MAX_FLOAT → none "<float text> > 10,000,000"; meta.structure_alive (= a tennis ball exists) kept
```

## H1–H5 option sweep (pinned in `test_each_placeholder_option_reads_as_documented`)
| Option | Fixture | Read |
|---|---|---|
| H1 = 2 / 8 (Ajay) · 2 / 4 | squeeze A+ | aplus · aplus |
| H2 = distinct (Ajay) · same_ok | squeeze A+ | aplus · aplus |
| H2 = distinct · same_ok | S8 36:12 shape (the try at the highs IS the tennis-ball start) | partial · aplus |
| H3 Fade leg = 1 · 2 (Ajay) · 3 | Fade A+ (2-bar leg) | aplus · aplus · none |
| H3 VCP leg = 1 (Ajay) · 2 · 3 | VCP A+ (1-bar leg) | aplus · none · none |
| H4 base = 1 (Ajay) · 2 · 3 | squeeze A+ (2-bar base) | aplus · aplus · forming (the top moves) |
| H5 pivot window = 1 · 2 (Ajay) · 3 | VCP A+ (break 1 bar after the 2nd low) | aplus · aplus · forming (2nd high unconfirmed) |
Any H constant set to None → that setup reads `none("awaiting Ajay's answer (Hn)")`; an out-of-list H2 value too.

## His invalid examples (synthetic shapes, `detector_frames.py`)
OCX first up bar 10× the candle before → A+ at the default, partial k2 with `K2_CHECK_FIRST_BAR` · RKDA two sudden bars +
a deep first pullback → invalid (both settings) · NVCT one big candle → none · ZYNE 5-bar flag → long flag; invalid with
LONG_FLAG_MAX 3; A+ with PULL_MAX 5 · HKD 9-bar Kiss & Fly → A+ (invalid at the old 8) · NEXI never touches → near-kiss
· BWV impatient break before 6 base bars → forming, never A+ · LQR heavy selling after the main bar (under the 21 EMA
on heavy volume) → invalid, both B settings · AYLA sharp pullback (expands AND under the 21 EMA) → invalid, both ·
SNES spike + violent decline → none · SASI steady fade → none · SGD no demand after the open → none · FCHL float on file
above shares out → none under "ineligible", A+ under "shares_out".

## Deviations from BUILD §3.3 / the WP3 test list (and why)
- DECISIONS overrides applied: K4a long flag; K5a honor rule + 9 bars + near-kiss; HF trigger = base high; VCP "B";
  K3 depth on Flag + Kiss & Fly only (so BUILD's "invalid if base sank below half" lines for Fade / VCP / Squeeze are
  gone, and the 🎾 "base under the top bar's midpoint → invalid" test now pins the OPPOSITE).
- 🎾 "7.99% drop → partial" reads `none`: with no tennis ball there is no structure (BUILD's own `structure_alive = tb
  exists`), so there is no top bar, base, trigger or stop to tile.
- "First-print name, 12 bars" reads `none` for all five (K1 needs 20 prior bars, so no leg exists); the EMA-None
  criteria + "9 EMA warming up" reason are pinned on a separate frame whose EMAs are None.
- Length minimums (BF 1 bar, Fade 6 bars, VCP 2 cycles, 🎾 H4 base, the K&F kiss) keep a read `forming` (not ready)
  instead of `partial` while unmet — the criterion still shows ✗ with "n of N".
- Fade forming with both a False and a None criterion reads `partial` (False wins); BUILD listed None first.
- Fade "base wider than 8%" is judged only while no entry has printed (after a break the base was already judged at the
  bar before the entry).

## Judgement calls / OPEN QUESTIONS for Ajay
- J1 (made, needs his OK): a tennis ball whose drop bar is the high bar itself needs the 1-minute order high-then-low.
  BUILD's literal "d may == r" made every ≥ 8%-range GREEN bar (low first, high last) a tennis ball.
- Q1 (CHANGED 2026-10-13 after review; the rule is still HIS CALL): BUILD took `legs[-1]`, so any K1 bar at or inside a
  structure (a +3% breakout bar, a K1 upswing inside the VCP cycles) erased it. Default now = option (b), widened: a
  leg that starts inside a live (forming / aplus / triggered) structure or at its break bar does not replace it (see
  "Which leg" above). Pinned by the NEGATIVES `test_a_k1_entry_bar_does_not_erase_the_kiss_fly_a_plus`,
  `test_a_k1_upswing_inside_the_vcp_cycles_does_not_erase_the_vcp`,
  `test_a_two_bar_k1_breakout_keeps_the_bull_flag_triggered_and_flag_1`, and the other way round by
  `test_a_leg_after_the_break_bar_does_start_a_new_structure` / `test_a_stopped_structure_does_not_hold_back_a_newer_leg`.
- J2 (made, needs his OK): a near-kiss whose pullback later touches the 9 EMA (inside the K4_KF_PULL_MAX window) is no
  longer a near-kiss; it reads as an ordinary Kiss & Fly (forming while it waits for the break). DECISIONS K5a only
  says near-kiss = "never kissed"; the touch-since check is how that wording is applied.
