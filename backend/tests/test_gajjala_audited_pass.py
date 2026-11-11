"""🧪 Gajjala · Audited — the fenced overlay step inside the 5-minute pass (BUILD SPEC 2026-11-01 §3.5, WP-B).

Ajay 2026-11-01: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..
Gajjals-Audited. So we can keep track of improvements on this tab"

Pins: GG5's WRITES and BOARD goldens stay byte-identical WITH the overlay ACTIVE (no regen inside this test; a
dated regen of either golden is recorded in test_gajjala_variant_gg5_identity.py);
run_pass's return keys never move; the overlay writes only the gajjala_audited_* collections, only for a name with an
A+ or an ARMED 🎾 read, and only when something changed; the sender is never called (the explicit shadow mode AND a
sender that refuses); the pass makes ZERO extra provider calls; a GG1 store is never audited (hook or no hook); a dry
pass lands nothing and logs ONE "dry writes" line; an on-open pass writes the overlay but claims nothing; the 🎾 stop is
frozen at the first armed read; the /alerts pass-health row is a kind no phone can receive. NEGATIVES throughout.
"""
from __future__ import annotations

import copy
import dataclasses
import logging
from datetime import date, datetime, timedelta

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


def _forced(real):
    """judge → the real audit with EVERY rule passed (with_t1 recomputes aplus from `passed`, so `passed` is forced
    too — MOVED 2026-11-01: `aplus=True, failed=[]` alone no longer survives the T1 composer)."""
    def j(r, F, fz=None, **kw):
        a = real(r, F, fz, **kw)
        return dict(a, aplus=True, failed=[], passed=list(a["rules"]))
    return j


def _gga_docs(gga, name) -> dict:
    return gga.coll(name).docs


# ── GG5 byte identity WITH the overlay active ─────────────────────────────────────────────────────────────────────
def test_gg5_writes_and_board_stay_byte_identical_with_the_overlay_active(monkeypatch):
    made: dict = {}
    _patch_idt_deps(monkeypatch, _hook(made))
    stores, text = IDT.writes_text(monkeypatch)
    IDT._check(IDT.WRITES, text)                                 # the golden — never regenerated here
    IDT._check(IDT.BOARD, IDT.board_text(stores))
    assert len(made) == 2                                        # one GGA store per mode — the overlay RAN
    for gga in made.values():
        latest = gga.get_state(AP.LATEST_ID)
        assert latest["ok"] is True and latest["version"] == AUD.AUDIT_VERSION
        assert latest["rules"] == [r.id for r in AUD.filter_rules()]       # MOVED 2026-11-01: filters (T1 incl.)
        assert latest["exit_rules"] == [r.id for r in AUD.exit_rules()]
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
    assert gga.get_state(AP.LATEST_ID)["ok"] is True                    # C6 — the assertion that bites
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
    _st, gga, deps, _o = _scenario_one_pass(monkeypatch, judge=_forced(AUD.judge))
    al = _gga_docs(gga, ST.ALERTS)
    key = f"SHADOW:{AL.claim_key(S, 'GGA', 'bull_flag', V.GGA)}"
    assert key.startswith("SHADOW:GGA:") and al[key]["state"] == "shadow"
    wp = al[key]["would_push"]
    assert wp["kind"] == "gajjala_audited_setup" == V.GGA.push_kind_setup
    assert "tab=gajjala_audited" in wp["url"] and wp["tag"] == "gga-bull_flag-GGA"
    assert not [k for k in al if k.endswith(f"#{AUD.HELD_ROW_STATE}")]   # NEGATIVE: an audited A+ is never held
    assert not [k for k in al if k.startswith("GG:") or k.startswith("SHADOW:GG:")]   # NEGATIVE: never a GG5 id


def test_forced_fail_holds_the_aplus_with_one_held_row_and_no_claim(monkeypatch):
    _st, gga, deps, _o = _scenario_one_pass(monkeypatch, judge=lambda r, F, fz=None, **kw: _audit(False, F.frame))
    al = _gga_docs(gga, ST.ALERTS)
    held = f"{AL.claim_key(S, 'GGA', 'bull_flag', V.GGA)}#{AUD.HELD_ROW_STATE}"
    assert al[held]["state"] == "held" and al[held]["mode"] == "shadow"
    assert al[held]["kind"] == V.GGA.push_kind_setup and al[held]["audit"]["failed"][0]["id"] == "G1"
    assert al[held]["entry_bar_t"] == "2026-10-13 10:40"
    assert not [k for k in al if k.startswith("SHADOW:")]       # NEGATIVE: a held read never rings (shadow or live)
    latest = gga.get_state(AP.LATEST_ID)
    assert latest["n_held"] == 1 and latest["held"] == [{"symbol": "GGA", "setup": "bull_flag", "failed": ["G1"], "admit": None}]   # MOVED 2026-11-09: + admit
    assert latest["n_aplus_audited"] == 0 and latest["alerts"]["aplus"] == 0     # alerts._candidates skipped it
    st2, gga2, _d2, _o2 = _scenario_one_pass(monkeypatch, judge=lambda r, F, fz=None, **kw: _audit(False, F.frame))
    assert len([k for k in _gga_docs(gga2, ST.ALERTS) if k.endswith("#held")]) == 1


def test_the_sender_is_never_called_even_when_the_constant_says_live(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_AUDITED_PUSH_MODE", "live")
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "shadow")      # GG5 rings nothing either: every send is visible
    _st, gga, deps, _o = _scenario_one_pass(monkeypatch, judge=_forced(AUD.judge))
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
        self.as_of_bar_t = {"5m": F.t[-1] if F is not None and F.t else None}

    def frame(self, tf):
        return self.F


def _restamp(F, last: str):
    """The same bars, every stamp shifted so the latest is `last` — a pre-market fixture as an in-window A+ bar."""
    fmt = "%Y-%m-%d %H:%M"
    shift = datetime.strptime(last, fmt) - datetime.strptime(F.t[-1], fmt)
    return dataclasses.replace(F, t=[(datetime.strptime(x, fmt) + shift).strftime(fmt) for x in F.t])


def _step(gga, reads, frames=None, now=None):
    frames = frames if frames is not None else {s: object() for s in reads}
    out = AP.run_step(gga.shared, gga, reads, frames, now or NOW, S, alert_ctx={}, owner="o", dry=False,
                      push_dry=True)
    assert gga.get_state(AP.LATEST_ID)["ok"] is True                    # C6
    return out


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
    F = _restamp(FX.rs_frame(), "2026-10-13 10:50")                   # MOVED 2026-11-01 (C1): an in-window bar
    gga = gga_store(fake_store())
    _step(gga, {"SQZ": {SQ: _armed(2.50, 2.06)}})
    _step(gga, {"SQZ": {SQ: _armed(2.50, 1.80)}}, now=NOW + timedelta(minutes=5))
    aplus = dict(_armed(2.50, 1.80, bar=F.t[-1]), state="aplus", entry_bar_t=F.t[-1],
                 base={"from_t": F.t[-4], "to_t": F.t[-2], "bars": 3}, red_closes=0)
    _step(gga, {"SQZ": {SQ: aplus}}, frames={"SQZ": _Frames(F)}, now=at(10, 51))
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


# ══ 2026-11-01 — the eight modifications (SPEC rev 2 §3.2, WP-B) ══════════════════════════════════════════════════
# Ajay 2026-11-01: "Yes make the changes in audited please" / "But keep a track record too to see the winners and
# loster". 🧪 judges ONLY the A+ bars 🚩 would ring on this pass (alerts.refusal is None and not claimed today) [C1];
# T1 is judged LAST over the claimable survivors in 🚩's ring order against today's GGA claims [C3, C4]; T4 reads the
# pass's own strip; the #held marker and the shadow claim carry the audit; the day's T4 count comes from the durable
# markers [C2]; every scenario asserts the state doc `ok is True` [C6]. NEGATIVES throughout.
BAR = "2026-10-13 10:40"
STRIP_OK = {"best_change_pct": 55.0, "best_symbol": "RUN"}             # a day whose top runner is well over T4's line
REFUSALS = ("not_aplus_variant", "no_risk", "late", "claimed_before", "suppressed_closed", "suppressed_premarket",
            "suppressed_first15", "suppressed_window", "suppressed_halt", "suppressed_exhausted")


class _Fr:
    """A Frames stand-in: the latest closed bar per frame (alerts._as_of reads it) + .frame() for the judge."""

    def __init__(self, as_of5, as_of15=None, F=None):
        self.as_of_bar_t = {"5m": as_of5, "15m": as_of15}
        self.F = F

    def frame(self, tf):
        return self.F


def _aplus(setup="bull_flag", bar=BAR, trigger=2.0, stop=1.8, frame="5m", **kw):
    return dict({"setup": setup, "state": "aplus", "entry_bar_t": bar, "frame": frame, "trigger": trigger,
                 "stop": stop, "risk_pct": 10.0, "variant": None, "grade": None}, **kw)


def _ok_audit(frame="5m", failed_ids=()) -> dict:
    """A judge()-shaped audit: every per-read rule passed, except `failed_ids`."""
    ids = [x.id for x in AUD.judge_rules()]
    failed = [{"id": i, "why": f"{i} held it"} for i in failed_ids]
    return {"aplus": not failed, "original_aplus": True, "rules": ids,
            "passed": [i for i in ids if i not in failed_ids], "failed": failed, "frame": frame,
            "values": {i: {"frame": frame} for i in ids},
            "text": "audited A+ · UNMEASURED" if not failed else "held · UNMEASURED", "version": AUD.AUDIT_VERSION}


def _stub(monkeypatch, calls=None, fail_by_sym=None):
    """judge → a judge()-shaped audit; `fail_by_sym` {SYM: [ids]}; records (sym-less) calls with their kwargs."""
    fail_by_sym = fail_by_sym or {}

    def j(r, F, fz=None, **kw):
        if calls is not None:
            calls.append((r.get("symbol"), r.get("setup"), r.get("entry_bar_t"), kw))
        return _ok_audit(r.get("frame") or "5m", fail_by_sym.get(r.get("symbol"), ()))
    monkeypatch.setattr(AUD, "judge", j)


def _reads(*rows):
    """rows = (SYM, read) → {SYM: {setup: read}} (the read carries its symbol so the stub can see it)."""
    out: dict = {}
    for sym, r in rows:
        out.setdefault(sym, {})[r["setup"]] = dict(r, symbol=sym)
    return out


def _run(gga, reads, frames, now=NOW, strip=STRIP_OK, push_dry=False, session=S):
    out = AP.run_step(gga.shared, gga, reads, frames, now, session, alert_ctx={}, owner="o", dry=False,
                      push_dry=push_dry, strip=strip)
    latest = gga.get_state(AP.LATEST_ID)
    assert latest["ok"] is True, latest                                 # C6 — every scenario
    return out, latest


def _fids(audit) -> list:
    return [f["id"] for f in (audit or {}).get("failed") or []]


def _held_ids(gga) -> dict:
    return {k: v for k, v in _gga_docs(gga, ST.ALERTS).items() if k.endswith(f"#{AUD.HELD_ROW_STATE}")}


def _claims(gga) -> dict:
    return {k: v for k, v in _gga_docs(gga, ST.ALERTS).items() if k.startswith("SHADOW:GGA:")}


# ── C6: the state-doc assertion bites ─────────────────────────────────────────────────────────────────────────────
def test_a_judge_stub_without_kwargs_raises_typeerror_and_marks_the_state_doc_not_ok(monkeypatch):
    monkeypatch.setattr(AUD, "judge", lambda r, F, fz=None: _ok_audit())     # the OLD stub shape (no **kw)
    gga = gga_store(fake_store())
    with pytest.raises(TypeError):
        AP.run_step(gga.shared, gga, _reads(("AAA", _aplus())), {"AAA": _Fr(BAR)}, NOW, S, alert_ctx={},
                    owner="o", dry=False, push_dry=False, strip=STRIP_OK)
    latest = gga.get_state(AP.LATEST_ID)
    assert latest["ok"] is False and latest["error"] == "TypeError"   # NEGATIVE: what `ok is True` catches


def test_a_typeerror_inside_the_step_never_reaches_gg5_errors_only_the_state_doc(monkeypatch):
    monkeypatch.setattr(AUD, "judge", lambda r, F, fz=None: _ok_audit())     # raises TypeError (ctx=)
    st = fake_store()
    gga = gga_store(st)
    deps = make_deps(rows={"GGA": IDT.snap_row(11.2, 8.0)}, load=IDT._load)[0]
    deps.audited_store = lambda s: gga
    deps.record_audited_status = Rec(True)
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["errors"] == []                                          # vacuous by design (run.py's fence)
    assert gga.get_state(AP.LATEST_ID) == dict(gga.get_state(AP.LATEST_ID), ok=False, error="TypeError")


# ── C1: alerts.refusal == run_pass's chain, branch by branch ──────────────────────────────────────────────────────
SAT = date(2026, 10, 17)


def _refusal_case(name):
    """-> (read, frames, now, session, preclaim) for one branch of the chain."""
    if name == "not_aplus_variant":
        return _aplus(variant="long_flag"), _Fr(BAR), NOW, S, False
    if name == "no_risk":
        return _aplus(trigger=2.0, stop=2.0), _Fr(BAR), NOW, S, False
    if name == "late":
        return _aplus(bar="2026-10-13 10:35"), _Fr(BAR), NOW, S, False
    if name == "claimed_before":
        return _aplus(bar="2026-10-13 10:35"), _Fr(BAR), NOW, S, True
    if name == "suppressed_closed":
        return _aplus(bar="2026-10-17 10:40"), _Fr("2026-10-17 10:40"), at(10, 41, d=SAT), SAT, False
    if name == "suppressed_premarket":
        return _aplus(bar="2026-10-13 08:05"), _Fr("2026-10-13 08:05"), at(8, 6), S, False
    if name == "suppressed_first15":
        return _aplus(bar="2026-10-13 09:40"), _Fr("2026-10-13 09:40"), at(9, 41), S, False
    return _aplus(), _Fr(BAR), NOW, S, False


@pytest.mark.parametrize("variant", ["gg5", "gga"])
@pytest.mark.parametrize("want", ["not_aplus_variant", "no_risk", "late", "claimed_before", "suppressed_closed",
                                  "suppressed_premarket", "suppressed_first15", None])
def test_refusal_returns_exactly_the_state_run_pass_records(variant, want):
    r, fr, now, session, preclaim = _refusal_case(want)
    st = fake_store() if variant == "gg5" else gga_store(fake_store())
    v = V.of(st)
    coll = st.alerts_coll()
    sym, setup = "AAA", r["setup"]
    key = AL.claim_key(session, sym, setup, v)
    if preclaim:
        coll.update_one({"_id": AL.shadow_key(session, sym, setup, v)},
                        {"$set": {"state": "shadow", "date": session.isoformat()}}, upsert=True)
    got = AL.refusal(dict(r), sym, r["entry_bar_t"], fr, now, session, {}, v, coll, closed=AL._closed_reason(now))
    counts = AL.run_pass({sym: {setup: dict(r)}}, {sym: fr}, now, session, store=st, owner="o", mode="shadow",
                         send=AP.refuse_send, ctx={})
    recorded = [k for k in REFUSALS if counts.get(k)]
    assert got == want
    assert recorded == ([want] if want else [])
    if want is None:
        assert counts["shadow"] == 1 and AL.shadow_key(session, sym, setup, v) in coll.docs
    elif want != "claimed_before":
        assert f"{key}#{want}" in coll.docs                             # the #state marker run_pass wrote
    else:
        assert not [k for k in coll.docs if "#" in k]                  # NEGATIVE: a repeat writes no marker


def test_refusal_closed_is_the_callers_once_per_pass_value():
    r, fr, now, session, _p = _refusal_case(None)
    coll = FakeColl()
    assert AL.refusal(r, "AAA", BAR, fr, now, session, {}, V.GG5, coll, closed=None) is None
    assert AL.refusal(r, "AAA", BAR, fr, now, session, {}, V.GG5, coll, closed="weekend") == "suppressed_closed"
    assert AL.refusal(dict(r, variant="x"), "AAA", BAR, fr, now, session, {}, V.GG5, coll,
                      closed="weekend") == "not_aplus_variant"          # the chain's ORDER: variant first


# ── C1: a bar 🚩 would refuse is never judged, recorded or given a slot ──────────────────────────────────────────
@pytest.mark.parametrize("bar,now,why", [("2026-10-13 08:05", at(8, 6), "suppressed_premarket"),
                                         ("2026-10-13 09:40", at(9, 41), "suppressed_first15")])
def test_premarket_and_first15_aplus_are_never_judged(monkeypatch, bar, now, why):
    calls: list = []
    _stub(monkeypatch, calls)
    gga = gga_store(fake_store())
    out, latest = _run(gga, _reads(("AAA", _aplus(bar=bar))), {"AAA": _Fr(bar)}, now=now)
    assert calls == []                                                  # never judged
    assert latest["n_unjudged"] == {why: 1}
    assert (gga.get_overlay(S, "AAA") or {}).get("setups") in (None, {})    # no overlay entry
    assert _held_ids(gga) == {} and _claims(gga) == {}                  # no marker, no claim
    assert latest["t1_slots_used"] == 0 and latest["n_held"] == 0 and latest["n_aplus_audited"] == 0
    assert f"{AL.claim_key(S, 'AAA', 'bull_flag', V.GGA)}#{why}" in _gga_docs(gga, ST.ALERTS)   # 🚩's own refusal row
    assert out["aplus_original"] == 1


def test_the_same_two_reads_on_a_1040_bar_are_judged(monkeypatch):
    calls: list = []
    _stub(monkeypatch, calls)
    gga = gga_store(fake_store())
    reads = _reads(("AAA", _aplus()), ("BBB", _aplus(setup="intraday_vcp")))
    _out, latest = _run(gga, reads, {"AAA": _Fr(BAR), "BBB": _Fr(BAR)})
    assert sorted((c[0], c[1]) for c in calls) == [("AAA", "bull_flag"), ("BBB", "intraday_vcp")]   # NEGATIVE
    assert latest["n_unjudged"] == {}
    assert gga.get_overlay(S, "AAA")["setups"]["bull_flag"]["aplus"] is True
    assert len(_claims(gga)) == 2 and latest["t1_slots_used"] == 2


def test_a_name_claimed_today_on_a_new_bar_is_unjudged_claimed_before(monkeypatch):
    calls: list = []
    _stub(monkeypatch, calls)
    gga = gga_store(fake_store())
    _run(gga, _reads(("AAA", _aplus())), {"AAA": _Fr(BAR)})
    claims1 = copy.deepcopy(_claims(gga))
    ov1 = copy.deepcopy(gga.get_overlay(S, "AAA"))
    assert len(claims1) == 1 and len(calls) == 1
    bar2 = "2026-10-13 10:45"
    _out, latest = _run(gga, _reads(("AAA", _aplus(bar=bar2))), {"AAA": _Fr(bar2)}, now=at(10, 46))
    assert len(calls) == 1                                              # NEGATIVE: never judged again
    assert latest["n_unjudged"] == {"claimed_before": 1}
    assert _claims(gga) == claims1 and _held_ids(gga) == {}             # no second record
    assert gga.get_overlay(S, "AAA")["setups"] == ov1["setups"]
    assert latest["t1_slots_used"] == 1                                 # the earlier claim keeps its slot


def test_aplus_original_is_audited_plus_held_plus_unjudged(monkeypatch):
    _stub(monkeypatch, fail_by_sym={"BBB": ["G1"]})
    gga = gga_store(fake_store())
    reads = _reads(("AAA", _aplus()), ("BBB", _aplus()), ("CCC", _aplus(trigger=2.0, stop=2.0)))
    out, latest = _run(gga, reads, {s: _Fr(BAR) for s in reads})
    assert out["aplus_original"] == 3 and out["aplus_audited"] == 1 and out["held"] == 1
    assert latest["n_unjudged"] == {"no_risk": 1}
    assert out["aplus_original"] == out["aplus_audited"] + out["held"] + sum(latest["n_unjudged"].values())


# ── C4: only a claimable survivor takes a slot ────────────────────────────────────────────────────────────────────
def test_a_no_risk_aplus_takes_no_slot(monkeypatch):
    calls: list = []
    _stub(monkeypatch, calls)
    gga = gga_store(fake_store())
    reads = _reads(("AAA", _aplus(trigger=2.0, stop=2.0)), ("BBB", _aplus()), ("CCC", _aplus()))
    _out, latest = _run(gga, reads, {s: _Fr(BAR) for s in reads})
    assert AUD.T1_DAILY_CAP == 2
    for s in ("BBB", "CCC"):
        a = gga.get_overlay(S, s)["setups"]["bull_flag"]
        assert a["aplus"] is True and "T1" in a["passed"]
    assert latest["t1_slots_used"] == 2 and latest["n_unjudged"] == {"no_risk": 1}
    assert gga.get_overlay(S, "AAA") is None                           # NEGATIVE: no overlay entry for AAA
    assert [c[0] for c in calls] == ["BBB", "CCC"]


# ── C3: T1 in 🚩's ring order ─────────────────────────────────────────────────────────────────────────────────────
def test_t1_holds_the_symbol_last_of_three_on_one_bar_and_flags_the_tie(monkeypatch):
    _stub(monkeypatch)
    gga = gga_store(fake_store())
    reads = _reads(("CCC", _aplus()), ("AAA", _aplus()), ("BBB", _aplus()))
    seen: list = []
    real = AL.run_pass
    monkeypatch.setattr(AL, "run_pass", lambda rs, *a, **k: seen.append(copy.deepcopy(rs)) or real(rs, *a, **k))
    _out, latest = _run(gga, reads, {s: _Fr(BAR) for s in reads})
    a = {s: gga.get_overlay(S, s)["setups"]["bull_flag"] for s in reads}
    assert a["AAA"]["aplus"] is True and a["BBB"]["aplus"] is True
    assert a["CCC"]["aplus"] is False and _fids(a["CCC"]) == ["T1"]
    assert a["CCC"]["values"]["T1"]["tie"] is True
    assert set(_claims(gga)) == {AL.shadow_key(S, s, "bull_flag", V.GGA) for s in ("AAA", "BBB")}
    held = _held_ids(gga)
    assert list(held) == [f"{AL.claim_key(S, 'CCC', 'bull_flag', V.GGA)}#{AUD.HELD_ROW_STATE}"]
    row = next(iter(held.values()))
    assert _fids(row["audit"]) == ["T1"] and row["audit"]["passed"] == [x.id for x in AUD.judge_rules()]
    assert set(row["audit"]) == {"passed", "failed", "values", "version", "frame", "rules", "admit"}   # MOVED 2026-11-09: + admit (K3S)
    assert row["audit"]["rules"][-1] == "T1"                            # T1 judged LAST
    served = seen[0]["CCC"]["bull_flag"]                                # what the tab serves as held
    assert served["state"] == AUD.HELD_STATE and [f["id"] for f in served["audit"]["failed"]] == ["T1"]
    assert latest["t1_slots_used"] == 2


def test_t1_on_three_bars_holds_the_latest_bar_not_the_alphabetically_first(monkeypatch):
    """Synthetic close stamps 10:36 / 10:38 / 10:40 (each the latest closed bar of its own name, all fresh at 10:41):
    🚩's ring order is the BAR first — the alphabetically-first name on the LATEST bar is the one held."""
    _stub(monkeypatch)
    gga = gga_store(fake_store())
    bars = {"AAA": "2026-10-13 10:40", "BBB": "2026-10-13 10:36", "CCC": "2026-10-13 10:38"}
    reads = _reads(*[(s, _aplus(bar=b)) for s, b in bars.items()])
    _out, latest = _run(gga, reads, {s: _Fr(b) for s, b in bars.items()})
    a = {s: gga.get_overlay(S, s)["setups"]["bull_flag"] for s in bars}
    assert a["AAA"]["aplus"] is False and _fids(a["AAA"]) == ["T1"]    # NEGATIVE: alphabetical order is not it
    assert a["AAA"]["values"]["T1"]["tie"] is False                     # no other survivor on its bar
    assert a["BBB"]["aplus"] is True and a["CCC"]["aplus"] is True
    assert latest["t1_slots_used"] == 2


def test_a_name_claimed_on_pass_one_keeps_its_slot_on_pass_two(monkeypatch):
    calls: list = []
    _stub(monkeypatch, calls)
    gga = gga_store(fake_store())
    reads = _reads(("AAA", _aplus()), ("BBB", _aplus()))
    _run(gga, reads, {s: _Fr(BAR) for s in reads})
    bar2 = "2026-10-13 10:45"
    reads2 = _reads(("AAA", _aplus(bar=bar2)), ("DDD", _aplus(bar=bar2)))
    _out, latest = _run(gga, reads2, {s: _Fr(bar2) for s in reads2}, now=at(10, 46))
    d = gga.get_overlay(S, "DDD")["setups"]["bull_flag"]
    assert d["aplus"] is False and _fids(d) == ["T1"]                   # the cap is the DAY's entries
    assert latest["n_unjudged"] == {"claimed_before": 1}                # AAA: claimed earlier — no new slot
    assert latest["t1_slots_used"] == 2
    assert [c[0] for c in calls].count("AAA") == 1


def test_a_read_held_by_another_rule_carries_no_t1_and_takes_no_slot(monkeypatch):
    _stub(monkeypatch, fail_by_sym={"AAA": ["G1"]})
    gga = gga_store(fake_store())
    reads = _reads(("AAA", _aplus()), ("BBB", _aplus()), ("CCC", _aplus()))
    _out, latest = _run(gga, reads, {s: _Fr(BAR) for s in reads})
    a = gga.get_overlay(S, "AAA")["setups"]["bull_flag"]
    assert _fids(a) == ["G1"] and "T1" not in a["rules"] and "T1" not in a["passed"]
    assert gga.get_overlay(S, "BBB")["setups"]["bull_flag"]["aplus"] is True
    assert gga.get_overlay(S, "CCC")["setups"]["bull_flag"]["aplus"] is True    # the held name freed its slot
    assert latest["t1_slots_used"] == 2


def test_a_claims_read_fault_holds_every_survivor_by_t1_fail_closed(monkeypatch):
    _stub(monkeypatch)
    gga = gga_store(fake_store())
    monkeypatch.setattr(gga, "alert_rows", lambda sessions: None)
    reads = _reads(("AAA", _aplus()), ("BBB", _aplus()))
    _out, latest = _run(gga, reads, {s: _Fr(BAR) for s in reads})
    for s in reads:
        a = gga.get_overlay(S, s)["setups"]["bull_flag"]
        assert a["aplus"] is False and a["failed"] == [{"id": "T1", "why": AUD.NONE_WHY["T1"]}]
    assert _claims(gga) == {} and latest["t1_slots_used"] == 0         # NEGATIVE: nothing rang in shadow
    assert "None" not in AUD.NONE_WHY["T1"]


# ── T4 from the pass's own strip (the real judge) ─────────────────────────────────────────────────────────────────
def _strip_into_step(monkeypatch, strip, seen=None):
    real = AP.run_step

    def rs(*a, **k):
        if seen is not None:
            seen.append(copy.deepcopy(k.get("strip")))
        if strip is not _KEEP:
            k["strip"] = strip
        return real(*a, **k)
    monkeypatch.setattr(AP, "run_step", rs)


_KEEP = object()


def test_run_pass_hands_the_strip_to_the_step(monkeypatch):
    seen: list = []
    _strip_into_step(monkeypatch, _KEEP, seen)
    _st, gga, _d, out = _scenario_one_pass(monkeypatch)
    assert seen == [out["strip"]] and seen[0]["best_change_pct"] == 40.0     # GGA +40.0 is the day's top runner
    assert gga.get_state(AP.LATEST_ID)["best_change_pct"] == 40.0


@pytest.mark.parametrize("strip,ok", [({"best_change_pct": 55.0, "best_symbol": "GGA"}, True),
                                      ({"best_change_pct": 40.0, "best_symbol": "GGA"}, False),
                                      (None, None)])
def test_t4_reads_the_strips_top_runner(monkeypatch, strip, ok):
    calls: list = []
    real = AUD.judge

    def spy(r, F, fz=None, **kw):
        calls.append(kw)
        return real(r, F, fz, **kw)
    monkeypatch.setattr(AUD, "judge", spy)
    _strip_into_step(monkeypatch, strip)
    _st, gga, _d, _o = _scenario_one_pass(monkeypatch)
    assert calls and calls[0]["ctx"]["best_change_pct"] == (strip or {}).get("best_change_pct")
    assert calls[0]["ctx"]["session"] == S
    a = gga.get_overlay(S, "GGA")["setups"]["bull_flag"]
    if ok is True:
        assert "T4" in a["passed"] and "T4" not in _fids(a)
        assert a["values"]["T4"]["fired"] is False
    else:
        f = [x for x in a["failed"] if x["id"] == "T4"]
        assert len(f) == 1 and "T4" not in a["passed"]
        if ok is False:
            assert a["values"]["T4"]["fired"] is True
        else:
            assert f[0]["why"] == AUD.NONE_WHY["T4"]                    # fail-closed: no number on the pass


# ── C2: the day's T4 count from the durable markers ───────────────────────────────────────────────────────────────
def _t4_stub(monkeypatch, extra_by_sym):
    """judge: T4 from ctx through the registry's own t4_pass; `extra_by_sym` adds other failed ids."""
    def j(r, F, fz=None, ctx=None, **kw):
        ids = list(extra_by_sym.get(r.get("symbol"), ()))
        if AUD.t4_pass((ctx or {}).get("best_change_pct")) is not True:
            ids.append("T4")
        return _ok_audit(r.get("frame") or "5m", tuple(ids))
    monkeypatch.setattr(AUD, "judge", j)


def test_t4_session_counts_fired_and_fired_alone_from_the_markers_idempotently(monkeypatch):
    _t4_stub(monkeypatch, {"BBB": ["G2"]})
    gga = gga_store(fake_store())
    quiet = {"best_change_pct": 40.0, "best_symbol": "AAA"}
    _o1, l1 = _run(gga, _reads(("AAA", _aplus())), {"AAA": _Fr(BAR)}, strip=quiet)
    assert l1["n_t4_fired_pass"] == 1 and l1["t4_session"] == {"fired": 1, "fired_alone": 1}
    bar2 = "2026-10-13 10:45"
    _o2, l2 = _run(gga, _reads(("BBB", _aplus(bar=bar2))), {"BBB": _Fr(bar2)}, now=at(10, 46), strip=quiet)
    assert l2["n_t4_fired_pass"] == 1
    assert l2["t4_session"] == {"fired": 2, "fired_alone": 1}
    assert l2["best_change_pct"] == 40.0
    _o3, l3 = _run(gga, _reads(("BBB", _aplus(bar=bar2))), {"BBB": _Fr(bar2)}, now=at(10, 46), strip=quiet)
    assert l3["t4_session"] == {"fired": 2, "fired_alone": 1}           # NEGATIVE: a re-run never double-counts
    assert len(_held_ids(gga)) == 2


def test_t4_session_read_fault_is_named_and_the_pass_stays_ok(monkeypatch):
    _t4_stub(monkeypatch, {})
    gga = gga_store(fake_store())
    monkeypatch.setattr(gga, "held_rows", lambda sessions: None)
    _o, latest = _run(gga, _reads(("AAA", _aplus())), {"AAA": _Fr(BAR)}, strip={"best_change_pct": 12.0})
    assert latest["t4_session"] == {"fired": None, "fired_alone": None, "read_fault": True}
    assert latest["n_t4_fired_pass"] == 1


def test_a_busy_day_fires_no_t4(monkeypatch):
    _t4_stub(monkeypatch, {})
    gga = gga_store(fake_store())
    _o, latest = _run(gga, _reads(("AAA", _aplus())), {"AAA": _Fr(BAR)}, strip={"best_change_pct": 40.01})
    assert latest["n_t4_fired_pass"] == 0 and latest["t4_session"] == {"fired": 0, "fired_alone": 0}   # NEGATIVE


# ── the identity world: GGA at +40.0 exactly → T4 holds every A+; GG5 byte-identical ──────────────────────────────
def test_identity_world_every_aplus_is_held_by_t4_and_the_goldens_stand(monkeypatch):
    made: dict = {}
    _patch_idt_deps(monkeypatch, _hook(made))
    stores, text = IDT.writes_text(monkeypatch)
    IDT._check(IDT.WRITES, text)
    IDT._check(IDT.BOARD, IDT.board_text(stores))
    assert len(made) == 2
    for gga in made.values():
        latest = gga.get_state(AP.LATEST_ID)
        assert latest["ok"] is True and latest["best_change_pct"] == 40.0
        judged = [a for d in _gga_docs(gga, ST.OVERLAY).values() for a in (d.get("setups") or {}).values()]
        assert judged and all("T4" in _fids(a) and a["aplus"] is False for a in judged)
        assert _claims(gga) == {}                                       # NEGATIVE: nothing rang in shadow
        assert latest["t4_session"]["fired"] == len(_held_ids(gga)) >= 1


# ── the audit on the shadow claim ─────────────────────────────────────────────────────────────────────────────────
def test_the_shadow_claim_is_settled_with_its_audit_once(monkeypatch):
    _stub(monkeypatch)
    gga = gga_store(fake_store())
    _run(gga, _reads(("AAA", _aplus())), {"AAA": _Fr(BAR)})
    sk = AL.shadow_key(S, "AAA", "bull_flag", V.GGA)
    claim = _gga_docs(gga, ST.ALERTS)[sk]
    assert set(claim["audit"]) == {"passed", "failed", "values", "version", "frame", "rules", "admit"}   # MOVED 2026-11-09
    assert claim["audit"]["admit"] is None                              # NEGATIVE: a 🚩 A+ is never admitted
    assert claim["audit"]["rules"][-1] == "T1" and "T1" in claim["audit"]["passed"]
    first = copy.deepcopy(claim["audit"])
    _stub(monkeypatch, fail_by_sym={"AAA": ["G1"]})
    bar2 = "2026-10-13 10:45"
    _run(gga, _reads(("AAA", _aplus(bar=bar2))), {"AAA": _Fr(bar2)}, now=at(10, 46))
    assert _gga_docs(gga, ST.ALERTS)[sk]["audit"] == first              # NEGATIVE: never overwritten


def test_a_claim_that_already_carries_an_audit_is_never_overwritten(monkeypatch):
    """A claim today's claims read cannot see (no `date` — so the name is judged) that already carries an audit: the
    pass's own _claim refuses (claimed_before) and the settle leaves the stored audit alone."""
    _stub(monkeypatch)
    gga = gga_store(fake_store())
    sk = AL.shadow_key(S, "AAA", "bull_flag", V.GGA)
    gga.alerts_coll().update_one({"_id": sk}, {"$set": {"state": "shadow", "audit": {"sentinel": 1}}}, upsert=True)
    out, _l = _run(gga, _reads(("AAA", _aplus())), {"AAA": _Fr(BAR)})
    assert out["claimed_before"] == 1
    assert _gga_docs(gga, ST.ALERTS)[sk]["audit"] == {"sentinel": 1}   # NEGATIVE: never overwritten


def test_on_demand_settles_nothing_and_claims_nothing(monkeypatch):
    _stub(monkeypatch)
    gga = gga_store(fake_store())
    _o, latest = _run(gga, _reads(("AAA", _aplus())), {"AAA": _Fr(BAR)}, push_dry=True)
    assert _gga_docs(gga, ST.ALERTS) == {}                              # NEGATIVE
    assert gga.get_overlay(S, "AAA")["setups"]["bull_flag"]["aplus"] is True


# ── the state doc ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_state_doc_carries_the_new_keys(monkeypatch):
    _stub(monkeypatch)
    gga = gga_store(fake_store())
    _o, latest = _run(gga, _reads(("AAA", _aplus())), {"AAA": _Fr(BAR)})
    assert {"best_change_pct", "best_symbol", "t1_slots_used", "n_t4_fired_pass", "t4_session", "n_unjudged",
            "rules", "exit_rules", "version"} <= set(latest)
    assert latest["rules"] == [r.id for r in AUD.filter_rules()] and "T1" in latest["rules"]
    assert latest["exit_rules"] == [r.id for r in AUD.exit_rules()] == ["T3", "T5"]
    assert not set(latest["exit_rules"]) & set(latest["rules"])        # NEGATIVE: an exit is never a filter
    assert latest["version"] == AUD.AUDIT_VERSION
    assert latest["best_change_pct"] == 55.0 and latest["best_symbol"] == "RUN"


def test_no_strip_reads_none_on_the_state_doc_never_a_number(monkeypatch):
    _stub(monkeypatch)
    gga = gga_store(fake_store())
    _o, latest = _run(gga, _reads(("AAA", _aplus())), {"AAA": _Fr(BAR)}, strip=None)
    assert latest["best_change_pct"] is None and latest["best_symbol"] is None
