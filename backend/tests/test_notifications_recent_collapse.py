"""The repeat collapse on GET /notifications/recent (2026-09-21).

Ajay, asked "Collapse the 2,022 old rows on the Alerts page?": "Yes to all..".
His screenshot showed the same ARM line twice and the same ON line twice inside
one 15:00 ET block. Nothing is deleted or hidden — adjacent identical rows fold
into the newest one, which carries a served `repeat` block.

Pure: `gather` / `gather_payload` with an injected `list_recent` and `get_db`,
plus one TestClient pass for the query param. No Mongo, no network.

Every ET string the tests compare against is COMPUTED here from the same two
engines the module uses (zoneinfo for the clock, `sepa.price_alerts._et_day_label`
for the day) — never retyped, so a formatter change fails loudly instead of
silently agreeing with a stale literal.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from push import recent as R  # noqa: E402

ET = ZoneInfo("America/New_York")


def _clock(ts: int) -> str:
    return datetime.fromtimestamp(ts, ET).strftime("%H:%M")


def _day(ts: int) -> str:
    from sepa.price_alerts import _et_day_label
    return _et_day_label(ts)


def push(ts, *, kind="price_alert", ticker="ARM", title="🔔 ARM -7.0% vs $150",
         body="Note: −7% preset", _id=None, **kw):
    """A push_history row as `list_recent` hands it over (no `source`, no
    `tickers` — `gather` tags both before the collapse)."""
    row = {"_id": _id or f"x{ts}", "ts": ts, "ts_iso": None, "title": title,
           "body": body, "kind": kind, "ticker": ticker, "url": "/sepa/ARM",
           "user_email": "a@x", "sent": 1, "failed": 0, "total": 1}
    row.update(kw)
    return row


def collect(rows, limit=25, *, collapse=True, get_db=None, **kw):
    calls = []

    def fake(email, n, **kwargs):
        calls.append((email, n, kwargs))
        return [dict(r) for r in rows]
    out = R.gather_payload("a@x", limit, list_recent=fake,
                           get_db=get_db or (lambda: None), collapse=collapse, **kw)
    return out, calls


# ── the fold itself ──────────────────────────────────────────────────────────
def test_three_adjacent_identical_rows_fold_into_the_newest(monkeypatch):
    # 2026-09-21 15:00 ET-ish stamps on one ET day
    base = int(datetime(2026, 9, 21, 15, 0, tzinfo=ET).timestamp())
    rows = [push(base + 120, _id="new", body="newest", sent=3),
            push(base + 60, _id="mid"),
            push(base, _id="old")]
    body, _ = collect(rows)
    assert body["count"] == 1
    row = body["rows"][0]
    # the survivor is the NEWEST row, whole
    assert row["_id"] == "new" and row["body"] == "newest" and row["sent"] == 3
    assert row["ts"] == base + 120 and row["tickers"] == ["ARM"] and row["enterable"] is None
    assert row["repeat"] == {
        "count": 3,
        "first_ts": base,
        "first_ts_iso": datetime.fromtimestamp(base, tz=timezone.utc).isoformat(),
        "last_ts": base + 120,
        "truncated": False,
        "line": f"2 more like this · first {_clock(base)} ET, last {_clock(base + 120)} ET",
    }


def test_the_correctness_pin_an_interleaved_name_splits_the_run():
    """[ARM, ON, ARM] is THREE events, not two — the fold is adjacency, never
    a whole-window group-by. This is the pin that says so."""
    rows = [push(300, ticker="ARM", title="🔔 ARM"),
            push(200, ticker="ON", title="🔔 ON"),
            push(100, ticker="ARM", title="🔔 ARM")]
    body, _ = collect(rows)
    assert [r["ticker"] for r in body["rows"]] == ["ARM", "ON", "ARM"]
    assert all("repeat" not in r for r in body["rows"])

    rows = [push(500, ticker="ARM", title="🔔 ARM"), push(400, ticker="ARM", title="🔔 ARM"),
            push(300, ticker="ON", title="🔔 ON"), push(200, ticker="ON", title="🔔 ON"),
            push(100, ticker="ARM", title="🔔 ARM")]
    body, _ = collect(rows)
    assert [(r["ticker"], (r.get("repeat") or {}).get("count", 1)) for r in body["rows"]] == \
        [("ARM", 2), ("ON", 2), ("ARM", 1)]


def test_same_title_different_body_folds_the_measured_screenshot_case():
    """The identity excludes the BODY on purpose: two of his presets (−7% and
    −12%) firing on ONE print differ only in their Note. With the body in the
    key the screenshot's duplicate would not fold at all."""
    rows = [push(200, body="Note: −12% preset", _id="newer"),
            push(100, body="Note: −7% preset", _id="older")]
    body, _ = collect(rows)
    assert body["count"] == 1
    assert body["rows"][0]["_id"] == "newer" and body["rows"][0]["body"] == "Note: −12% preset"
    assert body["rows"][0]["repeat"]["count"] == 2


def test_C5_count_only_digests_with_different_names_do_not_fold():
    """"🚀 3 growth names at demand" carries a COUNT and no name. Without
    `tickers` in the identity two such rows would swallow each other."""
    title = "🚀 3 growth names at demand"
    rows = [push(200, kind="growth_demand_alert", ticker=None, title=title,
                 body="", tickers=["A", "B", "C"], _id="abc"),
            push(100, kind="growth_demand_alert", ticker=None, title=title,
                 body="", tickers=["D", "E", "F"], _id="def")]
    body, _ = collect(rows)
    assert body["count"] == 2 and all("repeat" not in r for r in body["rows"])

    same = [push(200, kind="growth_demand_alert", ticker=None, title=title,
                 body="", tickers=["A", "B", "C"], _id="abc"),
            push(100, kind="growth_demand_alert", ticker=None, title=title,
                 body="", tickers=["A", "B", "C"], _id="abc2")]
    body, _ = collect(same)
    assert body["count"] == 1 and body["rows"][0]["repeat"]["count"] == 2


def test_missing_or_None_tickers_participate_as_empty_without_raising():
    rows = [push(200, kind="market_hours_reminder", ticker=None,
                 title="🔔 Market closes in 15 min", body="", tickers=None),
            push(100, kind="market_hours_reminder", ticker=None,
                 title="🔔 Market closes in 15 min", body="")]
    body, _ = collect(rows)
    assert body["count"] == 1 and body["rows"][0]["repeat"]["count"] == 2
    assert R.repeat_key({}) == ("push", None, None, None, ())
    assert R.repeat_key({"tickers": "NVDA"})[4] == (), "a string is not a list"
    assert R.repeat_key({"tickers": ["A", 7, None]})[4] == ("A",)


def test_ticker_normalises_blank_to_None_and_lower_to_upper():
    assert R.repeat_key({"ticker": "  "})[2] is None
    assert R.repeat_key({"ticker": "arm"})[2] == "ARM"
    assert R.repeat_key({"ticker": None})[2] is None


def test_a_group_of_one_is_the_same_object_and_collapse_never_mutates():
    a = {"ts": 2, "kind": "k", "title": "t", "source": "push"}
    b = {"ts": 1, "kind": "k2", "title": "t2", "source": "push"}
    before = [dict(a), dict(b)]
    out = R.collapse_repeats([a, b])
    assert out[0] is a and out[1] is b
    assert "repeat" not in a and "repeat" not in b
    assert [a, b] == before, "the input rows are untouched"

    c = {"ts": 2, "kind": "k", "title": "t", "source": "push"}
    d = {"ts": 1, "kind": "k", "title": "t", "source": "push"}
    out = R.collapse_repeats([c, d])
    assert out[0] is not c and "repeat" not in c and "repeat" not in d


def test_a_push_and_a_breakout_with_the_same_kind_ticker_title_do_not_fold():
    rows = [{"ts": 2, "kind": "volume_breakout", "ticker": "AAPL",
             "title": "🚀 Volume breakout · AAPL", "source": "push", "tickers": ["AAPL"]},
            {"ts": 1, "kind": "volume_breakout", "ticker": "AAPL",
             "title": "🚀 Volume breakout · AAPL", "source": "breakout", "tickers": ["AAPL"]}]
    out = R.collapse_repeats(rows)
    assert len(out) == 2 and all("repeat" not in r for r in out)


# ── order of operations: filter, then merge, then collapse ───────────────────
def test_the_retired_filter_runs_before_the_collapse():
    """A retired row between two identical price alerts is removed FIRST, so
    they become adjacent and fold."""
    rows = [push(300, _id="a"), push(200, kind="vb_workout", ticker=None,
                                     title="🏐 Sun", body=""), push(100, _id="b")]
    body, _ = collect(rows)
    assert body["count"] == 1 and body["rows"][0]["repeat"]["count"] == 2


def test_NEGATIVE_a_live_row_between_two_identical_rows_still_splits_them():
    rows = [push(300, _id="a"),
            push(200, kind="demand_alert", ticker="NVDA", title="🧲 NVDA", body=""),
            push(100, _id="b")]
    body, _ = collect(rows)
    assert body["count"] == 3 and all("repeat" not in r for r in body["rows"])


def test_NEGATIVE_the_collapse_never_hides_a_kind(monkeypatch):
    """With the retired registry empty every row is served, folded or not —
    the collapse is presentation, never a filter."""
    monkeypatch.setattr(R, "_retired_kinds", lambda: frozenset())
    rows = [push(300, kind="vb_workout", ticker=None, title="🏐 Sun", body=""),
            push(200, kind="vb_workout", ticker=None, title="🏐 Sun", body=""),
            push(100, kind="minervini_flashcards", ticker=None, title="📐 card", body="")]
    body, _ = collect(rows)
    assert [r["kind"] for r in body["rows"]] == ["vb_workout", "minervini_flashcards"]
    assert body["rows"][0]["repeat"]["count"] == 2


# ── the cap counts collapsed rows ────────────────────────────────────────────
def test_limit_counts_collapsed_rows_and_the_raw_fetch_over_reads():
    rows = []
    for i in range(5):
        for _ in range(2):
            rows.append(push(1000 - i * 10 - len(rows), ticker=f"T{i}", title=f"🔔 T{i}"))
    body, calls = collect(rows, limit=3)
    assert calls[-1][1] == 3 * R.COLLAPSE_OVERFETCH == 6
    assert body["count"] == 3
    assert [r["repeat"]["count"] for r in body["rows"]] == [2, 2, 2]


def test_the_over_fetch_is_bounded_by_MAX_LIMIT():
    _, calls = collect([push(1)], limit=R.MAX_LIMIT)
    assert calls[-1][1] == R.MAX_LIMIT == 500
    _, calls = collect([push(1)], limit=300)
    assert calls[-1][1] == R.MAX_LIMIT


def test_collapse_false_is_the_flat_list():
    rows = [push(300), push(200), push(100)]
    body, calls = collect(rows, limit=25, collapse=False)
    assert calls[-1][1] == 25, "no over-fetch"
    assert body["count"] == 3 and body["collapse"] is False
    assert body["raw_truncated"] is False
    assert all("repeat" not in r for r in body["rows"])


def test_gather_still_returns_a_list():
    out = R.gather("a@x", 10, list_recent=lambda *a, **k: [push(1)], get_db=lambda: None)
    assert isinstance(out, list) and len(out) == 1


def test_since_kinds_and_ticker_still_pass_through_unchanged():
    _, calls = collect([push(1)], limit=10, kinds="price_alert, demand_alert",
                       since=1_757_000_000, ticker="arm")
    assert calls[-1] == ("a@x", 20, {"kinds": ["price_alert", "demand_alert"],
                                     "since_ts": 1_757_000_000, "ticker": "ARM"})


# ── [C2] raw_truncated is measured on the RAW push fetch ─────────────────────
def test_C2_raw_truncated_is_true_even_when_the_served_list_is_short(monkeypatch):
    """limit=500 → raw 500; every row retired-filtered away except a folded
    handful → count far below the cap, but the page must still warn."""
    rows = ([push(2000 - i, kind="vb_workout", ticker=None, title="🏐", body="")
             for i in range(490)]
            + [push(1000 - i, ticker="ARM", title="🔔 ARM") for i in range(10)])
    assert len(rows) == 500
    body, calls = collect(rows, limit=500)
    assert calls[-1][1] == 500
    assert body["count"] == 1 and body["rows"][0]["repeat"]["count"] == 10
    assert body["raw_truncated"] is True


def test_C2_a_shorter_raw_fetch_is_not_truncated():
    body, calls = collect([push(300), push(200)], limit=25)
    assert calls[-1][1] == 50 and body["raw_truncated"] is False


def test_C2_the_singleton_tail_carries_no_block_but_raw_truncated_is_true():
    """The last push row is alone at the cut: no `+` anywhere, and the
    top-level flag is what tells the page the window was cut."""
    rows = [push(600, ticker="ARM", title="🔔 ARM"), push(500, ticker="ARM", title="🔔 ARM"),
            push(400, ticker="ON", title="🔔 ON"), push(300, ticker="ON", title="🔔 ON"),
            push(200, ticker="GFS", title="🔔 GFS"), push(100, ticker="NVDA", title="🔔 NVDA")]
    body, calls = collect(rows, limit=3)
    assert calls[-1][1] == 6 and len(rows) == 6
    assert body["raw_truncated"] is True
    assert [r["ticker"] for r in body["rows"]] == ["ARM", "ON", "GFS"]
    assert body["rows"][2].get("repeat") is None, "a singleton tail carries no block"
    # the GFS singleton is the LAST push group: it closes the ON run and the ARM
    # run above it, so no row of either can exist past the cut — no '+' anywhere.
    assert body["rows"][0]["repeat"]["truncated"] is False
    assert body["rows"][1]["repeat"]["truncated"] is False


# ── [C4] the '+' lands on the last PUSH group only ───────────────────────────
class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, *a):
        return self

    def limit(self, n):
        return self

    def __iter__(self):
        return iter(self.rows)


class _Db:
    def __init__(self, rows):
        self.sepa_breakouts = type("C", (), {"find": lambda _s, q: _Cursor(rows)})()


def test_C4_a_breakout_group_older_than_every_push_never_carries_the_plus():
    """`all` mode + `since`: a breakout run can sit older than every push in
    the merged list. The cut is on the PUSH fetch, so the '+' never lands
    there — and only ONE group can ever carry it."""
    pushes = ([push(600, ticker="ARM", title="🔔 ARM"), push(500, ticker="ARM", title="🔔 ARM")]
              + [push(400 - i * 10, ticker="ON", title="🔔 ON") for i in range(4)])
    bks = [{"_id": "b1", "ts": 200, "ticker": "AAPL", "kind": "volume_breakout",
            "reason": "vol 3.1x", "context": {}},
           {"_id": "b2", "ts": 100, "ticker": "AAPL", "kind": "volume_breakout",
            "reason": "vol 3.1x", "context": {}}]
    body, calls = collect(pushes, limit=3, get_db=lambda: _Db(bks))
    assert calls[-1][1] == 6 and len(pushes) == 6 and body["raw_truncated"] is True
    rows = body["rows"]
    assert [r["source"] for r in rows] == ["push", "push", "breakout"]
    assert [r["repeat"]["count"] for r in rows] == [2, 4, 2]
    marked = [r["ticker"] for r in rows if r["repeat"]["truncated"]]
    assert marked == ["ON"], "the LAST push group, never a breakout, never two"
    assert rows[1]["repeat"]["line"].startswith("3+ more like this")
    assert rows[2]["repeat"]["truncated"] is False


def test_C4_NEGATIVE_a_singleton_push_tail_closes_every_run_above_it():
    """The marker is the LAST push run, stamped only when that run has >= 2
    members. A singleton tail ends the run above it, so no member of any run
    can exist past the cut — the '+' would be a false promise on his page."""
    rows = [{"source": "push", "ts": 300, "kind": "price_alert", "ticker": "ARM",
             "title": "🔔 ARM", "tickers": ["ARM"]},
            {"source": "push", "ts": 200, "kind": "price_alert", "ticker": "ARM",
             "title": "🔔 ARM", "tickers": ["ARM"]},
            {"source": "push", "ts": 100, "kind": "price_alert", "ticker": "ON",
             "title": "🔔 ON", "tickers": ["ON"]}]
    out = R.collapse_repeats(rows, tail_truncated=True)
    assert [r["ticker"] for r in out] == ["ARM", "ON"]
    assert out[0]["repeat"]["truncated"] is False
    assert "+" not in out[0]["repeat"]["line"]
    assert out[1].get("repeat") is None
    # positive control: make the tail a run of two and it owns the marker
    rows2 = rows + [{"source": "push", "ts": 50, "kind": "price_alert", "ticker": "ON",
                     "title": "🔔 ON", "tickers": ["ON"]}]
    out2 = R.collapse_repeats(rows2, tail_truncated=True)
    assert out2[0]["repeat"]["truncated"] is False
    assert out2[1]["repeat"]["truncated"] is True


def test_C4_a_shorter_fetch_puts_no_plus_anywhere():
    rows = [push(600, ticker="ARM", title="🔔 ARM"), push(500, ticker="ARM", title="🔔 ARM")]
    body, _ = collect(rows, limit=25)
    assert body["raw_truncated"] is False
    assert body["rows"][0]["repeat"]["truncated"] is False
    assert "+" not in body["rows"][0]["repeat"]["line"]


# ── the sentence ─────────────────────────────────────────────────────────────
def test_repeat_line_same_et_day_uses_the_clock():
    a = int(datetime(2026, 9, 21, 9, 31, tzinfo=ET).timestamp())
    b = int(datetime(2026, 9, 21, 15, 0, tzinfo=ET).timestamp())
    assert R.repeat_line(2, a, b) == f"1 more like this · first {_clock(a)} ET, last {_clock(b)} ET"
    assert R.repeat_line(2, a, b).startswith("1 more like this · first 09:31 ET")


def test_repeat_line_across_days_uses_the_price_alert_day_words():
    a = int(datetime(2026, 6, 5, 12, 0, tzinfo=ET).timestamp())
    b = int(datetime(2026, 9, 21, 12, 0, tzinfo=ET).timestamp())
    assert R.repeat_line(13, a, b) == f"12 more like this · first {_day(a)} ET, last {_day(b)} ET"
    assert _day(a) == "Jun 5" and _day(b) == "Sep 21"


def test_repeat_line_truncated_and_missing_stamps():
    a = int(datetime(2026, 8, 31, 12, 0, tzinfo=ET).timestamp())
    b = int(datetime(2026, 9, 21, 12, 0, tzinfo=ET).timestamp())
    assert R.repeat_line(41, a, b, truncated=True) == \
        f"40+ more like this · first {_day(a)} ET, last {_day(b)} ET"
    assert R.repeat_line(2, 0, 0) == "1 more like this"
    assert R.repeat_line(2, None, 5) == "1 more like this"
    assert R.repeat_line(2, "x", "y") == "1 more like this"


def test_NEGATIVE_a_broken_day_engine_falls_back_to_a_date_not_a_blank(monkeypatch):
    """`sepa.price_alerts` drags notify/prices/massive_keys in. If that import
    dies the line must still read — never a blank feed, never a second
    "Mon D" formatter."""
    monkeypatch.setattr(R, "_et_day", lambda ts: datetime.fromtimestamp(ts, ET).strftime("%Y-%m-%d"))
    a = int(datetime(2026, 6, 5, 12, 0, tzinfo=ET).timestamp())
    b = int(datetime(2026, 9, 21, 12, 0, tzinfo=ET).timestamp())
    assert R.repeat_line(3, a, b) == "2 more like this · first 2026-06-05 ET, last 2026-09-21 ET"
    # and the real fallback path, with the import itself broken
    import builtins
    real = builtins.__import__

    def boom(name, *a, **k):
        if name == "sepa.price_alerts":
            raise ImportError("no massive key")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", boom)
    assert R._et_day(a) == "2026-06-05"


def test_repeat_block_count_includes_the_survivor():
    g = [{"ts": 300}, {"ts": 200}, {"ts": 100}]
    blk = R.repeat_block(g)
    assert blk["count"] == 3 and blk["first_ts"] == 100 and blk["last_ts"] == 300
    assert blk["line"].startswith("2 more like this")
    assert R.repeat_block([{"ts": 0}, {"ts": 0}])["first_ts_iso"] is None


# ── the route ────────────────────────────────────────────────────────────────
def _client(monkeypatch, pushes):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from auth import current_user_email
    from push import history as H
    from sepa import breakouts as bk
    monkeypatch.setattr(H, "list_recent", lambda e, n, **kw: [dict(p) for p in pushes])
    monkeypatch.setattr(bk, "_get_db", lambda: None)
    app = FastAPI()
    app.include_router(R.router)
    app.dependency_overrides[current_user_email] = lambda: "a@x"
    return TestClient(app)


@pytest.mark.parametrize("flag", ["false", "0"])
def test_route_collapse_false_and_zero_are_flat(monkeypatch, flag):
    c = _client(monkeypatch, [push(300), push(200), push(100)])
    body = c.get("/notifications/recent", params={"collapse": flag}).json()
    assert body["collapse"] is False and body["count"] == 3
    assert body["raw_truncated"] is False
    assert all("repeat" not in r for r in body["rows"])


def test_route_default_collapses_and_serves_both_flags(monkeypatch):
    c = _client(monkeypatch, [push(300), push(200), push(100)])
    body = c.get("/notifications/recent").json()
    assert set(["rows", "count", "collapse", "raw_truncated"]) <= set(body)
    assert body["collapse"] is True and body["count"] == 1
    assert body["rows"][0]["repeat"]["count"] == 3


def test_NEGATIVE_route_rejects_a_non_boolean_collapse(monkeypatch):
    c = _client(monkeypatch, [push(1)])
    assert c.get("/notifications/recent", params={"collapse": "maybe"}).status_code == 422


# ── the shipped probe is the source of the doc's table ───────────────────────
_PROBE = Path(__file__).resolve().parents[1] / "scripts" / "alerts_feed_fold_probe.py"
_DOC = (Path(__file__).resolve().parents[2]
        / "docs" / "notifications" / "alerts_feed_collapse.md")


def test_the_probe_imports_the_identity_and_never_retypes_it():
    src = _PROBE.read_text()
    assert "from push.recent import derive_tickers, known_symbols, repeat_key" in src
    for name in ("repeat_key", "derive_tickers", "known_symbols"):
        assert f"def {name}" not in src, f"{name} is re-typed in the probe"
        assert hasattr(R, name)


def test_NEGATIVE_the_probe_never_writes_to_mongo():
    """A measurement that can mutate `push_history` is not a measurement."""
    src = _PROBE.read_text()
    for verb in ("insert_one", "insert_many", "update_one", "update_many",
                 "replace_one", "delete_one", "delete_many", "bulk_write",
                 "find_one_and_", "drop("):
        assert verb not in src, f"the probe must stay read-only ({verb})"


def test_the_doc_quotes_the_probe_run_not_a_retyped_table():
    doc = _DOC.read_text()
    assert "python -m scripts.alerts_feed_fold_probe" in doc
    assert "alerts_feed_fold_probe.py` run inside the api container" in doc
    assert "## Measured — HIS read, 2026-09-21 17:08 ET" in doc
    # NEGATIVE: the superseded spec-time read must not survive in the table.
    assert "16:47 ET" not in doc and "13,590" not in doc
