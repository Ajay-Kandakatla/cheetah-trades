"""🧘 GG-like calm check — the pass / ring / board wiring (SPEC gglike REV 2 §3.6, WP be-serve-board, 2026-11-27).

Ajay 2026-11-27: "Yes please, I think we are in bear market and looking at bad setups and make them work, forcing them
to work honestly... Can you update them please.. find calmer and better setups.. Continue to track the runners we might
evolve and find patterns in the current runners too but I want to make sure we are finding similar setups to Gajjala".

The engine (chart_maps/gajjala/gg_like.py) is another package's; this file pins ONLY the wiring:
  run.py      — `_gg_like_of` stores `gg_like` on the read doc (the key only when a setup was judged) and hands the
                {SYM: {setup: block}} map to BOTH push gates only when it is non-empty.
  alerts.py   — `_gl_fields` freezes the block on the A+ claim / refusal / shadow record only at THIS entry bar.
  potential.py — `_gl_claim` freezes the block on the 🧠 claim only at THIS read's as_of bar.
  tab.py      — ONE `_soft("gg like", GL.tag, …, pots=pot_docs)` on the five setup subs + 🧠 (GG5) only.
The day is tests/test_gajjala_run.py's (GGA forming at 10:31 → 🧠, GGA A+ at 10:41, GGB forming); the two-pass scenario
and the board recipe are tests/test_gajjala_variant_gg5_identity.py's. NEGATIVES: a faulted engine leaves every write
byte-equal to the pass with the keys stripped; another entry / as_of bar freezes nothing; dry / on-open / held write
none; nothing is reordered or hidden server-side; ☀️ 🌙 📋 🏁 playbook 🧪 1-minute boards carry no key; a stale stored
block is recomputed.
"""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import re

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import gg_like as GL
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.gg_feed_pin import feed_pinned
from tests.test_gajjala_run import NOW, S, T1, at, make_deps, snap_row
from tests.test_gajjala_store import fake_store
from tests.test_gajjala_variant_gg5_identity import _dump, _plain, scenario

BOARD_AT = at(10, 42)
CARD_SUBS = tuple(GC.SETUPS) + (GC.POTENTIAL_SUB,)


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture(autouse=True)
def _no_1m_spawn(monkeypatch):
    from chart_maps.gajjala import run_1m as R1
    monkeypatch.setattr(R1, "spawn_loop", lambda *a, **k: True)


def _strip(o):
    """Every `gg_like` key removed, at any depth (dict keys only)."""
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if k != "gg_like"}
    if isinstance(o, list):
        return [_strip(v) for v in o]
    return o


def _has_key(o, key="gg_like") -> bool:
    if isinstance(o, dict):
        return key in o or any(_has_key(v, key) for v in o.values())
    if isinstance(o, list):
        return any(_has_key(v, key) for v in o)
    return False


def _json(o):
    return json.loads(json.dumps(_plain(o), ensure_ascii=False, sort_keys=True))


def _raise(*a, **k):
    raise RuntimeError("engine down")


def _seeded():
    st = fake_store()
    assert st.upsert_potential(ST.potential_key(S, "SEED", "kiss_fly"),
                               {"date": S.isoformat(), "symbol": "SEED", "setup": "kiss_fly"}, {"at": at(4, 6)})
    return st


def _no_key_read(sym):
    """deps.read_all that turns every setup of `sym` into state "none" (no judged read)."""
    def read_all(frames, ctx):
        out = RUN._read_all(frames, ctx)
        if ctx.get("symbol") == sym:
            return {k: dict(r or {}, state="none") for k, r in out.items()}
        return out
    return read_all


def _blocks_with(field, value):
    """GL.doc_blocks with every block's `field` replaced — a block of another bar."""
    real = GL.doc_blocks

    def doc_blocks(doc, v=None):
        return {k: dict(b, **{field: value}) for k, b in (real(doc) or {}).items()}
    return doc_blocks


# ── run.py — the pass stores the block ────────────────────────────────────────────────────────────────────────────
def test_the_pass_stores_gg_like_on_the_read_doc_equal_to_doc_blocks_of_the_stored_doc(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    st = fake_store()
    deps, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0), "GGB": snap_row(11.0, 8.0)})
    deps.read_all = _no_key_read("GGB")
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["ran"] and out["status"] == "ok" and out["errors"] == []
    doc = st.get_read(S, "GGA")
    assert doc["setups"]["bull_flag"]["state"] == "aplus"
    assert "bull_flag" in doc["gg_like"]
    bare = {k: v for k, v in doc.items() if k != "gg_like"}
    assert doc["gg_like"] == GL.doc_blocks(bare)
    assert set(doc["gg_like"]) <= set(GC.SETUPS)
    for k, blk in doc["gg_like"].items():
        assert GL.from_stamp(blk) is not None and blk["setup"] == k
        assert doc["setups"][k]["state"] in GT.TILE_STATES
    # NEGATIVE: a name read this pass with no judged setup carries NO key (never {} or a default verdict)
    gb = st.get_read(S, "GGB")
    assert gb is not None and all(r["state"] == "none" for r in gb["setups"].values())
    assert "gg_like" not in gb
    # NEGATIVE: nothing goes into the ctx the push engines read
    assert not _has_key(doc["ctx"])


def test_NEGATIVE_a_raising_engine_adds_no_key_and_moves_no_other_write(monkeypatch):
    """The pass with the engine faulted == the real pass with every gg_like key stripped: status, counts, every write,
    every payload sent and every /alerts row (both modes). So no kwarg reaches either push gate: the claim and the
    🧠 push are byte-equal to today's, and compose's payload never carries the block."""
    real = {}
    for mode in ("live", "shadow"):
        _st, real[mode] = scenario(mode, monkeypatch)
    assert _has_key(real["live"]["writes"])                                # the real pass DID add keys
    monkeypatch.setattr(GL, "doc_blocks", _raise)
    for mode in ("live", "shadow"):
        st, faulted = scenario(mode, monkeypatch)
        assert not _has_key(faulted)                                       # no read doc, claim or push carries it
        assert all(p["status"] == "ok" and p["errors"] == [] for p in faulted["passes"])
        assert _dump(faulted) == _dump(_strip(real[mode])), mode
        for d in st.coll(ST.READS).docs.values():
            assert "gg_like" not in d
    # the payloads the senders were handed never carry the block (compose never reads it)
    assert not _has_key(real["live"]["sent"]) and not _has_key(real["live"]["sent_potential"])


def test_NEGATIVE_an_engine_that_returns_nothing_passes_no_kwarg_to_either_gate(monkeypatch):
    seen = {"al": [], "pt": []}
    al_run, pt_run = AL.run_pass, PT.run_pass

    def al_spy(*a, **k):
        seen["al"].append("gg_like" in k)
        return al_run(*a, **k)

    def pt_spy(*a, **k):
        seen["pt"].append("gg_like" in k)
        return pt_run(*a, **k)

    monkeypatch.setattr(AL, "run_pass", al_spy)
    monkeypatch.setattr(PT, "run_pass", pt_spy)
    monkeypatch.setattr(GL, "doc_blocks", lambda doc, v=None: {})
    RUN.run_pass(NOW, store=fake_store(), deps=make_deps()[0])
    assert seen == {"al": [False], "pt": [False]}
    monkeypatch.setattr(GL, "doc_blocks", lambda doc, v=None: None)
    seen["al"].clear(), seen["pt"].clear()
    RUN.run_pass(NOW, store=fake_store(), deps=make_deps()[0])           # a non-dict answer → {} → no kwarg
    assert seen == {"al": [False], "pt": [False]}
    monkeypatch.undo()
    monkeypatch.setattr(AL, "run_pass", al_spy)
    monkeypatch.setattr(PT, "run_pass", pt_spy)
    seen["al"].clear(), seen["pt"].clear()
    RUN.run_pass(NOW, store=fake_store(), deps=make_deps()[0])           # the real engine judged GGA → kwarg on both
    assert seen == {"al": [True], "pt": [True]}


def test_NEGATIVE_a_check_fault_is_logged_once_per_pass(monkeypatch, caplog):
    import logging
    monkeypatch.setattr(GL, "doc_blocks", _raise)
    logged: dict = {}
    with caplog.at_level(logging.WARNING, logger="chart_maps.gajjala.run"):
        assert RUN._gg_like_of({}, "AAA", logged) == {}
        assert RUN._gg_like_of({}, "BBB", logged) == {}
        assert RUN._gg_like_of({}, "CCC", logged) == {}
    assert len([r for r in caplog.records if "gg like" in r.getMessage()]) == 1
    # through a real pass: three names faulted, ONE log line, the pass still ok
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="chart_maps.gajjala.run"):
        out = RUN.run_pass(NOW, store=fake_store(), deps=make_deps(
            rows={"GGA": snap_row(11.2, 8.0), "GGB": snap_row(11.0, 8.0)})[0])
    assert out["status"] == "ok" and out["errors"] == []
    assert len([r for r in caplog.records if "gg like" in r.getMessage()]) == 1


# ── alerts.py — frozen on the A+ claim at THIS entry bar ────────────────────────────────────────────────────────────
def test_the_aplus_claim_carries_the_block_of_its_own_entry_bar(monkeypatch):
    st, out = scenario("live", monkeypatch)
    claim = st.alerts_coll().docs["GG:2026-10-13|GGA|bull_flag"]
    read = st.get_read(S, "GGA")
    assert claim["gg_like"]["entry_bar_t"] == claim["entry_bar_t"] == "2026-10-13 10:40"
    assert claim["gg_like"] == read["gg_like"]["bull_flag"]               # the pass's block, frozen
    assert claim["state"] == "pushed"                                      # the settle never removed it
    assert GL.from_stamp(claim["gg_like"]) is not None
    # the shadow record carries it too (base is shared by claim / refusal / shadow)
    st2, _o = scenario("shadow", monkeypatch)
    sh = [d for d in st2.alerts_coll().docs.values() if d.get("state") == "shadow"]
    assert sh and all(d["gg_like"]["entry_bar_t"] == d["entry_bar_t"] for d in sh)
    assert not _has_key(sh[0]["would_push"])                              # compose never reads it


def test_NEGATIVE_a_block_of_another_entry_bar_is_not_frozen(monkeypatch):
    monkeypatch.setattr(GL, "doc_blocks", _blocks_with("entry_bar_t", "2026-10-13 09:55"))
    st, out = scenario("live", monkeypatch)
    claim = st.alerts_coll().docs["GG:2026-10-13|GGA|bull_flag"]
    assert "gg_like" in st.get_read(S, "GGA")                              # stored on the read doc …
    assert "gg_like" not in claim                                          # … never frozen on a ring of another bar
    assert claim["state"] == "pushed"


def test_gl_fields_unit(monkeypatch):
    st, _o = scenario("live", monkeypatch)
    blk = st.get_read(S, "GGA")["gg_like"]["bull_flag"]
    e = blk["entry_bar_t"]
    m = {"GGA": {"bull_flag": blk}}
    assert AL._gl_fields(m, "GGA", "bull_flag", e) == {"gg_like": GL.from_stamp(blk)}
    # NEGATIVES — every other case is {}
    assert AL._gl_fields(None, "GGA", "bull_flag", e) == {}
    assert AL._gl_fields({}, "GGA", "bull_flag", e) == {}
    assert AL._gl_fields(m, "GGB", "bull_flag", e) == {}
    assert AL._gl_fields(m, "GGA", "kiss_fly", e) == {}
    assert AL._gl_fields(m, "GGA", "bull_flag", "2026-10-13 10:35") == {}
    assert AL._gl_fields(m, "GGA", "bull_flag", None) == {}
    assert AL._gl_fields({"GGA": {"bull_flag": dict(blk, verdict="maybe")}}, "GGA", "bull_flag", e) == {}
    assert AL._gl_fields({"GGA": {"bull_flag": dict(blk, v=True)}}, "GGA", "bull_flag", e) == {}
    assert AL._gl_fields({"GGA": ["x"]}, "GGA", "bull_flag", e) == {}
    monkeypatch.setattr(GL, "from_stamp", _raise)
    assert AL._gl_fields(m, "GGA", "bull_flag", e) == {}                   # a fault → {} (never raises)


# ── potential.py — frozen on the 🧠 claim at THIS read's as_of bar ─────────────────────────────────────────────────
def test_the_potential_push_carries_the_block_of_its_own_as_of_bar(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    st = _seeded()
    deps, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    out = RUN.run_pass(T1, store=st, deps=deps)
    assert out["potential"]["pushed"] == 1
    read = st.get_read(S, "GGA")
    bf = st.get_potential(S, "GGA", "bull_flag")
    assert bf["push"]["state"] == "pushed"                                 # the settle's dotted $set kept it
    assert bf["push"]["gg_like"] == read["gg_like"]["bull_flag"]
    assert bf["push"]["gg_like"]["as_of"] == read["setups"]["bull_flag"]["as_of_bar_t"]
    # NEGATIVE: every held setup of the name has no push block → no block
    for d in st.coll(ST.POTENTIALS).docs.values():
        if d.get("symbol") == "GGA" and d.get("setup") != "bull_flag":
            assert "push" not in d and not _has_key(d)
    # NEGATIVE: the payload sent never carries it
    assert not _has_key([p for (_o, p), _k in deps.send_potential.calls])


def test_NEGATIVE_a_block_of_another_as_of_bar_is_not_frozen_on_the_push(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    monkeypatch.setattr(GL, "doc_blocks", _blocks_with("as_of", "2026-10-13 09:55"))
    st = _seeded()
    deps, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    RUN.run_pass(T1, store=st, deps=deps)
    bf = st.get_potential(S, "GGA", "bull_flag")
    assert bf["push"]["state"] == "pushed" and "gg_like" not in bf["push"]
    assert "gg_like" in st.get_read(S, "GGA")


def test_NEGATIVE_a_dry_or_on_open_pass_writes_no_push_block(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    st = _seeded()
    deps, *_ = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})
    RUN.run_pass(T1, store=st, deps=deps, dry=True)
    assert all("push" not in d for d in st.coll(ST.POTENTIALS).docs.values())
    assert st.alerts_coll().docs == {}
    st2 = fake_store()
    deps2, _snap, send, _status = make_deps()
    od = RUN.run_on_demand(NOW, store=st2, deps=deps2)
    assert od["ran"] and "GGA:bull_flag" in od["aplus"]
    assert st2.alerts_coll().docs == {} and send.calls == []
    assert all("push" not in d for d in st2.coll(ST.POTENTIALS).docs.values())
    assert "gg_like" in st2.get_read(S, "GGA")                             # the read IS refreshed with its block


def test_gl_claim_unit(monkeypatch):
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "live")
    st = _seeded()
    RUN.run_pass(T1, store=st, deps=make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 30))})[0])
    read = st.get_read(S, "GGA")
    blk, r = read["gg_like"]["bull_flag"], read["setups"]["bull_flag"]
    m = {"GGA": {"bull_flag": blk}}
    assert PT._gl_claim(m, "GGA", "bull_flag", r) == {"gg_like": GL.from_stamp(blk)}
    assert PT._gl_claim(None, "GGA", "bull_flag", r) == {}
    assert PT._gl_claim(m, "GGA", "bull_flag", dict(r, as_of_bar_t="2026-10-13 10:00")) == {}
    assert PT._gl_claim(m, "GGA", "bull_flag", dict(r, as_of_bar_t=None)) == {}
    assert PT._gl_claim(m, "GGA", "bull_flag", None) == {}
    assert PT._gl_claim(m, "GGX", "bull_flag", r) == {}
    assert PT._gl_claim({"GGA": {"bull_flag": {"v": 1}}}, "GGA", "bull_flag", r) == {}
    monkeypatch.setattr(GL, "from_stamp", _raise)
    assert PT._gl_claim(m, "GGA", "bull_flag", r) == {}


# ── tab.py — the board ────────────────────────────────────────────────────────────────────────────────────────────
def _board(st, sub, **kw):
    with feed_pinned():
        return GT.build(sub, now=BOARD_AT, store=st, owner=True, **kw)


def test_the_card_subs_carry_gg_like_and_nothing_else_moves(monkeypatch):
    st, _o = scenario("live", monkeypatch)
    real = {k: _board(st, k) for k in CARD_SUBS}
    with monkeypatch.context() as m:
        m.setattr(GL, "tag", lambda *a, **k: None)
        noop = {k: _board(st, k) for k in CARD_SUBS}
    judged = 0
    for k in CARD_SUBS:
        b = real[k]
        assert b["gg_like"] == _json(GL.board_block()), k
        assert not _has_key(noop[k]), k
        # NEGATIVE: nothing reordered, hidden or recounted server-side — the board minus the key is the no-op board
        assert _strip(b) == noop[k], k
        assert [t["symbol"] for t in b["tiles"]] == [t["symbol"] for t in noop[k]["tiles"]], k
        for t in b["tiles"]:
            g = t.get("gajjala") or {}
            if g.get("setup"):
                doc = st.get_read(S, t["symbol"])
                state = ((doc or {}).get("setups", {}).get(g["setup"]) or {}).get("state")
                if state in GT.TILE_STATES:
                    assert isinstance(g.get("gg_like"), dict), (k, t["symbol"])
                    assert g["gg_like"]["verdict"] in GL.VERDICTS and isinstance(g["gg_like"]["keep"], bool)
                    judged += 1
    assert judged >= 3


def _carded_key(b) -> bool:
    """The board-level `gg_like` block or a card's `gajjala.gg_like` — the two keys this package serves. (The 🏁
    rows' `gg_like` chip and `gg_like_split` are be-track's, under `track_record`, and are not this wiring.)"""
    return "gg_like" in b or any(_has_key(t) for t in b.get("tiles") or [])


def test_NEGATIVE_no_other_board_carries_the_key(monkeypatch):
    st, _o = scenario("live", monkeypatch)
    for k in GT.SUB_KEYS:
        if k in CARD_SUBS:
            continue
        b = _board(st, k)
        assert not _carded_key(b), k                                       # ☀️ 🌙 📋 🏁 playbook 🧨 🌱 🩳
        if k != GC.LEDGER_SUB:
            assert not _has_key(b), k                                      # not one key anywhere off the 🏁
    for k in CARD_SUBS:
        assert not _carded_key(_board(st, k, variant=V.GGA)), ("🧪", k)    # the audited tab
        assert not _carded_key(_board(st, k, variant=V.GG1)), ("1m", k)    # the 1-minute page


def test_keep_through_build_rang_cards_and_pushed_potentials_are_kept(monkeypatch):
    st, _o = scenario("live", monkeypatch)

    def cards(sub="bull_flag"):
        return {t["symbol"]: t["gajjala"] for t in _board(st, sub)["tiles"]}

    by = cards()
    assert by["GGA"]["state"] in GT.MARKED_STATES
    assert by["GGA"]["gg_like"]["keep"] is True                            # an A+ card is never hidden
    gid = ST.potential_key(S, "GGB", "bull_flag")
    pots = st.coll(ST.POTENTIALS).docs
    assert by["GGB"]["state"] not in GT.MARKED_STATES
    assert "push" not in pots[gid]                                         # the fixture day: GGB's 🧠 never rang
    assert by["GGB"]["gg_like"]["keep"] is False                           # NEGATIVE: a forming card, nothing rang
    base = {k: v for k, v in by["GGB"]["gg_like"].items() if k != "keep"}
    pots[gid]["push"] = {"state": "pushed", "at_et": "10:41"}              # its 🧠 push rang today
    assert cards()["GGB"]["gg_like"]["keep"] is True
    pb = cards(GC.POTENTIAL_SUB)
    assert pb["GGB"]["gg_like"]["keep"] is True                            # the 🧠 card too
    # NEGATIVE: a push that did not ring, a non-dict push, no tracker doc → not kept; keep moves nothing else
    for push in ({"state": "held"}, {"state": "failed"}, {"state": "claimed"}, "pushed", None):
        pots[gid]["push"] = push
        g = cards()["GGB"]["gg_like"]
        assert g["keep"] is False, push
        assert {k: v for k, v in g.items() if k != "keep"} == base, push
    pots.pop(gid)
    assert cards()["GGB"]["gg_like"]["keep"] is False


def test_a_stale_stored_block_is_recomputed_and_a_fresh_one_is_served(monkeypatch):
    st, _o = scenario("live", monkeypatch)
    rid = ST.key(S, "GGA")
    doc = st.coll(ST.READS).docs[rid]
    real = doc["gg_like"]["bull_flag"]
    with monkeypatch.context() as m:                                       # a genuine block judged under other bounds
        m.setattr(GL, "BASE_MIN_BARS", {k: 99 for k in GC.SETUPS})
        alt = GL.doc_blocks({k: v for k, v in doc.items() if k != "gg_like"})["bull_flag"]
    assert alt["as_of"] == real["as_of"] and alt["entry_bar_t"] == real["entry_bar_t"]
    want_alt, want_real = _json(GL.served(alt, keep=True)), _json(GL.served(real, keep=True))
    assert want_alt != want_real                                           # the two are told apart on the card

    def card():
        return {t["symbol"]: t["gajjala"] for t in _board(st, "bull_flag")["tiles"]}["GGA"]["gg_like"]

    doc["gg_like"] = {"bull_flag": copy.deepcopy(alt)}
    assert card() == want_alt                                              # fresh (same as_of / entry bar) → served as stored
    doc["gg_like"] = {"bull_flag": dict(copy.deepcopy(alt), as_of="2026-10-13 10:05")}
    assert card() == want_real                                             # stale as_of → recomputed, never served
    doc["gg_like"] = {"bull_flag": dict(copy.deepcopy(alt), entry_bar_t="2026-10-13 10:05")}
    assert card() == want_real                                             # stale entry bar → recomputed
    doc.pop("gg_like")
    assert card() == want_real                                             # no stored block → computed


# ── the push path moved ONLY by the fenced 🧘 edits (the REFIX of 2026-11-27) ──────────────────────────────────────
# The pre-edit sha256 of inspect.getsource, as pinned on 2026-11-25 by test_gajjala_pot_all_2026_11_24.PUSH_PATH_SHA
# and test_gajjala_si_ssr_potential_2026_11_24 (alerts.run_pass). Those two files are NOT this package's: the main
# session re-pins them to the new bytes; THIS pin keeps proving the edit is additive after that re-pin.
PRE_GG_LIKE_SHA = {
    "alerts.run_pass": "d2ded91a11f4fecd41deb023adb6ca4104ba9fcebbea8c808ebb8fff9acbc778",
    "potential.run_pass": "629c24a61435d57743a7be44ed6f30ad15adde584b3d674ae9d99397354f49a0",
}


def _sha(src: str) -> str:
    return hashlib.sha256(src.encode()).hexdigest()


def _strip_gg_like(src: str) -> str:
    """Undo exactly the four fenced 🧘 edits: the kwarg, the dated docstring tail, the `_gl_fields` line, the
    `**_gl_claim(...)` splat. Nothing else is touched."""
    src = src.replace(", gg_like: Optional[dict] = None) -> dict:", ") -> dict:")
    src = re.sub(r"\n    🧘 2026-11-27:.*?(\"\"\")", r"\1", src, flags=re.S)
    src = re.sub(r"\n[^\n]*_gl_fields\(gg_like[^\n]*", "", src)
    return src.replace(", **_gl_claim(gg_like, sym, setup, r)})", "})")


def _push_path_sources() -> dict:
    return {"alerts.run_pass": inspect.getsource(AL.run_pass), "potential.run_pass": inspect.getsource(PT.run_pass)}


def test_the_push_path_minus_the_fenced_edits_is_byte_identical_to_the_pre_edit_pins():
    got = {k: _sha(_strip_gg_like(src)) for k, src in _push_path_sources().items()}
    assert got == PRE_GG_LIKE_SHA


def test_the_push_path_did_move_so_the_old_pins_must_be_re_pinned():
    now = {k: _sha(src) for k, src in _push_path_sources().items()}
    assert all(now[k] != PRE_GG_LIKE_SHA[k] for k in now)                 # the main session's re-pin is real, not a no-op
    for src in _push_path_sources().values():
        assert "gg_like" in src and "_strip_gg_like" not in src


@pytest.mark.parametrize("name, mutate", [
    ("alerts.run_pass", lambda s: s.replace("closed=closed)", "closed=None)", 1)),
    ("alerts.run_pass", lambda s: s + "\n"),
    ("potential.run_pass", lambda s: s.replace('"px": px_of(sym)', '"px": None', 1)),
    ("potential.run_pass", lambda s: s.replace("dry=False", "dry=True", 1)),
])
def test_NEGATIVE_any_unfenced_change_breaks_the_strip_pin(name, mutate):
    src = _push_path_sources()[name]
    moved = mutate(src)
    assert moved != src
    assert _sha(_strip_gg_like(moved)) != PRE_GG_LIKE_SHA[name]


def test_NEGATIVE_the_strip_removes_only_gg_like_lines():
    for name, src in _push_path_sources().items():
        kept = _strip_gg_like(src).splitlines()
        gone = [ln for ln in src.splitlines() if ln not in kept]
        assert gone, name
        moved = [ln for ln in gone if ln + '"""' not in kept]                 # the old docstring end gains its quotes back
        assert all(any(w in ln for w in ("gg_like", "_gl_", "1-minute page")) for ln in moved), (name, moved)
        assert len(gone) - len(moved) <= 1, (name, gone)
