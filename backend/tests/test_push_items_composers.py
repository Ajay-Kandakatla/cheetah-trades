"""Every item of a consolidated push — the seven composers (2026-09-29).

Ajay, on "⚡ Tape burst at a zone — CRWV +7 more": "I am unable to see the
other that are hiddedn her … Can you show them all and make all the tickers
clicable individually?"

Each "+N more" composer now adds a LOG-ONLY ``items`` list — every entry, in
body order, ``text`` exactly the line it prints — while the body, the title and
every device key stay byte-identical (push.sender strips ``items``). Pinned per
builder: items cover every entry, ``items[i].text == body_lines[i]`` for the
printed lines (the positional merge in push.recent.served_items depends on it),
and ``set(msg) - {"items"}`` is the exact pre-change key set.

Hermetic: no Mongo, no network.
"""
import inspect
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orderflow import trade_flash as TF                    # noqa: E402
from supply_demand import demand_alerts as DA              # noqa: E402
from supply_demand import zone_bounce_alerts as ZB         # noqa: E402
from supply_demand import zone_edge as ZE                  # noqa: E402
from supply_demand import key_level_alerts as KLA          # noqa: E402
from supply_demand import accumulation_changes as AC       # noqa: E402
from catalysts.medical import alerts as MA                 # noqa: E402


def _band(lo, hi, touches=3, kind="demand"):
    return {"lo": lo, "hi": hi, "touches": touches, "kind": kind}


# ---------------------------------------------------------------------------
# trade_flash.record_and_push
# ---------------------------------------------------------------------------
class _Res:
    def __init__(self, upserted_id):
        self.upserted_id = upserted_id


class _TFColl:
    def update_one(self, q, u, upsert=False):
        return _Res(q["_id"])


class _TFDb(dict):
    def __getitem__(self, name):
        return _TFColl()


def _tf_ev(sym, dollars, t):
    return {"_id": f"{sym}|{t}|{dollars}", "symbol": sym, "time_et": t, "dollars": dollars,
            "side": "buy", "board": "supply"}


@pytest.fixture
def tf_spy(monkeypatch):
    from push import sender
    calls = []
    monkeypatch.setattr(TF, "_db", lambda: _TFDb())
    monkeypatch.setattr(sender, "send_to_user",
                        lambda email, payload, kind=None: calls.append(payload) or {"sent": 1})
    return calls


def test_trade_flash_logs_every_burst_and_the_phone_keeps_four(tf_spy):
    evs = [_tf_ev(s, d, f"13:1{i}:00") for i, (s, d) in enumerate(
        [("CRWV", 1.8e6), ("KLAC", 5.6e5), ("BRK.B", 9.0e5), ("CRWV", 1.0e6),
         ("NVDA", 3.0e5), ("AVGO", 7.0e5), ("CRWV", 2.0e5), ("KLAC", 4.0e5)])]
    out = TF.record_and_push(evs)
    assert out["new"] == 8
    p = tf_spy[-1]
    assert set(p) == {"title", "body", "url", "kind", "items"}
    ranked = sorted(evs, key=lambda e: -e["dollars"])
    assert p["body"].split("\n") == [TF.headline(e) for e in ranked[:4]]
    assert p["title"] == "⚡ Tape burst at a zone — CRWV +7 more"
    assert len(p["items"]) == 8
    assert [it["symbol"] for it in p["items"]] == [e["symbol"] for e in ranked]
    assert [it["text"] for it in p["items"]] == [TF.headline(e) for e in ranked]
    assert "BRK.B" in [it["symbol"] for it in p["items"]], "symbol verbatim"
    assert p["url"] == TF.tape_url("CRWV") == "/sepa/CRWV?tab=tape&from=supply-demand"
    assert TF.PUSH_BODY_LINES == 4


def test_NEGATIVE_trade_flash_single_and_empty(tf_spy):
    TF.record_and_push([_tf_ev("CRWV", 1.8e6, "13:17:30")])
    p = tf_spy[-1]
    assert len(p["items"]) == 1 and "more" not in p["title"]
    n = len(tf_spy)
    assert TF.record_and_push([])["pushed"] is False
    assert len(tf_spy) == n, "zero fresh -> no send"


# ---------------------------------------------------------------------------
# demand_alerts.digest_message
# ---------------------------------------------------------------------------
def _demand_items(n):
    return [{"symbol": f"S{i}", "last": 100.0 + i, "band": _band(90, 97), "cap": 2e9,
             "hit": {"tier": "near", "state": "falling", "dist_pct": 3.0 - i * 0.2}}
            for i in range(n)]


def test_demand_digest_items_cover_every_name():
    m = DA.digest_message(_demand_items(9))
    lines = m["body"].split("\n")
    assert len(lines) == DA.DIGEST_MAX + 1 and lines[-1] == "+3 more on the board"
    assert lines[0] == "S8 $108 · 1.4% above $90–97 · $2.0B"
    assert m["tickers"] == ["S8", "S7", "S6", "S5", "S4", "S3"]
    assert len(m["items"]) == 9
    assert [it["symbol"] for it in m["items"]] == [f"S{i}" for i in range(8, -1, -1)]
    for i in range(DA.DIGEST_MAX):
        assert m["items"][i]["text"] == lines[i]
    assert m["items"][-1]["text"] == "S0 $100 · 3% above $90–97 · $2.0B"
    assert set(m) - {"items"} == {"title", "body", "url", "data", "kind", "ticker", "tickers"}


def test_NEGATIVE_demand_digest_empty_is_none():
    assert DA.digest_message([]) is None


# ---------------------------------------------------------------------------
# zone_bounce_alerts.digest_message
# ---------------------------------------------------------------------------
def test_zone_bounce_digest_items_cover_every_name():
    items = [{"symbol": f"B{i}", "print": 50.0 + i, "band": _band(45, 49), "cap": 3e9,
              "room": None, "hit": {"bounce_pct": 1.0 + i}} for i in range(8)]
    m = ZB.digest_message(items)
    lines = m["body"].split("\n")
    assert len(lines) == ZB.DIGEST_MAX + 1 and lines[-1] == "+2 more"
    assert m["tickers"] == ["B7", "B6", "B5", "B4", "B3", "B2"]
    assert len(m["items"]) == 8
    assert [it["symbol"] for it in m["items"]] == [f"B{i}" for i in range(7, -1, -1)]
    for i in range(ZB.DIGEST_MAX):
        assert m["items"][i]["text"] == lines[i]
    assert set(m) - {"items"} == {"title", "body", "url", "data", "kind", "ticker", "tickers"}
    # NEGATIVE
    assert ZB.digest_message([]) is None


# ---------------------------------------------------------------------------
# zone_edge.break_digest_message
# ---------------------------------------------------------------------------
RES = _band(100, 102, 3, "supply")


def _break_items(n):
    return [{"symbol": f"N{i}", "band": RES, "last": 101.0 + i * 0.1, "dist_pct": 0.9 - i * 0.1,
             "tier": "near", "cap": 2e9} for i in range(n)]


def test_break_digest_items_cover_every_name_and_ride_the_session_tag():
    m = ZE.break_digest_message(_break_items(7))
    lines = m["body"].split("\n")
    assert len(lines) == ZE.DIGEST_MAX + 1 and lines[-1] == "+1 more"
    assert len(m["items"]) == 7
    for i in range(ZE.DIGEST_MAX):
        assert m["items"][i]["text"] == lines[i]
    assert set(m) - {"items"} == {"title", "body", "url", "data", "kind"}
    tagged = ZE._tag_msg(m, "premarket")
    assert tagged["items"] == m["items"]
    assert tagged["body"] == m["body"] + " · pre-mkt"
    assert all("pre-mkt" not in it["text"] for it in tagged["items"]), "the tag rides the body only"
    # NEGATIVE
    assert ZE.break_digest_message([]) is None


# ---------------------------------------------------------------------------
# key_level_alerts.digest_text
# ---------------------------------------------------------------------------
def test_key_level_digest_items_cover_every_name_and_skip_the_footer():
    from tests.test_key_level_alerts import _m
    items = [(f"K{chr(65 + i)}", [_m("week", "low", "down", 10.0 + i)], 9.9 + i) for i in range(8)]
    m = KLA.digest_text(items)
    lines = m["body"].split("\n")
    assert lines[-1] == KLA._UNMEASURED_DIGEST
    assert lines[-2] == "+2 more"
    assert len(m["items"]) == 8
    assert all(it["text"].startswith(f"{it['symbol']} closed ") for it in m["items"])
    for i in range(ZE.DIGEST_MAX):
        assert m["items"][i]["text"] == lines[i]
    assert KLA._UNMEASURED_DIGEST not in [it["text"] for it in m["items"]]
    assert m["tickers"] == [s for s, _m2, _c in items], "tickers unchanged (uncapped)"
    assert set(m) - {"items"} == {"title", "body", "url", "data", "kind", "ticker", "tickers"}


# ---------------------------------------------------------------------------
# catalysts/medical/alerts.digest_text
# ---------------------------------------------------------------------------
def test_med_digest_items_cover_every_event_and_stay_signal_free():
    from tests.test_med_alerts import kod
    evs = [kod(ticker=f"M{chr(65 + i)}") for i in range(9)]
    m = MA.digest_text(evs)
    lines = m["body"].split("\n")
    assert len(lines) == 7 and lines[-1] == "+3 more on Chart Maps ▸ Catalysts ▸ 🧬 Medical"
    assert len(m["items"]) == 9
    assert [it["symbol"] for it in m["items"]] == [f"M{chr(65 + i)}" for i in range(9)]
    for i in range(MA.DIGEST_MAX_LINES):
        assert m["items"][i]["text"] == lines[i]
    assert set(m) - {"items"} == {"title", "body", "icon", "url", "tag", "kind", "ticker",
                                  "tickers", "data"}
    # NEGATIVE: the item texts carry no entry / stop / target / bounce wording
    blob = " ".join(it["text"] for it in m["items"])
    assert not re.search(r"\b(entry|stop|target|bounce)\b", blob, re.I), blob


# ---------------------------------------------------------------------------
# accumulation_changes._notify
# ---------------------------------------------------------------------------
def test_accumulation_notify_logs_every_change_by_size(monkeypatch):
    payloads = []

    class _Sender:
        @staticmethod
        def send_to_user(email, payload, kind=None):
            payloads.append(payload)
            return {"sent": 1}

        @staticmethod
        def send_to_all(payload, kind=None):
            payloads.append(payload)
            return {"sent": 1}

    monkeypatch.setitem(sys.modules, "push.sender", _Sender())
    import push
    monkeypatch.setattr(push, "sender", _Sender(), raising=False)
    sizes = [3, 8, 1, 6, 2, 7, 4, 5]
    changes = [{"symbol": f"T{i}", "direction": "accumulating",
                "net_change_usd": 100_000_000 * s, "net_change_pct": 20.0,
                "new_buyers": [], "exits": [],
                "prev_quarter": "2026-03-31", "new_quarter": "2026-06-30"}
               for i, s in enumerate(sizes)]
    AC._notify(changes)
    p = payloads[-1]
    assert len(p["body"]) <= 300 and "+3 more" in p["body"]
    ordered = sorted(changes, key=lambda c: -abs(c["net_change_usd"]))
    assert len(p["items"]) == 8
    assert [it["text"] for it in p["items"]] == [AC.alert_line(c) for c in ordered]
    assert [it["symbol"] for it in p["items"]] == [c["symbol"] for c in ordered]
    assert p["body"].split("\n")[:5] == [it["text"] for it in p["items"][:5]]
    assert set(p) - {"items"} == {"title", "body", "tag", "url", "kind"}


# ---------------------------------------------------------------------------
# source guards
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fn", [TF.record_and_push, DA.digest_message, ZB.digest_message,
                                ZE.break_digest_message, KLA.digest_text, MA.digest_text,
                                AC._notify])
def test_every_builder_carries_items(fn):
    assert '"items"' in inspect.getsource(fn)
