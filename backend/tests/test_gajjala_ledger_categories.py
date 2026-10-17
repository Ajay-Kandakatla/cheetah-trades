"""chart_maps/gajjala/ledger.py — ✅ / ❌ categories and the loss facts (2026-10-16 night, DECISIONS11 D11 / D12,
BUILD_SPEC11 §3.14 / §3.15 C8, AMENDMENTS11 F2 / F7 / F13 / F14 / F17).

Ajay 2026-10-16 ~22:45 ET: "I want winners and losers category in his track record and would like us to study the
losers". The chips count ROWS, never a %; a loss fact is read from the STORED grade fields only (never a regrade, never
a bar) and carries no causal word. WP-C STEP 1's tests (9: the bucket truth table, 11: loss_facts / loss_text) and
STEP 2's served-block tests (10: buckets + categories over the SERVED rows, the replayed ones apart — AMENDMENTS11 F6 /
F13; 12: HONESTY + loss_text only on loser rows).

Every grade dict is SYNTHETIC (the ledger.grade shape) and named so. NEGATIVES are mandatory and marked.
"""
from __future__ import annotations

import itertools
import json
import re

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from tests.test_gajjala_ledger import (B_WORD, D15, D16, F3_HONESTY, aplus_doc, et, flat, pot_doc, row_of,
                                       store_with)
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_track_record_tab import NOW, graded_replay_doc, replay_tape


# ── 9. bucket_of — the C8 rule made total, as modified by F7 ───────────────────────────────────────────────────────
def _oracle(same, nxt, next_due=True) -> str:
    """The rule written out once more, case by case, to read the table against (BUILD_SPEC11 C8 + AMENDMENTS11 F7)."""
    if nxt in ("win", "loss"):
        return nxt
    if same in ("win", "loss"):
        return same
    if nxt == "flat":
        return "flat"
    if same == "open" and nxt == "pending" and next_due:
        return "open"
    return "out"


@pytest.mark.parametrize("next_due", [True, False])
def test_bucket_of_truth_table_over_every_cell_state_pair(next_due):
    for same, nxt in itertools.product(LG.CELL_STATES, LG.CELL_STATES):
        got = LG.bucket_of(same, nxt, next_due)
        assert got == _oracle(same, nxt, next_due), (same, nxt, next_due, got)
        assert got in LG.BUCKETS


@pytest.mark.parametrize("same,nxt,want", [
    ("win", "win", "win"), ("loss", "loss", "loss"),            # a decided same copied into next
    ("open", "win", "win"), ("open", "loss", "loss"),           # next decides
    ("win", "pending", "win"), ("loss", "pending", "loss"),     # next not graded yet → same
    ("win", "split", "win"), ("loss", "split", "loss"),         # next split → same
    ("open", "flat", "flat"), ("no_entry", "flat", "flat"),
    ("open", "pending", "open"),
    ("no_entry", "no_entry", "out"), ("no_plan", "no_plan", "out"), ("no_risk", "no_risk", "out"),
    ("no_time", "no_time", "out"), ("pending", "pending", "out"), ("split", "split", "out"),
    ("no_entry", "pending", "out"), ("pending", "no_entry", "out"),
])
def test_bucket_of_the_named_cases(same, nxt, want):
    assert LG.bucket_of(same, nxt) == want


def test_NEGATIVE_open_is_only_while_the_next_column_is_still_due():
    """F7: a replayed row whose next session was never cached (next_due False) and an open same with a split next are
    "out" — never "⏳ open" forever."""
    assert LG.bucket_of("open", "pending", next_due=False) == "out"
    assert LG.bucket_of("open", "split") == "out" and LG.bucket_of("open", "split", next_due=False) == "out"
    assert LG.bucket_of("open", "no_entry") == "out"
    assert LG.bucket_of("open", "pending") == "open"                    # the default is due


@pytest.mark.parametrize("same,nxt", [("flat", "pending"), ("flat", None), (None, None), ("bogus", "nope"), ("", ""),
                                      ("WIN", "LOSS"), (None, "open"), ("open", None)])
def test_NEGATIVE_unknown_or_impossible_states_answer_out(same, nxt):
    """A same "flat" never occurs (grade sets "open" for same); the function still answers for it and for any unknown
    string — total, never a raise, never a bucket outside BUCKETS."""
    assert LG.bucket_of(same, nxt) == "out"


def test_the_frozen_bucket_and_category_names():
    assert LG.BUCKETS == ("win", "loss", "open", "flat", "out")
    assert LG.BUCKET_TEXT == {"win": "✅ winner", "loss": "❌ loser", "open": "⏳ open", "flat": "➖ flat",
                              "out": "— no fill / not graded"}                      # F7
    assert LG.CATEGORY_KEYS == ("all", "win", "loss", "open", "flat", "out")
    assert LG.CATEGORY_LABELS == {"all": "📋 all", "win": "✅ winners", "loss": "❌ losers", "open": "⏳ open",
                                  "flat": "➖ flat", "out": "— no fill / not graded"}
    assert set(LG.BUCKET_TEXT) == set(LG.BUCKETS) and set(LG.CATEGORY_LABELS) == set(LG.CATEGORY_KEYS)
    assert LG.CATEGORY_PARAM == "cat" and LG.CATEGORY_EMPTY_TEXT == "No row in this category on this span."
    assert set(LG.BUCKETS[:2]) == set(LG.DECIDED) and set(LG.BUCKETS[:4]) <= set(LG.CELL_STATES)


def test_category_text_carries_the_row_count_and_the_replayed_count_apart():
    assert LG._category_text("loss", 12) == "❌ losers 12"
    assert LG._category_text("all", 0) == "📋 all 0"
    assert LG._category_text("win", 3, 2) == "✅ winners 3 +2 ⏪"                     # F13: counted apart
    assert LG._category_text("win", 3, 0) == "✅ winners 3"                           # NEGATIVE: no "+0 ⏪"
    assert "%" not in "".join(LG._category_text(k, 5, 1) for k in LG.CATEGORY_KEYS)  # rows, never a %


# ── 11. loss_facts / loss_text (D12, F2, F14, F17) ─────────────────────────────────────────────────────────────────
def _g(outcome, fill, exit_, *, fill_px=2.0, best_x=0.5, reason=None, entry="filled", **over) -> dict:
    """SYNTHETIC grade dict in the ledger.grade shape."""
    g = LG._blank("same")
    g.update(entry=entry, fill_px=fill_px, fill_t=LG._iso_t(fill) if fill else None, outcome=outcome,
             target_px=None, exit_t=LG._iso_t(exit_) if exit_ else None,
             reason=reason or {"loss": "stop", "win": "target"}.get(outcome, "horizon_end"),
             best_pct=best_x, best_to_exit_pct=best_x, close_pct=0.0)
    g.update(over)
    return g


def _rth_row():
    """SYNTHETIC: an RTH ring at 15:00 ET (Thu 10-15), trigger 2.00 / stop 1.95 → r 0.05."""
    return row_of(aplus_doc("LSR", "bull_flag", D15, et(D15, 15, 0), 2.00, 1.95), "aplus")


def test_loss_facts_on_a_late_rth_fill():
    row = _rth_row()
    assert row["rang"] == "rth" and row["r"] == pytest.approx(0.05) and not row["thin"]
    g = _g("loss", et(D15, 15, 41), et(D15, 15, 44))
    f = LG.loss_facts(row, g)
    assert f == {"stopped_min": 3, "fill_after_min": 41, "best_r": pytest.approx(0.2), "fill_minute": False,
                 "late_rth": True, "next_morning": False, "stale": False, "fast": True, "no_progress": True,
                 "gave_back": False, "thin": False}
    assert set(f) == {"stopped_min", "fill_after_min", "best_r", "fill_minute", "late_rth", "next_morning", "stale",
                      "fast", "no_progress", "gave_back", "thin"}
    want = ("stopped 3 min after the fill · high +0.2R through the stop minute · filled 41 min after it rang · "
            "last 30 min of RTH")
    assert LG.loss_text(row, g) == want
    assert want == " · ".join([LG.LOSS_FACT_STOPPED.format(n=3), LG.LOSS_FACT_BEST.format(x="0.2"),
                               LG.LOSS_FACT_FILLED.format(m=41),
                               LG.LOSS_FACT_LATE_RTH.format(n=GC.LEDGER_LOSS_LATE_RTH_MIN)])


def test_mutation_late_rth_min_moves_the_part_slot(monkeypatch):
    """The window is read from GC.LEDGER_LOSS_LATE_RTH_MIN by name: at 15 min, a 15:41 fill is no longer late and the
    part slot is empty."""
    monkeypatch.setattr(GC, "LEDGER_LOSS_LATE_RTH_MIN", 15)
    row, g = _rth_row(), _g("loss", et(D15, 15, 41), et(D15, 15, 44))
    assert LG.loss_facts(row, g)["late_rth"] is False
    assert LG.loss_text(row, g) == ("stopped 3 min after the fill · high +0.2R through the stop minute · filled 41 min "
                                    "after it rang")
    assert LG.fill_facts(row, g)["late_rth"] is False                   # one engine


def test_an_ah_ring_filled_next_morning_is_next_morning_never_stale():
    """F2: an AH ring filled 09:46 the next morning is "filled next morning (rang AH)" — ≥ 60 min after the ring yet
    NEVER "stale" (one class per fact)."""
    row = row_of(aplus_doc("AHX", "bull_flag", D15, et(D15, 16, 30), 2.00, 1.95), "aplus")
    assert row["rang"] == "ah"
    g = _g("loss", et(D16, 9, 46), et(D16, 9, 49), best_x=0.1)
    f = LG.loss_facts(row, g)
    assert f["next_morning"] is True and f["stale"] is False and f["late_rth"] is False
    assert f["fill_after_min"] == 17 * 60 + 16 and f["fill_after_min"] >= GC.LEDGER_LOSS_STALE_FILL_MIN
    assert f["stopped_min"] == 3 and f["fast"] is True and f["best_r"] == pytest.approx(0.04)
    assert LG.loss_text(row, g).endswith(" · filled next morning (rang AH)")


def test_a_stale_rth_fill_reads_the_stale_part():
    row = row_of(aplus_doc("STL", "bull_flag", D15, et(D15, 10, 0), 2.00, 1.95), "aplus")
    g = _g("loss", et(D15, 11, 10), et(D15, 11, 20), best_x=2.0)           # best_r 0.8 → gave back
    f = LG.loss_facts(row, g)
    assert (f["fill_after_min"], f["stale"], f["next_morning"], f["stopped_min"], f["fast"]) == (70, True, False, 10,
                                                                                              False)
    assert f["best_r"] == pytest.approx(0.8) and f["gave_back"] is True and f["no_progress"] is False
    assert LG.loss_text(row, g) == ("stopped 10 min after the fill · high +0.8R through the stop minute · filled 70 min "
                                    "after it rang · filled ≥60 min after the ring")


def test_stop_in_the_fill_minute_wins_the_part_slot():
    row, t = _rth_row(), et(D15, 15, 41)                                     # also late RTH
    g = _g("loss", t, t, reason="stop_fill_minute", best_x=0.0)
    f = LG.loss_facts(row, g)
    assert f["fill_minute"] is True and f["late_rth"] is True and f["stopped_min"] == 0
    assert LG.loss_text(row, g) == ("stopped 0 min after the fill · high +0.0R through the stop minute · filled 41 min "
                                    "after it rang · stop in the fill minute")


def test_a_thin_row_starts_with_the_thin_fact():
    row = row_of(aplus_doc("THN", "bull_flag", D15, et(D15, 11, 0), 0.543, 0.5429), "aplus")
    assert row["thin"] is True
    g = _g("loss", et(D15, 11, 5), et(D15, 11, 6), fill_px=0.543, best_x=0.01)
    assert LG.loss_facts(row, g)["thin"] is True
    assert LG.loss_text(row, g).startswith("thin R (not in the %) · stopped 1 min after the fill")


def test_no_r_drops_the_best_fact_and_no_alert_time_drops_the_filled_fact():
    row = dict(_rth_row(), r=None, at_utc=None)
    g = _g("loss", et(D15, 15, 41), et(D15, 15, 44))
    f = LG.loss_facts(row, g)
    assert f["best_r"] is None and f["fill_after_min"] is None and f["no_progress"] is False and f["gave_back"] is False
    assert LG.loss_text(row, g) == "stopped 3 min after the fill · last 30 min of RTH"


def test_fill_facts_is_the_shared_engine_for_winners_and_losers():
    """F14: fill_facts reads any decided trade (the +1R time for a win); loss_facts carries its fields unchanged."""
    row = _rth_row()
    win = _g("win", et(D15, 15, 41), et(D15, 15, 43), best_x=3.0)
    ff = LG.fill_facts(row, win)
    assert ff == {"fill_after_min": 41, "late_rth": True, "next_morning": False, "stale": False, "fast": True}
    loss = _g("loss", et(D15, 15, 41), et(D15, 15, 44))
    lf, lff = LG.loss_facts(row, loss), LG.fill_facts(row, loss)
    assert {k: lf[k] for k in lff} == lff
    slow = _g("win", et(D15, 10, 0), et(D15, 10, 0 + GC.LEDGER_LOSS_FAST_MIN + 1))
    assert LG.fill_facts(row, slow)["fast"] is False


@pytest.mark.parametrize("which", ["win", "open", "flat", "no_entry", "no_plan", "split", "none", "no_fill_t",
                                   "no_exit_t", "not_a_dict"])
def test_NEGATIVE_only_a_filled_loss_with_both_times_has_loss_facts(which):
    row = _rth_row()
    f, x = et(D15, 15, 41), et(D15, 15, 44)
    g = {"win": _g("win", f, x), "open": _g("open", f, None), "flat": _g("flat", f, None),
         "no_entry": _g(None, None, None, entry="no_entry", reason="no_entry"),
         "no_plan": _g(None, None, None, entry="no_plan", reason="no_plan"),
         "split": _g("loss", f, x, reason="split"), "none": None, "no_fill_t": _g("loss", None, x),
         "no_exit_t": _g("loss", f, None), "not_a_dict": "loss"}[which]
    assert LG.loss_facts(row, g) is None and LG.loss_text(row, g) is None
    if which not in ("win",):
        assert LG.fill_facts(row, g) is None


def test_NEGATIVE_no_loss_fact_word_carries_a_cause_or_a_forecast():
    words = [getattr(LG, n) for n in dir(LG) if n.startswith("LOSS_FACT_")]
    assert len(words) == 8
    bad = re.compile(r"\b(because|due to|caused?|why|will|likely|expect\w*|edge|win rate)\b", re.I)
    for w in words + list(LG.BUCKET_TEXT.values()) + list(LG.CATEGORY_LABELS.values()) + [LG.CATEGORY_EMPTY_TEXT]:
        assert not bad.search(w), w
        assert not B_WORD.search(w) and "fake" not in w.lower(), w
    assert LG.LOSS_FACT_BEST == "high +{x}R through the stop minute"                    # F17
    assert (LG.LOSS_FACT_THIN, LG.LOSS_FACT_STOPPED, LG.LOSS_FACT_FILLED, LG.LOSS_FACT_FILL_MINUTE,
            LG.LOSS_FACT_LATE_RTH, LG.LOSS_FACT_NEXT_MORNING, LG.LOSS_FACT_STALE) == (
        "thin R (not in the %)", "stopped {n} min after the fill", "filled {m} min after it rang",
        "stop in the fill minute", "last {n} min of RTH", "filled next morning (rang AH)",
        "filled ≥{n} min after the ring")


def test_NEGATIVE_loss_facts_never_regrades_nor_reads_a_bar(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("loss facts must read the stored grade only")
    monkeypatch.setattr(LG, "grade", boom)
    monkeypatch.setattr(LG, "_default_load_day", boom)
    monkeypatch.setattr(LG, "_today_load", boom)
    monkeypatch.setattr(LG, "today_bars", boom)
    row, g = _rth_row(), _g("loss", et(D15, 15, 41), et(D15, 15, 44))
    assert LG.loss_text(row, g).startswith("stopped 3 min")
    assert LG.fill_facts(row, g)["late_rth"] is True



# ── 10. served_block: every row's bucket; the chips count the SERVED rows, the replayed ones apart ──────────────────
def _graded(doc, kind, outcome, *, next_outcome=None, trigger=1.23, stop=1.11, tape=None) -> dict:
    """SYNTHETIC gajjala_ledger doc for `doc`: same = LG.grade on replay_tape (10-15) → `outcome`; next = LG.grade over
    10-15 + a 10-16 tape when `next_outcome` ("loss": 10-16 trades under the stop at 09:50) — else absent (pending)."""
    row = row_of(doc, kind)
    b = LG.session_bounds(row["date"], row["at_utc"])
    day1 = tape if tape is not None else replay_tape(D15, outcome=outcome, trigger=trigger, stop=stop)
    out = {"_id": row["id"], "date": row["date"], "symbol": row["symbol"], "setup": row["setup"], "kind": kind,
           "line": row["line"], "same": LG.grade(row, day1, b, "same")}
    if next_outcome == "loss":
        day2 = flat(D16, (4, 0), (9, 49), 1.30) + flat(D16, (9, 50), (19, 59), round(stop - 0.05, 4))
        out["next"] = LG.grade(row, day1 + day2, b, "next")
    return out


def cat_store(*, extra_win=False):
    """SYNTHETIC: on 10-15 a 🧠 WIN, an A+ shadow thin-R LOSS, an A+ shadow no-entry (a flat 1.20 tape under its 9.00
    trigger), an A+ shadow still open (next not
    due), a 🧠 open-then-LOSS next session; on 10-12 a ⏪ replayed WIN. `extra_win` adds a second 🧠 WIN."""
    at = et(D15, 10, 35)
    pots = [pot_doc("PWN", "bull_flag", D15, at, 1.23, 1.11), pot_doc("PNL", "kiss_fly", D15, at, 1.23, 1.11)]
    if extra_win:
        pots.append(pot_doc("PW2", "bull_flag", D15, at, 1.23, 1.11))
    als = [aplus_doc("THN", "bull_flag", D15, at, 2.00, 1.995), aplus_doc("NEN", "kiss_fly", D15, at, 9.00, 8.00),
           aplus_doc("OPN", "intraday_vcp", D15, at, 1.23, 1.11)]
    led = [_graded(pots[0], "potential", "win"), _graded(pots[1], "potential", "open", next_outcome="loss"),
           _graded(als[0], "aplus", "loss", trigger=2.00, stop=1.995), _graded(als[1], "aplus", "open",
                                                                                tape=flat(D15, (4, 0), (19, 59), 1.20)),
           _graded(als[2], "aplus", "open")]
    if extra_win:
        led.append(_graded(pots[2], "potential", "win"))
    st = store_with(pots, als, led)
    rep = graded_replay_doc("RPL", "bull_flag")
    st.coll(ST.REPLAY).docs[rep["_id"]] = rep
    return st


def served(st, **kw):
    return LG.served_block(st, D16, NOW, span="5d", is_today=True, today=None, **kw)


def _rows_of(b):
    return {r["symbol"]: r for d in b["days"] for r in d["rows"]}


def test_every_served_row_carries_its_bucket_and_the_served_text():
    b = served(cat_store())
    rows = _rows_of(b)
    want = {"PWN": "win", "PNL": "loss", "THN": "loss", "NEN": "out", "OPN": "open", "RPL": "win"}
    assert {k: r["bucket"] for k, r in rows.items()} == want
    for r in rows.values():
        assert r["bucket"] in LG.BUCKETS and r["bucket_text"] == LG.BUCKET_TEXT[r["bucket"]]
        nd = not (r["line"] == "replayed" and r["next"]["text"] == LG.REPLAY_NOT_GRADED_TEXT)
        assert r["bucket"] == LG.bucket_of(r["same"]["state"], r["next"]["state"], nd)
        assert not [t for t in LG.BUCKET_TEXT.values() if t in r["kind_text"]]          # NEGATIVE: no bucket word
    thin = rows["THN"]                                       # a thin-R loss keeps its bucket AND its thin chip
    assert thin["bucket"] == "loss" and thin["thin_text"] == LG.THIN_TEXT and thin["same"]["state"] == "loss"
    assert rows["NEN"]["same"]["state"] == "no_entry" and rows["OPN"]["next"]["state"] == "pending"


def test_categories_count_the_served_rows_in_category_order_with_the_replayed_ones_apart():
    b = served(cat_store())
    cats, tl = b["categories"], b["categories_timeline"]
    assert [c["key"] for c in cats] == list(LG.CATEGORY_KEYS) == [c["key"] for c in tl]
    assert {c["key"]: (c["n"], c["n_replayed"]) for c in cats} == {
        "all": (5, 1), "win": (1, 1), "loss": (2, 0), "open": (1, 0), "flat": (0, 0), "out": (1, 0)}
    assert [c["text"] for c in cats] == ["📋 all 5 +1 ⏪", "✅ winners 1 +1 ⏪", "❌ losers 2", "⏳ open 1", "➖ flat 0",
                                         "— no fill / not graded 1"]
    for c in cats + tl:
        assert c["text"] == LG._category_text(c["key"], c["n"], c["n_replayed"]) and "%" not in c["text"]
    shown = [r for d in b["days"] for r in d["rows"]]
    for cs in (cats, tl):
        assert sum(c["n"] for c in cs[1:]) == cs[0]["n"] and sum(c["n_replayed"] for c in cs[1:]) == cs[0]["n_replayed"]
    assert cats[0]["n"] + cats[0]["n_replayed"] == len(shown) == 6
    # the timeline lists only the kinds tape.views_block() names (aplus): the 🧠 rows are not in its chips
    assert {c["key"]: (c["n"], c["n_replayed"]) for c in tl} == {
        "all": (3, 1), "win": (0, 1), "loss": (1, 0), "open": (1, 0), "flat": (0, 0), "out": (1, 0)}
    assert (b["category_param"], b["category_empty_text"]) == (LG.CATEGORY_PARAM, LG.CATEGORY_EMPTY_TEXT)


def test_NEGATIVE_a_new_potential_win_moves_categories_never_categories_timeline():
    a, b = served(cat_store()), served(cat_store(extra_win=True))
    assert a["categories_timeline"] == b["categories_timeline"]
    ca, cb = ({c["key"]: c["n"] for c in x["categories"]} for x in (a, b))
    assert (cb["all"], cb["win"]) == (ca["all"] + 1, ca["win"] + 1)


def test_NEGATIVE_F7_a_replayed_open_whose_next_was_never_cached_serves_out_never_open():
    """F7 wired in served_block (critic fix round 2): a replayed row graded "open" on its same session whose next
    session was never cached (next null) is "out" — never "⏳ open" forever. The mutation next_due = True turns it to
    "open" and fails here (bucket_of's table alone never saw a SERVED row)."""
    st = cat_store()
    rep = graded_replay_doc("ROP", "bull_flag", outcome="open", next_graded=False)
    st.coll(ST.REPLAY).docs[rep["_id"]] = rep
    b = served(st)
    r = _rows_of(b)["ROP"]
    assert (r["same"]["state"], r["next"]["state"], r["next"]["text"]) == ("open", "pending",
                                                                            LG.REPLAY_NOT_GRADED_TEXT)
    assert (r["bucket"], r["bucket_text"]) == ("out", LG.BUCKET_TEXT["out"]) and r["loss_text"] is None
    cats = {c["key"]: (c["n"], c["n_replayed"]) for c in b["categories"]}
    assert cats["open"] == (1, 0)                       # NEGATIVE: the replayed open never enters the ⏳ open chip
    assert cats["out"] == (1, 1) and cats["all"] == (5, 2)
    base = {c["key"]: (c["n"], c["n_replayed"]) for c in served(cat_store())["categories"]}
    assert cats["open"] == base["open"] and cats["out"] == (base["out"][0], base["out"][1] + 1)


def test_NEGATIVE_the_chips_never_feed_a_count_line_or_a_pct(monkeypatch):
    """With bucket_of answering "loss" for every row, every count, count line and % is byte-equal — only the chips and
    the row buckets move (the patch took)."""
    base = served(cat_store())
    monkeypatch.setattr(LG, "bucket_of", lambda *a, **k: "loss")
    got = served(cat_store())
    assert json.dumps(got["counts"], sort_keys=True) == json.dumps(base["counts"], sort_keys=True)
    for k in ("counts_text", "shadow_text", "entries_text", "replayed_text", "replayed_note", "today_text",
              "more_text", "honesty"):
        assert got[k] == base[k], k
    assert {c["key"]: c["n"] + c["n_replayed"] for c in got["categories"]}["loss"] == 6     # the patch took
    assert base["replayed_text"] and base["shadow_text"]                                  # not vacuous


def test_NEGATIVE_F6_the_chips_never_exceed_the_rows_shown(monkeypatch):
    full = served(cat_store())
    monkeypatch.setattr(GC, "LEDGER_ROWS_MAX", 2)
    b = served(cat_store())
    shown = [r for d in b["days"] for r in d["rows"]]
    assert len(shown) == 2 and b["categories"][0]["n"] == 2 and b["categories"][0]["n_replayed"] == 0
    assert sum(c["n"] + c["n_replayed"] for c in b["categories"][1:]) == 2
    assert b["counts"] == full["counts"] and b["counts_text"] == full["counts_text"]    # the % lines cover every row
    assert b["more_text"] == "+4 more rows — the counts above cover all 6"


# ── 12. HONESTY gains the ONE sentence; loss_text rides only the losers ──────────────────────────────────────────────
def test_honesty_is_f3_plus_the_rows_sentence():
    sentence = (" The winners / losers chips count ROWS (a name that rang on two setups is two rows); the % lines are "
                "unchanged.")
    assert LG.HONESTY == F3_HONESTY and LG.HONESTY.endswith(sentence) and LG.HONESTY.count(sentence) == 1
    assert served(cat_store())["honesty"] == LG.HONESTY


def test_loss_text_is_served_only_on_loser_rows_from_the_deciding_column():
    st = cat_store()
    b = served(st)
    rows = _rows_of(b)
    for r in rows.values():
        assert (r["loss_text"] is not None) == (r["bucket"] == "loss"), r["symbol"]
    led = {d["symbol"]: d for d in st.coll(ST.LEDGER).docs.values()}
    thn = row_of(aplus_doc("THN", "bull_flag", D15, et(D15, 10, 35), 2.00, 1.995), "aplus")
    assert rows["THN"]["loss_text"] == LG.loss_text(thn, led["THN"]["same"])
    assert rows["THN"]["loss_text"].startswith(LG.LOSS_FACT_THIN)
    pnl = row_of(pot_doc("PNL", "kiss_fly", D15, et(D15, 10, 35), 1.23, 1.11))
    assert rows["PNL"]["same"]["state"] == "open" and rows["PNL"]["next"]["state"] == "loss"
    assert rows["PNL"]["loss_text"] == LG.loss_text(pnl, led["PNL"]["next"])                # the NEXT column decided
    assert LG.loss_text(pnl, led["PNL"]["same"]) is None
    assert rows["PNL"]["loss_text"].startswith("stopped ") and "filled 5 min after it rang" in rows["PNL"]["loss_text"]
    bad = re.compile(r"\b(because|due to|caused?|why)\b", re.I)
    assert not [r["loss_text"] for r in rows.values() if r["loss_text"] and bad.search(r["loss_text"])]
