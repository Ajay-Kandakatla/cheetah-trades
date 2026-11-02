"""🧪 Gajjala · Audited — the fenced overlay step inside the 5-minute pass (BUILD SPEC 2026-11-01 §3.5, WP-B).

Ajay 2026-11-01: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..
Gajjals-Audited. So we can keep track of improvements on this tab"

Pins: GG5's WRITES and BOARD goldens stay byte-identical WITH the overlay ACTIVE (the fixtures are never regenerated);
run_pass's return keys never move; the overlay writes only the gajjala_audited_* collections, only for a name with an
A+ or an ARMED 🎾 read, and only when something changed; the sender is never called (the explicit shadow mode AND a
sender that refuses); the pass makes ZERO extra provider calls; a GG1 store is never audited (hook or no hook); a dry
pass lands nothing and logs ONE "dry writes" line; an on-open pass writes the overlay but claims nothing; the 🎾 stop is
frozen at the first armed read; the /alerts pass-health row is a kind no phone can receive. NEGATIVES throughout.
"""
from __future__ import annotations

import copy
import logging
from datetime import timedelta

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import audited_pass as AP
from chart_maps.gajjala import audited_rules as AUD
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from tests import test_gajjala_variant_gg5_identity as IDT
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_run import NOW, S, Rec, at, make_deps
from tests.test_gajjala_store import FakeColl, fake_store

GGA_OWN = tuple(n for n in ST.OWN if n not in V.GGA.borrows)     # alerts / state / ledger / overlay


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    from chart_maps.gajjala import run_1m as R1
    monkeypatch.setattr(R1, "spawn_loop", lambda *a, **k: True)


def gga_store(shared, colls=None) -> ST.GajjalaStore:
    """A GGA store over FakeColls for its OWN, non-borrowed names; everything else reads through `shared`."""
    return ST.GajjalaStore(colls=colls or {n: FakeColl() for n in GGA_OWN}, variant=V.GGA, shared=shared)


def _hook(made: dict):
    """deps.audited_store: ONE GGA store per GG5 store (a scenario's two passes share it)."""
    return lambda st: made.setdefault(id(st), gga_store(st))


def _patch_idt_deps(monkeypatch, hook):
    real = IDT.make_deps

    def mk(*a, **k):
        res = real(*a, **k)
        res[0].audited_store = hook
        res[0].record_audited_status = Rec(True)
        return res
    monkeypatch.setattr(IDT, "make_deps", mk)


def _audit(ok: bool, frame="5m") -> dict:
    failed = [] if ok else [{"id": "G1", "why": "no base bars to prove against"}]
    return {"aplus": ok, "original_aplus": True, "rules": ["G1", "G2", "G4"],
            "passed": ["G1", "G2", "G4"] if ok else ["G2", "G4"], "failed": failed, "frame": frame,
            "values": {}, "text": "audited A+ · UNMEASURED" if ok else "held · UNMEASURED",
            "version": AUD.AUDIT_VERSION}


def _gga_docs(gga, name) -> dict:
    return gga.coll(name).docs


# ── GG5 byte identity WITH the overlay active ─────────────────────────────────────────────────────────────────────
def test_gg5_writes_and_board_stay_byte_identical_with_the_overlay_active(monkeypatch):
    made: dict = {}
    _patch_idt_deps(monkeypatch, _hook(made))
    stores, text = IDT.writes_text(monkeypatch)
    IDT._check(IDT.WRITES, text)                                 # the golden — never regenerated
    IDT._check(IDT.BOARD, IDT.board_text(stores))
    assert len(made) == 2                                        # one GGA store per mode — the overlay RAN
    for gga in made.values():
        latest = gga.get_state(AP.LATEST_ID)
        assert latest["ok"] is True and latest["version"] == AUD.AUDIT_VERSION
        assert latest["rules"] == [r.id for r in AUD.on_rules()]
        assert latest["n_aplus_original"] >= 1                   # the 10:41 Bull-Flag A+ was judged
        assert _gga_docs(gga, ST.OVERLAY)                        # the overlay wrote its own collection
    # NEGATIVE: no GGA byte reached GG5's log (the fixture's symbol is "GGA" — the GGA claim prefix is "GGA:<date>")
    assert "gajjala_audited" not in text and f"GGA:{S.isoformat()}" not in text and "aplus_held" not in text


def test_run_pass_return_keys_identical_with_and_without_the_overlay(monkeypatch):
    _patch_idt_deps(monkeypatch, _hook({}))
    _st, on = IDT.scenario("shadow", monkeypatch)
    _patch_idt_deps(monkeypatch, lambda st: None)
    _st2, off = IDT.scenario("shadow", monkeypatch)
    assert [set(r) for r in on["passes"]] == [set(r) for r in off["passes"]]
    assert [r["errors"] for r in on["passes"]] == [[], []]       # NEGATIVE: the step never writes out["errors"]
    assert not any(k.startswith("audit") for r in on["passes"] for k in r)


# ── what the overlay writes ───────────────────────────────────────────────────────────────────────────────────────
def test_overlay_docs_only_for_names_with_an_aplus_or_an_armed_squeeze(monkeypatch):
    made: dict = {}
    seen: list = []
    real = AP.run_step

    def spy(st, gga, reads, frames, *a, **k):
        seen.append({s: AP.wants_overlay(reads.get(s)) for s in frames})
        return real(st, gga, reads, frames, *a, **k)
    monkeypatch.setattr(AP, "run_step", spy)
    _patch_idt_deps(monkeypatch, _hook(made))
    st, _out = IDT.scenario("shadow", monkeypatch)
    gga = made[id(st)]
    want = {s for p in seen for s, w in p.items() if w}
    never = {s for p in seen for s in p} - want
    docs = _gga_docs(gga, ST.OVERLAY)
    assert {d["symbol"] for d in docs.values()} == want and "GGA" in want
    assert never, "the scenario reads a name with nothing to say (GGB) — the NEGATIVE needs one"
    assert not [d for d in docs.values() if d["symbol"] in never]       # NEGATIVE: no doc for a quiet name
    assert all(k.startswith(f"{S.isoformat()}|") for k in docs)
    # GG5's own physical names never carry an overlay; the GGA store's do
    assert st.physical(ST.OVERLAY) == "gajjala_overlay" and gga.physical(ST.OVERLAY) == "gajjala_audited_overlay"


def _scenario_one_pass(monkeypatch, judge=None):
    """The 10:41 pass only (GGA A+), the overlay on — -> (GG5 store, GGA store, deps)."""
    if judge is not None:
        monkeypatch.setattr(AUD, "judge", judge)
    st = fake_store()
    gga = gga_store(st)
    deps = make_deps(rows={"GGA": IDT.snap_row(11.2, 8.0), "GGB": IDT.snap_row(11.0, 8.0)}, load=IDT._load)[0]
    deps.audited_store = lambda s: gga
    deps.record_audited_status = Rec(True)
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["errors"] == []
    return st, gga, deps, out


def test_the_1041_bull_flag_aplus_is_either_claimed_in_shadow_or_held_never_both(monkeypatch):
    _st, gga, _d, out = _scenario_one_pass(monkeypatch)
    assert "GGA:bull_flag" in out["aplus"]
    al = _gga_docs(gga, ST.ALERTS)
    claim = f"SHADOW:{AL.claim_key(S, 'GGA', 'bull_flag', V.GGA)}"
    held = f"{AL.claim_key(S, 'GGA', 'bull_flag', V.GGA)}#{AUD.HELD_ROW_STATE}"
    ov = gga.get_overlay(S, "GGA")["setups"]["bull_flag"]
    assert ov["entry_bar_t"] == "2026-10-13 10:40" and ov["version"] == AUD.AUDIT_VERSION
    if ov["aplus"]:
        assert claim in al and held not in al
    else:
        assert held in al and claim not in al and al[held]["audit"]["failed"]


def test_forced_pass_rings_a_shadow_claim_with_the_gga_kind_url_and_tag(monkeypatch):
    real = AUD.judge
    _st, gga, deps, _o = _scenario_one_pass(monkeypatch, judge=lambda r, F, fz=None: dict(real(r, F, fz), aplus=True,
                                                                                         failed=[]))
    al = _gga_docs(gga, ST.ALERTS)
    key = f"SHADOW:{AL.claim_key(S, 'GGA', 'bull_flag', V.GGA)}"
    assert key.startswith("SHADOW:GGA:") and al[key]["state"] == "shadow"
    wp = al[key]["would_push"]
    assert wp["kind"] == "gajjala_audited_setup" == V.GGA.push_kind_setup
    assert "tab=gajjala_audited" in wp["url"] and wp["tag"] == "gga-bull_flag-GGA"
    assert not [k for k in al if k.endswith(f"#{AUD.HELD_ROW_STATE}")]   # NEGATIVE: an audited A+ is never held
    assert not [k for k in al if k.startswith("GG:") or k.startswith("SHADOW:GG:")]   # NEGATIVE: never a GG5 id


def test_forced_fail_holds_the_aplus_with_one_held_row_and_no_claim(monkeypatch):
    _st, gga, deps, _o = _scenario_one_pass(monkeypatch, judge=lambda r, F, fz=None: _audit(False, F.frame))
    al = _gga_docs(gga, ST.ALERTS)
    held = f"{AL.claim_key(S, 'GGA', 'bull_flag', V.GGA)}#{AUD.HELD_ROW_STATE}"
    assert al[held]["state"] == "held" and al[held]["mode"] == "shadow"
    assert al[held]["kind"] == V.GGA.push_kind_setup and al[held]["audit"]["failed"][0]["id"] == "G1"
    assert al[held]["entry_bar_t"] == "2026-10-13 10:40"
    assert not [k for k in al if k.startswith("SHADOW:")]       # NEGATIVE: a held read never rings (shadow or live)
    latest = gga.get_state(AP.LATEST_ID)
    assert latest["n_held"] == 1 and latest["held"] == [{"symbol": "GGA", "setup": "bull_flag", "failed": ["G1"]}]
    assert latest["n_aplus_audited"] == 0 and latest["alerts"]["aplus"] == 0     # alerts._candidates skipped it
    st2, gga2, _d2, _o2 = _scenario_one_pass(monkeypatch, judge=lambda r, F, fz=None: _audit(False, F.frame))
    assert len([k for k in _gga_docs(gga2, ST.ALERTS) if k.endswith("#held")]) == 1


def test_the_sender_is_never_called_even_when_the_constant_says_live(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_AUDITED_PUSH_MODE", "live")
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "shadow")      # GG5 rings nothing either: every send is visible
    real = AUD.judge
    _st, gga, deps, _o = _scenario_one_pass(monkeypatch, judge=lambda r, F, fz=None: dict(real(r, F, fz), aplus=True,
                                                                                         failed=[]))
    assert deps.send.calls == []                                 # NEGATIVE: nothing was sent, by anyone
    al = _gga_docs(gga, ST.ALERTS)
    assert [k for k in al if k.startswith("SHADOW:GGA:")]        # the explicit mode held it in shadow
    assert not [k for k in al if k.startswith("GGA:") and "#" not in k]   # NEGATIVE: no live claim
    with pytest.raises(RuntimeError, match="never sends"):
        AP.refuse_send("owner@example.com", {})


# ── zero extra provider calls in the pass ─────────────────────────────────────────────────────────────────────────
def _counted_pass(monkeypatch, hook) -> dict:
    counts: dict = {}
    frames_calls: list = []
    real_ff = B.frames_for

    def ff(*a, **k):
        frames_calls.append(1)
        return real_ff(*a, **k)
    monkeypatch.setattr(B, "frames_for", ff)
    deps = make_deps(rows={"GGA": IDT.snap_row(11.2, 8.0), "GGB": IDT.snap_row(11.0, 8.0)}, load=IDT._load)[0]
    for name in ("snapshot", "load_day", "status_lookup", "massive_lookup", "daily_loader", "fetch_types",
                 "fetch_splits", "halts"):
        fn = getattr(deps, name)

        def wrap(*a, _fn=fn, _n=name, **k):
            counts[_n] = counts.get(_n, 0) + 1
            return _fn(*a, **k)
        setattr(deps, name, wrap)
    deps.audited_store = hook
    deps.record_audited_status = Rec(True)
    RUN.run_pass(NOW, store=fake_store(), deps=deps)
    counts["frames_for"] = len(frames_calls)
    return counts


def _counted_dry_pass(monkeypatch, overlay: bool):
    """The §5 CLI proof in-process: `run --dry-run` = run_pass(dry=True) over a dry_store; counts every provider dep."""
    counts: dict = {}
    frames_calls: list = []
    real_ff = B.frames_for

    def ff(*a, **k):
        frames_calls.append(1)
        return real_ff(*a, **k)
    monkeypatch.setattr(B, "frames_for", ff)
    deps = make_deps(rows={"GGA": IDT.snap_row(11.2, 8.0), "GGB": IDT.snap_row(11.0, 8.0)}, load=IDT._load)[0]
    for name in ("snapshot", "load_day", "status_lookup", "massive_lookup", "daily_loader", "fetch_types",
                 "fetch_splits", "halts"):
        fn = getattr(deps, name)

        def wrap(*a, _fn=fn, _n=name, **k):
            counts[_n] = counts.get(_n, 0) + 1
            return _fn(*a, **k)
        setattr(deps, name, wrap)
    if not overlay:
        deps.audited_store = lambda st: None
    deps.record_audited_status = Rec(True)
    res = RUN.run_pass(NOW, store=RUN.dry_store(fake_store()), deps=deps, dry=True)
    counts["frames_for"] = len(frames_calls)
    return counts, res, deps


def test_the_dry_cli_pass_makes_equal_provider_calls_and_an_unchanged_summary(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    on, res_on, deps_on = _counted_dry_pass(monkeypatch, overlay=True)
    on_lines = _dry_records(caplog)
    caplog.clear()
    off, res_off, _d = _counted_dry_pass(monkeypatch, overlay=False)
    assert len(on_lines) == 1                                    # the overlay ran on the dry pass
    assert all(w[0].startswith("gajjala_audited_") for w in on_lines[0].args[0])
    assert _dry_records(caplog) == []                            # NEGATIVE: overlay off logs no dry line
    assert on == off and on["snapshot"] == 1 and on["frames_for"] == 1   # THE PASS = zero extra calls
    assert set(res_on) == set(res_off)                           # NEGATIVE: the JSON summary gains no key
    assert res_on["bars"] == res_off["bars"]                     # the bars block is unchanged
    assert res_on["errors"] == res_off["errors"] == []
    assert deps_on.record_audited_status.calls == []             # NEGATIVE: no /alerts row on a dry pass


def test_the_overlay_makes_zero_extra_provider_calls(monkeypatch):
    seen: list = []
    on = _counted_pass(monkeypatch, lambda st: seen.append(1) or gga_store(st))
    off = _counted_pass(monkeypatch, lambda st: None)
    assert seen == [1]                                           # the overlay ran on the first pass
    assert on == off and on["snapshot"] == 1 and on["frames_for"] == 1 and on["load_day"] >= 1


# ── store_for (C7) ────────────────────────────────────────────────────────────────────────────────────────────────
def test_store_for_never_audits_a_gg1_store_hook_or_no_hook():
    def boom(st):
        raise AssertionError("the hook is never consulted for a non-GG5 store")
    for d in (RUN.Deps(), RUN.Deps(audited_store=boom)):
        assert AP.store_for(ST.for_variant(V.GG1), d) is None
        assert AP.store_for(RUN.dry_store(ST.for_variant(V.GG1)), d) is None
        assert AP.store_for(ST.GajjalaStore(colls={}, variant=V.GG1), d) is None


def test_store_for_defaults():
    assert AP.store_for(ST.default(), RUN.Deps()) is ST.for_variant(V.GGA)
    dry = AP.store_for(RUN.dry_store(ST.default()), RUN.Deps())
    assert dry.dry is True and dry.variant is V.GGA and dry is not ST.for_variant(V.GGA)
    assert dry.physical(ST.ALERTS) == "gajjala_audited_alerts" and dry.physical(ST.READS) == ST.READS
    assert AP.store_for(fake_store(), RUN.Deps()) is None        # an injected test store: the step is skipped
    marker = object()
    assert AP.store_for(fake_store(), RUN.Deps(audited_store=lambda st: marker)) is marker


# ── dry / on-demand (C6) ──────────────────────────────────────────────────────────────────────────────────────────
DRY_LINE = "gajjala audit overlay dry writes:"


def _dry_records(caplog):
    return [r for r in caplog.records if r.getMessage().startswith(DRY_LINE)]


def test_dry_pass_lands_nothing_and_logs_one_dry_writes_line(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    deps = make_deps(rows={"GGA": IDT.snap_row(11.2, 8.0)}, load=IDT._load)[0]
    deps.record_audited_status = Rec(True)
    built: list = []
    real = AP.store_for

    def spy(st, d):
        g = real(st, d)
        built.append(g)
        return g
    monkeypatch.setattr(AP, "store_for", spy)
    res = RUN.run_pass(NOW, store=RUN.dry_store(fake_store()), deps=deps, dry=True)
    assert res["ran"] and res["errors"] == []
    gga = built[0]
    assert gga is not None and gga.dry is True and gga.variant is V.GGA
    recs = _dry_records(caplog)
    assert len(recs) == 1
    names = [w[0] for w in recs[0].args[0]]
    assert names and all(n.startswith("gajjala_audited_") for n in names)
    assert "gajjala_audited_overlay" in names                    # the overlay write was RECORDED, not made
    assert deps.record_audited_status.calls == []                # NEGATIVE: no /alerts row on a dry pass
    caplog.clear()
    deps2 = make_deps(rows={"GGA": IDT.snap_row(11.2, 8.0)}, load=IDT._load)[0]
    deps2.audited_store = lambda st: None
    res2 = RUN.run_pass(NOW, store=RUN.dry_store(fake_store()), deps=deps2, dry=True)
    assert set(res2) == set(res)                                 # the summary gains no key
    assert _dry_records(caplog) == []


def test_a_non_dry_pass_logs_no_dry_writes_line_and_records_the_status_row(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    _st, gga, deps, _o = _scenario_one_pass(monkeypatch)
    assert _dry_records(caplog) == []                            # NEGATIVE
    assert len(deps.record_audited_status.calls) == 1
    (counts, now, reason), _k = deps.record_audited_status.calls[0]
    assert {"aplus_original", "aplus_audited", "held", "aplus", "shadow"} <= set(counts)
    assert counts["aplus_original"] == counts["aplus_audited"] + counts["held"] >= 1
    assert now == NOW.astimezone(now.tzinfo) and reason is None


def test_a_dry_pass_with_a_real_gga_store_writes_nothing():
    st = fake_store()
    gga = gga_store(st)
    deps = make_deps(rows={"GGA": IDT.snap_row(11.2, 8.0)}, load=IDT._load)[0]
    deps.audited_store = lambda s: gga
    RUN.run_pass(NOW, store=st, deps=deps, dry=True)
    assert all(gga.coll(n).writes == 0 for n in GGA_OWN)        # NEGATIVE: a dry pass lands nothing


def test_on_demand_writes_the_overlay_but_claims_nothing():
    st = fake_store()
    gga = gga_store(st)
    deps = make_deps(rows={"GGA": IDT.snap_row(11.2, 8.0)}, load=IDT._load)[0]
    deps.audited_store = lambda s: gga
    deps.record_audited_status = Rec(True)
    out = RUN.run_on_demand(NOW, store=st, deps=deps)
    assert out["ran"] and out["errors"] == []
    assert gga.get_overlay(S, "GGA") and gga.get_state(AP.LATEST_ID)["ok"] is True
    assert _gga_docs(gga, ST.ALERTS) == {}                       # NEGATIVE: no claim, no #held, no refusal row
    assert deps.record_audited_status.calls == []                # NEGATIVE: no /alerts row


def _logged_gg5(monkeypatch, hook, judge=None):
    if judge is not None:
        monkeypatch.setattr(AUD, "judge", judge)
    log_: list = []
    st = ST.GajjalaStore(colls={n: IDT.RecColl(n, log_) for n in ST.ALL})
    deps = make_deps(rows={"GGA": IDT.snap_row(11.2, 8.0)}, load=IDT._load)[0]
    deps.audited_store = hook
    out = RUN.run_on_demand(NOW, store=st, deps=deps)
    return out, IDT._dump(log_)


def test_a_raising_judge_never_touches_gg5_and_marks_the_state_doc(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("judge down")
    _o0, base = _logged_gg5(monkeypatch, lambda st: None)
    gga_box: dict = {}
    out, logged = _logged_gg5(monkeypatch, lambda st: gga_box.setdefault("g", gga_store(st)), judge=boom)
    assert out["errors"] == [] and out["status"] == "ok"         # NEGATIVE: never GG5's errors
    assert logged == base                                        # GG5 writes byte-identical
    latest = gga_box["g"].get_state(AP.LATEST_ID)
    assert latest["ok"] is False and latest["error"] == "RuntimeError"


def test_a_plain_injected_store_skips_the_step_without_building_a_gga_store(monkeypatch):
    built: list = []
    steps: list = []
    monkeypatch.setattr(ST, "for_variant", lambda *a, **k: built.append(a) or None)
    monkeypatch.setattr(AP, "run_step", lambda *a, **k: steps.append(a))
    deps = make_deps(rows={"GGA": IDT.snap_row(11.2, 8.0)}, load=IDT._load)[0]
    out = RUN.run_pass(NOW, store=fake_store(), deps=deps)
    assert out["ran"] and built == [] and steps == []


# ── the 🎾 frozen stop ────────────────────────────────────────────────────────────────────────────────────────────
SQ = "reversal_squeeze"


def _armed(trigger, stop, bar="2026-10-13 10:20"):
    return {"setup": SQ, "state": GC.POTENTIAL_STATE, "ready": True, "base": {"bars": 3}, "trigger": trigger,
            "stop": stop, "as_of_bar_t": bar, "frame": "5m", "variant": None, "grade": None}


class _Frames:
    def __init__(self, F):
        self.F = F

    def frame(self, tf):
        return self.F


def _step(gga, reads, frames=None, now=None):
    frames = frames if frames is not None else {s: object() for s in reads}
    return AP.run_step(gga.shared, gga, reads, frames, now or NOW, S, alert_ctx={}, owner="o", dry=False,
                       push_dry=True)


def test_frozen_stop_keeps_the_first_armed_read_per_trigger():
    gga = gga_store(fake_store())
    _step(gga, {"SQZ": {SQ: _armed(2.50, 2.06)}})
    ov = gga.get_overlay(S, "SQZ")
    assert ov["frozen"][SQ] == [{"trigger": "2.5", "stop": 2.06, "bar_t": "2026-10-13 10:20", "at_et": "10:20"}]
    assert ov["setups"] == {}
    n0 = gga.coll(ST.OVERLAY).writes
    s0 = gga.coll(ST.STATE).writes
    _step(gga, {"SQZ": {SQ: _armed(2.50, 1.80, bar="2026-10-13 10:25")}}, now=NOW + timedelta(minutes=5))
    assert gga.get_overlay(S, "SQZ")["frozen"][SQ][0]["stop"] == 2.06        # never overwritten
    assert gga.coll(ST.OVERLAY).writes == n0                     # NEGATIVE: nothing changed → no overlay upsert
    assert gga.coll(ST.STATE).writes == s0 + 1                   # one state upsert per pass
    _step(gga, {"SQZ": {SQ: _armed(2.70, 2.30, bar="2026-10-13 10:30")}}, now=NOW + timedelta(minutes=10))
    fz = gga.get_overlay(S, "SQZ")["frozen"][SQ]
    assert [e["trigger"] for e in fz] == ["2.5", "2.7"] and gga.coll(ST.OVERLAY).writes == n0 + 1


def test_a_building_or_non_squeeze_read_writes_nothing():
    gga = gga_store(fake_store())
    building = dict(_armed(2.5, 2.06), ready=False)
    bf_forming = dict(_armed(2.5, 2.06), setup="bull_flag")
    _step(gga, {"AAA": {SQ: building}, "BBB": {"bull_flag": bf_forming}})
    assert _gga_docs(gga, ST.OVERLAY) == {}                      # NEGATIVE: neither name has anything to say
    assert AP.wants_overlay({SQ: building}) is False and AP.wants_overlay({"bull_flag": bf_forming}) is False
    assert AP.frozen_update([], building) == [] and AP.frozen_update([], dict(_armed(None, 2.0))) == []


def test_the_aplus_at_pass_three_uses_the_frozen_stop_in_g4():
    F = FX.rs_frame()
    gga = gga_store(fake_store())
    _step(gga, {"SQZ": {SQ: _armed(2.50, 2.06)}})
    _step(gga, {"SQZ": {SQ: _armed(2.50, 1.80)}}, now=NOW + timedelta(minutes=5))
    aplus = dict(_armed(2.50, 1.80, bar=F.t[-1]), state="aplus", entry_bar_t=F.t[-1],
                 base={"from_t": F.t[-4], "to_t": F.t[-2], "bars": 3}, red_closes=0)
    _step(gga, {"SQZ": {SQ: aplus}}, frames={"SQZ": _Frames(F)}, now=NOW + timedelta(minutes=10))
    ov = gga.get_overlay(S, "SQZ")["setups"][SQ]
    g4 = ov["values"]["G4"]
    assert g4["frozen"] is True and g4["frozen_reason"] == AUD.FROZEN_REASONS["frozen"]
    assert g4["stop_used"] == "2.06" and ov["stop"] == 1.80 and ov["entry_bar_t"] == F.t[-1]
    assert ov["aplus"] is False and "G4" in [f["id"] for f in ov["failed"]]     # 17.6 % > the cap
    assert gga.get_overlay(S, "SQZ")["frozen"][SQ][0]["stop"] == 2.06


# ── the /alerts pass-health row ───────────────────────────────────────────────────────────────────────────────────
def test_the_pass_health_kind_is_registered_and_no_phone_can_receive_it():
    from push import hooks, recent, subs
    from supply_demand import alert_status as AS
    k = AS.GAJJALA_AUDITED_KIND
    assert k == V.GGA.push_kind_setup == "gajjala_audited_setup"
    assert k in AS.PASS_KINDS and AS.CADENCE_SEC[k] == AS.CADENCE_SEC[AS.GAJJALA_KIND]
    i = AS.PASS_KINDS.index(AS.GAJJALA_1M_POTENTIAL_KIND)
    assert AS.PASS_KINDS[i + 1] == k                             # after the 1-minute pair (their pin stays)
    assert k not in subs.default_prefs() and k not in subs.OWNER_KEEP_SET     # NEGATIVE
    assert len(subs.OWNER_KEEP_SET) == 7                         # NEGATIVE: the 🧪 kind adds none (WIDENED 2026-11-01: six → seven — 🥇 luk_setup, Ajay 2026-11-01: "Lets make it live. also alerts too.")
    assert not [n for n in dir(hooks) if "audited" in n]         # NEGATIVE: no sender
    assert k not in recent.ITEM_URL_BY_KIND                      # NEGATIVE: no push url
    p = AS.status_payload(pass_coll=FakeColl(), latest_coll=FakeColl(), now=at(10, 42))
    assert p["passes"][k] == {"as_of": None, "date": None, "counts": {}, "cadence_sec": AS.CADENCE_SEC[k]}


def test_record_status_rides_the_cron_pass_only(monkeypatch):
    calls: list = []
    monkeypatch.setattr("supply_demand.alert_status.record_pass",
                        lambda kind, counts, now, reason=None: calls.append((kind, copy.deepcopy(counts))) or True)
    assert RUN._record_audited_status({"aplus": 1}, NOW) is True
    assert calls == [("gajjala_audited_setup", {"aplus": 1})]
