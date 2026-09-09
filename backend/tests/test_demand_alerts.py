"""supply_demand/demand_alerts — $1B+ names at / nearing a tested demand band.

Behavioural tests on synthetic boards + source guards for the wiring (pref
default, crontab line, notifications page). Ajay 2026-09-03.
"""
import sys

import pytest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import demand_alerts as DA  # noqa: E402

ET = ZoneInfo("America/New_York")
IN_SESSION = datetime(2026, 9, 3, 11, 0, tzinfo=ET)
ROOT = Path(__file__).resolve().parents[2]


class FakeColl:
    def __init__(self):
        self.docs = {}

    def find_one(self, q):
        return self.docs.get(q["_id"])

    def update_one(self, q, u, upsert=False):
        d = self.docs.setdefault(q["_id"], {"_id": q["_id"]})
        d.update(u.get("$set", {}))


def _band(lo, hi, touches=3, strength=50.0):
    return {"lo": lo, "hi": hi, "touches": touches, "strength": strength}


def _board(appr=(), rows=()):
    return {"approaching_rows": [{"symbol": s, "name": f"{s} Inc",
                                  "approaching": {"band": b}} for s, b in appr],
            "rows": [{"symbol": s, "name": f"{s} Inc", "entry_zone": b} for s, b in rows]}


@pytest.fixture(autouse=True)
def _no_mood_by_default(monkeypatch):
    """Mood is CONTEXT on the alert (2026-09-08) and it reads daily bars. In a
    unit test that would make every pinned body depend on the local price
    cache, so the default here is "unknown mood"; the mood tests stub their
    own."""
    monkeypatch.setattr(DA.AG, "mood_read", lambda sym, frame=None: None)

    # Bullish reversal, not a falling knife (2026-09-09). Both read DAILY bars,
    # so in a unit test they would make every pinned body depend on the local
    # price cache. Default here is "clean structure, bullish turn" so a test
    # whose subject is caps, dedupe, digests or mood keeps testing THAT; the
    # gate tests stub their own. The things-to-see block is off by default —
    # it reaches the network.
    monkeypatch.setattr(DA.AG, "daily_frame", lambda sym, frame=None: frame)
    monkeypatch.setattr(DA.AG, "knife_read",
                        lambda sym, frame=None: {"knife": False, "trend": "rising"})
    monkeypatch.setattr(DA.AG, "reversal_mood_read",
                        lambda sym, frame=None, bars=None: {"score": 40.0, "label": "bullish",
                                                            "bars": 60, "bullish": True})
    monkeypatch.setattr(DA.BC, "bullish_context",
                        lambda sym, frame=None, with_sentiment=True: {"gex": None, "patterns": None,
                                                                      "sentiment": None})


def _live_bouncing(**px):
    """`_live` with a day low just under each print, so every row reads as
    BOUNCING off its band.

    Since 2026-09-09 that is the ONLY approach the phone takes (Ajay: "Turn off
    falling in to deman alerts all together. only bouncing off alerts"), so a
    test whose subject is caps, dedupe, digests or mood has to hand the gate a
    bounce or it is really just re-testing the direction gate."""
    out = _live(**px)
    for sym, row in out.items():
        row.setdefault("low", round(row["price"] * 0.988, 4))
    return out


def _live(**px):
    """price, change_pct[, prev_day_close[, low]]. Default prev close = 5% above
    the live print, i.e. yesterday was outside every ring → today is an arrival.
    No `low` = the pre-market shape (day bar 0) → "falling into" from above,
    which since 2026-09-09 lists on the board and never reaches the phone."""
    out = {}
    for s, v in px.items():
        p, c = v[0], v[1]
        prev = v[2] if len(v) > 2 else round(p * 1.05, 4)
        out[s] = {"price": p, "change_pct": c, "prev_day_close": prev}
        if len(v) > 3:
            out[s]["low"] = v[3]
    return out


# ── the pure read ────────────────────────────────────────────────────────────
def test_inside_the_band_is_at_with_zero_distance():
    assert DA.read(100.0, _band(95, 105)) == {"tier": "at", "state": "in", "dist_pct": 0.0}


def test_within_one_percent_above_the_top_is_at():
    r = DA.read(105.5, _band(95, 105))
    assert r["tier"] == "at" and r["state"] == "above" and r["dist_pct"] == 0.47


def test_one_to_three_percent_above_and_falling_is_near():
    r = DA.read(107.0, _band(95, 105), change_pct=-0.8)
    assert r == {"tier": "near", "state": "falling", "dist_pct": 1.87}


def test_near_needs_a_down_day_flat_or_rising_is_departing():
    assert DA.read(107.0, _band(95, 105), change_pct=0.0) is None
    assert DA.read(107.0, _band(95, 105), change_pct=1.2) is None
    assert DA.read(107.0, _band(95, 105), change_pct=None) is None
    assert DA.read(107.0, _band(95, 105), change_pct="x") is None


def test_below_the_band_is_a_breakdown_not_an_approach():
    assert DA.read(94.0, _band(95, 105), change_pct=-2.0) is None
    assert DA.read(94.9, _band(95, 105)) is None


def test_beyond_three_percent_is_silent_and_garbage_never_crashes():
    assert DA.read(108.5, _band(95, 105), change_pct=-1.0) is None
    assert DA.read(0.0, _band(95, 105)) is None
    assert DA.read(None, _band(95, 105)) is None
    assert DA.read(100.0, {"lo": None, "hi": "x"}) is None
    assert DA.read(100.0, {}) is None
    assert DA.read(100.0, _band(105, 95)) is None                 # inverted band


# ── arrivals only (the 58-push dry run) ──────────────────────────────────────
def test_at_needs_yesterday_outside_the_one_percent_ring():
    band = _band(95, 105)
    assert DA.read(100.0, band, prev_close=110.0)["tier"] == "at"        # arrived today
    assert DA.read(100.0, band, prev_close=101.0) is None                # slept in the band
    assert DA.read(105.5, band, prev_close=105.8) is None                # was already at
    assert DA.read(105.5, band, prev_close=107.5)["state"] == "above"
    assert DA.read(100.0, band, prev_close=90.0)["tier"] == "at", \
        "closed under the floor yesterday, back inside today = a reclaim, still an arrival"


def test_near_needs_yesterday_outside_the_three_percent_ring():
    band = _band(95, 105)
    assert DA.read(107.0, band, change_pct=-0.8, prev_close=110.0)["tier"] == "near"
    assert DA.read(107.0, band, change_pct=-0.8, prev_close=107.5) is None   # was near already
    assert DA.read(107.0, band, change_pct=-0.8, prev_close=108.3)["tier"] == "near"  # 3.05% out
    assert DA.read(107.0, band, change_pct=-0.8, prev_close=108.2) is None            # 2.96% in


def test_unknown_prev_close_is_silent_never_a_guess(monkeypatch):
    sent = _capture(monkeypatch)
    live = {"AAPL": {"price": 205.0, "change_pct": -0.2, "prev_day_close": None}}
    out = DA.check_once(board=_board(rows=[("AAPL", _band(200, 210))]), live=live,
                        caps={"AAPL": 3e12}, coll=FakeColl(), owner="o@x",
                        now=IN_SESSION, force=True, store={})
    assert out["unknown_prev"] == 1 and out["at"] == 0 and sent == []

def test_cap_gate_is_known_and_at_least_a_billion():
    assert DA.passes_cap(2e9) is True
    assert DA.passes_cap(1e9) is True
    assert DA.passes_cap(999_999_999) is False
    assert DA.passes_cap(None) is False, "unknown cap is not a known-big company"
    assert DA.passes_cap("x") is False


def test_fmt_cap():
    assert DA.fmt_cap(3.2e12) == "$3.2T"
    assert DA.fmt_cap(12.4e9) == "$12.4B"
    assert DA.fmt_cap(None) == "cap n/a"


# ── candidates off the board ─────────────────────────────────────────────────
def test_candidates_take_the_approaching_band_and_the_reentry_zone():
    c = DA.candidates(_board(appr=[("AAA", _band(10, 11))], rows=[("BBB", _band(20, 22))]))
    assert c["AAA"]["bands"][0]["source"] == "approaching"
    assert c["BBB"]["bands"][0]["source"] == "reentry"
    assert c["AAA"]["name"] == "AAA Inc"


def test_same_band_on_both_boards_is_one_fact():
    c = DA.candidates(_board(appr=[("AAA", _band(10, 11))], rows=[("AAA", _band(10, 11))]))
    assert len(c["AAA"]["bands"]) == 1


def test_approaching_row_falls_back_to_entry_zone_and_missing_boards_are_empty():
    board = {"approaching_rows": [{"symbol": "ZZZ", "entry_zone": _band(5, 6)}]}
    assert DA.candidates(board)["ZZZ"]["bands"][0]["lo"] == 5
    assert DA.candidates(None) == {}
    assert DA.candidates({"warming": True}) == {}
    assert DA.candidates({"rows": [{"symbol": "", "entry_zone": _band(1, 2)},
                                   {"symbol": "Q", "entry_zone": {"lo": None, "hi": 2}}]}) == {}


def test_state_key_is_symbol_band_day_tier():
    assert DA.state_key("NTAP", _band(180.0, 183.5), "2026-09-03", "at") == "NTAP:180.00-183.50:2026-09-03:at"


# ── messages ─────────────────────────────────────────────────────────────────
def test_at_message_names_the_band_the_tests_and_the_cap():
    m = DA.at_message({"symbol": "NTAP", "last": 182.9, "band": _band(180, 183.5, touches=4),
                       "hit": {"tier": "at", "state": "in", "dist_pct": 0.0},
                       "cap": 37e9, "name": "NetApp"})
    assert m["title"] == "🧲 NTAP in demand $180–183.5"
    assert "tested 4x" in m["body"] and "$37.0B" in m["body"] and "NetApp" in m["body"]
    assert m["url"] == "/sepa/NTAP?tab=supply" and m["data"]["url"] == m["url"]
    assert m["kind"] == "demand_alert", "push/history.py records payload['kind']"


def test_at_message_says_which_way_it_got_here(monkeypatch):
    """Ajay 2026-09-08: "nearing demand zone from the top like falling or
    Bouncing back from Demand zone.. I need the distinction in writing"."""
    base = {"symbol": "DYN", "band": _band(17.9, 18.6, touches=3),
            "hit": {"tier": "at", "state": "in", "dist_pct": 0.0}, "cap": 1.2e9, "name": "Dyne"}
    from supply_demand import alert_gates as AG
    m = DA.at_message({**base, "last": 18.06, "approach": AG.approach_read(18.06, base["band"], 24.28, 18.05)})
    assert m["title"] == "🧲 DYN ↓ falling into demand $17.9–18.6"
    assert m["body"].startswith("$18.06 · ↓ falling into the band from 24.28 (-25.6% today) · tested 3x")
    m = DA.at_message({**base, "last": 18.27, "approach": AG.approach_read(18.27, base["band"], 24.28, 18.05)})
    assert m["title"] == "🧲 DYN ↑ bouncing off demand $17.9–18.6"
    assert m["body"].startswith("$18.27 · ↑ bouncing off the band, +1.2% off the 18.05 low · tested 3x")
    # NEGATIVE: no read (resting inside, or nothing known) keeps the old title and body
    for ap in (None, {}, AG.approach_read(18.2, base["band"], 18.3, 18.2), "junk"):
        m = DA.at_message({**base, "last": 18.2, "approach": ap})
        assert m["title"] == "🧲 DYN in demand $17.9–18.6"
        assert m["body"].startswith("$18.2 · tested 3x")
    # ABOVE the band: the distance the title used to carry moves into the body
    m = DA.at_message({**base, "last": 18.7, "hit": {"tier": "at", "state": "above", "dist_pct": 0.54},
                       "approach": AG.approach_read(18.7, base["band"], 24.28, 18.05)})
    assert m["title"] == "🧲 DYN ↑ bouncing off demand $17.9–18.6"
    assert m["body"].startswith("$18.7 · 0.54% above · ↑ bouncing off the band, +3.6% off the 18.05 low · tested 3x")


def test_at_message_reclaim_title_names_the_run_up():
    from supply_demand import alert_gates as AG
    band = _band(10.83, 11.22, touches=2)
    m = DA.at_message({"symbol": "SMR", "last": 10.835, "band": band, "cap": 4.4e9, "name": "NuScale",
                       "hit": {"tier": "at", "state": "in", "dist_pct": 0.0},
                       "approach": AG.approach_read(10.835, band, 9.70, 9.895)})
    assert m["title"] == "🧲 SMR ↑ reclaiming demand $10.83–11.22"
    assert m["body"].startswith("$10.835 · ↑ reclaiming the band from below (+11.7% today) · tested 2x")


def test_digest_lines_carry_the_direction_tag():
    from supply_demand import alert_gates as AG
    band = _band(17.9, 18.6, touches=3)
    items = [{"symbol": "DYN", "last": 18.27, "band": band, "cap": 1.2e9,
              "hit": {"tier": "at", "state": "in", "dist_pct": 0.0},
              "approach": AG.approach_read(18.27, band, 24.28, 18.05)},
             {"symbol": "FLL", "last": 18.06, "band": band, "cap": 3e9,
              "hit": {"tier": "at", "state": "in", "dist_pct": 0.0},
              "approach": AG.approach_read(18.06, band, 24.28, 18.05)},
             {"symbol": "RST", "last": 18.2, "band": band, "cap": 3e9,
              "hit": {"tier": "at", "state": "in", "dist_pct": 0.0}, "approach": None}]
    lines = DA.digest_message(items)["body"].split("\n")
    assert lines[0] == "DYN $18.27 · ↑ bouncing off $17.9–18.6 · $1.2B"
    assert lines[1] == "FLL $18.06 · ↓ falling into $17.9–18.6 · $3.0B"
    assert lines[2] == "RST $18.2 · in demand $17.9–18.6 · $3.0B"


def test_check_once_reads_the_day_low_off_the_live_row(monkeypatch):
    sent = _capture(monkeypatch)
    board = _board(rows=[("DYN", _band(17.9, 18.6))])
    store = _store("DYN", [{"kind": "demand", "lo": 17.9, "hi": 18.6, "touches": 3, "strength": 50.0}], 24.28)
    kw = dict(board=board, caps={"DYN": 1.2e9}, owner="o@x", now=IN_SESSION, force=True, store=store)
    out = DA.check_once(live=_live(DYN=(18.27, -24.8, 24.28, 18.05)), coll=FakeColl(), **kw)
    assert out["pushed"] == 1 and sent[-1]["title"] == "🧲 DYN ↑ bouncing off demand $17.9–18.6"
    assert out["hits"][0]["approach"]["dir"] == "bouncing"
    # The print sits ON the day's low → FALLING, and since 2026-09-09 falling
    # never reaches the phone (Ajay: "only bouncing off alerts"). The read is
    # still made and still listed — the push is what stops.
    n_before = len(sent)
    out = DA.check_once(live=_live(DYN=(18.06, -25.6, 24.28, 18.05)), coll=FakeColl(), **kw)
    assert out["hits"][0]["approach"]["dir"] == "falling"
    assert out["pushed"] == 0 and out["skipped_direction"] == 1 and len(sent) == n_before
    # NEGATIVE: no low on the row (pre-market) → falling from yesterday's close,
    # so it is silent too.
    out = DA.check_once(live=_live(DYN=(18.27, -24.8, 24.28)), coll=FakeColl(), **kw)
    assert out["hits"][0]["approach"]["dir"] == "falling"
    assert out["pushed"] == 0 and len(sent) == n_before


def test_digest_sorts_by_distance_and_caps_the_body():
    items = [{"symbol": f"S{i}", "last": 100.0 + i, "band": _band(90, 97), "cap": 2e9,
              "hit": {"tier": "near", "state": "falling", "dist_pct": 3.0 - i * 0.2}}
             for i in range(8)]
    m = DA.digest_message(items)
    assert m["title"] == "🧲 Nearing demand — S7 +7 more"
    lines = m["body"].split("\n")
    assert len(lines) == DA.DIGEST_MAX + 1 and lines[-1] == "+2 more on the board"
    assert lines[0].startswith("S7 $107 · 1.6% above $90–97 · $2.0B")
    assert m["url"] == "/chart-maps?tab=zones&phase=approaching"
    assert m["kind"] == "demand_alert", "push/history.py records payload['kind']"


# ── check_once end to end ────────────────────────────────────────────────────
def _capture(monkeypatch, result=None):
    from push import sender
    sent = []

    def fake(owner, payload, kind=None):
        sent.append({"owner": owner, "kind": kind, **payload})
        return result or {"sent": 1, "failed": 0, "total_targets": 1}
    monkeypatch.setattr(sender, "send_to_user", fake)
    return sent


def test_check_once_pushes_at_individually_near_as_one_digest_and_gates_cap(monkeypatch):
    sent = _capture(monkeypatch)
    board = _board(appr=[("BIGX", _band(90, 97)), ("BIGY", _band(40, 44)),
                         ("SMALL", _band(10, 11)), ("UNK", _band(50, 52))],
                   rows=[("AAPL", _band(200, 210))])
    live = _live_bouncing(BIGX=(99.0, -1.1), BIGY=(45.0, -0.4), SMALL=(11.05, -2.0),
                 UNK=(51.0, -1.0), AAPL=(211.0, -0.2))
    caps = {"BIGX": 5e9, "BIGY": 12e9, "SMALL": 5e8, "UNK": None, "AAPL": 3e12}
    coll = FakeColl()
    store = _store("AAPL", [{"kind": "demand", "lo": 200.0, "hi": 210.0, "touches": 3, "strength": 50.0}], 221.55)
    out = DA.check_once(board=board, live=live, caps=caps, coll=coll, owner="o@x",
                        now=IN_SESSION, force=True, store=store)
    # Since the phone gate (2026-09-05) the NEAR names are listed and counted, not pushed
    assert out["ran"] and out["at"] == 1 and out["near"] == 2 and out["pushed"] == 1
    assert out["skipped_cap"] == 1 and out["unknown_cap"] == 1 and out["skipped_proximity"] == 2
    assert [s["kind"] for s in sent] == ["demand_alert"]
    assert sent[0]["title"] == "🧲 AAPL ↑ bouncing off demand $200–210"   # bouncing is the only push since 2026-09-09
    assert [h["symbol"] for h in out["hits"] if h["hit"]["tier"] == "near"] == ["BIGX", "BIGY"]
    assert all(s["owner"] == "o@x" for s in sent)
    assert len(coll.docs) == 1                     # AAPL at; NEAR names are not recorded (nothing sent)


def test_dedupe_is_once_per_band_per_day_but_tiers_are_separate(monkeypatch):
    sent = _capture(monkeypatch)
    board = _board(appr=[("BIGX", _band(90, 97))])
    coll = FakeColl()
    kw = dict(board=board, caps={"BIGX": 5e9}, coll=coll, owner="o@x", now=IN_SESSION, force=True,
              store=_store("BIGX", [{"kind": "demand", "lo": 90.0, "hi": 97.0, "touches": 3, "strength": 50.0}], 103.95))
    out = DA.check_once(live=_live_bouncing(BIGX=(99.0, -1.1)), **kw)    # near → listed, not pushed (phone gate 2026-09-05)
    assert out["near"] == 1 and out["skipped_proximity"] == 1 and sent == []
    DA.check_once(live=_live_bouncing(BIGX=(99.0, -1.1)), **kw)
    assert sent == [] and coll.docs == {}, "nothing sent, nothing recorded"
    DA.check_once(live=_live_bouncing(BIGX=(96.5, -3.0)), **kw)          # arrived → at fires
    assert len(sent) == 1 and sent[0]["title"] == "🧲 BIGX ↑ bouncing off demand $90–97"
    DA.check_once(live=_live_bouncing(BIGX=(96.0, -3.5)), **kw)
    assert len(sent) == 1


def test_transport_failure_is_retried_but_muted_pref_is_terminal(monkeypatch):
    board = _board(rows=[("AAPL", _band(200, 210))])
    kw = dict(board=board, live=_live_bouncing(AAPL=(205.0, -0.2)), caps={"AAPL": 3e12},
              owner="o@x", now=IN_SESSION, force=True,
              store=_store("AAPL", [{"kind": "demand", "lo": 200.0, "hi": 210.0, "touches": 3}], 215.25))
    coll = FakeColl()
    _capture(monkeypatch, result={"sent": 0, "failed": 1, "total_targets": 1})
    out = DA.check_once(coll=coll, **kw)
    assert out["pushed"] == 0 and coll.docs == {}, "a failed transport must retry next pass"
    _capture(monkeypatch, result={"sent": 0, "failed": 0, "total_targets": 0})
    out = DA.check_once(coll=coll, **kw)
    assert out["pushed"] == 1 and len(coll.docs) == 1, "nobody targeted = done for today"


def test_dry_run_reads_everything_and_records_nothing(monkeypatch):
    sent = _capture(monkeypatch)
    coll = FakeColl()
    out = DA.check_once(push=False, board=_board(rows=[("AAPL", _band(200, 210))]),
                        live=_live_bouncing(AAPL=(205.0, 0.0)), caps={"AAPL": 3e12}, coll=coll,
                        now=IN_SESSION, force=True,
                        store=_store("AAPL", [{"kind": "demand", "lo": 200.0, "hi": 210.0, "touches": 3}], 215.25))
    assert out["at"] == 1 and out["pushed"] == 0 and sent == [] and coll.docs == {}


def test_empty_or_warming_board_is_a_quiet_pass(monkeypatch):
    sent = _capture(monkeypatch)
    out = DA.check_once(board={"warming": True}, now=IN_SESSION, force=True)
    assert out["ran"] and out["candidates"] == 0 and out["pushed"] == 0 and sent == []


# ── the session gate ─────────────────────────────────────────────────────────
def test_session_gate_blocks_weekends_and_off_hours():
    assert DA.in_session(datetime(2026, 9, 5, 11, 0, tzinfo=ET)) is False    # Sat
    assert DA.in_session(datetime(2026, 9, 3, 9, 25, tzinfo=ET)) is False    # pre-open
    assert DA.in_session(datetime(2026, 9, 3, 16, 10, tzinfo=ET)) is False   # after
    assert DA.in_session(IN_SESSION) is True


def test_check_once_refuses_outside_rth_unless_forced():
    out = DA.check_once(board={}, now=datetime(2026, 9, 3, 7, 0, tzinfo=ET))
    assert out["ran"] is False and "RTH" in out["reason"]


# ── the board over HTTP ──────────────────────────────────────────────────────
class _Resp:
    def __init__(self, code, body):
        self.status_code, self._b = code, body

    def json(self):
        return self._b


def test_fetch_board_treats_warming_errors_and_exceptions_as_nothing_to_watch(monkeypatch):
    import requests
    calls = []
    monkeypatch.setattr(requests, "get", lambda url, **kw: (calls.append((url, kw)),
                                                             _Resp(200, {"warming": True}))[1])
    assert DA.fetch_board(base="http://api:8000") is None
    assert calls[0][0].endswith("/supply-demand/demand-reentry")
    assert calls[0][1]["params"] == {"universe": "full", "limit": DA.BOARD_LIMIT}
    assert calls[0][1]["headers"]["X-User-Email"] == "cron@internal"
    monkeypatch.setattr(requests, "get", lambda url, **kw: _Resp(500, {}))
    assert DA.fetch_board(base="http://api:8000") is None

    def boom(url, **kw):
        raise ConnectionError("down")
    monkeypatch.setattr(requests, "get", boom)
    assert DA.fetch_board(base="http://api:8000") is None
    monkeypatch.setattr(requests, "get", lambda url, **kw: _Resp(200, {"rows": [1]}))
    assert DA.fetch_board(base="http://api:8000") == {"rows": [1]}


# ── source guards: the wiring ────────────────────────────────────────────────
def test_kind_is_demand_alert_with_a_default_pref_and_a_cron_line():
    assert DA.KIND == "demand_alert"
    subs = (ROOT / "backend/push/subs.py").read_text()
    assert '"demand_alert": True' in subs
    cron = (ROOT / "backend/crontab").read_text()
    line = [l for l in cron.splitlines() if "supply_demand.demand_alerts" in l and not l.startswith("#")]
    assert len(line) == 1 and line[0].split()[:5] == ["3-58/5", "9-16", "*", "*", "1-5"]


def test_notifications_page_and_prefs_type_know_the_kind():
    page = (ROOT / "frontend/src/pages/Notifications.tsx").read_text()
    assert "key: 'demand_alert'" in page
    assert "demand_alert: true" in page, "essentials preset keeps it on"
    prefs = (ROOT / "frontend/src/hooks/useNotificationPrefs.ts").read_text()
    assert "demand_alert?: boolean" in prefs
    feats = (ROOT / "frontend/src/lib/newFeatures.ts").read_text()
    assert "id: 'demand-zone-alerts'" in feats


def test_at_singles_are_capped_per_pass_and_the_rest_ride_the_digest(monkeypatch):
    """2026-09-03 12:48: the first pass after a deploy fired 14 singles at
    once. Closest first, MAX_SINGLES_PER_PASS ring alone, the spill joins the
    NEAR digest under a 'Demand zone' title — one buzz, every name still named."""
    sent = _capture(monkeypatch)
    syms = [f"A{i}" for i in range(6)]
    board = _board(rows=[(s, _band(100, 110)) for s in syms] + [("NEARX", _band(50, 55))])
    # A0 inside, A1..A5 0.1%..0.5% above (closest first ordering is testable)
    # `low` just under each print: since 2026-09-09 only a BOUNCE reaches the
    # phone, and this test's subject is the singles cap, not the direction gate.
    live = {s: {"price": 110.0 * (1 + 0.001 * i) if i else 105.0, "change_pct": -0.5,
                "prev_day_close": 120.0,
                "low": round((110.0 * (1 + 0.001 * i) if i else 105.0) * 0.988, 4)}
            for i, s in enumerate(syms)}
    live["NEARX"] = {"price": 56.0, "change_pct": -1.0, "prev_day_close": 60.0, "low": 55.3}
    caps = {s: 5e9 for s in syms + ["NEARX"]}
    coll = FakeColl()
    store = {}
    for s in syms:
        store.update(_store(s, [{"kind": "demand", "lo": 100.0, "hi": 110.0, "touches": 3}], 120.0))
    store.update(_store("NEARX", [{"kind": "demand", "lo": 50.0, "hi": 55.0, "touches": 3}], 60.0))
    out = DA.check_once(board=board, live=live, caps=caps, coll=coll, owner="o@x",
                        now=IN_SESSION, force=True, store=store)
    assert out["at"] == 6 and out["at_singles"] == DA.MAX_SINGLES_PER_PASS == 4
    assert out["near"] == 1 and out["pushed"] == 5           # 4 singles + 1 digest (AT spill only)
    assert out["skipped_proximity"] == 1, "NEARX (1.8% above) lists, never rings — phone gate 2026-09-05"
    singles = [s for s in sent if s["title"].startswith("🧲 A")]
    assert [s["title"].split()[1] for s in singles] == ["A0", "A1", "A2", "A3"], "closest first"
    digest = [s for s in sent if "more" in s["title"] or s["title"].startswith("🧲 Demand zone")][0]
    assert digest["title"] == "🧲 Demand zone — A4 +1 more"
    assert "A4 $" in digest["body"] and "A5 $" in digest["body"] and "NEARX" not in digest["body"]
    assert "↑ bouncing off $100–110 · room: clear runway" in digest["body"]
    assert len(coll.docs) == 6, "every pushed name recorded once — no second buzz next pass"
    assert DA.digest_message([]) is None
    near_only = DA.digest_message([{"symbol": "N", "last": 56.0, "band": _band(50, 55), "cap": 2e9,
                                    "hit": {"tier": "near", "state": "falling", "dist_pct": 1.8}}])
    assert near_only["title"] == "🧲 Nearing demand — N"


# ── fixes 2026-09-05 (review of the S/D zone logic; Ajay: "yes please fix the bugs") ──
def _store(sym, bands, prev_close, day="2026-09-03"):
    """A zone_store doc, the shape zone_store.build_doc writes."""
    return {sym: {"_id": f"{sym}:{day}", "symbol": sym, "date": day, "geom": "board",
                  "bands": bands, "atr14": 1.0, "prev_close": prev_close}}


def test_session_gate_skips_market_holidays():
    assert DA.in_session(datetime(2026, 9, 7, 10, 0, tzinfo=ET)) is False    # Labor Day 2026
    assert DA.in_session(datetime(2026, 9, 8, 10, 0, tzinfo=ET)) is True


def test_state_key_uses_fixed_two_decimals():
    a, b = _band(12345.67, 12400.0), _band(12345.72, 12400.0)
    assert DA.state_key("X", a, "2026-09-05", "at") != DA.state_key("X", b, "2026-09-05", "at")
    assert DA.state_key("NTAP", _band(180.0, 183.5), "2026-09-03", "at") == "NTAP:180.00-183.50:2026-09-03:at"


def test_phone_gate_near_tier_lists_but_no_longer_pushes_at_still_rings(monkeypatch):
    """Ajay 2026-09-05: "Need only alerts on stocks that have atleast 5% to Supply
    and also <1% bounce from demand zone". NEAR (1-3% above, falling) is listed
    and counted, never pushed; AT (inside / <=1% above) rings when the room to
    the first unbroken supply band is >= 5%. Distance for AT is unchanged
    (AT_PCT was already 1.0)."""
    sent = _capture(monkeypatch)
    board = _board(appr=[("BIGX", _band(90, 97))], rows=[("AAPL", _band(200, 210))])
    live = _live_bouncing(BIGX=(99.0, -1.1), AAPL=(211.0, -0.2))
    coll = FakeColl()
    store = _store("AAPL", [{"kind": "demand", "lo": 200.0, "hi": 210.0, "touches": 3, "strength": 50.0}], 221.55)
    out = DA.check_once(board=board, live=live, caps={"BIGX": 5e9, "AAPL": 3e12}, coll=coll, owner="o@x",
                        now=IN_SESSION, force=True, store=store)
    assert out["at"] == 1 and out["near"] == 1 and out["pushed"] == 1
    assert out["skipped_proximity"] == 1 and out["skipped_room"] == 0 and out["unknown_room"] == 0
    assert [s["title"] for s in sent] == ["🧲 AAPL ↑ bouncing off demand $200–210"]
    assert sent[0]["body"] == ("$211 · 0.47% above · ↑ bouncing off the band, +1.2% off the 208.468 low · tested 3x · "
                               "room: clear runway · buy $200-210 · stop $199.00 "
                               "(0.5% under the floor, 5.7% risk) · target: clear runway · $3.0T · AAPL Inc")
    assert list(coll.docs) == ["AAPL:200.00-210.00:2026-09-03:at"], "NEAR is not recorded: nothing was sent"
    # a lid 2.8% over the print (unbroken: hi 219 >= prev 215): listed, counted, silent
    sent.clear()
    lid_store = _store("AAPL", [{"kind": "supply", "lo": 217.0, "hi": 219.0, "touches": 2, "strength": 50.0}], 215.0)
    out2 = DA.check_once(board=_board(rows=[("AAPL", _band(200, 210))]), live=_live_bouncing(AAPL=(211.0, -0.2, 215.0)),
                         caps={"AAPL": 3e12}, coll=FakeColl(), owner="o@x", now=IN_SESSION, force=True,
                         store=lid_store)
    assert out2["at"] == 1 and out2["pushed"] == 0 and out2["skipped_room"] == 1 and sent == []
    assert out2["hits"][0]["room"]["room_pct"] == 2.8
    # the same lid 5.2% over: rings, and the body says so
    far_store = _store("AAPL", [{"kind": "supply", "lo": 222.0, "hi": 224.0, "touches": 2, "strength": 50.0}], 215.0)
    out3 = DA.check_once(board=_board(rows=[("AAPL", _band(200, 210))]), live=_live_bouncing(AAPL=(211.0, -0.2, 215.0)),
                         caps={"AAPL": 3e12}, coll=FakeColl(), owner="o@x", now=IN_SESSION, force=True,
                         store=far_store)
    assert out3["pushed"] == 1 and "room +5.2% -> $222" in sent[-1]["body"]
    # no zone_store doc for the name: the room is unknown -> conservative, silent, counted
    out4 = DA.check_once(board=_board(rows=[("AAPL", _band(200, 210))]), live=_live_bouncing(AAPL=(211.0, -0.2)),
                         caps={"AAPL": 3e12}, coll=FakeColl(), owner="o@x", now=IN_SESSION, force=True, store={})
    assert out4["at"] == 1 and out4["pushed"] == 0 and out4["unknown_room"] == 1 and len(sent) == 1
    assert DA.AT_PCT == 1.0


def test_an_AT_hit_is_measured_on_the_print_but_the_phone_gate_on_the_band_top():
    """Documented sliver (review 2026-09-05): DA.read's dist_pct is (px-hi)/px,
    the shared gate is px <= hi*1.01 ((px-hi)/hi). A print 1.005% over the top
    on the hi basis is 0.995% on the px basis -> tier AT, gate False ->
    skipped_proximity. Silence, never a wrong push; ~1c on a $100 name. Pinned
    so demand_alerts.md stays honest about 'AT distance unchanged'."""
    from supply_demand import alert_gates as AG
    band = _band(98.0, 100.0)
    hit = DA.read(101.005, band, -0.5, 110.0)
    assert hit["tier"] == "at" and hit["dist_pct"] == 1.0
    assert AG.demand_proximity_gate(101.005, band) is False
    assert AG.demand_proximity_gate(101.0, band) is True
    assert DA.read(101.0, band, -0.5, 110.0)["tier"] == "at"


# ── the pass record for /alerts/status (2026-09-05) ──────────────────────────
class PassColl(FakeColl):
    """alert_pass_latest: one replace_one per pass."""

    def replace_one(self, q, doc, upsert=False):
        self.docs[q["_id"]] = dict(doc)


def test_every_pass_records_its_counters_so_a_quiet_phone_is_explainable(monkeypatch):
    """Ajay 2026-09-05: "Do we have the same logic in back end demand for the ones
    that I get alerts" — no (board = closed-bar scan + R:R floor; phone = live,
    $1B+, gated). So the pass leaves WHY it was quiet in alert_pass_latest."""
    sent = _capture(monkeypatch)
    pc = PassColl()
    board = _board(appr=[("BIGX", _band(90, 97)), ("BIGY", _band(40, 44)),
                         ("SMALL", _band(10, 11)), ("UNK", _band(50, 52))],
                   rows=[("AAPL", _band(200, 210))])
    live = _live_bouncing(BIGX=(99.0, -1.1), BIGY=(45.0, -0.4), SMALL=(11.05, -2.0),
                 UNK=(51.0, -1.0), AAPL=(211.0, -0.2))
    caps = {"BIGX": 5e9, "BIGY": 12e9, "SMALL": 5e8, "UNK": None, "AAPL": 3e12}
    store = _store("AAPL", [{"kind": "demand", "lo": 200.0, "hi": 210.0, "touches": 3, "strength": 50.0}], 221.55)
    out = DA.check_once(board=board, live=live, caps=caps, coll=FakeColl(), owner="o@x",
                        now=IN_SESSION, force=True, store=store, pass_coll=pc)
    assert out["pushed"] == 1 and len(sent) == 1
    assert list(pc.docs) == ["demand_alert"]
    doc = pc.docs["demand_alert"]
    assert doc["_id"] == DA.KIND and doc["as_of"] == IN_SESSION.isoformat() and doc["date"] == "2026-09-03"
    c = doc["counts"]
    assert c == {"candidates": 5, "hits": 5, "at": 1, "at_singles": 1, "near": 2, "pushed": 1,
                 "skipped_cap": 1, "unknown_cap": 1, "unknown_prev": 0, "skipped_room": 0,
                 "skipped_proximity": 2, "unknown_room": 0, "skipped_direction": 0, "skipped_knife": 0, "skipped_mood": 0}
    assert all(type(v) is int for v in c.values()) and "reason" not in doc
    # a warming board is a recorded, explained quiet pass — and the doc is REPLACED, not appended
    out2 = DA.check_once(board={"warming": True}, now=IN_SESSION, force=True, pass_coll=pc)
    assert out2["ran"] and list(pc.docs) == ["demand_alert"]
    assert pc.docs["demand_alert"]["counts"] == {"candidates": 0, "hits": 0, "at": 0, "near": 0, "pushed": 0}
    assert pc.docs["demand_alert"]["reason"] == "board empty or warming"


def test_pass_record_is_best_effort_and_never_written_outside_rth(monkeypatch):
    sent = _capture(monkeypatch)

    class Broken(PassColl):
        def replace_one(self, q, doc, upsert=False):
            raise RuntimeError("mongo down")
    store = _store("AAPL", [{"kind": "demand", "lo": 200.0, "hi": 210.0, "touches": 3, "strength": 50.0}], 221.55)
    kw = dict(board=_board(rows=[("AAPL", _band(200, 210))]), live=_live_bouncing(AAPL=(211.0, -0.2)),
              caps={"AAPL": 3e12}, owner="o@x", store=store)
    assert DA.check_once(now=IN_SESSION, force=True, coll=FakeColl(), pass_coll=Broken(), **kw)["pushed"] == 1
    assert len(sent) == 1, "a dead status coll never blocks the push"
    pc = PassColl()
    closed = DA.check_once(now=datetime(2026, 9, 3, 7, 0, tzinfo=ET), coll=FakeColl(), pass_coll=pc, **kw)
    assert closed == {"ran": False, "reason": "outside RTH"} and pc.docs == {}
    assert DA.check_once(now=IN_SESSION, force=True, coll=FakeColl(), **kw)["pushed"] == 1, \
        "no pass coll injected: resolver path, no Mongo in tests, still quiet"


def test_at_message_carries_the_ticker_for_push_history_2026_09_05():
    """push.history.record stores payload["ticker"]; the /alerts page ticker
    filter and the boards' alerted-today chip key on it. Every zone push had
    ticker None until 2026-09-05 (verified on the live push_history)."""
    from supply_demand import demand_alerts as DA
    item = {"symbol": "ERIE", "hit": {"dist_pct": 0.8, "tier": "at", "state": "near"}, "last": 249.0,
            "band": {"lo": 246.99, "hi": 250.68, "touches": 2, "kind": "demand"},
            "cap": 12e9, "name": "Erie Indemnity", "tier": "near", "dist_pct": 0.8}
    msg = DA.at_message(item)
    assert msg["ticker"] == "ERIE"
    assert msg["url"].startswith("/sepa/ERIE")


# ── mood rides the alert as CONTEXT (Ajay 2026-09-08) ────────────────────────
def test_body_and_digest_carry_the_mood_and_do_not_need_it():
    band = _band(90, 97, touches=3)
    hit = {"tier": "at", "state": "in", "dist_pct": 0.0}
    m = DA.at_message({"symbol": "AAA", "last": 96.0, "band": band, "hit": hit, "cap": 5e9,
                       "name": "Alpha", "mood": {"score": 18.0, "label": "leaning bullish"}})
    assert "· mood +18 leaning bullish ·" in m["body"]
    assert m["title"] == "🧲 AAA in demand $90–97", "mood never touches the title"
    # NEGATIVE: no mood -> the old body, unchanged
    m2 = DA.at_message({"symbol": "AAA", "last": 96.0, "band": band, "hit": hit, "cap": 5e9,
                        "name": "Alpha"})
    assert "mood" not in m2["body"]
    d = DA.digest_message([{"symbol": "AAA", "last": 96.0, "band": band, "hit": hit, "cap": 5e9,
                            "mood": {"score": -31.0, "label": "bearish"}}])
    assert "· mood -31 bearish" in d["body"]


def test_a_constructive_mood_rings_first_but_nothing_is_dropped(monkeypatch):
    """Ajay 2026-09-08: "mood determins if stock grows faster from demand or
    not". It orders the singles; every name still gets through."""
    sent = _capture(monkeypatch)
    syms = [f"M{i}" for i in range(6)]
    board = _board(rows=[(s, _band(90, 97)) for s in syms])
    store = {}
    for s in syms:
        store.update(_store(s, [{"kind": "demand", "lo": 90.0, "hi": 97.0, "touches": 3, "strength": 50.0}], 103.95))
    live = _live_bouncing(**{s: (96.0 + i * 0.05, -2.0) for i, s in enumerate(syms)})
    # M5 is furthest but the only constructive name; M0 is closest and heavy
    moods = {"M5": {"score": 40.0, "label": "bullish", "constructive": True, "heavy": False},
             "M0": {"score": -40.0, "label": "bearish", "constructive": False, "heavy": True}}
    monkeypatch.setattr(DA.AG, "mood_read", lambda sym, frame=None: moods.get(sym))
    out = DA.check_once(board=board, live=live, caps={s: 5e9 for s in syms}, coll=FakeColl(),
                        owner="o@x", now=IN_SESSION, force=True, store=store)
    singles = [s for s in sent if "more" not in s["title"]]
    assert singles[0]["title"].startswith("🧲 M5"), "constructive rings first"
    assert not any(t["title"].startswith("🧲 M0") for t in singles), "the heavy name loses its single"
    assert out["at"] == 6 and out["pushed"] == DA.MAX_SINGLES_PER_PASS + 1
    digest = [s for s in sent if "more" in s["title"]][0]
    assert "M0" in digest["body"], "the heavy name is still delivered, in the digest"


def test_mood_is_recorded_with_every_alert_so_it_can_be_measured(monkeypatch):
    sent = _capture(monkeypatch)
    coll = FakeColl()
    board = _board(rows=[("AAA", _band(90, 97))])
    store = _store("AAA", [{"kind": "demand", "lo": 90.0, "hi": 97.0, "touches": 3, "strength": 50.0}], 103.95)
    monkeypatch.setattr(DA.AG, "mood_read",
                        lambda sym, frame=None: {"score": 22.0, "label": "bullish",
                                                 "constructive": True, "heavy": False})
    DA.check_once(board=board, live=_live_bouncing(AAA=(96.0, -2.0)), caps={"AAA": 5e9}, coll=coll,
                  owner="o@x", now=IN_SESSION, force=True, store=store)
    doc = list(coll.docs.values())[0]
    assert doc["mood"]["score"] == 22.0 and doc["mood"]["constructive"] is True
    assert doc["approach"] in {"falling", "bouncing", "settling", "resting", None}



# ── bullish reversal, not a falling knife (2026-09-09) ─────────────────────
# Ajay, hours after bouncing-only shipped: "I think we got alerts wrong.. I need
# only bullish reversal stocks that touched demand zone and bouncing back .. and
# mood has to be bullish too with reversal. After a stationary bottommed stocks
# as I caught a fallig knife today with Casy"
def _casy_kw():
    """The exact 2026-09-09 CASY shape: an arrival at a demand band, bouncing
    off the day's low, that passed every gate the phone had that morning."""
    band = _band(627.49, 651.0)
    return dict(board=_board(rows=[("CASY", band)]),
                caps={"CASY": 24e9}, owner="o@x", now=IN_SESSION, force=True,
                store=_store("CASY", [{"kind": "demand", "lo": 627.49, "hi": 651.0,
                                       "touches": 3, "strength": 55.0}], 733.49))


def test_a_falling_knife_is_listed_and_never_pushed(monkeypatch):
    """CASY's swing lows were stepping down under a falling 50-day. The board
    keeps it (wearing the 🔪 badge); the phone does not."""
    sent = _capture(monkeypatch)
    monkeypatch.setattr(DA.AG, "knife_read",
                        lambda sym, frame=None: {"knife": True, "trend": "falling"})
    out = DA.check_once(live=_live_bouncing(CASY=(646.0, -11.9, 733.49)),
                        coll=FakeColl(), **_casy_kw())
    assert out["hits"], "the board still lists it"
    assert out["hits"][0]["approach"]["dir"] == "bouncing", "it really was bouncing"
    assert out["pushed"] == 0 and out["skipped_knife"] == 1 and sent == []


def test_a_bearish_turn_is_listed_and_never_pushed(monkeypatch):
    """CASY's 60-session mood was -57. The floor for a push is +25."""
    sent = _capture(monkeypatch)
    monkeypatch.setattr(DA.AG, "reversal_mood_read",
                        lambda sym, frame=None, bars=None: {"score": -57.0, "label": "bearish",
                                                            "bars": 60, "bullish": False})
    out = DA.check_once(live=_live_bouncing(CASY=(646.0, -11.9, 733.49)),
                        coll=FakeColl(), **_casy_kw())
    assert out["hits"] and out["pushed"] == 0
    assert out["skipped_mood"] == 1 and sent == []


def test_both_new_gates_fail_closed_when_the_daily_bars_cannot_be_read(monkeypatch):
    """No frame = no evidence of a bullish reversal = no push. Same side the
    direction gate fails on."""
    sent = _capture(monkeypatch)
    monkeypatch.setattr(DA.AG, "knife_read", lambda sym, frame=None: None)
    out = DA.check_once(live=_live_bouncing(CASY=(646.0, -11.9, 733.49)),
                        coll=FakeColl(), **_casy_kw())
    assert out["pushed"] == 0 and out["skipped_knife"] == 1 and sent == []


def test_a_clean_bullish_reversal_still_rings(monkeypatch):
    """The gates are a TIGHTENING, not an off switch — the good case survives."""
    sent = _capture(monkeypatch)
    out = DA.check_once(live=_live_bouncing(CASY=(646.0, -11.9, 733.49)),
                        coll=FakeColl(), **_casy_kw())
    assert out["pushed"] == 1 and len(sent) == 1
    assert out["skipped_knife"] == 0 and out["skipped_mood"] == 0


def test_the_things_to_see_are_read_only_for_names_that_survive(monkeypatch):
    """GEX / patterns / sentiment cost a network hop, so they are read AFTER
    every gate — and never for a name the phone is not going to mention."""
    _capture(monkeypatch)
    seen = []
    monkeypatch.setattr(DA.BC, "bullish_context",
                        lambda sym, frame=None, with_sentiment=True: seen.append(sym) or {})
    monkeypatch.setattr(DA.AG, "knife_read",
                        lambda sym, frame=None: {"knife": True, "trend": "falling"})
    DA.check_once(live=_live_bouncing(CASY=(646.0, -11.9, 733.49)), coll=FakeColl(), **_casy_kw())
    assert seen == [], "a blocked name must not cost a network read"
    monkeypatch.setattr(DA.AG, "knife_read",
                        lambda sym, frame=None: {"knife": False, "trend": "rising"})
    DA.check_once(live=_live_bouncing(CASY=(646.0, -11.9, 733.49)), coll=FakeColl(), **_casy_kw())
    assert seen == ["CASY"]
