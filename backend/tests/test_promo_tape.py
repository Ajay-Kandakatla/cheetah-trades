"""Promo tag tape (catalysts/promo_tape.py) — before / mid-run / after read."""
from datetime import datetime, timezone

from catalysts import promo_tape as pt

T0 = int(datetime(2026, 9, 2, 13, 0, tzinfo=timezone.utc).timestamp() * 1000)   # 9:00 ET
M = 60_000


def _bar(t, o, h, l, c, s="rth"):
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": 1000.0, "s": s}


def _flat_then_run(tag_offset_min):
    """Flat at 3.00 for 2h, then a run to 4.00 from 9:30 ET, fading to 3.60."""
    bars = [_bar(T0 - (120 - i * 5) * M, 3.0, 3.02, 2.98, 3.0, "premarket") for i in range(24)]
    ramp = [3.0 + 0.1 * k for k in range(1, 11)]                              # 3.1 ... 4.0
    bars += [_bar(T0 + (30 + k * 5) * M, p - 0.05, p + 0.02, p - 0.08, p) for k, p in enumerate(ramp)]
    bars += [_bar(T0 + (90 + k * 5) * M, 3.9 - 0.05 * k, 3.92 - 0.05 * k, 3.85 - 0.05 * k, 3.9 - 0.05 * k) for k in range(6)]
    tags = [{"handle": "topstockalerts", "tier": "A", "which": "first",
             "at": datetime.fromtimestamp((T0 + tag_offset_min * M) / 1000, tz=timezone.utc).isoformat()}]
    return bars, tags


def test_tag_before_the_move_reads_before():
    bars, tags = _flat_then_run(0)                                              # tagged at 9:00, run starts 9:35
    a = pt.analyze(bars, tags)
    assert a["verdict"] == "BEFORE_THE_MOVE" and a["price_at_tag"] == 3.0
    assert a["before_pct"] == 0.0 and a["peak_pct"] == round((4.02 / 3.0 - 1) * 100, 1)
    assert "BEFORE the move" in a["read"] and a["mins_to_peak"] == 75   # 4.02 high prints at 10:15 ET


def test_tag_mid_run_reads_mid_run():
    bars, tags = _flat_then_run(55)                                             # tagged at 9:55, price 3.5 already
    a = pt.analyze(bars, tags)
    assert a["verdict"] == "MID_RUN" and a["price_at_tag"] == 3.6          # the 9:55 bar
    assert a["before_pct"] == round((3.6 / 3.0 - 1) * 100, 1)


def test_tag_after_the_peak_reads_after():
    bars, tags = _flat_then_run(95)                                             # tagged at 10:35 on the way down
    a = pt.analyze(bars, tags)
    assert a["verdict"] == "AFTER_THE_MOVE" and "AFTER the move" in a["read"]
    assert a["now_pct"] < 0


def test_negatives():
    assert pt.analyze([], [{"at": "2026-09-02T13:00:00+00:00"}])["verdict"] is None
    assert pt.analyze([_bar(T0, 1, 1, 1, 1)], [])["verdict"] is None
    bars, tags = _flat_then_run(0)
    late = [{"handle": "x", "tier": "B", "which": "first", "at": "2026-09-02T23:00:00+00:00"}]
    assert pt.analyze(bars, late)["verdict"] == "NO_TAPE_AFTER"                # tag after the last bar
    assert pt._price_at(bars, bars[0]["t"] - 1) is bars[0]                     # before the first bar -> first bar


def test_route_and_tag_marker_shape():
    from pathlib import Path
    assert '"/catalysts/promo-circuit/tape/{ticker}"' in (Path(__file__).resolve().parents[1] / "catalysts" / "api.py").read_text()
    assert pt._as_utc("2026-09-02T13:00:00Z").tzinfo is not None and pt._as_utc("nope") is None


def test_every_marker_carries_its_own_before_and_after():
    bars, tags = _flat_then_run(0)
    tags.append({"handle": "beppels", "tier": "A", "which": "first",
                 "at": datetime.fromtimestamp((T0 + 55 * M) / 1000, tz=timezone.utc).isoformat()})
    a = pt.analyze(bars, tags)
    assert "@topstockalerts first" in a["read"]
    assert tags[0]["price_at"] == 3.0 and tags[0]["before_pct"] == 0.0 and tags[0]["peak_after_pct"] == 34.0
    assert tags[1]["price_at"] == 3.6 and tags[1]["before_pct"] == 20.0 and tags[1]["peak_after_pct"] == round((4.02 / 3.6 - 1) * 100, 1)


def test_markers_prefer_every_stored_post_over_first_last(monkeypatch):
    import catalysts.promo_circuit as pc
    class _Coll:
        def find(self, q): return [{"account": "topstockalerts", "ticker": "TLYS", "tier": "A",
                                    "first_tagged_at": "2026-09-01T13:23:00+00:00", "last_tagged_at": "2026-09-02T19:35:00+00:00",
                                    "posts": [{"id": 12, "at": "2026-09-02T19:35:00+00:00", "body": "looks much better now"},
                                              {"id": 11, "at": "2026-09-01T13:23:00+00:00", "body": "watch"}]},
                                   {"account": "beppels", "ticker": "TLYS", "tier": "A",
                                    "first_tagged_at": "2026-09-02T12:00:00+00:00", "last_tagged_at": "2026-09-02T12:00:00+00:00"}]
    monkeypatch.setattr(pc, "_coll", lambda name: _Coll())
    tags = pt.tags_for_ticker("tlys")
    assert [(t["handle"], t["which"], t["at"][:16]) for t in tags] == [
        ("topstockalerts", "first", "2026-09-01T13:23"), ("beppels", "first", "2026-09-02T12:00"),
        ("topstockalerts", "post", "2026-09-02T19:35")]
    assert tags[2]["sample"] == "looks much better now" and tags[2]["msg_id"] == 12


def test_lite_payload_keeps_every_third_bar_plus_last_and_trims():
    from catalysts import promo_tape as _pt
    bars = [{"t": i, "o": 1, "h": 2, "l": 0.5, "c": 1 + i, "v": 9, "s": "rth"} for i in range(7)]
    p = {"ticker": "X", "bars": bars, "tf": "5min",
         "tags": [{"handle": "h", "tier": "B", "at": "2026-09-01T00:00:00+00:00", "which": "first",
                   "sample": "long body", "msg_id": 1, "price_at": 1.0}],
         "verdict": "MID_RUN", "read": "r", "peak_pct": 5.0}
    lite = _pt.lite_payload(p)
    assert [b["t"] for b in lite["bars"]] == [0, 3, 6] and set(lite["bars"][0]) == {"t", "c", "s"}
    assert lite["n_bars"] == 7 and lite["lite"] is True and lite["verdict"] == "MID_RUN"
    assert "sample" not in lite["tags"][0] and lite["tags"][0]["price_at"] == 1.0
    bars8 = bars + [dict(bars[0], t=7)]
    assert [b["t"] for b in _pt.lite_payload({"bars": bars8})["bars"]] == [0, 3, 6, 7]
    assert _pt.lite_payload({})["bars"] == [] and _pt.lite_payload({})["tags"] == []


def test_tape_route_takes_the_lite_flag():
    import inspect
    from catalysts import api
    src = inspect.getsource(api.get_promo_tape)
    assert "lite: bool = Query(False)" in src and "lite_payload(payload) if lite" in src
