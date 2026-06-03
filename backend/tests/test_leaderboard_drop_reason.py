"""Locks the leaderboard 'why it dropped' reason (sepa/leaderboard._drop_reason).

Most-severe signal first: Stage downgrade > distribution cluster (book p.76) >
volume turning > relative ease. Ajay 2026-06-03 ("why these went down").
"""
from sepa.leaderboard import _drop_reason


def test_stage_downgrade_wins_over_everything():
    assert "Stage 3" in _drop_reason(3, 5, "distributing")


def test_distribution_cluster_when_stage_ok():
    r = _drop_reason(2, 4, "accumulating")
    assert "distribution days" in r and r.startswith("4")


def test_volume_distributing():
    assert "distributing" in _drop_reason(2, 1, "distributing")


def test_volume_neutral():
    assert "cooled" in _drop_reason(2, 0, "neutral")


def test_relative_fallback_when_no_red_flag():
    assert "peers" in _drop_reason(2, 0, "accumulating")
