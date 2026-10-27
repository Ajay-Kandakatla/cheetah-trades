"""🚩 GG5 byte identity across the 1-minute variant build (BUILD_SPEC27 §4 WP-A step 0, 2026-10-27).

Ajay 2026-10-27: "Can you create a new page, I would like you to do the same logic of Gajjalas but on 1 min candles
please." The 1-minute page parametrizes the SAME pipeline by a `Variant`; today's 🚩 Gajjala's tab (GG5) must keep
every stored and served byte. This file was written and its fixtures captured on the UNTOUCHED tree (origin/main
4744b1b5) BEFORE any variant edit:

  tests/fixtures/gajjala/gg5_writes_2026_10_27.json — every write two real `run.run_pass` make on a recording fake
      store (collection, op, _id, body; datetimes ISO; the lease's uuid token and pid masked, and so is a stamp the
      code takes off the WALL clock — the A+ claim's `claimed_at`, the daily doc's `at` — "<wall>"), in LIVE and SHADOW mode,
      plus every payload the injected senders were handed and every /alerts row the recorders got.
  tests/fixtures/gajjala/gg5_board_2026_10_27.json — `tab.build` of all ten subs (owner=True) over each store.

The day: the tests/test_gajjala_run.py fixture — GGA forming a Bull Flag at 10:31 (one 🧠 potential), the same flag
broken at 10:41 (one A+); GGB truncated before its break bar (forming, its last bar old); NOPE never qualifies.

A moved GG5 byte is a BUG, never a regen. Recipe (the untouched tree only):
  GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_variant_gg5_identity.py
"""
from __future__ import annotations

import copy
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.test_gajjala_run import NOW, PREV, PRIOR_1M, S, TODAY_1M, T1, at, make_deps, snap_row
from tests.test_gajjala_store import FakeColl

FIX = Path(__file__).resolve().parent / "fixtures" / "gajjala"
WRITES = FIX / "gg5_writes_2026_10_27.json"
BOARD = FIX / "gg5_board_2026_10_27.json"
RECIPE = "GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_variant_gg5_identity.py (untouched tree only)"
MASK = {"token": "<token>", "pid": "<pid>"}
MODES = ("live", "shadow")
WALL_WINDOW = timedelta(hours=1)                                # the fixture day is 2026-10-13 — never inside it
SUB_KEYS = tuple(k for k, _e, _l in GC.SUBS)


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


class RecColl(FakeColl):
    """A FakeColl that logs every write (before applying it) into a shared list."""

    def __init__(self, name, log_):
        super().__init__()
        self.name, self.log = name, log_

    def _rec(self, op, **body):
        self.log.append({"coll": self.name, "op": op, "body": copy.deepcopy(body)})

    def update_one(self, q, upd, upsert=False):
        self._rec("update_one", q=q, upd=upd, upsert=upsert)
        return super().update_one(q, upd, upsert=upsert)

    def replace_one(self, q, doc, upsert=False):
        self._rec("replace_one", q=q, doc=doc, upsert=upsert)
        return super().replace_one(q, doc, upsert=upsert)

    def find_one_and_update(self, q, upd, upsert=False):
        self._rec("find_one_and_update", q=q, upd=upd, upsert=upsert)
        return super().find_one_and_update(q, upd, upsert=upsert)

    def create_index(self, spec, **kw):
        self._rec("create_index", spec=list(spec), kw=kw)
        return super().create_index(spec, **kw)


def _plain(o):
    if isinstance(o, dict):
        return {str(k): (MASK[k] if k in MASK else _plain(v)) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, (set, frozenset)):
        return sorted(_plain(v) for v in o)
    if isinstance(o, datetime):
        aware = o if o.tzinfo else o.replace(tzinfo=timezone.utc)
        if abs(aware - datetime.now(timezone.utc)) < WALL_WINDOW:   # a wall-clock stamp, not the fixture's clock
            return "<wall>"
        return o.isoformat()
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, float) and o != o:
        return "NaN"
    if isinstance(o, str) and len(o) >= 19 and o[4:5] == "-" and o[10:11] == "T":
        try:
            return _plain(datetime.fromisoformat(o))                # an ISO stamp stored as a string (the A+ claim)
        except ValueError:
            return o
    if o is None or isinstance(o, (str, int, float, bool)):
        return o
    return repr(o)


def _dump(obj) -> str:
    return json.dumps(_plain(obj), indent=1, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"


def _load(sym, day):
    if day == PREV:
        return PRIOR_1M.copy()
    if sym == "GGB":                                            # truncated before the break bucket (10:30 ET)
        cut = datetime(2026, 10, 13, 14, 30)                    # naive UTC = 10:30 ET
        return TODAY_1M[TODAY_1M.index < cut].copy()
    return TODAY_1M.copy()


def scenario(mode: str, monkeypatch):
    """Two real passes on one recording store: 10:31 (GGA forming → 🧠) and 10:41 (GGA A+, GGB forming)."""
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", mode)
    log_: list = []
    st = ST.GajjalaStore(colls={n: RecColl(n, log_) for n in ST.ALL})
    assert st.upsert_potential(ST.potential_key(S, "SEED", "kiss_fly"),          # the D9 join rule stays out
                               {"date": S.isoformat(), "symbol": "SEED", "setup": "kiss_fly"}, {"at": at(4, 6)})
    out = {"passes": [], "sent": [], "sent_potential": [], "status": [], "status_potential": []}
    for now, rows in ((T1, {"GGA": snap_row(11.2, 8.0, when=at(10, 30))}),
                      (NOW, {"GGA": snap_row(11.2, 8.0), "GGB": snap_row(11.0, 8.0), "NOPE": snap_row(1.0, 0.95)})):
        deps, _snap, send, status = make_deps(rows=rows, load=_load)
        res = RUN.run_pass(now, store=st, deps=deps)
        out["passes"].append(res)
        out["sent"].append([list(a) for a, _k in send.calls])
        out["sent_potential"].append([list(a) for a, _k in deps.send_potential.calls])
        out["status"].append([list(a) for a, _k in status.calls])
        out["status_potential"].append([list(a) for a, _k in deps.record_potential_status.calls])
    out["writes"] = log_
    return st, out


def writes_text(monkeypatch) -> tuple:
    stores, doc = {}, {"_recipe": RECIPE}
    for mode in MODES:
        st, out = scenario(mode, monkeypatch)
        stores[mode] = st
        doc[mode] = out
    return stores, _dump(doc)


def board_text(stores) -> str:
    now = at(10, 42)
    doc = {"_recipe": RECIPE}
    for mode, st in stores.items():
        doc[mode] = {k: GT.build(k, now=now, store=st, owner=True) for k in SUB_KEYS}
    return _dump(doc)


def _check(path: Path, text: str) -> None:
    if os.environ.get("GG_WRITE_GOLDEN") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert path.exists(), f"missing {path.name} — run: {RECIPE}"
    assert path.read_text(encoding="utf-8") == text, f"a GG5 byte moved in {path.name} — a BUG, never a regen"


def test_gg5_writes_are_byte_identical(monkeypatch):
    stores, text = writes_text(monkeypatch)
    _check(WRITES, text)
    doc = json.loads(text)
    live = doc["live"]
    assert any(w["coll"] == ST.ALERTS for w in live["writes"])                   # the A+ claim was exercised
    assert any(w["coll"] == ST.POTENTIALS for w in live["writes"])               # and the 🧠 tracker
    assert live["sent"][1] and live["sent_potential"][0]                          # LIVE rang both kinds
    assert doc["shadow"]["sent"] == [[], []]                                      # NEGATIVE: shadow never rang an A+
    # NEGATIVE: GG5 never writes a 1-minute collection. 2026-10-27 (critic finding 6): RecColl is injected under the
    # LOGICAL name, so the `writes` filter alone could never fail — the PHYSICAL name each logical name resolves to on
    # the scenario stores (and on a bare GG5 store) is what proves it.
    for m, st in stores.items():
        assert st.variant is V.GG5, m
        for n in ST.ALL:
            assert st.physical(n) == n, (m, n)
            assert not st.physical(n).startswith("gajjala_1m"), (m, n)
    bare = ST.GajjalaStore(colls={})
    assert [bare.physical(n) for n in ST.ALL] == list(ST.ALL)
    # the check can fail: the 1-minute store resolves its OWN names under its prefix
    assert all(ST.GajjalaStore(colls={}, variant=V.GG1).physical(n).startswith("gajjala_1m") for n in ST.OWN)
    assert not [w for m in MODES for w in doc[m]["writes"] if w["coll"].startswith("gajjala_1m")]


def test_gg5_board_is_byte_identical(monkeypatch):
    stores, _t = writes_text(monkeypatch)
    text = board_text(stores)
    _check(BOARD, text)
    doc = json.loads(text)
    for mode in MODES:
        assert set(doc[mode]) == set(SUB_KEYS) and len(SUB_KEYS) == 10
        for k, b in doc[mode].items():
            assert b["tab"] == "gajjala", k
            assert "variant" not in b, k                                          # NEGATIVE: GG5 serves no variant block
    assert "gajjala_1m" not in text and "tab=gajjala_1m" not in text              # NEGATIVE
