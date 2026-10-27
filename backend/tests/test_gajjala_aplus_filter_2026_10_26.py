"""chart_maps/gajjala/ledger.py — 🎯 A+ filter + the win / loss charts on the 🏁 Track record (2026-10-26, BUILD_SPEC25
§3.1 / §3.2 / §4 WP-A).

Ajay 2026-10-26 ~20:30 ET, verbatim: "Once done can you give me a  A+ filter in the track record I wanna see how many of
the A+ were successful draw some charts to show the winning vs losing percentages of A+ trades please" — and ~20:55 ET:
"I need these charts on Track Record page".

served_block serves the kind chips (ROW counts), `kind_param`, `kind_empty_text`, `categories_aplus` and the always-served
`aplus` block: the A+ rows (sent + shadow, never ⏪ replayed) pooled in ONE % of their own by the headline's own thin rule
(`_tally_into`), the house sentences, three charts whose every number-in-text is served, and its own capped rows. The 🧠
headline is byte-for-byte unchanged (PRE_SHA, frozen from 4d4058c9 before BUILD_SPEC25). UNMEASURED — no edge claim.

Every store is SYNTHETIC (cat_store + live A+ entries graded by the REAL LG.grade on replay_tape) and named so; the
network is never touched. NEGATIVES are mandatory and marked.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from tests.test_gajjala_ledger import B_WORD, D15, D16, SEPA_NAMES, aplus_doc, et, pot_doc, store_with
from tests.test_gajjala_ledger_categories import _graded, cat_store, served
from tests.test_gajjala_tab import _walk_strings
from tests.test_gajjala_track_record_tab import NOW, board, golden_store, replay_tape

D14 = date(2026, 10, 14)                      # a Wednesday, inside the 5d window of 2026-10-16
INT = re.compile(r"\d+")

# 11 — frozen from 4d4058c9 before BUILD_SPEC25 (step 0: the untouched code, hermetic cheetah-api:latest container)
PRE_KEYS = ("counts", "counts_text", "shadow_text", "entries_text", "replayed_text", "days", "categories",
            "categories_timeline", "more_text")
PRE_SHA = {"cat_store": "13dd7c4bc1d834b61ffccf6c11b217833d17df10e5938b7f074b155a497345d7",
           "today": "6880c02375217be276ae5e17ee1da1890f979ec42165d69f2f31649d46bd701f",
           "5d": "1bdd7cd0ff696eeaae94c1cb064df869e0c09145f2dec0dda5c257996910e2f5",
           "yesterday": "3cbf5949f79765dc58a452fb2139efda93f8b94223963d69fb700f2903d1ce48"}


@pytest.fixture(autouse=True)
def _clean_memo(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()
    yield
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()


# ── builders (SYNTHETIC) ─────────────────────────────────────────────────────────────────────────────────────────
def live_entry(sym, setup, d, outcome):
    """SYNTHETIC live A+ entry (a `GG:` claim in state pushed, 10:35 ET, trigger 1.23 / stop 1.11) + its ledger doc:
    same = LG.grade on replay_tape(d, outcome) (fill 10:40, the 10:41 minute decides); next absent (pending)."""
    doc = aplus_doc(sym, setup, d, et(d, 10, 35), 1.23, 1.11, state="pushed")
    return doc, _graded(doc, "aplus", outcome, tape=replay_tape(d, outcome=outcome))


LIVE = (("LVW", "kiss_fly", D15, "win"), ("LVL", "reversal_squeeze", D14, "loss"))


def ap_store(*, live=LIVE, base=True, extra_win=False, replay=True):
    """SYNTHETIC: cat_store (🧠 PWN win / PNL open→loss; A+ shadow THN thin-loss, NEN no entry, OPN open; ⏪ RPL win)
    + the live A+ entries given. `base=False` → only the live entries; `replay=False` drops the ⏪ doc."""
    st = cat_store(extra_win=extra_win) if base else store_with()
    if not replay:
        st.coll(ST.REPLAY).docs.clear()
    for args in live:
        doc, led = live_entry(*args)
        st.coll(ST.ALERTS).docs[doc["_id"]] = doc
        st.coll(ST.LEDGER).docs[led["_id"]] = led
    return st


def _days_rows(days):
    return [r for d in days for r in d["rows"]]


def _cells(ap):
    """Every served chart cell with its horizon: the outcome bars, then every by_setup / by_day group cell."""
    ch = {c["key"]: c for c in ap["charts"]}
    out = [(b["key"], b) for b in ch["outcomes"]["bars"]]
    for g in ch["by_setup"]["rows"] + ch["by_day"]["cols"]:
        out += [(h, g[h]) for h in GC.LEDGER_HORIZONS]
    return out


def _drop_null_trader_text(o):
    """WIDENED 2026-10-27 (BUILD_SPEC26 §3.3): every 🏁 row gained `trader_text` (the 📌 tag; null on these fixtures).
    Dropping ONLY that key, and only where it is null, keeps the pre-BUILD_SPEC25 hashes exact — a non-null value
    (or any other change) still moves them."""
    if isinstance(o, dict):
        return {k: _drop_null_trader_text(v) for k, v in o.items() if not (k == "trader_text" and v is None)}
    if isinstance(o, list):
        return [_drop_null_trader_text(v) for v in o]
    return o


def _sha_of(tr):
    blob = json.dumps(_drop_null_trader_text({k: tr[k] for k in PRE_KEYS}), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ── 1. pooled = shadow + entry ───────────────────────────────────────────────────────────────────────────────────
def test_aplus_counts_pool_the_shadow_and_the_entry_lines_key_wise():
    b = served(ap_store())
    ap = b["aplus"]
    for h in GC.LEDGER_HORIZONS:
        pooled, sh, en = ap["counts"][h], b["counts"]["shadow"][h], b["counts"]["entry"][h]
        assert set(pooled) == set(sh) == set(LG._counts_blank(h))
        for k in pooled:
            if k != "pct":
                assert pooled[k] == sh[k] + en[k], (h, k)
        assert pooled["pct"] == LG._win_pct(pooled)
    assert (ap["total"], ap["n_sent"], ap["n_shadow"]) == (5, 2, 3)
    assert ap["counts"]["same"]["win"] == 1 and ap["counts"]["same"]["loss"] == 1 and ap["counts"]["same"]["pct"] == 50


# ── 2. NEGATIVE: a 🧠 row never moves the A+ block ───────────────────────────────────────────────────────────────
def test_NEGATIVE_a_potential_row_never_moves_the_aplus_block():
    a, b = served(ap_store()), served(ap_store(extra_win=True))
    assert b["counts"]["live"]["same"]["win"] == a["counts"]["live"]["same"]["win"] + 1      # the 🧠 % did move
    assert a["aplus"] == b["aplus"]
    assert a["kinds"][1] == b["kinds"][1] and a["categories_aplus"] == b["categories_aplus"]
    assert b["kinds"][0]["n"] == a["kinds"][0]["n"] + 1


# ── 3. NEGATIVE: a ⏪ replayed A+ is never in the filter ──────────────────────────────────────────────────────────
def test_NEGATIVE_a_replayed_aplus_is_never_in_the_aplus_block_nor_the_chip():
    w, wo = served(ap_store()), served(ap_store(replay=False))
    assert any(r["line"] == "replayed" for r in _days_rows(w["days"]))                     # the ⏪ row IS served
    for k in ("counts", "counts_text", "charts", "total", "split_text", "more_text"):
        assert w["aplus"][k] == wo["aplus"][k], k
    assert not [r for r in _days_rows(w["aplus"]["days"]) if r["line"] == "replayed"
                or r["id"].startswith(LG.REPLAY_ID_PREFIX)]
    assert w["kinds"][1] == wo["kinds"][1] and w["kinds"][1]["n_replayed"] == 0
    assert (w["kinds"][0]["n_replayed"], wo["kinds"][0]["n_replayed"]) == (1, 0)
    assert w["aplus"]["replayed_note"] == LG.APLUS_REPLAYED_NOTE and wo["aplus"]["replayed_note"] is None


# ── 4. the thin row: listed, never in the % ──────────────────────────────────────────────────────────────────────
def test_the_thin_row_is_listed_and_kept_out_of_the_pct_and_the_loss_item():
    ap = served(ap_store())["aplus"]
    rows = {r["symbol"]: r for r in _days_rows(ap["days"])}
    assert rows["THN"]["thin_text"] == LG.THIN_TEXT and rows["THN"]["same"]["state"] == "loss"
    c = ap["counts"]["same"]
    assert c["thin"] == 1 and c["loss"] == 1                    # LVL's loss only — THN's is under thin
    bar = next(x for x in ap["charts"][0]["bars"] if x["key"] == "same")
    items = {i["key"]: i for i in bar["items"]}
    assert items["loss"]["n"] == 1 and bar["decided"] == 2
    assert "1 thin R (not in the %)" in items["other"]["text"]


# ── 5. counts_text = the house template with the A+ lead ─────────────────────────────────────────────────────────
def test_counts_text_is_the_house_template_with_the_aplus_lead():
    ap = served(ap_store())["aplus"]
    for h in GC.LEDGER_HORIZONS:
        assert ap["counts_text"][h] == LG._counts_text(ap["counts"][h], h, False, lead=LG.APLUS_LEADS[h])
        assert ap["counts_text"][h].startswith(LG.APLUS_LEADS[h] + ": ")
    assert ap["counts_text"]["same"] == ("A+ same session: 1 win · 1 loss · 50% won · 1 no entry · 1 open · "
                                         "1 thin R (not in the %)")
    assert ap["split_text"] == "2 sent to your phone · 3 from the shadow period (never sent)"


# ── 6. by_setup / by_day sum to the outcome bars ─────────────────────────────────────────────────────────────────
def test_by_setup_and_by_day_sum_to_the_outcomes_in_their_served_order():
    ap = served(ap_store())["aplus"]
    ch = {c["key"]: c for c in ap["charts"]}
    assert [c["key"] for c in ap["charts"]] == list(LG.APLUS_CHART_KEYS)
    assert [c["title"] for c in ap["charts"]] == [LG.APLUS_CHART_TITLES[k] for k in LG.APLUS_CHART_KEYS]
    rows = _days_rows(ap["days"])
    setups = [s for s in GC.SETUPS if any(r["setup"] == s for r in rows)]
    assert [g["key"] for g in ch["by_setup"]["rows"]] == setups
    assert "horizontal_fade" not in setups                       # NEGATIVE: a setup with no row is no group
    labels = {r["setup"]: r["setup_label"] for r in rows}
    assert [g["label"] for g in ch["by_setup"]["rows"]] == [labels[s] for s in setups]
    assert [g["key"] for g in ch["by_day"]["cols"]] == sorted({r["date"] for r in rows}) == ["2026-10-14", "2026-10-15"]
    for h in GC.LEDGER_HORIZONS:
        bar = next(b for b in ch["outcomes"]["bars"] if b["key"] == h)
        bi = {i["key"]: i["n"] for i in bar["items"]}
        for chart, groups in (("by_setup", ch["by_setup"]["rows"]), ("by_day", ch["by_day"]["cols"])):
            gi = [{i["key"]: i["n"] for i in g[h]["items"]} for g in groups]
            assert sum(x["win"] for x in gi) == bi["win"], (chart, h)
            assert sum(x["loss"] for x in gi) == bi["loss"], (chart, h)
            assert sum(x.get("other", 0) for x in gi) == bar["total"] - bi["win"] - bi["loss"], (chart, h)
            assert sum(g[h]["total"] for g in groups) == bar["total"], (chart, h)
    assert [b["label"] for b in ch["outcomes"]["bars"]] == [dict(LG.HEADS)[h] for h in GC.LEDGER_HORIZONS]


# ── 7. items: Σ n == total, win + loss always, no zero-n other ───────────────────────────────────────────────────
def test_every_cell_items_sum_to_its_total_with_win_and_loss_always():
    ap = served(ap_store())["aplus"]
    for h, cell in _cells(ap):
        items = cell["items"]
        assert sum(i["n"] for i in items) == cell["total"], (h, cell)
        assert [i["key"] for i in items[:2]] == ["win", "loss"]
        assert all(i["n"] > 0 for i in items[2:]), items                     # NEGATIVE: no zero-n extra item
        assert all(i["label"] == LG.APLUS_ITEM_LABELS[i["key"]] for i in items)
        assert cell["decided"] == items[0]["n"] + items[1]["n"]
    bar = next(b for b in ap["charts"][0]["bars"] if b["key"] == "same")
    assert bar["total"] == sum(v for k, v in ap["counts"]["same"].items() if k != "pct") == 5
    for h in GC.LEDGER_HORIZONS:                                            # NEGATIVE: an all-zero column
        cell = LG._aplus_cell(LG._counts_blank(h), h, True)
        assert [(i["key"], i["n"]) for i in cell["items"]] == [("win", 0), ("loss", 0)] and cell["total"] == 0


# ── 8. every number in every served sentence is a served int ─────────────────────────────────────────────────────
def _ints(s):
    return {int(x) for x in INT.findall(s or "")}


def test_every_number_in_every_aplus_sentence_is_one_of_its_served_ints():
    b = served(ap_store())
    ap = b["aplus"]
    for h, cell in _cells(ap):
        pool = {cell["total"], cell["decided"], cell["total"] - cell["decided"]}   # text's "{k} other", k = total − w − l
        pool |= {x for x in (cell["pct"], cell["loss_pct"]) if x is not None}
        pool |= {i["n"] for i in cell["items"]}
        pool |= {v for k, v in ap["counts"][h].items() if k != "pct" and v is not None}   # the other item's extras
        for s in [cell["text"], cell["pct_text"], cell["short_text"]] + [i["text"] for i in cell["items"]]:
            assert _ints(s) <= pool, (h, s, pool)
    for h in GC.LEDGER_HORIZONS:
        assert _ints(ap["counts_text"][h]) <= {v for v in ap["counts"][h].values() if v is not None}, h
    assert _ints(ap["split_text"]) <= {ap["n_sent"], ap["n_shadow"]}
    for k in b["kinds"]:
        assert _ints(k["text"]) <= {k["n"], k["n_replayed"]}, k
    by_day = next(c for c in ap["charts"] if c["key"] == "by_day")
    for col in by_day["cols"]:
        assert col["label"] == LG._dow_md(date.fromisoformat(col["key"]))
    assert by_day["cols"][0]["label"] == "Wed 10-14"


# ── 9. NEGATIVE: no b-word, no forbidden word, no SEPA name, no None / nan ───────────────────────────────────────
def test_NEGATIVE_no_forbidden_word_and_no_none_or_nan_in_the_aplus_strings():
    from chart_maps.high_beta_tab import FORBIDDEN_WORDS
    for st in (ap_store(), ap_store(base=False, live=())):
        b = served(st)
        for s in list(_walk_strings(b["aplus"])) + list(_walk_strings(b["kinds"])):
            low = s.lower()
            assert not B_WORD.search(s), s
            assert not any(w in low for w in FORBIDDEN_WORDS), s
            assert not SEPA_NAMES.search(s), s
            assert not re.search(r"\bNone\b|\bnan\b", s, re.I), s


# ── 10. NEGATIVE: no A+ row on the span ──────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_aplus_on_the_span_serves_the_empty_block():
    pot = pot_doc("PWN", "bull_flag", D15, et(D15, 10, 35), 1.23, 1.11)
    st = store_with([pot], [], [_graded(pot, "potential", "win")])
    b = served(st)
    ap = b["aplus"]
    assert b["days"] and ap is not None
    for h in GC.LEDGER_HORIZONS:
        assert ap["counts"][h]["pct"] is None
        assert all(v == 0 for k, v in ap["counts"][h].items() if k != "pct")
    assert (ap["total"], ap["n_sent"], ap["n_shadow"]) == (0, 0, 0)
    assert ap["counts_text"] is None and ap["split_text"] is None and ap["more_text"] is None
    assert ap["empty_text"] == LG.KIND_EMPTY_TEXT and ap["charts"] == [] and ap["days"] == []
    assert b["kinds"][1]["text"] == "🎯 A+ only 0" and b["kinds"][1]["n"] == 0
    assert ap["title"] == LG.APLUS_TITLE and ap["honesty"] == LG.APLUS_HONESTY


# ── 11. NEGATIVE: the 🧠 headline is byte-for-byte unchanged ─────────────────────────────────────────────────────
def test_NEGATIVE_the_headline_is_byte_equal_to_the_pre_build_spec25_payload():
    got = {"cat_store": _sha_of(served(cat_store()))}
    for sp in ("today", "5d", "yesterday"):
        LG._TODAY_MEMO.clear()
        LG._TODAY_SPLIT.clear()
        st = golden_store()
        LG._TODAY_MEMO.clear()
        LG._TODAY_SPLIT.clear()
        got[sp] = _sha_of(board(st, sp)["track_record"])
    assert got == PRE_SHA


def test_NEGATIVE_the_default_lead_counts_text_is_the_headline_line():
    c = dict(LG._counts_blank("same"), win=2, loss=1, no_entry=3, open=1, pending=2)
    assert LG._counts_text(c, "same", False) == ("Same session: 2 wins · 1 loss · 67% won · 3 no entry · 1 open · "
                                                 "2 not graded yet")
    assert LG._counts_text(c, "same", True).endswith(" · 1 open · 2 not graded yet · today not final")
    n = LG._counts_blank("next")
    assert LG._counts_text(n, "next", False) == ("Through next session: 0 wins · 0 losses · no graded entry yet · "
                                                 "0 no entry · 0 flat")
    assert LG._counts_text(n, "next", False, lead=None) == LG._counts_text(n, "next", False)


# ── 12. the kind chips ───────────────────────────────────────────────────────────────────────────────────────────
def test_the_kind_chips_count_served_rows_with_the_replayed_ones_apart():
    b = served(ap_store())
    assert [k["key"] for k in b["kinds"]] == list(LG.KIND_KEYS)
    for k in b["kinds"]:
        assert k["text"] == LG._kind_text(k["key"], k["n"], k["n_replayed"]) and "%" not in k["text"]
    shown = _days_rows(b["days"])
    assert (b["kinds"][0]["n"], b["kinds"][0]["n_replayed"]) == (len(shown) - 1, 1) == (7, 1)
    assert b["kinds"][0]["text"] == "📋 every alert 7 +1 ⏪"
    assert b["kinds"][1]["text"] == "🎯 A+ only 5" == LG._kind_text("aplus", len(_days_rows(b["aplus"]["days"])))
    assert (b["kind_param"], b["kind_empty_text"]) == ("kind", LG.KIND_EMPTY_TEXT)


# ── 13. categories_aplus ─────────────────────────────────────────────────────────────────────────────────────────
def test_categories_aplus_are_the_categories_of_the_aplus_rows():
    b = served(ap_store())
    ap_rows = _days_rows(b["aplus"]["days"])
    assert b["categories_aplus"] == LG._categories(ap_rows)
    assert b["categories_aplus"] != b["categories"]                     # the 🧠 rows are out
    assert all(c["n_replayed"] == 0 for c in b["categories_aplus"])
    assert [c["key"] for c in b["categories_aplus"]] == list(LG.CATEGORY_KEYS)


# ── 14. the cap: aplus.days is cut, the counts are not ───────────────────────────────────────────────────────────
def test_the_row_cap_cuts_aplus_days_never_the_aplus_counts(monkeypatch):
    live = (("CA1", "kiss_fly", D15, "win"), ("CA2", "intraday_vcp", D15, "loss"), ("CA3", "kiss_fly", D14, "win"))
    monkeypatch.setattr(GC, "LEDGER_ROWS_MAX", 2)
    ap = served(ap_store(base=False, live=live))["aplus"]
    assert len(_days_rows(ap["days"])) == 2 and [d["date"] for d in ap["days"]] == ["2026-10-15"]
    assert ap["more_text"] == "+1 more A+ rows — the counts above cover all 3"
    assert ap["total"] == 3 and ap["counts"]["same"]["win"] == 2 and ap["counts"]["same"]["loss"] == 1
    assert ap["charts"][0]["bars"][0]["total"] == 3                     # the charts cover every A+ row too
    assert [c["key"] for c in ap["charts"][2]["cols"]] == ["2026-10-14", "2026-10-15"]


# ── 15. aplus.days rows ARE the rows of days ─────────────────────────────────────────────────────────────────────
def test_aplus_days_rows_are_the_identical_dicts_of_days():
    b = served(ap_store())
    by_id = {r["id"]: r for r in _days_rows(b["days"])}
    ap_rows = _days_rows(b["aplus"]["days"])
    assert ap_rows and all(r is by_id[r["id"]] for r in ap_rows)
    assert {r["id"] for r in ap_rows} == {r["id"] for r in by_id.values() if LG.is_aplus_row(r)}
    assert [d["label"] for d in b["aplus"]["days"]] == [d["label"] for d in b["days"]
                                                        if any(LG.is_aplus_row(r) for r in d["rows"])]


# ── 16. NEGATIVE: loss_pct = 100 − pct; both None at 0 decided ───────────────────────────────────────────────────
def test_NEGATIVE_loss_pct_is_100_minus_pct_and_none_at_zero_decided():
    ap = served(ap_store())["aplus"]
    seen_none = False
    for h, cell in _cells(ap):
        if cell["pct"] is None:
            seen_none = True
            assert cell["loss_pct"] is None and cell["decided"] == 0 and cell["pct_text"] == LG.NO_DECIDED_TEXT
            assert all("%" not in i["text"] for i in cell["items"][:2]), cell
            assert cell["text"].split(" · ")[2] == LG.NO_DECIDED_TEXT
        else:
            assert cell["loss_pct"] == 100 - cell["pct"]
            assert cell["pct_text"] == f"{cell['pct']}% won · {cell['decided']} decided"
    assert seen_none                                                    # the next column: nothing graded yet
    bar = ap["charts"][0]["bars"][0]
    assert [i["text"] for i in bar["items"][:2]] == ["1 win (50% of the 2 decided)", "1 loss (50% of the 2 decided)"]


# ── 17. a provisional A+ same cell reads "today not final" on the A+ line only ───────────────────────────────────
def test_a_provisional_aplus_same_cell_marks_the_aplus_line_only():
    st = ap_store(base=False, live=())
    doc = aplus_doc("PRV", "kiss_fly", D16, et(D16, 10, 35), 1.23, 1.11, state="pushed")
    st.coll(ST.ALERTS).docs[doc["_id"]] = doc
    row = LG.alert_of(doc, "aplus")
    g = LG.grade(row, replay_tape(D16, outcome="win"), LG.session_bounds(row["date"], row["at_utc"]), "same")
    b = LG.served_block(st, D16, NOW, span="5d", is_today=True, today={"grades": {row["id"]: g}})
    r = next(x for x in _days_rows(b["aplus"]["days"]) if x["id"] == row["id"])
    assert r["same"]["provisional"] is True and r["same"]["state"] == "win"
    assert b["aplus"]["counts_text"]["same"].endswith(" · today not final")
    assert not b["counts_text"]["same"].endswith(" · today not final")
    assert not b["aplus"]["counts_text"]["next"].endswith(" · today not final")
    base = LG.served_block(st, D16, NOW, span="5d", is_today=True, today=None)               # NEGATIVE: no read
    assert not base["aplus"]["counts_text"]["same"].endswith(" · today not final")


# ── 18. the frozen words ─────────────────────────────────────────────────────────────────────────────────────────
def test_the_frozen_aplus_words():
    assert LG.KIND_PARAM == "kind" and LG.KIND_KEYS == ("all", "aplus")
    assert LG.KIND_LABELS == {"all": "📋 every alert", "aplus": "🎯 A+ only"}
    assert LG.KIND_EMPTY_TEXT == "No 🎯 A+ alert on this span."
    assert LG.APLUS_LINES == ("live", "shadow") == (LG.LINES[0], LG.LINES[1])
    assert LG.APLUS_TITLE == "🎯 A+ only — every A+ alert, sent or shadow, graded by GG's trade math · UNMEASURED"
    assert LG.APLUS_LEADS == {"same": "A+ same session", "next": "A+ through next session"}
    assert LG.APLUS_SENT_TEXT == "{n} sent to your phone"
    assert LG.APLUS_SHADOW_TEXT == "{n} from the shadow period (never sent)"
    assert LG.APLUS_REPLAYED_NOTE == ("⏪ Replayed rows are not in the 🎯 A+ filter, its counts or its charts — they "
                                      "never rang.")
    assert LG.APLUS_HONESTY == (
        "Pooled: the A+ alerts sent to your phone and the shadow-period A+ (never sent) in one %, on its own line — the "
        "🧠 headline % is unchanged. An A+ exists only once the trade survived its entry bar. Small n, a ledger graded "
        "by GG's own trade math — not a backtest of a strategy. The 2026-10-14 study of the five setups read NULL — no "
        "edge over a matched placebo (docs/gajjala/study_2026_10_13.md); this record does not change that.")
    assert LG.APLUS_CHART_KEYS == ("outcomes", "by_setup", "by_day")
    assert LG.APLUS_CHART_TITLES == {"outcomes": "🎯 A+ wins vs losses", "by_setup": "By setup",
                                     "by_day": "By alert day"}
    assert LG.APLUS_ITEM_LABELS == {"win": "wins", "loss": "losses", "open": "open", "flat": "flat",
                                    "no_entry": "no entry", "other": "other"}
    assert LG.NO_DECIDED_TEXT == "no graded entry yet"
    ap = served(ap_store())["aplus"]
    assert ap["horizons"] == [{"key": "same", "label": "Same session"}, {"key": "next", "label": "Through next session"}]
    assert ap["horizon_default"] == GC.LEDGER_HORIZONS[0] == "same"
    for k in ("KIND_PARAM", "KIND_KEYS", "APLUS_TITLE", "APLUS_HONESTY", "NO_DECIDED_TEXT", "is_aplus_row",
              "aplus_block"):
        assert k in LG.__all__, k


# ── 19. NEGATIVE: by_setup never ranks on the % ──────────────────────────────────────────────────────────────────
def test_NEGATIVE_by_setup_order_ignores_the_pct():
    live = (("BFW", "bull_flag", D15, "win"), ("BFL", "bull_flag", D14, "loss"),
            ("KFL", "kiss_fly", D14, "loss"), ("RSW", "reversal_squeeze", D15, "win"))
    ch = {c["key"]: c for c in served(ap_store(base=False, live=live))["aplus"]["charts"]}
    groups = ch["by_setup"]["rows"]
    want = [s for s in GC.SETUPS if s in ("bull_flag", "kiss_fly", "reversal_squeeze")]
    assert [g["key"] for g in groups] == want == ["bull_flag", "kiss_fly", "reversal_squeeze"]  # GC.SETUPS order
    pcts = [g["same"]["pct"] for g in groups]
    assert pcts == [50, 0, 100]                                  # SETUPS order matches neither % order
    assert want != [g["key"] for g in sorted(groups, key=lambda g: g["same"]["pct"])]
    assert want != [g["key"] for g in sorted(groups, key=lambda g: -g["same"]["pct"])]
    rows = _days_rows(served(ap_store(base=False, live=live))["aplus"]["days"])
    odd = [dict(rows[0], setup="zz_new"), dict(rows[0], setup="aa_new")] + rows     # unknown setups: after, sorted
    got = next(c for c in LG._aplus_charts(odd) if c["key"] == "by_setup")["rows"]
    assert [g["key"] for g in got] == ["bull_flag", "kiss_fly", "reversal_squeeze", "aa_new", "zz_new"]
