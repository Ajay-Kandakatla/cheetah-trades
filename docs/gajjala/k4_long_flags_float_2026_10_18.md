# 🚩 K4 long flags are A+ · 🎾 lowest float on top (2026-10-18)

Branch `feat/gajjala-k4-long-flags-float-sort-2026-10-18` off main 3ab4d2c5. Decisions: DECISIONS13 D1–D8.
Build spec: BUILD_SPEC13 (WP-A backend, WP-B frontend, WP-M docs). Not SEPA. **UNMEASURED.**

## READ THIS FIRST

What changed, in his words (Ajay, 2026-10-18, in order):

> "Keep the float reduce and also 15 mins filter."
> "make the change for Long flags"
> "for the float lower the better is what I wanna follow so sort it by lowest on top"

- **🚩 Bull Flag: a 4- or 5-bar pullback is A+ now.** `K4_BF_PULL_MAX = 5` (was 3) and `K4_BF_LONG_FLAG_MAX = None`
  (was 5). 1–5 pullback bars pass K4; when the break prints on a closed bar the read is A+ and it rings like any other
  A+. More than 5 bars = invalid, as before. (D1)
- **🎾 Reversal Squeeze: lowest float on top.** On the `reversal_squeeze` sub only, tiles in the same state list by
  float, smallest first; a name with no usable float lists last. The ordering word is served by the backend:
  "🎾 lowest float on top". (D3)

What did NOT change, in his words: *"Keep the float reduce and also 15 mins filter."* (D2)

- `K8_MAX_FLOAT = 10_000_000` stays. A squeeze name above 10,000,000 float is still not a 🎾 read.
- `NO_TRADE_AFTER_OPEN_MIN = 15` stays. Nothing rings on an entry bar that starts before 09:45 ET.
- Both constants gain a dated `# Ajay 2026-10-18` comment; their values and their pins are untouched.

## The evidence (with provenance)

| Source | Provenance | What it shows |
|---|---|---|
| S8 21:45–24:37 (IBD webinar) | FIRST-HAND (verified rule BF3) | "the pullback is one bar, usually two to three bars" — the typical case, not a cap |
| S10 masterclass | FIRST-HAND (BF3 rule text) | his own valid example took five bars to the side |
| S3 bull-flag post (Substack) | THIRD-PARTY — F4VS relay, no GG passage in quotation marks | NXTP with 4 sideways pullback bars and ZYNE with 5 pullback bars, shown as valid Bull Flag trades |
| S8 21:04 (verified rule U6) | FIRST-HAND | on the squeeze: "the lower the float the better"; GG gives no cutoff |
| S7 reversal-squeeze post (Substack) | THIRD-PARTY — F4VS relay | the same low-float line, relayed; no number |

The 10,000,000 float cap is Ajay's K8 number, not GG's (GG states no cutoff). The 1–5 range is Ajay's call on
2026-10-18 after the 2026-10-17 Substack read; GG's first-hand words give "usually two to three" and one five-bar example,
never a hard maximum.

## The K4 rule now

```
P = the pullback bars after the leg (e+1 .. j−1, or to the last closed bar while no break)
len(P) > long_max            → invalid "pullback longer than 5 bars"
                               long_max = K4_BF_LONG_FLAG_MAX, or K4_BF_PULL_MAX when that is None (now: 5)
K4 = K4_BF_PULL_MIN ≤ len(P) ≤ K4_BF_PULL_MAX   (now 1–5)
the "long_flag" variant      → only when len(P) > K4_BF_PULL_MAX and len(P) ≤ long_max — an EMPTY band while
                               K4_BF_LONG_FLAG_MAX is None
```

- The detector logic is unchanged (`detectors.py` already reads None as "fall back to `K4_BF_PULL_MAX`"). With
  LONG_FLAG_MAX None, `long_max == PULL_MAX`, so a 6-bar pullback takes the invalid path and the `long_flag` variant line
  is never reached.
- The variant code path stays config-driven: set `K4_BF_PULL_MAX = 3` and `K4_BF_LONG_FLAG_MAX = 5` and 4–5 bars read
  "long flag" (partial, listed, never A+) exactly as on 2026-10-13. A test pins that.
- The K4 label reads "K4 pullback 1–5 bars" with no "long flag" suffix while the band is empty. The 📓 Playbook K4 line
  reads "Bull Flag 1–5 bars · Kiss & Fly ≤ …" and the ℹ️ panel says "1–5 bar quiet pullback", both built from the
  constants at call time.
- 🧠 Potential: a 4–5 bar forming flag is a `forming` read now, so it IS a potential candidate (it was `partial` before).
- 🔔 Push: `not_aplus_variant` still refuses the near-kiss and the VCP "B — imperfect"; a long-flag read no longer occurs
  under the shipped setting. /notifications "WHAT NEVER FIRES" no longer names a long flag (both the 🚩 and the 🧠 kind).
- `scripts/gajjala_examples.py`: the shipped setting is the old "R1-4b" (flag 1–5); the alternative
  "R1-4c flag 1–3 + long flag (pre-2026-10-18)" stays in SETTINGS so the examples table still shows both readings.
- The FE fallback word `GG_VARIANT_LABEL.long_flag` stays (older payloads), with a dated comment; dropping it = HIS CALL Q3.

## The 🎾 order

- Constant `RS_FLOAT_SORT = "within_state"` (`# MINE`, D3). Key: state rank first (A+ › triggered › ready › forming ›
  partial › stopped, `tab.order_key`), then float ascending, unknown float last, then the existing tiebreaks. An A+
  never sinks under a forming name on its float — the convention every Gajjala sub follows.
- `"global"` flips it: float first, state second. One constant; which one is HIS CALL Q1.
- Unknown float = no float on file, a float of 0, or a float flagged suspect while `FLOAT_SUSPECT_POLICY` is
  "ineligible" (the same policy `context.rotation` applies). Unknown lists last.
- Plumbing: `setup_tile` stashes `_float_shares` on the tile's `gajjala` block (beside `_last` / `_bars_to_go`),
  `order_key` reads it for `setup == "reversal_squeeze"`, `_strip_private` removes it before the payload is served.
- The word: `tab.RS_ORDER_TEXT = "🎾 lowest float on top"`, served as `order_note` on the squeeze sub's payload, `null` on the other four
  setup subs and ABSENT on the list / 🧠 / 🏁 / 📓 subs (tab.py sets it inside the setup-sub branch only). The board prints it verbatim, muted, after the sub chips (`data-testid="gg-order-note"`); the FE
  types no word and has no sort control.
- The other subs keep their order byte for byte (their tiles carry no float today; float order there = HIS CALL Q2).

## Before / after

Counted on the cached fixtures, offline, main 3ab4d2c5 versus the branch commit. A count of reads that move, never an
edge claim.

<!-- filled by the main session 2026-10-18 -->

| Run | main 3ab4d2c5 | branch | moved |
|---|---|---|---|
| `scripts.gajjala_examples` (his 27 dated charts, minute bars fetched once into a scratch cache, then offline): bull-flag examples whose best state changes under 1–5 bars | 0 of 11 | 0 of 11 | 0 — the dated set holds no 4–5 bar flag; every bull-flag row's nearest miss is k2 / k3_vol / k3_depth, and the pre-existing "flag 1–5" setting column already read identical to "shipped" |
| `scripts.gajjala_replay` 2026-10-09 + 2026-10-12 (the 2026-10-17 run, detectors sha256 519282dd… = main's detectors today): breaks kept / dropped as a long-flag variant | 2 + 5 kept / 0 variant | not re-run | 0 — no break on either session was dropped as a variant, so 1–5 bars cannot add a replayed row there; a fresh run needs the study cache's grouped-day files rebuilt (they are gone from the scratch cache) |
| the goldens (synthetic fixtures, regenerated as the owner): the 4-bar flag `EEE` | partial "long flag", never a potential | forming, a 🧠 potential, armed; FIRST on the 🚩 strip (float 1M) | 🚩 strip [AAA, JJJ] → [EEE, AAA, JJJ]; 🚩 tiles [AAA, JJJ, GGG, EEE] → [EEE, AAA, JJJ, GGG, FFF]; 🧠 tiles 5 → 6; the partial tile is now `FFF` (a real k3_vol miss) so a partial still exists to pin |

What this says: on the sessions and charts on file, the only reads that move are the synthetic fixture's. The first LIVE
4–5 bar flag that rings will be the first measurement; the 2026-10-14 study measured 1–3 bar flags and never the
4–5 bar reads (UNMEASURED).

The LIVE `gajjala_replay` collection is NOT rewritten: the 7 replayed docs stay as written on 2026-10-17 (a re-replay
with the new K4 = HIS CALL Q4).

## What it does NOT do

- No change to the float cap (10,000,000) or the first 15 minutes — his word.
- No change to any other K rule, gate, window or push kind; no change to K5–K10.
- No float order on the Bull Flag, Kiss & Fly, Fade, VCP, Premarket, Post-market, 🧠 Potential or 🏁 Track record subs.
- No Mongo write; the 2026-10-09 / 2026-10-12 replay docs and the hand fixture `gajjala_board_2026_10_13.json` are untouched.
- No measurement: 4–5 bar flags are A+ on his call. The 2026-10-14 study of the five setups read NULL; the study
  measured 1–3 bar flags; the 4–5 bar A+ reads were never measured.

## Verification

Backend (hermetic, `cheetah-tmp-pytest-k4-a-<n>`, `--network none`):
- `test_gajjala_constants.py` — K4 pin `(1, 5, None)` dated; `RS_FLOAT_SORT in ("within_state", "global")`;
  `K8_MAX_FLOAT` and `NO_TRADE_AFTER_OPEN_MIN` pins unchanged.
- `test_gajjala_detectors.py` — `test_bf_4_or_5_bars_is_aplus_since_2026_10_18`, `test_bf_6_bars_is_invalid`,
  `test_bf_1_to_3_bars_unchanged`, `test_NEGATIVE_the_dormant_long_flag_band_still_reads_when_configured`; the mutation
  row `("K4_BF_PULL_MAX", 3, "bf5")`; the K4 label test (None → "K4 pullback 1–5 bars", (2, 5) → "(3–5 = long flag)").
- `test_gajjala_tab.py` — `test_squeeze_tiles_order_by_float_ascending_within_state`,
  `test_squeeze_aplus_stays_above_forming_whatever_the_float`, `test_setup_tiles_follow_the_spec_ordering_keys_exactly` (the EXPECTED pin, unchanged),
  `test_order_note_served_on_the_squeeze_sub_only`, `test_suspect_ineligible_float_sorts_last`, and no `_float_shares`
  in any served tile.
- `test_gajjala_potential.py` / `test_gajjala_potential_tab.py` — the `four_bar_flag` fixture is now a potential (WIDENED,
  dated); a synthetic future forming variant still reads None.
- `test_gajjala_playbook.py` / `test_rules_info_gajjala.py` — the K4 line with and without "long flag".
- Synthetic `long_flag` variants in `test_gajjala_on_open.py`, `test_gajjala_tab.py`, `test_gajjala_alerts.py` stay
  (the variant mechanism is what they test) with a dated comment.

Frontend: `GajjalaBoard` `gg-order-note` rendered verbatim, absent on null (NEGATIVE), an unknown word printed as served;
`Notifications.gajjala_setup.test.tsx` / `Notifications.gajjala_potential.test.tsx` — no "long flag" (NEGATIVE);
`scripts/contracts.mjs` block "🚩 K4 long flags + 🎾 float order (2026-10-18)"; two ✨ entries first
(`chart-maps-gajjala-float-sort-2026-10-18`, then `chart-maps-gajjala-long-flags-2026-10-18`).

Goldens (regenerated by the recipe, never hand-edited; the potential golden changes on its 4-bar flag), from the
worktree root:

```bash
/usr/bin/find backend -name __pycache__ -type d -prune -exec rm -rf {} +
docker run --rm --network none --name cheetah-tmp-pytest-k4-a-golden -v /Users/ajay/clinet-test/wt-ggcharts:/repo -w /repo/backend -e PYTHONDONTWRITEBYTECODE=1 -e GG_WRITE_GOLDEN=1 cheetah-api:latest python -m pytest -q -p no:cacheprovider tests/test_gajjala_on_open.py tests/test_gajjala_potential_tab.py tests/test_gajjala_track_record_tab.py -k golden
docker run --rm --network none --name cheetah-tmp-pytest-k4-a-golden2 -v /Users/ajay/clinet-test/wt-ggcharts:/repo -w /repo/backend -e PYTHONDONTWRITEBYTECODE=1 cheetah-api:latest python -m pytest -q -p no:cacheprovider tests/test_gajjala_on_open.py tests/test_gajjala_potential_tab.py tests/test_gajjala_track_record_tab.py -k golden
```

Deploy (detectors / tab / alerts are cron code too):

```bash
./deploy-cheetah-main.sh api frontend cron
```

## HIS CALL

- **Q1** — float order within the state bands (the DEFAULT, `RS_FLOAT_SORT = "within_state"`) or above them (`"global"`).
- **Q2** — float order on the other subs (their tiles serve no float today).
- **Q3** — drop the retired "long flag" fallback word from the FE map `GG_VARIANT_LABEL`.
- **Q4** — re-replay 2026-10-09 / 2026-10-12 into `gajjala_replay` with the new K4 (the ⏪ line would gain the 4–5 bar
  flags).
- **Q5** — `K4_VCP_MIN_CYCLES = 2` (one shrink) — still open from the 2026-10-17 audit.
- **Q6** — extended-hours EMAs — still open from the audit (the Substack images support it, no sentence states it).

## UNMEASURED

UNMEASURED — his setup, not a buy signal. 4–5 bar flags are A+ on Ajay's call of 2026-10-18; the float order is a
display order. The 2026-10-14 study read NULL; the study measured 1–3 bar flags; the 4–5 bar A+ reads were never
measured.
