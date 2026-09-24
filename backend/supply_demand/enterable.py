"""🎯 ENTERABLE read — one kind-aware verdict for "is this name enterable right now".

THE ASK (Ajay 2026-09-15, verbatim): *"We really need to figure out the entries,
I only wanna see the stocks that are enterable. i don't know if its volume burst
or candle stick patterns we need to read. Research the best strategy and make
sure its applicable across all chart maps. I do not want to see not enterable
alerts or stocks in any of the chart maps. ... look for any good tested entry
methods or strategies and apply them. across board.."*

WHAT THIS MODULE IS. A READ and a FILTER. It buys nothing, sizes nothing and
enters no lane. Every input it grades is a gate or a measurement that already
shipped:

  * the two STANDING push gates — `alert_gates.room_gate` (>= ALERT_MIN_ROOM_PCT
    to the first proven lid) and `alert_gates.demand_proximity_gate` (at the
    band, at most ALERT_MAX_ABOVE_DEMAND_PCT above its top);
  * the ONE measured separator — the band floor held
    (`alert_gates.FLOOR_HELD_STATES`, +8.3..+8.6pp on two independent studies),
    read through the one floor adapter (`intact_read`);
  * the two measured DRAGS from the 2026-09-08 autopsy of his own 286 pushes —
    `premarket_entry.approach_drag` (the reclaim from below) and
    `premarket_entry.day_change_drag` (the -3..-8% day);
  * the shipped grader itself — `premarket_entry.grade_row`. There is no second
    READY/WATCH/BLOCKED machine in the repo.

NOT ONE THRESHOLD IS TYPED HERE. Every number comes in by name from
`alert_gates` or `premarket_entry`; the floor states come from the enforcing
tuple, never from a state word written into this file.

THE STUDY SLOT. `MEASURED` holds the entry-TIMING measurement
(`backend/scripts/entry_trigger_study.py`): does a trigger or a confirmation
inside the episode lift the read? It is `pending` until that replay lands, and
`pending` is treated exactly like `no_signal` — the verdict is the standing
gates and the two drags, nothing is scored, nothing is quoted. If a convention
survives the study's selection rule, the paste sets `MEASURED["survivor"]` and
`survivor_read()` replays THE STUDY'S OWN `event_at` + `trigger_*` on the doc's
CLOSED bars, so the live read and the measurement can never be two definitions.

KIND-AWARE. Demand rows use the demand read; 🚀 supply-break rows use the room
to the NEXT lid (`next_lids`, the one overhead list in the repo); tabs whose
rows are not demand reversals at all carry no verdict and say so — they are
never silently hidden.

Docs: `docs/supply_demand/enterable.md`. S/D scope — no book, no cites, not
advice. "Reversal" is the word on every surface he reads.
"""
from __future__ import annotations

import logging
import math
from typing import Optional

from supply_demand import alert_gates as AG
from supply_demand import premarket_entry as PE

log = logging.getLogger(__name__)

# Price structure only — no book behind any of this (the `explosive` / `amd` /
# `keltner` precedent in this package).
CITED = False

STATUS_SEPARATES = "separates"
STATUS_NO_SIGNAL = "no_signal"
STATUS_PENDING = "pending"

# ── the measurement, in exactly one place ───────────────────────────────────
# Pasted verbatim from `entry_trigger_study.py --stage stats --emit-measured`
# beside `backend/scripts/entry_trigger_measured.json`, pinned equal by
# `test_measured_dict_equals_the_shipped_json`. PENDING until the replay lands.
MEASURED = {
    'base': {'N': {'R20': 0.30238249395882816,
           'R20_median': -1.0,
           'R20_trim': -0.046390360306308595,
           'clear_pct': 12.31428072015382,
           'd_risk': 0.0,
           'hit5_10': 33.01433315853872,
           'hit5_20': 35.00262191924489,
           'hit5_5': 27.744275476315327,
           'hit5b_20': 34.77101905261318,
           'hit5c_20': 28.574549903862962,
           'hit_lid_20': 22.798316801923654,
           'n_dates': 361,
           'n_ep': 22884,
           'n_ev': 92732,
           'n_lid': 19962,
           'risk_pct': 2.9920572786789243,
           'room_pct': 15.432690560157221,
           'room_risk': 5.157886070607304,
           'stop_20': 72.20765600419507,
           'tgt_stop_clk': '20/72/8',
           'win20': 26.68239818213599},
     'P': {'R20': 0.2879530525330524,
           'R20_median': -1.0,
           'R20_trim': 0.06720251201730648,
           'clear_pct': 11.957306797207288,
           'd_risk': 0.0,
           'hit5_10': 32.60171735815745,
           'hit5_20': 34.19468742476527,
           'hit5_5': 28.47283524596742,
           'hit5b_20': 31.927614156167245,
           'hit5c_20': 27.81478212021507,
           'hit_lid_20': 21.151216844407987,
           'n_dates': 361,
           'n_ep': 24922,
           'n_ev': 92732,
           'n_lid': 21942,
           'risk_pct': 2.565997858550368,
           'room_pct': 15.630916795023348,
           'room_risk': 6.091554886898409,
           'stop_20': 74.48037878179922,
           'tgt_stop_clk': '19/74/7',
           'win20': 24.861568092448437},
     'PC': {'R20': 0.2879530525330524,
            'R20_median': -1.0,
            'R20_trim': 0.06720251201730648,
            'clear_pct': 11.957306797207288,
            'd_risk': 0.0,
            'hit5_10': 32.60171735815745,
            'hit5_20': 34.19468742476527,
            'hit5_5': 28.47283524596742,
            'hit5b_20': 31.927614156167245,
            'hit5c_20': 27.81478212021507,
            'hit_lid_20': 21.151216844407987,
            'n_dates': 361,
            'n_ep': 24922,
            'n_ev': 92732,
            'n_lid': 21942,
            'risk_pct': 2.565997858550368,
            'room_pct': 15.630916795023348,
            'room_risk': 6.091554886898409,
            'stop_20': 74.48037878179922,
            'tgt_stop_clk': '19/74/7',
            'win20': 24.861568092448437}},
    'c1_window_sweep': {'1': {'hit5_20': 52.124645892351275,
           'n_fired': 4589,
           'n_no_bars': 13,
           'note': 'printed, never scored; no_bars rows excluded as conventions.C1 does'},
     '2': {'hit5_20': 53.13832132882552,
           'n_fired': 6803,
           'n_no_bars': 19,
           'note': 'printed, never scored; no_bars rows excluded as conventions.C1 does'},
     '3': {'hit5_20': 53.55510411376333,
           'n_fired': 7876,
           'n_no_bars': 26,
           'note': 'printed, never scored; no_bars rows excluded as conventions.C1 does'},
     '5': {'hit5_20': 53.747735507246375,
           'n_fired': 8832,
           'n_no_bars': 33,
           'note': 'printed, never scored; no_bars rows excluded as conventions.C1 does'}},
    'clocks': [5, 10, 20],
    'cohort_note': ("bouncing EPISODES at board demand bands; every convention keeps the event's own band, "
     'stop and target and moves only the ENTRY; outcomes walk from the ENTRY bar; no costs; PC '
     'is print-only'),
    'conventions': {'C1': {'R20': 0.052543885569851886,
            'R20_median': -0.07592241257197815,
            'R20_trim': -0.008680110988062753,
            'ci_cond': [5.747157404514597, 8.362431381474117],
            'ci_paired': [-26.457186234013875, -23.23148293551089],
            'ci_policy_R': [-0.38001184347771205, -0.16836206460785547],
            'ci_raw': [16.86022148516582, 21.992800884372045],
            'ci_rw': [-4.824585323267355, 1.0715336875128663],
            'ci_stop_cond': [-15.355625599008954, -12.974447463005024],
            'conditions': {'a_cond_beats_mdl': True,
                           'b_stop_not_raised': True,
                           'c_reweighted_sign': False,
                           'd_policy_not_worse': False,
                           'e_one_per_date_symbol': True,
                           'f_all_three_splits': True},
            'contrast': 'fired vs unfired survivors at the same bar',
            'd_cond': 7.03136283156719,
            'd_cond_reweighted': -1.9011978555472002,
            'd_delay_only': {'1': 10.416508537782043,
                             '2': 14.126802406158523,
                             '3': 16.799189164966243},
            'd_paired': -24.74606399187405,
            'd_policy_R': -0.27134781849292106,
            'd_policy_R_vs_delay': -0.08396020814483288,
            'd_raw': 19.36041668899806,
            'd_stop_cond': -14.135059844158029,
            'decomp_gap': 0.0,
            'dropped_k': [],
            'fire_bar_dist': {'1': 4589, '2': 2214, '3': 1073},
            'fire_rate': 0.3160260011235053,
            'hit5_20': 53.55510411376333,
            'hit_lid_20': 47.57957559681697,
            'mdl_cond': 0.9344867127664391,
            'mdl_paired': 1.6045972721525974,
            'n_base': 24922,
            'n_base_k': {'1': 15059, '2': 12243, '3': 10615},
            'n_fired': 7876,
            'n_lid': 6032,
            'n_skipped': {'floor_broke_before_trigger': 13459,
                          'no_bars': 26,
                          'no_trigger': 3561},
            'one_per_date': 5.872894735953909,
            'one_per_symbol': 8.678818293910053,
            'policy_R20': 0.016605234040131346,
            'policy_R20_P': 0.2879530525330524,
            'pooled_k': [1, 2, 3],
            'raw_note': 'includes survival to bar k (not a trigger effect)',
            'risk_pct': 6.944812280086864,
            'room_pct': 11.419205533497895,
            'room_risk': 1.6442785021332595,
            'splits': {'s1': {'ci_cond': [7.248690185723383, 10.376695046379334],
                              'd_cond': 8.79254367848917,
                              'd_policy_R': -0.2642953466500135,
                              'mdl_cond': 1.4531744164815628,
                              'n_scored': 12235,
                              'name': 's1 date H2 (score H2)',
                              'verdict': 'separates'},
                       's2': {'ci_cond': [3.7082266148118292, 7.454785725079208],
                              'd_cond': 5.537565662838809,
                              'd_policy_R': -0.2781490317819551,
                              'mdl_cond': 1.2953105279493333,
                              'n_scored': 12687,
                              'name': 's2 date H1 (score H1)',
                              'verdict': 'separates'},
                       's3': {'ci_cond': [5.973195181036347, 9.068853870393575],
                              'd_cond': 7.451362394356041,
                              'd_policy_R': -0.25245597700777805,
                              'mdl_cond': 1.2386067560182572,
                              'n_scored': 12769,
                              'name': 's3 symbol parity 1',
                              'verdict': 'separates'}},
            'stop_20': 40.667851701371255,
            'verdict': 'no_signal',
            'window_bars': 3},
     'C2': {'R20': 0.08866434211009341,
            'R20_median': -0.2039669490290737,
            'R20_trim': 0.011369782183297523,
            'c2_na': 6778,
            'ci_cond': [4.998591709879012, 7.599973930925566],
            'ci_paired': [-26.81066252999219, -23.591006009154043],
            'ci_policy_R': [-0.3731011516570099, -0.16209082245057382],
            'ci_raw': [15.61845166622292, 20.445824802758857],
            'ci_rw': [-3.144876824124507, 2.7190907565952824],
            'ci_stop_cond': [-11.259192876045086, -9.022740889154262],
            'conditions': {'a_cond_beats_mdl': True,
                           'b_stop_not_raised': True,
                           'c_reweighted_sign': False,
                           'd_policy_not_worse': False,
                           'e_one_per_date_symbol': True,
                           'f_all_three_splits': True},
            'contrast': 'fired vs unfired survivors at the same bar',
            'd_cond': 6.319379138469067,
            'd_cond_reweighted': -0.21127476829067576,
            'd_delay_only': {'1': 10.416508537782043,
                             '2': 14.126802406158523,
                             '3': 16.799189164966243},
            'd_paired': -25.173960105149217,
            'd_policy_R': -0.26494557719295236,
            'd_policy_R_vs_delay': -0.0842067734977638,
            'd_raw': 18.008807240458168,
            'd_stop_cond': -10.138856727983745,
            'decomp_gap': -5.329070518200751e-15,
            'dropped_k': [],
            'fire_bar_dist': {'1': 4589, '2': 1405, '3': 473},
            'fire_rate': 0.259489607575636,
            'hit5_20': 52.20349466522344,
            'hit_lid_20': 45.78858111927643,
            'mdl_cond': 1.0656855146644746,
            'mdl_paired': 1.5932677176437469,
            'n_base': 24922,
            'n_base_k': {'1': 15059, '2': 12243, '3': 10615},
            'n_fired': 6467,
            'n_lid': 5307,
            'n_skipped': {'c2_na': 6778,
                          'floor_broke_before_trigger': 10475,
                          'no_bars': 18,
                          'no_trigger': 1184},
            'one_per_date': 4.791708629106126,
            'one_per_symbol': 8.007910876426608,
            'policy_R20': 0.023007475340100076,
            'policy_R20_P': 0.2879530525330524,
            'pooled_k': [1, 2, 3],
            'raw_note': 'includes survival to bar k (not a trigger effect)',
            'risk_pct': 6.021509742603564,
            'room_pct': 12.468803639689314,
            'room_risk': 2.070710531524954,
            'splits': {'s1': {'ci_cond': [3.9679033557869663, 7.611146875418566],
                              'd_cond': 5.8432409174204825,
                              'd_policy_R': -0.27107076447843254,
                              'mdl_cond': 1.5717218777110242,
                              'n_scored': 12235,
                              'name': 's1 date H2 (score H2)',
                              'verdict': 'separates'},
                       's2': {'ci_cond': [4.940938678229212, 8.573663799448067],
                              'd_cond': 6.739281888423969,
                              'd_policy_R': -0.25903861207607287,
                              'mdl_cond': 1.5233048919469094,
                              'n_scored': 12687,
                              'name': 's2 date H1 (score H1)',
                              'verdict': 'separates'},
                       's3': {'ci_cond': [5.011602539520836, 8.066370386733182],
                              'd_cond': 6.550059036369629,
                              'd_policy_R': -0.24481573131427903,
                              'mdl_cond': 1.474011464559468,
                              'n_scored': 12769,
                              'name': 's3 symbol parity 1',
                              'verdict': 'separates'}},
            'stop_20': 46.01824648214009,
            'verdict': 'no_signal',
            'window_bars': 3},
     'D1': {'R20': 0.19705726332604115,
            'R20_median': -1.0,
            'R20_trim': 0.04139924843268675,
            'ci_cond': [None, None],
            'ci_paired': [-12.983064727810351, -10.785203181368745],
            'ci_policy_R': [-0.26601273276654386, -0.07764740770247758],
            'ci_raw': [8.625582242938757, 12.203834896758451],
            'ci_rw': [None, None],
            'ci_stop_cond': [None, None],
            'conditions': {'a_paired_beats_mdl': False,
                           'd_policy_not_worse': False,
                           'f_all_three_splits': False},
            'contrast': 'unconditional delay — kept == base by construction',
            'd_cond': None,
            'd_cond_reweighted': None,
            'd_delay_only': {},
            'd_paired': -11.873298359784847,
            'd_policy_R': -0.16888213814308156,
            'd_policy_R_vs_delay': None,
            'd_raw': 10.416508537782043,
            'd_stop_cond': None,
            'decomp_gap': None,
            'fire_bar_dist': {'1': 15059},
            'fire_rate': 0.6042452451649145,
            'hit5_20': 44.61119596254731,
            'hit_lid_20': 33.43240420917343,
            'mdl_cond': None,
            'mdl_paired': 1.0979231688940583,
            'n_base': 24922,
            'n_fired': 15059,
            'n_lid': 12449,
            'n_skipped': {'no_bars': 35, 'stopped_before_entry': 9828},
            'one_per_date': None,
            'one_per_symbol': None,
            'policy_R20': 0.11907091438997086,
            'policy_R20_P': 0.2879530525330524,
            'raw_note': 'includes survival to bar k (not a trigger effect)',
            'risk_pct': 4.4331952878379,
            'room_pct': 13.185951089200968,
            'room_risk': 2.974367297866512,
            'splits': {'s1': {'ci_cond': [None, None],
                              'ci_paired': [-13.941337580871341, -11.082591998201048],
                              'd_cond': None,
                              'd_paired': -12.519190509420797,
                              'd_policy_R': -0.15722275698443458,
                              'mdl_cond': None,
                              'mdl_paired': 1.4165189666524423,
                              'n_scored': 12235,
                              'name': 's1 date H2 (score H2)',
                              'verdict': 'no_signal'},
                       's2': {'ci_cond': [None, None],
                              'ci_paired': [-13.019121670057899, -9.685574672420923],
                              'd_cond': None,
                              'd_paired': -11.287053458322777,
                              'd_policy_R': -0.18012613029851987,
                              'mdl_cond': None,
                              'mdl_paired': 1.6878428645535957,
                              'n_scored': 12687,
                              'name': 's2 date H1 (score H1)',
                              'verdict': 'no_signal'},
                       's3': {'ci_cond': [None, None],
                              'ci_paired': [-12.765811637241692, -10.365284091323431],
                              'd_cond': None,
                              'd_paired': -11.548420507509062,
                              'd_policy_R': -0.15379926173654485,
                              'mdl_cond': None,
                              'mdl_paired': 1.2009306157036317,
                              'n_scored': 12769,
                              'name': 's3 symbol parity 1',
                              'verdict': 'no_signal'}},
            'stop_20': 58.841888571618306,
            'verdict': 'no_signal',
            'window_bars': None},
     'D2': {'R20': 0.18341485000909674,
            'R20_median': -1.0,
            'R20_trim': -0.003960136951514501,
            'ci_cond': [None, None],
            'ci_paired': [-19.764919903039775, -16.736351358690374],
            'ci_policy_R': [-0.3143826162253023, -0.08308592654229449],
            'ci_raw': [11.824440653141348, 16.3907948917805],
            'ci_rw': [None, None],
            'ci_stop_cond': [None, None],
            'conditions': {'a_paired_beats_mdl': False,
                           'd_policy_not_worse': False,
                           'f_all_three_splits': False},
            'contrast': 'unconditional delay — kept == base by construction',
            'd_cond': None,
            'd_cond_reweighted': None,
            'd_delay_only': {},
            'd_paired': -18.21448991260312,
            'd_policy_R': -0.19785001069606617,
            'd_policy_R_vs_delay': None,
            'd_raw': 14.126802406158523,
            'd_stop_cond': None,
            'decomp_gap': None,
            'fire_bar_dist': {'2': 12243},
            'fire_rate': 0.4912527084503651,
            'hit5_20': 48.321489830923795,
            'hit_lid_20': 38.46879916098584,
            'mdl_cond': None,
            'mdl_paired': 1.503976689392822,
            'n_base': 24922,
            'n_fired': 12243,
            'n_lid': 9535,
            'n_skipped': {'no_bars': 46, 'stopped_before_entry': 12633},
            'one_per_date': None,
            'one_per_symbol': None,
            'policy_R20': 0.09010304183698624,
            'policy_R20_P': 0.2879530525330524,
            'raw_note': 'includes survival to bar k (not a trigger effect)',
            'risk_pct': 5.524690260128056,
            'room_pct': 12.634523455260618,
            'room_risk': 2.2869197838011948,
            'splits': {'s1': {'ci_cond': [None, None],
                              'ci_paired': [-21.117688738698945, -17.194713427335444],
                              'd_cond': None,
                              'd_paired': -19.101123595505616,
                              'd_policy_R': -0.22993290875455108,
                              'mdl_cond': None,
                              'mdl_paired': 1.9389400490829531,
                              'n_scored': 12235,
                              'name': 's1 date H2 (score H2)',
                              'verdict': 'no_signal'},
                       's2': {'ci_cond': [None, None],
                              'ci_paired': [-19.69386742516494, -15.220542002412623],
                              'd_cond': None,
                              'd_paired': -17.420253948590894,
                              'd_policy_R': -0.16691013068143995,
                              'mdl_cond': None,
                              'mdl_paired': 2.2236043041519693,
                              'n_scored': 12687,
                              'name': 's2 date H1 (score H1)',
                              'verdict': 'no_signal'},
                       's3': {'ci_cond': [None, None],
                              'ci_paired': [-19.642919638690753, -16.403446700811696],
                              'd_cond': None,
                              'd_paired': -18.001598721023182,
                              'd_policy_R': -0.20170201659416076,
                              'mdl_cond': None,
                              'mdl_paired': 1.619452118817193,
                              'n_scored': 12769,
                              'name': 's3 symbol parity 1',
                              'verdict': 'no_signal'}},
            'stop_20': 51.05774728416238,
            'verdict': 'no_signal',
            'window_bars': None},
     'D3': {'R20': 0.10097739583426754,
            'R20_median': -0.3138514314909766,
            'R20_trim': -0.021623407218047334,
            'ci_cond': [None, None],
            'ci_paired': [-23.589667083354083, -20.654165329943115],
            'ci_policy_R': [-0.35846743314272167, -0.1366065374734146],
            'ci_raw': [14.518189035559434, 19.12587426354293],
            'ci_rw': [None, None],
            'ci_stop_cond': [None, None],
            'conditions': {'a_paired_beats_mdl': False,
                           'd_policy_not_worse': False,
                           'f_all_three_splits': False},
            'contrast': 'unconditional delay — kept == base by construction',
            'd_cond': None,
            'd_cond_reweighted': None,
            'd_delay_only': {},
            'd_paired': -22.100800753650496,
            'd_policy_R': -0.24494386158606782,
            'd_policy_R_vs_delay': None,
            'd_raw': 16.799189164966243,
            'd_stop_cond': None,
            'decomp_gap': None,
            'fire_bar_dist': {'3': 10615},
            'fire_rate': 0.42592889816226626,
            'hit5_20': 50.993876589731514,
            'hit_lid_20': 41.863147104049204,
            'mdl_cond': None,
            'mdl_paired': 1.4579406637353993,
            'n_base': 24922,
            'n_fired': 10615,
            'n_lid': 7804,
            'n_skipped': {'no_bars': 64, 'stopped_before_entry': 14243},
            'one_per_date': None,
            'one_per_symbol': None,
            'policy_R20': 0.0430091909469846,
            'policy_R20_P': 0.2879530525330524,
            'raw_note': 'includes survival to bar k (not a trigger effect)',
            'risk_pct': 6.4155965223440266,
            'room_pct': 12.283763188117328,
            'room_risk': 1.9146720254828753,
            'splits': {'s1': {'ci_cond': [None, None],
                              'ci_paired': [-25.382233116850383, -21.180404699974993],
                              'd_cond': None,
                              'd_paired': -23.26555023923445,
                              'd_policy_R': -0.24731628985091533,
                              'mdl_cond': None,
                              'mdl_paired': 2.095856177159659,
                              'n_scored': 12235,
                              'name': 's1 date H2 (score H2)',
                              'verdict': 'no_signal'},
                       's2': {'ci_cond': [None, None],
                              'ci_paired': [-23.204459666187947, -18.985076622489327],
                              'd_cond': None,
                              'd_paired': -21.057331666368995,
                              'd_policy_R': -0.24265595586994826,
                              'mdl_cond': None,
                              'mdl_paired': 2.095518884797553,
                              'n_scored': 12687,
                              'name': 's2 date H1 (score H1)',
                              'verdict': 'no_signal'},
                       's3': {'ci_cond': [None, None],
                              'ci_paired': [-23.399297644224617, -20.14049092058454],
                              'd_cond': None,
                              'd_paired': -21.7767151002391,
                              'd_policy_R': -0.23317223644370544,
                              'mdl_cond': None,
                              'mdl_paired': 1.6239893357388087,
                              'n_scored': 12769,
                              'name': 's3 symbol parity 1',
                              'verdict': 'no_signal'}},
            'stop_20': 45.25671219971738,
            'verdict': 'no_signal',
            'window_bars': None},
     'HL': {'R20': 0.016827720909029148,
            'R20_median': -0.0498939753024829,
            'R20_trim': -0.03703733660319125,
            'ci_cond': [6.4823524655937685, 9.532478496404998],
            'ci_paired': [-25.250719427498602, -20.56780223162211],
            'ci_policy_R': [-0.39799535574891626, -0.17503691472432295],
            'ci_raw': [20.408954429491004, 26.06552412523194],
            'ci_rw': [-4.863215417331311, 3.0941089230794487],
            'ci_stop_cond': [-17.887603004513007, -15.165276146026091],
            'conditions': {'a_cond_beats_mdl': True,
                           'b_stop_not_raised': True,
                           'c_reweighted_sign': False,
                           'd_policy_not_worse': False,
                           'e_one_per_date_symbol': True,
                           'f_all_three_splits': True},
            'contrast': 'fired vs unfired survivors at the same bar',
            'd_cond': 7.996574780376957,
            'd_cond_reweighted': -0.922484158605834,
            'd_delay_only': {'2': 14.126802406158523,
                             '3': 16.799189164966243,
                             '4': 18.555233402850057,
                             '5': 19.966200231268015,
                             '6': 20.424538542775306},
            'd_paired': -22.929720575783236,
            'd_policy_R': -0.28396590495389273,
            'd_policy_R_vs_delay': -0.060076120003075786,
            'd_raw': 23.16348361672499,
            'd_stop_cond': -16.505356218969094,
            'decomp_gap': -0.6372817815487757,
            'dropped_k': [7, 8, 9, 10],
            'fire_bar_dist': {'10': 22,
                              '2': 3225,
                              '3': 1337,
                              '4': 645,
                              '5': 292,
                              '6': 175,
                              '7': 102,
                              '8': 64,
                              '9': 43},
            'fire_rate': 0.23693925046143968,
            'hit5_20': 57.35817104149026,
            'hit_lid_20': 53.92303848075962,
            'mdl_cond': 1.2843995886262372,
            'mdl_paired': 2.363195179406383,
            'n_base': 24922,
            'n_base_k': {'1': 15059,
                         '10': 6467,
                         '2': 12243,
                         '3': 10615,
                         '4': 9473,
                         '5': 8652,
                         '6': 8010,
                         '7': 7553,
                         '8': 7141,
                         '9': 6773},
            'n_fired': 5905,
            'n_lid': 4002,
            'n_skipped': {'floor_broke_before_trigger': 15728,
                          'no_bars': 39,
                          'no_trigger': 3250},
            'one_per_date': 7.6198055885485,
            'one_per_symbol': 10.013115103922956,
            'policy_R20': 0.003987147579159665,
            'policy_R20_P': 0.2879530525330524,
            'pooled_k': [2, 3, 4, 5, 6],
            'raw_note': 'includes survival to bar k (not a trigger effect)',
            'risk_pct': 8.390392976654027,
            'room_pct': 10.993327775325508,
            'room_risk': 1.3102279959846999,
            'splits': {'s1': {'ci_cond': [7.8637330522741165, 11.716701582806468],
                              'd_cond': 9.78478430563772,
                              'd_policy_R': -0.2840028466597745,
                              'mdl_cond': 1.5629569079076429,
                              'n_scored': 12235,
                              'name': 's1 date H2 (score H2)',
                              'verdict': 'separates'},
                       's2': {'ci_cond': [4.412735005968659, 9.052774874697336],
                              'd_cond': 6.64486753013868,
                              'd_policy_R': -0.2839302793708973,
                              'mdl_cond': 1.6440159061995117,
                              'n_scored': 12687,
                              'name': 's2 date H1 (score H1)',
                              'verdict': 'separates'},
                       's3': {'ci_cond': [6.698563192634372, 10.528571233255922],
                              'd_cond': 8.581082510782272,
                              'd_policy_R': -0.26419448698420894,
                              'mdl_cond': 1.6984093725128606,
                              'n_scored': 12769,
                              'name': 's3 symbol parity 1',
                              'verdict': 'separates'}},
            'stop_20': 31.380186282811177,
            'verdict': 'no_signal',
            'window_bars': 10},
     'L1': {'R20': 0.08018198035809132,
            'R20_median': -0.27219036389945794,
            'R20_trim': 0.00531686749616626,
            'ci_cond': [5.493077393411081, 7.36748126156241],
            'ci_paired': [-23.966879458220987, -21.46470154040691],
            'ci_policy_R': [-0.35544514208357475, -0.15803125116003414],
            'ci_raw': [15.884236241130523, 20.2588058422831],
            'ci_rw': [-4.474769919589351, 4.094708155253481],
            'ci_stop_cond': [-9.75508998756732, -8.206461352868827],
            'conditions': {'a_cond_beats_mdl': True,
                           'b_stop_not_raised': True,
                           'c_reweighted_sign': False,
                           'd_policy_not_worse': False,
                           'e_one_per_date_symbol': True,
                           'f_all_three_splits': True},
            'contrast': 'fired vs unfired survivors at the same bar',
            'd_cond': 6.4019721467634465,
            'd_cond_reweighted': -0.2511211926448923,
            'd_delay_only': {'1': 10.416508537782043,
                             '2': 14.126802406158523,
                             '3': 16.799189164966243},
            'd_paired': -22.6948989412897,
            'd_policy_R': -0.2545251263665903,
            'd_policy_R_vs_delay': -0.07380224951828163,
            'd_raw': 18.076727397178903,
            'd_stop_cond': -8.968676295594086,
            'decomp_gap': -7.105427357601002e-15,
            'dropped_k': [],
            'fire_bar_dist': {'1': 7442, '2': 2149, '3': 799},
            'fire_rate': 0.4169007302784688,
            'hit5_20': 52.27141482194418,
            'hit_lid_20': 44.36619718309859,
            'mdl_cond': 0.7918267583824449,
            'mdl_paired': 1.2467355935094993,
            'n_base': 24922,
            'n_base_k': {'1': 15059, '2': 12243, '3': 10615},
            'n_fired': 10390,
            'n_lid': 8520,
            'n_skipped': {'floor_broke_before_trigger': 12672,
                          'no_bars': 28,
                          'no_trigger': 1832},
            'one_per_date': 3.7227572070010297,
            'one_per_symbol': 7.798293012638283,
            'policy_R20': 0.03342792616646211,
            'policy_R20_P': 0.2879530525330524,
            'pooled_k': [1, 2, 3],
            'raw_note': 'includes survival to bar k (not a trigger effect)',
            'risk_pct': 6.085564782697056,
            'room_pct': 12.347653587853097,
            'room_risk': 2.0290070073628814,
            'splits': {'s1': {'ci_cond': [5.683799408228181, 7.969342888722316],
                              'd_cond': 6.8093577671667465,
                              'd_policy_R': -0.257013562386794,
                              'mdl_cond': 1.0302395474135786,
                              'n_scored': 12235,
                              'name': 's1 date H2 (score H2)',
                              'verdict': 'separates'},
                       's2': {'ci_cond': [4.603812670168517, 7.452304448339335],
                              'd_cond': 5.997393308582961,
                              'd_policy_R': -0.25212534590570973,
                              'mdl_cond': 1.128044443053273,
                              'n_scored': 12687,
                              'name': 's2 date H1 (score H1)',
                              'verdict': 'separates'},
                       's3': {'ci_cond': [5.712996679189896, 7.90250431189119],
                              'd_cond': 6.778891669671117,
                              'd_policy_R': -0.23311330311146666,
                              'mdl_cond': 1.094263076514948,
                              'n_scored': 12769,
                              'name': 's3 symbol parity 1',
                              'verdict': 'separates'}},
            'stop_20': 47.21847930702599,
            'verdict': 'no_signal',
            'window_bars': 3},
     'N': {'R20': 0.30238249395882816,
           'R20_median': -1.0,
           'R20_trim': -0.046390360306308595,
           'ci_cond': [None, None],
           'ci_paired': [-2.838357499165127, -1.687961099543656],
           'ci_policy_R': [-0.25660681914950406, 0.11343526094781314],
           'ci_raw': [-2.838357499165127, -1.687961099543656],
           'ci_rw': [None, None],
           'ci_stop_cond': [None, None],
           'conditions': {'a_paired_beats_mdl': False,
                          'd_policy_not_worse': False,
                          'f_all_three_splits': False},
           'contrast': 'no fire bar — the deciding lift is the paired delta',
           'd_cond': None,
           'd_cond_reweighted': None,
           'd_delay_only': {},
           'd_paired': -2.2373710889704594,
           'd_policy_R': -0.10027289737261452,
           'd_policy_R_vs_delay': None,
           'd_raw': -2.2373710889704634,
           'd_stop_cond': None,
           'decomp_gap': None,
           'fire_bar_dist': {'1': 22884},
           'fire_rate': 0.9182248615680925,
           'hit5_20': 35.00262191924489,
           'hit_lid_20': 22.798316801923654,
           'mdl_cond': None,
           'mdl_paired': 0.5707573045523372,
           'n_base': 24922,
           'n_fired': 22884,
           'n_lid': 19962,
           'n_skipped': {'gap_N': 2038},
           'one_per_date': None,
           'one_per_symbol': None,
           'policy_R20': 0.30238249395882816,
           'policy_R20_P': 0.4026553913314427,
           'raw_note': 'includes survival to bar k (not a trigger effect)',
           'risk_pct': 2.9920572786789243,
           'room_pct': 15.083327474082425,
           'room_risk': 5.041122568596725,
           'splits': {'s1': {'ci_cond': [None, None],
                             'ci_paired': [-2.8838737409211084, -1.5192914159392374],
                             'd_cond': None,
                             'd_paired': -2.1891964047343597,
                             'd_policy_R': -0.04347796280282623,
                             'mdl_cond': None,
                             'mdl_paired': 0.6861722785208626,
                             'n_scored': 11237,
                             'name': 's1 date H2 (score H2)',
                             'verdict': 'no_signal'},
                      's2': {'ci_cond': [None, None],
                             'ci_paired': [-3.268964805959282, -1.4381481110454641],
                             'd_cond': None,
                             'd_paired': -2.2838499184339316,
                             'd_policy_R': -0.15506852541079674,
                             'mdl_cond': None,
                             'mdl_paired': 0.9067916875768862,
                             'n_scored': 11647,
                             'name': 's2 date H1 (score H1)',
                             'verdict': 'no_signal'},
                      's3': {'ci_cond': [None, None],
                             'ci_paired': [-2.7694460536195975, -1.602454041156505],
                             'd_cond': None,
                             'd_paired': -2.171691364333163,
                             'd_policy_R': -0.16415071990568697,
                             'mdl_cond': None,
                             'mdl_paired': 0.5900933113122646,
                             'n_scored': 11742,
                             'name': 's3 symbol parity 1',
                             'verdict': 'no_signal'}},
           'stop_20': 72.20765600419507,
           'verdict': 'no_signal',
           'window_bars': None},
     'PC': {'R20': 0.2879530525330524,
            'R20_median': -1.0,
            'R20_trim': 0.06720251201730648,
            'ci_cond': [None, None],
            'ci_paired': [0.0, 0.0],
            'ci_policy_R': [0.0, 0.0],
            'ci_raw': [0.0, 0.0],
            'ci_rw': [None, None],
            'ci_stop_cond': [None, None],
            'conditions': {'a_paired_beats_mdl': False,
                           'd_policy_not_worse': True,
                           'f_all_three_splits': False},
            'contrast': 'no fire bar — the deciding lift is the paired delta',
            'd_cond': None,
            'd_cond_reweighted': None,
            'd_delay_only': {},
            'd_paired': 0.0,
            'd_policy_R': 0.0,
            'd_policy_R_vs_delay': None,
            'd_raw': 0.0,
            'd_stop_cond': None,
            'decomp_gap': None,
            'fire_bar_dist': {'0': 24922},
            'fire_rate': 1.0,
            'hit5_20': 34.19468742476527,
            'hit_lid_20': 21.151216844407987,
            'mdl_cond': None,
            'mdl_paired': 0.0,
            'n_base': 24922,
            'n_fired': 24922,
            'n_lid': 21942,
            'n_skipped': {},
            'one_per_date': None,
            'one_per_symbol': None,
            'policy_R20': 0.2879530525330524,
            'policy_R20_P': 0.2879530525330524,
            'raw_note': 'includes survival to bar k (not a trigger effect)',
            'risk_pct': 2.565997858550368,
            'room_pct': 15.630916795023348,
            'room_risk': 6.091554886898409,
            'splits': {'s1': {'ci_cond': [None, None],
                              'ci_paired': [0.0, 0.0],
                              'd_cond': None,
                              'd_paired': 0.0,
                              'd_policy_R': 0.0,
                              'mdl_cond': None,
                              'mdl_paired': 0.0,
                              'n_scored': 12235,
                              'name': 's1 date H2 (score H2)',
                              'verdict': 'no_signal'},
                       's2': {'ci_cond': [None, None],
                              'ci_paired': [0.0, 0.0],
                              'd_cond': None,
                              'd_paired': 0.0,
                              'd_policy_R': 0.0,
                              'mdl_cond': None,
                              'mdl_paired': 0.0,
                              'n_scored': 12687,
                              'name': 's2 date H1 (score H1)',
                              'verdict': 'no_signal'},
                       's3': {'ci_cond': [None, None],
                              'ci_paired': [0.0, 0.0],
                              'd_cond': None,
                              'd_paired': 0.0,
                              'd_policy_R': 0.0,
                              'mdl_cond': None,
                              'mdl_paired': 0.0,
                              'n_scored': 12769,
                              'name': 's3 symbol parity 1',
                              'verdict': 'no_signal'}},
            'stop_20': 74.48037878179922,
            'verdict': 'no_signal',
            'window_bars': None}},
    'counters': {'band_mismatch': 0, 'no_band': 0, 'no_bar': 0, 'no_frame': 0},
    'delays': {'1': {'R20': 0.19705726332604115,
           'ci': [8.625582242938757, 12.203834896758451],
           'd_delay_only': 10.416508537782043,
           'hit5_20': 44.61119596254731,
           'n_fired': 15059,
           'policy_R20': 0.11907091438997086,
           'stop_20': 58.841888571618306},
     '10': {'R20': -0.05300686253536941,
            'ci': [17.437212504172262, 24.484140826208524],
            'd_delay_only': 20.97772636833818,
            'hit5_20': 55.172413793103445,
            'n_fired': 6467,
            'policy_R20': -0.01375472995811869,
            'stop_20': 26.28730477810422},
     '2': {'R20': 0.18341485000909674,
           'ci': [11.824440653141348, 16.3907948917805],
           'd_delay_only': 14.126802406158523,
           'hit5_20': 48.321489830923795,
           'n_fired': 12243,
           'policy_R20': 0.09010304183698624,
           'stop_20': 51.05774728416238},
     '3': {'R20': 0.10097739583426754,
           'ci': [14.518189035559434, 19.12587426354293],
           'd_delay_only': 16.799189164966243,
           'hit5_20': 50.993876589731514,
           'n_fired': 10615,
           'policy_R20': 0.0430091909469846,
           'stop_20': 45.25671219971738},
     '4': {'R20': 0.06911765840602396,
           'ci': [15.96440095685036, 21.17681957371024],
           'd_delay_only': 18.555233402850057,
           'hit5_20': 52.74992082761533,
           'n_fired': 9473,
           'policy_R20': 0.026272031862621982,
           'stop_20': 40.64182413174285},
     '5': {'R20': 0.021724437905320023,
           'ci': [17.342437725258577, 22.719497907149165],
           'd_delay_only': 19.966200231268015,
           'hit5_20': 54.16088765603328,
           'n_fired': 8652,
           'policy_R20': 0.0075419242740080595,
           'stop_20': 37.10124826629681},
     '6': {'R20': 0.007102862684155324,
           'ci': [17.723405322819154, 23.279479814986203],
           'd_delay_only': 20.424538542775306,
           'hit5_20': 54.61922596754057,
           'n_fired': 8010,
           'policy_R20': 0.0022828797889448745,
           'stop_20': 33.95755305867665},
     '7': {'R20': -0.025419473666509786,
           'ci': [17.47157307274569, 23.76911529834495],
           'd_delay_only': 20.63120956980642,
           'hit5_20': 54.825896994571686,
           'n_fired': 7553,
           'policy_R20': -0.007703767137595234,
           'stop_20': 32.000529590891034},
     '8': {'R20': -0.004717849317430061,
           'ci': [17.15191344780713, 23.804031607312506],
           'd_delay_only': 20.503534112834508,
           'hit5_20': 54.69822153759978,
           'n_fired': 7141,
           'policy_R20': -0.0013518241704425016,
           'stop_20': 29.75773701162302},
     '9': {'R20': -0.009799997087524041,
           'ci': [16.729436419280038, 23.886124735502765],
           'd_delay_only': 20.330633703242995,
           'hit5_20': 54.525321128008265,
           'n_fired': 6773,
           'policy_R20': -0.0026633247842789637,
           'stop_20': 27.8458585560313}},
    'fallback': 'P — enter at the print; the READY read is unchanged',
    'feature_notes': {},
    'floor': 120,
    'hold': 20,
    'intact_reconcile': {'d_hit5_P': 8.297637442664257, 'expected_2026_09_15': 8.3, 'n_intact': 7166},
    'interactions': [{'cell': 'yes',
      'ci_cond': [9.65171791806059, 20.089171357765604],
      'd_cond': 14.72514577585493,
      'hit5_20': 49.727767695099814,
      'n': 551,
      'name': 'intact x gap_up_next=yes',
      'stop_20': 42.46823956442831,
      'verdict': 'cushion'},
     {'cell': 'yes',
      'ci_cond': [6.378732662844023, 13.107830500253398],
      'd_cond': 9.65296002849858,
      'hit5_20': 44.655581947743464,
      'n': 1684,
      'name': 'not-intact x gap_up_next=yes',
      'stop_20': 57.779097387173394,
      'verdict': 'cushion'},
     {'cell': 'fired',
      'ci_cond': [5.454116701042014, 9.821017103758473],
      'ci_rw': [-5.955074930050445, 3.5944324865656228],
      'd_cond': 7.566193610946637,
      'd_cond_reweighted': -1.2906158092993256,
      'hit5_20': 56.060606060606055,
      'n': 2574,
      'name': 'intact x fired_C1',
      'verdict': 'not selected'},
     {'cell': 'fired',
      'ci_cond': [5.736305508265375, 8.46113606529896],
      'ci_rw': [-5.666192516371431, 1.4826372550899025],
      'd_cond': 7.037676090509756,
      'd_cond_reweighted': -2.0647705520182624,
      'hit5_20': 52.3387400980762,
      'n': 5302,
      'name': 'not-intact x fired_C1',
      'verdict': 'not selected'}],
    'liquidity_control': {'R20': 0.277424791518337,
     'hit5_20': 34.88873435326843,
     'min_dvol': 10000000.0,
     'n': 14380,
     'stop_20': 73.11543810848401},
    'min_cell_n': 120,
    'min_dvol_filter': 0.0,
    'n_dates': 361,
    'n_episodes': 24922,
    'n_episodes_N': 22884,
    'n_events_all': 157894,
    'n_events_bouncing': 92732,
    'n_feature_nan': {'above_sma200_pre': 42698,
     'above_sma50_pre': 0,
     'body_at': 192,
     'close_gt_prev_high_at': 0,
     'close_pos_at': 192,
     'engulf_at': 0,
     'gap_up_next': 0,
     'inside_at': 0,
     'intact_at': 0,
     'lower_wick_at': 192,
     'rs20_pre': 0,
     'rvol20_at': 0,
     'rvol20_pre': 0,
     'rvol50_pre': 0,
     'up_close_at': 0,
     'updn_vol10_pre': 58,
     'weak_day_at': 0},
    'n_names': 3585,
    'n_names_universe': 3716,
    'per_feature': [{'convention': 'P',
      'kind': 'num',
      'name': 'rvol20_pre',
      'orientation': -1,
      'ship_eligible': True,
      'top': {'ci': [-1.960487804857651, 1.0767298163628625],
              'ci_R': [-0.03969674148076576, 0.172392101576917],
              'ci_rw': [-2.913377270626926, 0.7991687671318128],
              'ci_stop': [-0.25061595374067075, 2.777732574660118],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': False,
                             'room_risk_kept': True,
                             'stop_not_raised': True},
              'd_R': 0.06433165358057197,
              'd_hit5': -0.41334339266898,
              'd_hit5_reweighted': -1.0285842997261188,
              'd_risk': 0.04049026917268472,
              'd_stop': 1.2468027628346867,
              'label': 'Q1',
              'n': 4985,
              'one_per_date': -4.528584325496338,
              'one_per_symbol': 5.125738687831605,
              'p_le0': 0.7014,
              'perm_p': 0.7355,
              'placebo_dates': [30.791374122367106, 37.57372116349047],
              'placebo_iid': [33.17853560682046, 35.16549648946841],
              'room_risk': 7.685573989468171,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'P',
      'kind': 'num',
      'name': 'rvol50_pre',
      'orientation': -1,
      'ship_eligible': True,
      'top': {'ci': [-1.0716254709910038, 1.6373156160249935],
              'ci_R': [-0.008774078622613295, 0.2172289423820379],
              'ci_rw': [-1.7262228495131773, 1.631269756666123],
              'ci_stop': [-0.10538798125434733, 2.4992799209787324],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': False,
                             'room_risk_kept': True,
                             'stop_not_raised': True},
              'd_R': 0.10146246362825945,
              'd_hit5': 0.2887629262878888,
              'd_hit5_reweighted': -0.046493500414994955,
              'd_risk': 0.025109991296670575,
              'd_stop': 1.1465018601265586,
              'label': 'Q1',
              'n': 4985,
              'one_per_date': -4.250032793462916,
              'one_per_symbol': 6.063085275951385,
              'p_le0': 0.349,
              'perm_p': 0.319,
              'placebo_dates': [30.791374122367106, 37.57372116349047],
              'placebo_iid': [33.17853560682046, 35.16549648946841],
              'room_risk': 8.11917186132261,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'P',
      'kind': 'num',
      'name': 'updn_vol10_pre',
      'orientation': -1,
      'ship_eligible': True,
      'top': {'ci': [0.07944646271740882, 3.096851910578598],
              'ci_R': [-0.023715961227922442, 0.16303507148235483],
              'ci_rw': [0.02579478232368788, 3.7490088427057],
              'ci_stop': [-2.1529591729211393, 0.48325103677793485],
              'conditions': {'ci_excludes_0': True,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': True},
              'd_R': 0.06596477660664607,
              'd_hit5': 1.586970211197003,
              'd_hit5_reweighted': 1.8802744278036447,
              'd_risk': 0.0001387529815755073,
              'd_stop': -0.8299673830434506,
              'label': 'Q1',
              'n': 4983,
              'one_per_date': -1.841335795629423,
              'one_per_symbol': 6.376535123975701,
              'p_le0': 0.02,
              'perm_p': 0.004,
              'placebo_dates': [30.98334336744933, 37.68813967489464],
              'placebo_iid': [33.1717840658238, 35.15954244431065],
              'room_risk': 6.291932314177192,
              'room_risk_base': 6.091554886898409,
              'verdict': 'selects wider stops'}},
     {'convention': 'P',
      'kind': 'bool',
      'name': 'above_sma50_pre',
      'orientation': -1,
      'ship_eligible': True,
      'top': {'ci': [-0.5997769648506851, 1.2897566516328656],
              'ci_R': [0.028291203098044306, 0.15050850286574632],
              'ci_rw': [0.23067047852085143, 4.649703027388026],
              'ci_stop': [0.11583091770898087, 1.799528999697466],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': False},
              'd_R': 0.08477535094318,
              'd_hit5': 0.3172856882441122,
              'd_hit5_reweighted': 2.3956659293562046,
              'd_risk': -0.11211303875545209,
              'd_stop': 0.9712386387301208,
              'label': 'no',
              'n': 14282,
              'one_per_date': -2.770083102493076,
              'one_per_symbol': 2.3606048804518998,
              'p_le0': 0.2522,
              'perm_p': 0.119,
              'placebo_dates': [32.810530737991876, 35.681977314101665],
              'placebo_iid': [33.78378378378378, 34.61700042010923],
              'room_risk': 7.051741355400422,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'num',
      'name': 'rvol20_pre',
      'orientation': -1,
      'ship_eligible': True,
      'top': {'ci': [-1.2013858346310813, 1.8266638474779349],
              'ci_R': [-0.297096166405822, 0.1081778458791194],
              'ci_rw': [-1.7559204908902775, 1.7627888965891958],
              'ci_stop': [-0.7133871658150376, 2.4270323749413287],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': True,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': True},
              'd_R': -0.06764406823437866,
              'd_hit5': 0.32619608381388443,
              'd_hit5_reweighted': 0.02590152736727724,
              'd_risk': 0.02476135366703991,
              'd_stop': 0.8533009545115045,
              'label': 'Q1',
              'n': 4577,
              'one_per_date': 1.689131679536976,
              'one_per_symbol': 4.230531078828292,
              'p_le0': 0.3496,
              'perm_p': 0.322,
              'placebo_dates': [32.073410530915446, 37.90801835263273],
              'placebo_iid': [33.974218920690404, 36.07166266113175],
              'room_risk': 6.595881398909153,
              'room_risk_base': 5.157886070607304,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'num',
      'name': 'rvol50_pre',
      'orientation': -1,
      'ship_eligible': True,
      'top': {'ci': [-1.1126811951783868, 1.5967245664812268],
              'ci_R': [-0.29590679540226145, 0.11225496633392601],
              'ci_rw': [-1.7545207885212828, 1.5863435105337422],
              'ci_stop': [-0.3621789549095142, 2.3834558636282583],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': False,
                             'room_risk_kept': True,
                             'stop_not_raised': True},
              'd_R': -0.06679875383552697,
              'd_hit5': 0.2824993392213593,
              'd_hit5_reweighted': -0.05886640799368345,
              'd_risk': 0.0467040324254171,
              'd_stop': 0.9625428159928173,
              'label': 'Q1',
              'n': 4577,
              'one_per_date': -1.4768632474015997,
              'one_per_symbol': 3.664670658682634,
              'p_le0': 0.3458,
              'perm_p': 0.339,
              'placebo_dates': [32.073410530915446, 37.90801835263273],
              'placebo_iid': [33.974218920690404, 36.07166266113175],
              'room_risk': 6.912431347120964,
              'room_risk_base': 5.157886070607304,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'num',
      'name': 'updn_vol10_pre',
      'orientation': -1,
      'ship_eligible': True,
      'top': {'ci': [-0.5510133832341222, 2.427174574464828],
              'ci_R': [-0.16067610363270482, 0.4628170808900014],
              'ci_rw': [-1.2086540169760347, 2.4571119370512147],
              'ci_stop': [-2.0556575897921987, 0.7591889235956665],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': True},
              'd_R': 0.13487361151384325,
              'd_hit5': 0.9536622337605771,
              'd_hit5_reweighted': 0.6227040286804016,
              'd_risk': 0.05336055379561966,
              'd_stop': -0.6448144741404316,
              'label': 'Q1',
              'n': 4575,
              'one_per_date': -1.1983117153681722,
              'one_per_symbol': 3.632130808740847,
              'p_le0': 0.108,
              'perm_p': 0.07,
              'placebo_dates': [31.998907103825136, 38.05573770491804],
              'placebo_iid': [33.98907103825137, 36.0655737704918],
              'room_risk': 5.224157248604086,
              'room_risk_base': 5.157886070607304,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'bool',
      'name': 'above_sma50_pre',
      'orientation': -1,
      'ship_eligible': True,
      'top': {'ci': [-0.45838668862940857, 1.340722776568495],
              'ci_R': [-0.03913136751817331, 0.23999443187447866],
              'ci_rw': [0.34914856709239944, 4.267996005862699],
              'ci_stop': [-0.021414392810049643, 1.7626303132921344],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': True},
              'd_R': 0.08225620706609527,
              'd_hit5': 0.41516370187074103,
              'd_hit5_reweighted': 2.289385305460249,
              'd_risk': -0.07312236556636931,
              'd_stop': 0.8914002376525398,
              'label': 'no',
              'n': 13033,
              'one_per_date': -1.3850415512465353,
              'one_per_symbol': 1.6515482103894918,
              'p_le0': 0.1772,
              'perm_p': 0.0635,
              'placebo_dates': [33.68372592649428, 36.28558275147702],
              'placebo_iid': [34.5503721322796, 35.44847694314433],
              'room_risk': 5.844990016567053,
              'room_risk_base': 5.157886070607304,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'num',
      'name': 'close_pos_at',
      'orientation': -1,
      'ship_eligible': True,
      'top': {'ci': [-1.4597013536370405, 2.1932587346637247],
              'ci_R': [-0.147208232538637, 0.5158872402973181],
              'ci_rw': [-1.8916721797446343, 2.3651421746112242],
              'ci_stop': [0.28780741933279985, 3.7780009500230514],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': False},
              'd_R': 0.1635875025588296,
              'd_hit5': 0.34804445611015256,
              'd_hit5_reweighted': 0.1941830152344975,
              'd_risk': 0.07728979294423599,
              'd_stop': 2.0112646862134875,
              'label': 'Q1',
              'n': 4577,
              'one_per_date': -1.5697137580794107,
              'one_per_symbol': 2.1572573767695724,
              'p_le0': 0.361,
              'perm_p': 0.2885,
              'placebo_dates': [32.073410530915446, 37.90801835263273],
              'placebo_iid': [33.974218920690404, 36.07166266113175],
              'room_risk': 6.020418139350349,
              'room_risk_base': 5.157886070607304,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'num',
      'name': 'lower_wick_at',
      'orientation': -1,
      'ship_eligible': True,
      'top': {'ci': [-0.3246841660379272, 2.6280198196318523],
              'ci_R': [-0.21038002140840212, 0.33335925222866],
              'ci_rw': [-1.4811784418364566, 2.205781630603708],
              'ci_stop': [-1.7635186408131283, 1.3150800047938571],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': True,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': True},
              'd_R': 0.04699980860161396,
              'd_hit5': 1.1345858587756497,
              'd_hit5_reweighted': 0.3233351923155113,
              'd_risk': 0.13069056014061076,
              'd_stop': -0.19542091570916575,
              'label': 'Q1',
              'n': 4577,
              'one_per_date': 1.2080640196983683,
              'one_per_symbol': 3.4687381583933306,
              'p_le0': 0.063,
              'perm_p': 0.035,
              'placebo_dates': [32.073410530915446, 37.90801835263273],
              'placebo_iid': [33.974218920690404, 36.07166266113175],
              'room_risk': 5.452025927164322,
              'room_risk_base': 5.157886070607304,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'num',
      'name': 'body_at',
      'orientation': 1,
      'ship_eligible': True,
      'top': {'ci': [-1.4777792913373788, 1.8491113319267938],
              'ci_R': [-0.3407391353465042, 0.29138855449417683],
              'ci_rw': [-2.2463312540652267, 1.7901014054325808],
              'ci_stop': [-1.7270173968963778, 1.5835090940252472],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': False,
                             'room_risk_kept': True,
                             'stop_not_raised': True},
              'd_R': -0.04682461718780567,
              'd_hit5': 0.19510585003630343,
              'd_hit5_reweighted': -0.20343478133241902,
              'd_risk': 0.06387860174038407,
              'd_stop': -0.04248230963531663,
              'label': 'Q5',
              'n': 4577,
              'one_per_date': -1.1983117153681722,
              'one_per_symbol': 1.6737411308723804,
              'p_le0': 0.4228,
              'perm_p': 0.3905,
              'placebo_dates': [32.073410530915446, 37.90801835263273],
              'placebo_iid': [33.974218920690404, 36.07166266113175],
              'room_risk': 5.247436861938925,
              'room_risk_base': 5.157886070607304,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'bool',
      'name': 'up_close_at',
      'orientation': 1,
      'ship_eligible': True,
      'top': {'ci': [-1.1334894361698, 1.9902788844084085],
              'ci_R': [-0.3870431413096459, 0.006920511857284481],
              'ci_rw': [-2.587798849900214, 1.6464707950192239],
              'ci_stop': [-3.5375502021483567, -0.566820694235164],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': False,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': -0.1648768487266662,
              'd_hit5': 0.42798941498090604,
              'd_hit5_reweighted': -0.4865804212467241,
              'd_risk': 0.056820033810471404,
              'd_stop': -2.0752746268337785,
              'label': 'yes',
              'n': 6723,
              'one_per_date': -2.680824869190518,
              'one_per_symbol': 1.409311877713365,
              'p_le0': 0.2942,
              'perm_p': 0.1935,
              'placebo_dates': [32.649114978432245, 37.36501561802766],
              'placebo_iid': [34.22504834151421, 35.847835787594825],
              'room_risk': 4.3364697195344135,
              'room_risk_base': 5.157886070607304,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'bool',
      'name': 'close_gt_prev_high_at',
      'orientation': 1,
      'ship_eligible': True,
      'top': {'ci': [-1.7098947843182115, 3.9163009011871948],
              'ci_R': [-0.49231809374180485, -0.05433812874635889],
              'ci_rw': [-4.3843734308878695, 1.731011894562046],
              'ci_stop': [-6.816376088177667, -0.9610039585293093],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': True,
                             'outside_date_placebo': False,
                             'reweighted_sign': False,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': -0.25888961696372426,
              'd_hit5': 1.068231542912923,
              'd_hit5_reweighted': -1.333077337826124,
              'd_risk': 0.18944749922218218,
              'd_stop': -3.769652783583155,
              'label': 'yes',
              'n': 1863,
              'one_per_date': 0.940326402563163,
              'one_per_symbol': 3.0416322029225284,
              'p_le0': 0.221,
              'perm_p': 0.157,
              'placebo_dates': [30.220075147611382, 39.99194847020934],
              'placebo_iid': [33.279656468062264, 36.87600644122383],
              'room_risk': 3.8167653613763486,
              'room_risk_base': 5.157886070607304,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'bool',
      'name': 'engulf_at',
      'orientation': 1,
      'ship_eligible': True,
      'top': {'ci': [-2.6719145350806524, 9.573779206975086],
              'ci_R': [-0.5370222968266033, 0.2508885865294005],
              'ci_rw': [-6.064306457268034, 6.6206424863838],
              'ci_stop': [-11.861208462614826, -0.23749399176758407],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': True,
                             'outside_date_placebo': False,
                             'reweighted_sign': False,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': -0.15556973458632115,
              'd_hit5': 3.3307114140884497,
              'd_hit5_reweighted': -0.022592926654539918,
              'd_risk': 0.32608959460113063,
              'd_stop': -5.957656004195078,
              'label': 'yes',
              'n': 240,
              'one_per_date': 7.954095765730113,
              'one_per_symbol': 4.26923076923077,
              'p_le0': 0.1366,
              'perm_p': 0.1605,
              'placebo_dates': [22.5, 50.0],
              'placebo_iid': [30.0, 40.0],
              'room_risk': 3.4240349067401197,
              'room_risk_base': 5.157886070607304,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'bool',
      'name': 'inside_at',
      'orientation': -1,
      'ship_eligible': True,
      'top': {'ci': [-0.20254550241286667, 0.36306089740737957],
              'ci_R': [-0.09255889580147338, 0.02976207282391536],
              'ci_rw': [-3.8183720981498306, 1.76370708375035],
              'ci_stop': [-0.44653977698437375, 0.13109720476404377],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': False,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': -0.022475471066324415,
              'd_hit5': 0.09027103268669512,
              'd_hit5_reweighted': -1.0923618650026186,
              'd_risk': 0.023376593000060897,
              'd_stop': -0.16892603270191042,
              'label': 'no',
              'n': 20346,
              'one_per_date': -0.83102493074792,
              'one_per_symbol': -0.20712058212057904,
              'p_le0': 0.2666,
              'perm_p': 0.2045,
              'placebo_dates': [34.44878600216259, 35.51066548707363],
              'placebo_iid': [34.822569546839674, 35.19119237196501],
              'room_risk': 5.080953839066371,
              'room_risk_base': 5.157886070607304,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'num',
      'name': 'rvol20_at',
      'orientation': 1,
      'ship_eligible': True,
      'top': {'ci': [-2.091231854472374, 1.1231870342444237],
              'ci_R': [-0.3359547870133149, 0.031474092408382254],
              'ci_rw': [-2.9276540032006726, 0.9967769895910744],
              'ci_stop': [-2.754774616904761, 0.5127480685827291],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': True,
                             'outside_date_placebo': False,
                             'reweighted_sign': False,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': -0.12769410561529543,
              'd_hit5': -0.4603453188516182,
              'd_hit5_reweighted': -0.9652662789163802,
              'd_risk': 0.1492445022787514,
              'd_stop': -1.134900924448512,
              'label': 'Q5',
              'n': 4577,
              'one_per_date': 2.422858201066369,
              'one_per_symbol': 1.8760268857356266,
              'p_le0': 0.714,
              'perm_p': 0.756,
              'placebo_dates': [32.073410530915446, 37.90801835263273],
              'placebo_iid': [33.974218920690404, 36.07166266113175],
              'room_risk': 4.5274904002519945,
              'room_risk_base': 5.157886070607304,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'bool',
      'name': 'gap_up_next',
      'orientation': 1,
      'ship_eligible': True,
      'top': {'ci': [7.9423623488993345, 14.064599809363546],
              'ci_R': [-0.40609555040734846, 0.006728354769224374],
              'ci_rw': [-2.561414499375405, 4.088994267972945],
              'ci_stop': [-21.565798313278204, -14.890210202207085],
              'conditions': {'ci_excludes_0': True,
                             'one_per_date_symbol': True,
                             'outside_date_placebo': True,
                             'reweighted_sign': True,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': -0.18075839767243104,
              'd_hit5': 10.903418349211492,
              'd_hit5_reweighted': 0.6527072240823066,
              'd_risk': 2.202153981236312,
              'd_stop': -18.20318173126443,
              'label': 'yes',
              'n': 2235,
              'one_per_date': 8.86594986907358,
              'one_per_symbol': 11.775472966484202,
              'p_le0': 0.0,
              'perm_p': 0.0,
              'placebo_dates': [30.469798657718123, 39.59955257270693],
              'placebo_iid': [33.46532438478748, 36.644295302013425],
              'room_risk': 2.6313135263307803,
              'room_risk_base': 5.157886070607304,
              'verdict': 'selects smaller trades'}},
     {'convention': 'N',
      'kind': 'bool',
      'name': 'weak_day_at',
      'orientation': 1,
      'ship_eligible': True,
      'top': {'ci': [-1.3078087632291706, 1.9990150885401587],
              'ci_R': [-0.17741143047430113, 0.2807106746622631],
              'ci_rw': [-1.6315279587597191, 2.5702380739238855],
              'ci_stop': [0.7897372956234044, 3.7085343660717944],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': False},
              'd_R': 0.06526861917224103,
              'd_hit5': 0.3402068319972473,
              'd_hit5_reweighted': 0.4760000419631686,
              'd_risk': 0.035685475996758864,
              'd_stop': 2.204400968312381,
              'label': 'yes',
              'n': 6038,
              'one_per_date': -2.033966311468455,
              'one_per_symbol': 4.165680473372779,
              'p_le0': 0.3528,
              'perm_p': 0.2685,
              'placebo_dates': [32.560450480291486, 37.59523020867837],
              'placebo_iid': [34.15038092083471, 35.89019542894999],
              'room_risk': 6.488505729628625,
              'room_risk_base': 5.157886070607304,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'bool',
      'name': 'intact_at',
      'orientation': 1,
      'ship_eligible': True,
      'top': {'ci': [5.441170122511949, 8.412807853429417],
              'ci_R': [-0.20093792270519184, 0.21964841792348397],
              'ci_rw': [1.1164924107720953, 5.2519398919648586],
              'ci_stop': [-9.554040456382184, -6.487322672279994],
              'conditions': {'ci_excludes_0': True,
                             'one_per_date_symbol': True,
                             'outside_date_placebo': True,
                             'reweighted_sign': True,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': 0.028390468420872894,
              'd_hit5': 6.904060108404886,
              'd_hit5_reweighted': 3.191318525236078,
              'd_risk': 0.6198238186459766,
              'd_stop': -7.993946326775725,
              'label': 'yes',
              'n': 6944,
              'one_per_date': 6.208064019698368,
              'one_per_symbol': 8.722330672860707,
              'p_le0': 0.0,
              'perm_p': 0.0,
              'placebo_dates': [32.761376728110605, 37.29838709677419],
              'placebo_iid': [34.230990783410135, 35.81509216589861],
              'room_risk': 4.446871750212406,
              'room_risk_base': 5.157886070607304,
              'verdict': 'selects smaller trades'}},
     {'convention': 'PC',
      'kind': 'num',
      'name': 'rvol20_pre',
      'orientation': -1,
      'ship_eligible': False,
      'top': {'ci': [-1.960487804857651, 1.0767298163628625],
              'ci_R': [-0.03969674148076576, 0.172392101576917],
              'ci_rw': [-2.913377270626926, 0.7991687671318128],
              'ci_stop': [-0.25061595374067075, 2.777732574660118],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': False,
                             'room_risk_kept': True,
                             'stop_not_raised': True},
              'd_R': 0.06433165358057197,
              'd_hit5': -0.41334339266898,
              'd_hit5_reweighted': -1.0285842997261188,
              'd_risk': 0.04049026917268472,
              'd_stop': 1.2468027628346867,
              'label': 'Q1',
              'n': 4985,
              'one_per_date': -4.528584325496338,
              'one_per_symbol': 5.125738687831605,
              'p_le0': 0.7014,
              'perm_p': 0.7355,
              'placebo_dates': [30.791374122367106, 37.57372116349047],
              'placebo_iid': [33.17853560682046, 35.16549648946841],
              'room_risk': 7.685573989468171,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'PC',
      'kind': 'num',
      'name': 'rvol50_pre',
      'orientation': -1,
      'ship_eligible': False,
      'top': {'ci': [-1.0716254709910038, 1.6373156160249935],
              'ci_R': [-0.008774078622613295, 0.2172289423820379],
              'ci_rw': [-1.7262228495131773, 1.631269756666123],
              'ci_stop': [-0.10538798125434733, 2.4992799209787324],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': False,
                             'room_risk_kept': True,
                             'stop_not_raised': True},
              'd_R': 0.10146246362825945,
              'd_hit5': 0.2887629262878888,
              'd_hit5_reweighted': -0.046493500414994955,
              'd_risk': 0.025109991296670575,
              'd_stop': 1.1465018601265586,
              'label': 'Q1',
              'n': 4985,
              'one_per_date': -4.250032793462916,
              'one_per_symbol': 6.063085275951385,
              'p_le0': 0.349,
              'perm_p': 0.319,
              'placebo_dates': [30.791374122367106, 37.57372116349047],
              'placebo_iid': [33.17853560682046, 35.16549648946841],
              'room_risk': 8.11917186132261,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'PC',
      'kind': 'num',
      'name': 'updn_vol10_pre',
      'orientation': -1,
      'ship_eligible': False,
      'top': {'ci': [0.07944646271740882, 3.096851910578598],
              'ci_R': [-0.023715961227922442, 0.16303507148235483],
              'ci_rw': [0.02579478232368788, 3.7490088427057],
              'ci_stop': [-2.1529591729211393, 0.48325103677793485],
              'conditions': {'ci_excludes_0': True,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': True},
              'd_R': 0.06596477660664607,
              'd_hit5': 1.586970211197003,
              'd_hit5_reweighted': 1.8802744278036447,
              'd_risk': 0.0001387529815755073,
              'd_stop': -0.8299673830434506,
              'label': 'Q1',
              'n': 4983,
              'one_per_date': -1.841335795629423,
              'one_per_symbol': 6.376535123975701,
              'p_le0': 0.02,
              'perm_p': 0.004,
              'placebo_dates': [30.98334336744933, 37.68813967489464],
              'placebo_iid': [33.1717840658238, 35.15954244431065],
              'room_risk': 6.291932314177192,
              'room_risk_base': 6.091554886898409,
              'verdict': 'selects wider stops'}},
     {'convention': 'PC',
      'kind': 'bool',
      'name': 'above_sma50_pre',
      'orientation': -1,
      'ship_eligible': False,
      'top': {'ci': [-0.5997769648506851, 1.2897566516328656],
              'ci_R': [0.028291203098044306, 0.15050850286574632],
              'ci_rw': [0.23067047852085143, 4.649703027388026],
              'ci_stop': [0.11583091770898087, 1.799528999697466],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': False},
              'd_R': 0.08477535094318,
              'd_hit5': 0.3172856882441122,
              'd_hit5_reweighted': 2.3956659293562046,
              'd_risk': -0.11211303875545209,
              'd_stop': 0.9712386387301208,
              'label': 'no',
              'n': 14282,
              'one_per_date': -2.770083102493076,
              'one_per_symbol': 2.3606048804518998,
              'p_le0': 0.2522,
              'perm_p': 0.119,
              'placebo_dates': [32.810530737991876, 35.681977314101665],
              'placebo_iid': [33.78378378378378, 34.61700042010923],
              'room_risk': 7.051741355400422,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'PC',
      'kind': 'num',
      'name': 'close_pos_at',
      'orientation': -1,
      'ship_eligible': False,
      'top': {'ci': [-1.1340050925400345, 2.6811251436257293],
              'ci_R': [0.0791140698007877, 0.36840136431720677],
              'ci_rw': [-0.47604306826469794, 4.207815926951817],
              'ci_stop': [0.3826454255260686, 3.6126178010970977],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': False},
              'd_R': 0.22050357040668117,
              'd_hit5': 0.7702072592868869,
              'd_hit5_reweighted': 1.8714531092218756,
              'd_risk': -0.10130850589442231,
              'd_stop': 1.9890294428748012,
              'label': 'Q1',
              'n': 4985,
              'one_per_date': -2.770083102493076,
              'one_per_symbol': 4.999145183785486,
              'p_le0': 0.2206,
              'perm_p': 0.1,
              'placebo_dates': [30.791374122367106, 37.57372116349047],
              'placebo_iid': [33.17853560682046, 35.16549648946841],
              'room_risk': 7.530544500794283,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'PC',
      'kind': 'num',
      'name': 'lower_wick_at',
      'orientation': -1,
      'ship_eligible': False,
      'top': {'ci': [-0.44454128295641754, 2.652344502382413],
              'ci_R': [-0.016538763218448434, 0.23147300956579528],
              'ci_rw': [-1.0794817422783642, 2.861606709239296],
              'ci_stop': [-1.591875298916184, 1.3310513906241062],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': True},
              'd_R': 0.1033481214201592,
              'd_hit5': 1.062879221857299,
              'd_hit5_reweighted': 0.8452712024708888,
              'd_risk': 0.04726284770410594,
              'd_stop': -0.11677886197560827,
              'label': 'Q1',
              'n': 4989,
              'one_per_date': -0.2770083102493104,
              'one_per_symbol': 5.02354699341549,
              'p_le0': 0.089,
              'perm_p': 0.044,
              'placebo_dates': [30.94708358388455, 37.48246141511325],
              'placebo_iid': [33.1729805572259, 35.15734616155542],
              'room_risk': 6.5876602363073715,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'PC',
      'kind': 'num',
      'name': 'body_at',
      'orientation': 1,
      'ship_eligible': False,
      'top': {'ci': [-1.9101247042832712, 1.5600774629701317],
              'ci_R': [-0.04091328965212285, 0.23197017276089832],
              'ci_rw': [-2.1492716332684116, 2.0910313125461855],
              'ci_stop': [-1.5665636283465239, 1.6638573571427915],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': True},
              'd_R': 0.09395519176432104,
              'd_hit5': -0.1620063676742889,
              'd_hit5_reweighted': 0.008137450184074382,
              'd_risk': -0.01880933520492656,
              'd_stop': 0.08084776651630099,
              'label': 'Q5',
              'n': 4957,
              'one_per_date': -4.528584325496338,
              'one_per_symbol': 3.5373041137618855,
              'p_le0': 0.5776,
              'perm_p': 0.6275,
              'placebo_dates': [31.025822069800284, 37.46419205164413],
              'placebo_iid': [33.185394391769215, 35.16239661085334],
              'room_risk': 6.357128219206602,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'PC',
      'kind': 'bool',
      'name': 'up_close_at',
      'orientation': 1,
      'ship_eligible': False,
      'top': {'ci': [-1.2665488487944472, 1.9336657912775477],
              'ci_R': [-0.19291779926977456, 0.003379605593500973],
              'ci_rw': [-3.6311182770275763, 0.7974270168269367],
              'ci_stop': [-3.7821707997593905, -0.8527204936431918],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': False,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': -0.09129902928655159,
              'd_hit5': 0.3311029246523711,
              'd_hit5_reweighted': -1.4266739197830285,
              'd_risk': 0.17233230832015556,
              'd_stop': -2.322863529442032,
              'label': 'yes',
              'n': 7212,
              'one_per_date': -5.174669128962761,
              'one_per_symbol': 3.4339203790709316,
              'p_le0': 0.345,
              'perm_p': 0.2385,
              'placebo_dates': [31.738075429839157, 36.772739877981145],
              'placebo_iid': [33.402662229617306, 34.969495285635055],
              'room_risk': 4.965445662935395,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'PC',
      'kind': 'bool',
      'name': 'close_gt_prev_high_at',
      'orientation': 1,
      'ship_eligible': False,
      'top': {'ci': [-2.287944573665862, 3.5459848769831477],
              'ci_R': [-0.3661120492352393, -0.07281181868214628],
              'ci_rw': [-7.229530196283792, -0.8500026177313053],
              'ci_stop': [-7.863118293139842, -2.1670966924972954],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': False,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': -0.22080210569987813,
              'd_hit5': 0.6036579733733061,
              'd_hit5_reweighted': -4.07406529384367,
              'd_risk': 0.5621332839991355,
              'd_stop': -4.883687985522068,
              'label': 'yes',
              'n': 1934,
              'one_per_date': -0.8095897638833949,
              'one_per_symbol': 4.842971968573928,
              'p_le0': 0.3384,
              'perm_p': 0.2855,
              'placebo_dates': [28.593588417786968, 40.17580144777663],
              'placebo_iid': [32.57497414684592, 35.935884177869696],
              'room_risk': 3.907873740067338,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'PC',
      'kind': 'bool',
      'name': 'engulf_at',
      'orientation': 1,
      'ship_eligible': False,
      'top': {'ci': [-2.446626838039366, 10.204550429960975],
              'ci_R': [-0.49829047510550445, -0.033546779976479084],
              'ci_rw': [-6.058737420329768, 6.373238643871964],
              'ci_stop': [-12.984827318746692, -1.4853773765172926],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': True,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': -0.2743157800928824,
              'd_hit5': 3.7085383816863438,
              'd_hit5_reweighted': 0.16433158134576356,
              'd_risk': 0.608086161885824,
              'd_stop': -7.141669104379867,
              'label': 'yes',
              'n': 248,
              'one_per_date': 3.9767768375516988,
              'one_per_symbol': 6.9857043235704355,
              'p_le0': 0.1168,
              'perm_p': 0.123,
              'placebo_dates': [19.758064516129032, 51.61290322580645],
              'placebo_iid': [29.435483870967744, 39.11290322580645],
              'room_risk': 3.569056207540122,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'PC',
      'kind': 'bool',
      'name': 'inside_at',
      'orientation': -1,
      'ship_eligible': False,
      'top': {'ci': [-0.08393306359095173, 0.4683227110055894],
              'ci_R': [-0.010973969235531783, 0.025746116525638466],
              'ci_rw': [-2.1700614679560264, 2.927245568640778],
              'ci_stop': [-0.47469693087960946, 0.08263881206536008],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': 0.00861759435324383,
              'd_hit5': 0.1984023002709112,
              'd_hit5_reweighted': 0.4045581480934621,
              'd_risk': 0.015108704184656041,
              'd_stop': -0.20849021450544125,
              'label': 'no',
              'n': 22112,
              'one_per_date': -1.1080332409972304,
              'one_per_symbol': -0.038689913495709716,
              'p_le0': 0.0766,
              'perm_p': 0.038,
              'placebo_dates': [33.56096237337192, 34.76415520984081],
              'placebo_iid': [34.01772793053546, 34.37047756874095],
              'room_risk': 6.024001115907036,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'PC',
      'kind': 'num',
      'name': 'rvol20_at',
      'orientation': 1,
      'ship_eligible': False,
      'top': {'ci': [-2.0951525436429854, 1.4203663409392486],
              'ci_R': [-0.039769456954600824, 0.18157118376521791],
              'ci_rw': [-1.9697681263068658, 2.253618169960387],
              'ci_stop': [-2.520026445193577, 0.6652829421531957],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': 0.07330263979761004,
              'd_hit5': -0.3130424899608575,
              'd_hit5_reweighted': 0.22127770078106912,
              'd_risk': -0.06384110166462387,
              'd_stop': -0.9196967356608021,
              'label': 'Q5',
              'n': 4985,
              'one_per_date': -1.5635580178516462,
              'one_per_symbol': 4.980905021650711,
              'p_le0': 0.6396,
              'perm_p': 0.709,
              'placebo_dates': [30.791374122367106, 37.57372116349047],
              'placebo_iid': [33.17853560682046, 35.16549648946841],
              'room_risk': 5.76026184501588,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'PC',
      'kind': 'bool',
      'name': 'weak_day_at',
      'orientation': 1,
      'ship_eligible': False,
      'top': {'ci': [-1.615791885574994, 1.7247929988253303],
              'ci_R': [0.02826582431262232, 0.27822488177540866],
              'ci_rw': [-1.220145081459497, 3.306313097593393],
              'ci_stop': [1.3906663402167931, 4.111800311151217],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': False},
              'd_R': 0.1479329385427398,
              'd_hit5': 0.03330254721526371,
              'd_hit5_reweighted': 1.0220374437069741,
              'd_risk': -0.09532101001692928,
              'd_stop': 2.7353711075976284,
              'label': 'yes',
              'n': 6781,
              'one_per_date': -3.8781163434903068,
              'one_per_symbol': 4.982707639051176,
              'p_le0': 0.5004,
              'perm_p': 0.474,
              'placebo_dates': [31.587523964017105, 36.91195988792214],
              'placebo_iid': [33.3874059873175, 34.99483851939242],
              'room_risk': 7.887439207874143,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'PC',
      'kind': 'bool',
      'name': 'intact_at',
      'orientation': 1,
      'ship_eligible': False,
      'top': {'ci': [6.655728575599275, 9.928869370355667],
              'ci_R': [-0.08094634398613443, 0.08023132524351909],
              'ci_rw': [1.2969788256462604, 6.2711685282778635],
              'ci_stop': [-10.744561083542699, -7.613290549093878],
              'conditions': {'ci_excludes_0': True,
                             'one_per_date_symbol': True,
                             'outside_date_placebo': True,
                             'reweighted_sign': True,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': -0.0007788223089483237,
              'd_hit5': 8.297637442664257,
              'd_hit5_reweighted': 3.785969620312325,
              'd_risk': 0.8044802855392823,
              'd_stop': -9.158023213839407,
              'label': 'yes',
              'n': 7166,
              'one_per_date': 4.8253308710372425,
              'one_per_symbol': 11.869480414652028,
              'p_le0': 0.0,
              'perm_p': 0.0,
              'placebo_dates': [31.593636617359756, 36.82737929109685],
              'placebo_iid': [33.40775886128942, 34.970694948367296],
              'room_risk': 4.802303484109265,
              'room_risk_base': 6.091554886898409,
              'verdict': 'selects smaller trades'}}],
    'primary_outcome': 'hit5',
    'quotable': True,
    'quotable_reasons': [],
    'run_date': '2026-09-15',
    'script': 'backend/scripts/entry_trigger_study.py',
    'selected': [],
    'splits_features': {'N': {'s1': {'ci': None,
                  'd_hit5': None,
                  'mdl': 2.7425344155087483,
                  'n_fit': 11647,
                  'n_scored': 11237,
                  'name': 'S1 date halves',
                  'selected': [],
                  'verdict': 'no_signal'},
           's2': {'ci': None,
                  'd_hit5': None,
                  'mdl': 2.616023369166106,
                  'n_fit': 11237,
                  'n_scored': 11647,
                  'name': 'S2 reverse',
                  'selected': [],
                  'verdict': 'no_signal'},
           's3': {'ci': None,
                  'd_hit5': None,
                  'mdl': 2.773594371896699,
                  'n_fit': 11142,
                  'n_scored': 11742,
                  'name': 'S3 symbol-disjoint',
                  'selected': [],
                  'verdict': 'no_signal'}},
     'P': {'s1': {'ci': None,
                  'd_hit5': None,
                  'mdl': 2.2218848542641836,
                  'n_fit': 12687,
                  'n_scored': 12235,
                  'name': 'S1 date halves',
                  'selected': [],
                  'verdict': 'no_signal'},
           's2': {'ci': None,
                  'd_hit5': None,
                  'mdl': 2.432366116959668,
                  'n_fit': 12235,
                  'n_scored': 12687,
                  'name': 'S2 reverse',
                  'selected': [],
                  'verdict': 'no_signal'},
           's3': {'ci': None,
                  'd_hit5': None,
                  'mdl': 2.52736126968948,
                  'n_fit': 12153,
                  'n_scored': 12769,
                  'name': 'S3 symbol-disjoint',
                  'selected': [],
                  'verdict': 'no_signal'}},
     'PC': {'s1': {'ci': None,
                   'd_hit5': None,
                   'mdl': 2.2218848542641836,
                   'n_fit': 12687,
                   'n_scored': 12235,
                   'name': 'S1 date halves',
                   'selected': [],
                   'verdict': 'no_signal'},
            's2': {'ci': None,
                   'd_hit5': None,
                   'mdl': 2.432366116959668,
                   'n_fit': 12235,
                   'n_scored': 12687,
                   'name': 'S2 reverse',
                   'selected': [],
                   'verdict': 'no_signal'},
            's3': {'ci': None,
                   'd_hit5': None,
                   'mdl': 2.52736126968948,
                   'n_fit': 12153,
                   'n_scored': 12769,
                   'name': 'S3 symbol-disjoint',
                   'selected': [],
                   'verdict': 'no_signal'}}},
    'status': 'no_signal',
    'stratifiers': [{'convention': 'P',
      'kind': 'bool',
      'name': 'intact_at',
      'orientation': 1,
      'ship_eligible': True,
      'top': {'ci': [6.655728575599275, 9.928869370355667],
              'ci_R': [-0.08094634398613443, 0.08023132524351909],
              'ci_rw': [1.2969788256462604, 6.2711685282778635],
              'ci_stop': [-10.744561083542699, -7.613290549093878],
              'conditions': {'ci_excludes_0': True,
                             'one_per_date_symbol': True,
                             'outside_date_placebo': True,
                             'reweighted_sign': True,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': -0.0007788223089483237,
              'd_hit5': 8.297637442664257,
              'd_hit5_reweighted': 3.785969620312325,
              'd_risk': 0.8044802855392823,
              'd_stop': -9.158023213839407,
              'label': 'yes',
              'n': 7166,
              'one_per_date': 4.8253308710372425,
              'one_per_symbol': 11.869480414652028,
              'p_le0': 0.0,
              'perm_p': 0.0,
              'placebo_dates': [31.593636617359756, 36.82737929109685],
              'placebo_iid': [33.40775886128942, 34.970694948367296],
              'room_risk': 4.802303484109265,
              'room_risk_base': 6.091554886898409,
              'verdict': 'selects smaller trades'}},
     {'convention': 'P',
      'kind': 'bool',
      'name': 'weak_day_at',
      'orientation': 1,
      'ship_eligible': True,
      'top': {'ci': [-1.615791885574994, 1.7247929988253303],
              'ci_R': [0.02826582431262232, 0.27822488177540866],
              'ci_rw': [-1.220145081459497, 3.306313097593393],
              'ci_stop': [1.3906663402167931, 4.111800311151217],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': False},
              'd_R': 0.1479329385427398,
              'd_hit5': 0.03330254721526371,
              'd_hit5_reweighted': 1.0220374437069741,
              'd_risk': -0.09532101001692928,
              'd_stop': 2.7353711075976284,
              'label': 'yes',
              'n': 6781,
              'one_per_date': -3.8781163434903068,
              'one_per_symbol': 4.982707639051176,
              'p_le0': 0.5004,
              'perm_p': 0.474,
              'placebo_dates': [31.587523964017105, 36.91195988792214],
              'placebo_iid': [33.3874059873175, 34.99483851939242],
              'room_risk': 7.887439207874143,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'P',
      'kind': 'bool',
      'name': 'above_sma200_pre',
      'orientation': 1,
      'ship_eligible': True,
      'top': {'ci': [-1.018693082882276, 2.319391429099886],
              'ci_R': [-0.148349764989598, 0.07139670494474984],
              'ci_rw': [-2.8344005611513583, 2.899207983291188],
              'ci_stop': [-3.8956071995067654, -0.872902728093238],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': -0.03253557134161189,
              'd_hit5': 0.6864125414242972,
              'd_hit5_reweighted': 0.05410124330365814,
              'd_risk': 0.20317480972906488,
              'd_stop': -2.40779904552062,
              'label': 'yes',
              'n': 8873,
              'one_per_date': -3.190542144835773,
              'one_per_symbol': 4.684979685889274,
              'p_le0': 0.2122,
              'perm_p': 0.047,
              'placebo_dates': [32.029189676546835, 36.447650174687254],
              'placebo_iid': [33.51741237461963, 34.86982982080469],
              'room_risk': 3.917627402353708,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'P',
      'kind': 'num',
      'name': 'rs20_pre',
      'orientation': -1,
      'ship_eligible': True,
      'top': {'ci': [0.09522870086468503, 3.6849936332472035],
              'ci_R': [0.007483429467050662, 0.2745629176555103],
              'ci_rw': [0.09105387334975189, 4.3981867909830274],
              'ci_stop': [1.626624712816797, 4.487996073617824],
              'conditions': {'ci_excludes_0': True,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': False},
              'd_R': 0.13540952501030562,
              'd_hit5': 1.9136375501595082,
              'd_hit5_reweighted': 2.2769335685218066,
              'd_risk': 0.010828787276864649,
              'd_stop': 3.0321588310393,
              'label': 'Q1',
              'n': 4985,
              'one_per_date': -2.3001720692289283,
              'one_per_symbol': 6.699104202578299,
              'p_le0': 0.0194,
              'perm_p': 0.0,
              'placebo_dates': [30.791374122367106, 37.57372116349047],
              'placebo_iid': [33.17853560682046, 35.16549648946841],
              'room_risk': 9.191017473082871,
              'room_risk_base': 6.091554886898409,
              'verdict': 'selects wider stops'}},
     {'convention': 'N',
      'kind': 'bool',
      'name': 'above_sma200_pre',
      'orientation': 1,
      'ship_eligible': True,
      'top': {'ci': [-1.2200707989441961, 1.9175621936140776],
              'ci_R': [-0.3243838188636, 0.06754158329348554],
              'ci_rw': [-3.1295952169735677, 2.067062693496944],
              'ci_stop': [-3.721204287254859, -0.6484297479516471],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': False,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': -0.10514683493536944,
              'd_hit5': 0.4120240555368804,
              'd_hit5_reweighted': -0.4161663587346342,
              'd_risk': 0.16082549072294094,
              'd_stop': -2.251302948908951,
              'label': 'yes',
              'n': 8248,
              'one_per_date': -3.1173328056984584,
              'one_per_symbol': 1.383295949333685,
              'p_le0': 0.3058,
              'perm_p': 0.1645,
              'placebo_dates': [32.96496120271581, 37.05140640155189],
              'placebo_iid': [34.2992240543162, 35.68137730358875],
              'room_risk': 3.3553290037460552,
              'room_risk_base': 5.157886070607304,
              'verdict': 'inert'}},
     {'convention': 'N',
      'kind': 'num',
      'name': 'rs20_pre',
      'orientation': -1,
      'ship_eligible': True,
      'top': {'ci': [0.21430860111466213, 3.7075393525893863],
              'ci_R': [-0.35065017983727825, 0.061976609882730314],
              'ci_rw': [-0.5659994063310408, 3.5445785928483056],
              'ci_stop': [1.4238180044150144, 4.397174371840649],
              'conditions': {'ci_excludes_0': True,
                             'one_per_date_symbol': True,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': False},
              'd_R': -0.11942003621617031,
              'd_hit5': 1.9866723783299456,
              'd_hit5_reweighted': 1.5068117063528692,
              'd_risk': 0.16679503574107635,
              'd_stop': 2.9070479503603086,
              'label': 'Q1',
              'n': 4577,
              'one_per_date': 0.19444594479895438,
              'one_per_symbol': 4.038603462957707,
              'p_le0': 0.012,
              'perm_p': 0.0015,
              'placebo_dates': [32.073410530915446, 37.90801835263273],
              'placebo_iid': [33.974218920690404, 36.07166266113175],
              'room_risk': 7.353721297870834,
              'room_risk_base': 5.157886070607304,
              'verdict': 'selects wider stops'}},
     {'convention': 'PC',
      'kind': 'bool',
      'name': 'above_sma200_pre',
      'orientation': 1,
      'ship_eligible': False,
      'top': {'ci': [-1.018693082882276, 2.319391429099886],
              'ci_R': [-0.148349764989598, 0.07139670494474984],
              'ci_rw': [-2.8344005611513583, 2.899207983291188],
              'ci_stop': [-3.8956071995067654, -0.872902728093238],
              'conditions': {'ci_excludes_0': False,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': False,
                             'stop_not_raised': True},
              'd_R': -0.03253557134161189,
              'd_hit5': 0.6864125414242972,
              'd_hit5_reweighted': 0.05410124330365814,
              'd_risk': 0.20317480972906488,
              'd_stop': -2.40779904552062,
              'label': 'yes',
              'n': 8873,
              'one_per_date': -3.190542144835773,
              'one_per_symbol': 4.684979685889274,
              'p_le0': 0.2122,
              'perm_p': 0.047,
              'placebo_dates': [32.029189676546835, 36.447650174687254],
              'placebo_iid': [33.51741237461963, 34.86982982080469],
              'room_risk': 3.917627402353708,
              'room_risk_base': 6.091554886898409,
              'verdict': 'inert'}},
     {'convention': 'PC',
      'kind': 'num',
      'name': 'rs20_pre',
      'orientation': -1,
      'ship_eligible': False,
      'top': {'ci': [0.09522870086468503, 3.6849936332472035],
              'ci_R': [0.007483429467050662, 0.2745629176555103],
              'ci_rw': [0.09105387334975189, 4.3981867909830274],
              'ci_stop': [1.626624712816797, 4.487996073617824],
              'conditions': {'ci_excludes_0': True,
                             'one_per_date_symbol': False,
                             'outside_date_placebo': False,
                             'reweighted_sign': True,
                             'room_risk_kept': True,
                             'stop_not_raised': False},
              'd_R': 0.13540952501030562,
              'd_hit5': 1.9136375501595082,
              'd_hit5_reweighted': 2.2769335685218066,
              'd_risk': 0.010828787276864649,
              'd_stop': 3.0321588310393,
              'label': 'Q1',
              'n': 4985,
              'one_per_date': -2.3001720692289283,
              'one_per_symbol': 6.699104202578299,
              'p_le0': 0.0194,
              'perm_p': 0.0,
              'placebo_dates': [30.791374122367106, 37.57372116349047],
              'placebo_iid': [33.17853560682046, 35.16549648946841],
              'room_risk': 9.191017473082871,
              'room_risk_base': 6.091554886898409,
              'verdict': 'selects wider stops'}}],
    'survivor': None,
    'survivorship': {'cache_hit5_20': 32.71431251172388,
     'cache_n_episodes': 37317,
     'cache_n_names': 5277,
     'cache_stop_20': 77.01583728595546,
     'd_hit5_vs_broad': -1.4803749130413877,
     'run_date': '2026-09-15',
     'source': 'cache-csv:/tmp/ets_cache_events.csv',
     'written_to': '/tmp/ets_cache_events.csv.survivorship.json'},
    'tail': {'names': 3710, 'nonpos_names': 0, 'nonpos_rows': 0, 'phantom': 0, 'today': 2670},
    'universe_mode': 'broad',
    'walltime_stats_s': 95.3,
    'window': '2025-03-10 -> 2026-08-14',
    'windows': {'c': 3, 'delays': [1, 2, 3], 'hl': 10, 'source': 'brief 2026-09-15 — unconfirmed'},
}
SURVIVOR = MEASURED.get("survivor")

# ── vocabulary ─────────────────────────────────────────────────────────────
KIND_DEMAND, KIND_SUPPLY_BREAK, KIND_NA = "demand", "supply_break", "n/a"
READY, WATCH, BLOCKED = PE.GRADE_READY, PE.GRADE_WATCH, PE.GRADE_BLOCKED
VERDICT_RANK = PE.GRADE_ORDER

# The ONLY floor reason template. The state word is whatever the sweep read
# returns — this file never writes one down, so a new state can never read
# READY by omission (it is not in AG.FLOOR_HELD_STATES, so it blocks).
FLOOR_CODE = "floor_{state}"

# reason codes, in the ORDER they are appended (the mirror fixture pins it)
BLOCK_CODES = ("no_band", "no_break", "break_extended", "proximity", "room", "floor")
WATCH_CODES = ("reclaim", "weak_day", "floor_unknown")     # + "survivor_<key>" last

# Two bands are the SAME band when they agree to the cent (spec 2026-09-15):
# the study's replayed band and the served band are computed by the same
# engine on the same bars, so anything beyond rounding is a different level.
BAND_MATCH_TOL = 0.01

# ONE map, tab -> kind. The FE mirror (`ENTERABLE_KIND`) is pinned against the
# same fixture. Defaults are the spec's (§7.16) — his call which tabs move.
KIND_BY_TAB = {
    "zones": KIND_DEMAND, "deep_demand": KIND_DEMAND, "quick_bounce": KIND_DEMAND,
    "hot_pullback": KIND_DEMAND, "session": KIND_DEMAND, "signals": KIND_DEMAND,
    "overnight": KIND_DEMAND, "patterns": KIND_DEMAND, "bonde": KIND_DEMAND,
    "growth": KIND_DEMAND, "gnt": KIND_DEMAND, "catalysts": KIND_DEMAND,
    "hot_sectors": KIND_DEMAND, "keltner": KIND_DEMAND, "amd": KIND_DEMAND,
    "gabbar": KIND_DEMAND, "ict": KIND_DEMAND,
    "breaking": KIND_SUPPLY_BREAK,
    # chip only — the FE never hides a position or a single-symbol page
    "holdings": KIND_DEMAND, "support": KIND_DEMAND,
    "vcp": KIND_NA, "winners": KIND_NA, "topping": KIND_NA, "earnings": KIND_NA,
    "zero_dte": KIND_NA, "undervalue": KIND_NA,
    # 〰️ 9 EMA · W/M (2026-09-23): the tiles are WEEKLY and MONTHLY bars with a
    # moving average drawn on them. There is no demand band and no daily
    # reversal on that frame, so a demand read would blank the tab by
    # construction — the chip says why instead.
    "ema_frames": KIND_NA,
    # 📰 News (2026-09-24): sector rows and headlines, no ticker rows — a
    # demand read has nothing to read.
    "news": KIND_NA,
}

NA_TEXT = ("no demand read for this tab — its rows are not demand reversals "
           "(pivot / highs / lid / event / options / value)")


def _f(x) -> Optional[float]:
    """Numbers only: NaN / inf / junk become None (the `alert_gates._f` rule)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and not math.isinf(v) else None


def _prose(s) -> str:
    """Prose he reads says REVERSAL (2026-09-09 rule, after CASY). Every served
    sentence in this module goes through here."""
    return str(s or "").replace("bouncing", "reversal").replace("bounce", "reversal")


# ═════════════════════════════════════════════════════════════════════════════
# THE 🚀 LID — the lane's own break window, and the print that is past it
# ═════════════════════════════════════════════════════════════════════════════
def _broke_max_pct():
    """`zone_edge.BROKE_MAX_PCT` — how far through a lid the lane still calls a
    break. Imported LAZILY (zone_edge imports this module) and None when it
    cannot be read: the sentence then names no number rather than a typed one."""
    try:
        from supply_demand import zone_edge as ZE                  # noqa: PLC0415
        return float(ZE.BROKE_MAX_PCT)
    except Exception as exc:                                       # noqa: BLE001
        log.debug("enterable: zone_edge unavailable for the break window: %s", exc)
        return None


def _extended_break(px, bands, prev_close) -> Optional[dict]:
    """The lid this print has ALREADY run past — `read_breaking`'s own "broke
    today" rule with its ceiling lifted.

    `read_breaking` answers None for two opposite facts: the name never broke a
    lid, and the name broke one and is now further through it than the lane
    reads (`BROKE_MAX_PCT`). Serving "no lid break" for the second says the
    opposite of what happened (critique M1, 2026-09-15), so the two are told
    apart here. Same selection as the lane, constant by name, upper bound
    inverted: a supply band yesterday's close sat at or under (so the lid was
    still a lid) whose top the print is now above, the highest one of them.

    None when nothing qualifies, when the previous close is unknown (the lane
    cannot tell "broke today" either) or when the print is still inside the
    lane's window — that case is `read_breaking`'s to answer, not this one's.
    """
    p, pc = _f(px), _f(prev_close)
    if p is None or p <= 0 or pc is None or pc <= 0:
        return None
    try:
        from supply_demand import zone_edge as ZE                  # noqa: PLC0415
    except Exception as exc:                                       # noqa: BLE001
        log.debug("enterable: zone_edge unavailable for the break read: %s", exc)
        return None
    through = [b for b in (bands or [])
               if isinstance(b, dict) and ZE._valid_band(b) and ZE._kind(b) == "supply"
               and pc <= float(b["hi"]) < p]
    if not through:
        return None
    band = max(through, key=lambda b: float(b["hi"]))
    hi = float(band["hi"])
    window = _broke_max_pct()
    if window is None or p <= hi * (1.0 + window / 100.0):
        return None
    return {"band": {"lo": float(band["lo"]), "hi": hi},
            "through_pct": (p - hi) / hi * 100.0}


# ═════════════════════════════════════════════════════════════════════════════
# THE WORDS — one callable per reason code, so nothing is typed twice
# ═════════════════════════════════════════════════════════════════════════════
def _floor_state(ctx) -> str:
    return str(ctx.get("floor_state") or "").strip().lower()


def _blocker_line(room_ok: bool, prox_ok: bool, room) -> str:
    """One line out of the SHIPPED `premarket_entry.blockers` — called with the
    other gate passing so exactly the wanted sentence comes back."""
    lines = PE.blockers(bool(room_ok), bool(prox_ok), room)
    return lines[0] if lines else ""


def _extended_text(ctx) -> str:
    """The break is past the lane's window — said with the window's own value,
    never a typed one (the constant is `zone_edge.BROKE_MAX_PCT`)."""
    ext = ctx.get("extended") or {}
    band = ext.get("band") or {}
    window = _broke_max_pct()
    where = (" ($%g–%g)" % (band["lo"], band["hi"])) if band.get("hi") else ""
    if window is None:
        return "the lid break%s is further along than this read follows" % where
    through = _f(ext.get("through_pct"))
    how_far = ("%.1f%% " % through) if through is not None else ""
    return ("the print is %sabove the lid%s it cleared — more than the %g%% "
            "through the lid this read follows, so the break is extended"
            % (how_far, where, window))


def _extended_short() -> str:
    window = _broke_max_pct()
    return "break extended" if window is None else "break > %g%%" % window


REASON_TEXT = {
    "no_band": lambda ctx: "no demand band at or below the print",
    "no_break": lambda ctx: "not breaking a lid at this print",
    "break_extended": lambda ctx: _extended_text(ctx),
    "proximity": lambda ctx: _blocker_line(True, False, ctx.get("room")),
    "room": lambda ctx: _blocker_line(False, True, ctx.get("room")),
    "floor": lambda ctx: ("band floor %s — the push gate needs one of %s%s"
                          % (_floor_state(ctx),
                             ", ".join(AG.FLOOR_HELD_STATES),
                             (" · " + AG.sweep_txt(ctx.get("sweep")))
                             if AG.sweep_txt(ctx.get("sweep")) else "")),
    "floor_unknown": lambda ctx: ("floor state unknown (no closed-bar tail yet) — "
                                  "cannot confirm the floor held"),
    "reclaim": lambda ctx: (ctx.get("drag") or {}).get("text") or "reclaiming the band from below",
    "weak_day": lambda ctx: (ctx.get("drag") or {}).get("text") or "down on the day",
    "survivor": lambda ctx: ((ctx.get("survivor") or {}).get("text")
                             or "trigger %s not fired yet: %s"
                             % ((ctx.get("survivor") or {}).get("key"),
                                (SURVIVOR or {}).get("definition"))),
    "na": lambda ctx: NA_TEXT,
}

REASON_SHORT = {
    "no_band": lambda ctx: "no band",
    "no_break": lambda ctx: "no lid break",
    "break_extended": lambda ctx: _extended_short(),
    "proximity": lambda ctx: "not at band",
    "room": lambda ctx: "room < %g%%" % AG.ALERT_MIN_ROOM_PCT,
    "floor": lambda ctx: "floor %s" % _floor_state(ctx),
    "floor_unknown": lambda ctx: "floor unknown",
    "reclaim": lambda ctx: "reclaim from below",
    "weak_day": lambda ctx: "weak day",
    "survivor": lambda ctx: "trigger %s" % ((ctx.get("survivor") or {}).get("key")),
    "na": lambda ctx: "n/a",
}


def _base_code(code) -> str:
    """`floor_<state>` -> "floor", `survivor_<key>` -> "survivor", else itself."""
    c = str(code or "")
    if c.startswith("floor_") and c != "floor_unknown":
        return "floor"
    if c.startswith("survivor_"):
        return "survivor"
    return c


def _lines(codes, ctx, table) -> list:
    out = []
    for code in codes or []:
        fn = table.get(_base_code(code))
        if fn is None:
            out.append(_prose(code))
            continue
        c = dict(ctx)
        if _base_code(code) in ("reclaim", "weak_day"):
            c["drag"] = next((d for d in (ctx.get("drags") or [])
                              if isinstance(d, dict) and d.get("key") == code), None)
        try:
            out.append(_prose(fn(c)))
        except Exception as exc:                       # noqa: BLE001
            log.debug("enterable: reason text %s failed: %s", code, exc)
            out.append(_prose(code))
    return out


# ═════════════════════════════════════════════════════════════════════════════
# THE VERDICT — the shipped grader, wrapped
# ═════════════════════════════════════════════════════════════════════════════
def grade(kind: str, room_ok, prox_ok, floor_state, drags: list, survivor) -> tuple:
    """(verdict, reasons).

    Mood is NOT a parameter, exactly as `PE.grade_row` refuses it: mood is a
    tiebreak, never a promotion (pinned both sides).

    demand        the shipped grader decides BLOCKED / WATCH / READY on the two
                  standing gates and the measured drags; on top of it a floor
                  that is READABLE and not in `AG.FLOOR_HELD_STATES` blocks, and
                  an UNREADABLE floor is a WATCH reason (unknown is not a
                  failure on a board — on the phone the standing gate already
                  fails closed).
    supply_break  room to the next lid is the whole rule (his call §7.6).
    n/a           no verdict at all: (None, ["na"]).

    A gate passed as None (unreadable) is False — the same side every phone
    gate fails on.
    """
    k = str(kind or KIND_DEMAND)
    if k == KIND_NA:
        return None, ["na"]

    ok_room, ok_prox = bool(room_ok), bool(prox_ok)
    if k == KIND_SUPPLY_BREAK:
        return (READY, []) if ok_room else (BLOCKED, ["room"])

    drag_list = [d for d in (drags or []) if isinstance(d, dict) and d.get("key")]
    verdict = PE.grade_row(ok_room, ok_prox, drag_list)
    if verdict == BLOCKED:
        reasons = []
        if not ok_prox:
            reasons.append("proximity")
        if not ok_room:
            reasons.append("room")
        return BLOCKED, reasons

    state = None if floor_state is None else str(floor_state).strip().lower()
    if state is not None and state not in AG.FLOOR_HELD_STATES:
        return BLOCKED, [FLOOR_CODE.format(state=state)]

    reasons = [d["key"] for d in drag_list]
    if state is None:
        reasons.append("floor_unknown")
    if isinstance(survivor, dict) and survivor.get("ok") is not True:
        reasons.append("survivor_%s" % survivor.get("key"))
    return (WATCH if reasons else READY), reasons


def assess(*, kind: str = KIND_DEMAND, px, band, bands, prev_close=None, day_low=None,
           change_pct=None, floor_state=None, approach=None, doc=None,
           room_ok=None, prox_ok=None, room=None, print_source: str = "live",
           day=None) -> dict:
    """The kind-aware read from already-known inputs.

    PRE-COMPUTED GATES. A caller that has already run a gate on the SAME inputs
    (every push path has, line by line, before this is reached) passes
    `room_ok` / `prox_ok` / `room` and they are used AS GIVEN — never recomputed,
    so the recorded verdict is the verdict the phone actually applied. Only a
    gate passed as None is computed here.

    ROOM. `AG.room_read` answers None both for CLEAR (nothing overhead) and for
    a print it cannot use. The served block tells them apart: CLEAR is a state,
    an unusable print is no room block at all.

    `day` — the SESSION date this print belongs to, the one the push paths hand
    `sweep_read` (`demand_alerts.py:812`). It reaches `with_session_bar`, which
    appends the print as a new bar only when the cached frame ends BEFORE that
    date: without it the default is the calendar today, so on a Saturday
    Friday's snapshot is appended a second time as a synthetic Saturday bar
    (critique m7). None keeps the old default.
    """
    k = str(kind or KIND_DEMAND)
    px_f = _f(px)
    sess_low = _f(day_low) is not None and _f(day_low) > 0
    base = {"kind": k, "print": {"px": px_f, "source": str(print_source or "live")},
            "measured": measured_block()}

    if k == KIND_NA:
        ctx = {"room": None, "drags": [], "survivor": None, "floor_state": None, "sweep": None}
        verdict, reasons = grade(k, None, None, None, [], None)
        return dict(base, verdict=verdict, reasons=reasons,
                    reason_text=_lines(reasons, ctx, REASON_TEXT),
                    reason_short=_lines(reasons, ctx, REASON_SHORT),
                    gates={"room_ok": None, "prox_ok": None, "floor_state": None,
                           "session_low": sess_low},
                    drags=[], band=None, room=None, survivor=None)

    usable_band = (isinstance(band, dict)
                   and _f(band.get("lo")) is not None and _f(band.get("hi")) is not None)
    if not usable_band:
        # 🚀 M1 (2026-09-15): `read_breaking` answers None for "never broke a
        # lid" AND for "broke one and ran further through it than the lane
        # reads". The second is not "no lid break" — it says so in its own
        # code, and stays BLOCKED (§7.6: the supply read is the existing gate,
        # and this print is past the window that gate is defined on).
        extended = (_extended_break(px_f, bands, prev_close)
                    if k == KIND_SUPPLY_BREAK else None)
        code = ("break_extended" if extended else
                ("no_break" if k == KIND_SUPPLY_BREAK else "no_band"))
        ctx = {"room": None, "drags": [], "survivor": None, "floor_state": None,
               "sweep": None, "extended": extended}
        return dict(base, verdict=BLOCKED, reasons=[code],
                    reason_text=_lines([code], ctx, REASON_TEXT),
                    reason_short=_lines([code], ctx, REASON_SHORT),
                    gates={"room_ok": None, "prox_ok": None, "floor_state": None,
                           "session_low": sess_low},
                    drags=[], band=None, room=None, survivor=None)

    if room_ok is None:
        room_ok, room = AG.room_gate(px_f, bands or [], prev_close)
    room_ok = bool(room_ok)

    sweep = None
    drags: list = []
    survivor = None
    if k == KIND_SUPPLY_BREAK:
        prox_ok = None
    else:
        if prox_ok is None:
            prox_ok = AG.demand_proximity_gate(px_f, band)
        prox_ok = bool(prox_ok)

        if not isinstance(approach, dict):
            approach = AG.approach_read(px_f, band, prev_close, day_low)

        if floor_state is None and doc is not None:
            sweep = _floor_read(doc, band, px_f, day_low, day=day)
            floor_state = (sweep or {}).get("state")

        chg = change_pct
        if chg is None:
            pc = _f(prev_close)
            if pc is not None and pc > 0 and px_f is not None:
                chg = (px_f / pc - 1.0) * 100.0
        drags = [d for d in (PE.approach_drag(approach), PE.day_change_drag(chg)) if d]

        if SURVIVOR:
            survivor = survivor_read(k, doc=doc, band=band, px=px_f)

    verdict, reasons = grade(k, room_ok, prox_ok, floor_state, drags, survivor)

    # CLEAR is a state; an unusable print is the absence of a read (B2).
    room_srv = room if room else (
        {"state": "CLEAR", "room_pct": None, "target": None} if room_ok else None)

    ctx = {"room": room_srv, "drags": drags, "survivor": survivor,
           "floor_state": floor_state, "sweep": sweep}
    return dict(base, verdict=verdict, reasons=reasons,
                reason_text=_lines(reasons, ctx, REASON_TEXT),
                reason_short=_lines(reasons, ctx, REASON_SHORT),
                gates={"room_ok": room_ok, "prox_ok": prox_ok,
                       "floor_state": floor_state, "session_low": sess_low},
                drags=drags,
                band={"lo": _f(band.get("lo")), "hi": _f(band.get("hi"))},
                room=room_srv, survivor=survivor)


def read(*, doc, px, day_low=None, prev_close=None, change_pct=None,
         kind: str = KIND_DEMAND, symbol=None, print_source: str = "live",
         day=None) -> Optional[dict]:
    """The board / tile / row path: pick the band this kind reads, then assess.

    None ONLY when the print is unusable — an unknown read is never a verdict.
    `day` is the session date of the print (see `assess`); None = the calendar
    today, the pre-2026-09-15 behaviour.
    """
    px_f = _f(px)
    if px_f is None or px_f <= 0:
        return None

    k = str(kind or KIND_DEMAND)
    if k == KIND_NA:
        return assess(kind=KIND_NA, px=px_f, band=None, bands=[], day_low=day_low,
                      print_source=print_source)

    d = doc if isinstance(doc, dict) else {}
    all_bands = d.get("bands") or []
    pc = prev_close if prev_close is not None else d.get("prev_close")

    if k == KIND_SUPPLY_BREAK:
        from supply_demand import zone_edge                       # noqa: PLC0415
        rb = zone_edge.read_breaking(px_f, all_bands, pc, d.get("high_252"))
        band = (rb or {}).get("band")
        # With a band, the room list is the ONE next-lid rule. With none, the
        # full band list goes down so `assess` can tell "never broke a lid"
        # from "already past the lane's break window" (M1) — no gate reads it.
        lids = zone_edge.next_lids(all_bands, band) if band else all_bands
        return assess(kind=k, px=px_f, band=band, bands=lids, prev_close=pc,
                      day_low=day_low, change_pct=change_pct,
                      print_source=print_source, day=day)

    from supply_demand import bounce_room                          # noqa: PLC0415
    band = bounce_room.demand_read(px_f, d)
    return assess(kind=KIND_DEMAND, px=px_f, band=band, bands=all_bands, prev_close=pc,
                  day_low=day_low, change_pct=change_pct, doc=d,
                  print_source=print_source, day=day)


def slim(read) -> Optional[dict]:
    """What rides on a push payload and into push history — the verdict and its
    words, nothing that would go stale in a stored row."""
    if not isinstance(read, dict):
        return None
    return {"kind": read.get("kind"),
            "verdict": read.get("verdict"),
            "reasons": list(read.get("reasons") or []),
            "reason_text": list(read.get("reason_text") or []),
            "reason_short": list(read.get("reason_short") or [])}


def is_shown(read, mode: str = "enterable") -> bool:
    """The filter rule, served so the FE never re-decides it. "enterable" hides
    BLOCKED only — a row with no read, an unknown verdict and an `n/a` tab are
    all SHOWN (unknown is not "not enterable", his call §7.1/§7.2)."""
    if str(mode or "enterable") == "all":
        return True
    if not isinstance(read, dict):
        return True
    return read.get("verdict") != BLOCKED


# ═════════════════════════════════════════════════════════════════════════════
# THE FLOOR — one adapter, the shipped one
# ═════════════════════════════════════════════════════════════════════════════
def _floor_read(doc, band, px, day_low=None, day=None) -> Optional[dict]:
    """`intact_read` — `AG.sweep_read` on the doc's closed tail with
    the live session appended. Imported INSIDE (circularity) and failing to
    None: an unreadable floor is UNKNOWN, never "the floor held"."""
    try:
        from supply_demand.explosive import intact_read            # noqa: PLC0415
    except Exception as exc:                                       # noqa: BLE001
        log.warning("enterable: the floor adapter is unavailable (%s) — floor unknown", exc)
        return None
    try:
        return intact_read(doc, band, px, day_low=day_low, day=day)
    except Exception as exc:                                       # noqa: BLE001
        log.debug("enterable: floor read failed: %s", exc)
        return None


# ═════════════════════════════════════════════════════════════════════════════
# THE SURVIVOR — the STUDY'S own event and trigger, replayed on CLOSED bars
# ═════════════════════════════════════════════════════════════════════════════
def _study():
    """`scripts.entry_trigger_study`, imported lazily (its trigger functions are
    pure numpy — no Mongo, no I/O). None + a warning when it is not on the path
    (a container image without `scripts/`): the survivor then reads UNKNOWN,
    which is a WATCH reason, never an entry."""
    try:
        from scripts import entry_trigger_study as ETS             # noqa: PLC0415
        return ETS
    except Exception:                                              # noqa: BLE001
        pass
    try:
        import entry_trigger_study as ETS                          # noqa: PLC0415
        return ETS
    except Exception as exc:                                       # noqa: BLE001
        log.warning("enterable: the entry-trigger study is not importable (%s) — "
                    "the survivor is not read", exc)
        return None


def _same_band(a, b) -> bool:
    """Two bands agree to the cent."""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    for key in ("lo", "hi"):
        x, y = _f(a.get(key)), _f(b.get(key))
        if x is None or y is None or abs(x - y) > BAND_MATCH_TOL:
            return False
    return True


def _tail_arrays(doc) -> tuple:
    """(o, h, l, c, dates) from the doc's CLOSED tail, oldest first. The live
    print is NEVER in here — a trigger is a CLOSE, and today's close is not in
    yet."""
    tail = ((doc or {}).get("feat") or {}).get("tail") or []
    o, h, l, c, dates = [], [], [], [], []
    for rec in tail:
        if not isinstance(rec, dict):
            continue
        vals = [_f(rec.get(k)) for k in ("open", "high", "low", "close")]
        if any(v is None for v in vals):
            continue
        o.append(vals[0]); h.append(vals[1]); l.append(vals[2]); c.append(vals[3])
        dates.append(rec.get("date"))
    return o, h, l, c, dates


def _survivor_replay(trigger_attr: str, key: str, *, doc, band, px, survivor) -> Optional[dict]:
    """The one survivor reader, parameterised by which trigger the study picked.

    It re-runs the STUDY'S `event_at` (the same touch definition `BQ.events`
    replayed) on the doc's closed tail, refuses when the event lands on a
    different band than the one being served, and then asks the STUDY'S own
    `trigger_*` whether it has fired at a CLOSE. No third definition exists.
    """
    ets = _study()
    if ets is None:
        return None
    event_at = getattr(ets, "event_at", None)
    trig = getattr(ets, trigger_attr, None)
    if event_at is None or trig is None:
        log.warning("enterable: the entry-trigger study has no %s/%s — the "
                    "survivor is not read", "event_at", trigger_attr)
        return None

    o, h, l, c, dates = _tail_arrays(doc)
    if not c:
        return None
    window = int(_f((survivor or {}).get("window_bars")) or 0)
    bands = (doc or {}).get("bands") or []
    stop_at = len(c) - 1 - window - 1

    for t in range(len(c) - 1, max(stop_at, -1), -1):
        ev = event_at(o, h, l, c, t, bands)
        if not isinstance(ev, dict):
            continue
        if not _same_band(ev.get("band"), band):
            return {"key": key, "ok": None, "touch_date": dates[t],
                    "text": _prose("trigger measured on a different band than the "
                                   "one served — not read")}
        k, why = trig(o, h, l, c, t, ev.get("stop"),
                      (ev.get("band") or {}).get("hi"), window)
        if k is not None and 0 <= int(k) < len(dates):
            return {"key": key, "ok": True, "touch_date": dates[t],
                    "fired_date": dates[int(k)],
                    "text": _prose("confirmed at the close of %s" % dates[int(k)])}
        return {"key": key, "ok": False, "touch_date": dates[t], "fired_date": None,
                "text": _prose("not confirmed at a close yet (%s)" % (why or "no trigger"))}
    return None


def _sv_c1(*, doc, band, px, survivor) -> Optional[dict]:
    return _survivor_replay("trigger_c1", "C1", doc=doc, band=band, px=px, survivor=survivor)


def _sv_c2(*, doc, band, px, survivor) -> Optional[dict]:
    return _survivor_replay("trigger_c2", "C2", doc=doc, band=band, px=px, survivor=survivor)


def _sv_hl(*, doc, band, px, survivor) -> Optional[dict]:
    return _survivor_replay("trigger_hl", "HL", doc=doc, band=band, px=px, survivor=survivor)


def _sv_l1(*, doc, band, px, survivor) -> Optional[dict]:
    return _survivor_replay("trigger_l1", "L1", doc=doc, band=band, px=px, survivor=survivor)


_SURVIVOR_READERS = {"C1": _sv_c1, "C2": _sv_c2, "L1": _sv_l1, "HL": _sv_hl}


def survivor_read(kind, *, doc, band, px) -> Optional[dict]:
    """The live read of the study's surviving trigger, or None (unknown).

    Only ever called when `MEASURED["survivor"]` is set — and only on demand
    rows, which is the cohort the study measured.
    """
    s = SURVIVOR
    if not isinstance(s, dict) or str(kind or "") != KIND_DEMAND:
        return None
    key = str(s.get("key") or "")
    fn = _SURVIVOR_READERS.get(key)
    if fn is None:
        log.warning("enterable: MEASURED survivor %r has no live reader — not read", key)
        return None
    try:
        return fn(doc=doc, band=band, px=px, survivor=s)
    except Exception as exc:                                       # noqa: BLE001
        log.warning("enterable: survivor reader %s failed: %s", key, exc)
        return None


# ═════════════════════════════════════════════════════════════════════════════
# THE MEASUREMENT, in prose
# ═════════════════════════════════════════════════════════════════════════════
def status() -> str:
    """The EFFECTIVE status. `separates` only when the dict carries everything a
    live read needs — the key, the definition, its CI and the window the trigger
    may fire in. A half-written survivor reads `no_signal` rather than inventing
    a trigger nobody measured."""
    st = MEASURED.get("status")
    if st != STATUS_SEPARATES:
        return STATUS_PENDING if st == STATUS_PENDING else STATUS_NO_SIGNAL
    s = SURVIVOR
    need = ("key", "definition", "ci_cond", "window_bars")
    if not isinstance(s, dict) or any(s.get(f) in (None, "", [], {}) for f in need):
        log.warning("enterable: MEASURED says separates but the survivor is "
                    "incomplete — reading no_signal")
        return STATUS_NO_SIGNAL
    return STATUS_SEPARATES


def measured_block() -> dict:
    """What every chip tooltip repeats — read from MEASURED, never typed."""
    s = SURVIVOR if isinstance(SURVIVOR, dict) else {}
    return {"status": MEASURED.get("status"),
            "run_date": MEASURED.get("run_date"),
            "n_episodes": MEASURED.get("n_episodes"),
            "survivor_key": s.get("key"),
            "mdl": s.get("mdl_cond"),
            "script": MEASURED.get("script")}


def measured_verdict() -> dict:
    """{headline, body, fallback_note, limits} — the banner every surface that
    shows the chip leads with, built from MEASURED so no number is typed into a
    sentence (or into any TSX)."""
    m = MEASURED
    st = status()
    s = SURVIVOR if isinstance(SURVIVOR, dict) else {}
    fallback_note = _prose(
        "Until a trigger measures, ENTERABLE is the rules that already shipped: "
        "the two standing push gates, the band floor that has to have held, and "
        "the two measured drags from his own 286 pushes. %s" % (m.get("fallback") or ""))

    if st == STATUS_PENDING:
        headline = ("MEASURED: pending — the entry timing is still being replayed; "
                    "the read is the gates that already shipped")
        body = _prose(
            "The replay behind the entry TRIGGER question is still running (%s). "
            "Until it lands nothing here is scored and no number is quoted: a row "
            "is READY when it clears both standing gates with the band floor "
            "intact, WATCH when a measured drag or an unknown floor rides on it, "
            "and BLOCKED when a gate fails." % m.get("script"))
    elif st == STATUS_SEPARATES:
        ci = s.get("ci_cond") or [None, None]
        headline = ("MEASURED %s: %s lifts the read %s, 95%% CI %s to %s, on all "
                    "three out-of-sample splits, %s episodes"
                    % (m.get("run_date"), s.get("key"), _pp(s.get("d_cond")),
                       _pp(_f(ci[0]) if len(ci) > 0 else None),
                       _pp(_f(ci[1]) if len(ci) > 1 else None),
                       "{:,}".format(int(_f(m.get("n_episodes")) or 0))))
        body = _prose(
            "%s. The live read replays the study's own event and trigger on the "
            "doc's CLOSED bars — the live print is never the trigger — and an "
            "un-fired trigger is a WATCH reason, never a blocker."
            % (s.get("definition") or "the surviving convention"))
    else:
        headline = ("MEASURED %s: NO ENTRY TRIGGER SEPARATES — the read stays the "
                    "gates that already shipped" % (m.get("run_date") or ""))
        body = _prose(
            "Not one confirmation convention beat the rows that survived to the "
            "same bar without firing, so nothing new gates anything. %s"
            % (m.get("fallback") or ""))

    limits = _prose(
        "This is a READ and a FILTER: it buys nothing, sizes nothing and enters "
        "no lane. On the phone every demand push already passes these gates "
        "before the read runs, so a BLOCKED verdict there is a bug, not a quiet "
        "phone. A floor that cannot be read is UNKNOWN on a board (shown, with "
        "the reason) and fails CLOSED on the phone, as it always has. Bands are "
        "the board's closed-bar geometry; a tile's band and a push's band can "
        "differ, and the row says which print it read.")
    return {"headline": _prose(headline), "body": body,
            "fallback_note": fallback_note, "limits": limits}


def _pp(v) -> str:
    """A signed percentage point with a REAL minus sign — an unsigned bound at
    the top of a CI reads as a magnitude (the `explosive._sgn` precedent)."""
    x = _f(v)
    if x is None:
        return "n/a"
    return "%s%.2fpp" % ("+" if x >= 0 else "−", abs(x))
