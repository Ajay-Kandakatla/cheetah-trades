"""🔁 One count per stock per day on every 🏁 (2026-11-02, SPEC luk-track §3.1 / §3.2, WP-A gg-dedupe).

Ajay 2026-11-02, verbatim: "Can you make Luk's track record similar to Gajjal's and also can you make sure you are not
accounting for duplicates of the same stock as winner unless it did the same pattern again and met all the criteria on
the same day"

A COUNTING rule over the served rows — no grade, gate or threshold moves. THE engine is `ledger.dedupe_trades` over
neutral trade facts (`ledger.trade_facts`), partition `ledger.dup_group` = (date, symbol, count line); the first ring
counts; a later ring is a duplicate when (a) it filled on the same minute, (b) it carries the same trigger and stop, or
(c) its trade overlapped the counted one's (a FILLED later row judged by its fill — wholly its own when it was over
before the first filled; an UNFILLED later row judged by its ring). Duplicates stay listed (`dup_of`, `dup_text`), lose
their ✅/❌ flag and leave every count, %, chart, category chip and 🧪 attribution.

Every store here is SYNTHETIC and named so (the XLAB 10-16 pair on the REAL tape is pinned in
test_gajjala_aplus_filter_2026_10_26.py); the network is never touched. NEGATIVES are mandatory and marked.
UNMEASURED — accounting, not a study.
"""
from __future__ import annotations

import random
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import audited_tab as AT
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import variant as V
from tests.test_gajjala_audited_tab import NOW_C, _claim, _held, _identity, stores
from tests.test_gajjala_ledger import D15, aplus_doc, et, flat, pot_doc, store_with
from tests.test_gajjala_ledger_categories import _graded, served
from tests.test_gajjala_track_record_tab import replay_tape

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
LEDGER_PY = Path(LG.__file__)
B_WORD = re.compile("b" + "ounc", re.I)
EDGE = re.compile(r"\bedge\b", re.I)
D = date(2026, 10, 30)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()
    yield
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()


# ── 1 / 2. the pure engine ───────────────────────────────────────────────────────────────────────────────────────
def t(hh, mm, d=D):
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).astimezone(UTC)


def fact(i, at, *, filled=True, fill=None, dec=None, trig=10.0, stop=9.0, group=("2026-10-30", "AAA", "live"), rank=0):
    """SYNTHETIC neutral facts (every time aware)."""
    return {"id": i, "group": group, "at": at, "filled": filled, "fill_t": fill, "decided_t": dec,
            "trigger": trig, "stop": stop, "rank": rank}


def test_a_the_same_fill_minute_is_one_trade():
    f1 = fact("A", t(10, 0), fill=t(10, 40), dec=t(10, 41), trig=10.0, stop=9.0)
    f2 = fact("B", t(10, 5), fill=t(10, 40), dec=t(10, 41), trig=11.0, stop=10.5, rank=1)
    assert LG.dedupe_trades([f1, f2]) == {"B": "A"}


def test_b_the_same_plan_on_another_fill_minute_is_one_trade():
    f1 = fact("A", t(10, 0), fill=t(10, 40), dec=t(10, 41))
    f2 = fact("B", t(11, 0), fill=t(11, 20), dec=t(11, 30), rank=1)          # filled AFTER A decided — still (b)
    assert LG.dedupe_trades([f1, f2]) == {"B": "A"}


def test_c_a_filled_later_ring_inside_the_first_trade_is_a_duplicate():
    # the first filled 10:40, decided 10:41; the second (own plan) filled 10:38, decided 10:45 — filled before the first
    # was decided and NOT over before the first filled
    f1 = fact("A", t(10, 0), fill=t(10, 40), dec=t(10, 41))
    f2 = fact("B", t(10, 5), fill=t(10, 38), dec=t(10, 45), trig=12.0, stop=11.0)
    assert LG.dedupe_trades([f1, f2]) == {"B": "A"}
    # the first still open (never decided) → any later fill is held inside it
    f1o = fact("A", t(10, 0), fill=t(10, 40), dec=None)
    f2o = fact("B", t(13, 0), fill=t(13, 5), dec=t(13, 9), trig=12.0, stop=11.0)
    assert LG.dedupe_trades([f1o, f2o]) == {"B": "A"}
    # the first pending (filled unknown, no fill_t) → a filled later row is a duplicate
    f1p = fact("A", t(10, 0), filled=None)
    assert LG.dedupe_trades([f1p, f2o]) == {"B": "A"}
    # an UNFILLED later ring (no entry / pending) that rang before the first was decided → judged by its RING
    for unfilled in (False, None):
        f2u = fact("B", t(10, 36), filled=unfilled, trig=12.0, stop=11.0)
        assert LG.dedupe_trades([f1, f2u]) == {"B": "A"}, unfilled


def test_NEGATIVE_a_genuine_second_pattern_counts():
    f1 = fact("A", t(10, 0), fill=t(10, 40), dec=t(10, 41))
    f2 = fact("B", t(11, 0), fill=t(10, 41), dec=t(11, 5), trig=12.0, stop=11.0)   # fills AT the decision minute
    assert LG.dedupe_trades([f1, f2]) == {}
    # NEGATIVE: an unfilled later ring that rang after the first was decided
    assert LG.dedupe_trades([f1, fact("B", t(10, 42), filled=False, trig=12.0, stop=11.0)]) == {}


def test_NEGATIVE_the_ncpl_shape_over_before_the_first_filled_counts_and_the_boundary_is_le():
    """NCPL 10-30: ➖ rang 09:56, filled 10:52, decided 12:49; 🌀 rang 10:31 on its own plan, filled 10:33, +1R 10:52
    (== the ➖ fill minute) — wholly its own trade. One minute later (10:53) it is inside the ➖ trade → duplicate."""
    hf = fact("HF", t(9, 56), fill=t(10, 52), dec=t(12, 49), trig=2.30, stop=2.20, rank=2)
    vcp = fact("VCP", t(10, 31), fill=t(10, 33), dec=t(10, 52), trig=2.21, stop=2.15, rank=3)
    assert LG.dedupe_trades([hf, vcp]) == {}
    assert LG.dedupe_trades([hf, dict(vcp, decided_t=t(10, 53))]) == {"VCP": "HF"}


def test_NEGATIVE_a_counted_row_that_can_never_fill_blocks_nothing_by_c():
    f1 = fact("A", t(10, 0), filled=False)
    f2 = fact("B", t(10, 5), fill=t(10, 40), dec=t(10, 41), trig=12.0, stop=11.0)
    assert LG.dedupe_trades([f1, f2]) == {}
    # NEGATIVE: (b) still fires on a never-filled first ring with the same plan
    assert LG.dedupe_trades([f1, dict(f2, trigger=10.0, stop=9.0)]) == {"B": "A"}


def test_NEGATIVE_other_groups_never_dedupe():
    f1 = fact("A", t(10, 0), fill=t(10, 40), dec=t(10, 41))
    for g in (("2026-10-30", "BBB", "live"), ("2026-10-29", "AAA", "live"), ("2026-10-30", "AAA", "entry"),
              ("2026-10-30", "AAA", "shadow"), ("2026-10-30", "AAA", "replayed")):
        assert LG.dedupe_trades([f1, fact("B", t(10, 5), fill=t(10, 40), group=g)]) == {}, g


def test_NEGATIVE_none_and_timeless_entries_are_ignored_and_order_never_matters():
    f1 = fact("A", t(10, 0), fill=t(10, 40), dec=t(10, 41))
    naive = fact("N", datetime(2026, 10, 30, 14, 0), fill=t(10, 40))
    assert LG.dedupe_trades([None, f1, fact("Z", None, fill=t(10, 40)), naive]) == {}
    trades = [f1, fact("B", t(10, 5), fill=t(10, 40), rank=1), fact("C", t(10, 5), fill=t(10, 50), rank=2),
              fact("E", t(14, 0), fill=t(14, 5), dec=t(14, 9), trig=20.0, stop=19.0, rank=3)]
    want = LG.dedupe_trades(trades)
    assert want == {"B": "A", "C": "A"}                                         # C: (b) — the same plan
    rng = random.Random(11)
    for _ in range(20):
        sh = list(trades)
        rng.shuffle(sh)
        assert LG.dedupe_trades(sh) == want
    # a same-clock tie breaks by rank (SETUPS order), then id
    tie = [fact("Y", t(10, 0), fill=t(10, 40), rank=1), fact("X", t(10, 0), fill=t(10, 40), rank=0)]
    assert LG.dedupe_trades(tie) == {"Y": "X"}


def test_dup_group_is_the_count_line_for_every_line():
    base = {"date": "2026-10-30", "symbol": "AAA"}
    rows = [dict(base, kind="potential", line="live"), dict(base, kind="potential", line="live", push_state="shadow"),
            dict(base, kind="aplus", line="live"), dict(base, kind="aplus", line="shadow"),
            dict(base, kind="aplus", line="replayed")]
    got = [LG.dup_group(r) for r in rows]
    assert [g[2] for g in got] == [LG._count_line(r) for r in rows] == ["live", "live", "entry", "shadow", "replayed"]
    assert all(g[:2] == ("2026-10-30", "AAA") for g in got)


def test_trade_facts_reads_the_filled_grade_and_never_judges():
    row = {"id": "R", "date": "2026-10-30", "symbol": "AAA", "setup": "bull_flag", "kind": "potential", "line": "live",
           "at_utc": t(10, 0), "trigger": 10.0, "stop": 9.0, "plan": "ok"}
    same = {"entry": "filled", "fill_px": 10.0, "fill_t": t(10, 40).isoformat(), "outcome": "win",
            "exit_t": t(10, 41).isoformat()}
    f = LG.trade_facts(row, same, None, group=LG.dup_group(row), rank=0)
    assert (f["filled"], f["fill_t"], f["decided_t"], f["group"]) == (True, t(10, 40), t(10, 41),
                                                                      ("2026-10-30", "AAA", "live"))
    assert LG.trade_facts(row, dict(same, outcome="open", exit_t=None), None, group=0, rank=0)["decided_t"] is None
    ne = {"entry": "no_entry"}
    assert LG.trade_facts(row, ne, ne, group=0, rank=0)["filled"] is False
    assert LG.trade_facts(row, ne, None, group=0, rank=0)["filled"] is None          # next still pending: unknown
    assert LG.trade_facts(row, None, None, group=0, rank=0)["filled"] is None
    # NEGATIVE: no aware ring time / no plan → never a trade
    assert LG.trade_facts(dict(row, at_utc=None), same, None, group=0, rank=0) is None
    assert LG.trade_facts(dict(row, plan="no_plan"), same, None, group=0, rank=0) is None


# ── 3. served_block ──────────────────────────────────────────────────────────────────────────────────────────────
def _live_aplus(sym, setup, at, trig, stop, tape):
    """SYNTHETIC live A+ entry (a `GG:` claim in state pushed) + its ledger doc graded by the REAL LG.grade on `tape`."""
    doc = aplus_doc(sym, setup, D15, at, trig, stop, state="pushed")
    return doc, _graded(doc, "aplus", "win", tape=tape)


def _second_tape():
    """SYNTHETIC 10-15 tape for two trades on one name: replay_tape's 10:40 fill / 10:41 +1R for 1.23 / 1.11, then flat
    1.35 (under 1.40, over 1.30) to 11:34, the 11:35 minute trades through 1.40, the 11:36 minute reaches 1.50 (+1R of
    1.40 / 1.30), then flat 1.45."""
    head = [b for b in replay_tape(D15, outcome="win") if b[0] < et(D15, 10, 42)]
    mid = flat(D15, (10, 42), (11, 34), 1.35)
    b35 = [(et(D15, 11, 35), 1.39, 1.42, 1.38, 1.41)]
    b36 = [(et(D15, 11, 36), 1.41, 1.50, 1.40, 1.49)]
    return LG._merge(head, mid, b35, b36, flat(D15, (11, 37), (19, 59), 1.45))


def _two_aplus(second=None):
    tape = replay_tape(D15, outcome="win")
    a = _live_aplus("DUP", "bull_flag", et(D15, 10, 35), 1.23, 1.11, tape)
    b = second or _live_aplus("DUP", "kiss_fly", et(D15, 10, 35), 1.23, 1.11, tape)
    return store_with(alerts=[a[0], b[0]], ledger=[a[1], b[1]])


def _rows(b):
    return {r["setup"]: r for d in b["days"] for r in d["rows"]}


def test_served_block_counts_two_aplus_on_one_pass_clock_once():
    b = served(_two_aplus())
    rows = _rows(b)
    bf, kf = rows["bull_flag"], rows["kiss_fly"]
    assert b["counts"]["entry"]["same"]["win"] == 1 and b["dup_counts"]["entry"] == 1
    assert b["dup_counts"] == {"live": 0, "shadow": 0, "entry": 1, "replayed": 0}
    assert kf["dup_of"] == bf["id"] and bf["dup_of"] is None                      # equal `at` → SETUPS order
    e, label = AL.SETUP_META["bull_flag"]
    assert kf["dup_text"] == f"🔁 same trade as the 10:35 {e} {label} ring — not counted"
    assert kf["dup_text"] == "🔁 same trade as the 10:35 🚩 Bull Flag ring — not counted"
    assert kf["flag_text"] is None and kf["bucket"] == "win" and bf["flag_text"] == "✅ winner"
    assert b["entries_text"].endswith("1 duplicate of the same stock not counted")
    ap = b["aplus"]
    assert ap["n_dup"] == 1 and ap["total"] == 2 and ap["counts"]["same"]["win"] == 1
    assert ap["counts_text"]["same"].endswith("1 duplicate of the same stock not counted")
    ch = {c["key"]: c for c in ap["charts"]}
    win = next(i for i in ch["outcomes"]["bars"][0]["items"] if i["key"] == "win")
    assert win["n"] == 1
    assert [r["key"] for r in ch["by_setup"]["rows"]] == ["bull_flag"]          # the duplicate's setup is not charted
    cats = {c["key"]: c for c in b["categories"]}
    assert cats["win"]["n"] == 1 and cats["all"]["n"] == 2                       # 📋 all = every listed row
    assert {c["key"]: c["n"] for c in b["categories_aplus"]}["win"] == 1
    assert ap["days"] and sum(len(d["rows"]) for d in ap["days"]) == 2           # listed, never hidden


def test_NEGATIVE_a_genuine_second_pattern_on_the_same_day_counts_twice():
    tape = _second_tape()
    first = _live_aplus("DUP", "bull_flag", et(D15, 10, 35), 1.23, 1.11, tape)
    second = _live_aplus("DUP", "kiss_fly", et(D15, 11, 30), 1.40, 1.30, tape)
    st = store_with(alerts=[first[0], second[0]], ledger=[first[1], second[1]])
    assert second[1]["same"]["outcome"] == "win" and second[1]["same"]["fill_t"] == et(D15, 11, 35).isoformat()
    b = served(st)
    rows = _rows(b)
    assert all(r["dup_of"] is None and r["dup_text"] is None for r in rows.values())
    assert b["counts"]["entry"]["same"]["win"] == 2 and b["dup_counts"]["entry"] == 0
    assert [r["flag_text"] for r in rows.values()] == ["✅ winner", "✅ winner"]
    assert "duplicate" not in b["entries_text"] and b["aplus"]["n_dup"] == 0


def test_NEGATIVE_the_same_plan_later_is_still_a_duplicate_by_b():
    tape = _second_tape()
    first = _live_aplus("DUP", "bull_flag", et(D15, 10, 35), 1.23, 1.11, tape)
    second = _live_aplus("DUP", "kiss_fly", et(D15, 11, 30), 1.23, 1.11, tape)
    assert second[1]["same"]["fill_t"] != first[1]["same"]["fill_t"]           # another fill minute — not (a)
    b = served(store_with(alerts=[first[0], second[0]], ledger=[first[1], second[1]]))
    rows = _rows(b)
    assert rows["kiss_fly"]["dup_of"] == rows["bull_flag"]["id"] and b["counts"]["entry"]["same"]["win"] == 1


def test_NEGATIVE_a_potential_and_its_aplus_are_two_ledgers():
    tape = replay_tape(D15, outcome="win")
    pot = pot_doc("TWO", "bull_flag", D15, et(D15, 10, 35), 1.23, 1.11)
    ap = aplus_doc("TWO", "bull_flag", D15, et(D15, 10, 35), 1.23, 1.11, state="pushed")
    st = store_with([pot], [ap], [_graded(pot, "potential", "win", tape=tape), _graded(ap, "aplus", "win", tape=tape)])
    b = served(st)
    assert b["dup_counts"] == {"live": 0, "shadow": 0, "entry": 0, "replayed": 0}
    assert b["counts"]["live"]["same"]["win"] == 1 and b["counts"]["entry"]["same"]["win"] == 1
    assert all(r["dup_of"] is None and r["flag_text"] == "✅ winner" for d in b["days"] for r in d["rows"])
    # NEGATIVE: a shadow A+ and a live A+ of one stock-day are two ledgers too
    sh = aplus_doc("TWO", "kiss_fly", D15, et(D15, 10, 35), 1.23, 1.11)
    st2 = store_with([], [ap, sh], [_graded(ap, "aplus", "win", tape=tape), _graded(sh, "aplus", "win", tape=tape)])
    assert served(st2)["dup_counts"] == {"live": 0, "shadow": 0, "entry": 0, "replayed": 0}


def test_NEGATIVE_no_pair_no_tail_and_dup_zero_is_byte_identical():
    c = dict(LG._counts_blank("same"), win=2, loss=1)
    assert LG._counts_text(c, "same", True, dup=0) == LG._counts_text(c, "same", True)
    assert LG._counts_text(c, "same", True, dup=1).endswith(" · 1 duplicate of the same stock not counted · today "
                                                             "not final")
    n = LG._counts_blank("next")
    assert LG._line_text("H", c, n, dup=0) == LG._line_text("H", c, n)
    assert LG._line_text("H", c, n, dup=2).endswith(" · 2 duplicates of the same stock not counted")
    assert LG.dup_count_text(0) is None and LG.dup_count_text(-1) is None
    full = LG._aplus_cell(dict(LG._counts_blank("same"), win=1, open=1), "same", True)
    assert LG._aplus_cell(dict(LG._counts_blank("same"), win=1, open=1), "same", True, mid_k=None) == full
    nxt = dict(LG._counts_blank("next"), win=1, flat=1)
    assert [i["key"] for i in LG._aplus_cell(nxt, "next", True)["items"]] == ["win", "loss", "flat"]


# ── words ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_words_carry_his_rule_verbatim():
    assert LG.DUP_RULE_WORDS == ("make sure you are not accounting for duplicates of the same stock as winner unless it "
                                 "did the same pattern again and met all the criteria on the same day")
    assert LG.DUP_RULE_WORDS in LG.HONESTY and "The winners / losers chips count ROWS" in LG.HONESTY
    assert LG.rule_text().endswith(" " + LG.DUP_RULE_TEXT)
    assert LG.APLUS_HONESTY.endswith(" " + LG.DUP_RULE_TEXT)
    assert V.DUP_RULE_TEXT == LG.DUP_RULE_TEXT                                   # typed twice, pinned equal
    for v in (V.GG1, V.GGA):
        assert LG.DUP_RULE_TEXT in V.word("ledger_honesty", v), v.key
    assert LG.DUP_RULE_TEXT in V.word("compare_honesty", V.GGA, r=1.0, floor=1, n=0)
    for k in ("ledger_honesty",):
        assert V.WORDS_1M_SHADOW[k].endswith(LG.DUP_RULE_TEXT)
    new_rows = LG.HONESTY[LG.HONESTY.index(" The winners / losers chips"):]       # the F3 text keeps its own words
    for s in (LG.DUP_RULE_TEXT, LG.DUP_TEXT, LG.DUP_COUNT_ONE, LG.DUP_COUNT_MANY, new_rows):
        assert not B_WORD.search(s) and not EDGE.search(s), s
    assert not re.search(r"\d", LG.DUP_RULE_TEXT) and "{" not in LG.DUP_RULE_TEXT and "}" not in LG.DUP_RULE_TEXT
    for name in ("dedupe_trades", "trade_facts", "dup_group", "dup_count_text", "DUP_RULE_WORDS", "DUP_RULE_TEXT",
                 "DUP_TEXT"):
        assert name in LG.__all__, name


def test_honesty_layout_survives_the_contract_regex():
    """contracts.mjs:9022 — the regex is LAZY to the first line that ends with `)`; the joined double-quoted literals
    must carry the pinned phrase AND be the WHOLE expression (no line inside ends with `)`)."""
    src = LEDGER_PY.read_text(encoding="utf-8")
    m = re.search(r"^HONESTY = \(([\s\S]*?)\)\s*(?:#[^\n]*)?$", src, re.M)
    assert m is not None
    joined = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)))
    assert re.search(r"[Tt]he winners / losers chips count ROWS", joined)
    assert joined.replace('\\"', '"') == LG.HONESTY.replace(LG.DUP_RULE_WORDS, "", 1)


# ── 4. 🧪 audited vs original ────────────────────────────────────────────────────────────────────────────────────
D1 = date(2026, 11, 3)


def _at(hh, mm):
    return datetime(D1.year, D1.month, D1.day, hh, mm, tzinfo=ET).astimezone(UTC).isoformat()


def _claim_at(sym, setup, at_iso, *, trigger=10.0, stop=9.0, variant=None):
    doc = _claim(sym, setup=setup, trigger=trigger, stop=stop, variant=variant)
    doc["at"] = at_iso
    return doc


def _fgrade(sym, setup, outcome, fill_iso, exit_iso):
    """SYNTHETIC stored same column that FILLED (fill_px / fill_t / exit_t set)."""
    g = {"entry": "filled", "outcome": outcome, "fill_px": 10.0, "fill_t": fill_iso, "exit_t": exit_iso,
         "version": GC.LEDGER_GRADE_VERSION}
    return {"_id": LG.ledger_id(D1.isoformat(), sym, setup, LG.KINDS[1]), "date": D1.isoformat(), "symbol": sym,
            "setup": setup, "same": g}


def _cmp(st):
    return AT.compare_block(st, date(2026, 11, 4), NOW_C, span="5d", is_today=True)


def _pair_world(*, second_plan=(10.0, 9.0), second_at=(10, 5), second_fill=(10, 40), second_exit=(10, 41),
                held=(), audited=True):
    """SYNTHETIC: AAA bull_flag (rang 10:00, filled 10:40, +1R 10:41) + AAA kiss_fly on the 🚩 original; BBB a loss."""
    g5a = [_claim_at("AAA", "bull_flag", _at(10, 0)),
           _claim_at("AAA", "kiss_fly", _at(*second_at), trigger=second_plan[0], stop=second_plan[1]),
           _claim_at("BBB", "bull_flag", _at(10, 0), trigger=20.0, stop=19.0)]
    g5l = [_fgrade("AAA", "bull_flag", "win", _at(10, 40), _at(10, 41)),
           _fgrade("AAA", "kiss_fly", "win", _at(*second_fill), _at(*second_exit)),
           _fgrade("BBB", "bull_flag", "loss", _at(10, 50), _at(10, 55))]
    aa = [_claim_at("AAA", "bull_flag", _at(10, 0), variant=V.GGA)] if audited else []
    al = [_fgrade("AAA", "bull_flag", "win", _at(10, 40), _at(10, 41))] if audited else []
    aa += [_held(sym, ["G4"], setup=setup) for sym, setup in held]
    return stores(g5a, g5l, aa, al)


def test_audited_original_side_counts_the_stock_day_once():
    c = _cmp(_pair_world())
    o, a = c["sides"]
    assert (o["n"], o["n_dup"], o["win"], o["loss"]) == (2, 1, 1, 1)
    assert (a["n"], a["n_dup"]) == (1, 0)
    assert c["recon"]["original_only"] == 2 and _identity(c)                     # kiss_fly + BBB: no audited row
    for k, side in (("original", o), ("audited", a)):
        assert sum(d[k]["n"] for d in c["by_day"]) == side["n"]
        assert sum(d[k]["win"] for d in c["by_day"]) == side["win"]
    pr = {r["key"]: r for r in c["per_rule"]}
    # the per-rule table never scores the duplicate original: AAA bull_flag scored (with, claim on its bar → fallback),
    # BBB not judged, the kiss_fly duplicate neither with nor held nor not-judged
    for rid in ("G1", "G2", "G4"):
        r = pr[rid]
        assert r["with"]["n"] + r["other"]["n"] + r["not_judged"] == 2, rid
    # NEGATIVE: the rule off → the duplicate is a third scored original (the identity of the table moves by one)
    world = _pair_world(second_plan=(12.0, 11.0), second_at=(10, 30), second_fill=(10, 33), second_exit=(10, 39))
    c2 = _cmp(world)
    o2 = c2["sides"][0]
    assert (o2["n"], o2["n_dup"], o2["win"]) == (3, 0, 2) and _identity(c2)
    pr2 = {r["key"]: r for r in c2["per_rule"]}
    assert pr2["G1"]["with"]["n"] + pr2["G1"]["other"]["n"] + pr2["G1"]["not_judged"] == 3


def test_held_side_dedupes_over_its_own_rows_from_the_originals_facts():
    c = _cmp(_pair_world(held=(("AAA", "bull_flag"), ("AAA", "kiss_fly")), audited=False))
    h = c["held"]
    assert (h["n"], h["n_dup"]) == (1, 1)
    rows = {r["setup"]: r for r in h["rows"]}
    assert set(rows) == {"bull_flag", "kiss_fly"}                                # both listed, never hidden
    assert rows["kiss_fly"]["dup_of"] == LG.ledger_id(D1.isoformat(), "AAA", "bull_flag", LG.KINDS[1])
    assert rows["bull_flag"]["dup_of"] is None
    assert _identity(c)


def test_NEGATIVE_a_held_row_whose_twin_is_not_held_counts_once_on_the_held_side():
    c = _cmp(_pair_world(held=(("AAA", "kiss_fly"),)))
    h = c["held"]
    assert (h["n"], h["n_dup"]) == (1, 0) and h["rows"][0]["dup_of"] is None    # never zero times
    assert c["sides"][0]["n_dup"] == 1 and _identity(c)                          # the original side deduped it


def test_NEGATIVE_a_no_original_held_row_is_never_a_duplicate():
    c = _cmp(_pair_world(held=(("EEE", "bull_flag"), ("EEE", "kiss_fly"))))
    h = c["held"]
    assert all(r["dup_of"] is None for r in h["rows"])
    assert h[AT.NO_ORIGINAL] == 2 and h["n_dup"] == 0 and _identity(c)
