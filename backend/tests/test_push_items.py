"""Every item of a consolidated push, each ticker its own link — push core (2026-09-29).

Ajay, on the /alerts card "⚡ Tape burst at a zone — CRWV +7 more": "I am unable
to see the other that are hiddedn her … Can you show them all and make all the
tickers clicable individually?"

Layers pinned here (spec alerts_all_tickers §3.2-3.5):
  1. push.sender strips the LOG-ONLY ``items`` before a device sees the payload,
     while push.history still records the full dict;
  2. push.history stores sanitized ``items`` (capped MAX_ITEMS) + ``items_total``;
  3. push.recent.served_items rebuilds one linked line per entry (body lines
     first, then the entries the phone never showed), including OLD rows parsed
     from the body against the known universe;
  4. the juggernaut / leaderboard hooks log every entry.

Hermetic: no Mongo, no network — collections, loaders and ``known`` are injected.
"""
import inspect
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from push import history as H          # noqa: E402
from push import recent as R           # noqa: E402
from push import sender as S           # noqa: E402

KNOWN = frozenset({"CRWV", "KLAC", "NVDA", "AVGO", "PCT", "BRK.B", "BRK-B", "ET", "AT"})
HIS_TITLE = "⚡ Tape burst at a zone — CRWV +7 more"
HIS_BODY = ("CRWV 13:17:30 — $1.8M sell burst, sellers defending the supply ceiling\n"
            "CRWV 13:14:30 — $1.0M buy burst, buyers pushing INTO the supply ceiling\n"
            "CRWV 13:15:40 — $897K buy burst, buyers pushing INTO the supply ceiling\n"
            "KLAC 13:14:30 — $562K buy burst, buyers pushing INTO the supply ceiling")


def _tf_items(syms):
    return [{"symbol": s, "text": f"{s} 13:{10 + i:02d}:00 — $1.0M buy burst, buyers pushing INTO the supply ceiling"}
            for i, s in enumerate(syms)]


# ---------------------------------------------------------------------------
# 1. sender
# ---------------------------------------------------------------------------
def test_device_payload_strips_items_and_keeps_every_other_key():
    p = {"title": "t", "body": "b", "url": "/u", "kind": "trade_flash",
         "items": _tf_items(["CRWV", "KLAC"])}
    device = S.device_payload(p)
    assert json.dumps(device) == json.dumps({k: v for k, v in p.items() if k != "items"})
    assert "items" not in device
    # NEGATIVE: the caller's dict (what history records) is never mutated
    assert "items" in p and len(p["items"]) == 2


def test_device_payload_without_items_is_unchanged():
    p = {"title": "t", "body": "b", "url": "/u", "kind": "demand_alert", "tickers": ["NVDA"]}
    assert S.device_payload(p) == p
    assert S.device_payload(p) is p, "nothing to strip -> the same object"
    assert S.LOG_ONLY_KEYS == frozenset({"items"})


@pytest.fixture
def push_stack(monkeypatch):
    from market_hours import gate
    from push import subs
    sent, recorded = [], []
    monkeypatch.setattr(gate, "should_drop_kind", lambda *a, **k: None)
    monkeypatch.setattr(subs, "list_subscriptions",
                        lambda *a, **k: [{"endpoint": "e1", "keys": {}}, {"endpoint": "e2", "keys": {}}])
    monkeypatch.setattr(S, "_send_one", lambda sub, payload: sent.append(payload) or True)
    monkeypatch.setattr(H, "record", lambda payload, **k: recorded.append(payload))
    return sent, recorded


@pytest.mark.parametrize("path", ["user", "all"])
def test_send_paths_hand_the_device_no_items_and_history_the_full_dict(push_stack, path):
    sent, recorded = push_stack
    p = {"title": HIS_TITLE, "body": "b", "url": "/u", "kind": "trade_flash",
         "items": _tf_items(["CRWV"] * 8)}
    if path == "user":
        out = S.send_to_user("a@x", p, kind="trade_flash")
    else:
        out = S.send_to_all(p, kind="trade_flash")
    assert out["sent"] == 2
    assert len(sent) == 2 and all("items" not in d for d in sent)
    assert all(set(d) == {"title", "body", "url", "kind"} for d in sent)
    assert len(recorded) == 1 and len(recorded[0]["items"]) == 8, "history gets the FULL payload"


# ---------------------------------------------------------------------------
# 2. history
# ---------------------------------------------------------------------------
class _Coll:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        self.docs.append(doc)


@pytest.fixture
def coll(monkeypatch):
    c = _Coll()
    monkeypatch.setattr(H, "_get_coll", lambda: c)
    return c


def _rec(coll, items):
    payload = {"title": "t", "body": "b", "kind": "trade_flash"}
    if items is not None:
        payload["items"] = items
    H.record(payload)
    return coll.docs[-1]


def test_history_stores_items_upper_and_stripped(coll):
    d = _rec(coll, [{"symbol": " crwv ", "text": "  CRWV 13:17:30 — burst  "},
                    {"symbol": "BRK.B", "text": "BRK.B x"}, {"symbol": "BRK-B", "text": "BRK-B y"}])
    assert d["items"] == [{"symbol": "CRWV", "text": "CRWV 13:17:30 — burst"},
                          {"symbol": "BRK.B", "text": "BRK.B x"},
                          {"symbol": "BRK-B", "text": "BRK-B y"}]
    assert d["items_total"] == 3
    assert "MAX_ITEMS" in H.__all__


def test_history_caps_at_max_items_keeping_the_head(coll):
    d = _rec(coll, [{"symbol": f"S{i}", "text": f"S{i} line"} for i in range(130)])
    assert len(d["items"]) == H.MAX_ITEMS == 100
    assert d["items_total"] == 130
    assert [it["symbol"] for it in d["items"][:3]] == ["S0", "S1", "S2"]
    assert d["items"][-1]["symbol"] == "S99"


def test_history_trims_a_long_text_never_drops_it(coll):
    d = _rec(coll, [{"symbol": "NVDA", "text": "N" * 400}])
    assert len(d["items"][0]["text"]) == H.ITEM_TEXT_MAX == 300


@pytest.mark.parametrize("raw", [None, "CRWV", [], [7], [{"symbol": "X"}], [{"text": "  "}]])
def test_NEGATIVE_history_stores_none_for_invalid_items(coll, raw):
    d = _rec(coll, raw)
    assert d["items"] is None and d["items_total"] is None


def test_NEGATIVE_history_drops_unknown_keys_and_non_str_symbols(coll):
    d = _rec(coll, [{"symbol": "NVDA", "text": "NVDA x", "url": "/evil", "evil": 1},
                    {"symbol": 7, "text": "seven"}])
    assert d["items"] == [{"symbol": "NVDA", "text": "NVDA x"}, {"symbol": None, "text": "seven"}]
    assert d["items_total"] == 2


# ---------------------------------------------------------------------------
# 3. served_items
# ---------------------------------------------------------------------------
def _stored_tf_row(n=8, shown=4):
    items = _tf_items(["CRWV", "KLAC", "NVDA", "AVGO", "CRWV", "KLAC", "NVDA", "AVGO"][:n])
    return {"kind": "trade_flash", "title": f"⚡ Tape burst at a zone — CRWV +{n - 1} more",
            "body": "\n".join(it["text"] for it in items[:shown]), "ticker": None,
            "items": items, "items_total": n}


def test_stored_trade_flash_row_lists_every_item_in_order():
    row = _stored_tf_row()
    items, not_stored = R.served_items(row, KNOWN)
    assert len(items) == 8
    assert [e["pushed"] for e in items] == [True] * 4 + [False] * 4
    assert [e["symbol"] for e in items] == [it["symbol"] for it in row["items"]]
    assert [e["text"] for e in items] == [it["text"] for it in row["items"]]
    assert all(e["url"] == f"/sepa/{e['symbol']}?tab=tape&from=supply-demand" for e in items)
    assert not_stored == 0


def test_stored_row_reports_what_the_cap_dropped():
    items = [{"symbol": "NVDA", "text": f"NVDA line {i}"} for i in range(100)]
    row = {"kind": "trade_flash", "body": "NVDA line 0", "items": items, "items_total": 130}
    _items, not_stored = R.served_items(row, KNOWN)
    assert not_stored == 30 and len(_items) == 100


def test_positional_match_trusts_the_builders_symbol_outside_token():
    row = {"kind": "trade_flash", "body": "ABCDEF 13:00:00 — burst",
           "items": [{"symbol": "ABCDEF", "text": "ABCDEF 13:00:00 — burst"},
                     {"symbol": "NVDA", "text": "NVDA 13:01:00 — burst"}], "items_total": 2}
    items, _ = R.served_items(row, KNOWN)
    assert [(e["symbol"], e["pushed"]) for e in items] == [("ABCDEF", True), ("NVDA", False)], \
        "matched positionally, not duplicated as unpushed"


def test_premkt_suffix_on_the_last_body_line_still_matches():
    lines = ["NVDA $1 · 0.3% under $1–2", "AVGO $2 · 0.4% under $1–2"]
    row = {"kind": "supply_break_alert", "body": "\n".join(lines) + " · pre-mkt",
           "items": [{"symbol": "NVDA", "text": lines[0]}, {"symbol": "AVGO", "text": lines[1]},
                     {"symbol": "CRWV", "text": "CRWV $3"}], "items_total": 3}
    items, _ = R.served_items(row, KNOWN)
    assert [(e["symbol"], e["pushed"]) for e in items] == [("NVDA", True), ("AVGO", True), ("CRWV", False)]
    assert items[1]["text"].endswith(" · pre-mkt"), "the body line is kept verbatim"


def test_his_legacy_row_links_four_lines_and_says_four_not_stored():
    row = {"kind": "trade_flash", "title": HIS_TITLE, "body": HIS_BODY, "ticker": None,
           "tickers": None, "url": "/sepa/CRWV?tab=tape&from=supply-demand"}
    items, not_stored = R.served_items(row, KNOWN)
    assert [e["symbol"] for e in items] == ["CRWV", "CRWV", "CRWV", "KLAC"]
    assert all(e["pushed"] for e in items)
    assert items[3]["url"] == "/sepa/KLAC?tab=tape&from=supply-demand"
    assert not_stored == 4


def test_legacy_demand_tail_wins_over_the_title():
    row = {"kind": "demand_alert", "title": "🧲 Nearing demand — NVDA +8 more", "ticker": None,
           "body": "NVDA $1 · 2% above\nAVGO $2 · 3% above\n+3 more on the board"}
    items, not_stored = R.served_items(row, KNOWN)
    assert not_stored == 3
    assert items[-1]["symbol"] is None and items[-1]["url"] is None
    assert items[-1]["text"] == "+3 more on the board"


def test_legacy_key_level_links_to_the_support_tab():
    row = {"kind": "key_level_alert", "title": "🔑 Key levels closed through — PCT over x", "ticker": None,
           "body": "PCT closed over prior-month high $1\nUnmeasured — a close through a level, not a signal."}
    items, _ = R.served_items(row, KNOWN)
    assert items[0]["url"] == "/chart-maps?tab=support&symbol=PCT"
    assert items[1]["symbol"] is None


def test_legacy_juggernaut_markers_are_skipped():
    row = {"kind": "juggernaut_watchlist", "ticker": None, "body": "🆕 NVDA · $1\n   AVGO · $2"}
    items, not_stored = R.served_items(row, KNOWN)
    assert [e["symbol"] for e in items] == ["NVDA", "AVGO"] and not_stored == 0


def test_legacy_class_shares_resolve_when_known():
    row = {"kind": "demand_alert", "ticker": None, "body": "BRK.B $1 · x\nBRK-B $2 · y"}
    items, _ = R.served_items(row, KNOWN)
    assert [e["symbol"] for e in items] == ["BRK.B", "BRK-B"]


def test_NEGATIVE_legacy_single_is_not_itemized():
    row = {"kind": "demand_alert", "ticker": "NVDA", "body": "NVDA $1 · x"}
    assert R.served_items(row, KNOWN) is None


def test_NEGATIVE_kind_outside_item_kinds_is_not_itemized():
    row = {"kind": "morning_brief", "ticker": None, "body": "NVDA, AVGO lead"}
    assert R.served_items(row, KNOWN) is None


def test_NEGATIVE_lower_case_lead_never_links():
    row = {"kind": "trade_flash", "ticker": None, "body": "crwv 13:17 — x\nNVDA 13:18 — y"}
    items, _ = R.served_items(row, KNOWN)
    assert items[0]["symbol"] is None and items[1]["symbol"] == "NVDA"


def test_NEGATIVE_unknown_symbol_stays_plain_and_still_counts_as_printed():
    body = "PPA 13:00:00 — x\nNVDA 13:01:00 — y\nAVGO 13:02:00 — z\nKLAC 13:03:00 — w"
    row = {"kind": "trade_flash", "title": "⚡ Tape burst at a zone — PPA +3 more", "ticker": None, "body": body}
    items, not_stored = R.served_items(row, KNOWN)
    assert items[0]["symbol"] is None and items[0]["url"] is None
    assert not_stored == 0, "a plain line still counts, so the claim never inflates"


def test_NEGATIVE_title_count_is_clamped_at_zero():
    body = "\n".join(f"NVDA 13:0{i}:00 — x" for i in range(5))
    row = {"kind": "trade_flash", "title": "⚡ Tape burst at a zone — NVDA +1 more", "ticker": None, "body": body}
    _items, not_stored = R.served_items(row, KNOWN)
    assert not_stored == 0


@pytest.mark.parametrize("body", [None, ""])
def test_NEGATIVE_empty_body_gives_none(body):
    assert R.served_items({"kind": "trade_flash", "ticker": None, "body": body}, KNOWN) is None


def test_NEGATIVE_body_without_a_symbol_line_gives_none():
    row = {"kind": "demand_alert", "ticker": None, "body": "$68.39 · tested 4x"}
    assert R.served_items(row, KNOWN) is None


def test_NEGATIVE_garbage_items_fall_back_to_the_legacy_parse():
    row = {"kind": "trade_flash", "title": HIS_TITLE, "ticker": None, "body": HIS_BODY,
           "items": "garbage", "items_total": 99}
    items, not_stored = R.served_items(row, KNOWN)
    assert [e["symbol"] for e in items] == ["CRWV", "CRWV", "CRWV", "KLAC"]
    assert not_stored == 4, "legacy arithmetic, not items_total"


def test_lead_token_and_symbol():
    assert R.lead_token("+3 more") == "+3" and R.lead_symbol("+3 more", KNOWN) is None
    assert R.lead_symbol("$68.39 · tested", KNOWN) is None
    assert R.lead_symbol("(NVDA) x", KNOWN) == "NVDA"
    assert R.lead_token("🆕 NVDA · $1") == "NVDA"
    assert R.lead_token("") == "" and R.lead_token("   ") == ""
    # NEGATIVE: a known-shaped token outside the universe
    assert R.lead_symbol("PPA 13:00", KNOWN) is None


# ---------------------------------------------------------------------------
# 4. _gather / the route
# ---------------------------------------------------------------------------
def _push_row(**kw):
    base = {"_id": "p1", "ts": 400, "ts_iso": "2026-09-29T17:17:30+00:00", "title": HIS_TITLE,
            "body": HIS_BODY, "kind": "trade_flash", "ticker": None, "tickers": None,
            "url": "/sepa/CRWV?tab=tape&from=supply-demand", "user_email": None,
            "sent": 0, "failed": 0, "total": 0}
    base.update(kw)
    return base


def test_route_serves_items_on_a_trade_flash_row_and_nothing_on_a_growth_row(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from auth import current_user_email
    from sepa import breakouts as bk
    monkeypatch.setattr(R, "known_symbols", lambda *a, **k: KNOWN)
    growth = {"_id": "p2", "ts": 300, "ts_iso": "2026-09-29T17:00:00+00:00",
              "title": "🚀 3 growth names at demand", "body": "NVDA, AVGO · pushed 08:15 ET",
              "kind": "growth_demand_alert", "ticker": None, "url": "/chart-maps?tab=growth",
              "user_email": None, "sent": 1, "failed": 0, "total": 1, "items": None, "items_total": None}
    rows_in = [_push_row(items=None, items_total=None), growth]
    monkeypatch.setattr(H, "list_recent", lambda e, l, **k: [dict(r) for r in rows_in])
    monkeypatch.setattr(bk, "_get_db", lambda: None)
    app = FastAPI()
    app.include_router(R.router)
    app.dependency_overrides[current_user_email] = lambda: "a@x"
    rows = TestClient(app).get("/notifications/recent").json()["rows"]
    tf, gr = rows
    assert [e["symbol"] for e in tf["items"]] == ["CRWV", "CRWV", "CRWV", "KLAC"]
    assert tf["items_not_stored"] == 4
    assert "items_total" not in tf
    assert "items" not in gr and "items_not_stored" not in gr and "items_total" not in gr


def test_gather_never_serves_items_total_and_the_fold_keeps_the_survivors_items(monkeypatch):
    monkeypatch.setattr(R, "known_symbols", lambda *a, **k: KNOWN)
    stored = _stored_tf_row()
    a = _push_row(_id="a", ts=500, body=stored["body"], title=stored["title"],
                  items=stored["items"], items_total=8)
    b = _push_row(_id="b", ts=400, body=stored["body"], title=stored["title"],
                  items=stored["items"][:5], items_total=5)
    rows = R.gather("a@x", 10, list_recent=lambda e, l, **k: [dict(a), dict(b)],
                    get_db=lambda: None)
    assert len(rows) == 1 and rows[0]["repeat"]["count"] == 2
    assert len(rows[0]["items"]) == 8, "the survivor's own items"
    assert "items_total" not in rows[0]


# ---------------------------------------------------------------------------
# 5. URL pins against the composers' own functions
# ---------------------------------------------------------------------------
def test_item_urls_match_each_kinds_single_push_url():
    from supply_demand import zone_edge as ZE
    from supply_demand import key_level_alerts as KLA
    from catalysts.medical import alerts as MA
    assert R.item_url("supply_break_alert", "NVDA") == ZE._url("NVDA")
    assert R.item_url("key_level_alert", "NVDA") == KLA.url_for("NVDA")
    assert "?tab=catalyst" in inspect.getsource(MA.single_text)
    assert R.item_url("med_catalyst", "NVDA") == "/sepa/NVDA?tab=catalyst"
    src = (Path(__file__).resolve().parents[1] / "orderflow" / "trade_flash.py").read_text()
    assert "?tab=tape&from=supply-demand" in src
    assert R.item_url("trade_flash", "NVDA") == "/sepa/NVDA?tab=tape&from=supply-demand"
    assert R.item_url("demand_alert", "NVDA") == "/sepa/NVDA?tab=supply"
    assert R.item_url("zone_bounce_alert", "NVDA") == "/sepa/NVDA?tab=supply"
    # NEGATIVE: an unknown / None kind falls back to the page's own chip destination
    assert R.item_url("morning_brief", "NVDA") == R.item_url(None, "NVDA") == "/sepa/NVDA?tab=supply"
    assert R.ITEM_KINDS == frozenset(R.ITEM_URL_BY_KIND) and len(R.ITEM_KINDS) == 9


# ---------------------------------------------------------------------------
# 6. hooks
# ---------------------------------------------------------------------------
@pytest.fixture
def hook_spy(monkeypatch):
    from push import hooks
    calls = []
    monkeypatch.setattr(hooks.sender, "send_to_all",
                        lambda payload, kind=None: calls.append(payload) or {"sent": 1})
    return hooks, calls


def test_juggernaut_hook_logs_every_entry(hook_spy):
    hooks, calls = hook_spy
    jug = [{"ticker": f"J{chr(65 + i)}", "last_close": 10.0 + i, "day_change_pct": 1.0,
            "ud_ratio": 1.6, "momentum": "rising"} for i in range(11)]
    hooks.notify_juggernauts(juggernauts=jug, new_today=["JA"], today_et="2026-09-29")
    p = calls[-1]
    lines = p["body"].split("\n")
    assert len(lines) == 9 and lines[-1] == "+3 more on /watchlist", "body unchanged"
    assert len(p["items"]) == 11
    assert [it["symbol"] for it in p["items"]] == [j["ticker"] for j in jug]
    assert [it["text"] for it in p["items"][:8]] == lines[:8]
    assert p["items"][0]["text"].startswith("🆕 JA ·")


def test_leaderboard_hook_logs_every_entry_and_keeps_the_ticker_rule(hook_spy):
    hooks, calls = hook_spy
    bo = [{"symbol": f"L{chr(65 + i)}", "last_close": 5.0, "rank": i + 1} for i in range(10)]
    hooks.notify_leaderboard_breakout(broke_out=bo, today_et="2026-09-29")
    p = calls[-1]
    assert len(p["items"]) == 10 and p["ticker"] is None
    assert p["body"].split("\n")[-1] == "+2 more"
    hooks.notify_leaderboard_breakout(broke_out=bo[:1], today_et="2026-09-29")
    assert calls[-1]["ticker"] == "LA" and len(calls[-1]["items"]) == 1


def test_hooks_source_guard():
    from push import hooks
    assert '"items"' in inspect.getsource(hooks.notify_juggernauts)
    assert '"items"' in inspect.getsource(hooks.notify_leaderboard_breakout)
