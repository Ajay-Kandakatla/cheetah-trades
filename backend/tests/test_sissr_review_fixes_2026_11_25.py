"""⛔🔒🩳 sissr review fixes (2026-11-25) — three defects the verifier found on feat/gg-si-ssr-potentials-watch-2026-11-24.

1. ⚡ break watch: an ADDED ⛔🔒 name (`si_ssr_add`) reached store.break_watch_docs → a ⚡ shadow record (and a live ring
   if GAJJALA_BREAK_PUSH_MODE goes live) and a WATCH_MAX seat. An add failed GG's own scanner rule: it is held from
   every push (HIS CALL #6), so the query now drops it.
2. 🧠 title: the si_ssr lead sat in FRONT of "🧠 SYM", so a 119-char lead pushed the ticker off the lock screen. The
   ticker now leads; the lead follows it ("🧠 AKAN · ⛔ SSR … · 🩳 … · 🚩 Bull Flag — …"). Where it sits is HIS CALL.
3. fail-open: on an unreadable scan window run.py read this pass's rows only, so an add CARRIED from an earlier pass
   (listed, no row this pass) was handed to 🎯 / 🧠 / 💧 / 🧪 un-held. Its stored read doc's add flag now holds it.
NEGATIVES are mandatory and named so. UNMEASURED.
"""
from __future__ import annotations

import sys

import pytest

from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import si_ssr_names as SSN
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import break_watch as BW
from tests.test_gajjala_break_watch_2026_11_11 import DAY, bw, et, pdoc, seed  # noqa: F401  (bw is a fixture)
from tests.test_gajjala_potential import bf_armed
from tests.test_gajjala_run import S, at
from tests.test_gajjala_si_ssr_push_hold_2026_11_24 import _env, deps_of, spies  # noqa: F401  (_env is autouse)
from tests.test_gajjala_store import fake_store


@pytest.fixture(autouse=True)
def _adds_on_for_the_add_machinery(monkeypatch):
    """2026-11-25: SSN.ADD_ON ships False (no TOTAL cap yet; his number). These tests exercise the add machinery as it
    runs once he turns adds on, so they switch it on here. The shipped-off state is pinned in
    test_gajjala_si_ssr_adds_off_2026_11_25.py."""
    from chart_maps.gajjala import si_ssr_names as _SSN
    monkeypatch.setattr(_SSN, "ADD_ON", True)


LONG_LEAD = ("⛔ SSR 11/23 · day 2 · 🔒 day 6 past close-out · 🩳 32.4% short interest · High (float unconfirmed) · "
             "float on file is old")                                    # the verifier's 119-char probe lead


# ── 1. ⚡ break watch never follows an add ───────────────────────────────────────────────────────────────────────
def test_the_break_watch_query_drops_an_added_name(bw):
    seed(bw.st, pdoc("ADD", si_ssr_add=True, sv=5_000_000), pdoc("OK"))
    assert [d["symbol"] for d in bw.st.break_watch_docs(DAY)] == ["OK"]


def test_an_added_armed_heavy_volume_name_never_takes_a_watch_seat(bw):
    seed(bw.st, pdoc("ADD", si_ssr_add=True, sv=5_000_000), pdoc("OK"))
    BW.refresh(DAY, et(10, 6, 10))
    assert "ADD" not in BW.symbols() and "OK" in BW.symbols()


def test_the_filter_is_the_add_modules_own_field():
    assert SSN.TRACKER_ADD_FIELD == "si_ssr_add" and ST.SSN is SSN


def test_NEGATIVE_a_listed_or_unmarked_name_still_watches(bw):
    seed(bw.st, pdoc("FLS", si_ssr_add=False), pdoc("OK"), pdoc("TAG", si_ssr={"lead": "⛔ SSR 11/23 · day 2"}))
    assert sorted(d["symbol"] for d in bw.st.break_watch_docs(DAY)) == ["FLS", "OK", "TAG"]


def test_NEGATIVE_a_failing_coll_is_still_a_read_fault():
    from tests.test_gajjala_store import FakeColl
    st = fake_store(**{ST.POTENTIALS: FakeColl(fail=True)})
    assert st.break_watch_docs(DAY) is None


# ── 2. 🧠 title: the ticker leads ─────────────────────────────────────────────────────────────────────────────────
def _title(lead):
    return PT.compose("AKAN", "bull_flag", bf_armed(), "armed", {}, first_seen_et="10:06", tape="rth",
                      lead_text=lead)["title"]


def test_the_ticker_leads_even_behind_a_long_lead():
    t = _title(LONG_LEAD)
    assert len(LONG_LEAD) >= 110 and t.startswith("🧠 AKAN · ") and t.index("AKAN") < 10
    assert t == f"🧠 AKAN · {LONG_LEAD} · 🚩 Bull Flag — trigger armed · UNMEASURED"
    assert "🩳 32.4% short interest · High" in t                                   # his "mention of High SI" kept


def test_the_broker_flag_still_ends_the_title():
    from chart_maps.gajjala.tab import BROKER_FLAG_ICON
    p = PT.compose("AKAN", "bull_flag", bf_armed(), "armed", {}, first_seen_et="10:06", tape="rth",
                   lead_text="⛔ x", broker_text="no Fidelity")
    assert p["title"] == f"🧠 AKAN · ⛔ x · 🚩 Bull Flag — trigger armed · UNMEASURED · {BROKER_FLAG_ICON}"


@pytest.mark.parametrize("bad", [None, "", 3, ["⛔"]])
def test_NEGATIVE_no_lead_is_the_title_of_before(bad):
    assert _title(bad) == "🧠 AKAN · 🚩 Bull Flag — trigger armed · UNMEASURED"


# ── 3. fail-open: a carried add stays held when the window read fails ─────────────────────────────────────────────
def _window_fault(st):
    """The window read run.py makes for the add order / the hold raises; every other scan_docs call is untouched."""
    real = st.scan_docs

    def sd(days):
        f = sys._getframe(1)
        if len(list(days)) > 1 and f.f_code.co_filename.endswith("chart_maps/gajjala/run.py"):
            raise RuntimeError("window down")
        return real(days)
    st.scan_docs = sd


def _two_passes(monkeypatch, *, fault: bool):
    st = fake_store()
    RUN.run_pass(at(10, 36), store=st, deps=deps_of()[0])                           # pass 1: AKAN added
    assert SSN.is_add(st.get_read(S, "AKAN"))
    seen, extra = spies(monkeypatch)
    d, send = deps_of(ssr={}, **extra)                                               # pass 2: no AKAN row
    if fault:
        _window_fault(st)
    out = RUN.run_pass(at(10, 41), store=st, deps=d)
    return out, seen, send


def test_a_carried_add_is_held_when_the_window_read_fails(monkeypatch):
    out, seen, _send = _two_passes(monkeypatch, fault=True)
    assert out["status"] == "ok"
    pt_reads, _pf, pt_kw = seen["pt"]
    assert "AKAN" in pt_reads and pt_kw["si_ssr_hold"] == frozenset({"AKAN"})       # 🧠 tracks it, held
    for k in ("al", "ap", "vd", "fx"):
        reads, frames = seen[k]
        assert "AKAN" not in reads and "AKAN" not in frames and "GGA" in reads, k
    assert "AKAN" not in seen["hx"]


def test_the_window_ok_path_holds_it_the_same_way(monkeypatch):
    _out, seen, _send = _two_passes(monkeypatch, fault=False)
    assert seen["pt"][2]["si_ssr_hold"] == frozenset({"AKAN"})


def test_NEGATIVE_gg_s_own_carried_name_is_never_held_by_the_fault(monkeypatch):
    _out, seen, _send = _two_passes(monkeypatch, fault=True)
    assert "GGA" not in seen["pt"][2]["si_ssr_hold"] and "GGA" in seen["al"][0]


def test_NEGATIVE_the_fallback_is_not_consulted_when_the_window_reads(monkeypatch):
    monkeypatch.setattr(RUN, "_carried_adds", lambda *a, **k: (_ for _ in ()).throw(AssertionError("never")))
    out, _seen, _send = _two_passes(monkeypatch, fault=False)
    assert out["status"] == "ok"


class _Reads:
    def __init__(self, docs, boom=()):
        self.docs, self.boom = docs, set(boom)

    def get_read(self, session, s):
        if s in self.boom:
            raise RuntimeError("x")
        return self.docs.get(s)


def test_carried_adds_reads_the_read_doc_flag_only_for_names_without_a_row():
    add = {"ctx": {"si_ssr": {"add": True}}}
    st = _Reads({"AKAN": add, "ROW": add, "GGA": {"ctx": {}}})
    rows = [{"symbol": "row", "source": "scanner"}]
    assert RUN._carried_adds(st, S, ["AKAN", "ROW", "GGA", "NONE"], rows) == {"AKAN"}


@pytest.mark.parametrize("doc", [None, {}, {"ctx": None}, {"ctx": {"si_ssr": {"add": False}}},
                                 {"ctx": {"si_ssr": {"add": "yes"}}}, "junk"])
def test_NEGATIVE_a_non_add_read_doc_is_never_held(doc):
    assert RUN._carried_adds(_Reads({"X": doc}), S, ["X"], []) == set()


def test_NEGATIVE_a_raising_read_is_not_an_add_and_never_raises():
    assert RUN._carried_adds(_Reads({}, boom={"X"}), S, ["X"], None) == set()
    assert RUN._carried_adds(_Reads({}), S, None, None) == set()
