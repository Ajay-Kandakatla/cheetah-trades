"""🏁 parity — 🚩 Gajjala's 1-minute 🏁 vs the 5-minute 🏁 (SPEC gg-track-parity §4 WP-B, 2026-11-05). PINS ONLY.

Ajay 2026-11-05, verbatim: "Can you make both Gajjala's track record and Gajjalas 1 min and Gajjalas AUDIT HAVE similar
track record." Measured the same night on the owner GETs (F2): the 1-minute block and the 5-minute block serve the SAME
keys (block keys, row keys, heads, views, sorts, bucket_order, categories / kinds / aplus / charts keys, rule_text,
rule_label, spans) — only the served WORDS differ (variant.WORDS_1M: title, honesty, the counts lead, the empty text).
Nothing to fix; this file keeps it that way.

The two blocks are `ledger.served_block` over the two EXISTING fixture stores, imported never copied: the 🏁 golden's
`golden_store` (tests/test_gajjala_track_record_tab.py — GG5, 2026-10-16) and the 1-minute page's fixture day
(tests/test_gajjala_1m_page_2026_10_27.py `day()` — the GG1 store, 2026-10-27), on every GC.LEDGER_SPANS value.
The two stores hold different alerts, so the words pin reads ONE store under both variants (the golden store without
its ⏪ replay — the 1-minute page has no replay by design, HIS CALL #15 — with GG1's record start moved, in the test
only, to the store's earliest session so both variants read the same rows): every top-level served string that differs
is one `_variant_words` rewrites, and a row differs only by its deep link's `tab=` (and the 🧠 kind word).
NEGATIVES: a key inserted into one block only, a row key, a head, a served word — each is caught by the pin.
UNMEASURED — nothing here measures a read; no golden is written.
"""
from __future__ import annotations

import copy

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import run_1m as R1
from chart_maps.gajjala import tape as TP
from chart_maps.gajjala import variant as V
from tests.test_gajjala_store import fake_store
import tests.test_gajjala_1m_page_2026_10_27 as T1
import tests.test_gajjala_track_record_tab as T5

COND_ROW_KEYS = frozenset({"promo", "promo_text"})      # served_block: a row carries them ONLY when 🎪-tagged
WORD_KEYS = frozenset({"title", "honesty", "counts_text", "empty_text"})   # what WORDS_1M rewrites (_variant_words)
ROW_WORD_KEYS = frozenset({"href", "kind_text"})         # a row: its deep link's tab= and the 🧠 kind word
EQUAL_KEYS = ("heads", "views", "sorts", "sort_default", "bucket_order", "category_param", "kind_param", "spans",
              "rule_text", "rule_label", "grade_at_et")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    _fresh()
    yield
    _fresh()


def _fresh():
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()
    TP._MEMO.clear()
    R1._PREV_MEMO.clear()


def block_5m(st, span):
    """🚩's 5-minute 🏁 as the tab serves it on the golden's session (GG5 = the store's own variant)."""
    _fresh()
    return LG.served_block(st, T5.D16, T5.NOW, span=span, is_today=True, today=T5.today_of(st, span))


def block_1m(st, span):
    """The 1-minute 🏁 as the tab serves it on the fixture day (variant=GG1, tab.py's 🏁 branch)."""
    _fresh()
    return LG.served_block(st, T1.D27, T1.NOW, span=span, is_today=True, today=T1.today_of(st, span),
                           variant=V.GG1)


def _rows(block):
    return [r for d in block.get("days") or [] for r in d.get("rows") or []]


def _stringy(x):
    return isinstance(x, str) or (isinstance(x, dict) and bool(x) and
                                  all(isinstance(t, str) or t is None for t in x.values()))


def word_diffs(a, b) -> set:
    """The top-level served strings (a str, or a dict of str like counts_text) that differ between the two blocks."""
    return {k for k in set(a) | set(b) if (_stringy(a.get(k)) or _stringy(b.get(k))) and a.get(k) != b.get(k)}


def parity_breaks(a, b) -> list:
    """THE pin: every way the two 🏁 blocks may NOT differ. [] = parity."""
    out = []
    if set(a) != set(b):
        out.append(("block keys", sorted(set(a) ^ set(b))))
    rows = [("5m", r) for r in _rows(a)] + [("1m", r) for r in _rows(b)]
    if rows:
        want = set(rows[0][1]) - COND_ROW_KEYS
        bad = [(side, r.get("id"), sorted((set(r) - COND_ROW_KEYS) ^ want)) for side, r in rows
               if set(r) - COND_ROW_KEYS != want]
        if bad:
            out.append(("row keys", bad))
    for k in EQUAL_KEYS:
        if a.get(k) != b.get(k):
            out.append((k, a.get(k), b.get(k)))
    ap_a, ap_b = a.get("aplus"), b.get("aplus")
    if not (isinstance(ap_a, dict) and isinstance(ap_b, dict)) or set(ap_a) != set(ap_b):
        out.append(("aplus keys", sorted(set(ap_a or {}) ^ set(ap_b or {}))))
    else:
        ca = [c.get("key") for c in ap_a.get("charts") or []]
        cb = [c.get("key") for c in ap_b.get("charts") or []]
        if ca and cb and ca != cb:
            out.append(("aplus charts order", ca, cb))
    return out


@pytest.fixture(scope="module")
def pairs():
    g5 = T5.golden_store()
    _g5, g1, *_ = T1.day()
    return {span: (block_5m(g5, span), block_1m(g1, span)) for span in GC.LEDGER_SPANS}


# ── the pin over the two existing fixture stores ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("span", GC.LEDGER_SPANS)
def test_the_1m_and_5m_blocks_serve_the_same_keys_on_every_span(pairs, span):
    a, b = pairs[span]
    assert parity_breaks(a, b) == [], span
    assert a["span"] == b["span"] == span
    assert [h["key"] for h in a["heads"]] == [k for k, _l in LG.HEADS]


def test_the_pin_is_not_vacuous(pairs):
    """Rows, A+ rows and the A+ charts are on both sides on at least one span (the 5d window holds both days)."""
    both = [s for s, (a, b) in pairs.items() if _rows(a) and _rows(b)]
    assert "5d" in both and "today" in both, both
    charts = [s for s, (a, b) in pairs.items() if a["aplus"]["charts"] and b["aplus"]["charts"]]
    assert charts and [c["key"] for c in pairs["5d"][0]["aplus"]["charts"]] == \
        [c["key"] for c in pairs["5d"][1]["aplus"]["charts"]]
    assert pairs["5d"][1]["title"] == V.word("ledger_title", V.GG1) and pairs["5d"][0]["title"] == LG.TITLE


# ── the words: ONE store under both variants ─────────────────────────────────────────────────────────────────────
def _same_rows_store(monkeypatch):
    st = T5.golden_store(with_replay=False)          # no ⏪: the 1-minute page has none by design (HIS CALL #15)
    start = min(min(LG._sessions_for(s, T5.D16, st)) for s in GC.LEDGER_SPANS)
    monkeypatch.setattr(GC, V.GG1.record_from_const, start.isoformat())   # test only: GG1 reads the same sessions
    return st


@pytest.mark.parametrize("span", GC.LEDGER_SPANS)
def test_NEGATIVE_the_words_differ_only_where_WORDS_1M_says(monkeypatch, span):
    st = _same_rows_store(monkeypatch)
    _fresh()
    t = T5.today_of(st, span)
    a = LG.served_block(st, T5.D16, T5.NOW, span=span, is_today=True, today=t)
    b = LG.served_block(st, T5.D16, T5.NOW, span=span, is_today=True, today=t, variant=V.GG1)
    assert parity_breaks(a, b) == [], span
    diffs = word_diffs(a, b)
    assert diffs <= WORD_KEYS, (span, sorted(diffs - WORD_KEYS))
    assert {"title", "honesty", "counts_text"} <= diffs, (span, diffs)          # the 1-minute words ARE served
    assert (b["title"], b["honesty"]) == (V.word("ledger_title", V.GG1), V.word("ledger_honesty", V.GG1))
    assert (a["title"], a["honesty"]) == (LG.TITLE, LG.HONESTY)
    ra, rb = _rows(a), _rows(b)
    assert ra and [r["id"] for r in ra] == [r["id"] for r in rb], span
    for x, y in zip(ra, rb):
        assert {k for k in set(x) | set(y) if x.get(k) != y.get(k)} <= ROW_WORD_KEYS, x["id"]
        assert y["href"] == x["href"].replace(f"tab={V.GG5.tab}&", f"tab={V.GG1.tab}&"), x["id"]
    strip = lambda ap: {k: v for k, v in ap.items() if k != "days"}                   # noqa: E731
    assert strip(a["aplus"]) == strip(b["aplus"]), span


def test_NEGATIVE_an_empty_span_differs_by_the_empty_word_too(monkeypatch):
    monkeypatch.setattr(GC, V.GG1.record_from_const, T5.D16.isoformat())
    st = fake_store()
    a = LG.served_block(st, T5.D16, T5.NOW, span="today", is_today=True, today=None)
    b = LG.served_block(st, T5.D16, T5.NOW, span="today", is_today=True, today=None, variant=V.GG1)
    assert parity_breaks(a, b) == []
    assert word_diffs(a, b) == WORD_KEYS
    assert b["empty_text"] == V.word("ledger_empty", V.GG1) and a["empty_text"] != b["empty_text"]


# ── NEGATIVES: the pin catches a one-sided change ────────────────────────────────────────────────────────────────
def _one_sided(pairs, span, edit):
    a, b = pairs[span]
    b = copy.deepcopy(b)
    edit(b)
    return parity_breaks(a, b), word_diffs(a, b)


def test_NEGATIVE_a_key_inserted_into_one_block_is_caught(pairs):
    breaks, _w = _one_sided(pairs, "5d", lambda b: b.__setitem__("leak", None))
    assert breaks == [("block keys", ["leak"])]


def test_NEGATIVE_a_key_inserted_through_served_block_is_caught(pairs, monkeypatch):
    """The insert rides the REAL call (monkeypatched served_block on the 1-minute side only)."""
    real = LG.served_block

    def leaky(*a, **k):
        out = real(*a, **k)
        if k.get("variant") is V.GG1:
            out["leak_1m"] = "x"
        return out
    monkeypatch.setattr(LG, "served_block", leaky)
    _g5, g1, *_ = T1.day()
    a, b = pairs["today"][0], block_1m(g1, "today")
    breaks = parity_breaks(a, b)
    assert ("block keys", ["leak_1m"]) in breaks
    assert "leak_1m" in word_diffs(a, b) - WORD_KEYS


def test_NEGATIVE_a_row_key_on_one_side_is_caught_but_the_promo_keys_are_conditional(pairs):
    breaks, _w = _one_sided(pairs, "5d", lambda b: _rows(b)[0].__setitem__("leak", 1))
    assert breaks and breaks[0][0] == "row keys"
    tagged, _w = _one_sided(pairs, "5d", lambda b: _rows(b)[0].update(promo=True, promo_text="🎪"))
    assert tagged == []


@pytest.mark.parametrize("key", EQUAL_KEYS)
def test_NEGATIVE_each_equal_key_is_pinned(pairs, key):
    breaks, _w = _one_sided(pairs, "5d", lambda b: b.__setitem__(key, ["moved"]))
    assert [x[0] for x in breaks] == [key]


def test_NEGATIVE_aplus_keys_and_chart_order_are_pinned(pairs):
    breaks, _w = _one_sided(pairs, "5d", lambda b: b["aplus"].__setitem__("leak", 1))
    assert breaks == [("aplus keys", ["leak"])]
    breaks, _w = _one_sided(pairs, "5d", lambda b: b["aplus"]["charts"].reverse())
    assert [x[0] for x in breaks] == ["aplus charts order"]


def test_NEGATIVE_a_served_word_outside_WORDS_1M_is_caught(monkeypatch):
    """On the same rows (the words pin's store), a word moved on the 1-minute side only is outside WORD_KEYS."""
    st = _same_rows_store(monkeypatch)
    _fresh()
    t = T5.today_of(st, "5d")
    a = LG.served_block(st, T5.D16, T5.NOW, span="5d", is_today=True, today=t)
    b = LG.served_block(st, T5.D16, T5.NOW, span="5d", is_today=True, today=t, variant=V.GG1)
    assert word_diffs(a, b) <= WORD_KEYS
    for key in ("category_empty_text", "today_text", "rule_label"):
        moved = copy.deepcopy(b)
        moved[key] = "moved"
        assert word_diffs(a, moved) - WORD_KEYS == {key}, key
