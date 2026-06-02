"""Entry-decision Stage-2 gate — behavioral + regression (2026-06-02).

Bug (SMCI-class): the green "ENTER" banner came from `entry_exit._decide`, which
only checked stage to REJECT Stage 3/4. A Stage 1 base that fired a one-day
pocket-pivot/volume pop with price at the pivot read "actionable + volume-
confirmed" → ENTER — contradicting the card's own WATCH verdict and "S1 · Basing"
label. Minervini buys ONLY a confirmed Stage 2 advance (Trade Like a Stock Market
Wizard, pp.39-71 stage analysis; pp.79-83 Trend Template).

Fix: `_decide` now requires book buyable-eligibility for ENTER — the scanner's
strict `_is_setup_ready` (Trend Template 8/8 + Stage 2 + setup + not late-stage +
liquid), passed in as `setup_ready`; falling back to `stage == 2` when called
standalone. This locks the green banner to the same gate as `is_buyable`.
"""
from sepa.entry_exit import build_entry_exit


def _plan(pivot=100.0, lo=100.0, hi=102.5, stop=93.0):
    return {
        "entries": {"aggressive": pivot},
        "buy_zone": {"lo": lo, "hi": hi},
        "stop": {"recommended": stop, "recommended_label": "base low"},
        "targets": {"r1": 110.0, "r2": 120.0, "r3": 135.0},
    }


def _ee(*, stage_num, setup_ready, last_close=101.0, vol=None):
    """Build an entry_exit verdict for a name sitting IN the buy zone with the
    given stage + setup_ready. df=None ⇒ ADX None ⇒ chop check skipped, so the
    stage gate is what decides between ENTER and WAIT."""
    return build_entry_exit(
        last_close=last_close,
        trade_plan=_plan(),
        df=None,
        stage={"stage": stage_num},
        vol=vol if vol is not None else {"high_vol_breakout": True},
        setup_ready=setup_ready,
    )


def test_stage2_buyable_still_enters():
    """Happy path unchanged: a Stage 2, setup_ready name in the zone on volume
    is the green light (book pp.79-83, 203)."""
    d = _ee(stage_num=2, setup_ready=True)
    assert d["decision"] == "ENTER"
    assert d["decision_color"] == "green"
    assert d["entry"]["status"] == "actionable"


def test_stage1_basing_never_enters():
    """REGRESSION (SMCI): Stage 1 basing + in-zone volume pop must NOT say ENTER.
    Minervini buys only Stage 2 — a base breakout has to confirm the Stage 1→2
    transition first."""
    d = _ee(stage_num=1, setup_ready=False)
    assert d["decision"] != "ENTER"
    assert d["decision"] == "WAIT"
    assert d["decision_color"] != "green"
    assert "Stage 2" in d["decision_reason"]          # tells the user WHY


def test_stage1_standalone_fallback_never_enters():
    """With no scanner setup_ready passed (standalone use), the gate falls back to
    stage==2 — so a Stage 1 name still cannot reach ENTER."""
    d = _ee(stage_num=1, setup_ready=None)
    assert d["decision"] != "ENTER"


def test_stage3_topping_never_enters():
    """Stage 3 (topping) in the zone is stand-aside, not a buy — even when the
    volume pop isn't outright distribution."""
    d = _ee(stage_num=3, setup_ready=False)
    assert d["decision"] != "ENTER"
    assert "Stage" in d["decision_reason"]


def test_stage2_failing_trend_template_holds_not_enter():
    """Stage 2 by MA geometry but setup_ready False (e.g. Trend Template only 7/8,
    or late-stage base) is NOT a clean book buy → HOLD_WATCH, not ENTER."""
    d = _ee(stage_num=2, setup_ready=False)
    assert d["decision"] != "ENTER"
    assert d["decision_color"] != "green"


def test_stage2_standalone_fallback_enters():
    """Standalone fallback (setup_ready=None) still greenlights a genuine Stage 2
    breakout via the stage==2 path — the gate doesn't over-block."""
    d = _ee(stage_num=2, setup_ready=None)
    assert d["decision"] == "ENTER"
    assert d["decision_color"] == "green"
