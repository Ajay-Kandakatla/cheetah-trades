"""🧲 GEX on every Chart Maps tile — nightly + just-in-time read (2026-09-27).

Ajay: "Can you add gex exposure bullish or bearish signal to the stocks in our
chartmaps and make it sorted by bullish gex please.." — "Checkbox, ON by
default", "GEX vs the stock's size", "Only Chart Maps names nightly", "Also
just in time GEX read too.", "One tab open both".

Everything runs on synthetic rows: the ledger, the options chain, the price
frames, the clock and the Mongo collections are fakes. The negatives carry the
weight — a settled expiry, a read with no gamma, a refused chain, a stale row,
a raise, a closed market, a deadlock-prone instant compute — and the safety
greps pin that no alert, gate or trading path reads any of it.
"""
from __future__ import annotations

import asyncio
import re
import sys
import threading
import time
from concurrent.futures import Future
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps import board as B  # noqa: E402
from chart_maps import gex_read as GR  # noqa: E402
from chart_maps import gex_seen as GS  # noqa: E402
from options import gex_history as GH  # noqa: E402
import options.opex as OP  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")
REAL_BUCKET = GH.board_bucket


def _et(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=ET)


def _ts(*a):
    return _et(*a).timestamp()


NOW = _et(2026, 9, 28, 11, 0)          # Monday, regular session
TODAY = NOW.date()
SAT = _et(2026, 9, 26, 12, 0)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    GR._reset_for_tests()
    from market_hours import gate
    monkeypatch.delenv(gate.OVERRIDE_ENV, raising=False)
    yield
    GR._reset_for_tests()


def _row(sym="AAA", regime="pinning", spot=100.0, flip=95.0, net=2e6,
         date_et="2026-09-25", exp="2026-10-02", recorded_at=None,
         rel="single_name"):
    r = {"symbol": sym, "date_et": date_et, "spot": spot, "regime": regime,
         "flip_strike": flip, "net_gex_dollars": net, "put_wall": 90.0,
         "call_wall": 110.0, "expiration_date": exp, "reliability": rel}
    if recorded_at is not None:
        r["recorded_at"] = recorded_at
    return r


def _opex(regime="pinning", spot=100.0, flip=95.0, net=2e7, exp="2026-10-02"):
    return {"spot": spot, "expiration_date": exp, "gex_reliability": "single_name",
            "gamma": {"regime": regime, "net_gex_dollars": net, "flip_strike": flip,
                      "put_wall": 90.0, "call_wall": 110.0, "magnet_strike": None},
            "max_pain": {}, "vex": {}}


def _frame(n=60, close=10.0, vol=1_000_000, end="2026-09-25"):
    idx = pd.bdate_range(end=end, periods=n)
    return pd.DataFrame({"open": [close] * n, "high": [close] * n,
                         "low": [close] * n, "close": [close] * n,
                         "volume": [vol] * n}, index=idx)


class _SyncPool:
    """A pool whose futures are ALREADY DONE when submit returns — the case
    where add_done_callback runs the callback on the calling thread."""

    def submit(self, fn, *a):
        f = Future()
        try:
            f.set_result(fn(*a))
        except Exception as exc:                                # noqa: BLE001
            f.set_exception(exc)
        return f


class _WriteSpyColl:
    """A gex_history stand-in that records every write attempt."""

    def __init__(self, rows=None, with_index=True):
        self.rows = list(rows or [])
        self.writes = []
        self.index_calls = 0
        if with_index:
            self.create_index = self._create_index

    def _create_index(self, *a, **k):
        self.index_calls += 1

    def aggregate(self, pipeline):
        syms = set(pipeline[0]["$match"]["symbol"]["$in"])
        return [dict(r) for r in self.rows if r["symbol"] in syms]

    def update_one(self, *a, **k):
        self.writes.append(("update_one", a, k))

    def insert_one(self, *a, **k):
        self.writes.append(("insert_one", a, k))

    def insert_many(self, *a, **k):
        self.writes.append(("insert_many", a, k))

    def replace_one(self, *a, **k):
        self.writes.append(("replace_one", a, k))

    def bulk_write(self, *a, **k):
        self.writes.append(("bulk_write", a, k))


@pytest.fixture
def live_env(monkeypatch):
    """Ledger rows, frames, a controllable compute_opex and clock."""
    env = {"snaps": {}, "frames": {}, "calls": [], "behave": {},
           "clock": [NOW.timestamp()]}

    def _snap(symbols, max_age_days=GH.NIGHTLY_MAX_AGE_DAYS):
        return {s: env["snaps"][s] for s in symbols or [] if s in env["snaps"]}

    def _compute(sym):
        env["calls"].append(sym)
        b = env["behave"].get(sym, "ok")
        if callable(b):
            return b(sym)
        if b == "none":
            return None
        if b == "raise":
            raise RuntimeError("boom")
        return _opex()

    monkeypatch.setattr(GH, "snapshot_for", _snap)
    monkeypatch.setattr(B, "_burst_frames", lambda syms: env["frames"])
    monkeypatch.setattr(OP, "compute_opex", _compute)
    monkeypatch.setattr(GR, "_now", lambda: env["clock"][0])
    return env


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------
def test_adv_before_uses_50_closed_sessions_and_excludes_today_bar():
    f = _frame(61, close=10.0, vol=1_000_000, end="2026-09-28")
    f.iloc[:10, f.columns.get_loc("volume")] = 9_000_000   # outside the window
    f.iloc[-1, f.columns.get_loc("volume")] = 900_000_000  # today's bar
    assert GR.adv_before(f, date(2026, 9, 28)) == pytest.approx(10.0 * 1_000_000)


def test_adv_before_49_closed_sessions_is_none():
    f = _frame(50, end="2026-09-28")              # 49 closed + today
    assert GR.adv_before(f, date(2026, 9, 28)) is None
    assert GR.adv_before(_frame(50, end="2026-09-25"), date(2026, 9, 28)) is not None


def test_adv_before_zero_volume_or_no_frame_is_none():
    assert GR.adv_before(_frame(60, vol=0), date(2026, 9, 28)) is None
    assert GR.adv_before(None, date(2026, 9, 28)) is None


def test_strength_is_signed_and_none_on_bad_inputs():
    assert GR.strength(2e6, 1e8) == pytest.approx(0.02)
    assert GR.strength(-2e6, 1e8) == pytest.approx(-0.02)
    for net, adv in ((None, 1e8), (2e6, None), (2e6, 0), (2e6, -5.0),
                     (float("nan"), 1e8), (2e6, float("inf"))):
        assert GR.strength(net, adv) is None


def test_strength_text_two_decimals_under_one_percent():
    assert GR.strength_text(0.0019) == "0.19%"
    assert GR.strength_text(-0.0019) == "0.19%"
    assert GR.strength_text(0.0297) == "3.0%"
    assert GR.strength_text(None) is None


def test_chip_texts_are_exact():
    bull = GR.read_block(_row(net=1.9e5), "nightly", 1e8)
    c = GR.compose("AAA", bull, None, "not_asked")["chips"]
    assert [(x["kind"], x["text"], x["tone"]) for x in c] == [
        ("single", "🧲 GEX bullish · 0.19%", "good")]
    bear = GR.read_block(_row(regime="amplifying", flip=105.0, net=-2.97e6), "nightly", 1e8)
    c = GR.compose("AAA", bear, None, "not_asked")["chips"]
    assert [(x["text"], x["tone"]) for x in c] == [("🧲 GEX bearish · 3.0%", "warn")]
    mixed = GR.read_block(_row(flip=105.0), "nightly", 1e8)
    assert GR.compose("AAA", mixed, None, "not_asked")["chips"][0]["text"] == "🧲 GEX mixed"
    no_adv = GR.read_block(_row(), "nightly", None)
    assert GR.compose("AAA", no_adv, None, "not_asked")["chips"][0]["text"] == "🧲 GEX bullish"
    assert GR.compose("AAA", None, None, "not_asked")["chips"][0]["text"] == "🧲 no GEX read"
    assert GR.compose("AAA", None, None, "no_options")["chips"][0]["text"] == "🧲 no options read"


def test_titles_say_unmeasured_post_close_and_the_expiry_bias():
    blk = GR.compose("AAA", GR.read_block(_row(), "nightly", 1e8), None, "not_asked")
    title = blk["chips"][0]["title"]
    assert title.splitlines()[-1].startswith("UNMEASURED")
    assert "post-close" in title
    assert "nearest expiry" in title and "days out" in title
    for text in (title, GR.RULE_TEXT, GR.SCOPE_NOTE, GR.SORT_OFF["zero_dte"]["title"]):
        assert "bounce" not in text.lower()
    assert "UNMEASURED" in GR.RULE_TEXT


def test_bucket_is_gex_history_board_bucket_verbatim(monkeypatch):
    calls = []

    def spy(row):
        calls.append(row)
        return REAL_BUCKET(row)

    monkeypatch.setattr(GH, "board_bucket", spy)
    for regime in ("pinning", "amplifying"):
        for spot in (90.0, 100.0, 110.0):
            for flip in (None, 100.0):
                row = _row(regime=regime, spot=spot, flip=flip)
                n = len(calls)
                assert GR.read_block(row, "nightly", 1e8)["bucket"] == REAL_BUCKET(row)
                assert len(calls) == n + 1


# ---------------------------------------------------------------------------
# settled expiry chains
# ---------------------------------------------------------------------------
def test_settled_nightly_row_is_no_read():
    row = _row(date_et="2026-09-25", exp="2026-09-25",
               recorded_at=_ts(2026, 9, 25, 17, 50))
    r = GR.read_block(row, "nightly", 1e8)
    assert r["void"] == "settled" and r["bucket"] is None and r["strength"] is None
    blk = GR.compose("AAA", r, None, "not_asked")
    assert blk["sort"]["group"] == GR.NO_READ_GROUP
    assert blk["chips"][0]["text"] == "🧲 no GEX read"
    assert "settled" in blk["chips"][0]["title"]


def test_legacy_row_without_recorded_at_on_expiry_is_settled():
    r = GR.read_block(_row(date_et="2026-09-25", exp="2026-09-25"), "nightly", 1e8)
    assert r["void"] == "settled"


def test_live_read_after_close_on_expiry_is_settled():
    row = _row(date_et="2026-09-25", exp="2026-09-25",
               recorded_at=_ts(2026, 9, 25, 16, 30))
    assert GR.read_block(row, "live", 1e8)["void"] == "settled"


def test_live_read_in_rth_on_expiry_is_not_settled():
    row = _row(date_et="2026-09-25", exp="2026-09-25",
               recorded_at=_ts(2026, 9, 25, 11, 0))
    r = GR.read_block(row, "live", 1e8)
    assert r["void"] is None and r["bucket"] == "bullish" and GR.usable(r)


def test_row_after_its_expiry_is_settled():
    """A Monday row still listing Friday's expiry (or a weekend refresh) read
    a chain that is gone — no read, whatever the read time."""
    for rec in (None, _ts(2026, 9, 28, 11, 0)):
        row = _row(date_et="2026-09-28", exp="2026-09-25", recorded_at=rec)
        assert GR.read_block(row, "nightly", 1e8)["void"] == "settled"
        assert GR.read_block(row, "live", 1e8)["void"] == "settled"


def test_row_before_expiry_is_not_settled():
    row = _row(date_et="2026-09-24", exp="2026-09-25",
               recorded_at=_ts(2026, 9, 24, 17, 50))
    r = GR.read_block(row, "nightly", 1e8)
    assert r["void"] is None and r["days_to_expiry"] == 1


def test_settled_live_falls_back_to_usable_nightly():
    nightly = GR.read_block(_row(date_et="2026-09-24", exp="2026-10-02"), "nightly", 1e8)
    live = GR.read_block(_row(date_et="2026-09-25", exp="2026-09-25",
                              recorded_at=_ts(2026, 9, 25, 16, 30)), "live", 1e8)
    blk = GR.compose("AAA", nightly, live, "ok")
    assert len(blk["chips"]) == 1 and blk["chips"][0]["text"].startswith("🧲 GEX bullish")
    assert blk["sort"] == {"group": 0, "key": nightly["strength"], "source": "nightly"}
    assert "settled" in blk["chips"][0]["title"]


# The realistic weekly-options case (critic 2026-09-27, HIGH): a Thursday row
# on a Friday expiry is gone from Friday 16:00 on — on the board all weekend and
# as the live read's fallback on Friday after the close.
_THU_ROW = dict(date_et="2026-09-24", exp="2026-09-25",
                recorded_at=_ts(2026, 9, 24, 17, 50))
FRI_1630 = _et(2026, 9, 25, 16, 30)


def test_thursday_row_on_friday_expiry_is_no_read_on_saturday(monkeypatch):
    row = _row("THU", **_THU_ROW)
    assert GR.read_block(row, "nightly", 1e8, now_et=SAT)["void"] == "settled"
    monkeypatch.setattr(GH, "snapshot_for", lambda s, max_age_days=7: {"THU": row})
    out = GR.nightly_blocks(["THU"], frames={}, now=SAT)
    blk = out["THU"]
    assert blk["nightly"]["void"] == "settled" and blk["nightly"]["bucket"] is None
    assert blk["sort"] == {"group": GR.NO_READ_GROUP, "key": None, "source": None}
    assert blk["chips"][0]["text"] == "🧲 no GEX read"
    assert "settled" in blk["chips"][0]["title"]


def test_thursday_row_is_no_read_friday_after_close_even_when_live_settles(live_env):
    live_env["snaps"]["THU"] = _row("THU", **_THU_ROW)
    live_env["behave"]["THU"] = lambda s: _opex(exp="2026-09-25")
    out = GR.live_payload(["THU"], now=FRI_1630, budget_sec=5)
    r = out["rows"]["THU"]
    assert r["live_status"] == "ok" and r["live"]["void"] == "settled"
    assert r["nightly"]["void"] == "settled"
    assert r["sort"]["group"] == GR.NO_READ_GROUP and r["sort"]["source"] is None
    assert r["chips"][0]["text"] == "🧲 no GEX read"
    assert out["counts"]["none"] == 1 and out["counts"]["bullish"] == 0


def test_thursday_row_still_reads_before_friday_close(monkeypatch, live_env):
    """Positive twin: Thursday evening and Friday in market hours the Friday
    chain is still live — the Thursday read stands."""
    row = _row("THU", **_THU_ROW)
    for now in (_et(2026, 9, 24, 20, 0), _et(2026, 9, 25, 11, 0), _et(2026, 9, 25, 15, 59)):
        r = GR.read_block(row, "nightly", 1e8, now_et=now)
        assert r["void"] is None and r["bucket"] == "bullish", now
    monkeypatch.setattr(GH, "snapshot_for", lambda s, max_age_days=7: {"THU": row})
    assert GR.nightly_blocks(["THU"], frames={}, now=_et(2026, 9, 25, 11, 0))[
        "THU"]["sort"]["group"] == 0


def test_cached_live_read_on_expiry_day_voids_once_served_after_close(live_env):
    """A live row read 15:55 on its expiry day, served from cache at 16:05, is
    a settled chain by the time it is shown."""
    row = _row(date_et="2026-09-25", exp="2026-09-25",
               recorded_at=_ts(2026, 9, 25, 15, 55))
    assert GR.read_block(row, "live", 1e8)["void"] is None
    assert GR.read_block(row, "live", 1e8, now_et=_et(2026, 9, 25, 16, 5))["void"] == "settled"


# ---------------------------------------------------------------------------
# honest labels
# ---------------------------------------------------------------------------
def test_regime_none_is_no_read_never_mixed():
    nightly = GR.read_block(_row(), "nightly", 1e8)
    live = GR.read_block(_row(regime=None, date_et="2026-09-28",
                              recorded_at=NOW.timestamp()), "live", 1e8)
    assert live["void"] == "no_gamma" and live["bucket"] is None
    blk = GR.compose("AAA", nightly, live, "ok")
    assert [c["text"] for c in blk["chips"]] == ["🧲 GEX bullish · 2.0%"]
    assert blk["sort"]["group"] == 0 and blk["live"]["void"] == "no_gamma"
    alone = GR.compose("AAA", None, live, "ok")
    assert alone["sort"]["group"] == GR.NO_READ_GROUP
    assert "mixed" not in alone["chips"][0]["text"]


def test_mixed_is_never_called_bullish_or_bearish():
    for row in (_row(regime="pinning", spot=100.0, flip=105.0),
                _row(regime="amplifying", spot=100.0, flip=95.0)):
        blk = GR.compose("AAA", GR.read_block(row, "nightly", 1e8), None, "not_asked")
        text = blk["chips"][0]["text"]
        assert text == "🧲 GEX mixed"
        assert "bullish" not in text and "bearish" not in text
        assert blk["sort"] == {"group": 1, "key": None, "source": "nightly"}
        assert blk["chips"][0]["tone"] == "muted"


def test_no_read_sorts_last_and_is_not_bearish():
    none = GR.compose("AAA", None, None, "not_asked")
    bear = GR.compose("BBB", GR.read_block(_row(regime="amplifying", flip=105.0,
                                                net=-5e6), "nightly", 1e8),
                      None, "not_asked")
    assert none["sort"]["group"] > bear["sort"]["group"]
    assert none["chips"][0]["tone"] == "muted"
    assert "bearish" not in none["chips"][0]["text"]
    assert none["sort"]["key"] is None and none["sort"]["source"] is None


def test_stale_nightly_row_older_than_max_age_is_ignored(monkeypatch):
    stale = (TODAY - timedelta(days=GH.NIGHTLY_MAX_AGE_DAYS + 1)).isoformat()
    edge = (TODAY - timedelta(days=GH.NIGHTLY_MAX_AGE_DAYS)).isoformat()
    rows = {"OLD": _row("OLD", date_et=stale, exp="2026-12-18"),
            "EDGE": _row("EDGE", date_et=edge, exp="2026-12-18")}
    monkeypatch.setattr(GH, "snapshot_for", lambda s, max_age_days=7: rows)
    out = GR.nightly_blocks(["OLD", "EDGE"], frames={}, today=TODAY)
    assert out["OLD"]["nightly"] is None
    assert out["OLD"]["sort"]["group"] == GR.NO_READ_GROUP
    assert out["EDGE"]["nightly"]["bucket"] == "bullish"


def test_disagree_renders_close_then_now_and_sorts_on_live():
    nightly = GR.read_block(_row(), "nightly", 1e8)
    live = GR.read_block(_row(regime="amplifying", flip=105.0, net=-3e6,
                              date_et="2026-09-28", recorded_at=NOW.timestamp()),
                         "live", 1e8)
    blk = GR.compose("AAA", nightly, live, "ok")
    assert [c["kind"] for c in blk["chips"]] == ["close", "now"]
    assert blk["chips"][0]["text"].startswith("🧲 close: bullish")
    assert blk["chips"][1]["text"].startswith("🧲 now: bearish")
    assert blk["sort"]["group"] == 2 and blk["sort"]["source"] == "live"
    assert blk["sort"]["key"] == pytest.approx(-0.03)


def test_agree_renders_one_chip():
    nightly = GR.read_block(_row(), "nightly", 1e8)
    live = GR.read_block(_row(net=4e6, date_et="2026-09-28",
                              recorded_at=NOW.timestamp()), "live", 1e8)
    blk = GR.compose("AAA", nightly, live, "ok")
    assert len(blk["chips"]) == 1 and blk["chips"][0]["kind"] == "single"
    assert blk["sort"]["source"] == "live"
    assert blk["sort"]["key"] == pytest.approx(0.04)


def test_zero_dte_chips_muted_and_sort_off_served():
    nightly = GR.read_block(_row(), "nightly", 1e8)
    blk = GR.compose("AAA", nightly, None, "not_asked", tab="zero_dte")
    assert {c["tone"] for c in blk["chips"]} == {"muted"}
    assert GR.SORT_OFF["zero_dte"]["title"] in blk["chips"][0]["title"]
    out: dict = {}
    B.attach_gex([{"symbol": "AAA"}], out, tab="zero_dte", frames={})
    assert out["gex_sort_off"] == GR.SORT_OFF["zero_dte"]


def test_other_tabs_never_muted_and_sort_off_null():
    nightly = GR.read_block(_row(), "nightly", 1e8)
    for tab in B.TABS:
        if tab == "zero_dte":
            continue
        blk = GR.compose("AAA", nightly, None, "not_asked", tab=tab)
        assert blk["chips"][0]["tone"] == "good", tab
        out: dict = {}
        B.attach_gex([{"symbol": "AAA"}], out, tab=tab, frames={})
        assert out["gex_sort_off"] is None, tab


# ---------------------------------------------------------------------------
# the live read never writes the ledger
# ---------------------------------------------------------------------------
def test_live_read_never_writes_gex_history(monkeypatch):
    coll = _WriteSpyColl(rows=[_row("AAA")])
    monkeypatch.setattr(GH, "_coll", lambda: coll)
    monkeypatch.setattr(GH, "_INDEXED", False)
    monkeypatch.setattr(OP, "compute_opex", lambda s: _opex())
    monkeypatch.setattr(B, "_burst_frames", lambda syms: {})
    out = GR.live_payload(["AAA", "BBB"], now=NOW, budget_sec=5)
    assert out["rows"]["AAA"]["live_status"] == "ok"
    assert out["rows"]["AAA"]["nightly"]["bucket"] == "bullish"
    assert coll.writes == []


def test_gex_read_source_has_no_ledger_write():
    src = (BACKEND / "chart_maps" / "gex_read.py").read_text()
    banned = re.compile(r"update_one|insert_one|insert_many|replace_one|bulk_write"
                        r"|add_symbol|gex_history\.run|\.run\(")
    assert banned.search(src) is None
    # Internal identifiers keep `bounce` (bounce_room.normalize_symbols); no
    # served word may.
    assert "bounce" not in src.lower().replace("bounce_room", "")


# ---------------------------------------------------------------------------
# live machinery: lock, single flight, cache
# ---------------------------------------------------------------------------
def test_claim_never_deadlocks_on_instant_compute(monkeypatch, live_env):
    monkeypatch.setattr(GR, "_pool", lambda: _SyncPool())
    live_env["behave"]["NOPT"] = "none"
    for sym in ("NOPT", "FAST"):
        box = {}
        th = threading.Thread(target=lambda s=sym: box.setdefault(
            "r", GR._claim(s, "2026-09-28")), daemon=True)
        th.start()
        th.join(2)
        assert not th.is_alive(), f"_claim hung on {sym}"
        assert box["r"][0] == "wait" and box["r"][1].done()
        assert GR._claim(sym, "2026-09-28")[0] == "hit"
    assert GR._INFLIGHT == {}


def test_land_clears_only_its_own_inflight_entry():
    old, new = Future(), Future()
    old.set_result(("ok", {"date_et": "2026-09-28", "symbol": "AAA"}))
    GR._INFLIGHT["AAA"] = new
    GR._land("AAA", old, day="2026-09-28")
    assert GR._INFLIGHT["AAA"] is new
    new.set_result(("failed", None))
    GR._land("AAA", new, day="2026-09-28")
    assert "AAA" not in GR._INFLIGHT


def test_single_flight_one_compute_per_symbol(live_env):
    gate = threading.Event()

    def slow(sym):
        gate.wait(5)
        return _opex()

    live_env["behave"]["SLOW"] = slow
    k1, f1 = GR._claim("SLOW", "2026-09-28")
    k2, f2 = GR._claim("SLOW", "2026-09-28")
    assert k1 == k2 == "wait" and f1 is f2
    gate.set()
    f1.result(5)
    deadline = time.time() + 5
    while "SLOW" in GR._INFLIGHT and time.time() < deadline:
        time.sleep(0.01)
    assert live_env["calls"] == ["SLOW"]
    assert GR._claim("SLOW", "2026-09-28")[0] == "hit"


def test_ttl_cache_hit_then_expiry(monkeypatch, live_env):
    monkeypatch.setattr(GR, "_pool", lambda: _SyncPool())
    GR._claim("AAA", "2026-09-28")
    live_env["clock"][0] += 1
    assert GR._claim("AAA", "2026-09-28")[0] == "hit"
    assert live_env["calls"] == ["AAA"]
    live_env["clock"][0] += GR.LIVE_TTL_SEC() + 1
    assert GR._claim("AAA", "2026-09-28")[0] == "wait"
    assert live_env["calls"] == ["AAA", "AAA"]


def test_repoll_serves_cached_any_age_same_day_without_submitting(monkeypatch, live_env):
    monkeypatch.setattr(GR, "_pool", lambda: _SyncPool())
    GR._claim("AAA", "2026-09-28")
    live_env["clock"][0] += 10 * GR.LIVE_TTL_SEC()
    kind, entry = GR._claim("AAA", "2026-09-28", repoll=True)
    assert kind == "hit" and entry["status"] == "ok"
    assert live_env["calls"] == ["AAA"]


def test_repoll_never_serves_yesterdays_cache(monkeypatch, live_env):
    monkeypatch.setattr(GR, "_pool", lambda: _SyncPool())
    GR._claim("AAA", "2026-09-25")
    assert GR._claim("AAA", "2026-09-28", repoll=True)[0] == "wait"
    assert live_env["calls"] == ["AAA", "AAA"]


def test_failed_is_not_cached_and_repoll_resubmits_it(monkeypatch, live_env):
    monkeypatch.setattr(GR, "_pool", lambda: _SyncPool())
    live_env["behave"]["BAD"] = "raise"
    kind, fut = GR._claim("BAD", "2026-09-28")
    assert fut.result() == ("failed", None)
    assert "BAD" not in GR._CACHE and "BAD" not in GR._INFLIGHT
    assert GR._claim("BAD", "2026-09-28", repoll=True)[0] == "wait"
    assert live_env["calls"] == ["BAD", "BAD"]


# ---------------------------------------------------------------------------
# live_payload
# ---------------------------------------------------------------------------
def test_budget_returns_partial_pending_and_keeps_nightly_chip(live_env):
    gate = threading.Event()
    live_env["behave"]["SLOW"] = lambda s: (gate.wait(5), _opex())[1]
    live_env["snaps"]["SLOW"] = _row("SLOW")
    try:
        out = GR.live_payload(["FAST", "SLOW"], now=NOW, budget_sec=0.3)
        slow = out["rows"]["SLOW"]
        assert slow["live_status"] == "pending" and slow["live"] is None
        assert slow["chips"][0]["text"].startswith("🧲 GEX bullish")
        assert out["rows"]["FAST"]["live_status"] == "ok"
        assert out["pending"] == 1 and "still reading" in out["note"]
    finally:
        gate.set()


def test_no_options_read_wording_never_claims_no_listed_options(live_env):
    live_env["behave"].update({"NOOPT": "none", "NOOPT2": "none"})
    live_env["snaps"]["NOOPT2"] = _row("NOOPT2")
    out = GR.live_payload(["NOOPT", "NOOPT2"], now=NOW, budget_sec=5)
    a, b = out["rows"]["NOOPT"], out["rows"]["NOOPT2"]
    assert a["live_status"] == "no_options" and a["live"] is None
    assert a["chips"][0]["text"] == "🧲 no options read"
    assert "or the request was refused" in a["chips"][0]["title"]
    assert a["sort"]["group"] == GR.NO_READ_GROUP
    assert b["live_status"] == "no_options"
    assert b["chips"][0]["text"].startswith("🧲 GEX bullish")


def test_compute_raises_is_failed_and_nightly_survives(live_env):
    live_env["behave"]["BAD"] = "raise"
    live_env["snaps"]["BAD"] = _row("BAD")
    out = GR.live_payload(["BAD"], now=NOW, budget_sec=5)
    r = out["rows"]["BAD"]
    assert r["live_status"] == "failed" and r["live"] is None
    assert r["chips"][0]["text"].startswith("🧲 GEX bullish")
    assert r["sort"]["source"] == "nightly"


def test_market_closed_makes_no_massive_call(live_env):
    live_env["snaps"]["AAA"] = _row("AAA")
    out = GR.live_payload(["AAA"], now=SAT)
    assert live_env["calls"] == []
    assert out["market_closed"] == "weekend" and out["session"] == "closed"
    assert out["rows"]["AAA"]["live_status"] == "market_closed"
    assert out["rows"]["AAA"]["chips"][0]["text"].startswith("🧲 GEX bullish")
    assert "Market closed (weekend)" in out["note"]
    assert GR.live_payload(["AAA"], now=_et(2026, 9, 28, 21, 0))["market_closed"] == "overnight"
    assert GR.live_payload(["AAA"], now=_et(2026, 11, 26, 11, 0))["market_closed"] == \
        "holiday 2026-11-26"
    assert live_env["calls"] == []


def test_symbols_capped_at_LIMIT_MAX_and_truncated_counted(live_env):
    syms = [f"S{i:03d}" for i in range(B.LIMIT_MAX + 5)] + ["s000", ""]
    out = GR.live_payload(syms, now=SAT)
    assert len(out["rows"]) == B.LIMIT_MAX
    assert out["truncated"] == 5
    assert sum(out["counts"].values()) == B.LIMIT_MAX


def test_live_payload_unknown_tab_is_none_and_zero_dte_serves_sort_off(live_env):
    assert GR.live_payload(["AAA"], tab="nope", now=SAT)["sort_off"] is None
    assert GR.live_payload(["AAA"], tab="zero_dte", now=SAT)["sort_off"] == \
        GR.SORT_OFF["zero_dte"]


# ---------------------------------------------------------------------------
# API route
# ---------------------------------------------------------------------------
@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chart_maps.api import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


LIVE_KEYS = {"as_of", "as_of_text", "session", "market_closed", "rows", "pending",
             "counts", "legend", "scope", "sort_off", "ttl_sec", "budget_sec",
             "truncated", "rule", "note"}
ROW_KEYS = {"symbol", "live_status", "nightly", "live", "chips", "sort"}


def test_api_422_on_empty_symbols(client):
    assert client.post("/chart-maps/gex-live", json={"symbols": []}).status_code == 422
    assert client.post("/chart-maps/gex-live", json={"symbols": [" ", ""]}).status_code == 422


def test_api_unknown_tab_is_none_and_keys_exact(client, monkeypatch, live_env):
    seen = {}
    real = GR.live_payload

    def spy(symbols, *, tab=None, repoll=False, **k):
        seen.update(tab=tab, repoll=repoll, symbols=list(symbols))
        return real(symbols, tab=tab, repoll=repoll, now=SAT)

    monkeypatch.setattr(GR, "live_payload", spy)
    live_env["snaps"]["AAA"] = _row("AAA")
    r = client.post("/chart-maps/gex-live",
                    json={"symbols": ["aaa"], "tab": "nope", "repoll": True})
    assert r.status_code == 200
    body = r.json()
    assert seen["tab"] is None and seen["repoll"] is True
    assert set(body) == LIVE_KEYS
    assert set(body["rows"]["AAA"]) == ROW_KEYS
    assert body["legend"] == GR.LEGEND and body["scope"] == GR.SCOPE_NOTE
    assert body["sort_off"] is None
    r2 = client.post("/chart-maps/gex-live", json={"symbols": ["AAA"], "tab": "zero_dte"})
    assert r2.json()["sort_off"] == GR.SORT_OFF["zero_dte"]


# ---------------------------------------------------------------------------
# board attach
# ---------------------------------------------------------------------------
def _tiles(*syms):
    return [{"symbol": s, "badges": [], "bands": []} for s in syms]


@pytest.fixture
def quiet_board(monkeypatch):
    """board() with every builder and overlay stubbed: only attach_gex and
    the coverage record are real."""
    env = {"tiles": {}, "frames_calls": 0, "seen": [], "ledger": {}}

    def _builder(tab):
        return lambda *a, **k: {"tiles": [dict(t) for t in env["tiles"].get(tab, [])]}

    for tab, fn in (("vcp", "vcp_tiles"), ("winners", "winner_tiles"),
                    ("zero_dte", "zero_dte_tiles"), ("earnings", "earnings_tiles"),
                    ("ict", "ict_tiles"), ("zones", "zone_tiles"),
                    ("deep_demand", "deep_demand_tiles")):
        monkeypatch.setattr(B, fn, _builder(tab))

    def _frames(syms):
        env["frames_calls"] += 1
        return {}

    monkeypatch.setattr(B, "_burst_frames", _frames)
    for name in ("attach_explosive", "attach_live_now", "attach_enterable",
                 "attach_band_structure", "attach_burst", "attach_key_levels"):
        monkeypatch.setattr(B, name, lambda *a, **k: None)
    monkeypatch.setattr(B, "_live_snapshot", lambda tiles: {})
    monkeypatch.setattr(B, "band_structure_coverage", lambda *a, **k: {})
    monkeypatch.setattr(GH, "snapshot_for", lambda s, max_age_days=7: {
        x: env["ledger"][x] for x in s or [] if x in env["ledger"]})
    monkeypatch.setattr(GS, "record", lambda tab, syms, **k: env["seen"].append(
        (tab, list(syms))) or len(syms))
    return env


def _recent(sym, **kw):
    kw.setdefault("date_et", (date.today() - timedelta(days=1)).isoformat())
    kw.setdefault("exp", "2099-01-01")
    return _row(sym, **kw)


def test_attach_gex_on_every_tab_tile(quiet_board):
    for tab in ("vcp", "winners", "zero_dte", "earnings"):
        quiet_board["tiles"][tab] = _tiles("AAA", "BBB", "CCC")
    quiet_board["ledger"]["AAA"] = _recent("AAA")
    for tab in ("vcp", "winners", "zero_dte", "earnings"):
        out = B.board(tab, limit=5)
        assert [t["symbol"] for t in out["tiles"]] == ["AAA", "BBB", "CCC"], tab
        for t in out["tiles"]:
            assert t["gex"]["symbol"] == t["symbol"]
            assert t["gex"]["live_status"] == "not_asked"
            assert 1 <= len(t["gex"]["chips"]) <= 2
        assert out["tiles"][0]["gex"]["nightly"]["bucket"] == "bullish"
        assert out["gex_counts"] == {"bullish": 1, "mixed": 0, "bearish": 0, "none": 2}
        assert "1 of 3 names have a nightly read" in out["gex_note"]
    assert [t for t, _ in quiet_board["seen"]] == ["vcp", "winners", "zero_dte", "earnings"]


def test_board_serves_legend_scope_rule(quiet_board):
    quiet_board["tiles"]["vcp"] = _tiles("AAA")
    out = B.board("vcp", limit=5)
    assert out["gex_rule"] == GR.RULE_TEXT
    assert out["gex_legend"] == GR.LEGEND
    assert out["gex_scope"] == GR.SCOPE_NOTE
    assert out["gex_sort_off"] is None
    assert out["gex_as_of"] is None


def test_attach_gex_never_reorders_or_drops(monkeypatch):
    rows = {"B1": _recent("B1", regime="amplifying", flip=120.0, net=-9e6),
            "A1": _recent("A1", net=9e9)}
    monkeypatch.setattr(GH, "snapshot_for", lambda s, max_age_days=7: rows)
    tiles = _tiles("B1", "ZZ", "A1", "MM")
    ids = [id(t) for t in tiles]
    B.attach_gex(tiles, {}, tab="vcp", frames={})
    assert [t["symbol"] for t in tiles] == ["B1", "ZZ", "A1", "MM"]
    assert [id(t) for t in tiles] == ids
    assert all("gex" in t for t in tiles)


def test_attach_gex_failure_leaves_board_intact(quiet_board, monkeypatch):
    quiet_board["tiles"]["vcp"] = _tiles("AAA", "BBB")

    def boom(*a, **k):
        raise RuntimeError("ledger down")

    monkeypatch.setattr(GR, "nightly_blocks", boom)
    out = B.board("vcp", limit=5)
    assert [t["symbol"] for t in out["tiles"]] == ["AAA", "BBB"]
    assert all(t["gex"]["chips"][0]["text"] == "🧲 no GEX read" for t in out["tiles"])
    monkeypatch.setattr(B, "attach_gex", boom)
    out = B.board("vcp", limit=5)
    assert [t["symbol"] for t in out["tiles"]] == ["AAA", "BBB"]
    assert "gex_rule" not in out


def test_ict_fetches_its_own_frames(quiet_board, monkeypatch):
    seen = []
    real = GR.nightly_blocks

    def spy(symbols, frames=None, today=None, tab=None):
        seen.append(frames)
        return real(symbols, frames=frames, today=today, tab=tab)

    monkeypatch.setattr(GR, "nightly_blocks", spy)
    quiet_board["tiles"]["ict"] = _tiles("AAA")
    quiet_board["tiles"]["vcp"] = _tiles("AAA")
    B.board("ict", limit=5)
    assert seen[-1] is None and quiet_board["frames_calls"] == 1
    B.board("vcp", limit=5)
    assert seen[-1] == {} and quiet_board["frames_calls"] == 2


def test_record_failure_never_breaks_board(quiet_board, monkeypatch):
    quiet_board["tiles"]["vcp"] = _tiles("AAA")

    def boom(*a, **k):
        raise RuntimeError("mongo down")

    monkeypatch.setattr(GS, "record", boom)
    out = B.board("vcp", limit=5)
    assert [t["symbol"] for t in out["tiles"]] == ["AAA"]

    class _Bad:
        def update_one(self, *a, **k):
            raise RuntimeError("write refused")

    monkeypatch.undo()
    assert GS.record("vcp", ["AAA"], now=NOW, coll=_Bad()) == 0


def test_session_board_symbols_identical_with_gex(quiet_board, monkeypatch):
    from supply_demand import session_board as SB
    band = [{"kind": "demand", "lo": 90.0, "hi": 95.0}]
    quiet_board["tiles"]["zones"] = [dict(t, bands=band) for t in _tiles("ZZZ", "AAA")]
    quiet_board["tiles"]["deep_demand"] = [dict(t, bands=band) for t in _tiles("DDD")]
    quiet_board["ledger"]["AAA"] = _recent("AAA")
    with_gex = SB.board_symbols()
    monkeypatch.setattr(B, "attach_gex", lambda *a, **k: None)
    without = SB.board_symbols()
    assert with_gex == without
    assert [r["symbol"] for r in with_gex] == ["AAA", "DDD", "ZZZ"]


# ---------------------------------------------------------------------------
# coverage: chart_maps_seen
# ---------------------------------------------------------------------------
def _agg(expr, doc, var=None):
    """A tiny evaluator for the aggregation operators gex_seen's update
    pipeline uses — generic operator semantics, not gex_seen's intent (the
    same pipeline was checked on Mongo 7 with a read-only $documents run)."""
    if isinstance(expr, str):
        if expr.startswith("$$"):
            return var
        return doc.get(expr[1:]) if expr.startswith("$") else expr
    if isinstance(expr, list):
        return [_agg(e, doc, var) for e in expr]
    if isinstance(expr, dict) and len(expr) == 1:
        (op, arg), = expr.items()
        if op == "$literal":
            return arg
        if op == "$ifNull":
            v = _agg(arg[0], doc, var)
            return v if v is not None else _agg(arg[1], doc, var)
        if op == "$concatArrays":
            return [x for a in arg for x in _agg(a, doc, var)]
        if op == "$in":
            return _agg(arg[0], doc, var) in _agg(arg[1], doc, var)
        if op == "$not":
            return not _agg(arg[0], doc, var)
        if op == "$filter":
            return [x for x in _agg(arg["input"], doc, var) if _agg(arg["cond"], doc, x)]
    raise AssertionError(f"unsupported expression {expr!r}")


class _SeenColl:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.updates = []

    def update_one(self, q, update, upsert=False):
        self.updates.append((q, update, upsert))
        assert isinstance(update, list), "record must use an update pipeline"
        doc = next((d for d in self.docs if d.get("_id") == q["_id"]), None)
        if doc is None:
            assert upsert
            doc = {"_id": q["_id"]}
            self.docs.append(doc)
        for stage in update:
            (op, fields), = stage.items()
            assert op == "$set"
            new = {k: _agg(v, doc) for k, v in fields.items()}
            doc.update(new)

    def find(self, q):
        floor = q["date_et"]["$gte"]
        return [dict(d) for d in self.docs if d["date_et"] >= floor]


def test_record_moves_served_names_to_the_end_per_day_tab():
    c = _SeenColl()
    assert GS.record("zones", ["aaa", "AAA", " bbb ", None], now=NOW, coll=c) == 2
    q, upd, upsert = c.updates[0]
    assert q == {"_id": "2026-09-28:zones"} and upsert is True
    doc = c.docs[0]
    assert doc["symbols"] == ["AAA", "BBB"]
    assert doc["date_et"] == "2026-09-28" and doc["tab"] == "zones"
    assert GS.record("zones", ["ccc", "aaa"], now=NOW, coll=c) == 2
    assert c.docs[0]["symbols"] == ["BBB", "CCC", "AAA"]          # no duplicate
    assert GS.record("zones", [], now=NOW, coll=c) == 0
    assert GS.record("", ["AAA"], now=NOW, coll=c) == 0
    assert len(c.updates) == 2 and len(c.docs) == 1


def test_names_on_screen_at_the_close_survive_the_cap():
    """Critic 2026-09-27 demo: 80 names seen at 08:00, 20 new ones at 15:55 —
    the 17:50 sweep must cover all 20 (it covered 0 of them when the doc kept
    first-seen order)."""
    c = _SeenColl()
    early = [f"E{i:02d}" for i in range(B.LIMIT_MAX)]
    late = [f"L{i:02d}" for i in range(20)]
    GS.record("zones", early, now=_et(2026, 9, 28, 8, 0), coll=c)
    GS.record("zones", late, now=_et(2026, 9, 28, 15, 55), coll=c)
    out = GS.recent_symbols(now=_et(2026, 9, 28, 17, 50), coll=c)
    assert len(out) == B.LIMIT_MAX
    assert out[:20] == late[::-1]
    assert all(s in out for s in late)
    assert out[20:] == early[::-1][:B.LIMIT_MAX - 20]
    # NEGATIVE: an early name re-seen at the close moves back inside the cap.
    GS.record("zones", ["E00"], now=_et(2026, 9, 28, 15, 58), coll=c)
    out2 = GS.recent_symbols(now=_et(2026, 9, 28, 17, 50), coll=c)
    assert out2[0] == "E00" and len(out2) == B.LIMIT_MAX and "E01" not in out2


def test_recent_symbols_lookback_newest_first():
    c = _SeenColl([
        {"date_et": "2026-09-25", "tab": "zones", "symbols": ["B", "A"]},
        {"date_et": "2026-09-28", "tab": "zones", "symbols": ["C", "A"]},
        {"date_et": "2026-09-10", "tab": "zones", "symbols": ["OLD"]},
        {"date_et": "2026-09-27", "tab": "vcp", "symbols": ["V", "C"]},
    ])
    # stored lists are last-seen order, oldest first → read back to front
    assert GS.recent_symbols(now=NOW, coll=c) == ["C", "V", "A", "B"]
    assert GS.recent_symbols(days=0, now=NOW, coll=c) == ["A", "C"]


def test_recent_symbols_caps_per_tab_zones_not_cut():
    docs = []
    for ti, tab in enumerate(B.TABS):
        names = [f"T{ti}N{i}" for i in range(100)]
        docs.append({"date_et": "2026-09-28", "tab": tab, "symbols": names[:50]})
        docs.append({"date_et": "2026-09-27", "tab": tab, "symbols": names[50:]})
    out = GS.recent_symbols(now=NOW, coll=_SeenColl(docs))
    assert len(out) == B.LIMIT_MAX * len(B.TABS)
    for ti, tab in enumerate(B.TABS):
        mine = [s for s in out if s.startswith(f"T{ti}N")]
        # newest day first, each day most recently seen first
        want = ([f"T{ti}N{i}" for i in range(49, -1, -1)]
                + [f"T{ti}N{i}" for i in range(99, 49, -1)])[:B.LIMIT_MAX]
        assert mine == want, tab
    zi = B.TABS.index("zones")
    assert f"T{zi}N0" in out and f"T{zi}N50" not in out


def test_recent_symbols_failure_is_empty():
    class _Bad:
        def find(self, q):
            raise RuntimeError("down")

    assert GS.recent_symbols(now=NOW, coll=_Bad()) == []


# ---------------------------------------------------------------------------
# nightly sweep: universe + tags + index
# ---------------------------------------------------------------------------
@pytest.fixture
def core_sources(monkeypatch):
    import options.scanner as SC
    import options.soir as SO
    import sepa.scanner as SS
    from watchlist import store as WL
    box = {"core": ["AAA", "BBB"], "recent": [], "recent_calls": 0}
    monkeypatch.setattr(SC, "_always_include_symbols", lambda: list(box["core"]))
    monkeypatch.setattr(WL, "list_entries", lambda: [])
    monkeypatch.setattr(SO, "load_latest", lambda *a, **k: [])
    monkeypatch.setattr(SS, "load_latest", lambda: {})

    def _recent_syms(*a, **k):
        box["recent_calls"] += 1
        return list(box["recent"])

    monkeypatch.setattr(GS, "recent_symbols", _recent_syms)
    return box


def test_snapshot_universe_default_is_unchanged(core_sources):
    core_sources["recent"] = ["ZZZ", "AAA"]
    assert GH.snapshot_universe() == ["AAA", "BBB"]
    assert core_sources["recent_calls"] == 0
    assert GH.snapshot_universe(include_chart_maps=True) == ["AAA", "BBB", "ZZZ"]


def test_universe_split_core_capped_extra_deduped(core_sources):
    names = [f"N{i:03d}" for i in range(GH.MAX_UNIVERSE + 50)]
    core_sources["core"] = names
    core_sources["recent"] = [names[0], "NEW1", "new1", "NEW2",
                              names[GH.MAX_UNIVERSE - 1], names[GH.MAX_UNIVERSE + 10]]
    core, extra = GH.universe_split()
    assert core == names[:GH.MAX_UNIVERSE]
    assert extra == ["NEW1", "NEW2", names[GH.MAX_UNIVERSE + 10]]
    calls = core_sources["recent_calls"]
    assert GH.universe_split(include_chart_maps=False)[1] == []
    assert core_sources["recent_calls"] == calls


def test_run_tags_core_vs_chart_maps(core_sources, monkeypatch):
    core_sources["recent"] = ["BBB", "CCC", "NOCHAIN"]
    coll = _WriteSpyColl()
    monkeypatch.setattr(GH, "_coll", lambda: coll)
    monkeypatch.setattr(GH, "_et_date", lambda: "2026-09-28")
    monkeypatch.setattr(OP, "compute_opex",
                        lambda s: None if s == "NOCHAIN" else _opex())
    res = GH.run()
    tags = {a[0]["_id"]: a[1]["$set"]["universe"] for _, a, _k in coll.writes}
    assert tags == {"AAA:2026-09-28": "core", "BBB:2026-09-28": "core",
                    "CCC:2026-09-28": "chart_maps"}
    assert res["core"] == 2 and res["chart_maps"] == 2
    assert res["recorded"] == 3 and res["skipped"] == 1 and res["universe"] == 4
    assert coll.index_calls == 1                     # test_run_ensures_index


def test_run_ensures_index(core_sources, monkeypatch):
    coll = _WriteSpyColl()
    monkeypatch.setattr(GH, "_coll", lambda: coll)
    monkeypatch.setattr(OP, "compute_opex", lambda s: None)
    GH.run(include_chart_maps=False)
    assert coll.index_calls == 1


def test_no_chain_symbol_writes_no_row(core_sources, monkeypatch):
    core_sources["recent"] = ["CCC"]
    coll = _WriteSpyColl()
    monkeypatch.setattr(GH, "_coll", lambda: coll)
    monkeypatch.setattr(OP, "compute_opex", lambda s: None)
    res = GH.run()
    assert coll.writes == [] and res["recorded"] == 0 and res["skipped"] == 3


def test_refresh_endpoint_sweeps_core_only(monkeypatch):
    from options import api as OA
    seen = {}
    monkeypatch.setattr(GH, "run", lambda **k: seen.update(k) or {"ok": True})
    assert asyncio.run(OA.refresh_gex_board()) == {"ok": True}
    assert seen == {"include_chart_maps": False}


def test_snapshot_for_ensures_index_once_per_process(monkeypatch):
    coll = _WriteSpyColl(rows=[_row("AAA", date_et=date.today().isoformat())])
    monkeypatch.setattr(GH, "_coll", lambda: coll)
    monkeypatch.setattr(GH, "_INDEXED", False)
    assert set(GH.snapshot_for(["AAA"])) == {"AAA"}
    GH.snapshot_for(["AAA"])
    assert coll.index_calls == 1
    assert GH.INDEX == [("symbol", 1), ("date_et", -1)]


def test_fake_coll_without_create_index_still_reads(monkeypatch):
    coll = _WriteSpyColl(rows=[_row("AAA")], with_index=False)
    monkeypatch.setattr(GH, "_coll", lambda: coll)
    monkeypatch.setattr(GH, "_INDEXED", False)
    assert set(GH.snapshot_for(["AAA"])) == {"AAA"}
    assert GH._INDEXED is False
    assert GH.ensure_index(None) is False


# ---------------------------------------------------------------------------
# safety: nothing that pushes, gates or trades reads any of this
# ---------------------------------------------------------------------------
def _sources(*globs):
    out = []
    for g in globs:
        out.extend(sorted(BACKEND.glob(g)))
    return out


def test_alert_and_trading_paths_never_read_chart_maps_gex():
    new_ids = re.compile(r"gex_read|gex_seen|attach_gex|gex_live|gex-live|chart_maps_seen")
    files = _sources("supply_demand/alert_gates.py", "supply_demand/demand_alerts.py",
                     "supply_demand/zone_edge.py", "patterns/pattern_alerts.py",
                     "push/*.py", "trading/*.py")
    assert files, "safety grep found no files"
    for f in files:
        assert new_ids.search(f.read_text()) is None, f
    ledger = re.compile(r"gex_history|board_bucket")
    for f in _sources("supply_demand/alert_gates.py", "supply_demand/zone_edge.py",
                      "trading/*.py"):
        assert ledger.search(f.read_text()) is None, f
    ctx = (BACKEND / "supply_demand" / "bullish_context.py").read_text()
    assert "chart_maps" not in ctx
