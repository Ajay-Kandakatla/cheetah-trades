"""💥 What hit it — `chart_maps/fallen_catalysts.py` (2026-10-02), WP-BE tests 1-11.

Ajay 2026-10-02 (mid-build): "also add things like possible catalyst that
made is drop like that."

Every item is CO-OCCURRENCE on a date — "possible", never proof — and the text
is the stored text. Readers are injected; the conftest refuses Mongo; nothing
reaches the network. Positive AND negative cases.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from chart_maps import fallen_catalysts as FC
from rotation import tracker as T
from sepa import universe as U

BACKEND = Path(__file__).resolve().parents[1]

DROP = {"date": "2026-02-12", "c2c_pct": -19.68, "gap_pct": -11.56, "intraday_pct": -9.18,
        "larger_leg": "gap", "vol_x50": 3.62, "share_of_fall_pct": 19.28,
        "prev_close": 456.81, "close": 366.91,
        "window": {"lo": "2026-02-11", "hi": "2026-02-13"}}
_BANNED = re.compile(r"bounc|fake|caused|because", re.I)


def _readers(**over):
    base = {k: (lambda syms, names, db: {}) for k in FC.PRIORITY}
    base["index"] = lambda syms, names, db: []
    base["frames"] = lambda syms: {}
    base.update(over)
    return base


def _src(**over):
    return FC.load(["APP", "GMED"], names={"APP": "AppLovin Corporation",
                                          "GMED": "Globus Medical"},
                   readers=_readers(**over))


# --------------------------------------------------------------------------
# 1 — earnings
# --------------------------------------------------------------------------
def test_01_earnings_after_the_close_the_day_before_sits_in_the_window():
    src = _src(earnings=lambda s, n, db: {"APP": {"date": "2026-02-11", "when": "AMC",
                                                  "eps_actual": 2.08, "eps_estimate": 1.85,
                                                  "surprise_pct": 12.43}})
    items = FC.items_for("APP", DROP, src)
    assert [i["kind"] for i in items] == ["earnings"]
    assert items[0]["text"] == ("earnings report 2026-02-11 after the close · EPS 2.08 vs 1.85 est "
                                "(+12.43% surprise)")
    assert items[0]["url"] is None and items[0]["source"] == "earnings_calendar"


def test_01b_NEG_a_report_outside_the_window_and_no_session_words_without_when():
    out = _src(earnings=lambda s, n, db: {"APP": {"date": "2026-02-09", "when": "BMO",
                                                  "eps_actual": 1.0}})
    assert FC.items_for("APP", DROP, out) == []
    src = _src(earnings=lambda s, n, db: {"APP": {"date": "2026-02-12", "when": None,
                                                  "eps_actual": -0.31, "eps_estimate": None}})
    t = FC.items_for("APP", DROP, src)[0]["text"]
    assert t == "earnings report 2026-02-12 · EPS −0.31"
    assert "before the open" not in t and "after the close" not in t
    bmo = FC.earnings_item({"date": "2026-02-12", "when": "BMO"})
    assert bmo["text"] == "earnings report 2026-02-12 before the open"


# --------------------------------------------------------------------------
# 2 — 8-K / shelf
# --------------------------------------------------------------------------
def test_02_promo_circuit_8k_items_and_shelf_in_the_window():
    row = {"ticker": "APP",
           "eightk": {"form": "8-K", "filing_date": "2026-02-12", "items": ["2.02", "7.01"],
                      "url": "https://www.sec.gov/x"},
           "edgar": {"shelf": {"form": "S-3", "filing_date": "2026-02-13", "url": None}}}
    src = _src(filing=lambda s, n, db: {"APP": row})
    items = FC.items_for("APP", DROP, src)
    # the shelf is dated the day AFTER the drop: kept in the fold, labelled (critic 2026-10-03)
    assert [i["text"] for i in items] == ["8-K 2026-02-12 items 2.02, 7.01",
                                          "after the drop: offering / shelf filing S-3 2026-02-13"]
    assert [i["after_drop"] for i in items] == [False, True]
    assert items[0]["url"] == "https://www.sec.gov/x" and items[1]["url"] is None


def test_02b_NEG_filings_outside_the_window_never_attach():
    row = {"eightk": {"filing_date": "2026-03-01", "items": ["1.01"]},
           "edgar": {"shelf": {"form": "424B5", "filing_date": "2026-01-02"}}}
    assert FC.items_for("APP", DROP, _src(filing=lambda s, n, db: {"APP": row})) == []


# --------------------------------------------------------------------------
# 3 — medical
# --------------------------------------------------------------------------
def test_03_medical_events_dated_by_published_at_ms_and_iso():
    ms = int(pd.Timestamp("2026-02-12 15:00", tz="America/New_York").timestamp() * 1000)
    evs = [{"ticker": "GMED", "published_at": ms, "label": "Phase 3 readout"},
           {"ticker": "GMED", "published_at": "2026-02-13T02:00:00Z", "headline": "FDA CRL"},
           {"ticker": "GMED", "published_at": "2026-02-20T12:00:00Z", "label": "later"}]
    src = _src(medical=lambda s, n, db: {"GMED": evs})
    items = FC.items_for("GMED", DROP, src)
    # 02:00Z = ET 21:00 the day before; same day -> the SOURCE's order breaks the
    # tie, never the raw text (critic 2026-10-03). 21:00 ET is AFTER that day's
    # close, so the CRL is labelled after the drop (critic r3 2026-10-03)
    assert [i["text"] for i in items] == ["medical event 2026-02-12: Phase 3 readout",
                                          f"{FC.AFTER_DROP}: medical event 2026-02-12: FDA CRL"]
    assert FC.et_date(ms) == "2026-02-12" and FC.et_date(ms / 1000) == "2026-02-12"
    assert FC.et_date("2026-02-13T02:00:00Z") == "2026-02-12"
    assert FC.et_date(None) is None and FC.et_date("not a date") is None and FC.et_date(True) is None


# --------------------------------------------------------------------------
# 4 — index deletions
# --------------------------------------------------------------------------
def test_04_a_sane_removal_in_the_window_and_NEG_the_seed_row_ignored():
    rows = [{"index": "sp500", "date": "2026-02-12", "removed": ["APP", "ZZZ"], "sane": True},
            {"index": "russell1000", "date": "2026-02-12", "removed": ["APP"]},       # seed: no sane
            {"index": "sp400", "date": "2026-02-12", "removed": ["APP"], "sane": False},
            {"index": "sp600", "date": "2026-03-12", "removed": ["APP"], "sane": True}]
    src = _src(index=lambda s, n, db: rows)
    items = FC.items_for("APP", DROP, src)
    assert [i["text"] for i in items] == ["removed from sp500 (detected 2026-02-12)"]


# --------------------------------------------------------------------------
# 5 — news
# --------------------------------------------------------------------------
def _ts(iso):
    return int(pd.Timestamp(iso, tz="America/New_York").timestamp())


def test_05_news_relevance_dedupe_and_undated():
    gmed = [{"title": "Intuitive Surgical beats estimates", "url": "u1", "source": "Reuters",
             "published": _ts("2026-02-12 10:00"), "cache": "finnhub_cache_v2"},
            {"title": "Globus Medical cuts outlook", "url": "u2", "source": "Reuters",
             "published": _ts("2026-02-12 08:00"), "cache": "finnhub_cache_v2"},
            {"title": "Globus Medical cuts outlook", "url": "u3", "source": "Yahoo",
             "published": _ts("2026-02-12 09:00"), "cache": "pioneer_news_cache"},
            {"title": "Globus Medical other story", "url": "u2", "source": "X",
             "published": _ts("2026-02-12 09:30"), "cache": "pioneer_news_cache"},
            {"title": "Globus Medical undated note", "url": "u4", "source": "Y",
             "published": None, "cache": "pioneer_news_cache"}]
    src = _src(news=lambda s, n, db: {"GMED": gmed})
    items = FC.items_for("GMED", DROP, src)
    assert [i["text"] for i in items] == ["headline 2026-02-12: “Globus Medical cuts "
                                          "outlook” — Reuters"]
    assert items[0]["url"] == "u2" and items[0]["source"] == "finnhub_cache_v2"


def test_05b_the_reader_normalises_every_cache_shape(monkeypatch):
    class _Coll:
        def __init__(self, docs):
            self.docs = docs

        def find(self, q, proj=None):
            return list(self.docs)

    class _DB(dict):
        def __getitem__(self, k):
            return dict.get(self, k) or _Coll([])

    db = _DB(finnhub_cache_v2=_Coll([{"symbol": "APP", "data": {"rows": [
        {"headline": "AppLovin falls", "url": "f", "source": "FH", "datetime": _ts("2026-02-12 9:00")}]}}]),
        product_launches=_Coll([{"symbol": "APP", "title": "AppLovin launches X", "url": "p",
                                 "published_at": "2026-02-13T15:00:00Z"}]),
        supply_demand_edge_news=_Coll([{"headlines": [{"title": "AppLovin and peers slide",
                                                        "tickers": ["APP", "META"], "url": "e",
                                                        "published_utc": "2026-02-12T15:00:00Z"}]}]),
        promo_news_cache=_Coll([{"_id": "APP", "catalyst": {"top": {
            "title": "AppLovin short report", "url": "s", "published_utc": "2026-02-11T15:00:00Z"}}}]))
    raw = FC._read_news(["APP"], {"APP": "AppLovin"}, db)
    caches = sorted(n["cache"] for n in raw["APP"])
    assert caches == ["finnhub_cache_v2", "product_launches", "promo_news_cache",
                      "supply_demand_edge_news"]
    assert "META" not in raw
    src = FC.load(["APP"], names={"APP": "AppLovin"}, readers=_readers(
        news=lambda s, n, d: FC._read_news(s, n, db)))
    got = FC.items_for("APP", DROP, src)
    assert len(got) == 4 and all(i["kind"] == "news" for i in got)


# --------------------------------------------------------------------------
# 6 — analyst + model
# --------------------------------------------------------------------------
def test_06_analyst_text_and_the_model_read_labelled_and_capped():
    acts = {"APP": {"actions": [{"date": "2026-02-12", "firm": "Citi", "action": "down",
                                 "from_grade": "Buy", "to_grade": "Neutral",
                                 "prior_pt": 600.0, "new_pt": 420.0},
                                {"date": "2026-02-12", "firm": "MS", "action": "main"},
                                {"date": "2026-04-01", "firm": "late"}]}}
    long = "x" * 500
    model = {"APP": [("news_two_sided", {"date": "2026-02-12", "read_by": "lmstudio",
                                         "bear": long, "why_positive": "y"})]}
    src = _src(analyst=lambda s, n, db: acts, model=lambda s, n, db: model)
    items = FC.items_for("APP", DROP, src)
    texts = [i["text"] for i in items]
    assert texts[0] == "analyst 2026-02-12: Citi down Buy→Neutral, PT 600→420"
    assert texts[1] == "analyst 2026-02-12: MS main"
    m = [i for i in items if i["kind"] == "model"][0]
    assert m["text"].startswith("model's read (cached, lmstudio, 2026-02-12): xxx")
    assert len(m["text"]) == FC.MODEL_READ_CHARS and m["source"] == "news_two_sided"
    assert FC.model_item({"date": "2026-02-12", "bear": "", "why_positive": None}, "x") is None


def test_06b_NEG_the_catalyst_one_liner_cache_is_never_read():
    src = (BACKEND / "chart_maps" / "fallen_catalysts.py").read_text(encoding="utf-8")
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    code = "\n".join(ln.split("#", 1)[0] for ln in code.splitlines())
    assert "catalyst_summaries" not in code and "macro_context" not in code
    assert "bonde_fin" not in code and "whales13d" not in code and "insider" not in code


# --------------------------------------------------------------------------
# 7 — the 💥 line
# --------------------------------------------------------------------------
def test_07_hit_class_follows_priority_and_the_line_says_possible():
    items = [{"kind": "news", "text": "headline …"}, {"kind": "earnings", "text": "earnings report X"},
             {"kind": "model", "text": "model's read"}]
    assert FC.hit_class(items) == "earnings"
    assert FC.hit_class([{"kind": "analyst"}, {"kind": "filing"}]) == "filing"
    group = {"line": "XLC −1.80% · RSP −1.31% that day"}
    t = FC.hit_text(DROP, items, group)
    assert t == ("\U0001F4A5 What hit it: −19.7% on 2026-02-12 (gap −11.6%, 3.6× its "
                 "50-day volume) — possible: earnings report X · XLC −1.80% · RSP "
                 "−1.31% that day")


def test_07b_NEG_nothing_on_file_and_no_banned_word():
    t = FC.hit_text({**DROP, "vol_x50": None}, [], {"line": ""})
    assert t == ("\U0001F4A5 What hit it: −19.7% on 2026-02-12 (gap −11.6%) — "
                 "possible: nothing on file")
    assert FC.hit_class([]) == "nothing"
    e = FC.empty_kinds([])
    assert e == ("nothing on file: earnings, 8-K / offering, medical, index deletion, news, "
                 "analyst action, model read; guidance: this app stores none")
    assert "earnings" not in FC.empty_kinds([{"kind": "earnings"}]).split(";")[0]
    for s in (t, e, FC.POSSIBLE_NOTE, FC.drop_line(DROP), FC.hit_text(DROP, [], None)):
        assert not _BANNED.search(s), s
    src = (BACKEND / "chart_maps" / "fallen_catalysts.py").read_text(encoding="utf-8")
    assert not _BANNED.search(src)
    assert FC.drop_line(DROP) == ("−19.68% on 2026-02-12 · gap −11.56%, intraday "
                                  "−9.18% · 3.62× volume · 19.28% of the fall")


# --------------------------------------------------------------------------
# 8 — the group day
# --------------------------------------------------------------------------
def test_08_group_day_etf_theme_median_excluding_the_name_and_rsp():
    theme = U.THEME_BY_TICKER["NVDA"]
    members = [str(m).upper() for m in U.THEME_UNIVERSE[theme] if str(m).upper() != "NVDA"]
    rets = {"XLK": {"2026-02-12": -1.8}, T.BENCHMARK: {"2026-02-12": -1.31},
            "NVDA": {"2026-02-12": -50.0}}
    for i, m in enumerate(members[:3]):
        rets[m] = {"2026-02-12": [-2.0, -4.0, -3.0][i]}
    g = FC.group_day("NVDA", "2026-02-12", "Technology", rets)
    assert g["sector_etf"] == T.SECTOR_ETF["Technology"] == "XLK" and g["sector_etf_pct"] == -1.8
    assert g["theme"] == theme and g["theme_median_pct"] == -3.0 and g["theme_n"] == 3
    assert g["rsp_pct"] == -1.31
    assert g["line"] == (f"XLK −1.80% · theme {theme} median −3.00% (n=3) · RSP "
                         "−1.31% that day")


def test_08b_NEG_alone_in_its_theme_and_no_verdict_word():
    g = FC.group_day("ZZZZ", "2026-02-12", None, {T.BENCHMARK: {"2026-02-12": 0.5}})
    assert g["theme_median_pct"] is None and g["theme_n"] == 0 and g["sector_etf"] is None
    assert g["line"] == "RSP +0.50% that day"
    assert FC.GROUP_DAY_CUT is None
    for word in ("sector-wide", "name-specific", "verdict"):
        assert word not in g["line"]
    assert FC.group_day("ZZZZ", "2026-02-12", None, {})["line"] == ""


def test_08c_day_returns_off_cached_frames():
    idx = pd.DatetimeIndex(pd.to_datetime(["2026-02-10", "2026-02-11", "2026-02-12"]))
    frames = {"XLK": pd.DataFrame({"close": [100.0, 100.0, 98.2]}, index=idx)}
    r = FC.day_returns(frames, ["XLK", "MISSING"], {"2026-02-12", "2026-02-10"})
    assert round(r["XLK"]["2026-02-12"], 2) == -1.8 and "2026-02-10" not in r["XLK"]
    assert "MISSING" not in r


# --------------------------------------------------------------------------
# 9 — one failing reader costs only itself
# --------------------------------------------------------------------------
def test_09_a_raising_reader_is_unavailable_alone():
    def boom(s, n, db):
        raise RuntimeError("analyst store down")
    src = _src(analyst=boom, earnings=lambda s, n, db: {"APP": {"date": "2026-02-12"}})
    assert src["analyst"]["available"] is False and "analyst store down" in src["analyst"]["error"]
    assert src["earnings"]["available"] is True
    assert [i["kind"] for i in FC.items_for("APP", DROP, src)] == ["earnings"]
    out = FC.attach_all({"APP": [DROP]}, sectors={"APP": "Communication Services"},
                        names={"APP": "AppLovin"}, frames={},
                        readers=_readers(analyst=boom, frames=lambda s: (_ for _ in ()).throw(
                            RuntimeError("frames down"))))
    d = out["by_sym"]["APP"][0]
    assert d["items"] == [] and d["group"]["line"] == "" and d["line"] == FC.drop_line(DROP)
    assert out["src_meta"]["analyst"]["available"] is False
    assert out["src_meta"]["earnings"]["available"] is True


# --------------------------------------------------------------------------
# 10 — source guard: cache only
# --------------------------------------------------------------------------
def test_10_NEG_no_provider_or_live_call_in_the_module():
    src = (BACKEND / "chart_maps" / "fallen_catalysts.py").read_text(encoding="utf-8")
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    code = "\n".join(ln.split("#", 1)[0] for ln in code.splitlines())
    for bad in ("get_13d", "insider_activity", "analyst_pulse.get_map", "get_map(",
                "analyst_pulse.refresh", "refresh(", "promo_circuit.build", "PC.build",
                "company_news", "fetch_", "requests", "httpx", "bulk_snapshot", "load_prices"):
        assert bad not in code, bad
    assert "earnings_watch.last_report_map" in code and "store.events_for_tickers" in code
    assert 'find_one({"_id": "latest"})' in code and "universe_changes.recent" in code


# --------------------------------------------------------------------------
# 11 — the sources block
# --------------------------------------------------------------------------
def test_11_sources_block_counts_over_the_pool():
    from catalysts import promo_circuit as PC
    reads = {"APP": [DROP, {**DROP, "date": "2026-05-01",
                            "window": {"lo": "2026-04-30", "hi": "2026-05-04"}}],
             "GMED": [DROP]}
    out = FC.attach_all(reads, sectors={}, names={"APP": "AppLovin", "GMED": "Globus Medical"},
                        frames={}, readers=_readers(
                            earnings=lambda s, n, db: {"APP": {"date": "2026-02-12"}},
                            medical=lambda s, n, db: {"GMED": [{"published_at": "2026-01-05",
                                                                "label": "old"}]}))
    cov = out["coverage"]
    assert cov == {"drops_total": 3, "drops_nothing": 2, "names_with_item": 1, "names": 2}
    blk = FC.sources_block(out["src_meta"], cov)
    assert blk["drops"] == 3 and blk["nothing_on_file"] == 2
    assert blk["nothing_line"] == "2 of 3 drop days have nothing dated on file."
    assert blk["note"] == FC.POSSIBLE_NOTE
    assert "earnings: the latest report per name only (1)" in blk["line"]
    assert f"the last {PC._EIGHTK_WINDOW_DAYS} / {PC._SEC_WINDOW_DAYS} days (0)" in blk["line"]
    assert "medical: earliest item on a listed name 2026-01-05 (1)" in blk["line"]
    assert "from 2026" not in blk["line"]       # never reads as the source's horizon
    assert f"news: {len(FC.NEWS_CACHES)} caches" in blk["line"]
    assert "index deletions: none on file" in blk["line"]
    keys = [s["key"] for s in blk["sources"]]
    assert keys == list(FC.PRIORITY)
    med = [s for s in blk["sources"] if s["key"] == "medical"][0]
    assert med == {"key": "medical", "label": FC.SOURCE_LABELS["medical"], "available": True,
                   "names": 1, "first": "2026-01-05", "last": "2026-01-05"}
    empty = FC.sources_block({}, {})
    assert empty["nothing_line"] == "0 of 0 drop days have nothing dated on file."
    assert f"{FC.WINDOW_BEFORE} session before to {FC.WINDOW_AFTER} after" in FC.POSSIBLE_NOTE


# --------------------------------------------------------------------------
# critic round 2026-10-03 — regressions
# --------------------------------------------------------------------------
def test_12_NEG_an_item_out_after_the_drop_close_is_never_the_possible_item():
    # PODD shape: −20.1% on the drop day, the downgrade came the NEXT morning
    acts = {"APP": {"actions": [{"date": "2026-02-13", "firm": "BTIG", "action": "down",
                                 "from_grade": "Buy", "to_grade": "Neutral"}]}}
    src = _src(analyst=lambda s, n, db: acts)
    items = FC.items_for("APP", DROP, src)
    assert len(items) == 1 and items[0]["after_drop"] is True
    assert items[0]["text"] == f"{FC.AFTER_DROP}: analyst 2026-02-13: BTIG down Buy→Neutral"
    assert FC.hit_class(items) == "nothing"
    t = FC.hit_text(DROP, items, None)
    assert t.endswith("— possible: nothing on file by that close")
    assert "BTIG" not in t


def test_12b_NEG_an_after_the_close_report_on_the_drop_day_is_after_the_drop():
    # APLD shape: an AMC report on the drop day was not out by that close
    amc = _src(earnings=lambda s, n, db: {"APP": {"date": "2026-02-12", "when": "AMC"}},
               news=lambda s, n, db: {})
    items = FC.items_for("APP", DROP, amc)
    assert items[0]["after_drop"] is True and items[0]["text"].startswith(FC.AFTER_DROP)
    acts = {"APP": {"actions": [{"date": "2026-02-12", "firm": "Citi", "action": "down"}]}}
    both = _src(earnings=lambda s, n, db: {"APP": {"date": "2026-02-12", "when": "AMC"}},
                analyst=lambda s, n, db: acts)
    items = FC.items_for("APP", DROP, both)
    assert [i["kind"] for i in items] == ["earnings", "analyst"]   # fold keeps PRIORITY
    assert FC.hit_class(items) == "analyst"                         # the public one leads
    assert FC.hit_text(DROP, items, None).endswith("possible: analyst 2026-02-12: Citi down")
    # public by the close: BMO / no session word on the day, AMC the day before
    for rep, ok in (({"date": "2026-02-12", "when": "BMO"}, True),
                    ({"date": "2026-02-12"}, True),
                    ({"date": "2026-02-11", "when": "AMC"}, True),
                    ({"date": "2026-02-13", "when": "BMO"}, False)):
        it = FC.earnings_item(rep)
        assert FC.public_by_close(it, DROP["date"]) is ok, rep
    assert FC.public_by_close({"date": None}, DROP["date"]) is False


def test_13_NEG_a_missing_price_target_stored_as_zero_never_prints():
    zero = FC.analyst_item({"date": "2026-02-12", "firm": "BTIG", "action": "down",
                            "from_grade": "Buy", "to_grade": "Neutral",
                            "prior_pt": 0, "new_pt": 0})
    assert zero["text"] == "analyst 2026-02-12: BTIG down Buy→Neutral"
    assert "PT" not in zero["text"]
    init = FC.analyst_item({"date": "2026-02-12", "firm": "X", "action": "init",
                            "to_grade": "Neutral", "prior_pt": 0.0, "new_pt": 83})
    assert init["text"] == "analyst 2026-02-12: X init →Neutral, PT →83"
    neg = FC.analyst_item({"date": "2026-02-12", "firm": "Y", "prior_pt": -1, "new_pt": None})
    assert neg["text"] == "analyst 2026-02-12: Y"
    real = FC.analyst_item({"date": "2026-02-12", "firm": "Z", "prior_pt": 300, "new_pt": 250})
    assert real["text"] == "analyst 2026-02-12: Z PT 300→250"


def test_14_NEG_a_rating_change_leads_a_maintained_rating_never_the_alphabet():
    # HUBS shape: 'BTIG main' sorted before 'Bernstein down' on raw text
    acts = {"APP": {"actions": [
        {"date": "2026-02-12", "firm": "BTIG", "action": "main", "from_grade": "Buy",
         "to_grade": "Buy", "prior_pt": 300, "new_pt": 250},
        {"date": "2026-02-12", "firm": "Zeta", "action": "down"},
        {"date": "2026-02-12", "firm": "Bernstein", "action": "down",
         "from_grade": "Outperform", "to_grade": "Market Perform", "prior_pt": 381,
         "new_pt": 220}]}}
    items = FC.items_for("APP", DROP, _src(analyst=lambda s, n, db: acts))
    firms = [i["text"].split(": ", 1)[1].split()[0] for i in items]
    assert firms == ["Zeta", "Bernstein", "BTIG"]        # changes first, then source order
    assert FC.hit_text(DROP, items, None).endswith("possible: analyst 2026-02-12: Zeta down")


# --------------------------------------------------------------------------
# critic round 2 2026-10-03 — a headline after the close on the drop day
# --------------------------------------------------------------------------
def test_15_NEG_a_headline_after_the_close_on_the_drop_day_is_never_the_possible_item():
    # LQDA shape: the source keeps newest first — the 19:29 ET "after hours"
    # headline came before the 08:05 ET ruling in the cache's own order
    late = {"title": "Why is AppLovin stock trending after hours?", "url": "late",
            "source": "Benzinga", "published": _ts("2026-02-12 19:29"),
            "cache": "finnhub_cache_v2"}
    early = {"title": "Judge rules AppLovin infringes patent", "url": "early",
             "source": "Reuters", "published": _ts("2026-02-12 08:05"),
             "cache": "finnhub_cache_v2"}
    src = _src(news=lambda s, n, db: {"APP": [late, early]})
    items = FC.items_for("APP", DROP, src)
    assert [i["url"] for i in items] == ["early", "late"]          # earliest of the day first
    assert [i["after_drop"] for i in items] == [False, True]
    assert items[1]["text"].startswith(f"{FC.AFTER_DROP}: headline 2026-02-12")
    t = FC.hit_text(DROP, items, None)
    assert t.endswith("possible: headline 2026-02-12: “Judge rules AppLovin infringes "
                      "patent” — Reuters")
    assert "after hours" not in t
    # only the late one on file -> nothing by that close, never the late headline
    only = FC.items_for("APP", DROP, _src(news=lambda s, n, db: {"APP": [late]}))
    assert only[0]["after_drop"] is True
    assert FC.hit_text(DROP, only, None).endswith("possible: nothing on file by that close")


def test_15b_NEG_the_close_cut_edges_and_untimed_items():
    day = DROP["date"]

    def it(ts, d=day):
        return {"kind": "news", "date": d, "ts": ts}
    assert FC.public_by_close(it(_ts("2026-02-12 15:59")), day) is True
    assert FC.public_by_close(it(_ts("2026-02-12 16:00")), day) is False      # AT the close
    assert FC.public_by_close(it(_ts("2026-02-12 16:00") * 1000), day) is False  # ms epoch
    assert FC.public_by_close(it(_ts("2026-02-11 19:00"), "2026-02-11"), day) is True
    assert FC.public_by_close(it(None), day) is True          # untimed same-day: date rule only
    assert FC.public_by_close(it(True), day) is True
    assert FC.public_by_close(it(_ts("2026-02-13 08:00"), "2026-02-13"), day) is False
    assert FC.SESSION_CLOSE.hour == 16 and FC.SESSION_CLOSE.minute == 0
    n = FC.news_item({"et_date": day, "title": "x", "published": _ts("2026-02-12 08:05") * 1000})
    assert n["ts"] == _ts("2026-02-12 08:05")
    assert FC.news_item({"et_date": day, "title": "x", "published": None})["ts"] is None


def test_16_NEG_a_single_day_share_above_100_never_prints_as_a_percent():
    over = FC.drop_line({**DROP, "share_of_fall_pct": 103.80})
    assert "103.80%" not in over and "% of the fall" not in over
    assert over.endswith(" · more than the high-to-close fall (it rallied in between)")
    assert FC.drop_line({**DROP, "share_of_fall_pct": 100.0}).endswith("100.00% of the fall")
    assert "of the fall" not in FC.drop_line({**DROP, "share_of_fall_pct": None})


# --------------------------------------------------------------------------
# critic round 3 2026-10-03 — a medical event after the close on the drop day
# --------------------------------------------------------------------------
def test_16_NEG_a_medical_event_after_the_close_is_never_public_by_that_close():
    from datetime import datetime as _dt
    day = DROP["date"]                                     # 2026-02-12
    late = FC.medical_item({"published_at": _dt(2026, 2, 13, 0, 30),   # naive UTC = 19:30 ET
                            "label": "Phase 3 topline miss"})
    early = FC.medical_item({"published_at": _dt(2026, 2, 12, 13, 34),  # 08:34 ET
                             "label": "FDA advisory vote"})
    assert late["date"] == day and early["date"] == day
    assert FC.public_by_close(late, day) is False
    assert FC.public_by_close(early, day) is True
    assert late["ts"] == _dt(2026, 2, 13, 0, 30, tzinfo=FC.timezone.utc).timestamp()
    # the stored shapes the epoch reader must accept, and the ones it must refuse
    assert FC._epoch_any("2026-02-13T00:30:00Z") == late["ts"]
    assert FC._epoch_any("2026-02-12") is None              # no time of day -> date rule
    assert FC._epoch_any(True) is None and FC._epoch_any(None) is None
    assert FC.medical_item({"published_at": None, "label": "x"}) is None
