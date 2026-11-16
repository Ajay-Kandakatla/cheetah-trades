"""🚩 GG LIVE §3.5 / WP-D (2026-11-09) — the tab live over `/events`: POST /chart-maps/live `stream` + the
`gajjala.update` events (chart_maps/gajjala/live_events.py).

Ajay 2026-11-09: "same for reuglar Gajjlas tab as well need it to be more live". Owner decision (§7 #16): "I only need
this setup for myself the owner of the app" — the bus broadcasts to every tab, so the payloads stay public prices +
data-free nudges (NEGATIVE pins below).

The hub (`backend/live_hub.py`, WP-A) is built concurrently: every test here STUBS `live_hub` / `live_feed` in
sys.modules — `register_interest(variant, symbols, levels) -> {"on", "word"}` per spec §3.2.

PRE-CHANGE CAPTURE: `PRE` below is the route's answer captured BEFORE api.py was touched (frozen clock 2026-09-03
14:00:30 ET, the live-card test stubs) — without `stream` the answer must stay byte-identical (NEGATIVE).
"""
from __future__ import annotations

import json
import re
import sys
import threading
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chart_maps import live_card as LC                       # noqa: E402
from chart_maps.gajjala import live_events as LE              # noqa: E402
from sepa import prices as P                                  # noqa: E402

from test_chart_maps_live_card import RTH_SNAP, _frame, _at   # noqa: E402

SRC = Path(__file__).resolve().parents[1] / "chart_maps" / "gajjala" / "live_events.py"
FIXED = _at(2026, 9, 3, 14, 0, 30)

# captured from the UNCHANGED route (scratchpad gg_live/wpd/capture_pre.py) — (status, body text)
PRE = {
    # WIDENED 2026-11-09 (Ajay: "I can't see now for them again"): a print stamped today carries add_line true in RTH too.
    'plain': (200, '{"session":"rth","as_of_epoch":1788458430.0,"as_of":"2026-09-03 14:00:30 ET","footer":{"live":"live · 14:00:30 ET","stale":"last refresh 14:00 ET"},"now_labels":["now","now · pre","now · AH"],"cap":250,"asked":1,"served":1,"missing":[],"fault":null,"faults":{},"quotes":{"XLAB":{"bar":{"t":"2026-09-03","o":6.9,"h":9.2,"l":6.71,"c":9.12,"v":30903227.0},"prev_t":"2026-09-02","prev_bar":{"t":"2026-09-02","o":5.79,"h":5.84,"l":5.74,"c":5.79,"v":1000000.0},"now":{"price":9.12,"label":"now","session":null,"add_line":true,"as_of_epoch":1788458400.0,"as_of":"14:00:00 ET"}}}}'),
    # WIDENED 2026-11-12 (🥇 realtime cards, spec WP-C): vs gains pct_text (only inside a returned vs); text unchanged.
    'levels': (200, '{"session":"rth","as_of_epoch":1788458430.0,"as_of":"2026-09-03 14:00:30 ET","footer":{"live":"live · 14:00:30 ET","stale":"last refresh 14:00 ET"},"now_labels":["now","now · pre","now · AH"],"cap":250,"asked":2,"served":1,"missing":["NVDA"],"fault":null,"faults":{},"quotes":{"XLAB":{"bar":{"t":"2026-09-03","o":6.9,"h":9.2,"l":6.71,"c":9.12,"v":30903227.0},"prev_t":"2026-09-02","prev_bar":{"t":"2026-09-02","o":5.79,"h":5.84,"l":5.74,"c":5.79,"v":1000000.0},"now":{"price":9.12,"label":"now","session":null,"add_line":true,"as_of_epoch":1788458400.0,"as_of":"14:00:00 ET"},"vs":{"kind":"over_trigger","text":"🔴 9.12 over the trigger 9.00 on the live bar — the read moves when the 5-minute bar closes (14:05 ET)","pct_text":"+1.3% vs the trigger · +7.3% vs the stop"}}}}'),
    'stream_false': (200, '{"session":"rth","as_of_epoch":1788458430.0,"as_of":"2026-09-03 14:00:30 ET","footer":{"live":"live · 14:00:30 ET","stale":"last refresh 14:00 ET"},"now_labels":["now","now · pre","now · AH"],"cap":250,"asked":1,"served":1,"missing":[],"fault":null,"faults":{},"quotes":{"XLAB":{"bar":{"t":"2026-09-03","o":6.9,"h":9.2,"l":6.71,"c":9.12,"v":30903227.0},"prev_t":"2026-09-02","prev_bar":{"t":"2026-09-02","o":5.79,"h":5.84,"l":5.74,"c":5.79,"v":1000000.0},"now":{"price":9.12,"label":"now","session":null,"add_line":true,"as_of_epoch":1788458400.0,"as_of":"14:00:00 ET"}}}}'),
    'bad_levels': (200, '{"session":"rth","as_of_epoch":1788458430.0,"as_of":"2026-09-03 14:00:30 ET","footer":{"live":"live · 14:00:30 ET","stale":"last refresh 14:00 ET"},"now_labels":["now","now · pre","now · AH"],"cap":250,"asked":1,"served":1,"missing":[],"fault":null,"faults":{},"quotes":{"XLAB":{"bar":{"t":"2026-09-03","o":6.9,"h":9.2,"l":6.71,"c":9.12,"v":30903227.0},"prev_t":"2026-09-02","prev_bar":{"t":"2026-09-02","o":5.79,"h":5.84,"l":5.74,"c":5.79,"v":1000000.0},"now":{"price":9.12,"label":"now","session":null,"add_line":true,"as_of_epoch":1788458400.0,"as_of":"14:00:00 ET"}}}}'),
    'e422': (422, '{"detail":"symbols must be a list of tickers"}'),
    'e413': (413, '{"detail":"up to 250 symbols per live read — 251 sent"}'),
}
BODIES = {
    "plain": {"symbols": ["XLAB"]},
    "levels": {"symbols": ["XLAB", "nvda"], "levels": {"XLAB": {"trigger": 9.0, "stop": 8.5, "tf": "5m"}}},
    "stream_false": {"symbols": ["XLAB"], "stream": False, "variant": "gajjala"},
    "bad_levels": {"symbols": ["XLAB"], "levels": "abc"},
    "e422": {"symbols": "XLAB"},
    "e413": {"symbols": [f"S{i:03d}" for i in range(251)]},
}
HUB_WORD = "📡 Live prices — last print 1 s ago"          # stand-ins for WP-A's served words (never composed here)
FEED_WORD = "📡 Live stream down (test) — the 1-minute check keeps running."


class _FrozenDT(datetime):
    @classmethod
    def now(cls, tz=None):
        return FIXED if tz is None else FIXED.astimezone(tz)


@pytest.fixture
def wired(monkeypatch):
    """Frozen clock + the live-card stubs + stub hub / feed + a recorded bus. Returns the record dict."""
    rec: dict = {"interest": [], "order": [], "published": [], "threads": {}}
    monkeypatch.setattr(LC, "datetime", _FrozenDT)
    monkeypatch.setattr(P, "bulk_snapshot", lambda syms: {s: RTH_SNAP for s in syms if s == "XLAB"})
    monkeypatch.setattr(P, "bulk_cached_frames", lambda syms: {s: _frame() for s in syms if s == "XLAB"})

    real_compose = LC.compose

    def _compose(*a, **k):
        rec["order"].append("compose")
        rec["threads"]["compose"] = threading.current_thread().name
        return real_compose(*a, **k)

    monkeypatch.setattr(LC, "compose", _compose)

    hub = types.ModuleType("live_hub")

    def register_interest(variant, symbols, levels):
        rec["order"].append("interest")
        rec["threads"]["interest"] = threading.current_thread().name
        rec["interest"].append((variant, list(symbols), levels))
        on = variant in LE.variant_keys()
        return {"on": on, "word": HUB_WORD if on else FEED_WORD}

    hub.register_interest = register_interest
    monkeypatch.setitem(sys.modules, "live_hub", hub)
    feed = types.ModuleType("live_feed")
    feed.pair = ("live", HUB_WORD)                                   # (state, word) — live_feed.state_word()'s shape
    feed.state_word = lambda: feed.pair
    monkeypatch.setitem(sys.modules, "live_feed", feed)
    rec["feed"] = feed

    import events
    from chart_maps import api as _api                              # noqa: F401 — its import injects the vs function
    monkeypatch.setattr(LE, "_vs_fn", LC.live_vs)
    monkeypatch.setattr(events, "publish", lambda t, p: rec["published"].append((t, p)))
    LE.reset()
    yield rec
    LE.reset()


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chart_maps import api as A
    app = FastAPI()
    app.include_router(A.router)
    return TestClient(app)


# ── POST /chart-maps/live — without `stream` byte-identical ──────────────────────────────────────────────────────
@pytest.mark.parametrize("key", sorted(PRE))
def test_negative_no_stream_is_byte_identical_to_the_pre_change_answer(wired, key):
    r = _client().post("/chart-maps/live", json=BODIES[key])
    assert (r.status_code, r.content.decode("utf-8")) == PRE[key]
    assert wired["interest"] == [], "no `stream` → the hub is never asked"


def test_stream_registers_interest_before_the_read_on_the_event_loop(wired):
    body = {"symbols": [" xlab ", "XLAB", "nvda"], "levels": {"XLAB": {"trigger": 9.0, "stop": 8.5, "tf": "5m"}},
            "stream": True, "variant": "gajjala_1m"}
    r = _client().post("/chart-maps/live", json=body)
    assert r.status_code == 200
    assert wired["interest"] == [("gajjala_1m", ["XLAB", "NVDA"], body["levels"])], "normalized syms, the levels"
    assert wired["order"] == ["interest", "compose"], "interest BEFORE the read"
    assert wired["threads"]["interest"] != wired["threads"]["compose"], "interest on the loop, the read in a thread"
    j = r.json()
    assert j["stream"] == {"on": True, "word": HUB_WORD, "state": "live"}
    pre = json.loads(PRE["levels"][1])
    assert {k: v for k, v in j.items() if k != "stream"} == pre, "the read itself is today's answer + one key"


def test_negative_unknown_variant_stream_off(wired):
    r = _client().post("/chart-maps/live", json={"symbols": ["XLAB"], "stream": True, "variant": "nope"})
    assert r.status_code == 200 and r.json()["stream"]["on"] is False
    assert r.json()["stream"]["word"] == FEED_WORD
    r = _client().post("/chart-maps/live", json={"symbols": ["XLAB"], "stream": True})
    assert r.json()["stream"]["on"] is False, "no variant → off"


def test_negative_stream_must_be_true_not_truthy(wired):
    for v in ("true", 1, "yes", None, False):
        r = _client().post("/chart-maps/live", json={"symbols": ["XLAB"], "stream": v, "variant": "gajjala"})
        assert (r.status_code, r.content.decode("utf-8")) == PRE["plain"], v
    assert wired["interest"] == []


def test_negative_hub_missing_or_raising_serves_off_with_the_feed_word(wired, monkeypatch):
    wired["feed"].pair = ("kicked", FEED_WORD)
    monkeypatch.setitem(sys.modules, "live_hub", None)              # import live_hub → ImportError
    r = _client().post("/chart-maps/live", json={"symbols": ["XLAB"], "stream": True, "variant": "gajjala"})
    assert r.status_code == 200
    assert r.json()["stream"] == {"on": False, "word": FEED_WORD, "state": "kicked"}
    hub = types.ModuleType("live_hub")

    def boom(*a, **k):
        raise RuntimeError("hub down")

    hub.register_interest = boom
    monkeypatch.setitem(sys.modules, "live_hub", hub)
    r = _client().post("/chart-maps/live", json={"symbols": ["XLAB"], "stream": True, "variant": "gajjala"})
    assert r.status_code == 200 and r.json()["stream"]["on"] is False
    assert json.loads(PRE["plain"][1]) == {k: v for k, v in r.json().items() if k != "stream"}


def test_negative_no_feed_module_serves_null_word_never_a_composed_one(wired, monkeypatch):
    monkeypatch.setitem(sys.modules, "live_feed", None)
    monkeypatch.setitem(sys.modules, "live_hub", None)
    r = _client().post("/chart-maps/live", json={"symbols": ["XLAB"], "stream": True, "variant": "gajjala"})
    assert r.json()["stream"] == {"on": False, "word": None, "state": None}


def test_negative_413_422_and_malformed_levels_unchanged_with_stream(wired):
    c = _client()
    for body in ({"stream": True, "variant": "gajjala"}, {"symbols": "XLAB", "stream": True}):
        r = c.post("/chart-maps/live", json=body)
        assert (r.status_code, r.content.decode("utf-8")) == PRE["e422"], body
    r = c.post("/chart-maps/live", json={**BODIES["e413"], "stream": True, "variant": "gajjala"})
    assert (r.status_code, r.content.decode("utf-8")) == PRE["e413"]
    assert wired["interest"] == [], "a refused read registers nothing"
    r = c.post("/chart-maps/live", json={"symbols": ["XLAB"], "levels": "abc", "stream": True, "variant": "gajjala"})
    assert r.status_code == 200
    assert {k: v for k, v in r.json().items() if k != "stream"} == json.loads(PRE["bad_levels"][1])


# ── vs: ONE engine ───────────────────────────────────────────────────────────────────────────────────────────────
def _pr(sym, p, t_s, recv=None):
    return {"sym": sym, "p": p, "s": 100, "c": [], "t_ms": int(t_s * 1000), "recv": recv or t_s, "trfi": False,
            "kind": "regular"}


@pytest.mark.parametrize("level", [{"trigger": 9.0, "stop": 8.5, "tf": "5m"}, {"trigger": 9.5, "stop": 9.0},
                                   {"trigger": 10.0, "stop": 9.2, "tf": "15m"}, {"trigger": 12.0, "stop": 11.0}])
def test_vs_text_equals_the_poll_vs_text(wired, level):
    poll = LC.compose(["XLAB"], levels={"XLAB": level}, now=FIXED)
    q = poll["quotes"]["XLAB"]
    LE.on_print("gajjala", _pr("XLAB", q["now"]["price"], FIXED.timestamp() - 1), level)
    out = LE.flush(FIXED)
    assert len(out) == 1
    sse = out[0]["quotes"]["XLAB"]["vs"]
    assert sse == q.get("vs"), "same price / level / clock → the same words"
    assert out[0]["quotes"]["XLAB"]["price"] == q["now"]["price"]


def test_no_level_serves_null_vs(wired):
    LE.on_print("gajjala", _pr("XLAB", 9.12, FIXED.timestamp()), None)
    assert LE.flush(FIXED)[0]["quotes"]["XLAB"]["vs"] is None


def test_per_variant_levels_never_cross_talk(wired):
    t = FIXED.timestamp()
    lv5 = {"trigger": 9.0, "stop": 8.5, "tf": "5m"}
    lv1 = {"trigger": 9.5, "stop": 9.0, "tf": "1m"}
    LE.on_print("gajjala", _pr("XLAB", 9.2, t), lv5)
    LE.on_print("gajjala_1m", _pr("XLAB", 9.2, t), lv1)
    out = LE.flush(FIXED)
    assert [p["variant"] for p in out] == ["gajjala", "gajjala_1m"], "variants ascending, one event each"
    by = {p["variant"]: p["quotes"]["XLAB"]["vs"] for p in out}
    et = FIXED.astimezone(LC_ET())
    assert by["gajjala"] == LC.live_vs(9.2, lv5, et) and by["gajjala"]["kind"] == "over_trigger"
    assert by["gajjala_1m"] == LC.live_vs(9.2, lv1, et) and by["gajjala_1m"]["kind"] == "between"
    assert by["gajjala"]["text"] != by["gajjala_1m"]["text"], "NEG: no last-writer-wins across variants"


def LC_ET():
    from chart_maps import board
    return board.ET


# ── batching ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_two_prints_in_200ms_are_one_entry_latest_wins(wired):
    t = FIXED.timestamp()
    LE.on_print("gajjala", _pr("XLAB", 9.10, t - 0.2), None)
    LE.on_print("gajjala", _pr("XLAB", 9.15, t), None)
    out = LE.flush(FIXED)
    assert len(out) == 1 and list(out[0]["quotes"]) == ["XLAB"]
    assert out[0]["quotes"]["XLAB"]["price"] == 9.15
    assert wired["published"] == [("gajjala.update", out[0])], "through events.publish, type gajjala.update"


def test_negative_an_older_print_never_replaces_a_newer_one(wired):
    t = FIXED.timestamp()
    LE.on_print("gajjala", _pr("XLAB", 9.15, t), None)
    LE.on_print("gajjala", _pr("XLAB", 9.10, t - 3), None)          # a late-arriving older print
    q = LE.flush(FIXED)[0]["quotes"]["XLAB"]
    assert (q["price"], q["as_of_epoch"]) == (9.15, t)


def test_at_most_one_batch_per_second_per_variant(wired):
    t = FIXED.timestamp()
    LE.on_print("gajjala", _pr("XLAB", 9.10, t), None)
    assert len(LE.flush(t)) == 1
    LE.on_print("gajjala", _pr("XLAB", 9.11, t + 0.3), None)
    LE.on_print("gajjala_1m", _pr("ABC", 2.0, t + 0.3), None)
    out = LE.flush(t + 0.5)
    assert [p["variant"] for p in out] == ["gajjala_1m"], "NEG: gajjala's second batch waits; another variant does not"
    out = LE.flush(t + 1.0)
    assert [p["variant"] for p in out] == ["gajjala"] and out[0]["quotes"]["XLAB"]["price"] == 9.11


def test_negative_no_new_print_no_batch_and_symbols_sorted(wired):
    t = FIXED.timestamp()
    for s in ("ZZZ", "AAA", "MMM"):
        LE.on_print("gajjala", _pr(s, 3.0, t), None)
    out = LE.flush(t)
    assert list(out[0]["quotes"]) == ["AAA", "MMM", "ZZZ"]
    assert LE.flush(t + 5) == [], "nothing new since the last batch → nothing published"
    assert len(wired["published"]) == 1


def test_negative_no_interest_never_in_a_batch_and_expiry_stops(wired):
    t = FIXED.timestamp()
    live = {("gajjala", "XLAB")}
    LE.on_print("gajjala", _pr("XLAB", 9.1, t), None)
    LE.on_print("gajjala", _pr("NOPE", 1.1, t), None)
    out = LE.flush(t, alive=lambda v, s: (v, s) in live)
    assert list(out[0]["quotes"]) == ["XLAB"], "a symbol without live interest never rides a batch"
    live.clear()                                                    # TTL expired between the print and the batch
    LE.on_print("gajjala", _pr("XLAB", 9.2, t + 2), None)
    assert LE.flush(t + 2, alive=lambda v, s: (v, s) in live) == []
    assert LE.flush(t + 4) == [], "an expired print is dropped, never re-sent later"


def test_negative_unknown_variant_and_bad_prints_dropped(wired):
    t = FIXED.timestamp()
    LE.on_print("gga", _pr("XLAB", 9.1, t), None)                  # the Variant KEY, not the board key
    LE.on_print("nope", _pr("XLAB", 9.1, t), None)
    for bad in ({"sym": "XLAB", "p": float("nan"), "t_ms": 1}, {"sym": "XLAB", "p": -1, "t_ms": 1},
                {"sym": "", "p": 1.0, "t_ms": 1}, {"sym": "XLAB", "p": True, "t_ms": 1}, {"p": 1.0}, None, "x",
                {"sym": "XLAB", "p": 1.0}):
        LE.on_print("gajjala", bad, None)                            # never raises
    assert LE.flush(t) == []


# ── payload keys ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_payload_keys_exactly_as_the_spec(wired):
    t = FIXED.timestamp()
    LE.on_print("gajjala_audited", _pr("XLAB", 9.1, t), {"trigger": 9.0, "stop": 8.0})
    q = LE.flush(t)[0]
    assert tuple(q) == LE.QUOTES_KEYS == ("kind", "variant", "quotes") and q["kind"] == "quotes"
    # WIDENED 2026-11-16 (👀 watch live, spec §3.1): `size` LAST — the 🚩 FE readers pick keys by name
    assert tuple(q["quotes"]["XLAB"]) == LE.QUOTE_KEYS == ("price", "as_of_epoch", "vs", "size")
    assert set(q["quotes"]["XLAB"]["vs"]) == {"kind", "text", "pct_text"}   # pct_text WIDENED 2026-11-12 (🥇 WP-C)
    p = LE.on_pass("gajjala", "2026-09-03|14:01", datetime(2026, 9, 3, 18, 1, 12))
    assert tuple(p) == LE.PASS_KEYS == ("kind", "variant", "pass_id", "finished_at_epoch")
    assert p["finished_at_epoch"] == datetime(2026, 9, 3, 18, 1, 12, tzinfo=timezone.utc).timestamp(), "naive = UTC"
    lane = LE.on_lane_change("2026-09-03", t)
    assert tuple(lane) == LE.LANE_KEYS == ("kind", "day", "changed_at_epoch")
    assert lane == {"kind": "lane", "day": "2026-09-03", "changed_at_epoch": t}
    assert [e[0] for e in wired["published"]] == ["gajjala.update"] * 3


def test_negative_lane_nudge_carries_no_symbol_qty_price_or_pnl(wired):
    lane = LE.on_lane_change(datetime(2026, 9, 3, 15, 0), FIXED)
    banned = re.compile(r"sym|qty|price|pnl|p&l|shares|fill|trigger|stop|px", re.I)
    assert not [k for k in lane if banned.search(k)]
    assert set(lane) == {"kind", "day", "changed_at_epoch"}
    assert all(isinstance(v, (str, float)) for v in lane.values())
    assert LE.on_lane_change("garbage", FIXED) is None and LE.on_lane_change("2026-09-03", "x") is None


# ── pass nudges ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_pass_nudges_route_by_the_store_naming(wired):
    assert LE.pass_variants("gajjala_passes") == ("gajjala", "gajjala_audited")
    assert LE.pass_variants("gajjala_1m_passes") == ("gajjala_1m",)
    fin = datetime(2026, 9, 3, 18, 6, 9)
    a = LE.on_pass_pointer("gajjala_passes", "2026-09-03|14:06", fin)
    assert [p["variant"] for p in a] == ["gajjala", "gajjala_audited"]
    b = LE.on_pass_pointer("gajjala_1m_passes", "2026-09-03|14:06", fin)
    assert [p["variant"] for p in b] == ["gajjala_1m"], "NEG: the 1-minute pointer never nudges 🚩 or 🧪"
    assert LE.on_pass_pointer("gajjala_audited_passes", "x", fin) == []
    assert LE.on_pass_pointer("nope", "x", fin) == []


def test_negative_pass_nudge_refusals(wired):
    fin = datetime(2026, 9, 3, 18, 6, 9)
    assert LE.on_pass("gga", "id", fin) is None, "the Variant key is not a board key"
    assert LE.on_pass("gajjala", "", fin) is None and LE.on_pass("gajjala", None, fin) is None
    assert LE.on_pass("gajjala", "id", "not a date") is None
    assert wired["published"] == []
    assert LE.on_pass("gajjala", "id", "2026-09-03T18:06:09Z")["finished_at_epoch"] == \
        datetime(2026, 9, 3, 18, 6, 9, tzinfo=timezone.utc).timestamp()


# ── wording / scope guards ───────────────────────────────────────────────────────────────────────────────────────
def test_source_guard_words_and_scope():
    src = SRC.read_text()
    assert not re.search(r"bounc", src, re.I), "reversal, never the b-word"
    assert not re.search(r"\bedge\b", src, re.I)
    assert "ajaykandakatla" not in src
    assert not re.search(r"update_one|insert_one|replace_one|\$set|upsert|place_order|broker\.", src), \
        "display only: nothing written, nothing traded"
    assert not re.search(r"VS_TEXT|over the trigger|under the stop", src), "no second formula / word"


def test_constants_named():
    assert LE.EVENT_TYPE == "gajjala.update"
    assert LE.GG_LIVE_QUOTE_BATCH_SEC == 1.0
    assert set(LE.variant_keys()) == {"gajjala", "gajjala_1m", "gajjala_audited"}


# ── the injected vs function (coordinator decision 2026-11-09: option (b)) ───────────────────────────────────────────
def test_negative_live_events_never_names_the_card_module():
    from test_gajjala_live_vs_2026_10_21 import _imports_live_card
    src = SRC.read_text()
    assert not _imports_live_card(src), "the 2026-10-21 import guard holds for live_events.py"
    assert "live_card" not in src and "live_vs" not in src


def test_api_import_injects_the_same_function_object(monkeypatch):
    import importlib
    from chart_maps import api as A
    monkeypatch.setattr(LE, "_vs_fn", None)
    importlib.reload(A)
    assert LE.vs_fn() is LC.live_vs, "the SAME object the poll calls — one engine"


def test_stream_registration_reinjects(wired, monkeypatch):
    monkeypatch.setattr(LE, "_vs_fn", None)
    r = _client().post("/chart-maps/live", json={"symbols": ["XLAB"], "stream": True, "variant": "gajjala"})
    assert r.status_code == 200
    assert LE.vs_fn() is LC.live_vs


def test_vs_equality_through_the_injected_function(wired):
    lv = {"trigger": 9.0, "stop": 8.5, "tf": "5m"}
    poll = LC.compose(["XLAB"], levels={"XLAB": lv}, now=FIXED)["quotes"]["XLAB"]
    _client().post("/chart-maps/live", json={"symbols": ["XLAB"], "stream": True, "variant": "gajjala"})
    LE.on_print("gajjala", _pr("XLAB", poll["now"]["price"], FIXED.timestamp()), lv)
    sse = LE.flush(FIXED)[0]["quotes"]["XLAB"]["vs"]
    assert sse is not None and sse["text"] == poll["vs"]["text"]


def test_negative_nothing_injected_serves_null_vs_never_a_second_formula(wired, monkeypatch):
    monkeypatch.setattr(LE, "_vs_fn", None)
    LE.on_print("gajjala", _pr("XLAB", 9.2, FIXED.timestamp()), {"trigger": 9.0, "stop": 8.5})
    q = LE.flush(FIXED)[0]["quotes"]["XLAB"]
    assert q["vs"] is None and q["price"] == 9.2
    LE.set_vs_fn("not callable")
    assert LE.vs_fn() is None


# ── the REAL feed + hub (critic 2026-11-09: `state` came from feed_state, which never carries it) ──────────────────
@pytest.fixture
def real_feed(monkeypatch):
    """The real live_feed / live_hub modules — NO feed_state stub: the served pair comes from live_feed.state_word()."""
    for name in ("live_feed", "live_hub"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    import live_feed as LF
    import live_hub as LH
    monkeypatch.setenv("MASSIVE_WS_ENABLED", "true")
    monkeypatch.setattr(LH, "_running", True)
    monkeypatch.setattr(LF, "_quiet", lambda now: False)          # an open session, whatever the wall clock says
    return LF, LH


def test_real_feed_kicked_serves_state_kicked_and_the_degraded_word(wired, real_feed, monkeypatch):
    LF, LH = real_feed
    monkeypatch.setitem(LF._link, "kick_pending", True)
    monkeypatch.setitem(LF._link, "yielding_wait", None)
    from chart_maps import api as A
    st = A._stream_interest("gajjala", ["XLAB"], None)
    state, word = LF.state_word()
    assert state == "kicked"
    assert st["state"] == "kicked", "the served state — never None while the hub runs"
    assert st["word"] == word and word.strip(), "the feed's served word, verbatim"
    assert st["on"] is True
    r = _client().post("/chart-maps/live", json={"symbols": ["XLAB"], "stream": True, "variant": "gajjala"})
    assert r.json()["stream"]["state"] == "kicked"                # → the board prints the word (state ≠ live)


def test_negative_real_feed_healthy_serves_state_live(wired, real_feed, monkeypatch):
    LF, LH = real_feed
    monkeypatch.setitem(LF._link, "kick_pending", False)
    monkeypatch.setitem(LF.feed_state, "authed", True)
    r = _client().post("/chart-maps/live", json={"symbols": ["XLAB"], "stream": True, "variant": "gajjala"})
    s = r.json()["stream"]
    assert s["on"] is True and s["state"] == "live", s
    # lib/cardLive.streamFeedWord prints a word only when on is false or state is not "live" → no footer word


def test_negative_real_feed_off_serves_state_off_with_the_off_word(wired, real_feed, monkeypatch):
    LF, LH = real_feed
    monkeypatch.setenv("MASSIVE_WS_ENABLED", "false")
    s = _client().post("/chart-maps/live", json={"symbols": ["XLAB"], "stream": True, "variant": "gajjala"}).json()
    assert s["stream"]["state"] == "off", "state ≠ live → the board prints the served word"
    assert s["stream"]["word"] == LF.FEED_WORDS["off"]



# ══ 👀 Watch live (spec 2026-11-16 §3.1, WP-A1) — live size + the watch tab on the quotes path + the audience ══════
# Ajay 2026-11-16: "Can you make the watch list charts live please" · "Also on the Watch list I need live volume to
# be shown at the bottom" · "Of each chart".
from chart_maps.gajjala_watch import constants as GW          # noqa: E402

OWNER_AUD = frozenset({"o@x"})


def _prs(sym, p, t_s, s):
    return {"sym": sym, "p": p, "s": s, "c": [], "t_ms": int(round(t_s * 1000)), "recv": t_s, "trfi": False,
            "kind": "regular"}


@pytest.fixture
def pub(wired, monkeypatch):
    """`events.publish` recording (args, kwargs) — the audience keyword is visible; GW.live_audience set to the test
    owner (raising=False: passes before AND after WP-A2 adds the function)."""
    import events
    calls: list = []
    monkeypatch.setattr(events, "publish", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(GW, "live_audience", lambda: OWNER_AUD, raising=False)
    return calls


def test_three_prints_in_one_second_are_one_batch_sizes_summed_and_never_carried(pub):
    t = FIXED.timestamp()
    LE.on_print("gajjala_watch", _prs("GP", 1.46, t - 0.9, 100), None)
    LE.on_print("gajjala_watch", _prs("GP", 1.47, t - 0.5, 200), None)
    LE.on_print("gajjala_watch", _prs("GP", 1.48, t - 0.1, 50), None)
    out = LE.flush(t)
    assert len(out) == 1
    q = out[0]["quotes"]["GP"]
    assert q["price"] == 1.48 and q["as_of_epoch"] == pytest.approx(t - 0.1)
    assert q["size"] == 350 and isinstance(q["size"], int)
    LE.on_print("gajjala_watch", _prs("GP", 1.49, t + 1.2, 75), None)
    q2 = LE.flush(t + 1.5)[0]["quotes"]["GP"]
    assert q2["size"] == 75, "NEG: the next batch counts only the new prints — size never carries over"
    assert LE.flush(t + 5) == [], "no new print → no batch"


def test_size_waits_with_the_price_when_the_batch_is_not_due(pub):
    t = FIXED.timestamp()
    LE.on_print("gajjala", _prs("XLAB", 9.1, t, 100), None)
    assert LE.flush(t)[0]["quotes"]["XLAB"]["size"] == 100
    LE.on_print("gajjala", _prs("XLAB", 9.2, t + 0.2, 30), None)
    assert LE.flush(t + 0.5) == [], "batch not due"
    LE.on_print("gajjala", _prs("XLAB", 9.3, t + 0.7, 20), None)
    q = LE.flush(t + 1.0)[0]["quotes"]["XLAB"]
    assert (q["price"], q["size"]) == (9.3, 50), "counted in exactly one batch, never dropped while waiting"


def test_an_older_stamped_print_adds_its_size_but_never_moves_price(pub):
    t = FIXED.timestamp()
    LE.on_print("gajjala_watch", _prs("GP", 1.50, t, 100), None)
    LE.on_print("gajjala_watch", _prs("GP", 1.40, t - 3, 400), None)       # arrives late, older SIP stamp
    q = LE.flush(t)[0]["quotes"]["GP"]
    assert (q["price"], q["as_of_epoch"]) == (1.50, t), "NEG: the older print never replaces the newer price"
    assert q["size"] == 500, "its real volume is still counted"


def test_an_equal_stamp_replaces_the_price_and_adds_the_size(pub):
    t = FIXED.timestamp()
    LE.on_print("gajjala_watch", _prs("GP", 1.50, t, 100), None)
    LE.on_print("gajjala_watch", _prs("GP", 1.51, t, 10), None)
    q = LE.flush(t)[0]["quotes"]["GP"]
    assert (q["price"], q["size"]) == (1.51, 110)


@pytest.mark.parametrize("bad", [None, 0, -5, float("nan"), float("inf"), True, False, "100", [100], {"s": 1}])
def test_negative_a_bad_size_is_never_counted_the_price_still_rides(pub, bad):
    t = FIXED.timestamp()
    LE.on_print("gajjala_watch", _prs("GP", 1.48, t, bad), None)
    q = LE.flush(t)[0]["quotes"]["GP"]
    assert q["price"] == 1.48 and q["size"] == 0 and isinstance(q["size"], int), "no valid size seen → 0"
    LE.on_print("gajjala_watch", _prs("GP", 1.49, t + 1, 100), None)
    LE.on_print("gajjala_watch", _prs("GP", 1.50, t + 1.1, bad), None)
    q = LE.flush(t + 1.5)[0]["quotes"]["GP"]
    assert (q["price"], q["size"]) == (1.50, 100), "a bad size adds nothing beside a good one"


def test_negative_a_print_without_an_s_key_counts_nothing(pub):
    t = FIXED.timestamp()
    pr = _prs("GP", 1.48, t, 1)
    del pr["s"]
    LE.on_print("gajjala_watch", pr, None)
    assert LE.flush(t)[0]["quotes"]["GP"]["size"] == 0


def test_a_fractional_size_stays_a_float_an_integral_float_becomes_int(pub):
    t = FIXED.timestamp()
    LE.on_print("gajjala_watch", _prs("GP", 1.48, t, 0.5), None)
    LE.on_print("gajjala_watch", _prs("AKAN", 2.0, t, 100.0), None)
    qs = LE.flush(t)[0]["quotes"]
    assert qs["GP"]["size"] == 0.5 and isinstance(qs["GP"]["size"], float)
    assert qs["AKAN"]["size"] == 100 and isinstance(qs["AKAN"]["size"], int)
    assert list(qs) == ["AKAN", "GP"], "symbols ascending (unchanged)"


@pytest.mark.parametrize("junk", [float("nan"), -1, 0, True, None, "1.48"])
def test_negative_a_junk_price_makes_no_entry_and_its_size_is_not_counted(pub, junk):
    t = FIXED.timestamp()
    LE.on_print("gajjala_watch", _prs("GP", junk, t, 500), None)
    assert LE.flush(t) == [] and pub == [], "no entry at all"
    LE.on_print("gajjala_watch", _prs("GP", 1.48, t + 1, 100), None)
    LE.on_print("gajjala_watch", _prs("GP", junk, t + 1.1, 500), None)
    q = LE.flush(t + 1.5)[0]["quotes"]["GP"]
    assert (q["price"], q["size"]) == (1.48, 100), "NEG: the junk print's size never rides"


def test_the_watch_tab_rides_the_quotes_path_with_null_vs(pub):
    t = FIXED.timestamp()
    LE.on_print("gajjala_watch", _prs("GP", 1.48, t, 350), None)
    out = LE.flush(t)
    assert out == [{"kind": "quotes", "variant": "gajjala_watch",
                    "quotes": {"GP": {"price": 1.48, "as_of_epoch": t, "vs": None, "size": 350}}}]
    assert tuple(out[0]["quotes"]["GP"]) == LE.QUOTE_KEYS


def test_extra_tabs_and_quote_tabs_name_the_watch_once():
    assert LE.extra_tabs() == (GW.TAB,) == ("gajjala_watch",)
    assert LE.quote_tabs() == LE.variant_keys() + LE.extra_tabs()
    assert GW.TAB not in LE.variant_keys(), "the watch is a board key, never a Variant"


def test_negative_unknown_and_near_miss_tabs_still_dropped(pub):
    t = FIXED.timestamp()
    for tab in ("GAJJALA_WATCH", "gajjala_watch ", "gajjala_5m", "", "ggw", "watch"):
        LE.on_print(tab, _prs("GP", 1.48, t, 100), None)
    assert LE.flush(t) == [] and pub == []


def test_negative_the_watch_gets_no_pass_nudge(pub):
    fin = datetime(2026, 11, 16, 18, 6, 9)
    assert LE.on_pass("gajjala_watch", "2026-11-16|13:06", fin) is None
    assert pub == [], "on_pass keeps variant_keys() — nothing published for the watch"
    assert "gajjala_watch" not in LE.pass_variants("gajjala_passes") + LE.pass_variants("gajjala_1m_passes")


# ── audience [C1] ────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_gajjala_batch_is_published_byte_identical_to_today_no_keyword(pub):
    t = FIXED.timestamp()
    LE.on_print("gajjala", _prs("XLAB", 9.1, t, 100), None)
    out = LE.flush(t)
    assert pub == [(("gajjala.update", out[0]), {})], "NEG: no audience keyword at all — not even audience=None"


@pytest.mark.parametrize("variant", ["gajjala", "gajjala_1m", "gajjala_audited"])
def test_every_variant_tab_has_no_audience(variant):
    assert LE._audience(variant) is None


def test_a_watch_batch_carries_the_owner_only_audience(pub):
    t = FIXED.timestamp()
    LE.on_print("gajjala_watch", _prs("GP", 1.48, t, 100), None)
    out = LE.flush(t)
    assert pub == [(("gajjala.update", out[0]), {"audience": frozenset({"o@x"})})]


def test_both_variants_in_one_second_two_publishes_each_with_its_own_audience(pub):
    t = FIXED.timestamp()
    LE.on_print("gajjala_watch", _prs("GP", 1.48, t, 100), None)
    LE.on_print("gajjala", _prs("GP", 1.48, t, 100), None)
    out = LE.flush(t)
    assert [p["variant"] for p in out] == ["gajjala", "gajjala_watch"], "variants ascending"
    assert [(a[1]["variant"], k) for a, k in pub] == [("gajjala", {}), ("gajjala_watch", {"audience": OWNER_AUD})]


def test_negative_a_raising_audience_source_publishes_to_nobody_with_one_warning(pub, monkeypatch, caplog):
    def boom():
        raise RuntimeError("no admin email")

    monkeypatch.setattr(GW, "live_audience", boom, raising=False)
    t = FIXED.timestamp()
    LE.on_print("gajjala_watch", _prs("GP", 1.48, t, 100), None)
    with caplog.at_level("WARNING", logger="chart_maps.gajjala.live_events"):
        out = LE.flush(t)
    assert len(out) == 1
    assert pub == [(("gajjala.update", out[0]), {"audience": frozenset()})], "fail closed — never a broadcast"
    warns = [r for r in caplog.records if r.levelname == "WARNING" and r.name == "chart_maps.gajjala.live_events"]
    assert len(warns) == 1 and "nobody" in warns[0].getMessage()


@pytest.mark.parametrize("bad", ["o@x", ["o@x"], None, 1])
def test_negative_a_non_set_audience_fails_closed(pub, monkeypatch, bad):
    monkeypatch.setattr(GW, "live_audience", lambda: bad, raising=False)
    assert LE._audience("gajjala_watch") == frozenset()


def test_negative_a_missing_audience_source_fails_closed(pub, monkeypatch):
    monkeypatch.delattr(GW, "live_audience", raising=False)
    assert LE._audience("gajjala_watch") == frozenset(), "before WP-A2: nobody, never everyone"


def test_source_pin_the_flag_call_is_unchanged():
    src = SRC.read_text()
    body = src[src.index("def _publish("):src.index("# ── the hub's calls")]
    assert len(re.findall(r"\n\s+publish\(EVENT_TYPE, payload\)\s", body)) == 1, "the 🚩 call, unchanged"
    assert body.count("publish(EVENT_TYPE, payload, audience=audience)") == 1
    assert len(re.findall(r"(?<![\w])publish\(", body)) == 2, "exactly the two calls — no third path"
