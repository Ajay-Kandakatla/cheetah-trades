"""Russell universe refresh 2026-09-29 — the scan was running on May-28 holdings.

`full`'s Russell layer came from iShares exports "as of May 28, 2026" (before
the June reconstitution and the Sep 21 Q3 IPO adds), and the weekly
`universe_changes` job re-read the same file and reported "no change". iShares
had moved its holdings link to `.../latest-holdings.csv`; the old URL returns
the product page as HTML with a `text/csv` header.

Covered here, negatives first-class:
  * the parser on the CURRENT live format and on the OLD ajax format
  * class shares with a SPACE ("BRK B") become the dash form, never dropped
  * residual rows (NO MARKET / Non-Nms / Price 0) and non-equity rows dropped
  * live first -> snapshot on HTML / garbage / a truncated list, with a WARNING,
    never an empty universe; the snapshot is never cached
  * staleness past ISHARES_SNAPSHOT_STALE_DAYS: WARNING + `_stale` + health WARN
  * universe_changes: real adds/drops from live fixtures; a snapshot is refused
  * symbol fates: THRD / TBPH out, DOMO -> HUCK spliced
  * the IPO tab's "today" is the ET date across midnight UTC
  * the committed snapshots themselves

All synthetic: no network, no Mongo.
"""
from __future__ import annotations

import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pd = pytest.importorskip("pandas")

from sepa import prices as P  # noqa: E402
from sepa import symbols as S  # noqa: E402
from sepa import universe as U  # noqa: E402
from sepa import universe_changes as UC  # noqa: E402


# ---------------------------------------------------------------------------
# fixtures: the two CSV formats
# ---------------------------------------------------------------------------
_LIVE_HEADER = ("Ticker,Name,Sector,Asset Class,Market Value,Weight (%),"
                "Notional Value,Quantity,Price,Location,Exchange,Currency,"
                "FX Rate,Market Currency,Accrual Date")
_OLD_HEADER = ("Ticker,Name,Sector,Asset Class,Market Value,Weight (%),"
               "Notional Value,Shares,Price,Location,Exchange,Currency,"
               "FX Rate,Market Currency,Accrual Date")


def _row(tkr, name="CO", asset="Equity", price="10.00", exch="NASDAQ"):
    return (f'"{tkr}","{name}","Information Technology","{asset}","1,000.00",'
            f'"0.01","1,000.00","100.00","{price}","United States","{exch}",'
            f'"USD","1.00","USD","-"')


def live_csv(rows, as_of="Sep 28, 2026", fund="iShares Russell 3000 ETF"):
    """The live latest-holdings.csv shape, byte-for-byte in its structure:
    8 metadata lines, a blank, an UNQUOTED header, quoted rows."""
    head = [fund, f'Fund Holdings as of,"{as_of}"', 'Inception Date,"May 22, 2000"',
            'Shares Outstanding,"47,000,000.00"', 'Stock,"-"', 'Bond,"-"',
            'Cash,"-"', 'Other,"-"', "", _LIVE_HEADER]
    return "\n".join(head + list(rows)) + "\n"


def old_csv(rows, as_of="May 20, 2026"):
    """The pre-2026 `1467271812596.ajax?fileType=csv` shape: `Shares` not
    `Quantity`, class shares JOINED (BRKB), a disclaimer footer."""
    head = ["iShares Russell 1000 ETF", f'Fund Holdings as of,"{as_of}"',
            'Inception Date,"May 15, 2000"', 'Shares Outstanding,"1.00"',
            'Stock,"-"', 'Bond,"-"', 'Cash,"-"', 'Other,"-"', "\xa0", _OLD_HEADER]
    foot = ["\xa0", '"The content contained herein is owned or licensed by '
            'BlackRock and/or its third-party information providers."']
    return "\n".join(head + list(rows) + foot) + "\n"


def _names(n, prefix="Q"):
    return [f"{prefix}{i:04d}" for i in range(n)]


# ---------------------------------------------------------------------------
# the parser — current format
# ---------------------------------------------------------------------------
def test_current_format_parses_and_keeps_equities_in_order():
    text = live_csv([_row("NVDA"), _row("AAPL"), _row("INIO")])
    assert U._parse_ishares_csv(text, source_label="t") == ["NVDA", "AAPL", "INIO"]
    _recs, as_of = U._ishares_csv_records(text, source_label="t")
    assert as_of == "2026-09-28"


@pytest.mark.parametrize("raw,want", [
    ("BRK B", "BRK-B"), ("HEI A", "HEI-A"), ("UHAL B", "UHAL-B"),
    ("BF A", "BF-A"), ("LEN B", "LEN-B"), ("GEF B", "GEF-B"),
    ("MOG A", "MOG-A"), ("CRD A", "CRD-A"), ("BH A", "BH-A"),
])
def test_class_shares_written_with_a_space_become_the_dash_form(raw, want):
    """The live CSV writes "BRK B"; the old shape check dropped it silently
    (HEI-A, BF-A, GEF-B, LEN-B, UHAL-B would have left `full`)."""
    assert U._normalize_ishares_ticker(raw) == want
    assert U._parse_ishares_csv(live_csv([_row(raw)]), source_label="t") == [want]


def test_a_spaced_class_share_goes_through_the_curated_remap_first():
    """RUSHA is curated as-is (yfinance spells it that way): "RUSH A" must
    land on RUSHA, not invent RUSH-A."""
    assert U._normalize_ishares_ticker("RUSH A") == "RUSHA"
    assert U._normalize_ishares_ticker("FCNC A") == "FCNCA"


@pytest.mark.parametrize("raw", ["BRK  B", "ABCDEF A", "BRK BB", "A B C", "BRK b1"])
def test_NEGATIVE_other_spaced_strings_are_still_rejected(raw):
    assert U._normalize_ishares_ticker(raw) is None


def test_non_equity_rows_are_dropped_on_the_CSV_path_too():
    """The network branch used to have no Asset Class filter at all."""
    rows = [_row("NVDA"),
            _row("ESZ6", asset="Futures", exch="Index And Options Market"),
            _row("XTSLA", asset="Money Market"),
            _row("USD", asset="Cash"),
            _row("MARGIN_USD", asset="Cash Collateral and Margins"),
            _row("PBI")]
    assert U._parse_ishares_csv(live_csv(rows), source_label="t") == ["NVDA", "PBI"]


def test_residual_rows_are_dropped_by_the_funds_own_marks():
    """HOLX: NO MARKET at $0.01. VUECF / P5N994: Non-Nms. THRD / SBT / GTXI:
    Price 0.00 on NASDAQ. Categorical marks and an exact zero — no threshold."""
    rows = [_row("NVDA", price="228.86"),
            _row("HOLX", price="0.01", exch="NO MARKET (E.G. UNLISTED)"),
            _row("VUECF", price="1.20", exch="Non-Nms Quotation Service (Nnqs)"),
            _row("THRD", price="0.00"),
            _row("SBT", price="0"),
            _row("PDLI", price="0.00", exch="NYSE"),
            _row("PBI", price="16.38", exch="NYSE")]
    out = U._parse_ishares_csv(live_csv(rows), source_label="t")
    assert out == ["NVDA", "PBI"]


def test_NEGATIVE_a_real_line_is_kept_when_a_same_ticker_residual_exists():
    """IWC lists NTRB twice: the real line at $8.23 and a "SERIES A" line at
    $0.00. The residual goes, the company stays."""
    rows = [_row("NTRB", name="NUTRIBAND INC", price="8.23"),
            _row("NTRB", name="NUTRIBAND INC SERIES A", price="0.00")]
    assert U._parse_ishares_csv(live_csv(rows), source_label="t") == ["NTRB"]


def test_NEGATIVE_a_price_that_is_not_a_number_is_not_evidence_of_death():
    rows = [_row("NVDA", price="-"), _row("AAPL", price="")]
    assert U._parse_ishares_csv(live_csv(rows), source_label="t") == ["NVDA", "AAPL"]


def test_NEGATIVE_small_but_nonzero_prices_and_real_exchanges_are_kept():
    rows = [_row("PENNY", price="0.05"), _row("AMX", exch="Nyse Mkt Llc"),
            _row("CBOE1", exch="Cboe BZX")]
    assert U._parse_ishares_csv(live_csv(rows), source_label="t") == [
        "PENNY", "AMX", "CBOE1"]


def test_dash_placeholder_tickers_are_dropped():
    rows = [_row("-", name="ARCELLX INC CVR"), _row("NVDA")]
    assert U._parse_ishares_csv(live_csv(rows), source_label="t") == ["NVDA"]


# ---------------------------------------------------------------------------
# the parser — old format
# ---------------------------------------------------------------------------
def test_old_ajax_format_still_parses():
    text = old_csv([_row("BRKB"), _row("AAPL"), _row("HEIA"),
                    _row("ESM6", asset="Futures")])
    assert U._parse_ishares_csv(text, source_label="t") == ["BRK-B", "AAPL", "HEI-A"]
    assert U._ishares_csv_records(text, source_label="t")[1] == "2026-05-20"


def test_old_format_disclaimer_footer_never_becomes_a_ticker():
    out = U._parse_ishares_csv(old_csv([_row("AAPL")]), source_label="t")
    assert out == ["AAPL"]


# ---------------------------------------------------------------------------
# the parser — garbage
# ---------------------------------------------------------------------------
_HTML = ("<!DOCTYPE html><html><head><title>iShares Russell 3000 ETF | IWV"
         "</title></head><body>" + "x" * 5000 + "</body></html>")


@pytest.mark.parametrize("text", [_HTML, "", "   \n", "garbage,without,a,header\n1,2,3\n"])
def test_NEGATIVE_html_or_garbage_raises_instead_of_parsing_to_nothing(text):
    with pytest.raises(RuntimeError):
        U._parse_ishares_csv(text, source_label="t")


def test_NEGATIVE_a_header_with_no_equity_rows_raises():
    with pytest.raises(RuntimeError):
        U._parse_ishares_csv(live_csv([_row("ESZ6", asset="Futures")]),
                             source_label="t")


@pytest.mark.parametrize("raw,want", [
    ("Sep 28, 2026", "2026-09-28"), ("05/28/2026", "2026-05-28"),
    ('"May 28, 2026"', "2026-05-28"), ("28-May-2026", "2026-05-28"),
    ("", None), ("not a date", None), (None, None),
])
def test_as_of_parsing(raw, want):
    assert U._parse_as_of(raw) == want


# ---------------------------------------------------------------------------
# the resolve ladder: live -> snapshot -> clean fallback
# ---------------------------------------------------------------------------
@pytest.fixture
def ladder(monkeypatch, tmp_path):
    """Cache in tmp, snapshot in tmp, network and Wikipedia stubbed."""
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(U, "UNIV_CACHE_DIR", cache)
    snap = tmp_path / "iShares-Russell-3000-ETF_holdings.csv"
    today_as_of = date.today().strftime("%b %d, %Y")
    snap.write_text(live_csv([_row(s) for s in _names(1900, "S")], as_of=today_as_of))
    monkeypatch.setattr(U, "_LOCAL_IWV_PATH", snap)
    state = {"text": live_csv([_row(s) for s in _names(2000, "L")],
                              as_of=today_as_of),
             "urls": [], "raise": None}

    def fake_fetch(url, *, timeout=20):
        state["urls"].append(url)
        if state["raise"]:
            raise state["raise"]
        return state["text"]
    monkeypatch.setattr(U, "_fetch_text", fake_fetch)
    monkeypatch.setattr(U, "fetch_sp500", lambda: ["CUR1", "CUR2"])
    monkeypatch.setattr(U, "fetch_sp400", lambda: ["CUR3"])
    monkeypatch.setattr(U, "UNIVERSE", ["CUR0"])
    U._LAST_SOURCE.pop("russell3000", None)
    U.forget_ishares_memos()
    clock = {"t": 1_000_000.0}
    monkeypatch.setattr(U, "_clock", lambda: clock["t"])
    state["clock"] = clock
    state["snap"] = snap
    state["cache"] = cache
    return state


def test_live_holdings_win_and_are_cached(ladder):
    out = U.fetch_russell3000()
    assert out[:2] == ["L0000", "L0001"] and len(out) == 2000
    rec = U.last_source("russell3000")
    assert rec["source"] == U.SRC_ISHARES_NETWORK
    assert rec["as_of"] == date.today().isoformat()
    assert U._cache_path("russell3000") == ladder["cache"] / "russell3000_v2.txt"
    assert U._cache_path("russell3000").exists()
    # the URL is the new latest-holdings link for IWV, not the dead ajax one
    assert ladder["urls"] == [U.ISHARES_HOLDINGS_URL.format(
        pid="239714", slug="ishares-russell-3000-etf")]
    assert "latest-holdings.csv" in ladder["urls"][0]
    assert "ajax" not in ladder["urls"][0]


def test_HTML_response_falls_back_to_the_snapshot_with_a_WARNING(ladder, caplog):
    ladder["text"] = _HTML
    with caplog.at_level(logging.WARNING, logger="sepa.universe"):
        out = U.fetch_russell3000()
    assert len(out) == 1900 and out[0] == "S0000", "never an empty universe"
    assert U.last_source("russell3000")["source"] == U.SRC_ISHARES_SNAPSHOT
    assert any("serving the committed snapshot" in r.getMessage()
               for r in caplog.records if r.levelno == logging.WARNING)
    # NOT cached: a cached snapshot would read back as `cache` and hide the
    # failure, and would keep serving the fallback after iShares recovers.
    assert not U._cache_path("russell3000").exists()


def test_the_live_list_is_retried_once_the_failure_memo_expires(ladder):
    """Round 2 (predicted pin change): the retry now waits out the memo."""
    ladder["text"] = _HTML
    U.fetch_russell3000()
    ladder["text"] = live_csv([_row(s) for s in _names(2000, "L")])
    ladder["clock"]["t"] += U.ISHARES_LIVE_FAILURE_MEMO_SEC
    assert U.fetch_russell3000()[0] == "L0000"
    assert U.last_source("russell3000")["source"] == U.SRC_ISHARES_NETWORK


def test_a_network_exception_falls_back_to_the_snapshot(ladder):
    ladder["raise"] = ConnectionError("network refused")
    assert len(U.fetch_russell3000()) == 1900
    assert U.last_source("russell3000")["source"] == U.SRC_ISHARES_SNAPSHOT


def test_NEGATIVE_a_truncated_live_list_is_rejected_for_the_snapshot(ladder):
    """A CSV that parses to 12 names is a broken parse, not a smaller index:
    the count band rejects it and the snapshot serves."""
    ladder["text"] = live_csv([_row(s) for s in _names(12, "T")])
    out = U.fetch_russell3000()
    assert len(out) == 1900
    assert U.last_source("russell3000")["source"] == U.SRC_ISHARES_SNAPSHOT


def test_NEGATIVE_live_AND_snapshot_failing_is_the_clean_fallback_not_empty(ladder):
    ladder["text"] = _HTML
    ladder["snap"].unlink()
    out = U.fetch_russell3000()
    assert out == ["CUR0", "CUR1", "CUR2", "CUR3"]
    assert U.last_source("russell3000")["source"] == "curated"


def test_NEGATIVE_a_corrupt_snapshot_is_the_clean_fallback_not_empty(ladder):
    ladder["text"] = _HTML
    ladder["snap"].write_text(_HTML)
    assert U.fetch_russell3000() == ["CUR0", "CUR1", "CUR2", "CUR3"]


def test_microcap_both_failing_is_empty_and_recorded(monkeypatch, tmp_path):
    monkeypatch.setattr(U, "UNIV_CACHE_DIR", tmp_path)
    monkeypatch.setattr(U, "_LOCAL_IWC_PATH", tmp_path / "absent.csv")
    monkeypatch.setattr(U, "_fetch_text", lambda url, timeout=20: _HTML)
    assert U.fetch_microcap() == []
    assert U.last_source("microcap")["source"] == "empty"


def test_microcap_live_uses_the_IWC_link(monkeypatch, tmp_path):
    monkeypatch.setattr(U, "UNIV_CACHE_DIR", tmp_path)
    # No snapshot -> no snapshot-anchored floor (round 2), so a 2-name fixture
    # is accepted; the floor itself is pinned in the round-2 tests below.
    monkeypatch.setattr(U, "_LOCAL_IWC_PATH", tmp_path / "absent.csv")
    seen = []

    def fake(url, timeout=20):
        seen.append(url)
        return live_csv([_row("MICRO1"), _row("CRD A")], fund="iShares Micro-Cap ETF")
    monkeypatch.setattr(U, "_fetch_text", fake)
    assert U.fetch_microcap() == ["MICRO1", "CRD-A"]
    assert "239716/ishares-microcap-etf/latest-holdings.csv" in seen[0]


# ---------------------------------------------------------------------------
# staleness: WARNING, `_stale`, health WARN
# ---------------------------------------------------------------------------
def _dated(days_ago):
    return (date.today() - timedelta(days=days_ago)).strftime("%b %d, %Y")


def test_a_stale_snapshot_logs_a_STALE_warning(ladder, caplog):
    ladder["text"] = _HTML
    ladder["snap"].write_text(live_csv([_row(s) for s in _names(1900, "S")],
                                       as_of=_dated(U.ISHARES_SNAPSHOT_STALE_DAYS + 5)))
    with caplog.at_level(logging.WARNING, logger="sepa.universe"):
        U.fetch_russell3000()
    assert any("STALE" in r.getMessage() for r in caplog.records)
    rec = U.last_source("russell3000")
    assert rec["age_days"] == U.ISHARES_SNAPSHOT_STALE_DAYS + 5


def test_NEGATIVE_a_fresh_snapshot_logs_no_STALE_warning(ladder, caplog):
    ladder["text"] = _HTML
    with caplog.at_level(logging.WARNING, logger="sepa.universe"):
        U.fetch_russell3000()
    assert not any("STALE" in r.getMessage() for r in caplog.records)


def test_staleness_is_measured_from_the_holdings_date_not_the_mtime(tmp_path):
    """In the image the file mtime is the build time; the content says when
    the holdings are from."""
    p = tmp_path / "x.csv"
    p.write_text(live_csv([_row("A")], as_of=_dated(200)))       # mtime = now
    assert U._snapshot_age_days(p) == 200.0
    q = tmp_path / "y.csv"
    q.write_text("no date in here\n")
    assert U._snapshot_age_days(q) < 1.0                         # mtime fallback
    assert U._snapshot_age_days(tmp_path / "absent.csv") is None


@pytest.mark.parametrize("age,stale", [
    (U.ISHARES_SNAPSHOT_STALE_DAYS + 1, True),
    (U.ISHARES_SNAPSHOT_STALE_DAYS, False),        # boundary: "older than N"
    (0, False),
])
def test_snapshot_status_flags_stale_past_N_days(monkeypatch, tmp_path, age, stale):
    for attr in ("_LOCAL_IWB_PATH", "_LOCAL_IWV_PATH", "_LOCAL_IWC_PATH"):
        p = tmp_path / f"{attr}.csv"
        p.write_text(live_csv([_row("A")], as_of=_dated(age)))
        monkeypatch.setattr(U, attr, p)
    st = U.ishares_snapshot_status()
    assert set(st) == {"russell1000", "russell3000", "microcap"}
    assert st["russell3000"]["stale"] is stale
    assert st["russell3000"]["stale_after_days"] == U.ISHARES_SNAPSHOT_STALE_DAYS


def test_NEGATIVE_a_missing_snapshot_is_reported_stale_not_fresh(monkeypatch, tmp_path):
    monkeypatch.setattr(U, "_LOCAL_IWV_PATH", tmp_path / "absent.csv")
    st = U.ishares_snapshot_status()["russell3000"]
    assert st["exists"] is False and st["stale"] is True


def _counts_fixture(monkeypatch, tmp_path, *, age, served):
    for attr in ("_LOCAL_IWB_PATH", "_LOCAL_IWV_PATH", "_LOCAL_IWC_PATH"):
        p = tmp_path / f"{attr}.csv"
        p.write_text(live_csv([_row("A")], as_of=_dated(age)))
        monkeypatch.setattr(U, attr, p)
    src = U.SRC_ISHARES_SNAPSHOT if served else U.SRC_ISHARES_NETWORK
    monkeypatch.setattr(U, "fetch_russell3000", lambda: _names(2000))
    monkeypatch.setattr(U, "last_source",
                        lambda n: {"source": src, "n": 2000, "age_days": age})
    return U.universe_counts(names=["russell3000"])


def test_universe_counts_names_a_list_SERVED_from_a_stale_snapshot(monkeypatch, tmp_path):
    got = _counts_fixture(monkeypatch, tmp_path,
                          age=U.ISHARES_SNAPSHOT_STALE_DAYS + 30, served=True)
    assert got["russell3000"]["ok"] is True, "right size..."
    assert got["_stale"] == ["russell3000"], "...wrong vintage"
    assert got["russell3000"]["source"] == U.SRC_ISHARES_SNAPSHOT
    assert got["russell3000"]["snapshot"]["served"] is True


def test_NEGATIVE_a_stale_snapshot_that_is_NOT_served_is_not_flagged(monkeypatch, tmp_path):
    got = _counts_fixture(monkeypatch, tmp_path,
                          age=U.ISHARES_SNAPSHOT_STALE_DAYS + 30, served=False)
    assert got["_stale"] == []


def test_NEGATIVE_a_fresh_served_snapshot_is_not_flagged(monkeypatch, tmp_path):
    got = _counts_fixture(monkeypatch, tmp_path, age=3, served=True)
    assert got["_stale"] == []


def test_health_audit_WARNS_on_a_stale_served_snapshot(monkeypatch):
    from observability import health_audit as H
    monkeypatch.setattr(U, "universe_counts", lambda: {
        "russell3000": {"count": 2000, "expected": [1800, 3200], "ok": True,
                        "snapshot": {"as_of": "2026-05-28", "age_days": 124.0}},
        "_failing": [], "_stale": ["russell3000"]})
    r = H.check_universe_counts()
    assert r["ok"] is False and r["severity"] == H.WARN
    assert "STALE" in r["detail"] and "2026-05-28" in r["detail"]


def test_NEGATIVE_health_audit_is_ok_without_stale_or_failing(monkeypatch):
    from observability import health_audit as H
    monkeypatch.setattr(U, "universe_counts", lambda: {
        "russell3000": {"count": 2000, "expected": [1800, 3200], "ok": True},
        "_failing": [], "_stale": []})
    r = H.check_universe_counts()
    assert r["ok"] is True
    assert "all 1 ticker lists" in r["detail"], "underscore keys are not lists"


# ---------------------------------------------------------------------------
# universe_changes compares LIVE data
# ---------------------------------------------------------------------------
class _Coll:
    def __init__(self, latest=None):
        self._latest = latest
        self.inserted = []

    def find_one(self, *a, **kw):
        return self._latest

    def insert_one(self, doc):
        self.inserted.append(doc)

    def delete_many(self, *a, **kw):
        pass


class _DB:
    def __init__(self, latest=None):
        self.universe_snapshots = _Coll(latest)
        self.universe_changes = _Coll(None)


def test_universe_changes_reports_real_adds_and_drops_from_live_fixtures(ladder):
    """End to end through the real fetcher: last week's LIVE list vs this
    week's LIVE list. The old job re-read the same file and could never see
    this."""
    base = _names(1990, "L")
    prev = base + ["GONE1", "GONE2"]
    ladder["text"] = live_csv([_row(s) for s in base + ["INIO", "HUCK"]])
    db = _DB(latest={"symbols": prev, "source": U.SRC_ISHARES_NETWORK,
                     "taken_at": "t0"})
    r = UC.refresh_one("russell3000", db=db)
    assert r["ok"] is True and r["source"] == U.SRC_ISHARES_NETWORK
    assert r["added"] == ["HUCK", "INIO"] and r["removed"] == ["GONE1", "GONE2"]
    chg = db.universe_changes.inserted[0]
    assert chg["added"] == ["HUCK", "INIO"] and chg["removed"] == ["GONE1", "GONE2"]
    assert db.universe_snapshots.inserted[0]["source"] == U.SRC_ISHARES_NETWORK


def test_NEGATIVE_universe_changes_refuses_the_snapshot_fallback(ladder):
    """A failed live fetch serves the committed file. Diffing it against the
    last live list would publish the file's age as index events; storing it
    would flip the baseline's source. Refused, nothing written."""
    ladder["text"] = _HTML
    db = _DB(latest={"symbols": _names(2000, "L"), "source": U.SRC_ISHARES_NETWORK,
                     "taken_at": "t0"})
    r = UC.refresh_one("russell3000", db=db)
    assert r["ok"] is False and U.SRC_ISHARES_SNAPSHOT in r["reason"]
    assert db.universe_snapshots.inserted == [] and db.universe_changes.inserted == []


def test_NEGATIVE_a_derived_r2000_off_a_snapshot_parent_is_refused(monkeypatch):
    monkeypatch.setattr(UC, "_expire_cache", lambda name: None)
    monkeypatch.setattr(UC, "_fetchers", lambda: {"russell2000": lambda: ["A", "B"]})
    srcs = {"russell2000": U.SRC_DERIVED_R2000,
            "russell1000": U.SRC_ISHARES_NETWORK,
            "russell3000": U.SRC_ISHARES_SNAPSHOT}
    monkeypatch.setattr(U, "last_source", lambda n: {"source": srcs.get(n)})
    db = _DB(latest={"symbols": ["A"], "source": U.SRC_DERIVED_R2000, "taken_at": "t0"})
    r = UC.refresh_one("russell2000", db=db)
    assert r["ok"] is False and "russell3000" in r["reason"]
    assert db.universe_changes.inserted == []


def test_a_derived_r2000_off_live_parents_still_diffs(monkeypatch):
    monkeypatch.setattr(UC, "_expire_cache", lambda name: None)
    monkeypatch.setattr(UC, "_fetchers", lambda: {"russell2000": lambda: ["A", "C"]})
    srcs = {"russell2000": U.SRC_DERIVED_R2000, "russell1000": "cache",
            "russell3000": U.SRC_ISHARES_NETWORK}
    monkeypatch.setattr(U, "last_source", lambda n: {"source": srcs.get(n)})
    monkeypatch.setattr(U, "russell2000_coverage",
                        lambda: {"complete": False, "attributable": False})
    db = _DB(latest={"symbols": ["A", "B"], "source": U.SRC_DERIVED_R2000,
                     "taken_at": "t0"})
    r = UC.refresh_one("russell2000", db=db)
    assert r["ok"] is True and r["added"] == ["C"] and r["removed"] == ["B"]


def test_the_first_live_run_after_the_local_file_is_a_rebaseline(ladder):
    """PINNED, HIS CALL #4: ishares-local -> ishares-network is a construction
    change, so the first live run re-baselines and the June reconstitution /
    Sep IPO adds are NOT published to the change log."""
    ladder["text"] = live_csv([_row(s) for s in _names(2000, "L")])
    db = _DB(latest={"symbols": _names(1950, "L") + ["OLD1"],
                     "source": U.SRC_ISHARES_LOCAL, "taken_at": "t0"})
    r = UC.refresh_one("russell3000", db=db)
    assert r["ok"] is True and r["rebaselined"] is True
    assert r["added"] == [] and r["removed"] == []
    assert db.universe_changes.inserted == []
    assert len(db.universe_snapshots.inserted) == 1


def test_the_not_live_set_carries_the_universe_constant():
    assert U.SRC_ISHARES_SNAPSHOT in UC._not_live()
    assert U.SRC_ISHARES_NETWORK not in UC._not_live()


# ---------------------------------------------------------------------------
# symbol fates
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("sym", ["THRD", "TBPH"])
def test_THRD_and_TBPH_are_delisted_with_dated_evidence(sym):
    import re
    assert S.is_delisted(sym)
    assert S.resolve(sym) == sym
    assert re.search(r"\b20\d\d-\d\d-\d\d\b", S.DELISTED[sym])


def test_DOMO_resolves_to_HUCK_on_its_first_print():
    assert S.resolve("DOMO") == "HUCK"
    rec = S.rename_of("DOMO")
    assert rec["effective"] == "2026-09-24" and "2026-09-24" in rec["evidence"]
    assert S.former_names("HUCK") == ["DOMO"]
    assert not S.is_delisted("DOMO") and not S.is_delisted("HUCK")


def _bar(day, px):
    return pd.DataFrame({"open": [px], "high": [px], "low": [px], "close": [px],
                         "volume": [1_000]}, index=pd.DatetimeIndex([pd.Timestamp(day)]))


def test_DOMO_HUCK_boundary_splices():
    """DOMO 2026-09-23 close 3.55 -> HUCK 2026-09-24 open 3.45 (-2.8%)."""
    out = P.splice_history(_bar("2026-09-23", 3.55), _bar("2026-09-24", 3.45),
                           "DOMO->HUCK")
    assert list(out.index) == [pd.Timestamp("2026-09-23"), pd.Timestamp("2026-09-24")]


def test_load_universe_drops_the_dead_and_maps_the_rename():
    out = U._resolve_fates(["NVDA", "THRD", "TBPH", "DOMO", "VSCO"])
    assert out == ["NVDA", "HUCK", "VSCO"]
    assert U._resolve_fates(["HUCK", "DOMO"]) == ["HUCK"], "collapses, no dup"


@pytest.mark.parametrize("sym", ["HUCK", "ZYME", "VSCO", "VSXY", "GBTG", "GETY"])
def test_NEGATIVE_live_and_his_call_names_are_untouched(sym):
    assert not S.is_delisted(sym)
    assert sym not in S.RENAMES


# ---------------------------------------------------------------------------
# IPO tab: ET date, not UTC
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("now,want", [
    # 2026-09-29 22:30 EDT is already 09-30 in UTC — the tab must say 09-29
    (datetime(2026, 9, 30, 2, 30, tzinfo=timezone.utc), date(2026, 9, 29)),
    (datetime(2026, 9, 30, 3, 59, tzinfo=timezone.utc), date(2026, 9, 29)),
    (datetime(2026, 9, 30, 4, 0, tzinfo=timezone.utc), date(2026, 9, 30)),
    # winter (EST, UTC-5)
    (datetime(2026, 12, 1, 4, 30, tzinfo=timezone.utc), date(2026, 11, 30)),
    (datetime(2026, 12, 1, 5, 0, tzinfo=timezone.utc), date(2026, 12, 1)),
    # a naive timestamp is read as UTC
    (datetime(2026, 9, 30, 2, 30), date(2026, 9, 29)),
    # NEGATIVE: midday is the same date in both zones
    (datetime(2026, 9, 29, 16, 0, tzinfo=timezone.utc), date(2026, 9, 29)),
])
def test_ipo_today_is_the_new_york_date_across_midnight_utc(now, want):
    from chart_maps import ipo as IPO
    assert IPO._today(now) == want


def test_ipo_today_no_longer_reads_utcnow():
    import inspect
    from chart_maps import ipo as IPO
    assert "utcnow" not in inspect.getsource(IPO._today)
    assert str(IPO.ET) == "America/New_York"


# ---------------------------------------------------------------------------
# the committed snapshots (what the image ships if the live fetch blips)
# ---------------------------------------------------------------------------
_SNAPS = {"russell1000": "_LOCAL_IWB_PATH", "russell3000": "_LOCAL_IWV_PATH",
          "microcap": "_LOCAL_IWC_PATH"}


@pytest.mark.parametrize("name", sorted(_SNAPS))
def test_committed_snapshot_parses_inside_its_band_and_is_dated(name):
    path = getattr(U, _SNAPS[name])
    assert path.suffix == ".csv" and path.exists()
    out, as_of = U._load_ishares_file(path, source_label=name)
    lo, hi = U._EXPECTED_COUNTS[name]
    assert lo <= len(out) <= hi
    assert as_of == "2026-09-28"
    assert len(out) == len(set(out))
    for dead in ("THRD", "HOLX", "GTXI", "P5N994", "TBPH", "DOMO"):
        assert dead not in out, (name, dead)


def test_committed_snapshots_carry_the_q3_r1000_ipo_adds():
    r1000, _ = U._load_ishares_file(U._LOCAL_IWB_PATH, source_label="r1000")
    r3000, _ = U._load_ishares_file(U._LOCAL_IWV_PATH, source_label="r3000")
    for s in ("INIO", "QNT", "JMKE", "FRVO", "DPC"):
        assert s in r1000 and s in r3000, s
    for s in ("HEI-A", "BF-A", "GEF-B", "LEN-B", "UHAL-B", "BRK-B", "HUCK"):
        assert s in r3000, s


def test_NEGATIVE_the_may_xls_snapshots_are_gone():
    data = U._DATA_DIR
    for f in ("iShares-Russell-1000-ETF_fund.xls", "iShares-Russell-3000-ETF_fund.xls",
              "iShares-Micro-Cap-ETF_fund.xls"):
        assert not (data / f).exists(), f


def test_the_xls_loader_still_reads_an_old_export(tmp_path):
    """The IWM drop-in path still accepts the SpreadsheetML .xls export."""
    pytest.importorskip("lxml")
    ns = "urn:schemas-microsoft-com:office:spreadsheet"

    def row(*cells):
        return "<Row>" + "".join(
            f'<Cell><Data ss:Type="String">{c}</Data></Cell>' for c in cells) + "</Row>"
    xml = (f'<?xml version="1.0"?><Workbook xmlns="{ns}" xmlns:ss="{ns}">'
           f'<Worksheet ss:Name="Holdings"><Table>'
           + row("Fund Holdings as of", "05/28/2026")
           + row("Ticker", "Name", "Sector", "Asset Class", "Price", "Exchange")
           + row("BRKB", "BERKSHIRE", "Fin", "Equity", "400.00", "NYSE")
           + row("HOLX", "HOLOGIC", "HC", "Equity", "0.01", "NO MARKET (E.G. UNLISTED)")
           + row("ESM6", "EMINI", "Cash", "Futures", "5000", "CME")
           + "</Table></Worksheet></Workbook>")
    p = tmp_path / "iShares-Russell-2000-ETF_fund.xls"
    p.write_text(xml)
    assert U._load_ishares_local_xls(p, source_label="t") == ["BRK-B"]
    assert U.ishares_snapshot_as_of(p) == "2026-05-28"
