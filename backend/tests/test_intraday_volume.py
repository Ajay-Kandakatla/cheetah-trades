"""Intraday volume projection (sepa/intraday_volume.py) — the curve-aware
full-session extrapolation that replaced the naive today_vol/session_fraction.

Book: TLSW p.229 ("Extrapolating Volume Intraday") — project the day's volume
properly; the morning trades heavier, so a hot open is not a hot day. The 1.5x
confirmation bar (p.203) lives in the engine; this module only makes the
PROJECTION honest and conservative.

REGRESSION: CGNX (2026-06-22) cleared its pivot on an opening burst and read a
fake ~2x projected RelVol at ~10am under the LINEAR projection; the engine
bought and it faded to 0.72x by the close. The curve must read that same early
volume BELOW the linear figure (and below the 1.5x gate).

Host-runnable (py3.9, stdlib only — no pandas):
    cd backend && python3 -m pytest tests/test_intraday_volume.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sepa import intraday_volume as IV


# ── the curve: shape, bounds, monotonicity, CONSERVATISM ────────────────────

def test_curve_boundaries():
    assert IV.expected_session_volume_fraction(0.0) == 0.0
    assert IV.expected_session_volume_fraction(1.0) == 1.0
    # pre-open / after-close clamp
    assert IV.expected_session_volume_fraction(-0.5) == 0.0
    assert IV.expected_session_volume_fraction(1.7) == 1.0


def test_curve_is_monotonic_non_decreasing():
    prev = -1.0
    f = 0.0
    while f <= 1.0001:
        v = IV.expected_session_volume_fraction(f)
        assert v >= prev - 1e-9, f"curve dipped at f={f}: {v} < {prev}"
        prev = v
        f += 0.01


def test_curve_is_conservative_above_the_diagonal():
    """The whole point: expected fraction >= elapsed fraction across the
    session, so projecting today_vol / expected never over-credits a hot open
    the way today_vol / elapsed does. Strictly conservative in (0, 1)."""
    f = 0.02
    while f < 1.0:
        v = IV.expected_session_volume_fraction(f)
        assert v >= f - 1e-9, f"curve below diagonal at f={f}: {v} < {f}"
        f += 0.02


def test_curve_interpolates_between_anchors():
    # halfway between (0.077, 0.130) and (0.154, 0.210) -> ~0.170
    mid = IV.expected_session_volume_fraction((0.077 + 0.154) / 2)
    assert abs(mid - 0.17) < 0.01


# ── projection: None-safety + curve < linear early (the fix) ────────────────

def test_projection_none_when_no_volume_or_preopen():
    assert IV.project_full_session_volume(None, 0.3) is None
    assert IV.project_full_session_volume(0, 0.3) is None
    assert IV.project_full_session_volume(1_000, 0.0) is None     # pre-open
    assert IV.projected_relvol(1_000, 5_000, 0.0) is None
    assert IV.projected_relvol(1_000, None, 0.3) is None          # no avg
    assert IV.projected_relvol(1_000, 0, 0.3) is None             # zero avg


def test_curve_projection_is_lower_than_linear_in_the_morning():
    """At frac 0.1 the linear projection divides by 0.10; the curve divides by
    ~0.15 — so the curve estimate is materially SMALLER (harder to clear)."""
    today_vol, frac = 200_000.0, 0.10
    linear = (today_vol / frac)
    curve = IV.project_full_session_volume(today_vol, frac)
    assert curve < linear
    assert curve / linear < 0.8          # at least ~20% haircut this early


def test_curve_and_linear_converge_at_the_close():
    today_vol = 1_234_567.0
    curve = IV.project_full_session_volume(today_vol, 1.0)
    assert abs(curve - today_vol) < 1e-6     # f=1 -> no projection needed


# ── CGNX regression: morning pop blocked, real breakout still passes ────────

AUTO_RELVOL_MIN = 1.5     # mirrors trading.auto_entry.AUTO_RELVOL_MIN (p.203)


def test_cgnx_morning_pop_reads_below_the_gate():
    """CGNX-shape: by ~10am (frac 0.10) it had traded only ~0.20x its 50-day
    average (an opening pop, not a real surge). LINEAR projects 0.20/0.10 =
    2.0x -> FALSE breakout cleared the 1.5x gate. The curve projects it BELOW
    1.5x, so the engine would NOT buy."""
    avg50 = 1_000_000.0
    today_vol = 0.20 * avg50                    # 20% of avg done by frac 0.10
    frac = 0.10
    linear_relvol = round((today_vol / frac) / avg50, 2)
    curve_relvol = IV.projected_relvol(today_vol, avg50, frac)
    assert linear_relvol >= AUTO_RELVOL_MIN     # the OLD bug: linear passed
    assert curve_relvol < AUTO_RELVOL_MIN       # the FIX: curve blocks it


def test_genuine_high_volume_breakout_still_clears():
    """A real volume-confirmed breakout — already trading ~0.40x of its full
    average by frac 0.10 (a true surge) — still projects well above 1.5x, so
    the fix does not strangle legitimate entries."""
    avg50 = 1_000_000.0
    today_vol = 0.40 * avg50
    relvol = IV.projected_relvol(today_vol, avg50, 0.10)
    assert relvol >= AUTO_RELVOL_MIN


def test_late_session_real_fade_not_rescued():
    """NEGATIVE: a name that has only done 0.6x average by the close projects
    ~0.6x — the curve never inflates a genuinely light day into a pass."""
    avg50 = 1_000_000.0
    relvol = IV.projected_relvol(0.6 * avg50, avg50, 1.0)
    assert relvol is not None and relvol < AUTO_RELVOL_MIN
