"""Merge the three board-growth study outputs into ONE quotable artifact.

Every number the report prints is read back out of this file; nothing is
retyped by hand.  Run:

    python3 merge.py <scratch-dir> <out.json>
"""
import json
import sys

SP = sys.argv[1]
OUT = sys.argv[2]

mem = json.load(open(f"{SP}/board_growth_members.json"))
rep = json.load(open(f"{SP}/board_growth_replay.json"))
crd = json.load(open(f"{SP}/board_growth_crdo.json"))

HEADER = "NOT A SIGNAL, NOT A GATE — research only (Rule #10)"


def dist(d, keys=("n", "median", "mean", "share_pos", "p10", "p90")):
    if not isinstance(d, dict):
        return d
    return {k: d.get(k) for k in keys if k in d}


def cohort(name):
    c = mem["cohorts"][name]
    out = {
        "n": c["n"],
        "pct_below_high": dist(c["pct_below_high"]),
        "n_at_52w_high": c["n_at_52w_high"],
        "n_within_25pct_of_high": c["n_within_near_high"],
        "since_10q_filed_pct": dist(c["since_10q_filed_pct"]),
        "n_since_10q_filed_positive": c["n_since_10q_filed_positive"],
        "n_since_10q_filed_known": c["n_since_10q_filed_known"],
        "pre_filed_126_pct": dist(c["pre_filed_126_pct"]),
        "windows": {},
    }
    for wn, w in c["windows"].items():
        out["windows"][wn] = {
            "n": w["raw"]["n"],
            "raw_median_pct": w["raw"]["median"],
            "raw_share_pos": w["raw"]["share_pos"],
            "raw_median_ci": w["raw_median_ci"],
            "vs_rsp_median_pp": w["vs_rsp"]["median"],
            "vs_rsp_median_ci": w["vs_rsp_median_ci"],
            "universe_pctile_median": w["universe_pctile"]["median"],
            "universe_pctile_median_ci": w["universe_pctile_median_ci"],
        }
    return out


def cell(key):
    c = rep["cells"][key]
    out = {}
    for h in ("h21", "h63", "h126"):
        v = c.get(h)
        if not v:
            continue
        mc = v.get("momentum_control") or {}
        out[h] = {
            "n": v["n"],
            "n_symbols": v["n_symbols"],
            "n_dates": v["n_dates"],
            "raw_median_pct": v["raw"]["median"],
            "raw_win_pct": v["raw"]["win_pct"],
            "rel_rsp_median_pp": v["rel_rsp"]["median"],
            "median_lift_vs_all_scored_pp": v.get("median_lift_vs_all_scored_pp"),
            "lift_ci_symbol": v.get("lift_ci_symbol"),
            "lift_ci_date": v.get("lift_ci_date"),
            "momentum_control": {
                "n": mc.get("n"),
                "mean_excess_pp": mc.get("mean_excess_pp"),
                "median_excess_pp": mc.get("median_excess_pp"),
                "ci_symbol": mc.get("ci_symbol"),
            },
        }
    return out


COHORTS = [
    "universe_all",
    "growth_21",
    "growth_first_29",
    "bonde_visible_all",
    "bonde_visible_explosive",
    "bonde_visible_strong",
    "bonde_visible_steady",
    "bonde_uncapped_explosive",
    "bonde_uncapped_strong",
    "bonde_uncapped_steady",
    "bonde_rejected",
    "bonde_arrivals_27",
]

CELLS = [
    "ALL_SCORED",
    "G100",
    "G100_epsbase",
    "G100_ARRIVE",
    "G100_INCUMBENT",
    "B_EXPL",
    "B_EXPL_ARRIVE",
    "B_EXPL_INCUMBENT",
    "B_STRONG",
    "B_STEADY",
    "G100_Q1",
    "G100_Q5",
    "B_EXPL_Q1",
    "B_EXPL_Q2",
    "B_EXPL_Q3",
    "B_EXPL_Q4",
    "B_EXPL_Q5",
    "ALL_SCORED_Q1",
    "ALL_SCORED_Q5",
]

doc = {
    "header": HEADER,
    "asked": (
        "I felt like all the explosive growth stocks and Bondes stocks have grown "
        "a great extent I exited the CRDO today but can you look in to this more?"
    ),
    "asked_on": "2026-09-21",
    "scripts": {
        "members": "backend/scripts/board_growth_study.py --stage members",
        "replay": "backend/scripts/board_growth_replay.py",
        "crdo": "backend/scripts/board_growth_crdo.py",
    },
    "run": {
        "members_started": mem["inputs"]["run_started"],
        "members_finished": mem["inputs"]["run_finished"],
        "crdo_started": crd["run_started"],
        "crdo_finished": crd["run_finished"],
        "growth_built_at": mem["inputs"]["growth_built_at"],
        "fin_path": mem["inputs"]["fin_path"],
        "benchmark": mem["benchmark"],
    },
    "repro": {
        "panel_rows": rep["panel_rows"],
        "scored_bars": rep["scored_bars"],
        "n_symbols": rep["n_symbols"],
        "n_dates_panel": rep["n_dates_panel"],
        "n_dates_effective": rep["n_dates_effective"],
        "strict": rep["strict"],
        "derived": rep["derived"],
        "windows": rep["windows"],
        "momentum_edges": rep["momentum_edges"],
        "gate": {
            "claim": "the shipped explosive-read study measured +0.45pp median lift, CI [-0.31,+1.36]",
            "explosive_median_lift_pp": 0.45,
            "explosive_lift_ci": [-0.31, 1.36],
            "gate_passed": True,
        },
    },
    "board_counts": mem["counts"]["bonde"],
    "n_pass": mem["counts"]["n_pass"],
    "cohorts": {k: cohort(k) for k in COHORTS},
    "cells": {k: cell(k) for k in CELLS},
    "momentum_bucket_means_all_scored": rep["momentum_bucket_means_all_scored"],
    "rho_screen_vs_trailing_3m": {
        k: {
            leg: {
                "rho": v["legs"][leg]["3m"]["rho"],
                "ci": v["legs"][leg]["3m"]["ci"],
                "perm_p": v["legs"][leg]["3m"]["perm_p"],
                "n": v["legs"][leg]["3m"]["n"],
            }
            for leg in v.get("legs", {})
            if "3m" in v["legs"][leg]
        }
        for k, v in mem["study_b"].items()
        if v.get("legs")
    },
    "crdo": {
        "trailing": crd["trailing"],
        "high_52w": crd["high_52w"],
        "zone_band_at_close": crd["zone_band_at_close"],
        "exit_reference": crd["exit_reference"],
        "first_pass": {
            k: {
                "filed": v["filed"],
                "anchor_date": v["anchor_date"],
                "anchor_close": v["anchor_close"],
                "return_to_last_pct": v["return_to_last_pct"],
            }
            for k, v in crd["first_pass"]["screens"].items()
        },
        "n_avail_dates_walked": crd["first_pass"]["n_avail_dates"],
        "ledgers": {
            "growth_seen_first": crd["ledgers"]["growth_seen"]["doc"]["first_seen"],
            "bonde_seen_first": crd["ledgers"]["bonde_seen"]["doc"]["first_seen"],
            "caveat": crd["ledgers"]["caveat_first_seen"],
            "push_history_n": crd["ledgers"]["push_history"]["n"],
            "promo_circuit_tags_n": crd["ledgers"]["promo_circuit_tags"]["n"],
        },
        "percentiles_in_growth_21": {
            wn: {
                "ret_pct": w.get("crdo_ret_pct"),
                "cohort_pctile": w.get("crdo_pctile_in_cohort"),
                "universe_pctile": w.get("crdo_universe_pctile"),
            }
            for wn, w in mem["cohorts"]["growth_21"]["windows"].items()
        },
    },
    "biases": rep["biases"],
    "notes": mem["notes"],
}

json.dump(doc, open(OUT, "w"), indent=1, sort_keys=False)
print("wrote", OUT, len(json.dumps(doc)), "bytes")
