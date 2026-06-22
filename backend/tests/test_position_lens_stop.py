"""Position-lens stop anchoring — behavioral + regression (2026-06-22).

The hold/sell verdict measures against a stop that is ANCHORED TO YOUR ENTRY and
only ever RAISED, never widened on a loser (Minervini pp.295, 308-309, 311).

BUG (ARM): the old code used the trade-plan stop alone — ≈7% below the *current*
price — which for an underwater holder sits BELOW the entry stop. That widened the
cut line as the stock fell and hid a breached ENTRY stop behind a HOLD verdict.
ARM held at $445.43 (entry stop $414.25) read HOLD at $404.69 because the displayed
stop was $382.39 (7% below the falling price). The fix anchors the auto stop to the
entry-based 7% line as a floor.
"""
from sepa.position_lens import _resolve_stop


def test_underwater_holder_uses_entry_stop_not_plan_stop():
    """REGRESSION (ARM): entry $445.43 → 7% entry stop $414.25. A trade-plan stop
    of $382.39 (below the entry stop) must NOT be used — the stop stays anchored
    at the entry line, so a holder at $404.69 reads as BREACHED, not HOLD."""
    stop, source = _resolve_stop(445.43, 382.39, None)
    assert stop == 414.25
    assert source == "entry_7pct"
    # the corrected stop is breached at the current price; the old $382.39 was not
    assert 404.69 <= stop          # → stop_loss_breached → SELL
    assert not (404.69 <= 382.39)  # the old (buggy) stop would have read HOLD


def test_stop_never_wider_than_entry_7pct_on_auto():
    """The auto stop is never LOOSER (lower) than 7% from entry, for any
    plan stop at or below that line (p.308-309 — don't widen on a loser)."""
    for plan in (None, 1.0, 380.0, 414.24, 414.25):
        stop, _ = _resolve_stop(445.43, plan, None)
        assert stop >= round(445.43 * 0.93, 2)


def test_winner_trail_above_entry_stop_is_used():
    """A position in profit whose trade-plan / trail stop has RISEN above the
    entry stop uses that tighter (higher) trail (raising stops is allowed)."""
    stop, source = _resolve_stop(100.0, 185.0, None)
    assert stop == 185.0
    assert source == "trade_plan_trail"


def test_user_stop_is_honored():
    """A user-supplied stop is the holder's explicit line and wins."""
    stop, source = _resolve_stop(100.0, 90.0, 95.0)
    assert stop == 95.0
    assert source == "user"


def test_no_plan_stop_falls_back_to_entry_stop():
    stop, source = _resolve_stop(100.0, None, None)
    assert stop == 93.0
    assert source == "entry_7pct"


# ── negative / edge ──────────────────────────────────────────────────────────
def test_zero_or_negative_user_stop_ignored():
    """A 0 / negative user stop is not a real line — fall through to the anchor."""
    stop, source = _resolve_stop(100.0, None, 0)
    assert (stop, source) == (93.0, "entry_7pct")


def test_plan_stop_exactly_at_entry_stop_does_not_widen():
    """A plan stop equal to the entry stop is not 'above' it → stays entry-anchored
    (strict >), so equality can never be used to nudge the stop looser."""
    entry_stop = round(100.0 * 0.93, 2)
    stop, source = _resolve_stop(100.0, entry_stop, None)
    assert stop == entry_stop
    assert source == "entry_7pct"
