"""🩳 POM chip, the 6-K dilution check, share-count sources — the PURE verdict side (2026-11-26, spec sishares §3.2 / §3.4 / §4.1).

Ajay 2026-11-26 ~21:10 ET, verbatim: "Fix the POM chip and the 6-K dilution check. Also find alternative srouces for
this share count, I think the short interest theory is actually working may be its a bias for me on the ones its
working out but lets track them in our list of SI. and maintain a track record of our stocks"

POM's stored record + basis doc are the 11-26 Mongo reads (scratchpad si_pom_ncpl/mongo1.txt); `sec.fts` is laid on
in the FROZEN §3.1 shape with the 11-26 efts answers (efts_num.json: the 11-04 6-K, accession 0001213900-26-116021).
Built default FLOAT_FRESH_WHEN = "issuance_before_float" (HIS CALL #1). Every missing / failed / blocked / switched-off
read leaves today's refusal (one NEGATIVE per state). The second mode `co_dated_no_filing` is driven by monkeypatch.
Display only; UNMEASURED.
"""
from __future__ import annotations

import copy
import json
from datetime import date

import pytest

from short_interest import basis_math as BM
from short_interest import read as SR
from tests.test_si_basis_math_2026_11_24 import _doc, _ok, _rec, _split

TODAY = date(2026, 11, 26)
POM_TODAY_CHIP = "🩳 SI 0.2% shs out · 0.2d · 11/13 · ⚠️ float updated · ⚠️ float stale"     # served 11-26
POM_CHIP = "🩳 SI Moderate 5.0% float · 0.2d · 11/13 · ⚠️ float updated · ⚠️ shares up 14×"
POM_ACCN, POM_DOC = "0001213900-26-116021", "ea0310863-6k_pomdoctor.htm"
POM_URL = "https://www.sec.gov/Archives/edgar/data/1877971/000121390026116021/ea0310863-6k_pomdoctor.htm"
POM_CHECK = ("SEC cover count: read 11/26 20:18 ET — no cover count on file · splits (Massive): read 11/26 20:18 ET · "
             "Yahoo shares outstanding: 35,761,933 as of 2026-11-25.")


# ═════════════════════════════════════════════ builders
def pom_rec(**over):
    d = {"symbol": "POM", "v": 2, "settlement_date": "2026-11-13", "short_interest": 77883,
         "avg_daily_volume": 488881, "days_to_cover": 1.0, "prev_settlement_date": "2026-10-30",
         "prev_short_interest": 250448, "si_change_pct": -68.9, "float_shares": 1119065, "float_asof": "2026-11-09",
         "float_source": "yfinance floatShares (shares_cache)", "shares_outstanding": 2576092,
         "shares_asof": "2026-11-09", "shares_source": "yfinance sharesOutstanding (shares_cache)",
         "pct_of_float": 6.96, "pct_of_shares": 3.02, "squeeze": "low",
         "source": "FINRA short interest (Rule 4560) via Massive /stocks/v1/short-interest",
         "checked_settlement": "2026-11-13", "fetched_at": 1795563605.5089588}
    d.update(over)
    return d


def pom_fts(**over):
    d = {"status": "ok", "since": "2026-10-30", "top_6k": "0001213900-26-116902", "top_6k_filed": "2026-11-06",
         "read_at": "2026-11-27T02:40:00Z", "error": None, "error_at": None,
         "issuance": [{"form": "6-K", "filed": "2026-11-04", "accn": POM_ACCN, "doc": POM_DOC,
                       "ex": [{"type": "EX-10.1", "desc": "DEBT CONVERSION AGREEMENT, DATED NOVEMBER 2, 2026"}]}],
         "number": {"n": 33185841, "from": 2576092, "to": 35761933, "read_at": "2026-11-27T02:40:00Z",
                    "hits": [{"accn": POM_ACCN, "filed": "2026-11-04", "form": "6-K", "doc": POM_DOC}]}}
    d.update(over)
    return d


def pom_doc(fts="default", **sec_over):
    """The 11-26 stored basis doc, plus `sec.fts` (None = the key absent, as on every doc before deploy)."""
    sec = {"status": "none", "since": "2026-10-30", "top_accn": "0001213900-26-056576", "covers": [],
           "filings": [{"form": "6-K", "filed": "2026-11-04", "items": "", "doc": POM_DOC, "file": None,
                        "accn": POM_ACCN, "with": None, "fts": "issuance"}],
           "read_at": "2026-11-27T01:18:59Z", "error": None, "error_at": None, "strikes": 0}
    sec.update(sec_over)
    if fts == "default":
        sec["fts"] = pom_fts()
    elif fts is not None:
        sec["fts"] = fts
    if fts is None:
        sec["filings"] = []
    return {"v": 1, "checked_at": "2026-11-27T01:18:59Z",
            "ref": {"status": "ok", "cik": "0001877971", "type": "CS", "read_at": "2026-11-25T21:49:15Z",
                    "error": None, "error_at": None, "strikes": 0, "share_class_shares": None,
                    "weighted_shares": 35966137},
            "sec": sec,
            "splits": {"status": "ok", "since": "2026-10-30", "rows": [], "read_at": "2026-11-27T01:18:59Z",
                       "error": None, "error_at": None, "strikes": 0},
            "yahoo": {"float_shares": 1545214, "shares_outstanding": 35761933, "as_of": "2026-11-25"},
            "float_track": {"value": 1119065, "since": "2026-11-09", "shares": 2576092, "shares_asof": "2026-11-09",
                            "basis_asof": "2026-11-09", "origin": "si_doc", "carried": []}}


def blk(rec, doc, today=TODAY):
    b = SR.si_block(copy.deepcopy(rec), today, basis=copy.deepcopy(doc))
    json.dumps(b, allow_nan=False)
    return b


def ver(rec, doc, today=TODAY):
    return BM.verdict(copy.deepcopy(rec), copy.deepcopy(doc), today)


@pytest.fixture
def mode(monkeypatch):
    def _set(m):
        monkeypatch.setattr(BM, "FLOAT_FRESH_WHEN", m)
    return _set


def _off_block(rec, doc, monkeypatch):
    monkeypatch.setattr(BM, "FLOAT_FRESH_WHEN", "off")
    b = blk(rec, doc)
    monkeypatch.undo()
    return b


# ═════════════════════════════════════════════ POM expected (§3.2)
def test_POM_expected():
    assert BM.FLOAT_FRESH_WHEN == "issuance_before_float" and BM.FLOAT_FRESH_WHEN in BM.FLOAT_FRESH_MODES
    b = blk(pom_rec(), pom_doc())
    assert b["chip"] == POM_CHIP
    assert (b["pct_of_float"], b["tier"]) == (5.04, "moderate") and SR.tier_of(5.04) == "moderate"
    assert (b["float_shares"], b["float_asof"]) == (1545214, "2026-11-25")
    assert (b["shares_outstanding"], b["pct_of_shares_out"]) == (35761933, 0.22)
    assert b["basis"]["float_refused"] is None and b["headline_basis"] == "float"
    v = ver(pom_rec(), pom_doc())
    assert v["float_fresh"] == {"mode": "issuance_before_float", "accn": POM_ACCN, "filed": "2026-11-04"}
    assert v["float_pct_on_file"] is None and v["tier_text"] is None and v["float_line"] is None
    i = b["basis"]["issuances"][0]
    assert (i["form"], i["filed"], i["shares"], i["before_float"], i["url"]) == \
        ("6-K", "2026-11-04", 33185841, True, POM_URL)
    assert "📄" not in b["chip"] and v["filings"] == []                # 11-04 is before the 11-09 anchor
    assert [f["key"] for f in v["flags"]] == ["float_updated", "count_stale"]
    assert v["flags"][1]["text"] == (
        "⚠️ 14× more shares than the count read with the older float: 35,761,933 (Yahoo, 11/25) vs 2,576,092 (11/9) — "
        "6-K filed 11/4, before that float was read, states 33,185,841 shares (2,576,092 + 33,185,841 = 35,761,933), "
        "so the older count was already out of date; the % of float uses the newer float 1,545,214 (Yahoo 11/25)")


def test_POM_rows_title_and_served_keys():
    b = blk(pom_rec(), pom_doc())
    rows = {r["k"]: r["v"] for r in b["rows"]}
    assert rows["Share counts"] == (
        "short-interest record 2,576,092 (read 11/9) · Yahoo 35,761,933 (read 11/25) · Massive, all classes "
        "35,966,137 (read 11/25 — the provider gives no as-of) · 6-K 11/4 states +33,185,841 · SEC cover: none on file.")
    assert rows["Share issuance"].startswith("6-K 11/4 — the SEC full-text search matched issuance words; it states "
                                             "33,185,841 shares; dated before 11/9")
    ks = [r["k"] for r in b["rows"]]
    assert ks.index("Share counts") < ks.index("Share issuance") < ks.index("Share-count check")
    assert rows["Share-count check"] == POM_CHECK[:-1] + " · 6-K issuance search (SEC full-text): read 11/26 21:40 ET."
    assert "Issuance on file: 6-K 11/4, 33,185,841 shares." in b["title"]
    assert "Share counts" not in b["title"] and "Massive, all classes" not in b["title"]
    assert set(b["basis"]) == set(SR.BASIS_KEYS)
    assert [r["key"] for r in b["basis"]["share_counts"]] == ["record", "yahoo", "massive_weighted", "filing"]


# ═════════════════════════════════════════════ [C1] fail closed: every state → today's served chip
def _no_fts(d):
    d["sec"].pop("fts")


def _fts_status(st):
    return lambda d: d["sec"]["fts"].update(status=st)


def _sec_status(st):
    return lambda d: d["sec"].update(status=st)


def _num(**kw):
    return lambda d: d["sec"]["fts"]["number"].update(**kw)


def _hit(**kw):
    return lambda d: d["sec"]["fts"]["number"]["hits"][0].update(**kw)


def _split_between(d):
    d["splits"]["rows"] = [_split("2026-11-06", 1, 2)]


def _number_none(d):
    d["sec"]["fts"]["number"] = None


FAIL_CLOSED = {
    "fts_absent": _no_fts, "fts_failed": _fts_status("failed"), "fts_blocked": _fts_status("blocked"),
    "fts_off": _fts_status("off"), "fts_none_6k": _fts_status("none_6k"), "sec_failed": _sec_status("failed"),
    "sec_blocked": _sec_status("blocked"), "sec_no_cik": _sec_status("no_cik"),
    "sec_missing": lambda d: d.pop("sec"), "number_none": _number_none, "hits_empty": _num(hits=[]),
    "n_off_by_one": _num(n=33185842), "from_not_this_growth": _num(**{"from": 2576093}),
    "to_not_this_growth": _num(to=35761934), "hit_on_anchor": _hit(filed="2026-11-09"),
    "hit_after_anchor": _hit(filed="2026-11-10"), "split_between_hit_and_anchor": _split_between,
    "hit_form_8K": _hit(form="8-K"), "n_a_float": _num(n=33185841.0), "n_a_bool": _num(n=True),
}


@pytest.mark.parametrize("name", sorted(FAIL_CLOSED))
def test_C1_NEGATIVE_POM_fails_closed(name, monkeypatch):
    doc = pom_doc()
    FAIL_CLOSED[name](doc)
    v = ver(pom_rec(), doc)
    assert v["float_refused"] == "diluted" and v["float_fresh"] is None, name
    b = blk(pom_rec(), doc)
    assert b["tier"] is None and b["pct_of_float"] is None and "⚠️ float stale" in b["chip"]
    assert b == _off_block(pom_rec(), doc, monkeypatch)                      # exactly what "off" (today) serves
    if name in ("fts_absent", "fts_failed", "fts_blocked", "fts_off", "fts_none_6k", "number_none", "hits_empty",
                "n_off_by_one", "from_not_this_growth", "to_not_this_growth", "hit_on_anchor", "hit_after_anchor",
                "hit_form_8K", "n_a_float", "n_a_bool", "sec_no_cik"):
        assert b["chip"] == POM_TODAY_CHIP, name


@pytest.mark.parametrize("m", ["off", "nope", "", None, "ISSUANCE_BEFORE_FLOAT"])
def test_C1_NEGATIVE_mode_off_or_unknown_is_todays_refusal(m, mode):
    mode(m)
    b = blk(pom_rec(), pom_doc())
    assert b["chip"] == POM_TODAY_CHIP and b["basis"]["float_refused"] == "diluted"
    assert ver(pom_rec(), pom_doc())["float_fresh"] is None


def test_C1_POM_with_no_fts_serves_todays_block_byte_for_byte_but_the_two_new_lists():
    b = blk(pom_rec(), pom_doc(fts=None))
    assert b["chip"] == POM_TODAY_CHIP
    assert b["basis"]["issuances"] == [] and isinstance(b["basis"]["share_counts"], list)
    assert {r["k"]: r["v"] for r in b["rows"]}["Share-count check"] == POM_CHECK      # no 4th clause [C9]


def test_C1_a_held_fts_answer_with_error_set_still_proves():
    doc = pom_doc(fts=pom_fts(error="http 500", error_at="2026-11-27T03:00:00Z"))
    assert blk(pom_rec(), doc)["chip"] == POM_CHIP


def test_NEGATIVE_a_suspect_newer_float_is_never_fresh():
    doc = pom_doc()
    doc["yahoo"]["float_shares"] = 40000000                                 # > its own row's 35,761,933 → suspect
    v = ver(pom_rec(), doc)
    assert v["float_update"] is None and v["float_refused"] == "diluted" and v["float_fresh"] is None


# ═════════════════════════════════════════════ the pure proof + co-dating conditions
def _growth(**over):
    g = {"ratio": 13.882, "from_shares": 2576092, "from_asof": "2026-11-09", "from_source": "yahoo",
         "to_shares": 35761933, "to_asof": "2026-11-25", "to_source": "yahoo", "to_form": None}
    g.update(over)
    return g


def _upd(**over):
    u = {"shares": 1545214, "as_of": "2026-11-25", "source": "yahoo", "paired_shares": 35761933,
         "replaced_shares": 1119065, "replaced_asof": "2026-11-09"}
    u.update(over)
    return u


def _ff(upd=None, growth=None, sec=None, events=(), executed=()):
    return BM.float_fresh(_upd() if upd is None else upd, _growth() if growth is None else growth,
                          pom_doc()["sec"] if sec is None else sec, list(events), anchor="2026-11-09",
                          basis_date="2026-11-09", executed=list(executed))


def test_float_fresh_positive_control():
    got = _ff()
    assert got["mode"] == "issuance_before_float"
    assert got["proof"] == {"n": 33185841, "accn": POM_ACCN, "filed": "2026-11-04", "doc": POM_DOC, "form": "6-K"}


@pytest.mark.parametrize("name,kw", [
    ("undated_yahoo_row", {"upd": _upd(as_of=None)}),
    ("no_count_on_the_yahoo_row", {"upd": _upd(paired_shares=None)}),
    ("evidence_after_the_newer_float", {"growth": _growth(to_asof="2026-11-26")}),
    ("yahoo_row_below_the_evidence", {"upd": _upd(paired_shares=35761932)}),
    ("split_between_the_two_dates", {"growth": _growth(to_asof="2026-11-20"), "executed": [_split("2026-11-22", 1, 2)]}),
    ("split_ON_the_evidence_date", {"growth": _growth(to_asof="2026-11-20"), "executed": [_split("2026-11-20", 1, 2)]}),
    ("split_ON_the_newer_float_date", {"growth": _growth(to_asof="2026-11-20"), "executed": [_split("2026-11-25", 1, 2)]}),
    # a REVERSE split rebases the Yahoo row's count UP, so only the same-side test can refuse these two
    ("reverse_split_between_the_two_dates", {"growth": _growth(to_asof="2026-11-20"),
                                             "executed": [_split("2026-11-22", 2, 1)]}),
    ("reverse_split_ON_the_evidence_date", {"growth": _growth(to_asof="2026-11-20"),
                                            "executed": [_split("2026-11-20", 2, 1)]}),
    ("no_upd", {"upd": "x"}), ("no_growth", {"growth": "x"}),
])
def test_NEGATIVE_float_fresh_co_dating_conditions(name, kw, mode):
    assert _ff(**kw) is None, name
    mode("co_dated_no_filing")
    assert _ff(**dict(kw, sec=_known_sec())) is None, name


def test_float_fresh_evidence_dated_before_the_newer_float_is_co_dated():
    g = _growth(to_asof="2026-11-20")
    doc = pom_doc()
    assert _ff(growth=g, sec=doc["sec"]) is not None                        # positive control for the two above


def test_NEGATIVE_a_float_refused_for_a_split_is_never_fresh():
    """The newer float read 11/12 and the 1-for-2 ON the 11/13 settlement: refused split_same_day. The growth and the
    proof alone would pass — the flag saying "the % of float uses the newer float" must not appear."""
    doc = pom_doc()
    doc["yahoo"]["as_of"] = "2026-11-12"
    doc["splits"]["rows"] = [_split("2026-11-13", 1, 2)]
    v = ver(pom_rec(), doc)
    assert v["float_refused"] == "split_same_day" and v["growth"]["to_asof"] == "2026-11-12"
    assert BM.float_fresh(v["float_update"], v["growth"], doc["sec"], [], anchor="2026-11-09",
                          basis_date="2026-11-09", executed=BM._rows(doc["splits"]["rows"])) is not None
    assert v["float_fresh"] is None and "count_stale" not in [f["key"] for f in v["flags"]]


def _known_sec(**over):
    s = _ok(since="2026-08-01", top_accn="a", covers=[], filings=[], fts={"status": "none_6k", "since": "2026-08-01"})
    s.update(over)
    return s


def test_issuance_proof_takes_the_OLDEST_qualifying_hit():
    sec = pom_doc()["sec"]
    sec["fts"]["number"]["hits"] = [{"accn": "0001213900-26-116999", "filed": "2026-11-07", "form": "6-K/A"},
                                    {"accn": POM_ACCN, "filed": "2026-11-04", "form": "6-K", "doc": POM_DOC}]
    p = BM.issuance_proof(sec, _growth(), "2026-11-09", "2026-11-09", [])
    assert p["accn"] == POM_ACCN and p["filed"] == "2026-11-04"


@pytest.mark.parametrize("junk", [None, 5, "x", {}, {"status": "ok"}, {"status": "ok", "fts": 5},
                                  {"status": "ok", "fts": {"status": "ok", "number": {"hits": "x"}}}])
def test_NEGATIVE_issuance_proof_never_raises_on_junk(junk):
    assert BM.issuance_proof(junk, _growth(), "2026-11-09", "2026-11-09", []) is None
    assert BM.issuance_proof(pom_doc()["sec"], junk, "2026-11-09", "2026-11-09", []) is None
    assert BM.issuance_proof(pom_doc()["sec"], _growth(), junk, "2026-11-09", []) is None


# ═════════════════════════════════════════════ [C1] the second mode, co_dated_no_filing (HIS CALL #1 / #2)
def _labt(fts="none_6k", **sec_over):
    from tests.test_si_float_newer_fixes_2026_11_24 import _labt as base
    rec, doc = base()
    if fts is not None:
        doc["sec"]["fts"] = {"status": fts, "since": "2026-08-01"} if isinstance(fts, str) else fts
    doc["sec"].update(sec_over)
    return rec, doc


def test_C1_co_dated_mode_frees_LABT_the_option_made_visible(mode):
    rec, doc = _labt()
    assert blk(rec, doc, date(2026, 11, 24))["basis"]["float_refused"] == "diluted"     # the default: refused
    mode("co_dated_no_filing")
    b = blk(rec, doc, date(2026, 11, 24))
    assert b["chip"] == "🩳 SI Low 4.8% float · ≤1d · 10/30 · ⚠️ float updated · ⚠️ shares up 3.8×"
    v = ver(rec, doc, date(2026, 11, 24))
    assert v["float_fresh"] == {"mode": "co_dated_no_filing", "accn": None, "filed": None}
    f = next(f for f in v["flags"] if f["key"] == "count_stale")
    assert f["text"].startswith("⚠️ 3.8× more shares than when the older float was read: 8,950,088 (SEC 10-Q cover, "
                                "11/13) vs 2,369,688 (11/9) — the newer float 3,201,536 (Yahoo 11/18) was read with")


def _ffai(sec_status="ok", filings="default", fts="none_6k"):
    """FFAI-shaped (the critic's failopen probe): 4 dilution events since the older float; the newer float would read
    39.24% of float."""
    rec = _rec("FFX", short_interest=392400, float_shares=500000, float_asof="2026-10-01",
               shares_outstanding=1000000, shares_asof="2026-10-01", prev_settlement_date=None,
               prev_short_interest=None)
    fl = [{"form": "424B4", "filed": "2026-10-20", "items": "", "doc": "p.htm", "file": "333-1"},
          {"form": "8-K", "filed": "2026-10-18", "items": "3.02,9.01"},
          {"form": "S-1/A", "filed": "2026-10-10", "items": ""}, {"form": "S-1", "filed": "2026-10-05", "items": ""}]
    doc = _doc("FFX", covers=[], splits=[], filings=fl if filings == "default" else filings,
               yahoo={"float_shares": 1000000, "shares_outstanding": 10000000, "as_of": "2026-11-20"})
    doc["sec"]["status"] = sec_status
    if fts:
        doc["sec"]["fts"] = {"status": fts, "since": "2026-10-01"}
    return rec, doc


def test_C1_co_dated_positive_control_on_the_FFAI_shape(mode):
    mode("co_dated_no_filing")
    rec, doc = _ffai(filings=[])
    v = ver(rec, doc, date(2026, 11, 24))
    assert v["float_refused"] is None and v["float_update"]["pct"] == 39.24


@pytest.mark.parametrize("name", ["events", "sec_failed", "sec_blocked", "sec_missing", "filings_cap", "sec_error",
                                  "fts_absent", "fts_failed", "fts_blocked", "fts_off", "fts_error", "fts_cap"])
def test_C1_NEGATIVE_co_dated_stays_refused(name, mode):
    mode("co_dated_no_filing")
    rec, doc = _ffai(filings=[] if name != "events" else "default")
    if name in ("sec_failed", "sec_blocked"):
        rec, doc = _ffai(sec_status=name[4:])                 # the 4 events are invisible to a failed read
    elif name == "sec_missing":
        rec, doc = _ffai()
        doc.pop("sec")
    elif name == "filings_cap":
        doc["sec"]["filings_cap"] = 60
    elif name == "sec_error":
        doc["sec"].update(error="timeout", error_at="2026-11-24T18:00:00Z")
    elif name == "fts_absent":
        doc["sec"].pop("fts")
    elif name in ("fts_failed", "fts_blocked", "fts_off"):
        doc["sec"]["fts"]["status"] = name[4:]
    elif name == "fts_error":
        doc["sec"]["fts"].update(error="http 500")
    elif name == "fts_cap":
        doc["sec"]["fts"].update(cap=100)
    v = ver(rec, doc, date(2026, 11, 24))
    assert v["float_refused"] == "diluted" and v["float_fresh"] is None, name
    assert blk(rec, doc, date(2026, 11, 24))["tier"] is None


def test_C1_NEGATIVE_co_dated_SRTM_KITT_and_a_6K_issuance_event_stay_refused(mode):
    from tests.test_si_float_newer_2026_11_24 import srtm
    from tests.test_si_float_newer_refix3_2026_11_24 import _kitt
    mode("co_dated_no_filing")
    for rec, doc in (srtm(), _kitt()):
        doc["sec"]["fts"] = {"status": "none_6k"}
        assert ver(rec, doc, date(2026, 11, 24))["float_refused"] == "diluted"
    rec, doc = _labt(fts=pom_fts(issuance=[]))
    doc["sec"]["filings"] = [{"form": "6-K", "filed": "2026-11-09", "items": "", "fts": "issuance"}]   # ON the anchor
    assert ver(rec, doc, date(2026, 11, 24))["float_refused"] == "diluted"
    doc["sec"]["filings"][0]["filed"] = "2026-11-08"                         # before it: no event → freed
    assert ver(rec, doc, date(2026, 11, 24))["float_refused"] is None


# ═════════════════════════════════════════════ [C6] the default leaves the rest of the book alone
def test_C6_default_LABT_SRTM_KITT_stay_refused_even_with_a_known_full_text_read():
    from tests.test_si_float_newer_2026_11_24 import srtm
    from tests.test_si_float_newer_refix3_2026_11_24 import _kitt
    for rec, doc in (_labt(), srtm(), _kitt(), _ffai(filings=[])):
        doc["sec"]["fts"] = {"status": "none_6k"}
        assert ver(rec, doc, date(2026, 11, 24))["float_refused"] == "diluted"


def test_C6_GMEX_verdict_is_identical_under_every_mode(monkeypatch):
    from tests.test_si_float_newer_2026_11_24 import gmex_doc, gmex_rec
    got = []
    for m in BM.FLOAT_FRESH_MODES:
        monkeypatch.setattr(BM, "FLOAT_FRESH_WHEN", m)
        got.append(json.dumps(ver(gmex_rec(), gmex_doc(), date(2026, 11, 24)), sort_keys=True, default=str))
    assert len(set(got)) == 1


@pytest.mark.parametrize("m", ["off", "issuance_before_float", "co_dated_no_filing"])
def test_C6_NEGATIVE_AKAN_shape_float_equal_on_the_yahoo_row_is_still_diluted(m, mode):
    mode(m)
    rec = _rec("AKX", short_interest=80000, float_shares=709911, float_asof="2026-11-10", shares_outstanding=800000,
               shares_asof="2026-11-10", prev_settlement_date=None, prev_short_interest=None)
    doc = _doc("AKX", covers=[], splits=[], filings=[{"form": "F-1/A", "filed": "2026-11-20", "items": ""}],
               yahoo={"float_shares": 709911, "shares_outstanding": 3600000, "as_of": "2026-11-20"})   # 4.5×
    doc["sec"]["fts"] = {"status": "none_6k"}
    v = ver(rec, doc, date(2026, 11, 24))
    assert v["float_update"] is None and v["float_refused"] == "diluted" and v["float_fresh"] is None


# ═════════════════════════════════════════════ the 6-K row
def test_6K_marked_on_or_after_the_anchor_is_a_filing_event():
    doc = pom_doc()
    doc["sec"]["filings"].insert(0, {"form": "6-K", "filed": "2026-11-20", "items": "", "accn": "0001213900-26-120000",
                                     "fts": "issuance"})
    b = blk(pom_rec(), doc)
    assert b["chip"] == POM_CHIP + " · 📄 6-K 11/20"
    assert b["basis"]["filings"][0]["kind"] == BM.KIND_FOREIGN_ISSUANCE
    doc["sec"]["filings"][0]["filed"] = "2026-11-09"                         # ON the anchor: counted, same day
    assert blk(pom_rec(), doc)["chip"].endswith(" · 📄 6-K 11/9 · same day")


def test_NEGATIVE_6K_before_the_anchor_is_not_a_filing_event_but_is_an_issuance():
    v = ver(pom_rec(), pom_doc())
    assert v["filings"] == [] and v["issuances"][0]["before_float"] is True


@pytest.mark.parametrize("raw,kind,fts", [
    ({"form": "6-K", "filed": "2026-11-04"}, None, None),                                   # unmarked → no kind
    ({"form": "6-K", "filed": "2026-11-04", "fts": "something"}, None, None),
    ({"form": "8-K", "filed": "2026-11-04", "items": "8.01", "fts": "issuance"}, None, None),   # marker dropped
    ({"form": "8-K", "filed": "2026-11-04", "items": "3.02", "fts": "issuance"}, BM.KIND_UNREGISTERED, None),
    ({"form": "424B5", "filed": "2026-11-04", "fts": "issuance"}, BM.KIND_PROSPECTUS, None),
    ({"form": "6-K/A", "filed": "2026-11-04", "fts": "issuance"}, BM.KIND_FOREIGN_ISSUANCE, "issuance"),
    ({"form": " 6-k ", "filed": "2026-11-04", "fts": "issuance"}, BM.KIND_FOREIGN_ISSUANCE, "issuance"),
])
def test_filings_marker_only_on_a_6K(raw, kind, fts):
    f = BM._filings([raw])[0]
    assert (f["kind"], f["fts"]) == (kind, fts)
    assert BM.filing_kind(raw["form"], raw.get("items", "")) == (None if fts else kind)   # filing_kind untouched


def test_6K_A_marked_is_an_event():
    ev = BM.filing_events([{"form": "6-K/A", "filed": "2026-11-20", "fts": "issuance"}], "2026-11-09")
    assert [(e["form"], e["label"]) for e in ev["events"]] == [("6-K/A", "6-K/A")]


# ═════════════════════════════════════════════ [C13] one offering, one event
def _6k(day):
    return {"form": "6-K", "filed": day, "items": "", "accn": "0000000000-26-00000%s" % day[-1], "fts": "issuance"}


def test_C13_424B5_and_a_marked_6K_the_same_day_is_ONE_event():
    rows = [_6k("2026-11-20"), {"form": "424B5", "filed": "2026-11-20", "items": "", "doc": "p.htm", "file": "333-1"}]
    ev = BM.filing_events(rows, "2026-11-09")
    assert [e["form"] for e in ev["events"]] == ["424B5"] and ev["n_reports"] == 1 and ev["n_filings"] == 2
    doc = pom_doc()
    doc["sec"]["filings"] = rows + doc["sec"]["filings"]
    f = next(f for f in ver(pom_rec(), doc)["flags"] if f["key"] == "filing")
    assert f["short"] == "📄 424B5 11/20"
    assert f["text"] == "📄 dilution filing: 424B5 11/20" + BM.TEXT_FILING_SAME_DAY_6K % 1


def test_C13_F1_and_a_6K_the_same_day_is_one_event():
    ev = BM.filing_events([_6k("2026-11-20"), {"form": "F-1", "filed": "2026-11-20"}], "2026-11-09")
    assert [e["form"] for e in ev["events"]] == ["F-1"] and ev["n_reports"] == 1


def test_C13_a_6K_alone_is_one_event():
    ev = BM.filing_events([_6k("2026-11-20")], "2026-11-09")
    assert [e["form"] for e in ev["events"]] == ["6-K"] and ev["n_reports"] == 0


def test_C13_on_an_E2_day_the_6K_IS_the_event():
    rows = [_6k("2026-11-20")] + [{"form": "424B3", "filed": "2026-11-20", "items": "", "doc": "same.htm",
                                   "file": "333-%d" % i, "with": "6-K"} for i in range(3)]
    ev = BM.filing_events(rows, "2026-11-09")
    assert [e["form"] for e in ev["events"]] == ["6-K"] and ev["n_reports"] == 0 and ev["n_copies"] == 3


def test_C13_NEGATIVE_a_6K_the_day_AFTER_a_424B5_is_two_events():
    rows = [_6k("2026-11-21"), {"form": "424B5", "filed": "2026-11-20", "items": "", "doc": "p.htm", "file": "333-1"}]
    ev = BM.filing_events(rows, "2026-11-09")
    assert [e["form"] for e in ev["events"]] == ["6-K", "424B5"] and ev["n_reports"] == 0


def test_C13_NEGATIVE_a_charter_8K_the_same_day_does_not_swallow_the_6K():
    ev = BM.filing_events([_6k("2026-11-20"), {"form": "8-K", "filed": "2026-11-20", "items": "5.03"}], "2026-11-09")
    assert [e["form"] for e in ev["events"]] == ["6-K"] and len(ev["charter"]) == 1


# ═════════════════════════════════════════════ [C14] _filings is idempotent
def test_C14_filings_twice_equals_once_and_events_match():
    raw = [_6k("2026-11-20"), {"form": "424B5", "filed": "2026-11-20", "items": "", "doc": "p.htm", "file": "333-1"},
           {"form": "6-K", "filed": "2026-11-18"}, {"form": "8-K", "filed": "2026-11-15", "items": ["3.02"]},
           {"form": "8-K", "filed": "2026-11-14", "items": "8.01", "fts": "issuance"}]
    once = BM._filings(raw)
    assert BM._filings(once) == once and all("fts" in f for f in once)
    assert BM.filing_events(raw, "2026-11-09") == BM.filing_events(once, "2026-11-09")


# ═════════════════════════════════════════════ [C9] the check sentence
@pytest.mark.parametrize("fts,words", [
    ({"status": "ok", "read_at": "2026-11-27T02:40:00Z"}, "read 11/26 21:40 ET"),
    ({"status": "ok", "read_at": "2026-11-27T02:40:00Z", "error": "x", "error_at": "2026-11-27T03:00:00Z"},
     "last try failed 11/26 22:00 ET; the answer read 11/26 21:40 ET is used"),
    ({"status": "ok", "read_at": "2026-11-27T02:40:00Z", "cap": 100},
     "read 11/26 21:40 ET — only the first 100 answers are read"),
    ({"status": "none_6k"}, "no 6-K filed in the window"),
    ({"status": "failed", "error_at": "2026-11-27T03:00:00Z"}, "not read — last try failed 11/26 22:00 ET"),
    ({"status": "blocked"}, "not read — paused"), ({"status": "off"}, "switched off"), ({}, "not read"),
    ({"status": "weird"}, "not read"),
])
def test_C9_check_sentence_says_the_full_text_state(fts, words):
    v = ver(pom_rec(), pom_doc(fts=fts))
    assert v["check_text"] == POM_CHECK[:-1] + BM.TEXT_CHECK_FTS % words + "."


@pytest.mark.parametrize("junk", [None, 5, "x", ["ok"]])
def test_C9_NEGATIVE_no_fts_dict_keeps_the_sentence_byte_identical(junk):
    doc = pom_doc(fts=None)
    if junk is not None:
        doc["sec"]["fts"] = junk
    assert ver(pom_rec(), doc)["check_text"] == POM_CHECK


# ═════════════════════════════════════════════ filing_url / issuances
def test_filing_url():
    assert BM.filing_url("0001877971", POM_ACCN, POM_DOC) == POM_URL == BM.filing_url(1877971, POM_ACCN, POM_DOC)


@pytest.mark.parametrize("cik,accn,doc", [
    ("abc", POM_ACCN, POM_DOC), ("", POM_ACCN, POM_DOC), (None, POM_ACCN, POM_DOC), (True, POM_ACCN, POM_DOC),
    (0, POM_ACCN, POM_DOC), (-5, POM_ACCN, POM_DOC), ("12345678901", POM_ACCN, POM_DOC), ("１２３", POM_ACCN, POM_DOC),
    ("1877971", "000121390026116021", POM_DOC), ("1877971", "0001213900-26-11602", POM_DOC),
    ("1877971", "x0001213900-26-116021", POM_DOC), ("1877971", None, POM_DOC),
    ("1877971", POM_ACCN, "a/b.htm"), ("1877971", POM_ACCN, "../x.htm"), ("1877971", POM_ACCN, ".htaccess"),
    ("1877971", POM_ACCN, ""), ("1877971", POM_ACCN, None), ("1877971", POM_ACCN, "a b.htm"),
    ("1877971", POM_ACCN, "x.htm?y=1"), ("1877971", POM_ACCN, "javascript:alert(1)"),
])
def test_NEGATIVE_filing_url_junk_is_None(cik, accn, doc):
    assert BM.filing_url(cik, accn, doc) is None


def test_issuances_shares_only_when_the_number_is_this_growths():
    d = pom_doc()
    d["sec"]["fts"]["number"]["n"] = 33185842
    v = ver(pom_rec(), d)
    assert v["issuances"][0]["shares"] is None and "states" not in v["issuances"][0]["text"]


@pytest.mark.parametrize("fts", [None, {"status": "failed", "issuance": pom_fts()["issuance"]},
                                 {"status": "ok", "issuance": "x"},
                                 {"status": "ok", "issuance": [5, None, {"form": "8-K", "filed": "2026-11-04"},
                                                               {"form": "6-K", "filed": "nope"}]}])
def test_NEGATIVE_issuances_junk_is_empty(fts):
    assert ver(pom_rec(), pom_doc(fts=fts))["issuances"] == []


def test_issuances_bad_exhibits_and_link_dropped():
    f = pom_fts()
    f["issuance"][0].update(doc="../evil.htm", ex=[5, {"type": ""}, {"type": "EX-99.1", "desc": None}])
    i = ver(pom_rec(), pom_doc(fts=f))["issuances"][0]
    assert i["url"] is None and i["ex"] == [{"type": "EX-99.1", "desc": None}]


# ═════════════════════════════════════════════ §3.4 share counts
def test_share_counts_order_and_date_words():
    d = pom_doc()
    d["ref"]["share_class_shares"] = 35761933
    d["sec"]["status"] = "ok"
    d["sec"]["covers"] = [{"as_of": "2026-03-19", "shares": 7847899, "form": "10-Q", "filed": "2026-03-19"}]
    rows = BM.share_counts(pom_rec(), d, ver(pom_rec(), d)["growth"])
    assert [(r["key"], r["date_kind"]) for r in rows] == [
        ("record", "read"), ("yahoo", "read"), ("sec_cover", "as_of"), ("massive_class", "read"),
        ("massive_weighted", "read"), ("filing", "filed")]
    assert rows[1] == {"key": "yahoo", "label": "Yahoo, current row", "shares": 35761933, "float": 1545214,
                       "as_of": "2026-11-25", "date_kind": "read"}
    assert rows[2]["label"] == "SEC 10-Q cover" and rows[3]["as_of"] == "2026-11-25"
    t = BM.share_counts_text(rows, d)
    assert "SEC 10-Q cover 7,847,899 (as of 3/19)" in t and "SEC cover: none on file" not in t
    assert "Massive, this class 35,761,933 (read 11/25 — the provider gives no as-of)" in t
    for w in ("disagree", "⚠️", "differ"):
        assert w not in t


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, False, 0, -5, "nope", None, [1], {}])
def test_NEGATIVE_share_counts_bad_values_are_absent(bad):
    d = pom_doc()
    d["ref"].update(share_class_shares=bad, weighted_shares=bad)
    d["yahoo"] = {"float_shares": bad, "shares_outstanding": bad, "as_of": "2026-11-25"}
    keys = [r["key"] for r in BM.share_counts(pom_rec(), d, None)]
    assert keys == ["record"]
    d.pop("ref")
    d.pop("yahoo")
    assert [r["key"] for r in BM.share_counts(pom_rec(shares_outstanding=bad, float_shares=bad), d, None)] == []
    json.dumps(BM.share_counts(None, None, None), allow_nan=False)


def test_NEGATIVE_share_counts_ref_not_ok_and_filing_without_this_growth():
    d = pom_doc()
    d["ref"]["status"] = "failed"
    assert "massive_weighted" not in [r["key"] for r in BM.share_counts(pom_rec(), d, _growth())]
    assert "filing" not in [r["key"] for r in BM.share_counts(pom_rec(), pom_doc(), _growth(to_shares=35761934))]
    assert "filing" not in [r["key"] for r in BM.share_counts(pom_rec(), pom_doc(), None)]


def test_share_counts_ADR_cover_keeps_the_not_compared_words():
    from tests.test_si_basis_math_2026_11_24 import _jz
    rec, doc = _jz("ADRC")
    v = BM.verdict(rec, doc, date(2026, 11, 24))
    assert "sec_cover" not in [r["key"] for r in v["share_counts"]]
    row = {r["k"]: r["v"] for r in v["rows"]}["Share counts"]
    assert row.endswith("SEC cover: not compared — an ADR's SEC cover counts ordinary shares.")


# ═════════════════════════════════════════════ read side
def test_BASIS_KEYS_carry_the_two_lists_always():
    assert SR.BASIS_KEYS[-2:] == ("share_counts", "issuances")
    for doc in (pom_doc(), pom_doc(fts=None), _doc()):
        b = blk(pom_rec(), doc)
        assert isinstance(b["basis"]["share_counts"], list) and isinstance(b["basis"]["issuances"], list)


def test_NEGATIVE_no_basis_doc_block_byte_identical():
    a, b = SR.si_block(pom_rec(), TODAY), SR.si_block(pom_rec(), TODAY, basis=None)
    assert a == b and "basis" not in a and list(a) == list(SR._BLOCK_KEYS)


def test_NEGATIVE_a_raising_verdict_keeps_the_failed_shape(monkeypatch):
    monkeypatch.setattr(BM, "share_counts", lambda *a: 1 / 0)
    b = blk(pom_rec(), pom_doc())
    assert b["basis"]["status"] == "failed" and b["chip"].endswith("❔ share count unchecked")


def test_NEGATIVE_junk_issuances_in_the_served_basis_make_no_title_sentence():
    b = blk(pom_rec(), pom_doc())
    for junk in (None, "abc", [5, {"label": ""}, {"label": 5}]):
        b["basis"]["issuances"] = junk
        assert SR._issuance_sentences(b) == []
    b["basis"]["issuances"] = [{"label": "6-K 11/4", "shares": float("nan")}]
    assert SR._issuance_sentences(b) == ["Issuance on file: 6-K 11/4."]


def test_rules_sentence_names_the_fresh_mode_and_the_6K():
    s = BM.rules_sentence()
    assert BM.FLOAT_FRESH_MODE_WORDS[BM.FLOAT_FRESH_WHEN] in s and BM.SHORT_COUNT_STALE % "N" in s
    assert "SEC full-text search matches for issuance words" in s and BM.FILING_6K_FORM in s
    assert set(BM.FLOAT_FRESH_MODE_WORDS) == set(BM.FLOAT_FRESH_MODES)
    for w in ("bounce", "signal", "edge"):
        assert w not in s.lower()


def test_rules_sentence_follows_the_mode(mode):
    mode("co_dated_no_filing")
    assert BM.FLOAT_FRESH_MODE_WORDS["co_dated_no_filing"] in BM.rules_sentence()
    mode("nope")
    assert BM.FLOAT_FRESH_MODE_WORDS["off"] in BM.rules_sentence()


# ═════════════════════════════════════════════ ⇄ be-io — the literals typed once per side
def test_literals_pinned_equal_across_the_two_sides():
    from short_interest import sec_fts as SF
    from short_interest import share_basis as SB
    assert SF.FTS_ISSUANCE == BM.FTS_ISSUANCE
    assert SB.SB_REPORT_FORMS[1] == BM.FILING_6K_FORM
    assert tuple(SF.FTS_GOOD) == tuple(BM.FTS_KNOWN_STATUSES)


def test_basis_math_stays_pure_and_never_fetches_the_archive_link():
    import re
    from pathlib import Path
    src = Path(BM.__file__).read_text(encoding="utf-8")
    code = re.sub(r"#[^\n]*", "", re.sub(r'"""[\s\S]*?"""', "", src))
    assert not re.search(r"^\s*(import|from)\s+(requests|pymongo|urllib|short_interest\.share_basis|"
                         r"short_interest import (share_basis|sec_fts))\b", code, re.M)
    for bad in ("requests.get", "urlopen", "insert_one", "update_one", "replace_one"):
        assert bad not in code
    assert code.count("www.sec.gov") == 1                                   # the ONE link constant


# ═════════════════════════════════════════════ §5.2a — the probe's --modes table (fake db; no outside call)
def _probe_db(with_state=True):
    from short_interest import client as SIC
    from short_interest import share_basis as SB
    from tests.test_si_basis_integration_2026_11_24 import DB
    from tests.test_si_float_newer_2026_11_24 import gmex_doc, gmex_rec
    db = DB()
    lr, ld = _labt()
    for sym, rec, doc in (("POM", pom_rec(), pom_doc()), ("LABT", lr, ld), ("GMEX", gmex_rec(), gmex_doc())):
        db[SIC.SI_COLL].docs[sym] = dict(rec, _id=sym, symbol=sym)
        db[SB.SB_COLL].docs[sym] = dict(copy.deepcopy(doc), _id=sym)
    if with_state:
        db[SB.SB_COLL].docs["state|sec"] = {"_id": "state|sec", "blocked_until": "2026-11-27T00:00:00Z"}
    return db


def _no_refresh(*a, **k):
    raise AssertionError("no outside call without --with-fts")


def test_probe_modes_names_POM_only_under_the_default_and_LABT_under_the_second():
    from datetime import datetime, timezone
    from scripts import si_share_basis_probe as PR
    from short_interest import share_basis as SB
    db = _probe_db()
    out = PR.modes_run(db=db, now=datetime(2026, 11, 27, 3, tzinfo=timezone.utc), today=TODAY, refresh=_no_refresh)
    assert out["n_docs"] == 3 and out["built_mode"] == BM.FLOAT_FRESH_WHEN and out["refreshed"] == []
    d = out["movers"]["issuance_before_float"]
    assert [r["symbol"] for r in d] == ["POM"]
    assert d[0]["refused"] == ["diluted", None] and d[0]["tier"] == [None, "moderate"]
    assert d[0]["pct_of_float"] == [None, 5.04] and d[0]["flags_gained"] == ["count_stale"]
    assert d[0]["flags_lost"] == ["float_stale"] and d[0]["listed"] == [None, None]          # no stored read given
    # the second mode frees LABT (HIS CALL #2) and POM too (no 📄 event since 11/9, every read answered)
    assert [r["symbol"] for r in out["movers"]["co_dated_no_filing"]] == ["LABT", "POM"]
    assert db[SB.SB_COLL].writes == 0 and BM.FLOAT_FRESH_WHEN == "issuance_before_float"
    json.dumps(out, allow_nan=False)


def test_probe_modes_with_fts_rereads_only_the_diluted_newer_float_names_store_False():
    from datetime import datetime, timezone
    from scripts import si_share_basis_probe as PR
    db = _probe_db()
    asked = []

    def refresh(sym, d, now, store):
        asked.append((sym, store))
        return pom_doc(fts=pom_fts(status="failed")) if sym == "POM" else {"skipped": "x"}
    out = PR.modes_run(db=db, now=datetime(2026, 11, 27, 3, tzinfo=timezone.utc), today=TODAY, with_fts=True,
                       refresh=refresh)
    assert sorted(asked) == [("LABT", False), ("POM", False)]                 # GMEX is not refused: never asked
    assert out["refreshed"] == ["POM"] and out["movers"]["issuance_before_float"] == []   # the real answer failed


def test_NEGATIVE_probe_modes_a_raising_reread_keeps_the_stored_doc():
    from datetime import datetime, timezone
    from scripts import si_share_basis_probe as PR

    def boom(*a, **k):
        raise RuntimeError("x")
    out = PR.modes_run(db=_probe_db(), now=datetime(2026, 11, 27, 3, tzinfo=timezone.utc), today=TODAY,
                       with_fts=True, refresh=boom)
    assert out["refresh_errors"] == {"LABT": "RuntimeError", "POM": "RuntimeError"}
    assert [r["symbol"] for r in out["movers"]["issuance_before_float"]] == ["POM"]


def test_probe_modes_lists_a_name_entering_the_high_si_list(monkeypatch):
    from datetime import datetime, timezone
    from scripts import si_share_basis_probe as PR
    monkeypatch.setattr(PR, "_listed", lambda block, rd: None if rd is None else [block.get("tier") == "moderate", "x"])
    out = PR.modes_run(db=_probe_db(), now=datetime(2026, 11, 27, 3, tzinfo=timezone.utc), today=TODAY,
                       refresh=_no_refresh, reads={"POM": {"symbol": "POM"}})
    assert out["list_moves"]["issuance_before_float"] == ["POM"]


def test_NEGATIVE_probe_with_fts_needs_modes(monkeypatch):
    from scripts import resiliency_study as RS
    from scripts import si_share_basis_probe as PR
    monkeypatch.setattr(RS, "block_writes", lambda: None)            # never patch pymongo inside the test process
    with pytest.raises(SystemExit) as e:
        PR.main(["--with-fts"])
    assert e.value.code == 2
