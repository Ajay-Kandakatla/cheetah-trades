"""⛔🔒🩳 🧠 for GG's own TAGGED names — the one-time stamp, the title lead, the unchanged gate (SPEC sissr rev 2 §3.5).

Ajay 2026-11-24 ~23:20 ET, verbatim: "Then potentials to be alerts sooner - add them to watch list and give them a time
stamp of the day". A name GG already lists and that carries a ⛔ / 🔒 / 🩳 tag (ctx["si_ssr"], run.py) rings through the
UNCHANGED 🧠 gate — the same minute as before — with its source LEADING the title ("⛔ SSR 11/23 · day 2 · 🧠 AKAN · …").
The tracker doc is stamped ONCE (`si_ssr`) at the first pass where the name is tagged AND a potential: the Watch's day
stamp. NEGATIVES are mandatory and named so: building, not a potential, one ring per name, closed day / pre-open, the
open, an unreadable tracker, a raising sender, NaN and an untagged compose. UNMEASURED.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
from datetime import timezone
from pathlib import Path

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import si_ssr_names as SSN
from chart_maps.gajjala import tab as GT
from tests.test_gajjala_potential import (LABOR_DAY, OK_SEND, Rec, S, at, bf_armed, ctx_for, frame_at, kf_building,
                                          seed)
from tests.test_gajjala_store import fake_store

ROOT = Path(__file__).resolve().parents[1]
AKAN_LEAD = "⛔ SSR 10/12 · day 2"


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def tag(lead=AKAN_LEAD, keys=("ssr_recent",), *, add=False, text=None, **kw):
    """The ctx tag run.py stores (si_ssr_names.tag_block's shape)."""
    t = SSN.tag_block("AKAN", {k: {"text": lead if i == 0 else f"{k} words", "day_n": 2, "triggered_on": "2026-10-12"}
                               for i, k in enumerate(keys) if k != "hsi"},
                      {"text": lead} if "hsi" in keys else None, add=add)
    if text is not None:
        t["text"] = text
    t.update(kw)
    return t


def go(st, now, reads, *, tags=None, send=None, dry=False, hold=None, session=None):
    session = session or now.astimezone(PT.ET).date()
    ctx = {s: dict(ctx_for(), **({"si_ssr": tags[s]} if tags and s in tags else {})) for s in reads}
    return PT.run_pass(reads, {s: frame_at(now) for s in reads}, now, session, store=st, ctx=ctx,
                       rows={s: {"volume": 2_000_000, "price": 11.2} for s in reads}, send=send,
                       owner="owner@example.com", dry=dry, tape="rth", si_ssr_hold=hold)


def doc(st, sym="AKAN", setup="bull_flag", d=S):
    return st.get_potential(d, sym, setup)


# ── POSITIVE: a listed tagged name ────────────────────────────────────────────────────────────────────────────────
def test_an_armed_listed_tagged_name_claims_once_then_sends_with_the_lead_first():
    st = fake_store()
    seed(st)
    order = []
    real_claim = st.claim_potential_push
    st.claim_potential_push = lambda _id, f: order.append("claim") or real_claim(_id, f)
    send = Rec(OK_SEND)
    send_rec = lambda o, p: order.append("send") or send(o, p)                     # noqa: E731
    out = go(st, at(10, 6), {"AKAN": {"bull_flag": bf_armed()}}, tags={"AKAN": tag()}, send=send_rec)
    assert order == ["claim", "send"] and out["pushed"] == 1 and len(send.calls) == 1
    (_o, p), _ = send.calls[0]
    plain = PT.compose("AKAN", "bull_flag", bf_armed(), "armed", {}, first_seen_et="10:06", tape="rth")
    # WIDENED 2026-11-25 (review: the ticker leads so the lock screen shows it; the lead follows — HIS CALL)
    assert p["title"] == plain["title"].replace("🧠 AKAN · ", f"🧠 AKAN · {AKAN_LEAD} · ", 1)
    assert p["title"] == "🧠 AKAN · ⛔ SSR 10/12 · day 2 · 🚩 Bull Flag — trigger armed · UNMEASURED"
    assert AKAN_LEAD not in p["body"]                                               # one source: the title only
    assert doc(st)["push"]["state"] == "pushed" and "si_ssr_held" not in out        # no hold set handed → no key


def test_the_stamp_is_the_pass_clock_and_carries_the_tag_once():
    st = fake_store()
    seed(st)
    go(st, at(10, 6), {"AKAN": {"bull_flag": bf_armed()}}, tags={"AKAN": tag()}, send=Rec(OK_SEND))
    stamp = doc(st)["si_ssr"]
    assert stamp["first_at"] == at(10, 6).astimezone(timezone.utc) and stamp["first_at_et"] == "10:06"
    assert (stamp["first_kind"], stamp["setup"], stamp["session"]) == ("armed", "bull_flag", S.isoformat())
    assert stamp["keys"] == ["ssr_recent"] and stamp["lead"] == AKAN_LEAD and stamp["glyphs"] == "⛔"
    assert stamp["ssr_day"] == 2 and stamp["potential_first_seen_et"] == "10:06"
    assert "add" not in stamp and "si_ssr_add" not in doc(st)                       # a listed name: no add marker


def test_the_stamp_names_the_earlier_potential_time_and_a_second_pass_never_rewrites_it():
    st = fake_store()
    seed(st)
    go(st, at(10, 1), {"AKAN": {"kiss_fly": kf_building()}}, send=Rec(OK_SEND))      # untagged potential first (C4)
    assert "si_ssr" not in doc(st, setup="kiss_fly")
    go(st, at(10, 6), {"AKAN": {"kiss_fly": kf_building()}}, tags={"AKAN": tag()}, send=Rec(OK_SEND))
    s1 = dict(doc(st, setup="kiss_fly")["si_ssr"])
    assert s1["first_at_et"] == "10:06" and s1["potential_first_seen_et"] == "10:01"
    go(st, at(10, 11), {"AKAN": {"kiss_fly": kf_building()}},
       tags={"AKAN": tag("🔒 day 9 past close-out", ("sho_past",))}, send=Rec(OK_SEND))
    assert doc(st, setup="kiss_fly")["si_ssr"] == s1                                # written ONCE


# ── NEGATIVES ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_building_is_held_building_and_still_stamped():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    out = go(st, at(10, 6), {"AKAN": {"kiss_fly": kf_building()}}, tags={"AKAN": tag()}, send=send)
    assert send.calls == [] and out["building_held"] == 1
    d = doc(st, setup="kiss_fly")
    assert [h["reason"] for h in d["held"]] == list(PT.BUILDING_HELD) and d["si_ssr"]["first_kind"] == "building"


def test_NEGATIVE_not_a_potential_or_a_tag_with_no_key_writes_no_stamp():
    st = fake_store()
    seed(st)
    from tests.test_gajjala_potential import bf_no_pullback
    go(st, at(10, 6), {"AKAN": {"bull_flag": bf_no_pullback()}}, tags={"AKAN": tag()}, send=Rec(OK_SEND))
    assert doc(st) is None
    go(st, at(10, 6), {"BBB": {"bull_flag": bf_armed()}}, tags={"BBB": SSN.tag_block("BBB", None, None, add=False)
                                                                      or {"keys": [], "lead": None}},
       send=Rec(OK_SEND))
    assert "si_ssr" not in doc(st, "BBB")


def test_NEGATIVE_a_name_that_already_rang_today_is_name_held():
    st = fake_store()
    seed(st)
    go(st, at(10, 1), {"AKAN": {"bull_flag": bf_armed()}}, send=Rec(OK_SEND))      # 🧠 rang on 🚩 before the tag
    send = Rec(OK_SEND)
    from tests.test_gajjala_potential import one_per_setup
    hf = one_per_setup()["horizontal_fade"]
    hf["ready"] = True
    out = go(st, at(10, 6), {"AKAN": {"horizontal_fade": hf}}, tags={"AKAN": tag()}, send=send)
    assert send.calls == [] and out["name_held"] == 1


@pytest.mark.parametrize("now", [at(10, 6, d=LABOR_DAY), at(3, 59)], ids=["closed_day", "pre_open"])
def test_NEGATIVE_a_closed_day_or_03_59_never_rings(now):
    st = fake_store()
    seed(st, d=now.astimezone(PT.ET).date())
    send = Rec(OK_SEND)
    out = go(st, now, {"AKAN": {"bull_flag": bf_armed()}}, tags={"AKAN": tag()}, send=send)
    assert send.calls == [] and out["pushed"] == 0
    d = doc(st, d=now.astimezone(PT.ET).date())
    assert d is None or "push" not in d


def test_NEGATIVE_the_open_is_dry_no_claim_no_send_no_tracker_write():
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    out = go(st, at(10, 6), {"AKAN": {"bull_flag": bf_armed()}}, tags={"AKAN": tag()}, send=send, dry=True)
    assert send.calls == [] and out["dry"] == 1 and doc(st) is None


def test_NEGATIVE_an_unreadable_tracker_does_nothing():
    st = fake_store()
    st.potentials = lambda session: None
    send = Rec(OK_SEND)
    out = go(st, at(10, 6), {"AKAN": {"bull_flag": bf_armed()}}, tags={"AKAN": tag()}, send=send)
    assert send.calls == [] and out["failed"] == 1 and "tracked_today" not in out and doc(st) is None


def test_NEGATIVE_a_raising_sender_is_failed_and_the_claim_is_kept():
    st = fake_store()
    seed(st)
    out = go(st, at(10, 6), {"AKAN": {"bull_flag": bf_armed()}}, tags={"AKAN": tag()},
             send=Rec(RuntimeError("apns down")))
    assert out["failed"] == 1 and out["pushed"] == 0
    assert doc(st)["push"]["state"] == "failed" and doc(st)["si_ssr"]["lead"] == AKAN_LEAD


def test_NEGATIVE_nan_in_a_tag_is_never_stored_as_nan():
    st = fake_store()
    seed(st)
    go(st, at(10, 6), {"AKAN": {"bull_flag": bf_armed()}}, tags={"AKAN": tag(ssr_day=float("nan"))},
       send=Rec(OK_SEND))
    stamp = doc(st)["si_ssr"]
    assert stamp["ssr_day"] is None
    json.dumps({k: v for k, v in stamp.items() if k != "first_at"}, allow_nan=False)


def test_NEGATIVE_an_untagged_compose_is_byte_identical():
    r = bf_armed()
    base = PT.compose("AAA", "bull_flag", r, "armed", {"float_text": "Float 3.1M"}, first_seen_et="10:06", tape="rth")
    for kw in ({}, {"lead_text": None}, {"lead_text": ""}, {"si_ssr_text": None}, {"lead_text": None, "si_ssr_text": ""}):
        assert json.dumps(PT.compose("AAA", "bull_flag", r, "armed", {"float_text": "Float 3.1M"},
                                     first_seen_et="10:06", tape="rth", **kw), sort_keys=True) == json.dumps(
            base, sort_keys=True), kw
    assert base["title"] == "🧠 AAA · 🚩 Bull Flag — trigger armed · UNMEASURED"


def test_a_two_source_tag_puts_every_source_in_the_title():
    # WIDENED 2026-11-25 (Ajay ~00:25 ET "I do need a mention of High SI stock when alerting for potential though.."):
    # the title lead is EVERY source's words (potential.title_lead), so the second source moved from the body to the
    # title — pinned in full in test_gajjala_si_ssr_title_hsi_2026_11_25.py.
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    t = tag("🔒 day 6 past close-out", ("sho_past", "ssr_today"))
    go(st, at(10, 6), {"AKAN": {"bull_flag": bf_armed()}}, tags={"AKAN": t}, send=send)
    (_o, p), _ = send.calls[0]
    assert p["title"].startswith("🧠 AKAN · " + t["text"] + " · 🚩") and t["text"] == "🔒 day 6 past close-out · ssr_today words"
    assert t["text"] not in p["body"]


# ── guards ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_tracker_marker_literal_is_one_name():
    assert PT.SI_SSR_HELD == (SSN.TRACKER_ADD_FIELD,) and PT.SI_SSR_ADD_FLAG == SSN.ADD_FLAG
    assert PT.SI_SSR_TAG_KEY == SSN.SOURCE
    assert PT.ADD_HELD == PT.TRADER_HELD + PT.PROMO_HELD + PT.SI_SSR_HELD
    assert PT.SI_SSR_HOLD_TEXT == "held: added ⛔🔒 name — not on GG's list"
    assert PT.SI_SSR_COUNT_KEY not in PT.COUNT_KEYS and not set(PT.SI_SSR_HELD) & set(PT.HELD_WORDS)


@pytest.mark.parametrize("name", ["alerts.py", "potential.py", "tab.py", "ledger.py"])
def test_NEGATIVE_the_gates_and_the_board_import_no_ssr(name):
    tree = ast.parse((ROOT / "chart_maps" / "gajjala" / name).read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            assert "ssr" not in (n.module or "") and all("ssr" not in a.name for a in n.names), (name, ast.unparse(n))
        elif isinstance(n, ast.Import):
            assert all("ssr" not in a.name for a in n.names), (name, ast.unparse(n))


def test_the_engines_the_c1_hold_never_edits_are_byte_unchanged():
    """Recorded on the untouched tree (origin/main 5dec3c6b / 7540094b) BEFORE any edit of WP be-pass.
    WIDENED 2026-11-27 (spec gg-like §3.6, suite refix): alerts.run_pass gains the `gg_like` kwarg + one
    `base.update(_gl_fields(...))` line (the 🧘 block frozen on the claim, never a gate). ADDED-only: undoing those lines
    reproduces the old d2ded91a… (tests/test_gajjala_gg_like_suite_2026_11_27.py). Every other engine here UNCHANGED."""
    from chart_maps.gajjala import audited_pass as AP
    from chart_maps.gajjala import stages as SG
    from chart_maps.gajjala import vol_dried as VD
    pinned = {
        "potential.potential_kind": (PT.potential_kind,
                                     "ac772217dc447021e13cec40c418c5d8f06cdc0790efac2ea98ae396348ac3d9"),
        "potential.eligible": (PT.eligible, "819f8d4f8eed7cd2f03a22a5f582e0b97cfa707a9bee2e6de69a48b53193e107"),
        "alerts.run_pass": (AL.run_pass, "e3bd70e8dc89477f2f3b8868baa135280e40a3ad7715a70c6a5812d8abb3a6fc"),
        "stages.steps": (SG.steps, "73110327d1518ea04868e97cdcd58f7b86f5e960c416a3d047b0781058c3f291"),
        "vol_dried.run_step": (VD.run_step, "ac3ab4eb6cdb0ae835025e55a19387c0f52c4d4ce7ee8984241d69dc4ad541b8"),
        "audited_pass.run_step": (AP.run_step, "61f04fff612f0558a040d6e5b571d3542d893cea972d4a98d8cddd792084f120"),
    }
    for name, (fn, sha) in pinned.items():
        assert hashlib.sha256(inspect.getsource(fn).encode()).hexdigest() == sha, name


def test_the_break_watch_is_not_live_or_skips_added_names():
    """§7 #13 — ⚡ reads today's armed 🧠 trackers. Shadow today, so an added name's armed plan is never pushed by it.
    This FAILS LOUD the day ⚡ goes live without excluding `si_ssr_add` trackers (HIS CALL #13)."""
    from chart_maps.gajjala import break_watch as BW
    src = Path(BW.__file__).read_text(encoding="utf-8")
    assert GC.GAJJALA_BREAK_PUSH_MODE != "live" or SSN.TRACKER_ADD_FIELD in src
    assert BW.mode() in ("off", "shadow") or SSN.TRACKER_ADD_FIELD in src
