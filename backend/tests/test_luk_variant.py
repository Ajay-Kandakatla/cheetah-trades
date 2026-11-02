"""chart_maps/luk/variant.py — 🥇 Luk's `Variant` INSTANCE of GG's frozen dataclass (BUILD SPEC luk-tab §3.3, WP-A1).

Pins: GG's registry is untouched (by_key / by_tab / VARIANTS); `gajjala.variant.push_mode(LUK)` fails CLOSED to
"shadow" whatever LC.LUK_PUSH_MODE holds (GC has no LUK_PUSH_MODE — it is NOT the Luk reader); Luk's own reader is
"live" since 2026-11-01 (Ajay: "Lets make it live. also alerts too.") and "shadow" for anything but exactly "live";
send_setup = "notify_luk_setup" reached through `gajjala.alerts._default_send(…, LUK)`; the generic numbers read GC's
names. NEGATIVE: `gajjala.ledger._record_from(LUK)` and `gajjala.variant.served_block(LUK)` raise — so an import guard
over every chart_maps/luk/*.py allows only the GENERIC gajjala.ledger names and never V.served_block / word / words.
"""
from __future__ import annotations

import ast
import pathlib
from datetime import date

import pytest

from chart_maps.gajjala import alerts as GA
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as GL
from chart_maps.gajjala import variant as V
from chart_maps.luk import constants as LC
from chart_maps.luk import variant as LV
from chart_maps.luk.variant import LUK

PKG = pathlib.Path(LV.__file__).resolve().parent
LEDGER_ALLOWED = frozenset({"bars_from_frame", "_default_load_day", "_today_load", "plan_of", "rang_of", "_D", "_num",
                            "_aware", "_iso_t", "_px", "_pct", "SETTLE", "ONE_MIN", "ET", "UTC",
                            "LINES",    # WIDENED 2026-11-01 (go-live): the 🏁 row line words, imported never retyped
                            # WIDENED 2026-11-02 (spec luk-track §3.3.2 + the A+ chart keys / titles): 🏁 like 🚩's +
                            # 🔁 one count per stock per day — GG's served-block words, helpers and THE one dedupe
                            # engine, imported never retyped. Still NOT allowed: grade / _record_from / rows_for /
                            # filled_grade (Luk has its own fill).
                            "dedupe_trades", "dup_count_text", "DUP_RULE_TEXT", "DUP_TEXT", "_aplus_cell",
                            "_counts_blank", "_counts_text", "_categories", "_sorts", "_win_pct", "_dow_md", "_plural",
                            "BUCKETS", "BUCKET_TEXT", "FLAG_BUCKETS", "CATEGORY_PARAM", "CATEGORY_EMPTY_TEXT",
                            "SORT_PARAM", "SORT_KEYS", "KIND_TEXT", "RANG_TEXT", "NO_TIME_TEXT", "KIND_EMPTY_TEXT",
                            "APLUS_CHART_KEYS", "APLUS_CHART_TITLES"})
VARIANT_FORBIDDEN = frozenset({"served_block", "word", "words", "_WORDS"})
LEDGER_MOD = "chart_maps.gajjala.ledger"
VARIANT_MOD = "chart_maps.gajjala.variant"


def test_the_instance():
    assert isinstance(LUK, V.Variant)
    assert (LUK.key, LUK.tab, LUK.label) == ("luk", LC.LUK_TAB, LC.LUK_TAB_LABEL)
    assert (LUK.primary, LUK.slow, LUK.tfs) == ("5m", "60m", ("1m", "5m", "60m"))
    assert LUK.rules_map == {"1m": "1min", "5m": "5min", "60m": "60min"}
    assert (LUK.store_prefix, LUK.claim_prefix, LUK.push_kind_setup) == ("luk", "LUK", LC.LUK_KIND)
    # FLIPPED 2026-11-01 (Ajay: "Lets make it live. also alerts too."): send_setup "" → "notify_luk_setup"
    assert (LUK.send_setup, LUK.send_potential, LUK.lane, LUK.ledger_push_states, LUK.borrows) == (
        "notify_luk_setup", "", False, (), ())
    assert (LUK.api_base, LUK.record_from_const, LUK.push_mode_const) == ("/chart-maps/luk", "LUK_RECORD_FROM",
                                                                          "LUK_PUSH_MODE")
    assert hasattr(LC, LUK.record_from_const) and hasattr(LC, LUK.push_mode_const)


def test_ggs_registry_is_untouched():
    assert V.by_key("luk") is None and V.by_tab("luk") is None
    assert V.VARIANTS == (V.GG5, V.GG1, V.GGA)
    assert V.for_api_base("/chart-maps/luk") is None
    assert V.is_gg5(LUK) is False and V.is_audited(LUK) is False
    assert V.of(LUK) is LUK


def test_the_generic_numbers_read_gcs_names():
    assert V.cadence_sec(LUK) == GC.PASS_CADENCE_SEC == 300
    assert V.stale_after_sec(LUK) == GC.STALE_AFTER_SEC
    assert V.tape_tf_min(LUK) == GC.LEDGER_TAPE_TF_MIN
    assert V.tape_bars_max(LUK) == GC.LEDGER_TAPE_BARS_MAX
    assert [V.frame_minutes(tf, LUK) for tf in LUK.tfs] == [1, 5, 60]
    assert V.frame_minutes("15m", LUK) == 5                 # not a Luk frame → the primary's minutes


def test_the_gate_primitives_take_it_as_is():
    d = date(2026, 11, 3)
    assert GA.claim_key(d, "abc", "pullback_reversal", LUK) == "LUK:2026-11-03|ABC|pullback_reversal"
    assert GA.shadow_key(d, "abc", "pullback_reversal", LUK).endswith("LUK:2026-11-03|ABC|pullback_reversal")
    assert GA.max_entry_age_sec(LUK) == GC.PASS_CADENCE_SEC + GC.BAR_SETTLE_SEC == 330


def test_push_mode_is_live_by_his_word():
    # FLIPPED 2026-11-01 (Ajay: "Lets make it live. also alerts too."): Luk's own reader says live
    assert LV.push_mode() == "live" and LC.LUK_PUSH_MODE == "live"
    assert V.push_mode(LUK) == "shadow"                     # GG's reader: GC has no LUK_PUSH_MODE — NOT the reader
    assert not hasattr(GC, "LUK_PUSH_MODE")


def test_NEGATIVE_no_luk_potential_sender():
    assert LUK.send_potential == "" and LUK.push_kind_potential == "luk_potential"
    from push import hooks
    assert not hasattr(hooks, "notify_luk_potential")


def test_the_default_send_resolves_notify_luk_setup_by_name(monkeypatch):
    from push import hooks
    seen = []
    monkeypatch.setattr(hooks, "notify_luk_setup", lambda **k: seen.append(k) or {"sent": 1}, raising=False)
    owner = "owner-local-part" + chr(64) + "example.com"
    assert GA._default_send(owner, {"title": "t"}, LUK) == {"sent": 1}
    assert seen == [{"owner": owner, "payload": {"title": "t"}}]


def test_NEGATIVE_the_audited_variant_still_refuses_to_send():
    from chart_maps.gajjala.audited_rules import NEVER_SENDS
    with pytest.raises(RuntimeError) as e:
        GA._default_send("o", {"title": "t"}, V.GGA)
    assert str(e.value) == NEVER_SENDS


def test_NEGATIVE_an_empty_send_setup_refuses(monkeypatch):
    import dataclasses
    from chart_maps.gajjala.audited_rules import NEVER_SENDS
    mute = dataclasses.replace(LUK, send_setup="")
    with pytest.raises(RuntimeError) as e:
        GA._default_send("o", {"title": "t"}, mute)
    assert str(e.value) == NEVER_SENDS


def test_ggs_push_mode_stays_shadow_under_a_live_patch_of_lc(monkeypatch):
    monkeypatch.setattr(LC, "LUK_PUSH_MODE", "live")
    assert V.push_mode(LUK) == "shadow"                     # GC has no LUK_PUSH_MODE → fail closed
    assert GA.push_mode(LUK) == "shadow"                    # the gate's reader too
    assert LV.push_mode() == "live"                         # Luk's own reader follows LC


@pytest.mark.parametrize("junk", ["LIVE", " live", None, "", "on", True, "shadow"])
def test_negative_lucks_own_reader_says_live_only_for_exactly_live(monkeypatch, junk):
    monkeypatch.setattr(LC, "LUK_PUSH_MODE", junk)
    assert LV.push_mode() == "shadow"


def test_negative_ggs_record_reader_raises_on_the_luk_variant():
    with pytest.raises(AttributeError):
        GL._record_from(LUK)
    with pytest.raises(AttributeError):
        V.served_block(LUK)


# ── the import guard over chart_maps/luk/*.py ────────────────────────────────────────────────────────────────────
def guard_errors(src: str) -> list:
    """Names a Luk module takes from gajjala.ledger outside LEDGER_ALLOWED, or GG's word / served_block readers."""
    tree = ast.parse(src)
    errs, aliases = [], {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == LEDGER_MOD:
                errs += [("ledger", a.name) for a in node.names if a.name not in LEDGER_ALLOWED]
            elif mod == VARIANT_MOD:
                errs += [("variant", a.name) for a in node.names if a.name in VARIANT_FORBIDDEN]
            elif mod == "chart_maps.gajjala":
                for a in node.names:
                    if a.name in ("ledger", "variant"):
                        aliases[a.asname or a.name] = a.name
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name in (LEDGER_MOD, VARIANT_MOD) and a.asname:
                    aliases[a.asname] = a.name.rsplit(".", 1)[1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in aliases:
            kind = aliases[node.value.id]
            if kind == "ledger" and node.attr not in LEDGER_ALLOWED:
                errs.append(("ledger", node.attr))
            if kind == "variant" and node.attr in VARIANT_FORBIDDEN:
                errs.append(("variant", node.attr))
    return errs


@pytest.mark.parametrize("path", sorted(PKG.glob("*.py")), ids=lambda p: p.name)
def test_no_luk_module_reaches_ggs_variant_words_or_ledger_internals(path):
    assert guard_errors(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("src,hit", [
    ("from chart_maps.gajjala.ledger import grade", ("ledger", "grade")),
    ("from chart_maps.gajjala.ledger import _record_from", ("ledger", "_record_from")),
    ("from chart_maps.gajjala import ledger as GL\nGL.grade_step(1)", ("ledger", "grade_step")),
    ("import chart_maps.gajjala.ledger as GL\nGL.rows_for(1)", ("ledger", "rows_for")),
    ("from chart_maps.gajjala import variant as V\nV.served_block(1)", ("variant", "served_block")),
    ("from chart_maps.gajjala.variant import word", ("variant", "word")),
    ("from chart_maps.gajjala.ledger import filled_grade", ("ledger", "filled_grade")),         # 2026-11-02: Luk has its own fill
    ("from chart_maps.gajjala import ledger as GL\nGL._aplus_counts([])", ("ledger", "_aplus_counts")),  # 2026-11-02
    ("from chart_maps.gajjala.ledger import _aplus_charts", ("ledger", "_aplus_charts")),       # 2026-11-02
])
def test_negative_the_import_guard_catches(src, hit):
    assert hit in guard_errors(src)


def test_the_import_guard_allows_the_generic_primitives():
    ok = ("from chart_maps.gajjala.ledger import bars_from_frame, plan_of, rang_of, SETTLE\n"
          "from chart_maps.gajjala import ledger as GL\nGL._default_load_day('X', 1)\n"
          "from chart_maps.gajjala import variant as V\nV.push_mode(1); V.cadence_sec(1)\n")
    assert guard_errors(ok) == []
    for name in LEDGER_ALLOWED:
        assert hasattr(GL, name), name
