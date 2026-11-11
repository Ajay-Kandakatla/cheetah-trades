"""🥇 Luk's on-demand pass (chart_maps/luk/run.py — lukscan spec WP-LUK-PASS, 2026-11-11).

Ajay 2026-11-11: "Can you put an ondeman scan button for Luk' scans too"

The pass the 🔄 button's child runs (`python -m chart_maps.luk.run --on-demand`): an on_demand lease, the push gate dry,
no 🏁 grade, no 1-minute clock write, no /alerts row, its own pass doc, reads tagged `on_demand` + `cron_setups`, the
`_carried` rule that keeps the cron shortlist exactly as the cron passes alone would make it, the cron claim's take-over
of a running on-demand holder (C1) and the A8 owner check before every tail write. NEGATIVES 1–15 of the package.
"""
from __future__ import annotations

import copy
import itertools
import json
from datetime import timedelta

import pytest

from chart_maps.gajjala import run as GR
from chart_maps.gajjala import store as GS
from chart_maps.luk import constants as LC
from chart_maps.luk import run as LR
from chart_maps.luk import store as ST
from tests.test_luk_run import (DAY, Rec, _aplus, _live, _shadow_by_default, at, fake_deps,  # noqa: F401
                                fake_steps, mk_colls, mk_store, SUMMARY_KEYS)

CRON_BODY_KEYS = {"ran", "dry", "errors", "lease", "snapshot", "screens", "shortlist", "bars", "n_read", "states",
                  "aplus", "alerts", "market_state", "ledger", "calls", "bars_through", "wall_s", "status",
                  "date", "at", "_id"}


def _forming():
    return {"pullback_reversal": {"setup": "pullback_reversal", "state": "forming"}}


def _none():
    return {"pullback_reversal": {"setup": "pullback_reversal", "state": "none"}}


def _clock(step: float = 7.5):
    c = itertools.count(0.0, step)
    return lambda: next(c)


def _od_ids(colls) -> list:
    return sorted(k for k in colls[GS.PASSES].docs if k.endswith("|" + LR.ON_DEMAND_PASS_SUFFIX))


def _cron_first(monkeypatch, st, *, read=None):
    """One cron pass at 09:36:07 (t1 / t5 09:35) — the board an on-demand tap lands on."""
    fake_steps(monkeypatch, t1=at("09:35"), t5=at("09:35"), read=read)
    return LR.run_pass(at("09:36", 7), store=st, deps=fake_deps())


# ── positives ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_on_demand_pass_claims_the_on_demand_lease_and_never_the_cron_gap_clock(monkeypatch):
    st, colls = mk_store()
    _cron_first(monkeypatch, st)
    before = dict(colls[GS.STATE].docs["lease"])
    now = at("09:38", 10)
    fake_steps(monkeypatch, t1=at("09:37"), t5=at("09:35"))
    out = LR.run_on_demand(now, store=st, deps=fake_deps())
    assert out["ran"] and out["status"] == "ok" and out["on_demand"] is True
    lease = colls[GS.STATE].docs["lease"]
    assert lease["od_started_at"] == now
    assert lease["last_cron_started_at"] == before["last_cron_started_at"]      # NEGATIVE: the gap clock untouched
    assert lease["started_at"] == before["started_at"]
    assert out["lease"]["why"] == "claimed"


def test_the_on_demand_pass_doc_moves_latest_and_never_latest_cron(monkeypatch):
    st, colls = mk_store()
    _cron_first(monkeypatch, st)
    cron_ptr = copy.deepcopy(colls[GS.PASSES].docs["latest_cron"])
    now = at("09:38", 10)
    fake_steps(monkeypatch, t1=at("09:37"), t5=at("09:35"))
    out = LR.run_on_demand(now, store=st, deps=fake_deps(clock=_clock()))
    ids = _od_ids(colls)
    assert ids == [f"{DAY}|09:38:10|on_demand"]
    doc = colls[GS.PASSES].docs[ids[0]]
    assert doc["on_demand"] is True and doc["finished_at"] == now + timedelta(seconds=out["wall_s"])
    assert colls[GS.PASSES].docs["latest"]["pass_id"] == ids[0]                 # "latest" moved
    assert colls[GS.PASSES].docs["latest_cron"] == cron_ptr                     # NEGATIVE: "latest_cron" did not
    assert f"{DAY}|09:38" not in colls[GS.PASSES].docs                          # never the cron's minute doc


def test_the_on_demand_reads_carry_on_demand_and_the_cron_setups(monkeypatch):
    st, colls = mk_store()
    _cron_first(monkeypatch, st, read=_forming())
    colls[GS.READS].docs.pop(f"{DAY}|BBB")                                      # BBB: no prior doc
    fake_steps(monkeypatch, t1=at("09:37"), t5=at("09:35"), read=_aplus())
    LR.run_on_demand(at("09:38", 10), store=st, deps=fake_deps())
    a = colls[GS.READS].docs[f"{DAY}|AAA"]
    assert a["on_demand"] is True and a["setups"] == _aplus() and a["cron_setups"] == _forming()
    b = colls[GS.READS].docs[f"{DAY}|BBB"]
    assert b["on_demand"] is True and b["cron_setups"] is None
    fake_steps(monkeypatch, t1=at("09:38"), t5=at("09:35"), read=_none())       # a second tap: the CRON setups carry on
    LR.run_on_demand(at("09:39", 30), store=st, deps=fake_deps())
    assert colls[GS.READS].docs[f"{DAY}|AAA"]["cron_setups"] == _forming()
    assert colls[GS.READS].docs[f"{DAY}|AAA"]["setups"] == _none()


def test_a_cron_read_after_an_on_demand_read_drops_the_tags(monkeypatch):
    st, colls = mk_store()
    _cron_first(monkeypatch, st, read=_forming())
    fake_steps(monkeypatch, t1=at("09:37"), t5=at("09:35"), read=_none())
    LR.run_on_demand(at("09:38", 10), store=st, deps=fake_deps())
    fake_steps(monkeypatch, t1=at("09:40"), t5=at("09:40"), read=_none())
    LR.run_pass(at("09:41", 7), store=st, deps=fake_deps())
    doc = colls[GS.READS].docs[f"{DAY}|AAA"]
    assert "on_demand" not in doc and "cron_setups" not in doc and doc["setups"] == _none()


def test_run_on_demand_is_run_pass_on_demand(monkeypatch):
    rp = Rec({"status": "ok"})
    monkeypatch.setattr(LR, "run_pass", rp)
    st = object()
    LR.run_on_demand(at("09:38"), store=st, deps=None)
    assert rp.calls == [((at("09:38"),), {"store": st, "deps": None, "dry": False, "on_demand": True})]
    LR.run_on_demand(at("09:38"), store=st, deps=None, dry=True)
    assert rp.calls[-1] == ((at("09:38"),), {"store": st, "deps": None, "dry": True, "on_demand": True})
    assert "run_on_demand" in LR.__all__


def test_the_on_demand_dry_cli_lands_nothing_and_records_only_luk_writes(monkeypatch, capsys):
    fake_steps(monkeypatch, t1=at("09:50"), t5=at("09:50"), read=_aplus())
    real, colls = mk_store()
    deps = fake_deps()
    deps.fetch = None
    rc = LR.main(["--on-demand", "--dry-run", "--json", "--now", f"{DAY}T09:52"], store=ST.dry_store(real), deps=deps)
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["on_demand"] is True and out["status"] == "ok"
    assert out["dry"] is True                                   # refix 2026-11-11: a dry run says so
    assert out["writes"] and all(n.startswith("luk_") for n in out["writes"])
    assert all(c.writes == 0 and c.docs == {} for c in colls.values())         # NEGATIVE: nothing lands
    assert deps.record_status.calls == []


# ── NEGATIVES ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_1_the_on_demand_pass_never_writes_the_one_minute_clock(monkeypatch):
    st, colls = mk_store()
    _cron_first(monkeypatch, st)
    before = copy.deepcopy(colls[GS.STATE].docs[LC.LUK_STATE_BARS_THROUGH])
    fake_steps(monkeypatch, t1=at("09:37"), t5=at("09:35"))
    out = LR.run_on_demand(at("09:38", 10), store=st, deps=fake_deps())
    assert colls[GS.STATE].docs[LC.LUK_STATE_BARS_THROUGH] == before
    assert out["bars_through"] == {"t1_et": "09:37", "t5_et": "09:35"}         # computed for its own doc only


def test_NEGATIVE_2_live_mode_with_an_aplus_rings_claims_and_records_nothing(monkeypatch):
    seen = _live(monkeypatch)
    fake_steps(monkeypatch, t1=at("09:35"), t5=at("09:35"), read=_aplus())
    st, colls = mk_store()
    out = LR.run_on_demand(at("09:36", 7), store=st, deps=fake_deps())
    assert out["states"]["aplus"] == 2 and out["status"] == "ok"
    assert seen == []                                                            # zero sends
    assert colls[GS.ALERTS].docs == {} and colls[GS.ALERTS].writes == 0          # zero luk_alerts writes
    assert out["alerts"]["pushed"] == 0 and out["alerts"]["dry"] == 2


def test_NEGATIVE_3_no_grade_step(monkeypatch):
    spies = fake_steps(monkeypatch, t1=at("09:35"), t5=at("09:35"), read=_aplus())
    st, _colls = mk_store()
    gl = Rec(([], False))
    out = LR.run_on_demand(at("09:36", 7), store=st, deps=fake_deps(grade_load_day=gl))
    assert spies["grade"] == [] and gl.calls == [] and out["ledger"] is None


def test_NEGATIVE_4_no_alerts_pass_health_row(monkeypatch):
    fake_steps(monkeypatch, t1=at("09:35"), t5=at("09:35"))
    st, _colls = mk_store()
    deps = fake_deps()
    LR.run_on_demand(at("09:36", 7), store=st, deps=deps)
    assert deps.record_status.calls == []


def test_NEGATIVE_5_the_next_cron_pass_claims_and_reads_the_cron_clock(monkeypatch):
    def run(with_tap: bool):
        st, colls = mk_store()
        _cron_first(monkeypatch, st)
        if with_tap:
            fake_steps(monkeypatch, t1=at("09:38"), t5=at("09:35"))
            LR.run_on_demand(at("09:38", 30), store=st, deps=fake_deps())
        spies = fake_steps(monkeypatch, t1=at("09:40"), t5=at("09:40"))
        out = LR.run_pass(at("09:41", 7), store=st, deps=fake_deps())
        return out, spies
    tapped, spies_t = run(True)
    plain, spies_p = run(False)
    assert tapped["lease"]["why"] == "claimed" and tapped["ran"] and tapped["status"] == "ok"
    assert spies_t["read_all"] == spies_p["read_all"] == [at("09:35"), at("09:35")]


@pytest.mark.parametrize("od_read,cron_read", [(_none(), _forming()), (_forming(), _none())])
def test_NEGATIVE_6_carried_is_unchanged_by_an_on_demand_pass(monkeypatch, od_read, cron_read):
    st, colls = mk_store()
    _cron_first(monkeypatch, st, read=cron_read)
    without = LR._carried(st, datetime_day())
    fake_steps(monkeypatch, t1=at("09:37"), t5=at("09:35"), read=od_read)
    LR.run_on_demand(at("09:38", 10), store=st, deps=fake_deps())
    assert all(colls[GS.READS].docs[f"{DAY}|{s}"]["setups"] == od_read for s in ("AAA", "BBB"))
    assert LR._carried(st, datetime_day()) == without
    spies = fake_steps(monkeypatch, t1=at("09:40"), t5=at("09:40"), read=cron_read)
    LR.run_pass(at("09:41", 7), store=st, deps=fake_deps())
    assert spies["shortlist"] == [without]                                      # the cron shortlist's carry set


def datetime_day():
    from datetime import date
    return date.fromisoformat(DAY)


def test_NEGATIVE_7_the_cron_summary_and_pass_doc_keys_are_unchanged(monkeypatch):
    st, colls = mk_store()
    out = _cron_first(monkeypatch, st)
    assert set(out) == SUMMARY_KEYS and "on_demand" not in out and "superseded" not in out
    assert set(colls[GS.PASSES].docs[f"{DAY}|09:36"]) == CRON_BODY_KEYS


def _flags(monkeypatch, *, on: bool, now):
    monkeypatch.setenv("LUK_ENABLED", "1" if on else "0")
    monkeypatch.setattr(LC, "LUK_ENABLED", True)
    monkeypatch.setattr(GR, "_utc", lambda v=None, _f=GR._utc: _f(now) if v is None else _f(v))


@pytest.mark.parametrize("on,now", [(False, at("10:01", 30)), (True, at("17:06")), (True, at("03:59"))])
def test_NEGATIVE_8_off_or_outside_the_window_exits_0_with_no_lease_and_no_child_doc(monkeypatch, on, now):
    _flags(monkeypatch, on=on, now=now)
    st, colls = mk_store()
    rod = Rec({"status": "ok"})
    monkeypatch.setattr(LR, "run_on_demand", rod)
    assert LR.main(["--on-demand"], store=st) == 0
    assert rod.calls == [] and colls[GS.STATE].docs == {} and colls[GS.STATE].writes == 0


@pytest.mark.parametrize("sec", [159, 170])
def test_NEGATIVE_8_the_on_demand_child_never_rechecks_the_slot(monkeypatch, sec):
    tick = at("10:01")
    now = tick + timedelta(seconds=sec)
    _flags(monkeypatch, on=True, now=now)
    assert LR.slot_of(now)[0] == tick
    st, colls = mk_store()
    rod = Rec({"status": "ok"})
    monkeypatch.setattr(LR, "run_on_demand", rod)
    assert LR.main(["--on-demand"], store=st) == 0
    assert len(rod.calls) == 1 and rod.calls[0][1]["store"] is st
    assert LR.CHILD_STATE_ID not in colls[GS.STATE].docs


def test_NEGATIVE_8_the_cron_child_keeps_fits(monkeypatch):
    now = at("10:01") + timedelta(seconds=170)
    _flags(monkeypatch, on=True, now=now)
    assert LR.child_refusal(now) == LR.SKIP_SLOT
    st, colls = mk_store()
    rp = Rec({"status": "ok"})
    monkeypatch.setattr(LR, "run_pass", rp)
    assert LR.main(["--child"], store=st) == 0 and rp.calls == []
    doc = colls[GS.STATE].docs[LR.CHILD_STATE_ID]
    assert doc["state"] == "skipped" and doc["reason"] == LR.SKIP_SLOT


@pytest.mark.parametrize("argv", [["--on-demand", "--now", f"{DAY}T09:52"], ["--on-demand", "--child"],
                                  ["--on-demand", "--child", "--dry-run"]])
def test_NEGATIVE_9_refused_cli_combinations_exit_2(monkeypatch, argv):
    rod, rp = Rec({"status": "ok"}), Rec({"status": "ok"})
    monkeypatch.setattr(LR, "run_on_demand", rod)
    monkeypatch.setattr(LR, "run_pass", rp)
    st, _colls = mk_store()
    assert LR.main(argv, store=st) == 2
    assert rod.calls == [] and rp.calls == []


def test_NEGATIVE_10_a_failed_snapshot_does_not_move_latest(monkeypatch):
    st, colls = mk_store()
    _cron_first(monkeypatch, st)
    latest = copy.deepcopy(colls[GS.PASSES].docs["latest"])
    fake_steps(monkeypatch)
    out = LR.run_on_demand(at("09:38", 10), store=st,
                           deps=fake_deps(snapshot=lambda: ({}, {"http": 503, "wall_s": 0.1})))
    assert out["status"] == "failed"
    assert colls[GS.PASSES].docs["latest"] == latest
    assert _od_ids(colls) == [f"{DAY}|09:38:10|on_demand"]                     # its own doc still records it

    def boom():
        raise RuntimeError("massive down")
    out = LR.run_on_demand(at("09:39", 40), store=st, deps=fake_deps(snapshot=boom))
    assert out["status"] == "error" and colls[GS.PASSES].docs["latest"] == latest


def test_NEGATIVE_11_the_release_stamps_the_real_finish_never_the_start(monkeypatch):
    st, colls = mk_store()
    fake_steps(monkeypatch, t1=at("09:35"), t5=at("09:35"))
    now = at("09:38", 10)
    out = LR.run_on_demand(now, store=st, deps=fake_deps(clock=_clock()))
    lease = colls[GS.STATE].docs["lease"]
    assert out["wall_s"] > 0
    assert lease["status"] == "done" and lease["done_at"] == now + timedelta(seconds=out["wall_s"])
    assert lease["done_at"] != now


def test_NEGATIVE_12_a_running_on_demand_holder_is_taken_over_by_the_cron(monkeypatch):
    st, colls = mk_store()
    now = at("09:41", 7)
    colls[GS.STATE].docs["lease"] = {"_id": "lease", "status": "running", "held_by": GS.LEASE_ON_DEMAND,
                                     "token": "OD", "claimed_at": now - timedelta(seconds=200),
                                     "od_started_at": now - timedelta(seconds=200),
                                     "last_cron_started_at": now - timedelta(seconds=300)}
    assert 200 < LC.LUK_LEASE_SEC
    fake_steps(monkeypatch, t1=at("09:40"), t5=at("09:40"))
    out = LR.run_pass(now, store=st, deps=fake_deps())
    assert out["lease"]["why"] == "taken_over" and out["ran"] and out["status"] == "ok"
    assert colls[GS.PASSES].docs["latest_cron"]["pass_id"] == f"{DAY}|09:41"
    assert f"{DAY}|09:41" in colls[GS.PASSES].docs


class _FlipStore(ST.LukStore):
    """A LukStore whose lease a cron takes over right after the k-th upsert_read (the real lease doc is rewritten,
    so the real lease_owner_is answers False from then on)."""

    def __init__(self, colls, k):
        super().__init__(colls=colls)
        self.k, self.n_reads = k, 0

    def upsert_read(self, *a, **kw):
        super().upsert_read(*a, **kw)
        self.n_reads += 1
        if self.n_reads == self.k:
            self._colls_ref[GS.STATE].docs["lease"] = {"_id": "lease", "status": "running", "held_by": GS.LEASE_CRON,
                                                       "token": "CRON", "claimed_at": at("09:41", 7)}


def test_NEGATIVE_13_a_superseded_on_demand_pass_writes_nothing_more(monkeypatch):
    colls = mk_colls()
    st = _FlipStore(colls, 1)
    st._colls_ref = colls
    _cron_first(monkeypatch, ST.LukStore(colls=colls))
    latest = copy.deepcopy(colls[GS.PASSES].docs["latest"])
    fake_steps(monkeypatch, t1=at("09:37"), t5=at("09:35"), read=_aplus())
    out = LR.run_on_demand(at("09:38", 10), store=st, deps=fake_deps())
    assert st.n_reads == 1                                                       # NO further upsert_read
    assert out["status"] == "superseded" and out["superseded"] == 1 and out["reason"] == LR._SUPERSEDED
    assert _od_ids(colls) == []                                                  # NO pass doc
    assert colls[GS.PASSES].docs["latest"] == latest                             # "latest" not moved
    lease = colls[GS.STATE].docs["lease"]
    assert lease["token"] == "CRON" and lease["status"] == "running"             # the cron's lease left in place


@pytest.mark.parametrize("owner", ["false", "raise"])
def test_NEGATIVE_13_an_owner_read_that_fails_before_the_first_write_writes_nothing_and_frees_its_lease(
        monkeypatch, owner):
    st, colls = mk_store()
    _cron_first(monkeypatch, st)
    latest = copy.deepcopy(colls[GS.PASSES].docs["latest"])
    screens_writes = colls[ST.SCREENS_KEY].writes
    reads_before = copy.deepcopy(colls[GS.READS].docs)

    def bad(token):
        if owner == "raise":
            raise RuntimeError("mongo down")
        return False
    monkeypatch.setattr(st, "lease_owner_is", bad)
    fake_steps(monkeypatch, t1=at("09:37"), t5=at("09:35"), read=_aplus())
    out = LR.run_on_demand(at("09:38", 10), store=st, deps=fake_deps())
    assert out["status"] == "superseded"
    assert colls[ST.SCREENS_KEY].writes == screens_writes                        # zero tail writes
    assert colls[GS.READS].docs == reads_before
    assert _od_ids(colls) == [] and colls[GS.PASSES].docs["latest"] == latest
    assert colls[GS.STATE].docs["lease"]["status"] == "done"                     # its own lease freed


def test_NEGATIVE_13_a_take_over_after_the_last_read_is_caught_before_the_pass_doc(monkeypatch):
    colls = mk_colls()
    st = _FlipStore(colls, 2)                                                    # flips after the LAST read
    st._colls_ref = colls
    fake_steps(monkeypatch, t1=at("09:37"), t5=at("09:35"))
    out = LR.run_on_demand(at("09:38", 10), store=st, deps=fake_deps())
    assert st.n_reads == 2 and out["status"] == "superseded"
    assert _od_ids(colls) == [] and "latest" not in colls[GS.PASSES].docs
    assert colls[GS.STATE].docs["lease"]["token"] == "CRON"


def _lease_doc(colls):
    d = dict(colls[GS.STATE].docs.get("lease") or {})
    d.pop("token", None)
    d.pop("pid", None)
    return d


@pytest.mark.parametrize("seed,why", [
    (None, "claimed"),
    ({"status": "running", "held_by": GS.LEASE_CRON, "token": "C", "claimed_at": -100, "started_at": -100,
      "last_cron_started_at": -100}, "held"),
    ({"status": "done", "held_by": GS.LEASE_CRON, "token": "C", "claimed_at": -60, "started_at": -60,
      "last_cron_started_at": -60, "done_at": -50}, "gap"),
    ({"status": "running", "held_by": GS.LEASE_CRON, "token": "C", "claimed_at": -200, "started_at": -200,
      "last_cron_started_at": -200}, "held"),
])
def test_NEGATIVE_14_with_no_on_demand_holder_take_over_changes_nothing(seed, why):
    now = at("09:41", 7)
    got = []
    for take_over in (False, True):
        st, colls = mk_store()
        if seed is not None:
            colls[GS.STATE].docs["lease"] = dict(
                {k: (now + timedelta(seconds=v) if isinstance(v, int) else v) for k, v in seed.items()}, _id="lease")
        claim = st.claim_lease(now, source=GS.LEASE_CRON, take_over=take_over)
        got.append((bool(claim), claim.why, claim.held_by, _lease_doc(colls)))
    assert got[0] == got[1]
    assert got[1][1] == why
    if seed and seed["status"] == "running":
        assert colls[GS.STATE].docs["lease"]["token"] == "C"                    # a CRON holder is never taken over


def test_NEGATIVE_14_the_cron_pass_claims_with_take_over_and_the_on_demand_pass_without(monkeypatch):
    fake_steps(monkeypatch, t1=at("09:35"), t5=at("09:35"))
    seen = []
    real = ST.LukStore.claim_lease

    def spy(self, now, source=GS.LEASE_CRON, **kw):
        seen.append((source, kw))
        return real(self, now, source, **kw)
    monkeypatch.setattr(ST.LukStore, "claim_lease", spy)
    st, _colls = mk_store()
    LR.run_pass(at("09:36", 7), store=st, deps=fake_deps())
    LR.run_on_demand(at("09:38", 10), store=st, deps=fake_deps())
    assert seen == [(GS.LEASE_CRON, {"take_over": True}), (GS.LEASE_ON_DEMAND, {})]


def test_NEGATIVE_14_a_cron_held_lease_still_refuses_the_cron_pass(monkeypatch):
    fake_steps(monkeypatch)
    st, colls = mk_store()
    now = at("09:41", 7)
    colls[GS.STATE].docs["lease"] = {"_id": "lease", "status": "running", "held_by": GS.LEASE_CRON, "token": "C",
                                     "claimed_at": now - timedelta(seconds=100),
                                     "started_at": now - timedelta(seconds=300),
                                     "last_cron_started_at": now - timedelta(seconds=300)}
    snap = Rec(({}, {"http": 200}))
    out = LR.run_pass(now, store=st, deps=fake_deps(snapshot=snap))
    assert out["ran"] is False and out["lease"]["why"] == "held" and snap.calls == []
    assert colls[GS.STATE].docs["lease"]["token"] == "C"


def test_NEGATIVE_15_a_dry_store_never_reads_the_lease_owner(monkeypatch, capsys):
    fake_steps(monkeypatch, t1=at("09:50"), t5=at("09:50"), read=_aplus())
    real, colls = mk_store()
    st = ST.dry_store(real)

    def boom(token):
        raise AssertionError("a dry store never reads the lease owner")
    st.lease_owner_is = boom
    deps = fake_deps()
    deps.fetch = None
    assert LR.main(["--on-demand", "--dry-run", "--json", "--now", f"{DAY}T09:52"], store=st, deps=deps) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok" and "superseded" not in out
    assert all(c.writes == 0 for c in colls.values())


def test_NEGATIVE_the_on_demand_cli_logs_its_own_line(monkeypatch, caplog):
    _flags(monkeypatch, on=True, now=at("10:01", 90))
    st, _colls = mk_store()
    monkeypatch.setattr(LR, "run_on_demand", Rec({"ran": True, "status": "ok", "n_read": 3, "wall_s": 9.1,
                                                  "lease": {"why": "claimed"}}))
    import logging
    with caplog.at_level(logging.INFO, logger="chart_maps.luk.run"):
        assert LR.main(["--on-demand"], store=st) == 0
    assert any(r.getMessage().startswith("luk on-demand pass: ") for r in caplog.records)


def test_NEGATIVE_the_on_demand_dry_cli_says_dry_and_the_cron_dry_cli_is_unchanged(monkeypatch, capsys):
    """Refix 2026-11-11: `--on-demand --dry-run` reported `"dry": false` while it touched nothing. The dry-run branch
    now hands `dry=True` to run_on_demand; the cron `--dry-run` keeps `dry` True; a real (non-dry) on-demand call keeps
    passing `dry=False` (its writes land — only its push gate is dry)."""
    rod = Rec({"status": "ok"})
    monkeypatch.setattr(LR, "run_on_demand", rod)
    real, _colls = mk_store()
    assert LR.main(["--on-demand", "--dry-run", "--json", "--now", f"{DAY}T09:52"], store=ST.dry_store(real),
                   deps=fake_deps()) == 0
    assert len(rod.calls) == 1 and rod.calls[0][1]["dry"] is True
    capsys.readouterr()
    monkeypatch.undo()
    fake_steps(monkeypatch, t1=at("09:50"), t5=at("09:50"), read=_aplus())
    deps = fake_deps()
    deps.fetch = None
    assert LR.main(["--dry-run", "--json", "--now", f"{DAY}T09:52"], store=ST.dry_store(real), deps=deps) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry"] is True and "on_demand" not in out
    st, _c = mk_store()
    rp = Rec({"status": "ok"})
    monkeypatch.setattr(LR, "run_pass", rp)
    LR.run_on_demand(at("09:38"), store=st, deps=None)
    assert rp.calls[-1][1]["dry"] is False
