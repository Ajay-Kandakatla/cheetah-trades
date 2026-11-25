"""⛔🔒 C1 — an ADDED SI / SSR / Reg SHO name is read, tagged and tracked, but never rung (SPEC sissr rev 2 §3.4–§3.5).

Ajay 2026-11-24 ~23:35 ET, verbatim: "Days past little bit like AKAN is what I am mainly looking for many were so
confident on SSR..". An off-list ⛔ / 🔒 name joins GG's pass (si_ssr_names.run_step) — and failed GG's own ≥25% scanner
rule doing so. So run.py hands the 🎯 A+, 🧪, 💧, 🔀 and 🩳🔀 engines the reads / frames WITHOUT it (the engines are
unchanged), and 🧠 tracks it (the Watch's stamp) but HOLDS it `si_ssr_add` at any volume. Ringing an added name is HIS
CALL #6. The REAL scanner, bars and detectors run on the fixture day; NEGATIVES are mandatory and named so. UNMEASURED.
"""
from __future__ import annotations

import copy
import json

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import audited_pass as AP
from chart_maps.gajjala import bars as B
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import high_si as HS
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import si_ssr_names as SSN
from chart_maps.gajjala import tab as GT
from short_interest import reg_sho as RSH
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_potential import OK_SEND, bf_armed, ctx_for, frame_at, seed
from tests.test_gajjala_run import NOW, PREV, PRIOR_1M, Rec, S, at, make_deps, minutes_from_5m, snap_row
from tests.test_gajjala_si_ssr_names_2026_11_24 import AKAN_TAG, reader_of, ssr_row
from tests.test_gajjala_store import fake_store


@pytest.fixture(autouse=True)
def _adds_on_for_the_add_machinery(monkeypatch):
    """2026-11-25: SSN.ADD_ON ships False (no TOTAL cap yet; his number). These tests exercise the add machinery as it
    runs once he turns adds on, so they switch it on here. The shipped-off state is pinned in
    test_gajjala_si_ssr_adds_off_2026_11_25.py."""
    from chart_maps.gajjala import si_ssr_names as _SSN
    monkeypatch.setattr(_SSN, "ADD_ON", True)


TODAY = S.isoformat()
FORMING_1M = minutes_from_5m(FX.bf_bars(entry=None), S, "10:00")


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    from chart_maps.gajjala import run_1m as R1
    monkeypatch.setattr(R1, "spawn_loop", lambda *a, **k: True)
    monkeypatch.setattr(HS, "si_blocks", lambda syms, *, today: {})               # never Mongo
    monkeypatch.setattr(RSH, "past_closeout_text", lambda run: (run or {}).get("_words"), raising=False)


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")


def rows_of(**extra):
    """GGA GG's own qualifier (+40%, 3M); AKAN an off-list ⛔ day-2 CS at $2.00 with 1.2M (+5.3%)."""
    rows = {"GGA": snap_row(11.2, 8.0), "AKAN": snap_row(2.00, 1.90, vol=1_200_000)}
    rows.update(extra)
    return rows


def deps_of(rows=None, *, ssr=None, wired=True, load=None, **kw):
    d, _snap, send, status = make_deps(rows=rows or rows_of(), load=load)
    if wired:
        d.si_ssr_names = reader_of({"AKAN": AKAN_TAG} if ssr is None else ssr)
    for k, v in kw.items():
        setattr(d, k, v)
    return d, send


def spies(monkeypatch):
    """Record what each push engine is handed (each still runs its real code, or is a recorder)."""
    seen: dict = {}
    real_al, real_pt = AL.run_pass, PT.run_pass

    def al(reads, frames, *a, **k):
        seen["al"] = (reads, frames)
        return real_al(reads, frames, *a, **k)

    def pt(reads, frames, *a, **k):
        seen["pt"] = (reads, frames, k)
        return real_pt(reads, frames, *a, **k)
    monkeypatch.setattr(AL, "run_pass", al)
    monkeypatch.setattr(PT, "run_pass", pt)
    monkeypatch.setattr(AP, "store_for", lambda st, deps: object())
    monkeypatch.setattr(AP, "run_step", lambda st, gga, reads, frames, *a, **k: seen.setdefault("ap", (reads, frames)))
    extra = {"vol_dried": Rec(lambda st, reads, frames, *a, **k: seen.setdefault("vd", (reads, frames)) and {}),
             "fade_cross": Rec(lambda reads, frames, *a, **k: seen.setdefault("fx", (reads, frames)) and {}),
             "high_si_cross": Rec(lambda st, frames, *a, **k: seen.setdefault("hx", frames) and {})}
    return seen, extra


# ── C1: the push engines never see an added name ──────────────────────────────────────────────────────────────────
def test_an_added_aplus_name_never_reaches_any_push_engine(monkeypatch, live):
    seen, extra = spies(monkeypatch)
    d, send = deps_of(**extra)
    st = fake_store()
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert out["status"] == "ok" and out["si_ssr"]["added"] == ["AKAN"]
    assert "AKAN:bull_flag" in out["aplus"] and "GGA:bull_flag" in out["aplus"]   # read, A+ on the board
    pushed = [a[1]["ticker"] for a, _k in send.calls]
    assert "GGA" in pushed and "AKAN" not in pushed                                 # 🎯 never rings the add
    for k in ("al", "ap", "vd", "fx"):
        reads, frames = seen[k]
        assert "AKAN" not in reads and "AKAN" not in frames and "GGA" in reads, k
    assert "AKAN" not in seen["hx"] and "GGA" in seen["hx"]
    pt_reads, pt_frames, pt_kw = seen["pt"]
    assert "AKAN" in pt_reads and pt_kw["si_ssr_hold"] == frozenset({"AKAN"})       # 🧠 tracks it, held
    assert out["si_ssr"]["push_held"] == 1 and out["counts"]["si_ssr_push_held"] == 1
    assert out["qualifiers"] == ["GGA"] and out["counts"]["qualifiers"] == 1        # GG's own list stays GG's


def test_NEGATIVE_with_no_add_the_push_engines_get_the_same_objects(monkeypatch):
    seen, extra = spies(monkeypatch)
    d, _send = deps_of(ssr={}, **extra)
    RUN.run_pass(NOW, store=fake_store(), deps=d)
    pt_reads, pt_frames, pt_kw = seen["pt"]
    for k in ("al", "ap", "vd", "fx"):
        assert seen[k][0] is pt_reads and seen[k][1] is pt_frames, k
    assert seen["hx"] is pt_frames and pt_kw["si_ssr_hold"] == frozenset()


def test_the_adds_are_read_after_gg_names(monkeypatch):
    order = []
    real = B.frames_for

    def ff(symbols, *a, **k):
        order.append(list(symbols))
        return real(symbols, *a, **k)
    monkeypatch.setattr(B, "frames_for", ff)
    d, _ = deps_of(rows_of(AAAA=snap_row(2.0, 1.9, vol=1_500_000)),
                   ssr={"AKAN": AKAN_TAG, "AAAA": ssr_row(TODAY, 1)})
    RUN.run_pass(NOW, store=fake_store(), deps=d)
    assert order[0][0] == "GGA" and set(order[0][1:]) == {"AAAA", "AKAN"}


def test_the_read_docs_carry_the_tag_and_the_pass_doc_the_block_without_its_tag_map():
    st = fake_store()
    d, _ = deps_of()
    RUN.run_pass(NOW, store=st, deps=d)
    ak = st.get_read(S, "AKAN")["ctx"]["si_ssr"]
    assert ak["lead"] == "⛔ SSR 10/12 · day 2" and ak["add"] is True and ak["keys"] == ["ssr_recent"]
    assert "si_ssr" not in st.get_read(S, "GGA")["ctx"]                              # untagged → no key
    blk = st.latest_pass()["si_ssr"]
    assert blk["added"] == ["AKAN"] and SSN.TAGS_KEY not in blk and blk["push_held"] == 1
    scan = {x["symbol"]: x["last"] for x in st.scan_docs([S])}
    assert scan["AKAN"]["source"] == SSN.SOURCE and "source" not in scan["GGA"]
    json.dumps(st.latest_pass()["si_ssr"], allow_nan=False)


# ── 🧠: tracked + stamped + held, then rings once as GG's own name ────────────────────────────────────────────────
def _pot_deps(**kw):
    return deps_of(load=lambda sym, day: PRIOR_1M.copy() if day == PREV else FORMING_1M.copy(), **kw)


def test_an_added_armed_potential_is_tracked_stamped_held_never_claimed():
    st = fake_store()
    seed(st)
    d, _ = _pot_deps()
    out = RUN.run_pass(at(10, 36), store=st, deps=d)
    pushed = [a[1]["ticker"] for a, _k in d.send_potential.calls]
    assert "GGA" in pushed and "AKAN" not in pushed
    doc = st.get_potential(S, "AKAN", "bull_flag")
    assert doc["si_ssr_add"] is True and doc["si_ssr"]["lead"] == "⛔ SSR 10/12 · day 2"
    assert doc["si_ssr"]["first_at_et"] == "10:36" and "push" not in doc
    assert [h["reason"] for h in doc["held"]] == list(PT.SI_SSR_HELD)
    ak = [x for x in st.potentials(S) if x["symbol"] == "AKAN"]
    assert out["potential"]["si_ssr_held"] == len(ak) >= 1                         # one hold per AKAN potential
    assert all(x["si_ssr_add"] is True and "push" not in x for x in ak)
    assert GT._track_row(doc)["push_text"] == PT.SI_SSR_HOLD_TEXT


def test_the_same_name_rings_once_when_it_becomes_gg_s_own_name():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    reads = {"AKAN": {"bull_flag": bf_armed()}}
    tagc = {"AKAN": dict(ctx_for(), si_ssr=SSN.tag_block("AKAN", {"ssr_recent": {"text": "⛔ x"}}, None, add=True))}

    def go(now, hold):
        return PT.run_pass(reads, {"AKAN": frame_at(now)}, now, S, store=st, ctx=tagc,
                           rows={"AKAN": {"volume": 2e6}}, send=send, owner="o", tape="rth", si_ssr_hold=hold)
    o1 = go(at(10, 6), frozenset({"AKAN"}))
    assert o1["si_ssr_held"] == 1 and send.calls == []
    o2 = go(at(10, 11), frozenset({"AKAN"}))                                         # still an add: still held
    assert o2["si_ssr_held"] == 1 and send.calls == []
    o3 = go(at(10, 16), frozenset())                                                 # GG's own name now, unbroken
    assert o3["pushed"] == 1 and len(send.calls) == 1
    o4 = go(at(10, 21), frozenset())
    assert o4["pushed"] == 0 and len(send.calls) == 1                                # K3: once
    assert st.get_potential(S, "AKAN", "bull_flag")["si_ssr_add"] is True             # insert-only, kept


def test_NEGATIVE_a_broken_structure_never_rings_after_the_hold_lifts():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    from tests.test_gajjala_potential import real_partials
    tagc = {"AKAN": dict(ctx_for(), si_ssr=SSN.tag_block("AKAN", None, None, add=True))}

    def go(now, read, hold):
        return PT.run_pass({"AKAN": {"bull_flag": read}}, {"AKAN": frame_at(now)}, now, S, store=st, ctx=tagc,
                           rows={}, send=send, owner="o", tape="rth", si_ssr_hold=hold)
    go(at(10, 6), bf_armed(), frozenset({"AKAN"}))
    go(at(10, 11), real_partials()["near_kiss"], frozenset({"AKAN"}))                # the structure broke
    go(at(10, 16), bf_armed(), frozenset())
    assert send.calls == []


def test_NEGATIVE_no_hold_set_means_no_count_key():
    st = fake_store()
    seed(st)
    out = PT.run_pass({"AAA": {"bull_flag": bf_armed()}}, {"AAA": frame_at(at(10, 6))}, at(10, 6), S, store=st,
                      ctx={"AAA": ctx_for()}, rows={}, send=Rec(OK_SEND), owner="o", tape="rth")
    assert tuple(out) == PT.COUNT_KEYS and PT.SI_SSR_COUNT_KEY not in out


# ── the step off / the open ───────────────────────────────────────────────────────────────────────────────────────
def _snap(st):
    doc = copy.deepcopy(st.latest_pass())
    doc.pop("lease", None)
    return json.dumps(doc, sort_keys=True, default=str)


def test_NEGATIVE_with_the_deps_off_nothing_carries_a_si_ssr_key(monkeypatch):
    seen, extra = spies(monkeypatch)
    st = fake_store()
    d, _ = deps_of(wired=False, **extra)
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert "si_ssr" not in out and "si_ssr" not in _snap(st)
    assert not [k for k in out["counts"] if k.startswith("si_ssr")]
    assert seen["pt"][2]["si_ssr_hold"] is None and "si_ssr_held" not in out["potential"]
    for x in st.reads(S):
        assert "si_ssr" not in x["ctx"], x["symbol"]
    for x in st.scan_docs([S]):
        assert x["last"].get("source") != SSN.SOURCE
    assert RUN.Deps().si_ssr_names is None and RUN.dry_deps().si_ssr_names is None
    assert RUN._cron_deps().si_ssr_names is SSN.default_reader


def test_NEGATIVE_an_on_open_pass_adds_nothing_and_still_tags(monkeypatch):
    st = fake_store()
    d, _ = deps_of()
    out = RUN.run_on_demand(NOW, store=st, deps=d)
    assert out["si_ssr"]["added"] == [] and out["si_ssr"]["queued"] == ["AKAN"] and out["si_ssr"]["on_open"] is True
    assert {x["symbol"] for x in st.scan_docs([S])} == {"GGA"}
    assert st.get_read(S, "AKAN") is None                                            # never listed, never read


def test_an_unwired_open_keeps_the_last_cron_tag():
    st = fake_store()
    RUN.run_pass(at(10, 36), store=st, deps=deps_of()[0])
    tag36 = st.get_read(S, "AKAN")["ctx"]["si_ssr"]
    RUN.run_on_demand(NOW, store=st, deps=deps_of(wired=False)[0])
    assert st.get_read(S, "AKAN")["ctx"]["si_ssr"] == tag36


def test_NEGATIVE_a_raising_reader_fails_the_step_not_the_pass():
    st = fake_store()

    def boom(now, session):
        raise RuntimeError("down")
    d, _ = deps_of()
    d.si_ssr_names = boom
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert out["status"] == "ok" and out["errors"] == [] and out["si_ssr"] == {"error": "RuntimeError"}
    assert out["counts"]["si_ssr_failed"] == 1 and st.get_read(S, "AKAN") is None
