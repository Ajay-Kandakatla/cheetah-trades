"""Locks the coiling / near-R1 indicators + the leaderboard breakout detector
(Ajay 2026-06-03)."""
from sepa.leaderboard import _coiling, _near_r1
from sepa.leaderboard_breakout_watch import _is_fresh_breakout, fresh_breakouts


# ── coiling ────────────────────────────────────────────────────────────────
def test_coiling_true_tight_drying_not_broken():
    vcp = {"has_base": True, "volume_drying": True, "final_contraction_pct": 4.0}
    assert _coiling(ready=True, buyable=False, vcp=vcp, vol={}) is True


def test_coiling_false_already_buyable():
    vcp = {"has_base": True, "volume_drying": True, "final_contraction_pct": 4.0}
    assert _coiling(ready=True, buyable=True, vcp=vcp, vol={}) is False


def test_coiling_false_when_base_loose():
    vcp = {"has_base": True, "volume_drying": True, "final_contraction_pct": 9.0}
    assert _coiling(ready=True, buyable=False, vcp=vcp, vol={}) is False


def test_coiling_via_vol_dryup_ratio():
    vcp = {"has_base": True, "volume_drying": False, "final_contraction_pct": 5.0}
    assert _coiling(ready=True, buyable=False, vcp=vcp, vol={"vol_dryup": 0.7}) is True


# ── near R1 ──────────────────────────────────────────────────────────────────
def test_near_r1_within_band():
    near, r1, dist = _near_r1(100.0, [{"label": "R1", "price": 103.0}])
    assert near is True and r1 == 103.0 and dist == 3.0


def test_near_r1_too_far():
    near, _r1, dist = _near_r1(100.0, [{"label": "R1", "price": 110.0}])
    assert near is False and dist == 10.0


def test_near_r1_no_targets():
    near, r1, dist = _near_r1(100.0, [])
    assert near is False and r1 is None and dist is None


# ── fresh breakout detection ─────────────────────────────────────────────────
def test_fresh_breakout_only_today_on_volume():
    live = {
        "AAA": {"volume": {"high_vol_breakout": True, "days_since_breakout": 0},
                "last_close": 10.0, "day_change_pct": 5.0, "rs_rank": 95},
        "BBB": {"volume": {"high_vol_breakout": True, "days_since_breakout": 3}},   # stale
        "CCC": {"volume": {"high_vol_breakout": False, "days_since_breakout": 0}},  # no breakout
    }
    out = fresh_breakouts({"AAA", "BBB", "CCC", "DDD"}, live)
    assert {o["symbol"] for o in out} == {"AAA"}
    assert out[0]["last_close"] == 10.0 and out[0]["rs_rank"] == 95
    assert _is_fresh_breakout(live["BBB"]) is False
