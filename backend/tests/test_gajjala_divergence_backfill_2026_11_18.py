"""🧨 Divergence backfill script (spec diverg2 §3.9, WP-D, 2026-11-18) — BUILT, running it = HIS CALL #6.

The script only orchestrates WP-A's engine (`divergence.units_today / from_tile / detect / trade / live_state`) over the
stored 5-min reads. Pinned here: a stored read doc gives the SAME listing and trade as `from_frame` on the equivalent
Frame (equality pin); and the honesty guards — a short prior, a missing reads doc, an unreadable tile, a ledger fault,
an unreadable record, an open session each REFUSE the session and write nothing; nothing is written without --write;
an existing record is never touched; no bar loader / provider is ever called. Hermetic: FakeColl stores only.
"""
from __future__ import annotations

import copy
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import divergence as DV
from chart_maps.gajjala import store as ST
from scripts import gajjala_divergence_backfill as BF
from tests.test_gajjala_store import FakeColl, fake_store

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
S = date(2026, 11, 18)
PREV = date(2026, 11, 17)
SYM = "DVGX"
NOW = datetime(2026, 11, 18, 20, 30, tzinfo=ET)                  # after the extended close + BAR_SETTLE_SEC
RING = datetime(2026, 11, 18, 9, 0, tzinfo=ET).astimezone(UTC)  # a 🧠 ring before the open
SCRIPT = Path(BF.__file__)


def _sess(t) -> str:
    if t < datetime.strptime("09:30", "%H:%M").time():
        return "premarket"
    return "rth" if t < datetime.strptime("16:00", "%H:%M").time() else "afterhours"


def _minutes(day: date, start: str, bars5: list) -> pd.DataFrame:
    """Each 5-minute (o, h, l, c, v) as five 1-minute bars that aggregate back to it exactly (naive-UTC index =
    the minute START, as daytrading.data hands them); prices on a 2-decimal grid so the tile's 4-dp rounding is exact."""
    t0 = datetime.combine(day, datetime.strptime(start, "%H:%M").time(), tzinfo=ET)
    idx, rows = [], []
    for k, (o, h, l, c, v) in enumerate(bars5):
        path = [(o, o, o, o), (o, o, l, l), (l, h, l, h), (h, h, c, c), (c, c, c, c)]
        for m, (mo, mh, ml, mc) in enumerate(path):
            ts = t0 + timedelta(minutes=5 * k + m)
            idx.append(pd.Timestamp(ts.astimezone(UTC).replace(tzinfo=None)))
            rows.append({"open": mo, "high": mh, "low": ml, "close": mc, "volume": v / 5,
                         "session": _sess(ts.time())})
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))


def _flat(n: int, px: float, vol: float) -> list:
    out = []
    for k in range(n):
        c = round(px + (0.01 if k % 2 else 0.0), 2)
        out.append((round(px, 2), round(px + 0.02, 2), round(px - 0.01, 2), c, vol))
    return out


def _today_5m() -> list:
    """04:00 → 20:00: flat pre-market (low volume), a steady climb from 09:30 with rising volume (the 9 EMA pulls
    away from the 21 → one R1 crossing with V2 True), a sharp fall from 11:30 (a 9/21 down-cross → the X3 exit), flat
    to the close and after hours."""
    out = _flat(66, 2.00, 1000.0)                               # 04:00 … 09:25 buckets
    px = 2.00
    for k in range(24):                                         # 09:30 … 11:25 — climb, volume rising
        o = round(px, 2)
        px = round(px + 0.03, 2)
        out.append((o, round(px + 0.01, 2), round(o - 0.01, 2), px, 2000.0 + 500.0 * k))
    for k in range(12):                                         # 11:30 … 12:25 — fall
        o = round(px, 2)
        px = round(px - 0.06, 2)
        out.append((o, round(o + 0.01, 2), round(px - 0.01, 2), px, 3000.0))
    n_left = (20 * 60 - (12 * 60 + 30)) // 5                    # 12:30 … 19:55 buckets
    return out + _flat(n_left, px, 1500.0)


PRIOR_1M = _minutes(PREV, "15:00", _flat(60, 2.00, 1200.0))    # the prior tail from 15:00 = what the tile keeps
TODAY_1M = _minutes(S, "04:00", _today_5m())


def _frames():
    fr = B.build_frames(SYM, S, NOW, PRIOR_1M, TODAY_1M)
    assert fr is not None and fr.f5 is not None
    return fr


def _read_doc(fr) -> dict:
    """The read doc's tile exactly as run.py builds it (the 5-min half)."""
    p = B.tile_payload(fr, "5m")
    q = B.tile_prior_payload(fr, "5m", from_et=GC.RS_TILE_PRIOR_FROM_ET)
    return {"_id": ST.key(S, SYM), "date": S.isoformat(), "symbol": SYM,
            "tile": {"bars5": p["bars"], "curves5": p["curves"], "vol_avg5": p["vol_avg"],
                     "bars5_prior": q["bars"], "curves5_prior": q["curves"], "vol_avg5_prior": q["vol_avg"]}}


def _unit(clock=RING) -> dict:
    return {"clock": clock, "kind": "potential", "setup": "bull_flag", "at_et": "09:00", "line": None}


@pytest.fixture
def frames():
    return _frames()


@pytest.fixture
def world(monkeypatch, frames):
    """A GG5 FakeColl store holding the read doc of the one unit; units_today answers that unit."""
    st = fake_store()
    doc = _read_doc(frames)
    st.coll(ST.READS).docs[doc["_id"]] = copy.deepcopy(doc)
    units = {SYM: _unit()}
    monkeypatch.setattr(DV, "units_today", lambda store, session: dict(units))
    return st, units, doc


def _no_providers(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a provider / bar loader was called by the backfill")
    import daytrading.data as DD
    monkeypatch.setattr(DD, "load_intraday", boom)
    monkeypatch.setattr(B, "frames_for", boom)


# ── the equality pin ────────────────────────────────────────────────────────────────────────────────────────────
def test_tile_series_lists_the_same_bar_and_trade_as_the_frame(frames):
    doc = _read_doc(frames)
    bt, bf = DV.from_tile(doc, S.isoformat()), DV.from_frame(frames.f5, S.isoformat())
    assert bt is not None and bf is not None
    dt, df = DV.detect(bt, RING, S), DV.detect(bf, RING, S)
    assert df is not None, "the synthetic series must list once (else the pin proves nothing)"
    assert dt == df
    assert df["window"] == "rth" and "09:35" <= df["bar_t"][11:] <= "15:55"
    hm, _ = DV.horizon_of(S, df["window"])
    tt, tf = DV.trade(bt, dt["i"], dt["window"], hm), DV.trade(bf, df["i"], df["window"], hm)
    assert tt == tf
    assert tf["exit"]["reason"] == "downcross"


def test_plan_row_carries_the_engine_listing_and_trade(world, frames, monkeypatch):
    _no_providers(monkeypatch)
    st, _units, _doc = world
    plan = BF.plan_session(st, S, NOW)
    assert plan["status"] == "ok" and plan["units"] == 1
    (row,) = plan["rows"]
    bf = DV.from_frame(frames.f5, S.isoformat())
    det = DV.detect(bf, RING, S)
    hm, _ = DV.horizon_of(S, det["window"])
    assert row["status"] == "new" and row["id"] == DV.record_id(S.isoformat(), SYM)
    assert row["window"] == det["window"]
    assert row["alert"] == {k: v for k, v in det.items() if k != "window"}
    assert row["trade"] == DV.trade(bf, det["i"], det["window"], hm)
    text = BF.render(plan)
    assert SYM in text and det["bar_t"][11:16] in text and "sealed until " + GC.DIVERGENCE_OOS_SEAL_ET in text


# ── writes: only with --write, only new ids, never an existing doc ─────────────────────────────────────────────
def test_dry_run_never_writes(world, monkeypatch, capsys):
    _no_providers(monkeypatch)
    st, _u, _d = world
    code = BF.main(["--sessions", S.isoformat()], store=st, now=NOW)
    assert code == BF.EXIT_OK
    c = st.coll(ST.DIVERGENCE)
    assert c.writes == 0 and c.docs == {}
    assert "nothing written" in capsys.readouterr().out


def test_write_records_the_new_listing_once_with_source_backfill(world, monkeypatch):
    _no_providers(monkeypatch)
    st, _u, _d = world
    assert BF.main(["--sessions", S.isoformat(), "--write"], store=st, now=NOW) == BF.EXIT_OK
    docs = st.coll(ST.DIVERGENCE).docs
    rid = DV.record_id(S.isoformat(), SYM)
    assert list(docs) == [rid]
    d = docs[rid]
    assert d["source"] == BF.SOURCE == "backfill" and d["date"] == S.isoformat() and d["symbol"] == SYM
    assert d["window"] == "rth" and d["alert"]["bar_t"] and d["half_day"] is False
    assert set(d) - {"_id"} <= ST.DIVERGENCE_KEYS
    assert "grade" not in d                                     # the nightly grades it, never the backfill
    # a second --write run: the record exists → untouched, nothing written
    before = copy.deepcopy(d)
    writes = st.coll(ST.DIVERGENCE).writes
    assert BF.main(["--sessions", S.isoformat(), "--write"], store=st, now=NOW + timedelta(hours=1)) == BF.EXIT_OK
    assert st.coll(ST.DIVERGENCE).writes == writes and docs[rid] == before


def test_never_overwrites_a_record_already_on_file(world, monkeypatch):
    _no_providers(monkeypatch)
    st, _u, _d = world
    rid = DV.record_id(S.isoformat(), SYM)
    planted = {"_id": rid, "date": S.isoformat(), "symbol": SYM, "window": "ah", "source": "pass",
               "alert": {"bar_t": "2026-11-18 16:35"}, "grade": {"net_pct": 1.0, "version": 1}}
    st.coll(ST.DIVERGENCE).docs[rid] = copy.deepcopy(planted)
    plan = BF.plan_session(st, S, NOW)
    assert [r["status"] for r in plan["rows"]] == ["exists"]
    res = BF.write_session(st, plan, NOW)
    assert res == {"written": 0, "skipped": 1, "failed": 0}
    assert st.coll(ST.DIVERGENCE).writes == 0 and st.coll(ST.DIVERGENCE).docs[rid] == planted


def test_a_unit_that_never_lists_writes_nothing(world, monkeypatch):
    st, units, _d = world
    units[SYM] = _unit(clock=datetime(2026, 11, 18, 19, 56, tzinfo=ET).astimezone(UTC))   # rang after the last window bar
    plan = BF.plan_session(st, S, NOW)
    assert plan["status"] == "ok" and [r["status"] for r in plan["rows"]] == ["no_listing"]
    assert BF.write_session(st, plan, NOW)["written"] == 0 and st.coll(ST.DIVERGENCE).docs == {}
    assert "no listing" in BF.render(plan)


# ── honesty guards: each REFUSES the session and writes nothing ────────────────────────────────────────────────
def _refused(st, reason, capsys=None, argv_extra=("--write",)):
    plan = BF.plan_session(st, S, NOW)
    assert plan["status"] == "refused" and plan["reason"] == reason and plan["rows"] == []
    assert BF.write_session(st, plan, NOW) == {"written": 0, "skipped": 0, "failed": 0}
    assert BF.main(["--sessions", S.isoformat(), *argv_extra], store=st, now=NOW) == BF.EXIT_REFUSED
    assert st.coll(ST.DIVERGENCE).docs == {} and st.coll(ST.DIVERGENCE).writes == 0
    return plan


def test_refuses_a_short_prior(world):
    st, _u, doc = world
    need = GC.DIVERGENCE_ATR_PERIOD + 1
    short = copy.deepcopy(doc)
    short["tile"]["bars5_prior"] = short["tile"]["bars5_prior"][-(need - 1):]
    for cv in short["tile"]["curves5_prior"]:
        cv["values"] = cv["values"][-(need - 1):]
    st.coll(ST.READS).docs[doc["_id"]] = short
    plan = _refused(st, "prior_short")
    assert plan["gaps"]["prior_short"] == [{"symbol": SYM, "prior_bars": need - 1, "need": need}]


def test_a_prior_of_exactly_atr_period_plus_one_is_not_refused_for_length(world):
    st, _u, doc = world
    need = GC.DIVERGENCE_ATR_PERIOD + 1
    edge = copy.deepcopy(doc)
    edge["tile"]["bars5_prior"] = edge["tile"]["bars5_prior"][-need:]
    for cv in edge["tile"]["curves5_prior"]:
        cv["values"] = cv["values"][-need:]
    st.coll(ST.READS).docs[doc["_id"]] = edge
    plan = BF.plan_session(st, S, NOW)
    assert plan["reason"] != "prior_short"


def test_refuses_a_session_with_any_missing_reads_doc_and_prints_the_gap(world, capsys):
    st, units, _d = world
    units["GONE"] = _unit()
    plan = _refused(st, "reads_missing")
    assert plan["gaps"]["reads_missing"] == ["GONE"]
    out = capsys.readouterr().out
    assert "reads_missing" in out and "GONE" in out and "nothing written" in out


def test_refuses_an_unreadable_tile(world):
    st, _u, doc = world
    bad = copy.deepcopy(doc)
    bad["tile"]["bars5"] = "not a list"
    st.coll(ST.READS).docs[doc["_id"]] = bad
    plan = _refused(st, "tile_unreadable")
    assert plan["gaps"]["tile_unreadable"] == [SYM]


def test_refuses_a_tile_without_a_prior_block(world):
    st, _u, doc = world
    bad = copy.deepcopy(doc)
    del bad["tile"]["bars5_prior"]
    st.coll(ST.READS).docs[doc["_id"]] = bad
    _refused(st, "tile_unreadable")


def test_refuses_on_a_ledger_read_fault(world, monkeypatch):
    st, _u, _d = world
    from chart_maps.gajjala import ledger as LG

    def raises(store, session):
        raise LG.LedgerReadError("down")
    monkeypatch.setattr(DV, "units_today", raises)
    plan = _refused(st, "ledger_unreadable")
    assert plan["gaps"] == {"error": "LedgerReadError"}


def test_refuses_when_the_record_cannot_be_read(world):
    _st, _u, doc = world
    st = fake_store(**{ST.DIVERGENCE: FakeColl(fail=True)})
    st.coll(ST.READS).docs[doc["_id"]] = copy.deepcopy(doc)
    plan = BF.plan_session(st, S, NOW)
    assert plan["status"] == "refused" and plan["reason"] == "record_unreadable" and plan["rows"] == []
    assert BF.main(["--sessions", S.isoformat(), "--write"], store=st, now=NOW) == BF.EXIT_REFUSED


def test_refuses_a_session_whose_extended_close_has_not_settled(world):
    st, _u, _d = world
    early = datetime(2026, 11, 18, 19, 59, tzinfo=ET)
    plan = BF.plan_session(st, S, early)
    assert plan["status"] == "refused" and plan["reason"] == "session_open"
    assert BF.main(["--sessions", S.isoformat(), "--write"], store=st, now=early) == BF.EXIT_REFUSED
    assert st.coll(ST.DIVERGENCE).docs == {}


def test_one_refused_session_does_not_block_the_other(world, monkeypatch):
    st, _u, _d = world
    code = BF.main(["--sessions", f"{S.isoformat()},2026-11-19", "--write"], store=st, now=NOW)
    assert code == BF.EXIT_REFUSED                              # 11-19 has not closed at NOW
    assert list(st.coll(ST.DIVERGENCE).docs) == [DV.record_id(S.isoformat(), SYM)]


def test_bad_sessions_argument_is_refused(world):
    st, _u, _d = world
    assert BF.main(["--sessions", "2026-13-01"], store=st, now=NOW) == BF.EXIT_REFUSED
    assert BF.main(["--sessions", " , "], store=st, now=NOW) == BF.EXIT_REFUSED
    assert BF.parse_sessions("2026-11-17,2026-11-18,2026-11-17") == [date(2026, 11, 17), S]


# ── no provider, no aggregate ───────────────────────────────────────────────────────────────────────────────────
def test_no_provider_or_bar_loader_in_the_script_source():
    src = SCRIPT.read_text()
    code = "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())
    body = code.split('"""', 2)[2]                              # past the module docstring
    for banned in ("load_intraday", "frames_for", "build_frames", "_dry_load_day", "grade_step", "massive", "requests",
                   "urllib", "httpx", "yfinance", "finnhub", "alpaca", "subprocess", "alerts.compose"):
        assert banned not in body.lower(), banned
    imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", body, flags=re.M)
    for mod in imports:
        assert not mod.startswith(("trading", "push", "chart_maps.gajjala.push", "notifications")), mod
    assert all(m in ("__future__", "argparse", "json", "sys", "datetime", "typing", "zoneinfo", "chart_maps.gajjala",
                     "chart_maps.gajjala.ema_cross", "daytrading.data") for m in imports), imports


def test_a_full_write_run_calls_no_provider(world, monkeypatch):
    _no_providers(monkeypatch)
    st, _u, _d = world
    assert BF.main(["--sessions", S.isoformat(), "--write", "--json"], store=st, now=NOW) == BF.EXIT_OK


def test_output_never_prints_an_aggregate_over_the_rows(world, capsys):
    st, _u, _d = world
    BF.main(["--sessions", S.isoformat()], store=st, now=NOW)
    out = capsys.readouterr().out.lower()
    for word in ("mean", "average", "win rate", "% won", "total net", "expectancy"):
        assert word not in out, word
    assert re.search(r"1 listing\(s\) of 1 unit\(s\)", out)


# ── refix 2026-11-18: the write-failed exit and the JSON dry run ────────────────────────────────────────────────
def test_a_failed_write_exits_one_and_counts_failed(world, monkeypatch, capsys):
    _no_providers(monkeypatch)
    st, _u, _d = world
    calls = []
    monkeypatch.setattr(st, "upsert_divergence", lambda _id, ins, sets: calls.append(_id) or False)
    code = BF.main(["--sessions", S.isoformat(), "--write"], store=st, now=NOW)
    assert code == BF.EXIT_WRITE_FAILED == 1
    assert calls == [DV.record_id(S.isoformat(), SYM)]
    out = capsys.readouterr().out
    assert "0 written" in out and "1 failed" in out
    assert st.coll(ST.DIVERGENCE).docs == {}


def test_a_refusal_outranks_a_failed_write_in_the_exit_code(world, monkeypatch):
    st, _u, _d = world
    monkeypatch.setattr(st, "upsert_divergence", lambda _id, ins, sets: False)
    code = BF.main(["--sessions", f"{S.isoformat()},2026-11-19", "--write"], store=st, now=NOW)
    assert code == BF.EXIT_REFUSED


def test_json_dry_run_writes_nothing_and_parses(world, monkeypatch, capsys):
    import json
    _no_providers(monkeypatch)
    st, _u, _d = world
    assert BF.main(["--sessions", S.isoformat(), "--json"], store=st, now=NOW) == BF.EXIT_OK
    plans = json.loads(capsys.readouterr().out)
    assert [p["session"] for p in plans] == [S.isoformat()] and plans[0]["write"] is None
    assert [r["status"] for r in plans[0]["rows"]] == ["new"]
    assert st.coll(ST.DIVERGENCE).writes == 0 and st.coll(ST.DIVERGENCE).docs == {}
