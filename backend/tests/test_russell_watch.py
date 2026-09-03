"""Russell inclusion watch — the classification table and its percentile
yardstick, locked pure so the EMAT-shaped false positive stays VISIBLE
(a name added after the baseline files still classifies as a candidate;
the payload's baseline note is the honesty valve, not silent magic).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from catalysts import russell_watch as rw  # noqa: E402
from catalysts.russell_watch import _pctl, classify  # noqa: E402

P25_R2000 = 250e6      # pretend p25 of current R2000 caps
P10_R1000 = 5_000e6    # pretend p10 of current R1000 caps (live run: ~$5.0B)


# ── classify ────────────────────────────────────────────────────────────────
def test_outsider_above_the_band_is_an_r2000_add_candidate():
    hit = classify("EMAT", 600e6, in_r1000=False, in_r3000=False,
                   r2000_p25=P25_R2000, r1000_p10=P10_R1000)
    assert hit == {"board": "add_r2000", "cap": 600e6}


def test_outsider_below_the_band_is_nothing():
    assert classify("TINY", 80e6, False, False, P25_R2000, P10_R1000) is None


def test_r2000_member_sized_for_r1000_is_a_promotion():
    hit = classify("GROWN", 6_000e6, in_r1000=False, in_r3000=True,
                   r2000_p25=P25_R2000, r1000_p10=P10_R1000)
    assert hit == {"board": "promote_r1000", "cap": 6_000e6}


def test_r2000_member_not_sized_up_is_nothing():
    assert classify("MID", 3_000e6, False, True, P25_R2000, P10_R1000) is None


def test_r1000_member_is_never_a_candidate_even_when_huge():
    assert classify("AAPL", 3_500_000e6, True, True, P25_R2000, P10_R1000) is None


def test_no_cap_data_is_nothing_not_a_guess():
    assert classify("X", None, False, False, P25_R2000, P10_R1000) is None
    assert classify("X", 0, False, False, P25_R2000, P10_R1000) is None


def test_missing_band_yardstick_refuses_rather_than_admits_everyone():
    # p25 unknown (empty member cap sample) -> no add candidates at all
    assert classify("Y", 600e6, False, False, None, P10_R1000) is None
    assert classify("Z", 9_999e6, False, True, P25_R2000, None) is None


def test_giant_outsider_is_rejected_as_almost_certainly_ineligible():
    # The first live run's "top adds" were ASML/BABA/RY — foreign names
    # Russell will never take. An outsider already sized for the R1000 is
    # a foreign/ineligible tell, not a missed add.
    assert classify("ASML", 651_000e6, False, False, P25_R2000, P10_R1000) is None


def test_emat_shaped_outsider_inside_the_window_is_an_add():
    # EMAT at ~$2.4B: above p25 of R2000, below p10 of R1000 — exactly the
    # window. (It is ALSO the known false-positive shape: already
    # preliminarily added effective 2026-09-21, baseline files older.)
    hit = classify("EMAT", 2_400e6, False, False, P25_R2000, P10_R1000)
    assert hit == {"board": "add_r2000", "cap": 2_400e6}


# ── _pctl ───────────────────────────────────────────────────────────────────
def test_pctl_nearest_rank_on_sorted_values():
    vals = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert _pctl(vals, 0) == 10.0
    assert _pctl(vals, 50) == 30.0
    assert _pctl(vals, 100) == 50.0
    assert _pctl(vals, 25) == 20.0


def test_pctl_empty_is_none():
    assert _pctl([], 25) is None


# ── add dates (Ajay 2026-09-02: "add the dates of these candidates additions") ─
from datetime import date  # noqa: E402


def test_schedule_is_ftse_published_dates_in_order():
    ev = rw.SCHEDULE["events"]
    keys = [e["key"] for e in ev]
    assert keys == ["recon_jun_2026", "ipo_q3_2026", "recon_dec_2026"]
    for e in ev:
        for k in ("rank_day", "prelim", "effective_close", "in_index"):
            date.fromisoformat(e[k])
        assert e["rank_day"] < e["prelim"] < e["effective_close"] < e["in_index"]
    dec = ev[-1]
    assert (dec["rank_day"], dec["prelim"], dec["effective_close"], dec["in_index"]) == \
        ("2026-10-30", "2026-11-13", "2026-12-11", "2026-12-14")        # FTSE notice 05-Nov-2025
    assert dec["ipo_window"] == ["2026-08-03", "2026-10-30"]
    q3 = ev[1]
    assert (q3["prelim"], q3["in_index"]) == ("2026-08-21", "2026-09-21")  # EMAT release 24-Aug-2026
    assert rw.SCHEDULE["sources"] and rw.SCHEDULE["verified_on"] == "2026-09-02"


def test_add_event_promotion_waits_for_the_reconstitution():
    e = rw.add_event("promote_r1000", None, date(2026, 9, 2))
    assert e["key"] == "recon_dec_2026" and e["in_index"] == "2026-12-14"
    assert e["lists_published"] is False


def test_add_event_ipo_inside_the_q3_window_rides_the_ipo_add_with_lists_out():
    e = rw.add_event("add_r2000", "2026-06-10", date(2026, 9, 2))
    assert e["key"] == "ipo_q3_2026" and e["in_index"] == "2026-09-21"
    assert e["lists_published"] is True and e["listed"] == "2026-06-10"


def test_add_event_ipo_in_the_december_window_and_old_names_go_to_december():
    assert rw.add_event("add_r2000", "2026-08-20", date(2026, 9, 2))["key"] == "recon_dec_2026"
    assert rw.add_event("add_r2000", "2019-03-01", date(2026, 9, 2))["key"] == "recon_dec_2026"
    assert rw.add_event("add_r2000", None, date(2026, 9, 2))["key"] == "recon_dec_2026"


def test_add_event_after_the_q3_effective_date_falls_through_to_december():
    e = rw.add_event("add_r2000", "2026-06-10", date(2026, 9, 25))
    assert e["key"] == "recon_dec_2026"


def test_add_event_refuses_to_guess_past_the_loaded_calendar():
    assert rw.add_event("add_r2000", "2026-06-10", date(2026, 12, 12)) is None
    assert rw.upcoming_events(date(2027, 1, 5)) == []


class _FakeColl:
    def __init__(self):
        self.docs = {}
    def find_one(self, q):
        return self.docs.get(q["_id"])
    def update_one(self, q, u, upsert=False):
        d = self.docs.setdefault(q["_id"], {"_id": q["_id"]})
        d.update(u["$set"])


def test_first_seen_ledger_seeds_from_the_prior_board_then_sticks():
    coll = _FakeColl()
    prior = {"as_of": "2026-09-01T04:00:00Z",
             "adds_r2000": [{"board": "add_r2000", "symbol": "SYM"}], "promotions_r1000": []}
    rows = [{"board": "add_r2000", "symbol": "SYM"}, {"board": "add_r2000", "symbol": "NEWB"}]
    rw.stamp_first_seen(rows, prior, coll, "2026-09-02T12:00:00Z")
    assert rows[0]["first_seen"] == "2026-09-01T04:00:00Z"      # was on yesterday's board
    assert rows[1]["first_seen"] == "2026-09-02T12:00:00Z"      # genuinely new today
    # next build: the ledger wins, last_seen advances
    rows2 = [{"board": "add_r2000", "symbol": "SYM"}]
    rw.stamp_first_seen(rows2, None, coll, "2026-09-03T12:00:00Z")
    assert rows2[0]["first_seen"] == "2026-09-01T04:00:00Z"
    assert coll.docs["add_r2000:SYM"]["last_seen"] == "2026-09-03T12:00:00Z"


def test_first_seen_without_mongo_is_none_not_today():
    rows = [{"board": "promote_r1000", "symbol": "BIG"}]
    rw.stamp_first_seen(rows, None, None, "2026-09-02T12:00:00Z")
    assert rows[0]["first_seen"] is None


def test_method_note_no_longer_calls_the_ipo_add_the_second_reconstitution():
    import inspect
    src = inspect.getsource(rw)
    assert "second 2026 recon is effective 2026-09-21" not in src
    assert "effective 2026-12-11" in src
