"""🧪 Gajjala · Audited — K3S served (2026-11-09, SPEC gg-k3s §3.4 / WP-C `gg-k3s-serve`).

Ajay 2026-11-09, verbatim: "yes change the audit as per you like that is yours I need you to make it successful and
earn money that is the goal I am losing money realtime I wanna cut down all my subscriptuons eventually but also I would
like us to learn from a big squeeze can you Identify any patterns please from big squeezes may be warn me about halts"

The registry's ADMIT rule K3S makes a 🎾 break 🚩 reads "broke — not A+" on K3 alone a 🧪 A+. Covered here (the serve
side only — the pass that writes the overlay entry / claim / marker is WP-B's file):
- the card: `overlay_reads` paints the 🚩 partial ONLY on its break pass (k3s_candidate ⇒ bars_since_entry == 0) and only
  when the overlay entry carries `admit` [C3]; `state_label` prints the admit's own words FIRST; the marker label; the
  recap word; a held K3S read in the held block with `admit`;
- the strip: `audited.admitted` from the GGA state doc's `k3s_session`;
- the 🏁 compare: the `admitted` block (W / L / filled / mean R by GG's math [C4], held-by counts [C8], same-day
  original [C7]), `recon.admitted` [C6], the per-rule K3S row (kind admit, LAST), the admitted record never scored on a
  filter row nor in 🚩's audit column [C7];
- the nightly: a K3S ring with no 🚩 row is a residual (graded on its own plan, nothing copied).
NEGATIVES are marked. UNMEASURED — nothing here trades.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone

from chart_maps.gajjala import audited_pass as AP
from chart_maps.gajjala import audited_rules as AUD
from chart_maps.gajjala import audited_tab as AT
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import nightly as NG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_audited_nightly import NIGHT, _gga_claim
from tests.test_gajjala_audited_nightly import stores as night_stores
from tests.test_gajjala_audited_tab import (  # noqa: F401 — `world` + `_no_override` are pytest fixtures
    B_WORD, D1, EDGE, NOW_B, NOW_C, _claim, _grade, _held, _identity, _no_override, base_world, entry, gga_store,
    plant, state_ok, stores, strings, tile_of, walk, world)
from tests.test_gajjala_run import S

RS = "reversal_squeeze"
TODAY_C = date(2026, 11, 4)
B_RS = "2026-11-03 10:40"
NEW_KEYS = ("k3s_pass_line", "admitted_title", "admitted_line", "admitted_empty", "admitted_held_by",
            "admitted_same_day", "per_rule_admit_with", "per_rule_admit_other", "per_rule_delta_admit")


# ── helpers ───────────────────────────────────────────────────────────────────────────────────────────────────────
def loud_frame(after=None):
    """The K3S precondition (test_gajjala_detectors.py:847): base volume 0.51× the squeeze-back → partial on k3 alone."""
    loud = FX.rs_replace(r11=(6.1875, 6.21875, 6.125, 6.15625, 0.51 * FX.RS_BARS[10][4]))
    return FX.rs_frame(loud, after=after)


def rs_partial(after=None) -> dict:
    """🚩's own read of the loud base — state partial, missed == ["k3_vol"], on its break bar unless `after`."""
    return D.reversal_squeeze(loud_frame(after), float_read=FX.float_read(5_000_000))


def admit_block(fails=()) -> dict:
    """An audit block exactly as audited_rules._finish composes it for a K3S admit (the ONE composer)."""
    ids = [r.id for r in AUD.judge_rules()]
    res = {i: (i not in fails, f"why {i}") for i in ids}
    return AUD._finish(res, {i: {} for i in ids}, "5m", admit=AUD.K3S.id)


def admit_entry(read, fails=()) -> dict:
    return dict(admit_block(fails), entry_bar_t=read.get("entry_bar_t"), trigger=read.get("trigger"),
                stop=read.get("stop"), risk_pct=read.get("risk_pct"))


class _Ov:
    def __init__(self, docs):
        self.docs = docs

    def overlays(self, session):
        return self.docs


UPD = datetime(2026, 10, 13, 14, 41, tzinfo=timezone.utc)


def rs_doc(read, upd=UPD) -> dict:
    return {"symbol": "KKK", "updated_at": upd, "tile": {"bars5": [{"t": read.get("entry_bar_t")}]},
            "setups": {RS: read, "bull_flag": {"state": "forming"}}}


def rs_ov(ent, pass_at=UPD) -> dict:
    return {"symbol": "KKK", "pass_at": pass_at, "setups": {RS: ent}}


def admit_audit(fails=(), *, admit="K3S") -> dict:
    """A GGA claim / marker audit block as the pass stores it (the K3S admit's)."""
    b = admit_block(fails)
    b["admit"] = admit
    return b


def k3s_claim(sym, *, d=D1, bar=B_RS, fails=()):
    return _claim(sym, variant=V.GGA, setup=RS, bar=bar, audit=admit_audit(fails), d=d)


def k3s_marker(sym, ids, *, d=D1, bar=B_RS):
    m = _held(sym, ids, d=d, bar=bar, setup=RS)
    m["audit"] = admit_audit(ids)
    return m


def compare(st):
    return AT.compare_block(st, TODAY_C, NOW_C, span="5d", is_today=True)


def rid(sym, setup=RS, d=D1):
    return LG.ledger_id(d.isoformat(), sym, setup, LG.KINDS[1])


# ── the card: overlay_reads paints the break pass only [C3] ───────────────────────────────────────────────────────
def test_the_break_pass_partial_is_painted_as_a_k3s_aplus_with_its_own_words():
    r = rs_partial()
    assert AUD.k3s_candidate(dict(r, setup=RS)) and r["bars_since_entry"] == 0
    d = rs_doc(r)
    out, stats = AT.overlay_reads({"KKK": d}, _Ov([rs_ov(admit_entry(r))]), S)
    p = out["KKK"]["setups"][RS]
    assert p["state"] == "aplus" and p["audit"]["admit"] == "K3S" and p["audit"]["aplus"] is True
    assert set(p["audit"]) == set(AUD.AUDIT_SERVED_KEYS)                       # only the served keys ride
    assert p["reason"] == D.NOT_APLUS_REASON                                     # what 🚩 read rides to the card
    k3 = next(c for c in p["criteria"] if c["key"] == D.K3_VOL_KEY)
    assert k3["ok"] is False and p["missed"] == [D.K3_VOL_KEY]                  # the K3 row stays visible ✗
    assert stats["n_admitted"] == 1 and stats["n_aplus_original"] == 0 and stats["n_unaudited"] == 0
    assert stats["n_aplus_audited"] == 0 and stats["n_held"] == 0               # those count 🚩 A+ only
    lab = GT.state_label(p)
    assert lab == p["audit"]["text"]
    assert lab.startswith(f"🧪 A+ by K3S — 🚩 reads it '{D.NOT_APLUS_REASON}'")
    assert d["setups"][RS]["state"] == "partial" and "audit" not in d["setups"][RS]   # never mutated


def test_a_failed_admit_is_painted_held_with_the_admit_held_words():
    r = rs_partial()
    out, stats = AT.overlay_reads({"KKK": rs_doc(r)}, _Ov([rs_ov(admit_entry(r, fails=("G1",)))]), S)
    p = out["KKK"]["setups"][RS]
    assert p["state"] == AUD.HELD_STATE and p["audit"]["failed"][0]["id"] == "G1"
    assert GT.state_label(p) == p["audit"]["text"]
    assert GT.state_label(p).startswith(f"🧪 A+ by K3S (🚩 reads it '{D.NOT_APLUS_REASON}'), held here by: G1")
    assert stats["n_admitted"] == 1 and stats["n_held"] == 0


def test_NEGATIVE_one_bar_after_the_break_the_card_is_the_stored_partial_byte_for_byte():
    """[C3] — the same stored read one bar later (the detector's own bars_since_entry == 1) is never painted."""
    later = rs_partial(after=[(6.25, 6.3, 6.2, 6.28, 300_000)])
    assert later["state"] == "partial" and later["bars_since_entry"] == 1
    assert later["entry_bar_t"] == rs_partial()["entry_bar_t"]
    d = rs_doc(later)
    before = json.dumps(d, default=str, sort_keys=True)
    out, stats = AT.overlay_reads({"KKK": d}, _Ov([rs_ov(admit_entry(rs_partial()))]), S)
    assert out["KKK"] is d and "audit" not in out["KKK"]["setups"][RS]
    assert out["KKK"]["setups"][RS]["state"] == "partial"
    assert json.dumps(out["KKK"], default=str, sort_keys=True) == before
    assert stats["n_admitted"] == 0
    assert GT.state_label(later).startswith(D.NOT_APLUS_REASON)                 # 🚩's own words, unchanged


def test_NEGATIVE_a_partial_with_an_entry_lacking_admit_or_stale_or_on_another_bar_is_never_painted():
    r = rs_partial()
    plain = admit_entry(r)
    plain.pop("admit")
    none = dict(admit_entry(r), admit=None)
    for ent in (plain, none):                                                    # today's (1) rule stays
        out, s = AT.overlay_reads({"KKK": rs_doc(r)}, _Ov([rs_ov(ent)]), S)
        assert "audit" not in out["KKK"]["setups"][RS] and s["n_admitted"] == 0
    old = UPD - timedelta(seconds=GC.PASS_CADENCE_SEC)                           # (3) one pass older than the read
    out, s = AT.overlay_reads({"KKK": rs_doc(r)}, _Ov([rs_ov(admit_entry(r), pass_at=old)]), S)
    assert "audit" not in out["KKK"]["setups"][RS] and s["n_admitted"] == 0 and s["n_unaudited"] == 0
    other = dict(admit_entry(r), entry_bar_t="2026-10-13 05:05")                 # (2) another bar
    out, s = AT.overlay_reads({"KKK": rs_doc(r)}, _Ov([rs_ov(other)]), S)
    assert "audit" not in out["KKK"]["setups"][RS]
    # a partial on another rule (placebo (a)) and a non-🎾 partial: never painted even with an admit entry
    two = dict(r, missed=[D.K3_VOL_KEY, "k8_failed"])
    out, s = AT.overlay_reads({"KKK": rs_doc(two)}, _Ov([rs_ov(admit_entry(r))]), S)
    assert "audit" not in out["KKK"]["setups"][RS]
    bf = {"KKK": {"symbol": "KKK", "updated_at": UPD, "setups": {"bull_flag": dict(r)}}}
    out, s = AT.overlay_reads(bf, _Ov([{"symbol": "KKK", "pass_at": UPD,
                                        "setups": {"bull_flag": admit_entry(r)}}]), S)
    assert "audit" not in out["KKK"]["setups"]["bull_flag"] and s["n_admitted"] == 0


def test_NEGATIVE_the_non_k3s_held_and_aplus_labels_are_byte_for_byte_today():
    held = {"state": AUD.HELD_STATE, "audit": {"text": "🚩 A+ on the original, held here by: G1 — w · UNMEASURED"}}
    assert GT.state_label(held) == held["audit"]["text"]
    assert GT.state_label(dict(held, audit=dict(held["audit"], admit=None))) == held["audit"]["text"]
    ap = {"state": "aplus", "audit": {"text": "audited A+ — G1 pass · UNMEASURED", "admit": None}}
    assert GT.state_label(ap) == GT.state_label({"state": "aplus"})
    assert GT.state_label({"state": "aplus"}) == f"A+ — every rule met, entry bar closed · {GT.UNMEASURED}"
    # an admit on a state it does not paint (a stored partial) never borrows the words
    part = dict(rs_partial(), audit={"text": "x", "admit": "K3S"})
    assert GT.state_label(part) != "x"


def test_the_recap_names_a_k3s_held_and_a_k3s_aplus():
    r = rs_partial()
    out, _s = AT.overlay_reads({"KKK": rs_doc(r)}, _Ov([rs_ov(admit_entry(r, fails=("H1",)))]), S)
    rows = GT.recap([out["KKK"]], V.GGA)["rows"]
    assert len(rows) == 1 and GT.ADMIT_RECAP_WORD in rows[0]["text"] and GT.HELD_RECAP_WORD not in rows[0]["text"]
    ok, _s = AT.overlay_reads({"KKK": rs_doc(r)}, _Ov([rs_ov(admit_entry(r))]), S)
    rows = GT.recap([ok["KKK"]], V.GGA)["rows"]
    assert len(rows) == 1 and rows[0]["text"].endswith(" · 🧪 only by K3S")
    # NEGATIVE: a 🚩 A+ (no admit) keeps today's recap line; GG5's recap never reads an audit
    plain = {"symbol": "PPP", "setups": {"bull_flag": {"state": "aplus", "entry_bar_t": "2026-10-13 10:40",
                                                       "trigger": 1.0, "stop": 0.9,
                                                       "audit": {"admit": None}}}}
    assert "🧪 only" not in GT.recap([plain], V.GGA)["rows"][0]["text"]
    assert "🧪 only" not in GT.recap([ok["KKK"]])["rows"][0]["text"]              # GG5's recap: no audit read


# ── the board: the marker, the held block ─────────────────────────────────────────────────────────────────────────
def _k3s_world(world, fails=()):
    st, doc, setup = world
    r0 = doc["setups"][setup]
    rs = dict(rs_partial(), entry_bar_t=r0["entry_bar_t"])                       # a bar the tile carries
    doc2 = dict(doc, setups={**doc["setups"], RS: rs})
    st.upsert_read(S, "GGA", {k: v for k, v in doc2.items() if k != "_id"}, now=doc["updated_at"])
    doc2 = st.get_read(S, "GGA")
    gga = gga_store(st)
    gga.upsert_overlay(S, "GGA", {"date": S.isoformat(), "symbol": "GGA", "frozen": {},
                                  "setups": {RS: admit_entry(rs, fails=fails)},
                                  "pass_at": doc2["updated_at"], "version": 1}, now=doc2["updated_at"])
    state_ok(gga, st)
    return st, gga


def test_the_board_k3s_held_card_marker_and_the_held_block_carry_the_admit(world):
    st, gga = _k3s_world(world, fails=("G1",))
    b = GT.build(RS, now=NOW_B, store=gga, owner=True)
    t = tile_of(b, "GGA")
    g = t["gajjala"]
    assert g["state"] == AUD.HELD_STATE and g["audit"]["admit"] == "K3S"
    assert g["state_label"] == g["audit"]["text"] and g["state_label"].startswith("🧪 A+ by K3S (")
    assert [m["label"] for m in t["markers"]] == [GT.ADMIT_MARKER_LABEL]
    held = [r for r in b["held"]["rows"] if r["symbol"] == "GGA" and r["setup"] == RS]
    assert len(held) == 1 and held[0]["admit"] == "K3S" and held[0]["held_by"][0]["id"] == "G1"
    assert st.get_read(S, "GGA")["setups"][RS]["state"] == "partial"           # never written back


def test_the_board_k3s_aplus_card_keeps_the_aplus_marker_and_a_plain_held_row_has_admit_none(world):
    st, gga = _k3s_world(world)
    b = GT.build(RS, now=NOW_B, store=gga, owner=True)
    t = tile_of(b, "GGA")
    assert t["gajjala"]["state"] == "aplus" and t["gajjala"]["state_label"].startswith("🧪 A+ by K3S — ")
    assert [m["label"] for m in t["markers"]] == ["A+"]
    # NEGATIVE: a 🚩 A+ held by G1 (no admit) serves `admit: None` on its held row and today's marker
    st2, doc, setup = world
    gga2 = gga_store(st2)
    plant(gga2, doc, setup, entry(doc["setups"][setup], failed=("G1",)))
    b2 = GT.build(setup, now=NOW_B, store=gga2)
    assert [r["admit"] for r in b2["held"]["rows"]] == [None]
    assert [m["label"] for m in tile_of(b2, "GGA")["markers"]] == [GT.HELD_MARKER_LABEL]


# ── the strip ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _strip(ks):
    st = base_world()
    st.set_state(AP.LATEST_ID, {"at": NOW_C.astimezone(timezone.utc), "ok": True, "n_read": 1,
                                **({"k3s_session": ks} if ks is not None else {})})
    return AT.audited_block(st, TODAY_C, NOW_C, None, None)["admitted"]


def test_the_strip_serves_the_admitted_line_from_the_durable_session_counts():
    a = _strip({"candidates": 3, "placebo_a": 2, "rang": 1, "held": 1, "k11_refused": 1, "read_fault": False})
    assert {k: a[k] for k in ("n", "rang", "held", "candidates", "k11_refused", "placebo_a")} == {
        "n": 2, "rang": 1, "held": 1, "candidates": 3, "k11_refused": 1, "placebo_a": 2}
    assert a["text"] == V.word("k3s_pass_line", V.GGA, n=2, rule="K3S", reason=D.NOT_APLUS_REASON, rang=1, held=1,
                               vol=1, gate=AT.K11_RULE, cand=3, pa=2)
    assert a["text"].startswith(f"2 🧪 A+ by K3S today — 🚩 read them '{D.NOT_APLUS_REASON}'")
    assert a["text"] == (f"2 🧪 A+ by K3S today — 🚩 read them '{D.NOT_APLUS_REASON}' · 1 rang in shadow · 1 held · "
                         "1 refused by K11 · 3 candidates · 2 🎾 breaks partial on another rule")   # spec §3.4 verbatim


def test_the_k11_word_is_the_rule_name_off_the_one_key_and_matches_the_card_label():
    assert AT.K11_RULE == "K11"
    assert D.k11_criterion(None)["label"].startswith(AT.K11_RULE + " ")              # the card's own "K11 …" label
    assert "{gate}" in V.WORDS_GGA["k3s_pass_line"] and "{vol}" in V.WORDS_GGA["k3s_pass_line"]


def test_NEGATIVE_the_admit_line_never_says_the_old_floor_words_nor_types_the_rule_name():
    tpl = V.WORDS_GGA["k3s_pass_line"]
    assert "session-volume floor" not in tpl and "K11" not in tpl                    # the name is a kwarg
    a = _strip({"candidates": 1, "placebo_a": 0, "rang": 1, "held": 0, "k11_refused": None, "read_fault": False})
    assert "0 refused by K11" in a["text"] and "None" not in a["text"]                # None count → 0, never "None"


def test_NEGATIVE_the_strip_without_k3s_session_or_without_a_candidate_has_no_text():
    assert _strip(None) == {"n": None, "rang": None, "held": None, "candidates": None, "k11_refused": None,
                            "placebo_a": None, "text": None}
    z = _strip({"candidates": 0, "placebo_a": 4, "rang": 0, "held": 0, "k11_refused": 0, "read_fault": False})
    assert z["text"] is None and z["placebo_a"] == 4 and z["n"] == 0
    assert _strip({"candidates": True, "rang": "1"})["candidates"] is None       # never a bool or a str as a count


# ── the 🏁 compare ────────────────────────────────────────────────────────────────────────────────────────────────
def test_a_k3s_ring_is_a_tested_only_row_with_its_grade_and_mean_r():
    st = base_world(extra_a=[k3s_claim("KKK")], extra_al=[_grade("KKK", "win", setup=RS)])
    c = compare(st)
    o, a = c["sides"]
    assert a["n"] == 2 and o["n"] == 2                                            # the 🧪 side counts the ring
    assert c["recon"]["admitted"] == 1 and c["recon"]["audited_only"] == 0 and _identity(c)
    assert c["recon"]["text"] == V.word("compare_recon", V.GGA, original_only=0, audited_only=0)
    ad = c["admitted"]
    assert (ad["n"], ad["rang"], ad["held"], ad["filled"], ad["win"], ad["loss"]) == (1, 1, 0, 1, 1, 0)
    assert ad["mean_r"] == AT._tally([{"state": "win"}])["mean_r"] == float(GC.LEDGER_R_MULT)
    assert ad["same_day_original"] == 0 and ad["held_by_counts"] == {} and ad["held_by_text"] is None
    assert AT._mean_text(AT._tally([{"state": "win"}])) in ad["text"] and "of 1 filled" in ad["text"]
    assert ad["title"] == V.word("admitted_title", V.GGA, reason=D.NOT_APLUS_REASON)
    row = ad["rows"][0]
    assert (row["symbol"], row["setup"], row["kind"], row["rule"], row["outcome"]) == ("KKK", RS, "rang", "K3S", "win")
    assert row["text"].startswith(f"{D1.isoformat()} · KKK · {GT._setup_label(RS)} · 🧪 only by K3S · rang in shadow")
    assert row["text"].endswith(row["outcome_text"]) and row["original_same_day"] is False
    pr = {r["key"]: r for r in c["per_rule"]}
    k = c["per_rule"][-1]
    assert k["key"] == "K3S" and k["kind"] == AUD.KIND_ADMIT and pr["K3S"] is k
    assert (k["with"]["n"], k["with"]["win"], k["with"]["mean_r"]) == (1, 1, float(GC.LEDGER_R_MULT))
    assert k["other"]["n"] == 0                                                   # 🚩 has no 🎾 A+ on the span
    assert k["with"]["label"] == V.word("per_rule_admit_with", V.GGA)
    assert k["other"]["label"] == V.word("per_rule_admit_other", V.GGA)
    wt = AT._tally([{"state": "win"}])
    assert k["delta_text"] == V.word("per_rule_delta_admit", V.GGA, n=1, w=1, l=0, filled=1, u=0,
                                     mr=AT._mean_text(wt), gw=0, gl=0, gn=0)
    assert AT._mean_text(wt) in k["delta_text"]
    # the admitted ring never lands on a filter row (no `no_original` from it)
    assert all(r["with"][AT.NO_ORIGINAL] + r["other"][AT.NO_ORIGINAL] == 0 for r in c["per_rule"]
               if r["kind"] in (AUD.KIND_FILTER, AT.KIND_CAP))


def test_the_k3s_row_other_counts_flag_reversal_squeeze_aplus_only():
    st = base_world(extra_g5=[_claim("RSQ", setup=RS)], extra_g5l=[_grade("RSQ", "loss", setup=RS)],
                    extra_a=[k3s_claim("KKK")], extra_al=[_grade("KKK", "loss", setup=RS)])
    c = compare(st)
    k = c["per_rule"][-1]
    assert (k["other"]["n"], k["other"]["loss"]) == (1, 1)                       # AAA / BBB are bull flags: not counted
    assert k["delta_text"].endswith("🚩 🎾 A+: 0 W / 1 L on 1")
    assert c["admitted"]["mean_r"] == -1.0 and _identity(c)


def test_a_k3s_held_marker_is_in_the_admitted_block_never_in_the_held_side():
    st = base_world(extra_a=[k3s_marker("HKK", ["G1"])])
    c = compare(st)
    assert "HKK" not in {r["symbol"] for r in c["held"]["rows"]} and c["held"]["n"] == 1
    ad = c["admitted"]
    assert (ad["n"], ad["rang"], ad["held"]) == (1, 0, 1)
    assert ad["held_by_counts"] == {"G1": 1} and ad["held_by_text"] == "held by: G1 ×1"
    row = ad["rows"][0]
    assert row["kind"] == "held" and row["held_by"] == ["G1"] and row["outcome"] == AT.ADMIT_HELD_STATE
    assert " · held by G1 · " in row["text"] and row["text"].endswith(AT.ADMIT_HELD_TEXT)
    assert c["recon"]["admitted"] == 0 and c["recon"]["audited_only"] == 0 and _identity(c)
    pr = {r["key"]: r for r in c["per_rule"]}
    assert pr["G1"]["other"][AT.NO_ORIGINAL] == 0 and pr["G1"]["other"]["n"] == 0   # never a filter verdict
    assert pr["K3S"]["with"]["n"] == 0 and pr["K3S"]["delta_text"] == V.word("per_rule_no_rows", V.GGA)


def test_held_by_counts_are_sorted_by_count_then_id():
    st = base_world(extra_a=[k3s_marker("HA", ["H1", "G1"]), k3s_marker("HB", ["G1"]),
                             k3s_marker("HC", ["A1"])])
    ad = compare(st)["admitted"]
    assert list(ad["held_by_counts"].items()) == [("G1", 2), ("A1", 1), ("H1", 1)]
    assert ad["held_by_text"] == "held by: G1 ×2 · A1 ×1 · H1 ×1"


def test_a_k3s_ring_and_a_later_same_day_flag_aplus_share_the_id_c7():
    st = base_world(extra_g5=[_claim("SDO", setup=RS, bar="2026-11-03 11:15")],
                    extra_g5l=[_grade("SDO", "loss", setup=RS)],
                    extra_a=[k3s_claim("SDO")], extra_al=[_grade("SDO", "win", setup=RS)])
    c = compare(st)
    assert c["recon"]["admitted"] == 0 and c["admitted"]["same_day_original"] == 1 and _identity(c)
    row = c["admitted"]["rows"][0]
    assert row["original_same_day"] is True and row["text"].endswith(V.word("admitted_same_day", V.GGA))
    read = AT.read_span(st, TODAY_C, NOW_C, span="5d", is_today=True)
    cells = AT.row_audits(read["sides"], read["exits_by_id"])
    assert cells[rid("SDO")]["state"] == "not_judged"                             # 🚩's row: not judged under C7
    assert cells[rid("SDO")]["text"] == V.word("row_audit_not_judged", V.GGA)
    pr = {r["key"]: r for r in c["per_rule"]}
    assert pr["G1"]["not_judged"] >= 1 and pr["K3S"]["other"]["n"] == 1


def test_NEGATIVE_a_world_with_no_admit_keeps_recon_and_serves_an_empty_admitted_block():
    c = compare(base_world())
    assert c["recon"]["admitted"] == 0
    assert c["recon"]["text"] == V.word("compare_recon", V.GGA, original_only=0, audited_only=0)
    ad = c["admitted"]
    assert (ad["n"], ad["rang"], ad["held"], ad["mean_r"], ad["same_day_original"]) == (0, 0, 0, None, 0)
    assert ad["rows"] == [] and ad["held_by_counts"] == {} and ad["held_by_text"] is None
    assert ad["text"] == V.word("admitted_empty", V.GGA, rule="K3S")
    k = c["per_rule"][-1]
    assert k["key"] == "K3S" and k["delta_text"] == V.word("per_rule_no_rows", V.GGA)
    assert set(c["sides"][0]) == set(c["sides"][1])                               # the side shape never moves


def test_NEGATIVE_the_both_world_identity_holds_with_admitted_zero():
    c4 = compare(base_world(extra_g5=[_claim("FFF")], extra_g5l=[_grade("FFF", "win")],
                            extra_a=[_claim("FFF", variant=V.GGA), _held("FFF", ["G2"])]))
    assert c4["recon"]["both"] == 1 and c4["recon"]["admitted"] == 0 and _identity(c4)
    r = c4["recon"]                                                                # NEGATIVE: needs `- both`
    o, a = c4["sides"]
    h = c4["held"]
    assert o["n"] + o["n_dup"] != (a["n"] + a["n_dup"] + h["n"] + h["n_dup"] + r["original_only"]
                                   - r["audited_only"] - r["admitted"])


def test_NEGATIVE_the_identity_needs_minus_admitted():
    c = compare(base_world(extra_a=[k3s_claim("KKK")], extra_al=[_grade("KKK", "win", setup=RS)]))
    r, h = c["recon"], c["held"]
    o, a = c["sides"]
    assert _identity(c)
    assert o["n"] + o["n_dup"] != (a["n"] + a["n_dup"] + h["n"] + h["n_dup"] + r["original_only"]
                                   - r["audited_only"] - r["both"])


def test_a_k3s_cell_never_appears_on_a_flag_row():
    st = base_world(extra_a=[k3s_claim("KKK")], extra_al=[_grade("KKK", "win", setup=RS)])
    read = AT.read_span(st, TODAY_C, NOW_C, span="5d", is_today=True)
    cells = AT.row_audits(read["sides"], read["exits_by_id"])
    assert set(cells) == {r["id"] for r in read["sides"]["original"]} and rid("KKK") not in cells
    base = AT.read_span(base_world(), TODAY_C, NOW_C, span="5d", is_today=True)
    assert cells == AT.row_audits(base["sides"], base["exits_by_id"])            # 🚩's rows: unchanged


def test_every_new_payload_dumps_and_carries_no_forbidden_word():
    st = base_world(extra_g5=[_claim("SDO", setup=RS)], extra_g5l=[_grade("SDO", "loss", setup=RS)],
                    extra_a=[k3s_claim("KKK"), k3s_claim("SDO"), k3s_marker("HKK", ["G1", "H1"])],
                    extra_al=[_grade("KKK", "win", setup=RS)])
    c = compare(st)
    json.dumps(c, allow_nan=False)
    b = GT.build(GC.LEDGER_SUB, now=NOW_C, store=st, span="5d")
    json.dumps(GT._plain(b), allow_nan=False)
    assert b["audited_compare"]["admitted"]["n"] == 3
    for s in strings({"a": c["admitted"], "r": c["per_rule"][-1], "s": _strip({"candidates": 1, "rang": 1,
                                                                                  "held": 0, "placebo_a": 0,
                                                                                  "k11_refused": 0})}):
        assert not EDGE.search(s) and not B_WORD.search(s) and "None" not in s, s
    assert not [p for p, _k, v in walk(c) if v.__class__.__name__ == "Decimal"]


def test_NEGATIVE_no_digit_in_any_new_template_and_gg5_gg1_serve_none():
    for k in NEW_KEYS:
        assert k in V.WORDS_GGA, k
        assert not re.search(r"\d", V.WORDS_GGA[k]), k
        assert not EDGE.search(V.WORDS_GGA[k]) and not B_WORD.search(V.WORDS_GGA[k]), k
        assert V.word(k, V.GG5) is None and k not in V.WORDS_1M, k


# ── the nightly ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_nightly_grades_a_k3s_ring_with_no_flag_row_as_the_residual():
    claim = _gga_claim("KKK", RS)
    claim["audit"] = admit_audit()
    _shared, gga = night_stores(gga_alerts=[claim])
    out = NG.copy_original_grades(gga, NIGHT)
    assert (out["rows"], out["matched"], out["copied_cols"], out["residual"]) == (1, 0, 0, 1)
    assert gga.coll(ST.LEDGER).docs == {}                                         # nothing copied


# ── NEGATIVE: the GG5 board golden ────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_the_gg5_board_golden_holds(monkeypatch):
    from tests.test_gajjala_variant_gg5_identity import BOARD, board_text, writes_text
    st, _t = writes_text(monkeypatch)
    assert board_text(st) == BOARD.read_text(encoding="utf-8")
