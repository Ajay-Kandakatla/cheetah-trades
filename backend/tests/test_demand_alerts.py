"""supply_demand/demand_alerts — $1B+ names at / nearing a tested demand band.

Behavioural tests on synthetic boards + source guards for the wiring (pref
default, crontab line, notifications page). Ajay 2026-09-03.
"""
import sys
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


def _live(**px):
    """price, change_pct[, prev_day_close]. Default prev close = 5% above the
    live print, i.e. yesterday was outside every ring → today is an arrival."""
    out = {}
    for s, v in px.items():
        p, c = v[0], v[1]
        prev = v[2] if len(v) > 2 else round(p * 1.05, 4)
        out[s] = {"price": p, "change_pct": c, "prev_day_close": prev}
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
                        now=IN_SESSION, force=True)
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
    assert DA.state_key("NTAP", _band(180.0, 183.5), "2026-09-03", "at") == "NTAP:180-183.5:2026-09-03:at"


# ── messages ─────────────────────────────────────────────────────────────────
def test_at_message_names_the_band_the_tests_and_the_cap():
    m = DA.at_message({"symbol": "NTAP", "last": 182.9, "band": _band(180, 183.5, touches=4),
                       "hit": {"tier": "at", "state": "in", "dist_pct": 0.0},
                       "cap": 37e9, "name": "NetApp"})
    assert m["title"] == "🧲 NTAP in demand $180–183.5"
    assert "tested 4x" in m["body"] and "$37.0B" in m["body"] and "NetApp" in m["body"]
    assert m["url"] == "/sepa/NTAP?tab=supply" and m["data"]["url"] == m["url"]


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
    live = _live(BIGX=(99.0, -1.1), BIGY=(45.0, -0.4), SMALL=(11.05, -2.0),
                 UNK=(51.0, -1.0), AAPL=(211.0, -0.2))
    caps = {"BIGX": 5e9, "BIGY": 12e9, "SMALL": 5e8, "UNK": None, "AAPL": 3e12}
    coll = FakeColl()
    out = DA.check_once(board=board, live=live, caps=caps, coll=coll, owner="o@x",
                        now=IN_SESSION, force=True)
    assert out["ran"] and out["at"] == 1 and out["near"] == 2 and out["pushed"] == 2
    assert out["skipped_cap"] == 1 and out["unknown_cap"] == 1
    assert [s["kind"] for s in sent] == ["demand_alert", "demand_alert"]
    assert sent[0]["title"] == "🧲 AAPL 0.47% above demand $200–210"
    assert sent[1]["title"] == "🧲 Nearing demand — BIGX +1 more"
    assert "BIGY $45 · 2.22% above $40–44 · $12.0B" in sent[1]["body"]
    assert all(s["owner"] == "o@x" for s in sent)
    assert len(coll.docs) == 3                     # AAPL at + BIGX near + BIGY near


def test_dedupe_is_once_per_band_per_day_but_tiers_are_separate(monkeypatch):
    sent = _capture(monkeypatch)
    board = _board(appr=[("BIGX", _band(90, 97))])
    coll = FakeColl()
    kw = dict(board=board, caps={"BIGX": 5e9}, coll=coll, owner="o@x", now=IN_SESSION, force=True)
    DA.check_once(live=_live(BIGX=(99.0, -1.1)), **kw)          # near → digest
    DA.check_once(live=_live(BIGX=(99.0, -1.1)), **kw)          # same fact, silent
    assert len(sent) == 1
    DA.check_once(live=_live(BIGX=(96.5, -3.0)), **kw)          # arrived → at fires
    assert len(sent) == 2 and sent[1]["title"] == "🧲 BIGX in demand $90–97"
    DA.check_once(live=_live(BIGX=(96.0, -3.5)), **kw)
    assert len(sent) == 2


def test_transport_failure_is_retried_but_muted_pref_is_terminal(monkeypatch):
    board = _board(rows=[("AAPL", _band(200, 210))])
    kw = dict(board=board, live=_live(AAPL=(205.0, -0.2)), caps={"AAPL": 3e12},
              owner="o@x", now=IN_SESSION, force=True)
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
                        live=_live(AAPL=(205.0, 0.0)), caps={"AAPL": 3e12}, coll=coll,
                        now=IN_SESSION, force=True)
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
