"""Per-ticker links on every alert row — the backend half (2026-09-20).

Ajay: "I need the stock tickers to be clickables in alerts individually if
there are multiple in one alert by command click".

Three layers, tested here:
  1. each of the five digest builders carries ``tickers`` in BODY order;
  2. ``push.history.record`` stores that list (upper, capped, else None);
  3. ``push.recent.gather`` serves a list on EVERY row — the stored one, the
     single's own ticker, or, for a DIGEST kind only, the leading tokens of an
     old body validated against the universe ∪ RENAMES ∪ DELISTED.

The derivation is the risky half, so the negatives are the point: a token is
read ONLY from the leading position of a comma/newline item, only for a digest
kind, and only when the universe knows it. A flashcard body that says
"NEW, AT, ET" must yield nothing.

Pure: no Mongo, no network — the collection, the feed loaders and the universe
loader are all injected.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from push import history as H          # noqa: E402
from push import recent as R           # noqa: E402


# ---------------------------------------------------------------------------
# 1. the five digest builders
# ---------------------------------------------------------------------------
def test_growth_digest_lists_every_name_in_body_order():
    from growth import alerts as GA
    items = [{"row": {"symbol": s}} for s in ("NVDA", "AVGO", "CRDO")]
    m = GA.digest_message(items)
    assert m["body"] == "NVDA, AVGO, CRDO"
    assert m["tickers"] == ["NVDA", "AVGO", "CRDO"], "body order, not sorted"
    assert m["ticker"] is None, "a digest names nobody in particular"


def _dband(lo, hi, touches=3):
    return {"lo": lo, "hi": hi, "touches": touches, "kind": "demand"}


def test_demand_digest_tickers_follow_the_body_and_stop_at_digest_max():
    from supply_demand import demand_alerts as DA
    items = [{"symbol": f"S{i}", "last": 100.0 + i, "band": _dband(90, 97), "cap": 2e9,
              "hit": {"tier": "near", "state": "falling", "dist_pct": 3.0 - i * 0.2}}
             for i in range(8)]
    m = DA.digest_message(items)
    lines = m["body"].split("\n")
    assert m["tickers"] == [ln.split(" ")[0] for ln in lines[:DA.DIGEST_MAX]]
    assert m["tickers"] == ["S7", "S6", "S5", "S4", "S3", "S2"][:DA.DIGEST_MAX]
    # NEGATIVE: the "+N more on the board" tail names nobody, so it is not a link
    assert lines[-1] == "+2 more on the board" and len(m["tickers"]) == DA.DIGEST_MAX
    assert m["ticker"] is None


def test_zone_bounce_digest_tickers_are_strongest_first():
    from supply_demand import zone_bounce_alerts as ZB
    items = [{"symbol": f"B{i}", "print": 50.0 + i, "band": _dband(45, 49), "cap": 3e9,
              "room": None, "hit": {"bounce_pct": 1.0 + i}}
             for i in range(3)]
    m = ZB.digest_message(items)
    assert m["tickers"] == ["B2", "B1", "B0"], "sorted by bounce_pct desc, like the body"
    assert [ln.split(" ")[0] for ln in m["body"].split("\n")] == m["tickers"]
    assert m["ticker"] is None


def test_hot_pullback_digest_tickers_are_the_first_twelve():
    from supply_demand import hot_pullback_alerts as HPA
    rows = [{"symbol": f"H{i}"} for i in range(15)]
    m = HPA.digest_message(rows, "2026-09-18")
    assert m["tickers"] == [f"H{i}" for i in range(12)]
    assert m["body"].startswith("H0, H1,") and "H12" not in m["body"]
    assert m["ticker"] is None
    # NEGATIVE: no rows -> no digest at all
    assert HPA.digest_message([], "2026-09-18") is None


def test_pattern_digest_tickers_are_the_first_ten_despite_the_paren_prose():
    from patterns import pattern_alerts as PA
    rows = [{"symbol": f"P{i}", "pattern": "cup_with_handle"} for i in range(13)]
    m = PA.digest_message(rows, "2026-09-18")
    assert m["tickers"] == [f"P{i}" for i in range(10)]
    assert m["body"].startswith("P0 (cup with handle)")
    assert m["ticker"] is None
    assert PA.digest_message([], "2026-09-18") is None


# ---------------------------------------------------------------------------
# 2. storage
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


def test_record_stores_the_list_upper_cased_and_capped(coll):
    H.record({"title": "t", "body": "b", "kind": "demand_alert",
              "tickers": ["nvda", "AvGo"]})
    assert coll.docs[-1]["tickers"] == ["NVDA", "AVGO"]
    H.record({"title": "t", "body": "b", "kind": "demand_alert",
              "tickers": [f"S{i}" for i in range(40)]})
    assert len(coll.docs[-1]["tickers"]) == H.MAX_TICKERS == 25
    assert coll.docs[-1]["tickers"][0] == "S0", "the cap keeps the head, in order"


@pytest.mark.parametrize("raw", [None, "NVDA", [], ["NVDA", 7], 12, {"a": 1}])
def test_record_stores_none_for_anything_that_is_not_a_list_of_strings(coll, raw):
    payload = {"title": "t", "body": "b", "kind": "demand_alert"}
    if raw is not None:
        payload["tickers"] = raw
    H.record(payload)
    assert coll.docs[-1]["tickers"] is None


def test_record_still_stores_the_single_ticker_untouched(coll):
    H.record({"title": "t", "body": "b", "kind": "demand_alert", "ticker": "ERIE"})
    assert coll.docs[-1]["ticker"] == "ERIE" and coll.docs[-1]["tickers"] is None


# ---------------------------------------------------------------------------
# 3. the derivation
# ---------------------------------------------------------------------------
KNOWN = frozenset({"NVDA", "AVGO", "CRDO", "ET", "AT", "NEW", "BRK-B", "ECHO", "SATS"})


def _row(**kw):
    base = {"kind": "demand_alert", "body": "", "ticker": None}
    base.update(kw)
    return base


def test_stored_list_wins_and_is_deduped_in_order():
    r = _row(tickers=["nvda", "AVGO", "NVDA"], ticker="ZZZ", body="anything")
    assert R.derive_tickers(r, KNOWN) == ["NVDA", "AVGO"]


def test_single_push_falls_back_to_its_own_ticker():
    assert R.derive_tickers(_row(ticker="ntap"), KNOWN) == ["NTAP"], \
        "a single links its own name even when it is not in the injected set"


def test_old_digest_body_derives_only_the_leading_tokens():
    r = _row(kind="growth_demand_alert", body="NVDA, AVGO · pushed 08:15 ET · NEW AT")
    assert R.derive_tickers(r, KNOWN) == ["NVDA", "AVGO"], \
        "ET / AT / NEW are known symbols but never lead an item"


def test_multiline_digest_body_derives_one_name_per_line():
    body = ("NVDA $18.27 · in demand $17.9–18.6 · $1.2B\n"
            "AVGO $18.06 · ↓ falling into $17.9–18.6 · $3.0B\n"
            "+3 more on the board")
    assert R.derive_tickers(_row(body=body), KNOWN) == ["NVDA", "AVGO"], \
        "the '+3 more' tail names nobody"


def test_a_non_digest_kind_never_runs_the_regex_over_its_prose():
    r = _row(kind="minervini_flashcards", body="NEW: AT vs ET, the lesson…")
    assert R.derive_tickers(r, KNOWN) == []
    r2 = _row(kind="morning_brief", body="NVDA, AVGO are leading")
    assert R.derive_tickers(r2, KNOWN) == [], "prose is prose, whatever it spells"


def test_unknown_tokens_are_dropped_even_in_leading_position():
    assert R.derive_tickers(_row(body="XYZQ, WXYZ"), KNOWN) == []
    assert R.derive_tickers(_row(body="NEW, AT, XYZQ"), frozenset({"NVDA"})) == []


def test_lower_case_is_not_a_ticker():
    assert R.derive_tickers(_row(body="nvda, avgo"), KNOWN | {"nvda"}) == []


def test_class_share_suffix_matches_the_universe_spelling():
    assert R.derive_tickers(_row(body="BRK-B $412 · in demand"), KNOWN) == ["BRK-B"]
    for bad in ("BRK-", "BRKB", "brk-b"):
        assert R.derive_tickers(_row(body=f"{bad} $412"), KNOWN) == [], bad
    # the dot spelling is accepted by the token shape but must still be known
    assert R.derive_tickers(_row(body="BRK.B $412"), KNOWN) == []
    assert R.derive_tickers(_row(body="BRK.B $412"), KNOWN | {"BRK.B"}) == ["BRK.B"]


def test_no_body_and_no_ticker_yields_nothing():
    assert R.derive_tickers(_row(body=None), KNOWN) == []
    assert R.derive_tickers(_row(body=""), KNOWN) == []
    assert R.derive_tickers({"kind": "demand_alert"}, KNOWN) == []


# ---------------------------------------------------------------------------
# known_symbols: universe ∪ RENAMES keys ∪ RENAMES new symbols ∪ DELISTED
# ---------------------------------------------------------------------------
def test_known_symbols_covers_both_sides_of_a_real_rename_and_the_delisted():
    from sepa import symbols as SY
    assert SY.RENAMES["SATS"][0] == "ECHO", "the tuple's first element is the NEW symbol"
    known = R.known_symbols(loader=lambda: ["NVDA"],
                            renames=SY.RENAMES, delisted=SY.DELISTED)
    # a stub universe carrying NEITHER spelling — both still resolve
    assert "SATS" in known and "ECHO" in known
    assert "SMAR" in known, "a delisted name can still be in a 90-day-old body"
    r_old = _row(body="SATS $103 · in demand")
    r_new = _row(body="ECHO $101 · in demand")
    assert R.derive_tickers(r_old, known) == ["SATS"]
    assert R.derive_tickers(r_new, known) == ["ECHO"]


def test_known_symbols_is_cached_across_gathers(monkeypatch):
    from sepa import universe as UN
    calls = {"n": 0}

    def fake_load(mode=None):
        calls["n"] += 1
        return ["NVDA", "AVGO"]
    monkeypatch.setattr(UN, "load_universe", fake_load)
    monkeypatch.setattr(R, "_known_cache", {"at": 0.0, "set": None})
    rows = [{"_id": "1", "ts": 1, "kind": "demand_alert", "body": "NVDA, AVGO"}]
    for _ in range(2):
        R.gather("a@x", 10, list_recent=lambda e, l, **k: [dict(r) for r in rows],
                 get_db=lambda: None)
    assert calls["n"] == 1, "the universe is loaded once per KNOWN_TTL_SEC, not per row"
    assert R.KNOWN_TTL_SEC == 3600


def test_known_symbols_survives_a_broken_universe_loader(monkeypatch):
    def boom():
        raise RuntimeError("no mongo")
    known = R.known_symbols(loader=boom, renames={"SATS": ("ECHO", "d", "e")}, delisted={})
    assert known == frozenset({"SATS", "ECHO"}), "the rename tables still stand"


# ---------------------------------------------------------------------------
# 4. gather serves a list on every row
# ---------------------------------------------------------------------------
BK = {"_id": "b1", "ts": 500, "ticker": "AAPL", "kind": "volume_breakout",
      "reason": "vol 3.1x", "context": {}, "dismissed_at": None}


class _Cursor(list):
    def sort(self, *_a):
        return self

    def limit(self, *_a):
        return self


class _Db:
    def __init__(self, rows):
        self.rows = rows

    class _C:
        def __init__(self, rows):
            self.rows = rows

        def find(self, q):
            return _Cursor(self.rows)

    @property
    def sepa_breakouts(self):
        return _Db._C(self.rows)


def test_gather_serves_tickers_for_stored_single_derived_and_breakout(monkeypatch):
    monkeypatch.setattr(R, "known_symbols", lambda *a, **k: KNOWN)
    pushes = [
        {"_id": "p1", "ts": 400, "kind": "demand_alert", "body": "x",
         "tickers": ["nvda", "avgo"]},                       # stored
        {"_id": "p2", "ts": 300, "kind": "demand_alert", "body": "x", "ticker": "ntap"},
        {"_id": "p3", "ts": 200, "kind": "growth_demand_alert",
         "body": "NVDA, CRDO"},                              # old digest, derived
        # A prose kind (NOT a retired one — retired kinds are filtered out of
        # gather entirely since 2026-09-20, see test_notifications_recent).
        {"_id": "p4", "ts": 100, "kind": "health",
         "body": "NEW, AT, ET"},                             # prose, nothing
    ]
    rows = R.gather("a@x", 10, list_recent=lambda e, l, **k: [dict(p) for p in pushes],
                    get_db=lambda: _Db([dict(BK)]))
    by_id = {r["_id"]: r for r in rows}
    assert by_id["p1"]["tickers"] == ["NVDA", "AVGO"]
    assert by_id["p2"]["tickers"] == ["NTAP"]
    assert by_id["p3"]["tickers"] == ["NVDA", "CRDO"]
    assert by_id["p4"]["tickers"] == []
    assert by_id["b1"]["tickers"] == ["AAPL"], "a breakout row names its own symbol"
    assert all(isinstance(r["tickers"], list) for r in rows), "never None on a served row"


def test_a_breakout_without_a_ticker_serves_an_empty_list():
    out = R.normalize_breakout({"_id": "b0", "ts": 1, "kind": "volume_breakout"})
    assert out["tickers"] == [] and out["ticker"] == ""


def test_route_adds_tickers_and_nothing_else(monkeypatch):
    """The TestClient read is the pre-2026-09-05 shape plus exactly one key."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from auth import current_user_email
    from push import history as PH
    from sepa import breakouts as bk
    monkeypatch.setattr(R, "known_symbols", lambda *a, **k: KNOWN)
    push = {"_id": "p1", "ts": 400, "ts_iso": "2026-09-18T13:46:40+00:00",
            "title": "🚀 3 growth names at demand", "body": "NVDA, AVGO · pushed 08:15 ET",
            "kind": "growth_demand_alert", "ticker": None, "url": "/chart-maps?tab=growth",
            "user_email": None, "sent": 1, "failed": 0, "total": 1}
    monkeypatch.setattr(PH, "list_recent", lambda e, l, **k: [dict(push)])
    monkeypatch.setattr(bk, "_get_db", lambda: None)
    app = FastAPI()
    app.include_router(R.router)
    app.dependency_overrides[current_user_email] = lambda: "a@x"
    row = TestClient(app).get("/notifications/recent").json()["rows"][0]
    assert row["tickers"] == ["NVDA", "AVGO"]
    assert set(row) - set(push) == {"source", "enterable", "tickers"}, \
        "no other key appeared on the feed row"


# ---------------------------------------------------------------------------
# contract guards
# ---------------------------------------------------------------------------
def test_digest_kinds_is_the_seven_list_bodies():
    assert R.DIGEST_KINDS == frozenset({
        "growth_demand_alert", "demand_alert", "zone_bounce_alert",
        "hot_pullback_alert", "pattern_alert", "board_arrival", "earnings_reaction"})


def test_every_digest_builder_emits_the_key():
    """A new digest that forgets `tickers` would silently fall back to a body
    parse — the source guard catches it at the builder, not on the phone."""
    import inspect
    from growth import alerts as GA
    from supply_demand import demand_alerts as DA
    from supply_demand import zone_bounce_alerts as ZB
    from supply_demand import hot_pullback_alerts as HPA
    from patterns import pattern_alerts as PA
    for mod in (GA, DA, ZB, HPA, PA):
        src = inspect.getsource(mod.digest_message)
        assert '"tickers"' in src, mod.__name__
