"""The 🚩 card's trigger line says BUY only when the read IS the entry (2026-10-21).

Ajay, on a NAUT 🚩 Bull Flag card that read "broke — not A+ · missed: K3 pullback volume ≤ 0.5× leg mean" while the
chart printed "BUY > 2.72": "So Gajjalas entries are only for A+ stock setups right? Why does this chart in potential
say buy? If its in Buy at the rate why is it not in A+?" — tab._tile_lines printed BUY for every read with a trigger.
Now: A+ or a ready forming read → "BUY > x" (tone buy); partial / not-ready forming / triggered / stopped / invalid →
"TRIGGER x" (the tone stays buy — the line style and the ladder's Entry row key on it). NEGATIVES: no trigger → no trigger line; the STOP line never changes; the lane's A+ claim
(alerts) is not touched by this file — it reads the detector state, not the chart label.
"""
from __future__ import annotations

import pytest

from chart_maps.gajjala import tab as GT

T, S = 2.72, 2.64


def _read(state, **kw):
    r = {"state": state, "trigger": T, "stop": S, "ready": None}
    r.update(kw)
    return r


@pytest.mark.parametrize("read, label, tone", [
    (_read("aplus", ready=True), "BUY > 2.72", "buy"),
    (_read("aplus"), "BUY > 2.72", "buy"),                                   # A+ is the entry whatever `ready` says
    (_read("forming", ready=True), "BUY > 2.72", "buy"),                     # the next bar over it would be the entry
    (_read("forming", ready=False), "TRIGGER 2.72", "buy"),              # not ready yet
    (_read("forming"), "TRIGGER 2.72", "buy"),                           # ready None is not True
    (_read("partial", missed=["k3_vol"], broke=True), "TRIGGER 2.72", "buy"),   # NAUT: broke — not A+
    (_read("partial", missed=["k3_vol"]), "TRIGGER 2.72", "buy"),
    (_read("triggered"), "TRIGGER 2.72", "buy"),                         # the entry has passed
    (_read("stopped"), "TRIGGER 2.72", "buy"),
    (_read("invalid"), "TRIGGER 2.72", "buy"),
])
def test_trigger_line_word_follows_the_state(read, label, tone):
    lines = GT._tile_lines(read)
    assert lines[0] == {"price": T, "label": label, "tone": tone}
    assert lines[1] == {"price": S, "label": "STOP 2.64", "tone": "stop"}    # the stop line never changes


def test_NEGATIVE_no_trigger_no_trigger_line_and_a_bool_ready_is_required():
    assert GT._tile_lines({"state": "forming", "trigger": None, "stop": S}) == [{"price": S, "label": "STOP 2.64", "tone": "stop"}]
    assert GT._tile_lines({"state": "none"}) == []
    assert GT._is_entry_read({"state": "forming", "trigger": T, "ready": 1}) is False     # truthy is not True
    assert GT._is_entry_read({"state": "forming", "trigger": T, "ready": "yes"}) is False
    assert GT._is_entry_read({}) is False and GT._is_entry_read(None) is False


def test_the_word_buy_never_prints_with_a_missed_rule():
    for st in ("partial", "forming", "triggered", "stopped", "invalid"):
        for ready in (None, False, True):
            r = _read(st, ready=ready, missed=["k3_vol"])
            if st == "forming" and ready is True:
                continue                                                      # a ready forming read has no missed rule by construction
            assert "BUY" not in GT._tile_lines(r)[0]["label"], (st, ready)
