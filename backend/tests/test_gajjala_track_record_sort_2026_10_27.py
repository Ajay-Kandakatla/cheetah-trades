"""✅ wins first + the per-row ✅ / ❌ flag on the 🏁 Track record (2026-10-27).

Ajay, verbatim (his spelling kept): "Can you sort the winds in Gajjals I can't seem to tell the difference in that tab or
show some greed flags on the wins rows". This ANSWERS HIS CALL Q11 of docs/gajjala/track_record_2026_10_16.md
(AMENDMENTS11 F13 — the hidden per-row chip — was the planner's default, not his).

What the server does: it serves the sort chips (`sorts`, each with its served label and a `bucket_sort` boolean), the
param name, the default key and the bucket order the FE sorts by, and each row's `flag_text` (the served ✅ winner / ❌
loser words on win / loss rows only). What the server NEVER does: reorder a row — the ledger stays chronological, as
rang; the sort is FE-only (lib/gajjala.ts ggSortRows). NEGATIVES below pin both halves. UNMEASURED.
"""
from __future__ import annotations

from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import variant as V
from tests.test_gajjala_track_record_tab import board, golden_store


def _tr(span: str = "5d") -> dict:
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()
    return board(golden_store(), span, owner=True)["track_record"]


def _rows_of(tr: dict) -> list:
    rows = [r for d in tr["days"] for r in d["rows"]]
    rows += [r for d in ((tr.get("aplus") or {}).get("days") or []) for r in d["rows"]]
    return rows


def test_sort_words_are_frozen_and_exported():
    assert LG.SORT_PARAM == "sort"
    assert LG.SORT_KEYS == ("wins", "rang") and LG.SORT_KEYS[0] == "wins"       # his ask: the wins on top = default
    assert LG.SORT_LABELS == {"wins": "✅ wins first", "rang": "🕰️ as rang"}
    assert LG.SORT_BY_BUCKET == {"wins": True, "rang": False}
    assert LG.FLAG_BUCKETS == ("win", "loss") == tuple(LG.BUCKETS[:2])
    for name in ("SORT_PARAM", "SORT_KEYS", "SORT_LABELS", "SORT_BY_BUCKET", "FLAG_BUCKETS"):
        assert name in LG.__all__, name


def test_served_block_carries_the_chips_the_default_and_the_bucket_order():
    tr = _tr()
    assert tr["sort_param"] == "sort"
    assert tr["sort_default"] == "wins"
    assert tr["bucket_order"] == list(LG.BUCKETS) == ["win", "loss", "open", "flat", "out"]
    assert tr["sorts"] == [{"key": "wins", "label": "✅ wins first", "bucket_sort": True},
                           {"key": "rang", "label": "🕰️ as rang", "bucket_sort": False}]
    # exactly one chip sorts, and it is the default — the FE compares keys to the served default and types none
    assert [s["key"] for s in tr["sorts"] if s["bucket_sort"]] == [tr["sort_default"]]
    for s in tr["sorts"]:
        assert isinstance(s["bucket_sort"], bool)


def test_every_served_row_flags_win_and_loss_rows_only():
    seen = set()
    for span in ("today", "5d", "yesterday"):
        for r in _rows_of(_tr(span)):
            seen.add(r["bucket"])
            if r["bucket"] in LG.FLAG_BUCKETS:
                assert r["flag_text"] == LG.BUCKET_TEXT[r["bucket"]], r["key"]
                assert r["flag_text"] in ("✅ winner", "❌ loser")
            else:
                assert r["flag_text"] is None, r["key"]          # NEGATIVE: open / flat / out rows carry no flag
    assert "win" in seen and "out" in seen                       # the golden exercises both branches


def test_server_never_reorders_rows_NEGATIVE():
    """The served order stays chronological (as rang): on the golden's 2026-10-16 day the "out" rows precede the XLAB
    wins. A server-side wins-first sort would put a win first — it must not (the FE sorts over `bucket_order`)."""
    tr = _tr("5d")
    d16 = next(d for d in tr["days"] if d["date"] == "2026-10-16")
    buckets = [r["bucket"] for r in d16["rows"]]
    assert buckets[0] == "out" and "win" in buckets, buckets
    assert buckets.index("win") > buckets.index("out"), buckets
    # the A+ list keeps its own served order too, and the sort fields never leak into a row
    for r in _rows_of(tr):
        for k in ("sorts", "sort_default", "sort_param", "bucket_order"):
            assert k not in r, (r["key"], k)


def test_the_one_minute_variant_serves_the_same_chips():
    """`_variant_words` touches the title / honesty / 🧠 kind word / counts lead / empty text only — the sort block and
    every row's flag come through unchanged on the 1-minute page."""
    tr = _tr("5d")
    copy = dict(tr, days=[dict(d, rows=[dict(r) for r in d["rows"]]) for d in tr["days"]],
                counts_text=dict(tr["counts_text"]))
    blk = LG._variant_words(copy, V.GG1)
    assert blk["sorts"] == tr["sorts"]
    assert blk["sort_default"] == tr["sort_default"] and blk["sort_param"] == tr["sort_param"]
    assert blk["bucket_order"] == tr["bucket_order"]
    assert [r["flag_text"] for d in blk["days"] for r in d["rows"]] == [r["flag_text"] for d in tr["days"] for r in d["rows"]]
    assert blk["title"] != tr["title"]                           # the variant did rewrite its own words


def test_kinds_categories_and_heads_are_untouched():
    tr = _tr("5d")
    assert [k["key"] for k in tr["kinds"]] == list(LG.KIND_KEYS)
    assert [c["key"] for c in tr["categories"]] == list(LG.CATEGORY_KEYS)
    assert [h["key"] for h in tr["heads"]] == [k for k, _ in LG.HEADS]
