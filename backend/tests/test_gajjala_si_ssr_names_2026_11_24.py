"""⛔🔒🩳 SI / SSR / Reg SHO names on 🚩 Gajjala's pass — chart_maps/gajjala/si_ssr_names.py (SPEC sissr rev 2 §3.3).

Ajay 2026-11-24 ~23:35 ET, verbatim: "Days past little bit like AKAN is what I am mainly looking for many were so
confident on SSR..". FOUR tagged sources (🩳 High SI · ⛔ SSR today · ⛔ SSR recent · 🔒 past close-out), read from STORED
reads only. An off-list ⛔ / 🔒 name that passes GG's add check AND GG's 1M floor joins the pass — at most
ADD_MAX_NEW_PER_PASS new a pass, none on the open; the rest are COUNTED (queued / skipped / under_floor), never hidden.
A name already on the list is TAGGED, never a second row. NEGATIVES are mandatory and named so. UNMEASURED.
"""
from __future__ import annotations

import ast
import inspect
import json
import math
from datetime import date
from pathlib import Path

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import high_si as HS
from chart_maps.gajjala import promo_names as PN
from chart_maps.gajjala import scanner as SC
from chart_maps.gajjala import si_ssr_names as SSN
from chart_maps.gajjala import trader_names as TN
from short_interest import reg_sho as RSH
from short_interest import ssr as SSR
from tests.test_gajjala_run import NOW, PREV, S, at, snap_row
from tests.test_gajjala_store import fake_store


@pytest.fixture(autouse=True)
def _adds_on_for_the_add_machinery(monkeypatch):
    """2026-11-25: SSN.ADD_ON ships False (no TOTAL cap yet; his number). These tests exercise the add machinery as it
    runs once he turns adds on, so they switch it on here. The shipped-off state is pinned in
    test_gajjala_si_ssr_adds_off_2026_11_25.py."""
    from chart_maps.gajjala import si_ssr_names as _SSN
    monkeypatch.setattr(_SSN, "ADD_ON", True)


ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "chart_maps" / "gajjala" / "si_ssr_names.py"
TODAY, PREV_ISO = S.isoformat(), PREV.isoformat()
TYPES = {"AKAN": "CS", "DBGI": "CS", "ETFX": "ETF", "BIGP": "CS", "THIN": "CS", "OLDP": "CS", "GGQ": "CS",
         "LOWC": "CS", "CRMT": "CS", "ZNB": "CS"}


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture(autouse=True)
def sho_words(monkeypatch):
    """The 🔒 engine's words (reg_sho.past_closeout_text, WP be-ssr-words) — a stand-in that RELAYS a test-only key, so
    these tests pin that this module serves the engine's words verbatim and never builds its own."""
    monkeypatch.setattr(RSH, "past_closeout_text", lambda run: (run or {}).get("_words"), raising=False)


@pytest.fixture(autouse=True)
def no_si_read(monkeypatch):
    """No test here reaches Mongo: the 🩳 read is the house read's stub (an empty map = nothing is High SI)."""
    monkeypatch.setattr(HS, "si_blocks", lambda syms, *, today: {})


# ── builders ──────────────────────────────────────────────────────────────────────────────────────────────────────
def ssr_row(on: str, day_n: int, **kw) -> dict:
    md = on[5:7] + "/" + on[8:10]
    return dict({"triggered_on": on, "day_n": day_n, "source": "official", "exchange": "NASDAQ",
                 "retriggered": False, "tag_text": f"⛔ SSR {md} · day {day_n}", "title": f"⛔ SSR started {md}"}, **kw)


def sho_item(words, *, state="on", stale=False):
    return {"state": state, "stale": stale, "run": {"state": "passed", "days": 19, "_words": words}}


def read_of(ssr=None, sho=None, *, today=TODAY, faults=()):
    return {"ssr": {"kind": "ssr_recent_triggers", "status": "ok", "today": today, "by_symbol": dict(ssr or {})},
            "sho": {"items": dict(sho or {})}, "faults": list(faults)}


def reader_of(*a, **k):
    calls = []

    def reader(now, session):
        calls.append((now, session))
        return read_of(*a, **k)
    reader.calls = calls
    return reader


AKAN_TAG = ssr_row(PREV_ISO, 2)


def worked_rows(**extra):
    """S 2026-10-13 10:40 ET: AKAN an off-list ⛔ day-2 CS at $2.00 with 1.2M (+5% — fails GG's ≥25%); ETFX an ETF;
    BIGP $150 (over GG's band); THIN 999,999 shares; OLDP printed only yesterday; GGQ GG's own qualifier (+40%)."""
    rows = {"AKAN": snap_row(2.00, 1.90, vol=1_200_000), "ETFX": snap_row(20.0, 19.0, vol=5_000_000),
            "BIGP": snap_row(150.0, 140.0, vol=5_000_000), "THIN": snap_row(2.0, 1.9, vol=999_999),
            "OLDP": snap_row(2.0, 1.9, vol=5_000_000, when=at(15, 59, d=PREV)), "GGQ": snap_row(1.40, 1.00),
            "LOWC": snap_row(2.10, 2.00, vol=300_000)}
    rows.update(extra)
    return rows


def all_tags():
    return {s: {"ssr_recent": {"text": f"⛔ {s}", "day_n": 2, "triggered_on": PREV_ISO}}
            for s in ("AKAN", "ETFX", "BIGP", "THIN", "OLDP", "GGQ", "NOPE")}


# ── constants: every bound by NAME ────────────────────────────────────────────────────────────────────────────────
def test_the_bounds_are_existing_constants_by_name():
    assert SSN.ADD_MIN_VOLUME == GC.SCAN_MIN_VOLUME
    assert SSN.ADD_MAX_NEW_PER_PASS == GC.FLOAT_MAX_NEW_PER_PASS
    assert SSN.ADD_ON_OPEN is False
    assert SSN.SOURCE_KEYS == ("ssr_recent", "sho_past", "ssr_today", "hsi") and SSN.SOURCES_ON == SSN.SOURCE_KEYS
    assert SSN.ADD_SOURCES == ("ssr_recent", "sho_past", "ssr_today") and "hsi" not in SSN.ADD_SOURCES
    assert SSN.TRACKER_ADD_FIELD == "si_ssr_add" and SSN.ADD_FLAG == "add" and SSN.SOURCE == "si_ssr"
    assert set(SSN.GLYPHS) == set(SSN.SOURCE_KEYS)
    assert SSN.SKIP_REASONS == TN.SKIP_REASONS[:-1] + ("under_floor",) and "over_cap" not in SSN.SKIP_REASONS
    src = SRC_PATH.read_text(encoding="utf-8")
    assert "ADD_MIN_VOLUME = GC.SCAN_MIN_VOLUME" in src and "ADD_MAX_NEW_PER_PASS = GC.FLOAT_MAX_NEW_PER_PASS" in src


def test_NEGATIVE_no_number_is_typed_in_the_module():
    """No literal for days / volume / cap: the only numbers allowed are the 0 / 1 counter seeds."""
    tree = ast.parse(SRC_PATH.read_text(encoding="utf-8"))
    nums = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool)]
    assert set(nums) <= {0, 1}, nums
    src = SRC_PATH.read_text(encoding="utf-8")
    for lit in ("1_000_000", "1000000", "= 8", "PASS = 8"):
        assert lit not in src, lit


def test_NEGATIVE_the_module_reads_the_reg_sho_payload_only_never_its_run_engine_or_a_kick():
    src = SRC_PATH.read_text(encoding="utf-8")
    assert "reg_sho" + "_runs" not in src and "kick_refresh" not in src and "backfill_history" not in src
    assert "payload(kick=False" in src and "kick=True" not in src
    tree = ast.parse(src)
    mods = {(n.module or "") for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert not [m for m in mods if "runs" in m]
    for bad in ("requests", "httpx", "urllib", "fetch_", "refresh("):
        assert bad not in src, bad
    assert "b" + "ounce" not in src.lower() and "squeeze" not in src.lower()


# ── default_reader: stored reads only, each source fenced ─────────────────────────────────────────────────────────
def test_default_reader_reads_the_two_stored_engines(monkeypatch):
    seen = []
    monkeypatch.setattr(SSR, "recent_triggers", lambda now: seen.append(("ssr", now)) or {"by_symbol": {}},
                        raising=False)
    monkeypatch.setattr(RSH, "payload", lambda **k: seen.append(("sho", k)) or {"items": {}})
    out = SSN.default_reader(NOW, S)
    assert out == {"ssr": {"by_symbol": {}}, "sho": {"items": {}}, "faults": []}
    assert seen == [("ssr", NOW), ("sho", {"kick": False, "now": NOW})]


def test_NEGATIVE_one_raising_source_leaves_the_other_and_names_the_fault(monkeypatch):
    def boom(now):
        raise RuntimeError("mongo down")
    monkeypatch.setattr(SSR, "recent_triggers", boom, raising=False)
    monkeypatch.setattr(RSH, "payload", lambda **k: {"items": {"ZNB": sho_item("🔒 day 6 past close-out")}})
    out = SSN.default_reader(NOW, S)
    assert out["ssr"] is None and out["faults"] == ["ssr"] and out["sho"]["items"]
    monkeypatch.setattr(RSH, "payload", lambda **k: (_ for _ in ()).throw(RuntimeError("x")))
    assert SSN.default_reader(NOW, S)["faults"] == ["ssr", "sho"]


@pytest.mark.skipif(not hasattr(SSR, "recent_triggers") or not hasattr(RSH, "past_closeout_text"),
                    reason="WP be-ssr-words lands the two engines' functions; the final run executes this")
def test_the_engines_this_module_names_exist():
    assert callable(SSR.recent_triggers) and callable(RSH.past_closeout_text)
    assert SSR.SSR_RECENT_TRIGGER_DAYS == SSR.SSR_FOLLOWING_TRADING_DAYS
    assert isinstance(SSN.rules_clause(), str) and str(SSR.SSR_RECENT_TRIGGER_DAYS) in SSN.rules_clause()


# ── source_tags (PURE) ────────────────────────────────────────────────────────────────────────────────────────────
def test_source_tags_ssr_today_vs_recent_and_sho_past_relays_the_engine_words():
    tags = SSN.source_tags(read_of({"AKAN": AKAN_TAG, "CRMT": ssr_row(TODAY, 1), "BRK.B": ssr_row(TODAY, 1)},
                                   {"ZNB": sho_item("🔒 day 6 past close-out"), "DBGI": sho_item("🔒 day 2+ past")}))
    assert set(tags) == {"AKAN", "CRMT", "BRK-B", "ZNB", "DBGI"}                  # the pass's spelling (for_yahoo)
    assert set(tags["AKAN"]) == {"ssr_recent"} and tags["AKAN"]["ssr_recent"]["text"] == "⛔ SSR 10/12 · day 2"
    assert tags["AKAN"]["ssr_recent"]["day_n"] == 2 and tags["AKAN"]["ssr_recent"]["triggered_on"] == PREV_ISO
    assert set(tags["CRMT"]) == {"ssr_today"} and tags["CRMT"]["ssr_today"]["day_n"] == 1
    assert tags["ZNB"] == {"sho_past": {"text": "🔒 day 6 past close-out"}}


@pytest.mark.parametrize("item", [sho_item(None), sho_item("w", state="off"), sho_item("w", state="off", stale=True),
                                  "junk", {"state": "on", "run": None}, {"state": None, "run": {"state": "passed"}}],
                         ids=["not_past", "off", "off_stale", "junk", "no_run", "no_state"])
def test_NEGATIVE_sho_items_not_on_a_list_or_not_past_add_nothing(item):
    assert SSN.source_tags(read_of(sho={"ZNB": item})) == {}


def test_a_stale_list_item_still_on_and_past_close_out_is_tagged_refix_2026_11_24():
    """Refix 2026-11-24: the spec's 🔒 is "still on a Reg SHO list after its day-13 close-out date" — the engine's
    `state "on"`. A stale list's item is still "on" (the engine's chip shows it with its stale tail), so no extra filter."""
    tags = SSN.source_tags(read_of(sho={"ZNB": sho_item("🔒 day 6 past close-out", stale=True)}))
    assert tags == {"ZNB": {"sho_past": {"text": "🔒 day 6 past close-out"}}}


def test_lead_follows_SOURCE_KEYS_for_a_today_trigger_plus_past_close_out_HIS_CALL_9():
    """DBGI 11-24 shape (⛔ today + 🔒). The spec's §5.2 line expected ⛔ first; SOURCE_KEYS puts 🔒 first. The lead is
    whatever SOURCE_KEYS ranks first — pinned against the constant, so his call flips it with no test edit here."""
    tags = SSN.source_tags(read_of({"DBGI": ssr_row(TODAY, 1)}, {"DBGI": sho_item("🔒 day 10 past close-out")}))
    tb = SSN.tag_block("DBGI", tags["DBGI"], None, add=False)
    want = sorted(("ssr_today", "sho_past"), key=SSN.SOURCE_KEYS.index)
    assert tb["keys"] == want and tb["lead"] == tags["DBGI"][want[0]]["text"]
    assert tb["text"] == SSN.LEAD_JOIN.join(tags["DBGI"][k]["text"] for k in want)
    assert SSN.SOURCE_KEYS.index("sho_past") < SSN.SOURCE_KEYS.index("ssr_today")   # shipped order (HIS CALL #9)
    assert tb["lead"] == "🔒 day 10 past close-out"


def test_NEGATIVE_junk_reads_add_nothing_and_never_raise(monkeypatch):
    for junk in (None, {}, {"ssr": "x", "sho": 3}, {"ssr": {"by_symbol": {"A": None, "": AKAN_TAG}}},
                 {"ssr": {"by_symbol": {"A": dict(AKAN_TAG, tag_text="  ")}}}):
        assert SSN.source_tags(junk) == {}
    monkeypatch.setattr(RSH, "past_closeout_text", lambda run: 1 / 0, raising=False)
    assert SSN.source_tags(read_of(sho={"ZNB": sho_item("w")})) == {}             # a raising word build → not past


def test_NEGATIVE_a_source_switched_off_tags_nothing(monkeypatch):
    monkeypatch.setattr(SSN, "SOURCES_ON", ("hsi",))
    assert SSN.source_tags(read_of({"AKAN": AKAN_TAG}, {"ZNB": sho_item("w")})) == {}


# ── tag_block / ctx_tags ──────────────────────────────────────────────────────────────────────────────────────────
def test_tag_block_orders_by_the_lead_precedence_and_joins_every_source():
    src = {"ssr_today": {"text": "⛔ SSR 10/13 · day 1", "day_n": 1, "triggered_on": TODAY},
           "sho_past": {"text": "🔒 day 6 past close-out"}}
    tb = SSN.tag_block("DBGI", src, {"text": "🩳 31% short interest · EXTREME"}, add=False)
    assert tb["keys"] == ["sho_past", "ssr_today", "hsi"] and tb["lead"] == "🔒 day 6 past close-out"
    assert tb["text"] == "🔒 day 6 past close-out · ⛔ SSR 10/13 · day 1 · 🩳 31% short interest · EXTREME"
    assert tb["glyphs"] == "🔒⛔🩳" and tb["ssr_day"] == 1 and tb["triggered_on"] == TODAY
    assert tb["sho_text"] == "🔒 day 6 past close-out" and tb["hsi_text"].startswith("🩳") and tb["add"] is False
    assert set(tb) == set(SSN.TAG_FIELDS)
    akan = SSN.tag_block("AKAN", {"ssr_recent": AKAN_TAG | {"text": AKAN_TAG["tag_text"]}}, None, add=False)
    assert akan["lead"] == "⛔ SSR 10/12 · day 2" and akan["keys"] == ["ssr_recent"] and akan["ssr_day"] == 2
    json.dumps(tb, allow_nan=False)


def test_NEGATIVE_tag_block_none_when_untagged_and_a_lapsed_add_keeps_only_its_flag():
    assert SSN.tag_block("ZZZ", None, None, add=False) is None
    assert SSN.tag_block("ZZZ", {"ssr_recent": {"text": "  "}}, {"text": None}, add=False) is None
    lapsed = SSN.tag_block("AKAN", None, None, add=True)
    assert lapsed == {"keys": [], "lead": None, "text": None, "glyphs": None, "ssr_day": None, "triggered_on": None,
                      "sho_text": None, "hsi_text": None, "add": True}
    nan = SSN.tag_block("AKAN", {"ssr_recent": {"text": "⛔ x", "day_n": float("nan")}}, None, add=False)
    assert nan["ssr_day"] is None and json.dumps(nan, allow_nan=False)


def test_ctx_tags_tags_every_read_name_hsi_by_the_one_rule(monkeypatch):
    seen = []

    def classify(b, fr):
        seen.append((b, fr))
        return {"listed": b is not None, "tier": "EXTREME", "pct_card": 31.0, "float_check": None}
    monkeypatch.setattr(HS, "classify", classify)
    block = {SSN.TAGS_KEY: {"AKAN": {"ssr_recent": {"text": "⛔ SSR 10/12 · day 2", "day_n": 2}}}}
    out = SSN.ctx_tags(block, ["AKAN", "KITT", "ZZZ", "NEWA"], {"KITT": {"shares": 1}}, {"NEWA"}, today=S,
                       si_read=lambda syms: {"KITT": {"pct_of_float": 31.0}})
    assert set(out) == {"AKAN", "KITT", "NEWA"}                                      # NEGATIVE: ZZZ untagged → no key
    assert out["KITT"]["keys"] == ["hsi"] and out["KITT"]["lead"].startswith("🩳 31")
    assert out["AKAN"]["lead"] == "⛔ SSR 10/12 · day 2" and out["AKAN"]["add"] is False
    assert out["NEWA"]["add"] is True and out["NEWA"]["keys"] == []
    assert ({"pct_of_float": 31.0}, {"shares": 1}) in seen                           # this pass's float, the ONE rule


def test_NEGATIVE_a_failed_si_read_drops_only_the_hsi_keys_and_a_raise_is_empty(monkeypatch):
    block = {SSN.TAGS_KEY: {"AKAN": {"ssr_recent": {"text": "⛔ SSR 10/12 · day 2"}}}}
    out = SSN.ctx_tags(block, ["AKAN", "KITT"], {}, set(), today=S, si_read=lambda syms: None)
    assert set(out) == {"AKAN"}
    assert SSN.ctx_tags({"error": "X"}, ["AKAN"], {}, set(), today=S) == {}           # a failed step: no ⛔ / 🔒 tag
    monkeypatch.setattr(SSN, "tag_block", lambda *a, **k: 1 / 0)
    assert SSN.ctx_tags(block, ["AKAN"], {}, set(), today=S) == {}                    # FENCED


# ── resolve: the ONE add check + the floor + the per-pass bound ───────────────────────────────────────────────────
def test_POSITIVE_an_off_list_ssr_day_2_cs_at_2_dollars_with_1_2m_is_added():
    res = SSN.resolve({"AKAN": {"ssr_recent": {"text": "⛔"}}}, worked_rows(), S, TYPES, [], set(), on_open=False)
    (row,) = res["added"]
    assert row["symbol"] == "AKAN" and row["source"] == SSN.SOURCE and row["si_ssr_keys"] == ["ssr_recent"]
    assert row["volume"] == 1_200_000 and math.isclose(row["price"], 2.0)
    assert res["tagged"] == res["kept"] == res["queued"] == [] and res["skips"] == {}


def test_NEGATIVE_every_failed_check_is_skipped_and_counted_by_reason():
    q = [{"symbol": "GGQ", "price": 1.4, "volume": 3e6}]
    res = SSN.resolve(all_tags(), worked_rows(), S, TYPES, q, set(), on_open=False)
    assert [r["symbol"] for r in res["added"]] == ["AKAN"]
    assert res["tagged"] == ["GGQ"]                                                  # GG's own qualifier: tagged
    assert res["skips"] == {"not_in_snapshot": ["NOPE"], "not_dated_session": ["OLDP"], "type_out": ["ETFX"],
                            "out_of_band": ["BIGP"], "under_floor": ["THIN"]}
    assert list(res["skips"]) == [k for k in SSN.SKIP_REASONS if k in res["skips"]]


def test_NEGATIVE_a_qualifier_or_a_promo_add_is_tagged_once_never_a_second_row():
    quals = [{"symbol": "GGQ"}, {"symbol": "LOWC", "source": PN.SOURCE, "promo": True}]
    res = SSN.resolve({"GGQ": {"ssr_today": {"text": "⛔"}}, "LOWC": {"sho_past": {"text": "🔒"}}}, worked_rows(), S,
                      TYPES, quals, set(), on_open=False)
    assert res["added"] == [] and res["tagged"] == ["GGQ", "LOWC"]
    res = SSN.resolve({"AKAN": {"ssr_recent": {"text": "⛔"}}}, worked_rows(), S, TYPES, [], {"AKAN"},
                      on_open=False)
    assert res["added"] == [] and res["kept"] == ["AKAN"]                             # listed off a stored doc: kept


def _twelve():
    rows, tags = {}, {}
    for i in range(12):
        s = f"N{i:02d}"
        rows[s] = snap_row(2.0, 1.9, vol=2_000_000 + i * 100_000)
        tags[s] = {"ssr_today": {"text": "⛔"}} if i % 3 else {"ssr_recent": {"text": "⛔"}}
    return rows, tags, {s: "CS" for s in rows}


def test_twelve_eligible_adds_eight_and_queues_four_ordered_by_source_then_volume():
    rows, tags, types = _twelve()
    res = SSN.resolve(tags, rows, S, types, [], set(), on_open=False)
    added = [r["symbol"] for r in res["added"]]
    assert len(added) == SSN.ADD_MAX_NEW_PER_PASS == 8 and len(res["queued"]) == 4
    assert added[:4] == ["N09", "N06", "N03", "N00"]                                 # ⛔ recent first, volume desc
    assert set(added) | set(res["queued"]) == set(rows) and not set(added) & set(res["queued"])


def test_the_bound_is_read_by_name(monkeypatch):
    rows, tags, types = _twelve()
    monkeypatch.setattr(SSN, "ADD_MAX_NEW_PER_PASS", 3)
    res = SSN.resolve(tags, rows, S, types, [], set(), on_open=False)
    assert len(res["added"]) == 3 and len(res["queued"]) == 9


def test_NEGATIVE_on_the_open_nothing_is_added_everything_queued():
    rows, tags, types = _twelve()
    res = SSN.resolve(tags, rows, S, types, [], set(), on_open=True)
    assert res["added"] == [] and len(res["queued"]) == 12


def test_NEGATIVE_hsi_only_names_are_never_added():
    res = SSN.resolve({"AKAN": {"hsi": {"text": "🩳"}}}, worked_rows(), S, TYPES, [], set(), on_open=False)
    assert res == {"added": [], "tagged": [], "kept": [], "queued": [], "skips": {}}


# ── run_step (FENCED) + recount + trim + the next pass ───────────────────────────────────────────────────────────
def _scan_result(quals=()):
    return {"qualifiers": [dict(q) for q in quals], "counts": {"qualifiers": len(quals), "held_split": 0,
                                                               "split_failed": 0}}


def test_run_step_adds_counts_and_keeps_the_tag_map_in_memory_only():
    st = fake_store()
    result = _scan_result([{"symbol": "GGQ", "price": 1.4, "volume": 3e6, "change_pct": 40.0}])
    reader = reader_of({"AKAN": AKAN_TAG, "THIN": ssr_row(TODAY, 1), "GGQ": ssr_row(TODAY, 1)})
    blk = SSN.run_step(st, NOW, S, worked_rows(), result, types=TYPES, reader=reader, good=True, on_open=False)
    assert reader.calls == [(NOW, S)]
    assert blk["added"] == ["AKAN"] and blk["tagged"] == ["GGQ"] and blk["skips"] == {"under_floor": ["THIN"]}
    assert blk["names"] == 3 and blk["on_open"] is False and blk["faults"] == []
    assert {k: result["counts"][k] for k in SSN.COUNT_KEYS} == {
        "si_ssr_added": 1, "si_ssr_tagged": 1, "si_ssr_queued": 0, "si_ssr_skipped": 0, "si_ssr_under_floor": 1,
        "si_ssr_failed": 0, "si_ssr_push_held": 0}
    assert [q["symbol"] for q in result["qualifiers"]] == ["GGQ", "AKAN"]
    assert set(blk[SSN.TAGS_KEY]) == {"AKAN", "THIN", "GGQ"}
    stored = SSN.stored_block(blk)
    assert SSN.TAGS_KEY not in stored and json.dumps(stored, allow_nan=False)
    SSN.recount(result)
    assert result["counts"]["qualifiers"] == 1 and result["counts"]["si_ssr_added"] == 1


def test_NEGATIVE_a_failed_snapshot_or_a_raising_reader():
    st = fake_store()
    result = _scan_result()
    assert SSN.run_step(st, NOW, S, {}, result, types=TYPES, reader=reader_of(), good=False, on_open=False) is None
    assert result == _scan_result()                                                   # untouched

    def boom(now, session):
        raise RuntimeError("down")
    blk = SSN.run_step(st, NOW, S, worked_rows(), result, types=TYPES, reader=boom, good=True, on_open=False)
    assert blk == {"error": "RuntimeError"} and result["qualifiers"] == []
    assert result["counts"]["si_ssr_failed"] == 1 and result["counts"]["si_ssr_added"] == 0
    assert SSN.ctx_tags(blk, ["AKAN"], {}, set(), today=S) == {}
    SSN.trim_block(blk, result)                                                       # a failed block is left as is
    assert blk == {"error": "RuntimeError"}


def test_NEGATIVE_on_the_open_zero_added_and_the_tags_still_serve():
    st = fake_store()
    result = _scan_result()
    blk = SSN.run_step(st, NOW, S, worked_rows(), result, types=TYPES, reader=reader_of({"AKAN": AKAN_TAG}),
                       good=True, on_open=True)
    assert blk["added"] == [] and blk["queued"] == ["AKAN"] and result["qualifiers"] == []
    assert result["counts"]["si_ssr_queued"] == 1 and blk["on_open"] is True
    assert SSN.ctx_tags(blk, ["AKAN"], {}, set(), today=S)["AKAN"]["lead"] == "⛔ SSR 10/12 · day 2"


def test_the_queued_names_land_on_the_next_pass():
    rows, tags, types = _twelve()
    st = fake_store()
    ssr = {s: (AKAN_TAG if "ssr_recent" in t else ssr_row(TODAY, 1)) for s, t in tags.items()}
    r1 = _scan_result()
    b1 = SSN.run_step(st, at(10, 31), S, rows, r1, types=types, reader=reader_of(ssr), good=True, on_open=False)
    assert len(b1["added"]) == 8 and len(b1["queued"]) == 4
    SC.record_scan(st, S, at(10, 31), r1, fetch_splits=lambda sym, since: [])
    r2 = _scan_result()
    b2 = SSN.run_step(st, at(10, 36), S, rows, r2, types=types, reader=reader_of(ssr), good=True, on_open=False)
    assert sorted(b2["added"]) == sorted(b1["queued"]) and sorted(b2["kept"]) == sorted(b1["added"])
    assert b2["queued"] == [] and r2["counts"]["si_ssr_tagged"] == 8
    assert SSN.added_symbols(st.scan_docs([S])) == set(rows) - set(b1["queued"])


def test_trim_block_follows_the_split_hold_out():
    result = _scan_result([{"symbol": "AKAN", "source": SSN.SOURCE}])
    blk = {"added": ["AKAN", "SPLT"], "tagged": ["GGQ"], "kept": ["OLD"]}
    result["counts"]["si_ssr_tagged"] = 2
    SSN.trim_block(blk, result)
    assert blk["added"] == ["AKAN"] and blk["tagged"] == [] and result["counts"]["si_ssr_tagged"] == 1


def test_NEGATIVE_recount_leaves_a_pass_without_the_source_alone():
    result = _scan_result([{"symbol": "GGQ"}, {"symbol": "MXCT", "source": TN.SOURCE}])
    result["counts"]["qualifiers"] = 7
    SSN.recount(result)
    assert result["counts"] == {"qualifiers": 7, "held_split": 0, "split_failed": 0}


def test_note_push_held_counts_only_a_good_block():
    result = {"counts": dict.fromkeys(SSN.COUNT_KEYS, 0)}
    blk = {"added": []}
    SSN.note_push_held(blk, result, 2)
    assert blk["push_held"] == 2 and result["counts"]["si_ssr_push_held"] == 2
    bad = {"error": "X"}
    SSN.note_push_held(bad, result, 5)
    assert bad == {"error": "X"} and result["counts"]["si_ssr_push_held"] == 2


# ── added_symbols / is_add ───────────────────────────────────────────────────────────────────────────────────────
def test_added_symbols_this_pass_row_decides_else_the_newest_scan_doc():
    docs = [{"symbol": "AKAN", "date": PREV_ISO, "last": {"source": SSN.SOURCE}},
            {"symbol": "OLD", "date": PREV_ISO, "last": {"source": SSN.SOURCE}},
            {"symbol": "OLD", "date": TODAY, "last": {}},                             # GG listed it today: not an add
            {"symbol": "PRM", "date": TODAY, "last": {"source": PN.SOURCE}}]
    assert SSN.added_symbols(docs) == {"AKAN"}
    assert SSN.added_symbols(docs, [{"symbol": "AKAN"}]) == set()                    # this pass's GG row decides
    assert SSN.added_symbols((), [{"symbol": "NEW", "source": SSN.SOURCE}]) == {"NEW"}
    assert SSN.added_symbols(None) == set()


def test_is_add_reads_the_read_doc_flag_or_the_tracker_marker():
    assert SSN.is_add({"ctx": {"si_ssr": {"add": True}}}) and SSN.is_add({"si_ssr_add": True})
    for no in ({"ctx": {"si_ssr": {"add": False}}}, {"ctx": {"si_ssr": "x"}}, {"si_ssr_add": 1}, {}, None, "x"):
        assert SSN.is_add(no) is False, no


# ── words ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_rules_clause_is_built_from_the_constants(monkeypatch):
    monkeypatch.setattr(SSR, "SSR_RECENT_TRIGGER_DAYS", SSR.SSR_FOLLOWING_TRADING_DAYS, raising=False)
    t = SSN.rules_clause()
    assert f"{SSN.ADD_MIN_VOLUME:,}" in t and f"at most {SSN.ADD_MAX_NEW_PER_PASS} new a pass" in t
    assert "none on the open" in t and "never rings" in t and "UNMEASURED" in t
    monkeypatch.setattr(SSN, "ADD_MAX_NEW_PER_PASS", 3)
    assert "at most 3 new a pass" in SSN.rules_clause()
    assert "b" + "ounce" not in t.lower() and "squeeze" not in t.lower() and "earliest" not in t.lower()


def test_NEGATIVE_the_module_is_not_imported_by_the_gates():
    for name in ("alerts.py", "potential.py", "tab.py", "ledger.py", "vol_dried.py", "audited_pass.py"):
        src = (ROOT / "chart_maps" / "gajjala" / name).read_text(encoding="utf-8")
        assert "si_ssr_names" not in src, name
    assert inspect.getsource(SSN.run_step).count("candidate_row") == 0               # resolve owns the ONE check
    assert "TN.candidate_row(" in inspect.getsource(SSN.resolve)


# ── the replay script (scripts/gajjala_si_ssr_replay.py) — read-only, approximate ────────────────────────────────
def test_the_replay_landing_clocks_follow_the_per_pass_bound():
    from scripts import gajjala_si_ssr_replay as RP
    clocks = RP.pass_clocks(S)
    assert clocks[0].strftime("%H:%M") == "04:01" and clocks[-1].strftime("%H:%M") == "20:01"
    eligible = [f"N{i:02d}" for i in range(12)]
    land = RP.landing_clocks(eligible, clocks, SSN.ADD_MAX_NEW_PER_PASS)
    assert [land[s] for s in eligible[:8]] == ["04:01"] * 8 and [land[s] for s in eligible[8:]] == ["04:06"] * 4
    assert RP.landing_clocks(["A", "B"], clocks[:1], 1) == {"A": "04:01", "B": None}   # NEGATIVE: past the last pass
    assert RP.landing_clocks(["A"], clocks, 0) == {"A": None}                         # NEGATIVE: a zero bound adds none


def test_NEGATIVE_the_replay_never_writes_never_sends_and_says_approximate():
    src = (ROOT / "scripts" / "gajjala_si_ssr_replay.py").read_text(encoding="utf-8")
    for bad in ("update_one", "insert_one", "insert_many", "replace_one", "delete_", "upsert", "record_pass",
                "ensure_indexes", "notify_", "send(", "_load_day(", "kick=True"):
        assert bad not in src.replace("_dry_load_day(", ""), bad
    assert "_dry_load_day(" in src and "_dry_status_lookup" in src and "APPROXIMATE" in src
    assert "SSN.resolve(" in src and "SSN.source_tags(" in src and "SSN.default_reader(" in src   # the module's own path


# ── 2026-11-25: the land-order interlock (watch_keeps_adds_out) is DROPPED — be-pass and be-watch ship in ONE commit,
# so the Watch's C2 filter (auto.py `_si_ssr_adds`) is always in the same tree; its tests live in
# test_gajjala_watch_si_ssr_2026_11_24.py. The interlock's own tests went with it; these pins stay.
def test_NEGATIVE_the_names_module_never_imports_the_watch():
    tree = ast.parse(SRC_PATH.read_text(encoding="utf-8"))
    mods = {(n.module or "") for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    mods |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not [m for m in mods if "gajjala_watch" in m], mods
    assert "import_module" not in SRC_PATH.read_text(encoding="utf-8")


def test_NEGATIVE_the_dropped_interlock_is_gone_for_good():
    src = SRC_PATH.read_text(encoding="utf-8")
    for gone in ("watch_keeps_adds_out", "WATCH_FILTER_PATH", "WATCH_HELD", "import ast", "from pathlib"):
        assert gone not in src, gone
    assert "adds_on" not in inspect.signature(SSN.resolve).parameters
    assert "watch_ready" not in inspect.signature(SSN.run_step).parameters

